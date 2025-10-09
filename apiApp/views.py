# apiApp/views.py
from django.http import HttpResponse, JsonResponse
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


def pending_accounts_api(request):
    """
    API endpoint that returns pending accounts data as JSON.
    Simplified to show only PENDING and PROCESSING statuses.
    
    Returns:
        JsonResponse: List of pending/processing accounts with stuck indicators.
    """
    pending_accounts_data = []
    try:
        from apiApp.models import (
            StellarCreatorAccountLineage,
            PENDING,
            PROCESSING,
            STUCK_THRESHOLD_MINUTES,
        )
        from datetime import datetime
        
        def convert_timestamp(ts):
            if ts is None:
                return None
            if isinstance(ts, datetime):
                return ts.isoformat()
            return str(ts)
        
        def calculate_age_minutes(updated_at):
            if not updated_at:
                return 0
            age_delta = datetime.utcnow() - updated_at
            return int(age_delta.total_seconds() / 60)
        
        # Fetch PENDING and PROCESSING records only
        try:
            records = StellarCreatorAccountLineage.objects.filter(status__in=[PENDING, PROCESSING]).all()
            for record in records:
                age_mins = calculate_age_minutes(record.updated_at)
                pending_accounts_data.append({
                    'stellar_account': record.stellar_account,
                    'network_name': record.network_name,
                    'status': record.status,
                    'created_at': convert_timestamp(record.created_at),
                    'updated_at': convert_timestamp(record.updated_at),
                    'age_minutes': age_mins,
                    'is_stuck': age_mins >= STUCK_THRESHOLD_MINUTES,
                    'retry_count': record.retry_count if record.retry_count else 0,
                })
        except Exception as e:
            sentry_sdk.capture_exception(e)
                
    except Exception as e:
        sentry_sdk.capture_exception(e)
    
    return JsonResponse(pending_accounts_data, safe=False)


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
        from apiApp.models import StellarAccountStageExecution
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
        # Order by created_at DESC and stage_number to show latest executions first
        records = StellarAccountStageExecution.objects.filter(
            stellar_account=account,
            network_name=network
        ).limit(100)
        
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
        from apiApp.models import StellarCreatorAccountLineage
        from apiApp.helpers.sm_bigquery import StellarBigQueryHelper
        from datetime import datetime
        import json
        import logging
        
        logger = logging.getLogger(__name__)
        
        # INSTANT SEARCH: Query BigQuery directly first (only for accounts <1 year old)
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
                                    status='PENDING',
                                    created_at=datetime.utcnow(),
                                    updated_at=datetime.utcnow()
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
                        existing = StellarCreatorAccountLineage.objects.filter(
                            stellar_account=account,
                            network_name=network
                        ).first()
                        
                        if not existing:
                            StellarCreatorAccountLineage.objects.create(
                                stellar_account=account,
                                network_name=network,
                                status='PENDING',
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow()
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
        for account_addr in all_records:
            try:
                child_records = StellarCreatorAccountLineage.objects.filter(
                    stellar_creator_account=account_addr,
                    network_name=network
                ).all()
                
                for child in child_records:
                    if child.stellar_account in all_records:
                        all_records[account_addr]['children'].append(all_records[child.stellar_account])
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
                record['hierarchy_level'] = level
                result.append(record)
                if record['children']:
                    result.extend(flatten_with_hierarchy(record['children'], level + 1))
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
        from apiApp.models import StellarCreatorAccountLineage, FAILED, RE_INQUIRY
        from datetime import datetime
        
        # Find the FAILED record
        try:
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
            record.updated_at = datetime.utcnow()
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