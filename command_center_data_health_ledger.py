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
    "stk_limit": ("手动刷新涨跌停/情绪", "command_center_limit_emotion_packet", "高级工具箱 / 数据源体检 / 涨跌停情绪"),
    "limit_list_d": ("手动刷新涨跌停/情绪", "command_center_limit_emotion_packet", "高级工具箱 / 数据源体检 / 涨跌停情绪"),
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


def _legacy_tab_from_recovery_target(writes_packet: Any = "", toolbox_entry: Any = "") -> str:
    packet = to_text(writes_packet)
    if packet in {"command_center_moneyflow_packet"}:
        return "今日关注池"
    if packet in {"command_center_margin_packet", "command_center_etf_packet"}:
        return "融资 ETF"
    if packet in {"command_center_dragon_tiger_packet", "command_center_radar_packet"}:
        return "下一票雷达"
    if packet in {"command_center_limit_emotion_packet", "command_center_data_capability_packet"}:
        return "数据源体检"
    if packet in {"command_center_chip_packet", "command_center_quant_packet"}:
        return "量化推演"
    if packet in {"command_center_hard_risk_packet"}:
        return "天眼风控"
    entry = to_text(toolbox_entry)
    for tab in ("今日关注池", "融资 ETF", "下一票雷达", "数据源体检", "量化推演", "天眼风控", "云端外脑"):
        if tab in entry:
            return tab
    return "数据源体检"


def _interface_diagnostic_answer(state: str, provider: str, label: str, api: str) -> str:
    api_text = f" {api}" if api else ""
    if provider.lower() == "tushare" and state == "permission_denied":
        return (
            f"{label}不是“没搜到行情”，而是 Tushare{api_text} 权限/积分不足；"
            "token 可用、之前拉满或其他接口正常，都不等于这个专业接口已开通。"
        )
    if provider.lower() == "tushare" and state == "disabled_this_session":
        return (
            f"{label}此前已被判定受限或失败，本会话跳过重复请求以防页面卡顿；"
            "确认权限恢复后再点对应手动检测。"
        )
    if provider.lower() == "tushare" and state == "empty_recent":
        return (
            f"{label}接口可读但近窗口无记录；常见原因是非交易日、数据尚未发布、"
            "标的未上榜、窗口期过短或接口暂不覆盖。"
        )
    if state in {"stale_cache", "fallback_used"}:
        return f"{label}当前来自缓存或替代口径，能防白屏，但不是实时已验证事实。"
    if state == "requires_manual_refresh":
        return f"{label}属于按钮触发型能力；页面打开不会自动请求 {provider} 重型接口。"
    if state in AVAILABLE_STATES:
        return f"{label}已有可用返回，可进入证据链；执行前仍需核对交易日、来源和当前标的。"
    if state == "not_configured":
        return f"{label}本地配置缺失；先检查 token、secrets 或连接设置。"
    if state == "network_failed":
        return f"{label}网络请求失败；保留缓存或安全空态，网络恢复后手动重试。"
    return f"{label}仍待验证；不要把缺失或未知状态写成利好、无风险或可加仓依据。"


def _recovery_button_context(api: str, label: str) -> str:
    api_text = api or label or "当前接口"
    return f"只检测 {api_text} 并回流对应 packet；不触发 DeepSeek、回测、全市场扫描或自动交易。"


