# apiApp/models.py
import datetime
import uuid
from django.conf import settings

# Check if Cassandra is available (production mode)
CASSANDRA_AVAILABLE = False
try:
    from cassandra.cqlengine import columns as cassandra_columns
    from django_cassandra_engine.models import DjangoCassandraModel
    CASSANDRA_AVAILABLE = True
except ImportError:
    # Cassandra not available, will use local SQLite models
    pass

# Conditionally import models based on Cassandra availability
if CASSANDRA_AVAILABLE and settings.ASTRA_DB_TOKEN:
    # Production mode: Use Cassandra models
    from .models_cassandra import *
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
    batch_size = django_models.IntegerField(default=100)  # Number of accounts to process per batch run

    # Data Freshness
    cache_ttl_hours = django_models.IntegerField(default=12)  # How long before data is considered stale

    # Metadata
    created_at = django_models.DateTimeField(auto_now_add=True)
    updated_at = django_models.DateTimeField(auto_now=True)
    updated_by = django_models.CharField(max_length=255, blank=True)  # Admin username who last updated
    notes = django_models.TextField(blank=True)  # Admin notes about configuration changes

    class Meta:
        verbose_name = "BigQuery Pipeline Configuration"
        verbose_name_plural = "BigQuery Pipeline Configuration"

    def __str__(self):
        return f"BigQuery Pipeline Config (Cost Limit: ${self.cost_limit_usd}, Mode: {self.pipeline_mode})"
