#!/usr/bin/env python3
"""Validate the local LTG-10 Streamlit legacy-retirement contract.

This push-gate guard is not Streamlit execution and not fallback removal. It
reads local legacy bridge cache contracts to keep legacy/admin/debug fallback,
ordinary-workflow exit blockers, no-feature-cut requirements, and no external
or trading side effects visible until Command Center 3 fully replaces the
ordinary user path.
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

from server.services import legacy_service  # noqa: E402


REQUIRED_EXIT_CRITERIA = {
    "streamlit_marked_legacy_admin_debug",
    "react_tauri_is_primary_entry",
    "legacy_cache_get_read_only",
    "legacy_startup_does_not_create_tasks",
    "legacy_startup_does_not_call_external_sources",
    "legacy_cannot_bypass_guardrails",
    "ordinary_workflow_route_inventory_visible",
    "ordinary_workflows_fully_migrated",
    "legacy_fallback_removal_ready",
    "snapshot_migration_cache_available",
    "legacy_migration_checklist_clear",
}
REQUIRED_ROUTE_WORKFLOWS = {
    "home_status",
    "next_session_map",
    "factor_quant_hub",
    "candidate_radar_quick_scan",
    "legacy_admin_debug_tools",
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


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def build_contract() -> dict[str, Any]:
    packet = legacy_service.read_legacy_bridge_cache()
    policy = _dict(packet.get("policy"))
    exit_audit = _dict(packet.get("primary_workflow_exit_audit"))
    exit_rows = [row for row in _list(packet.get("primary_workflow_exit_rows")) if isinstance(row, dict)]
    exit_criteria = {str(row.get("criterion") or "") for row in exit_rows}
    route_rows = [row for row in _list(packet.get("primary_workflow_route_rows")) if isinstance(row, dict)]
    route_workflows = {str(row.get("workflow") or "") for row in route_rows}
    fallback_contract = _dict(packet.get("streamlit_fallback_dependency_contract"))
    fallback_rows = [
        row for row in _list(packet.get("streamlit_fallback_dependency_rows")) if isinstance(row, dict)
    ]
    dependency_classes = {str(row.get("dependency_class") or "") for row in fallback_rows}
    source_summary = _dict(exit_audit.get("source_summary"))
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    route_source = _read_script("desktop/src/routes/LegacyTools.tsx")
    app_source = _read_script("app.py")
    this_script = _read_script("scripts/streamlit_legacy_contract.py")

    rows = [
        _row(
            "legacy_cache_is_read_only",
            packet.get("schema_version") == "legacy_bridge_cache.v1"
            and packet.get("mode") == "cache_only"
            and packet.get("cache_only") is True
            and packet.get("read_only") is True
            and policy.get("cache_api_external_calls") is False
            and policy.get("does_not_open_streamlit") is True
            and policy.get("does_not_run_legacy_tools") is True
            and policy.get("legacy_startup_task_creation") is False
            and policy.get("legacy_startup_external_calls") is False
            and _flag_false(packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and packet.get("does_not_execute_trades") is True
            and packet.get("does_not_modify_strategy_action") is True,
            "GET legacy cache must remain read-only and must not open Streamlit, run old tools, create tasks, call providers/models/GitHub, or trade.",
        ),
        _row(
            "streamlit_marked_legacy_not_primary",
            policy.get("streamlit_role") == "legacy/admin/debug"
            and policy.get("official_primary_entry") == "React/Vite/Tauri + FastAPI"
            and policy.get("streamlit_is_official_primary_entry") is False
            and policy.get("react_tauri_is_primary_entry") is True
            and source_summary.get("legacy_mode_marker_present") is True
            and source_summary.get("legacy_admin_notice_present") is True
            and "STREAMLIT_LEGACY_MODE_STATUS" in app_source
            and "legacy/admin/debug" in app_source
            and "普通主流程" in app_source,
            "Streamlit must stay clearly labeled legacy/admin/debug while React/Tauri + FastAPI remains the official primary entry.",
        ),
        _row(
            "primary_exit_audit_keeps_fallback_required",
            exit_audit.get("schema_version") == "streamlit_primary_workflow_exit_audit.v1"
            and exit_audit.get("status") == "ordinary_workflow_exit_partial_fallback_required"
            and exit_audit.get("scope") == "local_legacy_policy_and_route_inventory_not_streamlit_execution"
            and exit_audit.get("ordinary_workflow_exit_complete") is False
            and exit_audit.get("streamlit_fallback_retained") is True
            and exit_audit.get("streamlit_fallback_removal_ready") is False
            and int(exit_audit.get("ordinary_workflow_still_needs_fallback_count") or 0) > 0
            and int(exit_audit.get("blocker_count") or 0) > 0
            and REQUIRED_EXIT_CRITERIA.issubset(exit_criteria)
            and REQUIRED_ROUTE_WORKFLOWS.issubset(route_workflows)
            and _flag_false(exit_audit, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and exit_audit.get("does_not_open_streamlit") is True
            and exit_audit.get("does_not_run_legacy_tools") is True
            and exit_audit.get("does_not_execute_trades") is True
            and exit_audit.get("does_not_modify_strategy_action") is True,
            "Primary workflow exit audit must keep ordinary fallback blockers visible until Command Center 3 proves full replacement.",
        ),
        _row(
            "fallback_dependency_contract_keeps_retirement_pending",
            fallback_contract.get("schema_version") == "streamlit_fallback_dependency_contract.v1"
            and fallback_contract.get("status") == "streamlit_fallback_dependencies_visible_retirement_pending"
            and fallback_contract.get("scope") == "local_route_dependency_contract_not_streamlit_execution"
            and fallback_contract.get("ordinary_primary_exit_ready") is False
            and fallback_contract.get("full_streamlit_removal_ready") is False
            and fallback_contract.get("streamlit_fallback_retained") is True
            and int(fallback_contract.get("ordinary_fallback_dependency_count") or 0) > 0
            and int(fallback_contract.get("full_streamlit_removal_blocker_count") or 0) > 0
            and "ordinary_flow_partial_fallback_required" in dependency_classes
            and "legacy_admin_debug_retained" in dependency_classes
            and "candidate_radar_quick_scan" in set(fallback_contract.get("ordinary_blocking_workflows") or [])
            and "legacy_admin_debug_tools" in set(fallback_contract.get("full_removal_blocking_workflows") or [])
            and fallback_contract.get("feature_parity_required_before_removal") is True
            and fallback_contract.get("no_feature_cut_allowed") is True
            and _flag_false(fallback_contract, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and fallback_contract.get("does_not_open_streamlit") is True
            and fallback_contract.get("does_not_run_legacy_tools") is True
            and fallback_contract.get("does_not_create_tasks") is True
            and fallback_contract.get("does_not_execute_trades") is True
            and fallback_contract.get("does_not_modify_strategy_action") is True,
            "Fallback dependency contract must keep no-feature-cut and retained-admin/debug blockers visible before removal.",
        ),
        _row(
            "react_legacy_page_displays_boundaries",
            "Legacy / Admin / Debug" in route_source
            and "Streamlit 2.0 保留为 legacy" in route_source
            and "ordinary_workflow_exit_complete" in route_source
            and "streamlit_fallback_removal_ready" in route_source
            and "Streamlit fallback 依赖契约" in route_source
            and "普通主流程" in route_source
            and "真实交易" in route_source
            and "不会打开 Streamlit" in route_source,
            "React Legacy page must show primary-entry, fallback, no-autocall, no-task, no-trade, and removal-pending boundaries.",
        ),
        _row(
            "legacy_startup_does_not_autocreate_or_autoexternal",
            policy.get("legacy_startup_task_creation") is False
            and policy.get("legacy_startup_external_calls") is False
            and policy.get("legacy_can_bypass_guardrails") is False
            and policy.get("post_task_required_for_migration_work") is True
            and source_summary.get("legacy_action_guard_present") is True
            and "guard_legacy_projection_action" in app_source
            and "render_streamlit_legacy_admin_notice" in app_source,
            "Legacy startup must not create tasks, auto-call external sources, or bypass legacy action guardrails.",
        ),
        _row(
            "push_gate_runs_streamlit_contract_after_tauri",
            "scripts/streamlit_legacy_contract.py" in push_gate_script
            and "Streamlit legacy contract" in push_gate_script
            and "streamlit_legacy_contract: passed_local_contract_retirement_pending" in push_gate_script
            and push_gate_script.find('run_step "Tauri desktop contract"')
            < push_gate_script.find('run_step "Streamlit legacy contract"')
            and push_gate_script.find('run_step "Streamlit legacy contract"')
            < push_gate_script.find('run_step "Motion viewport QA contract"'),
            "Push gate must run LTG-10 Streamlit legacy contract after Tauri desktop and before motion/static QA.",
        ),
        _row(
            "script_is_local_no_streamlit_execution",
            "command_center_3_streamlit_legacy_contract.v1" in this_script
            and "local_streamlit_legacy_contract_not_streamlit_execution" in this_script
            and "ordinary_workflow_exit_complete" in this_script
            and "full_streamlit_removal_ready" in this_script
            and "streamlit_fallback_retained" in this_script
            and "does_not_open_streamlit" in this_script
            and "does_not_execute_trades" in this_script
            and ("import " + "streamlit") not in this_script
            and ("sub" + "process") not in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script
            and ("deepseek" + "_adapter") not in this_script,
            "The Streamlit legacy contract must stay local and must not import Streamlit, run shell commands, or call external clients.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_streamlit_legacy_contract.v1",
        "status": "streamlit_legacy_contract_passed" if not blockers else "streamlit_legacy_contract_blocked",
        "scope": "local_streamlit_legacy_contract_not_streamlit_execution",
        "ltg": "LTG-10/LTG-11",
        "contract_ready": not blockers,
        "legacy_cache_ready": packet.get("schema_version") == "legacy_bridge_cache.v1" and packet.get("cache_only") is True,
        "streamlit_marked_legacy": True,
        "react_tauri_primary_entry": True,
        "ordinary_workflow_exit_complete": False,
        "streamlit_fallback_removal_ready": False,
        "full_streamlit_removal_ready": False,
        "streamlit_fallback_retained": True,
        "legacy_fallback_required": True,
        "feature_parity_required_before_removal": True,
        "no_feature_cut_allowed": True,
        "cache_only": True,
        "does_not_open_streamlit": True,
        "does_not_run_legacy_tools": True,
        "does_not_create_tasks": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "observed": {
            "legacy_cache_status": packet.get("status"),
            "primary_exit_status": exit_audit.get("status"),
            "primary_exit_blocker_count": exit_audit.get("blocker_count"),
            "ordinary_workflow_route_count": exit_audit.get("ordinary_workflow_route_count"),
            "ordinary_workflow_still_needs_fallback_count": exit_audit.get(
                "ordinary_workflow_still_needs_fallback_count"
            ),
            "fallback_contract_status": fallback_contract.get("status"),
            "ordinary_fallback_dependency_count": fallback_contract.get("ordinary_fallback_dependency_count"),
            "full_streamlit_removal_blocker_count": fallback_contract.get(
                "full_streamlit_removal_blocker_count"
            ),
            "ordinary_blocking_workflows": fallback_contract.get("ordinary_blocking_workflows"),
            "full_removal_blocking_workflows": fallback_contract.get("full_removal_blocking_workflows"),
            "checklist_pending_count": exit_audit.get("checklist_pending_count"),
            "checklist_done_count": exit_audit.get("checklist_done_count"),
        },
        "rows": rows,
        "note": "This is a local push-gate contract. Streamlit fallback removal, full ordinary-workflow exit, replacement parity, and admin/debug retirement remain pending.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-10 Streamlit legacy contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"streamlit_legacy_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "ordinary_workflow_exit_complete: false; full_streamlit_removal_ready: false; "
            "streamlit_fallback_retained: true".format(**contract)
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
