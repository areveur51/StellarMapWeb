"""
Tests for Account Lineage data retrieval and display functionality.

This test suite ensures:
1. Robust data retrieval from all pipeline stages
2. Correct lineage chain following
3. Proper view context preparation
4. Accurate table display data
"""

from django.test import TestCase, RequestFactory
from django.urls import reverse
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

from apiApp.models import (
    StellarCreatorAccountLineage,
    PENDING_HORIZON_API_DATASETS,
    FAILED,
)

# Define status constants for tests
COMPLETED_SUCCESS = 'COMPLETED_SUCCESS'
from webApp.views import search_view


class AccountLineageDataRetrievalTests(TestCase):
    """Test data retrieval from StellarCreatorAccountLineage model."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.test_account = 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB'
        self.test_network = 'public'

    @patch('webApp.views.StellarCreatorAccountLineage')
    def test_lineage_data_retrieval_with_complete_data(self, mock_lineage_model):
        """Test retrieving lineage data when all fields are populated."""
        # Create mock lineage record with all fields
        mock_record = Mock()
        mock_record.stellar_account = self.test_account
        mock_record.stellar_creator_account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        mock_record.network_name = self.test_network
        mock_record.stellar_account_created_at = datetime(2024, 1, 15, 10, 30, 0)
        mock_record.home_domain = 'example.com'
        mock_record.xlm_balance = 1250.5
        mock_record.horizon_accounts_doc_api_href = 'https://horizon.stellar.org/accounts/test'
        mock_record.status = COMPLETED_SUCCESS
        mock_record.created_at = datetime(2024, 1, 15, 10, 0, 0)
        mock_record.updated_at = datetime(2024, 1, 15, 10, 35, 0)

        # Mock the query chain
        mock_query = Mock()
        mock_query.all.return_value = [mock_record]
        mock_filter = Mock()
        mock_filter.all.return_value = [mock_record]
        mock_lineage_model.objects.filter.return_value = mock_filter

        # Make request
        request = self.factory.get(
            reverse('search'),
            {'account': self.test_account, 'network': self.test_network}
        )

        with patch('webApp.views.StellarMapValidatorHelpers') as mock_validator, \
             patch('webApp.views.StellarMapCacheHelpers') as mock_cache, \
             patch('webApp.views.initialize_stage_executions'):
            
            mock_validator_instance = Mock()
            mock_validator_instance.validate_stellar_account_address.return_value = True
            mock_validator.return_value = mock_validator_instance

            mock_cache_instance = Mock()
            mock_cache_instance.check_cache_freshness.return_value = (True, None)
            mock_cache_instance.get_cached_data.return_value = {'name': 'test'}
            mock_cache.return_value = mock_cache_instance

            response = search_view(request)

        # Verify response
        self.assertEqual(response.status_code, 200)

    @patch('webApp.views.StellarCreatorAccountLineage')
    def test_lineage_data_with_missing_optional_fields(self, mock_lineage_model):
        """Test retrieving lineage data when optional fields are None."""
        mock_record = Mock()
        mock_record.stellar_account = self.test_account
        mock_record.stellar_creator_account = None  # Optional field
        mock_record.network_name = self.test_network
        mock_record.stellar_account_created_at = None  # Optional field
        mock_record.home_domain = None  # Optional field
        mock_record.xlm_balance = 0.0
        mock_record.horizon_accounts_doc_api_href = None  # Optional field
        mock_record.status = PENDING_HORIZON_API_DATASETS
        mock_record.created_at = datetime(2024, 1, 15, 10, 0, 0)
        mock_record.updated_at = datetime(2024, 1, 15, 10, 35, 0)

        mock_filter = Mock()
        mock_filter.all.return_value = [mock_record]
        mock_lineage_model.objects.filter.return_value = mock_filter

        request = self.factory.get(
            reverse('search'),
            {'account': self.test_account, 'network': self.test_network}
        )

        with patch('webApp.views.StellarMapValidatorHelpers') as mock_validator, \
             patch('webApp.views.StellarMapCacheHelpers') as mock_cache, \
             patch('webApp.views.initialize_stage_executions'):
            
            mock_validator_instance = Mock()
            mock_validator_instance.validate_stellar_account_address.return_value = True
            mock_validator.return_value = mock_validator_instance

            mock_cache_instance = Mock()
            mock_cache_instance.check_cache_freshness.return_value = (True, None)
            mock_cache_instance.get_cached_data.return_value = {'name': 'test'}
            mock_cache.return_value = mock_cache_instance

            response = search_view(request)

        self.assertEqual(response.status_code, 200)


class LineageChainFollowingTests(TestCase):
    """Test following the creator account lineage chain."""

    def setUp(self):
        """Set up test fixtures with multi-level lineage."""
        self.factory = RequestFactory()
        self.child_account = 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA1'
        self.parent_account = 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA2'
        self.grandparent_account = 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA3'
        self.test_network = 'public'

    @patch('webApp.views.StellarCreatorAccountLineage')
    def test_follows_complete_lineage_chain(self, mock_lineage_model):
        """Test that the view follows the entire lineage chain."""
        # Create three-level lineage: child -> parent -> grandparent
        child_record = Mock()
        child_record.stellar_account = self.child_account
        child_record.stellar_creator_account = self.parent_account
        child_record.network_name = self.test_network
        child_record.xlm_balance = 100.0
        child_record.status = COMPLETED_SUCCESS
        child_record.stellar_account_created_at = datetime(2024, 1, 15)
        child_record.home_domain = 'child.com'
        child_record.horizon_accounts_doc_api_href = 'https://horizon.stellar.org/child'
        child_record.created_at = datetime(2024, 1, 15)
        child_record.updated_at = datetime(2024, 1, 15)

        parent_record = Mock()
        parent_record.stellar_account = self.parent_account
        parent_record.stellar_creator_account = self.grandparent_account
        parent_record.network_name = self.test_network
        parent_record.xlm_balance = 500.0
        parent_record.status = COMPLETED_SUCCESS
        parent_record.stellar_account_created_at = datetime(2024, 1, 10)
        parent_record.home_domain = 'parent.com'
        parent_record.horizon_accounts_doc_api_href = 'https://horizon.stellar.org/parent'
        parent_record.created_at = datetime(2024, 1, 10)
        parent_record.updated_at = datetime(2024, 1, 10)

        grandparent_record = Mock()
        grandparent_record.stellar_account = self.grandparent_account
        grandparent_record.stellar_creator_account = None  # Origin account
        grandparent_record.network_name = self.test_network
        grandparent_record.xlm_balance = 1000.0
        grandparent_record.status = COMPLETED_SUCCESS
        grandparent_record.stellar_account_created_at = datetime(2024, 1, 1)
        grandparent_record.home_domain = 'grandparent.com'
        grandparent_record.horizon_accounts_doc_api_href = 'https://horizon.stellar.org/grandparent'
        grandparent_record.created_at = datetime(2024, 1, 1)
        grandparent_record.updated_at = datetime(2024, 1, 1)

        # Mock filter to return appropriate records for each account
        def filter_side_effect(*args, **kwargs):
            account = kwargs.get('stellar_account')
            mock_result = Mock()
            
            if account == self.child_account:
                mock_result.all.return_value = [child_record]
            elif account == self.parent_account:
                mock_result.all.return_value = [parent_record]
            elif account == self.grandparent_account:
                mock_result.all.return_value = [grandparent_record]
            else:
                mock_result.all.return_value = []
            
            return mock_result

        mock_lineage_model.objects.filter.side_effect = filter_side_effect

        request = self.factory.get(
            reverse('search'),
            {'account': self.child_account, 'network': self.test_network}
        )

        with patch('webApp.views.StellarMapValidatorHelpers') as mock_validator, \
             patch('webApp.views.StellarMapCacheHelpers') as mock_cache, \
             patch('webApp.views.initialize_stage_executions'):
            
            mock_validator_instance = Mock()
            mock_validator_instance.validate_stellar_account_address.return_value = True
            mock_validator.return_value = mock_validator_instance

            mock_cache_instance = Mock()
            mock_cache_instance.check_cache_freshness.return_value = (True, None)
            mock_cache_instance.get_cached_data.return_value = {'name': 'test'}
            mock_cache.return_value = mock_cache_instance

            response = search_view(request)

        # Verify all three levels were queried
        self.assertGreaterEqual(mock_lineage_model.objects.filter.call_count, 3)
        
    @patch('webApp.views.StellarCreatorAccountLineage')
    def test_prevents_circular_lineage_references(self, mock_lineage_model):
        """Test that circular references don't cause infinite loops."""
        # Create circular reference: A -> B -> A
        account_a = 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA1'
        account_b = 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA2'

        record_a = Mock()
        record_a.stellar_account = account_a
        record_a.stellar_creator_account = account_b
        record_a.network_name = self.test_network
        record_a.xlm_balance = 100.0
        record_a.status = COMPLETED_SUCCESS
        record_a.stellar_account_created_at = datetime(2024, 1, 15)
        record_a.home_domain = None
        record_a.horizon_accounts_doc_api_href = None
        record_a.created_at = datetime(2024, 1, 15)
        record_a.updated_at = datetime(2024, 1, 15)

        record_b = Mock()
        record_b.stellar_account = account_b
        record_b.stellar_creator_account = account_a  # Circular reference!
        record_b.network_name = self.test_network
        record_b.xlm_balance = 200.0
        record_b.status = COMPLETED_SUCCESS
        record_b.stellar_account_created_at = datetime(2024, 1, 10)
        record_b.home_domain = None
        record_b.horizon_accounts_doc_api_href = None
        record_b.created_at = datetime(2024, 1, 10)
        record_b.updated_at = datetime(2024, 1, 10)

        def filter_side_effect(*args, **kwargs):
            account = kwargs.get('stellar_account')
            mock_result = Mock()
            
            if account == account_a:
                mock_result.all.return_value = [record_a]
            elif account == account_b:
                mock_result.all.return_value = [record_b]
            else:
                mock_result.all.return_value = []
            
            return mock_result

        mock_lineage_model.objects.filter.side_effect = filter_side_effect

        request = self.factory.get(
            reverse('search'),
            {'account': account_a, 'network': self.test_network}
        )

        with patch('webApp.views.StellarMapValidatorHelpers') as mock_validator, \
             patch('webApp.views.StellarMapCacheHelpers') as mock_cache, \
             patch('webApp.views.initialize_stage_executions'):
            
            mock_validator_instance = Mock()
            mock_validator_instance.validate_stellar_account_address.return_value = True
            mock_validator.return_value = mock_validator_instance

            mock_cache_instance = Mock()
            mock_cache_instance.check_cache_freshness.return_value = (True, None)
            mock_cache_instance.get_cached_data.return_value = {'name': 'test'}
            mock_cache.return_value = mock_cache_instance

            # Should not hang or raise exception
            response = search_view(request)

        self.assertEqual(response.status_code, 200)


