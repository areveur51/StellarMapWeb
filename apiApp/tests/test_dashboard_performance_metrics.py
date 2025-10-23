"""
Dashboard Performance Metrics Regression Tests

Ensures Performance Metrics section accurately calculates from BOTH
Search Cache AND Lineage tables.

Tests verify:
1. Dual-table scanning (Search Cache + Lineage)
2. Accurate processing time calculations
3. Fastest/Slowest account detection
4. 24h and 7d account counts
5. Correct status filtering (DONE_MAKE_PARENT_LINEAGE, COMPLETE, BIGQUERY_COMPLETE)
"""

import pytest
from datetime import datetime, timedelta
from django.test import Client
from django.urls import reverse
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_search_cache_completed():
    """Mock completed Search Cache records with various processing times"""
    now = datetime.utcnow()
    
    records = [
        # Fast processing (5 minutes)
        MagicMock(
            stellar_account='GFAST1ACCOUNT',
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1) + timedelta(minutes=5),
            status='DONE_MAKE_PARENT_LINEAGE'
        ),
        # Medium processing (30 minutes) - 24h ago
        MagicMock(
            stellar_account='GMEDIUM1ACCOUNT',
            created_at=now - timedelta(hours=24),
            updated_at=now - timedelta(hours=24) + timedelta(minutes=30),
            status='DONE_MAKE_PARENT_LINEAGE'
        ),
        # Slow processing (120 minutes) - 7 days ago
        MagicMock(
            stellar_account='GSLOW1ACCOUNT',
            created_at=now - timedelta(days=7),
            updated_at=now - timedelta(days=7) + timedelta(minutes=120),
            status='DONE_MAKE_PARENT_LINEAGE'
        ),
    ]
    return records


@pytest.fixture
def mock_lineage_complete():
    """Mock COMPLETE Lineage records (API pipeline)"""
    now = datetime.utcnow()
    
    records = [
        # Very fast processing (2 minutes)
        MagicMock(
            stellar_account='GAPI1ACCOUNT',
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2) + timedelta(minutes=2),
            status='COMPLETE'
        ),
        # Medium processing (45 minutes) - 12h ago
        MagicMock(
            stellar_account='GAPI2ACCOUNT',
            created_at=now - timedelta(hours=12),
            updated_at=now - timedelta(hours=12) + timedelta(minutes=45),
            status='COMPLETE'
        ),
    ]
    return records


@pytest.fixture
def mock_lineage_bigquery_complete():
    """Mock BIGQUERY_COMPLETE Lineage records (BigQuery pipeline)"""
    now = datetime.utcnow()
    
    records = [
        # Fast BigQuery processing (1 minute)
        MagicMock(
            stellar_account='GBQ1ACCOUNT',
            created_at=now - timedelta(hours=3),
            updated_at=now - timedelta(hours=3) + timedelta(minutes=1),
            status='BIGQUERY_COMPLETE'
        ),
        # Medium BigQuery processing (15 minutes) - 6h ago
        MagicMock(
            stellar_account='GBQ2ACCOUNT',
            created_at=now - timedelta(hours=6),
            updated_at=now - timedelta(hours=6) + timedelta(minutes=15),
            status='BIGQUERY_COMPLETE'
        ),
        # Slow BigQuery processing (60 minutes) - 48h ago
        MagicMock(
            stellar_account='GBQ3ACCOUNT',
            created_at=now - timedelta(hours=48),
            updated_at=now - timedelta(hours=48) + timedelta(minutes=60),
            status='BIGQUERY_COMPLETE'
        ),
    ]
    return records


