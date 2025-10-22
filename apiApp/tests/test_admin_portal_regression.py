"""
Regression tests for Django Admin Portal

These tests ensure all admin portal links work correctly and prevent
database schema mismatches from causing admin page errors.

Created: 2025-10-22
Purpose: Prevent regression issues like missing database columns
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from apiApp.models import BigQueryPipelineConfig, SchedulerConfig


class AdminPortalRegressionTests(TestCase):
    """Test suite for admin portal functionality"""
    
    def setUp(self):
        """Create admin user and client for testing"""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='testpass123'
        )
        self.client.login(username='admin_test', password='testpass123')
    
    def test_admin_index_page_loads(self):
        """Test that admin index page loads successfully"""
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Django administration')
    
    def test_admin_apiapp_section_loads(self):
        """Test that apiApp section in admin loads"""
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        # Check for apiApp models in the admin index
        self.assertContains(response, 'APIAPP')
    
    def test_bigquery_pipeline_config_changelist(self):
        """Test BigQuery Pipeline Configuration changelist page"""
        # Create a default config if it doesn't exist
        BigQueryPipelineConfig.objects.get_or_create(
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
        
        url = reverse('admin:apiApp_bigquerypipelineconfig_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BigQuery Pipeline Configuration')
        # Verify critical fields are displayed
        self.assertContains(response, 'cost_limit_usd')
        self.assertContains(response, 'pipeline_mode')
    
    def test_bigquery_pipeline_config_add_page(self):
        """Test BigQuery Pipeline Configuration add page"""
        url = reverse('admin:apiApp_bigquerypipelineconfig_add')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check that all critical fields are present
        self.assertContains(response, 'config_id')
        self.assertContains(response, 'bigquery_enabled')
        self.assertContains(response, 'cost_limit_usd')
        self.assertContains(response, 'pipeline_mode')
        self.assertContains(response, 'api_pipeline_enabled')
        self.assertContains(response, 'api_pipeline_batch_size')
        self.assertContains(response, 'api_pipeline_interval_seconds')
    
    def test_bigquery_pipeline_config_change_page(self):
        """Test BigQuery Pipeline Configuration change page"""
        config = BigQueryPipelineConfig.objects.create(
            config_id='test_config',
            bigquery_enabled=True,
            cost_limit_usd=0.71,
            pipeline_mode='API_ONLY',
            api_pipeline_enabled=True,
            api_pipeline_batch_size=3,
            api_pipeline_interval_seconds=120,
        )
        
        url = reverse('admin:apiApp_bigquerypipelineconfig_change', args=[config.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test_config')
        self.assertContains(response, 'api_pipeline_enabled')
    
    def test_scheduler_config_changelist(self):
        """Test Scheduler Configuration changelist page"""
        url = reverse('admin:apiApp_schedulerconfig_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Scheduler Configuration')
    
    def test_api_rate_limiter_config_changelist(self):
        """Test API Rate Limiter Configuration changelist page"""
        url = reverse('admin:apiApp_apiratelimiterconfig_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'API Rate Limiter Configuration')
    
    def test_all_apiapp_admin_models_registered(self):
        """Test that all expected apiApp models are registered in admin"""
        response = self.client.get('/admin/')
        
        # Check for all expected admin models
        expected_models = [
            'API Rate Limiter Configuration',
            'BigQuery Pipeline Configuration',
            'Management cron healths',
            'Scheduler Configuration',
        ]
        
        for model_name in expected_models:
            with self.subTest(model=model_name):
                self.assertContains(response, model_name)
    
    def test_bigquery_config_schema_has_all_fields(self):
        """Test that BigQueryPipelineConfig model has all expected fields"""
        config = BigQueryPipelineConfig.objects.create(
            config_id='schema_test',
            bigquery_enabled=True,
            cost_limit_usd=0.71,
            pipeline_mode='API_ONLY',
            api_pipeline_enabled=True,
            api_pipeline_batch_size=3,
            api_pipeline_interval_seconds=120,
        )
        
        # Verify all critical fields exist and can be accessed
        self.assertEqual(config.config_id, 'schema_test')
        self.assertTrue(config.bigquery_enabled)
        self.assertEqual(config.cost_limit_usd, 0.71)
        self.assertEqual(config.pipeline_mode, 'API_ONLY')
        self.assertTrue(config.api_pipeline_enabled)
        self.assertEqual(config.api_pipeline_batch_size, 3)
        self.assertEqual(config.api_pipeline_interval_seconds, 120)
    
    def test_admin_search_functionality(self):
        """Test admin search functionality doesn't crash"""
        BigQueryPipelineConfig.objects.get_or_create(
            config_id='default',
            defaults={
                'bigquery_enabled': True,
                'cost_limit_usd': 0.71,
                'pipeline_mode': 'API_ONLY',
            }
        )
        
        url = reverse('admin:apiApp_bigquerypipelineconfig_changelist')
        response = self.client.get(url, {'q': 'default'})
        
        self.assertEqual(response.status_code, 200)
    
    def test_admin_filter_functionality(self):
        """Test admin filter functionality doesn't crash"""
        url = reverse('admin:apiApp_bigquerypipelineconfig_changelist')
        response = self.client.get(url, {'bigquery_enabled__exact': '1'})
        
        self.assertEqual(response.status_code, 200)
    
    def tearDown(self):
        """Clean up test data"""
        # Clean up any test configs created
        BigQueryPipelineConfig.objects.filter(config_id__startswith='test').delete()
        User.objects.filter(username='admin_test').delete()


