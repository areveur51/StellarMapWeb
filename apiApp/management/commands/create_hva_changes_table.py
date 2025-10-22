"""
Management command to create the hva_standing_changes Cassandra table.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from cassandra.cqlengine import connection
from cassandra.cluster import Cluster


class Command(BaseCommand):
    help = 'Create the hva_standing_changes Cassandra table for HVA ranking event tracking'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Creating hva_standing_changes Cassandra table...'))
        
        try:
            # Get Cassandra connection using connection helper
            from apiApp.helpers.sm_conn import CassandraConnectionsHelpers
            cassandra_conn = CassandraConnectionsHelpers()
            session = cassandra_conn.session
            
            if not session:
                self.stdout.write(self.style.WARNING('⚠ Development mode detected - using SQLite (no Cassandra table created)'))
                self.stdout.write(self.style.WARNING('  Note: HVA ranking changes will use SQLite hva_standing_change table instead'))
                return
            
            # Create table with CQL
            create_table_cql = """
            CREATE TABLE IF NOT EXISTS hva_standing_changes (
                stellar_account text,
                change_time timeuuid,
                event_type text,
                old_rank int,
                new_rank int,
                old_balance float,
                new_balance float,
                network_name text,
                home_domain text,
                rank_change int,
                balance_change_pct float,
                created_at timestamp,
                PRIMARY KEY ((stellar_account), change_time)
            ) WITH CLUSTERING ORDER BY (change_time DESC)
            AND comment = 'HVA leaderboard event log - tracks rank changes, entries, exits (480x more efficient than snapshots)';
            """
            
            session.execute(create_table_cql)
            
            self.stdout.write(self.style.SUCCESS('✓ Successfully created hva_standing_changes table!'))
            self.stdout.write(self.style.SUCCESS(f'  Keyspace: {settings.CASSANDRA_KEYSPACE}'))
            self.stdout.write(self.style.SUCCESS('  Primary Key: ((stellar_account), change_time)'))
            self.stdout.write(self.style.SUCCESS('  Clustering Order: change_time DESC'))
            self.stdout.write('')
            self.stdout.write('Table is now ready for HVA ranking event tracking.')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error creating table: {str(e)}'))
            raise
