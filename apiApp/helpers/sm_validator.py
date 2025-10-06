# sm_validator.py - Enhanced secure validation.
import re
from stellar_sdk import Keypair
from django.core.exceptions import ValidationError


class StellarMapValidatorHelpers:

    @staticmethod
    def validate_stellar_account_address(address, raise_exception=False):
        """
        Validate Stellar address: regex + crypto check.
        
        Args:
            address: Stellar address to validate
            raise_exception: If True, raises ValidationError on invalid input.
                           If False, returns True/False (backwards compatible)
        
        Returns:
            bool: True if valid, False if invalid (when raise_exception=False)
        
        Raises:
            ValidationError: When address is invalid and raise_exception=True
        """
        # Check for None or empty
        if not address or not isinstance(address, str):
            if raise_exception:
                raise ValidationError("Stellar address must be a non-empty string")
            return False
        
        # Check length (56 characters)
        if len(address) != 56:
            if raise_exception:
                raise ValidationError(f"Stellar address must be exactly 56 characters, got {len(address)}")
            return False
        
        # Check prefix (must start with G)
        if not address.startswith('G'):
            if raise_exception:
                raise ValidationError("Stellar address must start with 'G'")
            return False
        
        # Check for shell/command injection characters
        dangerous_chars = [';', '|', '&', '`', '$', '(', ')', '\n', '\r', '\0']
        for char in dangerous_chars:
            if char in address:
                if raise_exception:
                    raise ValidationError(f"Stellar address contains invalid character: {repr(char)}")
                return False
        
        # Check for path traversal patterns
        path_traversal_patterns = ['../', '..\\', '%2e%2e%2f', '%2e%2e%5c']
        for pattern in path_traversal_patterns:
            if pattern.lower() in address.lower():
                if raise_exception:
                    raise ValidationError(f"Stellar address contains path traversal pattern: {pattern}")
                return False
        
        # Base32 character whitelist (Stellar uses uppercase A-Z and 2-7)
        # We allow lowercase for flexibility, but validate the pattern
        pattern = re.compile(r'^G[A-Z2-7]{55}$', re.IGNORECASE)
        if not pattern.match(address):
            if raise_exception:
                raise ValidationError("Stellar address contains invalid characters (must be A-Z, 2-7)")
            return False
        
        # Cryptographic validation using Stellar SDK
        try:
            Keypair.from_public_key(address)
            return True
        except Exception as e:
            if raise_exception:
                raise ValidationError(f"Invalid Stellar address checksum: {str(e)}")
            return False
