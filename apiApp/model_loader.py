"""
Environment-aware model loader for StellarMapWeb.

This module dynamically imports the correct model classes based on the environment:
- ENV in ['production', 'replit']: Use Cassandra models from models_cassandra.py
- ENV='development': Use SQL models from models.py

This prevents SQL queries from being sent to Cassandra, which causes syntax errors.
"""

from django.conf import settings

# Detect environment
ENV = settings.ENV if hasattr(settings, 'ENV') else 'development'
USE_CASSANDRA = (ENV in ['production', 'replit'])

# Import the correct models based on environment
if USE_CASSANDRA:
    # Production/Replit: Use Cassandra models
    from apiApp.models_cassandra import (
        StellarAccountSearchCache,
        StellarCreatorAccountLineage,
        ManagementCronHealth,
        StellarAccountStageExecution,
        # Status constants
        PENDING,
        PROCESSING,
        COMPLETE,
        BIGQUERY_COMPLETE,
        FAILED,
        INVALID,
        STUCK_THRESHOLD_MINUTES,
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
        # Status constants
        PENDING,
        PROCESSING,
        COMPLETE,
        BIGQUERY_COMPLETE,
        FAILED,
        INVALID,
        STUCK_THRESHOLD_MINUTES,
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
    'BigQueryPipelineConfig',
    'PENDING',
    'PROCESSING',
    'COMPLETE',
    'BIGQUERY_COMPLETE',
    'FAILED',
    'INVALID',
    'STUCK_THRESHOLD_MINUTES',
    'MAX_RETRY_ATTEMPTS',
    'TESTNET',
    'PUBLIC',
    'NETWORK_CHOICES',
    'USE_CASSANDRA',
    'ENV',
]
