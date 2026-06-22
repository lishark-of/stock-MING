from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import config
from server.services import packet_service
from storage.sqlite_meta import SQLiteMetaStore

from .task_service import create_task_record, list_task_statuses, update_task_status


PACKET_KEY = "command_center_3_legacy_bridge_cache"
SCHEMA_VERSION = "legacy_bridge_cache.v1"
STREAMLIT_ORDINARY_WORKFLOW_PARITY_REVIEW_PACKET_KEY = (
    "command_center_3_streamlit_ordinary_workflow_parity_review_packet"
)
STREAMLIT_FALLBACK_RETIREMENT_REVIEW_PACKET_KEY = (
    "command_center_3_streamlit_fallback_retirement_review_packet"
)
LEGACY_AUDIT_OBSERVATION_DRY_RUN_PACKET_KEY = "command_center_3_legacy_audit_observation_dry_run_packet"
STREAMLIT_ORDINARY_WORKFLOW_PARITY_REVIEW_TASK_TYPE = "run_streamlit_ordinary_workflow_parity_review"
STREAMLIT_FALLBACK_RETIREMENT_REVIEW_TASK_TYPE = "run_streamlit_fallback_retirement_review"
LEGACY_AUDIT_OBSERVATION_DRY_RUN_TASK_TYPE = "run_legacy_audit_observation_dry_run"
STREAMLIT_ORDINARY_WORKFLOW_PARITY_REVIEW_SCHEMA_VERSION = (
    "streamlit_ordinary_workflow_parity_review.v1"
)
STREAMLIT_FALLBACK_RETIREMENT_REVIEW_SCHEMA_VERSION = "streamlit_fallback_retirement_review.v1"
LEGACY_AUDIT_OBSERVATION_DRY_RUN_SCHEMA_VERSION = "legacy_audit_observation_dry_run.v1"
STREAMLIT_RETIREMENT_DURABLE_EVIDENCE_SCHEMA_VERSION = "streamlit_retirement_durable_evidence_recipe.v1"
ORDINARY_ENTRANCE_ACCEPTANCE_SCHEMA_VERSION = "ordinary_entrance_acceptance_audit.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_PY_PATH = PROJECT_ROOT / "app.py"
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
SENSITIVE_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password", "passwd", "credential", "authorization")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")
STREAMLIT_RETIREMENT_DURABLE_EVIDENCE_KEYS = (
    "route_inventory_primary_entry",
    "ordinary_workflow_replacement_parity",
    "candidate_radar_no_feature_loss_acceptance",
    "provider_backed_parity_acceptance",
    "browser_performance_visual_qa",
    "admin_debug_retention_decision",
    "fallback_retirement_change_review",
    "app_py_removal_or_retention_decision",
    "legacy_guardrail_regression_review",
    "production_promotion_approval",
)
STREAMLIT_RETIREMENT_DURABLE_EVIDENCE_LABELS = {
    "route_inventory_primary_entry": "route inventory and primary-entry evidence",
    "ordinary_workflow_replacement_parity": "ordinary workflow replacement parity",
    "candidate_radar_no_feature_loss_acceptance": "Candidate Radar no-feature-loss acceptance",
    "provider_backed_parity_acceptance": "provider-backed parity acceptance",
    "browser_performance_visual_qa": "browser, visual, and performance QA",
    "admin_debug_retention_decision": "admin/debug retention or replacement decision",
    "fallback_retirement_change_review": "fallback retirement change review",
    "app_py_removal_or_retention_decision": "app.py removal or retention decision",
    "legacy_guardrail_regression_review": "legacy guardrail regression review",
    "production_promotion_approval": "production promotion approval",
}


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
    if depth > 5:
        return "[truncated]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            _safe_text(key, limit=100): _safe_value(val, depth=depth + 1)
            for key, val in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_safe_value(item, depth=depth + 1) for item in value[:80]]
    if isinstance(value, tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:80]]
    return _safe_text(value)


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "legacy_bridge_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _rows(value: Any, *, source: str, text_key: str = "label") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        items = value.get("items") or value.get("lanes") or value.get("next_actions") or value.get("priority_items")
        if isinstance(items, list):
            return _rows(items, source=source, text_key=text_key)
        for key, val in value.items():
            if isinstance(val, Mapping):
                row = dict(val)
                row.setdefault("key", key)
                row.setdefault("source", source)
                rows.append(row)
            elif isinstance(val, list):
                rows.extend(_rows(val, source=f"{source}.{key}", text_key=text_key))
        return rows[:100]
    for idx, raw in enumerate(_as_list(value), start=1):
        if isinstance(raw, Mapping):
            row = dict(raw)
            row.setdefault("index", idx)
            row.setdefault("source", source)
            rows.append(row)
        elif raw is not None:
            rows.append({"index": idx, "source": source, text_key: _safe_text(raw)})
    return rows[:100]


def _checklist_counts(checklist: Mapping[str, Any], capability: Mapping[str, Any]) -> dict[str, int]:
    checklist_items = _rows(checklist.get("items"), source="legacy_packet_migration_checklist.items")
    done = sum(1 for item in checklist_items if str(item.get("status") or item.get("state") or item.get("tone") or "").lower() in {"done", "ready", "complete", "completed"} or "完成" in str(item.get("status_label") or item.get("label") or ""))
    pending = sum(1 for item in checklist_items if "pending" in str(item.get("status") or item.get("state") or "").lower() or "待" in str(item.get("status_label") or item.get("label") or ""))
    return {
        "checklist_done_count": int(capability.get("checklist_done_count", done)),
        "checklist_pending_count": int(capability.get("checklist_pending_count", pending)),
    }


def _streamlit_source_summary() -> dict[str, Any]:
    if not APP_PY_PATH.exists():
        return {
            "path": "app.py",
            "available": False,
            "legacy_mode_marker_present": False,
            "legacy_admin_notice_present": False,
            "primary_legacy_tabs_present": False,
            "ordinary_workflow_caption_present": False,
            "legacy_action_guard_present": False,
            "contains_secret": False,
        }
    try:
        source = APP_PY_PATH.read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "path": "app.py",
            "available": False,
            "error_message_safe": _safe_text(exc, limit=240),
            "legacy_mode_marker_present": False,
            "legacy_admin_notice_present": False,
            "primary_legacy_tabs_present": False,
            "ordinary_workflow_caption_present": False,
            "legacy_action_guard_present": False,
            "contains_secret": False,
        }
    return {
        "path": "app.py",
        "available": True,
        "legacy_mode_marker_present": "STREAMLIT_LEGACY_MODE_STATUS" in source and "legacy/admin/debug" in source,
        "legacy_admin_notice_present": "render_streamlit_legacy_admin_notice" in source,
        "primary_legacy_tabs_present": "primary_legacy_tabs" in source,
        "ordinary_workflow_caption_present": "普通主流程" in source,
        "legacy_action_guard_present": "guard_legacy_projection_action" in source,
        "contains_secret": False,
    }


def _primary_workflow_route_rows() -> list[dict[str, Any]]:
    return [
        {
            "workflow": "home_status",
            "react_route": "CommandCenterHome.tsx",
            "api": "GET /health + GET /api/packets",
            "coverage_status": "migrated_cache",
            "ordinary_flow_supported": True,
            "still_needs_streamlit_fallback": False,
        },
        {
            "workflow": "next_session_map",
            "react_route": "NextSessionMap.tsx",
            "api": "GET /api/next-session/cache + POST /api/next-session/generate",
            "coverage_status": "migrated_cache_task",
            "ordinary_flow_supported": True,
            "still_needs_streamlit_fallback": False,
        },
        {
            "workflow": "factor_quant_hub",
            "react_route": "FactorQuantHub.tsx",
            "api": "GET /api/factor-quant/cache + guarded POST tasks",
            "coverage_status": "migrated_research_only",
            "ordinary_flow_supported": True,
            "still_needs_streamlit_fallback": False,
        },
        {
            "workflow": "candidate_radar_quick_scan",
            "react_route": "CandidateRadar.tsx",
            "api": "GET /api/candidate-radar/cache + local scan/plan POST tasks",
            "coverage_status": "partial_migrated",
            "ordinary_flow_supported": True,
            "still_needs_streamlit_fallback": True,
            "fallback_reason": "full-pool/deep-scan execution and legacy parity are still readiness plans",
        },
        {
            "workflow": "market_and_evidence",
            "react_route": "MarketContext.tsx + AShareEvidenceRadar.tsx",
            "api": "GET /api/market/cache + GET /api/evidence/cache",
            "coverage_status": "migrated_cache",
            "ordinary_flow_supported": True,
            "still_needs_streamlit_fallback": False,
        },
        {
            "workflow": "risk_and_strategy_trace",
            "react_route": "RiskGuardrails.tsx + StrategyTrace.tsx + PositionContext.tsx",
            "api": "GET /api/risk/cache + GET /api/strategy/cache + GET /api/position/cache",
            "coverage_status": "migrated_cache",
            "ordinary_flow_supported": True,
            "still_needs_streamlit_fallback": False,
        },
        {
            "workflow": "data_health_recovery",
            "react_route": "DataHealthTimeline.tsx + RecoveryCenter.tsx + DataCapabilityConsole.tsx",
            "api": "GET cache APIs",
            "coverage_status": "migrated_cache",
            "ordinary_flow_supported": True,
            "still_needs_streamlit_fallback": False,
        },
        {
            "workflow": "legacy_admin_debug_tools",
            "react_route": "LegacyTools.tsx",
            "api": "GET /api/legacy/cache",
            "coverage_status": "fallback_retained",
            "ordinary_flow_supported": False,
            "still_needs_streamlit_fallback": True,
            "fallback_reason": "old debug/admin/fallback tools are intentionally retained until replacement workflows are proven",
        },
    ]


def _primary_workflow_exit_audit(
    *,
    policy: Mapping[str, Any],
    checklist_counts: Mapping[str, int],
    status: str,
    snapshot_available: bool,
) -> dict[str, Any]:
    source_summary = _streamlit_source_summary()
    route_rows = _primary_workflow_route_rows()
    migrated_count = sum(1 for row in route_rows if row.get("ordinary_flow_supported") and not row.get("still_needs_streamlit_fallback"))
    fallback_rows = [row for row in route_rows if row.get("still_needs_streamlit_fallback")]
    safety_rows = [
        {
            "criterion": "streamlit_marked_legacy_admin_debug",
            "status": "passed" if source_summary.get("legacy_mode_marker_present") and source_summary.get("legacy_admin_notice_present") else "blocked",
            "passed": bool(source_summary.get("legacy_mode_marker_present") and source_summary.get("legacy_admin_notice_present")),
            "evidence": "app.py contains legacy/admin/debug marker and notice renderer",
            "production_blocker": False,
        },
        {
            "criterion": "react_tauri_is_primary_entry",
            "status": "passed" if policy.get("react_tauri_is_primary_entry") and not policy.get("streamlit_is_official_primary_entry") else "blocked",
            "passed": bool(policy.get("react_tauri_is_primary_entry") and not policy.get("streamlit_is_official_primary_entry")),
            "evidence": str(policy.get("official_primary_entry") or ""),
            "production_blocker": False,
        },
        {
            "criterion": "legacy_cache_get_read_only",
            "status": "passed",
            "passed": True,
            "evidence": "GET /api/legacy/cache reads sanitized local snapshot only",
            "production_blocker": False,
        },
        {
            "criterion": "legacy_startup_does_not_create_tasks",
            "status": "passed" if policy.get("legacy_startup_task_creation") is False else "blocked",
            "passed": policy.get("legacy_startup_task_creation") is False,
            "evidence": "legacy_startup_task_creation=false",
            "production_blocker": False,
        },
        {
            "criterion": "legacy_startup_does_not_call_external_sources",
            "status": "passed" if policy.get("legacy_startup_external_calls") is False else "blocked",
            "passed": policy.get("legacy_startup_external_calls") is False,
            "evidence": "startup does not call Tushare, DeepSeek, GitHub, or trade APIs",
            "production_blocker": False,
        },
        {
            "criterion": "legacy_cannot_bypass_guardrails",
            "status": "passed" if policy.get("legacy_can_bypass_guardrails") is False and source_summary.get("legacy_action_guard_present") else "blocked",
            "passed": bool(policy.get("legacy_can_bypass_guardrails") is False and source_summary.get("legacy_action_guard_present")),
            "evidence": "legacy action guard marker is present in app.py",
            "production_blocker": False,
        },
        {
            "criterion": "ordinary_workflow_route_inventory_visible",
            "status": "passed" if route_rows else "blocked",
            "passed": bool(route_rows),
            "evidence": f"route_count={len(route_rows)}; migrated_without_fallback={migrated_count}",
            "production_blocker": False,
        },
    ]
    blocker_rows = [
        {
            "criterion": "ordinary_workflows_fully_migrated",
            "status": "blocked" if fallback_rows else "passed",
            "passed": not fallback_rows,
            "evidence": f"fallback_workflow_count={len(fallback_rows)}",
            "production_blocker": bool(fallback_rows),
        },
        {
            "criterion": "legacy_fallback_removal_ready",
            "status": "blocked",
            "passed": False,
            "evidence": "Streamlit fallback must remain until all ordinary workflows and admin/debug replacements are proven",
            "production_blocker": True,
        },
        {
            "criterion": "snapshot_migration_cache_available",
            "status": "passed" if snapshot_available else "blocked",
            "passed": bool(snapshot_available),
            "evidence": f"legacy_cache_status={status}",
            "production_blocker": not snapshot_available,
        },
        {
            "criterion": "legacy_migration_checklist_clear",
            "status": "passed" if int(checklist_counts.get("checklist_pending_count") or 0) == 0 else "blocked",
            "passed": int(checklist_counts.get("checklist_pending_count") or 0) == 0,
            "evidence": f"pending={int(checklist_counts.get('checklist_pending_count') or 0)}; done={int(checklist_counts.get('checklist_done_count') or 0)}",
            "production_blocker": int(checklist_counts.get("checklist_pending_count") or 0) > 0,
        },
    ]
    rows = safety_rows + blocker_rows
    safety_passed = all(bool(row.get("passed")) for row in safety_rows)
    blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    exit_complete = safety_passed and not blockers
    return {
        "schema_version": "streamlit_primary_workflow_exit_audit.v1",
        "status": "ordinary_workflow_exit_complete" if exit_complete else "ordinary_workflow_exit_partial_fallback_required",
        "scope": "local_legacy_policy_and_route_inventory_not_streamlit_execution",
        "ordinary_workflow_exit_complete": exit_complete,
        "streamlit_fallback_retained": True,
        "streamlit_fallback_removal_ready": exit_complete,
        "react_tauri_primary_entry": bool(policy.get("react_tauri_is_primary_entry")),
        "streamlit_is_official_primary_entry": bool(policy.get("streamlit_is_official_primary_entry")),
        "ordinary_workflow_route_count": len(route_rows),
        "ordinary_workflow_migrated_without_fallback_count": migrated_count,
        "ordinary_workflow_still_needs_fallback_count": len(fallback_rows),
        "checklist_pending_count": int(checklist_counts.get("checklist_pending_count") or 0),
        "checklist_done_count": int(checklist_counts.get("checklist_done_count") or 0),
        "source_summary": source_summary,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "rows": rows,
        "route_rows": route_rows,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_open_streamlit": True,
        "does_not_run_legacy_tools": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "note": "This audit inventories retirement readiness only; it does not open Streamlit, run legacy tools, call providers/models/GitHub, or remove fallbacks.",
    }


