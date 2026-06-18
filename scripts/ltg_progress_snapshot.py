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
    runway_by_id = _row_by_id(runway_rows)
    goal_by_id = _row_by_id(goal_rows)

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
        }
        for row in goal_rows
        if isinstance(row, dict)
    ]

    summary = dict(status.get("long_term_goal_summary") or {})
    safety = dict(status.get("api_policy") or {})
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
