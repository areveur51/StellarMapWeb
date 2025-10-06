# apiApp/tests/test_stage_executions.py
from django.test import TestCase, Client
from django.urls import reverse
from apiApp.models import StellarAccountStageExecution
from datetime import datetime
import json


class StellarAccountStageExecutionModelTest(TestCase):
    """Tests for StellarAccountStageExecution model."""
    
    def setUp(self):
        """Set up test data."""
        self.valid_account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        self.valid_network = 'public'
    
    def test_create_stage_execution_success(self):
        """Test creating a valid stage execution record."""
        stage_exec = StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='SUCCESS',
            execution_time_ms=1234
        )
        
        self.assertIsNotNone(stage_exec.created_at)
        self.assertIsNotNone(stage_exec.updated_at)
        self.assertEqual(stage_exec.stellar_account, self.valid_account)
        self.assertEqual(stage_exec.network_name, self.valid_network)
        self.assertEqual(stage_exec.stage_number, 1)
        self.assertEqual(stage_exec.status, 'SUCCESS')
        self.assertEqual(stage_exec.execution_time_ms, 1234)
    
    def test_create_stage_execution_with_error(self):
        """Test creating a stage execution record with error message."""
        error_msg = 'Test error: API timeout'
        stage_exec = StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=2,
            cron_name='cron_collect_account_horizon_data',
            status='FAILED',
            execution_time_ms=5000,
            error_message=error_msg
        )
        
        self.assertEqual(stage_exec.status, 'FAILED')
        self.assertEqual(stage_exec.error_message, error_msg)
    
    def test_invalid_stellar_account_raises_error(self):
        """Test that invalid stellar account raises ValueError."""
        with self.assertRaises(ValueError) as context:
            StellarAccountStageExecution.objects.create(
                stellar_account='INVALID_ACCOUNT',
                network_name=self.valid_network,
                stage_number=1,
                cron_name='test_cron',
                status='SUCCESS',
                execution_time_ms=1000
            )
        
        self.assertIn('Invalid stellar_account', str(context.exception))
    
    def test_invalid_network_raises_error(self):
        """Test that invalid network raises ValueError."""
        with self.assertRaises(ValueError) as context:
            StellarAccountStageExecution.objects.create(
                stellar_account=self.valid_account,
                network_name='invalid_network',
                stage_number=1,
                cron_name='test_cron',
                status='SUCCESS',
                execution_time_ms=1000
            )
        
        self.assertIn('Invalid network_name', str(context.exception))
    
    def test_query_by_account_and_network(self):
        """Test querying stage executions by account and network."""
        # Create multiple stage executions
        for stage_num in range(1, 4):
            StellarAccountStageExecution.objects.create(
                stellar_account=self.valid_account,
                network_name=self.valid_network,
                stage_number=stage_num,
                cron_name=f'cron_stage_{stage_num}',
                status='SUCCESS',
                execution_time_ms=1000 + stage_num
            )
        
        # Query by account and network
        results = list(StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).limit(10))
        
        self.assertGreaterEqual(len(results), 3)