def _decision_guardrail_for_row(state: str, label: str) -> str:
    if state in BLOCKED_STATES:
        return f"{label}受限前，不能用缺失数据支持加仓、追高或加融资。"
    if state in {"empty_recent", "stale_cache", "fallback_used"}:
        return f"{label}未实时验证前，只能作为待验证/缓存证据，不能写成无风险。"
    if state == "requires_manual_refresh":
        return f"{label}未手动刷新前，不进入当日交易动作依据。"
    return f"{label}需要和价格、纪律、仓位、风险预算一起验证。"


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
    diagnostic_answer = _first_text(
        payload.get("diagnostic_answer"),
        default=_interface_diagnostic_answer(state, provider, label, api),
    )
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
        "diagnostic_answer": diagnostic_answer,
        "decision_impact": decision_impact,
        "decision_guardrail": _first_text(payload.get("decision_guardrail"), default=_decision_guardrail_for_row(state, label)),
        "next_action": next_action,
        "action_label": action_label,
        "toolbox_entry": toolbox_entry,
        "writes_packet": writes_packet,
        "refresh_policy": "button_gated" if state != "not_configured" else "manual_config",
        "recovery_button_context": _first_text(
            payload.get("recovery_button_context"),
            payload.get("button_context"),
            default=_recovery_button_context(api, label),
        ),
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
            "diagnostic_answer": _first_text(action.get("diagnostic_answer"), default=row.get("diagnostic_answer")),
            "decision_guardrail": _first_text(action.get("decision_guardrail"), default=row.get("decision_guardrail")),
            "recovery_button_context": _first_text(action.get("recovery_button_context"), action.get("button_context"), default=row.get("recovery_button_context")),
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


def _limited_labels(rows: list[dict], fallback: str = "无", limit: int = 3) -> str:
    labels = []
    seen = set()
    for row in rows:
        label = to_text(row.get("label") or row.get("api"))
        if label and label not in seen:
            labels.append(label)
            seen.add(label)
        if len(labels) >= limit:
            break
    if not labels:
        return fallback
    suffix = f" 等 {len(rows)} 项" if len(rows) > limit else ""
    return "、".join(labels) + suffix


def _market_scoped_rows(rows: list[dict], market_type: Any = None) -> list[dict]:
    market = to_text(market_type)
    if market in {"美股", "US", "US_STOCK"}:
        return [row for row in rows if to_text(row.get("provider")).lower() in {"yfinance", "supabase"}]
    if market in {"A股", "A_SHARE"}:
        return [row for row in rows if to_text(row.get("provider")).lower() in {"tushare", "akshare", "supabase"}]
    return rows


def build_data_health_impact_summary(data_health_ledger: Any = None, market_type: Any = None) -> dict:
    ledger = as_mapping(data_health_ledger)
    rows = [as_mapping(row) for row in as_list(ledger.get("rows")) if as_mapping(row)]
    rows = _market_scoped_rows(rows, market_type=market_type)
    blocked = [row for row in rows if row.get("category") == "blocked"]
    manual = [row for row in rows if row.get("category") == "manual"]
    stale = [row for row in rows if row.get("category") == "stale"]
    available = [row for row in rows if row.get("category") == "available"]
    status = _ledger_status(rows)
    if status == "blocked":
        tone = "danger"
        label = "阻断加仓"
        summary = f"接口健康阻断：{_limited_labels(blocked)}。"
        decision_impact = "受限接口未恢复前，不能把缺失数据当成利好，也不能支撑加仓、追高或加融资。"
        strategy_action = "策略执行降级为观察/小额试探；先按数据恢复中心手动恢复阻断接口。"
        projection_note = f"受限接口压制乐观路径：{_limited_labels(blocked)}。"
        risk_note = "关键接口受限时，趋势推演只用于观察验证，不作为加仓依据。"
    elif status == "partial":
        tone = "warning"
        label = "谨慎验证"
        pending_text = "；".join(
            item
            for item in [
                f"待手动：{_limited_labels(manual)}" if manual else "",
                f"缓存/待验证：{_limited_labels(stale)}" if stale else "",
            ]
            if item
        )
        summary = f"接口健康部分可用，{pending_text or '仍需复核'}。"
        decision_impact = "可继续看盘，但执行前必须复核缓存日期、手动刷新项和待验证接口。"
        strategy_action = "策略条件必须先验证数据新鲜度；不把缓存/无记录写成无风险。"
        projection_note = f"路径仍待数据确认：{pending_text or '接口待验证'}。"
        risk_note = "接口未完全确认时，乐观路径只能作为假设，优先维持中性/谨慎执行。"
    elif status == "ready":
        tone = "success"
        label = "可进入证据链"
        summary = f"接口健康可用：{_limited_labels(available)}。"
        decision_impact = "接口状态可作为辅助证据；执行前仍需价格、纪律和仓位共振。"
        strategy_action = "可把接口结果纳入策略验证，但仍需触发条件确认。"
        projection_note = f"可用接口支持路径验证：{_limited_labels(available)}。"
        risk_note = "即便接口可用，仍不自动交易、不保证收益。"
    else:
        tone = "muted"
        label = "待检测"
        summary = "接口健康账本待生成。"
        decision_impact = "尚未检测接口状态；只能展示安全空态或上次成功结果。"
        strategy_action = "先刷新今日基础数据或手动检测关键接口。"
        projection_note = "接口健康待检测，路径为待验证。"
        risk_note = "数据未检测时，不把乐观路径作为执行依据。"
    return {
        "status": status,
        "tone": tone,
        "label": label,
        "summary": summary,
        "decision_impact": decision_impact,
        "strategy_action": strategy_action,
        "projection_note": projection_note,
        "risk_note": risk_note,
        "blocked_count": len(blocked),
        "manual_count": len(manual),
        "stale_count": len(stale),
        "available_count": len(available),
        "blocked_labels": _limited_labels(blocked, fallback="无"),
        "manual_labels": _limited_labels(manual, fallback="无"),
        "stale_labels": _limited_labels(stale, fallback="无"),
        "available_labels": _limited_labels(available, fallback="无"),
        "deepseek_called": False,
    }


