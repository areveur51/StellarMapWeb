# Dashboard Troubleshooting Guide

This guide helps you fix unhealthy records and resolve issues reported on the System Dashboard.

---

## 📊 Dashboard Overview

The System Dashboard monitors your StellarMapWeb application health and displays several key metrics:

- **Database Health**: Total accounts, fresh/stale/stuck records
- **Processing Status**: Pending, in progress, completed accounts
- **Lineage Data Integrity**: Total lineage records, orphan accounts
- **System Health**: Cron status, stage executions, failed stages

---

## 🔴 Critical Issues (Requires Immediate Attention)

### 1. Stuck Records

**What it means:**  
Accounts that have been processing for more than 5 minutes (PENDING/PROCESSING status) or 30+ minutes for other pipeline stages. These records are likely frozen and won't complete on their own.

**How to identify:**
- Dashboard shows **Stuck Records** count in red
- Alert message: "X accounts are stuck in processing"

**How to fix:**

#### Option A: Via Django Admin (Recommended)
1. Click **"View in Admin"** button on Stuck Records card
2. Filter by `status` → Select `PENDING` or `PROCESSING`
3. Select all stuck records (checkbox at top)
4. From "Actions" dropdown → Select **"Force retry stuck records"**
5. Click **"Go"** button
6. Confirm the action

#### Option B: Via Database Query (Advanced)

> ⚠️ **WARNING**: Direct database modifications should only be performed by experienced users. Always backup your data first or use the Django Admin interface (Option A) instead.

```sql
-- SAFE: Check stuck records first (read-only)
SELECT stellar_account, status, updated_at 
FROM stellar_account_search_cache 
WHERE status IN ('PENDING', 'PROCESSING') 
AND updated_at < NOW() - INTERVAL '5 minutes';

-- CAUTION: Reset stuck records to allow retry
-- This UPDATE query modifies data - ensure you've verified the SELECT results first
UPDATE stellar_account_search_cache 
SET status = 'PENDING', updated_at = NOW() 
WHERE status IN ('PENDING', 'PROCESSING') 
AND updated_at < NOW() - INTERVAL '5 minutes';
```

#### Option C: Manual Investigation
1. Check if cron job is running: Look at **Cron Status** on dashboard
2. Check workflow logs for errors:
   ```bash
   # View BigQuery Pipeline logs
   tail -100 /tmp/logs/BigQuery_Pipeline_*.log
   ```
3. Restart the BigQuery Pipeline workflow if needed
4. Monitor the dashboard for 5-10 minutes to see if stuck records clear

**Prevention:**
- Ensure BigQuery Pipeline workflow is always running
- Check cost limits aren't blocking queries
- Monitor API rate limits (Horizon/Stellar Expert)

---

### 2. Failed Stages

**What it means:**  
Pipeline stage executions that encountered errors during processing. This indicates problems with data collection, API calls, or BigQuery queries.

**How to identify:**
- Dashboard shows **Failed Stages** count in red
- Alert message: "X stage executions have failed"

**How to fix:**

#### Step 1: View Failed Stages
1. Click **"View in Admin"** on Failed Stages card
2. Filter by `status` → Select `FAILED` or `ERROR`
3. Review the error messages in each record

#### Step 2: Common Failure Scenarios

**Scenario A: BigQuery Cost/Size Limit Exceeded**
- **Error**: "Cost/size limit exceeded"
- **Fix**: 
  1. Go to Admin → BigQuery Pipeline Config
  2. Increase cost limit (default: $0.71) or size limit (default: 145GB)
  3. OR switch pipeline mode to API-only temporarily
  4. Save changes and retry failed accounts

**Scenario B: API Rate Limit Hit**
- **Error**: "Rate limit exceeded" or "429 Too Many Requests"
- **Fix**:
  1. Wait 5-10 minutes for rate limits to reset
  2. Retry the failed accounts manually via search page
  3. Consider reducing processing frequency

**Scenario C: Network/Timeout Issues**
- **Error**: "Connection timeout" or "Network error"
- **Fix**:
  1. Check internet connectivity
  2. Verify Horizon API is accessible: https://horizon.stellar.org
  3. Retry failed accounts after network is stable

**Scenario D: Invalid Account Address**
- **Error**: "Account not found" or "Invalid address"
- **Fix**:
  1. Verify the account address is valid
  2. Check if account exists on the network (public vs testnet)
  3. Delete invalid records from cache

#### Step 3: Retry Failed Stages
1. Select failed stage executions in admin
2. Actions → **"Retry failed stages"**
3. Click **"Go"**
4. Monitor dashboard to verify resolution

**Prevention:**
- Configure appropriate cost/size limits
- Enable API fallback mode (BigQuery + API hybrid)
- Set up monitoring alerts for repeated failures

---

## ⚠️ Warnings (Should Be Addressed)

### 3. Stale Records

**What it means:**  
Cached account data that is more than 12 hours old. The data may be outdated and should be refreshed to get the latest blockchain information.

**How to identify:**
- Dashboard shows **Stale Records** count in yellow
- Label: "needs refresh"

