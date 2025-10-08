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
            if start_date:
                date_filter = f"AND closed_at >= '{start_date}'"
            
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
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("parent_account", "STRING", parent_account)
                ]
            )
            
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
