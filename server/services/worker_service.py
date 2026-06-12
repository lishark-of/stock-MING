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
            "task_types": ["refresh_factor_data", "run_factor_light"],
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
    ]


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
    production_readiness = _production_readiness(
        celery_available=celery_available,
        redis_available=redis_available,
        redis_configured=redis_configured,
        apscheduler_available=apscheduler_available,
        scheduled_refresh_enabled=scheduled_refresh_enabled,
    )
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
            "manual_preflight_step_count": len(manual_preflight_steps),
            "manual_preflight_operator_action_count": sum(1 for row in manual_preflight_steps if row.get("operator_action_required")),
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
