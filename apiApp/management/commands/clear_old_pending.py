"""
Management command to clear old PENDING accounts from the queue.
Useful for removing the backlog of old accounts that can't be processed via BigQuery.
"""
from django.core.management.base import BaseCommand
from datetime import datetime, timezone, timedelta
from apiApp.model_loader import StellarCreatorAccountLineage
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clear old PENDING accounts (>2 years) that exceed BigQuery limits'

    def add_arguments(self, parser):
        parser.add_argument(
            '--age-days',
            type=int,
            default=730,
            help='Clear accounts older than this many days (default: 730 = 2 years)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=1000,
            help='Maximum number of accounts to process per run (default: 1000)'
        )

    def handle(self, *args, **options):
        age_days = options['age_days']
        dry_run = options['dry_run']
        limit = options['limit']
        
        self.stdout.write(self.style.WARNING(
            f'╔══════════════════════════════════════════════════════════════╗'
        ))
        self.stdout.write(self.style.WARNING(
            f'║  Clear Old PENDING Accounts Tool                            ║'
        ))
        self.stdout.write(self.style.WARNING(
            f'╚══════════════════════════════════════════════════════════════╝'
        ))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('🔍 DRY RUN MODE - No accounts will be deleted'))
        else:
            self.stdout.write(self.style.ERROR('⚠️  LIVE MODE - Accounts will be permanently deleted'))
        
        self.stdout.write(f'   Age threshold: >{age_days} days old')
        self.stdout.write(f'   Batch limit: {limit} accounts')
        self.stdout.write('')
        
        try:
            # Get PENDING accounts
            pending_accounts = StellarCreatorAccountLineage.objects.filter(
                status='PENDING',
                network_name='public'
            ).limit(limit * 2)  # Get extra to filter by age
            
            # We need to filter by age manually since Cassandra doesn't support created_at filtering well
            # For efficiency, we'll just count and delete in batches
            
            self.stdout.write(f'📊 Analyzing PENDING accounts...')
            
            deleted_count = 0
            kept_count = 0
            error_count = 0
            
            for account in pending_accounts:
                try:
                    # Check if we've hit the limit
                    if deleted_count >= limit:
                        self.stdout.write(self.style.WARNING(
                            f'\n⚠️  Reached batch limit of {limit} deletions - stopping'
                        ))
                        break
                    
                    # For old accounts without created_at, we'll use a heuristic:
                    # If status=PENDING and created_at is None or very old, likely stuck
                    should_delete = False
                    
                    if hasattr(account, 'created_at') and account.created_at:
                        account_age = (datetime.now(timezone.utc) - account.created_at).days
                        if account_age > age_days:
                            should_delete = True
                    else:
                        # No created_at timestamp - likely very old, delete it
                        should_delete = True
                    
                    if should_delete:
                        if not dry_run:
                            account.delete()
                        deleted_count += 1
                        
                        if deleted_count % 100 == 0:
                            self.stdout.write(f'   Processed: {deleted_count} deleted, {kept_count} kept')
                    else:
                        kept_count += 1
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f'Error processing account {account.stellar_account}: {e}')
                    continue
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('═' * 64))
            self.stdout.write(self.style.SUCCESS('  SUMMARY'))
            self.stdout.write(self.style.SUCCESS('═' * 64))
            
            if dry_run:
                self.stdout.write(self.style.WARNING(f'  🔍 Would delete: {deleted_count} old PENDING accounts'))
                self.stdout.write(self.style.SUCCESS(f'  ✓ Would keep: {kept_count} recent accounts'))
            else:
                self.stdout.write(self.style.ERROR(f'  🗑️  Deleted: {deleted_count} old PENDING accounts'))
                self.stdout.write(self.style.SUCCESS(f'  ✓ Kept: {kept_count} recent accounts'))
            
            if error_count > 0:
                self.stdout.write(self.style.ERROR(f'  ✗ Errors: {error_count}'))
            
            self.stdout.write(self.style.SUCCESS('═' * 64))
            self.stdout.write('')
            
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    '💡 Run without --dry-run to actually delete these accounts'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    '✓ Cleanup complete! Old PENDING accounts removed.'
                ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))
            logger.error(f'Error in clear_old_pending command: {e}')
            raise
