# apiApp/management/commands/cron_make_grandparent_account_lineage.py
import logging
import sentry_sdk
from django.core.management.base import BaseCommand
from apiApp.helpers.sm_async import StellarMapAsyncHelpers
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.helpers.sm_cron import StellarMapCronHelpers
from apiApp.managers import StellarCreatorAccountLineageManager
from apiApp.model_loader import DONE_UPDATING_FROM_OPERATIONS_RAW_DATA, IN_PROGRESS_MAKE_GRANDPARENT_LINEAGE, DONE_GRANDPARENT_LINEAGE

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Scheduled task to create grandparent account lineages.

    Uses async for efficiency.
    """
    help = 'This management command is a scheduled task that creates grandparent accounts.'

    def handle(self, *args, **options):
        cron_name = 'cron_make_grandparent_account_lineage'
        try:
            cron_helpers = StellarMapCronHelpers(cron_name=cron_name)
            if not cron_helpers.check_cron_health():
                logger.warning(f"{cron_name} unhealthy; skipping.")
                return

            lineage_manager = StellarCreatorAccountLineageManager()
            lin_queryset = lineage_manager.get_queryset(status=DONE_UPDATING_FROM_OPERATIONS_RAW_DATA)

            if not lin_queryset:
                logger.info(f"{cron_name}: No records to process")
                return

            lineage_manager.update_status(
                id=lin_queryset.id,
                status=IN_PROGRESS_MAKE_GRANDPARENT_LINEAGE)

            lineage_helpers = StellarMapCreatorAccountLineageHelpers()
            async_helpers = StellarMapAsyncHelpers()
            
            # Create grandparent lineage
            async_helpers.execute_async(
                [lin_queryset],
                lineage_helpers.async_make_grandparent_account)
            
            # Fetch and add child accounts to database
            async_helpers.execute_async(
                [lin_queryset],
                lineage_helpers.async_fetch_child_accounts)
            
            self.stdout.write(self.style.SUCCESS(f'Successfully ran {cron_name}'))

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"{cron_name} failed: {e}")
            raise
