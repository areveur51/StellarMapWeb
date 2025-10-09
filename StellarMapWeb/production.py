"""
Production settings for StellarMapWeb with Cloudflare integration.
Inherit from base settings and override for production security.
"""

from .settings import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

# Cloudflare and production hosts
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')

# Trust Cloudflare proxy headers for HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Security settings
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Session and CSRF security
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# X-Frame-Options
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Cloudflare IP addresses (for getting real client IP)
# These are Cloudflare's IP ranges - update if needed
CLOUDFLARE_IPS = [
    '173.245.48.0/20',
    '103.21.244.0/22',
    '103.22.200.0/22',
    '103.31.4.0/22',
    '141.101.64.0/18',
    '108.162.192.0/18',
    '190.93.240.0/20',
    '188.114.96.0/20',
    '197.234.240.0/22',
    '198.41.128.0/17',
    '162.158.0.0/15',
    '104.16.0.0/13',
    '104.24.0.0/14',
    '172.64.0.0/13',
    '131.0.72.0/22',
]

# Get real IP from X-Forwarded-For header (behind Cloudflare/Nginx)
# django-ratelimit will use this to get the real client IP
def get_real_ip(request):
    """Get real client IP from Cloudflare headers"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# Configure django-ratelimit to use real IP
# Note: For multi-instance deployments, use Redis/Memcached for shared rate limiting
RATELIMIT_USE_CACHE = 'default'

# Static files (WhiteNoise for production)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'django_production.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Cache configuration (for rate limiting)
# Use Redis for cluster-wide rate limiting (recommended for production)
# Set REDIS_URL env var or use default

import os

REDIS_URL = os.environ.get('REDIS_URL', None)

if REDIS_URL:
    # Redis cache (cluster-wide rate limiting)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
    print(f"✅ Using Redis cache for cluster-wide rate limiting: {REDIS_URL}")
else:
    # LocMemCache fallback (SINGLE INSTANCE ONLY)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'stellarmapweb-cache',
            'OPTIONS': {
                'MAX_ENTRIES': 10000
            }
        }
    }
    print("⚠️  WARNING: Using LocMemCache (single instance only)")
    print("⚠️  For load balancing, set REDIS_URL environment variable")

# Admin site customization
ADMIN_URL = config('ADMIN_URL', default='admin/')

print("✅ Production settings loaded with Cloudflare integration")
