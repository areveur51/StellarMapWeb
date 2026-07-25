# Changelog

## Unreleased

### Added
- **Near-RT Phase 1** — `NEAR_RT_ENABLED` (faster search poll + progressive siblings); `run_sdk_near_rt_worker` (SDK PENDING loop); public `POST /api/queue-lineage/`; search **Refresh / queue** button; `STELLARMAP_NEAR_RT_WORKER=1` in stellarmapctl
- **App-wide DRY progress navigation** — sidebar + shell links use `StellarMapProgress.navigate`; elapsed time shown on overlay; `searchAccount` helper on all pages
- **Aggregation closeout** — rewrite `test_lineage_with_siblings_api` as Django TestCase (no pytest; valid keys); document Definition of Done in `LINEAGE_AGGREGATION.md`
- **Progressive siblings (PR5)** — optional `LINEAGE_PROGRESSIVE_SIBLINGS`; API `include_siblings` / `structure_only`; search UI path-first then siblings second fetch
- **Frontend server tree (PR6b)** — search poll prefers API `tree` when `meta.tree_build.algorithm` is `buildTreeFromLineage_v1`; client rebuild remains fallback
- **Lineage aggregation docs (PR6a)** — `LINEAGE_AGGREGATION.md` implementation status; `PERFORMANCE_OPTIMIZATIONS.md` §0 (flags, caches, rate limits, rollout)
- **Lineage API aggregator + cache + rate limits (PR4)** — `/api/lineage-with-siblings/` and feature-frozen `/api/account-lineage/` use `LineageAggregateService` (DB-only); process-local response LRU; `@ratelimit` 30/m siblings, 20/m account-lineage; removed Horizon/BigQuery branch from account-lineage
- **Search SSR unified aggregate (PR3)** — `LINEAGE_UNIFIED_AGGREGATE` flag: `search_view` serves table + tree from one `LineageAggregateService` projection; terminal COMPLETE + invalid body rebuilds without re-PENDING; legacy dual-walk kept when flag off
- **Write-time projection (PR2B)** — `LINEAGE_WRITE_PROJECTION` flag; on complete, API/BigQuery/SDK pipelines + parent-lineage cron can `rebuild_and_cache` DB-only projection; SDK now status-syncs search cache; `update_cache` rejects non-JSON bodies
- **LineageAggregateService (PR1)** — `apiApp/helpers/sm_lineage_aggregate.py`: DB-only unified projection (nodes/edges/path/tree/siblings), adapters for table + siblings API + tree parity with client XLM≥1000 filter
- **Shared shell** — `includes/head_assets.html`, vanilla slide-out menu (no Bootstrap-Vue sidebar), touch-friendly top bar
- **Responsive `frontend.css`** — restored page styles (dashboard/bulk/HVA/query) + mobile/iPad breakpoints and safe-area padding
- **Tailscale QR manager login** — passwordless `/login/` (auto QR + continue on device); allowlist via `TAILSCALE_ALLOW_LOGINS`
- **Access split** — public search/read UI; `/admin/` and management APIs require manager session
- **Dependency heartbeat** — dashboard panel + `GET /api/heartbeat/` (internal/external probes)
- **Postgres support** — `DATABASE_DRIVER=pg` + `DATABASE_URL` (lab: `StellarMapDB` on shared Postgres)
- **Light-footprint defaults** — `LIGHT_MODE` (locmem cache, quieter logs, longer UI poll, lean SQLite PRAGMAs)
- **Astra read-only lab mode** — `CASSANDRA_READ_ONLY=1` loads Cassandra models and routes `apiApp` reads to Astra while ENV stays `development`; model saves and cache queue writes are blocked (safe with a read-only token)

