from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_RECOMMENDED_ETFS = 3
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
        text = value.strip().replace(",", "").replace("%", "").replace("¥", "").replace("￥", "")
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


def _first_number(*values: Any) -> int | float | None:
    for value in values:
        number = to_number(value)
        if number is not None:
            return number
    return None


def _dedupe_text(values: Any, fallback: str = "", limit: int = MAX_RISK_NOTES) -> list[str]:
    items = []
    raw_values = values if isinstance(values, (list, tuple)) else [values]
    seen = set()
    for item in raw_values:
        if isinstance(item, Mapping):
            text = _first_text(item.get("message"), item.get("summary"), item.get("name"), item.get("warning"))
        else:
            text = to_text(item)
        if text and text not in seen:
            seen.add(text)
            items.append(text)
        if len(items) >= limit:
            break
    if not items and fallback:
        items.append(fallback)
    return items


def _candidate_rows(candidates: Any) -> list[dict]:
    rows = []
    if isinstance(candidates, Mapping):
        for bucket, items in candidates.items():
            for item in as_list(items):
                payload = as_mapping(item)
                if payload:
                    payload.setdefault("bucket", bucket)
                    rows.append(payload)
    else:
        rows = [as_mapping(item) for item in as_list(candidates)]
    return [row for row in rows if row]


def normalize_etf_candidate(row: Any = None, rank: int = 0, default_source: str = "融资 ETF 本地配置") -> dict:
    payload = as_mapping(row)
    return {
        "rank": rank,
        "code": _first_text(payload.get("etf_code"), payload.get("code"), payload.get("ts_code"), payload.get("symbol")),
        "name": _first_text(payload.get("etf_name"), payload.get("name"), payload.get("fund_name")),
        "bucket": _first_text(payload.get("bucket"), payload.get("theme"), payload.get("category"), default="ETF"),
        "score": _first_number(payload.get("total_score"), payload.get("score"), payload.get("composite_score")),
        "weight": _first_number(payload.get("weight"), payload.get("target_weight"), payload.get("allocation_ratio")),
        "action_state": _first_text(payload.get("action_state"), payload.get("advice"), payload.get("signal"), default="只观察不追"),
        "trigger_condition": _first_text(
            payload.get("trigger_condition"),
            payload.get("condition"),
            payload.get("reason"),
            default="等待回踩、量能和风险线确认。",
        ),
        "source": _first_text(payload.get("source"), default=default_source),
    }


def extract_recommended_etfs(allocation_result: Any = None, daily_packet: Any = None, limit: int = MAX_RECOMMENDED_ETFS) -> list[dict]:
    allocation = as_mapping(allocation_result)
    daily = as_mapping(daily_packet)
    candidates = (
        allocation.get("selected_etf_candidates")
        or allocation.get("recommended_etfs")
        or allocation.get("recommended_etf_allocation")
        or daily.get("selected_etf_candidates")
    )
    rows = _candidate_rows(candidates)
    if not rows:
        score_packet = as_mapping(daily.get("score_packet"))
        rows = _candidate_rows(score_packet.get("rows") or allocation.get("etf_score_table"))
    normalized = []
    seen = set()
    for row in rows:
        item = normalize_etf_candidate(row, rank=len(normalized) + 1)
        key = item.get("code") or item.get("name")
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(item)
        if len(normalized) >= int(limit or MAX_RECOMMENDED_ETFS):
            break
    return normalized


def _derive_main_direction(live_section: Mapping[str, Any], allocation: Mapping[str, Any], etfs: list[dict]) -> str:
    explicit = _first_text(
        live_section.get("today_main_direction"),
        allocation.get("today_main_direction"),
        allocation.get("main_direction"),
        allocation.get("style_tilt"),
    )
    if explicit:
        return explicit
    buckets = []
    seen = set()
    for item in etfs:
        bucket = to_text(item.get("bucket"))
        if bucket and bucket not in seen:
            seen.add(bucket)
            buckets.append(bucket)
    if buckets:
        return " / ".join(buckets[:3])
    return "待刷新"


def _derive_status(allocation: Mapping[str, Any], daily: Mapping[str, Any], live_section: Mapping[str, Any], etfs: list[dict]) -> str:
    if etfs:
        return "ready"
    if allocation or daily or live_section:
        return "partial"
    return "waiting"


def _derive_data_status(status: str, daily: Mapping[str, Any], etfs: list[dict]) -> str:
    if status == "waiting":
        return "missing"
    dataset = as_mapping(daily.get("daily_dataset"))
    text = _first_text(dataset.get("status"), daily.get("refresh_level"), daily.get("source"))
    if "manual_basic" in text or "本地" in text or "local" in text.lower():
        return "cached" if not etfs else "ready"
    return "ready" if etfs else "cached"


def _derive_risk_state(allocation: Mapping[str, Any], current_ratio: int | float | None, recommended_ratio: int | float | None, etfs: list[dict]) -> str:
    action_state = to_text(allocation.get("action_state"))
    if allocation.get("need_deleverage") or "降" in action_state:
        return "降杠杆"
    if not etfs:
        return "待刷新"
    if current_ratio is not None and recommended_ratio is not None and current_ratio > recommended_ratio:
        return "只观察，优先降融资暴露"
    if allocation.get("allow_margin_add"):
        return "可小幅配置"
    return _first_text(action_state, default="只观察不追")


def _build_risk_notes(allocation: Mapping[str, Any], daily: Mapping[str, Any], etfs: list[dict]) -> list[str]:
    notes = []
    for key in (
        "no_chase_warning",
        "risk_flags",
        "risk_lines",
        "must_reduce_risk_conditions",
        "holdings_data_gaps",
        "notes",
    ):
        notes.extend(_dedupe_text(allocation.get(key)))
    if not etfs:
        notes.append("暂无 ETF 配置快照；不触发全量 ETF 发现，等待手动刷新。")
    dataset = as_mapping(daily.get("daily_dataset"))
    note = to_text(dataset.get("note"))
    if note:
        notes.append(note)
    notes.append("DeepSeek 未调用；ETF 深度调研仍需手动按钮触发。")
    return _dedupe_text(notes, fallback="不追高 ETF；等待回踩、量能和风险线确认。")


def _watch_not_chase_items(allocation: Mapping[str, Any], etfs: list[dict]) -> list[str]:
    items = _dedupe_text(
        allocation.get("watch_not_chase") or allocation.get("watch_not_chase_etfs") or allocation.get("no_chase_warning"),
        limit=MAX_RECOMMENDED_ETFS,
    )
    if items:
        return items
    if etfs:
        return ["不追高 ETF；等待回踩、量能和风险线确认。"]
    return ["暂无 ETF 快照；不追高，等待刷新后再判断。"]


def build_command_center_etf_packet(
    state: Any = None,
    live_packet: Any = None,
    limit: int = MAX_RECOMMENDED_ETFS,
) -> dict:
    state_map = as_mapping(state)
    live = as_mapping(live_packet)
    live_section = as_mapping(live.get("margin_etf"))
    existing = as_mapping(state_map.get("command_center_etf_packet"))
    if existing.get("recommended_etfs") or existing.get("status") in {"ready", "partial"}:
        return {
            **existing,
            "recommended_etfs": [
                normalize_etf_candidate(item, rank=index + 1, default_source=to_text(existing.get("source"), "融资 ETF 本地配置"))
                for index, item in enumerate(as_list(existing.get("recommended_etfs"))[: int(limit or MAX_RECOMMENDED_ETFS)])
            ],
            "watch_not_chase": _dedupe_text(existing.get("watch_not_chase"), fallback="不追高 ETF；等待回踩、量能和风险线确认。", limit=MAX_RECOMMENDED_ETFS),
            "risk_notes": _dedupe_text(existing.get("risk_notes"), fallback="DeepSeek 未调用；ETF 深度调研仍需手动按钮触发。"),
            "deepseek_called": False,
        }
    allocation = as_mapping(state_map.get("legacy_margin_etf_allocation_result"))
    daily = as_mapping(state_map.get("legacy_margin_etf_daily_packet"))
    etfs = extract_recommended_etfs(allocation, daily, limit=limit)
    current_ratio = _first_number(
        live_section.get("current_margin_ratio"),
        live_section.get("current_margin_debt_ratio"),
        allocation.get("current_margin_debt_ratio"),
        state_map.get("current_margin_debt_ratio"),
        state_map.get("margin_current_margin_ratio"),
        state_map.get("margin_ratio"),
    )
    recommended_ratio = _first_number(live_section.get("recommended_margin_ratio"), allocation.get("recommended_margin_ratio"))
    recommended_cash_ratio = _first_number(live_section.get("recommended_cash_ratio"), allocation.get("recommended_cash_ratio"))
    status = _derive_status(allocation, daily, live_section, etfs)
    updated_at = _first_text(
        live_section.get("updated_at"),
        daily.get("updated_at"),
        allocation.get("generated_at"),
        allocation.get("updated_at"),
    )
    source = _first_text(live_section.get("source"), daily.get("source"), allocation.get("data_source"), default="融资 ETF 本地配置快照")
    return {
        "status": status,
        "source": source,
        "updated_at": updated_at,
        "current_margin_ratio": current_ratio,
        "recommended_margin_ratio": recommended_ratio,
        "recommended_cash_ratio": recommended_cash_ratio,
        "today_main_direction": _derive_main_direction(live_section, allocation, etfs),
        "recommended_etfs": etfs,
        "watch_not_chase": _watch_not_chase_items(allocation, etfs),
        "risk_state": _derive_risk_state(allocation, current_ratio, recommended_ratio, etfs),
        "risk_notes": _build_risk_notes(allocation, daily, etfs),
        "data_status": _derive_data_status(status, daily, etfs),
        "summary": _first_text(
            allocation.get("summary"),
            live_section.get("summary"),
            default=(
                "已读取融资 ETF 本地配置快照；深度行情、全量发现和同赛道比较仍需手动触发。"
                if status != "waiting"
                else "暂无 ETF 配置快照；点击刷新今日基础数据只生成本地配置快照，不自动全量发现。"
            ),
        ),
        "deepseek_called": False,
    }
