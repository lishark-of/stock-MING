from __future__ import annotations

import datetime as _dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from typing import Any

from server.services import task_service
from storage.sqlite_meta import SQLiteMetaStore


PACKET_KEY = "command_center_3_worker_runtime_cache"
SCHEMA_VERSION = "worker_runtime_cache.v1"
SYNTHETIC_HEALTHCHECK_PACKET_KEY = "command_center_3_worker_synthetic_healthcheck_packet"
SYNTHETIC_HEALTHCHECK_SCHEMA_VERSION = "worker_synthetic_healthcheck.v1"
ACTIVATION_REVIEW_PACKET_KEY = "command_center_3_worker_activation_review_packet"
ACTIVATION_REVIEW_SCHEMA_VERSION = "worker_activation_review_task_receipt.v1"
PRODUCTION_EVIDENCE_PLAN_PACKET_KEY = "command_center_3_worker_production_evidence_plan_packet"
PRODUCTION_EVIDENCE_PLAN_SCHEMA_VERSION = "worker_production_evidence_plan_receipt.v1"
RUNTIME_QA_EXECUTION_REQUEST_PACKET_KEY = "command_center_3_worker_runtime_qa_execution_request_packet"
RUNTIME_QA_EXECUTION_REQUEST_SCHEMA_VERSION = "worker_runtime_qa_execution_request_receipt.v1"
RUNTIME_QA_DRY_RUN_PACKET_KEY = "command_center_3_worker_runtime_qa_dry_run_packet"
RUNTIME_QA_DRY_RUN_SCHEMA_VERSION = "worker_runtime_qa_dry_run_receipt.v1"
RUNTIME_QA_EXECUTION_PACKET_KEY = "command_center_3_worker_runtime_qa_execution_packet"
RUNTIME_QA_EXECUTION_SCHEMA_VERSION = "worker_runtime_qa_execution_receipt.v1"
PRODUCTION_PROMOTION_REVIEW_PACKET_KEY = "command_center_3_worker_production_promotion_review_packet"
PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION = "worker_production_promotion_review_receipt.v1"
WORKER_RUNTIME_DURABLE_EVIDENCE_SCHEMA_VERSION = "worker_runtime_durable_evidence_recipe.v1"
WORKER_RUNTIME_STAGE_SCOPE_SCHEMA_VERSION = "worker_runtime_evidence_stage_scope_manifest.v1"
WORKER_RUNTIME_EVIDENCE_STAGE_KEYS = [
    "celery_process",
    "redis_broker",
    "local_fallback_round_trip",
    "cross_process_retry_cancel_lock_dedupe",
    "append_only_worker_logs",
    "scheduler_default_off_runtime",
    "provider_model_no_autoschedule_boundary",
    "no_trade_no_action_boundary",
    "production_worker_promotion_review",
]
WORKER_RUNTIME_EVIDENCE_STAGE_LABELS = {
    "celery_process": "Celery process evidence",
    "redis_broker": "Redis broker evidence",
    "local_fallback_round_trip": "Local fallback round-trip evidence",
    "cross_process_retry_cancel_lock_dedupe": "Cross-process controls evidence",
    "append_only_worker_logs": "Append-only worker log evidence",
    "scheduler_default_off_runtime": "Scheduler default-off runtime evidence",
    "provider_model_no_autoschedule_boundary": "Provider/model no-autoschedule boundary",
    "no_trade_no_action_boundary": "No-trade/no-action boundary",
    "production_worker_promotion_review": "Production worker promotion review evidence",
}
WORKER_RUNTIME_QA_EXECUTION_PHASES = [
    "evidence_plan_scope_ticket",
    "celery_process_manual_start",
    "redis_broker_redacted_reachability",
    "queue_binding_and_synthetic_round_trip",
    "cross_process_retry_cancel_lock_dedupe",
    "append_only_worker_log_validation",
    "scheduler_default_off_runtime",
    "provider_model_no_autoschedule_boundary",
    "local_fallback_rollback_plan",
    "production_worker_promotion_review",
]
WORKER_RUNTIME_QA_EXECUTION_PHASE_LABELS = {
    "evidence_plan_scope_ticket": "Evidence-plan scope ticket",
    "celery_process_manual_start": "Celery process manual start evidence",
    "redis_broker_redacted_reachability": "Redis broker redacted reachability evidence",
    "queue_binding_and_synthetic_round_trip": "Queue binding and synthetic round-trip evidence",
    "cross_process_retry_cancel_lock_dedupe": "Cross-process retry/cancel/lock/dedupe evidence",
    "append_only_worker_log_validation": "Append-only worker log validation",
    "scheduler_default_off_runtime": "Scheduler default-off runtime evidence",
    "provider_model_no_autoschedule_boundary": "Provider/model no-autoschedule boundary",
    "local_fallback_rollback_plan": "Local fallback rollback plan",
    "production_worker_promotion_review": "Production worker promotion review",
}
WORKER_RUNTIME_DURABLE_EVIDENCE_KEYS = [
    "production_blocker_audit_visible",
    "healthcheck_qa_contract_visible",
    "task_log_persistence_audit_visible",
    "queue_routing_contract_visible",
    "readiness_receipt_visible",
    "activation_receipt_visible",
    "production_evidence_plan_visible",
    "runtime_qa_execution_recipe_ready",
    "runtime_qa_execution_request_visible",
    "runtime_qa_dry_run_receipt_visible",
    "celery_process_evidence_required",
    "redis_broker_reachability_evidence_required",
    "queue_round_trip_evidence_required",
    "cross_process_controls_evidence_required",
    "append_only_worker_log_evidence_required",
    "scheduler_default_off_runtime_evidence_required",
    "provider_model_no_autoschedule_runtime_evidence_required",
    "local_fallback_rollback_evidence_required",
    "production_worker_promotion_review_required",
    "no_process_provider_trade_secret_boundary",
]
WORKER_RUNTIME_DURABLE_EVIDENCE_LABELS = {
    "production_blocker_audit_visible": "Production blocker audit visible",
    "healthcheck_qa_contract_visible": "Healthcheck QA contract visible",
    "task_log_persistence_audit_visible": "Task log persistence audit visible",
    "queue_routing_contract_visible": "Queue routing contract visible",
    "readiness_receipt_visible": "Readiness receipt visible",
    "activation_receipt_visible": "Activation receipt visible",
    "production_evidence_plan_visible": "Production evidence plan visible",
    "runtime_qa_execution_recipe_ready": "Runtime QA execution recipe ready",
    "runtime_qa_execution_request_visible": "Runtime QA execution request visible",
    "runtime_qa_dry_run_receipt_visible": "Runtime QA dry-run receipt visible",
    "celery_process_evidence_required": "Celery process evidence required",
    "redis_broker_reachability_evidence_required": "Redis broker reachability evidence required",
    "queue_round_trip_evidence_required": "Queue round-trip evidence required",
    "cross_process_controls_evidence_required": "Cross-process controls evidence required",
    "append_only_worker_log_evidence_required": "Append-only worker log evidence required",
    "scheduler_default_off_runtime_evidence_required": "Scheduler default-off runtime evidence required",
    "provider_model_no_autoschedule_runtime_evidence_required": "Provider/model no-autoschedule runtime evidence required",
    "local_fallback_rollback_evidence_required": "Local fallback rollback evidence required",
    "production_worker_promotion_review_required": "Production worker promotion review required",
    "no_process_provider_trade_secret_boundary": "No process, provider, trade, or secret boundary",
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
WORKER_CELERY_FILESYSTEM_ROUNDTRIP_EVIDENCE_PATH = (
    PROJECT_ROOT
    / ".stock_ming_3"
    / "worker_runtime"
    / "worker_celery_filesystem_roundtrip_smoke.json"
)
WORKER_REDIS_ROUNDTRIP_EVIDENCE_PATH = (
    PROJECT_ROOT
    / ".stock_ming_3"
    / "worker_runtime"
    / "worker_redis_roundtrip_smoke.json"
)
WORKER_V04_RUNTIME_ROOT = PROJECT_ROOT / ".stock_ming_3" / "v04_acceptance"
LOCAL_REDIS_SERVER_CANDIDATE_PATHS = (
    "/opt/homebrew/bin/redis-server",
    "/usr/local/bin/redis-server",
    "/opt/local/bin/redis-server",
    "/usr/bin/redis-server",
)
LOCAL_REDIS_CLI_CANDIDATE_PATHS = (
    "/opt/homebrew/bin/redis-cli",
    "/usr/local/bin/redis-cli",
    "/opt/local/bin/redis-cli",
    "/usr/bin/redis-cli",
)
REDIS_CONFIG_ENV_SOURCES = (
    ("COMMAND_CENTER_REDIS_URL", "command_center_redis_url"),
    ("REDIS_URL", "standard_redis_url"),
    ("CELERY_BROKER_URL", "celery_broker_url"),
)
WORKER_TASK_CONTROL_PROBE_PATH = PROJECT_ROOT / "scripts" / "worker_task_control_probe.py"
TASK_CONTROL_PROJECTION_KEYS = (
    "task_id",
    "task_type",
    "status",
    "output_packet_key",
    "current_step",
    "progress",
    "retry_policy",
    "lock_policy",
    "dedupe_policy",
)


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


def _task_control_projection(task: dict[str, Any]) -> dict[str, Any]:
    projection = {key: task.get(key) for key in TASK_CONTROL_PROJECTION_KEYS}
    projection["task_log_events"] = [
        {
            "event": row.get("event"),
            "status": row.get("status"),
            "step": row.get("step"),
        }
        for row in task.get("task_log") or []
        if isinstance(row, dict)
    ]
    return projection


def _safe_cross_process_task_control_probe(task: dict[str, Any]) -> dict[str, Any]:
    task_id = str(task.get("task_id") or "")
    expected_sha256 = _json_sha256(_task_control_projection(task)) if task_id else ""
    fallback = {
        "schema_version": "worker_task_control_cross_process_probe.v1",
        "status": "cross_process_task_control_blocked",
        "scope": "local_python_process_sqlite_task_status_readback_no_worker_start",
        "task_id": task_id,
        "storage_source": "sqlite_meta",
        "readback_found": False,
        "readback_hash_matches": False,
        "task_status": "",
        "task_log_count": 0,
        "retry_metadata_visible": False,
        "lock_metadata_visible": False,
        "dedupe_metadata_visible": False,
        "contains_secret": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "error_message_safe": "cross_process_probe_not_run",
    }
    if not task_id or not expected_sha256 or not WORKER_TASK_CONTROL_PROBE_PATH.exists():
        return fallback
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(WORKER_TASK_CONTROL_PROBE_PATH),
                "--db-path",
                str(SQLITE_META_PATH),
                "--task-id",
                task_id,
                "--expected-sha256",
                expected_sha256,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        result = dict(fallback)
        result["error_message_safe"] = "cross_process_probe_failed_safe"
        return result
    try:
        parsed = json.loads(completed.stdout or "{}")
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    result = {**fallback, **parsed}
    result["process_returncode"] = completed.returncode
    result["probe_script"] = "scripts/worker_task_control_probe.py"
    result["expected_task_identity_sha256"] = expected_sha256
    result["external_calls_triggered"] = False
    result["tushare_called"] = False
    result["deepseek_called"] = False
    result["github_called"] = False
    result["does_not_execute_trades"] = True
    result["does_not_modify_strategy_action"] = True
    return result


def _read_worker_meta_packet_no_init(packet_key: str) -> tuple[Any, str]:
    if not SQLITE_META_PATH.exists():
        return None, "meta_missing"
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(SQLITE_META_PATH)
        row = conn.execute("SELECT payload_json FROM packets WHERE packet_key = ?", (packet_key,)).fetchone()
    except Exception:
        return None, "packet_read_failed"
    finally:
        if conn is not None:
            conn.close()
    if row is None:
        return None, "packet_missing"
    try:
        return json.loads(row[0]), "packet_present"
    except Exception:
        return None, "packet_decode_failed"


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _command_available(command_name: str) -> bool:
    try:
        return shutil.which(command_name) is not None
    except Exception:
        return False


def _project_venv_command_available(command_name: str) -> bool:
    try:
        command_path = PROJECT_ROOT / ".venv" / "bin" / command_name
        return command_path.is_file() and os.access(command_path, os.X_OK)
    except Exception:
        return False


def _active_python_env_command_available(command_name: str) -> bool:
    try:
        executable = Path(sys.executable)
        command_path = executable.parent / command_name
        return command_path.is_file() and os.access(command_path, os.X_OK)
    except Exception:
        return False


def _known_executable_path_available(paths: tuple[str, ...]) -> bool:
    try:
        return any(Path(path).is_file() and os.access(path, os.X_OK) for path in paths)
    except Exception:
        return False


def _redis_config_source_labels_present() -> list[str]:
    return [label for env_name, label in REDIS_CONFIG_ENV_SOURCES if bool(os.environ.get(env_name))]


def _path_exists(path: str) -> bool:
    return (PROJECT_ROOT / path).exists()


def _worker_runtime_dependency_preflight(
    *,
    celery_available: bool,
    redis_available: bool,
    apscheduler_available: bool,
    redis_configured: bool,
    redis_config_source_labels: list[str] | None = None,
) -> dict[str, Any]:
    celery_command_path_available = _command_available("celery")
    celery_project_venv_command_available = _project_venv_command_available("celery")
    celery_active_python_env_command_available = _active_python_env_command_available("celery")
    celery_command_available = (
        celery_command_path_available
        or celery_project_venv_command_available
        or celery_active_python_env_command_available
    )
    redis_server_path_available = _command_available("redis-server")
    redis_server_known_path_available = _known_executable_path_available(LOCAL_REDIS_SERVER_CANDIDATE_PATHS)
    redis_server_binary_available = redis_server_path_available or redis_server_known_path_available
    redis_cli_path_available = _command_available("redis-cli")
    redis_cli_known_path_available = _known_executable_path_available(LOCAL_REDIS_CLI_CANDIDATE_PATHS)
    redis_cli_binary_available = redis_cli_path_available or redis_cli_known_path_available
    if celery_command_path_available:
        celery_command_status = "available_path"
    elif celery_project_venv_command_available:
        celery_command_status = "available_project_venv"
    elif celery_active_python_env_command_available:
        celery_command_status = "available_active_python_env"
    else:
        celery_command_status = "missing"
    redis_server_resolution = (
        "available_path"
        if redis_server_path_available
        else "available_known_path"
        if redis_server_known_path_available
        else "missing"
    )
    redis_cli_resolution = (
        "available_path"
        if redis_cli_path_available
        else "available_known_path"
        if redis_cli_known_path_available
        else "missing"
    )
    redis_config_sources = list(redis_config_source_labels or [])
    local_runtime_blocking_checks = {
        "python_celery_package",
        "python_redis_package",
        "celery_command",
    }
    rows = [
        {
            "check": "python_celery_package",
            "status": "available" if celery_available else "missing",
            "required_for_production_worker": True,
            "blocks_manual_runtime_evidence": not celery_available,
            "evidence": "importlib.find_spec('celery')",
        },
        {
            "check": "python_redis_package",
            "status": "available" if redis_available else "missing",
            "required_for_production_worker": True,
            "blocks_manual_runtime_evidence": not redis_available,
            "evidence": "importlib.find_spec('redis')",
        },
        {
            "check": "celery_command",
            "status": celery_command_status,
            "required_for_production_worker": True,
            "blocks_manual_runtime_evidence": not celery_command_available,
            "evidence": (
                "PATH command lookup, project .venv/bin/celery executable check, "
                "or active Python env sibling executable check only"
            ),
        },
        {
            "check": "redis_server_binary",
            "status": redis_server_resolution,
            "required_for_production_worker": True,
            "blocks_manual_runtime_evidence": False,
            "blocks_production_redis_evidence": not redis_server_binary_available,
            "evidence": "PATH command lookup plus known local Redis binary paths; does not start redis-server",
        },
        {
            "check": "redis_cli_binary",
            "status": redis_cli_resolution,
            "required_for_production_worker": False,
            "blocks_manual_runtime_evidence": False,
            "evidence": "PATH command lookup plus known local Redis CLI paths; does not ping Redis",
        },
        {
            "check": "redis_url_configured",
            "status": "configured_not_pinged" if redis_configured else "missing",
            "required_for_production_worker": True,
            "blocks_manual_runtime_evidence": False,
            "blocks_production_redis_evidence": not redis_configured,
            "evidence": "supported broker URL env presence boolean only; safe source label only; value redacted",
        },
        {
            "check": "apscheduler_package",
            "status": "available" if apscheduler_available else "missing",
            "required_for_production_worker": False,
            "blocks_manual_runtime_evidence": False,
            "evidence": "importlib.find_spec('apscheduler')",
        },
    ]
    blocker_count = sum(1 for row in rows if row["blocks_manual_runtime_evidence"])
    production_redis_blockers = [
        row["check"] for row in rows if row.get("blocks_production_redis_evidence") is True
    ]
    return {
        "schema_version": "worker_runtime_dependency_preflight.v1",
        "scope": "local_dependency_visibility_no_process_start_no_broker_ping",
        "status": "manual_runtime_dependency_ready" if blocker_count == 0 else "manual_runtime_dependency_blocked",
        "local_preflight_ready": blocker_count == 0,
        "blocker_count": blocker_count,
        "row_count": len(rows),
        "rows": rows,
        "celery_package_available": celery_available,
        "redis_package_available": redis_available,
        "apscheduler_package_available": apscheduler_available,
        "celery_command_available": celery_command_available,
        "celery_command_path_available": celery_command_path_available,
        "celery_project_venv_command_available": celery_project_venv_command_available,
        "celery_active_python_env_command_available": celery_active_python_env_command_available,
        "celery_command_resolution": celery_command_status,
        "redis_server_binary_available": redis_server_binary_available,
        "redis_server_path_available": redis_server_path_available,
        "redis_server_known_path_available": redis_server_known_path_available,
        "redis_server_resolution": redis_server_resolution,
        "redis_server_checked_paths": list(LOCAL_REDIS_SERVER_CANDIDATE_PATHS),
        "redis_cli_binary_available": redis_cli_binary_available,
        "redis_cli_path_available": redis_cli_path_available,
        "redis_cli_known_path_available": redis_cli_known_path_available,
        "redis_cli_resolution": redis_cli_resolution,
        "redis_cli_checked_paths": list(LOCAL_REDIS_CLI_CANDIDATE_PATHS),
        "redis_url_configured": redis_configured,
        "redis_config_sources_present": redis_config_sources,
        "redis_config_source_count": len(redis_config_sources),
        "redis_config_values_exposed": False,
        "redis_config_env_names_exposed": False,
        "local_non_redis_runtime_evidence_ready": blocker_count == 0,
        "local_non_redis_runtime_blocking_checks": [
            row["check"]
            for row in rows
            if row["check"] in local_runtime_blocking_checks
            and row["blocks_manual_runtime_evidence"]
        ],
        "production_redis_evidence_blocked": bool(production_redis_blockers),
        "production_redis_evidence_blockers": production_redis_blockers,
        "redis_manual_resolution_required": (not redis_server_binary_available) or (not redis_configured),
        "redis_manual_resolution_blockers": [
            row["check"]
            for row in rows
            if row["check"] in {"redis_server_binary", "redis_url_configured"}
            and row.get("blocks_production_redis_evidence") is True
        ],
        "redis_manual_resolution_next_steps": [
            "install or expose a local redis-server binary, or provide an approved remote broker URL",
            "configure REDIS_URL or CELERY_BROKER_URL without exposing the value",
            "run a separate approved broker reachability QA before production promotion",
        ],
        "redis_url_exposed": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "production_worker_complete": False,
        "evidence_boundary": "dependency_preflight_is_environment_visibility_not_runtime_process_evidence",
    }


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
    if task_type == "run_candidate_radar_full_market_production_acceptance":
        return "worker_production"
    if task_type in {
        "refresh_tushare_facts",
        "refresh_factor_data",
        "command_center_live_bootstrap",
        "run_candidate_radar_quant_projection",
        "run_candidate_radar_quant_projection_provider_model_acceptance",
        "run_candidate_radar_provider_parity_acceptance",
        "run_factor_test_provider_industry_membership",
    }:
        return "provider_refresh"
    if task_type in {
        "run_deepseek_factor_explanation",
        "run_deepseek_provider_benchmark",
    }:
        return "model_explain"
    if task_type in {"run_chokepoint_scan", "probe_serenity_github"}:
        return "external_probe"
    if task_type in {
        "run_storage_artifact_cleanup_dry_run",
        "run_storage_schema_validation_dry_run",
        "run_storage_backtest_results_schema_seed",
        "run_storage_schema_validation_acceptance",
        "run_storage_dataset_version_manifest_dry_run",
        "run_storage_dataset_version_manifest_review",
        "run_storage_dataset_version_manifest_write",
        "run_storage_dataset_version_manifest_validate",
        "run_storage_partition_migration_dry_run",
        "run_storage_partition_migration_execution",
        "run_storage_compaction_dry_run",
        "run_storage_compaction_execution",
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
        "worker_production": {
            "queue_role": "explicit Redis/Celery production acceptance tasks",
            "allowed_external_sources": ["redis", "celery_worker"],
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


def _missing_worker_synthetic_healthcheck_packet(read_status: str = "packet_missing") -> dict[str, Any]:
    return {
        "packet_key": SYNTHETIC_HEALTHCHECK_PACKET_KEY,
        "schema_version": SYNTHETIC_HEALTHCHECK_SCHEMA_VERSION,
        "status": "synthetic_healthcheck_missing",
        "scope": "explicit_post_worker_synthetic_healthcheck_no_process_start",
        "mode": "button_gated_local_synthetic_healthcheck",
        "source_packet_read_status": read_status,
        "source_packet_present": False,
        "cache_get_initializes_meta_store": False,
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
    packet, read_status = _read_worker_meta_packet_no_init(SYNTHETIC_HEALTHCHECK_PACKET_KEY)
    if not isinstance(packet, dict):
        return _missing_worker_synthetic_healthcheck_packet(read_status)
    safe_packet = _json_safe(packet)
    safe_packet.setdefault("healthcheck_hash_algorithm", "")
    safe_packet.setdefault("task_identity_sha256", "")
    safe_packet.setdefault("readback_task_identity_sha256", "")
    safe_packet.setdefault("task_readback_hash_matches", False)
    safe_packet.setdefault("safe_hash_payload_fields", [])
    safe_packet["source_packet_read_status"] = read_status
    safe_packet["source_packet_present"] = True
    safe_packet["cache_get_initializes_meta_store"] = False
    return safe_packet


def _activation_review_task_row(
    criterion: str,
    passed: bool,
    *,
    status: str | None = None,
    evidence: str,
    next_action: str,
    local_required: bool = True,
    production_required: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status or ("passed" if passed else "blocked"),
        "passed": bool(passed),
        "blocks_activation_review": bool(local_required and not passed),
        "production_blocker": bool(production_required and not passed),
        "evidence": evidence,
        "next_action": next_action,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "production_worker_complete": False,
    }


def _worker_activation_review_task_receipt(
    *,
    synthetic_healthcheck: dict[str, Any],
    activation_review_contract: dict[str, Any],
    production_activation_receipt: dict[str, Any],
    explicit_review: bool = False,
    task_id: str | None = None,
    reviewed_at: str | None = None,
    payload_safe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_payload = payload_safe if isinstance(payload_safe, dict) else {}
    approved = safe_payload.get("operator_approved") is True or safe_payload.get("approved") is True
    synthetic_executed = synthetic_healthcheck.get("synthetic_healthcheck_executed") is True
    local_round_trip = synthetic_healthcheck.get("local_task_round_trip_verified") is True
    task_log_round_trip = synthetic_healthcheck.get("task_log_round_trip_verified") is True
    activation_contract_ready = activation_review_contract.get("schema_version") == "worker_activation_review_contract.v1"
    activation_receipt_ready = production_activation_receipt.get("local_activation_receipt_ready") is True
    scheduler_off = production_activation_receipt.get("scheduler_started") is False
    provider_boundary_ok = (
        production_activation_receipt.get("provider_model_task_dispatched_by_receipt") is False
        and production_activation_receipt.get("external_calls_triggered") is False
    )
    rows = [
        _activation_review_task_row(
            "explicit_post_activation_review_done",
            explicit_review,
            evidence="Activation review must be created through POST /api/worker/activation-review.",
            next_action="Use the button-gated POST review after synthetic healthcheck evidence exists.",
        ),
        _activation_review_task_row(
            "operator_approval_recorded",
            approved,
            evidence="Payload must include operator_approved=true or approved=true for local activation review scoping.",
            next_action="Record explicit operator approval for the local review scope; do not infer approval from cache state.",
        ),
        _activation_review_task_row(
            "synthetic_healthcheck_executed",
            synthetic_executed and local_round_trip and task_log_round_trip,
            evidence=(
                f"synthetic={synthetic_executed}; local_round_trip={local_round_trip}; "
                f"task_log_round_trip={task_log_round_trip}"
            ),
            next_action="Run POST /api/worker/synthetic-healthcheck before activation review if local evidence is missing.",
        ),
        _activation_review_task_row(
            "activation_review_contract_visible",
            activation_contract_ready,
            evidence=str(activation_review_contract.get("status") or "missing"),
            next_action="Repair worker_activation_review_contract before activation review.",
        ),
        _activation_review_task_row(
            "production_activation_receipt_visible",
            activation_receipt_ready,
            evidence=str(production_activation_receipt.get("status") or "missing"),
            next_action="Keep worker_production_activation_receipt visible as the production blocker checklist.",
        ),
        _activation_review_task_row(
            "celery_redis_not_started_by_review",
            True,
            evidence="Activation review reads local packets only; it does not start Celery or ping Redis.",
            next_action="Start Celery/Redis only in a future manually approved production run outside cache/review paths.",
            local_required=False,
            production_required=False,
        ),
        _activation_review_task_row(
            "scheduler_default_off_preserved",
            scheduler_off,
            evidence=f"scheduler_started={production_activation_receipt.get('scheduler_started')}",
            next_action="Keep scheduler disabled unless a separate production scheduler review approves it.",
        ),
        _activation_review_task_row(
            "provider_model_no_autoschedule_boundary",
            provider_boundary_ok,
            evidence="Tushare, DeepSeek and GitHub-capable work remains button-gated and is not dispatched by review.",
            next_action="Keep provider/model/probe tasks behind explicit POST routes with call ledger.",
        ),
        _activation_review_task_row(
            "production_worker_completion_stays_blocked",
            True,
            evidence="Activation review keeps production_worker_complete=false and activation_ready=false.",
            next_action="Require later Celery process, Redis broker, cross-process controls, append-only logs, and promotion evidence.",
            local_required=False,
            production_required=False,
        ),
        _activation_review_task_row(
            "production_evidence_required",
            False,
            status="pending_production_worker_evidence",
            evidence="Celery process, Redis broker, cross-process controls, append-only logs, scheduler runtime, and promotion evidence are still missing.",
            next_action="Collect production worker evidence in a separate production activation task; this review only binds local scope.",
            local_required=False,
            production_required=True,
        ),
    ]
    local_blockers = [str(row["criterion"]) for row in rows if row.get("blocks_activation_review")]
    production_blockers = [str(row["criterion"]) for row in rows if row.get("production_blocker")]
    review_ready = not local_blockers
    status = (
        "worker_activation_review_task_blocked_operator_approval_required"
        if explicit_review and not approved
        else "worker_activation_review_task_ready_production_blocked"
        if review_ready
        else "worker_activation_review_task_pending"
    )
    request_params_safe = {
        "review_scope": "worker_activation_local_review_no_process_start",
        "operator_approved": approved,
        "synthetic_healthcheck_task_id": synthetic_healthcheck.get("task_id") or "",
        "external_sources_allowed": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "production_worker_complete": False,
    }
    receipt = {
        "packet_key": ACTIVATION_REVIEW_PACKET_KEY,
        "schema_version": ACTIVATION_REVIEW_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_worker_activation_review_no_process_start",
        "ltg": "LTG-06",
        "mode": "button_gated_local_activation_review",
        "explicit_activation_review_done": bool(explicit_review),
        "review_task_id": task_id,
        "reviewed_at": reviewed_at,
        "button_gated": True,
        "local_review_only": True,
        "operator_approved": approved,
        "activation_review_ready": review_ready,
        "ready_for_manual_celery_redis_activation_review": review_ready,
        "ready_to_mark_production_worker_complete": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "synthetic_healthcheck_executed": synthetic_executed,
        "synthetic_healthcheck_task_id": synthetic_healthcheck.get("task_id") or "",
        "local_task_round_trip_verified": local_round_trip,
        "task_log_round_trip_verified": task_log_round_trip,
        "activation_contract_ready": activation_contract_ready,
        "activation_receipt_ready": activation_receipt_ready,
        "production_blocker_count": len(production_blockers),
        "local_blocker_count": len(local_blockers),
        "row_count": len(rows),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "allowed_next_step": "manual_celery_redis_start_then_production_worker_evidence_ticket" if review_ready else "run_synthetic_healthcheck_then_activation_review",
        "not_allowed_next_steps": [
            "start Celery from activation review",
            "ping Redis from activation review",
            "start scheduler from activation review",
            "dispatch worker task from activation review",
            "automatic Tushare/DeepSeek/GitHub scheduling",
            "activation review as production worker completion",
            "synthetic healthcheck as Celery/Redis process proof",
        ],
        "missing_evidence_items": [
            "celery worker process evidence",
            "redis broker reachability evidence",
            "cross-process retry/cancel/lock/dedupe evidence",
            "append-only worker task log evidence",
            "scheduler default-off runtime evidence",
            "production worker promotion evidence",
        ],
        "request_params_safe": request_params_safe,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "cache_get_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "note": "This explicit activation review binds local LTG-06 evidence after synthetic healthcheck. It does not start Celery, ping Redis, start scheduler, dispatch tasks, call providers/models/probes, execute trades, or prove production worker completion.",
    }
    return receipt


def _missing_worker_activation_review_packet(
    synthetic_healthcheck: dict[str, Any],
    activation_review_contract: dict[str, Any],
    production_activation_receipt: dict[str, Any],
    read_status: str = "packet_missing",
) -> dict[str, Any]:
    receipt = _worker_activation_review_task_receipt(
        synthetic_healthcheck=synthetic_healthcheck,
        activation_review_contract=activation_review_contract,
        production_activation_receipt=production_activation_receipt,
        explicit_review=False,
    )
    receipt["source_packet_read_status"] = read_status
    receipt["source_packet_present"] = False
    receipt["cache_get_initializes_meta_store"] = False
    return receipt


def _read_worker_activation_review_packet(
    synthetic_healthcheck: dict[str, Any],
    activation_review_contract: dict[str, Any],
    production_activation_receipt: dict[str, Any],
) -> dict[str, Any]:
    packet, read_status = _read_worker_meta_packet_no_init(ACTIVATION_REVIEW_PACKET_KEY)
    if not isinstance(packet, dict):
        return _missing_worker_activation_review_packet(
            synthetic_healthcheck,
            activation_review_contract,
            production_activation_receipt,
            read_status,
        )
    receipt = _json_safe(packet.get("worker_activation_review_task_receipt") or packet)
    if not isinstance(receipt, dict) or receipt.get("schema_version") != ACTIVATION_REVIEW_SCHEMA_VERSION:
        return _missing_worker_activation_review_packet(
            synthetic_healthcheck,
            activation_review_contract,
            production_activation_receipt,
            read_status,
        )
    rebuilt = _worker_activation_review_task_receipt(
        synthetic_healthcheck=synthetic_healthcheck,
        activation_review_contract=activation_review_contract,
        production_activation_receipt=production_activation_receipt,
        explicit_review=receipt.get("explicit_activation_review_done") is True,
        task_id=str(receipt.get("review_task_id") or "") or None,
        reviewed_at=str(receipt.get("reviewed_at") or "") or None,
        payload_safe=receipt.get("request_params_safe") if isinstance(receipt.get("request_params_safe"), dict) else {},
    )
    rebuilt["source_packet_read_status"] = read_status
    rebuilt["source_packet_present"] = True
    rebuilt["cache_get_initializes_meta_store"] = False
    return rebuilt

def _production_evidence_plan_row(
    criterion: str,
    passed: bool,
    *,
    status: str | None = None,
    evidence: str,
    next_action: str,
    local_required: bool = True,
    production_required: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status or ("passed" if passed else "blocked"),
        "passed": bool(passed),
        "blocks_evidence_plan": bool(local_required and not passed),
        "production_blocker": bool(production_required and not passed),
        "evidence": evidence,
        "next_action": next_action,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "production_worker_complete": False,
    }


def _worker_production_evidence_plan_receipt(
    *,
    synthetic_healthcheck: dict[str, Any],
    activation_review_task: dict[str, Any],
    production_activation_receipt: dict[str, Any],
    explicit_plan: bool = False,
    task_id: str | None = None,
    planned_at: str | None = None,
    payload_safe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_payload = payload_safe if isinstance(payload_safe, dict) else {}
    approved = safe_payload.get("operator_approved") is True or safe_payload.get("approved") is True
    activation_review_visible = activation_review_task.get("schema_version") == ACTIVATION_REVIEW_SCHEMA_VERSION
    activation_review_ready = activation_review_task.get("activation_review_ready") is True
    synthetic_ready = synthetic_healthcheck.get("synthetic_healthcheck_executed") is True
    activation_receipt_visible = production_activation_receipt.get("schema_version") == "worker_production_activation_receipt.v1"
    provider_boundary_ok = (
        activation_review_task.get("external_calls_triggered") is False
        and activation_review_task.get("tushare_called") is False
        and activation_review_task.get("deepseek_called") is False
        and activation_review_task.get("github_called") is False
        and production_activation_receipt.get("provider_model_task_dispatched_by_receipt") is False
    )
    rows = [
        _production_evidence_plan_row(
            "explicit_post_evidence_plan_done",
            explicit_plan,
            evidence="Production evidence plan must be created through POST /api/worker/production-evidence-plan.",
            next_action="Use the button-gated POST route to bind the exact local plan scope.",
        ),
        _production_evidence_plan_row(
            "operator_approval_recorded",
            approved,
            evidence="Payload must include operator_approved=true or approved=true for the local evidence-plan scope.",
            next_action="Record explicit operator approval for this plan; do not infer approval from cache reads.",
        ),
        _production_evidence_plan_row(
            "activation_review_task_ready",
            activation_review_visible and activation_review_ready,
            evidence=str(activation_review_task.get("status") or "missing"),
            next_action="Run synthetic healthcheck and activation review before treating the production evidence plan as runtime-QA ready.",
        ),
        _production_evidence_plan_row(
            "production_activation_receipt_visible",
            activation_receipt_visible,
            evidence=str(production_activation_receipt.get("status") or "missing"),
            next_action="Keep worker_production_activation_receipt visible as the production-start blocker checklist.",
        ),
        _production_evidence_plan_row(
            "celery_process_evidence_required",
            False,
            status="pending_manual_runtime_evidence",
            evidence="No Celery process evidence is collected by this plan.",
            next_action="In a later approved runtime QA, capture process identity, queue registration, and safe worker startup proof.",
            local_required=False,
            production_required=True,
        ),
        _production_evidence_plan_row(
            "redis_broker_evidence_required",
            False,
            status="pending_manual_runtime_evidence",
            evidence="No Redis broker reachability is checked or pinged by this plan.",
            next_action="In a later approved runtime QA, capture broker reachability without exposing Redis URL or credentials.",
            local_required=False,
            production_required=True,
        ),
        _production_evidence_plan_row(
            "cross_process_controls_evidence_required",
            False,
            status="pending_manual_runtime_evidence",
            evidence="Retry/cancel/lock/dedupe are visible locally, but cross-process proof is not collected here.",
            next_action="In a later approved runtime QA, prove retry/cancel/lock/dedupe across worker process boundaries.",
            local_required=False,
            production_required=True,
        ),
        _production_evidence_plan_row(
            "append_only_worker_log_evidence_required",
            False,
            status="pending_manual_runtime_evidence",
            evidence="Local safe task_log metadata exists, but append-only worker log storage is not verified here.",
            next_action="In a later approved runtime QA, prove append-only worker logs without raw payload or secret leakage.",
            local_required=False,
            production_required=True,
        ),
        _production_evidence_plan_row(
            "scheduler_default_off_runtime_evidence_required",
            False,
            status="pending_manual_runtime_evidence",
            evidence="Scheduler stays off in cache/review paths; runtime default-off evidence is not collected here.",
            next_action="In a later approved runtime QA, prove scheduler remains disabled unless separately approved.",
            local_required=False,
            production_required=True,
        ),
        _production_evidence_plan_row(
            "provider_model_no_autoschedule_boundary",
            provider_boundary_ok,
            evidence="Tushare, DeepSeek and GitHub-capable queues remain button-gated and are not scheduled by this plan.",
            next_action="Keep provider/model/probe tasks behind explicit POST routes with call ledger in runtime QA.",
        ),
        _production_evidence_plan_row(
            "no_trade_no_action_boundary",
            True,
            evidence="Production evidence planning does not execute trades or mutate strategy action.",
            next_action="Keep broker/order integration out of LTG-06 worker runtime QA.",
            local_required=False,
            production_required=False,
        ),
        _production_evidence_plan_row(
            "production_worker_completion_stays_blocked",
            True,
            evidence="This plan keeps production_worker_complete=false until runtime evidence is collected and reviewed.",
            next_action="Treat this plan as a scope ticket only, not as production worker completion.",
            local_required=False,
            production_required=False,
        ),
    ]
    local_blockers = [str(row["criterion"]) for row in rows if row.get("blocks_evidence_plan")]
    production_blockers = [str(row["criterion"]) for row in rows if row.get("production_blocker")]
    plan_ready = not local_blockers
    status = (
        "worker_production_evidence_plan_blocked_operator_approval_required"
        if explicit_plan and not approved
        else "worker_production_evidence_plan_ready_runtime_qa_pending"
        if plan_ready
        else "worker_production_evidence_plan_pending_activation_review"
    )
    scope_ticket_payload = {
        "schema_version": PRODUCTION_EVIDENCE_PLAN_SCHEMA_VERSION,
        "scope": "button_gated_worker_production_evidence_plan_no_process_start",
        "operator_approved": approved,
        "activation_review_status": activation_review_task.get("status") or "missing",
        "activation_review_task_id": activation_review_task.get("review_task_id") or "",
        "synthetic_healthcheck_task_id": synthetic_healthcheck.get("task_id") or "",
        "evidence_scope": list(WORKER_RUNTIME_EVIDENCE_STAGE_KEYS),
        "external_sources_allowed": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "production_worker_complete": False,
    }
    request_params_safe = {
        "plan_scope": "worker_production_runtime_evidence_plan_no_process_start",
        "operator_approved": approved,
        "activation_review_task_id": activation_review_task.get("review_task_id") or "",
        "synthetic_healthcheck_task_id": synthetic_healthcheck.get("task_id") or "",
        "external_sources_allowed": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "production_worker_complete": False,
    }
    return {
        "packet_key": PRODUCTION_EVIDENCE_PLAN_PACKET_KEY,
        "schema_version": PRODUCTION_EVIDENCE_PLAN_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_worker_production_evidence_plan_no_process_start",
        "ltg": "LTG-06",
        "mode": "button_gated_local_production_evidence_plan",
        "explicit_evidence_plan_done": bool(explicit_plan),
        "plan_task_id": task_id,
        "planned_at": planned_at,
        "button_gated": True,
        "local_plan_only": True,
        "operator_approved": approved,
        "evidence_plan_ready": plan_ready,
        "ready_for_manual_runtime_qa": plan_ready,
        "ready_to_mark_production_worker_complete": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "synthetic_healthcheck_executed": synthetic_ready,
        "synthetic_healthcheck_task_id": synthetic_healthcheck.get("task_id") or "",
        "activation_review_task_ready": activation_review_ready,
        "activation_review_task_id": activation_review_task.get("review_task_id") or "",
        "activation_review_status": activation_review_task.get("status") or "missing",
        "activation_receipt_visible": activation_receipt_visible,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "row_count": len(rows),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "scope_ticket_payload": scope_ticket_payload,
        "scope_ticket_sha256": _json_sha256(scope_ticket_payload),
        "request_params_safe": request_params_safe,
        "allowed_next_step": "separate_manual_worker_runtime_qa_no_provider_no_trade" if plan_ready else "run_synthetic_healthcheck_then_activation_review_then_evidence_plan",
        "not_allowed_next_steps": [
            "start Celery from evidence plan",
            "ping Redis from evidence plan",
            "start scheduler from evidence plan",
            "dispatch worker task from evidence plan",
            "automatic Tushare/DeepSeek/GitHub scheduling",
            "evidence plan as production worker completion",
            "scope ticket as runtime evidence",
        ],
        "missing_evidence_items": [
            "celery worker process identity and queue registration evidence",
            "redis broker reachability evidence without URL/credential exposure",
            "cross-process retry/cancel/lock/dedupe evidence",
            "append-only worker task log evidence",
            "scheduler default-off runtime evidence",
            "runtime QA reviewer approval evidence",
            "production worker promotion evidence",
        ],
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "cache_get_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "note": "This receipt is a local LTG-06 production evidence plan. It creates a safe scope ticket for later manual runtime QA; it does not start Celery, ping Redis, start scheduler, dispatch tasks, call providers/models/probes, execute trades, or prove production worker completion.",
    }


def _missing_worker_production_evidence_plan_packet(
    synthetic_healthcheck: dict[str, Any],
    activation_review_task: dict[str, Any],
    production_activation_receipt: dict[str, Any],
    read_status: str = "packet_missing",
) -> dict[str, Any]:
    receipt = _worker_production_evidence_plan_receipt(
        synthetic_healthcheck=synthetic_healthcheck,
        activation_review_task=activation_review_task,
        production_activation_receipt=production_activation_receipt,
        explicit_plan=False,
    )
    receipt["source_packet_read_status"] = read_status
    receipt["source_packet_present"] = False
    receipt["cache_get_initializes_meta_store"] = False
    return receipt


def _read_worker_production_evidence_plan_packet(
    synthetic_healthcheck: dict[str, Any],
    activation_review_task: dict[str, Any],
    production_activation_receipt: dict[str, Any],
) -> dict[str, Any]:
    packet, read_status = _read_worker_meta_packet_no_init(PRODUCTION_EVIDENCE_PLAN_PACKET_KEY)
    if not isinstance(packet, dict):
        return _missing_worker_production_evidence_plan_packet(
            synthetic_healthcheck,
            activation_review_task,
            production_activation_receipt,
            read_status,
        )
    receipt = _json_safe(packet.get("worker_production_evidence_plan_receipt") or packet)
    if not isinstance(receipt, dict) or receipt.get("schema_version") != PRODUCTION_EVIDENCE_PLAN_SCHEMA_VERSION:
        return _missing_worker_production_evidence_plan_packet(
            synthetic_healthcheck,
            activation_review_task,
            production_activation_receipt,
            read_status,
        )
    rebuilt = _worker_production_evidence_plan_receipt(
        synthetic_healthcheck=synthetic_healthcheck,
        activation_review_task=activation_review_task,
        production_activation_receipt=production_activation_receipt,
        explicit_plan=receipt.get("explicit_evidence_plan_done") is True,
        task_id=str(receipt.get("plan_task_id") or "") or None,
        planned_at=str(receipt.get("planned_at") or "") or None,
        payload_safe=receipt.get("request_params_safe") if isinstance(receipt.get("request_params_safe"), dict) else {},
    )
    rebuilt["source_packet_read_status"] = read_status
    rebuilt["source_packet_present"] = True
    rebuilt["cache_get_initializes_meta_store"] = False
    return rebuilt



def _worker_runtime_qa_execution_recipe_row(
    phase: str,
    *,
    status: str,
    local_ready: bool,
    evidence: str,
    evidence_required: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "phase_label": WORKER_RUNTIME_QA_EXECUTION_PHASE_LABELS.get(phase, phase),
        "status": status,
        "local_ready": bool(local_ready),
        "runtime_qa_done": False,
        "production_ready": False,
        "production_blocker": True,
        "required_before_production": True,
        "evidence": evidence,
        "evidence_required": evidence_required,
        "next_action": next_action,
        "cache_only": True,
        "runs_no_commands": True,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "healthcheck_executed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _worker_runtime_qa_execution_scope_hash(recipe: dict[str, Any]) -> str:
    scope_payload = {
        "schema_version": recipe.get("schema_version"),
        "scope": recipe.get("scope"),
        "status": recipe.get("status"),
        "phase_keys": list(recipe.get("phase_keys") or []),
        "allowed_execution_sequence": list(recipe.get("allowed_execution_sequence") or []),
        "local_recipe_ready": recipe.get("local_recipe_ready") is True,
        "runtime_qa_done": recipe.get("runtime_qa_done") is True,
        "production_worker_complete": recipe.get("production_worker_complete") is True,
    }
    return _json_sha256(scope_payload)


def _worker_runtime_qa_execution_recipe(
    *,
    production_evidence_plan: dict[str, Any],
    production_activation_receipt: dict[str, Any],
    readiness_receipt: dict[str, Any],
    healthcheck_qa_contract: dict[str, Any],
    task_log_persistence_audit: dict[str, Any],
    queue_routing_contract: dict[str, Any],
) -> dict[str, Any]:
    evidence_scope = [
        str(item)
        for item in (
            _json_safe(production_evidence_plan.get("scope_ticket_payload") or {}).get("evidence_scope")
            if isinstance(production_evidence_plan.get("scope_ticket_payload"), dict)
            else []
        )
    ]
    evidence_plan_visible = production_evidence_plan.get("schema_version") == PRODUCTION_EVIDENCE_PLAN_SCHEMA_VERSION
    activation_receipt_visible = production_activation_receipt.get("schema_version") == "worker_production_activation_receipt.v1"
    readiness_visible = readiness_receipt.get("schema_version") == "worker_production_readiness_receipt.v1"
    healthcheck_contract_visible = healthcheck_qa_contract.get("schema_version") == "worker_healthcheck_qa_contract.v1"
    task_log_audit_visible = task_log_persistence_audit.get("schema_version") == "worker_task_log_persistence_audit.v1"
    queue_routing_visible = queue_routing_contract.get("schema_version") == "worker_queue_routing_contract.v1"
    safety_boundary_ready = (
        production_evidence_plan.get("starts_celery_worker") is False
        and production_evidence_plan.get("pings_redis") is False
        and production_evidence_plan.get("starts_scheduler") is False
        and production_evidence_plan.get("task_dispatched") is False
        and production_evidence_plan.get("provider_model_task_dispatched") is False
        and production_activation_receipt.get("worker_started_by_receipt") is False
        and production_activation_receipt.get("redis_pinged_by_receipt") is False
        and production_activation_receipt.get("scheduler_started_by_receipt") is False
        and production_activation_receipt.get("task_dispatched_by_receipt") is False
        and production_activation_receipt.get("provider_model_task_dispatched_by_receipt") is False
    )
    local_recipe_ready = all(
        [
            evidence_plan_visible,
            activation_receipt_visible,
            readiness_visible,
            healthcheck_contract_visible,
            task_log_audit_visible,
            queue_routing_visible,
            safety_boundary_ready,
        ]
    )
    rows = [
        _worker_runtime_qa_execution_recipe_row(
            "evidence_plan_scope_ticket",
            status=(
                "ready_runtime_qa_scope_ticket"
                if production_evidence_plan.get("evidence_plan_ready") is True
                else "pending_explicit_evidence_plan_or_activation_review"
            ),
            local_ready=evidence_plan_visible and bool(evidence_scope),
            evidence=(
                f"evidence_plan_status={production_evidence_plan.get('status')}; "
                f"evidence_scope_count={len(evidence_scope)}"
            ),
            evidence_required="approved production evidence plan scope ticket with SHA-256 fingerprint",
            next_action="Create or reuse the explicit POST evidence-plan scope ticket before runtime QA.",
        ),
        _worker_runtime_qa_execution_recipe_row(
            "celery_process_manual_start",
            status="pending_manual_worker_process_evidence",
            local_ready=activation_receipt_visible,
            evidence="No Celery process is started or inspected by this recipe.",
            evidence_required="manual Celery process identity, queue registration, and safe startup log evidence",
            next_action="Start Celery only in a separately approved runtime QA path and record redacted process evidence.",
        ),
        _worker_runtime_qa_execution_recipe_row(
            "redis_broker_redacted_reachability",
            status="pending_manual_broker_evidence",
            local_ready=activation_receipt_visible,
            evidence="Redis is not pinged and Redis URL/credentials are not exposed by this recipe.",
            evidence_required="redacted Redis broker reachability evidence without URL, token, key, or password values",
            next_action="Verify Redis only through a future explicit runtime QA path with redacted evidence.",
        ),
        _worker_runtime_qa_execution_recipe_row(
            "queue_binding_and_synthetic_round_trip",
            status="pending_live_queue_round_trip",
            local_ready=queue_routing_visible and healthcheck_contract_visible,
            evidence=f"queue_count={queue_routing_contract.get('queue_count')}; healthcheck_status={healthcheck_qa_contract.get('status')}",
            evidence_required="live worker queue binding plus synthetic task round-trip evidence",
            next_action="Bind queues and run a synthetic round trip only after Celery/Redis runtime evidence is present.",
        ),
        _worker_runtime_qa_execution_recipe_row(
            "cross_process_retry_cancel_lock_dedupe",
            status="pending_cross_process_controls",
            local_ready=healthcheck_contract_visible,
            evidence=f"healthcheck_pending_count={healthcheck_qa_contract.get('pending_criterion_count')}",
            evidence_required="cross-process retry/cancel/lock/dedupe evidence across worker process boundaries",
            next_action="Prove retry, cancel, lock, and dedupe semantics across live worker processes.",
        ),
        _worker_runtime_qa_execution_recipe_row(
            "append_only_worker_log_validation",
            status="pending_append_only_log_evidence",
            local_ready=task_log_audit_visible,
            evidence=f"task_log_audit_status={task_log_persistence_audit.get('status')}",
            evidence_required="append-only redacted worker log storage plus cross-process log readback",
            next_action="Collect append-only worker log evidence without raw payload or secret leakage.",
        ),
        _worker_runtime_qa_execution_recipe_row(
            "scheduler_default_off_runtime",
            status="pending_scheduler_runtime_evidence",
            local_ready=activation_receipt_visible,
            evidence="Scheduler remains default-off in cache and review paths.",
            evidence_required="runtime proof that scheduler stays disabled unless separately approved",
            next_action="Capture scheduler default-off evidence during runtime QA; do not start APScheduler from cache.",
        ),
        _worker_runtime_qa_execution_recipe_row(
            "provider_model_no_autoschedule_boundary",
            status="ready_local_boundary_runtime_proof_pending",
            local_ready=safety_boundary_ready,
            evidence="Provider/model/probe-capable work remains button-gated and is not autoscheduled by receipts.",
            evidence_required="runtime evidence that Tushare/DeepSeek/GitHub-capable tasks remain explicit and ledgered",
            next_action="Keep provider/model/probe tasks out of scheduler defaults and live worker auto-dispatch.",
        ),
        _worker_runtime_qa_execution_recipe_row(
            "local_fallback_rollback_plan",
            status="pending_runtime_rollback_evidence",
            local_ready=readiness_visible,
            evidence="Local fallback remains available while Celery/Redis production worker is blocked.",
            evidence_required="rollback evidence showing local fallback when Celery/Redis is unavailable or disabled",
            next_action="Prove graceful fallback before any production worker promotion.",
        ),
        _worker_runtime_qa_execution_recipe_row(
            "production_worker_promotion_review",
            status="blocked_until_runtime_evidence_passes",
            local_ready=False,
            evidence=f"production_blocker_count={production_evidence_plan.get('production_blocker_count')}",
            evidence_required="all runtime QA evidence plus explicit production worker promotion review",
            next_action="Promote production worker only after direct runtime evidence clears every blocker.",
        ),
    ]
    pending_phases = [row["phase"] for row in rows if not row.get("runtime_qa_done")]
    local_blockers = [row["phase"] for row in rows if not row.get("local_ready")]
    status = "worker_runtime_qa_recipe_ready_execution_pending" if local_recipe_ready else "worker_runtime_qa_recipe_blocked"
    recipe = {
        "schema_version": "worker_runtime_qa_execution_recipe.v1",
        "status": status,
        "scope": "local_worker_runtime_qa_execution_recipe_no_process_start",
        "ltg": "LTG-06/LTG-11",
        "local_recipe_ready": local_recipe_ready,
        "runtime_qa_done": False,
        "production_worker_complete": False,
        "requires_manual_runtime_qa": True,
        "requires_explicit_post_sequence": True,
        "phase_count": len(rows),
        "pending_phase_count": len(pending_phases),
        "local_blocker_count": len(local_blockers),
        "phase_keys": [row["phase"] for row in rows],
        "pending_phases": pending_phases,
        "local_blockers": local_blockers,
        "allowed_execution_sequence": list(WORKER_RUNTIME_QA_EXECUTION_PHASES),
        "required_evidence": [
            "approved production evidence plan scope ticket",
            "manual Celery process evidence",
            "redacted Redis broker reachability evidence",
            "live queue binding and synthetic round-trip evidence",
            "cross-process retry/cancel/lock/dedupe evidence",
            "append-only worker log evidence",
            "scheduler default-off runtime evidence",
            "provider/model no-autoschedule runtime evidence",
            "local fallback rollback evidence",
            "production worker promotion review",
        ],
        "not_allowed_next_steps": [
            "treat_recipe_as_runtime_qa_evidence",
            "start Celery from GET cache",
            "ping Redis from GET cache",
            "start scheduler from GET cache",
            "dispatch tasks from GET cache",
            "autoschedule Tushare DeepSeek GitHub tasks",
            "mark_production_worker_complete_from_scope_ticket",
        ],
        "cache_only": True,
        "runs_no_commands": True,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "healthcheck_executed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_worker_runtime_qa_execution_recipe",
                "source": "worker production evidence plan and activation receipts",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": status,
                "external": False,
                "external_calls_triggered": False,
                "redis_pinged": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This recipe sequences LTG-06 manual runtime QA. It does not start Celery, ping Redis, start scheduler, dispatch tasks, call providers/models/probes, execute trades, modify strategy action, or prove production worker completion.",
    }
    scope_hash = _worker_runtime_qa_execution_scope_hash(recipe)
    recipe["runtime_qa_scope_hash"] = scope_hash
    recipe["runtime_qa_scope_hash_short"] = scope_hash[:12]
    return recipe


def _worker_runtime_qa_execution_request_row(
    criterion: str,
    *,
    passed: bool,
    status: str,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "blocks_execution_request": not passed,
        "production_blocker": True,
        "required_before_runtime_qa": True,
        "request_only": True,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "runtime_qa_task_created": False,
        "runtime_qa_executed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "evidence": evidence,
        "next_action": next_action,
    }


def _worker_runtime_qa_execution_request_receipt(
    *,
    production_evidence_plan: dict[str, Any],
    runtime_qa_execution_recipe: dict[str, Any],
    explicit_request: bool = False,
    task_id: str | None = None,
    requested_at: str | None = None,
    payload_safe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_payload = payload_safe if isinstance(payload_safe, dict) else {}
    approved = safe_payload.get("operator_approved") is True or safe_payload.get("approved") is True
    evidence_plan_ready = production_evidence_plan.get("evidence_plan_ready") is True
    evidence_plan_scope_hash = str(production_evidence_plan.get("scope_ticket_sha256") or "")
    requested_evidence_plan_scope_hash = str(
        safe_payload.get("evidence_plan_scope_hash") or safe_payload.get("scope_ticket_sha256") or ""
    )
    recipe_ready = runtime_qa_execution_recipe.get("local_recipe_ready") is True
    runtime_qa_scope_hash = str(runtime_qa_execution_recipe.get("runtime_qa_scope_hash") or "")
    requested_runtime_qa_scope_hash = str(
        safe_payload.get("runtime_qa_scope_hash")
        or safe_payload.get("runtime_execution_scope_hash")
        or safe_payload.get("scope_hash")
        or ""
    )
    evidence_plan_scope_matches = bool(
        evidence_plan_scope_hash and requested_evidence_plan_scope_hash == evidence_plan_scope_hash
    )
    runtime_qa_scope_matches = bool(runtime_qa_scope_hash and requested_runtime_qa_scope_hash == runtime_qa_scope_hash)
    if not explicit_request:
        status = "worker_runtime_qa_execution_request_missing"
    elif not approved:
        status = "worker_runtime_qa_execution_request_blocked_operator_approval_required"
    elif not evidence_plan_ready:
        status = "worker_runtime_qa_execution_request_blocked_evidence_plan_required"
    elif not recipe_ready:
        status = "worker_runtime_qa_execution_request_blocked_recipe_not_ready"
    elif not requested_evidence_plan_scope_hash or not requested_runtime_qa_scope_hash:
        status = "worker_runtime_qa_execution_request_blocked_scope_hash_required"
    elif not evidence_plan_scope_matches or not runtime_qa_scope_matches:
        status = "worker_runtime_qa_execution_request_blocked_scope_hash_mismatch"
    else:
        status = "worker_runtime_qa_execution_request_ready_manual_runtime_qa_pending"
    ready = status == "worker_runtime_qa_execution_request_ready_manual_runtime_qa_pending"
    rows = [
        _worker_runtime_qa_execution_request_row(
            "explicit_post_execution_request_done",
            passed=explicit_request,
            status="passed" if explicit_request else "blocked_missing_execution_request",
            evidence="Execution request must be created through POST /api/worker/runtime-qa-execution-request.",
            next_action="Generate a request ticket from the Worker Runtime page before any future runtime QA task.",
        ),
        _worker_runtime_qa_execution_request_row(
            "operator_approval_recorded",
            passed=approved,
            status="passed" if approved else "blocked_operator_approval_required",
            evidence=f"operator_approved={approved}",
            next_action="Require explicit operator approval for the runtime QA request scope.",
        ),
        _worker_runtime_qa_execution_request_row(
            "production_evidence_plan_ready",
            passed=evidence_plan_ready,
            status="passed" if evidence_plan_ready else "blocked_evidence_plan_required",
            evidence=f"evidence_plan_status={production_evidence_plan.get('status')}",
            next_action="Run synthetic healthcheck, activation review, and production evidence plan before requesting runtime QA.",
        ),
        _worker_runtime_qa_execution_request_row(
            "runtime_qa_execution_recipe_ready",
            passed=recipe_ready,
            status="passed" if recipe_ready else "blocked_recipe_not_ready",
            evidence=f"recipe_status={runtime_qa_execution_recipe.get('status')}; phase_count={runtime_qa_execution_recipe.get('phase_count')}",
            next_action="Keep the runtime QA recipe visible before requesting manual runtime QA.",
        ),
        _worker_runtime_qa_execution_request_row(
            "evidence_plan_scope_hash_bound",
            passed=evidence_plan_scope_matches,
            status="passed" if evidence_plan_scope_matches else "blocked_scope_hash_mismatch_or_missing",
            evidence=(
                f"requested_scope_hash_short={requested_evidence_plan_scope_hash[:12]}; "
                f"latest_scope_hash_short={evidence_plan_scope_hash[:12]}"
            ),
            next_action="Regenerate the request if the production evidence plan scope ticket changes.",
        ),
        _worker_runtime_qa_execution_request_row(
            "runtime_qa_scope_hash_bound",
            passed=runtime_qa_scope_matches,
            status="passed" if runtime_qa_scope_matches else "blocked_scope_hash_mismatch_or_missing",
            evidence=(
                f"requested_runtime_hash_short={requested_runtime_qa_scope_hash[:12]}; "
                f"latest_runtime_hash_short={runtime_qa_scope_hash[:12]}"
            ),
            next_action="Regenerate the request if the runtime QA execution recipe changes.",
        ),
        _worker_runtime_qa_execution_request_row(
            "manual_runtime_qa_still_pending",
            passed=True,
            status="passed_request_only",
            evidence="Request ticket binds future runtime QA scope but does not create or execute a runtime QA task.",
            next_action="Submit separate explicit runtime QA only after reviewing this request ticket.",
        ),
        _worker_runtime_qa_execution_request_row(
            "no_process_provider_trade_secret_boundary",
            passed=True,
            status="passed_no_side_effects",
            evidence="Request ticket starts no worker, pings no Redis, starts no scheduler, dispatches no task, calls no provider/model/GitHub, trades nothing, mutates no action, and exposes no secret.",
            next_action="Preserve these false side-effect flags in every future runtime QA task.",
        ),
    ]
    local_blockers = [str(row["criterion"]) for row in rows if row.get("blocks_execution_request")]
    return {
        "packet_key": RUNTIME_QA_EXECUTION_REQUEST_PACKET_KEY,
        "schema_version": RUNTIME_QA_EXECUTION_REQUEST_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_worker_runtime_qa_execution_request_no_process_start",
        "ltg": "LTG-06/LTG-11",
        "mode": "button_gated_local_runtime_qa_execution_request",
        "explicit_execution_request_done": bool(explicit_request),
        "request_task_id": task_id,
        "requested_at": requested_at,
        "button_gated": True,
        "local_execution_request_only": True,
        "operator_approved": approved,
        "local_execution_request_ready": ready,
        "ready_for_manual_runtime_qa_task_submission": ready,
        "ready_to_mark_production_worker_complete": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "production_evidence_plan_ready": evidence_plan_ready,
        "production_evidence_plan_status": production_evidence_plan.get("status") or "missing",
        "production_evidence_plan_scope_hash": evidence_plan_scope_hash if evidence_plan_scope_matches else "",
        "production_evidence_plan_scope_hash_short": evidence_plan_scope_hash[:12],
        "requested_evidence_plan_scope_hash_short": requested_evidence_plan_scope_hash[:12],
        "requested_evidence_plan_scope_hash_matches_latest": evidence_plan_scope_matches,
        "runtime_qa_execution_recipe_ready": recipe_ready,
        "runtime_qa_execution_recipe_status": runtime_qa_execution_recipe.get("status") or "missing",
        "runtime_qa_scope_hash": runtime_qa_scope_hash if runtime_qa_scope_matches else "",
        "runtime_qa_scope_hash_short": runtime_qa_scope_hash[:12],
        "requested_runtime_qa_scope_hash_short": requested_runtime_qa_scope_hash[:12],
        "requested_runtime_qa_scope_hash_matches_latest": runtime_qa_scope_matches,
        "target_worker_task_route": "future POST /api/worker/runtime-qa-execution",
        "target_worker_task_type": "run_worker_runtime_qa_execution",
        "target_phases": list(runtime_qa_execution_recipe.get("allowed_execution_sequence") or []),
        "target_phase_count": int(runtime_qa_execution_recipe.get("phase_count") or 0),
        "required_evidence": list(runtime_qa_execution_recipe.get("required_evidence") or []),
        "local_blocker_count": len(local_blockers) if not ready else 0,
        "production_blocker_count": len(rows),
        "row_count": len(rows),
        "local_blockers": [] if ready else local_blockers,
        "not_allowed_next_steps": [
            "treat_execution_request_as_runtime_qa_execution",
            "start Celery from execution request",
            "ping Redis from execution request",
            "start scheduler from execution request",
            "dispatch worker task from execution request",
            "autoschedule Tushare DeepSeek GitHub tasks",
            "inspect Redis URL or credentials from execution request",
            "mark_production_worker_complete_from_execution_request",
        ],
        "request_params_safe": {
            "requested_from": safe_payload.get("requested_from") or "worker_runtime_page",
            "operator_approved": approved,
            "evidence_plan_scope_hash": requested_evidence_plan_scope_hash,
            "runtime_qa_scope_hash": requested_runtime_qa_scope_hash,
            "external_sources_allowed": False,
            "starts_celery_worker": False,
            "pings_redis": False,
            "starts_scheduler": False,
            "task_dispatched": False,
            "production_worker_complete": False,
        },
        "rows": rows,
        "runtime_qa_task_created": False,
        "runtime_qa_task_executed": False,
        "runtime_qa_execution_implemented": False,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "healthcheck_executed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_worker_runtime_qa_execution_request",
                "source": "worker production evidence plan and runtime QA recipe",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": status,
                "external": False,
                "external_calls_triggered": False,
                "redis_pinged": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [
            "Worker runtime QA execution request 只生成本地请求 ticket；不会启动 Celery、ping Redis、启动 scheduler 或派发任务。",
            "该 request 不调用 Tushare、DeepSeek、GitHub，不执行真实交易，不修改 strategy action，不代表 production worker 完成。",
        ],
        "note": "This explicit runtime QA execution request binds operator approval, production evidence plan scope, and runtime QA recipe scope. It does not start processes, dispatch tasks, call providers/models/probes, execute trades, mutate strategy action, expose secrets, or prove production worker completion.",
    }


def _missing_worker_runtime_qa_execution_request_packet(
    production_evidence_plan: dict[str, Any],
    runtime_qa_execution_recipe: dict[str, Any],
    read_status: str = "packet_missing",
) -> dict[str, Any]:
    receipt = _worker_runtime_qa_execution_request_receipt(
        production_evidence_plan=production_evidence_plan,
        runtime_qa_execution_recipe=runtime_qa_execution_recipe,
        explicit_request=False,
    )
    receipt["source_packet_read_status"] = read_status
    receipt["source_packet_present"] = False
    receipt["cache_get_initializes_meta_store"] = False
    return receipt


def _read_worker_runtime_qa_execution_request_packet(
    production_evidence_plan: dict[str, Any],
    runtime_qa_execution_recipe: dict[str, Any],
) -> dict[str, Any]:
    packet, read_status = _read_worker_meta_packet_no_init(RUNTIME_QA_EXECUTION_REQUEST_PACKET_KEY)
    if not isinstance(packet, dict):
        return _missing_worker_runtime_qa_execution_request_packet(
            production_evidence_plan,
            runtime_qa_execution_recipe,
            read_status,
        )
    receipt = _json_safe(packet.get("worker_runtime_qa_execution_request_receipt") or packet)
    if not isinstance(receipt, dict) or receipt.get("schema_version") != RUNTIME_QA_EXECUTION_REQUEST_SCHEMA_VERSION:
        return _missing_worker_runtime_qa_execution_request_packet(
            production_evidence_plan,
            runtime_qa_execution_recipe,
            read_status,
        )
    rebuilt = _worker_runtime_qa_execution_request_receipt(
        production_evidence_plan=production_evidence_plan,
        runtime_qa_execution_recipe=runtime_qa_execution_recipe,
        explicit_request=receipt.get("explicit_execution_request_done") is True,
        task_id=str(receipt.get("request_task_id") or "") or None,
        requested_at=str(receipt.get("requested_at") or "") or None,
        payload_safe=receipt.get("request_params_safe") if isinstance(receipt.get("request_params_safe"), dict) else {},
    )
    rebuilt["source_packet_read_status"] = read_status
    rebuilt["source_packet_present"] = True
    rebuilt["cache_get_initializes_meta_store"] = False
    return rebuilt


def _worker_runtime_qa_dry_run_row(
    criterion: str,
    *,
    passed: bool,
    status: str,
    evidence: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "blocks_dry_run": not passed,
        "production_blocker": True,
        "required_before_runtime_qa_execution": True,
        "dry_run_only": True,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "runtime_qa_task_created": False,
        "runtime_qa_task_executed": False,
        "runtime_qa_executed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "evidence": evidence,
        "next_action": next_action,
    }


def _worker_runtime_qa_dry_run_phase_rows(
    runtime_qa_execution_recipe: dict[str, Any],
    *,
    dry_run_ready: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, phase in enumerate(runtime_qa_execution_recipe.get("allowed_execution_sequence") or [], start=1):
        phase_key = str(phase)
        rows.append(
            {
                "phase_index": index,
                "phase": phase_key,
                "phase_label": WORKER_RUNTIME_QA_EXECUTION_PHASE_LABELS.get(phase_key, phase_key),
                "dry_run_status": "ready_for_future_execution" if dry_run_ready else "blocked_before_execution",
                "dry_run_reviewed": bool(dry_run_ready),
                "runtime_qa_done": False,
                "production_ready": False,
                "worker_started": False,
                "redis_pinged": False,
                "scheduler_started": False,
                "task_dispatched": False,
                "provider_model_task_dispatched": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
            }
        )
    return rows


def _worker_runtime_qa_dry_run_receipt(
    *,
    runtime_qa_execution_request: dict[str, Any],
    runtime_qa_execution_recipe: dict[str, Any],
    explicit_request: bool = False,
    task_id: str | None = None,
    requested_at: str | None = None,
    payload_safe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_payload = payload_safe if isinstance(payload_safe, dict) else {}
    approved = safe_payload.get("operator_approved") is True or safe_payload.get("approved") is True
    runtime_request_ready = runtime_qa_execution_request.get("local_execution_request_ready") is True
    request_task_id = str(runtime_qa_execution_request.get("request_task_id") or "")
    requested_request_task_id = str(
        safe_payload.get("request_task_id")
        or safe_payload.get("runtime_qa_request_task_id")
        or safe_payload.get("execution_request_task_id")
        or ""
    )
    recipe_ready = runtime_qa_execution_recipe.get("local_recipe_ready") is True
    evidence_plan_scope_hash = str(runtime_qa_execution_request.get("production_evidence_plan_scope_hash") or "")
    runtime_qa_scope_hash = str(runtime_qa_execution_request.get("runtime_qa_scope_hash") or "")
    requested_evidence_plan_scope_hash = str(
        safe_payload.get("evidence_plan_scope_hash") or safe_payload.get("production_evidence_plan_scope_hash") or ""
    )
    requested_runtime_qa_scope_hash = str(
        safe_payload.get("runtime_qa_scope_hash") or safe_payload.get("runtime_execution_scope_hash") or ""
    )
    request_task_matches = bool(request_task_id and requested_request_task_id == request_task_id)
    evidence_plan_scope_matches = bool(
        evidence_plan_scope_hash and requested_evidence_plan_scope_hash == evidence_plan_scope_hash
    )
    runtime_qa_scope_matches = bool(runtime_qa_scope_hash and requested_runtime_qa_scope_hash == runtime_qa_scope_hash)
    if not explicit_request:
        status = "worker_runtime_qa_dry_run_missing"
    elif not approved:
        status = "worker_runtime_qa_dry_run_blocked_operator_approval_required"
    elif not runtime_request_ready:
        status = "worker_runtime_qa_dry_run_blocked_execution_request_required"
    elif not recipe_ready:
        status = "worker_runtime_qa_dry_run_blocked_recipe_not_ready"
    elif not requested_request_task_id or not requested_evidence_plan_scope_hash or not requested_runtime_qa_scope_hash:
        status = "worker_runtime_qa_dry_run_blocked_scope_hash_required"
    elif not request_task_matches or not evidence_plan_scope_matches or not runtime_qa_scope_matches:
        status = "worker_runtime_qa_dry_run_blocked_scope_hash_mismatch"
    else:
        status = "worker_runtime_qa_dry_run_ready_execution_pending"
    ready = status == "worker_runtime_qa_dry_run_ready_execution_pending"
    rows = [
        _worker_runtime_qa_dry_run_row(
            "explicit_post_runtime_qa_dry_run_done",
            passed=explicit_request,
            status="passed" if explicit_request else "blocked_missing_dry_run",
            evidence="Dry-run receipt must be created through POST /api/worker/runtime-qa-dry-run.",
            next_action="Run the dry-run only after a runtime QA execution request ticket exists.",
        ),
        _worker_runtime_qa_dry_run_row(
            "operator_approval_recorded",
            passed=approved,
            status="passed" if approved else "blocked_operator_approval_required",
            evidence=f"operator_approved={approved}",
            next_action="Require explicit operator approval for the dry-run scope.",
        ),
        _worker_runtime_qa_dry_run_row(
            "runtime_qa_execution_request_ready",
            passed=runtime_request_ready,
            status="passed" if runtime_request_ready else "blocked_execution_request_required",
            evidence=f"execution_request_status={runtime_qa_execution_request.get('status')}",
            next_action="Generate a scope-bound runtime QA execution request before dry-run.",
        ),
        _worker_runtime_qa_dry_run_row(
            "runtime_qa_execution_recipe_ready",
            passed=recipe_ready,
            status="passed" if recipe_ready else "blocked_recipe_not_ready",
            evidence=f"recipe_status={runtime_qa_execution_recipe.get('status')}; phase_count={runtime_qa_execution_recipe.get('phase_count')}",
            next_action="Keep the runtime QA recipe visible before dry-run.",
        ),
        _worker_runtime_qa_dry_run_row(
            "request_task_id_bound",
            passed=request_task_matches,
            status="passed" if request_task_matches else "blocked_request_task_id_mismatch_or_missing",
            evidence=f"requested_request_task_id={requested_request_task_id}; latest_request_task_id={request_task_id}",
            next_action="Regenerate the dry-run if the request ticket changes.",
        ),
        _worker_runtime_qa_dry_run_row(
            "evidence_plan_scope_hash_bound",
            passed=evidence_plan_scope_matches,
            status="passed" if evidence_plan_scope_matches else "blocked_scope_hash_mismatch_or_missing",
            evidence=(
                f"requested_scope_hash_short={requested_evidence_plan_scope_hash[:12]}; "
                f"latest_scope_hash_short={evidence_plan_scope_hash[:12]}"
            ),
            next_action="Regenerate the dry-run if the production evidence plan scope ticket changes.",
        ),
        _worker_runtime_qa_dry_run_row(
            "runtime_qa_scope_hash_bound",
            passed=runtime_qa_scope_matches,
            status="passed" if runtime_qa_scope_matches else "blocked_scope_hash_mismatch_or_missing",
            evidence=(
                f"requested_runtime_hash_short={requested_runtime_qa_scope_hash[:12]}; "
                f"latest_runtime_hash_short={runtime_qa_scope_hash[:12]}"
            ),
            next_action="Regenerate the dry-run if the runtime QA execution recipe changes.",
        ),
        _worker_runtime_qa_dry_run_row(
            "phase_plan_visible",
            passed=bool(runtime_qa_execution_recipe.get("allowed_execution_sequence")),
            status="passed" if runtime_qa_execution_recipe.get("allowed_execution_sequence") else "blocked_phase_plan_missing",
            evidence=f"phase_count={runtime_qa_execution_recipe.get('phase_count')}",
            next_action="Keep every runtime QA phase visible before a future execution task.",
        ),
        _worker_runtime_qa_dry_run_row(
            "runtime_qa_execution_still_pending",
            passed=True,
            status="passed_dry_run_only",
            evidence="Dry-run verifies scope and phase plan locally but does not create or execute a runtime QA task.",
            next_action="Submit a separate explicit runtime QA execution task only after reviewing the dry-run receipt.",
        ),
        _worker_runtime_qa_dry_run_row(
            "no_process_provider_trade_secret_boundary",
            passed=True,
            status="passed_no_side_effects",
            evidence="Dry-run starts no worker, pings no Redis, starts no scheduler, dispatches no task, calls no provider/model/GitHub, trades nothing, mutates no action, and exposes no secret.",
            next_action="Preserve these false side-effect flags in any future runtime QA execution.",
        ),
    ]
    phase_rows = _worker_runtime_qa_dry_run_phase_rows(runtime_qa_execution_recipe, dry_run_ready=ready)
    local_blockers = [str(row["criterion"]) for row in rows if row.get("blocks_dry_run")]
    return {
        "packet_key": RUNTIME_QA_DRY_RUN_PACKET_KEY,
        "schema_version": RUNTIME_QA_DRY_RUN_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_worker_runtime_qa_dry_run_no_process_start_no_dispatch",
        "ltg": "LTG-06/LTG-11",
        "mode": "button_gated_local_runtime_qa_dry_run",
        "explicit_runtime_qa_dry_run_done": bool(explicit_request),
        "dry_run_task_id": task_id,
        "requested_at": requested_at,
        "button_gated": True,
        "local_dry_run_only": True,
        "operator_approved": approved,
        "local_runtime_qa_dry_run_done": ready,
        "runtime_qa_dry_run_done": ready,
        "local_dry_run_ready": ready,
        "ready_for_separate_runtime_qa_execution": ready,
        "ready_to_mark_production_worker_complete": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "runtime_qa_execution_request_ready": runtime_request_ready,
        "runtime_qa_execution_request_status": runtime_qa_execution_request.get("status") or "missing",
        "runtime_qa_execution_request_task_id": request_task_id,
        "requested_runtime_qa_execution_request_task_id": requested_request_task_id,
        "requested_runtime_qa_execution_request_task_id_matches_latest": request_task_matches,
        "runtime_qa_execution_recipe_ready": recipe_ready,
        "runtime_qa_execution_recipe_status": runtime_qa_execution_recipe.get("status") or "missing",
        "production_evidence_plan_scope_hash": evidence_plan_scope_hash if evidence_plan_scope_matches else "",
        "production_evidence_plan_scope_hash_short": evidence_plan_scope_hash[:12],
        "requested_evidence_plan_scope_hash_short": requested_evidence_plan_scope_hash[:12],
        "requested_evidence_plan_scope_hash_matches_latest": evidence_plan_scope_matches,
        "runtime_qa_scope_hash": runtime_qa_scope_hash if runtime_qa_scope_matches else "",
        "runtime_qa_scope_hash_short": runtime_qa_scope_hash[:12],
        "requested_runtime_qa_scope_hash_short": requested_runtime_qa_scope_hash[:12],
        "requested_runtime_qa_scope_hash_matches_latest": runtime_qa_scope_matches,
        "target_worker_task_route": "future POST /api/worker/runtime-qa-execution",
        "target_worker_task_type": "run_worker_runtime_qa_execution",
        "target_phases": list(runtime_qa_execution_recipe.get("allowed_execution_sequence") or []),
        "target_phase_count": int(runtime_qa_execution_recipe.get("phase_count") or 0),
        "dry_run_phase_count": len(phase_rows),
        "required_evidence": list(runtime_qa_execution_recipe.get("required_evidence") or []),
        "local_blocker_count": len(local_blockers) if not ready else 0,
        "production_blocker_count": len(rows),
        "row_count": len(rows),
        "phase_row_count": len(phase_rows),
        "local_blockers": [] if ready else local_blockers,
        "not_allowed_next_steps": [
            "treat_dry_run_as_runtime_qa_execution",
            "start Celery from runtime QA dry-run",
            "ping Redis from runtime QA dry-run",
            "start scheduler from runtime QA dry-run",
            "dispatch worker task from runtime QA dry-run",
            "autoschedule Tushare DeepSeek GitHub tasks",
            "inspect Redis URL or credentials from runtime QA dry-run",
            "mark_production_worker_complete_from_runtime_qa_dry_run",
        ],
        "request_params_safe": {
            "requested_from": safe_payload.get("requested_from") or "worker_runtime_page",
            "operator_approved": approved,
            "request_task_id": requested_request_task_id,
            "evidence_plan_scope_hash": requested_evidence_plan_scope_hash,
            "runtime_qa_scope_hash": requested_runtime_qa_scope_hash,
            "external_sources_allowed": False,
            "starts_celery_worker": False,
            "pings_redis": False,
            "starts_scheduler": False,
            "task_dispatched": False,
            "production_worker_complete": False,
        },
        "rows": rows,
        "phase_rows": phase_rows,
        "runtime_qa_task_created": False,
        "runtime_qa_task_executed": False,
        "runtime_qa_execution_implemented": False,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "healthcheck_executed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_worker_runtime_qa_dry_run",
                "source": "worker runtime QA execution request and runtime QA recipe",
                "row_count": len(rows),
                "phase_row_count": len(phase_rows),
                "local_fetched_at": _now_iso(),
                "call_status": status,
                "external": False,
                "external_calls_triggered": False,
                "redis_pinged": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [
            "Worker runtime QA dry-run 只生成本地 dry-run receipt；不会启动 Celery、ping Redis、启动 scheduler 或派发任务。",
            "该 dry-run 不调用 Tushare、DeepSeek、GitHub，不执行真实交易，不修改 strategy action，不代表 production worker 完成。",
        ],
        "note": "This explicit runtime QA dry-run validates the current request ticket and runtime recipe locally. It does not create or execute runtime QA, start processes, dispatch tasks, call providers/models/probes, execute trades, mutate strategy action, expose secrets, or prove production worker completion.",
    }


def _missing_worker_runtime_qa_dry_run_packet(
    runtime_qa_execution_request: dict[str, Any],
    runtime_qa_execution_recipe: dict[str, Any],
    read_status: str = "packet_missing",
) -> dict[str, Any]:
    receipt = _worker_runtime_qa_dry_run_receipt(
        runtime_qa_execution_request=runtime_qa_execution_request,
        runtime_qa_execution_recipe=runtime_qa_execution_recipe,
        explicit_request=False,
    )
    receipt["source_packet_read_status"] = read_status
    receipt["source_packet_present"] = False
    receipt["cache_get_initializes_meta_store"] = False
    return receipt


def _read_worker_runtime_qa_dry_run_packet(
    runtime_qa_execution_request: dict[str, Any],
    runtime_qa_execution_recipe: dict[str, Any],
) -> dict[str, Any]:
    packet, read_status = _read_worker_meta_packet_no_init(RUNTIME_QA_DRY_RUN_PACKET_KEY)
    if not isinstance(packet, dict):
        return _missing_worker_runtime_qa_dry_run_packet(
            runtime_qa_execution_request,
            runtime_qa_execution_recipe,
            read_status,
        )
    receipt = _json_safe(packet.get("worker_runtime_qa_dry_run_receipt") or packet)
    if not isinstance(receipt, dict) or receipt.get("schema_version") != RUNTIME_QA_DRY_RUN_SCHEMA_VERSION:
        return _missing_worker_runtime_qa_dry_run_packet(
            runtime_qa_execution_request,
            runtime_qa_execution_recipe,
            read_status,
        )
    rebuilt = _worker_runtime_qa_dry_run_receipt(
        runtime_qa_execution_request=runtime_qa_execution_request,
        runtime_qa_execution_recipe=runtime_qa_execution_recipe,
        explicit_request=receipt.get("explicit_runtime_qa_dry_run_done") is True,
        task_id=str(receipt.get("dry_run_task_id") or "") or None,
        requested_at=str(receipt.get("requested_at") or "") or None,
        payload_safe=receipt.get("request_params_safe") if isinstance(receipt.get("request_params_safe"), dict) else {},
    )
    rebuilt["source_packet_read_status"] = read_status
    rebuilt["source_packet_present"] = True
    rebuilt["cache_get_initializes_meta_store"] = False
    return rebuilt


def _worker_runtime_qa_event_log_path() -> Path:
    return SQLITE_META_PATH.parent / "worker_runtime_qa_events.jsonl"


def _append_worker_runtime_qa_event(event: dict[str, Any]) -> dict[str, Any]:
    path = _worker_runtime_qa_event_log_path()
    safe_event = _json_safe(event)
    event_sha256 = _json_sha256(safe_event)
    safe_event["event_sha256"] = event_sha256
    before_size = path.stat().st_size if path.exists() else 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe_event, ensure_ascii=False, sort_keys=True, default=str))
        handle.write("\n")
    after_size = path.stat().st_size if path.exists() else 0
    line_count = 0
    last_event: dict[str, Any] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            line_count += 1
            try:
                decoded = json.loads(stripped)
                if isinstance(decoded, dict):
                    last_event = decoded
            except Exception:
                last_event = {}
    return {
        "schema_version": "worker_runtime_qa_append_only_event_result.v1",
        "status": "append_only_worker_log_event_verified"
        if after_size > before_size and last_event.get("event_sha256") == event_sha256
        else "append_only_worker_log_event_blocked",
        "event_log_path": str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else path.name,
        "event_sha256": event_sha256,
        "line_count": line_count,
        "bytes_appended": max(after_size - before_size, 0),
        "append_only_write_done": after_size > before_size,
        "readback_event_hash_matches": last_event.get("event_sha256") == event_sha256,
        "contains_secret": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _worker_v04_scope_component(scope_hash: str) -> str:
    text = str(scope_hash or "").strip()
    if text and all(char.isalnum() or char in {"_", "-"} for char in text) and len(text) <= 96:
        return text
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _worker_v04_write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{hashlib.sha256(str(path).encode('utf-8')).hexdigest()[:12]}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str), encoding="utf-8")
    temp_path.replace(path)


def _worker_v04_path_label(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(WORKER_V04_RUNTIME_ROOT.resolve())
    except (OSError, ValueError):
        return path.name
    return f"v04_acceptance/{relative.as_posix()}"


def _worker_v04_pool_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_pool = payload.get("pool") or payload.get("symbols") or []
    if not isinstance(raw_pool, list):
        return []
    items: list[dict[str, Any]] = []
    for index, item in enumerate(raw_pool):
        if isinstance(item, dict):
            symbol = str(item.get("symbol") or item.get("ts_code") or f"LOCAL{index:04d}.SZ").strip().upper()
            weight = item.get("weight", index + 1)
        else:
            symbol = str(item or f"LOCAL{index:04d}.SZ").strip().upper()
            weight = index + 1
        try:
            safe_weight = float(weight)
        except Exception:
            safe_weight = float(index + 1)
        items.append({"symbol": symbol, "pool_index": index, "weight": safe_weight})
    return items


def _worker_v04_append_event(path: Path, event: dict[str, Any]) -> dict[str, Any]:
    safe_event = _json_safe(event)
    event_sha = _json_sha256(safe_event)
    safe_event["event_sha256"] = event_sha
    before_size = path.stat().st_size if path.exists() else 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe_event, ensure_ascii=False, sort_keys=True, default=str))
        handle.write("\n")
    after_size = path.stat().st_size if path.exists() else 0
    return {
        "event_sha256": event_sha,
        "bytes_appended": max(after_size - before_size, 0),
        "append_only_write_done": after_size > before_size,
    }


def _worker_v04_current_pointer(runtime_dir: Path, pointer: str = "current") -> dict[str, Any]:
    path = runtime_dir / f"{pointer}.json"
    if not path.exists():
        return {"status": "missing", "pointer": pointer}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "read_failed", "pointer": pointer}
    checksum = str(payload.get("manifest_sha256") or "")
    check_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"manifest_sha256", "pointer_kind", "pointer", "status"}
    }
    return {
        **payload,
        "status": "ready" if checksum and _json_sha256(check_payload) == checksum else "checksum_mismatch",
        "pointer": pointer,
    }


def _worker_v04_local_batch_runtime(
    payload_safe: dict[str, Any], *, task_id: str, executed_at: str, persist_packet: bool = True
) -> dict[str, Any]:
    scope_hash = str(payload_safe.get("runtime_scope_hash") or payload_safe.get("scope_hash") or "")
    scope_component = _worker_v04_scope_component(scope_hash)
    runtime_dir = WORKER_V04_RUNTIME_ROOT / scope_component / "worker_runtime"
    if not runtime_dir.resolve().is_relative_to(WORKER_V04_RUNTIME_ROOT.resolve()):
        raise ValueError("invalid_worker_v04_scope")
    pool = _worker_v04_pool_items(payload_safe)
    chunk_size = max(1, min(int(payload_safe.get("chunk_size") or 10), 100))
    fail_on_symbol = str(payload_safe.get("fail_on_symbol") or "").strip().upper()
    event_log_path = runtime_dir / "events.jsonl"
    current_before = _worker_v04_current_pointer(runtime_dir, "current")
    last_good_before = _worker_v04_current_pointer(runtime_dir, "last_good")
    chunks = [pool[index : index + chunk_size] for index in range(0, len(pool), chunk_size)]
    processed: list[dict[str, Any]] = []
    failed_symbol = ""
    stage_rows: list[dict[str, Any]] = []
    for chunk_index, chunk in enumerate(chunks):
        stage_status = "success"
        chunk_outputs = []
        for item in chunk:
            if fail_on_symbol and item["symbol"] == fail_on_symbol:
                stage_status = "failed"
                failed_symbol = item["symbol"]
                break
            output = {
                "symbol": item["symbol"],
                "pool_index": item["pool_index"],
                "score": round((item["pool_index"] + 1) * item["weight"], 6),
            }
            processed.append(output)
            chunk_outputs.append(output)
        event_result = _worker_v04_append_event(
            event_log_path,
            {
                "schema_version": "worker_v04_local_batch_event.v1",
                "task_id": task_id,
                "chunk_index": chunk_index,
                "chunk_size": len(chunk),
                "processed_count": len(chunk_outputs),
                "stage_status": stage_status,
                "failed_symbol": failed_symbol,
                "runtime_scope_hash_short": scope_hash[:12],
                "contains_secret": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "redis_pinged": False,
                "celery_started": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
        )
        stage_rows.append(
            {
                "chunk_index": chunk_index,
                "status": stage_status,
                "chunk_size": len(chunk),
                "processed_count": len(chunk_outputs),
                "event_sha256": event_result["event_sha256"],
                "append_only_write_done": event_result["append_only_write_done"],
            }
        )
        if stage_status == "failed":
            break
    status = "worker_v04_local_batch_runtime_success" if len(processed) == len(pool) and pool else "worker_v04_local_batch_runtime_failed_partial"
    manifest = {
        "schema_version": "worker_v04_local_batch_runtime_manifest.v1",
        "status": status,
        "task_id": task_id,
        "runtime_scope_hash_short": scope_hash[:12],
        "pool_count": len(pool),
        "processed_count": len(processed),
        "chunk_size": chunk_size,
        "chunk_count": len(chunks),
        "stage_count": len(stage_rows),
        "failed_symbol": failed_symbol,
        "result_checksum": _json_sha256({"processed": processed}),
        "append_only_event_count": len(stage_rows),
        "local_runtime_not_full_market_claim": True,
        "local_runtime_is_not_celery_redis_production": True,
        "contains_secret": False,
        "external_calls_triggered": False,
    }
    manifest["manifest_sha256"] = _json_sha256({key: value for key, value in manifest.items() if key != "status"})
    manifest_path = runtime_dir / f"manifest_{task_id}.json"
    _worker_v04_write_json_atomic(manifest_path, manifest)
    if status == "worker_v04_local_batch_runtime_success":
        if current_before.get("status") == "ready":
            last_good_payload = {
                key: value
                for key, value in current_before.items()
                if key not in {"status", "pointer"}
            }
            _worker_v04_write_json_atomic(runtime_dir / "last_good.json", {**last_good_payload, "pointer_kind": "last_good"})
        _worker_v04_write_json_atomic(runtime_dir / "current.json", {**manifest, "pointer_kind": "current"})
    current_after = _worker_v04_current_pointer(runtime_dir, "current")
    last_good_after = _worker_v04_current_pointer(runtime_dir, "last_good")
    if persist_packet:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(
            RUNTIME_QA_EXECUTION_PACKET_KEY,
            {
                "schema_version": "worker_v04_local_batch_runtime_packet.v1",
                "status": status,
                "task_id": task_id,
                "runtime_scope_hash_short": scope_hash[:12],
                "pool_count": len(pool),
                "processed_count": len(processed),
                "stage_rows": stage_rows,
                "manifest_sha256": manifest["manifest_sha256"],
                "contains_secret": False,
            },
        )
    return {
        "status": status,
        "runtime_dir": _worker_v04_path_label(runtime_dir),
        "event_log_path": _worker_v04_path_label(event_log_path),
        "manifest_path": _worker_v04_path_label(manifest_path),
        "manifest": manifest,
        "pool_count": len(pool),
        "processed_count": len(processed),
        "chunk_size": chunk_size,
        "chunk_count": len(chunks),
        "stage_rows": stage_rows,
        "append_only_event_count": len(stage_rows),
        "current_before": current_before,
        "last_good_before": last_good_before,
        "current_after": current_after,
        "last_good_after": last_good_after,
        "last_good_preserved": bool(status != "worker_v04_local_batch_runtime_success" and last_good_after.get("status") == "ready"),
        "local_runtime_not_full_market_claim": True,
        "local_runtime_is_not_celery_redis_production": True,
        "runtime_packet_persisted": persist_packet,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _run_worker_v04_local_batch_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_worker_v04_local_batch_runtime",
        output_packet_key=RUNTIME_QA_EXECUTION_PACKET_KEY,
        payload=payload,
        current_step="worker_v04_local_batch_runtime_queued",
        warnings=[
            "Worker v0.4 local batch runtime 只在当前 Python 进程处理调用方 pool；不启动 Celery/Redis，不声称 full-market。",
        ],
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    approved = bool(
        payload_safe.get("operator_approved") is True
        and payload_safe.get("confirm_local_in_process_runtime") is True
        and payload_safe.get("confirm_scope_hash") == str(payload_safe.get("runtime_scope_hash") or payload_safe.get("scope_hash") or "")
    )
    if not approved:
        return task_service.update_task_status(
            str(task["task_id"]),
            status="failed",
            progress=1.0,
            current_step="worker_v04_local_batch_runtime_blocked_confirmation_required",
            error_message_safe="worker_v04_local_batch_runtime_blocked_confirmation_required",
            call_ledger=[],
        ) or task
    executed_at = _now_iso()
    task_service.update_task_status(
        str(task["task_id"]),
        status="running",
        progress=0.4,
        current_step="worker_v04_local_batch_runtime_processing_pool",
    )
    persist_packet = payload_safe.get("persist_runtime_packet") is not False
    result = _worker_v04_local_batch_runtime(
        payload_safe,
        task_id=str(task["task_id"]),
        executed_at=executed_at,
        persist_packet=persist_packet,
    )
    succeeded = result["status"] == "worker_v04_local_batch_runtime_success"
    ledger = [
        {
            "api": "local_worker_v04_in_process_batch_runtime",
            "source": "explicit_post_payload_pool",
            "row_count": result["processed_count"],
            "pool_count": result["pool_count"],
            "chunk_count": result["chunk_count"],
            "call_status": result["status"],
            "event_log_path": result["event_log_path"],
            "manifest_sha256": result["manifest"]["manifest_sha256"],
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
        }
    ]
    updated = task_service.update_task_status(
        str(task["task_id"]),
        status="success" if succeeded else "failed",
        progress=1.0,
        current_step=result["status"],
        error_message_safe=None if succeeded else result["status"],
        call_ledger=ledger,
        warning=(
            "worker_v04_local_batch_runtime_success_current_promoted"
            if succeeded
            else "worker_v04_local_batch_runtime_partial_failure_last_good_preserved"
        ),
    ) or task
    updated["worker_v04_runtime"] = result
    return updated


def _local_task_control_metadata_evidence(task_map: dict[str, Any], readback_map: dict[str, Any]) -> dict[str, Any]:
    retry_policy = task_map.get("retry_policy") if isinstance(task_map.get("retry_policy"), dict) else {}
    readback_retry = readback_map.get("retry_policy") if isinstance(readback_map.get("retry_policy"), dict) else {}
    lock_policy = task_map.get("lock_policy") if isinstance(task_map.get("lock_policy"), dict) else {}
    readback_lock = readback_map.get("lock_policy") if isinstance(readback_map.get("lock_policy"), dict) else {}
    dedupe_policy = task_map.get("dedupe_policy") if isinstance(task_map.get("dedupe_policy"), dict) else {}
    readback_dedupe = readback_map.get("dedupe_policy") if isinstance(readback_map.get("dedupe_policy"), dict) else {}
    catalog = task_service.build_task_catalog()
    supports_cancel = bool(catalog.get("policy", {}).get("supports_local_task_cancel"))
    retry_visible = bool(
        retry_policy.get("manual_retry_allowed") is True
        and retry_policy.get("auto_retry_enabled") is False
        and retry_policy.get("cache_api_can_retry") is False
        and readback_retry.get("manual_retry_allowed") is True
        and readback_retry.get("auto_retry_enabled") is False
    )
    lock_visible = bool(
        lock_policy.get("conflict_detection_enabled") is True
        and lock_policy.get("cache_api_can_acquire_lock") is False
        and readback_lock.get("conflict_detection_enabled") is True
        and readback_lock.get("cache_api_can_acquire_lock") is False
    )
    dedupe_visible = bool(
        dedupe_policy.get("duplicate_detection_enabled") is True
        and dedupe_policy.get("cache_api_can_dedupe") is False
        and readback_dedupe.get("duplicate_detection_enabled") is True
        and readback_dedupe.get("cache_api_can_dedupe") is False
    )
    verified = bool(retry_visible and supports_cancel and lock_visible and dedupe_visible)
    return {
        "schema_version": "worker_runtime_local_task_control_metadata_evidence.v1",
        "status": "local_task_control_metadata_verified" if verified else "local_task_control_metadata_blocked",
        "scope": "local_task_store_control_metadata_no_celery_no_redis",
        "retry_metadata_verified": retry_visible,
        "cancel_metadata_verified": supports_cancel,
        "lock_metadata_verified": lock_visible,
        "dedupe_metadata_verified": dedupe_visible,
        "local_task_control_metadata_verified": verified,
        "cross_process_task_control_verified": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "evidence_boundary": "local task control metadata is not cross-process Celery/Redis runtime proof",
    }


def _worker_runtime_qa_execution_row(
    criterion: str,
    *,
    passed: bool,
    status: str,
    evidence: str,
    next_action: str,
    production_blocker: bool = False,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker and not passed),
        "runtime_qa_executed": bool(passed),
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "evidence": evidence,
        "next_action": next_action,
    }


def _worker_runtime_qa_execution_phase_rows(
    runtime_qa_execution_recipe: dict[str, Any],
    *,
    execution_ready: bool,
    append_only_log_verified: bool,
    local_fallback_verified: bool,
    cross_process_verified: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    completed_phases = {
        "evidence_plan_scope_ticket",
        "queue_binding_and_synthetic_round_trip",
        "append_only_worker_log_validation",
        "scheduler_default_off_runtime",
        "provider_model_no_autoschedule_boundary",
        "local_fallback_rollback_plan",
    }
    for index, phase in enumerate(runtime_qa_execution_recipe.get("allowed_execution_sequence") or [], start=1):
        phase_key = str(phase)
        phase_done = bool(
            execution_ready
            and (
                phase_key in completed_phases
                or (phase_key == "append_only_worker_log_validation" and append_only_log_verified)
                or (phase_key == "local_fallback_rollback_plan" and local_fallback_verified)
                or (phase_key == "cross_process_retry_cancel_lock_dedupe" and cross_process_verified)
            )
        )
        rows.append(
            {
                "phase_index": index,
                "phase": phase_key,
                "phase_label": WORKER_RUNTIME_QA_EXECUTION_PHASE_LABELS.get(phase_key, phase_key),
                "status": "passed_local_runtime_evidence" if phase_done else "pending_production_runtime_evidence",
                "runtime_qa_done": phase_done,
                "production_ready": False,
                "worker_started": False,
                "redis_pinged": False,
                "scheduler_started": False,
                "task_dispatched": False,
                "provider_model_task_dispatched": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
            }
        )
    return rows


def _worker_runtime_qa_execution_receipt(
    *,
    runtime_qa_dry_run: dict[str, Any],
    runtime_qa_execution_recipe: dict[str, Any],
    explicit_execution: bool = False,
    task_id: str | None = None,
    executed_at: str | None = None,
    payload_safe: dict[str, Any] | None = None,
    runtime_task: dict[str, Any] | None = None,
    readback: dict[str, Any] | None = None,
    append_only_log: dict[str, Any] | None = None,
    cross_process_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_payload = payload_safe if isinstance(payload_safe, dict) else {}
    task_map = runtime_task if isinstance(runtime_task, dict) else {}
    readback_map = readback if isinstance(readback, dict) else {}
    append_map = append_only_log if isinstance(append_only_log, dict) else {}
    cross_process_map = cross_process_probe if isinstance(cross_process_probe, dict) else {}
    approved = safe_payload.get("operator_approved") is True or safe_payload.get("approved") is True
    dry_run_ready = runtime_qa_dry_run.get("local_dry_run_ready") is True
    dry_run_task_id = str(runtime_qa_dry_run.get("dry_run_task_id") or "")
    requested_dry_run_task_id = str(
        safe_payload.get("dry_run_task_id")
        or safe_payload.get("runtime_qa_dry_run_task_id")
        or safe_payload.get("request_task_id")
        or ""
    )
    evidence_plan_scope_hash = str(runtime_qa_dry_run.get("production_evidence_plan_scope_hash") or "")
    runtime_qa_scope_hash = str(runtime_qa_dry_run.get("runtime_qa_scope_hash") or "")
    requested_evidence_plan_scope_hash = str(
        safe_payload.get("evidence_plan_scope_hash") or safe_payload.get("production_evidence_plan_scope_hash") or ""
    )
    requested_runtime_qa_scope_hash = str(
        safe_payload.get("runtime_qa_scope_hash") or safe_payload.get("runtime_execution_scope_hash") or ""
    )
    dry_run_task_matches = bool(dry_run_task_id and requested_dry_run_task_id == dry_run_task_id)
    evidence_plan_scope_matches = bool(
        evidence_plan_scope_hash and requested_evidence_plan_scope_hash == evidence_plan_scope_hash
    )
    runtime_qa_scope_matches = bool(runtime_qa_scope_hash and requested_runtime_qa_scope_hash == runtime_qa_scope_hash)
    local_round_trip = bool(task_map.get("status") == "success" and readback_map.get("status") == "success")
    task_log_round_trip = bool(
        isinstance(task_map.get("task_log"), list)
        and isinstance(readback_map.get("task_log"), list)
        and len(task_map.get("task_log") or []) > 0
        and len(readback_map.get("task_log") or []) > 0
    )
    append_only_log_verified = bool(
        append_map.get("append_only_write_done") is True
        and append_map.get("readback_event_hash_matches") is True
        and append_map.get("contains_secret") is False
    )
    local_fallback_verified = bool(
        local_round_trip
        and readback_map.get("storage_source") in {"memory", "sqlite_meta", "memory_and_sqlite"}
        and task_map.get("external_calls_triggered") is not True
    )
    task_control_metadata = _local_task_control_metadata_evidence(task_map, readback_map)
    local_task_control_metadata_verified = bool(
        task_control_metadata.get("local_task_control_metadata_verified") is True
    )
    cross_process_task_control_verified = bool(
        cross_process_map.get("schema_version") == "worker_task_control_cross_process_probe.v1"
        and cross_process_map.get("status") == "cross_process_task_control_verified"
        and cross_process_map.get("readback_found") is True
        and cross_process_map.get("readback_hash_matches") is True
        and cross_process_map.get("task_status") == "success"
        and int(cross_process_map.get("task_log_count") or 0) > 0
        and cross_process_map.get("retry_metadata_visible") is True
        and cross_process_map.get("lock_metadata_visible") is True
        and cross_process_map.get("dedupe_metadata_visible") is True
        and cross_process_map.get("contains_secret") is False
        and cross_process_map.get("external_calls_triggered") is False
        and cross_process_map.get("tushare_called") is False
        and cross_process_map.get("deepseek_called") is False
        and cross_process_map.get("github_called") is False
        and cross_process_map.get("does_not_execute_trades") is True
        and cross_process_map.get("does_not_modify_strategy_action") is True
    )
    if not explicit_execution:
        status = "worker_runtime_qa_execution_missing"
    elif not approved:
        status = "worker_runtime_qa_execution_blocked_operator_approval_required"
    elif not dry_run_ready:
        status = "worker_runtime_qa_execution_blocked_dry_run_required"
    elif not requested_dry_run_task_id or not requested_evidence_plan_scope_hash or not requested_runtime_qa_scope_hash:
        status = "worker_runtime_qa_execution_blocked_scope_hash_required"
    elif not dry_run_task_matches or not evidence_plan_scope_matches or not runtime_qa_scope_matches:
        status = "worker_runtime_qa_execution_blocked_scope_hash_mismatch"
    elif not local_round_trip or not task_log_round_trip or not append_only_log_verified:
        status = "worker_runtime_qa_execution_blocked_local_round_trip"
    else:
        status = "worker_runtime_qa_execution_ready_local_fallback_evidence"
    ready = status == "worker_runtime_qa_execution_ready_local_fallback_evidence"
    rows = [
        _worker_runtime_qa_execution_row(
            "explicit_post_runtime_qa_execution_done",
            passed=explicit_execution,
            status="passed" if explicit_execution else "blocked_missing_execution",
            evidence="Runtime QA execution must be created through POST /api/worker/runtime-qa-execution.",
            next_action="Run this only after request and dry-run receipts exist.",
        ),
        _worker_runtime_qa_execution_row(
            "operator_approval_recorded",
            passed=approved,
            status="passed" if approved else "blocked_operator_approval_required",
            evidence=f"operator_approved={approved}",
            next_action="Require explicit operator approval for local runtime QA execution.",
        ),
        _worker_runtime_qa_execution_row(
            "runtime_qa_dry_run_ready",
            passed=dry_run_ready,
            status="passed" if dry_run_ready else "blocked_dry_run_required",
            evidence=f"dry_run_status={runtime_qa_dry_run.get('status')}",
            next_action="Generate a scope-bound runtime QA dry-run before local execution.",
        ),
        _worker_runtime_qa_execution_row(
            "dry_run_task_id_bound",
            passed=dry_run_task_matches,
            status="passed" if dry_run_task_matches else "blocked_dry_run_task_id_mismatch_or_missing",
            evidence=f"requested_dry_run_task_id={requested_dry_run_task_id}; latest_dry_run_task_id={dry_run_task_id}",
            next_action="Regenerate execution payload if the dry-run receipt changes.",
        ),
        _worker_runtime_qa_execution_row(
            "evidence_plan_scope_hash_bound",
            passed=evidence_plan_scope_matches,
            status="passed" if evidence_plan_scope_matches else "blocked_scope_hash_mismatch_or_missing",
            evidence=(
                f"requested_scope_hash_short={requested_evidence_plan_scope_hash[:12]}; "
                f"latest_scope_hash_short={evidence_plan_scope_hash[:12]}"
            ),
            next_action="Regenerate execution if the production evidence plan scope changes.",
        ),
        _worker_runtime_qa_execution_row(
            "runtime_qa_scope_hash_bound",
            passed=runtime_qa_scope_matches,
            status="passed" if runtime_qa_scope_matches else "blocked_scope_hash_mismatch_or_missing",
            evidence=(
                f"requested_runtime_hash_short={requested_runtime_qa_scope_hash[:12]}; "
                f"latest_runtime_hash_short={runtime_qa_scope_hash[:12]}"
            ),
            next_action="Regenerate execution if the runtime QA recipe changes.",
        ),
        _worker_runtime_qa_execution_row(
            "local_fallback_round_trip_executed",
            passed=local_round_trip and local_fallback_verified,
            status="passed" if local_round_trip and local_fallback_verified else "blocked_local_round_trip",
            evidence=f"task_status={task_map.get('status')}; readback_status={readback_map.get('status')}; storage_source={readback_map.get('storage_source')}",
            next_action="Keep this as local fallback evidence; do not call it Celery/Redis process proof.",
        ),
        _worker_runtime_qa_execution_row(
            "safe_task_log_round_trip_verified",
            passed=task_log_round_trip,
            status="passed" if task_log_round_trip else "blocked_task_log_round_trip",
            evidence=f"task_log_count={len(task_map.get('task_log') or [])}; readback_task_log_count={len(readback_map.get('task_log') or [])}",
            next_action="Keep task logs redacted and structured before any worker-process promotion.",
        ),
        _worker_runtime_qa_execution_row(
            "local_task_control_metadata_verified",
            passed=local_task_control_metadata_verified,
            status="passed_local_metadata"
            if local_task_control_metadata_verified
            else "blocked_local_task_control_metadata",
            evidence=(
                f"retry={task_control_metadata['retry_metadata_verified']}; "
                f"cancel={task_control_metadata['cancel_metadata_verified']}; "
                f"lock={task_control_metadata['lock_metadata_verified']}; "
                f"dedupe={task_control_metadata['dedupe_metadata_verified']}"
            ),
            next_action="Use this as local task-control evidence only; prove cross-process behavior later with Celery/Redis runtime QA.",
        ),
        _worker_runtime_qa_execution_row(
            "cross_process_task_control_probe_verified",
            passed=cross_process_task_control_verified,
            status="passed_local_python_process_probe"
            if cross_process_task_control_verified
            else "pending_cross_process_task_control_probe",
            evidence=(
                f"probe_status={cross_process_map.get('status') or 'missing'}; "
                f"readback_hash_matches={cross_process_map.get('readback_hash_matches') is True}; "
                f"task_log_count={cross_process_map.get('task_log_count') or 0}"
            ),
            next_action=(
                "Keep this as local cross-process SQLite task-control evidence; Celery/Redis process proof remains separate."
            ),
            production_blocker=True,
        ),
        _worker_runtime_qa_execution_row(
            "append_only_worker_log_event_verified",
            passed=append_only_log_verified,
            status="passed" if append_only_log_verified else "blocked_append_only_log_event",
            evidence=f"event_sha256={append_map.get('event_sha256') or ''}; line_count={append_map.get('line_count') or 0}",
            next_action="Use this local JSONL proof as direct append-only evidence, not as Celery worker log proof.",
        ),
        _worker_runtime_qa_execution_row(
            "scheduler_default_off_runtime",
            passed=True,
            status="passed",
            evidence="Runtime QA execution starts no scheduler and records scheduler_started=false.",
            next_action="Keep scheduler production activation separate and explicit.",
        ),
        _worker_runtime_qa_execution_row(
            "provider_model_no_autoschedule_boundary",
            passed=True,
            status="passed",
            evidence="Runtime QA execution calls no Tushare, DeepSeek, GitHub, provider, model, or probe path.",
            next_action="Keep provider/model/probe tasks behind explicit task gates.",
        ),
        _worker_runtime_qa_execution_row(
            "no_trade_no_action_boundary",
            passed=True,
            status="passed",
            evidence="Runtime QA execution does not execute trades and does not mutate strategy action.",
            next_action="Keep real trading outside LTG-06 worker runtime QA.",
        ),
        _worker_runtime_qa_execution_row(
            "celery_redis_process_evidence_still_pending",
            passed=False,
            status="pending_manual_celery_redis_runtime_evidence",
            evidence="Local runtime QA does not start Celery and does not ping Redis.",
            next_action="Collect Celery/Redis process evidence in a separately approved runtime path.",
            production_blocker=True,
        ),
        _worker_runtime_qa_execution_row(
            "production_worker_completion_stays_blocked",
            passed=True,
            status="passed",
            evidence="production_worker_complete remains false after local runtime QA execution.",
            next_action="Promote only after Celery/Redis, cross-process controls, and production review evidence pass.",
        ),
    ]
    production_blockers = [str(row["criterion"]) for row in rows if row.get("production_blocker")]
    phase_rows = _worker_runtime_qa_execution_phase_rows(
        runtime_qa_execution_recipe,
        execution_ready=ready,
        append_only_log_verified=append_only_log_verified,
        local_fallback_verified=local_fallback_verified,
        cross_process_verified=cross_process_task_control_verified,
    )
    return {
        "packet_key": RUNTIME_QA_EXECUTION_PACKET_KEY,
        "schema_version": RUNTIME_QA_EXECUTION_SCHEMA_VERSION,
        "status": status,
        "scope": "button_gated_worker_runtime_qa_execution_local_fallback_no_process_start",
        "ltg": "LTG-06/LTG-11",
        "mode": "button_gated_local_runtime_qa_execution",
        "explicit_runtime_qa_execution_done": bool(explicit_execution),
        "execution_task_id": task_id,
        "executed_at": executed_at,
        "button_gated": True,
        "operator_approved": approved,
        "local_runtime_qa_execution_done": ready,
        "runtime_qa_done": ready,
        "runtime_qa_task_created": bool(task_id),
        "runtime_qa_task_executed": ready,
        "runtime_qa_execution_implemented": True,
        "runtime_qa_dry_run_ready": dry_run_ready,
        "runtime_qa_dry_run_status": runtime_qa_dry_run.get("status") or "missing",
        "runtime_qa_dry_run_task_id": dry_run_task_id,
        "requested_runtime_qa_dry_run_task_id": requested_dry_run_task_id,
        "requested_runtime_qa_dry_run_task_id_matches_latest": dry_run_task_matches,
        "runtime_qa_execution_recipe_ready": runtime_qa_execution_recipe.get("local_recipe_ready") is True,
        "production_evidence_plan_scope_hash": evidence_plan_scope_hash if evidence_plan_scope_matches else "",
        "production_evidence_plan_scope_hash_short": evidence_plan_scope_hash[:12],
        "requested_evidence_plan_scope_hash_short": requested_evidence_plan_scope_hash[:12],
        "requested_evidence_plan_scope_hash_matches_latest": evidence_plan_scope_matches,
        "runtime_qa_scope_hash": runtime_qa_scope_hash if runtime_qa_scope_matches else "",
        "runtime_qa_scope_hash_short": runtime_qa_scope_hash[:12],
        "requested_runtime_qa_scope_hash_short": requested_runtime_qa_scope_hash[:12],
        "requested_runtime_qa_scope_hash_matches_latest": runtime_qa_scope_matches,
        "local_fallback_round_trip_verified": local_fallback_verified,
        "local_task_round_trip_verified": local_round_trip,
        "task_log_round_trip_verified": task_log_round_trip,
        "task_log_persistence_verified": task_log_round_trip,
        "local_task_control_metadata_verified": local_task_control_metadata_verified,
        "cross_process_task_control_verified": cross_process_task_control_verified,
        "task_control_metadata_evidence": task_control_metadata,
        "cross_process_task_control_probe": cross_process_map,
        "append_only_worker_log_verified": append_only_log_verified,
        "append_only_worker_log_event_result": append_map,
        "scheduler_default_off_runtime_verified": True,
        "provider_model_no_autoschedule_boundary_verified": True,
        "no_trade_no_action_boundary_verified": True,
        "local_blocker_count": 0 if ready else sum(1 for row in rows if not row.get("passed") and not row.get("production_blocker")),
        "production_blocker_count": len(production_blockers),
        "row_count": len(rows),
        "phase_row_count": len(phase_rows),
        "production_blockers": production_blockers,
        "not_allowed_next_steps": [
            "treat_local_runtime_qa_as_celery_process_proof",
            "start Celery from runtime QA execution",
            "ping Redis from runtime QA execution",
            "start scheduler from runtime QA execution",
            "autoschedule Tushare DeepSeek GitHub tasks",
            "inspect Redis URL or credentials from runtime QA execution",
            "mark_production_worker_complete_from_local_runtime_qa",
        ],
        "request_params_safe": {
            "requested_from": safe_payload.get("requested_from") or "worker_runtime_page",
            "operator_approved": approved,
            "dry_run_task_id": requested_dry_run_task_id,
            "evidence_plan_scope_hash_short": requested_evidence_plan_scope_hash[:12],
            "runtime_qa_scope_hash_short": requested_runtime_qa_scope_hash[:12],
            "external_sources_allowed": False,
            "starts_celery_worker": False,
            "pings_redis": False,
            "starts_scheduler": False,
            "provider_model_task_dispatched": False,
            "production_worker_complete": False,
        },
        "rows": rows,
        "phase_rows": phase_rows,
        "production_worker_complete": False,
        "activation_ready": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_worker_runtime_qa_execution",
                "source": "worker_runtime_qa_dry_run + local_task_store + append_only_jsonl_event",
                "row_count": len(rows),
                "phase_row_count": len(phase_rows),
                "task_id": task_id,
                "local_fetched_at": executed_at,
                "call_status": status,
                "event_sha256": append_map.get("event_sha256") or "",
                "external": False,
                "external_calls_triggered": False,
                "redis_pinged": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [
            "Worker runtime QA execution 只执行本地 fallback round-trip 和 append-only JSONL evidence；不会启动 Celery、ping Redis 或启动 scheduler。",
            "该 execution 不调用 Tushare、DeepSeek、GitHub，不执行真实交易，不修改 strategy action，不代表 production worker 完成。",
        ],
        "note": "This explicit local runtime QA execution records direct local fallback and append-only log evidence. It does not prove live Celery/Redis process orchestration or production worker completion.",
    }


def _missing_worker_runtime_qa_execution_packet(
    runtime_qa_dry_run: dict[str, Any],
    runtime_qa_execution_recipe: dict[str, Any],
    read_status: str = "packet_missing",
) -> dict[str, Any]:
    receipt = _worker_runtime_qa_execution_receipt(
        runtime_qa_dry_run=runtime_qa_dry_run,
        runtime_qa_execution_recipe=runtime_qa_execution_recipe,
        explicit_execution=False,
    )
    receipt["source_packet_read_status"] = read_status
    receipt["source_packet_present"] = False
    receipt["cache_get_initializes_meta_store"] = False
    return receipt


def _read_worker_runtime_qa_execution_packet(
    runtime_qa_dry_run: dict[str, Any],
    runtime_qa_execution_recipe: dict[str, Any],
) -> dict[str, Any]:
    packet, read_status = _read_worker_meta_packet_no_init(RUNTIME_QA_EXECUTION_PACKET_KEY)
    if not isinstance(packet, dict):
        return _missing_worker_runtime_qa_execution_packet(
            runtime_qa_dry_run,
            runtime_qa_execution_recipe,
            read_status,
        )
    if packet.get("schema_version") == "worker_v04_local_batch_runtime_packet.v1":
        local_done = bool(
            packet.get("status") == "worker_v04_local_batch_runtime_success"
            and int(packet.get("processed_count") or 0) == int(packet.get("pool_count") or 0)
            and int(packet.get("pool_count") or 0) > 0
        )
        stage_rows = list(packet.get("stage_rows") or [])
        return {
            **_json_safe(packet),
            "mode": "cache_only_v04_local_batch_runtime_readback",
            "scope": "local_supplied_pool_not_celery_redis_production",
            "local_runtime_qa_execution_done": local_done,
            "runtime_qa_done": False,
            "runtime_qa_task_created": True,
            "runtime_qa_task_executed": True,
            "runtime_qa_execution_implemented": True,
            "local_fallback_round_trip_verified": local_done,
            "local_task_round_trip_verified": local_done,
            "task_log_round_trip_verified": bool(stage_rows),
            "task_log_persistence_verified": bool(stage_rows),
            "local_task_control_metadata_verified": False,
            "cross_process_task_control_verified": False,
            "cross_process_task_control_probe": {},
            "append_only_worker_log_verified": bool(
                stage_rows and all(row.get("append_only_write_done") is True for row in stage_rows)
            ),
            "scheduler_default_off_runtime_verified": True,
            "provider_model_no_autoschedule_boundary_verified": True,
            "no_trade_no_action_boundary_verified": True,
            "production_worker_complete": False,
            "worker_started": False,
            "celery_worker_started": False,
            "redis_pinged": False,
            "scheduler_started": False,
            "task_dispatched": False,
            "provider_model_task_dispatched": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "rows": stage_rows,
            "phase_rows": [],
            "call_ledger": [],
            "source_packet_read_status": read_status,
            "source_packet_present": True,
            "cache_get_initializes_meta_store": False,
            "warnings": [
                "v0.4 local batch readback 仅证明 supplied pool 的本地进程分块与 append-only 回放。",
                "未启动 Celery/Redis/worker process；production worker completion 仍为 false。",
            ],
        }
    receipt = _json_safe(packet.get("worker_runtime_qa_execution_receipt") or packet)
    if not isinstance(receipt, dict) or receipt.get("schema_version") != RUNTIME_QA_EXECUTION_SCHEMA_VERSION:
        return _missing_worker_runtime_qa_execution_packet(
            runtime_qa_dry_run,
            runtime_qa_execution_recipe,
            read_status,
        )
    receipt.setdefault("local_runtime_qa_execution_done", False)
    receipt.setdefault("runtime_qa_done", False)
    receipt.setdefault("runtime_qa_task_created", False)
    receipt.setdefault("runtime_qa_task_executed", False)
    receipt.setdefault("runtime_qa_execution_implemented", False)
    receipt.setdefault("local_fallback_round_trip_verified", False)
    receipt.setdefault("local_task_round_trip_verified", False)
    receipt.setdefault("task_log_round_trip_verified", False)
    receipt.setdefault("task_log_persistence_verified", False)
    receipt.setdefault("local_task_control_metadata_verified", False)
    receipt.setdefault("cross_process_task_control_verified", False)
    receipt.setdefault("cross_process_task_control_probe", {})
    receipt.setdefault("append_only_worker_log_verified", False)
    receipt.setdefault("scheduler_default_off_runtime_verified", False)
    receipt.setdefault("provider_model_no_autoschedule_boundary_verified", False)
    receipt.setdefault("no_trade_no_action_boundary_verified", False)
    receipt.setdefault("production_worker_complete", False)
    receipt.setdefault("worker_started", False)
    receipt.setdefault("celery_worker_started", False)
    receipt.setdefault("redis_pinged", False)
    receipt.setdefault("scheduler_started", False)
    receipt.setdefault("task_dispatched", False)
    receipt.setdefault("provider_model_task_dispatched", False)
    receipt.setdefault("external_calls_triggered", False)
    receipt.setdefault("tushare_called", False)
    receipt.setdefault("deepseek_called", False)
    receipt.setdefault("github_called", False)
    receipt.setdefault("does_not_execute_trades", True)
    receipt.setdefault("does_not_modify_strategy_action", True)
    receipt.setdefault("contains_secret", False)
    receipt.setdefault("rows", [])
    receipt.setdefault("phase_rows", [])
    receipt.setdefault("call_ledger", [])
    receipt["source_packet_read_status"] = read_status
    receipt["source_packet_present"] = True
    receipt["cache_get_initializes_meta_store"] = False
    return receipt


def _worker_runtime_durable_evidence_recipe_row(
    evidence_key: str,
    *,
    passed: bool,
    evidence: str,
    required_evidence: str,
    next_action: str,
    source_contract: str,
) -> dict[str, Any]:
    return {
        "evidence_key": evidence_key,
        "evidence_label": WORKER_RUNTIME_DURABLE_EVIDENCE_LABELS.get(evidence_key, evidence_key),
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "local_ready": bool(passed),
        "durable_evidence_present": bool(passed),
        "production_ready": False,
        "production_blocker": not passed,
        "required_before_production": True,
        "source_contract": source_contract,
        "evidence": evidence,
        "required_evidence": required_evidence,
        "next_action": next_action,
        "cache_only": True,
        "runs_no_commands": True,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "healthcheck_executed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _read_worker_celery_filesystem_roundtrip_evidence() -> dict[str, Any]:
    try:
        payload = json.loads(WORKER_CELERY_FILESYSTEM_ROUNDTRIP_EVIDENCE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _worker_celery_filesystem_roundtrip_ready(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("schema_version") == "worker_celery_filesystem_roundtrip_smoke.v1"
        and payload.get("status") == "celery_filesystem_roundtrip_passed"
        and payload.get("direct_evidence_layer") == "L3_local_celery_filesystem_roundtrip_not_redis"
        and payload.get("broker_url") == "filesystem://"
        and payload.get("result_backend") == "cache+memory://"
        and payload.get("celery_available") is True
        and payload.get("celery_testing_worker_started") is True
        and payload.get("task_dispatched") is True
        and payload.get("task_result_returned") is True
        and payload.get("filesystem_broker_used") is True
        and payload.get("redis_broker_used") is False
        and payload.get("redis_pinged") is False
        and payload.get("production_worker_complete") is False
        and payload.get("external_calls_triggered") is False
        and payload.get("tushare_called") is False
        and payload.get("deepseek_called") is False
        and payload.get("github_called") is False
        and payload.get("does_not_execute_trades") is True
        and payload.get("does_not_modify_strategy_action") is True
        and payload.get("contains_secret") is False
    )


def _read_worker_redis_roundtrip_evidence() -> dict[str, Any]:
    try:
        payload = json.loads(WORKER_REDIS_ROUNDTRIP_EVIDENCE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _worker_redis_roundtrip_ready(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("schema_version") == "worker_redis_roundtrip_smoke.v1"
        and payload.get("status") == "redis_roundtrip_passed"
        and payload.get("direct_evidence_layer") == "L3_local_redis_celery_roundtrip_not_production_worker"
        and payload.get("redis_server_binary_available") is True
        and payload.get("redis_server_started") is True
        and payload.get("redis_pinged") is True
        and payload.get("redis_broker_used") is True
        and payload.get("redis_url_configured") is True
        and payload.get("redis_url_exposed") is False
        and payload.get("redis_url_contains_credentials") is False
        and payload.get("celery_testing_worker_started") is True
        and payload.get("task_dispatched") is True
        and payload.get("task_result_returned") is True
        and payload.get("production_worker_complete") is False
        and payload.get("external_calls_triggered") is False
        and payload.get("tushare_called") is False
        and payload.get("deepseek_called") is False
        and payload.get("github_called") is False
        and payload.get("does_not_execute_trades") is True
        and payload.get("does_not_modify_strategy_action") is True
        and payload.get("contains_secret") is False
    )


def _worker_runtime_durable_evidence_recipe(
    *,
    production_blocker_audit: dict[str, Any],
    healthcheck_qa_contract: dict[str, Any],
    task_log_persistence_audit: dict[str, Any],
    queue_routing_contract: dict[str, Any],
    readiness_receipt: dict[str, Any],
    production_activation_receipt: dict[str, Any],
    production_evidence_plan: dict[str, Any],
    runtime_qa_execution_recipe: dict[str, Any],
    runtime_qa_execution_request: dict[str, Any],
    runtime_qa_dry_run: dict[str, Any],
    runtime_qa_execution: dict[str, Any],
    production_promotion_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    promotion_review = production_promotion_review if isinstance(production_promotion_review, dict) else {}
    celery_filesystem_roundtrip = _read_worker_celery_filesystem_roundtrip_evidence()
    celery_filesystem_roundtrip_visible = _worker_celery_filesystem_roundtrip_ready(
        celery_filesystem_roundtrip
    )
    redis_roundtrip = _read_worker_redis_roundtrip_evidence()
    redis_roundtrip_visible = _worker_redis_roundtrip_ready(redis_roundtrip)
    blocker_visible = production_blocker_audit.get("schema_version") == "worker_production_blocker_audit.v1"
    healthcheck_visible = healthcheck_qa_contract.get("schema_version") == "worker_healthcheck_qa_contract.v1"
    task_log_visible = task_log_persistence_audit.get("schema_version") == "worker_task_log_persistence_audit.v1"
    queue_routing_visible = queue_routing_contract.get("schema_version") == "worker_queue_routing_contract.v1"
    readiness_visible = readiness_receipt.get("schema_version") == "worker_production_readiness_receipt.v1"
    activation_visible = production_activation_receipt.get("schema_version") == "worker_production_activation_receipt.v1"
    evidence_plan_visible = production_evidence_plan.get("schema_version") == PRODUCTION_EVIDENCE_PLAN_SCHEMA_VERSION
    runtime_recipe_ready = runtime_qa_execution_recipe.get("local_recipe_ready") is True
    runtime_request_visible = (
        runtime_qa_execution_request.get("schema_version") == RUNTIME_QA_EXECUTION_REQUEST_SCHEMA_VERSION
        and runtime_qa_execution_request.get("local_execution_request_ready") is True
        and runtime_qa_execution_request.get("requested_evidence_plan_scope_hash_matches_latest") is True
        and runtime_qa_execution_request.get("requested_runtime_qa_scope_hash_matches_latest") is True
        and runtime_qa_execution_request.get("runtime_qa_task_created") is False
        and runtime_qa_execution_request.get("runtime_qa_task_executed") is False
    )
    runtime_dry_run_visible = (
        runtime_qa_dry_run.get("schema_version") == RUNTIME_QA_DRY_RUN_SCHEMA_VERSION
        and runtime_qa_dry_run.get("local_dry_run_ready") is True
        and runtime_qa_dry_run.get("requested_runtime_qa_execution_request_task_id_matches_latest") is True
        and runtime_qa_dry_run.get("requested_evidence_plan_scope_hash_matches_latest") is True
        and runtime_qa_dry_run.get("requested_runtime_qa_scope_hash_matches_latest") is True
        and runtime_qa_dry_run.get("runtime_qa_task_created") is False
        and runtime_qa_dry_run.get("runtime_qa_task_executed") is False
    )
    local_fallback_rollback_visible = (
        runtime_qa_execution.get("schema_version") == RUNTIME_QA_EXECUTION_SCHEMA_VERSION
        and runtime_qa_execution.get("status") == "worker_runtime_qa_execution_ready_local_fallback_evidence"
        and runtime_qa_execution.get("local_runtime_qa_execution_done") is True
        and runtime_qa_execution.get("local_fallback_round_trip_verified") is True
        and runtime_qa_execution.get("local_task_round_trip_verified") is True
        and runtime_qa_execution.get("task_log_round_trip_verified") is True
        and runtime_qa_execution.get("task_log_persistence_verified") is True
        and runtime_qa_execution.get("production_worker_complete") is False
        and runtime_qa_execution.get("worker_started") is False
        and runtime_qa_execution.get("celery_worker_started") is False
        and runtime_qa_execution.get("redis_pinged") is False
        and runtime_qa_execution.get("scheduler_started") is False
        and runtime_qa_execution.get("task_dispatched") is False
        and runtime_qa_execution.get("provider_model_task_dispatched") is False
        and runtime_qa_execution.get("external_calls_triggered") is False
        and runtime_qa_execution.get("tushare_called") is False
        and runtime_qa_execution.get("deepseek_called") is False
        and runtime_qa_execution.get("github_called") is False
        and runtime_qa_execution.get("does_not_execute_trades") is True
        and runtime_qa_execution.get("does_not_modify_strategy_action") is True
        and runtime_qa_execution.get("contains_secret") is False
    )
    runtime_execution_phase_rows = {
        str(row.get("phase") or ""): row
        for row in runtime_qa_execution.get("phase_rows", [])
        if isinstance(row, dict)
    }
    cross_process_controls_visible = (
        local_fallback_rollback_visible
        and runtime_qa_execution.get("cross_process_task_control_verified") is True
        and runtime_execution_phase_rows.get("cross_process_retry_cancel_lock_dedupe", {}).get("runtime_qa_done")
        is True
    )
    append_only_worker_log_visible = (
        local_fallback_rollback_visible
        and runtime_qa_execution.get("append_only_worker_log_verified") is True
        and runtime_execution_phase_rows.get("append_only_worker_log_validation", {}).get("runtime_qa_done") is True
    )
    scheduler_default_off_runtime_visible = (
        local_fallback_rollback_visible
        and runtime_qa_execution.get("scheduler_default_off_runtime_verified") is True
        and runtime_qa_execution.get("scheduler_started") is False
        and runtime_execution_phase_rows.get("scheduler_default_off_runtime", {}).get("runtime_qa_done") is True
    )
    provider_model_no_autoschedule_visible = (
        local_fallback_rollback_visible
        and runtime_qa_execution.get("provider_model_no_autoschedule_boundary_verified") is True
        and runtime_qa_execution.get("provider_model_task_dispatched") is False
        and runtime_qa_execution.get("external_calls_triggered") is False
        and runtime_qa_execution.get("tushare_called") is False
        and runtime_qa_execution.get("deepseek_called") is False
        and runtime_qa_execution.get("github_called") is False
        and runtime_execution_phase_rows.get("provider_model_no_autoschedule_boundary", {}).get("runtime_qa_done")
        is True
    )
    queue_round_trip_visible = (
        local_fallback_rollback_visible
        and queue_routing_visible
        and runtime_execution_phase_rows.get("queue_binding_and_synthetic_round_trip", {}).get("runtime_qa_done")
        is True
        and runtime_qa_execution.get("local_task_round_trip_verified") is True
        and runtime_qa_execution.get("task_log_round_trip_verified") is True
        and runtime_qa_execution.get("worker_started") is False
        and runtime_qa_execution.get("celery_worker_started") is False
        and runtime_qa_execution.get("redis_pinged") is False
        and runtime_qa_execution.get("task_dispatched") is False
        and runtime_qa_execution.get("external_calls_triggered") is False
    )
    production_promotion_review_visible = (
        promotion_review.get("schema_version") == PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION
        and promotion_review.get("local_promotion_review_ready") is True
        and promotion_review.get("runtime_qa_execution_visible") is True
        and promotion_review.get("worker_started") is False
        and promotion_review.get("redis_pinged") is False
        and promotion_review.get("scheduler_started") is False
        and promotion_review.get("task_dispatched") is False
        and promotion_review.get("provider_model_task_dispatched") is False
        and promotion_review.get("production_worker_complete") is False
        and promotion_review.get("external_calls_triggered") is False
        and promotion_review.get("tushare_called") is False
        and promotion_review.get("deepseek_called") is False
        and promotion_review.get("github_called") is False
        and promotion_review.get("does_not_execute_trades") is True
        and promotion_review.get("does_not_modify_strategy_action") is True
        and promotion_review.get("contains_secret") is False
    )
    no_process_boundary = (
        runtime_qa_execution_recipe.get("worker_started") is False
        and runtime_qa_execution_recipe.get("redis_pinged") is False
        and runtime_qa_execution_recipe.get("scheduler_started") is False
        and runtime_qa_execution_recipe.get("task_dispatched") is False
        and runtime_qa_execution_recipe.get("provider_model_task_dispatched") is False
        and runtime_qa_execution_recipe.get("healthcheck_executed") is False
        and runtime_qa_execution_recipe.get("external_calls_triggered") is False
        and runtime_qa_execution_recipe.get("tushare_called") is False
        and runtime_qa_execution_recipe.get("deepseek_called") is False
        and runtime_qa_execution_recipe.get("github_called") is False
        and runtime_qa_execution_recipe.get("does_not_execute_trades") is True
        and runtime_qa_execution_recipe.get("does_not_modify_strategy_action") is True
        and runtime_qa_execution_recipe.get("contains_secret") is False
        and runtime_qa_execution_request.get("worker_started") is False
        and runtime_qa_execution_request.get("redis_pinged") is False
        and runtime_qa_execution_request.get("scheduler_started") is False
        and runtime_qa_execution_request.get("task_dispatched") is False
        and runtime_qa_execution_request.get("provider_model_task_dispatched") is False
        and runtime_qa_execution_request.get("external_calls_triggered") is False
        and runtime_qa_execution_request.get("tushare_called") is False
        and runtime_qa_execution_request.get("deepseek_called") is False
        and runtime_qa_execution_request.get("github_called") is False
        and runtime_qa_execution_request.get("does_not_execute_trades") is True
        and runtime_qa_execution_request.get("does_not_modify_strategy_action") is True
        and runtime_qa_execution_request.get("contains_secret") is False
        and runtime_qa_dry_run.get("worker_started") is False
        and runtime_qa_dry_run.get("redis_pinged") is False
        and runtime_qa_dry_run.get("scheduler_started") is False
        and runtime_qa_dry_run.get("task_dispatched") is False
        and runtime_qa_dry_run.get("provider_model_task_dispatched") is False
        and runtime_qa_dry_run.get("external_calls_triggered") is False
        and runtime_qa_dry_run.get("tushare_called") is False
        and runtime_qa_dry_run.get("deepseek_called") is False
        and runtime_qa_dry_run.get("github_called") is False
        and runtime_qa_dry_run.get("does_not_execute_trades") is True
        and runtime_qa_dry_run.get("does_not_modify_strategy_action") is True
        and runtime_qa_dry_run.get("contains_secret") is False
    )
    local_recipe_ready = all(
        [
            blocker_visible,
            healthcheck_visible,
            task_log_visible,
            queue_routing_visible,
            readiness_visible,
            activation_visible,
            evidence_plan_visible,
            runtime_recipe_ready,
            no_process_boundary,
        ]
    )
    rows = [
        _worker_runtime_durable_evidence_recipe_row(
            "production_blocker_audit_visible",
            passed=blocker_visible,
            source_contract="worker_production_blocker_audit",
            evidence=f"status={production_blocker_audit.get('status')}; blocker_count={production_blocker_audit.get('blocking_criterion_count')}",
            required_evidence="visible worker production blocker audit with production_worker_complete=false",
            next_action="keep production worker blockers visible until runtime evidence clears them",
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "healthcheck_qa_contract_visible",
            passed=healthcheck_visible,
            source_contract="worker_healthcheck_qa_contract",
            evidence=f"status={healthcheck_qa_contract.get('status')}; pending={healthcheck_qa_contract.get('pending_criterion_count')}",
            required_evidence="future healthcheck QA contract with no process start from cache",
            next_action="use the contract as the checklist for explicit synthetic/runtime healthcheck tasks",
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "task_log_persistence_audit_visible",
            passed=task_log_visible,
            source_contract="worker_task_log_persistence_audit",
            evidence=f"status={task_log_persistence_audit.get('status')}; blocker_count={task_log_persistence_audit.get('production_blocker_count')}",
            required_evidence="local task-log visibility audit plus future append-only worker log proof",
            next_action="collect append-only worker log evidence only after manual worker runtime QA starts",
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "queue_routing_contract_visible",
            passed=queue_routing_visible,
            source_contract="worker_queue_routing_contract",
            evidence=f"status={queue_routing_contract.get('status')}; queue_count={queue_routing_contract.get('queue_count')}",
            required_evidence="queue routing contract separating provider/model/probe queues from local queues",
            next_action="keep provider/model/probe routing button-gated while collecting runtime evidence",
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "readiness_receipt_visible",
            passed=readiness_visible,
            source_contract="worker_production_readiness_receipt",
            evidence=f"status={readiness_receipt.get('status')}",
            required_evidence="readiness receipt that only permits explicit POST healthcheck/activation review",
            next_action="preserve receipt as a next-step gate, not production completion",
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "activation_receipt_visible",
            passed=activation_visible,
            source_contract="worker_production_activation_receipt",
            evidence=f"status={production_activation_receipt.get('status')}",
            required_evidence="activation receipt listing manual Celery/Redis/runtime evidence prerequisites",
            next_action="use activation receipt as the runtime QA entry checklist",
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "production_evidence_plan_visible",
            passed=evidence_plan_visible,
            source_contract="worker_production_evidence_plan_receipt",
            evidence=f"status={production_evidence_plan.get('status')}; scope_hash_present={bool(production_evidence_plan.get('scope_ticket_sha256'))}",
            required_evidence="button-gated runtime QA scope ticket with SHA-256 fingerprint",
            next_action="create an approved evidence plan before manual runtime QA",
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "runtime_qa_execution_recipe_ready",
            passed=runtime_recipe_ready,
            source_contract="worker_runtime_qa_execution_recipe",
            evidence=f"status={runtime_qa_execution_recipe.get('status')}; phase_count={runtime_qa_execution_recipe.get('phase_count')}",
            required_evidence="ordered runtime QA execution recipe with every production phase still pending",
            next_action="follow runtime QA order without treating the recipe as runtime evidence",
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "runtime_qa_execution_request_visible",
            passed=runtime_request_visible,
            source_contract="worker_runtime_qa_execution_request_receipt",
            evidence=(
                f"status={runtime_qa_execution_request.get('status')}; "
                f"runtime_scope_hash_short={runtime_qa_execution_request.get('runtime_qa_scope_hash_short')}"
            ),
            required_evidence="button-gated runtime QA execution request bound to the evidence-plan scope and runtime recipe scope",
            next_action="generate a request ticket from the current Worker Runtime recipe before future runtime QA tasks",
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "runtime_qa_dry_run_receipt_visible",
            passed=runtime_dry_run_visible,
            source_contract="worker_runtime_qa_dry_run_receipt",
            evidence=(
                f"status={runtime_qa_dry_run.get('status')}; "
                f"runtime_scope_hash_short={runtime_qa_dry_run.get('runtime_qa_scope_hash_short')}"
            ),
            required_evidence="button-gated dry-run receipt bound to the current runtime QA request and recipe",
            next_action="generate a dry-run receipt before any future runtime QA execution task",
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "celery_process_evidence_required",
            passed=celery_filesystem_roundtrip_visible,
            source_contract="worker_celery_filesystem_roundtrip_smoke",
            evidence=(
                f"Local Celery filesystem-broker round-trip artifact ready at {WORKER_CELERY_FILESYSTEM_ROUNDTRIP_EVIDENCE_PATH}; "
                "testing worker started, task dispatched, Redis not used, production_worker_complete=false."
                if celery_filesystem_roundtrip_visible
                else "No Celery testing-worker filesystem-broker round-trip evidence has been collected."
            ),
            required_evidence="local Celery testing-worker task round-trip evidence; production Redis worker evidence remains separate",
            next_action=(
                "keep Redis broker evidence pending; do not treat local testing worker as production worker"
                if celery_filesystem_roundtrip_visible
                else "collect Celery testing-worker evidence only through an explicit local smoke run"
            ),
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "redis_broker_reachability_evidence_required",
            passed=redis_roundtrip_visible,
            source_contract="worker_redis_roundtrip_smoke",
            evidence=(
                f"Local Redis-backed Celery round-trip artifact ready at {WORKER_REDIS_ROUNDTRIP_EVIDENCE_PATH}; "
                "redis-server started on loopback, redacted Redis URL configured, ping succeeded, task returned, production_worker_complete=false."
                if redis_roundtrip_visible
                else "Redis is not pinged and Redis URL/credentials are not exposed by worker cache or this recipe."
            ),
            required_evidence="redacted Redis broker reachability evidence without URL/token/key/password values",
            next_action=(
                "Keep this as local Redis runtime evidence; production worker promotion remains separate."
                if redis_roundtrip_visible
                else "verify Redis only through explicit runtime QA with redacted output"
            ),
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "queue_round_trip_evidence_required",
            passed=queue_round_trip_visible,
            source_contract="worker_runtime_qa_execution_receipt",
            evidence=(
                "Local queue binding and synthetic task/status/log round trip are visible from runtime QA without Celery or Redis."
                if queue_round_trip_visible
                else "No local queue binding or synthetic task/status/log round trip has run."
            ),
            required_evidence="queue binding plus synthetic task enqueue/execute/readback evidence",
            next_action=(
                "Keep this as local synthetic queue evidence; Celery process and Redis reachability remain separate blockers."
                if queue_round_trip_visible
                else "prove queue round trip through the explicit runtime QA execution path"
            ),
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "cross_process_controls_evidence_required",
            passed=cross_process_controls_visible,
            source_contract="manual_worker_runtime_qa",
            evidence=(
                "Local Python cross-process task-control probe verified retry/cancel/lock/dedupe metadata."
                if cross_process_controls_visible
                else "Retry/cancel/lock/dedupe are local-ready but not proven across worker process boundaries."
            ),
            required_evidence="cross-process retry, cancel, lock, and dedupe evidence",
            next_action=(
                "Keep this as local cross-process SQLite task-control evidence; Celery/Redis process proof remains separate."
                if cross_process_controls_visible
                else "collect cross-process control proof during manual runtime QA"
            ),
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "append_only_worker_log_evidence_required",
            passed=append_only_worker_log_visible,
            source_contract="manual_worker_runtime_qa",
            evidence=(
                "Append-only JSONL worker runtime QA event was written and read back with matching hash."
                if append_only_worker_log_visible
                else "Local safe task logs exist, but append-only worker logs and cross-process log readback are not proven."
            ),
            required_evidence="append-only redacted worker log storage plus cross-process log readback",
            next_action=(
                "Keep append-only local event evidence redacted; live Celery worker logs remain separate."
                if append_only_worker_log_visible
                else "collect append-only worker log proof without raw payload or secret leakage"
            ),
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "scheduler_default_off_runtime_evidence_required",
            passed=scheduler_default_off_runtime_visible,
            source_contract="manual_worker_runtime_qa",
            evidence=(
                "Runtime QA execution recorded scheduler_started=false while collecting local fallback evidence."
                if scheduler_default_off_runtime_visible
                else "Scheduler is default-off in cache/review paths; runtime default-off evidence is not collected here."
            ),
            required_evidence="runtime proof that scheduler remains disabled unless separately approved",
            next_action=(
                "Preserve scheduler default-off evidence; production scheduler enablement still requires separate approval."
                if scheduler_default_off_runtime_visible
                else "capture scheduler default-off evidence during runtime QA"
            ),
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "provider_model_no_autoschedule_runtime_evidence_required",
            passed=provider_model_no_autoschedule_visible,
            source_contract="manual_worker_runtime_qa",
            evidence=(
                "Runtime QA execution dispatched no provider/model/probe task and called no Tushare, DeepSeek, or GitHub path."
                if provider_model_no_autoschedule_visible
                else "Provider/model/probe queues are button-gated locally, but live worker runtime no-autoschedule proof is pending."
            ),
            required_evidence="runtime evidence that Tushare/DeepSeek/GitHub-capable work remains explicit and ledgered",
            next_action=(
                "Keep provider/model/probe tasks explicit and ledgered; no autoschedule boundary is locally proven."
                if provider_model_no_autoschedule_visible
                else "prove provider/model no-autoschedule boundary in worker runtime QA"
            ),
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "local_fallback_rollback_evidence_required",
            passed=local_fallback_rollback_visible,
            source_contract="worker_runtime_qa_execution_receipt",
            evidence=(
                "Local fallback rollback evidence is present from the button-gated runtime QA execution receipt."
                if local_fallback_rollback_visible
                else "Local fallback is available, but rollback behavior from Celery/Redis to local fallback is not proven."
            ),
            required_evidence="graceful local fallback rollback evidence when Celery/Redis is unavailable or disabled",
            next_action=(
                "Keep this as local fallback rollback evidence only; Celery/Redis process proof remains separate."
                if local_fallback_rollback_visible
                else "prove fallback rollback before any production worker promotion"
            ),
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "production_worker_promotion_review_required",
            passed=production_promotion_review_visible,
            source_contract="worker_production_promotion_review",
            evidence=(
                f"status={promotion_review.get('status')}; production_blocker_count={promotion_review.get('production_blocker_count')}"
                if production_promotion_review_visible
                else f"production_blocker_count={production_evidence_plan.get('production_blocker_count')}"
            ),
            required_evidence="all runtime QA receipts plus explicit production worker promotion review",
            next_action=(
                "Keep production_worker_complete=false until Celery, Redis, and live queue round-trip evidence are reviewed."
                if production_promotion_review_visible
                else "hold production_worker_complete=false until every durable evidence row is direct and reviewed"
            ),
        ),
        _worker_runtime_durable_evidence_recipe_row(
            "no_process_provider_trade_secret_boundary",
            passed=no_process_boundary,
            source_contract="worker_runtime_qa_execution_recipe",
            evidence="Durable evidence recipe is cache-only and starts no process, pings no Redis, dispatches no task, calls no provider/model/GitHub, trades nothing, mutates no action, and exposes no secret.",
            required_evidence="worker process/provider/model/GitHub/trade/action/key boundaries remain false in cache, rows, and push gate",
            next_action="preserve no-process/no-provider/no-trade/no-secret boundary while adding future runtime evidence",
        ),
    ]
    blocked_rows = [row["evidence_key"] for row in rows if row.get("production_blocker")]
    return {
        "schema_version": WORKER_RUNTIME_DURABLE_EVIDENCE_SCHEMA_VERSION,
        "status": (
            "worker_runtime_durable_evidence_recipe_ready_production_pending"
            if local_recipe_ready
            else "worker_runtime_durable_evidence_recipe_blocked_local_contract"
        ),
        "scope": "local_worker_runtime_durable_evidence_recipe_no_process_start_no_dispatch",
        "ltg": "LTG-06/LTG-11",
        "local_recipe_ready": local_recipe_ready,
        "durable_evidence_complete": False,
        "durable_promotion_ready": False,
        "runtime_qa_done": local_fallback_rollback_visible,
        "production_worker_complete": False,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "runtime_qa_task_created_by_request": False,
        "runtime_qa_task_executed_by_request": False,
        "healthcheck_executed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "evidence_key_count": len(rows),
        "row_count": len(rows),
        "production_blocker_count": len(blocked_rows),
        "durable_evidence_blocker_count": len(blocked_rows),
        "runtime_qa_execution_request_ready": runtime_request_visible,
        "runtime_qa_execution_request_status": runtime_qa_execution_request.get("status"),
        "runtime_qa_dry_run_ready": runtime_dry_run_visible,
        "runtime_qa_dry_run_status": runtime_qa_dry_run.get("status"),
        "local_fallback_rollback_evidence_ready": local_fallback_rollback_visible,
        "celery_process_evidence_ready": celery_filesystem_roundtrip_visible,
        "local_celery_filesystem_roundtrip_evidence_ready": celery_filesystem_roundtrip_visible,
        "local_celery_filesystem_roundtrip_artifact": (
            str(WORKER_CELERY_FILESYSTEM_ROUNDTRIP_EVIDENCE_PATH)
            if celery_filesystem_roundtrip_visible
            else ""
        ),
        "redis_broker_reachability_evidence_ready": redis_roundtrip_visible,
        "local_redis_roundtrip_evidence_ready": redis_roundtrip_visible,
        "local_redis_roundtrip_artifact": (
            str(WORKER_REDIS_ROUNDTRIP_EVIDENCE_PATH) if redis_roundtrip_visible else ""
        ),
        "cross_process_controls_evidence_ready": cross_process_controls_visible,
        "append_only_worker_log_evidence_ready": append_only_worker_log_visible,
        "queue_round_trip_evidence_ready": queue_round_trip_visible,
        "scheduler_default_off_runtime_evidence_ready": scheduler_default_off_runtime_visible,
        "provider_model_no_autoschedule_runtime_evidence_ready": provider_model_no_autoschedule_visible,
        "production_worker_promotion_review_ready": production_promotion_review_visible,
        "production_worker_promotion_review_status": promotion_review.get("status"),
        "runtime_qa_execution_status": runtime_qa_execution.get("status"),
        "evidence_keys": [row["evidence_key"] for row in rows],
        "missing_durable_evidence": blocked_rows,
        "required_evidence": [
            "approved production evidence plan scope ticket",
            "manual Celery process evidence",
            "redacted Redis broker reachability evidence",
            "live queue binding and synthetic round-trip evidence",
            "cross-process retry/cancel/lock/dedupe evidence",
            "append-only worker log evidence",
            "scheduler default-off runtime evidence",
            "provider/model no-autoschedule runtime evidence",
            "local fallback rollback evidence",
            "production worker promotion review",
        ],
        "not_allowed_next_steps": [
            "treat_durable_recipe_as_runtime_qa_execution",
            "start Celery from durable recipe",
            "ping Redis from durable recipe",
            "start scheduler from durable recipe",
            "dispatch tasks from durable recipe",
            "autoschedule Tushare DeepSeek GitHub tasks",
            "inspect Redis URL or credentials from durable recipe",
            "mark_production_worker_complete_from_durable_recipe",
        ],
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_worker_runtime_durable_evidence_recipe",
                "source": "worker runtime QA recipe and production receipts",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": (
                    "worker_runtime_durable_evidence_recipe_ready_production_pending"
                    if local_recipe_ready
                    else "worker_runtime_durable_evidence_recipe_blocked_local_contract"
                ),
                "external": False,
                "external_calls_triggered": False,
                "redis_pinged": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This durable evidence recipe is a local LTG-06 checklist. It does not start Celery, ping Redis, start scheduler, dispatch tasks, call providers/models/probes, execute trades, mutate strategy action, expose secrets, or prove production worker completion.",
    }


def _worker_runtime_evidence_stage_scope_rows(
    evidence_scope: list[str],
    *,
    direct_stage_keys: list[str] | tuple[str, ...] | set[str] | None = None,
    stage_evidence: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    selected = set(evidence_scope)
    direct = set(direct_stage_keys or [])
    evidence_by_stage = dict(stage_evidence or {})
    return [
        {
            "stage_key": stage_key,
            "stage_label": WORKER_RUNTIME_EVIDENCE_STAGE_LABELS.get(stage_key, stage_key),
            "scope": "worker_runtime_evidence_stage_scope_manifest",
            "current_status": (
                "direct_evidence_ready_local_runtime_qa_production_pending"
                if stage_key in direct
                else "local_evidence_plan_scope_ticket_only"
            ),
            "target_status": "manual_runtime_qa_evidence_required",
            "selected_by_evidence_plan_scope": stage_key in selected,
            "direct_evidence_complete": stage_key in direct,
            "direct_evidence_layer": "L3_local_worker_runtime_execution_evidence" if stage_key in direct else "",
            "required_before_production": True,
            "production_blocker": stage_key not in direct,
            "worker_started": False,
            "local_celery_testing_worker_started": stage_key == "celery_process" and stage_key in direct,
            "redis_pinged": False,
            "scheduler_started": False,
            "task_dispatched": False,
            "local_celery_task_dispatched": stage_key == "celery_process" and stage_key in direct,
            "local_celery_filesystem_roundtrip_evidence_present": (
                stage_key == "celery_process" and stage_key in direct
            ),
            "provider_model_task_dispatched": False,
            "healthcheck_executed": False,
            "task_log_persistence_verified": stage_key == "append_only_worker_logs" and stage_key in direct,
            "append_only_worker_log_verified": stage_key == "append_only_worker_logs" and stage_key in direct,
            "cross_process_task_control_verified": (
                stage_key == "cross_process_retry_cancel_lock_dedupe" and stage_key in direct
            ),
            "activation_ready": False,
            "production_worker_complete": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "tushare_called_by_contract": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "evidence": evidence_by_stage.get(stage_key, "manual runtime QA direct evidence pending"),
            "missing_evidence": []
            if stage_key in direct
            else [f"{WORKER_RUNTIME_EVIDENCE_STAGE_LABELS.get(stage_key, stage_key)} direct runtime evidence"],
            "required_real_evidence": [
                "explicit manual runtime QA evidence",
                "safe runtime task log rows",
                "redacted worker/broker evidence",
                "production promotion review",
            ],
        }
        for stage_key in WORKER_RUNTIME_EVIDENCE_STAGE_KEYS
    ]


def _worker_runtime_evidence_stage_scope_manifest(
    *,
    production_evidence_plan: dict[str, Any],
    runtime_qa_execution: dict[str, Any],
    runtime_durable_evidence_recipe: dict[str, Any],
) -> dict[str, Any]:
    evidence_scope = [
        str(item)
        for item in (production_evidence_plan.get("scope_ticket_payload") or {}).get("evidence_scope", [])
    ]
    direct_stage_keys: list[str] = []
    if runtime_durable_evidence_recipe.get("celery_process_evidence_ready") is True:
        direct_stage_keys.append("celery_process")
    if runtime_durable_evidence_recipe.get("redis_broker_reachability_evidence_ready") is True:
        direct_stage_keys.append("redis_broker")
    if runtime_durable_evidence_recipe.get("local_fallback_rollback_evidence_ready") is True:
        direct_stage_keys.append("local_fallback_round_trip")
    if runtime_durable_evidence_recipe.get("cross_process_controls_evidence_ready") is True:
        direct_stage_keys.append("cross_process_retry_cancel_lock_dedupe")
    if runtime_durable_evidence_recipe.get("append_only_worker_log_evidence_ready") is True:
        direct_stage_keys.append("append_only_worker_logs")
    if runtime_durable_evidence_recipe.get("scheduler_default_off_runtime_evidence_ready") is True:
        direct_stage_keys.append("scheduler_default_off_runtime")
    if runtime_durable_evidence_recipe.get("provider_model_no_autoschedule_runtime_evidence_ready") is True:
        direct_stage_keys.append("provider_model_no_autoschedule_boundary")
    if (
        runtime_qa_execution.get("no_trade_no_action_boundary_verified") is True
        and runtime_qa_execution.get("does_not_execute_trades") is True
        and runtime_qa_execution.get("does_not_modify_strategy_action") is True
    ):
        direct_stage_keys.append("no_trade_no_action_boundary")
    if runtime_durable_evidence_recipe.get("production_worker_promotion_review_ready") is True:
        direct_stage_keys.append("production_worker_promotion_review")
    rows = _worker_runtime_evidence_stage_scope_rows(
        evidence_scope,
        direct_stage_keys=direct_stage_keys,
        stage_evidence={
            "celery_process": "local Celery filesystem-broker testing worker round-trip verified; production worker remains incomplete",
            "redis_broker": "local Redis-backed Celery testing worker round-trip verified with redacted broker evidence; production worker remains incomplete",
            "local_fallback_round_trip": "local runtime QA fallback task/status/log round trip verified without Celery or Redis",
            "cross_process_retry_cancel_lock_dedupe": "local runtime QA cross-process control probe verified without worker start",
            "append_only_worker_logs": "local runtime QA task log persistence and append-only worker log evidence verified",
            "scheduler_default_off_runtime": "local runtime QA verified scheduler remains off during runtime path",
            "provider_model_no_autoschedule_boundary": "local runtime QA verified provider/model autoscheduling remains disabled",
            "no_trade_no_action_boundary": "local runtime QA verified no trade execution and no strategy action mutation",
            "production_worker_promotion_review": "local production promotion review recorded while Celery/Redis production blockers remain",
        },
    )
    pending_stage_keys = [row["stage_key"] for row in rows if row.get("production_blocker") is True]
    return {
        "schema_version": WORKER_RUNTIME_STAGE_SCOPE_SCHEMA_VERSION,
        "status": "worker_runtime_evidence_stage_scope_visible_production_pending",
        "scope": "worker_runtime_evidence_stage_scope_manifest",
        "source_packet_key": PACKET_KEY,
        "source_receipt_key": "worker_runtime_durable_evidence_recipe",
        "stage_keys": list(WORKER_RUNTIME_EVIDENCE_STAGE_KEYS),
        "stage_key_count": len(WORKER_RUNTIME_EVIDENCE_STAGE_KEYS),
        "row_count": len(rows),
        "selected_stage_count": sum(1 for row in rows if row.get("selected_by_evidence_plan_scope") is True),
        "direct_evidence_stage_keys": direct_stage_keys,
        "direct_evidence_stage_count": len(direct_stage_keys),
        "pending_stage_keys": pending_stage_keys,
        "pending_stage_count": len(pending_stage_keys),
        "production_blocker_count": len(pending_stage_keys),
        "production_worker_complete": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "evidence_boundary": "worker_runtime_stage_scope_is_cache_visible_local_evidence_not_celery_redis_production_completion",
    }


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


def run_worker_activation_review(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_worker_activation_review",
        output_packet_key=ACTIVATION_REVIEW_PACKET_KEY,
        payload=payload,
        current_step="worker_activation_review_queued_no_process_start",
        warnings=[
            "Worker activation review 只审查本地 synthetic healthcheck 与 activation receipt；不会启动 Celery、ping Redis、启动 scheduler、派发任务或调用 provider/model/probe。"
        ],
    )
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="running",
        progress=0.5,
        current_step="worker_activation_review_reading_local_cache_only",
    ) or task
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    runtime_packet = read_worker_runtime_cache()
    synthetic_healthcheck = runtime_packet.get("worker_synthetic_healthcheck") if isinstance(runtime_packet.get("worker_synthetic_healthcheck"), dict) else {}
    activation_review_contract = runtime_packet.get("worker_activation_review_contract") if isinstance(runtime_packet.get("worker_activation_review_contract"), dict) else {}
    production_activation_receipt = runtime_packet.get("worker_production_activation_receipt") if isinstance(runtime_packet.get("worker_production_activation_receipt"), dict) else {}
    reviewed_at = _now_iso()
    receipt = _worker_activation_review_task_receipt(
        synthetic_healthcheck=synthetic_healthcheck,
        activation_review_contract=activation_review_contract,
        production_activation_receipt=production_activation_receipt,
        explicit_review=True,
        task_id=str(task.get("task_id") or ""),
        reviewed_at=reviewed_at,
        payload_safe=payload_safe,
    )
    rows = receipt.get("rows") if isinstance(receipt.get("rows"), list) else []
    ledger = [
        {
            "api": "local_worker_activation_review_task",
            "source": "worker_runtime_cache + worker_synthetic_healthcheck_packet",
            "row_count": len(rows),
            "task_id": task.get("task_id"),
            "local_fetched_at": reviewed_at,
            "call_status": receipt["status"],
            "request_params_safe": receipt["request_params_safe"],
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "redis_pinged": False,
            "celery_started": False,
            "scheduler_started": False,
            "task_dispatched": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "error_message_safe": "",
        }
    ]
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="success",
        progress=1.0,
        current_step="worker_activation_review_completed_local_only",
        call_ledger=ledger,
        warning="worker_activation_review_completed_no_process_start",
    ) or task
    packet = {
        "packet_key": ACTIVATION_REVIEW_PACKET_KEY,
        "schema_version": ACTIVATION_REVIEW_SCHEMA_VERSION,
        "status": receipt["status"],
        "scope": receipt["scope"],
        "mode": receipt["mode"],
        "executed_at": reviewed_at,
        "task_id": task.get("task_id"),
        "task_status": task.get("status"),
        "task_type": task.get("task_type"),
        "output_packet_key": ACTIVATION_REVIEW_PACKET_KEY,
        "worker_activation_review_task_receipt": receipt,
        "worker_activation_review_task_rows": rows,
        "activation_review_ready": receipt["activation_review_ready"],
        "production_worker_complete": False,
        "activation_ready": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": ledger,
        "warnings": [
            "这是显式 POST 的本地 Worker activation review，只证明本地 synthetic healthcheck 和 activation receipt 已被审查。",
            "它不启动 Celery、不 ping Redis、不启动 scheduler、不派发任务、不调用 Tushare/DeepSeek/GitHub、不执行真实交易，也不代表 production worker 完成。",
        ],
    }
    packet = _json_safe(packet)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(ACTIVATION_REVIEW_PACKET_KEY, packet)
    except Exception:
        packet.setdefault("warnings", []).append("worker_activation_review_packet_persist_failed_safe")
    return packet


def run_worker_production_evidence_plan(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_worker_production_evidence_plan",
        output_packet_key=PRODUCTION_EVIDENCE_PLAN_PACKET_KEY,
        payload=payload,
        current_step="worker_production_evidence_plan_queued_no_process_start",
        warnings=[
            "Worker production evidence plan 只生成后续 Celery/Redis runtime QA 证据清单和 scope ticket；不会启动 Celery、ping Redis、启动 scheduler、派发任务或调用 provider/model/probe。"
        ],
    )
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="running",
        progress=0.5,
        current_step="worker_production_evidence_plan_reading_local_cache_only",
    ) or task
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    runtime_packet = read_worker_runtime_cache()
    synthetic_healthcheck = runtime_packet.get("worker_synthetic_healthcheck") if isinstance(runtime_packet.get("worker_synthetic_healthcheck"), dict) else {}
    activation_review_task = runtime_packet.get("worker_activation_review_task_receipt") if isinstance(runtime_packet.get("worker_activation_review_task_receipt"), dict) else {}
    production_activation_receipt = runtime_packet.get("worker_production_activation_receipt") if isinstance(runtime_packet.get("worker_production_activation_receipt"), dict) else {}
    planned_at = _now_iso()
    receipt = _worker_production_evidence_plan_receipt(
        synthetic_healthcheck=synthetic_healthcheck,
        activation_review_task=activation_review_task,
        production_activation_receipt=production_activation_receipt,
        explicit_plan=True,
        task_id=str(task.get("task_id") or ""),
        planned_at=planned_at,
        payload_safe=payload_safe,
    )
    rows = receipt.get("rows") if isinstance(receipt.get("rows"), list) else []
    ledger = [
        {
            "api": "local_worker_production_evidence_plan",
            "source": "worker_runtime_cache + activation_review_task_receipt",
            "row_count": len(rows),
            "task_id": task.get("task_id"),
            "local_fetched_at": planned_at,
            "call_status": receipt["status"],
            "request_params_safe": receipt["request_params_safe"],
            "scope_ticket_sha256": receipt["scope_ticket_sha256"],
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "redis_pinged": False,
            "celery_started": False,
            "scheduler_started": False,
            "task_dispatched": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "error_message_safe": "",
        }
    ]
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="success",
        progress=1.0,
        current_step="worker_production_evidence_plan_completed_local_only",
        call_ledger=ledger,
        warning="worker_production_evidence_plan_completed_no_process_start",
    ) or task
    packet = {
        "packet_key": PRODUCTION_EVIDENCE_PLAN_PACKET_KEY,
        "schema_version": PRODUCTION_EVIDENCE_PLAN_SCHEMA_VERSION,
        "status": receipt["status"],
        "scope": receipt["scope"],
        "mode": receipt["mode"],
        "executed_at": planned_at,
        "task_id": task.get("task_id"),
        "task_status": task.get("status"),
        "task_type": task.get("task_type"),
        "output_packet_key": PRODUCTION_EVIDENCE_PLAN_PACKET_KEY,
        "worker_production_evidence_plan_receipt": receipt,
        "worker_production_evidence_plan_rows": rows,
        "evidence_plan_ready": receipt["evidence_plan_ready"],
        "ready_for_manual_runtime_qa": receipt["ready_for_manual_runtime_qa"],
        "scope_ticket_sha256": receipt["scope_ticket_sha256"],
        "production_worker_complete": False,
        "activation_ready": False,
        "starts_celery_worker": False,
        "pings_redis": False,
        "starts_scheduler": False,
        "task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": ledger,
        "warnings": [
            "这是显式 POST 的本地 Worker production evidence plan，只生成后续 runtime QA 的安全 scope ticket。",
            "它不启动 Celery、不 ping Redis、不启动 scheduler、不派发任务、不调用 Tushare/DeepSeek/GitHub、不执行真实交易，也不代表 production worker 完成。",
        ],
    }
    packet = _json_safe(packet)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PRODUCTION_EVIDENCE_PLAN_PACKET_KEY, packet)
    except Exception:
        packet.setdefault("warnings", []).append("worker_production_evidence_plan_packet_persist_failed_safe")
    return packet


def run_worker_runtime_qa_execution_request(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_worker_runtime_qa_execution_request",
        output_packet_key=RUNTIME_QA_EXECUTION_REQUEST_PACKET_KEY,
        payload=payload,
        current_step="worker_runtime_qa_execution_request_queued_no_process_start",
        warnings=[
            "Worker runtime QA execution request 只生成本地请求 ticket；不会启动 Celery、ping Redis、启动 scheduler、派发任务或调用 provider/model/probe。"
        ],
    )
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="running",
        progress=0.5,
        current_step="worker_runtime_qa_execution_request_reading_local_recipe",
    ) or task
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    runtime_packet = read_worker_runtime_cache()
    production_evidence_plan = (
        runtime_packet.get("worker_production_evidence_plan_receipt")
        if isinstance(runtime_packet.get("worker_production_evidence_plan_receipt"), dict)
        else {}
    )
    runtime_qa_execution_recipe = (
        runtime_packet.get("worker_runtime_qa_execution_recipe")
        if isinstance(runtime_packet.get("worker_runtime_qa_execution_recipe"), dict)
        else {}
    )
    requested_at = _now_iso()
    receipt = _worker_runtime_qa_execution_request_receipt(
        production_evidence_plan=production_evidence_plan,
        runtime_qa_execution_recipe=runtime_qa_execution_recipe,
        explicit_request=True,
        task_id=str(task.get("task_id") or ""),
        requested_at=requested_at,
        payload_safe=payload_safe,
    )
    rows = receipt.get("rows") if isinstance(receipt.get("rows"), list) else []
    ledger = [
        {
            "api": "local_worker_runtime_qa_execution_request",
            "source": "worker_production_evidence_plan_receipt + worker_runtime_qa_execution_recipe",
            "row_count": len(rows),
            "task_id": task.get("task_id"),
            "local_fetched_at": requested_at,
            "call_status": receipt["status"],
            "request_params_safe": {
                "requested_from": receipt["request_params_safe"]["requested_from"],
                "operator_approved": receipt["request_params_safe"]["operator_approved"],
                "evidence_plan_scope_hash_short": receipt["requested_evidence_plan_scope_hash_short"],
                "runtime_qa_scope_hash_short": receipt["requested_runtime_qa_scope_hash_short"],
                "external_sources_allowed": False,
                "starts_celery_worker": False,
                "pings_redis": False,
                "starts_scheduler": False,
                "task_dispatched": False,
            },
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "redis_pinged": False,
            "celery_started": False,
            "scheduler_started": False,
            "task_dispatched": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "error_message_safe": "",
        }
    ]
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="success",
        progress=1.0,
        current_step=receipt["status"],
        call_ledger=ledger,
        warning="worker_runtime_qa_execution_request_recorded_no_process_start",
    ) or task
    packet = {
        "packet_key": RUNTIME_QA_EXECUTION_REQUEST_PACKET_KEY,
        "schema_version": RUNTIME_QA_EXECUTION_REQUEST_SCHEMA_VERSION,
        "status": receipt["status"],
        "scope": receipt["scope"],
        "mode": receipt["mode"],
        "executed_at": requested_at,
        "task_id": task.get("task_id"),
        "task_status": task.get("status"),
        "task_type": task.get("task_type"),
        "output_packet_key": RUNTIME_QA_EXECUTION_REQUEST_PACKET_KEY,
        "worker_runtime_qa_execution_request_receipt": receipt,
        "worker_runtime_qa_execution_request_rows": rows,
        "local_execution_request_ready": receipt["local_execution_request_ready"],
        "ready_for_manual_runtime_qa_task_submission": receipt["ready_for_manual_runtime_qa_task_submission"],
        "runtime_qa_scope_hash": receipt["runtime_qa_scope_hash"],
        "production_evidence_plan_scope_hash": receipt["production_evidence_plan_scope_hash"],
        "runtime_qa_task_created": False,
        "runtime_qa_task_executed": False,
        "runtime_qa_execution_implemented": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": ledger,
        "warnings": [
            "这是显式 POST 的本地 Worker runtime QA execution request，只绑定后续 runtime QA 的安全 scope。",
            "它不启动 Celery、不 ping Redis、不启动 scheduler、不派发任务、不调用 Tushare/DeepSeek/GitHub、不执行真实交易，也不代表 production worker 完成。",
        ],
    }
    packet = _json_safe(packet)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(RUNTIME_QA_EXECUTION_REQUEST_PACKET_KEY, packet)
    except Exception:
        packet.setdefault("warnings", []).append("worker_runtime_qa_execution_request_packet_persist_failed_safe")
    return packet


def run_worker_runtime_qa_dry_run(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_worker_runtime_qa_dry_run",
        output_packet_key=RUNTIME_QA_DRY_RUN_PACKET_KEY,
        payload=payload,
        current_step="worker_runtime_qa_dry_run_queued_no_process_start_no_dispatch",
        warnings=[
            "Worker runtime QA dry-run 只生成本地 dry-run receipt；不会启动 Celery、ping Redis、启动 scheduler、派发任务或调用 provider/model/probe。"
        ],
    )
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="running",
        progress=0.5,
        current_step="worker_runtime_qa_dry_run_reading_local_request_and_recipe",
    ) or task
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    runtime_packet = read_worker_runtime_cache()
    runtime_qa_execution_request = (
        runtime_packet.get("worker_runtime_qa_execution_request_receipt")
        if isinstance(runtime_packet.get("worker_runtime_qa_execution_request_receipt"), dict)
        else {}
    )
    runtime_qa_execution_recipe = (
        runtime_packet.get("worker_runtime_qa_execution_recipe")
        if isinstance(runtime_packet.get("worker_runtime_qa_execution_recipe"), dict)
        else {}
    )
    requested_at = _now_iso()
    receipt = _worker_runtime_qa_dry_run_receipt(
        runtime_qa_execution_request=runtime_qa_execution_request,
        runtime_qa_execution_recipe=runtime_qa_execution_recipe,
        explicit_request=True,
        task_id=str(task.get("task_id") or ""),
        requested_at=requested_at,
        payload_safe=payload_safe,
    )
    rows = receipt.get("rows") if isinstance(receipt.get("rows"), list) else []
    phase_rows = receipt.get("phase_rows") if isinstance(receipt.get("phase_rows"), list) else []
    ledger = [
        {
            "api": "local_worker_runtime_qa_dry_run",
            "source": "worker_runtime_qa_execution_request_receipt + worker_runtime_qa_execution_recipe",
            "row_count": len(rows),
            "phase_row_count": len(phase_rows),
            "task_id": task.get("task_id"),
            "local_fetched_at": requested_at,
            "call_status": receipt["status"],
            "request_params_safe": {
                "requested_from": receipt["request_params_safe"]["requested_from"],
                "operator_approved": receipt["request_params_safe"]["operator_approved"],
                "request_task_id": receipt["request_params_safe"]["request_task_id"],
                "evidence_plan_scope_hash_short": receipt["requested_evidence_plan_scope_hash_short"],
                "runtime_qa_scope_hash_short": receipt["requested_runtime_qa_scope_hash_short"],
                "external_sources_allowed": False,
                "starts_celery_worker": False,
                "pings_redis": False,
                "starts_scheduler": False,
                "task_dispatched": False,
            },
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "redis_pinged": False,
            "celery_started": False,
            "scheduler_started": False,
            "task_dispatched": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "error_message_safe": "",
        }
    ]
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="success",
        progress=1.0,
        current_step=receipt["status"],
        call_ledger=ledger,
        warning="worker_runtime_qa_dry_run_recorded_no_process_start_no_dispatch",
    ) or task
    packet = {
        "packet_key": RUNTIME_QA_DRY_RUN_PACKET_KEY,
        "schema_version": RUNTIME_QA_DRY_RUN_SCHEMA_VERSION,
        "status": receipt["status"],
        "scope": receipt["scope"],
        "mode": receipt["mode"],
        "executed_at": requested_at,
        "task_id": task.get("task_id"),
        "task_status": task.get("status"),
        "task_type": task.get("task_type"),
        "output_packet_key": RUNTIME_QA_DRY_RUN_PACKET_KEY,
        "worker_runtime_qa_dry_run_receipt": receipt,
        "worker_runtime_qa_dry_run_rows": rows,
        "worker_runtime_qa_dry_run_phase_rows": phase_rows,
        "local_dry_run_ready": receipt["local_dry_run_ready"],
        "ready_for_separate_runtime_qa_execution": receipt["ready_for_separate_runtime_qa_execution"],
        "runtime_qa_scope_hash": receipt["runtime_qa_scope_hash"],
        "production_evidence_plan_scope_hash": receipt["production_evidence_plan_scope_hash"],
        "runtime_qa_task_created": False,
        "runtime_qa_task_executed": False,
        "runtime_qa_execution_implemented": False,
        "production_worker_complete": False,
        "activation_ready": False,
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": ledger,
        "warnings": [
            "这是显式 POST 的本地 Worker runtime QA dry-run，只审查 request ticket 与 runtime recipe。",
            "它不创建或执行 runtime QA task，不启动 Celery、不 ping Redis、不启动 scheduler、不派发任务、不调用 Tushare/DeepSeek/GitHub、不执行真实交易，也不代表 production worker 完成。",
        ],
    }
    packet = _json_safe(packet)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(RUNTIME_QA_DRY_RUN_PACKET_KEY, packet)
    except Exception:
        packet.setdefault("warnings", []).append("worker_runtime_qa_dry_run_packet_persist_failed_safe")
    return packet


def run_worker_runtime_qa_execution(payload: Any = None) -> dict[str, Any]:
    if isinstance(payload, dict) and str(payload.get("runtime_mode") or "") == "v04_local_batch":
        return _run_worker_v04_local_batch_runtime(payload)
    task = task_service.create_task_record(
        "run_worker_runtime_qa_execution",
        output_packet_key=RUNTIME_QA_EXECUTION_PACKET_KEY,
        payload=payload,
        current_step="worker_runtime_qa_execution_queued_local_fallback_no_process_start",
        warnings=[
            "Worker runtime QA execution 只执行本地 fallback round-trip 和 append-only evidence；不会启动 Celery、ping Redis、启动 scheduler、派发 provider/model/probe 任务。"
        ],
    )
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="running",
        progress=0.5,
        current_step="worker_runtime_qa_execution_running_local_fallback_round_trip",
    ) or task
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    runtime_packet = read_worker_runtime_cache()
    runtime_qa_dry_run = (
        runtime_packet.get("worker_runtime_qa_dry_run_receipt")
        if isinstance(runtime_packet.get("worker_runtime_qa_dry_run_receipt"), dict)
        else {}
    )
    runtime_qa_execution_recipe = (
        runtime_packet.get("worker_runtime_qa_execution_recipe")
        if isinstance(runtime_packet.get("worker_runtime_qa_execution_recipe"), dict)
        else {}
    )
    executed_at = _now_iso()
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="success",
        progress=1.0,
        current_step="worker_runtime_qa_execution_local_fallback_round_trip_recorded",
        call_ledger=[
            {
                "api": "local_worker_runtime_qa_execution_pre_receipt",
                "source": "local_task_store",
                "row_count": 1,
                "task_id": task.get("task_id"),
                "local_fetched_at": executed_at,
                "call_status": "local_fallback_round_trip_recorded",
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
            }
        ],
        warning="worker_runtime_qa_execution_local_fallback_round_trip_no_external_call",
    ) or task
    readback = task_service.read_task_status(str(task.get("task_id") or ""))
    cross_process_probe = _safe_cross_process_task_control_probe(task)
    append_event = {
        "schema_version": "worker_runtime_qa_append_only_event.v1",
        "event_type": "worker_runtime_qa_local_fallback_round_trip",
        "task_id": task.get("task_id"),
        "task_type": task.get("task_type"),
        "task_status": task.get("status"),
        "runtime_qa_scope_hash_short": str(runtime_qa_dry_run.get("runtime_qa_scope_hash_short") or ""),
        "production_evidence_plan_scope_hash_short": str(
            runtime_qa_dry_run.get("production_evidence_plan_scope_hash_short") or ""
        ),
        "local_fallback_round_trip_verified": isinstance(readback, dict) and readback.get("status") == "success",
        "storage_source": readback.get("storage_source") if isinstance(readback, dict) else "",
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "redis_pinged": False,
        "celery_started": False,
        "scheduler_started": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    try:
        append_result = _append_worker_runtime_qa_event(append_event)
    except Exception:
        append_result = {
            "schema_version": "worker_runtime_qa_append_only_event_result.v1",
            "status": "append_only_worker_log_event_failed_safe",
            "append_only_write_done": False,
            "readback_event_hash_matches": False,
            "contains_secret": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    receipt = _worker_runtime_qa_execution_receipt(
        runtime_qa_dry_run=runtime_qa_dry_run,
        runtime_qa_execution_recipe=runtime_qa_execution_recipe,
        explicit_execution=True,
        task_id=str(task.get("task_id") or ""),
        executed_at=executed_at,
        payload_safe=payload_safe,
        runtime_task=task,
        readback=readback if isinstance(readback, dict) else {},
        append_only_log=append_result,
        cross_process_probe=cross_process_probe,
    )
    rows = receipt.get("rows") if isinstance(receipt.get("rows"), list) else []
    phase_rows = receipt.get("phase_rows") if isinstance(receipt.get("phase_rows"), list) else []
    ledger = [
        {
            "api": "local_worker_runtime_qa_execution",
            "source": "worker_runtime_qa_dry_run + local_task_store + cross_process_probe + append_only_jsonl_event",
            "row_count": len(rows),
            "phase_row_count": len(phase_rows),
            "task_id": task.get("task_id"),
            "local_fetched_at": executed_at,
            "call_status": receipt["status"],
            "request_params_safe": {
                "requested_from": receipt["request_params_safe"]["requested_from"],
                "operator_approved": receipt["request_params_safe"]["operator_approved"],
                "dry_run_task_id": receipt["request_params_safe"]["dry_run_task_id"],
                "evidence_plan_scope_hash_short": receipt["request_params_safe"]["evidence_plan_scope_hash_short"],
                "runtime_qa_scope_hash_short": receipt["request_params_safe"]["runtime_qa_scope_hash_short"],
                "external_sources_allowed": False,
                "starts_celery_worker": False,
                "pings_redis": False,
                "starts_scheduler": False,
                "provider_model_task_dispatched": False,
            },
            "event_sha256": append_result.get("event_sha256") or "",
            "cross_process_probe_status": cross_process_probe.get("status") or "missing",
            "cross_process_probe_returncode": cross_process_probe.get("process_returncode"),
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "redis_pinged": False,
            "celery_started": False,
            "scheduler_started": False,
            "task_dispatched": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "error_message_safe": "",
        }
    ]
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="success",
        progress=1.0,
        current_step=receipt["status"],
        call_ledger=ledger,
        warning="worker_runtime_qa_execution_recorded_local_fallback_no_process_start",
    ) or task
    packet = {
        "packet_key": RUNTIME_QA_EXECUTION_PACKET_KEY,
        "schema_version": RUNTIME_QA_EXECUTION_SCHEMA_VERSION,
        "status": receipt["status"],
        "scope": receipt["scope"],
        "mode": receipt["mode"],
        "executed_at": executed_at,
        "task_id": task.get("task_id"),
        "task_status": task.get("status"),
        "task_type": task.get("task_type"),
        "output_packet_key": RUNTIME_QA_EXECUTION_PACKET_KEY,
        "worker_runtime_qa_execution_receipt": receipt,
        "worker_runtime_qa_execution_rows": rows,
        "worker_runtime_qa_execution_phase_rows": phase_rows,
        "local_runtime_qa_execution_done": receipt["local_runtime_qa_execution_done"],
        "runtime_qa_done": receipt["runtime_qa_done"],
        "runtime_qa_scope_hash": receipt["runtime_qa_scope_hash"],
        "production_evidence_plan_scope_hash": receipt["production_evidence_plan_scope_hash"],
        "append_only_worker_log_verified": receipt["append_only_worker_log_verified"],
        "task_log_persistence_verified": receipt["task_log_persistence_verified"],
        "local_fallback_round_trip_verified": receipt["local_fallback_round_trip_verified"],
        "local_task_control_metadata_verified": receipt["local_task_control_metadata_verified"],
        "cross_process_task_control_verified": receipt["cross_process_task_control_verified"],
        "cross_process_task_control_probe": cross_process_probe,
        "production_worker_complete": False,
        "activation_ready": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": ledger,
        "warnings": [
            "这是显式 POST 的本地 Worker runtime QA execution，只证明 local fallback round-trip、local Python process task-control readback 与 append-only event。",
            "它不启动 Celery、不 ping Redis、不启动 scheduler、不调用 Tushare/DeepSeek/GitHub、不执行真实交易，也不代表 production worker 完成。",
        ],
    }
    packet = _json_safe(packet)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(RUNTIME_QA_EXECUTION_PACKET_KEY, packet)
    except Exception:
        packet.setdefault("warnings", []).append("worker_runtime_qa_execution_packet_persist_failed_safe")
    return packet


def _worker_production_promotion_review_row(
    criterion: str,
    status: str,
    evidence: str,
    next_action: str,
    *,
    passed: bool,
    production_blocker: bool,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker and not passed),
        "worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "evidence": evidence,
        "next_action": next_action,
    }


