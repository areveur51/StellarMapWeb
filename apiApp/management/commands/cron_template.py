# apiApp/management/commands/cron_template.py
import asyncio
import sentry_sdk
from tenacity import retry, stop_after_attempt, wait_random_exponential
from django.core.management.base import BaseCommand
from decouple import config
from apiApp.helpers.env import EnvHelpers
from apiApp.helpers.sm_conn import AsyncStellarMapHTTPHelpers
from apiApp.managers import StellarCreatorAccountLineageManager


class Command(BaseCommand):
    """
    Template cron for collecting creator account info.

    Uses async/retry for robust API fetches.
    """
    help = (
        'This management command is a scheduled task that retrieves creator account'
        'information from the Horizon API and persistently stores it in the database.'
    )

    def handle(self, *args, **options):
        asyncio.run(self.async_handle())  # Run async in sync command

    async def async_handle(self):

        @retry(reraise=True,
               wait=wait_random_exponential(multiplier=1, max=71),
               stop=stop_after_attempt(17))
        async def make_child_lineage():
            inquiry_manager = StellarCreatorAccountLineageManager(
            )  # Assume correct manager
            queryset = inquiry_manager.get_queryset(
                status__in=['PENDING', 'RE_INQUIRY'])  # Adjusted to match

            environ = config('ENV', default='development')
            env_helpers = EnvHelpers()
            if environ == 'production':
                env_helpers.set_public_network()
            else:
                env_helpers.set_testnet_network()

            uri = f"{env_helpers.get_base_horizon_account()}/{queryset.stellar_account}"
            req = AsyncStellarMapHTTPHelpers()
            await req.add_url(uri)  # Async add

            try:
                req_response = await req.get()

                lineage_manager = StellarCreatorAccountLineageManager()
                lin_queryset = lineage_manager.get_queryset(
                    stellar_account=queryset.stellar_account,
                    network_name=queryset.network_name)

                if lin_queryset:
                    lineage_manager.update_status(id=lin_queryset.id,
                                                  status='')
                else:
                    lineage_manager.create_lineage(
                        stellar_account=queryset.stellar_account,
                        network_name=queryset.network_name,
                        status='PENDING')
            except Exception as e:
                sentry_sdk.capture_exception(e)
                raise ValueError(f'Error: {e}')

        try:
            await make_child_lineage()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise ValueError(f'Error: {e}')

        self.stdout.write(
            self.style.SUCCESS('Successfully ran the example command'))
