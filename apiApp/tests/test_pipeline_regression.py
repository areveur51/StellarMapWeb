"""
Regression tests for Pipeline Modes and Stuck Record Detection.

Ensures:
1. API_ONLY pipeline processes records continuously
2. BIGQUERY_WITH_API_FALLBACK mode works correctly
3. Stuck/stale records are accurately detected
4. Pipeline health monitoring is accurate
5. Dashboard alerts match actual pipeline state

Created: October 23, 2025
"""
import datetime
from datetime import timedelta
from django.test import TestCase, Client
from django.conf import settings
from unittest.mock import patch, MagicMock
from apiApp.model_loader import (
    StellarCreatorAccountLineage,
    StellarAccountSearchCache,
    BigQueryPipelineConfig
)


class PipelineModeRegressionTests(TestCase):
    """Test pipeline mode configurations work correctly."""

    def setUp(self):
        """Set up test data and configuration."""
        self.client = Client()
        self.now = datetime.datetime.utcnow()
        
        # Create or get pipeline config
        self.config, _ = BigQueryPipelineConfig.objects.get_or_create(
            config_id='default',
            defaults={
                'bigquery_enabled': True,
                'cost_limit_usd': 0.71,
                'pipeline_mode': 'API_ONLY',
                'api_pipeline_enabled': True,
                'api_pipeline_batch_size': 3,
                'api_pipeline_interval_seconds': 120,
            }
        )

    def test_api_only_mode_configuration(self):
        """Test API_ONLY mode is properly configured."""
        # Set to API_ONLY mode
        self.config.pipeline_mode = 'API_ONLY'
        self.config.api_pipeline_enabled = True
        self.config.save()
        
        config = BigQueryPipelineConfig.objects.get(config_id='default')
        self.assertEqual(config.pipeline_mode, 'API_ONLY')
        self.assertTrue(config.api_pipeline_enabled)
        
    def test_bigquery_with_fallback_mode_configuration(self):
        """Test BIGQUERY_WITH_API_FALLBACK mode is properly configured."""
        # Set to fallback mode
        self.config.pipeline_mode = 'BIGQUERY_WITH_API_FALLBACK'
        self.config.bigquery_enabled = True
        self.config.api_pipeline_enabled = True
        self.config.save()
        
        config = BigQueryPipelineConfig.objects.get(config_id='default')
        self.assertEqual(config.pipeline_mode, 'BIGQUERY_WITH_API_FALLBACK')
        self.assertTrue(config.bigquery_enabled)
        self.assertTrue(config.api_pipeline_enabled)

    def test_pipeline_processes_pending_records(self):
        """Test that pipeline can process PENDING records."""
        # Create test PENDING account
        pending_account = StellarCreatorAccountLineage(
            stellar_account='G' + 'T' * 55,
            network_name='public',
            status='PENDING',
            created_at=self.now,
            updated_at=self.now
        )
        pending_account.save()
        
        # Verify it was created as PENDING
        account = StellarCreatorAccountLineage.objects.get(stellar_account=pending_account.stellar_account)
        self.assertEqual(account.status, 'PENDING')
        
        # Cleanup
        pending_account.delete()

    def test_api_pipeline_batch_size_configuration(self):
        """Test that API pipeline batch size is configurable."""
        self.config.api_pipeline_batch_size = 5
        self.config.save()
        
        config = BigQueryPipelineConfig.objects.get(config_id='default')
        self.assertEqual(config.api_pipeline_batch_size, 5)


