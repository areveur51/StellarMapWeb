# apiApp/helpers/sm_cache.py
import datetime
import json
from apiApp.models import StellarAccountSearchCache, PENDING_MAKE_PARENT_LINEAGE, DONE_MAKE_PARENT_LINEAGE


class StellarMapCacheHelpers:
    """
    Helper class for managing 12-hour Cassandra cache for Stellar account searches.
    
    Implements efficient caching strategy:
    - Check for fresh data (< 12 hours)
    - Return cached JSON if available
    - Create PENDING entry to trigger cron jobs if stale/missing
    """
    
    CACHE_FRESHNESS_HOURS = 12
    
    def check_cache_freshness(self, stellar_account, network):
        """
        Check if cached data exists and is fresh (< 12 hours old).
        
        Args:
            stellar_account (str): Stellar account address
            network (str): Network name (public/testnet)
            
        Returns:
            tuple: (is_fresh: bool, cache_entry: StellarAccountSearchCache or None)
        """
        try:
            cache_entry = StellarAccountSearchCache.objects.get(
                stellar_account=stellar_account,
                network=network
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
        
        Args:
            cache_entry (StellarAccountSearchCache): Cache entry object
            
        Returns:
            dict: Parsed tree_data JSON or None if not available
        """
        if cache_entry and cache_entry.cached_json:
            try:
                return json.loads(cache_entry.cached_json)
            except json.JSONDecodeError:
                return None
        return None
    
    def update_cache(self, stellar_account, network, tree_data, status=DONE_MAKE_PARENT_LINEAGE):
        """
        Update cache with fresh tree data after cron job completion.
        
        Args:
            stellar_account (str): Stellar account address
            network (str): Network name (public/testnet)
            tree_data (dict): Tree data to cache
            status (str): Workflow status (default: DONE_MAKE_PARENT_LINEAGE)
            
        Returns:
            StellarAccountSearchCache: Updated cache entry
        """
        try:
            cache_entry = StellarAccountSearchCache.objects.get(
                stellar_account=stellar_account,
                network=network
            )
            cache_entry.cached_json = json.dumps(tree_data)
            cache_entry.last_fetched_at = datetime.datetime.utcnow()
            cache_entry.status = status
            cache_entry.save()
            return cache_entry
            
        except StellarAccountSearchCache.DoesNotExist:
            cache_entry = StellarAccountSearchCache.objects.create(
                stellar_account=stellar_account,
                network=network,
                cached_json=json.dumps(tree_data),
                last_fetched_at=datetime.datetime.utcnow(),
                status=status,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            return cache_entry
    
    def create_pending_entry(self, stellar_account, network):
        """
        Create or update entry with PENDING_MAKE_PARENT_LINEAGE status to trigger cron job processing.
        
        This triggers the cron_make_parent_account_lineage workflow which will:
        1. Create StellarCreatorAccountLineage record with PENDING_HORIZON_API_DATASETS
        2. Process through complete PlantUML workflow
        3. Update cache with fresh data when complete
        
        Args:
            stellar_account (str): Stellar account address
            network (str): Network name (public/testnet)
            
        Returns:
            StellarAccountSearchCache: Cache entry set to PENDING
        """
        try:
            cache_entry = StellarAccountSearchCache.objects.get(
                stellar_account=stellar_account,
                network=network
            )
            cache_entry.status = PENDING_MAKE_PARENT_LINEAGE
            cache_entry.updated_at = datetime.datetime.utcnow()
            cache_entry.save()
            return cache_entry
            
        except StellarAccountSearchCache.DoesNotExist:
            cache_entry = StellarAccountSearchCache.objects.create(
                stellar_account=stellar_account,
                network=network,
                status=PENDING_MAKE_PARENT_LINEAGE,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            return cache_entry
