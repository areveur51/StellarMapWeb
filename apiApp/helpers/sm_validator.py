# sm_validator.py - Enhanced secure validation.
import re
from stellar_sdk import Keypair


class StellarMapValidatorHelpers:

    @staticmethod
    def validate_stellar_account_address(address):
        """Validate Stellar address: regex + crypto check."""
        pattern = re.compile(r'^G[A-Za-z0-9]{55}$')
        if not pattern.match(address):
            return False
        try:
            Keypair.from_public_key(address)  # Secure crypto validation
            return True
        except Exception:
            return False
