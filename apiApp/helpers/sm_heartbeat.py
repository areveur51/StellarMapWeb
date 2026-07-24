"""
System heartbeat probes for internal and external dependencies.

Designed for constrained hosts (NAS / old laptop): short timeouts, no heavy
pipeline work, optional deps report as skipped when not configured.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


# Keep probes short so the dashboard stays usable on a NAS
HTTP_TIMEOUT_SEC = float(os.environ.get("HEARTBEAT_HTTP_TIMEOUT", "2.5"))
DB_TIMEOUT_HINT = float(os.environ.get("HEARTBEAT_DB_TIMEOUT", "2.0"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ms_since(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _probe(
    probe_id: str,
    name: str,
    group: str,
    status: str,
    latency_ms: int,
    detail: str = "",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "id": probe_id,
        "name": name,
        "group": group,
        "status": status,  # ok | warn | fail | skipped
        "latency_ms": latency_ms,
        "detail": detail,
        "meta": meta or {},
    }


def _http_get(url: str, timeout: float = HTTP_TIMEOUT_SEC, ok_codes: Optional[set] = None) -> Dict[str, Any]:
    """
    HTTP probe. By default any HTTP response (2xx–4xx) means the host is reachable.
    Connection/timeout errors are failures. ok_codes can narrow success if needed.
    """
    start = time.monotonic()
    req = Request(url, headers={"User-Agent": "StellarMapWeb-Heartbeat/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", None) or resp.getcode())
            body = resp.read(256)
            latency = _ms_since(start)
            if ok_codes is not None:
                ok = code in ok_codes
            else:
                # Reachability: 2xx–4xx = service answered (5xx = degraded)
                ok = 200 <= code < 500
            return {
                "ok": ok,
                "warn": 500 <= code < 600,
                "latency_ms": latency,
                "detail": f"HTTP {code}",
                "meta": {"http_status": code, "bytes": len(body)},
            }
    except HTTPError as e:
        code = int(e.code)
        latency = _ms_since(start)
        if ok_codes is not None:
            ok = code in ok_codes
        else:
            ok = 200 <= code < 500
        return {
            "ok": ok,
            "warn": 500 <= code < 600,
            "latency_ms": latency,
            "detail": f"HTTP {code}",
            "meta": {"http_status": code},
        }
    except (URLError, TimeoutError, OSError) as e:
        return {
            "ok": False,
            "warn": False,
            "latency_ms": _ms_since(start),
            "detail": str(getattr(e, "reason", e))[:160],
            "meta": {},
        }


def check_django_app() -> Dict[str, Any]:
    start = time.monotonic()
    try:
        from django.apps import apps

        labels = [a.label for a in apps.get_app_configs()]
        required = {"apiApp", "webApp"}
        missing = sorted(required - set(labels))
        latency = _ms_since(start)
        if missing:
            return _probe(
                "django",
                "Django apps",
                "internal",
                "fail",
                latency,
                f"Missing apps: {', '.join(missing)}",
            )
        return _probe(
            "django",
            "Django apps",
            "internal",
            "ok",
            latency,
            f"{len(labels)} apps loaded",
            {"apps": labels[:20]},
        )
    except Exception as e:
        return _probe("django", "Django apps", "internal", "fail", _ms_since(start), str(e)[:160])


def check_default_db() -> Dict[str, Any]:
    start = time.monotonic()
    try:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        vendor = connection.vendor
        tables = []
        try:
            tables = connection.introspection.table_names()[:30]
        except Exception:
            pass
        latency = _ms_since(start)
        status = "ok"
        detail = f"{vendor} OK"
        meta = {"vendor": vendor, "table_count": len(tables)}
        if vendor == "sqlite":
            if "django_migrations" not in tables:
                status = "warn"
                detail = "SQLite reachable but django_migrations missing"
        elif vendor == "postgresql":
            # Surface DB name for dashboard (no secrets)
            try:
                db_name = connection.settings_dict.get("NAME", "")
                host = connection.settings_dict.get("HOST", "")
                port = connection.settings_dict.get("PORT", "")
                detail = f"postgresql {db_name} @ {host}:{port}"
                meta.update({"name": db_name, "host": host, "port": str(port)})
            except Exception:
                pass
            if "django_migrations" not in tables:
                status = "warn"
                detail += " (migrations table missing)"
        return _probe(
            "database",
            "Default database",
            "internal",
            status,
            latency,
            detail,
            meta,
        )
    except Exception as e:
        return _probe(
            "database",
            "Default database",
            "internal",
            "fail",
            _ms_since(start),
            str(e)[:160],
        )


def check_django_cache() -> Dict[str, Any]:
    start = time.monotonic()
    try:
        from django.core.cache import cache

        key = "stellarmap_heartbeat_probe"
        token = f"hb-{int(time.time())}"
        cache.set(key, token, timeout=30)
        got = cache.get(key)
        latency = _ms_since(start)
        backend = settings.CACHES.get("default", {}).get("BACKEND", "unknown")
        short = backend.rsplit(".", 1)[-1]
        if got != token:
            return _probe(
                "cache",
                "Django cache",
                "internal",
                "fail",
                latency,
                f"set/get mismatch ({short})",
            )
        return _probe(
            "cache",
            "Django cache",
            "internal",
            "ok",
            latency,
            short,
            {"backend": backend},
        )
    except Exception as e:
        return _probe("cache", "Django cache", "internal", "fail", _ms_since(start), str(e)[:160])


def check_cassandra() -> Dict[str, Any]:
    """Astra/Cassandra — skipped when no token (lab SQLite mode)."""
    start = time.monotonic()
    token = (
        getattr(settings, "ASTRA_DB_TOKEN", None)
        or os.environ.get("ASTRA_DB_TOKEN")
        or ""
    ).strip()
    if not token or token.startswith("placeholder") or token.startswith("your-"):
        return _probe(
            "cassandra",
            "Astra / Cassandra",
            "internal",
            "skipped",
            0,
            "Not configured (SQLite lab mode)",
        )
    try:
        # Prefer existing connection path if django_cassandra_engine is installed
        from django.db import connections

        if "cassandra" not in connections:
            return _probe(
                "cassandra",
                "Astra / Cassandra",
                "internal",
                "warn",
                _ms_since(start),
                "Token set but no cassandra DB alias",
            )
        conn = connections["cassandra"]
        # Touch connection (may be lazy)
        conn.ensure_connection()
        return _probe(
            "cassandra",
            "Astra / Cassandra",
            "internal",
            "ok",
            _ms_since(start),
            "Connection alias ready",
        )
    except Exception as e:
        return _probe(
            "cassandra",
            "Astra / Cassandra",
            "internal",
            "fail",
            _ms_since(start),
            str(e)[:160],
        )


def check_redis() -> Dict[str, Any]:
    start = time.monotonic()
    redis_url = (os.environ.get("REDIS_URL") or getattr(settings, "REDIS_URL", "") or "").strip()
    if not redis_url:
        # LocMem / DB cache path — Redis not required
        return _probe(
            "redis",
            "Redis",
            "internal",
            "skipped",
            0,
            "REDIS_URL not set",
        )
    try:
        import redis  # type: ignore

        client = redis.from_url(redis_url, socket_connect_timeout=HTTP_TIMEOUT_SEC)
        pong = client.ping()
        latency = _ms_since(start)
        if pong:
            return _probe("redis", "Redis", "internal", "ok", latency, "PING ok")
        return _probe("redis", "Redis", "internal", "fail", latency, "PING failed")
    except Exception as e:
        return _probe("redis", "Redis", "internal", "fail", _ms_since(start), str(e)[:160])


def _status_from_http(result: Dict[str, Any]) -> str:
    if result.get("ok"):
        return "ok"
    if result.get("warn"):
        return "warn"
    return "fail"


def check_horizon(network: str = "public") -> Dict[str, Any]:
    if network == "testnet":
        url = "https://horizon-testnet.stellar.org/"
        probe_id = "horizon_testnet"
        name = "Horizon (testnet)"
    else:
        url = "https://horizon.stellar.org/"
        probe_id = "horizon_public"
        name = "Horizon (public)"
    result = _http_get(url)
    return _probe(
        probe_id,
        name,
        "external",
        _status_from_http(result),
        result["latency_ms"],
        result["detail"],
        {**result.get("meta", {}), "url": url},
    )


def check_stellar_expert() -> Dict[str, Any]:
    # Directory listing is a stable, lightweight API surface
    url = "https://api.stellar.expert/explorer/public/directory?limit=1"
    result = _http_get(url)
    return _probe(
        "stellar_expert",
        "Stellar Expert API",
        "external",
        _status_from_http(result),
        result["latency_ms"],
        result["detail"],
        {**result.get("meta", {}), "url": url},
    )


def check_bigquery() -> Dict[str, Any]:
    start = time.monotonic()
    # Skip when light mode and no credentials — still report configured state
    light = bool(getattr(settings, "LIGHT_MODE", False))
    creds = (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        or ""
    ).strip()
    if not creds and light:
        return _probe(
            "bigquery",
            "Google BigQuery",
            "external",
            "skipped",
            0,
            "No GCP credentials (optional in LIGHT_MODE)",
        )
    try:
        from apiApp.helpers.sm_bigquery import StellarBigQueryHelper

        helper = StellarBigQueryHelper()
        available = False
        if hasattr(helper, "is_available"):
            available = bool(helper.is_available())
        else:
            available = getattr(helper, "client", None) is not None
        latency = _ms_since(start)
        if available:
            return _probe(
                "bigquery",
                "Google BigQuery",
                "external",
                "ok",
                latency,
                "Client available",
            )
        return _probe(
            "bigquery",
            "Google BigQuery",
            "external",
            "skipped" if not creds else "warn",
            latency,
            "Client not available",
        )
    except Exception as e:
        # Import / init failure is common without GCP — not fatal for lab
        return _probe(
            "bigquery",
            "Google BigQuery",
            "external",
            "skipped" if not creds else "fail",
            _ms_since(start),
            str(e)[:160],
        )


def _summarize(probes: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {"ok": 0, "warn": 0, "fail": 0, "skipped": 0}
    for p in probes:
        st = p.get("status", "fail")
        if st in summary:
            summary[st] += 1
        else:
            summary["fail"] += 1
    return summary


def _overall_status(summary: Dict[str, int]) -> str:
    if summary.get("fail", 0) > 0:
        return "unhealthy"
    if summary.get("warn", 0) > 0:
        return "degraded"
    # All ok or skipped
    if summary.get("ok", 0) == 0 and summary.get("skipped", 0) > 0:
        return "degraded"
    return "healthy"


def run_heartbeat(include_external: bool = True) -> Dict[str, Any]:
    """
    Run internal (+ optional external) dependency probes.
    """
    t0 = time.monotonic()
    internal: List[Dict[str, Any]] = [
        check_django_app(),
        check_default_db(),
        check_django_cache(),
        check_cassandra(),
        check_redis(),
    ]
    external: List[Dict[str, Any]] = []
    if include_external:
        # Public Horizon is enough for light mode; still include Expert + BQ status
        external = [
            check_horizon("public"),
            check_horizon("testnet"),
            check_stellar_expert(),
            check_bigquery(),
        ]

    all_probes = internal + external
    summary = _summarize(all_probes)
    overall = _overall_status(summary)
    duration_ms = _ms_since(t0)

    return {
        "status": overall,
        "checked_at": _now_iso(),
        "duration_ms": duration_ms,
        "light_mode": bool(getattr(settings, "LIGHT_MODE", False)),
        "env": getattr(settings, "ENV", os.environ.get("ENV", "development")),
        "summary": summary,
        "internal": internal,
        "external": external,
        "service": "stellarmapweb",
        "version": "1.0",
    }
