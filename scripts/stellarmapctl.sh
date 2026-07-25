#!/usr/bin/env bash
# StellarMapWeb control — start | stop | restart | status | logs | migrate | db-status
# Host Python (Django) + optional Docker Compose (Container Manager).
# Structured like ChronoTrace (chronotrctl.sh) and DoqumentWeb (doqumentctl.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${ROOT}/app"
PID_FILE="${ROOT}/stellarmap.pid"
LOG_FILE="${ROOT}/stellarmap.log"
SUPERVISE_PID_FILE="${ROOT}/stellarmap.supervise.pid"
CRON_PID_FILE="${ROOT}/stellarmap.cron.pid"
NEAR_RT_PID_FILE="${ROOT}/stellarmap.near_rt.pid"
ENV_FILE="${APP_DIR}/.env"
VENV_DIR="${APP_DIR}/.venv"
# GrokBuild micromamba (Python 3.10+ for Django 5 when system python is 3.8)
MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-/volume3/GrokBuild/tools/mamba-root}"
MAMBA_ENV_PYTHON="${MAMBA_ROOT_PREFIX}/envs/stellarmapweb/bin/python"
MICROMAMBA_BIN="${MICROMAMBA_BIN:-/volume3/GrokBuild/tools/micromamba/bin/micromamba}"

# Defaults (override via env or .env)
BIND_HOST="${STELLARMAP_BIND:-0.0.0.0}"
HOST_PORT=""

usage() {
  cat <<EOF
Usage: $(basename "$0") {start|stop|restart|status|logs|migrate|db-status|help}

  start       Start StellarMapWeb (Docker Compose preferred; host Python fallback)
  stop        Stop the app (and Docker stack / cron if used)
  restart     Stop then start
  status      Show running state
  logs        Tail ${LOG_FILE} (or docker compose logs)
  migrate     Run Django migrations (host venv)
  db-status   Show env/database mode (SQLite vs Cassandra)

Environment:
  STELLARMAP_PORT   Host port (default: PORT / HOST_PORT from .env or 5090)
  STELLARMAP_BIND   Bind address for host mode (default: 0.0.0.0)
  STELLARMAP_MODE   dev | prod
                      prod → gunicorn (default when available; preferred on NAS)
                      dev  → manage.py runserver (heavier; hot-reload)
  STELLARMAP_PYTHON Python binary (default: app/.venv, then micromamba env, then python3)
  STELLARMAP_CRON=1 Also start run_cron_jobs.py (OFF by default — heavy pipelines)
  STELLARMAP_NEAR_RT_WORKER=1
                    Start free SDK near-RT worker (PENDING only; not full cron).
                    Needs CASSANDRA_READ_ONLY=0 and a write-capable token.
  FORCE_HOST=1      Skip Docker even if available
  SKIP_DEPS=1       Do not pip-install requirements on start
  SKIP_MIGRATE=1    Never migrate on start (default: auto-skip when already applied)
  FORCE_MIGRATE=1   Always migrate on start (even if up to date)
  WORKERS           Gunicorn workers (default: 1 on NAS / LIGHT_MODE)
  THREADS           Gunicorn gthread threads (default: 2)
  LIGHT_MODE=1      Lean cache, quieter logs, slower UI poll (default: 1)
  READY_TIMEOUT     Seconds to wait for port open after start (default: 45)
  SUPERVISE_MAX_RESTARTS / SUPERVISE_STABLE_SECS  Crash loop (defaults 3 / 300)

  Base Python for venv (Django 5 needs 3.10+). On this NAS, preferred order:
    1) STELLARMAP_PYTHON
    2) micromamba env: ${MAMBA_ENV_PYTHON}
    3) python3 on PATH

  Resource policy (always-on NAS): single gunicorn worker, no cron/pipelines
  unless STELLARMAP_CRON=1, LIGHT_MODE=1, DEBUG off when LIGHT_MODE.

App:  ${APP_DIR}
Log:  ${LOG_FILE}
EOF
}

load_env() {
  export_env_file "$ENV_FILE"

  if [[ -n "${STELLARMAP_PORT:-}" ]]; then
    HOST_PORT="$STELLARMAP_PORT"
  else
    HOST_PORT="${PORT:-${HOST_PORT:-5090}}"
  fi
  export PORT="$HOST_PORT"
  export HOST="${HOST:-$BIND_HOST}"
  # Path used by apiApp helpers for secure-connect bundle
  export APP_PATH="${APP_PATH:-$APP_DIR}"
  # Constrained-host defaults: lean always-on (override in .env)
  export LIGHT_MODE="${LIGHT_MODE:-1}"
  export ENV="${ENV:-development}"
  export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-StellarMapWeb.settings}"
  export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost,127.0.0.1,0.0.0.0,*}"
  # Prefer DEBUG=False when LIGHT_MODE (less template/SQL overhead)
  if [[ -z "${DEBUG+x}" || -z "${DEBUG}" ]]; then
    if [[ "$LIGHT_MODE" == "1" || "$LIGHT_MODE" == "true" ]]; then
      export DEBUG=False
    else
      export DEBUG=True
    fi
  fi
  # glibc: cap arena count to reduce RSS fragmentation under long-lived Python
  export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
  export PYTHONUNBUFFERED=1
  export PYTHONOPTIMIZE="${PYTHONOPTIMIZE:-1}"
  export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"
}

