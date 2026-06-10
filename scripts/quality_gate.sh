#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
elif [[ -x "$ROOT_DIR/.venv-test/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv-test/bin/python"
else
  PYTHON_BIN="python3"
fi
RUN_LINT="${RUN_LINT:-1}"
RUN_TYPECHECK="${RUN_TYPECHECK:-1}"
RUN_MOBILE_AUDIT="${RUN_MOBILE_AUDIT:-1}"
RUN_MOBILE_E2E="${RUN_MOBILE_E2E:-0}"
RUN_API_TESTS="${RUN_API_TESTS:-1}"
RUN_REPO_HYGIENE="${RUN_REPO_HYGIENE:-1}"
RUN_QUANT_AUDIT="${RUN_QUANT_AUDIT:-1}"
RUN_CODEGRAPH="${RUN_CODEGRAPH:-1}"
RUN_BUILD="${RUN_BUILD:-1}"
RUN_SMOKE="${RUN_SMOKE:-0}"

section() {
  printf "\n==> %s\n" "$1"
}

if [[ "$RUN_LINT" == "1" ]]; then
  section "Frontend lint"
  npm run lint
fi

if [[ "$RUN_TYPECHECK" == "1" ]]; then
  section "Frontend typecheck"
  npm run typecheck
fi

if [[ "$RUN_MOBILE_AUDIT" == "1" ]]; then
  section "Mobile layout contract audit"
  "$PYTHON_BIN" scripts/audit_mobile_layout.py
fi

if [[ "$RUN_MOBILE_E2E" == "1" ]]; then
  section "Mobile end-to-end browser tests"
  npm run test:mobile
fi

if [[ "$RUN_API_TESTS" == "1" ]]; then
  section "Backend tests"
  (cd services/api && "$PYTHON_BIN" -m pytest)
fi

if [[ "$RUN_REPO_HYGIENE" == "1" ]]; then
  section "Repository hygiene audit"
  bash scripts/audit_repo_hygiene.sh
fi

if [[ "$RUN_QUANT_AUDIT" == "1" ]]; then
  section "Quant safety audit"
  "$PYTHON_BIN" scripts/audit_quant_safety.py
fi

if [[ "$RUN_CODEGRAPH" == "1" ]]; then
  section "CodeGraph impact guard"
  bash scripts/codegraph_guard.sh
fi

if [[ "$RUN_BUILD" == "1" ]]; then
  section "Frontend production build"
  npm run build
fi

if [[ "$RUN_SMOKE" == "1" ]]; then
  section "HTTP smoke checks"
  bash scripts/smoke.sh
fi

section "Quality gate passed"
