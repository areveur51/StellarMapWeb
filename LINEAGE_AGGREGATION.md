# Lineage aggregation (implementation status)

How StellarMapWeb builds data for the **Account Lineage table**, **Siblings tab**, and **radial / tidy tree**.

## Design

Long-form design (current vs optimized, PR plan, caps, tree contract):

- GrokBuild hub: `docs/StellarMapWeb/design-lineage-aggregation.md` (if present on this host)
- Product performance notes: [PERFORMANCE_OPTIMIZATIONS.md](./PERFORMANCE_OPTIMIZATIONS.md) §0

## Core module

| Piece | Path |
|-------|------|
| Aggregator | `apiApp/helpers/sm_lineage_aggregate.py` |
| Response LRU | `apiApp/helpers/sm_lineage_response_cache.py` |
| Status-only cache sync | `apiApp/helpers/queue_sync.py` |
| Search cache JSON write | `apiApp/helpers/sm_cache.py` |

`LineageAggregateService` builds a **unified projection** (nodes, edges, lineage_path, siblings, tree) from **DB only** — no Horizon / BigQuery / Stellar Expert on the read path.

Tree builder matches client `buildTreeFromLineage` rules (lineage always included; siblings only if `xlm_balance >= 1000`).

## Flags

| Env | Default | Meaning |
|-----|---------|---------|
| `LINEAGE_WRITE_PROJECTION` | `0` | On pipeline complete, `rebuild_and_cache` full projection |
| `LINEAGE_UNIFIED_AGGREGATE` | `0` | `search_view` uses aggregator for table + tree |
| `LINEAGE_SSR_INCLUDE_SIBLINGS` | `0` | SSR includes siblings (heavier) |
| `LINEAGE_API_RESPONSE_CACHE` | `1` | Process-local API response cache |

## Endpoints

| Endpoint | Role |
|----------|------|
| `GET /api/lineage-with-siblings/` | Primary live poll (30/m). Returns path, siblings, `all_account_data`, additive `tree` + `meta`. |
| `GET /api/account-lineage/` | Feature-frozen (20/m). Prefer siblings API. DB-only thin wrap. |

## Pipelines

On complete, status is always synced without clobbering `cached_json`. When `LINEAGE_WRITE_PROJECTION=1`, API / BigQuery / **SDK** / parent-lineage cron rebuild the display projection.

## Rollout suggestion

1. Deploy with flags **off** (PR2A safety already on: no `str(dict)` clobber).
2. Enable `LINEAGE_API_RESPONSE_CACHE` (default on).
3. Enable `LINEAGE_WRITE_PROJECTION=1` where pipelines run.
4. Enable `LINEAGE_UNIFIED_AGGREGATE=1` for SSR.
5. Frontend server-tree preference remains a follow-up (PR6b).

## Tests

- `apiApp/tests/test_queue_sync_status_only.py`
- `apiApp/tests/test_sm_lineage_aggregate.py`
- `apiApp/tests/test_lineage_write_projection.py`
- `apiApp/tests/test_lineage_api_pr4.py`
- `webApp/tests/test_search_ssr_unified.py`
