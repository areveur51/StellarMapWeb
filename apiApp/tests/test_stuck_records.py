# apiApp/tests/test_stuck_records.py
"""
Comprehensive tests for stuck record detection and recovery system.
"""
import datetime
from unittest.mock import Mock, patch
from django.test import TestCase
from apiApp.helpers.stuck_records import (
    detect_stuck_records,
    reset_stuck_record,
    recover_stuck_records,
)
from apiApp.models import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    PENDING_MAKE_PARENT_LINEAGE,
    IN_PROGRESS_MAKE_PARENT_LINEAGE,
    PENDING_HORIZON_API_DATASETS,
    FAILED,
    STUCK_THRESHOLDS,
    MAX_RETRY_ATTEMPTS,
)


class StuckRecordsDetectionTestCase(TestCase):
    """Test detection of stuck records."""
    
    @patch('apiApp.helpers.stuck_records.StellarAccountSearchCache')
    @patch('apiApp.helpers.stuck_records.StellarCreatorAccountLineage')
    def test_detect_stuck_cache_record_with_null_retry_count(
        self, mock_lineage_model, mock_cache_model
    ):
        """Test detection of stuck record when retry_count is None."""
        # Mock a stuck record with retry_count = None
        mock_record = Mock()
        mock_record.stellar_account = 'GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU'
        mock_record.network_name = 'testnet'
        mock_record.status = IN_PROGRESS_MAKE_PARENT_LINEAGE
        mock_record.retry_count = None  # This is the issue!
        mock_record.updated_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=60)
        
        # Mock the query to return this record only for IN_PROGRESS_MAKE_PARENT_LINEAGE status
        def filter_side_effect(status):
            mock_filter = Mock()
            if status == IN_PROGRESS_MAKE_PARENT_LINEAGE:
                mock_filter.all.return_value = [mock_record]
            else:
                mock_filter.all.return_value = []
            return mock_filter
        
        mock_cache_model.objects.filter.side_effect = filter_side_effect
        mock_lineage_model.objects.filter().all.return_value = []
        
        # Run detection
        stuck_records = detect_stuck_records()
        
        # Verify detection works with null retry_count
        # Filter for our specific record since other statuses may also be checked
        our_records = [r for r in stuck_records if r['stellar_account'] == mock_record.stellar_account]
        self.assertEqual(len(our_records), 1)
        self.assertEqual(our_records[0]['retry_count'], 0)  # Should default to 0
        self.assertEqual(our_records[0]['stellar_account'], mock_record.stellar_account)
    
    @patch('apiApp.helpers.stuck_records.StellarAccountSearchCache')
    @patch('apiApp.helpers.stuck_records.StellarCreatorAccountLineage')
    def test_detect_stuck_lineage_record_with_null_retry_count(
        self, mock_lineage_model, mock_cache_model
    ):
        """Test detection of stuck lineage record when retry_count is None."""
        # Mock a stuck record with retry_count = None
        mock_record = Mock()
        mock_record.stellar_account = 'GD6WU64OEP5C4LRBH6NK3MHYIA2ADN6K6II6EXPNVUR3ERBXT4AN4ACD'
        mock_record.network_name = 'public'
        mock_record.status = PENDING_HORIZON_API_DATASETS
        mock_record.retry_count = None
        mock_record.updated_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=300)
        
        # Mock the query
        mock_cache_model.objects.filter().all.return_value = []
        mock_lineage_model.objects.filter().all.return_value = [mock_record]
        
        # Run detection
        stuck_records = detect_stuck_records()
        
        # Verify detection works with null retry_count
        self.assertGreater(len(stuck_records), 0)
        self.assertEqual(stuck_records[0]['retry_count'], 0)  # Should default to 0


