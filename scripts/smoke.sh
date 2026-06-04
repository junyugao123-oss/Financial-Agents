#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
WEB_URL="${WEB_URL:-http://localhost:3001}"

curl -fsS "$API_URL/health" >/dev/null
curl -fsS "$WEB_URL/" >/dev/null

echo "Smoke checks passed"
