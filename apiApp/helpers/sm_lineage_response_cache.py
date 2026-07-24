"""
Process-local TTL + LRU cache for lineage API JSON responses.

Isolated from Django LocMem (LIGHT_MODE CACHE_MAX_ENTRIES=256) so large
lineage payloads do not thrash rate-limiter / heartbeat keys.

See design-lineage-aggregation.md §8.4.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

# Module singleton — one worker process = one dict (NAS default)
_lock = threading.Lock()
_store: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

DEFAULT_MAX_VALUE_BYTES = 512 * 1024


def lineage_response_cache_enabled() -> bool:
    return bool(getattr(settings, "LINEAGE_API_RESPONSE_CACHE", True))


def lineage_response_ttl_seconds() -> int:
    poll_ms = int(getattr(settings, "POLL_INTERVAL_MS", 30000) or 30000)
    return max(15, min(300, poll_ms // 1000))


def lineage_response_max_entries() -> int:
    light = bool(getattr(settings, "LIGHT_MODE", False))
    return 32 if light else 64


def lineage_response_max_value_bytes() -> int:
    return int(
        getattr(settings, "LINEAGE_API_RESPONSE_MAX_BYTES", DEFAULT_MAX_VALUE_BYTES)
        or DEFAULT_MAX_VALUE_BYTES
    )


def _estimate_size(data: Any) -> int:
    try:
        return len(json.dumps(data, default=str))
    except (TypeError, ValueError):
        return DEFAULT_MAX_VALUE_BYTES + 1


def cache_key(account: str, network: str, kind: str = "siblings", **extra) -> str:
    parts = [kind, network, account]
    for k in sorted(extra.keys()):
        parts.append(f"{k}={extra[k]}")
    return "|".join(parts)


def get_cached(key: str) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Returns (payload_copy_or_None, hit).
    """
    if not lineage_response_cache_enabled():
        return None, False
    ttl = lineage_response_ttl_seconds()
    now = datetime.utcnow()
    with _lock:
        entry = _store.get(key)
        if not entry:
            return None, False
        age = (now - entry["timestamp"]).total_seconds()
        if age >= ttl:
            del _store[key]
            return None, False
        # LRU: move to end
        _store.move_to_end(key)
        data = entry["data"]
        # shallow copy of top-level dict so callers can set meta.cached
        if isinstance(data, dict):
            return dict(data), True
        return data, True


def set_cached(key: str, data: Dict[str, Any]) -> bool:
    """
    Store response if under size limit. Returns True if stored.
    """
    if not lineage_response_cache_enabled():
        return False
    if not isinstance(data, dict):
        return False
    size = _estimate_size(data)
    max_bytes = lineage_response_max_value_bytes()
    if size > max_bytes:
        logger.debug(
            "lineage response cache skip key=%s size=%s max=%s",
            key[:48],
            size,
            max_bytes,
        )
        return False
    max_entries = lineage_response_max_entries()
    with _lock:
        if key in _store:
            del _store[key]
        _store[key] = {
            "data": data,
            "timestamp": datetime.utcnow(),
            "size": size,
        }
        while len(_store) > max_entries:
            _store.popitem(last=False)
    return True


def invalidate_prefix(account: str, network: Optional[str] = None) -> int:
    """Drop entries for an account (optional network filter). Returns count removed."""
    removed = 0
    with _lock:
        keys = list(_store.keys())
        for k in keys:
            if account not in k:
                continue
            if network and f"|{network}|" not in f"|{k}|":
                # keys look like kind|network|account|...
                parts = k.split("|")
                if len(parts) >= 2 and parts[1] != network:
                    continue
            del _store[k]
            removed += 1
    return removed


def clear_all() -> None:
    with _lock:
        _store.clear()


def stats() -> Dict[str, Any]:
    with _lock:
        return {
            "entries": len(_store),
            "max_entries": lineage_response_max_entries(),
            "ttl": lineage_response_ttl_seconds(),
            "enabled": lineage_response_cache_enabled(),
        }
