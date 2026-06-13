#!/usr/bin/env python3
"""Validate the local LTG-13 Candidate Radar contract.

This push-gate guard is not a production radar scan. It reads local cache and
builds local plan-only contracts to prevent quick scans, full-pool plans,
deep-scan plans, no-feature-loss QA, replacement triage, and result-delta
clarity from being mistaken for production radar replacement or buy signals.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import candidate_service, packet_service, task_service  # noqa: E402


REQUIRED_TASK_TYPES = {
    "run_candidate_radar_quick_scan",
    "run_candidate_radar_full_pool_plan",
    "run_candidate_radar_deep_scan_plan",
}
REQUIRED_NO_FEATURE_LOSS_GAPS = {
    "browser_performance_trace_pending",
    "full_pool_execution_pending",
    "deep_scan_execution_pending",
    "provider_backed_acceptance_pending",
}
REQUIRED_REPLACEMENT_GAPS = {
    "browser_visual_delta_qa",
    "browser_performance_trace",
    "full_pool_worker_execution",
    "deep_scan_execution",
    "provider_backed_acceptance",
}


def _row(criterion: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "evidence": evidence,
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _flag_false(contract: dict[str, Any], *keys: str) -> bool:
    return all(contract.get(key) is False for key in keys)


def _task_catalog_rows() -> dict[str, dict[str, Any]]:
    return {
        str(row.get("task_type") or ""): dict(row)
        for row in task_service.TASK_CATALOG
        if isinstance(row, dict) and row.get("task_type") in REQUIRED_TASK_TYPES
    }


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def _snapshot_map() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = candidate_service._safe_value(snapshot)
    return safe_snapshot if isinstance(safe_snapshot, dict) else {}


def build_contract() -> dict[str, Any]:
    now = "2026-06-13T10:00:00"
    snapshot_map = _snapshot_map()
    cache_packet = candidate_service.read_candidate_radar_cache()
    full_pool_plan = candidate_service._build_full_pool_scan_plan(snapshot_map, {}, now=now)
    deep_scan_plan = candidate_service._build_deep_scan_plan(snapshot_map, {}, now=now)
    plan_packet = candidate_service._build_candidate_radar_packet(
        snapshot_map,
        mode="local_contract_plan",
        cache_source="local_contract",
        scan_mode="deep_scan_plan",
        request_params_safe={"plan_only": True, "external_sources_allowed": False},
        full_pool_scan_plan=full_pool_plan,
        deep_scan_plan=deep_scan_plan,
    )
    readiness = _dict(cache_packet.get("fast_scan_readiness_audit"))
    runtime_budget = _dict(cache_packet.get("fast_scan_runtime_budget_contract"))
    no_loss = _dict(cache_packet.get("no_feature_loss_acceptance_contract"))
    no_loss_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(cache_packet.get("no_feature_loss_acceptance_rows"))
        if isinstance(row, dict)
    }
    triage = _dict(cache_packet.get("replacement_gap_triage_contract"))
    triage_rows = {
        str(row.get("gap_key") or ""): row
        for row in _list(cache_packet.get("replacement_gap_triage_rows"))
        if isinstance(row, dict)
    }
    result_delta = _dict(cache_packet.get("result_delta_clarity_contract"))
    policy = _dict(cache_packet.get("policy"))
    task_rows = _task_catalog_rows()
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/candidate_radar_contract.py")

    rows = [
        _row(
            "cache_get_is_read_only_no_scan",
            cache_packet.get("packet_key") == candidate_service.PACKET_KEY
            and cache_packet.get("cache_only") is True
            and cache_packet.get("read_only") is True
            and policy.get("does_not_scan_market") is True
            and policy.get("quick_scan_reads_cache_only") is True
            and policy.get("post_task_required_for_scan") is True
            and _flag_false(cache_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and cache_packet.get("does_not_execute_trades") is True
            and cache_packet.get("does_not_modify_strategy_action") is True,
            "GET candidate radar cache must remain local/read-only and must not start market scans or provider/model calls.",
        ),
        _row(
            "task_catalog_button_gates_scan_modes",
            set(task_rows) == REQUIRED_TASK_TYPES
            and task_rows["run_candidate_radar_quick_scan"].get("route") == "POST /api/candidate-radar/scan-quick"
            and task_rows["run_candidate_radar_quick_scan"].get("possible_external_sources") == []
            and set(task_rows["run_candidate_radar_quick_scan"].get("scan_modes") or []) == candidate_service.SUPPORTED_LOCAL_SCAN_MODES
            and task_rows["run_candidate_radar_full_pool_plan"].get("route") == "POST /api/candidate-radar/full-pool-plan"
            and task_rows["run_candidate_radar_full_pool_plan"].get("plan_only") is True
            and task_rows["run_candidate_radar_full_pool_plan"].get("full_pool_scan_done") is False
            and task_rows["run_candidate_radar_deep_scan_plan"].get("route") == "POST /api/candidate-radar/deep-scan-plan"
            and task_rows["run_candidate_radar_deep_scan_plan"].get("plan_only") is True
            and task_rows["run_candidate_radar_deep_scan_plan"].get("deep_scan_done") is False,
            "Candidate radar scan modes must stay button-gated local tasks; full-pool/deep-scan entries are plan-only.",
        ),
        _row(
            "fast_scan_readiness_is_local_pending",
            readiness.get("schema_version") == "candidate_radar_fast_scan_readiness.v1"
            and readiness.get("status") == "fast_scan_local_ready_full_pool_pending"
            and readiness.get("local_fast_scan_ready") is True
            and readiness.get("production_radar_replacement_complete") is False
            and readiness.get("full_pool_scan_done") is False
            and readiness.get("deep_scan_done") is False
            and readiness.get("provider_backed_acceptance_done") is False
            and _flag_false(readiness, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and readiness.get("does_not_execute_trades") is True
            and readiness.get("does_not_modify_strategy_action") is True,
            "Fast scan readiness can be locally ready only while full-pool, deep-scan, and provider acceptance remain pending.",
        ),
        _row(
            "runtime_budget_is_static_not_browser_trace",
            runtime_budget.get("schema_version") == "candidate_radar_fast_scan_runtime_budget.v1"
            and runtime_budget.get("status") == "fast_scan_runtime_budget_ready"
            and runtime_budget.get("browser_performance_trace_done") is False
            and runtime_budget.get("full_pool_scan_done") is False
            and runtime_budget.get("deep_scan_done") is False
            and runtime_budget.get("cache_get_starts_scan") is False
            and runtime_budget.get("page_render_starts_scan") is False,
            "Runtime budget contract is static/local and cannot be treated as browser performance proof.",
        ),
        _row(
            "no_feature_loss_is_local_not_replacement",
            no_loss.get("schema_version") == "candidate_radar_no_feature_loss_acceptance.v1"
            and no_loss.get("status") == "no_feature_loss_acceptance_local_ready_production_pending"
            and no_loss.get("local_no_feature_loss_contract_ready") is True
            and no_loss.get("production_radar_replacement_complete") is False
            and no_loss.get("legacy_fallback_required") is True
            and no_loss.get("full_pool_scan_done") is False
            and no_loss.get("deep_scan_done") is False
            and no_loss.get("provider_backed_acceptance_done") is False
            and no_loss.get("browser_performance_trace_done") is False
            and int(no_loss.get("production_blocker_count") or 0) > 0
            and all(_dict(no_loss_rows.get(key)).get("blocks_production_replacement") is True for key in REQUIRED_NO_FEATURE_LOSS_GAPS)
            and _flag_false(no_loss, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and no_loss.get("candidate_is_not_buy_instruction") is True,
            "No-feature-loss QA is visible locally, but production radar replacement and legacy retirement must stay blocked.",
        ),
        _row(
            "replacement_gap_triage_blocks_legacy_retirement",
            triage.get("schema_version") == "candidate_radar_replacement_gap_triage.v1"
            and triage.get("status") == "replacement_gap_triage_local_ready_legacy_retirement_blocked"
            and triage.get("local_triage_ready") is True
            and triage.get("legacy_retirement_ready") is False
            and triage.get("production_radar_replacement_complete") is False
            and triage.get("legacy_fallback_required") is True
            and int(triage.get("blocking_gap_count") or 0) > 0
            and all(_dict(triage_rows.get(key)).get("blocks_legacy_retirement") is True for key in REQUIRED_REPLACEMENT_GAPS)
            and _flag_false(triage, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Replacement-gap triage must keep legacy radar retirement blocked until browser/performance/full/deep/provider gaps are resolved.",
        ),
        _row(
            "result_delta_clarity_is_local_not_visual_qa",
            result_delta.get("schema_version") == "candidate_radar_result_delta_clarity.v1"
            and result_delta.get("local_result_delta_clarity_ready") is True
            and result_delta.get("production_radar_replacement_complete") is False
            and result_delta.get("browser_visual_delta_qa_done") is False
            and _flag_false(result_delta, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and result_delta.get("does_not_execute_trades") is True
            and result_delta.get("does_not_modify_strategy_action") is True,
            "Result-delta clarity may be locally ready; browser visual delta QA and production replacement must remain pending.",
        ),
        _row(
            "full_pool_plan_is_plan_only",
            full_pool_plan.get("schema_version") == "candidate_radar_full_pool_plan.v1"
            and full_pool_plan.get("status") == "full_pool_plan_ready"
            and full_pool_plan.get("full_pool_scan_done") is False
            and full_pool_plan.get("full_pool_validation_done") is False
            and full_pool_plan.get("worker_task_required") is True
            and full_pool_plan.get("page_render_starts_full_pool") is False
            and full_pool_plan.get("cache_get_starts_full_pool") is False
            and full_pool_plan.get("provider_refresh_executed") is False
            and full_pool_plan.get("candidate_scoring_executed") is False
            and full_pool_plan.get("candidate_packet_written_by_plan") is False
            and _flag_false(full_pool_plan, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and full_pool_plan.get("candidate_is_not_buy_instruction") is True,
            "Full-pool plan must remain plan-only: no market scan, provider refresh, candidate scoring, or packet write.",
        ),
        _row(
            "deep_scan_plan_is_plan_only",
            deep_scan_plan.get("schema_version") == "candidate_radar_deep_scan_plan.v1"
            and deep_scan_plan.get("status") == "deep_scan_plan_ready"
            and deep_scan_plan.get("deep_scan_done") is False
            and deep_scan_plan.get("deep_scan_validation_done") is False
            and deep_scan_plan.get("page_render_starts_deep_scan") is False
            and deep_scan_plan.get("cache_get_starts_deep_scan") is False
            and deep_scan_plan.get("provider_refresh_executed") is False
            and deep_scan_plan.get("candidate_scoring_executed") is False
            and deep_scan_plan.get("candidate_packet_written_by_plan") is False
            and _flag_false(deep_scan_plan, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and deep_scan_plan.get("candidate_is_not_buy_instruction") is True,
            "Deep-scan plan must remain plan-only: no deep scan execution, provider refresh, DeepSeek call, scoring, or trade instruction.",
        ),
        _row(
            "plan_packet_preserves_pending_boundaries",
            _dict(plan_packet.get("full_pool_scan_plan")).get("full_pool_scan_done") is False
            and _dict(plan_packet.get("deep_scan_plan")).get("deep_scan_done") is False
            and _dict(plan_packet.get("no_feature_loss_acceptance_contract")).get("production_radar_replacement_complete") is False
            and _dict(plan_packet.get("replacement_gap_triage_contract")).get("legacy_retirement_ready") is False
            and _dict(plan_packet.get("result_delta_clarity_contract")).get("production_radar_replacement_complete") is False
            and _flag_false(plan_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and plan_packet.get("does_not_execute_trades") is True
            and plan_packet.get("does_not_modify_strategy_action") is True,
            "A locally built plan packet must keep full/deep execution, production replacement, and legacy retirement pending.",
        ),
        _row(
            "push_gate_runs_contract_after_factor",
            "scripts/candidate_radar_contract.py" in push_gate_script
            and "Candidate Radar contract" in push_gate_script
            and "candidate_radar_contract: passed_local_contract_replacement_pending" in push_gate_script
            and push_gate_script.find('run_step "Factor Test Lab contract"') < push_gate_script.find('run_step "Candidate Radar contract"')
            and push_gate_script.find('run_step "Candidate Radar contract"') < push_gate_script.find('run_step "Motion viewport QA contract"'),
            "Push gate must run the LTG-13 local contract after Factor Test Lab and before motion/static QA.",
        ),
        _row(
            "script_is_local_no_provider_execution",
            "command_center_3_candidate_radar_contract.v1" in this_script
            and "local_candidate_radar_contract_no_provider_execution" in this_script
            and "production_radar_replacement_complete" in this_script
            and "legacy_retirement_ready" in this_script
            and "candidate_is_not_buy_instruction" in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script,
            "The push-gate contract script must stay local and must not import provider clients.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_candidate_radar_contract.v1",
        "status": "candidate_radar_contract_passed" if not blockers else "candidate_radar_contract_blocked",
        "scope": "local_candidate_radar_contract_no_provider_execution",
        "ltg": "LTG-13/LTG-11",
        "contract_ready": not blockers,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "browser_performance_trace_done": False,
        "browser_visual_delta_qa_done": False,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "observed": {
            "cache_status": cache_packet.get("status"),
            "cache_scan_mode": cache_packet.get("scan_mode"),
            "candidate_count": _dict(cache_packet.get("counts")).get("candidate_count"),
            "fast_scan_readiness_status": readiness.get("status"),
            "no_feature_loss_status": no_loss.get("status"),
            "no_feature_loss_production_blocker_count": no_loss.get("production_blocker_count"),
            "replacement_gap_status": triage.get("status"),
            "replacement_gap_blocking_count": triage.get("blocking_gap_count"),
            "result_delta_status": result_delta.get("status"),
            "full_pool_plan_blocker_count": full_pool_plan.get("blocking_issue_count"),
            "deep_scan_plan_blocker_count": deep_scan_plan.get("blocking_issue_count"),
        },
        "rows": rows,
        "note": "This is a local push-gate contract. Full-pool execution, deep-scan execution, provider-backed parity acceptance, browser performance/visual QA, and legacy radar retirement remain pending.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-13 Candidate Radar contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"candidate_radar_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "production_radar_replacement_complete: false; legacy_retirement_ready: false".format(
                **contract
            )
        )
        print(
            "external_calls_triggered: false; tushare_called: false; "
            "deepseek_called: false; github_called: false; does_not_execute_trades: true"
        )
        if contract["blockers"]:
            print("blockers: " + ", ".join(contract["blockers"]))
    return 0 if contract["contract_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
