import json
from django.test import TestCase, Client
from datetime import datetime, timezone
from apiApp.models import StellarAccountStageExecution
from apiApp.helpers.sm_stage_execution import initialize_stage_executions, update_stage_execution


class StageTableDisplayTest(TestCase):
    """Test that stage execution table displays Status and Time columns correctly."""
    
    def setUp(self):
        self.client = Client()
        self.stellar_account = 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB'
        self.network = 'public'
    
    def test_api_returns_correct_fields(self):
        """Test that API returns status and execution_time_seconds fields."""
        # Initialize stages with test data
        initialize_stage_executions(self.stellar_account, self.network)
        
        # Update a stage with specific status and time
        update_stage_execution(
            stellar_account=self.stellar_account,
            network_name=self.network,
            stage_number=1,
            status='SUCCESS',
            execution_time_ms=2500
        )
        
        # Fetch from API
        response = self.client.get(
            '/api/stage-executions/',
            {'account': self.stellar_account, 'network': self.network}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Verify structure
        self.assertIn('stages', data)
        self.assertTrue(len(data['stages']) > 0)
        
        # Check first stage has all required fields
        first_stage = data['stages'][0]
        self.assertIn('status', first_stage)
        self.assertIn('execution_time_seconds', first_stage)
        self.assertIn('execution_time_ms', first_stage)
        
        # Verify values
        self.assertEqual(first_stage['status'], 'SUCCESS')
        self.assertEqual(first_stage['execution_time_ms'], 2500)
        self.assertEqual(first_stage['execution_time_seconds'], 2.5)
        
        print(f"✓ API returns status: {first_stage['status']}")
        print(f"✓ API returns execution_time_seconds: {first_stage['execution_time_seconds']}")
    
    def test_all_status_values_returned(self):
        """Test that different status values are correctly returned."""
        # Initialize stages
        initialize_stage_executions(self.stellar_account, self.network)
        
        # Update stages with different statuses
        statuses = ['SUCCESS', 'FAILED', 'PENDING', 'TIMEOUT']
        for i, status in enumerate(statuses, 1):
            if i <= 8:  # We have 8 stages
                update_stage_execution(
                    stellar_account=self.stellar_account,
                    network_name=self.network,
                    stage_number=i,
                    status=status,
                    execution_time_ms=i * 1000
                )
        
        # Fetch from API
        response = self.client.get(
            '/api/stage-executions/',
            {'account': self.stellar_account, 'network': self.network}
        )
        
        data = json.loads(response.content)
        
        # Verify each stage has the correct status
        for stage in data['stages']:
            stage_num = stage['stage_number']
            if stage_num <= len(statuses):
                expected_status = statuses[stage_num - 1]
                self.assertEqual(stage['status'], expected_status)
                print(f"✓ Stage {stage_num} status: {stage['status']}")
                
                # Verify time calculation
                expected_seconds = stage_num
                self.assertEqual(stage['execution_time_seconds'], expected_seconds)
                print(f"✓ Stage {stage_num} time: {stage['execution_time_seconds']}s")