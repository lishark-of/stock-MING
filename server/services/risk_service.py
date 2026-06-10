from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any

from server.services import packet_service


PACKET_KEY = "command_center_3_risk_guardrails_cache"
SCHEMA_VERSION = "risk_guardrails_cache.v1"
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
        "counts": _counts(risk_alerts, guardrail, legacy_chain),
        "policy": {
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
        },
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
        ],
    }
    if status == "cache_missing":
        packet["warnings"].append("当前没有风险护栏缓存；3.0 cache 页不会自动刷新。")
    return _json_safe(packet)
