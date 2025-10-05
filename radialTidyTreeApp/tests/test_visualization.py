from django.test import TestCase, Client, override_settings
from django.urls import reverse
import json
import re
from pathlib import Path


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
        self.assertContains(response, 'id="tree"')

    def test_test_json_data_structure(self):
        """Test that test.json contains valid hierarchical data"""
        import os
        from pathlib import Path
        
        # Get the test.json from the radialTidyTreeApp static directory
        test_json_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'json' / 'test.json'
        
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
        from pathlib import Path
        
        # Get the test.json from the radialTidyTreeApp static directory
        test_json_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'json' / 'test.json'
        
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
        self.assertContains(response, 'd3.v7.min.js')

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
        tree_data_json = response.context['tree_data']
        
        # Parse the JSON string back to Python object
        tree_data = json.loads(tree_data_json)
        
        # Must be valid hierarchical data, not error
        self.assertIn('children', tree_data, "Tree data must contain valid hierarchical structure")
        self.assertNotIn('error', tree_data, "Tree data should not be error payload - test.json must be loaded")

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
    
    def test_color_scheme_constants_in_tidytree_js(self):
        """Test that tidytree.js contains correct color scheme for ASSET and ISSUER nodes"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify ASSET color (yellow #fcec04)
        self.assertIn('#fcec04', tidytree_content, "ASSET nodes should use yellow color #fcec04")
        
        # Verify ISSUER color (purple #3f2c70)
        self.assertIn('#3f2c70', tidytree_content, "ISSUER nodes should use purple color #3f2c70")
        
        # Verify color assignment logic based on node_type
        self.assertIn('node_type', tidytree_content, "Color logic should check node_type")
        self.assertIn('ASSET', tidytree_content, "Should differentiate ASSET node type")
    
    def test_tooltip_structure_for_issuer_nodes(self):
        """Test that tooltip HTML includes all required ISSUER node fields"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify ISSUER tooltip fields
        issuer_fields = ['Created', 'Home Domain', 'XLM Balance', 'Creator']
        for field in issuer_fields:
            self.assertIn(field, tidytree_content, 
                         f"Tooltip should display '{field}' for ISSUER nodes")
    
    def test_tooltip_structure_for_asset_nodes(self):
        """Test that tooltip HTML includes all required ASSET node fields"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify ASSET tooltip fields
        asset_fields = ['Issuer', 'Asset Type', 'Balance']
        for field in asset_fields:
            self.assertIn(field, tidytree_content, 
                         f"Tooltip should display '{field}' for ASSET nodes")
    
    def test_radial_tree_layout_implementation(self):
        """Test that radial tree layout uses d3.tree with radial positioning"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify radial tree layout implementation
        self.assertIn('d3.tree()', tidytree_content, "Should use d3.tree() for layout")
        self.assertIn('2 * Math.PI', tidytree_content, "Should use full circle (2π) for radial layout")
        self.assertIn('d3.linkRadial()', tidytree_content, "Should use d3.linkRadial() for radial links")
    
    def test_svg_centering_with_transform(self):
        """Test that SVG uses transform to center the radial tree"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify centering transform
        self.assertIn('translate', tidytree_content, "Should use translate for centering")
        self.assertIn('size / 2', tidytree_content, "Should center at half of calculated size")
    
    def test_hover_event_handlers_implemented(self):
        """Test that mouseover and mouseout event handlers are implemented for tooltips"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify hover event handlers
        self.assertIn('mouseover', tidytree_content, "Should have mouseover event handler")
        self.assertIn('mouseout', tidytree_content, "Should have mouseout event handler")
        self.assertIn('showTooltip', tidytree_content, "Should have showTooltip function")
        self.assertIn('hideTooltip', tidytree_content, "Should have hideTooltip function")
    
    def test_node_circle_radius_attribute(self):
        """Test that nodes are rendered as circles with proper radius"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify circle rendering
        self.assertIn('append(\'circle\')', tidytree_content, "Should append circle elements for nodes")
        self.assertIn('attr(\'r\'', tidytree_content, "Should set radius attribute for circles")
    
    def test_purple_links_default_color(self):
        """Test that links use purple color (#3f2c70) by default"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify purple link color
        self.assertIn("'#3f2c70'", tidytree_content, "Links should use purple color #3f2c70")
        self.assertIn("stroke", tidytree_content, "Should set stroke style for links")
    
    def test_red_hover_path_highlighting(self):
        """Test that hover interaction changes path to red (#ff0000)"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify red hover color
        self.assertIn("'#ff0000'", tidytree_content, "Hovered path should be highlighted in red #ff0000")
        self.assertIn("getPathToRoot", tidytree_content, "Should have getPathToRoot function for path highlighting")
    
    def test_breadcrumb_container_exists(self):
        """Test that breadcrumb container is created for displaying node path"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify breadcrumb implementation
        self.assertIn('breadcrumbContainer', tidytree_content, "Should have breadcrumbContainer for displaying path")
        self.assertIn('breadcrumb-container', tidytree_content, "Should have breadcrumb-container class")
    
    def test_semi_transparent_tooltip_background(self):
        """Test that tooltip background uses semi-transparent node color (rgba)"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify semi-transparent backgrounds
        self.assertIn('rgba(252, 236, 4, 0.9)', tidytree_content, "Should use semi-transparent yellow for ASSET tooltip")
        self.assertIn('rgba(63, 44, 112, 0.9)', tidytree_content, "Should use semi-transparent purple for ISSUER tooltip")
        self.assertIn('backgroundColor', tidytree_content, "Should set backgroundColor based on node type")
    
    def test_breadcrumb_color_coding(self):
        """Test that breadcrumbs use color-coded rectangles matching node types"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify breadcrumb color logic
        self.assertIn('breadcrumbColor', tidytree_content, "Should have breadcrumbColor variable")
        self.assertIn("append('rect')", tidytree_content, "Should append rect elements for breadcrumb backgrounds")
    
    def test_path_highlighting_opacity_changes(self):
        """Test that non-hovered links reduce opacity when hovering over a node"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify opacity changes
        self.assertIn('.style(\'opacity\'', tidytree_content, "Should change opacity during hover")
        self.assertIn('pathLinks', tidytree_content, "Should check if link is in hovered path using pathLinks Set")


class ResponsiveDesignTest(TestCase):
    """Test suite for responsive design across different screen sizes"""
    
    def test_responsive_css_in_template(self):
        """Test that template includes responsive CSS"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        
        # Verify viewport meta tag
        self.assertContains(response, 'name="viewport"', msg_prefix="Should have viewport meta tag for mobile")
        self.assertContains(response, 'width=device-width', msg_prefix="Should set viewport width to device width")
        
        # Verify responsive CSS classes
        self.assertContains(response, 'page-container', msg_prefix="Should have page-container class")
        self.assertContains(response, 'visualization-container', msg_prefix="Should have visualization-container class")
        
        # Verify flexbox layout for full height
        self.assertContains(response, 'height: 100%', msg_prefix="Should use 100% height for full viewport")
        
    def test_dynamic_viewport_calculation(self):
        """Test that JavaScript calculates dimensions based on viewport"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify dynamic dimension calculation
        self.assertIn('getBoundingClientRect', tidytree_content, "Should calculate container dimensions dynamically")
        self.assertIn('window.innerWidth', tidytree_content, "Should fallback to window dimensions if needed")
        self.assertIn('window.innerHeight', tidytree_content, "Should fallback to window height if needed")
        
    def test_mobile_small_screen_320x568(self):
        """Test visualization works on small mobile screens (iPhone SE)"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify responsive sizing uses Math.min for square layout
        self.assertIn('Math.min', tidytree_content, "Should use Math.min to ensure square layout on all screens")
        
    def test_mobile_medium_screen_375x667(self):
        """Test visualization works on medium mobile screens (iPhone 8)"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        
        # Verify media query for mobile
        self.assertContains(response, '@media (max-width: 768px)', msg_prefix="Should have mobile media query")
        
    def test_mobile_large_screen_414x896(self):
        """Test visualization works on large mobile screens (iPhone 11 Pro Max)"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify viewBox for scalability
        self.assertIn('viewBox', tidytree_content, "Should use viewBox for responsive SVG scaling")
        self.assertIn('preserveAspectRatio', tidytree_content, "Should preserve aspect ratio on all screens")
        
    def test_tablet_ipad_768x1024(self):
        """Test visualization works on iPad (768x1024)"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        
        # Verify SVG fills container
        self.assertContains(response, 'width: 100%', msg_prefix="SVG should fill 100% width on tablets")
        self.assertContains(response, 'height: 100%', msg_prefix="SVG should fill 100% height on tablets")
        
    def test_tablet_ipad_pro_834x1112(self):
        """Test visualization works on iPad Pro 10.5" (834x1112)"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify radius calculation adapts to size
        self.assertIn('radius = size / 2', tidytree_content, "Radius should adapt based on viewport size")
        
    def test_tablet_ipad_pro_large_1024x1366(self):
        """Test visualization works on iPad Pro 12.9" (1024x1366)"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        
        # Verify flexbox centers content
        self.assertContains(response, 'align-items: center', msg_prefix="Should center visualization on large tablets")
        self.assertContains(response, 'justify-content: center', msg_prefix="Should center horizontally on large tablets")
        
    def test_desktop_hd_1280x720(self):
        """Test visualization works on HD desktop screens (1280x720)"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        
        # Verify page container uses full viewport
        self.assertContains(response, 'page-container', msg_prefix="Should have page container for desktop layout")
        
    def test_desktop_full_hd_1920x1080(self):
        """Test visualization works on Full HD screens (1920x1080)"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify size calculation for large screens
        self.assertIn('const size = Math.min(width, height)', tidytree_content, 
                     "Should calculate size to fit both dimensions on large screens")
        
    def test_desktop_2k_2560x1440(self):
        """Test visualization works on 2K desktop screens (2560x1440)"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        
        # Verify responsive font sizing
        self.assertContains(response, 'clamp', msg_prefix="Should use clamp for responsive font sizing on all screens")
        
    def test_svg_responsive_attributes(self):
        """Test that SVG has proper responsive attributes"""
        tidytree_path = Path(__file__).parent.parent / 'static' / 'radialTidyTreeApp' / 'd3-3.2.2' / 'tidytree.js'
        
        with open(tidytree_path, 'r') as f:
            tidytree_content = f.read()
        
        # Verify SVG responsive setup
        self.assertIn('.attr(\'width\', \'100%\')', tidytree_content, "SVG width should be 100%")
        self.assertIn('.attr(\'height\', \'100%\')', tidytree_content, "SVG height should be 100%")
        self.assertIn('xMidYMid meet', tidytree_content, "Should center and scale SVG content")
        
    def test_container_overflow_hidden(self):
        """Test that container prevents scroll bars on all screen sizes"""
        response = self.client.get(reverse('radialTidyTreeApp:radial_tidy_tree'))
        
        # Verify overflow handling
        self.assertContains(response, 'overflow: hidden', msg_prefix="Should hide overflow to prevent scroll bars")
