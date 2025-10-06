"""
Tests for Search Cache and Account Lineage tabs functionality.

Tests verify:
1. Search Cache tab displays correct database entry after PENDING creation
2. Account Lineage tab recursively collects lineage records
3. create_pending_entry properly creates database entries
"""

import json
import datetime
from django.test import TestCase, Client
from django.urls import reverse
from apiApp.models import StellarAccountSearchCache, StellarCreatorAccountLineage
from apiApp.helpers.sm_cache import StellarMapCacheHelpers
from apiApp.models import (
    PENDING_MAKE_PARENT_LINEAGE,
    DONE_MAKE_PARENT_LINEAGE,
)


class SearchCacheTabTestCase(TestCase):
    """Test Search Cache tab data accuracy."""
    
    databases = ['default', 'cassandra']
    
    def setUp(self):
        """Set up test client and test data."""
        self.client = Client()
        self.test_account = 'GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB'
        self.test_network = 'public'
    
    def tearDown(self):
        """Clean up test data."""
        try:
            StellarAccountSearchCache.objects.filter(
                stellar_account=self.test_account
            ).delete()
        except Exception:
            pass
    
    def test_create_pending_entry_creates_database_record(self):
        """Test that create_pending_entry actually creates a database record."""
        cache_helpers = StellarMapCacheHelpers()
        
        # Create pending entry
        cache_entry = cache_helpers.create_pending_entry(
            self.test_account,
            self.test_network
        )
        
        # Verify entry was created
        self.assertIsNotNone(cache_entry)
        self.assertEqual(cache_entry.stellar_account, self.test_account)
        self.assertEqual(cache_entry.network_name, self.test_network)
        self.assertEqual(cache_entry.status, PENDING_MAKE_PARENT_LINEAGE)
        
        # Verify it can be retrieved from database
        retrieved_entry = StellarAccountSearchCache.objects.get(
            stellar_account=self.test_account,
            network_name=self.test_network
        )
        self.assertEqual(retrieved_entry.stellar_account, self.test_account)
        self.assertEqual(retrieved_entry.status, PENDING_MAKE_PARENT_LINEAGE)
    
    def test_search_view_creates_pending_entry_for_new_account(self):
        """Test that searching for a new account creates a PENDING entry."""
        # Make search request for new account
        response = self.client.get(
            reverse('search_view'),
            {
                'account': self.test_account,
                'network': self.test_network
            }
        )
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        
        # Check that PENDING entry was created in database
        cache_entry = StellarAccountSearchCache.objects.filter(
            stellar_account=self.test_account,
            network_name=self.test_network
        ).first()
        
        # Verify entry exists and has PENDING status
        self.assertIsNotNone(
            cache_entry,
            "PENDING cache entry should be created for new account search"
        )
        self.assertEqual(cache_entry.status, PENDING_MAKE_PARENT_LINEAGE)
    
    def test_search_cache_tab_shows_pending_entry(self):
        """Test that Search Cache tab displays PENDING entry data."""
        # Make search request
        response = self.client.get(
            reverse('search_view'),
            {
                'account': self.test_account,
                'network': self.test_network
            }
        )
        
        # Extract request_status_data from context
        request_status_data = response.context.get('request_status_data', {})
        
        # Verify it's not showing NOT_FOUND
        self.assertNotEqual(
            request_status_data.get('status'),
            'NOT_FOUND',
            "Should not show NOT_FOUND for new account search"
        )
        
        # Verify it shows PENDING status
        self.assertEqual(
            request_status_data.get('status'),
            PENDING_MAKE_PARENT_LINEAGE,
            f"Search Cache tab should show PENDING status, got: {request_status_data}"
        )
        
        # Verify other required fields
        self.assertEqual(request_status_data.get('stellar_account'), self.test_account)
        self.assertEqual(request_status_data.get('network'), self.test_network)
        self.assertIn('cache_status', request_status_data)
    
    def test_search_cache_tab_shows_cached_data_when_available(self):
        """Test that Search Cache tab shows cached data for existing entries."""
        # Create cache entry with data
        cache_helpers = StellarMapCacheHelpers()
        test_tree_data = {
            'name': self.test_account,
            'node_type': 'ISSUER',
            'children': []
        }
        cache_helpers.update_cache(
            self.test_account,
            self.test_network,
            test_tree_data,
            status=DONE_MAKE_PARENT_LINEAGE
        )
        
        # Make search request
        response = self.client.get(
            reverse('search_view'),
            {
                'account': self.test_account,
                'network': self.test_network
            }
        )
        
        # Extract request_status_data from context
        request_status_data = response.context.get('request_status_data', {})
        
        # Verify it shows DONE status
        self.assertEqual(request_status_data.get('status'), DONE_MAKE_PARENT_LINEAGE)
        self.assertTrue(request_status_data.get('has_cached_data'))


