"""
Fast High Value Accounts leaderboard for the /web/high-value-accounts/ page.

Cassandra cannot efficiently filter on is_hva / xlm_balance (not in PK), so a
naive ``list(queryset)`` becomes a full table scan and hangs the site.

This module:
- Uses indexed SQL queries when not on Cassandra
- Bounds Cassandra scans (max rows walked) and keeps only top-N by balance
- Caches results briefly so repeat loads are cheap
- Skips expensive per-account rank-change lookups by default on Cassandra
"""

from __future__ import annotations

import heapq
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Page display defaults (override via settings)
DEFAULT_DISPLAY_LIMIT = 100
DEFAULT_CACHE_TTL_SEC = 120
# Hard cap on Cassandra rows walked per request (prevents multi-minute hangs)
DEFAULT_CASSANDRA_MAX_SCAN = 2500
# Wall-clock budget for Cassandra iteration (Astra full scans are very slow)
DEFAULT_CASSANDRA_MAX_SECONDS = 4.0
# Rank-change enrichment does N partition reads — keep tiny or off on Cassandra
DEFAULT_RANK_ENRICH_SQL = 20
DEFAULT_RANK_ENRICH_CASSANDRA = 0


def _use_cassandra() -> bool:
    return bool(getattr(settings, "USE_CASSANDRA", False))


def _display_limit() -> int:
    return int(getattr(settings, "HVA_DISPLAY_LIMIT", DEFAULT_DISPLAY_LIMIT))


def _cache_ttl() -> int:
    return int(getattr(settings, "HVA_CACHE_TTL_SEC", DEFAULT_CACHE_TTL_SEC))


def _max_scan() -> int:
    # LIGHT_MODE / RO lab: keep scans short so the single gunicorn worker stays free
    default = DEFAULT_CASSANDRA_MAX_SCAN
    if getattr(settings, "LIGHT_MODE", False) or getattr(
        settings, "CASSANDRA_READ_ONLY", False
    ):
        default = min(default, 400)
    return int(getattr(settings, "HVA_CASSANDRA_MAX_SCAN", default))


def _max_scan_seconds() -> float:
    default = DEFAULT_CASSANDRA_MAX_SECONDS
    if getattr(settings, "LIGHT_MODE", False) or getattr(
        settings, "CASSANDRA_READ_ONLY", False
    ):
        default = min(default, 3.0)
    return float(getattr(settings, "HVA_CASSANDRA_MAX_SECONDS", default))


def _rank_enrich_limit() -> int:
    if _use_cassandra():
        return int(
            getattr(
                settings,
                "HVA_RANK_ENRICH_LIMIT",
                DEFAULT_RANK_ENRICH_CASSANDRA,
            )
        )
    return int(
        getattr(settings, "HVA_RANK_ENRICH_LIMIT", DEFAULT_RANK_ENRICH_SQL)
    )


def cache_key(network_name: str, threshold: float, limit: int) -> str:
    return f"hva_lb:v2:{network_name}:{int(threshold)}:{int(limit)}"


def invalidate_hva_leaderboard_cache(
    network_name: Optional[str] = None,
    threshold: Optional[float] = None,
) -> None:
    """Best-effort cache clear (locmem cannot list keys; delete known variants)."""
    networks = [network_name] if network_name else ["public", "testnet"]
    thresholds = (
        [float(threshold)]
        if threshold is not None
        else [10000, 50000, 100000, 500000, 750000, 1000000]
    )
    limits = {_display_limit(), 50, 100, 150}
    for net in networks:
        for thr in thresholds:
            for lim in limits:
                cache.delete(cache_key(net, thr, lim))


def _record_to_row(record, rank: int, enrich: Optional[dict] = None) -> dict:
    tags_list = (
        [tag.strip() for tag in record.tags.split(",") if tag.strip()]
        if getattr(record, "tags", None)
        else []
    )
    enrich = enrich or {}
    return {
        "stellar_account": record.stellar_account,
        "network_name": record.network_name,
        "xlm_balance": record.xlm_balance or 0,
        "stellar_creator_account": getattr(
            record, "stellar_creator_account", None
        ),
        "home_domain": getattr(record, "home_domain", None) or "",
        "tags": tags_list,
        "status": getattr(record, "status", None) or "",
        "created_at": getattr(record, "created_at", None),
        "updated_at": getattr(record, "updated_at", None),
        "current_rank": rank,
        "rank_change": enrich.get("rank_change", 0),
        "event_type": enrich.get("event_type"),
        "previous_rank": enrich.get("previous_rank"),
        "balance_change_pct": enrich.get("balance_change_pct", 0.0),
    }


