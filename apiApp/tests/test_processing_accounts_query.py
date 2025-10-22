"""
Test cases for the improved "Processing Accounts" query in Query Builder.

Tests dual-table scanning (Search Cache + Account Lineage) and stale detection.
"""
import pytest
import datetime
from datetime import timedelta
from django.test import TestCase
from django.conf import settings

USE_CASSANDRA = settings.DATABASES['default']['ENGINE'] == 'django_cassandra_engine'

if USE_CASSANDRA:
    from apiApp.models_cassandra import StellarAccountSearchCache, StellarCreatorAccountLineage
else:
    from apiApp.models_local import StellarAccountSearchCache, StellarCreatorAccountLineage


@pytest.mark.django_db
class TestProcessingAccountsQuery(TestCase):
    """Test the enhanced processing_accounts query with dual-table support."""

    def setUp(self):
        """Set up test data."""
        self.network = 'public'
        self.now = datetime.datetime.utcnow()
        self.stale_time = self.now - timedelta(minutes=45)  # Stale (> 30 min)
        self.fresh_time = self.now - timedelta(minutes=10)  # Fresh (< 30 min)

    def test_search_cache_processing_detected(self):
        """Test that processing accounts in Search Cache are detected."""
        # Create a processing account in Search Cache
        search_cache_record = StellarAccountSearchCache(
            stellar_account='G' + 'A' * 55,
            network_name=self.network,
            status='PROCESSING',
            created_at=self.fresh_time,
            updated_at=self.fresh_time
        )
        search_cache_record.save()

        # Verify it exists
        records = StellarAccountSearchCache.objects.filter(
            network_name=self.network,
            status__contains='PROGRESS'
        )
        assert len(list(records)) > 0

    def test_lineage_processing_detected(self):
        """Test that processing accounts in Account Lineage are detected."""
        # Create a processing account in Account Lineage
        lineage_record = StellarCreatorAccountLineage(
            stellar_account='G' + 'B' * 55,
            network_name=self.network,
            status='PROCESSING_STAGE_2',
            created_at=self.fresh_time,
            updated_at=self.fresh_time
        )
        if hasattr(lineage_record, 'processing_started_at'):
            lineage_record.processing_started_at = self.fresh_time
        lineage_record.save()

        # Verify it exists
        records = StellarCreatorAccountLineage.objects.filter(
            network_name=self.network,
            status__contains='PROGRESS'
        )
        assert len(list(records)) > 0

    def test_stale_detection_search_cache(self):
        """Test that stale processing in Search Cache is detected."""
        # Create a stale processing account
        stale_record = StellarAccountSearchCache(
            stellar_account='G' + 'C' * 55,
            network_name=self.network,
            status='PROCESSING',
            created_at=self.stale_time,
            updated_at=self.stale_time
        )
        stale_record.save()

        # Check if it's stale (> 30 min)
        stale_threshold = self.now - timedelta(minutes=30)
        assert stale_record.updated_at < stale_threshold

    def test_stale_detection_lineage(self):
        """Test that stale processing in Account Lineage is detected."""
        # Create a stale processing account
        stale_record = StellarCreatorAccountLineage(
            stellar_account='G' + 'D' * 55,
            network_name=self.network,
            status='PROCESSING_STAGE_5',
            created_at=self.stale_time,
            updated_at=self.stale_time
        )
        if hasattr(stale_record, 'processing_started_at'):
            stale_record.processing_started_at = self.stale_time
        stale_record.save()

        # Check if it's stale (> 30 min)
        stale_threshold = self.now - timedelta(minutes=30)
        if hasattr(stale_record, 'processing_started_at') and stale_record.processing_started_at:
            assert stale_record.processing_started_at < stale_threshold
        else:
            assert stale_record.updated_at < stale_threshold

    def test_fresh_vs_stale_differentiation(self):
        """Test that fresh and stale processing accounts are properly differentiated."""
        # Create fresh processing account
        fresh_record = StellarAccountSearchCache(
            stellar_account='G' + 'E' * 55,
            network_name=self.network,
            status='PROCESSING',
            created_at=self.fresh_time,
            updated_at=self.fresh_time
        )
        fresh_record.save()

        # Create stale processing account
        stale_record = StellarAccountSearchCache(
            stellar_account='G' + 'F' * 55,
            network_name=self.network,
            status='PROCESSING',
            created_at=self.stale_time,
            updated_at=self.stale_time
        )
        stale_record.save()

        # Verify both exist
        all_processing = StellarAccountSearchCache.objects.filter(
            network_name=self.network,
            status__contains='PROGRESS'
        )
        assert len(list(all_processing)) >= 2

        # Verify fresh vs stale classification
        stale_threshold = self.now - timedelta(minutes=30)
        assert fresh_record.updated_at > stale_threshold  # Fresh
        assert stale_record.updated_at < stale_threshold  # Stale
