import json
import requests
import sentry_sdk
from tenacity import retry, stop_after_attempt, wait_random_exponential
from stellar_sdk import Keypair  # For secure address validation
from apiApp.helpers.env import EnvHelpers
from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers  # Kept inheritance if needed
from apiApp.helpers.sm_utils import StellarMapUtilityHelpers


class RetryMixin:
    """Mixin for common retry logic to avoid duplication."""

    def __init__(self):
        self.cron_name = None  # Set via set_cron_name if needed

    def set_cron_name(self, cron_name: str):
        """Set cron name for error reporting."""
        self.cron_name = cron_name

    def on_retry_failure(self, retry_state):
        """Callback for retry failures: Log to Sentry and mark cron unhealthy."""
        sentry_sdk.capture_exception(retry_state.outcome.exception())
        sm_util = StellarMapUtilityHelpers()
        sm_util.on_retry_failure(retry_state, self.cron_name)

    retry_decorator = retry(wait=wait_random_exponential(multiplier=1, max=71),
                            stop=stop_after_attempt(7),
                            retry_error_callback=on_retry_failure)


class StellarMapStellarExpertAPIHelpers(RetryMixin,
                                        StellarMapHorizonAPIHelpers):
    """
    Helper class for interacting with Stellar Expert API.

    Provides secure, retried methods for fetching asset data, ratings, etc.
    Inherits RetryMixin for efficient retry handling.

    Note: All requests use timeouts and headers for security. Validate addresses before use.
    """

    def __init__(self, stellar_account=None, network_name=None, lin_queryset=None):
        """
        Initialize with stellar account and network or lineage queryset.

        Args:
            stellar_account (str, optional): Stellar account address.
            network_name (str, optional): Network name ('public' or 'testnet').
            lin_queryset (optional): Lineage record object (legacy support).
        """
        super().__init__()
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "StellarMap/1.0"  # Secure identification
        }
        self.env_helpers = EnvHelpers()
        
        if lin_queryset:
            self.lin_queryset = lin_queryset
            self.stellar_account = lin_queryset.stellar_account
            network_name = lin_queryset.network_name
        else:
            self.stellar_account = stellar_account
            self.lin_queryset = None
        
        if network_name == 'public':
            self.env_helpers.set_public_network()
        else:
            self.env_helpers.set_testnet_network()

    @RetryMixin.retry_decorator
    def get_account(self):
        """
        Fetch account information from Stellar Expert API.

        Returns:
            dict: JSON response with account details including creator.

        Raises:
            Exception: On API failure (retried 7x).

        Example URI: https://api.stellar.expert/explorer/public/account/GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB
        """
        try:
            url = f"{self.env_helpers.get_base_se_network()}/account/{self.stellar_account}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            sentry_sdk.capture_exception(e)
            raise Exception(f"Failed to GET SE account: {e}")

    @RetryMixin.retry_decorator
    def get_se_asset_list(self):
        """
        Fetch asset list for the account from Stellar Expert API.

        Returns:
            dict: JSON response of asset list.

        Raises:
            Exception: On API failure (retried 7x).

        Example URI: https://api.stellar.expert/explorer/public/asset?search=GDZZEJPAY2M4BU5EZ3H2V3HPNYHQUQLUUHKR4OQAM2RM453FRDZUOZJF
        """
        try:
            account = self.stellar_account if self.stellar_account else self.lin_queryset.stellar_account
            url = f"{self.env_helpers.get_base_se_network()}/asset?search={account}"
            response = requests.get(url, headers=self.headers,
                                    timeout=10)  # Secure timeout
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            sentry_sdk.capture_exception(e)
            raise Exception(f"Failed to GET SE asset list: {e}")

    # Similar refactoring for get_se_asset_rating, get_se_blocked_domain, get_se_account_directory
    # Example for get_se_asset_rating:
    @RetryMixin.retry_decorator
    def get_se_asset_rating(self, asset_code: str, asset_type: str):
        """
        Fetch asset rating.

        Args:
            asset_code (str): Asset code.
            asset_type (str): Asset type.

        Returns:
            dict: JSON response.
        """
        try:
            account = self.stellar_account if self.stellar_account else self.lin_queryset.stellar_account
            url = f"{self.env_helpers.get_base_se_network()}/asset/{asset_code}-{account}/rating"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            sentry_sdk.capture_exception(e)
            raise Exception(f"Failed to GET SE asset rating: {e}")

    # ... (apply to other methods)


class StellarMapStellarExpertAPIParserHelpers:
    """
    Parser for Stellar Expert JSON responses embedded in custom formats.

    Extracts asset code, issuer, type safely.
    """

    def __init__(self, datastax_response_or_queryset):
        """
        Initialize with datastax response dict or lineage queryset.
        
        Args:
            datastax_response_or_queryset: Either a dict with {'data': {'raw_data': {...}}} 
                                           or a lineage queryset object.
        """
        if isinstance(datastax_response_or_queryset, dict):
            self.datastax_response = datastax_response_or_queryset
            self.lin_queryset = None
        else:
            self.datastax_response = None
            self.lin_queryset = datastax_response_or_queryset

    def parse_account_creator(self) -> str:
        """
        Extract account creator from Stellar Expert response.
        
        Returns:
            str: Creator account address.
        """
        try:
            if self.datastax_response:
                raw_data = self.datastax_response.get('data', {}).get('raw_data', {})
                return raw_data.get('creator', '')
            return ''
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return ''
    
    def parse_account_created_at(self):
        """
        Extract account creation timestamp from Stellar Expert response.
        
        Returns:
            datetime or None: Created datetime object.
        """
        try:
            if self.datastax_response:
                raw_data = self.datastax_response.get('data', {}).get('raw_data', {})
                created_timestamp = raw_data.get('created')
                if created_timestamp:
                    from datetime import datetime
                    return datetime.fromtimestamp(created_timestamp)
            return None
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return None
    
    def parse_account_assets(self):
        """
        Extract asset holdings from Stellar Expert response.
        
        Returns:
            list: List of asset dictionaries with code, issuer, and balance.
        """
        try:
            if self.datastax_response:
                raw_data = self.datastax_response.get('data', {}).get('raw_data', {})
                balances = raw_data.get('balances', [])
                
                assets = []
                for balance in balances:
                    # Skip native XLM balance
                    if balance.get('asset_type') == 'native':
                        continue
                    
                    assets.append({
                        'asset_code': balance.get('asset_code', ''),
                        'asset_issuer': balance.get('asset_issuer', ''),
                        'asset_type': balance.get('asset_type', ''),
                        'balance': balance.get('balance', '0')
                    })
                
                return assets
            return []
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return []

    def parse_asset_code_issuer_type(self) -> dict:
        """
        Parse asset details from stored JSON.

        Returns:
            dict: {'asset_code': str, 'asset_issuer': str, 'asset_type': str}

        Raises:
            ValueError: If JSON invalid.
        """
        try:
            if not self.lin_queryset:
                return {}
            parsed_data = json.loads(
                self.lin_queryset.horizon_accounts_assets_doc_api_href)
            for item in parsed_data:
                if item.get("asset_issuer"
                            ) == self.lin_queryset.stellar_account:  # Safe get
                    return {
                        'asset_code': item.get("asset_code", ""),
                        "asset_issuer": item.get("asset_issuer", ""),
                        "asset_type": item.get("asset_type", "")
                    }
            return {}  # Empty if not found
        except json.JSONDecodeError as e:
            sentry_sdk.capture_exception(e)
            raise ValueError("Invalid JSON in assets doc")
