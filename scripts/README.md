# Production Scripts

## Background Scheduler

The `run_scheduler.py` script runs the BigQuery pipeline automatically on a schedule to process PENDING records.

### Configuration

**Schedule**: Set via `PIPELINE_SCHEDULE` environment variable (default: `0 */2 * * *` = every 2 hours)

Common schedules:
- `0 */2 * * *` - Every 2 hours (default)
- `*/30 * * * *` - Every 30 minutes
- `0 */6 * * *` - Every 6 hours
- `0 0 * * *` - Once per day at midnight

### How It Works

1. **Production Deployment**: `start_production.sh` runs both:
   - Background scheduler (processes PENDING records)
   - Gunicorn web server (serves Django app)

2. **Pipeline Execution**:
   - Runs `python manage.py bigquery_pipeline --limit 100`
   - Processes up to 100 PENDING accounts per run
   - Uses BIGQUERY_WITH_API_FALLBACK configuration from admin portal

3. **Monitoring**:
   - All runs are logged with timestamps
   - Errors are captured and logged
   - Check deployment logs to see scheduler activity

### Manual Execution

To test the scheduler locally:
```bash
python scripts/run_scheduler.py
```

To run the pipeline manually:
```bash
python manage.py bigquery_pipeline --limit 100
```

### Customization

Edit `run_scheduler.py` to:
- Change the schedule (modify `cron_schedule` variable)
- Adjust batch size (modify `--limit` parameter)
- Disable immediate run on startup (comment out the startup run)
