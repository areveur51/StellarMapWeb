# webApp/views.py
import json
import os
from decouple import config
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache  # For efficient caching
from django.http import Http404  # For secure error handling
from django_ratelimit.decorators import ratelimit
import sentry_sdk
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers  # For secure validation
from apiApp.helpers.sm_cache import StellarMapCacheHelpers
from apiApp.helpers.sm_stage_execution import initialize_stage_executions


def index_view(request):
    """
    Render the main landing page with search interface.

    Returns:
        HttpResponse: Rendered landing page.
    """
    return render(request, 'webApp/index.html')


@ratelimit(key='ip', rate='20/m', method='GET', block=True)
def search_view(request):
    """
    Handle search view: Validate params, fetch genealogy, render with context.
    
    Rate limited to 20 requests per minute per IP address.
    If no account is provided, loads default test data from test.json.
    Uses caching for genealogy data to reduce API/DB load.

    Args:
        request: HttpRequest object.

    Returns:
        HttpResponse: Rendered template.

    Raises:
        Http404: On invalid inputs.
    """
    
    # Helper function to fetch pending accounts from BOTH tables
    def fetch_pending_accounts():
        pending_accounts_data = []
        try:
            from apiApp.models import (
                StellarAccountSearchCache, 
                StellarCreatorAccountLineage,
                PENDING_MAKE_PARENT_LINEAGE, 
                IN_PROGRESS_MAKE_PARENT_LINEAGE, 
                RE_INQUIRY,
                PENDING_HORIZON_API_DATASETS,
                IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS,
                DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS,
                IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_OPERATIONS,
                DONE_COLLECTING_HORIZON_API_DATASETS_OPERATIONS,
                IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_EFFECTS,
                DONE_HORIZON_API_DATASETS,
                IN_PROGRESS_UPDATING_FROM_RAW_DATA,
                DONE_UPDATING_FROM_RAW_DATA,
                IN_PROGRESS_UPDATING_FROM_OPERATIONS_RAW_DATA,
                DONE_UPDATING_FROM_OPERATIONS_RAW_DATA,
                IN_PROGRESS_MAKE_GRANDPARENT_LINEAGE,
                DONE_GRANDPARENT_LINEAGE,
                STUCK_THRESHOLDS,
            )
            from datetime import datetime
            
            def convert_timestamp(ts):
                if ts is None:
                    return None
                if isinstance(ts, datetime):
                    return ts.isoformat()
                if isinstance(ts, (int, float)):
                    return datetime.fromtimestamp(ts / 1000).isoformat()
                return str(ts)
            
            def calculate_age_and_stuck(record, status):
                """Calculate record age and determine if it's stuck."""
                now = datetime.utcnow()
                age_minutes = 0
                is_stuck = False
                
                if hasattr(record, 'updated_at') and record.updated_at:
                    age_delta = now - record.updated_at
                    age_minutes = int(age_delta.total_seconds() / 60)
                    
                    # Check if stuck based on threshold
                    threshold = STUCK_THRESHOLDS.get(status, 30)  # Default 30 min
                    is_stuck = age_minutes > threshold
                
                return age_minutes, is_stuck
            
            # Query StellarAccountSearchCache
            for status_val in [PENDING_MAKE_PARENT_LINEAGE, IN_PROGRESS_MAKE_PARENT_LINEAGE, RE_INQUIRY]:
                try:
                    records = StellarAccountSearchCache.objects.filter(status=status_val).all()
                    for record in records:
                        age_minutes, is_stuck = calculate_age_and_stuck(record, status_val)
                        
                        pending_accounts_data.append({
                            'table': 'StellarAccountSearchCache',
                            'stellar_account': record.stellar_account,
                            'network_name': record.network_name,
                            'status': status_val,
                            'created_at': convert_timestamp(record.created_at) if hasattr(record, 'created_at') else None,
                            'updated_at': convert_timestamp(record.updated_at) if hasattr(record, 'updated_at') else None,
                            'last_fetched_at': convert_timestamp(record.last_fetched_at) if hasattr(record, 'last_fetched_at') else None,
                            'age_minutes': age_minutes,
                            'is_stuck': is_stuck,
                            'retry_count': getattr(record, 'retry_count', 0),
                        })
                except Exception:
                    pass
            
            # Query StellarCreatorAccountLineage (all pipeline stages)
            lineage_statuses = [
                PENDING_HORIZON_API_DATASETS,
                IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS,
                DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS,
                IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_OPERATIONS,
                DONE_COLLECTING_HORIZON_API_DATASETS_OPERATIONS,
                IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_EFFECTS,
                DONE_HORIZON_API_DATASETS,
                IN_PROGRESS_UPDATING_FROM_RAW_DATA,
                DONE_UPDATING_FROM_RAW_DATA,
                IN_PROGRESS_UPDATING_FROM_OPERATIONS_RAW_DATA,
                DONE_UPDATING_FROM_OPERATIONS_RAW_DATA,
                IN_PROGRESS_MAKE_GRANDPARENT_LINEAGE,
                DONE_GRANDPARENT_LINEAGE,
            ]
            for status_val in lineage_statuses:
                try:
                    records = StellarCreatorAccountLineage.objects.filter(status=status_val).all()
                    for record in records:
                        age_minutes, is_stuck = calculate_age_and_stuck(record, status_val)
                        
                        pending_accounts_data.append({
                            'table': 'StellarCreatorAccountLineage',
                            'stellar_account': record.stellar_account,
                            'stellar_creator_account': record.stellar_creator_account,
                            'network_name': record.network_name,
                            'status': status_val,
                            'created_at': convert_timestamp(record.created_at) if hasattr(record, 'created_at') else None,
                            'updated_at': convert_timestamp(record.updated_at) if hasattr(record, 'updated_at') else None,
                            'age_minutes': age_minutes,
                            'is_stuck': is_stuck,
                            'retry_count': getattr(record, 'retry_count', 0),
                        })
                except Exception:
                    pass
        except Exception:
            pending_accounts_data = []
        return pending_accounts_data
    
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
            network = 'public'  # Default to public network
            
            # Fetch pending accounts for default view - use helper function
            pending_accounts_data = fetch_pending_accounts()
            
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
                'pending_accounts_data': pending_accounts_data,
                'request_status_data': {},
                'account_lineage_data': [],
            }
            response = render(request, 'webApp/search.html', context)
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response
            
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
            network = 'public'
            
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
            response = render(request, 'webApp/search.html', context)
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response
    
    # If account was provided, validate and process
    # Secure validation
    validator = StellarMapValidatorHelpers()
    if not validator.validate_stellar_account_address(account):
        sentry_sdk.capture_message(f"Invalid Stellar account: {account}")
        # Don't throw 404, show error message instead
        context = {
            'search_variable': 'Invalid Address',
            'ENV': config('ENV', default='development'),
            'SENTRY_DSN_VUE': config('SENTRY_DSN_VUE', default=''),
            'account_genealogy_items': [],
            'tree_data': {'name': 'Error', 'node_type': 'ERROR', 'children': []},
            'account': account,
            'network': network,
            'query_account': account,
            'network_selected': network,
            'radial_tidy_tree_variable': {'name': 'Error', 'node_type': 'ERROR', 'children': []},
            'is_cached': False,
            'is_refreshing': False,
            'request_status_data': {
                'stellar_account': account,
                'network': network,
                'status': 'INVALID_ADDRESS',
                'cache_status': 'ERROR',
                'message': 'Invalid Stellar account address format. Must be 56 characters starting with G.'
            },
            'account_lineage_data': [],
            'pending_accounts_data': fetch_pending_accounts(),
        }
        response = render(request, 'webApp/search.html', context)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    
    if network not in ['public', 'testnet']:
        context = {
            'search_variable': 'Invalid Network',
            'ENV': config('ENV', default='development'),
            'SENTRY_DSN_VUE': config('SENTRY_DSN_VUE', default=''),
            'account_genealogy_items': [],
            'tree_data': {'name': 'Error', 'node_type': 'ERROR', 'children': []},
            'account': account,
            'network': network,
            'query_account': account,
            'network_selected': network,
            'radial_tidy_tree_variable': {'name': 'Error', 'node_type': 'ERROR', 'children': []},
            'is_cached': False,
            'is_refreshing': False,
            'request_status_data': {
                'stellar_account': account,
                'network': network,
                'status': 'INVALID_NETWORK',
                'cache_status': 'ERROR',
                'message': 'Invalid network. Must be "public" or "testnet".'
            },
            'account_lineage_data': [],
            'pending_accounts_data': fetch_pending_accounts(),
        }
        response = render(request, 'webApp/search.html', context)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    # 12-hour Cassandra cache strategy (with fallback for schema migration)
    is_fresh = False
    is_refreshing = False
    genealogy_data = None
    cache_helpers = None
    cache_entry = None
    
    try:
        cache_helpers = StellarMapCacheHelpers()
        is_fresh, cache_entry = cache_helpers.check_cache_freshness(account, network_name=network)
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
                cache_entry = cache_helpers.create_pending_entry(account, network_name=network)
                is_refreshing = True
                
                # Initialize all stage execution records for tracking
                try:
                    initialize_stage_executions(account, network)
                except Exception as stage_init_error:
                    sentry_sdk.capture_exception(stage_init_error)
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
            'network': cache_entry.network_name if hasattr(cache_entry, 'network_name') else network,
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
                    # Extract assets from horizon_accounts_json
                    assets = []
                    if record.horizon_accounts_json:
                        try:
                            import json
                            horizon_data = json.loads(record.horizon_accounts_json)
                            balances = horizon_data.get('balances', [])
                            
                            for balance in balances:
                                asset_type = balance.get('asset_type', '')
                                if asset_type != 'native':
                                    asset_code = balance.get('asset_code', '')
                                    asset_issuer = balance.get('asset_issuer', '')
                                    asset_balance = balance.get('balance', '0')
                                    
                                    assets.append({
                                        'name': asset_code,
                                        'node_type': 'ASSET',
                                        'asset_type': asset_type,
                                        'asset_code': asset_code,
                                        'asset_issuer': asset_issuer,
                                        'balance': float(asset_balance) if asset_balance else 0.0
                                    })
                        except (json.JSONDecodeError, KeyError, ValueError):
                            pass
                    
                    record_data = {
                        'stellar_account': record.stellar_account,
                        'stellar_creator_account': record.stellar_creator_account,
                        'network_name': record.network_name,
                        'stellar_account_created_at': record.stellar_account_created_at.isoformat() if record.stellar_account_created_at else None,
                        'home_domain': record.home_domain,
                        'xlm_balance': record.xlm_balance,
                        'assets': assets,
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

    # Fetch all pending accounts from BOTH tables using helper function
    pending_accounts_data = fetch_pending_accounts()

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
        'pending_accounts_data': pending_accounts_data,
    }
    
    response = render(request, 'webApp/search.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


def dashboard_view(request):
    """
    Dashboard view for monitoring system health, BigQuery costs, and database stats.
    
    Displays:
    - BigQuery cost and size tracking
    - Performance metrics
    - Cassandra DB health indicators
    - Stale records tracking
    - Other stats to prevent data loss
    """
    from apiApp.models import (
        BigQueryPipelineConfig,
        StellarAccountSearchCache,
        StellarCreatorAccountLineage,
        StellarAccountStageExecution,
        ManagementCronHealth,
        PENDING,
        PROCESSING,
        COMPLETE,
        STUCK_THRESHOLD_MINUTES,
        STUCK_STATUSES,
    )
    from datetime import datetime, timedelta
    import json
    
    # Status constants (using string literals for pipeline-specific statuses)
    PENDING_MAKE_PARENT_LINEAGE = 'PENDING_MAKE_PARENT_LINEAGE'
    IN_PROGRESS_MAKE_PARENT_LINEAGE = 'IN_PROGRESS_MAKE_PARENT_LINEAGE'
    DONE_MAKE_PARENT_LINEAGE = 'DONE_MAKE_PARENT_LINEAGE'
    RE_INQUIRY = 'RE_INQUIRY'
    
    # Get BigQuery configuration
    bigquery_config = None
    try:
        bigquery_config = BigQueryPipelineConfig.objects.get(config_id='default')
    except Exception:
        pass
    
    # Calculate database health stats
    db_stats = {
        'total_cached_accounts': 0,
        'fresh_accounts': 0,
        'stale_accounts': 0,
        'pending_accounts': 0,
        'in_progress_accounts': 0,
        'completed_accounts': 0,
        're_inquiry_accounts': 0,
        'stuck_accounts': 0,
        'total_lineage_records': 0,
        'accounts_with_lineage': 0,
        'orphan_accounts': 0,
    }
    
    # Count cache records
    try:
        all_cache_records = StellarAccountSearchCache.objects.all()
        db_stats['total_cached_accounts'] = len(list(all_cache_records))
        
        # Count by status
        db_stats['pending_accounts'] = len(list(
            StellarAccountSearchCache.objects.filter(status=PENDING_MAKE_PARENT_LINEAGE).all()
        ))
        db_stats['in_progress_accounts'] = len(list(
            StellarAccountSearchCache.objects.filter(status=IN_PROGRESS_MAKE_PARENT_LINEAGE).all()
        ))
        db_stats['completed_accounts'] = len(list(
            StellarAccountSearchCache.objects.filter(status=DONE_MAKE_PARENT_LINEAGE).all()
        ))
        db_stats['re_inquiry_accounts'] = len(list(
            StellarAccountSearchCache.objects.filter(status=RE_INQUIRY).all()
        ))
        
        # Count fresh vs stale (using cache TTL from config)
        cache_ttl_hours = bigquery_config.cache_ttl_hours if bigquery_config else 12
        staleness_threshold = datetime.utcnow() - timedelta(hours=cache_ttl_hours)
        
        fresh_count = 0
        stale_count = 0
        stuck_count = 0
        
        for record in all_cache_records:
            if hasattr(record, 'updated_at') and record.updated_at:
                if record.updated_at > staleness_threshold:
                    fresh_count += 1
                else:
                    stale_count += 1
                
                # Check if stuck (using model-defined thresholds)
                age_minutes = (datetime.utcnow() - record.updated_at).total_seconds() / 60
                # Use 5-minute threshold for core statuses (PENDING, PROCESSING), 30 min for others
                threshold = STUCK_THRESHOLD_MINUTES if record.status in STUCK_STATUSES else 30
                if age_minutes > threshold:
                    stuck_count += 1
        
        db_stats['fresh_accounts'] = fresh_count
        db_stats['stale_accounts'] = stale_count
        db_stats['stuck_accounts'] = stuck_count
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
    
    # Count lineage records
    try:
        all_lineage_records = StellarCreatorAccountLineage.objects.all()
        db_stats['total_lineage_records'] = len(list(all_lineage_records))
        
        # Count unique accounts with lineage
        unique_accounts = set()
        for record in all_lineage_records:
            unique_accounts.add(record.stellar_account)
        db_stats['accounts_with_lineage'] = len(unique_accounts)
        
        # Find orphan accounts (in cache but no lineage) - OPTIMIZED: use values_list
        try:
            cache_accounts = set(
                StellarAccountSearchCache.objects
                .filter(status=DONE_MAKE_PARENT_LINEAGE)
                .values_list('stellar_account', flat=True)
            )
            
            orphans = cache_accounts - unique_accounts
            db_stats['orphan_accounts'] = len(orphans)
        except Exception:
            pass
            
    except Exception as e:
        sentry_sdk.capture_exception(e)
    
    # Performance metrics
    performance_stats = {
        'avg_processing_time_minutes': 0,
        'fastest_account_minutes': None,
        'slowest_account_minutes': None,
        'total_accounts_processed_24h': 0,
        'total_accounts_processed_7d': 0,
    }
    
    try:
        # Calculate average processing time from completed accounts - OPTIMIZED: only load needed fields
        now = datetime.utcnow()
        processing_times = []
        
        # Only fetch created_at and updated_at fields instead of full objects
        completed_records = (
            StellarAccountSearchCache.objects
            .filter(status=DONE_MAKE_PARENT_LINEAGE)
            .only('created_at', 'updated_at')
        )
        
        for record in completed_records:
            if record.created_at and record.updated_at:
                delta = record.updated_at - record.created_at
                minutes = delta.total_seconds() / 60
                processing_times.append(minutes)
                
                # Count accounts processed in last 24h and 7d
                if record.updated_at > now - timedelta(hours=24):
                    performance_stats['total_accounts_processed_24h'] += 1
                if record.updated_at > now - timedelta(days=7):
                    performance_stats['total_accounts_processed_7d'] += 1
        
        if processing_times:
            performance_stats['avg_processing_time_minutes'] = sum(processing_times) / len(processing_times)
            performance_stats['fastest_account_minutes'] = min(processing_times)
            performance_stats['slowest_account_minutes'] = max(processing_times)
    
    except Exception as e:
        sentry_sdk.capture_exception(e)
    
    # BigQuery cost tracking (estimated from config and usage)
    bigquery_stats = {
        'cost_limit_usd': 0.71,
        'size_limit_gb': 145,
        'estimated_cost_per_account': 0.35,
        'estimated_monthly_cost': 0,
        'accounts_remaining_in_budget': 0,
        'bigquery_enabled': False,
        'pipeline_mode': 'API_ONLY',
    }
    
    if bigquery_config:
        bigquery_stats['cost_limit_usd'] = bigquery_config.cost_limit_usd
        bigquery_stats['size_limit_gb'] = bigquery_config.size_limit_mb / 1024
        bigquery_stats['bigquery_enabled'] = bigquery_config.bigquery_enabled
        bigquery_stats['pipeline_mode'] = getattr(bigquery_config, 'pipeline_mode', 'API_ONLY')
        
        # Estimate monthly costs based on processing rate
        if performance_stats['total_accounts_processed_7d'] > 0:
            weekly_accounts = performance_stats['total_accounts_processed_7d']
            monthly_accounts = (weekly_accounts / 7) * 30
            bigquery_stats['estimated_monthly_cost'] = monthly_accounts * bigquery_stats['estimated_cost_per_account']
            
            # Calculate how many more accounts can be processed within budget (assume $100/month budget)
            monthly_budget = 100.0
            if bigquery_stats['estimated_cost_per_account'] > 0:
                bigquery_stats['accounts_remaining_in_budget'] = int(
                    (monthly_budget - bigquery_stats['estimated_monthly_cost']) / 
                    bigquery_stats['estimated_cost_per_account']
                )
    
    # Cron health check
    cron_health = {
        'last_run': None,
        'status': 'UNKNOWN',
        'total_runs': 0,
    }
    
    try:
        cron_records = ManagementCronHealth.objects.all()
        cron_list = list(cron_records)
        cron_health['total_runs'] = len(cron_list)
        
        if cron_list:
            latest_cron = max(cron_list, key=lambda x: x.created_at if hasattr(x, 'created_at') and x.created_at else datetime.min)
            cron_health['last_run'] = latest_cron.created_at.isoformat() if hasattr(latest_cron, 'created_at') and latest_cron.created_at else None
            cron_health['status'] = latest_cron.status if hasattr(latest_cron, 'status') else 'UNKNOWN'
    
    except Exception as e:
        sentry_sdk.capture_exception(e)
    
    # Stage execution health
    stage_health = {
        'total_stage_executions': 0,
        'failed_stages': 0,
        'in_progress_stages': 0,
        'completed_stages': 0,
    }
    
    try:
        stage_records = StellarAccountStageExecution.objects.all()
        stage_list = list(stage_records)
        stage_health['total_stage_executions'] = len(stage_list)
        
        for record in stage_list:
            if hasattr(record, 'status'):
                if 'ERROR' in record.status or 'FAILED' in record.status:
                    stage_health['failed_stages'] += 1
                elif 'IN_PROGRESS' in record.status:
                    stage_health['in_progress_stages'] += 1
                elif 'DONE' in record.status or 'COMPLETE' in record.status:
                    stage_health['completed_stages'] += 1
    
    except Exception as e:
        sentry_sdk.capture_exception(e)
    
    # API Health Monitoring (rate limiter stats)
    api_health = {
        'horizon_calls_this_minute': 0,
        'horizon_burst_limit': 120,
        'horizon_rate_delay': 0.5,
        'horizon_last_call': None,
        'stellar_expert_calls_this_minute': 0,
        'stellar_expert_burst_limit': 50,
        'stellar_expert_rate_delay': 1.0,
        'stellar_expert_last_call': None,
        'bigquery_calls_this_minute': 0,
        'bigquery_burst_limit': 1000,
        'rate_limiting_enabled': True,
    }
    
    try:
        from apiApp.helpers.api_rate_limiter import APIRateLimiter
        limiter = APIRateLimiter()
        stats = limiter.get_stats()
        
        # Horizon API stats
        api_health['horizon_calls_this_minute'] = stats['horizon']['calls_this_minute']
        api_health['horizon_burst_limit'] = stats['horizon']['burst_limit']
        api_health['horizon_rate_delay'] = stats['horizon']['rate_limit_delay']
        api_health['horizon_last_call'] = stats['horizon']['last_call']
        
        # Stellar Expert API stats
        api_health['stellar_expert_calls_this_minute'] = stats['stellar_expert']['calls_this_minute']
        api_health['stellar_expert_burst_limit'] = stats['stellar_expert']['burst_limit']
        api_health['stellar_expert_rate_delay'] = stats['stellar_expert']['rate_limit_delay']
        api_health['stellar_expert_last_call'] = stats['stellar_expert']['last_call']
        
        # BigQuery stats
        api_health['bigquery_calls_this_minute'] = stats['bigquery']['calls_this_minute']
        api_health['bigquery_burst_limit'] = stats['bigquery']['burst_limit']
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        api_health['rate_limiting_enabled'] = False
    
    context = {
        'db_stats': db_stats,
        'performance_stats': performance_stats,
        'bigquery_stats': bigquery_stats,
        'cron_health': cron_health,
        'stage_health': stage_health,
        'bigquery_config': bigquery_config,
        'api_health': api_health,
    }
    
    return render(request, 'webApp/dashboard.html', context)


def theme_test_view(request):
    """
    Theme testing page to debug theme switching functionality.
    
    Returns:
        HttpResponse: Rendered theme test page.
    """
    return render(request, 'webApp/theme_test.html')


def high_value_accounts_view(request):
    """
    High Value Accounts (HVA) view - displays accounts above a configurable XLM threshold.
    Supports multiple threshold leaderboards (10K, 50K, 100K, 500K, 750K, 1M XLM).
    Now includes rank change tracking from HVAStandingChange events.
    
    Query Parameters:
        threshold: XLM threshold to use (default: admin-configured threshold)
    
    Returns:
        HttpResponse: Rendered HVA page with list of high value accounts.
    """
    from apiApp.models import StellarCreatorAccountLineage, HVAStandingChange, BigQueryPipelineConfig
    from apiApp.helpers.hva_ranking import HVARankingHelper
    from datetime import timedelta
    from django.utils import timezone
    import sentry_sdk
    
    # Get network from query parameter (default: public)
    network_name = request.GET.get('network', 'public')
    if network_name not in ['public', 'testnet']:
        network_name = 'public'
    
    # Get threshold from query parameter or use admin-configured default
    try:
        threshold_param = request.GET.get('threshold')
        if threshold_param:
            selected_threshold = float(threshold_param)
        else:
            # Use admin-configured default
            selected_threshold = HVARankingHelper.get_hva_threshold()
    except (ValueError, TypeError):
        selected_threshold = HVARankingHelper.get_hva_threshold()
    
    # Validate threshold is supported
    supported_thresholds = HVARankingHelper.get_supported_thresholds()
    if selected_threshold not in supported_thresholds:
        # Find closest supported threshold
        selected_threshold = min(
            supported_thresholds,
            key=lambda x: abs(x - selected_threshold)
        )
    
    hva_accounts = []
    total_hva_balance = 0
    
    try:
        # Query strategy based on selected threshold:
        # - If threshold <= admin default: Need to scan more records (potential accounts below is_hva threshold)
        # - If threshold > admin default: Can safely use is_hva filter
        admin_threshold = HVARankingHelper.get_hva_threshold()
        
        if selected_threshold <= admin_threshold:
            # Need broader query - get all accounts and filter in-memory
            # This is necessary because is_hva flag is based on admin_threshold
            # Note: This will do a table scan, but necessary for lower thresholds
            # OPTIMIZATION: Filter by network to reduce scan size
            all_records = StellarCreatorAccountLineage.objects.filter(network_name=network_name).all()
            hva_records = [
                rec for rec in all_records
                if rec.xlm_balance and rec.xlm_balance >= selected_threshold
            ]
        else:
            # Can use is_hva filter safely since selected_threshold > admin_threshold
            # OPTIMIZATION: Filter by network and is_hva flag
            hva_records = StellarCreatorAccountLineage.objects.filter(
                is_hva=True,
                network_name=network_name
            ).all()
            hva_records = [
                rec for rec in hva_records
                if rec.xlm_balance and rec.xlm_balance >= selected_threshold
            ]
        
        qualifying_records = hva_records
        
        sorted_records = sorted(
            qualifying_records,
            key=lambda x: x.xlm_balance if x.xlm_balance else 0,
            reverse=True
        )
        
        # Enrich with rank change data (last 24 hours)
        # NOTE: This uses N queries but each is efficient (partition-key lookup on stellar_account)
        # Batch fetching would require full table scan which is worse for Cassandra
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        for rank, record in enumerate(sorted_records, start=1):
            # Split tags into list for template rendering
            tags_list = [tag.strip() for tag in record.tags.split(',')] if record.tags else []
            
            # Get most recent standing change
            rank_change = 0
            event_type = None
            previous_rank = None
            balance_change_pct = 0.0
            
            try:
                # OPTIMIZATION: Query by partition key (stellar_account) for efficient lookup
                # Filter by threshold AND network in-memory for Cassandra compatibility
                all_changes = HVAStandingChange.objects.filter(
                    stellar_account=record.stellar_account
                ).all()
                
                # Filter by threshold AND network (in-memory for Cassandra compatibility)
                threshold_changes = [
                    c for c in all_changes 
                    if (hasattr(c, 'xlm_threshold') and abs(c.xlm_threshold - selected_threshold) < 1.0
                        and c.network_name == network_name)
                ]
                
                if threshold_changes:
                    # Get most recent change for this threshold
                    recent_change = sorted(threshold_changes, key=lambda x: x.created_at, reverse=True)[0]
                    
                    if recent_change.created_at and recent_change.created_at >= cutoff_time:
                        rank_change = recent_change.rank_change or 0
                        event_type = recent_change.event_type
                        previous_rank = recent_change.old_rank
                        balance_change_pct = recent_change.balance_change_pct or 0.0
            except Exception:
                pass  # Silently ignore change tracking errors
            
            hva_accounts.append({
                'stellar_account': record.stellar_account,
                'network_name': record.network_name,
                'xlm_balance': record.xlm_balance or 0,
                'stellar_creator_account': record.stellar_creator_account,
                'home_domain': record.home_domain,
                'tags': tags_list,
                'status': record.status,
                'created_at': record.created_at,
                'updated_at': record.updated_at,
                # Rank change data
                'current_rank': rank,
                'rank_change': rank_change,
                'event_type': event_type,
                'previous_rank': previous_rank,
                'balance_change_pct': balance_change_pct,
            })
            total_hva_balance += (record.xlm_balance or 0)
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
    
    context = {
        'hva_accounts': hva_accounts,
        'total_hva_count': len(hva_accounts),
        'total_hva_balance': total_hva_balance,
        'selected_threshold': selected_threshold,
        'supported_thresholds': HVARankingHelper.get_supported_thresholds(),
        'admin_default_threshold': HVARankingHelper.get_hva_threshold(),
    }
    
    return render(request, 'webApp/high_value_accounts.html', context)


@ratelimit(key='ip', rate='10/m', method='GET', block=True)
def bulk_search_view(request):
    """
    Bulk search view: Page for queuing multiple Stellar accounts at once.
    
    Rate limited to 10 requests per minute per IP address.
    Allows users to paste multiple accounts (enter, comma, or space delimited)
    and queue them all for pipeline processing.

    Args:
        request: HttpRequest object.

    Returns:
        HttpResponse: Rendered bulk search page.
    """
    return render(request, 'webApp/bulk_search.html')


@ratelimit(key='ip', rate='20/m', method='GET', block=True)
def query_builder_view(request):
    """
    Query Builder view: Interactive page for analyzing Cassandra database data.
    
    Rate limited to 20 requests per minute per IP address.
    Allows users to select pre-defined queries from the dashboard or build custom queries
    to explore and analyze Cassandra database records.

    Args:
        request: HttpRequest object.

    Returns:
        HttpResponse: Rendered query builder page.
    """
    return render(request, 'webApp/query_builder.html')
