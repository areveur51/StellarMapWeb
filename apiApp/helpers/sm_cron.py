# apiApp/helpers/sm_cron.py
import logging
import sentry_sdk
from apiApp.model_loader import ManagementCronHealth


class StellarMapCronHelpers:
    """
    Helper class for cron job management and monitoring.
    """
    
    def __init__(self, cron_name: str):
        """Initialize cron helpers with cron_name."""
        self.cron_name = cron_name
        self.logger = logging.getLogger(__name__)
    
    def log_cron_start(self):
        """Log cron job start."""
        try:
            self.logger.info(f"Starting cron job: {self.cron_name}")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            
    def log_cron_end(self):
        """Log cron job completion.""" 
        try:
            self.logger.info(f"Completed cron job: {self.cron_name}")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            
    def check_cron_health(self) -> bool:
        """Check if cron job is healthy."""
        try:
            cron_health = ManagementCronHealth.objects.filter(
                cron_name=self.cron_name
            ).first()
            
            if cron_health:
                return 'UNHEALTHY' not in cron_health.status
            return True
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return False
    
    def check_all_crons_health(self) -> dict:
        """Check health of all cron jobs - OPTIMIZED: Limited query instead of full table scan."""
        try:
            from datetime import datetime, timedelta
            cron_statuses = {}
            
            # Only fetch recent health records (last 24 hours) with limit to prevent full table scan
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            cron_healths = ManagementCronHealth.objects.filter(
                created_at__gte=recent_cutoff
            ).limit(100)
            
            # Group by cron_name and keep only the most recent status for each
            cron_map = {}
            for cron_health in cron_healths:
                cron_name = cron_health.cron_name
                if cron_name not in cron_map or cron_health.created_at > cron_map[cron_name]['created_at']:
                    cron_map[cron_name] = {
                        'status': cron_health.status,
                        'created_at': cron_health.created_at,
                        'reason': cron_health.reason
                    }
            
            return cron_map
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return {}
    
    def set_crons_healthy(self):
        """Reset unhealthy crons to healthy status."""
        try:
            cron_health = ManagementCronHealth.objects.filter(
                cron_name=self.cron_name
            ).first()
            
            if cron_health:
                cron_health.status = 'HEALTHY'
                cron_health.reason = 'Reset after buffer period'
                cron_health.save()
        except Exception as e:
            sentry_sdk.capture_exception(e)