from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


FACT_SECTIONS = (
    ("moneyflow", "个股资金流"),
    ("dragon_tiger", "龙虎榜"),
    ("margin", "融资融券"),
    ("limit_emotion", "涨跌停/情绪"),
    ("chip_radar", "筹码/胜率"),
)

STATE_TEXT = {
    "available": "通过",
    "permission_denied": "权限不足",
    "empty_recent": "近期无数据",
    "stale_cache": "使用缓存",
    "fallback_used": "替代口径",
    "disabled_this_session": "本会话跳过",
    "requires_manual_refresh": "待手动刷新",
    "network_failed": "网络失败",
    "not_configured": "未配置",
    "failed": "失败",
    "unknown": "待验证",
}

ACTION_HINTS = {
    "moneyflow": "资金流可用时才作为加减仓验证，不替代价格纪律。",
    "dragon_tiger": "龙虎榜只用于识别席位行为，不单独构成买入理由。",
    "margin": "融资融券用于观察杠杆变化，权限不足时不能假设融资改善。",
    "limit_emotion": "涨跌停/情绪用于判断过热和追高风险。",
    "chip_radar": "筹码/胜率只作压力位和结构验证，缺失时保持待验证。",
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


def _first_text(payload: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if value not in [None, ""]:
            return to_text(value)
    return ""


def _capability_by_section(data_capability_packet: Any = None) -> dict:
    packet = as_mapping(data_capability_packet)
    result = {}
    for item in as_list(packet.get("items")):
        payload = as_mapping(item)
        key = to_text(payload.get("section") or payload.get("api"))
        if key:
            result[key] = payload
    return result


def _section_state(section: Mapping[str, Any], capability_item: Mapping[str, Any]) -> str:
    if capability_item.get("capability_state") or capability_item.get("state"):
        return to_text(capability_item.get("capability_state") or capability_item.get("state"), "unknown")
    if section.get("available") or section.get("boundary_available") or section.get("records_available") or section.get("concept_available"):
        return "available"
    text = " ".join(
        to_text(section.get(key))
        for key in ("error", "warning", "message")
        if section.get(key)
    )
    if "权限" in text or "permission" in text.lower() or "denied" in text.lower():
        return "permission_denied"
    if "本会话跳过" in text or "跳过重复请求" in text:
        return "disabled_this_session"
    if "无数据" in text or "未见" in text or "未取得" in text or "暂无" in text:
        return "empty_recent"
    if text:
        return "failed"
    return "unknown"


def _status_for_state(state: str) -> str:
    return STATE_TEXT.get(state, STATE_TEXT["unknown"])


def _evidence_for_section(section_key: str, section: Mapping[str, Any]) -> str:
    if section_key == "moneyflow":
        date = _first_text(section, ("date", "latest_date", "trade_date", "updated_at"))
        main_net = _first_text(section, ("main_net_yi", "five_day_main_net_yi", "net_mf_amount"))
        if main_net:
            return f"{date or '最新'} 主力净额 {main_net}。"
        return _first_text(section, ("summary", "message", "warning")) or "资金流待验证。"
    if section_key == "dragon_tiger":
        date = _first_text(section, ("latest_date", "date", "trade_date", "updated_at"))
        net_buy = _first_text(section, ("net_buy_amount_yi", "buy_amount_yi", "sell_amount_yi"))
        inst_summary = _first_text(section, ("inst_summary", "summary", "message"))
        if net_buy:
            return f"{date or '最新'} 龙虎榜净买入线索 {net_buy}。"
        return inst_summary or "龙虎榜席位待验证。"
    if section_key == "margin":
        date = _first_text(section, ("date", "trade_date", "latest_date", "updated_at"))
        summary = _first_text(section, ("summary", "message", "warning"))
        return summary or (f"{date} 融资融券数据待复核。" if date else "融资融券数据待验证。")
    if section_key == "limit_emotion":
        date = _first_text(section, ("latest_date", "concept_date", "date", "updated_at"))
        up_limit = _first_text(section, ("up_limit", "distance_to_up_pct"))
        down_limit = _first_text(section, ("down_limit", "distance_to_down_pct"))
        if up_limit or down_limit:
            return f"{date or '最新'} 涨停/跌停边界：{up_limit or '暂无'} / {down_limit or '暂无'}。"
        return _first_text(section, ("summary", "message", "warning")) or "涨跌停和情绪边界待验证。"
    if section_key == "chip_radar":
        return _first_text(section, ("summary", "message", "warning")) or "筹码/胜率结构待验证。"
    return _first_text(section, ("summary", "message", "warning")) or "事实待验证。"


def build_a_share_fact_item(
    section_key: str,
    fact_section: Any = None,
    capability_item: Any = None,
) -> dict:
    section = as_mapping(fact_section)
    capability = as_mapping(capability_item)
    label = dict(FACT_SECTIONS).get(section_key, section_key)
    state = _section_state(section, capability)
    status = to_text(capability.get("status") or capability.get("capability_label") or _status_for_state(state), _status_for_state(state))
    updated_at = _first_text(section, ("updated_at", "date", "latest_date", "trade_date")) or to_text(capability.get("updated_at") or capability.get("latest_date"))
    source = to_text(section.get("source") or capability.get("source") or "Tushare")
    risk = _first_text(section, ("warning", "error", "message")) or to_text(capability.get("error"))
    if not risk and state != "available":
        risk = to_text(capability.get("action_hint"), "数据不足，保持待验证。")
    return {
        "key": section_key,
        "label": label,
        "status": status,
        "state": state,
        "evidence": _evidence_for_section(section_key, section),
        "risk": risk,
        "action_hint": to_text(capability.get("action_hint") or ACTION_HINTS.get(section_key), ACTION_HINTS.get(section_key, "")),
        "source": source,
        "updated_at": updated_at,
        "api": to_text(section.get("api") or capability.get("api")),
    }


def build_a_share_facts_packet(
    fact_packet: Any = None,
    data_capability_packet: Any = None,
    target: str = "",
    name: str = "",
) -> dict:
    facts = as_mapping(fact_packet)
    capability = data_capability_packet if data_capability_packet is not None else facts.get("data_capability")
    capability_items = _capability_by_section(capability)
    items = []
    for section_key, _label in FACT_SECTIONS:
        item = build_a_share_fact_item(
            section_key,
            facts.get(section_key) or {},
            capability_items.get(section_key) or capability_items.get(to_text((facts.get(section_key) or {}).get("api"))) or {},
        )
        items.append(item)
    available_count = sum(1 for item in items if item["state"] == "available")
    restricted_count = sum(1 for item in items if item["state"] in {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"})
    pending_count = len(items) - available_count - restricted_count
    if available_count:
        status = "ready" if restricted_count == 0 and pending_count == 0 else "partial"
    elif restricted_count or pending_count:
        status = "partial"
    else:
        status = "waiting"
    return {
        "status": status,
        "market": "A股",
        "ticker": to_text(target or facts.get("stock_code")),
        "name": to_text(name or facts.get("stock_name")),
        "available_count": available_count,
        "restricted_count": restricted_count,
        "pending_count": pending_count,
        "items": items,
        "summary": f"A股事实：可用 {available_count}，受限 {restricted_count}，待验证 {pending_count}。",
        "source": to_text(facts.get("data_source"), "Tushare + local cache"),
        "updated_at": to_text(facts.get("updated_at") or as_mapping(capability).get("checked_at")),
        "deepseek_called": False,
    }


def build_command_center_facts_packet(
    state: Any = None,
    target: str = "",
    name: str = "",
) -> dict:
    state_map = as_mapping(state)
    existing = as_mapping(state_map.get("command_center_facts_packet") or state_map.get("command_center_a_share_facts_packet"))
    if existing.get("items"):
        return {
            **existing,
            "deepseek_called": False,
        }
    facts = state_map.get("a_share_professional_facts") or {}
    capability = state_map.get("a_share_professional_data_capability") or {}
    if facts or capability:
        return build_a_share_facts_packet(facts, capability, target=target, name=name)
    return {
        "status": "waiting",
        "market": "待确认",
        "ticker": to_text(target),
        "name": to_text(name),
        "available_count": 0,
        "restricted_count": 0,
        "pending_count": 0,
        "items": [],
        "summary": "暂无可验证事实包；点击刷新今日基础数据或进入高级工具箱生成。",
        "source": "local cache",
        "updated_at": "",
        "deepseek_called": False,
    }
