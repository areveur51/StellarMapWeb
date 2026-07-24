"""HTTP endpoints for Tailscale QR / direct manager login."""
from __future__ import annotations

import logging

from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apiApp.helpers.tailscale_auth import (
    get_challenge,
    is_local_login_enabled,
    is_tailscale_qr_enabled,
    login_manager,
    new_challenge,
    public_base_url,
    qr_ttl_ms,
    user_is_manager,
)
from apiApp.helpers.tailscale_whois import is_login_allowed, resolve_client_identity

logger = logging.getLogger(__name__)


def _session_key(request) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key or ""


@ensure_csrf_cookie
@require_GET
def login_page(request):
    """Manager login (Tailscale QR). Public search does not require this."""
    next_url = request.GET.get("next") or "/admin/"
    if request.user.is_authenticated and user_is_manager(request.user):
        return redirect(next_url)
    return render(
        request,
        "webApp/login.html",
        {
            "next_url": next_url,
            "auth_mode": "tailscale-qr" if is_tailscale_qr_enabled() else "disabled",
            "allow_local": is_local_login_enabled(),
            "qr_enabled": is_tailscale_qr_enabled(),
        },
    )


@require_GET
def login_qr_page(request):
    """Phone approve page for QR challenge (?c=...)."""
    return render(
        request,
        "webApp/login_qr_approve.html",
        {"challenge_id": request.GET.get("c") or ""},
    )


@require_GET
def auth_status(request):
    return JsonResponse(
        {
            "authenticated": bool(
                request.user.is_authenticated and user_is_manager(request.user)
            ),
            "mode": "tailscale-qr" if is_tailscale_qr_enabled() else "none",
            "allowLocalLogin": is_local_login_enabled(),
            "directLogin": True,
            "user": (
                {
                    "username": request.user.username,
                    "email": request.user.email,
                    "is_staff": request.user.is_staff,
                }
                if request.user.is_authenticated
                else None
            ),
            "publicAccess": "search and read-only UI do not require login",
            "managerAccess": "Tailscale allowlist only (admin / management APIs)",
        }
    )


@require_POST
def qr_start(request):
    if not is_tailscale_qr_enabled():
        return JsonResponse({"message": "Tailscale QR auth is disabled"}, status=503)
    ch = new_challenge(_session_key(request))
    request.session["qr_desktop"] = True
    base = public_base_url(request)
    approve_path = f"/login/qr?c={ch.id}"
    return JsonResponse(
        {
            "challengeId": ch.id,
            "expiresIn": int(qr_ttl_ms() / 1000),
            "expiresAt": int(ch.expires_at * 1000),
            "approveUrl": f"{base}{approve_path}",
            "approvePath": approve_path,
        }
    )


@require_GET
def qr_status(request):
    ch = get_challenge(str(request.GET.get("c") or ""))
    if not ch:
        return JsonResponse({"status": "missing"}, status=404)
    if ch.desktop_session_key and ch.desktop_session_key != _session_key(request):
        return JsonResponse({"status": "wrong_session"}, status=403)
    payload = {
        "status": ch.status,
        "expiresAt": int(ch.expires_at * 1000),
    }
    if ch.approver and ch.status != "pending":
        payload["approver"] = {
            "loginName": ch.approver.login_name,
            "displayName": ch.approver.display_name,
            "nodeName": ch.approver.node_name,
        }
    return JsonResponse(payload)


@require_GET
def qr_info(request):
    ch = get_challenge(str(request.GET.get("c") or ""))
    if not ch:
        return JsonResponse({"message": "Challenge not found or expired"}, status=404)
    if ch.status != "pending" or ch.expires_at < __import__("time").time():
        return JsonResponse(
            {
                "message": "Challenge expired or already used",
                "status": "expired" if ch.status == "pending" else ch.status,
            },
            status=410,
        )
    identity = resolve_client_identity(request)
    whois = identity.get("whois")
    ip = identity.get("ip")
    return JsonResponse(
        {
            "challengeId": ch.id,
            "expiresAt": int(ch.expires_at * 1000),
            "fromTailscale": identity.get("from_tailscale"),
            "clientIp": ip,
            "trustPath": identity.get("trust_path"),
            "identity": (
                {
                    "loginName": whois.login_name,
                    "displayName": whois.display_name,
                    "nodeName": whois.node_name,
                    "allowed": is_login_allowed(whois.login_name),
                }
                if whois
                else None
            ),
            "hint": (
                None
                if whois
                else (
                    "Server sees loopback (userspace Tailscale). Set TAILSCALE_ALLOW_LOGINS to exactly one manager email."
                    if ip in ("127.0.0.1", "::1", None)
                    else "Open via MagicDNS (…ts.net) with Tailscale ON on the phone."
                )
            ),
        }
    )


