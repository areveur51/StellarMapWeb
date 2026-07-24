# Changelog

## Unreleased

### Added
- **Tailscale QR manager login** — passwordless `/login/` (QR + continue on device); allowlist via `TAILSCALE_ALLOW_LOGINS`
- **Access split** — public search/read UI; `/admin/` and management APIs require manager session
- **Dependency heartbeat** — dashboard panel + `GET /api/heartbeat/` (internal/external probes)
- **Postgres support** — `DATABASE_DRIVER=pg` + `DATABASE_URL` (lab: `StellarMapDB` on shared Postgres)
- **Light-footprint defaults** — `LIGHT_MODE` (locmem cache, quieter logs, longer UI poll, lean SQLite PRAGMAs)

### Changed
- Settings: env-driven hosts, WhiteNoise for static on host, session cookie name `stellarmap.sid`
- Dashboard / search: poll interval from server; manager login link in nav
- `requirements.txt`: `psycopg2-binary` for Postgres

### Security
- Manager routes gated by middleware; empty Tailscale allowlist denies manager login
- Do not commit `.env`, SQLite dumps, or Postgres passwords