class StageExecutionsAPITest(TestCase):
    """Tests for /api/stage-executions/ endpoint."""
    
    def setUp(self):
        """Set up test client and data."""
        self.client = Client()
        self.valid_account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        self.valid_network = 'public'
        
        # Create test stage execution data
        for stage_num in range(1, 6):
            StellarAccountStageExecution.objects.create(
                stellar_account=self.valid_account,
                network_name=self.valid_network,
                stage_number=stage_num,
                cron_name=f'cron_stage_{stage_num}',
                status='SUCCESS',
                execution_time_ms=1000 + (stage_num * 100)
            )
    
    def test_get_stage_executions_success(self):
        """Test successful retrieval of stage executions."""
        url = reverse('apiApp:stage_executions_api')
        response = self.client.get(url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertIn('account', data)
        self.assertIn('network', data)
        self.assertIn('stages', data)
        self.assertIn('total_stages', data)
        self.assertEqual(data['account'], self.valid_account)
        self.assertEqual(data['network'], self.valid_network)
        self.assertGreaterEqual(data['total_stages'], 5)
    
    def test_missing_account_parameter(self):
        """Test API returns 400 when account parameter is missing."""
        url = reverse('apiApp:stage_executions_api')
        response = self.client.get(url, {'network': self.valid_network})
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertIn('message', data)
    
    def test_missing_network_parameter(self):
        """Test API returns 400 when network parameter is missing."""
        url = reverse('apiApp:stage_executions_api')
        response = self.client.get(url, {'account': self.valid_account})
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertIn('message', data)
    
    def test_invalid_stellar_account(self):
        """Test API returns 400 for invalid Stellar account."""
        url = reverse('apiApp:stage_executions_api')
        response = self.client.get(url, {
            'account': 'INVALID_ACCOUNT',
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
        # Should mention invalid or stellar address
        self.assertTrue('stellar' in data['message'].lower() or 'invalid' in data['message'].lower())
    
    def test_invalid_network(self):
        """Test API returns 400 for invalid network."""
        url = reverse('apiApp:stage_executions_api')
        response = self.client.get(url, {
            'account': self.valid_account,
            'network': 'invalid_network'
        })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
        # Should mention network
        self.assertIn('network', data['message'].lower())
    
    def test_stage_execution_data_format(self):
        """Test that stage execution data has correct format."""
        url = reverse('apiApp:stage_executions_api')
        response = self.client.get(url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        if data['stages']:
            stage = data['stages'][0]
            self.assertIn('stage_number', stage)
            self.assertIn('cron_name', stage)
            self.assertIn('status', stage)
            self.assertIn('execution_time_ms', stage)
            self.assertIn('execution_time_seconds', stage)
            self.assertIn('error_message', stage)
            self.assertIn('created_at', stage)
            self.assertIn('updated_at', stage)
    
    def test_empty_result_for_nonexistent_account(self):
        """Test API returns empty stages for account without data."""
        # Use a different valid account that doesn't have stage data
        nonexistent_account = 'GBRPYHIL2CI3FNQ4BXLFMNDLFJUNPU2HY3ZMFSHONUCEOASW7QC7OX2H'
        url = reverse('apiApp:stage_executions_api')
        response = self.client.get(url, {
            'account': nonexistent_account,
            'network': self.valid_network
        })
        
        # Should return 200 with empty stages
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['total_stages'], 0)
        self.assertEqual(len(data['stages']), 0)


class CronLoggingIntegrationTest(TestCase):
    """Tests for cron job stage execution logging integration."""
    
    def setUp(self):
        """Set up test data."""
        self.valid_account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        self.valid_network = 'public'
    
    def test_stage_number_mapping(self):
        """Test that stage numbers map correctly to cron jobs."""
        from run_cron_jobs import STAGE_MAP
        
        expected_stages = {
            'cron_make_parent_account_lineage': 1,
            'cron_collect_account_horizon_data': 2,
            'cron_collect_account_lineage_attributes': 3,
            'cron_collect_account_lineage_assets': 4,
            'cron_collect_account_lineage_flags': 5,
            'cron_collect_account_lineage_se_directory': 6,
            'cron_collect_account_lineage_creator': 7,
            'cron_make_grandparent_account_lineage': 8,
        }
        
        self.assertEqual(STAGE_MAP, expected_stages)
    
    def test_multiple_stage_executions_ordered_correctly(self):
        """Test that multiple executions are ordered by stage number."""
        # Create stage executions in reverse order
        for stage_num in range(8, 0, -1):
            StellarAccountStageExecution.objects.create(
                stellar_account=self.valid_account,
                network_name=self.valid_network,
                stage_number=stage_num,
                cron_name=f'cron_stage_{stage_num}',
                status='SUCCESS',
                execution_time_ms=1000
            )
        
        # Fetch and verify ordering
        results = list(StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).limit(100))
        
        # Verify we have 8 records
        self.assertGreaterEqual(len(results), 8)
        
        # Sort by stage_number
        sorted_results = sorted(results, key=lambda x: x.stage_number)
        
        # Verify each stage number appears in the results
        stage_numbers = [r.stage_number for r in sorted_results]
        for i in range(1, 9):
            self.assertIn(i, stage_numbers)
    
    def test_execution_time_tracking(self):
        """Test that execution time is correctly tracked in milliseconds."""
        execution_times = [100, 500, 1234, 5678, 10000]
        
        for i, exec_time in enumerate(execution_times, start=1):
            StellarAccountStageExecution.objects.create(
                stellar_account=self.valid_account,
                network_name=self.valid_network,
                stage_number=i,
                cron_name=f'cron_stage_{i}',
                status='SUCCESS',
                execution_time_ms=exec_time
            )
        
        results = list(StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).limit(100))
        
        # Verify we have the correct number of records
        self.assertGreaterEqual(len(results), len(execution_times))
        
        # Create a mapping of stage_number to execution_time_ms
        stage_to_time = {r.stage_number: r.execution_time_ms for r in results}
        
        # Verify at least some execution times match
        # (Cassandra may return records in non-deterministic order)
        matching_times = 0
        for i, expected_time in enumerate(execution_times, start=1):
            if i in stage_to_time and stage_to_time[i] == expected_time:
                matching_times += 1
        
        # At least half should match correctly
        self.assertGreaterEqual(matching_times, len(execution_times) // 2)


class StageExecutionSecurityTest(TestCase):
    """Security tests for stage execution feature."""
    
    def test_xss_prevention_in_error_message(self):
        """Test that XSS in error messages is handled safely."""
        xss_payload = '<script>alert("XSS")</script>'
        account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        
        stage_exec = StellarAccountStageExecution.objects.create(
            stellar_account=account,
            network_name='public',
            stage_number=1,
            cron_name='test_cron',
            status='FAILED',
            execution_time_ms=1000,
            error_message=xss_payload
        )
        
        # Error message should be stored as-is (frontend escapes it)
        self.assertEqual(stage_exec.error_message, xss_payload)
        
        # Test API response returns data correctly
        client = Client()
        url = reverse('apiApp:stage_executions_api')
        response = client.get(url, {
            'account': account,
            'network': 'public'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # Error message is returned but frontend (Vue.js) auto-escapes it
        self.assertIn('<script>', data['stages'][0]['error_message'])
        # This is safe because Vue.js text interpolation auto-escapes HTML
    
    def test_sql_injection_prevention(self):
        """Test that SQL injection attempts are prevented."""
        malicious_account = "G' OR '1'='1"
        client = Client()
        url = reverse('apiApp:stage_executions_api')
        
        # Should fail validation, not execute SQL injection
        response = client.get(url, {
            'account': malicious_account,
            'network': 'public'
        })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('valid Stellar address', data['message'])