@csrf_exempt
@require_POST
def qr_approve(request):
    import json as _json
    import time as _time

    try:
        body = _json.loads(request.body.decode() or "{}")
    except Exception:
        body = {}
    c = str(body.get("c") or request.GET.get("c") or "")
    ch = get_challenge(c)
    if not ch:
        return JsonResponse({"message": "Challenge not found"}, status=404)
    if ch.status != "pending" or ch.expires_at < _time.time():
        return JsonResponse(
            {
                "message": "Challenge expired or already used",
                "status": "expired" if ch.status == "pending" else ch.status,
            },
            status=410,
        )
    identity = resolve_client_identity(request)
    whois = identity.get("whois")
    if not identity.get("from_tailscale") or not whois:
        return JsonResponse(
            {
                "message": "Could not resolve Tailscale identity. Use MagicDNS with Tailscale ON.",
                "clientIp": identity.get("ip"),
            },
            status=403,
        )
    if not is_login_allowed(whois.login_name):
        return JsonResponse(
            {
                "message": f"Tailscale user {whois.login_name} is not a StellarMapWeb manager (TAILSCALE_ALLOW_LOGINS).",
            },
            status=403,
        )
    ch.status = "approved"
    ch.approver = whois
    logger.info(
        "[AUTH] QR approved by %s node=%s", whois.login_name, whois.node_name
    )
    return JsonResponse(
        {
            "ok": True,
            "status": "approved",
            "identity": {
                "loginName": whois.login_name,
                "displayName": whois.display_name,
                "nodeName": whois.node_name,
            },
        }
    )


@require_POST
def qr_complete(request):
    import json as _json
    import time as _time

    try:
        body = _json.loads(request.body.decode() or "{}")
    except Exception:
        body = {}
    c = str(body.get("c") or "")
    ch = get_challenge(c)
    if not ch:
        return JsonResponse({"message": "Challenge not found"}, status=404)
    if ch.desktop_session_key and ch.desktop_session_key != _session_key(request):
        return JsonResponse(
            {"message": "Challenge belongs to another browser session"}, status=403
        )
    if ch.status != "approved" or not ch.approver:
        return JsonResponse(
            {"message": "Challenge not approved yet", "status": ch.status}, status=409
        )
    if ch.expires_at < _time.time():
        ch.status = "expired"
        return JsonResponse({"message": "Challenge expired"}, status=410)
    try:
        user = login_manager(request, ch.approver)
        ch.status = "consumed"
        return JsonResponse(
            {
                "ok": True,
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "is_staff": user.is_staff,
                },
            }
        )
    except Exception as e:
        logger.exception("[AUTH] QR complete failed")
        return JsonResponse({"message": f"Login failed: {str(e)[:160]}"}, status=500)


@require_POST
def tailscale_direct(request):
    """Same-device manager login (Continue on this device)."""
    if not is_tailscale_qr_enabled() and not is_local_login_enabled():
        return JsonResponse({"message": "Auth disabled"}, status=503)
    identity = resolve_client_identity(request)
    whois = identity.get("whois")
    if not identity.get("from_tailscale") or not whois:
        return JsonResponse(
            {
                "message": "Could not verify Tailscale identity. Open via MagicDNS (…ts.net) with Tailscale ON.",
                "clientIp": identity.get("ip"),
            },
            status=403,
        )
    if not is_login_allowed(whois.login_name):
        return JsonResponse(
            {
                "message": f"{whois.login_name} is not a manager (TAILSCALE_ALLOW_LOGINS).",
            },
            status=403,
        )
    try:
        user = login_manager(request, whois)
        return JsonResponse(
            {
                "ok": True,
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "is_staff": user.is_staff,
                },
                "trustPath": identity.get("trust_path"),
            }
        )
    except Exception as e:
        logger.exception("[AUTH] direct login failed")
        return JsonResponse({"message": f"Login failed: {str(e)[:160]}"}, status=500)


@require_http_methods(["GET", "POST"])
def logout_view(request):
    logout(request)
    if request.method == "GET" and "text/html" in (request.META.get("HTTP_ACCEPT") or ""):
        return redirect("/login/")
    return JsonResponse({"ok": True})
