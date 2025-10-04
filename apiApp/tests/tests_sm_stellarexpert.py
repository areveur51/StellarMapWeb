from django.test import TestCase
from unittest.mock import Mock, patch, MagicMock
from apiApp.helpers.sm_stellarexpert import (
    StellarMapStellarExpertAPIHelpers,
    StellarMapStellarExpertAPIParserHelpers
)
import json


class StellarMapStellarExpertAPIHelpersTestCase(TestCase):
    
    def setUp(self):
        self.mock_queryset = Mock()
        self.mock_queryset.stellar_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        self.mock_queryset.network_name = "testnet"
    
    @patch('apiApp.helpers.sm_stellarexpert.requests.get')
    def test_get_se_asset_list(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"_embedded": {"records": []}}
        mock_get.return_value = mock_response
        
        se_helpers = StellarMapStellarExpertAPIHelpers(self.mock_queryset)
        result = se_helpers.get_se_asset_list()
        
        self.assertIsInstance(result, dict)
        mock_get.assert_called_once()
    
    @patch('apiApp.helpers.sm_stellarexpert.requests.get')
    def test_get_se_asset_rating(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rating": 5}
        mock_get.return_value = mock_response
        
        se_helpers = StellarMapStellarExpertAPIHelpers(self.mock_queryset)
        result = se_helpers.get_se_asset_rating("USD", "credit_alphanum4")
        
        self.assertIsInstance(result, dict)
    
    def test_init_sets_network_testnet(self):
        se_helpers = StellarMapStellarExpertAPIHelpers(self.mock_queryset)
        self.assertEqual(se_helpers.env_helpers.network, 'testnet')
    
    def test_init_sets_network_public(self):
        self.mock_queryset.network_name = "public"
        se_helpers = StellarMapStellarExpertAPIHelpers(self.mock_queryset)
        self.assertEqual(se_helpers.env_helpers.network, 'public')


class StellarMapStellarExpertAPIParserHelpersTestCase(TestCase):
    
    def setUp(self):
        self.mock_queryset = Mock()
        self.mock_queryset.stellar_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
    
    def test_parse_asset_code_issuer_type(self):
        asset_data = json.dumps([
            {
                "asset_code": "USD",
                "asset_issuer": "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB",
                "asset_type": "credit_alphanum4"
            }
        ])
        self.mock_queryset.horizon_accounts_assets_doc_api_href = asset_data
        
        parser = StellarMapStellarExpertAPIParserHelpers(self.mock_queryset)
        result = parser.parse_asset_code_issuer_type()
        
        self.assertEqual(result['asset_code'], "USD")
        self.assertEqual(result['asset_issuer'], "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB")
        self.assertEqual(result['asset_type'], "credit_alphanum4")
    
    def test_parse_asset_code_issuer_type_no_match(self):
        asset_data = json.dumps([
            {
                "asset_code": "EUR",
                "asset_issuer": "DIFFERENT_ACCOUNT",
                "asset_type": "credit_alphanum4"
            }
        ])
        self.mock_queryset.horizon_accounts_assets_doc_api_href = asset_data
        
        parser = StellarMapStellarExpertAPIParserHelpers(self.mock_queryset)
        result = parser.parse_asset_code_issuer_type()
        
        self.assertEqual(result, {})
    
    def test_parse_asset_code_issuer_type_invalid_json(self):
        self.mock_queryset.horizon_accounts_assets_doc_api_href = "invalid json"
        
        parser = StellarMapStellarExpertAPIParserHelpers(self.mock_queryset)
        
        with self.assertRaises(ValueError):
            parser.parse_asset_code_issuer_type()
