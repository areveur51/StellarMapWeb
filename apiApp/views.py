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
    Returns 200 OK if the service process is up (shallow).

    For full dependency heartbeat see GET /api/heartbeat/.
    """
    return JsonResponse({
        'status': 'healthy',
        'service': 'stellarmapweb',
        'version': '1.0',
        'heartbeat': '/api/heartbeat/',
    }, status=200)


def system_heartbeat_api(request):
    """
    Dependency heartbeat for System Dashboard and operators.

    Probes internal (Django, DB, cache, optional Cassandra/Redis) and
    external (Horizon, Stellar Expert, optional BigQuery) with short timeouts.

    Query params:
        external=0  — skip external HTTP probes (faster, internal only)
    """
    include_external = request.GET.get('external', '1').lower() not in (
        '0', 'false', 'no', 'off',
    )
    try:
        from apiApp.helpers.sm_heartbeat import run_heartbeat

        payload = run_heartbeat(include_external=include_external)
        # Degraded/unhealthy still return 200 so the dashboard can render details;
        # use payload['status'] for monitoring. Optional strict mode:
        status_code = 200
        if request.GET.get('strict', '').lower() in ('1', 'true', 'yes'):
            if payload.get('status') == 'unhealthy':
                status_code = 503
            elif payload.get('status') == 'degraded':
                status_code = 200
        return JsonResponse(payload, status=status_code)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return JsonResponse(
            {
                'status': 'unhealthy',
                'service': 'stellarmapweb',
                'error': str(e)[:200],
                'internal': [],
                'external': [],
                'summary': {'ok': 0, 'warn': 0, 'fail': 1, 'skipped': 0},
            },
            status=503,
        )


# In-memory cache for pending accounts (TTL follows POLL_INTERVAL_MS / LIGHT_MODE)
_pending_accounts_cache = {'data': None, 'timestamp': None, 'ttl': None}


def _pending_cache_ttl_seconds():
    from django.conf import settings
    poll_ms = int(getattr(settings, 'POLL_INTERVAL_MS', 30000) or 30000)
    # Match UI poll cadence (min 15s, max 5m)
    return max(15, min(300, poll_ms // 1000))


def _pending_accounts_limit():
    from django.conf import settings
    return max(10, int(getattr(settings, 'PENDING_ACCOUNTS_LIMIT', 100) or 100))


def pending_accounts_api(request):
    """
    API endpoint that returns pending accounts data as JSON.
    Optimized with caching and result limiting to prevent 2MB+ responses.
    
    Performance optimizations:
    - Cache TTL tied to POLL_INTERVAL_MS (LIGHT_MODE → longer)
    - Limit records via PENDING_ACCOUNTS_LIMIT (default 50 light / 100 full)
    - Minimal payload (no timestamps, only essential fields)
    
    Returns:
        JsonResponse: Dict with pending accounts list and metadata.
    """
    from datetime import datetime, timedelta
    
    cache = _pending_accounts_cache
    cache['ttl'] = _pending_cache_ttl_seconds()
    limit = _pending_accounts_limit()

    # Check cache first
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
            # Cassandra: Collect pending/processing, then sort by updated_at and limit
            all_pending = []
            total_count = 0
            for record in StellarCreatorAccountLineage.objects.all():
                if record.status in [PENDING, PROCESSING]:
                    all_pending.append(record)
                    total_count += 1
            
            records = sorted(all_pending, key=lambda r: r.updated_at or datetime.min, reverse=True)[:limit]
        else:
            # SQLite: Use efficient filtering with ordering
            all_records = StellarCreatorAccountLineage.objects.filter(status__in=[PENDING, PROCESSING])
            total_count = all_records.count()
            records = list(all_records.order_by('-updated_at')[:limit])
        
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


@ratelimit(key='ip', rate='20/m', method='GET', block=True)
def account_lineage_api(request):
    """
    Feature-frozen compatibility endpoint for account lineage table rows.

    Prefer GET /api/lineage-with-siblings/ for the live search poll path.
    This view is a thin DB-only wrap around LineageAggregateService
    (no Horizon age checks, no BigQuery instant path).

    Query Parameters:
        account (str): Stellar account address (required)
        network (str): Network name (required, 'public' or 'testnet')
    """
    from apiApp.helpers.sm_validator import StellarMapValidatorHelpers
    from apiApp.helpers.sm_lineage_aggregate import (
        AggregateOptions,
        LineageAggregateService,
    )
    from apiApp.helpers.sm_lineage_response_cache import (
        cache_key,
        get_cached,
        set_cached,
        lineage_response_ttl_seconds,
    )
    import logging

    account = request.GET.get('account', '').strip()
    network = request.GET.get('network', '').strip()

    if not account or not network:
        return JsonResponse({
            'error': 'Missing required parameters',
            'message': 'Both account and network parameters are required'
        }, status=400)

    if not StellarMapValidatorHelpers.validate_stellar_account_address(account):
        return JsonResponse({
            'error': 'Invalid stellar account address',
            'message': 'Account must be a valid Stellar address'
        }, status=400)

    if network not in ['public', 'testnet']:
        return JsonResponse({
            'error': 'Invalid network',
            'message': 'Network must be either public or testnet'
        }, status=400)

    key = cache_key(account, network, kind='lineage')
    cached, hit = get_cached(key)
    if hit and cached is not None:
        cached = dict(cached)
        meta = dict(cached.get('meta') or {})
        meta['cached'] = True
        meta['cache_ttl'] = lineage_response_ttl_seconds()
        cached['meta'] = meta
        return JsonResponse(cached, safe=False)

    try:
        options = AggregateOptions.from_settings(
            include_siblings=False,
            use_search_cache=True,
        )
        svc = LineageAggregateService()
        projection = svc.get_projection(account, network, options)
        payload = svc.to_lineage_api_response(projection)
        payload['deprecated'] = True
        payload['prefer'] = '/api/lineage-with-siblings/'
        meta = dict(projection.get('meta') or {})
        meta['cached'] = False
        meta['cache_ttl'] = lineage_response_ttl_seconds()
        meta['feature_frozen'] = True
        payload['meta'] = meta
        set_cached(key, payload)
        return JsonResponse(payload, safe=False)
    except Exception as e:
        logging.getLogger(__name__).error('Error in account_lineage_api: %s', e)
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)


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


def refresh_enrichment_api(request):
    """
    API endpoint to refresh enrichment data by setting account status to PENDING.
    This triggers the pipeline to re-fetch balance, home_domain, flags, and assets.
    
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
        from apiApp.model_loader import StellarCreatorAccountLineage, PENDING, USE_CASSANDRA
        
        # Find the account record
        try:
            if USE_CASSANDRA:
                # Cassandra query - fetch by account and network
                record = StellarCreatorAccountLineage.objects.filter(
                    stellar_account=account,
                    network_name=network
                ).first()
            else:
                # SQL query
                record = StellarCreatorAccountLineage.objects.filter(
                    stellar_account=account,
                    network_name=network
                ).first()
            
            if not record:
                return JsonResponse({
                    'error': 'No record found for this account',
                    'account': account,
                    'network': network
                }, status=404)
            
            # Update status to PENDING to trigger enrichment refresh
            record.status = PENDING
            try:
                # Django ORM syntax
                record.save()
            except TypeError:
                # Cassandra syntax
                record.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Account queued for enrichment refresh',
                'account': account,
                'network': network,
                'new_status': PENDING
            })
            
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return JsonResponse({
                'error': 'Failed to update account status',
                'message': str(e)
            }, status=500)
            
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
        USE_CASSANDRA,
        STUCK_THRESHOLD_MINUTES,
        STUCK_STATUSES
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
            if 'home_domain' in include_fields:
                data['home_domain'] = getattr(record, 'home_domain', '')
            if 'age_minutes' in include_fields:
                data['age_minutes'] = calculate_age_minutes(getattr(record, 'updated_at', None))
            if 'retry_count' in include_fields:
                data['retry_count'] = getattr(record, 'retry_count', 0)
            if 'updated_at' in include_fields:
                updated = getattr(record, 'updated_at', None)
                data['updated_at'] = updated.isoformat() if updated else None
            if 'table_source' in include_fields:
                data['table_source'] = getattr(record, '_table_source', 'Unknown')
            
            return data
        
        # Execute query based on query_name
        if query_name == 'stuck_accounts':
            description = f'Stuck Accounts (PENDING/PROCESSING > {STUCK_THRESHOLD_MINUTES} min)'
            visible_columns = ['status', 'age_minutes', 'retry_count', 'updated_at']
            
            # Use model-defined threshold (5 minutes for PENDING/PROCESSING statuses)
            cutoff_time = datetime.utcnow() - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
            
            if USE_CASSANDRA:
                # Cassandra limitation: Cannot filter by updated_at/status (non-PK fields)
                # Strategy: Collect matches with early exit on StellarAccountSearchCache
                all_records = []
                count = 0
                max_scan = limit * 10  # Safety limit: scan at most 10x the result limit
                
                for record in StellarAccountSearchCache.objects.filter(network_name=network):
                    count += 1
                    if count > max_scan:
                        break  # Safety exit to prevent excessive scanning
                    
                    # Check if stuck: status in STUCK_STATUSES and age > threshold
                    if record.updated_at and record.updated_at < cutoff_time:
                        if record.status in STUCK_STATUSES:
                            all_records.append(record)
                            if len(all_records) >= limit:
                                break
                
                # Sort by updated_at ascending (oldest stuck records first)
                all_records.sort(key=lambda r: r.updated_at or datetime.min)
            else:
                # SQLite can filter efficiently
                all_records = StellarAccountSearchCache.objects.filter(
                    network_name=network,
                    updated_at__lt=cutoff_time,
                    status__in=STUCK_STATUSES
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
            description = 'Processing Accounts (from both Search Cache & Account Lineage)'
            visible_columns = ['status', 'age_minutes', 'retry_count', 'updated_at', 'table_source']
            
            from datetime import datetime, timedelta
            stale_threshold = datetime.utcnow() - timedelta(minutes=30)  # Processing older than 30 min is stale
            
            processing = []
            
            if USE_CASSANDRA:
                # Check Search Cache table for processing accounts
                search_cache_count = 0
                search_cache_max_scan = limit * 5
                
                for record in StellarAccountSearchCache.objects.filter(network_name=network):
                    search_cache_count += 1
                    if search_cache_count > search_cache_max_scan:
                        break
                    # Case-insensitive check for 'PROCESSING' in status
                    status_normalized = (record.status or '').upper()
                    if 'PROCESSING' in status_normalized:
                        # Mark as stale if no updates for 30+ minutes
                        is_stale = record.updated_at and record.updated_at < stale_threshold
                        record._table_source = 'Search Cache' + (' [STALE]' if is_stale else '')
                        processing.append(record)
                        if len(processing) >= limit:
                            break
                
                # Check Account Lineage table for processing accounts
                if len(processing) < limit:
                    lineage_count = 0
                    lineage_max_scan = limit * 10
                    
                    for record in StellarCreatorAccountLineage.objects.filter(network_name=network):
                        lineage_count += 1
                        if lineage_count > lineage_max_scan:
                            break
                        # Case-insensitive check for 'PROCESSING' in status
                        status_normalized = (record.status or '').upper()
                        if 'PROCESSING' in status_normalized:
                            # Check if processing_started_at indicates stale processing
                            is_stale = False
                            if hasattr(record, 'processing_started_at') and record.processing_started_at:
                                is_stale = record.processing_started_at < stale_threshold
                            elif record.updated_at and record.updated_at < stale_threshold:
                                is_stale = True
                            
                            record._table_source = 'Account Lineage' + (' [STALE]' if is_stale else '')
                            processing.append(record)
                            if len(processing) >= limit:
                                break
            else:
                from django.db.models import Q
                
                # Check Search Cache
                search_cache_processing = StellarAccountSearchCache.objects.filter(
                    network_name=network,
                    status__icontains='PROCESSING'
                )[:limit]
                
                for record in search_cache_processing:
                    is_stale = record.updated_at and record.updated_at < stale_threshold
                    record._table_source = 'Search Cache' + (' [STALE]' if is_stale else '')
                    processing.append(record)
                
                # Check Account Lineage if we need more records
                if len(processing) < limit:
                    remaining = limit - len(processing)
                    lineage_processing = StellarCreatorAccountLineage.objects.filter(
                        network_name=network,
                        status__icontains='PROCESSING'
                    )[:remaining]
                    
                    for record in lineage_processing:
                        is_stale = False
                        if hasattr(record, 'processing_started_at') and record.processing_started_at:
                            is_stale = record.processing_started_at < stale_threshold
                        elif record.updated_at and record.updated_at < stale_threshold:
                            is_stale = True
                        
                        record._table_source = 'Account Lineage' + (' [STALE]' if is_stale else '')
                        processing.append(record)
            
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
            # Get configurable HVA threshold
            from apiApp.models import BigQueryPipelineConfig
            config = BigQueryPipelineConfig.objects.filter(config_id='default').first()
            hva_threshold = config.hva_threshold_xlm if config else 100000.0
            
            # Format threshold for display (e.g., 100000 -> "100K", 1000000 -> "1M")
            if hva_threshold >= 1000000:
                threshold_display = f"{hva_threshold / 1000000:.1f}M".rstrip('0').rstrip('.')
            else:
                threshold_display = f"{hva_threshold / 1000:.0f}K"
            
            description = f'High Value Accounts (>={threshold_display} XLM)'
            visible_columns = ['xlm_balance', 'creator_account', 'updated_at']
            
            if USE_CASSANDRA:
                # Cassandra limitation: is_hva/xlm_balance not in PK
                # Strategy: Use is_hva flag with higher max_scan for sparse data
                # HVAs are rare, so need deeper scan
                # WARNING: This approach may miss HVAs if dataset grows beyond max_scan
                # TODO: Implement materialized view or secondary index on is_hva for guaranteed coverage
                hva_list = []
                count = 0
                max_scan = limit * 100  # Higher multiplier for sparse HVA data
                hit_scan_limit = False
                
                for record in StellarCreatorAccountLineage.objects.filter(network_name=network):
                    count += 1
                    if count > max_scan:
                        hit_scan_limit = True
                        break
                    # Use is_hva flag (set automatically based on configurable threshold)
                    if record.is_hva:
                        hva_list.append(record)
                        if len(hva_list) >= limit:
                            break
                
                # Log warning if max_scan limit was hit (potential false negatives)
                if hit_scan_limit:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"HVA query hit max_scan limit ({max_scan}). "
                        f"Found {len(hva_list)} HVAs but may have missed others. "
                        f"Network: {network}, Limit: {limit}"
                    )
                
                # Sort by balance descending
                hva_list.sort(key=lambda r: r.xlm_balance or 0, reverse=True)
            else:
                hva_list = StellarCreatorAccountLineage.objects.filter(network_name=network, xlm_balance__gte=hva_threshold).order_by('-xlm_balance')[:limit]
            
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
            
            # Start with base visible columns
            visible_columns = ['status', 'creator_account', 'xlm_balance', 'age_minutes', 'retry_count', 'updated_at']
            
            # Dynamically add any columns being filtered to visible columns
            for filter_obj in filters:
                column = filter_obj.get('column')
                if column and column not in visible_columns:
                    # Map column names to their display equivalents
                    column_map = {
                        'stellar_creator_account': 'creator_account',
                        'home_domain': 'home_domain',
                        'xlm_balance': 'xlm_balance',
                        'status': 'status',
                        'retry_count': 'retry_count'
                    }
                    display_column = column_map.get(column, column)
                    if display_column not in visible_columns:
                        visible_columns.append(display_column)
            
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


