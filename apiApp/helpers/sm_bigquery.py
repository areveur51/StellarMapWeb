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
            
            logger.info("BigQuery client initialized successfully")
            
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
        start_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch all accounts created by a specific parent account from BigQuery.
        
        This queries the Stellar Hubble dataset for create_account operations
        where the parent account is the funder.
        
        Args:
            parent_account: The Stellar account address to query
            limit: Maximum number of child accounts to return (default 10000)
            offset: Number of results to skip for pagination (default 0)
            start_date: Optional start date filter (format: 'YYYY-MM-DD') to limit costs
        
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
        
        try:
            date_filter = ""
            query_parameters = [
                bigquery.ScalarQueryParameter("parent_account", "STRING", parent_account)
            ]
            
            if start_date:
                date_filter = "AND closed_at >= TIMESTAMP(@start_date)"
                query_parameters.append(
                    bigquery.ScalarQueryParameter("start_date", "STRING", f"{start_date}T00:00:00Z")
                )
            
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
                  {date_filter}
                ORDER BY closed_at ASC
                LIMIT {limit}
                OFFSET {offset}
            """
            
            job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
            
            logger.info(f"Querying BigQuery for child accounts of {parent_account}")
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
    
    def get_account_creator(self, account: str) -> Optional[Dict]:
        """
        Find the creator (funder) of a specific account using BigQuery.
        
        This is useful as a fallback when Horizon operations are too deep
        or when the account was created through non-standard methods.
        
        Args:
            account: The Stellar account address to query
        
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
        
        try:
            query = """
                SELECT 
                    funder as creator,
                    closed_at as created_at
                FROM `crypto-stellar.crypto_stellar_dbt.enriched_history_operations`
                WHERE type = 0
                  AND account = @account
                ORDER BY closed_at ASC
                LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("account", "STRING", account)
                ]
            )
            
            logger.info(f"Querying BigQuery for creator of {account}")
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
            query = """
                SELECT 
                    account_id,
                    account_creation_date
                FROM `crypto-stellar.crypto_stellar_dbt.accounts_current`
                WHERE account_id = @account
                ORDER BY batch_run_date DESC
                LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("account", "STRING", account)
                ]
            )
            
            logger.info(f"Querying BigQuery for minimal account data of {account}")
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
            
            logger.info(f"Querying BigQuery for assets of {account}")
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
        
        BigQuery returns ONLY lineage structure (parent-child relationships and creation dates).
        All other data (assets, balance, home_domain, flags, etc.) should be fetched from
        Horizon API or Stellar Expert to minimize BigQuery usage and costs.
        
        Optimized to query only essential lineage data:
        - Account ID and creation date
        - Creator account and creation date
        - Child account addresses (for lineage tree structure)
        
        Args:
            account: The Stellar account address to query
        
        Returns:
            Dict containing minimal lineage data:
            {
                'account': {'account_id': 'G...', 'account_creation_date': '...'},
                'creator': {
                    'creator_account': 'G...',
                    'created_at': '...',
                    'account_creation_date': '...'  # From get_account_data
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
            # Query minimal account data (ID and creation date only)
            account_data = self.get_account_data(account)
            
            # Query creator info (address and creation date)
            creator_info = self.get_account_creator(account)
            creator_data = None
            if creator_info:
                # Get creator's account creation date
                creator_account_data = self.get_account_data(creator_info['creator_account'])
                creator_data = {
                    **creator_info,  # creator_account and created_at
                    'account_creation_date': creator_account_data['account_creation_date'] if creator_account_data else None
                }
            
            # Query child addresses only (limited to 100 for instant display)
            children = self.get_child_accounts(account, limit=100)
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
