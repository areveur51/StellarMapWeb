from decouple import config  # For secure env var loading


class StellarNetwork:
    """
    Class for managing Stellar network settings.

    Initializes EnvHelpers based on network type.
    """

    def __init__(self, network: str):
        """
        Set network; raise error on invalid.

        Args:
            network (str): 'testnet' or 'public'.

        Raises:
            ValueError: On invalid network.
        """
        self.env_helpers = EnvHelpers()
        if network == 'testnet':
            self.env_helpers.set_testnet_network()
        elif network == 'public':
            self.env_helpers.set_public_network()
        else:
            raise ValueError(f"Invalid network: {network}")


class EnvHelpers:
    """
    Manages environment variables for Stellar networks.

    Loads from env vars for security; defaults to testnet.
    """

    def __init__(self):
        """Initialize with testnet defaults; override via env vars."""
        self.debug = config('DEBUG', default='True')
        self.network = config('NETWORK', default='testnet')
        self.base_horizon = config(
            'BASE_HORIZON', default='https://horizon-testnet.stellar.org')
        self.base_site = config('BASE_SITE', default='https://stellar.expert')
        self.base_se = config('BASE_SE', default='https://api.stellar.expert')
        self._set_base_network()

    def set_testnet_network(self):
        """Set testnet env."""
        self.debug = 'True'
        self.network = 'testnet'
        self.base_horizon = 'https://horizon-testnet.stellar.org'
        self._set_base_network()

    def set_public_network(self):
        """Set public env."""
        self.debug = 'False'
        self.network = 'public'
        self.base_horizon = 'https://horizon.stellar.org'
        self._set_base_network()

    def _set_base_network(self):
        """Internal: Set derived URLs."""
        self.base_site_network = f"{self.base_site}/explorer/{self.network}"
        self.base_site_network_account = f"{self.base_site_network}/account/"
        self.base_se_blocked_domains = f"{self.base_se}/explorer/directory/blocked-domains/"
        self.base_se_network = f"{self.base_se}/explorer/{self.network}"
        self.base_se_network_account = f"{self.base_se_network}/account/"
        self.base_se_network_dir = f"{self.base_se_network}/directory/"
        self.base_horizon_account = f"{self.base_horizon}/accounts/"
        self.base_horizon_operations = f"{self.base_horizon}/operations/"
        self.base_horizon_effects = f"{self.base_horizon}/effects/"

    # Getters remain the same for compatibility
