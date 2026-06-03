from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


EVIDENCE_DEFS = (
    ("moneyflow_packet", "moneyflow", "个股资金流", "flow_state", ("five_day_main_net_yi", "main_net_yi"), "亿"),
    ("dragon_tiger_packet", "dragon_tiger", "龙虎榜", "activity_state", ("net_buy_amount_yi",), "亿"),
    ("margin_packet", "margin", "融资融券", "leverage_state", ("financing_buy_yi", "financing_balance_yi"), "亿"),
    ("limit_emotion_packet", "limit_emotion", "涨跌停/情绪", "emotion_state", ("distance_to_up_pct", "up_limit"), ""),
    ("hard_risk_packet", "hard_risk", "硬风险/公告", "risk_state", ("risk_item_count",), "项"),
    ("chip_packet", "chip_radar", "筹码/胜率", "pressure_state", ("winner_rate",), "%"),
)


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
        text = value.strip().replace(",", "").replace("%", "").replace("亿", "")
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


def _first_number(packet: Mapping[str, Any], keys: tuple[str, ...]) -> int | float | None:
    for key in keys:
        number = to_number(packet.get(key))
        if number is not None:
            return number
    return None


def _status_label(status: str, data_status: str) -> str:
    if status == "failed":
        return "失败/受限"
    if data_status == "ready":
        return "已刷新"
    if data_status == "cached":
        return "使用缓存"
    return "待验证"


def _status_tone(status: str, data_status: str) -> str:
    if status == "failed":
        return "failed"
    if data_status == "ready":
        return "ready"
    if data_status == "cached":
        return "stale"
    return "missing"


def _format_metric(key: str, value: int | float | None, suffix: str) -> str:
    if value is None:
        return "暂无数值"
    if key == "limit_emotion":
        if suffix:
            return f"{value:+.2f}{suffix}"
        return f"{value:.2f}"
    if suffix == "%":
        return f"{value:.2f}%"
    if suffix == "亿":
        return f"{value:+.2f}亿"
    if suffix == "项":
        return f"{int(value)}项" if float(value).is_integer() else f"{value}项"
    return f"{value}"


def _risk_text(packet: Mapping[str, Any]) -> str:
    notes = [to_text(item) for item in as_list(packet.get("risk_notes"))]
    notes = [item for item in notes if item]
    return notes[0] if notes else _first_text(packet.get("manual_required_text"), packet.get("summary"), default="待验证，不能单独作为交易依据。")


def build_evidence_item(
    packet: Any,
    *,
    key: str,
    label: str,
    headline_key: str,
    metric_keys: tuple[str, ...],
    metric_suffix: str = "",
) -> dict:
    payload = as_mapping(packet)
    status = to_text(payload.get("status"), "waiting")
    data_status = to_text(payload.get("data_status"), "missing")
    metric = _first_number(payload, metric_keys)
    headline = _first_text(
        payload.get(headline_key),
        payload.get("summary"),
        default="待验证" if data_status == "missing" else "已读取",
    )
    return {
        "key": key,
        "label": label,
        "status": status,
        "data_status": data_status,
        "status_label": _status_label(status, data_status),
        "tone": _status_tone(status, data_status),
        "headline": headline,
        "metric": _format_metric(key, metric, metric_suffix),
        "source": _first_text(payload.get("source"), payload.get("api"), default="本地缓存"),
        "updated_at": _first_text(payload.get("updated_at"), payload.get("trade_date"), default="暂无时间"),
        "risk_text": _risk_text(payload),
        "manual_required_text": _first_text(payload.get("manual_required_text"), default="缺失时需要手动刷新或权限校验。"),
        "deepseek_called": False,
    }


def build_a_share_evidence_radar_view_model(snapshot: Any = None) -> dict:
    payload = as_mapping(snapshot)
    items = [
        build_evidence_item(
            payload.get(packet_key),
            key=key,
            label=label,
            headline_key=headline_key,
            metric_keys=metric_keys,
            metric_suffix=suffix,
        )
        for packet_key, key, label, headline_key, metric_keys, suffix in EVIDENCE_DEFS
    ]
    ready = [item for item in items if item["data_status"] == "ready"]
    cached = [item for item in items if item["data_status"] == "cached"]
    failed = [item for item in items if item["status"] == "failed"]
    missing = [item for item in items if item["data_status"] == "missing" and item["status"] != "failed"]
    summary = (
        f"已刷新 {len(ready)} 项｜使用缓存 {len(cached)} 项｜失败/受限 {len(failed)} 项｜待验证 {len(missing)} 项"
    )
    return {
        "title": "A股证据雷达",
        "summary": summary,
        "items": items,
        "ready_count": len(ready),
        "cached_count": len(cached),
        "failed_count": len(failed),
        "missing_count": len(missing),
        "manual_note": "证据雷达只读取本地 packet；页面打开不会自动请求 Tushare、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }
