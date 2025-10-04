# webApp/tests/test_views.py
import json
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse


class IndexViewTests(TestCase):
    """Test cases for the index view (landing page)."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
    
    def test_index_view_url_exists(self):
        """Test that the index URL exists and returns 200."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
    
    def test_index_view_uses_correct_template(self):
        """Test that index view uses the correct template."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'webApp/index.html')
    
    def test_index_view_contains_search_interface(self):
        """Test that index page contains search interface elements."""
        response = self.client.get('/')
        self.assertContains(response, 'search-container')
        self.assertContains(response, 'Stellar')


class SearchViewDefaultTests(TestCase):
    """Test cases for search view without parameters (default/test data)."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
    
    def test_search_view_url_exists(self):
        """Test that the search URL exists and returns 200."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
    
    def test_search_view_uses_correct_template(self):
        """Test that search view uses the correct template."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'webApp/search.html')
    
    def test_search_view_loads_test_data(self):
        """Test that search view loads test.json data by default."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        
        # Check that tree_data is in context
        self.assertIn('tree_data', response.context)
        tree_data = response.context['tree_data']
        
        # Verify tree_data is not empty
        self.assertIsNotNone(tree_data)
        self.assertIsInstance(tree_data, dict)
        self.assertIn('stellar_account', tree_data)
    
    def test_search_view_context_variables(self):
        """Test that all required context variables are present."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        
        required_context = [
            'tree_data',
            'account_genealogy_items',
            'account',
            'network',
            'query_account',
            'network_selected',
        ]
        
        for var in required_context:
            self.assertIn(var, response.context, 
                         f"Missing required context variable: {var}")
    
    def test_search_view_tree_data_serializable(self):
        """Test that tree_data can be serialized to JSON."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        
        tree_data = response.context['tree_data']
        
        # Should not raise an exception
        try:
            json_str = json.dumps(tree_data)
            self.assertIsInstance(json_str, str)
            self.assertGreater(len(json_str), 100)  # Should be substantial data
        except (TypeError, ValueError) as e:
            self.fail(f"tree_data is not JSON serializable: {e}")
    
    def test_search_view_renders_without_errors(self):
        """Test that search page renders without template errors."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        
        # Check for key HTML elements
        self.assertContains(response, '<div id="app">')
        self.assertContains(response, 'tree_data:')
        self.assertContains(response, 'account_genealogy_items:')
        
    def test_search_view_includes_vue_components(self):
        """Test that Vue components are present in the template."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        
        # Check for Vue-specific elements
        self.assertContains(response, 'v-model')
        self.assertContains(response, '@click')
        self.assertContains(response, 'new Vue(')


class SearchViewParameterizedTests(TestCase):
    """Test cases for search view with account parameters."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
    
    @patch('webApp.views.StellarMapCreatorAccountLineageHelpers')
    def test_search_view_exception_fallback(self, mock_helpers):
        """Test that search view gracefully handles exceptions with fallback data."""
        # Mock the helper to raise an exception
        mock_instance = mock_helpers.return_value
        mock_instance.get_account_genealogy.side_effect = Exception("Simulated API error")
        
        response = self.client.get('/search/', {
            'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB',
            'network': 'testnet'
        })
        
        # Should still return 200 with fallback data
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['account_genealogy_items'], [])
        
        # Fallback tree_data should have minimal structure
        tree_data = response.context['tree_data']
        self.assertIn('name', tree_data)
        self.assertEqual(tree_data['name'], 'Root')
    
    def test_search_with_valid_account_testnet(self):
        """Test search with valid Stellar account on testnet."""
        response = self.client.get('/search/', {
            'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB',
            'network': 'testnet'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('tree_data', response.context)
    
    def test_search_with_valid_account_public(self):
        """Test search with valid Stellar account on public network."""
        response = self.client.get('/search/', {
            'account': 'GD6WU64OEP5C4LRBH6NK3MHYIA2ADN6K6II6EXPNVUR3ERBXT4AN4ACD',
            'network': 'public'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('tree_data', response.context)
    
    def test_search_with_invalid_account_returns_404(self):
        """Test that invalid account raises 404."""
        response = self.client.get('/search/', {
            'account': 'INVALID_ACCOUNT',
            'network': 'testnet'
        })
        self.assertEqual(response.status_code, 404)
    
    def test_search_with_invalid_network_returns_404(self):
        """Test that invalid network raises 404."""
        response = self.client.get('/search/', {
            'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB',
            'network': 'invalid_network'
        })
        self.assertEqual(response.status_code, 404)
    
    def test_search_preserves_account_in_context(self):
        """Test that search preserves account parameter in context."""
        test_account = 'GD6WU64OEP5C4LRBH6NK3MHYIA2ADN6K6II6EXPNVUR3ERBXT4AN4ACD'
        response = self.client.get('/search/', {
            'account': test_account,
            'network': 'public'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['account'], test_account)
        self.assertEqual(response.context['query_account'], test_account)
    
    def test_search_tree_data_structure(self):
        """Test that tree_data has expected structure."""
        response = self.client.get('/search/', {
            'account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB',
            'network': 'testnet'
        })
        self.assertEqual(response.status_code, 200)
        
        tree_data = response.context['tree_data']
        self.assertIsInstance(tree_data, dict)
        
        # Tree data should have either 'name' or 'stellar_account' as root
        self.assertTrue(
            'name' in tree_data or 'stellar_account' in tree_data,
            "tree_data must have 'name' or 'stellar_account' key"
        )


class HTMLRenderingTests(TestCase):
    """Test cases for HTML rendering without errors."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
    
    def test_index_html_valid(self):
        """Test that index page HTML is valid."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Check for proper HTML structure
        self.assertIn('<!DOCTYPE html>', content)
        self.assertIn('<html', content)
        self.assertIn('</html>', content)
        self.assertIn('<body', content)
        self.assertIn('</body>', content)
    
    def test_search_html_valid(self):
        """Test that search page HTML is valid."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Check for proper HTML structure
        self.assertIn('<!DOCTYPE html>', content)
        self.assertIn('<html', content)
        self.assertIn('</html>', content)
        self.assertIn('<body', content)
        self.assertIn('</body>', content)
    
    def test_search_html_no_template_errors(self):
        """Test that search page renders without template errors."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Check for common template error indicators
        self.assertNotIn('TemplateSyntaxError', content)
        self.assertNotIn('TemplateDoesNotExist', content)
        self.assertNotIn('VariableDoesNotExist', content)
    
    def test_search_html_includes_scripts(self):
        """Test that required scripts are included."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Check for required scripts
        self.assertIn('vue.min.js', content)
        self.assertIn('d3', content.lower())
        self.assertIn('bootstrap-vue', content)
        self.assertIn('tidytree.js', content)
    
    def test_search_html_includes_css(self):
        """Test that required CSS is included."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Check for CSS includes
        self.assertIn('frontend.css', content)
        self.assertIn('bootstrap', content.lower())
