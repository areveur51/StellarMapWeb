# apiApp/views.py
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit
import sentry_sdk

def api_home(request):
    """Simple API home view"""
    return JsonResponse({
        'message': 'StellarMapWeb API is working!',
        'status': 'success',
        'version': '1.0'
    })


def health_check(request):
    """
    Health check endpoint for load balancers and monitoring.
    Returns 200 OK if the service is healthy.
    """
    return JsonResponse({
        'status': 'healthy',
        'service': 'stellarmapweb',
        'version': '1.0'
    }, status=200)


# Simple in-memory cache for pending accounts (10 second TTL)
_pending_accounts_cache = {'data': None, 'timestamp': None, 'ttl': 10}

def pending_accounts_api(request):
    """
    API endpoint that returns pending accounts data as JSON.
    Optimized with caching and result limiting to prevent 2MB+ responses.
    
    Performance optimizations:
    - 10-second cache to reduce database load
    - Limit to 100 most recent records
    - Minimal payload (no timestamps, only essential fields)
    
    Returns:
        JsonResponse: Dict with pending accounts list and metadata.
    """
    from datetime import datetime, timedelta
    
    # Check cache first
    cache = _pending_accounts_cache
    if cache['data'] and cache['timestamp']:
        age_seconds = (datetime.utcnow() - cache['timestamp']).total_seconds()
        if age_seconds < cache['ttl']:
            # Mark response as cached before returning
            cached_response = cache['data'].copy()
            cached_response['cached'] = True
            return JsonResponse(cached_response, safe=False)
    
    pending_accounts_data = []
    total_count = 0
    
    try:
        from apiApp.model_loader import (
            StellarCreatorAccountLineage,
            PENDING,
            PROCESSING,
            STUCK_THRESHOLD_MINUTES,
            USE_CASSANDRA,
        )
        
        def calculate_age_minutes(updated_at):
            if not updated_at:
                return 0
            age_delta = datetime.utcnow() - updated_at
            return int(age_delta.total_seconds() / 60)
        
        # Fetch records with optimization
        if USE_CASSANDRA:
            # Cassandra: Collect all pending/processing, then sort by updated_at and limit to 100
            all_pending = []
            total_count = 0
            for record in StellarCreatorAccountLineage.objects.all():
                if record.status in [PENDING, PROCESSING]:
                    all_pending.append(record)
                    total_count += 1
            
            # Sort by updated_at descending (most recent first) and limit to 100
            records = sorted(all_pending, key=lambda r: r.updated_at or datetime.min, reverse=True)[:100]
        else:
            # SQLite: Use efficient filtering with ordering
            all_records = StellarCreatorAccountLineage.objects.filter(status__in=[PENDING, PROCESSING])
            total_count = all_records.count()
            records = list(all_records.order_by('-updated_at')[:100])
        
        # Build minimal response (no timestamps to reduce payload size)
        for record in records:
            age_mins = calculate_age_minutes(record.updated_at)
            pending_accounts_data.append({
                'stellar_account': record.stellar_account,
                'network_name': record.network_name,
                'status': record.status,
                'age_minutes': age_mins,
                'is_stuck': age_mins >= STUCK_THRESHOLD_MINUTES,
                'retry_count': record.retry_count if record.retry_count else 0,
            })
        
        # Build response with metadata
        response_data = {
            'accounts': pending_accounts_data,
            'count': len(pending_accounts_data),
            'total_pending': total_count,
            'cached': False,
            'cache_ttl': cache['ttl']
        }
        
        # Update cache
        cache['data'] = response_data
        cache['timestamp'] = datetime.utcnow()
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        response_data = {
            'accounts': [],
            'count': 0,
            'total_pending': 0,
            'error': str(e),
            'cached': False
        }
    
    return JsonResponse(response_data, safe=False)


def stage_executions_api(request):
    """
    API endpoint that returns stage execution history for a specific address.
    Used for real-time pipeline monitoring in the Stages tab.
    
    Query Parameters:
        account (str): Stellar account address (required)
        network (str): Network name (required, 'public' or 'testnet')
    
    Returns:
        JsonResponse: List of stage executions ordered by stage number and time.
    """
    account = request.GET.get('account', '').strip()
    network = request.GET.get('network', '').strip()
    
    # Validate required parameters
    if not account or not network:
        return JsonResponse({
            'error': 'Missing required parameters',
            'message': 'Both account and network parameters are required'
        }, status=400)
    
    # Validate address format (basic check)
    from apiApp.helpers.sm_validator import StellarMapValidatorHelpers
    if not StellarMapValidatorHelpers.validate_stellar_account_address(account):
        return JsonResponse({
            'error': 'Invalid stellar account address',
            'message': 'Account must be a valid Stellar address'
        }, status=400)
    
    # Validate network
    if network not in ['public', 'testnet']:
        return JsonResponse({
            'error': 'Invalid network',
            'message': 'Network must be either public or testnet'
        }, status=400)
    
    stage_executions_data = []
    try:
        from apiApp.model_loader import StellarAccountStageExecution, USE_CASSANDRA
        from datetime import datetime
        
        def convert_timestamp(ts):
            if ts is None:
                return None
            if isinstance(ts, datetime):
                return ts.isoformat()
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts).isoformat()
            return str(ts)
        
        # Fetch stage executions for the specific address and network
        if USE_CASSANDRA:
            # Cassandra query - partition key (stellar_account, network_name) allows direct filtering
            records = StellarAccountStageExecution.objects.filter(
                stellar_account=account,
                network_name=network
            ).limit(100)
        else:
            # SQL query - can use order_by
            records = StellarAccountStageExecution.objects.filter(
                stellar_account=account,
                network_name=network
            ).order_by('-created_at')[:100]
        
        # Convert to list and sort by stage_number and created_at (latest first)
        records_list = list(records)
        records_list.sort(key=lambda x: (x.stage_number, x.created_at), reverse=True)
        
        # Group by stage_number and get only the most recent execution for each stage
        stage_latest = {}
        for record in records_list:
            if record.stage_number not in stage_latest:
                stage_latest[record.stage_number] = record
        
        # Convert to response format, sorted by stage number
        for stage_num in sorted(stage_latest.keys()):
            record = stage_latest[stage_num]
            stage_executions_data.append({
                'stage_number': record.stage_number,
                'cron_name': record.cron_name,
                'status': record.status,
                'execution_time_ms': record.execution_time_ms,
                'execution_time_seconds': round(record.execution_time_ms / 1000, 2) if record.execution_time_ms else 0,
                'error_message': record.error_message or '',
                'created_at': convert_timestamp(record.created_at),
                'updated_at': convert_timestamp(record.updated_at),
            })
                
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)
    
    return JsonResponse({
        'account': account,
        'network': network,
        'stages': stage_executions_data,
        'total_stages': len(stage_executions_data)
    }, safe=False)


