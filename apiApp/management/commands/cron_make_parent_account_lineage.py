# apiApp/management/commands/cron_make_parent_account_lineage.py
import logging
import sentry_sdk
from django.core.management.base import BaseCommand
from django.http import HttpRequest
from apiApp.managers import UserInquirySearchHistoryManager, StellarCreatorAccountLineageManager
from apiApp.helpers.sm_cron import StellarMapCronHelpers
from apiApp.models import (
    PENDING_MAKE_PARENT_LINEAGE,
    IN_PROGRESS_MAKE_PARENT_LINEAGE,
    DONE_MAKE_PARENT_LINEAGE,
    PENDING_HORIZON_API_DATASETS
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Scheduled task to create parent account lineages.

    Processes pending inquiries; updates statuses.
    """
    help = (
        'This management command is a scheduled task that creates the parent lineage '
        'information from the Horizon API and persistently stores it in the database.'
    )

    def handle(self, *args, **options):
        cron_name = 'cron_make_parent_account_lineage'
        try:
            cron_helpers = StellarMapCronHelpers(cron_name=cron_name)
            if not cron_helpers.check_cron_health():
                logger.warning(f"{cron_name} unhealthy; skipping.")
                return

            inquiry_manager = UserInquirySearchHistoryManager()
            inq_queryset = inquiry_manager.get_queryset(
                status__in=[PENDING_MAKE_PARENT_LINEAGE, 'RE_INQUIRY'])

            if inq_queryset:
                inquiry_manager.update_inquiry(
                    id=inq_queryset.id,
                    status=IN_PROGRESS_MAKE_PARENT_LINEAGE)

                lineage_manager = StellarCreatorAccountLineageManager()
                lin_queryset = lineage_manager.get_queryset(
                    stellar_account=inq_queryset.stellar_account,
                    network_name=inq_queryset.network_name)

                if lin_queryset:
                    lineage_manager.update_status(id=lin_queryset.id,
                                                  status=PENDING_HORIZON_API_DATASETS)
                else:
                    request = HttpRequest()
                    request.data = {
                        'stellar_account': inq_queryset.stellar_account,
                        'network_name': inq_queryset.network_name,
                        'status': PENDING_HORIZON_API_DATASETS
                    }
                    lineage_manager.create_lineage(request)

                inquiry_manager.update_inquiry(
                    id=inq_queryset.id, status=DONE_MAKE_PARENT_LINEAGE)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"{cron_name} failed: {e}")
            raise ValueError(f'{cron_name} Error: {e}')

        self.stdout.write(self.style.SUCCESS(f'Successfully ran {cron_name}'))