class AdminPortalDatabaseSchemaTests(TestCase):
    """Test database schema integrity for admin models"""
    
    def test_bigquery_config_database_columns_exist(self):
        """
        Regression test for missing database columns
        
        This test prevents the error:
        OperationalError: no such column: bigquery_pipeline_config.api_pipeline_enabled
        """
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Get table info
            cursor.execute("PRAGMA table_info(bigquery_pipeline_config);")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Verify critical columns exist
            required_columns = [
                'config_id',
                'bigquery_enabled',
                'cost_limit_usd',
                'size_limit_mb',
                'pipeline_mode',
                'api_pipeline_enabled',
                'api_pipeline_batch_size',
                'api_pipeline_interval_seconds',
                'hva_threshold_xlm',
                'hva_supported_thresholds',
            ]
            
            for column in required_columns:
                with self.subTest(column=column):
                    self.assertIn(
                        column, 
                        column_names,
                        f"Missing required column: {column}"
                    )
    
    def test_scheduler_config_database_columns_exist(self):
        """Test that SchedulerConfig database table has all required columns"""
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(scheduler_config);")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            required_columns = [
                'config_id',
                'scheduler_enabled',
            ]
            
            for column in required_columns:
                with self.subTest(column=column):
                    self.assertIn(
                        column,
                        column_names,
                        f"Missing required column: {column}"
                    )


