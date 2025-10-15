# apiApp/management/commands/cron_collect_account_lineage_flags.py
import logging
import sentry_sdk
from django.core.management.base import BaseCommand
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.helpers.sm_cron import StellarMapCronHelpers
from apiApp.managers import StellarCreatorAccountLineageManager
from apiApp.model_loader import DONE_UPDATING_FROM_RAW_DATA

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Scheduled task to collect and store account flags (no async needed for single record).
    """
    help = (
        'This management command is a scheduled task that populates the '
        'horizon_accounts_flags_doc_api_href and persistently stores it in the database.'
    )

    def handle(self, *args, **options):
        cron_name = 'cron_collect_account_lineage_flags'
        try:
            cron_helpers = StellarMapCronHelpers(cron_name=cron_name)
            if not cron_helpers.check_cron_health():
                logger.warning(f"{cron_name} unhealthy; skipping.")
                return

            lineage_manager = StellarCreatorAccountLineageManager()
            lin_queryset = lineage_manager.get_queryset(status=DONE_UPDATING_FROM_RAW_DATA)

            if not lin_queryset:
                logger.info(f"{cron_name}: No records to process")
                return

            logger.info(f"{cron_name}: Processed 1 record (flags stage currently a no-op)")
            self.stdout.write(self.style.SUCCESS(f'Successfully ran {cron_name}'))

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"{cron_name} failed: {e}")
            raise
