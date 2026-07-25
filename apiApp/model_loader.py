"""
Environment-aware model loader for StellarMapWeb.

This module dynamically imports the correct model classes based on the environment:
- ENV in ['production', 'replit']: Use Cassandra models from models_cassandra.py
- CASSANDRA_READ_ONLY=1 + token (lab): same Cassandra models, writes blocked in router
- else ENV='development': Use SQL models from models_local.py

This prevents SQL queries from being sent to Cassandra, which causes syntax errors.
"""

from django.conf import settings

# Detect environment / lab RO mode (settings computes USE_CASSANDRA)
ENV = settings.ENV if hasattr(settings, 'ENV') else 'development'
USE_CASSANDRA = bool(getattr(settings, 'USE_CASSANDRA', ENV in ['production', 'replit']))
CASSANDRA_READ_ONLY = bool(getattr(settings, 'CASSANDRA_READ_ONLY', False))

# Import the correct models based on environment
if USE_CASSANDRA:
    # Production/Replit: Use Cassandra models
    from apiApp.models_cassandra import (
        StellarAccountSearchCache,
        StellarCreatorAccountLineage,
        ManagementCronHealth,
        StellarAccountStageExecution,
        HVAStandingChange,
        # Status constants
        PENDING,
        PROCESSING,
        COMPLETE,
        BIGQUERY_COMPLETE,
        FAILED,
        INVALID,
        STUCK_THRESHOLD_MINUTES,
        STUCK_STATUSES,
        MAX_RETRY_ATTEMPTS,
        # Network constants
        TESTNET,
        PUBLIC,
        NETWORK_CHOICES,
    )
else:
    # Development: Use SQL models from models_local.py
    from apiApp.models_local import (
        StellarAccountSearchCache,
        StellarCreatorAccountLineage,
        ManagementCronHealth,
        StellarAccountStageExecution,
        HVAStandingChange,
        # Status constants
        PENDING,
        PROCESSING,
        COMPLETE,
        BIGQUERY_COMPLETE,
        FAILED,
        INVALID,
        STUCK_THRESHOLD_MINUTES,
        STUCK_STATUSES,
        MAX_RETRY_ATTEMPTS,
        # Network constants
        TESTNET,
        PUBLIC,
        NETWORK_CHOICES,
    )

# BigQueryPipelineConfig always uses SQLite (not affected by database routing)
from apiApp.models import BigQueryPipelineConfig

# Export all for easy import
__all__ = [
    'StellarAccountSearchCache',
    'StellarCreatorAccountLineage',
    'ManagementCronHealth',
    'StellarAccountStageExecution',
    'HVAStandingChange',
    'BigQueryPipelineConfig',
    'PENDING',
    'PROCESSING',
    'COMPLETE',
    'BIGQUERY_COMPLETE',
    'FAILED',
    'INVALID',
    'STUCK_THRESHOLD_MINUTES',
    'STUCK_STATUSES',
    'MAX_RETRY_ATTEMPTS',
    'TESTNET',
    'PUBLIC',
    'NETWORK_CHOICES',
    'USE_CASSANDRA',
    'CASSANDRA_READ_ONLY',
    'ENV',
]
