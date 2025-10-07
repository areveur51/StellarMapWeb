# Overview

StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API and Stellar Expert, stores this data in Astra DB (Cassandra), and then renders it as interactive D3.js radial tree diagrams. The project aims to provide users with a clear, interactive "family tree" view of how Stellar accounts are created and interconnected, offering insights into the network's structure and activity. The application features a fast, optimized data collection pipeline capable of processing an address in 2-3 minutes, robust address validation, and a user-friendly interface with real-time pending account tracking and graceful error handling.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Architecture Diagrams
- **PlantUML Visualization**: 5 modular architecture diagrams in `diagrams/` directory with SVG outputs included in README.md
- **Color Scheme**: Custom cyberpunk theme (#372963 background, #00FF9C borders, #c592ff arrows)
- **Diagram Breakdown**:
  1. **System Overview** (`01_system_overview.puml`): High-level architecture showing frontend, Django apps, external APIs, and database
  2. **Data Pipeline** (`02_data_pipeline.puml`): 8-stage sequential pipeline with status tracking
  3. **Database Schema** (`03_database_schema.puml`): Cassandra tables with composite keys and optimized queries
  4. **Frontend & API** (`04_frontend_api.puml`): Vue.js components, API endpoints, and auto-refresh polling
  5. **Monitoring System** (`05_monitoring_system.puml`): Cron health monitoring, stuck record recovery, and stage tracking
- **Tools**: PlantUML and Graphviz installed as system dependencies for diagram generation
- **Regenerate**: Run `cd diagrams && plantuml -tsvg *.puml` to regenerate all diagrams

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
- **Stages Monitoring**: Real-time pipeline progress tracking showing execution time, status, and errors for each of the 8 stages (Stage 1: Make Parent Lineage, Stage 2: Collect Horizon Data, Stages 3-8: Lineage enrichment) per address via `/api/stage-executions/` endpoint with 5-second auto-refresh in dedicated Stages tab.
- **Immediate Stage Initialization**: All 8 pipeline stages are created instantly when a new address is searched, appearing immediately in the Stages tab with PENDING status before processing begins; helper functions `initialize_stage_executions()` and `update_stage_execution()` ensure consistent stage lifecycle management with no duplicates.
- **Interactive JSON Viewer**: Stages tab includes clickable JSON icon in Actions column that opens modal popup displaying complete stage execution data as formatted, syntax-highlighted JSON with dark theme styling using highlight.js; gracefully falls back to plain JSON if highlight.js unavailable.

## Security and Monitoring

### Testing Framework
- **Comprehensive Test Suite**: 122+ tests across 8 test modules covering security, functionality, and monitoring.
- **Test Modules**:
  - `test_validator_security.py`: 16 tests for enhanced validator with ValidationError enforcement
  - `test_security_injection_prevention.py`: NoSQL injection, XSS, command injection, path traversal
  - `test_security_api_validation.py`: Stellar address validation, external API data validation, query parameters
  - `test_security_configuration.py`: Secrets management, environment variables, secure defaults
  - `test_security_frontend.py`: XSS prevention, CSRF protection, clickjacking prevention
  - `test_failed_status_handling.py`: Terminal status exclusion from cron processing
  - `test_stage_executions.py`: 17 tests for pipeline stage monitoring (model validation, API security, stage tracking, cron integration)
  - `test_stage_json_viewer.py`: 15 tests for interactive JSON viewer (template rendering, API data integrity, JSON formatting, security)
- **Test Coverage Areas**:
  - ValidationError enforcement for malicious input (shell chars, path traversal, null bytes, invalid checksums)
  - Injection Prevention (NoSQL injection, XSS, command injection, path traversal)
  - API Input Validation (Stellar addresses, external API data, query parameters)
  - Configuration Security (secrets management, environment variables, secure defaults)
  - Frontend Security (XSS prevention, CSRF protection, clickjacking prevention)
  - Terminal Status Handling (FAILED, INVALID_HORIZON_STELLAR_ADDRESS exclusion from recovery)

### Input Validation & Injection Prevention
- **Enhanced Validator with ValidationError Enforcement**:
  - `StellarMapValidatorHelpers.validate_stellar_account_address()` supports dual modes:
    - `raise_exception=False` (default): Returns True/False for backwards compatibility
    - `raise_exception=True`: Raises Django ValidationError with descriptive messages for strict enforcement
  - Multi-layer validation prevents malicious data from proceeding past validation layer
- **Multi-Layer Address Validation**:
  - Stellar SDK regex and cryptographic checks at view/model/validator layers
  - 56-character length enforcement with 'G' prefix requirement
  - Base32 character whitelist (A-Z, 2-7) - prevents special characters, null bytes, unicode attacks
  - Horizon API 404 validation catches invalid addresses that don't exist on the network
  - Invalid addresses marked with `INVALID_HORIZON_STELLAR_ADDRESS` terminal status
- **NoSQL Injection Protection**:
  - Cassandra query parameter sanitization and validation
  - Status field whitelist validation (prevents status injection)
  - Numeric field bounds checking (prevents overflow attacks)
  - Query length limits to prevent buffer overflow
- **XSS Prevention**:
  - Django template auto-escaping enabled globally
  - Vue.js text interpolation (auto-escaped)
  - No v-html usage with user input
  - API response escaping and sanitization
  - Error messages sanitized to prevent reflection attacks
- **Command Injection Prevention**:
  - Shell character blacklist in validators (`;`, `|`, `&`, `` ` ``, `$`, `(`, `)`)
  - No shell execution in validation or processing code
  - External API command parameter whitelisting
- **Path Traversal Protection**:
  - Path traversal pattern detection (`../`, `..\\`, URL-encoded variants)
  - File path sanitization in all file operations

### API Security
- **CSRF Protection**: Django CSRF middleware enabled for all state-changing operations
- **Content-Type Validation**: API validates Content-Type headers and rejects invalid types
- **Query Parameter Security**: 
  - Length limits on all query parameters
  - Special character handling and sanitization
  - URL encoding validation
- **HTTP Security Headers**:
  - X-Frame-Options: DENY/SAMEORIGIN (clickjacking prevention)
  - X-Content-Type-Options: nosniff (MIME sniffing prevention)
  - Referrer-Policy configured
  - Content-Security-Policy (CSP) for inline script prevention
  - Strict-Transport-Security (HSTS) in production

### External API Data Validation
- **Horizon API Response Validation**:
  - Operation type whitelist (24 valid Stellar operation types)
  - Numeric field bounds checking (balance, timestamp validation)
  - Timestamp sanity checks (prevents time-based attacks)
  - JSON schema validation before processing
- **Stellar Expert Data Sanitization**:
  - Domain validation (prevents javascript:, file://, data: URIs)
  - HTML/script tag stripping from names and descriptions
  - Tag array sanitization

### Configuration Security
- **Secrets Management**:
  - All secrets from environment variables via Replit Secrets
  - `python-decouple` for typed environment variable loading
  - No hardcoded credentials in source code
  - Django SECRET_KEY from environment (50+ characters, not default values)
  - Cassandra/Astra DB credentials from ASTRA_DB_TOKEN environment variable
- **Secure Defaults**:
  - DEBUG=False in production
  - ALLOWED_HOSTS configured (not wildcard in production)
  - SESSION_COOKIE_SECURE=True (HTTPS-only cookies)
  - SESSION_COOKIE_HTTPONLY=True (prevents JS access)
  - CSRF_COOKIE_SECURE=True in production
  - SECURE_SSL_REDIRECT=True in production
- **Database Security**:
  - Cassandra connections use SSL/TLS
  - Connection encryption enforced
  - No database credentials in source code

### Frontend Security
- **Template Security**:
  - Django auto-escaping enabled for all templates
  - |safe filter never used with user input
  - json_script filter for safe JSON embedding
- **Vue.js Security**:
  - Text interpolation {{ }} used (auto-escaped)
  - v-bind for dynamic attributes (prevents attribute injection)
  - No v-html with user-provided content
  - Event handlers call methods, not eval
- **Session Security**:
  - Secure cookie flags set
  - HTTP-only cookies prevent XSS theft
  - SameSite cookie attribute configured

### Environment Configuration & Monitoring
- **Environment Configuration**: `Decouple` library for secure environment variable management with type validation.
- **Error Tracking**: Sentry integration for error monitoring (sensitive data filtered from logs).
- **HTTPS Enforcement**: Production settings enforce SSL/TLS with HSTS headers.
- **Security Test Automation**: Continuous security testing in CI/CD pipeline.

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