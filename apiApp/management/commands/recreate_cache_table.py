"""
Management command to drop and recreate the stellar_account_search_cache table.
"""
from django.core.management.base import BaseCommand
from cassandra.cqlengine import management
from apiApp.models import StellarAccountSearchCache
from django.conf import settings


class Command(BaseCommand):
    help = 'Drop and recreate stellar_account_search_cache table with correct schema'

    def handle(self, *args, **options):
        keyspace = settings.CASSANDRA_KEYSPACE
        
        self.stdout.write('Dropping old tables...')
        
        # Drop old table (if exists)
        try:
            management.drop_table(StellarAccountSearchCache)
            self.stdout.write(self.style.SUCCESS('✓ Dropped stellar_account_search_cache'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Note: {e}'))
        
        # Create new table with correct schema
        try:
            management.sync_table(StellarAccountSearchCache)
            self.stdout.write(self.style.SUCCESS('✓ Created stellar_account_search_cache with correct schema'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            
        self.stdout.write(self.style.SUCCESS('Done!'))
