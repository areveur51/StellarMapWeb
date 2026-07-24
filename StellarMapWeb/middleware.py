"""
Access model for StellarMapWeb on NAS:

- Public (no login): search, trees, dashboard view, read-only APIs, health
- Managers only (Tailscale QR allowlist → Django staff): /admin/, management APIs
"""
from __future__ import annotations

import re
from urllib.parse import quote

from django.http import JsonResponse
from django.shortcuts import redirect

from apiApp.helpers.tailscale_auth import user_is_manager

# Prefixes that require a manager session
MANAGER_PATH_PREFIXES = (
    "/admin/",
    "/login/",  # login itself is public; handled separately below
)

# API paths that mutate state or expose ops data — managers only
MANAGER_API_EXACT = {
    "/api/retry-failed-account/",
    "/api/refresh-enrichment/",
    "/api/bulk-queue-accounts/",
    "/api/cassandra-query/",
    "/api/server-logs/",
    "/api/error-logs/",
}

# Always public
PUBLIC_PREFIXES = (
    "/health/",
    "/static/",
    "/api/heartbeat/",
    "/api/auth/",
    "/api/pending-accounts/",
    "/api/stage-executions/",
    "/api/account-lineage/",
    "/api/lineage-with-siblings/",
    "/api/fetch-toml/",
    "/api/pipeline-stats/",
    "/api/",  # only if not in MANAGER_API — checked carefully
    "/search",
    "/dashboard",
    "/tree/",
    "/web/",
)


def _wants_json(request) -> bool:
    accept = request.META.get("HTTP_ACCEPT") or ""
    return "application/json" in accept or request.path.startswith("/api/")


class ManagerGateMiddleware:
    """
    Enforce manager auth on admin + management APIs.
    Public search/read stays open for all visitors (LAN/Tailscale network).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Auth endpoints + login pages are always reachable
        if path.startswith("/api/auth/") or path in ("/login", "/login/") or path.startswith("/login/"):
            return self.get_response(request)

        # Public health
        if path.startswith("/health"):
            return self.get_response(request)

        needs_manager = False
        if path.startswith("/admin"):
            needs_manager = True
        elif path in MANAGER_API_EXACT:
            needs_manager = True

        if needs_manager:
            user = getattr(request, "user", None)
            if not user_is_manager(user):
                # After login land on admin home, not /admin/login/
                dest = (
                    "/admin/"
                    if path.startswith("/admin/login")
                    else request.get_full_path()
                )
                next_q = quote(dest)
                if _wants_json(request):
                    return JsonResponse(
                        {
                            "error": "manager_login_required",
                            "message": "StellarMapWeb management requires Tailscale manager login.",
                            "login": f"/login/?next={next_q}",
                        },
                        status=401,
                    )
                return redirect(f"/login/?next={next_q}")

        return self.get_response(request)
