# apiApp/management/commands/cron_collect_account_horizon_data.py
import logging
import sentry_sdk
from tenacity import retry, stop_after_attempt, wait_random_exponential
from django.core.management.base import BaseCommand
from django.http import HttpRequest
from apiApp.helpers.env import EnvHelpers
from apiApp.helpers.sm_cron import StellarMapCronHelpers
from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers
from apiApp.managers import StellarCreatorAccountLineageManager
from apiApp.models import (
    PENDING_HORIZON_API_DATASETS,
    IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS,
    DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS,
    IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_OPERATIONS,
    DONE_COLLECTING_HORIZON_API_DATASETS_OPERATIONS,
    IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_EFFECTS,
    DONE_HORIZON_API_DATASETS,
    INVALID_HORIZON_STELLAR_ADDRESS
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Scheduled task to collect Horizon API data for account lineages.

    Fetches accounts, operations, effects; stores in Astra DB.
    Processes one record at a time to respect rate limits.
    """
    help = (
        'This management command is a scheduled task that creates the parent lineage '
        'information from the Horizon API and persistently stores it in the database.'
    )

    def handle(self, *args, **options):
        cron_name = 'cron_collect_account_horizon_data'
        try:
            cron_helpers = StellarMapCronHelpers(cron_name=cron_name)
            if not cron_helpers.check_cron_health():
                logger.warning(f"{cron_name} unhealthy; skipping.")
                return

            lineage_manager = StellarCreatorAccountLineageManager()
            
            lin_queryset = (
                lineage_manager.get_queryset(status=PENDING_HORIZON_API_DATASETS) or
                lineage_manager.get_queryset(status=DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS) or
                lineage_manager.get_queryset(status=DONE_COLLECTING_HORIZON_API_DATASETS_OPERATIONS)
            )

            lin_in_progress_qs = (
                lineage_manager.get_queryset(status=IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS) or
                lineage_manager.get_queryset(status=IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_OPERATIONS) or
                lineage_manager.get_queryset(status=IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_EFFECTS)
            )

            if lin_queryset and not lin_in_progress_qs:
                self._process_lineage_record(lin_queryset, cron_name)
            else:
                logger.info(f"No eligible records for {cron_name}.")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"{cron_name} failed: {e}")
            raise ValueError(f"{cron_name}: {e}")

        self.stdout.write(self.style.SUCCESS(f'Successfully ran {cron_name}'))

    def _process_lineage_record(self, lin_queryset, cron_name: str):
        """Helper: Process single lineage record securely/efficiently."""
        env_helpers = EnvHelpers()
        network_name = lin_queryset.network_name
        if network_name == 'public':
            env_helpers.set_public_network()
        else:
            env_helpers.set_testnet_network()

        account_id = lin_queryset.stellar_account
        horizon_url = env_helpers.get_base_horizon()

        lineage_manager = StellarCreatorAccountLineageManager()
        
        # Fetch accounts first - if invalid, stop processing
        is_valid = self._fetch_and_store_accounts(lineage_manager, lin_queryset,
                                                  horizon_url, account_id, network_name,
                                                  cron_name)
        
        # Only continue if the address is valid on Horizon
        if not is_valid:
            logger.info(f"Skipping operations/effects for invalid address: {account_id}")
            return
        
        self._fetch_and_store_operations(lineage_manager, lin_queryset,
                                         horizon_url, account_id, network_name,
                                         cron_name)
        self._fetch_and_store_effects(lineage_manager, lin_queryset,
                                      horizon_url, account_id, network_name,
                                      cron_name)

    @retry(wait=wait_random_exponential(multiplier=1, max=71),
           stop=stop_after_attempt(7))
    def _fetch_and_store_accounts(self, lineage_manager, lin_queryset,
                                  horizon_url: str, account_id: str,
                                  network_name: str, cron_name: str) -> bool:
        """
        Helper: Fetch/store accounts with retry/timeout.
        
        Returns:
            bool: True if account is valid and processing should continue,
                  False if account is invalid (404) and processing should stop.
        """
        from stellar_sdk.exceptions import NotFoundError, BaseRequestError
        import json
        try:
            lineage_manager.update_status(
                id=lin_queryset.id,
                status=IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS)

            sm_horizon_helpers = StellarMapHorizonAPIHelpers(
                horizon_url=horizon_url, account_id=account_id)
            sm_horizon_helpers.set_cron_name(cron_name=cron_name)
            accounts_dict = sm_horizon_helpers.get_base_accounts()

            # Store JSON directly in Cassandra TEXT column
            lin_queryset.horizon_accounts_json = json.dumps(accounts_dict)
            lin_queryset.status = DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS
            lin_queryset.save()
            return True  # Valid address, continue processing
            
        except (NotFoundError, BaseRequestError) as e:
            if 'NotFoundError' in str(type(e).__name__) or '404' in str(e):
                logger.warning(f"Invalid Stellar address on Horizon: {account_id} on {network_name}")
                lin_queryset.status = INVALID_HORIZON_STELLAR_ADDRESS
                lin_queryset.last_error = f'Horizon API validation failed: Account not found on {network_name} network'
                lin_queryset.save()
                
                from apiApp.managers import StellarAccountSearchCacheManager
                cache_manager = StellarAccountSearchCacheManager()
                cache_manager.update_inquiry(
                    stellar_account=account_id,
                    network_name=network_name,
                    status=INVALID_HORIZON_STELLAR_ADDRESS
                )
                logger.info(f"Marked {account_id} as INVALID_HORIZON_STELLAR_ADDRESS")
                return False  # Invalid address, stop processing
            else:
                sentry_sdk.capture_exception(e)
                raise ValueError(f'Error fetching accounts: {e}')
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise ValueError(f'Error fetching accounts: {e}')

    @retry(wait=wait_random_exponential(multiplier=1, max=71),
           stop=stop_after_attempt(7))
    def _fetch_and_store_operations(self, lineage_manager, lin_queryset,
                                    horizon_url: str, account_id: str,
                                    network_name: str, cron_name: str):
        import json
        try:
            lineage_manager.update_status(
                id=lin_queryset.id,
                status=IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_OPERATIONS
            )

            sm_horizon_helpers = StellarMapHorizonAPIHelpers(
                horizon_url=horizon_url, account_id=account_id)
            sm_horizon_helpers.set_cron_name(cron_name=cron_name)
            # Fetch operations in ascending order (oldest first) to get create_account operation
            operations_dict = sm_horizon_helpers.get_account_operations(order='asc', limit=200)

            # Store JSON directly in Cassandra TEXT column
            lin_queryset.horizon_operations_json = json.dumps(operations_dict)
            lin_queryset.status = DONE_COLLECTING_HORIZON_API_DATASETS_OPERATIONS
            lin_queryset.save()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise ValueError(f'Error fetching operations: {e}')

    @retry(wait=wait_random_exponential(multiplier=1, max=71),
           stop=stop_after_attempt(7))
    def _fetch_and_store_effects(self, lineage_manager, lin_queryset,
                                 horizon_url: str, account_id: str,
                                 network_name: str, cron_name: str):
        """Helper: Fetch/store effects with retry/timeout."""
        import json
        try:
            lineage_manager.update_status(
                id=lin_queryset.id,
                status=IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_EFFECTS
            )

            sm_horizon_helpers = StellarMapHorizonAPIHelpers(
                horizon_url=horizon_url, account_id=account_id)
            sm_horizon_helpers.set_cron_name(cron_name=cron_name)
            effects_dict = sm_horizon_helpers.get_account_effects()

            # Store JSON directly in Cassandra TEXT column
            lin_queryset.horizon_effects_json = json.dumps(effects_dict)
            lin_queryset.status = DONE_HORIZON_API_DATASETS
            lin_queryset.save()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise ValueError(f'Error fetching effects: {e}')
