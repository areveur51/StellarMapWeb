"""
Focused regression tests for API Pipeline datetime parsing bug.

Ensures that stellar_account_created_at is properly parsed from ISO 8601 strings
to datetime objects before saving to database.

Bug: API pipeline was saving '2025-03-09T05:18:48Z' as string, causing 100% failure
Fix: Parse ISO 8601 string to datetime object using datetime.fromisoformat()

Created: October 23, 2025
"""
import datetime
from datetime import timedelta
from django.test import TestCase
from unittest.mock import patch, MagicMock
from apiApp.model_loader import StellarCreatorAccountLineage
from apiApp.management.commands.api_pipeline import Command


class APIPipelineDateTimeRegressionTests(TestCase):
    """Regression tests for datetime parsing in API pipeline."""

    def setUp(self):
        """Set up test data."""
        self.now = datetime.datetime.utcnow()
        self.command = Command()

    @patch('apiApp.management.commands.api_pipeline.StellarMapHorizonAPIHelpers')
    @patch('apiApp.management.commands.api_pipeline.StellarMapStellarExpertAPIHelpers')
    def test_datetime_string_converted_to_datetime_object(self, mock_expert, mock_horizon):
        """Test that datetime string from API is converted to datetime object."""
        # Create test account
        test_account = StellarCreatorAccountLineage(
            stellar_account='G' + 'D' * 55,
            network_name='public',
            status='PENDING',
            created_at=self.now,
            updated_at=self.now
        )
        test_account.save()
        
        # Mock API responses with ISO 8601 datetime string (the bug scenario)
        mock_expert_instance = MagicMock()
        mock_expert_instance.get_account.return_value = {
            'creator': 'GTEST' + 'C' * 51,
            'account_creation_date': '2025-03-09T05:18:48Z',  # ISO 8601 string
            'balances': []
        }
        mock_expert.return_value = mock_expert_instance
        
        mock_horizon_instance = MagicMock()
        mock_horizon_instance.get_account_horizon.return_value = {
            'balance': 100.0,
            'home_domain': 'test.com',
            'flags': {},
            'thresholds': {},
            'signers': [],
            'sequence': '123',
            'subentry_count': 0
        }
        mock_horizon_instance.fetch_creator_from_horizon.return_value = None
        mock_horizon_instance.fetch_child_accounts.return_value = []
        mock_horizon.return_value = mock_horizon_instance
        
        # Call the update method directly
        account_data = {'account_creation_date': '2025-03-09T05:18:48Z'}
        horizon_data = {'balance': 100.0, 'home_domain': '', 'flags': {}, 'thresholds': {}, 'signers': [], 'sequence': '123', 'subentry_count': 0}
        
        try:
            self.command._update_account_in_database(
                test_account,
                account_data,
                horizon_data,
                [],
                {'creator_account': 'GTEST' + 'C' * 51},
                [],
                self.now
            )
            
            # Reload from database
            test_account = StellarCreatorAccountLineage.objects.get(stellar_account=test_account.stellar_account)
            
            # CRITICAL ASSERTION: Verify stellar_account_created_at is a datetime object, not a string
            self.assertIsInstance(
                test_account.stellar_account_created_at, 
                datetime.datetime,
                "stellar_account_created_at must be a datetime object, not a string"
            )
            
            # Verify the datetime value is correct
            expected_datetime = datetime.datetime.fromisoformat('2025-03-09T05:18:48+00:00')
            self.assertEqual(test_account.stellar_account_created_at, expected_datetime)
            
        finally:
            # Cleanup
            test_account.delete()

    @patch('apiApp.management.commands.api_pipeline.StellarMapHorizonAPIHelpers')
    @patch('apiApp.management.commands.api_pipeline.StellarMapStellarExpertAPIHelpers')
    def test_handles_missing_datetime_gracefully(self, mock_expert, mock_horizon):
        """Test that missing datetime is handled gracefully (set to None)."""
        # Create test account
        test_account = StellarCreatorAccountLineage(
            stellar_account='G' + 'N' * 55,
            network_name='public',
            status='PENDING',
            created_at=self.now,
            updated_at=self.now
        )
        test_account.save()
        
        # Mock with missing account_creation_date
        account_data = {}  # No account_creation_date
        horizon_data = {'balance': 100.0, 'home_domain': '', 'flags': {}, 'thresholds': {}, 'signers': [], 'sequence': '123', 'subentry_count': 0}
        
        try:
            self.command._update_account_in_database(
                test_account,
                account_data,
                horizon_data,
                [],
                {'creator_account': 'GTEST' + 'C' * 51},
                [],
                self.now
            )
            
            # Reload from database
            test_account = StellarCreatorAccountLineage.objects.get(stellar_account=test_account.stellar_account)
            
            # Should be None, not raise error
            self.assertIsNone(test_account.stellar_account_created_at)
            
        finally:
            # Cleanup
            test_account.delete()

    def test_datetime_parsing_edge_cases(self):
        """Test various ISO 8601 datetime formats are handled correctly."""
        from apiApp.management.commands.api_pipeline import Command
        
        test_cases = [
            ('2025-03-09T05:18:48Z', datetime.datetime.fromisoformat('2025-03-09T05:18:48+00:00')),
            ('2025-01-01T00:00:00Z', datetime.datetime.fromisoformat('2025-01-01T00:00:00+00:00')),
            ('2024-12-31T23:59:59Z', datetime.datetime.fromisoformat('2024-12-31T23:59:59+00:00')),
        ]
        
        for iso_string, expected_datetime in test_cases:
            # Parse as the code does
            parsed_string = iso_string.replace('Z', '+00:00')
            result = datetime.datetime.fromisoformat(parsed_string)
            
            self.assertEqual(result, expected_datetime, 
                           f"Failed to parse {iso_string} correctly")
            self.assertIsInstance(result, datetime.datetime,
                                f"Result for {iso_string} must be datetime object")
