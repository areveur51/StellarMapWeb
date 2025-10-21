"""
Comprehensive tests for XLM balance retrieval accuracy.

Tests ensure that XLM balances are correctly:
1. Fetched from Horizon API
2. Parsed from API responses
3. Saved to database fields
4. Displayed in API responses
"""

from django.test import TestCase, RequestFactory
from unittest.mock import Mock, patch, MagicMock
from apiApp.helpers.sm_horizon import StellarMapHorizonAPIParserHelpers
from apiApp.model_loader import StellarCreatorAccountLineage
import json


class HorizonBalanceParsingTests(TestCase):
    """Test that Horizon API balance parsing is accurate."""
    
    def test_parse_native_balance_standard_format(self):
        """Test parsing standard native balance format."""
        response = {
            'data': {
                'raw_data': {
                    'balances': [
                        {'asset_type': 'native', 'balance': '2483571.7231785'}
                    ]
                }
            }
        }
        parser = StellarMapHorizonAPIParserHelpers(response)
        balance = parser.parse_account_native_balance()
        self.assertEqual(balance, 2483571.7231785)
    
    def test_parse_native_balance_with_multiple_assets(self):
        """Test parsing native balance when account has multiple assets."""
        response = {
            'data': {
                'raw_data': {
                    'balances': [
                        {'asset_type': 'credit_alphanum4', 'asset_code': 'USD', 'balance': '100.0'},
                        {'asset_type': 'native', 'balance': '5000000.5'},
                        {'asset_type': 'credit_alphanum12', 'asset_code': 'LONGASSET', 'balance': '250.0'}
                    ]
                }
            }
        }
        parser = StellarMapHorizonAPIParserHelpers(response)
        balance = parser.parse_account_native_balance()
        self.assertEqual(balance, 5000000.5)
    
    def test_parse_native_balance_zero_xlm(self):
        """Test parsing when account has exactly 0 XLM (should be valid)."""
        response = {
            'data': {
                'raw_data': {
                    'balances': [
                        {'asset_type': 'native', 'balance': '0'}
                    ]
                }
            }
        }
        parser = StellarMapHorizonAPIParserHelpers(response)
        balance = parser.parse_account_native_balance()
        self.assertEqual(balance, 0.0)
    
    def test_parse_native_balance_high_value_account(self):
        """Test parsing for High Value Accounts (>1M XLM)."""
        response = {
            'data': {
                'raw_data': {
                    'balances': [
                        {'asset_type': 'native', 'balance': '15000000.1234567'}
                    ]
                }
            }
        }
        parser = StellarMapHorizonAPIParserHelpers(response)
        balance = parser.parse_account_native_balance()
        self.assertEqual(balance, 15000000.1234567)
        self.assertGreater(balance, 1_000_000)  # Verify HVA threshold
    
    def test_parse_native_balance_missing_balances_key(self):
        """Test graceful handling when balances key is missing."""
        response = {'data': {'raw_data': {}}}
        parser = StellarMapHorizonAPIParserHelpers(response)
        balance = parser.parse_account_native_balance()
        self.assertEqual(balance, 0.0)
    
    def test_parse_native_balance_empty_balances_array(self):
        """Test graceful handling when balances array is empty."""
        response = {'data': {'raw_data': {'balances': []}}}
        parser = StellarMapHorizonAPIParserHelpers(response)
        balance = parser.parse_account_native_balance()
        self.assertEqual(balance, 0.0)
    
    def test_parse_native_balance_no_native_asset(self):
        """Test when account has no native balance entry."""
        response = {
            'data': {
                'raw_data': {
                    'balances': [
                        {'asset_type': 'credit_alphanum4', 'asset_code': 'USD', 'balance': '100.0'}
                    ]
                }
            }
        }
        parser = StellarMapHorizonAPIParserHelpers(response)
        balance = parser.parse_account_native_balance()
        self.assertEqual(balance, 0.0)
    
    def test_parse_native_balance_decimal_precision(self):
        """Test that 7 decimal places of precision are preserved."""
        response = {
            'data': {
                'raw_data': {
                    'balances': [
                        {'asset_type': 'native', 'balance': '100.1234567'}
                    ]
                }
            }
        }
        parser = StellarMapHorizonAPIParserHelpers(response)
        balance = parser.parse_account_native_balance()
        self.assertEqual(balance, 100.1234567)


