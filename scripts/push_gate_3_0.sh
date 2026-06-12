#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "FAIL: expected project Python at $PYTHON_BIN. Do not use system Python for the push gate." >&2
  exit 1
fi

run_step() {
  local label="$1"
  shift
  echo
  echo "==> $label"
  "$@"
}

secret_high_risk_scan() {
  local hits
  hits="$(
    git grep -nE \
      '(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}|(api_key|apikey|token|secret|password)[[:space:]]*=[[:space:]]*["'\''][^"'\'']{12,}["'\''])' \
      -- ':!tests/*' ':!docs/*' ':!*.md' ':!desktop/src-tauri/Cargo.lock' || true
  )"
  if [ -n "$hits" ]; then
    echo "FAIL: high-risk secret-looking values found outside tests/docs:" >&2
    echo "$hits" >&2
    return 1
  fi
  echo "high-risk secret value scan: clean"

  local review_file review_count
  review_file="$(mktemp)"
  rg -n \
    'api_key|token|secret|password|Authorization|Bearer|DEEPSEEK|TUSHARE|GITHUB_TOKEN|AKSHARE|apikey|access_key' \
    server worker storage desktop/src app.py command_center_factor_research.py tests docs scripts \
    > "$review_file" || true
  review_count="$(wc -l < "$review_file" | tr -d ' ')"
  if [ "$review_count" -eq 0 ]; then
    echo "keyword scan for review: clean"
  else
    echo "keyword scan for review: $review_count lines found; showing first 120 for explanation"
    sed -n '1,120p' "$review_file"
    if [ "$review_count" -gt 120 ]; then
      echo "... keyword scan truncated; review full output by running the rg command in scripts/push_gate_3_0.sh"
    fi
  fi
  rm -f "$review_file"
}

artifact_scan() {
  local hits unexpected
  hits="$(
    git ls-files | rg '(^|/)(node_modules|dist|target|__pycache__)(/|$)|\.(parquet|duckdb|sqlite|db|log|env|mov|mp4|png|jpg)$' || true
  )"
  unexpected="$(
    printf '%s\n' "$hits" | awk 'NF && $0 != "desktop/src-tauri/icons/icon.png" {print}'
  )"
  if [ -n "$unexpected" ]; then
    echo "FAIL: tracked generated/data artifacts found:" >&2
    echo "$unexpected" >&2
    return 1
  fi
  if [ -n "$hits" ]; then
    echo "artifact scan allowed tracked assets:"
    printf '%s\n' "$hits"
  else
    echo "artifact scan: clean"
  fi
}

worktree_clean_scan() {
  local status
  status="$(git status --short)"
  if [ -n "$status" ]; then
    echo "FAIL: worktree is not clean:" >&2
    echo "$status" >&2
    return 1
  fi
  echo "worktree: clean"
}

run_step "Python unittest" "$PYTHON_BIN" -m unittest discover -s tests
run_step "Desktop build" bash -c "cd desktop && npm run build"
run_step "Command Center 3 smoke" env PYTHON_BIN="$PYTHON_BIN" scripts/smoke_3_0.sh
run_step "Diff whitespace check" git diff --check
run_step "Secret scan" secret_high_risk_scan
run_step "Generated artifact scan" artifact_scan
run_step "Clean worktree check" worktree_clean_scan

echo
echo "PASS: Command Center 3 push gate completed. This script did not push, did not call external providers, and did not execute trades."
