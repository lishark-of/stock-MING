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


MAX_LEDGER_ROWS = 12
AVAILABLE_STATES = {"available", "ready", "ok", "success"}
BLOCKED_STATES = {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}
MANUAL_STATES = {"requires_manual_refresh"}
STALE_STATES = {"empty_recent", "stale_cache", "fallback_used", "unknown", "missing"}

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

API_RECOVERY_MAP = {
    "moneyflow": ("手动刷新个股资金流", "command_center_moneyflow_packet", "高级工具箱 / A股专业实盘 / 个股资金流"),
    "margin_detail": ("手动刷新融资融券", "command_center_margin_packet", "高级工具箱 / 融资 ETF / 融资融券"),
    "top_list": ("手动刷新龙虎榜", "command_center_dragon_tiger_packet", "高级工具箱 / 下一票雷达 / 龙虎榜"),
    "top_inst": ("手动刷新龙虎榜", "command_center_dragon_tiger_packet", "高级工具箱 / 下一票雷达 / 龙虎榜"),
    "limit_cpt_list": ("手动刷新涨跌停/情绪", "command_center_limit_emotion_packet", "高级工具箱 / 数据源体检 / 涨跌停情绪"),
    "cyq_perf": ("手动刷新筹码/胜率", "command_center_chip_packet", "高级工具箱 / 量化推演 / 筹码胜率"),
    "cyq_chips": ("手动刷新筹码/胜率", "command_center_chip_packet", "高级工具箱 / 量化推演 / 筹码胜率"),
    "anns_d": ("检测公告/硬风险", "command_center_hard_risk_packet", "高级工具箱 / 天眼风控 / A股公告风险"),
    "forecast": ("检测公告/硬风险", "command_center_hard_risk_packet", "高级工具箱 / 天眼风控 / A股公告风险"),
    "stk_holdertrade": ("检测公告/硬风险", "command_center_hard_risk_packet", "高级工具箱 / 天眼风控 / A股公告风险"),
    "share_float": ("检测公告/硬风险", "command_center_hard_risk_packet", "高级工具箱 / 天眼风控 / A股公告风险"),
    "pledge_stat": ("检测公告/硬风险", "command_center_hard_risk_packet", "高级工具箱 / 天眼风控 / A股公告风险"),
    "pledge_detail": ("检测公告/硬风险", "command_center_hard_risk_packet", "高级工具箱 / 天眼风控 / A股公告风险"),
    "akshare_manual_refresh": ("点击对应模块手动刷新 AkShare", "command_center_data_capability_packet", "高级工具箱 / 数据源体检"),
    "yfinance_market_data": ("点击对应模块手动刷新 yfinance", "command_center_data_capability_packet", "高级工具箱 / 数据源体检"),
    "brain_memory": ("检查 Supabase 本地配置", "command_center_data_capability_packet", "高级工具箱 / 云端外脑"),
}


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


def _api_recovery_config(api: str, provider: str, label: str) -> tuple[str, str, str]:
    api_text = to_text(api)
    for api_key, config in API_RECOVERY_MAP.items():
        if api_key and api_key in api_text:
            return config
    provider_text = provider.lower()
    if provider_text == "supabase":
        return ("检查 Supabase 本地配置", "command_center_data_capability_packet", "高级工具箱 / 云端外脑")
    if provider_text in {"akshare", "yfinance"}:
        return (f"手动刷新{label}", "command_center_data_capability_packet", "高级工具箱 / 数据源体检")
    return (f"手动检查{label}", "command_center_data_capability_packet", "高级工具箱 / 数据源体检")


def _row_category(state: str) -> str:
    if state in AVAILABLE_STATES:
        return "available"
    if state in BLOCKED_STATES:
        return "blocked"
    if state in MANUAL_STATES:
        return "manual"
    return "stale"


def _row_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        to_text(row.get("provider")),
        to_text(row.get("api")),
        to_text(row.get("label")),
    )


def normalize_health_ledger_row(raw: Any = None, checked_at: Any = "") -> dict:
    payload = as_mapping(raw)
    label = _first_text(payload.get("label"), payload.get("section"), payload.get("api"), payload.get("table"), default="数据能力")
    provider = _provider_name(payload)
    api = _first_text(payload.get("api"), payload.get("table"))
    state = normalize_capability_state_value(payload.get("state") or payload.get("capability_state") or payload.get("status"))
    status_label = _first_text(payload.get("status_label"), payload.get("status"), payload.get("capability_label"), default=STATE_LABELS.get(state, "待验证"))
    latest_date = _first_text(payload.get("latest_date"), payload.get("date"), payload.get("trade_date"))
    last_checked = _first_text(payload.get("checked_at"), payload.get("updated_at"), checked_at)
    action_label, writes_packet, toolbox_entry = _api_recovery_config(api, provider, label)
    meaning = _first_text(payload.get("meaning"), payload.get("reason"), payload.get("message"), default=meaning_for_capability_state(state, provider, label))
    decision_impact = _first_text(payload.get("decision_impact"), default=decision_impact_for_capability_state(state, label))
    next_action = _first_text(payload.get("next_action"), payload.get("action_hint"), default=next_action_for_capability_state(state, label))
    return {
        "key": _first_text(payload.get("key"), payload.get("section"), payload.get("api"), payload.get("table"), default="data_capability"),
        "provider": provider,
        "api": api,
        "label": label,
        "state": state,
        "status_label": status_label,
        "tone": tone_for_capability_state(state),
        "category": _row_category(state),
        "latest_date": latest_date,
        "last_checked": last_checked,
        "last_success_text": latest_date or ("暂无" if state not in AVAILABLE_STATES else "已返回可用结果"),
        "error_text": _first_text(payload.get("error"), payload.get("last_error"), payload.get("reason")),
        "meaning": meaning,
        "decision_impact": decision_impact,
        "next_action": next_action,
        "action_label": action_label,
        "toolbox_entry": toolbox_entry,
        "writes_packet": writes_packet,
        "refresh_policy": "button_gated" if state != "not_configured" else "manual_config",
        "deepseek_called": False,
    }


