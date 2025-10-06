# Overview

StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API and Stellar Expert, stores this data in Astra DB (Cassandra), and then renders it as interactive D3.js radial tree diagrams. The project aims to provide users with a clear, interactive "family tree" view of how Stellar accounts are created and interconnected, offering insights into the network's structure and activity.

# Recent Changes

## October 2025 - Data Corruption Bug Fix
- **Fixed critical bug in StellarAccountSearchCacheManager**: The `update_inquiry()` method was incorrectly querying by non-existent `id` field instead of composite partition key (stellar_account, network_name)
- **Root Cause**: When cron job called `inquiry_manager.update_inquiry(id=inq_queryset.id, ...)`, it caused Cassandra ORM to create corrupted records with single-character values (e.g., stellar_account='G', network_name='D')
- **Solution**: 
  - Updated `StellarAccountSearchCacheManager.update_inquiry()` to accept `stellar_account` and `network_name` parameters
  - Fixed `cron_make_parent_account_lineage.py` to pass correct partition key fields instead of non-existent `id`
- **Impact**: Eliminated data corruption; all cache entries now created with full, valid Stellar account addresses and network names
- **Files Updated**: apiApp/managers.py, apiApp/management/commands/cron_make_parent_account_lineage.py

## October 2025 - Cassandra Table Schema Fix
- **Fixed table name mismatch**: Updated models to use `__table_name__` attribute to match production table names.
  - `StellarAccountSearchCache`: Now uses `stellar_account_search_cache` table with PRIMARY KEY ((stellar_account, network_name))
  - `StellarCreatorAccountLineage`: Now uses `stellar_creator_account_lineage` table with PRIMARY KEY ((id), stellar_account, network_name)
  - Dropped old `user_inquiry_search_history` table
- **Root Cause**: django-cassandra-engine ignores Meta.db_table setting, requires explicit `__table_name__` attribute
- **Impact**: Search functionality and Pending Accounts UI now work correctly with production database schema
- **Files Updated**: apiApp/models.py, webApp/views.py

## October 2025 - Automated Cron Jobs & Pending Accounts UI
- **Automated Cron Execution**: Implemented background cron worker (`run_cron_jobs.py`) that runs automatically when app starts.
  - Runs all 9 cron jobs on schedule (every 5-10 minutes with staggered offsets)
  - Replaces manual cron execution with automatic background processing
  - Logs all job execution status to console
- **Cron Job Prioritization**: Updated `cron_make_parent_account_lineage.py` to prioritize new user searches:
  - PENDING_MAKE_PARENT_LINEAGE entries processed first (new searches)
  - RE_INQUIRY entries processed second (12-hour cache refreshes)
  - Ensures new user searches get fastest response
- **New "Pending Accounts" UI Tab**: Added visibility into cron job activity
  - Displays all PENDING/IN_PROGRESS/RE_INQUIRY accounts in JSON format
  - Real-time Vue.js watcher for automatic updates
  - Located between "Account Lineage" and "TOML" tabs in search interface

## October 2025 - Critical Field Name Fix
- **Fixed Cassandra schema mismatch**: Updated all code references from `network` to `network_name` to match production database column name.
- **Impact**: This was preventing search functionality from creating PENDING cache entries in the database.
- **Files Updated**: 
  - Core: apiApp/models.py, apiApp/helpers/sm_cache.py, webApp/views.py
  - Tests: All test files updated for consistency (8 files total)
- **Result**: Search now correctly creates PENDING entries that trigger the cron workflow for data collection.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Framework and Structure
- **Django 4.2.7** with a multi-app architecture: `apiApp` (API/data management), `webApp` (user interface), and `radialTidyTreeApp` (visualization components).

## Database Architecture
- **Primary Storage**: Astra DB (DataStax Cassandra) for production, utilizing `django-cassandra-engine`.
- **Local Development**: SQLite for local environments.
- **Database Routing**: Custom `DatabaseAppsRouter` for directing apps to appropriate databases.
- **ORM**: Combines Django ORM with direct Cassandra integration.
- **Schema Design**: Cassandra models are designed with explicit composite primary keys and clustering keys for efficient querying, including timestamp management (`created_at`, `updated_at`).
- **Caching**: Implemented a 12-hour caching strategy for Stellar address searches using `StellarAccountSearchCache` to minimize API calls and improve performance.

## Data Collection Pipeline
- **Asynchronous Processing**: Extensive use of async/await for API interactions.
- **Scheduled Tasks**: Django management commands with cron scheduling for automated data collection.
- **API Integration**: Uses Horizon API for core Stellar data and Stellar Expert for enhanced account information.
- **Retry Logic**: `Tenacity` library ensures robust API calls.
- **Rate Limiting**: Staggered cron jobs prevent API rate limit violations.
- **Workflow Management**: Comprehensive PlantUML-based cron workflow with 17 status constants (`PENDING`, `IN_PROGRESS`, `DONE` states) for tracking data collection and processing.

## Frontend Architecture
- **Templating**: Django templates enhanced with Vue.js components for interactivity.
- **Visualization**: D3.js is used for rendering radial tree diagrams.
- **Responsive Design**: Bootstrap-based interface.
- **Component System**: Modular Vue.js components for reusable UI elements, including dedicated tabs for Search Cache and Account Lineage data display.

## Security and Monitoring
- **Environment Configuration**: `Decouple` library for secure environment variable management (e.g., `CASSANDRA_KEYSPACE`).
- **Error Tracking**: Sentry integration for comprehensive error monitoring.
- **Input Validation**: Stellar SDK for cryptographic address validation.
- **HTTPS Enforcement**: Production settings enforce SSL/TLS.

## Cron Job Architecture
- **Health Monitoring**: Dedicated system monitors cron job status.
- **Sequential Processing**: Jobs are staggered to prevent resource conflicts.
- **Status Tracking**: Each job tracks its progress through defined status states via `ManagementCronHealth` model.

# External Dependencies

## Blockchain APIs
- **Horizon API**: Official Stellar network API.
- **Stellar Expert**: Third-party service for Stellar network insights.

## Database Services
- **Astra DB**: DataStax managed Cassandra service.
- **Cassandra**: Distributed NoSQL database.

## Monitoring and Development
- **Sentry**: Error tracking and performance monitoring.
- **Replit**: Cloud development and deployment platform.

## Key Libraries
- **stellar-sdk**: Python SDK for Stellar blockchain.
- **django-cassandra-engine**: Django integration for Cassandra.
- **tenacity**: Retry library.
- **pandas**: Data manipulation.
- **requests**: HTTP library.
- **aiohttp**: Asynchronous HTTP client.

## Frontend Dependencies
- **D3.js**: Data visualization library.
- **Vue.js**: JavaScript framework.
- **Bootstrap**: CSS framework.
- **jQuery**: JavaScript library.