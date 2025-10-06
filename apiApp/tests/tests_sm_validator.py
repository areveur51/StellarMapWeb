from django.test import TestCase
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers


class StellarMapValidatorHelpersTestCase(TestCase):
    
    def test_validate_stellar_account_address_valid(self):
        """Test valid 56-character Stellar address starting with G"""
        valid_address = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(valid_address)
        self.assertTrue(result)
    
    def test_validate_stellar_account_address_valid_alternative(self):
        """Test another valid Stellar address"""
        valid_address = "GCQXVOCLE6OMZS3BNBHEAI4ICEOBQOH35GFKMNNVDBEPP5G3N63JLGWR"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(valid_address)
        self.assertTrue(result)
    
    def test_validate_stellar_account_address_invalid_length_too_short(self):
        """Test 55-character address (too short)"""
        invalid_address = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZT"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_length_too_long(self):
        """Test 57-character address (too long)"""
        invalid_address = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTBA"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_length_way_too_short(self):
        """Test very short address (single character)"""
        invalid_address = "G"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_prefix_lowercase(self):
        """Test lowercase 'g' prefix (should fail)"""
        invalid_address = "gALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_prefix_A(self):
        """Test address starting with 'A' instead of 'G'"""
        invalid_address = "AALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_prefix_F(self):
        """Test address starting with 'F' instead of 'G'"""
        invalid_address = "FALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_characters_special(self):
        """Test address with special characters"""
        invalid_address = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZ!@"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_characters_space(self):
        """Test address with embedded space"""
        invalid_address = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQ YLDMZTB"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_leading_whitespace(self):
        """Test valid address with leading whitespace"""
        invalid_address = " GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_trailing_whitespace(self):
        """Test valid address with trailing whitespace"""
        invalid_address = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB "
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_unicode(self):
        """Test address with Unicode characters"""
        invalid_address = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZ™"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_empty_string(self):
        """Test empty string"""
        result = StellarMapValidatorHelpers.validate_stellar_account_address("")
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_whitespace_only(self):
        """Test whitespace-only string"""
        result = StellarMapValidatorHelpers.validate_stellar_account_address("    ")
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_none(self):
        """Test None value raises TypeError"""
        with self.assertRaises(TypeError):
            StellarMapValidatorHelpers.validate_stellar_account_address(None)
    
    def test_validate_stellar_account_address_mixed_case(self):
        """Test mixed case address (should fail crypto check)"""
        invalid_address = "GaLPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_numeric_only(self):
        """Test address with only numbers (invalid)"""
        invalid_address = "G" + "1" * 55
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
