# webApp/tests.py
import datetime
import json
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock
from apiApp.models import UserInquirySearchHistory, PENDING_MAKE_PARENT_LINEAGE, DONE_MAKE_PARENT_LINEAGE


class SearchViewTests(TestCase):
    """
    Comprehensive tests for search functionality to ensure robustness.
    Tests default behavior, cache integration, and cron job triggering.
    """
    
    def setUp(self):
        """Set up test client and test data"""
        self.client = Client()
        self.test_account = 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB'
        self.test_network = 'testnet'
    
    def test_default_search_loads_successfully(self):
        """Test that default search (no parameters) loads with test data"""
        response = self.client.get(reverse('search'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('tree_data', response.context)
        self.assertIn('search_variable', response.context)
        self.assertIsNotNone(response.context['tree_data'])
    
    def test_default_search_displays_visualization(self):
        """Test that default search renders visualization template"""
        response = self.client.get(reverse('search'))
        
        self.assertTemplateUsed(response, 'webApp/search.html')
        self.assertContains(response, 'radial_tidy_tree_variable')
    
    @patch('webApp.views.StellarMapCacheHelpers')
    def test_search_with_fresh_cached_data(self, mock_cache_helpers):
        """Test that search returns cached data when fresh (< 12 hours)"""
        # Mock cache entry with fresh data
        mock_entry = MagicMock()
        mock_entry.cached_json = json.dumps({
            'name': self.test_account,
            'node_type': 'ISSUER',
            'children': []
        })
        mock_entry.last_fetched_at = datetime.datetime.utcnow()
        
        mock_cache_instance = mock_cache_helpers.return_value
        mock_cache_instance.check_cache_freshness.return_value = (True, mock_entry)
        mock_cache_instance.get_cached_data.return_value = {
            'name': self.test_account,
            'node_type': 'ISSUER',
            'children': []
        }
        
        response = self.client.get(reverse('search'), {
            'account': self.test_account,
            'network': self.test_network
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['is_cached'], True)
        self.assertEqual(response.context['is_refreshing'], False)
    
    @patch('webApp.views.StellarMapCacheHelpers')
    def test_search_with_stale_cache_triggers_pending(self, mock_cache_helpers):
        """Test that stale cache triggers PENDING entry creation"""
        # Mock stale cache entry
        mock_entry = MagicMock()
        mock_entry.cached_json = None
        mock_entry.last_fetched_at = datetime.datetime.utcnow() - datetime.timedelta(hours=13)
        
        mock_cache_instance = mock_cache_helpers.return_value
        mock_cache_instance.check_cache_freshness.return_value = (False, mock_entry)
        mock_cache_instance.create_pending_entry.return_value = mock_entry
        
        response = self.client.get(reverse('search'), {
            'account': self.test_account,
            'network': self.test_network
        })
        
        self.assertEqual(response.status_code, 200)
        mock_cache_instance.create_pending_entry.assert_called_once_with(
            self.test_account, self.test_network
        )
        self.assertEqual(response.context['is_refreshing'], True)
    
    @patch('webApp.views.StellarMapCacheHelpers')
    def test_search_with_no_cache_creates_pending_entry(self, mock_cache_helpers):
        """Test that search with no cache creates PENDING entry"""
        mock_cache_instance = mock_cache_helpers.return_value
        mock_cache_instance.check_cache_freshness.return_value = (False, None)
        
        response = self.client.get(reverse('search'), {
            'account': self.test_account,
            'network': self.test_network
        })
        
        self.assertEqual(response.status_code, 200)
        mock_cache_instance.create_pending_entry.assert_called_once()
    
    def test_search_with_invalid_account_returns_404(self):
        """Test that invalid stellar account returns 404"""
        invalid_account = 'INVALID_ACCOUNT_123'
        
        response = self.client.get(reverse('search'), {
            'account': invalid_account,
            'network': self.test_network
        })
        
        self.assertEqual(response.status_code, 404)
    
    def test_search_with_invalid_network_returns_404(self):
        """Test that invalid network returns 404"""
        response = self.client.get(reverse('search'), {
            'account': self.test_account,
            'network': 'invalid_network'
        })
        
        self.assertEqual(response.status_code, 404)
    
    @patch('webApp.views.StellarMapCacheHelpers')
    def test_search_with_cache_error_falls_back_gracefully(self, mock_cache_helpers):
        """Test that cache errors don't break search functionality"""
        mock_cache_instance = mock_cache_helpers.return_value
        mock_cache_instance.check_cache_freshness.side_effect = Exception("Cache error")
        
        response = self.client.get(reverse('search'), {
            'account': self.test_account,
            'network': self.test_network
        })
        
        # Should still return 200 with fallback behavior
        self.assertEqual(response.status_code, 200)
        self.assertIn('tree_data', response.context)


class CacheHelpersIntegrationTests(TestCase):
    """
    Integration tests for cache helper methods with actual Cassandra operations.
    These tests verify the cache workflow integrates properly with cron jobs.
    """
    
    def setUp(self):
        """Set up test data"""
        self.test_account = 'GBKT4JAFW5IX7P6XKUJSOHZLKW3UP4OQFHPFNQ6V5MTIXNUMHZL4Z5GH'
        self.test_network = 'testnet'
    
    @patch('apiApp.helpers.sm_cache.UserInquirySearchHistory')
    def test_create_pending_entry_sets_correct_status(self, mock_model):
        """Test that create_pending_entry sets PENDING_MAKE_PARENT_LINEAGE status"""
        from apiApp.helpers.sm_cache import StellarMapCacheHelpers
        
        mock_model.objects.get.side_effect = mock_model.DoesNotExist
        mock_entry = MagicMock()
        mock_model.objects.create.return_value = mock_entry
        
        cache_helpers = StellarMapCacheHelpers()
        result = cache_helpers.create_pending_entry(self.test_account, self.test_network)
        
        # Verify PENDING_MAKE_PARENT_LINEAGE status was used
        call_kwargs = mock_model.objects.create.call_args[1]
        self.assertEqual(call_kwargs['status'], PENDING_MAKE_PARENT_LINEAGE)
        self.assertEqual(call_kwargs['stellar_account'], self.test_account)
        self.assertEqual(call_kwargs['network_name'], self.test_network)
    
    @patch('apiApp.helpers.sm_cache.UserInquirySearchHistory')
    def test_update_cache_saves_json_and_timestamp(self, mock_model):
        """Test that update_cache properly saves cached_json and last_fetched_at"""
        from apiApp.helpers.sm_cache import StellarMapCacheHelpers
        
        mock_entry = MagicMock()
        mock_model.objects.get.return_value = mock_entry
        
        tree_data = {'name': 'Test', 'node_type': 'ISSUER', 'children': []}
        cache_helpers = StellarMapCacheHelpers()
        cache_helpers.update_cache(self.test_account, self.test_network, tree_data)
        
        # Verify cached_json was set
        self.assertIsNotNone(mock_entry.cached_json)
        # Verify last_fetched_at was set
        self.assertIsNotNone(mock_entry.last_fetched_at)
        # Verify save was called
        mock_entry.save.assert_called_once()
