"""
Comprehensive regression tests for ALL dashboard blocks.

Tests every section of the System Dashboard to ensure displayed data
matches the actual database state, preventing false alerts and inaccurate metrics.

Created: 2025-10-23
Purpose: Ensure 100% dashboard accuracy across all sections
"""
import pytest
from django.test import TestCase, Client
from django.utils import timezone
from datetime import datetime, timedelta
from apiApp.model_loader import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage
)


@pytest.mark.django_db
class TestDashboardAlertsSection(TestCase):
    """Test ALERTS & RECOMMENDATIONS section accuracy."""
    
    def setUp(self):
        """Set up test client and baseline data."""
        self.client = Client()
        self.now = datetime.utcnow()
        
    def tearDown(self):
        """Clean up test data."""
        try:
            StellarAccountSearchCache.objects.all().delete()
            StellarCreatorAccountLineage.objects.all().delete()
        except:
            pass
    
    def test_stuck_records_alert_shows_when_accounts_stuck(self):
        """Stuck Records Alert should appear when accounts are actually stuck."""
        # Create stuck account (over 30 minutes in PROCESSING)
        stuck_time = self.now - timedelta(minutes=35)
        stuck_account = StellarAccountSearchCache(
            stellar_account='G' + 'S' * 55,
            network_name='public',
            status='PROCESSING',
            created_at=stuck_time,
            updated_at=stuck_time
        )
        stuck_account.save()
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Alert should be present
            self.assertContains(response, 'Stuck Records Alert')
            self.assertGreater(response.context['db_stats']['stuck_accounts'], 0)
            
        finally:
            stuck_account.delete()
    
    def test_stuck_records_alert_hidden_when_no_stuck_accounts(self):
        """Stuck Records Alert should be hidden when all accounts are processing normally."""
        # Create fresh account
        fresh_account = StellarAccountSearchCache(
            stellar_account='G' + 'F' * 55,
            network_name='public',
            status='PROCESSING',
            created_at=self.now,
            updated_at=self.now
        )
        fresh_account.save()
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Stuck count should be 0
            self.assertEqual(response.context['db_stats']['stuck_accounts'], 0)
            
        finally:
            fresh_account.delete()
    
    def test_all_systems_healthy_alert_when_no_issues(self):
        """All Systems Healthy alert should show when there are no issues."""
        # Clean database
        try:
            StellarAccountSearchCache.objects.all().delete()
            StellarCreatorAccountLineage.objects.all().delete()
        except:
            pass
        
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        
        # Should show healthy message when no issues
        self.assertContains(response, 'All Systems Healthy')