def _fetch_sql_records(network_name: str, threshold: float, limit: int) -> List[Any]:
    """Efficient SQL path: filter + order + slice."""
    from apiApp.model_loader import StellarCreatorAccountLineage

    qs = StellarCreatorAccountLineage.objects.filter(
        network_name=network_name,
        is_hva=True,
        xlm_balance__gte=threshold,
    ).order_by("-xlm_balance")[:limit]
    return list(qs)


def _fetch_cassandra_top_records(
    network_name: str,
    threshold: float,
    limit: int,
    max_scan: int,
    max_seconds: Optional[float] = None,
) -> Tuple[List[Any], dict]:
    """
    Bounded Cassandra scan. Walk at most max_scan rows OR max_seconds wall time;
    keep top-N by balance with a min-heap. Never materializes the full table.
    """
    from apiApp.model_loader import StellarCreatorAccountLineage

    if max_seconds is None:
        max_seconds = _max_scan_seconds()

    meta = {
        "scanned": 0,
        "hit_scan_limit": False,
        "hit_time_limit": False,
        "qualifying_seen": 0,
        "max_scan": max_scan,
        "max_seconds": max_seconds,
    }
    # heap of (balance, counter, record) — counter breaks ties for heapq
    heap: List[Tuple[float, int, Any]] = []
    counter = 0
    deadline = time.monotonic() + float(max_seconds)

    # network_name is not the partition key — this is still an expensive scan,
    # so we always enforce row + wall-clock caps.
    try:
        qs = StellarCreatorAccountLineage.objects.filter(network_name=network_name)
    except Exception:
        qs = StellarCreatorAccountLineage.objects.all()

    try:
        stream = qs.iterator() if hasattr(qs, "iterator") else iter(qs)
        for record in stream:
            if time.monotonic() >= deadline:
                meta["hit_time_limit"] = True
                break
            meta["scanned"] += 1
            if meta["scanned"] > max_scan:
                meta["hit_scan_limit"] = True
                break

            bal = getattr(record, "xlm_balance", None) or 0.0
            is_hva = bool(getattr(record, "is_hva", False))
            # Accept HVA flag or explicit balance above selected threshold
            if not (is_hva or bal >= threshold):
                continue
            if bal < threshold:
                continue

            meta["qualifying_seen"] += 1
            counter += 1
            item = (bal, counter, record)
            if len(heap) < limit:
                heapq.heappush(heap, item)
            elif bal > heap[0][0]:
                heapq.heapreplace(heap, item)

            # Early exit if we already filled the leaderboard with strong HVAs
            # and have scanned a reasonable sample (best-effort completeness)
            if (
                len(heap) >= limit
                and meta["scanned"] >= max(limit * 20, 200)
                and heap[0][0] >= threshold * 2
            ):
                break
    except Exception as e:
        logger.error("Cassandra HVA scan failed: %s", e, exc_info=True)
        meta["error"] = str(e)

    # Highest balance first
    sorted_items = sorted(heap, key=lambda t: t[0], reverse=True)
    return [t[2] for t in sorted_items], meta


def _enrich_rank_changes(
    records: List[Any],
    network_name: str,
    threshold: float,
    enrich_limit: int,
) -> Dict[str, dict]:
    """Optional recent rank-change map for top enrich_limit accounts only."""
    if enrich_limit <= 0 or not records:
        return {}

    from datetime import timedelta

    from django.utils import timezone

    from apiApp.model_loader import HVAStandingChange

    cutoff = timezone.now() - timedelta(hours=24)
    out: Dict[str, dict] = {}

    for record in records[:enrich_limit]:
        acct = record.stellar_account
        try:
            changes = list(
                HVAStandingChange.objects.filter(stellar_account=acct)
            )
        except Exception:
            continue

        threshold_changes = [
            c
            for c in changes
            if (
                getattr(c, "network_name", None) == network_name
                and abs((getattr(c, "xlm_threshold", 0) or 0) - threshold) < 1.0
            )
        ]
        if not threshold_changes:
            continue
        recent = sorted(
            threshold_changes,
            key=lambda x: getattr(x, "created_at", None)
            or getattr(x, "change_time", None)
            or timezone.now(),
            reverse=True,
        )[0]
        created = getattr(recent, "created_at", None) or getattr(
            recent, "change_time", None
        )
        if created and created >= cutoff:
            out[acct] = {
                "rank_change": getattr(recent, "rank_change", 0) or 0,
                "event_type": getattr(recent, "event_type", None),
                "previous_rank": getattr(recent, "old_rank", None),
                "balance_change_pct": getattr(recent, "balance_change_pct", 0.0)
                or 0.0,
            }
    return out


def build_hva_leaderboard(
    network_name: str = "public",
    selected_threshold: Optional[float] = None,
    display_limit: Optional[int] = None,
    use_cache: bool = True,
    enrich_rank_changes: Optional[bool] = None,
) -> dict:
    """
    Build leaderboard payload for the HVA page.

    Returns dict with keys:
      hva_accounts, total_hva_count, total_hva_balance, selected_threshold,
      supported_thresholds, admin_default_threshold, hva_display_limit,
      meta (timing / scan info)
    """
    from apiApp.helpers.hva_ranking import HVARankingHelper

    t0 = time.monotonic()
    if network_name not in ("public", "testnet"):
        network_name = "public"

    admin_threshold = float(HVARankingHelper.get_hva_threshold())
    supported = list(HVARankingHelper.get_supported_thresholds())

    if selected_threshold is None:
        selected_threshold = admin_threshold
    else:
        try:
            selected_threshold = float(selected_threshold)
        except (TypeError, ValueError):
            selected_threshold = admin_threshold

    if supported and selected_threshold not in supported:
        selected_threshold = min(
            supported, key=lambda x: abs(x - selected_threshold)
        )

    limit = int(display_limit or _display_limit())
    limit = max(1, min(limit, 500))

    ck = cache_key(network_name, selected_threshold, limit)
    if use_cache:
        cached = cache.get(ck)
        if cached is not None:
            payload = dict(cached)
            payload.setdefault("meta", {})
            payload["meta"] = dict(payload["meta"])
            payload["meta"]["cache_hit"] = True
            payload["meta"]["elapsed_ms"] = int(
                (time.monotonic() - t0) * 1000
            )
            return payload

    if enrich_rank_changes is None:
        enrich_rank_changes = not _use_cassandra()

    enrich_limit = _rank_enrich_limit() if enrich_rank_changes else 0
    meta: dict = {
        "cache_hit": False,
        "backend": "cassandra" if _use_cassandra() else "sql",
        "scanned": 0,
        "hit_scan_limit": False,
    }

    records: List[Any] = []
    if _use_cassandra():
        # Cassandra driver can block for a long time on the first page fetch
        # (ALLOW FILTERING / full scan). Hard-timeout the request path so the
        # page never hangs the gunicorn worker.
        import concurrent.futures

        max_secs = _max_scan_seconds()
        max_scan = _max_scan()
        pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="hva-scan"
        )
        try:
            fut = pool.submit(
                _fetch_cassandra_top_records,
                network_name,
                selected_threshold,
                limit,
                max_scan,
                max_secs,
            )
            try:
                records, scan_meta = fut.result(timeout=max_secs + 0.75)
            except concurrent.futures.TimeoutError:
                records = []
                scan_meta = {
                    "scanned": 0,
                    "hit_scan_limit": False,
                    "hit_time_limit": True,
                    "qualifying_seen": 0,
                    "max_scan": max_scan,
                    "max_seconds": max_secs,
                    "timed_out": True,
                }
                logger.warning(
                    "HVA Cassandra scan timed out after %.1fs (network=%s threshold=%s)",
                    max_secs,
                    network_name,
                    selected_threshold,
                )
        except Exception as e:
            logger.error("HVA Cassandra scan executor failed: %s", e, exc_info=True)
            records = []
            scan_meta = {"error": str(e), "timed_out": True}
        finally:
            # Do not block the request waiting for a stuck Astra cursor
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                pool.shutdown(wait=False)
        meta.update(scan_meta)
    else:
        try:
            records = _fetch_sql_records(
                network_name, selected_threshold, limit
            )
            meta["scanned"] = len(records)
        except Exception as e:
            logger.error("SQL HVA fetch failed: %s", e, exc_info=True)
            records = []

    enrich_map = _enrich_rank_changes(
        records, network_name, selected_threshold, enrich_limit
    )

    hva_accounts = []
    total_balance = 0.0
    for rank, rec in enumerate(records, start=1):
        row = _record_to_row(rec, rank, enrich_map.get(rec.stellar_account))
        hva_accounts.append(row)
        total_balance += float(row["xlm_balance"] or 0)

    meta["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
    meta["returned"] = len(hva_accounts)

    payload = {
        "hva_accounts": hva_accounts,
        "total_hva_count": len(hva_accounts),
        "total_hva_balance": total_balance,
        "selected_threshold": selected_threshold,
        "supported_thresholds": supported,
        "admin_default_threshold": admin_threshold,
        "hva_display_limit": limit,
        "meta": meta,
    }

    if use_cache and _cache_ttl() > 0:
        # Do not cache empty results forever when scan hit limit with 0 hits —
        # short TTL so we retry soon after data appears.
        ttl = _cache_ttl()
        if not hva_accounts and meta.get("hit_scan_limit"):
            ttl = min(ttl, 30)
        cache.set(ck, payload, ttl)

    return payload
