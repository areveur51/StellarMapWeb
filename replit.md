# Overview

StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API and Stellar Expert, stores this data in Astra DB (Cassandra), and renders it as interactive D3.js radial tree diagrams. The project aims to provide users with a clear, interactive "family tree" view of how Stellar accounts are created and interconnected, offering insights into the network's structure and activity. The application features a fast, optimized data collection pipeline, robust address validation, and a user-friendly interface with real-time pending account tracking and graceful error handling.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design and UI/UX
- **Interactive Radial Tree Diagrams**: Utilizes D3.js for visualizing Stellar account lineage.
- **Responsive Design**: Bootstrap-based frontend for adaptive layouts.
- **Real-time Feedback**: Displays pending accounts and pipeline stage progress using Vue.js for immediate user feedback.
- **Consistent Theming**: Replit cyberpunk theme applied across the application and architecture diagrams.

## Technical Implementation
- **Django Framework**: Built on Django 4.2.7 with a multi-app structure (`apiApp`, `webApp`, `radialTidyTreeApp`).
- **Database Management**: Astra DB (Cassandra) for production, SQLite for development. Custom `DatabaseAppsRouter` for database routing. Cassandra models utilize composite primary keys for efficient querying.
- **Fast Data Collection Pipeline**: An 8-stage sequential pipeline runs every 2 minutes, processing an address in 2-3 minutes. Includes automated execution, comprehensive workflow tracking (18 status constants), health monitoring, and stuck record recovery.
- **API Integration**: Asynchronous interactions with Horizon API and Stellar Expert, using `Tenacity` for robust retries with exponential backoff.
- **Caching**: 12-hour caching for Stellar address searches to minimize API calls.
- **Frontend Interactivity**: Django templates enhanced with Vue.js components, including a polling system for real-time updates and an interactive JSON viewer for detailed stage execution data.

## Security and Monitoring
- **Comprehensive Testing**: 122+ tests cover security (injection prevention, validation), functionality, and monitoring.
- **Input Validation**: Multi-layer validation for Stellar addresses, including regex, cryptographic checks, and Horizon API 404 validation.
- **Injection Prevention**: Robust measures against NoSQL injection, XSS, command injection, and path traversal.
- **API Security**: CSRF protection, Content-Type validation, query parameter security, and HTTP security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP, HSTS).
- **Configuration Security**: Secrets managed via environment variables (Replit Secrets, `python-decouple`), secure Django defaults (DEBUG=False, ALLOWED_HOSTS), and HTTPS enforcement.
- **Error Tracking**: Sentry integration for error monitoring.

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

## Frontend Dependencies
- **D3.js**: Data visualization.
- **Vue.js**: Interactive UI.
- **Bootstrap**: CSS framework.
- **jQuery**: JavaScript library.