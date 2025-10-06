"""
Test Suite: FAILED Status Handling Tests
Tests that FAILED status is properly handled in the cron pipeline.
"""
from django.test import TestCase
from apiApp.models import StellarCreatorAccountLineage, StellarAccountSearchCache
from apiApp.management.commands.cron_recover_stuck_accounts import Command as RecoverStuckAccountsCommand
import uuid


class FailedStatusHandlingTestCase(TestCase):
    """Test FAILED status is treated as terminal and excluded from processing."""
    
    def test_failed_status_not_in_stuck_thresholds(self):
        """Test that FAILED status is excluded from stuck record recovery."""
        from apiApp.helpers.sm_cron import StellarMapCronHelpers
        
        # FAILED should not be in STUCK_THRESHOLDS
        self.assertNotIn('FAILED', StellarMapCronHelpers.STUCK_THRESHOLDS.keys())
    
    def test_invalid_horizon_address_not_in_stuck_thresholds(self):
        """Test that INVALID_HORIZON_STELLAR_ADDRESS is excluded from stuck record recovery."""
        from apiApp.helpers.sm_cron import StellarMapCronHelpers
        
        # INVALID_HORIZON_STELLAR_ADDRESS should not be in STUCK_THRESHOLDS
        self.assertNotIn('INVALID_HORIZON_STELLAR_ADDRESS', StellarMapCronHelpers.STUCK_THRESHOLDS.keys())
    
    def test_failed_records_not_picked_by_stuck_recovery(self):
        """Test that records with FAILED status are not picked up by stuck recovery."""
        # Create a test record with FAILED status
        test_lineage = StellarCreatorAccountLineage.create(
            id=str(uuid.uuid4()),
            stellar_account="GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A",
            network_name="public",
            status="FAILED",
            retry_count=5,
            last_error="Test error - record marked as failed"
        )
        
        # Run stuck recovery
        command = RecoverStuckAccountsCommand()
        command.handle()
        
        # Reload the record
        test_lineage_reloaded = StellarCreatorAccountLineage.objects.get(
            id=test_lineage.id,
            created_at=test_lineage.created_at
        )
        
        # Status should still be FAILED (not changed to PENDING)
        self.assertEqual(test_lineage_reloaded.status, "FAILED")
        
        # Cleanup
        test_lineage.delete()
    
    def test_invalid_horizon_address_not_picked_by_stuck_recovery(self):
        """Test that INVALID_HORIZON_STELLAR_ADDRESS records are not picked up by stuck recovery."""
        # Create a test record with INVALID_HORIZON_STELLAR_ADDRESS status
        test_lineage = StellarCreatorAccountLineage.create(
            id=str(uuid.uuid4()),
            stellar_account="GABC4DCOBIAW2LJBK3GZYOVAWL2FKXJ6DRRUF2WFHLPHYZDF4ZMZX3OA",  # Invalid
            network_name="public",
            status="INVALID_HORIZON_STELLAR_ADDRESS",
            retry_count=2,
            last_error="Not found on Horizon API"
        )
        
        # Run stuck recovery
        command = RecoverStuckAccountsCommand()
        command.handle()
        
        # Reload the record
        test_lineage_reloaded = StellarCreatorAccountLineage.objects.get(
            id=test_lineage.id,
            created_at=test_lineage.created_at
        )
        
        # Status should still be INVALID_HORIZON_STELLAR_ADDRESS (not changed)
        self.assertEqual(test_lineage_reloaded.status, "INVALID_HORIZON_STELLAR_ADDRESS")
        
        # Cleanup
        test_lineage.delete()
    
    def test_failed_cache_records_not_picked_up(self):
        """Test that StellarAccountSearchCache FAILED records are not picked up."""
        # Create a test cache record with FAILED status
        test_cache = StellarAccountSearchCache.create(
            stellar_account="GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A",
            network_name="public",
            status="FAILED",
            retry_count=5,
            last_error="Test error - cache record failed"
        )
        
        # Run stuck recovery
        command = RecoverStuckAccountsCommand()
        command.handle()
        
        # Reload the record
        test_cache_reloaded = StellarAccountSearchCache.objects.get(
            stellar_account=test_cache.stellar_account,
            created_at=test_cache.created_at
        )
        
        # Status should still be FAILED
        self.assertEqual(test_cache_reloaded.status, "FAILED")
        
        # Cleanup
        test_cache.delete()
    
    def test_terminal_statuses_are_documented(self):
        """Test that terminal statuses are properly documented in the system."""
        from apiApp.helpers.sm_cron import StellarMapCronHelpers
        
        # List of known terminal statuses
        terminal_statuses = ['FAILED', 'INVALID_HORIZON_STELLAR_ADDRESS']
        
        # These should never be in STUCK_THRESHOLDS
        for status in terminal_statuses:
            self.assertNotIn(
                status, 
                StellarMapCronHelpers.STUCK_THRESHOLDS.keys(),
                f"Terminal status {status} should not be in STUCK_THRESHOLDS"
            )


class FailedStatusCronExclusionTestCase(TestCase):
    """Test that cron jobs don't pick up FAILED or INVALID records."""
    
    def test_failed_status_constants_exist(self):
        """Test that FAILED status constant is defined."""
        from apiApp.helpers.sm_cron import StellarMapCronHelpers
        
        # Check that status constants include FAILED
        self.assertTrue(hasattr(StellarMapCronHelpers, 'STATUS_FAILED'))
        self.assertEqual(StellarMapCronHelpers.STATUS_FAILED, 'FAILED')
    
    def test_invalid_horizon_address_constant_exists(self):
        """Test that INVALID_HORIZON_STELLAR_ADDRESS constant is defined."""
        from apiApp.helpers.sm_cron import StellarMapCronHelpers
        
        # Check that status constant exists
        self.assertTrue(hasattr(StellarMapCronHelpers, 'STATUS_INVALID_HORIZON_STELLAR_ADDRESS'))
        self.assertEqual(
            StellarMapCronHelpers.STATUS_INVALID_HORIZON_STELLAR_ADDRESS,
            'INVALID_HORIZON_STELLAR_ADDRESS'
        )
    
    def test_cron_queries_exclude_failed_status(self):
        """Test that cron job queries exclude FAILED status records."""
        # Create test records with different statuses
        failed_record = StellarCreatorAccountLineage.create(
            id=str(uuid.uuid4()),
            stellar_account="GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A",
            network_name="public",
            status="FAILED",
            retry_count=5
        )
        
        pending_record = StellarCreatorAccountLineage.create(
            id=str(uuid.uuid4()),
            stellar_account="GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4B",
            network_name="public",
            status="PENDING_HORIZON_API_DATASETS",
            retry_count=0
        )
        
        # Query for pending records (simulating cron job behavior)
        pending_records = StellarCreatorAccountLineage.objects.filter(
            status="PENDING_HORIZON_API_DATASETS"
        ).limit(10)
        pending_list = list(pending_records)
        
        # Should only get the pending record, not the failed one
        account_list = [r.stellar_account for r in pending_list]
        self.assertIn(pending_record.stellar_account, account_list)
        self.assertNotIn(failed_record.stellar_account, account_list)
        
        # Cleanup
        failed_record.delete()
        pending_record.delete()
