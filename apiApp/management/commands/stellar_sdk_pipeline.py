"""
Stellar SDK Pipeline - Fast, Free, Concurrent Account Processing

This pipeline uses the native Stellar Python SDK with async/await for efficient
concurrent account processing. It's faster than the API pipeline and free unlike BigQuery.

Key Features:
- Concurrent processing of multiple accounts (3-5 at once)
- Built-in rate limiting (respects Horizon's 3600 req/hour)
- Automatic retries with exponential backoff
- Creator and child account discovery
- Zero cost (free Horizon API)

Performance:
- 30-60 seconds per account (vs 2-3 min API pipeline)
- Can process 3-5 accounts concurrently
- Free (vs $0.0001-0.0002 per account BigQuery)
"""

import asyncio
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from apiApp.model_loader import StellarCreatorAccountLineage, PENDING, PROCESSING, COMPLETE, FAILED, PUBLIC
from apiApp.helpers.sm_stellar_sdk import StellarSDKHelper, SDKRateLimiter
from apiApp.helpers.queue_sync import QueueSynchronizer
from apiApp.helpers.sm_stellarexpert import StellarMapStellarExpertAPIHelpers
from apiApp.helpers.env import EnvHelpers
import sentry_sdk

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Stellar SDK Pipeline - Process accounts using native SDK with async/await'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.env_helpers = EnvHelpers()
        self.rate_limiter = SDKRateLimiter()
        self.stats = {
            'processed': 0,
            'failed': 0,
            'skipped': 0
        }
        self.network = 'public'  # Will be set properly in handle()

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of accounts to process per run (default: 10)'
        )
        parser.add_argument(
            '--concurrent',
            type=int,
            default=5,
            help='Maximum concurrent account processing (default: 5, respects rate limits)'
        )
        parser.add_argument(
            '--network',
            type=str,
            default='public',
            choices=['public', 'testnet'],
            help='Stellar network to use (default: public)'
        )

    def handle(self, *args, **options):
        """Process accounts using Stellar SDK with concurrent async."""
        limit = options['limit']
        max_concurrent = options['concurrent']
        network = options['network']
        
        # Set network properly based on argument
        self.network = network
        if network == 'public':
            self.env_helpers.set_public_network()
        else:
            self.env_helpers.set_testnet_network()

        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*60}\n'
            f'Stellar SDK Pipeline Started\n'
            f'{"="*60}\n'
            f'Strategy: Concurrent async processing with native SDK\n'
            f'Network: {network}\n'
            f'Max accounts: {limit}\n'
            f'Max concurrent: {max_concurrent}\n'
            f'Rate limit: 3600 req/hour (Horizon standard)\n'
            f'{"="*60}\n'
        ))

        # Sync Search Cache PENDING accounts to Lineage (Queue Synchronizer)
        self.stdout.write('\n[Queue Sync] Syncing Search Cache → Lineage...')
        sync_result = QueueSynchronizer.sync_pending_to_lineage(network=network, max_accounts=limit)
        if sync_result['promoted'] > 0:
            self.stdout.write(self.style.SUCCESS(
                f"[Queue Sync] ✓ Promoted {sync_result['promoted']} accounts from Search Cache to Lineage"
            ))

        # Get pending accounts
        pending_accounts = self._get_pending_accounts(limit, network)

        if not pending_accounts:
            self.stdout.write(self.style.SUCCESS('No pending accounts to process'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Found {len(pending_accounts)} pending accounts to process\n'
        ))

        # Get Horizon URL for this network
        horizon_url = self.env_helpers.get_base_horizon()

        # Process accounts asynchronously
        asyncio.run(self._process_accounts_async(pending_accounts, horizon_url, max_concurrent))

        # Print summary
        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*60}\n'
            f'Stellar SDK Pipeline Completed\n'
            f'{"="*60}\n'
            f'Processed: {self.stats["processed"]} accounts\n'
            f'Failed: {self.stats["failed"]} accounts\n'
            f'Skipped: {self.stats["skipped"]} accounts\n'
            f'{"="*60}\n'
        ))

        # Show rate limiter stats
        rate_stats = self.rate_limiter.get_stats()
        self.stdout.write(self.style.SUCCESS(
            f'Rate Limiter Stats:\n'
            f'  Requests in window: {rate_stats["requests_in_window"]}/{rate_stats["max_requests"]}\n'
            f'  Remaining: {rate_stats["remaining"]}\n'
        ))

    def _get_pending_accounts(self, limit, network):
        """Get pending accounts from database."""
        try:
            accounts = StellarCreatorAccountLineage.objects.filter(
                network_name=network,
                status=PENDING
            ).limit(limit)

            return list(accounts)
        except Exception as e:
            logger.error(f'Error fetching pending accounts: {e}')
            sentry_sdk.capture_exception(e)
            return []

    async def _process_accounts_async(self, pending_accounts, horizon_url, max_concurrent):
        """Process accounts concurrently using async SDK."""
        async with StellarSDKHelper(horizon_url, self.rate_limiter) as sdk_helper:
            # Group accounts into batches for concurrent processing
            for i in range(0, len(pending_accounts), max_concurrent):
                batch = pending_accounts[i:i+max_concurrent]
                
                self.stdout.write(f'\n{"="*60}')
                self.stdout.write(f'Processing batch {i//max_concurrent + 1} ({len(batch)} accounts)')
                self.stdout.write(f'{"="*60}')
                
                # Process batch concurrently
                tasks = [self._process_single_account(account_obj, sdk_helper) for account_obj in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_single_account(self, account_obj, sdk_helper):
        """Process a single account using SDK helper."""
        account = account_obj.stellar_account
        start_time = datetime.utcnow()

        try:
            self.stdout.write(f'\n  → Processing: {account}')

            # Update status to PROCESSING
            account_obj.status = PROCESSING
            account_obj.processing_started_at = start_time
            account_obj.last_pipeline_attempt = start_time
            account_obj.save()

            # Enrich account with SDK (gets balance, creator, children, etc.)
            enriched_data = await sdk_helper.enrich_account(account)

            if not enriched_data:
                self.stdout.write(self.style.WARNING(
                    f'    ⚠ Account not found: {account}'
                ))
                account_obj.status = 'INVALID'
                account_obj.save()
                self.stats['failed'] += 1
                return False

            # Log what we found
            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Balance: {enriched_data["xlm_balance"]:.2f} XLM'
            ))

            if enriched_data['creator_account']:
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Creator: {enriched_data["creator_account"]}'
                ))
                
                # Queue creator for processing if not already in system
                await self._queue_account_if_needed(enriched_data['creator_account'], account_obj.network_name)

            if enriched_data['num_children'] > 0:
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Found {enriched_data["num_children"]} child accounts'
                ))
                
                # Queue children for processing
                for child in enriched_data['children']:
                    await self._queue_account_if_needed(child['account'], account_obj.network_name)

            # Get assets from Stellar Expert API (for consistency with other pipelines)
            self.stdout.write('    → Fetching assets from Stellar Expert...')
            assets = await self._fetch_stellar_expert_assets(account)
            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Found {len(assets)} assets'
            ))

            # Update database
            self._update_account_in_database(account_obj, enriched_data, assets)

            # Mark as complete
            account_obj.status = COMPLETE
            account_obj.processing_completed_at = datetime.utcnow()
            processing_time = (account_obj.processing_completed_at - account_obj.processing_started_at).total_seconds()
            account_obj.processing_time_seconds = int(processing_time)
            account_obj.save()

            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Completed in {processing_time:.1f}s'
            ))
            self.stats['processed'] += 1
            return True

        except Exception as e:
            logger.error(f'Error processing {account}: {e}')
            sentry_sdk.capture_exception(e)
            
            account_obj.status = FAILED
            account_obj.error_message = str(e)[:500]
            account_obj.save()
            
            self.stdout.write(self.style.ERROR(
                f'    ✗ Error: {str(e)}'
            ))
            self.stats['failed'] += 1
            return False

    async def _queue_account_if_needed(self, account_id, network):
        """Queue account for processing if it doesn't exist in the database."""
        try:
            # Check if account already exists
            existing = StellarCreatorAccountLineage.objects.filter(
                stellar_account=account_id,
                network_name=network
            ).first()

            if not existing:
                # Create new pending account
                StellarCreatorAccountLineage.create(
                    stellar_account=account_id,
                    network_name=network,
                    status=PENDING
                )
                logger.info(f'Queued new account for processing: {account_id}')

        except Exception as e:
            logger.error(f'Error queuing account {account_id}: {e}')
            sentry_sdk.capture_exception(e)

    async def _fetch_stellar_expert_assets(self, account):
        """Fetch asset holdings from Stellar Expert API."""
        try:
            # Use Stellar Expert API helper (synchronous, but fast)
            # Use self.network to ensure we're using the correct network
            se_helper = StellarMapStellarExpertAPIHelpers(stellar_account=account, network_name=self.network)
            response = se_helper.get_se_asset_list()

            if not response or 'error' in response:
                return []

            # Stellar Expert returns trustlines in _embedded.records
            assets = []
            if '_embedded' in response and 'records' in response['_embedded']:
                for record in response['_embedded']['records']:
                    # Stellar Expert format
                    assets.append({
                        'asset_code': record.get('asset_code', ''),
                        'asset_issuer': record.get('asset_issuer', ''),
                        'balance': record.get('balance', '0'),
                        'limit': record.get('limit', ''),
                        'flags': record.get('flags', 0)
                    })

            return assets

        except Exception as e:
            logger.error(f'Error fetching Stellar Expert assets for {account}: {e}')
            sentry_sdk.capture_exception(e)
            return []

    def _update_account_in_database(self, account_obj, enriched_data, assets):
        """Update account in database with enriched data."""
        try:
            # Update account fields
            account_obj.xlm_balance = enriched_data['xlm_balance']
            account_obj.home_domain = enriched_data.get('home_domain', '')
            
            # Set pipeline source to SDK
            account_obj.pipeline_source = 'SDK'
            
            # Set creator
            if enriched_data['creator_account']:
                account_obj.stellar_creator_account = enriched_data['creator_account']
            
            if enriched_data['created_at']:
                account_obj.account_created_at = enriched_data['created_at']
            
            # Set children count
            account_obj.num_child_accounts = enriched_data['num_children']
            
            # Set HVA flag (>1M XLM)
            account_obj.is_hva = enriched_data['xlm_balance'] > 1000000
            
            # Store flags as JSON
            account_obj.flags = enriched_data.get('flags', {})
            
            # Store assets as JSON
            account_obj.trustlines = assets
            account_obj.trustline_count = len(assets)
            
            # Update timestamp
            account_obj.updated_at = datetime.utcnow()
            
            account_obj.save()

        except Exception as e:
            logger.error(f'Error updating database for {account_obj.stellar_account}: {e}')
            sentry_sdk.capture_exception(e)
            raise
