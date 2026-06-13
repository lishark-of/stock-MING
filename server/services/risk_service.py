from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from server.services import packet_service, task_service


PACKET_KEY = "command_center_3_risk_guardrails_cache"
SCHEMA_VERSION = "risk_guardrails_cache.v1"
TRADE_ISOLATION_SCHEMA_VERSION = "command_center_3_trade_isolation_audit.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_RISK_PAGE_PATH = PROJECT_ROOT / "desktop" / "src" / "routes" / "RiskGuardrails.tsx"
FRONTEND_TASK_CATALOG_PATH = PROJECT_ROOT / "desktop" / "src" / "routes" / "TaskCatalog.tsx"
FRONTEND_PACKET_REGISTRY_PATH = PROJECT_ROOT / "desktop" / "src" / "routes" / "PacketRegistry.tsx"
SENSITIVE_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password", "passwd", "credential", "authorization")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _is_sensitive_key(key: Any) -> bool:
    lower = str(key or "").lower()
    return any(part in lower for part in SENSITIVE_KEY_PARTS)


def _safe_text(value: Any, *, limit: int = 1000) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in SENSITIVE_TEXT_MARKERS):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            _safe_text(key, limit=80): _safe_value(val, depth=depth + 1)
            for key, val in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_safe_value(item, depth=depth + 1) for item in value[:50]]
    if isinstance(value, tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:50]]
    return _safe_text(value)


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "risk_guardrails_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _list_rows(value: Any, *, text_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, raw in enumerate(_as_list(value), start=1):
        if isinstance(raw, Mapping):
            row = dict(raw)
            row.setdefault("index", idx)
            rows.append(row)
        elif raw is not None:
            rows.append({"index": idx, text_key: _safe_text(raw)})
    return rows


