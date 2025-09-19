# apiApp/management/commands/cron_collect_account_lineage_se_directory.py
import logging
import sentry_sdk
from django.core.management.base import BaseCommand
from apiApp.helpers.sm_async import StellarMapAsyncHelpers
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.helpers.sm_cron import StellarMapCronHelpers
from apiApp.managers import StellarCreatorAccountLineageManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Scheduled task to collect and store SE directory data.

    Uses async for efficiency.
    """
    help = (
        'This management command is a scheduled task that populates the '
        'stellar_expert_explorer_directory_doc_api_href and persistently stores it in the database.'
    )

    def handle(self, *args, **options):
        cron_name = 'cron_collect_account_lineage_se_directory'
        try:
            cron_helpers = StellarMapCronHelpers(cron_name=cron_name)
            if not cron_helpers.check_cron_health():
                logger.warning(f"{cron_name} unhealthy; skipping.")
                return

            async_helpers = StellarMapAsyncHelpers()
            lineage_manager = StellarCreatorAccountLineageManager()
            lin_queryset = lineage_manager.get_all_queryset(status__in=[
                'DONE_UPDATING_HORIZON_ACCOUNTS_FLAGS_DOC_API_HREF'
            ])

            lineage_helpers = StellarMapCreatorAccountLineageHelpers()
            async_helpers.execute_async(
                lin_queryset, lineage_helpers.
                async_stellar_expert_explorer_directory_doc_api_href_from_accounts_raw_data
            )

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"{cron_name} failed: {e}")
            raise ValueError(f'{cron_name} Error: {e}')
