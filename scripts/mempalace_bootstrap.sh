#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PALACE_DIR="${MEMPALACE_PROJECT_PALACE:-$ROOT_DIR/.mempalace/palace}"

if ! command -v mempalace >/dev/null 2>&1; then
  echo "mempalace CLI is not installed. Install with: uv tool install mempalace" >&2
  exit 1
fi

cd "$ROOT_DIR"
mkdir -p "$(dirname "$PALACE_DIR")"

mempalace --palace "$PALACE_DIR" init "$ROOT_DIR" --yes --no-llm

echo "MemPalace initialized at $PALACE_DIR"
echo "Next: npm run memory:mine"
