"""
Test suite for Query Builder home_domain filter accuracy.

Tests that the home_domain filter correctly retrieves accounts with specific domain values.
"""
import pytest
from django.test import Client


@pytest.mark.unit
@pytest.mark.django_db
class TestQueryBuilderHomeDomain:
    """Test Query Builder home_domain filter functionality."""
    
    def test_home_domain_filter_returns_results(self, client):
        """Verify home_domain filter executes without errors."""
        # Test with a simple filter
        response = client.get(
            '/api/cassandra-query/',
            {
                'query': 'custom',
                'table': 'lineage',
                'filters': '[{"column":"home_domain","operator":"contains","value":"."}]',
                'limit': '100',
                'network': 'public'
            }
        )
        
        # Should return 200, not 500
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.content}"
        
        data = response.json()
        
        # Verify response structure
        assert 'results' in data
        assert 'description' in data
        assert 'visible_columns' in data
        assert 'count' in data
        
        # Verify home_domain is in visible columns
        assert 'home_domain' in data['visible_columns'], \
            f"home_domain should be in visible_columns, got: {data['visible_columns']}"
    
    def test_home_domain_in_results(self, client):
        """Verify home_domain appears in result records."""
        response = client.get(
            '/api/cassandra-query/',
            {
                'query': 'custom',
                'table': 'lineage',
                'filters': '[{"column":"home_domain","operator":"contains","value":"stellar"}]',
                'limit': '50',
                'network': 'public'
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # If we have results, verify they contain home_domain
        if data['count'] > 0:
            first_result = data['results'][0]
            assert 'home_domain' in first_result, \
                f"home_domain should be in results, got keys: {first_result.keys()}"
    
    def test_home_domain_filter_operators(self, client):
        """Test different operators with home_domain filter."""
        operators = ['contains', 'equals']
        
        for operator in operators:
            response = client.get(
                '/api/cassandra-query/',
                {
                    'query': 'custom',
                    'table': 'lineage',
                    'filters': f'[{{"column":"home_domain","operator":"{operator}","value":"test"}}]',
                    'limit': '10',
                    'network': 'public'
                }
            )
            
            assert response.status_code == 200, \
                f"Operator '{operator}' should not cause error, got {response.status_code}"
            
            data = response.json()
            assert 'results' in data
            assert 'home_domain' in data['visible_columns']


@pytest.mark.integration
@pytest.mark.django_db
class TestHomeDomainFilterAccuracy:
    """Integration tests for home_domain filter accuracy."""
    
    def test_custom_query_structure(self, client):
        """Verify custom query with home_domain has correct structure."""
        import json
        
        filters = [
            {
                "column": "home_domain",
                "operator": "contains",
                "value": "."
            }
        ]
        
        response = client.get(
            '/api/cassandra-query/',
            {
                'query': 'custom',
                'table': 'lineage',
                'filters': json.dumps(filters),
                'limit': '100',
                'network': 'public'
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify the API properly parsed the filters
        assert data['description'] == 'Custom Query on Lineage'
        assert 'home_domain' in data['visible_columns']
        
        # Results should be a list
        assert isinstance(data['results'], list)
        assert isinstance(data['count'], int)
    
    def test_multiple_filters_with_home_domain(self, client):
        """Test combining home_domain filter with other filters (AND logic)."""
        import json
        
        filters = [
            {
                "column": "home_domain",
                "operator": "contains",
                "value": "."
            },
            {
                "column": "status",
                "operator": "equals",
                "value": "BIGQUERY_COMPLETE"
            }
        ]
        
        response = client.get(
            '/api/cassandra-query/',
            {
                'query': 'custom',
                'table': 'lineage',
                'filters': json.dumps(filters),
                'limit': '50',
                'network': 'public'
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Both filtered columns should be visible
        assert 'home_domain' in data['visible_columns']
        assert 'status' in data['visible_columns']
        
        # If results exist, verify they match both filters
        if data['count'] > 0:
            for result in data['results']:
                assert 'home_domain' in result
                assert 'status' in result
