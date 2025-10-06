# Overview

StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API and Stellar Expert, stores this data in Astra DB (Cassandra), and then renders it as interactive D3.js radial tree diagrams. The project aims to provide users with a clear, interactive "family tree" view of how Stellar accounts are created and interconnected, offering insights into the network's structure and activity. The application features a fast, optimized data collection pipeline capable of processing an address in 2-3 minutes, robust address validation, and a user-friendly interface with real-time pending account tracking and graceful error handling.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Framework and Structure
- **Django 4.2.7** with a multi-app architecture: `apiApp` (API/data management), `webApp` (user interface), and `radialTidyTreeApp` (visualization components).

## Database Architecture
- **Primary Storage**: Astra DB (DataStax Cassandra) for production using `django-cassandra-engine`. SQLite for local development.
- **Database Routing**: Custom `DatabaseAppsRouter` for directing apps to appropriate databases.
- **ORM**: Combines Django ORM with direct Cassandra integration, explicitly using `__table_name__` for Cassandra models.
- **Schema Design**: Cassandra models use composite primary keys and clustering keys for efficient querying and include `created_at` and `updated_at` timestamps.
- **Caching**: 12-hour caching strategy for Stellar address searches using `StellarAccountSearchCache` to minimize API calls.

## Data Collection Pipeline
- **Fast Pipeline Architecture**: Consolidated 9 staggered cron jobs into a single sequential pipeline running every 2 minutes, reducing processing time to ~2-3 minutes per address.
- **Automated Execution**: Background cron worker (`run_cron_jobs.py`) runs automatically, orchestrating 8 data collection stages.
- **Workflow Management**: Comprehensive cron workflow with 18 status constants (`PENDING`, `IN_PROGRESS`, `DONE`, `RE_INQUIRY`, `FAILED`, `INVALID_HORIZON_STELLAR_ADDRESS`) for tracking data collection.
- **Cron Health Monitoring**: `ManagementCronHealth` table tracks cron job health with `HEALTHY` and `UNHEALTHY_*` statuses; cron skips processing when any `UNHEALTHY` status exists to prevent cascading failures.
- **Rate Limiting Recovery**: When Cassandra Document API rate limits occur, cron is marked `UNHEALTHY_RATE_LIMITED_BY_CASSANDRA_DOCUMENT_API`; old unhealthy records must be manually cleared via `.allow_filtering()` query and deletion by composite primary key (id, created_at, cron_name).
- **Horizon API Validation**: When Horizon API returns 404 (NotFoundError) for an address, both `StellarAccountSearchCache` and `StellarCreatorAccountLineage` records are marked with `INVALID_HORIZON_STELLAR_ADDRESS` status and processing immediately stops (operations/effects fetching skipped).
- **Terminal Status Architecture**: `INVALID_HORIZON_STELLAR_ADDRESS` and `FAILED` are terminal statuses excluded from `STUCK_THRESHOLDS`, ensuring invalid addresses are never picked up by cron jobs or stuck record recovery.
- **Stuck Record Recovery**: Automatic detection and recovery system for stuck records in `STUCK_THRESHOLDS`, resetting them to `PENDING` or marking as `FAILED` after multiple retries; runs independently of cron health status.
- **API Integration**: Uses Horizon API and Stellar Expert with asynchronous interactions (`async/await`).
- **Retry Logic**: `Tenacity` library for robust API calls with exponential backoff.
- **Prioritization**: New user searches (`PENDING_MAKE_PARENT_LINEAGE`) are prioritized over cache refreshes (`RE_INQUIRY`).

## Frontend Architecture
- **Templating**: Django templates enhanced with Vue.js components for interactivity.
- **Visualization**: D3.js for interactive radial tree diagrams.
- **Responsive Design**: Bootstrap-based interface.
- **User Experience**: Graceful error handling for invalid Stellar addresses, default display of pending accounts, and prevention of browser caching using `Cache-Control` headers.
- **Pending Accounts UI**: Real-time Vue.js watcher displays all `PENDING`/`IN_PROGRESS`/`RE_INQUIRY` accounts from `StellarAccountSearchCache` and `StellarCreatorAccountLineage` tables.
- **Auto-Refresh**: Vue.js polling system refreshes Pending Accounts tab every 5 seconds via `/api/pending-accounts/` endpoint, with immediate initial fetch and proper cleanup on component destruction.

## Security and Monitoring
- **Environment Configuration**: `Decouple` library for secure environment variable management.
- **Error Tracking**: Sentry integration for error monitoring.
- **Input Validation**: Multi-layer address validation including:
  - Stellar SDK regex and cryptographic checks at view/model/validator layers
  - Horizon API 404 validation catches invalid addresses that pass format checks but don't exist on the network
  - Invalid addresses marked with `INVALID_HORIZON_STELLAR_ADDRESS` terminal status
- **HTTPS Enforcement**: Production settings enforce SSL/TLS.

# External Dependencies

## Blockchain APIs
- **Horizon API**: Official Stellar network API for core data.
- **Stellar Expert**: Third-party service for enhanced Stellar account information.

## Database Services
- **Astra DB**: DataStax managed Cassandra service for production.
- **Cassandra**: Distributed NoSQL database.

## Monitoring and Development
- **Sentry**: Error tracking and performance monitoring.
- **Replit**: Cloud development and deployment platform.

## Key Libraries
- **stellar-sdk**: Python SDK for Stellar blockchain.
- **django-cassandra-engine**: Django integration for Cassandra.
- **tenacity**: Retry library for robust operations.
- **pandas**: Data manipulation.
- **requests**: HTTP client.
- **aiohttp**: Asynchronous HTTP client.

## Frontend Dependencies
- **D3.js**: Data visualization library.
- **Vue.js**: JavaScript framework for interactive UI.
- **Bootstrap**: CSS framework for responsive design.
- **jQuery**: JavaScript library.