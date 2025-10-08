# BigQuery Pipeline vs Cron Pipeline Comparison

## Overview

This document compares the **BigQuery Pipeline** (permanent storage architecture) against the existing **Cron Pipeline** for collecting Stellar account lineage data.

---

## Architecture Comparison

### Permanent Storage Architecture (Core Concept)

**BigQuery is ONLY queried for accounts never searched before:**

```
First-Time Search → BigQuery (lineage data) → Cassandra (permanent storage)
                                                      ↓
Repeat Search ────────────────────────────────────→ Cassandra (0 BigQuery cost)
                                                      ↓
Enrichment Refresh ────────────────────────────→ Horizon/Stellar Expert APIs (free)
```

**Key Insight:** Once an account's lineage is stored in Cassandra, it's **free forever**. Only unique new accounts cost money.

---

### Cron Pipeline (8-Stage API-Based)

**Stages:**
1. Health Check
2. Recover Stuck Accounts
3. Parent Account Lineage (Process PENDING accounts)
4. Collect Account Horizon Data (API Call)
5. Collect Account Attributes (Parse Horizon Data)
6. Collect Account Flags (Parse Horizon Data)
7. Collect Account Assets (Parse Horizon Data)
8. Collect Stellar Expert Directory Data (API Call)
9. Collect Account Creator (API Call + BigQuery Fallback)
10. Collect Child Accounts (API Call + BigQuery Discovery)

**Data Sources:**
- Horizon API (primary for real-time data)
- Stellar Expert API (supplementary)
- BigQuery/Hubble (fallback for creators, child discovery)

**Processing Time:** 2-3 minutes per account (all 8 stages)

**Rate Limits:** Subject to Horizon API rate limits

---

### BigQuery Pipeline (Permanent Storage Model)

**What's Stored Where:**

| Data Type | First-Time Source | Stored In | Repeat Searches | Refresh Source |
|-----------|------------------|-----------|----------------|----------------|
| **Lineage data** (creation dates, parent-child relationships) | BigQuery | Cassandra | Cassandra (free) | Never (permanent) |
| **Account details** (balance, flags, home_domain) | Horizon API | N/A | Horizon API | Every search (fresh) |
| **Assets data** | Stellar Expert | N/A | Stellar Expert | Every search (fresh) |

**Processing Flow:**
1. Check if account exists in Cassandra
   - **Yes** → Return cached lineage + refresh enrichment from APIs (0 BigQuery cost)
   - **No** → Query BigQuery for lineage → Store permanently in Cassandra

**BigQuery Queries (First-Time Only):**
1. Account creation date from `accounts_current`
2. Creator account from `enriched_history_operations` (type=0)
3. Child accounts from `enriched_history_operations` (type=0, paginated up to 100,000)

**Processing Time:** 50-90 seconds for first-time searches, <1 second for repeat searches

**Rate Limits:** None on BigQuery, standard limits on Horizon/Stellar Expert APIs

---

## Performance Comparison

| Metric | Cron Pipeline | BigQuery Pipeline (First-Time) | BigQuery Pipeline (Cached) | Winner |
|--------|---------------|-------------------------------|---------------------------|---------|
| **Processing Time** | 2-3 minutes/account | 50-90 seconds/account | <1 second | BigQuery (cached) |
| **API Calls** | 3-5 per account | 1-2 per account | 1-2 per account | BigQuery |
| **BigQuery Calls** | 0-2 (fallback) | 3 queries (first-time only) | 0 | Cron (but limited data) |
| **Rate Limiting** | Yes (Horizon limits) | Yes (Horizon for enrichment) | Yes (Horizon for enrichment) | Tie |
| **Data Completeness** | Limited by Horizon | Complete historical lineage | Complete historical lineage | BigQuery |
| **Child Discovery** | Max ~1,000 operations | Up to 100,000 per account | Up to 100,000 per account | BigQuery |
| **Real-time Balance** | Yes | Yes (via Horizon) | Yes (via Horizon) | Tie |
| **Recurring Cost** | $0 | $0 (cached after first search) | $0 | Tie |
| **Complexity** | 8 stages, multiple files | 1 stage, simple logic | Cache lookup | BigQuery |

