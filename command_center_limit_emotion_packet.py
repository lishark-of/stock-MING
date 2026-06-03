from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_RECORDS = 5
MAX_CONCEPTS = 5
MAX_RISK_NOTES = 6


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


def _dedupe_text(values: Any, limit: int = MAX_RISK_NOTES) -> list[str]:
    raw_values = values if isinstance(values, (list, tuple)) else [values]
    items = []
    seen = set()
    for item in raw_values:
        if isinstance(item, Mapping):
            text = _first_text(item.get("message"), item.get("summary"), item.get("reason"), item.get("label"))
        else:
            text = to_text(item)
        if text and text not in seen:
            seen.add(text)
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _ticker_base(value: Any) -> str:
    text = to_text(value).upper()
    return text.split(".")[0] if text else ""


def _source_from_state(state_map: Mapping[str, Any], live_packet: Mapping[str, Any]) -> dict:
    existing = as_mapping(state_map.get("command_center_limit_emotion_packet"))
    if existing:
        return {"payload": existing, "source_key": "command_center_limit_emotion_packet"}

    facts = as_mapping(state_map.get("a_share_professional_facts"))
    limit_emotion = as_mapping(facts.get("limit_emotion"))
    if limit_emotion:
        return {"payload": limit_emotion, "source_key": "a_share_professional_facts.limit_emotion"}

    facts_packet = as_mapping(state_map.get("command_center_facts_packet"))
    for item in as_list(facts_packet.get("items")):
        item_map = as_mapping(item)
        if item_map.get("key") == "limit_emotion":
            return {"payload": item_map, "source_key": "command_center_facts_packet.items.limit_emotion"}

    live_limit = as_mapping(as_mapping(live_packet.get("facts")).get("limit_emotion") or live_packet.get("limit_emotion"))
    if live_limit:
        return {"payload": live_limit, "source_key": "command_center_live_packet.limit_emotion"}

    return {"payload": {}, "source_key": ""}


def _status_from(payload: Mapping[str, Any]) -> str:
    raw_status = to_text(payload.get("status")).lower()
    if raw_status in {"ready", "ok", "completed", "success"}:
        return "ready"
    if raw_status in {"failed", "error", "failure"}:
        return "failed"
    if payload.get("available") is True or payload.get("boundary_available") or payload.get("records_available") or payload.get("concept_available"):
        return "ready"
    state = to_text(payload.get("state") or payload.get("capability_state")).lower()
    if state == "available":
        return "ready"
    if state in {"permission_denied", "disabled_this_session", "failed", "network_failed", "not_configured"}:
        return "failed"
    if payload:
        return "partial"
    return "waiting"


def _data_status(status: str, payload: Mapping[str, Any]) -> str:
    if status == "ready":
        return "ready"
    if status in {"partial", "failed"} and payload:
        return "cached" if payload.get("available") else "missing"
    return "missing"


def _normalize_record(item: Any) -> dict:
    payload = as_mapping(item)
    if not payload:
        return {}
    return {
        "date": _first_text(payload.get("日期"), payload.get("date"), payload.get("trade_date")),
        "type": _first_text(payload.get("类型"), payload.get("type"), payload.get("limit_type"), default="未知"),
        "first_time": _first_text(payload.get("首次封板"), payload.get("first_time")),
        "last_time": _first_text(payload.get("最后封板"), payload.get("last_time")),
        "open_times": _first_text(payload.get("开板次数"), payload.get("open_times")),
        "seal_amount_yi": to_number(payload.get("封单金额(亿)") or payload.get("fd_amount_yi")),
        "limit_amount_yi": to_number(payload.get("板上成交额(亿)") or payload.get("limit_amount_yi")),
        "up_stat": _first_text(payload.get("连板统计"), payload.get("up_stat")),
        "limit_times": _first_text(payload.get("连板数"), payload.get("limit_times")),
    }


def _normalize_records(value: Any) -> list[dict]:
    rows = []
    for item in as_list(value):
        row = _normalize_record(item)
        if row:
            rows.append(row)
        if len(rows) >= MAX_RECORDS:
            break
    return rows


def _normalize_concept(item: Any) -> dict:
    payload = as_mapping(item)
    if not payload:
        return {}
    return {
        "name": _first_text(payload.get("概念"), payload.get("name"), payload.get("ts_code"), default="概念"),
        "limit_up_count": _first_text(payload.get("涨停家数"), payload.get("up_nums")),
        "consecutive_count": _first_text(payload.get("连板家数"), payload.get("cons_nums")),
        "height": _first_text(payload.get("连板高度"), payload.get("up_stat")),
        "pct_chg": _first_text(payload.get("涨跌幅"), payload.get("pct_chg")),
        "rank": _first_text(payload.get("排名"), payload.get("rank")),
    }


def _normalize_concepts(value: Any) -> list[dict]:
    rows = []
    for item in as_list(value):
        row = _normalize_concept(item)
        if row:
            rows.append(row)
        if len(rows) >= MAX_CONCEPTS:
            break
    return rows


