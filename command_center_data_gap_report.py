from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_ITEMS = 12
MAX_CHECKS = 8

AVAILABLE_STATES = {"available", "ready", "ok", "success"}
RESTRICTED_STATES = {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}
PENDING_STATES = {"empty_recent", "stale_cache", "fallback_used", "requires_manual_refresh", "unknown", "missing"}


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = to_text(value)
        if text:
            return text
    return default


def _dedupe(values: Any, limit: int = MAX_CHECKS) -> list[str]:
    raw_values = values if isinstance(values, (list, tuple)) else [values]
    items = []
    seen = set()
    for item in raw_values:
        if isinstance(item, Mapping):
            text = _first_text(item.get("action_hint"), item.get("message"), item.get("reason"), item.get("summary"), item.get("label"))
        else:
            text = to_text(item)
        if text and text not in seen:
            seen.add(text)
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _normalize_state(item: Mapping[str, Any]) -> str:
    state = _first_text(item.get("state"), item.get("capability_state"), item.get("status"))
    low = state.lower()
    if low in AVAILABLE_STATES | RESTRICTED_STATES | PENDING_STATES:
        return low
    if "权限" in state or "denied" in low:
        return "permission_denied"
    if "跳过" in state:
        return "disabled_this_session"
    if "缓存" in state:
        return "stale_cache"
    if "无数据" in state or "近期无" in state:
        return "empty_recent"
    if "失败" in state or "error" in low:
        return "failed"
    if "手动" in state:
        return "requires_manual_refresh"
    if "可用" in state or "通过" in state:
        return "available"
    return "unknown"


def _decision_impact(state: str, label: str) -> str:
    if state == "available":
        return f"{label}可作为辅助验证，但仍需结合价格纪律。"
    if state == "permission_denied":
        return f"{label}权限不足，不能把缺失数据当成利好。"
    if state == "disabled_this_session":
        return f"{label}本会话跳过重复请求，需手动重试后再验证。"
    if state == "empty_recent":
        return f"{label}近期无记录，只能说明无可验证事件。"
    if state == "stale_cache":
        return f"{label}正在使用缓存，需要复核交易日。"
    if state == "requires_manual_refresh":
        return f"{label}需要手动刷新，页面打开不会自动触发。"
    if state in {"network_failed", "failed", "not_configured"}:
        return f"{label}不可用，当前不应纳入决策依据。"
    return f"{label}待验证，当前只能作为数据缺口记录。"


def _item_from_capability(raw: Any, provider_default: str = "") -> dict:
    item = as_mapping(raw)
    label = _first_text(item.get("label"), item.get("section"), item.get("api"), default="数据能力")
    state = _normalize_state(item)
    return {
        "key": _first_text(item.get("key"), item.get("section"), item.get("api"), default="data_capability"),
        "label": label,
        "provider": _first_text(item.get("provider"), item.get("source"), default=provider_default or "数据能力"),
        "api": to_text(item.get("api")),
        "state": state,
        "status": _first_text(item.get("status"), item.get("capability_label"), default=state),
        "source": _first_text(item.get("source"), default=provider_default or "数据能力"),
        "updated_at": _first_text(item.get("updated_at"), item.get("latest_date")),
        "reason": _first_text(item.get("error"), item.get("reason"), item.get("action_hint")),
        "action_hint": _first_text(item.get("action_hint"), default=_decision_impact(state, label)),
        "decision_impact": _decision_impact(state, label),
    }


def _items_from_capability(packet: Any) -> list[dict]:
    payload = as_mapping(packet)
    provider_default = _first_text(payload.get("source"), payload.get("provider"), default="数据能力")
    return [_item_from_capability(item, provider_default=provider_default) for item in as_list(payload.get("items"))][:MAX_ITEMS]


def _items_from_facts(packet: Any) -> list[dict]:
    payload = as_mapping(packet)
    items = []
    for raw in as_list(payload.get("items")):
        item = as_mapping(raw)
        if not item:
            continue
        state = _normalize_state(item)
        label = _first_text(item.get("label"), item.get("key"), default="A股事实")
        items.append(
            {
                "key": _first_text(item.get("key"), default="a_share_fact"),
                "label": label,
                "provider": "Tushare A股事实",
                "api": to_text(item.get("api")),
                "state": state,
                "status": _first_text(item.get("status"), default=state),
                "source": _first_text(item.get("source"), default="Tushare + local cache"),
                "updated_at": to_text(item.get("updated_at")),
                "reason": _first_text(item.get("risk"), item.get("evidence")),
                "action_hint": _first_text(item.get("action_hint"), default=_decision_impact(state, label)),
                "decision_impact": _decision_impact(state, label),
            }
        )
    return items[:MAX_ITEMS]


def _items_from_errors(errors: Any, refresh_summary: Any = None, live_packet: Any = None) -> list[dict]:
    rows = []
    for source_packet in (as_mapping(refresh_summary), as_mapping(live_packet)):
        raw_errors = source_packet.get("error_items") or source_packet.get("errors") or []
        if isinstance(raw_errors, (str, Mapping)):
            raw_errors = [raw_errors]
        rows.extend(as_list(raw_errors))
    rows.extend(as_list(errors))
    items = []
    for raw in rows:
        row = as_mapping(raw)
        message = _first_text(row.get("message"), row.get("error"), row.get("last_error"), raw)
        if not message:
            continue
        label = _first_text(row.get("module"), row.get("label"), default="刷新错误")
        items.append(
            {
                "key": _first_text(row.get("key"), row.get("module"), default="refresh_error"),
                "label": label,
                "provider": _first_text(row.get("provider"), row.get("source"), default="刷新结果"),
                "api": to_text(row.get("api")),
                "state": "failed",
                "status": "失败",
                "source": _first_text(row.get("source"), default="刷新结果"),
                "updated_at": _first_text(row.get("updated_at"), row.get("finished_at")),
                "reason": message,
                "action_hint": f"{label}刷新失败：保留上次成功结果，手动排查后再重试。",
                "decision_impact": f"{label}失败，当前只能展示缓存或空态。",
            }
        )
    return items[:MAX_ITEMS]


def _merge_items(*groups: list[dict]) -> list[dict]:
    merged = []
    seen = set()
    for group in groups:
        for item in group:
            key = (item.get("provider"), item.get("key"), item.get("api"), item.get("label"), item.get("state"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= MAX_ITEMS:
                return merged
    return merged


def _trust_level(available_count: int, restricted_count: int, pending_count: int, failed_count: int) -> str:
    if failed_count or restricted_count >= 2:
        return "low"
    if available_count and restricted_count == 0 and failed_count == 0:
        return "high" if pending_count == 0 else "medium"
    if available_count:
        return "medium"
    return "low" if restricted_count or pending_count else "unknown"


def build_command_center_data_gap_report(
    data_capability_packet: Any = None,
    facts_packet: Any = None,
    refresh_summary: Any = None,
    live_packet: Any = None,
    errors: Any = None,
) -> dict:
    items = _merge_items(
        _items_from_capability(data_capability_packet),
        _items_from_facts(facts_packet),
        _items_from_errors(errors, refresh_summary=refresh_summary, live_packet=live_packet),
    )
    available = [item for item in items if item["state"] in AVAILABLE_STATES]
    restricted = [item for item in items if item["state"] in RESTRICTED_STATES]
    pending = [item for item in items if item["state"] in PENDING_STATES]
    failed = [item for item in items if item["state"] in {"failed", "network_failed"}]
    trust_level = _trust_level(len(available), len(restricted), len(pending), len(failed))
    if not items:
        summary = "尚未检测数据能力；页面打开不会自动请求 Tushare、AkShare、yfinance 或 Supabase。"
        status = "unknown"
    else:
        summary = (
            f"可用 {len(available)}｜受限/失败 {len(restricted)}｜待验证/缓存 {len(pending)}｜"
            f"可信度：{ {'high': '较高', 'medium': '中等', 'low': '偏低', 'unknown': '待确认'}[trust_level] }"
        )
        status = "ready" if trust_level in {"high", "medium"} else "partial"
    next_checks = _dedupe(
        [item.get("action_hint") for item in restricted + pending + failed],
        limit=MAX_CHECKS,
    )
    blocked = [item.get("decision_impact") for item in restricted + failed]
    return {
        "status": status,
        "summary": summary,
        "trust_level": trust_level,
        "available_count": len(available),
        "restricted_count": len(restricted),
        "pending_count": len(pending),
        "failed_count": len(failed),
        "usable_for_decision": trust_level in {"high", "medium"},
        "items": items,
        "next_manual_checks": next_checks,
        "blocked_decision_reasons": _dedupe(blocked, limit=MAX_CHECKS),
        "deepseek_called": False,
    }