class StuckRecordsResetTestCase(TestCase):
    """Test reset logic for stuck records."""
    
    def test_reset_cache_record_with_null_retry_count(self):
        """Test resetting a cache record when retry_count is None."""
        # Create mock record
        mock_record = Mock(spec=StellarAccountSearchCache)
        mock_record.stellar_account = 'GTEST123'
        mock_record.network_name = 'testnet'
        mock_record.status = IN_PROGRESS_MAKE_PARENT_LINEAGE
        mock_record.retry_count = None  # Simulates Cassandra null value
        mock_record.__class__.__name__ = 'StellarAccountSearchCache'
        
        # Run reset
        success = reset_stuck_record(mock_record, reason="Test reset")
        
        # Verify reset succeeded
        self.assertTrue(success)
        mock_record.save.assert_called_once()
        
        # Verify retry_count was set correctly (None should be treated as 0, then incremented to 1)
        self.assertEqual(mock_record.retry_count, 1)
        self.assertEqual(mock_record.status, PENDING_MAKE_PARENT_LINEAGE)
    
    def test_reset_lineage_record_with_null_retry_count(self):
        """Test resetting a lineage record when retry_count is None."""
        # Create mock record
        mock_record = Mock(spec=StellarCreatorAccountLineage)
        mock_record.stellar_account = 'GTEST456'
        mock_record.network_name = 'public'
        mock_record.status = PENDING_HORIZON_API_DATASETS
        mock_record.retry_count = None
        mock_record.__class__.__name__ = 'StellarCreatorAccountLineage'
        
        # Run reset
        success = reset_stuck_record(mock_record, reason="Test reset")
        
        # Verify reset succeeded
        self.assertTrue(success)
        mock_record.save.assert_called_once()
        
        # Verify retry_count was set correctly
        self.assertEqual(mock_record.retry_count, 1)
        self.assertEqual(mock_record.status, PENDING_HORIZON_API_DATASETS)
    
    def test_mark_as_failed_after_max_retries(self):
        """Test that record is marked as FAILED after MAX_RETRY_ATTEMPTS."""
        # Create mock record with max retries
        mock_record = Mock(spec=StellarAccountSearchCache)
        mock_record.stellar_account = 'GTEST789'
        mock_record.network_name = 'testnet'
        mock_record.status = IN_PROGRESS_MAKE_PARENT_LINEAGE
        mock_record.retry_count = MAX_RETRY_ATTEMPTS  # Already at max
        mock_record.__class__.__name__ = 'StellarAccountSearchCache'
        
        # Run reset
        success = reset_stuck_record(mock_record, reason="Test max retries")
        
        # Verify marked as FAILED
        self.assertTrue(success)
        self.assertEqual(mock_record.status, FAILED)
        self.assertIn('Exceeded', mock_record.last_error)
        mock_record.save.assert_called_once()
    
    def test_increment_retry_count_on_each_reset(self):
        """Test that retry_count increments correctly on each reset."""
        # Create mock record
        mock_record = Mock(spec=StellarAccountSearchCache)
        mock_record.stellar_account = 'GTEST999'
        mock_record.network_name = 'testnet'
        mock_record.status = IN_PROGRESS_MAKE_PARENT_LINEAGE
        mock_record.__class__.__name__ = 'StellarAccountSearchCache'
        
        # Test incrementing from 0 to 1
        mock_record.retry_count = 0
        success = reset_stuck_record(mock_record, reason="First reset")
        self.assertTrue(success)
        self.assertEqual(mock_record.retry_count, 1)
        
        # Test incrementing from 1 to 2
        mock_record.save.reset_mock()
        mock_record.retry_count = 1
        success = reset_stuck_record(mock_record, reason="Second reset")
        self.assertTrue(success)
        self.assertEqual(mock_record.retry_count, 2)


