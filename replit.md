# Overview

StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API and Stellar Expert, stores this data in Astra DB (Cassandra), and renders it as interactive D3.js radial tree diagrams.

# User Preferences

- Preferred communication style: Simple, everyday language.
- Keep Replit usage anonymous - do not mention Replit in public documentation
- Prompt attachments go to temp/ directory (gitignored), not attached_assets/

# System Architecture

## System Design and UI/UX
- **Interactive Radial Tree Diagrams**: Utilizes D3.js for visualizing Stellar account lineage with circular ISSUER node distribution (23° minimum angular separation at each depth level).
- **Responsive Design**: Bootstrap-based frontend for adaptive layouts.
- **Real-time Feedback**: Displays pending accounts and pipeline stage progress using Vue.js for immediate user feedback.
- **Consistent Theming**: Replit cyberpunk theme applied across the application and architecture diagrams.
- **Architecture Diagrams**: 5 PlantUML diagrams in `diagrams/` directory exported as PNG for README display.

## Technical Implementation
- **Django Framework**: Built on Django 5.0.2 with a multi-app structure (`apiApp`, `webApp`, `radialTidyTreeApp`). Note: Django 5.0.2 has known vulnerabilities but upgrading to 5.0.14+ breaks compatibility (documented in SECURITY.md).
- **Database Management**: Astra DB (Cassandra) for production, SQLite for development. Custom `DatabaseAppsRouter` for database routing. Cassandra models utilize composite primary keys for efficient querying.
- **Django Admin Integration**: Fully integrated Cassandra models with workarounds for query constraints: `ordering=()`, `show_full_result_count=False`, `.limit()` queries, and `CASSANDRA_FALLBACK_ORDER_BY_PYTHON=True` setting for Python-side sorting.
- **Docker Deployment**: Cross-platform Docker Compose setup for easy local development on Windows, Linux, and macOS. Includes separate development (`docker-compose.yml`) and production (`docker-compose.prod.yml`) configurations with automatic migrations and dual-service orchestration (web + cron).
- **BigQuery-Based Data Collection (Primary)**: Main pipeline uses Stellar's public BigQuery/Hubble dataset for **lineage data ONLY** (account creation dates, parent-child relationships, child issuers). **Permanent Storage Architecture**: BigQuery queried ONLY for first-time account searches (never searched before). Lineage data stored permanently in Cassandra DB - repeat searches use Cassandra (0 BigQuery cost). Account details (balance, home_domain, flags) fetched from Horizon API. Assets fetched from Stellar Expert. **Cost Controls (v2.0)**: BigQueryCostGuard enforces 100MB query limit via dry-run validation. ALL queries to enriched_history_operations require partition filters (closed_at BETWEEN date range). Safe date windows calculated from account creation dates. Prevents 10+ TiB runaway costs. **Cost-Effective**: Under 1 TB/month free tier for up to 2,500 unique accounts/month. With cost controls: ~$0.0001-0.0002 per account. Processes accounts in 50-90 seconds (2-3x faster than API-based approach). Discovers up to 100,000 child accounts. No API rate limits on BigQuery.
- **API-Based Fast Pipeline (Educational/Reference)**: Alternative 8-stage sequential pipeline using Horizon API and Stellar Expert. Processes addresses in 2-3 minutes. Includes comprehensive workflow tracking (18 status constants), health monitoring, and stuck record recovery. Retained for educational purposes and API-based data collection demonstrations. Not enabled by default.
- **API Integration**: Asynchronous interactions with Horizon API and Stellar Expert, using `Tenacity` for robust retries with exponential backoff.
- **Two-Tier Creator Extraction**: BigQuery pipeline queries `enriched_history_operations` for `create_account` operations (type=0) to find creator/funder. API pipeline uses Horizon operations (oldest first) with Stellar Expert as fallback.
- **Comprehensive Child Account Discovery**: BigQuery pipeline discovers up to 100,000 child accounts per parent with pagination (10,000-row batches) and deduplication by account address. Handles transactions creating multiple accounts (airdrops). Enables complete bi-directional tree visualization (ancestors + descendants).
- **Caching**: 12-hour caching for Stellar address searches to minimize API calls.
- **Frontend Interactivity**: Django templates enhanced with Vue.js components, including a polling system for real-time updates and an interactive JSON viewer for detailed stage execution data.

## Security and Monitoring
- **Comprehensive Testing**: 122+ tests cover security (injection prevention, validation), functionality, and monitoring.
- **Input Validation**: Multi-layer validation for Stellar addresses, including regex, cryptographic checks, and Horizon API 404 validation.
- **Injection Prevention**: Robust measures against NoSQL injection, XSS, command injection, and path traversal.
- **API Security**: CSRF protection, Content-Type validation, query parameter security, and HTTP security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP, HSTS).
- **Configuration Security**: Secrets managed via environment variables (Replit Secrets, `python-decouple`), secure Django defaults (DEBUG=False, ALLOWED_HOSTS), and HTTPS enforcement.
- **Production Settings**: Dedicated production.py with HTTPS enforcement, HSTS, secure cookies, WhiteNoise static file serving, and all security best practices.
- **Error Tracking**: Sentry integration for error monitoring.
- **Security Auditing**: Regular pip-audit checks, documented vulnerabilities in SECURITY.md with mitigation strategies.

## Open Source & CI/CD
- **License**: MIT License for maximum adoption and contribution flexibility.
- **Documentation**: Comprehensive CONTRIBUTING.md with setup instructions, coding standards, and PR guidelines.
- **Security Policy**: SECURITY.md with vulnerability reporting procedures, known issues, and production deployment checklist.
- **GitHub Actions**: Automated CI workflow for testing, linting, security audits, and deployment checks across Python 3.10 and 3.11.
- **Environment Configuration**: Complete .env.example with all required variables for easy setup.

# External Dependencies

## Blockchain APIs
- **Horizon API**: Stellar network data.
- **Stellar Expert**: Enhanced Stellar account information.

## Database Services
- **Astra DB**: DataStax managed Cassandra.
- **Cassandra**: NoSQL database.

## Monitoring and Development
- **Sentry**: Error tracking.
- **Replit**: Cloud development platform.

## Key Libraries
- **stellar-sdk**: Python SDK for Stellar.
- **django-cassandra-engine**: Django-Cassandra integration.
- **tenacity**: Retry logic.
- **pandas**: Data manipulation.
- **requests**: HTTP client.
- **aiohttp**: Asynchronous HTTP client.
- **google-cloud-bigquery**: Google BigQuery client for Stellar Hubble dataset queries.

## Frontend Dependencies
- **D3.js**: Data visualization.
- **Vue.js**: Interactive UI.
- **Bootstrap**: CSS framework.
- **jQuery**: JavaScript library.