class AccountLineageTabTestCase(TestCase):
    """Test Account Lineage tab data accuracy."""
    
    databases = ['default', 'cassandra']
    
    def setUp(self):
        """Set up test client and test lineage data."""
        self.client = Client()
        self.test_account = 'GACCOUNT1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ12345'
        self.creator_account = 'GCREATOR1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ12345'
        self.grandparent_account = 'GGRANDPA1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ12345'
        self.test_network = 'public'
    
    def tearDown(self):
        """Clean up test data."""
        try:
            StellarCreatorAccountLineage.objects.filter(
                stellar_account=self.test_account
            ).delete()
            StellarCreatorAccountLineage.objects.filter(
                stellar_account=self.creator_account
            ).delete()
        except Exception:
            pass
    
    def test_account_lineage_tab_collects_single_lineage_record(self):
        """Test that Account Lineage tab shows single lineage record."""
        # Create lineage record
        StellarCreatorAccountLineage.objects.create(
            stellar_account=self.test_account,
            stellar_creator_account=self.creator_account,
            network_name=self.test_network,
            xlm_balance='100.0000000',
            home_domain='example.com',
            stellar_account_created_at=datetime.datetime.utcnow(),
        )
        
        # Make search request
        response = self.client.get(
            reverse('search_view'),
            {
                'account': self.test_account,
                'network': self.test_network
            }
        )
        
        # Extract account_lineage_data from context
        account_lineage_data = response.context.get('account_lineage_data', [])
        
        # Verify lineage record is present
        self.assertEqual(len(account_lineage_data), 1)
        self.assertEqual(account_lineage_data[0]['stellar_account'], self.test_account)
        self.assertEqual(account_lineage_data[0]['stellar_creator_account'], self.creator_account)
    
    def test_account_lineage_tab_recursively_follows_creator_chain(self):
        """Test that Account Lineage tab recursively collects creator chain."""
        # Create lineage chain: test_account -> creator_account -> grandparent_account
        StellarCreatorAccountLineage.objects.create(
            stellar_account=self.test_account,
            stellar_creator_account=self.creator_account,
            network_name=self.test_network,
            xlm_balance='100.0000000',
            stellar_account_created_at=datetime.datetime.utcnow(),
        )
        
        StellarCreatorAccountLineage.objects.create(
            stellar_account=self.creator_account,
            stellar_creator_account=self.grandparent_account,
            network_name=self.test_network,
            xlm_balance='200.0000000',
            stellar_account_created_at=datetime.datetime.utcnow(),
        )
        
        # Make search request for test_account
        response = self.client.get(
            reverse('search_view'),
            {
                'account': self.test_account,
                'network': self.test_network
            }
        )
        
        # Extract account_lineage_data from context
        account_lineage_data = response.context.get('account_lineage_data', [])
        
        # Verify both lineage records are collected
        self.assertGreaterEqual(
            len(account_lineage_data),
            2,
            "Should recursively collect creator chain (test_account and creator_account)"
        )
        
        # Verify accounts are present in lineage
        accounts_in_lineage = {
            record['stellar_account'] for record in account_lineage_data
        }
        self.assertIn(self.test_account, accounts_in_lineage)
        self.assertIn(self.creator_account, accounts_in_lineage)
    
    def test_account_lineage_tab_prevents_infinite_loops(self):
        """Test that Account Lineage tab prevents infinite loops with circular references."""
        # Create circular reference: account1 -> account2 -> account1
        account1 = 'GACCOUNT1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ11111'
        account2 = 'GACCOUNT1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ22222'
        
        try:
            StellarCreatorAccountLineage.objects.create(
                stellar_account=account1,
                stellar_creator_account=account2,
                network_name=self.test_network,
                stellar_account_created_at=datetime.datetime.utcnow(),
            )
            
            StellarCreatorAccountLineage.objects.create(
                stellar_account=account2,
                stellar_creator_account=account1,
                network_name=self.test_network,
                stellar_account_created_at=datetime.datetime.utcnow(),
            )
            
            # Make search request - should not hang or error
            response = self.client.get(
                reverse('search_view'),
                {
                    'account': account1,
                    'network': self.test_network
                },
                follow=True
            )
            
            # Should return successfully without infinite loop
            self.assertEqual(response.status_code, 200)
            
            # Clean up
            StellarCreatorAccountLineage.objects.filter(stellar_account=account1).delete()
            StellarCreatorAccountLineage.objects.filter(stellar_account=account2).delete()
            
        except Exception as e:
            # Clean up even on error
            try:
                StellarCreatorAccountLineage.objects.filter(stellar_account=account1).delete()
                StellarCreatorAccountLineage.objects.filter(stellar_account=account2).delete()
            except:
                pass
            raise e
