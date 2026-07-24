# apiApp/helpers/sm_cache.py
import datetime
import json
from apiApp.helpers.sm_datetime import utc_now, ensure_aware, age_seconds
from apiApp.model_loader import (
    StellarAccountSearchCache, 
    StellarCreatorAccountLineage,
    PENDING,
    PROCESSING,
    COMPLETE,
    BIGQUERY_COMPLETE,
    USE_CASSANDRA,
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
                hours_since_fetch = age_seconds(cache_entry.last_fetched_at) / 3600
                
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
        Update cache with fresh tree / projection data.

        Always stores **valid JSON** via ``json.dumps`` (never ``str(dict)``).
        Sets ``last_fetched_at`` because a full display body was written.

        Args:
            tree_data: dict (legacy D3 tree or schema_version projection) or
                a JSON string already produced with json.dumps.
        """
        if isinstance(tree_data, str):
            # Validate string is JSON; reject Python repr bodies
            try:
                json.loads(tree_data)
            except (json.JSONDecodeError, TypeError) as e:
                raise ValueError(
                    "update_cache requires valid JSON string or dict body"
                ) from e
            body = tree_data
        else:
            body = json.dumps(tree_data)

        try:
            cache_entry = StellarAccountSearchCache.objects.get(
                stellar_account=stellar_account,
                network_name=network_name
            )
            cache_entry.cached_json = body
            cache_entry.last_fetched_at = utc_now()
            cache_entry.status = status
            cache_entry.save()
            return cache_entry
            
        except StellarAccountSearchCache.DoesNotExist:
            cache_entry = StellarAccountSearchCache.objects.create(
                stellar_account=stellar_account,
                network_name=network_name,
                cached_json=body,
                last_fetched_at=utc_now(),
                status=status,
                created_at=utc_now(),
                updated_at=utc_now()
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
            cache_entry.updated_at = utc_now()
            cache_entry.save()
            
        except StellarAccountSearchCache.DoesNotExist:
            cache_entry = StellarAccountSearchCache.objects.create(
                stellar_account=stellar_account,
                network_name=network_name,
                status=PENDING,
                created_at=utc_now(),
                updated_at=utc_now()
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
                lineage_entry.updated_at = utc_now()
                lineage_entry.save()
                
        except StellarCreatorAccountLineage.DoesNotExist:
            StellarCreatorAccountLineage.objects.create(
                stellar_account=stellar_account,
                network_name=network_name,
                status=PENDING,
                created_at=utc_now(),
                updated_at=utc_now()
            )
        
        return cache_entry
