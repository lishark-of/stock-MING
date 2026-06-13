from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from server.services import task_service


PACKET_KEY = "command_center_3_worker_runtime_cache"
SCHEMA_VERSION = "worker_runtime_cache.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "worker_runtime_cache_not_json_serializable"}


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _path_exists(path: str) -> bool:
    return (PROJECT_ROOT / path).exists()


def _worker_module_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "module": "worker.celery_app",
            "file": "worker/celery_app.py",
            "role": "Celery app factory",
            "task_types": [],
        },
        {
            "module": "worker.tasks_factor",
            "file": "worker/tasks_factor.py",
            "role": "Factor quant task wrappers",
            "task_types": ["refresh_factor_data", "run_factor_light", "run_factor_universe_research_plan"],
        },
        {
            "module": "worker.tasks_candidate",
            "file": "worker/tasks_candidate.py",
            "role": "Candidate radar task wrappers",
            "task_types": ["run_candidate_radar_full_pool_plan", "run_candidate_radar_deep_scan_plan"],
        },
        {
            "module": "worker.tasks_deepseek",
            "file": "worker/tasks_deepseek.py",
            "role": "Guarded DeepSeek explanation task wrapper",
            "task_types": ["run_deepseek_factor_explanation"],
        },
        {
            "module": "worker.tasks_chokepoint",
            "file": "worker/tasks_chokepoint.py",
            "role": "Chokepoint and Serenity task wrappers",
            "task_types": ["run_chokepoint_scan", "probe_serenity_github"],
        },
        {
            "module": "worker.tasks_tushare",
            "file": "worker/tasks_tushare.py",
            "role": "Tushare refresh task wrapper",
            "task_types": ["refresh_tushare_facts"],
        },
        {
            "module": "worker.scheduler",
            "file": "worker/scheduler.py",
            "role": "APScheduler config scaffold",
            "task_types": [],
        },
    ]
    for row in rows:
        row["module_available"] = _module_available(str(row["module"]))
        row["file_exists"] = _path_exists(str(row["file"]))
    return rows


def _queue_for_task_type(task_type: str) -> str:
    if task_type in {"refresh_tushare_facts", "refresh_factor_data"}:
        return "provider_refresh"
    if task_type == "run_deepseek_factor_explanation":
        return "model_explain"
    if task_type in {"run_chokepoint_scan", "probe_serenity_github"}:
        return "external_probe"
    if task_type in {
        "run_storage_artifact_cleanup_dry_run",
        "run_storage_schema_validation_dry_run",
        "run_storage_schema_validation_acceptance",
        "run_storage_dataset_version_manifest_dry_run",
        "run_storage_dataset_version_manifest_write",
        "run_storage_partition_migration_dry_run",
        "run_storage_compaction_dry_run",
        "run_storage_cache_ttl_dry_run",
    }:
        return "local_maintenance"
    return "local_compute"


