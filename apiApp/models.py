# apiApp/models.py
import datetime
import uuid
from cassandra.cqlengine import columns as cassandra_columns
from django_cassandra_engine.models import DjangoCassandraModel
from django.conf import settings

# Constants for choices (secure defaults)
PENDING = 'pending'
IN_PROGRESS = 'in_progress'
COMPLETED = 'completed'
STATUS_CHOICES = ((PENDING, 'Pending'), (IN_PROGRESS, 'In Progress'),
                  (COMPLETED, 'Completed'))

# Cron workflow status constants (based on PlantUML workflow)
PENDING_HORIZON_API_DATASETS = 'PENDING_HORIZON_API_DATASETS'
IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS = 'IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS'
DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS = 'DONE_COLLECTING_HORIZON_API_DATASETS_ACCOUNTS'
IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_OPERATIONS = 'IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_OPERATIONS'
DONE_COLLECTING_HORIZON_API_DATASETS_OPERATIONS = 'DONE_COLLECTING_HORIZON_API_DATASETS_OPERATIONS'
IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_EFFECTS = 'IN_PROGRESS_COLLECTING_HORIZON_API_DATASETS_EFFECTS'
DONE_HORIZON_API_DATASETS = 'DONE_HORIZON_API_DATASETS'
IN_PROGRESS_UPDATING_FROM_RAW_DATA = 'IN_PROGRESS_UPDATING_FROM_RAW_DATA'
DONE_UPDATING_FROM_RAW_DATA = 'DONE_UPDATING_FROM_RAW_DATA'
IN_PROGRESS_UPDATING_FROM_OPERATIONS_RAW_DATA = 'IN_PROGRESS_UPDATING_FROM_OPERATIONS_RAW_DATA'
DONE_UPDATING_FROM_OPERATIONS_RAW_DATA = 'DONE_UPDATING_FROM_OPERATIONS_RAW_DATA'
IN_PROGRESS_MAKE_GRANDPARENT_LINEAGE = 'IN_PROGRESS_MAKE_GRANDPARENT_LINEAGE'
DONE_GRANDPARENT_LINEAGE = 'DONE_GRANDPARENT_LINEAGE'
PENDING_MAKE_PARENT_LINEAGE = 'PENDING_MAKE_PARENT_LINEAGE'
IN_PROGRESS_MAKE_PARENT_LINEAGE = 'IN_PROGRESS_MAKE_PARENT_LINEAGE'
DONE_MAKE_PARENT_LINEAGE = 'DONE_MAKE_PARENT_LINEAGE'
RE_INQUIRY = 'RE_INQUIRY'

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
    status = cassandra_columns.Text(max_length=127,
                                    default=PENDING_HORIZON_API_DATASETS)  # Workflow status
    cached_json = cassandra_columns.Text()  # Stores tree_data JSON for quick retrieval
    last_fetched_at = cassandra_columns.DateTime()  # Tracks cache freshness
    created_at = cassandra_columns.DateTime()
    updated_at = cassandra_columns.DateTime()

    def save(self, *args, **kwargs):
        """Auto-set timestamps on save with validation to prevent data corruption."""
        # Validate data before saving to prevent corruption
        if len(self.stellar_account) < 50:
            raise ValueError(f"Invalid stellar_account: '{self.stellar_account}' (must be 56 chars, got {len(self.stellar_account)})")
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
    horizon_accounts_doc_api_href = cassandra_columns.Text()
    status = cassandra_columns.Text(max_length=127)
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
