# Overview
StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API, Stellar Expert, and Google BigQuery, stores this data in Astra DB (Cassandra), and renders it as interactive D3.js radial tree diagrams. The project aims to provide a comprehensive and cost-effective solution for exploring Stellar account relationships, with a focus on UI/UX, performance, and scalability. It includes features for identifying High-Value Accounts, offers a multi-theme interface, provides enhanced admin portal navigation with clickable account hyperlinks, and features a powerful Query Builder for Cassandra database exploration.

# User Preferences
- Preferred communication style: Simple, everyday language.
- Keep Replit usage anonymous - do not mention Replit in public documentation
- Prompt attachments go to temp/ directory (gitignored), not attached_assets/

# Recent Changes (December 2025)
## Comprehensive Testing Infrastructure
- **Pytest Configuration**: Added 6 test markers (unit, integration, e2e, performance, regression, slow) with parallel execution support in `pyproject.toml`.
- **New Test Files**: Created 5 comprehensive test suites covering BigQuery caching, API endpoint optimizations, Query Builder column parity, Vue component initialization, and database integration.
- **CI/CD Pipeline**: GitHub Actions workflow (`.github/workflows/test.yml`) with 5 parallel jobs for unit, integration, performance, coverage, and all-tests.
- **Documentation**: Enhanced `TESTING.md` with pytest usage examples, best practices, and debugging tips.

# System Architecture

## System Design and UI/UX
- **Interactive Radial Tree Diagrams**: Utilizes D3.js for visualizing Stellar account lineage with circular and standard tidy tree layouts. Features include smart tooltips, scroll restoration, viewport-aware overflow prevention, and dynamic line length calculation based on child node count.
- **Tidy Tree Visualization**: Dynamic horizontal spacing where line lengths adapt to child count (fewer children = shorter lines, more children = longer lines). Optimized typography with normal font weight (400) and increased letter spacing for readability. Text overflow prevented with increased right margin (250px) and constrained tree width (70%). Vertical spacing controlled by nodeSize() layout allowing natural tree expansion.
- **Visualization Mode Persistence**: Toggle state persists across page refreshes on both /search and /tree endpoints using localStorage with automatic re-rendering.
- **Advanced Spacing Controls (Tidy Tree Only)**: Three independent sliders for precise layout control: Vertical Spacing (0.5x-3.0x) for up/down node distribution, Min Child Distance (0.3x-1.5x) for nodes with few children, Max Child Distance (1.0x-3.0x) for nodes with many children. Controls automatically hidden in Radial mode, visible only in Tidy Tree mode. All preferences persist via localStorage.
- **Zoom & Pan Controls**: D3 zoom behavior with mouse wheel zoom, click-drag pan, and three control buttons (Zoom In 1.3x, Zoom Out 0.77x, Fit to Window). Scale extent 0.1x-10x with smooth transitions (300ms zoom, 750ms fit). Works seamlessly in both visualization modes.
- **DRY Visualization Controls**: Shared visualization controls (toggle switch, spacing sliders, zoom buttons) implemented with DRY architecture: `visualization_controls.css` for styling, `visualization_toggle_include.html` for HTML/JS, loaded by both /search and /tree pages for consistency.
- **Responsive Design**: Bootstrap-based frontend for adaptive layouts.
- **Real-time Feedback**: Vue.js displays pending accounts and pipeline progress.
- **Consistent Theming**: Cyberpunk theme, with additional Borg Green and Predator Red themes, applied across the application with dynamic switching and persistence.
- **Ultra-Compact Dashboard Design**: Optimized dashboard with minimal spacing and smaller font sizes for maximum information density.
- **Modern UX Enhancements**: Gradient backgrounds, shimmer effects, pulsing indicators, smooth transitions, and glow effects maintain the cyberpunk aesthetic.
- **DRY Template Architecture**: Shared components like `search_container_include.html` ensure no code duplication.
- **Icon-Free Navigation**: Clean, cyberpunk-styled navigation buttons.
- **High Value Account (HVA) Leaderboard**: Identifies and ranks accounts with >1M XLM, displayed on a dedicated page with efficient filtering.
- **HVA Ranking System**: Event-based change tracking that records only meaningful ranking changes (ENTERED, EXITED, RANK_UP, RANK_DOWN) achieving 480x storage efficiency vs snapshots. UI displays 24h rank changes with visual indicators (arrows, badges, percentages). See [HVA_RANKING_SYSTEM.md](HVA_RANKING_SYSTEM.md) for details.
- **Query Builder**: Comprehensive Cassandra database explorer at /web/query-builder/ with 10 pre-defined queries (stuck accounts, orphan accounts, failed stages, etc.) and custom multi-filter builder supporting AND logic. Features network-aware filtering (public/testnet) across all queries. Performance safeguards use adaptive max_scan limits (10x for dense data, 100x for sparse HVA data) to prevent unbounded table scans while ensuring complete results. Includes sortable results table with clickable account links and result limits (50-500 records).
- **System-Wide Glow Effects**: Comprehensive cyberpunk glow treatments on all interactive elements using a consistent color palette.
- **Dashboard Layout**: Alerts & Recommendations are prioritized at the top for immediate visibility.
- **Architecture Diagrams**: 7 PlantUML diagrams are used for documentation.

## Technical Implementation
- **Django Framework**: Built on Django 5.0.2 with a multi-app structure (`apiApp`, `webApp`, `radialTidyTreeApp`).
- **Database Management**: Astra DB (Cassandra) for production, SQLite for development, with a custom `DatabaseAppsRouter`. Cassandra models use composite primary keys.
- **Environment-Aware Model Loading**: `apiApp/model_loader.py` dynamically imports Cassandra or SQLite models based on the environment.
- **Django Admin Integration**: Full integration of Cassandra models with workarounds for query constraints. Admin portal features clickable hyperlinks for stellar_account and stellar_creator_account fields that open search pages in new windows.
- **Docker Deployment**: Cross-platform Docker Compose setup for development and production, including automatic migrations.
- **BigQuery-Based Data Collection**: Primary pipeline uses Stellar's BigQuery/Hubble dataset for lineage, with an age restriction for instant queries (<1 year old accounts). Cost optimization strategies include permanent Cassandra storage after first query, consolidated CTE-based queries, `BigQueryCostGuard` for cost and size limits, and singleton pattern for client caching to avoid expensive re-initialization. An Admin Configuration Panel allows dynamic adjustment of pipeline settings. Includes an API fallback mechanism if BigQuery limits are exceeded. Pipeline automatically detects and records HVA ranking changes.
- **HVA Change Tracking**: `HVARankingHelper` provides ranking calculations and change detection with dual SQLite/Cassandra compatibility. `recalculate_hva_rankings` management command for initial backfill.
- **API-Based Fast Pipeline**: An alternative 8-stage pipeline using Horizon API and Stellar Expert for educational purposes, providing comprehensive workflow tracking.
- **API Integration**: Asynchronous interactions with Horizon API and Stellar Expert, utilizing `Tenacity` for robust retries.
- **Two-Tier Creator Extraction**: BigQuery for `create_account` operations; API pipeline with Stellar Expert fallback.
- **Comprehensive Child Account Discovery**: BigQuery pipeline discovers up to 100,000 child accounts with pagination and deduplication.
- **Caching**: 12-hour caching for Stellar address searches. Optimized API endpoint caching with 30s TTL for pending accounts.
- **Frontend Interactivity**: Django templates enhanced with Vue.js components for real-time updates and JSON viewing.
- **Performance Optimizations**: 30s polling intervals (reduced from 15s) with Page Visibility API to pause when tab is inactive. Account lineage API eliminates Cassandra full-table scans by building hierarchy from in-memory lineage sets. Proper cleanup of event listeners to prevent memory leaks.

## Security and Monitoring
- **Comprehensive Testing**: 180+ tests across 45+ test files using pytest with markers. Includes performance, regression, integration, and unit tests. Tests cover security, functionality, visualization controls, monitoring, BigQuery caching, API optimizations, Query Builder schema parity, Vue component initialization, and database integration.
- **Input Validation**: Multi-layer validation for Stellar addresses.
- **Injection Prevention**: Robust measures against various injection types.
- **API Security**: CSRF protection, Content-Type validation, query parameter security, and HTTP security headers.
- **Configuration Security**: Secrets managed via environment variables, secure Django defaults, and HTTPS enforcement.
- **Production Settings**: Dedicated `production.py` for best practices.
- **Error Tracking**: Sentry integration for error monitoring.
- **Security Auditing**: Regular `pip-audit` checks and documented vulnerabilities.

## Open Source & CI/CD
- **License**: MIT License.
- **Documentation**: `CONTRIBUTING.md`, `SECURITY.md`, `TESTING.md`, and `USER_GUIDE.md`.
- **User Guide**: Comprehensive user guide with screenshots and examples for all features.
- **GitHub Actions**: Automated CI workflow for testing, linting, and security audits.
- **Environment Configuration**: `.env.example` for easy setup.
- **Startup Script**: `startup.sh` provides guidance for workflow restarts after ENV secret changes.

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