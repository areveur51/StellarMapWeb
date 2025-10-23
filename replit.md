# Overview
StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API, Stellar Expert, and Google BigQuery, stores this data in Astra DB (Cassandra), and renders it as interactive D3.js radial tree diagrams. The project aims to provide a comprehensive and cost-effective solution for exploring Stellar account relationships, with a focus on UI/UX, performance, and scalability. It includes features for identifying High-Value Accounts, offers a multi-theme interface, provides enhanced admin portal navigation with clickable account hyperlinks, and features a powerful Query Builder for Cassandra database exploration.

# User Preferences
- Preferred communication style: Simple, everyday language.
- Keep Replit usage anonymous - do not mention Replit in public documentation
- Prompt attachments go to temp/ directory (gitignored), not attached_assets/

# System Architecture

## System Design and UI/UX
- **Interactive Radial Tree Diagrams**: Utilizes D3.js for visualizing Stellar account lineage with circular and standard tidy tree layouts, featuring smart tooltips, scroll restoration, and dynamic line length calculation.
- **Sibling Visualization with Separated Tabs** (2025-10-23): Enhanced lineage tree displays siblings (other children of each creator) at every level alongside the direct lineage path. Intelligent color coding system: **Red links** (#ff3366) highlight the direct lineage path with 2.5px thickness and 90% opacity; **Gray links** (#888888) show siblings with 1.5px thickness and 50% opacity; **Cyan glow** (#00ffff) marks the searched account with enlarged radius and drop-shadow effect. **Separate Tabs**: "Account Lineage" tab shows ONLY the direct lineage path (10 accounts); "Siblings" tab displays all sibling accounts (175 siblings) separately with count header. Backend API endpoint `/api/lineage-with-siblings/` uses **chunked batch queries** (groups of 25 to respect Cassandra's IN limit) reducing total queries from ~200 to ~15 for 185 accounts (configurable max_siblings_per_level, default 50). Frontend `transformSiblingsToLineage()` separates data into `account_lineage_data` (direct path only) and `siblings_data` (siblings only) with metadata flags (is_lineage_path, is_sibling, is_searched_account) for D3.js rendering. Works in both radial and horizontal tidy tree modes.
- **Tidy Tree Visualization**: Dynamic horizontal spacing where line lengths adapt to child count, optimized typography, and constrained tree width. Vertical spacing is controlled by `nodeSize()` layout.
- **Visualization Mode Persistence**: Toggle state persists across page refreshes using localStorage with automatic re-rendering.
- **Advanced Spacing Controls (Tidy Tree Only)**: Three independent sliders for precise layout control (Vertical Spacing, Min Child Distance, Max Child Distance), with preferences persisting via localStorage.
- **Zoom & Pan Controls**: D3 zoom behavior with mouse wheel zoom, click-drag pan, and control buttons (Zoom In, Zoom Out, Fit to Window).
- **Tree Visualization Filters** (2025-10-23): Interactive filters integrated into visualization controls panel for real-time D3 tree filtering. Three filter criteria: **XLM Balance Range** (min/max), **Asset Count Range** (min/max), and **Issuers Only** (accounts with ≥1 asset). Filters apply ONLY to D3 visualizations (both radial and tidy tree modes), NOT to table data. `window.filterTreeAccounts()` filters nodes client-side before passing to `buildTreeFromLineage()`, with unfiltered data cached in `window.unfilteredTreeData` for reset functionality. Filter state persists via localStorage across page refreshes. Status indicator displays "Showing X of Y nodes" when filters are active. Reset button clears all filters, localStorage, and re-renders with full dataset. Cyberpunk-styled filter inputs with consistent glow effects.
- **DRY Visualization Controls**: Shared visualization controls implemented with DRY architecture (`visualization_controls.css`, `visualization_toggle_include.html`) for consistency across pages.
- **Responsive Design**: Bootstrap-based frontend for adaptive layouts.
- **Real-time Feedback**: Vue.js displays pending accounts and pipeline progress.
- **Consistent Theming**: Cyberpunk theme, with additional Borg Green and Predator Red themes, applied across the application with dynamic switching and persistence.
- **Ultra-Compact Dashboard Design**: Optimized dashboard with minimal spacing and smaller font sizes for maximum information density.
- **Modern UX Enhancements**: Gradient backgrounds, shimmer effects, pulsing indicators, smooth transitions, and glow effects.
- **DRY Template Architecture**: Shared components like `search_container_include.html` ensure no code duplication.
- **Icon-Free Navigation**: Clean, cyberpunk-styled navigation buttons.
- **High Value Account (HVA) Leaderboard**: Identifies and ranks accounts based on admin-configurable XLM thresholds, displayed on a dedicated page with efficient filtering and event-based change tracking for storage efficiency.
- **Query Builder**: Comprehensive Cassandra database explorer at `/web/query-builder/` with 10 pre-defined queries and a custom multi-filter builder supporting AND logic. Features network-aware filtering, adaptive `max_scan` limits, sortable results, and clickable account links. **Processing Accounts** query enhanced with dual-table scanning (Search Cache + Account Lineage) and stale detection (>30 min) with `[STALE]` tags. Management command `reset_stale_processing` available to reset stuck accounts.
- **System-Wide Glow Effects**: Comprehensive cyberpunk glow treatments on all interactive elements.
- **Dashboard Layout**: Alerts & Recommendations are prioritized at the top.
- **Architecture Diagrams**: 10 PlantUML diagrams document the system, including System Overview, Data Pipeline, Database Schema, Frontend & API Layer, Monitoring System, Hybrid Architecture, HVA Ranking System, Query Builder Architecture, Dual-Pipeline Architecture, and Pipeline Execution Workflow (with Creator/Child Queueing).

## Technical Implementation
- **Django Framework**: Built on Django 5.0.2 with a multi-app structure (`apiApp`, `webApp`, `radialTidyTreeApp`).
- **Database Management**: Astra DB (Cassandra) for production, SQLite for development, with a custom `DatabaseAppsRouter`. Cassandra models use composite primary keys.
- **Environment-Aware Model Loading**: `apiApp/model_loader.py` dynamically imports Cassandra or SQLite models based on the environment.
- **Django Admin Integration**: Full integration of Cassandra models with clickable hyperlinks for account fields.
- **Dual-Pipeline Tracking**: Cassandra migration completed (2025-10-22) adding `pipeline_source`, `last_pipeline_attempt`, and `processing_started_at` fields for tracking data origin and processing timestamps.
- **Query Optimizations**: HVA leaderboard uses network-aware filtering and smart threshold-based query strategies.
- **Docker Deployment**: Cross-platform Docker Compose setup for development and production.
- **Unified Pipeline Configuration**: All pipeline settings (BigQuery + API) consolidated into `BigQueryPipelineConfig` model (2025-10-23) - single source of truth for cost limits, pipeline mode (API_ONLY/BIGQUERY_ONLY/BIGQUERY_WITH_API_FALLBACK), batch sizes, and intervals. Replaces deprecated APScheduler-based system. Controlled via admin panel at `/admin/apiApp/bigquerypipelineconfig/`.
- **BigQuery-Based Data Collection**: Primary pipeline uses Stellar's BigQuery/Hubble dataset, with age restrictions, cost optimization strategies (`BigQueryCostGuard`), and an API fallback. Includes dynamic adjustment of pipeline settings via an Admin Configuration Panel.
- **Reserved VM Deployment**: Deployment configured for Reserved VM (not autoscale) to enable continuous background pipeline processing. Unified pipeline runner (`python manage.py run_pipelines --loop`) respects database configuration and pipeline_mode settings.
- **HVA Change Tracking**: `HVARankingHelper` provides ranking calculations and change detection with dual SQLite/Cassandra compatibility.
- **API-Based Fast Pipeline**: An alternative 8-stage pipeline using Horizon API and Stellar Expert for comprehensive workflow tracking. **Lineage Graph Expansion** (2025-10-23): Both pipelines now automatically queue discovered creator and child accounts for processing, expanding the lineage graph continuously. Critical bug fixes (2025-10-23): DateTime parsing now converts ISO 8601 strings to datetime objects (was causing 100% failure); asset parsing method added; processing accounts query fixed to match 'PROCESSING' not 'PROGRESS'; reset_stale_processing command fixed with runtime Cassandra detection using `__default_ttl__` attribute check.
- **Queue Synchronizer**: Automatic sync between Search Cache and Account Lineage tables (2025-10-23). Single-account searches create PENDING records in Search Cache, which are promoted to Account Lineage before pipeline processing. After processing completes, status is synced back to Search Cache. Bulk Search bypasses Search Cache and creates records directly in Account Lineage. This architecture ensures all user searches are processed while maintaining data consistency across both tables.
- **API Integration**: Asynchronous interactions with Horizon API and Stellar Expert, utilizing `Tenacity` for robust retries.
- **Two-Tier Creator Extraction**: BigQuery for `create_account` operations; API pipeline with Stellar Expert fallback.
- **Comprehensive Child Account Discovery**: BigQuery pipeline discovers up to 100,000 child accounts with pagination and deduplication.
- **Caching**: 12-hour caching for Stellar address searches, optimized API endpoint caching with 30s TTL for pending accounts.
- **Frontend Interactivity**: Django templates enhanced with Vue.js components for real-time updates.
- **Performance Optimizations**: 30s polling intervals with Page Visibility API and efficient lineage API to avoid full-table scans.
- **Comprehensive Testing**: 180+ tests across 45+ test files using pytest with various markers, covering security, functionality, and performance. Includes focused regression tests for API pipeline datetime parsing, Query Builder status matching with dual-table AND logic assertions, and comprehensive Dashboard accuracy for ALL blocks (2025-10-23). Tests enforce both Search Cache AND Account Lineage tables are scanned, preventing single-table regression. Dashboard regression tests cover ALL sections: Alerts & Recommendations, Database Health, Processing Status, Lineage Integrity, Performance Metrics, API Health, BigQuery Cost Tracking, Dual-Pipeline Metrics, and System Health - ensuring displayed data matches actual database state to prevent false alerts and inaccurate metrics. **Performance Metrics Cassandra Fix** (2025-10-23): Removed `.only()` ORM calls in dashboard view (incompatible with Cassandra) and added dedicated regression test suite `test_dashboard_performance_metrics.py` with 7 test cases verifying dual-table aggregation (Search Cache + Lineage) for avg/fastest/slowest processing times and 24h/7d account counts.
- **Input Validation**: Multi-layer validation for Stellar addresses.
- **Injection Prevention**: Robust measures against various injection types.
- **API Security**: CSRF protection, Content-Type validation, query parameter security, and HTTP security headers.
- **Configuration Security**: Secrets managed via environment variables, secure Django defaults, and HTTPS enforcement.
- **Production Settings**: Dedicated `production.py` for best practices.
- **Error Tracking**: Sentry integration for error monitoring.
- **Security Auditing**: Regular `pip-audit` checks.
- **Open Source & CI/CD**: MIT License, comprehensive documentation, GitHub Actions for automated CI, and environment configuration guidance.

# External Dependencies

## Blockchain APIs
- Horizon API
- Stellar Expert
- Google BigQuery (for Stellar Hubble dataset)

## Database Services
- Astra DB (DataStax managed Cassandra)
- Cassandra

## Monitoring and Development
- Sentry
- Replit

## Key Libraries
- stellar-sdk
- django-cassandra-engine
- tenacity
- pandas
- requests
- aiohttp
- google-cloud-bigquery

## Frontend Dependencies
- D3.js
- Vue.js
- Bootstrap
- jQuery

# Documentation Files
- **TECHNICAL_ARCHITECTURE.md**: Comprehensive developer documentation with all 10 PlantUML diagrams, detailed explanations of database schema, API endpoints, performance optimizations, security implementations, deployment strategies, and pipeline execution workflow with lineage expansion
- **USER_GUIDE.md**: End-user documentation with screenshots and examples
- **DUAL_PIPELINE_IMPLEMENTATION.md**: Dual-pipeline architecture (BigQuery + API fallback) with cost optimization
- **HVA_RANKING_SYSTEM.md**: Multi-threshold HVA system implementation details
- **TESTING.md**: pytest guide with admin portal regression tests and CI/CD pipeline configuration
- **SECURITY.md**: Security practices and vulnerability reporting
- **CONTRIBUTING.md**: Contribution guidelines
- **README.md**: Project overview and quick start guide