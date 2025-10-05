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


class UserInquirySearchHistory(BaseModel):
    """
    Model for user inquiry history.

    Prevents duplicates by primary key; status choices for security.
    """
    stellar_account = cassandra_columns.Text(primary_key=True, max_length=56)
    network_name = cassandra_columns.Text(primary_key=True, max_length=9)
    status = cassandra_columns.Text(max_length=63,
                                    default=PENDING)  # Secure default

    class Meta:
        get_pk_field = 'stellar_account'
        ordering = ['-created_at']  # Efficient ordering


class StellarCreatorAccountLineage(BaseModel):
    """
    Model for account lineage data.

    Stores API hrefs; status for processing tracking.
    """
    stellar_creator_account = cassandra_columns.Text(max_length=56)
    stellar_account = cassandra_columns.Text(primary_key=True, max_length=56)
    stellar_account_created_at = cassandra_columns.DateTime()
    network_name = cassandra_columns.Text(primary_key=True, max_length=9)
    home_domain = cassandra_columns.Text(max_length=127)
    xlm_balance = cassandra_columns.Float(default=0.0)
    horizon_accounts_doc_api_href = cassandra_columns.Text()
    status = cassandra_columns.Text(max_length=127)
    
    class Meta:
        get_pk_field = 'stellar_account'


class ManagementCronHealth(BaseModel):
    """
    Model for cron health monitoring.

    Clustering for efficient latest fetch.
    """
    cron_name = cassandra_columns.Text(primary_key=True, max_length=71)
    status = cassandra_columns.Text(max_length=63,
                                    default='HEALTHY')  # Secure default
    reason = cassandra_columns.Text()
    created_at = cassandra_columns.DateTime(primary_key=True,
                                            clustering_order="DESC")

    class Meta:
        get_pk_field = 'cron_name'
        db_table = 'management_cron_health'

    def __str__(self):
        """Admin display string."""
        return f"Cron: {self.cron_name} | Status: {self.status}"