def account_lineage_api(request):
    """
    API endpoint that returns account lineage data for a specific address.
    Used for real-time lineage table updates in the Account Lineage tab.
    
    NEW INSTANT SEARCH FLOW:
    1. Query BigQuery directly for immediate results
    2. Display results instantly to user
    3. Queue account for background processing to persist in database
    
    Returns hierarchical lineage from newest to oldest, with child accounts 
    nested under their parent issuers.
    
    Query Parameters:
        account (str): Stellar account address (required)
        network (str): Network name (required, 'public' or 'testnet')
    
    Returns:
        JsonResponse: Hierarchical list of lineage records ordered newest to oldest.
    """
    account = request.GET.get('account', '').strip()
    network = request.GET.get('network', '').strip()
    
    # Validate required parameters
    if not account or not network:
        return JsonResponse({
            'error': 'Missing required parameters',
            'message': 'Both account and network parameters are required'
        }, status=400)
    
    # Validate address format (basic check)
    from apiApp.helpers.sm_validator import StellarMapValidatorHelpers
    if not StellarMapValidatorHelpers.validate_stellar_account_address(account):
        return JsonResponse({
            'error': 'Invalid stellar account address',
            'message': 'Account must be a valid Stellar address'
        }, status=400)
    
    # Validate network
    if network not in ['public', 'testnet']:
        return JsonResponse({
            'error': 'Invalid network',
            'message': 'Network must be either public or testnet'
        }, status=400)
    
    try:
        from apiApp.model_loader import StellarCreatorAccountLineage, USE_CASSANDRA
        from apiApp.helpers.sm_bigquery import StellarBigQueryHelper
        from datetime import datetime
        import json
        import logging
        
        logger = logging.getLogger(__name__)
        
        # INSTANT SEARCH: Query BigQuery directly first (only for accounts <1 year old)
        # In development mode, BigQuery is typically not available, so skip to database
        from django.conf import settings
        env_value = getattr(settings, 'ENV', 'development')
        if env_value in ['production', 'replit']:
            bigquery_helper = StellarBigQueryHelper()
            if bigquery_helper.is_available():
                try:
                    # Check account age first - only use BigQuery for accounts <1 year old
                    from stellar_sdk import Server
                    from datetime import timedelta

                    horizon_server = Server(horizon_url="https://horizon.stellar.org")
                    try:
                        # Get account creation date from first transaction
                        transactions = horizon_server.transactions().for_account(account).order(desc=False).limit(1).call()

                        account_created_at_str = None
                        if transactions and '_embedded' in transactions and 'records' in transactions['_embedded']:
                            records = transactions['_embedded']['records']
                            if records:
                                account_created_at_str = records[0].get('created_at')

                        if account_created_at_str:
                            account_created_at = datetime.fromisoformat(account_created_at_str.replace('Z', '+00:00'))
                            account_age = datetime.now(account_created_at.tzinfo) - account_created_at

                            if account_age > timedelta(days=365):
                                logger.info(f"Account {account} is {account_age.days} days old (>1 year) - checking for existing data")
                                # Check if lineage data already exists in database
                                if USE_CASSANDRA:
                                    # Cassandra query
                                    existing = list(StellarCreatorAccountLineage.objects.filter(
                                        stellar_account=account,
                                        network_name=network
                                    ).limit(1))
                                    existing = existing[0] if existing else None
                                else:
                                    # SQL query
                                    existing = StellarCreatorAccountLineage.objects.filter(
                                        stellar_account=account,
                                        network_name=network
                                    ).first()

                                if existing and existing.status == 'BIGQUERY_COMPLETE':
                                    # Data exists - skip BigQuery and use database directly
                                    logger.info(f"Found existing complete lineage data for {account} - skipping BigQuery, using database")
                                    raise Exception("Skip_BigQuery_Use_Database")  # Jump to database fallback
                                elif not existing:
                                    # No data exists - queue for batch pipeline
                                    StellarCreatorAccountLineage.objects.create(
                                        stellar_account=account,
                                        network_name=network,
                                        status='PENDING'
                                    )
                                    logger.info(f"Queued {account} for batch pipeline processing")
                                    # Return message to user
                                    return JsonResponse({
                                        'account': account,
                                        'network': network,
                                        'lineage': [],
                                        'total_records': 0,
                                        'source': 'queued_for_batch',
                                        'message': f'Account is {account_age.days} days old. Queued for batch pipeline processing. Check back in a few minutes.'
                                    }, safe=False)
                                else:
                                    # Data exists but not complete - skip BigQuery and use database to show current status
                                    logger.info(f"Found incomplete lineage data for {account} (status: {existing.status}) - skipping BigQuery, using database")
                                    raise Exception("Skip_BigQuery_Use_Database")  # Jump to database fallback
                            else:
                                logger.info(f"Account {account} is {account_age.days} days old (<1 year) - proceeding with BigQuery instant query")
                        else:
                            logger.warning(f"Could not determine account age for {account} - continuing with BigQuery")
                    except Exception as horizon_error:
                        if str(horizon_error) == "Skip_BigQuery_Use_Database":
                            # This is intentional - skip to database fallback
                            raise
                        logger.warning(f"Failed to get account age from Horizon: {horizon_error}")
                        # Continue with BigQuery if we can't determine age

                    logger.info(f"Querying BigQuery directly for instant lineage of {account}")
                    instant_lineage = bigquery_helper.get_instant_lineage(account)

                    if instant_lineage['account']:
                        # Format minimal BigQuery lineage data for display
                        # NOTE: BigQuery now only provides lineage structure (parent-child relationships and dates)
                        # Assets, balance, home_domain, flags will be fetched from Horizon/Stellar Expert APIs
                        hierarchical_lineage = []

                        # Add creator if exists
                        if instant_lineage['creator']:
                            # Prefer account_creation_date (creator's actual creation), fallback to created_at
                            creator_created_at = instant_lineage['creator'].get('account_creation_date') or instant_lineage['creator'].get('created_at')

                            creator_record = {
                                'stellar_account': instant_lineage['creator']['creator_account'],
                                'stellar_creator_account': None,
                                'network_name': network,
                                'stellar_account_created_at': creator_created_at,
                                'home_domain': '',  # TODO: Fetch from Horizon/Stellar Expert
                                'xlm_balance': 0,  # TODO: Fetch from Horizon/Stellar Expert
                                'assets': [],  # TODO: Fetch from Stellar Expert
                                'status': 'BIGQUERY_LIVE',
                                'created_at': None,
                                'updated_at': None,
                                'children': [],
                                'hierarchy_level': 0
                            }
                            hierarchical_lineage.append(creator_record)

                        # Add searched account
                        creator_address = instant_lineage['creator']['creator_account'] if instant_lineage['creator'] else None
                        account_record = {
                            'stellar_account': account,
                            'stellar_creator_account': creator_address,
                            'network_name': network,
                            'stellar_account_created_at': instant_lineage['account'].get('account_creation_date'),
                            'home_domain': '',  # TODO: Fetch from Horizon/Stellar Expert
                            'xlm_balance': 0,  # TODO: Fetch from Horizon/Stellar Expert
                            'assets': [],  # TODO: Fetch from Stellar Expert
                            'status': 'BIGQUERY_LIVE',
                            'created_at': None,
                            'updated_at': None,
                            'children': [],
                            'hierarchy_level': 1 if instant_lineage['creator'] else 0
                        }
                        hierarchical_lineage.append(account_record)

                        # Queue account for background processing
                        try:
                            if USE_CASSANDRA:
                                # Cassandra query
                                existing_list = list(StellarCreatorAccountLineage.objects.filter(
                                    stellar_account=account,
                                    network_name=network
                                ).limit(1))
                                existing = existing_list[0] if existing_list else None
                            else:
                                # SQL query
                                existing = StellarCreatorAccountLineage.objects.filter(
                                    stellar_account=account,
                                    network_name=network
                                ).first()

                            if not existing:
                                StellarCreatorAccountLineage.objects.create(
                                    stellar_account=account,
                                    network_name=network,
                                    status='PENDING'
                                )
                                logger.info(f"Queued {account} for background processing")
                        except Exception as queue_error:
                            logger.warning(f"Failed to queue account for background processing: {queue_error}")

                        return JsonResponse({
                            'account': account,
                            'network': network,
                            'lineage': hierarchical_lineage,
                            'total_records': len(hierarchical_lineage),
                            'source': 'bigquery_instant'
                        }, safe=False)

                except Exception as bq_error:
                    logger.warning(f"BigQuery instant query failed, falling back to database: {bq_error}")
        else:
            logger.info(f"Development mode (ENV={env_value}): Skipping BigQuery, using database directly")
        
        # FALLBACK: Query database if BigQuery fails or unavailable
        
        def convert_timestamp(ts):
            if ts is None:
                return None
            if isinstance(ts, datetime):
                return ts.isoformat()
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts).isoformat()
            return str(ts)
        
        # First, collect all lineage records in the chain
        all_records = {}
        visited_accounts = set()
        accounts_to_process = [account]
        
        while accounts_to_process:
            current_account = accounts_to_process.pop(0)
            if current_account in visited_accounts:
                continue
            visited_accounts.add(current_account)
            
            # Fetch lineage record for current account
            if USE_CASSANDRA:
                # Cassandra query
                lineage_records = list(StellarCreatorAccountLineage.objects.filter(
                    stellar_account=current_account,
                    network_name=network
                ))
            else:
                # SQL query
                lineage_records = list(StellarCreatorAccountLineage.objects.filter(
                    stellar_account=current_account,
                    network_name=network
                ))
            
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
                    'stellar_account_created_at': convert_timestamp(record.stellar_account_created_at),
                    'home_domain': record.home_domain,
                    'xlm_balance': record.xlm_balance,
                    'assets': assets,
                    'status': record.status,
                    'created_at': convert_timestamp(record.created_at),
                    'updated_at': convert_timestamp(record.updated_at),
                    'children': []
                }
                all_records[record.stellar_account] = record_data
                
                # Follow the creator chain upward
                if record.stellar_creator_account and record.stellar_creator_account not in visited_accounts:
                    if record.stellar_creator_account not in accounts_to_process:
                        accounts_to_process.append(record.stellar_creator_account)
        
        # Now fetch all child accounts for each record to build hierarchy
        # Use a separate structure to avoid circular references
        hierarchy_links = {}
        for account_addr in all_records:
            hierarchy_links[account_addr] = []

        for account_addr in all_records:
            try:
                if USE_CASSANDRA:
                    # Cassandra query - cannot filter by stellar_creator_account (not in primary key)
                    # Must fetch all and filter in Python
                    all_lineage = StellarCreatorAccountLineage.objects.all()
                    child_records = [r for r in all_lineage if r.stellar_creator_account == account_addr and r.network_name == network]
                else:
                    # SQL query
                    child_records = list(StellarCreatorAccountLineage.objects.filter(
                        stellar_creator_account=account_addr,
                        network_name=network
                    ))

                for child in child_records:
                    if child.stellar_account in all_records:
                        hierarchy_links[account_addr].append(child.stellar_account)
            except Exception:
                pass
        
        # Build hierarchical structure starting from root (oldest ancestor)
        def find_root_accounts():
            roots = []
            for acc_addr, rec in all_records.items():
                if not rec['stellar_creator_account'] or rec['stellar_creator_account'] not in all_records:
                    roots.append(rec)
            return roots
        
        # Sort children by creation date (newest first) recursively
        def sort_children_recursive(record):
            if record['children']:
                record['children'].sort(
                    key=lambda x: x.get('stellar_account_created_at') or '', 
                    reverse=True
                )
                for child in record['children']:
                    sort_children_recursive(child)
        
        root_accounts = find_root_accounts()
        
        # Sort roots by creation date (newest first)
        root_accounts.sort(
            key=lambda x: x.get('stellar_account_created_at') or '', 
            reverse=True
        )
        
        # Sort all children recursively
        for root in root_accounts:
            sort_children_recursive(root)
        
        # Flatten to hierarchical list format with indentation levels
        def flatten_with_hierarchy(records, level=0):
            result = []
            for record in records:
                # Create a copy of the record without the children array to avoid circular references
                record_copy = {k: v for k, v in record.items() if k != 'children'}
                record_copy['hierarchy_level'] = level
                result.append(record_copy)

                # Add children recursively
                if record['stellar_account'] in hierarchy_links:
                    child_accounts = hierarchy_links[record['stellar_account']]
                    child_records = [all_records[child_addr] for child_addr in child_accounts if child_addr in all_records]
                    if child_records:
                        result.extend(flatten_with_hierarchy(child_records, level + 1))
            return result
        
        hierarchical_lineage = flatten_with_hierarchy(root_accounts)
                        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)
    
    return JsonResponse({
        'account': account,
        'network': network,
        'lineage': hierarchical_lineage,
        'total_records': len(hierarchical_lineage)
    }, safe=False)