class StuckRecordsRecoveryIntegrationTestCase(TestCase):
    """Integration tests for the full recovery workflow."""
    
    @patch('apiApp.helpers.stuck_records.detect_stuck_records')
    def test_recovery_workflow_with_null_retry_counts(self, mock_detect):
        """Test full recovery workflow with null retry counts."""
        # Mock detection returning stuck records with null retry_count
        mock_record1 = Mock(spec=StellarAccountSearchCache)
        mock_record1.stellar_account = 'GTEST111'
        mock_record1.network_name = 'testnet'
        mock_record1.status = IN_PROGRESS_MAKE_PARENT_LINEAGE
        mock_record1.retry_count = None
        mock_record1.__class__.__name__ = 'StellarAccountSearchCache'
        
        mock_record2 = Mock(spec=StellarCreatorAccountLineage)
        mock_record2.stellar_account = 'GTEST222'
        mock_record2.network_name = 'public'
        mock_record2.status = PENDING_HORIZON_API_DATASETS
        mock_record2.retry_count = None
        mock_record2.__class__.__name__ = 'StellarCreatorAccountLineage'
        
        mock_detect.return_value = [
            {
                'table': 'StellarAccountSearchCache',
                'record': mock_record1,
                'status': IN_PROGRESS_MAKE_PARENT_LINEAGE,
                'age_minutes': 60,
                'threshold_minutes': 5,
                'stellar_account': 'GTEST111',
                'network_name': 'testnet',
                'retry_count': 0,  # Detection should have converted None to 0
            },
            {
                'table': 'StellarCreatorAccountLineage',
                'record': mock_record2,
                'status': PENDING_HORIZON_API_DATASETS,
                'age_minutes': 300,
                'threshold_minutes': 5,
                'stellar_account': 'GTEST222',
                'network_name': 'public',
                'retry_count': 0,
            },
        ]
        
        # Run recovery
        stats = recover_stuck_records(auto_fix=True)
        
        # Verify statistics
        self.assertEqual(stats['detected'], 2)
        self.assertEqual(stats['reset'], 2)
        self.assertEqual(stats['failed'], 0)
        self.assertEqual(stats['errors'], 0)
        
        # Verify both records were saved
        mock_record1.save.assert_called_once()
        mock_record2.save.assert_called_once()
        
        # Verify retry counts were incremented
        self.assertEqual(mock_record1.retry_count, 1)
        self.assertEqual(mock_record2.retry_count, 1)
    
    @patch('apiApp.helpers.stuck_records.detect_stuck_records')
    def test_dry_run_doesnt_modify_records(self, mock_detect):
        """Test that dry-run mode detects but doesn't modify records."""
        # Mock a stuck record
        mock_record = Mock(spec=StellarAccountSearchCache)
        mock_record.stellar_account = 'GTEST333'
        mock_record.network_name = 'testnet'
        mock_record.status = IN_PROGRESS_MAKE_PARENT_LINEAGE
        mock_record.retry_count = None
        
        mock_detect.return_value = [
            {
                'table': 'StellarAccountSearchCache',
                'record': mock_record,
                'status': IN_PROGRESS_MAKE_PARENT_LINEAGE,
                'age_minutes': 60,
                'threshold_minutes': 5,
                'stellar_account': 'GTEST333',
                'network_name': 'testnet',
                'retry_count': 0,
            },
        ]
        
        # Run recovery in dry-run mode
        stats = recover_stuck_records(auto_fix=False)
        
        # Verify detection occurred but no changes were made
        self.assertEqual(stats['detected'], 1)
        self.assertEqual(stats['reset'], 0)
        self.assertEqual(stats['failed'], 0)
        mock_record.save.assert_not_called()


class EdgeCaseTestCase(TestCase):
    """Test edge cases and error conditions."""
    
    def test_reset_record_without_retry_count_attribute(self):
        """Test resetting a record that doesn't have retry_count attribute at all."""
        # Create mock record WITHOUT retry_count attribute
        mock_record = Mock(spec=['stellar_account', 'network_name', 'status', 'save'])
        mock_record.stellar_account = 'GTEST444'
        mock_record.network_name = 'testnet'
        mock_record.status = IN_PROGRESS_MAKE_PARENT_LINEAGE
        mock_record.__class__.__name__ = 'StellarAccountSearchCache'
        
        # This should not raise AttributeError
        success = reset_stuck_record(mock_record, reason="Test missing attribute")
        
        # Should succeed and create the attribute
        self.assertTrue(success)
        self.assertEqual(mock_record.retry_count, 1)
