# webApp/tests/test_urls.py
from django.test import TestCase
from django.urls import reverse, resolve
from webApp import views


class URLResolutionTests(TestCase):
    """Test cases for URL resolution."""
    
    def test_index_url_resolves(self):
        """Test that index URL resolves to correct view."""
        # Test using direct URL path since name may not be defined
        self.assertEqual(resolve('/').func, views.index_view)
    
    def test_search_url_resolves(self):
        """Test that search URL resolves to correct view."""
        # Test using direct URL path since name may not be defined
        self.assertEqual(resolve('/search/').func, views.search_view)


class URLAccessibilityTests(TestCase):
    """Test cases for URL accessibility."""
    
    def test_all_main_urls_accessible(self):
        """Test that all main URLs are accessible."""
        urls_to_test = [
            '/',
            '/search/',
        ]
        
        for url in urls_to_test:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, [200, 302], 
                             f"URL {url} returned {response.status_code}")
    
    def test_static_files_referenced(self):
        """Test that static files are properly referenced."""
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Check for static file references
        self.assertIn('/static/', content)
