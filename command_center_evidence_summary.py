from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


EVIDENCE_DEFS = (
    (
        "moneyflow_packet",
        "moneyflow",
        "个股资金流",
        "flow_state",
        ("five_day_main_net_yi", "main_net_yi"),
        "亿",
        1,
        "验证资金是否支持当前动作。",
    ),
    (
        "hard_risk_packet",
        "hard_risk",
        "硬风险/公告",
        "risk_state",
        ("risk_item_count",),
        "项",
        1,
        "排查公告、减持、质押、解禁等硬风险阻断。",
    ),
    (
        "margin_packet",
        "margin",
        "融资融券",
        "leverage_state",
        ("financing_buy_yi", "financing_balance_yi"),
        "亿",
        2,
        "观察杠杆变化和融资风险预算。",
    ),
    (
        "limit_emotion_packet",
        "limit_emotion",
        "涨跌停/情绪",
        "emotion_state",
        ("distance_to_up_pct", "up_limit"),
        "",
        2,
        "识别过热、追高和情绪边界。",
    ),
    (
        "dragon_tiger_packet",
        "dragon_tiger",
        "龙虎榜",
        "activity_state",
        ("net_buy_amount_yi",),
        "亿",
        3,
        "识别席位行为和短线情绪线索。",
    ),
    (
        "chip_packet",
        "chip_radar",
        "筹码/胜率",
        "pressure_state",
        ("winner_rate",),
        "%",
        3,
        "验证压力位、筹码结构和胜率口径。",
    ),
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


def _evidence_state(status: str, data_status: str) -> str:
    if status == "failed":
        return "blocked"
    if data_status == "ready":
        return "supporting"
    if data_status == "cached":
        return "cached"
    return "missing"


def _evidence_label(evidence_state: str) -> str:
    return {
        "supporting": "支持证据",
        "blocked": "阻断证据",
        "cached": "缓存证据",
        "missing": "缺失证据",
    }.get(evidence_state, "待验证证据")


def _decision_signal(label: str, headline: str, evidence_state: str) -> str:
    if evidence_state == "supporting":
        return f"{label}已刷新，可辅助验证：{headline}"
    if evidence_state == "blocked":
        return f"{label}失败/受限，不能支撑加仓或放大仓位。"
    if evidence_state == "cached":
        return f"{label}使用缓存，执行前必须复核日期和口径。"
    return f"{label}待验证，当前不进入核心决策依据。"


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
    priority: int = 3,
    decision_role: str = "",
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
    evidence_state = _evidence_state(status, data_status)
    return {
        "key": key,
        "label": label,
        "priority": priority,
        "decision_role": decision_role,
        "status": status,
        "data_status": data_status,
        "evidence_state": evidence_state,
        "evidence_label": _evidence_label(evidence_state),
        "status_label": _status_label(status, data_status),
        "tone": _status_tone(status, data_status),
        "headline": headline,
        "metric": _format_metric(key, metric, metric_suffix),
        "decision_signal": _decision_signal(label, headline, evidence_state),
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
            priority=priority,
            decision_role=decision_role,
        )
        for packet_key, key, label, headline_key, metric_keys, suffix, priority, decision_role in EVIDENCE_DEFS
    ]
    ready = [item for item in items if item["data_status"] == "ready"]
    cached = [item for item in items if item["data_status"] == "cached"]
    failed = [item for item in items if item["status"] == "failed"]
    missing = [item for item in items if item["data_status"] == "missing" and item["status"] != "failed"]
    support_items = [item for item in items if item["evidence_state"] == "supporting"]
    blocker_items = [item for item in items if item["evidence_state"] == "blocked"]
    cached_items = [item for item in items if item["evidence_state"] == "cached"]
    missing_items = [item for item in items if item["evidence_state"] == "missing"]
    decision_evidence_queue = sorted(
        items,
        key=lambda item: (
            item["priority"],
            {"blocked": 0, "missing": 1, "cached": 2, "supporting": 3}.get(item["evidence_state"], 4),
            item["label"],
        ),
    )
    summary = (
        f"已刷新 {len(ready)} 项｜使用缓存 {len(cached)} 项｜失败/受限 {len(failed)} 项｜待验证 {len(missing)} 项"
    )
    decision_summary = (
        f"支持 {len(support_items)}｜阻断 {len(blocker_items)}｜缓存 {len(cached_items)}｜缺失 {len(missing_items)}"
    )
    return {
        "title": "A股证据雷达",
        "summary": summary,
        "decision_summary": decision_summary,
        "items": items,
        "support_items": support_items,
        "blocker_items": blocker_items,
        "cached_items": cached_items,
        "missing_items": missing_items,
        "decision_evidence_queue": decision_evidence_queue,
        "ready_count": len(ready),
        "cached_count": len(cached),
        "failed_count": len(failed),
        "missing_count": len(missing),
        "manual_note": "证据雷达只读取本地 packet；页面打开不会自动请求 Tushare、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }
