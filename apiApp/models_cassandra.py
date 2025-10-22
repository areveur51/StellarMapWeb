"""
Cassandra models for production use.
These are the original Cassandra models from models.py.
"""

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

    # Tags for categorizing accounts (e.g., HVA for High Value Account)
    tags = cassandra_columns.Text(max_length=255)

    # High Value Account flag for efficient querying (configurable threshold, default >=100K XLM)
    is_hva = cassandra_columns.Boolean(default=False)

    # Dual-pipeline tracking fields
    # IMPORTANT: These fields are temporarily commented out until cassandra_migration_dual_pipeline.cql is run
    # The column does not exist in production Cassandra schema yet, causing ALL queries to fail
    # Uncomment these fields AFTER running the Cassandra migration script
    # pipeline_source = cassandra_columns.Text(max_length=64, default='')  # BIGQUERY, API, BIGQUERY_WITH_API_FALLBACK
    # last_pipeline_attempt = cassandra_columns.DateTime(default=None)  # Last time either pipeline attempted processing
    # processing_started_at = cassandra_columns.DateTime(default=None)  # When current processing started

    status = cassandra_columns.Text(max_length=127)
    retry_count = cassandra_columns.Integer(default=0)
    last_error = cassandra_columns.Text()
    created_at = cassandra_columns.DateTime()
    updated_at = cassandra_columns.DateTime()

    def save(self, *args, **kwargs):
        """Auto-set timestamps, HVA tag, and HVA flag on save."""
        if not self.created_at:
            self.created_at = datetime.datetime.utcnow()
        self.updated_at = datetime.datetime.utcnow()

        # Get configurable HVA threshold (default: 100K XLM)
        try:
            from apiApp.models import BigQueryPipelineConfig
            config = BigQueryPipelineConfig.objects.filter(config_id='default').first()
            hva_threshold = config.hva_threshold_xlm if config else 100000.0
        except Exception:
            hva_threshold = 100000.0  # Fallback default

        # Auto-tag High Value Accounts (HVA) based on configurable threshold
        if self.xlm_balance and self.xlm_balance >= hva_threshold:
            # Set HVA flag for efficient querying
            self.is_hva = True

            # Add HVA tag if not present (using exact match to avoid false positives)
            if self.tags:
                tags_list = [tag.strip() for tag in self.tags.split(',')]
                if 'HVA' not in tags_list:
                    tags_list.append('HVA')
                    self.tags = ','.join(tags_list)
            else:
                self.tags = 'HVA'
        else:
            # Clear HVA flag and remove HVA tag if balance drops below threshold
            self.is_hva = False

            if self.tags:
                tags_list = [tag.strip() for tag in self.tags.split(',') if tag.strip() != 'HVA']
                self.tags = ','.join(tags_list) if tags_list else ''

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
    __table_name__ = 'management_cron_health'

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

class HVAStandingChange(DjangoCassandraModel):
    """
    Event log tracking High Value Account (HVA) leaderboard position changes.
    Records events ONLY when standings change (rank up/down, enter/exit top 1000).
    
    PRIMARY KEY ((stellar_account), change_time)
    - Partition by stellar_account for efficient per-account history queries
    - Cluster by change_time DESC (most recent changes first)
    
    Event Types:
    - ENTERED: Account entered top 1000 HVA leaderboard
    - EXITED: Account dropped below top 1000 or balance fell below 1M XLM
    - RANK_UP: Account improved position in leaderboard
    - RANK_DOWN: Account dropped position in leaderboard
    - BALANCE_INCREASE: Significant balance increase (>5%) without rank change
    - BALANCE_DECREASE: Significant balance decrease (>5%) without rank change
    
    Storage Efficiency: Only stores ~50 events/day vs 24,000 rows/day with snapshots.
    """
    __keyspace__ = settings.CASSANDRA_KEYSPACE
    __table_name__ = 'hva_standing_changes'

    stellar_account = cassandra_columns.Text(partition_key=True, max_length=56)
    change_time = cassandra_columns.TimeUUID(primary_key=True, clustering_order="DESC")
    
    # Event metadata
    event_type = cassandra_columns.Text(max_length=32)  # ENTERED, EXITED, RANK_UP, RANK_DOWN, etc.
    
    # Before/After state
    old_rank = cassandra_columns.Integer()  # null if ENTERED
    new_rank = cassandra_columns.Integer()  # null if EXITED
    old_balance = cassandra_columns.Float()
    new_balance = cassandra_columns.Float()
    
    # Additional context
    network_name = cassandra_columns.Text(max_length=9)
    home_domain = cassandra_columns.Text(max_length=127)
    xlm_threshold = cassandra_columns.Float(default=100000.0)  # Threshold used for this leaderboard
    
    # Calculated metrics
    rank_change = cassandra_columns.Integer()  # Positive = moved up, Negative = moved down
    balance_change_pct = cassandra_columns.Float()  # Percentage change
    
    created_at = cassandra_columns.DateTime()

    def save(self, *args, **kwargs):
        """Auto-set timestamps and calculate derived fields."""
        from apiApp.helpers.sm_validator import StellarMapValidatorHelpers
        from django.utils import timezone
        
        # Validate stellar_account
        if not StellarMapValidatorHelpers.validate_stellar_account_address(self.stellar_account):
            raise ValueError(f"Invalid stellar_account: '{self.stellar_account}'")
        
        # Validate network_name
        if self.network_name not in ['public', 'testnet']:
            raise ValueError(f"Invalid network_name: '{self.network_name}'")
        
        # Calculate rank_change
        if self.old_rank and self.new_rank:
            self.rank_change = self.old_rank - self.new_rank  # Positive = moved up
        
        # Calculate balance_change_pct (allow zero balances for EXITED events)
        if self.old_balance is not None and self.new_balance is not None and self.old_balance > 0:
            self.balance_change_pct = ((self.new_balance - self.old_balance) / self.old_balance) * 100
        elif self.old_balance is not None and self.new_balance is not None and self.old_balance == 0 and self.new_balance > 0:
            self.balance_change_pct = 100.0  # Started from zero
        
        if not self.created_at:
            self.created_at = timezone.now()  # Use timezone-aware datetime
        
        return super().save(*args, **kwargs)

    class Meta:
        get_pk_field = 'stellar_account'
    
    def __str__(self):
        """String representation for debugging."""
        return f"{self.stellar_account[:8]}... {self.event_type} at {self.created_at}"
