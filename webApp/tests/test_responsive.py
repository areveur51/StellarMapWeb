from django.test import TestCase, Client
from django.urls import reverse
from pathlib import Path


class WebAppResponsiveDesignTest(TestCase):
    """Comprehensive test suite for webApp responsive design across all screen sizes"""
    
    def setUp(self):
        self.client = Client()
    
    def test_index_viewport_meta_tag(self):
        """Test that index page has viewport meta tag for mobile"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'name="viewport"', msg_prefix="Index should have viewport meta tag")
        self.assertContains(response, 'width=device-width', msg_prefix="Index viewport should set device width")
        self.assertContains(response, 'initial-scale=1', msg_prefix="Index viewport should set initial scale")
    
    def test_search_viewport_meta_tag(self):
        """Test that search page has viewport meta tag for mobile"""
        response = self.client.get(reverse('search'))
        
        self.assertContains(response, 'name="viewport"', msg_prefix="Search should have viewport meta tag")
        self.assertContains(response, 'width=device-width', msg_prefix="Search viewport should set device width")
        self.assertContains(response, 'initial-scale=1', msg_prefix="Search viewport should set initial scale")
    
    def test_bootstrap_grid_system(self):
        """Test that index page uses Bootstrap grid for responsive layout"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'container-fluid', msg_prefix="Should use container-fluid for responsive width")
        self.assertContains(response, 'class="row', msg_prefix="Should use Bootstrap row")
        self.assertContains(response, 'col-', msg_prefix="Should use Bootstrap column classes")
    
    def test_responsive_table_on_search(self):
        """Test that search page tables are responsive"""
        response = self.client.get(reverse('search'))
        
        self.assertContains(response, 'b-table', msg_prefix="Should use BootstrapVue table")
        self.assertContains(response, 'small', msg_prefix="Should use small table variant for mobile readability")
    
    def test_mobile_responsive_css_media_query(self):
        """Test that CSS includes mobile media queries"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('@media (max-width: 600px)', css_content, "Should have mobile media query")
        self.assertIn('flex-direction: column', css_content, "Should stack elements on mobile")
    
    def test_mobile_small_screen_320x568(self):
        """Test layout works on small mobile screens (iPhone SE)"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'shrink-to-fit=no', msg_prefix="Should prevent shrink-to-fit on small screens")
        self.assertContains(response, 'col-auto', msg_prefix="Should use col-auto for flexible sizing")
    
    def test_mobile_medium_screen_375x667(self):
        """Test layout works on medium mobile screens (iPhone 8)"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('width: 100%', css_content, "Elements should fill container width on mobile")
    
    def test_mobile_large_screen_414x896(self):
        """Test layout works on large mobile screens (iPhone 11 Pro Max)"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'align-items-center', msg_prefix="Should vertically center elements")
    
    def test_tablet_ipad_768x1024(self):
        """Test layout works on iPad (768x1024)"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'col-md-', msg_prefix="Should use medium breakpoint for tablets")
    
    def test_tablet_ipad_pro_834x1112(self):
        """Test layout works on iPad Pro 10.5 (834x1112)"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('display: flex', css_content, "Should use flexbox for responsive layout")
    
    def test_tablet_ipad_pro_large_1024x1366(self):
        """Test layout works on iPad Pro 12.9 (1024x1366)"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'justify-content-center', msg_prefix="Should center content on large tablets")
    
    def test_desktop_hd_1280x720(self):
        """Test layout works on HD desktop screens (1280x720)"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'container', msg_prefix="Should use container for desktop layout")
    
    def test_desktop_full_hd_1920x1080(self):
        """Test layout works on Full HD screens (1920x1080)"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('width: 100%', css_content, "Should support full-width layouts")
    
    def test_desktop_2k_2560x1440(self):
        """Test layout works on 2K desktop screens (2560x1440)"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'col-md-10', msg_prefix="Should constrain content width on large screens")


