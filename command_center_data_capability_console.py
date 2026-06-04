from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_data_capability_dashboard import build_data_capability_dashboard_view_model
from command_center_data_issue_explainer import build_data_issue_explainer_packet
from command_center_data_health_ledger import build_data_health_ledger


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


def _diagnostic_answer(item: Mapping[str, Any]) -> str:
    label = _to_text(item.get("label"), "数据能力")
    provider = _to_text(item.get("provider"), "数据源")
    api = _to_text(item.get("api"))
    state = _to_text(item.get("state"))
    api_text = f" {api}" if api else ""
    if provider.lower() == "tushare" and state == "permission_denied":
        return (
            f"{label}不是“没搜到行情”，而是 Tushare{api_text} 返回权限/积分不足；"
            "token 可用或积分较高也不等于该专业接口已开通。"
        )
    if provider.lower() == "tushare" and state == "disabled_this_session":
        return (
            f"{label}此前已被判定受限或失败，本会话跳过重复请求以避免卡顿；"
            "确认接口权限恢复后再点手动检测。"
        )
    if provider.lower() == "tushare" and state == "empty_recent":
        return (
            f"{label}接口可用但近窗口无记录，常见原因是非交易日、数据尚未发布、"
            "标的未上榜或该接口暂不覆盖。"
        )
    if state == "requires_manual_refresh":
        return f"{label}被标记为按钮触发型能力；页面打开不会自动请求 {provider} 重型接口。"
    if state == "not_configured":
        return f"{label}本地配置缺失或 token/secrets 不可用；这不是数据不存在。"
    if state == "stale_cache":
        return f"{label}正在使用缓存防白屏；执行前要核对最后更新时间和来源。"
    if state == "fallback_used":
        return f"{label}使用替代口径，只能辅助判断，不能等同于原始接口事实。"
    return _to_text(item.get("meaning") or item.get("decision_impact"), f"{label}仍需核对接口状态、日期和覆盖范围。")


def _provider_guardrail(item: Mapping[str, Any]) -> str:
    label = _to_text(item.get("label"), "数据能力")
    state = _to_text(item.get("state"))
    provider = _to_text(item.get("provider"), "数据源")
    if state in BLOCKED_STATES:
        return f"{provider} {label}恢复前不能支撑加仓、追高、加融资或自动交易。"
    if state in MANUAL_STATES:
        return f"{provider} {label}必须按钮触发，未刷新前只能作为待验证缺口。"
    if state in STALE_STATES:
        return f"{provider} {label}执行前要复核日期、来源和覆盖范围。"
    return f"{provider} {label}只作辅助证据，仍需价格、纪律和仓位共同确认。"


def _recovery_mode(state: str) -> str:
    if state == "permission_denied":
        return "check_permission"
    if state == "disabled_this_session":
        return "manual_retry_after_skip"
    if state == "not_configured":
        return "configure_provider"
    if state in {"network_failed", "failed"}:
        return "retry_after_fix"
    if state == "requires_manual_refresh":
        return "manual_refresh"
    if state == "empty_recent":
        return "verify_window"
    if state == "stale_cache":
        return "verify_cache"
    if state == "fallback_used":
        return "verify_fallback"
    return "manual_check"


def _recovery_mode_label(mode: str) -> str:
    return {
        "check_permission": "先查权限/积分",
        "manual_retry_after_skip": "确认恢复后手动重试",
        "configure_provider": "先补本地配置",
        "retry_after_fix": "修复后重试",
        "manual_refresh": "手动刷新",
        "verify_window": "核对交易日/覆盖范围",
        "verify_cache": "复核缓存日期",
        "verify_fallback": "复核替代口径",
        "manual_check": "手动检查",
    }.get(mode, "手动检查")


def _recovery_button_context(item: Mapping[str, Any], action_label: str, writes_packet: str) -> str:
    api = _to_text(item.get("api") or item.get("label"), "当前接口")
    return (
        f"{action_label}只处理 {api} 并回流 {writes_packet}；"
        "不会自动调用 DeepSeek、回测、全市场扫描或外部重型刷新。"
    )


def _recovery_steps(item: Mapping[str, Any], action_label: str, writes_packet: str, toolbox_entry: str) -> list[str]:
    label = _to_text(item.get("label"), "数据能力")
    state = _to_text(item.get("state"))
    if state == "permission_denied":
        first = f"先确认 {label} 对应接口权限/积分是否开通。"
    elif state == "disabled_this_session":
        first = f"先确认 {label} 权限或接口状态已恢复，避免重复卡顿。"
    elif state == "not_configured":
        first = f"先补齐 {label} 的本地 token/secrets 或连接配置。"
    elif state == "network_failed":
        first = f"先确认网络恢复，再重试 {label}。"
    elif state == "empty_recent":
        first = f"先核对 {label} 的交易日、发布时间、标的覆盖和窗口期。"
    elif state == "stale_cache":
        first = f"先核对 {label} 的缓存日期、来源和是否匹配当前标的。"
    elif state == "fallback_used":
        first = f"先确认 {label} 当前是替代口径，不等同于原始接口事实。"
    elif state == "requires_manual_refresh":
        first = f"确认需要最新 {label} 后再手动触发。"
    else:
        first = f"先复核 {label} 的状态、来源和适用范围。"
    return [
        first,
        f"进入 {toolbox_entry}，点击“{action_label}”。",
        f"结果回流 {writes_packet} 后，再进入综合中心决策链。",
    ]


def _provider_gap_headline(status: str, blocked_count: int, manual_count: int, stale_count: int) -> str:
    if status == "blocked":
        return f"多数据源有 {blocked_count} 个阻断项"
    if status == "partial":
        return f"多数据源有 {manual_count + stale_count} 个待手动或待复核项"
    if status == "ready":
        return "多数据源当前可辅助验证"
    return "多数据源能力待检测"


