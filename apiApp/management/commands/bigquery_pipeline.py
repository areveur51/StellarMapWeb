"""
BigQuery Pipeline - Fast & Efficient Data Collection

This pipeline uses BigQuery/Hubble dataset to retrieve all account data
in a single efficient query, avoiding API rate limits and pagination issues.

Comparison with cron_pipeline (8-stage API-based):
- cron_pipeline: 8 stages, 2-3 minutes per account, API rate limits
- bigquery_pipeline: 1 stage, seconds per account, no rate limits

Data Retrieved:
1. Account data (balance, flags, thresholds) from accounts_current
2. Asset holdings (trustlines) from trust_lines
3. Creator account from enriched_history_operations
4. Child accounts from enriched_history_operations
"""

import logging
import json
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from apiApp.models import StellarCreatorAccountLineage
from apiApp.helpers.sm_bigquery import StellarBigQueryHelper
import sentry_sdk

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'BigQuery Pipeline - Process accounts using BigQuery/Hubble dataset'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of accounts to process per run (default: 10)'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all accounts to PENDING status for reprocessing'
        )

    def handle(self, *args, **options):
        """
        Process accounts using BigQuery/Hubble dataset.
        """
        limit = options['limit']
        reset = options['reset']
        
        if reset:
            self._reset_accounts()
            return
        
        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*60}\n'
            f'BigQuery Pipeline Started\n'
            f'{"="*60}\n'
            f'Strategy: Retrieve all data from BigQuery in one query\n'
            f'No API rate limits, no pagination issues\n'
            f'Processing up to {limit} accounts...\n'
            f'{"="*60}\n'
        ))
        
        bq_helper = StellarBigQueryHelper()
        
        if not bq_helper.is_available():
            self.stdout.write(self.style.ERROR(
                'BigQuery integration not available. '
                'Please configure GOOGLE_APPLICATION_CREDENTIALS_JSON.'
            ))
            return
        
        pending_accounts = self._get_pending_accounts(limit)
        
        if not pending_accounts:
            self.stdout.write(self.style.SUCCESS('No pending accounts to process'))
            return
        
        self.stdout.write(self.style.SUCCESS(
            f'Found {len(pending_accounts)} pending accounts to process\n'
        ))
        
        processed = 0
        failed = 0
        
        for account_obj in pending_accounts:
            try:
                self.stdout.write(f'\n{"="*60}')
                self.stdout.write(f'Processing: {account_obj.stellar_account}')
                self.stdout.write(f'{"="*60}\n')
                
                success = self._process_account(account_obj, bq_helper)
                
                if success:
                    processed += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ Successfully processed {account_obj.stellar_account}'
                    ))
                else:
                    failed += 1
                    self.stdout.write(self.style.ERROR(
                        f'✗ Failed to process {account_obj.stellar_account}'
                    ))
                    
            except Exception as e:
                failed += 1
                logger.error(f'Error processing {account_obj.stellar_account}: {e}')
                sentry_sdk.capture_exception(e)
                self.stdout.write(self.style.ERROR(
                    f'✗ Error: {account_obj.stellar_account}: {str(e)}'
                ))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*60}\n'
            f'BigQuery Pipeline Completed\n'
            f'{"="*60}\n'
            f'Processed: {processed} accounts\n'
            f'Failed: {failed} accounts\n'
            f'{"="*60}\n'
        ))
    
    def _get_pending_accounts(self, limit):
        """Get pending accounts from database."""
        try:
            accounts = StellarCreatorAccountLineage.objects.filter(
                network_name='public',
                status='PENDING'
            ).limit(limit)
            
            return list(accounts)
        except Exception as e:
            logger.error(f'Error fetching pending accounts: {e}')
            sentry_sdk.capture_exception(e)
            return []
    
    def _process_account(self, account_obj, bq_helper):
        """
        Process a single account using MINIMAL BigQuery data + Horizon/Stellar Expert APIs.
        
        BigQuery provides ONLY lineage structure (minimizes costs):
        1. Account creation date
        2. Creator account and creation date
        3. Child accounts
        
        Horizon/Stellar Expert provide account details:
        4. Balance, home_domain, flags (from Horizon)
        5. Assets (from Stellar Expert)
        6. Update database
        """
        account = account_obj.stellar_account
        start_time = datetime.utcnow()
        
        try:
            account_obj.status = 'PROCESSING'
            account_obj.save()
            
            # Step 1: Get account creation date from Horizon API (free, no BigQuery cost)
            self.stdout.write('  → Fetching account creation date from Horizon API...')
            horizon_data = self._fetch_horizon_account_data(account)
            
            if not horizon_data:
                self.stdout.write(self.style.WARNING(
                    '    ⚠ Account not found in Horizon API'
                ))
                account_obj.status = 'INVALID'
                account_obj.save()
                return False
            
            # Extract creation date from Horizon last_modified_time
            creation_date_str = horizon_data.get('last_modified_time', '2015-01-01T00:00:00Z')
            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Account found (last modified: {creation_date_str})'
            ))
            
            account_data = {
                'account_id': account,
                'account_creation_date': creation_date_str
            }
            
            # Calculate safe date window for partition filters (avoids full table scans)
            creation_date_str = account_data.get('account_creation_date', '2015-01-01')
            if 'T' in creation_date_str:
                creation_date = creation_date_str.split('T')[0]  # Extract YYYY-MM-DD
            else:
                creation_date = creation_date_str
            
            # Use creation date minus 7 days as start (safety buffer) and today as end
            try:
                start_dt = datetime.fromisoformat(creation_date.replace('Z', '')) - timedelta(days=7)
                start_date = start_dt.strftime('%Y-%m-%d')
            except:
                start_date = '2015-01-01'  # Fallback to Stellar genesis
            
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
            
            self.stdout.write(self.style.SUCCESS(
                f'    📅 Date window: {start_date} to {end_date}'
            ))
            
            # Step 2: Get creator account from BigQuery (with date filters)
            self.stdout.write('  → Fetching creator from BigQuery...')
            creator_info = bq_helper.get_account_creator(account, start_date=start_date, end_date=end_date)
            
            if creator_info:
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Creator: {creator_info["creator_account"]}'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    '    ⚠ Creator not found (might be root account)'
                ))
            
            # Step 3: Get child accounts from BigQuery (paginated, with date filters)
            self.stdout.write('  → Fetching child accounts from BigQuery...')
            children = self._get_all_child_accounts(bq_helper, account, start_date=start_date, end_date=end_date)
            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Found {len(children)} child accounts'
            ))
            
            # Step 4: Use account details from Horizon API (already fetched in Step 1)
            self.stdout.write('  → Using account details from Horizon API...')
            if horizon_data:
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Balance: {horizon_data.get("balance", 0)} XLM'
                ))
            
            # Step 5: Get assets from Stellar Expert API
            self.stdout.write('  → Fetching assets from Stellar Expert API...')
            assets = self._fetch_stellar_expert_assets(account)
            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Found {len(assets)} assets'
            ))
            
            # Step 6: Update database
            self.stdout.write('  → Updating database...')
            self._update_account_in_database(
                account_obj, 
                account_data, 
                horizon_data,
                assets, 
                creator_info, 
                children,
                start_time
            )
            self.stdout.write(self.style.SUCCESS(
                '    ✓ Database updated'
            ))
            
            # Calculate processing time
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            self.stdout.write(self.style.SUCCESS(
                f'  ⏱ Processing time: {duration:.2f} seconds'
            ))
            
            return True
            
        except Exception as e:
            logger.error(f'Error processing account {account}: {e}')
            sentry_sdk.capture_exception(e)
            
            account_obj.status = 'FAILED'
            account_obj.save()
            return False
    
    def _fetch_horizon_account_data(self, account):
        """
        Fetch account details from Horizon API (balance, home_domain, flags).
        Returns dict with account details or None if fetch fails.
        """
        try:
            from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers, StellarMapHorizonAPIParserHelpers
            
            horizon_helper = StellarMapHorizonAPIHelpers(
                horizon_url='https://horizon.stellar.org',
                account_id=account
            )
            
            account_response = horizon_helper.get_base_accounts()
            
            if not account_response:
                logger.warning(f'Failed to fetch Horizon data for {account}')
                return None
            
            parser = StellarMapHorizonAPIParserHelpers(account_response)
            
            return {
                'balance': parser.parse_account_native_balance(),
                'home_domain': parser.parse_account_home_domain(),
                'flags': account_response.get('flags', {}),
                'thresholds': account_response.get('thresholds', {}),
                'signers': account_response.get('signers', []),
                'sequence': account_response.get('sequence'),
                'subentry_count': account_response.get('subentry_count', 0),
                'num_sponsoring': account_response.get('num_sponsoring', 0),
                'num_sponsored': account_response.get('num_sponsored', 0)
            }
            
        except Exception as e:
            logger.error(f'Error fetching Horizon data for {account}: {e}')
            sentry_sdk.capture_exception(e)
            return None
    
    def _fetch_stellar_expert_assets(self, account):
        """
        Fetch asset holdings from Stellar Expert API.
        Returns list of assets or empty list if fetch fails.
        """
        try:
            from apiApp.helpers.sm_stellarexpert import StellarMapStellarExpertAPIHelpers
            
            expert_helper = StellarMapStellarExpertAPIHelpers(
                stellar_account=account,
                network_name='public'
            )
            
            assets_response = expert_helper.get_se_asset_list()
            
            if not assets_response:
                return []
            
            # Parse and format assets
            assets = []
            if isinstance(assets_response, list):
                for asset in assets_response:
                    if isinstance(asset, dict):
                        assets.append({
                            'asset_code': asset.get('asset_code'),
                            'asset_issuer': asset.get('asset_issuer'),
                            'balance': asset.get('balance', 0),
                            'asset_type': asset.get('asset_type')
                        })
            
            return assets
            
        except Exception as e:
            logger.error(f'Error fetching Stellar Expert assets for {account}: {e}')
            sentry_sdk.capture_exception(e)
            return []
    
    def _update_account_in_database(
        self, 
        account_obj, 
        account_data,  # Minimal BigQuery data (account_id, account_creation_date)
        horizon_data,  # Horizon API data (balance, home_domain, flags)
        assets,  # Stellar Expert assets
        creator_info,  # Creator info from BigQuery (dict with creator_account, created_at)
        children,  # Children from BigQuery
        start_time
    ):
        """
        Update account data in database using combined data from:
        - BigQuery: lineage structure (creation dates, parent-child relationships)
        - Horizon API: account details (balance, home_domain, flags)
        - Stellar Expert: assets
        """
        try:
            # Store account data (combined BigQuery + Horizon)
            account_obj.stellar_account_attributes_json = json.dumps({
                'source': 'bigquery_minimal + horizon + stellar_expert',
                'account_creation_date': account_data.get('account_creation_date'),
                'balance': int(horizon_data.get('balance', 0) * 10000000) if horizon_data else 0,
                'home_domain': horizon_data.get('home_domain', '') if horizon_data else '',
                'flags': horizon_data.get('flags', {}) if horizon_data else {},
                'thresholds': horizon_data.get('thresholds', {}) if horizon_data else {},
                'signers': horizon_data.get('signers', []) if horizon_data else [],
                'sequence': horizon_data.get('sequence') if horizon_data else None,
                'subentry_count': horizon_data.get('subentry_count', 0) if horizon_data else 0,
                'num_sponsoring': horizon_data.get('num_sponsoring', 0) if horizon_data else 0,
                'num_sponsored': horizon_data.get('num_sponsored', 0) if horizon_data else 0
            })
            
            # Store assets (from Stellar Expert)
            account_obj.stellar_account_assets_json = json.dumps({
                'source': 'stellar_expert',
                'count': len(assets),
                'assets': assets
            })
            
            # Store creator (from BigQuery)
            if creator_info:
                account_obj.stellar_creator_account = creator_info['creator_account']
                # Parse datetime string if needed
                created_at_str = creator_info.get('created_at')
                if created_at_str and isinstance(created_at_str, str):
                    from dateutil.parser import parse as parse_datetime
                    account_obj.stellar_account_created_at = parse_datetime(created_at_str)
                else:
                    account_obj.stellar_account_created_at = created_at_str
            elif account_data.get('account_creation_date'):
                # Parse datetime string from BigQuery
                created_date_str = account_data['account_creation_date']
                if isinstance(created_date_str, str):
                    from dateutil.parser import parse as parse_datetime
                    account_obj.stellar_account_created_at = parse_datetime(created_date_str)
                else:
                    account_obj.stellar_account_created_at = created_date_str
            
            # Store child accounts (from BigQuery)
            account_obj.child_accounts_json = json.dumps({
                'source': 'bigquery',
                'count': len(children),
                'children': [
                    {
                        'account': child['account'],
                        'starting_balance': child['starting_balance'],
                        'created_at': child['created_at'],
                        'transaction_hash': child['transaction_hash']
                    }
                    for child in children
                ]
            })
            
            # Calculate flags from Horizon data
            if horizon_data and 'flags' in horizon_data:
                flags = horizon_data['flags']
                if isinstance(flags, dict):
                    account_obj.stellar_flag_auth_required = flags.get('auth_required', False)
                    account_obj.stellar_flag_auth_revocable = flags.get('auth_revocable', False)
                    account_obj.stellar_flag_auth_immutable = flags.get('auth_immutable', False)
                    account_obj.stellar_flag_auth_clawback_enabled = flags.get('auth_clawback_enabled', False)
                elif isinstance(flags, int):
                    # Handle numeric flags
                    account_obj.stellar_flag_auth_required = bool(flags & 1)
                    account_obj.stellar_flag_auth_revocable = bool(flags & 2)
                    account_obj.stellar_flag_auth_immutable = bool(flags & 4)
                    account_obj.stellar_flag_auth_clawback_enabled = bool(flags & 8)
            
            # Update timestamps and status
            account_obj.last_fetched_at = datetime.utcnow()
            account_obj.status = 'BIGQUERY_COMPLETE'
            account_obj.save()
            
            # Queue creator account for processing
            if creator_info:
                self._queue_creator_account(creator_info['creator_account'], account_obj.stellar_account)
            
            # Queue child accounts for processing
            if children:
                self._queue_child_accounts(children, account_obj.stellar_account)
                
        except Exception as e:
            logger.error(f'Error updating database: {e}')
            sentry_sdk.capture_exception(e)
            raise
    
    def _queue_creator_account(self, creator_account, child_account):
        """Add creator account to database for processing."""
        try:
            existing = StellarCreatorAccountLineage.objects.filter(
                stellar_account=creator_account,
                network_name='public'
            ).first()
            
            if not existing:
                StellarCreatorAccountLineage.objects.create(
                    stellar_account=creator_account,
                    network_name='public',
                    status='PENDING',
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Queued creator account {creator_account} for processing'
                ))
                
        except Exception as e:
            logger.error(f'Error queuing creator account {creator_account}: {e}')
    
    def _queue_child_accounts(self, children, parent_account):
        """Add child accounts to database for processing."""
        queued = 0
        
        for child in children:
            try:
                child_account = child['account']
                
                existing = StellarCreatorAccountLineage.objects.filter(
                    stellar_account=child_account,
                    network_name='public'
                ).first()
                
                if not existing:
                    StellarCreatorAccountLineage.objects.create(
                        stellar_account=child_account,
                        network_name='public',
                        stellar_creator_account=parent_account,
                        status='PENDING',
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    queued += 1
                    
            except Exception as e:
                logger.error(f'Error queuing child account {child.get("account")}: {e}')
                continue
        
        if queued > 0:
            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Queued {queued} new child accounts for processing'
            ))
    
    def _get_all_child_accounts(self, bq_helper, account, start_date='2015-01-01', end_date=None):
        """
        Get ALL child accounts for a given parent, handling pagination for high-fanout accounts.
        
        Uses chunked retrieval to avoid BigQuery result limits and ensure complete data.
        Deduplicates results by account address to prevent duplicate entries while allowing
        multiple accounts from the same transaction (common in airdrops).
        
        Args:
            bq_helper: BigQuery helper instance
            account: Parent account address
            start_date: Start date for partition filter (YYYY-MM-DD)
            end_date: End date for partition filter (YYYY-MM-DD)
        """
        all_children = []
        seen_accounts = set()
        page_size = 10000
        offset = 0
        
        while True:
            # Get a page of child accounts with proper offset and date filters
            children_page = bq_helper.get_child_accounts(
                account, 
                limit=page_size,
                offset=offset,
                start_date=start_date,
                end_date=end_date
            )
            
            if not children_page:
                break
            
            # Deduplicate by account address (not tx hash, as one tx can create multiple accounts)
            for child in children_page:
                child_account = child.get('account')
                if child_account and child_account not in seen_accounts:
                    seen_accounts.add(child_account)
                    all_children.append(child)
            
            # If we got fewer than page_size results, we've reached the end
            if len(children_page) < page_size:
                break
            
            offset += page_size
            
            # Safety limit: stop at 100,000 children to avoid runaway queries
            if len(all_children) >= 100000:
                self.stdout.write(self.style.WARNING(
                    f'    ⚠ Reached safety limit of 100,000 children (actual count may be higher)'
                ))
                break
        
        return all_children
    
    def _reset_accounts(self):
        """Reset all accounts to PENDING status."""
        self.stdout.write('Resetting all accounts to PENDING status...')
        
        try:
            accounts = StellarCreatorAccountLineage.objects.filter(
                network_name='public'
            ).limit(10000)
            
            count = 0
            for account in accounts:
                account.status = 'PENDING'
                account.save()
                count += 1
            
            self.stdout.write(self.style.SUCCESS(
                f'✓ Reset {count} accounts to PENDING status'
            ))
            
        except Exception as e:
            logger.error(f'Error resetting accounts: {e}')
            self.stdout.write(self.style.ERROR(
                f'✗ Error: {str(e)}'
            ))
