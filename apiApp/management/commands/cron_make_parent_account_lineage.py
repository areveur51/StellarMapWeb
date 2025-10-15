# apiApp/management/commands/cron_make_parent_account_lineage.py
import logging
import sentry_sdk
from django.core.management.base import BaseCommand
from django.http import HttpRequest
from apiApp.managers import StellarAccountSearchCacheManager, StellarCreatorAccountLineageManager
from apiApp.helpers.sm_cron import StellarMapCronHelpers
from apiApp.helpers.sm_cache import StellarMapCacheHelpers
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.model_loader import (
    PENDING_MAKE_PARENT_LINEAGE,
    IN_PROGRESS_MAKE_PARENT_LINEAGE,
    DONE_MAKE_PARENT_LINEAGE,
    PENDING_HORIZON_API_DATASETS,
    RE_INQUIRY
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

            inquiry_manager = StellarAccountSearchCacheManager()
            
            # Prioritize new searches (PENDING) over cache refreshes (RE_INQUIRY)
            # Try PENDING first (newest first for better user experience)
            inq_queryset = inquiry_manager.get_queryset(
                status=PENDING_MAKE_PARENT_LINEAGE)
            
            if inq_queryset:
                logger.info(f"Processing new search (PENDING): {inq_queryset.stellar_account}")
            else:
                # If no PENDING entries, process RE_INQUIRY (oldest first for fairness)
                inq_queryset = inquiry_manager.get_queryset(
                    status=RE_INQUIRY)
                if inq_queryset:
                    logger.info(f"Processing cache refresh (RE_INQUIRY): {inq_queryset.stellar_account}")
            
            if inq_queryset:
                inquiry_manager.update_inquiry(
                    stellar_account=inq_queryset.stellar_account,
                    network_name=inq_queryset.network_name,
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
                    stellar_account=inq_queryset.stellar_account,
                    network_name=inq_queryset.network_name,
                    status=DONE_MAKE_PARENT_LINEAGE)
                
                # Update cache with fresh tree data after completing lineage collection
                try:
                    lineage_helpers = StellarMapCreatorAccountLineageHelpers()
                    genealogy_df = lineage_helpers.get_account_genealogy(
                        inq_queryset.stellar_account, inq_queryset.network_name)
                    tree_data = lineage_helpers.generate_tidy_radial_tree_genealogy(genealogy_df)
                    
                    cache_helpers = StellarMapCacheHelpers()
                    cache_helpers.update_cache(
                        inq_queryset.stellar_account,
                        inq_queryset.network_name,
                        tree_data,
                        DONE_MAKE_PARENT_LINEAGE
                    )
                    logger.info(f"Updated cache for {inq_queryset.stellar_account} on {inq_queryset.network_name}")
                except Exception as cache_error:
                    logger.error(f"Failed to update cache: {cache_error}")
                    sentry_sdk.capture_exception(cache_error)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"{cron_name} failed: {e}")
            raise ValueError(f'{cron_name} Error: {e}')

        self.stdout.write(self.style.SUCCESS(f'Successfully ran {cron_name}'))
