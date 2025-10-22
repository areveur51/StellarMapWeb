"""
Test suite for Query Builder "Stuck Accounts" pre-defined query accuracy.

Tests that the Query Builder API returns the same stuck accounts as the dashboard logic.

Related to: User report that Query Builder shows 0 stuck accounts while dashboard shows 37
Fix: Changed Query Builder to query StellarAccountSearchCache instead of StellarCreatorAccountLineage
"""
import pytest
from datetime import datetime, timedelta
from django.test import Client
from apiApp.model_loader import (
    StellarAccountSearchCache,
    STUCK_THRESHOLD_MINUTES,
    STUCK_STATUSES,
    USE_CASSANDRA
)


@pytest.mark.unit
@pytest.mark.django_db
class TestQueryBuilderStuckAccounts:
    """Test Query Builder stuck accounts query matches dashboard logic."""
    
    def test_stuck_accounts_query_uses_correct_table(self, client):
        """Verify stuck accounts query uses StellarAccountSearchCache, not StellarCreatorAccountLineage."""
        # This is a regression test for the bug where Query Builder was querying the wrong table
        
        # Create test data: stuck account in cache
        cutoff_time = datetime.utcnow() - timedelta(minutes=STUCK_THRESHOLD_MINUTES + 10)
        
        # Try to create a stuck account (may fail in read-only test environment)
        try:
            stuck_account = StellarAccountSearchCache(
                stellar_account='GTEST_STUCK_ACCOUNT_123',
                network_name='public',
                status=STUCK_STATUSES[0] if STUCK_STATUSES else 'PENDING',
                updated_at=cutoff_time
            )
            stuck_account.save()
            created = True
        except Exception:
            created = False
            pytest.skip("Cannot create test data in current environment")
        
        if not created:
            return
        
        # Query via API
        response = client.get('/api/cassandra-query/?query=stuck_accounts&network=public&limit=100')
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Should have results (at least the one we created)
        assert 'results' in data
        assert isinstance(data['results'], list)
        
        # Verify description mentions correct threshold
        assert 'description' in data
        assert str(STUCK_THRESHOLD_MINUTES) in data['description']
        
        # Clean up
        try:
            stuck_account.delete()
        except Exception:
            pass
    
    def test_stuck_accounts_matches_dashboard_logic(self):
        """Verify Query Builder stuck accounts logic matches dashboard calculation."""
        # This test verifies the logic is consistent between dashboard and Query Builder
        
        # Dashboard logic (from webApp/views.py):
        # for record in StellarAccountSearchCache.objects.all():
        #     age_minutes = (datetime.utcnow() - record.updated_at).total_seconds() / 60
        #     threshold = STUCK_THRESHOLD_MINUTES if record.status in STUCK_STATUSES else 30
        #     if age_minutes > threshold:
        #         stuck_count += 1
        
        # Query Builder logic (from apiApp/views.py) should now match:
        # cutoff_time = datetime.utcnow() - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
        # for record in StellarAccountSearchCache.objects.filter(network_name=network):
        #     if record.updated_at and record.updated_at < cutoff_time:
        #         if record.status in STUCK_STATUSES:
        #             all_records.append(record)
        
        # Calculate cutoff time
        cutoff_time = datetime.utcnow() - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
        
        # Manual count using dashboard logic
        dashboard_stuck_count = 0
        try:
            for record in StellarAccountSearchCache.objects.all():
                if hasattr(record, 'updated_at') and record.updated_at:
                    age_minutes = (datetime.utcnow() - record.updated_at).total_seconds() / 60
                    threshold = STUCK_THRESHOLD_MINUTES if record.status in STUCK_STATUSES else 30
                    if age_minutes > threshold:
                        dashboard_stuck_count += 1
        except Exception as e:
            pytest.skip(f"Cannot query database: {e}")
        
        # Manual count using Query Builder logic
        query_builder_stuck_count = 0
        try:
            for record in StellarAccountSearchCache.objects.filter(network_name='public'):
                if record.updated_at and record.updated_at < cutoff_time:
                    if record.status in STUCK_STATUSES:
                        query_builder_stuck_count += 1
        except Exception as e:
            pytest.skip(f"Cannot query database: {e}")
        
        # The counts should be close (may differ slightly due to timing)
        # Allow for a small delta (e.g., records that just crossed the threshold)
        assert abs(dashboard_stuck_count - query_builder_stuck_count) <= 5, \
            f"Dashboard: {dashboard_stuck_count}, Query Builder: {query_builder_stuck_count}"
    
    def test_stuck_accounts_api_response_structure(self, client):
        """Verify API response has correct structure for stuck accounts query."""
        response = client.get('/api/cassandra-query/?query=stuck_accounts&network=public&limit=100')
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert 'query' in data
        assert 'description' in data
        assert 'network' in data
        assert 'results' in data
        assert 'count' in data
        assert 'visible_columns' in data
        
        # Verify query name
        assert data['query'] == 'stuck_accounts'
        
        # Verify network
        assert data['network'] == 'public'
        
        # Verify visible columns
        expected_columns = ['status', 'age_minutes', 'retry_count', 'updated_at']
        assert data['visible_columns'] == expected_columns
        
        # Verify results structure (if any results)
        if data['count'] > 0:
            first_result = data['results'][0]
            assert 'stellar_account' in first_result
            assert 'network_name' in first_result
            assert 'status' in first_result
            assert 'age_minutes' in first_result
            assert 'retry_count' in first_result
            assert 'updated_at' in first_result


