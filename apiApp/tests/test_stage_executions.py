# apiApp/tests/test_stage_executions.py
from django.test import TestCase, Client
from django.urls import reverse
from apiApp.models import StellarAccountStageExecution
from apiApp.helpers.sm_stage_execution import initialize_stage_executions, update_stage_execution
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
                stellar_account='invalid_account',
                network_name=self.valid_network,
                stage_number=1,
                cron_name='test_cron',
                status='PENDING',
                execution_time_ms=0
            )
        
        self.assertIn('Invalid Stellar account', str(context.exception))
    
    def test_invalid_network_name_raises_error(self):
        """Test that invalid network name raises ValueError."""
        with self.assertRaises(ValueError) as context:
            StellarAccountStageExecution.objects.create(
                stellar_account=self.valid_account,
                network_name='invalid_network',
                stage_number=1,
                cron_name='test_cron',
                status='PENDING',
                execution_time_ms=0
            )
        
        self.assertIn('Invalid network name', str(context.exception))
    
    def test_stage_number_validation(self):
        """Test that stage number must be between 1 and 8."""
        with self.assertRaises(ValueError) as context:
            StellarAccountStageExecution.objects.create(
                stellar_account=self.valid_account,
                network_name=self.valid_network,
                stage_number=0,
                cron_name='test_cron',
                status='PENDING',
                execution_time_ms=0
            )
        
        self.assertIn('Stage number must be between 1 and 8', str(context.exception))
        
        with self.assertRaises(ValueError) as context:
            StellarAccountStageExecution.objects.create(
                stellar_account=self.valid_account,
                network_name=self.valid_network,
                stage_number=9,
                cron_name='test_cron',
                status='PENDING',
                execution_time_ms=0
            )
        
        self.assertIn('Stage number must be between 1 and 8', str(context.exception))


class StageExecutionAPITest(TestCase):
    """Tests for stage execution API endpoint."""
    
    def setUp(self):
        """Set up test client and test data."""
        self.client = Client()
        self.url = reverse('apiApp:stage_executions_api')
        self.valid_account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        self.valid_network = 'public'
        
        # Clean up existing test data
        StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).delete()
    
    def test_get_stage_executions_success(self):
        """Test successful retrieval of stage executions."""
        # Create test stage execution
        stage_exec = StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='SUCCESS',
            execution_time_ms=1500
        )
        
        response = self.client.get(self.url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertEqual(data['account'], self.valid_account)
        self.assertEqual(data['network'], self.valid_network)
        self.assertEqual(len(data['stages']), 1)
        
        stage = data['stages'][0]
        self.assertEqual(stage['stage_number'], 1)
        self.assertEqual(stage['status'], 'SUCCESS')
        self.assertEqual(stage['execution_time_ms'], 1500)
    
    def test_missing_account_parameter(self):
        """Test that missing account parameter returns 400."""
        response = self.client.get(self.url, {
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('account', data['message'].lower())
    
    def test_missing_network_parameter(self):
        """Test that missing network parameter returns 400."""
        response = self.client.get(self.url, {
            'account': self.valid_account
        })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('network', data['message'].lower())
    
    def test_invalid_account_format(self):
        """Test that invalid account format returns 400."""
        response = self.client.get(self.url, {
            'account': 'invalid',
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('valid Stellar address', data['message'])
    
    def test_invalid_network_value(self):
        """Test that invalid network value returns 400."""
        response = self.client.get(self.url, {
            'account': self.valid_account,
            'network': 'invalid'
        })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('must be', data['message'])
    
    def test_no_stages_found(self):
        """Test response when no stage executions exist."""
        # Use a different account that has no records
        other_account = 'GBKTJSNMUOTQYSCLXXBZIZLKZOADQCTJJF2BHSRTBCJR3GJJQ7BGDUED'
        
        response = self.client.get(self.url, {
            'account': other_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['stages']), 0)


class StageExecutionCronTest(TestCase):
    """Tests for stage execution tracking during cron job execution."""
    
    def setUp(self):
        """Set up test data."""
        self.valid_account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        self.valid_network = 'public'
        
        # Clean up existing test data
        StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).delete()
    
    def test_stage_logging_creates_records(self):
        """Test that stage execution logging creates records."""
        StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='SUCCESS',
            execution_time_ms=1500
        )
        
        StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=2,
            cron_name='cron_collect_account_horizon_data',
            status='SUCCESS',
            execution_time_ms=2000
        )
        
        # Clean up before querying (deterministic results)
        StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).limit(1000).delete()
        
        # Recreate for assertion
        stage1 = StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='SUCCESS',
            execution_time_ms=1500
        )
        
        stage2 = StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=2,
            cron_name='cron_collect_account_horizon_data',
            status='SUCCESS',
            execution_time_ms=2000
        )
        
        # Verify both stages were created
        all_stages = list(StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).all())
        
        self.assertEqual(len(all_stages), 2)
        stage_numbers = [s.stage_number for s in all_stages]
        self.assertIn(1, stage_numbers)
        self.assertIn(2, stage_numbers)
    
    def test_stage_execution_time_tracking(self):
        """Test that execution time is accurately tracked."""
        execution_times = {1: 1500, 2: 2000, 3: 1800}
        
        # Clean up before test
        StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).delete()
        
        for stage_num, exec_time in execution_times.items():
            StellarAccountStageExecution.objects.create(
                stellar_account=self.valid_account,
                network_name=self.valid_network,
                stage_number=stage_num,
                cron_name=f'cron_stage_{stage_num}',
                status='SUCCESS',
                execution_time_ms=exec_time
            )
        
        # Verify execution times
        stages = list(StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).all())
        
        actual_times = {s.stage_number: s.execution_time_ms for s in stages}
        
        for stage_num, expected_time in execution_times.items():
            self.assertIn(stage_num, actual_times, 
                         f"Stage {stage_num} not found in results")
            self.assertEqual(actual_times[stage_num], expected_time,
                           f"Stage {stage_num}: expected {expected_time}ms, got {actual_times[stage_num]}ms")


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


class StageExecutionHelperTest(TestCase):
    """Tests for stage execution helper functions."""
    
    def setUp(self):
        """Set up test data."""
        self.valid_account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        self.valid_network = 'public'
        
        # Clean up existing test data
        StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).delete()
    
    def test_initialize_stage_executions_creates_all_stages(self):
        """Test that initialize_stage_executions creates all 8 stages."""
        created_count = initialize_stage_executions(self.valid_account, self.valid_network)
        
        self.assertEqual(created_count, 8, "Should create all 8 stages")
        
        # Verify all 8 stages exist
        stages = list(StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).all())
        
        self.assertEqual(len(stages), 8, "Should have 8 stage records")
        
        # Verify all stage numbers are present
        stage_numbers = sorted([s.stage_number for s in stages])
        self.assertEqual(stage_numbers, [1, 2, 3, 4, 5, 6, 7, 8])
        
        # Verify all stages start with PENDING status
        for stage in stages:
            self.assertEqual(stage.status, 'PENDING', f"Stage {stage.stage_number} should be PENDING")
            self.assertEqual(stage.execution_time_ms, 0, f"Stage {stage.stage_number} should have 0ms execution time")
    
    def test_initialize_stage_executions_skips_existing_stages(self):
        """Test that initialize_stage_executions skips already existing stages."""
        # Create stage 1 manually
        StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='SUCCESS',
            execution_time_ms=1500
        )
        
        # Initialize should create 7 more stages (skipping stage 1)
        created_count = initialize_stage_executions(self.valid_account, self.valid_network)
        
        self.assertEqual(created_count, 7, "Should create 7 new stages (stage 1 already exists)")
        
        # Verify total of 8 stages
        total_stages = list(StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).all())
        
        self.assertEqual(len(total_stages), 8)
        
        # Verify stage 1 was not overwritten
        stage1 = next(s for s in total_stages if s.stage_number == 1)
        self.assertEqual(stage1.status, 'SUCCESS', "Stage 1 should remain SUCCESS")
        self.assertEqual(stage1.execution_time_ms, 1500, "Stage 1 execution time should be preserved")
    
    def test_update_stage_execution_updates_existing_stage(self):
        """Test that update_stage_execution updates an existing stage record."""
        # Create initial stage
        initial_stage = StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='PENDING',
            execution_time_ms=0
        )
        
        # Update the stage
        updated_stage = update_stage_execution(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            status='SUCCESS',
            execution_time_ms=2500,
            error_message=''
        )
        
        self.assertEqual(updated_stage.status, 'SUCCESS')
        self.assertEqual(updated_stage.execution_time_ms, 2500)
        
        # Verify only one record exists for this stage
        all_stage1_records = list(StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1
        ).all())
        
        self.assertEqual(len(all_stage1_records), 1, "Should only have one record for stage 1")
    
    def test_update_stage_execution_creates_if_not_exists(self):
        """Test that update_stage_execution creates a record if it doesn't exist."""
        # Update stage that doesn't exist yet
        new_stage = update_stage_execution(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=2,
            status='IN_PROGRESS',
            execution_time_ms=500,
            error_message=''
        )
        
        self.assertIsNotNone(new_stage)
        self.assertEqual(new_stage.stage_number, 2)
        self.assertEqual(new_stage.status, 'IN_PROGRESS')
        self.assertEqual(new_stage.execution_time_ms, 500)
        
        # Verify record was created
        stage_records = list(StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=2
        ).all())
        
        self.assertEqual(len(stage_records), 1)
    
    def test_update_stage_execution_with_error_message(self):
        """Test that update_stage_execution properly handles error messages."""
        error_msg = 'API timeout: Connection to Horizon failed after 30 seconds'
        
        stage = update_stage_execution(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=3,
            status='FAILED',
            execution_time_ms=30000,
            error_message=error_msg
        )
        
        self.assertEqual(stage.status, 'FAILED')
        self.assertEqual(stage.error_message, error_msg)
        self.assertEqual(stage.execution_time_ms, 30000)
    
    def test_full_workflow_initialize_then_update(self):
        """Test complete workflow: initialize all stages, then update them as they execute."""
        # Step 1: Initialize all stages
        created_count = initialize_stage_executions(self.valid_account, self.valid_network)
        self.assertEqual(created_count, 8)
        
        # Step 2: Simulate stage 1 execution
        update_stage_execution(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            status='SUCCESS',
            execution_time_ms=1500
        )
        
        # Step 3: Simulate stage 2 execution
        update_stage_execution(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=2,
            status='SUCCESS',
            execution_time_ms=2000
        )
        
        # Step 4: Simulate stage 3 failure
        update_stage_execution(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=3,
            status='FAILED',
            execution_time_ms=500,
            error_message='API error'
        )
        
        # Verify final state
        all_stages = list(StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).all())
        
        self.assertEqual(len(all_stages), 8, "Should still have all 8 stages")
        
        # Verify stage statuses
        stage_status_map = {s.stage_number: s.status for s in all_stages}
        self.assertEqual(stage_status_map[1], 'SUCCESS')
        self.assertEqual(stage_status_map[2], 'SUCCESS')
        self.assertEqual(stage_status_map[3], 'FAILED')
        self.assertEqual(stage_status_map[4], 'PENDING')  # Remaining stages still pending
        self.assertEqual(stage_status_map[5], 'PENDING')
        self.assertEqual(stage_status_map[6], 'PENDING')
        self.assertEqual(stage_status_map[7], 'PENDING')
        self.assertEqual(stage_status_map[8], 'PENDING')
