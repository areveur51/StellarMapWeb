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
from datetime import datetime
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
        Process a single account using BigQuery.
        
        Steps:
        1. Get account data (balance, flags)
        2. Get asset holdings
        3. Get creator account
        4. Get child accounts
        5. Update database
        """
        account = account_obj.stellar_account
        start_time = datetime.utcnow()
        
        try:
            account_obj.status = 'PROCESSING'
            account_obj.save()
            
            # Step 1: Get account data
            self.stdout.write('  → Fetching account data from BigQuery...')
            account_data = bq_helper.get_account_data(account)
            
            if not account_data:
                self.stdout.write(self.style.WARNING(
                    '    ⚠ Account not found in BigQuery accounts_current table'
                ))
                account_obj.status = 'INVALID'
                account_obj.save()
                return False
            
            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Balance: {account_data["balance"]} stroops'
            ))
            
            # Step 2: Get asset holdings
            self.stdout.write('  → Fetching asset holdings from BigQuery...')
            assets = bq_helper.get_account_assets(account)
            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Found {len(assets)} assets'
            ))
            
            # Step 3: Get creator account
            self.stdout.write('  → Fetching creator account from BigQuery...')
            creator = bq_helper.get_account_creator(account)
            
            if creator:
                self.stdout.write(self.style.SUCCESS(
                    f'    ✓ Creator: {creator}'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    '    ⚠ Creator not found (might be root account)'
                ))
            
            # Step 4: Get child accounts (paginated for high-fanout accounts)
            self.stdout.write('  → Fetching child accounts from BigQuery...')
            children = self._get_all_child_accounts(bq_helper, account)
            self.stdout.write(self.style.SUCCESS(
                f'    ✓ Found {len(children)} child accounts'
            ))
            
            # Step 5: Update database
            self.stdout.write('  → Updating database...')
            self._update_account_in_database(
                account_obj, 
                account_data, 
                assets, 
                creator, 
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
    
    def _update_account_in_database(
        self, 
        account_obj, 
        account_data, 
        assets, 
        creator, 
        children,
        start_time
    ):
        """Update account data in database."""
        try:
            # Store account data
            account_obj.stellar_account_attributes_json = json.dumps({
                'source': 'bigquery',
                'balance': account_data['balance'],
                'flags': account_data['flags'],
                'home_domain': account_data['home_domain'],
                'thresholds': {
                    'low': account_data['threshold_low'],
                    'medium': account_data['threshold_medium'],
                    'high': account_data['threshold_high']
                },
                'master_weight': account_data['master_weight'],
                'num_subentries': account_data['num_subentries'],
                'num_sponsored': account_data['num_sponsored'],
                'num_sponsoring': account_data['num_sponsoring'],
                'sequence': account_data['sequence_number'],
                'last_modified_ledger': account_data['last_modified_ledger'],
                'batch_run_date': account_data['batch_run_date']
            })
            
            # Store assets
            account_obj.stellar_account_assets_json = json.dumps({
                'source': 'bigquery',
                'count': len(assets),
                'assets': assets
            })
            
            # Store creator
            if creator:
                account_obj.stellar_creator_account = creator
            
            # Store child accounts
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
            
            # Calculate flags
            account_obj.stellar_flag_auth_required = bool(account_data['flags'] & 1)
            account_obj.stellar_flag_auth_revocable = bool(account_data['flags'] & 2)
            account_obj.stellar_flag_auth_immutable = bool(account_data['flags'] & 4)
            account_obj.stellar_flag_auth_clawback_enabled = bool(account_data['flags'] & 8)
            
            # Update timestamps and status
            account_obj.last_fetched_at = datetime.utcnow()
            account_obj.status = 'BIGQUERY_COMPLETE'
            account_obj.save()
            
            # Queue child accounts for processing
            if children:
                self._queue_child_accounts(children, account_obj.stellar_account)
                
        except Exception as e:
            logger.error(f'Error updating database: {e}')
            sentry_sdk.capture_exception(e)
            raise
    
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
    
    def _get_all_child_accounts(self, bq_helper, account):
        """
        Get ALL child accounts for a given parent, handling pagination for high-fanout accounts.
        
        Uses chunked retrieval to avoid BigQuery result limits and ensure complete data.
        Deduplicates results by account address to prevent duplicate entries while allowing
        multiple accounts from the same transaction (common in airdrops).
        """
        all_children = []
        seen_accounts = set()
        page_size = 10000
        offset = 0
        
        while True:
            # Get a page of child accounts with proper offset
            children_page = bq_helper.get_child_accounts(
                account, 
                limit=page_size,
                offset=offset
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
