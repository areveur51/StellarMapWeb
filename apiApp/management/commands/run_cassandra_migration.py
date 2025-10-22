"""
Django management command to run Cassandra migration for dual-pipeline tracking fields.
"""
from django.core.management.base import BaseCommand
from cassandra.cqlengine import connection
from django.conf import settings


class Command(BaseCommand):
    help = 'Run Cassandra migration to add dual-pipeline tracking fields'

    def handle(self, *args, **options):
        """Execute the Cassandra migration."""
        
        self.stdout.write("🔧 Running Cassandra Migration: Dual-Pipeline Tracking Fields")
        self.stdout.write("=" * 70)
        
        # Get the session from Django's Cassandra connection
        try:
            session = connection.get_session()
            keyspace = connection.get_session().keyspace
            self.stdout.write(f"✅ Connected to keyspace: {keyspace}")
        except Exception as e:
            self.stderr.write(f"❌ Failed to get Cassandra session: {e}")
            return
        
        # Get keyspace name from settings
        from django.conf import settings
        keyspace = getattr(settings, 'CASSANDRA_KEYSPACE', 'stellarmapweb')
        
        # Migration statements with fully qualified table names
        migrations = [
            {
                'name': 'pipeline_source',
                'statement': f'ALTER TABLE {keyspace}.stellar_creator_account_lineage ADD pipeline_source text'
            },
            {
                'name': 'last_pipeline_attempt',
                'statement': f'ALTER TABLE {keyspace}.stellar_creator_account_lineage ADD last_pipeline_attempt timestamp'
            },
            {
                'name': 'processing_started_at',
                'statement': f'ALTER TABLE {keyspace}.stellar_creator_account_lineage ADD processing_started_at timestamp'
            }
        ]
        
        self.stdout.write("\n📝 Executing migration statements...")
        success_count = 0
        skip_count = 0
        
        for i, migration in enumerate(migrations, 1):
            column_name = migration['name']
            statement = migration['statement']
            
            try:
                session.execute(statement)
                self.stdout.write(
                    self.style.SUCCESS(f"  ✅ [{i}/3] Added column: {column_name}")
                )
                success_count += 1
            except Exception as e:
                error_msg = str(e).lower()
                if 'already exists' in error_msg or 'duplicate' in error_msg:
                    self.stdout.write(
                        self.style.WARNING(f"  ⚠️  [{i}/3] Column '{column_name}' already exists (skipping)")
                    )
                    skip_count += 1
                else:
                    self.stderr.write(
                        self.style.ERROR(f"  ❌ [{i}/3] Failed to add '{column_name}': {e}")
                    )
                    return
        
        # Verify the schema
        self.stdout.write("\n🔍 Verifying schema changes...")
        try:
            result = session.execute(
                f"SELECT column_name FROM system_schema.columns "
                f"WHERE keyspace_name = '{keyspace}' AND table_name = 'stellar_creator_account_lineage'"
            )
            
            columns = {row.column_name for row in result}
            
            required_columns = ['pipeline_source', 'last_pipeline_attempt', 'processing_started_at']
            missing = [col for col in required_columns if col not in columns]
            
            if missing:
                self.stderr.write(self.style.ERROR(f"❌ Missing columns: {missing}"))
                return
            else:
                self.stdout.write(self.style.SUCCESS("✅ All required columns verified:"))
                for col in required_columns:
                    self.stdout.write(f"   • {col}")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️  Could not verify schema: {e}"))
        
        # Summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ MIGRATION COMPLETED SUCCESSFULLY!"))
        self.stdout.write(f"\nSummary:")
        self.stdout.write(f"  • Columns added: {success_count}")
        self.stdout.write(f"  • Already existed: {skip_count}")
        self.stdout.write(f"  • Total: {success_count + skip_count}/3")
        
        self.stdout.write("\n📋 Next Steps:")
        self.stdout.write("  1. Uncomment model fields in apiApp/models_cassandra.py (lines 148-150)")
        self.stdout.write("  2. Restart all workflows")
        self.stdout.write("  3. Verify dual-pipeline feature works")
        self.stdout.write("\n" + "=" * 70)
