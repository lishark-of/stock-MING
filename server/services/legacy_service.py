from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from server.services import packet_service


PACKET_KEY = "command_center_3_legacy_bridge_cache"
SCHEMA_VERSION = "legacy_bridge_cache.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_PY_PATH = PROJECT_ROOT / "app.py"
SENSITIVE_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password", "passwd", "credential", "authorization")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")


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
            "GET /api/legacy/cache 只读展示旧工作台桥接和迁移清单；不会打开 Streamlit 或运行旧工具。",
            "Streamlit 仅保留为 legacy/admin/debug；不是正式主入口，普通主流程迁往 React/Tauri + FastAPI。",
            "Legacy 启动不创建任务、不自动外联、不绕过 strategy guardrails。",
            "本页不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。",
        ],
    }
    if status == "cache_missing":
        packet["warnings"].append("当前没有旧工作台桥接缓存；3.0 cache 页不会自动扫描旧工具。")
    return _json_safe(packet)
