from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_ROWS = 8
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
    existing = as_mapping(state_map.get("command_center_dragon_tiger_packet"))
    if existing:
        return {"payload": existing, "source_key": "command_center_dragon_tiger_packet"}

    facts = as_mapping(state_map.get("a_share_professional_facts"))
    dragon = as_mapping(facts.get("dragon_tiger"))
    if dragon:
        return {"payload": dragon, "source_key": "a_share_professional_facts.dragon_tiger"}

    facts_packet = as_mapping(state_map.get("command_center_facts_packet"))
    for item in as_list(facts_packet.get("items")):
        item_map = as_mapping(item)
        if item_map.get("key") == "dragon_tiger":
            return {"payload": item_map, "source_key": "command_center_facts_packet.items.dragon_tiger"}

    live_dragon = as_mapping(as_mapping(live_packet.get("facts")).get("dragon_tiger") or live_packet.get("dragon_tiger"))
    if live_dragon:
        return {"payload": live_dragon, "source_key": "command_center_live_packet.dragon_tiger"}

    return {"payload": {}, "source_key": ""}


def _status_from(payload: Mapping[str, Any]) -> str:
    raw_status = to_text(payload.get("status")).lower()
    if raw_status in {"ready", "ok", "completed", "success"}:
        return "ready"
    if raw_status in {"failed", "error", "failure"}:
        return "failed"
    if payload.get("available") is True:
        return "ready"
    state = to_text(payload.get("state") or payload.get("capability_state")).lower()
    if state == "available":
        return "ready"
    if state in {"permission_denied", "disabled_this_session", "failed", "network_failed"}:
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


def _normalize_rows(value: Any) -> list[dict]:
    rows = []
    for item in as_list(value):
        payload = as_mapping(item)
        if not payload:
            continue
        rows.append(
            {
                "name": _first_text(payload.get("name"), payload.get("exalter"), payload.get("营业部名称"), default="席位"),
                "buy": to_number(payload.get("buy")),
                "sell": to_number(payload.get("sell")),
                "net_buy": to_number(payload.get("net_buy") or payload.get("net_amount")),
            }
        )
        if len(rows) >= MAX_ROWS:
            break
    return rows


def _activity_state(status: str, net_buy_amount_yi: int | float | None, inst_rows: list[dict]) -> str:
    if status == "waiting":
        return "待验证"
    if status != "ready":
        return "近期无上榜或不可用"
    if net_buy_amount_yi is not None:
        if net_buy_amount_yi > 0:
            return "席位净买入"
        if net_buy_amount_yi < 0:
            return "席位净卖出"
    if inst_rows:
        return "有席位明细"
    return "已上榜待复核"


def _build_risk_notes(payload: Mapping[str, Any], status: str, activity_state: str) -> list[str]:
    notes = []
    for key in ("message", "warning", "error", "risk", "note"):
        text = to_text(payload.get(key))
        if text and text != "暂无可验证数据":
            notes.append(text)
    if status != "ready":
        notes.append("近期无龙虎榜记录只说明没有可验证上榜事件，不等于机构支持或无风险。")
    if activity_state == "席位净买入":
        notes.append("龙虎榜净买入只作席位行为线索，不单独构成买入理由。")
    if activity_state == "席位净卖出":
        notes.append("龙虎榜净卖出需要结合资金流、价格纪律和风险预算复核。")
    notes.append("页面打开不会自动请求 Tushare top_list/top_inst；需要手动刷新后再验证。")
    return _dedupe_text(notes)


def build_command_center_dragon_tiger_packet(
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
    net_buy_amount_yi = to_number(payload.get("net_buy_amount_yi") or payload.get("net_buy_amount") or payload.get("net_buy"))
    inst_rows = _normalize_rows(payload.get("inst_rows"))
    activity_state = _activity_state(status, net_buy_amount_yi, inst_rows)
    summary = _first_text(
        payload.get("summary"),
        payload.get("inst_summary"),
        payload.get("message"),
        default=(
            "龙虎榜待刷新；页面打开不会自动请求 Tushare top_list/top_inst。"
            if status == "waiting"
            else f"龙虎榜状态：{activity_state}。"
        ),
    )
    return {
        "status": status,
        "data_status": _data_status(status, payload),
        "source": _first_text(payload.get("source"), default="Tushare 龙虎榜缓存"),
        "source_key": to_text(source.get("source_key")),
        "api": _first_text(payload.get("api"), default="top_list/top_inst"),
        "updated_at": _first_text(payload.get("updated_at"), payload.get("latest_date"), payload.get("trade_date")),
        "trade_date": _first_text(payload.get("latest_date"), payload.get("trade_date"), payload.get("date")),
        "target": _first_text(target, existing_target),
        "ticker": _first_text(payload.get("ticker"), payload.get("ts_code"), target),
        "reason": to_text(payload.get("reason")),
        "close": to_number(payload.get("close")),
        "pct_change": to_number(payload.get("pct_change")),
        "buy_amount_yi": to_number(payload.get("buy_amount_yi") or payload.get("buy_amount")),
        "sell_amount_yi": to_number(payload.get("sell_amount_yi") or payload.get("sell_amount")),
        "net_buy_amount_yi": net_buy_amount_yi,
        "inst_summary": to_text(payload.get("inst_summary")),
        "inst_rows": inst_rows,
        "raw_rows": [as_mapping(item) for item in as_list(payload.get("raw_rows"))[:MAX_ROWS]],
        "activity_state": activity_state,
        "summary": summary,
        "risk_notes": _build_risk_notes(payload, status, activity_state),
        "manual_required_text": "龙虎榜来自 Tushare top_list/top_inst 缓存；缺失时必须手动刷新或权限校验，综合中心不会自动请求。",
        "deepseek_called": False,
    }
