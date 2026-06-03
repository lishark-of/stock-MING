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


def _decision_readiness(status: str) -> tuple[str, str, str]:
    if status == "blocked":
        return (
            "blocked",
            "阻断加仓",
            "只允许观察、降风险或等待验证；不能用缺失/受限数据支持加仓、追高或加融资。",
        )
    if status == "partial":
        return (
            "caution",
            "谨慎验证",
            "允许继续看盘，但执行前必须补齐手动刷新、缓存日期和待验证接口。",
        )
    if status == "ready":
        return (
            "ready",
            "可进入证据链",
            "数据能力可作为辅助证据；执行前仍需价格、纪律和仓位三重确认。",
        )
    return (
        "missing",
        "待检测",
        "尚未检测数据能力；只能展示安全空态或上次成功结果。",
    )


def _decision_blockers(blocked_items: list[dict], manual_items: list[dict], stale_items: list[dict]) -> list[str]:
    items = []
    for item in blocked_items:
        items.append(f"{item.get('label') or '数据能力'}：{item.get('decision_impact') or '不可作为交易依据。'}")
    for item in manual_items:
        items.append(f"{item.get('label') or '手动刷新'}：需要手动刷新后才能进入当日判断。")
    for item in stale_items:
        if item.get("state") in {"empty_recent", "stale_cache", "fallback_used"}:
            items.append(f"{item.get('label') or '缓存/待验证'}：{item.get('decision_impact') or '需要复核。'}")
    return _dedupe_text(items, limit=MAX_QUEUE_ITEMS)


def _dedupe_text(values: list[str], limit: int = MAX_QUEUE_ITEMS) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = _to_text(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
        if len(result) >= limit:
            break
    return result


def _api_recovery_config(item: Mapping[str, Any]) -> tuple[str, str, str]:
    api_text = _to_text(item.get("api"))
    for api_key, config in API_RECOVERY_MAP.items():
        if api_key and api_key in api_text:
            return config
    provider = _to_text(item.get("provider"), "数据源")
    label = _to_text(item.get("label"), "数据能力")
    if provider.lower() == "supabase":
        return ("检查 Supabase 本地配置", "command_center_data_capability_packet", "高级工具箱 / 云端外脑")
    if provider.lower() == "akshare":
        return (f"手动刷新{label}", "command_center_data_capability_packet", "高级工具箱 / 数据源体检")
    if provider.lower() == "yfinance":
        return (f"手动刷新{label}", "command_center_data_capability_packet", "高级工具箱 / 数据源体检")
    return (f"手动检查{label}", "command_center_data_capability_packet", "高级工具箱 / 数据源体检")


def _recovery_reason(item: Mapping[str, Any]) -> str:
    label = _to_text(item.get("label"), "数据能力")
    state = _to_text(item.get("state"))
    if state == "permission_denied":
        return f"{label}权限或积分不足；接口接入成功不等于当前账户有权限。"
    if state == "disabled_this_session":
        return f"{label}本会话已跳过重复请求；确认权限恢复后再手动检测。"
    if state == "not_configured":
        return f"{label}本地配置缺失；先检查 token、secrets 或连接设置。"
    if state == "network_failed":
        return f"{label}网络失败；保留缓存并等待网络恢复后手动重试。"
    if state == "requires_manual_refresh":
        return f"{label}需要按钮触发；页面打开不会自动刷新该接口。"
    if state == "empty_recent":
        return f"{label}近期无数据；可能是非交易日、标的不覆盖或数据尚未发布。"
    if state == "stale_cache":
        return f"{label}正在使用缓存；执行前需要复核日期和来源。"
    if state == "fallback_used":
        return f"{label}使用替代口径；不能等同于原始接口事实。"
    return _to_text(item.get("meaning") or item.get("next_action"), f"{label}仍待验证。")


def _recovery_priority(item: Mapping[str, Any]) -> int:
    state = _to_text(item.get("state"))
    if state in BLOCKED_STATES:
        return 1
    if state in MANUAL_STATES:
        return 2
    return 3


def build_data_capability_recovery_actions(
    blocked_items: Any = None,
    manual_items: Any = None,
    stale_items: Any = None,
    limit: int = MAX_QUEUE_ITEMS,
) -> list[dict]:
    candidates = []
    for raw in _as_list(blocked_items) + _as_list(manual_items) + _as_list(stale_items):
        item = _queue_item(_as_mapping(raw))
        if not item.get("label"):
            continue
        action_label, writes_packet, toolbox_entry = _api_recovery_config(item)
        candidates.append(
            {
                "provider": item["provider"],
                "label": item["label"],
                "api": item["api"],
                "state": item["state"],
                "status_label": item["status_label"],
                "tone": item["tone"],
                "priority": _recovery_priority(item),
                "reason": _recovery_reason(item),
                "action_label": action_label,
                "action_hint": item["next_action"],
                "toolbox_entry": toolbox_entry,
                "writes_packet": writes_packet,
                "refresh_policy": "button_gated" if item["state"] != "not_configured" else "manual_config",
                "deepseek_called": False,
            }
        )
    sorted_items = sorted(candidates, key=lambda item: (item["priority"], item["provider"], item["label"], item["api"]))
    return _dedupe_recovery_actions(sorted_items, limit=limit)


def _dedupe_recovery_actions(items: list[dict], limit: int = MAX_QUEUE_ITEMS) -> list[dict]:
    result = []
    seen = set()
    for item in items:
        key = (item.get("provider"), item.get("api"), item.get("label"), item.get("state"), item.get("writes_packet"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= max(1, int(limit or MAX_QUEUE_ITEMS)):
            break
    return result


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
    readiness, readiness_label, safe_mode_text = _decision_readiness(status)
    decision_blockers = _decision_blockers(blocked_items, manual_items, stale_items)
    recovery_actions = build_data_capability_recovery_actions(blocked_items, manual_items, stale_items)
    return {
        "status": status,
        "tone": _tone(status),
        "headline": _headline(status, len(ready_items), len(blocked_items), pending_count),
        "decision_readiness": readiness,
        "decision_readiness_label": readiness_label,
        "safe_mode_text": safe_mode_text,
        "decision_blockers": decision_blockers,
        "short_answer": _to_text(issue_packet.get("short_answer"), "尚未检测数据能力；不会自动 ping 外部接口。"),
        "provider_cards": _as_list(dashboard.get("provider_cards")),
        "ready_items": ready_items,
        "blocked_items": blocked_items,
        "manual_items": manual_items,
        "stale_items": stale_items,
        "recovery_actions": recovery_actions,
        "recovery_summary": (
            f"优先处理 {recovery_actions[0]['label']}：{recovery_actions[0]['action_label']}。"
            if recovery_actions
            else "暂无需要手动恢复的数据源动作。"
        ),
        "next_actions": _as_list(issue_packet.get("next_actions"))[:MAX_QUEUE_ITEMS],
        "available_count": len(ready_items),
        "blocked_count": len(blocked_items),
        "manual_count": len(manual_items),
        "stale_count": len(stale_items),
        "source": "local data capability console",
        "manual_note": "本控制台只读取本地检测 packet；不会自动调用 Tushare、AkShare、yfinance、Supabase、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }
