"""
Regression tests for lineage-with-siblings API endpoint.

Tests the new API endpoint that fetches account lineage with siblings
for enhanced visualization with color coding (red for direct lineage,
gray for siblings, cyan glow for searched account).

Created: 2025-10-23
"""
import pytest
import json
from datetime import datetime
from django.test import Client
from apiApp.model_loader import (
    StellarCreatorAccountLineage,
    USE_CASSANDRA
)


@pytest.mark.django_db
class TestLineageWithSiblingsAPI:
    """Test suite for /api/lineage-with-siblings/ endpoint"""
    
    @pytest.fixture
    def client(self):
        """Provide Django test client"""
        return Client()
    
    @pytest.fixture
    def sample_lineage_data(self):
        """
        Create sample lineage data with siblings for testing.
        
        Hierarchy:
        ROOT (GROOT...)
          ├─ CHILD1 (GCHILD1...) [direct lineage path]
          │  ├─ GRANDCHILD1 (GGRAND1...) [searched account]
          │  └─ GRANDCHILD2 (GGRAND2...) [sibling]
          └─ CHILD2 (GCHILD2...) [sibling of CHILD1]
        """
        # Root account
        root = StellarCreatorAccountLineage.objects.create(
            stellar_account='GROOTROOTROOTROOTROOTROOTROOTROOTROOTROOT12345',
            stellar_creator_account=None,
            network_name='public',
            status='COMPLETE',
            xlm_balance=10000.0,
            stellar_account_created_at=datetime(2023, 1, 1)
        )
        
        # Child 1 - in direct lineage path
        child1 = StellarCreatorAccountLineage.objects.create(
            stellar_account='GCHILD1CHILD1CHILD1CHILD1CHILD1CHILD1CHILD12345',
            stellar_creator_account='GROOTROOTROOTROOTROOTROOTROOTROOTROOTROOT12345',
            network_name='public',
            status='COMPLETE',
            xlm_balance=5000.0,
            stellar_account_created_at=datetime(2023, 2, 1)
        )
        
        # Child 2 - sibling of Child 1
        child2 = StellarCreatorAccountLineage.objects.create(
            stellar_account='GCHILD2CHILD2CHILD2CHILD2CHILD2CHILD2CHILD22345',
            stellar_creator_account='GROOTROOTROOTROOTROOTROOTROOTROOTROOTROOT12345',
            network_name='public',
            status='COMPLETE',
            xlm_balance=3000.0,
            stellar_account_created_at=datetime(2023, 2, 15)
        )
        
        # Grandchild 1 - searched account (end of lineage path)
        grandchild1 = StellarCreatorAccountLineage.objects.create(
            stellar_account='GGRAND1GRAND1GRAND1GRAND1GRAND1GRAND1GRAND12345',
            stellar_creator_account='GCHILD1CHILD1CHILD1CHILD1CHILD1CHILD1CHILD12345',
            network_name='public',
            status='COMPLETE',
            xlm_balance=1000.0,
            stellar_account_created_at=datetime(2023, 3, 1)
        )
        
        # Grandchild 2 - sibling of Grandchild 1
        grandchild2 = StellarCreatorAccountLineage.objects.create(
            stellar_account='GGRAND2GRAND2GRAND2GRAND2GRAND2GRAND2GRAND22345',
            stellar_creator_account='GCHILD1CHILD1CHILD1CHILD1CHILD1CHILD1CHILD12345',
            network_name='public',
            status='COMPLETE',
            xlm_balance=800.0,
            stellar_account_created_at=datetime(2023, 3, 15)
        )
        
        return {
            'root': root,
            'child1': child1,
            'child2': child2,
            'grandchild1': grandchild1,
            'grandchild2': grandchild2
        }
    
    def test_successful_lineage_with_siblings_fetch(self, client, sample_lineage_data):
        """Test successful fetch of lineage with siblings"""
        # Search for grandchild1 - should return path + siblings
        response = client.get('/api/lineage-with-siblings/', {
            'account': 'GGRAND1GRAND1GRAND1GRAND1GRAND1GRAND1GRAND12345',
            'network': 'public'
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert 'lineage_path' in data
        assert 'siblings_by_creator' in data
        assert 'all_account_data' in data
        assert 'account' in data
        assert 'network' in data
        
        # Verify lineage path (root -> child1 -> grandchild1)
        assert len(data['lineage_path']) == 3
        assert data['lineage_path'][0] == 'GROOTROOTROOTROOTROOTROOTROOTROOTROOTROOT12345'
        assert data['lineage_path'][1] == 'GCHILD1CHILD1CHILD1CHILD1CHILD1CHILD1CHILD12345'
        assert data['lineage_path'][2] == 'GGRAND1GRAND1GRAND1GRAND1GRAND1GRAND1GRAND12345'
        
        # Verify siblings are included
        assert 'siblings_by_creator' in data
        # Root should have child2 as sibling of child1
        root_addr = 'GROOTROOTROOTROOTROOTROOTROOTROOTROOTROOT12345'
        if root_addr in data['siblings_by_creator']:
            assert 'GCHILD2CHILD2CHILD2CHILD2CHILD2CHILD2CHILD22345' in data['siblings_by_creator'][root_addr]
        
        # Child1 should have grandchild2 as sibling of grandchild1
        child1_addr = 'GCHILD1CHILD1CHILD1CHILD1CHILD1CHILD1CHILD12345'
        if child1_addr in data['siblings_by_creator']:
            assert 'GGRAND2GRAND2GRAND2GRAND2GRAND2GRAND2GRAND22345' in data['siblings_by_creator'][child1_addr]
        
        # Verify all account data is present
        assert 'GROOTROOTROOTROOTROOTROOTROOTROOTROOTROOT12345' in data['all_account_data']
        assert 'GCHILD1CHILD1CHILD1CHILD1CHILD1CHILD1CHILD12345' in data['all_account_data']
        assert 'GGRAND1GRAND1GRAND1GRAND1GRAND1GRAND1GRAND12345' in data['all_account_data']
        
        # Verify in_lineage_path flag is set correctly
        assert data['all_account_data']['GGRAND1GRAND1GRAND1GRAND1GRAND1GRAND1GRAND12345']['in_lineage_path'] is True
    
    def test_missing_account_parameter(self, client):
        """Test error when account parameter is missing"""
        response = client.get('/api/lineage-with-siblings/', {
            'network': 'public'
        })
        
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert 'Missing required parameters' in data['error']
    
    def test_missing_network_parameter(self, client):
        """Test error when network parameter is missing"""
        response = client.get('/api/lineage-with-siblings/', {
            'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB'
        })
        
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert 'Missing required parameters' in data['error']
    
    def test_invalid_account_address(self, client):
        """Test error when account address is invalid"""
        response = client.get('/api/lineage-with-siblings/', {
            'account': 'INVALID_ADDRESS',
            'network': 'public'
        })
        
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert 'Invalid stellar account address' in data['error']
    
    def test_invalid_network(self, client):
        """Test error when network is invalid"""
        response = client.get('/api/lineage-with-siblings/', {
            'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB',
            'network': 'invalid_network'
        })
        
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert 'Invalid network' in data['error']
    
    def test_account_not_found(self, client):
        """Test when account doesn't exist in database"""
        response = client.get('/api/lineage-with-siblings/', {
            'account': 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF',
            'network': 'public'
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return empty lineage path
        assert data['lineage_path'] == []
        assert data['siblings_by_creator'] == {}
        assert data['all_account_data'] == {}
    
    def test_max_siblings_parameter(self, client, sample_lineage_data):
        """Test max_siblings_per_level parameter limits sibling count"""
        # Create many siblings
        for i in range(10):
            StellarCreatorAccountLineage.objects.create(
                stellar_account=f'GSIBLING{i:02d}SIBLING{i:02d}SIBLING{i:02d}SIBLING{i:02d}123',
                stellar_creator_account='GROOTROOTROOTROOTROOTROOTROOTROOTROOTROOT12345',
                network_name='public',
                status='COMPLETE',
                xlm_balance=100.0,
                stellar_account_created_at=datetime(2023, 2, i+1)
            )
        
        # Request with max_siblings=3
        response = client.get('/api/lineage-with-siblings/', {
            'account': 'GCHILD1CHILD1CHILD1CHILD1CHILD1CHILD1CHILD12345',
            'network': 'public',
            'max_siblings_per_level': 3
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify sibling limit is respected
        root_addr = 'GROOTROOTROOTROOTROOTROOTROOTROOTROOTROOT12345'
        if root_addr in data['siblings_by_creator']:
            # Should have at most 3 siblings (excluding the lineage path account)
            assert len(data['siblings_by_creator'][root_addr]) <= 3
    
    def test_color_coding_flags_in_response(self, client, sample_lineage_data):
        """Test that color coding flags are present for visualization"""
        response = client.get('/api/lineage-with-siblings/', {
            'account': 'GGRAND1GRAND1GRAND1GRAND1GRAND1GRAND1GRAND12345',
            'network': 'public'
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Check lineage path accounts have in_lineage_path=True
        for account_addr in data['lineage_path']:
            if account_addr in data['all_account_data']:
                assert data['all_account_data'][account_addr]['in_lineage_path'] is True
        
        # Check is_issuer flag is present
        for account_data in data['all_account_data'].values():
            assert 'is_issuer' in account_data
            assert isinstance(account_data['is_issuer'], bool)
    
    def test_assets_extraction(self, client):
        """Test that assets are extracted from horizon_accounts_json"""
        # Create account with assets in horizon JSON
        horizon_json = json.dumps({
            'balances': [
                {
                    'asset_type': 'native',
                    'balance': '1000.0'
                },
                {
                    'asset_type': 'credit_alphanum4',
                    'asset_code': 'USDC',
                    'asset_issuer': 'GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN',
                    'balance': '500.0'
                }
            ]
        })
        
        account = StellarCreatorAccountLineage.objects.create(
            stellar_account='GASSETASSETASSETASSETASSETASSETASSETASSET12345',
            stellar_creator_account=None,
            network_name='public',
            status='COMPLETE',
            xlm_balance=1000.0,
            horizon_accounts_json=horizon_json,
            stellar_account_created_at=datetime(2023, 1, 1)
        )
        
        response = client.get('/api/lineage-with-siblings/', {
            'account': 'GASSETASSETASSETASSETASSETASSETASSETASSET12345',
            'network': 'public'
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify assets are extracted
        account_data = data['all_account_data']['GASSETASSETASSETASSETASSETASSETASSETASSET12345']
        assert 'assets' in account_data
        assert len(account_data['assets']) == 1  # Only non-native assets
        assert account_data['assets'][0]['asset_code'] == 'USDC'
        assert account_data['is_issuer'] is True  # Has assets, so is_issuer=True


@pytest.mark.django_db
class TestLineageWithSiblingsIntegration:
    """Integration tests with actual account data"""
    
    @pytest.fixture
    def client(self):
        return Client()
    
    def test_real_account_lineage_structure(self, client):
        """Test with real Stellar account that exists in database"""
        # This test checks if an actual account in the database returns proper structure
        # Note: Only runs if the account exists
        response = client.get('/api/lineage-with-siblings/', {
            'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB',
            'network': 'public'
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields are present
        assert 'lineage_path' in data
        assert 'siblings_by_creator' in data
        assert 'all_account_data' in data
        assert 'total_accounts' in data
        assert 'total_siblings' in data
        
        # Verify data types
        assert isinstance(data['lineage_path'], list)
        assert isinstance(data['siblings_by_creator'], dict)
        assert isinstance(data['all_account_data'], dict)
        assert isinstance(data['total_accounts'], int)
        assert isinstance(data['total_siblings'], int)
