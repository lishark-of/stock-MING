from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_RISK_NOTES = 6


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


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
    existing = as_mapping(state_map.get("command_center_moneyflow_packet"))
    if existing:
        return {"payload": existing, "source_key": "command_center_moneyflow_packet"}

    facts = as_mapping(state_map.get("a_share_professional_facts"))
    moneyflow = as_mapping(facts.get("moneyflow"))
    if moneyflow:
        return {"payload": moneyflow, "source_key": "a_share_professional_facts.moneyflow"}

    facts_packet = as_mapping(state_map.get("command_center_facts_packet"))
    for item in facts_packet.get("items") or []:
        item_map = as_mapping(item)
        if item_map.get("key") == "moneyflow":
            return {"payload": item_map, "source_key": "command_center_facts_packet.items.moneyflow"}

    live_moneyflow = as_mapping(as_mapping(live_packet.get("facts")).get("moneyflow") or live_packet.get("moneyflow"))
    if live_moneyflow:
        return {"payload": live_moneyflow, "source_key": "command_center_live_packet.moneyflow"}

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


def _capability_state(payload: Mapping[str, Any], status: str) -> str:
    state = _first_text(payload.get("capability_state"), payload.get("state")).lower()
    if state:
        return state
    if status == "ready":
        return "available"
    if status == "failed":
        return "failed"
    if status == "partial":
        return "empty_recent"
    return "requires_manual_refresh"


def _status_label(payload: Mapping[str, Any], capability_state: str, status: str) -> str:
    explicit = _first_text(payload.get("status_label"), payload.get("capability_label"), payload.get("status"))
    if explicit and explicit.lower() not in {"ready", "ok", "completed", "success", "failed", "error", "partial", "waiting"}:
        return explicit
    return {
        "available": "可用",
        "permission_denied": "权限不足",
        "disabled_this_session": "本会话跳过",
        "empty_recent": "近期无数据",
        "stale_cache": "使用缓存",
        "fallback_used": "使用替代口径",
        "requires_manual_refresh": "需要手动刷新",
        "network_failed": "网络失败",
        "not_configured": "未配置",
        "failed": "调用失败",
    }.get(capability_state, {"ready": "可用", "failed": "调用失败", "partial": "待验证"}.get(status, "待刷新"))


def _recovery_state(status: str, capability_state: str, data_status: str) -> str:
    if status == "ready" or data_status in {"ready", "cached"}:
        return "recovered"
    if capability_state in {"permission_denied", "disabled_this_session", "network_failed", "not_configured", "failed"}:
        return "blocked"
    return "waiting"


def _flow_state(main_net_yi: int | float | None, five_day_main_net_yi: int | float | None, status: str) -> str:
    if status in {"waiting", "failed"} or (main_net_yi is None and five_day_main_net_yi is None):
        return "待验证"
    basis = five_day_main_net_yi if five_day_main_net_yi is not None else main_net_yi
    if basis > 0:
        return "主力净流入"
    if basis < 0:
        return "主力净流出"
    return "中性"


def _build_risk_notes(payload: Mapping[str, Any], status: str, flow_state: str) -> list[str]:
    notes = []
    for key in ("message", "warning", "error", "risk", "note"):
        text = to_text(payload.get(key))
        if text and text != "暂无可验证数据":
            notes.append(text)
    if status != "ready":
        notes.append("暂未取得可验证个股资金流；不能把缺失数据当成无资金风险。")
    if flow_state == "主力净流入":
        notes.append("资金净流入只作验证线索，不单独构成买入理由。")
    if flow_state == "主力净流出":
        notes.append("主力净流出需要优先复核价格纪律和减仓条件。")
    notes.append("页面打开不会自动请求 Tushare moneyflow；需要手动刷新后再验证。")
    return _dedupe_text(notes)


def build_command_center_moneyflow_packet(
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
    data_status = _data_status(status, payload)
    capability_state = _capability_state(payload, status)
    status_label = _status_label(payload, capability_state, status)
    recovery_state = _recovery_state(status, capability_state, data_status)
    main_net_yi = to_number(payload.get("main_net_yi") or payload.get("main_net_inflow_yi") or payload.get("net_mf_amount"))
    five_day_main_net_yi = to_number(payload.get("five_day_main_net_yi") or payload.get("five_day_main_net_inflow_yi"))
    flow_state = _flow_state(main_net_yi, five_day_main_net_yi, status)
    summary = _first_text(
        payload.get("summary"),
        payload.get("evidence"),
        payload.get("message"),
        default=(
            "个股资金流待刷新；页面打开不会自动请求 Tushare moneyflow。"
            if status == "waiting"
            else f"资金流状态：{flow_state}。"
        ),
    )
    return {
        "status": status,
        "data_status": data_status,
        "capability_state": capability_state,
        "status_label": status_label,
        "recovery_state": recovery_state,
        "source": _first_text(payload.get("source"), default="Tushare moneyflow 缓存"),
        "source_key": to_text(source.get("source_key")),
        "api": _first_text(payload.get("api"), default="moneyflow"),
        "updated_at": _first_text(payload.get("updated_at"), payload.get("checked_at"), payload.get("date"), payload.get("trade_date")),
        "checked_at": _first_text(payload.get("checked_at"), payload.get("updated_at")),
        "trade_date": _first_text(payload.get("date"), payload.get("trade_date"), payload.get("latest_date")),
        "target": _first_text(target, existing_target),
        "ticker": _first_text(payload.get("ticker"), payload.get("ts_code"), target),
        "main_net_yi": main_net_yi,
        "five_day_main_net_yi": five_day_main_net_yi,
        "large_net_yi": to_number(payload.get("large_net_yi") or payload.get("large_net_inflow_yi")),
        "medium_net_yi": to_number(payload.get("medium_net_yi") or payload.get("medium_net_inflow_yi")),
        "small_net_yi": to_number(payload.get("small_net_yi") or payload.get("small_net_inflow_yi")),
        "direction": _first_text(payload.get("direction"), default=flow_state),
        "flow_state": flow_state,
        "summary": summary,
        "risk_notes": _build_risk_notes(payload, status, flow_state),
        "manual_required_text": "个股资金流来自 Tushare moneyflow 缓存；缺失时必须手动刷新或权限校验，综合中心不会自动请求。",
        "deepseek_called": False,
    }
