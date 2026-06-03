from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_PROVIDER_ITEMS = 4
MAX_MANUAL_ACTIONS = 6

AVAILABLE_STATES = {"available", "ready", "ok", "success"}
RESTRICTED_STATES = {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}
PENDING_STATES = {"empty_recent", "stale_cache", "fallback_used", "requires_manual_refresh", "unknown", "missing"}

STATE_LABELS = {
    "available": "可用",
    "permission_denied": "权限不足",
    "disabled_this_session": "本会话跳过",
    "not_configured": "未配置",
    "network_failed": "网络失败",
    "failed": "调用失败",
    "empty_recent": "近期无数据",
    "stale_cache": "使用缓存",
    "fallback_used": "替代口径",
    "requires_manual_refresh": "需要手动刷新",
    "unknown": "待验证",
    "missing": "待刷新",
}

PROVIDER_ORDER = ("Tushare", "AkShare", "yfinance", "Supabase")


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


def normalize_capability_state(value: Any) -> str:
    text = to_text(value).lower()
    if text in AVAILABLE_STATES | RESTRICTED_STATES | PENDING_STATES:
        return text
    if "权限" in text or "denied" in text or "unauthorized" in text:
        return "permission_denied"
    if "跳过" in text:
        return "disabled_this_session"
    if "缓存" in text:
        return "stale_cache"
    if "手动" in text:
        return "requires_manual_refresh"
    if "无数据" in text or "近期无" in text:
        return "empty_recent"
    if "未配置" in text:
        return "not_configured"
    if "失败" in text or "error" in text:
        return "failed"
    if "可用" in text or "通过" in text:
        return "available"
    return "unknown"


def _tone_for_state(state: str) -> str:
    if state in AVAILABLE_STATES:
        return "ready"
    if state in RESTRICTED_STATES:
        return "failed"
    if state in {"stale_cache", "fallback_used"}:
        return "stale"
    return "missing"


def _provider_name(item: Mapping[str, Any], fallback: str = "数据源") -> str:
    provider = _first_text(item.get("provider"), item.get("source"), fallback)
    if "Tushare" in provider:
        return "Tushare"
    if "AkShare" in provider:
        return "AkShare"
    if "yfinance" in provider or "Yahoo" in provider:
        return "yfinance"
    if "Supabase" in provider:
        return "Supabase"
    return provider


def _decision_text(state: str, label: str) -> str:
    if state in AVAILABLE_STATES:
        return f"{label}可作为辅助验证。"
    if state == "permission_denied":
        return f"{label}权限不足；不能把缺失数据当成利好。"
    if state == "disabled_this_session":
        return f"{label}本会话跳过重复请求；如权限恢复需手动重试。"
    if state == "requires_manual_refresh":
        return f"{label}需要手动刷新；页面打开不会自动请求。"
    if state == "stale_cache":
        return f"{label}正在使用缓存；需要复核交易日和更新时间。"
    if state == "empty_recent":
        return f"{label}近期无数据；可能是非交易日、未发布或标的不覆盖。"
    if state == "not_configured":
        return f"{label}未配置；需检查本地 token/secrets。"
    if state in {"failed", "network_failed"}:
        return f"{label}不可用；保留上次成功或安全空态。"
    return f"{label}待验证；当前不能作为核心依据。"


def normalize_capability_item(item: Any) -> dict:
    payload = as_mapping(item)
    label = _first_text(payload.get("label"), payload.get("section"), payload.get("api"), payload.get("table"), default="数据能力")
    state = normalize_capability_state(payload.get("state") or payload.get("capability_state") or payload.get("status"))
    return {
        "key": _first_text(payload.get("key"), payload.get("section"), payload.get("api"), payload.get("table"), default="data_capability"),
        "label": label,
        "provider": _provider_name(payload),
        "api": to_text(payload.get("api") or payload.get("table")),
        "state": state,
        "status_label": _first_text(payload.get("status"), payload.get("capability_label"), default=STATE_LABELS.get(state, "待验证")),
        "tone": _tone_for_state(state),
        "latest_date": _first_text(payload.get("latest_date"), payload.get("updated_at")),
        "updated_at": to_text(payload.get("updated_at")),
        "action_hint": _first_text(payload.get("action_hint"), default=_decision_text(state, label)),
        "error": to_text(payload.get("error")),
        "deepseek_called": False,
    }


