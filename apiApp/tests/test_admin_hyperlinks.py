"""
Tests for admin portal hyperlinks functionality.

These tests verify that stellar_account and stellar_creator_account values 
are rendered as clickable hyperlinks in the Django admin portal.
"""

from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.utils.html import format_html
from apiApp.admin import (
    StellarAccountSearchCacheAdmin,
    StellarCreatorAccountLineageAdmin,
    StellarAccountStageExecutionAdmin,
    USE_CASSANDRA_ADMIN
)
from apiApp.model_loader import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    StellarAccountStageExecution
)


class AdminHyperlinkTestCase(TestCase):
    """Test cases for admin portal hyperlinks."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        
        # Sample stellar account for testing
        self.test_account = 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB'
        self.test_creator = 'GBRPYHIL2CI3FNQ4BXLFMNDLFJUNPU2HY3ZMFSHONUCEOASW7QC7OX2H'
        self.test_network = 'public'
    
    def test_search_cache_admin_has_link_method(self):
        """Test that StellarAccountSearchCacheAdmin has stellar_account_link method."""
        admin_instance = StellarAccountSearchCacheAdmin(StellarAccountSearchCache, self.site)
        self.assertTrue(hasattr(admin_instance, 'stellar_account_link'))
    
    def test_lineage_admin_has_link_methods(self):
        """Test that StellarCreatorAccountLineageAdmin has both link methods."""
        admin_instance = StellarCreatorAccountLineageAdmin(StellarCreatorAccountLineage, self.site)
        self.assertTrue(hasattr(admin_instance, 'stellar_account_link'))
        self.assertTrue(hasattr(admin_instance, 'creator_account_link'))
    
    def test_stage_execution_admin_has_link_method(self):
        """Test that StellarAccountStageExecutionAdmin has stellar_account_link method."""
        admin_instance = StellarAccountStageExecutionAdmin(StellarAccountStageExecution, self.site)
        self.assertTrue(hasattr(admin_instance, 'stellar_account_link'))
    
    def test_stellar_account_link_generates_correct_html(self):
        """Test that stellar_account_link generates correct HTML with hyperlink."""
        admin_instance = StellarAccountSearchCacheAdmin(StellarAccountSearchCache, self.site)
        
        # Create mock object (dict for Cassandra, object for SQLite)
        if USE_CASSANDRA_ADMIN:
            mock_obj = {
                'stellar_account': self.test_account,
                'network_name': self.test_network
            }
        else:
            # Create a real object for SQLite testing
            mock_obj = StellarAccountSearchCache.objects.create(
                stellar_account=self.test_account,
                network_name=self.test_network,
                status='COMPLETE'
            )
        
        # Call the method
        html_output = admin_instance.stellar_account_link(mock_obj)
        
        # Verify HTML contains essential elements
        self.assertIn('<a href=', str(html_output))
        self.assertIn(f'/search/?account={self.test_account}&network={self.test_network}', str(html_output))
        self.assertIn('target="_blank"', str(html_output))
        self.assertIn('GALP...MZTB', str(html_output))  # Truncated display
    
    def test_creator_account_link_generates_correct_html(self):
        """Test that creator_account_link generates correct HTML with hyperlink."""
        admin_instance = StellarCreatorAccountLineageAdmin(StellarCreatorAccountLineage, self.site)
        
        # Create mock object with creator
        if USE_CASSANDRA_ADMIN:
            mock_obj = {
                'stellar_account': self.test_account,
                'stellar_creator_account': self.test_creator,
                'network_name': self.test_network
            }
        else:
            mock_obj = StellarCreatorAccountLineage.objects.create(
                stellar_account=self.test_account,
                stellar_creator_account=self.test_creator,
                network_name=self.test_network,
                status='COMPLETE'
            )
        
        # Call the method
        html_output = admin_instance.creator_account_link(mock_obj)
        
        # Verify HTML contains essential elements
        self.assertIn('<a href=', str(html_output))
        self.assertIn(f'/search/?account={self.test_creator}&network={self.test_network}', str(html_output))
        self.assertIn('target="_blank"', str(html_output))
        self.assertIn('GBRP...X2H', str(html_output))  # Truncated display
    
    def test_creator_account_link_handles_null_creator(self):
        """Test that creator_account_link returns dash for null creator."""
        admin_instance = StellarCreatorAccountLineageAdmin(StellarCreatorAccountLineage, self.site)
        
        # Create mock object without creator
        if USE_CASSANDRA_ADMIN:
            mock_obj = {
                'stellar_account': self.test_account,
                'stellar_creator_account': None,
                'network_name': self.test_network
            }
        else:
            mock_obj = StellarCreatorAccountLineage.objects.create(
                stellar_account=self.test_account,
                stellar_creator_account=None,
                network_name=self.test_network,
                status='COMPLETE'
            )
        
        # Call the method
        html_output = admin_instance.creator_account_link(mock_obj)
        
        # Should return dash for null creator
        self.assertEqual(str(html_output), '-')
    
    def test_link_display_includes_short_description(self):
        """Test that link methods have proper short_description attributes."""
        admin_instance = StellarCreatorAccountLineageAdmin(StellarCreatorAccountLineage, self.site)
        
        self.assertEqual(
            admin_instance.stellar_account_link.short_description,
            'Stellar Account'
        )
        self.assertEqual(
            admin_instance.creator_account_link.short_description,
            'Creator Account'
        )
    
    def test_link_truncation_for_long_addresses(self):
        """Test that long addresses are properly truncated in display."""
        admin_instance = StellarAccountSearchCacheAdmin(StellarAccountSearchCache, self.site)
        
        # Test with long address (>20 characters, which is always true for Stellar addresses)
        if USE_CASSANDRA_ADMIN:
            mock_obj = {
                'stellar_account': self.test_account,
                'network_name': self.test_network
            }
        else:
            mock_obj = StellarAccountSearchCache.objects.create(
                stellar_account=self.test_account,
                network_name=self.test_network,
                status='COMPLETE'
            )
        
        html_output = str(admin_instance.stellar_account_link(mock_obj))
        
        # Should show first 8 and last 8 characters
        self.assertIn('GALP', html_output)  # First 4 chars
        self.assertIn('MZTB', html_output)  # Last 4 chars
        self.assertIn('...', html_output)    # Truncation indicator
    
    def test_link_opens_in_new_window(self):
        """Test that links have target='_blank' to open in new window."""
        admin_instance = StellarAccountSearchCacheAdmin(StellarAccountSearchCache, self.site)
        
        if USE_CASSANDRA_ADMIN:
            mock_obj = {
                'stellar_account': self.test_account,
                'network_name': self.test_network
            }
        else:
            mock_obj = StellarAccountSearchCache.objects.create(
                stellar_account=self.test_account,
                network_name=self.test_network,
                status='COMPLETE'
            )
        
        html_output = str(admin_instance.stellar_account_link(mock_obj))
        
        # Must have target="_blank"
        self.assertIn('target="_blank"', html_output)
    
    def test_link_includes_full_address_in_title(self):
        """Test that full address is included in title attribute for hover tooltip."""
        admin_instance = StellarAccountSearchCacheAdmin(StellarAccountSearchCache, self.site)
        
        if USE_CASSANDRA_ADMIN:
            mock_obj = {
                'stellar_account': self.test_account,
                'network_name': self.test_network
            }
        else:
            mock_obj = StellarAccountSearchCache.objects.create(
                stellar_account=self.test_account,
                network_name=self.test_network,
                status='COMPLETE'
            )
        
        html_output = str(admin_instance.stellar_account_link(mock_obj))
        
        # Should include full address in title attribute
        self.assertIn(f'title="{self.test_account}"', html_output)
    
    def test_list_display_includes_link_fields(self):
        """Test that list_display uses link fields instead of raw fields."""
        # Search Cache Admin
        search_cache_admin = StellarAccountSearchCacheAdmin(StellarAccountSearchCache, self.site)
        self.assertIn('stellar_account_link', search_cache_admin.list_display)
        self.assertNotIn('stellar_account', search_cache_admin.list_display)
        
        # Lineage Admin
        lineage_admin = StellarCreatorAccountLineageAdmin(StellarCreatorAccountLineage, self.site)
        self.assertIn('stellar_account_link', lineage_admin.list_display)
        self.assertIn('creator_account_link', lineage_admin.list_display)
        self.assertNotIn('stellar_account', lineage_admin.list_display)
        self.assertNotIn('stellar_creator_account', lineage_admin.list_display)
        
        # Stage Execution Admin
        stage_admin = StellarAccountStageExecutionAdmin(StellarAccountStageExecution, self.site)
        self.assertIn('stellar_account_link', stage_admin.list_display)
        self.assertNotIn('stellar_account', stage_admin.list_display)


class AdminHyperlinkIntegrationTestCase(TestCase):
    """Integration tests for admin hyperlink functionality with HTTP requests."""
    
    def setUp(self):
        """Set up test client and user."""
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        self.client.login(username='admin', password='testpass123')
        
        # Create test data
        self.test_account = 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB'
        self.test_network = 'public'
    
    def test_admin_changelist_renders_hyperlinks(self):
        """Test that admin changelist page renders hyperlinks in HTML."""
        # Note: This test only works properly if we have data in the database
        # For Cassandra, we'd need actual data. For SQLite, we can create it.
        
        if not USE_CASSANDRA_ADMIN:
            # Create test record for SQLite
            StellarAccountSearchCache.objects.create(
                stellar_account=self.test_account,
                network_name=self.test_network,
                status='COMPLETE'
            )
            
            # Request the admin changelist page
            response = self.client.get('/admin/apiApp/stellaraccountsearchcache/')
            
            # Check response is successful
            self.assertEqual(response.status_code, 200)
            
            # Check that the response contains a link element
            self.assertContains(response, '<a href=')
            self.assertContains(response, '/search/?account=')
            self.assertContains(response, 'target="_blank"')
