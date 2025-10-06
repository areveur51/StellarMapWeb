# apiApp/management/commands/cron_collect_account_horizon_data.py
import uuid
import re
import logging
import sentry_sdk
from tenacity import retry, stop_after_attempt, wait_random_exponential
from django.core.management.base import BaseCommand
from django.http import HttpRequest
from apiApp.helpers.env import EnvHelpers
from apiApp.helpers.sm_cron import StellarMapCronHelpers
from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers
from apiApp.helpers.sm_utils import StellarMapParsingUtilityHelpers
from apiApp.managers import StellarCreatorAccountLineageManager
from apiApp.services import AstraDocument
from apiApp.models import (
    PENDING_HORIZON_API_DATASETS,
    IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS,
    DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS,
    IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_OPERATIONS,
    DONE_COLLECTING_HORIZON_API_DATASETS_OPERATIONS,
    IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_EFFECTS,
    DONE_HORIZON_API_DATASETS
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
        self._fetch_and_store_accounts(lineage_manager, lin_queryset,
                                       horizon_url, account_id, network_name,
                                       cron_name)
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
                                  network_name: str, cron_name: str):
        """Helper: Fetch/store accounts with retry/timeout."""
        try:
            lineage_manager.update_status(
                id=lin_queryset.id,
                status=IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS)

            sm_horizon_helpers = StellarMapHorizonAPIHelpers(
                horizon_url=horizon_url, account_id=account_id)
            sm_horizon_helpers.set_cron_name(cron_name=cron_name)
            accounts_dict = sm_horizon_helpers.get_base_accounts()

            ext_horiz_acc = f"{horizon_url}/accounts/{account_id}"

            doc_id = self._get_or_create_doc_id(
                lin_queryset.horizon_accounts_doc_api_href)

            astra_doc = AstraDocument()
            astra_doc.set_document_id(document_id=doc_id)
            astra_doc.set_collections_name(collections_name='horizon_accounts')
            res_dict = astra_doc.patch_document(stellar_account=account_id,
                                                network_name=network_name,
                                                external_url=ext_horiz_acc,
                                                raw_data=accounts_dict,
                                                cron_name=cron_name)

            request = HttpRequest()
            request.data = {
                'horizon_accounts_doc_api_href': res_dict.get("href"),
                'status': DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS
            }
            lineage_manager.update_lineage(id=lin_queryset.id, request=request)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise ValueError(f'Error fetching accounts: {e}')

    # Similar @retry decorators and structure for _fetch_and_store_operations, _fetch_and_store_effects
    # Example for operations:
    @retry(wait=wait_random_exponential(multiplier=1, max=71),
           stop=stop_after_attempt(7))
    def _fetch_and_store_operations(self, lineage_manager, lin_queryset,
                                    horizon_url: str, account_id: str,
                                    network_name: str, cron_name: str):
        try:
            lineage_manager.update_status(
                id=lin_queryset.id,
                status=IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_OPERATIONS
            )

            sm_horizon_helpers = StellarMapHorizonAPIHelpers(
                horizon_url=horizon_url, account_id=account_id)
            sm_horizon_helpers.set_cron_name(cron_name=cron_name)
            operations_dict = sm_horizon_helpers.get_account_operations()

            ext_horiz_ops = f"{horizon_url}/accounts/{account_id}/operations"

            doc_id = self._get_or_create_doc_id(
                lin_queryset.horizon_accounts_operations_doc_api_href)

            astra_doc = AstraDocument()
            astra_doc.set_document_id(document_id=doc_id)
            astra_doc.set_collections_name(
                collections_name='horizon_operations')
            res_dict = astra_doc.patch_document(stellar_account=account_id,
                                                network_name=network_name,
                                                external_url=ext_horiz_ops,
                                                raw_data=operations_dict,
                                                cron_name=cron_name)

            request = HttpRequest()
            request.data = {
                'horizon_accounts_operations_doc_api_href':
                res_dict.get("href"),
                'status': DONE_COLLECTING_HORIZON_API_DATASETS_OPERATIONS
            }
            lineage_manager.update_lineage(id=lin_queryset.id, request=request)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise ValueError(f'Error fetching operations: {e}')

    @retry(wait=wait_random_exponential(multiplier=1, max=71),
           stop=stop_after_attempt(7))
    def _fetch_and_store_effects(self, lineage_manager, lin_queryset,
                                 horizon_url: str, account_id: str,
                                 network_name: str, cron_name: str):
        """Helper: Fetch/store effects with retry/timeout."""
        try:
            lineage_manager.update_status(
                id=lin_queryset.id,
                status=IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_EFFECTS
            )

            sm_horizon_helpers = StellarMapHorizonAPIHelpers(
                horizon_url=horizon_url, account_id=account_id)
            sm_horizon_helpers.set_cron_name(cron_name=cron_name)
            effects_dict = sm_horizon_helpers.get_account_effects()

            ext_horiz_eff = f"{horizon_url}/accounts/{account_id}/effects"

            doc_id = self._get_or_create_doc_id(
                lin_queryset.horizon_accounts_effects_doc_api_href)

            astra_doc = AstraDocument()
            astra_doc.set_document_id(document_id=doc_id)
            astra_doc.set_collections_name(
                collections_name='horizon_effects')
            res_dict = astra_doc.patch_document(stellar_account=account_id,
                                                network_name=network_name,
                                                external_url=ext_horiz_eff,
                                                raw_data=effects_dict,
                                                cron_name=cron_name)

            request = HttpRequest()
            request.data = {
                'horizon_accounts_effects_doc_api_href':
                res_dict.get("href"),
                'status': DONE_HORIZON_API_DATASETS
            }
            lineage_manager.update_lineage(id=lin_queryset.id, request=request)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise ValueError(f'Error fetching effects: {e}')

    def _get_or_create_doc_id(self, href: str | None) -> str:
        """Helper: Extract or generate doc ID securely."""
        if href:
            util_helpers = StellarMapParsingUtilityHelpers()
            return util_helpers.get_documentid_from_url_address(
                url_address=href)
        return str(uuid.uuid4())
