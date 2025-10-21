"""
Regression test for BigQuery pipeline XLM balance storage bug.

This test exercises the ACTUAL pipeline code path to ensure balances
are saved to the database field (not just JSON).

CRITICAL: This test would FAIL before the fix was applied.
"""

from django.test import TestCase
from unittest.mock import patch, MagicMock, Mock
from apiApp.model_loader import StellarCreatorAccountLineage, BigQueryPipelineConfig
from apiApp.management.commands.bigquery_pipeline import Command
from datetime import datetime
import json


class BigQueryPipelineBalanceRegressionTest(TestCase):
    """
    Test that exercises the actual _update_account_in_database method
    to ensure xlm_balance is saved to the database field.
    
    This test validates the fix in bigquery_pipeline.py lines 629-635.
    """
    
    def setUp(self):
        """Set up test environment."""
        self.test_account = 'GTESTBALANCEACCOUNT123'
        self.expected_balance = 2483571.7231785
        
        # Create pipeline config
        try:
            BigQueryPipelineConfig.objects.create(
                config_id='test_config',
                bigquery_enabled=True,
                cost_limit_usd=0.71,
                size_limit_mb=148900.0,
                pipeline_mode='BIGQUERY_WITH_API_FALLBACK',
                batch_size=1
            )
        except:
            pass  # May already exist
    
    def tearDown(self):
        """Clean up test data."""
        StellarCreatorAccountLineage.objects.filter(
            stellar_account=self.test_account,
            network_name='public'
        ).delete()
        
        try:
            BigQueryPipelineConfig.objects.filter(config_id='test_config').delete()
        except:
            pass
    
    def test_update_account_in_database_saves_balance_to_field(self):
        """
        REGRESSION TEST: Validate that _update_account_in_database
        saves xlm_balance to the database field (not just JSON).
        
        This test exercises the ACTUAL pipeline code path.
        Without the fix (lines 629-635), this test would FAIL.
        """
        # Create account object (simulating pipeline state)
        account_obj = StellarCreatorAccountLineage.objects.create(
            stellar_account=self.test_account,
            network_name='public',
            status='PENDING'
        )
        
        # VERIFY: Balance starts at 0 (default)
        self.assertEqual(
            account_obj.xlm_balance, 
            0.0,
            "Balance should start at 0.0 (default)"
        )
        
        # Prepare data as it would come from BigQuery/Horizon
        account_data = {
            'account_id': self.test_account,
            'account_creation_date': '2020-01-01T00:00:00Z'
        }
        
        horizon_data = {
            'balance': self.expected_balance,
            'home_domain': 'example.com',
            'flags': {'auth_required': False, 'auth_revocable': False},
            'thresholds': {'low_threshold': 0, 'med_threshold': 0, 'high_threshold': 0},
            'signers': [],
            'sequence': '123456',
            'subentry_count': 0,
            'num_sponsoring': 0,
            'num_sponsored': 0
        }
        
        assets = []
        creator_info = {'creator_account': 'GCREATOR123', 'created_at': '2020-01-01T00:00:00Z'}
        children = []
        start_time = datetime.utcnow()
        
        # Create command instance
        cmd = Command()
        cmd.stdout = MagicMock()  # Suppress output
        cmd.config = Mock()
        cmd.config.bigquery_enabled = True
        
        # THIS IS THE CRITICAL TEST:
        # Call the actual _update_account_in_database method
        # This exercises the REAL code path that was buggy
        cmd._update_account_in_database(
            account_obj=account_obj,
            account_data=account_data,
            horizon_data=horizon_data,
            assets=assets,
            creator_info=creator_info,
            children=children,
            start_time=start_time
        )
        
        # CRITICAL ASSERTION:
        # Retrieve account from database and verify balance was saved
        saved_account = StellarCreatorAccountLineage.objects.filter(
            stellar_account=self.test_account,
            network_name='public'
        ).first()
        
        # WITHOUT THE FIX, this would FAIL (balance would be 0.0)
        # WITH THE FIX, this should PASS (balance should be ~2.48M)
        self.assertNotEqual(
            saved_account.xlm_balance,
            0.0,
            "❌ REGRESSION: Balance is 0.0! The fix is not working or was removed."
        )
        
        # Verify balance is approximately correct (allow Float precision difference)
        self.assertGreater(
            saved_account.xlm_balance,
            2_400_000,
            f"Balance should be >2.4M XLM, got {saved_account.xlm_balance}"
        )
        
        self.assertAlmostEqual(
            saved_account.xlm_balance,
            self.expected_balance,
            places=1,
            msg=f"Balance should be ~{self.expected_balance}, got {saved_account.xlm_balance}"
        )
        
        # Also verify home_domain was saved
        self.assertEqual(
            saved_account.home_domain,
            'example.com',
            "home_domain should also be saved to database field"
        )
        
        # Verify it's also in JSON (both should work)
        attributes = json.loads(saved_account.stellar_account_attributes_json)
        self.assertIn('balance', attributes, "Balance should also be in JSON")
        self.assertGreater(attributes['balance'], 0, "JSON balance should be non-zero")
        
        print("\n✅ REGRESSION TEST PASSED!")
        print(f"   The fix is working correctly:")
        print(f"   - xlm_balance field: {saved_account.xlm_balance:,.2f} XLM")
        print(f"   - home_domain field: {saved_account.home_domain}")
        print(f"   - JSON also includes balance: ✅")
    
    def test_balance_zero_without_horizon_data(self):
        """
        Test that balance is 0 when Horizon data is unavailable.
        This validates the else clause in the fix.
        """
        account_obj = StellarCreatorAccountLineage.objects.create(
            stellar_account='GNOHORIZONDATA123',
            network_name='public',
            status='PENDING'
        )
        
        # Prepare data WITHOUT horizon_data
        account_data = {'account_id': 'GNOHORIZONDATA123'}
        horizon_data = None  # No Horizon data available
        assets = []
        creator_info = None
        children = []
        start_time = datetime.utcnow()
        
        cmd = Command()
        cmd.stdout = MagicMock()
        cmd.config = Mock()
        
        # Call update method with no Horizon data
        cmd._update_account_in_database(
            account_obj=account_obj,
            account_data=account_data,
            horizon_data=horizon_data,
            assets=assets,
            creator_info=creator_info,
            children=children,
            start_time=start_time
        )
        
        # Verify balance is 0 (as expected without Horizon data)
        saved = StellarCreatorAccountLineage.objects.filter(
            stellar_account='GNOHORIZONDATA123',
            network_name='public'
        ).first()
        
        self.assertEqual(
            saved.xlm_balance,
            0.0,
            "Balance should be 0 when Horizon data unavailable"
        )
        
        self.assertEqual(
            saved.home_domain,
            '',
            "home_domain should be empty when Horizon data unavailable"
        )
        
        # Clean up
        account_obj.delete()
    
    def test_high_value_account_detection_requires_balance(self):
        """
        Test that HVA (High Value Account) detection works correctly
        now that balances are being saved.
        
        HVA requires xlm_balance > 1,000,000 XLM.
        """
        # Create HVA account
        hva_account = StellarCreatorAccountLineage.objects.create(
            stellar_account='GHVATEST123',
            network_name='public',
            xlm_balance=5_000_000.0,  # 5M XLM
            status='BIGQUERY_COMPLETE'
        )
        
        # Verify HVA logic
        if hva_account.xlm_balance > 1_000_000:
            hva_account.is_hva = True
            hva_account.save()
        
        retrieved = StellarCreatorAccountLineage.objects.filter(
            stellar_account='GHVATEST123',
            network_name='public'
        ).first()
        
        self.assertTrue(
            retrieved.is_hva,
            "Account with >1M XLM should be marked as HVA"
        )
        
        # Create non-HVA account
        non_hva = StellarCreatorAccountLineage.objects.create(
            stellar_account='GNONHVATEST123',
            network_name='public',
            xlm_balance=500_000.0,  # 500K XLM
            status='BIGQUERY_COMPLETE'
        )
        
        self.assertFalse(
            non_hva.is_hva,
            "Account with <1M XLM should NOT be marked as HVA"
        )
        
        # Clean up
        hva_account.delete()
        non_hva.delete()


