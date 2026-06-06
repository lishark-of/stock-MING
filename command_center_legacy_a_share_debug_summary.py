from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import market_data_capability as capability_language


PERMISSION_KEYWORDS = ("权限", "permission", "积分", "无接口访问权限")
STALE_KEYWORDS = ("无数据", "暂无可验证", "暂未取得", "数据尚未更新", "待刷新", "待验证", "缺失")
FUND_SOURCE_LABELS = {
    "moneyflow": "个股资金流",
    "dragon_tiger": "龙虎榜",
    "margin": "融资融券",
    "limit_emotion": "涨跌停 / 情绪",
    "chip_radar": "筹码 / 胜率",
    "hard_risk": "公告 / 硬风险",
}
A_SHARE_RECOVERY_CONFIG = {
    "moneyflow": {
        "action_label": "检测资金流",
        "toolbox_entry": "综合推演中心 / A股数据能力检测",
        "advanced_entry": "高级工具箱 / 今日关注池 / A股专业数据穿透系统",
        "legacy_tab": "今日关注池",
        "writes_packet": "command_center_moneyflow_packet",
        "api_hint": "Tushare moneyflow",
    },
    "dragon_tiger": {
        "action_label": "检测龙虎榜",
        "toolbox_entry": "综合推演中心 / A股数据能力检测",
        "advanced_entry": "高级工具箱 / 今日关注池 / A股专业数据穿透系统",
        "legacy_tab": "今日关注池",
        "writes_packet": "command_center_dragon_tiger_packet",
        "api_hint": "Tushare top_list / top_inst",
    },
    "margin": {
        "action_label": "检测融资融券",
        "toolbox_entry": "综合推演中心 / A股数据能力检测",
        "advanced_entry": "高级工具箱 / 今日关注池 / A股专业数据穿透系统",
        "legacy_tab": "今日关注池",
        "writes_packet": "command_center_margin_packet",
        "api_hint": "Tushare margin_detail",
    },
    "limit_emotion": {
        "action_label": "检测涨跌停",
        "toolbox_entry": "综合推演中心 / A股数据能力检测",
        "advanced_entry": "高级工具箱 / 今日关注池 / A股专业数据穿透系统",
        "legacy_tab": "今日关注池",
        "writes_packet": "command_center_limit_emotion_packet",
        "api_hint": "Tushare stk_limit / limit_list_d / limit_cpt_list",
    },
    "chip_radar": {
        "action_label": "检测筹码/胜率",
        "toolbox_entry": "综合推演中心 / A股数据能力检测",
        "advanced_entry": "高级工具箱 / 今日关注池 / A股专业数据穿透系统",
        "legacy_tab": "今日关注池",
        "writes_packet": "command_center_chip_packet",
        "api_hint": "Tushare cyq_perf / cyq_chips",
    },
    "hard_risk": {
        "action_label": "检测公告/硬风险",
        "toolbox_entry": "综合推演中心 / A股数据能力检测",
        "advanced_entry": "高级工具箱 / 天眼风控",
        "legacy_tab": "天眼风控",
        "writes_packet": "command_center_hard_risk_packet",
        "api_hint": "Tushare anns_d / forecast / holdertrade / pledge / suspend",
    },
}
STATUS_GROUP_CONFIG = {
    "available": {"label": "可用", "tone": "ready", "empty": "暂无可用数据"},
    "permission_denied": {"label": "受限", "tone": "failed", "empty": "暂无权限阻断"},
    "stale_or_empty": {"label": "暂无数据", "tone": "stale", "empty": "暂无空数据项"},
    "manual_required": {"label": "自动检测中", "tone": "missing", "empty": "暂无自动检测待验证项"},
}


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def debug_text(value: Any, fallback: str = "暂无可验证数据", limit: int = 120) -> str:
    if value is None or value == "":
        return fallback
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def debug_status(data: Any) -> bool:
    data = as_mapping(data)
    if "ok" in data:
        return bool(data.get("ok"))
    status = str(data.get("status") or "").lower()
    if status in {"ready", "ok", "completed", "success"}:
        return True
    if status in {"failed", "error", "failure", "waiting", "missing"}:
        return False
    data_status = str(data.get("data_status") or data.get("cache_state") or "").lower()
    if data_status == "ready":
        return True
    if data_status in {"missing", "failed", "waiting"}:
        return False
    return bool(data.get("available"))


