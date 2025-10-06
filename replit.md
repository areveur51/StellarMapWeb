# Overview

StellarMapWeb is a Django application for visualizing Stellar blockchain lineage data using D3.js radial tree diagrams. The system tracks account creation relationships across the Stellar network, collecting data from Horizon API and Stellar Expert, then storing it in Astra DB (Cassandra) for visualization. Users can input Stellar addresses to generate interactive family tree-style visualizations showing how accounts were created and their relationships.

# Recent Changes

## October 6, 2025 - Request Status and Account Lineage Tabs Implementation
- **Request Status Tab**: Added new b-tab for visibility into UserInquirySearchHistory entries
  - Displays database entry details in JSON format with syntax highlighting
  - Shows key fields: stellar_account, network, status, last_fetched_at, created_at, updated_at, has_cached_data, cache_status
  - Context data prepared in webApp/views.py with comprehensive status information
  - Positioned between "JSON" and "TOML" tabs for easy access to request state
  - Enables users to monitor cache freshness and workflow status for searched accounts
- **Account Lineage Tab**: Added new b-tab for displaying StellarCreatorAccountLineage records
  - Recursively follows creator account chain up the lineage hierarchy
  - Displays all lineage records matching searched stellar account and network
  - Shows comprehensive record data: stellar_account, stellar_creator_account, network_name, xlm_balance, home_domain, status timestamps
  - Positioned between "Request Status" and "TOML" tabs
  - Provides complete visibility into account creation relationships
- Implemented Vue.js integration for both tabs:
  - Data properties for JSON data binding (`request_status_data`, `account_lineage_data`)
  - Syntax-highlighted display using HighlightJS
  - Update methods for JSON formatting (`updateRequestStatusDisplay()`, `updateAccountLineageDisplay()`)
  - Watchers to automatically update display when data changes

## October 5, 2025 (Late Evening) - 12-Hour Database Caching System
- Implemented efficient 12-hour caching strategy for Stellar address searches to minimize API calls
- Enhanced UserInquirySearchHistory model with new fields:
  - `cached_json`: Stores complete tree_data JSON for instant retrieval
  - `last_fetched_at`: Tracks cache freshness for 12-hour window validation
  - Updated `status` field to use workflow status constants (PENDING_HORIZON_API_DATASETS, etc.)
- Created StellarMapCacheHelpers class (apiApp/helpers/sm_cache.py) with methods:
  - `check_cache_freshness()`: Validates if cached data is < 12 hours old
  - `get_cached_data()`: Retrieves and parses cached JSON
  - `update_cache()`: Stores fresh tree data after cron job completion
  - `create_pending_entry()`: Marks stale/missing entries as PENDING to trigger cron processing
- Updated search_view (webApp/views.py) with intelligent cache flow:
  - Checks Cassandra DB for fresh cached data first (< 12 hours old)
  - Returns cached JSON immediately if available (significant performance boost)
  - Creates PENDING entry for cron jobs if data is stale/missing
  - Attempts immediate refresh for better UX, falls back to cached data on error
- Enhanced cron_make_parent_account_lineage to update cache after completing lineage workflow
- Added UX indicators in search.html template:
  - Green badge "Cached Data (Fresh)" for data served from cache
  - Yellow spinner "Refreshing Data..." for stale data being updated
- Synced Cassandra database schema to support new caching fields
- Architect-reviewed and approved: No race conditions or data integrity issues observed
- Production-ready implementation improves performance and reduces API load significantly

## October 5, 2025 (Evening) - PlantUML Workflow Implementation
- Implemented complete PlantUML-based cron workflow with 17 status constants in models.py
- Added all workflow states: PENDING_HORIZON_API_DATASETS → IN_PROGRESS states → DONE states
- Implemented missing async methods in sm_creatoraccountlineage.py:
  - `async_update_from_operations_raw_data`: Extracts creator account from operations data
  - `async_make_grandparent_account`: Creates lineage records for grandparent accounts
- Updated all 5 cron management commands to use centralized status constants
- Implemented `_fetch_and_store_effects` method in cron_collect_account_horizon_data.py
- Enhanced sm_cron.py helper to accept cron_name parameter and check cron health via database
- Eliminated all hardcoded status strings across codebase, using imported constants from models.py
- Verified workflow properly advances through complete PlantUML state machine:
  1. Horizon data collection: PENDING → collect accounts → operations → effects → DONE_HORIZON_API_DATASETS
  2. Attribute extraction: DONE_HORIZON_API_DATASETS → DONE_UPDATING_FROM_RAW_DATA
  3. Creator extraction: DONE_UPDATING_FROM_RAW_DATA → DONE_UPDATING_FROM_OPERATIONS_RAW_DATA
  4. Grandparent creation: DONE_UPDATING_FROM_OPERATIONS_RAW_DATA → DONE_GRANDPARENT_LINEAGE
  5. Parent lineage: PENDING_MAKE_PARENT_LINEAGE/RE_INQUIRY → DONE_MAKE_PARENT_LINEAGE
