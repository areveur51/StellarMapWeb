"""
Helper for refreshing account enrichment data from Horizon API and Stellar Expert API.

This module provides functionality to re-fetch and update account data including:
- Balance, flags, home_domain from Horizon API
- Assets and trustlines from Stellar Expert API
"""
import json
import requests
import sentry_sdk
from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers, StellarMapHorizonAPIParserHelpers
from apiApp.helpers.sm_stellarexpert import StellarMapStellarExpertAPIHelpers
from apiApp.helpers.env import EnvHelpers


class StellarMapEnrichmentHelper:
    """
    Helper class for refreshing account enrichment data.
    
    Fetches fresh data from Horizon API and Stellar Expert API and updates
    the account object.
    """
    
    @staticmethod
    def refresh_account_enrichment(account_obj, network_name='public'):
        """
        Refresh enrichment data for a specific account.
        
        Fetches and updates:
        - xlm_balance: Native XLM balance from Horizon
        - home_domain: Home domain from Horizon
        - stellar_account_attributes_json: Flags, balances, signers, etc. from Horizon
        - stellar_account_assets_json: Assets and trustlines from Stellar Expert
        
        Args:
            account_obj: StellarCreatorAccountLineage object (Cassandra or SQLite)
            network_name: Network to use ('public' or 'testnet')
        
        Returns:
            dict: Status information with success flag and details
        """
        try:
            stellar_account = account_obj.stellar_account if hasattr(account_obj, 'stellar_account') else account_obj.get('stellar_account')
            
            # Get Horizon URL based on network
            env_helpers = EnvHelpers()
            if network_name == 'public':
                env_helpers.set_public_network()
            else:
                env_helpers.set_testnet_network()
            
            horizon_url = env_helpers.get_base_horizon()
            
            # ============================================================
            # STEP 1: Fetch from Horizon API
            # ============================================================
            horizon_helper = StellarMapHorizonAPIHelpers(
                horizon_url=horizon_url,
                account_id=stellar_account
            )
            
            horizon_response = horizon_helper.get_base_accounts()
            
            # Parse Horizon response
            parser = StellarMapHorizonAPIParserHelpers(horizon_response)
            balance = parser.parse_account_native_balance()
            home_domain = parser.parse_account_home_domain()
            
            # Extract flags and other attributes
            flags = horizon_response.get('flags', {})
            num_subentries = horizon_response.get('num_subentries', 0)
            num_sponsoring = horizon_response.get('num_sponsoring', 0)
            num_sponsored = horizon_response.get('num_sponsored', 0)
            signers = horizon_response.get('signers', [])
            
            # ============================================================
            # STEP 2: Fetch from Stellar Expert API
            # ============================================================
            stellar_expert_helper = StellarMapStellarExpertAPIHelpers(
                stellar_account=stellar_account,
                network_name=network_name
            )
            
            # Get assets list
            try:
                assets_response = stellar_expert_helper.get_se_asset_list()
                assets = assets_response.get('_embedded', {}).get('records', [])
            except Exception as e:
                sentry_sdk.capture_exception(e)
                assets = []
            
            # ============================================================
            # STEP 3: Update account object
            # ============================================================
            
            # Update simple fields
            if hasattr(account_obj, 'xlm_balance'):
                account_obj.xlm_balance = balance
            else:
                account_obj['xlm_balance'] = balance
                
            if hasattr(account_obj, 'home_domain'):
                account_obj.home_domain = home_domain
            else:
                account_obj['home_domain'] = home_domain
            
            # Update attributes JSON (flags, signers, etc.)
            attributes_data = {
                'source': 'horizon_refresh',
                'balance': int(balance * 10000000),  # Store in stroops
                'home_domain': home_domain,
                'flags': flags,
                'signers': signers,
                'num_subentries': num_subentries,
                'num_sponsoring': num_sponsoring,
                'num_sponsored': num_sponsored
            }
            
            if hasattr(account_obj, 'stellar_account_attributes_json'):
                account_obj.stellar_account_attributes_json = json.dumps(attributes_data)
            else:
                account_obj['stellar_account_attributes_json'] = json.dumps(attributes_data)
            
            # Update assets JSON
            assets_data = {
                'source': 'stellar_expert_refresh',
                'count': len(assets),
                'assets': assets
            }
            
            if hasattr(account_obj, 'stellar_account_assets_json'):
                account_obj.stellar_account_assets_json = json.dumps(assets_data)
            else:
                account_obj['stellar_account_assets_json'] = json.dumps(assets_data)
            
            # Save the updated object
            if hasattr(account_obj, 'save'):
                account_obj.save()
            
            return {
                'success': True,
                'message': f'Successfully refreshed enrichment data for {stellar_account}',
                'details': {
                    'balance': balance,
                    'home_domain': home_domain,
                    'flags': flags,
                    'assets_count': len(assets)
                }
            }
            
        except Exception as e:
            sentry_sdk.capture_exception(e)
            error_msg = f'Failed to refresh enrichment data: {str(e)}'
            return {
                'success': False,
                'message': error_msg,
                'error': str(e)
            }
