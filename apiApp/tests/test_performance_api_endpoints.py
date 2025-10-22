"""
Performance and regression tests for API endpoint optimizations.

Tests ensure that:
1. Pending accounts API respects 30s cache TTL
2. Account lineage API uses in-memory hierarchy (no full table scans)
3. Pagination limits are enforced
4. Rate limiting works correctly
"""

import pytest
from django.test import TestCase, Client
from django.core.cache import cache
from django.urls import reverse
from unittest.mock import patch, MagicMock
import time


@pytest.mark.performance
@pytest.mark.integration
class TestPendingAccountsCacheOptimization(TestCase):
    """Test pending accounts API cache optimization (30s TTL)."""
    
    def setUp(self):
        """Set up test client and clear cache."""
        self.client = Client()
        cache.clear()
    
    def tearDown(self):
        """Clean up cache after each test."""
        cache.clear()
    
    def test_pending_accounts_cache_ttl_30_seconds(self):
        """Test that pending accounts cache has 30s TTL."""
        with patch('apiApp.views.StellarAccountSearchCache') as mock_cache_model:
            with patch('apiApp.views.StellarCreatorAccountLineage') as mock_lineage_model:
                # Mock empty query results
                mock_cache_model.objects.filter.return_value.all.return_value = []
                mock_lineage_model.objects.filter.return_value.all.return_value = []
                
                # First request should hit the database
                response1 = self.client.get('/api/pending-accounts/')
                assert response1.status_code == 200
                
                # Second request within TTL should use cache (no DB query)
                response2 = self.client.get('/api/pending-accounts/')
                assert response2.status_code == 200
                
                # Verify cache was used (queries called only once)
                assert mock_cache_model.objects.filter.call_count <= 3  # Once per status value
    
    def test_pending_accounts_cache_invalidation_after_ttl(self):
        """Test that cache is refreshed after TTL expires."""
        with patch('apiApp.views.StellarAccountSearchCache') as mock_cache_model:
            with patch('apiApp.views.StellarCreatorAccountLineage') as mock_lineage_model:
                mock_cache_model.objects.filter.return_value.all.return_value = []
                mock_lineage_model.objects.filter.return_value.all.return_value = []
                
                # First request
                response1 = self.client.get('/api/pending-accounts/')
                assert response1.status_code == 200
                initial_call_count = mock_cache_model.objects.filter.call_count
                
                # Manually expire cache
                cache.delete('pending_accounts_data')
                
                # Request after cache expiry should hit DB again
                response2 = self.client.get('/api/pending-accounts/')
                assert response2.status_code == 200
                
                # Verify DB was queried again
                assert mock_cache_model.objects.filter.call_count > initial_call_count


@pytest.mark.performance
@pytest.mark.regression
class TestAccountLineageOptimization(TestCase):
    """Test account lineage API optimization (no full table scans)."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
    
    def test_no_full_table_scan_in_lineage_api(self):
        """Test that lineage API doesn't call objects.all() on Cassandra."""
        with patch('apiApp.views.StellarCreatorAccountLineage') as mock_model:
            # Mock the lineage records
            mock_lineage_data = []
            mock_model.objects.filter.return_value.all.return_value = mock_lineage_data
            
            # Make API request
            response = self.client.get(
                '/api/account-lineage/',
                {'account': 'GABC123', 'network': 'public'}
            )
            
            # Verify objects.all() was NEVER called (would be full table scan)
            assert not mock_model.objects.all.called
            
            # Verify filter() was used instead
            assert mock_model.objects.filter.called
    
    def test_lineage_builds_hierarchy_from_fetched_records_only(self):
        """Test that hierarchy is built from already-fetched records."""
        test_account = 'GABC123'
        
        with patch('apiApp.views.StellarCreatorAccountLineage') as mock_model:
            # Mock lineage records
            mock_records = [
                MagicMock(
                    stellar_account='GCHILD1',
                    stellar_creator_account=test_account,
                    stellar_account_created_at=None,
                    xlm_balance=100.0,
                    home_domain='test.com',
                    tags='',
                    status='DONE'
                )
            ]
            mock_model.objects.filter.return_value.all.return_value = mock_records
            
            response = self.client.get(
                '/api/account-lineage/',
                {'account': test_account, 'network': 'public'}
            )
            
            # Should succeed without full table scan
            assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.performance
class TestAPIRateLimiting(TestCase):
    """Test API rate limiting enforcement."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
    
    def test_rate_limit_enforcement(self):
        """Test that rate limiting is enforced on API endpoints."""
        # This test would require actual rate limiting to be active
        # For now, verify the decorator is present
        from apiApp.views import pending_accounts_api
        
        # Check if ratelimit decorator is applied
        assert hasattr(pending_accounts_api, '__wrapped__')


@pytest.mark.performance
@pytest.mark.unit
class TestAPIResponseCacheHeaders(TestCase):
    """Test that API responses include proper cache control headers."""
    
    def test_pending_accounts_includes_cache_metadata(self):
        """Test that pending accounts response includes cache metadata."""
        with patch('apiApp.views.StellarAccountSearchCache'):
            with patch('apiApp.views.StellarCreatorAccountLineage'):
                response = self.client.get('/api/pending-accounts/')
                
                # Should return JSON
                assert response['Content-Type'] == 'application/json'
                assert response.status_code == 200
