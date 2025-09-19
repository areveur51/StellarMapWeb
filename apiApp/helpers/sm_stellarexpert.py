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

    def __init__(self, lin_queryset):
        """
        Initialize with lineage queryset and set network env.

        Args:
            lin_queryset: Lineage record object.
        """
        super().__init__()
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "StellarMap/1.0"  # Secure identification
        }
        self.lin_queryset = lin_queryset
        self.env_helpers = EnvHelpers()
        network_name = lin_queryset.network_name
        if network_name == 'public':
            self.env_helpers.set_public_network()
        else:
            self.env_helpers.set_testnet_network()

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
            url = f"{self.env_helpers.get_base_se_network()}/asset?search={self.lin_queryset.stellar_account}"
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
            url = f"{self.env_helpers.get_base_se_network()}/asset/{asset_code}-{self.lin_queryset.stellar_account}/rating"
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

    def __init__(self, lin_queryset):
        self.lin_queryset = lin_queryset

    def parse_asset_code_issuer_type(self) -> dict:
        """
        Parse asset details from stored JSON.

        Returns:
            dict: {'asset_code': str, 'asset_issuer': str, 'asset_type': str}

        Raises:
            ValueError: If JSON invalid.
        """
        try:
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
