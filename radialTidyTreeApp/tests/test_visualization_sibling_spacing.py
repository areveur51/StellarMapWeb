"""
Regression Tests for D3 Radial Tree Sibling Spacing and Line Colors

Tests verify:
1. Siblings are properly spread in radial visualizations (not clustered)
2. Direct lineage path lines are persistently RED
3. Hover adds GREEN glow to non-lineage links only
4. Lineage links maintain red color during interactions
"""

import pytest
from django.test import Client
from django.urls import reverse
import json


@pytest.mark.django_db
class TestVisualizationSiblingSpacing:
    """
    Tests for verifying sibling spacing and line color persistence
    in D3 radial tree visualizations
    """
    
    def test_api_returns_sibling_metadata_flags(self, client: Client, sample_lineage_with_siblings):
        """
        Verify API endpoint returns correct is_lineage_path and is_sibling flags
        for proper D3 rendering
        """
        account = sample_lineage_with_siblings['searched_account']
        network = sample_lineage_with_siblings['network']
        
        url = reverse('lineage_with_siblings_api', args=[account, network])
        response = client.get(url)
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        # Verify lineage path accounts have is_lineage_path=True
        lineage_accounts = data.get('account_lineage_data', [])
        for acc in lineage_accounts:
            assert acc.get('is_lineage_path') == True
            assert acc.get('is_sibling') == False
        
        # Verify sibling accounts have is_sibling=True
        sibling_accounts = data.get('siblings_data', [])
        for sib in sibling_accounts:
            assert sib.get('is_sibling') == True
            assert sib.get('is_lineage_path') == False
    
    def test_search_page_loads_visualization_controls(self, client: Client):
        """
        Verify search page includes visualization controls template
        with proper filter inputs for sibling visualization
        """
        url = reverse('search')
        response = client.get(url)
        
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        
        # Check for visualization toggle controls
        assert 'visualization_toggle_include.html' in response.template_name or \
               'id="radial-toggle"' in content
        
        # Check for filter controls
        assert 'issuerBalanceMin' in content
        assert 'issuerBalanceMax' in content
        assert 'assetBalanceMin' in content
        assert 'assetBalanceMax' in content
    
    def test_tidytree_js_has_nodesize_layout(self):
        """
        Verify tidytree.js uses nodeSize() instead of size() 
        to prevent angle rescaling that clusters siblings
        """
        with open('radialTidyTreeApp/static/radialTidyTreeApp/d3-3.2.2/tidytree.js', 'r') as f:
            content = f.read()
        
        # Should use nodeSize for proper sibling spacing
        assert '.nodeSize([' in content, \
            "Radial tree must use .nodeSize() to preserve separation values"
        
        # Should have angle normalization after layout
        assert 'Normalize angles' in content or 'd.x = ((d.x - minX)' in content, \
            "Must normalize angles to [0, 2π] after nodeSize layout"
    
    def test_tidytree_js_has_lineage_css_classes(self):
        """
        Verify tidytree.js applies persistent CSS classes to lineage links
        for red color that survives interactions
        """
        with open('radialTidyTreeApp/static/radialTidyTreeApp/d3-3.2.2/tidytree.js', 'r') as f:
            content = f.read()
        
        # Should apply link-lineage class for persistent styling
        assert 'link-lineage' in content, \
            "Must use 'link-lineage' CSS class for persistent red lineage links"
        
        # Should have mouseover/mouseout handlers for green glow
        assert '.on(\'mouseover\'' in content, \
            "Must have mouseover handler for green glow on hover"
        
        assert '.on(\'mouseout\'' in content, \
            "Must have mouseout handler to remove green glow"
        
        # Green glow should only apply to non-lineage links
        assert 'drop-shadow(0 0 4px #00ff00)' in content or \
               'drop-shadow' in content and '#00ff00' in content, \
            "Must apply green drop-shadow glow on hover"
    
    def test_tidytree_js_has_separation_logic_for_siblings(self):
        """
        Verify tidytree.js has separation function with sibling-aware spacing
        """
        with open('radialTidyTreeApp/static/radialTidyTreeApp/d3-3.2.2/tidytree.js', 'r') as f:
            content = f.read()
        
        # Should have separation function
        assert '.separation(' in content, \
            "Must define separation function for sibling spacing"
        
        # Should check sibling count
        assert 'siblingCount' in content or 'children.length' in content, \
            "Separation logic must account for sibling count"
    
    def test_lineage_link_red_color_hardcoded(self):
        """
        Verify red color (#ff3366) for lineage links is hardcoded in tidytree.js
        """
        with open('radialTidyTreeApp/static/radialTidyTreeApp/d3-3.2.2/tidytree.js', 'r') as f:
            content = f.read()
        
        # Red color for lineage path
        assert '#ff3366' in content, \
            "Lineage links must use red color #ff3366"
        
        # Gray color for siblings
        assert '#888888' in content, \
            "Sibling links must use gray color #888888"


@pytest.mark.django_db 
class TestVisualizationFilterPersistence:
    """
    Tests for filter controls and localStorage persistence
    """
    
    def test_visualization_controls_include_slider_increment(self):
        """
        Verify visualization controls template has slider increment dropdown
        """
        with open('radialTidyTreeApp/templates/radialTidyTreeApp/visualization_toggle_include.html', 'r') as f:
            content = f.read()
        
        # Should have slider increment selector
        assert 'sliderIncrement' in content or 'SLIDER INCREMENT' in content, \
            "Must have slider increment dropdown for filter precision"
        
        # Should have increment options
        increment_values = ['5', '10', '50', '100', '1000', '5000', '10000']
        for val in increment_values:
            assert f'value="{val}"' in content or f'>{val}<' in content, \
                f"Must have {val} as slider increment option"


# Fixtures
@pytest.fixture
def sample_lineage_with_siblings():
    """
    Create sample lineage data with siblings for testing
    """
    from apiApp.model_loader import StellarCreatorAccountLineage
    from datetime import datetime
    
    # Create lineage path: A -> B -> C
    lineage = [
        {
            'stellar_account': 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
            'stellar_creator_account': None,
            'network_name': 'public',
        },
        {
            'stellar_account': 'GBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
            'stellar_creator_account': 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
            'network_name': 'public',
        },
        {
            'stellar_account': 'GCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',
            'stellar_creator_account': 'GBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
            'network_name': 'public',
        },
    ]
    
    # Create siblings for account B (children of A)
    siblings = []
    for i in range(5):
        siblings.append({
            'stellar_account': f'GS{i:056d}',
            'stellar_creator_account': 'GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
            'network_name': 'public',
        })
    
    # Insert into database
    for account_data in lineage + siblings:
        StellarCreatorAccountLineage.objects.create(
            stellar_account=account_data['stellar_account'],
            stellar_creator_account=account_data['stellar_creator_account'],
            network_name=account_data['network_name'],
            status='SUCCESS',
            stellar_account_created_at=datetime.now(),
            xlm_balance=100.0,
        )
    
    return {
        'searched_account': 'GCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',
        'network': 'public',
        'lineage_count': 3,
        'sibling_count': 5,
    }
