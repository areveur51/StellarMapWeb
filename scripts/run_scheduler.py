#!/usr/bin/env python
"""
Background Scheduler for BigQuery Pipeline
Runs the pipeline periodically to process PENDING records.
"""

import os
import sys
import logging
import django
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StellarMapWeb.settings')
django.setup()

from django.core.management import call_command

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SCHEDULER] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def run_bigquery_pipeline():
    """Execute the BigQuery pipeline to process PENDING records."""
    try:
        logger.info("="*60)
        logger.info("Starting scheduled BigQuery pipeline run")
        logger.info("="*60)
        
        call_command('bigquery_pipeline', '--limit', '100')
        
        logger.info("="*60)
        logger.info("Completed scheduled BigQuery pipeline run")
        logger.info("="*60)
    except Exception as e:
        logger.error(f"Error running BigQuery pipeline: {e}", exc_info=True)


def main():
    """Start the background scheduler."""
    scheduler = BlockingScheduler()
    
    # Schedule the pipeline to run every 2 hours
    # You can modify this cron expression to change the frequency:
    # - "0 */2 * * *" = every 2 hours
    # - "*/30 * * * *" = every 30 minutes
    # - "0 */6 * * *" = every 6 hours
    cron_schedule = os.environ.get('PIPELINE_SCHEDULE', '0 */2 * * *')
    
    scheduler.add_job(
        run_bigquery_pipeline,
        trigger=CronTrigger.from_crontab(cron_schedule),
        id='bigquery_pipeline',
        name='BigQuery Pipeline - Process PENDING Records',
        replace_existing=True
    )
    
    logger.info("="*60)
    logger.info("BigQuery Pipeline Scheduler Started")
    logger.info(f"Schedule: {cron_schedule} (every 2 hours)")
    logger.info("="*60)
    
    # Get next run time after scheduler starts
    job = scheduler.get_jobs()[0] if scheduler.get_jobs() else None
    if job:
        logger.info(f"Job: {job.name}")
    logger.info("="*60)
    
    # Run immediately on startup (optional - comment out if you don't want this)
    logger.info("Running pipeline immediately on startup...")
    run_bigquery_pipeline()
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
        scheduler.shutdown()


if __name__ == '__main__':
    main()
