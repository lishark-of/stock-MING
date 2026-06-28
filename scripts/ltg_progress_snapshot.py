#!/usr/bin/env python3
"""Print a local Command Center 3 long-term-goal progress snapshot.

This helper is intentionally read-only. It uses the existing migration-status
cache builder so future LTG work can start from a short queue view instead of
re-reading the full roadmap every turn.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import migration_status_service  # noqa: E402


SNAPSHOT_SCHEMA_VERSION = "ltg_progress_snapshot.v1"


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _row_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id") or ""): row for row in rows if isinstance(row, dict)}


def _normalize_ltg_id(value: str) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if text.startswith("LTG-"):
        return text
    if text.isdigit():
        return f"LTG-{int(text):02d}"
    return text


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _compact_handoff_rows(rows: list[Any]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        target_route = row.get("target_route") or row.get("future_route") or ""
        target_task_type = row.get("target_task_type") or row.get("future_task_type") or ""
        preflight_blocking_checks = row.get(
            "supporting_worker_runtime_dependency_preflight_blocking_checks"
        ) or []
        preflight_blocker_count = int(
            row.get("supporting_worker_runtime_dependency_preflight_blocker_count") or 0
        )
        redis_manual_resolution_blockers = row.get(
            "supporting_worker_runtime_dependency_redis_manual_resolution_blockers"
        ) or []
        local_non_redis_runtime_blocking_checks = row.get(
            "supporting_worker_runtime_dependency_local_non_redis_runtime_blocking_checks"
        ) or []
        production_redis_evidence_blockers = row.get(
            "supporting_worker_runtime_dependency_production_redis_evidence_blockers"
        ) or []
        compact.append(
            {
                "target_route": target_route,
                "target_task_type": target_task_type,
                "target_acceptance_mode": row.get("target_acceptance_mode") or "",
                "source_local_phase_key": row.get("source_local_phase_key") or "",
                "source_local_task_id": row.get("source_local_task_id") or "",
                "source_local_receipt_status": row.get("source_local_receipt_status") or "",
                "source_local_receipt_durable_in_sqlite": row.get(
                    "source_local_receipt_durable_in_sqlite"
                )
                is True,
                "source_local_receipt_memory_only": row.get("source_local_receipt_memory_only") is True,
                "handoff_ready_from_local_receipt": row.get("handoff_ready_from_local_receipt") is True,
                "requires_separate_user_approved_provider_task": row.get(
                    "requires_separate_user_approved_provider_task"
                )
                is True,
                "requires_separate_user_approved_worker_task": row.get(
                    "requires_separate_user_approved_worker_task"
                )
                is True,
                "supporting_worker_runtime_dependency_preflight_visible": row.get(
                    "supporting_worker_runtime_dependency_preflight_visible"
                )
                is True,
                "supporting_worker_runtime_dependency_preflight_status": row.get(
                    "supporting_worker_runtime_dependency_preflight_status"
                )
                or "",
                "supporting_worker_runtime_dependency_preflight_blocker_count": preflight_blocker_count,
                "supporting_worker_runtime_dependency_preflight_blocking_checks": preflight_blocking_checks,
                "supporting_worker_runtime_dependency_redis_server_resolution": row.get(
                    "supporting_worker_runtime_dependency_redis_server_resolution"
                )
                or "",
                "supporting_worker_runtime_dependency_redis_url_configured": row.get(
                    "supporting_worker_runtime_dependency_redis_url_configured"
                )
                is True,
                "supporting_worker_runtime_dependency_redis_manual_resolution_required": row.get(
                    "supporting_worker_runtime_dependency_redis_manual_resolution_required"
                )
                is True,
                "supporting_worker_runtime_dependency_redis_manual_resolution_blockers": (
                    redis_manual_resolution_blockers
                ),
                "supporting_worker_runtime_dependency_local_non_redis_runtime_ready": (
                    not local_non_redis_runtime_blocking_checks
                ),
                "supporting_worker_runtime_dependency_local_non_redis_runtime_blocking_checks": (
                    local_non_redis_runtime_blocking_checks
                ),
                "supporting_worker_runtime_dependency_production_redis_evidence_blocked": bool(
                    production_redis_evidence_blockers
                ),
                "supporting_worker_runtime_dependency_production_redis_evidence_blockers": production_redis_evidence_blockers,
                "supporting_worker_runtime_dependency_redis_checked_path_count": int(
                    row.get("supporting_worker_runtime_dependency_redis_checked_path_count") or 0
                ),
                "supporting_worker_runtime_dependency_preflight_blocks_manual_runtime_evidence": (
                    preflight_blocker_count > 0
                ),
                "disabled_reason": row.get("disabled_reason") or "",
                "external_calls_triggered": row.get("external_calls_triggered") is True,
                "tushare_called": row.get("tushare_called") is True,
                "deepseek_called": row.get("deepseek_called") is True,
                "github_called": row.get("github_called") is True,
                "does_not_execute_trades": row.get("does_not_execute_trades") is True,
                "contains_secret": row.get("contains_secret") is True,
                "can_close_goal": row.get("can_close_goal") is True,
                "production_complete": row.get("production_complete") is True,
                "evidence_boundary": row.get("evidence_boundary") or "",
            }
        )
    return compact


def build_snapshot() -> dict[str, Any]:
    status = migration_status_service.build_migration_status()
    goal_rows = _list(status.get("long_term_goal_rows"))
    runway_rows = _list(status.get("ltg_acceptance_runway_rows"))
    action_rows = _list(status.get("ltg_next_acceptance_action_rows"))
    spine_summary = dict(status.get("ltg_strict_closeout_evidence_spine_summary") or {})
    spine_rows = _list(status.get("ltg_strict_closeout_evidence_spine_rows"))
    runway_by_id = _row_by_id(runway_rows)
    goal_by_id = _row_by_id(goal_rows)
    spine_by_id = _row_by_id(spine_rows)

    queue_rows: list[dict[str, Any]] = []
    ready_button_count = 0
    durable_handoff_ready_count = 0
    for action in action_rows:
        if not isinstance(action, dict):
            continue
        ltg_ids = [str(item) for item in _list(action.get("ltg_ids"))]
        linked = [runway_by_id.get(item, {}) for item in ltg_ids]
        linked_goals = [goal_by_id.get(item, {}) for item in ltg_ids]
        ready_for_clean_receipt = action.get("next_local_step_ready_for_clean_receipt") is True
        future_handoff_ready = action.get("future_handoff_ready_from_local_receipt") is True
        if ready_for_clean_receipt:
            ready_button_count += 1
        if future_handoff_ready:
            durable_handoff_ready_count += 1
        handoff_rows = _compact_handoff_rows(_list(action.get("future_handoff_preview_rows")))
        linked_pending_counts = {
            str(row.get("id") or ""): int(row.get("observed_stage_scope_pending_count") or 0)
            for row in linked_goals
            if row
        }
        linked_direct_counts = {
            str(row.get("id") or ""): int(row.get("observed_stage_scope_direct_evidence_count") or 0)
            for row in linked_goals
            if row
        }
        queue_rows.append(
            {
                "queue_id": action.get("queue_id"),
                "ltg_ids": ltg_ids,
                "priority": action.get("priority") or " / ".join(
                    str(row.get("priority") or "") for row in linked if row
                ),
                "completion_estimates": [
                    f"{row.get('id')}:{row.get('completion_estimate')}" for row in linked if row
                ],
                "target_acceptance_mode": action.get("target_acceptance_mode") or "",
                "required_evidence_count": action.get("required_evidence_count"),
                "max_linked_observed_pending": action.get("max_linked_observed_pending"),
                "linked_observed_stage_scope_pending_counts": linked_pending_counts,
                "linked_observed_stage_scope_direct_evidence_counts": linked_direct_counts,
                "next_local_step": action.get("next_local_step"),
                "next_local_step_ready_for_clean_receipt": ready_for_clean_receipt,
                "disabled_reason": action.get("next_local_step_disabled_reason") or "",
                "future_handoff_ready_from_local_receipt": future_handoff_ready,
                "future_provider_route": action.get("future_provider_route") or "",
                "future_handoff_preview_row_count": action.get("future_handoff_preview_row_count"),
                "future_handoff_preview_rows": handoff_rows,
                "first_future_handoff_target_route": handoff_rows[0]["target_route"] if handoff_rows else "",
                "first_future_handoff_target_task_type": (
                    handoff_rows[0]["target_task_type"] if handoff_rows else ""
                ),
                "local_receipt_status": action.get("local_receipt_status"),
                "local_receipt_step_count": action.get("local_receipt_step_count"),
                "missing_local_receipt_step_count": action.get("missing_local_receipt_step_count"),
                "ready_local_receipt_step_count": action.get("ready_local_receipt_step_count"),
                "blocked_local_receipt_step_count": action.get("blocked_local_receipt_step_count"),
                "durable_local_receipt_step_count": action.get("durable_local_receipt_step_count"),
                "memory_only_local_receipt_step_count": action.get("memory_only_local_receipt_step_count"),
                "external_calls_triggered": action.get("external_calls_triggered") is True,
                "tushare_called": action.get("tushare_called") is True,
                "deepseek_called": action.get("deepseek_called") is True,
                "github_called": action.get("github_called") is True,
                "does_not_execute_trades": action.get("does_not_execute_trades") is True,
                "contains_secret": action.get("contains_secret") is True,
                "can_close_goal": action.get("can_close_goal") is True,
            }
        )

    goal_snapshot_rows = [
        {
            "id": row.get("id"),
            "goal": row.get("goal"),
            "bucket": row.get("completion_bucket"),
            "completion_estimate": row.get("completion_estimate"),
            "production_complete": row.get("production_complete") is True,
            "can_close_from_local_contracts": row.get("can_close_from_local_contracts") is True,
            "stage_scope_manifest_status": row.get("stage_scope_manifest_status"),
            "observed_stage_scope_manifest_status": row.get("observed_stage_scope_manifest_status"),
            "observed_stage_scope_row_count": row.get("observed_stage_scope_row_count"),
            "observed_stage_scope_local_evidence_count": row.get("observed_stage_scope_local_evidence_count"),
            "observed_stage_scope_direct_evidence_count": row.get("observed_stage_scope_direct_evidence_count"),
            "observed_stage_scope_direct_evidence_keys": _list(
                row.get("observed_stage_scope_direct_evidence_keys")
            ),
            "observed_stage_scope_pending_count": row.get("observed_stage_scope_pending_count"),
            "observed_stage_scope_can_close_goal": row.get("observed_stage_scope_can_close_goal") is True,
            "next_step": row.get("next_step"),
            "strict_closeout_spine_work_order_visible": spine_by_id.get(
                str(row.get("id") or ""), {}
            ).get("strict_closeout_work_order_visible")
            is True,
            "strict_closeout_spine_next_evidence_action": spine_by_id.get(
                str(row.get("id") or ""), {}
            ).get("next_evidence_action")
            or "",
            "strict_closeout_spine_primary_gate_id": spine_by_id.get(
                str(row.get("id") or ""), {}
            ).get("primary_gate_id")
            or "",
            "strict_closeout_spine_acceptance_queue_id": spine_by_id.get(
                str(row.get("id") or ""), {}
            ).get("acceptance_queue_id")
            or "",
            "strict_closeout_spine_one_ltg_only": spine_by_id.get(
                str(row.get("id") or ""), {}
            ).get("one_ltg_only")
            is True,
            "strict_closeout_spine_can_close_ltg_now": spine_by_id.get(
                str(row.get("id") or ""), {}
            ).get("can_close_ltg_now")
            is True,
        }
        for row in goal_rows
        if isinstance(row, dict)
    ]

    summary = dict(status.get("long_term_goal_summary") or {})
    safety = dict(status.get("api_policy") or {})
    raw_action_by_queue_id = {
        str(row.get("queue_id") or ""): row for row in action_rows if isinstance(row, dict)
    }
    trade_cal_handoff = dict(status.get("ltg01_trade_cal_provider_acceptance_evidence_handoff_summary") or {})
    tushare_target_handoff = dict(status.get("ltg02_tushare_target_sample_evidence_handoff_summary") or {})
    tushare_pipeline_handoff = dict(status.get("ltg02_tushare_full_interface_pipeline_handoff_summary") or {})
    factor_test_action = dict(raw_action_by_queue_id.get("p3_factor_small_pool_provider_validation") or {})
    factor_test_provider_handoff = dict(
        factor_test_action.get("supporting_factor_test_lab_provider_validation_handoff") or {}
    )
    factor_test_production_handoff = dict(
        factor_test_action.get("supporting_factor_test_lab_production_validation_handoff") or {}
    )
    release_split = dict(status.get("release_gate_remote_review_split_summary") or {})
    release_handoff = dict(status.get("ltg11_release_gate_remote_review_handoff_summary") or {})
    trade_handoff = dict(status.get("ltg12_trade_isolation_release_guard_handoff_summary") or {})
    work_order_summary = dict(status.get("ltg_strict_closeout_work_order_summary") or {})
    no_broker_or_broker_call = (
        trade_handoff.get("broker_adapter_connected") is not True
        and trade_handoff.get("broker_called") is not True
        and trade_handoff.get("cache_get_calls_broker") is not True
    )
    no_order_endpoint_or_submission = (
        trade_handoff.get("order_endpoint_present") is not True
        and trade_handoff.get("order_route_present") is not True
        and trade_handoff.get("order_submitted") is not True
        and trade_handoff.get("cache_get_calls_order_endpoint") is not True
    )
    no_trade_execution_api = (
        trade_handoff.get("trade_execution_api_enabled") is not True
        and trade_handoff.get("does_not_execute_trades") is True
    )
    no_action_mutation = (
        trade_handoff.get("model_or_provider_can_modify_action") is not True
        and trade_handoff.get("strategy_action_mutated_by_contract") is not True
        and trade_handoff.get("does_not_modify_strategy_action") is True
    )
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "source_packet_key": status.get("packet_key"),
        "mode": status.get("mode"),
        "loaded_at": status.get("loaded_at"),
        "strict_closeout": summary.get("strict_closeout"),
        "strict_closeout_done_count": summary.get("strict_closeout_done_count"),
        "strict_closeout_total_count": summary.get("strict_closeout_total_count"),
        "strict_closeout_remaining_count": summary.get("strict_closeout_remaining_count"),
        "ready_local_button_count": ready_button_count,
        "durable_handoff_ready_count": durable_handoff_ready_count,
        "evidence_spine": {
            "schema_version": spine_summary.get("schema_version") or "",
            "spine_visible_count": int(spine_summary.get("spine_visible_count") or 0),
            "spine_total_count": int(spine_summary.get("spine_total_count") or 0),
            "strict_closeout_work_order_visible_count": int(
                spine_summary.get("strict_closeout_work_order_visible_count") or 0
            ),
            "strict_closeout_work_order_total_count": int(
                spine_summary.get("strict_closeout_work_order_total_count") or 0
            ),
            "all_rows_have_strict_closeout_work_order": (
                spine_summary.get("all_rows_have_strict_closeout_work_order") is True
            ),
            "all_rows_have_next_evidence_action": (
                spine_summary.get("all_rows_have_next_evidence_action") is True
            ),
            "all_rows_keep_one_ltg_scope": spine_summary.get("all_rows_keep_one_ltg_scope")
            is True,
            "remote_review_state": spine_summary.get(
                "release_gate_current_head_remote_review_state"
            )
            or "",
            "release_gate_current_blocker_count": int(
                spine_summary.get("release_gate_current_blocker_count") or 0
            ),
            "release_gate_current_blockers": _list(
                spine_summary.get("release_gate_current_blockers")
            ),
            "strict_closeout_claim_allowed": (
                spine_summary.get("strict_closeout_claim_allowed") is True
            ),
            "cache_only_readback": spine_summary.get("cache_only_readback") is True,
            "external_calls_triggered": spine_summary.get("external_calls_triggered") is True,
            "tushare_called": spine_summary.get("tushare_called") is True,
            "deepseek_called": spine_summary.get("deepseek_called") is True,
            "github_called": spine_summary.get("github_called") is True,
            "does_not_execute_trades": spine_summary.get("does_not_execute_trades") is True,
            "contains_secret": spine_summary.get("contains_secret") is True,
        },
        "release_gate_remote_review": {
            "schema_version": release_handoff.get("schema_version") or "",
            "status": release_handoff.get("status") or release_split.get("status") or "",
            "current_head_publish_status": release_split.get("current_head_publish_status")
            or release_handoff.get("current_head_publish_status")
            or work_order_summary.get("release_gate_current_head_publish_status")
            or "",
            "current_head_origin_ahead_count": _as_int(
                release_split.get("current_head_origin_ahead_count")
                if release_split.get("current_head_origin_ahead_count") is not None
                else release_handoff.get("current_head_origin_ahead_count")
                if release_handoff.get("current_head_origin_ahead_count") is not None
                else work_order_summary.get("release_gate_current_head_origin_ahead_count")
            ),
            "current_head_push_required_before_remote_review": (
                release_split.get("current_head_push_required_before_remote_review") is True
                or release_handoff.get("current_head_push_required_before_remote_review") is True
                or work_order_summary.get("release_gate_current_head_push_required_before_remote_review")
                is True
            ),
            "remote_review_status": release_split.get("remote_review_status") or "",
            "remote_review_state": work_order_summary.get("release_gate_current_head_remote_review_state")
            or spine_summary.get("release_gate_current_head_remote_review_state")
            or "",
            "remote_actions_status_known": release_split.get("remote_actions_status_known") is True
            or release_handoff.get("remote_actions_status_known") is True
            or work_order_summary.get("release_gate_remote_actions_status_known") is True,
            "latest_remote_run_verified_green": (
                release_split.get("latest_remote_run_verified_green") is True
                or release_handoff.get("latest_remote_run_verified_green") is True
                or work_order_summary.get("release_gate_latest_remote_run_verified_green") is True
            ),
            "remote_ci_green_for_current_head": release_split.get("remote_ci_green_for_current_head")
            is True
            or release_handoff.get("remote_ci_green_for_current_head") is True,
            "remote_ci_review_receipt_status": release_split.get("remote_ci_review_receipt_status")
            or release_handoff.get("remote_ci_review_receipt_status")
            or "",
            "remote_ci_review_receipt_head_matches_current": (
                release_split.get("remote_ci_review_receipt_head_matches_current") is True
                or release_handoff.get("remote_ci_review_receipt_head_matches_current") is True
            ),
            "remote_ci_review_receipt_run_id": str(
                release_split.get("remote_ci_review_receipt_run_id")
                or release_handoff.get("remote_ci_review_receipt_run_id")
                or ""
            ),
            "remote_ci_artifact_digest_pending": (
                release_split.get("remote_ci_artifact_digest_pending") is True
                or release_handoff.get("remote_ci_artifact_digest_pending") is True
            ),
            "requires_current_head_local_gate_recheck": (
                release_handoff.get("requires_current_head_local_gate_recheck") is True
                or release_split.get("remote_ci_green_local_gate_recheck_required") is True
            ),
            "fresh_local_gate_run_observed": (
                release_split.get("fresh_local_gate_run_observed") is True
                or release_handoff.get("fresh_local_gate_run_observed") is True
                or work_order_summary.get("release_gate_fresh_local_gate_run_observed") is True
            ),
            "required_local_gate_checks_present": release_split.get(
                "required_local_gate_checks_present"
            )
            is True,
            "local_worktree_clean": release_split.get("local_worktree_clean") is True
            or release_handoff.get("local_worktree_clean") is True
            or work_order_summary.get("release_gate_worktree_clean") is True,
            "local_worktree_dirty_file_count": _as_int(
                release_split.get("local_worktree_dirty_file_count")
                if release_split.get("local_worktree_dirty_file_count") is not None
                else release_handoff.get("local_worktree_dirty_file_count")
                if release_handoff.get("local_worktree_dirty_file_count") is not None
                else work_order_summary.get("release_gate_worktree_dirty_file_count")
            ),
            "local_worktree_blocks_local_gate_receipt": (
                release_split.get("local_worktree_blocks_local_gate_receipt") is True
                or work_order_summary.get("release_gate_worktree_blocks_fresh_local_gate") is True
            ),
            "local_push_gate_report_reached_clean_worktree_check": (
                release_split.get("local_push_gate_report_reached_clean_worktree_check") is True
                or release_handoff.get("local_push_gate_report_reached_clean_worktree_check") is True
                or work_order_summary.get("release_gate_local_push_gate_report_reached_clean_worktree_check")
                is True
            ),
            "local_push_gate_report_is_not_pass_receipt": work_order_summary.get(
                "release_gate_local_push_gate_report_is_not_pass_receipt"
            )
            is True,
            "release_review_blocked_by_local_gate_recheck": (
                release_split.get("release_review_blocked_by_local_gate_recheck") is True
                or release_handoff.get("release_review_blocked_by_local_gate_recheck") is True
            ),
            "strict_closeout_ready": release_split.get("strict_closeout_ready") is True
            or release_handoff.get("strict_closeout_ready") is True,
            "strict_closeout_claim_allowed": work_order_summary.get(
                "strict_closeout_claim_allowed"
            )
            is True,
            "release_gate_current_blocker_count": int(
                spine_summary.get("release_gate_current_blocker_count")
                or len(_list(work_order_summary.get("release_gate_current_blockers")))
            ),
            "release_gate_current_blockers": _list(
                work_order_summary.get("release_gate_current_blockers")
            )
            or _list(spine_summary.get("release_gate_current_blockers")),
            "next_local_step": release_handoff.get("next_local_step") or "",
            "next_publish_step": release_handoff.get("next_publish_step")
            or release_split.get("next_publish_step")
            or work_order_summary.get("release_gate_next_publish_step")
            or "",
        },
        "trade_cal_provider_acceptance": {
            "schema_version": trade_cal_handoff.get("schema_version") or "",
            "status": trade_cal_handoff.get("status") or "",
            "provider_direct_evidence_layer": trade_cal_handoff.get(
                "provider_direct_evidence_layer"
            )
            or "",
            "provider_direct_evidence_source": trade_cal_handoff.get(
                "provider_direct_evidence_source"
            )
            or "",
            "provider_direct_evidence_status": trade_cal_handoff.get(
                "provider_direct_evidence_status"
            )
            or "",
            "trade_cal_provider_call_ledger_observed_count": _as_int(
                trade_cal_handoff.get("trade_cal_provider_call_ledger_observed_count")
            ),
            "trade_cal_provider_observed_row_count": _as_int(
                trade_cal_handoff.get("trade_cal_provider_observed_row_count")
            ),
            "failure_mode_provider_evidence_done": (
                trade_cal_handoff.get("failure_mode_provider_evidence_done") is True
            ),
            "freshness_replay_provider_evidence_done": (
                trade_cal_handoff.get("freshness_replay_provider_evidence_done") is True
            ),
            "freshness_replay_scenario_count": _as_int(
                trade_cal_handoff.get("freshness_replay_scenario_count")
            ),
            "provider_backed_acceptance_done_by_blocker_audit": (
                trade_cal_handoff.get("provider_backed_acceptance_done_by_blocker_audit")
                is True
            ),
            "provider_backed_acceptance_done_by_durable_recipe": (
                trade_cal_handoff.get("provider_backed_acceptance_done_by_durable_recipe")
                is True
            ),
            "provider_evidence_visible": trade_cal_handoff.get("provider_evidence_visible")
            is True,
            "durable_recipe_ready": trade_cal_handoff.get("durable_recipe_ready") is True,
            "durable_promotion_ready": trade_cal_handoff.get("durable_promotion_ready") is True,
            "latest_dry_run_found": trade_cal_handoff.get("latest_dry_run_found") is True,
            "latest_dry_run_status": trade_cal_handoff.get("latest_dry_run_status") or "",
            "latest_execution_request_found": (
                trade_cal_handoff.get("latest_execution_request_found") is True
            ),
            "latest_execution_request_status": trade_cal_handoff.get(
                "latest_execution_request_status"
            )
            or "",
            "latest_execution_request_ready_for_manual_provider_task_submission": (
                trade_cal_handoff.get(
                    "latest_execution_request_ready_for_manual_provider_task_submission"
                )
                is True
            ),
            "latest_promotion_review_found": (
                trade_cal_handoff.get("latest_promotion_review_found") is True
            ),
            "latest_promotion_review_status": trade_cal_handoff.get(
                "latest_promotion_review_status"
            )
            or "",
            "latest_promotion_review_ready_for_release": (
                trade_cal_handoff.get("latest_promotion_review_ready_for_release") is True
            ),
            "requires_explicit_provider_trade_cal_task": (
                trade_cal_handoff.get("requires_explicit_provider_trade_cal_task") is True
            ),
            "requires_provider_freshness_replay": (
                trade_cal_handoff.get("requires_provider_freshness_replay") is True
            ),
            "requires_promotion_review_task": (
                trade_cal_handoff.get("requires_promotion_review_task") is True
            ),
            "requires_release_review_after_remote_green": (
                trade_cal_handoff.get("requires_release_review_after_remote_green") is True
            ),
            "production_freshness_gate_complete": (
                trade_cal_handoff.get("production_freshness_gate_complete") is True
            ),
            "strict_closeout_ready": trade_cal_handoff.get("strict_closeout_ready") is True,
            "cache_get_calls_provider": trade_cal_handoff.get("cache_get_calls_provider")
            is True,
            "creates_provider_task_from_get": (
                trade_cal_handoff.get("creates_provider_task_from_get") is True
            ),
            "external_calls_triggered": trade_cal_handoff.get("external_calls_triggered")
            is True,
            "tushare_called": trade_cal_handoff.get("tushare_called") is True,
            "does_not_execute_trades": trade_cal_handoff.get("does_not_execute_trades")
            is True,
            "next_local_step": trade_cal_handoff.get("next_local_step") or "",
            "allowed_next_step": trade_cal_handoff.get("allowed_next_step") or "",
            "missing_durable_evidence_item_count": _as_int(
                trade_cal_handoff.get("missing_durable_evidence_item_count")
            ),
            "local_evidence_missing_item_count": _as_int(
                trade_cal_handoff.get("local_evidence_missing_item_count")
            ),
        },
        "tushare_pipeline": {
            "target_sample_schema_version": tushare_target_handoff.get("schema_version") or "",
            "full_interface_schema_version": tushare_pipeline_handoff.get("schema_version") or "",
            "target_sample_status": tushare_target_handoff.get("status") or "",
            "full_interface_status": tushare_pipeline_handoff.get("status") or "",
            "provider_direct_evidence_layer": tushare_target_handoff.get(
                "provider_direct_evidence_layer"
            )
            or "",
            "provider_call_ledger_count": _as_int(
                tushare_target_handoff.get("provider_call_ledger_count")
                if tushare_target_handoff.get("provider_call_ledger_count") is not None
                else tushare_pipeline_handoff.get("provider_call_ledger_count")
            ),
            "provider_call_ledger_visible": (
                tushare_target_handoff.get("provider_call_ledger_visible") is True
                or tushare_pipeline_handoff.get("provider_call_ledger_evidence_done") is True
            ),
            "prior_provider_evidence_observed": (
                tushare_pipeline_handoff.get("prior_provider_evidence_observed") is True
            ),
            "prior_provider_evidence_is_not_new_call": (
                tushare_pipeline_handoff.get("prior_provider_evidence_is_not_new_call")
                is True
            ),
            "durable_recipe_ready": tushare_target_handoff.get("durable_recipe_ready") is True
            or tushare_pipeline_handoff.get("durable_recipe_ready") is True,
            "recipe_visible": tushare_pipeline_handoff.get("recipe_visible") is True,
            "recipe_ready_for_user_confirmation": (
                tushare_pipeline_handoff.get("recipe_ready_for_user_confirmation") is True
            ),
            "execution_recipe_scope_hash_short": tushare_pipeline_handoff.get(
                "execution_recipe_scope_hash_short"
            )
            or "",
            "latest_execution_request_found": (
                tushare_target_handoff.get("latest_execution_request_found") is True
            ),
            "latest_execution_request_status": tushare_target_handoff.get(
                "latest_execution_request_status"
            )
            or "",
            "latest_execution_request_ready_for_manual_provider_task_submission": (
                tushare_target_handoff.get(
                    "latest_execution_request_ready_for_manual_provider_task_submission"
                )
                is True
                or tushare_pipeline_handoff.get(
                    "latest_execution_request_ready_for_manual_provider_task_submission"
                )
                is True
            ),
            "target_sample_acceptance_ready_for_review": (
                tushare_target_handoff.get("target_sample_acceptance_ready_for_review")
                is True
                or tushare_pipeline_handoff.get("target_sample_acceptance_ready_for_review")
                is True
            ),
            "target_sample_acceptance_is_full_interface_acceptance": (
                tushare_target_handoff.get("target_sample_acceptance_is_full_interface_acceptance")
                is True
                or tushare_pipeline_handoff.get(
                    "target_sample_acceptance_is_full_interface_acceptance"
                )
                is True
            ),
            "provider_backed_target_sample_acceptance_done": (
                tushare_target_handoff.get("provider_backed_target_sample_acceptance_done")
                is True
            ),
            "full_interface_selection_done": (
                tushare_target_handoff.get("full_interface_selection_done") is True
                or tushare_pipeline_handoff.get("full_interface_selection_done") is True
            ),
            "full_interface_acceptance_done": (
                tushare_target_handoff.get("full_interface_acceptance_done") is True
                or tushare_pipeline_handoff.get("full_interface_acceptance_done") is True
            ),
            "production_tushare_pipeline_complete": (
                tushare_target_handoff.get("production_tushare_pipeline_complete") is True
                or tushare_pipeline_handoff.get("production_tushare_pipeline_complete") is True
            ),
            "requested_target_count": _as_int(
                tushare_pipeline_handoff.get("requested_target_count")
                if tushare_pipeline_handoff.get("requested_target_count") is not None
                else tushare_target_handoff.get("requested_target_count")
            ),
            "requested_targets": _list(tushare_pipeline_handoff.get("requested_targets"))
            or _list(tushare_target_handoff.get("requested_targets")),
            "requires_full_interface_selection": (
                tushare_target_handoff.get("requires_full_interface_selection") is True
                or tushare_pipeline_handoff.get("requires_full_interface_selection") is True
            ),
            "requires_separate_user_approved_provider_task": (
                tushare_target_handoff.get("requires_separate_user_approved_provider_task")
                is True
                or tushare_pipeline_handoff.get("requires_separate_user_approved_provider_task")
                is True
            ),
            "requires_storage_or_no_storage_promotion_review": (
                tushare_target_handoff.get("requires_storage_or_no_storage_promotion_review")
                is True
                or tushare_pipeline_handoff.get(
                    "requires_storage_or_no_storage_promotion_review"
                )
                is True
            ),
            "requires_release_review_after_remote_green": (
                tushare_target_handoff.get("requires_release_review_after_remote_green")
                is True
                or tushare_pipeline_handoff.get("requires_release_review_after_remote_green")
                is True
            ),
            "cache_get_calls_provider": (
                tushare_target_handoff.get("cache_get_calls_provider") is True
                or tushare_pipeline_handoff.get("cache_get_calls_provider") is True
                or tushare_pipeline_handoff.get("cache_get_calls_tushare") is True
            ),
            "creates_provider_task_from_get": (
                tushare_target_handoff.get("creates_provider_task_from_get") is True
                or tushare_pipeline_handoff.get("creates_provider_task_from_get") is True
            ),
            "external_calls_triggered": (
                tushare_target_handoff.get("external_calls_triggered") is True
                or tushare_pipeline_handoff.get("external_calls_triggered") is True
            ),
            "tushare_called": tushare_target_handoff.get("tushare_called") is True
            or tushare_pipeline_handoff.get("tushare_called") is True,
            "does_not_execute_trades": (
                tushare_target_handoff.get("does_not_execute_trades") is True
                or tushare_pipeline_handoff.get("does_not_execute_trades") is True
            ),
            "next_local_step": tushare_target_handoff.get("next_local_step")
            or tushare_pipeline_handoff.get("next_local_step")
            or "",
        },
        "factor_test_lab": {
            "provider_schema_version": factor_test_provider_handoff.get("schema_version") or "",
            "production_schema_version": factor_test_production_handoff.get("schema_version") or "",
            "provider_status": factor_test_provider_handoff.get("status") or "",
            "production_status": factor_test_production_handoff.get("status") or "",
            "direct_evidence_layer": factor_test_provider_handoff.get("direct_evidence_layer") or "",
            "direct_evidence_status": factor_test_provider_handoff.get("direct_evidence_status") or "",
            "provider_small_pool_scope_ticket_verified": (
                factor_test_provider_handoff.get("provider_small_pool_scope_ticket_verified") is True
                or factor_test_production_handoff.get("provider_small_pool_scope_ticket_verified") is True
            ),
            "provider_small_pool_scope_hash_short": factor_test_provider_handoff.get(
                "provider_small_pool_scope_hash_short"
            )
            or factor_test_production_handoff.get("provider_small_pool_scope_hash_short")
            or "",
            "provider_small_pool_dry_run_ready": (
                factor_test_provider_handoff.get("provider_small_pool_dry_run_ready") is True
                or factor_test_production_handoff.get("provider_small_pool_dry_run_ready") is True
            ),
            "provider_small_pool_execution_recipe_ready": (
                factor_test_provider_handoff.get("provider_small_pool_execution_recipe_ready") is True
                or factor_test_production_handoff.get("provider_small_pool_execution_recipe_ready") is True
            ),
            "provider_small_pool_execution_request_ready": (
                factor_test_provider_handoff.get("provider_small_pool_execution_request_ready") is True
                or factor_test_production_handoff.get("provider_small_pool_execution_request_ready") is True
            ),
            "ready_for_explicit_provider_small_pool_task": (
                factor_test_provider_handoff.get("ready_for_explicit_provider_small_pool_task") is True
            ),
            "provider_task_created": (
                factor_test_provider_handoff.get("provider_task_created") is True
                or factor_test_production_handoff.get("provider_task_created") is True
            ),
            "provider_backed_small_pool_validation_done": (
                factor_test_provider_handoff.get("provider_backed_small_pool_validation_done") is True
                or factor_test_production_handoff.get("provider_backed_small_pool_validation_done") is True
            ),
            "provider_call_ledger_evidence_done": (
                factor_test_provider_handoff.get("provider_call_ledger_evidence_done") is True
                or factor_test_production_handoff.get("provider_call_ledger_evidence_done") is True
            ),
            "sample_rows_collected": (
                factor_test_provider_handoff.get("sample_rows_collected") is True
                or factor_test_production_handoff.get("sample_rows_collected") is True
            ),
            "multi_horizon_forward_returns_done": (
                factor_test_provider_handoff.get("multi_horizon_forward_returns_done") is True
                or factor_test_production_handoff.get("multi_horizon_forward_returns_done") is True
            ),
            "rolling_window_validation_done": (
                factor_test_provider_handoff.get("rolling_window_validation_done") is True
                or factor_test_production_handoff.get("rolling_window_validation_done") is True
            ),
            "cost_assumption_validation_done": (
                factor_test_provider_handoff.get("cost_assumption_validation_done") is True
                or factor_test_production_handoff.get("cost_assumption_validation_done") is True
            ),
            "neutralization_stability_done": (
                factor_test_provider_handoff.get("neutralization_stability_done") is True
                or factor_test_production_handoff.get("neutralization_stability_done") is True
            ),
            "pit_bias_controls_done": (
                factor_test_provider_handoff.get("pit_bias_controls_done") is True
                or factor_test_production_handoff.get("pit_bias_controls_done") is True
            ),
            "full_market_validation_done": (
                factor_test_provider_handoff.get("full_market_validation_done") is True
                or factor_test_production_handoff.get("full_market_validation_done") is True
            ),
            "production_validation_qa_ready": (
                factor_test_production_handoff.get("production_validation_qa_ready") is True
            ),
            "durable_recipe_ready": (
                factor_test_provider_handoff.get("durable_recipe_ready") is True
                or factor_test_production_handoff.get("durable_recipe_ready") is True
            ),
            "durable_promotion_ready": (
                factor_test_provider_handoff.get("durable_promotion_ready") is True
                or factor_test_production_handoff.get("durable_promotion_ready") is True
            ),
            "production_factor_test_validation_complete": (
                factor_test_provider_handoff.get("production_factor_test_validation_complete") is True
                or factor_test_production_handoff.get("production_factor_test_validation_complete") is True
            ),
            "requires_provider_call_ledger": (
                factor_test_provider_handoff.get("requires_provider_call_ledger") is True
                or factor_test_production_handoff.get("requires_provider_call_ledger") is True
            ),
            "requires_full_market_boundary_review": (
                factor_test_provider_handoff.get("requires_full_market_boundary_review") is True
                or factor_test_production_handoff.get("requires_full_market_boundary_review") is True
            ),
            "requires_release_review_after_remote_green": (
                factor_test_provider_handoff.get("requires_release_review_after_remote_green") is True
                or factor_test_production_handoff.get("requires_release_review_after_remote_green") is True
            ),
            "cache_get_calls_provider": (
                factor_test_provider_handoff.get("cache_get_calls_provider") is True
                or factor_test_production_handoff.get("cache_get_calls_provider") is True
            ),
            "creates_provider_task_from_get": (
                factor_test_provider_handoff.get("creates_provider_task_from_get") is True
                or factor_test_production_handoff.get("creates_provider_task_from_get") is True
            ),
            "external_calls_triggered": (
                factor_test_provider_handoff.get("external_calls_triggered") is True
                or factor_test_production_handoff.get("external_calls_triggered") is True
            ),
            "tushare_called": factor_test_provider_handoff.get("tushare_called") is True
            or factor_test_production_handoff.get("tushare_called") is True,
            "does_not_execute_trades": (
                factor_test_provider_handoff.get("does_not_execute_trades") is True
                or factor_test_production_handoff.get("does_not_execute_trades") is True
            ),
            "next_local_step": factor_test_action.get("next_local_step")
            or factor_test_provider_handoff.get("next_local_step")
            or factor_test_production_handoff.get("next_local_step")
            or "",
            "provider_next_local_step": factor_test_provider_handoff.get("next_local_step")
            or factor_test_production_handoff.get("next_local_step")
            or "",
        },
        "trade_isolation_release_guard": {
            "schema_version": trade_handoff.get("schema_version") or "",
            "trade_isolation_release_receipt_status": trade_handoff.get(
                "trade_isolation_release_receipt_status"
            )
            or "",
            "trade_isolation_release_receipt_ready": (
                trade_handoff.get("trade_isolation_release_receipt_ready") is True
            ),
            "current_slice_trade_isolation_recheck_ready": (
                trade_handoff.get("current_slice_trade_isolation_recheck_ready") is True
            ),
            "current_slice_no_broker_no_order_no_action_proof_ready": (
                trade_handoff.get("current_slice_no_broker_no_order_no_action_proof_ready")
                is True
            ),
            "no_broker_or_broker_call": no_broker_or_broker_call,
            "no_order_endpoint_or_submission": no_order_endpoint_or_submission,
            "no_trade_execution_api": no_trade_execution_api,
            "no_action_mutation": no_action_mutation,
            "real_trading_connected": trade_handoff.get("real_trading_connected") is True,
            "broker_adapter_connected": trade_handoff.get("broker_adapter_connected") is True,
            "broker_called": trade_handoff.get("broker_called") is True,
            "order_endpoint_present": trade_handoff.get("order_endpoint_present") is True,
            "order_route_present": trade_handoff.get("order_route_present") is True,
            "order_submitted": trade_handoff.get("order_submitted") is True,
            "trade_execution_api_enabled": trade_handoff.get("trade_execution_api_enabled")
            is True,
            "frontend_trade_controls_present": (
                trade_handoff.get("frontend_trade_controls_present") is True
            ),
            "model_or_provider_can_modify_action": (
                trade_handoff.get("model_or_provider_can_modify_action") is True
            ),
            "strategy_action_mutated_by_contract": (
                trade_handoff.get("strategy_action_mutated_by_contract") is True
            ),
            "release_receipt_is_trading_approval": (
                trade_handoff.get("release_receipt_is_trading_approval") is True
            ),
            "ready_for_real_trading_integration": (
                trade_handoff.get("ready_for_real_trading_integration") is True
            ),
            "future_real_trading_requires_separate_project": (
                trade_handoff.get("future_real_trading_requires_separate_project") is True
            ),
            "per_slice_trade_isolation_recheck_required": (
                trade_handoff.get("per_slice_trade_isolation_recheck_required") is True
            ),
            "cache_get_calls_model": trade_handoff.get("cache_get_calls_model") is True,
            "cache_get_calls_broker": trade_handoff.get("cache_get_calls_broker") is True,
            "cache_get_calls_order_endpoint": (
                trade_handoff.get("cache_get_calls_order_endpoint") is True
            ),
            "does_not_execute_trades": trade_handoff.get("does_not_execute_trades") is True,
            "does_not_modify_strategy_action": (
                trade_handoff.get("does_not_modify_strategy_action") is True
            ),
            "next_local_step": trade_handoff.get("next_local_step") or "",
        },
        "goal_rows": goal_snapshot_rows,
        "queue_rows": queue_rows,
        "safety": {
            "cache_only": safety.get("cache_only") is True,
            "external_calls_triggered": safety.get("external_calls_triggered") is True,
            "tushare_called": safety.get("tushare_called") is True,
            "deepseek_called": safety.get("deepseek_called") is True,
            "github_called": safety.get("github_called") is True,
            "does_not_execute_trades": safety.get("does_not_execute_trades") is True,
            "contains_secret": safety.get("contains_secret") is True,
        },
    }


def filter_snapshot(snapshot: dict[str, Any], focus_ltg_ids: set[str]) -> dict[str, Any]:
    focus = {item for item in (_normalize_ltg_id(value) for value in focus_ltg_ids) if item}
    if not focus:
        snapshot["focus_ltg_ids"] = []
        snapshot["focus_goal_count"] = len(_list(snapshot.get("goal_rows")))
        snapshot["focus_queue_count"] = len(_list(snapshot.get("queue_rows")))
        return snapshot

    goal_rows = [
        row
        for row in _list(snapshot.get("goal_rows"))
        if isinstance(row, dict) and str(row.get("id") or "") in focus
    ]
    queue_rows = [
        row
        for row in _list(snapshot.get("queue_rows"))
        if isinstance(row, dict) and focus.intersection({str(item) for item in _list(row.get("ltg_ids"))})
    ]
    filtered = dict(snapshot)
    filtered["focus_ltg_ids"] = sorted(focus)
    filtered["focus_goal_count"] = len(goal_rows)
    filtered["focus_queue_count"] = len(queue_rows)
    filtered["ready_local_button_count"] = sum(
        1 for row in queue_rows if isinstance(row, dict) and row.get("next_local_step_ready_for_clean_receipt") is True
    )
    filtered["durable_handoff_ready_count"] = sum(
        1 for row in queue_rows if isinstance(row, dict) and row.get("future_handoff_ready_from_local_receipt") is True
    )
    filtered["goal_rows"] = goal_rows
    filtered["queue_rows"] = queue_rows
    return filtered


def _print_text(snapshot: dict[str, Any]) -> None:
    print(
        "LTG snapshot:"
        f" strict_closeout={snapshot['strict_closeout']}"
        f" ready_local_buttons={snapshot['ready_local_button_count']}"
        f" durable_handoffs={snapshot['durable_handoff_ready_count']}"
    )
    focus_ltg_ids = snapshot.get("focus_ltg_ids") or []
    if focus_ltg_ids:
        print(f"Focus: {','.join(str(item) for item in focus_ltg_ids)}")
    safety = snapshot["safety"]
    print(
        "Safety:"
        f" cache_only={safety['cache_only']}"
        f" external_calls={safety['external_calls_triggered']}"
        f" tushare={safety['tushare_called']}"
        f" deepseek={safety['deepseek_called']}"
        f" github={safety['github_called']}"
        f" trades={not safety['does_not_execute_trades']}"
        f" secrets={safety['contains_secret']}"
    )
    evidence_spine = snapshot["evidence_spine"]
    print(
        "Spine:"
        f" rows={evidence_spine['spine_visible_count']}/{evidence_spine['spine_total_count']}"
        f" work_orders={evidence_spine['strict_closeout_work_order_visible_count']}/"
        f"{evidence_spine['strict_closeout_work_order_total_count']}"
        f" next_evidence={evidence_spine['all_rows_have_next_evidence_action']}"
        f" remote_state={evidence_spine['remote_review_state']}"
        f" blockers={evidence_spine['release_gate_current_blocker_count']}"
    )
    release_gate = snapshot["release_gate_remote_review"]
    print(
        "Release gate:"
        f" publish_status={release_gate['current_head_publish_status']}"
        f" origin_ahead={release_gate['current_head_origin_ahead_count']}"
        f" push_required={release_gate['current_head_push_required_before_remote_review']}"
        f" remote_status={release_gate['remote_review_status']}"
        f" remote_green={release_gate['remote_ci_green_for_current_head']}"
        f" local_recheck={release_gate['requires_current_head_local_gate_recheck']}"
        f" dirty_files={release_gate['local_worktree_dirty_file_count']}"
        f" blockers={release_gate['release_gate_current_blocker_count']}"
        f" next_local={release_gate['next_local_step']}"
        f" next_publish={release_gate['next_publish_step']}"
    )
    trade_cal = snapshot["trade_cal_provider_acceptance"]
    print(
        "Trade cal acceptance:"
        f" status={trade_cal['status']}"
        f" direct_provider={trade_cal['provider_direct_evidence_status']}"
        f" ledger={trade_cal['trade_cal_provider_call_ledger_observed_count']}"
        f" rows={trade_cal['trade_cal_provider_observed_row_count']}"
        f" failure_mode={trade_cal['failure_mode_provider_evidence_done']}"
        f" replay={trade_cal['freshness_replay_provider_evidence_done']}"
        f" provider_backed={trade_cal['provider_backed_acceptance_done_by_durable_recipe']}"
        f" dry_run={trade_cal['latest_dry_run_found']}"
        f" execution_request={trade_cal['latest_execution_request_found']}"
        f" promotion={trade_cal['latest_promotion_review_ready_for_release']}"
        f" cache_provider={trade_cal['cache_get_calls_provider']}"
        f" tushare_called={trade_cal['tushare_called']}"
        f" next={trade_cal['next_local_step']}"
    )
    tushare_pipeline = snapshot["tushare_pipeline"]
    print(
        "Tushare pipeline:"
        f" target_status={tushare_pipeline['target_sample_status']}"
        f" recipe_ready={tushare_pipeline['recipe_ready_for_user_confirmation']}"
        f" provider_ledger={tushare_pipeline['provider_call_ledger_count']}"
        f" prior_provider={tushare_pipeline['prior_provider_evidence_observed']}"
        f" target_request={tushare_pipeline['latest_execution_request_found']}"
        f" target_review={tushare_pipeline['target_sample_acceptance_ready_for_review']}"
        f" full_selection={tushare_pipeline['full_interface_selection_done']}"
        f" full_acceptance={tushare_pipeline['full_interface_acceptance_done']}"
        f" production_complete={tushare_pipeline['production_tushare_pipeline_complete']}"
        f" cache_provider={tushare_pipeline['cache_get_calls_provider']}"
        f" tushare_called={tushare_pipeline['tushare_called']}"
        f" next={tushare_pipeline['next_local_step']}"
    )
    factor_test = snapshot["factor_test_lab"]
    print(
        "Factor test lab:"
        f" provider_status={factor_test['provider_status']}"
        f" scope_ticket={factor_test['provider_small_pool_scope_ticket_verified']}"
        f" dry_run={factor_test['provider_small_pool_dry_run_ready']}"
        f" execution_request={factor_test['provider_small_pool_execution_request_ready']}"
        f" provider_task={factor_test['provider_task_created']}"
        f" provider_backed={factor_test['provider_backed_small_pool_validation_done']}"
        f" sample_rows={factor_test['sample_rows_collected']}"
        f" rolling_validation={factor_test['rolling_window_validation_done']}"
        f" cost={factor_test['cost_assumption_validation_done']}"
        f" full_market={factor_test['full_market_validation_done']}"
        f" production_complete={factor_test['production_factor_test_validation_complete']}"
        f" cache_provider={factor_test['cache_get_calls_provider']}"
        f" next={factor_test['next_local_step']}"
    )
    trade_guard = snapshot["trade_isolation_release_guard"]
    print(
        "Trade isolation:"
        f" receipt={trade_guard['trade_isolation_release_receipt_status']}"
        f" recheck_ready={trade_guard['current_slice_trade_isolation_recheck_ready']}"
        f" no_broker={trade_guard['no_broker_or_broker_call']}"
        f" no_order_endpoint={trade_guard['no_order_endpoint_or_submission']}"
        f" no_trade_api={trade_guard['no_trade_execution_api']}"
        f" no_action_mutation={trade_guard['no_action_mutation']}"
        f" separate_project={trade_guard['future_real_trading_requires_separate_project']}"
        f" ready_for_real_trading={trade_guard['ready_for_real_trading_integration']}"
        f" next={trade_guard['next_local_step']}"
    )
    print()
    print("Goals:")
    for row in snapshot["goal_rows"]:
        print(
            f"- {row['id']} {row['completion_estimate']} {row['bucket']}: "
            f"production_complete={row['production_complete']} "
            f"direct_evidence={row.get('observed_stage_scope_direct_evidence_count')} "
            f"pending_stage_rows={row.get('observed_stage_scope_pending_count')}"
        )
    print()
    print("Next local queue:")
    for row in snapshot["queue_rows"]:
        ready = "ready" if row["next_local_step_ready_for_clean_receipt"] else "blocked"
        reason = f" ({row['disabled_reason']})" if row["disabled_reason"] else ""
        ltg_ids = ",".join(row["ltg_ids"])
        handoff = (
            f" handoff={row['first_future_handoff_target_route']}"
            if row.get("first_future_handoff_target_route")
            else ""
        )
        print(
            f"- {row['queue_id']} [{ltg_ids}] {ready}{reason}: "
            f"{row['next_local_step']}{handoff}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Print the local 14-LTG progress snapshot.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--ltg",
        action="append",
        default=[],
        help="Limit goal_rows and queue_rows to one LTG id, e.g. LTG-13 or 13. May be repeated.",
    )
    args = parser.parse_args()
    snapshot = filter_snapshot(build_snapshot(), set(args.ltg))
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text(snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
