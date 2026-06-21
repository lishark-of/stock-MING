#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
PUSH_GATE_REPORT_PATH="${PUSH_GATE_REPORT_PATH:-}"
LOCAL_PUSH_GATE_RECEIPT_PATH="${LOCAL_PUSH_GATE_RECEIPT_PATH:-.stock_ming_3/release_gate/local_push_gate_run_receipt.json}"
DESKTOP_BUILD_OUT_DIR="${DESKTOP_BUILD_OUT_DIR:-${TMPDIR:-/tmp}/stock-ming-command-center-3-vite-build}"
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

run_local_contract_step() {
  local label="$1"
  local script_path="$2"
  local allowed_blockers="$3"
  local contract_json
  contract_json="$(mktemp)"
  echo
  echo "==> $label"
  set +e
  "$PYTHON_BIN" "$script_path" --json > "$contract_json"
  local contract_status=$?
  set -e
  "$PYTHON_BIN" - "$contract_json" "$allowed_blockers" "$contract_status" <<'PY'
import json
import sys
from pathlib import Path

contract_path, allowed_csv, status = sys.argv[1:4]
payload = json.loads(Path(contract_path).read_text(encoding="utf-8"))
allowed = {item for item in allowed_csv.split(",") if item}
blockers = set(payload.get("blockers") or [])
unexpected = blockers - allowed
if unexpected:
    print(f"FAIL: unexpected contract blockers: {sorted(unexpected)}", file=sys.stderr)
    raise SystemExit(1)
if int(status) != 0 and not blockers:
    print("FAIL: contract exited non-zero without structured blockers", file=sys.stderr)
    raise SystemExit(1)
for key in ("external_calls_triggered", "tushare_called", "deepseek_called", "github_called"):
    if payload.get(key):
        print(f"FAIL: {key} became true", file=sys.stderr)
        raise SystemExit(1)
if payload.get("does_not_execute_trades") is not True:
    print("FAIL: does_not_execute_trades is not true", file=sys.stderr)
    raise SystemExit(1)
if "does_not_modify_strategy_action" in payload and payload.get("does_not_modify_strategy_action") is not True:
    print("FAIL: does_not_modify_strategy_action is not true", file=sys.stderr)
    raise SystemExit(1)
if payload.get("contains_secret") is True:
    print("FAIL: contract reported contains_secret", file=sys.stderr)
    raise SystemExit(1)
status_label = payload.get("status", "unknown")
if blockers:
    print(f"{Path(contract_path).name}: {status_label}; allowed production-pending blockers: {sorted(blockers)}")
else:
    print(f"{Path(contract_path).name}: {status_label}; blockers: 0")
PY
  rm -f "$contract_json"
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
- migration_principle_docs_guard: passed_no_blind_streamlit_copy_policy_and_commit_checkpoint_surfaces
- desktop_build: passed
- command_center_3_smoke: passed
- data_health_freshness_contract: passed_local_contract_provider_execution_pending
- tushare_acceptance_contract: passed_local_contract_provider_execution_pending
- bootstrap_runtime_contract: passed_local_contract_provider_execution_pending
- tushare_deepseek_linkage_contract: passed_local_linkage_contract_execution_pending
- factor_test_lab_contract: passed_local_contract_provider_execution_pending
- factor_universe_contract: passed_local_contract_read_plan_execution_pending
- deepseek_governance_contract: passed_local_contract_provider_benchmark_pending
- next_session_map_contract: passed_local_contract_streamlit_parity_pending
- candidate_radar_contract: passed_local_contract_replacement_pending
- candidate_radar_contract: passed_or_known_production_pending_local_contract
- candidate_radar_browser_qa_runbook: passed_runbook_execution_pending
- storage_contract: passed_local_contract_physical_migration_pending
- storage_contract: passed_or_known_physical_migration_pending_local_contract
- worker_contract: worker_contract_passed
- worker_contract: passed_or_known_runtime_evidence_pending_local_contract
- tauri_desktop_contract: passed_local_contract_package_validation_pending
- streamlit_legacy_contract: passed_local_contract_retirement_pending
- trade_isolation_contract: passed_local_contract_real_trading_disconnected
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
- local_gate_pass_is_not_remote_ci: true
- remote_actions_status_known: false
- latest_remote_run_verified_green: false

## Scope Notes

- This report is local evidence for the current push gate run.
- Local gate pass is not remote CI evidence; release remains blocked until the matching remote Actions run is inspected green or failure logs are reviewed.
- A report path inside the repository must be ignored or intentionally staged later; otherwise the final clean-worktree check fails.
- Scaffold, preflight, matrix, mock, and sanitizer checks are not production completion evidence.
REPORT

  echo "release readiness report: $PUSH_GATE_REPORT_PATH"
}

write_local_push_gate_run_receipt() {
  local receipt_path receipt_dir branch head head_full ahead_count generated_at
  receipt_path="$LOCAL_PUSH_GATE_RECEIPT_PATH"
  receipt_dir="$(dirname "$receipt_path")"
  mkdir -p "$receipt_dir"
  branch="$(git rev-parse --abbrev-ref HEAD)"
  head="$(git rev-parse --short HEAD)"
  head_full="$(git rev-parse HEAD)"
  ahead_count="$(git rev-list --count origin/main..HEAD 2>/dev/null || echo unknown)"
  generated_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  "$PYTHON_BIN" - "$receipt_path" "$generated_at" "$branch" "$head" "$head_full" "$ahead_count" "$PUSH_GATE_REPORT_PATH" <<'PY'
import json
import sys
from pathlib import Path

receipt_path, generated_at, branch, head, head_full, ahead_count, report_path = sys.argv[1:8]
payload = {
    "schema_version": "command_center_3_local_push_gate_run_receipt.v1",
    "status": "local_push_gate_passed_current_head",
    "scope": "ignored_local_push_gate_run_receipt_no_push_no_github_api",
    "generated_at_utc": generated_at,
    "branch": branch,
    "head": head,
    "head_full": head_full,
    "origin_ahead_count": ahead_count,
    "report_path": report_path,
    "checks": [
        "python_unittest",
        "migration_principle_docs_guard",
        "desktop_build",
        "command_center_3_smoke",
        "data_health_freshness_contract",
        "tushare_acceptance_contract",
        "bootstrap_runtime_contract",
        "tushare_deepseek_linkage_contract",
        "factor_test_lab_contract",
        "factor_universe_contract",
        "deepseek_governance_contract",
        "next_session_map_contract",
        "candidate_radar_contract",
        "candidate_radar_browser_qa_runbook",
        "storage_contract",
        "worker_contract",
        "tauri_desktop_contract",
        "streamlit_legacy_contract",
        "trade_isolation_contract",
        "motion_viewport_qa_contract",
        "motion_browser_qa_runbook",
        "diff_whitespace_check",
        "high_risk_secret_scan",
        "secret_keyword_review_contract",
        "generated_artifact_scan",
        "release_readiness_report",
        "clean_worktree_check",
    ],
    "did_not_push": True,
    "git_add_dot_used": False,
    "external_calls_triggered": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "github_api_called": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
    "contains_secret": False,
    "local_gate_pass_is_not_ci_status": True,
    "remote_actions_status_known": False,
    "latest_remote_run_verified_green": False,
    "remote_ci_status_note": "local push gate pass is not remote CI green; inspect matching remote Actions run before release.",
}
path = Path(receipt_path)
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  echo "local push gate run receipt: $receipt_path"
}

run_step "Python unittest" "$PYTHON_BIN" -m unittest discover -s tests
run_step "Migration principle docs guard" "$PYTHON_BIN" -m unittest tests.test_command_center_migration_principles
run_step "Desktop build" env DESKTOP_BUILD_OUT_DIR="$DESKTOP_BUILD_OUT_DIR" bash -c 'cd desktop && npm run build -- --configLoader runner --outDir "$DESKTOP_BUILD_OUT_DIR" --emptyOutDir'
run_step "Command Center 3 smoke" env PYTHON_BIN="$PYTHON_BIN" scripts/smoke_3_0.sh
run_step "Data Health freshness contract" "$PYTHON_BIN" scripts/data_health_freshness_contract.py
run_step "Tushare acceptance contract" "$PYTHON_BIN" scripts/tushare_acceptance_contract.py
run_step "Bootstrap runtime contract" "$PYTHON_BIN" scripts/bootstrap_runtime_contract.py
run_step "Tushare DeepSeek linkage contract" "$PYTHON_BIN" scripts/tushare_deepseek_linkage_contract.py
run_step "Factor Test Lab contract" run_local_contract_step "Factor Test Lab contract" scripts/factor_test_lab_contract.py "provider_small_pool_execution_recipe_is_local_pending,provider_small_pool_execution_request_is_local_scope_bound,factor_test_durable_evidence_recipe_is_local_production_pending"
run_step "Factor universe contract" "$PYTHON_BIN" scripts/factor_universe_contract.py
run_step "DeepSeek governance contract" "$PYTHON_BIN" scripts/deepseek_governance_contract.py
run_step "Next-session map contract" "$PYTHON_BIN" scripts/next_session_map_contract.py
run_step "Candidate Radar contract" run_local_contract_step "Candidate Radar contract" scripts/candidate_radar_contract.py "candidate_radar_full_pool_worker_fallback_is_local_route_shape_only,candidate_radar_deep_scan_worker_fallback_is_local_route_shape_only,candidate_radar_production_replacement_review_is_local_production_blocked,candidate_radar_production_promotion_dry_run_is_scope_bound_local_only,candidate_radar_legacy_retirement_review_is_local_retirement_blocked,candidate_radar_production_promotion_review_is_local_production_blocked,candidate_radar_durable_evidence_recipe_is_local_production_pending,candidate_radar_production_stage_scope_manifest_is_complete_and_pending"
run_step "Candidate Radar browser QA runbook" "$PYTHON_BIN" scripts/candidate_radar_browser_qa_runbook.py
run_step "Storage contract" run_local_contract_step "Storage contract" scripts/storage_contract.py "physical_execution_phase_a_is_local_direct_evidence_not_production,physical_durable_evidence_recipe_is_local_pending"
run_step "Worker contract" run_local_contract_step "Worker contract" scripts/worker_contract.py "worker_runtime_evidence_stage_scope_manifest_is_complete_and_pending"
run_step "Tauri desktop contract" "$PYTHON_BIN" scripts/tauri_desktop_contract.py
run_step "Streamlit legacy contract" "$PYTHON_BIN" scripts/streamlit_legacy_contract.py
run_step "Trade isolation contract" "$PYTHON_BIN" scripts/trade_isolation_contract.py
run_step "Motion viewport QA contract" "$PYTHON_BIN" scripts/motion_viewport_qa_contract.py
run_step "Motion browser QA runbook" "$PYTHON_BIN" scripts/motion_browser_qa_runbook.py
run_step "Diff whitespace check" git diff --check
run_step "Secret scan" secret_high_risk_scan
run_step "Secret keyword review contract" "$PYTHON_BIN" scripts/secret_keyword_review_contract.py
run_step "Generated artifact scan" artifact_scan
run_step "Release readiness report" write_release_readiness_report
run_step "Clean worktree check" worktree_clean_scan
run_step "Local push gate run receipt" write_local_push_gate_run_receipt

echo
echo "PASS: Command Center 3 push gate completed. This script did not push, did not call external providers, and did not execute trades."
