from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


READY_STATES = {"ready", "recovered", "available", "ok", "success", "completed"}
CACHE_STATES = {"cached", "cache_only", "stale_cache", "fallback", "fallback_used", "using_cache"}
BLOCKED_STATES = {
    "blocked",
    "failed",
    "failure",
    "error",
    "permission_denied",
    "disabled_this_session",
    "network_failed",
    "not_configured",
}


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _normalize_decision_chain_state(
    payload: Mapping[str, Any],
    *,
    status: Any = "",
    data_status: Any = "",
    recovery_state: Any = "",
    capability_state: Any = "",
) -> str:
    explicit = to_text(payload.get("decision_chain_state")).lower()
    if explicit in {"ready", "cache_only", "blocked", "waiting"}:
        return explicit
    if payload.get("can_enter_decision_chain") is False:
        return "blocked"

    state_values = {
        to_text(status).lower(),
        to_text(data_status).lower(),
        to_text(recovery_state).lower(),
        to_text(capability_state).lower(),
    }
    if state_values & BLOCKED_STATES:
        return "blocked"
    if state_values & CACHE_STATES:
        return "cache_only"
    if state_values & READY_STATES:
        return "ready"
    return "waiting"


def build_legacy_packet_decision_contract(
    payload: Any = None,
    *,
    label: Any = "旧能力",
    status: Any = "",
    data_status: Any = "",
    recovery_state: Any = "",
    capability_state: Any = "",
) -> dict:
    """Return the shared command-center decision-chain contract for legacy packets."""
    source = as_mapping(payload)
    label_text = to_text(label, "旧能力")
    state = _normalize_decision_chain_state(
        source,
        status=status,
        data_status=data_status,
        recovery_state=recovery_state,
        capability_state=capability_state,
    )
    state_label = {
        "ready": "已验证",
        "cache_only": "缓存辅助",
        "blocked": "阻断决策",
        "waiting": "待验证",
    }.get(state, "待验证")
    effect = {
        "ready": f"{label_text}可进入证据链，但仍需价格、纪律和仓位共同确认。",
        "cache_only": f"{label_text}只能作为缓存/替代证据；执行前复核日期、来源和覆盖口径。",
        "blocked": f"{label_text}仍阻断加仓、追高、加融资或把风险写成已排除。",
        "waiting": f"{label_text}待验证；未回流前只能保留安全空态。",
    }.get(state, f"{label_text}待验证。")
    return {
        "decision_chain_state": state,
        "decision_chain_label": state_label,
        "can_enter_decision_chain": state in {"ready", "cache_only"},
        "decision_chain_effect": effect,
        "decision_chain_stage": "数据能力状态 → 市场分析方法 → 趋势推演 → 策略执行 → 今日总决策",
        "external_call_policy": to_text(source.get("external_call_policy"), "not_triggered"),
        "deepseek_called": False,
    }
