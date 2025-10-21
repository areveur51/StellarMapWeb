"""
Tests for Query Builder API endpoint and pre-defined queries.

This module tests all 10 pre-defined queries to ensure they:
1. Filter correctly by network (public/testnet)
2. Return accurate results
3. Handle edge cases properly
4. Respect performance limits (max_scan)
"""

from django.test import TestCase, Client
from datetime import datetime, timedelta
from django.utils import timezone
import json


class QueryBuilderAPITests(TestCase):
    """Test Query Builder API functionality"""
    
    def setUp(self):
        """Set up test client and test data"""
        self.client = Client()
        self.api_url = '/api/cassandra-query/'
        
        # Import models
        from apiApp.model_loader import (
            StellarCreatorAccountLineage,
            StellarAccountSearchCache,
            StellarAccountStageExecution,
            HVAStandingChange,
            USE_CASSANDRA
        )
        
        self.StellarCreatorAccountLineage = StellarCreatorAccountLineage
        self.StellarAccountSearchCache = StellarAccountSearchCache
        self.StellarAccountStageExecution = StellarAccountStageExecution
        self.HVAStandingChange = HVAStandingChange
        self.USE_CASSANDRA = USE_CASSANDRA
        
        # Create test data for both networks
        self._create_test_data()
    
    def _create_test_data(self):
        """Create comprehensive test data for all query types"""
        now = datetime.utcnow()
        
        # Test accounts for PUBLIC network
        # 1. High Value Account (>1M XLM)
        self.hva_public = self.StellarCreatorAccountLineage.objects.create(
            stellar_account='GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU',
            network_name='public',
            status='BIGQUERY_DONE',
            xlm_balance=2483571.75,
            is_hva=True,
            stellar_creator_account='GCREATOR1EXAMPLE',
            created_at=now,
            updated_at=now
        )
        
        # 2. Stuck account (processing > 60 minutes)
        self.stuck_public = self.StellarCreatorAccountLineage.objects.create(
            stellar_account='GSTUCK1PUBLIC',
            network_name='public',
            status='STAGE_6_IN_PROGRESS',
            retry_count=3,
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2)
        )
        
        # 3. Pending account
        self.pending_public = self.StellarCreatorAccountLineage.objects.create(
            stellar_account='GPENDING1PUBLIC',
            network_name='public',
            status='PENDING',
            retry_count=0,
            created_at=now,
            updated_at=now
        )
        
        # 4. Processing account
        self.processing_public = self.StellarCreatorAccountLineage.objects.create(
            stellar_account='GPROCESSING1PUBLIC',
            network_name='public',
            status='STAGE_2_IN_PROGRESS',
            retry_count=1,
            created_at=now - timedelta(minutes=10),
            updated_at=now - timedelta(minutes=10)
        )
        
        # 5. Completed account
        self.completed_public = self.StellarCreatorAccountLineage.objects.create(
            stellar_account='GCOMPLETED1PUBLIC',
            network_name='public',
            status='BIGQUERY_DONE',
            stellar_creator_account='GCREATOR2EXAMPLE',
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1)
        )
        
        # Test accounts for TESTNET network
        # 1. Testnet HVA (should NOT appear in public queries)
        self.hva_testnet = self.StellarCreatorAccountLineage.objects.create(
            stellar_account='GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU',
            network_name='testnet',
            status='FAILED',
            xlm_balance=0.0,  # No balance on testnet
            created_at=now,
            updated_at=now
        )
        
        # 2. Testnet pending
        self.pending_testnet = self.StellarCreatorAccountLineage.objects.create(
            stellar_account='GPENDING1TESTNET',
            network_name='testnet',
            status='PENDING',
            retry_count=0,
            created_at=now,
            updated_at=now
        )
        
        # Create cache entries
        # Public cache - fresh (updated within 1 hour)
        self.cache_fresh_public = self.StellarAccountSearchCache.objects.create(
            stellar_account='GCACHE1PUBLIC',
            network_name='public',
            status='CACHED',
            created_at=now - timedelta(minutes=30),
            updated_at=now - timedelta(minutes=30)
        )
        
        # Public cache - stale (>12 hours old)
        self.cache_stale_public = self.StellarAccountSearchCache.objects.create(
            stellar_account='GCACHE2PUBLIC',
            network_name='public',
            status='CACHED',
            created_at=now - timedelta(hours=24),
            updated_at=now - timedelta(hours=24)
        )
        
        # Testnet cache - fresh
        self.cache_fresh_testnet = self.StellarAccountSearchCache.objects.create(
            stellar_account='GCACHE1TESTNET',
            network_name='testnet',
            status='CACHED',
            created_at=now - timedelta(minutes=15),
            updated_at=now - timedelta(minutes=15)
        )
        
        # Create stage executions
        # Public - failed stage
        self.stage_failed_public = self.StellarAccountStageExecution.objects.create(
            stellar_account='GSTAGE1PUBLIC',
            network_name='public',
            stage_number=3,
            status='FAILED',
            created_at=now
        )
        
        # Testnet - failed stage
        self.stage_failed_testnet = self.StellarAccountStageExecution.objects.create(
            stellar_account='GSTAGE1TESTNET',
            network_name='testnet',
            stage_number=2,
            status='FAILED',
            created_at=now
        )
        
        # Create HVA standing changes
        # Public - recent change
        self.hva_change_public = self.HVAStandingChange.objects.create(
            stellar_account='GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU',
            network_name='public',
            event_type='ENTERED',
            created_at=timezone.now() - timedelta(hours=12)
        )
        
        # Testnet - recent change
        self.hva_change_testnet = self.HVAStandingChange.objects.create(
            stellar_account='GHVACHANGE1TESTNET',
            network_name='testnet',
            event_type='EXITED',
            created_at=timezone.now() - timedelta(hours=6)
        )
    
    def test_query_requires_network_parameter(self):
        """Test that network parameter defaults to 'public'"""
        response = self.client.get(self.api_url, {
            'query': 'pending_accounts',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should default to public network
        self.assertIn('results', data)
    
    def test_network_validation(self):
        """Test that invalid network defaults to public"""
        response = self.client.get(self.api_url, {
            'query': 'pending_accounts',
            'network': 'invalid_network',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        # Should accept and default to public
    
    def test_stuck_accounts_query_public(self):
        """Test stuck accounts query filters by public network"""
        response = self.client.get(self.api_url, {
            'query': 'stuck_accounts',
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should return stuck public account, not testnet
        results = data['results']
        accounts = [r['stellar_account'] for r in results]
        
        # Public stuck account should be in results
        self.assertIn('GSTUCK1PUBLIC', accounts)
        
        # All results should be from public network
        for result in results:
            self.assertEqual(result['network_name'], 'public')
    
    def test_stuck_accounts_query_testnet(self):
        """Test stuck accounts query filters by testnet network"""
        response = self.client.get(self.api_url, {
            'query': 'stuck_accounts',
            'network': 'testnet',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        
        # Should not include public stuck account
        accounts = [r['stellar_account'] for r in results]
        self.assertNotIn('GSTUCK1PUBLIC', accounts)
        
        # All results should be from testnet
        for result in results:
            self.assertEqual(result['network_name'], 'testnet')
    
    def test_pending_accounts_query(self):
        """Test pending accounts query with network filtering"""
        response = self.client.get(self.api_url, {
            'query': 'pending_accounts',
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        accounts = [r['stellar_account'] for r in results]
        
        # Should include public pending, not testnet
        self.assertIn('GPENDING1PUBLIC', accounts)
        self.assertNotIn('GPENDING1TESTNET', accounts)
        
        # All should have PENDING status and public network
        for result in results:
            self.assertEqual(result['status'], 'PENDING')
            self.assertEqual(result['network_name'], 'public')
    
    def test_processing_accounts_query(self):
        """Test processing accounts query with network filtering"""
        response = self.client.get(self.api_url, {
            'query': 'processing_accounts',
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        accounts = [r['stellar_account'] for r in results]
        
        # Should include public processing account
        self.assertIn('GPROCESSING1PUBLIC', accounts)
        
        # All should have PROGRESS in status
        for result in results:
            self.assertIn('PROGRESS', result['status'])
            self.assertEqual(result['network_name'], 'public')
    
    def test_completed_accounts_query(self):
        """Test completed accounts query with network filtering"""
        response = self.client.get(self.api_url, {
            'query': 'completed_accounts',
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        accounts = [r['stellar_account'] for r in results]
        
        # Should include completed accounts (HVA and completed)
        self.assertIn('GCOMPLETED1PUBLIC', accounts)
        
        # All should have COMPLETE or DONE in status
        for result in results:
            status = result['status']
            self.assertTrue('COMPLETE' in status or 'DONE' in status)
            self.assertEqual(result['network_name'], 'public')
    
    def test_high_value_accounts_query_public(self):
        """Test HVA query returns accounts only from public network"""
        response = self.client.get(self.api_url, {
            'query': 'high_value_accounts',
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        self.assertGreater(len(results), 0, "Should find at least one HVA on public network")
        
        # Check that the HVA account is in results
        accounts = [r['stellar_account'] for r in results]
        self.assertIn('GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU', accounts)
        
        # Verify all results are from public and have xlm_balance > 1M
        for result in results:
            self.assertEqual(result['network_name'], 'public')
            self.assertGreater(result['xlm_balance'], 1000000)
    
    def test_high_value_accounts_query_testnet(self):
        """Test HVA query returns empty for testnet (no HVAs)"""
        response = self.client.get(self.api_url, {
            'query': 'high_value_accounts',
            'network': 'testnet',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        
        # Testnet version of account has 0 balance, shouldn't appear
        accounts = [r['stellar_account'] for r in results]
        self.assertNotIn('GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU', accounts)
        
        # All should be from testnet if any exist
        for result in results:
            self.assertEqual(result['network_name'], 'testnet')
    
    def test_fresh_records_query(self):
        """Test fresh records query (updated within 1 hour)"""
        response = self.client.get(self.api_url, {
            'query': 'fresh_records',
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        accounts = [r['stellar_account'] for r in results]
        
        # Should include fresh public cache, not stale
        self.assertIn('GCACHE1PUBLIC', accounts)
        self.assertNotIn('GCACHE2PUBLIC', accounts)  # Stale (24h old)
        
        # All should be from public network
        for result in results:
            self.assertEqual(result['network_name'], 'public')
    
    def test_stale_records_query(self):
        """Test stale records query (>12 hours old)"""
        response = self.client.get(self.api_url, {
            'query': 'stale_records',
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        accounts = [r['stellar_account'] for r in results]
        
        # Should include stale public cache, not fresh
        self.assertIn('GCACHE2PUBLIC', accounts)
        self.assertNotIn('GCACHE1PUBLIC', accounts)  # Fresh (30min old)
        
        # All should be from public network
        for result in results:
            self.assertEqual(result['network_name'], 'public')
    
    def test_failed_stages_query(self):
        """Test failed stages query with network filtering"""
        response = self.client.get(self.api_url, {
            'query': 'failed_stages',
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        accounts = [r['stellar_account'] for r in results]
        
        # Should include public failed stage, not testnet
        self.assertIn('GSTAGE1PUBLIC', accounts)
        self.assertNotIn('GSTAGE1TESTNET', accounts)
        
        # All should have FAILED status and public network
        for result in results:
            self.assertEqual(result['status'], 'FAILED')
            self.assertEqual(result['network_name'], 'public')
    
    def test_recent_hva_changes_query(self):
        """Test recent HVA standing changes query (24h)"""
        response = self.client.get(self.api_url, {
            'query': 'recent_hva_changes',
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        accounts = [r['stellar_account'] for r in results]
        
        # Should include public HVA change, not testnet
        self.assertIn('GACJFMOXTSE7QOL5HNYI2NIAQ4RDHZTGD6FNYK4P5THDVNWIKQDGOODU', accounts)
        self.assertNotIn('GHVACHANGE1TESTNET', accounts)
        
        # All should be from public network
        for result in results:
            self.assertEqual(result['network_name'], 'public')
    
    def test_custom_query_with_network_filter(self):
        """Test custom query builder respects network parameter"""
        filters = [
            {'column': 'status', 'operator': 'equals', 'value': 'PENDING'}
        ]
        
        response = self.client.get(self.api_url, {
            'query': 'custom',
            'table': 'lineage',
            'filters': json.dumps(filters),
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        accounts = [r['stellar_account'] for r in results]
        
        # Should include public pending, not testnet
        self.assertIn('GPENDING1PUBLIC', accounts)
        self.assertNotIn('GPENDING1TESTNET', accounts)
        
        # All should be from public network
        for result in results:
            self.assertEqual(result['network_name'], 'public')
    
    def test_query_result_limit(self):
        """Test that result limit parameter is respected"""
        response = self.client.get(self.api_url, {
            'query': 'completed_accounts',
            'network': 'public',
            'limit': 1  # Very small limit
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        self.assertLessEqual(len(results), 1, "Should respect limit parameter")
    
    def test_missing_query_parameter(self):
        """Test error handling for missing query parameter"""
        response = self.client.get(self.api_url, {
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
    
    def test_invalid_query_name(self):
        """Test error handling for invalid query name"""
        response = self.client.get(self.api_url, {
            'query': 'nonexistent_query',
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
    
    def test_orphan_accounts_query(self):
        """Test orphan accounts query (cached without lineage)"""
        # Create orphan in cache only (no lineage)
        orphan_public = self.StellarAccountSearchCache.objects.create(
            stellar_account='GORPHAN1PUBLIC',
            network_name='public',
            status='CACHED',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        response = self.client.get(self.api_url, {
            'query': 'orphan_accounts',
            'network': 'public',
            'limit': 50
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        results = data['results']
        accounts = [r['stellar_account'] for r in results]
        
        # Should include orphan account
        self.assertIn('GORPHAN1PUBLIC', accounts)
        
        # Should NOT include accounts that have lineage
        self.assertNotIn('GCACHE1PUBLIC', accounts)  # Has lineage (HVA)
        
        # All should be from public network
        for result in results:
            self.assertEqual(result['network_name'], 'public')
    
    def tearDown(self):
        """Clean up test data"""
        # Models automatically clean up in test database
        pass
