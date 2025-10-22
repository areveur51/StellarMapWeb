"""
Local development models for SQLite when Cassandra is not available.
These models mirror the Cassandra models but use Django ORM for local development.
"""

from django.db import models
from django.conf import settings
import datetime
import uuid

# Status constants (same as in models.py)
PENDING = 'PENDING'
PROCESSING = 'PROCESSING'
COMPLETE = 'COMPLETE'
FAILED = 'FAILED'
INVALID = 'INVALID'
BIGQUERY_COMPLETE = 'BIGQUERY_COMPLETE'

STATUS_CHOICES = (
    (PENDING, 'Pending'),
    (PROCESSING, 'Processing'),
    (COMPLETE, 'Complete'),
    (BIGQUERY_COMPLETE, 'Complete'),
    (FAILED, 'Failed'),
    (INVALID, 'Invalid'),
)

TESTNET = 'testnet'
PUBLIC = 'public'
NETWORK_CHOICES = ((TESTNET, 'testnet'), (PUBLIC, 'public'))

STUCK_THRESHOLD_MINUTES = 5
STUCK_STATUSES = [PENDING, PROCESSING]
MAX_RETRY_ATTEMPTS = 3


class StellarAccountSearchCache(models.Model):
    """
    SQLite version of StellarAccountSearchCache for local development.
    Mirrors the Cassandra model structure.
    """
    stellar_account = models.CharField(max_length=56, primary_key=True)
    network_name = models.CharField(max_length=9)
    status = models.CharField(max_length=127, default=PENDING, choices=STATUS_CHOICES)
    cached_json = models.TextField()
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('stellar_account', 'network_name')
        db_table = 'apiApp_stellaraccountsearchcache'
        indexes = [
            models.Index(fields=['network_name', 'status']),
            models.Index(fields=['last_fetched_at']),
        ]

    def __str__(self):
        return f"{self.stellar_account} ({self.network_name}) - {self.status}"


class StellarCreatorAccountLineage(models.Model):
    """
    SQLite version of StellarCreatorAccountLineage for local development.
    Mirrors the Cassandra model structure.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    stellar_account = models.CharField(max_length=56)
    network_name = models.CharField(max_length=9)
    stellar_creator_account = models.CharField(max_length=56)
    stellar_account_created_at = models.DateTimeField(null=True, blank=True)
    home_domain = models.CharField(max_length=127, blank=True)
    xlm_balance = models.FloatField(default=0.0)
    horizon_accounts_json = models.TextField(blank=True)
    horizon_operations_json = models.TextField(blank=True)
    horizon_effects_json = models.TextField(blank=True)

    # BigQuery pipeline fields
    stellar_account_attributes_json = models.TextField(blank=True)
    stellar_account_assets_json = models.TextField(blank=True)
    child_accounts_json = models.TextField(blank=True)

    # Tags for categorizing accounts
    tags = models.CharField(max_length=255, blank=True)

    # High Value Account flag
    is_hva = models.BooleanField(default=False)

    status = models.CharField(max_length=127, choices=STATUS_CHOICES)
    retry_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'apiApp_stellarcreatoraccountlineage'
        indexes = [
            models.Index(fields=['stellar_account', 'network_name']),
            models.Index(fields=['stellar_creator_account']),
            models.Index(fields=['is_hva']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.stellar_account} -> {self.stellar_creator_account}"


class ManagementCronHealth(models.Model):
    """
    SQLite version of ManagementCronHealth for local development.
    Mirrors the Cassandra model structure.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = models.DateTimeField()
    cron_name = models.CharField(max_length=71)
    status = models.CharField(max_length=63, default='HEALTHY')
    reason = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'apiApp_managementcronhealth'
        indexes = [
            models.Index(fields=['cron_name', '-created_at']),
            models.Index(fields=['status']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Cron: {self.cron_name} | Status: {self.status}"


class StellarAccountStageExecution(models.Model):
    """
    SQLite version of StellarAccountStageExecution for local development.
    Mirrors the Cassandra model structure.
    """
    stellar_account = models.CharField(max_length=56)
    network_name = models.CharField(max_length=9)
    created_at = models.DateTimeField()
    stage_number = models.IntegerField()
    cron_name = models.CharField(max_length=127)
    status = models.CharField(max_length=63)
    execution_time_ms = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'apiApp_stellaraccountstageexecution'
        indexes = [
            models.Index(fields=['stellar_account', 'network_name', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['cron_name']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.stellar_account} ({self.network_name}) - Stage {self.stage_number}: {self.status}"

class HVAStandingChange(models.Model):
    """
    SQLite version of HVA Standing Change model for development.
    Event log tracking High Value Account leaderboard position changes.
    """
    stellar_account = models.CharField(max_length=56)
    change_time = models.DateTimeField()  # Manually set, no auto_now_add
    
    # Event metadata
    event_type = models.CharField(max_length=32)  # ENTERED, EXITED, RANK_UP, etc.
    
    # Before/After state
    old_rank = models.IntegerField(null=True, blank=True)
    new_rank = models.IntegerField(null=True, blank=True)
    old_balance = models.FloatField(default=0.0)
    new_balance = models.FloatField(default=0.0)
    
    # Additional context
    network_name = models.CharField(max_length=9)
    home_domain = models.CharField(max_length=127, blank=True, default='')
    xlm_threshold = models.FloatField(default=100000.0)  # Threshold used for this leaderboard
    
    # Calculated metrics
    rank_change = models.IntegerField(null=True, blank=True)
    balance_change_pct = models.FloatField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-change_time']
        indexes = [
            models.Index(fields=['stellar_account', '-change_time']),
            models.Index(fields=['event_type']),
        ]
    
    def __str__(self):
        return f"{self.stellar_account[:8]}... {self.event_type} at {self.created_at}"
