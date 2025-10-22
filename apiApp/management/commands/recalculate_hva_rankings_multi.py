"""
Management command to recalculate HVA rankings for ALL thresholds.

This command:
1. Clears existing ranking history for all thresholds
2. Recalculates rankings for 10K, 50K, 100K, 500K, 750K, and 1M XLM thresholds
3. Backfills HVAStandingChange events for all qualifying accounts

Usage:
    python manage.py recalculate_hva_rankings_multi --network public
    python manage.py recalculate_hva_rankings_multi --network testnet --dry-run
    python manage.py recalculate_hva_rankings_multi --thresholds 10000 100000 1000000
"""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from uuid import uuid1
from apiApp.model_loader import StellarCreatorAccountLineage, HVAStandingChange, USE_CASSANDRA
from apiApp.helpers.hva_ranking import HVARankingHelper

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Recalculate HVA rankings for multiple thresholds and backfill ranking history'

    def add_arguments(self, parser):
        parser.add_argument(
            '--network',
            type=str,
            default='public',
            help='Network name (public or testnet)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--clear-history',
            action='store_true',
            help='Clear existing ranking history before recalculating'
        )
        parser.add_argument(
            '--thresholds',
            nargs='+',
            type=int,
            default=None,
            help='Specific thresholds to calculate (default: all supported)'
        )

    def handle(self, *args, **options):
        network_name = options['network']
        dry_run = options['dry_run']
        clear_history = options['clear_history']
        custom_thresholds = options['thresholds']
        
        # Use custom thresholds or default to all supported
        thresholds = custom_thresholds if custom_thresholds else HVARankingHelper.get_supported_thresholds()
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*60}\n"
            f"Recalculating HVA Rankings for Multiple Thresholds\n"
            f"{'='*60}\n"
            f"Network: {network_name}\n"
            f"Thresholds: {', '.join([f'{t:,} XLM' for t in thresholds])}\n"
            f"Dry Run: {dry_run}\n"
            f"Clear History: {clear_history}\n"
            f"{'='*60}\n"
        ))
        
        # Step 1: Clear existing history if requested
        if clear_history and not dry_run:
            self.stdout.write("Clearing existing ranking history...")
            try:
                deleted_count = HVAStandingChange.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"✓ Cleared {deleted_count} ranking events"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠ Could not clear history: {e}"))
        
        # Step 2: Calculate rankings for each threshold
        total_events = 0
        
        for threshold in thresholds:
            self.stdout.write(f"\n{'-'*60}")
            self.stdout.write(self.style.SUCCESS(f"Processing Threshold: {threshold:,} XLM"))
            self.stdout.write(f"{'-'*60}")
            
            # Get rankings for this threshold
            rankings = HVARankingHelper.get_current_rankings(
                network_name=network_name,
                xlm_threshold=threshold,
                limit=1000
            )
            
            self.stdout.write(f"Found {len(rankings)} accounts qualifying for {threshold:,} XLM threshold")
            
            if dry_run:
                # Show sample accounts
                for rank, account in rankings[:10]:
                    self.stdout.write(
                        f"  #{rank:3d} | {account.stellar_account[:8]}... | "
                        f"{account.xlm_balance:>15,.2f} XLM"
                    )
                if len(rankings) > 10:
                    self.stdout.write(f"  ... and {len(rankings) - 10} more accounts")
                continue
            
            # Record ENTERED events for all qualifying accounts
            threshold_events = 0
            for rank, account in rankings:
                try:
                    # Create ENTERED event for this threshold
                    change_time_val = uuid1() if USE_CASSANDRA else timezone.now()
                    
                    HVAStandingChange.create(
                        stellar_account=account.stellar_account,
                        change_time=change_time_val,
                        event_type='ENTERED',
                        old_rank=None,
                        new_rank=rank,
                        old_balance=0.0,
                        new_balance=account.xlm_balance or 0.0,
                        network_name=network_name,
                        home_domain=account.home_domain or '',
                        xlm_threshold=threshold
                    )
                    threshold_events += 1
                    
                    if threshold_events % 50 == 0:
                        self.stdout.write(f"  Processed {threshold_events}/{len(rankings)} accounts...")
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"  ✗ Error recording event for {account.stellar_account}: {e}"
                    ))
            
            total_events += threshold_events
            self.stdout.write(self.style.SUCCESS(
                f"✓ Recorded {threshold_events} ENTERED events for {threshold:,} XLM threshold"
            ))
        
        # Summary
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS(
            f"✅ Recalculation Complete!\n"
            f"  Total Events Created: {total_events}\n"
            f"  Thresholds Processed: {len(thresholds)}\n"
            f"  Network: {network_name}\n"
        ))
        self.stdout.write(f"{'='*60}\n")