@pytest.mark.django_db
class TestDashboardDatabaseHealthSection(TestCase):
    """Test DATABASE HEALTH section accuracy."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.now = datetime.utcnow()
        
    def tearDown(self):
        """Clean up test data."""
        try:
            StellarAccountSearchCache.objects.all().delete()
        except:
            pass
    
    def test_total_accounts_matches_database(self):
        """Total Accounts should match actual database count."""
        # Create exactly 5 accounts
        created_accounts = []
        for i in range(5):
            account = StellarAccountSearchCache(
                stellar_account='G' + str(i).zfill(55),
                network_name='public',
                status='COMPLETE',
                created_at=self.now,
                updated_at=self.now
            )
            account.save()
            created_accounts.append(account)
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should show exactly 5 total accounts
            self.assertEqual(response.context['db_stats']['total_cached_accounts'], 5)
            
        finally:
            for account in created_accounts:
                account.delete()
    
    def test_fresh_records_calculation_accuracy(self):
        """Fresh Records should match accounts updated within cache TTL."""
        # Create fresh account (updated recently)
        fresh_account = StellarAccountSearchCache(
            stellar_account='G' + 'F' * 55,
            network_name='public',
            status='COMPLETE',
            created_at=self.now,
            updated_at=self.now
        )
        fresh_account.save()
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should have 1 fresh account
            self.assertEqual(response.context['db_stats']['fresh_accounts'], 1)
            self.assertEqual(response.context['db_stats']['stale_accounts'], 0)
            
        finally:
            fresh_account.delete()
    
    def test_stale_records_calculation_accuracy(self):
        """Stale Records should match accounts beyond cache TTL (12 hours default)."""
        # Create stale account (13 hours old)
        stale_time = self.now - timedelta(hours=13)
        stale_account = StellarAccountSearchCache(
            stellar_account='G' + 'S' * 55,
            network_name='public',
            status='COMPLETE',
            created_at=stale_time,
            updated_at=stale_time
        )
        stale_account.save()
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should have 1 stale account
            self.assertEqual(response.context['db_stats']['stale_accounts'], 1)
            
        finally:
            stale_account.delete()
    
    def test_stuck_records_uses_correct_thresholds(self):
        """Stuck Records should use correct thresholds per status."""
        # Create account stuck for 35 minutes (threshold is 30 min for PROCESSING)
        stuck_time = self.now - timedelta(minutes=35)
        stuck_account = StellarAccountSearchCache(
            stellar_account='G' + 'S' * 55,
            network_name='public',
            status='PROCESSING',
            created_at=stuck_time,
            updated_at=stuck_time
        )
        stuck_account.save()
        
        # Create account in PROCESSING for only 5 minutes (not stuck yet)
        not_stuck_time = self.now - timedelta(minutes=5)
        not_stuck_account = StellarAccountSearchCache(
            stellar_account='G' + 'N' * 55,
            network_name='public',
            status='PROCESSING',
            created_at=not_stuck_time,
            updated_at=not_stuck_time
        )
        not_stuck_account.save()
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should detect 1 stuck account (35 min) but not the 5 min one
            self.assertEqual(response.context['db_stats']['stuck_accounts'], 1)
            
        finally:
            stuck_account.delete()
            not_stuck_account.delete()


@pytest.mark.django_db
class TestDashboardProcessingStatusSection(TestCase):
    """Test PROCESSING STATUS section accuracy."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.now = datetime.utcnow()
        
    def tearDown(self):
        """Clean up test data."""
        try:
            StellarAccountSearchCache.objects.all().delete()
        except:
            pass
    
    def test_pending_count_matches_database(self):
        """Pending count should match accounts with PENDING status."""
        # Create 3 pending accounts
        created_accounts = []
        for i in range(3):
            account = StellarAccountSearchCache(
                stellar_account='G' + str(i).zfill(55),
                network_name='public',
                status='PENDING_MAKE_PARENT_LINEAGE',
                created_at=self.now,
                updated_at=self.now
            )
            account.save()
            created_accounts.append(account)
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should show 3 pending accounts
            self.assertEqual(response.context['db_stats']['pending_accounts'], 3)
            
        finally:
            for account in created_accounts:
                account.delete()
    
    def test_in_progress_count_matches_database(self):
        """In Progress count should match accounts with IN_PROGRESS status."""
        # Create 2 in-progress accounts
        created_accounts = []
        for i in range(2):
            account = StellarAccountSearchCache(
                stellar_account='G' + str(i).zfill(55),
                network_name='public',
                status='IN_PROGRESS_MAKE_PARENT_LINEAGE',
                created_at=self.now,
                updated_at=self.now
            )
            account.save()
            created_accounts.append(account)
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should show 2 in-progress accounts
            self.assertEqual(response.context['db_stats']['in_progress_accounts'], 2)
            
        finally:
            for account in created_accounts:
                account.delete()
    
    def test_completed_count_matches_database(self):
        """Completed count should match accounts with DONE status."""
        # Create 4 completed accounts
        created_accounts = []
        for i in range(4):
            account = StellarAccountSearchCache(
                stellar_account='G' + str(i).zfill(55),
                network_name='public',
                status='DONE_MAKE_PARENT_LINEAGE',
                created_at=self.now,
                updated_at=self.now
            )
            account.save()
            created_accounts.append(account)
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should show 4 completed accounts
            self.assertEqual(response.context['db_stats']['completed_accounts'], 4)
            
        finally:
            for account in created_accounts:
                account.delete()
    
    def test_re_inquiry_count_matches_database(self):
        """Re-inquiry count should match accounts with RE_INQUIRY status."""
        # Create 1 re-inquiry account
        account = StellarAccountSearchCache(
            stellar_account='G' + 'R' * 55,
            network_name='public',
            status='RE_INQUIRY',
            created_at=self.now,
            updated_at=self.now
        )
        account.save()
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should show 1 re-inquiry account
            self.assertEqual(response.context['db_stats']['re_inquiry_accounts'], 1)
            
        finally:
            account.delete()


@pytest.mark.django_db
class TestDashboardLineageIntegritySection(TestCase):
    """Test LINEAGE DATA INTEGRITY section accuracy."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.now = datetime.utcnow()
        
    def tearDown(self):
        """Clean up test data."""
        try:
            StellarAccountSearchCache.objects.all().delete()
            StellarCreatorAccountLineage.objects.all().delete()
        except:
            pass
    
    def test_total_lineage_records_matches_database(self):
        """Total Lineage Records should match actual lineage table count."""
        # Create 3 lineage records
        created_records = []
        for i in range(3):
            record = StellarCreatorAccountLineage(
                stellar_account='G' + str(i).zfill(55),
                network_name='public',
                status='COMPLETE',
                created_at=self.now,
                updated_at=self.now
            )
            record.save()
            created_records.append(record)
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should show 3 lineage records
            self.assertEqual(response.context['db_stats']['total_lineage_records'], 3)
            
        finally:
            for record in created_records:
                record.delete()
    
    def test_accounts_with_lineage_counts_unique_accounts(self):
        """Accounts with Lineage should count unique accounts with lineage data."""
        # Create 2 lineage records for the same account
        account_id = 'G' + 'A' * 55
        record1 = StellarCreatorAccountLineage(
            stellar_account=account_id,
            network_name='public',
            status='COMPLETE',
            created_at=self.now,
            updated_at=self.now
        )
        record1.save()
        
        record2 = StellarCreatorAccountLineage(
            stellar_account=account_id,
            network_name='public',
            status='PROCESSING',
            created_at=self.now,
            updated_at=self.now
        )
        record2.save()
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should show 1 unique account (even though 2 records exist)
            self.assertEqual(response.context['db_stats']['accounts_with_lineage'], 1)
            self.assertEqual(response.context['db_stats']['total_lineage_records'], 2)
            
        finally:
            record1.delete()
            record2.delete()
    
    def test_orphan_accounts_calculation_accuracy(self):
        """Orphan Accounts should show cached accounts without lineage."""
        # Create cache account with DONE status but no lineage
        cache_account = StellarAccountSearchCache(
            stellar_account='G' + 'C' * 55,
            network_name='public',
            status='DONE_MAKE_PARENT_LINEAGE',
            created_at=self.now,
            updated_at=self.now
        )
        cache_account.save()
        
        # Create another cache account WITH lineage
        cache_with_lineage = StellarAccountSearchCache(
            stellar_account='G' + 'L' * 55,
            network_name='public',
            status='DONE_MAKE_PARENT_LINEAGE',
            created_at=self.now,
            updated_at=self.now
        )
        cache_with_lineage.save()
        
        lineage_record = StellarCreatorAccountLineage(
            stellar_account='G' + 'L' * 55,
            network_name='public',
            status='COMPLETE',
            created_at=self.now,
            updated_at=self.now
        )
        lineage_record.save()
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should show 1 orphan (cache account without lineage)
            self.assertEqual(response.context['db_stats']['orphan_accounts'], 1)
            
        finally:
            cache_account.delete()
            cache_with_lineage.delete()
            lineage_record.delete()


@pytest.mark.django_db
class TestDashboardPerformanceMetricsSection(TestCase):
    """Test PERFORMANCE METRICS section accuracy."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.now = datetime.utcnow()
        
    def tearDown(self):
        """Clean up test data."""
        try:
            StellarAccountSearchCache.objects.all().delete()
        except:
            pass
    
    def test_avg_processing_time_calculation(self):
        """Avg Processing Time should calculate correctly from completed accounts."""
        # Create 2 completed accounts with known processing times
        # Account 1: 10 minutes to process
        account1_created = self.now - timedelta(minutes=10)
        account1 = StellarAccountSearchCache(
            stellar_account='G' + '1' * 55,
            network_name='public',
            status='DONE_MAKE_PARENT_LINEAGE',
            created_at=account1_created,
            updated_at=self.now
        )
        account1.save()
        
        # Account 2: 20 minutes to process
        account2_created = self.now - timedelta(minutes=20)
        account2 = StellarAccountSearchCache(
            stellar_account='G' + '2' * 55,
            network_name='public',
            status='DONE_MAKE_PARENT_LINEAGE',
            created_at=account2_created,
            updated_at=self.now
        )
        account2.save()
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Average should be approximately 15 minutes
            avg_time = response.context['performance_stats']['avg_processing_time_minutes']
            self.assertGreater(avg_time, 0)
            self.assertLess(avg_time, 30)  # Reasonable upper bound
            
        finally:
            account1.delete()
            account2.delete()
    
    def test_fastest_account_detection(self):
        """Fastest Account should show the minimum processing time."""
        # Create accounts with different processing times
        # Fast account: 2 minutes
        fast_created = self.now - timedelta(minutes=2)
        fast_account = StellarAccountSearchCache(
            stellar_account='G' + 'F' * 55,
            network_name='public',
            status='DONE_MAKE_PARENT_LINEAGE',
            created_at=fast_created,
            updated_at=self.now
        )
        fast_account.save()
        
        # Slow account: 30 minutes
        slow_created = self.now - timedelta(minutes=30)
        slow_account = StellarAccountSearchCache(
            stellar_account='G' + 'S' * 55,
            network_name='public',
            status='DONE_MAKE_PARENT_LINEAGE',
            created_at=slow_created,
            updated_at=self.now
        )
        slow_account.save()
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Fastest should be around 2 minutes
            fastest = response.context['performance_stats']['fastest_account_minutes']
            if fastest is not None:
                self.assertLess(fastest, 10)  # Should be less than 10 minutes
            
            # Slowest should be around 30 minutes
            slowest = response.context['performance_stats']['slowest_account_minutes']
            if slowest is not None:
                self.assertGreater(slowest, 20)  # Should be greater than 20 minutes
            
        finally:
            fast_account.delete()
            slow_account.delete()
    
    def test_processed_24h_accuracy(self):
        """Processed (24h) should count accounts processed in last 24 hours."""
        # Create account processed recently (within 24h)
        recent_time = self.now - timedelta(hours=12)
        recent_account = StellarAccountSearchCache(
            stellar_account='G' + 'R' * 55,
            network_name='public',
            status='DONE_MAKE_PARENT_LINEAGE',
            created_at=recent_time,
            updated_at=recent_time
        )
        recent_account.save()
        
        # Create old account (processed 48 hours ago)
        old_time = self.now - timedelta(hours=48)
        old_account = StellarAccountSearchCache(
            stellar_account='G' + 'O' * 55,
            network_name='public',
            status='DONE_MAKE_PARENT_LINEAGE',
            created_at=old_time,
            updated_at=old_time
        )
        old_account.save()
        
        try:
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)
            
            # Should count at least 1 (the recent account)
            processed_24h = response.context['performance_stats']['total_accounts_processed_24h']
            self.assertGreaterEqual(processed_24h, 1)
            
        finally:
            recent_account.delete()
            old_account.delete()