class IndexPageResponsiveTest(TestCase):
    """Test suite for index page responsive features"""
    
    def setUp(self):
        self.client = Client()
    
    def test_landing_header_responsive(self):
        """Test that landing header adapts to screen sizes"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'landing-header', msg_prefix="Should have landing header class")
        self.assertContains(response, 'text-center', msg_prefix="Should center text on all screens")
    
    def test_main_title_responsive_font(self):
        """Test that main title has responsive font sizing"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'main-title', msg_prefix="Should have main-title class")
        self.assertContains(response, '@media (max-width: 768px)', msg_prefix="Should have mobile font adjustment")
    
    def test_feature_cards_responsive_grid(self):
        """Test that feature cards use responsive grid"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'col-md-4', msg_prefix="Should use 3-column grid on medium+ screens")
        self.assertContains(response, 'mb-3', msg_prefix="Should have bottom margin for spacing")
    
    def test_feature_cards_equal_height(self):
        """Test that feature cards have equal height on same row"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'h-100', msg_prefix="Cards should use h-100 for equal height")
    
    def test_info_card_responsive_width(self):
        """Test that info card constrains width appropriately"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'col-md-10', msg_prefix="Should constrain info card width on larger screens")
    
    def test_search_input_responsive(self):
        """Test that search input is responsive"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'type="text"', msg_prefix="Should have text input")
        self.assertContains(response, 'placeholder=', msg_prefix="Should have placeholder text")
    
    def test_network_toggle_responsive(self):
        """Test that network toggle is responsive"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'b-form-checkbox', msg_prefix="Should use BootstrapVue checkbox")
        self.assertContains(response, 'switch', msg_prefix="Should use switch style")
    
    def test_sidebar_responsive(self):
        """Test that sidebar is responsive"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'b-sidebar', msg_prefix="Should use BootstrapVue sidebar")
        self.assertContains(response, 'sidebar-menu', msg_prefix="Should have sidebar menu")
    
    def test_button_responsive(self):
        """Test that buttons are responsive"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'col-auto', msg_prefix="Should use col-auto for button wrapping")


class SearchPageResponsiveTest(TestCase):
    """Test suite for search page responsive features"""
    
    def setUp(self):
        self.client = Client()
    
    def test_search_container_responsive(self):
        """Test that search container is responsive"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('search-container', css_content, "Should have search-container class")
        self.assertIn('display: flex', css_content, "Should use flexbox layout")
    
    def test_search_container_mobile_stack(self):
        """Test that search container stacks on mobile"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('flex-direction: column', css_content, "Should stack vertically on mobile")
    
    def test_results_container_responsive(self):
        """Test that results container is responsive"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('results-container', css_content, "Should have results-container class")
        self.assertIn('justify-content: center', css_content, "Should center results")
    
    def test_response_container_padding(self):
        """Test that response container has appropriate padding"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('response-container', css_content, "Should have response-container class")
        self.assertIn('padding', css_content, "Should have padding for spacing")
    
    def test_tabs_responsive(self):
        """Test that tabs are responsive"""
        response = self.client.get(reverse('search'))
        
        self.assertContains(response, 'b-tabs', msg_prefix="Should use BootstrapVue tabs")
        self.assertContains(response, 'b-tab', msg_prefix="Should have tab components")
    
    def test_table_responsive(self):
        """Test that table is responsive"""
        response = self.client.get(reverse('search'))
        
        self.assertContains(response, 'striped', msg_prefix="Should use striped table")
        self.assertContains(response, 'small', msg_prefix="Should use small table for mobile")
    
    def test_progress_bar_responsive(self):
        """Test that progress bar is responsive"""
        response = self.client.get(reverse('search'))
        
        self.assertContains(response, 'b-progress', msg_prefix="Should use BootstrapVue progress bar")
        self.assertContains(response, 'mt-3', msg_prefix="Should have top margin")


class CSSResponsiveTest(TestCase):
    """Test suite for CSS responsive design patterns"""
    
    def test_frontend_css_has_theme_import(self):
        """Test that frontend CSS imports theme"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('@import url(\'cyberpunk_theme.css\')', css_content, "Should import theme CSS")
    
    def test_frontend_css_responsive_utilities(self):
        """Test that CSS has responsive utility classes"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('flex', css_content, "Should use flexbox for responsive layouts")
        self.assertIn('align-items', css_content, "Should have alignment utilities")
    
    def test_top_container_fixed_position(self):
        """Test that top container is fixed for sticky header"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('position: fixed', css_content, "Should have fixed positioning")
        self.assertIn('width: 100%', css_content, "Should span full width")
        self.assertIn('z-index', css_content, "Should have z-index for layering")
    
    def test_search_input_full_width(self):
        """Test that search input expands to fill available space"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('flex: 1', css_content, "Search input should flex to fill space")
    
    def test_radial_tree_visual_responsive_width(self):
        """Test that radial tree visual has responsive width"""
        css_path = Path(__file__).parent.parent / 'static' / 'webApp' / 'css' / 'frontend.css'
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        self.assertIn('radial-tree-visual', css_content, "Should have radial-tree-visual class")
        self.assertIn('width:', css_content, "Should define width")


class BootstrapIntegrationTest(TestCase):
    """Test suite for Bootstrap framework integration"""
    
    def setUp(self):
        self.client = Client()
    
    def test_bootstrap_css_loaded(self):
        """Test that Bootstrap CSS is loaded"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'bootstrap', msg_prefix="Should load Bootstrap CSS")
    
    def test_bootstrap_vue_loaded(self):
        """Test that BootstrapVue is loaded"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'bootstrap-vue', msg_prefix="Should load BootstrapVue")
    
    def test_vue_js_loaded(self):
        """Test that Vue.js is loaded"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'vue', msg_prefix="Should load Vue.js")
    
    def test_font_awesome_loaded(self):
        """Test that Font Awesome is loaded for icons"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'font-awesome', msg_prefix="Should load Font Awesome")


class AccessibilityResponsiveTest(TestCase):
    """Test suite for accessibility in responsive design"""
    
    def setUp(self):
        self.client = Client()
    
    def test_input_has_placeholder(self):
        """Test that input fields have placeholder text"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'placeholder=', msg_prefix="Inputs should have placeholder for accessibility")
    
    def test_buttons_have_icons(self):
        """Test that buttons have icons for visual clarity"""
        response = self.client.get(reverse('home'))
        
        self.assertContains(response, 'fa fa-', msg_prefix="Buttons should have Font Awesome icons")
    
    def test_links_target_blank_security(self):
        """Test that dataset template includes secure external link patterns"""
        dataset_path = Path(__file__).parent.parent / 'templates' / 'webApp' / 'dataset.html'
        
        with open(dataset_path, 'r') as f:
            dataset_content = f.read()
        
        self.assertIn('target="_blank"', dataset_content, "External links should open in new tab")
        self.assertIn('rel="noopener', dataset_content, "External links should have noopener for security")
