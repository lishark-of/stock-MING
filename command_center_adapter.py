from __future__ import annotations

import datetime
from collections.abc import Mapping
from copy import deepcopy
from numbers import Number
from typing import Any


COMMAND_CENTER_MODULES = (
    ("market", "市场环境"),
    ("quant", "量化推演"),
    ("discipline", "交易纪律"),
    ("margin_etf", "融资 ETF"),
    ("next_ticket", "下一票雷达"),
)

READY_STATUSES = {"已刷新", "ready", "completed", "complete", "ok", "partial", "partial_failed"}
CACHED_LABELS = {"使用缓存"}


def as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def get_nested(mapping: Any, path: str | list[str] | tuple[str, ...], default: Any = None) -> Any:
    current: Any = mapping
    parts = path.split(".") if isinstance(path, str) else list(path)
    for part in parts:
        if not isinstance(current, Mapping):
            return default
        if part not in current:
            return default
        current = current[part]
    return current


def _json_friendly(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_friendly(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_friendly(item) for item in value]
    if isinstance(value, (str, bool, Number)) or value is None:
        return value
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return str(value)


def clone_packet(packet: Any) -> dict:
    mapping = as_mapping(packet)
    if not mapping:
        return {}
    try:
        return _json_friendly(deepcopy(mapping))
    except Exception:
        return _json_friendly(mapping)


def pick_display_packet(state: Any, packet_key: str, last_success_key: str) -> dict:
    state_mapping = as_mapping(state)
    packet = clone_packet(state_mapping.get(packet_key))
    if packet:
        return packet
    return clone_packet(state_mapping.get(last_success_key))


def attach_child_packet(live_packet: Any, child_key: str, child_packet: Any) -> dict:
    payload = clone_packet(live_packet)
    child = clone_packet(child_packet)
    if child:
        payload[child_key] = child
    return payload


def _section_coverage(section: Any) -> str:
    payload = as_mapping(section)
    if not payload:
        return "missing"

    status = str(payload.get("status") or "").strip()
    refresh_label = str(payload.get("refresh_label") or "").strip()
    if payload.get("is_fresh") is True or status in READY_STATUSES:
        return "ready"
    if payload.get("last_success") or payload.get("stale") or refresh_label in CACHED_LABELS:
        return "cached"
    return "missing"


def _packet_coverage(packet: Any) -> str:
    payload = as_mapping(packet)
    if not payload:
        return "missing"

    status = str(payload.get("status") or "").strip()
    if status in READY_STATUSES:
        return "ready"
    if payload.get("last_success") or payload.get("stale"):
        return "cached"
    return "missing"


def build_data_status(live_packet: Any, strategy_execution_packet: Any = None, decision_packet: Any = None) -> dict:
    live_payload = as_mapping(live_packet)
    data_status = {
        module_key: _section_coverage(live_payload.get(module_key))
        for module_key, _label in COMMAND_CENTER_MODULES
    }
    data_status["strategy_execution"] = _packet_coverage(strategy_execution_packet)
    data_status["decision"] = _packet_coverage(decision_packet)
    return data_status


def build_module_statuses(live_packet: Any) -> list[dict]:
    live_payload = as_mapping(live_packet)
    statuses = []
    for module_key, label in COMMAND_CENTER_MODULES:
        section = as_mapping(live_payload.get(module_key))
        statuses.append(
            {
                "key": module_key,
                "label": label,
                "status": section.get("status") or "未刷新",
                "refresh_label": section.get("refresh_label") or "",
                "updated_at": section.get("updated_at") or "",
                "source": section.get("source") or "",
                "coverage": _section_coverage(section),
                "stale": bool(section.get("stale")),
                "deepseek_called": bool(section.get("deepseek_called")),
            }
        )
    return statuses


def build_workflow_steps(data_status: Mapping[str, str]) -> list[dict]:
    live_coverages = [
        data_status.get("market"),
        data_status.get("quant"),
        data_status.get("discipline"),
        data_status.get("margin_etf"),
        data_status.get("next_ticket"),
    ]
    has_live_data = any(status in {"ready", "cached"} for status in live_coverages)
    has_strategy = data_status.get("strategy_execution") in {"ready", "cached"}
    has_decision = data_status.get("decision") in {"ready", "cached"}
    return [
        {
            "key": "refresh_basic",
            "label": "刷新今日基础数据",
            "status": "ready" if has_live_data else "waiting",
            "button_gated": True,
            "deepseek_called": False,
        },
        {
            "key": "strategy_execution",
            "label": "生成策略执行建议",
            "status": "ready" if has_strategy else "waiting",
            "button_gated": True,
            "deepseek_called": False,
        },
        {
            "key": "daily_decision",
            "label": "生成今日总决策",
            "status": "ready" if has_decision else "waiting",
            "button_gated": True,
            "deepseek_called": False,
        },
        {
            "key": "deepseek_explain",
            "label": "DeepSeek 综合解释",
            "status": "manual_deep",
            "button_gated": True,
            "deepseek_called": False,
        },
    ]


def build_command_center_view_model(
    live_packet: Any = None,
    strategy_execution_packet: Any = None,
    decision_packet: Any = None,
    refresh_level: str | None = None,
    generated_at: str | None = None,
) -> dict:
    live_payload = clone_packet(live_packet)
    strategy_payload = clone_packet(strategy_execution_packet)
    decision_payload = clone_packet(decision_packet)

    if strategy_payload:
        live_payload["strategy_execution"] = strategy_payload
    if decision_payload:
        live_payload["decision"] = decision_payload

    effective_refresh_level = refresh_level or live_payload.get("refresh_level")
    effective_generated_at = generated_at or live_payload.get("updated_at") or live_payload.get("generated_at")
    data_status = build_data_status(live_payload, strategy_payload, decision_payload)

    return {
        "live_packet": live_payload,
        "strategy_execution_packet": strategy_payload,
        "decision_packet": decision_payload,
        "has_live_packet": bool(live_payload),
        "has_strategy_execution_packet": bool(strategy_payload),
        "has_decision_packet": bool(decision_payload),
        "refresh_level": effective_refresh_level,
        "generated_at": effective_generated_at,
        "data_status": data_status,
        "module_statuses": build_module_statuses(live_payload),
        "workflow_steps": build_workflow_steps(data_status),
    }
