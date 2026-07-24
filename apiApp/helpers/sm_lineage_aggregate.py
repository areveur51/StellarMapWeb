"""
Unified lineage aggregation for table + siblings tab + radial tidy tree.

DB-only: never calls Horizon, BigQuery, or Stellar Expert.
See docs/StellarMapWeb/design-lineage-aggregation.md (PR1 foundation).
"""

from __future__ import annotations

import copy
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from django.conf import settings

from apiApp.model_loader import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    USE_CASSANDRA,
)

logger = logging.getLogger(__name__)

PROJECTION_SCHEMA_VERSION = 1
DEFAULT_MAX_DEPTH = 50
DEFAULT_MAX_NODES = 500
DEFAULT_MAX_SIBLINGS_PER_LEVEL = 50
LIGHT_MAX_NODES = 200
LIGHT_MAX_SIBLINGS_PER_LEVEL = 25
CASSANDRA_IN_BATCH = 25
XLM_SIBLING_TREE_THRESHOLD = 1000  # matches search.html buildTreeFromLineage
TREE_ALGORITHM = "buildTreeFromLineage_v1"

# Path walk stop tokens (not real accounts)
_CREATOR_STOP = frozenset({"", "no_element_funder", "unknown", "none", "null"})


@dataclass
class AggregateOptions:
    max_depth: int = DEFAULT_MAX_DEPTH
    max_nodes: int = DEFAULT_MAX_NODES
    max_siblings_per_level: int = DEFAULT_MAX_SIBLINGS_PER_LEVEL
    include_siblings: bool = True
    include_assets: bool = True
    use_search_cache: bool = True
    force_rebuild: bool = False
    # Never call Horizon / external HTTP from aggregator

    @classmethod
    def from_settings(cls, **overrides) -> "AggregateOptions":
        light = bool(getattr(settings, "LIGHT_MODE", False))
        opts = cls(
            max_depth=DEFAULT_MAX_DEPTH,
            max_nodes=LIGHT_MAX_NODES if light else DEFAULT_MAX_NODES,
            max_siblings_per_level=(
                LIGHT_MAX_SIBLINGS_PER_LEVEL if light else DEFAULT_MAX_SIBLINGS_PER_LEVEL
            ),
        )
        for k, v in overrides.items():
            if hasattr(opts, k) and v is not None:
                setattr(opts, k, v)
        return opts


# ---------------------------------------------------------------------------
# Pure helpers (no ORM)
# ---------------------------------------------------------------------------


def convert_timestamp(ts) -> Optional[str]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.isoformat()
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts).isoformat()
    return str(ts)


def extract_assets(horizon_json) -> List[Dict[str, Any]]:
    """Extract non-native assets from Horizon accounts JSON (TEXT column)."""
    assets: List[Dict[str, Any]] = []
    if not horizon_json:
        return assets
    try:
        if isinstance(horizon_json, dict):
            horizon_data = horizon_json
        else:
            horizon_data = json.loads(horizon_json)
        balances = horizon_data.get("balances", []) or []
        for balance in balances:
            asset_type = balance.get("asset_type", "")
            if asset_type == "native":
                continue
            asset_code = balance.get("asset_code", "") or ""
            asset_issuer = balance.get("asset_issuer", "") or ""
            asset_balance = balance.get("balance", "0")
            assets.append(
                {
                    "name": asset_code,
                    "node_type": "ASSET",
                    "asset_type": asset_type,
                    "asset_code": asset_code,
                    "asset_issuer": asset_issuer,
                    "balance": float(asset_balance) if asset_balance else 0.0,
                }
            )
    except (json.JSONDecodeError, TypeError, KeyError, ValueError):
        pass
    return assets


def parse_cache_body(raw: Any) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Dual-format / invalid cache reader.

    Returns:
        (kind, data) where kind is one of:
        - 'projection' — schema_version>=1 with nodes
        - 'legacy_tree' — D3 tree root with children
        - 'miss' — empty, invalid JSON (incl. str(dict)), or unknown
    """
    if raw is None:
        return "miss", None
    if not isinstance(raw, str):
        raw = str(raw)
    if not raw.strip():
        return "miss", None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return "miss", None
    if not isinstance(data, dict):
        return "miss", None
    if data.get("schema_version", 0) >= 1 and isinstance(data.get("nodes"), dict):
        return "projection", data
    if "children" in data and (data.get("name") or data.get("stellar_account")):
        return "legacy_tree", data
    return "miss", None


def _is_stop_creator(creator: Optional[str]) -> bool:
    if creator is None:
        return True
    c = str(creator).strip()
    if not c:
        return True
    return c.lower() in _CREATOR_STOP


def build_tree_from_nodes(
    nodes: Dict[str, Dict[str, Any]],
    lineage_path: List[str],
    siblings_by_creator: Dict[str, List[str]],
    searched_account: str,
    xlm_threshold: float = XLM_SIBLING_TREE_THRESHOLD,
) -> Dict[str, Any]:
    """
    Build D3 tree matching client ``buildTreeFromLineage`` (search.html).

    - Lineage nodes always included
    - Siblings only if xlm_balance >= threshold
    - Asset children nested under included accounts
    - Flags: is_lineage_path, is_sibling, is_searched_account, is_issuer
    """
    path_set = set(lineage_path)
    sibling_set: Set[str] = set()
    for sibs in siblings_by_creator.values():
        for s in sibs:
            if s not in path_set:
                sibling_set.add(s)

    # Ordered records: lineage path first (root → searched), then siblings
    records: List[Dict[str, Any]] = []
    for addr in lineage_path:
        node = nodes.get(addr)
        if not node:
            continue
        records.append(_record_for_tree(node, True, False, addr == searched_account))
    for addr in sorted(sibling_set):
        node = nodes.get(addr)
        if not node:
            continue
        records.append(_record_for_tree(node, False, True, False))

    if not records:
        return {
            "name": searched_account,
            "node_type": "ISSUER",
            "stellar_account": searched_account,
            "children": [],
            "is_lineage_path": True,
            "is_sibling": False,
            "is_searched_account": True,
            "is_issuer": False,
        }

    lineage_accounts = [r for r in records if r.get("is_lineage_path")]
    oldest_ancestor = (
        lineage_accounts[0]["stellar_account"] if lineage_accounts else None
    )

    account_map: Dict[str, Dict[str, Any]] = {}
    for record in records:
        is_lineage = bool(record.get("is_lineage_path"))
        is_sibling = bool(record.get("is_sibling"))
        xlm_balance = float(record.get("xlm_balance") or 0)
        if is_lineage or (is_sibling and xlm_balance >= xlm_threshold):
            addr = record["stellar_account"]
            account_map[addr] = {
                "name": addr,
                "node_type": "ISSUER",
                "stellar_account": addr,
                "created": record.get("stellar_account_created_at") or "",
                "home_domain": record.get("home_domain") or "",
                "xlm_balance": xlm_balance,
                "creator_account": record.get("stellar_creator_account") or "",
                "is_lineage_path": is_lineage,
                "is_sibling": is_sibling,
                "is_searched_account": bool(record.get("is_searched_account")),
                "is_issuer": bool(record.get("is_issuer")),
                "children": [],
            }

    for addr, current_node in list(account_map.items()):
        creator = current_node.get("creator_account")
        if creator and creator in account_map:
            parent = account_map[creator]
            if not any(
                c.get("stellar_account") == current_node["stellar_account"]
                for c in parent["children"]
            ):
                parent["children"].append(current_node)

    for record in records:
        current = account_map.get(record["stellar_account"])
        if not current:
            continue
        for asset in record.get("assets") or []:
            current["children"].append(
                {
                    "name": asset.get("asset_code") or asset.get("name") or "",
                    "node_type": "ASSET",
                    "asset_type": asset.get("asset_type", ""),
                    "asset_code": asset.get("asset_code", ""),
                    "asset_issuer": asset.get("asset_issuer", ""),
                    "balance": asset.get("balance", 0),
                    "children": [],
                }
            )

    root_node = None
    if oldest_ancestor and oldest_ancestor in account_map:
        root_node = account_map[oldest_ancestor]
    elif records:
        root_node = account_map.get(records[0]["stellar_account"])

    if not root_node:
        return {
            "name": searched_account,
            "node_type": "ISSUER",
            "stellar_account": searched_account,
            "children": [],
        }

    return _clone_tree(root_node)


def _record_for_tree(
    node: Dict[str, Any],
    is_lineage: bool,
    is_sibling: bool,
    is_searched: bool,
) -> Dict[str, Any]:
    return {
        "stellar_account": node.get("stellar_account"),
        "stellar_creator_account": node.get("stellar_creator_account"),
        "stellar_account_created_at": node.get("stellar_account_created_at"),
        "home_domain": node.get("home_domain") or "",
        "xlm_balance": float(node.get("xlm_balance") or 0),
        "assets": node.get("assets") or [],
        "is_lineage_path": is_lineage,
        "is_sibling": is_sibling,
        "is_searched_account": is_searched,
        "is_issuer": bool(node.get("is_issuer")),
    }


def _clone_tree(node: Dict[str, Any], visited: Optional[Set[str]] = None) -> Dict[str, Any]:
    if visited is None:
        visited = set()
    key = node.get("stellar_account") or node.get("name") or id(node)
    if key in visited:
        return None  # type: ignore
    visited = set(visited)
    visited.add(key)
    cloned = {
        "name": node.get("name"),
        "node_type": node.get("node_type"),
        "stellar_account": node.get("stellar_account"),
        "created": node.get("created"),
        "home_domain": node.get("home_domain"),
        "xlm_balance": node.get("xlm_balance"),
        "creator_account": node.get("creator_account"),
        "is_lineage_path": node.get("is_lineage_path"),
        "is_sibling": node.get("is_sibling"),
        "is_searched_account": node.get("is_searched_account"),
        "is_issuer": node.get("is_issuer"),
        "asset_type": node.get("asset_type"),
        "asset_code": node.get("asset_code"),
        "asset_issuer": node.get("asset_issuer"),
        "balance": node.get("balance"),
        "children": [],
    }
    # Drop None keys for cleaner JSON (keep children)
    cleaned = {k: v for k, v in cloned.items() if v is not None or k == "children"}
    cleaned["children"] = []
    for child in node.get("children") or []:
        c = _clone_tree(child, visited)
        if c is not None:
            cleaned["children"].append(c)
    return cleaned


def _node_from_record(
    record,
    network: str,
    include_assets: bool,
    in_lineage_path: bool,
) -> Dict[str, Any]:
    assets = extract_assets(getattr(record, "horizon_accounts_json", None)) if include_assets else []
    return {
        "stellar_account": record.stellar_account,
        "stellar_creator_account": record.stellar_creator_account or None,
        "network_name": getattr(record, "network_name", None) or network,
        "stellar_account_created_at": convert_timestamp(
            getattr(record, "stellar_account_created_at", None)
        ),
        "home_domain": getattr(record, "home_domain", None) or "",
        "xlm_balance": float(getattr(record, "xlm_balance", 0) or 0),
        "assets": assets,
        "status": getattr(record, "status", None) or "",
        "created_at": convert_timestamp(getattr(record, "created_at", None)),
        "updated_at": convert_timestamp(getattr(record, "updated_at", None)),
        "is_issuer": len(assets) > 0,
        "in_lineage_path": in_lineage_path,
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class LineageAggregateService:
    """
    Build and adapt a unified lineage projection for table, siblings, and tree.
    """

    def get_projection(
        self,
        account: str,
        network: str,
        options: Optional[AggregateOptions] = None,
    ) -> Dict[str, Any]:
        options = options or AggregateOptions.from_settings()
        if options.use_search_cache and not options.force_rebuild:
            cached = self._try_load_cache(account, network, options)
            if cached is not None:
                return cached
        return self.build_projection(account, network, options)

    def build_projection(
        self,
        account: str,
        network: str,
        options: Optional[AggregateOptions] = None,
    ) -> Dict[str, Any]:
        """DB-only. No Horizon, no BigQuery, no Stellar Expert."""
        options = options or AggregateOptions.from_settings()
        t0 = time.monotonic()

        lineage_path, path_records = self._walk_lineage_path(
            account, network, options.max_depth
        )
        path_set = set(lineage_path)

        siblings_by_creator: Dict[str, List[str]] = {}
        sibling_records: Dict[str, Any] = {}

        if options.include_siblings and lineage_path:
            siblings_by_creator, sibling_records = self._fetch_siblings(
                path_records, path_set, network, options.max_siblings_per_level
            )

        nodes: Dict[str, Dict[str, Any]] = {}
        for addr, rec in path_records.items():
            nodes[addr] = _node_from_record(
                rec, network, options.include_assets, in_lineage_path=True
            )
        for addr, rec in sibling_records.items():
            if addr not in nodes:
                nodes[addr] = _node_from_record(
                    rec, network, options.include_assets, in_lineage_path=False
                )

        # Ensure path membership flags after sibling merge
        for addr, node in nodes.items():
            node["in_lineage_path"] = addr in path_set

        truncated = False
        if len(nodes) > options.max_nodes:
            truncated = True
            nodes, siblings_by_creator = self._truncate_nodes(
                nodes, lineage_path, siblings_by_creator, options.max_nodes
            )

        edges = self._build_edges(nodes, lineage_path, siblings_by_creator)

        tree = build_tree_from_nodes(
            nodes,
            lineage_path,
            siblings_by_creator,
            searched_account=account,
            xlm_threshold=XLM_SIBLING_TREE_THRESHOLD,
        )

        build_ms = int((time.monotonic() - t0) * 1000)
        sibling_count = sum(len(v) for v in siblings_by_creator.values())
        status = ""
        if account in nodes:
            status = nodes[account].get("status") or ""

        return {
            "schema_version": PROJECTION_SCHEMA_VERSION,
            "account": account,
            "network": network,
            "built_at": datetime.utcnow().isoformat(),
            "source": "database",
            "status": status,
            "lineage_path": lineage_path,
            "nodes": nodes,
            "edges": edges,
            "siblings_by_creator": siblings_by_creator,
            "tree": tree,
            "tree_build": {
                "xlm_sibling_threshold": XLM_SIBLING_TREE_THRESHOLD,
                "algorithm": TREE_ALGORITHM,
            },
            "meta": {
                "depth": len(lineage_path),
                "node_count": len(nodes),
                "sibling_count": sibling_count,
                "truncated": truncated,
                "max_depth": options.max_depth,
                "max_nodes": options.max_nodes,
                "max_siblings_per_level": options.max_siblings_per_level,
                "build_ms": build_ms,
                "db_only": True,
                "cached": False,
            },
        }

    def rebuild_and_cache(
        self,
        account: str,
        network: str,
        options: Optional[AggregateOptions] = None,
        cache_status: str = "DONE_MAKE_PARENT_LINEAGE",
    ) -> Dict[str, Any]:
        """
        Pipeline hook: build_projection + write valid JSON only via update_cache.
        """
        options = options or AggregateOptions.from_settings(force_rebuild=True)
        options.force_rebuild = True
        options.use_search_cache = False
        projection = self.build_projection(account, network, options)
        try:
            from apiApp.helpers.sm_cache import StellarMapCacheHelpers

            StellarMapCacheHelpers().update_cache(
                stellar_account=account,
                network_name=network,
                tree_data=projection,
                status=cache_status,
            )
        except Exception as e:
            logger.warning(
                "rebuild_and_cache: failed to write search cache for %s...: %s",
                account[:8],
                e,
            )
        projection.setdefault("meta", {})["cached"] = True
        return projection

    def to_tree(self, projection: Dict[str, Any]) -> Dict[str, Any]:
        tree = projection.get("tree")
        if tree:
            return tree
        return build_tree_from_nodes(
            projection.get("nodes") or {},
            projection.get("lineage_path") or [],
            projection.get("siblings_by_creator") or {},
            searched_account=projection.get("account") or "",
            xlm_threshold=(
                (projection.get("tree_build") or {}).get(
                    "xlm_sibling_threshold", XLM_SIBLING_TREE_THRESHOLD
                )
            ),
        )

    def to_table_rows(self, projection: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Path-only rows root → searched for SSR / Account Lineage table."""
        nodes = projection.get("nodes") or {}
        rows = []
        for level, addr in enumerate(projection.get("lineage_path") or []):
            node = nodes.get(addr)
            if not node:
                continue
            rows.append(
                {
                    "stellar_account": node.get("stellar_account"),
                    "stellar_creator_account": node.get("stellar_creator_account"),
                    "network_name": node.get("network_name"),
                    "stellar_account_created_at": node.get("stellar_account_created_at"),
                    "home_domain": node.get("home_domain") or "",
                    "xlm_balance": node.get("xlm_balance") or 0,
                    "assets": node.get("assets") or [],
                    "status": node.get("status") or "",
                    "created_at": node.get("created_at"),
                    "updated_at": node.get("updated_at"),
                    "hierarchy_level": level,
                    "is_issuer": bool(node.get("is_issuer")),
                }
            )
        return rows

    def to_siblings_response(self, projection: Dict[str, Any]) -> Dict[str, Any]:
        """Match lineage-with-siblings API shape + additive tree/meta."""
        nodes = projection.get("nodes") or {}
        all_account_data = {
            addr: {
                "stellar_account": n.get("stellar_account"),
                "stellar_creator_account": n.get("stellar_creator_account"),
                "network_name": n.get("network_name"),
                "stellar_account_created_at": n.get("stellar_account_created_at"),
                "home_domain": n.get("home_domain") or "",
                "xlm_balance": n.get("xlm_balance") or 0,
                "assets": n.get("assets") or [],
                "status": n.get("status") or "",
                "created_at": n.get("created_at"),
                "updated_at": n.get("updated_at"),
                "is_issuer": bool(n.get("is_issuer")),
                "in_lineage_path": bool(n.get("in_lineage_path")),
            }
            for addr, n in nodes.items()
        }
        siblings_by_creator = projection.get("siblings_by_creator") or {}
        meta = dict(projection.get("meta") or {})
        tree_build = projection.get("tree_build") or {
            "xlm_sibling_threshold": XLM_SIBLING_TREE_THRESHOLD,
            "algorithm": TREE_ALGORITHM,
        }
        meta["tree_build"] = tree_build
        meta["schema_version"] = projection.get("schema_version", PROJECTION_SCHEMA_VERSION)
        meta["source"] = projection.get("source", "database")

        return {
            "account": projection.get("account"),
            "network": projection.get("network"),
            "lineage_path": list(projection.get("lineage_path") or []),
            "siblings_by_creator": siblings_by_creator,
            "all_account_data": all_account_data,
            "total_accounts": len(all_account_data),
            "total_siblings": sum(len(v) for v in siblings_by_creator.values()),
            "tree": self.to_tree(projection),
            "meta": meta,
        }

    def to_lineage_api_response(self, projection: Dict[str, Any]) -> Dict[str, Any]:
        """Feature-frozen account-lineage shape: path-only flatten with hierarchy_level."""
        rows = self.to_table_rows(projection)
        lineage = []
        for row in rows:
            lineage.append(
                {
                    "stellar_account": row["stellar_account"],
                    "stellar_creator_account": row.get("stellar_creator_account"),
                    "network_name": row.get("network_name"),
                    "stellar_account_created_at": row.get("stellar_account_created_at"),
                    "home_domain": row.get("home_domain") or "",
                    "xlm_balance": row.get("xlm_balance") or 0,
                    "assets": row.get("assets") or [],
                    "status": row.get("status") or "",
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "hierarchy_level": row.get("hierarchy_level", 0),
                }
            )
        return {
            "account": projection.get("account"),
            "network": projection.get("network"),
            "lineage": lineage,
            "total_records": len(lineage),
            "source": projection.get("source") or "database",
        }

    def get_display_bundle(
        self,
        account: str,
        network: str,
        options: Optional[AggregateOptions] = None,
    ) -> Dict[str, Any]:
        """SSR bundle: tree_data + account_lineage_data from one projection."""
        projection = self.get_projection(account, network, options)
        tree = self.to_tree(projection)
        return {
            "tree_data": tree,
            "radial_tidy_tree_variable": tree,
            "account_lineage_data": self.to_table_rows(projection),
            "account_genealogy_items": [],
            "meta": projection.get("meta") or {},
            "projection": projection,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _try_load_cache(
        self,
        account: str,
        network: str,
        options: AggregateOptions,
    ) -> Optional[Dict[str, Any]]:
        try:
            entry = StellarAccountSearchCache.objects.filter(
                stellar_account=account,
                network_name=network,
            ).first()
        except Exception as e:
            logger.debug("cache load failed: %s", e)
            return None
        if not entry:
            return None
        kind, data = parse_cache_body(getattr(entry, "cached_json", None))
        if kind == "projection" and data is not None:
            if "tree" not in data or not data.get("tree"):
                data["tree"] = build_tree_from_nodes(
                    data.get("nodes") or {},
                    data.get("lineage_path") or [],
                    data.get("siblings_by_creator") or {},
                    searched_account=account,
                )
            data.setdefault("meta", {})
            data["meta"]["cached"] = True
            data["meta"]["db_only"] = True
            return data
        if kind == "legacy_tree" and data is not None:
            # Minimal wrap: tree-only SSR; empty path/nodes until rebuild
            return {
                "schema_version": PROJECTION_SCHEMA_VERSION,
                "account": account,
                "network": network,
                "built_at": datetime.utcnow().isoformat(),
                "source": "legacy_cache_tree",
                "status": getattr(entry, "status", "") or "",
                "lineage_path": [],
                "nodes": {},
                "edges": [],
                "siblings_by_creator": {},
                "tree": data,
                "tree_build": {
                    "xlm_sibling_threshold": XLM_SIBLING_TREE_THRESHOLD,
                    "algorithm": TREE_ALGORITHM,
                },
                "meta": {
                    "depth": 0,
                    "node_count": 0,
                    "sibling_count": 0,
                    "truncated": False,
                    "cached": True,
                    "db_only": True,
                    "legacy_tree": True,
                },
            }
        return None

    def _fetch_one(self, account: str, network: str):
        if USE_CASSANDRA:
            records = list(
                StellarCreatorAccountLineage.objects.filter(
                    stellar_account=account,
                    network_name=network,
                ).limit(1)
            )
            return records[0] if records else None
        return StellarCreatorAccountLineage.objects.filter(
            stellar_account=account,
            network_name=network,
        ).first()

    def _walk_lineage_path(
        self,
        account: str,
        network: str,
        max_depth: int,
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Sequential path discovery O(D). Returns (root→searched path, records map).
        """
        searched_to_root: List[str] = []
        records: Dict[str, Any] = {}
        current = account
        visited: Set[str] = set()

        while (
            current
            and current not in visited
            and len(searched_to_root) < max_depth
            and not _is_stop_creator(current)
        ):
            visited.add(current)
            rec = self._fetch_one(current, network)
            if not rec:
                break
            searched_to_root.append(current)
            records[current] = rec
            creator = getattr(rec, "stellar_creator_account", None)
            if _is_stop_creator(creator):
                break
            current = creator

        lineage_path = list(reversed(searched_to_root))
        return lineage_path, records

    def _fetch_siblings(
        self,
        path_records: Dict[str, Any],
        path_set: Set[str],
        network: str,
        max_siblings: int,
    ) -> Tuple[Dict[str, List[str]], Dict[str, Any]]:
        creators: List[str] = []
        for rec in path_records.values():
            creator = getattr(rec, "stellar_creator_account", None)
            if creator and not _is_stop_creator(creator) and creator not in creators:
                creators.append(creator)

        siblings_by_creator: Dict[str, List[str]] = {}
        sibling_records: Dict[str, Any] = {}
        if not creators:
            return siblings_by_creator, sibling_records

        children_records = []
        if USE_CASSANDRA:
            for creator_addr in creators:
                children = list(
                    StellarCreatorAccountLineage.objects.filter(
                        stellar_creator_account=creator_addr,
                        network_name=network,
                    ).limit(max_siblings + 1)
                )
                children_records.extend(children)
        else:
            children_records = list(
                StellarCreatorAccountLineage.objects.filter(
                    stellar_creator_account__in=creators,
                    network_name=network,
                )
            )

        for rec in children_records:
            creator_addr = rec.stellar_creator_account
            child_addr = rec.stellar_account
            if child_addr in path_set:
                continue
            if creator_addr not in siblings_by_creator:
                siblings_by_creator[creator_addr] = []
            if len(siblings_by_creator[creator_addr]) < max_siblings:
                siblings_by_creator[creator_addr].append(child_addr)
                sibling_records[child_addr] = rec

        return siblings_by_creator, sibling_records

    def _truncate_nodes(
        self,
        nodes: Dict[str, Dict[str, Any]],
        lineage_path: List[str],
        siblings_by_creator: Dict[str, List[str]],
        max_nodes: int,
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
        """Drop siblings first to keep path; then hard-cap path if needed."""
        path_set = set(lineage_path)
        # Prefer keeping path nodes
        kept = {a: nodes[a] for a in lineage_path if a in nodes}
        # Add siblings until cap
        new_sibs: Dict[str, List[str]] = {}
        for creator, sibs in siblings_by_creator.items():
            for s in sibs:
                if len(kept) >= max_nodes:
                    break
                if s in nodes and s not in kept:
                    kept[s] = nodes[s]
                    new_sibs.setdefault(creator, []).append(s)
            if len(kept) >= max_nodes:
                break
        # If still over (path alone too long), trim path from root end of extras — keep searched end
        if len(kept) > max_nodes and lineage_path:
            # path-only case
            path_keep = lineage_path[-max_nodes:]
            kept = {a: nodes[a] for a in path_keep if a in nodes}
            new_sibs = {}
        return kept, new_sibs

    def _build_edges(
        self,
        nodes: Dict[str, Dict[str, Any]],
        lineage_path: List[str],
        siblings_by_creator: Dict[str, List[str]],
    ) -> List[Dict[str, str]]:
        edges = []
        path_set = set(lineage_path)
        for addr, node in nodes.items():
            parent = node.get("stellar_creator_account")
            if parent and parent in nodes:
                edge_type = "lineage" if addr in path_set else "sibling"
                edges.append(
                    {"parent": parent, "child": addr, "edge_type": edge_type}
                )
        return edges
