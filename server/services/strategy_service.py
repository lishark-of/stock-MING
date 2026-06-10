from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any

import command_center_strategy_summary
from server.services import packet_service


PACKET_KEY = "command_center_3_strategy_trace_cache"
SCHEMA_VERSION = "strategy_trace_cache.v1"
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
        return {"serialization_error_safe": "strategy_trace_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _status_from_packet(packet: Mapping[str, Any]) -> str:
    status = str(packet.get("status") or "").strip()
    if status and status != "cache_missing":
        return "ready" if status in {"ready", "cached", "partial", "waiting"} else status
    if packet.get("action") or packet.get("summary") or packet.get("strategy_execution_trace"):
        return "ready"
    return "cache_missing"


def _action_summary(strategy_packet: Mapping[str, Any], view_model: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "action": strategy_packet.get("action"),
        "action_label": view_model.get("action_label") or strategy_packet.get("action") or "尚未生成",
        "confidence": strategy_packet.get("confidence"),
        "confidence_label": view_model.get("confidence_label") or strategy_packet.get("confidence") or "待生成",
        "position_advice": strategy_packet.get("position_advice"),
        "summary": strategy_packet.get("summary") or view_model.get("summary"),
        "source": strategy_packet.get("source") or "strategy_execution_packet",
        "action_source": "strategy_execution_packet",
        "does_not_modify_strategy_action": True,
    }


def _decision_summary(decision_packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": decision_packet.get("status"),
        "overall_action": decision_packet.get("overall_action"),
        "market_bias": decision_packet.get("market_bias"),
        "risk_level": decision_packet.get("risk_level"),
        "summary": decision_packet.get("summary"),
        "source": decision_packet.get("source") or "command_center_decision_packet",
    }


def read_strategy_trace_cache() -> dict[str, Any]:
    raw_strategy = packet_service.read_packet("strategy_execution_packet")
    raw_decision = packet_service.read_packet("command_center_decision_packet")

    safe_strategy = _safe_value(raw_strategy)
    safe_decision = _safe_value(raw_decision)
    strategy_packet = _as_dict(safe_strategy)
    decision_packet = _as_dict(safe_decision)

    view_model = command_center_strategy_summary.build_strategy_summary_view_model(strategy_packet)
    safe_view_model = _safe_value(view_model)
    if not isinstance(safe_view_model, dict):
        safe_view_model = {}

    strategy_trace = safe_view_model.get("strategy_execution_trace")
    if not isinstance(strategy_trace, dict):
        strategy_trace = {}

    status = _status_from_packet(strategy_packet)
    call_status = "cache_read" if status != "cache_missing" else "cache_missing"
    warnings = [
        "GET /api/strategy/cache 只读展示 strategy_execution_packet / command_center_decision_packet。",
        "本页不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，也不会修改 strategy_execution_packet.action。",
        "action 只能来自已存在的 strategy_execution_packet；3.0 前端不得重新计算或改写。",
    ]
    if status == "cache_missing":
        warnings.append("当前未发现 strategy_execution_packet 缓存；请在旧工作台或后续按钮门控任务中生成。")

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "source_packet_keys": ["strategy_execution_packet", "command_center_decision_packet"],
        "action_summary": _action_summary(strategy_packet, safe_view_model),
        "decision_summary": _decision_summary(decision_packet),
        "strategy_trace": strategy_trace,
        "strategy_view_model": safe_view_model,
        "strategy_packet": strategy_packet,
        "decision_packet": decision_packet,
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_tushare": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_run_backtest": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_decision_packet": True,
            "action_source": "strategy_execution_packet",
            "decision_source": "command_center_decision_packet",
            "post_task_required_for_recompute": True,
        },
        "call_ledger": [
            {
                "api": "local_strategy_trace_cache",
                "source_packet_key": "strategy_execution_packet",
                "decision_packet_key": "command_center_decision_packet",
                "call_status": call_status,
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
        "does_not_modify_decision_packet": True,
        "contains_secret": False,
        "warnings": warnings,
    }
    return _json_safe(packet)
