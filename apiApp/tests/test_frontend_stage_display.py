import json
from django.test import TestCase, Client
from apiApp.helpers.sm_stage_execution import initialize_stage_executions, update_stage_execution


class FrontendStageDisplayTest(TestCase):
    """Test that verifies the frontend table display issue is fixed."""
    
    def setUp(self):
        self.client = Client()
        self.stellar_account = 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB'
        self.network = 'public'
    
    def test_status_and_time_fields_exist_in_api_response(self):
        """Verify API returns correct status and execution_time_seconds fields."""
        # Initialize stages
        initialize_stage_executions(self.stellar_account, self.network)
        
        # Update multiple stages with different statuses and times
        test_data = [
            (1, 'SUCCESS', 1500),
            (2, 'PENDING', 0),
            (3, 'FAILED', 3000),
            (4, 'TIMEOUT', 30000),
        ]
        
        for stage_num, status, time_ms in test_data:
            update_stage_execution(
                stellar_account=self.stellar_account,
                network_name=self.network,
                stage_number=stage_num,
                status=status,
                execution_time_ms=time_ms
            )
        
        # Fetch from API
        response = self.client.get(
            '/api/stage-executions/',
            {'account': self.stellar_account, 'network': self.network}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Verify all stages have required fields
        self.assertIn('stages', data)
        self.assertGreaterEqual(len(data['stages']), 4)
        
        # Check each stage has the correct structure
        for stage in data['stages']:
            # Verify required fields exist
            self.assertIn('status', stage, "Missing 'status' field")
            self.assertIn('execution_time_seconds', stage, "Missing 'execution_time_seconds' field")
            self.assertIn('execution_time_ms', stage, "Missing 'execution_time_ms' field")
            
            # Verify field types
            self.assertIsInstance(stage['status'], str, "'status' should be a string")
            self.assertIsInstance(stage['execution_time_seconds'], (int, float), "'execution_time_seconds' should be numeric")
            
            # Verify status is not empty
            self.assertTrue(stage['status'], "'status' should not be empty")
            
            # Verify time conversion is correct
            if stage['execution_time_ms']:
                expected_seconds = round(stage['execution_time_ms'] / 1000, 2)
                self.assertEqual(stage['execution_time_seconds'], expected_seconds)
        
        # Print verification for specific stages
        stage_map = {s['stage_number']: s for s in data['stages']}
        
        if 1 in stage_map:
            print(f"✓ Stage 1 - Status: '{stage_map[1]['status']}' (expected: 'SUCCESS')")
            print(f"✓ Stage 1 - Time: {stage_map[1]['execution_time_seconds']}s (expected: 1.5s)")
            self.assertEqual(stage_map[1]['status'], 'SUCCESS')
            self.assertEqual(stage_map[1]['execution_time_seconds'], 1.5)
        
        if 3 in stage_map:
            print(f"✓ Stage 3 - Status: '{stage_map[3]['status']}' (expected: 'FAILED')")
            print(f"✓ Stage 3 - Time: {stage_map[3]['execution_time_seconds']}s (expected: 3.0s)")
            self.assertEqual(stage_map[3]['status'], 'FAILED')
            self.assertEqual(stage_map[3]['execution_time_seconds'], 3.0)
    
    def test_html_template_renders_correctly(self):
        """Test that the search page HTML renders without errors."""
        response = self.client.get(
            '/search/',
            {'account': self.stellar_account, 'network': self.network}
        )
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Check that Vue.js template code is present
        self.assertIn('stage_executions_data', content, "Vue data property missing")
        self.assertIn('stageExecutionFields', content, "Table fields definition missing")
        self.assertIn('#cell(status)', content, "Status cell template missing")
        self.assertIn('#cell(execution_time_seconds)', content, "Time cell template missing")
        
        # Check that the fix is applied (using data.item instead of data.value)
        self.assertIn('data.item.status', content, "Status should use data.item.status")
        self.assertIn('data.item.execution_time_seconds', content, "Time should use data.item.execution_time_seconds")
        
        print("✓ HTML template renders correctly with fixed cell bindings")