#!/usr/bin/env python3
"""Validate the local LTG-06 Worker production-boundary contract.

This push-gate guard is not a worker healthcheck. It reads local worker cache
contracts to keep dispatch plans, blocker audits, healthcheck QA, activation
review, scheduler boundaries, and local fallback separate from production
Celery/Redis worker completion.
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

from server.services import task_service, worker_service  # noqa: E402


REQUIRED_BLOCKER_CRITERIA = {
    "celery_worker_started",
    "dispatch_queue_contract_complete",
    "external_tasks_button_gated",
    "external_tasks_call_ledger_required",
    "scheduler_default_off",
    "cache_get_never_dispatches_external_work",
    "retry_cancel_lock_dedupe_local_only",
    "no_real_trade_or_action_mutation",
}
REQUIRED_HEALTHCHECK_CRITERIA = {
    "celery_worker_process_visible",
    "redis_broker_reachable",
    "task_round_trip_healthcheck",
    "cancel_retry_cross_process",
    "scheduler_default_off_verified",
    "provider_model_tasks_not_autoscheduled",
    "task_log_persistence_verified",
    "external_call_boundary",
    "secret_redaction_boundary",
}
REQUIRED_ACTIVATION_STEPS = {
    "review_production_blockers",
    "review_redis_broker_configuration",
    "review_celery_manual_start",
    "review_synthetic_healthcheck",
    "review_cross_process_task_controls",
    "review_task_log_persistence",
    "review_scheduler_default_off",
    "review_provider_model_isolation",
    "review_local_fallback_rollback",
    "review_secret_redaction",
}
REQUIRED_TASK_LOG_CRITERIA = {
    "local_task_status_index_visible",
    "memory_sqlite_fallback_visible",
    "safe_task_log_fields_visible",
    "task_log_payload_redaction_boundary",
    "task_log_external_boundary",
    "append_only_worker_log_storage_verified",
    "cross_process_task_log_round_trip_verified",
}


def _row(criterion: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "evidence": evidence,
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _flag_false(contract: dict[str, Any], *keys: str) -> bool:
    return all(contract.get(key) is False for key in keys)


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def build_contract() -> dict[str, Any]:
    packet = worker_service.read_worker_runtime_cache()
    catalog = task_service.build_task_catalog()
    runtime = _dict(packet.get("runtime"))
    policy = _dict(packet.get("policy"))
    task_summary = _dict(packet.get("task_catalog_summary"))
    dispatch_summary = _dict(packet.get("dispatch_plan_summary"))
    dispatch_rows = [row for row in _list(packet.get("dispatch_plan_rows")) if isinstance(row, dict)]
    blocker_audit = _dict(packet.get("worker_production_blocker_audit"))
    blocker_rows = [row for row in _list(packet.get("worker_production_blocker_rows")) if isinstance(row, dict)]
    blocker_criteria = {str(row.get("criterion") or "") for row in blocker_rows}
    healthcheck = _dict(packet.get("worker_healthcheck_qa_contract"))
    healthcheck_rows = [row for row in _list(packet.get("worker_healthcheck_qa_rows")) if isinstance(row, dict)]
    healthcheck_criteria = {str(row.get("criterion") or "") for row in healthcheck_rows}
    activation = _dict(packet.get("worker_activation_review_contract"))
    activation_rows = [row for row in _list(packet.get("worker_activation_review_rows")) if isinstance(row, dict)]
    activation_steps = {str(row.get("review_step") or "") for row in activation_rows}
    task_log_audit = _dict(packet.get("worker_task_log_persistence_audit"))
    task_log_rows = [row for row in _list(packet.get("worker_task_log_persistence_rows")) if isinstance(row, dict)]
    task_log_criteria = {str(row.get("criterion") or "") for row in task_log_rows}
    synthetic_healthcheck = _dict(packet.get("worker_synthetic_healthcheck"))
    task_persistence = _dict(packet.get("task_persistence"))
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/worker_contract.py")

    rows = [
        _row(
            "worker_cache_is_diagnostic_only",
            packet.get("schema_version") == "worker_runtime_cache.v1"
            and packet.get("mode") == "cache_only"
            and packet.get("cache_only") is True
            and packet.get("read_only") is True
            and policy.get("worker_runtime_is_diagnostic_only") is True
            and policy.get("post_task_required_for_work") is True
            and policy.get("does_not_ping_redis") is True
            and policy.get("does_not_start_celery_worker") is True
            and policy.get("does_not_start_scheduler") is True
            and policy.get("does_not_schedule_real_tasks") is True
            and _flag_false(packet, "external_calls_triggered", "redis_pinged", "tushare_called", "deepseek_called", "github_called")
            and packet.get("does_not_execute_trades") is True
            and packet.get("does_not_modify_strategy_action") is True,
            "GET worker cache must remain read-only diagnostics and must not start workers, ping Redis, schedule tasks, or call providers/models.",
        ),
        _row(
            "runtime_does_not_start_processes",
            runtime.get("local_fallback_enabled") is True
            and runtime.get("sqlite_task_metadata_enabled") is True
            and runtime.get("redis_url_exposed") is False
            and runtime.get("celery_worker_started") is False
            and runtime.get("scheduler_started") is False
            and runtime.get("redis_pinged") is False,
            "Runtime metadata may reveal dependency availability, but process start, scheduler start, Redis ping, and URL exposure must stay false.",
        ),
        _row(
            "task_catalog_boundary_is_button_gated",
            task_summary.get("task_count") == catalog.get("task_count")
            and task_summary.get("all_tasks_button_gated") is True
            and task_summary.get("call_ledger_required_for_all") is True
            and task_summary.get("supports_local_task_cancel") is True
            and _dict(catalog.get("policy")).get("all_tasks_button_gated") is True
            and _dict(catalog.get("policy")).get("call_ledger_required_for_all") is True,
            "Task catalog must keep work behind explicit POST/task buttons with call ledger and local cancel support.",
        ),
        _row(
            "dispatch_plan_is_local_fallback_no_auto_scheduler",
            len(dispatch_rows) == int(catalog.get("task_count") or 0)
            and dispatch_summary.get("task_count") == len(dispatch_rows)
            and dispatch_summary.get("cache_get_external_call_count") == 0
            and dispatch_summary.get("scheduler_auto_task_count") == 0
            and dispatch_summary.get("redis_pinged") is False
            and dispatch_summary.get("celery_started") is False
            and dispatch_summary.get("external_calls_triggered") is False
            and dispatch_summary.get("does_not_execute_trades") is True
            and dispatch_summary.get("does_not_modify_strategy_action") is True
            and all(row.get("future_queue") for row in dispatch_rows)
            and all(row.get("local_fallback_supported") is True for row in dispatch_rows)
            and all(row.get("button_gated") is True for row in dispatch_rows)
            and all(row.get("automatic_scheduler_allowed") is False for row in dispatch_rows)
            and all(row.get("cache_get_external_calls") is False for row in dispatch_rows)
            and all(row.get("external_calls_triggered") is False for row in dispatch_rows)
            and all(row.get("does_not_execute_trades") is True for row in dispatch_rows)
            and all(row.get("does_not_modify_strategy_action") is True for row in dispatch_rows),
            "Dispatch plan must expose future queues and local fallback without cache GET external work or automatic scheduler dispatch.",
        ),
        _row(
            "production_blocker_audit_keeps_worker_blocked",
            blocker_audit.get("schema_version") == "worker_production_blocker_audit.v1"
            and blocker_audit.get("status") == "production_worker_blocked"
            and blocker_audit.get("production_worker_complete") is False
            and int(blocker_audit.get("blocking_criterion_count") or 0) > 0
            and REQUIRED_BLOCKER_CRITERIA.issubset(blocker_criteria)
            and blocker_audit.get("cache_api_started_workers") is False
            and blocker_audit.get("cache_api_pinged_redis") is False
            and blocker_audit.get("cache_api_started_scheduler") is False
            and blocker_audit.get("cache_get_external_calls") is False
            and _flag_false(blocker_audit, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and blocker_audit.get("does_not_execute_trades") is True
            and blocker_audit.get("does_not_modify_strategy_action") is True,
            "Worker production blocker audit must keep process start, Redis broker proof, stub migration, scheduler, and cache GET boundaries visible.",
        ),
        _row(
            "healthcheck_contract_is_execution_pending",
            healthcheck.get("schema_version") == "worker_healthcheck_qa_contract.v1"
            and healthcheck.get("status") == "worker_healthcheck_qa_contract_ready_execution_pending"
            and healthcheck.get("scope") == "local_static_healthcheck_contract_no_process_start"
            and healthcheck.get("production_worker_complete") is False
            and healthcheck.get("healthcheck_executed") is False
            and healthcheck.get("healthcheck_task_dispatched") is False
            and healthcheck.get("synthetic_task_only") is True
            and healthcheck.get("provider_model_task_validation_in_scope") is False
            and healthcheck.get("future_healthcheck_required") is True
            and int(healthcheck.get("pending_criterion_count") or 0) > 0
            and REQUIRED_HEALTHCHECK_CRITERIA.issubset(healthcheck_criteria)
            and healthcheck.get("cache_api_started_workers") is False
            and healthcheck.get("cache_api_pinged_redis") is False
            and healthcheck.get("cache_api_started_scheduler") is False
            and healthcheck.get("cache_get_external_calls") is False
            and _flag_false(healthcheck, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and healthcheck.get("contains_secret") is False,
            "Worker healthcheck QA must remain a local static contract until a future synthetic healthcheck is explicitly run.",
        ),
        _row(
            "activation_review_keeps_manual_activation_pending",
            activation.get("schema_version") == "worker_activation_review_contract.v1"
            and activation.get("status") == "worker_activation_review_ready_activation_pending"
            and activation.get("scope") == "manual_worker_activation_review_no_process_start"
            and activation.get("activation_ready") is False
            and activation.get("production_worker_complete") is False
            and activation.get("manual_activation_required") is True
            and activation.get("healthcheck_required_before_activation") is True
            and activation.get("healthcheck_executed") is False
            and REQUIRED_ACTIVATION_STEPS.issubset(activation_steps)
            and activation.get("worker_started_by_cache_api") is False
            and activation.get("redis_pinged_by_cache_api") is False
            and activation.get("scheduler_started_by_cache_api") is False
            and activation.get("task_dispatched_by_cache_api") is False
            and activation.get("cache_get_external_calls") is False
            and _flag_false(activation, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and activation.get("contains_secret") is False,
            "Worker activation review must stay manual and pending until blockers are resolved and an explicit synthetic healthcheck proves readiness.",
        ),
        _row(
            "task_persistence_is_local_control_plane",
            task_persistence.get("sqlite_fallback_enabled") is not False
            and task_persistence.get("external_calls_triggered") in {False, None}
            and int(task_persistence.get("lock_conflict_audit_count") or 0) >= 0
            and int(task_persistence.get("dedupe_duplicate_audit_count") or 0) >= 0,
            "Task persistence can support local fallback, lock, dedupe, retry, cancel, and logs, but it is not cross-process worker proof.",
        ),
        _row(
            "task_log_persistence_audit_is_local_and_pending",
            task_log_audit.get("schema_version") == "worker_task_log_persistence_audit.v1"
            and task_log_audit.get("status") == "local_task_log_persistence_ready_worker_append_only_pending"
            and task_log_audit.get("scope") == "local_task_log_persistence_audit_no_process_start"
            and task_log_audit.get("mode") == "cache_only_read_only_task_log_audit"
            and REQUIRED_TASK_LOG_CRITERIA.issubset(task_log_criteria)
            and task_log_audit.get("local_task_log_persistence_ready") is True
            and task_log_audit.get("task_log_persistence_verified") is False
            and task_log_audit.get("append_only_worker_log_verified") is False
            and task_log_audit.get("cross_process_log_round_trip_verified") is False
            and task_log_audit.get("healthcheck_executed") is False
            and task_log_audit.get("production_worker_complete") is False
            and task_log_audit.get("cache_get_reads_raw_payload") is False
            and task_log_audit.get("cache_get_writes_logs") is False
            and task_log_audit.get("cache_api_started_workers") is False
            and task_log_audit.get("cache_api_pinged_redis") is False
            and task_log_audit.get("task_dispatched_by_cache_api") is False
            and task_log_audit.get("contains_secret") is False
            and _flag_false(task_log_audit, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and task_log_audit.get("does_not_execute_trades") is True
            and task_log_audit.get("does_not_modify_strategy_action") is True,
            "Worker task-log persistence audit must prove only local safe log visibility and keep append-only/cross-process worker log proof pending.",
        ),
        _row(
            "synthetic_healthcheck_is_explicit_post_only",
            "POST /api/worker/synthetic-healthcheck" in _dict(catalog.get("route_coverage")).get("known_post_routes", [])
            and _dict(catalog.get("policy")).get("all_known_post_routes_button_gated") is True
            and synthetic_healthcheck.get("schema_version") == "worker_synthetic_healthcheck.v1"
            and synthetic_healthcheck.get("scope") == "explicit_post_worker_synthetic_healthcheck_no_process_start"
            and synthetic_healthcheck.get("cache_get_external_calls") is False
            and synthetic_healthcheck.get("celery_worker_started") is False
            and synthetic_healthcheck.get("redis_pinged") is False
            and synthetic_healthcheck.get("scheduler_started") is False
            and synthetic_healthcheck.get("production_worker_complete") is False
            and synthetic_healthcheck.get("activation_ready") is False
            and _flag_false(synthetic_healthcheck, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and synthetic_healthcheck.get("does_not_execute_trades") is True
            and synthetic_healthcheck.get("does_not_modify_strategy_action") is True
            and policy.get("worker_synthetic_healthcheck_requires_explicit_post") is True
            and policy.get("cache_get_executes_synthetic_healthcheck") is False
            and policy.get("worker_synthetic_healthcheck_is_not_production_complete") is True,
            "Worker synthetic healthcheck must be a button-gated POST route; GET cache may read the last result but must not execute it or claim production completion.",
        ),
        _row(
            "push_gate_runs_worker_contract_after_storage",
            "scripts/worker_contract.py" in push_gate_script
            and "Worker contract" in push_gate_script
            and "worker_contract: passed_local_contract_worker_activation_pending" in push_gate_script
            and push_gate_script.find('run_step "Storage contract"') < push_gate_script.find('run_step "Worker contract"')
            and push_gate_script.find('run_step "Worker contract"') < push_gate_script.find('run_step "Motion viewport QA contract"'),
            "Push gate must run LTG-06 worker contract after Storage and before motion/static QA.",
        ),
        _row(
            "script_is_local_no_process_or_provider_execution",
            "command_center_3_worker_contract.v1" in this_script
            and "local_worker_contract_no_process_start" in this_script
            and "production_worker_complete" in this_script
            and "healthcheck_executed" in this_script
            and "activation_ready" in this_script
            and "does_not_execute_trades" in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script,
            "The push-gate contract script must stay local and must not import provider clients or start worker processes.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_worker_contract.v1",
        "status": "worker_contract_passed" if not blockers else "worker_contract_blocked",
        "scope": "local_worker_contract_no_process_start",
        "ltg": "LTG-06/LTG-11",
        "contract_ready": not blockers,
        "production_worker_complete": False,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "healthcheck_executed": False,
        "healthcheck_task_dispatched": False,
        "activation_ready": False,
        "manual_activation_required": True,
        "task_log_persistence_verified": False,
        "append_only_worker_log_verified": False,
        "local_fallback_available": True,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "observed": {
            "worker_cache_status": packet.get("status"),
            "task_count": catalog.get("task_count"),
            "dispatch_plan_task_count": dispatch_summary.get("task_count"),
            "dispatch_plan_queue_count": dispatch_summary.get("queue_names") and len(dispatch_summary.get("queue_names")),
            "production_blocker_status": blocker_audit.get("status"),
            "production_blocker_count": blocker_audit.get("blocking_criterion_count"),
            "healthcheck_status": healthcheck.get("status"),
            "healthcheck_pending_count": healthcheck.get("pending_criterion_count"),
            "task_log_persistence_status": task_log_audit.get("status"),
            "task_log_persistence_blocker_count": task_log_audit.get("production_blocker_count"),
            "synthetic_healthcheck_status": synthetic_healthcheck.get("status"),
            "synthetic_healthcheck_executed": synthetic_healthcheck.get("synthetic_healthcheck_executed"),
            "activation_review_status": activation.get("status"),
            "activation_blocker_count": activation.get("activation_blocker_count"),
            "scheduler_auto_task_count": dispatch_summary.get("scheduler_auto_task_count"),
            "cache_get_external_call_count": dispatch_summary.get("cache_get_external_call_count"),
        },
        "rows": rows,
        "note": "This is a local push-gate contract. It does not run the synthetic healthcheck. Celery worker startup, Redis broker reachability, cross-process task controls, scheduler production config, and production worker activation remain pending.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-06 Worker contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"worker_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "production_worker_complete: false; healthcheck_executed: false; activation_ready: false".format(
                **contract
            )
        )
        print(
            "external_calls_triggered: false; tushare_called: false; "
            "deepseek_called: false; github_called: false; does_not_execute_trades: true"
        )
        if contract["blockers"]:
            print("blockers: " + ", ".join(contract["blockers"]))
    return 0 if contract["contract_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