def _worker_dispatch_plan_rows(
    catalog: dict[str, Any],
    *,
    celery_available: bool,
    redis_configured: bool,
    scheduled_refresh_enabled: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in catalog.get("tasks") or []:
        task_type = str(item.get("task_type") or "")
        queue = _queue_for_task_type(task_type)
        external_sources = [str(source) for source in item.get("possible_external_sources") or []]
        backend = str(item.get("current_backend") or "")
        if "stub" in backend:
            dispatch_status = "stub_worker_pending"
            next_action = "replace local stub with explicit worker implementation before production dispatch."
        elif celery_available and redis_configured:
            dispatch_status = "celery_dispatch_preflight_ready"
            next_action = "operator may route this task to Celery only through explicit POST task dispatch."
        else:
            dispatch_status = "local_fallback_ready_worker_pending"
            next_action = "keep local fallback; configure Redis and start Celery manually before worker dispatch."
        rows.append(
            {
                "task_type": task_type,
                "route": item.get("route"),
                "output_packet_key": item.get("output_packet_key"),
                "current_backend": backend,
                "future_queue": queue,
                "dispatch_status": dispatch_status,
                "local_fallback_supported": True,
                "celery_available": celery_available,
                "redis_configured": redis_configured,
                "redis_required_for_celery": True,
                "redis_pinged": False,
                "celery_started": False,
                "button_gated": item.get("button_gated") is True,
                "cache_get_external_calls": item.get("cache_get_external_calls") is True,
                "possible_external_sources": external_sources,
                "possible_external_source_count": len(external_sources),
                "automatic_scheduler_allowed": False,
                "scheduled_refresh_enabled": scheduled_refresh_enabled,
                "scheduler_default_off": not scheduled_refresh_enabled,
                "retry_policy_required": True,
                "cancel_policy_required": True,
                "lock_policy_required": True,
                "dedupe_policy_required": True,
                "safe_task_log_required": True,
                "error_message_safe_required": True,
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "next_action": next_action,
            }
        )
    return rows


def _backend_rows(*, celery_available: bool, redis_available: bool, apscheduler_available: bool, scheduled_refresh_enabled: bool) -> list[dict[str, Any]]:
    return [
        {
            "backend": "local_fallback",
            "status": "ready",
            "role": "Default local task lifecycle and SQLite persistence",
            "external_connection": False,
            "started_by_cache_api": False,
        },
        {
            "backend": "celery",
            "status": "available" if celery_available else "missing_dependency",
            "role": "Optional distributed worker backend",
            "external_connection": False,
            "started_by_cache_api": False,
        },
        {
            "backend": "redis",
            "status": "package_available" if redis_available else "missing_dependency",
            "role": "Optional broker / hot cache",
            "external_connection": False,
            "pinged_by_cache_api": False,
        },
        {
            "backend": "apscheduler",
            "status": "configured_disabled" if apscheduler_available and not scheduled_refresh_enabled else "configured_enabled" if apscheduler_available else "missing_dependency",
            "role": "Optional scheduled task trigger scaffold",
            "external_connection": False,
            "started_by_cache_api": False,
        },
    ]


def _manual_worker_preflight_steps(
    *,
    celery_available: bool,
    redis_available: bool,
    redis_configured: bool,
    apscheduler_available: bool,
    scheduled_refresh_enabled: bool,
) -> list[dict[str, Any]]:
    return [
        {
            "step_key": "verify_python_dependencies",
            "label": "确认 Celery / Redis / APScheduler Python 依赖",
            "status": "ready" if celery_available and redis_available and apscheduler_available else "dependency_missing",
            "required_for_desktop_mvp": False,
            "required_for_production_worker": True,
            "cache_api_can_execute": False,
            "operator_action_required": not (celery_available and redis_available and apscheduler_available),
            "safe_note": "GET /api/worker/cache 只检查依赖可见性，不安装依赖、不启动 worker。",
        },
        {
            "step_key": "configure_redis_broker",
            "label": "配置 Redis broker URL",
            "status": "configured_not_pinged" if redis_configured else "pending_manual_config",
            "required_for_desktop_mvp": False,
            "required_for_production_worker": True,
            "cache_api_can_execute": False,
            "operator_action_required": not redis_configured,
            "safe_note": "仅记录是否配置，不暴露连接串，也不会 ping Redis。",
        },
        {
            "step_key": "start_fastapi_server",
            "label": "手动启动 FastAPI 服务",
            "status": "manual_required",
            "required_for_desktop_mvp": True,
            "required_for_production_worker": True,
            "cache_api_can_execute": False,
            "operator_action_required": True,
            "safe_note": "由开发者显式启动；cache API 不会拉起后端进程。",
        },
        {
            "step_key": "start_celery_worker",
            "label": "手动启动 Celery worker",
            "status": "manual_required" if celery_available and redis_configured else "blocked_by_preflight",
            "required_for_desktop_mvp": False,
            "required_for_production_worker": True,
            "cache_api_can_execute": False,
            "operator_action_required": True,
            "safe_note": "后续用脚本手动启动；本 cache API 不会启动 worker。",
        },
        {
            "step_key": "run_task_smoke",
            "label": "运行任务 smoke / cache smoke",
            "status": "manual_required",
            "required_for_desktop_mvp": True,
            "required_for_production_worker": True,
            "cache_api_can_execute": False,
            "operator_action_required": True,
            "safe_note": "由开发者手动执行；不会从 GET cache 触发 Tushare、DeepSeek 或 GitHub。",
        },
        {
            "step_key": "enable_scheduler",
            "label": "显式启用 APScheduler 定时刷新",
            "status": "configured_enabled" if scheduled_refresh_enabled else "disabled_by_default",
            "required_for_desktop_mvp": False,
            "required_for_production_worker": False,
            "cache_api_can_execute": False,
            "operator_action_required": not scheduled_refresh_enabled,
            "safe_note": "定时任务默认关闭；必须显式配置后才允许进入计划刷新。",
        },
    ]


def _production_readiness(
    *,
    celery_available: bool,
    redis_available: bool,
    redis_configured: bool,
    apscheduler_available: bool,
    scheduled_refresh_enabled: bool,
) -> dict[str, Any]:
    rows = [
        {
            "component": "local_fallback_runner",
            "status": "ready",
            "production_role": "single-user local task execution and test fallback",
            "blocks_desktop_mvp": False,
            "blocks_production_worker": False,
            "next_action": "Keep as fallback even after Celery is enabled.",
        },
        {
            "component": "celery_worker_process",
            "status": "dependency_available_not_started" if celery_available else "dependency_missing",
            "production_role": "background long-running jobs",
            "blocks_desktop_mvp": False,
            "blocks_production_worker": True,
            "next_action": "Start with scripts/run_worker.sh after Redis broker is configured.",
        },
        {
            "component": "redis_broker",
            "status": "configured_not_pinged" if redis_configured else ("package_available_not_configured" if redis_available else "dependency_missing"),
            "production_role": "Celery broker / hot task status cache",
            "blocks_desktop_mvp": False,
            "blocks_production_worker": True,
            "next_action": "Configure a local Redis broker URL and verify manually; cache API must not ping Redis.",
        },
        {
            "component": "apscheduler",
            "status": "configured_enabled" if scheduled_refresh_enabled else ("configured_disabled" if apscheduler_available else "dependency_missing"),
            "production_role": "optional scheduled refresh trigger",
            "blocks_desktop_mvp": False,
            "blocks_production_worker": False,
            "next_action": "Keep scheduled refresh disabled by default; enable only by explicit config.",
        },
    ]
    blockers = [row["component"] for row in rows if row.get("blocks_production_worker") and str(row.get("status")) != "configured_not_pinged"]
    if redis_configured and celery_available:
        blockers = [item for item in blockers if item != "celery_worker_process"]
    return {
        "status": "desktop_mvp_ready_worker_production_pending" if blockers else "production_worker_preflight_ready",
        "scope": "worker_task_pipeline_productionization_preflight",
        "rows": rows,
        "production_control_rows": _worker_production_control_rows(),
        "manual_preflight_steps": _manual_worker_preflight_steps(
            celery_available=celery_available,
            redis_available=redis_available,
            redis_configured=redis_configured,
            apscheduler_available=apscheduler_available,
            scheduled_refresh_enabled=scheduled_refresh_enabled,
        ),
        "production_blockers": blockers,
        "local_fallback_available": True,
        "cache_api_starts_no_workers": True,
        "cache_api_pings_no_redis": True,
        "scheduled_refresh_default_off": not scheduled_refresh_enabled,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "Worker production readiness is diagnostic; it does not start Celery, ping Redis, schedule Tushare, or run real jobs.",
    }


def _worker_production_control_rows() -> list[dict[str, Any]]:
    return [
        {
            "control": "retry_policy",
            "status": "local_ready",
            "current_coverage": "task catalog, task records, POST /api/tasks/{task_id}/retry, and React Task Monitor expose manual retry; automatic retry/backoff remains disabled.",
            "next_action": "enable Celery retry/backoff only after production worker locks, dedupe, and operator approval are enforced.",
            "external_calls_triggered": False,
        },
        {
            "control": "task_cancel",
            "status": "local_ready",
            "current_coverage": "pending local tasks can be marked cancelled without external calls.",
            "next_action": "extend cancellation to running Celery tasks when production worker is enabled.",
            "external_calls_triggered": False,
        },
        {
            "control": "concurrency_lock",
            "status": "local_ready",
            "current_coverage": "task records expose lock_policy and local dispatch reuses active tasks with the same lock_key before queue execution.",
            "next_action": "extend lock enforcement to Celery/Redis dispatch once production worker is enabled.",
            "external_calls_triggered": False,
        },
        {
            "control": "task_dedupe",
            "status": "local_ready",
            "current_coverage": "task records expose dedupe_policy and local dispatch reuses active tasks with the same task_type+payload before queue execution.",
            "next_action": "extend dedupe enforcement to Celery/Redis dispatch once production worker is enabled.",
            "external_calls_triggered": False,
        },
        {
            "control": "task_logs",
            "status": "local_ready",
            "current_coverage": "task packets persist safe task_log entries alongside call_ledger and error_message_safe; no raw payloads, stack traces, or tokens are included.",
            "next_action": "move safe task logs to append-only worker log storage when Celery/Redis production worker is enabled.",
            "external_calls_triggered": False,
        },
        {
            "control": "worker_dispatch_plan",
            "status": "contract_ready",
            "current_coverage": "worker runtime exposes a per-task dispatch plan with future Celery queue, local fallback, Redis requirement, scheduler boundary, lock/dedupe/retry/log requirements, and external-call boundaries.",
            "next_action": "wire Celery queue routing only after Redis configuration and worker startup are manually verified.",
            "external_calls_triggered": False,
        },
    ]


def _worker_production_blocker_audit(
    *,
    celery_available: bool,
    redis_available: bool,
    redis_configured: bool,
    scheduled_refresh_enabled: bool,
    dispatch_plan_rows: list[dict[str, Any]],
    task_implementation_status: dict[str, Any],
    task_retry_policy_summary: dict[str, Any],
    task_persistence: dict[str, Any],
) -> dict[str, Any]:
    stub_count = int(task_implementation_status.get("stub_task_count") or 0)
    external_capable_button_gated = bool(task_implementation_status.get("all_external_capable_tasks_are_button_gated", True))
    external_capable_call_ledger = bool(task_implementation_status.get("all_external_capable_tasks_require_call_ledger", True))
    scheduler_auto_task_count = sum(1 for row in dispatch_plan_rows if row.get("automatic_scheduler_allowed"))
    unsafe_cache_get_count = sum(1 for row in dispatch_plan_rows if row.get("cache_get_external_calls"))
    missing_queue_contract_count = sum(1 for row in dispatch_plan_rows if not row.get("future_queue"))

    def _row(
        criterion: str,
        component: str,
        status: str,
        detail: str,
        next_action: str,
        *,
        required: bool = True,
        blocks_desktop_mvp: bool = False,
    ) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "component": component,
            "status": status,
            "required_for_production_worker": required,
            "blocks_desktop_mvp": blocks_desktop_mvp,
            "blocks_production_worker": bool(required and status != "passed"),
            "detail": detail,
            "next_action": next_action,
            "cache_api_can_resolve": False,
            "operator_action_required": bool(required and status != "passed"),
            "external_calls_triggered": False,
            "redis_pinged": False,
            "celery_started": False,
            "scheduler_started": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    rows = [
        _row(
            "redis_python_package_available",
            "redis_broker",
            "passed" if redis_available else "blocked",
            "Redis Python package is visible locally." if redis_available else "Redis Python package is not visible to this environment.",
            "Install project dependencies before enabling Celery broker routing.",
        ),
        _row(
            "redis_broker_url_configured",
            "redis_broker",
            "passed" if redis_configured else "blocked",
            "Redis broker URL is configured but not exposed or pinged." if redis_configured else "Redis broker URL is not configured; cache API intentionally does not ping Redis.",
            "Configure Redis broker URL manually and verify it outside GET cache.",
        ),
        _row(
            "celery_python_package_available",
            "celery_worker",
            "passed" if celery_available else "blocked",
            "Celery package is visible locally." if celery_available else "Celery package is not visible to this environment.",
            "Install project dependencies before routing heavy tasks to Celery.",
        ),
        _row(
            "celery_worker_started",
            "celery_worker",
            "blocked",
            "GET /api/worker/cache never starts worker processes; production worker is not proven running by this preflight.",
            "Start Celery manually and add a future explicit worker health check that does not run real provider/model tasks.",
        ),
        _row(
            "stub_tasks_migrated",
            "task_catalog",
            "passed" if stub_count == 0 else "blocked",
            f"{stub_count} task(s) still report stub backend; scaffold cannot be called production worker completion.",
            "Replace stub task backends or keep them clearly marked as non-production.",
        ),
        _row(
            "dispatch_queue_contract_complete",
            "dispatch_plan",
            "passed" if missing_queue_contract_count == 0 else "blocked",
            f"{len(dispatch_plan_rows) - missing_queue_contract_count}/{len(dispatch_plan_rows)} task(s) have future queue contracts.",
            "Assign future queue contracts before Celery routing is enabled.",
        ),
        _row(
            "external_tasks_button_gated",
            "task_catalog",
            "passed" if external_capable_button_gated else "blocked",
            "External-capable tasks remain button-gated." if external_capable_button_gated else "At least one external-capable task is not button-gated.",
            "Keep provider/model/probe tasks behind explicit POST buttons.",
        ),
        _row(
            "external_tasks_call_ledger_required",
            "task_catalog",
            "passed" if external_capable_call_ledger else "blocked",
            "External-capable tasks require call_ledger." if external_capable_call_ledger else "At least one external-capable task lacks call_ledger requirement.",
            "Require call_ledger before enabling worker routing.",
        ),
        _row(
            "scheduler_default_off",
            "scheduler",
            "passed" if not scheduled_refresh_enabled and scheduler_auto_task_count == 0 else "blocked",
            "Scheduler is off by default and dispatch plan contains no automatic scheduler tasks." if not scheduled_refresh_enabled and scheduler_auto_task_count == 0 else "Scheduler auto dispatch is enabled or planned.",
            "Keep scheduler disabled until explicit production scheduling design is approved.",
        ),
        _row(
            "cache_get_never_dispatches_external_work",
            "cache_api",
            "passed" if unsafe_cache_get_count == 0 else "blocked",
            f"Dispatch plan has {unsafe_cache_get_count} cache GET external-call row(s).",
            "Ensure all external work is POST/task gated.",
        ),
        _row(
            "retry_cancel_lock_dedupe_local_only",
            "task_controls",
            "passed"
            if task_retry_policy_summary.get("manual_retry_supported") and task_persistence.get("sqlite_fallback_enabled", True)
            else "blocked",
            "Manual retry/cancel/lock/dedupe/log controls are local-ready but not Celery-process complete.",
            "Extend these controls to Celery/Redis before claiming production worker completion.",
        ),
        _row(
            "no_real_trade_or_action_mutation",
            "safety",
            "passed",
            "Worker runtime cache is diagnostic and does not execute trades or mutate strategy action.",
            "Preserve this boundary when production worker dispatch is added.",
            required=True,
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_production_worker"]]
    return {
        "schema_version": "worker_production_blocker_audit.v1",
        "status": "production_worker_blocked" if blocking_rows else "production_worker_preflight_ready",
        "scope": "local_worker_runtime_blocker_audit_no_process_start",
        "criterion_count": len(rows),
        "blocking_criterion_count": len(blocking_rows),
        "passed_criterion_count": len(rows) - len(blocking_rows),
        "blocking_criteria": [str(row["criterion"]) for row in blocking_rows],
        "desktop_mvp_blocking_count": sum(1 for row in rows if row["blocks_desktop_mvp"]),
        "local_fallback_available": True,
        "production_worker_complete": False if blocking_rows else False,
        "cache_api_started_workers": False,
        "cache_api_pinged_redis": False,
        "cache_api_started_scheduler": False,
        "cache_get_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
        "note": "This audit lists production worker blockers. It is not a Celery/Redis health check and does not start processes or dispatch tasks.",
    }


def _worker_healthcheck_qa_contract(
    *,
    redis_configured: bool,
    scheduled_refresh_enabled: bool,
    dispatch_plan_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    scheduler_auto_task_count = sum(1 for row in dispatch_plan_rows if row.get("automatic_scheduler_allowed"))
    unsafe_cache_get_count = sum(1 for row in dispatch_plan_rows if row.get("cache_get_external_calls"))

    def _row(
        criterion: str,
        component: str,
        status: str,
        current_evidence: str,
        success_criteria: str,
        next_action: str,
        *,
        required: bool = True,
    ) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "component": component,
            "status": status,
            "current_evidence": current_evidence,
            "success_criteria": success_criteria,
            "next_action": next_action,
            "required_for_production_worker": required,
            "blocks_production_worker": bool(required and status != "passed"),
            "healthcheck_executed": False,
            "cache_api_can_execute": False,
            "operator_action_required": bool(required and status != "passed"),
            "external_calls_triggered": False,
            "redis_pinged": False,
            "celery_started": False,
            "scheduler_started": False,
            "task_dispatched": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    rows = [
        _row(
            "celery_worker_process_visible",
            "celery_worker",
            "pending_manual_healthcheck",
            "GET /api/worker/cache intentionally does not inspect or start a live Celery worker process.",
            "A future explicit healthcheck confirms a manually started worker process without dispatching provider/model jobs.",
            "Add a button-gated local healthcheck after Celery/Redis production config is approved.",
        ),
        _row(
            "redis_broker_reachable",
            "redis_broker",
            "pending_manual_healthcheck",
            "Redis URL configured but not pinged." if redis_configured else "Redis broker URL is not configured and cache API does not ping Redis.",
            "A future explicit healthcheck can prove broker reachability while redacting the URL and never exposing secrets.",
            "Verify Redis only through a manual healthcheck path, not through cache GET.",
        ),
        _row(
            "task_round_trip_healthcheck",
            "task_runtime",
            "pending_manual_healthcheck",
            "Current task lifecycle is local fallback plus SQLite metadata; no cross-process round trip is executed here.",
            "A future synthetic local-only task can be enqueued, completed, and read back through POST/task status without provider calls.",
            "Introduce a synthetic healthcheck task that cannot call Tushare, DeepSeek, GitHub, or trading code.",
        ),
        _row(
            "cancel_retry_cross_process",
            "task_controls",
            "pending_manual_healthcheck",
            "Retry/cancel/lock/dedupe are local-ready; Celery process semantics are not proven.",
            "Retry and cancel work across worker process boundaries with safe task logs and error_message_safe.",
            "Extend local controls to Celery only after worker round trip is proven.",
        ),
        _row(
            "scheduler_default_off_verified",
            "scheduler",
            "passed" if not scheduled_refresh_enabled and scheduler_auto_task_count == 0 else "blocked",
            "Scheduler config is disabled by default and dispatch plan has no automatic scheduler rows."
            if not scheduled_refresh_enabled and scheduler_auto_task_count == 0
            else "Scheduler is enabled or dispatch plan declares automatic tasks.",
            "Scheduler stays off unless explicitly configured by the operator.",
            "Keep scheduler disabled for the production worker healthcheck baseline.",
        ),
        _row(
            "provider_model_tasks_not_autoscheduled",
            "external_boundaries",
            "passed" if scheduler_auto_task_count == 0 and unsafe_cache_get_count == 0 else "blocked",
            f"Dispatch plan has {scheduler_auto_task_count} scheduler auto task(s) and {unsafe_cache_get_count} cache GET external-call row(s).",
            "Tushare, DeepSeek, and GitHub-capable work remains button/POST gated and never runs from page render or cache GET.",
            "Preserve button gating when Celery routing is added.",
        ),
        _row(
            "task_log_persistence_verified",
            "task_logs",
            "pending_manual_healthcheck",
            "Local task packets persist safe task logs; append-only worker log persistence is not proven.",
            "Future worker logs persist safe, redacted task events without payload secrets, stack traces, or raw provider responses.",
            "Add append-only worker log verification after Celery worker is running.",
        ),
        _row(
            "external_call_boundary",
            "safety",
            "passed",
            "This QA contract is local static metadata; it does not call providers, models, probes, or trading paths.",
            "Healthcheck tasks remain synthetic/local unless the operator explicitly launches separate provider/model validation.",
            "Keep production worker healthcheck separate from Tushare, DeepSeek, GitHub, and trading acceptance.",
        ),
        _row(
            "secret_redaction_boundary",
            "safety",
            "passed",
            "The contract records boolean configuration state only and never returns Redis URL, token, key, or password values.",
            "No token/key appears in frontend, logs, packet, cache, or healthcheck result payloads.",
            "Keep all runtime configuration values redacted.",
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_production_worker"]]
    pending_rows = [row for row in rows if str(row.get("status", "")).startswith("pending")]
    return {
        "schema_version": "worker_healthcheck_qa_contract.v1",
        "status": "worker_healthcheck_qa_contract_ready_execution_pending",
        "scope": "local_static_healthcheck_contract_no_process_start",
        "criterion_count": len(rows),
        "pending_criterion_count": len(pending_rows),
        "blocking_criterion_count": len(blocking_rows),
        "passed_criterion_count": len(rows) - len(blocking_rows),
        "blocking_criteria": [str(row["criterion"]) for row in blocking_rows],
        "production_worker_complete": False,
        "healthcheck_executed": False,
        "healthcheck_task_dispatched": False,
        "synthetic_task_only": True,
        "provider_model_task_validation_in_scope": False,
        "future_healthcheck_required": True,
        "release_gate_blocking_until_executed": True,
        "cache_api_started_workers": False,
        "cache_api_pinged_redis": False,
        "cache_api_started_scheduler": False,
        "cache_get_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "note": "This is a QA contract for a future explicit worker healthcheck. It does not start Celery, ping Redis, start APScheduler, dispatch tasks, call providers/models/probes, or execute trades.",
    }


def _worker_activation_review_contract(
    *,
    redis_configured: bool,
    scheduled_refresh_enabled: bool,
    dispatch_plan_rows: list[dict[str, Any]],
    production_blocker_audit: dict[str, Any],
    healthcheck_qa_contract: dict[str, Any],
) -> dict[str, Any]:
    external_source_count = sum(int(row.get("possible_external_source_count") or 0) for row in dispatch_plan_rows)
    scheduler_auto_task_count = sum(1 for row in dispatch_plan_rows if row.get("automatic_scheduler_allowed"))
    unsafe_cache_get_count = sum(1 for row in dispatch_plan_rows if row.get("cache_get_external_calls"))

    def _row(
        review_step: str,
        status: str,
        evidence: str,
        next_action: str,
        *,
        operator_action_required: bool = True,
        activation_blocker: bool = True,
    ) -> dict[str, Any]:
        return {
            "review_step": review_step,
            "status": status,
            "evidence": evidence,
            "next_action": next_action,
            "operator_action_required": operator_action_required,
            "activation_blocker": bool(activation_blocker and status != "passed"),
            "cache_api_can_execute": False,
            "cache_api_started_workers": False,
            "cache_api_pinged_redis": False,
            "cache_api_started_scheduler": False,
            "healthcheck_executed": False,
            "task_dispatched": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    rows = [
        _row(
            "review_production_blockers",
            "pending_manual_resolution"
            if int(production_blocker_audit.get("blocking_criterion_count") or 0) > 0
            else "passed",
            f"{production_blocker_audit.get('blocking_criterion_count', 0)} production blocker(s) remain visible.",
            "Resolve blocker rows before enabling Celery/Redis worker dispatch.",
        ),
        _row(
            "review_redis_broker_configuration",
            "pending_manual_config" if not redis_configured else "configured_not_pinged",
            "Redis broker URL is configured but not exposed or pinged." if redis_configured else "Redis broker URL is not configured.",
            "Configure and verify Redis manually outside GET /api/worker/cache.",
        ),
        _row(
            "review_celery_manual_start",
            "pending_manual_start",
            "GET /api/worker/cache never starts a Celery worker process.",
            "Start Celery manually only after Redis broker configuration and queue contracts are reviewed.",
        ),
        _row(
            "review_synthetic_healthcheck",
            "pending_manual_healthcheck",
            "worker_healthcheck_qa_contract remains execution-pending and no healthcheck task has been dispatched.",
            "Run a future explicit synthetic/local healthcheck before claiming worker activation readiness.",
        ),
        _row(
            "review_cross_process_task_controls",
            "pending_worker_semantics",
            "retry/cancel/lock/dedupe are local-ready, but Celery cross-process semantics are not proven.",
            "Validate cross-process retry/cancel/lock/dedupe only through a future worker healthcheck.",
        ),
        _row(
            "review_task_log_persistence",
            "pending_worker_log_validation",
            "safe task logs exist locally; append-only worker log persistence is not proven.",
            "Verify redacted worker task logs after a manually started worker is available.",
        ),
        _row(
            "review_scheduler_default_off",
            "passed" if not scheduled_refresh_enabled and scheduler_auto_task_count == 0 else "blocked",
            f"scheduled_refresh_enabled={scheduled_refresh_enabled}; scheduler_auto_task_count={scheduler_auto_task_count}.",
            "Keep scheduler off by default; any production scheduler requires separate approval.",
            operator_action_required=bool(scheduled_refresh_enabled or scheduler_auto_task_count),
        ),
        _row(
            "review_provider_model_isolation",
            "passed" if unsafe_cache_get_count == 0 else "blocked",
            f"{external_source_count} external-capable source reference(s) remain POST/task gated; cache_get_external_call_count={unsafe_cache_get_count}.",
            "Keep Tushare, DeepSeek and GitHub-capable work behind explicit POST task buttons.",
            operator_action_required=False,
            activation_blocker=True,
        ),
        _row(
            "review_local_fallback_rollback",
            "passed",
            "local fallback stays available when Redis/Celery are absent or not manually started.",
            "Preserve local fallback as the rollback path after worker routing is introduced.",
            operator_action_required=False,
            activation_blocker=False,
        ),
        _row(
            "review_secret_redaction",
            "passed",
            "activation review exposes boolean configuration state only and never returns Redis URL, token, key or password values.",
            "Keep config values out of frontend, logs, packets and cache.",
            operator_action_required=False,
            activation_blocker=True,
        ),
    ]
    activation_blockers = [row for row in rows if row["activation_blocker"]]
    return {
        "schema_version": "worker_activation_review_contract.v1",
        "status": "worker_activation_review_ready_activation_pending",
        "scope": "manual_worker_activation_review_no_process_start",
        "review_policy": "manual_activation_required_after_blocker_and_healthcheck_review",
        "review_step_count": len(rows),
        "activation_blocker_count": len(activation_blockers),
        "operator_action_required_count": sum(1 for row in rows if row.get("operator_action_required")),
        "pending_healthcheck_count": int(healthcheck_qa_contract.get("pending_criterion_count") or 0),
        "production_blocker_count": int(production_blocker_audit.get("blocking_criterion_count") or 0),
        "external_capable_source_reference_count": external_source_count,
        "activation_ready": False,
        "production_worker_complete": False,
        "manual_activation_required": True,
        "healthcheck_required_before_activation": True,
        "healthcheck_executed": False,
        "worker_started_by_cache_api": False,
        "redis_pinged_by_cache_api": False,
        "scheduler_started_by_cache_api": False,
        "task_dispatched_by_cache_api": False,
        "cache_get_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "note": "Worker activation review is a local manual approval contract. It does not start Celery, ping Redis, start scheduler, dispatch tasks, call providers/models/probes, execute trades, or modify strategy action.",
    }


def read_worker_runtime_cache() -> dict[str, Any]:
    celery_available = _module_available("celery")
    redis_available = _module_available("redis")
    apscheduler_available = _module_available("apscheduler")
    scheduled_refresh_enabled = os.getenv("COMMAND_CENTER_ENABLE_SCHEDULED_REFRESH") == "1"
    redis_configured = bool(os.getenv("COMMAND_CENTER_REDIS_URL"))
    catalog = task_service.build_task_catalog()
    task_implementation_status = catalog.get("implementation_status") or {}
    task_retry_policy_summary = catalog.get("retry_policy_summary") or {}
    task_index = task_service.build_task_status_index()
    task_persistence = task_index.get("persistence") or {}
    task_persistence_source_rows = task_index.get("persistence_source_rows") or []
    worker_module_rows = _worker_module_rows()
    backend_rows = _backend_rows(
        celery_available=celery_available,
        redis_available=redis_available,
        apscheduler_available=apscheduler_available,
        scheduled_refresh_enabled=scheduled_refresh_enabled,
    )
    dispatch_plan_rows = _worker_dispatch_plan_rows(
        catalog,
        celery_available=celery_available,
        redis_configured=redis_configured,
        scheduled_refresh_enabled=scheduled_refresh_enabled,
    )
    dispatch_plan_status_counts: dict[str, int] = {}
    for row in dispatch_plan_rows:
        status_key = str(row.get("dispatch_status") or "unknown")
        dispatch_plan_status_counts[status_key] = dispatch_plan_status_counts.get(status_key, 0) + 1
    production_readiness = _production_readiness(
        celery_available=celery_available,
        redis_available=redis_available,
        redis_configured=redis_configured,
        apscheduler_available=apscheduler_available,
        scheduled_refresh_enabled=scheduled_refresh_enabled,
    )
    production_blocker_audit = _worker_production_blocker_audit(
        celery_available=celery_available,
        redis_available=redis_available,
        redis_configured=redis_configured,
        scheduled_refresh_enabled=scheduled_refresh_enabled,
        dispatch_plan_rows=dispatch_plan_rows,
        task_implementation_status=task_implementation_status,
        task_retry_policy_summary=task_retry_policy_summary,
        task_persistence=task_persistence,
    )
    production_readiness["production_blocker_audit"] = production_blocker_audit
    production_readiness["production_blocker_rows"] = production_blocker_audit["rows"]
    production_readiness["production_worker_complete"] = False
    healthcheck_qa_contract = _worker_healthcheck_qa_contract(
        redis_configured=redis_configured,
        scheduled_refresh_enabled=scheduled_refresh_enabled,
        dispatch_plan_rows=dispatch_plan_rows,
    )
    production_readiness["worker_healthcheck_qa_contract"] = healthcheck_qa_contract
    production_readiness["worker_healthcheck_qa_rows"] = healthcheck_qa_contract["rows"]
    activation_review_contract = _worker_activation_review_contract(
        redis_configured=redis_configured,
        scheduled_refresh_enabled=scheduled_refresh_enabled,
        dispatch_plan_rows=dispatch_plan_rows,
        production_blocker_audit=production_blocker_audit,
        healthcheck_qa_contract=healthcheck_qa_contract,
    )
    production_readiness["worker_activation_review_contract"] = activation_review_contract
    production_readiness["worker_activation_review_rows"] = activation_review_contract["rows"]
    module_ready_count = sum(1 for row in worker_module_rows if row["module_available"] and row["file_exists"])
    manual_preflight_steps = production_readiness.get("manual_preflight_steps") or []
    status = "ready" if module_ready_count == len(worker_module_rows) else "partial"

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "runtime": {
            "local_fallback_enabled": True,
            "sqlite_task_metadata_enabled": True,
            "celery_available": celery_available,
            "redis_package_available": redis_available,
            "redis_url_configured": redis_configured,
            "redis_url_exposed": False,
            "apscheduler_available": apscheduler_available,
            "scheduled_refresh_enabled": scheduled_refresh_enabled,
            "celery_worker_started": False,
            "scheduler_started": False,
            "redis_pinged": False,
        },
        "task_catalog_summary": {
            "task_count": catalog.get("task_count", 0),
            "external_sources": catalog.get("external_sources", []),
            "all_tasks_button_gated": bool(catalog.get("policy", {}).get("all_tasks_button_gated")),
            "call_ledger_required_for_all": bool(catalog.get("policy", {}).get("call_ledger_required_for_all")),
            "supports_local_task_cancel": bool(catalog.get("policy", {}).get("supports_local_task_cancel")),
            "implementation_status": task_implementation_status.get("status"),
            "stub_task_count": task_implementation_status.get("stub_task_count", 0),
            "local_pipeline_task_count": task_implementation_status.get("local_pipeline_task_count", 0),
            "guarded_local_task_count": task_implementation_status.get("guarded_local_task_count", 0),
            "implemented_local_task_count": task_implementation_status.get("implemented_local_task_count", 0),
            "retry_policy_status": task_retry_policy_summary.get("status"),
            "auto_retry_enabled": bool(task_retry_policy_summary.get("auto_retry_enabled")),
        },
        "task_implementation_status": task_implementation_status,
        "task_retry_policy_summary": task_retry_policy_summary,
        "task_status_summary": {
            "packet_key": task_index.get("packet_key"),
            "task_count": task_index.get("task_count", 0),
            "status_counts": task_index.get("status_counts", {}),
            "latest_task_id": task_index.get("latest_task_id"),
            "latest_task_type": task_index.get("latest_task_type"),
            "latest_task_status": task_index.get("latest_task_status"),
            "call_ledger_count": task_index.get("call_ledger_count", 0),
            "task_log_count": task_index.get("task_log_count", 0),
            "persistence": task_persistence,
            "persistence_source_rows": task_persistence_source_rows,
            "memory_task_count": task_persistence.get("memory_task_count", 0),
            "sqlite_task_count": task_persistence.get("sqlite_task_count", 0),
            "deduplicated_task_count": task_persistence.get("deduplicated_task_count", task_index.get("task_count", 0)),
            "sqlite_fallback_enabled": task_persistence.get("sqlite_fallback_enabled", True),
            "lock_conflict_audit_count": task_persistence.get("lock_conflict_audit_count", 0),
            "lock_enforced_task_count": task_persistence.get("lock_enforced_task_count", 0),
            "dedupe_duplicate_audit_count": task_persistence.get("dedupe_duplicate_audit_count", 0),
            "dispatch_dedupe_enforced_count": task_persistence.get("dispatch_dedupe_enforced_count", 0),
            "external_calls_triggered": task_index.get("external_calls_triggered", False),
            "does_not_execute_trades": task_index.get("does_not_execute_trades", True),
            "does_not_modify_strategy_action": task_index.get("does_not_modify_strategy_action", True),
        },
        "task_persistence": task_persistence,
        "task_persistence_source_rows": task_persistence_source_rows,
        "production_readiness": production_readiness,
        "worker_production_blocker_audit": production_blocker_audit,
        "worker_production_blocker_rows": production_blocker_audit["rows"],
        "worker_healthcheck_qa_contract": healthcheck_qa_contract,
        "worker_healthcheck_qa_rows": healthcheck_qa_contract["rows"],
        "worker_activation_review_contract": activation_review_contract,
        "worker_activation_review_rows": activation_review_contract["rows"],
        "dispatch_plan_status": "contract_ready_local_fallback",
        "dispatch_plan_rows": dispatch_plan_rows,
        "dispatch_plan_summary": {
            "task_count": len(dispatch_plan_rows),
            "queue_names": sorted({str(row.get("future_queue") or "") for row in dispatch_plan_rows if row.get("future_queue")}),
            "status_counts": dispatch_plan_status_counts,
            "local_fallback_supported_count": sum(1 for row in dispatch_plan_rows if row.get("local_fallback_supported")),
            "celery_ready_count": sum(1 for row in dispatch_plan_rows if row.get("dispatch_status") == "celery_dispatch_preflight_ready"),
            "stub_worker_pending_count": sum(1 for row in dispatch_plan_rows if row.get("dispatch_status") == "stub_worker_pending"),
            "all_routes_button_gated": all(row.get("button_gated") for row in dispatch_plan_rows),
            "cache_get_external_call_count": sum(1 for row in dispatch_plan_rows if row.get("cache_get_external_calls")),
            "scheduler_auto_task_count": sum(1 for row in dispatch_plan_rows if row.get("automatic_scheduler_allowed")),
            "redis_pinged": False,
            "celery_started": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        "backend_rows": backend_rows,
        "worker_module_rows": worker_module_rows,
        "counts": {
            "backend_count": len(backend_rows),
            "worker_module_count": len(worker_module_rows),
            "worker_module_ready_count": module_ready_count,
            "task_count": catalog.get("task_count", 0),
            "task_status_count": task_index.get("task_count", 0),
            "task_status_call_ledger_count": task_index.get("call_ledger_count", 0),
            "stub_task_count": task_implementation_status.get("stub_task_count", 0),
            "local_pipeline_task_count": task_implementation_status.get("local_pipeline_task_count", 0),
            "guarded_local_task_count": task_implementation_status.get("guarded_local_task_count", 0),
            "implemented_local_task_count": task_implementation_status.get("implemented_local_task_count", 0),
            "memory_task_count": task_persistence.get("memory_task_count", 0),
            "sqlite_task_count": task_persistence.get("sqlite_task_count", 0),
            "deduplicated_task_count": task_persistence.get("deduplicated_task_count", task_index.get("task_count", 0)),
            "production_blocker_count": len(production_readiness.get("production_blockers") or []),
            "production_blocker_audit_count": production_blocker_audit["blocking_criterion_count"],
            "worker_healthcheck_qa_pending_count": healthcheck_qa_contract["pending_criterion_count"],
            "worker_healthcheck_qa_blocking_count": healthcheck_qa_contract["blocking_criterion_count"],
            "worker_activation_review_step_count": activation_review_contract["review_step_count"],
            "worker_activation_blocker_count": activation_review_contract["activation_blocker_count"],
            "worker_activation_operator_action_count": activation_review_contract["operator_action_required_count"],
            "manual_preflight_step_count": len(manual_preflight_steps),
            "manual_preflight_operator_action_count": sum(1 for row in manual_preflight_steps if row.get("operator_action_required")),
            "dispatch_plan_task_count": len(dispatch_plan_rows),
            "dispatch_plan_queue_count": len({str(row.get("future_queue") or "") for row in dispatch_plan_rows if row.get("future_queue")}),
        },
        "policy": {
            "cache_api_external_calls": False,
            "does_not_ping_redis": True,
            "does_not_start_celery_worker": True,
            "does_not_start_scheduler": True,
            "does_not_schedule_real_tasks": True,
            "does_not_call_tushare": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "post_task_required_for_work": True,
            "worker_runtime_is_diagnostic_only": True,
            "task_implementation_status_is_read_only": True,
            "stub_tasks_must_not_be_reported_as_complete": True,
            "contains_secret": False,
        },
        "call_ledger": [
            {
                "api": "local_worker_runtime_cache",
                "source": "worker scaffold and task catalog",
                "row_count": len(worker_module_rows) + len(backend_rows),
                "local_fetched_at": _now_iso(),
                "call_status": "cache_read",
                "external": False,
            }
        ],
        "external_calls_triggered": False,
        "redis_pinged": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/worker/cache 只读检查本地 worker scaffold 和依赖可见性；不会连接 Redis。",
            "本页不会启动 Celery worker 或 APScheduler，不会调度真实 Tushare、DeepSeek 或 GitHub 任务。",
            "Worker runtime 只做诊断说明，不执行真实交易，不修改 strategy action。",
        ],
    }
    return _json_safe(packet)