find_docker() {
  if [[ -n "${FORCE_HOST:-}" ]]; then
    return 1
  fi
  local candidate=""
  if command -v docker >/dev/null 2>&1; then
    candidate="$(command -v docker)"
  else
    for p in \
      /usr/local/bin/docker \
      /var/packages/ContainerManager/target/usr/bin/docker \
      /var/packages/Docker/target/usr/bin/docker \
      /usr/bin/docker
    do
      if [[ -x "$p" ]]; then
        candidate="$p"
        break
      fi
    done
  fi
  [[ -n "$candidate" ]] || return 1
  # Synology: docker binary exists but socket is root-only → fall back to host mode
  if ! "$candidate" info >/dev/null 2>&1; then
    return 1
  fi
  DOCKER_BIN="$candidate"
  return 0
}

compose() {
  if "$DOCKER_BIN" compose version >/dev/null 2>&1; then
    (cd "$APP_DIR" && "$DOCKER_BIN" compose "$@")
  elif command -v docker-compose >/dev/null 2>&1; then
    (cd "$APP_DIR" && docker-compose "$@")
  else
    (cd "$APP_DIR" && "$DOCKER_BIN" compose "$@")
  fi
}

docker_running() {
  find_docker || return 1
  compose ps --status running 2>/dev/null | grep -qiE 'stellarmapweb|web' && return 0
  "$DOCKER_BIN" ps --format '{{.Names}}' 2>/dev/null | grep -qiE '^stellarmapweb' && return 0
  return 1
}

base_python() {
  # Interpreter used to *create* the project venv (must be 3.10+)
  if [[ -n "${STELLARMAP_PYTHON:-}" && -x "${STELLARMAP_PYTHON}" ]]; then
    echo "$STELLARMAP_PYTHON"
    return 0
  fi
  if [[ -x "$MAMBA_ENV_PYTHON" ]]; then
    echo "$MAMBA_ENV_PYTHON"
    return 0
  fi
  command -v python3
}

python_bin() {
  # Runtime interpreter: prefer project venv
  if [[ -n "${STELLARMAP_PYTHON:-}" && -x "${STELLARMAP_PYTHON}" ]]; then
    # If user points at a full env, use it directly (skip project venv)
    if [[ "${STELLARMAP_PYTHON}" != "${VENV_DIR}/bin/python" ]]; then
      echo "$STELLARMAP_PYTHON"
      return 0
    fi
  fi
  if [[ -x "${VENV_DIR}/bin/python" ]]; then
    echo "${VENV_DIR}/bin/python"
    return 0
  fi
  base_python
}

python_version_ok() {
  local py="$1"
  "$py" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null
}

host_running() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  if pgrep -f "manage.py runserver.*${HOST_PORT:-5090}" >/dev/null 2>&1; then
    return 0
  fi
  if pgrep -f "gunicorn.*StellarMapWeb.wsgi" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

get_host_pid() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "$pid"
      return 0
    fi
  fi
  pgrep -f "manage.py runserver.*${HOST_PORT:-5090}" 2>/dev/null | head -1 \
    || pgrep -f "gunicorn.*StellarMapWeb.wsgi" 2>/dev/null | head -1 \
    || true
}

is_running() {
  docker_running || host_running
}

ensure_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    return 0
  fi
  if [[ -f "${APP_DIR}/.env.example" ]]; then
    echo "Creating ${ENV_FILE} from .env.example ..."
    cp "${APP_DIR}/.env.example" "$ENV_FILE"
  else
    echo "ERROR: missing ${ENV_FILE} — copy app/.env.example to app/.env" >&2
    exit 1
  fi
}

# Source KEY=VAL from a file into the current shell (no re-read of comments/junk)
export_env_file() {
  local f="${1:-$ENV_FILE}"
  [[ -f "$f" ]] || return 0
  set -a
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      # shellcheck disable=SC2163
      export "$line"
    fi
  done <"$f"
  set +a
}

ensure_secret_key() {
  # Avoid rewrite when secret already set (saves disk I/O on every start)
  if [[ -n "${DJANGO_SECRET_KEY:-}" && "$DJANGO_SECRET_KEY" != your-secret-key* && "$DJANGO_SECRET_KEY" != replace-with* ]]; then
    return 0
  fi
  load_env
  if [[ -n "${DJANGO_SECRET_KEY:-}" && "$DJANGO_SECRET_KEY" != your-secret-key* && "$DJANGO_SECRET_KEY" != replace-with* ]]; then
    return 0
  fi
  local gen
  if command -v openssl >/dev/null 2>&1; then
    gen="$(openssl rand -hex 32)"
  else
    gen="$(python3 -c 'import secrets; print(secrets.token_hex(32))' 2>/dev/null || echo "stellarmap-dev-$(date +%s)")"
  fi
  if grep -q '^DJANGO_SECRET_KEY=' "$ENV_FILE" 2>/dev/null; then
    local tmp
    tmp="$(mktemp)"
    sed "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=${gen}|" "$ENV_FILE" >"$tmp"
    mv "$tmp" "$ENV_FILE"
  else
    echo "DJANGO_SECRET_KEY=${gen}" >>"$ENV_FILE"
  fi
  export DJANGO_SECRET_KEY="$gen"
  echo "Generated DJANGO_SECRET_KEY in ${ENV_FILE}"
}

