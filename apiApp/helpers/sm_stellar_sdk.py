"""
Stellar SDK Pipeline Helper

Provides async wrapper around stellar-sdk for efficient concurrent account processing.
Uses native SDK features: async/await, pagination, streaming, and built-in error handling.

Key advantages over API pipeline:
- Concurrent processing of multiple accounts
- SDK-native pagination and filtering
- Zero cost (free Horizon API)
- Faster than sequential API pipeline
- Simpler than BigQuery pipeline
"""

import asyncio
import logging
import time
from collections import deque
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import sentry_sdk
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from stellar_sdk import ServerAsync
from stellar_sdk.exceptions import BaseHorizonError, NotFoundError, BadRequestError
from stellar_sdk.client.aiohttp_client import AiohttpClient

logger = logging.getLogger(__name__)


class SDKRateLimiter:
    """
    Client-side rate limiter for Stellar Horizon API.
    
    Horizon limits: 3600 requests/hour (~1 req/sec average)
    This implements a sliding window rate limiter with burst support.
    """
    
    def __init__(self, max_requests: int = 3500, time_window: int = 3600):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests in time window (default 3500, slightly under 3600 limit)
            time_window: Time window in seconds (default 3600 = 1 hour)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self._lock = asyncio.Lock()
    
    async def wait_if_needed(self):
        """
        Wait if we've hit the rate limit.
        Automatically removes old requests outside the time window.
        """
        async with self._lock:
            now = time.time()
            
            # Remove requests outside the time window
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()
            
            # Check if we're at the limit
            if len(self.requests) >= self.max_requests:
                wait_time = self.time_window - (now - self.requests[0])
                if wait_time > 0:
                    logger.warning(f"Rate limit reached. Waiting {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time + 0.1)
                    # Clean up after waiting
                    now = time.time()
                    while self.requests and self.requests[0] < now - self.time_window:
                        self.requests.popleft()
            
            # Record this request
            self.requests.append(now)
    
    def get_stats(self) -> Dict[str, int]:
        """Get current rate limiter statistics."""
        now = time.time()
        # Count valid requests in current window
        valid_requests = sum(1 for req_time in self.requests if req_time > now - self.time_window)
        return {
            'requests_in_window': valid_requests,
            'max_requests': self.max_requests,
            'remaining': max(0, self.max_requests - valid_requests)
        }


class StellarSDKHelper:
    """
    Async Stellar SDK helper for concurrent account processing.
    
    Features:
    - Async/await for concurrent operations
    - Built-in rate limiting
    - Automatic retries with exponential backoff
    - Creator and child account discovery
    - Account enrichment (balance, assets, flags)
    """
    
    def __init__(self, horizon_url: str, rate_limiter: Optional[SDKRateLimiter] = None):
        """
        Initialize SDK helper.
        
        Args:
            horizon_url: Horizon API endpoint URL
            rate_limiter: Optional rate limiter (creates default if None)
        """
        self.horizon_url = horizon_url
        self.rate_limiter = rate_limiter or SDKRateLimiter()
        self._session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = ServerAsync(
            horizon_url=self.horizon_url,
            client=AiohttpClient()
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
    
    @retry(
        retry=retry_if_exception_type((BaseHorizonError, asyncio.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def load_account(self, account_id: str) -> Optional[Dict]:
        """
        Load account data from Horizon.
        
        Args:
            account_id: Stellar account address
        
        Returns:
            Account data dict or None if not found
        """
        try:
            await self.rate_limiter.wait_if_needed()
            account = await self._session.load_account(account_id)
            
            # Account object has:
            # - account.account: The account ID string (NOT account_id!)
            # - account.sequence: The sequence number
            # - account.raw_data: Dict with full Horizon response (balances, flags, etc.)
            
            raw_data = account.raw_data or {}
            
            # Convert to dict format
            return {
                'id': account.account,  # Use account.account, NOT account.account_id
                'sequence': account.sequence,
                'balances': raw_data.get('balances', []),
                'home_domain': raw_data.get('home_domain', ''),
                'flags': raw_data.get('flags', {}),
                'thresholds': raw_data.get('thresholds', {}),
                'signers': raw_data.get('signers', []),
                'last_modified_time': raw_data.get('last_modified_time', ''),
                'subentry_count': raw_data.get('subentry_count', 0),
                'num_sponsoring': raw_data.get('num_sponsoring', 0),
                'num_sponsored': raw_data.get('num_sponsored', 0)
            }
        except NotFoundError:
            logger.info(f"Account not found: {account_id}")
            return None
        except BadRequestError as e:
            logger.error(f"Bad request for account {account_id}: {e}")
            sentry_sdk.capture_exception(e)
            return None
        except Exception as e:
            logger.error(f"Error loading account {account_id}: {e}")
            sentry_sdk.capture_exception(e)
            raise
    
    @retry(
        retry=retry_if_exception_type((BaseHorizonError, asyncio.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def get_operations(
        self,
        account_id: str,
        limit: int = 200,
        order: str = 'asc',
        cursor: Optional[str] = None
    ) -> Dict:
        """
        Get operations for an account.
        
        Args:
            account_id: Stellar account address
            limit: Max operations to fetch (default 200, max per request)
            order: 'asc' for oldest first, 'desc' for newest first
            cursor: Pagination cursor
        
        Returns:
            Operations response dict
        """
        try:
            await self.rate_limiter.wait_if_needed()
            
            query = self._session.operations().for_account(account_id)
            query = query.order(desc=(order == 'desc'))
            query = query.limit(limit)
            
            if cursor:
                query = query.cursor(cursor)
            
            response = await query.call()
            return response
            
        except NotFoundError:
            logger.info(f"No operations found for account: {account_id}")
            return {'_embedded': {'records': []}}
        except Exception as e:
            logger.error(f"Error fetching operations for {account_id}: {e}")
            sentry_sdk.capture_exception(e)
            raise
    
    async def discover_creator(self, account_id: str, max_operations: int = 200) -> Optional[Tuple[str, datetime]]:
        """
        Discover who created this account.
        
        Searches operations in ascending order (oldest first) for the create_account
        operation where this account was the destination.
        
        Args:
            account_id: Account to find creator for
            max_operations: Maximum operations to check (default 200)
        
        Returns:
            Tuple of (creator_account, created_at) or None if not found
        """
        try:
            # Get oldest operations first (ascending order)
            response = await self.get_operations(
                account_id=account_id,
                limit=max_operations,
                order='asc'
            )
            
            records = response.get('_embedded', {}).get('records', [])
            
            # Find create_account operation
            for op in records:
                if op.get('type') == 'create_account' and op.get('account') == account_id:
                    creator = op.get('funder') or op.get('source_account')
                    created_at_str = op.get('created_at', '')
                    
                    if creator and created_at_str:
                        # Parse datetime
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        return (creator, created_at)
            
            logger.info(f"No creator found for {account_id} in {len(records)} operations")
            return None
            
        except Exception as e:
            logger.error(f"Error discovering creator for {account_id}: {e}")
            sentry_sdk.capture_exception(e)
            return None
    
    async def discover_children(
        self,
        account_id: str,
        max_pages: int = 5,
        limit_per_page: int = 200
    ) -> List[Dict]:
        """
        Discover all accounts created by this account (children).
        
        Searches operations in ascending order and filters for create_account
        operations where this account was the funder.
        
        Args:
            account_id: Account to find children for
            max_pages: Maximum pages to fetch (default 5 = 1000 operations)
            limit_per_page: Operations per page (default 200, max)
        
        Returns:
            List of child account dicts with account, starting_balance, created_at
        """
        try:
            children = []
            cursor = None
            pages_fetched = 0
            
            while pages_fetched < max_pages:
                response = await self.get_operations(
                    account_id=account_id,
                    limit=limit_per_page,
                    order='asc',
                    cursor=cursor
                )
                
                records = response.get('_embedded', {}).get('records', [])
                
                if not records:
                    break
                
                # Filter for create_account operations where this account is the funder
                for op in records:
                    if op.get('type') == 'create_account':
                        # Check if this account was the funder/source
                        funder = op.get('funder') or op.get('source_account')
                        if funder == account_id:
                            created_account = op.get('account')
                            if created_account:
                                children.append({
                                    'account': created_account,
                                    'starting_balance': op.get('starting_balance', '0'),
                                    'created_at': op.get('created_at', '')
                                })
                
                # Get cursor for next page
                cursor = records[-1].get('paging_token') if records else None
                pages_fetched += 1
                
                # If we got fewer records than requested, we've reached the end
                if len(records) < limit_per_page:
                    break
            
            logger.info(f"Found {len(children)} child accounts for {account_id} (scanned {pages_fetched} pages)")
            return children
            
        except Exception as e:
            logger.error(f"Error discovering children for {account_id}: {e}")
            sentry_sdk.capture_exception(e)
            return []
    
    async def enrich_account(self, account_id: str) -> Optional[Dict]:
        """
        Enrich account with full data: balance, assets, flags, creator, children.
        
        This is the main method that gathers all account data in one call.
        
        Args:
            account_id: Account to enrich
        
        Returns:
            Enriched account data dict or None if account not found
        """
        try:
            # Load basic account data
            account_data = await self.load_account(account_id)
            
            if not account_data:
                return None
            
            # Discover creator and children concurrently
            creator_task = self.discover_creator(account_id)
            children_task = self.discover_children(account_id)
            
            creator_result, children_result = await asyncio.gather(
                creator_task,
                children_task,
                return_exceptions=True
            )
            
            # Handle results
            creator_account = None
            created_at = None
            if isinstance(creator_result, tuple):
                creator_account, created_at = creator_result
            
            children = children_result if isinstance(children_result, list) else []
            
            # Extract XLM balance
            xlm_balance = 0.0
            for bal in account_data.get('balances', []):
                if bal.get('asset_type') == 'native':
                    xlm_balance = float(bal.get('balance', 0.0))
                    break
            
            # Build enriched result
            return {
                'account_id': account_id,
                'xlm_balance': xlm_balance,
                'home_domain': account_data.get('home_domain', ''),
                'creator_account': creator_account,
                'created_at': created_at,
                'children': children,
                'num_children': len(children),
                'balances': account_data.get('balances', []),
                'flags': account_data.get('flags', {}),
                'thresholds': account_data.get('thresholds', {}),
                'signers': account_data.get('signers', [])
            }
            
        except Exception as e:
            logger.error(f"Error enriching account {account_id}: {e}")
            sentry_sdk.capture_exception(e)
            return None
    
    async def process_accounts_batch(
        self,
        account_ids: List[str],
        max_concurrent: int = 5
    ) -> List[Dict]:
        """
        Process multiple accounts concurrently with concurrency limit.
        
        Args:
            account_ids: List of accounts to process
            max_concurrent: Maximum concurrent requests (default 5)
        
        Returns:
            List of enriched account data dicts
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_limit(account_id: str):
            async with semaphore:
                return await self.enrich_account(account_id)
        
        tasks = [process_with_limit(aid) for aid in account_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None and exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to process {account_ids[i]}: {result}")
                sentry_sdk.capture_exception(result)
            elif result is not None:
                valid_results.append(result)
        
        return valid_results