def _streamlit_fallback_dependency_contract(route_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _dependency_row(row: Mapping[str, Any]) -> dict[str, Any]:
        workflow = str(row.get("workflow") or "unknown_workflow")
        ordinary_flow_supported = bool(row.get("ordinary_flow_supported"))
        fallback_required = bool(row.get("still_needs_streamlit_fallback"))
        if fallback_required and ordinary_flow_supported:
            dependency_class = "ordinary_flow_partial_fallback_required"
            removal_criteria = "Prove Command Center 3 route parity, data freshness, task pipeline execution, and legacy feature coverage without opening Streamlit."
        elif fallback_required:
            dependency_class = "legacy_admin_debug_retained"
            removal_criteria = "Keep as legacy/admin/debug until replacement admin/debug workflows are proven or explicitly retired."
        else:
            dependency_class = "command_center_3_primary_ready"
            removal_criteria = "Keep route coverage and safety boundaries under regression test."
        return {
            "workflow": workflow,
            "react_route": row.get("react_route"),
            "api": row.get("api"),
            "coverage_status": row.get("coverage_status"),
            "ordinary_flow_supported": ordinary_flow_supported,
            "still_needs_streamlit_fallback": fallback_required,
            "dependency_class": dependency_class,
            "blocks_ordinary_primary_exit": bool(fallback_required and ordinary_flow_supported),
            "blocks_full_streamlit_removal": fallback_required,
            "fallback_reason": row.get("fallback_reason") or "",
            "removal_criteria": removal_criteria,
            "replacement_must_preserve_features": True,
            "cache_api_can_resolve": False,
            "operator_action_required": fallback_required,
            "external_calls_triggered": False,
            "does_not_open_streamlit": True,
            "does_not_run_legacy_tools": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    rows = [_dependency_row(row) for row in route_rows]
    ordinary_fallback_rows = [row for row in rows if row["blocks_ordinary_primary_exit"]]
    full_removal_blockers = [row for row in rows if row["blocks_full_streamlit_removal"]]
    retained_admin_rows = [row for row in rows if row["dependency_class"] == "legacy_admin_debug_retained"]
    primary_ready_rows = [row for row in rows if row["dependency_class"] == "command_center_3_primary_ready"]
    return {
        "schema_version": "streamlit_fallback_dependency_contract.v1",
        "status": "streamlit_fallback_dependencies_visible_retirement_pending"
        if full_removal_blockers
        else "streamlit_fallback_dependencies_clear",
        "scope": "local_route_dependency_contract_not_streamlit_execution",
        "route_count": len(rows),
        "command_center_primary_ready_count": len(primary_ready_rows),
        "ordinary_fallback_dependency_count": len(ordinary_fallback_rows),
        "admin_debug_fallback_retained_count": len(retained_admin_rows),
        "full_streamlit_removal_blocker_count": len(full_removal_blockers),
        "ordinary_primary_exit_ready": len(ordinary_fallback_rows) == 0,
        "full_streamlit_removal_ready": len(full_removal_blockers) == 0,
        "streamlit_fallback_retained": bool(full_removal_blockers),
        "ordinary_blocking_workflows": [str(row["workflow"]) for row in ordinary_fallback_rows],
        "full_removal_blocking_workflows": [str(row["workflow"]) for row in full_removal_blockers],
        "feature_parity_required_before_removal": True,
        "no_feature_cut_allowed": True,
        "cache_api_can_resolve": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_open_streamlit": True,
        "does_not_run_legacy_tools": True,
        "does_not_create_tasks": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "note": "This contract makes remaining Streamlit fallback dependencies explicit. It is not a fallback removal, does not open Streamlit, and does not execute legacy tools.",
    }


def _ordinary_entrance_acceptance_audit() -> dict[str, Any]:
    legacy_module_rows = [
        {
            "legacy_module": "today_focus_home",
            "classification": "REDESIGN",
            "preserve_capability": "today_focus / risk_summary / cache_source / next_click",
            "legacy_ux_or_bug_path_not_migrated": "multi_button_rerun_home / engineering_tables_before_decision",
            "target_surface": "Daily Command Center summary",
            "ordinary_flow_entry_allowed": True,
        },
        {
            "legacy_module": "single_stock_quant_room",
            "classification": "REDESIGN",
            "preserve_capability": "searched_symbol_projection / factor_support_pressure / next_session_preview",
            "legacy_ux_or_bug_path_not_migrated": "deep_tab_radio_navigation / blocking_projection / position_context_conflict",
            "target_surface": "Stock Quant Projection",
            "ordinary_flow_entry_allowed": True,
        },
        {
            "legacy_module": "candidate_radar",
            "classification": "REDESIGN",
            "preserve_capability": "top_watch_excluded_candidates / score_reasoning / scan_scope",
            "legacy_ux_or_bug_path_not_migrated": "candidate_reads_like_buy_instruction / unclear_full_pool_deep_scan_boundary",
            "target_surface": "Candidate Radar",
            "ordinary_flow_entry_allowed": True,
        },
        {
            "legacy_module": "next_session_map",
            "classification": "REDESIGN",
            "preserve_capability": "operation_zones / triggers / invalidation_conditions / chart_data_trust",
            "legacy_ux_or_bug_path_not_migrated": "streamlit_visual_clone / chart_receipt_as_production_replacement",
            "target_surface": "Stock Quant Projection result panel",
            "ordinary_flow_entry_allowed": True,
        },
        {
            "legacy_module": "factor_quant_hub",
            "classification": "REDESIGN",
            "preserve_capability": "support_pressure_missing_conflict / factor_lineage / light_research_metrics",
            "legacy_ux_or_bug_path_not_migrated": "engineering_contract_tables_as_primary_user_flow / small_sample_as_production_ic",
            "target_surface": "Stock Quant Projection summary plus Developer/Audit detail",
            "ordinary_flow_entry_allowed": True,
        },
        {
            "legacy_module": "hard_risk_scan",
            "classification": "REDESIGN",
            "preserve_capability": "hard_risk / announcements / pledge_reduction_funding_gaps",
            "legacy_ux_or_bug_path_not_migrated": "missing_data_written_as_no_risk / model_text_overwrites_fact",
            "target_surface": "Daily Command Center and Stock Quant Projection risk block",
            "ordinary_flow_entry_allowed": True,
        },
        {
            "legacy_module": "discipline_backtest_lab",
            "classification": "LEGACY-DEBUG",
            "preserve_capability": "review / rule_lab / backtest_params / historical_discipline_reference",
            "legacy_ux_or_bug_path_not_migrated": "deep_forms / synchronous_backtest / cloud_write_mixed_with_trade_advice",
            "target_surface": "Legacy/Admin/Debug until redesigned as explicit backtest lab",
            "ordinary_flow_entry_allowed": False,
        },
        {
            "legacy_module": "provider_health_console",
            "classification": "LEGACY-DEBUG",
            "preserve_capability": "provider_permission / cache_health / config_status",
            "legacy_ux_or_bug_path_not_migrated": "provider_health_table_dominates_ordinary_path / page_entry_auto_probe",
            "target_surface": "Settings / Config Health / Audit",
            "ordinary_flow_entry_allowed": False,
        },
        {
            "legacy_module": "external_memory_and_method_labs",
            "classification": "LEGACY-DEBUG",
            "preserve_capability": "research_memory / method_library / special_topic_clues",
            "legacy_ux_or_bug_path_not_migrated": "rag_document_ingestion_mixed_with_ordinary_action / unclear_data_lineage",
            "target_surface": "Advanced research / Developer / External Brain",
            "ordinary_flow_entry_allowed": False,
        },
        {
            "legacy_module": "legacy_ai_strategy_advisor",
            "classification": "RETIRE",
            "preserve_capability": "research_tone_for_explaining_existing_evidence",
            "legacy_ux_or_bug_path_not_migrated": "direct_trade_advice / cross_market_fact_source_unclear / model_text_as_action",
            "target_surface": "Governed DeepSeek explain summary only",
            "ordinary_flow_entry_allowed": False,
        },
    ]
    classification_counts = {
        classification: sum(1 for row in legacy_module_rows if row["classification"] == classification)
        for classification in ("KEEP", "REDESIGN", "LEGACY-DEBUG", "RETIRE")
    }
    direct_evidence_pending_label = "seed_only_direct_evidence_pending_before_KEEP"
    for row in legacy_module_rows:
        row["direct_ux_bug_evidence_source"] = direct_evidence_pending_label
        row["ordinary_entrance_placement"] = row["target_surface"]
        row["frozen_legacy_path"] = row["legacy_ux_or_bug_path_not_migrated"]
        row["keep_upgrade_blocked_without_direct_evidence"] = True
    direct_evidence_pending_count = sum(
        1 for row in legacy_module_rows if row["direct_ux_bug_evidence_source"] == direct_evidence_pending_label
    )
    keep_upgrade_blocked_count = sum(
        1 for row in legacy_module_rows if row["keep_upgrade_blocked_without_direct_evidence"] is True
    )
    rows = [
        {
            "entrance": "daily_command_center",
            "display_name": "今日作战台 / Daily Command Center",
            "classification": "REDESIGN",
            "legacy_capability_preserved": [
                "today_focus",
                "risk_summary",
                "watchlist_context",
                "data_source_health",
                "last_good_cache",
            ],
            "required_visible_state": [
                "next_click",
                "tushare_cache_deepseek_or_pending_source",
                "missing_evidence",
                "blocked_or_degraded_state",
                "last_good_cache",
                "research_only_boundary",
            ],
            "legacy_ux_or_bug_path_not_migrated": [
                "streamlit_multi_button_rerun_home",
                "engineering_tables_dominate_decision_surface",
                "provider_health_auto_probe_from_ordinary_page",
                "ai_text_that_reads_like_trade_instruction",
            ],
            "next_safe_migration_slice": (
                "compress ordinary home into summary plus next action; move provider/config/audit detail "
                "to Settings or Audit"
            ),
            "engineering_details_destination": "Settings / Developer / Audit",
            "ordinary_page_should_show_summary_only": True,
        },
        {
            "entrance": "stock_quant_projection",
            "display_name": "股票量化推演 / Stock Quant Projection",
            "classification": "REDESIGN",
            "legacy_capability_preserved": [
                "searched_symbol_research",
                "factor_support_pressure_neutral_missing",
                "next_session_map",
                "optional_deepseek_explanation",
                "risk_budget_context",
            ],
            "required_visible_state": [
                "generate_3_0_quant_projection_button",
                "cache_provider_model_pending_layers",
                "missing_task_or_evidence",
                "last_successful_result",
                "no_action_no_trade_boundary",
            ],
            "legacy_ux_or_bug_path_not_migrated": [
                "deep_tab_or_radio_navigation",
                "sync_blocking_projection",
                "conflicting_position_context",
                "deepseek_overwrites_numeric_price_factor_or_strategy_action",
            ],
            "next_safe_migration_slice": (
                "build searched-symbol to local task/cache replay path first; real provider/model execution "
                "requires later acceptance"
            ),
            "engineering_details_destination": "Settings / Developer / Audit",
            "ordinary_page_should_show_summary_only": True,
        },
        {
            "entrance": "candidate_radar",
            "display_name": "下一票雷达 / Candidate Radar",
            "classification": "REDESIGN",
            "legacy_capability_preserved": [
                "top_watch_excluded_candidates",
                "score_reasoning",
                "scan_scope",
                "candidate_pool_source",
                "no_feature_loss_comparison",
            ],
            "required_visible_state": [
                "candidate_is_not_buy_instruction",
                "scan_scope_and_source",
                "provider_cache_pending_state",
                "missing_full_pool_deep_scan_browser_ci_evidence",
                "last_radar_cache",
            ],
            "legacy_ux_or_bug_path_not_migrated": [
                "legacy_radar_candidate_reads_like_recommendation",
                "unclear_full_pool_or_deep_scan_boundary",
                "timeout_prone_sync_scan",
                "retire_legacy_fallback_before_replacement_evidence",
            ],
            "next_safe_migration_slice": (
                "restore usable quick scan and no-feature-loss surface before worker/provider/browser/"
                "legacy-retirement evidence"
            ),
            "engineering_details_destination": "Settings / Developer / Audit",
            "ordinary_page_should_show_summary_only": True,
        },
    ]
    commit_questions = [
        "what_user_capability_was_preserved",
        "what_legacy_ux_problem_was_removed",
        "what_legacy_bug_or_patchwork_path_was_not_migrated",
        "what_became_simpler_for_nontechnical_user",
        "which_real_blocker_was_reduced",
    ]
    return {
        "schema_version": ORDINARY_ENTRANCE_ACCEPTANCE_SCHEMA_VERSION,
        "status": "ordinary_entrance_acceptance_map_ready_audit_pending",
        "scope": "local_ordinary_entrance_acceptance_audit_no_streamlit_execution",
        "row_count": len(rows),
        "ordinary_entrance_acceptance_complete": False,
        "requires_legacy_bug_ux_audit_before_major_migration": True,
        "ordinary_user_entrance_count": len(rows),
        "legacy_bug_ux_module_row_count": len(legacy_module_rows),
        "legacy_bug_ux_keep_count": classification_counts["KEEP"],
        "legacy_bug_ux_redesign_count": classification_counts["REDESIGN"],
        "legacy_bug_ux_legacy_debug_count": classification_counts["LEGACY-DEBUG"],
        "legacy_bug_ux_retire_count": classification_counts["RETIRE"],
        "legacy_bug_ux_direct_evidence_pending_count": direct_evidence_pending_count,
        "legacy_bug_ux_keep_upgrade_blocked_count": keep_upgrade_blocked_count,
        "legacy_modules_enter_ordinary_flow_without_audit": False,
        "engineering_details_moved_to_settings_developer_audit": True,
        "commit_questions": commit_questions,
        "rows": rows,
        "legacy_bug_ux_module_rows": legacy_module_rows,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_open_streamlit": True,
        "does_not_run_legacy_tools": True,
        "does_not_create_tasks": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_ordinary_entrance_acceptance_audit",
                "source_snapshot": "static_legacy_bug_ux_audit_map",
                "row_count": len(rows),
                "call_status": "local_static_read",
                "local_fetched_at": _now_iso(),
                "external": False,
            }
        ],
        "note": (
            "This maps the three ordinary Command Center 3 entrances for Legacy Bug / UX Audit. "
            "It is not production acceptance, does not open Streamlit, and does not create tasks."
        ),
    }


