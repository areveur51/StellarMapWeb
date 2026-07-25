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
from apiApp.helpers.sm_datetime import utc_now, ensure_aware, age_seconds
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers  # For secure validation
from apiApp.helpers.sm_cache import StellarMapCacheHelpers
from apiApp.helpers.sm_stage_execution import initialize_stage_executions


def _skeleton_tree(account):
    """Minimal D3 tree placeholder while lineage is processing or missing."""
    return {
        'name': account or 'Root',
        'node_type': 'ISSUER',
        'stellar_account': account or '',
        'children': [],
        'is_lineage_path': True,
        'is_sibling': False,
        'is_searched_account': True,
        'is_issuer': False,
    }


def _lineage_example_paths():
    """Candidate paths for the demo radial tree (schema matches buildTreeFromLineage_v1)."""
    base = settings.BASE_DIR.parent
    return [
        os.path.join(
            base,
            'radialTidyTreeApp',
            'static',
            'radialTidyTreeApp',
            'json',
            'lineage_example.json',
        ),
        os.path.join(
            base,
            'static',
            'radialTidyTreeApp',
            'json',
            'lineage_example.json',
        ),
        # Legacy fallback (older schema) only if example file missing
        os.path.join(
            base,
            'radialTidyTreeApp',
            'static',
            'radialTidyTreeApp',
            'json',
            'test_small.json',
        ),
    ]


def _load_lineage_example_tree():
    """
    Load the canned example tree for /search/ with no account param.

    This is **not** live public/testnet data — it demonstrates how real
    aggregated lineage + siblings + assets should appear in the radial tree.
    """
    last_err = None
    for path in _lineage_example_paths():
        try:
            if not os.path.isfile(path):
                continue
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and (
                data.get('stellar_account') or data.get('name') or data.get('children') is not None
            ):
                return data, path
        except Exception as e:
            last_err = e
            continue
    if last_err:
        sentry_sdk.capture_exception(last_err)
    return None, None


def _find_searched_account_in_tree(node):
    """Prefer the node flagged is_searched_account; else deepest lineage leaf."""
    if not isinstance(node, dict):
        return ''
    if node.get('is_searched_account') and node.get('stellar_account'):
        return node['stellar_account']
    for child in node.get('children') or []:
        if not isinstance(child, dict):
            continue
        if child.get('node_type') == 'ASSET':
            continue
        found = _find_searched_account_in_tree(child)
        if found:
            return found
    if node.get('is_lineage_path') and node.get('stellar_account'):
        # leaf-ish: no ISSUER children
        issuer_kids = [
            c for c in (node.get('children') or [])
            if isinstance(c, dict) and c.get('node_type') != 'ASSET'
        ]
        if not issuer_kids:
            return node['stellar_account']
    return node.get('stellar_account') or node.get('name') or ''


def _example_table_rows_from_tree(tree):
    """Flatten ISSUER nodes into a simple lineage-table-shaped list for the demo."""
    rows = []

    def walk(n, level=0):
        if not isinstance(n, dict):
            return
        if n.get('node_type') == 'ASSET':
            return
        addr = n.get('stellar_account') or n.get('name') or ''
        if addr:
            rows.append({
                'stellar_account': addr,
                'stellar_creator_account': n.get('creator_account') or '',
                'network_name': 'public',
                'stellar_account_created_at': n.get('created') or '',
                'home_domain': n.get('home_domain') or '',
                'xlm_balance': n.get('xlm_balance') if n.get('xlm_balance') is not None else '',
                'status': 'EXAMPLE',
                'is_lineage_path': bool(n.get('is_lineage_path')),
                'is_sibling': bool(n.get('is_sibling')),
                'is_searched_account': bool(n.get('is_searched_account')),
                'hierarchy_level': level,
            })
        for c in n.get('children') or []:
            if isinstance(c, dict) and c.get('node_type') != 'ASSET':
                walk(c, level + 1)

    walk(tree or {}, 0)
    return rows


def _is_terminal_search_cache_status(status):
    """
    True when search-cache / lineage status means processing finished.
    Used to avoid re-PENDING COMPLETE accounts solely for invalid cache body.
    """
    if not status:
        return False
    s = str(status).upper()
    if s in (
        'DONE_MAKE_PARENT_LINEAGE',
        'COMPLETE',
        'BIGQUERY_COMPLETE',
        'API_COMPLETE',
        'DONE',
    ):
        return True
    if s.startswith('DONE_'):
        return True
    if 'COMPLETE' in s and 'IN_PROGRESS' not in s and 'PENDING' not in s:
        return True
    return False


def _search_ssr_via_unified_aggregate(account, network):
    """
    Build search page tree + lineage table from LineageAggregateService.

    PR3: flag-gated path (LINEAGE_UNIFIED_AGGREGATE). DB-only aggregation;
    never Horizon. Avoids create_pending_entry when status is already terminal
    but cached_json is invalid/missing (re-PENDING loop fix).

    Returns:
        dict with genealogy_data, account_lineage_data, is_fresh, is_refreshing,
        cache_entry, meta
    """
    from apiApp.helpers.sm_lineage_aggregate import (
        AggregateOptions,
        LineageAggregateService,
        maybe_rebuild_projection_on_complete,
        parse_cache_body,
        write_projection_enabled,
    )

    include_siblings = bool(getattr(settings, 'LINEAGE_SSR_INCLUDE_SIBLINGS', False))
    options = AggregateOptions.from_settings(
        include_siblings=include_siblings,
        use_search_cache=True,
        force_rebuild=False,
    )

    is_fresh = False
    is_refreshing = False
    cache_helpers = None
    cache_entry = None
    body_kind = 'miss'

    try:
        cache_helpers = StellarMapCacheHelpers()
        is_fresh, cache_entry = cache_helpers.check_cache_freshness(
            account, network_name=network
        )
    except Exception as cache_error:
        sentry_sdk.capture_exception(cache_error)
        is_fresh = False
        cache_entry = None

    if cache_entry is not None:
        body_kind, _ = parse_cache_body(getattr(cache_entry, 'cached_json', None))
        if body_kind == 'miss':
            # Fresh timestamp but unusable body (e.g. legacy str(dict)) is not fresh
            is_fresh = False

    terminal = _is_terminal_search_cache_status(
        getattr(cache_entry, 'status', None) if cache_entry else None
    )
    svc = LineageAggregateService()
    projection = None

    if body_kind in ('projection', 'legacy_tree') and not options.force_rebuild:
        # Serve from dual-format cache reader inside get_projection
        projection = svc.get_projection(account, network, options)
        if body_kind == 'projection' and is_fresh:
            pass  # keep is_fresh
        elif body_kind in ('projection', 'legacy_tree'):
            # Stale-but-usable body: show it; do not thrash PENDING if terminal
            if not terminal and not is_fresh:
                try:
                    if cache_helpers:
                        cache_entry = cache_helpers.create_pending_entry(
                            account, network_name=network
                        )
                        is_refreshing = True
                        try:
                            initialize_stage_executions(account, network)
                        except Exception as stage_init_error:
                            sentry_sdk.capture_exception(stage_init_error)
                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    is_refreshing = False

    elif terminal:
        # Invalid/empty body but complete status: rebuild DB-only, never re-PENDING
        if write_projection_enabled():
            projection = maybe_rebuild_projection_on_complete(account, network)
        if projection is None:
            build_opts = AggregateOptions.from_settings(
                include_siblings=include_siblings,
                use_search_cache=False,
                force_rebuild=True,
            )
            projection = svc.build_projection(account, network, build_opts)
        is_fresh = True
        is_refreshing = False

    else:
        # New / in-progress / no terminal status: queue for pipelines if needed
        try:
            if cache_helpers:
                cache_entry = cache_helpers.create_pending_entry(
                    account, network_name=network
                )
                is_refreshing = True
                try:
                    initialize_stage_executions(account, network)
                except Exception as stage_init_error:
                    sentry_sdk.capture_exception(stage_init_error)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            is_refreshing = False

        build_opts = AggregateOptions.from_settings(
            include_siblings=include_siblings,
            use_search_cache=False,
            force_rebuild=True,
        )
        try:
            projection = svc.build_projection(account, network, build_opts)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            projection = None

    if not projection:
        projection = {
            'account': account,
            'network': network,
            'lineage_path': [],
            'nodes': {},
            'siblings_by_creator': {},
            'tree': _skeleton_tree(account),
            'meta': {'db_only': True, 'empty': True},
        }

    tree = svc.to_tree(projection) if projection.get('nodes') or projection.get('tree') else _skeleton_tree(account)
    if not tree or not isinstance(tree, dict):
        tree = _skeleton_tree(account)
    # Guard: never pass full projection object as D3 root
    if tree.get('schema_version') is not None and 'nodes' in tree:
        tree = tree.get('tree') or _skeleton_tree(account)

    account_lineage_data = svc.to_table_rows(projection)

    genealogy_data = {
        'account_genealogy_items': [],
        'tree_data': tree,
    }

    return {
        'genealogy_data': genealogy_data,
        'account_lineage_data': account_lineage_data,
        'is_fresh': is_fresh,
        'is_refreshing': is_refreshing,
        'cache_entry': cache_entry,
        'meta': projection.get('meta') or {},
    }


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
        # Lab RO: never full-scan Cassandra by status (no secondary index → multi-minute hang)
        if getattr(settings, 'CASSANDRA_READ_ONLY', False):
            return []
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
                now = utc_now()
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
    
    # No account param: show canned example tree (schema matches real aggregate output).
    # This is a demo of creator-path + siblings + assets — not live network data.
    if not account:
        tree_data, example_path = _load_lineage_example_tree()
        if not tree_data:
            tree_data = _skeleton_tree(
                'GD6WU64OEP5C4LRBH6NK3MHYIA2ADN6K6II6EXPNVUR3ERBXT4AN4ACD'
            )
            tree_data['home_domain'] = 'example.stellarmap.demo'
            tree_data['is_searched_account'] = True

        network = 'public'
        demo_account = _find_searched_account_in_tree(tree_data) or tree_data.get(
            'stellar_account', ''
        )
        # Search box starts empty so users paste a real G… address to inquire
        account_lineage_data = _example_table_rows_from_tree(tree_data)
        pending_accounts_data = fetch_pending_accounts()

        context = {
            'search_variable': 'Example lineage visualization',
            'ENV': config('ENV', default='development'),
            'SENTRY_DSN_VUE': config('SENTRY_DSN_VUE', default=''),
            'account_genealogy_items': [],
            'tree_data': tree_data,
            'account': '',  # empty — not a live inquiry
            'network': network,
            'query_account': '',
            'network_selected': network,
            'radial_tidy_tree_variable': tree_data,
            'pending_accounts_data': pending_accounts_data,
            'request_status_data': {
                'status': 'EXAMPLE_DATASET',
                'cache_status': 'DEMO',
                'message': (
                    'Example radial tidy tree (not live public/testnet data). '
                    'Paste a Stellar account above to scan and aggregate real '
                    'creator-path + related accounts for that address.'
                ),
                'example_demo_account': demo_account,
                'example_source': example_path or 'fallback',
            },
            'account_lineage_data': account_lineage_data,
            'is_cached': False,
            'is_refreshing': False,
            'is_example_dataset': True,
            'lineage_progressive_siblings': bool(
                getattr(settings, 'LINEAGE_PROGRESSIVE_SIBLINGS', False)
            ),
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

    # LINEAGE_UNIFIED_AGGREGATE=1: single projection for table + tree (PR3)
    # Default off: legacy dual path (cache tree + separate O(D) table walk)
    use_unified = bool(getattr(settings, 'LINEAGE_UNIFIED_AGGREGATE', False))

    is_fresh = False
    is_refreshing = False
    genealogy_data = None
    cache_helpers = None
    cache_entry = None
    account_lineage_data = []

    if use_unified:
        unified = _search_ssr_via_unified_aggregate(account, network)
        genealogy_data = unified['genealogy_data']
        account_lineage_data = unified['account_lineage_data']
        is_fresh = unified['is_fresh']
        is_refreshing = unified['is_refreshing']
        cache_entry = unified['cache_entry']
    else:
        # --- legacy path (flag off) ---
        # 12-hour Cassandra cache strategy (with fallback for schema migration)
        try:
            cache_helpers = StellarMapCacheHelpers()
            is_fresh, cache_entry = cache_helpers.check_cache_freshness(
                account, network_name=network
            )
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
            else:
                # Cache entry exists but no JSON, treat as stale
                is_fresh = False

        # Handle stale or missing cache
        if not is_fresh and genealogy_data is None:
            # Stale or missing cache, create PENDING entry to trigger cron jobs
            try:
                if cache_helpers:
                    cache_entry = cache_helpers.create_pending_entry(
                        account, network_name=network
                    )
                    is_refreshing = True

                    try:
                        initialize_stage_executions(account, network)
                    except Exception as stage_init_error:
                        sentry_sdk.capture_exception(stage_init_error)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                is_refreshing = False

            if cache_entry and hasattr(cache_entry, 'cached_json') and cache_entry.cached_json:
                try:
                    cached_tree_data = cache_helpers.get_cached_data(cache_entry)
                    genealogy_data = {
                        'account_genealogy_items': [],
                        'tree_data': cached_tree_data or _skeleton_tree(account),
                    }
                except Exception:
                    genealogy_data = {
                        'account_genealogy_items': [],
                        'tree_data': _skeleton_tree(account),
                    }
            else:
                genealogy_data = {
                    'account_genealogy_items': [],
                    'tree_data': _skeleton_tree(account),
                }

        if genealogy_data is None:
            genealogy_data = {
                'account_genealogy_items': [],
                'tree_data': _skeleton_tree(account),
            }

        # Separate O(D) walk for Account Lineage table (legacy)
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
                        assets = []
                        if record.horizon_accounts_json:
                            try:
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

                        if record.stellar_creator_account and record.stellar_creator_account not in visited_accounts:
                            if record.stellar_creator_account not in accounts_to_process:
                                accounts_to_process.append(record.stellar_creator_account)
                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    continue

        except Exception as e:
            sentry_sdk.capture_exception(e)
            account_lineage_data = []

    # Ensure genealogy_data is set (fallback safety)
    if genealogy_data is None:
        genealogy_data = {
            'account_genealogy_items': [],
            'tree_data': _skeleton_tree(account),
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

    # Fetch all pending accounts from BOTH tables using helper function
    pending_accounts_data = fetch_pending_accounts()

    # radial_tidy_tree template may expect tree root; never pass projection envelope
    tree_for_ui = genealogy_data['tree_data']
    if isinstance(tree_for_ui, dict) and tree_for_ui.get('schema_version') is not None and 'nodes' in tree_for_ui:
        tree_for_ui = tree_for_ui.get('tree') or _skeleton_tree(account)
        genealogy_data['tree_data'] = tree_for_ui

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
        'lineage_unified_aggregate': use_unified,
        'lineage_progressive_siblings': bool(
            getattr(settings, 'LINEAGE_PROGRESSIVE_SIBLINGS', False)
        ),
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

    # Lab RO: full-table Cassandra scans hang for minutes (no secondary indexes).
    # Keep heartbeat + config; skip multi-scan aggregate counters.
    _skip_full_scans = bool(getattr(settings, 'CASSANDRA_READ_ONLY', False))
    
    # Count cache records
    try:
        if _skip_full_scans:
            raise RuntimeError('skip full cache scan in CASSANDRA_READ_ONLY')
        all_cache_records = StellarAccountSearchCache.objects.all()
        db_stats['total_cached_accounts'] = len(list(all_cache_records))
        
        # Count by status from Search Cache
        cache_pending = len(list(
            StellarAccountSearchCache.objects.filter(status=PENDING_MAKE_PARENT_LINEAGE).all()
        ))
        cache_in_progress = len(list(
            StellarAccountSearchCache.objects.filter(status=IN_PROGRESS_MAKE_PARENT_LINEAGE).all()
        ))
        cache_completed = len(list(
            StellarAccountSearchCache.objects.filter(status=DONE_MAKE_PARENT_LINEAGE).all()
        ))
        cache_re_inquiry = len(list(
            StellarAccountSearchCache.objects.filter(status=RE_INQUIRY).all()
        ))
        
        # Count fresh vs stale (using cache TTL from config)
        cache_ttl_hours = bigquery_config.cache_ttl_hours if bigquery_config else 12
        staleness_threshold = utc_now() - timedelta(hours=cache_ttl_hours)
        
        fresh_count = 0
        stale_count = 0
        stuck_count = 0
        
        for record in all_cache_records:
            if hasattr(record, 'updated_at') and record.updated_at:
                if record.updated_at > staleness_threshold:
                    fresh_count += 1
                else:
                    stale_count += 1
                
                # Check if stuck - ONLY for active processing statuses (not completed ones)
                # Only PENDING and PROCESSING can be "stuck" - completed records should not be counted
                if record.status in STUCK_STATUSES:
                    age_minutes = age_seconds(record.updated_at) / 60
                    # Use model-defined threshold (5 minutes for PENDING/PROCESSING)
                    if age_minutes > STUCK_THRESHOLD_MINUTES:
                        stuck_count += 1
        
        db_stats['fresh_accounts'] = fresh_count
        db_stats['stale_accounts'] = stale_count
        db_stats['stuck_accounts'] = stuck_count
        
        # COUNT FROM LINEAGE TABLE - All pipeline statuses (comprehensive)
        try:
            # PENDING: PENDING status in lineage table (used by both BigQuery and API pipelines)
            lineage_pending = len(list(
                StellarCreatorAccountLineage.objects.filter(status=PENDING).all()
            ))
            
            # IN_PROGRESS/PROCESSING: All active processing statuses
            lineage_processing = len(list(
                StellarCreatorAccountLineage.objects.filter(status=PROCESSING).all()
            ))
            
            # Also count API pipeline IN_PROGRESS statuses (not used by BigQuery pipeline)
            api_pipeline_in_progress_statuses = [
                'IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS',
                'IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_OPERATIONS',
                'IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_EFFECTS',
                'IN_PROGRESS_UPDATING_FROM_RAW_DATA',
                'IN_PROGRESS_UPDATING_FROM_OPERATIONS_RAW_DATA',
                'IN_PROGRESS_MAKE_GRANDPARENT_LINEAGE',
            ]
            
            api_pipeline_in_progress = 0
            for status in api_pipeline_in_progress_statuses:
                try:
                    count = len(list(StellarCreatorAccountLineage.objects.filter(status=status).all()))
                    api_pipeline_in_progress += count
                except Exception:
                    pass
            
            # COMPLETED: COMPLETE (API pipeline) and BIGQUERY_COMPLETE (BigQuery pipeline)
            lineage_complete = len(list(
                StellarCreatorAccountLineage.objects.filter(status=COMPLETE).all()
            ))
            
            try:
                bigquery_complete = len(list(
                    StellarCreatorAccountLineage.objects.filter(status='BIGQUERY_COMPLETE').all()
                ))
                lineage_complete += bigquery_complete
            except Exception:
                pass
            
            # Also count API pipeline DONE statuses (intermediate completion states)
            api_pipeline_done_statuses = [
                'DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS',
                'DONE_COLLECTING_HORIZON_API_DATASETS_OPERATIONS',
                'DONE_HORIZON_API_DATASETS',
                'DONE_UPDATING_FROM_RAW_DATA',
                'DONE_UPDATING_FROM_OPERATIONS_RAW_DATA',
                'DONE_GRANDPARENT_LINEAGE',
            ]
            
            for status in api_pipeline_done_statuses:
                try:
                    count = len(list(StellarCreatorAccountLineage.objects.filter(status=status).all()))
                    lineage_complete += count
                except Exception:
                    pass
            
            # FAILED: Count failed records from lineage table (both pipelines use FAILED status)
            try:
                lineage_failed = len(list(
                    StellarCreatorAccountLineage.objects.filter(status='FAILED').all()
                ))
                # Add failed accounts to re_inquiry count (they need attention like RE_INQUIRY)
                db_stats['re_inquiry_accounts'] = cache_re_inquiry + lineage_failed
            except Exception:
                db_stats['re_inquiry_accounts'] = cache_re_inquiry
            
            # COMBINE counts from both tables
            db_stats['pending_accounts'] = cache_pending + lineage_pending
            db_stats['in_progress_accounts'] = cache_in_progress + lineage_processing + api_pipeline_in_progress
            db_stats['completed_accounts'] = cache_completed + lineage_complete
            
        except Exception as e:
            # Fallback to cache-only counts if lineage query fails
            db_stats['pending_accounts'] = cache_pending
            db_stats['in_progress_accounts'] = cache_in_progress
            db_stats['completed_accounts'] = cache_completed
            db_stats['re_inquiry_accounts'] = cache_re_inquiry
            sentry_sdk.capture_exception(e)
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
    
    # Count lineage records
    try:
        if _skip_full_scans:
            raise RuntimeError('skip full lineage scan in CASSANDRA_READ_ONLY')
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
    
    # Performance metrics - Calculate from BOTH Search Cache AND Lineage tables
    performance_stats = {
        'avg_processing_time_minutes': 0,
        'fastest_account_minutes': None,
        'slowest_account_minutes': None,
        'total_accounts_processed_24h': 0,
        'total_accounts_processed_7d': 0,
    }
    
    try:
        if _skip_full_scans:
            raise RuntimeError('skip performance dual scan in CASSANDRA_READ_ONLY')
        # Calculate average processing time from completed accounts - DUAL TABLE SCAN
        now = utc_now()
        processing_times = []
        
        # SEARCH CACHE: Fetch DONE_MAKE_PARENT_LINEAGE records
        try:
            completed_cache_records = (
                StellarAccountSearchCache.objects
                .filter(status=DONE_MAKE_PARENT_LINEAGE)
                .all()
            )
            
            for record in completed_cache_records:
                if record.created_at and record.updated_at:
                    delta = record.updated_at - record.created_at
                    minutes = delta.total_seconds() / 60
                    processing_times.append(minutes)
                    
                    # Count accounts processed in last 24h and 7d
                    if record.updated_at > now - timedelta(hours=24):
                        performance_stats['total_accounts_processed_24h'] += 1
                    if record.updated_at > now - timedelta(days=7):
                        performance_stats['total_accounts_processed_7d'] += 1
        except Exception as e:
            sentry_sdk.capture_exception(e)
        
        # LINEAGE TABLE: Fetch COMPLETE and BIGQUERY_COMPLETE records
        try:
            # Get COMPLETE status records
            completed_lineage_records = (
                StellarCreatorAccountLineage.objects
                .filter(status=COMPLETE)
                .all()
            )
            
            for record in completed_lineage_records:
                if record.created_at and record.updated_at:
                    delta = record.updated_at - record.created_at
                    minutes = delta.total_seconds() / 60
                    processing_times.append(minutes)
                    
                    # Count accounts processed in last 24h and 7d
                    if record.updated_at > now - timedelta(hours=24):
                        performance_stats['total_accounts_processed_24h'] += 1
                    if record.updated_at > now - timedelta(days=7):
                        performance_stats['total_accounts_processed_7d'] += 1
            
            # Get BIGQUERY_COMPLETE status records
            try:
                bigquery_completed_records = (
                    StellarCreatorAccountLineage.objects
                    .filter(status='BIGQUERY_COMPLETE')
                    .all()
                )
                
                for record in bigquery_completed_records:
                    if record.created_at and record.updated_at:
                        delta = record.updated_at - record.created_at
                        minutes = delta.total_seconds() / 60
                        processing_times.append(minutes)
                        
                        # Count accounts processed in last 24h and 7d
                        if record.updated_at > now - timedelta(hours=24):
                            performance_stats['total_accounts_processed_24h'] += 1
                        if record.updated_at > now - timedelta(days=7):
                            performance_stats['total_accounts_processed_7d'] += 1
            except Exception:
                pass
                
        except Exception as e:
            sentry_sdk.capture_exception(e)
        
        # Calculate aggregate stats from combined processing times
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
        if _skip_full_scans:
            cron_health['status'] = 'SKIPPED_RO'
        else:
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
        if _skip_full_scans:
            raise RuntimeError('skip stage scan in CASSANDRA_READ_ONLY')
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
    
    # Initial dependency heartbeat (SSR); page also polls /api/heartbeat/
    heartbeat = {
        'status': 'unknown',
        'checked_at': None,
        'duration_ms': 0,
        'summary': {'ok': 0, 'warn': 0, 'fail': 0, 'skipped': 0},
        'internal': [],
        'external': [],
        'light_mode': False,
        'env': 'development',
    }
    try:
        from apiApp.helpers.sm_heartbeat import run_heartbeat

        # SSR: internal only (fast; no multi-second external HTTP on page render).
        # Full internal+external probes run via GET /api/heartbeat/ (JS auto-refresh).
        heartbeat = run_heartbeat(include_external=False)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        heartbeat['status'] = 'unhealthy'
        heartbeat['error'] = str(e)[:160]

    context = {
        'db_stats': db_stats,
        'performance_stats': performance_stats,
        'bigquery_stats': bigquery_stats,
        'cron_health': cron_health,
        'stage_health': stage_health,
        'bigquery_config': bigquery_config,
        'api_health': api_health,
        'heartbeat': heartbeat,
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
    # Cap list length for SSR (page stays usable; leaderboard is top-N by definition)
    HVA_DISPLAY_LIMIT = 150
    # Rank-change enrichment is N partition lookups — only top rows
    HVA_RANK_ENRICH_LIMIT = 25 if getattr(settings, 'CASSANDRA_READ_ONLY', False) else 50

    try:
        admin_threshold = HVARankingHelper.get_hva_threshold()
        # Prefer is_hva filter (indexed path / smaller set). Full network scan is too
        # expensive on Cassandra (multi-second–minute). For thresholds below admin
        # default we still start from is_hva and only fall back to a capped scan
        # when not in read-only lab mode.
        records = []
        try:
            qs = StellarCreatorAccountLineage.objects.filter(
                is_hva=True,
                network_name=network_name,
            )
            records = list(qs)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            records = []

        if (
            not records
            and selected_threshold < admin_threshold
            and not getattr(settings, 'CASSANDRA_READ_ONLY', False)
        ):
            # Dev/SQL only: broader filter when is_hva empty and lower threshold
            try:
                records = list(
                    StellarCreatorAccountLineage.objects.filter(network_name=network_name)
                )
            except Exception as e:
                sentry_sdk.capture_exception(e)
                records = []

        hva_records = [
            rec for rec in records
            if rec.xlm_balance and rec.xlm_balance >= selected_threshold
        ]

        sorted_records = sorted(
            hva_records,
            key=lambda x: x.xlm_balance if x.xlm_balance else 0,
            reverse=True,
        )[:HVA_DISPLAY_LIMIT]

        cutoff_time = timezone.now() - timedelta(hours=24)

        for rank, record in enumerate(sorted_records, start=1):
            tags_list = [tag.strip() for tag in record.tags.split(',')] if record.tags else []

            rank_change = 0
            event_type = None
            previous_rank = None
            balance_change_pct = 0.0

            if rank <= HVA_RANK_ENRICH_LIMIT:
                try:
                    all_changes = list(
                        HVAStandingChange.objects.filter(
                            stellar_account=record.stellar_account
                        )
                    )
                    threshold_changes = [
                        c for c in all_changes
                        if (
                            hasattr(c, 'xlm_threshold')
                            and abs((c.xlm_threshold or 0) - selected_threshold) < 1.0
                            and c.network_name == network_name
                        )
                    ]
                    if threshold_changes:
                        recent_change = sorted(
                            threshold_changes,
                            key=lambda x: x.created_at or timezone.now(),
                            reverse=True,
                        )[0]
                        if recent_change.created_at and recent_change.created_at >= cutoff_time:
                            rank_change = recent_change.rank_change or 0
                            event_type = recent_change.event_type
                            previous_rank = recent_change.old_rank
                            balance_change_pct = recent_change.balance_change_pct or 0.0
                except Exception:
                    pass

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
        'hva_display_limit': HVA_DISPLAY_LIMIT,
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
