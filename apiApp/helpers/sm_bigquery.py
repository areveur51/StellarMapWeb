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
        start_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch all accounts created by a specific parent account from BigQuery.
        
        This queries the Stellar Hubble dataset for create_account operations
        where the parent account is the funder.
        
        Args:
            parent_account: The Stellar account address to query
            limit: Maximum number of child accounts to return (default 10000)
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
    
    def get_account_creator(self, account: str) -> Optional[str]:
        """
        Find the creator (funder) of a specific account using BigQuery.
        
        This is useful as a fallback when Horizon operations are too deep
        or when the account was created through non-standard methods.
        
        Args:
            account: The Stellar account address to query
        
        Returns:
            The creator account address, or None if not found
        """
        if not self.is_available():
            logger.warning("BigQuery not available. Returning None.")
            return None
        
        try:
            query = """
                SELECT 
                    source_account as creator
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
                creator = row.creator
                logger.info(f"Found creator {creator} for {account} in BigQuery")
                return creator
            
            logger.info(f"No creator found in BigQuery for {account}")
            return None
            
        except Exception as e:
            logger.error(f"BigQuery query failed: {e}")
            sentry_sdk.capture_exception(e)
            return None
    
    def get_account_data(self, account: str) -> Optional[Dict]:
        """
        Get comprehensive account data from BigQuery including balance, flags, and assets.
        
        Args:
            account: The Stellar account address to query
        
        Returns:
            Dict containing account data:
            {
                'account_id': 'G...',
                'balance': 1234567890,  # stroops
                'buying_liabilities': 0,
                'selling_liabilities': 0,
                'num_subentries': 5,
                'num_sponsored': 0,
                'num_sponsoring': 0,
                'sequence_number': 123456789,
                'sequence_ledger': 123456,
                'sequence_time': 1234567890,
                'flags': 0,
                'home_domain': 'example.com',
                'master_weight': 1,
                'threshold_low': 0,
                'threshold_medium': 0,
                'threshold_high': 0,
                'last_modified_ledger': 123456,
                'ledger_entry_change': 1,
                'deleted': False,
                'batch_id': '2025-01-01-000000',
                'batch_run_date': '2025-01-01',
                'closed_at': '2025-01-01T00:00:00Z'
            }
        """
        if not self.is_available():
            logger.warning("BigQuery not available. Returning None.")
            return None
        
        try:
            query = """
                SELECT 
                    account_id,
                    balance,
                    buying_liabilities,
                    selling_liabilities,
                    num_subentries,
                    num_sponsored,
                    num_sponsoring,
                    sequence_number,
                    sequence_ledger,
                    sequence_time,
                    flags,
                    home_domain,
                    master_weight,
                    threshold_low,
                    threshold_medium,
                    threshold_high,
                    last_modified_ledger,
                    ledger_entry_change,
                    deleted,
                    batch_id,
                    batch_run_date,
                    closed_at
                FROM `crypto-stellar.crypto_stellar.accounts_current`
                WHERE account_id = @account
                ORDER BY batch_run_date DESC
                LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("account", "STRING", account)
                ]
            )
            
            logger.info(f"Querying BigQuery for account data of {account}")
            query_job = self.client.query(query, job_config=job_config)
            
            for row in query_job:
                result = {
                    'account_id': row.account_id,
                    'balance': row.balance,
                    'buying_liabilities': row.buying_liabilities,
                    'selling_liabilities': row.selling_liabilities,
                    'num_subentries': row.num_subentries,
                    'num_sponsored': row.num_sponsored,
                    'num_sponsoring': row.num_sponsoring,
                    'sequence_number': row.sequence_number,
                    'sequence_ledger': row.sequence_ledger,
                    'sequence_time': row.sequence_time,
                    'flags': row.flags,
                    'home_domain': row.home_domain or '',
                    'master_weight': row.master_weight,
                    'threshold_low': row.threshold_low,
                    'threshold_medium': row.threshold_medium,
                    'threshold_high': row.threshold_high,
                    'last_modified_ledger': row.last_modified_ledger,
                    'ledger_entry_change': row.ledger_entry_change,
                    'deleted': row.deleted,
                    'batch_id': row.batch_id,
                    'batch_run_date': str(row.batch_run_date) if row.batch_run_date else None,
                    'closed_at': row.closed_at.isoformat() if row.closed_at else None
                }
                logger.info(f"Found account data in BigQuery for {account}")
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
                FROM `crypto-stellar.crypto_stellar.trust_lines`
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
