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
REQUIRED_QUEUE_ROUTING_CRITERIA = {
    "future_queues_declared",
    "queue_policy_rows_visible",
    "all_tasks_button_gated",
    "external_capable_tasks_isolated_from_local_queues",
    "local_queues_are_local_only",
    "provider_model_probe_queues_are_button_gated",
    "scheduler_default_off_for_all_queues",
    "cache_get_never_dispatches_queue_work",
    "celery_redis_not_started_by_routing_contract",
    "no_trade_or_action_boundary",
}
REQUIRED_ACTIVATION_REVIEW_TASK_CRITERIA = {
    "explicit_post_activation_review_done",
    "operator_approval_recorded",
    "synthetic_healthcheck_executed",
    "activation_review_contract_visible",
    "production_activation_receipt_visible",
    "celery_redis_not_started_by_review",
    "scheduler_default_off_preserved",
    "provider_model_no_autoschedule_boundary",
    "production_worker_completion_stays_blocked",
    "production_evidence_required",
}
REQUIRED_PRODUCTION_EVIDENCE_PLAN_CRITERIA = {
    "explicit_post_evidence_plan_done",
    "operator_approval_recorded",
    "activation_review_task_ready",
    "production_activation_receipt_visible",
    "celery_process_evidence_required",
    "redis_broker_evidence_required",
    "cross_process_controls_evidence_required",
    "append_only_worker_log_evidence_required",
    "scheduler_default_off_runtime_evidence_required",
    "provider_model_no_autoschedule_boundary",
    "no_trade_no_action_boundary",
    "production_worker_completion_stays_blocked",
}

REQUIRED_READINESS_RECEIPT_CRITERIA = {
    "local_worker_contracts_visible",
    "explicit_post_synthetic_healthcheck_boundary",
    "cache_get_no_process_start_boundary",
    "scheduler_default_off_boundary",
    "provider_model_isolation_boundary",
    "celery_redis_process_readiness_pending",
    "cross_process_task_controls_pending",
    "manual_activation_review_pending",
    "production_completion_evidence_ticket",
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


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text.lower())


