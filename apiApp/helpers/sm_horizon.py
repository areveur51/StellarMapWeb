import json
import sentry_sdk
from tenacity import retry, stop_after_attempt, wait_random_exponential
from stellar_sdk import Server
from stellar_sdk.exceptions import BaseRequestError  # For specific handling
from apiApp.helpers.sm_datetime import StellarMapDateTimeHelpers
from apiApp.helpers.sm_utils import StellarMapUtilityHelpers
from apiApp.services import AstraDocument

class RetryMixin:  # Reused from above
    """Base mixin for retry functionality."""
    
    @staticmethod
    def retry_decorator(func):
        """Basic retry decorator."""
        @retry(wait=wait_random_exponential(multiplier=1, max=5), stop=stop_after_attempt(3))
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper

class StellarMapHorizonAPIHelpers(RetryMixin):
    """
    Helper class for interacting with Horizon API.

    Provides secure, retried methods for account info, operations, effects.
    """
    def __init__(self, horizon_url: str, account_id: str):
        """
        Initialize with Horizon URL and account ID.

        Args:
            horizon_url (str): Horizon API base URL.
            account_id (str): Stellar account ID (validated externally).
        """
        super().__init__()
        self.server = Server(horizon_url=horizon_url)
        self.account_id = account_id
        self.cron_name = None
    
    def set_cron_name(self, cron_name: str):
        """Set cron name for error reporting."""
        self.cron_name = cron_name

    @RetryMixin.retry_decorator
    def get_base_accounts(self) -> dict:
        """
        Fetch base account info.

        Returns:
            dict: Account JSON.

        Raises:
            BaseRequestError: On API failure (retried).
        """
        try:
            return self.server.accounts().account_id(self.account_id).call()
        except BaseRequestError as e:
            sentry_sdk.capture_exception(e)
            raise

    @RetryMixin.retry_decorator
    def get_account_operations(self) -> dict:
        """Fetch account operations."""
        try:
            return self.server.operations().for_account(self.account_id).call()
        except BaseRequestError as e:
            sentry_sdk.capture_exception(e)
            raise
    
    @RetryMixin.retry_decorator
    def get_account_effects(self) -> dict:
        """Fetch account effects."""
        try:
            return self.server.effects().for_account(self.account_id).call()
        except BaseRequestError as e:
            sentry_sdk.capture_exception(e)
            raise

class StellarMapHorizonAPIParserHelpers:
    """
    Parser for Horizon JSON responses.

    Extracts balances, domains, creators, assets, flags safely.
    """
    def __init__(self, datastax_response: dict):
        """
        Initialize with Datastax response dict.

        Args:
            datastax_response (dict): Fetched JSON.
        """
        self.datastax_response = datastax_response

    def parse_account_native_balance(self) -> float:
        """Extract native (XLM) balance safely."""
        try:
            for balance in self.datastax_response.get('data', {}).get('raw_data', {}).get('balances', []):
                if balance.get('asset_type') == 'native':
                    return float(balance.get('balance', 0.0))
            return 0.0
        except (KeyError, ValueError) as e:
            sentry_sdk.capture_exception(e)
            return 0.0

    # Similar safe parsing for other methods: parse_account_home_domain, parse_operations_creator_account, parse_account_assets, parse_account_flags
    # Example for parse_operations_creator_account:
    def parse_operations_creator_account(self, stellar_account: str) -> dict:
        try:
            records = self.datastax_response.get('data', {}).get('raw_data', {}).get('_embedded', {}).get('records', [])
            for record in records:
                if record.get('type') == 'create_account' and record.get('account') == stellar_account:
                    dt_helpers = StellarMapDateTimeHelpers()
                    created_at_obj = dt_helpers.convert_horizon_datetime_str_to_obj(record.get('created_at', ''))
                    return {'funder': record.get('funder', ''), 'created_at': created_at_obj}
            return {}
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return {}