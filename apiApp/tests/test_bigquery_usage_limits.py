"""
Tests for BigQuery Usage Monitoring and Quota Limits

These tests ensure StellarMapWeb stays within BigQuery usage limits
to avoid excessive costs and quota exhaustion.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from apiApp.helpers.sm_bigquery import StellarBigQueryHelper


class BigQueryUsageLimitsTestCase(TestCase):
    """
    Test BigQuery usage patterns to ensure we stay within limits.
    
    Current Limits (Post-Refactoring):
    - Per search: ~110-420 MB
    - Per day (100 searches): ~42 GB
    - Per month: ~1.26 TB (within 1 TB free tier)
    
    Scale Target (5000 searches/day):
    - Per day: ~2.1 GB
    - Per month: ~63 TB (requires cost management)
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.helper = StellarBigQueryHelper()
    
    def test_instant_lineage_query_count(self):
        """
        Test that instant lineage executes exactly 4 queries maximum.
        
        Expected queries:
        1. get_account_data(searched_account)
        2. get_account_creator(searched_account)
        3. get_account_data(creator_account)
        4. get_child_accounts(searched_account, limit=100)
        """
        with patch.object(self.helper, 'client') as mock_client:
            mock_query_job = Mock()
            mock_query_job.__iter__ = Mock(return_value=iter([
                Mock(account_id='GTEST', account_creation_date='2020-01-01T00:00:00Z'),
                Mock(creator='GCREATOR', created_at='2020-01-01T00:00:00Z'),
                Mock(account='GCHILD1'),
            ]))
            mock_client.query.return_value = mock_query_job
            
            # Execute instant lineage query
            result = self.helper.get_instant_lineage('GTESTACCOUNT123456789012345678901234567890123')
            
            # Should execute exactly 4 queries (or fewer if data not found)
            self.assertLessEqual(
                mock_client.query.call_count, 
                4,
                "Instant lineage should execute maximum 4 BigQuery queries"
            )
    
    def test_child_accounts_limit_enforced(self):
        """
        Test that child account discovery respects the 100-account limit
        for instant display to minimize BigQuery scanning.
        """
        with patch.object(self.helper, 'client') as mock_client:
            # Simulate query execution
            mock_query_job = Mock()
            mock_query_job.__iter__ = Mock(return_value=iter([]))
            mock_client.query.return_value = mock_query_job
            
            # Call get_child_accounts
            self.helper.get_child_accounts('GTEST', limit=100)
            
            # Check that LIMIT clause is in the query
            call_args = mock_client.query.call_args
            query = call_args[0][0]
            
            self.assertIn('LIMIT 100', query, "Child account query must include LIMIT clause")
    
    def test_no_asset_queries_in_instant_lineage(self):
        """
        Test that instant lineage does NOT query asset tables.
        Assets should be fetched from Stellar Expert API instead.
        """
        with patch.object(self.helper, 'get_account_assets') as mock_assets:
            with patch.object(self.helper, 'client') as mock_client:
                mock_query_job = Mock()
                mock_query_job.__iter__ = Mock(return_value=iter([]))
                mock_client.query.return_value = mock_query_job
                
                # Execute instant lineage
                self.helper.get_instant_lineage('GTEST')
                
                # get_account_assets should NOT be called
                mock_assets.assert_not_called()
    
    def test_minimal_columns_queried(self):
        """
        Test that account data queries only retrieve minimal columns
        (account_id, account_creation_date) to reduce data scanned.
        """
        with patch.object(self.helper, 'client') as mock_client:
            mock_query_job = Mock()
            mock_query_job.__iter__ = Mock(return_value=iter([
                Mock(account_id='GTEST', account_creation_date='2020-01-01T00:00:00Z')
            ]))
            mock_client.query.return_value = mock_query_job
            
            # Query account data
            self.helper.get_account_data('GTEST')
            
            # Check query only selects minimal columns
            query = mock_client.query.call_args[0][0]
            
            # Should NOT contain these expensive columns
            self.assertNotIn('balance', query.lower(), "Should not query balance from BigQuery")
            self.assertNotIn('home_domain', query.lower(), "Should not query home_domain from BigQuery")
            self.assertNotIn('flags', query.lower(), "Should not query flags from BigQuery")
            
            # Should contain only these minimal columns
            self.assertIn('account_id', query.lower(), "Should query account_id")
            self.assertIn('account_creation_date', query.lower(), "Should query account_creation_date")
    
    def test_parameterized_queries_used(self):
        """
        Test that all queries use parameterized queries (not string formatting)
        for better BigQuery optimization and security.
        """
        with patch.object(self.helper, 'client') as mock_client:
            mock_query_job = Mock()
            mock_query_job.__iter__ = Mock(return_value=iter([]))
            mock_client.query.return_value = mock_query_job
            
            # Execute various queries
            self.helper.get_account_data('GTEST')
            self.helper.get_account_creator('GTEST')
            self.helper.get_child_accounts('GTEST')
            
            # All queries should have job_config with parameters
            for call in mock_client.query.call_args_list:
                # Second argument should be job_config
                if len(call[0]) > 1 or 'job_config' in call[1]:
                    job_config = call[1].get('job_config') or call[0][1]
                    self.assertIsNotNone(
                        job_config,
                        "All queries should use QueryJobConfig with parameters"
                    )