- Production-ready implementation confirmed by architect review

## October 5, 2025 (Morning)
- Refactored environment variable naming for technical accuracy
- Renamed `CASSANDRA_DB_NAME` to `CASSANDRA_KEYSPACE` across all codebase
- Updated models.py, sm_conn.py, and settings_base.py to use CASSANDRA_KEYSPACE
- Verified Astra DB connection working with new secret naming convention
- Database tables (stellar_creator_account_lineage, user_inquiry_search_history, management_cron_health) confirmed accessible

## September 21, 2025
- Successfully resolved complex dependency chain from new webApp/views.py file
- Installed missing packages: pandas, stellar-sdk  
- Added required environment variables for Astra DB integration
- Fixed import chain: StellarMapCreatorAccountLineageHelpers → sm_horizon → stellar_sdk
- Created missing sm_cron.py helper module for cron job management
- Resolved syntax errors and indentation issues in helper files
- Django Server workflow running successfully on port 5000

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Framework and Structure
- **Django 4.2.7** with a multi-app architecture consisting of three main applications:
  - `apiApp`: Core API functionality and data management
  - `webApp`: Main web interface for user interactions
  - `radialTidyTreeApp`: Specialized visualization components

## Database Architecture
- **Primary Storage**: Astra DB (DataStax Cassandra) for production data storage
- **Local Development**: SQLite fallback for development environments
- **Database Routing**: Custom router (`DatabaseAppsRouter`) directs different apps to appropriate databases
- **ORM**: Mix of Django ORM and django-cassandra-engine for Cassandra integration

## Data Collection Pipeline
- **Asynchronous Processing**: Extensive use of async/await patterns for API calls
- **Scheduled Tasks**: Django management commands with cron scheduling for automated data collection
- **API Integration**: 
  - Horizon API for Stellar blockchain data
  - Stellar Expert API for enhanced account information
- **Retry Logic**: Tenacity library provides robust retry mechanisms for API failures
- **Rate Limiting**: Staggered cron jobs prevent API rate limit violations

## Frontend Architecture
- **Templating**: Django templates with Vue.js components for interactive elements
- **Visualization**: D3.js for radial tree rendering
- **Responsive Design**: Bootstrap-based responsive interface
- **Component System**: Modular Vue.js components for reusable UI elements

## Security and Monitoring
- **Environment Configuration**: Decouple library for secure environment variable management
- **Error Tracking**: Sentry integration for comprehensive error monitoring
- **Input Validation**: Stellar SDK for cryptographic address validation
- **HTTPS Enforcement**: Production settings enforce SSL/TLS

## Cron Job Architecture
- **Health Monitoring**: Dedicated health check system monitors cron job status
- **Sequential Processing**: Jobs are staggered to prevent resource conflicts
- **Status Tracking**: Each job tracks its progress through defined status states
- **Automatic Recovery**: Health check system can reset unhealthy jobs after timeout periods

# External Dependencies

## Blockchain APIs
- **Horizon API**: Official Stellar network API for transaction and account data
- **Stellar Expert**: Third-party service for enhanced Stellar network insights and directory information

## Database Services
- **Astra DB**: DataStax managed Cassandra service for production data storage
- **Cassandra**: Distributed NoSQL database for handling large-scale lineage data

## Monitoring and Development
- **Sentry**: Error tracking and performance monitoring service
- **Replit**: Cloud development and deployment platform

## Key Libraries
- **stellar-sdk**: Official Python SDK for Stellar blockchain interactions
- **django-cassandra-engine**: Django integration for Cassandra databases
- **tenacity**: Retry library for robust API interactions
- **pandas**: Data manipulation and analysis for lineage processing
- **requests**: HTTP library for API communications
- **aiohttp**: Asynchronous HTTP client for efficient API calls

## Frontend Dependencies
- **D3.js**: Data visualization library for radial tree rendering
- **Vue.js**: Progressive JavaScript framework for interactive components
- **Bootstrap**: CSS framework for responsive design
- **jQuery**: JavaScript library for DOM manipulation (legacy admin interface)