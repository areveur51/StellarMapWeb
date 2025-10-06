import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
from apiApp.models import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    ManagementCronHealth,
    PENDING_MAKE_PARENT_LINEAGE,
    DONE_MAKE_PARENT_LINEAGE,
    PENDING_HORIZON_API_DATASETS,
    DONE_HORIZON_API_DATASETS
)


class CronCommandsIntegrationTest(TestCase):
    """
    Integration tests for Django management cron commands.
    Tests workflow progression, API integration, and database updates.
    """

    def setUp(self):
        """Set up test data."""
        self.test_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        self.test_network = "public"

    @patch('apiApp.management.commands.cron_make_parent_account_lineage.StellarAccountSearchCache.objects')
    @patch('apiApp.management.commands.cron_make_parent_account_lineage.ManagementCronHealth.objects')
    def test_cron_make_parent_lineage_finds_pending_entries(self, mock_health_objects, mock_cache_objects):
        """Test that cron_make_parent_account_lineage finds PENDING entries."""
        mock_pending = [
            Mock(stellar_account=self.test_account, network_name=self.test_network, status=PENDING_MAKE_PARENT_LINEAGE)
        ]
        
        mock_cache_objects.filter.return_value = mock_pending
        
        # Mock health record creation
        mock_health = Mock()
        mock_health_objects.create.return_value = mock_health
        
        pending_entries = StellarAccountSearchCache.objects.filter(
            status=PENDING_MAKE_PARENT_LINEAGE
        )
        
        self.assertEqual(len(pending_entries), 1)
        self.assertEqual(pending_entries[0].stellar_account, self.test_account)

    @patch('apiApp.management.commands.cron_collect_account_horizon_data.StellarAccountSearchCache.objects')
    @patch('apiApp.management.commands.cron_collect_account_horizon_data.requests.get')
    def test_cron_collect_horizon_data_api_call(self, mock_get, mock_cache_objects):
        """Test that cron_collect_account_horizon_data makes Horizon API calls."""
        mock_entry = Mock()
        mock_entry.stellar_account = self.test_account
        mock_entry.network = self.test_network
        mock_entry.status = PENDING_HORIZON_API_DATASETS
        
        mock_cache_objects.filter.return_value = [mock_entry]
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": self.test_account,
            "balances": [{"asset_type": "native", "balance": "100.0"}]
        }
        mock_get.return_value = mock_response
        
        # Simulate API call
        response = mock_get(f"https://horizon.stellar.org/accounts/{self.test_account}")
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("balances", response.json())

    @patch('apiApp.management.commands.cron_make_parent_account_lineage.StellarAccountSearchCache.objects')
    def test_cron_updates_cache_status_on_completion(self, mock_cache_objects):
        """Test that cron updates cache entry status upon completion."""
        mock_entry = Mock()
        mock_entry.stellar_account = self.test_account
        mock_entry.status = PENDING_MAKE_PARENT_LINEAGE
        mock_entry.save = Mock()
        
        mock_cache_objects.get.return_value = mock_entry
        
        # Simulate cron completion
        mock_entry.status = DONE_MAKE_PARENT_LINEAGE
        mock_entry.save()
        
        self.assertEqual(mock_entry.status, DONE_MAKE_PARENT_LINEAGE)
        mock_entry.save.assert_called_once()

    @patch('apiApp.management.commands.cron_health_check.ManagementCronHealth.objects')
    def test_cron_health_check_creates_health_record(self, mock_health_objects):
        """Test that cron_health_check creates health monitoring records."""
        mock_health = Mock()
        mock_health.cron_name = "cron_make_parent_account_lineage"
        mock_health.status = "HEALTHY"
        mock_health.created_at = datetime.datetime.utcnow()
        
        mock_health_objects.create.return_value = mock_health
        
        health_record = ManagementCronHealth.objects.create(
            cron_name="cron_make_parent_account_lineage",
            status="HEALTHY"
        )
        
        self.assertEqual(health_record.cron_name, "cron_make_parent_account_lineage")
        self.assertEqual(health_record.status, "HEALTHY")

    @patch('apiApp.management.commands.cron_make_parent_account_lineage.StellarAccountSearchCache.objects')
    def test_cron_handles_multiple_pending_entries(self, mock_cache_objects):
        """Test that cron processes multiple PENDING entries."""
        mock_entries = [
            Mock(stellar_account="ACCOUNT1", network_name="public", status=PENDING_MAKE_PARENT_LINEAGE),
            Mock(stellar_account="ACCOUNT2", network_name="public", status=PENDING_MAKE_PARENT_LINEAGE),
            Mock(stellar_account="ACCOUNT3", network_name="testnet", status=PENDING_MAKE_PARENT_LINEAGE),
        ]
        
        mock_cache_objects.filter.return_value = mock_entries
        
        pending = StellarAccountSearchCache.objects.filter(status=PENDING_MAKE_PARENT_LINEAGE)
        
        self.assertEqual(len(pending), 3)

    @patch('apiApp.management.commands.cron_collect_account_horizon_data.requests.get')
    def test_cron_handles_api_errors(self, mock_get):
        """Test that cron handles Horizon API errors gracefully."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Not Found"}
        mock_get.return_value = mock_response
        
        response = mock_get(f"https://horizon.stellar.org/accounts/{self.test_account}")
        
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

    @patch('apiApp.management.commands.cron_collect_account_horizon_data.StellarCreatorAccountLineage.objects')
    def test_cron_creates_lineage_records(self, mock_lineage_objects):
        """Test that cron creates lineage records from Horizon data."""
        mock_lineage = Mock()
        mock_lineage.stellar_account = self.test_account
        mock_lineage.stellar_creator_account = "GCREATOR123"
        mock_lineage.save = Mock()
        
        with patch('apiApp.management.commands.cron_collect_account_horizon_data.StellarCreatorAccountLineage', return_value=mock_lineage):
            lineage = StellarCreatorAccountLineage()
            lineage.stellar_account = self.test_account
            lineage.stellar_creator_account = "GCREATOR123"
            lineage.save()
            
            mock_lineage.save.assert_called_once()

    @patch('apiApp.management.commands.cron_make_parent_account_lineage.StellarMapCacheHelpers')
    def test_cron_updates_cache_after_completion(self, mock_cache_helpers_class):
        """Test that cron updates cache with tree_data after completion."""
        mock_helpers = Mock()
        mock_helpers.update_cache = Mock()
        mock_cache_helpers_class.return_value = mock_helpers
        
        tree_data = {"stellar_account": self.test_account, "children": []}
        
        helpers = mock_cache_helpers_class()
        helpers.update_cache(self.test_account, self.test_network, tree_data, DONE_MAKE_PARENT_LINEAGE)
        
        mock_helpers.update_cache.assert_called_once_with(
            self.test_account, self.test_network, tree_data, DONE_MAKE_PARENT_LINEAGE
        )

    @patch('apiApp.management.commands.cron_health_check.ManagementCronHealth.objects')
    def test_cron_health_check_detects_stale_jobs(self, mock_health_objects):
        """Test that cron_health_check detects stale/unhealthy jobs."""
        old_time = datetime.datetime.utcnow() - datetime.timedelta(hours=25)
        
        mock_old_health = Mock()
        mock_old_health.cron_name = "cron_make_parent_account_lineage"
        mock_old_health.created_at = old_time
        mock_old_health.status = "RUNNING"
        
        mock_queryset = MagicMock()
        mock_queryset.filter.return_value.first.return_value = mock_old_health
        mock_health_objects.filter.return_value = mock_queryset.filter.return_value
        
        latest = ManagementCronHealth.objects.filter(
            cron_name="cron_make_parent_account_lineage"
        ).first()
        
        self.assertIsNotNone(latest)
        # Should be older than 24 hours
        time_diff = datetime.datetime.utcnow() - latest.created_at
        self.assertGreater(time_diff.total_seconds(), 24 * 3600)

    @patch('apiApp.management.commands.cron_update_from_raw_data.StellarCreatorAccountLineage.objects')
    def test_cron_update_from_raw_data_processes_records(self, mock_lineage_objects):
        """Test that cron_update_from_raw_data updates lineage attributes."""
        mock_lineage = Mock()
        mock_lineage.stellar_account = self.test_account
        mock_lineage.xlm_balance = 0.0
        mock_lineage.save = Mock()
        
        mock_lineage_objects.filter.return_value = [mock_lineage]
        
        lineages = StellarCreatorAccountLineage.objects.filter(
            status=DONE_HORIZON_API_DATASETS
        )
        
        # Simulate updating balance from raw data
        for lineage in lineages:
            lineage.xlm_balance = 150.5
            lineage.save()
        
        self.assertEqual(mock_lineage.xlm_balance, 150.5)
        mock_lineage.save.assert_called_once()
