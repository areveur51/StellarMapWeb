# radialTidyTreeApp/views.py
import json
import os
from django.shortcuts import render
from django.conf import settings

def radial_tidy_tree_view(request):
    """Radial tidy tree view that loads test JSON data and renders D3 visualization"""
    
    # Load test JSON data
    test_json_path = os.path.join(
        settings.BASE_DIR, 
        'radialTidyTreeApp', 
        'static', 
        'radialTidyTreeApp', 
        'json', 
        'test.json'
    )
    
    try:
        with open(test_json_path, 'r') as f:
            tree_data = json.load(f)
        
        # Extract account information from the root of the tree data
        account = tree_data.get('stellar_account', 'Test Account')
        network = 'public'  # Default to public network for test data
        
        context = {
            'account': account,
            'network': network,
            'tree_data': json.dumps(tree_data),  # Convert to JSON string for template
            'radial_tidy_tree_variable': 'Stellar Lineage Tree Visualization'
        }
        
        return render(request, 'radialTidyTreeApp/radial_tidy_tree.html', context)
        
    except FileNotFoundError:
        return render(request, 'radialTidyTreeApp/radial_tidy_tree.html', {
            'account': 'Test Account',
            'network': 'public',
            'tree_data': json.dumps({"error": "Test data not found"}),
            'radial_tidy_tree_variable': 'Error: Test data file not found'
        })
    except json.JSONDecodeError:
        return render(request, 'radialTidyTreeApp/radial_tidy_tree.html', {
            'account': 'Test Account',
            'network': 'public',
            'tree_data': json.dumps({"error": "Invalid JSON data"}),
            'radial_tidy_tree_variable': 'Error: Invalid JSON data'
        })