def debug_note(data: Any) -> str:
    data = as_mapping(data)
    risk_notes = as_list(data.get("risk_notes"))
    return debug_text(
        data.get("warning")
        or data.get("message")
        or data.get("error")
        or data.get("summary")
        or data.get("manual_required_text")
        or (risk_notes[0] if risk_notes else "")
        or ""
    )


def debug_issue_matches(data: Any, keywords: tuple[str, ...]) -> str:
    data = as_mapping(data)
    text = " ".join(str(data.get(key) or "") for key in ["message", "warning", "error"])
    if not text:
        return ""
    lowered = text.lower()
    if not any(keyword.lower() in lowered for keyword in keywords):
        return ""
    return debug_text(text)


def _issue_text(data: Any) -> str:
    payload = as_mapping(data)
    return " ".join(str(payload.get(key) or "") for key in ["message", "warning", "error", "status", "capability_state"])


def _capability_state_from_data(data: Any) -> str:
    payload = as_mapping(data)
    explicit = payload.get("capability_state") or payload.get("state")
    if explicit:
        normalized = capability_language.normalize_capability_state_value(explicit)
        if normalized != "unknown":
            return normalized
    text = _issue_text(payload)
    if not text.strip():
        return capability_language.STATE_EMPTY_RECENT
    return capability_language.normalize_capability_state_value(text)


def build_technical_summary(verified_technical_facts: Any) -> dict:
    facts = as_mapping(verified_technical_facts)
    technical_missing = as_list(facts.get("missing")) or as_list(facts.get("missing_items"))
    return {
        "available": bool(facts.get("available")),
        "latest_close": debug_text(facts.get("latest_close")),
        "ma60_state": debug_text(facts.get("ma60_state")),
        "rsi_14": debug_text(facts.get("rsi_14")),
        "volume_vs_20d": debug_text(facts.get("volume_vs_20d")),
        "return_20d": debug_text(facts.get("return_20d")),
        "return_60d": debug_text(facts.get("return_60d")),
        "drawdown_60d": debug_text(facts.get("drawdown_60d")),
        "market_date": debug_text(facts.get("market_date")),
        "source": debug_text(facts.get("source")),
        "confidence": debug_text(facts.get("confidence")),
        "missing": "、".join(str(item) for item in technical_missing) if technical_missing else "无",
    }