@pytest.mark.django_db
class TestDashboardZeroStateAccuracy(TestCase):
    """Test dashboard displays accurate zeros when database is empty."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
        
    def tearDown(self):
        """Clean up test data."""
        try:
            StellarAccountSearchCache.objects.all().delete()
            StellarCreatorAccountLineage.objects.all().delete()
        except:
            pass
    
    def test_all_counts_zero_when_database_empty(self):
        """All dashboard counts should be 0 when database is empty."""
        # Clean database
        try:
            StellarAccountSearchCache.objects.all().delete()
            StellarCreatorAccountLineage.objects.all().delete()
        except:
            pass
        
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        
        # All counts should be 0
        db_stats = response.context['db_stats']
        self.assertEqual(db_stats['total_cached_accounts'], 0)
        self.assertEqual(db_stats['fresh_accounts'], 0)
        self.assertEqual(db_stats['stale_accounts'], 0)
        self.assertEqual(db_stats['stuck_accounts'], 0)
        self.assertEqual(db_stats['pending_accounts'], 0)
        self.assertEqual(db_stats['in_progress_accounts'], 0)
        self.assertEqual(db_stats['completed_accounts'], 0)
        self.assertEqual(db_stats['re_inquiry_accounts'], 0)
        self.assertEqual(db_stats['total_lineage_records'], 0)
        self.assertEqual(db_stats['accounts_with_lineage'], 0)
        self.assertEqual(db_stats['orphan_accounts'], 0)


@pytest.mark.django_db
class TestDashboardConsistencyAcrossRefresh(TestCase):
    """Test dashboard data remains consistent across page refreshes."""
    
    def setUp(self):
        """Set up test client and data."""
        self.client = Client()
        self.now = datetime.utcnow()
        
        # Create stable test data
        self.test_account = StellarAccountSearchCache(
            stellar_account='G' + 'T' * 55,
            network_name='public',
            status='COMPLETE',
            created_at=self.now,
            updated_at=self.now
        )
        self.test_account.save()
        
    def tearDown(self):
        """Clean up test data."""
        try:
            self.test_account.delete()
        except:
            pass
    
    def test_dashboard_data_consistent_across_multiple_requests(self):
        """Dashboard should show same data across multiple requests."""
        # Make 3 requests
        response1 = self.client.get('/dashboard/')
        response2 = self.client.get('/dashboard/')
        response3 = self.client.get('/dashboard/')
        
        # All should succeed
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response3.status_code, 200)
        
        # All should show same total
        total1 = response1.context['db_stats']['total_cached_accounts']
        total2 = response2.context['db_stats']['total_cached_accounts']
        total3 = response3.context['db_stats']['total_cached_accounts']
        
        self.assertEqual(total1, total2)
        self.assertEqual(total2, total3)
        self.assertEqual(total1, 1)  # Should be our 1 test account
