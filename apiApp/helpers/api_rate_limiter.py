"""
API Rate Limiter - Ensures slow, continuous API access without hitting rate limits.

Implements configurable delays between API calls to prevent rate limiting from:
- Horizon API
- Stellar Expert API
- BigQuery API

IMPORTANT: Metrics are stored in Django cache (cross-process) so the dashboard can display them.

Usage:
    from apiApp.helpers.api_rate_limiter import APIRateLimiter
    
    limiter = APIRateLimiter()
    limiter.wait_for_horizon()  # Waits if needed before making Horizon API call
    limiter.wait_for_stellar_expert()  # Waits if needed before making Stellar Expert call
"""

import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class APIRateLimiter:
    """
    Smart rate limiter that ensures continuous slow retrieval without hitting API limits.
    
    Default Limits (conservative to prevent rate limiting):
    - Horizon API: 1 request per 0.5 seconds (120 req/min, well under their limits)
    - Stellar Expert: 1 request per 1 second (60 req/min, safe for free tier)
    - BigQuery: No rate limiting (cost-based controls handled elsewhere)
    
    CROSS-PROCESS: Uses Django cache backend to share metrics across processes
    (e.g., management commands and web server) so dashboard can display real-time data.
    """
    
    # Cache key prefixes for cross-process storage
    CACHE_PREFIX_LAST_CALL = 'api_limiter_last_call_'
    CACHE_PREFIX_CALL_COUNT = 'api_limiter_call_count_'
    CACHE_PREFIX_RESET_TIME = 'api_limiter_reset_time_'
    CACHE_TTL = 120  # 2 minutes (must be longer than reset window)
    
    # Rate limit configurations (seconds between calls)
    RATE_LIMITS = {
        'horizon': 0.5,          # 120 requests/minute (Horizon limit is 3600/hour)
        'stellar_expert': 1.0,   # 60 requests/minute (conservative for free tier)
        'bigquery': 0.0,         # No delay (cost-based controls elsewhere)
    }
    
    # Burst allowances (requests per minute)
    BURST_LIMITS = {
        'horizon': 120,
        'stellar_expert': 50,
        'bigquery': 1000,
    }
    
    def __init__(self, enable_logging: bool = False):
        """Initialize rate limiter with optional logging."""
        self.enable_logging = enable_logging
    
    def wait_for_horizon(self) -> float:
        """
        Wait if necessary before making a Horizon API call.
        Returns the wait time in seconds.
        """
        return self._wait_if_needed('horizon')
    
    def wait_for_stellar_expert(self) -> float:
        """
        Wait if necessary before making a Stellar Expert API call.
        Returns the wait time in seconds.
        """
        return self._wait_if_needed('stellar_expert')
    
    def wait_for_bigquery(self) -> float:
        """
        Wait if necessary before making a BigQuery API call.
        Returns the wait time in seconds (typically 0).
        """
        return self._wait_if_needed('bigquery')
    
    def _wait_if_needed(self, api_name: str) -> float:
        """
        Core rate limiting logic - wait if needed to respect rate limits.
        Uses Django cache for cross-process coordination.
        
        Args:
            api_name: API identifier ('horizon', 'stellar_expert', 'bigquery')
            
        Returns:
            float: Actual wait time in seconds
        """
        now = datetime.now(timezone.utc)
        delay = self.RATE_LIMITS.get(api_name, 1.0)
        
        # Cache keys
        last_call_key = f'{self.CACHE_PREFIX_LAST_CALL}{api_name}'
        call_count_key = f'{self.CACHE_PREFIX_CALL_COUNT}{api_name}'
        reset_time_key = f'{self.CACHE_PREFIX_RESET_TIME}{api_name}'
        
        # Get or initialize tracking from cache
        last_call = cache.get(last_call_key)
        call_count = cache.get(call_count_key, 0)
        reset_time = cache.get(reset_time_key)
        
        if not last_call or not reset_time:
            # First call - initialize
            cache.set(last_call_key, now.isoformat(), self.CACHE_TTL)
            cache.set(call_count_key, 0, self.CACHE_TTL)
            cache.set(reset_time_key, (now + timedelta(minutes=1)).isoformat(), self.CACHE_TTL)
            return 0.0
        
        # Parse datetime strings from cache
        last_call_dt = datetime.fromisoformat(last_call)
        reset_time_dt = datetime.fromisoformat(reset_time)
        
        # Reset counters every minute
        if now >= reset_time_dt:
            call_count = 0
            reset_time_dt = now + timedelta(minutes=1)
            cache.set(call_count_key, 0, self.CACHE_TTL)
            cache.set(reset_time_key, reset_time_dt.isoformat(), self.CACHE_TTL)
        
        # Check if we've exceeded burst limit
        burst_limit = self.BURST_LIMITS.get(api_name, 100)
        if call_count >= burst_limit:
            # Wait until reset time
            wait_time = (reset_time_dt - now).total_seconds()
            if wait_time > 0:
                if self.enable_logging:
                    logger.warning(f'Rate limit reached for {api_name} - waiting {wait_time:.2f}s')
                time.sleep(wait_time)
                # Reset counters after wait
                now = datetime.now(timezone.utc)
                cache.set(call_count_key, 0, self.CACHE_TTL)
                cache.set(reset_time_key, (now + timedelta(minutes=1)).isoformat(), self.CACHE_TTL)
                cache.set(last_call_key, now.isoformat(), self.CACHE_TTL)
                return wait_time
        
        # Calculate time since last call
        time_since_last = (now - last_call_dt).total_seconds()
        
        # Wait if needed to maintain rate limit
        if time_since_last < delay:
            wait_time = delay - time_since_last
            if self.enable_logging and wait_time > 0.1:
                logger.debug(f'Rate limiting {api_name}: waiting {wait_time:.2f}s')
            time.sleep(wait_time)
            now = datetime.now(timezone.utc)
            cache.set(last_call_key, now.isoformat(), self.CACHE_TTL)
            cache.set(call_count_key, call_count + 1, self.CACHE_TTL)
            return wait_time
        
        # No wait needed
        cache.set(last_call_key, now.isoformat(), self.CACHE_TTL)
        cache.set(call_count_key, call_count + 1, self.CACHE_TTL)
        return 0.0
    
    def get_stats(self) -> Dict[str, Dict]:
        """
        Get current rate limiting statistics for all APIs.
        Reads from Django cache (cross-process compatible).
        
        Returns:
            Dict with stats for each API including call counts and last call times.
        """
        now = datetime.now(timezone.utc)
        stats = {}
        
        for api_name in ['horizon', 'stellar_expert', 'bigquery']:
            # Cache keys
            last_call_key = f'{self.CACHE_PREFIX_LAST_CALL}{api_name}'
            call_count_key = f'{self.CACHE_PREFIX_CALL_COUNT}{api_name}'
            reset_time_key = f'{self.CACHE_PREFIX_RESET_TIME}{api_name}'
            
            # Get from cache
            last_call_str = cache.get(last_call_key)
            call_count = cache.get(call_count_key, 0)
            reset_time_str = cache.get(reset_time_key)
            
            # Parse datetimes
            last_call_dt = None
            seconds_since_last = None
            if last_call_str:
                try:
                    last_call_dt = datetime.fromisoformat(last_call_str)
                    seconds_since_last = (now - last_call_dt).total_seconds()
                except:
                    pass
            
            stats[api_name] = {
                'calls_this_minute': call_count,
                'burst_limit': self.BURST_LIMITS[api_name],
                'rate_limit_delay': self.RATE_LIMITS[api_name],
                'last_call': last_call_str,
                'seconds_since_last_call': seconds_since_last,
                'reset_time': reset_time_str or (now + timedelta(minutes=1)).isoformat(),
            }
        
        return stats
    
    @classmethod
    def reset_all(cls):
        """Reset all rate limiting state (useful for testing). Clears Django cache."""
        for api_name in ['horizon', 'stellar_expert', 'bigquery']:
            cache.delete(f'{cls.CACHE_PREFIX_LAST_CALL}{api_name}')
            cache.delete(f'{cls.CACHE_PREFIX_CALL_COUNT}{api_name}')
            cache.delete(f'{cls.CACHE_PREFIX_RESET_TIME}{api_name}')