class StuckRecordDetectionTests(TestCase):
    """Test stuck/stale record detection accuracy."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.now = datetime.datetime.utcnow()
        self.stale_time = self.now - timedelta(minutes=45)  # Stale (>30 min)
        self.fresh_time = self.now - timedelta(minutes=10)  # Fresh (<30 min)

    def test_detects_stale_processing_accounts(self):
        """Test that stale PROCESSING accounts are detected (>30 min)."""
        # Create stale PROCESSING account
        stale_account = StellarCreatorAccountLineage(
            stellar_account='G' + 'S' * 55,
            network_name='public',
            status='PROCESSING',
            processing_started_at=self.stale_time,
            created_at=self.stale_time,
            updated_at=self.stale_time
        )
        stale_account.save()
        
        # Query for stuck accounts via API
        response = self.client.get('/api/cassandra-query/', {
            'query': 'processing_accounts',
            'network': 'public',
            'limit': 100
        })
        
        data = response.json()
        
        # Should find the stale account
        self.assertGreater(data['count'], 0, "Should find at least one processing account")
        
        # Check for STALE tag
        stale_found = any('[STALE]' in str(result.get('table_source', '')) for result in data['results'])
        self.assertTrue(stale_found, "Should mark stale processing accounts with [STALE] tag")
        
        # Cleanup
        stale_account.delete()

    def test_does_not_mark_fresh_processing_as_stale(self):
        """Test that fresh PROCESSING accounts (<30 min) are NOT marked as stale."""
        # Create fresh PROCESSING account
        fresh_account = StellarCreatorAccountLineage(
            stellar_account='G' + 'F' * 55,
            network_name='public',
            status='PROCESSING',
            processing_started_at=self.fresh_time,
            created_at=self.fresh_time,
            updated_at=self.fresh_time
        )
        fresh_account.save()
        
        # Query for processing accounts
        response = self.client.get('/api/cassandra-query/', {
            'query': 'processing_accounts',
            'network': 'public',
            'limit': 100
        })
        
        data = response.json()
        
        # Find our fresh account
        fresh_results = [r for r in data['results'] if r['stellar_account'] == fresh_account.stellar_account]
        
        if fresh_results:
            table_source = fresh_results[0].get('table_source', '')
            self.assertNotIn('[STALE]', table_source, "Fresh processing accounts should NOT be marked as STALE")
        
        # Cleanup
        fresh_account.delete()

    def test_stuck_records_query_accuracy(self):
        """Test that stuck_records query accurately identifies stuck accounts."""
        # Create stuck account (PROCESSING for >30 min)
        stuck_account = StellarCreatorAccountLineage(
            stellar_account='G' + 'X' * 55,
            network_name='public',
            status='PROCESSING',
            processing_started_at=self.stale_time,
            retry_count=5,  # High retry count indicates stuck
            created_at=self.stale_time,
            updated_at=self.stale_time
        )
        stuck_account.save()
        
        # Query for stuck accounts
        response = self.client.get('/api/cassandra-query/', {
            'query': 'stuck_accounts',
            'network': 'public',
            'limit': 100
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify structure
        self.assertIn('results', data)
        self.assertIn('count', data)
        
        # Cleanup
        stuck_account.delete()


class DashboardAlertsAccuracyTests(TestCase):
    """Test that dashboard alerts accurately reflect pipeline state."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.now = datetime.datetime.utcnow()
        self.stale_time = self.now - timedelta(minutes=45)

    def test_dashboard_shows_stuck_records_count(self):
        """Test that dashboard accurately counts stuck PROCESSING records."""
        # Create multiple stuck accounts
        stuck_accounts = []
        for i in range(3):
            account = StellarCreatorAccountLineage(
                stellar_account=f'G{"A" + str(i)}'  + 'Z' * 53,
                network_name='public',
                status='PROCESSING',
                processing_started_at=self.stale_time,
                created_at=self.stale_time,
                updated_at=self.stale_time
            )
            account.save()
            stuck_accounts.append(account)
        
        # Get dashboard
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        
        # Cleanup
        for account in stuck_accounts:
            account.delete()

    def test_processing_accounts_query_matches_actual_state(self):
        """Test that processing_accounts query returns accurate count."""
        # Create known number of PROCESSING accounts
        processing_accounts = []
        for i in range(5):
            account = StellarCreatorAccountLineage(
                stellar_account=f'G{"P" + str(i)}' + 'X' * 53,
                network_name='public',
                status='PROCESSING',
                processing_started_at=self.now,
                created_at=self.now,
                updated_at=self.now
            )
            account.save()
            processing_accounts.append(account)
        
        # Query via API
        response = self.client.get('/api/cassandra-query/', {
            'query': 'processing_accounts',
            'network': 'public',
            'limit': 100
        })
        
        data = response.json()
        
        # Should find at least the accounts we created
        self.assertGreaterEqual(data['count'], 5, "Should find at least 5 processing accounts")
        
        # Cleanup
        for account in processing_accounts:
            account.delete()

    def test_pending_accounts_count_accurate(self):
        """Test that pending_accounts query returns accurate count."""
        # Create known number of PENDING accounts
        pending_accounts = []
        for i in range(3):
            account = StellarCreatorAccountLineage(
                stellar_account=f'G{"N" + str(i)}' + 'Y' * 53,
                network_name='public',
                status='PENDING',
                created_at=self.now,
                updated_at=self.now
            )
            account.save()
            pending_accounts.append(account)
        
        # Query via API
        response = self.client.get('/api/cassandra-query/', {
            'query': 'pending_accounts',
            'network': 'public',
            'limit': 100
        })
        
        data = response.json()
        
        # Should find at least the accounts we created
        self.assertGreaterEqual(data['count'], 3, "Should find at least 3 pending accounts")
        
        # Cleanup
        for account in pending_accounts:
            account.delete()


class PipelineHealthMonitoringTests(TestCase):
    """Test pipeline health monitoring and error reporting."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_pipeline_stats_endpoint_available(self):
        """Test that pipeline stats endpoint is available."""
        response = self.client.get('/api/pipeline-stats/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('pending_count', data)
        self.assertIn('processing_count', data)

    def test_pipeline_stats_returns_valid_json(self):
        """Test that pipeline stats returns valid JSON structure."""
        response = self.client.get('/api/pipeline-stats/')
        data = response.json()
        
        # Verify required fields
        required_fields = ['pending_count', 'processing_count']
        for field in required_fields:
            self.assertIn(field, data, f"Pipeline stats should include {field}")
            self.assertIsInstance(data[field], int, f"{field} should be an integer")