### Changed
- **HVA leaderboard performance** — bounded Cassandra scan + response cache; no full-table list; rank-change N+1 disabled on Cassandra RO
- **Gunicorn + Cassandra** — removed `--preload` (forked workers inherited broken Astra sessions; HVA page hung/empty)
- **Radial tree UX** — full-circle layout adapts radius to sibling density; non-overlapping node placement; click opens right-side properties pane; large top-left HTML breadcrumbs; tree controls collapsible on iPad/mobile; filter re-renders debounced
- **Radial node UX** — non-overlapping nodes; click opens right properties pane; breadcrumbs as large top-left overlay
- **Search default tree** — `/search/` with no account shows a canned **example** radial tree: dense structure from original `test.json` converted to real `buildTreeFromLineage_v1` fields (path + siblings + assets + flags); not live public/testnet data; search box starts empty
- **HVA page performance** — prefer `is_hva` filter (no full network table scan), cap list length, limit rank-change enrichment queries
- **System Dashboard UI** — metric sections use the same elevated panel + compact card language as Dependency Heartbeat (no more fixed 180×180 square tiles); shared `.dash-panel` styles
- Menu no longer depends on Bootstrap-Vue `b-sidebar` (plain HTML/JS drawer; always clickable)
- Login QR uses **qrcodejs** CDN (previous node-qrcode path 404'd); QR generates on page load; CSRF token on form
- App styles live in `frontend.css` (not global Bootstrap reboot — original pages never used full Bootstrap CSS)
- Settings: env-driven hosts, WhiteNoise for static on host, session cookie name `stellarmap.sid`
- Dashboard / search: poll interval from server; manager login link in nav
- `requirements.txt`: `psycopg2-binary` for Postgres

### Fixed
- **Home page purple blank** — shared top bar required `networkLabel` / `toggleNetworkSwitch`; home Vue lacked them so render threw and emptied `#app`. Added `sm_network_mixin` and wired it on home + other shell pages (dashboard, bulk, HVA, query builder)
- **Search page not fully loading** — progress overlay moved outside Vue `#app`; helpers load before Vue (no defer race); progress DOM re-queried on show/hide
- **Search shell unit tests** — `test_search_page_shell.py` guards template/script structure regressions
- **Network PUBLIC/TESTNET switch** — replace bare BV checkbox with accessible switch; `StellarMapNetwork` + unit tests
- **Leaked Django comment on Search** — multi-line `{# #}` is invalid; use `{% comment %}` (text no longer shows next to Filters)
- **Search refresh layout** — results container full-width block (no flex-center left shunt)
- **DRY progress bar** — `StellarMapProgress` + `sm_progress.html` / `sm_progress.js` used on search (and other main pages)
- **Search UI tabs look like a bullet list** — full `.nav-tabs` styles without loading Bootstrap CSS (BV was rendering bare `<ul>` titles)
- **Radial tree flash then disappear** — single D3 owner path (Vue `paintTreeVisualization`); remove early partial auto-render that fought the lineage poll
- **Timezone-aware datetimes** — replace `datetime.utcnow()` with `timezone.now()` on ORM write/filter paths; add `utc_now`/`ensure_aware`/`age_seconds` helpers (stops USE_TZ RuntimeWarnings in logs)
- **Login CSRF for QR** — prefer form CSRF token; set `CSRF_COOKIE_HTTPONLY=False` so Tailscale QR start can send `X-CSRFToken`
- **Search-cache clobber (PR2A)** — `QueueSynchronizer.sync_status_back_to_cache` is **status-only**: never writes `str(dict)` into `cached_json` (was invalid non-JSON and could re-PENDING COMPLETE accounts). API/BigQuery pipelines no longer pass summary payloads; existing tree JSON is preserved. Full display rebuild remains PR2B.
- Multi-line Django `{# #}` comments leaking as visible text in page heads
- Unclickable hamburger after UI polish (BV sidebar without Bootstrap grid)
- Broken layout from loading Bootstrap CSS globally then stripping page `<style>` blocks

### Security
- Manager routes gated by middleware; empty Tailscale allowlist denies manager login
- Do not commit `.env`, SQLite dumps, or Postgres passwords
