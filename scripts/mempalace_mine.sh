#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PALACE_DIR="${MEMPALACE_PROJECT_PALACE:-$ROOT_DIR/.mempalace/palace}"
WING="${MEMPALACE_PROJECT_WING:-君宇·投研智能体}"
AGENT="${MEMPALACE_AGENT:-codex}"

if ! command -v mempalace >/dev/null 2>&1; then
  echo "mempalace CLI is not installed. Install with: uv tool install mempalace" >&2
  exit 1
fi

cd "$ROOT_DIR"
mkdir -p "$(dirname "$PALACE_DIR")"

paths=(
  "docs"
  "scripts"
  "services/api/app"
  "services/api/tests"
  "apps/web/components"
  "apps/web/lib"
)

for path in "${paths[@]}"; do
  if [ -d "$path" ]; then
    echo "Mining $path into MemPalace wing: $WING"
    mempalace --palace "$PALACE_DIR" mine "$path" --wing "$WING" --agent "$AGENT"
  fi
done

mempalace --palace "$PALACE_DIR" status