**How to fix:**

#### Option A: Bulk Refresh via Admin
1. Click **"View in Admin"** on Stale Records card
2. Filter by checking **"Stale only"** checkbox
3. Select all stale records (checkbox at top)
4. Actions → **"Refresh selected accounts"**
5. Click **"Go"**
6. The pipeline will re-process these accounts with fresh data

#### Option B: Individual Refresh via Search
1. Go to Search page
2. Enter the stale account address
3. Click the **"Refresh"** button (if displayed)
4. Wait for pipeline to complete

#### Option C: Automatic Refresh
Stale records automatically refresh when:
- User searches for the same account again
- Cron job runs periodic cleanup (if configured)
- 24+ hours have passed (triggers auto-refresh on next search)

**Best Practice:**
- Fresh data ensures accurate lineage visualization
- Refresh important accounts regularly
- Stale data is still usable, just potentially outdated

---

### 4. Orphan Accounts

**What it means:**  
Accounts that exist in the search cache but have no corresponding lineage data. This indicates incomplete pipeline processing or data integrity issues.

**How to identify:**
- Dashboard shows **Orphan Accounts** count in yellow
- Alert: "X accounts in cache have no lineage data"

**How to fix:**

#### Option A: Re-process Orphan Accounts
1. Click **"View in Admin"** on Orphan Accounts card
2. You'll see accounts with cached data but no lineage
3. Select orphan accounts
4. Actions → **"Re-process lineage data"**
5. Click **"Go"**
6. Pipeline will fetch missing lineage information

#### Option B: Delete and Re-search
1. Identify orphan accounts in admin
2. Select orphan records
3. Actions → **"Delete selected"** (this clears cache)
4. Click **"Go"**
5. Search for these accounts again from scratch
6. Complete pipeline will run and populate lineage

#### Option C: Manual Investigation (Advanced)

> ⚠️ **NOTE**: This is a read-only diagnostic query - safe to run for analysis.

```sql
-- SAFE: Find orphan accounts (read-only query)
SELECT sc.stellar_account, sc.status, sc.updated_at
FROM stellar_account_search_cache sc
LEFT JOIN stellar_creator_account_lineage lc 
  ON sc.stellar_account = lc.stellar_account 
  AND sc.network_name = lc.network_name
WHERE lc.stellar_account IS NULL;
```

**Common Causes:**
- Pipeline interrupted during lineage fetch
- BigQuery query failed but cache was created
- Lineage data exceeded storage limits

**Prevention:**
- Ensure pipeline completes all stages
- Monitor "Failed Stages" metric
- Use atomic transactions for data storage

---

## 📈 Monitoring & Maintenance

### Regular Health Checks

**Daily:**
1. Check dashboard for any red (critical) alerts
2. Verify Stuck Records = 0
3. Verify Failed Stages = 0

**Weekly:**
1. Review Stale Records count
2. Refresh important accounts
3. Check Orphan Accounts count
4. Review BigQuery cost trends

**Monthly:**
1. Analyze Performance Metrics
2. Review estimated monthly BigQuery costs
3. Optimize pipeline configuration if needed
4. Clean up old test accounts

### Quick Actions Reference

| Issue | Quick Fix | Time |
|-------|-----------|------|
| Stuck Records | Admin → Force retry | 2 min |
| Failed Stages | Admin → Retry failed | 2 min |
| Stale Records | Admin → Refresh selected | 5 min |
| Orphan Accounts | Admin → Re-process | 5 min |
| High Costs | Config → Adjust limits | 2 min |

---

## 🔧 Admin Panel Quick Reference

### Key Admin Pages

1. **Stellar Account Search Cache**
   - URL: `/admin/apiApp/stellaraccountsearchcache/`
   - Manage: All cached account searches
   - Actions: Refresh, retry, delete

2. **Stellar Creator Account Lineage**
   - URL: `/admin/apiApp/stellarcreatoraccountlineage/`
   - Manage: Lineage relationship data
   - Actions: View, delete, re-process

3. **Stellar Account Stage Execution**
   - URL: `/admin/apiApp/stellaraccountstageexecution/`
   - Manage: Pipeline stage logs
   - Actions: Retry failed, view errors

4. **BigQuery Pipeline Config**
   - URL: `/admin/apiApp/bigquerypipelineconfig/`
   - Manage: Pipeline settings
   - Configure: Cost limits, pipeline mode, API fallback

### Common Admin Actions

**Bulk Operations:**
```
1. Select records (checkboxes)
2. Choose action from dropdown
3. Click "Go" button
4. Confirm action
```

**Filtering:**
```
1. Use right sidebar filters
2. Click "Filter" button
3. Results update automatically
```

**Search:**
```
1. Use search box at top
2. Enter account address or partial match
3. Press Enter
```

---

## 🆘 Emergency Procedures

### System Not Processing Accounts

1. **Check Cron Status** on dashboard
   - If ERROR/FAILED → Restart cron workflow
   
2. **Check BigQuery Pipeline** workflow
   - Ensure it's RUNNING status
   - Check logs for errors
   
