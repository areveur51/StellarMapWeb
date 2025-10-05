# apiApp/management/commands/recreate_user_inquiry_table.py
from django.core.management.base import BaseCommand
from cassandra.cqlengine.management import drop_table, sync_table
from apiApp.models import UserInquirySearchHistory


class Command(BaseCommand):
    help = 'Drop and recreate UserInquirySearchHistory table with new schema'

    def handle(self, *args, **options):
        try:
            drop_table(UserInquirySearchHistory)
            self.stdout.write(self.style.SUCCESS('✓ Dropped existing table'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'No existing table to drop: {e}'))

        try:
            sync_table(UserInquirySearchHistory)
            self.stdout.write(self.style.SUCCESS('✓ Created table with new schema (cached_json, last_fetched_at)'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed to create table: {e}'))
            raise

        self.stdout.write(self.style.SUCCESS('\n✓ UserInquirySearchHistory table recreated successfully!'))
