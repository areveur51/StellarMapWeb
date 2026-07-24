# Performance Optimizations Applied

## Summary
This document tracks all performance optimizations applied to the StellarMapWeb application. The optimizations focus on database queries, API caching, frontend rendering, and pipeline efficiency.

## 0. Lineage Aggregation (2026-07 — development)

Unified **table + siblings + radial tree** aggregation landed on the `development` branch (design PR roadmap). Full design: hub `docs/StellarMapWeb/design-lineage-aggregation.md` (GrokBuild) or product design notes.

| PR | Change | Status |
|----|--------|--------|
| **PR2A** | Status-only search-cache sync; never `str(dict)` into `cached_json` | Merged |
| **PR1** | `LineageAggregateService` (`apiApp/helpers/sm_lineage_aggregate.py`) DB-only projection | Merged |
| **PR2B** | Flag `LINEAGE_WRITE_PROJECTION` → `rebuild_and_cache` on API/BQ/SDK/cron complete | Merged |
| **PR3** | Flag `LINEAGE_UNIFIED_AGGREGATE` → `search_view` one projection for table+tree | Merged |
| **PR4** | Lineage APIs via aggregator; process-local response LRU; rate limits | Merged |
| **PR5** | Progressive / lazy siblings (`LINEAGE_PROGRESSIVE_SIBLINGS`) | This PR (optional, default off) |
| **PR6b** | Frontend prefers server `tree` when algorithm matches | This PR |

### Caching (lineage)

| Layer | Behavior |
|-------|----------|
| **Search cache `cached_json`** | Valid `json.dumps` only (tree or schema v1 projection). Status-only sync does **not** touch body or `last_fetched_at`. |
| **`LINEAGE_WRITE_PROJECTION=1`** | On pipeline complete, write full projection via `rebuild_and_cache` (DB-only). |
| **`LINEAGE_API_RESPONSE_CACHE` (default on)** | Process-local TTL/LRU for `/api/lineage-with-siblings/` and `/api/account-lineage/` — **not** Django LocMem (avoids thrashing `CACHE_MAX_ENTRIES=256` under LIGHT_MODE). TTL = `max(15, min(300, POLL_INTERVAL_MS//1000))`. Max entries 32 light / 64 full; skip payloads &gt; 512KB. |
| **`pending_accounts_api`** | Separate process-local cache; TTL still poll-aligned. |

### Rate limits (lineage)

| Endpoint | Limit |
|----------|-------|
| `GET /api/lineage-with-siblings/` | **30/m** per IP |
| `GET /api/account-lineage/` | **20/m** per IP (feature-frozen; prefer siblings API) |
| `search_view` | **20/m** per IP (existing) |

### Flags (default safe for NAS)

| Variable | Default | Effect |
|----------|---------|--------|
| `LINEAGE_WRITE_PROJECTION` | `0` | Pipelines write full projection on complete |
| `LINEAGE_UNIFIED_AGGREGATE` | `0` | SSR uses unified service |
| `LINEAGE_SSR_INCLUDE_SIBLINGS` | `0` | SSR includes siblings (heavier) |
| `LINEAGE_API_RESPONSE_CACHE` | `1` | Process-local API response LRU |
| `LINEAGE_PROGRESSIVE_SIBLINGS` | `0` | Path-first API poll then siblings (2 requests) |

### Query model

- Path discovery remains **O(D)** sequential partition reads (creator unknown until hop).
- Siblings / enrichment use batch IN ≤25 on Cassandra.
- Aggregator is **DB-only** (no Horizon/BigQuery on request or rebuild).

### Lab tip

On LIGHT_MODE NAS, leave write/SSR flags off until pipelines are intentionally enabled; PR2A alone already stops cache clobber. Turn on `LINEAGE_UNIFIED_AGGREGATE` + `LINEAGE_WRITE_PROJECTION` when you want one projection end-to-end.

---

## 1. SDK Pipeline Source Tracking (October 25, 2025)

### Issue
SDK Pipeline was processing accounts but not setting `pipeline_source='SDK'`, making it impossible to track which accounts were processed by the SDK pipeline on the dashboard.

### Fix
Added `account_obj.pipeline_source = 'SDK'` to the `_update_account_in_database()` method in `stellar_sdk_pipeline.py`.

### Impact
- Dashboard now correctly shows SDK pipeline statistics
- Enables accurate triple-pipeline metrics tracking
- Allows performance comparison between BigQuery, API, and SDK pipelines

---

## 2. API Endpoint Caching Strategy

### Current Status
- `pending_accounts_api`: process-local cache, TTL tied to `POLL_INTERVAL_MS` (✓)
- `lineage-with-siblings` / `account-lineage`: process-local LRU + poll-aligned TTL (✓ PR4)
- Search cache: 12-hour freshness on `last_fetched_at` (✓); body is JSON only (✓ PR2A/PR2B)
- `pipeline_stats_api`: No caching (opportunity for optimization)

### Recommendations
1. **pipeline_stats_api**: Add 10-15s cache (stats change slowly)
2. ~~**lineage_api**: Add per-account caching~~ — done via process-local LRU (PR4)
3. **search results**: Already cached for 12 hours (✓ Good)

---

## 3. Database Query Optimizations

### Current Cassandra Model Indexes
Cassandra uses composite primary keys for efficient querying:
- `StellarAccountSearchCache`: Primary key = `stellar_account`
- `StellarCreatorAccountLineage`: Primary key = `id` (composite: account + network)
- `StellarAccountStageExecution`: Primary key = `stellar_account`
- `HVAStandingChange`: Primary key = `stellar_account`

