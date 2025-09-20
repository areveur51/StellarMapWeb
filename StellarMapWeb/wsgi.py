# StellarMapWeb/wsgi.py
"""
WSGI config for StellarMapWeb.

Exposes WSGI callable as 'application'.
For deployment: https://docs.djangoproject.com/en/4.0/howto/deployment/wsgi/

Efficiency: Standard minimal setup.
Security: Uses os.environ for settings; ensure env vars secure.
"""

import os
from django.core.wsgi import get_wsgi_application

# Set Django settings module securely via env var
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StellarMapWeb.settings')

application = get_wsgi_application()
