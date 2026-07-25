"""Template context shared across pages (NAS light-mode poll cadence, etc.)."""
from django.conf import settings


def nas_runtime(request):
    is_manager = False
    try:
        from apiApp.helpers.tailscale_auth import user_is_manager

        is_manager = user_is_manager(getattr(request, 'user', None))
    except Exception:
        pass
    poll_ms = getattr(settings, 'POLL_INTERVAL_MS', 30000)
    search_poll = getattr(settings, 'NEAR_RT_SEARCH_POLL_MS', poll_ms)
    return {
        'poll_interval_ms': poll_ms,
        'search_poll_interval_ms': search_poll,
        'near_rt_enabled': getattr(settings, 'NEAR_RT_ENABLED', False),
        'light_mode': getattr(settings, 'LIGHT_MODE', False),
        'is_manager': is_manager,
        'manager_login_url': '/login/',
        'cassandra_read_only': getattr(settings, 'CASSANDRA_READ_ONLY', False),
        'use_cassandra': getattr(settings, 'USE_CASSANDRA', False),
        'can_queue_lineage': (
            not getattr(settings, 'CASSANDRA_READ_ONLY', False)
        ),
    }