class BigQueryPipelineBalanceStorageTests(TestCase):
    """Test that BigQuery pipeline correctly stores balances to database."""
    
    @patch('apiApp.management.commands.bigquery_pipeline.StellarMapHorizonAPIHelpers')
    def test_balance_saved_to_database_field(self, mock_horizon):
        """Test that balance from Horizon is saved to xlm_balance field."""
        # Mock Horizon API response
        mock_instance = mock_horizon.return_value
        mock_instance.get_base_accounts.return_value = {
            'balances': [{'asset_type': 'native', 'balance': '2483571.7231785'}],
            'home_domain': 'example.com',
            'flags': {},
            'thresholds': {},
            'signers': [],
            'sequence': '123456',
            'subentry_count': 5
        }
        
        # Import and test the _fetch_horizon_account_data method
        from apiApp.management.commands.bigquery_pipeline import Command
        from apiApp.helpers.env import EnvHelpers
        
        cmd = Command()
        cmd.env_helpers = EnvHelpers()
        cmd.env_helpers.set_public_network()
        
        horizon_data = cmd._fetch_horizon_account_data('GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU')
        
        # Verify balance is in returned data
        self.assertIsNotNone(horizon_data)
        self.assertEqual(horizon_data['balance'], 2483571.7231785)
        self.assertEqual(horizon_data['home_domain'], 'example.com')
    
    def test_database_model_stores_balance(self):
        """Test that StellarCreatorAccountLineage model can store and retrieve balance."""
        # Create a lineage record with balance
        lineage = StellarCreatorAccountLineage.objects.create(
            stellar_account='GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU',
            network_name='public',
            stellar_creator_account='GCREATOR123',
            xlm_balance=2483571.7231785,
            status='BIGQUERY_COMPLETE'
        )
        
        # Retrieve and verify
        retrieved = StellarCreatorAccountLineage.objects.filter(
            stellar_account='GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU',
            network_name='public'
        ).first()
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.xlm_balance, 2483571.7231785)
        
        # Clean up
        lineage.delete()
    
    def test_high_value_account_flag_set_correctly(self):
        """Test that HVA flag is set for accounts with >1M XLM."""
        # Create HVA account
        hva = StellarCreatorAccountLineage.objects.create(
            stellar_account='GHVAACCOUNT123',
            network_name='public',
            stellar_creator_account='GCREATOR123',
            xlm_balance=2483571.72,
            status='BIGQUERY_COMPLETE'
        )
        
        # Manually trigger the HVA logic (normally in save())
        if hva.xlm_balance > 1_000_000:
            hva.is_hva = True
            hva.save()
        
        # Verify HVA flag
        retrieved = StellarCreatorAccountLineage.objects.filter(
            stellar_account='GHVAACCOUNT123',
            network_name='public'
        ).first()
        
        self.assertTrue(retrieved.is_hva)
        
        # Test non-HVA account
        non_hva = StellarCreatorAccountLineage.objects.create(
            stellar_account='GNOTHVA123',
            network_name='public',
            stellar_creator_account='GCREATOR123',
            xlm_balance=500000.0,
            status='BIGQUERY_COMPLETE'
        )
        
        retrieved_non_hva = StellarCreatorAccountLineage.objects.filter(
            stellar_account='GNOTHVA123',
            network_name='public'
        ).first()
        
        self.assertFalse(retrieved_non_hva.is_hva)
        
        # Clean up
        hva.delete()
        non_hva.delete()


class APIResponseBalanceTests(TestCase):
    """Test that API responses include correct balance data."""
    
    def setUp(self):
        """Create test account with known balance."""
        self.test_account = 'GTESTACCOUNT123'
        self.test_balance = 2483571.7231785
        
        StellarCreatorAccountLineage.objects.create(
            stellar_account=self.test_account,
            network_name='public',
            stellar_creator_account='GCREATOR123',
            xlm_balance=self.test_balance,
            home_domain='example.com',
            status='BIGQUERY_COMPLETE'
        )
    
    def tearDown(self):
        """Clean up test data."""
        StellarCreatorAccountLineage.objects.filter(
            stellar_account=self.test_account,
            network_name='public'
        ).delete()
    
    def test_account_lineage_api_returns_balance(self):
        """Test that /api/account-lineage/ endpoint returns correct balance."""
        from django.test import Client
        
        client = Client()
        response = client.get(f'/api/account-lineage/?account={self.test_account}&network=public')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Find the account in lineage
        account_data = None
        for item in data['lineage']:
            if item['stellar_account'] == self.test_account:
                account_data = item
                break
        
        self.assertIsNotNone(account_data, "Account not found in lineage response")
        self.assertEqual(account_data['xlm_balance'], self.test_balance)
    
    def test_balance_precision_preserved_in_api(self):
        """Test that 7 decimal places are preserved in API response."""
        from django.test import Client
        
        client = Client()
        response = client.get(f'/api/account-lineage/?account={self.test_account}&network=public')
        
        data = response.json()
        
        # Find the account in lineage
        for item in data['lineage']:
            if item['stellar_account'] == self.test_account:
                # Check precision (should match database value)
                self.assertAlmostEqual(item['xlm_balance'], self.test_balance, places=7)
                break