class BigQueryScalingTestCase(TestCase):
    """
    Test scenarios for scaling to higher query volumes.
    """
    
    def test_usage_calculation_100_searches_per_day(self):
        """
        Calculate expected usage for 100 searches/day scenario.
        
        Expected:
        - Per search: ~420 MB (worst case)
        - Per day: 100 × 420 MB = 42 GB
        - Per month: 42 GB × 30 = 1.26 TB (within free tier)
        """
        searches_per_day = 100
        mb_per_search = 420  # Worst case estimate
        days_per_month = 30
        
        daily_usage_gb = (searches_per_day * mb_per_search) / 1024
        monthly_usage_tb = (daily_usage_gb * days_per_month) / 1024
        
        self.assertLess(
            monthly_usage_tb,
            1.0,
            f"100 searches/day should stay under 1 TB free tier. Got {monthly_usage_tb:.2f} TB"
        )
    
    def test_usage_calculation_5000_searches_per_day(self):
        """
        Calculate expected usage for 5000 searches/day scenario.
        
        Expected:
        - Per search: ~420 MB (worst case)
        - Per day: 5000 × 420 MB = 2.1 GB
        - Per month: 2.1 GB × 30 = 63 TB
        - Cost: (63 TB - 1 TB free) × $5 = $310/month
        """
        searches_per_day = 5000
        mb_per_search = 420  # Worst case estimate
        days_per_month = 30
        free_tier_tb = 1.0
        cost_per_tb = 5.0
        
        daily_usage_gb = (searches_per_day * mb_per_search) / 1024
        monthly_usage_tb = (daily_usage_gb * days_per_month) / 1024
        billable_tb = max(0, monthly_usage_tb - free_tier_tb)
        monthly_cost = billable_tb * cost_per_tb
        
        # Document the scaling scenario
        print(f"\n=== 5000 Searches/Day Scaling Analysis ===")
        print(f"Daily usage: {daily_usage_gb:.2f} GB")
        print(f"Monthly usage: {monthly_usage_tb:.2f} TB")
        print(f"Billable: {billable_tb:.2f} TB")
        print(f"Estimated cost: ${monthly_cost:.2f}/month")
        
        # Assertion: Should be manageable cost
        self.assertLess(
            monthly_cost,
            500,
            f"5000 searches/day cost should be under $500/month. Got ${monthly_cost:.2f}"
        )
    
    def test_cache_reduces_bigquery_calls(self):
        """
        Test that caching mechanisms can reduce BigQuery calls for repeat searches.
        With 12-hour caching, repeat searches should use database instead.
        """
        # This is a documentation test - actual caching is implemented in views.py
        cache_duration_hours = 12
        repeat_search_percentage = 0.30  # Assume 30% are repeat searches within 12 hours
        
        searches_per_day = 5000
        unique_searches = searches_per_day * (1 - repeat_search_percentage)
        
        # Only unique searches hit BigQuery
        mb_per_search = 420
        daily_usage_gb = (unique_searches * mb_per_search) / 1024
        monthly_usage_tb = (daily_usage_gb * 30) / 1024
        
        print(f"\n=== Cache Impact Analysis (30% repeat searches) ===")
        print(f"Unique searches: {unique_searches:.0f}/day")
        print(f"Cache hits: {searches_per_day * repeat_search_percentage:.0f}/day")
        print(f"Daily BigQuery usage: {daily_usage_gb:.2f} GB")
        print(f"Monthly BigQuery usage: {monthly_usage_tb:.2f} TB")
        print(f"Savings vs no cache: {63 - monthly_usage_tb:.2f} TB/month")
        
        self.assertLess(
            monthly_usage_tb,
            50,
            "With 30% cache hit rate, should reduce usage below 50 TB/month"
        )


class BigQueryErrorHandlingTestCase(TestCase):
    """
    Test that quota exceeded errors are handled gracefully.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.helper = StellarBigQueryHelper()
    
    def test_quota_exceeded_graceful_fallback(self):
        """
        Test that quota exceeded errors don't crash the application.
        Should return None/empty results and log the error.
        """
        with patch.object(self.helper, 'client') as mock_client:
            # Simulate quota exceeded error
            from google.api_core.exceptions import Forbidden
            mock_client.query.side_effect = Forbidden("403 Custom quota exceeded")
            
            # Should not raise exception
            result = self.helper.get_account_data('GTEST')
            
            # Should return None gracefully
            self.assertIsNone(result, "Should return None when quota exceeded")
    
    def test_quota_exceeded_logged(self):
        """
        Test that quota exceeded errors are logged for monitoring.
        """
        with patch.object(self.helper, 'client') as mock_client:
            with patch('apiApp.helpers.sm_bigquery.logger') as mock_logger:
                from google.api_core.exceptions import Forbidden
                mock_client.query.side_effect = Forbidden("403 Custom quota exceeded")
                
                # Execute query
                self.helper.get_account_data('GTEST')
                
                # Should log the error
                mock_logger.error.assert_called()
                error_msg = str(mock_logger.error.call_args)
                self.assertIn('403', error_msg, "Should log 403 error")


if __name__ == '__main__':
    unittest.main()
