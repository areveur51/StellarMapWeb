# apiApp/models.py
import datetime
import uuid
from django.conf import settings

# Environment-based model selection
ENV = settings.ENV if hasattr(settings, 'ENV') else 'development'

if ENV in ['production', 'replit']:
    # Production/Replit mode: Use Cassandra models
    try:
        from cassandra.cqlengine import columns as cassandra_columns
        from django_cassandra_engine.models import DjangoCassandraModel
        from .models_cassandra import *
    except ImportError as e:
        raise ImportError(f"Production/Replit mode requires Cassandra dependencies: {e}")
else:
    # Local development mode: Use SQLite models
    from .models_local import *

# Always import the BigQueryPipelineConfig (Django model)
from django.db import models as django_models

class BigQueryPipelineConfig(django_models.Model):
    """
    Configuration settings for BigQuery pipeline behavior.

    Singleton model - only one configuration record should exist.
    Controls cost limits, pipeline modes, age restrictions, and API fallback behavior.

    Stored in SQLite/default database for easy admin access.
    """
    # Singleton primary key
    config_id = django_models.CharField(max_length=50, primary_key=True, default='default')

    # BigQuery Cost Controls
    bigquery_enabled = django_models.BooleanField(default=True)
    cost_limit_usd = django_models.FloatField(default=0.71)  # Maximum cost per query in USD
    size_limit_mb = django_models.FloatField(default=148900.0)  # Maximum query size in MB (~145GB)

    # Pipeline Strategy
    pipeline_mode = django_models.CharField(max_length=50, default='BIGQUERY_WITH_API_FALLBACK')
    # Options:
    # - 'BIGQUERY_ONLY': Use only BigQuery, fail if blocked by cost controls
    # - 'API_ONLY': Use only Horizon/Stellar Expert APIs (no BigQuery)
    # - 'BIGQUERY_WITH_API_FALLBACK': Try BigQuery first, fall back to APIs if blocked (RECOMMENDED)

    # Age Restrictions (in days)
    instant_query_max_age_days = django_models.IntegerField(default=365)  # 1 year
    # Accounts older than this use existing data or queue for batch processing

    # API Fallback Settings
    api_fallback_enabled = django_models.BooleanField(default=True)
    horizon_max_operations = django_models.IntegerField(default=200)  # Max operations to fetch for creator discovery
    horizon_child_max_pages = django_models.IntegerField(default=5)  # Max pages for child account discovery (200 ops/page)

    # Child Account Collection
    bigquery_max_children = django_models.IntegerField(default=100000)  # Max child accounts to discover via BigQuery
    bigquery_child_page_size = django_models.IntegerField(default=10000)  # Pagination size for child queries

    # Batch Processing
    batch_processing_enabled = django_models.BooleanField(default=True)
    batch_size = django_models.IntegerField(default=6)  # Number of accounts to process per batch run (slow continuous retrieval)

    # Data Freshness
    cache_ttl_hours = django_models.IntegerField(default=12)  # How long before data is considered stale

    # High Value Account (HVA) Settings
    hva_threshold_xlm = django_models.FloatField(
        default=100000.0,
        help_text="Minimum XLM balance to be considered a High Value Account (default: 100,000 XLM)"
    )
    
    hva_supported_thresholds = django_models.TextField(
        default='10000,50000,100000,500000,750000,1000000',
        help_text="Comma-separated list of XLM thresholds for multi-threshold leaderboards (e.g., 10000,50000,100000,500000,750000,1000000). Each threshold creates a separate leaderboard."
    )
    
    # API Pipeline Settings
    api_pipeline_enabled = django_models.BooleanField(
        default=True,
        help_text="Enable/disable the API-only pipeline for consistent PENDING record processing"
    )
    api_pipeline_batch_size = django_models.IntegerField(
        default=3,
        help_text="Number of accounts to process per API pipeline run (default: 3 for slow continuous retrieval)"
    )
    api_pipeline_interval_seconds = django_models.IntegerField(
        default=120,
        help_text="Time between API pipeline runs in seconds (default: 120 = 2 minutes)"
    )

    # Metadata
    created_at = django_models.DateTimeField(auto_now_add=True)
    updated_at = django_models.DateTimeField(auto_now=True)
    updated_by = django_models.CharField(max_length=255, blank=True)  # Admin username who last updated
    notes = django_models.TextField(blank=True)  # Admin notes about configuration changes

    class Meta:
        verbose_name = "BigQuery Pipeline Configuration"
        verbose_name_plural = "BigQuery Pipeline Configuration"
        # Always use default database (SQLite), not Cassandra
        # This is a Django admin config model, not a Cassandra model
        db_table = 'bigquery_pipeline_config'
        app_label = 'apiApp'

    def __str__(self):
        return f"BigQuery Pipeline Config (Cost Limit: ${self.cost_limit_usd}, Mode: {self.pipeline_mode})"