def build_fund_rows(
    moneyflow_data: Any = None,
    dragon_data: Any = None,
    margin_data: Any = None,
    limit_emotion_data: Any = None,
    chip_radar_data: Any = None,
    hard_risk_data: Any = None,
) -> tuple[list[dict], list[str], list[str], list[str]]:
    moneyflow_data = as_mapping(moneyflow_data)
    dragon_data = as_mapping(dragon_data)
    margin_data = as_mapping(margin_data)
    limit_emotion_data = as_mapping(limit_emotion_data)
    chip_radar_data = as_mapping(chip_radar_data)
    hard_risk_data = as_mapping(hard_risk_data)
    fund_sources = [
        ("moneyflow", moneyflow_data, {
            "latest_date": moneyflow_data.get("date"),
            "direction": moneyflow_data.get("direction"),
            "main_net_inflow_yi": moneyflow_data.get("main_net_yi"),
            "five_day_main_net_inflow_yi": moneyflow_data.get("five_day_main_net_yi"),
        }),
        ("dragon_tiger", dragon_data, {
            "trade_date": dragon_data.get("latest_date"),
            "reason": dragon_data.get("reason"),
            "net_buy_amount": dragon_data.get("net_buy_amount_yi"),
            "institution_summary_exists": bool(dragon_data.get("inst_summary")),
        }),
        ("margin", margin_data, {
            "trade_date": margin_data.get("date"),
            "financing_balance_yi": margin_data.get("financing_balance_yi"),
            "margin_balance_yi": margin_data.get("margin_balance_yi"),
        }),
        ("limit_emotion", limit_emotion_data, {
            "trade_date": limit_emotion_data.get("latest_date") or limit_emotion_data.get("concept_date"),
            "limit_up_price": limit_emotion_data.get("up_limit"),
            "limit_down_price": limit_emotion_data.get("down_limit"),
            "recent_limit_records_count": len(as_list(limit_emotion_data.get("limit_records"))),
        }),
        ("chip_radar", chip_radar_data, {
            "trade_date": chip_radar_data.get("trade_date") or chip_radar_data.get("date"),
            "winner_rate": chip_radar_data.get("winner_rate"),
            "pressure_state": chip_radar_data.get("pressure_state") or chip_radar_data.get("chip_pressure_comment"),
        }),
        ("hard_risk", hard_risk_data, {
            "updated_at": hard_risk_data.get("updated_at"),
            "risk_state": hard_risk_data.get("risk_state"),
            "risk_item_count": hard_risk_data.get("risk_item_count") or len(as_list(hard_risk_data.get("risk_items"))),
        }),
    ]

    fund_rows = []
    funding_missing = []
    permission_issues = []
    stale_issues = []
    for name, data, extras in fund_sources:
        available = debug_status(data)
        ok = debug_status(data)
        if not available or not ok:
            funding_missing.append(name)
        capability_state = _capability_state_from_data(data)
        issue_text = debug_text(_issue_text(data), fallback="")
        permission_note = issue_text if capability_state in {"permission_denied", "disabled_this_session"} else ""
        stale_note = issue_text if capability_state in {"empty_recent", "stale_cache", "fallback_used"} else ""
        if permission_note:
            permission_issues.append(f"{name}: {permission_note}")
        if stale_note:
            stale_issues.append(f"{name}: {stale_note}")
        row = {
            "name": name,
            "available": available,
            "ok": ok,
            "source": debug_text(data.get("source")),
            "api": debug_text(data.get("api")),
            "note": debug_note(data),
            "capability_state": capability_state,
        }
        for key, value in extras.items():
            row[key] = value if isinstance(value, bool) else debug_text(value)
        fund_rows.append(row)

    return fund_rows, funding_missing, permission_issues, stale_issues


def build_packet_status(
    verified_technical_facts: Any = None,
    ai_context_packet: Any = "",
    whale_fact_packet: Any = None,
    next_day_plan_fact_packet: Any = None,
    single_stock_war_room_fact_packet: Any = None,
) -> dict:
    facts = as_mapping(verified_technical_facts)
    ai_context_text = str(ai_context_packet or "")
    return {
        "verified_technical_facts_available": bool(facts.get("available")),
        "ai_context_packet_has_verified_technical_facts": "【已验证技术事实】" in ai_context_text,
        "whale_fact_packet_status": "已构造" if whale_fact_packet is not None else "尚未触发",
        "next_day_plan_fact_packet_status": "已构造" if next_day_plan_fact_packet is not None else "尚未触发",
        "single_stock_war_room_fact_packet_status": "已构造" if single_stock_war_room_fact_packet is not None else "尚未触发",
        "market_style_fact_packet_status": "仅今日关注池生成 / 当前页未生成",
    }


def build_missing_summary(
    verified_technical_facts: Any = None,
    funding_missing: Any = None,
    permission_issues: Any = None,
    stale_issues: Any = None,
) -> dict:
    facts = as_mapping(verified_technical_facts)
    technical_missing = as_list(facts.get("missing")) or as_list(facts.get("missing_items"))
    funding_missing = as_list(funding_missing)
    permission_issues = as_list(permission_issues)
    stale_issues = as_list(stale_issues)
    return {
        "技术缺失项": "、".join(str(item) for item in technical_missing) if technical_missing else "无",
        "资金缺失项": "、".join(str(item) for item in funding_missing) if funding_missing else "无",
        "权限不足项": "；".join(str(item) for item in permission_issues) if permission_issues else "无",
        "数据未更新项": "；".join(str(item) for item in stale_issues) if stale_issues else "无",
    }


