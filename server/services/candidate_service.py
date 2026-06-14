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
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
CANDIDATE_BROWSER_QA_RUNBOOK_PATH = PROJECT_ROOT / "scripts" / "candidate_radar_browser_qa_runbook.py"
MOTION_BROWSER_QA_RUNNER_PATH = PROJECT_ROOT / "scripts" / "motion_browser_qa_runner.mjs"
MOTION_QA_ARTIFACT_ROOT = PROJECT_ROOT / ".stock_ming_3" / "motion_qa"
CANDIDATE_ROUTE_SOURCE_PATH = PROJECT_ROOT / "desktop" / "src" / "routes" / "CandidateRadar.tsx"
SUPPORTED_LOCAL_SCAN_MODES = {"quick_cache_scan", "watchlist_scan", "custom_pool_scan", "full_pool_local_scan"}
LOCAL_POOL_SCAN_MODES = {"watchlist_scan", "custom_pool_scan", "full_pool_local_scan"}
FAST_SCAN_DISPLAY_CANDIDATE_LIMIT = 120
FAST_SCAN_LOCAL_POOL_INPUT_LIMIT = 50
FULL_POOL_LOCAL_INPUT_LIMIT = 500
FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD = 500
PRIORITY_EXPLANATION_LIMIT = 30
SAFE_LIST_LIMIT = 200
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
        "scan_mode": "full_pool_local_scan",
        "status": "implemented_local_universe_receipt",
        "scope": "explicit local universe payload/cache execution",
        "external_calls": False,
        "notes": "Consumes a local universe payload or cached candidates and writes a local execution receipt; it is not provider-backed full-market production acceptance.",
    },
    {
        "scan_mode": "deep_scan",
        "status": "implemented_plan_only",
        "scope": "legacy parity, provider, freshness, worker, and action-boundary readiness",
        "external_calls": False,
        "notes": "Deep-scan plan is a local readiness checklist; it does not scan, refresh providers, score candidates, or call DeepSeek.",
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
        return [_safe_value(item, depth=depth + 1) for item in value[:SAFE_LIST_LIMIT]]
    if isinstance(value, tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:SAFE_LIST_LIMIT]]
    return _safe_text(value)


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "candidate_radar_cache_not_json_serializable"}


def _read_local_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


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
    elif scan_mode == "full_pool_local_scan":
        keys = [
            "full_pool_candidates",
            "universe_candidates",
            "local_universe_candidates",
            "local_universe",
            "candidates",
            "targets",
        ]
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
    if scan_mode == "custom_pool_scan":
        text_value = payload_safe.get("custom_pool_text")
    elif scan_mode == "full_pool_local_scan":
        text_value = payload_safe.get("full_pool_text") or payload_safe.get("local_universe_text")
    else:
        text_value = payload_safe.get("watchlist_text")
    text_rows = _split_candidate_text(text_value)
    if text_rows and not rows:
        rows.extend(text_rows)
        if scan_mode == "custom_pool_scan":
            source_key = "payload.custom_pool_text"
        elif scan_mode == "full_pool_local_scan":
            source_key = "payload.full_pool_text"
        else:
            source_key = "payload.watchlist_text"
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
    max_items: int = FAST_SCAN_LOCAL_POOL_INPUT_LIMIT,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()
    disabled_count = 0
    invalid_count = 0
    duplicate_count = 0
    truncated_count = max(0, len(raw_items) - max_items)
    if scan_mode == "watchlist_scan":
        source_label = "持续调查池本地输入"
    elif scan_mode == "full_pool_local_scan":
        source_label = "本地 full-pool universe 输入"
    else:
        source_label = "自定义候选池本地输入"

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
        "skipped_candidate_count": disabled_count + invalid_count + duplicate_count + truncated_count,
        "max_local_candidates": max_items,
        "sync_input_limit": max_items,
        "requires_worker_when_over_limit": truncated_count > 0,
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
    if scan_mode == "full_pool_local_scan" and not raw_items:
        radar_packet = _as_dict(snapshot_map.get("radar_packet") or snapshot_map.get("command_center_radar_packet"))
        raw_items = _as_list(snapshot_map.get("next_ticket_candidates")) or _as_list(radar_packet.get("top_candidates"))
        input_source = "snapshot.next_ticket_candidates_or_radar_top_candidates" if raw_items else input_source
    max_items = FULL_POOL_LOCAL_INPUT_LIMIT if scan_mode == "full_pool_local_scan" else FAST_SCAN_LOCAL_POOL_INPUT_LIMIT
    candidates, skipped, audit = _normalize_local_pool_candidates(
        raw_items,
        scan_mode=scan_mode,
        input_source=input_source,
        max_items=max_items,
    )
    overlay = dict(snapshot_map)
    existing_radar = _as_dict(snapshot_map.get("radar_packet") or snapshot_map.get("command_center_radar_packet"))
    if scan_mode == "watchlist_scan":
        source_text = "持续调查池本地扫描"
    elif scan_mode == "full_pool_local_scan":
        source_text = "本地 full-pool universe 执行"
    else:
        source_text = "自定义候选池本地扫描"
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