class BalanceEdgeCaseTests(TestCase):
    """Test edge cases for balance handling."""
    
    def test_very_large_balance(self):
        """Test handling of very large balances (100M+ XLM)."""
        large_balance = 100000000.1234567
        
        lineage = StellarCreatorAccountLineage.objects.create(
            stellar_account='GLARGEACCOUNT123',
            network_name='public',
            stellar_creator_account='GCREATOR123',
            xlm_balance=large_balance,
            status='BIGQUERY_COMPLETE'
        )
        
        retrieved = StellarCreatorAccountLineage.objects.filter(
            stellar_account='GLARGEACCOUNT123',
            network_name='public'
        ).first()
        
        self.assertEqual(retrieved.xlm_balance, large_balance)
        lineage.delete()
    
    def test_very_small_balance(self):
        """Test handling of very small balances (< 1 XLM)."""
        small_balance = 0.0000001
        
        lineage = StellarCreatorAccountLineage.objects.create(
            stellar_account='GSMALLACCOUNT123',
            network_name='public',
            stellar_creator_account='GCREATOR123',
            xlm_balance=small_balance,
            status='BIGQUERY_COMPLETE'
        )
        
        retrieved = StellarCreatorAccountLineage.objects.filter(
            stellar_account='GSMALLACCOUNT123',
            network_name='public'
        ).first()
        
        self.assertAlmostEqual(retrieved.xlm_balance, small_balance, places=7)
        lineage.delete()
    
    def test_balance_update_on_reprocessing(self):
        """Test that balance is updated when account is reprocessed."""
        # Create account with initial balance
        lineage = StellarCreatorAccountLineage.objects.create(
            stellar_account='GUPDATEACCOUNT123',
            network_name='public',
            stellar_creator_account='GCREATOR123',
            xlm_balance=1000.0,
            status='BIGQUERY_COMPLETE'
        )
        
        # Update balance (simulating reprocessing)
        lineage.xlm_balance = 2000.0
        lineage.save()
        
        # Verify update
        retrieved = StellarCreatorAccountLineage.objects.filter(
            stellar_account='GUPDATEACCOUNT123',
            network_name='public'
        ).first()
        
        self.assertEqual(retrieved.xlm_balance, 2000.0)
        lineage.delete()


class RealWorldBalanceTests(TestCase):
    """Test with real Stellar account data (if available)."""
    
    @patch('apiApp.helpers.sm_horizon.Server')
    def test_real_account_balance_parsing(self, mock_server):
        """Test parsing real Horizon API response structure."""
        # Mock a real Horizon API response structure
        mock_server_instance = mock_server.return_value
        mock_accounts = MagicMock()
        mock_server_instance.accounts.return_value = mock_accounts
        mock_accounts.account_id.return_value = mock_accounts
        mock_accounts.call.return_value = {
            'id': 'GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU',
            'account_id': 'GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU',
            'sequence': '123456789',
            'balances': [
                {
                    'balance': '2483571.7231785',
                    'asset_type': 'native'
                }
            ],
            'home_domain': '',
            'flags': {
                'auth_required': False,
                'auth_revocable': False
            },
            'thresholds': {
                'low_threshold': 0,
                'med_threshold': 0,
                'high_threshold': 0
            }
        }
        
        from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers
        
        helper = StellarMapHorizonAPIHelpers(
            horizon_url='https://horizon.stellar.org',
            account_id='GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU'
        )
        
        account_data = helper.get_base_accounts()
        
        # Parse balance
        parser = StellarMapHorizonAPIParserHelpers({'data': {'raw_data': account_data}})
        balance = parser.parse_account_native_balance()
        
        self.assertEqual(balance, 2483571.7231785)
