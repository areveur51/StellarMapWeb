# apiApp/models.py
import datetime
import uuid
from cassandra.cqlengine import columns as cassandra_columns
from django_cassandra_engine.models import DjangoCassandraModel
from django.conf import settings

# Simplified Status Constants (5 total)
PENDING = 'PENDING'
PROCESSING = 'PROCESSING'
COMPLETE = 'COMPLETE'
FAILED = 'FAILED'
INVALID = 'INVALID'

# BigQuery pipeline status (for backwards compatibility)
BIGQUERY_COMPLETE = 'BIGQUERY_COMPLETE'

# Status choices
STATUS_CHOICES = (
    (PENDING, 'Pending'),
    (PROCESSING, 'Processing'),
    (COMPLETE, 'Complete'),
    (BIGQUERY_COMPLETE, 'Complete'),
    (FAILED, 'Failed'),
    (INVALID, 'Invalid'),
)

# Stuck record detection: 5 minutes for PENDING or PROCESSING
STUCK_THRESHOLD_MINUTES = 5
STUCK_STATUSES = [PENDING, PROCESSING]

# Maximum retry attempts before marking as FAILED
MAX_RETRY_ATTEMPTS = 3

TESTNET = 'testnet'
PUBLIC = 'public'
NETWORK_CHOICES = ((TESTNET, 'testnet'), (PUBLIC, 'public'))


class BaseModel(DjangoCassandraModel):
    """
    Abstract base model with common fields/timestamps.
    """
    __keyspace__ = settings.CASSANDRA_KEYSPACE
    id = cassandra_columns.UUID(primary_key=True, default=uuid.uuid4)
    created_at = cassandra_columns.DateTime()
    updated_at = cassandra_columns.DateTime()

    def save(self, *args, **kwargs):
        """Auto-set timestamps on save."""
        if not self.created_at:
            self.created_at = datetime.datetime.utcnow()
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    class Meta:
        get_pk_field = "id"
        abstract = True


class BigQueryPipelineConfig(DjangoCassandraModel):
    """
    Configuration settings for BigQuery pipeline behavior.
    
    Singleton model - only one configuration record should exist.
    Controls cost limits, pipeline modes, age restrictions, and API fallback behavior.
    """
    __keyspace__ = settings.CASSANDRA_KEYSPACE
    __table_name__ = 'bigquery_pipeline_config'
    
    # Singleton primary key
    config_id = cassandra_columns.Text(primary_key=True, default='default')
    
    # BigQuery Cost Controls
    bigquery_enabled = cassandra_columns.Boolean(default=True)
    cost_limit_usd = cassandra_columns.Float(default=0.71)  # Maximum cost per query in USD
    size_limit_mb = cassandra_columns.Float(default=148900.0)  # Maximum query size in MB (~145GB)
    
    # Pipeline Strategy
    pipeline_mode = cassandra_columns.Text(default='BIGQUERY_WITH_API_FALLBACK')
    # Options: 
    # - 'BIGQUERY_ONLY': Use only BigQuery, fail if blocked by cost controls
    # - 'API_ONLY': Use only Horizon/Stellar Expert APIs (no BigQuery)
    # - 'BIGQUERY_WITH_API_FALLBACK': Try BigQuery first, fall back to APIs if blocked (RECOMMENDED)
    
    # Age Restrictions (in days)
    instant_query_max_age_days = cassandra_columns.Integer(default=365)  # 1 year
    # Accounts older than this use existing data or queue for batch processing
    
    # API Fallback Settings
    api_fallback_enabled = cassandra_columns.Boolean(default=True)
    horizon_max_operations = cassandra_columns.Integer(default=200)  # Max operations to fetch for creator discovery
    horizon_child_max_pages = cassandra_columns.Integer(default=5)  # Max pages for child account discovery (200 ops/page)
    
    # Child Account Collection
    bigquery_max_children = cassandra_columns.Integer(default=100000)  # Max child accounts to discover via BigQuery
    bigquery_child_page_size = cassandra_columns.Integer(default=10000)  # Pagination size for child queries
    
    # Batch Processing
    batch_processing_enabled = cassandra_columns.Boolean(default=True)
    batch_size = cassandra_columns.Integer(default=100)  # Number of accounts to process per batch run
    
    # Data Freshness
    cache_ttl_hours = cassandra_columns.Integer(default=12)  # How long before data is considered stale
    
    # Metadata
    created_at = cassandra_columns.DateTime()
    updated_at = cassandra_columns.DateTime()
    updated_by = cassandra_columns.Text(max_length=255)  # Admin username who last updated
    notes = cassandra_columns.Text()  # Admin notes about configuration changes
    
    def save(self, *args, **kwargs):
        """Auto-set timestamps on save."""
        if not self.created_at:
            self.created_at = datetime.datetime.utcnow()
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)
    
    class Meta:
        get_pk_field = 'config_id'

    def __str__(self):
        return f"BigQuery Pipeline Config (Cost Limit: ${self.cost_limit_usd}, Mode: {self.pipeline_mode})"


