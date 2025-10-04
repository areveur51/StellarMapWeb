from django.test import TestCase
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers


class StellarMapValidatorHelpersTestCase(TestCase):
    
    def test_validate_stellar_account_address_valid(self):
        valid_address = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(valid_address)
        self.assertTrue(result)
    
    def test_validate_stellar_account_address_invalid_length(self):
        invalid_address = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZT"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_prefix(self):
        invalid_address = "AALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_invalid_characters(self):
        invalid_address = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZ!@"
        result = StellarMapValidatorHelpers.validate_stellar_account_address(invalid_address)
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_empty_string(self):
        result = StellarMapValidatorHelpers.validate_stellar_account_address("")
        self.assertFalse(result)
    
    def test_validate_stellar_account_address_none(self):
        with self.assertRaises(TypeError):
            StellarMapValidatorHelpers.validate_stellar_account_address(None)
