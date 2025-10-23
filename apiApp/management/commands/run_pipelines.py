"""
Unified Pipeline Runner - Respects Configuration

This command reads the pipeline configuration from the database and runs
the appropriate pipeline(s) based on the pipeline_mode setting:
- API_ONLY: Only runs API pipeline
- BIGQUERY_WITH_API_FALLBACK: Runs BigQuery pipeline (API runs separately)
- BIGQUERY_ONLY: Only runs BigQuery pipeline
"""

import logging
import time
from django.core.management.base import BaseCommand
from django.core.management import call_command
from apiApp.model_loader import BigQueryPipelineConfig

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Unified pipeline runner that respects configuration settings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Run in continuous loop (for production deployment)'
        )

    def handle(self, *args, **options):
        loop = options['loop']

        # Load configuration from database
        config = self._load_config()
        if not config:
            self.stdout.write(self.style.ERROR('Failed to load configuration'))
            return

        api_interval = config.api_pipeline_interval_seconds
        bigquery_interval = config.bigquery_pipeline_interval_seconds
        api_batch = config.api_pipeline_batch_size
        bigquery_batch = config.batch_size

        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*60}\n'
            f'Unified Pipeline Runner\n'
            f'{"="*60}\n'
            f'Loop Mode: {loop}\n'
            f'Pipeline Mode: {config.pipeline_mode}\n'
            f'API Interval: {api_interval}s (batch: {api_batch})\n'
            f'BigQuery Interval: {bigquery_interval}s (batch: {bigquery_batch})\n'
            f'{"="*60}\n'
        ))

        if loop:
            self._run_continuous_loop()
        else:
            self._run_single_iteration()

    def _load_config(self):
        """Load pipeline configuration from database."""
        try:
            config = BigQueryPipelineConfig.objects.filter(config_id='default').first()
            if config:
                return config
            
            # No configuration exists - create default
            self.stdout.write(self.style.WARNING(
                'No configuration found, creating default with API_ONLY mode'
            ))
            config = BigQueryPipelineConfig.create(
                config_id='default',
                bigquery_enabled=False,
                cost_limit_usd=0.71,
                size_limit_mb=148900.0,
                pipeline_mode='API_ONLY',
                instant_query_max_age_days=365,
                api_fallback_enabled=True,
                horizon_max_operations=200,
                horizon_child_max_pages=5,
                batch_size=100
            )
            return config
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'Failed to load configuration: {e}'
            ))
            return None

    def _run_single_iteration(self):
        """Run pipelines once based on configuration."""
        config = self._load_config()
        if not config:
            return

        pipeline_mode = config.pipeline_mode
        api_batch = config.api_pipeline_batch_size
        bigquery_batch = config.batch_size
        
        self.stdout.write(self.style.SUCCESS(
            f'\nPipeline Mode: {pipeline_mode}'
        ))

        if pipeline_mode == 'API_ONLY':
            self.stdout.write(self.style.SUCCESS(f'Running API Pipeline only (batch: {api_batch})...'))
            call_command('api_pipeline', limit=api_batch)
        
        elif pipeline_mode == 'BIGQUERY_ONLY':
            self.stdout.write(self.style.SUCCESS(f'Running BigQuery Pipeline only (batch: {bigquery_batch})...'))
            call_command('bigquery_pipeline', limit=bigquery_batch)
        
        elif pipeline_mode == 'BIGQUERY_WITH_API_FALLBACK':
            self.stdout.write(self.style.SUCCESS(f'Running BigQuery Pipeline (batch: {bigquery_batch}, API fallback enabled)...'))
            call_command('bigquery_pipeline', limit=bigquery_batch)

    def _run_continuous_loop(self):
        """Run pipelines continuously based on configuration."""
        last_api_run = 0
        last_bigquery_run = 0

        while True:
            try:
                # Reload config each iteration to pick up changes
                config = self._load_config()
                if not config:
                    self.stdout.write(self.style.ERROR('No configuration found, sleeping...'))
                    time.sleep(60)
                    continue

                pipeline_mode = config.pipeline_mode
                api_interval = config.api_pipeline_interval_seconds
                bigquery_interval = config.bigquery_pipeline_interval_seconds
                api_batch = config.api_pipeline_batch_size
                bigquery_batch = config.batch_size
                current_time = time.time()

                if pipeline_mode == 'API_ONLY':
                    if current_time - last_api_run >= api_interval:
                        self.stdout.write(self.style.SUCCESS(
                            f'\n[{self._get_timestamp()}] Running API Pipeline (batch: {api_batch})...'
                        ))
                        call_command('api_pipeline', limit=api_batch)
                        last_api_run = current_time

                elif pipeline_mode == 'BIGQUERY_ONLY':
                    if current_time - last_bigquery_run >= bigquery_interval:
                        self.stdout.write(self.style.SUCCESS(
                            f'\n[{self._get_timestamp()}] Running BigQuery Pipeline (batch: {bigquery_batch})...'
                        ))
                        call_command('bigquery_pipeline', limit=bigquery_batch)
                        last_bigquery_run = current_time

                elif pipeline_mode == 'BIGQUERY_WITH_API_FALLBACK':
                    # Run BigQuery pipeline at bigquery_interval
                    if current_time - last_bigquery_run >= bigquery_interval:
                        self.stdout.write(self.style.SUCCESS(
                            f'\n[{self._get_timestamp()}] Running BigQuery Pipeline (batch: {bigquery_batch})...'
                        ))
                        call_command('bigquery_pipeline', limit=bigquery_batch)
                        last_bigquery_run = current_time
                    
                    # Also run API pipeline at api_interval for fallback
                    if current_time - last_api_run >= api_interval:
                        self.stdout.write(self.style.SUCCESS(
                            f'\n[{self._get_timestamp()}] Running API Pipeline (batch: {api_batch}, fallback)...'
                        ))
                        call_command('api_pipeline', limit=api_batch)
                        last_api_run = current_time

                # Sleep for a short interval
                time.sleep(10)

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Error in pipeline loop: {e}'
                ))
                logger.exception('Pipeline loop error')
                time.sleep(60)

    def _get_timestamp(self):
        """Get current timestamp for logging."""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
