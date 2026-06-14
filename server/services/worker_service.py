from __future__ import annotations

import datetime as _dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from server.services import task_service
from storage.sqlite_meta import SQLiteMetaStore


PACKET_KEY = "command_center_3_worker_runtime_cache"
SCHEMA_VERSION = "worker_runtime_cache.v1"
SYNTHETIC_HEALTHCHECK_PACKET_KEY = "command_center_3_worker_synthetic_healthcheck_packet"
SYNTHETIC_HEALTHCHECK_SCHEMA_VERSION = "worker_synthetic_healthcheck.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "worker_runtime_cache_not_json_serializable"}


def _stable_json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _json_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_stable_json_text(payload).encode("utf-8")).hexdigest()


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
            "task_types": [
                "run_candidate_radar_full_pool_plan",
                "run_candidate_radar_full_pool_local_scan",
                "run_candidate_radar_deep_scan_plan",
                "run_candidate_radar_deep_scan_local_review",
            ],
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
        "run_storage_dataset_version_manifest_review",
        "run_storage_dataset_version_manifest_write",
        "run_storage_dataset_version_manifest_validate",
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


def _worker_queue_routing_contract(
    dispatch_plan_rows: list[dict[str, Any]],
    *,
    scheduled_refresh_enabled: bool,
    celery_available: bool,
    redis_configured: bool,
) -> dict[str, Any]:
    queue_policy = {
        "provider_refresh": {
            "queue_role": "provider-capable refresh tasks",
            "allowed_external_sources": ["Tushare"],
            "allows_provider_or_model": True,
        },
        "model_explain": {
            "queue_role": "model explanation tasks",
            "allowed_external_sources": ["DeepSeek"],
            "allows_provider_or_model": True,
        },
        "external_probe": {
            "queue_role": "explicit external probe tasks",
            "allowed_external_sources": ["GitHub"],
            "allows_provider_or_model": True,
        },
        "local_maintenance": {
            "queue_role": "local storage and maintenance tasks",
            "allowed_external_sources": [],
            "allows_provider_or_model": False,
        },
        "local_compute": {
            "queue_role": "local compute and cache tasks",
            "allowed_external_sources": [],
            "allows_provider_or_model": False,
        },
    }
    queue_rows: list[dict[str, Any]] = []
    for queue_name in sorted({str(row.get("future_queue") or "missing") for row in dispatch_plan_rows}):
        queue_tasks = [row for row in dispatch_plan_rows if str(row.get("future_queue") or "missing") == queue_name]
        possible_sources = sorted(
            {
                str(source)
                for row in queue_tasks
                for source in row.get("possible_external_sources") or []
                if str(source)
            }
        )
        policy = queue_policy.get(
            queue_name,
            {
                "queue_role": "unclassified queue",
                "allowed_external_sources": [],
                "allows_provider_or_model": False,
            },
        )
        queue_rows.append(
            {
                "queue": queue_name,
                "queue_role": policy["queue_role"],
                "task_count": len(queue_tasks),
                "task_types": [str(row.get("task_type") or "") for row in queue_tasks],
                "possible_external_sources": possible_sources,
                "allowed_external_sources": policy["allowed_external_sources"],
                "allows_provider_or_model": bool(policy["allows_provider_or_model"]),
                "all_tasks_button_gated": all(row.get("button_gated") is True for row in queue_tasks),
                "all_tasks_have_call_ledger_requirement": all(row.get("safe_task_log_required") is True for row in queue_tasks),
                "automatic_scheduler_allowed_count": sum(1 for row in queue_tasks if row.get("automatic_scheduler_allowed") is True),
                "cache_get_external_call_count": sum(1 for row in queue_tasks if row.get("cache_get_external_calls") is True),
                "redis_pinged": False,
                "celery_started": False,
                "scheduler_started": False,
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    external_capable_rows = [row for row in dispatch_plan_rows if int(row.get("possible_external_source_count") or 0) > 0]
    local_queue_external_rows = [
        row
        for row in external_capable_rows
        if str(row.get("future_queue") or "") in {"local_compute", "local_maintenance"}
    ]
    local_only_rows = [
        row
        for row in dispatch_plan_rows
        if str(row.get("future_queue") or "") in {"local_compute", "local_maintenance"}
    ]

    def _row(criterion: str, passed: bool, status: str, evidence: str, next_step: str) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": bool(passed),
            "evidence": evidence,
            "next_step": next_step,
            "cache_get_external_calls": False,
            "redis_pinged": False,
            "celery_started": False,
            "scheduler_started": False,
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
            "future_queues_declared",
            bool(dispatch_plan_rows) and all(str(row.get("future_queue") or "") for row in dispatch_plan_rows),
            "passed" if dispatch_plan_rows and all(str(row.get("future_queue") or "") for row in dispatch_plan_rows) else "blocked",
            f"task_count={len(dispatch_plan_rows)}; queue_names={[row['queue'] for row in queue_rows]}",
            "Every task must keep an explicit future_queue before Celery routing can be enabled.",
        ),
        _row(
            "queue_policy_rows_visible",
            {row["queue"] for row in queue_rows}.issubset(set(queue_policy)),
            "passed" if {row["queue"] for row in queue_rows}.issubset(set(queue_policy)) else "blocked",
            f"queue_policy_names={sorted(queue_policy)}",
            "Classify every future queue before worker activation.",
        ),
        _row(
            "all_tasks_button_gated",
            all(row.get("button_gated") is True for row in dispatch_plan_rows),
            "passed" if all(row.get("button_gated") is True for row in dispatch_plan_rows) else "blocked",
            "All queue-routed tasks must still require explicit POST/button gates.",
            "Keep worker routing behind task creation APIs.",
        ),
        _row(
            "external_capable_tasks_isolated_from_local_queues",
            not local_queue_external_rows,
            "passed" if not local_queue_external_rows else "blocked_external_task_in_local_queue",
            f"external_capable_task_count={len(external_capable_rows)}; local_queue_external_task_count={len(local_queue_external_rows)}",
            "Move provider/model/probe-capable tasks into provider_refresh, model_explain, or external_probe queues.",
        ),
        _row(
            "local_queues_are_local_only",
            all(int(row.get("possible_external_source_count") or 0) == 0 for row in local_only_rows),
            "passed" if all(int(row.get("possible_external_source_count") or 0) == 0 for row in local_only_rows) else "blocked_local_queue_external_source",
            f"local_queue_task_count={len(local_only_rows)}",
            "Keep local_compute/local_maintenance free of provider/model/probe-capable tasks.",
        ),
        _row(
            "provider_model_probe_queues_are_button_gated",
            all(row.get("button_gated") is True for row in external_capable_rows),
            "passed" if all(row.get("button_gated") is True for row in external_capable_rows) else "blocked_external_queue_not_gated",
            f"external_capable_task_count={len(external_capable_rows)}",
            "Provider/model/probe-capable queues must stay explicit and auditable.",
        ),
        _row(
            "scheduler_default_off_for_all_queues",
            not scheduled_refresh_enabled and all(row.get("automatic_scheduler_allowed") is False for row in dispatch_plan_rows),
            "passed" if not scheduled_refresh_enabled and all(row.get("automatic_scheduler_allowed") is False for row in dispatch_plan_rows) else "blocked_scheduler_enabled",
            f"scheduled_refresh_enabled={scheduled_refresh_enabled}",
            "Do not enable scheduler production routing until a separate scheduler activation review passes.",
        ),
        _row(
            "cache_get_never_dispatches_queue_work",
            all(row.get("cache_get_external_calls") is False for row in dispatch_plan_rows),
            "passed" if all(row.get("cache_get_external_calls") is False for row in dispatch_plan_rows) else "blocked_cache_get_dispatch",
            "GET /api/worker/cache reads routing metadata only.",
            "Preserve POST-only task dispatch.",
        ),
        _row(
            "celery_redis_not_started_by_routing_contract",
            celery_available in {True, False} and redis_configured in {True, False},
            "passed_no_process_start",
            f"celery_available={celery_available}; redis_configured={redis_configured}; celery_started=false; redis_pinged=false",
            "Only a future manual healthcheck may start Celery or prove Redis reachability.",
        ),
        _row(
            "no_trade_or_action_boundary",
            all(row.get("does_not_execute_trades") is True and row.get("does_not_modify_strategy_action") is True for row in dispatch_plan_rows),
            "passed",
            "Queue routing never executes trades or mutates strategy action.",
            "Keep real trading outside worker productionization.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "worker_queue_routing_contract.v1",
        "status": "worker_queue_routing_contract_ready_activation_pending" if not blockers else "worker_queue_routing_contract_blocked",
        "scope": "local_worker_queue_routing_contract_no_process_start",
        "ltg": "LTG-06/LTG-11",
        "queue_routing_contract_ready": not blockers,
        "task_count": len(dispatch_plan_rows),
        "queue_count": len(queue_rows),
        "external_capable_task_count": len(external_capable_rows),
        "local_queue_external_task_count": len(local_queue_external_rows),
        "queue_names": [row["queue"] for row in queue_rows],
        "queue_rows": queue_rows,
        "production_worker_complete": False,
        "activation_ready": False,
        "worker_started_by_contract": False,
        "redis_pinged_by_contract": False,
        "scheduler_started_by_contract": False,
        "task_dispatched_by_contract": False,
        "provider_model_task_dispatched_by_contract": False,
        "cache_get_external_calls": False,
        "contract_external_calls_triggered": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_worker_queue_routing_contract",
                "source": "worker dispatch plan and task catalog",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "queue_routing_contract_ready_activation_pending" if not blockers else "queue_routing_contract_blocked",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This contract fixes future Celery queue routing boundaries. It does not start Celery, ping Redis, start scheduler, dispatch tasks, call providers/models/probes, execute trades, or prove production worker completion.",
    }


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


def _worker_task_log_persistence_audit(
    *,
    task_index: dict[str, Any],
    task_persistence: dict[str, Any],
    task_persistence_source_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    task_count = int(task_index.get("task_count") or 0)
    task_log_count = int(task_index.get("task_log_count") or 0)
    call_ledger_count = int(task_index.get("call_ledger_count") or 0)
    memory_task_count = int(task_persistence.get("memory_task_count") or 0)
    sqlite_task_count = int(task_persistence.get("sqlite_task_count") or 0)
    deduplicated_task_count = int(task_persistence.get("deduplicated_task_count") or task_count)

    def _row(
        criterion: str,
        component: str,
        status: str,
        evidence: str,
        next_action: str,
        *,
        production_blocker: bool = False,
    ) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "component": component,
            "status": status,
            "evidence": evidence,
            "next_action": next_action,
            "production_blocker": bool(production_blocker and status != "passed"),
            "cache_api_can_execute": False,
            "cache_get_reads_raw_payload": False,
            "cache_get_writes_logs": False,
            "append_only_worker_log_verified": False,
            "healthcheck_executed": False,
            "worker_started": False,
            "redis_pinged": False,
            "scheduler_started": False,
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
            "local_task_status_index_visible",
            "task_status_index",
            "passed",
            f"GET /api/tasks exposes {task_count} deduplicated task row(s), {call_ledger_count} call_ledger row(s), and {task_log_count} task_log event(s).",
            "Keep Worker runtime cache consuming task status summaries instead of raw task payloads.",
        ),
        _row(
            "memory_sqlite_fallback_visible",
            "task_persistence",
            "passed" if task_persistence.get("sqlite_fallback_enabled") is not False else "blocked",
            f"memory={memory_task_count}; sqlite={sqlite_task_count}; deduplicated={deduplicated_task_count}; storage_backend={task_persistence.get('storage_backend') or 'unknown'}.",
            "Preserve SQLite fallback for local task state until production worker storage is explicitly enabled.",
        ),
        _row(
            "safe_task_log_fields_visible",
            "task_logs",
            "passed" if task_persistence.get("task_rows_include_task_log") is not False else "blocked",
            "Task status rows expose safe task_log metadata and the task status index reports task_log_count.",
            "Keep task logs redacted and structured when worker routing is added.",
        ),
        _row(
            "task_log_payload_redaction_boundary",
            "safety",
            "passed" if (task_index.get("policy") or {}).get("task_logs_include_no_raw_payload") is True else "blocked",
            "GET /api/tasks policy reports task_logs_include_no_raw_payload=true and contains_secret=false.",
            "Do not copy request payloads, provider responses, stack traces, token, key, or password values into worker logs.",
        ),
        _row(
            "task_log_external_boundary",
            "safety",
            "passed" if task_index.get("external_calls_triggered") is False else "blocked",
            "Task status index cache read does not call Redis, Tushare, DeepSeek, GitHub, or trading routes.",
            "Keep task log inspection cache-only; external work must stay behind explicit POST tasks.",
        ),
        _row(
            "append_only_worker_log_storage_verified",
            "worker_log_storage",
            "pending_worker_healthcheck",
            "Local safe task logs exist, but append-only worker log storage has not been verified across a live worker process.",
            "Verify append-only, redacted worker logs only after Celery/Redis is manually started and a synthetic healthcheck is explicitly run.",
            production_blocker=True,
        ),
        _row(
            "cross_process_task_log_round_trip_verified",
            "worker_log_storage",
            "pending_worker_healthcheck",
            "No live worker process round trip has been executed by this cache read.",
            "Use a future synthetic/local healthcheck to prove enqueue, execution, log persistence, and readback without provider/model/trading calls.",
            production_blocker=True,
        ),
    ]
    blocker_rows = [row for row in rows if row["production_blocker"]]
    return {
        "schema_version": "worker_task_log_persistence_audit.v1",
        "status": "local_task_log_persistence_ready_worker_append_only_pending",
        "scope": "local_task_log_persistence_audit_no_process_start",
        "mode": "cache_only_read_only_task_log_audit",
        "task_count": task_count,
        "task_log_count": task_log_count,
        "call_ledger_count": call_ledger_count,
        "memory_task_count": memory_task_count,
        "sqlite_task_count": sqlite_task_count,
        "deduplicated_task_count": deduplicated_task_count,
        "persistence_source_count": len(task_persistence_source_rows),
        "criterion_count": len(rows),
        "production_blocker_count": len(blocker_rows),
        "blocking_criteria": [str(row["criterion"]) for row in blocker_rows],
        "local_task_log_persistence_ready": True,
        "task_log_persistence_verified": False,
        "append_only_worker_log_verified": False,
        "cross_process_log_round_trip_verified": False,
        "healthcheck_executed": False,
        "production_worker_complete": False,
        "cache_get_reads_raw_payload": False,
        "cache_get_writes_logs": False,
        "cache_api_started_workers": False,
        "cache_api_pinged_redis": False,
        "cache_api_started_scheduler": False,
        "task_dispatched_by_cache_api": False,
        "cache_get_external_calls": False,
        "contains_secret": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
        "source_rows": task_persistence_source_rows,
        "note": "This audit proves local safe task-log visibility only. It does not prove append-only Celery worker logs, Redis broker reachability, synthetic healthcheck execution, or production worker completion.",
    }


