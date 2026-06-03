from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_EVIDENCE = 6
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


def _status_from(payload: Mapping[str, Any], live_section: Mapping[str, Any]) -> str:
    raw_status = to_text(payload.get("status")).lower()
    if raw_status in {"completed", "ready", "ok", "success"}:
        return "ready"
    if raw_status in {"failed", "error", "failure"}:
        return "failed"
    if raw_status in {"running", "partial"}:
        return "partial"
    if payload:
        return "cached" if live_section.get("last_success") or live_section.get("stale") else "partial"
    if live_section:
        return "cached" if live_section.get("last_success") or live_section.get("stale") else "partial"
    return "waiting"


def _derive_data_status(status: str, payload: Mapping[str, Any], live_section: Mapping[str, Any]) -> str:
    if status == "ready":
        return "ready"
    if status in {"cached", "partial"} or payload or live_section.get("last_success"):
        return "cached"
    return "missing"


def _derive_action_state(score: int | float | None, direction: str, summary: str, status: str) -> str:
    blob = f"{direction} {summary}"
    low = blob.lower()
    if status in {"waiting", "failed"}:
        return "待刷新"
    if score is not None and score <= 50:
        return "防守观察"
    if any(token in blob for token in ("防守", "降风险", "偏弱", "风险")) or any(token in low for token in ("weak", "risk", "defensive")):
        return "防守观察"
    if score is not None and score >= 65:
        return "轻仓验证"
    if any(token in blob for token in ("偏积极", "可准备", "强", "进攻")):
        return "轻仓验证"
    if status in {"ready", "cached", "partial"}:
        return "只观察"
    return "待验证"


def _confidence_from(score: int | float | None, status: str, backtest_report: Mapping[str, Any]) -> str:
    if status in {"waiting", "failed"}:
        return "低"
    if score is None:
        return "低"
    has_backtest = bool(backtest_report)
    if score >= 70 and has_backtest:
        return "中"
    if score >= 60:
        return "中" if has_backtest else "低"
    return "低"


def _backtest_summary(report: Mapping[str, Any], target: str = "") -> str:
    if not report:
        return "未读取到回测缓存；综合中心不会自动跑回测。"
    report_target = _first_text(report.get("ticker"), target, default="当前标的")
    summary = _first_text(report.get("summary"), default="已读取回测缓存。")
    return f"{report_target} 回测缓存：{summary}"


def _build_evidence(payload: Mapping[str, Any], live_section: Mapping[str, Any], backtest_report: Mapping[str, Any]) -> list[str]:
    evidence = []
    score = to_number(payload.get("score") or live_section.get("score"))
    direction = _first_text(payload.get("direction"), payload.get("label"), live_section.get("direction"))
    market_type = _first_text(payload.get("market_type"), live_section.get("market_type"))
    if score is not None:
        evidence.append(f"量化分数：{score}")
    if direction:
        evidence.append(f"方向：{direction}")
    if market_type:
        evidence.append(f"市场类型：{market_type}")
    summary = _first_text(payload.get("summary"), live_section.get("summary"))
    if summary:
        evidence.append(summary)
    if backtest_report:
        evidence.append(_backtest_summary(backtest_report, target=payload.get("target")))
    return _dedupe_text(evidence, limit=MAX_EVIDENCE)


def _build_risk_notes(status: str, payload: Mapping[str, Any], live_section: Mapping[str, Any], backtest_report: Mapping[str, Any]) -> list[str]:
    notes = []
    for key in ("last_error", "error"):
        text = _first_text(payload.get(key), live_section.get(key))
        if text:
            notes.append(text)
    if not backtest_report:
        notes.append("缺少回测缓存；量化分数不能单独作为交易依据。")
    if status in {"waiting", "failed"}:
        notes.append("量化推演待刷新；当前不能假装已有完整单票诊断。")
    notes.append("旧版完整量化推演、回测和 DeepSeek 解释都必须手动触发。")
    return _dedupe_text(notes, limit=MAX_RISK_NOTES)


