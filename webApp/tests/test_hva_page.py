"""
Test suite for High Value Accounts (HVA) page functionality.

This test verifies that the HVA page:
- Loads successfully
- Has proper CSS and JavaScript dependencies
- Displays the search bar correctly
- Has working BootstrapVue components
"""

from django.test import TestCase, Client
from django.urls import reverse


class HighValueAccountsPageTest(TestCase):
    """Test cases for the High Value Accounts page."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.hva_url = '/web/high-value-accounts/'
    
    def test_hva_page_loads_successfully(self):
        """Test that the HVA page loads with 200 status code."""
        response = self.client.get(self.hva_url)
        self.assertEqual(response.status_code, 200)
    
    def test_hva_page_has_correct_title(self):
        """Test that the HVA page has the correct title."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, '<title>StellarMap Web - High Value Accounts</title>')
    
    def test_hva_page_includes_bootstrap_css(self):
        """Test that Bootstrap CSS is included."""
        response = self.client.get(self.hva_url)
        self.assertContains(
            response, 
            'https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css'
        )
    
    def test_hva_page_includes_bootstrap_vue_css(self):
        """Test that BootstrapVue CSS is included."""
        response = self.client.get(self.hva_url)
        self.assertContains(
            response,
            'https://cdn.jsdelivr.net/npm/bootstrap-vue@2.23.1/dist/bootstrap-vue.min.css'
        )
    
    def test_hva_page_includes_vue_js(self):
        """Test that Vue.js is included."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, 'vue@2.6.14/dist/vue.js')
    
    def test_hva_page_includes_bootstrap_vue_js(self):
        """Test that BootstrapVue JavaScript is included."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, 'bootstrap-vue@2.23.1/dist/bootstrap-vue.min.js')
    
    def test_hva_page_registers_bootstrap_vue(self):
        """Test that BootstrapVue is registered with Vue."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, 'Vue.use(BootstrapVue)')
    
    def test_hva_page_includes_theme_loader(self):
        """Test that global theme loader is included."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, 'global_theme_loader.js')
    
    def test_hva_page_includes_theme_sync(self):
        """Test that theme sync script is included."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, 'theme_sync.js')
    
    def test_hva_page_includes_shared_search_container(self):
        """Test that the shared search container component is included."""
        response = self.client.get(self.hva_url)
        # Check for elements from search_container_include.html
        self.assertContains(response, 'search-container')
        self.assertContains(response, 'sidebar-button')
    
    def test_hva_page_has_search_input_placeholder(self):
        """Test that search input has correct placeholder text."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, 'Paste a Stellar account address...')
    
    def test_hva_page_has_vue_app_instance(self):
        """Test that Vue app instance is created."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, "new Vue({")
        self.assertContains(response, "el: '#app'")
    
    def test_hva_page_has_network_toggle(self):
        """Test that network toggle functionality exists."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, 'network_toggle')
        self.assertContains(response, 'toggleNetwork')
    
    def test_hva_page_has_search_method(self):
        """Test that search method exists in Vue instance."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, 'search()')
    
    def test_hva_page_header_content(self):
        """Test that HVA page header content is present."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, 'High Value Accounts Leaderboard')
        self.assertContains(response, 'Top Stellar accounts ranked by XLM balance')
    
    def test_hva_page_has_sidebar_menu(self):
        """Test that sidebar menu is included."""
        response = self.client.get(self.hva_url)
        self.assertContains(response, 'sidebar-menu')
        self.assertContains(response, 'StellarMap.Network')
    
    def test_hva_page_sidebar_navigation_links(self):
        """Test that sidebar has all navigation links."""
        response = self.client.get(self.hva_url)
        # Check for navigation links
        self.assertContains(response, 'href="/"')
        self.assertContains(response, 'href="/search"')
        self.assertContains(response, 'href="/web/high-value-accounts/"')
        self.assertContains(response, 'href="/dashboard"')
        self.assertContains(response, 'href="/admin"')


class HVAPageConsistencyTest(TestCase):
    """Test consistency between HVA page and other pages."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
    
    def test_hva_matches_dashboard_css_dependencies(self):
        """Test that HVA page has same CSS dependencies as Dashboard."""
        hva_response = self.client.get('/web/high-value-accounts/')
        dashboard_response = self.client.get('/dashboard/')
        
        # Both should have Bootstrap CSS
        self.assertContains(hva_response, 'bootstrap@4.6.2/dist/css/bootstrap.min.css')
        self.assertContains(dashboard_response, 'bootstrap@4.6.2/dist/css/bootstrap.min.css')
        
        # Both should have BootstrapVue CSS
        self.assertContains(hva_response, 'bootstrap-vue@2.23.1/dist/bootstrap-vue.min.css')
        self.assertContains(dashboard_response, 'bootstrap-vue@2.23.1/dist/bootstrap-vue.min.css')
    
    def test_hva_matches_dashboard_vue_registration(self):
        """Test that HVA page registers BootstrapVue like Dashboard."""
        hva_response = self.client.get('/web/high-value-accounts/')
        dashboard_response = self.client.get('/dashboard/')
        
        # Both should register BootstrapVue
        self.assertContains(hva_response, 'Vue.use(BootstrapVue)')
        self.assertContains(dashboard_response, 'Vue.use(BootstrapVue)')
    
    def test_all_pages_use_shared_search_container(self):
        """Test that all pages use the shared search container component."""
        pages = [
            '/',
            '/search/',
            '/dashboard/',
            '/web/high-value-accounts/'
        ]
        
        for page_url in pages:
            response = self.client.get(page_url)
            # All pages should have the search container
            self.assertContains(
                response, 
                'search-container',
                msg_prefix=f"Page {page_url} missing search-container"
            )
            # All pages should have the network toggle
            self.assertContains(
                response,
                'network_toggle',
                msg_prefix=f"Page {page_url} missing network_toggle"
            )
