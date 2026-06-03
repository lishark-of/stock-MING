from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_SOURCES = 6
MAX_NOTES = 6


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


def to_number(value: Any) -> int | float | None:
    if value in [None, ""]:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Number):
        return value
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("%", "")
        if not text or text in {"--", "暂无", "N/A", "None", "nan"}:
            return None
        try:
            number = float(text)
            return int(number) if number.is_integer() else number
        except Exception:
            return None
    return None


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = to_text(value)
        if text:
            return text
    return default


def _dedupe_text(values: Any, limit: int = MAX_NOTES) -> list[str]:
    raw_values = values if isinstance(values, (list, tuple)) else [values]
    items = []
    seen = set()
    for item in raw_values:
        if isinstance(item, Mapping):
            text = _first_text(item.get("message"), item.get("summary"), item.get("reason"), item.get("source"))
        else:
            text = to_text(item)
        if text and text not in seen:
            seen.add(text)
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _derive_status(packet: Mapping[str, Any], verified_sources: list[str], missing_sources: list[str]) -> str:
    if verified_sources:
        return "ready" if not missing_sources else "partial"
    if packet:
        return "partial"
    return "waiting"


def _derive_action_state(market_state: str, risk_switch: str) -> str:
    text = f"{market_state} {risk_switch}"
    if any(token in text for token in ("退潮", "防守", "只观察", "风险")):
        return "防守观察"
    if any(token in text for token in ("高潮", "强修复", "进攻")):
        return "可轻仓试错"
    if any(token in text for token in ("修复", "分歧", "轻仓")):
        return "轻仓验证"
    return "待验证"


def _derive_risk_notes(packet: Mapping[str, Any], missing_sources: list[str], break_rate: int | float | None) -> list[str]:
    notes = []
    if break_rate is not None and break_rate >= 0.45:
        notes.append("炸板率偏高，追高风险上升。")
    down_count = to_number(packet.get("limit_down_count")) or 0
    if down_count >= 10:
        notes.append("跌停家数偏多，优先防守观察。")
    if missing_sources:
        notes.append("存在市场数据缺口，不能把缺失数据当成利好。")
    notes.extend(_dedupe_text(missing_sources, limit=MAX_NOTES))
    if not notes:
        notes.append("市场风格只作为仓位和节奏辅助，不单独构成买入理由。")
    return _dedupe_text(notes, limit=MAX_NOTES)


def build_command_center_market_packet(state: Any = None, live_packet: Any = None) -> dict:
    state_map = as_mapping(state)
    live = as_mapping(live_packet)
    live_section = as_mapping(live.get("market"))
    existing = as_mapping(state_map.get("command_center_market_packet"))
    if existing.get("status") in {"ready", "partial"}:
        return {
            **existing,
            "verified_sources": _dedupe_text(existing.get("verified_sources"), limit=MAX_SOURCES),
            "missing_sources": _dedupe_text(existing.get("missing_sources"), limit=MAX_SOURCES),
            "risk_notes": _dedupe_text(existing.get("risk_notes"), limit=MAX_NOTES)
            or ["市场风格只作为仓位和节奏辅助，不单独构成买入理由。"],
            "deepseek_called": False,
        }
    packet = as_mapping(state_map.get("legacy_market_style_fact_packet"))
    verified_sources = _dedupe_text(packet.get("verified_sources"), limit=MAX_SOURCES)
    missing_sources = _dedupe_text(packet.get("missing_sources"), limit=MAX_SOURCES)
    market_state = _first_text(
        live_section.get("market_state"),
        packet.get("market_state"),
        default="暂无可验证数据" if packet else "待刷新",
    )
    risk_switch = _first_text(
        live_section.get("risk_switch"),
        packet.get("risk_switch"),
        default="等待刷新" if not packet else "适合只观察不买",
    )
    break_rate = to_number(packet.get("break_limit_rate"))
    status = _derive_status(packet, verified_sources, missing_sources)
    limit_up_count = to_number(packet.get("limit_up_count")) or 0
    limit_down_count = to_number(packet.get("limit_down_count")) or 0
    break_limit_count = to_number(packet.get("break_limit_count")) or 0
    summary = _first_text(
        live_section.get("summary"),
        packet.get("summary"),
        default=(
            f"{market_state}；{risk_switch}。涨停 {limit_up_count}，跌停 {limit_down_count}，炸板 {break_limit_count}。"
            if packet
            else "暂无市场风格缓存；点击刷新今日基础数据后读取，不在页面打开时自动请求 Tushare。"
        ),
    )
    return {
        "status": status,
        "source": _first_text(live_section.get("source"), default=" / ".join(verified_sources[:4]) if verified_sources else "Tushare 市场风格事实包"),
        "updated_at": _first_text(packet.get("updated_at"), live_section.get("updated_at")),
        "trade_date": to_text(packet.get("trade_date")),
        "market_state": market_state,
        "risk_switch": risk_switch,
        "action_state": _derive_action_state(market_state, risk_switch),
        "limit_up_count": limit_up_count,
        "limit_down_count": limit_down_count,
        "break_limit_count": break_limit_count,
        "break_limit_rate": break_rate,
        "max_consecutive_limit": to_number(packet.get("max_consecutive_limit")),
        "verified_sources": verified_sources,
        "missing_sources": missing_sources,
        "concept_strength_top": as_list(packet.get("concept_strength_top"))[:5],
        "dragon_tiger_activity_count": to_number(as_mapping(packet.get("dragon_tiger_activity")).get("list_count")) or 0,
        "positive_moneyflow_sample_count": len(as_list(as_mapping(packet.get("moneyflow_samples")).get("positive_samples"))),
        "negative_moneyflow_sample_count": len(as_list(as_mapping(packet.get("moneyflow_samples")).get("negative_samples"))),
        "summary": summary,
        "risk_notes": _derive_risk_notes(packet, missing_sources, break_rate),
        "data_status": "ready" if verified_sources else ("cached" if packet else "missing"),
        "deepseek_called": False,
    }