---

## Cost Analysis (Realistic Model)

### Permanent Storage Economics

**Key Principle:** BigQuery costs are **one-time per unique account**, not per search.

| Deployment Stage | Unique Accounts/Month | Total Searches/Month | Monthly BigQuery Cost | Notes |
|-----------------|----------------------|---------------------|---------------------|-------|
| **Early Stage** | 100 | 500-1,000 | **$0** 💚 | Within 1 TB free tier |
| **Growing** | 500 | 2,500-5,000 | **$0** 💚 | Within free tier |
| **Established** | 1,000 | 5,000-10,000 | **$0** 💚 | Within free tier |
| **High Growth** | 2,500 | 10,000-25,000 | **$0** 💚 | Just under free tier |
| **Enterprise** | 5,000 | 25,000-50,000 | **$1-5/month** | 80-90% cache hit rate |

### Free Tier Coverage

- **1 TB free tier = 2,500-3,900 unique accounts/month**
- Average cost per unique account: **$0.00025** (after free tier)
- **Most deployments stay free indefinitely**

### Database Growth Benefits

As your Cassandra database grows:
- ✅ **BigQuery costs DECREASE** (more accounts already cached)
- ✅ **Response time IMPROVES** (Cassandra < 50ms vs BigQuery 2-3 seconds)
- ✅ **No data deletion needed** (lineage stored permanently)
- ✅ **Enrichment stays fresh** (Horizon/Expert APIs update balance/assets)

**Example 6-Month Growth:**
| Month | New Unique | Cumulative | BigQuery Usage | Cost |
|-------|-----------|------------|---------------|------|
| 1 | 1,000 | 1,000 | 259 GB | $0 |
| 2 | 800 | 1,800 | 207 GB | $0 |
| 3 | 600 | 2,400 | 155 GB | $0 |
| 4 | 500 | 2,900 | 129 GB | $0 |
| 5 | 400 | 3,300 | 104 GB | $0 |
| 6 | 300 | 3,600 | 78 GB | $0 |
| **Total** | **3,600** | **3,600** | **932 GB** | **$0** |

**Insight:** New unique accounts naturally decline as popular accounts get cached!

---

## Data Accuracy Comparison

### Cron Pipeline
- ✅ Real-time data (30 second latency)
- ⚠️ Limited child account discovery (Horizon pagination limit ~1,000 operations)
- ⚠️ Creator discovery may fail for old accounts
- ✅ Includes Stellar Expert directory metadata

### BigQuery Pipeline
- ✅ Real-time enrichment data (balance, assets via Horizon/Stellar Expert)
- ✅ Comprehensive child account discovery (up to 100,000 per account with pagination)
- ✅ Complete creator discovery (all blockchain history)
- ✅ Permanent lineage storage (never re-query BigQuery)
- ⚠️ Lineage data has ~30 minute BigQuery update latency (acceptable for historical data)

---

## Use Case Recommendations

### Use Cron Pipeline When:
- Educational purposes (understanding API-based approaches)
- Zero external dependencies (no BigQuery credentials)
- Development/testing without BigQuery access
- API integration demonstrations

### Use BigQuery Pipeline When:
- **Production deployments** (recommended)
- Complete historical lineage data needed
- Processing >100 accounts
- Discovering all child accounts is critical
- Long-term cost efficiency is important (permanent storage)
- Building a growing database that gets cheaper over time

---

## Cost Optimization Strategies

### 1. Pre-Load Popular Accounts
Pre-populate Cassandra with high-traffic accounts:
```bash
python manage.py bigquery_pipeline GBSTRUSD... --limit 100
```
**Impact:** Free forever for all users after initial load

