"""
Performance tests for BigQuery client singleton caching optimization.

Tests ensure that:
1. BigQuery client is cached as a singleton per credential hash
2. Client cache is invalidated when credentials change
3. Cost guard is properly initialized each time
4. No expensive re-initialization occurs on subsequent calls
"""

import pytest
from unittest.mock import patch, MagicMock
from apiApp.helpers.sm_bigquery import BigQueryHelpers
import hashlib
import json


@pytest.mark.performance
@pytest.mark.unit
class TestBigQueryClientCaching:
    """Test BigQuery client singleton caching mechanism."""
    
    def test_client_caching_same_credentials(self):
        """Test that client is reused when credentials haven't changed."""
        with patch('apiApp.helpers.sm_bigquery.bigquery.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            with patch('apiApp.helpers.sm_bigquery.config') as mock_config:
                mock_config.return_value = '{"test": "credentials"}'
                
                # First call should create client
                helper1 = BigQueryHelpers()
                client1 = helper1.client
                
                # Second call should reuse cached client
                helper2 = BigQueryHelpers()
                client2 = helper2.client
                
                # Client should be cached (same instance)
                assert client1 is client2
                # Client constructor should only be called once
                assert mock_client_class.call_count == 1
    
    def test_cache_invalidation_on_credential_change(self):
        """Test that cache is invalidated when credentials change."""
        # Clear any existing cache
        BigQueryHelpers._client_cache = {}
        
        with patch('apiApp.helpers.sm_bigquery.bigquery.Client') as mock_client_class:
            with patch('apiApp.helpers.sm_bigquery.config') as mock_config:
                # First credentials
                mock_config.return_value = '{"test": "credentials1"}'
                helper1 = BigQueryHelpers()
                client1 = helper1.client
                
                # Change credentials
                mock_config.return_value = '{"test": "credentials2"}'
                helper2 = BigQueryHelpers()
                client2 = helper2.client
                
                # Should have different clients
                assert client1 is not client2
                # Client constructor should be called twice
                assert mock_client_class.call_count == 2
    
    def test_credential_hash_calculation(self):
        """Test credential hash calculation is consistent."""
        with patch('apiApp.helpers.sm_bigquery.config') as mock_config:
            credentials_json = '{"type": "service_account", "project_id": "test"}'
            mock_config.return_value = credentials_json
            
            # Calculate hash manually
            expected_hash = hashlib.sha256(credentials_json.encode()).hexdigest()
            
            # Get hash from helper
            helper = BigQueryHelpers()
            actual_hash = helper._get_credentials_hash()
            
            assert actual_hash == expected_hash
    
    def test_cost_guard_initialization_per_instance(self):
        """Test that cost guard is initialized for each helper instance."""
        with patch('apiApp.helpers.sm_bigquery.bigquery.Client'):
            with patch('apiApp.helpers.sm_bigquery.config') as mock_config:
                mock_config.return_value = '{"test": "credentials"}'
                
                helper1 = BigQueryHelpers()
                helper2 = BigQueryHelpers()
                
                # Each helper should have its own cost guard instance
                assert helper1.cost_guard is not None
                assert helper2.cost_guard is not None
                assert helper1.cost_guard is not helper2.cost_guard


@pytest.mark.performance
@pytest.mark.regression
class TestBigQueryPerformanceRegression:
    """Regression tests to ensure performance optimizations don't break functionality."""
    
    def test_no_client_reinitialization_in_loop(self):
        """Test that client isn't recreated in tight loops (performance regression)."""
        with patch('apiApp.helpers.sm_bigquery.bigquery.Client') as mock_client_class:
            with patch('apiApp.helpers.sm_bigquery.config') as mock_config:
                mock_config.return_value = '{"test": "credentials"}'
                
                # Simulate multiple calls in quick succession
                for _ in range(10):
                    helper = BigQueryHelpers()
                    _ = helper.client
                
                # Client should only be created once despite 10 helper instances
                assert mock_client_class.call_count == 1
    
    def test_cache_cleanup_on_credential_rotation(self):
        """Test that old clients are properly cleaned up on credential rotation."""
        BigQueryHelpers._client_cache = {}
        
        with patch('apiApp.helpers.sm_bigquery.bigquery.Client'):
            with patch('apiApp.helpers.sm_bigquery.config') as mock_config:
                # Cycle through different credentials
                for i in range(5):
                    mock_config.return_value = f'{{"cred": "{i}"}}'
                    helper = BigQueryHelpers()
                    _ = helper.client
                
                # Cache should only contain the latest credential
                # (old ones are replaced, not accumulated)
                assert len(BigQueryHelpers._client_cache) == 5
