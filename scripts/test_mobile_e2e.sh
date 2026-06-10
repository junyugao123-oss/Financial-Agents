#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WEB_PORT="${WEB_PORT:-3120}"
WEB_URL="${WEB_URL:-http://127.0.0.1:${WEB_PORT}}"
LOG_DIR="${ROOT_DIR}/test-results/mobile-e2e-logs"
SERVER_MODE="${MOBILE_E2E_SERVER_MODE:-production}"
WEB_PID=""

mkdir -p "$LOG_DIR"

if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
elif [[ -x "$ROOT_DIR/.venv-test/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv-test/bin/python"
else
  PYTHON_BIN="python3"
fi

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempts="${3:-90}"
  local quiet="${4:-0}"

  for _ in $(seq 1 "$attempts"); do
    if "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1; then
import sys
import urllib.request

url = sys.argv[1]
with urllib.request.urlopen(url, timeout=2) as response:
    if response.status < 500:
        raise SystemExit(0)
raise SystemExit(1)
PY
      return 0
    fi
    sleep 1
  done

  if [[ "$quiet" != "1" ]]; then
    echo "Timed out waiting for ${label}: ${url}" >&2
  fi
  return 1
}

cleanup() {
  local status="$?"
  if [[ -n "$WEB_PID" ]] && kill -0 "$WEB_PID" >/dev/null 2>&1; then
    kill "$WEB_PID" >/dev/null 2>&1 || true
    wait "$WEB_PID" >/dev/null 2>&1 || true
  fi
  if [[ "$status" != "0" ]]; then
    if [[ -f "$LOG_DIR/web.log" ]]; then
      echo "" >&2
      echo "Mobile E2E failed. Recent web log:" >&2
      tail -80 "$LOG_DIR/web.log" >&2 || true
    fi
  fi
  exit "$status"
}

trap cleanup EXIT

if wait_for_url "${WEB_URL}/?v=mobile-e2e#start" "existing web server" 2 1; then
  WEB_PID=""
else
  if [[ "$SERVER_MODE" == "production" ]]; then
    if [[ ! -f "$ROOT_DIR/apps/web/.next/standalone/apps/web/server.js" ]]; then
      npm run build >"$LOG_DIR/build.log" 2>&1
    fi
    (
      cd "$ROOT_DIR/apps/web"
      API_PROXY_TARGET="${API_PROXY_TARGET:-http://127.0.0.1:65535}" \
        HOSTNAME=127.0.0.1 \
        PORT="$WEB_PORT" \
        node .next/standalone/apps/web/server.js
    ) >"$LOG_DIR/web.log" 2>&1 &
  else
    API_PROXY_TARGET="${API_PROXY_TARGET:-http://127.0.0.1:65535}" \
      npm --workspace apps/web run dev -- --hostname 127.0.0.1 --port "$WEB_PORT" \
      >"$LOG_DIR/web.log" 2>&1 &
  fi
  WEB_PID="$!"

  wait_for_url "${WEB_URL}/?v=mobile-e2e#start" "Next.js mobile test server"
fi

WEB_URL="$WEB_URL" npx playwright test --config playwright.config.ts "$@"