def _flag_state(records: list[dict], flags: Mapping[str, Any]) -> dict:
    joined = " ".join(_first_text(row.get("type"), row.get("up_stat"), row.get("limit_times")) for row in records)
    return {
        "has_limit_up": bool(flags.get("has_limit_up") or "涨停" in joined),
        "has_limit_down": bool(flags.get("has_limit_down") or "跌停" in joined),
        "has_break_limit": bool(flags.get("has_break_limit") or "炸" in joined),
        "has_consecutive_limit": bool(flags.get("has_consecutive_limit") or "连" in joined),
    }


def _emotion_state(
    status: str,
    distance_to_up_pct: int | float | None,
    records: list[dict],
    concepts: list[dict],
    flags: Mapping[str, Any],
) -> str:
    if status == "waiting":
        return "待刷新"
    if status == "failed":
        return "待验证"
    if distance_to_up_pct is not None and distance_to_up_pct <= 3:
        return "接近涨停/追高区"
    if flags.get("has_break_limit"):
        return "炸板风险待验证"
    if flags.get("has_limit_down"):
        return "跌停风险待验证"
    if flags.get("has_consecutive_limit"):
        return "连板热度待验证"
    if records or concepts:
        return "情绪线索可参考"
    return "待验证"


def _build_risk_notes(payload: Mapping[str, Any], status: str, emotion_state: str, records: list[dict]) -> list[str]:
    notes = []
    for key in ("message", "record_message", "warning", "error", "risk", "note"):
        text = to_text(payload.get(key))
        if text and text != "暂无可验证数据":
            notes.append(text)
    if status != "ready":
        notes.append("涨跌停/情绪不可用时，不能把缺失数据当成无追高风险。")
    if emotion_state == "接近涨停/追高区":
        notes.append("距离涨停较近时优先防追高，不能用情绪热度替代纪律条件。")
    if emotion_state == "炸板风险待验证":
        notes.append("出现炸板记录时，需要降低追高和加仓冲动。")
    if records:
        notes.append("涨跌停/炸板记录只是事件证据，不单独构成买入理由。")
    notes.append("页面打开不会自动请求 Tushare stk_limit/limit_list_d/limit_cpt_list；需要手动刷新后再验证。")
    return _dedupe_text(notes)


def build_command_center_limit_emotion_packet(
    state: Any = None,
    live_packet: Any = None,
    target: str = "",
) -> dict:
    state_map = as_mapping(state)
    live = as_mapping(live_packet)
    source = _source_from_state(state_map, live)
    payload = as_mapping(source.get("payload"))
    existing_target = _first_text(payload.get("target"), payload.get("ticker"), payload.get("ts_code"))
    if payload and target and existing_target and _ticker_base(existing_target) != _ticker_base(target):
        payload = {}

    status = _status_from(payload)
    records = _normalize_records(payload.get("limit_records") or payload.get("recent_limit_records"))
    concepts = _normalize_concepts(payload.get("concept_top5") or payload.get("concept_strength_top"))
    flags = _flag_state(records, as_mapping(payload.get("flags")))
    distance_to_up_pct = to_number(payload.get("distance_to_up_pct") or payload.get("distance_to_limit_up"))
    distance_to_down_pct = to_number(payload.get("distance_to_down_pct") or payload.get("distance_to_limit_down"))
    emotion_state = _emotion_state(status, distance_to_up_pct, records, concepts, flags)
    summary = _first_text(
        payload.get("summary"),
        payload.get("evidence"),
        payload.get("message"),
        default=(
            "涨跌停/情绪待刷新；页面打开不会自动请求 Tushare 涨跌停接口。"
            if status == "waiting"
            else f"涨跌停/情绪状态：{emotion_state}。"
        ),
    )
    return {
        "status": status,
        "data_status": _data_status(status, payload),
        "source": _first_text(payload.get("source"), default="Tushare 涨跌停/情绪缓存"),
        "source_key": to_text(source.get("source_key")),
        "api": _first_text(payload.get("api"), default="stk_limit / limit_list_d / limit_cpt_list"),
        "updated_at": _first_text(payload.get("updated_at"), payload.get("latest_date"), payload.get("concept_date")),
        "trade_date": _first_text(payload.get("latest_date"), payload.get("concept_date"), payload.get("date"), payload.get("trade_date")),
        "target": _first_text(target, existing_target),
        "ticker": _first_text(payload.get("ticker"), payload.get("ts_code"), target),
        "up_limit": to_number(payload.get("up_limit") or payload.get("limit_up_price")),
        "down_limit": to_number(payload.get("down_limit") or payload.get("limit_down_price")),
        "pre_close": to_number(payload.get("pre_close")),
        "current_price": to_number(payload.get("current_price")),
        "distance_to_up_pct": distance_to_up_pct,
        "distance_to_down_pct": distance_to_down_pct,
        "boundary_available": bool(payload.get("boundary_available")),
        "records_available": bool(payload.get("records_available") or records),
        "concept_available": bool(payload.get("concept_available") or concepts),
        "limit_records": records,
        "concept_top5": concepts,
        "flags": flags,
        "emotion_state": emotion_state,
        "summary": summary,
        "risk_notes": _build_risk_notes(payload, status, emotion_state, records),
        "manual_required_text": "涨跌停/情绪来自 Tushare stk_limit、limit_list_d、limit_cpt_list 缓存；缺失时必须手动刷新或权限校验，综合中心不会自动请求。",
        "deepseek_called": False,
    }