ensure_app_path() {
  # Only rewrite .env when APP_PATH is missing or wrong
  export APP_PATH="$APP_DIR"
  local current=""
  if [[ -f "$ENV_FILE" ]]; then
    current="$(grep '^APP_PATH=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  fi
  if [[ "$current" == "$APP_DIR" ]]; then
    return 0
  fi
  if grep -q '^APP_PATH=' "$ENV_FILE" 2>/dev/null; then
    local tmp
    tmp="$(mktemp)"
    sed "s|^APP_PATH=.*|APP_PATH=${APP_DIR}|" "$ENV_FILE" >"$tmp"
    mv "$tmp" "$ENV_FILE"
  else
    echo "APP_PATH=${APP_DIR}" >>"$ENV_FILE"
  fi
}

# True if port is accepting TCP connections (fast readiness without curl)
port_is_open() {
  local host="${1:-127.0.0.1}"
  local port="${2:-$HOST_PORT}"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$host" "$port" <<'PY' 2>/dev/null
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.35)
try:
    s.connect((host, port))
except Exception:
    sys.exit(1)
finally:
    s.close()
sys.exit(0)
PY
    return $?
  fi
  # Fallback: bash /dev/tcp
  (echo >/dev/tcp/"$host"/"$port") >/dev/null 2>&1
}

wait_for_listen() {
  local port="${1:-$HOST_PORT}"
  # Wall-clock seconds (NAS cold import can be slow)
  local timeout="${READY_TIMEOUT:-45}"
  local start_ts end_ts
  start_ts=$(date +%s)
  end_ts=$((start_ts + timeout))
  while [[ "$(date +%s)" -lt "$end_ts" ]]; do
    if port_is_open 127.0.0.1 "$port"; then
      return 0
    fi
    # Process gone → fail early (do not wait full timeout)
    if [[ -f "$PID_FILE" ]]; then
      local pid
      pid="$(cat "$PID_FILE" 2>/dev/null || true)"
      if [[ -n "${pid:-}" ]] && ! kill -0 "$pid" 2>/dev/null; then
        # Supervise may still be retrying — only fail if supervise also dead
        if [[ -f "$SUPERVISE_PID_FILE" ]]; then
          local sp
          sp="$(cat "$SUPERVISE_PID_FILE" 2>/dev/null || true)"
          if [[ -n "${sp:-}" ]] && ! kill -0 "$sp" 2>/dev/null; then
            return 1
          fi
        else
          return 1
        fi
      fi
    fi
    sleep 0.35
  done
  port_is_open 127.0.0.1 "$port"
}

migrations_newer_than() {
  # Return 0 if any migration .py is newer than marker (needs migrate)
  local marker="$1"
  [[ -f "$marker" ]] || return 0
  # Portable: no -printf required
  local f
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    if [[ "$f" -nt "$marker" ]]; then
      return 0
    fi
  done < <(find "$APP_DIR" -type f -path '*/migrations/*.py' ! -path '*/.venv/*' ! -path '*/__pycache__/*' 2>/dev/null)
  return 1
}

should_run_migrate() {
  if [[ -n "${SKIP_MIGRATE:-}" ]]; then
    return 1
  fi
  if [[ -n "${FORCE_MIGRATE:-}" ]]; then
    return 0
  fi
  local marker="${APP_DIR}/.migrate-ok"
  local sqlite="${APP_DIR}/db.sqlite3"
  # First boot or no DB → migrate
  if [[ ! -f "$sqlite" && ! -f "$marker" ]]; then
    return 0
  fi
  # Marker present and no newer migrations → skip (big win on restart)
  if [[ -f "$marker" ]] && ! migrations_newer_than "$marker"; then
    return 1
  fi
  return 0
}

run_migrate_if_needed() {
  local py="$1"
  if ! should_run_migrate; then
    echo "[start] migrate skip (up to date or SKIP_MIGRATE=1)" | tee -a "$LOG_FILE"
    return 0
  fi
  echo "[start] schema bootstrap (light / constrained host)..." | tee -a "$LOG_FILE"
  # One Python process (avoids multi× cold import cost on NAS).
  # apiApp migration chain is broken under Django 5 (LookupError apiApp) —
  # create managed tables from models, migrate django.contrib, fake apiApp history.
  if (
    cd "$APP_DIR"
    export_env_file "$ENV_FILE"
    export APP_PATH="$APP_DIR"
    export LIGHT_MODE="${LIGHT_MODE:-1}"
    export ENV="${ENV:-development}"
    export DEBUG="${DEBUG:-False}"
    export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-StellarMapWeb.settings}"
    export PATH="${VENV_DIR}/bin:${PATH}"
    export PYTHONDONTWRITEBYTECODE=1
    "$py" - <<'PY' >>"$LOG_FILE" 2>&1
import os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "StellarMapWeb.settings")
import django
django.setup()
from django.core.management import call_command
from django.apps import apps
from django.db import connection

# 1) Built-in apps (auth/admin/sessions) — required for login/admin
for app in ("contenttypes", "auth", "admin", "sessions"):
    try:
        call_command("migrate", app, interactive=False, verbosity=0)
    except Exception as e:
        print(f"[migrate] {app}: {e}")

