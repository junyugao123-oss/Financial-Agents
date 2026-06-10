#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PALACE_DIR="${MEMPALACE_PROJECT_PALACE:-$ROOT_DIR/.mempalace/palace}"
WING="${MEMPALACE_PROJECT_WING:-君宇·投研智能体}"

if ! command -v mempalace >/dev/null 2>&1; then
  echo "mempalace CLI is not installed. Install with: uv tool install mempalace" >&2
  exit 1
fi

mempalace --palace "$PALACE_DIR" wake-up --wing "$WING"
