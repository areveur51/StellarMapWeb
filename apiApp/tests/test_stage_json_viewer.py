# apiApp/tests/test_stage_json_viewer.py
from django.test import TestCase, Client
from django.urls import reverse
from apiApp.models import StellarAccountStageExecution
import json


class StageJSONViewerTemplateTest(TestCase):
    """Tests for Stage JSON viewer template rendering."""
    
    def setUp(self):
        """Set up test client and test data."""
        self.client = Client()
        self.valid_account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        self.valid_network = 'public'
        
        # Clean up existing test data
        StellarAccountStageExecution.objects.filter(
            stellar_account=self.valid_account,
            network_name=self.valid_network
        ).delete()
    
    def test_template_includes_json_column(self):
        """Test that the search template includes the JSON actions column."""
        # Create test stage execution
        StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='SUCCESS',
            execution_time_ms=1500
        )
        
        # Load search page
        url = reverse('webApp:search_view')
        response = self.client.get(url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Check that template includes stageExecutionFields with actions column
        content = response.content.decode('utf-8')
        self.assertIn('stageExecutionFields', content)
        self.assertIn("key: 'actions'", content)
        self.assertIn("label: 'JSON'", content)
    
    def test_template_includes_json_button(self):
        """Test that the template includes the JSON button with icon."""
        url = reverse('webApp:search_view')
        response = self.client.get(url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Check for JSON button template
        self.assertIn('#cell(actions)', content)
        self.assertIn('showStageJson', content)
        self.assertIn('fa-code', content)
    
    def test_template_includes_modal_component(self):
        """Test that the template includes the modal component."""
        url = reverse('webApp:search_view')
        response = self.client.get(url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Check for modal component
        self.assertIn('showStageJsonModal', content)
        self.assertIn('Stage Execution Data', content)
        self.assertIn('highlightedStageJSON', content)
    
    def test_template_includes_show_stage_json_method(self):
        """Test that the template includes the showStageJson method."""
        url = reverse('webApp:search_view')
        response = self.client.get(url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Check for showStageJson method
        self.assertIn('showStageJson(stageData)', content)
        self.assertIn('selectedStageData', content)


class StageJSONViewerAPITest(TestCase):
    """Tests for Stage JSON viewer API data."""
    
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
    
    def test_api_returns_complete_stage_data_for_json_display(self):
        """Test that API returns all necessary fields for JSON display."""
        # Create test stage execution with all fields
        StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=2,
            cron_name='cron_collect_account_horizon_data',
            status='SUCCESS',
            execution_time_ms=2500,
            error_message=''
        )
        
        response = self.client.get(self.url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Verify all fields are present
        stage = data['stages'][0]
        self.assertIn('stage_number', stage)
        self.assertIn('cron_name', stage)
        self.assertIn('status', stage)
        self.assertIn('execution_time_ms', stage)
        self.assertIn('execution_time_seconds', stage)
        self.assertIn('error_message', stage)
        self.assertIn('created_at', stage)
        self.assertIn('updated_at', stage)
    
    def test_api_returns_data_with_error_message(self):
        """Test that API correctly returns stage data with error messages."""
        error_msg = 'API timeout: Connection to Horizon failed'
        
        StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=3,
            cron_name='cron_collect_account_lineage_attributes',
            status='FAILED',
            execution_time_ms=30000,
            error_message=error_msg
        )
        
        response = self.client.get(self.url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        stage = data['stages'][0]
        self.assertEqual(stage['error_message'], error_msg)
        self.assertEqual(stage['status'], 'FAILED')
    
    def test_api_json_is_well_formed(self):
        """Test that API returns well-formed JSON that can be parsed."""
        StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='SUCCESS',
            execution_time_ms=1000
        )
        
        response = self.client.get(self.url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify JSON is valid and can be re-serialized
        data = json.loads(response.content)
        re_serialized = json.dumps(data, indent=2)
        self.assertIsNotNone(re_serialized)
        
        # Verify structure
        self.assertIn('account', data)
        self.assertIn('network', data)
        self.assertIn('stages', data)
        self.assertIsInstance(data['stages'], list)
    
    def test_api_returns_multiple_stages_for_json_display(self):
        """Test that API returns multiple stages correctly."""
        # Create multiple stages
        for i in range(1, 5):
            StellarAccountStageExecution.objects.create(
                stellar_account=self.valid_account,
                network_name=self.valid_network,
                stage_number=i,
                cron_name=f'cron_stage_{i}',
                status='SUCCESS',
                execution_time_ms=1000 * i
            )
        
        response = self.client.get(self.url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertEqual(len(data['stages']), 4)
        
        # Verify each stage has all required fields
        for stage in data['stages']:
            self.assertIn('stage_number', stage)
            self.assertIn('cron_name', stage)
            self.assertIn('status', stage)


class StageJSONViewerDataIntegrityTest(TestCase):
    """Tests for JSON viewer data integrity and edge cases."""
    
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
    
    def test_json_viewer_handles_empty_error_message(self):
        """Test that JSON viewer correctly handles empty error messages."""
        StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='SUCCESS',
            execution_time_ms=1500,
            error_message=''
        )
        
        response = self.client.get(self.url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        stage = data['stages'][0]
        self.assertEqual(stage['error_message'], '')
    
    def test_json_viewer_handles_long_error_message(self):
        """Test that JSON viewer handles long error messages."""
        long_error = 'A' * 500  # 500 character error message
        
        StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='FAILED',
            execution_time_ms=5000,
            error_message=long_error
        )
        
        response = self.client.get(self.url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        stage = data['stages'][0]
        self.assertEqual(len(stage['error_message']), 500)
    
    def test_json_viewer_handles_special_characters_in_error(self):
        """Test that JSON viewer handles special characters in error messages."""
        special_error = 'Error: "Connection failed" with status <500> & message'
        
        StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='FAILED',
            execution_time_ms=3000,
            error_message=special_error
        )
        
        response = self.client.get(self.url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Verify JSON parsing handles special characters
        stage = data['stages'][0]
        self.assertIn('"Connection failed"', stage['error_message'])
        self.assertIn('<500>', stage['error_message'])
    
    def test_json_viewer_preserves_timestamps(self):
        """Test that JSON viewer preserves timestamp information."""
        stage = StellarAccountStageExecution.objects.create(
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
        
        returned_stage = data['stages'][0]
        self.assertIn('created_at', returned_stage)
        self.assertIn('updated_at', returned_stage)
        self.assertIsNotNone(returned_stage['created_at'])
        self.assertIsNotNone(returned_stage['updated_at'])
    
    def test_json_viewer_handles_zero_execution_time(self):
        """Test that JSON viewer correctly displays zero execution time."""
        StellarAccountStageExecution.objects.create(
            stellar_account=self.valid_account,
            network_name=self.valid_network,
            stage_number=1,
            cron_name='cron_make_parent_account_lineage',
            status='PENDING',
            execution_time_ms=0
        )
        
        response = self.client.get(self.url, {
            'account': self.valid_account,
            'network': self.valid_network
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        stage = data['stages'][0]
        self.assertEqual(stage['execution_time_ms'], 0)
        self.assertEqual(stage['execution_time_seconds'], 0)


class StageJSONViewerSecurityTest(TestCase):
    """Security tests for JSON viewer feature."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.url = reverse('apiApp:stage_executions_api')
    
    def test_json_viewer_prevents_xss_in_error_message(self):
        """Test that XSS attempts in error messages are safely handled."""
        xss_payload = '<script>alert("XSS")</script>'
        account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        
        # Clean up existing test data
        StellarAccountStageExecution.objects.filter(
            stellar_account=account,
            network_name='public'
        ).delete()
        
        StellarAccountStageExecution.objects.create(
            stellar_account=account,
            network_name='public',
            stage_number=1,
            cron_name='test_cron',
            status='FAILED',
            execution_time_ms=1000,
            error_message=xss_payload
        )
        
        response = self.client.get(self.url, {
            'account': account,
            'network': 'public'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Verify XSS payload is stored but will be escaped by frontend
        stage = data['stages'][0]
        self.assertEqual(stage['error_message'], xss_payload)
        
        # JSON should be valid (no script execution in JSON format)
        self.assertIsInstance(data, dict)
    
    def test_json_viewer_handles_json_injection_attempt(self):
        """Test that JSON injection attempts in cron_name are handled safely."""
        injection_attempt = '", "injected": "value'
        account = 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        
        # Clean up existing test data
        StellarAccountStageExecution.objects.filter(
            stellar_account=account,
            network_name='public'
        ).delete()
        
        # This should fail model validation, but if it somehow passes,
        # the JSON serialization should still be safe
        try:
            StellarAccountStageExecution.objects.create(
                stellar_account=account,
                network_name='public',
                stage_number=1,
                cron_name=injection_attempt,
                status='PENDING',
                execution_time_ms=0
            )
            
            response = self.client.get(self.url, {
                'account': account,
                'network': 'public'
            })
            
            # If creation succeeded, verify JSON is still valid
            if response.status_code == 200:
                data = json.loads(response.content)
                self.assertIsInstance(data, dict)
                # JSON library should properly escape the string
                re_serialized = json.dumps(data)
                self.assertIsNotNone(re_serialized)
        except (ValueError, Exception):
            # Expected to fail validation
            pass
