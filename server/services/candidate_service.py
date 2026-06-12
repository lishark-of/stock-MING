from __future__ import annotations

import datetime as _dt
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore
from server.services import packet_service, task_service


PACKET_KEY = "command_center_3_candidate_radar_cache"
SCHEMA_VERSION = "candidate_radar_cache.v1"
SQLITE_META_PATH = Path(__file__).resolve().parents[2] / ".stock_ming_3" / "meta.sqlite"
SENSITIVE_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password", "passwd", "credential", "authorization")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")
LEGACY_RADAR_SIGNAL_GROUPS = [
    {
        "group": "radar_packet",
        "source_keys": ["radar_packet", "command_center_radar_packet"],
        "role": "legacy ranking packet and top candidate cache",
    },
    {
        "group": "next_ticket_candidates",
        "source_keys": ["next_ticket_candidates"],
        "role": "legacy executable candidate rows",
    },
    {
        "group": "candidate_execution_evidence_overview",
        "source_keys": ["candidate_execution_evidence_overview"],
        "role": "candidate evidence and execution readiness summary",
    },
    {
        "group": "next_ticket_evidence_recovery_actions",
        "source_keys": ["next_ticket_evidence_recovery_actions"],
        "role": "manual evidence recovery actions",
    },
    {
        "group": "old_workspace_packet_bridge",
        "source_keys": ["old_workspace_packet_bridge"],
        "role": "legacy packet bridge for parity checks",
    },
    {
        "group": "risk_alerts",
        "source_keys": ["risk_alerts"],
        "role": "candidate-level risk warnings and guardrails",
    },
]
LEGACY_RADAR_PARITY_ITEMS = [
    {
        "key": "top_watch_excluded_split",
        "label": "Top / Watch / Excluded 分层",
        "legacy_sources": ["command_center_radar_packet.top_candidates", "watch_candidates", "excluded_candidates"],
        "current_fields": ["candidate_rows", "excluded_candidates"],
        "target_state": "top/watch/excluded all mapped or missing_reported",
        "current_support": "mapped_from_cache",
    },
    {
        "key": "evidence_links",
        "label": "四类证据链",
        "legacy_sources": ["moneyflow", "dragon_tiger", "limit_emotion", "hard_risk"],
        "current_fields": ["evidence_chain_summary", "candidate_execution_evidence_overview", "evidence_recovery_actions"],
        "target_state": "moneyflow/dragon-tiger/limit-emotion/hard-risk gaps are visible",
        "current_support": "gap_reported",
    },
    {
        "key": "scoring_dimensions",
        "label": "规则评分维度",
        "legacy_sources": ["trend_score", "money_score", "risk_score", "position_score", "information_score", "total_score"],
        "current_fields": ["score"],
        "target_state": "dimension scores preserved when present; missing dimensions are not invented",
        "current_support": "partial_cache_projection",
    },
    {
        "key": "trigger_invalidation",
        "label": "触发 / 失效条件",
        "legacy_sources": ["trigger_conditions", "invalid_conditions", "trigger_condition", "invalidation_condition"],
        "current_fields": ["trigger_condition", "invalidation_condition"],
        "target_state": "candidate rows keep trigger/invalidation text before action review",
        "current_support": "mapped_from_cache",
    },
    {
        "key": "holding_comparison",
        "label": "当前持仓对比",
        "legacy_sources": ["current_holding_context", "position_profile", "candidate_vs_holding_*", "switch_relation"],
        "current_fields": ["position_risk_budget", "holding_action", "position_context"],
        "target_state": "candidate-vs-holding comparison becomes explicit before replacing legacy fallback",
        "current_support": "missing_reported",
    },
    {
        "key": "candidate_pool_sources",
        "label": "候选池来源",
        "legacy_sources": ["manual_input", "TECH_SAMPLE_POOL", "watchlist", "A-share broad scan", "index pool", "mixed scan"],
        "current_fields": ["radar_packet.source", "candidate_rows.source"],
        "target_state": "quick/watchlist/custom/full-pool modes report universe and degraded mode",
        "current_support": "quick_cache_only",
    },
    {
        "key": "scan_filters",
        "label": "扫描过滤条件",
        "legacy_sources": ["exclude_st", "exclude_chinext", "exclude_star", "exclude_bj", "exclude_low_amount", "trend_up_only"],
        "current_fields": ["scan_coverage.skipped_reason_rows"],
        "target_state": "filters become task params and skipped_reason_rows before broad scan",
        "current_support": "future_task_required",
    },
    {
        "key": "timeout_and_fallback",
        "label": "超时 / 上次成功缓存回退",
        "legacy_sources": ["timeout_seconds", "previous_rows", "radar_scan_status"],
        "current_fields": ["sqlite_meta persisted packet", "task status"],
        "target_state": "last successful packet remains visible while new scan runs or fails",
        "current_support": "mapped_from_sqlite_cache",
    },
    {
        "key": "manual_deep_research",
        "label": "手动深度研究",
        "legacy_sources": ["call_deepseek_non_stream", "deep_research_results"],
        "current_fields": ["future manual DeepSeek task"],
        "target_state": "DeepSeek remains manual/button-gated and does not feed radar action",
        "current_support": "not_in_quick_scan",
    },
]
LEGACY_RADAR_OUTPUT_CONTRACT_FIELDS = [
    {"field": "status", "role": "radar packet state", "required_for": "cache display"},
    {"field": "source", "role": "candidate source label", "required_for": "coverage audit"},
    {"field": "generated_at", "role": "last successful packet timestamp", "required_for": "cache freshness"},
    {"field": "total_count", "role": "legacy scanned/result count", "required_for": "universe coverage"},
    {"field": "top_candidates", "role": "primary Top candidates", "required_for": "next-ticket display"},
    {"field": "watch_candidates", "role": "observe-only candidates", "required_for": "non-actionable visibility"},
    {"field": "excluded_candidates", "role": "blocked/excluded candidates", "required_for": "feature parity"},
    {"field": "decision_summary", "role": "execution-layer summary", "required_for": "manual review"},
    {"field": "evidence_items", "role": "score/status/trigger/invalid/data-gap evidence cards", "required_for": "audit"},
    {"field": "trigger_condition", "role": "candidate trigger text", "required_for": "no blind action"},
    {"field": "invalidation_condition", "role": "candidate invalidation text", "required_for": "risk boundary"},
    {"field": "data_gaps", "role": "missing evidence list", "required_for": "coverage gaps"},
]
SCAN_MODE_STATUS_ROWS = [
    {
        "scan_mode": "quick_cache_scan",
        "status": "implemented_cache_only",
        "scope": "local snapshot/cache candidate packet",
        "external_calls": False,
        "notes": "Current 3.0 button task writes SQLite packet and reports coverage gaps.",
    },
    {
        "scan_mode": "watchlist_scan",
        "status": "planned_future_task",
        "scope": "legacy 持续调查池 / watchlist",
        "external_calls": False,
        "notes": "Must preserve watchlist source counts before enabling.",
    },
    {
        "scan_mode": "custom_pool_scan",
        "status": "planned_future_task",
        "scope": "manual/custom candidate pool",
        "external_calls": False,
        "notes": "Must preserve manual candidate parsing and duplicate handling.",
    },
    {
        "scan_mode": "full_pool_scan",
        "status": "planned_future_task",
        "scope": "A-share broad/index pool scan",
        "external_calls": "button_gated_future",
        "notes": "Must move slow provider refreshes behind explicit POST tasks, never render.",
    },
    {
        "scan_mode": "manual_deep_research",
        "status": "planned_manual_only",
        "scope": "DeepSeek explanation for selected candidate",
        "external_calls": "button_gated_future",
        "notes": "Not part of quick scan; output must remain research-only.",
    },
]


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _is_sensitive_key(key: Any) -> bool:
    lower = str(key or "").lower()
    return any(part in lower for part in SENSITIVE_KEY_PARTS)