class StellarAccountSearchCache(DjangoCassandraModel):
    """
    Model for Stellar account search caching with 12-hour freshness.

    PRIMARY KEY ((stellar_account, network_name)) for efficient queries by account.
    Composite partition key prevents duplicates and enables fast lookups.
    
    NOTE: Does NOT inherit from BaseModel to match existing table schema.
    """
    __keyspace__ = settings.CASSANDRA_KEYSPACE
    __table_name__ = 'stellar_account_search_cache'
    
    stellar_account = cassandra_columns.Text(partition_key=True, max_length=56)
    network_name = cassandra_columns.Text(partition_key=True, max_length=9)
    status = cassandra_columns.Text(max_length=127, default=PENDING)
    cached_json = cassandra_columns.Text()  # Stores tree_data JSON for quick retrieval
    last_fetched_at = cassandra_columns.DateTime()  # Tracks cache freshness
    retry_count = cassandra_columns.Integer(default=0)  # Number of recovery attempts
    last_error = cassandra_columns.Text()  # Last error message for troubleshooting
    created_at = cassandra_columns.DateTime()
    updated_at = cassandra_columns.DateTime()

    def save(self, *args, **kwargs):
        """Auto-set timestamps on save with full validation to prevent data corruption."""
        from apiApp.helpers.sm_validator import StellarMapValidatorHelpers
        
        # Validate stellar_account format (56 chars, G-prefix, crypto check)
        if not StellarMapValidatorHelpers.validate_stellar_account_address(self.stellar_account):
            raise ValueError(f"Invalid stellar_account: '{self.stellar_account}' (must be 56 characters starting with G)")
        
        # Validate network_name
        if self.network_name not in ['public', 'testnet']:
            raise ValueError(f"Invalid network_name: '{self.network_name}' (must be 'public' or 'testnet')")
        
        if not self.created_at:
            self.created_at = datetime.datetime.utcnow()
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    class Meta:
        get_pk_field = 'stellar_account'


class StellarCreatorAccountLineage(DjangoCassandraModel):
    """
    Model for account lineage data.

    PRIMARY KEY ((id), stellar_account, network_name) matches production table schema.
    
    NOTE: Does NOT inherit from BaseModel to match existing table schema.
    """
    __keyspace__ = settings.CASSANDRA_KEYSPACE
    __table_name__ = 'stellar_creator_account_lineage'
    
    id = cassandra_columns.UUID(primary_key=True, default=uuid.uuid4)
    stellar_account = cassandra_columns.Text(primary_key=True, max_length=56)
    network_name = cassandra_columns.Text(primary_key=True, max_length=9)
    stellar_creator_account = cassandra_columns.Text(max_length=56)
    stellar_account_created_at = cassandra_columns.DateTime()
    home_domain = cassandra_columns.Text(max_length=127)
    xlm_balance = cassandra_columns.Float(default=0.0)
    horizon_accounts_json = cassandra_columns.Text()
    horizon_operations_json = cassandra_columns.Text()
    horizon_effects_json = cassandra_columns.Text()
    
    # BigQuery pipeline fields
    stellar_account_attributes_json = cassandra_columns.Text()
    stellar_account_assets_json = cassandra_columns.Text()
    child_accounts_json = cassandra_columns.Text()
    
    status = cassandra_columns.Text(max_length=127)
    retry_count = cassandra_columns.Integer(default=0)
    last_error = cassandra_columns.Text()
    created_at = cassandra_columns.DateTime()
    updated_at = cassandra_columns.DateTime()
    
    def save(self, *args, **kwargs):
        """Auto-set timestamps on save."""
        if not self.created_at:
            self.created_at = datetime.datetime.utcnow()
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)
    
    class Meta:
        get_pk_field = 'id'