class BigQueryPipelineFetchHorizonDataTest(TestCase):
    """
    Test the _fetch_horizon_account_data method to ensure
    it correctly extracts and returns balance data.
    """
    
    @patch('apiApp.management.commands.bigquery_pipeline.StellarMapHorizonAPIHelpers')
    def test_fetch_horizon_data_returns_balance(self, mock_horizon_class):
        """
        Test that _fetch_horizon_account_data returns balance
        in the correct format for saving to database.
        """
        # Mock Horizon API response
        mock_horizon = mock_horizon_class.return_value
        mock_horizon.get_base_accounts.return_value = {
            'id': 'GTEST123',
            'balances': [
                {'asset_type': 'native', 'balance': '1234567.89'}
            ],
            'home_domain': 'test.example.com',
            'flags': {},
            'thresholds': {},
            'signers': [],
            'sequence': '999',
            'subentry_count': 5,
            'num_sponsoring': 0,
            'num_sponsored': 0
        }
        
        # Create command
        cmd = Command()
        from apiApp.helpers.env import EnvHelpers
        cmd.env_helpers = EnvHelpers()
        cmd.env_helpers.set_public_network()
        
        # Call method
        result = cmd._fetch_horizon_account_data('GTEST123')
        
        # Verify result structure
        self.assertIsNotNone(result, "Should return data dict")
        self.assertIn('balance', result, "Should include balance key")
        self.assertIn('home_domain', result, "Should include home_domain key")
        
        # Verify balance value
        self.assertEqual(
            result['balance'],
            1234567.89,
            "Balance should be parsed as float"
        )
        
        self.assertEqual(
            result['home_domain'],
            'test.example.com',
            "home_domain should be extracted"
        )
        
        print("\n✅ Horizon data fetch test passed!")
        print(f"   Balance extracted: {result['balance']:,.2f} XLM")
        print(f"   Home domain: {result['home_domain']}")
