"""
Tests for BigQuery Pipeline Configuration admin interface.
Ensures admin portal works correctly without SafeString errors.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from apiApp.models import BigQueryPipelineConfig
from apiApp.admin import BigQueryPipelineConfigAdmin
from django.contrib.admin.sites import site


class BigQueryPipelineConfigAdminTest(TestCase):
    """Test suite for BigQuery Pipeline Configuration admin interface."""
    
    def setUp(self):
        """Set up test client and create admin user."""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        self.client.login(username='admin', password='admin123')
        
        # Create default config if doesn't exist
        self.config, _ = BigQueryPipelineConfig.objects.get_or_create(
            config_id='default',
            defaults={
                'cost_limit_usd': 0.71,
                'size_limit_mb': 148900.0,
                'pipeline_mode': 'BIGQUERY_WITH_API_FALLBACK',
                'batch_size': 100,
            }
        )
    
    def test_admin_registration(self):
        """Test that BigQueryPipelineConfig is registered in admin."""
        self.assertIn(BigQueryPipelineConfig, site._registry)
        admin_class = site._registry[BigQueryPipelineConfig]
        self.assertIsInstance(admin_class, BigQueryPipelineConfigAdmin)
    
    def test_admin_list_display_no_errors(self):
        """Test admin list view loads without SafeString errors."""
        response = self.client.get('/admin/apiApp/bigquerypipelineconfig/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'ValueError')
        self.assertNotContains(response, 'SafeString')
    
    def test_config_summary_display(self):
        """Test config_summary display method works correctly."""
        admin = site._registry[BigQueryPipelineConfig]
        
        # Test enabled state
        self.config.bigquery_enabled = True
        self.config.save()
        result = admin.config_summary(self.config)
        self.assertIn('BigQuery Enabled', str(result))
        self.assertIn('green', str(result))
        
        # Test disabled state
        self.config.bigquery_enabled = False
        self.config.save()
        result = admin.config_summary(self.config)
        self.assertIn('BigQuery Disabled', str(result))
        self.assertIn('red', str(result))
    
    def test_cost_limit_display_no_format_errors(self):
        """Test cost_limit_display works without format code errors."""
        admin = site._registry[BigQueryPipelineConfig]
        
        # Test different cost values for color coding
        test_cases = [
            (0.50, 'green'),   # Low cost
            (0.75, 'orange'),  # Medium cost
            (1.50, 'red'),     # High cost
        ]
        
        for cost, expected_color in test_cases:
            self.config.cost_limit_usd = cost
            self.config.save()
            result = admin.cost_limit_display(self.config)
            
            # Verify no errors and correct color
            self.assertIsNotNone(result)
            self.assertIn(expected_color, str(result))
            self.assertIn(f'${cost:.2f}', str(result))
            
            # Verify GB calculation
            size_gb = self.config.size_limit_mb / 1024
            self.assertIn(f'{size_gb:.0f} GB', str(result))
    
    def test_admin_change_view_loads(self):
        """Test admin change view loads without errors."""
        response = self.client.get(f'/admin/apiApp/bigquerypipelineconfig/{self.config.config_id}/change/')
        self.assertEqual(response.status_code, 200)
    
    def test_admin_save_model_updates_user(self):
        """Test save_model automatically updates updated_by field."""
        admin = site._registry[BigQueryPipelineConfig]
        
        from django.http import HttpRequest
        request = HttpRequest()
        request.user = self.admin_user
        
        # Clear updated_by
        self.config.updated_by = ''
        
        # Save through admin
        admin.save_model(request, self.config, None, False)
        
        # Verify updated_by is set
        self.config.refresh_from_db()
        self.assertEqual(self.config.updated_by, 'admin')
    
    def test_all_fieldsets_render(self):
        """Test that all fieldsets render without errors."""
        response = self.client.get(f'/admin/apiApp/bigquerypipelineconfig/{self.config.config_id}/change/')
        
        # Check all major fieldset labels are present
        fieldset_labels = [
            'BigQuery Cost Controls',
            'Pipeline Strategy',
            'Age-Based Query Optimization',
            'API Fallback Settings',
            'Child Account Collection',
            'Batch Processing',
            'Metadata',
        ]
        
        for label in fieldset_labels:
            self.assertContains(response, label)
    
    def test_config_model_str(self):
        """Test __str__ method returns correct format."""
        result = str(self.config)
        self.assertIn('BigQuery Pipeline Config', result)
        self.assertIn('$0.71', result)
        self.assertIn('BIGQUERY_WITH_API_FALLBACK', result)
    
    def test_readonly_fields(self):
        """Test that readonly fields are correctly configured."""
        admin = site._registry[BigQueryPipelineConfig]
        self.assertIn('created_at', admin.readonly_fields)
        self.assertIn('updated_at', admin.readonly_fields)
