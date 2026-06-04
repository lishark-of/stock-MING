from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_legacy_packet_contract import build_legacy_packet_decision_contract


MAX_AREAS = 5
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


def _chip_source_from_state(state_map: Mapping[str, Any], live_packet: Mapping[str, Any]) -> dict:
    existing = as_mapping(state_map.get("command_center_chip_packet"))
    if existing:
        return {"payload": existing, "source_key": "command_center_chip_packet"}

    facts = as_mapping(state_map.get("a_share_professional_facts"))
    chip = as_mapping(facts.get("chip_radar"))
    if chip:
        return {"payload": chip, "source_key": "a_share_professional_facts.chip_radar"}

    facts_packet = as_mapping(state_map.get("command_center_facts_packet"))
    for item in as_list(facts_packet.get("items")):
        item_map = as_mapping(item)
        if item_map.get("key") == "chip_radar":
            return {"payload": item_map, "source_key": "command_center_facts_packet.items.chip_radar"}

    live_chip = as_mapping(as_mapping(live_packet.get("facts")).get("chip_radar") or as_mapping(live_packet.get("chip_radar")))
    if live_chip:
        return {"payload": live_chip, "source_key": "command_center_live_packet.chip_radar"}

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


def _normalize_top_areas(value: Any) -> list[dict]:
    rows = []
    for item in as_list(value):
        payload = as_mapping(item)
        if not payload:
            continue
        price = to_number(payload.get("price") or payload.get("cost") or payload.get("avg_cost"))
        percent = to_number(payload.get("percent") or payload.get("weight") or payload.get("ratio"))
        rows.append(
            {
                "price": price,
                "percent": percent,
                "label": _first_text(payload.get("label"), payload.get("price"), default="筹码区"),
            }
        )
        if len(rows) >= MAX_AREAS:
            break
    return rows


def _pressure_state(winner_rate: int | float | None, current_vs_weight_avg_pct: int | float | None, chip_band_width: int | float | None) -> str:
    if winner_rate is None and current_vs_weight_avg_pct is None and chip_band_width is None:
        return "待验证"
    if winner_rate is not None and winner_rate >= 70:
        return "获利盘压力偏高"
    if current_vs_weight_avg_pct is not None and current_vs_weight_avg_pct < -8:
        return "上方套牢盘压力"
    if chip_band_width is not None and chip_band_width >= 35:
        return "筹码分散"
    if chip_band_width is not None and chip_band_width <= 15:
        return "筹码相对收敛"
    return "中性待验证"


def _build_risk_notes(payload: Mapping[str, Any], status: str, pressure_state: str) -> list[str]:
    notes = []
    for key in ("message", "warning", "error", "risk", "note"):
        text = to_text(payload.get(key))
        if text and text != "暂无可验证数据":
            notes.append(text)
    if status != "ready":
        notes.append("暂未取得可验证筹码/胜率数据；不能写筹码压力或把缺失当成无风险。")
    if pressure_state == "获利盘压力偏高":
        notes.append("获利盘比例偏高时只提示兑现压力，不等于必须卖出。")
    if pressure_state == "上方套牢盘压力":
        notes.append("当前价低于筹码中枢时，需要结合量价确认突破有效性。")
    notes.append("筹码集中不是必涨；筹码/胜率只能作为压力位和纪律验证。")
    return _dedupe_text(notes)


def build_command_center_chip_packet(
    state: Any = None,
    live_packet: Any = None,
    target: str = "",
) -> dict:
    state_map = as_mapping(state)
    live = as_mapping(live_packet)
    source = _chip_source_from_state(state_map, live)
    payload = as_mapping(source.get("payload"))
    existing_target = _first_text(payload.get("target"), payload.get("ticker"), payload.get("ts_code"))
    if payload and target and existing_target and _ticker_base(existing_target) != _ticker_base(target):
        payload = {}

    status = _status_from(payload)
    data_status = _data_status(status, payload)
    capability_state = _capability_state(payload, status)
    status_label = _status_label(payload, capability_state, status)
    recovery_state = _recovery_state(status, capability_state, data_status)
    winner_rate = to_number(payload.get("winner_rate"))
    weight_avg = to_number(payload.get("weight_avg") or payload.get("avg_cost"))
    current_vs_weight_avg_pct = to_number(payload.get("current_vs_weight_avg_pct"))
    chip_band_width = to_number(payload.get("chip_band_width"))
    pressure_state = _pressure_state(winner_rate, current_vs_weight_avg_pct, chip_band_width)
    summary = _first_text(
        payload.get("summary"),
        payload.get("chip_pressure_comment"),
        payload.get("chip_structure_comment"),
        payload.get("message"),
        default=(
            "筹码/胜率待刷新；页面打开不会自动请求 Tushare cyq_perf/cyq_chips。"
            if status == "waiting"
            else "筹码/胜率只能作为压力位和纪律验证。"
        ),
    )
    packet = {
        "status": status,
        "data_status": data_status,
        "capability_state": capability_state,
        "status_label": status_label,
        "recovery_state": recovery_state,
        "source": _first_text(payload.get("source"), default="Tushare 筹码/胜率缓存"),
        "source_key": to_text(source.get("source_key")),
        "api": _first_text(payload.get("api"), default="cyq_perf/cyq_chips"),
        "updated_at": _first_text(payload.get("updated_at"), payload.get("checked_at"), payload.get("trade_date"), payload.get("date")),
        "checked_at": _first_text(payload.get("checked_at"), payload.get("updated_at")),
        "trade_date": _first_text(payload.get("trade_date"), payload.get("date"), payload.get("latest_date")),
        "target": _first_text(target, existing_target),
        "ticker": _first_text(payload.get("ticker"), payload.get("ts_code"), target),
        "winner_rate": winner_rate,
        "weight_avg": weight_avg,
        "cost_5pct": to_number(payload.get("cost_5pct")),
        "cost_50pct": to_number(payload.get("cost_50pct")),
        "cost_95pct": to_number(payload.get("cost_95pct")),
        "current_vs_weight_avg_pct": current_vs_weight_avg_pct,
        "chip_band_width": chip_band_width,
        "pressure_state": pressure_state,
        "chip_pressure_comment": _first_text(payload.get("chip_pressure_comment"), default=pressure_state),
        "chip_structure_comment": _first_text(payload.get("chip_structure_comment"), default="筹码结构待验证。"),
        "chips_top_areas": _normalize_top_areas(payload.get("chips_top_areas")),
        "summary": summary,
        "risk_notes": _build_risk_notes(payload, status, pressure_state),
        "manual_required_text": "筹码/胜率来自 Tushare cyq_perf/cyq_chips 缓存；缺失时必须手动刷新或权限校验，综合中心不会自动请求。",
        "deepseek_called": False,
    }
    packet.update(
        build_legacy_packet_decision_contract(
            payload,
            label="筹码/胜率",
            status=status,
            data_status=data_status,
            recovery_state=recovery_state,
            capability_state=capability_state,
        )
    )
    return packet