def _normalize_existing(existing: Mapping[str, Any]) -> dict:
    payload = dict(existing)
    status = _first_text(payload.get("status"), default="ready")
    score = to_number(payload.get("score"))
    direction = _first_text(payload.get("direction"), payload.get("label"))
    summary = _first_text(payload.get("summary"), default="量化 packet 已缓存。")
    payload.update(
        {
            "status": status,
            "score": score,
            "direction": direction,
            "summary": summary,
            "action_state": _first_text(payload.get("action_state"), default=_derive_action_state(score, direction, summary, status)),
            "confidence": _first_text(payload.get("confidence"), default=_confidence_from(score, status, {})),
            "evidence_items": _dedupe_text(payload.get("evidence_items")) or [summary],
            "risk_notes": _dedupe_text(payload.get("risk_notes")) or ["旧版完整量化推演、回测和 DeepSeek 解释都必须手动触发。"],
            "data_status": _first_text(payload.get("data_status"), default="ready" if status == "ready" else "cached"),
            "deepseek_called": False,
        }
    )
    return payload


def build_command_center_quant_packet(
    state: Any = None,
    live_packet: Any = None,
    target: str = "",
) -> dict:
    state_map = as_mapping(state)
    live = as_mapping(live_packet)
    live_section = as_mapping(live.get("quant"))
    existing = as_mapping(state_map.get("command_center_quant_packet"))
    existing_target = _first_text(existing.get("target"), existing.get("ticker"))
    if existing and not (target and existing_target and _ticker_base(existing_target) != _ticker_base(target)):
        return _normalize_existing(existing)

    payload = as_mapping(state_map.get("legacy_quant_result")) or live_section
    payload_target = _first_text(payload.get("target"), payload.get("ticker"), live_section.get("target"))
    if payload and target and payload_target and _ticker_base(payload_target) != _ticker_base(target):
        payload = {}

    backtest_report = as_mapping(state_map.get("last_backtest_report"))
    if backtest_report and target and backtest_report.get("ticker") and _ticker_base(backtest_report.get("ticker")) != _ticker_base(target):
        backtest_report = {}

    status = _status_from(payload, live_section)
    score = to_number(payload.get("score") or live_section.get("score"))
    direction = _first_text(payload.get("direction"), payload.get("label"), live_section.get("direction"), default="待验证")
    summary = _first_text(
        payload.get("summary"),
        live_section.get("summary"),
        default=(
            "暂无量化缓存；请手动生成量化推演或刷新今日基础数据。"
            if status == "waiting"
            else "量化摘要来自旧版缓存，完整推演仍需手动触发。"
        ),
    )
    action_state = _derive_action_state(score, direction, summary, status)
    evidence = _build_evidence(payload, live_section, backtest_report)
    risk_notes = _build_risk_notes(status, payload, live_section, backtest_report)
    return {
        "status": status,
        "source": _first_text(payload.get("source"), live_section.get("source"), default="量化推演缓存"),
        "updated_at": _first_text(payload.get("generated_at"), payload.get("updated_at"), live_section.get("updated_at")),
        "target": _first_text(target, payload_target),
        "ticker": _first_text(payload.get("ticker"), target),
        "market_type": _first_text(payload.get("market_type"), live_section.get("market_type")),
        "score": score,
        "direction": direction,
        "summary": summary,
        "action_state": action_state,
        "confidence": _confidence_from(score, status, backtest_report),
        "evidence_items": evidence or ["量化证据待刷新。"],
        "risk_notes": risk_notes,
        "backtest_reference": _backtest_summary(backtest_report, target=target),
        "data_status": _derive_data_status(status, payload, live_section),
        "manual_required_text": "完整量化推演、回测和 DeepSeek 解释必须在高级工具箱或按钮中手动触发。",
        "deepseek_called": False,
    }