# 2) Create missing managed tables from current models (handles broken apiApp chain)
existing = set(connection.introspection.table_names())
created = []
with connection.schema_editor() as se:
    for model in apps.get_models():
        opts = model._meta
        if opts.proxy or opts.auto_created or not opts.managed:
            continue
        if opts.db_table in existing:
            continue
        try:
            se.create_model(model)
            existing.add(opts.db_table)
            created.append(opts.label)
        except Exception as e:
            print(f"[sync] skip {opts.label}: {e}")
if created:
    print("[sync] created tables for:", ", ".join(created))
else:
    print("[sync] no new tables")

# 3) Mark apiApp migrations applied so migrate is not re-run forever
try:
    call_command("migrate", "apiApp", fake=True, interactive=False, verbosity=0)
    print("[migrate] apiApp faked")
except Exception as e:
    print(f"[migrate] apiApp fake: {e}")

print("[migrate] bootstrap done")
sys.exit(0)
PY
  ); then
    touch "${APP_DIR}/.migrate-ok"
    echo "[start] schema bootstrap ok" | tee -a "$LOG_FILE"
  else
    echo "[start] schema bootstrap failed (continuing) — see log" | tee -a "$LOG_FILE"
    return 0
  fi
}

ensure_mamba_env() {
  # Create micromamba env stellarmapweb (python 3.11) if missing
  if [[ -x "$MAMBA_ENV_PYTHON" ]]; then
    return 0
  fi
  if [[ ! -x "$MICROMAMBA_BIN" ]]; then
    return 1
  fi
  echo "Creating micromamba env 'stellarmapweb' (python 3.11) ..."
  export MAMBA_ROOT_PREFIX
  "$MICROMAMBA_BIN" create -y -n stellarmapweb python=3.11 pip
  [[ -x "$MAMBA_ENV_PYTHON" ]]
}

ensure_venv() {
  local py
  # Prefer micromamba when system python is too old
  if ! py="$(base_python)"; then
    echo "ERROR: no Python interpreter found" >&2
    exit 1
  fi
  if ! python_version_ok "$py"; then
    if ensure_mamba_env && [[ -x "$MAMBA_ENV_PYTHON" ]]; then
      py="$MAMBA_ENV_PYTHON"
    else
      echo "ERROR: $($py --version 2>&1) is too old (Django 5 needs Python 3.10+)." >&2
      echo "  Install micromamba env: ${MICROMAMBA_BIN} create -n stellarmapweb python=3.11 pip" >&2
      echo "  Or set STELLARMAP_PYTHON=/path/to/python3.11" >&2
      return 1
    fi
  fi

  # Recreate venv if it exists but was built with an old Python
  if [[ -x "${VENV_DIR}/bin/python" ]] && ! python_version_ok "${VENV_DIR}/bin/python"; then
    echo "Removing stale venv (Python < 3.10) at ${VENV_DIR} ..."
    rm -rf "$VENV_DIR"
  fi

  if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtualenv at ${VENV_DIR} with $($py --version 2>&1) ..."
    "$py" -m venv "$VENV_DIR" || {
      echo "ERROR: venv creation failed with $py" >&2
      exit 1
    }
  fi

  if [[ -n "${SKIP_DEPS:-}" ]]; then
    return 0
  fi

  local marker="${VENV_DIR}/.deps-installed"
  local req="${APP_DIR}/requirements.txt"
  local vpy="${VENV_DIR}/bin/python"
  # Fast path: django+gunicorn importable and requirements not newer than marker
  if [[ -x "$vpy" ]] && "$vpy" -c "import django, gunicorn" >/dev/null 2>&1; then
    if [[ -f "$marker" && -f "$req" && ! "$req" -nt "$marker" ]]; then
      return 0
    fi
    if [[ -f "$marker" && -f "$req" && "$req" -nt "$marker" ]]; then
      echo "requirements.txt changed — updating venv deps..."
    elif [[ ! -f "$marker" ]]; then
      # Imports work (manual install) — just stamp marker, skip reinstall
      touch "$marker"
      return 0
    fi
  fi

  if [[ -f "$req" ]]; then
    if [[ ! -f "$marker" ]] || [[ "$req" -nt "$marker" ]] || ! "$vpy" -c "import django" >/dev/null 2>&1; then
      echo "Installing Python dependencies into venv (first boot or requirements changed)..."
      export PIP_DISABLE_PIP_VERSION_CHECK=1
      export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-120}"
      # Prefer wheels; skip pip self-upgrade every start (slow on NAS)
      if ! "${VENV_DIR}/bin/pip" install --prefer-binary -r "$req"; then
        echo "WARNING: pip install failed." >&2
        echo "  Venv python: $($vpy --version 2>&1)" >&2
        echo "  Base python: $($py --version 2>&1)" >&2
        return 1
      fi
      touch "$marker"
    fi
  fi
}

cmd_start_docker() {
  find_docker || return 1
  echo "Starting StellarMapWeb via Docker Compose (web only — no cron scale by default)..."
  export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-change-me}"
  export DEBUG="${DEBUG:-False}"
  export USE_SQLITE="${USE_SQLITE:-True}"
  export LIGHT_MODE="${LIGHT_MODE:-1}"
  # Prefer profile without always-on cron: only `web` service if compose supports it
  if compose config --services 2>/dev/null | grep -qx web; then
    # Scale cron to 0 when present so pipelines do not burn NAS RAM/CPU
    if compose config --services 2>/dev/null | grep -qx cron; then
      compose up -d --build --scale cron=0 web || compose up -d --build web
    else
      compose up -d --build web
    fi
  else
    compose up -d --build
  fi
  sleep 2
  if docker_running; then
    echo "Started StellarMapWeb (Docker, LIGHT_MODE=${LIGHT_MODE})"
    echo "  url:  http://<host>:${HOST_PORT}/  (compose maps container 5000; check docker-compose.yml)"
    echo "  tip:  cron service scaled to 0 — set STELLARMAP_CRON only if you need pipelines"
    return 0
  fi
  echo "ERROR: Docker start may have failed — try: cd ${APP_DIR} && docker compose logs" >&2
  return 1
}

