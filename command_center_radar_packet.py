from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_TOP_CANDIDATES = 3


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


def _first_list(*values: Any) -> list:
    for value in values:
        rows = as_list(value)
        if rows:
            return rows
    return []


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = to_text(value)
        if text:
            return text
    return default


def _conditions_text(values: Any, fallback: str) -> str:
    items = [to_text(item) for item in as_list(values)]
    items = [item for item in items if item]
    return "；".join(items[:3]) if items else fallback


def normalize_radar_candidate(row: Any = None, scan_packet: Any = None, live_section: Any = None, rank: int = 0) -> dict:
    row_map = as_mapping(row)
    scan = as_mapping(scan_packet)
    live = as_mapping(live_section)
    candidate = as_mapping(row_map.get("candidate")) or row_map
    score = as_mapping(row_map.get("score")) or row_map
    context = as_mapping(row_map.get("candidate_context"))
    trigger_conditions = _first_list(
        score.get("trigger_conditions"),
        row_map.get("trigger_conditions"),
        candidate.get("trigger_conditions"),
    )
    invalidation_conditions = _first_list(
        score.get("invalid_conditions"),
        score.get("invalidation_conditions"),
        row_map.get("invalid_conditions"),
        row_map.get("invalidation_conditions"),
        candidate.get("invalid_conditions"),
    )
    ticker = _first_text(candidate.get("ticker"), score.get("ticker"), row_map.get("ticker"))
    name = _first_text(candidate.get("name"), score.get("name"), row_map.get("name"))
    action_state = _first_text(
        score.get("battle_state"),
        row_map.get("battle_state"),
        row_map.get("action_state"),
        candidate.get("action_state"),
        default="只观察",
    )
    trigger_text = _conditions_text(
        trigger_conditions,
        _first_text(score.get("trigger_condition"), row_map.get("trigger_condition"), score.get("one_sentence_conclusion"), row_map.get("summary"), default="等待规则雷达触发条件确认。"),
    )
    invalidation_text = _conditions_text(
        invalidation_conditions,
        _first_text(score.get("invalidation_condition"), row_map.get("invalidation_condition"), score.get("fail_condition"), default="市场转弱、候选评分下降或纪律信号反向时失效。"),
    )
    data_gaps = _first_list(
        context.get("data_gaps"),
        as_mapping(score.get("score_notes")).get("data_gaps"),
        row_map.get("data_gaps"),
    )
    return {
        "rank": rank,
        "ticker": ticker,
        "name": name,
        "action_state": action_state,
        "score": to_number(score.get("total_score") or score.get("score") or row_map.get("score")),
        "trigger_conditions": trigger_conditions[:5],
        "trigger_condition": trigger_text,
        "invalidation_conditions": invalidation_conditions[:5],
        "invalidation_condition": invalidation_text,
        "reason": _first_text(score.get("battle_state_reason"), row_map.get("reason"), score.get("one_sentence_conclusion"), default="规则雷达缓存候选。"),
        "data_gaps": [to_text(item) for item in data_gaps if to_text(item)][:5],
        "source": _first_text(row_map.get("source"), row_map.get("scan_source"), context.get("scan_source"), scan.get("source"), live.get("source"), default="下一票雷达缓存"),
        "updated_at": _first_text(row_map.get("updated_at"), row_map.get("generated_at"), scan.get("generated_at"), live.get("updated_at"), default="暂无"),
        "deepseek_called": False,
    }


def _packet_status(scan_packet: Mapping[str, Any], rows: list, errors: list, status_raw: str) -> str:
    if status_raw == "failed":
        return "failed"
    if status_raw == "partial_failed" or errors:
        return "partial"
    if rows:
        return "ready"
    if scan_packet:
        return "waiting"
    return "waiting"


def build_command_center_radar_packet(
    state: Any = None,
    live_packet: Any = None,
    limit: int = MAX_TOP_CANDIDATES,
) -> dict:
    state_map = as_mapping(state)
    live = as_mapping(live_packet)
    live_section = as_mapping(live.get("next_ticket"))
    existing = as_mapping(state_map.get("command_center_radar_packet"))
    if existing.get("top_candidates"):
        return {**existing, "deepseek_called": bool(existing.get("deepseek_called", False))}
    scan_packet = as_mapping(state_map.get("radar_scan_results"))
    summary = as_mapping(state_map.get("radar_scan_summary") or scan_packet.get("summary"))
    rows = _first_list(
        live_section.get("top_candidates"),
        scan_packet.get("rule_rows"),
        scan_packet.get("results"),
    )
    errors = _first_list(state_map.get("radar_scan_errors"), summary.get("errors"), scan_packet.get("errors"))
    status_raw = to_text(state_map.get("radar_scan_status") or scan_packet.get("status"))
    top_candidates = []
    seen = set()
    for row in rows:
        candidate = normalize_radar_candidate(row, scan_packet=scan_packet, live_section=live_section, rank=len(top_candidates) + 1)
        key = candidate.get("ticker") or candidate.get("name")
        if not key or key in seen:
            continue
        seen.add(key)
        top_candidates.append(candidate)
        if len(top_candidates) >= int(limit or MAX_TOP_CANDIDATES):
            break
    status = _packet_status(scan_packet, rows, errors, status_raw)
    generated_at = _first_text(
        scan_packet.get("generated_at"),
        state_map.get("radar_scan_finished_at"),
        live_section.get("updated_at"),
        default="",
    )
    total_count = len(rows)
    return {
        "status": status,
        "source": _first_text(summary.get("source_mode"), scan_packet.get("source_mode"), live_section.get("source"), default="下一票雷达缓存"),
        "generated_at": generated_at,
        "total_count": total_count,
        "display_count": len(top_candidates),
        "top_candidates": top_candidates,
        "summary": _first_text(
            summary.get("note"),
            summary.get("summary"),
            default=(
                f"规则雷达缓存 {total_count} 条，首页展示 Top {len(top_candidates)}。"
                if rows
                else "暂无下一票雷达缓存；点击刷新今日基础数据不会自动全市场扫描。"
            ),
        ),
        "errors": [to_text(item) for item in errors if to_text(item)][:8],
        "data_status": "ready" if top_candidates else "missing",
        "deepseek_called": bool(summary.get("deepseek_called", False)),
    }