def fetch_toml_api(request):
    """
    API endpoint to fetch stellar.toml files server-side (bypasses CORS).
    
    Query Parameters:
        domain (str): The home domain to fetch TOML from.
    
    Returns:
        JsonResponse: TOML content or error message.
    """
    import requests
    import re
    import socket
    import ipaddress
    
    domain = request.GET.get('domain', '').strip()
    
    # Validate domain parameter
    if not domain:
        return JsonResponse({
            'error': 'Missing domain parameter'
        }, status=400)
    
    # Basic domain validation (alphanumeric, dots, hyphens)
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]*[a-zA-Z0-9]$', domain):
        return JsonResponse({
            'error': 'Invalid domain format'
        }, status=400)
    
    # Prevent private/localhost domains by name
    if domain.lower() in ['localhost', '127.0.0.1', '0.0.0.0']:
        return JsonResponse({
            'error': 'Cannot fetch from private/localhost domains'
        }, status=400)
    
    # Resolve domain to IP and validate it's not private/internal
    validated_ip = None
    try:
        ip_addresses = socket.getaddrinfo(domain, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for ip_info in ip_addresses:
            ip_str = ip_info[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                
                # Reject loopback (127.0.0.0/8, ::1)
                if ip_obj.is_loopback:
                    return JsonResponse({
                        'error': f'Cannot fetch from loopback address: {ip_str}'
                    }, status=400)
                
                # Reject private addresses (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)
                if ip_obj.is_private:
                    return JsonResponse({
                        'error': f'Cannot fetch from private address: {ip_str}'
                    }, status=400)
                
                # Reject link-local (169.254.0.0/16, fe80::/10)
                if ip_obj.is_link_local:
                    return JsonResponse({
                        'error': f'Cannot fetch from link-local address: {ip_str}'
                    }, status=400)
                
                # Reject reserved addresses
                if ip_obj.is_reserved:
                    return JsonResponse({
                        'error': f'Cannot fetch from reserved address: {ip_str}'
                    }, status=400)
                
                # Reject unspecified addresses (0.0.0.0, ::)
                if ip_obj.is_unspecified:
                    return JsonResponse({
                        'error': f'Cannot fetch from unspecified address: {ip_str}'
                    }, status=400)
                
                # Reject multicast addresses
                if ip_obj.is_multicast:
                    return JsonResponse({
                        'error': f'Cannot fetch from multicast address: {ip_str}'
                    }, status=400)
                
                # Use the first valid public IP
                validated_ip = ip_str
                break
                    
            except ValueError:
                # Skip invalid IP addresses
                continue
                
    except socket.gaierror:
        return JsonResponse({
            'error': f'Cannot resolve domain: {domain}'
        }, status=400)
    
    if not validated_ip:
        return JsonResponse({
            'error': f'No valid public IP found for domain: {domain}'
        }, status=400)
    
    # Use domain URL (validated IP stored but domain needed for SNI/HTTPS)
    # DNS rebinding risk is minimized by the pre-validation and short timeout
    toml_url = f'https://{domain}/.well-known/stellar.toml'
    
    try:
        # Fetch TOML with timeout (IP already validated above)
        headers = {
            'User-Agent': 'StellarMapWeb/1.0'
        }
        response = requests.get(toml_url, headers=headers, timeout=10, allow_redirects=False)
        response.raise_for_status()
        
        return JsonResponse({
            'domain': domain,
            'url': toml_url,
            'content': response.text,
            'status': 'success'
        })
        
    except requests.exceptions.Timeout:
        return JsonResponse({
            'error': f'Request timeout while fetching TOML from {toml_url}'
        }, status=504)
        
    except requests.exceptions.RequestException as e:
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': f'Failed to fetch TOML from {toml_url}',
            'message': str(e)
        }, status=502)
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)


