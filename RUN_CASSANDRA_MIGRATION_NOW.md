# Run Cassandra Migration - Step-by-Step Guide

## Quick Start (5 Minutes)

### Step 1: Access Astra DB CQL Console

1. Go to https://astra.datastax.com/
2. Log in to your account
3. Select your database: **stellarmapweb_keyspace**
4. Click on the **"CQL Console"** tab (or "Connect" → "CQL Console")

### Step 2: Copy and Paste This CQL Script

**IMPORTANT**: Copy this ENTIRE block and paste it into the CQL console, then press Enter:

```cql
-- Cassandra Migration: Add Dual-Pipeline Tracking Fields
-- Safe to run - only adds new columns, doesn't modify existing data

-- Add pipeline_source column
ALTER TABLE stellarmapweb_keyspace.stellar_creator_account_lineage 
ADD pipeline_source text;

-- Add last_pipeline_attempt column
ALTER TABLE stellarmapweb_keyspace.stellar_creator_account_lineage 
ADD last_pipeline_attempt timestamp;

-- Add processing_started_at column
ALTER TABLE stellarmapweb_keyspace.stellar_creator_account_lineage 
ADD processing_started_at timestamp;
```

### Step 3: Verify It Worked

After running the commands above, verify the columns were added by running:

```cql
DESCRIBE TABLE stellarmapweb_keyspace.stellar_creator_account_lineage;
```

You should see the three new columns at the bottom of the table definition:
- `pipeline_source text`
- `last_pipeline_attempt timestamp`
- `processing_started_at timestamp`

### Step 4: Notify Me

Once you've run the migration and verified it worked, **respond with "migration complete"** and I'll:
1. Uncomment the model fields in `apiApp/models_cassandra.py`
2. Restart the workflows
3. Verify the dual-pipeline feature is working

## What This Migration Does

### Safe Changes Only ✅
- Adds 3 new columns to existing table
- Does NOT modify existing data
- Does NOT change primary keys
- Does NOT delete anything
- Existing queries continue to work

### New Columns Added

1. **pipeline_source** (text)
   - Tracks which pipeline created each record: 'BIGQUERY', 'API', or 'BIGQUERY_WITH_API_FALLBACK'
   - Optional field - defaults to NULL for existing records

2. **last_pipeline_attempt** (timestamp)
   - Tracks the last time either pipeline attempted to process this account
   - Used for retry logic and stuck record detection

3. **processing_started_at** (timestamp)
   - Tracks when current processing started
   - Used to detect stuck/hung processing

## Troubleshooting

### Error: "Keyspace does not exist"

If you get this error, your keyspace name might be different. Check your keyspace name and replace `stellarmapweb_keyspace` with your actual keyspace name.

To find your keyspace name:
```cql
DESCRIBE KEYSPACES;
```

### Error: "Column already exists"

This means the migration was already run successfully. You can proceed to Step 4.

### Error: "Table does not exist"

Verify your table name with:
```cql
DESCRIBE TABLES;
```

The table should be named `stellar_creator_account_lineage`.

## What Happens After Migration

Once you confirm the migration is complete, I will:

1. **Uncomment Model Fields** in `apiApp/models_cassandra.py`:
   ```python
   pipeline_source = cassandra_columns.Text(max_length=64, default='')
   last_pipeline_attempt = cassandra_columns.DateTime(default=None)
   processing_started_at = cassandra_columns.DateTime(default=None)
   ```

2. **Restart All Workflows**:
   - Django Server
   - API Pipeline
   - BigQuery Pipeline (if enabled)

3. **Verify Dual-Pipeline Feature**:
   - Dashboard pipeline stats work without errors
   - API Pipeline can track processed records
   - BigQuery Pipeline marks records with source

4. **Run Smoke Tests**:
   - HVA Leaderboard still displays accounts
   - Query Builder still executes queries
   - All existing functionality preserved

## Benefits After Migration

✅ **Dual-Pipeline Tracking**: Know which pipeline created each account record
✅ **Pipeline Performance Metrics**: Compare BigQuery vs API pipeline efficiency
✅ **Dashboard Pipeline Stats**: See breakdown by data source
✅ **Better Retry Logic**: Track which accounts need reprocessing
✅ **Stuck Record Detection**: Identify and recover hung processing

## Safety Notes

- Migration is **non-destructive** - only adds columns
- Existing data remains unchanged
- Queries continue to work during migration
- Can be safely rolled back by dropping columns (not recommended)
- Takes ~1-2 seconds to execute

## Alternative: If You Can't Access Astra DB Console

If you don't have access to the Astra DB CQL console, you'll need to:

1. Contact your database administrator
2. Provide them this migration file: `cassandra_migration_dual_pipeline.cql`
3. Ask them to run it on the production Cassandra instance

## Questions?

- **Q: Will this affect my existing data?**
  - A: No, it only adds new columns. Existing data is untouched.

- **Q: Can I run this during business hours?**
  - A: Yes, it's a safe additive change with no downtime.

- **Q: What if something goes wrong?**
  - A: The worst case is the columns aren't added and you see the same errors as before. Nothing will break.

- **Q: Do I need to stop the application?**
  - A: No, the application can keep running during the migration.

---

**Ready?** Copy the CQL commands from Step 2, paste into your Astra DB CQL console, and let me know when it's done!
