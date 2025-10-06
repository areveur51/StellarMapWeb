# apiApp/tests/test_invalid_address_validation.py
"""
Tests for Horizon API validation and INVALID_HORIZON_STELLAR_ADDRESS status.
"""
from unittest.mock import Mock, patch
from django.test import TestCase
from stellar_sdk.exceptions import NotFoundError


class HorizonAddressValidationTestCase(TestCase):
    """Test validation of Stellar addresses against Horizon API."""
    
    @patch('apiApp.management.commands.cron_collect_account_horizon_data.StellarMapHorizonAPIHelpers')
    @patch('apiApp.management.commands.cron_collect_account_horizon_data.StellarCreatorAccountLineageManager')
    @patch('apiApp.management.commands.cron_collect_account_horizon_data.EnvHelpers')
    def test_invalid_address_marked_and_stops_processing(
        self, mock_env_helpers, mock_lineage_manager, mock_horizon_helpers
    ):
        """Test that a 404 from Horizon marks record as invalid AND stops further processing."""
        from apiApp.management.commands.cron_collect_account_horizon_data import Command
        from apiApp.models import INVALID_HORIZON_STELLAR_ADDRESS
        
        # Create mock lineage record
        mock_record = Mock()
        mock_record.id = 'test-id-123'
        mock_record.stellar_account = 'GINVALIDADDRESSNOTFOUNDON404HORIZONAPI123456789012'
        mock_record.network_name = 'public'
        mock_record.horizon_accounts_doc_api_href = None
        
        # Mock the manager to return our test record
        mock_manager_instance = Mock()
        mock_lineage_manager.return_value = mock_manager_instance
        
        # Mock environment helpers
        mock_env_instance = Mock()
        mock_env_instance.get_base_horizon.return_value = 'https://horizon.stellar.org'
        mock_env_helpers.return_value = mock_env_instance
        
        # Mock Horizon API to raise NotFoundError (404)
        mock_horizon_instance = Mock()
        mock_horizon_instance.get_base_accounts.side_effect = NotFoundError(
            Mock(status_code=404, text='{"type": "https://stellar.org/horizon-errors/not_found"}')
        )
        # These should NOT be called for invalid addresses
        mock_horizon_instance.get_account_operations = Mock()
        mock_horizon_instance.get_account_effects = Mock()
        mock_horizon_helpers.return_value = mock_horizon_instance
        
        # Create command instance and call _process_lineage_record
        command = Command()
        
        # This should detect the 404, mark as invalid, and STOP processing (no operations/effects)
        command._process_lineage_record(
            lin_queryset=mock_record,
            cron_name='test_cron'
        )
        
        # Verify the record was marked as INVALID_HORIZON_STELLAR_ADDRESS
        update_calls = [call for call in mock_manager_instance.update_lineage.call_args_list]
        
        # Should have at least one call to update_lineage
        self.assertGreater(len(update_calls), 0)
        
        # Check if any call set status to INVALID_HORIZON_STELLAR_ADDRESS
        found_invalid_status = False
        for call in update_calls:
            if 'request' in call.kwargs or len(call.args) > 1:
                request_obj = call.kwargs.get('request') if 'request' in call.kwargs else call.args[1]
                if hasattr(request_obj, 'data') and request_obj.data.get('status') == INVALID_HORIZON_STELLAR_ADDRESS:
                    found_invalid_status = True
                    self.assertIn('Horizon API validation failed', request_obj.data.get('last_error', ''))
                    break
        
        self.assertTrue(found_invalid_status, "Record should have been marked as INVALID_HORIZON_STELLAR_ADDRESS")
        
        # CRITICAL: Verify operations and effects were NOT called
        mock_horizon_instance.get_account_operations.assert_not_called()
        mock_horizon_instance.get_account_effects.assert_not_called()
    
    @patch('apiApp.management.commands.cron_collect_account_horizon_data.StellarMapHorizonAPIHelpers')
    @patch('apiApp.management.commands.cron_collect_account_horizon_data.StellarCreatorAccountLineageManager')
    @patch('apiApp.management.commands.cron_collect_account_horizon_data.AstraDocument')
    def test_valid_address_continues_normally(
        self, mock_astra, mock_lineage_manager, mock_horizon_helpers
    ):
        """Test that a valid address from Horizon continues processing normally."""
        from apiApp.management.commands.cron_collect_account_horizon_data import Command
        from apiApp.models import DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS
        
        # Create mock lineage record
        mock_record = Mock()
        mock_record.id = 'test-id-456'
        mock_record.stellar_account = 'GVALIDADDRESSTHISISFOUNDONHORIZONAPI1234567890123'
        mock_record.network_name = 'public'
        mock_record.horizon_accounts_doc_api_href = None
        
        # Mock the manager
        mock_manager_instance = Mock()
        mock_lineage_manager.return_value = mock_manager_instance
        
        # Mock Horizon API to return valid account data
        mock_horizon_instance = Mock()
        mock_horizon_instance.get_base_accounts.return_value = {
            'id': mock_record.stellar_account,
            'account_id': mock_record.stellar_account,
            'sequence': '123456789',
            'balances': []
        }
        mock_horizon_helpers.return_value = mock_horizon_instance
        
        # Mock AstraDocument
        mock_astra_instance = Mock()
        mock_astra_instance.patch_document.return_value = {'href': 'https://astra.example.com/doc/123'}
        mock_astra.return_value = mock_astra_instance
        
        # Create command instance
        command = Command()
        
        # Call _fetch_and_store_accounts - should succeed
        command._fetch_and_store_accounts(
            lineage_manager=mock_manager_instance,
            lin_queryset=mock_record,
            horizon_url='https://horizon.stellar.org',
            account_id=mock_record.stellar_account,
            network_name=mock_record.network_name,
            cron_name='test_cron'
        )
        
        # Verify the record was marked as DONE (not INVALID)
        update_calls = [call for call in mock_manager_instance.update_lineage.call_args_list]
        
        # Should have calls to update_lineage
        self.assertGreater(len(update_calls), 0)
        
        # Check that status was set to DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS
        found_done_status = False
        for call in update_calls:
            if 'request' in call.kwargs or len(call.args) > 1:
                request_obj = call.kwargs.get('request') if 'request' in call.kwargs else call.args[1]
                if hasattr(request_obj, 'data') and request_obj.data.get('status') == DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS:
                    found_done_status = True
                    break
        
        self.assertTrue(found_done_status, "Valid address should have been marked as DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS")


class InvalidAddressExclusionTestCase(TestCase):
    """Test that invalid addresses are excluded from pipeline processing."""
    
    def test_invalid_status_not_in_pending_api(self):
        """Verify INVALID_HORIZON_STELLAR_ADDRESS is not included in pending accounts API."""
        from apiApp.views import pending_accounts_api
        from apiApp.models import INVALID_HORIZON_STELLAR_ADDRESS
        
        # The pending_accounts_api view should not query for INVALID_HORIZON_STELLAR_ADDRESS status
        # This is verified by checking the source code statically - the status is not in the lists
        
        # This is a compile-time check rather than runtime
        import inspect
        source = inspect.getsource(pending_accounts_api)
        
        # Verify INVALID_HORIZON_STELLAR_ADDRESS is NOT imported or used in the pending API
        self.assertNotIn('INVALID_HORIZON_STELLAR_ADDRESS', source, 
                        "pending_accounts_api should not query INVALID_HORIZON_STELLAR_ADDRESS status")
    
    def test_stuck_records_imports_invalid_status(self):
        """Verify stuck_records helper imports INVALID_HORIZON_STELLAR_ADDRESS to handle exclusion."""
        from apiApp.helpers import stuck_records
        
        # Verify the module has access to the constant (for future exclusion logic if needed)
        self.assertTrue(hasattr(stuck_records, 'INVALID_HORIZON_STELLAR_ADDRESS'),
                       "stuck_records should import INVALID_HORIZON_STELLAR_ADDRESS constant")
