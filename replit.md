# Overview

StellarMapWeb is a Django application for visualizing Stellar blockchain lineage data using D3.js radial tree diagrams. The system tracks account creation relationships across the Stellar network, collecting data from Horizon API and Stellar Expert, then storing it in Astra DB (Cassandra) for visualization. Users can input Stellar addresses to generate interactive family tree-style visualizations showing how accounts were created and their relationships.

# Recent Changes

## September 21, 2025
- Successfully resolved complex dependency chain from new webApp/views.py file
- Installed missing packages: pandas, stellar-sdk  
- Added required environment variables for Astra DB integration
- Fixed import chain: StellarMapCreatorAccountLineageHelpers → sm_horizon → stellar_sdk
- Created missing sm_cron.py helper module for cron job management
- Resolved syntax errors and indentation issues in helper files
- Django Server workflow running successfully on port 5000

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Framework and Structure
- **Django 4.2.7** with a multi-app architecture consisting of three main applications:
  - `apiApp`: Core API functionality and data management
  - `webApp`: Main web interface for user interactions
  - `radialTidyTreeApp`: Specialized visualization components

## Database Architecture
- **Primary Storage**: Astra DB (DataStax Cassandra) for production data storage
- **Local Development**: SQLite fallback for development environments
- **Database Routing**: Custom router (`DatabaseAppsRouter`) directs different apps to appropriate databases
- **ORM**: Mix of Django ORM and django-cassandra-engine for Cassandra integration

## Data Collection Pipeline
- **Asynchronous Processing**: Extensive use of async/await patterns for API calls
- **Scheduled Tasks**: Django management commands with cron scheduling for automated data collection
- **API Integration**: 
  - Horizon API for Stellar blockchain data
  - Stellar Expert API for enhanced account information
- **Retry Logic**: Tenacity library provides robust retry mechanisms for API failures
- **Rate Limiting**: Staggered cron jobs prevent API rate limit violations

## Frontend Architecture
- **Templating**: Django templates with Vue.js components for interactive elements
- **Visualization**: D3.js for radial tree rendering
- **Responsive Design**: Bootstrap-based responsive interface
- **Component System**: Modular Vue.js components for reusable UI elements

## Security and Monitoring
- **Environment Configuration**: Decouple library for secure environment variable management
- **Error Tracking**: Sentry integration for comprehensive error monitoring
- **Input Validation**: Stellar SDK for cryptographic address validation
- **HTTPS Enforcement**: Production settings enforce SSL/TLS

## Cron Job Architecture
- **Health Monitoring**: Dedicated health check system monitors cron job status
- **Sequential Processing**: Jobs are staggered to prevent resource conflicts
- **Status Tracking**: Each job tracks its progress through defined status states
- **Automatic Recovery**: Health check system can reset unhealthy jobs after timeout periods

# External Dependencies

## Blockchain APIs
- **Horizon API**: Official Stellar network API for transaction and account data
- **Stellar Expert**: Third-party service for enhanced Stellar network insights and directory information

## Database Services
- **Astra DB**: DataStax managed Cassandra service for production data storage
- **Cassandra**: Distributed NoSQL database for handling large-scale lineage data

## Monitoring and Development
- **Sentry**: Error tracking and performance monitoring service
- **Replit**: Cloud development and deployment platform

## Key Libraries
- **stellar-sdk**: Official Python SDK for Stellar blockchain interactions
- **django-cassandra-engine**: Django integration for Cassandra databases
- **tenacity**: Retry library for robust API interactions
- **pandas**: Data manipulation and analysis for lineage processing
- **requests**: HTTP library for API communications
- **aiohttp**: Asynchronous HTTP client for efficient API calls

## Frontend Dependencies
- **D3.js**: Data visualization library for radial tree rendering
- **Vue.js**: Progressive JavaScript framework for interactive components
- **Bootstrap**: CSS framework for responsive design
- **jQuery**: JavaScript library for DOM manipulation (legacy admin interface)