def build_data_health_visibility_summary(data_health_ledger: Any = None, limit: int = 4) -> dict:
    ledger = as_mapping(data_health_ledger)
    rows = [as_mapping(row) for row in as_list(ledger.get("rows")) if as_mapping(row)]
    if not rows:
        return {
            "title": "为什么搜不到",
            "status": "missing",
            "tone": "missing",
            "headline": "数据能力待检测",
            "summary": "暂无接口级健康账本；页面打开不会自动请求外部接口。",
            "explanation": "先刷新今日基础数据或在数据恢复中心手动检测关键接口。",
            "items": [],
            "permission_labels": "无",
            "skipped_labels": "无",
            "cache_labels": "无",
            "empty_labels": "无",
            "manual_labels": "无",
            "external_call_policy": "not_triggered",
            "deepseek_called": False,
        }
    permission = [row for row in rows if row.get("state") == "permission_denied"]
    skipped = [row for row in rows if row.get("state") == "disabled_this_session"]
    cache = [row for row in rows if row.get("state") in {"stale_cache", "fallback_used"}]
    empty = [row for row in rows if row.get("state") == "empty_recent"]
    manual = [row for row in rows if row.get("category") == "manual"]
    blocked = [row for row in rows if row.get("category") == "blocked"]
    stale = [row for row in rows if row.get("category") == "stale"]
    available = [row for row in rows if row.get("category") == "available"]
    if permission or skipped:
        status = "blocked"
        tone = "failed"
        headline = "Tushare 拉满 ≠ 每个专业接口都有权限"
        explanation = "token 或基础行情可用，不代表融资融券、涨跌停情绪、龙虎榜等专业接口都有权限；受限项不能写成利好。"
    elif cache or empty or manual or stale:
        status = "partial"
        tone = "stale"
        headline = "部分数据来自缓存、近期无记录或需要手动刷新"
        explanation = "搜不到可能是非交易日、数据尚未更新、标的未覆盖、缓存过期或接口需要手动刷新；执行前要复核日期和来源。"
    else:
        status = "ready"
        tone = "ready"
        headline = "关键数据能力当前可读"
        explanation = "接口健康可作为辅助证据；仍需价格纪律、仓位预算和失效条件共同确认。"
    visible_rows = []
    recovery_actions = []
    seen = set()
    for row in blocked + manual + cache + empty + stale + available:
        key = _row_key(row)
        if key in seen:
            continue
        seen.add(key)
        legacy_tab = _legacy_tab_from_recovery_target(row.get("writes_packet"), row.get("toolbox_entry"))
        recovery_action = {
            "key": f"data_health_visibility:{to_text(row.get('api') or row.get('label'), 'data_capability')}",
            "label": to_text(row.get("label"), "数据接口"),
            "provider": to_text(row.get("provider"), "数据源"),
            "api": to_text(row.get("api")),
            "state": to_text(row.get("state"), "unknown"),
            "status_label": to_text(row.get("status_label"), STATE_LABELS.get(to_text(row.get("state")), "待验证")),
            "tone": to_text(row.get("tone"), "missing"),
            "action_label": to_text(row.get("action_label"), f"手动检查{to_text(row.get('label'), '数据接口')}"),
            "toolbox_entry": to_text(row.get("toolbox_entry"), "高级工具箱 / 数据源体检"),
            "workspace_target": "高级工具箱（旧版保留）",
            "workspace_state_key": "workspace_mode_v2",
            "legacy_tab_state_key": "legacy_workspace_selected_tab",
            "legacy_tab": legacy_tab,
            "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {to_text(row.get('writes_packet'), 'command_center_data_capability_packet')}。",
            "writes_packet": to_text(row.get("writes_packet"), "command_center_data_capability_packet"),
            "refresh_policy": to_text(row.get("refresh_policy"), "button_gated"),
            "diagnostic_answer": to_text(row.get("diagnostic_answer"), "仍需核对接口状态、日期和覆盖范围。"),
            "decision_guardrail": to_text(row.get("decision_guardrail"), "缺失或未知状态不能作为加仓依据。"),
            "recovery_button_context": to_text(row.get("recovery_button_context"), "按钮只检测当前接口并回流 packet；不会自动调用 DeepSeek 或重型任务。"),
            "deepseek_called": False,
        }
        visible_rows.append(
            {
                **{
                    key: recovery_action[key]
                    for key in (
                        "label",
                        "provider",
                        "api",
                        "state",
                        "status_label",
                        "tone",
                        "action_label",
                        "toolbox_entry",
                        "legacy_tab",
                        "writes_packet",
                        "refresh_policy",
                    )
                },
                "meaning": to_text(row.get("meaning"), "仍需核对接口状态。"),
                "diagnostic_answer": recovery_action["diagnostic_answer"],
                "decision_guardrail": recovery_action["decision_guardrail"],
                "recovery_button_context": recovery_action["recovery_button_context"],
                "next_action": to_text(row.get("next_action"), "按数据恢复中心手动处理。"),
                "last_success_text": to_text(row.get("last_success_text"), "暂无"),
                "navigation_label": recovery_action["navigation_label"],
            }
        )
        if recovery_action["refresh_policy"] == "button_gated":
            recovery_actions.append(recovery_action)
        if len(visible_rows) >= max(1, int(limit or 4)):
            break
    return {
        "title": "为什么搜不到",
        "status": status,
        "tone": tone,
        "headline": headline,
        "summary": (
            f"阻断 {len(blocked)}｜手动 {len(manual)}｜缓存/近期无数据 {len(stale)}｜可用 {len(available)}"
        ),
        "explanation": explanation,
        "items": visible_rows,
        "permission_labels": _limited_labels(permission, fallback="无"),
        "skipped_labels": _limited_labels(skipped, fallback="无"),
        "cache_labels": _limited_labels(cache, fallback="无"),
        "empty_labels": _limited_labels(empty, fallback="无"),
        "manual_labels": _limited_labels(manual, fallback="无"),
        "recovery_actions": recovery_actions,
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }


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
