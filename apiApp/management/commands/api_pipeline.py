"""
API Pipeline - Consistent PENDING Record Processing

This pipeline uses ONLY Horizon API and Stellar Expert to process PENDING records.
It runs independently of the BigQuery pipeline to ensure consistent data retrieval
even when BigQuery cost guard blocks queries.

Key Features:
- Rate-limited API calls to respect external API limits
- Processes small batches (default: 3 accounts per run)
- Runs frequently (every 2 minutes) for continuous processing
- No BigQuery dependency or costs
- Fallback pipeline for reliable PENDING record processing

Use Cases:
- When BigQuery pipeline is blocked by cost guard
- For continuous slow processing of PENDING backlog
- As reliable fallback for critical accounts
"""

import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from apiApp.model_loader import StellarCreatorAccountLineage, BigQueryPipelineConfig
from apiApp.helpers.env import EnvHelpers
from apiApp.helpers.api_rate_limiter import APIRateLimiter
from apiApp.helpers.queue_sync import QueueSynchronizer
import sentry_sdk

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'API Pipeline - Process PENDING accounts using API-only approach (rate-limited)'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.env_helpers = EnvHelpers()
        self.env_helpers.set_public_network()
        self.rate_limiter = APIRateLimiter(enable_logging=True)

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=3,
            help='Maximum number of accounts to process per run (default: 3 for slow continuous processing)'
        )
        parser.add_argument(
            '--skip-stuck-check',
            action='store_true',
            help='Skip check for stuck PROCESSING records and process only PENDING'
        )
    
    def handle(self, *args, **options):
        """
        Process PENDING accounts using API-only approach with rate limiting.
        """
        limit = options['limit']
        skip_stuck_check = options['skip_stuck_check']
        
        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*60}\n'
            f'API Pipeline - Rate-Limited PENDING Processing\n'
            f'{"="*60}\n'
            f'Batch Size: {limit} accounts\n'
            f'Rate Limits: Horizon (1 req/0.5s), Expert (1 req/1s)\n'
            f'{"="*60}\n'
        ))
        
        # Recover stuck PROCESSING records first (unless skipped)
        if not skip_stuck_check:
            self._recover_stuck_records()
        
        # Sync Search Cache PENDING accounts to Lineage (Queue Synchronizer)
        self.stdout.write('\n[Queue Sync] Syncing Search Cache → Lineage...')
        sync_result = QueueSynchronizer.sync_pending_to_lineage(network='public', max_accounts=limit)
        if sync_result['promoted'] > 0:
            self.stdout.write(self.style.SUCCESS(
                f"[Queue Sync] ✓ Promoted {sync_result['promoted']} accounts from Search Cache to Lineage"
            ))
        
        # Get PENDING accounts to process
        accounts = self._get_pending_accounts(limit)
        
        if not accounts:
            self.stdout.write(self.style.WARNING('No PENDING accounts found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Found {len(accounts)} PENDING accounts to process\n'))
        
        # Process each account
        processed = 0
        failed = 0
        
        for account_obj in accounts:
            try:
                self.stdout.write(self.style.WARNING(
                    f'\n[{processed + failed + 1}/{len(accounts)}] Processing {account_obj.stellar_account}...'
                ))
                
                success = self._process_account(account_obj)
                
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
            f'API Pipeline Completed\n'
            f'{"="*60}\n'
            f'Processed: {processed} accounts\n'
            f'Failed: {failed} accounts\n'
            f'Pipeline Source: API\n'
            f'{"="*60}\n'
        ))
    
    def _recover_stuck_records(self):
        """
        Recover accounts stuck in PROCESSING state for more than 5 minutes.
        These are likely from crashed pipeline runs.
        """
        try:
            from apiApp.models_cassandra import STUCK_THRESHOLD_MINUTES
            
            stuck_threshold = datetime.utcnow() - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
            
            stuck_accounts = StellarCreatorAccountLineage.objects.filter(
                network_name='public',
                status='PROCESSING'
            ).all()
            
            recovered = 0
            for account in stuck_accounts:
                if account.processing_started_at and account.processing_started_at < stuck_threshold:
                    account.status = 'PENDING'
                    account.retry_count += 1
                    account.last_error = f'Recovered from stuck PROCESSING state (started at {account.processing_started_at})'
                    account.save()
                    recovered += 1
            
            if recovered > 0:
                self.stdout.write(self.style.WARNING(
                    f'Recovered {recovered} stuck PROCESSING records → PENDING'
                ))
                
        except Exception as e:
            logger.error(f'Error recovering stuck records: {e}')
            sentry_sdk.capture_exception(e)
    
    def _get_pending_accounts(self, limit):
        """Get PENDING accounts from database, prioritizing older attempts."""
        try:
            accounts = StellarCreatorAccountLineage.objects.filter(
                network_name='public',
                status='PENDING'
            ).limit(limit)
            
            return list(accounts)
        except Exception as e:
            logger.error(f'Error fetching PENDING accounts: {e}')
            sentry_sdk.capture_exception(e)
            return []
    
    def _process_account(self, account_obj):
        """
        Process a single account using API-only approach.
        
        Steps:
        1. Fetch account data from Horizon API (balance, flags)
        2. Fetch creator from Horizon operations or Stellar Expert
        3. Fetch child accounts from Horizon operations
        4. Fetch assets from Stellar Expert
        5. Update database
        """
        account = account_obj.stellar_account
        start_time = datetime.utcnow()
        
        try:
            # Mark as PROCESSING and record start time
            account_obj.status = 'PROCESSING'
            account_obj.processing_started_at = start_time
            account_obj.last_pipeline_attempt = start_time
            account_obj.save()
            
            # Step 1: Get account data from Horizon API
            self.stdout.write('  → Fetching account data from Horizon API...')
            self.rate_limiter.wait_for_horizon()
            horizon_data = self._fetch_horizon_account_data(account)
            
            if not horizon_data:
                self.stdout.write(self.style.WARNING('    ⚠ Account not found in Horizon API'))
                account_obj.status = 'INVALID'
                account_obj.save()
                return False
            
            creation_date_str = horizon_data.get('last_modified_time', '2015-01-01T00:00:00Z')
            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Balance: {horizon_data.get("balance", 0)} XLM'
            ))
            
            # Step 2: Get creator account
            self.stdout.write('  → Fetching creator from Horizon API...')
            self.rate_limiter.wait_for_horizon()
            creator_info = self._get_creator_from_api(account)
            
            if creator_info:
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Creator: {creator_info["creator_account"]}'
                ))
            else:
                self.stdout.write(self.style.WARNING('    ⚠ Creator not found'))
            
            # Step 3: Get child accounts
            self.stdout.write('  → Fetching child accounts from Horizon API...')
            self.rate_limiter.wait_for_horizon()
            children = self._get_children_from_api(account)
            
            if children:
                self.stdout.write(self.style.SUCCESS(f'    ✓ Found {len(children)} children'))
            
            # Step 4: Get assets from Stellar Expert
            self.stdout.write('  → Fetching assets from Stellar Expert API...')
            self.rate_limiter.wait_for_stellar_expert()
            assets = self._fetch_stellar_expert_assets(account)
            
            self.stdout.write(self.style.SUCCESS(f'    ✓ Found {len(assets)} assets'))
            
            # Step 5: Update database
            self.stdout.write('  → Updating database...')
            self._update_account_in_database(
                account_obj,
                {'account_id': account, 'account_creation_date': creation_date_str},
                horizon_data,
                assets,
                creator_info,
                children,
                start_time
            )
            
            self.stdout.write(self.style.SUCCESS('    ✓ Database updated'))
            
            # Calculate processing time
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            self.stdout.write(self.style.SUCCESS(f'  ⏱ Processing time: {duration:.2f} seconds'))
            
            return True
            
        except Exception as e:
            logger.error(f'Error processing account {account}: {e}')
            sentry_sdk.capture_exception(e)
            
            account_obj.status = 'FAILED'
            account_obj.last_error = str(e)
            account_obj.retry_count += 1
            account_obj.save()
            
            # Sync error status back to Search Cache
            QueueSynchronizer.sync_status_back_to_cache(
                stellar_account=account_obj.stellar_account,
                network_name=account_obj.network_name,
                status='FAILED'
            )
            
            return False
    
    def _fetch_horizon_account_data(self, account):
        """Fetch account details from Horizon API."""
        try:
            from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers, StellarMapHorizonAPIParserHelpers
            
            horizon_helper = StellarMapHorizonAPIHelpers(
                horizon_url=self.env_helpers.get_base_horizon(),
                account_id=account
            )
            
            account_response = horizon_helper.get_base_accounts()
            
            if not account_response:
                return None
            
            parser = StellarMapHorizonAPIParserHelpers(account_response)
            
            return {
                'balance': parser.parse_account_native_balance(),
                'home_domain': parser.parse_account_home_domain(),
                'last_modified_time': account_response.get('last_modified_time', ''),
                'flags': account_response.get('flags', {}),
                'thresholds': account_response.get('thresholds', {}),
                'signers': account_response.get('signers', []),
                'sequence': account_response.get('sequence'),
                'subentry_count': account_response.get('subentry_count', 0),
            }
            
        except Exception as e:
            logger.error(f'Error fetching Horizon data for {account}: {e}')
            return None
    
    def _get_creator_from_api(self, account):
        """Get creator using Horizon operations API + Stellar Expert fallback."""
        try:
            from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers, StellarMapHorizonAPIParserHelpers
            from apiApp.helpers.sm_stellarexpert import (
                StellarMapStellarExpertAPIHelpers,
                StellarMapStellarExpertAPIParserHelpers
            )
            
            # Try Horizon operations first
            horizon_helper = StellarMapHorizonAPIHelpers(
                horizon_url=self.env_helpers.get_base_horizon(),
                account_id=account
            )
            
            operations_response = horizon_helper.get_account_operations(order='asc', limit=200)
            
            if operations_response:
                parser = StellarMapHorizonAPIParserHelpers({'data': {'raw_data': operations_response}})
                creator_data = parser.parse_operations_creator_account(account)
                
                if creator_data and creator_data.get('funder'):
                    return {
                        'creator_account': creator_data['funder'],
                        'created_at': creator_data.get('created_at').isoformat() if creator_data.get('created_at') else None
                    }
            
            # Fallback to Stellar Expert
            self.stdout.write(self.style.WARNING('    → Falling back to Stellar Expert...'))
            self.rate_limiter.wait_for_stellar_expert()
            
            expert_helper = StellarMapStellarExpertAPIHelpers(
                stellar_account=account,
                network_name='public'
            )
            
            expert_data = expert_helper.get_account()
            
            if expert_data:
                expert_parser = StellarMapStellarExpertAPIParserHelpers({'data': {'raw_data': expert_data}})
                return {
                    'creator_account': expert_parser.parse_account_creator(),
                    'created_at': expert_parser.parse_account_created_at()
                }
            
            return None
            
        except Exception as e:
            logger.error(f'Error fetching creator for {account}: {e}')
            return None
    
    def _get_children_from_api(self, account):
        """Get child accounts using Horizon operations API."""
        try:
            from apiApp.helpers.sm_horizon import StellarMapHorizonAPIHelpers
            
            horizon_helper = StellarMapHorizonAPIHelpers(
                horizon_url=self.env_helpers.get_base_horizon(),
                account_id=account
            )
            
            child_accounts_raw = horizon_helper.get_child_accounts(max_pages=5)
            
            if child_accounts_raw:
                return [child['account'] for child in child_accounts_raw if 'account' in child]
            
            return []
            
        except Exception as e:
            logger.error(f'Error fetching children for {account}: {e}')
            return []
    
    def _fetch_stellar_expert_assets(self, account):
        """Fetch asset holdings from Stellar Expert API."""
        try:
            from apiApp.helpers.sm_stellarexpert import (
                StellarMapStellarExpertAPIHelpers,
                StellarMapStellarExpertAPIParserHelpers
            )
            
            expert_helper = StellarMapStellarExpertAPIHelpers(
                stellar_account=account,
                network_name='public'
            )
            
            account_data = expert_helper.get_account()
            
            if account_data:
                parser = StellarMapStellarExpertAPIParserHelpers({'data': {'raw_data': account_data}})
                return parser.parse_account_assets()
            
            return []
            
        except Exception as e:
            logger.error(f'Error fetching assets for {account}: {e}')
            return []
    
    def _update_account_in_database(self, account_obj, account_data, horizon_data, assets, creator_info, children, start_time):
        """Update account record in database with API-sourced data."""
        try:
            import json
            
            # Update basic account info - parse datetime string to datetime object
            created_at_str = account_data.get('account_creation_date')
            if created_at_str:
                # Parse ISO 8601 datetime string (e.g., '2025-03-09T05:18:48Z')
                # Replace 'Z' with '+00:00' for Python's fromisoformat()
                created_at_str = created_at_str.replace('Z', '+00:00')
                account_obj.stellar_account_created_at = datetime.fromisoformat(created_at_str)
            else:
                account_obj.stellar_account_created_at = None
                
            account_obj.xlm_balance = horizon_data.get('balance', 0.0)
            account_obj.home_domain = horizon_data.get('home_domain', '')
            
            # Update creator info
            if creator_info:
                account_obj.stellar_creator_account = creator_info.get('creator_account', '')
            
            # Store JSON data
            account_obj.stellar_account_attributes_json = json.dumps({
                'flags': horizon_data.get('flags', {}),
                'thresholds': horizon_data.get('thresholds', {}),
                'signers': horizon_data.get('signers', []),
                'sequence': horizon_data.get('sequence'),
                'subentry_count': horizon_data.get('subentry_count', 0),
            })
            
            account_obj.stellar_account_assets_json = json.dumps(assets)
            account_obj.child_accounts_json = json.dumps(children)
            
            # Mark pipeline source as API
            account_obj.pipeline_source = 'API'
            account_obj.status = 'COMPLETE'
            account_obj.last_error = ''
            account_obj.processing_started_at = None
            
            account_obj.save()
            
            # Sync status back to Search Cache (if record exists there)
            QueueSynchronizer.sync_status_back_to_cache(
                stellar_account=account_obj.stellar_account,
                network_name=account_obj.network_name,
                status='API_COMPLETE',
                cached_json={
                    'xlm_balance': float(account_obj.xlm_balance or 0),
                    'creator_account': account_obj.stellar_creator_account,
                    'home_domain': account_obj.home_domain,
                    'pipeline_source': 'API',
                }
            )
            
            # Queue creator account for processing (expand lineage graph)
            if creator_info and creator_info.get('creator_account'):
                self._queue_creator_account(creator_info['creator_account'], account_obj.stellar_account)
            
            # Queue child accounts for processing (expand lineage graph)
            if children:
                self._queue_child_accounts(children, account_obj.stellar_account)
            
        except Exception as e:
            logger.error(f'Error updating database for {account_obj.stellar_account}: {e}')
            sentry_sdk.capture_exception(e)
            raise
    
    def _queue_creator_account(self, creator_account, child_account):
        """
        Queue creator account for processing to expand lineage graph.
        
        Unlike BigQuery pipeline, API pipeline can process accounts of any age,
        so no age-based filtering is needed.
        """
        try:
            existing = StellarCreatorAccountLineage.objects.filter(
                stellar_account=creator_account,
                network_name='public'
            ).first()
            
            if not existing:
                StellarCreatorAccountLineage.create(
                    stellar_account=creator_account,
                    network_name='public',
                    status='PENDING',
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Queued creator account {creator_account[:8]}... for processing'
                ))
            else:
                logger.debug(f'Creator {creator_account[:8]}... already exists in database')
                
        except Exception as e:
            logger.error(f'Error queuing creator account {creator_account}: {e}')
    
    def _queue_child_accounts(self, children, parent_account):
        """
        Queue child accounts for processing to expand lineage graph.
        
        Args:
            children: List of child account addresses (strings)
            parent_account: Parent account address
        """
        queued = 0
        
        for child_account in children:
            try:
                existing = StellarCreatorAccountLineage.objects.filter(
                    stellar_account=child_account,
                    network_name='public'
                ).first()
                
                if not existing:
                    StellarCreatorAccountLineage.create(
                        stellar_account=child_account,
                        network_name='public',
                        stellar_creator_account=parent_account,
                        status='PENDING',
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    queued += 1
                    
            except Exception as e:
                logger.error(f'Error queuing child account {child_account}: {e}')
                continue
        
        if queued > 0:
            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Queued {queued} new child accounts for processing'
            ))
