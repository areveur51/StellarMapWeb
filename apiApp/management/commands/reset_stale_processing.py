"""
Django management command to reset stale processing accounts.

Usage:
    python manage.py reset_stale_processing --minutes 30 --network public
    python manage.py reset_stale_processing --minutes 60 --dry-run
"""
import datetime
from django.core.management.base import BaseCommand
from apiApp.model_loader import StellarAccountSearchCache, StellarCreatorAccountLineage


class Command(BaseCommand):
    help = 'Reset stale processing accounts (stuck in PROCESSING status for too long)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=30,
            help='Age threshold in minutes (default: 30). Accounts in PROCESSING status older than this will be reset.'
        )
        parser.add_argument(
            '--network',
            type=str,
            default='public',
            choices=['public', 'testnet'],
            help='Network to check (default: public)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without actually resetting'
        )

    def handle(self, *args, **options):
        minutes = options['minutes']
        network = options['network']
        dry_run = options['dry_run']

        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(f"Resetting Stale Processing Accounts")
        self.stdout.write(f"{'='*70}")
        self.stdout.write(f"Network: {network}")
        self.stdout.write(f"Stale Threshold: {minutes} minutes")
        self.stdout.write(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        self.stdout.write(f"{'='*70}\n")

        from django.conf import settings
        USE_CASSANDRA = settings.DATABASES['default']['ENGINE'] == 'django_cassandra_engine'
        
        stale_threshold = datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes)
        
        search_cache_reset = 0
        lineage_reset = 0
        
        # Reset stale accounts in Search Cache
        self.stdout.write("\n[1/2] Checking Search Cache table...")
        
        if USE_CASSANDRA:
            # Scan through Search Cache
            for record in StellarAccountSearchCache.objects.filter(network_name=network):
                # Case-insensitive check for 'PROCESSING' in status
                status_normalized = (record.status or '').upper()
                if 'PROCESSING' in status_normalized:
                    is_stale = record.updated_at and record.updated_at < stale_threshold
                    
                    if is_stale:
                        age_minutes = int((datetime.datetime.utcnow() - record.updated_at).total_seconds() / 60)
                        self.stdout.write(
                            self.style.WARNING(
                                f"  • {record.stellar_account[:8]}... stuck for {age_minutes} min in '{record.status}'"
                            )
                        )
                        
                        if not dry_run:
                            record.status = 'ERROR'
                            record.last_error = f'Reset from stale {record.status} (stuck for {age_minutes} minutes)'
                            record.save()
                        
                        search_cache_reset += 1
        else:
            # SQLite can filter directly
            stale_records = StellarAccountSearchCache.objects.filter(
                network_name=network,
                status__icontains='PROCESSING',
                updated_at__lt=stale_threshold
            )
            
            for record in stale_records:
                age_minutes = int((datetime.datetime.utcnow() - record.updated_at).total_seconds() / 60)
                self.stdout.write(
                    self.style.WARNING(
                        f"  • {record.stellar_account[:8]}... stuck for {age_minutes} min in '{record.status}'"
                    )
                )
                
                if not dry_run:
                    record.status = 'ERROR'
                    record.last_error = f'Reset from stale {record.status} (stuck for {age_minutes} minutes)'
                    record.save()
                
                search_cache_reset += 1
        
        # Reset stale accounts in Account Lineage
        self.stdout.write("\n[2/2] Checking Account Lineage table...")
        
        if USE_CASSANDRA:
            # Scan through Account Lineage
            for record in StellarCreatorAccountLineage.objects.filter(network_name=network):
                # Case-insensitive check for 'PROCESSING' in status
                status_normalized = (record.status or '').upper()
                if 'PROCESSING' in status_normalized:
                    # Use processing_started_at if available, otherwise fall back to updated_at
                    is_stale = False
                    age_minutes = 0
                    
                    if hasattr(record, 'processing_started_at') and record.processing_started_at:
                        is_stale = record.processing_started_at < stale_threshold
                        age_minutes = int((datetime.datetime.utcnow() - record.processing_started_at).total_seconds() / 60)
                    elif record.updated_at:
                        is_stale = record.updated_at < stale_threshold
                        age_minutes = int((datetime.datetime.utcnow() - record.updated_at).total_seconds() / 60)
                    
                    if is_stale:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  • {record.stellar_account[:8]}... stuck for {age_minutes} min in '{record.status}'"
                            )
                        )
                        
                        if not dry_run:
                            record.status = 'ERROR'
                            record.last_error = f'Reset from stale processing (stuck for {age_minutes} minutes)'
                            if hasattr(record, 'processing_started_at'):
                                record.processing_started_at = None
                            record.save()
                        
                        lineage_reset += 1
        else:
            # SQLite can filter directly
            from django.db.models import Q
            
            # Check both processing_started_at and updated_at
            stale_records = StellarCreatorAccountLineage.objects.filter(
                network_name=network,
                status__icontains='PROCESSING'
            ).filter(
                Q(processing_started_at__lt=stale_threshold) | 
                Q(updated_at__lt=stale_threshold)
            )
            
            for record in stale_records:
                if hasattr(record, 'processing_started_at') and record.processing_started_at:
                    age_minutes = int((datetime.datetime.utcnow() - record.processing_started_at).total_seconds() / 60)
                else:
                    age_minutes = int((datetime.datetime.utcnow() - record.updated_at).total_seconds() / 60)
                
                self.stdout.write(
                    self.style.WARNING(
                        f"  • {record.stellar_account[:8]}... stuck for {age_minutes} min in '{record.status}'"
                    )
                )
                
                if not dry_run:
                    record.status = 'ERROR'
                    record.last_error = f'Reset from stale processing (stuck for {age_minutes} minutes)'
                    if hasattr(record, 'processing_started_at'):
                        record.processing_started_at = None
                    record.save()
                
                lineage_reset += 1
        
        # Summary
        total_reset = search_cache_reset + lineage_reset
        
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(f"Summary")
        self.stdout.write(f"{'='*70}")
        self.stdout.write(f"Search Cache: {search_cache_reset} accounts reset")
        self.stdout.write(f"Account Lineage: {lineage_reset} accounts reset")
        self.stdout.write(f"Total: {total_reset} accounts reset")
        
        if dry_run:
            self.stdout.write(self.style.NOTICE("\nDRY RUN - No changes were made. Run without --dry-run to apply changes."))
        else:
            if total_reset > 0:
                self.stdout.write(self.style.SUCCESS(f"\n✓ Successfully reset {total_reset} stale processing accounts"))
            else:
                self.stdout.write(self.style.SUCCESS("\n✓ No stale processing accounts found"))
        
        self.stdout.write(f"{'='*70}\n")
