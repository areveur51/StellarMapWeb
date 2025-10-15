# Overview

StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API and Stellar Expert, stores this data in Astra DB (Cassandra), and renders it as interactive D3.js radial tree diagrams.

# User Preferences

- Preferred communication style: Simple, everyday language.
- Keep Replit usage anonymous - do not mention Replit in public documentation
- Prompt attachments go to temp/ directory (gitignored), not attached_assets/

# System Architecture

## System Design and UI/UX
- **Interactive Radial Tree Diagrams**: Utilizes D3.js for visualizing Stellar account lineage with circular ISSUER node distribution (23° minimum angular separation at each depth level).
- **Dual Visualization Modes**: Toggle between Radial Tidy Tree (circular layout, default) and standard Tidy Tree (left-to-right hierarchical layout). Cyberpunk-styled toggle switch with gradient slider and real-time mode indicator in top-right corner of visualization page. Both modes feature identical tooltip/breadcrumb functionality, path highlighting, and glow effects.
- **Responsive Design**: Bootstrap-based frontend for adaptive layouts.
- **Real-time Feedback**: Displays pending accounts and pipeline stage progress using Vue.js for immediate user feedback.
- **Consistent Theming**: Replit cyberpunk theme applied across the application and architecture diagrams.
- **Ultra-Compact Dashboard Design**: Highly optimized System Dashboard with minimal spacing (10px container padding, 8px card padding, 8px row gutters), smaller font sizes (1.3rem stat values, 0.7rem labels), and no icon usage for maximum space utilization and cleaner visual appearance.
- **Modern UX Enhancements**: Gradient backgrounds on stat cards and alerts, shimmer hover effects, pulsing health indicators for warnings/errors, color-coded alert borders, smooth transitions, and glowing text effects - all maintaining cyberpunk theme cohesion.
- **DRY Template Architecture**: Shared `search_container_include.html` component used across all pages (index, search, dashboard, HVA) - single source of truth for navigation and search functionality. No code duplication.
- **Icon-Free Navigation**: Clean, cyberpunk-styled Quick Navigation buttons without icons, using consistent cyan (#96DDF2) outline styling throughout the sidebar and dashboard.
- **High Value Account (HVA) Leaderboard**: Automatic identification and tagging of accounts with >1M XLM balance. Dedicated leaderboard page at `/web/high-value-accounts/` displays rankings sorted by XLM balance with timestamps. Efficient boolean-based filtering with is_hva column for scalable queries. Clean table design with gold/silver/bronze rank highlighting and cyberpunk theme cohesion.
- **System-Wide Glow Effects**: Comprehensive cyberpunk glow treatments applied across all interactive elements: search bar (border/input/icons with gradient backgrounds and dual-color glows), navbar sidebar (header/body/footer with shimmer animations and cyan highlights on hover), and radial tidy tree visualization (SVG nodes, links, and text with drop-shadow filters, scale transforms, and color transitions). All effects use consistent color palette (cyan #96DDF2, green #0BE784, purple gradients) with smooth 0.3s transitions.
- **Multi-Theme System (Admin & Main App)**: Dynamic theme switcher with three sci-fi themed options that apply across the entire application:
  - **Cyberpunk (Default)**: Dark purple backgrounds (#261D45), cyan/green accent colors, gradient buttons, glowing interactive elements
  - **Borg Green**: Star Trek Borg-inspired matrix green theme (#00ff41) with assimilation aesthetics, monospace fonts, and green glow effects
  - **Predator Red**: Predator thermal HUD red theme (#ff0000) with hunting mode visuals, scanline effects, and thermal vision overlay
  - Theme preferences stored in localStorage and persist across sessions
  - Theme selector in admin header syncs with main application pages
  - Global theme loader (`global_theme_loader.js`) applies selected theme to homepage, search pages, and admin portal
  - Real-time theme sync (`theme_sync.js`) with 1-second polling detects theme changes and applies them automatically
  - Seamless theme consistency across all pages using shared localStorage key (`django_admin_theme`)
  - Change theme in admin portal → frontend automatically updates within 1 second
- **Dashboard Layout**: Alerts & Recommendations moved to top of System Dashboard for immediate visibility of critical issues. Quick Actions section removed to streamline interface and eliminate redundancy with sidebar navigation.
- **Architecture Diagrams**: 5 PlantUML diagrams in `diagrams/` directory exported as PNG for README display.

## Technical Implementation
- **Django Framework**: Built on Django 5.0.2 with a multi-app structure (`apiApp`, `webApp`, `radialTidyTreeApp`). Note: Django 5.0.2 has known vulnerabilities but upgrading to 5.0.14+ breaks compatibility (documented in SECURITY.md).
- **Database Management**: Astra DB (Cassandra) for production, SQLite for development. Custom `DatabaseAppsRouter` for database routing. Cassandra models utilize composite primary keys for efficient querying.
- **Environment-Aware Model Loading**: Centralized model import system via `apiApp/model_loader.py` prevents conflicts between Cassandra and SQLite models. When `ENV in ['production', 'replit']`, imports from `models_cassandra.py`; otherwise imports from `models_local.py`. All helper files and management commands use `model_loader` instead of direct imports to ensure correct model selection. Query syntax adapts automatically: Cassandra uses `.filter().all()` or `.filter().limit(n)`, SQLite uses `.filter()` or `.filter()[:n]`.
- **Django Admin Integration**: Fully integrated Cassandra models with workarounds for query constraints: `ordering=()`, `show_full_result_count=False`, `.limit()` queries, and `CASSANDRA_FALLBACK_ORDER_BY_PYTHON=True` setting for Python-side sorting.
- **Docker Deployment**: Cross-platform Docker Compose setup for easy local development on Windows, Linux, and macOS. Includes separate development (`docker-compose.yml`) and production (`docker-compose.prod.yml`) configurations with automatic migrations and dual-service orchestration (web + cron).
- **BigQuery-Based Data Collection (Primary)**: Main pipeline uses Stellar's public BigQuery/Hubble dataset for **lineage data ONLY** (account creation dates, parent-child relationships, child issuers). **Age Restriction (v3.0)**: Instant BigQuery queries ONLY for accounts <1 year old. Accounts >1 year old: if existing complete lineage found in database, use it directly (skip BigQuery); if no data exists, queue for batch pipeline processing. Cost optimization strategy prevents expensive historical queries while ensuring data availability. **Permanent Storage Architecture**: BigQuery queried ONLY for first-time account searches (never searched before). Lineage data stored permanently in Cassandra DB - repeat searches use Cassandra (0 BigQuery cost). Records updated when stale (>12 hours) or when user requests refresh. **Consolidated Query Optimization**: Single CTE-based query fetches creator + children + issuers in ONE BigQuery scan (50% cost reduction vs separate queries). Uses partition filters, ROW_NUMBER() pagination, and JOIN to accounts_current for issuer discovery. **Cost Controls (v3.0)**: BigQueryCostGuard enforces BOTH cost limit (default $0.71) AND size limit (default 145GB) via dual dry-run validation. ALL queries to enriched_history_operations require partition filters (closed_at BETWEEN date range). Safe date windows calculated from account creation dates. Prevents runaway costs. **Admin Configuration Panel (v3.0)**: All BigQuery pipeline settings now configurable via Django admin panel: cost limits (USD and GB), pipeline modes (BigQuery only, API only, hybrid), age restrictions, API fallback settings, and batch processing limits. Singleton configuration model with helpful examples, disclaimers, and change tracking. Eliminates need for code deployment to adjust pipeline behavior. **API Fallback Mechanism**: When Cost Guard blocks queries (exceeds cost/size limits), pipeline automatically falls back to free APIs: Horizon operations → Stellar Expert for creator discovery, Horizon operations for child accounts. **Cost-Effective**: Typical queries cost $0.18-0.35 per account with full lineage. Under 1 TB/month free tier for up to 2,500 unique accounts/month. Processes accounts in 50-90 seconds (2-3x faster than API-based approach). Discovers up to 100,000 child accounts. No API rate limits on BigQuery.
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
- **Startup Script with Workflow Restart Guidance**: `startup.sh` checks environment configuration and provides clear instructions for manually restarting workflows after ENV secret changes. **Important**: Workflows do not automatically pick up secret changes - you must manually restart them via the UI (Stop ⏹ then Run ▶ button). After restarting workflows, ENV changes take effect immediately, enabling database switching (SQLite ↔ Cassandra).

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