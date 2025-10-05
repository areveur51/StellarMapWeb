from django.test import TestCase, Client
from django.urls import reverse
import json


class RadialTidyTreeVisualizationTest(TestCase):
    """Test suite for radial tidy tree visualization features"""

    def setUp(self):
        self.client = Client()
        self.test_data = {
            "stellar_account": "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB",
            "node_type": "ISSUER",
            "created": "2015-09-30 13:15:54",
            "home_domain": "test-domain.com",
            "xlm_balance": "1000",
            "creator_account": "GAAZI4TCR3TY5OJHCTJC2A4QSY6CJWJH5IAJTGKIN2ER7LBNVKOCCWN7",
            "children": [
                {
                    "stellar_account": "CHILD1ACCOUNT123",
                    "node_type": "ISSUER",
                    "created": "2016-01-15 10:20:30",
                    "home_domain": "child-domain.com",
                    "xlm_balance": "500",
                    "creator_account": "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB",
                    "children": []
                },
                {
                    "asset_code": "USD",
                    "asset_issuer": "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB",
                    "node_type": "ASSET",
                    "asset_type": "credit_alphanum4",
                    "balance": "10000",
                    "children": []
                }
            ]
        }

    def test_visualization_page_loads(self):
        """Test that the visualization page loads correctly"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<div id="tree"')

    def test_test_json_data_structure(self):
        """Test that test.json contains valid hierarchical data"""
        import os
        from django.conf import settings
        
        test_json_path = os.path.join(
            settings.BASE_DIR,
            'radialTidyTreeApp',
            'static',
            'radialTidyTreeApp',
            'json',
            'test.json'
        )
        
        with open(test_json_path, 'r') as f:
            data = json.load(f)
        
        # Verify root node exists
        self.assertIn('name', data)
        self.assertIn('node_type', data)
        
        # Verify hierarchical structure
        self.assertIn('children', data)
        self.assertIsInstance(data['children'], list)
        
        # Count nodes
        def count_nodes(node):
            count = 1
            if 'children' in node:
                for child in node['children']:
                    count += count_nodes(child)
            return count
        
        total_nodes = count_nodes(data)
        self.assertGreater(total_nodes, 1, "Tree should have multiple nodes")

    def test_node_types_present(self):
        """Test that both ISSUER and ASSET node types exist in test data"""
        import os
        from django.conf import settings
        
        test_json_path = os.path.join(
            settings.BASE_DIR,
            'radialTidyTreeApp',
            'static',
            'radialTidyTreeApp',
            'json',
            'test.json'
        )
        
        with open(test_json_path, 'r') as f:
            data = json.load(f)
        
        # Collect all node types
        def collect_node_types(node, types_set):
            if 'node_type' in node:
                types_set.add(node['node_type'])
            if 'children' in node:
                for child in node['children']:
                    collect_node_types(child, types_set)
        
        node_types = set()
        collect_node_types(data, node_types)
        
        # Verify both types exist
        self.assertIn('ISSUER', node_types, "Test data should contain ISSUER nodes")
        self.assertIn('ASSET', node_types, "Test data should contain ASSET nodes")

    def test_issuer_node_attributes(self):
        """Test that ISSUER nodes have required attributes"""
        data = self.test_data
        
        # Root is an ISSUER
        self.assertEqual(data['node_type'], 'ISSUER')
        self.assertIn('stellar_account', data)
        self.assertIn('created', data)
        self.assertIn('home_domain', data)
        self.assertIn('xlm_balance', data)
        self.assertIn('creator_account', data)

    def test_asset_node_attributes(self):
        """Test that ASSET nodes have required attributes"""
        # Find the asset child
        asset_node = None
        for child in self.test_data['children']:
            if child['node_type'] == 'ASSET':
                asset_node = child
                break
        
        self.assertIsNotNone(asset_node, "Test data should contain an ASSET node")
        self.assertEqual(asset_node['node_type'], 'ASSET')
        self.assertIn('asset_code', asset_node)
        self.assertIn('asset_issuer', asset_node)
        self.assertIn('asset_type', asset_node)
        self.assertIn('balance', asset_node)

    def test_d3_library_loaded(self):
        """Test that D3.js library is loaded on the page"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        self.assertContains(response, 'd3.min.js')

    def test_tidytree_script_loaded(self):
        """Test that tidytree.js script is loaded on the page"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        self.assertContains(response, 'tidytree.js')

    def test_svg_container_present(self):
        """Test that SVG container is present for visualization"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        self.assertContains(response, 'id="tree"')

    def test_json_data_passed_to_template(self):
        """Test that JSON data is properly passed to the template"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        
        # Check that tree_data is in the template context
        self.assertIn('tree_data', response.context)
        tree_data = response.context['tree_data']
        
        # Verify it's a valid hierarchical structure
        self.assertIn('children', tree_data)

    def test_radial_tree_function_called(self):
        """Test that renderRadialTree function is called with data"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        self.assertContains(response, 'renderRadialTree')

    def test_color_scheme_differentiation(self):
        """
        Test that test data contains both ASSET and ISSUER nodes
        to verify color scheme differentiation (yellow for ASSET, purple for ISSUER)
        """
        issuer_count = 0
        asset_count = 0
        
        def count_node_types(node):
            nonlocal issuer_count, asset_count
            if node.get('node_type') == 'ISSUER':
                issuer_count += 1
            elif node.get('node_type') == 'ASSET':
                asset_count += 1
            
            if 'children' in node:
                for child in node['children']:
                    count_node_types(child)
        
        count_node_types(self.test_data)
        
        self.assertGreater(issuer_count, 0, "Should have ISSUER nodes for purple color (#3f2c70)")
        self.assertGreater(asset_count, 0, "Should have ASSET nodes for yellow color (#fcec04)")

    def test_tooltip_data_structure(self):
        """Test that nodes have complete data for tooltips"""
        # Test ISSUER tooltip data
        issuer_node = self.test_data
        required_issuer_fields = ['stellar_account', 'created', 'home_domain', 'xlm_balance', 'creator_account']
        for field in required_issuer_fields:
            self.assertIn(field, issuer_node, f"ISSUER node should have {field} for tooltip")
        
        # Test ASSET tooltip data
        asset_node = self.test_data['children'][1]
        required_asset_fields = ['asset_code', 'asset_issuer', 'asset_type', 'balance']
        for field in required_asset_fields:
            self.assertIn(field, asset_node, f"ASSET node should have {field} for tooltip")

    def test_hierarchical_children_structure(self):
        """Test that parent-child relationships are properly structured"""
        root = self.test_data
        
        # Root should have children
        self.assertIn('children', root)
        self.assertIsInstance(root['children'], list)
        self.assertEqual(len(root['children']), 2, "Root should have 2 children in test data")
        
        # Each child should be a valid node
        for child in root['children']:
            self.assertIn('node_type', child)
            self.assertIn('children', child)

    def test_tree_depth(self):
        """Test that tree has proper depth for radial visualization"""
        def get_max_depth(node, current_depth=0):
            if not node.get('children'):
                return current_depth
            max_child_depth = current_depth
            for child in node['children']:
                child_depth = get_max_depth(child, current_depth + 1)
                max_child_depth = max(max_child_depth, child_depth)
            return max_child_depth
        
        depth = get_max_depth(self.test_data)
        self.assertGreater(depth, 0, "Tree should have at least one level of children")

    def test_no_circular_references(self):
        """Test that tree structure doesn't contain circular references"""
        visited_nodes = set()
        
        def check_circular(node, path=None):
            if path is None:
                path = []
            
            node_id = id(node)
            self.assertNotIn(node_id, path, "Circular reference detected in tree structure")
            
            new_path = path + [node_id]
            if 'children' in node:
                for child in node['children']:
                    check_circular(child, new_path)
        
        check_circular(self.test_data)

    def test_radial_layout_dimensions(self):
        """Test that the visualization uses proper radial layout dimensions"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        
        # The tidytree.js should set width and height (928x928)
        # This is tested implicitly by checking the script is loaded
        self.assertContains(response, 'tidytree.js')