cmd_start_host() {
  local t0 t1
  t0=$(date +%s)

  load_env
  ensure_env_file
  ensure_app_path
  ensure_secret_key
  # One more env load only if secret was just generated
  load_env

  if host_running; then
    echo "StellarMapWeb already running on host (pid $(get_host_pid))"
    echo "  url: http://<host>:${HOST_PORT}/"
    return 0
  fi

  if [[ ! -f "${APP_DIR}/manage.py" ]]; then
    echo "ERROR: missing ${APP_DIR}/manage.py — clone or extract into app/" >&2
    exit 1
  fi

  if ! ensure_venv; then
    echo "ERROR: could not prepare Python venv / dependencies" >&2
    exit 1
  fi

  local py mode workers threads max_restarts stable_secs timeout_s max_req log_level access_log
  py="$(python_bin)"
  mode="${STELLARMAP_MODE:-}"
  # Single worker is the constrained-host default (each worker ≈ full Django RSS)
  workers="${WORKERS:-1}"
  threads="${THREADS:-2}"
  timeout_s="${GUNICORN_TIMEOUT:-60}"
  max_req="${GUNICORN_MAX_REQUESTS:-200}"
  max_restarts="${SUPERVISE_MAX_RESTARTS:-3}"
  stable_secs="${SUPERVISE_STABLE_SECS:-300}"
  log_level="${GUNICORN_LOG_LEVEL:-}"
  if [[ -z "$log_level" ]]; then
    if [[ "${LIGHT_MODE:-1}" == "1" || "${LIGHT_MODE:-}" == "true" ]]; then
      log_level=warning
    else
      log_level=info
    fi
  fi
  # Access log off in light mode (less disk I/O on NAS); errors still logged
  if [[ "${LIGHT_MODE:-1}" == "1" || "${LIGHT_MODE:-}" == "true" ]]; then
    access_log=none
  else
    access_log=-
  fi

  # Auto: prod (gunicorn) when available — lighter than runserver reloader
  if [[ -z "$mode" ]]; then
    if "${py}" -c "import gunicorn" >/dev/null 2>&1; then
      mode=prod
    else
      mode=dev
    fi
  fi

  # Drop strays only if present (avoids pkill + sleep on clean start)
  if pgrep -f "gunicorn.*StellarMapWeb.wsgi" >/dev/null 2>&1 \
    || pgrep -f "manage.py runserver.*${HOST_PORT}" >/dev/null 2>&1; then
    pkill -f "gunicorn.*StellarMapWeb.wsgi" 2>/dev/null || true
    pkill -f "manage.py runserver.*${HOST_PORT}" 2>/dev/null || true
    sleep 0.3
  fi
  rm -f "$PID_FILE"
  mkdir -p "$(dirname "$LOG_FILE")"
  # Cap log growth on constrained disk
  if [[ -f "$LOG_FILE" ]]; then
    local log_bytes
    log_bytes="$(wc -c <"$LOG_FILE" 2>/dev/null || echo 0)"
    if [[ "${log_bytes:-0}" -gt 10485760 ]]; then
      tail -c 1048576 "$LOG_FILE" >"${LOG_FILE}.tmp" 2>/dev/null && mv "${LOG_FILE}.tmp" "$LOG_FILE" || : >"$LOG_FILE"
    fi
  fi
  : >>"$LOG_FILE"

  # Worker heartbeat dir: tmpfs when available (faster than NAS volume)
  local worker_tmp="${GUNICORN_WORKER_TMPDIR:-}"
  if [[ -z "$worker_tmp" ]]; then
    if [[ -d /dev/shm && -w /dev/shm ]]; then
      worker_tmp=/dev/shm
    else
      worker_tmp="${ROOT}/.gunicorn-tmp"
      mkdir -p "$worker_tmp"
    fi
  fi

  echo "Starting StellarMapWeb host (${mode}) on ${BIND_HOST}:${HOST_PORT} (LIGHT_MODE=${LIGHT_MODE:-1}, workers=${workers}, threads=${threads}) ..."

  # Foreground env + migrate BEFORE supervise so readiness only waits for bind
  (
    cd "$APP_DIR"
    export_env_file "$ENV_FILE"
    export APP_PATH="$APP_DIR"
    export PORT="$HOST_PORT"
    export HOST="$BIND_HOST"
    export LIGHT_MODE="${LIGHT_MODE:-1}"
    export ENV="${ENV:-development}"
    export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-StellarMapWeb.settings}"
    if [[ -z "${DEBUG:-}" ]]; then
      if [[ "$LIGHT_MODE" == "1" || "$LIGHT_MODE" == "true" ]]; then
        export DEBUG=False
      else
        export DEBUG=True
      fi
    fi
    export PYTHONUNBUFFERED=1
    export PYTHONOPTIMIZE="${PYTHONOPTIMIZE:-1}"
    export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
    export PATH="${VENV_DIR}/bin:${PATH}"
    export PYTHONDONTWRITEBYTECODE=1
    # Warm restart skips this (largest win after first successful migrate)
    run_migrate_if_needed "$py"
  )

  (
    cd "$APP_DIR"
    export_env_file "$ENV_FILE"
    export APP_PATH="$APP_DIR"
    export PORT="$HOST_PORT"
    export HOST="$BIND_HOST"
    export LIGHT_MODE="${LIGHT_MODE:-1}"
    export ENV="${ENV:-development}"
    export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-StellarMapWeb.settings}"
    if [[ -z "${DEBUG:-}" ]]; then
      if [[ "$LIGHT_MODE" == "1" || "$LIGHT_MODE" == "true" ]]; then
        export DEBUG=False
      else
        export DEBUG=True
      fi
    fi
    export PYTHONUNBUFFERED=1
    export PYTHONOPTIMIZE="${PYTHONOPTIMIZE:-1}"
    export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
    export PATH="${VENV_DIR}/bin:${PATH}"
    export PYTHONDONTWRITEBYTECODE=1

    failures=0
    backoff=2
    while true; do
      started_at=$(date +%s)
      if [[ "$mode" == "prod" ]]; then
        echo "[supervise] $(date -Iseconds 2>/dev/null || date) starting gunicorn workers=${workers} threads=${threads} (failures=${failures}/${max_restarts})" >>"$LOG_FILE"
        # gthread: 1 process + N threads uses far less RAM than N workers
        # Do NOT use --preload with Cassandra/Astra: forked workers inherit a
        # broken CQL session and HVA/lineage queries hang indefinitely.
        # (CLI/test client create a fresh session and work fine.)
        "$py" -m gunicorn \
          --bind "${BIND_HOST}:${HOST_PORT}" \
          --worker-class gthread \
          --workers "$workers" \
          --threads "$threads" \
          --timeout "$timeout_s" \
          --graceful-timeout 15 \
          --keep-alive 2 \
          --max-requests "$max_req" \
          --max-requests-jitter 40 \
          --worker-tmp-dir "$worker_tmp" \
          --log-level "$log_level" \
          --access-logfile "$access_log" \
          --error-logfile - \
          --capture-output \
          StellarMapWeb.wsgi:application >>"$LOG_FILE" 2>&1 &
      else
        echo "[supervise] $(date -Iseconds 2>/dev/null || date) starting runserver (failures=${failures}/${max_restarts})" >>"$LOG_FILE"
        # --noreload: one process only (reloader doubles memory + startup)
        "$py" manage.py runserver --noreload "${BIND_HOST}:${HOST_PORT}" >>"$LOG_FILE" 2>&1 &
      fi
      child=$!
      echo "$child" >"$PID_FILE"
      wait "$child"
      code=$?
      ended_at=$(date +%s)
      ran=$((ended_at - started_at))
      if [[ "$ran" -ge "$stable_secs" ]]; then
        failures=0
        backoff=2
      fi
      failures=$((failures + 1))
      if [[ "$failures" -gt "$max_restarts" ]]; then
        echo "[supervise] $(date -Iseconds 2>/dev/null || date) giving up after ${failures} exits (max ${max_restarts}). code=${code} ran ${ran}s. Fix log then: ./stellarmapctl.sh start" >>"$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
      fi
      echo "[supervise] $(date -Iseconds 2>/dev/null || date) process exited code=${code} after ${ran}s; retry ${failures}/${max_restarts} in ${backoff}s" >>"$LOG_FILE"
      sleep "$backoff"
      if [[ "$backoff" -lt 15 ]]; then
        backoff=$((backoff + 3))
      fi
    done
  ) >/dev/null 2>&1 &
  echo $! >"$SUPERVISE_PID_FILE"

  # Optional background cron / pipeline runner — OFF by default (CPU/network heavy)
  if [[ "${STELLARMAP_CRON:-0}" == "1" ]] && [[ -f "${APP_DIR}/run_cron_jobs.py" ]]; then
    echo "WARNING: STELLARMAP_CRON=1 starts pipeline jobs — high CPU/network on NAS" >&2
    (
      cd "$APP_DIR"
      export_env_file "$ENV_FILE"
      export APP_PATH="$APP_DIR"
      export LIGHT_MODE="${LIGHT_MODE:-1}"
      export PATH="${VENV_DIR}/bin:${PATH}"
      export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
      export PYTHONDONTWRITEBYTECODE=1
      exec "$(python_bin)" run_cron_jobs.py
    ) >>"$LOG_FILE" 2>&1 &
    echo $! >"$CRON_PID_FILE"
    echo "Started cron worker pid=$(cat "$CRON_PID_FILE")"
  fi

  # Optional interest-driven SDK near-RT worker (PENDING batches only — free Horizon)
  if [[ "${STELLARMAP_NEAR_RT_WORKER:-0}" == "1" ]]; then
    echo "Starting near-RT SDK worker (STELLARMAP_NEAR_RT_WORKER=1)…"
    (
      cd "$APP_DIR"
      export_env_file "$ENV_FILE"
      export APP_PATH="$APP_DIR"
      export LIGHT_MODE="${LIGHT_MODE:-1}"
      export PATH="${VENV_DIR}/bin:${PATH}"
      export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
      export PYTHONDONTWRITEBYTECODE=1
      exec "$(python_bin)" manage.py run_sdk_near_rt_worker
    ) >>"$LOG_FILE" 2>&1 &
    echo $! >"$NEAR_RT_PID_FILE"
    echo "Started near-RT worker pid=$(cat "$NEAR_RT_PID_FILE")"
  fi

  # Poll port instead of fixed sleep 3 (faster when app is ready; fails faster when not)
  if wait_for_listen "$HOST_PORT" && host_running; then
    local rss_kb="" hpid
    hpid="$(get_host_pid)"
    rss_kb="$(ps -o rss= -p "$hpid" 2>/dev/null | tr -d ' ' || true)"
    t1=$(date +%s)
    echo "Started StellarMapWeb (host pid ${hpid}, mode=${mode}, workers=${workers} threads=${threads}, LIGHT_MODE=${LIGHT_MODE:-1})"
    echo "  port: ${HOST_PORT}"
    echo "  log:  ${LOG_FILE}"
    echo "  boot: ~$((t1 - t0))s (ctl wall time to listen)"
    if [[ -n "${rss_kb:-}" ]]; then
      echo "  rss:  ~$((rss_kb / 1024)) MB (process only; rises under heavy searches)"
    fi
    echo "  url:  http://<nas-ip>:${HOST_PORT}/"
    echo "  tip:  crash retries: ${max_restarts}; pipelines OFF unless STELLARMAP_CRON=1"
  else
    echo "ERROR: process not listening on :${HOST_PORT} — see ${LOG_FILE}" >&2
    # Tear down supervise so a hung boot does not keep retrying in the background
    if [[ -f "$SUPERVISE_PID_FILE" ]]; then
      local sup
      sup="$(cat "$SUPERVISE_PID_FILE" 2>/dev/null || true)"
      [[ -n "${sup:-}" ]] && kill "$sup" 2>/dev/null || true
      sleep 0.2
      [[ -n "${sup:-}" ]] && kill -9 "$sup" 2>/dev/null || true
    fi
    pkill -f "gunicorn.*StellarMapWeb.wsgi" 2>/dev/null || true
    pkill -f "manage.py runserver.*${HOST_PORT}" 2>/dev/null || true
    rm -f "$PID_FILE" "$SUPERVISE_PID_FILE"
    tail -40 "$LOG_FILE" 2>/dev/null || true
    exit 1
  fi
}

