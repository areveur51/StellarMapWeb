# sm_creatoraccountlineage.py - Modular async updates with batching/retries.
import json
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential
import sentry_sdk
from stellar_sdk import Server
from stellar_sdk.exceptions import BaseRequestError
from apiApp.managers import StellarCreatorAccountLineageManager
from apiApp.services import AstraDocument
from django.http import HttpRequest
from .sm_horizon import StellarMapHorizonAPIParserHelpers, StellarMapHorizonAPIHelpers
from .sm_stellarexpert import StellarMapStellarExpertAPIHelpers, StellarMapStellarExpertAPIParserHelpers
from apiApp.models import (
    PENDING,
    PROCESSING,
    COMPLETE,
    BIGQUERY_COMPLETE
)


class StellarMapCreatorAccountLineageHelpers:

    @retry(wait=wait_exponential(multiplier=1, max=5),
           stop=stop_after_attempt(5))
    async def async_update_from_accounts_raw_data(self, client_session,
                                                  lin_queryset):
        """Modular update from accounts data."""
        manager = StellarCreatorAccountLineageManager()
        await manager.async_update_status(lin_queryset.id,
                                          PROCESSING)
        
        # Read JSON directly from Cassandra TEXT column
        if not lin_queryset.horizon_accounts_json:
            raise Exception(f"No Horizon accounts JSON data found for {lin_queryset.stellar_account}")
        
        raw_data = json.loads(lin_queryset.horizon_accounts_json)
        response = {"data": {"raw_data": raw_data}}
        parser = StellarMapHorizonAPIParserHelpers(response)
        req = HttpRequest()
        req.data = {
            'home_domain': parser.parse_account_home_domain(),
            'xlm_balance': parser.parse_account_native_balance(),
            'status': COMPLETE
        }
        await manager.async_update_lineage(lin_queryset.id, req)

    @retry(wait=wait_exponential(multiplier=1, max=5),
           stop=stop_after_attempt(5))
    async def async_update_from_operations_raw_data(self, client_session,
                                                     lin_queryset):
        """Update lineage from operations data to extract creator account."""
        manager = StellarCreatorAccountLineageManager()
        await manager.async_update_status(lin_queryset.id,
                                          PROCESSING)
        
        # Read JSON directly from Cassandra TEXT column
        if not lin_queryset.horizon_operations_json:
            raise Exception(f"No Horizon operations JSON data found for {lin_queryset.stellar_account}")
        
        raw_data = json.loads(lin_queryset.horizon_operations_json)
        response = {"data": {"raw_data": raw_data}}
        parser = StellarMapHorizonAPIParserHelpers(response)
        creator_data = parser.parse_operations_creator_account(lin_queryset.stellar_account)
        
        # If no creator found in operations (e.g., claimable balance accounts),
        # fall back to Stellar Expert API as authoritative source
        if not creator_data.get('funder'):
            stellar_expert_helpers = StellarMapStellarExpertAPIHelpers(
                stellar_account=lin_queryset.stellar_account,
                network_name=lin_queryset.network_name
            )
            expert_data = stellar_expert_helpers.get_account()
            expert_parser = StellarMapStellarExpertAPIParserHelpers(
                {"data": {"raw_data": expert_data}}
            )
            creator_data = {
                'funder': expert_parser.parse_account_creator(),
                'created_at': expert_parser.parse_account_created_at()
            }
        
        req = HttpRequest()
        req.data = {
            'stellar_creator_account': creator_data.get('funder', ''),
            'stellar_account_created_at': creator_data.get('created_at'),
            'status': COMPLETE
        }
        await manager.async_update_lineage(lin_queryset.id, req)

    @retry(wait=wait_exponential(multiplier=1, max=5),
           stop=stop_after_attempt(5))
    async def async_make_grandparent_account(self, client_session,
                                              lin_queryset):
        """Create grandparent lineage by processing creator account."""
        manager = StellarCreatorAccountLineageManager()
        await manager.async_update_status(lin_queryset.id,
                                          PROCESSING)
        
        creator_account = lin_queryset.stellar_creator_account
        network_name = lin_queryset.network_name
        
        if creator_account and creator_account not in ['no_element_funder', 'unknown', '']:
            existing_lineage = manager.get_queryset(
                stellar_account=creator_account,
                network_name=network_name
            )
            
            if not existing_lineage:
                req = HttpRequest()
                req.data = {
                    'stellar_account': creator_account,
                    'network_name': network_name,
                    'status': PENDING
                }
                manager.create_lineage(req)
        
        await manager.async_update_status(lin_queryset.id,
                                          COMPLETE)
    
    @retry(wait=wait_exponential(multiplier=1, max=5),
           stop=stop_after_attempt(5))
    async def async_fetch_child_accounts(self, client_session, lin_queryset):
        """
        Fetch child accounts created by this account.
        
        Uses two-tier approach:
        1. Primary: Horizon API (recent operations, ~1000 operations max)
        2. Fallback: BigQuery/Hubble (complete historical data if configured)
        
        Queries for create_account operations where this account is the funder,
        then adds those child accounts to the database for processing.
        """
        from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers
        from apiApp.helpers.sm_bigquery import StellarBigQueryHelper
        
        manager = StellarCreatorAccountLineageManager()
        stellar_account = lin_queryset.stellar_account
        network_name = lin_queryset.network_name
        
        # Determine Horizon URL based on network
        horizon_url = 'https://horizon.stellar.org' if network_name == 'public' else 'https://horizon-testnet.stellar.org'
        
        try:
            child_accounts = []
            
            # Primary: Try Horizon API first (up to 1000 operations)
            try:
                horizon_helper = StellarMapHorizonAPIHelpers(
                    horizon_url=horizon_url,
                    account_id=stellar_account
                )
                child_accounts = horizon_helper.get_child_accounts(max_pages=5)
                print(f"[DEBUG] Horizon API found {len(child_accounts)} child accounts for {stellar_account[-7:]}")
            except Exception as horizon_error:
                sentry_sdk.capture_exception(horizon_error)
                print(f"[WARNING] Horizon API failed for {stellar_account[-7:]}: {str(horizon_error)}")
            
            # Fallback: Try BigQuery for complete historical data (if configured)
            if network_name == 'public':
                try:
                    bigquery_helper = StellarBigQueryHelper()
                    if bigquery_helper.is_available():
                        # Get account creation date to optimize BigQuery scan
                        account_created = lin_queryset.stellar_account_created_at
                        start_date = None
                        if account_created:
                            start_date = account_created.strftime('%Y-%m-%d')
                        
                        bigquery_children = bigquery_helper.get_child_accounts(
                            parent_account=stellar_account,
                            start_date=start_date,
                            limit=10000
                        )
                        
                        if bigquery_children:
                            # Merge with Horizon results, avoiding duplicates
                            horizon_accounts = {c.get('account') for c in child_accounts}
                            for bq_child in bigquery_children:
                                if bq_child.get('account') not in horizon_accounts:
                                    child_accounts.append(bq_child)
                            
                            print(f"[DEBUG] BigQuery found {len(bigquery_children)} total child accounts for {stellar_account[-7:]}")
                            print(f"[DEBUG] Combined: {len(child_accounts)} unique child accounts")
                except Exception as bigquery_error:
                    sentry_sdk.capture_exception(bigquery_error)
                    print(f"[INFO] BigQuery fallback not available for {stellar_account[-7:]}: {str(bigquery_error)}")
            
            # Add each child account to the database if not already present
            added_count = 0
            for child_data in child_accounts:
                child_account = child_data.get('account')
                
                if not child_account:
                    continue
                
                # Check if child account already exists in database
                existing_lineage = manager.get_queryset(
                    stellar_account=child_account,
                    network_name=network_name
                )
                
                if not existing_lineage:
                    # Create new lineage record for child account
                    req = HttpRequest()
                    req.data = {
                        'stellar_account': child_account,
                        'network_name': network_name,
                        'status': PENDING
                    }
                    manager.create_lineage(req)
                    added_count += 1
                    print(f"[DEBUG] Added child account {child_account[-7:]} to database (parent: {stellar_account[-7:]})")
            
            if child_accounts:
                print(f"[DEBUG] Processed {len(child_accounts)} child accounts for {stellar_account[-7:]} ({added_count} new)")
            
        except Exception as e:
            # Don't fail the pipeline if child account fetching fails
            sentry_sdk.capture_exception(e)
            print(f"[WARNING] Failed to fetch child accounts for {stellar_account[-7:]}: {str(e)}")

    def get_account_genealogy_from_horizon(self, stellar_account, network_name, max_depth=10):
        """
        Fetch account genealogy directly from Horizon API as fallback.
        
        Note: Horizon only keeps ~1 year of history. Accounts created before 
        August 2023 will not have create_account operations available.
        
        Args:
            stellar_account: Stellar account address
            network_name: 'public' or 'testnet'
            max_depth: Maximum depth to traverse
            
        Returns:
            pd.DataFrame: Genealogy data in same format as database query
        """
        horizon_url = 'https://horizon.stellar.org' if network_name == 'public' else 'https://horizon-testnet.stellar.org'
        
        records = []
        current_account = stellar_account
        depth = 0
        
        try:
            while depth < max_depth:
                helper = StellarMapHorizonAPIHelpers(horizon_url, current_account)
                operations = helper.get_account_operations()
                
                # Find the create_account operation for this account
                # Look through all operations, prioritizing those with matching account field
                creator_info = None
                all_records = operations.get('_embedded', {}).get('records', [])
                
                for record in all_records:
                    if record.get('type') == 'create_account':
                        # Check if this create_account operation matches our account
                        if record.get('account') == current_account:
                            creator_info = {
                                'stellar_account': current_account,
                                'stellar_creator_account': record.get('funder', record.get('source_account', 'unknown')),
                                'created': record.get('created_at', ''),
                                'network_name': network_name,
                                'node_type': 'ACCOUNT'
                            }
                            break
                
                # If no create_account found, account is too old or data unavailable
                if not creator_info:
                    print(f"[DEBUG] No create_account operation found for {current_account}. Account may be >1 year old.")
                    break
                    
                records.append(creator_info)
                
                # Move to creator account
                current_account = creator_info['stellar_creator_account']
                if current_account in ['unknown', 'no_element_funder', '']:
                    break
                    
                depth += 1
                
            if records:
                print(f"[DEBUG] Successfully fetched {len(records)} lineage records from Horizon API")
            else:
                print(f"[DEBUG] Account {stellar_account} is likely >1 year old. Horizon API data unavailable.")
                
            return pd.DataFrame(records)
            
        except (BaseRequestError, Exception) as e:
            sentry_sdk.capture_exception(e)
            print(f"[DEBUG] Error fetching from Horizon: {str(e)}")
            return pd.DataFrame()

    def get_account_genealogy(self,
                              stellar_account,
                              network_name,
                              max_depth=10):
        """
        Efficient genealogy fetch with depth limit. Falls back to Horizon API if database is empty.
        
        First tries to fetch from Astra DB (Cassandra). If database is not available or has no data,
        falls back to fetching directly from Horizon API (limited to ~1 year of history).
        """
        df = pd.DataFrame()
        
        # First try to get from database
        try:
            current_account = stellar_account
            current_network = network_name
            depth = 0
            
            while depth < max_depth:
                manager = StellarCreatorAccountLineageManager()
                qs = manager.get_queryset(stellar_account=current_account,
                                          network_name=current_network)
                if not qs:
                    break
                row = {
                    f: getattr(qs, f)
                    for f in qs._meta.fields
                }  # Efficient dict
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                current_account = qs.stellar_creator_account
                if current_account == 'no_element_funder':
                    break
                depth += 1
            
        except Exception as e:
            # Database not available or query failed - will fallback to Horizon API
            sentry_sdk.capture_exception(e)
        
        # If database returned no data or failed, fallback to Horizon API
        if df.empty:
            try:
                df = self.get_account_genealogy_from_horizon(stellar_account, network_name, max_depth)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                
        return df

    def generate_tidy_radial_tree_genealogy(self, genealogy_df):
        """Efficient tree build from DF."""
        if genealogy_df.empty:
            return {'name': 'Root', 'children': []}
        records = genealogy_df.to_dict('records')
        node_lookup = {
            r['stellar_account']: {
                'name': r['stellar_account'],
                'stellar_account': r['stellar_account'],
                'node_type': r.get('node_type', 'ACCOUNT'),
                'created': str(r.get('created', '')),
                'children': []
            }
            for r in records
        }
        root = None
        for r in records:
            creator = r.get('stellar_creator_account', 'unknown')
            if creator not in node_lookup or creator in ['no_element_funder', 'unknown']:
                root = node_lookup[r['stellar_account']]
            else:
                node_lookup[creator]['children'].append(
                    node_lookup[r['stellar_account']])
        return root or {'name': 'Root', 'children': []}
