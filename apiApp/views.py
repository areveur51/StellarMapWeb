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


def pending_accounts_api(request):
    """
    API endpoint that returns pending accounts data as JSON.
    Used for auto-refresh in Vue.js frontend.
    
    Returns:
        JsonResponse: List of pending accounts with stuck indicators.
    """
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
                return datetime.fromtimestamp(ts).isoformat()
            return str(ts)
        
        def calculate_age_minutes(updated_at):
            if not updated_at:
                return 0
            if isinstance(updated_at, str):
                try:
                    updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                except:
                    return 0
            age_delta = datetime.utcnow() - updated_at
            return int(age_delta.total_seconds() / 60)
        
        def is_record_stuck(status, age_minutes):
            threshold = STUCK_THRESHOLDS.get(status, float('inf'))
            return age_minutes >= threshold
        
        # Fetch from StellarAccountSearchCache
        cache_statuses = [PENDING_MAKE_PARENT_LINEAGE, IN_PROGRESS_MAKE_PARENT_LINEAGE, RE_INQUIRY]
        for status in cache_statuses:
            try:
                records = StellarAccountSearchCache.objects.filter(status=status).all()
                for record in records:
                    age_mins = calculate_age_minutes(record.updated_at)
                    pending_accounts_data.append({
                        'table': 'StellarAccountSearchCache',
                        'stellar_account': record.stellar_account,
                        'network_name': record.network_name,
                        'status': record.status,
                        'created_at': convert_timestamp(record.created_at),
                        'updated_at': convert_timestamp(record.updated_at),
                        'last_fetched_at': convert_timestamp(record.last_fetched_at),
                        'age_minutes': age_mins,
                        'is_stuck': is_record_stuck(record.status, age_mins),
                        'retry_count': getattr(record, 'retry_count', 0),
                    })
            except Exception as e:
                sentry_sdk.capture_exception(e)
                continue
        
        # Fetch from StellarCreatorAccountLineage
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
        for status in lineage_statuses:
            try:
                records = StellarCreatorAccountLineage.objects.filter(status=status).all()
                for record in records:
                    age_mins = calculate_age_minutes(record.updated_at)
                    pending_accounts_data.append({
                        'table': 'StellarCreatorAccountLineage',
                        'stellar_account': record.stellar_account,
                        'network_name': record.network_name,
                        'status': record.status,
                        'created_at': convert_timestamp(record.created_at),
                        'updated_at': convert_timestamp(record.updated_at),
                        'last_fetched_at': None,
                        'age_minutes': age_mins,
                        'is_stuck': is_record_stuck(record.status, age_mins),
                        'retry_count': getattr(record, 'retry_count', 0),
                    })
            except Exception as e:
                sentry_sdk.capture_exception(e)
                continue
                
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