# StellarMapWeb

Complete Django app for Stellar lineage visualization with D3 radial trees, Astra DB storage.

## Replit Deployment
1. Create Python Repl, upload files.
2. Shell: pip install -r requirements.txt
3. Secrets: DJANGO_SECRET_KEY (generate), DEBUG=True, ASTRA_DB_* vars, CLIENT_ID/SECRET, APP_PATH, SENTRY_DSN.
4. Run: Auto-runs migrate/server via .replit.
5. Access: Webview, input address/network for tree.

## Local
1. Set env vars.
2. pip install -r requirements.txt
3. python manage.py migrate
4. python manage.py runserver

## Tests
python manage.py test

