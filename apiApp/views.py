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