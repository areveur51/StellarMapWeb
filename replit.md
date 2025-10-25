# Overview
StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API, Stellar Expert, and Google BigQuery, stores this data in Astra DB (Cassandra), and renders it as interactive D3.js radial tree diagrams. The project aims to provide a comprehensive and cost-effective solution for exploring Stellar account relationships, with a focus on UI/UX, performance, and scalability. Key features include identifying High-Value Accounts, a multi-theme interface, enhanced admin portal navigation, and a powerful Query Builder for Cassandra database exploration.

# User Preferences
- Preferred communication style: Simple, everyday language.
- Keep Replit usage anonymous - do not mention Replit in public documentation
- Prompt attachments go to temp/ directory (gitignored), not attached_assets/

# System Architecture

## System Design and UI/UX
- **Interactive Radial & Tidy Tree Diagrams**: Utilizes D3.js for visualizing Stellar account lineage with interactive radial and standard tidy tree layouts, featuring smart tooltips, scroll restoration, and dynamic radius calculation. Implements Mike Bostock's canonical radial tree approach with `.size([2π, radius])` for natural 360° distribution and compact radius calculation with no node overlaps. Uses fixed standard sizes (node: 9px, text: 17px) and 0.5x compactness factor to shorten child node lines for a compact, professional visualization. Features lineage-first positioning using **Fibonacci spiral** with golden angle (≈137.508°) for organic, natural flow - lineage nodes are positioned sequentially following the golden ratio before other nodes are distributed, creating a beautiful curved spiral pattern. Shortest-path link generation ensures lineage links always follow the minimal angular arc, never crossing the center. Includes sibling visualization in separated tabs with intelligent color coding and optimized spacing.
- **Tree Visualization Filters with Color Muting**: Interactive filters for issuer balance, asset balance, and "issuers only" criteria, applied to D3 visualizations using color muting instead of hiding nodes to preserve tree structure. Filter settings and slider increments persist via localStorage.
- **Tidy Tree Spacing Controls**: User-adjustable sliders for vertical spacing and min/max child distances (tidy tree only), with preferences persisting via localStorage and working across both /search and /tree pages.
- **Zoom & Pan Controls**: D3 zoom behavior with mouse wheel, click-drag, and control buttons.
- **Responsive Design & Theming**: Bootstrap-based frontend with adaptive layouts and a consistent cyberpunk theme, offering additional themes (Borg Green, Predator Red) with dynamic switching and persistence.
- **Modern UX Enhancements**: Gradient backgrounds, shimmer effects, pulsing indicators, smooth transitions, and glow effects, applied system-wide.
- **High Value Account (HVA) Leaderboard**: Identifies and ranks accounts based on configurable XLM thresholds with efficient filtering and event-based change tracking.
- **Query Builder**: Comprehensive Cassandra database explorer with pre-defined queries and a custom multi-filter builder, supporting network-aware filtering and adaptive `max_scan` limits.
- **Dashboard Design**: Optimized dashboard with high information density, prioritizing Alerts & Recommendations.
- **Architectural Documentation**: 10 PlantUML diagrams detailing system components, data flow, and architectural decisions.

## Technical Implementation
- **Django Framework**: Built on Django 5.0.2 with a multi-app structure.
- **Database Management**: Astra DB (Cassandra) for production, SQLite for development, with a custom `DatabaseAppsRouter` and environment-aware model loading. Cassandra models use composite primary keys and are fully integrated with Django Admin.
- **Dual-Pipeline Architecture**: Primary data collection via BigQuery-based pipeline with age restrictions and cost optimization (`BigQueryCostGuard`), and an API-based fast pipeline using Horizon API and Stellar Expert as fallback. Both pipelines automatically queue discovered creator and child accounts for continuous lineage graph expansion.
- **Unified Pipeline Configuration**: All pipeline settings consolidated into `BigQueryPipelineConfig` model, configurable via the admin panel.
- **Queue Synchronizer**: Automatic synchronization between Search Cache and Account Lineage tables to ensure all user searches are processed and data consistency is maintained.
- **API Integration**: Asynchronous interactions with Horizon API and Stellar Expert, utilizing `Tenacity` for robust retries.
- **Caching**: 12-hour caching for Stellar address searches and optimized API endpoint caching with 30s TTL for pending accounts.
- **Frontend Interactivity**: Django templates enhanced with Vue.js components for real-time updates.
- **Performance Optimizations**: 30s polling intervals with Page Visibility API and efficient lineage API to avoid full-table scans.
- **Security & Reliability**: Multi-layer input validation, injection prevention, API security (CSRF, Content-Type, query parameter security, HTTP headers), environment variable-based secret management, HTTPS enforcement, Sentry integration for error tracking, and regular `pip-audit` checks.
- **Deployment**: Docker Compose setup for development and production, configured for Reserved VM deployment to enable continuous background pipeline processing.
- **Comprehensive Testing**: 180+ tests across 45+ test files using pytest, covering security, functionality, and performance, including focused regression tests for core features and dashboard accuracy.

# External Dependencies

## Blockchain APIs
- Horizon API
- Stellar Expert
- Google BigQuery (for Stellar Hubble dataset)

## Database Services
- Astra DB (DataStax managed Cassandra)
- Cassandra

## Monitoring
- Sentry

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