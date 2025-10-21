"""
Management command to recalculate HVA rankings and create initial change events.

This command:
1. Gets all current HVA accounts
2. Calculates their rankings
3. Creates ENTERED events for accounts in the top 1000
4. Useful for backfilling initial data or recalculating after data migrations

Usage:
    python manage.py recalculate_hva_rankings
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apiApp.helpers.hva_ranking import HVARankingHelper
from apiApp.model_loader import StellarCreatorAccountLineage, HVAStandingChange
from uuid import uuid1
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Recalculate HVA rankings and create initial standing change events'

    def add_arguments(self, parser):
        parser.add_argument(
            '--network',
            type=str,
            default='public',
            help='Network to recalculate (public or testnet)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving to database'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear all existing HVA standing changes before recalculating'
        )

    def handle(self, *args, **options):
        network = options['network']
        dry_run = options['dry_run']
        clear_existing = options['clear_existing']
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*60}\nRecalculating HVA Rankings\n{'='*60}"
        ))
        self.stdout.write(f"Network: {network}")
        self.stdout.write(f"Dry Run: {dry_run}")
        
        # Clear existing records if requested
        if clear_existing and not dry_run:
            self.stdout.write(self.style.WARNING("\nClearing existing HVA standing changes..."))
            try:
                # Note: Cassandra doesn't support DELETE without WHERE clause
                # We'd need to iterate and delete individually
                # For now, just warn the user
                self.stdout.write(self.style.WARNING(
                    "⚠️  Clearing all records requires manual intervention in Cassandra"
                ))
                self.stdout.write(self.style.WARNING(
                    "    Run: TRUNCATE TABLE hva_standing_changes;"
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error clearing records: {e}"))
                return
        
        # Get current rankings
        self.stdout.write("\nFetching current HVA rankings...")
        rankings = HVARankingHelper.get_current_rankings(
            network_name=network,
            limit=1000
        )
        
        if not rankings:
            self.stdout.write(self.style.WARNING("No HVA accounts found"))
            return
        
        self.stdout.write(self.style.SUCCESS(
            f"Found {len(rankings)} HVA accounts"
        ))
        
        # Create initial ENTERED events for top 1000
        self.stdout.write(f"\nCreating initial ENTERED events...")
        
        created_count = 0
        error_count = 0
        
        for rank, account in rankings:
            try:
                if dry_run:
                    self.stdout.write(
                        f"  [DRY RUN] Would create ENTERED event for "
                        f"{account.stellar_account[:8]}... at rank #{rank}"
                    )
                else:
                    # Check if account already has a change event
                    existing = HVAStandingChange.objects.filter(
                        stellar_account=account.stellar_account
                    ).first()
                    
                    if existing:
                        self.stdout.write(
                            f"  ⊘ Skipping {account.stellar_account[:8]}... "
                            f"(already has change event)"
                        )
                        continue
                    
                    # Create ENTERED event
                    # Use timezone-aware datetime for SQLite, uuid1() for Cassandra compatibility
                    from apiApp.model_loader import USE_CASSANDRA
                    change_time_val = uuid1() if USE_CASSANDRA else timezone.now()
                    
                    HVAStandingChange.create(
                        stellar_account=account.stellar_account,
                        change_time=change_time_val,
                        event_type='ENTERED',
                        old_rank=None,
                        new_rank=rank,
                        old_balance=0.0,
                        new_balance=account.xlm_balance or 0.0,
                        network_name=network,
                        home_domain=account.home_domain or ''
                    )
                    
                    created_count += 1
                    
                    if created_count % 100 == 0:
                        self.stdout.write(
                            f"  ✓ Created {created_count} events..."
                        )
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error creating event for {account.stellar_account}: {e}")
                self.stdout.write(self.style.ERROR(
                    f"  ✗ Error for {account.stellar_account[:8]}...: {e}"
                ))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*60}\nSummary\n{'='*60}"
        ))
        self.stdout.write(f"Total HVA accounts: {len(rankings)}")
        self.stdout.write(f"Events created: {created_count}")
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {error_count}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n⚠️  This was a DRY RUN - no changes were saved"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n✓ HVA ranking recalculation complete!"
            ))
