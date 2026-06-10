#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v codegraph >/dev/null 2>&1; then
  echo "CodeGraph not installed; skipping local code intelligence check."
  echo "Install later with: curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh"
  exit 0
fi

if [[ ! -d "$ROOT_DIR/.codegraph" ]]; then
  echo "CodeGraph index not initialized; skipping local code intelligence check."
  echo "Initialize with: codegraph init -i \"$ROOT_DIR\""
  exit 0
fi

section() {
  printf "\n==> %s\n" "$1"
}

section "CodeGraph index status"
codegraph status "$ROOT_DIR"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  changed_files="$(git diff --name-only --diff-filter=ACMR HEAD -- . ':!.codegraph/**' || true)"
  if [[ -n "$changed_files" ]]; then
    section "CodeGraph affected-test hints"
    printf '%s\n' "$changed_files" | codegraph affected --path "$ROOT_DIR" --stdin --quiet || true
  else
    section "CodeGraph affected-test hints"
    echo "No changed files detected for affected-test analysis."
  fi
fi