def _items_from_capability(data_capability: Any) -> list[dict]:
    payload = as_mapping(data_capability)
    return [normalize_capability_item(item) for item in as_list(payload.get("items")) if as_mapping(item)]


def _items_from_gap_report(data_gap_report: Any) -> list[dict]:
    payload = as_mapping(data_gap_report)
    return [normalize_capability_item(item) for item in as_list(payload.get("items")) if as_mapping(item)]


def _merge_items(primary: list[dict], fallback: list[dict]) -> list[dict]:
    merged = []
    seen = set()
    for item in primary + fallback:
        key = (item.get("provider"), item.get("key"), item.get("api"), item.get("label"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _provider_cards(items: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(item["provider"], []).append(item)
    providers = sorted(grouped, key=lambda name: (PROVIDER_ORDER.index(name) if name in PROVIDER_ORDER else 99, name))
    cards = []
    for provider in providers:
        rows = grouped[provider]
        ready = [item for item in rows if item["state"] in AVAILABLE_STATES]
        failed = [item for item in rows if item["state"] in RESTRICTED_STATES]
        pending = [item for item in rows if item["state"] in PENDING_STATES]
        if failed:
            tone = "failed"
        elif pending:
            tone = "stale"
        elif ready:
            tone = "ready"
        else:
            tone = "missing"
        cards.append(
            {
                "provider": provider,
                "tone": tone,
                "summary": f"可用 {len(ready)}｜受限/失败 {len(failed)}｜待验证/缓存 {len(pending)}",
                "available_count": len(ready),
                "restricted_count": len(failed),
                "pending_count": len(pending),
                "items": rows[:MAX_PROVIDER_ITEMS],
            }
        )
    return cards


def _manual_actions(items: list[dict], data_gap_report: Any) -> list[str]:
    actions = []
    for item in items:
        if item["state"] in RESTRICTED_STATES | PENDING_STATES:
            actions.append(item["action_hint"])
    actions.extend(to_text(item) for item in as_list(as_mapping(data_gap_report).get("next_manual_checks")))
    deduped = []
    seen = set()
    for action in actions:
        text = to_text(action)
        if text and text not in seen:
            seen.add(text)
            deduped.append(text)
        if len(deduped) >= MAX_MANUAL_ACTIONS:
            break
    return deduped


def build_data_capability_dashboard_view_model(data_capability: Any = None, data_gap_report: Any = None) -> dict:
    capability = as_mapping(data_capability)
    gap_report = as_mapping(data_gap_report)
    items = _merge_items(_items_from_capability(capability), _items_from_gap_report(gap_report))
    provider_cards = _provider_cards(items)
    available = [item for item in items if item["state"] in AVAILABLE_STATES]
    restricted = [item for item in items if item["state"] in RESTRICTED_STATES]
    pending = [item for item in items if item["state"] in PENDING_STATES]
    if not items:
        summary = "尚未检测数据能力；页面打开不会自动请求 Tushare、AkShare、yfinance 或 Supabase。"
        status = "missing"
    else:
        summary = f"数据源 {len(provider_cards)} 个｜可用 {len(available)}｜受限/失败 {len(restricted)}｜待验证/缓存 {len(pending)}"
        status = "partial" if restricted or pending else "ready"
    return {
        "status": status,
        "summary": summary,
        "source": _first_text(capability.get("source"), gap_report.get("source"), default="数据能力"),
        "checked_at": _first_text(capability.get("checked_at"), gap_report.get("updated_at")),
        "provider_cards": provider_cards,
        "items": items,
        "manual_actions": _manual_actions(items, gap_report),
        "available_count": len(available),
        "restricted_count": len(restricted),
        "pending_count": len(pending),
        "manual_note": "数据能力面板只读取本地检测结果；不会自动 ping 外部接口、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }
