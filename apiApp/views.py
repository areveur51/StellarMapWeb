"""
API Views for StellarMapWeb

This module contains all API endpoints for the application.
"""

import json
import logging
import sentry_sdk
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from apiApp.model_loader import (
    StellarCreatorAccountLineage,
    StellarAccountSearchCache, 
    StellarAccountStageExecution,
    USE_CASSANDRA
)
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers


logger = logging.getLogger(__name__)


def lineage_with_siblings_api(request):
    """
    API endpoint that returns account lineage with siblings at each level.
    
    This endpoint provides both:
    1. Direct lineage path from searched account to root creator
    2. Siblings (other children) of each creator in the path
    
    Used for enhanced visualization showing family trees with siblings.
    
    Query Parameters:
        account (str): Stellar account address (required)
        network (str): Network name (required, 'public' or 'testnet')
        max_siblings_per_level (int): Maximum siblings to return per level (default: 50)
    
    Returns:
        JsonResponse: {
            'account': str,
            'network': str,
            'lineage_path': [list of accounts in direct path, root to searched],
            'siblings_by_creator': {
                'GCREATOR1...': [list of sibling accounts],
                'GCREATOR2...': [list of sibling accounts],
                ...
            },
            'all_account_data': {
                'GACCOUNT1...': {account details},
                'GACCOUNT2...': {account details},
                ...
            }
        }
    """
    account = request.GET.get('account', '').strip()
    network = request.GET.get('network', '').strip()
    max_siblings = int(request.GET.get('max_siblings_per_level', 50))
    
    # Validate required parameters
    if not account or not network:
        return JsonResponse({
            'error': 'Missing required parameters',
            'message': 'Both account and network parameters are required'
        }, status=400)
    
    # Validate address format
    if not StellarMapValidatorHelpers.validate_stellar_account_address(account):
        return JsonResponse({
            'error': 'Invalid stellar account address',
            'message': 'Account must be a valid Stellar address'
        }, status=400)
    
    # Validate network
    if network not in ['public', 'testnet']:
        return JsonResponse({
            'error': 'Invalid network',
            'message': 'Network must be either public or testnet'
        }, status=400)
    
    try:
        def convert_timestamp(ts):
            """Convert timestamp to ISO format string"""
            if ts is None:
                return None
            if isinstance(ts, datetime):
                return ts.isoformat()
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts).isoformat()
            return str(ts)
        
        def extract_assets(horizon_json):
            """Extract assets from horizon API JSON"""
            assets = []
            if horizon_json:
                try:
                    horizon_data = json.loads(horizon_json)
                    balances = horizon_data.get('balances', [])
                    
                    for balance in balances:
                        asset_type = balance.get('asset_type', '')
                        if asset_type != 'native':
                            asset_code = balance.get('asset_code', '')
                            asset_issuer = balance.get('asset_issuer', '')
                            asset_balance = balance.get('balance', '0')
                            
                            assets.append({
                                'name': asset_code,
                                'node_type': 'ASSET',
                                'asset_type': asset_type,
                                'asset_code': asset_code,
                                'asset_issuer': asset_issuer,
                                'balance': float(asset_balance) if asset_balance else 0.0
                            })
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass
            return assets
        
        # STEP 1: Build direct lineage path (from account to root creator)
        lineage_path = []  # Will be ordered from searched account to root
        current_account = account
        visited = set()
        max_depth = 50  # Prevent infinite loops
        
        while current_account and current_account not in visited and len(lineage_path) < max_depth:
            visited.add(current_account)
            
            # Fetch record for current account
            if USE_CASSANDRA:
                records = list(StellarCreatorAccountLineage.objects.filter(
                    stellar_account=current_account,
                    network_name=network
                ).limit(1))
                record = records[0] if records else None
            else:
                record = StellarCreatorAccountLineage.objects.filter(
                    stellar_account=current_account,
                    network_name=network
                ).first()
            
            if not record:
                break
            
            lineage_path.append(current_account)
            current_account = record.stellar_creator_account
        
        # Reverse to get root → searched account order
        lineage_path.reverse()
        
        # STEP 2: For each account in lineage path, fetch siblings
        siblings_by_creator = {}
        all_accounts_to_fetch = set(lineage_path)  # Start with lineage path
        
        for account_addr in lineage_path:
            # Fetch the record to get creator
            if USE_CASSANDRA:
                records = list(StellarCreatorAccountLineage.objects.filter(
                    stellar_account=account_addr,
                    network_name=network
                ).limit(1))
                record = records[0] if records else None
            else:
                record = StellarCreatorAccountLineage.objects.filter(
                    stellar_account=account_addr,
                    network_name=network
                ).first()
            
            if record and record.stellar_creator_account:
                creator_addr = record.stellar_creator_account
                
                # Fetch all children of this creator (siblings of current account)
                if USE_CASSANDRA:
                    # Cassandra: fetch all children
                    sibling_records = list(StellarCreatorAccountLineage.objects.filter(
                        stellar_creator_account=creator_addr,
                        network_name=network
                    ).limit(max_siblings + 1))  # +1 to detect if there are more
                else:
                    # SQL: fetch with limit
                    sibling_records = list(StellarCreatorAccountLineage.objects.filter(
                        stellar_creator_account=creator_addr,
                        network_name=network
                    )[:max_siblings + 1])
                
                # Extract sibling account addresses (excluding the one in lineage path)
                sibling_addrs = [
                    rec.stellar_account 
                    for rec in sibling_records 
                    if rec.stellar_account != account_addr
                ][:max_siblings]
                
                if sibling_addrs:
                    siblings_by_creator[creator_addr] = sibling_addrs
                    all_accounts_to_fetch.update(sibling_addrs)
                    all_accounts_to_fetch.add(creator_addr)
        
        # STEP 3: Fetch full data for all accounts (lineage path + siblings)
        all_account_data = {}
        
        for acct_addr in all_accounts_to_fetch:
            if USE_CASSANDRA:
                records = list(StellarCreatorAccountLineage.objects.filter(
                    stellar_account=acct_addr,
                    network_name=network
                ).limit(1))
                record = records[0] if records else None
            else:
                record = StellarCreatorAccountLineage.objects.filter(
                    stellar_account=acct_addr,
                    network_name=network
                ).first()
            
            if record:
                assets = extract_assets(record.horizon_accounts_json)
                
                all_account_data[acct_addr] = {
                    'stellar_account': record.stellar_account,
                    'stellar_creator_account': record.stellar_creator_account,
                    'network_name': record.network_name,
                    'stellar_account_created_at': convert_timestamp(record.stellar_account_created_at),
                    'home_domain': record.home_domain or '',
                    'xlm_balance': float(record.xlm_balance) if record.xlm_balance else 0.0,
                    'assets': assets,
                    'status': record.status,
                    'created_at': convert_timestamp(record.created_at),
                    'updated_at': convert_timestamp(record.updated_at),
                    'is_issuer': len(assets) > 0,  # Flag for green nodes
                }
        
        return JsonResponse({
            'account': account,
            'network': network,
            'lineage_path': lineage_path,
            'siblings_by_creator': siblings_by_creator,
            'all_account_data': all_account_data,
            'total_accounts': len(all_account_data),
            'total_siblings': sum(len(siblings) for siblings in siblings_by_creator.values())
        }, safe=False)
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)
