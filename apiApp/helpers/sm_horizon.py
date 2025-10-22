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
    def get_account_operations(self, order='asc', limit=200) -> dict:
        """Fetch account operations.
        
        Args:
            order: 'asc' for oldest first (to get creation), 'desc' for newest first
            limit: Number of operations to fetch (default 200)
        """
        try:
            query = self.server.operations().for_account(self.account_id)
            if order == 'asc':
                query = query.order(desc=False)
            else:
                query = query.order(desc=True)
            query = query.limit(limit)
            return query.call()
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
    
    @RetryMixin.retry_decorator
    def get_child_accounts(self, max_pages=5) -> list:
        """
        Fetch accounts created by this account (child accounts).
        
        Queries operations for this account in ascending order (oldest first) 
        and filters for create_account operations where this account was the funder.
        Paginates through multiple pages to find all child accounts.
        
        Args:
            max_pages: Maximum number of pages to fetch (default 5, 200 ops per page = 1000 total)
        
        Returns:
            list: List of child account addresses created by this account
        """
        try:
            child_accounts = []
            cursor = None
            pages_fetched = 0
            
            # Fetch operations in ascending order (oldest first)
            # This ensures create_account operations (usually early) are found
            while pages_fetched < max_pages:
                query = self.server.operations().for_account(self.account_id).order(desc=False).limit(200)
                
                if cursor:
                    query = query.cursor(cursor)
                
                ops_response = query.call()
                records = ops_response.get('_embedded', {}).get('records', [])
                
                if not records:
                    break
                
                # Filter for create_account operations
                for op in records:
                    if op.get('type') == 'create_account':
                        created_account = op.get('account')
                        
                        if created_account:
                            child_accounts.append({
                                'account': created_account,
                                'starting_balance': op.get('starting_balance', '0'),
                                'created_at': op.get('created_at', '')
                            })
                
                # Get cursor for next page
                cursor = records[-1].get('paging_token') if records else None
                pages_fetched += 1
                
                # If we got less than 200 records, we've reached the end
                if len(records) < 200:
                    break
            
            return child_accounts
            
        except BaseRequestError as e:
            sentry_sdk.capture_exception(e)
            return []  # Return empty list on error rather than raising

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
            # Check if response is nested DataStax format or direct Horizon format
            balances = self.datastax_response.get('balances', [])
            if not balances:
                # Try nested format for backward compatibility
                balances = self.datastax_response.get('data', {}).get('raw_data', {}).get('balances', [])
            
            for balance in balances:
                if balance.get('asset_type') == 'native':
                    return float(balance.get('balance', 0.0))
            return 0.0
        except (KeyError, ValueError) as e:
            sentry_sdk.capture_exception(e)
            return 0.0

    def parse_account_home_domain(self) -> str:
        """Extract home domain safely."""
        try:
            # Check if response is direct Horizon format (top-level home_domain)
            home_domain = self.datastax_response.get('home_domain', '')
            if not home_domain:
                # Try nested DataStax format for backward compatibility
                home_domain = self.datastax_response.get('data', {}).get('raw_data', {}).get('home_domain', '')
            return home_domain
        except (KeyError, AttributeError) as e:
            sentry_sdk.capture_exception(e)
            return ''

    def parse_operations_creator_account(self, stellar_account: str) -> dict:
        try:
            records = self.datastax_response.get('data', {}).get('raw_data', {}).get('_embedded', {}).get('records', [])
            
            # Only return creator if we find a create_account operation
            # Do NOT fallback to first operation's source_account - let Stellar Expert handle that
            for record in records:
                if record.get('type') == 'create_account' and record.get('account') == stellar_account:
                    dt_helpers = StellarMapDateTimeHelpers()
                    created_at_obj = dt_helpers.convert_horizon_datetime_str_to_obj(record.get('created_at', ''))
                    return {'funder': record.get('funder', ''), 'created_at': created_at_obj}
            
            # No create_account operation found - return empty to trigger Stellar Expert fallback
            return {}
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return {}