def retry_failed_account_api(request):
    """
    API endpoint to retry a failed account by changing its status from FAILED to RE_INQUIRY.
    
    Query Parameters:
        account (str): Stellar account address
        network (str): Network name (public or testnet)
    
    Returns:
        JsonResponse: Success or error message
    """
    if request.method != 'POST':
        return JsonResponse({
            'error': 'Method not allowed. Use POST.'
        }, status=405)
    
    account = request.POST.get('account') or request.GET.get('account')
    network = request.POST.get('network') or request.GET.get('network')
    
    if not account or not network:
        return JsonResponse({
            'error': 'Missing required parameters: account and network'
        }, status=400)
    
    try:
        from apiApp.model_loader import StellarCreatorAccountLineage, FAILED, USE_CASSANDRA
        RE_INQUIRY = 'RE_INQUIRY'  # Define locally since it might not be in models
        from datetime import datetime
        
        # Find the FAILED record
        try:
            if USE_CASSANDRA:
                # Cassandra query - must fetch all and filter (status not in primary key)
                all_records = StellarCreatorAccountLineage.objects.filter(
                    stellar_account=account,
                    network_name=network
                )
                record = None
                for r in all_records:
                    if r.status == FAILED:
                        record = r
                        break
            else:
                # SQL query
                record = StellarCreatorAccountLineage.objects.filter(
                    stellar_account=account,
                    network_name=network,
                    status=FAILED
                ).first()
            
            if not record:
                return JsonResponse({
                    'error': 'No FAILED record found for this account',
                    'account': account,
                    'network': network
                }, status=404)
            
            # Update status to RE_INQUIRY to trigger retry
            record.status = RE_INQUIRY
            try:
                # Django ORM syntax
                record.save()
            except TypeError:
                # Cassandra syntax
                record.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Account queued for retry',
                'account': account,
                'network': network,
                'new_status': RE_INQUIRY
            })
            
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return JsonResponse({
                'error': 'Database error',
                'message': str(e)
            }, status=500)
            
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)