def pipeline_stats_api(request):
    """
    API endpoint that returns triple-pipeline statistics showing BigQuery, API, and SDK processing.
    
    Returns:
        JsonResponse: Dict with pipeline processing counts and status.
    """
    try:
        from apiApp.model_loader import StellarCreatorAccountLineage, USE_CASSANDRA
        from datetime import datetime, timedelta
        
        # Initialize stats
        stats = {
            'bigquery_total': 0,
            'bigquery_with_fallback_total': 0,
            'api_total': 0,
            'sdk_total': 0,
            'pending_total': 0,
            'processing_total': 0,
            'complete_total': 0,
            'failed_total': 0,
            'last_24h': {
                'bigquery': 0,
                'bigquery_with_fallback': 0,
                'api': 0,
                'sdk': 0,
            }
        }
        
        # Calculate 24h cutoff
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        
        # Query records
        if USE_CASSANDRA:
            # Cassandra: Scan all records and aggregate
            for record in StellarCreatorAccountLineage.objects.filter(network_name='public'):
                # Count by pipeline source
                pipeline_source = getattr(record, 'pipeline_source', '')
                if pipeline_source == 'BIGQUERY':
                    stats['bigquery_total'] += 1
                elif pipeline_source == 'BIGQUERY_WITH_API_FALLBACK':
                    stats['bigquery_with_fallback_total'] += 1
                elif pipeline_source == 'API':
                    stats['api_total'] += 1
                elif pipeline_source == 'SDK':
                    stats['sdk_total'] += 1
                
                # Count by status
                status = getattr(record, 'status', '')
                if status == 'PENDING':
                    stats['pending_total'] += 1
                elif status == 'PROCESSING':
                    stats['processing_total'] += 1
                elif status in ['COMPLETE', 'BIGQUERY_COMPLETE']:
                    stats['complete_total'] += 1
                elif status == 'FAILED':
                    stats['failed_total'] += 1
                
                # Count last 24h by pipeline source
                updated_at = getattr(record, 'updated_at', None)
                if updated_at and updated_at >= cutoff_24h:
                    if pipeline_source == 'BIGQUERY':
                        stats['last_24h']['bigquery'] += 1
                    elif pipeline_source == 'BIGQUERY_WITH_API_FALLBACK':
                        stats['last_24h']['bigquery_with_fallback'] += 1
                    elif pipeline_source == 'API':
                        stats['last_24h']['api'] += 1
                    elif pipeline_source == 'SDK':
                        stats['last_24h']['sdk'] += 1
        else:
            # SQLite: Use efficient filtering
            all_records = StellarCreatorAccountLineage.objects.filter(network_name='public')
            
            # Count by pipeline source
            stats['bigquery_total'] = all_records.filter(pipeline_source='BIGQUERY').count()
            stats['bigquery_with_fallback_total'] = all_records.filter(pipeline_source='BIGQUERY_WITH_API_FALLBACK').count()
            stats['api_total'] = all_records.filter(pipeline_source='API').count()
            stats['sdk_total'] = all_records.filter(pipeline_source='SDK').count()
            
            # Count by status
            stats['pending_total'] = all_records.filter(status='PENDING').count()
            stats['processing_total'] = all_records.filter(status='PROCESSING').count()
            stats['complete_total'] = all_records.filter(status__in=['COMPLETE', 'BIGQUERY_COMPLETE']).count()
            stats['failed_total'] = all_records.filter(status='FAILED').count()
            
            # Count last 24h by pipeline source
            recent_records = all_records.filter(updated_at__gte=cutoff_24h)
            stats['last_24h']['bigquery'] = recent_records.filter(pipeline_source='BIGQUERY').count()
            stats['last_24h']['bigquery_with_fallback'] = recent_records.filter(pipeline_source='BIGQUERY_WITH_API_FALLBACK').count()
            stats['last_24h']['api'] = recent_records.filter(pipeline_source='API').count()
            stats['last_24h']['sdk'] = recent_records.filter(pipeline_source='SDK').count()
        
        # Add metadata
        stats['timestamp'] = datetime.utcnow().isoformat()
        stats['total_accounts'] = stats['bigquery_total'] + stats['bigquery_with_fallback_total'] + stats['api_total'] + stats['sdk_total']
        
        return JsonResponse(stats, status=200)
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f'Error in pipeline_stats_api: {e}')
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)


