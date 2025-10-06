# apiApp/tests/test_stellar_account_search_cache.py
import datetime
import json
from django.test import TestCase
from apiApp.models import StellarAccountSearchCache, PENDING_MAKE_PARENT_LINEAGE, DONE_MAKE_PARENT_LINEAGE
from apiApp.helpers.sm_cache import StellarMapCacheHelpers


class StellarAccountSearchCacheModelTest(TestCase):
    """Test suite for StellarAccountSearchCache model with composite primary key."""
    
    def setUp(self):
        """Set up test data."""
        self.test_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        self.test_network = "public"
        self.cache_helpers = StellarMapCacheHelpers()
    
    def test_create_pending_entry_new_account(self):
        """Test creating a PENDING entry for a new account."""
        cache_entry = self.cache_helpers.create_pending_entry(
            self.test_account, 
            self.test_network
        )
        
        self.assertIsNotNone(cache_entry)
        self.assertEqual(cache_entry.stellar_account, self.test_account)
        self.assertEqual(cache_entry.network, self.test_network)
        self.assertEqual(cache_entry.status, PENDING_MAKE_PARENT_LINEAGE)
        self.assertIsNotNone(cache_entry.created_at)
        self.assertIsNotNone(cache_entry.updated_at)
    
    def test_create_pending_entry_existing_account(self):
        """Test updating an existing entry to PENDING status."""
        # First, create an entry with DONE status
        initial_entry = StellarAccountSearchCache.objects.create(
            stellar_account=self.test_account,
            network=self.test_network,
            status=DONE_MAKE_PARENT_LINEAGE,
            cached_json=json.dumps({"test": "data"}),
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        
        # Now update it to PENDING
        updated_entry = self.cache_helpers.create_pending_entry(
            self.test_account,
            self.test_network
        )
        
        self.assertEqual(updated_entry.stellar_account, self.test_account)
        self.assertEqual(updated_entry.network, self.test_network)
        self.assertEqual(updated_entry.status, PENDING_MAKE_PARENT_LINEAGE)
        self.assertEqual(updated_entry.created_at, initial_entry.created_at)
        self.assertGreater(updated_entry.updated_at, initial_entry.updated_at)
    
    def test_check_cache_freshness_fresh_data(self):
        """Test cache freshness check for fresh data (< 12 hours)."""
        # Create entry with recent last_fetched_at
        cache_entry = StellarAccountSearchCache.objects.create(
            stellar_account=self.test_account,
            network=self.test_network,
            status=DONE_MAKE_PARENT_LINEAGE,
            cached_json=json.dumps({"test": "data"}),
            last_fetched_at=datetime.datetime.utcnow(),
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        
        is_fresh, entry = self.cache_helpers.check_cache_freshness(
            self.test_account,
            self.test_network
        )
        
        self.assertTrue(is_fresh)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.stellar_account, self.test_account)
    
    def test_check_cache_freshness_stale_data(self):
        """Test cache freshness check for stale data (> 12 hours)."""
        # Create entry with old last_fetched_at (13 hours ago)
        old_time = datetime.datetime.utcnow() - datetime.timedelta(hours=13)
        cache_entry = StellarAccountSearchCache.objects.create(
            stellar_account=self.test_account,
            network=self.test_network,
            status=DONE_MAKE_PARENT_LINEAGE,
            cached_json=json.dumps({"test": "data"}),
            last_fetched_at=old_time,
            created_at=old_time,
            updated_at=old_time
        )
        
        is_fresh, entry = self.cache_helpers.check_cache_freshness(
            self.test_account,
            self.test_network
        )
        
        self.assertFalse(is_fresh)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.stellar_account, self.test_account)
    
    def test_check_cache_freshness_no_entry(self):
        """Test cache freshness check when no entry exists."""
        is_fresh, entry = self.cache_helpers.check_cache_freshness(
            "NONEXISTENT_ACCOUNT",
            self.test_network
        )
        
        self.assertFalse(is_fresh)
        self.assertIsNone(entry)
    
    def test_update_cache_new_entry(self):
        """Test updating cache for a new entry."""
        tree_data = {
            "stellar_account": self.test_account,
            "node_type": "ISSUER",
            "children": []
        }
        
        cache_entry = self.cache_helpers.update_cache(
            self.test_account,
            self.test_network,
            tree_data,
            DONE_MAKE_PARENT_LINEAGE
        )
        
        self.assertIsNotNone(cache_entry)
        self.assertEqual(cache_entry.stellar_account, self.test_account)
        self.assertEqual(cache_entry.network, self.test_network)
        self.assertEqual(cache_entry.status, DONE_MAKE_PARENT_LINEAGE)
        self.assertIsNotNone(cache_entry.cached_json)
        self.assertIsNotNone(cache_entry.last_fetched_at)
        
        # Verify cached data can be parsed
        cached_data = json.loads(cache_entry.cached_json)
        self.assertEqual(cached_data["stellar_account"], self.test_account)
    
    def test_update_cache_existing_entry(self):
        """Test updating cache for an existing entry."""
        # Create initial entry
        initial_entry = StellarAccountSearchCache.objects.create(
            stellar_account=self.test_account,
            network=self.test_network,
            status=PENDING_MAKE_PARENT_LINEAGE,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        
        # Update with tree data
        tree_data = {
            "stellar_account": self.test_account,
            "node_type": "ISSUER",
            "children": [{"name": "child1"}]
        }
        
        updated_entry = self.cache_helpers.update_cache(
            self.test_account,
            self.test_network,
            tree_data,
            DONE_MAKE_PARENT_LINEAGE
        )
        
        self.assertEqual(updated_entry.stellar_account, self.test_account)
        self.assertEqual(updated_entry.status, DONE_MAKE_PARENT_LINEAGE)
        self.assertIsNotNone(updated_entry.cached_json)
        self.assertIsNotNone(updated_entry.last_fetched_at)
    
    def test_get_cached_data(self):
        """Test retrieving cached JSON data."""
        tree_data = {
            "stellar_account": self.test_account,
            "node_type": "ISSUER",
            "children": []
        }
        
        cache_entry = StellarAccountSearchCache.objects.create(
            stellar_account=self.test_account,
            network=self.test_network,
            status=DONE_MAKE_PARENT_LINEAGE,
            cached_json=json.dumps(tree_data),
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        
        cached_data = self.cache_helpers.get_cached_data(cache_entry)
        
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data["stellar_account"], self.test_account)
        self.assertEqual(cached_data["node_type"], "ISSUER")
    
    def test_composite_primary_key_uniqueness(self):
        """Test that composite primary key (stellar_account, network) enforces uniqueness."""
        # Create first entry
        entry1 = StellarAccountSearchCache.objects.create(
            stellar_account=self.test_account,
            network="public",
            status=PENDING_MAKE_PARENT_LINEAGE,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        
        # Create second entry with same account but different network
        entry2 = StellarAccountSearchCache.objects.create(
            stellar_account=self.test_account,
            network="testnet",
            status=PENDING_MAKE_PARENT_LINEAGE,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        
        # Both should exist independently
        self.assertIsNotNone(entry1)
        self.assertIsNotNone(entry2)
        self.assertEqual(entry1.network, "public")
        self.assertEqual(entry2.network, "testnet")
    
    def test_model_save_timestamps(self):
        """Test that save() method auto-sets timestamps."""
        cache_entry = StellarAccountSearchCache()
        cache_entry.stellar_account = self.test_account
        cache_entry.network = self.test_network
        cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
        cache_entry.save()
        
        self.assertIsNotNone(cache_entry.created_at)
        self.assertIsNotNone(cache_entry.updated_at)
        
        # Test update
        original_created = cache_entry.created_at
        cache_entry.status = DONE_MAKE_PARENT_LINEAGE
        cache_entry.save()
        
        self.assertEqual(cache_entry.created_at, original_created)
        self.assertGreater(cache_entry.updated_at, original_created)
