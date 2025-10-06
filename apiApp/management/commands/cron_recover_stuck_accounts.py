# apiApp/management/commands/cron_recover_stuck_accounts.py
"""
Django management command to detect and recover stuck pipeline records.

Usage:
    # Detect only (dry-run):
    python manage.py cron_recover_stuck_accounts --dry-run
    
    # Auto-fix stuck records:
    python manage.py cron_recover_stuck_accounts
    
    # Verbose output:
    python manage.py cron_recover_stuck_accounts --verbose
"""
from django.core.management.base import BaseCommand
from apiApp.helpers.stuck_records import recover_stuck_records
import json


class Command(BaseCommand):
    help = 'Detect and recover stuck pipeline records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Detect stuck records without fixing them',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each stuck record',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        verbose = options.get('verbose', False)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"{'[DRY RUN] ' if dry_run else ''}Scanning for stuck pipeline records..."
            )
        )
        
        # Run recovery
        stats = recover_stuck_records(auto_fix=not dry_run)
        
        # Display summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Stuck Record Recovery Summary ==="))
        self.stdout.write(f"Detected: {stats['detected']} stuck records")
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Reset: {stats['reset']} records"))
            self.stdout.write(self.style.WARNING(f"Failed: {stats['failed']} records marked as FAILED"))
            if stats['errors'] > 0:
                self.stdout.write(self.style.ERROR(f"Errors: {stats['errors']} recovery attempts failed"))
        
        # Display details if verbose or if there are stuck records
        if verbose or (stats['detected'] > 0 and not dry_run):
            self.stdout.write("")
            self.stdout.write("=== Details ===")
            for detail in stats['details']:
                status_color = self.style.WARNING if detail['age_minutes'] > detail['threshold_minutes'] * 2 else self.style.NOTICE
                
                self.stdout.write("")
                self.stdout.write(f"Account: {detail['stellar_account']}")
                self.stdout.write(f"Network: {detail['network_name']}")
                self.stdout.write(status_color(f"Status: {detail['status']}"))
                self.stdout.write(f"Age: {detail['age_minutes']} minutes (threshold: {detail['threshold_minutes']} min)")
                self.stdout.write(f"Retry Count: {detail['retry_count']}")
                if not dry_run:
                    action_msg = detail.get('action', 'unknown')
                    if action_msg == 'reset_to_pending':
                        self.stdout.write(self.style.SUCCESS(f"Action: ✓ Reset to PENDING"))
                    elif action_msg == 'marked_failed':
                        self.stdout.write(self.style.WARNING(f"Action: ⚠ Marked as FAILED (max retries exceeded)"))
                    elif action_msg == 'error':
                        self.stdout.write(self.style.ERROR(f"Action: ✗ Error during reset"))
        
        self.stdout.write("")
        if stats['detected'] == 0:
            self.stdout.write(self.style.SUCCESS("✓ No stuck records found! Pipeline is healthy."))
        elif dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ Found {stats['detected']} stuck record(s). "
                    "Run without --dry-run to auto-fix."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Recovery complete. Reset {stats['reset']} record(s), "
                    f"marked {stats['failed']} as FAILED."
                )
            )
