"""
Regression test for Query Builder Processing Accounts status matching.

Bug: Pre-defined query checked for 'PROGRESS' substring, but actual status values 
      contain 'PROCESSING', causing 0 results even when 28 processing accounts existed.
Fix: Changed to check for 'PROCESSING' (case-insensitive) instead of 'PROGRESS'

This test ensures the fix prevents future regressions by:
1. Seeding accounts with 'PROCESSING' status
2. Verifying query finds them
3. Seeding accounts with 'PROGRESS' status (old bug scenario)
4. Verifying query correctly ignores them

Created: October 23, 2025
"""
import datetime
from datetime import timedelta
from django.test import TestCase, Client
from apiApp.model_loader import StellarCreatorAccountLineage, StellarAccountSearchCache


class QueryBuilderProcessingStatusRegressionTest(TestCase):
    """Regression test ensuring PROCESSING vs PROGRESS distinction."""

    def setUp(self):
        """Set up test client and timestamps."""
        self.client = Client()
        self.now = datetime.datetime.utcnow()

    def test_query_finds_processing_status_accounts(self):
        """Test that query finds accounts with 'PROCESSING' status."""
        # Create accounts with various PROCESSING statuses
        processing_statuses = [
            'PROCESSING',
            'PROCESSING_STAGE_1',
            'PROCESSING_STAGE_2', 
            'PROCESSING_ASSETS',
        ]
        
        created_accounts = []
        for i, status in enumerate(processing_statuses):
            account = StellarCreatorAccountLineage(
                stellar_account=f'G{"P" + str(i)}' + 'X' * 53,
                network_name='public',
                status=status,
                processing_started_at=self.now,
                created_at=self.now,
                updated_at=self.now
            )
            account.save()
            created_accounts.append(account)
        
        try:
            # Query for processing accounts
            response = self.client.get('/api/cassandra-query/', {
                'query': 'processing_accounts',
                'network': 'public',
                'limit': 100
            })
            
            data = response.json()
            
            # CRITICAL: Should find all PROCESSING accounts
            self.assertGreaterEqual(data['count'], len(processing_statuses),
                                  f"Should find at least {len(processing_statuses)} PROCESSING accounts")
            
            # Verify each status variant is found
            found_accounts = {r['stellar_account'] for r in data['results']}
            for account in created_accounts:
                self.assertIn(account.stellar_account, found_accounts,
                            f"Should find account with status {account.status}")
                
        finally:
            # Cleanup
            for account in created_accounts:
                account.delete()

    def test_query_does_not_find_progress_status_accounts(self):
        """Test that query does NOT find accounts with 'PROGRESS' status (old bug scenario)."""
        # Create account with 'PROGRESS' status (the old incorrect check)
        progress_account = StellarCreatorAccountLineage(
            stellar_account='G' + 'R' * 55,
            network_name='public',
            status='PROGRESS',  # This should NOT be found
            processing_started_at=self.now,
            created_at=self.now,
            updated_at=self.now
        )
        progress_account.save()
        
        try:
            # Query for processing accounts
            response = self.client.get('/api/cassandra-query/', {
                'query': 'processing_accounts',
                'network': 'public',
                'limit': 100
            })
            
            data = response.json()
            
            # CRITICAL: Should NOT find 'PROGRESS' status account
            found_accounts = [r['stellar_account'] for r in data['results']]
            self.assertNotIn(progress_account.stellar_account, found_accounts,
                           "Should NOT find accounts with 'PROGRESS' status - only 'PROCESSING'")
            
        finally:
            # Cleanup
            progress_account.delete()

    def test_query_matches_processing_case_insensitive(self):
        """Test that query matches PROCESSING case-insensitively."""
        # Create accounts with different case variations
        case_variations = [
            ('processing', 'G' + 'L' * 55),
            ('PROCESSING', 'G' + 'U' * 55),
            ('Processing', 'G' + 'M' * 55),
        ]
        
        created_accounts = []
        for status, address in case_variations:
            account = StellarCreatorAccountLineage(
                stellar_account=address,
                network_name='public',
                status=status,
                processing_started_at=self.now,
                created_at=self.now,
                updated_at=self.now
            )
            account.save()
            created_accounts.append(account)
        
        try:
            # Query for processing accounts
            response = self.client.get('/api/cassandra-query/', {
                'query': 'processing_accounts',
                'network': 'public',
                'limit': 100
            })
            
            data = response.json()
            found_accounts = {r['stellar_account'] for r in data['results']}
            
            # All case variations should be found
            for account in created_accounts:
                self.assertIn(account.stellar_account, found_accounts,
                            f"Should find account with status '{account.status}' (case-insensitive)")
                
        finally:
            # Cleanup
            for account in created_accounts:
                account.delete()

    def test_query_scans_both_tables(self):
        """Test that query scans BOTH Search Cache AND Account Lineage tables."""
        # Create one account in Search Cache
        cache_account = StellarAccountSearchCache(
            stellar_account='G' + 'C' * 55,
            network_name='public',
            status='PROCESSING',
            created_at=self.now,
            updated_at=self.now
        )
        cache_account.save()
        
        # Create one account in Account Lineage
        lineage_account = StellarCreatorAccountLineage(
            stellar_account='G' + 'L' * 55,
            network_name='public',
            status='PROCESSING',
            processing_started_at=self.now,
            created_at=self.now,
            updated_at=self.now
        )
        lineage_account.save()
        
        try:
            # Query for processing accounts
            response = self.client.get('/api/cassandra-query/', {
                'query': 'processing_accounts',
                'network': 'public',
                'limit': 100
            })
            
            data = response.json()
            
            # CRITICAL: Should find BOTH accounts (from both tables)
            found_accounts = {r['stellar_account'] for r in data['results']}
            
            # Verify BOTH specific accounts are found
            self.assertIn(cache_account.stellar_account, found_accounts,
                        "Should find account from Search Cache table")
            self.assertIn(lineage_account.stellar_account, found_accounts,
                        "Should find account from Account Lineage table")
            
            # Verify table_source includes BOTH tables (critical: use AND not OR)
            found_sources = {r['table_source'] for r in data['results']}
            has_cache = any('Search Cache' in source for source in found_sources)
            has_lineage = any('Account Lineage' in source for source in found_sources)
            
            self.assertTrue(has_cache, 
                          "MUST scan Search Cache table - regression would break this")
            self.assertTrue(has_lineage, 
                          "MUST scan Account Lineage table - regression would break this")
            
        finally:
            # Cleanup
            cache_account.delete()
            lineage_account.delete()