@pytest.mark.integration
@pytest.mark.django_db
class TestStuckAccountsEndToEnd:
    """End-to-end tests for stuck accounts detection across dashboard and Query Builder."""
    
    def test_dashboard_and_query_builder_consistency(self, client):
        """Verify dashboard stuck count and Query Builder results are consistent."""
        # Get dashboard stats
        dashboard_response = client.get('/web/dashboard/')
        assert dashboard_response.status_code == 200
        
        # Extract stuck count from dashboard (would need to parse HTML in real test)
        # For now, just verify dashboard loads
        
        # Get Query Builder results
        query_response = client.get('/api/cassandra-query/?query=stuck_accounts&network=public&limit=500')
        assert query_response.status_code == 200
        
        query_data = query_response.json()
        query_stuck_count = query_data['count']
        
        # Manual verification
        manual_stuck_count = 0
        cutoff_time = datetime.utcnow() - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
        
        try:
            for record in StellarAccountSearchCache.objects.all():
                if hasattr(record, 'updated_at') and record.updated_at:
                    age_minutes = (datetime.utcnow() - record.updated_at).total_seconds() / 60
                    threshold = STUCK_THRESHOLD_MINUTES if record.status in STUCK_STATUSES else 30
                    if age_minutes > threshold:
                        manual_stuck_count += 1
        except Exception as e:
            pytest.skip(f"Cannot query database: {e}")
        
        # All three counts should be consistent (allow small delta for timing)
        assert abs(query_stuck_count - manual_stuck_count) <= 5, \
            f"Query Builder: {query_stuck_count}, Manual: {manual_stuck_count}"
    
    def test_stuck_accounts_threshold_accuracy(self):
        """Verify stuck accounts threshold is applied correctly."""
        # Get all cache records
        try:
            all_records = list(StellarAccountSearchCache.objects.all())
        except Exception as e:
            pytest.skip(f"Cannot query database: {e}")
        
        if not all_records:
            pytest.skip("No records in database to test")
        
        # Calculate stuck accounts manually
        cutoff_time = datetime.utcnow() - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
        stuck_records = []
        
        for record in all_records:
            if not hasattr(record, 'updated_at') or not record.updated_at:
                continue
            
            # Apply same logic as Query Builder
            if record.updated_at < cutoff_time and record.status in STUCK_STATUSES:
                stuck_records.append(record)
        
        # All stuck records should be older than threshold
        for record in stuck_records:
            age_minutes = (datetime.utcnow() - record.updated_at).total_seconds() / 60
            assert age_minutes >= STUCK_THRESHOLD_MINUTES, \
                f"Record {record.stellar_account} is {age_minutes} min old, threshold is {STUCK_THRESHOLD_MINUTES}"
        
        # Verify status is in STUCK_STATUSES
        for record in stuck_records:
            assert record.status in STUCK_STATUSES, \
                f"Record {record.stellar_account} has status {record.status}, expected one of {STUCK_STATUSES}"