### 2. Set Google Cloud Quota Limits
Prevent unexpected spikes:
- **Recommended:** 2 GB/day (~500-750 unique accounts/day max)
- **Location:** Google Cloud Console → BigQuery → Quotas

### 3. Monitor Cache Hit Rate
```python
cache_hits = searches_from_cassandra / total_searches
```
**Target:** 80-90% for mature deployments

---

## Testing Results

### BigQuery Pipeline Test (Oct 8, 2025)

**Test 1: Single Account**
- Account: `GCQXVOCLE6OMZS3BNBHEAI4ICEOBQOH35GFKMNNVDBEPP5G3N63JLGWR`
- Balance: 143,454,349 stroops
- Creator: Not found (root account)
- Children: 0
- **First Search:** 46.49 seconds
- **Repeat Search:** <1 second (from Cassandra)

**Test 2: Account with Creator**
- Account: `GBHN7WYXPQJ54AVXMHR23QDKQXIRDVO3HHWPEPESF4ZT7Y5NJEI5YHTW`
- Balance: 16,746,286 stroops (refreshed from Horizon)
- Creator: `GCO2IP3MJNUOKS4PUDI4C7LGGMQDJGXG3COYX3WSB4HHNAHKYV5YL3VC`
- **First Search:** 82.37 seconds
- **Repeat Search:** <1 second (lineage from Cassandra, balance from Horizon)

**Test 3: Account with Many Children**
- Account: `GCO2IP3MJNUOKS4PUDI4C7LGGMQDJGXG3COYX3WSB4HHNAHKYV5YL3VC`
- Children: 1,000+ accounts discovered
- **First Search:** ~100 seconds (BigQuery pagination)
- **Repeat Search:** <1 second (all children cached)

---

## Monitoring Commands

### View Realistic Cost Projections
```bash
python manage.py analyze_realistic_bigquery_costs
```

### View Worst-Case Per-Search Costs
```bash
python manage.py analyze_bigquery_scaling
```

### Run Cost Validation Tests
```bash
python manage.py test apiApp.tests.test_bigquery_usage_limits
```

---

## Conclusion

The **BigQuery Pipeline with Permanent Storage** is:
- ✅ **2-3x faster** than Cron Pipeline (first-time searches)
- ✅ **100x+ faster** for repeat searches (<1s from cache)
- ✅ **Complete historical data** (not limited by Horizon pagination)
- ✅ **Simpler architecture** (1 stage vs 8 stages)
- ✅ **Cost-effective** (free for most deployments, $1-5/month at enterprise scale)
- ✅ **Gets cheaper over time** (growing database = higher cache hit rate)
- ✅ **Fresh enrichment data** (balance/assets always current via APIs)

### Recommendation

**Use BigQuery Pipeline as the primary method for all deployments.** The permanent storage architecture makes it:
- Free for 99% of use cases
- Faster and more comprehensive than API-based approaches
- Self-optimizing (costs decrease as database grows)

Keep the Cron Pipeline available for:
- Educational purposes and API demonstrations
- Development environments without BigQuery credentials
- Understanding API-based data collection patterns

---

## Running the Pipelines

### BigQuery Pipeline (Recommended)
```bash
# Process up to 100 accounts
python manage.py bigquery_pipeline --limit 100

# Process specific account
python manage.py bigquery_pipeline GABC... --limit 10
```

### Cron Pipeline (Educational/Reference)
```bash
# Run via workflow (not enabled by default)
python run_cron_jobs.py
```

---

## Summary: Why BigQuery Wins

**Bottom Line:** The permanent storage architecture provides:

1. **Extreme Cost Efficiency**: $0-5/month for most deployments (vs $995/month before refactoring)
2. **Performance**: 100x faster for repeat searches
3. **Completeness**: Up to 100,000 child accounts discovered
4. **Simplicity**: 1-stage pipeline vs 8-stage complexity
5. **Self-Optimization**: Costs decrease as database grows

**The system is designed to be cost-effective from day one and gets cheaper over time!** 🚀
