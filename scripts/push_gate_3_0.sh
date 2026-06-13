#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
PUSH_GATE_REPORT_PATH="${PUSH_GATE_REPORT_PATH:-}"
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
    echo "keyword scan for review: $review_count lines found; raw lines suppressed, structured contract runs next"
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

write_release_readiness_report() {
  if [ -z "$PUSH_GATE_REPORT_PATH" ]; then
    echo "release readiness report: skipped; set PUSH_GATE_REPORT_PATH to write a local report"
    return 0
  fi

  local report_dir branch head ahead_count generated_at
  report_dir="$(dirname "$PUSH_GATE_REPORT_PATH")"
  mkdir -p "$report_dir"
  branch="$(git rev-parse --abbrev-ref HEAD)"
  head="$(git rev-parse --short HEAD)"
  ahead_count="$(git rev-list --count origin/main..HEAD 2>/dev/null || echo unknown)"
  generated_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  cat > "$PUSH_GATE_REPORT_PATH" <<REPORT
# Command Center 3 Push Gate Report

- generated_at_utc: $generated_at
- branch: $branch
- head: $head
- origin_ahead_count: $ahead_count
- worktree_clean_check_runs_after_report: true

## Passed Checks

- python_unittest: passed
- desktop_build: passed
- command_center_3_smoke: passed
- data_health_freshness_contract: passed_local_contract_provider_execution_pending
- tushare_acceptance_contract: passed_local_contract_provider_execution_pending
- factor_test_lab_contract: passed_local_contract_provider_execution_pending
- candidate_radar_contract: passed_local_contract_replacement_pending
- motion_viewport_qa_contract: passed_static_contract_visual_run_pending
- motion_browser_qa_runbook: passed_runbook_execution_pending
- diff_whitespace_check: passed
- high_risk_secret_scan: clean
- secret_keyword_review_contract: passed_structured_no_raw_lines
- generated_artifact_scan: clean_or_allowed_assets_only

## Safety Boundaries

- did_not_push: true
- did_not_call_external_providers: true
- did_not_execute_trades: true
- did_not_use_system_python: true
- no_git_add_dot: true

## Scope Notes

- This report is local evidence for the current push gate run.
- A report path inside the repository must be ignored or intentionally staged later; otherwise the final clean-worktree check fails.
- Scaffold, preflight, matrix, mock, and sanitizer checks are not production completion evidence.
REPORT

  echo "release readiness report: $PUSH_GATE_REPORT_PATH"
}

run_step "Python unittest" "$PYTHON_BIN" -m unittest discover -s tests
run_step "Desktop build" bash -c "cd desktop && npm run build"
run_step "Command Center 3 smoke" env PYTHON_BIN="$PYTHON_BIN" scripts/smoke_3_0.sh
run_step "Data Health freshness contract" "$PYTHON_BIN" scripts/data_health_freshness_contract.py
run_step "Tushare acceptance contract" "$PYTHON_BIN" scripts/tushare_acceptance_contract.py
run_step "Factor Test Lab contract" "$PYTHON_BIN" scripts/factor_test_lab_contract.py
run_step "Candidate Radar contract" "$PYTHON_BIN" scripts/candidate_radar_contract.py
run_step "Motion viewport QA contract" "$PYTHON_BIN" scripts/motion_viewport_qa_contract.py
run_step "Motion browser QA runbook" "$PYTHON_BIN" scripts/motion_browser_qa_runbook.py
run_step "Diff whitespace check" git diff --check
run_step "Secret scan" secret_high_risk_scan
run_step "Secret keyword review contract" "$PYTHON_BIN" scripts/secret_keyword_review_contract.py
run_step "Generated artifact scan" artifact_scan
run_step "Release readiness report" write_release_readiness_report
run_step "Clean worktree check" worktree_clean_scan

echo
echo "PASS: Command Center 3 push gate completed. This script did not push, did not call external providers, and did not execute trades."
