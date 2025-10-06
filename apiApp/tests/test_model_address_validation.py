from django.test import TestCase
from apiApp.models import StellarAccountSearchCache, PENDING_MAKE_PARENT_LINEAGE
from unittest.mock import patch, MagicMock


class StellarAccountSearchCacheValidationTestCase(TestCase):
    """Test that StellarAccountSearchCache model validates addresses before saving"""
    
    @patch('apiApp.models.connection')
    def test_model_save_rejects_too_short_address(self, mock_connection):
        """Test that addresses < 50 chars are rejected"""
        with self.assertRaises(ValueError) as context:
            cache_entry = StellarAccountSearchCache()
            cache_entry.stellar_account = "G"  # Only 1 char
            cache_entry.network_name = "public"
            cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
            cache_entry.save()
        
        self.assertIn("stellar_account must be at least 50 characters", str(context.exception))
    
    @patch('apiApp.models.connection')
    def test_model_save_rejects_49_char_address(self, mock_connection):
        """Test that 49-char address is rejected"""
        with self.assertRaises(ValueError) as context:
            cache_entry = StellarAccountSearchCache()
            cache_entry.stellar_account = "G" * 49  # 49 chars
            cache_entry.network_name = "public"
            cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
            cache_entry.save()
        
        self.assertIn("stellar_account must be at least 50 characters", str(context.exception))
    
    @patch('apiApp.models.connection')
    def test_model_save_rejects_invalid_network(self, mock_connection):
        """Test that invalid network_name is rejected"""
        with self.assertRaises(ValueError) as context:
            cache_entry = StellarAccountSearchCache()
            cache_entry.stellar_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
            cache_entry.network_name = "invalid"
            cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
            cache_entry.save()
        
        self.assertIn("network_name must be 'public' or 'testnet'", str(context.exception))
    
    @patch('apiApp.models.connection')
    def test_model_save_rejects_testnet_uppercase(self, mock_connection):
        """Test that 'TESTNET' (uppercase) is rejected"""
        with self.assertRaises(ValueError) as context:
            cache_entry = StellarAccountSearchCache()
            cache_entry.stellar_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
            cache_entry.network_name = "TESTNET"  # Wrong case
            cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
            cache_entry.save()
        
        self.assertIn("network_name must be 'public' or 'testnet'", str(context.exception))
    
    @patch('apiApp.models.connection')
    def test_model_save_accepts_valid_public_address(self, mock_connection):
        """Test that valid 56-char address with 'public' network is accepted"""
        mock_connection.return_value = MagicMock()
        
        cache_entry = StellarAccountSearchCache()
        cache_entry.stellar_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        cache_entry.network_name = "public"
        cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
        
        try:
            cache_entry.save()
        except ValueError:
            self.fail("Valid address should not raise ValueError")
    
    @patch('apiApp.models.connection')
    def test_model_save_accepts_valid_testnet_address(self, mock_connection):
        """Test that valid address with 'testnet' network is accepted"""
        mock_connection.return_value = MagicMock()
        
        cache_entry = StellarAccountSearchCache()
        cache_entry.stellar_account = "GCQXVOCLE6OMZS3BNBHEAI4ICEOBQOH35GFKMNNVDBEPP5G3N63JLGWR"
        cache_entry.network_name = "testnet"
        cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
        
        try:
            cache_entry.save()
        except ValueError:
            self.fail("Valid address should not raise ValueError")
    
    @patch('apiApp.models.connection')
    def test_model_save_accepts_50_char_address_minimum(self, mock_connection):
        """Test that 50-char address (minimum) is accepted"""
        mock_connection.return_value = MagicMock()
        
        cache_entry = StellarAccountSearchCache()
        cache_entry.stellar_account = "G" * 50  # Exactly 50 chars
        cache_entry.network_name = "public"
        cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
        
        try:
            cache_entry.save()
        except ValueError:
            self.fail("50-char address should not raise ValueError")
