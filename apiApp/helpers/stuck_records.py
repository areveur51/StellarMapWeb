# apiApp/helpers/stuck_records.py
"""
Helper functions for detecting and recovering stuck pipeline records.

A record is considered "stuck" when its updated_at timestamp hasn't changed
for longer than the configured threshold for its current status.
"""
import datetime
import sentry_sdk
from typing import List, Dict, Any
from apiApp.models import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    STUCK_THRESHOLDS,
    MAX_RETRY_ATTEMPTS,
    FAILED,
    PENDING_HORIZON_API_DATASETS,
    PENDING_MAKE_PARENT_LINEAGE,
)


def detect_stuck_records() -> List[Dict[str, Any]]:
    """
    Detect records that are stuck in their current status.
    
    A record is stuck if:
    1. It's in a PENDING or IN_PROGRESS status
    2. Its updated_at timestamp exceeds the threshold for that status
    
    Returns:
        List of dictionaries containing stuck record information with fields:
        - table: Source table name
        - record: The stuck record object
        - status: Current status
        - age_minutes: How long it's been stuck (in minutes)
        - threshold_minutes: Configured threshold for this status
    """
    stuck_records = []
    now = datetime.datetime.utcnow()
    
    # Define which statuses belong to which table
    cache_statuses = ['PENDING_MAKE_PARENT_LINEAGE', 'IN_PROGRESS_MAKE_PARENT_LINEAGE', 'RE_INQUIRY']
    
    try:
        # Check each status defined in thresholds
        for status, threshold_minutes in STUCK_THRESHOLDS.items():
            threshold_delta = datetime.timedelta(minutes=threshold_minutes)
            cutoff_time = now - threshold_delta
            
            # Check StellarAccountSearchCache for cache-related statuses
            if status in cache_statuses:
                try:
                    records = StellarAccountSearchCache.objects.filter(status=status).all()
                    
                    for record in records:
                        if record.updated_at and record.updated_at < cutoff_time:
                            age_delta = now - record.updated_at
                            age_minutes = int(age_delta.total_seconds() / 60)
                            
                            stuck_records.append({
                                'table': 'StellarAccountSearchCache',
                                'record': record,
                                'status': status,
                                'age_minutes': age_minutes,
                                'threshold_minutes': threshold_minutes,
                                'stellar_account': record.stellar_account,
                                'network_name': record.network_name,
                                'retry_count': record.retry_count if (hasattr(record, 'retry_count') and record.retry_count is not None) else 0,
                            })
                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    continue
            
            # Check StellarCreatorAccountLineage for all statuses
            try:
                records = StellarCreatorAccountLineage.objects.filter(status=status).all()
                
                for record in records:
                    if record.updated_at and record.updated_at < cutoff_time:
                        age_delta = now - record.updated_at
                        age_minutes = int(age_delta.total_seconds() / 60)
                        
                        stuck_records.append({
                            'table': 'StellarCreatorAccountLineage',
                            'record': record,
                            'status': status,
                            'age_minutes': age_minutes,
                            'threshold_minutes': threshold_minutes,
                            'stellar_account': record.stellar_account,
                            'network_name': record.network_name,
                            'retry_count': record.retry_count if (hasattr(record, 'retry_count') and record.retry_count is not None) else 0,
                        })
            except Exception as e:
                sentry_sdk.capture_exception(e)
                continue
                
    except Exception as e:
        sentry_sdk.capture_exception(e)
    
    return stuck_records


def reset_stuck_record(record, reason: str = "Auto-recovery") -> bool:
    """
    Reset a stuck record to retry processing.
    
    Strategy:
    1. If retry_count < MAX_RETRY_ATTEMPTS: Reset to appropriate PENDING status
    2. If retry_count >= MAX_RETRY_ATTEMPTS: Mark as FAILED
    
    Args:
        record: The stuck record (StellarAccountSearchCache or StellarCreatorAccountLineage)
        reason: Reason for the reset (for logging)
    
    Returns:
        bool: True if reset was successful, False otherwise
    """
    try:
        current_status = record.status
        current_retry_count = record.retry_count if (hasattr(record, 'retry_count') and record.retry_count is not None) else 0
        table_name = record.__class__.__name__
        
        # Determine correct PENDING status based on table
        if isinstance(record, StellarAccountSearchCache):
            pending_status = PENDING_MAKE_PARENT_LINEAGE
        else:
            pending_status = PENDING_HORIZON_API_DATASETS
        
        # Check if we've exceeded retry limit
        if current_retry_count >= MAX_RETRY_ATTEMPTS:
            # Mark as FAILED
            record.status = FAILED
            record.last_error = f"Exceeded {MAX_RETRY_ATTEMPTS} retry attempts. Last status: {current_status}"
            record.save()
            
            sentry_sdk.capture_message(
                f"{table_name} record marked as FAILED after {MAX_RETRY_ATTEMPTS} retries",
                level='warning',
                extras={
                    'table': table_name,
                    'stellar_account': record.stellar_account,
                    'network_name': record.network_name,
                    'final_status': current_status,
                    'retry_count': current_retry_count,
                }
            )
            return True
        
        # Reset to PENDING to restart processing
        record.status = pending_status
        record.retry_count = current_retry_count + 1
        record.last_error = f"{reason}: Reset from {current_status} (attempt #{record.retry_count})"
        record.save()
        
        sentry_sdk.capture_message(
            f"{table_name} stuck record reset: {record.stellar_account}",
            level='info',
            extras={
                'table': table_name,
                'stellar_account': record.stellar_account,
                'network_name': record.network_name,
                'previous_status': current_status,
                'new_status': pending_status,
                'retry_count': record.retry_count,
                'reason': reason,
            }
        )
        
        return True
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return False


def recover_stuck_records(auto_fix: bool = True) -> Dict[str, Any]:
    """
    Detect and optionally recover all stuck records.
    
    Args:
        auto_fix: If True, automatically reset stuck records. If False, only detect.
    
    Returns:
        Dictionary with recovery statistics:
        - detected: Number of stuck records found
        - reset: Number of records successfully reset
        - failed: Number of records marked as FAILED
        - errors: Number of errors encountered
        - details: List of stuck record details
    """
    stuck_records = detect_stuck_records()
    
    stats = {
        'detected': len(stuck_records),
        'reset': 0,
        'failed': 0,
        'errors': 0,
        'details': []
    }
    
    for stuck_info in stuck_records:
        record_detail = {
            'stellar_account': stuck_info['stellar_account'],
            'network_name': stuck_info['network_name'],
            'status': stuck_info['status'],
            'age_minutes': stuck_info['age_minutes'],
            'threshold_minutes': stuck_info['threshold_minutes'],
            'retry_count': stuck_info['retry_count'],
        }
        
        if auto_fix:
            record = stuck_info['record']
            success = reset_stuck_record(record, reason="Automated stuck record recovery")
            
            if success:
                if record.status == FAILED:
                    stats['failed'] += 1
                    record_detail['action'] = 'marked_failed'
                else:
                    stats['reset'] += 1
                    record_detail['action'] = 'reset_to_pending'
            else:
                stats['errors'] += 1
                record_detail['action'] = 'error'
        else:
            record_detail['action'] = 'detected_only'
        
        stats['details'].append(record_detail)
    
    return stats
