"""
Test Suite: Validator Security Tests
Tests the enhanced validator with ValidationError enforcement.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers


class ValidatorSecurityTestCase(TestCase):
    """Test security features of the enhanced validator."""
    
    def test_valid_stellar_address(self):
        """Test that valid Stellar addresses pass validation."""
        valid_address = "GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A"
        
        # Should return True without exception
        result = StellarMapValidatorHelpers.validate_stellar_account_address(valid_address)
        self.assertTrue(result)
        
        # Should also pass with raise_exception=True
        result = StellarMapValidatorHelpers.validate_stellar_account_address(valid_address, raise_exception=True)
        self.assertTrue(result)
    
    def test_empty_address_raises_validation_error(self):
        """Test that empty address raises ValidationError."""
        with self.assertRaises(ValidationError) as context:
            StellarMapValidatorHelpers.validate_stellar_account_address("", raise_exception=True)
        self.assertIn("non-empty string", str(context.exception))
    
    def test_none_address_raises_validation_error(self):
        """Test that None address raises ValidationError."""
        with self.assertRaises(ValidationError) as context:
            StellarMapValidatorHelpers.validate_stellar_account_address(None, raise_exception=True)
        self.assertIn("non-empty string", str(context.exception))
    
    def test_wrong_length_raises_validation_error(self):
        """Test that wrong length raises ValidationError."""
        # Too short
        with self.assertRaises(ValidationError) as context:
            StellarMapValidatorHelpers.validate_stellar_account_address("GABC", raise_exception=True)
        self.assertIn("exactly 56 characters", str(context.exception))
        
        # Too long
        with self.assertRaises(ValidationError) as context:
            StellarMapValidatorHelpers.validate_stellar_account_address("G" + "A" * 100, raise_exception=True)
        self.assertIn("exactly 56 characters", str(context.exception))
    
    def test_wrong_prefix_raises_validation_error(self):
        """Test that wrong prefix raises ValidationError."""
        # Starts with X instead of G
        with self.assertRaises(ValidationError) as context:
            StellarMapValidatorHelpers.validate_stellar_account_address("XAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A", raise_exception=True)
        self.assertIn("must start with 'G'", str(context.exception))
    
    def test_shell_injection_raises_validation_error(self):
        """Test that shell injection characters raise ValidationError."""
        dangerous_chars = [';', '|', '&', '`', '$', '(', ')']
        
        for char in dangerous_chars:
            # Insert dangerous char in the middle, not at the end
            malicious_address = f"GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP{char}2RBW3K6BTODB"
            # Ensure it's still 56 chars (pad if needed)
            malicious_address = malicious_address[:56].ljust(56, 'A')
            
            with self.assertRaises(ValidationError) as context:
                StellarMapValidatorHelpers.validate_stellar_account_address(malicious_address, raise_exception=True)
            self.assertIn("invalid character", str(context.exception))
    
    def test_path_traversal_raises_validation_error(self):
        """Test that path traversal patterns raise ValidationError."""
        path_traversal_patterns = ['../', '..\\', '%2e%2e%2f', '%2e%2e%5c']
        
        for pattern in path_traversal_patterns:
            # Insert pattern in middle and ensure proper length
            malicious_address = f"GAHK{pattern}7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DPAAAA"
            malicious_address = malicious_address[:56].ljust(56, 'A')
            
            with self.assertRaises(ValidationError) as context:
                StellarMapValidatorHelpers.validate_stellar_account_address(malicious_address, raise_exception=True)
            # Should fail either due to path traversal or invalid characters
            error_msg = str(context.exception).lower()
            self.assertTrue("path traversal" in error_msg or "invalid character" in error_msg)
    
    def test_invalid_characters_raise_validation_error(self):
        """Test that invalid Base32 characters raise ValidationError."""
        # Stellar uses Base32: A-Z and 2-7, but not 0, 1, 8, 9
        invalid_chars_addresses = [
            "G0HK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A",  # Contains 0
            "G1HK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A",  # Contains 1
            "G8HK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A",  # Contains 8
            "G9HK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A",  # Contains 9
        ]
        
        for address in invalid_chars_addresses:
            with self.assertRaises(ValidationError) as context:
                StellarMapValidatorHelpers.validate_stellar_account_address(address, raise_exception=True)
            # Could fail either at character validation or checksum validation
            self.assertTrue(
                "invalid characters" in str(context.exception).lower() or 
                "checksum" in str(context.exception).lower()
            )
    
    def test_null_byte_injection_raises_validation_error(self):
        """Test that null byte injection raises ValidationError."""
        null_byte_payloads = [
            "GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A\x00",
            "\x00GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A",
            "GAHK7EEG2WWHVKDNT4\x00CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A",
        ]
        
        for payload in null_byte_payloads:
            with self.assertRaises(ValidationError):
                StellarMapValidatorHelpers.validate_stellar_account_address(payload, raise_exception=True)
    
    def test_invalid_checksum_raises_validation_error(self):
        """Test that invalid checksum raises ValidationError."""
        # Valid format but invalid checksum
        invalid_checksum = "GABC4DCOBIAW2LJBK3GZYOVAWL2FKXJ6DRRUF2WFHLPHYZDF4ZMZX3OA"
        
        with self.assertRaises(ValidationError) as context:
            StellarMapValidatorHelpers.validate_stellar_account_address(invalid_checksum, raise_exception=True)
        self.assertIn("checksum", str(context.exception).lower())
    
    def test_backwards_compatible_mode_returns_false(self):
        """Test that without raise_exception, validator returns False for invalid input."""
        # Empty string
        result = StellarMapValidatorHelpers.validate_stellar_account_address("")
        self.assertFalse(result)
        
        # Shell injection
        result = StellarMapValidatorHelpers.validate_stellar_account_address("GAHK; rm -rf /")
        self.assertFalse(result)
        
        # Path traversal
        result = StellarMapValidatorHelpers.validate_stellar_account_address("G../etc/passwd")
        self.assertFalse(result)
        
        # Wrong length
        result = StellarMapValidatorHelpers.validate_stellar_account_address("GABC")
        self.assertFalse(result)


class ValidatorXSSPreventionTestCase(TestCase):
    """Test XSS prevention in validator."""
    
    def test_script_tags_rejected(self):
        """Test that addresses containing script tags are rejected."""
        xss_payloads = [
            "<script>alert('XSS')</script>GAHK7EEG2WWHVKDNT4CEQFZ",
            "GAHK<script>alert(1)</script>7EEG2WWHVKDNT4CEQFZGKF2L",
        ]
        
        for payload in xss_payloads:
            # Should fail validation (wrong length or invalid characters)
            result = StellarMapValidatorHelpers.validate_stellar_account_address(payload)
            self.assertFalse(result)
            
            with self.assertRaises(ValidationError):
                StellarMapValidatorHelpers.validate_stellar_account_address(payload, raise_exception=True)
    
    def test_html_entities_rejected(self):
        """Test that HTML entities in addresses are rejected."""
        html_payloads = [
            "&lt;script&gt;alert('XSS')&lt;/script&gt;GAHK7EEG2WWHV",
            "GAHK&nbsp;7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K",
        ]
        
        for payload in html_payloads:
            result = StellarMapValidatorHelpers.validate_stellar_account_address(payload)
            self.assertFalse(result)
    
    def test_javascript_protocol_rejected(self):
        """Test that javascript: protocol is rejected."""
        js_payloads = [
            "javascript:alert(1)GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW",
            "Gjavascript:alert(1)AHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW",
        ]
        
        for payload in js_payloads:
            result = StellarMapValidatorHelpers.validate_stellar_account_address(payload)
            self.assertFalse(result)


class ValidatorCommandInjectionPreventionTestCase(TestCase):
    """Test command injection prevention in validator."""
    
    def test_shell_metacharacters_blocked(self):
        """Test that shell metacharacters are blocked."""
        shell_chars = [';', '|', '&', '`', '$', '(', ')', '\n', '\r']
        
        for char in shell_chars:
            malicious_input = f"GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP{char}2RBW3K6BTO"
            
            # Should return False in backwards compatible mode
            result = StellarMapValidatorHelpers.validate_stellar_account_address(malicious_input)
            self.assertFalse(result, f"Shell char {repr(char)} should be rejected")
            
            # Should raise ValidationError in strict mode
            with self.assertRaises(ValidationError):
                StellarMapValidatorHelpers.validate_stellar_account_address(malicious_input, raise_exception=True)
    
    def test_command_substitution_blocked(self):
        """Test that command substitution attempts are blocked."""
        command_injection_attempts = [
            "GAHK$(whoami)7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RB",
            "GAHK`whoami`7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW",
        ]
        
        for attempt in command_injection_attempts:
            with self.assertRaises(ValidationError):
                StellarMapValidatorHelpers.validate_stellar_account_address(attempt, raise_exception=True)