def _legacy_audit_first_round_intake_status() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    contract = config.get_command_center_legacy_audit_classification_contract()
    required_fields = list(contract.get("intake_required_fields") or [])
    safe_sources = list(contract.get("intake_safe_attachment_sources") or [])
    forbidden_sources = list(contract.get("intake_forbidden_attachment_sources") or [])
    allowed_statuses = list(contract.get("intake_allowed_statuses") or [])
    focus_workflows = list(contract.get("first_round_focus_workflows") or [])
    rows = [
        {
            "workflow_group": workflow,
            "required_fields": list(required_fields),
            "allowed_initial_status": "direct_evidence_intake_pending",
            "safe_attachment_sources": list(safe_sources),
            "forbidden_attachment_sources": list(forbidden_sources),
            "keep_promotion_allowed_this_round": False,
            "ordinary_entry_promotion_allowed_this_round": False,
            "legacy_admin_debug_surface_only": True,
            "next_action": "capture_safe_user_observation_lineage_and_freeze_decision",
        }
        for workflow in focus_workflows
    ]
    summary = {
        "schema_version": "legacy_audit_first_round_intake_status.v1",
        "status": "legacy_audit_first_round_intake_visible_admin_debug_only",
        "config_source": "config.get_command_center_legacy_audit_classification_contract",
        "first_round_intake_rule": contract.get("first_round_intake_rule"),
        "required_fields": required_fields,
        "safe_attachment_sources": safe_sources,
        "forbidden_attachment_sources": forbidden_sources,
        "allowed_statuses": allowed_statuses,
        "row_count": len(rows),
        "focus_workflow_count": len(focus_workflows),
        "keep_promotion_allowed_this_round": False,
        "ordinary_entry_promotion_allowed_this_round": False,
        "legacy_admin_debug_surface_only": True,
        "production_evidence_rule": contract.get("production_evidence_rule"),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_open_streamlit": True,
        "does_not_run_legacy_tools": True,
        "does_not_create_tasks": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_legacy_audit_first_round_intake",
                "source_snapshot": "config_legacy_audit_classification_contract",
                "row_count": len(rows),
                "call_status": "local_static_read",
                "local_fetched_at": _now_iso(),
                "external": False,
            }
        ],
    }
    return summary, rows


def _sanitize_legacy_audit_observation_payload(payload: Any) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    return {
        "schema_version": LEGACY_AUDIT_OBSERVATION_DRY_RUN_SCHEMA_VERSION,
        "workflow_group": _safe_text(raw.get("workflow_group"), limit=160),
        "user_observation": _safe_text(raw.get("user_observation"), limit=1000),
        "legacy_ux_bug_or_patchwork": _safe_text(raw.get("legacy_ux_bug_or_patchwork"), limit=1000),
        "data_lineage_observation": _safe_text(raw.get("data_lineage_observation"), limit=1000),
        "replacement_user_path": _safe_text(raw.get("replacement_user_path"), limit=400),
        "frozen_legacy_path": _safe_text(raw.get("frozen_legacy_path"), limit=400),
        "evidence_attachment": _safe_text(raw.get("evidence_attachment"), limit=400),
        "evidence_attachment_type": _safe_text(raw.get("evidence_attachment_type"), limit=120),
        "requested_status": _safe_text(raw.get("requested_status"), limit=120),
        "keep_promotion_decision": _safe_text(
            raw.get("keep_promotion_decision") or "no_keep_promotion_this_round",
            limit=160,
        ),
        "requested_by": _safe_text(raw.get("requested_by") or raw.get("operator") or "local_reviewer", limit=120),
        "contains_secret": False,
    }