class ViewContextPreparationTests(TestCase):
    """Test that view properly prepares context data for template."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.test_account = 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB'
        self.test_network = 'public'

    @patch('webApp.views.StellarCreatorAccountLineage')
    def test_context_contains_account_lineage_data(self, mock_lineage_model):
        """Test that context includes account_lineage_data key."""
        mock_record = Mock()
        mock_record.stellar_account = self.test_account
        mock_record.stellar_creator_account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        mock_record.network_name = self.test_network
        mock_record.stellar_account_created_at = datetime(2024, 1, 15)
        mock_record.home_domain = 'example.com'
        mock_record.xlm_balance = 1250.5
        mock_record.horizon_accounts_doc_api_href = 'https://horizon.stellar.org/test'
        mock_record.status = COMPLETED_SUCCESS
        mock_record.created_at = datetime(2024, 1, 15)
        mock_record.updated_at = datetime(2024, 1, 15)

        mock_filter = Mock()
        mock_filter.all.return_value = [mock_record]
        mock_lineage_model.objects.filter.return_value = mock_filter

        request = self.factory.get(
            reverse('search'),
            {'account': self.test_account, 'network': self.test_network}
        )

        with patch('webApp.views.StellarMapValidatorHelpers') as mock_validator, \
             patch('webApp.views.StellarMapCacheHelpers') as mock_cache, \
             patch('webApp.views.initialize_stage_executions'), \
             patch('webApp.views.render') as mock_render:
            
            mock_validator_instance = Mock()
            mock_validator_instance.validate_stellar_account_address.return_value = True
            mock_validator.return_value = mock_validator_instance

            mock_cache_instance = Mock()
            mock_cache_instance.check_cache_freshness.return_value = (True, None)
            mock_cache_instance.get_cached_data.return_value = {'name': 'test'}
            mock_cache.return_value = mock_cache_instance

            mock_response = Mock()
            mock_response.status_code = 200
            mock_render.return_value = mock_response

            search_view(request)

            # Verify render was called with context containing account_lineage_data
            self.assertTrue(mock_render.called)
            call_args = mock_render.call_args
            context = call_args[0][2]  # Third argument is context
            
            self.assertIn('account_lineage_data', context)
            self.assertIsInstance(context['account_lineage_data'], list)

    @patch('webApp.views.StellarCreatorAccountLineage')
    def test_context_data_structure_matches_template_expectations(self, mock_lineage_model):
        """Test that each lineage record has all expected fields."""
        mock_record = Mock()
        mock_record.stellar_account = self.test_account
        mock_record.stellar_creator_account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        mock_record.network_name = self.test_network
        mock_record.stellar_account_created_at = datetime(2024, 1, 15, 10, 30, 0)
        mock_record.home_domain = 'example.com'
        mock_record.xlm_balance = 1250.5
        mock_record.horizon_accounts_doc_api_href = 'https://horizon.stellar.org/test'
        mock_record.status = COMPLETED_SUCCESS
        mock_record.created_at = datetime(2024, 1, 15, 10, 0, 0)
        mock_record.updated_at = datetime(2024, 1, 15, 10, 35, 0)

        mock_filter = Mock()
        mock_filter.all.return_value = [mock_record]
        mock_lineage_model.objects.filter.return_value = mock_filter

        request = self.factory.get(
            reverse('search'),
            {'account': self.test_account, 'network': self.test_network}
        )

        with patch('webApp.views.StellarMapValidatorHelpers') as mock_validator, \
             patch('webApp.views.StellarMapCacheHelpers') as mock_cache, \
             patch('webApp.views.initialize_stage_executions'), \
             patch('webApp.views.render') as mock_render:
            
            mock_validator_instance = Mock()
            mock_validator_instance.validate_stellar_account_address.return_value = True
            mock_validator.return_value = mock_validator_instance

            mock_cache_instance = Mock()
            mock_cache_instance.check_cache_freshness.return_value = (True, None)
            mock_cache_instance.get_cached_data.return_value = {'name': 'test'}
            mock_cache.return_value = mock_cache_instance

            mock_response = Mock()
            mock_response.status_code = 200
            mock_render.return_value = mock_response

            search_view(request)

            context = mock_render.call_args[0][2]
            lineage_data = context['account_lineage_data']
            
            # Verify at least one record
            self.assertGreater(len(lineage_data), 0)
            
            # Verify required fields in first record
            first_record = lineage_data[0]
            required_fields = [
                'stellar_account',
                'stellar_creator_account',
                'network_name',
                'xlm_balance',
                'status',
            ]
            for field in required_fields:
                self.assertIn(field, first_record)


class TemplateDataDisplayTests(TestCase):
    """Test that template correctly displays lineage data in table."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.test_account = 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB'
        self.test_network = 'public'

    @patch('webApp.views.StellarCreatorAccountLineage')
    def test_template_renders_account_lineage_data(self, mock_lineage_model):
        """Test that template includes account_lineage_data in JSON script."""
        mock_record = Mock()
        mock_record.stellar_account = self.test_account
        mock_record.stellar_creator_account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        mock_record.network_name = self.test_network
        mock_record.stellar_account_created_at = datetime(2024, 1, 15)
        mock_record.home_domain = 'example.com'
        mock_record.xlm_balance = 1250.5
        mock_record.horizon_accounts_doc_api_href = 'https://horizon.stellar.org/test'
        mock_record.status = COMPLETED_SUCCESS
        mock_record.created_at = datetime(2024, 1, 15)
        mock_record.updated_at = datetime(2024, 1, 15)

        mock_filter = Mock()
        mock_filter.all.return_value = [mock_record]
        mock_lineage_model.objects.filter.return_value = mock_filter

        request = self.factory.get(
            reverse('search'),
            {'account': self.test_account, 'network': self.test_network}
        )

        with patch('webApp.views.StellarMapValidatorHelpers') as mock_validator, \
             patch('webApp.views.StellarMapCacheHelpers') as mock_cache, \
             patch('webApp.views.initialize_stage_executions'):
            
            mock_validator_instance = Mock()
            mock_validator_instance.validate_stellar_account_address.return_value = True
            mock_validator.return_value = mock_validator_instance

            mock_cache_instance = Mock()
            mock_cache_instance.check_cache_freshness.return_value = (True, None)
            mock_cache_instance.get_cached_data.return_value = {'name': 'test'}
            mock_cache.return_value = mock_cache_instance

            response = search_view(request)

        # Decode response content
        content = response.content.decode('utf-8')
        
        # Verify account-lineage-json script tag exists
        self.assertIn('id="account-lineage-json"', content)
        
        # Verify Account Lineage tab exists and is first
        self.assertIn('title="Account Lineage"', content)
        self.assertIn('active', content)  # First tab should be active

    def test_empty_lineage_data_shows_appropriate_message(self):
        """Test that empty lineage data shows user-friendly message."""
        request = self.factory.get(
            reverse('search'),
            {'account': self.test_account, 'network': self.test_network}
        )

        with patch('webApp.views.StellarMapValidatorHelpers') as mock_validator, \
             patch('webApp.views.StellarMapCacheHelpers') as mock_cache, \
             patch('webApp.views.StellarCreatorAccountLineage') as mock_lineage, \
             patch('webApp.views.initialize_stage_executions'):
            
            mock_validator_instance = Mock()
            mock_validator_instance.validate_stellar_account_address.return_value = True
            mock_validator.return_value = mock_validator_instance

            mock_cache_instance = Mock()
            mock_cache_instance.check_cache_freshness.return_value = (True, None)
            mock_cache_instance.get_cached_data.return_value = {'name': 'test'}
            mock_cache.return_value = mock_cache_instance

            # Mock empty lineage
            mock_filter = Mock()
            mock_filter.all.return_value = []
            mock_lineage.objects.filter.return_value = mock_filter

            response = search_view(request)

        content = response.content.decode('utf-8')
        
        # Verify empty state message appears
        self.assertIn('No lineage data available', content)
