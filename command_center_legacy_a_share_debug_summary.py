from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PERMISSION_KEYWORDS = ("权限", "permission", "积分", "无接口访问权限")
STALE_KEYWORDS = ("无数据", "暂未取得", "数据尚未更新")
FUND_SOURCE_LABELS = {
    "moneyflow": "个股资金流",
    "dragon_tiger": "龙虎榜",
    "margin": "融资融券",
    "limit_emotion": "涨跌停 / 情绪",
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
    return bool(data.get("available"))


def debug_note(data: Any) -> str:
    data = as_mapping(data)
    return debug_text(data.get("warning") or data.get("message") or data.get("error") or "")


def debug_issue_matches(data: Any, keywords: tuple[str, ...]) -> str:
    data = as_mapping(data)
    text = " ".join(str(data.get(key) or "") for key in ["message", "warning", "error"])
    if not text:
        return ""
    lowered = text.lower()
    if not any(keyword.lower() in lowered for keyword in keywords):
        return ""
    return debug_text(text)


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
) -> tuple[list[dict], list[str], list[str], list[str]]:
    moneyflow_data = as_mapping(moneyflow_data)
    dragon_data = as_mapping(dragon_data)
    margin_data = as_mapping(margin_data)
    limit_emotion_data = as_mapping(limit_emotion_data)
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
    ]

    fund_rows = []
    funding_missing = []
    permission_issues = []
    stale_issues = []
    for name, data, extras in fund_sources:
        available = bool(data.get("available"))
        ok = debug_status(data)
        if not available or not ok:
            funding_missing.append(name)
        permission_note = debug_issue_matches(data, PERMISSION_KEYWORDS)
        stale_note = debug_issue_matches(data, STALE_KEYWORDS)
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
    name = str(row.get("name") or "")
    note = str(row.get("note") or "")
    if row.get("available") and row.get("ok"):
        return "available", "已取得", "已读取到可验证数据。"
    if debug_issue_matches({"message": note}, PERMISSION_KEYWORDS):
        return "permission_denied", "权限不足", "当前接口可能需要更高 Tushare 权限或积分。"
    if debug_issue_matches({"message": note}, STALE_KEYWORDS):
        return "stale_or_empty", "暂无当日数据", "可能为非交易日、数据尚未发布或标的暂不覆盖。"
    return "manual_required", "待手动刷新", "页面打开不会自动请求重接口，需要点击检测或刷新。"


def build_user_data_diagnostic_view_model(
    verified_technical_facts: Any = None,
    moneyflow_data: Any = None,
    dragon_data: Any = None,
    margin_data: Any = None,
    limit_emotion_data: Any = None,
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
        items.append({
            "key": row.get("name") or "",
            "label": FUND_SOURCE_LABELS.get(row.get("name"), row.get("name") or "A股数据"),
            "status": status,
            "status_label": status_label,
            "reason": reason,
            "source": row.get("source") or "暂无可验证数据",
            "api": row.get("api") or "暂无可验证数据",
            "note": row.get("note") or "暂无可验证数据",
        })

    if counts["permission_denied"]:
        tone = "warning"
        headline = "部分 A股数据接口权限不足"
        next_action = "如已升级 Tushare 权限，请点击对应重试或 A股数据能力检测；否则先使用缓存/空态。"
    elif counts["stale_or_empty"]:
        tone = "info"
        headline = "部分 A股数据今日暂未取得"
        next_action = "等待交易日数据发布后手动刷新，或先按上次成功缓存/空态观察。"
    elif counts["manual_required"]:
        tone = "info"
        headline = "A股专业数据待手动刷新"
        next_action = "点击上方 A股数据能力检测或对应刷新按钮；页面打开不会自动请求 Tushare 重接口。"
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

    return {
        "title": "A股数据能力诊断",
        "tone": tone,
        "headline": headline,
        "summary": "；".join(reason_parts) if reason_parts else "关键 A股事实已读取到可验证数据。",
        "next_action": next_action,
        "safe_mode_text": "页面打开不会自动请求 Tushare、AkShare、DeepSeek 或回测；所有重型动作仍需手动按钮触发。",
        "items": items,
        "counts": counts,
        "debug_view_model": debug_view_model,
    }
