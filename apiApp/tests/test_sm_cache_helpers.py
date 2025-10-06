import datetime
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from apiApp.helpers.sm_cache import StellarMapCacheHelpers
from apiApp.models import (
    StellarAccountSearchCache,
    PENDING_MAKE_PARENT_LINEAGE,
    DONE_MAKE_PARENT_LINEAGE
)


class StellarMapCacheHelpersTest(TestCase):
    """
    Tests for StellarMapCacheHelpers with mocked Cassandra operations.
    Validates cache freshness logic, PENDING entry creation, and cache updates.
    """

    def setUp(self):
        """Set up test data and helper instance."""
        self.cache_helpers = StellarMapCacheHelpers()
        self.test_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        self.test_network = "public"

    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache.objects')
    def test_check_cache_freshness_fresh_data(self, mock_objects):
        """Test that fresh cache data (< 12 hours) is correctly identified."""
        mock_entry = Mock()
        mock_entry.stellar_account = self.test_account
        mock_entry.network_name = self.test_network
        mock_entry.last_fetched_at = datetime.datetime.utcnow()
        mock_entry.cached_json = json.dumps({"test": "data"})
        
        mock_objects.get.return_value = mock_entry
        
        is_fresh, entry = self.cache_helpers.check_cache_freshness(
            self.test_account,
            network_name=self.test_network
        )
        
        self.assertTrue(is_fresh)
        self.assertIsNotNone(entry)
        mock_objects.get.assert_called_once_with(
            stellar_account=self.test_account,
            network_name=self.test_network
        )

    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache.objects')
    def test_check_cache_freshness_stale_data(self, mock_objects):
        """Test that stale cache data (> 12 hours) is correctly identified."""
        mock_entry = Mock()
        mock_entry.stellar_account = self.test_account
        mock_entry.network_name = self.test_network
        mock_entry.last_fetched_at = datetime.datetime.utcnow() - datetime.timedelta(hours=13)
        
        mock_objects.get.return_value = mock_entry
        
        is_fresh, entry = self.cache_helpers.check_cache_freshness(
            self.test_account,
            self.test_network
        )
        
        self.assertFalse(is_fresh)
        self.assertIsNotNone(entry)

    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache.objects')
    def test_check_cache_freshness_no_last_fetched(self, mock_objects):
        """Test that entries without last_fetched_at are treated as stale."""
        mock_entry = Mock()
        mock_entry.stellar_account = self.test_account
        mock_entry.network_name = self.test_network
        mock_entry.last_fetched_at = None
        
        mock_objects.get.return_value = mock_entry
        
        is_fresh, entry = self.cache_helpers.check_cache_freshness(
            self.test_account,
            self.test_network
        )
        
        self.assertFalse(is_fresh)
        self.assertIsNotNone(entry)

    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache.objects')
    def test_check_cache_freshness_entry_not_found(self, mock_objects):
        """Test handling when cache entry doesn't exist."""
        mock_objects.get.side_effect = StellarAccountSearchCache.DoesNotExist
        
        is_fresh, entry = self.cache_helpers.check_cache_freshness(
            self.test_account,
            self.test_network
        )
        
        self.assertFalse(is_fresh)
        self.assertIsNone(entry)

    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache.objects')
    def test_create_pending_entry_new_account(self, mock_objects):
        """Test creating a PENDING entry for a new account."""
        mock_objects.get.side_effect = StellarAccountSearchCache.DoesNotExist
        
        mock_new_entry = Mock()
        mock_new_entry.stellar_account = self.test_account
        mock_new_entry.network_name = self.test_network
        mock_new_entry.status = PENDING_MAKE_PARENT_LINEAGE
        mock_new_entry.save = Mock()
        
        with patch('apiApp.helpers.sm_cache.StellarAccountSearchCache', return_value=mock_new_entry):
            entry = self.cache_helpers.create_pending_entry(
                self.test_account,
                self.test_network
            )
            
            self.assertIsNotNone(entry)
            self.assertEqual(entry.status, PENDING_MAKE_PARENT_LINEAGE)

    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache.objects')
    def test_create_pending_entry_existing_account(self, mock_objects):
        """Test updating an existing entry to PENDING status."""
        mock_existing = Mock()
        mock_existing.stellar_account = self.test_account
        mock_existing.network_name = self.test_network
        mock_existing.status = DONE_MAKE_PARENT_LINEAGE
        mock_existing.save = Mock()
        
        mock_objects.get.return_value = mock_existing
        
        entry = self.cache_helpers.create_pending_entry(
            self.test_account,
            self.test_network
        )
        
        self.assertEqual(entry.status, PENDING_MAKE_PARENT_LINEAGE)
        mock_existing.save.assert_called_once()

    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache.objects')
    def test_update_cache_new_entry(self, mock_objects):
        """Test updating cache with new tree data for a new entry."""
        mock_objects.get.side_effect = StellarAccountSearchCache.DoesNotExist
        
        tree_data = {
            "stellar_account": self.test_account,
            "node_type": "ISSUER",
            "children": []
        }
        
        mock_new_entry = Mock()
        mock_new_entry.stellar_account = self.test_account
        mock_new_entry.network_name = self.test_network
        mock_new_entry.cached_json = json.dumps(tree_data)
        mock_new_entry.save = Mock()
        
        with patch('apiApp.helpers.sm_cache.StellarAccountSearchCache', return_value=mock_new_entry):
            entry = self.cache_helpers.update_cache(
                self.test_account,
                self.test_network,
                tree_data,
                DONE_MAKE_PARENT_LINEAGE
            )
            
            self.assertIsNotNone(entry)
            self.assertEqual(entry.cached_json, json.dumps(tree_data))

    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache.objects')
    def test_update_cache_existing_entry(self, mock_objects):
        """Test updating cache for an existing entry."""
        mock_existing = Mock()
        mock_existing.stellar_account = self.test_account
        mock_existing.network_name = self.test_network
        mock_existing.status = PENDING_MAKE_PARENT_LINEAGE
        mock_existing.save = Mock()
        
        mock_objects.get.return_value = mock_existing
        
        tree_data = {"test": "data"}
        
        entry = self.cache_helpers.update_cache(
            self.test_account,
            self.test_network,
            tree_data,
            DONE_MAKE_PARENT_LINEAGE
        )
        
        self.assertEqual(entry.status, DONE_MAKE_PARENT_LINEAGE)
        self.assertIsNotNone(entry.cached_json)
        self.assertIsNotNone(entry.last_fetched_at)
        mock_existing.save.assert_called_once()

    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache.objects')
    def test_get_cached_data_valid_json(self, mock_objects):
        """Test retrieving and parsing valid cached JSON data."""
        tree_data = {"stellar_account": self.test_account, "children": []}
        
        mock_entry = Mock()
        mock_entry.cached_json = json.dumps(tree_data)
        
        cached_data = self.cache_helpers.get_cached_data(mock_entry)
        
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data["stellar_account"], self.test_account)

    def test_get_cached_data_empty_json(self):
        """Test handling of empty cached_json."""
        mock_entry = Mock()
        mock_entry.cached_json = None
        
        cached_data = self.cache_helpers.get_cached_data(mock_entry)
        
        self.assertIsNone(cached_data)

    def test_get_cached_data_invalid_json(self):
        """Test handling of malformed JSON in cached_json."""
        mock_entry = Mock()
        mock_entry.cached_json = "invalid json {{"
        
        with self.assertRaises(json.JSONDecodeError):
            self.cache_helpers.get_cached_data(mock_entry)

    @patch('apiApp.helpers.sm_cache.StellarAccountSearchCache.objects')
    def test_cache_freshness_boundary_exactly_12_hours(self, mock_objects):
        """Test cache freshness at exactly 12-hour boundary."""
        mock_entry = Mock()
        mock_entry.last_fetched_at = datetime.datetime.utcnow() - datetime.timedelta(hours=12)
        
        mock_objects.get.return_value = mock_entry
        
        is_fresh, entry = self.cache_helpers.check_cache_freshness(
            self.test_account,
            self.test_network
        )
        
        # At exactly 12 hours, should be considered stale
        self.assertFalse(is_fresh)
