# Overview
StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API, Stellar Expert, and Google BigQuery, stores this data in Astra DB (Cassandra), and renders it as interactive D3.js radial tree diagrams. The project aims to provide a comprehensive and cost-effective solution for exploring Stellar account relationships, with a focus on UI/UX, performance, and scalability. It includes features for identifying High-Value Accounts and offers a multi-theme interface.

# User Preferences
- Preferred communication style: Simple, everyday language.
- Keep Replit usage anonymous - do not mention Replit in public documentation
- Prompt attachments go to temp/ directory (gitignored), not attached_assets/

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
- **System-Wide Glow Effects**: Comprehensive cyberpunk glow treatments on all interactive elements using a consistent color palette.
- **Dashboard Layout**: Alerts & Recommendations are prioritized at the top for immediate visibility.
- **Architecture Diagrams**: 5 PlantUML diagrams are used for documentation.

## Technical Implementation
- **Django Framework**: Built on Django 5.0.2 with a multi-app structure (`apiApp`, `webApp`, `radialTidyTreeApp`).
- **Database Management**: Astra DB (Cassandra) for production, SQLite for development, with a custom `DatabaseAppsRouter`. Cassandra models use composite primary keys.
- **Environment-Aware Model Loading**: `apiApp/model_loader.py` dynamically imports Cassandra or SQLite models based on the environment.
- **Django Admin Integration**: Full integration of Cassandra models with workarounds for query constraints.
- **Docker Deployment**: Cross-platform Docker Compose setup for development and production, including automatic migrations.
- **BigQuery-Based Data Collection**: Primary pipeline uses Stellar's BigQuery/Hubble dataset for lineage, with an age restriction for instant queries (<1 year old accounts). Cost optimization strategies include permanent Cassandra storage after first query, consolidated CTE-based queries, and `BigQueryCostGuard` for cost and size limits. An Admin Configuration Panel allows dynamic adjustment of pipeline settings. Includes an API fallback mechanism if BigQuery limits are exceeded.
- **API-Based Fast Pipeline**: An alternative 8-stage pipeline using Horizon API and Stellar Expert for educational purposes, providing comprehensive workflow tracking.
- **API Integration**: Asynchronous interactions with Horizon API and Stellar Expert, utilizing `Tenacity` for robust retries.
- **Two-Tier Creator Extraction**: BigQuery for `create_account` operations; API pipeline with Stellar Expert fallback.
- **Comprehensive Child Account Discovery**: BigQuery pipeline discovers up to 100,000 child accounts with pagination and deduplication.
- **Caching**: 12-hour caching for Stellar address searches.
- **Frontend Interactivity**: Django templates enhanced with Vue.js components for real-time updates and JSON viewing.

## Security and Monitoring
- **Comprehensive Testing**: 134+ tests cover security, functionality, visualization controls, and monitoring. Includes 12 spacing slider tests.
- **Input Validation**: Multi-layer validation for Stellar addresses.
- **Injection Prevention**: Robust measures against various injection types.
- **API Security**: CSRF protection, Content-Type validation, query parameter security, and HTTP security headers.
- **Configuration Security**: Secrets managed via environment variables, secure Django defaults, and HTTPS enforcement.
- **Production Settings**: Dedicated `production.py` for best practices.
- **Error Tracking**: Sentry integration for error monitoring.
- **Security Auditing**: Regular `pip-audit` checks and documented vulnerabilities.

## Open Source & CI/CD
- **License**: MIT License.
- **Documentation**: `CONTRIBUTING.md` and `SECURITY.md`.
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