def _risk_rows(risk_breakdown: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in _as_list(risk_breakdown.get("items")):
        item = _as_dict(raw)
        if item:
            rows.append(item)
    if rows:
        return rows
    for key, label in (("overall", "账户整体风险"), ("position", "单票风险"), ("margin", "融资风险"), ("data", "数据风险")):
        value = risk_breakdown.get(key)
        if isinstance(value, Mapping):
            rows.append({"key": key, "label": label, **dict(value)})
    return rows


def _counts(alerts: Mapping[str, Any], guardrail: Mapping[str, Any], legacy_chain: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "hard_risk_alert_count": len(_as_list(alerts.get("hard_risk_alerts"))),
        "data_gap_count": len(_as_list(alerts.get("data_gaps"))),
        "must_not_do_count": len(_as_list(alerts.get("must_not_do"))),
        "reduce_condition_count": len(_as_list(alerts.get("reduce_conditions"))),
        "execution_blocked_count": guardrail.get("blocked_count", 0),
        "legacy_blocked_count": legacy_chain.get("blocked_count", 0),
        "legacy_waiting_count": legacy_chain.get("waiting_count", 0),
    }


def _read_local_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _trade_isolation_row(criterion: str, passed: bool, *, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": passed,
        "evidence": evidence,
        "production_blocker": not passed,
    }


def _trade_isolation_audit(policy: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    catalog = task_service.build_task_catalog()
    tasks = _as_list(catalog.get("tasks"))
    lifecycle_routes = _as_list(catalog.get("task_lifecycle_routes"))
    route_coverage = _as_dict(catalog.get("route_coverage"))
    task_boundary_rows: list[dict[str, Any]] = []
    for item in tasks:
        task = _as_dict(item)
        task_boundary_rows.append(
            {
                "task_type": task.get("task_type"),
                "route": task.get("route"),
                "current_backend": task.get("current_backend"),
                "button_gated": task.get("button_gated") is True,
                "call_ledger_required": task.get("call_ledger_required") is True,
                "possible_external_sources": task.get("possible_external_sources", []),
                "does_not_execute_trades": task.get("does_not_execute_trades") is not False,
                "does_not_modify_strategy_action": task.get("does_not_modify_strategy_action") is not False,
            }
        )
    for item in lifecycle_routes:
        route = _as_dict(item)
        task_boundary_rows.append(
            {
                "task_type": route.get("task_type") or route.get("route_type") or "local_lifecycle_route",
                "route": route.get("route"),
                "current_backend": route.get("current_backend", "local_lifecycle"),
                "button_gated": route.get("button_gated") is True,
                "call_ledger_required": route.get("call_ledger_required") is True,
                "possible_external_sources": [],
                "does_not_execute_trades": route.get("does_not_execute_trades", True) is not False,
                "does_not_modify_strategy_action": route.get("does_not_modify_strategy_action", True) is not False,
            }
        )

    all_task_routes_no_trade = all(row["does_not_execute_trades"] for row in task_boundary_rows)
    all_task_routes_no_action = all(row["does_not_modify_strategy_action"] for row in task_boundary_rows)
    risk_page = _read_local_text(FRONTEND_RISK_PAGE_PATH)
    task_catalog_page = _read_local_text(FRONTEND_TASK_CATALOG_PATH)
    packet_registry_page = _read_local_text(FRONTEND_PACKET_REGISTRY_PATH)
    frontend_rows = [
        {
            "surface": "RiskGuardrails.tsx",
            "path": "desktop/src/routes/RiskGuardrails.tsx",
            "status": "passed" if risk_page and "postTask" not in risk_page else "blocked",
            "does_not_launch_tasks": bool(risk_page and "postTask" not in risk_page),
            "shows_no_trade_boundary": "不执行真实交易" in risk_page and "不自动下单" in risk_page,
            "shows_no_action_mutation_boundary": "不修改 strategy action" in risk_page,
        },
        {
            "surface": "TaskCatalog.tsx",
            "path": "desktop/src/routes/TaskCatalog.tsx",
            "status": "passed" if "does_not_execute_trades" in task_catalog_page and "does_not_modify_strategy_action" in task_catalog_page else "blocked",
            "does_not_launch_tasks": False,
            "shows_no_trade_boundary": "does_not_execute_trades" in task_catalog_page,
            "shows_no_action_mutation_boundary": "does_not_modify_strategy_action" in task_catalog_page,
        },
        {
            "surface": "PacketRegistry.tsx",
            "path": "desktop/src/routes/PacketRegistry.tsx",
            "status": "passed" if "does_not_execute_trades" in packet_registry_page and "does_not_modify_strategy_action" in packet_registry_page else "blocked",
            "does_not_launch_tasks": True,
            "shows_no_trade_boundary": "does_not_execute_trades" in packet_registry_page,
            "shows_no_action_mutation_boundary": "does_not_modify_strategy_action" in packet_registry_page,
        },
    ]
    frontend_boundaries_visible = all(
        row.get("status") == "passed"
        and row.get("shows_no_trade_boundary") is True
        and row.get("shows_no_action_mutation_boundary") is True
        for row in frontend_rows
    )
    rows = [
        _trade_isolation_row(
            "risk_cache_policy_no_trade",
            policy.get("does_not_execute_trades") is True,
            evidence="GET /api/risk/cache policy declares does_not_execute_trades=true",
        ),
        _trade_isolation_row(
            "risk_cache_policy_no_strategy_action_mutation",
            policy.get("does_not_modify_strategy_action") is True,
            evidence="GET /api/risk/cache policy declares does_not_modify_strategy_action=true",
        ),
        _trade_isolation_row(
            "risk_cache_policy_not_trade_orders",
            policy.get("risk_guardrails_are_not_trade_orders") is True,
            evidence="risk guardrails remain explanation/display guardrails, not order instructions",
        ),
        _trade_isolation_row(
            "task_catalog_all_routes_no_trade",
            all_task_routes_no_trade,
            evidence=f"{len(task_boundary_rows)} task/lifecycle route rows declare no trade execution",
        ),
        _trade_isolation_row(
            "task_catalog_all_routes_no_strategy_action_mutation",
            all_task_routes_no_action,
            evidence=f"{len(task_boundary_rows)} task/lifecycle route rows declare no strategy action mutation",
        ),
        _trade_isolation_row(
            "all_known_post_routes_button_gated",
            route_coverage.get("all_known_post_routes_button_gated") is True,
            evidence=f"{route_coverage.get('known_post_route_count', 0)} known POST routes in task catalog",
        ),
        _trade_isolation_row(
            "call_ledger_required_for_all_known_post_routes",
            route_coverage.get("call_ledger_required_for_all_known_post_routes") is True,
            evidence="task catalog route coverage requires call_ledger for all known POST routes",
        ),
        _trade_isolation_row(
            "frontend_boundaries_visible",
            frontend_boundaries_visible,
            evidence="risk, task catalog, and packet registry surfaces show no-trade/no-action boundaries",
        ),
        _trade_isolation_row(
            "future_trading_requires_separate_approved_design",
            True,
            evidence="ordinary Command Center 3 migration roadmap excludes broker/order integration",
        ),
    ]
    blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    audit = {
        "schema_version": TRADE_ISOLATION_SCHEMA_VERSION,
        "status": "trade_isolation_ready" if not blockers else "trade_isolation_blocked",
        "scope": "command_center_3_cache_task_frontend_contract",
        "task_catalog_schema_version": catalog.get("schema_version"),
        "known_post_route_count": route_coverage.get("known_post_route_count", 0),
        "task_boundary_row_count": len(task_boundary_rows),
        "frontend_surface_count": len(frontend_rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "no_automatic_order_path_in_task_catalog": all_task_routes_no_trade and all_task_routes_no_action,
        "research_paths_cannot_mutate_strategy_action": policy.get("does_not_modify_strategy_action") is True and all_task_routes_no_action,
        "frontend_surfaces_are_display_only_for_trade_boundaries": frontend_boundaries_visible,
        "future_trade_integration_out_of_roadmap": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
    }
    return audit, rows, task_boundary_rows + frontend_rows


def read_risk_guardrails_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    risk_alerts = _as_dict(snapshot_map.get("risk_alerts"))
    guardrail = _as_dict(snapshot_map.get("execution_guardrail_overview"))
    legacy_chain = _as_dict(snapshot_map.get("legacy_decision_chain_summary"))
    recovery_ledger = _as_dict(snapshot_map.get("strategy_prerequisite_recovery_ledger"))
    position_budget = _as_dict(snapshot_map.get("position_risk_budget"))
    risk_breakdown = _as_dict(snapshot_map.get("risk_breakdown"))
    recovery_status = _as_dict(snapshot_map.get("recovery_result_status_strip"))

    source_values = (risk_alerts, guardrail, legacy_chain, recovery_ledger, recovery_status, position_budget, risk_breakdown, snapshot_map.get("safety_line"))
    has_cache = any(bool(item) for item in source_values)
    if risk_alerts or guardrail or legacy_chain or position_budget or risk_breakdown:
        status = "ready"
    elif has_cache:
        status = "partial"
    else:
        status = "cache_missing"

    policy = {
        "cache_api_external_calls": False,
        "does_not_call_tushare": True,
        "does_not_call_deepseek": True,
        "does_not_call_github": True,
        "does_not_refresh_data": True,
        "does_not_run_backtest": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "does_not_clear_risk_flags": True,
        "risk_guardrails_are_read_only": True,
        "risk_guardrails_are_not_trade_orders": True,
        "post_task_required_for_refresh": True,
        "trade_isolation_audit_is_read_only": True,
        "future_trade_integration_requires_separate_approved_design": True,
    }
    trade_isolation_audit, trade_isolation_rows, trade_isolation_boundary_rows = _trade_isolation_audit(policy)
    counts = _counts(risk_alerts, guardrail, legacy_chain)
    counts.update(
        {
            "trade_isolation_check_count": len(trade_isolation_rows),
            "trade_isolation_blocker_count": trade_isolation_audit.get("blocking_criterion_count", 0),
            "task_trade_boundary_row_count": trade_isolation_audit.get("task_boundary_row_count", 0),
            "trade_boundary_frontend_surface_count": trade_isolation_audit.get("frontend_surface_count", 0),
        }
    )

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "snapshot_available": bool(snapshot),
        "source_packet_keys": [
            "risk_alerts",
            "safety_line",
            "execution_guardrail_overview",
            "legacy_decision_chain_summary",
            "strategy_prerequisite_recovery_ledger",
            "recovery_result_status_strip",
            "position_risk_budget",
            "risk_breakdown",
        ],
        "summary": risk_alerts.get("recovery_priority_summary")
        or guardrail.get("summary")
        or legacy_chain.get("summary")
        or "风险护栏 cache 只读展示；无缓存时不自动刷新。",
        "risk_alerts": risk_alerts,
        "hard_risk_rows": _list_rows(risk_alerts.get("hard_risk_alerts"), text_key="alert"),
        "must_not_do_rows": _list_rows(risk_alerts.get("must_not_do"), text_key="guardrail"),
        "reduce_condition_rows": _list_rows(risk_alerts.get("reduce_conditions"), text_key="condition"),
        "data_gap_rows": _list_rows(risk_alerts.get("data_gaps"), text_key="gap"),
        "risk_rows": _risk_rows(risk_breakdown),
        "execution_guardrail_overview": guardrail,
        "legacy_decision_chain_summary": legacy_chain,
        "strategy_prerequisite_recovery_ledger": recovery_ledger,
        "recovery_result_status_strip": recovery_status,
        "position_risk_budget": position_budget,
        "risk_breakdown": risk_breakdown,
        "safety_line": snapshot_map.get("safety_line"),
        "counts": counts,
        "policy": policy,
        "trade_isolation_audit": trade_isolation_audit,
        "trade_isolation_rows": trade_isolation_rows,
        "trade_isolation_boundary_rows": trade_isolation_boundary_rows,
        "call_ledger": [
            {
                "api": "local_risk_guardrails_cache",
                "source_snapshot": "command_center_latest.json",
                "call_status": "cache_read" if snapshot else "cache_missing",
                "local_fetched_at": _now_iso(),
                "external": False,
            }
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/risk/cache 只读展示风险护栏缓存；不会刷新数据或运行回测。",
            "风险提示只约束解释和页面展示，不会自动下单或修改 strategy action。",
            "本页不调用 Tushare、DeepSeek 或 GitHub；缺失风险不得写成无风险。",
            "trade_isolation_audit 只读消费本地 task catalog 和前端边界文案；不会创建任务、不会接入券商或订单接口。",
        ],
    }
    if status == "cache_missing":
        packet["warnings"].append("当前没有风险护栏缓存；3.0 cache 页不会自动刷新。")
    return _json_safe(packet)
