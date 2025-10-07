# StellarMapWeb

StellarMapWeb is a Django application designed to visualize Stellar blockchain lineage data. It collects account creation relationships from the Horizon API and Stellar Expert, stores this data in Astra DB (Cassandra), and then renders it as interactive D3.js radial tree diagrams. The project provides users with a clear, interactive "family tree" view of how Stellar accounts are created and interconnected, offering insights into the network's structure and activity.

## Key Features

- **Fast Pipeline**: 2-3 minute processing time per address with 8 sequential stages
- **Real-time Monitoring**: Live progress tracking via Stages tab with auto-refresh
- **Interactive Visualization**: D3.js radial tree diagrams with Vue.js enhancements
- **Robust Validation**: Multi-layer Stellar address validation with terminal status handling
- **Comprehensive Security**: 122+ tests covering injection prevention, XSS, CSRF, and more
- **Auto-recovery**: Automatic stuck record detection and recovery system
- **Health Monitoring**: Cron health tracking with rate-limit recovery

## Quick Start

### Replit Deployment
1. Create Python Repl and upload files
2. Install dependencies: `pip install -r requirements.txt`
3. Configure Secrets:
   - `DJANGO_SECRET_KEY` (generate secure key)
   - `DEBUG=True` (development only)
   - `ASTRA_DB_TOKEN`, `CASSANDRA_DB_NAME`, `CASSANDRA_KEYSPACE`
   - `SENTRY_DSN` (optional)
4. Run: Auto-runs migrate/server via `.replit` config
5. Access via Webview and input Stellar address

### Local Development
```bash
# Set environment variables
export DJANGO_SECRET_KEY="your-secret-key"
export ASTRA_DB_TOKEN="your-token"
# ... other env vars

# Install and run
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:5000
```

### Run Tests
```bash
python manage.py test
```

---

## System Architecture

### Framework and Structure
- **Django 4.2.7** with multi-app architecture:
  - `apiApp`: API and data management
  - `webApp`: User interface
  - `radialTidyTreeApp`: Visualization components

### Database Architecture
- **Primary Storage**: Astra DB (DataStax Cassandra) for production
- **Local Development**: SQLite
- **ORM**: Django ORM + `django-cassandra-engine`
- **Schema**: Composite primary keys and clustering keys
- **Caching**: 12-hour strategy via `StellarAccountSearchCache`

### Data Collection Pipeline

#### Fast Pipeline (2-3 minutes/address)
- **8 Sequential Stages**:
  1. Make Parent Lineage
  2. Collect Horizon Data
  3. Collect Account Attributes
  4. Collect Account Assets
  5. Collect Account Flags
  6. Collect SE Directory
  7. Collect Account Creator
  8. Make Grandparent Lineage

#### Status Management
- **18