def _worker_production_promotion_review_receipt(
    *,
    runtime_durable_evidence_recipe: dict[str, Any],
    runtime_qa_execution: dict[str, Any],
    payload_safe: dict[str, Any],
    task_id: str,
    reviewed_at: str,
) -> dict[str, Any]:
    approved = payload_safe.get("operator_approved") is True or payload_safe.get("approved") is True
    runtime_qa_visible = (
        runtime_qa_execution.get("schema_version") == RUNTIME_QA_EXECUTION_SCHEMA_VERSION
        and runtime_qa_execution.get("local_runtime_qa_execution_done") is True
        and runtime_qa_execution.get("local_fallback_round_trip_verified") is True
        and runtime_qa_execution.get("production_worker_complete") is False
        and runtime_qa_execution.get("external_calls_triggered") is False
    )
    durable_ready = runtime_durable_evidence_recipe.get("local_recipe_ready") is True
    durable_missing = [
        str(item)
        for item in runtime_durable_evidence_recipe.get("missing_durable_evidence") or []
        if item != "production_worker_promotion_review_required"
    ]
    celery_ready = "celery_process_evidence_required" not in durable_missing
    redis_ready = "redis_broker_reachability_evidence_required" not in durable_missing
    queue_ready = "queue_round_trip_evidence_required" not in durable_missing
    local_ready = bool(approved and durable_ready and runtime_qa_visible)
    rows = [
        _worker_production_promotion_review_row(
            "explicit_production_promotion_review_task",
            "passed_explicit_post" if approved else "blocked_operator_approval_required",
            f"operator_approved={approved}; task_id={task_id}",
            "Run this review only from an explicit POST after local runtime QA evidence is visible.",
            passed=approved,
            production_blocker=True,
        ),
        _worker_production_promotion_review_row(
            "runtime_durable_recipe_visible",
            "passed_durable_recipe_visible" if durable_ready else "blocked_missing_durable_recipe",
            f"durable_status={runtime_durable_evidence_recipe.get('status')}; missing={runtime_durable_evidence_recipe.get('missing_durable_evidence')}",
            "Keep durable evidence rows visible before any promotion decision.",
            passed=durable_ready,
            production_blocker=True,
        ),
        _worker_production_promotion_review_row(
            "runtime_qa_execution_visible",
            "passed_local_runtime_qa_visible" if runtime_qa_visible else "blocked_missing_runtime_qa_execution",
            f"runtime_status={runtime_qa_execution.get('status')}",
            "Require button-gated local runtime QA execution before promotion review.",
            passed=runtime_qa_visible,
            production_blocker=True,
        ),
        _worker_production_promotion_review_row(
            "celery_process_evidence_required",
            "passed" if celery_ready else "blocked_celery_process_evidence_missing",
            "Production worker still needs live Celery process identity and queue registration evidence.",
            "Collect Celery process evidence in a separately approved runtime path.",
            passed=celery_ready,
            production_blocker=True,
        ),
        _worker_production_promotion_review_row(
            "redis_broker_reachability_required",
            "passed" if redis_ready else "blocked_redis_broker_evidence_missing",
            "Production worker still needs redacted Redis broker reachability evidence.",
            "Collect Redis broker evidence without exposing URL or credentials.",
            passed=redis_ready,
            production_blocker=True,
        ),
        _worker_production_promotion_review_row(
            "live_queue_round_trip_required",
            "passed" if queue_ready else "blocked_live_queue_round_trip_missing",
            "Production worker still needs live queue binding and synthetic round-trip evidence.",
            "Prove queue round-trip after Celery/Redis are available.",
            passed=queue_ready,
            production_blocker=True,
        ),
        _worker_production_promotion_review_row(
            "no_process_provider_trade_secret_boundary",
            "passed_no_side_effects",
            "Promotion review starts no worker, pings no Redis, dispatches no task, calls no provider/model/GitHub, trades nothing, mutates no action, and exposes no secret.",
            "Preserve this boundary for every later production promotion attempt.",
            passed=True,
            production_blocker=False,
        ),
    ]
    production_blockers = [row for row in rows if row.get("production_blocker")]
    scope_input = {
        "route": "POST /api/worker/production-promotion-review",
        "task_type": "run_worker_production_promotion_review",
        "runtime_qa_execution_task_id": runtime_qa_execution.get("execution_task_id") or runtime_qa_execution.get("task_id"),
        "runtime_durable_status": runtime_durable_evidence_recipe.get("status"),
        "missing_durable_evidence": runtime_durable_evidence_recipe.get("missing_durable_evidence") or [],
        "operator_approved": approved,
    }
    scope_hash = _json_sha256(scope_input)
    return {
        "packet_key": PRODUCTION_PROMOTION_REVIEW_PACKET_KEY,
        "schema_version": PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION,
        "status": (
            "worker_production_promotion_review_ready_production_blocked"
            if local_ready
            else "worker_production_promotion_review_blocked_local_evidence"
        ),
        "scope": "button_gated_worker_production_promotion_review_no_process_start",
        "ltg": "LTG-06/LTG-11",
        "mode": "button_gated_local_worker_production_promotion_review",
        "explicit_production_promotion_review_done": True,
        "review_task_id": task_id,
        "reviewed_at": reviewed_at,
        "operator_approved": approved,
        "local_promotion_review_ready": local_ready,
        "ready_to_mark_production_worker_complete": False,
        "production_worker_complete": False,
        "runtime_durable_recipe_visible": durable_ready,
        "runtime_qa_execution_visible": runtime_qa_visible,
        "runtime_qa_execution_task_id": runtime_qa_execution.get("execution_task_id") or runtime_qa_execution.get("task_id"),
        "runtime_qa_scope_hash": runtime_qa_execution.get("runtime_qa_scope_hash"),
        "runtime_qa_scope_hash_short": runtime_qa_execution.get("runtime_qa_scope_hash_short"),
        "promotion_review_scope_hash": scope_hash,
        "promotion_review_scope_hash_short": scope_hash[:12],
        "promotion_review_scope_hash_input_includes_secret": False,
        "missing_durable_evidence_after_review": durable_missing,
        "production_blocker_count": len(production_blockers),
        "local_blocker_count": 0 if local_ready else len([row for row in rows[:3] if not row.get("passed")]),
        "row_count": len(rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_worker_production_promotion_review",
                "source": "worker_runtime_durable_evidence_recipe + worker_runtime_qa_execution_receipt",
                "row_count": len(rows),
                "task_id": task_id,
                "local_fetched_at": reviewed_at,
                "call_status": (
                    "worker_production_promotion_review_ready_production_blocked"
                    if local_ready
                    else "worker_production_promotion_review_blocked_local_evidence"
                ),
                "external": False,
                "external_calls_triggered": False,
                "redis_pinged": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "not_allowed_next_steps": [
            "treat_production_promotion_review_as_celery_runtime_evidence",
            "start Celery from production promotion review",
            "ping Redis from production promotion review",
            "dispatch worker task from production promotion review",
            "autoschedule Tushare DeepSeek GitHub tasks",
            "mark_production_worker_complete_from_review",
        ],
        "worker_started": False,
        "celery_worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _missing_worker_production_promotion_review_packet(read_status: str = "packet_missing") -> dict[str, Any]:
    return {
        "packet_key": PRODUCTION_PROMOTION_REVIEW_PACKET_KEY,
        "schema_version": PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION,
        "status": "worker_production_promotion_review_missing",
        "scope": "button_gated_worker_production_promotion_review_no_process_start",
        "local_promotion_review_ready": False,
        "production_worker_complete": False,
        "ready_to_mark_production_worker_complete": False,
        "source_packet_read_status": read_status,
        "source_packet_present": False,
        "cache_get_initializes_meta_store": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": [],
        "call_ledger": [],
    }


def _read_worker_production_promotion_review_packet(
    runtime_durable_evidence_recipe: dict[str, Any],
    runtime_qa_execution: dict[str, Any],
) -> dict[str, Any]:
    packet, read_status = _read_worker_meta_packet_no_init(PRODUCTION_PROMOTION_REVIEW_PACKET_KEY)
    if not isinstance(packet, dict):
        return _missing_worker_production_promotion_review_packet(read_status)
    receipt = _json_safe(packet.get("worker_production_promotion_review_receipt") or packet)
    if receipt.get("schema_version") != PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION:
        return _missing_worker_production_promotion_review_packet("packet_invalid")
    rebuilt = _worker_production_promotion_review_receipt(
        runtime_durable_evidence_recipe=runtime_durable_evidence_recipe,
        runtime_qa_execution=runtime_qa_execution,
        payload_safe={"operator_approved": receipt.get("operator_approved") is True},
        task_id=str(receipt.get("review_task_id") or ""),
        reviewed_at=str(receipt.get("reviewed_at") or _now_iso()),
    )
    rebuilt["source_packet_read_status"] = read_status
    rebuilt["source_packet_present"] = read_status == "packet_present"
    rebuilt["cache_get_initializes_meta_store"] = False
    return rebuilt


def run_worker_production_promotion_review(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_worker_production_promotion_review",
        output_packet_key=PRODUCTION_PROMOTION_REVIEW_PACKET_KEY,
        payload=payload,
        current_step="worker_production_promotion_review_queued_no_process_start",
        warnings=[
            "Worker production promotion review 只审查本地 runtime QA 和 durable evidence；不会启动 Celery、ping Redis、启动 scheduler、派发任务或完成 production worker。"
        ],
    )
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="running",
        progress=0.5,
        current_step="worker_production_promotion_review_running_local_review",
    ) or task
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    runtime_packet = read_worker_runtime_cache()
    runtime_durable_evidence_recipe = (
        runtime_packet.get("worker_runtime_durable_evidence_recipe")
        if isinstance(runtime_packet.get("worker_runtime_durable_evidence_recipe"), dict)
        else {}
    )
    runtime_qa_execution = (
        runtime_packet.get("worker_runtime_qa_execution_receipt")
        if isinstance(runtime_packet.get("worker_runtime_qa_execution_receipt"), dict)
        else {}
    )
    reviewed_at = _now_iso()
    receipt = _worker_production_promotion_review_receipt(
        runtime_durable_evidence_recipe=runtime_durable_evidence_recipe,
        runtime_qa_execution=runtime_qa_execution,
        payload_safe=payload_safe,
        task_id=str(task.get("task_id") or ""),
        reviewed_at=reviewed_at,
    )
    rows = receipt.get("rows") if isinstance(receipt.get("rows"), list) else []
    ledger = [
        {
            "api": "local_worker_production_promotion_review",
            "source": "worker_runtime_durable_evidence_recipe + worker_runtime_qa_execution_receipt",
            "row_count": len(rows),
            "task_id": task.get("task_id"),
            "local_fetched_at": reviewed_at,
            "call_status": receipt["status"],
            "request_params_safe": {
                "requested_from": payload_safe.get("requested_from") or "",
                "operator_approved": receipt["operator_approved"],
                "runtime_qa_scope_hash_short": receipt.get("runtime_qa_scope_hash_short") or "",
                "promotion_review_scope_hash_short": receipt["promotion_review_scope_hash_short"],
                "external_sources_allowed": False,
                "starts_celery_worker": False,
                "pings_redis": False,
                "starts_scheduler": False,
                "task_dispatched": False,
                "provider_model_task_dispatched": False,
                "production_worker_complete": False,
            },
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "redis_pinged": False,
            "celery_started": False,
            "scheduler_started": False,
            "task_dispatched": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "error_message_safe": "",
        }
    ]
    task = task_service.update_task_status(
        str(task["task_id"]),
        status="success",
        progress=1.0,
        current_step=receipt["status"],
        call_ledger=ledger,
        warning="worker_production_promotion_review_recorded_no_process_start",
    ) or task
    packet = {
        "packet_key": PRODUCTION_PROMOTION_REVIEW_PACKET_KEY,
        "schema_version": PRODUCTION_PROMOTION_REVIEW_SCHEMA_VERSION,
        "status": receipt["status"],
        "scope": receipt["scope"],
        "mode": receipt["mode"],
        "reviewed_at": reviewed_at,
        "task_id": task.get("task_id"),
        "task_status": task.get("status"),
        "task_type": task.get("task_type"),
        "output_packet_key": PRODUCTION_PROMOTION_REVIEW_PACKET_KEY,
        "worker_production_promotion_review_receipt": receipt,
        "worker_production_promotion_review_rows": rows,
        "local_promotion_review_ready": receipt["local_promotion_review_ready"],
        "production_worker_complete": False,
        "worker_started": False,
        "celery_worker_started": False,
        "redis_pinged": False,
        "scheduler_started": False,
        "task_dispatched": False,
        "provider_model_task_dispatched": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": ledger,
        "warnings": [
            "这是显式 POST 的本地 Worker production promotion review；只审查 runtime QA 与 durable evidence。",
            "它不启动 Celery、不 ping Redis、不启动 scheduler、不派发任务、不调用 Tushare/DeepSeek/GitHub、不执行真实交易，也不代表 production worker 完成。",
        ],
    }
    packet = _json_safe(packet)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PRODUCTION_PROMOTION_REVIEW_PACKET_KEY, packet)
    except Exception:
        packet.setdefault("warnings", []).append("worker_production_promotion_review_packet_persist_failed_safe")
    return packet


