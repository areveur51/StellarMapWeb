from django.test import TestCase
from unittest.mock import Mock, patch, MagicMock
from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers, StellarMapHorizonAPIParserHelpers


class StellarMapHorizonAPIHelpersTestCase(TestCase):
    
    def setUp(self):
        self.horizon_url = "https://horizon-testnet.stellar.org"
        self.account_id = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        self.horizon_helpers = StellarMapHorizonAPIHelpers(self.horizon_url, self.account_id)
    
    def test_init(self):
        self.assertEqual(self.horizon_helpers.account_id, self.account_id)
        self.assertIsNotNone(self.horizon_helpers.server)
    
    @patch('stellar_sdk.Server.accounts')
    def test_get_base_accounts(self, mock_accounts):
        mock_account = Mock()
        mock_account.call.return_value = {"id": self.account_id}
        mock_accounts.return_value.account_id.return_value = mock_account
        
        result = self.horizon_helpers.get_base_accounts()
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("id"), self.account_id)
    
    @patch('stellar_sdk.Server.operations')
    def test_get_account_operations(self, mock_operations):
        mock_ops = Mock()
        mock_ops.call.return_value = {"_embedded": {"records": []}}
        mock_operations.return_value.for_account.return_value = mock_ops
        
        result = self.horizon_helpers.get_account_operations()
        self.assertIsInstance(result, dict)


class StellarMapHorizonAPIParserHelpersTestCase(TestCase):
    
    def setUp(self):
        self.datastax_response = {
            "data": {
                "raw_data": {
                    "balances": [
                        {"asset_type": "native", "balance": "100.5"},
                        {"asset_type": "credit_alphanum4", "balance": "50.0"}
                    ],
                    "home_domain": "example.com"
                }
            }
        }
        self.parser = StellarMapHorizonAPIParserHelpers(self.datastax_response)
    
    def test_parse_account_native_balance(self):
        balance = self.parser.parse_account_native_balance()
        self.assertEqual(balance, 100.5)
    
    def test_parse_account_native_balance_missing(self):
        empty_response = {"data": {"raw_data": {"balances": []}}}
        parser = StellarMapHorizonAPIParserHelpers(empty_response)
        balance = parser.parse_account_native_balance()
        self.assertEqual(balance, 0.0)
    
    def test_parse_operations_creator_account(self):
        operations_response = {
            "data": {
                "raw_data": {
                    "_embedded": {
                        "records": [
                            {
                                "type": "create_account",
                                "account": "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB",
                                "funder": "GBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
                                "created_at": "2023-10-15T12:30:45Z"
                            }
                        ]
                    }
                }
            }
        }
        parser = StellarMapHorizonAPIParserHelpers(operations_response)
        result = parser.parse_operations_creator_account("GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB")
        
        self.assertIsInstance(result, dict)
        self.assertIn('funder', result)