def _synthetic_healthcheck_hash_consistent(packet: dict[str, Any]) -> bool:
    if packet.get("synthetic_healthcheck_executed") is True:
        return (
            packet.get("healthcheck_hash_algorithm") == "sha256"
            and _is_sha256(packet.get("task_identity_sha256"))
            and _is_sha256(packet.get("readback_task_identity_sha256"))
            and packet.get("task_readback_hash_matches") is True
        )
    return (
        packet.get("healthcheck_hash_algorithm") == ""
        and packet.get("task_identity_sha256") == ""
        and packet.get("readback_task_identity_sha256") == ""
        and packet.get("task_readback_hash_matches") is False
    )


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
    queue_routing = _dict(packet.get("worker_queue_routing_contract"))
    queue_routing_rows = [row for row in _list(packet.get("worker_queue_routing_rows")) if isinstance(row, dict)]
    queue_routing_criteria = {str(row.get("criterion") or "") for row in queue_routing_rows}
    queue_rows = [row for row in _list(packet.get("worker_queue_routing_queue_rows")) if isinstance(row, dict)]
    synthetic_healthcheck = _dict(packet.get("worker_synthetic_healthcheck"))
    readiness_receipt = _dict(packet.get("worker_production_readiness_receipt"))
    readiness_receipt_rows = [row for row in _list(packet.get("worker_production_readiness_receipt_rows")) if isinstance(row, dict)]
    readiness_receipt_criteria = {str(row.get("criterion") or "") for row in readiness_receipt_rows}
    activation_receipt = _dict(packet.get("worker_production_activation_receipt"))
    activation_receipt_rows = [row for row in _list(packet.get("worker_production_activation_rows")) if isinstance(row, dict)]
    activation_receipt_criteria = {str(row.get("criterion") or "") for row in activation_receipt_rows}
    activation_review_task = _dict(packet.get("worker_activation_review_task_receipt"))
    activation_review_task_rows = [row for row in _list(packet.get("worker_activation_review_task_rows")) if isinstance(row, dict)]
    activation_review_task_criteria = {str(row.get("criterion") or "") for row in activation_review_task_rows}
    production_evidence_plan = _dict(packet.get("worker_production_evidence_plan_receipt"))
    production_evidence_plan_rows = [
        row for row in _list(packet.get("worker_production_evidence_plan_rows")) if isinstance(row, dict)
    ]
    production_evidence_plan_criteria = {
        str(row.get("criterion") or "") for row in production_evidence_plan_rows
    }
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
            "queue_routing_contract_is_local_and_button_gated",
            queue_routing.get("schema_version") == "worker_queue_routing_contract.v1"
            and queue_routing.get("status") == "worker_queue_routing_contract_ready_activation_pending"
            and queue_routing.get("scope") == "local_worker_queue_routing_contract_no_process_start"
            and queue_routing.get("queue_routing_contract_ready") is True
            and int(queue_routing.get("task_count") or 0) == int(catalog.get("task_count") or 0)
            and int(queue_routing.get("queue_count") or 0) >= 5
            and int(queue_routing.get("local_queue_external_task_count") or 0) == 0
            and REQUIRED_QUEUE_ROUTING_CRITERIA.issubset(queue_routing_criteria)
            and {"provider_refresh", "model_explain", "external_probe", "local_maintenance", "local_compute"}.issubset(
                set(queue_routing.get("queue_names") or [])
            )
            and all(row.get("all_tasks_button_gated") is True for row in queue_rows)
            and all(row.get("cache_get_external_call_count") == 0 for row in queue_rows)
            and all(row.get("automatic_scheduler_allowed_count") == 0 for row in queue_rows)
            and queue_routing.get("production_worker_complete") is False
            and queue_routing.get("activation_ready") is False
            and queue_routing.get("worker_started_by_contract") is False
            and queue_routing.get("redis_pinged_by_contract") is False
            and queue_routing.get("scheduler_started_by_contract") is False
            and queue_routing.get("task_dispatched_by_contract") is False
            and queue_routing.get("provider_model_task_dispatched_by_contract") is False
            and queue_routing.get("cache_get_external_calls") is False
            and queue_routing.get("contract_external_calls_triggered") is False
            and _flag_false(queue_routing, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and queue_routing.get("does_not_execute_trades") is True
            and queue_routing.get("does_not_modify_strategy_action") is True
            and queue_routing.get("contains_secret") is False
            and _list(queue_routing.get("call_ledger"))
            and _dict(_list(queue_routing.get("call_ledger"))[0]).get("api") == "local_worker_queue_routing_contract"
            and "local_worker_queue_routing_contract" in {item.get("api") for item in _list(packet.get("call_ledger"))}
            and _dict(packet.get("policy")).get("worker_queue_routing_contract_is_local") is True
            and _dict(packet.get("policy")).get("worker_queue_routing_contract_is_not_process_start") is True
            and _dict(packet.get("policy")).get("worker_queue_routing_contract_is_not_production_completion") is True,
            "Worker queue routing contract must keep future Celery queues explicit, button-gated, scheduler-off, local/no-process-start, no-provider-call, no-trade, and not production complete.",
        ),
        _row(
            "synthetic_healthcheck_is_explicit_post_only",
            "POST /api/worker/synthetic-healthcheck" in _dict(catalog.get("route_coverage")).get("known_post_routes", [])
            and _dict(catalog.get("policy")).get("all_known_post_routes_button_gated") is True
            and synthetic_healthcheck.get("schema_version") == "worker_synthetic_healthcheck.v1"
            and synthetic_healthcheck.get("scope") == "explicit_post_worker_synthetic_healthcheck_no_process_start"
            and synthetic_healthcheck.get("cache_get_external_calls") is False
            and _synthetic_healthcheck_hash_consistent(synthetic_healthcheck)
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
            "production_readiness_receipt_allows_only_explicit_next_step",
            readiness_receipt.get("schema_version") == "worker_production_readiness_receipt.v1"
            and readiness_receipt.get("status")
            in {
                "worker_readiness_receipt_ready_synthetic_healthcheck_pending",
                "worker_readiness_receipt_ready_activation_review_pending",
            }
            and readiness_receipt.get("scope") == "local_worker_production_readiness_receipt_no_process_start"
            and readiness_receipt.get("local_receipt_ready") is True
            and readiness_receipt.get("ready_for_explicit_synthetic_healthcheck") is True
            and readiness_receipt.get("allowed_next_step") == "explicit_post_worker_synthetic_healthcheck_then_manual_activation_review"
            and "GET /api/worker/cache worker process start" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and "GET /api/worker/cache Redis ping" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and "automatic Tushare/DeepSeek/GitHub task scheduling" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and "readiness receipt as production worker completion" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and REQUIRED_READINESS_RECEIPT_CRITERIA.issubset(readiness_receipt_criteria)
            and readiness_receipt.get("production_worker_complete") is False
            and readiness_receipt.get("worker_started_by_receipt") is False
            and readiness_receipt.get("celery_worker_started") is False
            and readiness_receipt.get("redis_pinged_by_receipt") is False
            and readiness_receipt.get("redis_pinged") is False
            and readiness_receipt.get("scheduler_started_by_receipt") is False
            and readiness_receipt.get("scheduler_started") is False
            and readiness_receipt.get("task_dispatched_by_receipt") is False
            and readiness_receipt.get("provider_model_task_dispatched_by_receipt") is False
            and readiness_receipt.get("cache_get_external_calls") is False
            and readiness_receipt.get("receipt_external_calls_triggered") is False
            and _flag_false(readiness_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and readiness_receipt.get("tushare_called_by_receipt") is False
            and readiness_receipt.get("does_not_execute_trades") is True
            and readiness_receipt.get("does_not_modify_strategy_action") is True
            and readiness_receipt.get("contains_secret") is False
            and _list(readiness_receipt.get("call_ledger"))
            and _dict(_list(readiness_receipt.get("call_ledger"))[0]).get("api") == "local_worker_production_readiness_receipt"
            and _dict(_list(readiness_receipt.get("call_ledger"))[0]).get("external") is False
            and policy.get("worker_production_readiness_receipt_is_local") is True
            and policy.get("worker_production_readiness_receipt_is_not_process_start") is True
            and policy.get("worker_production_readiness_receipt_is_not_production_completion") is True,
            "Worker production readiness receipt may choose the next safe explicit step, but it must not start processes, ping Redis, dispatch tasks, call providers/models, or claim production completion.",
        ),
        _row(
            "activation_review_task_is_button_gated_no_process_start",
            "POST /api/worker/activation-review" in _dict(catalog.get("route_coverage")).get("known_post_routes", [])
            and activation_review_task.get("schema_version") == "worker_activation_review_task_receipt.v1"
            and activation_review_task.get("status")
            in {
                "worker_activation_review_task_pending",
                "worker_activation_review_task_ready_production_blocked",
                "worker_activation_review_task_blocked_operator_approval_required",
            }
            and activation_review_task.get("scope") == "button_gated_worker_activation_review_no_process_start"
            and activation_review_task.get("button_gated") is True
            and activation_review_task.get("local_review_only") is True
            and activation_review_task.get("ready_to_mark_production_worker_complete") is False
            and activation_review_task.get("production_worker_complete") is False
            and activation_review_task.get("activation_ready") is False
            and int(activation_review_task.get("production_blocker_count") or 0) > 0
            and REQUIRED_ACTIVATION_REVIEW_TASK_CRITERIA.issubset(activation_review_task_criteria)
            and "activation review as production worker completion" in _list(
                activation_review_task.get("not_allowed_next_steps")
            )
            and "celery worker process evidence" in _list(activation_review_task.get("missing_evidence_items"))
            and activation_review_task.get("starts_celery_worker") is False
            and activation_review_task.get("pings_redis") is False
            and activation_review_task.get("starts_scheduler") is False
            and activation_review_task.get("task_dispatched") is False
            and activation_review_task.get("provider_model_task_dispatched") is False
            and activation_review_task.get("cache_get_external_calls") is False
            and _flag_false(activation_review_task, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and activation_review_task.get("does_not_execute_trades") is True
            and activation_review_task.get("does_not_modify_strategy_action") is True
            and activation_review_task.get("contains_secret") is False
            and all(row.get("worker_started") is False for row in activation_review_task_rows)
            and all(row.get("redis_pinged") is False for row in activation_review_task_rows)
            and all(row.get("scheduler_started") is False for row in activation_review_task_rows)
            and all(row.get("task_dispatched") is False for row in activation_review_task_rows)
            and policy.get("worker_activation_review_task_is_button_gated") is True
            and policy.get("worker_activation_review_task_is_not_process_start") is True
            and policy.get("worker_activation_review_task_is_not_production_completion") is True,
            "Worker activation review task may bind local synthetic-healthcheck evidence, but must not start processes, ping Redis, dispatch tasks, call providers/models, or claim production completion.",
        ),
        _row(
            "production_evidence_plan_is_scope_ticket_only",
            "POST /api/worker/production-evidence-plan"
            in _dict(catalog.get("route_coverage")).get("known_post_routes", [])
            and production_evidence_plan.get("schema_version") == "worker_production_evidence_plan_receipt.v1"
            and production_evidence_plan.get("status")
            in {
                "worker_production_evidence_plan_pending_activation_review",
                "worker_production_evidence_plan_ready_runtime_qa_pending",
                "worker_production_evidence_plan_blocked_operator_approval_required",
            }
            and production_evidence_plan.get("scope")
            == "button_gated_worker_production_evidence_plan_no_process_start"
            and production_evidence_plan.get("button_gated") is True
            and production_evidence_plan.get("local_plan_only") is True
            and production_evidence_plan.get("ready_to_mark_production_worker_complete") is False
            and production_evidence_plan.get("production_worker_complete") is False
            and production_evidence_plan.get("activation_ready") is False
            and int(production_evidence_plan.get("production_blocker_count") or 0) > 0
            and REQUIRED_PRODUCTION_EVIDENCE_PLAN_CRITERIA.issubset(production_evidence_plan_criteria)
            and "evidence plan as production worker completion" in _list(
                production_evidence_plan.get("not_allowed_next_steps")
            )
            and "scope ticket as runtime evidence" in _list(production_evidence_plan.get("not_allowed_next_steps"))
            and "celery worker process identity and queue registration evidence"
            in _list(production_evidence_plan.get("missing_evidence_items"))
            and _is_sha256(production_evidence_plan.get("scope_ticket_sha256"))
            and production_evidence_plan.get("starts_celery_worker") is False
            and production_evidence_plan.get("pings_redis") is False
            and production_evidence_plan.get("starts_scheduler") is False
            and production_evidence_plan.get("task_dispatched") is False
            and production_evidence_plan.get("provider_model_task_dispatched") is False
            and production_evidence_plan.get("cache_get_external_calls") is False
            and _flag_false(
                production_evidence_plan,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and production_evidence_plan.get("does_not_execute_trades") is True
            and production_evidence_plan.get("does_not_modify_strategy_action") is True
            and production_evidence_plan.get("contains_secret") is False
            and all(row.get("worker_started") is False for row in production_evidence_plan_rows)
            and all(row.get("redis_pinged") is False for row in production_evidence_plan_rows)
            and all(row.get("scheduler_started") is False for row in production_evidence_plan_rows)
            and all(row.get("task_dispatched") is False for row in production_evidence_plan_rows)
            and policy.get("worker_production_evidence_plan_is_button_gated") is True
            and policy.get("worker_production_evidence_plan_is_not_process_start") is True
            and policy.get("worker_production_evidence_plan_is_not_production_completion") is True,
            "Worker production evidence plan may create a later runtime-QA scope ticket, but it must not start processes, ping Redis, dispatch tasks, call providers/models, execute trades, or claim production worker completion.",
        ),
        _row(
            "production_activation_receipt_keeps_worker_blocked",
            activation_receipt.get("schema_version") == "worker_production_activation_receipt.v1"
            and activation_receipt.get("status") == "worker_activation_receipt_ready_production_blocked"
            and activation_receipt.get("scope") == "local_worker_production_activation_receipt_no_process_start"
            and activation_receipt.get("local_activation_receipt_ready") is True
            and activation_receipt.get("allowed_next_step")
            == "explicit_synthetic_healthcheck_then_manual_celery_redis_activation_review"
            and "GET /api/worker/cache worker process start" in _list(activation_receipt.get("not_allowed_next_steps"))
            and "GET /api/worker/cache Redis ping" in _list(activation_receipt.get("not_allowed_next_steps"))
            and "automatic Tushare/DeepSeek/GitHub task scheduling" in _list(activation_receipt.get("not_allowed_next_steps"))
            and "activation receipt as production worker completion" in _list(activation_receipt.get("not_allowed_next_steps"))
            and "celery worker process evidence" in _list(activation_receipt.get("missing_evidence_items"))
            and "redis broker reachability evidence" in _list(activation_receipt.get("missing_evidence_items"))
            and "production worker promotion evidence" in _list(activation_receipt.get("missing_evidence_items"))
            and activation_receipt.get("production_worker_complete") is False
            and activation_receipt.get("activation_ready") is False
            and activation_receipt.get("healthcheck_executed_by_receipt") is False
            and activation_receipt.get("worker_started_by_receipt") is False
            and activation_receipt.get("celery_worker_started") is False
            and activation_receipt.get("redis_pinged_by_receipt") is False
            and activation_receipt.get("redis_pinged") is False
            and activation_receipt.get("scheduler_started_by_receipt") is False
            and activation_receipt.get("scheduler_started") is False
            and activation_receipt.get("task_dispatched_by_receipt") is False
            and activation_receipt.get("provider_model_task_dispatched_by_receipt") is False
            and activation_receipt.get("cache_get_external_calls") is False
            and activation_receipt.get("receipt_external_calls_triggered") is False
            and _flag_false(activation_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and activation_receipt.get("tushare_called_by_receipt") is False
            and activation_receipt.get("does_not_execute_trades") is True
            and activation_receipt.get("does_not_modify_strategy_action") is True
            and activation_receipt.get("contains_secret") is False
            and activation_receipt.get("production_blocker_count") == blocker_audit.get("blocking_criterion_count")
            and {
                "local_readiness_receipt_ready",
                "synthetic_healthcheck_execution_required",
                "celery_worker_manual_start_required",
                "redis_broker_reachability_required",
                "cross_process_controls_required",
                "append_only_log_required",
                "manual_activation_review_required",
                "scheduler_default_off_boundary",
                "provider_model_isolation_boundary",
                "no_trade_or_action_boundary",
                "production_completion_evidence_required",
            }.issubset(activation_receipt_criteria)
            and _list(activation_receipt.get("call_ledger"))
            and _dict(_list(activation_receipt.get("call_ledger"))[0]).get("api")
            == "local_worker_production_activation_receipt"
            and "local_worker_production_activation_receipt" in {item.get("api") for item in _list(packet.get("call_ledger"))},
            "Worker production activation receipt must keep Celery/Redis/manual activation evidence pending while forbidding cache GET process starts, Redis pings, task dispatch, provider/model scheduling, trades, and production completion claims.",
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
            and "worker_production_activation_receipt.v1" in this_script
            and "worker_activation_review_task_receipt.v1" in this_script
            and "worker_production_evidence_plan_receipt.v1" in this_script
            and "worker_queue_routing_contract.v1" in this_script
            and "task_readback_fingerprint_matches" in this_script
            and "queue_routing_contract_is_local_and_button_gated" in this_script
            and "production_activation_receipt_keeps_worker_blocked" in this_script
            and "activation_review_task_is_button_gated_no_process_start" in this_script
            and "production_evidence_plan_is_scope_ticket_only" in this_script
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
        "worker_production_readiness_receipt_ready": readiness_receipt.get("local_receipt_ready") is True,
        "worker_production_readiness_receipt_status": readiness_receipt.get("status"),
        "worker_production_activation_receipt_ready": activation_receipt.get("local_activation_receipt_ready") is True,
        "worker_production_activation_receipt_status": activation_receipt.get("status"),
        "worker_activation_review_task_ready": activation_review_task.get("activation_review_ready") is True,
        "worker_activation_review_task_status": activation_review_task.get("status"),
        "worker_production_evidence_plan_ready": production_evidence_plan.get("evidence_plan_ready") is True,
        "worker_production_evidence_plan_status": production_evidence_plan.get("status"),
        "worker_queue_routing_contract_ready": queue_routing.get("queue_routing_contract_ready") is True,
        "worker_queue_routing_contract_status": queue_routing.get("status"),
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
            "queue_routing_status": queue_routing.get("status"),
            "queue_routing_queue_count": queue_routing.get("queue_count"),
            "queue_routing_external_capable_task_count": queue_routing.get("external_capable_task_count"),
            "synthetic_healthcheck_status": synthetic_healthcheck.get("status"),
            "synthetic_healthcheck_executed": synthetic_healthcheck.get("synthetic_healthcheck_executed"),
            "synthetic_healthcheck_hash_algorithm": synthetic_healthcheck.get("healthcheck_hash_algorithm"),
            "synthetic_healthcheck_task_hash_present": _is_sha256(synthetic_healthcheck.get("task_identity_sha256")),
            "synthetic_healthcheck_readback_hash_present": _is_sha256(
                synthetic_healthcheck.get("readback_task_identity_sha256")
            ),
            "synthetic_healthcheck_hash_matches": synthetic_healthcheck.get("task_readback_hash_matches"),
            "activation_review_status": activation.get("status"),
            "activation_blocker_count": activation.get("activation_blocker_count"),
            "worker_production_readiness_receipt_status": readiness_receipt.get("status"),
            "worker_production_readiness_receipt_blocker_count": readiness_receipt.get("blocking_criterion_count"),
            "worker_production_readiness_allowed_next_step": readiness_receipt.get("allowed_next_step"),
            "worker_production_activation_receipt_status": activation_receipt.get("status"),
            "worker_production_activation_blocker_count": activation_receipt.get("blocking_criterion_count"),
            "worker_production_activation_allowed_next_step": activation_receipt.get("allowed_next_step"),
            "worker_activation_review_task_status": activation_review_task.get("status"),
            "worker_activation_review_task_local_blocker_count": activation_review_task.get("local_blocker_count"),
            "worker_activation_review_task_production_blocker_count": activation_review_task.get("production_blocker_count"),
            "worker_production_evidence_plan_status": production_evidence_plan.get("status"),
            "worker_production_evidence_plan_local_blocker_count": production_evidence_plan.get("local_blocker_count"),
            "worker_production_evidence_plan_production_blocker_count": production_evidence_plan.get(
                "production_blocker_count"
            ),
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
