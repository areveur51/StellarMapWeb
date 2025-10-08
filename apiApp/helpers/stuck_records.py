# apiApp/helpers/stuck_records.py
"""
Simplified helper functions for detecting and recovering stuck pipeline records.
"""
import datetime
import sentry_sdk
from typing import List, Dict, Any
from apiApp.models import (
    StellarCreatorAccountLineage,
    PENDING,
    PROCESSING,
    FAILED,
    INVALID,
    STUCK_THRESHOLD_MINUTES,
    STUCK_STATUSES,
    MAX_RETRY_ATTEMPTS,
)


def detect_stuck_records() -> List[Dict[str, Any]]:
    """
    Detect records stuck in PENDING or PROCESSING status for too long.
    
    Returns:
        List of stuck record information dictionaries
    """
    stuck_records = []
    now = datetime.datetime.utcnow()
    threshold_delta = datetime.timedelta(minutes=STUCK_THRESHOLD_MINUTES)
    cutoff_time = now - threshold_delta
    
    try:
        for status in STUCK_STATUSES:
            try:
                records = StellarCreatorAccountLineage.objects.filter(status=status).all()
                
                for record in records:
                    if record.updated_at and record.updated_at < cutoff_time:
                        age_delta = now - record.updated_at
                        age_minutes = int(age_delta.total_seconds() / 60)
                        
                        stuck_records.append({
                            'record': record,
                            'status': status,
                            'age_minutes': age_minutes,
                            'threshold_minutes': STUCK_THRESHOLD_MINUTES,
                            'stellar_account': record.stellar_account,
                            'network_name': record.network_name,
                            'retry_count': record.retry_count if record.retry_count else 0,
                        })
            except Exception as e:
                sentry_sdk.capture_exception(e)
                continue
                
    except Exception as e:
        sentry_sdk.capture_exception(e)
    
    return stuck_records


def reset_stuck_record(record, reason: str = "Auto-recovery") -> bool:
    """
    Reset a stuck record to PENDING or mark as FAILED if max retries exceeded.
    
    Args:
        record: The stuck record
        reason: Reason for the reset
    
    Returns:
        bool: True if reset successful
    """
    try:
        current_status = record.status
        current_retry_count = record.retry_count if record.retry_count else 0
        
        # Check if max retries exceeded
        if current_retry_count >= MAX_RETRY_ATTEMPTS:
            record.status = FAILED
            record.last_error = f"Exceeded {MAX_RETRY_ATTEMPTS} retry attempts. Last status: {current_status}"
            record.save()
            
            sentry_sdk.capture_message(
                f"Record marked as FAILED after {MAX_RETRY_ATTEMPTS} retries",
                level='warning',
                extras={
                    'stellar_account': record.stellar_account,
                    'network_name': record.network_name,
                }
            )
            return True
        
        # Reset to PENDING to restart processing
        record.status = PENDING
        record.retry_count = current_retry_count + 1
        record.last_error = f"{reason}: Reset from {current_status} (attempt #{record.retry_count})"
        record.save()
        
        return True
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return False


def recover_stuck_records(auto_fix: bool = True) -> Dict[str, Any]:
    """
    Detect and optionally recover all stuck records.
    
    Args:
        auto_fix: If True, automatically reset stuck records
    
    Returns:
        Dictionary with recovery statistics
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
            success = reset_stuck_record(record)
            
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
