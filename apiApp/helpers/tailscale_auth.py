"""
Tailscale QR challenge store + Django user/session login for managers only.

Search / public UI stays anonymous. Staff/superuser is granted only to
TAILSCALE_ALLOW_LOGINS identities.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.models import User

from apiApp.helpers.tailscale_whois import TailscaleWhois, is_login_allowed

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_challenges: Dict[str, "Challenge"] = {}


def qr_ttl_ms() -> int:
    raw = int(os.environ.get("TAILSCALE_QR_TTL_MS") or getattr(settings, "TAILSCALE_QR_TTL_MS", 90000) or 90000)
    return max(30_000, min(180_000, raw))


def auth_modes() -> list:
    mode = (
        os.environ.get("AUTH_MODE")
        or getattr(settings, "AUTH_MODE", "tailscale-qr")
        or "tailscale-qr"
    ).lower()
    return [p for p in re.split(r"[,\s]+", mode) if p]


def is_tailscale_qr_enabled() -> bool:
    parts = auth_modes()
    if any(p in ("tailscale-qr", "ts-qr", "tailscale") for p in parts):
        return True
    if any(p in ("local", "dev") for p in parts):
        return os.environ.get("TAILSCALE_QR", "1").lower() not in ("0", "false", "off")
    return False


def is_local_login_enabled() -> bool:
    return any(p in ("local", "dev") for p in auth_modes())


@dataclass
class Challenge:
    id: str
    created_at: float
    expires_at: float
    desktop_session_key: str
    status: str = "pending"  # pending | approved | consumed | expired
    approver: Optional[TailscaleWhois] = None


def _prune() -> None:
    now = time.time()
    dead = []
    for cid, ch in _challenges.items():
        if ch.expires_at < now and ch.status == "pending":
            ch.status = "expired"
        if ch.status == "consumed" or ch.expires_at < now - 60:
            dead.append(cid)
    for cid in dead:
        _challenges.pop(cid, None)


def new_challenge(desktop_session_key: str) -> Challenge:
    with _lock:
        _prune()
        cid = secrets.token_urlsafe(18)
        now = time.time()
        ch = Challenge(
            id=cid,
            created_at=now,
            expires_at=now + qr_ttl_ms() / 1000.0,
            desktop_session_key=desktop_session_key or "",
            status="pending",
        )
        _challenges[cid] = ch
        return ch


def get_challenge(cid: str) -> Optional[Challenge]:
    with _lock:
        _prune()
        ch = _challenges.get(cid or "")
        if not ch:
            return None
        if ch.status == "pending" and ch.expires_at < time.time():
            ch.status = "expired"
        return ch


def public_base_url(request) -> str:
    env = (os.environ.get("PUBLIC_BASE_URL") or getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/")
    if env:
        return env
    proto = request.META.get("HTTP_X_FORWARDED_PROTO") or ("https" if request.is_secure() else "http")
    host = request.META.get("HTTP_X_FORWARDED_HOST") or request.get_host()
    return f"{proto}://{host}"


def username_from_login(login_name: str) -> str:
    # Django username max 150; prefer email local-part + safe chars
    base = login_name.strip().lower()
    if "@" in base:
        local, _, domain = base.partition("@")
        base = f"{local}_{domain.replace('.', '_')}"
    base = re.sub(r"[^a-z0-9_@.+-]", "_", base)[:140]
    return base or "tailscale_user"


def ensure_manager_user(whois: TailscaleWhois) -> User:
    """Create/update a staff superuser for an allowlisted Tailscale identity."""
    if not is_login_allowed(whois.login_name):
        raise PermissionError(f"{whois.login_name} is not on TAILSCALE_ALLOW_LOGINS")

    email = whois.login_name if "@" in whois.login_name else f"{whois.login_name}@tailscale.local"
    UserModel = get_user_model()
    user = UserModel.objects.filter(email__iexact=email).first()
    if not user:
        uname = username_from_login(whois.login_name)
        # avoid collisions
        candidate = uname
        n = 1
        while UserModel.objects.filter(username=candidate).exists():
            candidate = f"{uname}_{n}"[:150]
            n += 1
        user = UserModel(username=candidate, email=email)
        user.set_unusable_password()

    parts = (whois.display_name or whois.login_name).split()
    user.first_name = (parts[0] if parts else "Tailscale")[:150]
    user.last_name = (" ".join(parts[1:]) if len(parts) > 1 else "Manager")[:150]
    user.email = email
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()
    return user


def login_manager(request, whois: TailscaleWhois) -> User:
    user = ensure_manager_user(whois)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["tailscale_login"] = whois.login_name
    request.session["tailscale_node"] = whois.node_name
    request.session["auth_via"] = "tailscale-qr"
    request.session.set_expiry(
        int(getattr(settings, "SESSION_IDLE_HOURS", 8) or 8) * 3600
    )
    logger.info(
        "[AUTH] manager login %s node=%s",
        whois.login_name,
        whois.node_name,
    )
    return user


def user_is_manager(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    # Also honor allowlist email match
    email = (getattr(user, "email", "") or "").lower()
    ts = ""
    return bool(email and is_login_allowed(email))
