# apiApp/management/commands/cron_collect_account_lineage_attributes.py
import logging
import sentry_sdk
from django.core.management.base import BaseCommand
from apiApp.helpers.sm_async import StellarMapAsyncHelpers
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.helpers.sm_cron import StellarMapCronHelpers
from apiApp.managers import StellarCreatorAccountLineageManager
from apiApp.models import DONE_HORIZON_API_DATASETS, IN_PROGRESS_UPDATING_FROM_RAW_DATA, DONE_UPDATING_FROM_RAW_DATA

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Scheduled task to collect and store lineage attributes (home_domain, XLM balance).

    Uses async for efficiency.
    """
    help = (
        'This management command is a scheduled task that populates the '
        'home_domain and XLM balance Horizon API and persistently stores it in the database.'
    )

    def handle(self, *args, **options):
        cron_name = 'cron_collect_account_lineage_attributes'
        try:
            cron_helpers = StellarMapCronHelpers(cron_name=cron_name)
            if not cron_helpers.check_cron_health():
                logger.warning(f"{cron_name} unhealthy; skipping.")
                return

            lineage_manager = StellarCreatorAccountLineageManager()
            lin_queryset = lineage_manager.get_queryset(status=DONE_HORIZON_API_DATASETS)
            
            if not lin_queryset:
                logger.info(f"{cron_name}: No records to process")
                return

            lineage_manager.update_status(
                id=lin_queryset.id,
                status=IN_PROGRESS_UPDATING_FROM_RAW_DATA)

            lineage_helpers = StellarMapCreatorAccountLineageHelpers()
            async_helpers = StellarMapAsyncHelpers()
            async_helpers.execute_async(
                [lin_queryset],
                lineage_helpers.async_update_from_accounts_raw_data)
            
            self.stdout.write(self.style.SUCCESS(f'Successfully ran {cron_name}'))

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"{cron_name} failed: {e}")
            raise