def _build_legacy_audit_observation_receipt(payload_safe: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    contract = config.get_command_center_legacy_audit_classification_contract()
    required_fields = list(contract.get("intake_required_fields") or [])
    safe_sources = list(contract.get("intake_safe_attachment_sources") or [])
    allowed_statuses = list(contract.get("intake_allowed_statuses") or [])
    focus_workflows = list(contract.get("first_round_focus_workflows") or [])
    requested_status = str(payload_safe.get("requested_status") or "direct_evidence_intake_pending")
    requested_keep = requested_status == "KEEP" or str(payload_safe.get("keep_promotion_decision") or "") == "KEEP"
    proposed_status = requested_status if requested_status in allowed_statuses else "direct_evidence_intake_pending"
    required_present = {
        field: bool(str(payload_safe.get(field) or "").strip())
        for field in required_fields
    }
    missing_fields = [field for field, present in required_present.items() if not present]
    workflow_group = str(payload_safe.get("workflow_group") or "")
    workflow_known = workflow_group in focus_workflows
    attachment_type = str(payload_safe.get("evidence_attachment_type") or "")
    attachment_safe = attachment_type in safe_sources
    local_record_ready = not missing_fields and workflow_known and attachment_safe and not requested_keep
    if requested_keep:
        status = "legacy_audit_observation_dry_run_blocked_keep_promotion_not_allowed"
    elif missing_fields:
        status = "legacy_audit_observation_dry_run_blocked_missing_required_fields"
    elif not workflow_known:
        status = "legacy_audit_observation_dry_run_blocked_unknown_workflow"
    elif not attachment_safe:
        status = "legacy_audit_observation_dry_run_blocked_unsafe_attachment_source"
    else:
        status = "legacy_audit_observation_dry_run_recorded_no_keep_promotion"
    rows = [
        {
            "schema_version": LEGACY_AUDIT_OBSERVATION_DRY_RUN_SCHEMA_VERSION,
            "criterion": "required_intake_fields_present",
            "status": "passed" if not missing_fields else "blocked_missing_required_fields",
            "passed": not missing_fields,
            "missing_fields": missing_fields,
            "external_calls_triggered": False,
            "does_not_open_streamlit": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "schema_version": LEGACY_AUDIT_OBSERVATION_DRY_RUN_SCHEMA_VERSION,
            "criterion": "workflow_group_in_first_round_scope",
            "status": "passed" if workflow_known else "blocked_unknown_workflow",
            "passed": workflow_known,
            "workflow_group": workflow_group,
            "external_calls_triggered": False,
            "does_not_open_streamlit": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "schema_version": LEGACY_AUDIT_OBSERVATION_DRY_RUN_SCHEMA_VERSION,
            "criterion": "safe_evidence_attachment_source",
            "status": "passed" if attachment_safe else "blocked_unsafe_attachment_source",
            "passed": attachment_safe,
            "evidence_attachment_type": attachment_type,
            "safe_attachment_sources": safe_sources,
            "external_calls_triggered": False,
            "does_not_open_streamlit": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "schema_version": LEGACY_AUDIT_OBSERVATION_DRY_RUN_SCHEMA_VERSION,
            "criterion": "no_keep_or_ordinary_promotion_this_round",
            "status": "blocked_keep_promotion_not_allowed" if requested_keep else "passed_no_keep_promotion",
            "passed": not requested_keep,
            "requested_status": requested_status,
            "proposed_status": proposed_status,
            "keep_promotion_allowed_this_round": False,
            "ordinary_entry_promotion_allowed_this_round": False,
            "external_calls_triggered": False,
            "does_not_open_streamlit": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
    ]
    receipt = {
        "schema_version": LEGACY_AUDIT_OBSERVATION_DRY_RUN_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_local_legacy_audit_observation_dry_run_no_streamlit_execution",
        "workflow_group": workflow_group,
        "workflow_group_known": workflow_known,
        "allowed_statuses": allowed_statuses,
        "proposed_status": proposed_status,
        "requested_status": requested_status,
        "required_fields": required_fields,
        "missing_required_fields": missing_fields,
        "safe_attachment_sources": safe_sources,
        "evidence_attachment_type": attachment_type,
        "evidence_attachment_safe": attachment_safe,
        "direct_user_evidence_recorded": local_record_ready,
        "direct_evidence_ready_for_keep_review": False,
        "keep_request_rejected": requested_keep,
        "keep_promotion_allowed_this_round": False,
        "ordinary_entry_promotion_allowed_this_round": False,
        "streamlit_fallback_retirement_allowed": False,
        "production_evidence": False,
        "observation_dry_run_only": True,
        "opens_streamlit": False,
        "runs_legacy_tools": False,
        "creates_followup_tasks": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_open_streamlit": True,
        "does_not_run_legacy_tools": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "row_count": len(rows),
    }
    return receipt, rows


def _legacy_audit_observation_call_ledger(
    *,
    payload_safe: Mapping[str, Any],
    receipt: Mapping[str, Any],
    now: str,
) -> dict[str, Any]:
    return {
        "api": "local_legacy_audit_observation_dry_run",
        "endpoint": "POST /api/legacy/audit-observation-dry-run",
        "request_params_safe": {
            "workflow_group": payload_safe.get("workflow_group"),
            "requested_by": payload_safe.get("requested_by"),
            "requested_status": receipt.get("requested_status"),
            "proposed_status": receipt.get("proposed_status"),
            "direct_user_evidence_recorded": receipt.get("direct_user_evidence_recorded"),
            "keep_promotion_allowed_this_round": False,
            "ordinary_entry_promotion_allowed_this_round": False,
        },
        "row_count": int(receipt.get("row_count") or 0),
        "local_fetched_at": now,
        "call_status": receipt.get("status"),
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_open_streamlit": True,
        "does_not_run_legacy_tools": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _streamlit_retirement_readiness_receipt(
    *,
    primary_workflow_exit_audit: Mapping[str, Any],
    fallback_dependency_contract: Mapping[str, Any],
) -> dict[str, Any]:
    exit_blocker_count = int(primary_workflow_exit_audit.get("blocker_count") or 0)
    ordinary_fallback_count = int(
        primary_workflow_exit_audit.get("ordinary_workflow_still_needs_fallback_count") or 0
    )
    full_removal_blocker_count = int(fallback_dependency_contract.get("full_streamlit_removal_blocker_count") or 0)
    ordinary_blocking_workflows = [
        str(item) for item in _as_list(fallback_dependency_contract.get("ordinary_blocking_workflows"))
    ]
    full_removal_blocking_workflows = [
        str(item) for item in _as_list(fallback_dependency_contract.get("full_removal_blocking_workflows"))
    ]
    local_receipt_ready = (
        primary_workflow_exit_audit.get("schema_version") == "streamlit_primary_workflow_exit_audit.v1"
        and fallback_dependency_contract.get("schema_version") == "streamlit_fallback_dependency_contract.v1"
        and primary_workflow_exit_audit.get("scope")
        == "local_legacy_policy_and_route_inventory_not_streamlit_execution"
        and fallback_dependency_contract.get("scope") == "local_route_dependency_contract_not_streamlit_execution"
        and primary_workflow_exit_audit.get("does_not_open_streamlit") is True
        and primary_workflow_exit_audit.get("does_not_run_legacy_tools") is True
        and fallback_dependency_contract.get("does_not_open_streamlit") is True
        and fallback_dependency_contract.get("does_not_run_legacy_tools") is True
        and fallback_dependency_contract.get("no_feature_cut_allowed") is True
    )
    ordinary_exit_ready = bool(
        local_receipt_ready
        and primary_workflow_exit_audit.get("ordinary_workflow_exit_complete") is True
        and fallback_dependency_contract.get("ordinary_primary_exit_ready") is True
        and ordinary_fallback_count == 0
    )
    full_retirement_ready = bool(
        ordinary_exit_ready
        and fallback_dependency_contract.get("full_streamlit_removal_ready") is True
        and full_removal_blocker_count == 0
    )

    def _row(criterion: str, status: str, detail: str, required_evidence: str) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": status == "passed",
            "retirement_blocker": status != "passed",
            "detail": detail,
            "required_evidence": required_evidence,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_open_streamlit": True,
            "does_not_run_legacy_tools": True,
            "does_not_create_tasks": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    rows = [
        _row(
            "local_exit_contracts_visible",
            "passed" if local_receipt_ready else "blocked",
            "Legacy cache exposes primary workflow exit audit and fallback dependency contract.",
            "GET /api/legacy/cache includes exit audit, fallback contract, rows, policy, and call ledger.",
        ),
        _row(
            "react_tauri_primary_entry_declared",
            "passed" if primary_workflow_exit_audit.get("react_tauri_primary_entry") is True else "blocked",
            "React/Vite/Tauri + FastAPI is the official primary entry; Streamlit is not.",
            "Primary entry policy stays visible in legacy cache and LegacyTools page.",
        ),
        _row(
            "ordinary_fallback_dependencies_visible",
            "blocked" if ordinary_fallback_count > 0 else "passed",
            f"{ordinary_fallback_count} ordinary workflow fallback dependency item(s) remain.",
            "All ordinary workflows have Command Center 3 parity and no longer need Streamlit fallback.",
        ),
        _row(
            "candidate_radar_retirement_dependency_visible",
            "blocked" if "candidate_radar_quick_scan" in ordinary_blocking_workflows else "passed",
            f"ordinary_blocking_workflows={ordinary_blocking_workflows}",
            "Candidate Radar full-pool/deep-scan/provider/browser acceptance clears legacy fallback dependency.",
        ),
        _row(
            "legacy_admin_debug_retained_until_replacement",
            "blocked" if "legacy_admin_debug_tools" in full_removal_blocking_workflows else "passed",
            f"full_removal_blocking_workflows={full_removal_blocking_workflows}",
            "Admin/debug/fallback workflows are replaced or explicitly retired without feature cuts.",
        ),
        _row(
            "no_feature_cut_boundary",
            "passed" if fallback_dependency_contract.get("no_feature_cut_allowed") is True else "blocked",
            "Streamlit cannot be removed by cutting ordinary or admin/debug capabilities.",
            "Every removed fallback has replacement parity or an explicit retirement decision.",
        ),
        _row(
            "cache_render_does_not_open_streamlit",
            "passed",
            "Receipt is generated from local cache metadata only; render does not open Streamlit.",
            "No Streamlit process, legacy tool execution, task creation, provider/model/GitHub call, or trade occurs on cache/render.",
        ),
        _row(
            "ordinary_exit_completion_boundary",
            "blocked" if not ordinary_exit_ready else "passed",
            f"ordinary_exit_ready={ordinary_exit_ready}; exit_blocker_count={exit_blocker_count}",
            "ordinary_workflow_exit_complete=true only after route coverage and fallback dependencies are clear.",
        ),
        _row(
            "full_streamlit_retirement_boundary",
            "blocked" if not full_retirement_ready else "passed",
            f"full_retirement_ready={full_retirement_ready}; full_removal_blocker_count={full_removal_blocker_count}",
            "full_streamlit_removal_ready=true only after ordinary and admin/debug fallback blockers are cleared.",
        ),
        _row(
            "trade_action_isolation_boundary",
            "passed",
            "Retirement receipt cannot execute trades, mutate holdings, or modify strategy action.",
            "Legacy retirement work remains separate from broker/order execution and strategy action mutation.",
        ),
    ]
    blocked_rows = [row for row in rows if row["status"] != "passed"]
    status = (
        "streamlit_retirement_receipt_ready_full_retirement_review"
        if full_retirement_ready
        else "streamlit_retirement_receipt_ready_ordinary_exit_review"
        if ordinary_exit_ready
        else "streamlit_retirement_receipt_ready_fallback_blocked"
        if local_receipt_ready
        else "streamlit_retirement_receipt_blocked_local_contract"
    )
    return {
        "schema_version": "streamlit_retirement_readiness_receipt.v1",
        "status": status,
        "scope": "local_streamlit_retirement_readiness_receipt_no_streamlit_execution",
        "ltg": "LTG-10",
        "local_receipt_ready": bool(local_receipt_ready),
        "ready_for_ordinary_primary_exit_review": ordinary_exit_ready,
        "ready_for_full_streamlit_retirement_review": full_retirement_ready,
        "ordinary_workflow_exit_complete": False,
        "streamlit_fallback_removal_ready": False,
        "full_streamlit_removal_ready": False,
        "streamlit_fallback_retained": True,
        "allowed_next_step": "explicit_replacement_parity_review_then_streamlit_fallback_retirement_review",
        "not_allowed_next_steps": [
            "GET /api/legacy/cache opens Streamlit",
            "GET /api/legacy/cache runs legacy tools",
            "GET /api/legacy/cache creates tasks",
            "page render retires Streamlit fallback",
            "mark ordinary_workflow_exit_complete without zero ordinary fallback dependencies",
            "mark full_streamlit_removal_ready while admin/debug fallback remains",
            "delete app.py before replacement parity or explicit retirement decision",
            "treat local receipt as Streamlit retirement completion",
        ],
        "missing_evidence_items": [
            "ordinary_route_parity_acceptance",
            "candidate_radar_full_pool_deep_scan_acceptance",
            "provider_backed_radar_parity_acceptance",
            "browser_performance_visual_acceptance",
            "admin_debug_replacement_or_retirement_decision",
            "fallback_removal_change_review",
        ],
        "exit_blocker_count": exit_blocker_count,
        "ordinary_fallback_dependency_count": ordinary_fallback_count,
        "full_streamlit_removal_blocker_count": full_removal_blocker_count,
        "ordinary_blocking_workflows": ordinary_blocking_workflows,
        "full_removal_blocking_workflows": full_removal_blocking_workflows,
        "streamlit_opened_by_receipt": False,
        "legacy_tools_run_by_receipt": False,
        "tasks_created_by_receipt": False,
        "fallback_removed_by_receipt": False,
        "app_py_deleted_by_receipt": False,
        "provider_model_task_dispatched_by_receipt": False,
        "receipt_external_calls_triggered": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_open_streamlit": True,
        "does_not_run_legacy_tools": True,
        "does_not_create_tasks": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "criterion_count": len(rows),
        "blocking_criterion_count": len(blocked_rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_streamlit_retirement_readiness_receipt",
                "source": "legacy bridge local exit and fallback contracts",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_retirement_readiness_receipt",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_open_streamlit": True,
                "does_not_run_legacy_tools": True,
                "does_not_create_tasks": True,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This receipt selects the next safe LTG-10 review step only. It does not open Streamlit, run legacy tools, create tasks, remove fallback, delete app.py, call providers/models/GitHub, execute trades, or mark retirement complete.",
    }


def _streamlit_retirement_durable_evidence_recipe_row(
    evidence_key: str,
    *,
    current_status: str,
    target_status: str,
    local_prerequisite_visible: bool,
    direct_evidence_required: bool,
    missing_evidence: list[str],
) -> dict[str, Any]:
    production_blocker = direct_evidence_required or current_status.startswith("pending")
    return {
        "evidence_key": evidence_key,
        "evidence_label": STREAMLIT_RETIREMENT_DURABLE_EVIDENCE_LABELS[evidence_key],
        "scope": "streamlit_retirement_durable_evidence_recipe",
        "current_status": current_status,
        "target_status": target_status,
        "local_prerequisite_visible": bool(local_prerequisite_visible),
        "direct_evidence_required": bool(direct_evidence_required),
        "production_blocker": bool(production_blocker),
        "missing_evidence": missing_evidence,
        "ordinary_workflow_exit_complete": False,
        "streamlit_fallback_removal_ready": False,
        "full_streamlit_removal_ready": False,
        "streamlit_fallback_retained": True,
        "legacy_fallback_required": True,
        "replacement_parity_complete": False,
        "candidate_radar_parity_complete": False,
        "provider_backed_parity_done": False,
        "browser_performance_qa_done": False,
        "admin_debug_decision_done": False,
        "fallback_removed_by_recipe": False,
        "app_py_deleted_by_recipe": False,
        "streamlit_opened_by_recipe": False,
        "legacy_tools_run_by_recipe": False,
        "tasks_created_by_recipe": False,
        "provider_model_task_dispatched_by_recipe": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
    }


def _streamlit_retirement_durable_evidence_recipe(
    *,
    primary_workflow_exit_audit: Mapping[str, Any],
    fallback_dependency_contract: Mapping[str, Any],
    retirement_readiness_receipt: Mapping[str, Any],
    fallback_retirement_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    route_inventory_visible = bool(primary_workflow_exit_audit.get("ordinary_workflow_route_count"))
    local_receipt_ready = retirement_readiness_receipt.get("local_receipt_ready") is True
    no_feature_cut_visible = fallback_dependency_contract.get("no_feature_cut_allowed") is True
    local_recipe_ready = bool(route_inventory_visible and local_receipt_ready and no_feature_cut_visible)
    ordinary_blocking_workflows = [
        str(item) for item in _as_list(fallback_dependency_contract.get("ordinary_blocking_workflows"))
    ]
    full_removal_blocking_workflows = [
        str(item) for item in _as_list(fallback_dependency_contract.get("full_removal_blocking_workflows"))
    ]
    fallback_review_map = fallback_retirement_review if isinstance(fallback_retirement_review, Mapping) else {}
    fallback_retirement_review_done = bool(
        fallback_review_map.get("direct_evidence_verified") is True
        and fallback_review_map.get("explicit_fallback_retirement_review_done") is True
        and fallback_review_map.get("fallback_removed_by_review") is False
        and fallback_review_map.get("streamlit_opened_by_review") is False
        and fallback_review_map.get("legacy_tools_run_by_review") is False
        and fallback_review_map.get("external_calls_triggered") is False
    )
    rows = [
        _streamlit_retirement_durable_evidence_recipe_row(
            "route_inventory_primary_entry",
            current_status="local_verified",
            target_status="keep_primary_entry_contract_under_push_gate",
            local_prerequisite_visible=route_inventory_visible,
            direct_evidence_required=False,
            missing_evidence=[],
        ),
        _streamlit_retirement_durable_evidence_recipe_row(
            "ordinary_workflow_replacement_parity",
            current_status="pending_direct_parity_evidence",
            target_status="all_ordinary_workflows_have_command_center_3_parity",
            local_prerequisite_visible=route_inventory_visible,
            direct_evidence_required=True,
            missing_evidence=[
                "same-workflow React/Tauri parity review",
                "ordinary workflow fallback dependency count reaches zero",
                "migration checklist has no pending ordinary-workflow item",
            ],
        ),
        _streamlit_retirement_durable_evidence_recipe_row(
            "candidate_radar_no_feature_loss_acceptance",
            current_status="pending_provider_worker_browser_evidence",
            target_status="Candidate Radar quick/full/deep scan replaces legacy path without feature loss",
            local_prerequisite_visible="candidate_radar_quick_scan" in ordinary_blocking_workflows,
            direct_evidence_required=True,
            missing_evidence=[
                "legacy signal-group parity matrix",
                "full-pool/deep-scan provider or accepted fixture evidence",
                "worker/background execution evidence without UI stall",
                "browser QA evidence for radar scan and result drilldown",
            ],
        ),
        _streamlit_retirement_durable_evidence_recipe_row(
            "provider_backed_parity_acceptance",
            current_status="pending_provider_backed_acceptance",
            target_status="provider-backed parity proves migrated routes preserve accepted data behavior",
            local_prerequisite_visible=True,
            direct_evidence_required=True,
            missing_evidence=[
                "explicit POST task provider acceptance",
                "safe call ledger with row counts and data dates",
                "permission/empty-window/error states distinguished",
            ],
        ),
        _streamlit_retirement_durable_evidence_recipe_row(
            "browser_performance_visual_qa",
            current_status="pending_browser_performance_evidence",
            target_status="React/Tauri primary flow passes visual, reduced-motion, and performance QA",
            local_prerequisite_visible=True,
            direct_evidence_required=True,
            missing_evidence=[
                "browser visual QA screenshots or report",
                "performance trace proving no ordinary-flow stall",
                "reduced-motion and clarity review",
            ],
        ),
        _streamlit_retirement_durable_evidence_recipe_row(
            "admin_debug_retention_decision",
            current_status="pending_admin_debug_decision",
            target_status="admin/debug tools are replaced or explicitly retained as non-primary fallback",
            local_prerequisite_visible="legacy_admin_debug_tools" in full_removal_blocking_workflows,
            direct_evidence_required=True,
            missing_evidence=[
                "admin/debug route replacement decision",
                "fallback-only access policy",
                "guardrail review for retained old modules",
            ],
        ),
        _streamlit_retirement_durable_evidence_recipe_row(
            "fallback_retirement_change_review",
            current_status="local_explicit_retirement_review_done_retirement_blocked"
            if fallback_retirement_review_done
            else "pending_explicit_retirement_review",
            target_status="fallback removal receives explicit review after parity evidence exists",
            local_prerequisite_visible=local_receipt_ready,
            direct_evidence_required=not fallback_retirement_review_done,
            missing_evidence=[] if fallback_retirement_review_done else [
                "ordinary fallback blocker count is zero",
                "full removal blocker count is zero or retained-by-policy",
                "explicit fallback retirement approval",
            ],
        ),
        _streamlit_retirement_durable_evidence_recipe_row(
            "app_py_removal_or_retention_decision",
            current_status="pending_explicit_app_py_decision",
            target_status="app.py is either retained as guarded fallback or removed after replacement proof",
            local_prerequisite_visible=True,
            direct_evidence_required=True,
            missing_evidence=[
                "app.py retention/removal decision record",
                "legacy entrypoint and docs update review",
                "rollback/fallback note if retained",
            ],
        ),
        _streamlit_retirement_durable_evidence_recipe_row(
            "legacy_guardrail_regression_review",
            current_status="local_verified",
            target_status="legacy guardrails remain tested during retirement work",
            local_prerequisite_visible=bool(
                primary_workflow_exit_audit.get("does_not_open_streamlit")
                and primary_workflow_exit_audit.get("does_not_run_legacy_tools")
                and retirement_readiness_receipt.get("does_not_modify_strategy_action")
            ),
            direct_evidence_required=False,
            missing_evidence=[],
        ),
        _streamlit_retirement_durable_evidence_recipe_row(
            "production_promotion_approval",
            current_status="pending_production_promotion_approval",
            target_status="ordinary workflow exit and fallback retirement are explicitly promoted",
            local_prerequisite_visible=local_recipe_ready,
            direct_evidence_required=True,
            missing_evidence=[
                "ordinary workflow replacement parity evidence",
                "Candidate Radar no-feature-loss evidence",
                "browser/performance QA evidence",
                "admin/debug decision",
                "explicit production promotion approval",
            ],
        ),
    ]
    blocker_rows = [row for row in rows if row["production_blocker"]]
    return {
        "schema_version": STREAMLIT_RETIREMENT_DURABLE_EVIDENCE_SCHEMA_VERSION,
        "status": "streamlit_retirement_durable_evidence_recipe_ready_fallback_blocked"
        if local_recipe_ready
        else "streamlit_retirement_durable_evidence_recipe_blocked_local_contract",
        "scope": "local_streamlit_retirement_durable_evidence_recipe_no_streamlit_execution",
        "ltg": "LTG-10",
        "local_recipe_ready": local_recipe_ready,
        "durable_evidence_complete": False,
        "durable_promotion_ready": False,
        "ordinary_workflow_exit_complete": False,
        "streamlit_fallback_removal_ready": False,
        "full_streamlit_removal_ready": False,
        "streamlit_fallback_retained": True,
        "legacy_fallback_required": True,
        "feature_parity_required_before_removal": True,
        "no_feature_cut_allowed": True,
        "allowed_next_step": "collect_direct_replacement_parity_browser_provider_and_retirement_review_evidence",
        "not_allowed_next_steps": [
            "treat durable recipe as Streamlit retirement completion",
            "remove fallback before ordinary workflow parity is proven",
            "delete app.py before explicit retention or removal decision",
            "open Streamlit from GET cache or page render",
            "run legacy tools from GET cache or page render",
            "create tasks from GET cache or page render",
            "use provider/model calls as page startup behavior",
        ],
        "missing_evidence_items": sorted(
            {item for row in blocker_rows for item in _as_list(row.get("missing_evidence"))}
        ),
        "row_count": len(rows),
        "production_blocker_count": len(blocker_rows),
        "blocking_evidence_keys": [row["evidence_key"] for row in blocker_rows],
        "ordinary_blocking_workflows": ordinary_blocking_workflows,
        "full_removal_blocking_workflows": full_removal_blocking_workflows,
        "streamlit_opened_by_recipe": False,
        "legacy_tools_run_by_recipe": False,
        "tasks_created_by_recipe": False,
        "fallback_removed_by_recipe": False,
        "app_py_deleted_by_recipe": False,
        "provider_model_task_dispatched_by_recipe": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_streamlit_retirement_durable_evidence_recipe",
                "source": "legacy exit audit, fallback dependency contract, and retirement readiness receipt",
                "row_count": len(rows),
                "production_blocker_count": len(blocker_rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_durable_evidence_recipe",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_open_streamlit": True,
                "does_not_run_legacy_tools": True,
                "does_not_create_tasks": True,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This recipe fixes the durable evidence still required before LTG-10 can exit ordinary workflow. It does not open Streamlit, run legacy tools, remove fallback, delete app.py, call providers/models/GitHub, execute trades, or mark retirement complete.",
    }


def _streamlit_ordinary_workflow_parity_review_contract(
    *,
    legacy_packet: Mapping[str, Any],
    explicit_review: bool,
    task_id: str,
    reviewed_at: str,
    operator_safe: str = "",
) -> dict[str, Any]:
    route_rows = [row for row in _as_list(legacy_packet.get("primary_workflow_route_rows")) if isinstance(row, dict)]
    fallback_contract = _as_dict(legacy_packet.get("streamlit_fallback_dependency_contract"))
    primary_exit_audit = _as_dict(legacy_packet.get("primary_workflow_exit_audit"))
    review_rows: list[dict[str, Any]] = []
    for row in route_rows:
        workflow = str(row.get("workflow") or "unknown_workflow")
        ordinary_flow_supported = row.get("ordinary_flow_supported") is True
        fallback_required = row.get("still_needs_streamlit_fallback") is True
        if workflow == "legacy_admin_debug_tools":
            parity_status = "legacy_admin_debug_fallback_retained"
            evidence_class = "admin_debug_retention_pending"
        elif fallback_required:
            parity_status = "partial_react_route_fallback_required"
            evidence_class = "ordinary_workflow_direct_review_pending_replacement_parity"
        else:
            parity_status = "react_tauri_route_parity_visible"
            evidence_class = "ordinary_workflow_direct_review_passed_for_route_inventory"
        review_rows.append(
            {
                "workflow": workflow,
                "react_route": row.get("react_route"),
                "api": row.get("api"),
                "coverage_status": row.get("coverage_status"),
                "ordinary_flow_supported": ordinary_flow_supported,
                "still_needs_streamlit_fallback": fallback_required,
                "parity_status": parity_status,
                "evidence_class": evidence_class,
                "direct_evidence_key": "ordinary_workflow_replacement_parity",
                "blocks_ordinary_primary_exit": bool(ordinary_flow_supported and fallback_required),
                "blocks_full_streamlit_removal": fallback_required,
                "fallback_reason": row.get("fallback_reason") or "",
                "feature_parity_required_before_removal": True,
                "no_feature_cut_allowed": True,
                "streamlit_opened_by_review": False,
                "legacy_tools_run_by_review": False,
                "tasks_created_by_cache_render": False,
                "provider_model_task_dispatched_by_review": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "does_not_modify_holdings": True,
                "contains_secret": False,
            }
        )

    ordinary_rows = [row for row in review_rows if row["ordinary_flow_supported"]]
    ordinary_blockers = [row for row in review_rows if row["blocks_ordinary_primary_exit"]]
    full_removal_blockers = [row for row in review_rows if row["blocks_full_streamlit_removal"]]
    migrated_without_fallback = [
        row for row in ordinary_rows if not row["still_needs_streamlit_fallback"]
    ]
    review_ready = bool(explicit_review and route_rows and fallback_contract)
    replacement_parity_complete = bool(review_ready and ordinary_rows and not ordinary_blockers)
    direct_evidence_verified = review_ready
    status = (
        "streamlit_ordinary_workflow_parity_review_ready_exit_review_pending"
        if replacement_parity_complete
        else "streamlit_ordinary_workflow_parity_review_ready_fallback_required"
        if review_ready
        else "streamlit_ordinary_workflow_parity_review_blocked_missing_local_contract"
    )
    production_blocker_count = len(ordinary_blockers) + len(
        [row for row in full_removal_blockers if row["workflow"] == "legacy_admin_debug_tools"]
    )
    call_ledger = [
        {
            "api": "local_streamlit_ordinary_workflow_parity_review",
            "task_id": task_id,
            "source": "GET /api/legacy/cache local route inventory and fallback dependency contract",
            "row_count": len(review_rows),
            "ordinary_workflow_count": len(ordinary_rows),
            "ordinary_fallback_dependency_count": len(ordinary_blockers),
            "full_streamlit_removal_blocker_count": len(full_removal_blockers),
            "local_fetched_at": reviewed_at,
            "call_status": status,
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_open_streamlit": True,
            "does_not_run_legacy_tools": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]
    return {
        "packet_key": STREAMLIT_ORDINARY_WORKFLOW_PARITY_REVIEW_PACKET_KEY,
        "schema_version": STREAMLIT_ORDINARY_WORKFLOW_PARITY_REVIEW_SCHEMA_VERSION,
        "status": status,
        "scope": "local_streamlit_ordinary_workflow_parity_review_no_streamlit_execution",
        "ltg": "LTG-10/LTG-13",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "operator_safe": operator_safe,
        "explicit_post_task_review": bool(explicit_review),
        "button_gated": True,
        "direct_evidence_key": "ordinary_workflow_replacement_parity",
        "direct_evidence_layer": "L3_local_streamlit_ordinary_workflow_parity_inventory",
        "direct_evidence_verified": direct_evidence_verified,
        "local_review_ready": review_ready,
        "replacement_parity_complete": replacement_parity_complete,
        "candidate_radar_parity_complete": False,
        "provider_backed_parity_done": False,
        "browser_performance_qa_done": False,
        "admin_debug_retention_decision_done": False,
        "ordinary_workflow_exit_complete": False,
        "streamlit_fallback_removal_ready": False,
        "full_streamlit_removal_ready": False,
        "streamlit_fallback_retained": True,
        "legacy_fallback_required": bool(full_removal_blockers),
        "feature_parity_required_before_removal": True,
        "no_feature_cut_allowed": True,
        "ordinary_workflow_route_count": len(ordinary_rows),
        "ordinary_workflow_migrated_without_fallback_count": len(migrated_without_fallback),
        "ordinary_fallback_dependency_count": len(ordinary_blockers),
        "full_streamlit_removal_blocker_count": len(full_removal_blockers),
        "production_blocker_count": production_blocker_count,
        "ordinary_blocking_workflows": [row["workflow"] for row in ordinary_blockers],
        "full_removal_blocking_workflows": [row["workflow"] for row in full_removal_blockers],
        "source_exit_audit_status": str(primary_exit_audit.get("status") or "missing"),
        "source_fallback_contract_status": str(fallback_contract.get("status") or "missing"),
        "streamlit_opened_by_review": False,
        "legacy_tools_run_by_review": False,
        "tasks_created_by_cache_render": False,
        "fallback_removed_by_review": False,
        "app_py_deleted_by_review": False,
        "provider_model_task_dispatched_by_review": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "row_count": len(review_rows),
        "rows": review_rows,
        "call_ledger": call_ledger,
        "warnings": [
            "This LTG-10 parity review is local direct evidence, not Streamlit retirement completion.",
            "It does not open Streamlit, run legacy tools, call Tushare/DeepSeek/GitHub, or execute trades.",
            "Candidate Radar and admin/debug fallback blockers remain visible until separate evidence clears them.",
        ],
    }


def _read_streamlit_ordinary_workflow_parity_review_packet() -> dict[str, Any]:
    if not SQLITE_META_PATH.exists():
        return {}
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(
            STREAMLIT_ORDINARY_WORKFLOW_PARITY_REVIEW_PACKET_KEY
        )
    except Exception:
        return {}
    return packet if isinstance(packet, dict) else {}


def _write_streamlit_ordinary_workflow_parity_review_packet(packet: Mapping[str, Any]) -> None:
    SQLiteMetaStore(SQLITE_META_PATH).write_packet(
        STREAMLIT_ORDINARY_WORKFLOW_PARITY_REVIEW_PACKET_KEY,
        _json_safe(packet),
    )


def _streamlit_fallback_retirement_review_contract(
    *,
    legacy_packet: Mapping[str, Any],
    explicit_review: bool,
    task_id: str,
    reviewed_at: str,
    operator_safe: str = "",
) -> dict[str, Any]:
    fallback_contract = _as_dict(legacy_packet.get("streamlit_fallback_dependency_contract"))
    retirement_receipt = _as_dict(legacy_packet.get("streamlit_retirement_readiness_receipt"))
    durable_recipe = _as_dict(legacy_packet.get("streamlit_retirement_durable_evidence_recipe"))
    parity_review = _as_dict(legacy_packet.get("streamlit_ordinary_workflow_parity_review"))
    parity_ready = bool(
        parity_review.get("direct_evidence_verified") is True
        and parity_review.get("local_review_ready") is True
        and parity_review.get("fallback_removed_by_review") is False
    )
    ordinary_blocking_workflows = [
        str(item) for item in _as_list(fallback_contract.get("ordinary_blocking_workflows"))
    ]
    full_removal_blocking_workflows = [
        str(item) for item in _as_list(fallback_contract.get("full_removal_blocking_workflows"))
    ]
    ordinary_blocker_count = int(fallback_contract.get("ordinary_fallback_dependency_count") or 0)
    full_blocker_count = int(fallback_contract.get("full_streamlit_removal_blocker_count") or 0)
    local_contracts_visible = bool(
        fallback_contract.get("schema_version") == "streamlit_fallback_dependency_contract.v1"
        and retirement_receipt.get("schema_version") == "streamlit_retirement_readiness_receipt.v1"
        and durable_recipe.get("schema_version") == STREAMLIT_RETIREMENT_DURABLE_EVIDENCE_SCHEMA_VERSION
        and fallback_contract.get("does_not_open_streamlit") is True
        and retirement_receipt.get("does_not_create_tasks") is True
        and durable_recipe.get("local_recipe_ready") is True
    )
    local_review_ready = bool(explicit_review and local_contracts_visible)
    direct_evidence_verified = bool(local_review_ready and parity_ready)

    def _row(criterion: str, passed: bool, detail: str, required_evidence: str) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": "passed" if passed else "blocked",
            "passed": bool(passed),
            "production_blocker": not passed,
            "detail": detail,
            "required_evidence": required_evidence,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "streamlit_opened_by_review": False,
            "legacy_tools_run_by_review": False,
            "fallback_removed_by_review": False,
            "app_py_deleted_by_review": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_holdings": True,
            "contains_secret": False,
        }

    rows = [
        _row(
            "explicit_fallback_retirement_review_task",
            bool(explicit_review),
            "The operator used an explicit POST task for fallback retirement review.",
            "POST /api/legacy/fallback-retirement-review must be the only way to create this receipt.",
        ),
        _row(
            "local_retirement_contracts_visible",
            local_contracts_visible,
            "Legacy cache exposes fallback dependency, retirement readiness, and durable evidence recipe contracts.",
            "GET /api/legacy/cache contracts are visible and read-only.",
        ),
        _row(
            "ordinary_workflow_parity_review_visible",
            parity_ready,
            f"ordinary parity review status={parity_review.get('status') or 'missing'}",
            "Run POST /api/legacy/ordinary-workflow-parity-review before fallback retirement review.",
        ),
        _row(
            "ordinary_fallback_blockers_resolved",
            ordinary_blocker_count == 0,
            f"ordinary_blocker_count={ordinary_blocker_count}; ordinary_blocking_workflows={ordinary_blocking_workflows}",
            "All ordinary workflows must have Command Center 3 parity before fallback retirement.",
        ),
        _row(
            "admin_debug_retention_or_replacement_decided",
            "legacy_admin_debug_tools" not in full_removal_blocking_workflows,
            f"full_removal_blocking_workflows={full_removal_blocking_workflows}",
            "Admin/debug tools need replacement or an explicit retained-fallback policy.",
        ),
        _row(
            "provider_browser_and_radar_evidence_complete",
            bool(
                parity_review.get("candidate_radar_parity_complete") is True
                and parity_review.get("provider_backed_parity_done") is True
                and parity_review.get("browser_performance_qa_done") is True
            ),
            "Candidate Radar, provider-backed parity, and browser/performance evidence are still pending.",
            "Collect provider/worker/browser evidence before production fallback removal.",
        ),
        _row(
            "fallback_retained_no_feature_cut",
            bool(fallback_contract.get("no_feature_cut_allowed") is True),
            "Fallback remains retained and no feature-cut boundary is visible.",
            "No fallback may be removed by deleting or hiding old functionality.",
        ),
        _row(
            "cache_render_no_side_effects",
            True,
            "Review writes only a local receipt and does not run Streamlit, providers, models, GitHub, or trades.",
            "GET cache and React render remain read-only; POST review stays local.",
        ),
    ]
    blocked_rows = [row for row in rows if row["status"] != "passed"]
    status = (
        "streamlit_fallback_retirement_review_ready_retirement_blocked"
        if direct_evidence_verified
        else "streamlit_fallback_retirement_review_blocked_missing_parity"
        if local_review_ready
        else "streamlit_fallback_retirement_review_blocked_local_contract"
    )
    call_ledger = [
        {
            "api": "local_streamlit_fallback_retirement_review",
            "task_id": task_id,
            "source": "GET /api/legacy/cache local parity review and retirement blockers",
            "row_count": len(rows),
            "production_blocker_count": len(blocked_rows),
            "ordinary_fallback_dependency_count": ordinary_blocker_count,
            "full_streamlit_removal_blocker_count": full_blocker_count,
            "local_fetched_at": reviewed_at,
            "call_status": status,
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_open_streamlit": True,
            "does_not_run_legacy_tools": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]
    return {
        "packet_key": STREAMLIT_FALLBACK_RETIREMENT_REVIEW_PACKET_KEY,
        "schema_version": STREAMLIT_FALLBACK_RETIREMENT_REVIEW_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_local_streamlit_fallback_retirement_review_no_streamlit_execution",
        "ltg": "LTG-10",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "operator_safe": operator_safe,
        "button_gated": True,
        "explicit_post_task_review": bool(explicit_review),
        "explicit_fallback_retirement_review_done": bool(explicit_review),
        "direct_evidence_key": "fallback_retirement_change_review",
        "direct_evidence_layer": "L3_local_streamlit_fallback_retirement_review",
        "direct_evidence_verified": direct_evidence_verified,
        "local_review_ready": local_review_ready,
        "fallback_retirement_review_visible": True,
        "fallback_retirement_change_review_done": direct_evidence_verified,
        "ordinary_workflow_parity_review_ready": parity_ready,
        "ordinary_workflow_exit_complete": False,
        "streamlit_fallback_removal_ready": False,
        "full_streamlit_removal_ready": False,
        "streamlit_fallback_retained": True,
        "legacy_fallback_required": True,
        "feature_parity_required_before_removal": True,
        "no_feature_cut_allowed": True,
        "replacement_parity_complete": parity_review.get("replacement_parity_complete") is True,
        "candidate_radar_parity_complete": False,
        "provider_backed_parity_done": False,
        "browser_performance_qa_done": False,
        "admin_debug_retention_decision_done": False,
        "ordinary_fallback_dependency_count": ordinary_blocker_count,
        "full_streamlit_removal_blocker_count": full_blocker_count,
        "production_blocker_count": len(blocked_rows),
        "ordinary_blocking_workflows": ordinary_blocking_workflows,
        "full_removal_blocking_workflows": full_removal_blocking_workflows,
        "streamlit_opened_by_review": False,
        "legacy_tools_run_by_review": False,
        "tasks_created_by_review": False,
        "fallback_removed_by_review": False,
        "app_py_deleted_by_review": False,
        "provider_model_task_dispatched_by_review": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "row_count": len(rows),
        "rows": rows,
        "call_ledger": call_ledger,
        "warnings": [
            "This fallback retirement review is local direct evidence, not Streamlit fallback removal.",
            "It does not open Streamlit, run legacy tools, call Tushare/DeepSeek/GitHub, delete app.py, or execute trades.",
            "Production retirement stays blocked until ordinary/admin-debug/provider/browser/radar blockers are cleared.",
        ],
    }


def _read_streamlit_fallback_retirement_review_packet() -> dict[str, Any]:
    if not SQLITE_META_PATH.exists():
        return {}
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(
            STREAMLIT_FALLBACK_RETIREMENT_REVIEW_PACKET_KEY
        )
    except Exception:
        return {}
    return packet if isinstance(packet, dict) else {}


def _write_streamlit_fallback_retirement_review_packet(packet: Mapping[str, Any]) -> None:
    SQLiteMetaStore(SQLITE_META_PATH).write_packet(
        STREAMLIT_FALLBACK_RETIREMENT_REVIEW_PACKET_KEY,
        _json_safe(packet),
    )


def run_legacy_audit_observation_dry_run_task(payload: Any = None) -> dict[str, Any]:
    payload_safe = _sanitize_legacy_audit_observation_payload(payload)
    receipt, rows = _build_legacy_audit_observation_receipt(payload_safe)
    payload_safe.update(
        {
            "task_type": LEGACY_AUDIT_OBSERVATION_DRY_RUN_TASK_TYPE,
            "route": "POST /api/legacy/audit-observation-dry-run",
            "output_packet_key": LEGACY_AUDIT_OBSERVATION_DRY_RUN_PACKET_KEY,
            "legacy_audit_observation_receipt": receipt,
            "legacy_audit_observation_rows": rows,
            "observation_dry_run_only": True,
            "keep_promotion_allowed_this_round": False,
            "ordinary_entry_promotion_allowed_this_round": False,
            "streamlit_fallback_retirement_allowed": False,
            "production_evidence": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_open_streamlit": True,
            "does_not_run_legacy_tools": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    )
    if receipt["status"] == "legacy_audit_observation_dry_run_recorded_no_keep_promotion":
        current_step = "legacy_audit_observation_dry_run_recorded_no_keep_promotion"
    elif receipt["status"] == "legacy_audit_observation_dry_run_blocked_keep_promotion_not_allowed":
        current_step = "legacy_audit_observation_dry_run_blocked_keep_promotion_not_allowed"
    elif receipt["status"] == "legacy_audit_observation_dry_run_blocked_unknown_workflow":
        current_step = "legacy_audit_observation_dry_run_blocked_unknown_workflow"
    elif receipt["status"] == "legacy_audit_observation_dry_run_blocked_unsafe_attachment_source":
        current_step = "legacy_audit_observation_dry_run_blocked_unsafe_attachment_source"
    else:
        current_step = "legacy_audit_observation_dry_run_blocked_missing_required_fields"
    task = create_task_record(
        LEGACY_AUDIT_OBSERVATION_DRY_RUN_TASK_TYPE,
        output_packet_key=LEGACY_AUDIT_OBSERVATION_DRY_RUN_PACKET_KEY,
        payload=payload_safe,
        current_step="legacy_audit_observation_dry_run_requested_local_only",
        warnings=[
            "Legacy Audit observation dry-run 只记录脱敏问题陈述，不打开 Streamlit，不运行旧工具。",
            "本任务不能升级 KEEP，不能让旧模块进入普通入口，也不能作为 Streamlit retirement evidence。",
            "本任务不调用 Tushare、DeepSeek、GitHub，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    now = _now_iso()
    ledger = [_legacy_audit_observation_call_ledger(payload_safe=payload_safe, receipt=receipt, now=now)]
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=current_step,
        output_packet_key=LEGACY_AUDIT_OBSERVATION_DRY_RUN_PACKET_KEY,
        call_ledger=ledger,
        warning="legacy_audit_observation_dry_run_completed_no_streamlit_no_external_call",
    ) or task


def _latest_legacy_audit_observation_status() -> dict[str, Any]:
    tasks = [
        task
        for task in list_task_statuses()
        if task.get("task_type") == LEGACY_AUDIT_OBSERVATION_DRY_RUN_TASK_TYPE
    ]
    if not tasks:
        return {
            "schema_version": "legacy_audit_latest_observation_status.v1",
            "status": "no_legacy_audit_observation_dry_run_task_found",
            "lookup_source": "task_service.list_task_statuses",
            "lookup_creates_task": False,
            "route": "POST /api/legacy/audit-observation-dry-run",
            "task_type": LEGACY_AUDIT_OBSERVATION_DRY_RUN_TASK_TYPE,
            "receipt_found": False,
            "task_id": "",
            "task_status": "",
            "current_step": "",
            "output_packet_key": "",
            "storage_source": "",
            "workflow_group": "",
            "proposed_status": "",
            "direct_user_evidence_recorded": False,
            "direct_evidence_ready_for_keep_review": False,
            "keep_promotion_allowed_this_round": False,
            "ordinary_entry_promotion_allowed_this_round": False,
            "streamlit_fallback_retirement_allowed": False,
            "production_evidence": False,
            "row_count": 0,
            "rows": [],
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_open_streamlit": True,
            "does_not_run_legacy_tools": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "call_ledger": [
                {
                    "api": "local_legacy_audit_latest_observation_status",
                    "lookup_source": "task_service.list_task_statuses",
                    "row_count": 0,
                    "call_status": "latest_observation_missing_cache_read",
                    "local_fetched_at": _now_iso(),
                    "external": False,
                    "external_calls_triggered": False,
                    "tushare_called": False,
                    "deepseek_called": False,
                    "github_called": False,
                    "does_not_open_streamlit": True,
                    "does_not_run_legacy_tools": True,
                    "does_not_execute_trades": True,
                    "does_not_modify_strategy_action": True,
                }
            ],
        }

    latest_task = tasks[0]
    payload = _as_dict(latest_task.get("payload_safe"))
    receipt = _as_dict(payload.get("legacy_audit_observation_receipt"))
    rows = _as_list(payload.get("legacy_audit_observation_rows"))
    direct_recorded = receipt.get("direct_user_evidence_recorded") is True
    return {
        "schema_version": "legacy_audit_latest_observation_status.v1",
        "status": "latest_legacy_audit_observation_visible_recorded"
        if direct_recorded
        else "latest_legacy_audit_observation_visible_blocked",
        "lookup_source": "task_service.list_task_statuses",
        "lookup_creates_task": False,
        "route": "POST /api/legacy/audit-observation-dry-run",
        "task_type": LEGACY_AUDIT_OBSERVATION_DRY_RUN_TASK_TYPE,
        "receipt_found": True,
        "task_id": latest_task.get("task_id"),
        "task_status": latest_task.get("status"),
        "current_step": latest_task.get("current_step"),
        "output_packet_key": latest_task.get("output_packet_key"),
        "storage_source": latest_task.get("storage_source") or "",
        "workflow_group": receipt.get("workflow_group"),
        "proposed_status": receipt.get("proposed_status"),
        "receipt_status": receipt.get("status"),
        "direct_user_evidence_recorded": direct_recorded,
        "direct_evidence_ready_for_keep_review": False,
        "keep_promotion_allowed_this_round": False,
        "ordinary_entry_promotion_allowed_this_round": False,
        "streamlit_fallback_retirement_allowed": False,
        "production_evidence": False,
        "row_count": len(rows),
        "rows": rows,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_open_streamlit": True,
        "does_not_run_legacy_tools": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_legacy_audit_latest_observation_status",
                "lookup_source": "task_service.list_task_statuses",
                "task_id": latest_task.get("task_id"),
                "workflow_group": receipt.get("workflow_group"),
                "direct_user_evidence_recorded": direct_recorded,
                "keep_promotion_allowed_this_round": False,
                "ordinary_entry_promotion_allowed_this_round": False,
                "row_count": len(rows),
                "call_status": "latest_observation_cache_read",
                "local_fetched_at": _now_iso(),
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_open_streamlit": True,
                "does_not_run_legacy_tools": True,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
    }


def run_streamlit_ordinary_workflow_parity_review_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, dict) else {}
    task = create_task_record(
        STREAMLIT_ORDINARY_WORKFLOW_PARITY_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="streamlit_ordinary_workflow_parity_review_queued",
        warnings=[
            "Streamlit ordinary workflow parity review 只读取本地 legacy cache/route inventory。",
            "review 不打开 Streamlit，不运行旧工具，不调用 Tushare/DeepSeek/GitHub，不交易，不删除 fallback。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_streamlit_route_inventory",
    )
    legacy_packet = read_legacy_bridge_cache()
    reviewed_at = _now_iso()
    review_contract = _streamlit_ordinary_workflow_parity_review_contract(
        legacy_packet=legacy_packet,
        explicit_review=True,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
        operator_safe=_safe_text(payload_map.get("operator") or "", limit=120),
    )
    _write_streamlit_ordinary_workflow_parity_review_packet(review_contract)
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="streamlit_ordinary_workflow_parity_review_ready_fallback_required"
        if review_contract["local_review_ready"]
        else "streamlit_ordinary_workflow_parity_review_blocked",
        call_ledger=review_contract["call_ledger"],
        warning="streamlit_ordinary_workflow_parity_review_completed_no_streamlit_no_external_call",
    ) or task


def run_streamlit_fallback_retirement_review_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, dict) else {}
    task = create_task_record(
        STREAMLIT_FALLBACK_RETIREMENT_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="streamlit_fallback_retirement_review_queued",
        warnings=[
            "Streamlit fallback retirement review 只审查本地 parity/retirement blocker。",
            "review 不打开 Streamlit，不运行旧工具，不调用 Tushare/DeepSeek/GitHub，不交易，不删除 fallback。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_streamlit_retirement_evidence",
    )
    legacy_packet = read_legacy_bridge_cache()
    reviewed_at = _now_iso()
    review_contract = _streamlit_fallback_retirement_review_contract(
        legacy_packet=legacy_packet,
        explicit_review=True,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
        operator_safe=_safe_text(payload_map.get("operator") or "", limit=120),
    )
    _write_streamlit_fallback_retirement_review_packet(review_contract)
    return update_task_status(
        task["task_id"],
        status="success" if review_contract["local_review_ready"] else "failed",
        progress=1.0,
        current_step=review_contract["status"],
        call_ledger=review_contract["call_ledger"],
        warning="streamlit_fallback_retirement_review_completed_no_streamlit_no_external_call",
    ) or task


def read_legacy_bridge_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}

    migration_map = _as_dict(snapshot_map.get("legacy_migration_map"))
    checklist = _as_dict(snapshot_map.get("legacy_packet_migration_checklist"))
    packet_bridge = _as_dict(snapshot_map.get("old_workspace_packet_bridge"))
    capability = _as_dict(snapshot_map.get("old_workspace_capability_overview"))
    absence_ledger = _as_dict(snapshot_map.get("old_workspace_data_absence_ledger"))
    decision_chain = _as_dict(snapshot_map.get("legacy_decision_chain_summary"))
    gap_summary = _as_dict(snapshot_map.get("legacy_a_share_gap_summary"))
    fact_recovery_actions = _rows(snapshot_map.get("legacy_a_share_fact_recovery_actions"), source="legacy_a_share_fact_recovery_actions")

    migration_items = _rows(migration_map.get("items"), source="legacy_migration_map.items")
    migration_lanes = _rows(migration_map.get("lanes"), source="legacy_migration_map.lanes")
    checklist_items = _rows(checklist.get("items"), source="legacy_packet_migration_checklist.items")
    bridge_items = _rows(packet_bridge.get("items"), source="old_workspace_packet_bridge.items")
    capability_items = _rows(capability.get("items"), source="old_workspace_capability_overview.items")
    absence_items = _rows(absence_ledger.get("items"), source="old_workspace_data_absence_ledger.items")
    decision_chain_items = _rows(decision_chain.get("items"), source="legacy_decision_chain_summary.items")
    gap_items = _rows(gap_summary.get("items"), source="legacy_a_share_gap_summary.items")
    checklist_counts = _checklist_counts(checklist, capability)

    has_cache = any(
        bool(item)
        for item in (
            migration_map,
            checklist,
            packet_bridge,
            capability,
            absence_ledger,
            decision_chain,
            gap_summary,
            fact_recovery_actions,
        )
    )
    status = "ready" if migration_map or checklist or packet_bridge or capability else "partial" if has_cache or snapshot else "cache_missing"
    summary = (
        capability.get("summary")
        or packet_bridge.get("summary")
        or checklist.get("summary")
        or migration_map.get("summary")
        or "旧工作台桥接 cache 只读展示；Streamlit 保留为 legacy/admin/debug。"
    )
    policy = {
        "cache_api_external_calls": False,
        "does_not_call_tushare": True,
        "does_not_call_deepseek": True,
        "does_not_call_github": True,
        "does_not_open_streamlit": True,
        "does_not_run_legacy_tools": True,
        "does_not_run_backtest": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "streamlit_role": "legacy/admin/debug",
        "official_primary_entry": "React/Vite/Tauri + FastAPI",
        "streamlit_is_official_primary_entry": False,
        "react_tauri_is_primary_entry": True,
        "legacy_startup_external_calls": False,
        "legacy_startup_task_creation": False,
        "legacy_can_bypass_guardrails": False,
        "legacy_bridge_is_not_trade_instruction": True,
        "post_task_required_for_migration_work": True,
    }
    primary_workflow_exit_audit = _primary_workflow_exit_audit(
        policy=policy,
        checklist_counts=checklist_counts,
        status=status,
        snapshot_available=bool(snapshot),
    )
    ordinary_entrance_acceptance_audit = _ordinary_entrance_acceptance_audit()
    legacy_audit_first_round_intake, legacy_audit_first_round_intake_rows = (
        _legacy_audit_first_round_intake_status()
    )
    latest_legacy_audit_observation_status = _latest_legacy_audit_observation_status()
    fallback_dependency_contract = _streamlit_fallback_dependency_contract(primary_workflow_exit_audit["route_rows"])
    ordinary_parity_review = _read_streamlit_ordinary_workflow_parity_review_packet()
    ordinary_parity_review_rows = _as_list(ordinary_parity_review.get("rows"))
    ordinary_parity_review_call_ledger = _as_list(ordinary_parity_review.get("call_ledger"))
    fallback_retirement_review = _read_streamlit_fallback_retirement_review_packet()
    fallback_retirement_review_rows = _as_list(fallback_retirement_review.get("rows"))
    fallback_retirement_review_call_ledger = _as_list(fallback_retirement_review.get("call_ledger"))
    retirement_readiness_receipt = _streamlit_retirement_readiness_receipt(
        primary_workflow_exit_audit=primary_workflow_exit_audit,
        fallback_dependency_contract=fallback_dependency_contract,
    )
    durable_evidence_recipe = _streamlit_retirement_durable_evidence_recipe(
        primary_workflow_exit_audit=primary_workflow_exit_audit,
        fallback_dependency_contract=fallback_dependency_contract,
        retirement_readiness_receipt=retirement_readiness_receipt,
        fallback_retirement_review=fallback_retirement_review,
    )

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "snapshot_available": bool(snapshot),
        "source_packet_keys": [
            "legacy_migration_map",
            "legacy_packet_migration_checklist",
            "old_workspace_packet_bridge",
            "old_workspace_capability_overview",
            "old_workspace_data_absence_ledger",
            "legacy_decision_chain_summary",
            "legacy_a_share_gap_summary",
            "legacy_a_share_fact_recovery_actions",
        ],
        "summary": summary,
        "legacy_migration_map": migration_map,
        "legacy_packet_migration_checklist": checklist,
        "old_workspace_packet_bridge": packet_bridge,
        "old_workspace_capability_overview": capability,
        "old_workspace_data_absence_ledger": absence_ledger,
        "legacy_decision_chain_summary": decision_chain,
        "legacy_a_share_gap_summary": gap_summary,
        "migration_items": migration_items,
        "migration_lanes": migration_lanes,
        "checklist_items": checklist_items,
        "bridge_items": bridge_items,
        "capability_items": capability_items,
        "absence_items": absence_items,
        "decision_chain_items": decision_chain_items,
        "gap_items": gap_items,
        "fact_recovery_action_rows": fact_recovery_actions,
        "primary_workflow_exit_audit": primary_workflow_exit_audit,
        "primary_workflow_exit_rows": primary_workflow_exit_audit["rows"],
        "primary_workflow_route_rows": primary_workflow_exit_audit["route_rows"],
        "ordinary_entrance_acceptance_audit": ordinary_entrance_acceptance_audit,
        "ordinary_entrance_acceptance_rows": ordinary_entrance_acceptance_audit["rows"],
        "legacy_bug_ux_module_rows": ordinary_entrance_acceptance_audit["legacy_bug_ux_module_rows"],
        "legacy_audit_first_round_intake": legacy_audit_first_round_intake,
        "legacy_audit_first_round_intake_rows": legacy_audit_first_round_intake_rows,
        "legacy_audit_latest_observation_status": latest_legacy_audit_observation_status,
        "legacy_audit_latest_observation_rows": latest_legacy_audit_observation_status["rows"],
        "streamlit_fallback_dependency_contract": fallback_dependency_contract,
        "streamlit_fallback_dependency_rows": fallback_dependency_contract["rows"],
        "streamlit_retirement_readiness_receipt": retirement_readiness_receipt,
        "streamlit_retirement_readiness_rows": retirement_readiness_receipt["rows"],
        "streamlit_retirement_durable_evidence_recipe": durable_evidence_recipe,
        "streamlit_retirement_durable_evidence_rows": durable_evidence_recipe["rows"],
        "streamlit_ordinary_workflow_parity_review": ordinary_parity_review,
        "streamlit_ordinary_workflow_parity_review_rows": ordinary_parity_review_rows,
        "streamlit_fallback_retirement_review": fallback_retirement_review,
        "streamlit_fallback_retirement_review_rows": fallback_retirement_review_rows,
        "counts": {
            **checklist_counts,
            "migration_item_count": len(migration_items),
            "migration_lane_count": len(migration_lanes),
            "checklist_item_count": len(checklist_items),
            "bridge_item_count": len(bridge_items),
            "capability_item_count": len(capability_items),
            "absence_item_count": len(absence_items),
            "decision_chain_item_count": len(decision_chain_items),
            "fact_recovery_action_count": len(fact_recovery_actions),
            "decision_ready_count": decision_chain.get("ready_count", 0),
            "decision_waiting_count": decision_chain.get("waiting_count", 0),
            "decision_blocked_count": decision_chain.get("blocked_count", 0),
            "primary_workflow_route_count": primary_workflow_exit_audit["ordinary_workflow_route_count"],
            "primary_workflow_fallback_count": primary_workflow_exit_audit["ordinary_workflow_still_needs_fallback_count"],
            "primary_workflow_exit_blocker_count": primary_workflow_exit_audit["blocker_count"],
            "ordinary_entrance_acceptance_row_count": ordinary_entrance_acceptance_audit["row_count"],
            "legacy_bug_ux_module_row_count": ordinary_entrance_acceptance_audit[
                "legacy_bug_ux_module_row_count"
            ],
            "legacy_bug_ux_redesign_count": ordinary_entrance_acceptance_audit[
                "legacy_bug_ux_redesign_count"
            ],
            "legacy_bug_ux_legacy_debug_count": ordinary_entrance_acceptance_audit[
                "legacy_bug_ux_legacy_debug_count"
            ],
            "legacy_bug_ux_retire_count": ordinary_entrance_acceptance_audit[
                "legacy_bug_ux_retire_count"
            ],
            "legacy_bug_ux_direct_evidence_pending_count": ordinary_entrance_acceptance_audit[
                "legacy_bug_ux_direct_evidence_pending_count"
            ],
            "legacy_bug_ux_keep_upgrade_blocked_count": ordinary_entrance_acceptance_audit[
                "legacy_bug_ux_keep_upgrade_blocked_count"
            ],
            "ordinary_entrance_acceptance_complete_count": 1
            if ordinary_entrance_acceptance_audit["ordinary_entrance_acceptance_complete"]
            else 0,
            "legacy_audit_first_round_intake_row_count": len(
                legacy_audit_first_round_intake_rows
            ),
            "legacy_audit_latest_observation_found_count": 1
            if latest_legacy_audit_observation_status["receipt_found"]
            else 0,
            "legacy_audit_latest_observation_row_count": latest_legacy_audit_observation_status[
                "row_count"
            ],
            "legacy_audit_latest_observation_direct_user_evidence_count": 1
            if latest_legacy_audit_observation_status["direct_user_evidence_recorded"]
            else 0,
            "streamlit_fallback_dependency_count": fallback_dependency_contract["full_streamlit_removal_blocker_count"],
            "ordinary_fallback_dependency_count": fallback_dependency_contract["ordinary_fallback_dependency_count"],
            "admin_debug_fallback_retained_count": fallback_dependency_contract["admin_debug_fallback_retained_count"],
            "streamlit_retirement_readiness_receipt_ready": 1 if retirement_readiness_receipt["local_receipt_ready"] else 0,
            "streamlit_retirement_readiness_blocker_count": retirement_readiness_receipt[
                "blocking_criterion_count"
            ],
            "streamlit_retirement_durable_evidence_row_count": durable_evidence_recipe["row_count"],
            "streamlit_retirement_durable_evidence_blocker_count": durable_evidence_recipe[
                "production_blocker_count"
            ],
            "streamlit_ordinary_workflow_parity_review_row_count": len(ordinary_parity_review_rows),
            "streamlit_ordinary_workflow_parity_review_direct_evidence_count": 1
            if ordinary_parity_review.get("direct_evidence_verified") is True
            else 0,
            "streamlit_ordinary_workflow_parity_review_production_blocker_count": int(
                ordinary_parity_review.get("production_blocker_count") or 0
            ),
            "streamlit_fallback_retirement_review_row_count": len(fallback_retirement_review_rows),
            "streamlit_fallback_retirement_review_direct_evidence_count": 1
            if fallback_retirement_review.get("direct_evidence_verified") is True
            else 0,
            "streamlit_fallback_retirement_review_production_blocker_count": int(
                fallback_retirement_review.get("production_blocker_count") or 0
            ),
        },
        "policy": policy,
        "call_ledger": [
            {
                "api": "local_legacy_bridge_cache",
                "source_snapshot": "command_center_latest.json",
                "row_count": len(migration_items) + len(checklist_items) + len(bridge_items),
                "call_status": "cache_read" if snapshot else "cache_missing",
                "local_fetched_at": _now_iso(),
                "external": False,
            }
        ]
        + retirement_readiness_receipt["call_ledger"]
        + durable_evidence_recipe["call_ledger"]
        + ordinary_entrance_acceptance_audit["call_ledger"]
        + legacy_audit_first_round_intake["call_ledger"]
        + latest_legacy_audit_observation_status["call_ledger"]
        + ordinary_parity_review_call_ledger
        + fallback_retirement_review_call_ledger,
        "streamlit_ordinary_workflow_parity_review_ready": ordinary_parity_review.get(
            "local_review_ready"
        )
        is True,
        "streamlit_ordinary_workflow_parity_review_status": ordinary_parity_review.get("status")
        or "missing",
        "streamlit_ordinary_workflow_parity_review_direct_evidence_verified": ordinary_parity_review.get(
            "direct_evidence_verified"
        )
        is True,
        "streamlit_ordinary_workflow_parity_review_is_not_retirement": True,
        "streamlit_fallback_retirement_review_ready": fallback_retirement_review.get("local_review_ready")
        is True,
        "streamlit_fallback_retirement_review_status": fallback_retirement_review.get("status") or "missing",
        "streamlit_fallback_retirement_review_direct_evidence_verified": fallback_retirement_review.get(
            "direct_evidence_verified"
        )
        is True,
        "streamlit_fallback_retirement_review_is_not_retirement": True,
        "streamlit_retirement_durable_evidence_recipe_ready": durable_evidence_recipe["local_recipe_ready"],
        "streamlit_retirement_durable_evidence_recipe_status": durable_evidence_recipe["status"],
        "streamlit_retirement_durable_evidence_blocker_count": durable_evidence_recipe[
            "production_blocker_count"
        ],
        "streamlit_retirement_durable_evidence_recipe_is_local": True,
        "streamlit_retirement_durable_evidence_recipe_is_not_retirement": True,
        "streamlit_retirement_durable_evidence_requires_replacement_parity": True,
        "streamlit_retirement_readiness_receipt_ready": retirement_readiness_receipt["local_receipt_ready"],
        "streamlit_retirement_readiness_receipt_status": retirement_readiness_receipt["status"],
        "ordinary_entrance_acceptance_audit_ready": True,
        "ordinary_entrance_acceptance_audit_status": ordinary_entrance_acceptance_audit["status"],
        "ordinary_entrance_acceptance_complete": ordinary_entrance_acceptance_audit[
            "ordinary_entrance_acceptance_complete"
        ],
        "legacy_audit_first_round_intake_ready": True,
        "legacy_audit_first_round_intake_status": legacy_audit_first_round_intake["status"],
        "legacy_audit_first_round_intake_row_count": len(
            legacy_audit_first_round_intake_rows
        ),
        "legacy_audit_latest_observation_visible": latest_legacy_audit_observation_status[
            "receipt_found"
        ],
        "legacy_audit_latest_observation_status_text": latest_legacy_audit_observation_status[
            "status"
        ],
        "legacy_audit_latest_observation_direct_user_evidence_recorded": latest_legacy_audit_observation_status[
            "direct_user_evidence_recorded"
        ],
        "legacy_audit_latest_observation_is_not_keep_promotion": True,
        "legacy_audit_latest_observation_is_not_streamlit_retirement": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/legacy/cache 只读展示旧工作台桥接和迁移清单；不会打开 Streamlit 或运行旧工具。",
            "Streamlit 仅保留为 legacy/admin/debug；不是正式主入口，普通主流程迁往 React/Tauri + FastAPI。",
            "Legacy 启动不创建任务、不自动外联、不绕过 strategy guardrails。",
            "本页不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。",
            "streamlit_retirement_durable_evidence_recipe 只是 LTG-10 证据配方；不是 fallback 删除、app.py 删除或普通主流程退出完成。",
            "streamlit_ordinary_workflow_parity_review 只有显式 POST task 后才会出现；它是本地 parity inventory evidence，不是生产退出完成。",
            "streamlit_fallback_retirement_review 只有显式 POST task 后才会出现；它是本地 fallback retirement review evidence，不是 fallback 删除或 production 退场完成。",
            "ordinary_entrance_acceptance_audit 只是三入口 Legacy/UX 审计地图；不是生产验收，也不会创建任务。",
            "legacy_audit_first_round_intake 只是第一轮取证模板；不能升级 KEEP，也不能让旧模块进入普通入口。",
            "legacy_audit_latest_observation_status 只读回放显式 observation dry-run；不会创建任务、升级 KEEP 或退场 Streamlit。",
        ],
    }
    if status == "cache_missing":
        packet["warnings"].append("当前没有旧工作台桥接缓存；3.0 cache 页不会自动扫描旧工具。")
    return _json_safe(packet)
