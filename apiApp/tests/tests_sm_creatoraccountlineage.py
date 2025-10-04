from django.test import TestCase
from unittest.mock import Mock, patch, AsyncMock
import pandas as pd
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers


class StellarMapCreatorAccountLineageHelpersTestCase(TestCase):
    
    def setUp(self):
        self.lineage_helpers = StellarMapCreatorAccountLineageHelpers()
    
    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineageManager')
    def test_get_account_genealogy_empty_queryset(self, mock_manager):
        mock_manager_instance = Mock()
        mock_manager_instance.get_queryset.return_value = None
        mock_manager.return_value = mock_manager_instance
        
        result = self.lineage_helpers.get_account_genealogy(
            "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB",
            "testnet"
        )
        
        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)
    
    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineageManager')
    def test_get_account_genealogy_with_data(self, mock_manager):
        mock_qs = Mock()
        mock_qs.stellar_account = "ACCOUNT1"
        mock_qs.stellar_creator_account = "no_element_funder"
        mock_qs._meta.fields = []
        
        mock_manager_instance = Mock()
        mock_manager_instance.get_queryset.return_value = mock_qs
        mock_manager.return_value = mock_manager_instance
        
        result = self.lineage_helpers.get_account_genealogy("ACCOUNT1", "testnet")
        
        self.assertIsInstance(result, pd.DataFrame)
    
    def test_generate_tidy_radial_tree_genealogy_empty_df(self):
        empty_df = pd.DataFrame()
        result = self.lineage_helpers.generate_tidy_radial_tree_genealogy(empty_df)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['name'], 'Root')
        self.assertEqual(result['children'], [])
    
    def test_generate_tidy_radial_tree_genealogy_with_data(self):
        data = {
            'stellar_account': ['ACCOUNT1', 'ACCOUNT2'],
            'stellar_creator_account': ['no_element_funder', 'ACCOUNT1']
        }
        df = pd.DataFrame(data)
        
        result = self.lineage_helpers.generate_tidy_radial_tree_genealogy(df)
        
        self.assertIsInstance(result, dict)
        self.assertIn('name', result)
        self.assertIn('children', result)
    
    @patch('apiApp.helpers.sm_creatoraccountlineage.StellarCreatorAccountLineageManager')
    @patch('apiApp.helpers.sm_creatoraccountlineage.AstraDocument')
    async def test_async_update_from_accounts_raw_data(self, mock_astra, mock_manager):
        mock_lin_queryset = Mock()
        mock_lin_queryset.id = 1
        mock_lin_queryset.horizon_accounts_doc_api_href = "https://example.com/doc"
        
        mock_manager_instance = AsyncMock()
        mock_manager.return_value = mock_manager_instance
        
        mock_astra_instance = Mock()
        mock_astra_instance.get_document.return_value = {
            "data": {"raw_data": {"balances": [], "home_domain": "example.com"}}
        }
        mock_astra.return_value = mock_astra_instance
        
        client_session = Mock()
        
        await self.lineage_helpers.async_update_from_accounts_raw_data(
            client_session, mock_lin_queryset
        )
        
        mock_manager_instance.async_update_status.assert_called()