### Optimization Opportunities
1. **Cassandra queries**: Already using partition keys (✓ Good)
2. **Aggregation queries**: Show "Server warning: Aggregation query used without partition key"
   - These are expected in Cassandra when counting totals
   - Consider adding materialized views for frequently aggregated data

### Recommendations
- Add MATERIALIZED VIEWS for:
  - Count of accounts by pipeline_source (for dashboard stats)
  - Count of accounts by status (for queue monitoring)

---

## 4. Frontend D3.js Rendering Optimizations

### Current Implementation
- Smart node positioning with Fibonacci spiral
- Adaptive radius calculation based on node count
- Interactive zoom and pan with D3 zoom behavior

### Optimization Opportunities
1. **Lazy loading**: Load tree data progressively for large graphs
2. **Debouncing**: Debounce filter slider changes (currently instant)
3. **Canvas rendering**: For graphs >500 nodes, switch from SVG to Canvas
4. **Virtual scrolling**: For large sibling lists in separate tabs

### Recommendations
- Add debouncing to filter sliders (300ms delay)
- Implement canvas fallback for graphs >500 nodes
- Consider WebGL for graphs >1000 nodes

---

## 5. Pipeline Processing Efficiency

### Current Configuration
- **SDK Pipeline**: 3-5 concurrent accounts, 3600 req/hour rate limit
- **API Pipeline**: Sequential processing, ~2-3 min per account
- **BigQuery Pipeline**: Batch processing, cost-limited

### Optimization Applied
1. **SDK Pipeline**: Now correctly sets `pipeline_source='SDK'` ✓
2. **Queue Synchronizer**: Automatically syncs Search Cache → Lineage ✓
3. **Rate limiting**: Optimized to use full 3600 req/hour quota ✓

### Performance Metrics
- **SDK Pipeline**: ~30-60s per account (concurrent)
- **API Pipeline**: ~2-3 minutes per account (sequential)
- **BigQuery Pipeline**: ~5-10s per account (bulk processing, but costs money)

### Recommendations
- **SDK_ONLY** mode recommended for continuous background processing (free, fast)
- **API_ONLY** mode for reliable fallback (free, slower)
- **BIGQUERY** modes only for historical data or bulk imports (costs $0.18-0.71 per query)

---

## 6. Memory and Resource Usage

### Current Status
- Python process memory: ~100-200MB per workflow
- Database connections: Pool of 5-10 connections
- API rate limiting: In-memory tracking with TTL

### Optimization Opportunities
1. **Connection pooling**: Already implemented ✓
2. **Memory profiling**: Monitor for memory leaks in long-running pipelines
3. **Garbage collection**: Python GC handles cleanup automatically

---

## 7. Network and Latency Optimizations

### Current Implementation
- **API endpoints**: JSON responses, gzip compression enabled
- **Static files**: Served directly by Django (development)
- **Database**: Cassandra connections use connection pooling

### Production Recommendations
1. **CDN**: Use CloudFlare or similar for static assets
2. **Gzip/Brotli**: Enable compression for API responses
3. **HTTP/2**: Enable for multiplexing requests
4. **Keep-Alive**: Enable persistent connections

---

## 8. Monitoring and Metrics

### Current Tracking
- Pipeline statistics (BigQuery, API, SDK totals)
- Rate limiter stats (requests per window)
- Error tracking (Sentry integration)

### Future Enhancements
1. **Performance monitoring**: Add timing metrics for API endpoints
2. **Query profiling**: Track slow database queries
3. **Memory profiling**: Monitor memory usage over time
4. **Dashboard analytics**: Track user interactions and page load times

---

## Quick Wins Applied

1. ✅ **SDK Pipeline Source Tracking**: Fixed `pipeline_source='SDK'` bug
2. ✅ **Pending Accounts Cache**: 30s TTL prevents database overload
3. ✅ **Rate Limiting**: Optimized to use full Horizon quota (3600 req/hour)
4. ✅ **Queue Synchronizer**: Automatic sync reduces manual intervention

## Next Steps

1. Add caching to `pipeline_stats_api` endpoint (10-15s TTL)
2. Implement debouncing for D3.js filter sliders (300ms)
3. Add materialized views for dashboard statistics
4. Monitor SDK Pipeline performance and adjust concurrent limit if needed
5. Consider canvas rendering fallback for large graphs (>500 nodes)

---

## Performance Testing Results

### Before Optimizations
- Dashboard stats endpoint: ~500-1000ms response time
- Pending accounts endpoint: ~2000-3000ms response time (full table scan)
- D3.js filter updates: Instant (can cause lag on large graphs)

### After Optimizations
- Dashboard stats endpoint: ~200-500ms response time (no caching yet)
- Pending accounts endpoint: ~50-100ms response time (30s cache) ✓
- SDK Pipeline: Now tracking correctly with pipeline_source='SDK' ✓

### Target Performance Goals
- Dashboard stats: <100ms (with caching)
- Pending accounts: <50ms (cached)
- D3.js rendering: <1s for graphs with <200 nodes
- Pipeline processing: <60s per account (SDK), <180s per account (API)

---

## Cost Optimization

### Current Costs
- **SDK Pipeline**: $0.00 (free Horizon API)
- **API Pipeline**: $0.00 (free Horizon/Stellar Expert APIs)
- **BigQuery Pipeline**: $0.18-0.71 per query (when enabled)

### Recommendation
- **Use SDK_ONLY mode** for continuous background processing (free, fast)
- **Avoid BigQuery modes** unless you need bulk historical data
- **Monitor BigQuery costs** if enabled (set cost limits in admin config)

---

## Last Updated
October 25, 2025

## Changelog
- **2025-10-25**: Fixed SDK Pipeline source tracking bug, created performance optimization document