def _safe_text(value: Any, *, limit: int = 1000) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in SENSITIVE_TEXT_MARKERS):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            _safe_text(key, limit=80): _safe_value(val, depth=depth + 1)
            for key, val in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_safe_value(item, depth=depth + 1) for item in value[:40]]
    if isinstance(value, tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:40]]
    return _safe_text(value)


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "candidate_radar_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _snapshot_fingerprint(snapshot_map: Mapping[str, Any]) -> str:
    serialized = json.dumps(snapshot_map, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _first_present_key(snapshot_map: Mapping[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = snapshot_map.get(key)
        if value not in (None, {}, []):
            return key
    return ""


def _source_group_rows(snapshot_map: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for spec in LEGACY_RADAR_SIGNAL_GROUPS:
        source_keys = [str(item) for item in spec["source_keys"]]
        present_key = _first_present_key(snapshot_map, source_keys)
        rows.append(
            {
                "group": spec["group"],
                "source_keys": source_keys,
                "present": bool(present_key),
                "source_key_used": present_key,
                "role": spec["role"],
                "migration_status": "mapped" if present_key else "missing_reported",
                "does_not_silently_drop": True,
            }
        )
    return rows


def _candidate_rows(candidates: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, raw in enumerate(_as_list(candidates), start=1):
        item = _as_dict(raw)
        if not item:
            continue
        rows.append(
            {
                "rank": item.get("rank") or idx,
                "ticker": item.get("ticker"),
                "name": item.get("name"),
                "score": item.get("score"),
                "status_label": item.get("status_label"),
                "action_state": item.get("action_state"),
                "tone": item.get("tone"),
                "evidence_chain_summary": item.get("evidence_chain_summary"),
                "trigger_condition": item.get("trigger_condition"),
                "invalidation_condition": item.get("invalidation_condition"),
                "source": item.get("source"),
                "updated_at": item.get("updated_at"),
            }
        )
    return rows


def _candidate_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ready = sum(1 for item in rows if str(item.get("action_state") or "").strip() in {"可准备", "作战准备"})
    observe = sum(1 for item in rows if "观察" in str(item.get("action_state") or item.get("status_label") or ""))
    verify = sum(1 for item in rows if "验证" in str(item.get("action_state") or item.get("status_label") or item.get("tone") or ""))
    return {
        "candidate_count": len(rows),
        "ready_count": ready,
        "observe_count": observe,
        "verify_count": verify,
    }


def _has_any_candidate_field(candidate_rows: list[dict[str, Any]], fields: list[str]) -> bool:
    for row in candidate_rows:
        for field in fields:
            if row.get(field) not in (None, "", [], {}):
                return True
    return False


def _has_any_packet_field(packet: Mapping[str, Any], fields: list[str]) -> bool:
    for field in fields:
        value = packet.get(field)
        if value not in (None, "", [], {}):
            return True
    return False


def _legacy_parity_rows(
    *,
    snapshot_map: Mapping[str, Any],
    radar_packet: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    excluded_candidates: list[Any],
    evidence_recovery_actions: list[Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_group_map = {row["group"]: row for row in _source_group_rows(snapshot_map)}
    for item in LEGACY_RADAR_PARITY_ITEMS:
        key = str(item["key"])
        support = str(item["current_support"])
        present = False
        status = support
        if key == "top_watch_excluded_split":
            present = bool(candidate_rows or excluded_candidates)
            status = "mapped" if present else "missing_reported"
        elif key == "evidence_links":
            present = bool(_has_any_candidate_field(candidate_rows, ["evidence_chain_summary"]) or evidence_recovery_actions)
            status = "mapped_or_gap_reported" if present else "missing_reported"
        elif key == "scoring_dimensions":
            present = bool(_has_any_candidate_field(candidate_rows, ["score"]))
            status = "partial_mapped" if present else "missing_reported"
        elif key == "trigger_invalidation":
            present = bool(_has_any_candidate_field(candidate_rows, ["trigger_condition", "invalidation_condition"]))
            status = "mapped" if present else "missing_reported"
        elif key == "holding_comparison":
            present = any(
                snapshot_map.get(source_key) not in (None, "", [], {})
                for source_key in ("position_risk_budget", "holding_action", "position_context", "current_holding_context")
            )
            status = "partial_mapped" if present else "missing_reported"
        elif key == "candidate_pool_sources":
            present = bool(radar_packet.get("source") or _has_any_candidate_field(candidate_rows, ["source"]))
            status = "quick_cache_only" if present else "missing_reported"
        elif key == "scan_filters":
            present = False
            status = "future_task_required"
        elif key == "timeout_and_fallback":
            present = bool(radar_packet or candidate_rows)
            status = "mapped_from_cache" if present else "missing_reported"
        elif key == "manual_deep_research":
            present = False
            status = "manual_only_future_task"

        source_group = source_group_map.get("radar_packet") if key in {"top_watch_excluded_split", "timeout_and_fallback"} else None
        rows.append(
            {
                "key": key,
                "label": item["label"],
                "legacy_sources": item["legacy_sources"],
                "current_fields": item["current_fields"],
                "present_in_current_cache": present,
                "migration_status": status,
                "target_state": item["target_state"],
                "source_key_used": source_group.get("source_key_used") if source_group else "",
                "does_not_call_external_sources": True,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _legacy_output_contract_rows(
    *,
    radar_packet: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    excluded_candidates: list[Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in LEGACY_RADAR_OUTPUT_CONTRACT_FIELDS:
        field = str(item["field"])
        if field == "top_candidates":
            present = bool(candidate_rows)
            source = "candidate_rows/radar_packet.top_candidates"
        elif field == "excluded_candidates":
            present = bool(excluded_candidates)
            source = "radar_packet.excluded_candidates"
        elif field == "watch_candidates":
            present = bool(_as_list(radar_packet.get("watch_candidates")))
            source = "radar_packet.watch_candidates"
        elif field in {"trigger_condition", "invalidation_condition", "data_gaps"}:
            present = _has_any_candidate_field(candidate_rows, [field])
            source = "candidate_rows"
        elif field == "evidence_items":
            present = _has_any_candidate_field(candidate_rows, ["evidence_chain_summary"])
            source = "candidate_rows.evidence_chain_summary"
        else:
            present = _has_any_packet_field(radar_packet, [field])
            source = "radar_packet"
        rows.append(
            {
                "field": field,
                "role": item["role"],
                "required_for": item["required_for"],
                "present": bool(present),
                "source": source,
                "migration_status": "mapped" if present else "missing_reported",
                "does_not_invent_value": True,
            }
        )
    return rows


def _legacy_parity_inventory(
    *,
    snapshot_map: Mapping[str, Any],
    radar_packet: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    excluded_candidates: list[Any],
    evidence_recovery_actions: list[Any],
) -> dict[str, Any]:
    parity_rows = _legacy_parity_rows(
        snapshot_map=snapshot_map,
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        evidence_recovery_actions=evidence_recovery_actions,
    )
    output_rows = _legacy_output_contract_rows(
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
    )
    mapped = [row for row in parity_rows if str(row.get("migration_status")) in {"mapped", "mapped_or_gap_reported", "partial_mapped", "mapped_from_cache", "quick_cache_only"}]
    gaps = [row for row in parity_rows if "missing" in str(row.get("migration_status")) or "future" in str(row.get("migration_status"))]
    return {
        "status": "partial_parity",
        "scope": "legacy_next_ticket_radar_inventory",
        "legacy_module_files": ["next_stock_radar.py", "command_center_radar_packet.py", "app.py"],
        "parity_row_count": len(parity_rows),
        "mapped_or_partial_count": len(mapped),
        "gap_or_future_count": len(gaps),
        "output_contract_field_count": len(output_rows),
        "output_contract_mapped_count": sum(1 for row in output_rows if row["present"]),
        "quick_scan_is_full_replacement": False,
        "slow_paths_are_future_button_tasks": True,
        "deep_research_is_manual_only_future": True,
        "does_not_call_tushare": True,
        "does_not_call_deepseek": True,
        "does_not_call_github": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _candidate_call_ledger_row(
    *,
    api: str,
    source_snapshot: str,
    row_count: int,
    call_status: str,
    request_params_safe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "api": api,
        "source_snapshot": source_snapshot,
        "request_params_safe": request_params_safe or {},
        "row_count": int(row_count),
        "data_date": None,
        "local_fetched_at": _now_iso(),
        "call_status": call_status,
        "error_message_safe": "",
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _candidate_freshness_state(snapshot_map: Mapping[str, Any]) -> dict[str, Any]:
    data_freshness = _as_dict(snapshot_map.get("data_freshness"))
    source = "data_freshness" if data_freshness else "missing"
    state = (
        data_freshness.get("state")
        or data_freshness.get("status")
        or data_freshness.get("freshness_status")
        or "unknown"
    )
    return {
        "source": source,
        "state": state,
        "expected_trade_date": data_freshness.get("expected_trade_date")
        or data_freshness.get("expected_data_date")
        or data_freshness.get("expected_date"),
        "data_date": data_freshness.get("data_date") or data_freshness.get("trade_date"),
        "last_updated": data_freshness.get("last_updated") or data_freshness.get("updated_at"),
        "stale_inputs_are_reported_only": True,
        "enters_current_evidence": False,
        "does_not_modify_strategy_action": True,
    }


def _skipped_reason_rows(
    *,
    source_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    excluded_candidates: list[Any],
    freshness_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        if row.get("present"):
            continue
        rows.append(
            {
                "reason": "legacy_signal_group_missing_in_snapshot",
                "group": row.get("group"),
                "severity": "coverage_gap",
                "action": "report_gap_do_not_silently_drop",
            }
        )
    if not candidate_rows:
        rows.append(
            {
                "reason": "no_candidate_rows_in_cache",
                "group": "next_ticket_candidates",
                "severity": "empty_result",
                "action": "show_empty_state_do_not_scan_full_market",
            }
        )
    if excluded_candidates:
        rows.append(
            {
                "reason": "excluded_candidates_present",
                "group": "radar_packet.excluded_candidates",
                "severity": "info",
                "action": "display_exclusions_without_trade_instruction",
                "row_count": len(excluded_candidates),
            }
        )
    if freshness_state.get("source") == "missing":
        rows.append(
            {
                "reason": "data_freshness_missing",
                "group": "data_freshness",
                "severity": "freshness_unknown",
                "action": "report_unknown_freshness_as_research_only",
            }
        )
    elif str(freshness_state.get("state") or "").lower() in {"stale", "expired", "historical", "unknown"}:
        rows.append(
            {
                "reason": "data_freshness_not_current",
                "group": "data_freshness",
                "severity": "freshness_gap",
                "state": freshness_state.get("state"),
                "action": "report_stale_inputs_without_action_mutation",
            }
        )
    return rows


def _scan_coverage(
    *,
    snapshot_available: bool,
    snapshot_map: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    excluded_candidates: list[Any],
    scan_mode: str,
) -> dict[str, Any]:
    source_rows = _source_group_rows(snapshot_map)
    present = [row for row in source_rows if row["present"]]
    missing = [str(row["group"]) for row in source_rows if not row["present"]]
    freshness_state = _candidate_freshness_state(snapshot_map)
    skipped_rows = _skipped_reason_rows(
        source_rows=source_rows,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        freshness_state=freshness_state,
    )
    return {
        "scan_mode": scan_mode,
        "scan_scope": "local_snapshot_cache_only",
        "snapshot_available": snapshot_available,
        "legacy_signal_group_count": len(source_rows),
        "mapped_signal_group_count": len(present),
        "missing_signal_group_count": len(missing),
        "missing_signal_groups": missing,
        "legacy_signal_group_rows": source_rows,
        "candidate_count": len(candidate_rows),
        "excluded_candidate_count": len(excluded_candidates),
        "skipped_reason_count": len(skipped_rows),
        "skipped_reason_rows": skipped_rows,
        "freshness_state": freshness_state,
        "coverage_status": "ready" if candidate_rows else ("partial_no_candidates" if present else "cache_missing"),
        "feature_loss_guard": "Missing legacy radar groups are reported as coverage gaps; they are not silently dropped.",
        "quick_scan_reads_cache_only": True,
        "does_not_scan_full_market_on_render": True,
        "does_not_call_external_sources": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _build_candidate_radar_packet(
    snapshot: Mapping[str, Any],
    *,
    mode: str,
    cache_source: str,
    scan_mode: str = "cache_only",
    request_params_safe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    radar_packet = _as_dict(snapshot_map.get("radar_packet") or snapshot_map.get("command_center_radar_packet"))
    candidates = _as_list(snapshot_map.get("next_ticket_candidates")) or _as_list(radar_packet.get("top_candidates"))
    excluded_candidates = _as_list(radar_packet.get("excluded_candidates"))[:10]
    evidence_recovery_actions = _as_list(snapshot_map.get("next_ticket_evidence_recovery_actions"))[:10]
    candidate_rows = _candidate_rows(candidates)
    counts = _candidate_counts(candidate_rows)
    parity_inventory = _legacy_parity_inventory(
        snapshot_map=snapshot_map,
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        evidence_recovery_actions=evidence_recovery_actions,
    )
    coverage = _scan_coverage(
        snapshot_available=bool(snapshot),
        snapshot_map=snapshot_map,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        scan_mode=scan_mode,
    )
    counts["legacy_parity_gap_count"] = parity_inventory["gap_or_future_count"]
    counts["legacy_parity_mapped_count"] = parity_inventory["mapped_or_partial_count"]
    counts["legacy_output_mapped_count"] = parity_inventory["output_contract_mapped_count"]

    if candidate_rows:
        status = "ready"
    elif radar_packet:
        status = "partial"
    elif snapshot:
        status = "cache_missing"
    else:
        status = "cache_missing"

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": mode,
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "snapshot_available": bool(snapshot),
        "source_snapshot_hash": _snapshot_fingerprint(snapshot_map),
        "cache_source": cache_source,
        "scan_mode": scan_mode,
        "quick_scan_supported": True,
        "source_packet_keys": ["radar_packet", "next_ticket_candidates", "candidate_execution_evidence_overview"],
        "summary": radar_packet.get("summary") or "候选雷达 cache 只读展示；无缓存时不自动扫描。",
        "manual_required_text": radar_packet.get("manual_required_text")
        or "下一票候选来自本地缓存或手动扫描结果；页面打开不会自动全市场扫描。",
        "counts": counts,
        "scan_coverage": coverage,
        "legacy_signal_group_rows": coverage["legacy_signal_group_rows"],
        "legacy_parity_inventory": parity_inventory,
        "legacy_parity_rows": _legacy_parity_rows(
            snapshot_map=snapshot_map,
            radar_packet=radar_packet,
            candidate_rows=candidate_rows,
            excluded_candidates=excluded_candidates,
            evidence_recovery_actions=evidence_recovery_actions,
        ),
        "legacy_output_contract_rows": _legacy_output_contract_rows(
            radar_packet=radar_packet,
            candidate_rows=candidate_rows,
            excluded_candidates=excluded_candidates,
        ),
        "scan_mode_status_rows": [dict(row) for row in SCAN_MODE_STATUS_ROWS],
        "skipped_reason_rows": coverage["skipped_reason_rows"],
        "freshness_state": coverage["freshness_state"],
        "candidate_rows": candidate_rows,
        "candidates": candidates[:10],
        "excluded_candidates": excluded_candidates,
        "candidate_execution_evidence_overview": _as_dict(snapshot_map.get("candidate_execution_evidence_overview")),
        "evidence_recovery_actions": evidence_recovery_actions,
        "old_workspace_packet_bridge": _as_dict(snapshot_map.get("old_workspace_packet_bridge")),
        "risk_alerts": _as_dict(snapshot_map.get("risk_alerts")),
        "radar_packet": radar_packet,
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_tushare": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_scan_market": True,
            "quick_scan_reads_cache_only": True,
            "quick_scan_preserves_legacy_signal_groups": True,
            "missing_legacy_groups_are_reported": True,
            "does_not_run_backtest": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_holdings": True,
            "candidate_is_not_buy_instruction": True,
            "post_task_required_for_scan": True,
        },
        "call_ledger": [
            _candidate_call_ledger_row(
                api="local_candidate_radar_cache",
                source_snapshot="command_center_latest.json",
                row_count=len(candidate_rows),
                call_status="cache_read" if snapshot else "cache_missing",
                request_params_safe=request_params_safe or {},
            )
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/candidate-radar/cache 只读展示下一票雷达缓存；不会自动全市场扫描。",
            "POST /api/candidate-radar/scan-quick 只扫描本地缓存并记录覆盖缺口；不会调用外部源。",
            "候选不是买入指令；必须经过证据链、触发条件、纪律和仓位预算复核。",
            "本页不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。",
        ],
    }
    if not candidate_rows:
        packet["warnings"].append("当前没有可展示候选；3.0 cache 页不会自动刷新或扫描。")
    return _json_safe(packet)


def _read_persisted_packet() -> dict[str, Any] | None:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(PACKET_KEY)
    except Exception:
        return None
    return packet if isinstance(packet, dict) else None


def _cache_view_from_persisted(packet: Mapping[str, Any]) -> dict[str, Any]:
    row_count = len(_as_list(packet.get("candidate_rows")))
    cache_row = _candidate_call_ledger_row(
        api="local_candidate_radar_cache",
        source_snapshot="sqlite_meta_candidate_radar_packet",
        row_count=row_count,
        call_status="cache_read_persisted_quick_scan",
    )
    view = dict(_json_safe(packet))
    existing_ledger = _as_list(view.get("call_ledger"))
    view["loaded_at"] = _now_iso()
    view["cache_only"] = True
    view["read_only"] = True
    view["cache_source"] = "sqlite_meta"
    view["call_ledger"] = [cache_row] + [row for row in existing_ledger if isinstance(row, dict)]
    warnings = _as_list(view.get("warnings"))
    first_warning = "GET /api/candidate-radar/cache 只读展示已持久化的 quick scan 结果；不会自动全市场扫描。"
    view["warnings"] = [first_warning] + [str(item) for item in warnings if item != first_warning]
    view["external_calls_triggered"] = False
    view["tushare_called"] = False
    view["deepseek_called"] = False
    view["github_called"] = False
    view["does_not_execute_trades"] = True
    view["does_not_modify_strategy_action"] = True
    view["contains_secret"] = False
    return _json_safe(view)


def read_candidate_radar_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    snapshot_hash = _snapshot_fingerprint(snapshot_map)
    persisted = _read_persisted_packet()
    if persisted and persisted.get("source_snapshot_hash") == snapshot_hash:
        return _cache_view_from_persisted(persisted)
    return _build_candidate_radar_packet(snapshot, mode="cache_only", cache_source="snapshot", scan_mode="cache_only")


def run_candidate_quick_scan_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_quick_scan",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_quick_scan_queued",
        warnings=[
            "候选雷达 quick scan 只读取本地 snapshot/cache；不会全市场扫描、不会调用 Tushare、DeepSeek 或 GitHub。",
            "候选不是买入指令；扫描结果不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="reading_local_candidate_radar_snapshot",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    requested_scan_mode = str(payload_safe.get("scan_mode") or "quick_cache_scan")
    scan_mode = requested_scan_mode if requested_scan_mode == "quick_cache_scan" else "quick_cache_scan"
    request_params_safe = {
        "requested_scan_mode": requested_scan_mode,
        "scan_mode": scan_mode,
        "unsupported_scan_mode_fallback": requested_scan_mode != scan_mode,
        "universe_mode": payload_safe.get("universe_mode") or "cache_snapshot",
        "external_sources_allowed": False,
    }
    snapshot = packet_service.load_snapshot_cache()
    packet = _build_candidate_radar_packet(
        snapshot,
        mode="quick_cache_scan",
        cache_source="quick_scan_task",
        scan_mode=scan_mode,
        request_params_safe=request_params_safe,
    )
    quick_ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_quick_scan",
        source_snapshot="command_center_latest.json",
        row_count=len(_as_list(packet.get("candidate_rows"))),
        call_status="quick_scan_completed" if snapshot else "quick_scan_cache_missing",
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["quick_scan_completed_at"] = _now_iso()
    packet["call_ledger"] = [quick_ledger]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        quick_ledger["call_status"] = "quick_scan_storage_write_failed"
        quick_ledger["error_message_safe"] = "candidate_radar_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_quick_scan_storage_write_failed",
            error_message_safe="candidate_radar_sqlite_write_failed",
            call_ledger=[quick_ledger],
            warning="candidate_radar_quick_scan_failed_no_external_call",
        ) or task

    final_warning = "candidate_radar_quick_scan_completed_no_external_call"
    if not _as_list(packet.get("candidate_rows")):
        final_warning = "candidate_radar_quick_scan_completed_no_candidates_no_external_call"
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_quick_scan_completed",
        call_ledger=[quick_ledger],
        warning=final_warning,
    ) or task
