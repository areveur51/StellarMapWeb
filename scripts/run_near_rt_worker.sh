#!/usr/bin/env bash
# Interest-driven free SDK near-RT worker (PENDING batches).
# Requires CASSANDRA_READ_ONLY=0 and a write-capable Astra token.
set -euo pipefail
cd "$(dirname "$0")/.."
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-StellarMapWeb.settings.settings_base}"
if [[ -f .venv/bin/python ]]; then
  exec .venv/bin/python manage.py run_sdk_near_rt_worker "$@"
fi
exec python manage.py run_sdk_near_rt_worker "$@"
