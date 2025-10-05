# webApp/views.py
import json
import os
import datetime
from decouple import config
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache  # For efficient caching
from django.http import Http404  # For secure error handling
import sentry_sdk
from apiApp.models import StellarCreatorAccountLineage, PENDING_HORIZON_API_DATASETS
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers  # For secure validation


def index_view(request):
    """
    Render the main landing page with search interface.

    Returns:
        HttpResponse: Rendered landing page.
    """
    return render(request, 'webApp/index.html')


def search_view(request):
    """
    Handle search view: Validate params, fetch genealogy, render with context.
    
    If no account is provided, loads default test data from test.json.
    Uses caching for genealogy data to reduce API/DB load.

    Args:
        request: HttpRequest object.

    Returns:
        HttpResponse: Rendered template.

    Raises:
        Http404: On invalid inputs.
    """
    account = request.GET.get('account')  # No default, check if provided
    network = request.GET.get('network', 'public')  # Secure default
    
    # Check if this is a default view (no account parameter provided)
    if not account:
        # Load default test data from test.json
        # Use BASE_DIR.parent since apps are at workspace root, not in StellarMapWeb/
        test_json_path = os.path.join(
            settings.BASE_DIR.parent, 
            'radialTidyTreeApp', 
            'static', 
            'radialTidyTreeApp', 
            'json', 
            'test.json'
        )
        try:
            with open(test_json_path, 'r') as f:
                tree_data = json.load(f)
            
            # Set default display values from test data
            account = tree_data.get('stellar_account', 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB')
            network = 'testnet'  # Test data uses testnet
            
            context = {
                'search_variable': 'Default Tree Data',
                'ENV': config('ENV', default='development'),
                'SENTRY_DSN_VUE': config('SENTRY_DSN_VUE', default=''),
                'account_genealogy_items': [],  # Could parse from tree_data if needed
                'tree_data': tree_data,
                'account': account,  # Template expects 'account' not 'query_account'
                'network': network,  # Template expects 'network' not 'network_selected'
                'query_account': account,  # For form persistence
                'network_selected': network,  # For form persistence
                'radial_tidy_tree_variable': tree_data,  # For the tree template
            }
            return render(request, 'webApp/search.html', context)
            
        except Exception as e:
            sentry_sdk.capture_exception(e)
            # Fallback: Create simple default tree structure
            tree_data = {
                'stellar_account': 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB',
                'node_type': 'ISSUER',
                'created': '2015-09-30 13:15:54',
                'children': []
            }
            account = tree_data['stellar_account']
            network = 'testnet'
            
            context = {
                'search_variable': 'Fallback Tree Data',
                'ENV': config('ENV', default='development'),
                'SENTRY_DSN_VUE': config('SENTRY_DSN_VUE', default=''),
                'account_genealogy_items': [],
                'tree_data': tree_data,
                'account': account,
                'network': network,
                'query_account': account,
                'network_selected': network,
                'radial_tidy_tree_variable': tree_data,
            }
            return render(request, 'webApp/search.html', context)
    
    # If account was provided, validate and process
    # Secure validation
    validator = StellarMapValidatorHelpers()
    if not validator.validate_stellar_account_address(account):
        sentry_sdk.capture_message(f"Invalid Stellar account: {account}")
        raise Http404("Invalid Stellar account address")
    
    if network not in ['public', 'testnet']:
        raise Http404("Invalid network")

    # Check StellarCreatorAccountLineage table for existing records
    try:
        existing_records = StellarCreatorAccountLineage.objects.filter(
            stellar_account=account,
            network_name=network
        ).all()
        
        has_records = len(list(existing_records)) > 0
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        has_records = False
    
    # If no records exist, create minimal PENDING entry to trigger cron processing
    if not has_records:
        try:
            StellarCreatorAccountLineage.create(
                stellar_account=account,
                network_name=network,
                status=PENDING_HORIZON_API_DATASETS,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            sentry_sdk.capture_message(
                f"Created PENDING entry for {account} on {network}",
                level='info'
            )
        except Exception as e:
            sentry_sdk.capture_exception(e)
    
    # Fetch genealogy data from existing records (or empty if just created)
    genealogy_data = None
    try:
        lineage_helpers = StellarMapCreatorAccountLineageHelpers()
        genealogy_df = lineage_helpers.get_account_genealogy(account, network)
        tree_data = lineage_helpers.generate_tidy_radial_tree_genealogy(genealogy_df)
        account_genealogy_items = genealogy_df.to_dict(
            orient='records') if not genealogy_df.empty else []
        genealogy_data = {
            'account_genealogy_items': account_genealogy_items,
            'tree_data': tree_data
        }
    except Exception as e:
        sentry_sdk.capture_exception(e)
        # Fallback to empty tree
        genealogy_data = {
            'account_genealogy_items': [],
            'tree_data': {
                'name': account[:8] + '...',
                'node_type': 'ISSUER',
                'children': []
            }
        }
    
    # Ensure genealogy_data is set (fallback safety)
    if genealogy_data is None:
        genealogy_data = {
            'account_genealogy_items': [],
            'tree_data': {
                'name': 'Root',
                'node_type': 'ISSUER',
                'children': []
            }
        }

    context = {
        'search_variable': 'Genealogy Results' if has_records else 'Processing...',
        'ENV': config('ENV', default='development'),
        'SENTRY_DSN_VUE': config('SENTRY_DSN_VUE', default=''),
        'account_genealogy_items': genealogy_data['account_genealogy_items'],
        'tree_data': genealogy_data['tree_data'],
        'account': account,
        'network': network,
        'query_account': account,
        'network_selected': network,
        'is_cached': False,
        'is_refreshing': not has_records,
    }
    return render(request, 'webApp/search.html', context)
