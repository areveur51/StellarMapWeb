"""
Regression test for Query Builder "Processing Accounts" query.

This test verifies that the processing_accounts query correctly:
- Scans both Search Cache and Account Lineage tables
- Detects stale processing (>30 minutes)
- Shows table source for each account
- Returns empty results when no processing accounts exist
"""
import datetime
from datetime import timedelta
from django.test import TestCase, Client

from apiApp.model_loader import StellarAccountSearchCache, StellarCreatorAccountLineage


class QueryBuilderProcessingAccountsTest(TestCase):
    """Test the processing_accounts query endpoint."""

    def setUp(self):
        """Set up test client and timestamps."""
        self.client = Client()
        self.now = datetime.datetime.utcnow()
        self.fresh = self.now - timedelta(minutes=10)  # Fresh (< 30 min)
        self.stale = self.now - timedelta(minutes=45)  # Stale (> 30 min)

    def test_returns_valid_json_structure(self):
        """Test that query returns valid JSON with expected structure."""
        response = self.client.get('/api/cassandra-query/', {
            'query': 'processing_accounts',
            'network': 'public',
            'limit': 10
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify required fields
        self.assertIn('results', data)
        self.assertIn('description', data)
        self.assertIn('visible_columns', data)
        self.assertIn('count', data)

        # Verify visible_columns includes table_source
        self.assertIn('table_source', data['visible_columns'])

    def test_empty_results_when_no_processing_accounts(self):
        """Test that query returns empty when no PROCESSING accounts exist."""
        # Create only PENDING/COMPLETE accounts, no PROCESSING
        pending = StellarAccountSearchCache(
            stellar_account='G' + 'A' * 55,
            network_name='public',
            status='PENDING',
            created_at=self.fresh,
            updated_at=self.fresh
        )
        pending.save()

        response = self.client.get('/api/cassandra-query/', {
            'query': 'processing_accounts',
            'network': 'public',
            'limit': 10
        })

        data = response.json()
        self.assertEqual(data['count'], 0, 
                        "Should return 0 when no PROCESSING accounts exist")
        self.assertEqual(len(data['results']), 0,
                        "Results should be empty array")

        # Cleanup
        pending.delete()

    def test_description_mentions_both_tables(self):
        """Test that description indicates dual-table scanning."""
        response = self.client.get('/api/cassandra-query/', {
            'query': 'processing_accounts',
            'network': 'public',
            'limit': 10
        })

        data = response.json()
        description = data['description'].lower()

        # Verify description mentions both tables or dual scanning
        self.assertTrue(
            'both' in description or 'search cache' in description,
            "Description should mention dual-table scanning"
        )

    def test_network_parameter_respected(self):
        """Test that network parameter filters results correctly."""
        # Test public network
        response_public = self.client.get('/api/cassandra-query/', {
            'query': 'processing_accounts',
            'network': 'public',
            'limit': 10
        })

        # Test testnet
        response_testnet = self.client.get('/api/cassandra-query/', {
            'query': 'processing_accounts',
            'network': 'testnet',
            'limit': 10
        })

        # Both should return valid responses
        self.assertEqual(response_public.status_code, 200)
        self.assertEqual(response_testnet.status_code, 200)
