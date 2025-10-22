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
from django.utils import timezone
from apiApp.models import SchedulerConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SCHEDULER] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_scheduler_config():
    """Load scheduler configuration from database, create if doesn't exist."""
    try:
        config, created = SchedulerConfig.objects.get_or_create(
            config_id='default',
            defaults={
                'scheduler_enabled': True,
                'cron_schedule': '0 */2 * * *',
                'batch_limit': 100,
                'run_on_startup': True,
            }
        )
        if created:
            logger.info("Created default scheduler configuration")
        return config
    except Exception as e:
        logger.error(f"Error loading scheduler config: {e}")
        # Return defaults if database error
        class DefaultConfig:
            scheduler_enabled = True
            cron_schedule = '0 */2 * * *'
            batch_limit = 100
            run_on_startup = True
        return DefaultConfig()


def run_bigquery_pipeline():
    """Execute the BigQuery pipeline to process PENDING records."""
    config = load_scheduler_config()
    
    # Check if scheduler is enabled
    if not config.scheduler_enabled:
        logger.warning("Scheduler is DISABLED in admin configuration. Skipping run.")
        return
    
    try:
        logger.info("="*60)
        logger.info("Starting scheduled BigQuery pipeline run")
        logger.info(f"Batch limit: {config.batch_limit}")
        logger.info("="*60)
        
        # Track start time
        start_time = timezone.now()
        
        # Run the pipeline
        call_command('bigquery_pipeline', '--limit', str(config.batch_limit))
        
        # Update last run statistics
        try:
            config.last_run_at = timezone.now()
            config.last_run_status = 'SUCCESS'
            # Note: processed/failed counts would need to be returned from command
            config.save()
        except Exception as save_error:
            logger.warning(f"Could not update run statistics: {save_error}")
        
        logger.info("="*60)
        logger.info("Completed scheduled BigQuery pipeline run")
        logger.info("="*60)
    except Exception as e:
        logger.error(f"Error running BigQuery pipeline: {e}", exc_info=True)
        
        # Update last run status to FAILED
        try:
            config.last_run_at = timezone.now()
            config.last_run_status = 'FAILED'
            config.save()
        except:
            pass


def main():
    """Start the background scheduler."""
    # Load configuration
    config = load_scheduler_config()
    
    if not config.scheduler_enabled:
        logger.warning("="*60)
        logger.warning("Scheduler is DISABLED in admin configuration")
        logger.warning("Enable it at /admin/apiApp/schedulerconfig/")
        logger.warning("="*60)
        return
    
    scheduler = BlockingScheduler()
    
    # Use schedule from admin configuration (fallback to env var if needed)
    cron_schedule = config.cron_schedule or os.environ.get('PIPELINE_SCHEDULE', '0 */2 * * *')
    
    scheduler.add_job(
        run_bigquery_pipeline,
        trigger=CronTrigger.from_crontab(cron_schedule),
        id='bigquery_pipeline',
        name='BigQuery Pipeline - Process PENDING Records',
        replace_existing=True
    )
    
    logger.info("="*60)
    logger.info("BigQuery Pipeline Scheduler Started")
    logger.info(f"Schedule: {cron_schedule}")
    logger.info(f"Batch Limit: {config.batch_limit}")
    logger.info(f"Run on Startup: {config.run_on_startup}")
    logger.info("Configure at: /admin/apiApp/schedulerconfig/")
    logger.info("="*60)
    
    # Get next run time after scheduler starts
    job = scheduler.get_jobs()[0] if scheduler.get_jobs() else None
    if job:
        logger.info(f"Job: {job.name}")
    logger.info("="*60)
    
    # Run immediately on startup (if configured)
    if config.run_on_startup:
        logger.info("Running pipeline immediately on startup...")
        run_bigquery_pipeline()
    else:
        logger.info("Startup run disabled. Waiting for scheduled run.")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
        scheduler.shutdown()


if __name__ == '__main__':
    main()
