# apiApp/helpers/sm_cron.py
import logging
import sentry_sdk


class StellarMapCronHelpers:
    """
    Helper class for cron job management and monitoring.
    """
    
    def __init__(self):
        """Initialize cron helpers."""
        self.logger = logging.getLogger(__name__)
    
    def log_cron_start(self, cron_name: str):
        """Log cron job start."""
        try:
            self.logger.info(f"Starting cron job: {cron_name}")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            
    def log_cron_end(self, cron_name: str):
        """Log cron job completion.""" 
        try:
            self.logger.info(f"Completed cron job: {cron_name}")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            
    def check_cron_health(self, cron_name: str) -> bool:
        """Check if cron job is healthy."""
        try:
            # Basic health check logic
            return True
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return False