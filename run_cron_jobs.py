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
        print(f"[{timestamp}] {command}: {status}")
        if result.returncode != 0:
            print(f"  Error: {result.stderr[:200]}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {command}: TIMEOUT")
        return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {command}: ERROR - {e}")
        return False

def main():
    """Run cron jobs on schedule."""
    print("=" * 60)
    print("Cron Worker Started")
    print("=" * 60)
    
    minute_counter = 0
    
    while True:
        current_minute = int(time.strftime('%M'))
        
        # Health check: Every 5 min
        if minute_counter % 5 == 0:
            run_command('cron_health_check')
        
        # Parent lineage: Every 5 min (prioritizes PENDING over RE_INQUIRY)
        if current_minute % 5 == 0:
            run_command('cron_make_parent_account_lineage')
        
        # Horizon data: Every 10 min, offset 1
        if current_minute % 10 == 1:
            run_command('cron_collect_account_horizon_data')
        
        # Attributes: Every 5 min, offset 2
        if current_minute % 5 == 2:
            run_command('cron_collect_account_lineage_attributes')
        
        # Assets: Every 5 min, offset 3
        if current_minute % 5 == 3:
            run_command('cron_collect_account_lineage_assets')
        
        # Flags: Every 5 min, offset 4
        if current_minute % 5 == 4:
            run_command('cron_collect_account_lineage_flags')
        
        # SE directory: Every 5 min, offset 0
        if current_minute % 5 == 0:
            run_command('cron_collect_account_lineage_se_directory')
        
        # Creator: Every 5 min, offset 1
        if current_minute % 5 == 1:
            run_command('cron_collect_account_lineage_creator')
        
        # Grandparent: Every 10 min, offset 2
        if current_minute % 10 == 2:
            run_command('cron_make_grandparent_account_lineage')
        
        # Wait 1 minute before next check
        minute_counter += 1
        time.sleep(60)

if __name__ == '__main__':
    main()
