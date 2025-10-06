from django.test import TestCase
from unittest.mock import patch, MagicMock
from apiApp.helpers.sm_cache import StellarMapCacheHelpers


class CacheHelperAddressValidationTestCase(TestCase):
    """Test that cache helper methods validate addresses before processing"""
    
    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache')
    @patch('apiApp.helpers.sm_cache.StellarMapValidatorHelpers')
    def test_check_cache_freshness_validates_address(self, mock_validator, mock_cache):
        """Test that check_cache_freshness validates address format"""
        mock_validator.return_value.validate_stellar_account_address.return_value = False
        
        helper = StellarMapCacheHelpers()
        
        is_fresh, cache_entry = helper.check_cache_freshness("invalid", "public")
        
        self.assertFalse(is_fresh)
        self.assertIsNone(cache_entry)
    
    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache')
    @patch('apiApp.helpers.sm_cache.StellarMapValidatorHelpers')
    def test_create_pending_entry_validates_address(self, mock_validator, mock_cache):
        """Test that create_pending_entry validates address before creating"""
        mock_validator.return_value.validate_stellar_account_address.return_value = False
        
        helper = StellarMapCacheHelpers()
        
        with self.assertRaises(ValueError) as context:
            helper.create_pending_entry("G", "public")
        
        self.assertIn("Invalid Stellar address", str(context.exception))
    
    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache')
    @patch('apiApp.helpers.sm_cache.StellarMapValidatorHelpers')
    def test_create_pending_entry_validates_network(self, mock_validator, mock_cache):
        """Test that create_pending_entry validates network_name"""
        mock_validator.return_value.validate_stellar_account_address.return_value = True
        
        helper = StellarMapCacheHelpers()
        
        with self.assertRaises(ValueError) as context:
            helper.create_pending_entry("GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB", "invalid")
        
        self.assertIn("Invalid network", str(context.exception))
    
    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache')
    @patch('apiApp.helpers.sm_cache.StellarMapValidatorHelpers')
    def test_helper_accepts_valid_address_and_network(self, mock_validator, mock_cache):
        """Test that valid address and network are accepted"""
        mock_validator.return_value.validate_stellar_account_address.return_value = True
        mock_cache.objects.filter.return_value.first.return_value = None
        mock_cache.return_value.save.return_value = None
        
        helper = StellarMapCacheHelpers()
        
        try:
            result = helper.create_pending_entry("GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB", "public")
        except ValueError:
            self.fail("Valid address and network should not raise ValueError")
