"""
BigQuery Usage Tracker

Monitors and logs BigQuery usage to ensure we stay within quota limits
and track costs.
"""

import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """Metrics for a single BigQuery query."""
    query_type: str  # e.g., 'get_account_data', 'get_creator', 'get_children'
    account_address: str
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None
    
    # BigQuery metrics (if available from job stats)
    bytes_processed: Optional[int] = None
    bytes_billed: Optional[int] = None
    cache_hit: bool = False


class BigQueryUsageTracker:
    """
    Tracks BigQuery usage to monitor quota consumption and costs.
    
    Usage Limits:
    - Free tier: 1 TB per month
    - Cost after free tier: $5 per TB
    - Daily quota: Can be set in Google Cloud Console
    
    Expected Usage (Post-Refactoring):
    - Per search: ~110-420 MB
    - 100 searches/day: ~42 GB/day = 1.26 TB/month (within free tier)
    - 5000 searches/day: ~2.1 GB/day = 63 TB/month (~$310/month)
    """
    
    def __init__(self):
        """Initialize usage tracker."""
        self.queries_today = []
        self.quota_exceeded_count = 0
    
    def log_query(self, metrics: QueryMetrics):
        """
        Log a BigQuery query execution.
        
        Args:
            metrics: QueryMetrics object with query details
        """
        self.queries_today.append(metrics)
        
        # Log to console/file
        if metrics.success:
            if metrics.bytes_processed:
                mb_processed = metrics.bytes_processed / (1024 * 1024)
                logger.info(
                    f"BigQuery {metrics.query_type}: {metrics.account_address} "
                    f"- {mb_processed:.2f} MB processed"
                )
            else:
                logger.info(
                    f"BigQuery {metrics.query_type}: {metrics.account_address} - SUCCESS"
                )
        else:
            if "quota exceeded" in (metrics.error_message or "").lower():
                self.quota_exceeded_count += 1
                logger.warning(
                    f"BigQuery QUOTA EXCEEDED (#{self.quota_exceeded_count} today): "
                    f"{metrics.query_type} for {metrics.account_address}"
                )
            else:
                logger.error(
                    f"BigQuery {metrics.query_type} FAILED: {metrics.account_address} "
                    f"- {metrics.error_message}"
                )
    
    def get_daily_stats(self) -> dict:
        """
        Get daily usage statistics.
        
        Returns:
            dict: Daily statistics including query count, bytes processed, etc.
        """
        total_queries = len(self.queries_today)
        successful_queries = sum(1 for q in self.queries_today if q.success)
        failed_queries = total_queries - successful_queries
        
        total_bytes = sum(
            q.bytes_processed or 0 
            for q in self.queries_today 
            if q.bytes_processed
        )
        
        total_mb = total_bytes / (1024 * 1024)
        total_gb = total_mb / 1024
        
        return {
            'total_queries': total_queries,
            'successful': successful_queries,
            'failed': failed_queries,
            'quota_exceeded': self.quota_exceeded_count,
            'total_mb_processed': round(total_mb, 2),
            'total_gb_processed': round(total_gb, 2),
            'avg_mb_per_query': round(total_mb / total_queries, 2) if total_queries > 0 else 0
        }
    
    def estimate_monthly_usage(self, searches_per_day: int) -> dict:
        """
        Estimate monthly BigQuery usage and costs.
        
        Args:
            searches_per_day: Expected number of searches per day
        
        Returns:
            dict: Estimated monthly usage and costs
        """
        # Assumptions based on refactored queries
        mb_per_search_avg = 265  # Average of 110-420 MB range
        mb_per_search_worst = 420  # Worst case
        
        days_per_month = 30
        free_tier_tb = 1.0
        cost_per_tb = 5.0
        
        # Average case calculation
        daily_mb_avg = searches_per_day * mb_per_search_avg
        daily_gb_avg = daily_mb_avg / 1024
        monthly_tb_avg = (daily_gb_avg * days_per_month) / 1024
        
        # Worst case calculation
        daily_mb_worst = searches_per_day * mb_per_search_worst
        daily_gb_worst = daily_mb_worst / 1024
        monthly_tb_worst = (daily_gb_worst * days_per_month) / 1024
        
        # Cost calculation (average)
        billable_tb_avg = max(0, monthly_tb_avg - free_tier_tb)
        monthly_cost_avg = billable_tb_avg * cost_per_tb
        
        # Cost calculation (worst case)
        billable_tb_worst = max(0, monthly_tb_worst - free_tier_tb)
        monthly_cost_worst = billable_tb_worst * cost_per_tb
        
        return {
            'searches_per_day': searches_per_day,
            'daily_usage_gb': {
                'average': round(daily_gb_avg, 2),
                'worst_case': round(daily_gb_worst, 2)
            },
            'monthly_usage_tb': {
                'average': round(monthly_tb_avg, 2),
                'worst_case': round(monthly_tb_worst, 2)
            },
            'billable_tb': {
                'average': round(billable_tb_avg, 2),
                'worst_case': round(billable_tb_worst, 2)
            },
            'estimated_monthly_cost': {
                'average': round(monthly_cost_avg, 2),
                'worst_case': round(monthly_cost_worst, 2)
            },
            'within_free_tier': monthly_tb_avg <= free_tier_tb
        }
    
    def print_scaling_scenarios(self):
        """Print usage estimates for various scaling scenarios."""
        scenarios = [100, 500, 1000, 2000, 5000, 10000]
        
        print("\n" + "=" * 80)
        print("BIGQUERY USAGE & COST SCALING SCENARIOS")
        print("=" * 80)
        print("\nAssumptions:")
        print("- Per search: 110-420 MB (avg 265 MB)")
        print("- Free tier: 1 TB/month")
        print("- Cost: $5 per TB after free tier")
        print("- BigQuery queries ONLY lineage data (not assets/balance)")
        print("\n" + "-" * 80)
        
        for searches_per_day in scenarios:
            estimate = self.estimate_monthly_usage(searches_per_day)
            
            print(f"\n📊 {searches_per_day:,} searches/day:")
            print(f"   Daily usage: {estimate['daily_usage_gb']['average']} GB (avg) | "
                  f"{estimate['daily_usage_gb']['worst_case']} GB (worst)")
            print(f"   Monthly usage: {estimate['monthly_usage_tb']['average']} TB (avg) | "
                  f"{estimate['monthly_usage_tb']['worst_case']} TB (worst)")
            
            if estimate['within_free_tier']:
                print(f"   💚 Cost: $0/month (within free tier)")
            else:
                print(f"   💰 Cost: ${estimate['estimated_monthly_cost']['average']}/month (avg) | "
                      f"${estimate['estimated_monthly_cost']['worst_case']}/month (worst)")
        
        print("\n" + "=" * 80)
        print("\n💡 Cost Optimization Strategies:")
        print("   1. ✅ Already minimized: Only query lineage data from BigQuery")
        print("   2. 🔄 Caching: 12-hour cache reduces repeat searches by ~30%")
        print("   3. 📊 Monitoring: Track daily usage to catch anomalies early")
        print("   4. 🎯 Quota limits: Set daily quota in Google Cloud Console")
        print("   5. 💾 Database fallback: Use cached data when quota exceeded")
        print("=" * 80 + "\n")


# Global tracker instance
_usage_tracker = None


def get_tracker() -> BigQueryUsageTracker:
    """Get the global usage tracker instance."""
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = BigQueryUsageTracker()
    return _usage_tracker


def log_bigquery_query(query_type: str, account: str, success: bool, 
                       error: Optional[str] = None, bytes_processed: Optional[int] = None):
    """
    Convenience function to log a BigQuery query.
    
    Args:
        query_type: Type of query (e.g., 'get_account_data')
        account: Account address being queried
        success: Whether query succeeded
        error: Error message if failed
        bytes_processed: Bytes processed by BigQuery (if available)
    """
    tracker = get_tracker()
    metrics = QueryMetrics(
        query_type=query_type,
        account_address=account,
        timestamp=datetime.now(),
        success=success,
        error_message=error,
        bytes_processed=bytes_processed
    )
    tracker.log_query(metrics)
