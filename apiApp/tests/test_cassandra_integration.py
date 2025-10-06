import datetime
import json
from django.test import TestCase
from apiApp.models import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    ManagementCronHealth,
    PENDING_MAKE_PARENT_LINEAGE,
    DONE_MAKE_PARENT_LINEAGE,
    PENDING_HORIZON_API_DATASETS,
    DONE_HORIZON_API_DATASETS
)


class CassandraRealIntegrationTest(TestCase):
    """
    REAL integration tests that actually exercise Cassandra database operations.
    These tests use real model instances and database queries to catch schema issues.
    """

    def setUp(self):
        """Set up test data - will be cleaned up after each test."""
        self.test_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        self.test_network = "public"
        self.test_cron_name = "test_cron_integration"

    def tearDown(self):
        """Clean up test data from Cassandra."""
        try:
            StellarAccountSearchCache.objects.filter(
                stellar_account=self.test_account
            ).delete()
        except:
            pass
        
        try:
            StellarCreatorAccountLineage.objects.filter(
                stellar_account=self.test_account
            ).delete()
        except:
            pass
        
        try:
            ManagementCronHealth.objects.filter(
                cron_name=self.test_cron_name
            ).delete()
        except:
            pass

    def test_search_cache_create_and_retrieve(self):
        """Test creating and retrieving StellarAccountSearchCache with composite key."""
        # Create entry
        cache_entry = StellarAccountSearchCache()
        cache_entry.stellar_account = self.test_account
        cache_entry.network = self.test_network
        cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
        cache_entry.save()
        
        # Retrieve entry using composite primary key
        retrieved = StellarAccountSearchCache.objects.get(
            stellar_account=self.test_account,
            network=self.test_network
        )
        
        self.assertEqual(retrieved.stellar_account, self.test_account)
        self.assertEqual(retrieved.network, self.test_network)
        self.assertEqual(retrieved.status, PENDING_MAKE_PARENT_LINEAGE)
        self.assertIsNotNone(retrieved.created_at)
        self.assertIsNotNone(retrieved.updated_at)

    def test_search_cache_update_existing_entry(self):
        """Test updating an existing cache entry."""
        # Create initial entry
        cache_entry = StellarAccountSearchCache()
        cache_entry.stellar_account = self.test_account
        cache_entry.network = self.test_network
        cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
        cache_entry.save()
        
        original_created_at = cache_entry.created_at
        
        # Update entry
        cache_entry.status = DONE_MAKE_PARENT_LINEAGE
        cache_entry.cached_json = json.dumps({"test": "data"})
        cache_entry.last_fetched_at = datetime.datetime.utcnow()
        cache_entry.save()
        
        # Retrieve updated entry
        updated = StellarAccountSearchCache.objects.get(
            stellar_account=self.test_account,
            network=self.test_network
        )
        
        self.assertEqual(updated.status, DONE_MAKE_PARENT_LINEAGE)
        self.assertIsNotNone(updated.cached_json)
        self.assertIsNotNone(updated.last_fetched_at)
        self.assertEqual(updated.created_at, original_created_at)
        self.assertGreater(updated.updated_at, original_created_at)

    def test_search_cache_different_networks(self):
        """Test that same account on different networks are separate entries."""
        # Create public network entry
        public_entry = StellarAccountSearchCache()
        public_entry.stellar_account = self.test_account
        public_entry.network = "public"
        public_entry.status = PENDING_MAKE_PARENT_LINEAGE
        public_entry.save()
        
        # Create testnet entry
        testnet_entry = StellarAccountSearchCache()
        testnet_entry.stellar_account = self.test_account
        testnet_entry.network = "testnet"
        testnet_entry.status = DONE_MAKE_PARENT_LINEAGE
        testnet_entry.save()
        
        # Verify both exist independently
        public_retrieved = StellarAccountSearchCache.objects.get(
            stellar_account=self.test_account,
            network="public"
        )
        testnet_retrieved = StellarAccountSearchCache.objects.get(
            stellar_account=self.test_account,
            network="testnet"
        )
        
        self.assertEqual(public_retrieved.status, PENDING_MAKE_PARENT_LINEAGE)
        self.assertEqual(testnet_retrieved.status, DONE_MAKE_PARENT_LINEAGE)
        
        # Clean up testnet entry
        testnet_entry.delete()

    def test_lineage_create_and_retrieve(self):
        """Test creating and retrieving lineage with composite key."""
        lineage = StellarCreatorAccountLineage()
        lineage.stellar_account = self.test_account
        lineage.network_name = self.test_network
        lineage.stellar_creator_account = "GCREATOR123"
        lineage.xlm_balance = 100.5
        lineage.home_domain = "example.com"
        lineage.save()
        
        # Retrieve using composite key
        retrieved = StellarCreatorAccountLineage.objects.get(
            stellar_account=self.test_account,
            network_name=self.test_network
        )
        
        self.assertEqual(retrieved.stellar_creator_account, "GCREATOR123")
        self.assertEqual(retrieved.xlm_balance, 100.5)
        self.assertEqual(retrieved.home_domain, "example.com")
        self.assertIsNotNone(retrieved.created_at)
        self.assertIsNotNone(retrieved.updated_at)

    def test_lineage_filter_by_account(self):
        """Test filtering lineage records by stellar account."""
        # Create lineage entry
        lineage = StellarCreatorAccountLineage()
        lineage.stellar_account = self.test_account
        lineage.network_name = self.test_network
        lineage.stellar_creator_account = "GCREATOR123"
        lineage.save()
        
        # Filter by account
        lineages = list(StellarCreatorAccountLineage.objects.filter(
            stellar_account=self.test_account
        ))
        
        self.assertGreater(len(lineages), 0)
        self.assertEqual(lineages[0].stellar_account, self.test_account)

    def test_cron_health_create_and_retrieve_latest(self):
        """Test creating cron health records and retrieving latest via clustering."""
        # Create first health record
        health1 = ManagementCronHealth()
        health1.cron_name = self.test_cron_name
        health1.status = "RUNNING"
        health1.save()
        
        # Create second health record (more recent)
        health2 = ManagementCronHealth()
        health2.cron_name = self.test_cron_name
        health2.status = "HEALTHY"
        health2.save()
        
        # Retrieve latest (should be health2 due to DESC clustering)
        latest = ManagementCronHealth.objects.filter(
            cron_name=self.test_cron_name
        ).first()
        
        self.assertIsNotNone(latest)
        self.assertEqual(latest.status, "HEALTHY")

    def test_cron_health_multiple_cron_jobs(self):
        """Test that different cron jobs maintain separate health histories."""
        # Create health for first cron
        health1 = ManagementCronHealth()
        health1.cron_name = "cron_job_1"
        health1.status = "HEALTHY"
        health1.save()
        
        # Create health for second cron
        health2 = ManagementCronHealth()
        health2.cron_name = "cron_job_2"
        health2.status = "UNHEALTHY"
        health2.save()
        
        # Retrieve each independently
        job1_health = ManagementCronHealth.objects.filter(
            cron_name="cron_job_1"
        ).first()
        job2_health = ManagementCronHealth.objects.filter(
            cron_name="cron_job_2"
        ).first()
        
        self.assertEqual(job1_health.status, "HEALTHY")
        self.assertEqual(job2_health.status, "UNHEALTHY")
        
        # Clean up
        health1.delete()
        health2.delete()

    def test_timestamp_auto_management_on_save(self):
        """Test that timestamps are automatically set on save()."""
        cache_entry = StellarAccountSearchCache()
        cache_entry.stellar_account = self.test_account
        cache_entry.network = self.test_network
        cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
        
        # Before save, timestamps should not exist
        self.assertIsNone(cache_entry.created_at)
        self.assertIsNone(cache_entry.updated_at)
        
        # After save, timestamps should be set
        cache_entry.save()
        
        self.assertIsNotNone(cache_entry.created_at)
        self.assertIsNotNone(cache_entry.updated_at)

    def test_cache_json_storage_and_parsing(self):
        """Test storing and retrieving JSON data in cached_json field."""
        tree_data = {
            "stellar_account": self.test_account,
            "node_type": "ISSUER",
            "children": [
                {"name": "child1", "value": 100},
                {"name": "child2", "value": 200}
            ]
        }
        
        cache_entry = StellarAccountSearchCache()
        cache_entry.stellar_account = self.test_account
        cache_entry.network = self.test_network
        cache_entry.cached_json = json.dumps(tree_data)
        cache_entry.save()
        
        # Retrieve and parse JSON
        retrieved = StellarAccountSearchCache.objects.get(
            stellar_account=self.test_account,
            network=self.test_network
        )
        
        parsed_data = json.loads(retrieved.cached_json)
        
        self.assertEqual(parsed_data["stellar_account"], self.test_account)
        self.assertEqual(parsed_data["node_type"], "ISSUER")
        self.assertEqual(len(parsed_data["children"]), 2)
        self.assertEqual(parsed_data["children"][0]["value"], 100)