def _dict_rows(mapping: dict, key_name: str, value_name: str) -> list[dict]:
    return [{key_name: key, value_name: value} for key, value in mapping.items()]


def build_legacy_a_share_debug_view_model(
    verified_technical_facts: Any = None,
    moneyflow_data: Any = None,
    dragon_data: Any = None,
    margin_data: Any = None,
    limit_emotion_data: Any = None,
    chip_radar_data: Any = None,
    hard_risk_data: Any = None,
    ai_context_packet: Any = "",
    whale_fact_packet: Any = None,
    next_day_plan_fact_packet: Any = None,
    single_stock_war_room_fact_packet: Any = None,
) -> dict:
    technical_summary = build_technical_summary(verified_technical_facts)
    fund_rows, funding_missing, permission_issues, stale_issues = build_fund_rows(
        moneyflow_data=moneyflow_data,
        dragon_data=dragon_data,
        margin_data=margin_data,
        limit_emotion_data=limit_emotion_data,
        chip_radar_data=chip_radar_data,
        hard_risk_data=hard_risk_data,
    )
    packet_status = build_packet_status(
        verified_technical_facts=verified_technical_facts,
        ai_context_packet=ai_context_packet,
        whale_fact_packet=whale_fact_packet,
        next_day_plan_fact_packet=next_day_plan_fact_packet,
        single_stock_war_room_fact_packet=single_stock_war_room_fact_packet,
    )
    missing_summary = build_missing_summary(
        verified_technical_facts=verified_technical_facts,
        funding_missing=funding_missing,
        permission_issues=permission_issues,
        stale_issues=stale_issues,
    )

    return {
        "technical_summary": technical_summary,
        "technical_rows": _dict_rows(technical_summary, "字段", "值"),
        "fund_rows": fund_rows,
        "funding_missing": funding_missing,
        "permission_issues": permission_issues,
        "stale_issues": stale_issues,
        "packet_status": packet_status,
        "packet_status_rows": _dict_rows(packet_status, "字段", "状态"),
        "missing_summary": missing_summary,
        "missing_rows": _dict_rows(missing_summary, "类别", "摘要"),
    }


def _classify_fund_row(row: dict) -> tuple[str, str, str]:
    if row.get("available") and row.get("ok"):
        return "available", "已取得", "已读取到可验证数据。"
    state = str(row.get("capability_state") or "")
    if state == "permission_denied":
        return "permission_denied", "权限不足", "当前接口需要更高 Tushare 权限或积分。"
    if state == "disabled_this_session":
        return "permission_denied", "本会话跳过", "当前接口此前已判定受限，本会话跳过重复请求以避免卡顿。"
    if state in {"not_configured", "network_failed", "failed"}:
        return "permission_denied", "调用受限", capability_language.meaning_for_capability_state(state, "Tushare", FUND_SOURCE_LABELS.get(row.get("name"), "A股数据"))
    if state in {"empty_recent", "stale_cache", "fallback_used"}:
        return "stale_or_empty", capability_language.STATE_LABELS.get(state, "暂无当日数据"), capability_language.meaning_for_capability_state(state, "Tushare", FUND_SOURCE_LABELS.get(row.get("name"), "A股数据"))
    if state == "requires_manual_refresh":
        return "manual_required", "自动检测中", "当前分区会按 TTL 自动检测；强制刷新可绕过 TTL。"
    return "manual_required", "自动检测中", "当前分区会按 TTL 自动检测；强制刷新可绕过 TTL。"


def _recovery_reason(status: str, label: str) -> str:
    if status == "available":
        return f"{label}已可用；无需恢复，只需复核日期和来源。"
    if status == "permission_denied":
        return f"{label}可能需要更高 Tushare 权限或积分；如已升级权限，可强制重检。"
    if status == "stale_or_empty":
        return f"{label}可能尚未发布、非交易日或标的不覆盖；不能把缺失写成利好，等待发布后自动重检或强制重检。"
    return f"{label}自动检测中或待验证；当前分区按 TTL 请求 Tushare。"