def build_provider_gap_explainer(
    recovery_actions: Any = None,
    ready_items: Any = None,
) -> dict:
    actions = [_as_mapping(item) for item in _as_list(recovery_actions) if _as_mapping(item)]
    ready = [_as_mapping(item) for item in _as_list(ready_items) if _as_mapping(item)]
    if not actions and not ready:
        return {
            "title": "多数据源为什么不可用",
            "status": "missing",
            "tone": "missing",
            "headline": "多数据源能力待检测",
            "summary": "暂无本地能力检测结果；页面打开不会自动请求 Tushare、AkShare、yfinance 或 Supabase。",
            "explanation": "先读取上次快照或手动检测关键接口，再把结果回流到综合中心 packet。",
            "items": [],
            "next_action": "在数据源体检或对应高级工具里手动检测。",
            "deepseek_called": False,
            "external_call_policy": "not_triggered",
        }
    blocked = [item for item in actions if _to_text(item.get("state")) in BLOCKED_STATES]
    manual = [item for item in actions if _to_text(item.get("state")) in MANUAL_STATES]
    stale = [item for item in actions if _to_text(item.get("state")) in STALE_STATES]
    if blocked:
        status = "blocked"
    elif manual or stale:
        status = "partial"
    elif ready:
        status = "ready"
    else:
        status = "missing"
    rows = []
    for action in actions + ready:
        state = _to_text(action.get("state"), "available" if action in ready else "unknown")
        mode = _to_text(action.get("recovery_mode"), _recovery_mode(state))
        action_label = _to_text(action.get("action_label"), "手动检查")
        writes_packet = _to_text(action.get("writes_packet"), "command_center_data_capability_packet")
        toolbox_entry = _to_text(action.get("toolbox_entry"), "高级工具箱 / 数据源体检")
        rows.append(
            {
                "provider": _to_text(action.get("provider"), "数据源"),
                "label": _to_text(action.get("label"), "数据能力"),
                "api": _to_text(action.get("api")),
                "state": state,
                "status_label": _to_text(action.get("status_label") or action.get("status"), state),
                "tone": _to_text(action.get("tone"), _tone(status)),
                "why_unavailable": _to_text(action.get("diagnostic_answer") or action.get("reason"), _diagnostic_answer(action)),
                "decision_guardrail": _provider_guardrail(action),
                "action_label": action_label,
                "toolbox_entry": toolbox_entry,
                "writes_packet": writes_packet,
                "refresh_policy": _to_text(action.get("refresh_policy"), "button_gated"),
                "recovery_mode": mode,
                "recovery_mode_label": _to_text(action.get("recovery_mode_label"), _recovery_mode_label(mode)),
                "recovery_steps": _as_list(action.get("recovery_steps")) or _recovery_steps(action, action_label, writes_packet, toolbox_entry),
                "recovery_button_context": _to_text(
                    action.get("recovery_button_context"),
                    _recovery_button_context(action, action_label, writes_packet),
                ),
                "deepseek_called": False,
                "external_call_policy": "not_triggered",
            }
        )
    summary = f"阻断 {len(blocked)}｜手动 {len(manual)}｜缓存/待验证 {len(stale)}｜可用 {len(ready)}"
    return {
        "title": "多数据源为什么不可用",
        "status": status,
        "tone": _tone(status),
        "headline": _provider_gap_headline(status, len(blocked), len(manual), len(stale)),
        "summary": summary,
        "explanation": "不同数据源失败原因不同：Tushare 可能是权限/近期无数据，AkShare/yfinance 多为手动刷新，Supabase 多为本地配置。",
        "items": rows[:MAX_QUEUE_ITEMS],
        "next_action": (
            "先处理阻断项，再按按钮手动刷新 AkShare/yfinance；Supabase 只检查本地配置。"
            if actions
            else "继续复核可用数据的日期、来源和适用标的。"
        ),
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


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
        mode = _recovery_mode(item["state"])
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
                "diagnostic_answer": _diagnostic_answer(item),
                "action_label": action_label,
                "action_hint": item["next_action"],
                "toolbox_entry": toolbox_entry,
                "writes_packet": writes_packet,
                "refresh_policy": "button_gated" if item["state"] != "not_configured" else "manual_config",
                "recovery_mode": mode,
                "recovery_mode_label": _recovery_mode_label(mode),
                "recovery_steps": _recovery_steps(item, action_label, writes_packet, toolbox_entry),
                "recovery_button_context": _recovery_button_context(item, action_label, writes_packet),
                "decision_guardrail": _provider_guardrail(item),
                "external_call_policy": "not_triggered",
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
    provider_gap_explainer = build_provider_gap_explainer(recovery_actions, ready_items=ready_items)
    data_health_ledger = build_data_health_ledger(
        data_capability_packet=data_capability_packet,
        data_gap_report=data_gap_report,
        data_issue_explainer=issue_packet,
        recovery_actions=recovery_actions,
    )
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
        "provider_gap_explainer": provider_gap_explainer,
        "recovery_summary": (
            f"优先处理 {recovery_actions[0]['label']}：{recovery_actions[0]['action_label']}。"
            if recovery_actions
            else "暂无需要手动恢复的数据源动作。"
        ),
        "data_health_ledger": data_health_ledger,
        "provider_diagnostic_cards": _as_list(issue_packet.get("provider_diagnostic_cards"))[:MAX_QUEUE_ITEMS],
        "next_actions": _as_list(issue_packet.get("next_actions"))[:MAX_QUEUE_ITEMS],
        "available_count": len(ready_items),
        "blocked_count": len(blocked_items),
        "manual_count": len(manual_items),
        "stale_count": len(stale_items),
        "source": "local data capability console",
        "manual_note": "本控制台只读取本地检测 packet；不会自动调用 Tushare、AkShare、yfinance、Supabase、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }
