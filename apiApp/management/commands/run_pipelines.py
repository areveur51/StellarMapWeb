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
        parser.add_argument(
            '--api-interval',
            type=int,
            default=120,
            help='Interval in seconds between API pipeline runs (default: 120)'
        )
        parser.add_argument(
            '--bigquery-interval',
            type=int,
            default=300,
            help='Interval in seconds between BigQuery pipeline runs (default: 300)'
        )

    def handle(self, *args, **options):
        loop = options['loop']
        api_interval = options['api_interval']
        bigquery_interval = options['bigquery_interval']

        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*60}\n'
            f'Unified Pipeline Runner\n'
            f'{"="*60}\n'
            f'Loop Mode: {loop}\n'
            f'API Interval: {api_interval}s\n'
            f'BigQuery Interval: {bigquery_interval}s\n'
            f'{"="*60}\n'
        ))

        if loop:
            self._run_continuous_loop(api_interval, bigquery_interval)
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
        
        self.stdout.write(self.style.SUCCESS(
            f'\nPipeline Mode: {pipeline_mode}'
        ))

        if pipeline_mode == 'API_ONLY':
            self.stdout.write(self.style.SUCCESS('Running API Pipeline only...'))
            call_command('api_pipeline', limit=3)
        
        elif pipeline_mode == 'BIGQUERY_ONLY':
            self.stdout.write(self.style.SUCCESS('Running BigQuery Pipeline only...'))
            call_command('bigquery_pipeline', limit=100)
        
        elif pipeline_mode == 'BIGQUERY_WITH_API_FALLBACK':
            self.stdout.write(self.style.SUCCESS('Running BigQuery Pipeline (API fallback enabled)...'))
            call_command('bigquery_pipeline', limit=100)

    def _run_continuous_loop(self, api_interval, bigquery_interval):
        """Run pipelines continuously based on configuration."""
        last_api_run = 0
        last_bigquery_run = 0

        while True:
            try:
                config = self._load_config()
                if not config:
                    self.stdout.write(self.style.ERROR('No configuration found, sleeping...'))
                    time.sleep(60)
                    continue

                pipeline_mode = config.pipeline_mode
                current_time = time.time()

                if pipeline_mode == 'API_ONLY':
                    if current_time - last_api_run >= api_interval:
                        self.stdout.write(self.style.SUCCESS(
                            f'\n[{self._get_timestamp()}] Running API Pipeline...'
                        ))
                        call_command('api_pipeline', limit=3)
                        last_api_run = current_time

                elif pipeline_mode == 'BIGQUERY_ONLY':
                    if current_time - last_bigquery_run >= bigquery_interval:
                        self.stdout.write(self.style.SUCCESS(
                            f'\n[{self._get_timestamp()}] Running BigQuery Pipeline...'
                        ))
                        call_command('bigquery_pipeline', limit=100)
                        last_bigquery_run = current_time

                elif pipeline_mode == 'BIGQUERY_WITH_API_FALLBACK':
                    # Run BigQuery pipeline at bigquery_interval
                    if current_time - last_bigquery_run >= bigquery_interval:
                        self.stdout.write(self.style.SUCCESS(
                            f'\n[{self._get_timestamp()}] Running BigQuery Pipeline...'
                        ))
                        call_command('bigquery_pipeline', limit=100)
                        last_bigquery_run = current_time
                    
                    # Also run API pipeline at api_interval for fallback
                    if current_time - last_api_run >= api_interval:
                        self.stdout.write(self.style.SUCCESS(
                            f'\n[{self._get_timestamp()}] Running API Pipeline (fallback)...'
                        ))
                        call_command('api_pipeline', limit=3)
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
