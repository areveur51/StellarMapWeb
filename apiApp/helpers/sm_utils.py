import re
import sentry_sdk
from apiApp.helpers.sm_cron import StellarMapCronHelpers  # Assume exists


class StellarMapParsingUtilityHelpers:
    """
    Utility for parsing strings (e.g., UUID from URLs).
    """

    @staticmethod
    def get_documentid_from_url_address(url_address: str) -> str:
        """
        Extract UUID from URL using secure regex.

        Args:
            url_address (str): URL containing UUID.

        Returns:
            str: Extracted UUID or empty if not found.
        """
        pattern = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
        match = re.search(pattern, url_address)
        return match.group(0) if match else ''


class StellarMapUtilityHelpers:
    """
    General utilities, e.g., retry failure handling.
    """

    def on_retry_failure(self, retry_state, cron_name: str):
        """
        Handle retry failures: Log and mark cron unhealthy.

        Args:
            retry_state: Tenacity retry state.
            cron_name (str): Cron job name.
        """
        sentry_sdk.capture_exception(retry_state.outcome.exception())
        cron_helpers = StellarMapCronHelpers(cron_name=cron_name)
        cron_helpers.set_crons_unhealthy()
