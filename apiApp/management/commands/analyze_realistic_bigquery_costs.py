"""
Management command to analyze realistic BigQuery costs based on unique account searches.

BigQuery is ONLY queried for accounts never searched before (not in Cassandra).
Repeat searches use cached Cassandra data with API enrichment refresh.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Analyze realistic BigQuery costs based on unique account discovery patterns'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*70)
        self.stdout.write("📊 REALISTIC BigQuery Cost Analysis")
        self.stdout.write("="*70 + "\n")
        
        self.stdout.write("🏗️  Architecture:")
        self.stdout.write("  • First-time account: BigQuery → Cassandra (permanent storage)")
        self.stdout.write("  • Repeat searches: Cassandra only (0 BigQuery cost)")
        self.stdout.write("  • Enrichment refresh: Horizon/Stellar Expert APIs (0 BigQuery cost)\n")
        
        # BigQuery costs per account (one-time)
        mb_per_account_avg = 265  # Average
        mb_per_account_worst = 420  # Worst case with many children
        
        scenarios = [
            {
                'name': 'Early Stage (100 unique accounts/month)',
                'unique_per_month': 100,
                'total_searches': '500-1000',
                'repeat_ratio': '80-90%'
            },
            {
                'name': 'Growing (500 unique accounts/month)',
                'unique_per_month': 500,
                'total_searches': '2,500-5,000',
                'repeat_ratio': '80-90%'
            },
            {
                'name': 'Established (1,000 unique accounts/month)',
                'unique_per_month': 1000,
                'total_searches': '5,000-10,000',
                'repeat_ratio': '80-90%'
            },
            {
                'name': 'High Growth (2,500 unique accounts/month)',
                'unique_per_month': 2500,
                'total_searches': '10,000-25,000',
                'repeat_ratio': '75-90%'
            },
            {
                'name': 'Enterprise (5,000 unique accounts/month)',
                'unique_per_month': 5000,
                'total_searches': '25,000-50,000',
                'repeat_ratio': '80-90%'
            },
        ]
        
        for scenario in scenarios:
            unique = scenario['unique_per_month']
            
            # Calculate monthly BigQuery usage (only for unique accounts)
            monthly_mb_avg = unique * mb_per_account_avg
            monthly_mb_worst = unique * mb_per_account_worst
            
            monthly_gb_avg = monthly_mb_avg / 1024
            monthly_gb_worst = monthly_mb_worst / 1024
            
            monthly_tb_avg = monthly_gb_avg / 1024
            monthly_tb_worst = monthly_gb_worst / 1024
            
            # Calculate costs (1 TB free tier)
            free_tier = 1.0
            cost_per_tb = 5.0
            
            billable_avg = max(0, monthly_tb_avg - free_tier)
            billable_worst = max(0, monthly_tb_worst - free_tier)
            
            monthly_cost_avg = billable_avg * cost_per_tb
            monthly_cost_worst = billable_worst * cost_per_tb
            
            # Annual projections
            annual_cost_avg = monthly_cost_avg * 12
            annual_cost_worst = monthly_cost_worst * 12
            
            self.stdout.write(f"\n{'─'*70}")
            self.stdout.write(f"📈 {scenario['name']}")
            self.stdout.write(f"{'─'*70}")
            self.stdout.write(f"  Total searches: {scenario['total_searches']}/month")
            self.stdout.write(f"  Unique accounts: {unique:,}/month")
            self.stdout.write(f"  Repeat search ratio: {scenario['repeat_ratio']}\n")
            
            self.stdout.write(f"  💾 BigQuery Usage (unique accounts only):")
            self.stdout.write(f"    Average: {monthly_gb_avg:.2f} GB/month ({monthly_tb_avg:.3f} TB)")
            self.stdout.write(f"    Worst case: {monthly_gb_worst:.2f} GB/month ({monthly_tb_worst:.3f} TB)\n")
            
            if monthly_cost_avg == 0:
                self.stdout.write(f"  💰 Monthly Cost: $0 (within 1 TB free tier) 💚")
            else:
                self.stdout.write(f"  💰 Monthly Cost:")
                self.stdout.write(f"    Average: ${monthly_cost_avg:.2f}/month")
                self.stdout.write(f"    Worst case: ${monthly_cost_worst:.2f}/month")
            
            if annual_cost_avg > 0:
                self.stdout.write(f"\n  📅 Annual Cost:")
                self.stdout.write(f"    Average: ${annual_cost_avg:.2f}/year")
                self.stdout.write(f"    Worst case: ${annual_cost_worst:.2f}/year")
        
        # Database growth insights
        self.stdout.write(f"\n\n{'='*70}")
        self.stdout.write("📚 Database Growth Insights")
        self.stdout.write(f"{'='*70}\n")
        
        self.stdout.write("  As your Cassandra database grows:")
        self.stdout.write("  ✅ BigQuery costs DECREASE (more cached accounts)")
        self.stdout.write("  ✅ Response time IMPROVES (Cassandra < BigQuery)")
        self.stdout.write("  ✅ No data deletion needed (lineage stored permanently)")
        self.stdout.write("  ✅ Enrichment refresh via free Horizon/Expert APIs\n")
        
        # Cost comparison
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write("💡 Cost Optimization Tips")
        self.stdout.write(f"{'='*70}\n")
        
        self.stdout.write("  1. Promote popular accounts (e.g., exchanges, anchors)")
        self.stdout.write("     → Pre-load into Cassandra → 0 BigQuery cost for future searches")
        self.stdout.write("\n  2. Set Google Cloud daily quota limits:")
        self.stdout.write("     → Prevents unexpected spikes")
        self.stdout.write("     → Example: 2 GB/day limit (~7,500 unique accounts/day max)")
        self.stdout.write("\n  3. Monitor Cassandra hit rate:")
        self.stdout.write("     → Higher hit rate = lower BigQuery costs")
        self.stdout.write("     → Target: 80-90% cache hits for mature deployment")
        self.stdout.write("\n  4. Database never shrinks:")
        self.stdout.write("     → Once an account is stored, it's free forever")
        self.stdout.write("     → Only new unique accounts cost money\n")
        
        # Break-even analysis
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write("📊 Free Tier Coverage")
        self.stdout.write(f"{'='*70}\n")
        
        max_unique_free_avg = int((1024 * 1024) / mb_per_account_avg)  # 1 TB in MB / MB per account
        max_unique_free_worst = int((1024 * 1024) / mb_per_account_worst)
        
        self.stdout.write(f"  1 TB free tier covers:")
        self.stdout.write(f"    • {max_unique_free_avg:,} unique accounts (average case)")
        self.stdout.write(f"    • {max_unique_free_worst:,} unique accounts (worst case with many children)\n")
        
        self.stdout.write(f"  At 80% cache hit rate (5,000 total searches/day):")
        self.stdout.write(f"    • 1,000 unique accounts/day")
        self.stdout.write(f"    • ~30 unique accounts/month covers free tier")
        self.stdout.write(f"    • Remaining 970 unique/month costs ~$125/month average\n")
        
        self.stdout.write("\n" + "="*70 + "\n")
