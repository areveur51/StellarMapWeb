# BigQuery Cost Controls Documentation

## Overview

This document describes the cost control mechanisms implemented to prevent excessive BigQuery usage and costs.

## Problem Statement

**Issue:** BigQuery queries were scanning the entire `enriched_history_operations` table (3-4 TiB) without partition filters, causing 10.88 TiB usage instead of expected ~260 MB per account.

**Root Cause:** Queries lacked:
1. Partition filters (closed_at date range)
2. Query size validation before execution
3. Cost estimation and limits

## Solution Architecture

### 1. BigQueryCostGuard Class

**Location:** `apiApp/helpers/sm_bigquery.py`

**Purpose:** Validates query size before execution using BigQuery dry-run feature.

**Key Features:**
- Maximum query size: **100 MB** (strictly enforced)
- Dry-run validation before actual execution
- Cost estimation ($5 per TB)
- Automatic rejection of queries exceeding limit

**Usage:**
```python
cost_guard = BigQueryCostGuard(client)
cost_info = cost_guard.validate_query_cost(query, job_config)
# Raises ValueError if query > 100 MB
```

### 2. Mandatory Partition Filters

**All queries to `enriched_history_operations` MUST include:**
```sql
WHERE closed_at >= TIMESTAMP(@start_date)
  AND closed_at <= TIMESTAMP(@end_date)
```

**Why:** The enriched_history_operations table is partitioned by `closed_at`. Without partition filters, BigQuery scans the entire table (billions of rows, 3-4 TiB).

**Date Range Calculation:**
- Start date: Account creation date - 7 days (safety buffer)
- End date: Current timestamp
- Fallback: '2015-01-01' (Stellar genesis) to today

### 3. Protected Query Methods

**All BigQuery query methods now use cost guard:**

| Method | Table | Partition Filter Required | Cost Guard |
|--------|-------|--------------------------|------------|
| `get_account_data()` | accounts_current | No (small table) | ✅ Yes |
| `get_account_creator()` | enriched_history_operations | ✅ **YES** | ✅ Yes |
| `get_child_accounts()` | enriched_history_operations | ✅ **YES** | ✅ Yes |
| `get_account_assets()` | trust_lines_current | No (small table) | ✅ Yes |

### 4. Pipeline Integration

**Location:** `apiApp/management/commands/bigquery_pipeline.py`

**Flow:**
1. Fetch account creation date from `accounts_current`
2. Calculate safe date window (creation date - 7 days to today)
3. Pass date window to ALL BigQuery queries
4. Cost guard validates each query before execution
5. Log cost estimates for monitoring

**Example:**
```python
# Calculate date window
creation_date = account_data.get('account_creation_date')
start_date = (creation_date - 7 days).strftime('%Y-%m-%d')
end_date = datetime.utcnow().strftime('%Y-%m-%d')

# Pass to queries
creator_info = bq_helper.get_account_creator(
    account, 
    start_date=start_date, 
    end_date=end_date
)
```

## Test Coverage

**Location:** `apiApp/tests/test_bigquery_usage_limits.py`

**Test Suites:**
1. **BigQueryCostGuardTestCase** - Tests cost guard enforcement
2. **PartitionFilterEnforcementTestCase** - Tests partition filter presence
3. **FullTableScanPreventionTestCase** - Tests full table scan prevention

**Key Tests:**
- ✅ Queries over 100MB are blocked
- ✅ Queries under 100MB are allowed
- ✅ Partition filters are present in all queries
- ✅ Cost estimation is accurate
- ✅ Cost guard runs before query execution

## Expected Query Sizes

| Query Type | Expected Size | Notes |
|------------|--------------|-------|
| Account data (accounts_current) | 1-10 MB | Small lookup table |
| Account creator (with partition filter) | 10-50 MB | Single operation lookup |
| Child accounts (with partition filter) | 50-100 MB | May return many children |
| Total per account | **~100-200 MB** | All queries combined |

## Cost Estimates

**Per Account (with partition filters):**
- Data scanned: ~100-200 MB
- Cost: ~$0.0001-0.0002 (less than 1 cent)

**Per 1,000 Accounts:**
- Data scanned: ~100-200 GB
- Cost: ~$0.50-1.00

**Per Month (5,000 accounts):**
- Data scanned: ~500 GB - 1 TB
- Cost: ~$0-5 (within free tier)

**vs. Without Partition Filters:**
- Data scanned: 3-4 TiB **per account**
- Cost: ~$15-20 **per account**
- Per 1,000 accounts: ~$15,000-20,000 ❌

## How to Add New BigQuery Queries

**MANDATORY STEPS:**

1. **Add Cost Guard Validation:**
```python
# COST GUARD: Validate query size before execution
cost_info = self.cost_guard.validate_query_cost(query, job_config)
logger.info(f"✅ Query approved: {cost_info['size_mb']} MB")

# Re-enable actual execution
job_config.dry_run = False
query_job = self.client.query(query, job_config=job_config)
```

2. **Add Partition Filters (if querying enriched_history_operations):**
```sql
WHERE closed_at >= TIMESTAMP(@start_date)
  AND closed_at <= TIMESTAMP(@end_date)
```

3. **Add Method Parameters:**
```python
def new_query_method(
    self,
    account: str,
    start_date: str = '2015-01-01',
    end_date: Optional[str] = None
) -> Optional[Dict]:
    if not end_date:
        from datetime import datetime
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
    # ... rest of implementation
```

4. **Add Tests:**
- Test cost guard validation
- Test partition filter presence
- Test query size is under 100MB

## Monitoring

**Key Metrics to Monitor:**
- Query size (MB) - logged before each query
- Estimated cost ($) - logged before each query
- Total daily BigQuery usage (GB)
- Queries blocked by cost guard

**Log Format:**
```
Validating query cost for creator of GTEST... (date range: 2024-01-01 to 2024-12-31)
✅ Query approved: 45.2 MB, $0.0002
```

## Emergency Procedures

**If BigQuery quota is exceeded:**

1. **Stop all pipelines immediately:**
   - Disable BigQuery Pipeline workflow
   - Check for any running cron jobs

2. **Investigate:**
   - Check logs for query sizes
   - Identify queries without partition filters
   - Review cost guard validations

3. **Fix and Resume:**
   - Add partition filters to problematic queries
   - Reduce quota to 35 GB/day for safety
   - Resume with monitoring

## References

- **Cost Guard Implementation:** `apiApp/helpers/sm_bigquery.py` (lines 27-98)
- **Partition Filters:** `apiApp/helpers/sm_bigquery.py` (lines 154-233, 241-316)
- **Pipeline Integration:** `apiApp/management/commands/bigquery_pipeline.py` (lines 178-214)
- **Tests:** `apiApp/tests/test_bigquery_usage_limits.py` (lines 290-482)

## Version History

- **v2.0** (2025-10-09): Added BigQueryCostGuard, mandatory partition filters, comprehensive tests
- **v1.0** (Previous): Basic BigQuery integration (no cost controls) ❌
