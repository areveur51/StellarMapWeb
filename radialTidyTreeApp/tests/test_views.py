# radialTidyTreeApp/tests/test_views.py
import json
from django.test import TestCase, Client


class TreeViewTests(TestCase):
    """Test cases for the radial tree view."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
    
    def test_tree_view_url_exists(self):
        """Test that the tree URL exists and returns 200."""
        response = self.client.get('/tree/')
        self.assertEqual(response.status_code, 200)
    
    def test_tree_view_uses_correct_template(self):
        """Test that tree view uses the correct template."""
        response = self.client.get('/tree/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'radialTidyTreeApp/radial_tidy_tree.html')
    
    def test_tree_view_renders_without_errors(self):
        """Test that tree page renders without template errors."""
        response = self.client.get('/tree/')
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Check for key HTML elements
        self.assertIn('<!DOCTYPE html>', content)
        self.assertIn('<svg id="tree"', content)
    
    def test_tree_view_includes_d3_script(self):
        """Test that D3.js is included in the tree view."""
        response = self.client.get('/tree/')
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        self.assertIn('d3', content.lower())
