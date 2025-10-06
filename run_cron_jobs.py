#!/usr/bin/env python
import os
import sys
import time
import subprocess
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StellarMapWeb.settings')

def run_command(command):
    """Run a Django management command."""
    try:
        result = subprocess.run(
            ['python', 'manage.py'] + command.split(),
            capture_output=True,
            text=True,
            timeout=300
        )
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = "SUCCESS" if result.returncode == 0 else "FAILED"
        print(f"[{timestamp}] {command}: {status} (returncode={result.returncode})")
        if result.returncode != 0:
            stderr_preview = result.stderr[:300] if result.stderr else "(no stderr)"
            print(f"  Error: {stderr_preview}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {command}: TIMEOUT")
        return False
    except Exception as e:
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
