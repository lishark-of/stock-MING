from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore
from server.services import packet_service, task_service


PACKET_KEY = "command_center_3_candidate_radar_cache"
SCHEMA_VERSION = "candidate_radar_cache.v1"
SQLITE_META_PATH = Path(__file__).resolve().parents[2] / ".stock_ming_3" / "meta.sqlite"
SUPPORTED_LOCAL_SCAN_MODES = {"quick_cache_scan", "watchlist_scan", "custom_pool_scan"}
LOCAL_POOL_SCAN_MODES = {"watchlist_scan", "custom_pool_scan"}
SENSITIVE_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password", "passwd", "credential", "authorization")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")
FULL_POOL_FILTER_DEFAULTS = {
    "exclude_st": True,
    "exclude_chinext": True,
    "exclude_star": True,
    "exclude_bj": True,
    "exclude_low_amount": True,
    "trend_up_only": True,
}
FULL_POOL_REQUIRED_STORAGE_DATASETS = ["daily", "daily_basic", "moneyflow", "trade_cal"]
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
        "status": "implemented_local_input",
        "scope": "local payload or snapshot watchlist",
        "external_calls": False,
        "notes": "Reads only provided/local watchlist candidates; missing watchlist is reported as a gap.",
    },
    {
        "scan_mode": "custom_pool_scan",
        "status": "implemented_local_input",
        "scope": "manual/custom candidate pool",
        "external_calls": False,
        "notes": "Parses local manual candidates, de-duplicates them, and keeps all results research-only.",
    },
    {
        "scan_mode": "full_pool_scan",
        "status": "planned_future_task_read_plan_available",
        "scope": "A-share broad/index pool scan",
        "external_calls": "button_gated_future",
        "notes": "Full-pool plan can be generated locally; actual scan still requires future worker execution and explicit provider refresh tasks.",
    },
    {
        "scan_mode": "manual_deep_research",
        "status": "planned_manual_only",
        "scope": "DeepSeek explanation for selected candidate",
        "external_calls": "button_gated_future",
        "notes": "Not part of quick scan; output must remain research-only.",
    },
]
RADAR_PROVIDER_SIGNAL_REQUIREMENTS = [
    {
        "signal_group": "moneyflow",
        "label": "资金流",
        "apis": ["moneyflow"],
        "legacy_role": "candidate fund-flow confirmation",
    },
    {
        "signal_group": "dragon_tiger",
        "label": "龙虎榜",
        "apis": ["top_list", "top_inst"],
        "legacy_role": "hot-money and institutional behavior",
    },
    {
        "signal_group": "limit_emotion",
        "label": "涨跌停/情绪",
        "apis": ["stk_limit", "limit_list_d", "limit_cpt_list"],
        "legacy_role": "limit-up/down and market emotion",
    },
    {
        "signal_group": "chip_radar",
        "label": "筹码/胜率",
        "apis": ["cyq_perf", "cyq_chips"],
        "legacy_role": "chip distribution and winner-rate pressure",
    },
    {
        "signal_group": "hard_risk",
        "label": "硬风险",
        "apis": ["anns_d", "forecast", "pledge", "holdertrade", "share_float", "stk_surv"],
        "legacy_role": "announcement and structural risk exclusion",
    },
]
PROVIDER_BLOCKED_MARKERS = {
    "blocked",
    "permission_denied",
    "not_configured",
    "disabled_this_session",
    "runtime_secret_missing",
    "requires_manual_config",
    "权限不足",
    "未配置",
    "本会话跳过",
}
PROVIDER_STALE_MARKERS = {"stale", "stale_cache", "expired", "historical", "fallback_used", "使用缓存", "过期"}
PROVIDER_MISSING_MARKERS = {
    "missing",
    "empty_recent",
    "not_loaded",
    "no_data",
    "cache_missing",
    "matrix_only",
    "近期无数据",
    "缺失",
}
PROVIDER_AVAILABLE_MARKERS = {"available", "ready", "success", "validated", "可用", "完成"}


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