cmd_start() {
  load_env
  ensure_env_file

  if is_running; then
    cmd_status
    return 0
  fi

  if find_docker; then
    if cmd_start_docker; then
      return 0
    fi
    echo "Docker start failed; trying host mode..." >&2
  else
    echo "Docker not available — using host Python mode..."
  fi
  cmd_start_host
}

cmd_stop() {
  local stopped=0

  if find_docker 2>/dev/null; then
    if docker_running || compose ps -q 2>/dev/null | grep -q .; then
      echo "Stopping Docker Compose stack..."
      compose down 2>/dev/null || compose stop 2>/dev/null || true
      stopped=1
    fi
  fi

  # Kill supervisor first so it does not respawn the app
  if [[ -f "$SUPERVISE_PID_FILE" ]]; then
    local sup
    sup="$(cat "$SUPERVISE_PID_FILE" 2>/dev/null || true)"
    if [[ -n "${sup:-}" ]]; then
      kill "$sup" 2>/dev/null || true
      sleep 0.3
      kill -9 "$sup" 2>/dev/null || true
    fi
    rm -f "$SUPERVISE_PID_FILE"
  fi

  if host_running || [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(get_host_pid)"
    if [[ -n "${pid:-}" ]]; then
      echo "Stopping host pid=${pid} ..."
      kill "$pid" 2>/dev/null || true
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
      done
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
    pkill -f "manage.py runserver.*${HOST_PORT:-5090}" 2>/dev/null || true
    pkill -f "gunicorn.*StellarMapWeb.wsgi" 2>/dev/null || true
    pkill -f "${APP_DIR}/manage.py" 2>/dev/null || true
    rm -f "$PID_FILE"
    stopped=1
    echo "Stopped host StellarMapWeb"
  fi

  if [[ -f "$CRON_PID_FILE" ]]; then
    local cpid
    cpid="$(cat "$CRON_PID_FILE" 2>/dev/null || true)"
    if [[ -n "${cpid:-}" ]]; then
      kill "$cpid" 2>/dev/null || true
      kill -9 "$cpid" 2>/dev/null || true
    fi
    pkill -f "${APP_DIR}/run_cron_jobs.py" 2>/dev/null || true
    rm -f "$CRON_PID_FILE"
  fi

  if [[ -f "$NEAR_RT_PID_FILE" ]]; then
    local npid
    npid="$(cat "$NEAR_RT_PID_FILE" 2>/dev/null || true)"
    if [[ -n "${npid:-}" ]]; then
      kill "$npid" 2>/dev/null || true
      kill -9 "$npid" 2>/dev/null || true
    fi
    pkill -f "run_sdk_near_rt_worker" 2>/dev/null || true
    rm -f "$NEAR_RT_PID_FILE"
    echo "Stopped near-RT SDK worker"
  fi

  if [[ "$stopped" -eq 0 ]]; then
    echo "StellarMapWeb is not running"
    rm -f "$PID_FILE" "$SUPERVISE_PID_FILE" "$CRON_PID_FILE" "$NEAR_RT_PID_FILE"
  fi
}

cmd_status() {
  load_env
  if docker_running; then
    echo "StellarMapWeb is running (Docker)"
    echo "  port: ${HOST_PORT} (see docker-compose.yml for mapping)"
    echo "  LIGHT_MODE=${LIGHT_MODE:-1}"
    echo "  url:  http://<host>:${HOST_PORT}/"
    return 0
  fi
  if host_running; then
    local pid rss_kb
    pid="$(get_host_pid)"
    rss_kb="$(ps -o rss= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
    echo "StellarMapWeb is running (host pid ${pid})"
    echo "  port: ${HOST_PORT}"
    echo "  log:  ${LOG_FILE}"
    echo "  LIGHT_MODE=${LIGHT_MODE:-1} ENV=${ENV:-} DEBUG=${DEBUG:-}"
    if [[ -n "${rss_kb:-}" ]]; then
      echo "  rss:  ~$((rss_kb / 1024)) MB"
    fi
    echo "  url:  http://<host>:${HOST_PORT}/"
    ps -o pid,%cpu,%mem,rss,etime,cmd -p "$pid" 2>/dev/null || true
    # Show worker children if gunicorn master
    pgrep -P "$pid" >/dev/null 2>&1 && ps -o pid,rss,etime,cmd --ppid "$pid" 2>/dev/null || true
    return 0
  fi
  echo "StellarMapWeb is stopped"
  rm -f "$PID_FILE"
}

cmd_restart() {
  cmd_stop
  sleep 1
  cmd_start
}

cmd_logs() {
  if find_docker && docker_running; then
    compose logs -f --tail="${1:-100}"
  else
    touch "$LOG_FILE"
    tail -n "${1:-100}" -f "$LOG_FILE"
  fi
}

cmd_migrate() {
  load_env
  ensure_env_file
  ensure_app_path
  ensure_secret_key
  load_env
  ensure_venv || exit 1
  local py
  py="$(python_bin)"
  echo "Running migrations with ${py} ..."
  (
    cd "$APP_DIR"
    set -a
    while IFS= read -r line || [[ -n "$line" ]]; do
      case "$line" in
        ''|\#*) continue ;;
      esac
      if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
        # shellcheck disable=SC2163
        export "$line"
      fi
    done < "$ENV_FILE"
    set +a
    export APP_PATH="$APP_DIR"
    export PATH="${VENV_DIR}/bin:${PATH}"
    exec "$py" manage.py migrate --noinput
  )
}

cmd_db_status() {
  load_env
  echo "ENV=${ENV:-development}"
  echo "APP_PATH=${APP_PATH:-$APP_DIR}"
  echo "DEBUG=${DEBUG:-}"
  echo "DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-StellarMapWeb.settings}"
  if [[ -n "${ASTRA_DB_TOKEN:-}${ASTRA_DB_APPLICATION_TOKEN:-}" ]] && \
     [[ "${ASTRA_DB_TOKEN:-${ASTRA_DB_APPLICATION_TOKEN:-}}" != placeholder* ]]; then
    echo "Database mode: Cassandra/Astra likely (token set)"
    echo "  CASSANDRA_KEYSPACE=${CASSANDRA_KEYSPACE:-${ASTRA_DB_KEYSPACE:-}}"
    echo "  CASSANDRA_DB_NAME=${CASSANDRA_DB_NAME:-}"
  else
    echo "Database mode: SQLite (development / no Astra token)"
    local sqlite_path="${APP_DIR}/db.sqlite3"
    if [[ -f "$sqlite_path" ]]; then
      echo "  sqlite: ${sqlite_path} ($(du -sh "$sqlite_path" 2>/dev/null | awk '{print $1}'))"
    else
      echo "  sqlite: ${sqlite_path} (missing — will be created on migrate/start)"
    fi
  fi
  local bundle="${APP_DIR}/secure-connect-stellarmapwebastradb.zip"
  if [[ -f "$bundle" ]]; then
    echo "  secure-connect bundle: present"
  else
    echo "  secure-connect bundle: missing (needed for Astra)"
  fi
}

case "${1:-}" in
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  restart) cmd_restart ;;
  status)  cmd_status ;;
  logs)
    shift || true
    cmd_logs "${1:-100}"
    ;;
  migrate) cmd_migrate ;;
  db-status) cmd_db_status ;;
  help|-h|--help) usage ;;
  *)
    usage >&2
    exit 1
    ;;
esac
