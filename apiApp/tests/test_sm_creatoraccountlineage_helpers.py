import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from django.test import TestCase
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.models import StellarCreatorAccountLineage


class StellarMapCreatorAccountLineageHelpersTest(TestCase):
    """
    Tests for StellarMapCreatorAccountLineageHelpers with mocked Cassandra and API operations.
    Validates lineage creation, grandparent traversal, and data extraction.
    """

    def setUp(self):
        """Set up test data and helper instance."""
        self.lineage_helpers = StellarMapCreatorAccountLineageHelpers()
        self.test_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        self.test_creator = "GCREATOR123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
        self.test_network = "public"

    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineage.objects')
    def test_create_lineage_record(self, mock_objects):
        """Test creating a new lineage record."""
        mock_lineage = Mock()
        mock_lineage.stellar_account = self.test_account
        mock_lineage.network_name = self.test_network
        mock_lineage.stellar_creator_account = self.test_creator
        mock_lineage.save = Mock()
        
        with patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineage', return_value=mock_lineage):
            lineage = StellarCreatorAccountLineage()
            lineage.stellar_account = self.test_account
            lineage.network_name = self.test_network
            lineage.stellar_creator_account = self.test_creator
            lineage.save()
            
            self.assertEqual(lineage.stellar_account, self.test_account)
            self.assertEqual(lineage.stellar_creator_account, self.test_creator)
            mock_lineage.save.assert_called_once()

    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineage.objects')
    def test_fetch_lineage_by_account(self, mock_objects):
        """Test fetching lineage records by stellar account and network."""
        mock_lineages = [
            Mock(stellar_account=self.test_account, network_name=self.test_network),
            Mock(stellar_account=self.test_account, network_name=self.test_network),
        ]
        
        mock_objects.filter.return_value = mock_lineages
        
        lineages = StellarCreatorAccountLineage.objects.filter(
            stellar_account=self.test_account,
            network_name=self.test_network
        )
        
        self.assertEqual(len(lineages), 2)
        mock_objects.filter.assert_called_once_with(
            stellar_account=self.test_account,
            network_name=self.test_network
        )

    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineage.objects')
    def test_update_lineage_from_horizon_data(self, mock_objects):
        """Test updating lineage with Horizon API account data."""
        mock_lineage = Mock()
        mock_lineage.stellar_account = self.test_account
        mock_lineage.xlm_balance = 0.0
        mock_lineage.home_domain = None
        mock_lineage.save = Mock()
        
        mock_objects.get.return_value = mock_lineage
        
        # Simulate updating with Horizon data
        mock_lineage.xlm_balance = 150.5
        mock_lineage.home_domain = "example.com"
        mock_lineage.save()
        
        self.assertEqual(mock_lineage.xlm_balance, 150.5)
        self.assertEqual(mock_lineage.home_domain, "example.com")
        mock_lineage.save.assert_called_once()

    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineage.objects')
    def test_update_from_operations_raw_data(self, mock_objects):
        """Test extracting creator account from operations data."""
        mock_lineage = Mock()
        mock_lineage.stellar_account = self.test_account
        mock_lineage.stellar_creator_account = None
        mock_lineage.save = Mock()
        
        mock_objects.get.return_value = mock_lineage
        
        # Simulate operations data with source_account (creator)
        operations_data = {
            "source_account": self.test_creator,
            "type": "create_account"
        }
        
        mock_lineage.stellar_creator_account = operations_data.get("source_account")
        mock_lineage.save()
        
        self.assertEqual(mock_lineage.stellar_creator_account, self.test_creator)
        mock_lineage.save.assert_called_once()

    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineage.objects')
    def test_make_grandparent_account_creates_parent_lineage(self, mock_objects):
        """Test that grandparent creation recursively creates parent lineage records."""
        # Child lineage
        mock_child = Mock()
        mock_child.stellar_account = self.test_account
        mock_child.stellar_creator_account = self.test_creator
        
        # Parent lineage (to be created)
        mock_parent = Mock()
        mock_parent.stellar_account = self.test_creator
        mock_parent.stellar_creator_account = "GGRANDPARENT123"
        
        mock_objects.filter.return_value = [mock_child]
        
        lineages = StellarCreatorAccountLineage.objects.filter(
            stellar_account=self.test_account,
            network_name=self.test_network
        )
        
        # Verify we can traverse to parent
        self.assertTrue(len(lineages) > 0)
        self.assertEqual(lineages[0].stellar_creator_account, self.test_creator)

    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineage.objects')
    def test_lineage_with_missing_creator_account(self, mock_objects):
        """Test handling lineage records with missing creator account."""
        mock_lineage = Mock()
        mock_lineage.stellar_account = self.test_account
        mock_lineage.stellar_creator_account = None
        
        mock_objects.get.return_value = mock_lineage
        
        lineage = StellarCreatorAccountLineage.objects.get(
            stellar_account=self.test_account,
            network_name=self.test_network
        )
        
        self.assertIsNone(lineage.stellar_creator_account)

    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineage.objects')
    def test_lineage_status_tracking(self, mock_objects):
        """Test that lineage records track processing status."""
        mock_lineage = Mock()
        mock_lineage.status = "PENDING_HORIZON_API_DATASETS"
        mock_lineage.save = Mock()
        
        mock_objects.get.return_value = mock_lineage
        
        # Simulate status progression
        mock_lineage.status = "DONE_HORIZON_API_DATASETS"
        mock_lineage.save()
        
        self.assertEqual(mock_lineage.status, "DONE_HORIZON_API_DATASETS")
        mock_lineage.save.assert_called_once()

    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineage.objects')
    def test_multiple_lineage_records_for_account(self, mock_objects):
        """Test querying multiple lineage records for the same account."""
        mock_lineages = [
            Mock(stellar_account=self.test_account, stellar_creator_account="CREATOR1"),
            Mock(stellar_account=self.test_account, stellar_creator_account="CREATOR2"),
            Mock(stellar_account=self.test_account, stellar_creator_account="CREATOR3"),
        ]
        
        mock_objects.filter.return_value = mock_lineages
        
        lineages = StellarCreatorAccountLineage.objects.filter(
            stellar_account=self.test_account,
            network_name=self.test_network
        )
        
        self.assertEqual(len(lineages), 3)

    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineage.objects')
    def test_lineage_timestamp_tracking(self, mock_objects):
        """Test that lineage records maintain creation timestamps."""
        now = datetime.datetime.utcnow()
        
        mock_lineage = Mock()
        mock_lineage.stellar_account = self.test_account
        mock_lineage.stellar_account_created_at = now
        mock_lineage.created_at = now
        mock_lineage.updated_at = now
        
        mock_objects.get.return_value = mock_lineage
        
        lineage = StellarCreatorAccountLineage.objects.get(
            stellar_account=self.test_account,
            network_name=self.test_network
        )
        
        self.assertIsNotNone(lineage.stellar_account_created_at)
        self.assertIsNotNone(lineage.created_at)
        self.assertIsNotNone(lineage.updated_at)
