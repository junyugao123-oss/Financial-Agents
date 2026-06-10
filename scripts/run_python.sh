#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
elif [[ -x "$ROOT_DIR/.venv-test/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv-test/bin/python"
else
  PYTHON_BIN="python3"
fi

exec "$PYTHON_BIN" "$@"
