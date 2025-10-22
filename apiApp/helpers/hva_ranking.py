"""
HVA (High Value Account) Ranking Helper

Provides utilities for:
- Calculating current HVA rankings based on XLM balance
- Detecting ranking changes and recording events
- Efficient change tracking without full snapshots
"""

import logging
from uuid import uuid1
from datetime import timedelta
from django.utils import timezone
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class HVARankingHelper:
    """Helper class for HVA leaderboard ranking calculations and change tracking."""
    
    # Default supported HVA thresholds (in XLM) - can be overridden in admin config
    DEFAULT_SUPPORTED_THRESHOLDS = [10000, 50000, 100000, 500000, 750000, 1000000]
    
    # Significant balance change threshold (percentage)
    SIGNIFICANT_BALANCE_CHANGE_PCT = 5.0  # 5%
    
    # Minimum rank change to trigger event
    MIN_RANK_CHANGE = 1  # Any rank change is significant
    
    @classmethod
    def get_supported_thresholds(cls):
        """Get list of supported HVA thresholds from admin config."""
        try:
            from apiApp.models import BigQueryPipelineConfig
            config = BigQueryPipelineConfig.objects.filter(config_id='default').first()
            if config and hasattr(config, 'hva_supported_thresholds') and config.hva_supported_thresholds:
                # Parse comma-separated string into list of floats
                threshold_strings = config.hva_supported_thresholds.split(',')
                thresholds = []
                for t in threshold_strings:
                    try:
                        thresholds.append(float(t.strip()))
                    except (ValueError, AttributeError):
                        pass
                
                if thresholds:
                    return sorted(thresholds)  # Return sorted list
            
            # Fall back to default if config doesn't exist or parsing fails
            return cls.DEFAULT_SUPPORTED_THRESHOLDS
        except Exception:
            return cls.DEFAULT_SUPPORTED_THRESHOLDS
    
    @classmethod
    def get_hva_threshold(cls):
        """Get current HVA threshold from config (default: 100K XLM)."""
        try:
            from apiApp.models import BigQueryPipelineConfig
            config = BigQueryPipelineConfig.objects.filter(config_id='default').first()
            if config:
                return config.hva_threshold_xlm
            return 100000.0  # Default if no config exists
        except Exception:
            return 100000.0  # Default fallback
    
    @classmethod
    def get_current_rankings(cls, network_name='public', xlm_threshold=None, limit=1000):
        """
        Get current HVA rankings ordered by balance for a specific threshold.
        
        Args:
            network_name: 'public' or 'testnet'
            xlm_threshold: Minimum XLM balance threshold (uses admin config if None)
            limit: Maximum number of accounts to return
            
        Returns:
            List of (rank, account) tuples, ordered by xlm_balance DESC
        """
        from apiApp.model_loader import StellarCreatorAccountLineage
        
        # Use admin-configured threshold if not specified
        if xlm_threshold is None:
            xlm_threshold = cls.get_hva_threshold()
        
        try:
            # Query all accounts above the threshold
            all_accounts = StellarCreatorAccountLineage.objects.filter(
                network_name=network_name
            ).all()
            
            # Filter accounts meeting the threshold (in-memory filter for Cassandra)
            qualifying_accounts = [
                acc for acc in all_accounts 
                if acc.xlm_balance and acc.xlm_balance >= xlm_threshold
            ]
            
            # Sort by balance (Cassandra doesn't support ORDER BY on non-clustering columns)
            sorted_accounts = sorted(
                qualifying_accounts, 
                key=lambda x: x.xlm_balance if x.xlm_balance else 0, 
                reverse=True
            )[:limit]
            
            # Return with ranks (1-indexed)
            return [(rank + 1, account) for rank, account in enumerate(sorted_accounts)]
            
        except Exception as e:
            logger.error(f"Error fetching HVA rankings for threshold {xlm_threshold}: {e}")
            return []
    
    @classmethod
    def get_account_rank(cls, stellar_account, network_name='public', xlm_threshold=None):
        """
        Get current rank for a specific account at a given threshold.
        
        Args:
            stellar_account: Stellar account address
            network_name: 'public' or 'testnet'
            xlm_threshold: Minimum XLM balance threshold (uses admin config if None)
            
        Returns:
            int: Current rank (1-indexed), or None if not in top 1000
        """
        rankings = cls.get_current_rankings(network_name=network_name, xlm_threshold=xlm_threshold, limit=1000)
        
        for rank, account in rankings:
            if account.stellar_account == stellar_account:
                return rank
        
        return None  # Not in top 1000
    
    @classmethod
    def get_account_previous_rank(cls, stellar_account, network_name='public', xlm_threshold=None):
        """
        Get the most recent rank from change history for a specific threshold.
        
        Args:
            stellar_account: Stellar account address
            network_name: 'public' or 'testnet'
            xlm_threshold: Minimum XLM balance threshold (uses admin config if None)
            
        Returns:
            int: Previous rank, or None if no history
        """
        from apiApp.model_loader import HVAStandingChange
        
        # Use admin-configured threshold if not specified
        if xlm_threshold is None:
            xlm_threshold = cls.get_hva_threshold()
        
        try:
            # Get most recent change event for this threshold
            all_changes = HVAStandingChange.objects.filter(
                stellar_account=stellar_account
            ).all()
            
            # Filter by threshold (in-memory for Cassandra compatibility)
            threshold_changes = [
                c for c in all_changes 
                if hasattr(c, 'xlm_threshold') and abs(c.xlm_threshold - xlm_threshold) < 1.0
            ]
            
            if threshold_changes:
                # Sort by change_time descending
                sorted_changes = sorted(
                    threshold_changes,
                    key=lambda x: x.change_time,
                    reverse=True
                )
                return sorted_changes[0].new_rank
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching previous rank for {stellar_account} at threshold {xlm_threshold}: {e}")
            return None
    
    @classmethod
    def detect_and_record_change(cls, account_obj, old_balance=None, new_balance=None, xlm_threshold=None):
        """
        Detect if account's standing changed and record an event for a specific threshold.
        
        Args:
            account_obj: StellarCreatorAccountLineage instance
            old_balance: Previous balance (if known)
            new_balance: New balance (if known)
            xlm_threshold: Minimum XLM balance threshold (uses admin config if None)
            
        Returns:
            HVAStandingChange instance if event was recorded, None otherwise
        """
        from apiApp.model_loader import HVAStandingChange
        
        # Use admin-configured threshold if not specified
        if xlm_threshold is None:
            xlm_threshold = cls.get_hva_threshold()
        
        try:
            stellar_account = account_obj.stellar_account
            network_name = account_obj.network_name
            
            # Use provided balances or fall back to account object
            if new_balance is None:
                new_balance = account_obj.xlm_balance or 0.0
            
            # Get current and previous ranks for this specific threshold
            current_rank = cls.get_account_rank(stellar_account, network_name, xlm_threshold)
            previous_rank = cls.get_account_previous_rank(stellar_account, network_name, xlm_threshold)
            
            # Determine event type
            event_type = None
            
            # Case 1: Account entered top 1000 for this threshold
            if current_rank and not previous_rank:
                if new_balance >= xlm_threshold:
                    event_type = 'ENTERED'
            
            # Case 2: Account exited top 1000
            elif not current_rank and previous_rank:
                event_type = 'EXITED'
            
            # Case 3: Rank changed within top 1000
            elif current_rank and previous_rank and current_rank != previous_rank:
                rank_diff = previous_rank - current_rank
                if abs(rank_diff) >= cls.MIN_RANK_CHANGE:
                    event_type = 'RANK_UP' if rank_diff > 0 else 'RANK_DOWN'
            
            # Case 4: Significant balance change without rank change
            elif current_rank and previous_rank and old_balance and new_balance:
                if old_balance > 0:
                    balance_change_pct = abs((new_balance - old_balance) / old_balance) * 100
                    if balance_change_pct >= cls.SIGNIFICANT_BALANCE_CHANGE_PCT:
                        event_type = 'BALANCE_INCREASE' if new_balance > old_balance else 'BALANCE_DECREASE'
            
            # If no event detected, return None
            if not event_type:
                return None
            
            # Record the event
            # Use timezone-aware datetime for SQLite, uuid1() for Cassandra
            from apiApp.model_loader import USE_CASSANDRA
            change_time_val = uuid1() if USE_CASSANDRA else timezone.now()
            
            change_event = HVAStandingChange.create(
                stellar_account=stellar_account,
                change_time=change_time_val,
                event_type=event_type,
                old_rank=previous_rank,
                new_rank=current_rank,
                old_balance=old_balance or 0.0,
                new_balance=new_balance,
                network_name=network_name,
                home_domain=account_obj.home_domain or '',
                xlm_threshold=xlm_threshold
            )
            
            logger.info(
                f"HVA Change: {stellar_account[:8]}... {event_type} "
                f"(Rank: {previous_rank}→{current_rank}, Balance: {old_balance}→{new_balance})"
            )
            
            return change_event
            
        except Exception as e:
            logger.error(f"Error detecting/recording HVA change for {account_obj.stellar_account}: {e}")
            return None
    
    @classmethod
    def get_recent_changes(cls, stellar_account=None, network_name='public', limit=10):
        """
        Get recent HVA standing changes.
        
        Args:
            stellar_account: Optional - filter by specific account
            network_name: 'public' or 'testnet'
            limit: Maximum number of changes to return
            
        Returns:
            List of HVAStandingChange instances
        """
        from apiApp.model_loader import HVAStandingChange
        
        try:
            if stellar_account:
                # Get changes for specific account
                changes = HVAStandingChange.objects.filter(
                    stellar_account=stellar_account
                ).limit(limit)
            else:
                # Get all recent changes (requires scanning - use sparingly)
                changes = HVAStandingChange.objects.all().limit(limit)
            
            return list(changes)
            
        except Exception as e:
            logger.error(f"Error fetching recent HVA changes: {e}")
            return []
    
    @classmethod
    def get_account_change_summary(cls, stellar_account, days=7):
        """
        Get a summary of recent rank changes for an account.
        
        Args:
            stellar_account: Stellar account address
            days: Number of days to look back
            
        Returns:
            Dict with change summary (total changes, best rank, worst rank, etc.)
        """
        changes = cls.get_recent_changes(stellar_account=stellar_account, limit=100)
        
        if not changes:
            return {
                'total_changes': 0,
                'best_rank': None,
                'worst_rank': None,
                'current_rank': cls.get_account_rank(stellar_account),
                'trend': 'stable'
            }
        
        # Filter by date range
        cutoff_date = timezone.now() - timedelta(days=days)
        recent_changes = [
            c for c in changes 
            if c.created_at and c.created_at >= cutoff_date
        ]
        
        # Calculate metrics
        ranks = [c.new_rank for c in recent_changes if c.new_rank]
        best_rank = min(ranks) if ranks else None
        worst_rank = max(ranks) if ranks else None
        
        # Determine trend
        trend = 'stable'
        if len(recent_changes) >= 2:
            first_rank = recent_changes[-1].new_rank
            last_rank = recent_changes[0].new_rank
            if last_rank and first_rank:
                if last_rank < first_rank:
                    trend = 'improving'
                elif last_rank > first_rank:
                    trend = 'declining'
        
        return {
            'total_changes': len(recent_changes),
            'best_rank': best_rank,
            'worst_rank': worst_rank,
            'current_rank': cls.get_account_rank(stellar_account),
            'trend': trend
        }