@pytest.mark.django_db
class TestDashboardPerformanceMetrics:
    """Test suite for Dashboard Performance Metrics accuracy"""
    
    def test_performance_metrics_dual_table_scanning(
        self,
        mock_search_cache_completed,
        mock_lineage_complete,
        mock_lineage_bigquery_complete
    ):
        """
        Test that Performance Metrics scans BOTH Search Cache AND Lineage tables
        
        Expected behavior:
        - Scans Search Cache for DONE_MAKE_PARENT_LINEAGE records
        - Scans Lineage for COMPLETE records
        - Scans Lineage for BIGQUERY_COMPLETE records
        - Combines all processing times for aggregate calculations
        """
        with patch('webApp.views.StellarAccountSearchCache') as mock_cache, \
             patch('webApp.views.StellarCreatorAccountLineage') as mock_lineage:
            
            # Setup Search Cache mock
            mock_cache_filter = MagicMock()
            mock_cache_filter.all.return_value = mock_search_cache_completed
            mock_cache.objects.filter.return_value = mock_cache_filter
            
            # Setup Lineage COMPLETE mock
            mock_lineage_complete_filter = MagicMock()
            mock_lineage_complete_filter.all.return_value = mock_lineage_complete
            
            # Setup Lineage BIGQUERY_COMPLETE mock
            mock_lineage_bq_filter = MagicMock()
            mock_lineage_bq_filter.all.return_value = mock_lineage_bigquery_complete
            
            # Configure side_effect to return different results based on status filter
            def lineage_filter_side_effect(status):
                if status == 'COMPLETE':
                    return mock_lineage_complete_filter
                elif status == 'BIGQUERY_COMPLETE':
                    return mock_lineage_bq_filter
                return MagicMock(all=MagicMock(return_value=[]))
            
            mock_lineage.objects.filter.side_effect = lineage_filter_side_effect
            mock_lineage.objects.all.return_value = []
            
            # Make request
            client = Client()
            response = client.get(reverse('web:dashboard'))
            
            # Verify both tables were queried
            assert response.status_code == 200
            
            # Verify Search Cache was queried for DONE_MAKE_PARENT_LINEAGE
            mock_cache.objects.filter.assert_called()
            
            # Verify Lineage was queried for both COMPLETE and BIGQUERY_COMPLETE
            assert mock_lineage.objects.filter.call_count >= 2
    
    def test_performance_metrics_processing_time_calculations(
        self,
        mock_search_cache_completed,
        mock_lineage_complete,
        mock_lineage_bigquery_complete
    ):
        """
        Test accurate processing time calculations from both tables
        
        Expected processing times:
        - Search Cache: 5min, 30min, 120min
        - Lineage COMPLETE: 2min, 45min
        - Lineage BIGQUERY_COMPLETE: 1min, 15min, 60min
        
        Total: 8 records
        Average: (5 + 30 + 120 + 2 + 45 + 1 + 15 + 60) / 8 = 34.75 minutes
        Fastest: 1 minute (GBQ1ACCOUNT)
        Slowest: 120 minutes (GSLOW1ACCOUNT)
        """
        with patch('webApp.views.StellarAccountSearchCache') as mock_cache, \
             patch('webApp.views.StellarCreatorAccountLineage') as mock_lineage:
            
            # Setup mocks
            mock_cache_filter = MagicMock()
            mock_cache_filter.all.return_value = mock_search_cache_completed
            mock_cache.objects.filter.return_value = mock_cache_filter
            
            mock_lineage_complete_filter = MagicMock()
            mock_lineage_complete_filter.all.return_value = mock_lineage_complete
            
            mock_lineage_bq_filter = MagicMock()
            mock_lineage_bq_filter.all.return_value = mock_lineage_bigquery_complete
            
            def lineage_filter_side_effect(status):
                if status == 'COMPLETE':
                    return mock_lineage_complete_filter
                elif status == 'BIGQUERY_COMPLETE':
                    return mock_lineage_bq_filter
                return MagicMock(all=MagicMock(return_value=[]))
            
            mock_lineage.objects.filter.side_effect = lineage_filter_side_effect
            mock_lineage.objects.all.return_value = []
            
            # Make request
            client = Client()
            response = client.get(reverse('web:dashboard'))
            
            assert response.status_code == 200
            context = response.context
            
            # Verify aggregate calculations
            performance_stats = context['performance_stats']
            
            # Average should be around 34.75 minutes
            assert performance_stats['avg_processing_time_minutes'] > 0
            assert 30 < performance_stats['avg_processing_time_minutes'] < 40
            
            # Fastest should be 1 minute (BigQuery record)
            assert performance_stats['fastest_account_minutes'] is not None
            assert performance_stats['fastest_account_minutes'] < 2
            
            # Slowest should be 120 minutes (Search Cache record)
            assert performance_stats['slowest_account_minutes'] is not None
            assert performance_stats['slowest_account_minutes'] > 100
    
    def test_performance_metrics_24h_account_count(
        self,
        mock_search_cache_completed,
        mock_lineage_complete,
        mock_lineage_bigquery_complete
    ):
        """
        Test 24h account count from both tables
        
        Expected 24h accounts:
        - Search Cache: GFAST1ACCOUNT (1h ago), GMEDIUM1ACCOUNT (24h ago edge case)
        - Lineage COMPLETE: GAPI1ACCOUNT (2h ago), GAPI2ACCOUNT (12h ago)
        - Lineage BIGQUERY_COMPLETE: GBQ1ACCOUNT (3h ago), GBQ2ACCOUNT (6h ago)
        
        Total: 6 accounts in last 24h
        """
        with patch('webApp.views.StellarAccountSearchCache') as mock_cache, \
             patch('webApp.views.StellarCreatorAccountLineage') as mock_lineage:
            
            # Setup mocks
            mock_cache_filter = MagicMock()
            mock_cache_filter.all.return_value = mock_search_cache_completed
            mock_cache.objects.filter.return_value = mock_cache_filter
            
            mock_lineage_complete_filter = MagicMock()
            mock_lineage_complete_filter.all.return_value = mock_lineage_complete
            
            mock_lineage_bq_filter = MagicMock()
            mock_lineage_bq_filter.all.return_value = mock_lineage_bigquery_complete
            
            def lineage_filter_side_effect(status):
                if status == 'COMPLETE':
                    return mock_lineage_complete_filter
                elif status == 'BIGQUERY_COMPLETE':
                    return mock_lineage_bq_filter
                return MagicMock(all=MagicMock(return_value=[]))
            
            mock_lineage.objects.filter.side_effect = lineage_filter_side_effect
            mock_lineage.objects.all.return_value = []
            
            # Make request
            client = Client()
            response = client.get(reverse('web:dashboard'))
            
            assert response.status_code == 200
            context = response.context
            
            performance_stats = context['performance_stats']
            
            # Should have 5-6 accounts processed in last 24h
            # (GMEDIUM1ACCOUNT is exactly 24h ago, may be edge case)
            assert 5 <= performance_stats['total_accounts_processed_24h'] <= 6
    
    def test_performance_metrics_7d_account_count(
        self,
        mock_search_cache_completed,
        mock_lineage_complete,
        mock_lineage_bigquery_complete
    ):
        """
        Test 7d account count from both tables
        
        Expected 7d accounts:
        - All accounts from 24h test: 6 accounts
        - Search Cache: GSLOW1ACCOUNT (7d ago edge case)
        
        Total: 7 accounts in last 7d (GSLOW1ACCOUNT is edge case)
        GBQ3ACCOUNT is 48h ago, so it's included
        """
        with patch('webApp.views.StellarAccountSearchCache') as mock_cache, \
             patch('webApp.views.StellarCreatorAccountLineage') as mock_lineage:
            
            # Setup mocks
            mock_cache_filter = MagicMock()
            mock_cache_filter.all.return_value = mock_search_cache_completed
            mock_cache.objects.filter.return_value = mock_cache_filter
            
            mock_lineage_complete_filter = MagicMock()
            mock_lineage_complete_filter.all.return_value = mock_lineage_complete
            
            mock_lineage_bq_filter = MagicMock()
            mock_lineage_bq_filter.all.return_value = mock_lineage_bigquery_complete
            
            def lineage_filter_side_effect(status):
                if status == 'COMPLETE':
                    return mock_lineage_complete_filter
                elif status == 'BIGQUERY_COMPLETE':
                    return mock_lineage_bq_filter
                return MagicMock(all=MagicMock(return_value=[]))
            
            mock_lineage.objects.filter.side_effect = lineage_filter_side_effect
            mock_lineage.objects.all.return_value = []
            
            # Make request
            client = Client()
            response = client.get(reverse('web:dashboard'))
            
            assert response.status_code == 200
            context = response.context
            
            performance_stats = context['performance_stats']
            
            # Should have 7-8 accounts processed in last 7d
            # (includes GBQ3ACCOUNT at 48h, edge cases for 7d boundary)
            assert 7 <= performance_stats['total_accounts_processed_7d'] <= 8
    
    def test_performance_metrics_with_missing_timestamps(self):
        """
        Test that Performance Metrics handles records with missing timestamps gracefully
        
        Records without created_at or updated_at should be skipped from calculations
        """
        now = datetime.utcnow()
        
        mock_records_with_none = [
            # Valid record
            MagicMock(
                stellar_account='GVALID',
                created_at=now - timedelta(hours=1),
                updated_at=now - timedelta(hours=1) + timedelta(minutes=10),
                status='BIGQUERY_COMPLETE'
            ),
            # Missing created_at
            MagicMock(
                stellar_account='GMISSING1',
                created_at=None,
                updated_at=now,
                status='BIGQUERY_COMPLETE'
            ),
            # Missing updated_at
            MagicMock(
                stellar_account='GMISSING2',
                created_at=now,
                updated_at=None,
                status='BIGQUERY_COMPLETE'
            ),
        ]
        
        with patch('webApp.views.StellarAccountSearchCache') as mock_cache, \
             patch('webApp.views.StellarCreatorAccountLineage') as mock_lineage:
            
            # Setup mocks to return empty for cache
            mock_cache.objects.filter.return_value.all.return_value = []
            
            # Setup lineage to return records with missing timestamps
            mock_lineage_bq_filter = MagicMock()
            mock_lineage_bq_filter.all.return_value = mock_records_with_none
            
            def lineage_filter_side_effect(status):
                if status == 'BIGQUERY_COMPLETE':
                    return mock_lineage_bq_filter
                return MagicMock(all=MagicMock(return_value=[]))
            
            mock_lineage.objects.filter.side_effect = lineage_filter_side_effect
            mock_lineage.objects.all.return_value = []
            
            # Make request
            client = Client()
            response = client.get(reverse('web:dashboard'))
            
            assert response.status_code == 200
            context = response.context
            
            performance_stats = context['performance_stats']
            
            # Should only count the 1 valid record
            assert performance_stats['total_accounts_processed_24h'] == 1
            assert performance_stats['fastest_account_minutes'] is not None
            assert performance_stats['slowest_account_minutes'] is not None
            # Both should be around 10 minutes (only 1 valid record)
            assert 9 < performance_stats['fastest_account_minutes'] < 11
            assert 9 < performance_stats['slowest_account_minutes'] < 11
    
    def test_performance_metrics_empty_database(self):
        """
        Test Performance Metrics with no completed records
        
        Should display default values without errors:
        - avg_processing_time_minutes: 0
        - fastest_account_minutes: None (displays as N/A)
        - slowest_account_minutes: None (displays as N/A)
        - total_accounts_processed_24h: 0
        - total_accounts_processed_7d: 0
        """
        with patch('webApp.views.StellarAccountSearchCache') as mock_cache, \
             patch('webApp.views.StellarCreatorAccountLineage') as mock_lineage:
            
            # Setup mocks to return empty results
            mock_cache.objects.filter.return_value.all.return_value = []
            mock_lineage.objects.filter.return_value.all.return_value = []
            mock_lineage.objects.all.return_value = []
            
            # Make request
            client = Client()
            response = client.get(reverse('web:dashboard'))
            
            assert response.status_code == 200
            context = response.context
            
            performance_stats = context['performance_stats']
            
            # Verify default values
            assert performance_stats['avg_processing_time_minutes'] == 0
            assert performance_stats['fastest_account_minutes'] is None
            assert performance_stats['slowest_account_minutes'] is None
            assert performance_stats['total_accounts_processed_24h'] == 0
            assert performance_stats['total_accounts_processed_7d'] == 0