def _first_non_empty(mapping: Mapping[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _split_candidate_text(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [part.strip() for part in re.split(r"[\s,，;；]+", value) if part.strip()]


def _candidate_code_from_item(item: Mapping[str, Any]) -> str:
    value = _first_non_empty(item, ["ticker", "ts_code", "code", "stock_code", "symbol"])
    return _safe_text(value, limit=32).upper()


def _candidate_name_from_item(item: Mapping[str, Any]) -> str:
    value = _first_non_empty(item, ["name", "stock_name", "security_name", "display_name"])
    return _safe_text(value, limit=80)


def _local_pool_items_from_payload(payload_safe: Mapping[str, Any], scan_mode: str) -> tuple[list[Any], str]:
    if scan_mode == "watchlist_scan":
        keys = ["watchlist_candidates", "watchlist_targets", "candidates", "targets"]
    else:
        keys = ["custom_candidates", "custom_pool", "manual_candidates", "candidates", "targets"]
    rows: list[Any] = []
    source_key = ""
    for key in keys:
        value = payload_safe.get(key)
        if value in (None, "", [], {}):
            continue
        source_key = f"payload.{key}"
        if isinstance(value, str):
            rows.extend(_split_candidate_text(value))
        elif isinstance(value, list):
            rows.extend(value)
        else:
            rows.append(value)
        break
    text_value = payload_safe.get("custom_pool_text") if scan_mode == "custom_pool_scan" else payload_safe.get("watchlist_text")
    text_rows = _split_candidate_text(text_value)
    if text_rows and not rows:
        rows.extend(text_rows)
        source_key = "payload.custom_pool_text" if scan_mode == "custom_pool_scan" else "payload.watchlist_text"
    return rows, source_key


def _local_watchlist_items_from_snapshot(snapshot_map: Mapping[str, Any]) -> tuple[list[Any], str]:
    for key in [
        "announcement_watchlist",
        "announcement_watchlist_payload",
        "watchlist",
        "watchlist_payload",
        "next_observation_targets",
        "watchlist_targets",
    ]:
        value = snapshot_map.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, Mapping):
            for child_key in ["targets", "items", "candidates", "rows"]:
                rows = value.get(child_key)
                if isinstance(rows, list):
                    return rows, f"snapshot.{key}.{child_key}"
        if isinstance(value, list):
            return value, f"snapshot.{key}"
    return [], ""


def _normalize_local_pool_candidates(
    raw_items: list[Any],
    *,
    scan_mode: str,
    input_source: str,
    max_items: int = 50,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()
    disabled_count = 0
    invalid_count = 0
    duplicate_count = 0
    truncated_count = max(0, len(raw_items) - max_items)
    source_label = "持续调查池本地输入" if scan_mode == "watchlist_scan" else "自定义候选池本地输入"

    for index, raw in enumerate(raw_items[:max_items], start=1):
        safe_raw = _safe_value(raw)
        item = safe_raw if isinstance(safe_raw, dict) else {"ticker": safe_raw}
        enabled = item.get("enabled", True)
        if enabled is False or str(enabled).strip().lower() in {"false", "0", "no", "disabled"}:
            disabled_count += 1
            skipped.append(
                {
                    "reason": "local_pool_candidate_disabled",
                    "group": scan_mode,
                    "severity": "info",
                    "row_index": index,
                    "ticker": _candidate_code_from_item(item),
                    "action": "skip_disabled_candidate_no_external_call",
                }
            )
            continue
        ticker = _candidate_code_from_item(item)
        if not ticker:
            invalid_count += 1
            skipped.append(
                {
                    "reason": "local_pool_candidate_missing_code",
                    "group": scan_mode,
                    "severity": "input_gap",
                    "row_index": index,
                    "action": "skip_invalid_candidate_do_not_guess_code",
                }
            )
            continue
        if ticker in seen:
            duplicate_count += 1
            skipped.append(
                {
                    "reason": "local_pool_candidate_duplicate",
                    "group": scan_mode,
                    "severity": "dedupe",
                    "row_index": index,
                    "ticker": ticker,
                    "action": "dedupe_local_candidate_keep_first",
                }
            )
            continue
        seen.add(ticker)
        candidates.append(
            {
                "rank": len(candidates) + 1,
                "ticker": ticker,
                "name": _candidate_name_from_item(item),
                "score": item.get("score"),
                "status_label": item.get("status_label") or "本地候选待验证",
                "action_state": item.get("action_state") or "只观察",
                "tone": item.get("tone") or "warn",
                "evidence_chain_summary": item.get("evidence_chain_summary") or "本地候选池输入；未刷新外部证据链。",
                "trigger_condition": item.get("trigger_condition") or item.get("trigger") or "",
                "invalidation_condition": item.get("invalidation_condition") or item.get("invalid_condition") or "",
                "source": item.get("source") or source_label,
                "updated_at": item.get("updated_at") or item.get("created_at"),
                "data_gaps": item.get("data_gaps")
                or ["local_pool_evidence_not_refreshed", "freshness_requires_current_cache_review"],
            }
        )

    if truncated_count:
        skipped.append(
            {
                "reason": "local_pool_candidate_limit_truncated",
                "group": scan_mode,
                "severity": "input_limit",
                "row_count": truncated_count,
                "action": "truncate_large_local_payload_keep_scan_fast",
            }
        )

    audit = {
        "scan_mode": scan_mode,
        "input_source": input_source or "missing",
        "input_candidate_count": len(raw_items),
        "normalized_candidate_count": len(candidates),
        "disabled_candidate_count": disabled_count,
        "invalid_candidate_count": invalid_count,
        "duplicate_candidate_count": duplicate_count,
        "truncated_candidate_count": truncated_count,
        "max_local_candidates": max_items,
        "cache_only": True,
        "external_calls_triggered": False,
        "does_not_call_tushare": True,
        "does_not_call_deepseek": True,
        "does_not_call_github": True,
        "does_not_scan_full_market": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }
    return candidates, skipped, audit


def _snapshot_with_local_candidate_pool(
    snapshot_map: Mapping[str, Any],
    payload_safe: Mapping[str, Any],
    scan_mode: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    raw_items, input_source = _local_pool_items_from_payload(payload_safe, scan_mode)
    if scan_mode == "watchlist_scan" and not raw_items:
        raw_items, input_source = _local_watchlist_items_from_snapshot(snapshot_map)
    candidates, skipped, audit = _normalize_local_pool_candidates(
        raw_items,
        scan_mode=scan_mode,
        input_source=input_source,
    )
    overlay = dict(snapshot_map)
    existing_radar = _as_dict(snapshot_map.get("radar_packet") or snapshot_map.get("command_center_radar_packet"))
    source_text = "持续调查池本地扫描" if scan_mode == "watchlist_scan" else "自定义候选池本地扫描"
    overlay["next_ticket_candidates"] = candidates
    overlay["radar_packet"] = {
        **existing_radar,
        "status": "ready" if candidates else "cache_missing",
        "source": source_text,
        "summary": f"{source_text}生成 {len(candidates)} 个候选；未调用外部源，结果只用于 research-only 复核。",
        "generated_at": _now_iso(),
        "total_count": len(candidates),
        "top_candidates": candidates,
        "watch_candidates": [],
        "excluded_candidates": _as_list(existing_radar.get("excluded_candidates")),
        "manual_required_text": "本地候选池扫描不是买入指令；必须补齐证据链、freshness、纪律和仓位预算。",
    }
    overlay["local_candidate_pool_audit"] = audit
    overlay["local_candidate_pool_skipped_rows"] = skipped
    return overlay, audit, skipped


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
                "data_gaps": item.get("data_gaps"),
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


def _rows_from_any(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for key in ("rows", "items", "providers", "capabilities", "data", "records"):
            nested = value.get(key)
            if isinstance(nested, list):
                rows.extend(_rows_from_any(nested))
        if not rows and any(key in value for key in ("provider", "api", "capability_state", "status", "state", "label")):
            rows.append(dict(value))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                rows.extend(_rows_from_any(item))
    return rows[:120]


def _provider_capability_rows(snapshot_map: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_key in (
        "data_health_ledger",
        "command_center_data_health_ledger",
        "a_share_capability_matrix",
        "provider_data_capability_cockpit",
        "provider_recovery_matrix",
        "data_gap_report",
    ):
        for row in _rows_from_any(snapshot_map.get(source_key)):
            safe = _safe_value(row)
            if not isinstance(safe, dict):
                continue
            safe.setdefault("source_key", source_key)
            rows.append(safe)
    return rows[:160]


def _provider_row_api_text(row: Mapping[str, Any]) -> str:
    values = [
        row.get("api"),
        row.get("interface"),
        row.get("section"),
        row.get("fact_key"),
        row.get("group"),
        row.get("label"),
        row.get("name"),
    ]
    return " ".join(str(value or "").lower() for value in values)


def _provider_status_text(row: Mapping[str, Any]) -> str:
    values = [
        row.get("capability_state"),
        row.get("status"),
        row.get("state"),
        row.get("readiness"),
        row.get("call_status"),
        row.get("validation_status"),
        row.get("error"),
        row.get("message"),
    ]
    return " ".join(str(value or "").lower() for value in values)


def _classify_provider_status(row: Mapping[str, Any]) -> str:
    status_text = _provider_status_text(row)
    if any(marker.lower() in status_text for marker in PROVIDER_BLOCKED_MARKERS):
        return "provider_blocked"
    if any(marker.lower() in status_text for marker in PROVIDER_STALE_MARKERS):
        return "stale_input"
    if any(marker.lower() in status_text for marker in PROVIDER_MISSING_MARKERS):
        return "missing_provider_data"
    if any(marker.lower() in status_text for marker in PROVIDER_AVAILABLE_MARKERS):
        return "available"
    return "unknown"


def _provider_coverage_rows(snapshot_map: Mapping[str, Any]) -> list[dict[str, Any]]:
    capability_rows = _provider_capability_rows(snapshot_map)
    coverage_rows: list[dict[str, Any]] = []
    for requirement in RADAR_PROVIDER_SIGNAL_REQUIREMENTS:
        apis = [str(api).lower() for api in requirement["apis"]]
        matched = [row for row in capability_rows if any(api in _provider_row_api_text(row) for api in apis)]
        classifications = [_classify_provider_status(row) for row in matched]
        if not matched:
            coverage_status = "missing_provider_data"
            severity = "coverage_gap"
        elif "provider_blocked" in classifications:
            coverage_status = "provider_blocked"
            severity = "provider_blocked"
        elif "stale_input" in classifications:
            coverage_status = "stale_input"
            severity = "freshness_gap"
        elif "missing_provider_data" in classifications:
            coverage_status = "missing_provider_data"
            severity = "coverage_gap"
        elif "available" in classifications:
            coverage_status = "available"
            severity = "ok"
        else:
            coverage_status = "unknown"
            severity = "coverage_unknown"
        coverage_rows.append(
            {
                "signal_group": requirement["signal_group"],
                "label": requirement["label"],
                "required_apis": requirement["apis"],
                "legacy_role": requirement["legacy_role"],
                "matched_provider_row_count": len(matched),
                "coverage_status": coverage_status,
                "severity": severity,
                "source_keys": sorted({str(row.get("source_key") or "") for row in matched if row.get("source_key")}),
                "matched_apis": sorted(
                    {
                        str(row.get("api") or row.get("interface") or row.get("section") or "")
                        for row in matched
                        if row.get("api") or row.get("interface") or row.get("section")
                    }
                ),
                "reported_as_gap": coverage_status != "available",
                "does_not_refresh_provider": True,
                "does_not_call_external_sources": True,
                "does_not_modify_strategy_action": True,
                "does_not_execute_trades": True,
            }
        )
    return coverage_rows


def _degraded_mode_rows(
    *,
    scan_mode: str,
    provider_rows: list[dict[str, Any]],
    freshness_state: Mapping[str, Any],
    local_pool_audit: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "mode": "local_cache_only",
            "active": True,
            "severity": "info",
            "reason": "radar_scan_reads_local_snapshot_without_provider_refresh",
            "user_visible": True,
            "does_not_call_external_sources": True,
        },
        {
            "mode": "full_pool_scan_pending",
            "active": scan_mode != "full_pool_scan",
            "severity": "future_task",
            "reason": "full_pool_scan_requires_future_worker_task",
            "user_visible": True,
            "does_not_scan_full_market_on_render": True,
        },
    ]
    status_counts = {
        "provider_blocked": sum(1 for row in provider_rows if row.get("coverage_status") == "provider_blocked"),
        "stale_input": sum(1 for row in provider_rows if row.get("coverage_status") == "stale_input"),
        "missing_provider_data": sum(1 for row in provider_rows if row.get("coverage_status") == "missing_provider_data"),
    }
    for status, count in status_counts.items():
        rows.append(
            {
                "mode": status,
                "active": bool(count),
                "severity": "coverage_gap" if status != "stale_input" else "freshness_gap",
                "affected_group_count": count,
                "reason": f"{status}_reported_without_refresh",
                "user_visible": True,
                "does_not_call_external_sources": True,
            }
        )
    freshness = str(freshness_state.get("state") or "").lower()
    rows.append(
        {
            "mode": "freshness_research_only",
            "active": freshness_state.get("source") == "missing" or freshness in {"stale", "expired", "historical", "unknown"},
            "severity": "freshness_gap",
            "reason": "stale_or_missing_freshness_is_display_only",
            "user_visible": True,
            "does_not_modify_strategy_action": True,
        }
    )
    if local_pool_audit:
        rows.append(
            {
                "mode": "local_pool_partial",
                "active": bool(
                    local_pool_audit.get("duplicate_candidate_count")
                    or local_pool_audit.get("invalid_candidate_count")
                    or local_pool_audit.get("disabled_candidate_count")
                    or local_pool_audit.get("truncated_candidate_count")
                    or not candidate_rows
                ),
                "severity": "input_gap",
                "reason": "local_pool_skips_are_visible_and_do_not_trigger_broad_scan",
                "user_visible": True,
                "does_not_scan_full_market_on_render": True,
            }
        )
    return rows


def _skipped_reason_rows(
    *,
    source_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    excluded_candidates: list[Any],
    freshness_state: Mapping[str, Any],
    provider_coverage_rows: list[dict[str, Any]] | None = None,
    local_pool_audit: Mapping[str, Any] | None = None,
    local_pool_skipped_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = list(local_pool_skipped_rows or [])
    audit = local_pool_audit or {}
    if audit and not audit.get("normalized_candidate_count"):
        rows.append(
            {
                "reason": "local_candidate_pool_empty",
                "group": audit.get("scan_mode") or "local_candidate_pool",
                "severity": "empty_result",
                "input_source": audit.get("input_source") or "missing",
                "action": "show_empty_state_do_not_scan_full_market",
            }
        )
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
    for row in provider_coverage_rows or []:
        status = str(row.get("coverage_status") or "")
        if status == "available":
            continue
        reason = {
            "provider_blocked": "radar_provider_blocked",
            "stale_input": "radar_provider_stale_input",
            "missing_provider_data": "radar_provider_missing_data",
        }.get(status, "radar_provider_unknown")
        rows.append(
            {
                "reason": reason,
                "group": row.get("signal_group"),
                "severity": row.get("severity") or "coverage_gap",
                "matched_provider_row_count": row.get("matched_provider_row_count"),
                "action": "report_provider_gap_do_not_refresh_on_render",
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
    local_pool_audit: Mapping[str, Any] | None = None,
    local_pool_skipped_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source_rows = _source_group_rows(snapshot_map)
    present = [row for row in source_rows if row["present"]]
    missing = [str(row["group"]) for row in source_rows if not row["present"]]
    freshness_state = _candidate_freshness_state(snapshot_map)
    provider_rows = _provider_coverage_rows(snapshot_map)
    skipped_rows = _skipped_reason_rows(
        source_rows=source_rows,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        freshness_state=freshness_state,
        provider_coverage_rows=provider_rows,
        local_pool_audit=local_pool_audit,
        local_pool_skipped_rows=local_pool_skipped_rows,
    )
    audit = local_pool_audit or {}
    universe_mode = (
        "local_watchlist"
        if scan_mode == "watchlist_scan"
        else "manual_input"
        if scan_mode == "custom_pool_scan"
        else "cache_snapshot"
    )
    universe_size = (
        audit.get("input_candidate_count")
        if audit.get("input_candidate_count") is not None
        else len(candidate_rows) + len(excluded_candidates)
    )
    degraded_rows = _degraded_mode_rows(
        scan_mode=scan_mode,
        provider_rows=provider_rows,
        freshness_state=freshness_state,
        local_pool_audit=audit,
        candidate_rows=candidate_rows,
    )
    provider_blocked_count = sum(1 for row in provider_rows if row.get("coverage_status") == "provider_blocked")
    stale_input_count = sum(1 for row in provider_rows if row.get("coverage_status") == "stale_input")
    missing_provider_count = sum(1 for row in provider_rows if row.get("coverage_status") == "missing_provider_data")
    degraded_active_count = sum(1 for row in degraded_rows if row.get("active"))
    coverage_detail_summary = {
        "scan_mode": scan_mode,
        "universe_mode": universe_mode,
        "universe_size": int(universe_size or 0),
        "candidate_count": len(candidate_rows),
        "excluded_candidate_count": len(excluded_candidates),
        "provider_signal_group_count": len(provider_rows),
        "provider_blocked_group_count": provider_blocked_count,
        "stale_input_group_count": stale_input_count,
        "missing_provider_data_group_count": missing_provider_count,
        "degraded_mode_count": len(degraded_rows),
        "degraded_mode_active_count": degraded_active_count,
        "degraded_mode_active": bool(degraded_active_count),
        "quick_scan_is_research_only": True,
        "full_pool_scan_done": False,
        "full_pool_scan_requires_worker": True,
        "missing_data_is_reported_not_dropped": True,
        "does_not_call_external_sources": True,
        "does_not_scan_full_market_on_render": True,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }
    return {
        "scan_mode": scan_mode,
        "scan_scope": "local_snapshot_cache_only",
        "snapshot_available": snapshot_available,
        "universe_mode": universe_mode,
        "universe_size": int(universe_size or 0),
        "legacy_signal_group_count": len(source_rows),
        "mapped_signal_group_count": len(present),
        "missing_signal_group_count": len(missing),
        "missing_signal_groups": missing,
        "legacy_signal_group_rows": source_rows,
        "provider_signal_group_count": len(provider_rows),
        "provider_blocked_group_count": provider_blocked_count,
        "stale_input_group_count": stale_input_count,
        "missing_provider_data_group_count": missing_provider_count,
        "provider_coverage_rows": provider_rows,
        "degraded_mode_rows": degraded_rows,
        "coverage_detail_summary": coverage_detail_summary,
        "candidate_count": len(candidate_rows),
        "local_pool_input_candidate_count": audit.get("input_candidate_count"),
        "local_pool_normalized_candidate_count": audit.get("normalized_candidate_count"),
        "local_pool_duplicate_candidate_count": audit.get("duplicate_candidate_count"),
        "local_pool_invalid_candidate_count": audit.get("invalid_candidate_count"),
        "local_pool_disabled_candidate_count": audit.get("disabled_candidate_count"),
        "local_pool_truncated_candidate_count": audit.get("truncated_candidate_count"),
        "excluded_candidate_count": len(excluded_candidates),
        "skipped_reason_count": len(skipped_rows),
        "skipped_reason_rows": skipped_rows,
        "freshness_state": freshness_state,
        "coverage_status": "ready" if candidate_rows else ("partial_no_candidates" if present else "cache_missing"),
        "feature_loss_guard": "Missing legacy radar groups are reported as coverage gaps; they are not silently dropped.",
        "quick_scan_reads_cache_only": True,
        "watchlist_scan_reads_local_input_only": scan_mode == "watchlist_scan",
        "custom_pool_scan_reads_local_input_only": scan_mode == "custom_pool_scan",
        "does_not_scan_full_market_on_render": True,
        "does_not_call_external_sources": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _full_pool_filter_rows(payload_safe: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, default in FULL_POOL_FILTER_DEFAULTS.items():
        value = payload_safe.get(key, default)
        if isinstance(value, str):
            enabled = value.strip().lower() not in {"false", "0", "no", "off"}
        else:
            enabled = bool(value)
        rows.append(
            {
                "filter_key": key,
                "enabled": enabled,
                "default_enabled": default,
                "source": "payload" if key in payload_safe else "default",
                "effect": "candidate_exclusion_before_scoring",
                "applied_now": False,
                "requires_future_scan_execution": True,
                "does_not_scan_full_market_on_plan": True,
                "does_not_modify_strategy_action": True,
                "does_not_execute_trades": True,
            }
        )
    return rows


def _full_pool_stage_rows(
    *,
    provider_rows: list[dict[str, Any]],
    freshness_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    provider_gap_count = sum(1 for row in provider_rows if row.get("coverage_status") != "available")
    freshness_missing = freshness_state.get("source") == "missing"
    return [
        {
            "stage": "load_universe",
            "status": "planned_worker_required",
            "source": "future local universe dataset or explicit task payload",
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "full_pool_universe_not_loaded_in_plan_task",
        },
        {
            "stage": "apply_filters",
            "status": "planned_filters_declared",
            "source": "full_pool_filter_rows",
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "",
        },
        {
            "stage": "read_local_storage",
            "status": "planned_storage_contract_required",
            "source": ",".join(FULL_POOL_REQUIRED_STORAGE_DATASETS),
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "storage_query_contracts_must_be_consumed_by_future_worker",
        },
        {
            "stage": "provider_refresh",
            "status": "blocked_until_explicit_provider_tasks" if provider_gap_count else "optional_if_cache_fresh",
            "source": "Tushare button-gated refresh tasks",
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "provider_gaps_present" if provider_gap_count else "",
        },
        {
            "stage": "freshness_gate",
            "status": "blocked_until_current_freshness" if freshness_missing else "planned_gate_required",
            "source": "data_freshness/trade_cal",
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "freshness_state_missing" if freshness_missing else "",
        },
        {
            "stage": "score_candidates",
            "status": "planned_research_only",
            "source": "legacy radar scoring parity map",
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "scoring_not_executed_in_plan_task",
        },
        {
            "stage": "write_candidate_packet",
            "status": "planned_after_worker_scan",
            "source": PACKET_KEY,
            "executed_now": False,
            "external_calls_triggered": False,
            "blocker": "full_pool_packet_not_written_by_plan",
        },
    ]


def _full_pool_blocker_rows(
    *,
    provider_rows: list[dict[str, Any]],
    freshness_state: Mapping[str, Any],
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "blocker_key": "worker_required",
            "severity": "production_required",
            "status": "blocked",
            "message": "full_pool_scan must run through future worker/task execution, not page render.",
            "blocks_full_pool_scan": True,
        }
    ]
    if freshness_state.get("source") == "missing":
        rows.append(
            {
                "blocker_key": "freshness_missing",
                "severity": "freshness_gap",
                "status": "blocked",
                "message": "freshness_state is missing; full-pool candidates would be research-only.",
                "blocks_full_pool_scan": True,
            }
        )
    for row in provider_rows:
        if row.get("coverage_status") == "available":
            continue
        rows.append(
            {
                "blocker_key": f"provider_{row.get('signal_group')}",
                "severity": row.get("severity") or "coverage_gap",
                "status": row.get("coverage_status") or "unknown",
                "message": f"{row.get('label')} provider coverage is {row.get('coverage_status')}.",
                "blocks_full_pool_scan": True,
            }
        )
    missing_groups = [row.get("group") for row in source_rows if not row.get("present")]
    if missing_groups:
        rows.append(
            {
                "blocker_key": "legacy_signal_group_gaps",
                "severity": "parity_gap",
                "status": "missing_reported",
                "message": "Legacy radar signal groups are not all mapped in current cache.",
                "missing_signal_groups": missing_groups,
                "blocks_full_pool_scan": False,
            }
        )
    for row in rows:
        row.update(
            {
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _full_pool_required_signal_rows(provider_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_group = {str(row.get("signal_group") or ""): row for row in provider_rows}
    for requirement in RADAR_PROVIDER_SIGNAL_REQUIREMENTS:
        coverage = by_group.get(str(requirement["signal_group"])) or {}
        rows.append(
            {
                "signal_group": requirement["signal_group"],
                "label": requirement["label"],
                "required_apis": requirement["apis"],
                "legacy_role": requirement["legacy_role"],
                "coverage_status": coverage.get("coverage_status") or "missing_provider_data",
                "matched_provider_row_count": coverage.get("matched_provider_row_count") or 0,
                "ready_for_full_pool": coverage.get("coverage_status") == "available",
                "requires_explicit_provider_task": coverage.get("coverage_status") != "available",
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _build_full_pool_scan_plan(
    snapshot_map: Mapping[str, Any],
    payload_safe: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any]:
    provider_rows = _provider_coverage_rows(snapshot_map)
    freshness_state = _candidate_freshness_state(snapshot_map)
    source_rows = _source_group_rows(snapshot_map)
    filter_rows = _full_pool_filter_rows(payload_safe)
    blocker_rows = _full_pool_blocker_rows(
        provider_rows=provider_rows,
        freshness_state=freshness_state,
        source_rows=source_rows,
    )
    stage_rows = _full_pool_stage_rows(provider_rows=provider_rows, freshness_state=freshness_state)
    signal_rows = _full_pool_required_signal_rows(provider_rows)
    blocking_count = sum(1 for row in blocker_rows if row.get("blocks_full_pool_scan"))
    return {
        "schema_version": "candidate_radar_full_pool_plan.v1",
        "status": "full_pool_plan_ready",
        "task_type": "run_candidate_radar_full_pool_plan",
        "created_at": now,
        "requested_scan_mode": "full_pool_scan",
        "full_pool_scan_done": False,
        "full_pool_validation_done": False,
        "worker_task_required": True,
        "worker_task_consumption_plan_ready": True,
        "page_render_starts_full_pool": False,
        "cache_get_starts_full_pool": False,
        "provider_refresh_executed": False,
        "candidate_scoring_executed": False,
        "candidate_packet_written_by_plan": False,
        "storage_datasets_required": list(FULL_POOL_REQUIRED_STORAGE_DATASETS),
        "required_signal_group_count": len(signal_rows),
        "ready_signal_group_count": sum(1 for row in signal_rows if row.get("ready_for_full_pool")),
        "provider_gap_count": sum(1 for row in signal_rows if not row.get("ready_for_full_pool")),
        "blocking_issue_count": blocking_count,
        "filter_rows": filter_rows,
        "stage_rows": stage_rows,
        "required_signal_rows": signal_rows,
        "blocker_rows": blocker_rows,
        "legacy_signal_group_rows": source_rows,
        "freshness_state": freshness_state,
        "research_only": True,
        "candidate_is_not_buy_instruction": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "warning": "Full-pool plan only records prerequisites and blockers; it does not scan the market or produce buy candidates.",
    }


def _build_candidate_radar_packet(
    snapshot: Mapping[str, Any],
    *,
    mode: str,
    cache_source: str,
    scan_mode: str = "cache_only",
    request_params_safe: dict[str, Any] | None = None,
    local_pool_audit: Mapping[str, Any] | None = None,
    local_pool_skipped_rows: list[dict[str, Any]] | None = None,
    full_pool_scan_plan: Mapping[str, Any] | None = None,
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
        local_pool_audit=local_pool_audit,
        local_pool_skipped_rows=local_pool_skipped_rows,
    )
    counts["legacy_parity_gap_count"] = parity_inventory["gap_or_future_count"]
    counts["legacy_parity_mapped_count"] = parity_inventory["mapped_or_partial_count"]
    counts["legacy_output_mapped_count"] = parity_inventory["output_contract_mapped_count"]
    if local_pool_audit:
        counts["local_pool_input_candidate_count"] = local_pool_audit.get("input_candidate_count")
        counts["local_pool_normalized_candidate_count"] = local_pool_audit.get("normalized_candidate_count")
        counts["local_pool_duplicate_candidate_count"] = local_pool_audit.get("duplicate_candidate_count")
    counts["provider_blocked_group_count"] = coverage["coverage_detail_summary"]["provider_blocked_group_count"]
    counts["stale_input_group_count"] = coverage["coverage_detail_summary"]["stale_input_group_count"]
    counts["missing_provider_data_group_count"] = coverage["coverage_detail_summary"]["missing_provider_data_group_count"]
    counts["degraded_mode_active_count"] = coverage["coverage_detail_summary"]["degraded_mode_active_count"]
    counts["universe_size"] = coverage["coverage_detail_summary"]["universe_size"]
    plan = dict(full_pool_scan_plan or _as_dict(snapshot_map.get("full_pool_scan_plan")))
    full_pool_blocker_rows = _as_list(plan.get("blocker_rows"))
    if plan:
        counts["full_pool_plan_blocking_issue_count"] = plan.get("blocking_issue_count")
        counts["full_pool_plan_ready_signal_group_count"] = plan.get("ready_signal_group_count")
        counts["full_pool_plan_provider_gap_count"] = plan.get("provider_gap_count")

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
        "local_pool_scan_supported": True,
        "supported_local_scan_modes": sorted(SUPPORTED_LOCAL_SCAN_MODES),
        "source_packet_keys": [
            "radar_packet",
            "next_ticket_candidates",
            "candidate_execution_evidence_overview",
            "local_candidate_pool_audit",
        ],
        "summary": radar_packet.get("summary") or "候选雷达 cache 只读展示；无缓存时不自动扫描。",
        "manual_required_text": radar_packet.get("manual_required_text")
        or "下一票候选来自本地缓存或手动扫描结果；页面打开不会自动全市场扫描。",
        "counts": counts,
        "scan_coverage": coverage,
        "coverage_detail_summary": coverage["coverage_detail_summary"],
        "provider_coverage_rows": coverage["provider_coverage_rows"],
        "degraded_mode_rows": coverage["degraded_mode_rows"],
        "local_candidate_pool_audit": dict(local_pool_audit or _as_dict(snapshot_map.get("local_candidate_pool_audit"))),
        "local_candidate_pool_skipped_rows": list(local_pool_skipped_rows or _as_list(snapshot_map.get("local_candidate_pool_skipped_rows"))),
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
        "full_pool_scan_plan": plan,
        "full_pool_plan_stage_rows": _as_list(plan.get("stage_rows")),
        "full_pool_plan_filter_rows": _as_list(plan.get("filter_rows")),
        "full_pool_required_signal_rows": _as_list(plan.get("required_signal_rows")),
        "full_pool_blocker_rows": full_pool_blocker_rows,
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
            "local_pool_scan_reads_local_input_only": scan_mode in LOCAL_POOL_SCAN_MODES,
            "watchlist_scan_reads_local_input_only": scan_mode == "watchlist_scan",
            "custom_pool_scan_reads_local_input_only": scan_mode == "custom_pool_scan",
            "quick_scan_preserves_legacy_signal_groups": True,
            "missing_legacy_groups_are_reported": True,
            "provider_gaps_are_reported": True,
            "missing_provider_data_is_not_silently_dropped": True,
            "stale_inputs_are_research_only": True,
            "degraded_modes_are_visible": True,
            "full_pool_scan_requires_future_worker": True,
            "full_pool_plan_is_not_full_pool_scan": True,
            "full_pool_plan_writes_no_candidates": True,
            "full_pool_plan_provider_refresh_executed": False,
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
            "provider 阻断、stale 输入、缺失 provider 数据和降级模式会作为 coverage gap 展示，不会在页面渲染时补数。",
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
    persisted_scan_mode = str(packet.get("scan_mode") or "local_scan")
    cache_row = _candidate_call_ledger_row(
        api="local_candidate_radar_cache",
        source_snapshot="sqlite_meta_candidate_radar_packet",
        row_count=row_count,
        call_status=f"cache_read_persisted_{persisted_scan_mode}",
    )
    view = dict(_json_safe(packet))
    existing_ledger = _as_list(view.get("call_ledger"))
    view["loaded_at"] = _now_iso()
    view["cache_only"] = True
    view["read_only"] = True
    view["cache_source"] = "sqlite_meta"
    view["call_ledger"] = [cache_row] + [row for row in existing_ledger if isinstance(row, dict)]
    warnings = _as_list(view.get("warnings"))
    first_warning = "GET /api/candidate-radar/cache 只读展示已持久化的 local scan 结果；不会自动全市场扫描。"
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
    if persisted and (
        persisted.get("source_snapshot_hash") == snapshot_hash
        or str(persisted.get("scan_mode") or "") in LOCAL_POOL_SCAN_MODES
    ):
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
    scan_mode = requested_scan_mode if requested_scan_mode in SUPPORTED_LOCAL_SCAN_MODES else "quick_cache_scan"
    request_params_safe = {
        "requested_scan_mode": requested_scan_mode,
        "scan_mode": scan_mode,
        "unsupported_scan_mode_fallback": requested_scan_mode != scan_mode,
        "universe_mode": payload_safe.get("universe_mode")
        or ("local_watchlist" if scan_mode == "watchlist_scan" else "manual_input" if scan_mode == "custom_pool_scan" else "cache_snapshot"),
        "external_sources_allowed": False,
        "local_pool_scan": scan_mode in LOCAL_POOL_SCAN_MODES,
    }
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    scan_snapshot: Mapping[str, Any] = snapshot
    local_pool_audit: dict[str, Any] = {}
    local_pool_skipped_rows: list[dict[str, Any]] = []
    if scan_mode in LOCAL_POOL_SCAN_MODES:
        scan_snapshot, local_pool_audit, local_pool_skipped_rows = _snapshot_with_local_candidate_pool(
            snapshot_map,
            payload_safe,
            scan_mode,
        )
        request_params_safe["candidate_pool_source"] = local_pool_audit.get("input_source")
        request_params_safe["input_candidate_count"] = local_pool_audit.get("input_candidate_count")
        request_params_safe["normalized_candidate_count"] = local_pool_audit.get("normalized_candidate_count")
    packet = _build_candidate_radar_packet(
        scan_snapshot,
        mode=scan_mode,
        cache_source=f"{scan_mode}_task",
        scan_mode=scan_mode,
        request_params_safe=request_params_safe,
        local_pool_audit=local_pool_audit,
        local_pool_skipped_rows=local_pool_skipped_rows,
    )
    task_scan_label = "quick_scan" if scan_mode == "quick_cache_scan" else scan_mode
    ledger_api = "local_candidate_radar_quick_scan" if scan_mode == "quick_cache_scan" else f"local_candidate_radar_{scan_mode}"
    quick_ledger = _candidate_call_ledger_row(
        api=ledger_api,
        source_snapshot="command_center_latest.json",
        row_count=len(_as_list(packet.get("candidate_rows"))),
        call_status=f"{task_scan_label}_completed" if scan_snapshot else f"{task_scan_label}_cache_missing",
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["quick_scan_completed_at"] = _now_iso()
    packet["local_scan_completed_at"] = packet["quick_scan_completed_at"]
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

    final_warning = f"candidate_radar_{task_scan_label}_completed_no_external_call"
    if not _as_list(packet.get("candidate_rows")):
        final_warning = f"candidate_radar_{task_scan_label}_completed_no_candidates_no_external_call"
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=f"candidate_radar_{task_scan_label}_completed",
        call_ledger=[quick_ledger],
        warning=final_warning,
    ) or task


def run_candidate_full_pool_plan_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_full_pool_plan",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_full_pool_plan_queued",
        warnings=[
            "下一票雷达 full-pool plan 只生成本地准备度计划；不会扫描全市场、不会调用 Tushare、DeepSeek 或 GitHub。",
            "计划结果只说明 worker、freshness、provider 覆盖和 legacy parity 阻断项；不会生成买入候选或修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="reading_local_candidate_radar_plan_inputs",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    now = _now_iso()
    plan = _build_full_pool_scan_plan(snapshot_map, payload_safe, now=now)
    request_params_safe = {
        "scan_mode": "full_pool_scan",
        "plan_only": True,
        "filter_count": len(plan.get("filter_rows") or []),
        "required_signal_group_count": plan.get("required_signal_group_count"),
        "blocking_issue_count": plan.get("blocking_issue_count"),
        "external_sources_allowed": False,
        "full_pool_scan_done": False,
    }
    packet = _build_candidate_radar_packet(
        snapshot_map,
        mode="full_pool_plan",
        cache_source="full_pool_plan_task",
        scan_mode="full_pool_plan",
        request_params_safe=request_params_safe,
        full_pool_scan_plan=plan,
    )
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_full_pool_plan",
        source_snapshot="command_center_latest.json",
        row_count=len(plan.get("blocker_rows") or []),
        call_status="full_pool_plan_ready",
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["full_pool_plan_completed_at"] = now
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 full-pool plan 只记录准备度和阻断项；不扫描全市场、不刷新 provider、不生成买入候选。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "full-pool plan" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "full_pool_plan_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_full_pool_plan_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_full_pool_plan_storage_write_failed",
            error_message_safe="candidate_radar_full_pool_plan_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_full_pool_plan_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_full_pool_plan_ready",
        call_ledger=[ledger],
        warning="candidate_radar_full_pool_plan_ready_no_external_call",
    ) or task