def _items_from_packet(packet: Any = None) -> tuple[list[dict], str]:
    payload = as_mapping(packet)
    checked_at = _first_text(payload.get("checked_at"), payload.get("updated_at"))
    rows = [
        normalize_health_ledger_row(item, checked_at=checked_at)
        for item in as_list(payload.get("items"))
        if as_mapping(item)
    ]
    return rows, checked_at


def _items_from_issue_packet(packet: Any = None) -> list[dict]:
    payload = as_mapping(packet)
    return [normalize_health_ledger_row(item) for item in as_list(payload.get("items")) if as_mapping(item)]


def _merge_recovery_action(row: dict, actions: list[dict]) -> dict:
    for raw in actions:
        action = as_mapping(raw)
        if not action:
            continue
        same_api = row.get("api") and row.get("api") == to_text(action.get("api"))
        same_label = row.get("label") and row.get("provider") == _provider_name(action) and row.get("label") == to_text(action.get("label"))
        same_packet = (
            row.get("writes_packet")
            and row.get("writes_packet") == to_text(action.get("writes_packet"))
            and (same_api or same_label)
        )
        if not any([same_api, same_label, same_packet]):
            continue
        return {
            **row,
            "action_label": _first_text(action.get("action_label"), default=row["action_label"]),
            "toolbox_entry": _first_text(action.get("toolbox_entry"), default=row["toolbox_entry"]),
            "writes_packet": _first_text(action.get("writes_packet"), default=row["writes_packet"]),
            "refresh_policy": _first_text(action.get("refresh_policy"), default=row["refresh_policy"]),
            "next_action": _first_text(action.get("action_hint"), action.get("next_action"), default=row["next_action"]),
            "meaning": _first_text(action.get("diagnostic_answer"), action.get("reason"), default=row["meaning"]),
        }
    return row


def _provider_groups(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["provider"], []).append(row)
    result = []
    for provider in sorted(grouped):
        provider_rows = grouped[provider]
        available = [row for row in provider_rows if row["category"] == "available"]
        blocked = [row for row in provider_rows if row["category"] == "blocked"]
        manual = [row for row in provider_rows if row["category"] == "manual"]
        stale = [row for row in provider_rows if row["category"] == "stale"]
        tone = "failed" if blocked else "stale" if manual or stale else "ready" if available else "missing"
        result.append(
            {
                "provider": provider,
                "tone": tone,
                "summary": f"可用 {len(available)}｜阻断 {len(blocked)}｜手动 {len(manual)}｜缓存/待验证 {len(stale)}",
                "available_count": len(available),
                "blocked_count": len(blocked),
                "manual_count": len(manual),
                "stale_count": len(stale),
                "rows": provider_rows[:4],
            }
        )
    return result


def _ledger_status(rows: list[dict]) -> str:
    if not rows:
        return "missing"
    if any(row["category"] == "blocked" for row in rows):
        return "blocked"
    if any(row["category"] in {"manual", "stale"} for row in rows):
        return "partial"
    return "ready"


def build_data_health_ledger(
    data_capability_packet: Any = None,
    data_gap_report: Any = None,
    data_issue_explainer: Any = None,
    recovery_actions: Any = None,
    limit: int = MAX_LEDGER_ROWS,
) -> dict:
    capability_rows, capability_checked_at = _items_from_packet(data_capability_packet)
    gap_rows, gap_checked_at = _items_from_packet(data_gap_report)
    issue_rows = _items_from_issue_packet(data_issue_explainer)
    action_rows = [normalize_health_ledger_row(action) for action in as_list(recovery_actions) if as_mapping(action)]
    actions = [as_mapping(action) for action in as_list(recovery_actions) if as_mapping(action)]
    rows = []
    seen = set()
    for row in capability_rows + gap_rows + issue_rows + action_rows:
        if not row.get("label"):
            continue
        key = _row_key(row)
        if key in seen:
            continue
        seen.add(key)
        rows.append(_merge_recovery_action(row, actions))
        if len(rows) >= max(1, int(limit or MAX_LEDGER_ROWS)):
            break
    status = _ledger_status(rows)
    available = [row for row in rows if row["category"] == "available"]
    blocked = [row for row in rows if row["category"] == "blocked"]
    manual = [row for row in rows if row["category"] == "manual"]
    stale = [row for row in rows if row["category"] == "stale"]
    summary = (
        f"接口 {len(rows)} 个｜可用 {len(available)}｜阻断 {len(blocked)}｜手动 {len(manual)}｜缓存/待验证 {len(stale)}"
        if rows
        else "暂无接口级健康账本；页面打开不会自动请求外部接口。"
    )
    return {
        "status": status,
        "tone": "failed" if status == "blocked" else "stale" if status == "partial" else "ready" if status == "ready" else "missing",
        "summary": summary,
        "checked_at": _first_text(capability_checked_at, gap_checked_at),
        "rows": rows,
        "provider_groups": _provider_groups(rows),
        "available_count": len(available),
        "blocked_count": len(blocked),
        "manual_count": len(manual),
        "stale_count": len(stale),
        "manual_note": "接口级健康账本只整理本地检测结果；不会自动调用 Tushare、AkShare、yfinance、Supabase、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }
