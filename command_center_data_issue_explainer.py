from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from market_data_capability import (
    decision_impact_for_capability_state,
    meaning_for_capability_state,
    next_action_for_capability_state,
    normalize_capability_state_value,
    tone_for_capability_state,
)


MAX_ITEMS = 8
MAX_ACTIONS = 6

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


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = _to_text(value)
        if text:
            return text
    return default


def _dedupe(values: Any, limit: int = MAX_ACTIONS) -> list[str]:
    result = []
    seen = set()
    for value in _as_list(values):
        text = _to_text(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
        if len(result) >= limit:
            break
    return result


def normalize_data_issue_state(value: Any) -> str:
    return normalize_capability_state_value(value)


def _tone(state: str) -> str:
    return tone_for_capability_state(state)


def _meaning_for_state(state: str, provider: str, label: str) -> str:
    return meaning_for_capability_state(state, provider, label)


def _decision_impact_for_state(state: str, label: str) -> str:
    return decision_impact_for_capability_state(state, label)


def _next_action_for_state(state: str, label: str) -> str:
    return next_action_for_capability_state(state, label)


def explain_data_issue_item(raw: Any, provider_default: str = "数据源") -> dict:
    payload = _as_mapping(raw)
    label = _first_text(payload.get("label"), payload.get("section"), payload.get("api"), payload.get("table"), default="数据能力")
    provider = _first_text(payload.get("provider"), payload.get("source"), default=provider_default)
    state = normalize_data_issue_state(payload.get("state") or payload.get("capability_state") or payload.get("status"))
    api = _to_text(payload.get("api") or payload.get("table"))
    return {
        "key": _first_text(payload.get("key"), payload.get("section"), payload.get("api"), payload.get("table"), default="data_issue"),
        "label": label,
        "provider": provider,
        "api": api,
        "state": state,
        "status_label": _first_text(payload.get("status"), payload.get("capability_label"), default=STATE_LABELS.get(state, "待验证")),
        "tone": _tone(state),
        "latest_date": _first_text(payload.get("latest_date"), payload.get("updated_at")),
        "reason": _first_text(payload.get("error"), payload.get("reason"), payload.get("message"), payload.get("action_hint")),
        "meaning": _meaning_for_state(state, provider, label),
        "decision_impact": _decision_impact_for_state(state, label),
        "next_action": _first_text(payload.get("action_hint"), default=_next_action_for_state(state, label)),
    }


def _items_from_packet(packet: Any, provider_default: str = "数据源") -> list[dict]:
    payload = _as_mapping(packet)
    return [
        explain_data_issue_item(item, provider_default=provider_default or _to_text(payload.get("source"), "数据源"))
        for item in _as_list(payload.get("items"))
        if _as_mapping(item)
    ]


def _items_from_refresh_errors(refresh_summary: Any = None, errors: Any = None) -> list[dict]:
    rows = []
    refresh = _as_mapping(refresh_summary)
    for key in ("error_items", "errors"):
        raw = refresh.get(key) or []
        if isinstance(raw, (str, Mapping)):
            raw = [raw]
        rows.extend(_as_list(raw))
    raw_errors = errors
    if isinstance(raw_errors, (str, Mapping)):
        raw_errors = [raw_errors]
    rows.extend(_as_list(raw_errors))

    result = []
    for row in rows:
        payload = _as_mapping(row)
        if payload:
            label = _first_text(payload.get("module"), payload.get("label"), default="刷新错误")
            result.append(
                explain_data_issue_item(
                    {
                        "label": label,
                        "provider": _first_text(payload.get("provider"), payload.get("source"), default="刷新结果"),
                        "api": payload.get("api"),
                        "state": "failed",
                        "status": "失败",
                        "error": _first_text(payload.get("message"), payload.get("error"), payload.get("last_error")),
                        "updated_at": _first_text(payload.get("updated_at"), payload.get("finished_at")),
                    }
                )
            )
        else:
            text = _to_text(row)
            if text:
                result.append(
                    explain_data_issue_item(
                        {
                            "label": "刷新错误",
                            "provider": "刷新结果",
                            "state": "failed",
                            "status": "失败",
                            "error": text,
                        }
                    )
                )
    return result


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


def _headline(available: int, restricted: int, pending: int) -> str:
    if not any([available, restricted, pending]):
        return "尚未检测数据能力"
    if restricted:
        return "部分数据接口受限，不能把缺失写成利好"
    if pending:
        return "部分数据待验证或使用缓存"
    return "数据能力已读取，可继续核对日期和口径"


def _short_answer(items: list[dict]) -> str:
    if not items:
        return "还没有本地检测结果；页面打开不会自动 ping Tushare、AkShare、yfinance 或 Supabase。"
    states = {item["state"] for item in items}
    if "permission_denied" in states or "disabled_this_session" in states:
        return "Tushare 配置成功只代表 token 可用；单个接口仍可能需要额外权限/积分，失败后本会话会跳过重复请求以避免卡顿。"
    if "empty_recent" in states:
        return "接口可用也可能搜不到：近期无数据通常来自非交易日、尚未发布、标的未上榜或接口不覆盖。"
    if "stale_cache" in states or "fallback_used" in states:
        return "当前主要展示缓存或替代口径；它能防白屏，但不能当作实时已验证事实。"
    if "requires_manual_refresh" in states:
        return "这类数据必须按钮触发；页面打开不会自动请求重型接口。"
    return "当前数据能力有可用结果；执行前仍需核对日期、来源和适用市场。"


def _root_cause_items(items: list[dict]) -> list[dict]:
    states = {item["state"] for item in items}
    result = []
    if not items:
        return [
            {
                "key": "not_checked",
                "label": "尚未检测",
                "tone": "missing",
                "detail": "还没有本地数据能力检测结果；页面打开不会自动请求外部接口。",
                "next_action": "先点击对应刷新或检测按钮，再查看接口状态。",
            }
        ]
    if "permission_denied" in states:
        result.append(
            {
                "key": "endpoint_permission",
                "label": "接口权限/积分",
                "tone": "failed",
                "detail": "Tushare token 可用不等于每个专业接口都有权限；融资融券、筹码、涨跌停情绪等可能需要额外权限或积分。",
                "next_action": "检查具体接口权限，不要把权限不足写成行情不存在。",
            }
        )
    if "disabled_this_session" in states:
        result.append(
            {
                "key": "session_skip",
                "label": "本会话跳过",
                "tone": "failed",
                "detail": "某接口已经被判定受限或失败，本会话会跳过重复请求，避免页面反复卡顿。",
                "next_action": "确认权限恢复后，手动点击对应检测按钮重试。",
            }
        )
    if "empty_recent" in states:
        result.append(
            {
                "key": "empty_recent",
                "label": "近期无记录",
                "tone": "missing",
                "detail": "接口可用也可能搜不到：常见原因是非交易日、数据尚未发布、标的未上榜或该接口暂不覆盖。",
                "next_action": "核对交易日、发布时间和标的覆盖范围，不能把无记录写成利好。",
            }
        )
    if "stale_cache" in states or "fallback_used" in states:
        result.append(
            {
                "key": "cache_or_fallback",
                "label": "缓存/替代口径",
                "tone": "stale",
                "detail": "缓存能防白屏，但不是实时事实；替代口径也不能等同于原始接口数据。",
                "next_action": "执行前复核日期、来源和口径，必要时手动刷新。",
            }
        )
    if "requires_manual_refresh" in states:
        result.append(
            {
                "key": "manual_required",
                "label": "必须手动触发",
                "tone": "missing",
                "detail": "重型接口、批量扫描和外部刷新不会在页面打开时自动执行。",
                "next_action": "只在需要时点击对应按钮，并等待结果回流到综合中心。",
            }
        )
    if not result:
        result.append(
            {
                "key": "verify_scope",
                "label": "口径复核",
                "tone": "ready",
                "detail": "当前已有可用数据，但仍要确认日期、市场类型、标的范围和接口口径。",
                "next_action": "把可用接口当作辅助证据，不要单独作为交易动作依据。",
            }
        )
    return result[:MAX_ACTIONS]


def build_data_issue_explainer_packet(
    data_capability_packet: Any = None,
    data_gap_report: Any = None,
    refresh_summary: Any = None,
    errors: Any = None,
) -> dict:
    capability = _as_mapping(data_capability_packet)
    gap_report = _as_mapping(data_gap_report)
    items = _merge_items(
        _items_from_packet(capability, provider_default=_to_text(capability.get("source"), "数据能力")),
        _items_from_packet(gap_report, provider_default=_to_text(gap_report.get("source"), "数据缺口")),
        _items_from_refresh_errors(refresh_summary=refresh_summary, errors=errors),
    )
    available = [item for item in items if item["state"] in AVAILABLE_STATES]
    restricted = [item for item in items if item["state"] in RESTRICTED_STATES]
    pending = [item for item in items if item["state"] in PENDING_STATES]
    actions = _dedupe([item["next_action"] for item in restricted + pending], limit=MAX_ACTIONS)
    return {
        "status": "ready" if items else "missing",
        "headline": _headline(len(available), len(restricted), len(pending)),
        "short_answer": _short_answer(items),
        "available_count": len(available),
        "restricted_count": len(restricted),
        "pending_count": len(pending),
        "items": items,
        "root_cause_items": _root_cause_items(items),
        "next_actions": actions,
        "source": "local data capability packet / gap report",
        "deepseek_called": False,
    }
