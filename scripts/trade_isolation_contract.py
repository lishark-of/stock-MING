#!/usr/bin/env python3
"""Validate the local LTG-12 real-trading isolation contract.

This push-gate guard reads only local risk cache, task catalog, frontend
source contracts, and the push-gate script. It keeps Command Center 3 research,
cache, model, task, and frontend paths visibly separated from broker/order
execution until a separate approved trading design exists.
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

from server.services import risk_service, task_service  # noqa: E402


FRONTEND_BOUNDARY_PATHS = (
    "desktop/src/routes/RiskGuardrails.tsx",
    "desktop/src/routes/TaskCatalog.tsx",
    "desktop/src/routes/PacketRegistry.tsx",
)
SERVER_BOUNDARY_PATHS = (
    "server/services/risk_service.py",
    "server/services/task_service.py",
)
REQUIRED_RELEASE_RECEIPT_CRITERIA = {
    "risk_cache_policy_visible",
    "trade_isolation_audit_clear",
    "task_catalog_no_order_routes",
    "task_catalog_no_trade_no_action_mutation",
    "frontend_no_trade_boundaries_visible",
    "model_factor_cache_not_order_source",
    "separate_project_required_for_real_trading",
    "release_receipt_not_trade_approval",
    "cache_render_no_external_no_trade",
}
REQUIRED_TRADE_ISOLATION_STAGE_SCOPE_KEYS = {
    "current_no_broker_adapter_boundary",
    "task_catalog_no_order_routes",
    "frontend_no_trade_controls",
    "model_provider_no_action_mutation",
    "separate_real_trading_project_decision",
    "broker_adapter_design_review",
    "order_endpoint_security_review",
    "paper_or_simulated_trade_sandbox",
}
TRADE_ISOLATION_STAGE_SCOPE_LABELS = {
    "current_no_broker_adapter_boundary": "current Command Center 3 has no broker adapter",
    "task_catalog_no_order_routes": "task catalog has no order routes",
    "frontend_no_trade_controls": "frontend exposes no trade submission controls",
    "model_provider_no_action_mutation": "model and provider paths cannot mutate action",
    "separate_real_trading_project_decision": "real trading requires a separate project decision",
    "broker_adapter_design_review": "broker adapter design review is required later",
    "order_endpoint_security_review": "order endpoint security review is required later",
    "paper_or_simulated_trade_sandbox": "paper or simulated trade sandbox is required later",
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


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def _flag_false(contract: dict[str, Any], *keys: str) -> bool:
    return all(contract.get(key) is False for key in keys)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(marker.lower() in lower for marker in markers)


def _task_boundary_rows(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _list(catalog.get("tasks")):
        task = _dict(item)
        rows.append(
            {
                "route_type": "task_creation",
                "route": task.get("route"),
                "task_type": task.get("task_type"),
                "button_gated": task.get("button_gated") is True,
                "call_ledger_required": task.get("call_ledger_required") is True,
                "does_not_execute_trades": task.get("does_not_execute_trades") is not False,
                "does_not_modify_strategy_action": task.get("does_not_modify_strategy_action") is not False,
            }
        )
    for item in _list(catalog.get("task_lifecycle_routes")):
        route = _dict(item)
        rows.append(
            {
                "route_type": route.get("route_type") or "local_lifecycle",
                "route": route.get("route"),
                "task_type": route.get("task_type") or "local_task_lifecycle",
                "button_gated": route.get("button_gated") is True,
                "call_ledger_required": route.get("call_ledger_required") is True,
                "does_not_execute_trades": route.get("does_not_execute_trades", True) is not False,
                "does_not_modify_strategy_action": route.get("does_not_modify_strategy_action", True) is not False,
            }
        )
    return rows


def _trade_isolation_stage_scope_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage_key in sorted(REQUIRED_TRADE_ISOLATION_STAGE_SCOPE_KEYS):
        rows.append(
            {
                "stage_key": stage_key,
                "stage_label": TRADE_ISOLATION_STAGE_SCOPE_LABELS[stage_key],
                "scope": "trade_isolation_stage_scope_manifest",
                "current_status": "current_research_client_isolated",
                "target_status": "separate_real_trading_project_evidence_required",
                "required_before_real_trading": True,
                "real_trading_connected": False,
                "broker_adapter_connected": False,
                "order_endpoint_present": False,
                "trade_execution_api_enabled": False,
                "order_route_present": False,
                "frontend_trade_controls_present": False,
                "model_or_provider_can_modify_action": False,
                "strategy_action_mutated_by_contract": False,
                "paper_trading_sandbox_ready": False,
                "separate_project_approved": False,
                "future_real_trading_requires_separate_project": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "broker_called": False,
                "order_submitted": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "missing_evidence": [
                    "separate project approval",
                    "broker adapter threat model",
                    "order endpoint security review",
                    "paper or simulated trade sandbox",
                    "audit trail and kill switch plan",
                    "explicit operator approval",
                ],
            }
        )
    return rows


def build_contract() -> dict[str, Any]:
    packet = risk_service.read_risk_guardrails_cache()
    policy = _dict(packet.get("policy"))
    trade_audit = _dict(packet.get("trade_isolation_audit"))
    trade_rows = [row for row in _list(packet.get("trade_isolation_rows")) if isinstance(row, dict)]
    trade_criteria = {str(row.get("criterion") or "") for row in trade_rows}
    release_receipt = _dict(packet.get("trade_isolation_release_receipt"))
    release_receipt_rows = [
        row for row in _list(packet.get("trade_isolation_release_receipt_rows")) if isinstance(row, dict)
    ]
    release_receipt_criteria = {str(row.get("criterion") or "") for row in release_receipt_rows}
    catalog = task_service.build_task_catalog()
    route_coverage = _dict(catalog.get("route_coverage"))
    boundary_rows = _task_boundary_rows(catalog)
    trade_isolation_stage_scope_rows = _trade_isolation_stage_scope_rows()
    trade_isolation_stage_scope_keys = {
        str(row.get("stage_key") or "") for row in trade_isolation_stage_scope_rows
    }

    risk_page = _read_script("desktop/src/routes/RiskGuardrails.tsx")
    task_page = _read_script("desktop/src/routes/TaskCatalog.tsx")
    packet_page = _read_script("desktop/src/routes/PacketRegistry.tsx")
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/trade_isolation_contract.py")
    local_source_text = "\n".join(
        [_read_script(path) for path in FRONTEND_BOUNDARY_PATHS + SERVER_BOUNDARY_PATHS]
    )

    endpoint_markers = (
        "/api/order",
        "/api/orders",
        "/api/broker",
        "/api/trade-execution",
        "/api/trades/execute",
    )
    live_execution_markers = (
        "execute_" + "trade(",
        "place_" + "order(",
        "live_" + "order(",
        "broker." + "submit(",
        "real_trading_enabled=true",
        "trade_execution_api_enabled=true",
    )
    local_client_markers = (
        "import " + "tushare" + "_adapter",
        "import " + "deepseek" + "_adapter",
        "api.github" + ".com",
        "gh " + "api",
        "request" + "s",
        "ht" + "tpx",
        "sub" + "process",
    )

    task_routes_no_trade = all(row["does_not_execute_trades"] for row in boundary_rows)
    task_routes_no_action = all(row["does_not_modify_strategy_action"] for row in boundary_rows)
    task_routes_button_gated = bool(route_coverage.get("all_known_post_routes_button_gated"))
    task_routes_call_ledger_required = bool(
        route_coverage.get("call_ledger_required_for_all_known_post_routes")
    )
    known_routes_text = "\n".join(str(row.get("route") or "") for row in boundary_rows)
    order_endpoint_present = _contains_any(known_routes_text, endpoint_markers)
    broker_adapter_connected = _contains_any(local_source_text, live_execution_markers)
    frontend_boundary_visible = (
        "不执行真实交易" in risk_page
        and "不自动下单" in risk_page
        and "不修改 strategy action" in risk_page
        and "does_not_execute_trades" in task_page
        and "does_not_modify_strategy_action" in task_page
        and "does_not_execute_trades" in packet_page
        and "does_not_modify_strategy_action" in packet_page
    )
    push_gate_step_ready = (
        "scripts/trade_isolation_contract.py" in push_gate_script
        and "Trade isolation contract" in push_gate_script
        and "trade_isolation_contract: passed_local_contract_real_trading_disconnected" in push_gate_script
        and push_gate_script.find('run_step "Streamlit legacy contract"')
        < push_gate_script.find('run_step "Trade isolation contract"')
        < push_gate_script.find('run_step "Motion viewport QA contract"')
    )
    trade_isolation_stage_scope_ready = (
        REQUIRED_TRADE_ISOLATION_STAGE_SCOPE_KEYS == trade_isolation_stage_scope_keys
        and all(
            row.get("scope") == "trade_isolation_stage_scope_manifest"
            and row.get("current_status") == "current_research_client_isolated"
            and row.get("target_status") == "separate_real_trading_project_evidence_required"
            and row.get("required_before_real_trading") is True
            and row.get("real_trading_connected") is False
            and row.get("broker_adapter_connected") is False
            and row.get("order_endpoint_present") is False
            and row.get("trade_execution_api_enabled") is False
            and row.get("order_route_present") is False
            and row.get("frontend_trade_controls_present") is False
            and row.get("model_or_provider_can_modify_action") is False
            and row.get("strategy_action_mutated_by_contract") is False
            and row.get("paper_trading_sandbox_ready") is False
            and row.get("separate_project_approved") is False
            and row.get("future_real_trading_requires_separate_project") is True
            and row.get("external_calls_triggered") is False
            and row.get("tushare_called") is False
            and row.get("deepseek_called") is False
            and row.get("github_called") is False
            and row.get("broker_called") is False
            and row.get("order_submitted") is False
            and row.get("does_not_execute_trades") is True
            and row.get("does_not_modify_strategy_action") is True
            and row.get("contains_secret") is False
            and len(_list(row.get("missing_evidence"))) >= 6
            for row in trade_isolation_stage_scope_rows
        )
    )
    current_slice_recheck_ready = (
        packet.get("schema_version") == "risk_guardrails_cache.v1"
        and packet.get("mode") == "cache_only"
        and packet.get("cache_only") is True
        and packet.get("read_only") is True
        and trade_audit.get("status") == "trade_isolation_ready"
        and task_routes_no_trade
        and task_routes_no_action
        and not order_endpoint_present
        and not broker_adapter_connected
        and frontend_boundary_visible
        and release_receipt.get("status") == "trade_isolation_release_receipt_ready_research_release_only"
        and release_receipt.get("ready_for_real_trading_integration") is False
        and release_receipt.get("real_trading_connected") is False
        and release_receipt.get("broker_adapter_connected") is False
        and release_receipt.get("order_endpoint_present") is False
        and release_receipt.get("trade_execution_api_enabled") is False
        and _flag_false(packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
        and _flag_false(release_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
        and packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("does_not_modify_holdings") is True
        and release_receipt.get("does_not_execute_trades") is True
        and release_receipt.get("does_not_modify_strategy_action") is True
        and release_receipt.get("does_not_modify_holdings") is True
        and release_receipt.get("contains_secret") is False
    )

    rows = [
        _row(
            "risk_cache_is_read_only_no_trade",
            packet.get("schema_version") == "risk_guardrails_cache.v1"
            and packet.get("mode") == "cache_only"
            and packet.get("cache_only") is True
            and packet.get("read_only") is True
            and policy.get("trade_isolation_audit_is_read_only") is True
            and policy.get("risk_guardrails_are_not_trade_orders") is True
            and _flag_false(packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and packet.get("does_not_execute_trades") is True
            and packet.get("does_not_modify_strategy_action") is True
            and packet.get("does_not_modify_holdings") is True,
            "GET risk cache is cache-only, read-only, no provider/model/GitHub call, no trade, no action or holdings mutation.",
        ),
        _row(
            "trade_isolation_audit_keeps_real_trading_disabled",
            trade_audit.get("schema_version") == "command_center_3_trade_isolation_audit.v1"
            and trade_audit.get("status") == "trade_isolation_ready"
            and trade_audit.get("no_automatic_order_path_in_task_catalog") is True
            and trade_audit.get("research_paths_cannot_mutate_strategy_action") is True
            and trade_audit.get("frontend_surfaces_are_display_only_for_trade_boundaries") is True
            and trade_audit.get("future_trade_integration_out_of_roadmap") is True
            and int(trade_audit.get("blocking_criterion_count") or 0) == 0
            and {"risk_cache_policy_no_trade", "frontend_boundaries_visible", "future_trading_requires_separate_approved_design"}.issubset(
                trade_criteria
            ),
            "Risk cache exposes trade_isolation_audit as a local boundary audit, not a trading integration.",
        ),
        _row(
            "task_catalog_has_no_trade_execution_routes",
            bool(boundary_rows)
            and task_routes_no_trade
            and task_routes_no_action
            and not order_endpoint_present,
            "Task catalog and lifecycle rows declare no trade execution, no strategy action mutation, and no order/broker endpoint route.",
        ),
        _row(
            "trade_isolation_release_receipt_is_research_only",
            release_receipt.get("schema_version") == "command_center_3_trade_isolation_release_receipt.v1"
            and release_receipt.get("status") == "trade_isolation_release_receipt_ready_research_release_only"
            and release_receipt.get("scope")
            == "local_trade_isolation_release_receipt_no_broker_or_order_execution"
            and release_receipt.get("local_receipt_ready") is True
            and release_receipt.get("research_client_release_safe") is True
            and release_receipt.get("ready_for_real_trading_integration") is False
            and release_receipt.get("future_real_trading_requires_separate_project") is True
            and release_receipt.get("allowed_next_step")
            == "continue_research_client_release_or_create_separate_real_trading_project_design"
            and REQUIRED_RELEASE_RECEIPT_CRITERIA.issubset(release_receipt_criteria)
            and int(release_receipt.get("trade_isolation_blocker_count") or 0) == 0
            and int(release_receipt.get("release_receipt_blocker_count") or 0) == 0
            and release_receipt.get("order_like_routes") == []
            and release_receipt.get("boundary_blockers") == []
            and "connect broker adapter inside Command Center 3 migration"
            in _list(release_receipt.get("not_allowed_next_steps"))
            and "add order endpoint to cache/task API" in _list(release_receipt.get("not_allowed_next_steps"))
            and "let model or factor output become orders" in _list(release_receipt.get("not_allowed_next_steps"))
            and "let frontend compute or submit trades" in _list(release_receipt.get("not_allowed_next_steps"))
            and "treat release receipt as real-trading approval"
            in _list(release_receipt.get("not_allowed_next_steps"))
            and "execute real trades from push gate, cache GET, task catalog, or page render"
            in _list(release_receipt.get("not_allowed_next_steps"))
            and release_receipt.get("real_trading_connected") is False
            and release_receipt.get("broker_adapter_connected") is False
            and release_receipt.get("order_endpoint_present") is False
            and release_receipt.get("trade_execution_api_enabled") is False
            and _flag_false(release_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and release_receipt.get("does_not_execute_trades") is True
            and release_receipt.get("does_not_modify_strategy_action") is True
            and release_receipt.get("does_not_modify_holdings") is True
            and release_receipt.get("contains_secret") is False
            and _list(release_receipt.get("call_ledger"))
            and _dict(_list(release_receipt.get("call_ledger"))[0]).get("api")
            == "local_trade_isolation_release_receipt"
            and _dict(_list(release_receipt.get("call_ledger"))[0]).get("external") is False
            and packet.get("trade_isolation_release_receipt_ready") is True
            and packet.get("trade_isolation_release_receipt_status") == release_receipt.get("status"),
            "Trade isolation release receipt may support research-client release only; it must not approve real trading, broker adapters, order endpoints, provider/model calls, action mutation, or trade execution.",
        ),
        _row(
            "current_slice_no_broker_no_order_no_action_recheck",
            current_slice_recheck_ready,
            "Current slice still has no broker adapter, order endpoint, frontend trade controls, provider/model action mutation, external calls, holdings mutation, or trade execution.",
        ),
        _row(
            "task_lifecycle_records_no_trade_no_action",
            task_routes_button_gated and task_routes_call_ledger_required,
            "All known POST task/lifecycle routes remain button-gated and require call_ledger.",
        ),
        _row(
            "frontend_trade_boundaries_visible",
            frontend_boundary_visible,
            "Risk, task catalog, and packet registry pages show no-trade/no-action/no-holdings boundaries.",
        ),
        _row(
            "push_gate_runs_trade_isolation_contract_after_streamlit",
            push_gate_step_ready,
            "Push gate must run LTG-12 contract after Streamlit legacy and before motion/static QA.",
        ),
        _row(
            "trade_isolation_stage_scope_manifest_is_complete_and_pending",
            trade_isolation_stage_scope_ready,
            "Future real-trading stages are listed as pending evidence while broker, order, frontend submission, model action mutation, provider/probe calls, and real order submission remain disabled.",
        ),
        _row(
            "script_is_local_no_broker_or_order_execution",
            "command_center_3_trade_isolation_contract.v1" in this_script
            and "local_trade_isolation_contract_no_broker_or_order_execution" in this_script
            and "trade_isolation_stage_scope_manifest" in this_script
            and "real_trading_connected" in this_script
            and "broker_adapter_connected" in this_script
            and "order_endpoint_present" in this_script
            and "trade_execution_api_enabled" in this_script
            and "future_real_trading_requires_separate_project" in this_script
            and "does_not_execute_trades" in this_script
            and not broker_adapter_connected
            and not order_endpoint_present
            and not _contains_any(this_script, local_client_markers),
            "This contract must stay local, import no provider/model/probe clients, run no shell commands, and execute no broker/order path.",
        ),
        _row(
            "future_real_trading_requires_separate_project",
            policy.get("future_trade_integration_requires_separate_approved_design") is True
            and trade_audit.get("future_trade_integration_out_of_roadmap") is True,
            "Any future real-trading integration remains a separate approved design, not part of current research/cache/task migration.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_trade_isolation_contract.v1",
        "status": "trade_isolation_contract_passed" if not blockers else "trade_isolation_contract_blocked",
        "scope": "local_trade_isolation_contract_no_broker_or_order_execution",
        "ltg": "LTG-12/LTG-11",
        "contract_ready": not blockers,
        "risk_cache_ready": packet.get("schema_version") == "risk_guardrails_cache.v1" and packet.get("cache_only") is True,
        "trade_isolation_audit_visible": trade_audit.get("schema_version") == "command_center_3_trade_isolation_audit.v1",
        "trade_isolation_status": trade_audit.get("status"),
        "trade_isolation_release_receipt_ready": release_receipt.get("local_receipt_ready") is True,
        "trade_isolation_release_receipt_status": release_receipt.get("status"),
        "task_catalog_boundary_visible": bool(boundary_rows) and task_routes_no_trade and task_routes_no_action,
        "frontend_boundary_visible": frontend_boundary_visible,
        "current_slice_trade_isolation_recheck_ready": current_slice_recheck_ready,
        "push_gate_step_ready": push_gate_step_ready,
        "cache_only": True,
        "real_trading_connected": False,
        "broker_adapter_connected": bool(broker_adapter_connected),
        "order_endpoint_present": bool(order_endpoint_present),
        "trade_execution_api_enabled": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "future_real_trading_requires_separate_project": True,
        "contains_secret": False,
        "row_count": len(rows),
        "task_boundary_row_count": len(boundary_rows),
        "trade_isolation_stage_scope_count": len(trade_isolation_stage_scope_rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "observed": {
            "risk_cache_status": packet.get("status"),
            "trade_isolation_status": trade_audit.get("status"),
            "known_post_route_count": route_coverage.get("known_post_route_count"),
            "trade_isolation_blocker_count": trade_audit.get("blocking_criterion_count"),
            "frontend_surface_count": trade_audit.get("frontend_surface_count"),
            "task_boundary_row_count": trade_audit.get("task_boundary_row_count"),
            "release_receipt_status": release_receipt.get("status"),
            "release_receipt_allowed_next_step": release_receipt.get("allowed_next_step"),
            "release_receipt_blocker_count": release_receipt.get("blocking_criterion_count"),
            "current_slice_trade_isolation_recheck_ready": current_slice_recheck_ready,
            "trade_isolation_stage_scope_count": len(trade_isolation_stage_scope_rows),
            "trade_isolation_stage_scope_keys": sorted(trade_isolation_stage_scope_keys),
            "trade_isolation_stage_scope_pending_count": sum(
                1
                for row in trade_isolation_stage_scope_rows
                if row.get("current_status") == "current_research_client_isolated"
                and row.get("target_status") == "separate_real_trading_project_evidence_required"
                and row.get("real_trading_connected") is False
            ),
            "task_routes_button_gated": task_routes_button_gated,
            "task_routes_call_ledger_required": task_routes_call_ledger_required,
        },
        "rows": rows,
        "trade_isolation_stage_scope_rows": trade_isolation_stage_scope_rows,
        "note": "This is a local push-gate contract. Real trading remains disconnected; broker/order integration requires a separate approved project.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-12 real-trading isolation contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"trade_isolation_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "real_trading_connected: {real_trading_connected}; "
            "broker_adapter_connected: {broker_adapter_connected}; "
            "order_endpoint_present: {order_endpoint_present}".format(**contract).lower()
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