class SchedulerConfig(django_models.Model):
    """
    Configuration settings for the background scheduler that processes PENDING records.
    
    Singleton model - only one configuration record should exist.
    Controls schedule frequency, batch sizes, and execution behavior.
    
    Stored in SQLite/default database for easy admin access.
    """
    # Singleton primary key
    config_id = django_models.CharField(max_length=50, primary_key=True, default='default')
    
    # Scheduler Status
    scheduler_enabled = django_models.BooleanField(
        default=True,
        help_text="Enable/disable the background scheduler. When disabled, PENDING records won't be processed automatically."
    )
    
    # Schedule Configuration
    cron_schedule = django_models.CharField(
        max_length=50,
        default='*/3 * * * *',
        help_text="Cron expression for schedule (e.g., '*/3 * * * *' = every 3 minutes, '*/30 * * * *' = every 30 minutes)"
    )
    
    # Batch Processing
    batch_limit = django_models.IntegerField(
        default=6,
        help_text="Maximum number of PENDING accounts to process per scheduled run (slow continuous retrieval)"
    )
    
    # Execution Settings
    run_on_startup = django_models.BooleanField(
        default=True,
        help_text="Run the pipeline immediately when the scheduler starts (in addition to scheduled runs)"
    )
    
    # Monitoring
    last_run_at = django_models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last successful pipeline run"
    )
    last_run_status = django_models.CharField(
        max_length=50,
        blank=True,
        help_text="Status of the last run (SUCCESS, FAILED, etc.)"
    )
    last_run_processed = django_models.IntegerField(
        default=0,
        help_text="Number of accounts processed in the last run"
    )
    last_run_failed = django_models.IntegerField(
        default=0,
        help_text="Number of accounts that failed in the last run"
    )
    
    # Metadata
    created_at = django_models.DateTimeField(auto_now_add=True)
    updated_at = django_models.DateTimeField(auto_now=True)
    updated_by = django_models.CharField(max_length=255, blank=True, help_text="Admin username who last updated")
    notes = django_models.TextField(blank=True, help_text="Admin notes about configuration changes")
    
    class Meta:
        verbose_name = "Scheduler Configuration"
        verbose_name_plural = "Scheduler Configuration"
        db_table = 'scheduler_config'
        app_label = 'apiApp'
        # Force this model to use default database (SQLite), not Cassandra
        # This is a Django admin config model
        managed = True
    
    def __str__(self):
        status = "Enabled" if self.scheduler_enabled else "Disabled"
        return f"Scheduler Config ({status}, Schedule: {self.cron_schedule}, Batch: {self.batch_limit})"


class APIRateLimiterConfig(django_models.Model):
    """
    Configuration settings for API Rate Limiter - control rate limits as percentages.
    
    Singleton model - only one configuration record should exist.
    Allows admins to set API rate limits as percentages of maximum allowed rates.
    
    Maximum Rates:
    - Horizon API: 120 requests/minute
    - Stellar Expert API: 50 requests/minute
    
    Example: Setting horizon_percentage to 85% means 102 requests/minute (85% of 120).
    
    Stored in SQLite/default database for easy admin access.
    """
    # Singleton primary key
    config_id = django_models.CharField(max_length=50, primary_key=True, default='default')
    
    # Rate Limit Percentages (0-100%)
    horizon_percentage = django_models.IntegerField(
        default=100,
        help_text="Horizon API rate limit as percentage of max (100% = 120 req/min). Example: 85% = 102 req/min"
    )
    stellar_expert_percentage = django_models.IntegerField(
        default=83,
        help_text="Stellar Expert API rate limit as percentage of max (100% = 50 req/min). Example: 85% = 42 req/min"
    )
    
    # Calculated read-only values (auto-computed from percentages)
    @property
    def horizon_calls_per_minute(self):
        """Calculate actual Horizon calls/minute based on percentage."""
        max_calls = 120
        return int((self.horizon_percentage / 100.0) * max_calls)
    
    @property
    def stellar_expert_calls_per_minute(self):
        """Calculate actual Stellar Expert calls/minute based on percentage."""
        max_calls = 50
        return int((self.stellar_expert_percentage / 100.0) * max_calls)
    
    @property
    def horizon_delay_seconds(self):
        """Calculate delay between Horizon API calls."""
        calls_per_min = self.horizon_calls_per_minute
        if calls_per_min == 0:
            return 999999  # Effectively disabled
        return 60.0 / calls_per_min
    
    @property
    def stellar_expert_delay_seconds(self):
        """Calculate delay between Stellar Expert API calls."""
        calls_per_min = self.stellar_expert_calls_per_minute
        if calls_per_min == 0:
            return 999999  # Effectively disabled
        return 60.0 / calls_per_min
    
    # Metadata
    created_at = django_models.DateTimeField(auto_now_add=True)
    updated_at = django_models.DateTimeField(auto_now=True)
    updated_by = django_models.CharField(max_length=255, blank=True, help_text="Admin username who last updated")
    notes = django_models.TextField(blank=True, help_text="Admin notes about configuration changes")
    
    class Meta:
        verbose_name = "API Rate Limiter Configuration"
        verbose_name_plural = "API Rate Limiter Configuration"
        db_table = 'api_rate_limiter_config'
        app_label = 'apiApp'
        managed = True
    
    def __str__(self):
        return f"API Rate Limiter Config (Horizon: {self.horizon_percentage}% = {self.horizon_calls_per_minute} req/min, Expert: {self.stellar_expert_percentage}% = {self.stellar_expert_calls_per_minute} req/min)"
