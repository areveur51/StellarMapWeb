# apiApp/helpers/sm_cache.py
import datetime
import json
from apiApp.models import (
    StellarAccountSearchCache, 
    StellarCreatorAccountLineage,
    PENDING,
    PROCESSING,
    COMPLETE,
    BIGQUERY_COMPLETE,
)


class StellarMapCacheHelpers:
    """
    Simplified helper class for managing 12-hour Cassandra cache.
    """
    
    CACHE_FRESHNESS_HOURS = 12
    
    def check_cache_freshness(self, stellar_account, network_name):
        """
        Check if cached data exists and is fresh (< 12 hours old).
        
        Returns:
            tuple: (is_fresh: bool, cache_entry: StellarAccountSearchCache or None)
        """
        try:
            cache_entry = StellarAccountSearchCache.objects.get(
                stellar_account=stellar_account,
                network_name=network_name
            )
            
            if cache_entry.last_fetched_at:
                time_since_fetch = datetime.datetime.utcnow() - cache_entry.last_fetched_at
                hours_since_fetch = time_since_fetch.total_seconds() / 3600
                
                is_fresh = hours_since_fetch < self.CACHE_FRESHNESS_HOURS
                return is_fresh, cache_entry
            
            return False, cache_entry
            
        except StellarAccountSearchCache.DoesNotExist:
            return False, None
    
    def get_cached_data(self, cache_entry):
        """
        Get cached JSON data from cache entry.
        
        Returns:
            dict: Parsed tree_data JSON or None
        """
        if cache_entry and cache_entry.cached_json:
            try:
                return json.loads(cache_entry.cached_json)
            except json.JSONDecodeError:
                return None
        return None
    
    def update_cache(self, stellar_account, network_name, tree_data, status=COMPLETE):
        """
        Update cache with fresh tree data.
        
        Returns:
            StellarAccountSearchCache: Updated cache entry
        """
        try:
            cache_entry = StellarAccountSearchCache.objects.get(
                stellar_account=stellar_account,
                network_name=network_name
            )
            cache_entry.cached_json = json.dumps(tree_data)
            cache_entry.last_fetched_at = datetime.datetime.utcnow()
            cache_entry.status = status
            cache_entry.save()
            return cache_entry
            
        except StellarAccountSearchCache.DoesNotExist:
            cache_entry = StellarAccountSearchCache.objects.create(
                stellar_account=stellar_account,
                network_name=network_name,
                cached_json=json.dumps(tree_data),
                last_fetched_at=datetime.datetime.utcnow(),
                status=status,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            return cache_entry
    
    def create_pending_entry(self, stellar_account, network_name):
        """
        Create or update entry with PENDING status to trigger BigQuery pipeline.
        
        Creates entries in BOTH tables:
        1. StellarAccountSearchCache (for web UI cache tracking)
        2. StellarCreatorAccountLineage (for BigQuery pipeline processing)
        
        If pipeline is already running (PENDING or PROCESSING), does nothing.
        
        Returns:
            StellarAccountSearchCache: Cache entry
        """
        # Create or update cache entry
        try:
            cache_entry = StellarAccountSearchCache.objects.get(
                stellar_account=stellar_account,
                network_name=network_name
            )
            
            # Don't reset if already running
            if cache_entry.status in [PENDING, PROCESSING]:
                return cache_entry
            
            # Set to PENDING if in terminal state
            cache_entry.status = PENDING
            cache_entry.updated_at = datetime.datetime.utcnow()
            cache_entry.save()
            
        except StellarAccountSearchCache.DoesNotExist:
            cache_entry = StellarAccountSearchCache.objects.create(
                stellar_account=stellar_account,
                network_name=network_name,
                status=PENDING,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
        
        # Create or update lineage entry for BigQuery pipeline
        try:
            lineage_entry = StellarCreatorAccountLineage.objects.get(
                stellar_account=stellar_account,
                network_name=network_name
            )
            
            # Only reset to PENDING if in terminal state
            if lineage_entry.status in [BIGQUERY_COMPLETE, COMPLETE, 'FAILED', 'INVALID']:
                lineage_entry.status = PENDING
                lineage_entry.updated_at = datetime.datetime.utcnow()
                lineage_entry.save()
                
        except StellarCreatorAccountLineage.DoesNotExist:
            StellarCreatorAccountLineage.objects.create(
                stellar_account=stellar_account,
                network_name=network_name,
                status=PENDING,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
        
        return cache_entry
