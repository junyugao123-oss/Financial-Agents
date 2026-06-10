#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FILES=()
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  while IFS= read -r file; do
    FILES+=("$file")
  done < <(git ls-files --cached --others --exclude-standard)
else
  while IFS= read -r file; do
    FILES+=("$file")
  done < <(find . -type f | sed 's#^\./##')
fi

is_excluded() {
  local file="$1"
  case "$file" in
    .git/*|node_modules/*|apps/*/.next/*|apps/*/node_modules/*|services/*/.pytest_cache/*|.venv*/*|dist/*|build/*)
      return 0
      ;;
    *.png|*.jpg|*.jpeg|*.gif|*.webp|*.ico|*.pdf|*.pyc|*.woff|*.woff2)
      return 0
      ;;
  esac
  return 1
}

findings=()

for file in "${FILES[@]}"; do
  [[ -f "$file" ]] || continue
  is_excluded "$file" && continue
  grep -Iq . "$file" || continue

  while IFS= read -r line; do
    findings+=("$file:$line: possible committed API key")
  done < <(grep -nE 'sk-[A-Za-z0-9_-]{20,}' "$file" || true)

  while IFS=: read -r line_no line_text; do
    value="${line_text#*=}"
    value="${value%%#*}"
    value="${value//\"/}"
    value="${value//\'/}"
    value="$(printf '%s' "$value" | xargs)"
    case "$value" in
      ""|your_rotated_key|your_key_here|changeme|example|placeholder)
        continue
        ;;
      *)
        findings+=("$file:$line_no: DEEPSEEK_API_KEY has a non-placeholder value")
        ;;
    esac
  done < <(grep -nE '(^|[[:space:]])DEEPSEEK_API_KEY=[^[:space:]#]+' "$file" || true)

  case "$file" in
    *.js|*.jsx|*.ts|*.tsx)
      while IFS= read -r line; do
        findings+=("$file:$line: remove console.log/debugger before release")
      done < <(grep -nE '\b(console\.log\s*\(|debugger\b)' "$file" || true)
      ;;
  esac
done

if (( ${#findings[@]} > 0 )); then
  printf 'Repository hygiene audit failed:\n'
  for finding in "${findings[@]}"; do
    printf -- '- %s\n' "$finding"
  done
  exit 1
fi

printf 'Repository hygiene audit passed\n'