@ratelimit(key='ip', rate='30/m', method='GET', block=True)
def lineage_with_siblings_api(request):
    """
    Account lineage with siblings at each level (primary live poll API).

    Thin wrapper over LineageAggregateService (DB-only) with process-local
    response TTL/LRU cache. Additive fields: tree, meta (build_ms, cached, …).

    Query Parameters:
        account (str): Stellar account address (required)
        network (str): Network name (required, 'public' or 'testnet')
        max_siblings_per_level (int): Cap siblings per creator (default from settings)
        include_siblings (0|1): Default 1. When 0, path-only structure (PR5 progressive).
        structure_only (0|1): Alias for include_siblings=0 (faster first paint).
    """
    from apiApp.helpers.sm_validator import StellarMapValidatorHelpers
    from apiApp.helpers.sm_lineage_aggregate import (
        AggregateOptions,
        LineageAggregateService,
    )
    from apiApp.helpers.sm_lineage_response_cache import (
        cache_key,
        get_cached,
        set_cached,
        lineage_response_ttl_seconds,
    )
    from django.conf import settings
    import logging

    account = request.GET.get('account', '').strip()
    network = request.GET.get('network', '').strip()

    light = bool(getattr(settings, 'LIGHT_MODE', False))
    default_max_sib = 25 if light else 50
    try:
        max_siblings = int(request.GET.get('max_siblings_per_level', default_max_sib))
    except (TypeError, ValueError):
        max_siblings = default_max_sib
    max_siblings = max(1, min(max_siblings, 200))

    def _truthy(val, default=True):
        if val is None:
            return default
        return str(val).strip().lower() not in ('0', 'false', 'no', 'off')

    structure_only = _truthy(request.GET.get('structure_only'), default=False)
    # structure_only forces path-only; else honor include_siblings (default on)
    if structure_only:
        include_siblings = False
    else:
        include_siblings = _truthy(request.GET.get('include_siblings'), default=True)

    if not account or not network:
        return JsonResponse({
            'error': 'Missing required parameters',
            'message': 'Both account and network parameters are required'
        }, status=400)

    if not StellarMapValidatorHelpers.validate_stellar_account_address(account):
        return JsonResponse({
            'error': 'Invalid stellar account address',
            'message': 'Account must be a valid Stellar address'
        }, status=400)

    if network not in ['public', 'testnet']:
        return JsonResponse({
            'error': 'Invalid network',
            'message': 'Network must be either public or testnet'
        }, status=400)

    key = cache_key(
        account,
        network,
        kind='siblings' if include_siblings else 'structure',
        max_siblings=max_siblings if include_siblings else 0,
        include_siblings=1 if include_siblings else 0,
    )
    cached, hit = get_cached(key)
    if hit and cached is not None:
        cached = dict(cached)
        meta = dict(cached.get('meta') or {})
        meta['cached'] = True
        meta['cache_ttl'] = lineage_response_ttl_seconds()
        cached['meta'] = meta
        return JsonResponse(cached, safe=False)

    try:
        options = AggregateOptions.from_settings(
            include_siblings=include_siblings,
            max_siblings_per_level=max_siblings,
            use_search_cache=True,
        )
        svc = LineageAggregateService()
        projection = svc.get_projection(account, network, options)
        payload = svc.to_siblings_response(projection)
        meta = dict(payload.get('meta') or {})
        meta['cached'] = False
        meta['cache_ttl'] = lineage_response_ttl_seconds()
        meta['include_siblings'] = include_siblings
        meta['structure_only'] = not include_siblings
        payload['meta'] = meta
        set_cached(key, payload)
        return JsonResponse(payload, safe=False)
    except Exception as e:
        logging.getLogger(__name__).error(
            'Error in lineage_with_siblings_api: %s', e
        )
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)

