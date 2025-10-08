#!/usr/bin/env python
"""
EDUCATIONAL/REFERENCE CODE - NOT ENABLED BY DEFAULT

This is the API-based Cron Pipeline (8-stage Horizon/Stellar Expert approach).
The BigQuery Pipeline is now the primary data collection method.

This file is retained for:
- Educational purposes
- API-based data collection demonstrations
- Reference implementation of workflow tracking

To use this pipeline: Manually create a workflow pointing to this file.
NOT recommended for production use due to API rate limits and slower processing.
"""
import os
import sys
import time
import subprocess
from datetime import datetime
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StellarMapWeb.settings')
django.setup()

from apiApp.models import StellarAccountStageExecution, StellarCreatorAccountLineage, StellarAccountSearchCache
from apiApp.helpers.sm_stage_execution import update_stage_execution

# Stage mapping: cron command -> stage number
STAGE_MAP = {
    'cron_make_parent_account_lineage': 1,
    'cron_collect_account_horizon_data': 2,
    'cron_collect_account_lineage_attributes': 3,
    'cron_collect_account_lineage_assets': 4,
    'cron_collect_account_lineage_flags': 5,
    'cron_collect_account_lineage_se_directory': 6,
    'cron_collect_account_lineage_creator': 7,
    'cron_make_grandparent_account_lineage': 8,
}

def log_stage_execution(command, status, execution_time_ms, error_message=None):
    """Log stage execution for addresses currently being processed."""
    try:
        stage_number = STAGE_MAP.get(command)
        if not stage_number:
            return
        
        # Find addresses currently being processed
        addresses_to_log = set()
        
        # Check StellarCreatorAccountLineage for addresses in progress
        try:
            lineage_records = list(StellarCreatorAccountLineage.objects.all().limit(100))
            for record in lineage_records:
                if record.stellar_account and record.network_name:
                    addresses_to_log.add((record.stellar_account, record.network_name))
        except Exception as e:
            print(f"Warning: Could not query lineage records: {e}")
        
        # Check StellarAccountSearchCache for addresses in progress
        try:
            cache_records = list(StellarAccountSearchCache.objects.all().limit(100))
            for record in cache_records:
                if record.stellar_account and record.network_name:
                    addresses_to_log.add((record.stellar_account, record.network_name))
        except Exception as e:
            print(f"Warning: Could not query cache records: {e}")
        
        # Log execution for each address (update existing or create new)
        for stellar_account, network_name in addresses_to_log:
            try:
                update_stage_execution(
                    stellar_account=stellar_account,
                    network_name=network_name,
                    stage_number=stage_number,
                    status=status,
                    execution_time_ms=execution_time_ms,
                    error_message=error_message or ''
                )
            except Exception as log_error:
                print(f"Warning: Could not log stage execution for {stellar_account}: {log_error}")
    except Exception as e:
        print(f"Warning: Stage logging failed: {e}")

def run_command(command):
    """Run a Django management command and log stage execution."""
    start_time = time.time()
    try:
        result = subprocess.run(
            ['python', 'manage.py'] + command.split(),
            capture_output=True,
            text=True,
            timeout=300
        )
        execution_time_ms = int((time.time() - start_time) * 1000)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = "SUCCESS" if result.returncode == 0 else "FAILED"
        error_message = None if result.returncode == 0 else result.stderr[:500]
        
        print(f"[{timestamp}] {command}: {status} (returncode={result.returncode})")
        if result.returncode != 0:
            stderr_preview = result.stderr[:300] if result.stderr else "(no stderr)"
            print(f"  Error: {stderr_preview}")
        
        # Log stage execution to database
        log_stage_execution(command, status, execution_time_ms, error_message)
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_stage_execution(command, "TIMEOUT", execution_time_ms, "Command timeout after 300s")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {command}: TIMEOUT")
        return False
    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_stage_execution(command, "ERROR", execution_time_ms, str(e))
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {command}: ERROR - {e}")
        return False

def run_data_collection_pipeline():
    """Run all data collection stages for one address in sequence."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting data collection pipeline...")
    
    # Auto-recover stuck records before processing (5-minute threshold)
    run_command('cron_recover_stuck_accounts')
    
    run_command('cron_make_parent_account_lineage')
    run_command('cron_collect_account_horizon_data')
    run_command('cron_collect_account_lineage_attributes')
    run_command('cron_collect_account_lineage_assets')
    run_command('cron_collect_account_lineage_flags')
    run_command('cron_collect_account_lineage_se_directory')
    run_command('cron_collect_account_lineage_creator')
    run_command('cron_make_grandparent_account_lineage')
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Data collection pipeline completed\n")

def main():
    """Run cron jobs with optimized scheduling for fast per-address processing."""
    print("=" * 60)
    print("Cron Worker Started (Option A: Fast Pipeline)")
    print("=" * 60)
    print("Strategy: Process each address FAST (all stages in ~1-2 min)")
    print("Rate limiting: Natural delay between different user searches")
    print("=" * 60)
    
    cycle_counter = 0
    
    while True:
        # Health check: Every 5 cycles (10 minutes)
        if cycle_counter % 5 == 0:
            run_command('cron_health_check')
        
        # CRITICAL: Run full data collection pipeline every cycle (2 minutes)
        # This processes ONE address through ALL stages quickly
        run_data_collection_pipeline()
        
        # Wait 2 minutes before next cycle
        # This provides natural rate limiting between processing different addresses
        cycle_counter += 1
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Waiting 2 minutes before next cycle...")
        time.sleep(120)

if __name__ == '__main__':
    main()
