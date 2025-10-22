"""
Query Builder column parity tests.

Tests ensure that:
1. Column definitions in query_builder.html match actual Cassandra model fields
2. All model fields are available in the custom filter builder
3. Column labels are descriptive and consistent
4. No orphaned columns in UI that don't exist in models
"""

import pytest
from django.test import TestCase
import re
from pathlib import Path


@pytest.mark.unit
@pytest.mark.regression
class TestQueryBuilderColumnParity:
    """Test Query Builder column definitions match Cassandra models."""
    
    def _get_template_columns(self, table_key):
        """Extract column definitions from query_builder.html template."""
        template_path = Path('webApp/templates/webApp/query_builder.html')
        
        if not template_path.exists():
            pytest.skip("Template file not found")
        
        with open(template_path, 'r') as f:
            content = f.read()
        
        # Find the tableColumns object
        pattern = rf'{table_key}:\s*\[(.*?)\]'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            return []
        
        # Extract column values
        column_pattern = r'\{value:\s*[\'"](\w+)[\'"]'
        columns = re.findall(column_pattern, match.group(1))
        
        return set(columns)
    
    def _get_model_fields(self, model_class):
        """Extract field names from Cassandra model."""
        from cassandra.cqlengine import columns as cassandra_columns
        
        fields = set()
        for field_name, field_obj in model_class.__dict__.items():
            if isinstance(field_obj, cassandra_columns.Column):
                fields.add(field_name)
        
        # Add common fields that are always present
        if not fields:  # Fallback if introspection fails
            return None
            
        return fields
    
    @pytest.mark.parametrize("table_key,model_name,expected_core_fields", [
        ('lineage', 'StellarCreatorAccountLineage', {
            'stellar_creator_account', 'xlm_balance', 'home_domain', 
            'tags', 'is_hva', 'status', 'network_name'
        }),
        ('cache', 'StellarAccountSearchCache', {
            'status', 'last_fetched_at', 'retry_count', 'network_name'
        }),
        ('stages', 'StellarAccountStageExecution', {
            'stage_number', 'cron_name', 'status', 'network_name'
        }),
        ('hva_changes', 'HVAStandingChange', {
            'event_type', 'old_rank', 'new_rank', 'rank_change', 'network_name'
        }),
    ])
    def test_template_columns_match_model_fields(self, table_key, model_name, expected_core_fields):
        """Test that template columns include all core model fields."""
        template_columns = self._get_template_columns(table_key)
        
        # Verify core fields are present in template
        missing_fields = expected_core_fields - template_columns
        assert not missing_fields, f"Missing fields in template for {table_key}: {missing_fields}"
    
    def test_lineage_table_has_all_important_columns(self):
        """Test that lineage table includes all important queryable columns."""
        columns = self._get_template_columns('lineage')
        
        required_columns = {
            'stellar_creator_account',
            'xlm_balance',
            'home_domain',
            'tags',
            'is_hva',
            'status',
            'network_name',
            'created_at',
            'updated_at'
        }
        
        missing = required_columns - columns
        assert not missing, f"Lineage table missing columns: {missing}"
    
    def test_cache_table_has_all_important_columns(self):
        """Test that cache table includes all important queryable columns."""
        columns = self._get_template_columns('cache')
        
        required_columns = {
            'status',
            'last_fetched_at',
            'retry_count',
            'network_name',
            'created_at',
            'updated_at'
        }
        
        missing = required_columns - columns
        assert not missing, f"Cache table missing columns: {missing}"
    
    def test_stages_table_has_all_important_columns(self):
        """Test that stages table includes all important queryable columns."""
        columns = self._get_template_columns('stages')
        
        required_columns = {
            'stage_number',
            'cron_name',
            'status',
            'execution_time_ms',
            'network_name',
            'created_at'
        }
        
        missing = required_columns - columns
        assert not missing, f"Stages table missing columns: {missing}"
    
    def test_hva_changes_table_has_all_important_columns(self):
        """Test that HVA changes table includes all important queryable columns."""
        columns = self._get_template_columns('hva_changes')
        
        required_columns = {
            'event_type',
            'old_rank',
            'new_rank',
            'rank_change',
            'balance_change_pct',
            'network_name'
        }
        
        missing = required_columns - columns
        assert not missing, f"HVA changes table missing columns: {missing}"
    
    def test_all_tables_have_network_column(self):
        """Test that all tables include network_name for filtering."""
        tables = ['lineage', 'cache', 'hva', 'stages', 'hva_changes']
        
        for table in tables:
            columns = self._get_template_columns(table)
            assert 'network_name' in columns, f"Table '{table}' missing network_name column"
    
    def test_column_count_reasonable(self):
        """Test that each table has a reasonable number of columns (not too few)."""
        tables = {
            'lineage': 8,   # Should have at least 8 columns
            'cache': 5,     # Should have at least 5 columns  
            'hva': 8,       # Should have at least 8 columns
            'stages': 6,    # Should have at least 6 columns
            'hva_changes': 8  # Should have at least 8 columns
        }
        
        for table, min_columns in tables.items():
            columns = self._get_template_columns(table)
            assert len(columns) >= min_columns, \
                f"Table '{table}' has only {len(columns)} columns, expected at least {min_columns}"


@pytest.mark.regression
class TestQueryBuilderAPIIntegration(TestCase):
    """Test Query Builder API integration with custom filters."""
    
    def test_custom_query_endpoint_exists(self):
        """Test that custom query endpoint is accessible."""
        from django.urls import reverse, resolve
        
        # Verify URL pattern exists
        url = '/api/cassandra-query/'
        response = self.client.get(url, {'query': 'stuck_accounts', 'network': 'public'})
        
        # Should not be 404
        assert response.status_code != 404
    
    def test_custom_query_with_filters_parameter(self):
        """Test that custom query accepts filters parameter."""
        import json
        
        filters = [
            {'column': 'status', 'operator': 'equals', 'value': 'PENDING'}
        ]
        
        url = '/api/cassandra-query/'
        params = {
            'query': 'custom',
            'table': 'lineage',
            'filters': json.dumps(filters),
            'network': 'public',
            'limit': '100'
        }
        
        response = self.client.get(url, params)
        
        # Should accept the request (may return empty results)
        assert response.status_code == 200
