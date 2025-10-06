# Overview

StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API and Stellar Expert, stores this data in Astra DB (Cassandra), and then renders it as interactive D3.js radial tree diagrams. The project aims to provide users with a clear, interactive "family tree" view of how Stellar accounts are created and interconnected, offering insights into the network's structure and activity.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Framework and Structure
- **Django 4.2.7** with a multi-app architecture: `apiApp` (API/data management), `webApp` (user interface), and `radialTidyTreeApp` (visualization components).

## Database Architecture
- **Primary Storage**: Astra DB (DataStax Cassandra) for production, utilizing `django-cassandra-engine`.
- **Local Development**: SQLite for local environments.
- **Database Routing**: Custom `DatabaseAppsRouter` for directing apps to appropriate databases.
- **ORM**: Combines Django ORM with direct Cassandra integration.
- **Schema Design**: Cassandra models are designed with explicit composite primary keys and clustering keys for efficient querying, including timestamp management (`created_at`, `updated_at`).
- **Caching**: Implemented a 12-hour caching strategy for Stellar address searches using `StellarAccountSearchCache` to minimize API calls and improve performance.

## Data Collection Pipeline
- **Asynchronous Processing**: Extensive use of async/await for API interactions.
- **Scheduled Tasks**: Django management commands with cron scheduling for automated data collection.
- **API Integration**: Uses Horizon API for core Stellar data and Stellar Expert for enhanced account information.
- **Retry Logic**: `Tenacity` library ensures robust API calls.
- **Rate Limiting**: Staggered cron jobs prevent API rate limit violations.
- **Workflow Management**: Comprehensive PlantUML-based cron workflow with 17 status constants (`PENDING`, `IN_PROGRESS`, `DONE` states) for tracking data collection and processing.

## Frontend Architecture
- **Templating**: Django templates enhanced with Vue.js components for interactivity.
- **Visualization**: D3.js is used for rendering radial tree diagrams.
- **Responsive Design**: Bootstrap-based interface.
- **Component System**: Modular Vue.js components for reusable UI elements, including dedicated tabs for Search Cache and Account Lineage data display.

## Security and Monitoring
- **Environment Configuration**: `Decouple` library for secure environment variable management (e.g., `CASSANDRA_KEYSPACE`).
- **Error Tracking**: Sentry integration for comprehensive error monitoring.
- **Input Validation**: Stellar SDK for cryptographic address validation.
- **HTTPS Enforcement**: Production settings enforce SSL/TLS.

## Cron Job Architecture
- **Health Monitoring**: Dedicated system monitors cron job status.
- **Sequential Processing**: Jobs are staggered to prevent resource conflicts.
- **Status Tracking**: Each job tracks its progress through defined status states via `ManagementCronHealth` model.

# External Dependencies

## Blockchain APIs
- **Horizon API**: Official Stellar network API.
- **Stellar Expert**: Third-party service for Stellar network insights.

## Database Services
- **Astra DB**: DataStax managed Cassandra service.
- **Cassandra**: Distributed NoSQL database.

## Monitoring and Development
- **Sentry**: Error tracking and performance monitoring.
- **Replit**: Cloud development and deployment platform.

## Key Libraries
- **stellar-sdk**: Python SDK for Stellar blockchain.
- **django-cassandra-engine**: Django integration for Cassandra.
- **tenacity**: Retry library.
- **pandas**: Data manipulation.
- **requests**: HTTP library.
- **aiohttp**: Asynchronous HTTP client.

## Frontend Dependencies
- **D3.js**: Data visualization library.
- **Vue.js**: JavaScript framework.
- **Bootstrap**: CSS framework.
- **jQuery**: JavaScript library.