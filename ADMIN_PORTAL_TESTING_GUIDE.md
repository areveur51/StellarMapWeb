# Admin Portal Manual Testing Guide

## Purpose

This guide provides manual testing procedures for the Django Admin Portal to ensure all links and pages work correctly. Use this checklist after making database schema changes or updating admin configurations.

## Created

October 22, 2025 - After fixing `api_pipeline_enabled` field regression

## Prerequisites

1. Django server must be running
2. You must have admin credentials
3. Database schema must be up-to-date

## Manual Test Checklist

### 1. Admin Login & Index

- [ ] Navigate to `/admin/`
- [ ] Enter admin credentials
- [ ] Verify admin index page loads successfully
- [ ] Verify "APIAPP" section is visible

### 2. BigQuery Pipeline Configuration

- [ ] Click on "BigQuery Pipeline Configuration"
- [ ] Verify changelist page loads without errors
- [ ] Verify you can see existing configurations
- [ ] Click "+ Add BigQuery Pipeline Configuration"
- [ ] Verify all fields are present:
  - [ ] config_id
  - [ ] bigquery_enabled
  - [ ] cost_limit_usd
  - [ ] pipeline_mode
  - [ ] api_pipeline_enabled
  - [ ] api_pipeline_batch_size
  - [ ] api_pipeline_interval_seconds
- [ ] Click on an existing configuration
- [ ] Verify change page loads successfully
- [ ] Try updating a field and saving
- [ ] Verify changes are saved

### 3. API Rate Limiter Configuration

- [ ] Click on "API Rate Limiter Configuration"
- [ ] Verify changelist page loads
- [ ] Click on existing config or add new one
- [ ] Verify all fields load correctly

### 4. Scheduler Configuration

- [ ] Click on "Scheduler Configuration"
- [ ] Verify changelist page loads
- [ ] Click on existing config
- [ ] Verify change page loads

### 5. Management Cron Healths

- [ ] Click on "Management cron healths"
- [ ] Verify changelist page loads
- [ ] Verify health records are displayed

### 6. Stellar Account Models

- [ ] Click on "Stellar account search caches"
- [ ] Verify changelist loads
- [ ] Click on "Stellar account stage executions"
- [ ] Verify changelist loads
- [ ] Click on "Stellar creator account lineages"
- [ ] Verify changelist loads

## Common Errors to Watch For

### Database Schema Errors

**Error**: `OperationalError: no such column: [table].[column]`  
**Solution**: Database schema needs updating. Run schema migration script.

**Example**:
```
OperationalError: no such column: bigquery_pipeline_config.api_pipeline_enabled
```

### Migration Errors

**Error**: `LookupError: No installed app with label 'apiApp'`  
**Solution**: This occurs during test database setup due to django-cassandra-engine conflicts. For production databases, use `python manage.py migrate` to apply schema changes. For test environments, manual testing is recommended until migration compatibility is resolved.

## Fixing Schema Issues

If you encounter a missing column error:

### Proper Solution: Apply Django Migrations

```bash
# 1. Check which migrations need to be applied
python manage.py showmigrations apiApp

# 2. Apply pending migrations
python manage.py migrate

# 3. Verify migrations were applied
python manage.py showmigrations apiApp
```

All migrations should show [X]:
```
apiApp
 [X] 0001_initial
 [X] 0002_auto_20251014_1317
 [X] 0003_add_scheduler_config
 [X] 0004_add_hva_threshold_config
 [X] 0005_add_dual_pipeline_tracking
 [X] 0006_add_api_rate_limiter_config
```

### Legacy Database Repair (Only if columns were manually added)

If you previously added columns manually with ALTER TABLE and now need to sync migration state:

```bash
# Apply migrations as "fake" to mark them as applied without changing schema
python manage.py migrate apiApp 0006 --fake

# Verify migration state
python manage.py showmigrations apiApp
```

**⚠️ Important**: Never manually edit the database with ALTER TABLE. Always use Django migrations.

### Verification

After applying migrations, verify the model works:

```python
python manage.py shell
```

```python
from apiApp.models import BigQueryPipelineConfig

config = BigQueryPipelineConfig.objects.first()
if config:
    print(f"✅ Config loaded: {config}")
    print(f"   - api_pipeline_enabled: {config.api_pipeline_enabled}")
else:
    print("⚠️  No config found")
```

## Automated Tests

Automated regression tests are available in:
- `apiApp/tests/test_admin_portal_regression.py`

Note: Tests may fail due to migration system conflicts with Cassandra engine. Manual testing is recommended.

## Test Results Template

Date: __________  
Tester: __________

| Test Section | Status | Notes |
|--------------|--------|-------|
| Admin Login & Index | ☐ Pass ☐ Fail |  |
| BigQuery Pipeline Config | ☐ Pass ☐ Fail |  |
| API Rate Limiter Config | ☐ Pass ☐ Fail |  |
| Scheduler Config | ☐ Pass ☐ Fail |  |
| Management Cron Healths | ☐ Pass ☐ Fail |  |
| Stellar Account Models | ☐ Pass ☐ Fail |  |

## Quick Verification Script

Run this to verify all admin models are registered:

```python
python manage.py shell
```

```python
from django.contrib import admin
from apiApp.models import BigQueryPipelineConfig, SchedulerConfig

# Check registration
print("BigQueryPipelineConfig registered:", admin.site.is_registered(BigQueryPipelineConfig))
print("SchedulerConfig registered:", admin.site.is_registered(SchedulerConfig))

# Check model can be queried
config = BigQueryPipelineConfig.objects.first()
if config:
    print(f"✅ Config loaded: {config}")
    print(f"   - api_pipeline_enabled: {config.api_pipeline_enabled}")
else:
    print("⚠️  No config found")
```

## Related Documentation

- `apiApp/tests/test_admin_portal_regression.py` - Automated regression tests
- `REGRESSION_TESTING_STRATEGY.md` - Prevention strategies
- `TECHNICAL_ARCHITECTURE.md` - System architecture

## Maintenance

Update this checklist when:
1. New admin models are added
2. New fields are added to existing models
3. Admin interface changes are made
4. Database schema changes occur

## Success Criteria

All checkboxes must pass for the admin portal to be considered healthy:
- ✅ All pages load without 500 errors
- ✅ All models are accessible
- ✅ CRUD operations (Create, Read, Update, Delete) work
- ✅ No database schema errors in logs
- ✅ All fields display correctly
