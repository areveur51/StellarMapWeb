# apiApp/management/commands/cron_health_check.py
import logging
import datetime
import sentry_sdk
from django.core.management.base import BaseCommand
from apiApp.helpers.sm_cron import StellarMapCronHelpers
from apiApp.helpers.sm_datetime import StellarMapDateTimeHelpers

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Checks and updates cron health status.

    Resets unhealthy crons after buffer time (1.7 hours).
    """
    help = 'Checks the health status of crons and updates their status accordingly'

    def handle(self, *args, **options):
        cron_name = 'cron_health_check'
        try:
            cron_helpers = StellarMapCronHelpers(cron_name=cron_name)
            cron_status = cron_helpers.check_all_crons_health()

            dt_helpers = StellarMapDateTimeHelpers()
            dt_helpers.set_datetime_obj()
            current_dt = dt_helpers.get_datetime_obj()

            if cron_status:
                for cron in cron_status:
                    created_at = cron_status[cron]['created_at']
                    time_diff = current_dt - created_at
                    status = cron_status[cron]['status']
                    if 'UNHEALTHY_' in status and time_diff.total_seconds(
                    ) >= (1.7 * 3600):
                        cron_helpers.set_crons_healthy()
                        logger.info(f"Reset {cron} to HEALTHY after buffer.")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"{cron_name} failed: {e}")
