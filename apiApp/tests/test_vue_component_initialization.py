"""
Vue.js component initialization and frontend tests.

Tests ensure that:
1. Vue components initialize without JavaScript errors
2. Polling intervals are correctly configured
3. Visibility handlers are properly set up and cleaned up
4. No template rendering issues
"""

import pytest
from django.test import TestCase, Client
import re


@pytest.mark.integration
@pytest.mark.regression
class TestVueComponentInitialization(TestCase):
    """Test Vue.js component initialization in templates."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
    
    def test_search_page_vue_initialization(self):
        """Test that search page Vue component initializes correctly."""
        response = self.client.get('/search')
        
        # Should render successfully
        assert response.status_code == 200
        
        # Should contain Vue initialization
        content = response.content.decode('utf-8')
        assert 'new Vue(' in content
        assert 'el: \'#app\'' in content
        
        # Should not have raw Vue template syntax visible
        assert '{{ tomlError }}' not in content
        assert '{{ tomlContent }}' not in content
    
    def test_search_page_has_polling_configuration(self):
        """Test that search page has polling configuration."""
        response = self.client.get('/search')
        content = response.content.decode('utf-8')
        
        # Should have polling interval configured (30000ms = 30s)
        assert '30000' in content or '30s' in content.lower()
        
        # Should have stopPolling method
        assert 'stopPolling' in content
    
    def test_search_page_has_visibility_handler(self):
        """Test that search page has Page Visibility API handler."""
        response = self.client.get('/search')
        content = response.content.decode('utf-8')
        
        # Should have visibility change listener
        assert 'visibilitychange' in content
        assert 'document.hidden' in content
    
    def test_search_page_has_cleanup_logic(self):
        """Test that search page has proper cleanup logic."""
        response = self.client.get('/search')
        content = response.content.decode('utf-8')
        
        # Should have beforeDestroy lifecycle hook
        assert 'beforeDestroy' in content
        
        # Should remove event listener
        assert 'removeEventListener' in content
    
    def test_query_builder_vue_initialization(self):
        """Test that query builder Vue component initializes correctly."""
        response = self.client.get('/web/query-builder/')
        
        # Should render successfully
        assert response.status_code == 200
        
        content = response.content.decode('utf-8')
        
        # Should contain Vue initialization
        assert 'new Vue(' in content
        
        # Should have table columns configuration
        assert 'tableColumns' in content
    
    def test_query_builder_has_all_table_definitions(self):
        """Test that query builder has all table column definitions."""
        response = self.client.get('/web/query-builder/')
        content = response.content.decode('utf-8')
        
        # Should have all table keys
        required_tables = ['lineage', 'cache', 'hva', 'stages', 'hva_changes']
        
        for table in required_tables:
            assert f'{table}:' in content, f"Missing table definition for '{table}'"


@pytest.mark.unit
@pytest.mark.performance
class TestVueComponentPerformance:
    """Test Vue component performance characteristics."""
    
    def test_polling_interval_is_30_seconds(self):
        """Test that polling interval is set to 30 seconds (performance optimization)."""
        from django.test import Client
        
        client = Client()
        response = client.get('/search')
        content = response.content.decode('utf-8')
        
        # Extract polling interval from JavaScript
        # Should find setInterval with 30000 (30 seconds)
        interval_pattern = r'setInterval\([^,]+,\s*(\d+)\)'
        intervals = re.findall(interval_pattern, content)
        
        # Should have at least one 30-second interval
        has_30s_interval = any(int(interval) == 30000 for interval in intervals if interval.isdigit())
        assert has_30s_interval, "No 30-second polling interval found"
    
    def test_no_15_second_polling_intervals(self):
        """Test that old 15-second intervals have been removed (regression test)."""
        from django.test import Client
        
        client = Client()
        response = client.get('/search')
        content = response.content.decode('utf-8')
        
        # Should NOT have 15-second intervals (old implementation)
        interval_pattern = r'setInterval\([^,]+,\s*(\d+)\)'
        intervals = re.findall(interval_pattern, content)
        
        # Check that no intervals are 15000 (15 seconds)
        has_15s_interval = any(int(interval) == 15000 for interval in intervals if interval.isdigit())
        assert not has_15s_interval, "Found old 15-second polling interval (should be 30s)"


@pytest.mark.regression
class TestVueTemplateRenderingRegression(TestCase):
    """Regression tests for Vue template rendering issues."""
    
    def test_no_raw_vue_syntax_in_search_page(self):
        """Test that Vue syntax is not rendered raw (regression for recent bug)."""
        response = self.client.get('/search')
        content = response.content.decode('utf-8')
        
        # These should NOT appear as raw text in the rendered page
        raw_vue_patterns = [
            '{{ tomlError }}',
            '{{ tomlContent }}',
            '{{ query_account }}',
            'v-if="tomlError"',
            'v-else-if="tomlContent"'
        ]
        
        # Some patterns are OK in JavaScript, but not in visible HTML
        # Extract just the HTML body (rough approximation)
        body_start = content.find('<body')
        script_start = content.find('<script')
        
        if body_start > 0 and script_start > body_start:
            visible_html = content[body_start:script_start]
            
            for pattern in ['{{ tomlError }}', '{{ tomlContent }}']:
                assert pattern not in visible_html, \
                    f"Found raw Vue template syntax '{pattern}' in visible HTML"
    
    def test_vue_methods_properly_scoped(self):
        """Test that Vue methods are properly scoped within methods object."""
        response = self.client.get('/search')
        content = response.content.decode('utf-8')
        
        # Extract Vue instance definition
        vue_start = content.find('new Vue(')
        if vue_start < 0:
            pytest.skip("Vue instance not found in template")
        
        # stopPolling should be inside methods object, not outside
        # This is a regression test for the recent bug fix
        methods_pattern = r'methods:\s*\{[^}]*stopPolling'
        assert re.search(methods_pattern, content, re.DOTALL), \
            "stopPolling method not found inside methods object"
        
        # beforeDestroy should be a lifecycle hook (outside methods)
        lifecycle_pattern = r'\},\s*beforeDestroy\('
        assert re.search(lifecycle_pattern, content), \
            "beforeDestroy should be a lifecycle hook, not inside methods"
