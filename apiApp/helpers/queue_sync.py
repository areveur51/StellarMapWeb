"""
Queue Synchronizer - Syncs Search Cache PENDING accounts to Lineage table

This helper ensures that user-initiated searches (stored in StellarAccountSearchCache)
are promoted to StellarCreatorAccountLineage where the pipelines can process them.

Architecture:
1. User searches → Creates PENDING in Search Cache
2. Queue Synchronizer (runs before pipeline) → Promotes to Lineage PENDING
3. Pipeline processes → Updates Lineage status
4. Pipeline completion hook → Syncs status back to Search Cache

This ensures both tables stay in sync and all searches get processed.
"""

import logging
from datetime import datetime
from apiApp.model_loader import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    USE_CASSANDRA,
)

logger = logging.getLogger(__name__)


class QueueSynchronizer:
    """Synchronizes PENDING accounts from Search Cache to Lineage table."""
    
    @staticmethod
    def sync_pending_to_lineage(network='public', max_accounts=100):
        """
        Promote PENDING accounts from Search Cache to Lineage table.
        
        This runs before pipeline execution to ensure user searches are queued
        for processing.
        
        Args:
            network (str): Network name ('public' or 'testnet')
            max_accounts (int): Maximum accounts to sync per run
        
        Returns:
            dict: Summary of sync operation
                {
                    'promoted': int,  # New accounts added to Lineage
                    'already_exists': int,  # Already in Lineage
                    'errors': int,  # Errors during sync
                }
        """
        promoted = 0
        already_exists = 0
        errors = 0
        
        try:
            # Get PENDING accounts from Search Cache
            pending_cache_records = list(
                StellarAccountSearchCache.objects.filter(
                    network_name=network,
                    status='PENDING'
                ).all()
            )
            
            # Limit batch size
            pending_cache_records = pending_cache_records[:max_accounts]
            
            logger.info(f'Queue Sync: Found {len(pending_cache_records)} PENDING in Search Cache')
            
            for cache_record in pending_cache_records:
                try:
                    # Check if already exists in Lineage
                    lineage_record = StellarCreatorAccountLineage.objects.filter(
                        stellar_account=cache_record.stellar_account,
                        network_name=cache_record.network_name
                    ).first()
                    
                    if lineage_record:
                        already_exists += 1
                        logger.debug(
                            f'Queue Sync: {cache_record.stellar_account[:8]}... '
                            f'already in Lineage (status: {lineage_record.status})'
                        )
                    else:
                        # Create new PENDING record in Lineage
                        StellarCreatorAccountLineage.create(
                            stellar_account=cache_record.stellar_account,
                            network_name=cache_record.network_name,
                            status='PENDING',
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                            notes=f'Promoted from Search Cache (user search at {cache_record.created_at})'
                        )
                        promoted += 1
                        logger.info(
                            f'Queue Sync: ✓ Promoted {cache_record.stellar_account[:8]}... '
                            f'to Lineage'
                        )
                        
                except Exception as e:
                    errors += 1
                    logger.error(
                        f'Queue Sync: Error syncing {cache_record.stellar_account[:8]}...: {e}'
                    )
            
            logger.info(
                f'Queue Sync Complete: {promoted} promoted, '
                f'{already_exists} already exist, {errors} errors'
            )
            
            return {
                'promoted': promoted,
                'already_exists': already_exists,
                'errors': errors,
            }
            
        except Exception as e:
            logger.error(f'Queue Sync: Fatal error during sync: {e}')
            return {
                'promoted': 0,
                'already_exists': 0,
                'errors': 1,
            }
    
    @staticmethod
    def sync_status_back_to_cache(stellar_account, network_name, status, cached_json=None):
        """
        Update Search Cache status when Lineage processing completes.
        
        This is called by pipeline completion hooks to keep Search Cache in sync.
        
        Args:
            stellar_account (str): Stellar account address
            network_name (str): Network name
            status (str): New status from Lineage
            cached_json (dict, optional): Result data to cache
        
        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            # Find corresponding Search Cache record
            cache_record = StellarAccountSearchCache.objects.filter(
                stellar_account=stellar_account,
                network_name=network_name
            ).first()
            
            if not cache_record:
                logger.debug(
                    f'Sync Back: No Search Cache record for {stellar_account[:8]}... '
                    f'(likely from Bulk Search or child discovery)'
                )
                return False
            
            # Map Lineage statuses to Search Cache statuses
            status_map = {
                'BIGQUERY_COMPLETE': 'DONE_MAKE_PARENT_LINEAGE',
                'API_COMPLETE': 'DONE_MAKE_PARENT_LINEAGE',
                'DONE_MAKE_PARENT_LINEAGE': 'DONE_MAKE_PARENT_LINEAGE',
                'PENDING': 'PENDING',
                'PROCESSING': 'IN_PROGRESS_MAKE_PARENT_LINEAGE',
                'IN_PROGRESS': 'IN_PROGRESS_MAKE_PARENT_LINEAGE',
                'ERROR': 'ERROR',
                'FAILED': 'FAILED',
                'INVALID': 'INVALID',
            }
            
            cache_status = status_map.get(status, status)
            
            # Update cache record
            old_status = cache_record.status
            cache_record.status = cache_status
            cache_record.updated_at = datetime.utcnow()
            
            if cached_json:
                cache_record.cached_json = str(cached_json)
            
            cache_record.save()
            
            logger.info(
                f'Sync Back: ✓ Updated Search Cache {stellar_account[:8]}... '
                f'{old_status} → {cache_status}'
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f'Sync Back: Error updating Search Cache for {stellar_account[:8]}...: {e}'
            )
            return False