def read_worker_runtime_cache() -> dict[str, Any]:
    celery_available = _module_available("celery")
    redis_available = _module_available("redis")
    apscheduler_available = _module_available("apscheduler")
    scheduled_refresh_enabled = os.getenv("COMMAND_CENTER_ENABLE_SCHEDULED_REFRESH") == "1"
    redis_config_source_labels = _redis_config_source_labels_present()
    redis_configured = bool(redis_config_source_labels)
    dependency_preflight = _worker_runtime_dependency_preflight(
        celery_available=celery_available,
        redis_available=redis_available,
        apscheduler_available=apscheduler_available,
        redis_configured=redis_configured,
        redis_config_source_labels=redis_config_source_labels,
    )
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
    production_readiness["worker_synthetic_healthcheck_source_packet_read_status"] = synthetic_healthcheck.get(
        "source_packet_read_status"
    )
    production_readiness["worker_synthetic_healthcheck_source_packet_present"] = synthetic_healthcheck.get(
        "source_packet_present"
    )
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
    activation_review_task_receipt = _read_worker_activation_review_packet(
        synthetic_healthcheck,
        activation_review_contract,
        production_activation_receipt,
    )
    activation_review_task_rows = activation_review_task_receipt.get("rows") or []
    production_readiness["worker_activation_review_task_receipt"] = activation_review_task_receipt
    production_readiness["worker_activation_review_task_rows"] = activation_review_task_rows
    production_readiness["worker_activation_review_source_packet_read_status"] = activation_review_task_receipt.get(
        "source_packet_read_status"
    )
    production_readiness["worker_activation_review_source_packet_present"] = activation_review_task_receipt.get(
        "source_packet_present"
    )
    production_evidence_plan_receipt = _read_worker_production_evidence_plan_packet(
        synthetic_healthcheck,
        activation_review_task_receipt,
        production_activation_receipt,
    )
    production_evidence_plan_rows = production_evidence_plan_receipt.get("rows") or []
    production_readiness["worker_production_evidence_plan_receipt"] = production_evidence_plan_receipt
    production_readiness["worker_production_evidence_plan_rows"] = production_evidence_plan_rows
    production_readiness["worker_production_evidence_plan_source_packet_read_status"] = production_evidence_plan_receipt.get(
        "source_packet_read_status"
    )
    production_readiness["worker_production_evidence_plan_source_packet_present"] = production_evidence_plan_receipt.get(
        "source_packet_present"
    )
    runtime_qa_execution_recipe = _worker_runtime_qa_execution_recipe(
        production_evidence_plan=production_evidence_plan_receipt,
        production_activation_receipt=production_activation_receipt,
        readiness_receipt=production_readiness_receipt,
        healthcheck_qa_contract=healthcheck_qa_contract,
        task_log_persistence_audit=task_log_persistence_audit,
        queue_routing_contract=queue_routing_contract,
    )
    production_readiness["worker_runtime_qa_execution_recipe"] = runtime_qa_execution_recipe
    production_readiness["worker_runtime_qa_execution_recipe_rows"] = runtime_qa_execution_recipe["rows"]
    runtime_qa_execution_request = _read_worker_runtime_qa_execution_request_packet(
        production_evidence_plan_receipt,
        runtime_qa_execution_recipe,
    )
    runtime_qa_execution_request_rows = runtime_qa_execution_request.get("rows") or []
    production_readiness["worker_runtime_qa_execution_request_receipt"] = runtime_qa_execution_request
    production_readiness["worker_runtime_qa_execution_request_rows"] = runtime_qa_execution_request_rows
    production_readiness["worker_runtime_qa_execution_request_source_packet_read_status"] = runtime_qa_execution_request.get(
        "source_packet_read_status"
    )
    production_readiness["worker_runtime_qa_execution_request_source_packet_present"] = runtime_qa_execution_request.get(
        "source_packet_present"
    )
    runtime_qa_dry_run = _read_worker_runtime_qa_dry_run_packet(
        runtime_qa_execution_request,
        runtime_qa_execution_recipe,
    )
    runtime_qa_dry_run_rows = runtime_qa_dry_run.get("rows") or []
    production_readiness["worker_runtime_qa_dry_run_receipt"] = runtime_qa_dry_run
    production_readiness["worker_runtime_qa_dry_run_rows"] = runtime_qa_dry_run_rows
    production_readiness["worker_runtime_qa_dry_run_phase_rows"] = runtime_qa_dry_run.get("phase_rows") or []
    production_readiness["worker_runtime_qa_dry_run_source_packet_read_status"] = runtime_qa_dry_run.get(
        "source_packet_read_status"
    )
    production_readiness["worker_runtime_qa_dry_run_source_packet_present"] = runtime_qa_dry_run.get(
        "source_packet_present"
    )
    runtime_qa_execution = _read_worker_runtime_qa_execution_packet(
        runtime_qa_dry_run,
        runtime_qa_execution_recipe,
    )
    runtime_qa_execution_rows = runtime_qa_execution.get("rows") or []
    production_readiness["worker_runtime_qa_execution_receipt"] = runtime_qa_execution
    production_readiness["worker_runtime_qa_execution_rows"] = runtime_qa_execution_rows
    production_readiness["worker_runtime_qa_execution_phase_rows"] = runtime_qa_execution.get("phase_rows") or []
    production_readiness["worker_runtime_qa_execution_source_packet_read_status"] = runtime_qa_execution.get(
        "source_packet_read_status"
    )
    production_readiness["worker_runtime_qa_execution_source_packet_present"] = runtime_qa_execution.get(
        "source_packet_present"
    )
    runtime_durable_evidence_recipe = _worker_runtime_durable_evidence_recipe(
        production_blocker_audit=production_blocker_audit,
        healthcheck_qa_contract=healthcheck_qa_contract,
        task_log_persistence_audit=task_log_persistence_audit,
        queue_routing_contract=queue_routing_contract,
        readiness_receipt=production_readiness_receipt,
        production_activation_receipt=production_activation_receipt,
        production_evidence_plan=production_evidence_plan_receipt,
        runtime_qa_execution_recipe=runtime_qa_execution_recipe,
        runtime_qa_execution_request=runtime_qa_execution_request,
        runtime_qa_dry_run=runtime_qa_dry_run,
        runtime_qa_execution=runtime_qa_execution,
    )
    production_promotion_review = _read_worker_production_promotion_review_packet(
        runtime_durable_evidence_recipe,
        runtime_qa_execution,
    )
    production_promotion_review_rows = production_promotion_review.get("rows") or []
    runtime_durable_evidence_recipe = _worker_runtime_durable_evidence_recipe(
        production_blocker_audit=production_blocker_audit,
        healthcheck_qa_contract=healthcheck_qa_contract,
        task_log_persistence_audit=task_log_persistence_audit,
        queue_routing_contract=queue_routing_contract,
        readiness_receipt=production_readiness_receipt,
        production_activation_receipt=production_activation_receipt,
        production_evidence_plan=production_evidence_plan_receipt,
        runtime_qa_execution_recipe=runtime_qa_execution_recipe,
        runtime_qa_execution_request=runtime_qa_execution_request,
        runtime_qa_dry_run=runtime_qa_dry_run,
        runtime_qa_execution=runtime_qa_execution,
        production_promotion_review=production_promotion_review,
    )
    production_readiness["worker_production_promotion_review_receipt"] = production_promotion_review
    production_readiness["worker_production_promotion_review_rows"] = production_promotion_review_rows
    production_readiness["worker_production_promotion_review_source_packet_read_status"] = production_promotion_review.get(
        "source_packet_read_status"
    )
    production_readiness["worker_production_promotion_review_source_packet_present"] = production_promotion_review.get(
        "source_packet_present"
    )
    production_readiness["worker_runtime_durable_evidence_recipe"] = runtime_durable_evidence_recipe
    production_readiness["worker_runtime_durable_evidence_rows"] = runtime_durable_evidence_recipe["rows"]
    worker_runtime_stage_scope_manifest = _worker_runtime_evidence_stage_scope_manifest(
        production_evidence_plan=production_evidence_plan_receipt,
        runtime_qa_execution=runtime_qa_execution,
        runtime_durable_evidence_recipe=runtime_durable_evidence_recipe,
    )
    production_readiness["worker_runtime_evidence_stage_scope_manifest"] = worker_runtime_stage_scope_manifest
    production_readiness["worker_runtime_evidence_stage_scope_rows"] = worker_runtime_stage_scope_manifest["rows"]
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
        "worker_synthetic_healthcheck_source_packet_read_status": synthetic_healthcheck.get("source_packet_read_status"),
        "worker_synthetic_healthcheck_source_packet_present": synthetic_healthcheck.get("source_packet_present"),
        "worker_activation_review_contract": activation_review_contract,
        "worker_activation_review_rows": activation_review_contract["rows"],
        "worker_production_readiness_receipt": production_readiness_receipt,
        "worker_production_readiness_receipt_rows": production_readiness_receipt["rows"],
        "worker_production_activation_receipt": production_activation_receipt,
        "worker_production_activation_rows": production_activation_receipt["rows"],
        "worker_activation_review_task_receipt": activation_review_task_receipt,
        "worker_activation_review_task_rows": activation_review_task_rows,
        "worker_activation_review_source_packet_read_status": activation_review_task_receipt.get(
            "source_packet_read_status"
        ),
        "worker_activation_review_source_packet_present": activation_review_task_receipt.get("source_packet_present"),
        "worker_production_evidence_plan_receipt": production_evidence_plan_receipt,
        "worker_production_evidence_plan_rows": production_evidence_plan_rows,
        "worker_production_evidence_plan_source_packet_read_status": production_evidence_plan_receipt.get(
            "source_packet_read_status"
        ),
        "worker_production_evidence_plan_source_packet_present": production_evidence_plan_receipt.get(
            "source_packet_present"
        ),
        "worker_runtime_qa_execution_recipe": runtime_qa_execution_recipe,
        "worker_runtime_qa_execution_recipe_rows": runtime_qa_execution_recipe["rows"],
        "worker_runtime_qa_execution_request_receipt": runtime_qa_execution_request,
        "worker_runtime_qa_execution_request_rows": runtime_qa_execution_request_rows,
        "worker_runtime_qa_execution_request_source_packet_read_status": runtime_qa_execution_request.get(
            "source_packet_read_status"
        ),
        "worker_runtime_qa_execution_request_source_packet_present": runtime_qa_execution_request.get(
            "source_packet_present"
        ),
        "worker_runtime_qa_dry_run_receipt": runtime_qa_dry_run,
        "worker_runtime_qa_dry_run_rows": runtime_qa_dry_run_rows,
        "worker_runtime_qa_dry_run_phase_rows": runtime_qa_dry_run.get("phase_rows") or [],
        "worker_runtime_qa_dry_run_source_packet_read_status": runtime_qa_dry_run.get(
            "source_packet_read_status"
        ),
        "worker_runtime_qa_dry_run_source_packet_present": runtime_qa_dry_run.get(
            "source_packet_present"
        ),
        "worker_runtime_qa_execution_receipt": runtime_qa_execution,
        "worker_runtime_qa_execution_rows": runtime_qa_execution_rows,
        "worker_runtime_qa_execution_phase_rows": runtime_qa_execution.get("phase_rows") or [],
        "worker_runtime_qa_execution_source_packet_read_status": runtime_qa_execution.get(
            "source_packet_read_status"
        ),
        "worker_runtime_qa_execution_source_packet_present": runtime_qa_execution.get(
            "source_packet_present"
        ),
        "worker_production_promotion_review_receipt": production_promotion_review,
        "worker_production_promotion_review_rows": production_promotion_review_rows,
        "worker_production_promotion_review_source_packet_read_status": production_promotion_review.get(
            "source_packet_read_status"
        ),
        "worker_production_promotion_review_source_packet_present": production_promotion_review.get(
            "source_packet_present"
        ),
        "worker_runtime_durable_evidence_recipe": runtime_durable_evidence_recipe,
        "worker_runtime_durable_evidence_rows": runtime_durable_evidence_recipe["rows"],
        "worker_runtime_evidence_stage_scope_manifest": worker_runtime_stage_scope_manifest,
        "worker_runtime_evidence_stage_scope_rows": worker_runtime_stage_scope_manifest["rows"],
        "worker_runtime_dependency_preflight": dependency_preflight,
        "worker_runtime_dependency_preflight_rows": dependency_preflight["rows"],
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
            "worker_activation_review_task_ready": 1 if activation_review_task_receipt.get("activation_review_ready") else 0,
            "worker_activation_review_task_local_blocker_count": activation_review_task_receipt.get("local_blocker_count", 0),
            "worker_activation_review_task_production_blocker_count": activation_review_task_receipt.get("production_blocker_count", 0),
            "worker_activation_review_task_row_count": activation_review_task_receipt.get("row_count", 0),
            "worker_production_evidence_plan_ready": 1 if production_evidence_plan_receipt.get("evidence_plan_ready") else 0,
            "worker_production_evidence_plan_local_blocker_count": production_evidence_plan_receipt.get("local_blocker_count", 0),
            "worker_production_evidence_plan_production_blocker_count": production_evidence_plan_receipt.get("production_blocker_count", 0),
            "worker_production_evidence_plan_row_count": production_evidence_plan_receipt.get("row_count", 0),
            "worker_runtime_qa_execution_recipe_ready": 1 if runtime_qa_execution_recipe.get("local_recipe_ready") else 0,
            "worker_runtime_qa_execution_recipe_phase_count": runtime_qa_execution_recipe.get("phase_count", 0),
            "worker_runtime_qa_execution_recipe_pending_phase_count": runtime_qa_execution_recipe.get("pending_phase_count", 0),
            "worker_runtime_qa_execution_request_ready": 1
            if runtime_qa_execution_request.get("local_execution_request_ready")
            else 0,
            "worker_runtime_qa_execution_request_row_count": runtime_qa_execution_request.get("row_count", 0),
            "worker_runtime_qa_dry_run_ready": 1 if runtime_qa_dry_run.get("local_dry_run_ready") else 0,
            "worker_runtime_qa_dry_run_row_count": runtime_qa_dry_run.get("row_count", 0),
            "worker_runtime_qa_dry_run_phase_row_count": runtime_qa_dry_run.get("phase_row_count", 0),
            "worker_runtime_qa_execution_ready": 1
            if runtime_qa_execution.get("local_runtime_qa_execution_done")
            else 0,
            "worker_runtime_qa_execution_row_count": runtime_qa_execution.get("row_count", 0),
            "worker_runtime_qa_execution_phase_row_count": runtime_qa_execution.get("phase_row_count", 0),
            "worker_production_promotion_review_ready": 1
            if production_promotion_review.get("local_promotion_review_ready")
            else 0,
            "worker_production_promotion_review_row_count": production_promotion_review.get("row_count", 0),
            "worker_production_promotion_review_production_blocker_count": production_promotion_review.get(
                "production_blocker_count",
                0,
            ),
            "worker_runtime_durable_evidence_recipe_ready": 1 if runtime_durable_evidence_recipe.get("local_recipe_ready") else 0,
            "worker_runtime_durable_evidence_row_count": runtime_durable_evidence_recipe.get("row_count", 0),
            "worker_runtime_durable_evidence_production_blocker_count": runtime_durable_evidence_recipe.get(
                "production_blocker_count",
                0,
            ),
            "worker_runtime_evidence_stage_scope_count": worker_runtime_stage_scope_manifest.get("row_count", 0),
            "worker_runtime_evidence_stage_scope_direct_evidence_count": worker_runtime_stage_scope_manifest.get(
                "direct_evidence_stage_count",
                0,
            ),
            "worker_runtime_evidence_stage_scope_pending_count": worker_runtime_stage_scope_manifest.get(
                "pending_stage_count",
                0,
            ),
            "worker_runtime_dependency_preflight_blocker_count": dependency_preflight["blocker_count"],
            "worker_runtime_dependency_preflight_row_count": dependency_preflight["row_count"],
            "worker_runtime_dependency_preflight_ready": 1 if dependency_preflight["local_preflight_ready"] else 0,
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
            "worker_activation_review_task_is_button_gated": True,
            "worker_activation_review_task_is_not_process_start": True,
            "worker_activation_review_task_is_not_production_completion": True,
            "worker_production_evidence_plan_is_button_gated": True,
            "worker_production_evidence_plan_is_not_process_start": True,
            "worker_production_evidence_plan_is_not_production_completion": True,
            "worker_runtime_qa_execution_recipe_is_local": True,
            "worker_runtime_qa_execution_recipe_is_not_process_start": True,
            "worker_runtime_qa_execution_recipe_is_not_production_completion": True,
            "worker_runtime_qa_execution_request_is_button_gated": True,
            "worker_runtime_qa_execution_request_is_not_process_start": True,
            "worker_runtime_qa_execution_request_is_not_production_completion": True,
            "worker_runtime_qa_dry_run_is_button_gated": True,
            "worker_runtime_qa_dry_run_is_not_process_start": True,
            "worker_runtime_qa_dry_run_is_not_production_completion": True,
            "worker_runtime_qa_execution_is_button_gated": True,
            "worker_runtime_qa_execution_is_local_fallback_only": True,
            "worker_runtime_qa_execution_is_not_process_start": True,
            "worker_runtime_qa_execution_is_not_production_completion": True,
            "worker_production_promotion_review_is_button_gated": True,
            "worker_production_promotion_review_is_local": True,
            "worker_production_promotion_review_is_not_process_start": True,
            "worker_production_promotion_review_is_not_production_completion": True,
            "worker_runtime_durable_evidence_recipe_is_local": True,
            "worker_runtime_durable_evidence_recipe_is_not_process_start": True,
            "worker_runtime_durable_evidence_recipe_is_not_production_completion": True,
            "worker_runtime_evidence_stage_scope_manifest_is_local": True,
            "worker_runtime_evidence_stage_scope_manifest_is_not_process_start": True,
            "worker_runtime_evidence_stage_scope_manifest_is_not_production_completion": True,
            "worker_runtime_dependency_preflight_is_local": True,
            "worker_runtime_dependency_preflight_does_not_start_process": True,
            "worker_runtime_dependency_preflight_does_not_ping_redis": True,
            "worker_runtime_dependency_preflight_is_not_production_completion": True,
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
        + production_activation_receipt["call_ledger"]
        + runtime_qa_execution_recipe["call_ledger"]
        + runtime_qa_execution_request["call_ledger"]
        + runtime_qa_dry_run["call_ledger"]
        + runtime_qa_execution["call_ledger"]
        + production_promotion_review["call_ledger"]
        + runtime_durable_evidence_recipe["call_ledger"],
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
            "Worker activation review task 只审查本地 synthetic healthcheck 和 activation receipt；不会启动 Celery、ping Redis、启动 scheduler 或完成 production worker。",
            "Worker production evidence plan 只生成后续 runtime QA 的本地 scope ticket；不会启动 Celery、ping Redis、启动 scheduler、派发任务或完成 production worker。",
            "Worker runtime QA execution request 只绑定后续手动 runtime QA 的 scope；不会启动 Celery、ping Redis、启动 scheduler 或派发任务。",
            "Worker runtime QA dry-run 只本地审查 request ticket 与 recipe；不会创建/执行 runtime QA task 或启动任何 worker 进程。",
            "Worker runtime QA execution 只执行本地 fallback round-trip 和 append-only event；不会启动 Celery/Redis 或证明 production worker。",
            "Worker production promotion review 只本地审查 runtime QA 与 durable evidence；不会启动 Celery/Redis 或证明 production worker。",
            "Worker runtime 只做诊断说明，不执行真实交易，不修改 strategy action。",
        ],
    }
    return _json_safe(packet)
