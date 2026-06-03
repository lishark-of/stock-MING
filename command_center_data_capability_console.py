from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_data_capability_dashboard import build_data_capability_dashboard_view_model
from command_center_data_issue_explainer import build_data_issue_explainer_packet


MAX_QUEUE_ITEMS = 5

AVAILABLE_STATES = {"available", "ready", "ok", "success"}
BLOCKED_STATES = {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}
MANUAL_STATES = {"requires_manual_refresh"}
STALE_STATES = {"empty_recent", "stale_cache", "fallback_used", "unknown", "missing"}


def _as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _queue_item(item: Mapping[str, Any]) -> dict:
    return {
        "label": _to_text(item.get("label"), "数据能力"),
        "provider": _to_text(item.get("provider"), "数据源"),
        "api": _to_text(item.get("api")),
        "state": _to_text(item.get("state"), "unknown"),
        "status_label": _to_text(item.get("status_label") or item.get("status"), "待验证"),
        "tone": _to_text(item.get("tone"), "missing"),
        "latest_date": _to_text(item.get("latest_date") or item.get("updated_at")),
        "meaning": _to_text(item.get("meaning") or item.get("action_hint"), "待验证。"),
        "decision_impact": _to_text(item.get("decision_impact"), "不能单独作为交易依据。"),
        "next_action": _to_text(item.get("next_action") or item.get("action_hint"), "保留安全空态或手动刷新。"),
    }


def _dedupe_queue(items: list[dict], limit: int = MAX_QUEUE_ITEMS) -> list[dict]:
    result = []
    seen = set()
    for item in items:
        key = (item.get("provider"), item.get("api"), item.get("label"), item.get("state"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _tone(status: str) -> str:
    if status == "ready":
        return "ready"
    if status == "blocked":
        return "failed"
    if status == "partial":
        return "stale"
    return "missing"


def _status(ready_count: int, blocked_count: int, pending_count: int) -> str:
    if blocked_count:
        return "blocked"
    if pending_count:
        return "partial"
    if ready_count:
        return "ready"
    return "missing"


def _headline(status: str, ready_count: int, blocked_count: int, pending_count: int) -> str:
    if status == "blocked":
        return f"数据能力有 {blocked_count} 个阻断项，不能直接放大仓位。"
    if status == "partial":
        return f"数据能力部分可用，{pending_count} 个接口仍需验证或手动刷新。"
    if status == "ready":
        return f"数据能力已读取，{ready_count} 个接口可进入证据链。"
    return "尚未检测数据能力；页面打开不会自动请求外部接口。"


def build_data_capability_console_packet(
    data_capability_packet: Any = None,
    data_gap_report: Any = None,
    data_issue_explainer: Any = None,
    refresh_summary: Any = None,
    errors: Any = None,
) -> dict:
    dashboard = build_data_capability_dashboard_view_model(data_capability_packet, data_gap_report)
    issue_packet = _as_mapping(data_issue_explainer) or build_data_issue_explainer_packet(
        data_capability_packet=data_capability_packet,
        data_gap_report=data_gap_report,
        refresh_summary=refresh_summary,
        errors=errors,
    )
    issue_items = [_queue_item(item) for item in _as_list(issue_packet.get("items")) if _as_mapping(item)]
    ready_items = _dedupe_queue([item for item in issue_items if item["state"] in AVAILABLE_STATES])
    blocked_items = _dedupe_queue([item for item in issue_items if item["state"] in BLOCKED_STATES])
    manual_items = _dedupe_queue([item for item in issue_items if item["state"] in MANUAL_STATES])
    stale_items = _dedupe_queue([item for item in issue_items if item["state"] in STALE_STATES])
    pending_count = len(manual_items) + len(stale_items)
    status = _status(len(ready_items), len(blocked_items), pending_count)
    return {
        "status": status,
        "tone": _tone(status),
        "headline": _headline(status, len(ready_items), len(blocked_items), pending_count),
        "short_answer": _to_text(issue_packet.get("short_answer"), "尚未检测数据能力；不会自动 ping 外部接口。"),
        "provider_cards": _as_list(dashboard.get("provider_cards")),
        "ready_items": ready_items,
        "blocked_items": blocked_items,
        "manual_items": manual_items,
        "stale_items": stale_items,
        "next_actions": _as_list(issue_packet.get("next_actions"))[:MAX_QUEUE_ITEMS],
        "available_count": len(ready_items),
        "blocked_count": len(blocked_items),
        "manual_count": len(manual_items),
        "stale_count": len(stale_items),
        "source": "local data capability console",
        "manual_note": "本控制台只读取本地检测 packet；不会自动调用 Tushare、AkShare、yfinance、Supabase、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }
