"""
BigQuery/Hubble Helper for Stellar Account Lineage Queries

This module provides functionality to query Stellar's BigQuery/Hubble dataset
for complete account creation relationships. This solves the limitation where
Horizon API pagination cannot reach historical create_account operations for
highly active accounts.

Dataset: crypto-stellar.crypto_stellar
Table: enriched_history_operations
"""

import os
import json
import logging
from typing import List, Dict, Optional
from google.cloud import bigquery
from google.oauth2 import service_account
import sentry_sdk

logger = logging.getLogger(__name__)


class BigQueryCostGuard:
    """
    Cost guard that validates query size before execution.
    Prevents queries over 100MB to avoid unexpected costs.
    """
    
    MAX_QUERY_SIZE_MB = 100
    MAX_QUERY_SIZE_BYTES = MAX_QUERY_SIZE_MB * 1024 * 1024  # 100 MB in bytes
    COST_PER_TB = 5.0  # $5 per TB scanned
    
    def __init__(self, client: bigquery.Client):
        self.client = client
    
    def validate_query_cost(self, query: str, job_config: bigquery.QueryJobConfig = None) -> Dict:
        """
        Perform a dry-run to estimate query cost and validate size limit.
        
        Args:
            query: SQL query to validate
            job_config: Optional query configuration
            
        Returns:
            Dict with:
                - bytes_processed: Estimated bytes to scan
                - size_mb: Size in MB
                - estimated_cost: Estimated cost in USD
                - is_valid: Whether query is under size limit
                
        Raises:
            ValueError: If query exceeds size limit
        """
        if not job_config:
            job_config = bigquery.QueryJobConfig()
        
        # Enable dry-run mode
        job_config.dry_run = True
        job_config.use_query_cache = False
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            
            bytes_processed = query_job.total_bytes_processed
            size_mb = bytes_processed / (1024 * 1024)
            estimated_cost = (bytes_processed / (1024**4)) * self.COST_PER_TB  # Convert to TB
            
            result = {
                'bytes_processed': bytes_processed,
                'size_mb': round(size_mb, 2),
                'estimated_cost': round(estimated_cost, 4),
                'is_valid': bytes_processed <= self.MAX_QUERY_SIZE_BYTES
            }
            
            logger.info(f"Query cost estimate: {size_mb:.2f} MB (${estimated_cost:.4f})")
            
            if not result['is_valid']:
                error_msg = (
                    f"Query exceeds size limit! "
                    f"Scans {size_mb:.2f} MB but limit is {self.MAX_QUERY_SIZE_MB} MB. "
                    f"Estimated cost: ${estimated_cost:.4f}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            return result
            
        except Exception as e:
            if "Query exceeds size limit" in str(e):
                raise
            logger.error(f"Error validating query cost: {e}")
            sentry_sdk.capture_exception(e)
            raise


class StellarBigQueryHelper:
    """
    Helper class for querying Stellar's BigQuery/Hubble dataset.
    """
    
    def __init__(self):
        """
        Initialize BigQuery client with service account credentials.
        Credentials should be stored in GOOGLE_APPLICATION_CREDENTIALS_JSON secret.
        """
        self.client = None
        self.cost_guard = None
        self._initialize_client()
    
    def _initialize_client(self):
        """
        Initialize the BigQuery client with authentication.
        """
        try:
            credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
            
            if not credentials_json:
                logger.warning("GOOGLE_APPLICATION_CREDENTIALS_JSON not found. BigQuery integration disabled.")
                return
            
            credentials_dict = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
            
            self.client = bigquery.Client(
                credentials=credentials,
                project=credentials_dict.get('project_id')
            )
            
            # Initialize cost guard
            self.cost_guard = BigQueryCostGuard(self.client)
            
            logger.info("BigQuery client and cost guard initialized successfully")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in GOOGLE_APPLICATION_CREDENTIALS_JSON: {e}")
            sentry_sdk.capture_exception(e)
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery client: {e}")
            sentry_sdk.capture_exception(e)
    
    def is_available(self) -> bool:
        """
        Check if BigQuery integration is available and configured.
        
        Returns:
            bool: True if BigQuery client is initialized
        """
        return self.client is not None
    
    def get_child_accounts(
        self, 
        parent_account: str,
        limit: int = 10000,
        offset: int = 0,
        start_date: str = '2015-01-01',
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch all accounts created by a specific parent account from BigQuery.
        
        This queries the Stellar Hubble dataset for create_account operations
        where the parent account is the funder.
        
        IMPORTANT: Always requires date range filters to avoid full table scans.
        
        Args:
            parent_account: The Stellar account address to query
            limit: Maximum number of child accounts to return (default 10000)
            offset: Number of results to skip for pagination (default 0)
            start_date: Start date for partition filter (YYYY-MM-DD), defaults to Stellar genesis
            end_date: End date for partition filter (YYYY-MM-DD), defaults to today
        
        Returns:
            List of dicts containing child account info:
            [
                {
                    'account': 'G...',
                    'starting_balance': '10.0000000',
                    'created_at': '2017-12-05T14:09:53Z',
                    'transaction_hash': 'abc123...',
                    'ledger_sequence': 12345
                },
                ...
            ]
        """
        if not self.is_available():
            logger.warning("BigQuery not available. Returning empty results.")
            return []
        
        if not end_date:
            from datetime import datetime
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        try:
            # MANDATORY: Add partition filters to avoid full table scan
            query = f"""
                SELECT 
                    account,
                    starting_balance,
                    closed_at as created_at,
                    transaction_hash,
                    ledger_sequence
                FROM `crypto-stellar.crypto_stellar_dbt.enriched_history_operations`
                WHERE type = 0
                  AND funder = @parent_account
                  AND closed_at >= TIMESTAMP(@start_date)
                  AND closed_at <= TIMESTAMP(@end_date)
                ORDER BY closed_at ASC
                LIMIT {limit}
                OFFSET {offset}
            """
            
            query_parameters = [
                bigquery.ScalarQueryParameter("parent_account", "STRING", parent_account),
                bigquery.ScalarQueryParameter("start_date", "STRING", f"{start_date}T00:00:00Z"),
                bigquery.ScalarQueryParameter("end_date", "STRING", f"{end_date}T23:59:59Z")
            ]
            
            job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
            
            # COST GUARD: Validate query size before execution
            logger.info(f"Validating query cost for child accounts of {parent_account} (date range: {start_date} to {end_date})")
            cost_info = self.cost_guard.validate_query_cost(query, job_config)
            logger.info(f"✅ Query approved: {cost_info['size_mb']} MB, ${cost_info['estimated_cost']}")
            
            # Execute query
            logger.info(f"Querying BigQuery for child accounts of {parent_account}")
            job_config.dry_run = False  # Re-enable actual execution
            query_job = self.client.query(query, job_config=job_config)
            
            results = []
            for row in query_job:
                results.append({
                    'account': row.account,
                    'starting_balance': row.starting_balance,
                    'created_at': row.created_at.isoformat() if row.created_at else None,
                    'transaction_hash': row.transaction_hash,
                    'ledger_sequence': row.ledger_sequence
                })
            
            logger.info(f"Found {len(results)} child accounts in BigQuery for {parent_account}")
            return results
            
        except Exception as e:
            logger.error(f"BigQuery query failed: {e}")
            sentry_sdk.capture_exception(e)
            return []
    
    def fetch_lineage_bundle(
        self,
        target_account: str,
        start_date: str = '2015-01-01',
        end_date: Optional[str] = None,
        max_children: int = 10000,
        offset: int = 0
    ) -> Dict:
        """
        **CONSOLIDATED QUERY**: Fetch creator, children, and issuers in a SINGLE BigQuery query.
        
        This replaces the old two-query approach (get_account_creator + get_child_accounts) with
        a single optimized CTE-based query that scans enriched_history_operations once.
        
        Benefits:
        - Reduces BigQuery costs (1 scan instead of 2)
        - Reduces transactions (1 query instead of 2)
        - Discovers issuers (accounts with issuer flag in lineage)
        - Maintains 100MB cost guard compliance with partition filters
        
        Args:
            target_account: The Stellar account to analyze
            start_date: Start date for partition filter (YYYY-MM-DD)
            end_date: End date for partition filter (YYYY-MM-DD), defaults to today
            max_children: Maximum child accounts to return (default 10000)
            offset: Pagination offset for child accounts (default 0)
        
        Returns:
            Dict containing:
            {
                'creator': {'creator_account': 'G...', 'created_at': '...'},
                'children': [{'account': 'G...', 'created_at': '...', ...}, ...],
                'issuers': [{'account': 'G...', 'flags': 1, 'home_domain': '...'}, ...],
                'pagination': {'total': 123, 'offset': 0, 'limit': 10000, 'has_more': True}
            }
        """
        if not self.is_available():
            logger.warning("BigQuery not available for lineage bundle query")
            return {
                'creator': None,
                'children': [],
                'issuers': [],
                'pagination': {'total': 0, 'offset': 0, 'limit': max_children, 'has_more': False}
            }
        
        if not end_date:
            from datetime import datetime
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        try:
            # CONSOLIDATED CTE QUERY: Single table scan for all lineage data
            query = """
                WITH filtered_ops AS (
                    -- Single partition-filtered scan of create_account operations
                    SELECT 
                        account,
                        funder,
                        starting_balance,
                        closed_at,
                        transaction_hash,
                        ledger_sequence
                    FROM `crypto-stellar.crypto_stellar_dbt.enriched_history_operations`
                    WHERE type = 0  -- create_account operations only
                      AND closed_at >= TIMESTAMP(@start_date)
                      AND closed_at <= TIMESTAMP(@end_date)
                      AND (account = @target_account OR funder = @target_account)
                ),
                creator_op AS (
                    -- Find who created the target account
                    SELECT 
                        funder as creator_account,
                        closed_at as created_at,
                        transaction_hash,
                        ledger_sequence
                    FROM filtered_ops 
                    WHERE account = @target_account
                    ORDER BY closed_at ASC
                    LIMIT 1
                ),
                child_ops_numbered AS (
                    -- Find accounts created by target (with row numbers for pagination)
                    SELECT 
                        account,
                        starting_balance,
                        closed_at as created_at,
                        transaction_hash,
                        ledger_sequence,
                        ROW_NUMBER() OVER (ORDER BY closed_at ASC) as row_num
                    FROM filtered_ops 
                    WHERE funder = @target_account
                ),
                child_ops_paginated AS (
                    -- Apply pagination
                    SELECT * FROM child_ops_numbered
                    WHERE row_num > @offset AND row_num <= @offset + @max_children
                ),
                child_count AS (
                    -- Count total children for pagination
                    SELECT COUNT(*) as total FROM child_ops_numbered
                ),
                lineage_accounts AS (
                    -- Collect all lineage accounts for issuer lookup
                    SELECT creator_account as account FROM creator_op
                    UNION DISTINCT
                    SELECT account FROM child_ops_paginated
                ),
                issuer_accounts AS (
                    -- Find which lineage accounts are issuers (have created assets)
                    SELECT DISTINCT
                        l.account,
                        a.flags,
                        a.home_domain
                    FROM lineage_accounts l
                    JOIN `crypto-stellar.crypto_stellar_dbt.accounts_current` a 
                        ON l.account = a.account_id
                    WHERE (a.flags & 1) = 1  -- Issuer flag bit
                )
                
                -- Return all results in structured format
                SELECT
                    'creator' as result_type,
                    creator_account as account,
                    created_at,
                    transaction_hash,
                    ledger_sequence,
                    NULL as starting_balance,
                    NULL as flags,
                    NULL as home_domain,
                    NULL as total_count
                FROM creator_op
                
                UNION ALL
                
                SELECT
                    'child' as result_type,
                    account,
                    created_at,
                    transaction_hash,
                    ledger_sequence,
                    starting_balance,
                    NULL as flags,
                    NULL as home_domain,
                    NULL as total_count
                FROM child_ops_paginated
                
                UNION ALL
                
                SELECT
                    'issuer' as result_type,
                    account,
                    NULL as created_at,
                    NULL as transaction_hash,
                    NULL as ledger_sequence,
                    NULL as starting_balance,
                    flags,
                    home_domain,
                    NULL as total_count
                FROM issuer_accounts
                
                UNION ALL
                
                SELECT
                    'count' as result_type,
                    NULL as account,
                    NULL as created_at,
                    NULL as transaction_hash,
                    NULL as ledger_sequence,
                    NULL as starting_balance,
                    NULL as flags,
                    NULL as home_domain,
                    total as total_count
                FROM child_count
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("target_account", "STRING", target_account),
                    bigquery.ScalarQueryParameter("start_date", "STRING", f"{start_date}T00:00:00Z"),
                    bigquery.ScalarQueryParameter("end_date", "STRING", f"{end_date}T23:59:59Z"),
                    bigquery.ScalarQueryParameter("max_children", "INT64", max_children),
                    bigquery.ScalarQueryParameter("offset", "INT64", offset)
                ]
            )
            
            # COST GUARD: Validate consolidated query size
            logger.info(f"🔍 Validating CONSOLIDATED lineage query for {target_account} (date range: {start_date} to {end_date})")
            cost_info = self.cost_guard.validate_query_cost(query, job_config)
            logger.info(f"✅ Consolidated query approved: {cost_info['size_mb']} MB, ${cost_info['estimated_cost']}")
            
            # Execute consolidated query
            logger.info(f"🚀 Executing CONSOLIDATED lineage query for {target_account}")
            job_config.dry_run = False
            query_job = self.client.query(query, job_config=job_config)
            
            # Parse consolidated results
            creator = None
            children = []
            issuers = []
            total_children = 0
            
            for row in query_job:
                if row.result_type == 'creator':
                    creator = {
                        'creator_account': row.account,
                        'created_at': row.created_at.isoformat() if row.created_at else None,
                        'transaction_hash': row.transaction_hash,
                        'ledger_sequence': row.ledger_sequence
                    }
                elif row.result_type == 'child':
                    children.append({
                        'account': row.account,
                        'starting_balance': row.starting_balance,
                        'created_at': row.created_at.isoformat() if row.created_at else None,
                        'transaction_hash': row.transaction_hash,
                        'ledger_sequence': row.ledger_sequence
                    })
                elif row.result_type == 'issuer':
                    issuers.append({
                        'account': row.account,
                        'flags': row.flags,
                        'home_domain': row.home_domain
                    })
                elif row.result_type == 'count':
                    total_children = row.total_count or 0
            
            has_more = (offset + len(children)) < total_children
            
            logger.info(f"✅ Consolidated query complete: creator={bool(creator)}, children={len(children)}/{total_children}, issuers={len(issuers)}")
            
            return {
                'creator': creator,
                'children': children,
                'issuers': issuers,
                'pagination': {
                    'total': total_children,
                    'offset': offset,
                    'limit': max_children,
                    'has_more': has_more
                }
            }
            
        except Exception as e:
            logger.error(f"Consolidated lineage query failed for {target_account}: {e}")
            sentry_sdk.capture_exception(e)
            return {
                'creator': None,
                'children': [],
                'issuers': [],
                'pagination': {'total': 0, 'offset': 0, 'limit': max_children, 'has_more': False}
            }
    
    def get_account_creator(
        self, 
        account: str,
        start_date: str = '2015-01-01',
        end_date: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Find the creator (funder) of a specific account using BigQuery.
        
        This is useful as a fallback when Horizon operations are too deep
        or when the account was created through non-standard methods.
        
        IMPORTANT: Always requires date range filters to avoid full table scans.
        
        Args:
            account: The Stellar account address to query
            start_date: Start date for partition filter (YYYY-MM-DD), defaults to Stellar genesis
            end_date: End date for partition filter (YYYY-MM-DD), defaults to today
        
        Returns:
            Dict containing creator info:
            {
                'creator_account': 'G...',
                'created_at': '2017-12-05T14:09:53Z'
            }
            or None if not found
        """
        if not self.is_available():
            logger.warning("BigQuery not available. Returning None.")
            return None
        
        if not end_date:
            from datetime import datetime
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        try:
            # MANDATORY: Add partition filters to avoid full table scan
            query = """
                SELECT 
                    funder as creator,
                    closed_at as created_at
                FROM `crypto-stellar.crypto_stellar_dbt.enriched_history_operations`
                WHERE type = 0
                  AND account = @account
                  AND closed_at >= TIMESTAMP(@start_date)
                  AND closed_at <= TIMESTAMP(@end_date)
                ORDER BY closed_at ASC
                LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("account", "STRING", account),
                    bigquery.ScalarQueryParameter("start_date", "STRING", f"{start_date}T00:00:00Z"),
                    bigquery.ScalarQueryParameter("end_date", "STRING", f"{end_date}T23:59:59Z")
                ]
            )
            
            # COST GUARD: Validate query size before execution
            logger.info(f"Validating query cost for creator of {account} (date range: {start_date} to {end_date})")
            cost_info = self.cost_guard.validate_query_cost(query, job_config)
            logger.info(f"✅ Query approved: {cost_info['size_mb']} MB, ${cost_info['estimated_cost']}")
            
            # Execute query
            logger.info(f"Querying BigQuery for creator of {account}")
            job_config.dry_run = False  # Re-enable actual execution
            query_job = self.client.query(query, job_config=job_config)
            
            for row in query_job:
                result = {
                    'creator_account': row.creator,
                    'created_at': row.created_at.isoformat() if row.created_at else None
                }
                logger.info(f"Found creator {result['creator_account']} for {account} in BigQuery")
                return result
            
            logger.info(f"No creator found in BigQuery for {account}")
            return None
            
        except Exception as e:
            logger.error(f"BigQuery query failed: {e}")
            sentry_sdk.capture_exception(e)
            return None
    
    def get_account_data(self, account: str) -> Optional[Dict]:
        """
        Get minimal account lineage data from BigQuery (account ID and creation date only).
        
        All other account details (balance, flags, home_domain, assets, etc.) should be
        retrieved from Stellar Expert or Horizon APIs to minimize BigQuery usage.
        
        Args:
            account: The Stellar account address to query
        
        Returns:
            Dict containing minimal account data for lineage tracking:
            {
                'account_id': 'G...',
                'account_creation_date': '2017-12-05T14:09:53Z'
            }
        """
        if not self.is_available():
            logger.warning("BigQuery not available. Returning None.")
            return None
        
        try:
            # COST CONTROL: Add partition filter to accounts_current (partitioned by batch_run_date)
            # Query only recent data (last 90 days) to minimize scan size
            from datetime import datetime, timedelta
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=90)  # 90-day window for recent accounts
            
            query = """
                SELECT 
                    account_id,
                    account_creation_date
                FROM `crypto-stellar.crypto_stellar_dbt.accounts_current`
                WHERE account_id = @account
                  AND batch_run_date >= DATETIME(@start_date)
                  AND batch_run_date <= DATETIME(@end_date)
                ORDER BY batch_run_date DESC
                LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("account", "STRING", account),
                    bigquery.ScalarQueryParameter("start_date", "STRING", start_date.strftime('%Y-%m-%d')),
                    bigquery.ScalarQueryParameter("end_date", "STRING", end_date.strftime('%Y-%m-%d'))
                ]
            )
            
            # COST GUARD: Validate query size before execution (accounts_current is small, but validate for safety)
            logger.info(f"Validating query cost for account data of {account}")
            cost_info = self.cost_guard.validate_query_cost(query, job_config)
            logger.info(f"✅ Query approved: {cost_info['size_mb']} MB, ${cost_info['estimated_cost']}")
            
            # Execute query
            logger.info(f"Querying BigQuery for minimal account data of {account}")
            job_config.dry_run = False  # Re-enable actual execution
            query_job = self.client.query(query, job_config=job_config)
            
            for row in query_job:
                result = {
                    'account_id': row.account_id,
                    'account_creation_date': row.account_creation_date.isoformat() if row.account_creation_date else None
                }
                logger.info(f"Found account creation date in BigQuery for {account}")
                return result
            
            logger.warning(f"No account data found in BigQuery for {account}")
            return None
            
        except Exception as e:
            logger.error(f"BigQuery query failed for account data: {e}")
            sentry_sdk.capture_exception(e)
            return None
    
    def get_account_assets(self, account: str) -> List[Dict]:
        """
        Get all asset holdings (trustlines) for an account from BigQuery.
        
        Args:
            account: The Stellar account address to query
        
        Returns:
            List of dicts containing asset holdings:
            [
                {
                    'account_id': 'G...',
                    'asset_type': 'credit_alphanum4',
                    'asset_code': 'USDC',
                    'asset_issuer': 'G...',
                    'balance': 1234.5678,
                    'limit': 10000,
                    'buying_liabilities': 0,
                    'selling_liabilities': 0,
                    'flags': 1,
                    'last_modified_ledger': 123456,
                    'ledger_entry_change': 2,
                    'deleted': False,
                    'sponsor': None,
                    'batch_run_date': '2025-01-01'
                },
                ...
            ]
        """
        if not self.is_available():
            logger.warning("BigQuery not available. Returning empty list.")
            return []
        
        try:
            query = """
                SELECT 
                    account_id,
                    asset_type,
                    asset_code,
                    asset_issuer,
                    balance,
                    trust_line_limit as trust_limit,
                    buying_liabilities,
                    selling_liabilities,
                    flags,
                    last_modified_ledger,
                    ledger_entry_change,
                    deleted,
                    sponsor,
                    batch_run_date
                FROM `crypto-stellar.crypto_stellar_dbt.trust_lines_current`
                WHERE account_id = @account
                  AND deleted = FALSE
                ORDER BY batch_run_date DESC, asset_code ASC
                LIMIT 1000
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("account", "STRING", account)
                ]
            )
            
            # COST GUARD: Validate query size before execution (trust_lines_current is small, but validate for safety)
            logger.info(f"Validating query cost for assets of {account}")
            cost_info = self.cost_guard.validate_query_cost(query, job_config)
            logger.info(f"✅ Query approved: {cost_info['size_mb']} MB, ${cost_info['estimated_cost']}")
            
            # Execute query
            logger.info(f"Querying BigQuery for assets of {account}")
            job_config.dry_run = False  # Re-enable actual execution
            query_job = self.client.query(query, job_config=job_config)
            
            results = []
            seen_assets = set()
            
            for row in query_job:
                asset_key = f"{row.asset_code}:{row.asset_issuer}"
                
                if asset_key not in seen_assets:
                    seen_assets.add(asset_key)
                    results.append({
                        'account_id': row.account_id,
                        'asset_type': row.asset_type,
                        'asset_code': row.asset_code,
                        'asset_issuer': row.asset_issuer,
                        'balance': float(row.balance) if row.balance else 0.0,
                        'limit': float(row.trust_limit) if row.trust_limit else 0.0,
                        'buying_liabilities': float(row.buying_liabilities) if row.buying_liabilities else 0.0,
                        'selling_liabilities': float(row.selling_liabilities) if row.selling_liabilities else 0.0,
                        'flags': row.flags,
                        'last_modified_ledger': row.last_modified_ledger,
                        'ledger_entry_change': row.ledger_entry_change,
                        'deleted': row.deleted,
                        'sponsor': row.sponsor,
                        'batch_run_date': str(row.batch_run_date) if row.batch_run_date else None
                    })
            
            logger.info(f"Found {len(results)} assets in BigQuery for {account}")
            return results
            
        except Exception as e:
            logger.error(f"BigQuery query failed for account assets: {e}")
            sentry_sdk.capture_exception(e)
            return []
    
    def get_instant_lineage(self, account: str) -> Dict:
        """
        Get instant MINIMAL lineage data for an account by querying BigQuery directly.
        This is used for immediate display when a user searches for an account.
        
        Uses Horizon API for account creation date (free), then BigQuery with proper
        date filters for lineage. Falls back to API methods if Cost Guard blocks queries.
        
        Optimized to query only essential lineage data:
        - Account ID and creation date (from Horizon API - free)
        - Creator account and creation date (BigQuery with fallback to APIs)
        - Child account addresses (BigQuery, skipped if blocked)
        
        Args:
            account: The Stellar account address to query
        
        Returns:
            Dict containing minimal lineage data:
            {
                'account': {'account_id': 'G...', 'account_creation_date': '...'},
                'creator': {
                    'creator_account': 'G...',
                    'created_at': '...',
                    'account_creation_date': '...'
                },
                'children_addresses': ['G...', 'G...', ...]
            }
        """
        if not self.is_available():
            logger.warning("BigQuery not available for instant lineage query")
            return {
                'account': None,
                'creator': None,
                'children_addresses': []
            }
        
        try:
            from datetime import datetime, timedelta
            from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers
            from apiApp.helpers.sm_stellarexpert import (
                StellarMapStellarExpertAPIHelpers,
                StellarMapStellarExpertAPIParserHelpers
            )
            
            # Step 1: Get account creation date from Horizon API (FREE, no BigQuery cost)
            horizon_helper = StellarMapHorizonAPIHelpers(
                horizon_url='https://horizon.stellar.org',
                account_id=account
            )
            horizon_account = horizon_helper.get_base_accounts()
            
            if not horizon_account:
                logger.warning(f"Account {account} not found in Horizon API")
                return {
                    'account': None,
                    'creator': None,
                    'children_addresses': []
                }
            
            # Extract creation date from Horizon
            creation_date_str = horizon_account.get('last_modified_time', '2015-01-01T00:00:00Z')
            account_data = {
                'account_id': account,
                'account_creation_date': creation_date_str
            }
            
            # Step 2: Calculate safe date window for partition filters
            if 'T' in creation_date_str:
                creation_date = creation_date_str.split('T')[0]
            else:
                creation_date = creation_date_str
            
            try:
                start_dt = datetime.fromisoformat(creation_date.replace('Z', '')) - timedelta(days=7)
                start_date = start_dt.strftime('%Y-%m-%d')
            except:
                start_date = '2015-01-01'
            
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
            
            # Step 3: Query creator info with date filters (BigQuery)
            creator_info = self.get_account_creator(account, start_date=start_date, end_date=end_date)
            creator_data = None
            
            if creator_info:
                # BigQuery succeeded
                creator_data = {
                    **creator_info,
                    'account_creation_date': None  # Optional: fetch creator's creation date if needed
                }
                logger.info(f"Creator found via BigQuery for {account}")
            else:
                # Cost Guard blocked or no result - use API fallback
                logger.warning(f"BigQuery blocked for creator of {account} - using API fallback")
                
                # Try Horizon operations first
                operations_response = horizon_helper.get_base_operations()
                if operations_response:
                    from apiApp.helpers.sm_horizon import StellarMapHorizonAPIParserHelpers
                    parser = StellarMapHorizonAPIParserHelpers({'data': {'raw_data': operations_response}})
                    api_creator = parser.parse_operations_creator_account(account)
                    
                    if api_creator and api_creator.get('funder'):
                        creator_data = {
                            'creator_account': api_creator['funder'],
                            'created_at': api_creator.get('created_at').isoformat() if api_creator.get('created_at') else None,
                            'account_creation_date': None
                        }
                        logger.info(f"Creator found via Horizon API for {account}")
                
                # Fallback to Stellar Expert if still no creator
                if not creator_data:
                    expert_helper = StellarMapStellarExpertAPIHelpers(
                        stellar_account=account,
                        network_name='public'
                    )
                    expert_data = expert_helper.get_account()
                    
                    if expert_data:
                        expert_parser = StellarMapStellarExpertAPIParserHelpers({'data': {'raw_data': expert_data}})
                        creator_data = {
                            'creator_account': expert_parser.parse_account_creator(),
                            'created_at': expert_parser.parse_account_created_at(),
                            'account_creation_date': None
                        }
                        logger.info(f"Creator found via Stellar Expert for {account}")
            
            # Step 4: Query child addresses (limited to 100 for instant display)
            children = self.get_child_accounts(account, limit=100, start_date=start_date, end_date=end_date)
            children_addresses = [child['account'] for child in children]
            
            logger.info(f"Instant minimal lineage query complete: account={bool(account_data)}, creator={bool(creator_data)}, children={len(children_addresses)}")
            
            return {
                'account': account_data,
                'creator': creator_data,
                'children_addresses': children_addresses
            }
            
        except Exception as e:
            logger.error(f"Failed to get instant lineage for {account}: {e}")
            sentry_sdk.capture_exception(e)
            return {
                'account': None,
                'creator': None,
                'children_addresses': []
            }
    
    def get_dataset_info(self) -> Dict:
        """
        Get information about the Stellar BigQuery dataset.
        Useful for debugging and verification.
        
        Returns:
            Dict with dataset information
        """
        if not self.is_available():
            return {'available': False, 'error': 'BigQuery client not initialized'}
        
        try:
            dataset_id = 'crypto-stellar.crypto_stellar_dbt'
            dataset = self.client.get_dataset(dataset_id)
            
            return {
                'available': True,
                'dataset_id': dataset_id,
                'location': dataset.location,
                'description': dataset.description,
                'created': dataset.created.isoformat() if dataset.created else None,
                'modified': dataset.modified.isoformat() if dataset.modified else None
            }
        except Exception as e:
            logger.error(f"Failed to get dataset info: {e}")
            sentry_sdk.capture_exception(e)
            return {'available': False, 'error': str(e)}