def _candidate_rows(candidates: Any, *, max_rows: int = FAST_SCAN_DISPLAY_CANDIDATE_LIMIT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, raw in enumerate(_as_list(candidates)[:max_rows], start=1):
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


def _raw_candidate_input_count(snapshot: Mapping[str, Any]) -> int:
    raw_radar = _as_dict(snapshot.get("radar_packet") or snapshot.get("command_center_radar_packet"))
    raw_candidates = _as_list(snapshot.get("next_ticket_candidates")) or _as_list(raw_radar.get("top_candidates"))
    return len(raw_candidates)


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


def _candidate_data_gap_count(row: Mapping[str, Any]) -> int:
    value = row.get("data_gaps")
    if isinstance(value, list):
        return len([item for item in value if item not in (None, "", [], {})])
    if value in (None, "", [], {}):
        return 0
    return 1


def _candidate_priority_bucket(row: Mapping[str, Any], gap_count: int) -> str:
    action_text = str(row.get("action_state") or row.get("status_label") or row.get("tone") or "")
    if gap_count:
        return "gap_first_review"
    if "验证" in action_text:
        return "verification_required"
    if "观察" in action_text:
        return "observe_only"
    if str(row.get("score") or "").strip():
        return "ranked_cache_candidate"
    return "manual_review_required"


def _candidate_explanation_missing_fields(row: Mapping[str, Any]) -> list[str]:
    required_fields = [
        "rank",
        "ticker",
        "score",
        "evidence_chain_summary",
        "trigger_condition",
        "invalidation_condition",
        "data_gaps",
        "action_state",
    ]
    return [field for field in required_fields if row.get(field) in (None, "", [], {})]


def _candidate_priority_explanation_contract(
    candidate_rows: list[dict[str, Any]],
    *,
    scan_mode: str,
    coverage: Mapping[str, Any],
) -> dict[str, Any]:
    freshness_state = _as_dict(coverage.get("freshness_state"))
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(candidate_rows[:PRIORITY_EXPLANATION_LIMIT], start=1):
        gap_count = _candidate_data_gap_count(row)
        missing_fields = _candidate_explanation_missing_fields(row)
        explanation_status = (
            "gap_visible"
            if gap_count
            else "partial_cache_explanation"
            if missing_fields
            else "complete_cache_explanation"
        )
        rows.append(
            {
                "display_rank": row.get("rank") or index,
                "ticker": row.get("ticker"),
                "name": row.get("name"),
                "cached_score": row.get("score"),
                "priority_bucket": _candidate_priority_bucket(row, gap_count),
                "explanation_status": explanation_status,
                "rank_source": "existing_candidate_rows_order",
                "score_source": "existing_cache_score_preserved" if row.get("score") not in (None, "") else "score_missing",
                "action_state": row.get("action_state"),
                "status_label": row.get("status_label"),
                "evidence_summary_present": row.get("evidence_chain_summary") not in (None, "", [], {}),
                "trigger_condition_present": row.get("trigger_condition") not in (None, "", [], {}),
                "invalidation_condition_present": row.get("invalidation_condition") not in (None, "", [], {}),
                "data_gap_count": gap_count,
                "missing_explanation_fields": missing_fields,
                "manual_review_required": True,
                "uses_existing_rank_only": True,
                "uses_existing_score_only": True,
                "does_not_recompute_score": True,
                "does_not_sort_candidates": True,
                "candidate_is_not_buy_instruction": True,
                "does_not_modify_strategy_action": True,
                "does_not_execute_trades": True,
            }
        )
    explanation_gap_count = sum(1 for row in rows if row["explanation_status"] != "complete_cache_explanation")
    data_gap_visible_count = sum(1 for row in rows if int(row.get("data_gap_count") or 0) > 0)
    missing_score_count = sum(1 for row in rows if row["score_source"] == "score_missing")
    return {
        "schema_version": "candidate_radar_priority_explanation.v1",
        "status": "candidate_priority_explanation_ready" if rows else "candidate_priority_explanation_empty",
        "scope": "local_cache_rank_explanation_not_rescore_or_trade_signal",
        "scan_mode": scan_mode,
        "row_limit": PRIORITY_EXPLANATION_LIMIT,
        "candidate_row_count": len(candidate_rows),
        "explained_candidate_count": len(rows),
        "explanation_gap_count": explanation_gap_count,
        "data_gap_visible_count": data_gap_visible_count,
        "missing_score_count": missing_score_count,
        "freshness_state": freshness_state.get("state") or "unknown",
        "freshness_source": freshness_state.get("source") or "missing",
        "sort_order_source": "existing_candidate_rows_order",
        "cached_rank_preserved": True,
        "cached_score_preserved": True,
        "uses_existing_rank_only": True,
        "uses_existing_score_only": True,
        "does_not_recompute_score": True,
        "does_not_sort_candidates": True,
        "does_not_calculate_action": True,
        "manual_review_required": True,
        "priority_explanation_is_not_trade_signal": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "production_radar_replacement_complete": False,
        "row_count": len(rows),
        "rows": rows,
        "note": "This contract explains visible cached candidate rank/score and missing evidence fields. It does not rescore, reorder, refresh providers, call models, or create trading instructions.",
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


def _legacy_parity_acceptance_row(
    item_key: str,
    category: str,
    label: str,
    status: str,
    *,
    local_contract_passed: bool,
    production_ready: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "item_key": item_key,
        "category": category,
        "label": label,
        "status": status,
        "local_contract_passed": bool(local_contract_passed),
        "production_ready": bool(production_ready),
        "blocks_production_replacement": not bool(production_ready),
        "gap_visible": not bool(production_ready),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _legacy_parity_acceptance_receipt(
    *,
    parity_inventory: Mapping[str, Any],
    parity_rows: list[dict[str, Any]],
    output_contract_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    production_ready_statuses = {"mapped", "mapped_from_cache"}
    rows: list[dict[str, Any]] = []
    for row in parity_rows:
        migration_status = str(row.get("migration_status") or "missing_reported")
        production_ready = migration_status in production_ready_statuses
        rows.append(
            _legacy_parity_acceptance_row(
                str(row.get("key") or ""),
                "legacy_parity_item",
                str(row.get("label") or row.get("key") or ""),
                "production_ready" if production_ready else "gap_visible",
                local_contract_passed=True,
                production_ready=production_ready,
                evidence=(
                    f"migration_status={migration_status}; present_in_current_cache="
                    f"{bool(row.get('present_in_current_cache'))}; target={row.get('target_state')}"
                ),
                next_action=(
                    "Keep mapped behavior covered in React/cache acceptance."
                    if production_ready
                    else "Map this legacy radar behavior with provider/worker/browser evidence or keep Streamlit fallback visible."
                ),
            )
        )
    for row in output_contract_rows:
        present = row.get("present") is True
        rows.append(
            _legacy_parity_acceptance_row(
                str(row.get("field") or ""),
                "legacy_output_field",
                str(row.get("field") or ""),
                "production_ready" if present else "missing_reported",
                local_contract_passed=True,
                production_ready=present,
                evidence=f"source={row.get('source')}; required_for={row.get('required_for')}; present={present}",
                next_action=(
                    "Preserve this output field in Candidate Radar replacement."
                    if present
                    else "Expose this missing output field as a gap; do not invent values before retiring legacy radar."
                ),
            )
        )
    local_blockers = [row["item_key"] for row in rows if not row.get("local_contract_passed")]
    production_blockers = [row["item_key"] for row in rows if row.get("blocks_production_replacement")]
    ready_count = sum(1 for row in rows if row.get("production_ready"))
    receipt = {
        "schema_version": "candidate_radar_legacy_parity_acceptance_receipt.v1",
        "status": "legacy_parity_acceptance_local_ready_production_pending" if not local_blockers else "legacy_parity_acceptance_blocked",
        "scope": "local_legacy_radar_parity_acceptance_not_production_replacement",
        "ltg": "LTG-13",
        "local_acceptance_receipt_ready": not local_blockers,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "parity_inventory_status": parity_inventory.get("status"),
        "parity_item_count": int(parity_inventory.get("parity_row_count") or len(parity_rows)),
        "mapped_or_partial_count": int(parity_inventory.get("mapped_or_partial_count") or 0),
        "gap_or_future_count": int(parity_inventory.get("gap_or_future_count") or 0),
        "output_contract_field_count": int(parity_inventory.get("output_contract_field_count") or len(output_contract_rows)),
        "output_contract_mapped_count": int(parity_inventory.get("output_contract_mapped_count") or 0),
        "receipt_row_count": len(rows),
        "production_ready_count": ready_count,
        "production_blocker_count": len(production_blockers),
        "local_blocker_count": len(local_blockers),
        "production_blockers": production_blockers,
        "local_blockers": local_blockers,
        "required_before_legacy_retirement": [
            "top_watch_excluded_split",
            "evidence_links",
            "scoring_dimensions",
            "trigger_invalidation",
            "holding_comparison",
            "candidate_pool_sources",
            "scan_filters",
            "timeout_and_fallback",
            "manual_deep_research",
            "legacy_output_contract_fields",
        ],
        "not_allowed_next_steps": [
            "treat_gap_reported_as_feature_parity_complete",
            "retire_streamlit_radar_before_provider_worker_browser_acceptance",
            "claim_quick_scan_as_full_replacement",
            "invent_missing_legacy_output_fields",
            "convert_candidate_score_to_strategy_action",
        ],
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "browser_visual_qa_done": False,
        "browser_performance_trace_done": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_candidate_radar_legacy_parity_acceptance_receipt",
                "source_snapshot": "legacy_parity_rows_and_output_contract_rows",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_parity_acceptance_receipt",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This receipt turns legacy next-ticket radar parity into explicit acceptance rows. It is local evidence only; production replacement still requires provider-backed parity, worker full/deep scans, browser visual/performance QA, and legacy retirement review.",
    }
    return receipt, rows


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
    candidate_input_count: int = 0,
    candidate_display_limit: int = FAST_SCAN_DISPLAY_CANDIDATE_LIMIT,
    candidate_display_truncated_count: int = 0,
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
    if candidate_display_truncated_count:
        rows.append(
            {
                "reason": "candidate_rows_display_capped",
                "group": "next_ticket_candidates",
                "severity": "ui_runtime_budget",
                "input_candidate_count": candidate_input_count,
                "display_limit": candidate_display_limit,
                "truncated_candidate_count": candidate_display_truncated_count,
                "action": "show_runtime_budget_contract_and_require_worker_for_large_universe",
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
    candidate_input_count: int = 0,
    candidate_display_truncated_count: int = 0,
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
        candidate_input_count=candidate_input_count,
        candidate_display_limit=FAST_SCAN_DISPLAY_CANDIDATE_LIMIT,
        candidate_display_truncated_count=candidate_display_truncated_count,
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
        else candidate_input_count + len(excluded_candidates)
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
        "candidate_input_count": int(candidate_input_count or 0),
        "candidate_count": len(candidate_rows),
        "candidate_display_limit": FAST_SCAN_DISPLAY_CANDIDATE_LIMIT,
        "candidate_display_truncated_count": int(candidate_display_truncated_count or 0),
        "candidate_rows_capped_for_ui": bool(candidate_display_truncated_count),
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
        "large_universe_requires_worker": int(universe_size or 0) > FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD,
        "worker_required_universe_threshold": FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD,
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
        "candidate_input_count": int(candidate_input_count or 0),
        "candidate_display_limit": FAST_SCAN_DISPLAY_CANDIDATE_LIMIT,
        "candidate_display_truncated_count": int(candidate_display_truncated_count or 0),
        "candidate_rows_capped_for_ui": bool(candidate_display_truncated_count),
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
        "large_universe_requires_worker": int(universe_size or 0) > FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD,
        "worker_required_universe_threshold": FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD,
        "watchlist_scan_reads_local_input_only": scan_mode == "watchlist_scan",
        "custom_pool_scan_reads_local_input_only": scan_mode == "custom_pool_scan",
        "does_not_scan_full_market_on_render": True,
        "does_not_call_external_sources": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _scan_execution_summary(
    *,
    mode: str,
    cache_source: str,
    scan_mode: str,
    request_params_safe: Mapping[str, Any],
    coverage: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    local_pool_audit: Mapping[str, Any],
    full_pool_scan_plan: Mapping[str, Any],
    deep_scan_plan: Mapping[str, Any],
) -> dict[str, Any]:
    coverage_detail = _as_dict(coverage.get("coverage_detail_summary"))
    freshness_state = _as_dict(coverage.get("freshness_state"))
    provider_gap_count = int(coverage_detail.get("provider_blocked_group_count") or 0) + int(
        coverage_detail.get("stale_input_group_count") or 0
    ) + int(coverage_detail.get("missing_provider_data_group_count") or 0)
    scan_family = (
        "full_pool_plan"
        if scan_mode == "full_pool_plan"
        else "full_pool_local_execution"
        if scan_mode == "full_pool_local_scan"
        else "deep_scan_plan"
        if scan_mode == "deep_scan_plan"
        else "local_pool_scan"
        if scan_mode in LOCAL_POOL_SCAN_MODES
        else "quick_cache_scan"
        if scan_mode == "quick_cache_scan"
        else "cache_view"
    )
    return {
        "schema_version": "candidate_radar_scan_execution_summary.v1",
        "mode": mode,
        "scan_mode": scan_mode,
        "scan_family": scan_family,
        "cache_source": cache_source,
        "requested_scan_mode": request_params_safe.get("requested_scan_mode") or request_params_safe.get("scan_mode") or scan_mode,
        "unsupported_scan_mode_fallback": bool(request_params_safe.get("unsupported_scan_mode_fallback")),
        "universe_mode": coverage_detail.get("universe_mode") or request_params_safe.get("universe_mode") or coverage.get("universe_mode"),
        "universe_size": int(coverage_detail.get("universe_size") or coverage.get("universe_size") or 0),
        "candidate_input_count": int(coverage_detail.get("candidate_input_count") or 0),
        "candidate_row_count": len(candidate_rows),
        "candidate_display_limit": int(coverage_detail.get("candidate_display_limit") or FAST_SCAN_DISPLAY_CANDIDATE_LIMIT),
        "candidate_display_truncated_count": int(coverage_detail.get("candidate_display_truncated_count") or 0),
        "candidate_rows_capped_for_ui": bool(coverage_detail.get("candidate_rows_capped_for_ui")),
        "skipped_reason_count": int(coverage.get("skipped_reason_count") or 0),
        "provider_gap_count": provider_gap_count,
        "degraded_mode_active_count": int(coverage_detail.get("degraded_mode_active_count") or 0),
        "freshness_state": freshness_state.get("state") or "unknown",
        "freshness_source": freshness_state.get("source") or "missing",
        "local_pool_input_candidate_count": local_pool_audit.get("input_candidate_count"),
        "local_pool_normalized_candidate_count": local_pool_audit.get("normalized_candidate_count"),
        "full_pool_plan_ready": full_pool_scan_plan.get("status") == "full_pool_plan_ready",
        "full_pool_scan_done": bool(full_pool_scan_plan.get("full_pool_scan_done") is True),
        "full_pool_blocking_issue_count": full_pool_scan_plan.get("blocking_issue_count"),
        "deep_scan_plan_ready": deep_scan_plan.get("status") == "deep_scan_plan_ready",
        "deep_scan_done": bool(deep_scan_plan.get("deep_scan_done") is True),
        "deep_scan_blocking_issue_count": deep_scan_plan.get("blocking_issue_count"),
        "writes_sqlite_packet": mode != "cache_only",
        "cache_view_only": mode == "cache_only",
        "result_is_research_only": True,
        "candidate_is_not_buy_instruction": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _scan_acceptance_rows(
    *,
    scan_mode: str,
    coverage: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    local_pool_audit: Mapping[str, Any],
    full_pool_scan_plan: Mapping[str, Any],
    deep_scan_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    coverage_detail = _as_dict(coverage.get("coverage_detail_summary"))
    freshness_state = _as_dict(coverage.get("freshness_state"))
    full_pool_plan_ready = full_pool_scan_plan.get("status") == "full_pool_plan_ready"
    provider_gap_count = int(coverage_detail.get("provider_blocked_group_count") or 0) + int(
        coverage_detail.get("stale_input_group_count") or 0
    ) + int(coverage_detail.get("missing_provider_data_group_count") or 0)
    freshness_ok = freshness_state.get("source") != "missing" and str(freshness_state.get("state") or "").lower() not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    deep_scan_plan_ready = deep_scan_plan.get("status") == "deep_scan_plan_ready"
    rows = [
        {
            "check_key": "page_render_does_not_scan",
            "status": "passed",
            "observed": "GET cache and React render are read-only.",
            "user_visible": True,
        },
        {
            "check_key": "external_call_boundary",
            "status": "passed",
            "observed": "No Tushare, DeepSeek, or GitHub call is made by this radar packet.",
            "user_visible": True,
        },
        {
            "check_key": "scan_mode_contract",
            "status": "passed"
            if scan_mode in SUPPORTED_LOCAL_SCAN_MODES or scan_mode in {"cache_only", "full_pool_plan"}
            else "fallback_reported",
            "observed": scan_mode,
            "user_visible": True,
        },
        {
            "check_key": "candidate_result_boundary",
            "status": "ready" if candidate_rows else "empty_reported",
            "observed": f"{len(candidate_rows)} candidate rows; result remains research-only.",
            "user_visible": True,
        },
        {
            "check_key": "provider_gap_visibility",
            "status": "gap_reported" if provider_gap_count else "passed",
            "observed": f"{provider_gap_count} provider gaps reported without refresh.",
            "user_visible": True,
        },
        {
            "check_key": "freshness_boundary",
            "status": "passed" if freshness_ok else "research_only_reported",
            "observed": f"{freshness_state.get('source') or 'missing'}:{freshness_state.get('state') or 'unknown'}",
            "user_visible": True,
        },
        {
            "check_key": "local_pool_boundary",
            "status": "input_reported" if local_pool_audit else "not_applicable",
            "observed": f"input={local_pool_audit.get('input_candidate_count')} normalized={local_pool_audit.get('normalized_candidate_count')}"
            if local_pool_audit
            else "quick cache or full-pool plan does not consume local pool input.",
            "user_visible": True,
        },
        {
            "check_key": "full_pool_boundary",
            "status": "local_execution_receipt" if scan_mode == "full_pool_local_scan" else "plan_only" if full_pool_plan_ready else "not_executed",
            "observed": (
                "local_full_pool_execution_done=true; production_full_pool_scan_done=false; provider_refresh_executed=false."
                if scan_mode == "full_pool_local_scan"
                else "full_pool_scan_done=false; plan does not score candidates or refresh providers."
            ),
            "user_visible": True,
        },
        {
            "check_key": "deep_scan_boundary",
            "status": "plan_only" if deep_scan_plan_ready else "not_executed",
            "observed": "deep_scan_done=false; plan records no-feature-loss readiness and does not call providers or DeepSeek.",
            "user_visible": True,
        },
        {
            "check_key": "feature_loss_boundary",
            "status": "gap_reported"
            if int(deep_scan_plan.get("legacy_feature_gap_count") or 0)
            else "passed"
            if deep_scan_plan_ready
            else "not_executed",
            "observed": f"{deep_scan_plan.get('legacy_feature_gap_count') or 0} legacy feature gaps visible.",
            "user_visible": True,
        },
        {
            "check_key": "trade_action_boundary",
            "status": "passed",
            "observed": "Radar candidates do not modify strategy action, holdings, or execute trades.",
            "user_visible": True,
        },
    ]
    for row in rows:
        row.update(
            {
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "candidate_is_not_buy_instruction": True,
            }
        )
    return rows


def _runtime_budget_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    user_visible: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "evidence": evidence,
        "user_visible": user_visible,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _fast_scan_runtime_budget_contract(
    *,
    scan_mode: str,
    coverage: Mapping[str, Any],
    local_pool_audit: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    coverage_detail = _as_dict(coverage.get("coverage_detail_summary"))
    universe_size = int(coverage_detail.get("universe_size") or 0)
    input_count = int(coverage_detail.get("candidate_input_count") or 0)
    truncated_count = int(coverage_detail.get("candidate_display_truncated_count") or 0)
    local_pool_input_count = local_pool_audit.get("input_candidate_count")
    local_pool_truncated_count = int(local_pool_audit.get("truncated_candidate_count") or 0)
    worker_required = universe_size > FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD or local_pool_truncated_count > 0
    rows = [
        _runtime_budget_row(
            "page_render_zero_scan_budget",
            "passed",
            passed=True,
            evidence="React render and GET cache do not start candidate scans or provider refresh.",
        ),
        _runtime_budget_row(
            "sync_candidate_display_budget",
            "capped_visible" if truncated_count else "passed",
            passed=True,
            evidence=f"input={input_count}; displayed={len(candidate_rows)}; limit={FAST_SCAN_DISPLAY_CANDIDATE_LIMIT}; truncated={truncated_count}",
        ),
        _runtime_budget_row(
            "local_pool_sync_input_budget",
            "capped_visible" if local_pool_truncated_count else "passed",
            passed=True,
            evidence=f"input={local_pool_input_count}; limit={FAST_SCAN_LOCAL_POOL_INPUT_LIMIT}; truncated={local_pool_truncated_count}",
        ),
        _runtime_budget_row(
            "large_universe_worker_boundary",
            "worker_required" if worker_required else "not_required",
            passed=True,
            evidence=f"universe_size={universe_size}; threshold={FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD}",
        ),
        _runtime_budget_row(
            "feature_gap_visibility_budget",
            "passed",
            passed=True,
            evidence="Candidate display caps, provider gaps, stale inputs, and missing legacy groups are reported as rows instead of being hidden.",
        ),
    ]
    return {
        "schema_version": "candidate_radar_fast_scan_runtime_budget.v1",
        "status": "fast_scan_runtime_budget_ready",
        "scope": "local_sync_budget_contract_not_browser_performance_trace",
        "scan_mode": scan_mode,
        "display_candidate_limit": FAST_SCAN_DISPLAY_CANDIDATE_LIMIT,
        "local_pool_input_limit": FAST_SCAN_LOCAL_POOL_INPUT_LIMIT,
        "worker_required_universe_threshold": FAST_SCAN_WORKER_REQUIRED_UNIVERSE_THRESHOLD,
        "candidate_input_count": input_count,
        "candidate_displayed_count": len(candidate_rows),
        "candidate_display_truncated_count": truncated_count,
        "candidate_rows_capped_for_ui": bool(truncated_count),
        "local_pool_input_candidate_count": local_pool_input_count,
        "local_pool_truncated_candidate_count": local_pool_truncated_count,
        "large_universe_worker_required": worker_required,
        "browser_performance_trace_done": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "feature_gaps_visible": True,
        "cache_get_starts_scan": False,
        "page_render_starts_scan": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "row_count": len(rows),
        "rows": rows,
        "note": "This is a static runtime-budget contract for local quick/watchlist/custom scans; browser performance traces and real full-pool worker execution remain future validation.",
    }


def _quick_scan_receipt_row(
    receipt_key: str,
    status: str,
    *,
    local_contract_passed: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "receipt_key": receipt_key,
        "status": status,
        "local_contract_passed": bool(local_contract_passed),
        "production_blocker": bool(production_blocker),
        "user_visible": True,
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _quick_scan_receipt_rows(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    scan_summary = _as_dict(packet.get("scan_execution_summary"))
    coverage = _as_dict(packet.get("scan_coverage"))
    coverage_detail = _as_dict(packet.get("coverage_detail_summary"))
    runtime_budget = _as_dict(packet.get("fast_scan_runtime_budget_contract"))
    parity = _as_dict(packet.get("legacy_parity_inventory"))
    result_delta = _as_dict(packet.get("result_delta_clarity_contract"))
    local_pool = _as_dict(packet.get("local_candidate_pool_audit"))
    freshness = _as_dict(packet.get("freshness_state"))
    full_pool_plan = _as_dict(packet.get("full_pool_scan_plan"))
    deep_scan_plan = _as_dict(packet.get("deep_scan_plan"))
    call_ledger = _as_list(packet.get("call_ledger"))
    candidate_rows = _as_list(packet.get("candidate_rows"))
    scan_mode = str(packet.get("scan_mode") or scan_summary.get("scan_mode") or "cache_only")
    freshness_state = str(freshness.get("state") or scan_summary.get("freshness_state") or "unknown").lower()
    freshness_ready = freshness.get("source") != "missing" and freshness_state not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    provider_gap_count = int(scan_summary.get("provider_gap_count") or 0)
    if not provider_gap_count:
        provider_gap_count = int(coverage_detail.get("provider_blocked_group_count") or 0) + int(
            coverage_detail.get("stale_input_group_count") or 0
        ) + int(coverage_detail.get("missing_provider_data_group_count") or 0)
    legacy_gap_count = int(coverage.get("missing_signal_group_count") or parity.get("gap_or_future_count") or 0)
    full_pool_done = bool(full_pool_plan.get("full_pool_scan_done") is True or scan_summary.get("full_pool_scan_done") is True)
    deep_scan_done = bool(deep_scan_plan.get("deep_scan_done") is True or scan_summary.get("deep_scan_done") is True)
    local_pool_input_count = local_pool.get("input_candidate_count")
    local_pool_truncated_count = int(local_pool.get("truncated_candidate_count") or 0)
    return [
        _quick_scan_receipt_row(
            "scan_mode_visible",
            "passed" if scan_mode else "missing",
            local_contract_passed=bool(scan_mode),
            production_blocker=False,
            evidence=f"scan_mode={scan_mode}; scan_family={scan_summary.get('scan_family') or 'missing'}",
            next_action="Keep scan mode and scan family visible before interpreting candidate rows.",
        ),
        _quick_scan_receipt_row(
            "task_or_cache_receipt_visible",
            "passed" if scan_summary and call_ledger else "missing_receipt",
            local_contract_passed=bool(scan_summary and call_ledger),
            production_blocker=False,
            evidence=f"call_ledger_count={len(call_ledger)}; writes_sqlite_packet={scan_summary.get('writes_sqlite_packet')}",
            next_action="Use the visible call ledger and scan summary as the local receipt for cache reads or button-gated scans.",
        ),
        _quick_scan_receipt_row(
            "candidate_count_visible",
            "passed",
            local_contract_passed=True,
            production_blocker=False,
            evidence=f"candidate_rows={len(candidate_rows)}; input={scan_summary.get('candidate_input_count')}; display_limit={scan_summary.get('candidate_display_limit')}; truncated={scan_summary.get('candidate_display_truncated_count')}",
            next_action="Keep displayed count, input count, display limit, and truncation visible to avoid hiding scan shrinkage.",
        ),
        _quick_scan_receipt_row(
            "runtime_budget_visible",
            "passed" if runtime_budget.get("schema_version") == "candidate_radar_fast_scan_runtime_budget.v1" else "missing",
            local_contract_passed=runtime_budget.get("schema_version") == "candidate_radar_fast_scan_runtime_budget.v1",
            production_blocker=False,
            evidence=f"large_universe_worker_required={runtime_budget.get('large_universe_worker_required')}; browser_performance_trace_done={runtime_budget.get('browser_performance_trace_done')}",
            next_action="Keep sync display caps and worker boundary visible; run browser traces before production replacement.",
        ),
        _quick_scan_receipt_row(
            "legacy_signal_coverage_visible",
            "gap_reported" if legacy_gap_count else "passed",
            local_contract_passed=True,
            production_blocker=legacy_gap_count > 0,
            evidence=f"mapped={coverage.get('mapped_signal_group_count')}; missing_or_future={legacy_gap_count}",
            next_action="Map remaining legacy signal groups or keep fallback visible before claiming no feature loss.",
        ),
        _quick_scan_receipt_row(
            "provider_gap_visible",
            "gap_reported" if provider_gap_count else "passed",
            local_contract_passed=True,
            production_blocker=provider_gap_count > 0,
            evidence=f"provider_gap_count={provider_gap_count}",
            next_action="Validate provider-backed parity through explicit future tasks; do not refresh providers on render.",
        ),
        _quick_scan_receipt_row(
            "freshness_boundary_visible",
            "passed" if freshness_ready else "research_only_reported",
            local_contract_passed=True,
            production_blocker=not freshness_ready,
            evidence=f"freshness={freshness.get('source') or 'missing'}:{freshness_state}",
            next_action="Require trading-calendar freshness before treating radar rows as current evidence.",
        ),
        _quick_scan_receipt_row(
            "local_pool_limit_visible",
            "capped_visible" if local_pool_truncated_count else "passed" if local_pool else "not_applicable",
            local_contract_passed=True,
            production_blocker=False,
            evidence=f"local_pool_input={local_pool_input_count}; truncated={local_pool_truncated_count}; input_limit={FAST_SCAN_LOCAL_POOL_INPUT_LIMIT}",
            next_action="Keep watchlist/custom-pool normalization and truncation visible for non-blocking local scans.",
        ),
        _quick_scan_receipt_row(
            "result_delta_visible",
            "passed" if result_delta.get("schema_version") == "candidate_radar_result_delta_clarity.v1" else "missing",
            local_contract_passed=result_delta.get("schema_version") == "candidate_radar_result_delta_clarity.v1",
            production_blocker=False,
            evidence=f"previous_cache_diff_done={result_delta.get('previous_cache_diff_done')}; browser_visual_delta_qa_done={result_delta.get('browser_visual_delta_qa_done')}",
            next_action="Keep previous-cache diff visible when available; browser visual QA remains a separate acceptance step.",
        ),
        _quick_scan_receipt_row(
            "full_deep_provider_blockers_visible",
            "pending_production_acceptance" if not (full_pool_done and deep_scan_done and provider_gap_count == 0) else "passed",
            local_contract_passed=True,
            production_blocker=not (full_pool_done and deep_scan_done and provider_gap_count == 0),
            evidence=f"full_pool_scan_done={full_pool_done}; deep_scan_done={deep_scan_done}; provider_gap_count={provider_gap_count}",
            next_action="Complete worker-backed full-pool/deep-scan and provider-backed acceptance before retiring legacy radar.",
        ),
        _quick_scan_receipt_row(
            "trade_action_isolation",
            "passed"
            if packet.get("does_not_execute_trades") is True and packet.get("does_not_modify_strategy_action") is True
            else "blocked",
            local_contract_passed=packet.get("does_not_execute_trades") is True
            and packet.get("does_not_modify_strategy_action") is True,
            production_blocker=False,
            evidence="Candidate radar remains research-only and does not mutate action, holdings, or orders.",
            next_action="Keep radar candidates separate from strategy action and real-trading paths.",
        ),
    ]


def _attach_quick_scan_receipt_contract(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    rows = _quick_scan_receipt_rows(view)
    local_blockers = [row["receipt_key"] for row in rows if not row.get("local_contract_passed")]
    production_blockers = [row["receipt_key"] for row in rows if row.get("production_blocker")]
    scan_summary = _as_dict(view.get("scan_execution_summary"))
    coverage_detail = _as_dict(view.get("coverage_detail_summary"))
    local_pool = _as_dict(view.get("local_candidate_pool_audit"))
    freshness = _as_dict(view.get("freshness_state"))
    contract = {
        "schema_version": "candidate_radar_quick_scan_receipt.v1",
        "status": "quick_scan_receipt_ready_local_only" if not local_blockers else "quick_scan_receipt_blocked",
        "scope": "local_candidate_radar_quick_scan_receipt_not_production_replacement",
        "ltg": "LTG-13",
        "scan_mode": view.get("scan_mode") or scan_summary.get("scan_mode"),
        "scan_family": scan_summary.get("scan_family"),
        "cache_source": view.get("cache_source") or scan_summary.get("cache_source"),
        "requested_scan_mode": scan_summary.get("requested_scan_mode"),
        "unsupported_scan_mode_fallback": bool(scan_summary.get("unsupported_scan_mode_fallback")),
        "candidate_input_count": int(scan_summary.get("candidate_input_count") or coverage_detail.get("candidate_input_count") or 0),
        "candidate_row_count": len(_as_list(view.get("candidate_rows"))),
        "candidate_display_limit": int(
            scan_summary.get("candidate_display_limit") or coverage_detail.get("candidate_display_limit") or FAST_SCAN_DISPLAY_CANDIDATE_LIMIT
        ),
        "candidate_display_truncated_count": int(
            scan_summary.get("candidate_display_truncated_count")
            or coverage_detail.get("candidate_display_truncated_count")
            or 0
        ),
        "local_pool_input_candidate_count": local_pool.get("input_candidate_count"),
        "local_pool_truncated_candidate_count": int(local_pool.get("truncated_candidate_count") or 0),
        "mapped_signal_group_count": int(_as_dict(view.get("scan_coverage")).get("mapped_signal_group_count") or 0),
        "missing_signal_group_count": int(_as_dict(view.get("scan_coverage")).get("missing_signal_group_count") or 0),
        "provider_gap_count": int(scan_summary.get("provider_gap_count") or 0),
        "degraded_mode_active_count": int(scan_summary.get("degraded_mode_active_count") or 0),
        "freshness_state": freshness.get("state") or scan_summary.get("freshness_state") or "unknown",
        "freshness_source": freshness.get("source") or scan_summary.get("freshness_source") or "missing",
        "writes_sqlite_packet": bool(scan_summary.get("writes_sqlite_packet") is True),
        "cache_view_only": bool(scan_summary.get("cache_view_only") is True),
        "local_quick_scan_receipt_ready": not local_blockers,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "browser_performance_trace_done": False,
        "browser_visual_delta_qa_done": False,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This receipt is local/cache-only. It makes fast-scan coverage, limits, gaps, and blockers visible; it is not full-pool, deep-scan, provider-backed, browser-performance, or production replacement evidence.",
    }
    counts = dict(_as_dict(view.get("counts")))
    counts["quick_scan_receipt_row_count"] = contract["row_count"]
    counts["quick_scan_receipt_local_blocker_count"] = contract["local_blocker_count"]
    counts["quick_scan_receipt_production_blocker_count"] = contract["production_blocker_count"]
    counts["quick_scan_receipt_provider_gap_count"] = contract["provider_gap_count"]
    counts["quick_scan_receipt_missing_signal_group_count"] = contract["missing_signal_group_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["quick_scan_receipt_contract_is_local"] = True
    policy["quick_scan_receipt_is_not_production_replacement"] = True
    policy["quick_scan_receipt_requires_full_deep_provider_browser_evidence"] = True
    view["counts"] = counts
    view["policy"] = policy
    view["quick_scan_execution_receipt"] = contract
    view["quick_scan_execution_receipt_rows"] = rows
    return view


def _candidate_browser_qa_runbook_row(
    phase: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    required_before_completion: bool = True,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "passed": bool(passed),
        "evidence": evidence,
        "required_before_completion": bool(required_before_completion),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_browser_qa_runbook_contract() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    runbook_source = _read_local_text(CANDIDATE_BROWSER_QA_RUNBOOK_PATH)
    runner_source = _read_local_text(MOTION_BROWSER_QA_RUNNER_PATH)
    candidate_source = _read_local_text(CANDIDATE_ROUTE_SOURCE_PATH)
    viewports = [
        {"name": "desktop", "width": 1440, "height": 900},
        {"name": "laptop", "width": 1280, "height": 800},
        {"name": "tablet", "width": 834, "height": 1112},
        {"name": "mobile", "width": 390, "height": 844},
    ]
    runner_available = (
        MOTION_BROWSER_QA_RUNNER_PATH.exists()
        and "command_center_3_motion_browser_qa_result.v1" in runner_source
        and "explicit_local_browser_visual_performance_run" in runner_source
        and "chromium.launch" in runner_source
        and "page.goto" in runner_source
        and "#candidates" in runner_source
        and "Candidate Radar" in runner_source
        and ".stock_ming_3/motion_qa" in runner_source
        and "starts_no_servers" in runner_source
        and "local_urls_only" in runner_source
        and "tushare_adapter" not in runner_source
        and "deepseek_adapter" not in runner_source
        and "api.github.com" not in runner_source
        and "place_order" not in runner_source
    )
    runbook_ready = (
        CANDIDATE_BROWSER_QA_RUNBOOK_PATH.exists()
        and "candidate_radar_browser_qa_runbook.v1" in runbook_source
        and "local_candidate_radar_browser_qa_runbook_not_browser_execution" in runbook_source
        and "#candidates" in runbook_source
        and ".stock_ming_3/motion_qa" in runbook_source
        and "opens_no_browser" in runbook_source
        and "writes_no_artifacts" in runbook_source
        and "visual_qa_complete" in runbook_source
        and "browser_performance_trace_done" in runbook_source
    )
    route_source_ready = (
        CANDIDATE_ROUTE_SOURCE_PATH.exists()
        and "radar-result-cluster" in candidate_source
        and "StateClarityRail" in candidate_source
        and "resultDeltaClarity" in candidate_source
        and "previousCacheDiffRows" in candidate_source
        and "postCandidateRadarQuickScan" in candidate_source
        and "postCandidateRadarFullPoolPlan" in candidate_source
        and "postCandidateRadarDeepScanPlan" in candidate_source
        and "候选不是买入指令" in candidate_source
        and "不调用 Tushare、DeepSeek 或 GitHub" in candidate_source
    )
    rows = [
        _candidate_browser_qa_runbook_row(
            "candidate_browser_qa_runbook_ready",
            "passed_static_policy" if runbook_ready else "blocked",
            passed=runbook_ready,
            evidence="scripts/candidate_radar_browser_qa_runbook.py pins route, viewports, criteria, artifact policy, and pending browser execution state",
        ),
        _candidate_browser_qa_runbook_row(
            "shared_motion_runner_covers_candidate_route",
            "passed_static_policy" if runner_available else "blocked",
            passed=runner_available,
            evidence="scripts/motion_browser_qa_runner.mjs includes #candidates, local-only URL policy, ignored artifact path, and no-provider/no-trade flags",
        ),
        _candidate_browser_qa_runbook_row(
            "candidate_route_source_ready",
            "passed_static_policy" if route_source_ready else "blocked",
            passed=route_source_ready,
            evidence="CandidateRadar.tsx exposes result cluster, clarity rail, delta rows, and button-gated local scan controls",
        ),
        _candidate_browser_qa_runbook_row(
            "default_motion_browser_run_pending",
            "execution_pending",
            passed=False,
            evidence="Default-motion browser pass is explicit and not run by GET cache or push-gate static checks.",
            required_before_completion=False,
        ),
        _candidate_browser_qa_runbook_row(
            "reduced_motion_browser_run_pending",
            "execution_pending",
            passed=False,
            evidence="Reduced-motion browser pass is explicit and not run by GET cache or push-gate static checks.",
            required_before_completion=False,
        ),
        _candidate_browser_qa_runbook_row(
            "candidate_radar_performance_trace_pending",
            "execution_pending",
            passed=False,
            evidence="Browser first-stable, long-task, layout-shift, and route-transition evidence remains an explicit run artifact.",
            required_before_completion=False,
        ),
    ]
    blockers = [row["phase"] for row in rows if row["status"] == "blocked"]
    matrix_rows = [
        {
            "route": "#candidates",
            "label": "Candidate Radar",
            "viewport": viewport["name"],
            "width": viewport["width"],
            "height": viewport["height"],
            "risk_focus": "candidate result cluster, local scan controls, result-delta visibility, and no-trade boundaries",
            "required_checks": [
                "candidate result cluster is visible and readable",
                "local scan buttons are visible and do not auto-run",
                "delta/freshness/provider/degraded gaps remain visible",
                "no clipped primary labels or state clarity rail text",
                "no long task above the local budget",
            ],
            "visual_qa_complete": False,
            "browser_performance_trace_done": False,
        }
        for viewport in viewports
    ]
    local_ready = not blockers
    contract = {
        "schema_version": "candidate_radar_browser_qa_runbook.v1",
        "status": "candidate_radar_browser_qa_runbook_ready_execution_pending" if local_ready else "candidate_radar_browser_qa_runbook_blocked",
        "scope": "local_candidate_radar_browser_qa_runbook_not_browser_execution",
        "ltg": "LTG-13/LTG-14",
        "local_runbook_ready": local_ready,
        "runner_available": runner_available,
        "candidate_route_source_ready": route_source_ready,
        "shared_runner_script": "scripts/motion_browser_qa_runner.mjs",
        "candidate_route": "#candidates",
        "artifact_root": ".stock_ming_3/motion_qa",
        "route_count": 1,
        "viewport_count": len(viewports),
        "qa_matrix_count": len(matrix_rows),
        "performance_budgets": {
            "candidate_radar_first_stable_ms": 1200,
            "route_transition_observed_ms": 500,
            "largest_motion_layout_shift": 0.1,
            "long_task_over_50ms_count": 0,
        },
        "visual_acceptance_criteria": [
            "candidate result cluster remains readable without opening raw JSON",
            "quick/watchlist/custom/full-pool/deep-scan controls remain visibly button-gated",
            "result-delta and previous-cache rows do not imply a trade recommendation",
            "provider/freshness/degraded gaps remain visible and are not hidden by motion",
            "mobile layout does not clip primary labels, state clarity rails, or action buttons",
            "reduced-motion mode preserves readable state boundaries",
        ],
        "row_count": len(rows),
        "blocking_phase_count": len(blockers),
        "blockers": blockers,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "visual_qa_complete": False,
        "browser_performance_trace_done": False,
        "browser_visual_delta_qa_done": False,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "cache_only": True,
        "local_urls_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "Runbook availability prepares targeted Candidate Radar browser QA; it is not browser evidence, provider-backed parity, or production radar replacement.",
    }
    return contract, rows, matrix_rows


def _relative_project_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except Exception:
        return str(path)


def _read_candidate_browser_qa_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _candidate_browser_qa_evidence_row(report: Mapping[str, Any], row: Mapping[str, Any], report_path: Path) -> dict[str, Any]:
    transition_observed = row.get("route_transition_observed_ms")
    transition_budget = row.get("route_transition_budget_ms") or _as_dict(report.get("performance_budgets")).get(
        "route_transition_observed_ms"
    )
    try:
        transition_within_budget = float(transition_observed) <= float(transition_budget)
    except Exception:
        transition_within_budget = False
    row_status = str(row.get("status") or "unknown")
    long_task_count = int(row.get("long_task_over_50ms_count") or 0)
    clipped_count = int(row.get("clipped_count") or 0)
    offscreen_count = int(row.get("offscreen_count") or 0)
    performance_trace_complete = row.get("performance_trace_complete") is True
    visual_complete = row.get("visual_qa_complete") is True and row_status == "passed"
    performance_passed = performance_trace_complete and transition_within_budget and long_task_count == 0
    return {
        "run_id": report.get("run_id") or report_path.parent.name,
        "generated_at": report.get("generated_at"),
        "reduced_motion": report.get("reduced_motion") is True,
        "route": str(row.get("route") or ""),
        "label": str(row.get("label") or "Candidate Radar"),
        "viewport": str(row.get("viewport") or ""),
        "width": row.get("width"),
        "height": row.get("height"),
        "status": row_status,
        "visual_qa_complete": visual_complete,
        "performance_trace_complete": performance_trace_complete,
        "performance_passed": performance_passed,
        "route_transition_observed_ms": transition_observed,
        "route_transition_budget_ms": transition_budget,
        "long_task_over_50ms_count": long_task_count,
        "largest_motion_layout_shift": row.get("largest_motion_layout_shift"),
        "clipped_count": clipped_count,
        "offscreen_count": offscreen_count,
        "review_required": row_status != "passed" or not visual_complete or not performance_passed,
        "artifact_report_path": _relative_project_path(report_path),
        "screenshot_path": _safe_text(row.get("screenshot_path"), limit=240),
        "reads_local_artifact_only": True,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_browser_qa_evidence_summary() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report_paths = (
        sorted(MOTION_QA_ARTIFACT_ROOT.glob("*/motion_browser_qa_report.json"))
        if MOTION_QA_ARTIFACT_ROOT.exists()
        else []
    )
    candidate_rows: list[dict[str, Any]] = []
    scanned_report_count = 0
    valid_report_count = 0
    candidate_report_count = 0
    latest_report_path: str | None = None
    latest_run_id: str | None = None
    latest_generated_at: Any = None
    for path in report_paths[-20:]:
        scanned_report_count += 1
        report = _read_candidate_browser_qa_report(path)
        if not report:
            continue
        valid_report = (
            report.get("schema_version") == "command_center_3_motion_browser_qa_result.v1"
            and report.get("scope") == "explicit_local_browser_visual_performance_run"
            and report.get("local_urls_only") is True
            and report.get("starts_no_servers") is True
            and report.get("external_calls_triggered") is False
            and report.get("tushare_called") is False
            and report.get("deepseek_called") is False
            and report.get("github_called") is False
            and report.get("does_not_execute_trades") is True
            and report.get("does_not_modify_strategy_action") is True
        )
        if not valid_report:
            continue
        valid_report_count += 1
        report_candidate_rows = [
            row
            for row in _as_list(report.get("rows"))
            if isinstance(row, Mapping) and str(row.get("route") or "") == "#candidates"
        ]
        if not report_candidate_rows:
            continue
        candidate_report_count += 1
        latest_report_path = _relative_project_path(path)
        latest_run_id = str(report.get("run_id") or path.parent.name)
        latest_generated_at = report.get("generated_at")
        candidate_rows.extend(_candidate_browser_qa_evidence_row(report, row, path) for row in report_candidate_rows)

    candidate_rows = candidate_rows[-16:]
    row_count = len(candidate_rows)
    review_required_count = sum(1 for row in candidate_rows if row.get("review_required") is True)
    visual_passed_count = sum(1 for row in candidate_rows if row.get("visual_qa_complete") is True)
    performance_passed_count = sum(1 for row in candidate_rows if row.get("performance_passed") is True)
    default_motion_passed = any(row.get("reduced_motion") is False and row.get("review_required") is False for row in candidate_rows)
    reduced_motion_passed = any(row.get("reduced_motion") is True and row.get("review_required") is False for row in candidate_rows)
    local_evidence_found = row_count > 0
    visual_passed = local_evidence_found and visual_passed_count == row_count and review_required_count == 0
    performance_passed = local_evidence_found and performance_passed_count == row_count and review_required_count == 0
    status = (
        "candidate_browser_qa_evidence_passed_local_artifact"
        if visual_passed and performance_passed
        else "candidate_browser_qa_evidence_review_required_local_artifact"
        if local_evidence_found
        else "candidate_browser_qa_evidence_pending"
    )
    summary = {
        "schema_version": "candidate_radar_browser_qa_evidence.v1",
        "status": status,
        "scope": "local_candidate_radar_browser_qa_evidence_reader_no_browser_execution",
        "ltg": "LTG-13/LTG-14",
        "artifact_root": ".stock_ming_3/motion_qa",
        "local_browser_qa_evidence_found": local_evidence_found,
        "scanned_report_count": scanned_report_count,
        "valid_report_count": valid_report_count,
        "candidate_report_count": candidate_report_count,
        "candidate_route": "#candidates",
        "candidate_viewport_row_count": row_count,
        "review_required_count": review_required_count,
        "visual_passed_count": visual_passed_count,
        "performance_passed_count": performance_passed_count,
        "default_motion_passed": default_motion_passed,
        "reduced_motion_passed": reduced_motion_passed,
        "candidate_visual_qa_evidence_passed": visual_passed,
        "candidate_browser_performance_evidence_passed": performance_passed,
        "visual_qa_complete": visual_passed,
        "browser_performance_trace_done": performance_passed,
        "browser_visual_delta_qa_done": visual_passed,
        "latest_report_path": latest_report_path,
        "latest_run_id": latest_run_id,
        "latest_generated_at": latest_generated_at,
        "row_count": row_count,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "reads_ignored_local_reports_only": True,
        "screenshots_are_not_tracked": True,
        "report_artifacts_are_not_tracked": True,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "cache_only": True,
        "local_urls_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This reads ignored local motion browser QA reports for #candidates only. It does not open a browser, write artifacts, prove provider parity, or mark production radar replacement complete.",
    }
    return summary, candidate_rows


def _candidate_browser_qa_review_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    blocks_review: bool = False,
    blocks_production: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "evidence": evidence,
        "blocks_review": bool(blocks_review and not passed),
        "blocks_production": bool(blocks_production),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_browser_qa_review_contract(
    evidence_summary: Mapping[str, Any],
    evidence_rows: list[dict[str, Any]],
    *,
    explicit_review: bool = False,
    task_id: str | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    viewport_names = {str(row.get("viewport") or "") for row in evidence_rows}
    required_viewports = {"desktop", "laptop", "tablet", "mobile"}
    evidence_found = evidence_summary.get("local_browser_qa_evidence_found") is True
    review_rows = [
        _candidate_browser_qa_review_row(
            "explicit_post_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            passed=explicit_review,
            evidence="POST /api/candidate-radar/browser-qa-review creates the review record; GET cache only previews local evidence.",
            blocks_review=True,
            blocks_production=True,
        ),
        _candidate_browser_qa_review_row(
            "candidate_route_evidence_available",
            "passed" if evidence_found else "pending_local_report",
            passed=evidence_found,
            evidence="candidate_browser_qa_evidence_summary found ignored local runner rows for #candidates.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "candidate_viewport_matrix_complete",
            "passed" if required_viewports.issubset(viewport_names) else "pending_viewports",
            passed=required_viewports.issubset(viewport_names),
            evidence="desktop/laptop/tablet/mobile candidate rows must all be present in local runner evidence.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "visual_evidence_passed",
            "passed" if evidence_summary.get("candidate_visual_qa_evidence_passed") is True else "pending_visual_review",
            passed=evidence_summary.get("candidate_visual_qa_evidence_passed") is True,
            evidence="All candidate route rows must report visual_qa_complete and zero review rows.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "performance_evidence_passed",
            "passed" if evidence_summary.get("candidate_browser_performance_evidence_passed") is True else "pending_performance_review",
            passed=evidence_summary.get("candidate_browser_performance_evidence_passed") is True,
            evidence="All candidate route rows must include performance traces within local budgets and no long tasks.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "default_and_reduced_motion_coverage",
            "passed"
            if evidence_summary.get("default_motion_passed") is True
            and evidence_summary.get("reduced_motion_passed") is True
            else "pending_reduced_or_default_motion",
            passed=evidence_summary.get("default_motion_passed") is True
            and evidence_summary.get("reduced_motion_passed") is True,
            evidence="Both default-motion and reduced-motion candidate route passes are required before motion evidence can be reviewed as complete.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "ignored_artifact_policy_preserved",
            "passed" if evidence_summary.get("reads_ignored_local_reports_only") is True else "blocked_artifact_policy",
            passed=evidence_summary.get("reads_ignored_local_reports_only") is True,
            evidence="Review reads only ignored local reports and does not commit screenshots, videos, or JSON artifacts.",
            blocks_review=True,
        ),
        _candidate_browser_qa_review_row(
            "production_replacement_stays_blocked",
            "passed",
            passed=True,
            evidence="Browser QA review cannot override full-pool/deep-scan/provider-backed acceptance blockers.",
            blocks_review=False,
            blocks_production=True,
        ),
    ]
    blocking_review_rows = [row for row in review_rows if row.get("blocks_review") is True]
    local_review_ready = explicit_review and not blocking_review_rows
    status = "candidate_browser_qa_review_ready_local_artifact" if local_review_ready else "candidate_browser_qa_review_pending"
    return {
        "schema_version": "candidate_radar_browser_qa_review.v1",
        "status": status,
        "scope": "button_gated_local_candidate_browser_qa_review_no_browser_execution",
        "ltg": "LTG-13/LTG-14",
        "explicit_review_task_done": bool(explicit_review),
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "local_browser_qa_review_ready": local_review_ready,
        "local_browser_qa_evidence_found": evidence_found,
        "candidate_route": "#candidates",
        "required_viewports": sorted(required_viewports),
        "observed_viewports": sorted(viewport for viewport in viewport_names if viewport),
        "review_required_count": evidence_summary.get("review_required_count", 0),
        "evidence_row_count": len(evidence_rows),
        "review_row_count": len(review_rows),
        "blocking_review_count": len(blocking_review_rows),
        "blocking_review_keys": [str(row.get("criterion")) for row in blocking_review_rows],
        "default_motion_passed": evidence_summary.get("default_motion_passed") is True,
        "reduced_motion_passed": evidence_summary.get("reduced_motion_passed") is True,
        "candidate_visual_qa_evidence_passed": evidence_summary.get("candidate_visual_qa_evidence_passed") is True,
        "candidate_browser_performance_evidence_passed": evidence_summary.get(
            "candidate_browser_performance_evidence_passed"
        )
        is True,
        "rows": review_rows,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "reads_ignored_local_reports_only": True,
        "screenshots_are_not_tracked": True,
        "report_artifacts_are_not_tracked": True,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This review promotes local browser QA evidence only to a button-gated local review state. It does not execute browser QA, call providers, or complete production radar replacement.",
    }


def _fast_scan_readiness_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    production_blocker: bool = False,
    user_visible: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": passed,
        "evidence": evidence,
        "production_blocker": production_blocker and not passed,
        "user_visible": user_visible,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _fast_scan_readiness_rows(
    *,
    mode: str,
    scan_mode: str,
    cache_source: str,
    coverage: Mapping[str, Any],
    scan_execution_summary: Mapping[str, Any],
    scan_acceptance_rows: list[dict[str, Any]],
    parity_inventory: Mapping[str, Any],
    full_pool_scan_plan: Mapping[str, Any],
    deep_scan_plan: Mapping[str, Any],
    local_pool_audit: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    runtime_budget_contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    coverage_detail = _as_dict(coverage.get("coverage_detail_summary"))
    acceptance_by_key = {str(row.get("check_key")): row for row in scan_acceptance_rows}
    provider_gap_count = int(scan_execution_summary.get("provider_gap_count") or 0)
    degraded_count = int(scan_execution_summary.get("degraded_mode_active_count") or 0)
    freshness_state = str(scan_execution_summary.get("freshness_state") or "unknown")
    local_modes_ready = set(SUPPORTED_LOCAL_SCAN_MODES) >= {"quick_cache_scan", "watchlist_scan", "custom_pool_scan"}
    return [
        _fast_scan_readiness_row(
            "page_render_does_not_scan",
            "passed" if coverage_detail.get("does_not_scan_full_market_on_render") is True else "blocked",
            passed=coverage_detail.get("does_not_scan_full_market_on_render") is True,
            evidence="GET cache and React render display persisted/cache packet only.",
            production_blocker=True,
        ),
        _fast_scan_readiness_row(
            "cache_get_is_read_only",
            "passed",
            passed=True,
            evidence=f"mode={mode}; cache_source={cache_source}; scan_mode={scan_mode}",
        ),
        _fast_scan_readiness_row(
            "button_task_receipt_contract",
            "passed" if scan_execution_summary.get("writes_sqlite_packet") is not None else "blocked",
            passed=scan_execution_summary.get("writes_sqlite_packet") is not None,
            evidence="POST scan tasks return local task_id and write/read SQLite packet when executed.",
            production_blocker=True,
        ),
        _fast_scan_readiness_row(
            "local_scan_modes_supported",
            "passed" if local_modes_ready else "blocked",
            passed=local_modes_ready,
            evidence="/".join(sorted(SUPPORTED_LOCAL_SCAN_MODES)),
            production_blocker=True,
        ),
        _fast_scan_readiness_row(
            "legacy_signal_groups_visible",
            "gap_reported" if int(coverage.get("missing_signal_group_count") or 0) else "passed",
            passed=True,
            evidence=f"mapped={coverage.get('mapped_signal_group_count')}; missing={coverage.get('missing_signal_group_count')}",
        ),
        _fast_scan_readiness_row(
            "legacy_parity_gap_visible",
            "gap_reported" if int(parity_inventory.get("gap_or_future_count") or 0) else "passed",
            passed=True,
            evidence=f"mapped_or_partial={parity_inventory.get('mapped_or_partial_count')}; gap_or_future={parity_inventory.get('gap_or_future_count')}",
        ),
        _fast_scan_readiness_row(
            "provider_gap_visible",
            "gap_reported" if provider_gap_count else "passed",
            passed=True,
            evidence=f"provider_gap_count={provider_gap_count}; degraded_active={degraded_count}",
        ),
        _fast_scan_readiness_row(
            "freshness_research_only_boundary",
            str(acceptance_by_key.get("freshness_boundary", {}).get("status") or "unknown"),
            passed=True,
            evidence=f"freshness={freshness_state}; stale/unknown inputs remain display-only.",
        ),
        _fast_scan_readiness_row(
            "last_success_cache_visible",
            "passed" if cache_source in {"sqlite_meta", "snapshot", "snapshot_cache", "local_builder"} or candidate_rows else "empty_reported",
            passed=True,
            evidence=f"cache_source={cache_source}; candidate_rows={len(candidate_rows)}; empty state does not trigger broad scan.",
        ),
        _fast_scan_readiness_row(
            "local_pool_skips_visible",
            "passed" if not local_pool_audit or local_pool_audit.get("skipped_candidate_count") is not None else "input_reported",
            passed=True,
            evidence=f"input={local_pool_audit.get('input_candidate_count')}; normalized={local_pool_audit.get('normalized_candidate_count')}",
        ),
        _fast_scan_readiness_row(
            "runtime_budget_contract_visible",
            "passed" if runtime_budget_contract.get("status") == "fast_scan_runtime_budget_ready" else "blocked",
            passed=runtime_budget_contract.get("status") == "fast_scan_runtime_budget_ready",
            evidence=f"display_limit={runtime_budget_contract.get('display_candidate_limit')}; worker_threshold={runtime_budget_contract.get('worker_required_universe_threshold')}",
            production_blocker=True,
        ),
        _fast_scan_readiness_row(
            "full_pool_boundary_plan_only",
            "plan_only" if full_pool_scan_plan.get("status") == "full_pool_plan_ready" else "not_executed",
            passed=True,
            evidence=f"full_pool_scan_done={bool(full_pool_scan_plan.get('full_pool_scan_done') is True)}; worker_required={full_pool_scan_plan.get('worker_task_required')}",
        ),
        _fast_scan_readiness_row(
            "deep_scan_boundary_plan_only",
            "plan_only" if deep_scan_plan.get("status") == "deep_scan_plan_ready" else "not_executed",
            passed=True,
            evidence=f"deep_scan_done={bool(deep_scan_plan.get('deep_scan_done') is True)}; deepseek_called={bool(deep_scan_plan.get('deepseek_called') is True)}",
        ),
        _fast_scan_readiness_row(
            "trade_action_boundary",
            "passed",
            passed=True,
            evidence="Candidate rows remain research-only and never mutate strategy action or holdings.",
        ),
        _fast_scan_readiness_row(
            "production_full_replacement_pending",
            "pending",
            passed=False,
            evidence="Real full-pool/deep-scan execution and provider-backed parity acceptance remain future work.",
            production_blocker=False,
        ),
    ]


def _fast_scan_readiness_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    pending = [row["criterion"] for row in rows if row.get("status") == "pending" and not row.get("production_blocker")]
    passed_count = sum(1 for row in rows if row.get("passed") is True)
    static_ready = not blockers
    return {
        "schema_version": "candidate_radar_fast_scan_readiness.v1",
        "status": "fast_scan_local_ready_full_pool_pending" if static_ready else "fast_scan_blocked",
        "scope": "local_cache_task_readiness_not_full_pool_or_provider_acceptance",
        "ltg": "LTG-13",
        "local_fast_scan_ready": static_ready,
        "production_radar_replacement_complete": False,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "row_count": len(rows),
        "passed_count": passed_count,
        "blocking_criterion_count": len(blockers),
        "soft_blocker_count": len(pending),
        "blockers": blockers,
        "soft_blockers": pending,
        "cache_only": True,
        "post_task_required_for_scan": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "next_action": "implement worker-backed full-pool/deep-scan execution and provider-backed parity acceptance before retiring legacy radar fallback.",
    }


def _no_feature_loss_acceptance_row(
    criterion: str,
    status: str,
    *,
    local_contract_passed: bool,
    production_ready: bool,
    evidence: str,
    next_action: str,
    required_for_production_replacement: bool = True,
    gap_visible: bool = False,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "local_contract_passed": bool(local_contract_passed),
        "production_ready": bool(production_ready),
        "required_for_production_replacement": bool(required_for_production_replacement),
        "blocks_production_replacement": bool(required_for_production_replacement and not production_ready),
        "gap_visible": bool(gap_visible),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _no_feature_loss_acceptance_rows(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    counts = _as_dict(packet.get("counts"))
    policy = _as_dict(packet.get("policy"))
    coverage = _as_dict(packet.get("scan_coverage"))
    coverage_detail = _as_dict(packet.get("coverage_detail_summary"))
    parity = _as_dict(packet.get("legacy_parity_inventory"))
    runtime_budget = _as_dict(packet.get("fast_scan_runtime_budget_contract"))
    readiness = _as_dict(packet.get("fast_scan_readiness_audit"))
    freshness = _as_dict(packet.get("freshness_state"))
    full_pool_plan = _as_dict(packet.get("full_pool_scan_plan"))
    deep_scan_plan = _as_dict(packet.get("deep_scan_plan"))
    output_total = int(parity.get("output_contract_field_count") or len(_as_list(packet.get("legacy_output_contract_rows"))))
    output_mapped = int(parity.get("output_contract_mapped_count") or counts.get("legacy_output_mapped_count") or 0)
    missing_signal_count = int(coverage.get("missing_signal_group_count") or 0)
    parity_gap_count = int(parity.get("gap_or_future_count") or counts.get("legacy_parity_gap_count") or 0)
    provider_gap_count = int(coverage_detail.get("provider_blocked_group_count") or 0) + int(
        coverage_detail.get("stale_input_group_count") or 0
    ) + int(coverage_detail.get("missing_provider_data_group_count") or 0)
    freshness_state = str(freshness.get("state") or "unknown").lower()
    freshness_ready = freshness.get("source") != "missing" and freshness_state not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    full_pool_done = bool(full_pool_plan.get("full_pool_scan_done") is True)
    deep_scan_done = bool(deep_scan_plan.get("deep_scan_done") is True)
    return [
        _no_feature_loss_acceptance_row(
            "page_render_zero_scan",
            "passed" if policy.get("does_not_scan_market") is True else "blocked",
            local_contract_passed=policy.get("does_not_scan_market") is True,
            production_ready=policy.get("does_not_scan_market") is True,
            evidence="React page render and GET cache display persisted/cache packet only.",
            next_action="Keep broad scans behind explicit POST task buttons.",
        ),
        _no_feature_loss_acceptance_row(
            "cache_get_external_boundary",
            "passed" if packet.get("external_calls_triggered") is False else "blocked",
            local_contract_passed=packet.get("external_calls_triggered") is False,
            production_ready=packet.get("external_calls_triggered") is False,
            evidence="GET candidate cache does not call Tushare, DeepSeek, GitHub, or trading interfaces.",
            next_action="Preserve cache-only reads and keep provider/model calls button gated.",
        ),
        _no_feature_loss_acceptance_row(
            "local_fast_scan_modes",
            "passed" if readiness.get("local_fast_scan_ready") is True else "blocked",
            local_contract_passed=readiness.get("local_fast_scan_ready") is True,
            production_ready=readiness.get("local_fast_scan_ready") is True,
            evidence=f"supported_local_scan_modes={packet.get('supported_local_scan_modes')}",
            next_action="Keep quick/watchlist/custom scan modes local and task based.",
        ),
        _no_feature_loss_acceptance_row(
            "legacy_signal_groups_visible",
            "gap_reported" if missing_signal_count else "passed",
            local_contract_passed=True,
            production_ready=missing_signal_count == 0,
            evidence=f"mapped={coverage.get('mapped_signal_group_count')}; missing={missing_signal_count}",
            next_action="Map each missing legacy signal group or keep the gap visible before retiring fallback.",
            gap_visible=missing_signal_count > 0,
        ),
        _no_feature_loss_acceptance_row(
            "legacy_parity_rows_visible",
            "gap_reported" if parity_gap_count else "passed",
            local_contract_passed=True,
            production_ready=parity_gap_count == 0,
            evidence=f"mapped_or_partial={parity.get('mapped_or_partial_count')}; gap_or_future={parity_gap_count}",
            next_action="Close or explicitly accept legacy parity gaps before claiming production replacement.",
            gap_visible=parity_gap_count > 0,
        ),
        _no_feature_loss_acceptance_row(
            "legacy_output_contract_visible",
            "gap_reported" if output_total and output_mapped < output_total else "passed",
            local_contract_passed=True,
            production_ready=bool(output_total and output_mapped >= output_total),
            evidence=f"output_mapped={output_mapped}; output_total={output_total}",
            next_action="Keep absent output fields as missing_reported; do not invent legacy output values.",
            gap_visible=bool(output_total and output_mapped < output_total),
        ),
        _no_feature_loss_acceptance_row(
            "provider_signal_gaps_visible",
            "gap_reported" if provider_gap_count else "passed",
            local_contract_passed=True,
            production_ready=provider_gap_count == 0,
            evidence=f"provider_gap_count={provider_gap_count}",
            next_action="Validate missing provider signal groups through future explicit provider tasks.",
            gap_visible=provider_gap_count > 0,
        ),
        _no_feature_loss_acceptance_row(
            "freshness_research_only_boundary",
            "passed" if freshness_ready else "research_only_reported",
            local_contract_passed=True,
            production_ready=freshness_ready,
            evidence=f"freshness={freshness.get('source') or 'missing'}:{freshness.get('state') or 'unknown'}",
            next_action="Require current trade-calendar freshness before using candidates as current evidence.",
            gap_visible=not freshness_ready,
        ),
        _no_feature_loss_acceptance_row(
            "runtime_budget_contract_visible",
            "passed" if runtime_budget.get("status") == "fast_scan_runtime_budget_ready" else "blocked",
            local_contract_passed=runtime_budget.get("status") == "fast_scan_runtime_budget_ready",
            production_ready=runtime_budget.get("status") == "fast_scan_runtime_budget_ready",
            evidence=f"display_limit={runtime_budget.get('display_candidate_limit')}; worker_threshold={runtime_budget.get('worker_required_universe_threshold')}",
            next_action="Keep sync display capped and move large universes to worker execution.",
        ),
        _no_feature_loss_acceptance_row(
            "browser_performance_trace_pending",
            "pending_visual_perf_trace",
            local_contract_passed=True,
            production_ready=False,
            evidence="Browser performance trace is not executed by this local cache contract.",
            next_action="Run desktop/mobile browser trace validation before claiming the scan is stall-free in production.",
        ),
        _no_feature_loss_acceptance_row(
            "full_pool_execution_pending",
            "completed" if full_pool_done else "pending_worker_execution",
            local_contract_passed=True,
            production_ready=full_pool_done,
            evidence=f"full_pool_scan_done={full_pool_done}",
            next_action="Implement future worker-backed full-pool execution without page-load scanning.",
        ),
        _no_feature_loss_acceptance_row(
            "deep_scan_execution_pending",
            "completed" if deep_scan_done else "pending_worker_execution",
            local_contract_passed=True,
            production_ready=deep_scan_done,
            evidence=f"deep_scan_done={deep_scan_done}; deepseek_called={bool(deep_scan_plan.get('deepseek_called') is True)}",
            next_action="Implement future deep scan as a guarded task and keep DeepSeek manual/button gated.",
        ),
        _no_feature_loss_acceptance_row(
            "provider_backed_acceptance_pending",
            "pending_provider_acceptance",
            local_contract_passed=True,
            production_ready=False,
            evidence="No provider-backed radar parity acceptance is executed by cache reads or local plan tasks.",
            next_action="Run future provider-backed acceptance samples after Tushare interface validation is ready.",
        ),
        _no_feature_loss_acceptance_row(
            "trade_action_isolation",
            "passed" if packet.get("does_not_modify_strategy_action") is True else "blocked",
            local_contract_passed=packet.get("does_not_modify_strategy_action") is True,
            production_ready=packet.get("does_not_modify_strategy_action") is True,
            evidence="Radar candidates remain research-only and do not mutate strategy action, holdings, or orders.",
            next_action="Keep candidate selection separate from trading integration.",
        ),
    ]


def _attach_no_feature_loss_acceptance_contract(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    rows = _no_feature_loss_acceptance_rows(view)
    local_blockers = [row["criterion"] for row in rows if not row.get("local_contract_passed")]
    production_blockers = [row["criterion"] for row in rows if row.get("blocks_production_replacement")]
    visible_gaps = [row["criterion"] for row in rows if row.get("gap_visible")]
    local_ready = not local_blockers
    contract = {
        "schema_version": "candidate_radar_no_feature_loss_acceptance.v1",
        "status": "no_feature_loss_acceptance_local_ready_production_pending" if local_ready else "no_feature_loss_acceptance_blocked",
        "scope": "local_fast_scan_no_feature_loss_contract_not_production_replacement",
        "ltg": "LTG-13",
        "local_no_feature_loss_contract_ready": local_ready,
        "production_radar_replacement_complete": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": False,
        "deep_scan_done": False,
        "provider_backed_acceptance_done": False,
        "browser_performance_trace_done": False,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "visible_gap_count": len(visible_gaps),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "visible_gaps": visible_gaps,
        "cache_only": True,
        "post_task_required_for_scan": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This contract proves local no-feature-loss acceptance is visible. It does not prove production radar replacement, full-pool execution, deep-scan execution, provider-backed acceptance, or browser performance.",
    }
    counts = dict(_as_dict(view.get("counts")))
    counts["no_feature_loss_acceptance_row_count"] = contract["row_count"]
    counts["no_feature_loss_local_blocker_count"] = contract["local_blocker_count"]
    counts["no_feature_loss_production_blocker_count"] = contract["production_blocker_count"]
    counts["no_feature_loss_visible_gap_count"] = contract["visible_gap_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["no_feature_loss_acceptance_contract_is_local"] = True
    policy["no_feature_loss_acceptance_is_not_production_replacement"] = True
    policy["legacy_fallback_required_until_full_pool_deep_scan_acceptance"] = True
    view["counts"] = counts
    view["policy"] = policy
    view["no_feature_loss_acceptance_contract"] = contract
    view["no_feature_loss_acceptance_rows"] = rows
    view = _attach_replacement_gap_triage_contract(view)
    view = _attach_candidate_radar_promotion_blocker_audit(view)
    view = _attach_candidate_radar_production_activation_receipt(view)
    return view


def _replacement_gap_triage_row(
    gap_key: str,
    category: str,
    severity: str,
    status: str,
    *,
    passed: bool,
    blocks_legacy_retirement: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "gap_key": gap_key,
        "category": category,
        "severity": severity,
        "status": status,
        "passed": bool(passed),
        "blocks_legacy_retirement": bool(blocks_legacy_retirement and not passed),
        "user_visible": True,
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _replacement_gap_triage_rows(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    counts = _as_dict(packet.get("counts"))
    policy = _as_dict(packet.get("policy"))
    coverage = _as_dict(packet.get("scan_coverage"))
    coverage_detail = _as_dict(packet.get("coverage_detail_summary"))
    parity = _as_dict(packet.get("legacy_parity_inventory"))
    no_loss = _as_dict(packet.get("no_feature_loss_acceptance_contract"))
    result_delta = _as_dict(packet.get("result_delta_clarity_contract"))
    freshness = _as_dict(packet.get("freshness_state"))
    full_pool_plan = _as_dict(packet.get("full_pool_scan_plan"))
    deep_scan_plan = _as_dict(packet.get("deep_scan_plan"))
    output_total = int(parity.get("output_contract_field_count") or len(_as_list(packet.get("legacy_output_contract_rows"))))
    output_mapped = int(parity.get("output_contract_mapped_count") or counts.get("legacy_output_mapped_count") or 0)
    missing_signal_count = int(coverage.get("missing_signal_group_count") or 0)
    provider_gap_count = int(coverage_detail.get("provider_blocked_group_count") or 0) + int(
        coverage_detail.get("stale_input_group_count") or 0
    ) + int(coverage_detail.get("missing_provider_data_group_count") or 0)
    freshness_state = str(freshness.get("state") or "unknown").lower()
    freshness_ready = freshness.get("source") != "missing" and freshness_state not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    full_pool_done = bool(full_pool_plan.get("full_pool_scan_done") is True)
    deep_scan_done = bool(deep_scan_plan.get("deep_scan_done") is True)
    previous_diff_done = bool(result_delta.get("previous_cache_diff_done") is True)
    browser_delta_done = bool(result_delta.get("browser_visual_delta_qa_done") is True)
    return [
        _replacement_gap_triage_row(
            "page_render_zero_scan_guardrail",
            "guardrail",
            "info",
            "passed" if policy.get("does_not_scan_market") is True else "blocked",
            passed=policy.get("does_not_scan_market") is True,
            blocks_legacy_retirement=True,
            evidence="GET cache and React render remain read-only and do not start a broad scan.",
            next_action="Keep all future radar scans behind explicit task buttons.",
        ),
        _replacement_gap_triage_row(
            "legacy_signal_group_mapping",
            "legacy_parity",
            "critical" if missing_signal_count else "ok",
            "gap_reported" if missing_signal_count else "passed",
            passed=missing_signal_count == 0,
            blocks_legacy_retirement=True,
            evidence=f"missing_signal_group_count={missing_signal_count}",
            next_action="Map missing legacy radar signal groups or keep Streamlit fallback available.",
        ),
        _replacement_gap_triage_row(
            "legacy_output_contract_mapping",
            "legacy_parity",
            "critical" if output_total and output_mapped < output_total else "ok",
            "gap_reported" if output_total and output_mapped < output_total else "passed",
            passed=bool(output_total and output_mapped >= output_total),
            blocks_legacy_retirement=True,
            evidence=f"output_mapped={output_mapped}; output_total={output_total}",
            next_action="Preserve every legacy output field or explicitly show it as missing before retirement.",
        ),
        _replacement_gap_triage_row(
            "provider_signal_coverage",
            "provider_acceptance",
            "critical" if provider_gap_count else "ok",
            "gap_reported" if provider_gap_count else "passed",
            passed=provider_gap_count == 0,
            blocks_legacy_retirement=True,
            evidence=f"provider_gap_count={provider_gap_count}",
            next_action="Validate provider-backed radar signals through future explicit provider tasks.",
        ),
        _replacement_gap_triage_row(
            "current_freshness_gate",
            "freshness",
            "critical" if not freshness_ready else "ok",
            "research_only_reported" if not freshness_ready else "passed",
            passed=freshness_ready,
            blocks_legacy_retirement=True,
            evidence=f"freshness={freshness.get('source') or 'missing'}:{freshness.get('state') or 'unknown'}",
            next_action="Require current trade-calendar freshness before treating candidates as current evidence.",
        ),
        _replacement_gap_triage_row(
            "previous_cache_delta_clarity",
            "result_delta",
            "pending" if not previous_diff_done else "ok",
            "pending_previous_cache_diff" if not previous_diff_done else "passed",
            passed=previous_diff_done,
            blocks_legacy_retirement=False,
            evidence=f"previous_cache_diff_done={previous_diff_done}; changed={result_delta.get('candidate_changed_count')}",
            next_action="Keep previous-cache diff visible when a persisted prior radar packet exists.",
        ),
        _replacement_gap_triage_row(
            "browser_visual_delta_qa",
            "visual_qa",
            "blocking_pending",
            "pending_visual_qa" if not browser_delta_done else "passed",
            passed=browser_delta_done,
            blocks_legacy_retirement=True,
            evidence=f"browser_visual_delta_qa_done={browser_delta_done}",
            next_action="Run viewport visual QA so result changes are visible without overlap or occlusion.",
        ),
        _replacement_gap_triage_row(
            "browser_performance_trace",
            "performance",
            "blocking_pending",
            "pending_perf_trace",
            passed=False,
            blocks_legacy_retirement=True,
            evidence="Browser performance trace is not executed by the local cache contract.",
            next_action="Run desktop/mobile trace validation before claiming the radar is stall-free in production.",
        ),
        _replacement_gap_triage_row(
            "full_pool_worker_execution",
            "worker_pipeline",
            "blocking_pending" if not full_pool_done else "ok",
            "pending_worker_execution" if not full_pool_done else "passed",
            passed=full_pool_done,
            blocks_legacy_retirement=True,
            evidence=f"full_pool_scan_done={full_pool_done}",
            next_action="Implement worker-backed full-pool execution without page-load scanning.",
        ),
        _replacement_gap_triage_row(
            "deep_scan_execution",
            "worker_pipeline",
            "blocking_pending" if not deep_scan_done else "ok",
            "pending_worker_execution" if not deep_scan_done else "passed",
            passed=deep_scan_done,
            blocks_legacy_retirement=True,
            evidence=f"deep_scan_done={deep_scan_done}; deepseek_called={bool(deep_scan_plan.get('deepseek_called') is True)}",
            next_action="Implement deep scan as a guarded task; keep DeepSeek manual/button gated.",
        ),
        _replacement_gap_triage_row(
            "provider_backed_acceptance",
            "provider_acceptance",
            "blocking_pending",
            "pending_provider_acceptance",
            passed=False,
            blocks_legacy_retirement=True,
            evidence=f"provider_backed_acceptance_done={bool(no_loss.get('provider_backed_acceptance_done') is True)}",
            next_action="Run provider-backed radar parity acceptance only after the Tushare task pipeline is ready.",
        ),
        _replacement_gap_triage_row(
            "trade_action_isolation",
            "safety",
            "ok",
            "passed" if packet.get("does_not_modify_strategy_action") is True and packet.get("does_not_execute_trades") is True else "blocked",
            passed=packet.get("does_not_modify_strategy_action") is True and packet.get("does_not_execute_trades") is True,
            blocks_legacy_retirement=True,
            evidence="Radar candidates remain research-only and do not mutate action, holdings, or orders.",
            next_action="Keep candidate radar isolated from trading integration.",
        ),
    ]


def _attach_replacement_gap_triage_contract(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    rows = _replacement_gap_triage_rows(view)
    blocking_rows = [row for row in rows if row.get("blocks_legacy_retirement")]
    critical_rows = [row for row in rows if row.get("severity") == "critical"]
    pending_rows = [row for row in rows if "pending" in str(row.get("severity") or row.get("status") or "")]
    legacy_retirement_ready = not blocking_rows
    contract = {
        "schema_version": "candidate_radar_replacement_gap_triage.v1",
        "status": (
            "replacement_gap_triage_ready_for_legacy_retirement"
            if legacy_retirement_ready
            else "replacement_gap_triage_local_ready_legacy_retirement_blocked"
        ),
        "scope": "local_replacement_gap_triage_not_production_radar_replacement",
        "ltg": "LTG-13",
        "local_triage_ready": True,
        "legacy_retirement_ready": legacy_retirement_ready,
        "production_radar_replacement_complete": False,
        "legacy_fallback_required": not legacy_retirement_ready,
        "row_count": len(rows),
        "blocking_gap_count": len(blocking_rows),
        "critical_gap_count": len(critical_rows),
        "pending_gap_count": len(pending_rows),
        "blocking_gap_keys": [str(row.get("gap_key")) for row in blocking_rows],
        "critical_gap_keys": [str(row.get("gap_key")) for row in critical_rows],
        "high_priority_next_actions": [str(row.get("next_action")) for row in blocking_rows[:5]],
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This triage makes the blockers to retiring the legacy next-ticket radar visible. It is not full-pool execution, provider-backed acceptance, browser visual QA, or production replacement.",
    }
    counts = dict(_as_dict(view.get("counts")))
    counts["replacement_gap_triage_row_count"] = contract["row_count"]
    counts["replacement_gap_triage_blocking_count"] = contract["blocking_gap_count"]
    counts["replacement_gap_triage_critical_count"] = contract["critical_gap_count"]
    counts["replacement_gap_triage_pending_count"] = contract["pending_gap_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["replacement_gap_triage_contract_is_local"] = True
    policy["replacement_gap_triage_is_not_production_replacement"] = True
    policy["legacy_radar_retirement_blocked_by_triage"] = not legacy_retirement_ready
    view["counts"] = counts
    view["policy"] = policy
    view["replacement_gap_triage_contract"] = contract
    view["replacement_gap_triage_rows"] = rows
    return view


def _promotion_blocker_row(
    criterion: str,
    category: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    next_action: str,
    blocks_promotion: bool = True,
    evidence_kind: str = "local_contract",
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "category": category,
        "status": status,
        "passed": bool(passed),
        "evidence_kind": evidence_kind,
        "evidence": evidence,
        "next_action": next_action,
        "blocks_promotion": bool(blocks_promotion and not passed),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_radar_promotion_blocker_audit(packet: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    counts = _as_dict(packet.get("counts"))
    no_loss = _as_dict(packet.get("no_feature_loss_acceptance_contract"))
    replacement = _as_dict(packet.get("replacement_gap_triage_contract"))
    result_delta = _as_dict(packet.get("result_delta_clarity_contract"))
    browser_evidence = _as_dict(packet.get("candidate_browser_qa_evidence_summary"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    runtime_budget = _as_dict(packet.get("fast_scan_runtime_budget_contract"))
    readiness = _as_dict(packet.get("fast_scan_readiness_audit"))
    full_pool_plan = _as_dict(packet.get("full_pool_scan_plan"))
    deep_scan_plan = _as_dict(packet.get("deep_scan_plan"))
    coverage = _as_dict(packet.get("coverage_detail_summary"))
    freshness = _as_dict(packet.get("freshness_state"))
    candidate_count = int(counts.get("candidate_count") or 0)
    freshness_state = str(freshness.get("state") or "unknown").lower()
    freshness_ready = freshness.get("source") != "missing" and freshness_state not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    provider_gap_count = int(coverage.get("provider_blocked_group_count") or 0) + int(
        coverage.get("stale_input_group_count") or 0
    ) + int(coverage.get("missing_provider_data_group_count") or 0)
    full_pool_done = full_pool_plan.get("full_pool_scan_done") is True
    deep_scan_done = deep_scan_plan.get("deep_scan_done") is True
    provider_acceptance_done = no_loss.get("provider_backed_acceptance_done") is True
    browser_review_ready = browser_review.get("local_browser_qa_review_ready") is True
    browser_visual_passed = browser_evidence.get("candidate_visual_qa_evidence_passed") is True
    browser_perf_passed = browser_evidence.get("candidate_browser_performance_evidence_passed") is True
    rows = [
        _promotion_blocker_row(
            "local_fast_scan_ready",
            "local_readiness",
            "passed" if readiness.get("local_fast_scan_ready") is True else "blocked",
            passed=readiness.get("local_fast_scan_ready") is True,
            evidence=f"fast_scan_status={readiness.get('status')}; candidate_count={candidate_count}",
            next_action="Keep quick/watchlist/custom scan modes button-gated and cache-only.",
            blocks_promotion=True,
        ),
        _promotion_blocker_row(
            "no_feature_loss_local_contract_ready",
            "feature_parity",
            "passed" if no_loss.get("local_no_feature_loss_contract_ready") is True else "blocked",
            passed=no_loss.get("local_no_feature_loss_contract_ready") is True,
            evidence=f"local_blockers={no_loss.get('local_blocker_count')}; production_blockers={no_loss.get('production_blocker_count')}",
            next_action="Keep no-feature-loss rows visible and close local blockers before production promotion.",
            blocks_promotion=True,
        ),
        _promotion_blocker_row(
            "legacy_retirement_triage_clear",
            "legacy_parity",
            "passed" if replacement.get("legacy_retirement_ready") is True else "blocked_legacy_retirement",
            passed=replacement.get("legacy_retirement_ready") is True,
            evidence=f"blocking_gap_count={replacement.get('blocking_gap_count')}; critical_gap_count={replacement.get('critical_gap_count')}",
            next_action="Resolve legacy signal/output/provider/browser/full/deep blockers before retiring old radar fallback.",
            blocks_promotion=True,
        ),
        _promotion_blocker_row(
            "provider_signal_coverage_complete",
            "provider_acceptance",
            "passed" if provider_gap_count == 0 and provider_acceptance_done else "pending_provider_acceptance",
            passed=provider_gap_count == 0 and provider_acceptance_done,
            evidence=f"provider_gap_count={provider_gap_count}; provider_backed_acceptance_done={provider_acceptance_done}",
            next_action="Run explicit provider-backed radar parity samples after Tushare interface validation is ready.",
            blocks_promotion=True,
            evidence_kind="provider_acceptance_required",
        ),
        _promotion_blocker_row(
            "current_freshness_ready",
            "freshness",
            "passed" if freshness_ready else "research_only_freshness",
            passed=freshness_ready,
            evidence=f"freshness={freshness.get('source') or 'missing'}:{freshness.get('state') or 'unknown'}",
            next_action="Require trade-calendar current evidence before production radar promotion.",
            blocks_promotion=True,
        ),
        _promotion_blocker_row(
            "browser_visual_and_performance_reviewed",
            "browser_qa",
            "passed" if browser_review_ready and browser_visual_passed and browser_perf_passed else "pending_browser_qa_review",
            passed=browser_review_ready and browser_visual_passed and browser_perf_passed,
            evidence=f"review_ready={browser_review_ready}; visual={browser_visual_passed}; performance={browser_perf_passed}",
            next_action="Run and review ignored local browser QA evidence, then promote durable CI/browser evidence separately.",
            blocks_promotion=True,
            evidence_kind="browser_evidence_required",
        ),
        _promotion_blocker_row(
            "result_delta_clarity_complete",
            "result_delta",
            "passed" if result_delta.get("previous_cache_diff_done") is True else "pending_previous_cache_diff",
            passed=result_delta.get("previous_cache_diff_done") is True,
            evidence=f"previous_cache_diff_done={result_delta.get('previous_cache_diff_done')}; visible_gap_count={result_delta.get('visible_gap_count')}",
            next_action="Keep added/removed/rank/score delta rows visible when a previous radar packet exists.",
            blocks_promotion=False,
        ),
        _promotion_blocker_row(
            "runtime_budget_ready_not_perf_trace",
            "performance",
            "pending_browser_performance_trace"
            if runtime_budget.get("browser_performance_trace_done") is not True
            else "passed",
            passed=runtime_budget.get("browser_performance_trace_done") is True,
            evidence=f"browser_performance_trace_done={runtime_budget.get('browser_performance_trace_done')}; large_universe_worker_required={runtime_budget.get('large_universe_worker_required')}",
            next_action="Use runtime budget as local guard only; browser trace remains required for production promotion.",
            blocks_promotion=True,
        ),
        _promotion_blocker_row(
            "full_pool_execution_complete",
            "worker_pipeline",
            "passed" if full_pool_done else "pending_worker_execution",
            passed=full_pool_done,
            evidence=f"full_pool_scan_done={full_pool_done}; worker_task_required={full_pool_plan.get('worker_task_required')}",
            next_action="Implement worker-backed full-pool execution without page-render scanning.",
            blocks_promotion=True,
            evidence_kind="worker_execution_required",
        ),
        _promotion_blocker_row(
            "deep_scan_execution_complete",
            "worker_pipeline",
            "passed" if deep_scan_done else "pending_worker_execution",
            passed=deep_scan_done,
            evidence=f"deep_scan_done={deep_scan_done}; deepseek_called={deep_scan_plan.get('deepseek_called') is True}",
            next_action="Implement guarded deep scan with explicit model/provider gates and no action mutation.",
            blocks_promotion=True,
            evidence_kind="worker_execution_required",
        ),
        _promotion_blocker_row(
            "trade_action_isolation_preserved",
            "safety",
            "passed" if packet.get("does_not_execute_trades") is True and packet.get("does_not_modify_strategy_action") is True else "blocked",
            passed=packet.get("does_not_execute_trades") is True and packet.get("does_not_modify_strategy_action") is True,
            evidence="Candidate Radar remains research-only and isolated from strategy action, holdings, orders, and broker paths.",
            next_action="Keep production radar promotion separate from any future trading integration.",
            blocks_promotion=True,
        ),
    ]
    blocking_rows = [row for row in rows if row.get("blocks_promotion")]
    provider_rows = [row for row in rows if row.get("evidence_kind") == "provider_acceptance_required"]
    worker_rows = [row for row in rows if row.get("evidence_kind") == "worker_execution_required"]
    browser_rows = [row for row in rows if row.get("evidence_kind") == "browser_evidence_required"]
    promotion_ready = not blocking_rows
    contract = {
        "schema_version": "candidate_radar_promotion_blocker_audit.v1",
        "status": "candidate_radar_promotion_ready" if promotion_ready else "candidate_radar_promotion_blocked",
        "scope": "local_candidate_radar_promotion_audit_not_production_execution",
        "ltg": "LTG-13",
        "local_promotion_audit_ready": True,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "promotion_ready": promotion_ready,
        "row_count": len(rows),
        "blocking_promotion_count": len(blocking_rows),
        "provider_acceptance_blocker_count": len(provider_rows),
        "worker_execution_blocker_count": len(worker_rows),
        "browser_evidence_blocker_count": len(browser_rows),
        "blocking_promotion_keys": [str(row.get("criterion")) for row in blocking_rows],
        "high_priority_next_actions": [str(row.get("next_action")) for row in blocking_rows[:5]],
        "full_pool_scan_done": full_pool_done,
        "deep_scan_done": deep_scan_done,
        "provider_backed_acceptance_done": provider_acceptance_done,
        "browser_qa_review_ready": browser_review_ready,
        "browser_visual_evidence_passed": browser_visual_passed,
        "browser_performance_evidence_passed": browser_perf_passed,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "note": "This audit promotes no evidence by itself. It lists blockers that must be cleared before Candidate Radar can replace the legacy next-ticket radar without feature loss.",
    }
    return contract, rows


def _attach_candidate_radar_promotion_blocker_audit(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    contract, rows = _candidate_radar_promotion_blocker_audit(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_promotion_blocking_count"] = contract["blocking_promotion_count"]
    counts["candidate_radar_promotion_provider_blocker_count"] = contract["provider_acceptance_blocker_count"]
    counts["candidate_radar_promotion_worker_blocker_count"] = contract["worker_execution_blocker_count"]
    counts["candidate_radar_promotion_browser_blocker_count"] = contract["browser_evidence_blocker_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_promotion_audit_is_local"] = True
    policy["candidate_radar_promotion_audit_is_not_production_replacement"] = True
    policy["candidate_radar_promotion_requires_provider_worker_browser_evidence"] = True
    view["counts"] = counts
    view["policy"] = policy
    view["candidate_radar_promotion_blocker_audit"] = contract
    view["candidate_radar_promotion_blocker_rows"] = rows
    return view


def _activation_receipt_row(
    activation_key: str,
    category: str,
    status: str,
    *,
    local_ready: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "activation_key": activation_key,
        "category": category,
        "status": status,
        "local_ready": bool(local_ready),
        "production_blocker": bool(production_blocker),
        "user_visible": True,
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_radar_production_activation_receipt(
    packet: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    quick_receipt = _as_dict(packet.get("quick_scan_execution_receipt"))
    no_loss = _as_dict(packet.get("no_feature_loss_acceptance_contract"))
    replacement = _as_dict(packet.get("replacement_gap_triage_contract"))
    promotion = _as_dict(packet.get("candidate_radar_promotion_blocker_audit"))
    priority_explanation = _as_dict(packet.get("candidate_priority_explanation_contract"))
    browser_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    full_pool_plan = _as_dict(packet.get("full_pool_scan_plan"))
    deep_scan_plan = _as_dict(packet.get("deep_scan_plan"))
    policy = _as_dict(packet.get("policy"))
    full_pool_done = full_pool_plan.get("full_pool_scan_done") is True
    deep_scan_done = deep_scan_plan.get("deep_scan_done") is True
    provider_acceptance_done = promotion.get("provider_backed_acceptance_done") is True
    browser_review_ready = browser_review.get("local_browser_qa_review_ready") is True
    trade_guard_ready = (
        packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("candidate_is_not_buy_instruction") is not False
    )
    rows = [
        _activation_receipt_row(
            "local_quick_scan_receipt_ready",
            "local_fast_path",
            "passed" if quick_receipt.get("local_quick_scan_receipt_ready") is True else "blocked",
            local_ready=quick_receipt.get("local_quick_scan_receipt_ready") is True,
            production_blocker=False,
            evidence=f"quick_status={quick_receipt.get('status')}; blockers={quick_receipt.get('local_blocker_count')}",
            next_action="Keep cache/quick/watchlist/custom scan receipt visible before comparing candidates.",
        ),
        _activation_receipt_row(
            "no_feature_loss_surface_ready",
            "feature_parity",
            "passed" if no_loss.get("local_no_feature_loss_contract_ready") is True else "blocked",
            local_ready=no_loss.get("local_no_feature_loss_contract_ready") is True,
            production_blocker=False,
            evidence=f"no_loss_status={no_loss.get('status')}; visible_gaps={no_loss.get('visible_gap_count')}",
            next_action="Keep legacy signal, output, provider, freshness, and runtime gaps visible.",
        ),
        _activation_receipt_row(
            "production_promotion_blocked_visible",
            "promotion_boundary",
            "passed" if promotion.get("local_promotion_audit_ready") is True else "blocked",
            local_ready=promotion.get("local_promotion_audit_ready") is True,
            production_blocker=promotion.get("promotion_ready") is not True,
            evidence=f"promotion_ready={promotion.get('promotion_ready')}; blockers={promotion.get('blocking_promotion_count')}",
            next_action="Use the blocker audit as the promotion checklist; do not treat it as promotion evidence.",
        ),
        _activation_receipt_row(
            "full_pool_worker_execution_required",
            "worker_pipeline",
            "completed" if full_pool_done else "pending_worker_execution",
            local_ready=True,
            production_blocker=not full_pool_done,
            evidence=f"full_pool_scan_done={full_pool_done}; plan_status={full_pool_plan.get('status')}",
            next_action="Run future explicit worker-backed full-pool execution without page-render scanning.",
        ),
        _activation_receipt_row(
            "deep_scan_worker_execution_required",
            "worker_pipeline",
            "completed" if deep_scan_done else "pending_worker_execution",
            local_ready=True,
            production_blocker=not deep_scan_done,
            evidence=f"deep_scan_done={deep_scan_done}; plan_status={deep_scan_plan.get('status')}",
            next_action="Run future guarded deep scan as a task; keep model/provider calls explicitly gated.",
        ),
        _activation_receipt_row(
            "provider_backed_acceptance_required",
            "provider_acceptance",
            "completed" if provider_acceptance_done else "pending_provider_acceptance",
            local_ready=True,
            production_blocker=not provider_acceptance_done,
            evidence=f"provider_backed_acceptance_done={provider_acceptance_done}",
            next_action="Validate provider-backed radar parity only through explicit acceptance tasks.",
        ),
        _activation_receipt_row(
            "browser_visual_performance_review_required",
            "browser_qa",
            "reviewed_local_artifact" if browser_review_ready else "pending_browser_review",
            local_ready=True,
            production_blocker=True,
            evidence=f"local_browser_qa_review_ready={browser_review_ready}; durable_ci_evidence_complete=false",
            next_action="Promote only durable visual and performance evidence after explicit review.",
        ),
        _activation_receipt_row(
            "legacy_retirement_stays_blocked",
            "legacy_retirement",
            "blocked" if replacement.get("legacy_retirement_ready") is not True else "ready_for_review",
            local_ready=True,
            production_blocker=replacement.get("legacy_retirement_ready") is not True,
            evidence=f"legacy_retirement_ready={replacement.get('legacy_retirement_ready')}; blocking_gaps={replacement.get('blocking_gap_count')}",
            next_action="Keep Streamlit fallback until full/deep/provider/browser evidence clears the retirement gate.",
        ),
        _activation_receipt_row(
            "priority_explanation_research_only",
            "research_boundary",
            "passed"
            if priority_explanation.get("priority_explanation_is_not_trade_signal") is True
            else "blocked",
            local_ready=priority_explanation.get("priority_explanation_is_not_trade_signal") is True,
            production_blocker=False,
            evidence=f"cached_rank_preserved={priority_explanation.get('cached_rank_preserved')}; rescore={priority_explanation.get('does_not_recompute_score') is not True}",
            next_action="Keep candidate priority explanations as cache-rank explanations, not trade signals.",
        ),
        _activation_receipt_row(
            "trade_action_isolation_preserved",
            "safety",
            "passed" if trade_guard_ready else "blocked",
            local_ready=trade_guard_ready,
            production_blocker=not trade_guard_ready,
            evidence="Candidate Radar remains isolated from action, holdings, orders, and broker paths.",
            next_action="Keep radar promotion separate from any future trading integration.",
        ),
        _activation_receipt_row(
            "no_external_calls_from_receipt",
            "safety",
            "passed"
            if policy.get("does_not_call_tushare") is True
            and policy.get("does_not_call_deepseek") is True
            and policy.get("does_not_call_github") is True
            else "blocked",
            local_ready=policy.get("does_not_call_tushare") is True
            and policy.get("does_not_call_deepseek") is True
            and policy.get("does_not_call_github") is True,
            production_blocker=False,
            evidence="Activation receipt is computed from the local packet and does not invoke providers, models, or remote services.",
            next_action="Preserve GET/cache/render no-provider boundaries and keep external-capable work POST gated.",
        ),
    ]
    local_blockers = [row["activation_key"] for row in rows if not row.get("local_ready")]
    production_blockers = [row["activation_key"] for row in rows if row.get("production_blocker")]
    missing_evidence_items = [
        key
        for key, done in {
            "full_pool_worker_execution_evidence": full_pool_done,
            "deep_scan_worker_execution_evidence": deep_scan_done,
            "provider_backed_parity_call_ledger": provider_acceptance_done,
            "browser_visual_performance_review": False,
            "durable_ci_or_packaged_runtime_evidence": False,
            "legacy_retirement_acceptance": replacement.get("legacy_retirement_ready") is True,
        }.items()
        if not done
    ]
    local_ready = not local_blockers
    contract = {
        "schema_version": "candidate_radar_production_activation_receipt.v1",
        "status": (
            "candidate_radar_activation_receipt_ready_production_blocked"
            if local_ready
            else "candidate_radar_activation_receipt_blocked"
        ),
        "scope": "local_candidate_radar_activation_receipt_no_execution_or_provider_call",
        "ltg": "LTG-13",
        "local_activation_receipt_ready": local_ready,
        "production_radar_replacement_complete": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "full_pool_scan_done": full_pool_done,
        "deep_scan_done": deep_scan_done,
        "provider_backed_acceptance_done": provider_acceptance_done,
        "browser_visual_performance_reviewed": False,
        "durable_ci_evidence_complete": False,
        "candidate_is_not_buy_instruction": True,
        "allowed_next_step": "explicit_worker_full_pool_and_deep_scan_acceptance_then_provider_backed_parity_and_browser_review",
        "not_allowed_next_steps": [
            "treat quick scan as production radar replacement",
            "treat full_pool_plan as full_pool_scan_done",
            "treat deep_scan_plan as deep_scan_done",
            "promote local browser artifact without explicit review",
            "call Tushare/DeepSeek/GitHub from GET cache or render",
            "treat candidates as buy instructions",
            "modify strategy action",
        ],
        "missing_evidence_items": missing_evidence_items,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "pending_evidence_count": len(missing_evidence_items),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This receipt only organizes the remaining activation evidence. It does not execute full-pool/deep-scan work, call providers/models, promote browser artifacts, retire legacy radar, or complete production replacement.",
    }
    return contract, rows


def _attach_candidate_radar_production_activation_receipt(packet: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(packet)
    contract, rows = _candidate_radar_production_activation_receipt(view)
    counts = dict(_as_dict(view.get("counts")))
    counts["candidate_radar_activation_receipt_ready"] = contract["local_activation_receipt_ready"]
    counts["candidate_radar_activation_blocker_count"] = contract["production_blocker_count"]
    counts["candidate_radar_activation_pending_evidence_count"] = contract["pending_evidence_count"]
    counts["candidate_radar_activation_row_count"] = contract["row_count"]
    policy = dict(_as_dict(view.get("policy")))
    policy["candidate_radar_activation_receipt_is_local"] = True
    policy["candidate_radar_activation_receipt_is_not_production_replacement"] = True
    policy["candidate_radar_activation_requires_worker_provider_browser_evidence"] = True
    ledger = _as_list(view.get("call_ledger"))
    ledger.append(
        _candidate_call_ledger_row(
            api="local_candidate_radar_production_activation_receipt",
            source_snapshot="candidate_radar_packet",
            row_count=len(rows),
            call_status=contract["status"],
        )
    )
    view["counts"] = counts
    view["policy"] = policy
    view["call_ledger"] = ledger
    view["candidate_radar_production_activation_receipt"] = contract
    view["candidate_radar_production_activation_rows"] = rows
    return view


def _result_delta_clarity_row(
    criterion: str,
    status: str,
    *,
    passed: bool,
    evidence: str,
    user_visible: bool = True,
    gap_visible: bool = False,
    production_pending: bool = False,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "user_visible": bool(user_visible),
        "gap_visible": bool(gap_visible),
        "production_pending": bool(production_pending),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _candidate_delta_signature(candidate_rows: list[dict[str, Any]]) -> str:
    compact_rows = [
        {
            "rank": row.get("rank"),
            "ticker": row.get("ticker"),
            "score": row.get("score"),
            "status_label": row.get("status_label"),
            "action_state": row.get("action_state"),
            "data_gaps": row.get("data_gaps"),
        }
        for row in candidate_rows[:FAST_SCAN_DISPLAY_CANDIDATE_LIMIT]
    ]
    serialized = json.dumps(compact_rows, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _delta_candidate_key(row: Mapping[str, Any], fallback_index: int) -> str:
    key = _first_non_empty(row, ["ticker", "ts_code", "code", "stock_code", "symbol"])
    return _safe_text(key, limit=32).upper() or f"ROW-{fallback_index}"


def _delta_candidate_map(candidate_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(candidate_rows[:FAST_SCAN_DISPLAY_CANDIDATE_LIMIT], start=1):
        key = _delta_candidate_key(row, index)
        if key in mapped:
            continue
        mapped[key] = {
            "ticker": key,
            "rank": row.get("rank") or index,
            "score": row.get("score"),
            "status_label": row.get("status_label"),
            "action_state": row.get("action_state"),
        }
    return mapped


def _previous_candidate_rows_from_packet(previous_packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in _as_list(previous_packet.get("candidate_rows")) if isinstance(row, Mapping)]
    if rows:
        return rows[:FAST_SCAN_DISPLAY_CANDIDATE_LIMIT]
    candidates = _as_list(previous_packet.get("candidates"))
    return _candidate_rows(candidates)


def _previous_cache_candidate_diff(
    previous_packet: Mapping[str, Any] | None,
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    previous_available = isinstance(previous_packet, Mapping) and bool(previous_packet)
    previous_rows = _previous_candidate_rows_from_packet(previous_packet or {}) if previous_available else []
    current_map = _delta_candidate_map(candidate_rows)
    previous_map = _delta_candidate_map(previous_rows)
    current_keys = list(current_map.keys())
    previous_keys = list(previous_map.keys())
    added = [key for key in current_keys if key not in previous_map]
    removed = [key for key in previous_keys if key not in current_map]
    shared = [key for key in current_keys if key in previous_map]
    rank_changed = [key for key in shared if current_map[key].get("rank") != previous_map[key].get("rank")]
    score_changed = [key for key in shared if current_map[key].get("score") != previous_map[key].get("score")]
    status_changed = [
        key
        for key in shared
        if current_map[key].get("status_label") != previous_map[key].get("status_label")
        or current_map[key].get("action_state") != previous_map[key].get("action_state")
    ]
    diff_rows: list[dict[str, Any]] = []
    for key in added[:30]:
        diff_rows.append(
            {
                "change_type": "added",
                "ticker": key,
                "previous_rank": None,
                "current_rank": current_map[key].get("rank"),
                "previous_score": None,
                "current_score": current_map[key].get("score"),
                "user_visible": True,
            }
        )
    for key in removed[:30]:
        diff_rows.append(
            {
                "change_type": "removed",
                "ticker": key,
                "previous_rank": previous_map[key].get("rank"),
                "current_rank": None,
                "previous_score": previous_map[key].get("score"),
                "current_score": None,
                "user_visible": True,
            }
        )
    for key in sorted(set(rank_changed + score_changed + status_changed))[:30]:
        diff_rows.append(
            {
                "change_type": "updated",
                "ticker": key,
                "previous_rank": previous_map[key].get("rank"),
                "current_rank": current_map[key].get("rank"),
                "previous_score": previous_map[key].get("score"),
                "current_score": current_map[key].get("score"),
                "rank_changed": key in rank_changed,
                "score_changed": key in score_changed,
                "status_changed": key in status_changed,
                "user_visible": True,
            }
        )
    for row in diff_rows:
        row.update(
            {
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "candidate_is_not_buy_instruction": True,
            }
        )
    changed_count = len(added) + len(removed) + len(set(rank_changed + score_changed + status_changed))
    previous_signature = str(_as_dict(previous_packet or {}).get("result_delta_clarity_contract", {}).get("candidate_delta_signature") or "")
    return {
        "previous_cache_available": previous_available,
        "previous_cache_diff_done": previous_available,
        "previous_scan_mode": _safe_text(_as_dict(previous_packet or {}).get("scan_mode"), limit=40),
        "previous_cache_source": _safe_text(_as_dict(previous_packet or {}).get("cache_source"), limit=60),
        "previous_candidate_delta_signature": previous_signature or _candidate_delta_signature(previous_rows),
        "previous_candidate_count": len(previous_rows),
        "candidate_added_count": len(added),
        "candidate_removed_count": len(removed),
        "candidate_rank_changed_count": len(rank_changed),
        "candidate_score_changed_count": len(score_changed),
        "candidate_status_changed_count": len(status_changed),
        "candidate_unchanged_count": max(0, len(shared) - len(set(rank_changed + score_changed + status_changed))),
        "candidate_changed_count": changed_count,
        "added_tickers": added[:20],
        "removed_tickers": removed[:20],
        "rank_changed_tickers": rank_changed[:20],
        "score_changed_tickers": score_changed[:20],
        "status_changed_tickers": status_changed[:20],
        "diff_rows": diff_rows,
        "diff_row_count": len(diff_rows),
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _result_delta_clarity_contract(
    *,
    scan_mode: str,
    candidate_rows: list[dict[str, Any]],
    counts: Mapping[str, Any],
    coverage: Mapping[str, Any],
    scan_execution_summary: Mapping[str, Any],
    scan_acceptance_rows: list[dict[str, Any]],
    runtime_budget_contract: Mapping[str, Any],
    local_pool_audit: Mapping[str, Any],
    full_pool_scan_plan: Mapping[str, Any],
    deep_scan_plan: Mapping[str, Any],
    previous_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    coverage_detail = _as_dict(coverage.get("coverage_detail_summary"))
    freshness_state = _as_dict(coverage.get("freshness_state"))
    acceptance_by_key = {str(row.get("check_key")): row for row in scan_acceptance_rows}
    provider_gap_count = int(scan_execution_summary.get("provider_gap_count") or 0)
    skipped_reason_count = int(coverage.get("skipped_reason_count") or 0)
    truncated_count = int(runtime_budget_contract.get("candidate_display_truncated_count") or 0)
    full_pool_plan_ready = full_pool_scan_plan.get("status") == "full_pool_plan_ready"
    deep_scan_plan_ready = deep_scan_plan.get("status") == "deep_scan_plan_ready"
    previous_diff = _previous_cache_candidate_diff(previous_packet, candidate_rows)
    previous_diff_done = bool(previous_diff.get("previous_cache_diff_done"))
    rows = [
        _result_delta_clarity_row(
            "candidate_count_and_mix_visible",
            "passed",
            passed=True,
            evidence=(
                f"candidate_count={counts.get('candidate_count')}; "
                f"ready={counts.get('ready_count')}; observe={counts.get('observe_count')}; verify={counts.get('verify_count')}"
            ),
        ),
        _result_delta_clarity_row(
            "candidate_display_cap_visible",
            "capped_visible" if truncated_count else "passed",
            passed=True,
            evidence=(
                f"displayed={runtime_budget_contract.get('candidate_displayed_count')}; "
                f"limit={runtime_budget_contract.get('display_candidate_limit')}; truncated={truncated_count}"
            ),
            gap_visible=bool(truncated_count),
        ),
        _result_delta_clarity_row(
            "skipped_reason_visibility",
            "gap_reported" if skipped_reason_count else "passed",
            passed=True,
            evidence=f"skipped_reason_count={skipped_reason_count}",
            gap_visible=bool(skipped_reason_count),
        ),
        _result_delta_clarity_row(
            "provider_gap_visibility",
            "gap_reported" if provider_gap_count else "passed",
            passed=True,
            evidence=f"provider_gap_count={provider_gap_count}",
            gap_visible=bool(provider_gap_count),
        ),
        _result_delta_clarity_row(
            "freshness_state_visibility",
            str(acceptance_by_key.get("freshness_boundary", {}).get("status") or "unknown"),
            passed=True,
            evidence=f"freshness={freshness_state.get('source') or 'missing'}:{freshness_state.get('state') or 'unknown'}",
            gap_visible=str(acceptance_by_key.get("freshness_boundary", {}).get("status") or "") != "passed",
        ),
        _result_delta_clarity_row(
            "scan_mode_transition_visibility",
            "passed",
            passed=True,
            evidence=(
                f"scan_mode={scan_mode}; family={scan_execution_summary.get('scan_family')}; "
                f"fallback={scan_execution_summary.get('unsupported_scan_mode_fallback')}"
            ),
        ),
        _result_delta_clarity_row(
            "local_pool_delta_visibility",
            "input_reported" if local_pool_audit else "not_applicable",
            passed=True,
            evidence=(
                f"input={local_pool_audit.get('input_candidate_count')}; "
                f"normalized={local_pool_audit.get('normalized_candidate_count')}; "
                f"skipped={local_pool_audit.get('skipped_candidate_count')}"
            )
            if local_pool_audit
            else "current scan did not consume local pool input.",
            gap_visible=bool(local_pool_audit and local_pool_audit.get("skipped_candidate_count")),
        ),
        _result_delta_clarity_row(
            "full_pool_deep_scan_boundary_visibility",
            "plan_only" if full_pool_plan_ready or deep_scan_plan_ready else "pending",
            passed=True,
            evidence=(
                f"full_pool_plan_ready={full_pool_plan_ready}; full_pool_scan_done={full_pool_scan_plan.get('full_pool_scan_done') is True}; "
                f"deep_scan_plan_ready={deep_scan_plan_ready}; deep_scan_done={deep_scan_plan.get('deep_scan_done') is True}"
            ),
            gap_visible=not (full_pool_scan_plan.get("full_pool_scan_done") is True and deep_scan_plan.get("deep_scan_done") is True),
        ),
        _result_delta_clarity_row(
            "previous_cache_diff_pending",
            "completed_previous_cache_diff" if previous_diff_done else "pending_previous_cache_diff",
            passed=previous_diff_done,
            evidence=(
                f"previous_available={previous_diff.get('previous_cache_available')}; "
                f"added={previous_diff.get('candidate_added_count')}; removed={previous_diff.get('candidate_removed_count')}; "
                f"rank_changed={previous_diff.get('candidate_rank_changed_count')}; score_changed={previous_diff.get('candidate_score_changed_count')}"
            ),
            gap_visible=bool(previous_diff.get("candidate_changed_count")),
            production_pending=not previous_diff_done,
        ),
        _result_delta_clarity_row(
            "browser_visual_delta_qa_pending",
            "pending_visual_qa",
            passed=False,
            evidence="Browser viewport/performance QA is not executed by the local cache contract.",
            production_pending=True,
        ),
        _result_delta_clarity_row(
            "trade_action_boundary",
            "passed",
            passed=True,
            evidence="Result change cues never modify strategy action, holdings, or orders.",
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if not row.get("passed") and not row.get("production_pending")]
    visible_gaps = [row["criterion"] for row in rows if row.get("gap_visible")]
    production_pending = [row["criterion"] for row in rows if row.get("production_pending")]
    local_ready = not local_blockers
    return {
        "schema_version": "candidate_radar_result_delta_clarity.v1",
        "status": (
            "result_delta_clarity_local_ready_browser_qa_pending"
            if local_ready and previous_diff_done
            else "result_delta_clarity_local_ready_previous_diff_pending"
            if local_ready
            else "result_delta_clarity_blocked"
        ),
        "scope": (
            "local_result_delta_visibility_and_previous_cache_diff_not_browser_visual_qa"
            if previous_diff_done
            else "local_result_delta_visibility_contract_not_previous_cache_diff_or_browser_visual_qa"
        ),
        "ltg": "LTG-13/LTG-14",
        "scan_mode": scan_mode,
        "candidate_delta_signature": _candidate_delta_signature(candidate_rows),
        "local_result_delta_clarity_ready": local_ready,
        "previous_cache_available": bool(previous_diff.get("previous_cache_available")),
        "previous_cache_diff_done": previous_diff_done,
        "previous_scan_mode": previous_diff.get("previous_scan_mode"),
        "previous_cache_source": previous_diff.get("previous_cache_source"),
        "previous_candidate_delta_signature": previous_diff.get("previous_candidate_delta_signature"),
        "previous_candidate_count": previous_diff.get("previous_candidate_count"),
        "candidate_added_count": previous_diff.get("candidate_added_count"),
        "candidate_removed_count": previous_diff.get("candidate_removed_count"),
        "candidate_rank_changed_count": previous_diff.get("candidate_rank_changed_count"),
        "candidate_score_changed_count": previous_diff.get("candidate_score_changed_count"),
        "candidate_status_changed_count": previous_diff.get("candidate_status_changed_count"),
        "candidate_unchanged_count": previous_diff.get("candidate_unchanged_count"),
        "candidate_changed_count": previous_diff.get("candidate_changed_count"),
        "added_tickers": previous_diff.get("added_tickers"),
        "removed_tickers": previous_diff.get("removed_tickers"),
        "rank_changed_tickers": previous_diff.get("rank_changed_tickers"),
        "score_changed_tickers": previous_diff.get("score_changed_tickers"),
        "status_changed_tickers": previous_diff.get("status_changed_tickers"),
        "previous_cache_diff_row_count": previous_diff.get("diff_row_count"),
        "browser_visual_delta_qa_done": False,
        "production_radar_replacement_complete": False,
        "candidate_count": len(candidate_rows),
        "candidate_input_count": int(coverage_detail.get("candidate_input_count") or 0),
        "candidate_display_truncated_count": truncated_count,
        "skipped_reason_count": skipped_reason_count,
        "provider_gap_count": provider_gap_count,
        "visible_gap_count": len(visible_gaps),
        "production_pending_count": len(production_pending),
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "local_blockers": local_blockers,
        "visible_gaps": visible_gaps,
        "production_pending_items": production_pending,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "rows": rows,
        "previous_cache_diff_rows": previous_diff.get("diff_rows") or [],
        "note": "This contract makes candidate result-change cues visible without rescoring, provider refreshes, timers, browser QA, or trade/action mutation. When a previous persisted packet exists, it also computes a local previous-cache diff.",
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


def _full_pool_local_execution_row(
    receipt_key: str,
    status: str,
    *,
    passed: bool,
    production_blocker: bool,
    evidence: str,
) -> dict[str, Any]:
    return {
        "receipt_key": receipt_key,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
    }


def _full_pool_local_execution_receipt(
    *,
    scan_mode: str,
    local_pool_audit: Mapping[str, Any],
    candidate_rows: list[dict[str, Any]],
    full_pool_scan_plan: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    is_local_full_pool = scan_mode == "full_pool_local_scan"
    normalized_count = int(local_pool_audit.get("normalized_candidate_count") or 0)
    input_count = int(local_pool_audit.get("input_candidate_count") or 0)
    truncated_count = int(local_pool_audit.get("truncated_candidate_count") or 0)
    freshness = _as_dict(coverage.get("freshness_state"))
    provider_gap_count = int(_as_dict(coverage.get("coverage_detail_summary")).get("provider_blocked_group_count") or 0) + int(
        _as_dict(coverage.get("coverage_detail_summary")).get("stale_input_group_count") or 0
    ) + int(_as_dict(coverage.get("coverage_detail_summary")).get("missing_provider_data_group_count") or 0)
    local_execution_done = is_local_full_pool and normalized_count > 0
    rows = [
        _full_pool_local_execution_row(
            "explicit_post_task_required",
            "passed" if is_local_full_pool else "not_applicable",
            passed=is_local_full_pool,
            production_blocker=False,
            evidence=f"scan_mode={scan_mode}; page_render_starts_full_pool=false; cache_get_starts_full_pool=false",
        ),
        _full_pool_local_execution_row(
            "local_universe_consumed",
            "passed" if normalized_count else "blocked_empty_local_universe",
            passed=normalized_count > 0,
            production_blocker=not local_execution_done,
            evidence=f"input={input_count}; normalized={normalized_count}; source={local_pool_audit.get('input_source')}",
        ),
        _full_pool_local_execution_row(
            "display_cap_visible",
            "capped_visible" if truncated_count else "passed",
            passed=True,
            production_blocker=False,
            evidence=f"displayed={len(candidate_rows)}; input_limit={local_pool_audit.get('max_local_candidates')}; truncated={truncated_count}",
        ),
        _full_pool_local_execution_row(
            "provider_not_refreshed",
            "provider_gaps_visible" if provider_gap_count else "passed",
            passed=True,
            production_blocker=True,
            evidence=f"provider_gap_count={provider_gap_count}; provider_refresh_executed=false",
        ),
        _full_pool_local_execution_row(
            "freshness_boundary_visible",
            "research_only_reported" if freshness.get("source") == "missing" else "visible",
            passed=True,
            production_blocker=True,
            evidence=f"freshness={freshness.get('source') or 'missing'}:{freshness.get('state') or 'unknown'}",
        ),
        _full_pool_local_execution_row(
            "production_full_market_acceptance_pending",
            "pending_provider_worker_browser_acceptance",
            passed=False,
            production_blocker=True,
            evidence=(
                f"local_execution_done={local_execution_done}; "
                f"full_pool_plan_status={full_pool_scan_plan.get('status')}; provider_backed_acceptance_done=false"
            ),
        ),
        _full_pool_local_execution_row(
            "trade_action_boundary",
            "passed",
            passed=True,
            production_blocker=False,
            evidence="Local full-pool execution writes research candidates only and never mutates strategy action, holdings, or orders.",
        ),
    ]
    local_blockers = [row["receipt_key"] for row in rows if not row.get("passed") and not row.get("production_blocker")]
    production_blockers = [row["receipt_key"] for row in rows if row.get("production_blocker")]
    receipt = {
        "schema_version": "candidate_radar_full_pool_local_execution_receipt.v1",
        "status": (
            "full_pool_local_execution_ready_production_pending"
            if local_execution_done
            else "full_pool_local_execution_blocked_empty_universe"
            if is_local_full_pool
            else "full_pool_local_execution_not_run"
        ),
        "scope": "explicit_local_universe_execution_not_provider_backed_full_market_acceptance",
        "ltg": "LTG-13",
        "scan_mode": scan_mode,
        "local_full_pool_execution_done": local_execution_done,
        "production_full_pool_scan_done": False,
        "full_pool_scan_done": False,
        "provider_backed_acceptance_done": False,
        "worker_backed_execution_done": False,
        "browser_visual_qa_done": False,
        "browser_performance_trace_done": False,
        "legacy_retirement_ready": False,
        "legacy_fallback_required": True,
        "input_candidate_count": input_count,
        "normalized_candidate_count": normalized_count,
        "candidate_row_count": len(candidate_rows),
        "truncated_candidate_count": truncated_count,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "row_count": len(rows),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "not_allowed_next_steps": [
            "treat_local_full_pool_execution_as_provider_backed_full_market_acceptance",
            "retire_legacy_radar_after_local_execution_only",
            "convert_candidate_rows_to_buy_instruction",
            "refresh_provider_from_full_pool_local_scan",
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "candidate_is_not_buy_instruction": True,
        "rows": rows,
        "note": "This receipt proves only an explicit local-universe Candidate Radar task consumed local candidates and wrote a packet. It is not real provider-backed full-market acceptance.",
    }
    return receipt, rows


def _deep_scan_required_signal_rows(provider_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_group = {str(row.get("signal_group") or ""): row for row in provider_rows}
    for requirement in RADAR_PROVIDER_SIGNAL_REQUIREMENTS:
        coverage = by_group.get(str(requirement["signal_group"])) or {}
        coverage_status = str(coverage.get("coverage_status") or "missing_provider_data")
        rows.append(
            {
                "signal_group": requirement["signal_group"],
                "label": requirement["label"],
                "required_apis": requirement["apis"],
                "legacy_role": requirement["legacy_role"],
                "coverage_status": coverage_status,
                "matched_provider_row_count": coverage.get("matched_provider_row_count") or 0,
                "ready_for_deep_scan": coverage_status == "available",
                "gap_visible": coverage_status != "available",
                "requires_explicit_provider_task": coverage_status != "available",
                "does_not_refresh_provider": True,
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _deep_scan_parity_rows(
    *,
    parity_rows: list[dict[str, Any]],
    output_contract_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in parity_rows:
        status = str(row.get("migration_status") or "")
        gap_visible = "missing" in status or "future" in status
        rows.append(
            {
                "kind": "legacy_parity",
                "key": row.get("key"),
                "label": row.get("label"),
                "migration_status": status,
                "ready_for_deep_scan": not gap_visible,
                "blocks_legacy_replacement": gap_visible,
                "gap_visible": gap_visible,
                "target_state": row.get("target_state"),
                "does_not_silently_drop_feature": True,
                "does_not_call_external_sources": True,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    for row in output_contract_rows:
        present = bool(row.get("present"))
        rows.append(
            {
                "kind": "output_contract",
                "key": row.get("field"),
                "label": row.get("field"),
                "migration_status": "mapped" if present else "missing_reported",
                "ready_for_deep_scan": present,
                "blocks_legacy_replacement": not present,
                "gap_visible": not present,
                "target_state": row.get("required_for"),
                "does_not_invent_value": True,
                "does_not_call_external_sources": True,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _deep_scan_stage_rows(
    *,
    candidate_rows: list[dict[str, Any]],
    provider_signal_rows: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
    freshness_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    provider_gap_count = sum(1 for row in provider_signal_rows if not row.get("ready_for_deep_scan"))
    parity_gap_count = sum(1 for row in parity_rows if row.get("gap_visible"))
    freshness = str(freshness_state.get("state") or "").lower()
    freshness_ready = freshness_state.get("source") != "missing" and freshness not in {
        "stale",
        "expired",
        "historical",
        "unknown",
    }
    rows = [
        {
            "stage": "load_local_candidate_universe",
            "status": "ready" if candidate_rows else "blocked_missing_local_candidates",
            "executed_now": False,
            "row_count": len(candidate_rows),
            "blocks_deep_scan": not bool(candidate_rows),
            "external_calls_triggered": False,
        },
        {
            "stage": "legacy_feature_parity",
            "status": "ready" if not parity_gap_count else "gaps_visible_do_not_replace_legacy",
            "executed_now": False,
            "gap_count": parity_gap_count,
            "blocks_deep_scan": bool(parity_gap_count),
            "external_calls_triggered": False,
        },
        {
            "stage": "provider_signal_inputs",
            "status": "ready" if not provider_gap_count else "provider_gaps_visible_no_refresh",
            "executed_now": False,
            "gap_count": provider_gap_count,
            "blocks_deep_scan": bool(provider_gap_count),
            "external_calls_triggered": False,
        },
        {
            "stage": "freshness_gate",
            "status": "ready" if freshness_ready else "research_only_until_current_freshness",
            "executed_now": False,
            "freshness_state": freshness_state.get("state") or "unknown",
            "blocks_deep_scan": not freshness_ready,
            "external_calls_triggered": False,
        },
        {
            "stage": "async_worker_execution",
            "status": "future_worker_required",
            "executed_now": False,
            "blocks_deep_scan": True,
            "external_calls_triggered": False,
        },
        {
            "stage": "manual_deep_research_boundary",
            "status": "manual_only_future_task",
            "executed_now": False,
            "blocks_deep_scan": False,
            "external_calls_triggered": False,
        },
        {
            "stage": "write_deep_scan_packet",
            "status": "not_executed_by_plan",
            "executed_now": False,
            "blocks_deep_scan": True,
            "external_calls_triggered": False,
        },
    ]
    for row in rows:
        row.update(
            {
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "candidate_is_not_buy_instruction": True,
            }
        )
    return rows


def _deep_scan_blocker_rows(
    *,
    stage_rows: list[dict[str, Any]],
    provider_signal_rows: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage in stage_rows:
        if not stage.get("blocks_deep_scan"):
            continue
        rows.append(
            {
                "blocker_key": f"stage_{stage.get('stage')}",
                "severity": "production_required" if stage.get("stage") in {"async_worker_execution", "write_deep_scan_packet"} else "readiness_gap",
                "status": stage.get("status"),
                "message": f"Deep scan stage {stage.get('stage')} is not ready for execution.",
                "blocks_deep_scan": True,
            }
        )
    for row in provider_signal_rows:
        if row.get("ready_for_deep_scan"):
            continue
        rows.append(
            {
                "blocker_key": f"provider_{row.get('signal_group')}",
                "severity": "coverage_gap",
                "status": row.get("coverage_status") or "missing_provider_data",
                "message": f"{row.get('label')} coverage is not ready for deep scan.",
                "blocks_deep_scan": True,
            }
        )
    parity_gap_count = sum(1 for row in parity_rows if row.get("gap_visible"))
    if parity_gap_count:
        rows.append(
            {
                "blocker_key": "legacy_feature_parity_gaps",
                "severity": "parity_gap",
                "status": "gaps_visible",
                "message": "Legacy radar features are not all mapped; keep Streamlit fallback until gaps are closed.",
                "gap_count": parity_gap_count,
                "blocks_deep_scan": True,
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


def _build_deep_scan_plan(
    snapshot_map: Mapping[str, Any],
    payload_safe: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any]:
    radar_packet = _as_dict(snapshot_map.get("radar_packet") or snapshot_map.get("command_center_radar_packet"))
    candidates = _as_list(snapshot_map.get("next_ticket_candidates")) or _as_list(radar_packet.get("top_candidates"))
    excluded_candidates = _as_list(radar_packet.get("excluded_candidates"))[:10]
    evidence_recovery_actions = _as_list(snapshot_map.get("next_ticket_evidence_recovery_actions"))[:10]
    candidate_rows = _candidate_rows(candidates)
    provider_rows = _provider_coverage_rows(snapshot_map)
    freshness_state = _candidate_freshness_state(snapshot_map)
    parity_rows_raw = _legacy_parity_rows(
        snapshot_map=snapshot_map,
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        evidence_recovery_actions=evidence_recovery_actions,
    )
    output_contract_rows = _legacy_output_contract_rows(
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
    )
    provider_signal_rows = _deep_scan_required_signal_rows(provider_rows)
    parity_rows = _deep_scan_parity_rows(
        parity_rows=parity_rows_raw,
        output_contract_rows=output_contract_rows,
    )
    stage_rows = _deep_scan_stage_rows(
        candidate_rows=candidate_rows,
        provider_signal_rows=provider_signal_rows,
        parity_rows=parity_rows,
        freshness_state=freshness_state,
    )
    blocker_rows = _deep_scan_blocker_rows(
        stage_rows=stage_rows,
        provider_signal_rows=provider_signal_rows,
        parity_rows=parity_rows,
    )
    gap_count = sum(1 for row in parity_rows if row.get("gap_visible"))
    ready_signal_count = sum(1 for row in provider_signal_rows if row.get("ready_for_deep_scan"))
    return {
        "schema_version": "candidate_radar_deep_scan_plan.v1",
        "status": "deep_scan_plan_ready",
        "task_type": "run_candidate_radar_deep_scan_plan",
        "created_at": now,
        "requested_scan_mode": "deep_scan",
        "requested_depth": _safe_text(payload_safe.get("scan_depth") or "legacy_parity_first", limit=40),
        "deep_scan_done": False,
        "deep_scan_validation_done": False,
        "fast_path_ready": bool(candidate_rows),
        "legacy_feature_loss_guard_ready": gap_count == 0,
        "page_render_starts_deep_scan": False,
        "cache_get_starts_deep_scan": False,
        "provider_refresh_executed": False,
        "candidate_scoring_executed": False,
        "candidate_packet_written_by_plan": False,
        "worker_task_required": True,
        "worker_task_consumption_plan_ready": True,
        "stage_rows": stage_rows,
        "parity_rows": parity_rows,
        "required_signal_rows": provider_signal_rows,
        "blocker_rows": blocker_rows,
        "candidate_row_count": len(candidate_rows),
        "required_signal_group_count": len(provider_signal_rows),
        "ready_signal_group_count": ready_signal_count,
        "provider_gap_count": len(provider_signal_rows) - ready_signal_count,
        "legacy_feature_gap_count": gap_count,
        "blocking_issue_count": sum(1 for row in blocker_rows if row.get("blocks_deep_scan")),
        "research_only": True,
        "candidate_is_not_buy_instruction": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "warning": "Deep-scan plan records readiness and feature-loss gaps; it does not execute a deep scan, refresh providers, call DeepSeek, or produce trade instructions.",
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
    deep_scan_plan: Mapping[str, Any] | None = None,
    previous_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw_snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    radar_packet = _as_dict(snapshot_map.get("radar_packet") or snapshot_map.get("command_center_radar_packet"))
    candidates = _as_list(snapshot_map.get("next_ticket_candidates")) or _as_list(radar_packet.get("top_candidates"))
    candidate_input_count = max(_raw_candidate_input_count(raw_snapshot), len(candidates))
    excluded_candidates = _as_list(radar_packet.get("excluded_candidates"))[:10]
    evidence_recovery_actions = _as_list(snapshot_map.get("next_ticket_evidence_recovery_actions"))[:10]
    candidate_rows = _candidate_rows(candidates)
    candidate_display_truncated_count = max(0, candidate_input_count - len(candidate_rows))
    counts = _candidate_counts(candidate_rows)
    parity_inventory = _legacy_parity_inventory(
        snapshot_map=snapshot_map,
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        evidence_recovery_actions=evidence_recovery_actions,
    )
    legacy_parity_rows = _legacy_parity_rows(
        snapshot_map=snapshot_map,
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        evidence_recovery_actions=evidence_recovery_actions,
    )
    legacy_output_contract_rows = _legacy_output_contract_rows(
        radar_packet=radar_packet,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
    )
    legacy_parity_acceptance_receipt, legacy_parity_acceptance_rows = _legacy_parity_acceptance_receipt(
        parity_inventory=parity_inventory,
        parity_rows=legacy_parity_rows,
        output_contract_rows=legacy_output_contract_rows,
    )
    coverage = _scan_coverage(
        snapshot_available=bool(snapshot),
        snapshot_map=snapshot_map,
        candidate_rows=candidate_rows,
        excluded_candidates=excluded_candidates,
        scan_mode=scan_mode,
        local_pool_audit=local_pool_audit,
        local_pool_skipped_rows=local_pool_skipped_rows,
        candidate_input_count=candidate_input_count,
        candidate_display_truncated_count=candidate_display_truncated_count,
    )
    counts["legacy_parity_gap_count"] = parity_inventory["gap_or_future_count"]
    counts["legacy_parity_mapped_count"] = parity_inventory["mapped_or_partial_count"]
    counts["legacy_output_mapped_count"] = parity_inventory["output_contract_mapped_count"]
    counts["legacy_parity_acceptance_row_count"] = legacy_parity_acceptance_receipt["receipt_row_count"]
    counts["legacy_parity_acceptance_production_blocker_count"] = legacy_parity_acceptance_receipt[
        "production_blocker_count"
    ]
    counts["legacy_parity_acceptance_ready_count"] = legacy_parity_acceptance_receipt["production_ready_count"]
    if local_pool_audit:
        counts["local_pool_input_candidate_count"] = local_pool_audit.get("input_candidate_count")
        counts["local_pool_normalized_candidate_count"] = local_pool_audit.get("normalized_candidate_count")
        counts["local_pool_duplicate_candidate_count"] = local_pool_audit.get("duplicate_candidate_count")
    counts["provider_blocked_group_count"] = coverage["coverage_detail_summary"]["provider_blocked_group_count"]
    counts["stale_input_group_count"] = coverage["coverage_detail_summary"]["stale_input_group_count"]
    counts["missing_provider_data_group_count"] = coverage["coverage_detail_summary"]["missing_provider_data_group_count"]
    counts["degraded_mode_active_count"] = coverage["coverage_detail_summary"]["degraded_mode_active_count"]
    counts["universe_size"] = coverage["coverage_detail_summary"]["universe_size"]
    counts["candidate_input_count"] = candidate_input_count
    counts["candidate_display_limit"] = FAST_SCAN_DISPLAY_CANDIDATE_LIMIT
    counts["candidate_display_truncated_count"] = candidate_display_truncated_count
    plan = dict(full_pool_scan_plan or _as_dict(snapshot_map.get("full_pool_scan_plan")))
    deep_plan = dict(deep_scan_plan or _as_dict(snapshot_map.get("deep_scan_plan")))
    full_pool_local_execution_receipt, full_pool_local_execution_rows = _full_pool_local_execution_receipt(
        scan_mode=scan_mode,
        local_pool_audit=local_pool_audit or {},
        candidate_rows=candidate_rows,
        full_pool_scan_plan=plan,
        coverage=coverage,
    )
    counts["full_pool_local_execution_row_count"] = full_pool_local_execution_receipt["row_count"]
    counts["full_pool_local_execution_candidate_count"] = full_pool_local_execution_receipt["normalized_candidate_count"]
    counts["full_pool_local_execution_production_blocker_count"] = full_pool_local_execution_receipt[
        "production_blocker_count"
    ]
    full_pool_blocker_rows = _as_list(plan.get("blocker_rows"))
    deep_scan_blocker_rows = _as_list(deep_plan.get("blocker_rows"))
    scan_execution_summary = _scan_execution_summary(
        mode=mode,
        cache_source=cache_source,
        scan_mode=scan_mode,
        request_params_safe=request_params_safe or {},
        coverage=coverage,
        candidate_rows=candidate_rows,
        local_pool_audit=local_pool_audit or {},
        full_pool_scan_plan=plan,
        deep_scan_plan=deep_plan,
    )
    scan_acceptance_rows = _scan_acceptance_rows(
        scan_mode=scan_mode,
        coverage=coverage,
        candidate_rows=candidate_rows,
        local_pool_audit=local_pool_audit or {},
        full_pool_scan_plan=plan,
        deep_scan_plan=deep_plan,
    )
    fast_scan_runtime_budget_contract = _fast_scan_runtime_budget_contract(
        scan_mode=scan_mode,
        coverage=coverage,
        local_pool_audit=local_pool_audit or {},
        candidate_rows=candidate_rows,
    )
    (
        candidate_browser_qa_runbook_contract,
        candidate_browser_qa_runbook_rows,
        candidate_browser_qa_matrix_rows,
    ) = _candidate_browser_qa_runbook_contract()
    candidate_browser_qa_evidence_summary, candidate_browser_qa_evidence_rows = _candidate_browser_qa_evidence_summary()
    candidate_browser_qa_review_contract = _candidate_browser_qa_review_contract(
        candidate_browser_qa_evidence_summary,
        candidate_browser_qa_evidence_rows,
    )
    counts["fast_scan_runtime_budget_row_count"] = fast_scan_runtime_budget_contract["row_count"]
    counts["candidate_browser_qa_runbook_row_count"] = candidate_browser_qa_runbook_contract["row_count"]
    counts["candidate_browser_qa_matrix_count"] = candidate_browser_qa_runbook_contract["qa_matrix_count"]
    counts["candidate_browser_qa_blocking_phase_count"] = candidate_browser_qa_runbook_contract["blocking_phase_count"]
    counts["candidate_browser_qa_evidence_report_count"] = candidate_browser_qa_evidence_summary["candidate_report_count"]
    counts["candidate_browser_qa_evidence_row_count"] = candidate_browser_qa_evidence_summary["row_count"]
    counts["candidate_browser_qa_evidence_review_required_count"] = candidate_browser_qa_evidence_summary[
        "review_required_count"
    ]
    counts["candidate_browser_qa_visual_evidence_passed"] = candidate_browser_qa_evidence_summary[
        "candidate_visual_qa_evidence_passed"
    ]
    counts["candidate_browser_qa_performance_evidence_passed"] = candidate_browser_qa_evidence_summary[
        "candidate_browser_performance_evidence_passed"
    ]
    counts["candidate_browser_qa_review_blocking_count"] = candidate_browser_qa_review_contract["blocking_review_count"]
    counts["candidate_browser_qa_review_ready"] = candidate_browser_qa_review_contract["local_browser_qa_review_ready"]
    fast_scan_readiness_rows = _fast_scan_readiness_rows(
        mode=mode,
        scan_mode=scan_mode,
        cache_source=cache_source,
        coverage=coverage,
        scan_execution_summary=scan_execution_summary,
        scan_acceptance_rows=scan_acceptance_rows,
        parity_inventory=parity_inventory,
        full_pool_scan_plan=plan,
        deep_scan_plan=deep_plan,
        local_pool_audit=local_pool_audit or {},
        candidate_rows=candidate_rows,
        runtime_budget_contract=fast_scan_runtime_budget_contract,
    )
    fast_scan_readiness_audit = _fast_scan_readiness_audit(fast_scan_readiness_rows)
    result_delta_clarity_contract = _result_delta_clarity_contract(
        scan_mode=scan_mode,
        candidate_rows=candidate_rows,
        counts=counts,
        coverage=coverage,
        scan_execution_summary=scan_execution_summary,
        scan_acceptance_rows=scan_acceptance_rows,
        runtime_budget_contract=fast_scan_runtime_budget_contract,
        local_pool_audit=local_pool_audit or {},
        full_pool_scan_plan=plan,
        deep_scan_plan=deep_plan,
        previous_packet=previous_packet,
    )
    candidate_priority_explanation_contract = _candidate_priority_explanation_contract(
        candidate_rows,
        scan_mode=scan_mode,
        coverage=coverage,
    )
    if plan:
        counts["full_pool_plan_blocking_issue_count"] = plan.get("blocking_issue_count")
        counts["full_pool_plan_ready_signal_group_count"] = plan.get("ready_signal_group_count")
        counts["full_pool_plan_provider_gap_count"] = plan.get("provider_gap_count")
    if deep_plan:
        counts["deep_scan_plan_blocking_issue_count"] = deep_plan.get("blocking_issue_count")
        counts["deep_scan_plan_ready_signal_group_count"] = deep_plan.get("ready_signal_group_count")
        counts["deep_scan_plan_provider_gap_count"] = deep_plan.get("provider_gap_count")
        counts["deep_scan_plan_legacy_feature_gap_count"] = deep_plan.get("legacy_feature_gap_count")
    counts["fast_scan_readiness_blocker_count"] = fast_scan_readiness_audit["blocking_criterion_count"]
    counts["fast_scan_readiness_soft_blocker_count"] = fast_scan_readiness_audit["soft_blocker_count"]
    counts["fast_scan_readiness_row_count"] = fast_scan_readiness_audit["row_count"]
    counts["result_delta_clarity_visible_gap_count"] = result_delta_clarity_contract["visible_gap_count"]
    counts["result_delta_clarity_pending_count"] = result_delta_clarity_contract["production_pending_count"]
    counts["result_delta_clarity_row_count"] = result_delta_clarity_contract["row_count"]
    counts["result_delta_previous_candidate_count"] = result_delta_clarity_contract["previous_candidate_count"]
    counts["result_delta_added_count"] = result_delta_clarity_contract["candidate_added_count"]
    counts["result_delta_removed_count"] = result_delta_clarity_contract["candidate_removed_count"]
    counts["result_delta_rank_changed_count"] = result_delta_clarity_contract["candidate_rank_changed_count"]
    counts["result_delta_score_changed_count"] = result_delta_clarity_contract["candidate_score_changed_count"]
    counts["priority_explanation_row_count"] = candidate_priority_explanation_contract["row_count"]
    counts["priority_explanation_gap_count"] = candidate_priority_explanation_contract["explanation_gap_count"]
    counts["priority_explanation_data_gap_visible_count"] = candidate_priority_explanation_contract["data_gap_visible_count"]
    counts["priority_explanation_missing_score_count"] = candidate_priority_explanation_contract["missing_score_count"]

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
        "scan_execution_summary": scan_execution_summary,
        "scan_acceptance_rows": scan_acceptance_rows,
        "fast_scan_runtime_budget_contract": fast_scan_runtime_budget_contract,
        "fast_scan_runtime_budget_rows": fast_scan_runtime_budget_contract["rows"],
        "candidate_browser_qa_runbook_contract": candidate_browser_qa_runbook_contract,
        "candidate_browser_qa_runbook_rows": candidate_browser_qa_runbook_rows,
        "candidate_browser_qa_matrix_rows": candidate_browser_qa_matrix_rows,
        "candidate_browser_qa_evidence_summary": candidate_browser_qa_evidence_summary,
        "candidate_browser_qa_evidence_rows": candidate_browser_qa_evidence_rows,
        "candidate_browser_qa_review_contract": candidate_browser_qa_review_contract,
        "candidate_browser_qa_review_rows": candidate_browser_qa_review_contract["rows"],
        "fast_scan_readiness_audit": fast_scan_readiness_audit,
        "fast_scan_readiness_rows": fast_scan_readiness_rows,
        "result_delta_clarity_contract": result_delta_clarity_contract,
        "result_delta_clarity_rows": result_delta_clarity_contract["rows"],
        "previous_cache_diff_rows": result_delta_clarity_contract["previous_cache_diff_rows"],
        "candidate_priority_explanation_contract": candidate_priority_explanation_contract,
        "candidate_priority_explanation_rows": candidate_priority_explanation_contract["rows"],
        "provider_coverage_rows": coverage["provider_coverage_rows"],
        "degraded_mode_rows": coverage["degraded_mode_rows"],
        "local_candidate_pool_audit": dict(local_pool_audit or _as_dict(snapshot_map.get("local_candidate_pool_audit"))),
        "local_candidate_pool_skipped_rows": list(local_pool_skipped_rows or _as_list(snapshot_map.get("local_candidate_pool_skipped_rows"))),
        "legacy_signal_group_rows": coverage["legacy_signal_group_rows"],
        "legacy_parity_inventory": parity_inventory,
        "legacy_parity_rows": legacy_parity_rows,
        "legacy_output_contract_rows": legacy_output_contract_rows,
        "legacy_parity_acceptance_receipt": legacy_parity_acceptance_receipt,
        "legacy_parity_acceptance_rows": legacy_parity_acceptance_rows,
        "scan_mode_status_rows": [dict(row) for row in SCAN_MODE_STATUS_ROWS],
        "full_pool_scan_plan": plan,
        "full_pool_local_execution_receipt": full_pool_local_execution_receipt,
        "full_pool_local_execution_rows": full_pool_local_execution_rows,
        "full_pool_plan_stage_rows": _as_list(plan.get("stage_rows")),
        "full_pool_plan_filter_rows": _as_list(plan.get("filter_rows")),
        "full_pool_required_signal_rows": _as_list(plan.get("required_signal_rows")),
        "full_pool_blocker_rows": full_pool_blocker_rows,
        "deep_scan_plan": deep_plan,
        "deep_scan_stage_rows": _as_list(deep_plan.get("stage_rows")),
        "deep_scan_parity_rows": _as_list(deep_plan.get("parity_rows")),
        "deep_scan_required_signal_rows": _as_list(deep_plan.get("required_signal_rows")),
        "deep_scan_blocker_rows": deep_scan_blocker_rows,
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
            "full_pool_local_execution_is_button_gated": scan_mode == "full_pool_local_scan",
            "full_pool_local_execution_is_not_provider_backed_acceptance": True,
            "full_pool_local_execution_does_not_refresh_provider": True,
            "deep_scan_plan_is_not_deep_scan": True,
            "deep_scan_plan_writes_no_new_candidates": True,
            "deep_scan_plan_provider_refresh_executed": False,
            "deep_scan_plan_deepseek_called": False,
            "deep_scan_feature_loss_gaps_visible": True,
            "does_not_run_backtest": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_holdings": True,
            "candidate_is_not_buy_instruction": True,
            "post_task_required_for_scan": True,
            "fast_scan_runtime_budget_contract_visible": True,
            "candidate_browser_qa_runbook_contract_is_local": True,
            "candidate_browser_qa_runbook_ready": candidate_browser_qa_runbook_contract["local_runbook_ready"],
            "candidate_browser_qa_is_not_visual_qa": True,
            "candidate_browser_qa_is_not_production_replacement": True,
            "candidate_browser_qa_evidence_reads_local_artifact_only": True,
            "candidate_browser_qa_evidence_does_not_open_browser": True,
            "candidate_browser_qa_evidence_does_not_write_artifacts": True,
            "candidate_browser_qa_evidence_is_not_production_replacement": True,
            "candidate_browser_qa_evidence_found": candidate_browser_qa_evidence_summary["local_browser_qa_evidence_found"],
            "candidate_browser_qa_review_is_button_gated": True,
            "candidate_browser_qa_review_does_not_open_browser": True,
            "candidate_browser_qa_review_is_not_production_replacement": True,
            "candidate_rows_capped_for_ui": bool(candidate_display_truncated_count),
            "large_universe_requires_worker": coverage["coverage_detail_summary"]["large_universe_requires_worker"],
            "fast_scan_readiness_audit_is_local": True,
            "fast_scan_readiness_is_not_full_replacement": True,
            "result_delta_clarity_contract_is_local": True,
            "result_delta_clarity_previous_cache_diff_done": bool(result_delta_clarity_contract["previous_cache_diff_done"]),
            "result_delta_clarity_previous_cache_diff_is_local": bool(result_delta_clarity_contract["previous_cache_diff_done"]),
            "result_delta_clarity_is_not_previous_cache_diff": not bool(result_delta_clarity_contract["previous_cache_diff_done"]),
            "result_delta_clarity_is_not_browser_visual_qa": True,
            "candidate_priority_explanation_contract_is_local": True,
            "candidate_priority_explanation_uses_existing_rank_only": True,
            "candidate_priority_explanation_uses_existing_score_only": True,
            "candidate_priority_explanation_is_not_trade_signal": True,
            "legacy_parity_acceptance_receipt_is_local": True,
            "legacy_parity_acceptance_is_not_production_replacement": True,
            "legacy_parity_acceptance_requires_provider_worker_browser_evidence": True,
        },
        "call_ledger": [
            _candidate_call_ledger_row(
                api="local_candidate_radar_cache",
                source_snapshot="command_center_latest.json",
                row_count=len(candidate_rows),
                call_status="cache_read" if snapshot else "cache_missing",
                request_params_safe=request_params_safe or {},
            )
        ]
        + legacy_parity_acceptance_receipt["call_ledger"],
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
    packet = _attach_quick_scan_receipt_contract(packet)
    packet = _attach_no_feature_loss_acceptance_contract(packet)
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
    candidate_browser_qa_evidence_summary, candidate_browser_qa_evidence_rows = _candidate_browser_qa_evidence_summary()
    persisted_review = _as_dict(packet.get("candidate_browser_qa_review_contract"))
    explicit_review_done = persisted_review.get("explicit_review_task_done") is True
    candidate_browser_qa_review_contract = _candidate_browser_qa_review_contract(
        candidate_browser_qa_evidence_summary,
        candidate_browser_qa_evidence_rows,
        explicit_review=explicit_review_done,
        task_id=str(persisted_review.get("task_id") or packet.get("task_id") or "") if explicit_review_done else None,
        reviewed_at=str(persisted_review.get("reviewed_at") or packet.get("candidate_browser_qa_review_completed_at") or "")
        if explicit_review_done
        else None,
    )
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
    if not isinstance(view.get("legacy_parity_acceptance_receipt"), dict):
        parity_receipt, parity_acceptance_rows = _legacy_parity_acceptance_receipt(
            parity_inventory=_as_dict(view.get("legacy_parity_inventory")),
            parity_rows=[row for row in _as_list(view.get("legacy_parity_rows")) if isinstance(row, dict)],
            output_contract_rows=[
                row for row in _as_list(view.get("legacy_output_contract_rows")) if isinstance(row, dict)
            ],
        )
        view["legacy_parity_acceptance_receipt"] = parity_receipt
        view["legacy_parity_acceptance_rows"] = parity_acceptance_rows
        view["call_ledger"] = view["call_ledger"] + parity_receipt["call_ledger"]
    if not isinstance(view.get("full_pool_local_execution_receipt"), dict):
        full_pool_local_receipt, full_pool_local_rows = _full_pool_local_execution_receipt(
            scan_mode=persisted_scan_mode,
            local_pool_audit=_as_dict(view.get("local_candidate_pool_audit")),
            candidate_rows=[row for row in _as_list(view.get("candidate_rows")) if isinstance(row, dict)],
            full_pool_scan_plan=_as_dict(view.get("full_pool_scan_plan")),
            coverage={
                "freshness_state": _as_dict(view.get("freshness_state")),
                "coverage_detail_summary": _as_dict(view.get("coverage_detail_summary")),
            },
        )
        view["full_pool_local_execution_receipt"] = full_pool_local_receipt
        view["full_pool_local_execution_rows"] = full_pool_local_rows
    view["candidate_browser_qa_evidence_summary"] = candidate_browser_qa_evidence_summary
    view["candidate_browser_qa_evidence_rows"] = candidate_browser_qa_evidence_rows
    view["candidate_browser_qa_review_contract"] = candidate_browser_qa_review_contract
    view["candidate_browser_qa_review_rows"] = candidate_browser_qa_review_contract["rows"]
    counts = _as_dict(view.get("counts"))
    counts["candidate_browser_qa_evidence_report_count"] = candidate_browser_qa_evidence_summary["candidate_report_count"]
    counts["candidate_browser_qa_evidence_row_count"] = candidate_browser_qa_evidence_summary["row_count"]
    counts["candidate_browser_qa_evidence_review_required_count"] = candidate_browser_qa_evidence_summary[
        "review_required_count"
    ]
    counts["candidate_browser_qa_visual_evidence_passed"] = candidate_browser_qa_evidence_summary[
        "candidate_visual_qa_evidence_passed"
    ]
    counts["candidate_browser_qa_performance_evidence_passed"] = candidate_browser_qa_evidence_summary[
        "candidate_browser_performance_evidence_passed"
    ]
    counts["candidate_browser_qa_review_blocking_count"] = candidate_browser_qa_review_contract["blocking_review_count"]
    counts["candidate_browser_qa_review_ready"] = candidate_browser_qa_review_contract["local_browser_qa_review_ready"]
    parity_receipt = _as_dict(view.get("legacy_parity_acceptance_receipt"))
    counts["legacy_parity_acceptance_row_count"] = parity_receipt.get("receipt_row_count")
    counts["legacy_parity_acceptance_production_blocker_count"] = parity_receipt.get("production_blocker_count")
    counts["legacy_parity_acceptance_ready_count"] = parity_receipt.get("production_ready_count")
    full_pool_local_receipt = _as_dict(view.get("full_pool_local_execution_receipt"))
    counts["full_pool_local_execution_row_count"] = full_pool_local_receipt.get("row_count")
    counts["full_pool_local_execution_candidate_count"] = full_pool_local_receipt.get("normalized_candidate_count")
    counts["full_pool_local_execution_production_blocker_count"] = full_pool_local_receipt.get(
        "production_blocker_count"
    )
    view["counts"] = counts
    policy = _as_dict(view.get("policy"))
    policy["candidate_browser_qa_evidence_reads_local_artifact_only"] = True
    policy["candidate_browser_qa_evidence_does_not_open_browser"] = True
    policy["candidate_browser_qa_evidence_does_not_write_artifacts"] = True
    policy["candidate_browser_qa_evidence_is_not_production_replacement"] = True
    policy["candidate_browser_qa_evidence_found"] = candidate_browser_qa_evidence_summary["local_browser_qa_evidence_found"]
    policy["candidate_browser_qa_review_is_button_gated"] = True
    policy["candidate_browser_qa_review_does_not_open_browser"] = True
    policy["candidate_browser_qa_review_is_not_production_replacement"] = True
    policy["legacy_parity_acceptance_receipt_is_local"] = True
    policy["legacy_parity_acceptance_is_not_production_replacement"] = True
    policy["legacy_parity_acceptance_requires_provider_worker_browser_evidence"] = True
    policy["full_pool_local_execution_is_button_gated"] = persisted_scan_mode == "full_pool_local_scan"
    policy["full_pool_local_execution_is_not_provider_backed_acceptance"] = True
    policy["full_pool_local_execution_does_not_refresh_provider"] = True
    view["policy"] = policy
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
    view = _attach_quick_scan_receipt_contract(view)
    view = _attach_no_feature_loss_acceptance_contract(view)
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
    return _build_candidate_radar_packet(
        snapshot,
        mode="cache_only",
        cache_source="snapshot",
        scan_mode="cache_only",
        previous_packet=persisted,
    )


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
    previous_packet = _read_persisted_packet()
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
        previous_packet=previous_packet,
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
    previous_packet = _read_persisted_packet()
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
        previous_packet=previous_packet,
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


def run_candidate_full_pool_local_scan_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_full_pool_local_scan",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_full_pool_local_scan_queued",
        warnings=[
            "下一票雷达 full-pool local scan 只消费本地 universe/payload/cache；不会调用 Tushare、DeepSeek 或 GitHub。",
            "本地 full-pool 执行收据不是 provider-backed 全市场生产验收，不生成买入指令，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="reading_local_full_pool_universe",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    snapshot = packet_service.load_snapshot_cache()
    previous_packet = _read_persisted_packet()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    scan_snapshot, local_pool_audit, local_pool_skipped_rows = _snapshot_with_local_candidate_pool(
        snapshot_map,
        payload_safe,
        "full_pool_local_scan",
    )
    now = _now_iso()
    plan = _build_full_pool_scan_plan(scan_snapshot, payload_safe, now=now)
    request_params_safe = {
        "scan_mode": "full_pool_local_scan",
        "local_execution_only": True,
        "input_candidate_count": local_pool_audit.get("input_candidate_count"),
        "normalized_candidate_count": local_pool_audit.get("normalized_candidate_count"),
        "truncated_candidate_count": local_pool_audit.get("truncated_candidate_count"),
        "external_sources_allowed": False,
        "provider_backed_acceptance_done": False,
        "production_full_pool_scan_done": False,
    }
    packet = _build_candidate_radar_packet(
        scan_snapshot,
        mode="full_pool_local_scan",
        cache_source="full_pool_local_scan_task",
        scan_mode="full_pool_local_scan",
        request_params_safe=request_params_safe,
        local_pool_audit=local_pool_audit,
        local_pool_skipped_rows=local_pool_skipped_rows,
        full_pool_scan_plan=plan,
        previous_packet=previous_packet,
    )
    receipt = _as_dict(packet.get("full_pool_local_execution_receipt"))
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_full_pool_local_scan",
        source_snapshot=str(local_pool_audit.get("input_source") or "local_universe_payload_or_cache"),
        row_count=len(_as_list(packet.get("candidate_rows"))),
        call_status=receipt.get("status") or "full_pool_local_execution_ready_production_pending",
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["full_pool_local_scan_completed_at"] = now
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 full-pool local scan 已消费本地 universe 并写入执行收据；不刷新 provider、不调用模型、不代表 provider-backed 全市场验收。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "full-pool local scan" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "full_pool_local_scan_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_full_pool_local_scan_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_full_pool_local_scan_storage_write_failed",
            error_message_safe="candidate_radar_full_pool_local_scan_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_full_pool_local_scan_failed_no_external_call",
        ) or task

    final_step = "candidate_radar_full_pool_local_scan_completed"
    final_warning = "candidate_radar_full_pool_local_scan_completed_no_external_call"
    if not _as_list(packet.get("candidate_rows")):
        final_step = "candidate_radar_full_pool_local_scan_empty_universe"
        final_warning = "candidate_radar_full_pool_local_scan_empty_universe_no_external_call"
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=final_step,
        call_ledger=[ledger],
        warning=final_warning,
    ) or task


def run_candidate_deep_scan_plan_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_deep_scan_plan",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_deep_scan_plan_queued",
        warnings=[
            "下一票雷达 deep-scan plan 只生成本地功能覆盖和准备度清单；不会扫描全市场、不会调用 Tushare、DeepSeek 或 GitHub。",
            "deep-scan plan 用来防止迁移降能；它不是 deep_scan 完成，不生成买入候选，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.25,
        current_step="reading_local_candidate_radar_deep_scan_inputs",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    snapshot = packet_service.load_snapshot_cache()
    previous_packet = _read_persisted_packet()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    now = _now_iso()
    plan = _build_deep_scan_plan(snapshot_map, payload_safe, now=now)
    request_params_safe = {
        "scan_mode": "deep_scan",
        "plan_only": True,
        "scan_depth": plan.get("requested_depth"),
        "required_signal_group_count": plan.get("required_signal_group_count"),
        "legacy_feature_gap_count": plan.get("legacy_feature_gap_count"),
        "blocking_issue_count": plan.get("blocking_issue_count"),
        "external_sources_allowed": False,
        "deep_scan_done": False,
    }
    packet = _build_candidate_radar_packet(
        snapshot_map,
        mode="deep_scan_plan",
        cache_source="deep_scan_plan_task",
        scan_mode="deep_scan_plan",
        request_params_safe=request_params_safe,
        deep_scan_plan=plan,
        previous_packet=previous_packet,
    )
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_deep_scan_plan",
        source_snapshot="command_center_latest.json",
        row_count=len(plan.get("blocker_rows") or []),
        call_status="deep_scan_plan_ready",
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["deep_scan_plan_completed_at"] = now
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "下一票雷达 deep-scan plan 只记录功能覆盖、provider、freshness、worker 和交易隔离准备度；不执行 deep_scan、不刷新 provider、不调用 DeepSeek、不生成买入候选。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "deep-scan plan" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "deep_scan_plan_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_deep_scan_plan_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_deep_scan_plan_storage_write_failed",
            error_message_safe="candidate_radar_deep_scan_plan_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_deep_scan_plan_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_deep_scan_plan_ready",
        call_ledger=[ledger],
        warning="candidate_radar_deep_scan_plan_ready_no_external_call",
    ) or task


def run_candidate_browser_qa_review_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_candidate_radar_browser_qa_review",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="candidate_radar_browser_qa_review_queued",
        warnings=[
            "候选雷达 browser QA review 只读取本地 ignored runner 报告；不会打开浏览器、不会启动服务、不会调用 Tushare/DeepSeek/GitHub。",
            "review 结果只代表本地 artifact 审查状态；不代表 full-pool/deep-scan/provider-backed 验收或 production radar replacement。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_candidate_browser_qa_evidence",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_candidate_radar_cache()
    evidence_summary = _as_dict(packet.get("candidate_browser_qa_evidence_summary"))
    evidence_rows = [row for row in _as_list(packet.get("candidate_browser_qa_evidence_rows")) if isinstance(row, dict)]
    reviewed_at = _now_iso()
    review_contract = _candidate_browser_qa_review_contract(
        evidence_summary,
        evidence_rows,
        explicit_review=True,
        task_id=task["task_id"],
        reviewed_at=reviewed_at,
    )
    request_params_safe = {
        "review_scope": "candidate_route_browser_qa_local_artifact",
        "candidate_route": "#candidates",
        "external_sources_allowed": False,
        "opens_no_browser": True,
        "writes_no_artifacts": True,
        "production_radar_replacement_complete": False,
    }
    request_params_safe.update(
        {
            key: payload_safe.get(key)
            for key in ("review_note", "reviewer")
            if payload_safe.get(key) is not None
        }
    )
    ledger = _candidate_call_ledger_row(
        api="local_candidate_radar_browser_qa_review",
        source_snapshot=".stock_ming_3/motion_qa",
        row_count=len(review_contract.get("rows") or []),
        call_status=review_contract["status"],
        request_params_safe=request_params_safe,
    )
    packet["task_id"] = task["task_id"]
    packet["candidate_browser_qa_review_completed_at"] = reviewed_at
    packet["candidate_browser_qa_review_contract"] = review_contract
    packet["candidate_browser_qa_review_rows"] = review_contract["rows"]
    counts = _as_dict(packet.get("counts"))
    counts["candidate_browser_qa_review_blocking_count"] = review_contract["blocking_review_count"]
    counts["candidate_browser_qa_review_ready"] = review_contract["local_browser_qa_review_ready"]
    packet["counts"] = counts
    policy = _as_dict(packet.get("policy"))
    policy["candidate_browser_qa_review_is_button_gated"] = True
    policy["candidate_browser_qa_review_does_not_open_browser"] = True
    policy["candidate_browser_qa_review_is_not_production_replacement"] = True
    packet["policy"] = policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "候选雷达 browser QA review 只审查本地 ignored artifact；不打开浏览器、不提交截图、不调用 provider、不完成生产雷达替代。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "browser QA review" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "browser_qa_review_storage_write_failed"
        ledger["error_message_safe"] = "candidate_radar_browser_qa_review_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="candidate_radar_browser_qa_review_storage_write_failed",
            error_message_safe="candidate_radar_browser_qa_review_sqlite_write_failed",
            call_ledger=[ledger],
            warning="candidate_radar_browser_qa_review_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="candidate_radar_browser_qa_review_ready",
        call_ledger=[ledger],
        warning="candidate_radar_browser_qa_review_ready_no_external_call",
    ) or task
