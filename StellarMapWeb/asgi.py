# StellarMapWeb/asgi.py
"""
ASGI config for StellarMapWeb.

Exposes ASGI callable as 'application'.
For deployment: https://docs.djangoproject.com/en/4.0/howto/deployment/asgi/

Efficiency: Standard minimal setup.
Security: Uses os.environ for settings; ensure env vars secure.
"""

import os
from django.core.asgi import get_asgi_application

# Set Django settings module securely via env var
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StellarMapWeb.settings')

application = get_asgi_application()
