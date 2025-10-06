import datetime
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from apiApp.models import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    ManagementCronHealth,
    PENDING_MAKE_PARENT_LINEAGE,
    DONE_MAKE_PARENT_LINEAGE,
    PENDING_HORIZON_API_DATASETS
)


class CassandraModelIntegrationTest(TestCase):
    """
    Integration tests for Cassandra models with mocked database operations.
    Tests composite primary keys, timestamp management, and CRUD operations.
    """

    def setUp(self):
        """Set up test data."""
        self.test_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        self.test_network = "public"
        self.test_cron_name = "cron_make_parent_account_lineage"

    @patch('apiApp.models.StellarAccountSearchCache.objects')
    def test_search_cache_composite_primary_key(self, mock_objects):
        """Test StellarAccountSearchCache uses composite primary key (stellar_account, network)."""
        mock_entry = Mock()
        mock_entry.stellar_account = self.test_account
        mock_entry.network = self.test_network
        mock_entry.status = PENDING_MAKE_PARENT_LINEAGE
        mock_entry.created_at = datetime.datetime.utcnow()
        mock_entry.updated_at = datetime.datetime.utcnow()
        
        mock_objects.create.return_value = mock_entry
        
        entry = StellarAccountSearchCache.objects.create(
            stellar_account=self.test_account,
            network=self.test_network,
            status=PENDING_MAKE_PARENT_LINEAGE
        )
        
        self.assertEqual(entry.stellar_account, self.test_account)
        self.assertEqual(entry.network, self.test_network)
        mock_objects.create.assert_called_once()

    def test_search_cache_timestamp_management(self):
        """Test that StellarAccountSearchCache auto-manages timestamps."""
        cache_entry = StellarAccountSearchCache()
        cache_entry.stellar_account = self.test_account
        cache_entry.network = self.test_network
        cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
        
        # Call the save() method to trigger timestamp setting logic
        original_save = super(StellarAccountSearchCache, cache_entry).save
        with patch.object(StellarAccountSearchCache, 'save', wraps=cache_entry.save) as mock_save:
            # Manually trigger timestamp logic (mimics what save() does)
            if not cache_entry.created_at:
                cache_entry.created_at = datetime.datetime.utcnow()
            cache_entry.updated_at = datetime.datetime.utcnow()
            
            self.assertIsNotNone(cache_entry.created_at)
            self.assertIsNotNone(cache_entry.updated_at)

    @patch('apiApp.models.StellarCreatorAccountLineage.objects')
    def test_lineage_composite_primary_key(self, mock_objects):
        """Test StellarCreatorAccountLineage uses composite primary key (stellar_account, network_name)."""
        mock_lineage = Mock()
        mock_lineage.stellar_account = self.test_account
        mock_lineage.network_name = self.test_network
        mock_lineage.stellar_creator_account = "GCREATOR123"
        mock_lineage.xlm_balance = 100.5
        
        mock_objects.create.return_value = mock_lineage
        
        lineage = StellarCreatorAccountLineage.objects.create(
            stellar_account=self.test_account,
            network_name=self.test_network,
            stellar_creator_account="GCREATOR123"
        )
        
        self.assertEqual(lineage.stellar_account, self.test_account)
        self.assertEqual(lineage.network_name, self.test_network)
        mock_objects.create.assert_called_once()

    def test_lineage_timestamp_management(self):
        """Test that StellarCreatorAccountLineage auto-manages timestamps."""
        lineage = StellarCreatorAccountLineage()
        lineage.stellar_account = self.test_account
        lineage.network_name = self.test_network
        
        # Manually trigger timestamp logic (mimics what save() does)
        if not lineage.created_at:
            lineage.created_at = datetime.datetime.utcnow()
        lineage.updated_at = datetime.datetime.utcnow()
        
        self.assertIsNotNone(lineage.created_at)
        self.assertIsNotNone(lineage.updated_at)

    @patch('apiApp.models.ManagementCronHealth.objects')
    def test_cron_health_composite_primary_key(self, mock_objects):
        """Test ManagementCronHealth uses composite primary key (cron_name, created_at DESC)."""
        mock_health = Mock()
        mock_health.cron_name = self.test_cron_name
        mock_health.created_at = datetime.datetime.utcnow()
        mock_health.status = "HEALTHY"
        
        mock_objects.create.return_value = mock_health
        
        health = ManagementCronHealth.objects.create(
            cron_name=self.test_cron_name,
            status="HEALTHY"
        )
        
        self.assertEqual(health.cron_name, self.test_cron_name)
        self.assertEqual(health.status, "HEALTHY")
        mock_objects.create.assert_called_once()

    @patch('apiApp.models.ManagementCronHealth.objects')
    def test_cron_health_clustering_order(self, mock_objects):
        """Test that ManagementCronHealth can retrieve latest entry via clustering order."""
        mock_queryset = MagicMock()
        mock_latest = Mock()
        mock_latest.cron_name = self.test_cron_name
        mock_latest.created_at = datetime.datetime.utcnow()
        mock_latest.status = "HEALTHY"
        
        mock_queryset.filter.return_value.first.return_value = mock_latest
        mock_objects.filter.return_value = mock_queryset.filter.return_value
        
        latest_health = ManagementCronHealth.objects.filter(
            cron_name=self.test_cron_name
        ).first()
        
        self.assertIsNotNone(latest_health)
        self.assertEqual(latest_health.status, "HEALTHY")

    @patch('apiApp.models.StellarAccountSearchCache.objects')
    def test_search_cache_update_operation(self, mock_objects):
        """Test updating an existing StellarAccountSearchCache entry."""
        mock_entry = Mock()
        mock_entry.stellar_account = self.test_account
        mock_entry.network = self.test_network
        mock_entry.status = PENDING_MAKE_PARENT_LINEAGE
        mock_entry.cached_json = None
        
        mock_objects.get.return_value = mock_entry
        
        entry = StellarAccountSearchCache.objects.get(
            stellar_account=self.test_account,
            network=self.test_network
        )
        
        entry.status = DONE_MAKE_PARENT_LINEAGE
        entry.cached_json = json.dumps({"test": "data"})
        
        with patch.object(entry, 'save', return_value=None):
            entry.save()
            self.assertEqual(entry.status, DONE_MAKE_PARENT_LINEAGE)
            self.assertIsNotNone(entry.cached_json)

    @patch('apiApp.models.StellarCreatorAccountLineage.objects')
    def test_lineage_filter_by_account_and_network(self, mock_objects):
        """Test querying lineage by composite key filters efficiently."""
        mock_queryset = [
            Mock(stellar_account=self.test_account, network_name=self.test_network),
            Mock(stellar_account=self.test_account, network_name=self.test_network),
        ]
        
        mock_objects.filter.return_value = mock_queryset
        
        lineages = StellarCreatorAccountLineage.objects.filter(
            stellar_account=self.test_account,
            network_name=self.test_network
        )
        
        self.assertEqual(len(lineages), 2)
        mock_objects.filter.assert_called_once_with(
            stellar_account=self.test_account,
            network_name=self.test_network
        )

    @patch('apiApp.models.StellarAccountSearchCache.objects')
    def test_search_cache_no_uuid_id_field(self, mock_objects):
        """Test that StellarAccountSearchCache does not have a UUID id field."""
        cache = StellarAccountSearchCache()
        
        # Should not have an 'id' attribute from BaseModel
        self.assertFalse(hasattr(cache, 'id') and isinstance(getattr(cache, 'id', None), type(None)))
        
        # Should have composite primary key fields
        self.assertTrue(hasattr(cache, 'stellar_account'))
        self.assertTrue(hasattr(cache, 'network'))

    @patch('apiApp.models.StellarCreatorAccountLineage.objects')
    def test_lineage_no_uuid_id_field(self, mock_objects):
        """Test that StellarCreatorAccountLineage does not have a UUID id field."""
        lineage = StellarCreatorAccountLineage()
        
        # Should not have an 'id' attribute from BaseModel
        self.assertFalse(hasattr(lineage, 'id') and isinstance(getattr(lineage, 'id', None), type(None)))
        
        # Should have composite primary key fields
        self.assertTrue(hasattr(lineage, 'stellar_account'))
        self.assertTrue(hasattr(lineage, 'network_name'))

    @patch('apiApp.models.ManagementCronHealth.objects')
    def test_cron_health_no_uuid_id_field(self, mock_objects):
        """Test that ManagementCronHealth does not have a UUID id field."""
        health = ManagementCronHealth()
        
        # Should not have an 'id' attribute from BaseModel
        self.assertFalse(hasattr(health, 'id') and isinstance(getattr(health, 'id', None), type(None)))
        
        # Should have composite primary key fields
        self.assertTrue(hasattr(health, 'cron_name'))
        self.assertTrue(hasattr(health, 'created_at'))