3. **Verify Database Connection**
   - Test admin panel access
   - Check if queries execute

4. **Review Cost Limits**
   - Admin → BigQuery Pipeline Config
   - Ensure limits aren't blocking all queries

### All Records Stuck

> 🚨 **DANGER**: These are emergency procedures. Use Django Admin first whenever possible. Always backup your database before running UPDATE queries.

1. **Emergency Reset (Advanced - Use Admin Instead):**
   ```sql
   -- CAUTION: This UPDATE affects all processing records
   -- Recommended: Use Admin → Search Cache → Actions → "Reset to pending" instead
   UPDATE stellar_account_search_cache 
   SET status = 'PENDING' 
   WHERE status IN ('PROCESSING', 'IN_PROGRESS');
   ```

2. **Restart Workflows:**
   - Restart "BigQuery Pipeline" workflow
   - Restart "Django Server" workflow

3. **Clear Processing Locks:**
   - Admin → Search Cache
   - Filter by status: PROCESSING
   - Actions → "Reset to pending"

### Database Full / Storage Issues

> 🚨 **DANGER - DESTRUCTIVE OPERATIONS**: These DELETE queries permanently remove data. ALWAYS backup your database first. Consider using Django Admin → Delete selected instead for safety.

1. **Clear Old Data (Advanced - High Risk):**
   ```sql
   -- STEP 1 (SAFE): Review what will be deleted (read-only)
   SELECT COUNT(*), MIN(updated_at), MAX(updated_at)
   FROM stellar_account_search_cache 
   WHERE updated_at < NOW() - INTERVAL '30 days'
   AND stellar_account NOT IN (
     SELECT stellar_account FROM stellar_creator_account_lineage
   );
   
   -- STEP 2 (DESTRUCTIVE): Only run after backup and verification
   -- DANGER: This permanently deletes data older than 30 days
   -- DELETE FROM stellar_account_search_cache 
   -- WHERE updated_at < NOW() - INTERVAL '30 days'
   -- AND stellar_account NOT IN (
   --   SELECT stellar_account FROM stellar_creator_account_lineage
   -- );
   ```
   
   **Safer Alternative**: Use Django Admin → Stellar Account Search Cache → Filter by date → Select → Delete selected

2. **Archive Stage Executions (Advanced - Moderate Risk):**
   ```sql
   -- STEP 1 (SAFE): Review what will be deleted (read-only)
   SELECT COUNT(*), MIN(created_at), MAX(created_at)
   FROM stellar_account_stage_execution 
   WHERE created_at < NOW() - INTERVAL '7 days';
   
   -- STEP 2 (DESTRUCTIVE): Only run after backup
   -- DANGER: This permanently deletes stage logs older than 7 days
   -- DELETE FROM stellar_account_stage_execution 
   -- WHERE created_at < NOW() - INTERVAL '7 days';
   ```
   
   **Safer Alternative**: Use Django Admin → Stage Execution → Filter by date → Select → Delete selected

---

## 💡 Best Practices

### Data Hygiene
- Clean up test accounts regularly
- Delete failed records after investigation
- Archive old stage execution logs
- Maintain stale records below 20%

### Performance Optimization
- Keep stuck records at 0
- Process accounts during off-peak hours
- Use BigQuery for bulk operations
- Use API fallback for rate limits

### Cost Management
- Monitor estimated monthly costs
- Set conservative cost limits initially
- Use API-only mode for low-priority accounts
- Enable age restrictions (>1 year accounts)

### Monitoring
- Check dashboard daily for critical alerts
- Set up external monitoring (if available)
- Review pipeline logs weekly
- Track processing trends monthly

---

## 📞 Getting Help

### Diagnostic Information to Collect

When reporting issues, include:

1. **Dashboard Statistics:**
   - Stuck Records count
   - Failed Stages count
   - Stale/Orphan counts

2. **Error Details:**
   - Error message from admin
   - Account address affected
   - Timestamp of issue

3. **System State:**
   - Cron status
   - Pipeline mode configured
   - Cost limit settings

4. **Recent Changes:**
   - Configuration updates
   - Pipeline mode changes
   - New accounts processed

### Log Locations

- **Django Server**: `/tmp/logs/Django_Server_*.log`
- **BigQuery Pipeline**: `/tmp/logs/BigQuery_Pipeline_*.log`
- **Browser Console**: Check browser DevTools → Console tab

---

## ✅ Health Check Checklist

Use this checklist to verify system health:

- [ ] Stuck Records = 0
- [ ] Failed Stages = 0
- [ ] Stale Records < 20% of total
- [ ] Orphan Accounts < 5% of total
- [ ] Cron Status = SUCCESS
- [ ] BigQuery cost within budget
- [ ] All workflows RUNNING
- [ ] No critical alerts on dashboard
- [ ] Processing time reasonable (<5 min avg)

**All checked?** Your system is healthy! ✨

---

*Last Updated: October 2025*  
*StellarMapWeb Dashboard Troubleshooting Guide*
