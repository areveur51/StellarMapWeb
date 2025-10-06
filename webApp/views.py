# webApp/views.py
import json
import os
from decouple import config
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache  # For efficient caching
from django.http import Http404  # For secure error handling
import sentry_sdk
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers  # For secure validation
from apiApp.helpers.sm_cache import StellarMapCacheHelpers


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

    # 12-hour Cassandra cache strategy (with fallback for schema migration)
    is_fresh = False
    is_refreshing = False
    genealogy_data = None
    cache_helpers = None
    cache_entry = None
    
    try:
        cache_helpers = StellarMapCacheHelpers()
        is_fresh, cache_entry = cache_helpers.check_cache_freshness(account, network)
    except Exception as cache_error:
        # Cache not available yet (schema migration needed), skip cache
        sentry_sdk.capture_exception(cache_error)
        is_fresh = False
        cache_entry = None
    
    # Return cached data immediately if fresh
    if is_fresh and cache_entry and cache_helpers:
        cached_tree_data = cache_helpers.get_cached_data(cache_entry)
        if cached_tree_data:
            genealogy_data = {
                'account_genealogy_items': [],
                'tree_data': cached_tree_data
            }
            # Data is fresh and available, skip refresh logic
        else:
            # Cache entry exists but no JSON, treat as stale
            is_fresh = False
    
    # Handle stale or missing cache
    if not is_fresh and genealogy_data is None:
        # Stale or missing cache, create PENDING entry to trigger cron jobs
        try:
            if cache_helpers:
                cache_entry = cache_helpers.create_pending_entry(account, network)
                is_refreshing = True
        except Exception as e:
            sentry_sdk.capture_exception(e)
            is_refreshing = False
        
        # Check if there's any cached data (even if stale) to show while processing
        if cache_entry and hasattr(cache_entry, 'cached_json') and cache_entry.cached_json:
            try:
                cached_tree_data = cache_helpers.get_cached_data(cache_entry)
                genealogy_data = {
                    'account_genealogy_items': [],
                    'tree_data': cached_tree_data or {
                        'name': account,
                        'node_type': 'ISSUER',
                        'children': []
                    }
                }
            except Exception:
                # No cached data available, show processing state
                genealogy_data = {
                    'account_genealogy_items': [],
                    'tree_data': {
                        'name': account,
                        'node_type': 'ISSUER',
                        'children': []
                    }
                }
        else:
            # No cached data at all, show processing state with account info
            genealogy_data = {
                'account_genealogy_items': [],
                'tree_data': {
                    'name': account,
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

    # Prepare request status data for display
    request_status_data = {}
    if cache_entry:
        request_status_data = {
            'stellar_account': cache_entry.stellar_account if hasattr(cache_entry, 'stellar_account') else account,
            'network': cache_entry.network if hasattr(cache_entry, 'network') else network,
            'status': cache_entry.status if hasattr(cache_entry, 'status') else 'UNKNOWN',
            'last_fetched_at': cache_entry.last_fetched_at.isoformat() if hasattr(cache_entry, 'last_fetched_at') and cache_entry.last_fetched_at else None,
            'created_at': cache_entry.created_at.isoformat() if hasattr(cache_entry, 'created_at') and cache_entry.created_at else None,
            'updated_at': cache_entry.updated_at.isoformat() if hasattr(cache_entry, 'updated_at') and cache_entry.updated_at else None,
            'has_cached_data': bool(cache_entry.cached_json) if hasattr(cache_entry, 'cached_json') else False,
            'cache_status': 'FRESH' if is_fresh else ('REFRESHING' if is_refreshing else 'STALE'),
        }
    else:
        request_status_data = {
            'stellar_account': account,
            'network': network,
            'status': 'NOT_FOUND',
            'cache_status': 'NO_CACHE_ENTRY',
            'message': 'No database entry found for this account/network combination'
        }

    # Fetch Account Lineage records from StellarCreatorAccountLineage
    # Recursively follow creator accounts up the lineage chain
    account_lineage_data = []
    try:
        from apiApp.models import StellarCreatorAccountLineage
        
        visited_accounts = set()
        accounts_to_process = [account]
        
        while accounts_to_process:
            current_account = accounts_to_process.pop(0)
            if current_account in visited_accounts:
                continue
            visited_accounts.add(current_account)
            
            try:
                lineage_records = StellarCreatorAccountLineage.objects.filter(
                    stellar_account=current_account,
                    network_name=network
                ).all()
                
                for record in lineage_records:
                    record_data = {
                        'stellar_account': record.stellar_account,
                        'stellar_creator_account': record.stellar_creator_account,
                        'network_name': record.network_name,
                        'stellar_account_created_at': record.stellar_account_created_at.isoformat() if record.stellar_account_created_at else None,
                        'home_domain': record.home_domain,
                        'xlm_balance': record.xlm_balance,
                        'horizon_accounts_doc_api_href': record.horizon_accounts_doc_api_href,
                        'status': record.status,
                        'created_at': record.created_at.isoformat() if hasattr(record, 'created_at') and record.created_at else None,
                        'updated_at': record.updated_at.isoformat() if hasattr(record, 'updated_at') and record.updated_at else None,
                    }
                    account_lineage_data.append(record_data)
                    
                    # Follow the creator chain: add creator account to process next
                    if record.stellar_creator_account and record.stellar_creator_account not in visited_accounts:
                        if record.stellar_creator_account not in accounts_to_process:
                            accounts_to_process.append(record.stellar_creator_account)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                continue
                
    except Exception as e:
        sentry_sdk.capture_exception(e)
        account_lineage_data = []

    context = {
        'search_variable': 'Cached Results' if is_fresh else ('Refreshing...' if is_refreshing else 'Live Search Results'),
        'ENV': config('ENV', default='development'),
        'SENTRY_DSN_VUE': config('SENTRY_DSN_VUE', default=''),
        'account_genealogy_items': genealogy_data['account_genealogy_items'],
        'tree_data': genealogy_data['tree_data'],
        'account': account,
        'network': network,
        'query_account': account,
        'network_selected': network,
        'radial_tidy_tree_variable': genealogy_data['tree_data'],  # Required for JS visualization
        'is_cached': is_fresh,
        'is_refreshing': is_refreshing,
        'request_status_data': request_status_data,
        'account_lineage_data': account_lineage_data,
    }
    return render(request, 'webApp/search.html', context)