def _missing_worker_synthetic_healthcheck_packet() -> dict[str, Any]:
    return {
        "packet_key": SYNTHETIC_HEALTHCHECK_PACKET_KEY,
        "schema_version": SYNTHETIC_HEALTHCHECK_SCHEMA_VERSION,
        "status": "synthetic_healthcheck_missing",
        "scope": "explicit_post_worker_synthetic_healthcheck_no_process_start",
        "mode": "button_gated_local_synthetic_healthcheck",
        "cache_only_placeholder": True,
        "synthetic_healthcheck_executed": False,
        "healthcheck_task_dispatched": False,
        "local_task_round_trip_verified": False,
        "task_log_round_trip_verified": False,
        "task_status_readback_verified": False,
        "healthcheck_hash_algorithm": "",
        "task_identity_sha256": "",
        "readback_task_identity_sha256": "",
        "task_readback_hash_matches": False,
        "safe_hash_payload_fields": [],
        "sqlite_task_metadata_visible": False,
        "celery_worker_started": False,
        "celery_process_visible": False,
        "redis_pinged": False,
        "redis_broker_reachable": False,
        "scheduler_started": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "cross_process_controls_verified": False,
        "cross_process_log_round_trip_verified": False,
        "append_only_worker_log_verified": False,
        "provider_model_task_validation_in_scope": False,
        "cache_get_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": [],
        "call_ledger": [
            {
                "api": "local_worker_synthetic_healthcheck_cache",
                "source": "sqlite_meta_packet_absence",
                "row_count": 0,
                "local_fetched_at": _now_iso(),
                "call_status": "cache_read_missing_no_task_dispatched",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [
            "尚未通过 POST /api/worker/synthetic-healthcheck 显式执行本地 synthetic healthcheck；GET cache 不会自动创建任务。"
        ],
    }


def _read_worker_synthetic_healthcheck_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(SYNTHETIC_HEALTHCHECK_PACKET_KEY)
    except Exception:
        packet = None
    if not isinstance(packet, dict):
        return _missing_worker_synthetic_healthcheck_packet()
    safe_packet = _json_safe(packet)
    safe_packet.setdefault("healthcheck_hash_algorithm", "")
    safe_packet.setdefault("task_identity_sha256", "")
    safe_packet.setdefault("readback_task_identity_sha256", "")
    safe_packet.setdefault("task_readback_hash_matches", False)
    safe_packet.setdefault("safe_hash_payload_fields", [])
    return safe_packet


def _synthetic_healthcheck_rows(task: dict[str, Any], readback: dict[str, Any] | None) -> list[dict[str, Any]]:
    task_log = task.get("task_log") if isinstance(task.get("task_log"), list) else []
    readback_log = readback.get("task_log") if isinstance(readback, dict) and isinstance(readback.get("task_log"), list) else []

    def _row(
        criterion: str,
        component: str,
        status: str,
        evidence: str,
        *,
        production_blocker: bool = False,
    ) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "component": component,
            "status": status,
            "passed": status == "passed",
            "evidence": evidence,
            "production_blocker": bool(production_blocker and status != "passed"),
            "cache_api_can_execute": False,
            "explicit_post_executed": True,
            "worker_started": False,
            "redis_pinged": False,
            "scheduler_started": False,
            "task_dispatched": criterion == "local_task_record_created",
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    return [
        _row(
            "local_task_record_created",
            "task_runtime",
            "passed" if task.get("task_id") else "blocked",
            f"task_id={task.get('task_id') or '--'}; status={task.get('status') or '--'}",
        ),
        _row(
            "local_task_status_round_trip",
            "task_runtime",
            "passed" if isinstance(readback, dict) and readback.get("status") == "success" else "blocked",
            f"readback_status={readback.get('status') if isinstance(readback, dict) else '--'}",
        ),
        _row(
            "local_task_log_round_trip",
            "task_logs",
            "passed" if len(task_log) > 0 and len(readback_log) > 0 else "blocked",
            f"task_log_count={len(task_log)}; readback_task_log_count={len(readback_log)}",
        ),
        _row(
            "celery_process_visible",
            "celery_worker",
            "pending_manual_worker_start",
            "Synthetic healthcheck does not inspect or start a live Celery worker process.",
            production_blocker=True,
        ),
        _row(
            "redis_broker_reachable",
            "redis_broker",
            "pending_manual_worker_start",
            "Synthetic healthcheck does not ping Redis and never exposes a Redis URL.",
            production_blocker=True,
        ),
        _row(
            "cross_process_controls_verified",
            "task_controls",
            "pending_manual_worker_start",
            "Retry/cancel/lock/dedupe across Celery process boundaries are not proven by local fallback.",
            production_blocker=True,
        ),
        _row(
            "append_only_worker_log_verified",
            "worker_log_storage",
            "pending_manual_worker_start",
            "Local task log readback is visible, but append-only Celery worker logs are not proven.",
            production_blocker=True,
        ),
        _row(
            "provider_model_boundary",
            "safety",
            "passed",
            "This healthcheck is synthetic/local only and cannot call Tushare, DeepSeek, GitHub, or trading code.",
        ),
        _row(
            "no_trade_no_action_mutation",
            "safety",
            "passed",
            "The synthetic task does not execute trades and does not modify strategy action.",
        ),
    ]


def _synthetic_task_identity_payload(task: dict[str, Any], *, task_log_count: int) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "task_type": task.get("task_type"),
        "status": task.get("status"),
        "progress": task.get("progress"),
        "current_step": task.get("current_step"),
        "output_packet_key": task.get("output_packet_key"),
        "task_log_count": task_log_count,
        "external_calls_triggered": task.get("external_calls_triggered") is True,
        "tushare_called": task.get("tushare_called") is True,
        "deepseek_called": task.get("deepseek_called") is True,
        "github_called": task.get("github_called") is True,
        "does_not_execute_trades": task.get("does_not_execute_trades") is not False,
        "does_not_modify_strategy_action": task.get("does_not_modify_strategy_action") is not False,
    }


def run_worker_synthetic_healthcheck(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_worker_synthetic_healthcheck",
        output_packet_key=SYNTHETIC_HEALTHCHECK_PACKET_KEY,
        payload=payload,
        current_step="synthetic_healthcheck_queued_no_external_call",
        warnings=[
            "Worker synthetic healthcheck 只验证本地 task/status/log 往返；不会启动 Celery、ping Redis、启动 scheduler、调用 provider/model/probe 或执行交易。"
        ],
    )
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="running",
        progress=0.5,
        current_step="synthetic_healthcheck_running_local_task_store_only",
    ) or task
    ledger = [
        {
            "api": "local_worker_synthetic_healthcheck",
            "source": "local_task_store",
            "row_count": 1,
            "task_id": task.get("task_id"),
            "local_fetched_at": _now_iso(),
            "call_status": "synthetic_healthcheck_completed_no_external_call",
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "redis_pinged": False,
            "celery_started": False,
            "scheduler_started": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "error_message_safe": "",
        }
    ]
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="success",
        progress=1.0,
        current_step="synthetic_healthcheck_completed_local_task_store_only",
        call_ledger=ledger,
        warning="worker_synthetic_healthcheck_completed_no_external_call",
    ) or task
    readback = task_service.read_task_status(str(task.get("task_id") or ""))
    task_log = task.get("task_log") if isinstance(task.get("task_log"), list) else []
    readback_log = readback.get("task_log") if isinstance(readback, dict) and isinstance(readback.get("task_log"), list) else []
    task_identity_payload = _synthetic_task_identity_payload(task, task_log_count=len(task_log))
    readback_identity_payload = _synthetic_task_identity_payload(readback, task_log_count=len(readback_log)) if isinstance(readback, dict) else {}
    task_identity_sha256 = _json_sha256(task_identity_payload)
    readback_task_identity_sha256 = _json_sha256(readback_identity_payload) if readback_identity_payload else ""
    task_readback_hash_matches = bool(
        readback_task_identity_sha256 and task_identity_sha256 == readback_task_identity_sha256
    )
    rows = _synthetic_healthcheck_rows(task, readback)
    rows.append(
        {
            "criterion": "task_readback_fingerprint_matches",
            "component": "task_runtime",
            "status": "passed" if task_readback_hash_matches else "blocked",
            "passed": task_readback_hash_matches,
            "evidence": f"hash_algorithm=sha256; hash_matches={str(task_readback_hash_matches).lower()}",
            "production_blocker": False,
            "cache_api_can_execute": False,
            "explicit_post_executed": True,
            "worker_started": False,
            "redis_pinged": False,
            "scheduler_started": False,
            "task_dispatched": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    )
    blocker_rows = [row for row in rows if row.get("production_blocker")]
    packet = {
        "packet_key": SYNTHETIC_HEALTHCHECK_PACKET_KEY,
        "schema_version": SYNTHETIC_HEALTHCHECK_SCHEMA_VERSION,
        "status": "synthetic_healthcheck_passed_local_task_store_only"
        if not any(row["status"] == "blocked" for row in rows)
        else "synthetic_healthcheck_local_blocked",
        "scope": "explicit_post_worker_synthetic_healthcheck_no_process_start",
        "mode": "button_gated_local_synthetic_healthcheck",
        "executed_at": _now_iso(),
        "task_id": task.get("task_id"),
        "task_status": task.get("status"),
        "task_type": task.get("task_type"),
        "output_packet_key": SYNTHETIC_HEALTHCHECK_PACKET_KEY,
        "synthetic_healthcheck_executed": True,
        "healthcheck_task_dispatched": True,
        "local_task_round_trip_verified": isinstance(readback, dict) and readback.get("status") == "success",
        "task_log_round_trip_verified": len(task_log) > 0 and len(readback_log) > 0,
        "task_status_readback_verified": isinstance(readback, dict),
        "healthcheck_hash_algorithm": "sha256",
        "task_identity_sha256": task_identity_sha256,
        "readback_task_identity_sha256": readback_task_identity_sha256,
        "task_readback_hash_matches": task_readback_hash_matches,
        "safe_hash_payload_fields": [
            "task_id",
            "task_type",
            "status",
            "progress",
            "current_step",
            "output_packet_key",
            "task_log_count",
            "external/tushare/deepseek/github boundary flags",
            "trade/action boundary flags",
        ],
        "sqlite_task_metadata_visible": bool(readback and readback.get("storage_source") in {"memory_and_sqlite", "sqlite_meta"}),
        "task_log_count": len(task_log),
        "readback_task_log_count": len(readback_log),
        "call_ledger_count": len(ledger),
        "production_blocker_count": len(blocker_rows),
        "production_blockers": [str(row["criterion"]) for row in blocker_rows],
        "celery_worker_started": False,
        "celery_process_visible": False,
        "redis_pinged": False,
        "redis_broker_reachable": False,
        "scheduler_started": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "cross_process_controls_verified": False,
        "cross_process_log_round_trip_verified": False,
        "append_only_worker_log_verified": False,
        "provider_model_task_validation_in_scope": False,
        "cache_get_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "task_summary": {
            "task_id": task.get("task_id"),
            "task_type": task.get("task_type"),
            "status": task.get("status"),
            "progress": task.get("progress"),
            "current_step": task.get("current_step"),
            "storage_source": readback.get("storage_source") if isinstance(readback, dict) else None,
            "task_log_count": len(task_log),
            "call_ledger_count": len(task.get("call_ledger") or []),
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        "call_ledger": ledger,
        "warnings": [
            "这是显式 POST 的本地 synthetic healthcheck，只证明本地 task/status/log 往返。",
            "它不启动 Celery、不 ping Redis、不启动 scheduler、不调用 Tushare/DeepSeek/GitHub、不执行真实交易，也不代表 production worker 完成。",
        ],
    }
    packet = _json_safe(packet)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(SYNTHETIC_HEALTHCHECK_PACKET_KEY, packet)
    except Exception:
        packet.setdefault("warnings", []).append("worker_synthetic_healthcheck_packet_persist_failed_safe")
    return packet


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


def _worker_production_readiness_receipt(
    *,
    production_blocker_audit: dict[str, Any],
    healthcheck_qa_contract: dict[str, Any],
    task_log_persistence_audit: dict[str, Any],
    synthetic_healthcheck: dict[str, Any],
    activation_review_contract: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    known_post_routes = (catalog.get("route_coverage") or {}).get("known_post_routes") or []
    route_button_gated = bool((catalog.get("policy") or {}).get("all_known_post_routes_button_gated"))
    production_blocker_count = int(production_blocker_audit.get("blocking_criterion_count") or 0)
    healthcheck_pending_count = int(healthcheck_qa_contract.get("pending_criterion_count") or 0)
    task_log_blocker_count = int(task_log_persistence_audit.get("production_blocker_count") or 0)
    activation_blocker_count = int(activation_review_contract.get("activation_blocker_count") or 0)
    synthetic_executed = bool(synthetic_healthcheck.get("synthetic_healthcheck_executed") is True)
    local_contract_ready = (
        production_blocker_audit.get("schema_version") == "worker_production_blocker_audit.v1"
        and healthcheck_qa_contract.get("schema_version") == "worker_healthcheck_qa_contract.v1"
        and task_log_persistence_audit.get("schema_version") == "worker_task_log_persistence_audit.v1"
        and synthetic_healthcheck.get("schema_version") == "worker_synthetic_healthcheck.v1"
        and activation_review_contract.get("schema_version") == "worker_activation_review_contract.v1"
        and "POST /api/worker/synthetic-healthcheck" in known_post_routes
        and route_button_gated
        and production_blocker_audit.get("cache_get_external_calls") is False
        and healthcheck_qa_contract.get("cache_get_external_calls") is False
        and task_log_persistence_audit.get("cache_get_writes_logs") is False
        and activation_review_contract.get("cache_get_external_calls") is False
    )
    ready_for_explicit_synthetic_healthcheck = bool(local_contract_ready)
    ready_for_manual_activation_review = bool(local_contract_ready and synthetic_executed and production_blocker_count == 0)

    def _row(criterion: str, status: str, detail: str, required_evidence: str) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": status == "passed",
            "blocks_production_worker": status != "passed",
            "detail": detail,
            "required_evidence": required_evidence,
            "external_calls_triggered": False,
            "redis_pinged": False,
            "celery_started": False,
            "scheduler_started": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    rows = [
        _row(
            "local_worker_contracts_visible",
            "passed" if local_contract_ready else "blocked",
            "Worker cache exposes blocker audit, healthcheck QA, task-log audit, synthetic healthcheck state, activation review, and POST route coverage.",
            "All local contracts and route coverage remain present in GET /api/worker/cache.",
        ),
        _row(
            "explicit_post_synthetic_healthcheck_boundary",
            "passed" if "POST /api/worker/synthetic-healthcheck" in known_post_routes and route_button_gated else "blocked",
            "Synthetic healthcheck is visible only as an explicit POST route; GET cache may read the last packet but cannot run it.",
            "Operator explicitly runs POST /api/worker/synthetic-healthcheck.",
        ),
        _row(
            "cache_get_no_process_start_boundary",
            "passed",
            "GET cache does not start Celery, ping Redis, start APScheduler, dispatch tasks, or call providers/models/probes.",
            "Keep all process and network proof in explicit future tasks.",
        ),
        _row(
            "scheduler_default_off_boundary",
            "passed" if activation_review_contract.get("scheduler_started_by_cache_api") is False else "blocked",
            "Scheduler remains default-off and cache GET does not start it.",
            "Future production scheduler design stays separately approved and explicitly enabled.",
        ),
        _row(
            "provider_model_isolation_boundary",
            "passed",
            "Worker readiness receipt does not schedule Tushare, DeepSeek, GitHub, or real trading tasks.",
            "Provider/model tasks stay button-gated with call_ledger.",
        ),
        _row(
            "celery_redis_process_readiness_pending",
            "blocked" if production_blocker_count > 0 else "passed",
            f"{production_blocker_count} production worker blocker(s) remain in the blocker audit.",
            "Manual Celery worker start, Redis broker proof, queue contract, and stub migration evidence.",
        ),
        _row(
            "cross_process_task_controls_pending",
            "blocked" if healthcheck_pending_count > 0 or task_log_blocker_count > 0 else "passed",
            f"{healthcheck_pending_count} healthcheck QA item(s) and {task_log_blocker_count} task-log persistence item(s) remain pending.",
            "Cross-process retry/cancel/lock/dedupe/task-log healthcheck evidence.",
        ),
        _row(
            "manual_activation_review_pending",
            "blocked" if activation_blocker_count > 0 or not ready_for_manual_activation_review else "passed",
            f"{activation_blocker_count} activation blocker(s) remain; synthetic healthcheck executed={synthetic_executed}.",
            "Manual activation review after blockers clear and explicit synthetic healthcheck passes.",
        ),
        _row(
            "production_completion_evidence_ticket",
            "blocked",
            "This receipt is next-step evidence only; production_worker_complete remains false.",
            "A future production worker evidence ticket must prove Celery/Redis runtime, cross-process controls, logs, scheduler default-off, and external-call isolation.",
        ),
    ]
    blocked_rows = [row for row in rows if row["status"] != "passed"]
    status = (
        "worker_readiness_receipt_ready_activation_review_pending"
        if ready_for_manual_activation_review
        else "worker_readiness_receipt_ready_synthetic_healthcheck_pending"
        if local_contract_ready
        else "worker_readiness_receipt_blocked_local_contract"
    )
    return {
        "schema_version": "worker_production_readiness_receipt.v1",
        "status": status,
        "scope": "local_worker_production_readiness_receipt_no_process_start",
        "ltg": "LTG-06",
        "local_receipt_ready": bool(local_contract_ready),
        "ready_for_explicit_synthetic_healthcheck": ready_for_explicit_synthetic_healthcheck,
        "ready_for_manual_activation_review": ready_for_manual_activation_review,
        "allowed_next_step": "explicit_post_worker_synthetic_healthcheck_then_manual_activation_review",
        "not_allowed_next_steps": [
            "GET /api/worker/cache worker process start",
            "GET /api/worker/cache Redis ping",
            "GET /api/worker/cache scheduler start",
            "GET /api/worker/cache task dispatch",
            "automatic Tushare/DeepSeek/GitHub task scheduling",
            "synthetic healthcheck as production worker completion",
            "readiness receipt as production worker completion",
        ],
        "missing_evidence_items": [
            "celery_worker_process_evidence",
            "redis_broker_reachability_evidence",
            "cross_process_retry_cancel_lock_dedupe_evidence",
            "append_only_worker_task_log_evidence",
            "scheduler_default_off_runtime_evidence",
            "provider_model_no_autoschedule_evidence",
        ],
        "production_blocker_count": production_blocker_count,
        "healthcheck_pending_count": healthcheck_pending_count,
        "task_log_persistence_blocker_count": task_log_blocker_count,
        "activation_blocker_count": activation_blocker_count,
        "synthetic_healthcheck_executed": synthetic_executed,
        "production_worker_complete": False,
        "worker_started_by_receipt": False,
        "celery_worker_started": False,
        "redis_pinged_by_receipt": False,
        "redis_pinged": False,
        "scheduler_started_by_receipt": False,
        "scheduler_started": False,
        "task_dispatched_by_receipt": False,
        "provider_model_task_dispatched_by_receipt": False,
        "cache_get_external_calls": False,
        "receipt_external_calls_triggered": False,
        "external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "criterion_count": len(rows),
        "blocking_criterion_count": len(blocked_rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_worker_production_readiness_receipt",
                "source": "worker cache local contracts",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_readiness_receipt",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This receipt only chooses the next safe LTG-06 step. It does not start Celery, ping Redis, run healthcheck, start scheduler, dispatch tasks, call providers/models/probes, execute trades, modify strategy action, or prove production worker completion.",
    }


def _worker_production_activation_receipt(
    *,
    production_blocker_audit: dict[str, Any],
    healthcheck_qa_contract: dict[str, Any],
    task_log_persistence_audit: dict[str, Any],
    synthetic_healthcheck: dict[str, Any],
    activation_review_contract: dict[str, Any],
    readiness_receipt: dict[str, Any],
) -> dict[str, Any]:
    synthetic_executed = bool(synthetic_healthcheck.get("synthetic_healthcheck_executed") is True)
    production_blocker_count = int(production_blocker_audit.get("blocking_criterion_count") or 0)
    healthcheck_pending_count = int(healthcheck_qa_contract.get("pending_criterion_count") or 0)
    task_log_blocker_count = int(task_log_persistence_audit.get("production_blocker_count") or 0)
    activation_blocker_count = int(activation_review_contract.get("activation_blocker_count") or 0)
    local_activation_ready = (
        readiness_receipt.get("local_receipt_ready") is True
        and production_blocker_audit.get("schema_version") == "worker_production_blocker_audit.v1"
        and healthcheck_qa_contract.get("schema_version") == "worker_healthcheck_qa_contract.v1"
        and task_log_persistence_audit.get("schema_version") == "worker_task_log_persistence_audit.v1"
        and synthetic_healthcheck.get("schema_version") == "worker_synthetic_healthcheck.v1"
        and activation_review_contract.get("schema_version") == "worker_activation_review_contract.v1"
        and readiness_receipt.get("cache_get_external_calls") is False
        and activation_review_contract.get("cache_get_external_calls") is False
    )

    def _row(criterion: str, passed: bool, status: str, evidence: str, next_step: str) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": passed,
            "evidence": evidence,
            "next_step": next_step,
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
            "local_readiness_receipt_ready",
            bool(readiness_receipt.get("local_receipt_ready")),
            "passed" if readiness_receipt.get("local_receipt_ready") else "blocked",
            "worker_production_readiness_receipt is visible and keeps process start, Redis ping, scheduler start, task dispatch, and provider/model scheduling forbidden.",
            "run explicit synthetic healthcheck before any manual activation review",
        ),
        _row(
            "synthetic_healthcheck_execution_required",
            synthetic_executed,
            "passed" if synthetic_executed else "pending_explicit_post_healthcheck",
            f"synthetic_healthcheck_executed={synthetic_executed}; GET cache never executes the healthcheck.",
            "POST /api/worker/synthetic-healthcheck must run and remain local/no-provider/no-trade",
        ),
        _row(
            "celery_worker_manual_start_required",
            False,
            "pending_manual_worker_start",
            "No live Celery worker process is started or inspected by this cache receipt.",
            "manually start Celery after Redis broker and queue contracts are reviewed",
        ),
        _row(
            "redis_broker_reachability_required",
            False,
            "pending_manual_broker_check",
            "Redis is not pinged by GET cache or by this activation receipt.",
            "prove Redis reachability through a future explicit, redacted healthcheck",
        ),
        _row(
            "cross_process_controls_required",
            False,
            "pending_worker_semantics",
            f"{healthcheck_pending_count} healthcheck QA item(s) remain pending for retry/cancel/lock/dedupe semantics.",
            "verify retry, cancel, lock, and dedupe across a live worker process",
        ),
        _row(
            "append_only_log_required",
            False,
            "pending_worker_log_validation",
            f"{task_log_blocker_count} task-log persistence blocker(s) remain for append-only worker logs.",
            "verify redacted append-only worker logs after a manual worker start",
        ),
        _row(
            "manual_activation_review_required",
            False,
            "pending_manual_activation_review",
            f"{activation_blocker_count} activation review blocker(s) remain visible.",
            "complete manual activation review after healthcheck and blocker rows clear",
        ),
        _row(
            "scheduler_default_off_boundary",
            activation_review_contract.get("scheduler_started_by_cache_api") is False,
            "passed" if activation_review_contract.get("scheduler_started_by_cache_api") is False else "blocked",
            "Scheduler remains default-off and is not started by cache or receipt paths.",
            "keep scheduler production enablement separate and explicit",
        ),
        _row(
            "provider_model_isolation_boundary",
            activation_review_contract.get("cache_get_external_calls") is False,
            "passed" if activation_review_contract.get("cache_get_external_calls") is False else "blocked",
            "Tushare, DeepSeek, and GitHub-capable work remains button/POST gated and is not autoscheduled.",
            "preserve call_ledger and explicit task gating for provider/model tasks",
        ),
        _row(
            "no_trade_or_action_boundary",
            True,
            "passed",
            "Worker activation receipt does not execute trades and does not mutate strategy action.",
            "keep real trading disconnected from worker productionization",
        ),
        _row(
            "production_completion_evidence_required",
            False,
            "pending_production_evidence",
            "activation receipt is not production worker completion evidence.",
            "require a future production worker evidence ticket before production_worker_complete can become true",
        ),
    ]
    blocker_rows = [row for row in rows if row["status"] != "passed"]
    return {
        "schema_version": "worker_production_activation_receipt.v1",
        "status": "worker_activation_receipt_ready_production_blocked"
        if local_activation_ready
        else "worker_activation_receipt_blocked_local_contract",
        "scope": "local_worker_production_activation_receipt_no_process_start",
        "ltg": "LTG-06",
        "local_activation_receipt_ready": local_activation_ready,
        "allowed_next_step": "explicit_synthetic_healthcheck_then_manual_celery_redis_activation_review",
        "not_allowed_next_steps": [
            "GET /api/worker/cache worker process start",
            "GET /api/worker/cache Redis ping",
            "GET /api/worker/cache scheduler start",
            "GET /api/worker/cache task dispatch",
            "automatic Tushare/DeepSeek/GitHub task scheduling",
            "synthetic healthcheck as production worker completion",
            "activation receipt as production worker completion",
        ],
        "missing_evidence_items": [
            "explicit synthetic healthcheck execution",
            "celery worker process evidence",
            "redis broker reachability evidence",
            "cross-process retry/cancel/lock/dedupe evidence",
            "append-only worker task log evidence",
            "scheduler default-off runtime evidence",
            "provider/model no-autoschedule evidence",
            "manual activation approval",
            "production worker promotion evidence",
        ],
        "production_worker_complete": False,
        "activation_ready": False,
        "synthetic_healthcheck_executed": synthetic_executed,
        "healthcheck_executed_by_receipt": False,
        "worker_started_by_receipt": False,
        "celery_worker_started": False,
        "redis_pinged_by_receipt": False,
        "redis_pinged": False,
        "scheduler_started_by_receipt": False,
        "scheduler_started": False,
        "task_dispatched_by_receipt": False,
        "provider_model_task_dispatched_by_receipt": False,
        "cache_get_external_calls": False,
        "receipt_external_calls_triggered": False,
        "external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "production_blocker_count": production_blocker_count,
        "healthcheck_pending_count": healthcheck_pending_count,
        "task_log_persistence_blocker_count": task_log_blocker_count,
        "activation_blocker_count": activation_blocker_count,
        "blocking_criterion_count": len(blocker_rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_worker_production_activation_receipt",
                "source": "worker cache local activation contracts",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_activation_receipt_production_blocked",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This activation receipt is a local LTG-06 production-start checklist. It does not start Celery, ping Redis, run healthcheck, start scheduler, dispatch tasks, call providers/models/probes, execute trades, modify strategy action, or prove production worker completion.",
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
    task_log_persistence_audit = _worker_task_log_persistence_audit(
        task_index=task_index,
        task_persistence=task_persistence,
        task_persistence_source_rows=task_persistence_source_rows,
    )
    synthetic_healthcheck = _read_worker_synthetic_healthcheck_packet()
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
    queue_routing_contract = _worker_queue_routing_contract(
        dispatch_plan_rows,
        scheduled_refresh_enabled=scheduled_refresh_enabled,
        celery_available=celery_available,
        redis_configured=redis_configured,
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
    production_readiness["worker_task_log_persistence_audit"] = task_log_persistence_audit
    production_readiness["worker_task_log_persistence_rows"] = task_log_persistence_audit["rows"]
    production_readiness["worker_queue_routing_contract"] = queue_routing_contract
    production_readiness["worker_queue_routing_rows"] = queue_routing_contract["rows"]
    production_readiness["worker_queue_routing_queue_rows"] = queue_routing_contract["queue_rows"]
    production_readiness["worker_synthetic_healthcheck"] = synthetic_healthcheck
    production_readiness["worker_synthetic_healthcheck_rows"] = synthetic_healthcheck.get("rows") or []
    activation_review_contract = _worker_activation_review_contract(
        redis_configured=redis_configured,
        scheduled_refresh_enabled=scheduled_refresh_enabled,
        dispatch_plan_rows=dispatch_plan_rows,
        production_blocker_audit=production_blocker_audit,
        healthcheck_qa_contract=healthcheck_qa_contract,
    )
    production_readiness["worker_activation_review_contract"] = activation_review_contract
    production_readiness["worker_activation_review_rows"] = activation_review_contract["rows"]
    production_readiness_receipt = _worker_production_readiness_receipt(
        production_blocker_audit=production_blocker_audit,
        healthcheck_qa_contract=healthcheck_qa_contract,
        task_log_persistence_audit=task_log_persistence_audit,
        synthetic_healthcheck=synthetic_healthcheck,
        activation_review_contract=activation_review_contract,
        catalog=catalog,
    )
    production_readiness["worker_production_readiness_receipt"] = production_readiness_receipt
    production_readiness["worker_production_readiness_receipt_rows"] = production_readiness_receipt["rows"]
    production_activation_receipt = _worker_production_activation_receipt(
        production_blocker_audit=production_blocker_audit,
        healthcheck_qa_contract=healthcheck_qa_contract,
        task_log_persistence_audit=task_log_persistence_audit,
        synthetic_healthcheck=synthetic_healthcheck,
        activation_review_contract=activation_review_contract,
        readiness_receipt=production_readiness_receipt,
    )
    production_readiness["worker_production_activation_receipt"] = production_activation_receipt
    production_readiness["worker_production_activation_rows"] = production_activation_receipt["rows"]
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
        "worker_task_log_persistence_audit": task_log_persistence_audit,
        "worker_task_log_persistence_rows": task_log_persistence_audit["rows"],
        "worker_queue_routing_contract": queue_routing_contract,
        "worker_queue_routing_rows": queue_routing_contract["rows"],
        "worker_queue_routing_queue_rows": queue_routing_contract["queue_rows"],
        "worker_synthetic_healthcheck": synthetic_healthcheck,
        "worker_synthetic_healthcheck_rows": synthetic_healthcheck.get("rows") or [],
        "worker_activation_review_contract": activation_review_contract,
        "worker_activation_review_rows": activation_review_contract["rows"],
        "worker_production_readiness_receipt": production_readiness_receipt,
        "worker_production_readiness_receipt_rows": production_readiness_receipt["rows"],
        "worker_production_activation_receipt": production_activation_receipt,
        "worker_production_activation_rows": production_activation_receipt["rows"],
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
            "worker_task_log_persistence_criterion_count": task_log_persistence_audit["criterion_count"],
            "worker_task_log_persistence_blocker_count": task_log_persistence_audit["production_blocker_count"],
            "worker_task_log_count": task_log_persistence_audit["task_log_count"],
            "worker_queue_routing_queue_count": queue_routing_contract["queue_count"],
            "worker_queue_routing_task_count": queue_routing_contract["task_count"],
            "worker_queue_routing_external_capable_task_count": queue_routing_contract["external_capable_task_count"],
            "worker_queue_routing_blocker_count": queue_routing_contract["blocking_criterion_count"],
            "worker_synthetic_healthcheck_executed": 1 if synthetic_healthcheck.get("synthetic_healthcheck_executed") is True else 0,
            "worker_synthetic_healthcheck_blocker_count": synthetic_healthcheck.get("production_blocker_count", 0),
            "worker_activation_review_step_count": activation_review_contract["review_step_count"],
            "worker_activation_blocker_count": activation_review_contract["activation_blocker_count"],
            "worker_activation_operator_action_count": activation_review_contract["operator_action_required_count"],
            "worker_production_readiness_receipt_ready": 1 if production_readiness_receipt.get("local_receipt_ready") else 0,
            "worker_production_readiness_receipt_blocker_count": production_readiness_receipt["blocking_criterion_count"],
            "worker_production_activation_receipt_ready": 1
            if production_activation_receipt.get("local_activation_receipt_ready")
            else 0,
            "worker_production_activation_blocker_count": production_activation_receipt["blocking_criterion_count"],
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
            "worker_task_log_persistence_audit_is_read_only": True,
            "worker_task_log_persistence_is_not_worker_healthcheck": True,
            "worker_task_log_persistence_is_not_production_complete": True,
            "worker_queue_routing_contract_is_local": True,
            "worker_queue_routing_contract_is_not_process_start": True,
            "worker_queue_routing_contract_is_not_production_completion": True,
            "worker_synthetic_healthcheck_requires_explicit_post": True,
            "cache_get_executes_synthetic_healthcheck": False,
            "worker_synthetic_healthcheck_is_not_production_complete": True,
            "worker_production_readiness_receipt_is_local": True,
            "worker_production_readiness_receipt_is_not_process_start": True,
            "worker_production_readiness_receipt_is_not_production_completion": True,
            "worker_production_activation_receipt_is_local": True,
            "worker_production_activation_receipt_is_not_process_start": True,
            "worker_production_activation_receipt_is_not_production_completion": True,
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
        ]
        + queue_routing_contract["call_ledger"]
        + production_readiness_receipt["call_ledger"]
        + production_activation_receipt["call_ledger"],
        "queue_call_ledger": queue_routing_contract["call_ledger"],
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