def _build_recovery_metadata(name: str, status: str, label: str) -> dict:
    config = A_SHARE_RECOVERY_CONFIG.get(name, {})
    action_label = config.get("action_label") or f"检测{label}"
    return {
        "action_label": "无需恢复" if status == "available" else action_label,
        "reason": _recovery_reason(status, label),
        "toolbox_entry": config.get("toolbox_entry") or "综合推演中心 / A股数据能力检测",
        "advanced_entry": config.get("advanced_entry") or "高级工具箱 / 今日关注池",
        "legacy_tab": config.get("legacy_tab") or "今日关注池",
        "writes_packet": config.get("writes_packet") or "command_center_facts_packet",
        "api_hint": config.get("api_hint") or "Tushare A股专业接口",
        "refresh_policy": "not_needed" if status == "available" else "button_gated",
        "deepseek_called": False,
    }


def build_status_console(items: Any = None) -> dict:
    rows = [as_mapping(item) for item in as_list(items) if as_mapping(item)]
    groups = []
    for key, config in STATUS_GROUP_CONFIG.items():
        matched = [item for item in rows if item.get("status") == key]
        labels = [debug_text(item.get("label"), "A股数据", limit=40) for item in matched]
        groups.append(
            {
                "key": key,
                "label": config["label"],
                "tone": config["tone"],
                "count": len(matched),
                "items": labels,
                "summary": "、".join(labels) if labels else config["empty"],
            }
        )
    counts = {group["key"]: group["count"] for group in groups}
    if counts.get("permission_denied"):
        readiness = "阻断加仓"
        headline = "A股关键数据有权限阻断"
    elif counts.get("stale_or_empty"):
        readiness = "谨慎验证"
        headline = "A股关键数据部分暂无当日结果"
    elif counts.get("manual_required"):
        readiness = "自动检测中"
        headline = "A股关键数据自动检测中"
    elif counts.get("available"):
        readiness = "可进入证据链"
        headline = "A股关键数据已可用"
    else:
        readiness = "待检测"
        headline = "A股关键数据尚未检测"
    return {
        "title": "A股数据能力控制台",
        "headline": headline,
        "decision_readiness_label": readiness,
        "summary": (
            f"可用 {counts.get('available', 0)}｜"
            f"受限 {counts.get('permission_denied', 0)}｜"
            f"暂无数据 {counts.get('stale_or_empty', 0)}｜"
            f"自动检测中 {counts.get('manual_required', 0)}"
        ),
        "groups": groups,
        "safe_mode_text": "当前页按 TTL 自动请求当前标的必要 Tushare 分区；DeepSeek、回测和全市场扫描仍只手动触发。",
        "deepseek_called": False,
    }


def build_user_data_diagnostic_view_model(
    verified_technical_facts: Any = None,
    moneyflow_data: Any = None,
    dragon_data: Any = None,
    margin_data: Any = None,
    limit_emotion_data: Any = None,
    chip_radar_data: Any = None,
    hard_risk_data: Any = None,
    ai_context_packet: Any = "",
    whale_fact_packet: Any = None,
    next_day_plan_fact_packet: Any = None,
    single_stock_war_room_fact_packet: Any = None,
) -> dict:
    debug_view_model = build_legacy_a_share_debug_view_model(
        verified_technical_facts=verified_technical_facts,
        moneyflow_data=moneyflow_data,
        dragon_data=dragon_data,
        margin_data=margin_data,
        limit_emotion_data=limit_emotion_data,
        chip_radar_data=chip_radar_data,
        hard_risk_data=hard_risk_data,
        ai_context_packet=ai_context_packet,
        whale_fact_packet=whale_fact_packet,
        next_day_plan_fact_packet=next_day_plan_fact_packet,
        single_stock_war_room_fact_packet=single_stock_war_room_fact_packet,
    )

    items = []
    counts = {
        "available": 0,
        "permission_denied": 0,
        "stale_or_empty": 0,
        "manual_required": 0,
    }
    for row in debug_view_model.get("fund_rows") or []:
        status, status_label, reason = _classify_fund_row(row)
        counts[status] = counts.get(status, 0) + 1
        label = FUND_SOURCE_LABELS.get(row.get("name"), row.get("name") or "A股数据")
        recovery = _build_recovery_metadata(str(row.get("name") or ""), status, label)
        items.append({
            "key": row.get("name") or "",
            "label": label,
            "status": status,
            "status_label": status_label,
            "reason": reason,
            "source": row.get("source") or "暂无可验证数据",
            "api": row.get("api") or "暂无可验证数据",
            "note": row.get("note") or "暂无可验证数据",
            "recovery": recovery,
            "action_label": recovery["action_label"],
            "toolbox_entry": recovery["toolbox_entry"],
            "advanced_entry": recovery["advanced_entry"],
            "legacy_tab": recovery["legacy_tab"],
            "writes_packet": recovery["writes_packet"],
            "refresh_policy": recovery["refresh_policy"],
            "deepseek_called": False,
        })

    if counts["permission_denied"]:
        tone = "warning"
        headline = "部分 A股数据接口权限不足"
        next_action = "如已升级 Tushare 权限，请点击对应重试或 A股数据能力检测；否则先使用缓存/空态。"
    elif counts["stale_or_empty"]:
        tone = "info"
        headline = "部分 A股数据今日暂未取得"
        next_action = "等待交易日数据发布后自动重检，或先按上次成功缓存/空态观察。"
    elif counts["manual_required"]:
        tone = "info"
        headline = "A股专业数据自动检测中"
        next_action = "等待当前分区自动检测完成；如需立即重跑，点击强制刷新。"
    else:
        tone = "success"
        headline = "A股专业数据能力可用"
        next_action = "可继续查看事实卡；如需 DeepSeek 解释，仍需手动点击对应按钮。"

    reason_parts = []
    missing_summary = debug_view_model.get("missing_summary") or {}
    for key in ["权限不足项", "数据未更新项", "资金缺失项", "技术缺失项"]:
        value = missing_summary.get(key)
        if value and value != "无":
            reason_parts.append(f"{key}：{value}")
    recovery_actions = [
        {
            "key": item["key"],
            "label": item["label"],
            "status": item["status"],
            "status_label": item["status_label"],
            "reason": item["recovery"]["reason"],
            "action_label": item["action_label"],
            "toolbox_entry": item["toolbox_entry"],
            "advanced_entry": item["advanced_entry"],
            "legacy_tab": item["legacy_tab"],
            "workspace_target": "高级工具箱（旧版保留）",
            "workspace_state_key": "workspace_mode_v2",
            "legacy_tab_state_key": "legacy_workspace_selected_tab",
            "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{item['legacy_tab']}",
            "writes_packet": item["writes_packet"],
            "api_hint": item["recovery"]["api_hint"],
            "refresh_policy": item["refresh_policy"],
            "deepseek_called": False,
        }
        for item in items
        if item["status"] != "available"
    ]
    status_console = build_status_console(items)

    return {
        "title": "A股数据能力诊断",
        "tone": tone,
        "headline": headline,
        "summary": "；".join(reason_parts) if reason_parts else "关键 A股事实已读取到可验证数据。",
        "next_action": next_action,
        "safe_mode_text": "当前页按 TTL 自动请求当前标的必要 Tushare 分区；DeepSeek、回测和全市场扫描仍只手动触发。",
        "items": items,
        "status_console": status_console,
        "recovery_actions": recovery_actions,
        "recovery_summary": (
            f"优先处理 {recovery_actions[0]['label']}：{recovery_actions[0]['action_label']}。"
            if recovery_actions
            else "A股专业数据均已可用，暂无需要恢复的接口。"
        ),
        "counts": counts,
        "debug_view_model": debug_view_model,
    }