def server_logs_api(request):
    """
    API endpoint that returns the latest 1700 lines from Django Server logs.
    
    Returns:
        JsonResponse: Latest log lines as plain text
    """
    try:
        import os
        
        # Get the latest Django Server log file
        log_dir = '/tmp/logs'
        if not os.path.exists(log_dir):
            return JsonResponse({
                'error': 'Log directory not found',
                'logs': ''
            }, status=404)
        
        # Find Django Server log files
        log_files = [f for f in os.listdir(log_dir) if f.startswith('Django_Server_')]
        if not log_files:
            return JsonResponse({
                'error': 'No Django Server logs found',
                'logs': ''
            }, status=404)
        
        # Sort by modification time, get the latest
        log_files.sort(key=lambda f: os.path.getmtime(os.path.join(log_dir, f)), reverse=True)
        latest_log_file = os.path.join(log_dir, log_files[0])
        
        # Read last 1700 lines
        with open(latest_log_file, 'r') as f:
            all_lines = f.readlines()
            last_1700_lines = all_lines[-1700:]
            logs_content = ''.join(last_1700_lines)
        
        return JsonResponse({
            'logs': logs_content,
            'file': log_files[0],
            'total_lines': len(all_lines),
            'returned_lines': len(last_1700_lines)
        })
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Failed to fetch logs',
            'message': str(e),
            'logs': ''
        }, status=500)


def error_logs_api(request):
    """
    API endpoint that returns the latest 710 lines containing errors/warnings from Django Server logs.
    
    Returns:
        JsonResponse: Latest error/warning log lines as plain text
    """
    try:
        import os
        import re
        
        # Get the latest Django Server log file
        log_dir = '/tmp/logs'
        if not os.path.exists(log_dir):
            return JsonResponse({
                'error': 'Log directory not found',
                'logs': ''
            }, status=404)
        
        # Find Django Server log files
        log_files = [f for f in os.listdir(log_dir) if f.startswith('Django_Server_')]
        if not log_files:
            return JsonResponse({
                'error': 'No Django Server logs found',
                'logs': ''
            }, status=404)
        
        # Sort by modification time, get the latest
        log_files.sort(key=lambda f: os.path.getmtime(os.path.join(log_dir, f)), reverse=True)
        latest_log_file = os.path.join(log_dir, log_files[0])
        
        # Read all lines and filter for errors/warnings
        with open(latest_log_file, 'r') as f:
            all_lines = f.readlines()
            
            # Filter lines containing error/warning keywords (case-insensitive)
            error_pattern = re.compile(r'(error|warning|exception|traceback|failed|critical)', re.IGNORECASE)
            error_lines = [line for line in all_lines if error_pattern.search(line)]
            
            # Get last 710 error lines
            last_error_lines = error_lines[-710:] if len(error_lines) > 710 else error_lines
            logs_content = ''.join(last_error_lines)
        
        return JsonResponse({
            'logs': logs_content,
            'file': log_files[0],
            'total_lines': len(all_lines),
            'total_error_lines': len(error_lines),
            'returned_lines': len(last_error_lines)
        })
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Failed to fetch error logs',
            'message': str(e),
            'logs': ''
        }, status=500)

@require_http_methods(["POST"])
@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def bulk_queue_accounts_api(request):
    """
    API endpoint for bulk queueing multiple Stellar accounts for processing.
    
    Accepts a JSON payload with a list of Stellar accounts and creates PENDING records
    in the StellarCreatorAccountLineage table for each valid, unique account.
    
    POST /api/bulk-queue-accounts/
    
    Request Body:
    {
        "accounts": ["GABC...", "GDEF...", ...],
        "network": "public"
    }
    
    Response:
    {
        "queued": ["GABC..."],  # Successfully queued accounts
        "duplicates": ["GDEF..."],  # Already exist in database
        "invalid": ["GXYZ..."],  # Invalid addresses
        "total_processed": 10
    }
    
    Returns:
        JsonResponse: Summary of queued, duplicate, and invalid accounts.
    """
    try:
        import json
        import logging
        from datetime import datetime
        from apiApp.model_loader import StellarCreatorAccountLineage
        from apiApp.helpers.sm_validator import StellarMapValidatorHelpers
        import sentry_sdk
        
        logger = logging.getLogger(__name__)
        
        # Parse JSON body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON',
                'message': 'Request body must be valid JSON'
            }, status=400)
        
        # Get accounts list and network
        accounts = data.get('accounts', [])
        network = data.get('network', 'public')
        
        # Validate parameters
        if not isinstance(accounts, list):
            return JsonResponse({
                'error': 'Invalid input',
                'message': 'accounts must be an array'
            }, status=400)
        
        if network not in ['public', 'testnet']:
            return JsonResponse({
                'error': 'Invalid network',
                'message': 'network must be either public or testnet'
            }, status=400)
        
        if len(accounts) == 0:
            return JsonResponse({
                'error': 'No accounts provided',
                'message': 'Please provide at least one account'
            }, status=400)
        
        if len(accounts) > 1000:
            return JsonResponse({
                'error': 'Too many accounts',
                'message': 'Maximum 1000 accounts per request'
            }, status=400)
        
        # Process accounts
        queued = []
        duplicates = []
        invalid = []
        
        for account in accounts:
            account = account.strip()
            
            # Validate address format
            if not StellarMapValidatorHelpers.validate_stellar_account_address(account):
                invalid.append(account)
                continue
            
            # Check if already exists in database
            try:
                existing = StellarCreatorAccountLineage.objects.filter(
                    stellar_account=account,
                    network_name=network
                ).first()
                
                if existing:
                    duplicates.append(account)
                    continue
            except Exception as e:
                # If filter fails, try to create anyway
                logger.warning(f'Error checking for duplicate {account}: {e}')
            
            # Create PENDING record
            try:
                StellarCreatorAccountLineage.objects.create(
                    stellar_account=account,
                    network_name=network,
                    status='PENDING',
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                queued.append(account)
            except Exception as e:
                logger.error(f'Error creating record for {account}: {e}')
                duplicates.append(account)  # Likely a duplicate that wasn't caught by filter
        
        return JsonResponse({
            'queued': queued,
            'duplicates': duplicates,
            'invalid': invalid,
            'total_processed': len(queued) + len(duplicates) + len(invalid)
        }, status=200)
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f'Error in bulk_queue_accounts_api: {e}')
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)