class ManagementCronHealth(DjangoCassandraModel):
    """
    Model for cron health monitoring.

    PRIMARY KEY ((id), created_at, cron_name) matches production table schema.
    
    NOTE: Does NOT inherit from BaseModel to match existing table schema.
    """
    __keyspace__ = settings.CASSANDRA_KEYSPACE
    
    id = cassandra_columns.UUID(primary_key=True, default=uuid.uuid4)
    created_at = cassandra_columns.DateTime(primary_key=True, clustering_order="DESC")
    cron_name = cassandra_columns.Text(primary_key=True, max_length=71)
    status = cassandra_columns.Text(max_length=63, default='HEALTHY')  # Secure default
    reason = cassandra_columns.Text()
    updated_at = cassandra_columns.DateTime()

    def save(self, *args, **kwargs):
        """Auto-set timestamps on save."""
        if not self.created_at:
            self.created_at = datetime.datetime.utcnow()
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    class Meta:
        get_pk_field = 'id'
        db_table = 'management_cron_health'

    def __str__(self):
        """Admin display string."""
        return f"Cron: {self.cron_name} | Status: {self.status}"


class StellarAccountStageExecution(DjangoCassandraModel):
    """
    Model for tracking stage execution progress per address.
    
    Tracks each cron job execution for a specific stellar account,
    enabling real-time pipeline monitoring in the Stages tab.
    
    PRIMARY KEY ((stellar_account, network_name), created_at, stage_number)
    - Partition key: (stellar_account, network_name) for efficient per-address queries
    - Clustering key: created_at DESC for chronological ordering
    - Clustering key: stage_number for stage ordering
    
    NOTE: Does NOT inherit from BaseModel to match Cassandra patterns.
    """
    __keyspace__ = settings.CASSANDRA_KEYSPACE
    __table_name__ = 'stellar_account_stage_execution'
    
    stellar_account = cassandra_columns.Text(partition_key=True, max_length=56)
    network_name = cassandra_columns.Text(partition_key=True, max_length=9)
    created_at = cassandra_columns.DateTime(primary_key=True, clustering_order="DESC")
    stage_number = cassandra_columns.Integer(primary_key=True)
    cron_name = cassandra_columns.Text(max_length=127)
    status = cassandra_columns.Text(max_length=63)
    execution_time_ms = cassandra_columns.Integer(default=0)
    error_message = cassandra_columns.Text()
    updated_at = cassandra_columns.DateTime()
    
    def save(self, *args, **kwargs):
        """Auto-set timestamps on save with validation."""
        from apiApp.helpers.sm_validator import StellarMapValidatorHelpers
        
        # Validate stellar_account format
        if not StellarMapValidatorHelpers.validate_stellar_account_address(self.stellar_account):
            raise ValueError(f"Invalid stellar_account: '{self.stellar_account}'")
        
        # Validate network_name
        if self.network_name not in ['public', 'testnet']:
            raise ValueError(f"Invalid network_name: '{self.network_name}'")
        
        if not self.created_at:
            self.created_at = datetime.datetime.utcnow()
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)
    
    class Meta:
        get_pk_field = 'stellar_account'
