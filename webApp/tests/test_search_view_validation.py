from django.test import TestCase, Client
from unittest.mock import patch, MagicMock


class SearchViewAddressValidationTestCase(TestCase):
    """Test that invalid Stellar addresses are rejected at the view layer"""
    
    def setUp(self):
        self.client = Client()
    
    def test_search_view_rejects_empty_address(self):
        """Test that empty address shows error"""
        response = self.client.get('/search/', {'account': '', 'network': 'public'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('INVALID_ADDRESS', str(response.content))
    
    def test_search_view_rejects_short_address(self):
        """Test that short address (single char) shows error"""
        response = self.client.get('/search/', {'account': 'G', 'network': 'public'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('INVALID_ADDRESS', str(response.content))
    
    def test_search_view_rejects_55_char_address(self):
        """Test that 55-char address shows error"""
        response = self.client.get('/search/', {'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZT', 'network': 'public'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('INVALID_ADDRESS', str(response.content))
    
    def test_search_view_rejects_57_char_address(self):
        """Test that 57-char address shows error"""
        response = self.client.get('/search/', {'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTBA', 'network': 'public'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('INVALID_ADDRESS', str(response.content))
    
    def test_search_view_rejects_lowercase_prefix(self):
        """Test that lowercase 'g' prefix shows error"""
        response = self.client.get('/search/', {'account': 'gALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB', 'network': 'public'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('INVALID_ADDRESS', str(response.content))
    
    def test_search_view_rejects_wrong_prefix(self):
        """Test that address starting with 'A' shows error"""
        response = self.client.get('/search/', {'account': 'AALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB', 'network': 'public'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('INVALID_ADDRESS', str(response.content))
    
    def test_search_view_rejects_special_characters(self):
        """Test that address with special characters shows error"""
        response = self.client.get('/search/', {'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZ!@', 'network': 'public'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('INVALID_ADDRESS', str(response.content))
    
    def test_search_view_rejects_whitespace_embedded(self):
        """Test that address with embedded space shows error"""
        response = self.client.get('/search/', {'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQ YLDMZTB', 'network': 'public'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('INVALID_ADDRESS', str(response.content))
    
    def test_search_view_rejects_invalid_network(self):
        """Test that invalid network shows error"""
        response = self.client.get('/search/', {'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB', 'network': 'invalid'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('INVALID_NETWORK', str(response.content))
    
    @patch('webApp.views.StellarAccountSearchCache')
    def test_search_view_no_db_write_on_invalid_address(self, mock_cache):
        """Test that invalid addresses don't trigger database writes"""
        response = self.client.get('/search/', {'account': 'G', 'network': 'public'})
        self.assertEqual(response.status_code, 200)
        mock_cache.objects.create.assert_not_called()
    
    def test_search_view_error_message_format(self):
        """Test that error message is user-friendly"""
        response = self.client.get('/search/', {'account': 'invalid', 'network': 'public'})
        self.assertEqual(response.status_code, 200)
        content = str(response.content)
        self.assertIn('Invalid Stellar account address format', content)
        self.assertIn('Must be 56 characters starting with G', content)
    
    def test_search_view_includes_pending_accounts_on_error(self):
        """Test that Pending Accounts tab is populated even on error"""
        response = self.client.get('/search/', {'account': 'invalid', 'network': 'public'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('pending_accounts_data', str(response.content))