class AdminPortalPermissionTests(TestCase):
    """Test admin portal permissions and access control"""
    
    def setUp(self):
        """Create test users"""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@test.com',
            password='regular123'
        )
    
    def test_admin_portal_requires_authentication(self):
        """Test that admin portal requires authentication"""
        response = self.client.get('/admin/')
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)
    
    def test_regular_user_cannot_access_admin(self):
        """Test that regular users cannot access admin portal"""
        self.client.login(username='regular', password='regular123')
        response = self.client.get('/admin/')
        # Should redirect to login (regular users don't have permission)
        self.assertEqual(response.status_code, 302)
    
    def test_superuser_can_access_admin(self):
        """Test that superusers can access admin portal"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Django administration')
    
    def tearDown(self):
        """Clean up test users"""
        User.objects.all().delete()


class AdminPortalIntegrationTests(TestCase):
    """Integration tests for admin portal workflows"""
    
    def setUp(self):
        """Create admin user and client"""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin_integration',
            email='admin@test.com',
            password='testpass123'
        )
        self.client.login(username='admin_integration', password='testpass123')
    
    def test_create_bigquery_config_workflow(self):
        """Test complete workflow of creating a BigQuery config via admin"""
        # Step 1: Access add page
        add_url = reverse('admin:apiApp_bigquerypipelineconfig_add')
        response = self.client.get(add_url)
        self.assertEqual(response.status_code, 200)
        
        # Step 2: Submit form
        data = {
            'config_id': 'integration_test',
            'bigquery_enabled': True,
            'cost_limit_usd': 1.0,
            'size_limit_mb': 150000.0,
            'pipeline_mode': 'API_ONLY',
            'instant_query_max_age_days': 365,
            'api_fallback_enabled': True,
            'horizon_max_operations': 200,
            'horizon_child_max_pages': 5,
            'bigquery_max_children': 100000,
            'bigquery_child_page_size': 10000,
            'batch_processing_enabled': True,
            'batch_size': 6,
            'cache_ttl_hours': 12,
            'hva_threshold_xlm': 100000.0,
            'hva_supported_thresholds': '10000,50000,100000',
            'api_pipeline_enabled': True,
            'api_pipeline_batch_size': 3,
            'api_pipeline_interval_seconds': 120,
        }
        response = self.client.post(add_url, data, follow=True)
        
        # Should redirect to changelist
        self.assertEqual(response.status_code, 200)
        
        # Step 3: Verify config was created
        config = BigQueryPipelineConfig.objects.get(config_id='integration_test')
        self.assertEqual(config.cost_limit_usd, 1.0)
        self.assertTrue(config.api_pipeline_enabled)
    
    def test_update_bigquery_config_workflow(self):
        """Test complete workflow of updating a BigQuery config via admin"""
        # Create initial config
        config = BigQueryPipelineConfig.objects.create(
            config_id='update_test',
            bigquery_enabled=True,
            cost_limit_usd=0.5,
            pipeline_mode='API_ONLY',
            api_pipeline_enabled=True,
            api_pipeline_batch_size=3,
            api_pipeline_interval_seconds=120,
        )
        
        # Update via admin
        change_url = reverse('admin:apiApp_bigquerypipelineconfig_change', args=[config.pk])
        response = self.client.get(change_url)
        self.assertEqual(response.status_code, 200)
        
        # Submit update
        data = {
            'config_id': 'update_test',
            'bigquery_enabled': False,  # Changed
            'cost_limit_usd': 0.71,     # Changed
            'size_limit_mb': 148900.0,
            'pipeline_mode': 'BIGQUERY_WITH_API_FALLBACK',  # Changed
            'instant_query_max_age_days': 365,
            'api_fallback_enabled': True,
            'horizon_max_operations': 200,
            'horizon_child_max_pages': 5,
            'bigquery_max_children': 100000,
            'bigquery_child_page_size': 10000,
            'batch_processing_enabled': True,
            'batch_size': 6,
            'cache_ttl_hours': 12,
            'hva_threshold_xlm': 100000.0,
            'hva_supported_thresholds': '10000,50000,100000',
            'api_pipeline_enabled': False,  # Changed
            'api_pipeline_batch_size': 5,   # Changed
            'api_pipeline_interval_seconds': 180,  # Changed
        }
        response = self.client.post(change_url, data, follow=True)
        
        # Verify changes
        config.refresh_from_db()
        self.assertFalse(config.bigquery_enabled)
        self.assertEqual(config.cost_limit_usd, 0.71)
        self.assertEqual(config.pipeline_mode, 'BIGQUERY_WITH_API_FALLBACK')
        self.assertFalse(config.api_pipeline_enabled)
        self.assertEqual(config.api_pipeline_batch_size, 5)
    
    def tearDown(self):
        """Clean up test data"""
        BigQueryPipelineConfig.objects.filter(
            config_id__in=['integration_test', 'update_test']
        ).delete()
        User.objects.filter(username='admin_integration').delete()
