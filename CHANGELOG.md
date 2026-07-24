# Changelog

## Unreleased

### Added
- **Write-time projection (PR2B)** — `LINEAGE_WRITE_PROJECTION` flag; on complete, API/BigQuery/SDK pipelines + parent-lineage cron can `rebuild_and_cache` DB-only projection; SDK now status-syncs search cache; `update_cache` rejects non-JSON bodies
- **LineageAggregateService (PR1)** — `apiApp/helpers/sm_lineage_aggregate.py`: DB-only unified projection (nodes/edges/path/tree/siblings), adapters for table + siblings API + tree parity with client XLM≥1000 filter; no view wiring yet (PR3/PR4)
- **Shared shell** — `includes/head_assets.html`, vanilla slide-out menu (no Bootstrap-Vue sidebar), touch-friendly top bar
- **Responsive `frontend.css`** — restored page styles (dashboard/bulk/HVA/query) + mobile/iPad breakpoints and safe-area padding
- **Tailscale QR manager login** — passwordless `/login/` (auto QR + continue on device); allowlist via `TAILSCALE_ALLOW_LOGINS`
- **Access split** — public search/read UI; `/admin/` and management APIs require manager session
- **Dependency heartbeat** — dashboard panel + `GET /api/heartbeat/` (internal/external probes)
- **Postgres support** — `DATABASE_DRIVER=pg` + `DATABASE_URL` (lab: `StellarMapDB` on shared Postgres)
- **Light-footprint defaults** — `LIGHT_MODE` (locmem cache, quieter logs, longer UI poll, lean SQLite PRAGMAs)

### Changed
- Menu no longer depends on Bootstrap-Vue `b-sidebar` (plain HTML/JS drawer; always clickable)
- Login QR uses **qrcodejs** CDN (previous node-qrcode path 404'd); QR generates on page load; CSRF token on form
- App styles live in `frontend.css` (not global Bootstrap reboot — original pages never used full Bootstrap CSS)
- Settings: env-driven hosts, WhiteNoise for static on host, session cookie name `stellarmap.sid`
- Dashboard / search: poll interval from server; manager login link in nav
- `requirements.txt`: `psycopg2-binary` for Postgres

### Fixed
- **Search-cache clobber (PR2A)** — `QueueSynchronizer.sync_status_back_to_cache` is **status-only**: never writes `str(dict)` into `cached_json` (was invalid non-JSON and could re-PENDING COMPLETE accounts). API/BigQuery pipelines no longer pass summary payloads; existing tree JSON is preserved. Full display rebuild remains PR2B.
- Multi-line Django `{# #}` comments leaking as visible text in page heads
- Unclickable hamburger after UI polish (BV sidebar without Bootstrap grid)
- Broken layout from loading Bootstrap CSS globally then stripping page `<style>` blocks

### Security
- Manager routes gated by middleware; empty Tailscale allowlist denies manager login
- Do not commit `.env`, SQLite dumps, or Postgres passwords