@ratelimit(key='ip', rate='30/m', method='GET', block=True)
def cassandra_query_api(request):
    """
    API endpoint for executing pre-defined queries on Cassandra database.
    
    Query Parameters:
        query (str): Pre-defined query name
        limit (int): Result limit (default 100, max 500)
    
    Returns:
        JsonResponse: Query results with metadata
    """
    from apiApp.model_loader import (
        StellarAccountSearchCache,
        StellarCreatorAccountLineage,
        HVAStandingChange,
        StellarAccountStageExecution,
        USE_CASSANDRA
    )
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    try:
        query_name = request.GET.get('query', '')
        limit = min(int(request.GET.get('limit', 100)), 500)
        network = request.GET.get('network', 'public').strip()
        
        # Validate network
        if network not in ['public', 'testnet']:
            network = 'public'
        
        if not query_name:
            return JsonResponse({
                'error': 'Missing query parameter'
            }, status=400)
        
        results = []
        description = ''
        visible_columns = []
        
        # Helper function to calculate age
        def calculate_age_minutes(updated_at):
            if not updated_at:
                return None
            try:
                if isinstance(updated_at, datetime):
                    age_delta = datetime.utcnow() - updated_at
                else:
                    age_delta = datetime.utcnow() - datetime.fromtimestamp(updated_at.timestamp())
                return int(age_delta.total_seconds() / 60)
            except:
                return None
        
        # Helper function to format record
        def format_record(record, include_fields):
            data = {
                'stellar_account': getattr(record, 'stellar_account', ''),
                'network_name': getattr(record, 'network_name', 'public'),
            }
            
            if 'status' in include_fields:
                data['status'] = getattr(record, 'status', '')
            if 'xlm_balance' in include_fields:
                data['xlm_balance'] = getattr(record, 'xlm_balance', 0)
            if 'creator_account' in include_fields:
                data['creator_account'] = getattr(record, 'stellar_creator_account', '')
            if 'age_minutes' in include_fields:
                data['age_minutes'] = calculate_age_minutes(getattr(record, 'updated_at', None))
            if 'retry_count' in include_fields:
                data['retry_count'] = getattr(record, 'retry_count', 0)
            if 'updated_at' in include_fields:
                updated = getattr(record, 'updated_at', None)
                data['updated_at'] = updated.isoformat() if updated else None
            
            return data
        
        # Execute query based on query_name
        if query_name == 'stuck_accounts':
            description = 'Stuck Accounts (Processing > 60 minutes)'
            visible_columns = ['status', 'age_minutes', 'retry_count', 'updated_at']
            
            cutoff_time = datetime.utcnow() - timedelta(minutes=60)
            
            if USE_CASSANDRA:
                # Cassandra limitation: Cannot filter by updated_at/status (non-PK fields)
                # Strategy: Collect matches with early exit, then sort by updated_at DESC
                all_records = []
                count = 0
                max_scan = limit * 10  # Safety limit: scan at most 10x the result limit
                
                for record in StellarCreatorAccountLineage.objects.filter(network_name=network):
                    count += 1
                    if count > max_scan:
                        break  # Safety exit to prevent excessive scanning
                    
                    if record.updated_at and record.updated_at < cutoff_time:
                        if record.status and 'PROGRESS' in record.status:
                            all_records.append(record)
                            if len(all_records) >= limit:
                                break
                
                # Sort by updated_at descending (oldest stuck records first)
                all_records.sort(key=lambda r: r.updated_at or datetime.min)
            else:
                all_records = StellarCreatorAccountLineage.objects.filter(
                    network_name=network,
                    updated_at__lt=cutoff_time,
                    status__contains='PROGRESS'
                ).order_by('updated_at')[:limit]
            
            results = [format_record(r, visible_columns) for r in all_records]
        
        elif query_name == 'orphan_accounts':
            description = 'Orphan Accounts (Cached Without Lineage)'
            visible_columns = ['status', 'updated_at']
            
            # Find accounts in cache without lineage
            if USE_CASSANDRA:
                # Cassandra limitation: Must collect all cache, then check lineage
                # Strategy: Limit cache collection, check lineage per account
                cached_accounts = {}
                count = 0
                max_cache_scan = limit * 5  # Scan up to 5x limit for cache records
                
                for record in StellarAccountSearchCache.objects.filter(network_name=network):
                    count += 1
                    if count > max_cache_scan:
                        break
                    key = f"{record.stellar_account}_{record.network_name}"
                    cached_accounts[key] = record
                
                orphans = []
                for key, cache_record in cached_accounts.items():
                    if len(orphans) >= limit:
                        break
                    
                    account, net = key.rsplit('_', 1)
                    has_lineage = False
                    
                    # Check if lineage exists (PK filter is efficient)
                    for lineage in StellarCreatorAccountLineage.objects.filter(
                        stellar_account=account, network_name=net
                    ):
                        has_lineage = True
                        break
                    
                    if not has_lineage:
                        orphans.append(cache_record)
                
                results = [format_record(r, visible_columns) for r in orphans]
            else:
                # SQLite can use subquery
                lineage_accounts = StellarCreatorAccountLineage.objects.filter(network_name=network).values_list('stellar_account', flat=True)
                orphans = StellarAccountSearchCache.objects.filter(network_name=network).exclude(
                    stellar_account__in=lineage_accounts
                )[:limit]
                results = [format_record(r, visible_columns) for r in orphans]
        
        elif query_name == 'failed_stages':
            description = 'Failed Stage Executions'
            visible_columns = ['status', 'updated_at']
            
            if USE_CASSANDRA:
                # Cassandra limitation: status not in PK, must scan
                # Strategy: Early exit after finding limit records
                failed = []
                count = 0
                max_scan = limit * 10
                
                for record in StellarAccountStageExecution.objects.filter(network_name=network):
                    count += 1
                    if count > max_scan:
                        break
                    if record.status == 'FAILED':
                        failed.append(record)
                        if len(failed) >= limit:
                            break
            else:
                failed = StellarAccountStageExecution.objects.filter(network_name=network, status='FAILED')[:limit]
            
            results = [format_record(r, visible_columns) for r in failed]
        
        elif query_name == 'stale_records':
            description = 'Stale Records (>12 hours old)'
            visible_columns = ['status', 'age_minutes', 'updated_at']
            
            cutoff_time = datetime.utcnow() - timedelta(hours=12)
            
            if USE_CASSANDRA:
                # Cassandra limitation: updated_at not in PK
                # Strategy: Collect with early exit, sort by age
                stale = []
                count = 0
                max_scan = limit * 10
                
                for record in StellarAccountSearchCache.objects.filter(network_name=network):
                    count += 1
                    if count > max_scan:
                        break
                    if record.updated_at and record.updated_at < cutoff_time:
                        stale.append(record)
                        if len(stale) >= limit:
                            break
                
                stale.sort(key=lambda r: r.updated_at or datetime.min)
            else:
                stale = StellarAccountSearchCache.objects.filter(network_name=network, updated_at__lt=cutoff_time).order_by('updated_at')[:limit]
            
            results = [format_record(r, visible_columns) for r in stale]
        
        elif query_name == 'fresh_records':
            description = 'Fresh Records (Recently Updated)'
            visible_columns = ['status', 'age_minutes', 'updated_at']
            
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            if USE_CASSANDRA:
                # Cassandra limitation: updated_at not in PK
                # Strategy: Collect with early exit, sort by updated_at DESC
                fresh = []
                count = 0
                max_scan = limit * 10
                
                for record in StellarAccountSearchCache.objects.filter(network_name=network):
                    count += 1
                    if count > max_scan:
                        break
                    if record.updated_at and record.updated_at >= cutoff_time:
                        fresh.append(record)
                        if len(fresh) >= limit:
                            break
                
                fresh.sort(key=lambda r: r.updated_at or datetime.max, reverse=True)
            else:
                fresh = StellarAccountSearchCache.objects.filter(network_name=network, updated_at__gte=cutoff_time).order_by('-updated_at')[:limit]
            
            results = [format_record(r, visible_columns) for r in fresh]
        
        elif query_name == 'pending_accounts':
            description = 'Pending Accounts'
            visible_columns = ['status', 'age_minutes', 'retry_count', 'updated_at']
            
            if USE_CASSANDRA:
                # Cassandra limitation: status not in PK
                # Strategy: Early exit with max scan limit
                pending = []
                count = 0
                max_scan = limit * 10
                
                for record in StellarCreatorAccountLineage.objects.filter(network_name=network):
                    count += 1
                    if count > max_scan:
                        break
                    if record.status == 'PENDING':
                        pending.append(record)
                        if len(pending) >= limit:
                            break
            else:
                pending = StellarCreatorAccountLineage.objects.filter(network_name=network, status='PENDING')[:limit]
            
            results = [format_record(r, visible_columns) for r in pending]
        
        elif query_name == 'processing_accounts':
            description = 'Processing Accounts'
            visible_columns = ['status', 'age_minutes', 'retry_count', 'updated_at']
            
            if USE_CASSANDRA:
                # Cassandra limitation: status not in PK
                # Strategy: Early exit with max scan limit
                processing = []
                count = 0
                max_scan = limit * 10
                
                for record in StellarCreatorAccountLineage.objects.filter(network_name=network):
                    count += 1
                    if count > max_scan:
                        break
                    if record.status and 'PROGRESS' in record.status:
                        processing.append(record)
                        if len(processing) >= limit:
                            break
            else:
                processing = StellarCreatorAccountLineage.objects.filter(network_name=network, status__contains='PROGRESS')[:limit]
            
            results = [format_record(r, visible_columns) for r in processing]
        
        elif query_name == 'completed_accounts':
            description = 'Completed Accounts'
            visible_columns = ['status', 'creator_account', 'updated_at']
            
            if USE_CASSANDRA:
                # Cassandra limitation: status not in PK
                # Strategy: Early exit with max scan limit
                completed = []
                count = 0
                max_scan = limit * 10
                
                for record in StellarCreatorAccountLineage.objects.filter(network_name=network):
                    count += 1
                    if count > max_scan:
                        break
                    if record.status and ('COMPLETE' in record.status or 'DONE' in record.status):
                        completed.append(record)
                        if len(completed) >= limit:
                            break
            else:
                from django.db.models import Q
                completed = StellarCreatorAccountLineage.objects.filter(
                    network_name=network
                ).filter(
                    Q(status__contains='COMPLETE') | Q(status__contains='DONE')
                )[:limit]
            
            results = [format_record(r, visible_columns) for r in completed]
        
        elif query_name == 'high_value_accounts':
            description = 'High Value Accounts (>1M XLM)'
            visible_columns = ['xlm_balance', 'creator_account', 'updated_at']
            
            if USE_CASSANDRA:
                # Cassandra limitation: xlm_balance not in PK
                # Strategy: Early exit with max scan limit
                hva_list = []
                count = 0
                max_scan = limit * 10
                
                for record in StellarCreatorAccountLineage.objects.filter(network_name=network):
                    count += 1
                    if count > max_scan:
                        break
                    if record.xlm_balance and record.xlm_balance > 1000000:
                        hva_list.append(record)
                        if len(hva_list) >= limit:
                            break
                
                # Sort by balance descending
                hva_list.sort(key=lambda r: r.xlm_balance or 0, reverse=True)
            else:
                hva_list = StellarCreatorAccountLineage.objects.filter(network_name=network, xlm_balance__gt=1000000).order_by('-xlm_balance')[:limit]
            
            results = [format_record(r, visible_columns) for r in hva_list]
        
        elif query_name == 'recent_hva_changes':
            description = 'Recent HVA Standing Changes (24 hours)'
            visible_columns = ['status', 'updated_at']
            
            cutoff_time = timezone.now() - timedelta(hours=24)
            
            if USE_CASSANDRA:
                # Cassandra limitation: created_at not in PK
                # Strategy: Early exit with max scan limit
                changes = []
                count = 0
                max_scan = limit * 10
                
                for record in HVAStandingChange.objects.filter(network_name=network):
                    count += 1
                    if count > max_scan:
                        break
                    if record.created_at and record.created_at >= cutoff_time:
                        changes.append(record)
                        if len(changes) >= limit:
                            break
                
                # Sort by created_at descending
                changes.sort(key=lambda r: r.created_at or datetime.min, reverse=True)
            else:
                changes = HVAStandingChange.objects.filter(network_name=network, created_at__gte=cutoff_time).order_by('-created_at')[:limit]
            
            # Format HVA changes differently
            for change in changes:
                results.append({
                    'stellar_account': getattr(change, 'stellar_account', ''),
                    'network_name': getattr(change, 'network_name', 'public'),
                    'status': getattr(change, 'event_type', ''),
                    'updated_at': getattr(change, 'created_at', None).isoformat() if getattr(change, 'created_at', None) else None
                })
        
        elif query_name == 'custom':
            # Custom query with multiple filters (AND logic)
            table_name = request.GET.get('table', '')
            filters_json = request.GET.get('filters', '[]')
            
            try:
                import json
                filters = json.loads(filters_json)
            except:
                return JsonResponse({'error': 'Invalid filters JSON'}, status=400)
            
            if not table_name or not filters:
                return JsonResponse({'error': 'Missing table or filters'}, status=400)
            
            # Map table names to models
            table_models = {
                'lineage': StellarCreatorAccountLineage,
                'cache': StellarAccountSearchCache,
                'hva': StellarCreatorAccountLineage,  # HVAs are in lineage table with xlm_balance > 1M
                'stages': StellarAccountStageExecution,
                'hva_changes': HVAStandingChange
            }
            
            model = table_models.get(table_name)
            if not model:
                return JsonResponse({'error': 'Invalid table name'}, status=400)
            
            description = f'Custom Query on {table_name.title()}'
            visible_columns = ['status', 'creator_account', 'xlm_balance', 'age_minutes', 'retry_count', 'updated_at']
            
            # Helper to apply filter
            def matches_filter(record, filter_obj):
                column = filter_obj.get('column')
                operator = filter_obj.get('operator')
                value = filter_obj.get('value', '')
                
                if not column or not operator:
                    return True
                
                # Get field value
                field_value = getattr(record, column, None)
                if field_value is None:
                    return False
                
                # Convert to string for comparison
                field_str = str(field_value)
                
                # Apply operator
                if operator == 'equals':
                    return field_str.lower() == value.lower()
                elif operator == 'contains':
                    return value.lower() in field_str.lower()
                elif operator == 'gt':
                    try:
                        return float(field_value) > float(value)
                    except:
                        return False
                elif operator == 'lt':
                    try:
                        return float(field_value) < float(value)
                    except:
                        return False
                elif operator == 'gte':
                    try:
                        return float(field_value) >= float(value)
                    except:
                        return False
                elif operator == 'lte':
                    try:
                        return float(field_value) <= float(value)
                    except:
                        return False
                
                return False
            
            # Fetch and filter records (AND logic)
            # Cassandra limitation: Must scan, but limit with max_scan
            filtered_records = []
            count = 0
            max_scan = limit * 20  # For custom filters, allow more scanning
            
            # Start with network filter for efficiency
            for record in model.objects.filter(network_name=network):
                count += 1
                if count > max_scan:
                    break  # Safety exit to prevent excessive scanning
                
                # Apply all filters with AND logic
                matches_all = True
                for filter_obj in filters:
                    if not matches_filter(record, filter_obj):
                        matches_all = False
                        break
                
                if matches_all:
                    filtered_records.append(record)
                    if len(filtered_records) >= limit:
                        break
            
            results = [format_record(r, visible_columns) for r in filtered_records]
        
        else:
            return JsonResponse({
                'error': 'Invalid query name',
                'query': query_name
            }, status=400)
        
        return JsonResponse({
            'results': results,
            'description': description,
            'visible_columns': visible_columns,
            'count': len(results)
        }, status=200)
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f'Error in cassandra_query_api: {e}')
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)
