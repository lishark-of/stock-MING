from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Mapping

from storage import duckdb_store, parquet_store
from storage.sqlite_meta import SQLiteMetaStore

from . import task_service

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARQUET_ROOT = PROJECT_ROOT / ".stock_ming_3" / "parquet"
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
V04_ACCEPTANCE_ROOT = PROJECT_ROOT / ".stock_ming_3" / "v04_acceptance"
ARTIFACT_CLEANUP_DRY_RUN_PACKET_KEY = "command_center_3_storage_artifact_cleanup_dry_run_packet"
SCHEMA_VALIDATION_DRY_RUN_PACKET_KEY = "command_center_3_storage_schema_validation_dry_run_packet"
SCHEMA_VALIDATION_ACCEPTANCE_PACKET_KEY = "command_center_3_storage_schema_validation_acceptance_packet"
SCHEMA_MIGRATION_EXECUTION_PACKET_KEY = "command_center_3_storage_schema_migration_execution_packet"
BACKTEST_RESULTS_SCHEMA_SEED_PACKET_KEY = "command_center_3_storage_backtest_results_schema_seed_packet"
PARTITION_MIGRATION_DRY_RUN_PACKET_KEY = "command_center_3_storage_partition_migration_dry_run_packet"
PARTITION_MIGRATION_EXECUTION_PACKET_KEY = "command_center_3_storage_partition_migration_execution_packet"
COMPACTION_EXECUTION_PACKET_KEY = "command_center_3_storage_compaction_execution_packet"
COMPACTION_DRY_RUN_PACKET_KEY = "command_center_3_storage_compaction_dry_run_packet"
CACHE_TTL_DRY_RUN_PACKET_KEY = "command_center_3_storage_cache_ttl_dry_run_packet"
DATASET_VERSION_MANIFEST_DRY_RUN_PACKET_KEY = "command_center_3_storage_dataset_version_manifest_dry_run_packet"
DATASET_VERSION_MANIFEST_REVIEW_PACKET_KEY = "command_center_3_storage_dataset_version_manifest_review_packet"
DATASET_VERSION_MANIFEST_WRITE_PACKET_KEY = "command_center_3_storage_dataset_version_manifest_write_packet"
DATASET_VERSION_MANIFEST_VALIDATE_PACKET_KEY = "command_center_3_storage_dataset_version_manifest_validate_packet"
STORAGE_PHYSICAL_EXECUTION_REQUEST_PACKET_KEY = "command_center_3_storage_physical_execution_request_packet"
STORAGE_PHYSICAL_EXECUTION_PHASE_A_PACKET_KEY = "command_center_3_storage_physical_execution_phase_a_packet"
STORAGE_CURRENT_RESULT_ATOMIC_PROMOTION_PACKET_KEY = (
    "command_center_3_storage_current_result_atomic_promotion_packet"
)
STORAGE_CURRENT_RESULT_RETENTION_CLEANUP_PACKET_KEY = (
    "command_center_3_storage_current_result_retention_cleanup_packet"
)
STORAGE_PRODUCTION_PROMOTION_REVIEW_PACKET_KEY = "command_center_3_storage_production_promotion_review_packet"
DUCKDB_READ_VALIDATION_PACKET_KEY = "command_center_3_storage_duckdb_read_validation_packet"
STORAGE_PRODUCTION_BLOCKER_SCHEMA_VERSION = "command_center_3_storage_production_blocker_audit.v1"
STORAGE_PHYSICAL_DURABLE_EVIDENCE_SCHEMA_VERSION = (
    "command_center_3_storage_physical_durable_evidence_recipe.v1"
)
ARTIFACT_CLEANUP_REVIEW_SCHEMA_VERSION = "command_center_3_storage_artifact_cleanup_review_contract.v1"
SUPPORTED_PARQUET_DATASETS = {
    "factor_values": "factor_values",
    "factor-values": "factor_values",
    "daily": "daily",
    "daily_basic": "daily_basic",
    "daily-basic": "daily_basic",
    "moneyflow": "moneyflow",
    "trade_cal": "trade_cal",
    "trade-cal": "trade_cal",
    "backtest_results": "backtest_results",
    "backtest-results": "backtest_results",
}
CANONICAL_PARQUET_DATASETS = ["factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"]
DUCKDB_QUERY_DEFAULT_LIMIT = 100
DUCKDB_QUERY_MAX_LIMIT = 10000
DUCKDB_QUERY_FILTER_PARAMS = ["limit", "cursor", "ts_code", "trade_date", "start_date", "end_date"]
CURRENT_RESULT_TTL_SECONDS = 24 * 60 * 60
CURRENT_RESULT_MAX_VERSIONS = 10
DATASET_TTL_SECONDS = {
    "factor_values": 6 * 60 * 60,
    "daily": 24 * 60 * 60,
    "daily_basic": 24 * 60 * 60,
    "moneyflow": 24 * 60 * 60,
    "trade_cal": 14 * 24 * 60 * 60,
    "backtest_results": 30 * 24 * 60 * 60,
}
DATASET_COMPACTION_SIZE_THRESHOLD_BYTES = 128 * 1024 * 1024
DATASET_VERSION_MANIFEST_NAME = "_dataset_versions.json"
STORAGE_PHYSICAL_EXECUTION_PHASES = [
    "physical_schema_validation_acceptance",
    "dataset_version_manifest_write_validate",
    "schema_migration_execution_plan",
    "partition_migration_execution_plan",
    "physical_compaction_execution_plan",
    "cache_ttl_refresh_execution_plan",
    "artifact_cleanup_delete_review",
    "duckdb_post_migration_validation",
    "production_promotion_review",
]
STORAGE_PHYSICAL_EXECUTION_PHASE_LABELS = {
    "physical_schema_validation_acceptance": "Physical schema validation acceptance",
    "dataset_version_manifest_write_validate": "Dataset version manifest write and validate",
    "schema_migration_execution_plan": "Schema migration execution plan",
    "partition_migration_execution_plan": "Partition migration execution plan",
    "physical_compaction_execution_plan": "Physical compaction execution plan",
    "cache_ttl_refresh_execution_plan": "Cache TTL refresh execution plan",
    "artifact_cleanup_delete_review": "Artifact cleanup delete review",
    "duckdb_post_migration_validation": "DuckDB post-migration validation",
    "production_promotion_review": "Production promotion review",
}
CURRENT_RESULT_LINEAGE_PACKET_KEY = "command_center_3_candidate_radar_cache"
CURRENT_RESULT_LINEAGE_DATASET = "research_result_lineage"
CURRENT_RESULT_LINEAGE_REQUIRED_COLUMNS = [
    "task_id",
    "user_confirm_task_id",
    "task_family_id",
    "symbol",
    "scope_hash",
    "provider_call_ledger_ids_json",
    "input_packet_keys_json",
    "output_packet_keys_json",
    "data_date",
    "freshness_state",
    "model_ledger_id",
    "result_version",
    "facts_packet_key",
    "facts_package_hash",
    "deepseek_status",
    "promoted_at",
]
V04_STORAGE_ACCEPTANCE_COLUMNS = ["ts_code", "trade_date", "metric", "value", "stage"]
STORAGE_PHYSICAL_DURABLE_EVIDENCE_KEYS = [
    "production_blocker_audit_visible",
    "readiness_receipt_visible",
    "activation_receipt_visible",
    "physical_execution_recipe_ready",
    "physical_execution_request_visible",
    "current_result_atomic_parquet_promotion_required",
    "physical_schema_validation_evidence_required",
    "dataset_version_manifest_validation_required",
    "partition_migration_evidence_required",
    "physical_compaction_evidence_required",
    "cache_ttl_refresh_evidence_required",
    "artifact_cleanup_delete_review_required",
    "duckdb_post_migration_validation_required",
    "production_promotion_review_required",
    "no_provider_trade_action_secret_boundary",
]
STORAGE_PHYSICAL_DURABLE_EVIDENCE_LABELS = {
    "production_blocker_audit_visible": "Production blocker audit visible",
    "readiness_receipt_visible": "Readiness receipt visible",
    "activation_receipt_visible": "Activation receipt visible",
    "physical_execution_recipe_ready": "Physical execution recipe ready",
    "physical_execution_request_visible": "Physical execution request visible",
    "current_result_atomic_parquet_promotion_required": "Current result atomic Parquet promotion required",
    "physical_schema_validation_evidence_required": "Physical schema validation evidence required",
    "dataset_version_manifest_validation_required": "Dataset version manifest validation required",
    "partition_migration_evidence_required": "Partition migration evidence required",
    "physical_compaction_evidence_required": "Physical compaction evidence required",
    "cache_ttl_refresh_evidence_required": "Cache TTL refresh evidence required",
    "artifact_cleanup_delete_review_required": "Artifact cleanup delete review required",
    "duckdb_post_migration_validation_required": "DuckDB post-migration validation required",
    "production_promotion_review_required": "Production promotion review required",
    "no_provider_trade_action_secret_boundary": "No provider, trade, action, or secret boundary",
}
LOCAL_ARTIFACT_HYGIENE_TARGETS = [
    {
        "artifact": "command_center_runtime_cache",
        "path_parts": [".stock_ming_3"],
        "artifact_type": "runtime_cache_dir",
        "expected_kind": "directory",
        "git_policy": "ignored_local_only",
        "cleanup_policy": "manual_only_after_review",
        "reason": "SQLite metadata, Parquet datasets, task packets and local runtime state must stay out of git.",
    },
    {
        "artifact": "legacy_streamlit_cache",
        "path_parts": [".stock_ming_cache"],
        "artifact_type": "legacy_cache_dir",
        "expected_kind": "directory",
        "git_policy": "ignored_local_only",
        "cleanup_policy": "manual_only_after_review",
        "reason": "Legacy fallback cache may contain local snapshots and should not be committed.",
    },
    {
        "artifact": "desktop_build_output",
        "path_parts": ["desktop", "dist"],
        "artifact_type": "frontend_build_dir",
        "expected_kind": "directory",
        "git_policy": "ignored_generated_output",
        "cleanup_policy": "manual_or_build_tool_only",
        "reason": "Vite build output is reproducible generated UI artifact.",
    },
    {
        "artifact": "desktop_dependencies",
        "path_parts": ["desktop", "node_modules"],
        "artifact_type": "dependency_dir",
        "expected_kind": "directory",
        "git_policy": "ignored_generated_output",
        "cleanup_policy": "package_manager_only",
        "reason": "Node dependencies are restored from lockfiles and must not enter git.",
    },
    {
        "artifact": "tauri_build_output",
        "path_parts": ["desktop", "src-tauri", "target"],
        "artifact_type": "rust_build_dir",
        "expected_kind": "directory",
        "git_policy": "ignored_generated_output",
        "cleanup_policy": "manual_or_cargo_only",
        "reason": "Rust/Tauri target output is generated and can be large.",
    },
    {
        "artifact": "python_bytecode_cache",
        "path_parts": ["__pycache__"],
        "artifact_type": "bytecode_cache_dir",
        "expected_kind": "directory",
        "git_policy": "ignored_generated_output",
        "cleanup_policy": "manual_only_after_review",
        "reason": "Python bytecode caches are generated and not source artifacts.",
    },
]
LOCAL_ARTIFACT_GIT_EXCLUDED_PATTERNS = [
    "desktop/node_modules",
    "desktop/dist",
    "desktop/src-tauri/target",
    "target/",
    "__pycache__/",
    "*.parquet",
    "*.duckdb",
    "*.sqlite",
    "*.db",
    "*.log",
    ".env",
    ".stock_ming_3/",
    ".stock_ming_cache/",
]
DATASET_SCHEMA_CONTRACTS = {
    "factor_values": {
        "schema_version": "storage.factor_values.v1",
        "date_column": "trade_date",
        "entity_columns": ["ts_code", "factor_key"],
        "primary_key": ["ts_code", "trade_date", "factor_key"],
        "required_columns": ["factor_key", "ts_code", "trade_date", "raw_value", "data_status", "calculated_at"],
        "recommended_partition_columns": ["trade_date"],
    },
    "daily": {
        "schema_version": "storage.daily.v1",
        "date_column": "trade_date",
        "entity_columns": ["ts_code"],
        "primary_key": ["ts_code", "trade_date"],
        "required_columns": ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"],
        "recommended_partition_columns": ["trade_date"],
    },
    "daily_basic": {
        "schema_version": "storage.daily_basic.v1",
        "date_column": "trade_date",
        "entity_columns": ["ts_code"],
        "primary_key": ["ts_code", "trade_date"],
        "required_columns": ["ts_code", "trade_date", "turnover_rate", "pe_ttm", "pb", "total_mv", "circ_mv"],
        "recommended_partition_columns": ["trade_date"],
    },
    "moneyflow": {
        "schema_version": "storage.moneyflow.v1",
        "date_column": "trade_date",
        "entity_columns": ["ts_code"],
        "primary_key": ["ts_code", "trade_date"],
        "required_columns": ["ts_code", "trade_date", "buy_sm_amount", "sell_sm_amount", "buy_lg_amount", "sell_lg_amount"],
        "recommended_partition_columns": ["trade_date"],
    },
    "trade_cal": {
        "schema_version": "storage.trade_cal.v1",
        "date_column": "cal_date",
        "entity_columns": ["exchange"],
        "primary_key": ["exchange", "cal_date"],
        "required_columns": ["exchange", "cal_date", "is_open"],
        "recommended_partition_columns": ["exchange"],
    },
    "backtest_results": {
        "schema_version": "storage.backtest_results.v1",
        "date_column": "run_date",
        "entity_columns": ["strategy_key", "universe"],
        "primary_key": ["strategy_key", "universe", "run_date"],
        "required_columns": ["strategy_key", "universe", "run_date", "status", "metrics"],
        "recommended_partition_columns": ["run_date"],
    },
}
DATASET_QUERY_PROJECTION_COLUMNS = {
    "factor_values": ["ts_code", "trade_date", "factor_key", "category", "raw_value", "data_status", "calculated_at"],
    "daily": ["ts_code", "trade_date", "open", "high", "low", "close", "pct_chg", "vol", "amount", "provider_scope_hash", "provider_scope_hash_short", "provider_acceptance_mode", "provider_source_task_type"],
    "daily_basic": ["ts_code", "trade_date", "turnover_rate", "pe_ttm", "pb", "total_mv", "circ_mv", "provider_scope_hash", "provider_scope_hash_short", "provider_acceptance_mode", "provider_source_task_type"],
    "moneyflow": [
        "ts_code",
        "trade_date",
        "buy_sm_amount",
        "sell_sm_amount",
        "buy_lg_amount",
        "sell_lg_amount",
        "net_mf_amount", "provider_scope_hash", "provider_scope_hash_short", "provider_acceptance_mode", "provider_source_task_type",
    ],
    "trade_cal": ["exchange", "cal_date", "is_open", "pretrade_date"],
    "backtest_results": ["strategy_key", "universe", "run_date", "status", "metrics"],
}
DATASET_CATALOG = [
    {
        "dataset": "factor_values",
        "aliases": ["factor-values"],
        "cache_endpoint": "GET /api/storage/factor-values",
        "source": "runtime.factor_values",
        "purpose": "light mode 因子运行值本地落盘",
        "write_policy": "task_pipeline_write_allowed",
        "writer": "POST /api/factor-quant/run-light",
        "external_refresh_policy": "local_cache_pipeline_no_external_call",
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    },
    {
        "dataset": "daily",
        "aliases": [],
        "cache_endpoint": "GET /api/storage/daily",
        "source": "tushare.daily parquet cache",
        "purpose": "日线 OHLCV 与次日图谱行情底座",
        "write_policy": "future_button_gated_tushare_task",
        "writer": "future refresh_tushare_facts task",
        "external_refresh_policy": "button_gated_tushare_capable",
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    },
    {
        "dataset": "daily_basic",
        "aliases": ["daily-basic"],
        "cache_endpoint": "GET /api/storage/daily-basic",
        "source": "tushare.daily_basic parquet cache",
        "purpose": "估值、换手率、市值等 A 股基础因子底座",
        "write_policy": "future_button_gated_tushare_task",
        "writer": "future refresh_tushare_facts task",
        "external_refresh_policy": "button_gated_tushare_capable",
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    },
    {
        "dataset": "moneyflow",
        "aliases": [],
        "cache_endpoint": "GET /api/storage/moneyflow",
        "source": "tushare.moneyflow parquet cache",
        "purpose": "资金流因子与市场证据底座",
        "write_policy": "future_button_gated_tushare_task",
        "writer": "future refresh_tushare_facts task",
        "external_refresh_policy": "button_gated_tushare_capable",
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    },
    {
        "dataset": "trade_cal",
        "aliases": ["trade-cal"],
        "cache_endpoint": "GET /api/storage/trade-cal",
        "source": "tushare.trade_cal parquet cache",
        "purpose": "A 股交易日历 freshness gate、盘前/盘中/盘后 expected_data_date 推导",
        "write_policy": "future_button_gated_tushare_task",
        "writer": "POST /api/tasks/refresh-tushare-facts",
        "external_refresh_policy": "button_gated_tushare_capable",
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    },
    {
        "dataset": "backtest_results",
        "aliases": ["backtest-results"],
        "cache_endpoint": "GET /api/storage/backtest-results",
        "source": "local backtest task parquet cache",
        "purpose": "旧量化/组合回测结果持久化预留",
        "write_policy": "future_button_gated_backtest_task",
        "writer": "future backtest task",
        "external_refresh_policy": "local_compute_task_no_external_call",
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    },
]


def _path_label(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _cache_ttl_status(dataset: str, path: Path, metadata: Mapping[str, Any]) -> dict[str, Any]:
    ttl_seconds = int(DATASET_TTL_SECONDS.get(dataset, 24 * 60 * 60))
    exists = bool(metadata.get("exists"))
    state = "missing"
    age_seconds = None
    stale_reason = "dataset_missing"
    if exists and path.exists():
        updated_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        age_seconds = max(0, int((datetime.now(timezone.utc) - updated_at).total_seconds()))
        state = "fresh" if age_seconds <= ttl_seconds else "stale"
        stale_reason = "within_ttl" if state == "fresh" else "age_exceeds_ttl"
    return {
        "dataset": dataset,
        "ttl_seconds": ttl_seconds,
        "ttl_hours": round(ttl_seconds / 3600, 2),
        "cache_age_seconds": age_seconds,
        "ttl_state": state,
        "stale_reason": stale_reason,
        "refresh_policy": "post_task_required",
        "auto_refresh_on_get": False,
        "cache_read_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def _cache_ttl_dry_run_row(dataset: str) -> dict[str, Any]:
    path = parquet_store.dataset_path(root=PARQUET_ROOT, name=dataset)
    metadata = parquet_store.dataset_metadata(root=PARQUET_ROOT, name=dataset)
    ttl_status = _cache_ttl_status(dataset, path, metadata)
    catalog_item = _dataset_catalog_item(dataset)
    ttl_state = str(ttl_status.get("ttl_state") or "unknown")
    if ttl_state == "stale":
        dry_run_status = "refresh_recommended"
    elif ttl_state == "fresh":
        dry_run_status = "fresh_no_action"
    elif ttl_state == "missing":
        dry_run_status = "missing_dataset"
    else:
        dry_run_status = ttl_state
    refresh_policy = str(catalog_item.get("external_refresh_policy") or "")
    return {
        "dataset": dataset,
        "status": dry_run_status,
        "cache_ttl_dry_run_status": dry_run_status,
        "ttl_state": ttl_state,
        "stale_reason": ttl_status.get("stale_reason"),
        "ttl_seconds": ttl_status.get("ttl_seconds"),
        "ttl_hours": ttl_status.get("ttl_hours"),
        "cache_age_seconds": ttl_status.get("cache_age_seconds"),
        "path": _path_label(path),
        "parquet_status": metadata.get("status", "missing"),
        "refresh_policy": "post_task_required",
        "refresh_task_required": True,
        "refresh_recommended": dry_run_status == "refresh_recommended",
        "refresh_task_route": catalog_item.get("writer"),
        "external_refresh_policy": refresh_policy,
        "button_gated": "button_gated" in refresh_policy or str(catalog_item.get("write_policy") or "") == "task_pipeline_write_allowed",
        "tushare_capable": "tushare" in refresh_policy,
        "local_compute_capable": "local_compute" in refresh_policy or "local_cache_pipeline" in refresh_policy,
        "auto_refresh_on_get": False,
        "auto_refresh_on_post": False,
        "refresh_executed": False,
        "would_call_external_source": False,
        "would_write_parquet": False,
        "post_dry_run_writes_parquet": False,
        "post_dry_run_reads_row_payloads": False,
        "cache_get_writes_files": False,
        "cache_get_reads_payloads": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def storage_cache_ttl_dry_run_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [_cache_ttl_dry_run_row(dataset) for dataset in CANONICAL_PARQUET_DATASETS]
    status_counts = _count_values(row.get("cache_ttl_dry_run_status") for row in rows)
    refresh_recommended_count = sum(1 for row in rows if row.get("refresh_recommended"))
    packet = {
        "schema_version": "command_center_3_storage_cache_ttl_dry_run.v1",
        "packet_key": CACHE_TTL_DRY_RUN_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": "dry_run_completed",
        "mode": "dry_run",
        "scope": "cache_ttl_refresh_plan_before_provider_call",
        "dataset_count": len(rows),
        "refresh_recommended_count": refresh_recommended_count,
        "fresh_no_action_count": status_counts.get("fresh_no_action", 0),
        "missing_dataset_count": status_counts.get("missing_dataset", 0),
        "refresh_executed_count": 0,
        "status_counts": status_counts,
        "rows": rows,
        "request_params_safe": {
            "source": (payload_safe or {}).get("source") or "storage_page_button",
            "dry_run": True,
            "external_sources_allowed": False,
            "refresh_allowed": False,
            "write_parquet_allowed": False,
        },
        "cache_get_writes_files": False,
        "post_dry_run_writes_parquet": False,
        "post_dry_run_reads_row_payloads": False,
        "post_dry_run_reads_env_files": False,
        "auto_refresh_on_get": False,
        "refresh_executed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "contains_secret": False,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_cache_ttl_dry_run",
            endpoint="POST /api/storage/cache-ttl/dry-run",
            status="dry_run_completed",
            row_count=len(rows),
        ),
        "warnings": [
            "POST /api/storage/cache-ttl/dry-run 只生成本地 TTL 刷新建议；不会刷新数据。",
            "cache TTL dry-run 不读取行 payload、不写 Parquet、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }
    return packet


def run_storage_cache_ttl_dry_run_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "dry_run": True,
        "external_sources_allowed": False,
        "refresh_allowed": False,
        "write_parquet_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_cache_ttl_dry_run",
        output_packet_key=CACHE_TTL_DRY_RUN_PACKET_KEY,
        payload=task_payload,
        current_step="storage_cache_ttl_dry_run_queued",
        warnings=[
            "storage cache TTL dry-run 只读取本地文件 metadata/mtime；不会刷新外部源、不会读取行 payload、不会写 Parquet。",
            "任何真实 refresh 必须走单独按钮任务；本任务不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="building_storage_cache_ttl_refresh_plan",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_cache_ttl_dry_run_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(CACHE_TTL_DRY_RUN_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_cache_ttl_dry_run_storage_write_failed",
            error_message_safe="storage_cache_ttl_dry_run_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_cache_ttl_dry_run_failed_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="storage_cache_ttl_dry_run_completed",
        call_ledger=packet["call_ledger"],
        warning="storage_cache_ttl_dry_run_completed_no_refresh_no_external_call",
    ) or task


def _schema_contract(dataset: str) -> dict[str, Any]:
    contract = dict(DATASET_SCHEMA_CONTRACTS.get(dataset) or {})
    if not contract:
        return {
            "dataset": dataset,
            "status": "missing_contract",
            "schema_version": None,
            "external_calls_triggered": False,
        }
    contract["dataset"] = dataset
    contract["status"] = "contract_ready"
    contract["physical_migration_done"] = False
    contract["external_calls_triggered"] = False
    contract["tushare_called"] = False
    contract["deepseek_called"] = False
    contract["github_called"] = False
    contract["does_not_modify_strategy_action"] = True
    contract["does_not_execute_trades"] = True
    return contract


def _dataset_catalog_item(dataset: str) -> dict[str, Any]:
    for item in DATASET_CATALOG:
        if item.get("dataset") == dataset:
            return dict(item)
    return {"dataset": dataset}


def _dataset_query_projection_columns(dataset: str) -> list[str]:
    projection = DATASET_QUERY_PROJECTION_COLUMNS.get(dataset)
    if projection:
        return list(projection)
    return [str(column) for column in _schema_contract(dataset).get("required_columns") or []]


def _schema_migration_row(dataset: str, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    catalog_item = _dataset_catalog_item(dataset)
    contract = _schema_contract(dataset)
    path = parquet_store.dataset_path(root=PARQUET_ROOT, name=dataset)
    metadata = dict(metadata or parquet_store.dataset_metadata(root=PARQUET_ROOT, name=dataset))
    if contract.get("status") == "contract_ready":
        migration_status = "contract_ready_physical_validation_pending"
    else:
        migration_status = "missing_schema_contract"
    required_columns = list(contract.get("required_columns") or [])
    return {
        "dataset": dataset,
        "status": migration_status,
        "migration_status": migration_status,
        "current_schema_version": contract.get("schema_version"),
        "target_schema_version": contract.get("schema_version"),
        "schema_version_change_detected": False,
        "physical_column_validation_status": "not_run_metadata_only",
        "physical_validation_done": False,
        "schema_migration_executed": False,
        "schema_migration_ready_for_execution": False,
        "physical_validation_required_before_migration": True,
        "requires_manual_migration_task": True,
        "manual_migration_task_required": True,
        "reason": "physical_validation_not_run",
        "parquet_status": metadata.get("status", "missing"),
        "path": _path_label(Path(str(metadata.get("path") or path))),
        "write_policy": catalog_item.get("write_policy"),
        "writer": catalog_item.get("writer"),
        "primary_key": contract.get("primary_key") or [],
        "required_columns": required_columns,
        "required_column_count": len(required_columns),
        "missing_required_columns": [],
        "missing_required_columns_status": "not_evaluated_metadata_only",
        "expected_partition_columns": contract.get("recommended_partition_columns") or [],
        "cache_get_writes_files": False,
        "cache_get_reads_payloads": False,
        "physical_validation_reads_payloads": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def storage_schema_migration_preflight() -> dict[str, Any]:
    execution_evidence = storage_schema_migration_execution_evidence()
    execution_rows = {
        str(row.get("dataset") or ""): dict(row)
        for row in execution_evidence.get("rows") or []
        if isinstance(row, Mapping)
    }
    rows = []
    for dataset in CANONICAL_PARQUET_DATASETS:
        row = _schema_migration_row(dataset)
        execution_row = execution_rows.get(dataset)
        if execution_row and execution_row.get("schema_migration_executed") is True:
            row.update(
                {
                    "status": "schema_migration_noop_verified",
                    "migration_status": "schema_migration_noop_verified",
                    "physical_column_validation_status": "accepted_physical_schema",
                    "physical_validation_done": True,
                    "schema_migration_executed": True,
                    "schema_migration_ready_for_execution": True,
                    "requires_manual_migration_task": False,
                    "manual_migration_task_required": False,
                    "reason": "current_schema_matches_target_no_rewrite_required",
                    "schema_version_change_detected": False,
                    "migration_execution_status": execution_row.get("migration_execution_status"),
                    "schema_migration_rewrite_executed": execution_row.get("schema_migration_rewrite_executed"),
                    "writes_parquet": execution_row.get("writes_parquet"),
                    "reads_row_payloads": execution_row.get("reads_row_payloads"),
                }
            )
        rows.append(row)
    status = (
        "schema_migration_execution_noop_verified"
        if rows and all(row.get("schema_migration_executed") for row in rows)
        else (
            "preflight_ready"
            if all(row.get("migration_status") == "contract_ready_physical_validation_pending" for row in rows)
            else "contract_gap"
        )
    )
    return {
        "schema_version": "command_center_3_storage_schema_migration_preflight.v1",
        "status": status,
        "scope": "schema_version_migration_contract",
        "mode": "metadata_only_read_only_preflight",
        "dataset_count": len(rows),
        "contract_ready_count": sum(1 for row in rows if row.get("migration_status") == "contract_ready_physical_validation_pending"),
        "physical_validation_done_count": sum(1 for row in rows if row.get("physical_validation_done")),
        "migration_executed_count": sum(1 for row in rows if row.get("schema_migration_executed")),
        "schema_migration_ready_count": sum(1 for row in rows if row.get("schema_migration_ready_for_execution")),
        "manual_migration_task_required": not all(row.get("schema_migration_executed") for row in rows),
        "schema_migration_task_executed": execution_evidence.get("schema_migration_executed") is True,
        "schema_migration_execution_status": execution_evidence.get("status"),
        "schema_migration_execution_packet_key": SCHEMA_MIGRATION_EXECUTION_PACKET_KEY,
        "cache_get_writes_files": False,
        "cache_api_external_calls": False,
        "physical_validation_reads_payloads": False,
        "payload_reads_on_get": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "status_counts": _count_values(row.get("migration_status") for row in rows),
        "rows": rows,
        "note": "Schema migration preflight is GET read-only. Execution evidence, when present, must come from explicit POST schema-migration task.",
    }


def _dataset_version_manifest_path() -> Path:
    return PARQUET_ROOT / DATASET_VERSION_MANIFEST_NAME


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _stable_json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_stable_json_text(payload).encode("utf-8")).hexdigest()


def _dataset_version_manifest_payload() -> tuple[dict[str, Any], str, str]:
    manifest_path = _dataset_version_manifest_path()
    if not manifest_path.exists():
        return {}, "manifest_missing", ""
    try:
        parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, "manifest_read_failed", _safe_error_message(exc)
    if not isinstance(parsed, dict):
        return {}, "manifest_invalid_shape", "manifest_root_not_object"
    return parsed, "manifest_read", ""


def _dataset_version_manifest_rows(manifest: Mapping[str, Any], manifest_status: str) -> list[dict[str, Any]]:
    raw_datasets = manifest.get("datasets") if isinstance(manifest, Mapping) else {}
    if isinstance(raw_datasets, list):
        manifest_datasets = {
            str(item.get("dataset") or item.get("name") or ""): item
            for item in raw_datasets
            if isinstance(item, Mapping)
        }
    elif isinstance(raw_datasets, Mapping):
        manifest_datasets = {str(key): value for key, value in raw_datasets.items()}
    else:
        manifest_datasets = {}
    if not manifest_datasets and isinstance(manifest, Mapping):
        manifest_datasets = {
            str(key): value
            for key, value in manifest.items()
            if key in CANONICAL_PARQUET_DATASETS and isinstance(value, Mapping)
        }

    rows: list[dict[str, Any]] = []
    for dataset in CANONICAL_PARQUET_DATASETS:
        contract = _schema_contract(dataset)
        expected_version = str(contract.get("schema_version") or "")
        raw_row = manifest_datasets.get(dataset)
        manifest_present = isinstance(raw_row, Mapping)
        manifest_version = ""
        if isinstance(raw_row, Mapping):
            manifest_version = str(
                raw_row.get("schema_version")
                or raw_row.get("dataset_version")
                or raw_row.get("version")
                or ""
            )
        if manifest_status != "manifest_read":
            status = "manifest_missing_validation_pending" if manifest_status == "manifest_missing" else manifest_status
        elif not manifest_present:
            status = "dataset_missing_from_manifest"
        elif manifest_version != expected_version:
            status = "dataset_version_mismatch"
        else:
            status = "dataset_version_manifest_validated"
        rows.append(
            {
                "dataset": dataset,
                "status": status,
                "expected_schema_version": expected_version,
                "manifest_present": manifest_present,
                "manifest_schema_version": manifest_version,
                "version_match": status == "dataset_version_manifest_validated",
                "physical_dataset_version_validated": status == "dataset_version_manifest_validated",
                "dataset_version_migration_executed": False,
                "manifest_written_on_get": False,
                "cache_get_writes_files": False,
                "cache_get_reads_parquet_payloads": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_modify_strategy_action": True,
                "does_not_execute_trades": True,
            }
        )
    return rows


def storage_dataset_version_manifest_evidence_audit() -> dict[str, Any]:
    manifest_path = _dataset_version_manifest_path()
    manifest, manifest_status, error_message_safe = _dataset_version_manifest_payload()
    manifest_datasets = manifest.get("datasets") if isinstance(manifest.get("datasets"), Mapping) else {}
    rows = _dataset_version_manifest_rows(manifest, manifest_status)
    status_counts = _count_values(row.get("status") for row in rows)
    validated_count = sum(1 for row in rows if row.get("physical_dataset_version_validated"))
    manifest_present = manifest_status == "manifest_read"
    dataset_count = len(CANONICAL_PARQUET_DATASETS)
    if not manifest_present:
        status = "manifest_missing_validation_pending" if manifest_status == "manifest_missing" else "manifest_validation_blocked"
    elif validated_count == dataset_count:
        status = "manifest_validation_ready_local_only"
    else:
        status = "manifest_validation_incomplete"
    manifest_content_sha256 = _json_sha256(manifest) if manifest_present else ""
    audit = {
        "schema_version": "command_center_3_storage_dataset_version_manifest_evidence.v1",
        "status": status,
        "scope": "read_only_local_manifest_evidence_not_manifest_writer",
        "mode": "cache_only_read_only_manifest_evidence",
        "manifest_path": _path_label(manifest_path),
        "manifest_exists": manifest_present,
        "manifest_read_status": manifest_status,
        "manifest_hash_algorithm": "sha256" if manifest_present else "",
        "manifest_content_sha256": manifest_content_sha256,
        "manifest_dataset_keys": sorted(str(key) for key in manifest_datasets) if manifest_present else [],
        "dataset_count": dataset_count,
        "manifest_dataset_count": sum(1 for row in rows if row.get("manifest_present")),
        "validated_dataset_count": validated_count,
        "missing_dataset_count": sum(1 for row in rows if row.get("status") == "dataset_missing_from_manifest"),
        "schema_version_mismatch_count": sum(1 for row in rows if row.get("status") == "dataset_version_mismatch"),
        "dataset_version_manifest_validated": manifest_present and validated_count == dataset_count,
        "dataset_version_manifest_written": False,
        "manifest_writer_task_executed": False,
        "dataset_version_migration_executed_count": 0,
        "status_counts": status_counts,
        "rows": rows,
        "manifest_written_on_get": False,
        "cache_get_writes_files": False,
        "cache_get_reads_parquet_payloads": False,
        "cache_get_reads_payloads": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_dataset_version_manifest_evidence",
            endpoint="GET /api/storage",
            status=status,
            row_count=len(rows),
            path=_path_label(manifest_path),
        ),
        "note": "This audit reads only a local ignored _dataset_versions.json when present. It does not create, update, or validate Parquet payloads on GET.",
    }
    if error_message_safe:
        audit["error_message_safe"] = error_message_safe
    return audit


def _dataset_version_manifest_proposal_row(current_row: Mapping[str, Any]) -> dict[str, Any]:
    dataset = str(current_row.get("dataset") or "")
    contract = _schema_contract(dataset)
    expected_version = str(contract.get("schema_version") or "")
    current_status = str(current_row.get("status") or "")
    if current_status == "dataset_version_manifest_validated":
        proposal_status = "already_current"
    elif current_status in {"manifest_read_failed", "manifest_invalid_shape"}:
        proposal_status = "blocked_existing_manifest_unreadable"
    elif current_status == "dataset_version_mismatch":
        proposal_status = "would_update_dataset_version"
    else:
        proposal_status = "would_add_dataset_version"
    return {
        "dataset": dataset,
        "status": proposal_status,
        "current_status": current_status,
        "expected_schema_version": expected_version,
        "current_manifest_schema_version": str(current_row.get("manifest_schema_version") or ""),
        "manifest_present": bool(current_row.get("manifest_present")),
        "proposed_manifest_entry": {
            "schema_version": expected_version,
            "date_column": contract.get("date_column"),
            "primary_key": contract.get("primary_key") or [],
            "required_column_count": len(contract.get("required_columns") or []),
            "recommended_partition_columns": contract.get("recommended_partition_columns") or [],
        },
        "would_change_manifest": proposal_status in {"would_add_dataset_version", "would_update_dataset_version"},
        "manifest_write_executed": False,
        "writes_parquet": False,
        "reads_parquet_payloads": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def storage_dataset_version_manifest_dry_run_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = storage_dataset_version_manifest_evidence_audit()
    rows = [_dataset_version_manifest_proposal_row(row) for row in evidence["rows"]]
    status_counts = _count_values(row.get("status") for row in rows)
    blocked_count = status_counts.get("blocked_existing_manifest_unreadable", 0)
    would_change_count = sum(1 for row in rows if row.get("would_change_manifest"))
    proposed_manifest = {
        "schema_version": "command_center_3_dataset_versions_manifest.v1",
        "generated_by": "storage_dataset_version_manifest_dry_run",
        "generated_at": _now_iso(),
        "manifest_path": _path_label(_dataset_version_manifest_path()),
        "datasets": {
            row["dataset"]: row["proposed_manifest_entry"]
            for row in rows
            if row.get("status") != "blocked_existing_manifest_unreadable"
        },
    }
    proposed_manifest_content_sha256 = _json_sha256(proposed_manifest)
    packet = {
        "schema_version": "command_center_3_storage_dataset_version_manifest_dry_run.v1",
        "packet_key": DATASET_VERSION_MANIFEST_DRY_RUN_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": "dry_run_completed" if blocked_count == 0 else "dry_run_blocked_existing_manifest_unreadable",
        "mode": "dry_run",
        "scope": "dataset_version_manifest_write_plan_before_manifest_write",
        "manifest_path": _path_label(_dataset_version_manifest_path()),
        "dataset_count": len(rows),
        "would_change_count": would_change_count,
        "already_current_count": status_counts.get("already_current", 0),
        "blocked_count": blocked_count,
        "status_counts": status_counts,
        "rows": rows,
        "current_manifest_evidence": evidence,
        "proposed_manifest": proposed_manifest,
        "proposed_manifest_hash_algorithm": "sha256",
        "proposed_manifest_content_sha256": proposed_manifest_content_sha256,
        "proposed_manifest_dataset_count": len(proposed_manifest["datasets"]),
        "request_params_safe": {
            "source": (payload_safe or {}).get("source") or "storage_page_button",
            "dry_run": True,
            "write_manifest_allowed": False,
            "external_sources_allowed": False,
            "write_parquet_allowed": False,
        },
        "manifest_write_plan_ready": blocked_count == 0,
        "manifest_write_executed": False,
        "manifest_written_on_post": False,
        "manifest_written_on_get": False,
        "cache_get_writes_files": False,
        "post_dry_run_writes_manifest": False,
        "post_dry_run_writes_parquet": False,
        "post_dry_run_reads_parquet_payloads": False,
        "post_dry_run_reads_env_files": False,
        "manual_approval_required_before_write": True,
        "separate_write_task_required": True,
        "production_storage_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_dataset_version_manifest_dry_run",
            endpoint="POST /api/storage/dataset-version-manifest/dry-run",
            status="dry_run_completed" if blocked_count == 0 else "dry_run_blocked_existing_manifest_unreadable",
            row_count=len(rows),
            path=_path_label(_dataset_version_manifest_path()),
        ),
        "warnings": [
            "POST /api/storage/dataset-version-manifest/dry-run 只生成本地 _dataset_versions.json 写入计划；不会写 manifest。",
            "manifest dry-run 不读取 Parquet 行 payload、不写 Parquet、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }
    return packet


def run_storage_dataset_version_manifest_dry_run_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "dry_run": True,
        "write_manifest_allowed": False,
        "external_sources_allowed": False,
        "write_parquet_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_dataset_version_manifest_dry_run",
        output_packet_key=DATASET_VERSION_MANIFEST_DRY_RUN_PACKET_KEY,
        payload=task_payload,
        current_step="storage_dataset_version_manifest_dry_run_queued",
        warnings=[
            "storage dataset version manifest dry-run 只生成本地 manifest 写入计划；不会写 _dataset_versions.json、不会读取 Parquet 行 payload、不会调用外部源。",
            "任何真实 manifest 写入必须在 dry-run 审阅后另行手动确认；本任务不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="building_storage_dataset_version_manifest_write_plan",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_dataset_version_manifest_dry_run_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(DATASET_VERSION_MANIFEST_DRY_RUN_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_dataset_version_manifest_dry_run_storage_write_failed",
            error_message_safe="storage_dataset_version_manifest_dry_run_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_dataset_version_manifest_dry_run_failed_no_manifest_write_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="storage_dataset_version_manifest_dry_run_completed"
        if packet["manifest_write_plan_ready"]
        else "storage_dataset_version_manifest_dry_run_completed_with_blockers",
        call_ledger=packet["call_ledger"],
        warning="storage_dataset_version_manifest_dry_run_completed_no_manifest_write_no_external_call",
    ) or task


def storage_dataset_version_manifest_review_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    dry_run = storage_dataset_version_manifest_dry_run_packet(task_id=task_id, payload_safe=payload_safe)
    schema_acceptance = storage_schema_validation_acceptance_packet(task_id=task_id, payload_safe=payload_safe)
    schema_by_dataset = {
        str(row.get("dataset") or ""): row
        for row in schema_acceptance.get("rows") or []
        if isinstance(row, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for row in dry_run.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        dataset = str(row.get("dataset") or "")
        schema_row = schema_by_dataset.get(dataset, {})
        schema_passed = schema_row.get("physical_schema_acceptance_passed") is True
        manifest_ready = row.get("status") in {"would_add_dataset_version", "would_update_dataset_version", "already_current"}
        review_ready = bool(schema_passed and manifest_ready)
        if review_ready:
            review_status = "review_ready_for_manual_manifest_write"
        elif not schema_passed:
            review_status = "review_blocked_schema_acceptance"
        else:
            review_status = "review_blocked_manifest_plan"
        rows.append(
            {
                **dict(row),
                "review_status": review_status,
                "schema_acceptance_status": schema_row.get("acceptance_status") or "acceptance_missing",
                "physical_schema_acceptance_passed": bool(schema_passed),
                "manifest_plan_status": row.get("status"),
                "manifest_change_required": bool(row.get("would_change_manifest")),
                "manual_review_passed": review_ready,
                "approved_for_manifest_write": review_ready,
                "approved_for_production_promotion": False,
                "manifest_write_executed": False,
                "manifest_written_on_post": False,
                "writes_parquet": False,
                "reads_parquet_payloads": False,
                "schema_migration_executed": False,
                "production_storage_complete": False,
            }
        )
    approved_count = sum(1 for row in rows if row.get("approved_for_manifest_write"))
    blocked_count = len(rows) - approved_count
    status = (
        "manifest_review_ready_for_manual_write"
        if rows and blocked_count == 0 and dry_run.get("manifest_write_plan_ready") is True
        else "manifest_review_blocked"
    )
    return {
        "schema_version": "command_center_3_storage_dataset_version_manifest_review.v1",
        "packet_key": DATASET_VERSION_MANIFEST_REVIEW_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_manifest_review",
        "scope": "dataset_version_manifest_review_before_write_and_promotion",
        "manifest_path": dry_run.get("manifest_path"),
        "dataset_count": len(rows),
        "reviewed_dataset_count": len(rows),
        "approved_dataset_count": approved_count,
        "blocked_dataset_count": blocked_count,
        "would_change_count": int(dry_run.get("would_change_count") or 0),
        "status_counts": _count_values(row.get("review_status") for row in rows),
        "rows": rows,
        "source_dry_run_packet_key": DATASET_VERSION_MANIFEST_DRY_RUN_PACKET_KEY,
        "source_dry_run_status": dry_run.get("status"),
        "source_schema_acceptance_packet_key": SCHEMA_VALIDATION_ACCEPTANCE_PACKET_KEY,
        "source_schema_acceptance_status": schema_acceptance.get("status"),
        "manifest_write_plan_ready": bool(dry_run.get("manifest_write_plan_ready")),
        "schema_acceptance_passed_all": bool(schema_acceptance.get("status") == "schema_acceptance_passed_all_local_datasets"),
        "manual_review_required_before_write": True,
        "separate_write_task_required": True,
        "separate_production_promotion_required": True,
        "manifest_write_executed": False,
        "manifest_written_on_post": False,
        "manifest_written_on_get": False,
        "cache_get_writes_files": False,
        "post_review_writes_manifest": False,
        "post_review_writes_parquet": False,
        "post_review_reads_parquet_payloads": False,
        "post_review_reads_env_files": False,
        "schema_migration_executed": False,
        "dataset_version_manifest_validated": False,
        "production_storage_complete": False,
        "request_params_safe": {
            "source": (payload_safe or {}).get("source") or "storage_page_button",
            "review": True,
            "external_sources_allowed": False,
            "write_manifest_allowed": False,
            "write_parquet_allowed": False,
        },
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_dataset_version_manifest_review",
            endpoint="POST /api/storage/dataset-version-manifest/review",
            status=status,
            row_count=len(rows),
            path=str(dry_run.get("manifest_path") or ""),
        ),
        "warnings": [
            "POST /api/storage/dataset-version-manifest/review 只审查 dry-run 与 schema acceptance；不会写 _dataset_versions.json。",
            "manifest review 不读取 Parquet 行 payload、不写 Parquet、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }


def run_storage_dataset_version_manifest_review_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "review": True,
        "external_sources_allowed": False,
        "write_manifest_allowed": False,
        "write_parquet_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_dataset_version_manifest_review",
        output_packet_key=DATASET_VERSION_MANIFEST_REVIEW_PACKET_KEY,
        payload=task_payload,
        current_step="storage_dataset_version_manifest_review_queued",
        warnings=[
            "storage dataset version manifest review 只审查 dry-run 与 schema acceptance；不会写 _dataset_versions.json、不会读取 Parquet 行 payload、不会调用外部源。",
            "本任务不代表生产 storage 完成；任何 manifest 写入仍需单独手动确认任务。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="reviewing_storage_dataset_version_manifest_plan",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_dataset_version_manifest_review_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(DATASET_VERSION_MANIFEST_REVIEW_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_dataset_version_manifest_review_packet_persist_failed",
            error_message_safe="storage_dataset_version_manifest_review_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_dataset_version_manifest_review_packet_failed_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="storage_dataset_version_manifest_review_completed"
        if packet["status"] == "manifest_review_ready_for_manual_write"
        else "storage_dataset_version_manifest_review_completed_with_blockers",
        call_ledger=packet["call_ledger"],
        warning="storage_dataset_version_manifest_review_completed_no_manifest_write_no_external_call",
    ) or task


def storage_dataset_version_manifest_write_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload_safe = payload_safe or {}
    confirm_manifest_write = payload_safe.get("confirm_manifest_write") is True
    dry_run_packet = storage_dataset_version_manifest_dry_run_packet(task_id=task_id, payload_safe=payload_safe)
    manifest_path = _dataset_version_manifest_path()
    write_blocked = not confirm_manifest_write or not dry_run_packet.get("manifest_write_plan_ready")
    pre_write_evidence = dry_run_packet.get("current_manifest_evidence") if isinstance(dry_run_packet.get("current_manifest_evidence"), Mapping) else {}
    manifest_payload = dict(dry_run_packet.get("proposed_manifest") or {})
    manifest_payload.update(
        {
            "generated_by": "storage_dataset_version_manifest_write_task",
            "written_at": _now_iso(),
            "source_task_id": str(task_id or ""),
            "write_policy": "button_gated_local_manifest_only",
        }
    )
    written_manifest_content_sha256 = _json_sha256(manifest_payload) if manifest_payload else ""
    write_error = ""
    manifest_write_executed = False
    if not write_blocked:
        try:
            _write_json_atomic(manifest_path, manifest_payload)
            manifest_write_executed = True
        except Exception as exc:
            write_error = _safe_error_message(exc)
            write_blocked = True

    post_write_evidence = storage_dataset_version_manifest_evidence_audit()
    post_write_manifest_content_sha256 = str(post_write_evidence.get("manifest_content_sha256") or "")
    post_write_manifest_hash_matches_written_payload = (
        manifest_write_executed
        and bool(written_manifest_content_sha256)
        and post_write_manifest_content_sha256 == written_manifest_content_sha256
    )
    status = "manifest_write_blocked_confirmation_required"
    if confirm_manifest_write and not dry_run_packet.get("manifest_write_plan_ready"):
        status = "manifest_write_blocked_plan_not_ready"
    elif write_error:
        status = "manifest_write_failed"
    elif manifest_write_executed and post_write_evidence.get("dataset_version_manifest_validated"):
        status = "manifest_write_completed_validated"
    elif manifest_write_executed:
        status = "manifest_write_completed_validation_incomplete"
    packet = {
        "schema_version": "command_center_3_storage_dataset_version_manifest_write.v1",
        "packet_key": DATASET_VERSION_MANIFEST_WRITE_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_manifest_write",
        "scope": "local_dataset_version_manifest_writer_after_dry_run",
        "manifest_path": _path_label(manifest_path),
        "confirm_manifest_write": confirm_manifest_write,
        "manifest_write_plan_ready": bool(dry_run_packet.get("manifest_write_plan_ready")),
        "manifest_write_executed": manifest_write_executed,
        "manifest_written_on_post": manifest_write_executed,
        "manifest_written_on_get": False,
        "cache_get_writes_files": False,
        "post_write_validation_status": post_write_evidence.get("status"),
        "post_write_manifest_validated": bool(post_write_evidence.get("dataset_version_manifest_validated")),
        "manifest_hash_algorithm": "sha256",
        "pre_write_manifest_content_sha256": str(pre_write_evidence.get("manifest_content_sha256") or ""),
        "dry_run_proposed_manifest_content_sha256": str(dry_run_packet.get("proposed_manifest_content_sha256") or ""),
        "written_manifest_content_sha256": written_manifest_content_sha256 if manifest_write_executed else "",
        "post_write_manifest_content_sha256": post_write_manifest_content_sha256,
        "post_write_manifest_hash_matches_written_payload": post_write_manifest_hash_matches_written_payload,
        "atomic_manifest_write_used": manifest_write_executed,
        "temporary_manifest_path_policy": "same_directory_hidden_tmp_replace",
        "post_write_validated_dataset_count": post_write_evidence.get("validated_dataset_count"),
        "dataset_count": dry_run_packet.get("dataset_count"),
        "would_change_count": dry_run_packet.get("would_change_count"),
        "proposed_manifest_dataset_count": dry_run_packet.get("proposed_manifest_dataset_count"),
        "written_manifest_dataset_count": len((manifest_payload.get("datasets") or {}) if manifest_write_executed else {}),
        "dry_run_packet_key": DATASET_VERSION_MANIFEST_DRY_RUN_PACKET_KEY,
        "dry_run_status": dry_run_packet.get("status"),
        "dry_run_rows": dry_run_packet.get("rows") or [],
        "post_write_evidence": post_write_evidence,
        "writes_parquet": False,
        "reads_parquet_payloads": False,
        "reads_env_files": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "production_storage_complete": False,
        "request_params_safe": {
            "source": payload_safe.get("source") or "storage_page_button",
            "confirm_manifest_write": confirm_manifest_write,
            "external_sources_allowed": False,
            "write_parquet_allowed": False,
        },
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_dataset_version_manifest_write",
            endpoint="POST /api/storage/dataset-version-manifest/write",
            status=status,
            row_count=int(dry_run_packet.get("dataset_count") or 0),
            path=_path_label(manifest_path),
        ),
        "warnings": [
            "POST /api/storage/dataset-version-manifest/write 只写本地 ignored 的 _dataset_versions.json；不会写 Parquet 或读取 Parquet 行 payload。",
            "dataset version manifest write 不调用 Tushare、DeepSeek、GitHub，不执行真实交易，不修改 strategy action。",
        ],
    }
    if write_error:
        packet["error_message_safe"] = write_error
    return packet


def run_storage_dataset_version_manifest_write_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "confirm_manifest_write": payload_map.get("confirm_manifest_write") is True,
        "external_sources_allowed": False,
        "write_parquet_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_dataset_version_manifest_write",
        output_packet_key=DATASET_VERSION_MANIFEST_WRITE_PACKET_KEY,
        payload=task_payload,
        current_step="storage_dataset_version_manifest_write_queued",
        warnings=[
            "storage dataset version manifest write 只写本地 ignored 的 _dataset_versions.json；不会写 Parquet、不会读取行 payload、不会调用外部源。",
            "本任务只用于 Storage dataset version manifest 验收，不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.4,
        current_step="writing_storage_dataset_version_manifest",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_dataset_version_manifest_write_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(DATASET_VERSION_MANIFEST_WRITE_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_dataset_version_manifest_write_packet_persist_failed",
            error_message_safe="storage_dataset_version_manifest_write_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_dataset_version_manifest_write_packet_failed_no_external_call",
        ) or task
    task_status = "success" if packet["manifest_write_executed"] else "failed"
    return task_service.update_task_status(
        task["task_id"],
        status=task_status,
        progress=1.0,
        current_step="storage_dataset_version_manifest_write_completed"
        if packet["manifest_write_executed"]
        else "storage_dataset_version_manifest_write_blocked",
        error_message_safe=None
        if packet["manifest_write_executed"]
        else str(packet.get("status") or "storage_dataset_version_manifest_write_blocked"),
        call_ledger=packet["call_ledger"],
        warning="storage_dataset_version_manifest_write_completed_local_only"
        if packet["manifest_write_executed"]
        else "storage_dataset_version_manifest_write_blocked_no_manifest_write",
    ) or task


def storage_dataset_version_manifest_validate_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = storage_dataset_version_manifest_evidence_audit()
    rows = []
    blockers: list[str] = []
    for row in evidence.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        status = str(row.get("status") or "")
        validation_passed = status == "dataset_version_manifest_validated"
        if not validation_passed:
            blockers.append(f"{row.get('dataset') or 'unknown'}:{status or 'unknown'}")
        rows.append(
            {
                **dict(row),
                "validation_status": "validated_local_manifest_entry" if validation_passed else "validation_blocked",
                "manifest_validation_passed": validation_passed,
                "approved_for_dataset_version_claim": validation_passed,
                "approved_for_production_promotion": False,
                "manifest_write_executed": False,
                "manifest_written_on_post": False,
                "writes_manifest": False,
                "writes_parquet": False,
                "reads_parquet_payloads": False,
                "schema_migration_executed": False,
                "partition_migration_executed": False,
                "physical_compaction_executed": False,
                "cache_ttl_refresh_executed": False,
                "production_storage_complete": False,
            }
        )
    validated_count = sum(1 for row in rows if row.get("manifest_validation_passed"))
    dataset_count = len(rows)
    status = (
        "manifest_validate_passed_local_only"
        if dataset_count and validated_count == dataset_count
        else "manifest_validate_blocked"
    )
    return {
        "schema_version": "command_center_3_storage_dataset_version_manifest_validate.v1",
        "packet_key": DATASET_VERSION_MANIFEST_VALIDATE_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_manifest_validation",
        "scope": "dataset_version_manifest_validation_after_write_before_production_promotion",
        "manifest_path": evidence.get("manifest_path"),
        "manifest_exists": bool(evidence.get("manifest_exists")),
        "manifest_read_status": evidence.get("manifest_read_status"),
        "dataset_count": dataset_count,
        "validated_dataset_count": validated_count,
        "blocked_dataset_count": dataset_count - validated_count,
        "missing_dataset_count": evidence.get("missing_dataset_count"),
        "schema_version_mismatch_count": evidence.get("schema_version_mismatch_count"),
        "status_counts": _count_values(row.get("validation_status") for row in rows),
        "rows": rows,
        "blockers": blockers,
        "source_manifest_evidence_schema_version": evidence.get("schema_version"),
        "source_manifest_evidence_status": evidence.get("status"),
        "source_manifest_hash_algorithm": evidence.get("manifest_hash_algorithm"),
        "source_manifest_content_sha256": evidence.get("manifest_content_sha256"),
        "source_manifest_hash_present": bool(evidence.get("manifest_content_sha256")),
        "dataset_version_manifest_validated": validated_count == dataset_count and dataset_count > 0,
        "physical_dataset_version_validated_count": validated_count,
        "dataset_version_migration_executed_count": 0,
        "manual_validation_required_after_write": True,
        "separate_manifest_write_required_before_validate": not bool(evidence.get("manifest_exists")),
        "separate_schema_migration_required": True,
        "separate_partition_migration_required": True,
        "separate_production_promotion_required": True,
        "manifest_write_executed": False,
        "manifest_written_on_post": False,
        "manifest_written_on_get": False,
        "cache_get_writes_files": False,
        "post_validate_writes_manifest": False,
        "post_validate_writes_parquet": False,
        "post_validate_reads_parquet_payloads": False,
        "post_validate_reads_env_files": False,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "production_storage_complete": False,
        "request_params_safe": {
            "source": (payload_safe or {}).get("source") or "storage_page_button",
            "validate": True,
            "external_sources_allowed": False,
            "write_manifest_allowed": False,
            "write_parquet_allowed": False,
        },
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_dataset_version_manifest_validate",
            endpoint="POST /api/storage/dataset-version-manifest/validate",
            status=status,
            row_count=dataset_count,
            path=str(evidence.get("manifest_path") or ""),
        ),
        "warnings": [
            "POST /api/storage/dataset-version-manifest/validate 只验证本地 ignored 的 _dataset_versions.json；不会写 manifest。",
            "manifest validate 不读取 Parquet 行 payload、不写 Parquet、不执行 schema/partition/compaction/TTL 任务、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }


def storage_dataset_version_manifest_validate_evidence() -> dict[str, Any]:
    packet, read_status = _read_storage_meta_packet_no_init(DATASET_VERSION_MANIFEST_VALIDATE_PACKET_KEY)
    if read_status != "packet_present" or not isinstance(packet, Mapping):
        return {
            "schema_version": "command_center_3_storage_dataset_version_manifest_validate.v1",
            "packet_key": DATASET_VERSION_MANIFEST_VALIDATE_PACKET_KEY,
            "status": "manifest_validate_missing",
            "read_status": read_status,
            "dataset_version_manifest_validated": False,
            "validated_dataset_count": 0,
            "dataset_count": 0,
            "production_storage_complete": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    evidence = dict(packet)
    evidence["read_status"] = read_status
    evidence.setdefault("dataset_version_manifest_validated", False)
    evidence.setdefault("validated_dataset_count", 0)
    evidence.setdefault("dataset_count", 0)
    evidence.setdefault("production_storage_complete", False)
    evidence.setdefault("external_calls_triggered", False)
    evidence.setdefault("tushare_called", False)
    evidence.setdefault("deepseek_called", False)
    evidence.setdefault("github_called", False)
    evidence.setdefault("does_not_execute_trades", True)
    evidence.setdefault("does_not_modify_strategy_action", True)
    evidence.setdefault("contains_secret", False)
    return evidence


def run_storage_dataset_version_manifest_validate_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "validate": True,
        "external_sources_allowed": False,
        "write_manifest_allowed": False,
        "write_parquet_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_dataset_version_manifest_validate",
        output_packet_key=DATASET_VERSION_MANIFEST_VALIDATE_PACKET_KEY,
        payload=task_payload,
        current_step="storage_dataset_version_manifest_validate_queued",
        warnings=[
            "storage dataset version manifest validate 只验证本地 ignored 的 _dataset_versions.json；不会写 manifest、不会读取 Parquet 行 payload、不会调用外部源。",
            "本任务只验证 manifest 证据，不代表 schema migration、partition migration、compaction、TTL refresh 或 production storage 完成。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="validating_storage_dataset_version_manifest",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_dataset_version_manifest_validate_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(DATASET_VERSION_MANIFEST_VALIDATE_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_dataset_version_manifest_validate_packet_persist_failed",
            error_message_safe="storage_dataset_version_manifest_validate_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_dataset_version_manifest_validate_packet_failed_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="storage_dataset_version_manifest_validate_completed"
        if packet["status"] == "manifest_validate_passed_local_only"
        else "storage_dataset_version_manifest_validate_completed_with_blockers",
        call_ledger=packet["call_ledger"],
        warning="storage_dataset_version_manifest_validate_completed_no_manifest_write_no_external_call",
    ) or task


def _dataset_version_policy_row(dataset: str, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    contract = _schema_contract(dataset)
    path = parquet_store.dataset_path(root=PARQUET_ROOT, name=dataset)
    metadata = dict(metadata or parquet_store.dataset_metadata(root=PARQUET_ROOT, name=dataset))
    manifest_path = _dataset_version_manifest_path()
    dataset_exists = bool(metadata.get("exists"))
    manifest_present = manifest_path.exists()
    if not contract.get("schema_version"):
        version_status = "missing_schema_contract"
    elif not dataset_exists:
        version_status = "contract_declared_dataset_missing"
    elif manifest_present:
        version_status = "manifest_present_physical_validation_pending"
    else:
        version_status = "contract_declared_manifest_missing"
    return {
        "dataset": dataset,
        "status": version_status,
        "version_status": version_status,
        "declared_dataset_version": contract.get("schema_version"),
        "current_schema_version": contract.get("schema_version"),
        "target_schema_version": contract.get("schema_version"),
        "version_source": "local_schema_contract",
        "version_claim_level": "contract_only_not_physical_proof",
        "dataset_path": _path_label(Path(str(metadata.get("path") or path))),
        "version_manifest_path": _path_label(manifest_path),
        "version_manifest_present": manifest_present,
        "physical_dataset_exists": dataset_exists,
        "physical_version_metadata_present": False,
        "physical_version_validated": False,
        "dataset_version_migration_executed": False,
        "dataset_manifest_write_required": True,
        "manual_version_manifest_task_required": True,
        "physical_validation_required_before_version_claim": True,
        "cache_get_writes_files": False,
        "cache_get_reads_payloads": False,
        "manifest_written_on_get": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def storage_dataset_version_policy() -> dict[str, Any]:
    rows = [_dataset_version_policy_row(dataset) for dataset in CANONICAL_PARQUET_DATASETS]
    status_counts = _count_values(row.get("version_status") for row in rows)
    return {
        "schema_version": "command_center_3_storage_dataset_version_policy.v1",
        "status": "policy_ready"
        if all(row.get("declared_dataset_version") for row in rows)
        else "contract_gap",
        "scope": "dataset_versioning_contract_before_manifest_write",
        "mode": "cache_only_read_only_policy",
        "dataset_count": len(rows),
        "target_version_declared_count": sum(1 for row in rows if row.get("declared_dataset_version")),
        "version_manifest_present_count": sum(1 for row in rows if row.get("version_manifest_present")),
        "physical_dataset_version_validated_count": sum(1 for row in rows if row.get("physical_version_validated")),
        "dataset_version_migration_executed_count": sum(
            1 for row in rows if row.get("dataset_version_migration_executed")
        ),
        "manifest_written_on_get_count": sum(1 for row in rows if row.get("manifest_written_on_get")),
        "status_counts": status_counts,
        "rows": rows,
        "version_manifest_path": _path_label(_dataset_version_manifest_path()),
        "version_policy": "contract_only_manifest_write_requires_explicit_task",
        "manifest_write_task_required": True,
        "physical_validation_required_before_version_claim": True,
        "cache_get_writes_files": False,
        "cache_get_reads_payloads": False,
        "manifest_written_on_get": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "note": "Dataset version policy is a read-only contract matrix. It does not create a manifest or validate physical dataset versions.",
    }


def _schema_validation_row(dataset: str) -> dict[str, Any]:
    contract = _schema_contract(dataset)
    schema_metadata = parquet_store.dataset_schema_metadata(root=PARQUET_ROOT, name=dataset)
    required_columns = [str(column) for column in (contract.get("required_columns") or [])]
    physical_columns = [str(column) for column in (schema_metadata.get("columns") or [])]
    missing_required_columns = [column for column in required_columns if column not in physical_columns]
    unexpected_columns = [column for column in physical_columns if column not in required_columns]
    metadata_status = str(schema_metadata.get("status") or "missing")
    if metadata_status == "ready":
        validation_status = "schema_validated" if not missing_required_columns else "schema_mismatch"
        physical_validation_done = True
        validation_passed = not missing_required_columns
    elif metadata_status == "missing":
        validation_status = "missing_dataset"
        physical_validation_done = False
        validation_passed = False
    else:
        validation_status = metadata_status
        physical_validation_done = False
        validation_passed = False
    return {
        "dataset": dataset,
        "status": validation_status,
        "validation_status": validation_status,
        "schema_version": contract.get("schema_version"),
        "target_schema_version": contract.get("schema_version"),
        "parquet_status": metadata_status,
        "path": _path_label(Path(str(schema_metadata.get("path") or parquet_store.dataset_path(root=PARQUET_ROOT, name=dataset)))),
        "required_columns": required_columns,
        "required_column_count": len(required_columns),
        "physical_columns": physical_columns,
        "physical_column_count": len(physical_columns),
        "missing_required_columns": missing_required_columns,
        "missing_required_column_count": len(missing_required_columns),
        "unexpected_columns": unexpected_columns,
        "unexpected_column_count": len(unexpected_columns),
        "primary_key": contract.get("primary_key") or [],
        "expected_partition_columns": contract.get("recommended_partition_columns") or [],
        "row_count_metadata": schema_metadata.get("row_count_metadata"),
        "row_group_count": schema_metadata.get("row_group_count"),
        "schema_read_done": bool(schema_metadata.get("schema_read_done")),
        "physical_validation_done": physical_validation_done,
        "validation_passed": validation_passed,
        "schema_migration_executed": False,
        "schema_migration_ready_for_execution": bool(validation_passed),
        "manual_migration_task_required": True,
        "cache_get_writes_files": False,
        "post_dry_run_writes_parquet": False,
        "does_not_read_row_payloads": True,
        "reads_file_payloads": False,
        "physical_validation_reads_payloads": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def storage_schema_validation_dry_run_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [_schema_validation_row(dataset) for dataset in CANONICAL_PARQUET_DATASETS]
    status_counts = _count_values(row.get("validation_status") for row in rows)
    passed_count = sum(1 for row in rows if row.get("validation_passed"))
    physical_validation_done_count = sum(1 for row in rows if row.get("physical_validation_done"))
    packet = {
        "schema_version": "command_center_3_storage_schema_validation_dry_run.v1",
        "packet_key": SCHEMA_VALIDATION_DRY_RUN_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": "dry_run_completed",
        "mode": "dry_run",
        "scope": "physical_schema_validation_before_migration",
        "dataset_count": len(rows),
        "validation_passed_count": passed_count,
        "validation_failed_count": len(rows) - passed_count,
        "physical_validation_done_count": physical_validation_done_count,
        "missing_dataset_count": status_counts.get("missing_dataset", 0),
        "schema_mismatch_count": status_counts.get("schema_mismatch", 0),
        "read_failed_count": status_counts.get("read_failed", 0),
        "dependency_missing_count": status_counts.get("dependency_missing", 0),
        "schema_migration_ready_count": sum(1 for row in rows if row.get("schema_migration_ready_for_execution")),
        "schema_migration_executed_count": 0,
        "status_counts": status_counts,
        "rows": rows,
        "request_params_safe": {
            "source": (payload_safe or {}).get("source") or "storage_page_button",
            "dry_run": True,
            "external_sources_allowed": False,
            "write_parquet_allowed": False,
        },
        "cache_get_writes_files": False,
        "post_dry_run_writes_parquet": False,
        "post_dry_run_reads_row_payloads": False,
        "post_dry_run_reads_env_files": False,
        "schema_migration_executed": False,
        "manual_migration_task_required": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_schema_validation_dry_run",
            endpoint="POST /api/storage/schema-validation/dry-run",
            status="dry_run_completed",
            row_count=len(rows),
        ),
        "warnings": [
            "POST /api/storage/schema-validation/dry-run 只读取本地 Parquet schema metadata；不会读取行 payload。",
            "schema validation dry-run 不写 Parquet、不执行迁移、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }
    return packet


def run_storage_schema_validation_dry_run_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "dry_run": True,
        "external_sources_allowed": False,
        "write_parquet_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_schema_validation_dry_run",
        output_packet_key=SCHEMA_VALIDATION_DRY_RUN_PACKET_KEY,
        payload=task_payload,
        current_step="storage_schema_validation_dry_run_queued",
        warnings=[
            "storage schema validation dry-run 只读取本地 Parquet schema metadata；不会读取行 payload、不会写 Parquet、不会调用外部源。",
            "任何真实 schema migration 必须在 dry-run 审阅后另行手动确认；本任务不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_storage_schema_metadata",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_schema_validation_dry_run_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(SCHEMA_VALIDATION_DRY_RUN_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_schema_validation_dry_run_storage_write_failed",
            error_message_safe="storage_schema_validation_dry_run_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_schema_validation_dry_run_failed_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="storage_schema_validation_dry_run_completed",
        call_ledger=packet["call_ledger"],
        warning="storage_schema_validation_dry_run_completed_no_write_no_external_call",
    ) or task


def storage_backtest_results_schema_seed_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload_safe = payload_safe or {}
    dataset = "backtest_results"
    contract = _schema_contract(dataset)
    required_columns = [str(column) for column in contract.get("required_columns") or []]
    confirm_schema_seed = payload_safe.get("confirm_schema_seed") is True
    dataset_path = parquet_store.dataset_path(root=PARQUET_ROOT, name=dataset)
    dependency = parquet_store.dependency_status()
    write_result: dict[str, Any] = {}
    write_error = ""
    schema_seed_write_executed = False
    if not confirm_schema_seed:
        status = "backtest_results_schema_seed_blocked_confirmation_required"
    elif not dependency.get("available"):
        status = "backtest_results_schema_seed_dependency_missing"
    else:
        try:
            import pandas as pd

            seed_frame = pd.DataFrame({column: pd.Series(dtype="string") for column in required_columns})
            write_result = parquet_store.write_dataset(seed_frame, root=PARQUET_ROOT, name=dataset)
            schema_seed_write_executed = write_result.get("status") == "written"
        except Exception as exc:
            write_error = _safe_error_message(exc)
            schema_seed_write_executed = False
        if schema_seed_write_executed:
            status = "backtest_results_schema_seed_written_validation_pending"
        else:
            status = str(write_result.get("status") or "backtest_results_schema_seed_write_failed")
    post_seed_schema_metadata = parquet_store.dataset_schema_metadata(root=PARQUET_ROOT, name=dataset)
    physical_columns = [str(column) for column in post_seed_schema_metadata.get("columns") or []]
    missing_required_columns = [column for column in required_columns if column not in physical_columns]
    post_seed_schema_validated = (
        post_seed_schema_metadata.get("status") == "ready"
        and not missing_required_columns
        and post_seed_schema_metadata.get("schema_read_done") is True
    )
    if schema_seed_write_executed and post_seed_schema_validated:
        status = "backtest_results_schema_seed_ready_for_schema_acceptance"
    elif schema_seed_write_executed:
        status = "backtest_results_schema_seed_written_validation_blocked"
    row_count_written = int(write_result.get("row_count") or 0) if schema_seed_write_executed else 0
    schema_seed_ready = status == "backtest_results_schema_seed_ready_for_schema_acceptance"
    return {
        "schema_version": "command_center_3_storage_backtest_results_schema_seed.v1",
        "packet_key": BACKTEST_RESULTS_SCHEMA_SEED_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_schema_seed",
        "scope": "local_backtest_results_zero_row_schema_seed_before_storage_acceptance",
        "target_dataset": dataset,
        "target_schema_version": contract.get("schema_version"),
        "dataset_path": _path_label(dataset_path),
        "confirm_schema_seed": confirm_schema_seed,
        "schema_seed_ready_for_schema_acceptance": schema_seed_ready,
        "local_schema_seed_ready": schema_seed_ready,
        "schema_seed_write_executed": schema_seed_write_executed,
        "schema_seed_written_on_post": schema_seed_write_executed,
        "schema_seed_written_on_get": False,
        "schema_seed_writes_parquet": schema_seed_write_executed,
        "writes_only_ignored_local_parquet": True,
        "writes_backtest_result_rows": False,
        "mock_backtest_result_written": False,
        "row_count_written": row_count_written,
        "expected_row_count_written": 0,
        "required_columns": required_columns,
        "physical_columns": physical_columns,
        "missing_required_columns": missing_required_columns,
        "missing_required_column_count": len(missing_required_columns),
        "post_seed_schema_metadata": {
            **dict(post_seed_schema_metadata),
            "path": _path_label(Path(str(post_seed_schema_metadata.get("path") or dataset_path))),
        },
        "post_seed_schema_validated": post_seed_schema_validated,
        "post_seed_reads_row_payloads": False,
        "cache_get_writes_files": False,
        "post_task_writes_files": schema_seed_write_executed,
        "post_task_writes_parquet": schema_seed_write_executed,
        "post_task_reads_row_payloads": False,
        "post_task_reads_env_files": False,
        "writes_manifest": False,
        "manifest_write_executed": False,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "production_storage_complete": False,
        "allowed_next_step": "POST /api/storage/schema-validation/acceptance" if schema_seed_ready else "",
        "manual_schema_acceptance_required_after_seed": schema_seed_ready,
        "request_params_safe": {
            "source": payload_safe.get("source") or "storage_page_button",
            "target_dataset": dataset,
            "confirm_schema_seed": confirm_schema_seed,
            "external_sources_allowed": False,
            "write_backtest_rows_allowed": False,
            "write_parquet_schema_seed_allowed": confirm_schema_seed,
        },
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "contains_secret": False,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_backtest_results_schema_seed",
            endpoint="POST /api/storage/backtest-results/schema-seed",
            status=status,
            dataset=dataset,
            row_count=row_count_written,
            path=_path_label(dataset_path),
        ),
        "warnings": [
            "POST /api/storage/backtest-results/schema-seed 只在确认后写入 ignored 本地 Parquet 空 schema；不会写入任何回测结果行。",
            "backtest_results schema seed 不调用 Tushare、DeepSeek、GitHub，不执行真实交易，不修改 strategy action，也不代表生产 storage 完成。",
        ],
        **({"dependency": dependency} if not dependency.get("available") else {}),
        **({"write_result": {**write_result, "path": _path_label(Path(str(write_result.get("path") or dataset_path)))}} if write_result else {}),
        **({"error_message_safe": write_error} if write_error else {}),
    }


def run_storage_backtest_results_schema_seed_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "target_dataset": "backtest_results",
        "confirm_schema_seed": payload_map.get("confirm_schema_seed") is True,
        "external_sources_allowed": False,
        "write_backtest_rows_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_backtest_results_schema_seed",
        output_packet_key=BACKTEST_RESULTS_SCHEMA_SEED_PACKET_KEY,
        payload=task_payload,
        current_step="storage_backtest_results_schema_seed_queued",
        warnings=[
            "backtest_results schema seed 只写 ignored 本地 Parquet 空 schema；不会写 mock 回测行、不会读取凭据、不会调用外部源。",
            "本任务只解除 schema metadata 验收前的本地 dataset 缺口，不执行 schema migration、partition、compaction、TTL、manifest 或生产 promotion。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="writing_backtest_results_zero_row_schema_seed",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_backtest_results_schema_seed_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(BACKTEST_RESULTS_SCHEMA_SEED_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_backtest_results_schema_seed_packet_persist_failed",
            error_message_safe="storage_backtest_results_schema_seed_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_backtest_results_schema_seed_packet_failed_no_external_call",
        ) or task
    ready = packet["schema_seed_ready_for_schema_acceptance"] is True
    return task_service.update_task_status(
        task["task_id"],
        status="success" if ready else "failed",
        progress=1.0,
        current_step="storage_backtest_results_schema_seed_completed" if ready else "storage_backtest_results_schema_seed_blocked",
        error_message_safe=None if ready else str(packet.get("status") or "backtest_results_schema_seed_blocked"),
        call_ledger=packet["call_ledger"],
        warning="storage_backtest_results_schema_seed_completed_local_only"
        if ready
        else "storage_backtest_results_schema_seed_blocked_no_provider_no_trade",
    ) or task


def storage_schema_validation_acceptance_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    dry_run = storage_schema_validation_dry_run_packet(task_id=task_id, payload_safe=payload_safe)
    rows = []
    for row in dry_run["rows"]:
        accepted = row.get("validation_status") == "schema_validated" and row.get("validation_passed") is True
        rows.append(
            {
                **row,
                "acceptance_status": "accepted_physical_schema" if accepted else "acceptance_blocked",
                "physical_schema_acceptance_done": bool(row.get("physical_validation_done")),
                "physical_schema_acceptance_passed": bool(accepted),
                "accepted_for_manifest_promotion": bool(accepted),
                "accepted_for_partition_migration": bool(accepted),
                "acceptance_reads_row_payloads": False,
                "acceptance_writes_parquet": False,
                "schema_migration_executed": False,
                "production_storage_complete": False,
            }
        )
    accepted_count = sum(1 for row in rows if row.get("physical_schema_acceptance_passed"))
    blocked_count = len(rows) - accepted_count
    status = "schema_acceptance_passed_all_local_datasets" if accepted_count == len(rows) else "schema_acceptance_partial_or_blocked"
    return {
        "schema_version": "command_center_3_storage_schema_validation_acceptance.v1",
        "packet_key": SCHEMA_VALIDATION_ACCEPTANCE_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_schema_metadata_acceptance",
        "scope": "physical_schema_metadata_acceptance_before_migration",
        "dataset_count": len(rows),
        "accepted_dataset_count": accepted_count,
        "blocked_dataset_count": blocked_count,
        "missing_dataset_count": int(dry_run.get("missing_dataset_count") or 0),
        "schema_mismatch_count": int(dry_run.get("schema_mismatch_count") or 0),
        "read_failed_count": int(dry_run.get("read_failed_count") or 0),
        "dependency_missing_count": int(dry_run.get("dependency_missing_count") or 0),
        "physical_validation_done_count": int(dry_run.get("physical_validation_done_count") or 0),
        "status_counts": _count_values(row.get("acceptance_status") for row in rows),
        "rows": rows,
        "source_dry_run_packet_key": SCHEMA_VALIDATION_DRY_RUN_PACKET_KEY,
        "source_dry_run_status": dry_run.get("status"),
        "request_params_safe": {
            "source": (payload_safe or {}).get("source") or "storage_page_button",
            "acceptance": True,
            "external_sources_allowed": False,
            "write_parquet_allowed": False,
        },
        "cache_get_writes_files": False,
        "post_acceptance_writes_parquet": False,
        "post_acceptance_reads_row_payloads": False,
        "post_acceptance_reads_env_files": False,
        "schema_migration_executed": False,
        "production_storage_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_schema_validation_acceptance",
            endpoint="POST /api/storage/schema-validation/acceptance",
            status=status,
            row_count=len(rows),
        ),
        "warnings": [
            "POST /api/storage/schema-validation/acceptance 只验收本地 Parquet schema metadata；不会读取行 payload。",
            "schema validation acceptance 不写 Parquet、不执行 migration、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }


def run_storage_schema_validation_acceptance_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "acceptance": True,
        "external_sources_allowed": False,
        "write_parquet_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_schema_validation_acceptance",
        output_packet_key=SCHEMA_VALIDATION_ACCEPTANCE_PACKET_KEY,
        payload=task_payload,
        current_step="storage_schema_validation_acceptance_queued",
        warnings=[
            "storage schema validation acceptance 只读取本地 Parquet schema metadata；不会读取行 payload、不会写 Parquet、不会调用外部源。",
            "本任务只确认本地物理 schema metadata 验收结果；不执行 schema migration、不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="accepting_storage_schema_metadata",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_schema_validation_acceptance_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(SCHEMA_VALIDATION_ACCEPTANCE_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_schema_validation_acceptance_storage_write_failed",
            error_message_safe="storage_schema_validation_acceptance_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_schema_validation_acceptance_failed_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="storage_schema_validation_acceptance_completed",
        call_ledger=packet["call_ledger"],
        warning="storage_schema_validation_acceptance_completed_no_write_no_external_call",
    ) or task


def _read_storage_meta_packet_no_init(packet_key: str) -> tuple[Any, str]:
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


def storage_backtest_results_schema_seed_evidence() -> dict[str, Any]:
    packet, read_status = _read_storage_meta_packet_no_init(BACKTEST_RESULTS_SCHEMA_SEED_PACKET_KEY)
    packet_map = packet if isinstance(packet, Mapping) else {}
    if read_status == "packet_present" and packet_map:
        return dict(packet_map)
    status = f"backtest_results_schema_seed_{read_status}"
    return {
        "schema_version": "command_center_3_storage_backtest_results_schema_seed.v1",
        "packet_key": BACKTEST_RESULTS_SCHEMA_SEED_PACKET_KEY,
        "task_id": "",
        "status": status,
        "mode": "cache_only_latest_schema_seed_evidence",
        "scope": "read_latest_button_gated_backtest_results_schema_seed_packet",
        "target_dataset": "backtest_results",
        "target_schema_version": DATASET_SCHEMA_CONTRACTS["backtest_results"]["schema_version"],
        "confirm_schema_seed": False,
        "schema_seed_ready_for_schema_acceptance": False,
        "local_schema_seed_ready": False,
        "schema_seed_write_executed": False,
        "schema_seed_written_on_post": False,
        "schema_seed_written_on_get": False,
        "schema_seed_writes_parquet": False,
        "writes_only_ignored_local_parquet": True,
        "writes_backtest_result_rows": False,
        "mock_backtest_result_written": False,
        "row_count_written": 0,
        "expected_row_count_written": 0,
        "required_columns": list(DATASET_SCHEMA_CONTRACTS["backtest_results"]["required_columns"]),
        "physical_columns": [],
        "missing_required_columns": list(DATASET_SCHEMA_CONTRACTS["backtest_results"]["required_columns"]),
        "missing_required_column_count": len(DATASET_SCHEMA_CONTRACTS["backtest_results"]["required_columns"]),
        "post_seed_schema_validated": False,
        "post_seed_reads_row_payloads": False,
        "cache_get_writes_files": False,
        "post_task_writes_files": False,
        "post_task_writes_parquet": False,
        "post_task_reads_row_payloads": False,
        "post_task_reads_env_files": False,
        "writes_manifest": False,
        "manifest_write_executed": False,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "production_storage_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "contains_secret": False,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_backtest_results_schema_seed_evidence",
            endpoint="GET /api/storage",
            status=status,
            dataset="backtest_results",
            row_count=0,
            path=_path_label(parquet_store.dataset_path(root=PARQUET_ROOT, name="backtest_results")),
        ),
        "warnings": [
            "backtest_results schema seed evidence 只读取已存在的本地 SQLite packet；meta 不存在时不会创建文件。",
            "该 evidence 不写 Parquet、不执行 migration、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }


def storage_schema_validation_acceptance_evidence_audit() -> dict[str, Any]:
    packet, read_status = _read_storage_meta_packet_no_init(SCHEMA_VALIDATION_ACCEPTANCE_PACKET_KEY)
    packet_map = packet if isinstance(packet, Mapping) else {}
    packet_present = read_status == "packet_present" and bool(packet_map)
    rows = [dict(row) for row in packet_map.get("rows") or [] if isinstance(row, Mapping)] if packet_present else []
    rows_by_dataset = {str(row.get("dataset") or ""): row for row in rows}
    accepted_datasets = [
        dataset
        for dataset in CANONICAL_PARQUET_DATASETS
        if rows_by_dataset.get(dataset, {}).get("physical_schema_acceptance_passed") is True
    ]
    missing_datasets = [dataset for dataset in CANONICAL_PARQUET_DATASETS if dataset not in rows_by_dataset]
    blocked_datasets = [dataset for dataset in CANONICAL_PARQUET_DATASETS if dataset not in accepted_datasets]
    accepted_count = len(accepted_datasets)
    dataset_count = len(CANONICAL_PARQUET_DATASETS)
    try:
        source_packet_dataset_count = int(packet_map.get("dataset_count") or len(rows) or 0)
    except Exception:
        source_packet_dataset_count = len(rows)
    all_accepted = (
        packet_present
        and accepted_count == dataset_count
        and str(packet_map.get("status")) == "schema_acceptance_passed_all_local_datasets"
    )
    if not packet_present:
        status = f"schema_acceptance_evidence_{read_status}"
    elif all_accepted:
        status = "schema_acceptance_evidence_passed_all_local_datasets"
    else:
        status = "schema_acceptance_evidence_partial_or_blocked"
    return {
        "schema_version": "command_center_3_storage_schema_validation_acceptance_evidence.v1",
        "packet_key": "command_center_3_storage_schema_validation_acceptance_evidence_audit",
        "status": status,
        "mode": "cache_only_latest_schema_acceptance_evidence",
        "scope": "read_latest_button_gated_schema_acceptance_packet",
        "source_packet_key": SCHEMA_VALIDATION_ACCEPTANCE_PACKET_KEY,
        "source_packet_present": packet_present,
        "source_packet_read_status": read_status,
        "source_packet_status": packet_map.get("status"),
        "source_packet_task_id": str(packet_map.get("task_id") or ""),
        "dataset_count": dataset_count,
        "source_packet_dataset_count": source_packet_dataset_count,
        "accepted_dataset_count": accepted_count,
        "blocked_dataset_count": len(blocked_datasets),
        "missing_dataset_count": len(missing_datasets),
        "accepted_datasets": accepted_datasets,
        "blocked_datasets": blocked_datasets,
        "missing_datasets": missing_datasets,
        "status_counts": _count_values(row.get("acceptance_status") for row in rows),
        "rows": rows,
        "physical_schema_validation_done": all_accepted,
        "physical_schema_validation_done_count": accepted_count,
        "schema_acceptance_passed_all": all_accepted,
        "cache_get_writes_files": False,
        "cache_get_reads_row_payloads": False,
        "cache_get_reads_env_files": False,
        "post_acceptance_writes_parquet": False,
        "schema_migration_executed": False,
        "production_storage_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_schema_validation_acceptance_evidence",
            endpoint="GET /api/storage",
            status=status,
            row_count=len(rows),
        ),
        "warnings": [
            "schema acceptance evidence audit 只读取已存在的本地 SQLite packet；meta 不存在时不会创建文件。",
            "该 audit 不写 Parquet、不执行 migration、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }


def _schema_migration_execution_row(
    dataset: str,
    *,
    acceptance_row: Mapping[str, Any] | None,
    manifest_row: Mapping[str, Any] | None,
    confirm_schema_migration_execution: bool,
) -> dict[str, Any]:
    contract = _schema_contract(dataset)
    acceptance_row = dict(acceptance_row or {})
    manifest_row = dict(manifest_row or {})
    physical_passed = acceptance_row.get("physical_schema_acceptance_passed") is True
    manifest_passed = manifest_row.get("manifest_validation_passed") is True
    ready = bool(confirm_schema_migration_execution and physical_passed and manifest_passed)
    if not confirm_schema_migration_execution:
        status = "schema_migration_confirmation_required"
    elif not physical_passed:
        status = "schema_migration_blocked_physical_schema_acceptance"
    elif not manifest_passed:
        status = "schema_migration_blocked_manifest_validation"
    else:
        status = "schema_migration_noop_verified"
    return {
        "dataset": dataset,
        "status": status,
        "migration_execution_status": status,
        "current_schema_version": contract.get("schema_version"),
        "target_schema_version": contract.get("schema_version"),
        "schema_version_change_detected": False,
        "physical_schema_acceptance_passed": physical_passed,
        "manifest_validation_passed": manifest_passed,
        "schema_migration_ready_for_execution": bool(physical_passed and manifest_passed),
        "schema_migration_executed": ready,
        "schema_migration_noop_verified": ready,
        "schema_migration_rewrite_executed": False,
        "rewrite_required": False,
        "writes_parquet": False,
        "writes_manifest": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "cache_get_writes_files": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "production_storage_complete": False,
    }


def storage_schema_migration_execution_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload_safe = payload_safe or {}
    confirm = payload_safe.get("confirm_schema_migration_execution") is True
    schema_acceptance = storage_schema_validation_acceptance_evidence_audit()
    manifest_packet, manifest_read_status = _read_storage_meta_packet_no_init(DATASET_VERSION_MANIFEST_VALIDATE_PACKET_KEY)
    manifest_map = manifest_packet if isinstance(manifest_packet, Mapping) else {}
    acceptance_rows = {
        str(row.get("dataset") or ""): row
        for row in schema_acceptance.get("rows") or []
        if isinstance(row, Mapping)
    }
    manifest_rows = {
        str(row.get("dataset") or ""): row
        for row in manifest_map.get("rows") or []
        if isinstance(row, Mapping)
    }
    rows = [
        _schema_migration_execution_row(
            dataset,
            acceptance_row=acceptance_rows.get(dataset),
            manifest_row=manifest_rows.get(dataset),
            confirm_schema_migration_execution=confirm,
        )
        for dataset in CANONICAL_PARQUET_DATASETS
    ]
    dataset_count = len(rows)
    executed_count = sum(1 for row in rows if row.get("schema_migration_executed"))
    physical_ready_count = sum(1 for row in rows if row.get("physical_schema_acceptance_passed"))
    manifest_ready_count = sum(1 for row in rows if row.get("manifest_validation_passed"))
    if not confirm:
        status = "schema_migration_execution_blocked_confirmation_required"
    elif physical_ready_count < dataset_count:
        status = "schema_migration_execution_blocked_physical_schema_acceptance"
    elif manifest_ready_count < dataset_count:
        status = "schema_migration_execution_blocked_manifest_validation"
    else:
        status = "schema_migration_execution_completed_noop_verified"
    local_ready = status == "schema_migration_execution_completed_noop_verified"
    return {
        "schema_version": "command_center_3_storage_schema_migration_execution.v1",
        "packet_key": SCHEMA_MIGRATION_EXECUTION_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_schema_migration_execution",
        "scope": "schema_migration_noop_verification_after_schema_acceptance_and_manifest_validation",
        "ltg": "LTG-05",
        "dataset_count": dataset_count,
        "schema_migration_executed_count": executed_count if local_ready else 0,
        "schema_migration_noop_verified_count": executed_count if local_ready else 0,
        "physical_schema_acceptance_ready_count": physical_ready_count,
        "manifest_validation_ready_count": manifest_ready_count,
        "blocked_dataset_count": dataset_count - executed_count,
        "rows": rows,
        "status_counts": _count_values(row.get("migration_execution_status") for row in rows),
        "confirm_schema_migration_execution": confirm,
        "local_schema_migration_execution_ready": local_ready,
        "schema_migration_executed": local_ready,
        "schema_migration_noop_verified": local_ready,
        "schema_migration_rewrite_executed": False,
        "physical_schema_validation_done": physical_ready_count == dataset_count,
        "dataset_version_manifest_validated": manifest_ready_count == dataset_count,
        "source_schema_acceptance_packet_key": SCHEMA_VALIDATION_ACCEPTANCE_PACKET_KEY,
        "source_schema_acceptance_status": schema_acceptance.get("status"),
        "source_manifest_validate_packet_key": DATASET_VERSION_MANIFEST_VALIDATE_PACKET_KEY,
        "source_manifest_validate_read_status": manifest_read_status,
        "source_manifest_validate_status": manifest_map.get("status") or "packet_missing",
        "request_params_safe": {
            "source": payload_safe.get("source") or "storage_page_button",
            "confirm_schema_migration_execution": confirm,
            "external_sources_allowed": False,
            "write_parquet_allowed": False,
            "write_manifest_allowed": False,
            "read_row_payloads_allowed": False,
        },
        "post_task_writes_sqlite_packet": True,
        "post_task_writes_parquet": False,
        "post_task_writes_manifest": False,
        "post_task_reads_row_payloads": False,
        "post_task_reads_env_files": False,
        "cache_get_writes_files": False,
        "cache_get_reads_row_payloads": False,
        "cache_get_reads_env_files": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "contains_secret": False,
        "production_storage_complete": False,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_schema_migration_execution",
            endpoint="POST /api/storage/schema-migration/execute",
            status=status,
            row_count=dataset_count,
        ),
        "warnings": [
            "schema migration execution 只写入本地 SQLite 证据；当前实现为 no-op verified，不重写 Parquet、不写 manifest。",
            "该任务需要显式确认，不调用 Tushare、DeepSeek、GitHub，不修改 strategy action，不执行真实交易，也不代表 production storage 完成。",
        ],
    }


def storage_schema_migration_execution_evidence() -> dict[str, Any]:
    packet, read_status = _read_storage_meta_packet_no_init(SCHEMA_MIGRATION_EXECUTION_PACKET_KEY)
    if read_status == "packet_present" and isinstance(packet, Mapping):
        evidence = dict(packet)
        evidence["read_status"] = read_status
        evidence.setdefault("schema_migration_executed", False)
        evidence.setdefault("schema_migration_rewrite_executed", False)
        evidence.setdefault("production_storage_complete", False)
        evidence.setdefault("external_calls_triggered", False)
        evidence.setdefault("tushare_called", False)
        evidence.setdefault("deepseek_called", False)
        evidence.setdefault("github_called", False)
        evidence.setdefault("does_not_execute_trades", True)
        evidence.setdefault("does_not_modify_strategy_action", True)
        evidence.setdefault("contains_secret", False)
        return evidence
    status = f"schema_migration_execution_{read_status}"
    return {
        "schema_version": "command_center_3_storage_schema_migration_execution.v1",
        "packet_key": SCHEMA_MIGRATION_EXECUTION_PACKET_KEY,
        "task_id": "",
        "status": status,
        "mode": "cache_only_latest_schema_migration_execution_evidence",
        "scope": "read_latest_button_gated_schema_migration_execution_packet",
        "dataset_count": len(CANONICAL_PARQUET_DATASETS),
        "schema_migration_executed_count": 0,
        "schema_migration_noop_verified_count": 0,
        "rows": [],
        "schema_migration_executed": False,
        "schema_migration_rewrite_executed": False,
        "post_task_writes_parquet": False,
        "post_task_reads_row_payloads": False,
        "cache_get_writes_files": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "contains_secret": False,
        "production_storage_complete": False,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_schema_migration_execution_evidence",
            endpoint="GET /api/storage",
            status=status,
            row_count=0,
        ),
        "warnings": [
            "schema migration execution evidence 只读取已存在的本地 SQLite packet；meta 不存在时不会创建文件。",
            "该 evidence 不写 Parquet、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }


def run_storage_schema_migration_execution_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "confirm_schema_migration_execution": payload_map.get("confirm_schema_migration_execution") is True,
        "external_sources_allowed": False,
        "write_parquet_allowed": False,
        "write_manifest_allowed": False,
        "read_row_payloads_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_schema_migration_execution",
        output_packet_key=SCHEMA_MIGRATION_EXECUTION_PACKET_KEY,
        payload=task_payload,
        current_step="storage_schema_migration_execution_queued",
        warnings=[
            "storage schema migration execution 是显式确认的本地 no-op verification；只写 SQLite evidence，不重写 Parquet。",
            "本任务不调用外部源、不修改 strategy action、不执行真实交易，也不代表 production storage 完成。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="verifying_storage_schema_migration_noop_scope",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_schema_migration_execution_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(SCHEMA_MIGRATION_EXECUTION_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_schema_migration_execution_packet_persist_failed",
            error_message_safe="storage_schema_migration_execution_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_schema_migration_execution_failed_no_external_call",
        ) or task
    success = packet.get("schema_migration_executed") is True
    return task_service.update_task_status(
        task["task_id"],
        status="success" if success else "failed",
        progress=1.0,
        current_step=str(packet.get("status") or "storage_schema_migration_execution_recorded"),
        error_message_safe=None if success else str(packet.get("status") or "storage_schema_migration_execution_blocked"),
        call_ledger=packet["call_ledger"],
        warning="storage_schema_migration_execution_noop_verified_no_parquet_no_external_call"
        if success
        else "storage_schema_migration_execution_blocked_no_parquet_no_external_call",
    ) or task


def _partition_migration_dry_run_row(dataset: str) -> dict[str, Any]:
    metadata = parquet_store.dataset_metadata(root=PARQUET_ROOT, name=dataset)
    partition_plan = _partition_plan(dataset)
    schema_validation = _schema_validation_row(dataset)
    partition_columns = [str(column) for column in (partition_plan.get("recommended_partition_columns") or [])]
    physical_columns = [str(column) for column in (schema_validation.get("physical_columns") or [])]
    missing_partition_columns = [column for column in partition_columns if column not in physical_columns]
    if metadata.get("status") == "missing":
        dry_run_status = "missing_dataset"
    elif schema_validation.get("validation_status") != "schema_validated":
        dry_run_status = "blocked_schema_validation"
    elif missing_partition_columns:
        dry_run_status = "blocked_missing_partition_columns"
    elif not partition_columns:
        dry_run_status = "partition_contract_missing"
    else:
        dry_run_status = "ready_for_manual_partition_migration"
    return {
        "dataset": dataset,
        "status": dry_run_status,
        "partition_migration_status": dry_run_status,
        "partition_migration_metadata_validation_done": dry_run_status == "ready_for_manual_partition_migration",
        "schema_validation_status": schema_validation.get("validation_status"),
        "schema_version": schema_validation.get("schema_version"),
        "source_parquet_status": metadata.get("status", "missing"),
        "source_parquet_path": _path_label(Path(str(metadata.get("path") or parquet_store.dataset_path(root=PARQUET_ROOT, name=dataset)))),
        "target_partitioned_path": _path_label(parquet_store.partitioned_dataset_path(root=PARQUET_ROOT, name=dataset)),
        "partition_columns": partition_columns,
        "missing_partition_columns": missing_partition_columns,
        "physical_columns": physical_columns,
        "row_count_metadata": schema_validation.get("row_count_metadata"),
        "physical_schema_validation_done": bool(schema_validation.get("physical_validation_done")),
        "partition_writer": partition_plan.get("partition_writer"),
        "partition_migration_ready": dry_run_status == "ready_for_manual_partition_migration",
        "partition_migration_executed": False,
        "production_storage_complete": False,
        "would_write_partitioned_dataset": False,
        "post_dry_run_writes_parquet": False,
        "post_dry_run_reads_row_payloads": False,
        "cache_get_writes_files": False,
        "contains_secret": False,
        "manual_partition_migration_task_required": True,
        "manual_compaction_required_after_migration": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def storage_partition_migration_dry_run_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [_partition_migration_dry_run_row(dataset) for dataset in CANONICAL_PARQUET_DATASETS]
    status_counts = _count_values(row.get("partition_migration_status") for row in rows)
    ready_count = sum(1 for row in rows if row.get("partition_migration_ready"))
    metadata_validated_count = sum(1 for row in rows if row.get("partition_migration_metadata_validation_done"))
    metadata_validation_done = metadata_validated_count == len(rows)
    packet = {
        "schema_version": "command_center_3_storage_partition_migration_dry_run.v1",
        "packet_key": PARTITION_MIGRATION_DRY_RUN_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": "dry_run_completed",
        "mode": "dry_run",
        "scope": "partition_migration_plan_before_write",
        "dataset_count": len(rows),
        "partition_migration_ready_count": ready_count,
        "partition_migration_metadata_validated_count": metadata_validated_count,
        "partition_migration_metadata_validation_done": metadata_validation_done,
        "partition_migration_blocked_count": len(rows) - ready_count,
        "missing_dataset_count": status_counts.get("missing_dataset", 0),
        "blocked_schema_validation_count": status_counts.get("blocked_schema_validation", 0),
        "blocked_missing_partition_column_count": status_counts.get("blocked_missing_partition_columns", 0),
        "partition_contract_missing_count": status_counts.get("partition_contract_missing", 0),
        "partition_migration_executed_count": 0,
        "status_counts": status_counts,
        "rows": rows,
        "request_params_safe": {
            "source": (payload_safe or {}).get("source") or "storage_page_button",
            "dry_run": True,
            "external_sources_allowed": False,
            "write_parquet_allowed": False,
            "partition_migration_allowed": False,
        },
        "cache_get_writes_files": False,
        "post_dry_run_writes_parquet": False,
        "post_dry_run_reads_row_payloads": False,
        "post_dry_run_reads_env_files": False,
        "partition_migration_executed": False,
        "production_storage_complete": False,
        "contains_secret": False,
        "manual_partition_migration_task_required": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_partition_migration_dry_run",
            endpoint="POST /api/storage/partition-migration/dry-run",
            status="dry_run_completed",
            row_count=len(rows),
        ),
        "warnings": [
            "POST /api/storage/partition-migration/dry-run 只生成本地分区迁移计划；不会写 partitioned Parquet。",
            "partition migration dry-run 不读取行 payload、不执行迁移、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }
    return packet


def run_storage_partition_migration_dry_run_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "dry_run": True,
        "external_sources_allowed": False,
        "write_parquet_allowed": False,
        "partition_migration_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_partition_migration_dry_run",
        output_packet_key=PARTITION_MIGRATION_DRY_RUN_PACKET_KEY,
        payload=task_payload,
        current_step="storage_partition_migration_dry_run_queued",
        warnings=[
            "storage partition migration dry-run 只读取本地 Parquet metadata/schema；不会读取行 payload、不会写 Parquet、不会调用外部源。",
            "任何真实 partition migration 必须在 dry-run 审阅后另行手动确认；本任务不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="building_storage_partition_migration_plan",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_partition_migration_dry_run_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PARTITION_MIGRATION_DRY_RUN_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_partition_migration_dry_run_storage_write_failed",
            error_message_safe="storage_partition_migration_dry_run_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_partition_migration_dry_run_failed_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="storage_partition_migration_dry_run_completed",
        call_ledger=packet["call_ledger"],
        warning="storage_partition_migration_dry_run_completed_no_write_no_external_call",
    ) or task


def _partition_migration_tree_sha256(path: Path) -> str:
    """Hash a partitioned dataset without depending on filesystem mtimes."""
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
        return digest.hexdigest()
    if not path.is_dir():
        return ""
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        with child.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _partition_migration_scope_hash(rows: list[Mapping[str, Any]]) -> str:
    material = []
    for row in rows:
        dataset = str(row.get("dataset") or "")
        source = PROJECT_ROOT / str(row.get("source_parquet_path") or "")
        material.append(
            {
                "dataset": dataset,
                "source_sha256": _partition_migration_tree_sha256(source),
                "schema_version": str(row.get("schema_version") or ""),
                "partition_columns": [str(item) for item in row.get("partition_columns") or []],
                "row_count_metadata": row.get("row_count_metadata"),
            }
        )
    return _json_sha256({"schema_version": "storage_partition_migration_scope.v1", "rows": material})


def _partition_migration_execution_row(
    dataset: str,
    *,
    status: str,
    source_path: Path,
    target_path: Path,
    partition_columns: list[str],
    source_sha256: str = "",
    target_sha256: str = "",
    source_row_count: int = 0,
    target_row_count: int = 0,
    schema_columns_match: bool = False,
    row_count_match: bool = False,
    error_message_safe: str = "",
) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "status": status,
        "source_parquet_path": _path_label(source_path),
        "target_partitioned_path": _path_label(target_path),
        "partition_columns": list(partition_columns),
        "source_sha256": source_sha256,
        "target_tree_sha256": target_sha256,
        "source_row_count": int(source_row_count),
        "target_row_count": int(target_row_count),
        "schema_columns_match": bool(schema_columns_match),
        "row_count_match": bool(row_count_match),
        "partition_migration_executed": status == "partition_migration_executed",
        "dataset_version_migration_executed": status == "partition_migration_executed",
        "physical_dataset_version_validated": status == "partition_migration_executed",
        "reads_row_payloads": status == "partition_migration_executed",
        "writes_parquet": status == "partition_migration_executed",
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        **({"error_message_safe": error_message_safe} if error_message_safe else {}),
    }


def _execute_partition_migration(
    *,
    rows: list[Mapping[str, Any]],
    scope_hash: str,
) -> dict[str, Any]:
    """Materialize the reviewed partition plan into ignored local storage.

    The source single-file Parquet datasets are never removed or overwritten. Each
    partitioned dataset is written below a scope-specific staging directory,
    validated, and then moved into its previously absent canonical directory.
    """
    import pandas as pd
    import pyarrow as pa
    import pyarrow.dataset as pa_dataset
    import pyarrow.parquet as pq

    stage_root = PARQUET_ROOT / ".partition_migration_staging" / scope_hash
    stage_root.mkdir(parents=True, exist_ok=True)
    execution_rows: list[dict[str, Any]] = []
    for raw_row in rows:
        row = dict(raw_row)
        dataset = str(row.get("dataset") or "")
        source_path = PROJECT_ROOT / str(row.get("source_parquet_path") or "")
        target_path = PARQUET_ROOT / dataset
        partition_columns = [str(item) for item in row.get("partition_columns") or []]
        if not dataset or not source_path.is_file() or not partition_columns:
            execution_rows.append(
                _partition_migration_execution_row(
                    dataset,
                    status="partition_migration_blocked_source_or_contract",
                    source_path=source_path,
                    target_path=target_path,
                    partition_columns=partition_columns,
                    error_message_safe="source_or_partition_contract_missing",
                )
            )
            continue
        source_sha256 = _partition_migration_tree_sha256(source_path)
        try:
            frame = pd.read_parquet(source_path)
            source_columns = [str(column) for column in frame.columns]
            schema_columns_match = all(column in source_columns for column in partition_columns)
            if not schema_columns_match:
                raise ValueError("partition_columns_missing_from_source")
            source_row_count = int(len(frame))
            if target_path.exists():
                existing_dataset = pa_dataset.dataset(target_path, format="parquet")
                existing_columns = [str(field.name) for field in existing_dataset.schema]
                target_row_count = int(existing_dataset.count_rows())
                target_sha256 = _partition_migration_tree_sha256(target_path)
                existing_schema_match = all(
                    column in existing_columns for column in source_columns if column not in partition_columns
                )
                row_count_match = target_row_count == source_row_count
                if not (existing_schema_match and row_count_match and target_sha256):
                    raise ValueError("canonical_partition_target_readback_mismatch")
                execution_rows.append(
                    _partition_migration_execution_row(
                        dataset,
                        status="partition_migration_executed",
                        source_path=source_path,
                        target_path=target_path,
                        partition_columns=partition_columns,
                        source_sha256=source_sha256,
                        target_sha256=target_sha256,
                        source_row_count=source_row_count,
                        target_row_count=target_row_count,
                        schema_columns_match=schema_columns_match and existing_schema_match,
                        row_count_match=row_count_match,
                    )
                )
                continue
            stage_dataset_root = stage_root
            stage_dataset = stage_dataset_root / dataset
            if stage_dataset.exists():
                shutil.rmtree(stage_dataset)
            if source_row_count == 0:
                import pyarrow as pa
                import pyarrow.parquet as pq

                stage_dataset.mkdir(parents=True, exist_ok=True)
                pq.write_table(
                    pa.Table.from_pandas(frame, preserve_index=False),
                    stage_dataset / "part-0.parquet",
                )
                write_result = {"status": "written", "row_count": 0}
            else:
                write_result = parquet_store.write_partitioned_dataset(
                    frame,
                    root=stage_dataset_root,
                    name=dataset,
                    partition_columns=partition_columns,
                )
            if write_result.get("status") != "written":
                raise ValueError(str(write_result.get("status") or "partition_write_failed"))
            staged_meta = parquet_store.partitioned_dataset_metadata(root=stage_dataset_root, name=dataset)
            target_row_count = int(pa_dataset.dataset(stage_dataset, format="parquet").count_rows())
            row_count_match = target_row_count == source_row_count
            target_sha256 = _partition_migration_tree_sha256(stage_dataset)
            if not row_count_match or not target_sha256 or staged_meta.get("status") != "ready":
                raise ValueError("partition_readback_validation_failed")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            stage_dataset.replace(target_path)
            execution_rows.append(
                _partition_migration_execution_row(
                    dataset,
                    status="partition_migration_executed",
                    source_path=source_path,
                    target_path=target_path,
                    partition_columns=partition_columns,
                    source_sha256=source_sha256,
                    target_sha256=target_sha256,
                    source_row_count=source_row_count,
                    target_row_count=target_row_count,
                    schema_columns_match=schema_columns_match,
                    row_count_match=row_count_match,
                )
            )
        except Exception as exc:
            execution_rows.append(
                _partition_migration_execution_row(
                    dataset,
                    status="partition_migration_failed_safe",
                    source_path=source_path,
                    target_path=target_path,
                    partition_columns=partition_columns,
                    source_sha256=source_sha256,
                    error_message_safe=type(exc).__name__,
                )
            )
    executed_count = sum(1 for row in execution_rows if row.get("partition_migration_executed"))
    complete = executed_count == len(rows) and bool(rows)
    manifest = {
        "schema_version": "storage_partition_migration_execution_manifest.v1",
        "scope_hash": scope_hash,
        "dataset_count": len(rows),
        "executed_count": executed_count,
        "rows": execution_rows,
        "contains_secret": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    if complete:
        _write_json_atomic(PARQUET_ROOT / ".partition_migration_execution.json", manifest)
    return {
        "status": "partition_migration_execution_complete" if complete else "partition_migration_execution_failed_safe",
        "scope_hash": scope_hash,
        "scope_hash_short": scope_hash[:12],
        "dataset_count": len(rows),
        "partition_migration_executed_count": executed_count,
        "dataset_version_migration_executed_count": executed_count,
        "physical_dataset_version_validated_count": executed_count,
        "partition_migration_executed": complete,
        "dataset_version_migration_executed": complete,
        "physical_dataset_version_validated": complete,
        "manifest_path": _path_label(PARQUET_ROOT / ".partition_migration_execution.json") if complete else "",
        "manifest": manifest,
        "rows": execution_rows,
        "reads_row_payloads": complete,
        "writes_parquet": executed_count > 0,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def storage_partition_migration_execution_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload_safe or {}
    dry_run, read_status = _read_storage_meta_packet_no_init(PARTITION_MIGRATION_DRY_RUN_PACKET_KEY)
    dry_run = dict(dry_run) if isinstance(dry_run, Mapping) else {}
    rows = [dict(row) for row in dry_run.get("rows") or [] if isinstance(row, Mapping)]
    scope_hash = _partition_migration_scope_hash(rows) if rows else ""
    requested_scope_hash = str(payload.get("scope_hash") or payload.get("partition_migration_scope_hash") or "")
    approved = payload.get("approved_by_user") is True
    confirmed = payload.get("confirm_partition_migration") is True
    scope_matches = bool(scope_hash and requested_scope_hash == scope_hash)
    plan_ready = bool(
        read_status == "packet_present"
        and dry_run.get("status") == "dry_run_completed"
        and rows
        and all(row.get("partition_migration_ready") is True for row in rows)
    )
    if not approved:
        status = "partition_migration_execution_blocked_user_confirmation_required"
    elif not confirmed:
        status = "partition_migration_execution_blocked_execution_confirmation_required"
    elif not plan_ready:
        status = "partition_migration_execution_blocked_dry_run_not_ready"
    elif not requested_scope_hash:
        status = "partition_migration_execution_blocked_scope_hash_required"
    elif not scope_matches:
        status = "partition_migration_execution_blocked_scope_hash_mismatch"
    else:
        result = _execute_partition_migration(rows=rows, scope_hash=scope_hash)
        status = str(result.get("status") or "partition_migration_execution_failed_safe")
    if "result" not in locals():
        result = {
            "status": status,
            "scope_hash": scope_hash,
            "scope_hash_short": scope_hash[:12],
            "dataset_count": len(rows),
            "partition_migration_executed_count": 0,
            "dataset_version_migration_executed_count": 0,
            "physical_dataset_version_validated_count": 0,
            "partition_migration_executed": False,
            "dataset_version_migration_executed": False,
            "physical_dataset_version_validated": False,
            "rows": [],
            "reads_row_payloads": False,
            "writes_parquet": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    return {
        "schema_version": "command_center_3_storage_partition_migration_execution.v1",
        "packet_key": PARTITION_MIGRATION_EXECUTION_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_partition_migration_execution",
        "scope": "local_partition_migration_execution_no_provider_no_trade",
        "ltg": "LTG-05",
        "approved_by_user": approved,
        "confirm_partition_migration": confirmed,
        "dry_run_read_status": read_status,
        "dry_run_task_id": dry_run.get("task_id"),
        "dry_run_ready": plan_ready,
        "requested_scope_hash": requested_scope_hash,
        "requested_scope_hash_short": requested_scope_hash[:12],
        "scope_hash": scope_hash,
        "scope_hash_short": scope_hash[:12],
        "scope_hash_matches": scope_matches,
        "dataset_count": int(result.get("dataset_count") or len(rows)),
        "partition_migration_executed_count": int(result.get("partition_migration_executed_count") or 0),
        "dataset_version_migration_executed_count": int(result.get("dataset_version_migration_executed_count") or 0),
        "physical_dataset_version_validated_count": int(result.get("physical_dataset_version_validated_count") or 0),
        "partition_migration_executed": result.get("partition_migration_executed") is True,
        "dataset_version_migration_executed": result.get("dataset_version_migration_executed") is True,
        "physical_dataset_version_validated": result.get("physical_dataset_version_validated") is True,
        "manifest_path": result.get("manifest_path") or "",
        "rows": list(result.get("rows") or []),
        "reads_row_payloads": result.get("reads_row_payloads") is True,
        "writes_parquet": result.get("writes_parquet") is True,
        "writes_manifest": bool(result.get("manifest_path")),
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "request_params_safe": {
            "source": payload.get("source") or "storage_page_button",
            "approved_by_user": approved,
            "confirm_partition_migration": confirmed,
            "scope_hash_short": requested_scope_hash[:12],
            "external_sources_allowed": False,
            "delete_allowed": False,
        },
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_partition_migration_execution",
            endpoint="POST /api/storage/partition-migration/execute",
            status=status,
            row_count=int(result.get("partition_migration_executed_count") or 0),
        ),
        "warnings": [
            "该任务仅在显式确认且 scope hash 匹配时读取本地 Parquet 行并写入新的分区目录；源单文件不删除、不覆盖。",
            "不调用 Tushare、DeepSeek、GitHub，不执行真实交易，也不从 GET/cache 触发。",
            "partition execution evidence 不等于 full production storage；TTL/provider 与 promotion 仍独立验收。",
        ],
    }


def storage_partition_migration_execution_evidence() -> dict[str, Any]:
    packet, read_status = _read_storage_meta_packet_no_init(PARTITION_MIGRATION_EXECUTION_PACKET_KEY)
    if read_status != "packet_present" or not isinstance(packet, Mapping):
        return {
            "schema_version": "command_center_3_storage_partition_migration_execution.v1",
            "status": "partition_migration_execution_missing",
            "partition_migration_executed": False,
            "dataset_version_migration_executed": False,
            "physical_dataset_version_validated": False,
            "partition_migration_executed_count": 0,
            "dataset_version_migration_executed_count": 0,
            "physical_dataset_version_validated_count": 0,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "rows": [],
        }
    evidence = dict(packet)
    evidence["read_status"] = read_status
    return evidence


def _compaction_scope_hash(rows: list[Mapping[str, Any]]) -> str:
    material = []
    for row in rows:
        dataset = str(row.get("dataset") or "")
        target = PARQUET_ROOT / dataset
        material.append(
            {
                "dataset": dataset,
                "target_tree_sha256": _partition_migration_tree_sha256(target),
                "schema_version": str(DATASET_SCHEMA_CONTRACTS.get(dataset, {}).get("schema_version") or ""),
                "partition_columns": list(
                    DATASET_SCHEMA_CONTRACTS.get(dataset, {}).get("recommended_partition_columns") or []
                ),
                "row_count": int(row.get("source_row_count") or row.get("size_bytes") or 0),
            }
        )
    return _json_sha256({"schema_version": "storage_compaction_scope.v1", "rows": material})


def _compaction_execution_row(
    dataset: str,
    *,
    status: str,
    target_path: Path,
    partition_columns: list[str],
    source_tree_sha256: str = "",
    target_tree_sha256: str = "",
    source_row_count: int = 0,
    target_row_count: int = 0,
    schema_columns_match: bool = False,
    row_count_match: bool = False,
    error_message_safe: str = "",
) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "status": status,
        "target_partitioned_path": _path_label(target_path),
        "partition_columns": list(partition_columns),
        "source_tree_sha256": source_tree_sha256,
        "target_tree_sha256": target_tree_sha256,
        "source_row_count": int(source_row_count),
        "target_row_count": int(target_row_count),
        "schema_columns_match": bool(schema_columns_match),
        "row_count_match": bool(row_count_match),
        "compaction_executed": status == "physical_compaction_executed",
        "physical_compaction_executed": status == "physical_compaction_executed",
        "reads_row_payloads": status == "physical_compaction_executed",
        "writes_parquet": status == "physical_compaction_executed",
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        **({"error_message_safe": error_message_safe} if error_message_safe else {}),
    }


def _execute_storage_compaction(
    *, rows: list[Mapping[str, Any]], scope_hash: str
) -> dict[str, Any]:
    """Rewrite each existing partitioned dataset into a validated compact target.

    The rewrite is confirm-gated and local-only. A scope-specific staging and
    backup directory makes a failed replacement recoverable without deleting the
    source single-file datasets or invoking any provider/model/trade path.
    """
    import pandas as pd
    import pyarrow as pa
    import pyarrow.dataset as pa_dataset
    import pyarrow.parquet as pq

    stage_root = PARQUET_ROOT / ".compaction_staging" / scope_hash
    stage_root.mkdir(parents=True, exist_ok=True)
    backup_root = stage_root / "backup"
    execution_rows: list[dict[str, Any]] = []
    for raw_row in rows:
        row = dict(raw_row)
        dataset = str(row.get("dataset") or "")
        target_path = PARQUET_ROOT / dataset
        partition_columns = [
            str(item)
            for item in DATASET_SCHEMA_CONTRACTS.get(dataset, {}).get("recommended_partition_columns") or []
        ]
        source_tree_sha256 = _partition_migration_tree_sha256(target_path)
        if not dataset or not target_path.is_dir() or not partition_columns:
            execution_rows.append(
                _compaction_execution_row(
                    dataset,
                    status="compaction_blocked_target_or_contract",
                    target_path=target_path,
                    partition_columns=partition_columns,
                    source_tree_sha256=source_tree_sha256,
                    error_message_safe="target_or_partition_contract_missing",
                )
            )
            continue
        stage_dataset = stage_root / dataset
        backup_dataset = backup_root / dataset
        try:
            try:
                frame = pd.read_parquet(target_path)
            except Exception:
                # A Hive target can contain legacy default-partition fragments
                # with an incompatible inferred partition type. The preserved
                # canonical single-file source is the safe recovery input.
                source_file = PARQUET_ROOT / f"{dataset}.parquet"
                if not source_file.is_file():
                    raise
                frame = pd.read_parquet(source_file)
            source_row_count = int(len(frame))
            source_columns = [str(column) for column in frame.columns]
            if not all(column in source_columns for column in partition_columns):
                raise ValueError("partition_columns_missing_from_target")
            if stage_dataset.exists():
                shutil.rmtree(stage_dataset)
            if source_row_count == 0:
                stage_dataset.mkdir(parents=True, exist_ok=True)
                pq.write_table(
                    pa.Table.from_pandas(frame, preserve_index=False),
                    stage_dataset / "part-0.parquet",
                )
                write_result = {"status": "written", "row_count": 0}
            else:
                write_result = parquet_store.write_partitioned_dataset(
                    frame,
                    root=stage_root,
                    name=dataset,
                    partition_columns=partition_columns,
                )
                if write_result.get("status") != "written":
                    raise ValueError(str(write_result.get("status") or "compaction_write_failed"))
            try:
                compacted = pd.read_parquet(stage_dataset)
                target_row_count = int(len(compacted))
                target_columns = [str(column) for column in compacted.columns]
            except Exception:
                compacted_dataset = pa_dataset.dataset(stage_dataset, format="parquet")
                target_row_count = int(compacted_dataset.count_rows())
                target_columns = [str(field.name) for field in compacted_dataset.schema]
            source_schema_columns = sorted(column for column in source_columns if column not in partition_columns)
            target_schema_columns = sorted(column for column in target_columns if column not in partition_columns)
            schema_columns_match = target_schema_columns == source_schema_columns
            row_count_match = target_row_count == source_row_count
            target_tree_sha256 = _partition_migration_tree_sha256(stage_dataset)
            if not schema_columns_match or not row_count_match or not target_tree_sha256:
                raise ValueError("compaction_readback_validation_failed")
            backup_dataset.parent.mkdir(parents=True, exist_ok=True)
            if backup_dataset.exists():
                shutil.rmtree(backup_dataset)
            target_path.replace(backup_dataset)
            try:
                stage_dataset.replace(target_path)
            except Exception:
                backup_dataset.replace(target_path)
                raise
            execution_rows.append(
                _compaction_execution_row(
                    dataset,
                    status="physical_compaction_executed",
                    target_path=target_path,
                    partition_columns=partition_columns,
                    source_tree_sha256=source_tree_sha256,
                    target_tree_sha256=target_tree_sha256,
                    source_row_count=source_row_count,
                    target_row_count=target_row_count,
                    schema_columns_match=schema_columns_match,
                    row_count_match=row_count_match,
                )
            )
        except Exception as exc:
            execution_rows.append(
                _compaction_execution_row(
                    dataset,
                    status="physical_compaction_failed_safe",
                    target_path=target_path,
                    partition_columns=partition_columns,
                    source_tree_sha256=source_tree_sha256,
                    error_message_safe=type(exc).__name__,
                )
            )
    executed_count = sum(1 for row in execution_rows if row.get("physical_compaction_executed"))
    complete = executed_count == len(rows) and bool(rows)
    manifest = {
        "schema_version": "storage_compaction_execution_manifest.v1",
        "scope_hash": scope_hash,
        "dataset_count": len(rows),
        "executed_count": executed_count,
        "rows": execution_rows,
        "contains_secret": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    if complete:
        _write_json_atomic(PARQUET_ROOT / ".compaction_execution.json", manifest)
    return {
        "status": "physical_compaction_execution_complete" if complete else "physical_compaction_execution_failed_safe",
        "scope_hash": scope_hash,
        "scope_hash_short": scope_hash[:12],
        "dataset_count": len(rows),
        "physical_compaction_executed_count": executed_count,
        "compaction_executed_count": executed_count,
        "physical_compaction_executed": complete,
        "compaction_executed": complete,
        "manifest_path": _path_label(PARQUET_ROOT / ".compaction_execution.json") if complete else "",
        "manifest": manifest,
        "rows": execution_rows,
        "reads_row_payloads": complete,
        "writes_parquet": executed_count > 0,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def storage_compaction_execution_evidence() -> dict[str, Any]:
    packet, read_status = _read_storage_meta_packet_no_init(COMPACTION_EXECUTION_PACKET_KEY)
    if read_status != "packet_present" or not isinstance(packet, Mapping):
        return {
            "schema_version": "command_center_3_storage_compaction_execution.v1",
            "status": "physical_compaction_execution_missing",
            "physical_compaction_executed": False,
            "physical_compaction_executed_count": 0,
            "compaction_executed_count": 0,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "rows": [],
        }
    evidence = dict(packet)
    evidence["read_status"] = read_status
    return evidence


def storage_compaction_execution_packet(
    *, task_id: str | None = None, payload_safe: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    payload = payload_safe or {}
    dry_run, read_status = _read_storage_meta_packet_no_init(COMPACTION_DRY_RUN_PACKET_KEY)
    dry_run = dict(dry_run) if isinstance(dry_run, Mapping) else {}
    rows = [dict(row) for row in dry_run.get("rows") or [] if isinstance(row, Mapping)]
    scope_hash = _compaction_scope_hash(rows) if rows else ""
    requested_scope_hash = str(payload.get("scope_hash") or payload.get("compaction_scope_hash") or "")
    approved = payload.get("approved_by_user") is True
    confirmed = payload.get("confirm_compaction") is True
    scope_matches = bool(scope_hash and requested_scope_hash == scope_hash)
    plan_ready = bool(
        read_status == "packet_present"
        and dry_run.get("status") == "dry_run_completed"
        and rows
        and all(row.get("source_parquet_status") == "ready" for row in rows)
    )
    if not approved:
        status = "physical_compaction_execution_blocked_user_confirmation_required"
    elif not confirmed:
        status = "physical_compaction_execution_blocked_compaction_confirmation_required"
    elif not plan_ready:
        status = "physical_compaction_execution_blocked_dry_run_not_ready"
    elif not scope_matches:
        status = "physical_compaction_execution_blocked_scope_hash_mismatch"
    else:
        result = _execute_storage_compaction(rows=rows, scope_hash=scope_hash)
        status = str(result.get("status") or "physical_compaction_execution_failed_safe")
    result = locals().get("result") if "result" in locals() else {
        "status": status,
        "scope_hash": scope_hash,
        "scope_hash_short": scope_hash[:12],
        "dataset_count": len(rows),
        "physical_compaction_executed_count": 0,
        "compaction_executed_count": 0,
        "physical_compaction_executed": False,
        "compaction_executed": False,
        "manifest_path": "",
        "manifest": {},
        "rows": [],
        "reads_row_payloads": False,
        "writes_parquet": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    return {
        "schema_version": "command_center_3_storage_compaction_execution.v1",
        "packet_key": COMPACTION_EXECUTION_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_compaction_execution",
        "scope": "local_storage_compaction_no_provider_no_trade",
        "ltg": "LTG-05",
        "approved_by_user": approved,
        "confirm_compaction": confirmed,
        "dry_run_read_status": read_status,
        "dry_run_task_id": dry_run.get("task_id"),
        "dry_run_ready": plan_ready,
        "requested_scope_hash": requested_scope_hash,
        "requested_scope_hash_short": requested_scope_hash[:12],
        "scope_hash": scope_hash,
        "scope_hash_short": scope_hash[:12],
        "scope_hash_matches": scope_matches,
        "dataset_count": int(result.get("dataset_count") or len(rows)),
        "physical_compaction_executed_count": int(result.get("physical_compaction_executed_count") or 0),
        "compaction_executed_count": int(result.get("compaction_executed_count") or 0),
        "physical_compaction_executed": result.get("physical_compaction_executed") is True,
        "compaction_executed": result.get("compaction_executed") is True,
        "manifest_path": result.get("manifest_path") or "",
        "manifest": result.get("manifest") or {},
        "rows": result.get("rows") or [],
        "reads_row_payloads": result.get("reads_row_payloads") is True,
        "writes_parquet": result.get("writes_parquet") is True,
        "writes_only_ignored_local_parquet": True,
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_storage_compaction_execution",
                "endpoint": "POST /api/storage/compaction/execute",
                "source_type": "local_partitioned_parquet",
                "external": False,
                "call_status": status,
                "row_count": int(result.get("compaction_executed_count") or 0),
                "writes_parquet": result.get("writes_parquet") is True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [
            "该任务仅在显式确认且 scope hash 匹配时重写本地分区 Parquet；采用 staging/backup 目录并做 schema/行数/tree-hash 回读。",
            "不调用 Tushare、DeepSeek、GitHub，不执行真实交易，也不从 GET/cache 触发。",
            "compaction execution evidence 不等于 TTL/provider refresh 或 full production storage。",
        ],
    }


def run_storage_compaction_execution_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_compaction_execution",
        "approved_by_user": payload_map.get("approved_by_user") is True,
        "confirm_compaction": payload_map.get("confirm_compaction") is True,
        "scope_hash": str(payload_map.get("scope_hash") or payload_map.get("compaction_scope_hash") or ""),
        "external_sources_allowed": False,
        "write_parquet_allowed": True,
        "delete_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_compaction_execution",
        output_packet_key=COMPACTION_EXECUTION_PACKET_KEY,
        payload=task_payload,
        current_step="storage_compaction_execution_queued",
        warnings=[
            "This task may rewrite ignored local partitioned Parquet after dry-run scope and explicit confirmation.",
            "It never refreshes providers, calls models, deletes artifacts, trades, or mutates strategy action.",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    task_service.update_task_status(
        task["task_id"], status="running", progress=0.45, current_step="validating_compaction_scope_before_local_rewrite"
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_compaction_execution_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(COMPACTION_EXECUTION_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"], status="failed", progress=1.0,
            current_step="storage_compaction_execution_packet_persist_failed",
            error_message_safe="storage_compaction_execution_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
        ) or task
    succeeded = packet.get("physical_compaction_executed") is True
    return task_service.update_task_status(
        task["task_id"], status="success" if succeeded else "failed", progress=1.0,
        current_step=str(packet.get("status") or "storage_compaction_execution_finished"),
        error_message_safe=None if succeeded else str(packet.get("status") or "compaction_execution_blocked"),
        call_ledger=packet["call_ledger"],
        warning=("storage_compaction_execution_complete" if succeeded else "compaction_execution_not_executed_or_incomplete"),
    ) or task


def run_storage_partition_migration_execution_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "approved_by_user": payload_map.get("approved_by_user") is True,
        "confirm_partition_migration": payload_map.get("confirm_partition_migration") is True,
        "scope_hash": str(payload_map.get("scope_hash") or payload_map.get("partition_migration_scope_hash") or ""),
        "external_sources_allowed": False,
        "delete_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_partition_migration_execution",
        output_packet_key=PARTITION_MIGRATION_EXECUTION_PACKET_KEY,
        payload=task_payload,
        current_step="storage_partition_migration_execution_queued",
        warnings=[
            "partition migration execution requires explicit confirmation and current dry-run scope hash.",
            "the task writes only ignored local partitioned Parquet; source files remain intact and no external source is called.",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="executing_storage_partition_migration",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_partition_migration_execution_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PARTITION_MIGRATION_EXECUTION_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_partition_migration_execution_packet_persist_failed",
            error_message_safe="storage_partition_migration_execution_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
        ) or task
    successful = packet.get("partition_migration_executed") is True
    return task_service.update_task_status(
        task["task_id"],
        status="success" if successful else "failed",
        progress=1.0,
        current_step=str(packet.get("status") or "partition_migration_execution_recorded"),
        error_message_safe=None if successful else str(packet.get("status") or "partition_migration_execution_blocked"),
        call_ledger=packet["call_ledger"],
        warning="partition_migration_execution_completed_local_no_provider_no_trade"
        if successful
        else "partition_migration_execution_blocked_or_failed_safe_no_provider_no_trade",
    ) or task


def _partition_plan(dataset: str) -> dict[str, Any]:
    contract = _schema_contract(dataset)
    partition_columns = list(contract.get("recommended_partition_columns") or [])
    return {
        "dataset": dataset,
        "status": "contract_ready" if partition_columns else "planned",
        "recommended_partition_columns": partition_columns,
        "physical_partitioning_supported": bool(partition_columns),
        "physical_partitioning_enabled": False,
        "partition_writer": "storage.parquet_store.write_partitioned_dataset" if partition_columns else None,
        "manual_compaction_required": True,
        "auto_partition_on_get": False,
        "external_calls_triggered": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def _compaction_plan(dataset: str, path: Path, metadata: Mapping[str, Any]) -> dict[str, Any]:
    exists = bool(metadata.get("exists"))
    size_bytes = int(metadata.get("size_bytes") or 0)
    if not exists:
        status = "not_applicable_missing"
        reason = "dataset_missing"
        manual_compaction_recommended = False
    elif size_bytes >= DATASET_COMPACTION_SIZE_THRESHOLD_BYTES:
        status = "manual_compaction_recommended"
        reason = "size_exceeds_threshold"
        manual_compaction_recommended = True
    else:
        status = "not_needed"
        reason = "size_within_threshold"
        manual_compaction_recommended = False
    return {
        "dataset": dataset,
        "status": status,
        "reason": reason,
        "size_bytes": size_bytes,
        "threshold_bytes": DATASET_COMPACTION_SIZE_THRESHOLD_BYTES,
        "path": _path_label(path),
        "manual_compaction_recommended": manual_compaction_recommended,
        "manual_compaction_task_required": True,
        "auto_compact_on_get": False,
        "physical_compaction_executed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def _compaction_dry_run_row(dataset: str) -> dict[str, Any]:
    path = parquet_store.dataset_path(root=PARQUET_ROOT, name=dataset)
    metadata = parquet_store.dataset_metadata(root=PARQUET_ROOT, name=dataset)
    compaction_plan = _compaction_plan(dataset, path, metadata)
    plan_status = str(compaction_plan.get("status") or "unknown")
    if plan_status == "manual_compaction_recommended":
        dry_run_status = "ready_for_manual_compaction"
    elif plan_status == "not_needed":
        dry_run_status = "not_needed"
    elif plan_status == "not_applicable_missing":
        dry_run_status = "missing_dataset"
    else:
        dry_run_status = plan_status
    return {
        "dataset": dataset,
        "status": dry_run_status,
        "compaction_dry_run_status": dry_run_status,
        "compaction_plan_status": plan_status,
        "reason": compaction_plan.get("reason"),
        "source_parquet_status": metadata.get("status", "missing"),
        "source_parquet_path": _path_label(path),
        "size_bytes": compaction_plan.get("size_bytes", 0),
        "threshold_bytes": compaction_plan.get("threshold_bytes", DATASET_COMPACTION_SIZE_THRESHOLD_BYTES),
        "manual_compaction_recommended": bool(compaction_plan.get("manual_compaction_recommended")),
        "manual_compaction_task_required": True,
        "compaction_ready": dry_run_status == "ready_for_manual_compaction",
        "physical_compaction_metadata_validation_done": dry_run_status == "not_needed",
        "compaction_executed": False,
        "physical_compaction_executed": False,
        "production_storage_complete": False,
        "would_rewrite_parquet": False,
        "post_dry_run_writes_parquet": False,
        "post_dry_run_reads_row_payloads": False,
        "cache_get_writes_files": False,
        "cache_get_reads_payloads": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }


def storage_compaction_dry_run_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [_compaction_dry_run_row(dataset) for dataset in CANONICAL_PARQUET_DATASETS]
    status_counts = _count_values(row.get("compaction_dry_run_status") for row in rows)
    ready_count = sum(1 for row in rows if row.get("compaction_ready"))
    metadata_validated_count = sum(
        1 for row in rows if row.get("physical_compaction_metadata_validation_done")
    )
    metadata_validation_done = metadata_validated_count == len(rows)
    packet = {
        "schema_version": "command_center_3_storage_compaction_dry_run.v1",
        "packet_key": COMPACTION_DRY_RUN_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": "dry_run_completed",
        "mode": "dry_run",
        "scope": "parquet_compaction_plan_before_rewrite",
        "dataset_count": len(rows),
        "compaction_ready_count": ready_count,
        "physical_compaction_metadata_validated_count": metadata_validated_count,
        "physical_compaction_metadata_validation_done": metadata_validation_done,
        "compaction_not_needed_count": status_counts.get("not_needed", 0),
        "missing_dataset_count": status_counts.get("missing_dataset", 0),
        "compaction_blocked_count": len(rows) - ready_count - status_counts.get("not_needed", 0),
        "compaction_executed_count": 0,
        "status_counts": status_counts,
        "rows": rows,
        "request_params_safe": {
            "source": (payload_safe or {}).get("source") or "storage_page_button",
            "dry_run": True,
            "external_sources_allowed": False,
            "rewrite_parquet_allowed": False,
            "compaction_allowed": False,
        },
        "cache_get_writes_files": False,
        "post_dry_run_writes_parquet": False,
        "post_dry_run_reads_row_payloads": False,
        "post_dry_run_reads_env_files": False,
        "compaction_executed": False,
        "physical_compaction_executed": False,
        "production_storage_complete": False,
        "manual_compaction_task_required": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "contains_secret": False,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_compaction_dry_run",
            endpoint="POST /api/storage/compaction/dry-run",
            status="dry_run_completed",
            row_count=len(rows),
        ),
        "warnings": [
            "POST /api/storage/compaction/dry-run 只生成本地 Parquet compaction 预检清单；不会重写 Parquet。",
            "compaction dry-run 不读取行 payload、不执行物理压缩、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }
    return packet


def run_storage_compaction_dry_run_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "dry_run": True,
        "external_sources_allowed": False,
        "rewrite_parquet_allowed": False,
        "compaction_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_compaction_dry_run",
        output_packet_key=COMPACTION_DRY_RUN_PACKET_KEY,
        payload=task_payload,
        current_step="storage_compaction_dry_run_queued",
        warnings=[
            "storage compaction dry-run 只读取本地 Parquet metadata；不会读取行 payload、不会重写 Parquet、不会调用外部源。",
            "任何真实 compaction 必须在 dry-run 审阅后另行手动确认；本任务不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="building_storage_compaction_plan",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_compaction_dry_run_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(COMPACTION_DRY_RUN_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_compaction_dry_run_storage_write_failed",
            error_message_safe="storage_compaction_dry_run_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_compaction_dry_run_failed_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="storage_compaction_dry_run_completed",
        call_ledger=packet["call_ledger"],
        warning="storage_compaction_dry_run_completed_no_rewrite_no_external_call",
    ) or task


def _canonical_dataset(dataset: str) -> str:
    key = str(dataset or "").strip().lower().replace(" ", "_")
    if key not in SUPPORTED_PARQUET_DATASETS:
        return ""
    return SUPPORTED_PARQUET_DATASETS[key]


def dataset_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in DATASET_CATALOG]


def _duckdb_query_service_row(dataset: str) -> dict[str, Any]:
    contract = _schema_contract(dataset)
    catalog_item = _dataset_catalog_item(dataset)
    metadata = parquet_store.dataset_metadata(root=PARQUET_ROOT, name=dataset)
    date_column = str(contract.get("date_column") or "")
    entity_columns = [str(item) for item in contract.get("entity_columns") or []]
    projection_columns = _dataset_query_projection_columns(dataset)
    filter_columns = {
        "limit": "result_limit",
        "cursor": "offset_cursor",
        "ts_code": "ts_code" if "ts_code" in entity_columns or dataset in {"daily", "daily_basic", "moneyflow", "factor_values"} else "",
        "trade_date": date_column,
        "start_date": date_column,
        "end_date": date_column,
    }
    supported_filters = [
        filter_name
        for filter_name in DUCKDB_QUERY_FILTER_PARAMS
        if filter_name == "limit" or filter_columns.get(filter_name)
    ]
    skipped_filters = [
        {
            "filter": filter_name,
            "reason": "dataset_column_not_declared",
        }
        for filter_name in DUCKDB_QUERY_FILTER_PARAMS
        if filter_name != "limit" and not filter_columns.get(filter_name)
    ]
    return {
        "dataset": dataset,
        "cache_endpoint": catalog_item.get("cache_endpoint") or f"GET /api/storage/{dataset}",
        "query_wrapper": "duckdb_filtered_parquet.v1",
        "query_backend": "duckdb_read_parquet",
        "parquet_status": metadata.get("status", "missing"),
        "path": _path_label(parquet_store.dataset_path(root=PARQUET_ROOT, name=dataset)),
        "date_column": date_column,
        "entity_columns": entity_columns,
        "projection_columns": projection_columns,
        "query_result_contract_schema_version": "duckdb_query_result_contract.v1",
        "cursor_pagination": "offset_cursor",
        "supported_filter_params": supported_filters,
        "filter_columns": filter_columns,
        "skipped_filter_params": skipped_filters,
        "default_limit": DUCKDB_QUERY_DEFAULT_LIMIT,
        "max_limit": DUCKDB_QUERY_MAX_LIMIT,
        "safe_limit_enforced": True,
        "safe_parameter_binding": True,
        "typed_projection_enabled": True,
        "query_result_contract_enabled": True,
        "cursor_pagination_enabled": True,
        "query_path_policy": "canonical_dataset_path_only",
        "frontend_executes_query": False,
        "ui_direct_dataframe_read": False,
        "cache_get_external_calls": False,
        "cache_get_writes_files": False,
        "writes_parquet_on_get": False,
        "auto_refresh_on_get": False,
        "reads_env_files": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def duckdb_query_service_policy() -> dict[str, Any]:
    dependency = duckdb_store.dependency_status()
    rows = [_duckdb_query_service_row(dataset) for dataset in CANONICAL_PARQUET_DATASETS]
    status = "service_ready" if dependency.get("available") else "dependency_missing"
    return {
        "schema_version": "command_center_3_storage_duckdb_query_service.v1",
        "status": status,
        "mode": "cache_only_read_only_query_service",
        "query_wrapper": "duckdb_filtered_parquet.v1",
        "query_backend": "duckdb_read_parquet",
        "dataset_count": len(rows),
        "rows": rows,
        "supported_filter_params": list(DUCKDB_QUERY_FILTER_PARAMS),
        "default_limit": DUCKDB_QUERY_DEFAULT_LIMIT,
        "max_limit": DUCKDB_QUERY_MAX_LIMIT,
        "safe_limit_enforced": True,
        "safe_parameter_binding": True,
        "typed_projection_enabled": True,
        "query_result_contract_enabled": True,
        "query_result_contract_schema_version": "duckdb_query_result_contract.v1",
        "cursor_pagination_enabled": True,
        "cursor_policy": "offset_cursor",
        "canonical_path_only": True,
        "frontend_executes_query": False,
        "ui_direct_dataframe_read": False,
        "cache_get_external_calls": False,
        "cache_get_writes_files": False,
        "writes_parquet_on_get": False,
        "auto_refresh_on_get": False,
        "reads_env_files": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "dependency": dependency,
        "next_action": "connect full-pool research reads through worker/task consumption before production research.",
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_duckdb_query_service_policy",
            endpoint="GET /api/storage",
            status=status,
            row_count=len(rows),
        ),
        "warnings": [
            "DuckDB query service policy 只描述本地 Parquet 查询包装；不会刷新数据、不会写 Parquet、不会外联。",
        ],
    }


def dataset_implementation_status() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in DATASET_CATALOG:
        dataset = str(item.get("dataset") or "")
        metadata = parquet_store.dataset_metadata(root=PARQUET_ROOT, name=dataset)
        schema_contract = _schema_contract(dataset)
        version_policy = _dataset_version_policy_row(dataset, metadata=metadata)
        partition_plan = _partition_plan(dataset)
        compaction_plan = _compaction_plan(dataset, parquet_store.dataset_path(root=PARQUET_ROOT, name=dataset), metadata)
        schema_migration = _schema_migration_row(dataset, metadata=metadata)
        write_policy = str(item.get("write_policy") or "")
        external_refresh_policy = str(item.get("external_refresh_policy") or "")
        if write_policy == "task_pipeline_write_allowed":
            implementation_state = "local_pipeline_enabled"
        elif write_policy.startswith("future_button_gated"):
            implementation_state = "future_button_gated"
        else:
            implementation_state = "catalog_only"
        rows.append(
            {
                "dataset": dataset,
                "implementation_state": implementation_state,
                "parquet_status": metadata.get("status", "missing"),
                "parquet_exists": bool(metadata.get("exists")),
                "write_policy": write_policy,
                "writer": item.get("writer"),
                "external_refresh_policy": external_refresh_policy,
                "tushare_capable": "tushare" in external_refresh_policy,
                "local_compute_capable": "local_compute" in external_refresh_policy or "local_cache_pipeline" in external_refresh_policy,
                "button_gated": "button_gated" in external_refresh_policy or write_policy == "task_pipeline_write_allowed",
                "schema_contract_status": schema_contract.get("status"),
                "schema_version": schema_contract.get("schema_version"),
                "dataset_version_status": version_policy.get("version_status"),
                "declared_dataset_version": version_policy.get("declared_dataset_version"),
                "version_claim_level": version_policy.get("version_claim_level"),
                "version_manifest_present": bool(version_policy.get("version_manifest_present")),
                "physical_dataset_version_validated": bool(version_policy.get("physical_version_validated")),
                "dataset_version_migration_executed": bool(version_policy.get("dataset_version_migration_executed")),
                "schema_migration_status": schema_migration.get("migration_status"),
                "physical_schema_validation_status": schema_migration.get("physical_column_validation_status"),
                "schema_migration_executed": bool(schema_migration.get("schema_migration_executed")),
                "manual_migration_task_required": bool(schema_migration.get("manual_migration_task_required")),
                "partition_plan_status": partition_plan.get("status"),
                "recommended_partition_columns": partition_plan.get("recommended_partition_columns"),
                "compaction_plan_status": compaction_plan.get("status"),
                "manual_compaction_recommended": bool(compaction_plan.get("manual_compaction_recommended")),
                "does_not_modify_strategy_action": item.get("does_not_modify_strategy_action") is not False,
                "does_not_execute_trades": item.get("does_not_execute_trades") is not False,
                "path": _path_label(Path(str(metadata.get("path") or parquet_store.dataset_path(root=PARQUET_ROOT, name=dataset)))),
            }
        )

    return {
        "status": "partial_migration",
        "scope": "command_center_3_storage_dataset_implementation",
        "dataset_count": len(rows),
        "dataset_rows": rows,
        "state_counts": _count_values(row.get("implementation_state") for row in rows),
        "parquet_status_counts": _count_values(row.get("parquet_status") for row in rows),
        "dataset_version_status_counts": _count_values(row.get("dataset_version_status") for row in rows),
        "local_pipeline_dataset_count": sum(1 for row in rows if row.get("implementation_state") == "local_pipeline_enabled"),
        "future_button_gated_dataset_count": sum(1 for row in rows if row.get("implementation_state") == "future_button_gated"),
        "catalog_only_dataset_count": sum(1 for row in rows if row.get("implementation_state") == "catalog_only"),
        "parquet_ready_dataset_count": sum(1 for row in rows if row.get("parquet_status") == "ready"),
        "parquet_missing_dataset_count": sum(1 for row in rows if row.get("parquet_status") == "missing"),
        "tushare_capable_dataset_count": sum(1 for row in rows if row.get("tushare_capable")),
        "local_compute_capable_dataset_count": sum(1 for row in rows if row.get("local_compute_capable")),
        "schema_contract_ready_count": sum(1 for row in rows if row.get("schema_contract_status") == "contract_ready"),
        "dataset_version_declared_count": sum(1 for row in rows if row.get("declared_dataset_version")),
        "dataset_version_manifest_present_count": sum(1 for row in rows if row.get("version_manifest_present")),
        "physical_dataset_version_validated_count": sum(
            1 for row in rows if row.get("physical_dataset_version_validated")
        ),
        "dataset_version_migration_executed_count": sum(
            1 for row in rows if row.get("dataset_version_migration_executed")
        ),
        "dataset_version_policy": storage_dataset_version_policy(),
        "schema_migration_preflight": storage_schema_migration_preflight(),
        "schema_migration_status_counts": _count_values(row.get("schema_migration_status") for row in rows),
        "schema_migration_executed_count": sum(1 for row in rows if row.get("schema_migration_executed")),
        "physical_schema_validation_done_count": sum(
            1 for row in rows if row.get("physical_schema_validation_status") == "done"
        ),
        "partition_contract_ready_count": sum(1 for row in rows if row.get("partition_plan_status") == "contract_ready"),
        "manual_compaction_recommended_count": sum(1 for row in rows if row.get("manual_compaction_recommended")),
        "all_external_refreshes_button_gated": all(
            bool(row.get("button_gated"))
            for row in rows
            if row.get("tushare_capable") or str(row.get("external_refresh_policy") or "").startswith("button_gated")
        ),
        "all_datasets_do_not_modify_strategy_action": all(row.get("does_not_modify_strategy_action") for row in rows),
        "all_datasets_do_not_execute_trades": all(row.get("does_not_execute_trades") for row in rows),
        "note": "Storage implementation status 只读展示数据集落地状态；不会创建 Parquet、刷新 Tushare 或运行回测。",
    }


def _storage_production_control_rows() -> list[dict[str, Any]]:
    return [
        {
            "control": "schema_version",
            "status": "local_ready",
            "current_coverage": "all canonical Parquet datasets expose local schema contracts with schema_version, date column, primary key and required columns.",
            "next_action": "validate physical files against contracts before full-market research writes.",
            "external_calls_triggered": False,
        },
        {
            "control": "dataset_version_policy",
            "status": "policy_ready",
            "current_coverage": "all canonical datasets expose a read-only version policy with declared dataset version, manifest path and physical validation boundary.",
            "next_action": "use the button-gated manifest writer only after reviewing dry-run output; keep physical schema validation separate.",
            "external_calls_triggered": False,
        },
        {
            "control": "dataset_version_manifest_evidence",
            "status": "read_only_evidence_ready",
            "current_coverage": "storage overview/catalog can read a local ignored _dataset_versions.json if present and report missing/mismatch/validated rows without writing files.",
            "next_action": "after any explicit manifest write, use read-only evidence to verify version rows before claiming local manifest validation.",
            "external_calls_triggered": False,
        },
        {
            "control": "dataset_version_manifest_dry_run",
            "status": "button_gated_ready",
            "current_coverage": "POST manifest dry-run can generate a proposed _dataset_versions.json and per-dataset change plan without writing files.",
            "next_action": "run the button-gated manifest review before using the separately button-gated local manifest writer.",
            "external_calls_triggered": False,
        },
        {
            "control": "dataset_version_manifest_review",
            "status": "button_gated_ready",
            "current_coverage": "POST manifest review compares manifest dry-run rows with schema acceptance rows and records write/promotion blockers without writing files.",
            "next_action": "only use the manifest writer after review rows are ready; keep production promotion separate from manifest write.",
            "external_calls_triggered": False,
        },
        {
            "control": "dataset_version_manifest_write",
            "status": "button_gated_ready",
            "current_coverage": "POST manifest write can create or update the local ignored _dataset_versions.json and then run read-only evidence validation.",
            "next_action": "keep writer manual and local-only; do not treat manifest validation as schema migration, Parquet validation, or production storage completion.",
            "external_calls_triggered": False,
        },
        {
            "control": "dataset_version_manifest_validate",
            "status": "button_gated_ready",
            "current_coverage": "POST manifest validate reads local manifest evidence after a manual write and records validated/blocked rows without writing files.",
            "next_action": "use validate as local manifest evidence only; keep schema migration, partition migration, compaction, TTL refresh and production promotion separate.",
            "external_calls_triggered": False,
        },
        {
            "control": "schema_migration_preflight",
            "status": "preflight_ready",
            "current_coverage": "canonical datasets expose metadata-only schema migration rows with target schema versions, required columns and manual migration boundaries.",
            "next_action": "run an explicit physical validation task before any schema migration or partition rewrite.",
            "external_calls_triggered": False,
        },
        {
            "control": "schema_validation_dry_run",
            "status": "button_gated_ready",
            "current_coverage": "POST schema validation dry-run reads local Parquet schema metadata only and records missing/mismatch/validated rows before migration.",
            "next_action": "review dry-run results before enabling any physical migration or partition rewrite task.",
            "external_calls_triggered": False,
        },
        {
            "control": "schema_validation_acceptance",
            "status": "button_gated_ready",
            "current_coverage": "POST schema validation acceptance records physical schema metadata acceptance rows without reading payloads or writing Parquet.",
            "next_action": "use acceptance rows as a dependency for later manifest promotion, partition migration, and schema migration execution.",
            "external_calls_triggered": False,
        },
        {
            "control": "partition_migration_dry_run",
            "status": "button_gated_ready",
            "current_coverage": "POST partition migration dry-run builds per-dataset partition plans from schema validation and partition contracts without writing partitioned Parquet.",
            "next_action": "review ready/blocked rows before enabling any manual partition writer task.",
            "external_calls_triggered": False,
        },
        {
            "control": "parquet_partitioning",
            "status": "contract_ready",
            "current_coverage": "partition columns are declared per dataset; physical date/universe partition migration is still manual and not run by GET cache.",
            "next_action": "implement explicit manual partition/compaction task after schema validation is stable.",
            "external_calls_triggered": False,
        },
        {
            "control": "duckdb_query_wrappers",
            "status": "local_ready",
            "current_coverage": "DuckDB cache endpoints support safe local ts_code and date-window filters for Parquet datasets.",
            "next_action": "add typed dataset-specific projections and pagination before Factor Test Lab full/small research modes.",
            "external_calls_triggered": False,
        },
        {
            "control": "cache_ttl",
            "status": "button_gated_ready",
            "current_coverage": "Parquet cache endpoints expose audit-only TTL state and POST cache TTL dry-run records refresh-recommended/fresh/missing rows without refreshing data.",
            "next_action": "review TTL dry-run before launching any explicit provider refresh task.",
            "external_calls_triggered": False,
        },
        {
            "control": "parquet_compaction",
            "status": "button_gated_ready",
            "current_coverage": "dataset cache endpoints expose audit-only compaction plans and POST compaction dry-run records ready/not-needed/missing rows without rewriting Parquet.",
            "next_action": "review compaction dry-run before enabling any physical Parquet rewrite task.",
            "external_calls_triggered": False,
        },
        {
            "control": "local_artifact_hygiene",
            "status": "audit_ready",
            "current_coverage": "storage overview exposes path-only generated artifact hygiene, git exclusion patterns, manual cleanup boundaries and a button-gated dry-run task.",
            "next_action": "keep any real cleanup/delete operation separate, explicit and manually approved after dry-run review.",
            "external_calls_triggered": False,
        },
        {
            "control": "artifact_cleanup_manual_review",
            "status": "manual_review_contract_ready",
            "current_coverage": "cleanup dry-run results now expose a manual review contract with required review steps, no-delete boundaries and no generated delete command.",
            "next_action": "review the dry-run rows before adding any separately approved cleanup/delete execution task.",
            "external_calls_triggered": False,
        },
    ]


def _safe_directory_child_count(path: Path) -> int | None:
    if not path.exists() or not path.is_dir():
        return None
    try:
        return sum(1 for _ in path.iterdir())
    except OSError:
        return None


def _artifact_hygiene_row(target: Mapping[str, Any]) -> dict[str, Any]:
    path_parts = [str(part) for part in target.get("path_parts") or []]
    path = PROJECT_ROOT.joinpath(*path_parts)
    exists = path.exists()
    expected_kind = str(target.get("expected_kind") or "directory")
    actual_kind = "missing"
    status = "not_present"
    if exists:
        if path.is_dir():
            actual_kind = "directory"
        elif path.is_file():
            actual_kind = "file"
        else:
            actual_kind = "other"
        status = "present_local_only" if actual_kind == expected_kind else "review_required_type_mismatch"
    return {
        "artifact": str(target.get("artifact") or ""),
        "artifact_type": str(target.get("artifact_type") or ""),
        "path": _path_label(path),
        "expected_kind": expected_kind,
        "actual_kind": actual_kind,
        "exists": exists,
        "status": status,
        "top_level_entry_count": _safe_directory_child_count(path),
        "git_policy": str(target.get("git_policy") or "ignored_local_only"),
        "cleanup_policy": str(target.get("cleanup_policy") or "manual_only_after_review"),
        "reason": str(target.get("reason") or ""),
        "delete_files_on_get": False,
        "auto_cleanup_on_get": False,
        "external_calls_triggered": False,
        "does_not_read_file_payloads": True,
        "does_not_read_env_files": True,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def _artifact_cleanup_review_rows(hygiene_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate_rows = [row for row in hygiene_rows if row.get("exists")]
    path_category_count = len({str(row.get("artifact_type") or "") for row in candidate_rows})
    return [
        {
            "review_step": "review_dry_run_only",
            "status": "required",
            "evidence": "cleanup candidates come from local path metadata only; no delete task has run.",
            "candidate_count": len(candidate_rows),
            "delete_executed": False,
            "external_calls_triggered": False,
        },
        {
            "review_step": "review_path_category",
            "status": "required" if candidate_rows else "no_candidate",
            "evidence": "operator must confirm each path is generated/cache/build/dependency output before any future cleanup.",
            "candidate_count": len(candidate_rows),
            "path_category_count": path_category_count,
            "delete_executed": False,
            "external_calls_triggered": False,
        },
        {
            "review_step": "review_git_ignore_boundary",
            "status": "required",
            "evidence": "push gate and git exclusions remain the source of truth for keeping generated/data artifacts out of git.",
            "tracked_artifact_gate": "scripts/push_gate_3_0.sh generated artifact scan",
            "delete_executed": False,
            "external_calls_triggered": False,
        },
        {
            "review_step": "review_data_artifact_boundary",
            "status": "required",
            "evidence": ".stock_ming_3, parquet/sqlite/db/log/cache artifacts stay local; review does not read payloads or data values.",
            "reads_payloads": False,
            "reads_env_files": False,
            "delete_executed": False,
            "external_calls_triggered": False,
        },
        {
            "review_step": "review_build_artifact_boundary",
            "status": "required",
            "evidence": "desktop/dist and Tauri target output are generated build artifacts; cleanup remains manual/tool-owned.",
            "delete_executed": False,
            "external_calls_triggered": False,
        },
        {
            "review_step": "review_node_dependency_boundary",
            "status": "required",
            "evidence": "desktop/node_modules is package-manager-owned and must not be treated as a generic delete candidate.",
            "delete_executed": False,
            "external_calls_triggered": False,
        },
        {
            "review_step": "review_manual_approval_required",
            "status": "required",
            "evidence": "any future real cleanup/delete operation needs a separate explicit approval after dry-run review.",
            "manual_approval_required": True,
            "safe_delete_command_generated": False,
            "delete_executed": False,
            "external_calls_triggered": False,
        },
        {
            "review_step": "review_no_payload_read",
            "status": "passed",
            "evidence": "review contract uses path existence and metadata only; it does not read file payloads or secret values.",
            "reads_payloads": False,
            "reads_file_payloads": False,
            "reads_env_files": False,
            "scans_secret_values": False,
            "delete_executed": False,
            "external_calls_triggered": False,
        },
        {
            "review_step": "review_no_delete_execution",
            "status": "passed",
            "evidence": "dry-run/review packet does not delete files and does not generate a delete command.",
            "delete_executed": False,
            "safe_delete_command_generated": False,
            "cleanup_review_is_not_delete_execution": True,
            "external_calls_triggered": False,
        },
        {
            "review_step": "review_no_external_or_trade",
            "status": "passed",
            "evidence": "artifact cleanup review is local-only and does not call providers or touch strategy action.",
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
    ]


def artifact_cleanup_review_contract(hygiene_rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_rows = [row for row in hygiene_rows if row.get("exists")]
    review_rows = _artifact_cleanup_review_rows(hygiene_rows)
    required_rows = [row for row in review_rows if row.get("status") == "required"]
    return {
        "schema_version": ARTIFACT_CLEANUP_REVIEW_SCHEMA_VERSION,
        "status": "manual_review_ready_delete_pending" if candidate_rows else "manual_review_ready_no_candidates",
        "mode": "local_path_only_review_contract",
        "scope": "post_cleanup_dry_run_manual_review_before_delete",
        "review_policy": "manual_review_required_after_dry_run_before_any_delete",
        "candidate_count": len(candidate_rows),
        "present_artifact_count": len(candidate_rows),
        "required_review_step_count": len(required_rows),
        "review_step_count": len(review_rows),
        "manual_approval_required": True,
        "dry_run_required_before_delete": True,
        "delete_execution_task_available": False,
        "delete_executed": False,
        "delete_executed_count": 0,
        "safe_delete_command_generated": False,
        "delete_command_not_generated": True,
        "cleanup_review_is_not_delete_execution": True,
        "artifact_cleanup_review_done": True,
        "production_cleanup_complete": False,
        "cache_get_external_calls": False,
        "post_dry_run_external_calls": False,
        "reads_payloads": False,
        "reads_file_payloads": False,
        "reads_env_files": False,
        "scans_secret_values": False,
        "does_not_scan_secret_values": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "contains_secret": False,
        "rows": review_rows,
        "note": "Artifact cleanup review is a human approval contract after dry-run. It does not delete files, generate delete commands, read payloads, scan secret values, call providers, execute trades or modify strategy action.",
    }


def storage_artifact_hygiene_status() -> dict[str, Any]:
    rows = [_artifact_hygiene_row(target) for target in LOCAL_ARTIFACT_HYGIENE_TARGETS]
    review_required = [row for row in rows if row.get("status") == "review_required_type_mismatch"]
    present_rows = [row for row in rows if row.get("exists")]
    review_contract = artifact_cleanup_review_contract(rows)
    return {
        "schema_version": "command_center_3_storage_artifact_hygiene.v1",
        "status": "review_required" if review_required else "audit_ready",
        "scope": "local_generated_artifact_hygiene",
        "rows": rows,
        "present_artifact_count": len(present_rows),
        "review_required_count": len(review_required),
        "git_excluded_patterns": list(LOCAL_ARTIFACT_GIT_EXCLUDED_PATTERNS),
        "tracked_artifact_gate": "scripts/push_gate_3_0.sh generated artifact scan",
        "cleanup_policy": "manual_only_no_delete_on_get",
        "cleanup_task_status": "dry_run_button_gated",
        "cleanup_dry_run_route": "POST /api/storage/artifact-hygiene/dry-run",
        "artifact_cleanup_review_contract": review_contract,
        "artifact_cleanup_review_rows": review_contract["rows"],
        "artifact_cleanup_review_status": review_contract["status"],
        "artifact_cleanup_review_required_step_count": review_contract["required_review_step_count"],
        "artifact_cleanup_delete_executed_count": 0,
        "artifact_cleanup_manual_approval_required": True,
        "artifact_cleanup_delete_command_generated": False,
        "dry_run_required_before_delete": True,
        "data_files_allowed_in_git": False,
        "delete_files_on_get": False,
        "auto_cleanup_on_get": False,
        "does_not_scan_secret_values": True,
        "does_not_read_file_payloads": True,
        "does_not_read_env_files": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "note": "Artifact hygiene is path-only audit data. It never deletes files, reads payloads, scans secret values, refreshes providers or touches strategy action.",
    }


def storage_artifact_cleanup_dry_run_packet(*, task_id: str | None = None, payload_safe: Mapping[str, Any] | None = None) -> dict[str, Any]:
    hygiene = storage_artifact_hygiene_status()
    review_contract = dict(hygiene.get("artifact_cleanup_review_contract") or artifact_cleanup_review_contract(hygiene["rows"]))
    rows: list[dict[str, Any]] = []
    for row in hygiene["rows"]:
        exists = bool(row.get("exists"))
        cleanup_policy = str(row.get("cleanup_policy") or "")
        if not exists:
            dry_run_status = "not_present_no_action"
            candidate_action = "none"
        elif cleanup_policy == "package_manager_only":
            dry_run_status = "present_package_manager_owned"
            candidate_action = "review_with_package_manager"
        else:
            dry_run_status = "present_manual_review_required"
            candidate_action = "manual_cleanup_candidate_after_review"
        rows.append(
            {
                "artifact": row.get("artifact"),
                "artifact_type": row.get("artifact_type"),
                "path": row.get("path"),
                "exists": exists,
                "actual_kind": row.get("actual_kind"),
                "top_level_entry_count": row.get("top_level_entry_count"),
                "git_policy": row.get("git_policy"),
                "cleanup_policy": cleanup_policy,
                "dry_run_status": dry_run_status,
                "candidate_action": candidate_action,
                "would_delete_on_this_task": False,
                "requires_manual_confirmation": exists,
                "does_not_read_file_payloads": True,
                "does_not_read_env_files": True,
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
            }
        )
    candidate_rows = [row for row in rows if row["candidate_action"] != "none"]
    payload = dict(payload_safe or {})
    packet = {
        "packet_key": ARTIFACT_CLEANUP_DRY_RUN_PACKET_KEY,
        "schema_version": "command_center_3_storage_artifact_cleanup_dry_run.v1",
        "status": "ready",
        "mode": "dry_run",
        "task_id": task_id or "",
        "scope": "local_generated_artifact_cleanup_preflight",
        "artifact_hygiene_status": hygiene["status"],
        "cleanup_policy": "dry_run_only_no_delete",
        "cleanup_dry_run_route": "POST /api/storage/artifact-hygiene/dry-run",
        "candidate_rows": rows,
        "candidate_count": len(candidate_rows),
        "present_artifact_count": hygiene["present_artifact_count"],
        "review_required_count": hygiene["review_required_count"],
        "artifact_cleanup_review_contract": review_contract,
        "artifact_cleanup_review_rows": review_contract["rows"],
        "artifact_cleanup_review_status": review_contract["status"],
        "artifact_cleanup_review_required_step_count": review_contract["required_review_step_count"],
        "artifact_cleanup_review_done": review_contract.get("artifact_cleanup_review_done") is True,
        "manual_approval_required_before_delete": True,
        "delete_execution_task_available": False,
        "delete_executed_count": 0,
        "safe_delete_command_generated": False,
        "cleanup_review_is_not_delete_execution": True,
        "production_cleanup_complete": False,
        "git_excluded_patterns": list(hygiene["git_excluded_patterns"]),
        "tracked_artifact_gate": hygiene["tracked_artifact_gate"],
        "request_params_safe": {
            "source": payload.get("source") or "storage_page_button",
            "confirm_delete": False,
            "delete_requested": False,
            "external_sources_allowed": False,
        },
        "delete_files_on_post": False,
        "auto_cleanup_on_post": False,
        "would_delete_files": False,
        "dry_run_required_before_delete": True,
        "does_not_scan_secret_values": True,
        "does_not_read_file_payloads": True,
        "does_not_read_env_files": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "contains_secret": False,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_artifact_cleanup_dry_run",
            endpoint="POST /api/storage/artifact-hygiene/dry-run",
            status="dry_run_completed",
            row_count=len(rows),
        ),
        "warnings": [
            "POST /api/storage/artifact-hygiene/dry-run 只生成本地清理预检清单；不会删除文件。",
            "cleanup review contract 只定义人工复核步骤；不会生成删除命令或执行真实 cleanup。",
            "dry-run 不读取 payload、不扫描 secret 值、不调用 Tushare、DeepSeek、GitHub 或真实交易接口。",
        ],
    }
    return packet


def run_storage_artifact_cleanup_dry_run_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_storage_artifact_cleanup_dry_run",
        output_packet_key=ARTIFACT_CLEANUP_DRY_RUN_PACKET_KEY,
        payload=payload,
        current_step="storage_artifact_cleanup_dry_run_queued",
        warnings=[
            "storage artifact cleanup dry-run 只生成清理候选清单；不会删除文件、不会读取 payload、不会调用外部源。",
            "任何真实清理必须在 dry-run 审阅后另行手动确认；本任务不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="building_storage_artifact_cleanup_dry_run",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_artifact_cleanup_dry_run_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(ARTIFACT_CLEANUP_DRY_RUN_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_artifact_cleanup_dry_run_storage_write_failed",
            error_message_safe="storage_artifact_cleanup_dry_run_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_artifact_cleanup_dry_run_failed_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="storage_artifact_cleanup_dry_run_completed",
        call_ledger=packet["call_ledger"],
        warning="storage_artifact_cleanup_dry_run_completed_no_delete_no_external_call",
    ) or task


def storage_production_readiness(sqlite_meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
    parquet_dependency = parquet_store.dependency_status()
    sqlite_status = str((sqlite_meta or {}).get("status") or ("ready" if SQLITE_META_PATH.exists() else "missing"))
    artifact_hygiene = storage_artifact_hygiene_status()
    artifact_cleanup_review = dict(artifact_hygiene.get("artifact_cleanup_review_contract") or {})
    schema_migration_preflight = storage_schema_migration_preflight()
    schema_migration_execution_evidence = storage_schema_migration_execution_evidence()
    schema_acceptance_evidence = storage_schema_validation_acceptance_evidence_audit()
    backtest_schema_seed_evidence = storage_backtest_results_schema_seed_evidence()
    dataset_version_policy = storage_dataset_version_policy()
    dataset_version_manifest_evidence = storage_dataset_version_manifest_evidence_audit()
    partition_migration_execution = storage_partition_migration_execution_evidence()
    compaction_execution = storage_compaction_execution_evidence()
    duckdb_query_service = duckdb_query_service_policy()
    partition_execution_count = int(
        partition_migration_execution.get("partition_migration_executed_count") or 0
    )
    version_execution_count = int(
        partition_migration_execution.get("dataset_version_migration_executed_count") or 0
    )
    physical_version_count = int(
        partition_migration_execution.get("physical_dataset_version_validated_count") or 0
    )
    compaction_execution_count = int(compaction_execution.get("physical_compaction_executed_count") or 0)
    rows = [
        {
            "component": "sqlite_meta",
            "status": sqlite_status,
            "production_role": "packet metadata / task metadata / local config",
            "current_backend": "sqlite_file",
            "blocking_for_cache_read": False,
            "next_action": "keep payload-safe metadata views; do not expose payload_json in cache endpoints.",
        },
        {
            "component": "schema_migration_preflight",
            "status": schema_migration_preflight["status"],
            "production_role": "schema version audit before any physical dataset migration",
            "current_backend": "metadata_only_contract_rows",
            "blocking_for_cache_read": False,
            "next_action": "add explicit physical schema validation and migration tasks; never run them from GET cache.",
        },
        {
            "component": "schema_migration_execution_evidence",
            "status": schema_migration_execution_evidence["status"],
            "production_role": "latest button-gated schema migration noop verification packet",
            "current_backend": "local_sqlite_packet_read_only_no_init",
            "blocking_for_cache_read": False,
            "schema_migration_executed": schema_migration_execution_evidence["schema_migration_executed"],
            "schema_migration_executed_count": schema_migration_execution_evidence["schema_migration_executed_count"],
            "schema_migration_rewrite_executed": schema_migration_execution_evidence["schema_migration_rewrite_executed"],
            "next_action": "run explicit schema migration execution task only after schema acceptance and manifest validation are stable.",
        },
        {
            "component": "backtest_results_schema_seed_evidence",
            "status": backtest_schema_seed_evidence["status"],
            "production_role": "zero-row backtest_results physical schema seed before schema acceptance",
            "current_backend": "confirm_gated_local_parquet_schema_seed",
            "blocking_for_cache_read": False,
            "schema_seed_ready_for_schema_acceptance": backtest_schema_seed_evidence[
                "schema_seed_ready_for_schema_acceptance"
            ],
            "row_count_written": backtest_schema_seed_evidence["row_count_written"],
            "writes_backtest_result_rows": backtest_schema_seed_evidence["writes_backtest_result_rows"],
            "mock_backtest_result_written": backtest_schema_seed_evidence["mock_backtest_result_written"],
            "next_action": "run explicit backtest_results schema seed before schema acceptance when this dataset is missing.",
        },
        {
            "component": "schema_validation_acceptance_evidence",
            "status": schema_acceptance_evidence["status"],
            "production_role": "latest button-gated physical schema acceptance packet before any migration writer",
            "current_backend": "local_sqlite_packet_read_only_no_init",
            "blocking_for_cache_read": False,
            "source_packet_present": schema_acceptance_evidence["source_packet_present"],
            "accepted_dataset_count": schema_acceptance_evidence["accepted_dataset_count"],
            "blocked_dataset_count": schema_acceptance_evidence["blocked_dataset_count"],
            "physical_schema_validation_done": schema_acceptance_evidence["physical_schema_validation_done"],
            "next_action": "run explicit schema validation acceptance and review blocked datasets before manifest or migration promotion.",
        },
        {
            "component": "dataset_version_policy",
            "status": dataset_version_policy["status"],
            "production_role": "dataset version manifest policy before production reads/writes claim physical versioning",
            "current_backend": "read_only_contract_matrix_no_manifest_write",
            "blocking_for_cache_read": False,
            "next_action": "add explicit manifest writer/validator task after schema validation dry-run passes.",
        },
        {
            "component": "dataset_version_manifest_evidence",
            "status": dataset_version_manifest_evidence["status"],
            "production_role": "read-only local _dataset_versions.json evidence before production dataset version claims",
            "current_backend": "local_manifest_read_only_no_writer_no_payload_read",
            "blocking_for_cache_read": False,
            "manifest_exists": dataset_version_manifest_evidence["manifest_exists"],
            "validated_dataset_count": dataset_version_manifest_evidence["validated_dataset_count"],
            "dataset_version_manifest_validated": dataset_version_manifest_evidence["dataset_version_manifest_validated"],
            "next_action": "add a separately approved manifest writer and validator after physical schema validation is stable.",
        },
        {
            "component": "parquet_store",
            "status": "available" if parquet_dependency.get("available") else "dependency_missing",
            "production_role": "large local datasets and factor values",
            "current_backend": "local_parquet_files",
            "blocking_for_cache_read": False,
            "next_action": "add schema version / compaction / partition policy before full-market research.",
        },
        {
            "component": "duckdb_query",
            "status": duckdb_query_service["status"],
            "production_role": "query Parquet without loading large DataFrames into UI state",
            "current_backend": "duckdb_read_parquet",
            "blocking_for_cache_read": False,
            "query_wrapper": duckdb_query_service["query_wrapper"],
            "max_limit": duckdb_query_service["max_limit"],
            "safe_parameter_binding": duckdb_query_service["safe_parameter_binding"],
            "typed_projection_enabled": duckdb_query_service["typed_projection_enabled"],
            "query_result_contract_enabled": duckdb_query_service["query_result_contract_enabled"],
            "cursor_pagination_enabled": duckdb_query_service["cursor_pagination_enabled"],
            "frontend_executes_query": duckdb_query_service["frontend_executes_query"],
            "cache_get_writes_files": duckdb_query_service["cache_get_writes_files"],
            "next_action": duckdb_query_service["next_action"],
        },
        {
            "component": "local_data_git_guard",
            "status": "ready",
            "production_role": "prevent parquet/cache/db files from entering git",
            "current_backend": ".stock_ming_3 local cache directory",
            "blocking_for_cache_read": False,
            "next_action": "keep node_modules/dist/parquet/cache artifacts ignored and out of commits.",
        },
        {
            "component": "artifact_hygiene",
            "status": artifact_hygiene["status"],
            "production_role": "path-only audit for generated data/build/cache artifacts before any manual cleanup",
            "current_backend": "local_path_preflight_no_payload_reads",
            "blocking_for_cache_read": False,
            "next_action": "review cleanup dry-run rows before any separate delete operation; keep GET storage read-only.",
        },
        {
            "component": "artifact_cleanup_review",
            "status": artifact_cleanup_review.get("status") or "manual_review_ready_no_candidates",
            "production_role": "manual review contract after cleanup dry-run and before any future delete execution",
            "current_backend": "local_path_only_review_contract_no_delete_no_payload_read",
            "blocking_for_cache_read": False,
            "manual_approval_required": True,
            "delete_executed": False,
            "safe_delete_command_generated": False,
            "cleanup_review_is_not_delete_execution": True,
            "production_cleanup_complete": False,
            "next_action": "perform human review of dry-run candidates before designing any separately approved cleanup executor.",
        },
        {
            "component": "partition_migration_execution_evidence",
            "status": partition_migration_execution.get("status") or "partition_migration_execution_missing",
            "production_role": "explicit local partitioned Parquet writer and readback evidence",
            "current_backend": "button_gated_local_partition_writer",
            "blocking_for_cache_read": False,
            "executed_count": int(partition_migration_execution.get("partition_migration_executed_count") or 0),
            "dataset_count": int(partition_migration_execution.get("dataset_count") or len(CANONICAL_PARQUET_DATASETS)),
            "writes_parquet": partition_migration_execution.get("writes_parquet") is True,
            "reads_row_payloads": partition_migration_execution.get("reads_row_payloads") is True,
            "external_calls_triggered": False,
            "next_action": "keep physical partition writes explicit and continue independent TTL/provider and promotion review.",
        },
        {
            "component": "physical_compaction_execution_evidence",
            "status": compaction_execution.get("status") or "physical_compaction_execution_missing",
            "production_role": "explicit local rewrite/readback evidence for canonical partitioned Parquet",
            "current_backend": "button_gated_local_compaction_writer",
            "blocking_for_cache_read": False,
            "executed_count": compaction_execution_count,
            "dataset_count": int(compaction_execution.get("dataset_count") or len(CANONICAL_PARQUET_DATASETS)),
            "writes_parquet": compaction_execution.get("writes_parquet") is True,
            "reads_row_payloads": compaction_execution.get("reads_row_payloads") is True,
            "external_calls_triggered": False,
            "next_action": "keep compaction scope/hash and per-dataset readback evidence bound; TTL/provider refresh remains separate.",
        },
    ]
    blockers = [
        row["component"]
        for row in rows
        if str(row.get("status")) in {"dependency_missing", "read_failed"} and row.get("component") in {"parquet_store", "duckdb_query"}
    ]
    return {
        "status": "foundation_ready" if not blockers else "partial_dependency_missing",
        "scope": "storage_productionization_preflight",
        "rows": rows,
        "production_control_rows": _storage_production_control_rows(),
        "blockers": blockers,
        "production_storage_complete": False,
        "schema_version_policy": "packet metadata and factor_values require explicit schema_version before production migration.",
        "dataset_version_policy": "contract_only_manifest_write_requires_explicit_task",
        "dataset_version_policy_status": dataset_version_policy["status"],
        "dataset_version_policy_dataset_count": dataset_version_policy["dataset_count"],
        "dataset_version_declared_count": dataset_version_policy["target_version_declared_count"],
        "dataset_version_manifest_present_count": dataset_version_policy["version_manifest_present_count"],
        "physical_dataset_version_validated_count": max(
            int(dataset_version_policy["physical_dataset_version_validated_count"]),
            physical_version_count,
        ),
        "dataset_version_migration_executed_count": max(
            int(dataset_version_policy["dataset_version_migration_executed_count"]),
            version_execution_count,
        ),
        "partition_migration_execution_status": partition_migration_execution.get("status"),
        "partition_migration_execution_evidence_present": partition_migration_execution.get("read_status") == "packet_present",
        "partition_migration_executed_count": partition_execution_count,
        "partition_migration_execution": partition_migration_execution,
        "physical_compaction_execution_status": compaction_execution.get("status"),
        "physical_compaction_execution_evidence_present": compaction_execution.get("read_status") == "packet_present",
        "physical_compaction_executed_count": compaction_execution_count,
        "physical_compaction_execution": compaction_execution,
        "dataset_version_manifest_written_on_get": False,
        "dataset_version_manifest_evidence_status": dataset_version_manifest_evidence["status"],
        "dataset_version_manifest_evidence_dataset_count": dataset_version_manifest_evidence["dataset_count"],
        "dataset_version_manifest_evidence_validated_count": dataset_version_manifest_evidence["validated_dataset_count"],
        "dataset_version_manifest_evidence_missing_count": dataset_version_manifest_evidence["missing_dataset_count"],
        "dataset_version_manifest_evidence_mismatch_count": dataset_version_manifest_evidence["schema_version_mismatch_count"],
        "dataset_version_manifest_evidence_exists": dataset_version_manifest_evidence["manifest_exists"],
        "dataset_version_manifest_evidence_validated": dataset_version_manifest_evidence["dataset_version_manifest_validated"],
        "dataset_version_manifest_evidence_written_on_get": dataset_version_manifest_evidence["manifest_written_on_get"],
        "dataset_version_manifest_evidence_reads_parquet_payloads": dataset_version_manifest_evidence["cache_get_reads_parquet_payloads"],
        "dataset_version_manifest_dry_run_route": "POST /api/storage/dataset-version-manifest/dry-run",
        "dataset_version_manifest_dry_run_button_gated": True,
        "dataset_version_manifest_dry_run_writes_manifest": False,
        "dataset_version_manifest_dry_run_writes_parquet": False,
        "dataset_version_manifest_dry_run_reads_parquet_payloads": False,
        "dataset_version_manifest_review_route": "POST /api/storage/dataset-version-manifest/review",
        "dataset_version_manifest_review_button_gated": True,
        "dataset_version_manifest_review_writes_manifest": False,
        "dataset_version_manifest_review_writes_parquet": False,
        "dataset_version_manifest_review_reads_parquet_payloads": False,
        "dataset_version_manifest_review_external_calls": False,
        "dataset_version_manifest_review_production_storage_complete": False,
        "dataset_version_manifest_write_route": "POST /api/storage/dataset-version-manifest/write",
        "dataset_version_manifest_write_button_gated": True,
        "dataset_version_manifest_write_requires_confirm": True,
        "dataset_version_manifest_write_writes_manifest": True,
        "dataset_version_manifest_write_writes_parquet": False,
        "dataset_version_manifest_write_reads_parquet_payloads": False,
        "dataset_version_manifest_write_external_calls": False,
        "dataset_version_manifest_write_executed_count": 0,
        "dataset_version_manifest_validate_route": "POST /api/storage/dataset-version-manifest/validate",
        "dataset_version_manifest_validate_button_gated": True,
        "dataset_version_manifest_validate_writes_manifest": False,
        "dataset_version_manifest_validate_writes_parquet": False,
        "dataset_version_manifest_validate_reads_parquet_payloads": False,
        "dataset_version_manifest_validate_external_calls": False,
        "dataset_version_manifest_validate_production_storage_complete": False,
        "dataset_version_manifest_validate_requires_prior_write": True,
        "schema_contract_policy": "canonical datasets expose local schema contracts; physical validation remains explicit and non-refreshing.",
        "schema_migration_policy": "preflight_only_no_physical_migration_on_get",
        "schema_migration_execution_evidence": schema_migration_execution_evidence,
        "schema_migration_execution_route": "POST /api/storage/schema-migration/execute",
        "schema_migration_execution_button_gated": True,
        "schema_migration_execution_requires_confirm": True,
        "schema_migration_execution_writes_parquet": False,
        "schema_migration_execution_writes_manifest": False,
        "schema_migration_execution_reads_row_payloads": False,
        "schema_migration_execution_external_calls": False,
        "schema_migration_execution_production_storage_complete": False,
        "schema_migration_execution_status": schema_migration_execution_evidence["status"],
        "schema_migration_rewrite_executed": schema_migration_execution_evidence["schema_migration_rewrite_executed"],
        "backtest_results_schema_seed_evidence": backtest_schema_seed_evidence,
        "backtest_results_schema_seed_route": "POST /api/storage/backtest-results/schema-seed",
        "backtest_results_schema_seed_button_gated": True,
        "backtest_results_schema_seed_requires_confirm": True,
        "backtest_results_schema_seed_writes_parquet": True,
        "backtest_results_schema_seed_writes_only_ignored_local_parquet": True,
        "backtest_results_schema_seed_writes_backtest_result_rows": False,
        "backtest_results_schema_seed_mock_backtest_result_written": False,
        "backtest_results_schema_seed_reads_row_payloads": False,
        "backtest_results_schema_seed_reads_env_files": False,
        "backtest_results_schema_seed_schema_migration_executed": False,
        "backtest_results_schema_seed_production_storage_complete": False,
        "backtest_results_schema_seed_ready_for_schema_acceptance": backtest_schema_seed_evidence[
            "schema_seed_ready_for_schema_acceptance"
        ],
        "backtest_results_schema_seed_row_count_written": backtest_schema_seed_evidence["row_count_written"],
        "schema_migration_preflight_status": schema_migration_preflight["status"],
        "schema_migration_dataset_count": schema_migration_preflight["dataset_count"],
        "schema_migration_executed_count": schema_migration_preflight["migration_executed_count"],
        "schema_migration_preflight_physical_validation_done_count": schema_migration_preflight[
            "physical_validation_done_count"
        ],
        "schema_validation_acceptance_evidence": schema_acceptance_evidence,
        "schema_validation_acceptance_evidence_status": schema_acceptance_evidence["status"],
        "schema_validation_acceptance_evidence_exists": schema_acceptance_evidence["source_packet_present"],
        "schema_validation_acceptance_source_packet_status": schema_acceptance_evidence["source_packet_status"],
        "schema_validation_acceptance_source_packet_task_id": schema_acceptance_evidence["source_packet_task_id"],
        "schema_validation_acceptance_accepted_dataset_count": schema_acceptance_evidence["accepted_dataset_count"],
        "schema_validation_acceptance_blocked_dataset_count": schema_acceptance_evidence["blocked_dataset_count"],
        "schema_validation_acceptance_missing_dataset_count": schema_acceptance_evidence["missing_dataset_count"],
        "schema_validation_acceptance_passed_all": schema_acceptance_evidence["schema_acceptance_passed_all"],
        "schema_validation_acceptance_cache_get_writes_files": schema_acceptance_evidence["cache_get_writes_files"],
        "schema_validation_acceptance_reads_row_payloads": schema_acceptance_evidence["cache_get_reads_row_payloads"],
        "physical_schema_validation_done": schema_acceptance_evidence["physical_schema_validation_done"],
        "physical_schema_validation_done_count": schema_acceptance_evidence["physical_schema_validation_done_count"],
        "physical_schema_validation_source": "schema_validation_acceptance_evidence_packet",
        "schema_validation_dry_run_route": "POST /api/storage/schema-validation/dry-run",
        "schema_validation_dry_run_button_gated": True,
        "schema_validation_dry_run_writes_parquet": False,
        "schema_validation_dry_run_reads_row_payloads": False,
        "schema_validation_acceptance_route": "POST /api/storage/schema-validation/acceptance",
        "schema_validation_acceptance_button_gated": True,
        "schema_validation_acceptance_writes_parquet": False,
        "schema_validation_acceptance_reads_row_payloads": False,
        "schema_validation_acceptance_executes_migration": False,
        "schema_validation_acceptance_external_calls": False,
        "duckdb_query_service_policy": "read_only_service_wrappers_local_parquet_only",
        "duckdb_query_service_status": duckdb_query_service["status"],
        "duckdb_query_service_dataset_count": duckdb_query_service["dataset_count"],
        "duckdb_query_wrapper": duckdb_query_service["query_wrapper"],
        "duckdb_query_max_limit": duckdb_query_service["max_limit"],
        "duckdb_query_safe_parameter_binding": duckdb_query_service["safe_parameter_binding"],
        "duckdb_query_typed_projection_enabled": duckdb_query_service["typed_projection_enabled"],
        "duckdb_query_result_contract_enabled": duckdb_query_service["query_result_contract_enabled"],
        "duckdb_query_result_contract_schema_version": duckdb_query_service["query_result_contract_schema_version"],
        "duckdb_query_cursor_pagination_enabled": duckdb_query_service["cursor_pagination_enabled"],
        "duckdb_query_frontend_executes_queries": duckdb_query_service["frontend_executes_query"],
        "duckdb_query_cache_get_external_calls": duckdb_query_service["cache_get_external_calls"],
        "duckdb_query_cache_get_writes_files": duckdb_query_service["cache_get_writes_files"],
        "duckdb_query_writes_parquet_on_get": duckdb_query_service["writes_parquet_on_get"],
        "partition_migration_dry_run_route": "POST /api/storage/partition-migration/dry-run",
        "partition_migration_dry_run_button_gated": True,
        "partition_migration_dry_run_writes_parquet": False,
        "partition_migration_dry_run_reads_row_payloads": False,
        "partition_migration_execution_route": "POST /api/storage/partition-migration/execute",
        "partition_migration_execution_button_gated": True,
        "partition_migration_execution_requires_confirm": True,
        "partition_migration_execution_writes_parquet": partition_execution_count > 0,
        "partition_migration_execution_reads_row_payloads": partition_migration_execution.get("reads_row_payloads") is True,
        "partition_migration_execution_external_calls": False,
        "partition_migration_execution_status": partition_migration_execution.get("status"),
        "partition_migration_execution_production_storage_complete": False,
        "cache_ttl_policy": "dry_run_button_gated_no_auto_refresh",
        "cache_ttl_dry_run_route": "POST /api/storage/cache-ttl/dry-run",
        "cache_ttl_dry_run_button_gated": True,
        "cache_ttl_dry_run_writes_parquet": False,
        "cache_ttl_dry_run_reads_row_payloads": False,
        "cache_ttl_refresh_executed_count": 0,
        "compaction_policy": "confirm_gated_local_partition_rewrite_no_external_call",
        "compaction_dry_run_route": "POST /api/storage/compaction/dry-run",
        "compaction_dry_run_button_gated": True,
        "compaction_dry_run_writes_parquet": False,
        "compaction_dry_run_reads_row_payloads": False,
        "compaction_execution_route": "POST /api/storage/compaction/execute",
        "compaction_execution_button_gated": True,
        "compaction_execution_requires_confirm": True,
        "compaction_execution_writes_parquet": compaction_execution_count > 0,
        "compaction_execution_reads_row_payloads": compaction_execution.get("reads_row_payloads") is True,
        "compaction_execution_external_calls": False,
        "compaction_execution_status": compaction_execution.get("status"),
        "compaction_execution_production_storage_complete": False,
        "compaction_executed_count": compaction_execution_count,
        "artifact_hygiene_policy": "path_only_manual_cleanup_no_delete_on_get",
        "artifact_hygiene_status": artifact_hygiene["status"],
        "artifact_hygiene_present_count": artifact_hygiene["present_artifact_count"],
        "artifact_cleanup_dry_run_route": "POST /api/storage/artifact-hygiene/dry-run",
        "artifact_cleanup_dry_run_button_gated": True,
        "artifact_cleanup_dry_run_deletes_files": False,
        "artifact_cleanup_review_status": artifact_cleanup_review.get("status") or "manual_review_ready_no_candidates",
        "artifact_cleanup_review_required_step_count": artifact_cleanup_review.get("required_review_step_count", 0),
        "artifact_cleanup_manual_review_required": True,
        "artifact_cleanup_delete_executed_count": 0,
        "artifact_cleanup_delete_command_generated": False,
        "artifact_cleanup_review_is_not_delete_execution": True,
        "artifact_cleanup_production_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "Storage production readiness is diagnostic only; it does not create datasets or connect to external services.",
    }


def _storage_production_blocker_row(
    criterion: str,
    passed: bool,
    *,
    current_status: Any,
    evidence: str,
    next_action: str,
    classification: str,
    production_blocker: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": passed,
        "current_status": current_status,
        "evidence": evidence,
        "next_action": next_action,
        "classification": classification,
        "production_blocker": production_blocker and not passed,
    }


def storage_production_blocker_audit(production_readiness: Mapping[str, Any] | None = None) -> dict[str, Any]:
    readiness = dict(production_readiness or storage_production_readiness())
    dataset_count = int(readiness.get("schema_migration_dataset_count") or len(CANONICAL_PARQUET_DATASETS))
    schema_validation_done = int(readiness.get("physical_schema_validation_done_count") or 0)
    schema_migration_executed = int(readiness.get("schema_migration_executed_count") or 0)
    version_validated = int(readiness.get("physical_dataset_version_validated_count") or 0)
    version_migrations = int(readiness.get("dataset_version_migration_executed_count") or 0)
    manifest_present = int(readiness.get("dataset_version_manifest_present_count") or 0)
    manifest_evidence_validated = bool(readiness.get("dataset_version_manifest_evidence_validated"))
    manifest_evidence_count = int(readiness.get("dataset_version_manifest_evidence_validated_count") or 0)
    compaction_executed = int(readiness.get("compaction_executed_count") or 0)
    ttl_refresh_executed = int(readiness.get("cache_ttl_refresh_executed_count") or 0)
    partition_executed = int(readiness.get("partition_migration_executed_count") or 0)
    cleanup_review_ready = str(readiness.get("artifact_cleanup_review_status") or "").startswith("manual_review_ready")
    dependency_ready = str(readiness.get("status")) == "foundation_ready"
    duckdb_ready = str(readiness.get("duckdb_query_service_status")) == "service_ready"
    rows = [
        _storage_production_blocker_row(
            "schema_physical_validation_complete",
            schema_validation_done >= dataset_count,
            current_status=f"{schema_validation_done}/{dataset_count}",
            evidence=(
                "schema validation dry-run is available; latest button-gated schema acceptance evidence "
                f"status={readiness.get('schema_validation_acceptance_evidence_status')}."
            ),
            next_action="Run and review explicit schema validation tasks for all canonical datasets before production migration.",
            classification="dry_run_or_preflight_not_production",
        ),
        _storage_production_blocker_row(
            "schema_migration_executed",
            schema_migration_executed >= dataset_count,
            current_status=f"{schema_migration_executed}/{dataset_count}",
            evidence="schema migration preflight exists, but physical schema migration execution count remains below dataset count.",
            next_action="Add a separately approved physical schema migration task after validation is stable.",
            classification="preflight_only",
        ),
        _storage_production_blocker_row(
            "dataset_version_manifest_validated",
            manifest_present >= dataset_count
            and version_validated >= dataset_count
            and version_migrations >= dataset_count
            and manifest_evidence_validated,
            current_status=(
                f"policy_manifest={manifest_present}/{dataset_count}; "
                f"policy_validated={version_validated}/{dataset_count}; "
                f"evidence_validated={manifest_evidence_count}/{dataset_count}; "
                f"migrated={version_migrations}/{dataset_count}"
            ),
            evidence="dataset version policy is contract-only; manifest evidence audit is read-only and does not write _dataset_versions.json on GET.",
            next_action="Add explicit manifest writer and physical version validator tasks before claiming versioned production datasets.",
            classification="policy_only_not_physical_proof",
        ),
        _storage_production_blocker_row(
            "partition_migration_executed",
            partition_executed >= dataset_count,
            current_status=f"{partition_executed}/{dataset_count}",
            evidence=(
                "partition migration execution packet has complete target tree hashes and row-count readback."
                if partition_executed >= dataset_count
                else "partition migration dry-run creates ready/blocked plans, but physical execution is incomplete."
            ),
            next_action=(
                "Keep partitioned targets and source single-file datasets aligned; continue independent storage gates."
                if partition_executed >= dataset_count
                else "Review partition dry-run rows, then run the explicit confirm-gated partition writer task."
            ),
            classification="physical_local_execution" if partition_executed >= dataset_count else "dry_run_only",
        ),
        _storage_production_blocker_row(
            "physical_compaction_executed",
            compaction_executed >= dataset_count,
            current_status=f"{compaction_executed}/{dataset_count}",
            evidence=(
                "compaction execution packet has complete per-dataset rewrite/readback evidence."
                if compaction_executed >= dataset_count
                else "compaction dry-run is available, but explicit local rewrite/readback is incomplete."
            ),
            next_action=(
                "Keep compacted targets and their tree hashes bound to this scope; continue TTL/provider review."
                if compaction_executed >= dataset_count
                else "Review compaction dry-run rows, then run the explicit confirm-gated local compaction task."
            ),
            classification="physical_local_execution" if compaction_executed >= dataset_count else "dry_run_only",
        ),
        _storage_production_blocker_row(
            "cache_ttl_refresh_pipeline_executed",
            ttl_refresh_executed > 0,
            current_status=ttl_refresh_executed,
            evidence="cache TTL dry-run records stale/fresh recommendations, but does not refresh providers or write Parquet.",
            next_action="Add explicit provider refresh tasks after Tushare interface acceptance is complete.",
            classification="dry_run_only_no_provider_refresh",
        ),
        _storage_production_blocker_row(
            "duckdb_query_service_dependency_ready",
            duckdb_ready,
            current_status=readiness.get("duckdb_query_service_status"),
            evidence="DuckDB query service must be available for production reads; dependency_missing remains a production blocker.",
            next_action="Install/verify DuckDB dependency in the standard project environment before production packaging.",
            classification="runtime_dependency",
        ),
        _storage_production_blocker_row(
            "generated_data_artifacts_guarded",
            readiness.get("artifact_hygiene_policy") == "path_only_manual_cleanup_no_delete_on_get",
            current_status=readiness.get("artifact_hygiene_status"),
            evidence="artifact hygiene is path-only and push gate blocks generated/data files from git; cleanup remains manual.",
            next_action="Continue using push gate artifact scan and keep any real cleanup/delete operation separately approved.",
            classification="guardrail_ready",
            production_blocker=False,
        ),
        _storage_production_blocker_row(
            "artifact_cleanup_manual_review_visible",
            cleanup_review_ready
            and readiness.get("artifact_cleanup_manual_review_required") is True
            and int(readiness.get("artifact_cleanup_delete_executed_count") or 0) == 0
            and readiness.get("artifact_cleanup_delete_command_generated") is False,
            current_status=readiness.get("artifact_cleanup_review_status"),
            evidence="artifact cleanup review contract is visible after dry-run and remains no-delete/no-generated-command.",
            next_action="Review dry-run candidate rows before any separately approved cleanup/delete executor is designed.",
            classification="manual_review_contract_not_cleanup_execution",
            production_blocker=False,
        ),
        _storage_production_blocker_row(
            "cache_get_remains_read_only",
            readiness.get("external_calls_triggered") is False
            and readiness.get("schema_validation_dry_run_writes_parquet") is False
            and readiness.get("compaction_dry_run_writes_parquet") is False
            and readiness.get("cache_ttl_dry_run_writes_parquet") is False,
            current_status="cache_only_no_writes",
            evidence="GET storage cache and dry-run policies do not write Parquet, refresh providers, or execute trades.",
            next_action="Preserve GET cache read-only semantics while adding future explicit POST tasks.",
            classification="guardrail_ready",
            production_blocker=False,
        ),
    ]
    blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    return {
        "schema_version": STORAGE_PRODUCTION_BLOCKER_SCHEMA_VERSION,
        "status": "storage_production_ready" if not blockers and dependency_ready else "storage_production_blocked",
        "scope": "ltg_05_storage_duckdb_parquet_productionization",
        "dataset_count": dataset_count,
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "production_storage_complete": not blockers and dependency_ready,
        "local_contracts_ready": readiness.get("status") in {"foundation_ready", "partial_dependency_missing"},
        "dry_runs_are_not_production_completion": True,
        "preflight_is_not_physical_migration": True,
        "dataset_version_policy_is_not_manifest_validation": True,
        "dataset_version_manifest_evidence_is_read_only": True,
        "dataset_version_manifest_dry_run_is_not_write": True,
        "dataset_version_manifest_review_is_not_write": True,
        "dataset_version_manifest_evidence_status": readiness.get("dataset_version_manifest_evidence_status"),
        "dataset_version_manifest_evidence_validated": manifest_evidence_validated,
        "dataset_version_manifest_evidence_validated_count": manifest_evidence_count,
        "query_service_status": readiness.get("duckdb_query_service_status"),
        "schema_validation_done_count": schema_validation_done,
        "schema_migration_executed_count": schema_migration_executed,
        "physical_dataset_version_validated_count": version_validated,
        "dataset_version_migration_executed_count": version_migrations,
        "compaction_executed_count": compaction_executed,
        "cache_ttl_refresh_executed_count": ttl_refresh_executed,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
    }


def storage_production_readiness_receipt(
    production_readiness: Mapping[str, Any] | None = None,
    production_blocker_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    readiness = dict(production_readiness or storage_production_readiness())
    blocker_audit = dict(production_blocker_audit or storage_production_blocker_audit(readiness))
    blocker_rows = [row for row in blocker_audit.get("rows") or [] if isinstance(row, Mapping)]
    production_blockers = [str(row.get("criterion") or "") for row in blocker_rows if row.get("production_blocker")]
    local_contracts_ready = bool(blocker_audit.get("local_contracts_ready"))
    explicit_post_boundaries_ready = all(
        bool(readiness.get(key))
        for key in (
            "schema_validation_dry_run_button_gated",
            "schema_validation_acceptance_button_gated",
            "schema_migration_execution_button_gated",
            "dataset_version_manifest_dry_run_button_gated",
            "dataset_version_manifest_review_button_gated",
            "dataset_version_manifest_write_button_gated",
            "dataset_version_manifest_validate_button_gated",
            "partition_migration_dry_run_button_gated",
            "compaction_dry_run_button_gated",
            "cache_ttl_dry_run_button_gated",
            "artifact_cleanup_dry_run_button_gated",
        )
    )
    cache_read_only = (
        readiness.get("external_calls_triggered") is False
        and readiness.get("schema_validation_dry_run_writes_parquet") is False
        and readiness.get("dataset_version_manifest_dry_run_writes_manifest") is False
        and readiness.get("dataset_version_manifest_review_writes_manifest") is False
        and readiness.get("dataset_version_manifest_validate_writes_manifest") is False
        and readiness.get("partition_migration_dry_run_writes_parquet") is False
        and readiness.get("compaction_dry_run_writes_parquet") is False
        and readiness.get("cache_ttl_dry_run_writes_parquet") is False
        and readiness.get("artifact_cleanup_dry_run_deletes_files") is False
    )
    manifest_write_guarded = (
        readiness.get("dataset_version_manifest_write_button_gated") is True
        and readiness.get("dataset_version_manifest_write_requires_confirm") is True
        and readiness.get("dataset_version_manifest_write_writes_manifest") is True
        and readiness.get("dataset_version_manifest_write_writes_parquet") is False
        and readiness.get("dataset_version_manifest_write_external_calls") is False
        and int(readiness.get("dataset_version_manifest_write_executed_count") or 0) == 0
    )
    production_complete = bool(blocker_audit.get("production_storage_complete"))
    receipt_ready = bool(local_contracts_ready and explicit_post_boundaries_ready and cache_read_only and manifest_write_guarded)
    if not receipt_ready:
        status = "storage_production_receipt_blocked_local_contract"
        allowed_next_step = "fix_storage_local_contract_before_any_storage_task"
    elif production_complete:
        status = "storage_production_receipt_ready_for_promotion_review"
        allowed_next_step = "explicit_post_task_storage_production_promotion_review"
    else:
        status = "storage_readiness_receipt_ready_physical_migration_pending"
        allowed_next_step = "explicit_post_task_storage_schema_acceptance_manifest_review"

    rows = [
        {
            "criterion": "local_contracts_visible",
            "status": "passed" if local_contracts_ready else "blocked",
            "passed": local_contracts_ready,
            "evidence": "production_readiness and storage_production_blocker_audit are present in the GET storage cache.",
            "next_step": "continue to explicit POST storage review tasks",
        },
        {
            "criterion": "explicit_post_task_boundaries",
            "status": "passed" if explicit_post_boundaries_ready else "blocked",
            "passed": explicit_post_boundaries_ready,
            "evidence": "schema, manifest, partition, compaction, TTL, and cleanup tasks are button-gated POST tasks.",
            "next_step": "preserve button gating before adding any physical writer",
        },
        {
            "criterion": "cache_get_read_only_boundary",
            "status": "passed" if cache_read_only else "blocked",
            "passed": cache_read_only,
            "evidence": "GET storage cache does not refresh providers, write Parquet, write manifest, delete files, or trade.",
            "next_step": "keep GET /api/storage as evidence-only",
        },
        {
            "criterion": "manifest_write_is_guarded",
            "status": "passed" if manifest_write_guarded else "blocked",
            "passed": manifest_write_guarded,
            "evidence": "manifest write is explicit, confirm-gated, local manifest only, no Parquet, no provider, and not executed by receipt.",
            "next_step": "run dry-run/review before any separately approved manifest write",
        },
        {
            "criterion": "physical_schema_validation_pending",
            "status": "blocked" if "schema_physical_validation_complete" in production_blockers else "passed",
            "passed": "schema_physical_validation_complete" not in production_blockers,
            "evidence": "physical schema validation remains a production blocker until all canonical datasets pass.",
            "next_step": "explicit POST schema validation acceptance review",
        },
        {
            "criterion": "physical_migration_and_versioning_pending",
            "status": "blocked"
            if any(
                blocker in production_blockers
                for blocker in ("schema_migration_executed", "dataset_version_manifest_validated", "partition_migration_executed")
            )
            else "passed",
            "passed": not any(
                blocker in production_blockers
                for blocker in ("schema_migration_executed", "dataset_version_manifest_validated", "partition_migration_executed")
            ),
            "evidence": "schema migration, dataset version validation, and partition migration are not production-complete.",
            "next_step": "separate manual writer/migration tasks after review evidence is stable",
        },
        {
            "criterion": "maintenance_execution_pending",
            "status": "blocked"
            if any(blocker in production_blockers for blocker in ("physical_compaction_executed", "cache_ttl_refresh_pipeline_executed"))
            else "passed",
            "passed": not any(
                blocker in production_blockers for blocker in ("physical_compaction_executed", "cache_ttl_refresh_pipeline_executed")
            ),
            "evidence": "compaction and TTL refresh are still dry-run/recommendation paths, not execution paths.",
            "next_step": "keep compaction and refresh execution separate from cache rendering",
        },
        {
            "criterion": "production_completion_evidence_ticket",
            "status": "passed" if production_complete else "blocked",
            "passed": production_complete,
            "evidence": "production storage completion requires all blocker rows to pass and separate promotion evidence.",
            "next_step": "do not claim production storage complete from receipt, preflight, dry-run, or manifest policy alone",
        },
    ]
    blocked_rows = [row["criterion"] for row in rows if not row.get("passed")]
    return {
        "schema_version": "command_center_3_storage_production_readiness_receipt.v1",
        "scope": "local_storage_production_readiness_receipt_no_physical_migration",
        "status": status,
        "local_receipt_ready": receipt_ready,
        "ready_for_explicit_storage_review_tasks": receipt_ready,
        "allowed_next_step": allowed_next_step,
        "not_allowed_next_steps": [
            "GET /api/storage physical migration",
            "GET /api/storage provider refresh",
            "automatic Parquet compaction",
            "automatic cache TTL provider refresh",
            "artifact cleanup delete execution from dry-run",
            "dry-run/preflight/receipt as production storage completion",
        ],
        "production_storage_complete": production_complete,
        "physical_schema_validation_done": bool(readiness.get("physical_schema_validation_done")),
        "schema_migration_executed": False,
        "dataset_version_manifest_validated": bool(readiness.get("dataset_version_manifest_evidence_validated")),
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "artifact_cleanup_delete_executed": False,
        "provider_refresh_called_by_receipt": False,
        "cache_get_external_calls": False,
        "receipt_external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "blocked_readiness_count": len(blocked_rows),
        "blocked_readiness": blocked_rows,
        "production_blocker_count": int(blocker_audit.get("blocking_criterion_count") or 0),
        "production_blockers": list(blocker_audit.get("blockers") or []),
        "rows": rows,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_production_readiness_receipt",
            endpoint="GET /api/storage",
            status=status,
            row_count=len(rows),
        ),
        "note": "This receipt only summarizes local LTG-05 readiness. It does not write manifests, write Parquet, compact files, refresh providers, delete artifacts, or trade.",
    }


def _storage_activation_row(
    criterion: str,
    passed: bool,
    evidence: str,
    next_step: str,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": passed,
        "evidence": evidence,
        "next_step": next_step,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def storage_physical_migration_activation_receipt(
    production_readiness: Mapping[str, Any] | None = None,
    production_blocker_audit: Mapping[str, Any] | None = None,
    production_readiness_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    readiness = dict(production_readiness or storage_production_readiness())
    blocker_audit = dict(production_blocker_audit or storage_production_blocker_audit(readiness))
    readiness_receipt = dict(
        production_readiness_receipt
        or storage_production_readiness_receipt(readiness, blocker_audit)
    )
    readiness_ready = bool(readiness_receipt.get("local_receipt_ready"))
    cache_get_boundary = (
        readiness.get("external_calls_triggered") is False
        and readiness_receipt.get("cache_get_external_calls") is False
        and readiness_receipt.get("provider_refresh_called_by_receipt") is False
        and readiness_receipt.get("receipt_external_calls_triggered") is False
    )
    explicit_task_boundary = (
        readiness_receipt.get("allowed_next_step")
        == "explicit_post_task_storage_schema_acceptance_manifest_review"
        and readiness.get("schema_validation_acceptance_button_gated") is True
        and readiness.get("dataset_version_manifest_validate_button_gated") is True
        and readiness.get("partition_migration_dry_run_button_gated") is True
        and readiness.get("compaction_dry_run_button_gated") is True
        and readiness.get("cache_ttl_dry_run_button_gated") is True
        and readiness.get("artifact_cleanup_dry_run_button_gated") is True
    )
    duckdb_boundary = readiness.get("duckdb_query_service_status") in {"service_ready", "dependency_missing"}
    local_activation_ready = readiness_ready and cache_get_boundary and explicit_task_boundary
    schema_acceptance_done = readiness.get("physical_schema_validation_done") is True
    rows = [
        _storage_activation_row(
            "readiness_receipt_ready",
            readiness_ready,
            "storage_production_readiness_receipt is present and ready for explicit review tasks.",
            "keep readiness receipt visible while physical execution remains separate",
        ),
        _storage_activation_row(
            "schema_acceptance_required",
            schema_acceptance_done,
            (
                "Latest schema acceptance packet proves all canonical datasets."
                if schema_acceptance_done
                else "Physical schema acceptance has not been promoted to production evidence."
            ),
            "run explicit schema acceptance review before any migration writer",
        ),
        _storage_activation_row(
            "manifest_validation_required",
            False,
            "Dataset version manifest validation remains pending and cannot be inferred from policy or dry-run output.",
            "validate an ignored local manifest only after schema acceptance evidence is reviewed",
        ),
        _storage_activation_row(
            "partition_migration_required",
            False,
            "Partition migration remains dry-run only and has not written partitioned Parquet.",
            "prepare a separate confirm-gated migration task after manifest validation",
        ),
        _storage_activation_row(
            "compaction_execution_required",
            False,
            "Compaction remains dry-run/recommendation only and has not rewritten Parquet.",
            "execute compaction only through a separately approved maintenance task",
        ),
        _storage_activation_row(
            "cache_ttl_refresh_required",
            False,
            "TTL refresh remains recommendation-only and has not called providers or written Parquet.",
            "keep provider refresh as explicit POST task evidence, never GET cache rendering",
        ),
        _storage_activation_row(
            "cleanup_manual_approval_required",
            False,
            "Artifact cleanup dry-run has not deleted files and has not generated delete commands.",
            "require manual cleanup approval and separate delete execution evidence",
        ),
        _storage_activation_row(
            "duckdb_query_boundary_ready",
            duckdb_boundary,
            "DuckDB query service is local/service-ready or dependency-missing without frontend DataFrame access.",
            "keep UI behind FastAPI query wrappers and cursor contracts",
        ),
        _storage_activation_row(
            "no_get_migration_or_provider_refresh",
            cache_get_boundary,
            "GET storage cache remains read-only with no provider refresh, Parquet writes, manifest writes, or cleanup deletes.",
            "preserve GET /api/storage as evidence-only",
        ),
        _storage_activation_row(
            "no_trade_or_action_boundary",
            readiness_receipt.get("does_not_execute_trades") is True
            and readiness_receipt.get("does_not_modify_strategy_action") is True,
            "Storage activation receipt does not execute trades or mutate strategy action.",
            "keep storage productionization isolated from strategy action",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row.get("passed")]
    return {
        "schema_version": "command_center_3_storage_physical_migration_activation_receipt.v1",
        "scope": "local_storage_physical_migration_activation_receipt_no_physical_execution",
        "status": (
            "storage_physical_migration_activation_receipt_ready_execution_pending"
            if local_activation_ready
            else "storage_physical_migration_activation_receipt_blocked_local_contract"
        ),
        "local_activation_receipt_ready": local_activation_ready,
        "ready_for_explicit_physical_migration_review": local_activation_ready,
        "allowed_next_step": "explicit_schema_acceptance_manifest_validate_then_partition_compaction_ttl_cleanup_reviews",
        "not_allowed_next_steps": [
            "GET /api/storage physical migration",
            "GET /api/storage Parquet write",
            "GET /api/storage provider refresh",
            "automatic partition migration",
            "automatic compaction",
            "automatic TTL refresh",
            "artifact cleanup delete execution from dry-run",
            "activation receipt as production storage completion",
        ],
        "missing_evidence": [
            *([] if schema_acceptance_done else ["physical schema validation acceptance for all canonical datasets"]),
            "manifest validation backed by schema acceptance",
            "partition migration execution evidence",
            "physical compaction execution evidence",
            "cache TTL refresh execution evidence",
            "cleanup manual approval/delete evidence",
            "production promotion review",
        ],
        "production_storage_complete": False,
        "physical_schema_validation_done": schema_acceptance_done,
        "schema_migration_executed": False,
        "dataset_version_manifest_validated": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "artifact_cleanup_delete_executed": False,
        "provider_refresh_called_by_receipt": False,
        "parquet_written_by_receipt": False,
        "manifest_written_by_receipt": False,
        "cleanup_delete_generated_by_receipt": False,
        "cache_get_external_calls": False,
        "receipt_external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "production_blocker_count": int(blocker_audit.get("blocking_criterion_count") or 0),
        "blocked_activation_count": len(blockers),
        "blocked_activation": blockers,
        "rows": rows,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_physical_migration_activation_receipt",
            endpoint="GET /api/storage",
            status="activation_receipt_ready_physical_execution_pending"
            if local_activation_ready
            else "activation_receipt_blocked_local_contract",
            row_count=len(rows),
        ),
        "note": "This activation receipt identifies LTG-05 physical migration execution prerequisites. It does not write Parquet, validate production promotion, refresh providers, delete files, or trade.",
    }


def _storage_physical_execution_recipe_row(
    phase: str,
    *,
    status: str,
    local_ready: bool,
    evidence: str,
    next_step: str,
    evidence_required: str,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "phase_label": STORAGE_PHYSICAL_EXECUTION_PHASE_LABELS.get(phase, phase),
        "status": status,
        "local_ready": bool(local_ready),
        "execution_done": False,
        "production_ready": False,
        "production_blocker": True,
        "required_before_production": True,
        "evidence_required": evidence_required,
        "evidence": evidence,
        "next_step": next_step,
        "cache_only": True,
        "runs_no_commands": True,
        "writes_parquet": False,
        "writes_manifest": False,
        "reads_row_payloads": False,
        "refreshes_providers": False,
        "deletes_artifacts": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _storage_physical_execution_scope_hash(recipe: Mapping[str, Any]) -> str:
    scope_payload = {
        "schema_version": recipe.get("schema_version"),
        "scope": recipe.get("scope"),
        "status": recipe.get("status"),
        "canonical_datasets": list(CANONICAL_PARQUET_DATASETS),
        "phase_keys": list(recipe.get("phase_keys") or []),
        "allowed_execution_sequence": list(recipe.get("allowed_execution_sequence") or []),
        "local_recipe_ready": bool(recipe.get("local_recipe_ready")),
        "production_storage_complete": bool(recipe.get("production_storage_complete")),
    }
    return _json_sha256(scope_payload)


def storage_physical_execution_recipe(
    production_readiness: Mapping[str, Any] | None = None,
    production_blocker_audit: Mapping[str, Any] | None = None,
    physical_migration_activation_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    readiness = dict(production_readiness or storage_production_readiness())
    blocker_audit = dict(production_blocker_audit or storage_production_blocker_audit(readiness))
    activation_receipt = dict(
        physical_migration_activation_receipt
        or storage_physical_migration_activation_receipt(readiness, blocker_audit)
    )
    dataset_count = int(readiness.get("schema_migration_dataset_count") or len(CANONICAL_PARQUET_DATASETS))
    activation_ready = activation_receipt.get("local_activation_receipt_ready") is True
    cache_get_boundary = (
        readiness.get("external_calls_triggered") is False
        and activation_receipt.get("cache_get_external_calls") is False
        and activation_receipt.get("provider_refresh_called_by_receipt") is False
        and activation_receipt.get("parquet_written_by_receipt") is False
        and activation_receipt.get("cleanup_delete_generated_by_receipt") is False
    )
    required_task_boundaries_ready = all(
        readiness.get(key) is True
        for key in (
            "schema_validation_acceptance_button_gated",
            "dataset_version_manifest_write_button_gated",
            "dataset_version_manifest_validate_button_gated",
            "partition_migration_dry_run_button_gated",
            "compaction_dry_run_button_gated",
            "cache_ttl_dry_run_button_gated",
            "artifact_cleanup_dry_run_button_gated",
        )
    )
    manifest_guarded = (
        readiness.get("dataset_version_manifest_write_requires_confirm") is True
        and readiness.get("dataset_version_manifest_write_writes_manifest") is True
        and readiness.get("dataset_version_manifest_write_writes_parquet") is False
        and readiness.get("dataset_version_manifest_validate_writes_manifest") is False
        and readiness.get("dataset_version_manifest_validate_writes_parquet") is False
    )
    duckdb_boundary = readiness.get("duckdb_query_service_status") in {"service_ready", "dependency_missing"}
    schema_acceptance_done = readiness.get("physical_schema_validation_done") is True
    recipe_ready = bool(activation_ready and cache_get_boundary and required_task_boundaries_ready and manifest_guarded)
    rows = [
        _storage_physical_execution_recipe_row(
            "physical_schema_validation_acceptance",
            status=(
                "accepted_physical_schema_evidence_present"
                if schema_acceptance_done
                else "ready_for_explicit_acceptance_review"
                if readiness.get("schema_validation_acceptance_button_gated")
                else "blocked_missing_schema_acceptance_task"
            ),
            local_ready=readiness.get("schema_validation_acceptance_button_gated") is True,
            evidence=f"physical_schema_validation_done_count={readiness.get('physical_schema_validation_done_count')}/{dataset_count}",
            evidence_required="accepted schema-validation packet for every canonical dataset",
            next_step="Run explicit schema validation acceptance and review all dataset rows before any writer task.",
        ),
        _storage_physical_execution_recipe_row(
            "dataset_version_manifest_write_validate",
            status="ready_for_confirm_gated_manifest_write_then_validate" if manifest_guarded else "blocked_manifest_guard_missing",
            local_ready=manifest_guarded,
            evidence=(
                f"manifest_write_requires_confirm={readiness.get('dataset_version_manifest_write_requires_confirm')}; "
                f"manifest_validate_requires_prior_write={readiness.get('dataset_version_manifest_validate_requires_prior_write')}"
            ),
            evidence_required="confirm-gated manifest write receipt plus read-only manifest validation receipt",
            next_step="Write only the ignored _dataset_versions.json after review, then validate it in a separate POST task.",
        ),
        _storage_physical_execution_recipe_row(
            "schema_migration_execution_plan",
            status="pending_physical_writer_design",
            local_ready=activation_ready,
            evidence=f"schema_migration_executed_count={readiness.get('schema_migration_executed_count')}/{dataset_count}",
            evidence_required="manual schema migration writer evidence with before/after schema metadata",
            next_step="Design a separate confirm-gated schema migration writer only after schema acceptance and manifest validation.",
        ),
        _storage_physical_execution_recipe_row(
            "partition_migration_execution_plan",
            status="pending_partition_writer_design",
            local_ready=readiness.get("partition_migration_dry_run_button_gated") is True,
            evidence="partition migration is currently dry-run only.",
            evidence_required="partition writer receipt plus physical partition metadata validation",
            next_step="Promote from dry-run to a confirm-gated partition writer only when dataset version evidence is stable.",
        ),
        _storage_physical_execution_recipe_row(
            "physical_compaction_execution_plan",
            status="pending_compaction_executor",
            local_ready=readiness.get("compaction_dry_run_button_gated") is True,
            evidence=f"compaction_executed_count={readiness.get('compaction_executed_count')}",
            evidence_required="physical compaction task ledger and rewritten artifact metadata",
            next_step="Run compaction only through a separate maintenance task after partition/schema migration evidence exists.",
        ),
        _storage_physical_execution_recipe_row(
            "cache_ttl_refresh_execution_plan",
            status="pending_provider_refresh_acceptance",
            local_ready=readiness.get("cache_ttl_dry_run_button_gated") is True,
            evidence=f"cache_ttl_refresh_executed_count={readiness.get('cache_ttl_refresh_executed_count')}",
            evidence_required="explicit provider refresh task ledger and local fetched-at/date evidence",
            next_step="Bind TTL refresh execution to provider acceptance tasks; never refresh providers from GET cache.",
        ),
        _storage_physical_execution_recipe_row(
            "artifact_cleanup_delete_review",
            status="pending_manual_cleanup_approval",
            local_ready=readiness.get("artifact_cleanup_manual_review_required") is True,
            evidence=(
                f"cleanup_review_status={readiness.get('artifact_cleanup_review_status')}; "
                f"delete_executed_count={readiness.get('artifact_cleanup_delete_executed_count')}"
            ),
            evidence_required="manual cleanup approval plus separate delete execution receipt if cleanup is needed",
            next_step="Review cleanup candidates manually; do not generate delete commands from dry-run output.",
        ),
        _storage_physical_execution_recipe_row(
            "duckdb_post_migration_validation",
            status="ready_or_dependency_pending_for_read_only_validation",
            local_ready=duckdb_boundary,
            evidence=f"duckdb_query_service_status={readiness.get('duckdb_query_service_status')}",
            evidence_required="post-migration DuckDB read-only query result contract for canonical datasets",
            next_step="Use FastAPI/DuckDB read wrappers to validate migrated datasets without frontend DataFrame access.",
        ),
        _storage_physical_execution_recipe_row(
            "production_promotion_review",
            status="blocked_until_all_physical_evidence_passes",
            local_ready=False,
            evidence=f"production_blocker_count={blocker_audit.get('blocking_criterion_count')}",
            evidence_required="all physical execution receipts plus release review proving production_storage_complete may flip",
            next_step="Promote production storage only after every physical evidence row is direct and reviewed.",
        ),
    ]
    pending_phases = [row["phase"] for row in rows if not row.get("execution_done")]
    local_blockers = [row["phase"] for row in rows if not row.get("local_ready")]
    status = "storage_physical_execution_recipe_ready_execution_pending" if recipe_ready else "storage_physical_execution_recipe_blocked"
    recipe = {
        "schema_version": "command_center_3_storage_physical_execution_recipe.v1",
        "scope": "local_storage_physical_execution_recipe_no_write_no_provider",
        "status": status,
        "ltg": "LTG-05/LTG-11",
        "local_recipe_ready": recipe_ready,
        "execution_done": False,
        "physical_execution_done": False,
        "production_storage_complete": False,
        "requires_explicit_post_sequence": True,
        "requires_manual_review": True,
        "canonical_dataset_count": dataset_count,
        "phase_count": len(rows),
        "pending_phase_count": len(pending_phases),
        "local_blocker_count": len(local_blockers),
        "phase_keys": [row["phase"] for row in rows],
        "pending_phases": pending_phases,
        "local_blockers": local_blockers,
        "allowed_execution_sequence": list(STORAGE_PHYSICAL_EXECUTION_PHASES),
        "required_evidence": [
            "schema validation acceptance packet",
            "confirm-gated dataset version manifest write receipt",
            "manifest validation receipt",
            "schema migration before/after metadata",
            "partition migration artifact metadata",
            "physical compaction ledger",
            "TTL refresh/provider task ledger",
            "cleanup approval/delete receipt if needed",
            "DuckDB post-migration query contract",
            "production promotion review",
        ],
        "not_allowed_next_steps": [
            "treat_recipe_as_physical_execution_evidence",
            "write_parquet_from_get_storage_cache",
            "refresh_providers_from_get_storage_cache",
            "delete_artifacts_from_dry_run",
            "promote_storage_without_manifest_validation",
            "mark_production_storage_complete_from_preflight_or_dry_run",
        ],
        "cache_only": True,
        "runs_no_commands": True,
        "writes_parquet": False,
        "writes_manifest": False,
        "reads_row_payloads": False,
        "refreshes_providers": False,
        "deletes_artifacts": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_physical_execution_recipe",
            endpoint="GET /api/storage",
            status=status,
            row_count=len(rows),
        ),
        "note": "This recipe sequences LTG-05 physical storage execution. It does not write Parquet, write manifests, refresh providers, delete artifacts, run commands, trade, or complete production storage.",
    }
    scope_hash = _storage_physical_execution_scope_hash(recipe)
    recipe["physical_execution_scope_hash"] = scope_hash
    recipe["physical_execution_scope_hash_short"] = scope_hash[:12]
    return recipe


def _storage_physical_durable_evidence_recipe_row(
    evidence_key: str,
    *,
    passed: bool,
    evidence: str,
    required_evidence: str,
    next_step: str,
    source_contract: str,
    status: str | None = None,
) -> dict[str, Any]:
    return {
        "evidence_key": evidence_key,
        "evidence_label": STORAGE_PHYSICAL_DURABLE_EVIDENCE_LABELS.get(evidence_key, evidence_key),
        "status": status or ("passed" if passed else "blocked"),
        "passed": bool(passed),
        "local_ready": bool(passed),
        "durable_evidence_present": False if not passed else True,
        "production_ready": False,
        "production_blocker": not passed,
        "required_before_production": True,
        "required_evidence": required_evidence,
        "evidence": evidence,
        "next_step": next_step,
        "source_contract": source_contract,
        "cache_only": True,
        "runs_no_commands": True,
        "writes_parquet": False,
        "writes_manifest": False,
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def storage_physical_durable_evidence_recipe(
    production_readiness: Mapping[str, Any] | None = None,
    production_blocker_audit: Mapping[str, Any] | None = None,
    physical_migration_activation_receipt: Mapping[str, Any] | None = None,
    physical_execution_recipe: Mapping[str, Any] | None = None,
    physical_execution_request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    readiness = dict(production_readiness or storage_production_readiness())
    blocker_audit = dict(production_blocker_audit or storage_production_blocker_audit(readiness))
    activation_receipt = dict(
        physical_migration_activation_receipt
        or storage_physical_migration_activation_receipt(readiness, blocker_audit)
    )
    execution_recipe = dict(
        physical_execution_recipe
        or storage_physical_execution_recipe(readiness, blocker_audit, activation_receipt)
    )
    execution_request = dict(physical_execution_request or storage_physical_execution_request_evidence())
    current_result_atomic_promotion = storage_current_result_atomic_promotion_evidence()
    production_promotion_review = storage_production_promotion_review_evidence()
    manifest_validation = storage_dataset_version_manifest_validate_evidence()
    schema_migration_execution = storage_schema_migration_execution_evidence()
    duckdb_read_validation = storage_duckdb_read_validation_evidence()
    artifact_hygiene = storage_artifact_hygiene_status()
    cleanup_review = dict(artifact_hygiene.get("artifact_cleanup_review_contract") or {})
    partition_packet, _partition_read_status = _read_storage_meta_packet_no_init(PARTITION_MIGRATION_DRY_RUN_PACKET_KEY)
    compaction_packet, _compaction_read_status = _read_storage_meta_packet_no_init(COMPACTION_DRY_RUN_PACKET_KEY)
    cache_ttl_packet, _cache_ttl_read_status = _read_storage_meta_packet_no_init(CACHE_TTL_DRY_RUN_PACKET_KEY)
    partition_execution = storage_partition_migration_execution_evidence()
    compaction_execution = storage_compaction_execution_evidence()
    partition_migration_metadata = dict(partition_packet) if isinstance(partition_packet, Mapping) else {}
    compaction_metadata = dict(compaction_packet) if isinstance(compaction_packet, Mapping) else {}
    cache_ttl_metadata = dict(cache_ttl_packet) if isinstance(cache_ttl_packet, Mapping) else {}
    blocker_audit_visible = blocker_audit.get("schema_version") == STORAGE_PRODUCTION_BLOCKER_SCHEMA_VERSION
    readiness_visible = readiness.get("status") in {"foundation_ready", "partial_dependency_missing"}
    activation_visible = activation_receipt.get("local_activation_receipt_ready") is True
    execution_ready = execution_recipe.get("local_recipe_ready") is True
    execution_request_visible = (
        execution_request.get("schema_version") == "command_center_3_storage_physical_execution_request.v1"
        and execution_request.get("local_execution_request_ready") is True
        and execution_request.get("requested_scope_hash_matches_latest") is True
        and execution_request.get("physical_task_created") is False
        and execution_request.get("physical_task_executed") is False
    )
    current_result_atomic_receipt_direct_evidence = bool(
        current_result_atomic_promotion.get("latest_receipt_status")
        == "storage_current_result_atomic_promotion_success"
        and current_result_atomic_promotion.get("atomic_promotion_current") is True
        and current_result_atomic_promotion.get("physical_write_executed") is True
        and current_result_atomic_promotion.get("latest_receipt_task_id")
        and current_result_atomic_promotion.get("expected_symbol")
        and current_result_atomic_promotion.get("expected_result_version")
        and current_result_atomic_promotion.get("last_good_pointer_ready") is True
        and current_result_atomic_promotion.get("current_last_good_distinct") is True
        and current_result_atomic_promotion.get("duckdb_readback_verified") is True
        and current_result_atomic_promotion.get("manifest_current_version_ready") is True
        and current_result_atomic_promotion.get("cache_get_writes_files") is False
        and current_result_atomic_promotion.get("production_storage_complete") is False
        and current_result_atomic_promotion.get("external_calls_triggered") is False
        and current_result_atomic_promotion.get("tushare_called") is False
        and current_result_atomic_promotion.get("deepseek_called") is False
        and current_result_atomic_promotion.get("github_called") is False
        and current_result_atomic_promotion.get("does_not_execute_trades") is True
        and current_result_atomic_promotion.get("does_not_modify_strategy_action") is True
        and current_result_atomic_promotion.get("contains_secret") is False
    )
    current_result_atomic_promotion_done = bool(
        current_result_atomic_promotion.get("status")
        == "storage_current_result_atomic_promotion_current"
        and (
            current_result_atomic_promotion.get("canonical_lineage_ready") is True
            or current_result_atomic_receipt_direct_evidence
        )
        and current_result_atomic_promotion.get("atomic_promotion_current") is True
        and current_result_atomic_promotion.get("physical_write_executed") is True
        and bool(current_result_atomic_promotion.get("latest_receipt_task_id"))
        and bool(current_result_atomic_promotion.get("expected_symbol"))
        and bool(current_result_atomic_promotion.get("expected_result_version"))
        and current_result_atomic_promotion.get("duckdb_readback_verified") is True
        and current_result_atomic_promotion.get("manifest_current_version_ready") is True
        and current_result_atomic_promotion.get("cache_get_writes_files") is False
        and current_result_atomic_promotion.get("production_storage_complete") is False
        and current_result_atomic_promotion.get("external_calls_triggered") is False
        and current_result_atomic_promotion.get("tushare_called") is False
        and current_result_atomic_promotion.get("deepseek_called") is False
        and current_result_atomic_promotion.get("github_called") is False
        and current_result_atomic_promotion.get("does_not_execute_trades") is True
        and current_result_atomic_promotion.get("does_not_modify_strategy_action") is True
        and current_result_atomic_promotion.get("contains_secret") is False
    )
    current_result_storage_acceptance_ready = bool(
        current_result_atomic_promotion_done
        and current_result_atomic_promotion.get("current_result_storage_acceptance_ready") is True
        and current_result_atomic_promotion.get("last_good_pointer_ready") is True
        and current_result_atomic_promotion.get("retention_protects_current_and_last_good") is True
    )
    no_external_boundary = (
        execution_recipe.get("external_calls_triggered") is False
        and execution_recipe.get("tushare_called") is False
        and execution_recipe.get("deepseek_called") is False
        and execution_recipe.get("github_called") is False
        and execution_request.get("external_calls_triggered") is False
        and execution_request.get("tushare_called") is False
        and execution_request.get("deepseek_called") is False
        and execution_request.get("github_called") is False
        and execution_recipe.get("does_not_execute_trades") is True
        and execution_recipe.get("does_not_modify_strategy_action") is True
        and execution_recipe.get("contains_secret") is False
        and execution_request.get("does_not_execute_trades") is True
        and execution_request.get("does_not_modify_strategy_action") is True
        and execution_request.get("contains_secret") is False
        and production_promotion_review.get("external_calls_triggered") is False
        and production_promotion_review.get("tushare_called") is False
        and production_promotion_review.get("deepseek_called") is False
        and production_promotion_review.get("github_called") is False
        and production_promotion_review.get("does_not_execute_trades") is True
        and production_promotion_review.get("does_not_modify_strategy_action") is True
        and production_promotion_review.get("contains_secret") is False
    )
    local_recipe_ready = bool(blocker_audit_visible and readiness_visible and activation_visible and execution_ready and no_external_boundary)
    schema_acceptance_done = readiness.get("physical_schema_validation_done") is True
    schema_acceptance_status = readiness.get("schema_validation_acceptance_evidence_status")
    manifest_validation_done = bool(
        manifest_validation.get("schema_version") == "command_center_3_storage_dataset_version_manifest_validate.v1"
        and manifest_validation.get("status") == "manifest_validate_passed_local_only"
        and manifest_validation.get("dataset_version_manifest_validated") is True
        and int(manifest_validation.get("validated_dataset_count") or 0) > 0
        and int(manifest_validation.get("validated_dataset_count") or 0)
        == int(manifest_validation.get("dataset_count") or 0)
        and manifest_validation.get("manifest_write_executed") is False
        and manifest_validation.get("manifest_written_on_post") is False
        and manifest_validation.get("post_validate_writes_manifest") is False
        and manifest_validation.get("post_validate_writes_parquet") is False
        and manifest_validation.get("post_validate_reads_parquet_payloads") is False
        and manifest_validation.get("post_validate_reads_env_files") is False
        and manifest_validation.get("schema_migration_executed") is False
        and manifest_validation.get("partition_migration_executed") is False
        and manifest_validation.get("physical_compaction_executed") is False
        and manifest_validation.get("cache_ttl_refresh_executed") is False
        and manifest_validation.get("production_storage_complete") is False
        and manifest_validation.get("external_calls_triggered") is False
        and manifest_validation.get("tushare_called") is False
        and manifest_validation.get("deepseek_called") is False
        and manifest_validation.get("github_called") is False
        and manifest_validation.get("does_not_execute_trades") is True
        and manifest_validation.get("does_not_modify_strategy_action") is True
        and manifest_validation.get("contains_secret") is False
    )
    schema_migration_done = bool(
        schema_migration_execution.get("schema_version")
        == "command_center_3_storage_schema_migration_execution.v1"
        and schema_migration_execution.get("status") == "schema_migration_execution_completed_noop_verified"
        and schema_migration_execution.get("schema_migration_executed") is True
        and schema_migration_execution.get("schema_migration_noop_verified") is True
        and schema_migration_execution.get("schema_migration_rewrite_executed") is False
        and int(schema_migration_execution.get("dataset_count") or 0) > 0
        and int(schema_migration_execution.get("schema_migration_executed_count") or 0)
        == int(schema_migration_execution.get("dataset_count") or 0)
        and schema_migration_execution.get("post_task_writes_manifest") is False
        and schema_migration_execution.get("post_task_writes_parquet") is False
        and schema_migration_execution.get("post_task_reads_row_payloads") is False
        and schema_migration_execution.get("cache_get_writes_files") is False
        and schema_migration_execution.get("production_storage_complete") is False
        and schema_migration_execution.get("external_calls_triggered") is False
        and schema_migration_execution.get("tushare_called") is False
        and schema_migration_execution.get("deepseek_called") is False
        and schema_migration_execution.get("github_called") is False
        and schema_migration_execution.get("does_not_execute_trades") is True
        and schema_migration_execution.get("does_not_modify_strategy_action") is True
        and schema_migration_execution.get("contains_secret") is False
    )
    duckdb_read_validation_done = bool(
        duckdb_read_validation.get("schema_version") == "command_center_3_storage_duckdb_read_validation.v1"
        and duckdb_read_validation.get("status") == "storage_duckdb_read_validation_ready_local_query_contract"
        and duckdb_read_validation.get("local_duckdb_read_validation_ready") is True
        and duckdb_read_validation.get("duckdb_dependency_available") is True
        and int(duckdb_read_validation.get("dataset_count") or 0) > 0
        and int(duckdb_read_validation.get("contract_ready_count") or 0)
        == int(duckdb_read_validation.get("dataset_count") or 0)
        and duckdb_read_validation.get("query_result_contract_schema_version") == "duckdb_query_result_contract.v1"
        and duckdb_read_validation.get("query_wrapper") == "duckdb_filtered_parquet.v1"
        and duckdb_read_validation.get("safe_parameter_binding") is True
        and duckdb_read_validation.get("typed_projection_enabled") is True
        and duckdb_read_validation.get("cursor_pagination_enabled") is True
        and duckdb_read_validation.get("frontend_executes_query") is False
        and duckdb_read_validation.get("cache_get_writes_files") is False
        and duckdb_read_validation.get("writes_parquet_on_get") is False
        and duckdb_read_validation.get("writes_parquet") is False
        and duckdb_read_validation.get("writes_manifest") is False
        and duckdb_read_validation.get("deletes_artifacts") is False
        and duckdb_read_validation.get("refreshes_providers") is False
        and duckdb_read_validation.get("schema_migration_executed") is False
        and duckdb_read_validation.get("partition_migration_executed") is False
        and duckdb_read_validation.get("physical_compaction_executed") is False
        and duckdb_read_validation.get("cache_ttl_refresh_executed") is False
        and duckdb_read_validation.get("artifact_cleanup_delete_executed") is False
        and duckdb_read_validation.get("post_migration_validation_done") is False
        and duckdb_read_validation.get("production_storage_complete") is False
        and duckdb_read_validation.get("external_calls_triggered") is False
        and duckdb_read_validation.get("tushare_called") is False
        and duckdb_read_validation.get("deepseek_called") is False
        and duckdb_read_validation.get("github_called") is False
        and duckdb_read_validation.get("does_not_execute_trades") is True
        and duckdb_read_validation.get("does_not_modify_strategy_action") is True
        and duckdb_read_validation.get("contains_secret") is False
    )
    artifact_cleanup_review_done = bool(
        cleanup_review.get("schema_version") == ARTIFACT_CLEANUP_REVIEW_SCHEMA_VERSION
        and cleanup_review.get("status") in {"manual_review_ready_delete_pending", "manual_review_ready_no_candidates"}
        and cleanup_review.get("artifact_cleanup_review_done") is True
        and int(cleanup_review.get("required_review_step_count") or 0) > 0
        and cleanup_review.get("manual_approval_required") is True
        and cleanup_review.get("dry_run_required_before_delete") is True
        and cleanup_review.get("delete_execution_task_available") is False
        and cleanup_review.get("delete_executed") is False
        and int(cleanup_review.get("delete_executed_count") or 0) == 0
        and cleanup_review.get("safe_delete_command_generated") is False
        and cleanup_review.get("delete_command_not_generated") is True
        and cleanup_review.get("cleanup_review_is_not_delete_execution") is True
        and cleanup_review.get("production_cleanup_complete") is False
        and cleanup_review.get("reads_payloads") is False
        and cleanup_review.get("reads_file_payloads") is False
        and cleanup_review.get("reads_env_files") is False
        and cleanup_review.get("scans_secret_values") is False
        and cleanup_review.get("does_not_scan_secret_values") is True
        and cleanup_review.get("external_calls_triggered") is False
        and cleanup_review.get("tushare_called") is False
        and cleanup_review.get("deepseek_called") is False
        and cleanup_review.get("github_called") is False
        and cleanup_review.get("does_not_execute_trades") is True
        and cleanup_review.get("does_not_modify_strategy_action") is True
        and cleanup_review.get("contains_secret") is False
    )
    partition_migration_metadata_validation_done = bool(
        partition_migration_metadata.get("schema_version") == "command_center_3_storage_partition_migration_dry_run.v1"
        and partition_migration_metadata.get("status") == "dry_run_completed"
        and partition_migration_metadata.get("partition_migration_metadata_validation_done") is True
        and int(partition_migration_metadata.get("dataset_count") or 0) > 0
        and int(partition_migration_metadata.get("partition_migration_metadata_validated_count") or 0)
        == int(partition_migration_metadata.get("dataset_count") or 0)
        and int(partition_migration_metadata.get("partition_migration_blocked_count") or 0) == 0
        and partition_migration_metadata.get("partition_migration_executed") is False
        and int(partition_migration_metadata.get("partition_migration_executed_count") or 0) == 0
        and partition_migration_metadata.get("post_dry_run_writes_parquet") is False
        and partition_migration_metadata.get("post_dry_run_reads_row_payloads") is False
        and partition_migration_metadata.get("post_dry_run_reads_env_files") is False
        and partition_migration_metadata.get("cache_get_writes_files") is False
        and partition_migration_metadata.get("external_calls_triggered") is False
        and partition_migration_metadata.get("tushare_called") is False
        and partition_migration_metadata.get("deepseek_called") is False
        and partition_migration_metadata.get("github_called") is False
        and partition_migration_metadata.get("does_not_execute_trades") is True
        and partition_migration_metadata.get("contains_secret") is False
    )
    partition_migration_execution_done = bool(
        partition_execution.get("schema_version") == "command_center_3_storage_partition_migration_execution.v1"
        and partition_execution.get("status") == "partition_migration_execution_complete"
        and partition_execution.get("partition_migration_executed") is True
        and int(partition_execution.get("partition_migration_executed_count") or 0)
        == int(partition_execution.get("dataset_count") or 0)
        and int(partition_execution.get("dataset_count") or 0) > 0
        and all(
            row.get("partition_migration_executed") is True
            and row.get("schema_columns_match") is True
            and row.get("row_count_match") is True
            and row.get("target_tree_sha256")
            for row in partition_execution.get("rows") or []
            if isinstance(row, Mapping)
        )
        and partition_execution.get("writes_parquet") is True
        and partition_execution.get("external_calls_triggered") is False
        and partition_execution.get("tushare_called") is False
        and partition_execution.get("deepseek_called") is False
        and partition_execution.get("github_called") is False
        and partition_execution.get("does_not_execute_trades") is True
        and partition_execution.get("contains_secret") is False
    )
    physical_compaction_execution_done = bool(
        compaction_execution.get("schema_version") == "command_center_3_storage_compaction_execution.v1"
        and compaction_execution.get("status") == "physical_compaction_execution_complete"
        and compaction_execution.get("physical_compaction_executed") is True
        and int(compaction_execution.get("physical_compaction_executed_count") or 0)
        == int(compaction_execution.get("dataset_count") or 0)
        and int(compaction_execution.get("dataset_count") or 0) > 0
        and all(
            row.get("physical_compaction_executed") is True
            and row.get("schema_columns_match") is True
            and row.get("row_count_match") is True
            and len(str(row.get("target_tree_sha256") or "")) == 64
            and all(char in "0123456789abcdef" for char in str(row.get("target_tree_sha256") or "").lower())
            and row.get("reads_row_payloads") is True
            and row.get("writes_parquet") is True
            and row.get("external_calls_triggered") is False
            and row.get("does_not_execute_trades") is True
            and row.get("does_not_modify_strategy_action") is True
            and row.get("contains_secret") is False
            for row in compaction_execution.get("rows") or []
            if isinstance(row, Mapping)
        )
        and compaction_execution.get("writes_parquet") is True
        and compaction_execution.get("reads_row_payloads") is True
        and compaction_execution.get("external_calls_triggered") is False
        and compaction_execution.get("tushare_called") is False
        and compaction_execution.get("deepseek_called") is False
        and compaction_execution.get("github_called") is False
        and compaction_execution.get("does_not_execute_trades") is True
        and compaction_execution.get("does_not_modify_strategy_action") is True
        and compaction_execution.get("contains_secret") is False
    )
    physical_compaction_metadata_validation_done = bool(
        compaction_metadata.get("schema_version") == "command_center_3_storage_compaction_dry_run.v1"
        and compaction_metadata.get("status") == "dry_run_completed"
        and compaction_metadata.get("physical_compaction_metadata_validation_done") is True
        and int(compaction_metadata.get("dataset_count") or 0) > 0
        and int(compaction_metadata.get("physical_compaction_metadata_validated_count") or 0)
        == int(compaction_metadata.get("dataset_count") or 0)
        and int(compaction_metadata.get("compaction_not_needed_count") or 0)
        == int(compaction_metadata.get("dataset_count") or 0)
        and int(compaction_metadata.get("compaction_ready_count") or 0) == 0
        and int(compaction_metadata.get("compaction_blocked_count") or 0) == 0
        and int(compaction_metadata.get("missing_dataset_count") or 0) == 0
        and compaction_metadata.get("physical_compaction_executed") is False
        and compaction_metadata.get("compaction_executed") is False
        and int(compaction_metadata.get("compaction_executed_count") or 0) == 0
        and compaction_metadata.get("post_dry_run_writes_parquet") is False
        and compaction_metadata.get("post_dry_run_reads_row_payloads") is False
        and compaction_metadata.get("post_dry_run_reads_env_files") is False
        and compaction_metadata.get("cache_get_writes_files") is False
        and compaction_metadata.get("external_calls_triggered") is False
        and compaction_metadata.get("tushare_called") is False
        and compaction_metadata.get("deepseek_called") is False
        and compaction_metadata.get("github_called") is False
        and compaction_metadata.get("does_not_execute_trades") is True
        and compaction_metadata.get("contains_secret") is False
    )
    cache_ttl_refresh_metadata_validation_done = bool(
        cache_ttl_metadata.get("schema_version") == "command_center_3_storage_cache_ttl_dry_run.v1"
        and cache_ttl_metadata.get("status") == "dry_run_completed"
        and int(cache_ttl_metadata.get("dataset_count") or 0) > 0
        and int(cache_ttl_metadata.get("refresh_executed_count") or 0) == 0
        and cache_ttl_metadata.get("refresh_executed") is False
        and cache_ttl_metadata.get("auto_refresh_on_get") is False
        and cache_ttl_metadata.get("post_dry_run_writes_parquet") is False
        and cache_ttl_metadata.get("post_dry_run_reads_row_payloads") is False
        and cache_ttl_metadata.get("post_dry_run_reads_env_files") is False
        and cache_ttl_metadata.get("cache_get_writes_files") is False
        and cache_ttl_metadata.get("external_calls_triggered") is False
        and cache_ttl_metadata.get("tushare_called") is False
        and cache_ttl_metadata.get("deepseek_called") is False
        and cache_ttl_metadata.get("github_called") is False
        and cache_ttl_metadata.get("does_not_execute_trades") is True
        and cache_ttl_metadata.get("contains_secret") is False
    )
    production_promotion_review_done = bool(
        production_promotion_review.get("schema_version")
        == "command_center_3_storage_production_promotion_review.v1"
        and production_promotion_review.get("status")
        in {
            "storage_production_promotion_review_ready_production_still_blocked",
            "storage_current_result_acceptance_ready_full_storage_pending",
        }
        and production_promotion_review.get("explicit_production_promotion_review_done") is True
        and production_promotion_review.get("local_promotion_review_ready") is True
        and production_promotion_review.get("approved_by_user") is True
        and production_promotion_review.get("requested_physical_execution_scope_hash_matches_latest") is True
        and production_promotion_review.get("physical_execution_request_visible") is True
        and production_promotion_review.get("durable_evidence_recipe_visible") is True
        and production_promotion_review.get("ready_to_mark_production_storage_complete") is False
        and production_promotion_review.get("production_storage_complete") is False
        and production_promotion_review.get("writes_parquet") is False
        and production_promotion_review.get("writes_manifest") is False
        and production_promotion_review.get("deletes_artifacts") is False
        and production_promotion_review.get("refreshes_providers") is False
        and production_promotion_review.get("external_calls_triggered") is False
        and production_promotion_review.get("tushare_called") is False
        and production_promotion_review.get("deepseek_called") is False
        and production_promotion_review.get("github_called") is False
        and production_promotion_review.get("does_not_execute_trades") is True
        and production_promotion_review.get("does_not_modify_strategy_action") is True
        and production_promotion_review.get("contains_secret") is False
    )
    rows = [
        _storage_physical_durable_evidence_recipe_row(
            "production_blocker_audit_visible",
            passed=blocker_audit_visible,
            source_contract="storage_production_blocker_audit",
            evidence=f"status={blocker_audit.get('status')}; blocker_count={blocker_audit.get('blocking_criterion_count')}",
            required_evidence="visible storage_production_blocker_audit with production_storage_complete=false until all physical evidence passes",
            next_step="keep production blockers visible in storage overview and push gate",
        ),
        _storage_physical_durable_evidence_recipe_row(
            "readiness_receipt_visible",
            passed=readiness_visible,
            source_contract="production_readiness",
            evidence=f"production_readiness_status={readiness.get('status')}",
            required_evidence="local production readiness contract with explicit POST-only review boundaries",
            next_step="preserve readiness receipt while physical evidence is collected",
        ),
        _storage_physical_durable_evidence_recipe_row(
            "activation_receipt_visible",
            passed=activation_visible,
            source_contract="storage_physical_migration_activation_receipt",
            evidence=f"activation_status={activation_receipt.get('status')}",
            required_evidence="activation receipt naming schema, manifest, partition, compaction, TTL, cleanup, and promotion prerequisites",
            next_step="use activation receipt as the entry point for future explicit storage tasks",
        ),
        _storage_physical_durable_evidence_recipe_row(
            "physical_execution_recipe_ready",
            passed=execution_ready,
            source_contract="storage_physical_execution_recipe",
            evidence=f"recipe_status={execution_recipe.get('status')}; phase_count={execution_recipe.get('phase_count')}",
            required_evidence="ordered physical execution recipe with every production phase still pending",
            next_step="follow the recipe order without treating it as execution evidence",
        ),
        _storage_physical_durable_evidence_recipe_row(
            "physical_execution_request_visible",
            passed=execution_request_visible,
            source_contract="storage_physical_execution_request",
            evidence=(
                f"request_status={execution_request.get('status')}; "
                f"scope_hash_short={execution_request.get('physical_execution_scope_hash_short')}"
            ),
            required_evidence="button-gated execution-request ticket bound to the current physical execution recipe scope hash",
            next_step="generate a request ticket from the current recipe before future physical storage tasks",
        ),
        _storage_physical_durable_evidence_recipe_row(
            "current_result_atomic_parquet_promotion_required",
            passed=current_result_atomic_promotion_done,
            source_contract="storage_current_result_atomic_promotion_evidence",
            status="passed_local_atomic_parquet_direct_evidence"
            if current_result_atomic_promotion_done
            else "blocked_atomic_parquet_promotion_missing",
            evidence=(
                f"status={current_result_atomic_promotion.get('status')}; "
                f"task_id={current_result_atomic_promotion.get('latest_receipt_task_id')}; "
                f"symbol={current_result_atomic_promotion.get('expected_symbol')}; "
                f"result_version={current_result_atomic_promotion.get('expected_result_version')}; "
                f"duckdb_readback_verified={current_result_atomic_promotion.get('duckdb_readback_verified')}; "
                f"manifest_current_version_ready={current_result_atomic_promotion.get('manifest_current_version_ready')}"
            ),
            required_evidence="explicit canonical-result immutable Parquet write with atomic current and preserved last-good pointers",
            next_step=(
                "Keep this as one L3 physical-write stage; continue the remaining storage stages and release review."
                if current_result_atomic_promotion_done
                else "confirm a canonical result, then use the explicit atomic promotion button"
            ),
        ),
        _storage_physical_durable_evidence_recipe_row(
            "physical_schema_validation_evidence_required",
            passed=schema_acceptance_done,
            source_contract="schema_validation_acceptance",
            evidence=(
                f"acceptance_status={schema_acceptance_status}; "
                f"physical_schema_validation_done_count={readiness.get('physical_schema_validation_done_count')}"
            ),
            required_evidence="accepted physical schema validation packet for every canonical dataset",
            next_step="run explicit schema validation acceptance before any writer or migration task",
        ),
        _storage_physical_durable_evidence_recipe_row(
            "dataset_version_manifest_validation_required",
            passed=manifest_validation_done,
            source_contract="dataset_version_manifest_validate",
            evidence=(
                f"manifest_validate_status={manifest_validation.get('status')}; "
                f"validated_count={manifest_validation.get('validated_dataset_count')}"
            ),
            required_evidence="confirm-gated manifest write receipt plus read-only manifest validation receipt",
            next_step=(
                "Keep this as read-only manifest validation evidence; manifest write and production promotion remain separate."
                if manifest_validation_done
                else "validate an ignored local manifest only after schema acceptance evidence is reviewed"
            ),
        ),
        _storage_physical_durable_evidence_recipe_row(
            "partition_migration_evidence_required",
            passed=partition_migration_execution_done,
            source_contract="partition_migration_execution",
            status="passed_partition_writer_readback"
            if partition_migration_execution_done
            else "passed_metadata_validation_execution_pending"
            if partition_migration_metadata_validation_done
            else "blocked",
            evidence=(
                f"partition_metadata_validated_count={partition_migration_metadata.get('partition_migration_metadata_validated_count')}; "
                f"dataset_count={partition_migration_metadata.get('dataset_count')}; "
                f"partition_migration_executed_count={partition_execution.get('partition_migration_executed_count')}; "
                f"execution_status={partition_execution.get('status')}"
            ),
            required_evidence="partition writer receipt plus partition metadata validation",
            next_step=(
                "Keep partitioned targets, source files, and readback hashes bound to this scope; production promotion remains separate."
                if partition_migration_execution_done
                else "Keep partition metadata validation as local direct evidence; any physical partition writer remains a separate approval."
                if partition_migration_metadata_validation_done
                else "design a separate confirm-gated partition writer after manifest evidence is stable"
            ),
        ),
        _storage_physical_durable_evidence_recipe_row(
            "physical_compaction_evidence_required",
            passed=physical_compaction_execution_done or physical_compaction_metadata_validation_done,
            source_contract="physical_compaction_execution",
            status="passed_compaction_writer_readback"
            if physical_compaction_execution_done
            else "passed_no_compaction_needed_metadata_validated"
            if physical_compaction_metadata_validation_done
            else "blocked",
            evidence=(
                f"execution_status={compaction_execution.get('status')}; "
                f"execution_count={compaction_execution.get('physical_compaction_executed_count')}; "
                f"compaction_not_needed_count={compaction_metadata.get('compaction_not_needed_count')}; "
                f"dataset_count={compaction_metadata.get('dataset_count')}; "
                f"compaction_executed_count={compaction_metadata.get('compaction_executed_count')}"
            ),
            required_evidence="physical compaction task ledger and rewritten artifact metadata",
            next_step=(
                "Keep compacted targets and readback hashes bound to this scope; TTL/provider refresh remains separate."
                if physical_compaction_execution_done
                else "Keep no-compaction-needed metadata as local evidence; any future rewrite still needs a separate maintenance task."
            ),
        ),
        _storage_physical_durable_evidence_recipe_row(
            "cache_ttl_refresh_evidence_required",
            passed=cache_ttl_refresh_metadata_validation_done,
            source_contract="cache_ttl_refresh_execution",
            status="passed_ttl_metadata_validation_refresh_execution_pending"
            if cache_ttl_refresh_metadata_validation_done
            else "blocked",
            evidence=(
                f"refresh_recommended_count={cache_ttl_metadata.get('refresh_recommended_count')}; "
                f"dataset_count={cache_ttl_metadata.get('dataset_count')}; "
                f"refresh_executed_count={cache_ttl_metadata.get('refresh_executed_count')}"
            ),
            required_evidence="explicit provider refresh task ledger and local fetched-at/date evidence",
            next_step=(
                "Keep TTL metadata validation as local direct evidence; provider refresh execution remains explicit and never runs from GET cache."
                if cache_ttl_refresh_metadata_validation_done
                else "bind refresh evidence to provider acceptance tasks; never refresh from GET cache"
            ),
        ),
        _storage_physical_durable_evidence_recipe_row(
            "artifact_cleanup_delete_review_required",
            passed=artifact_cleanup_review_done,
            source_contract="artifact_cleanup_review",
            evidence=(
                f"cleanup_review_status={cleanup_review.get('status')}; "
                f"required_review_step_count={cleanup_review.get('required_review_step_count')}; "
                f"delete_executed_count={cleanup_review.get('delete_executed_count')}"
            ),
            required_evidence="manual cleanup approval and separate delete execution receipt if cleanup is needed",
            next_step=(
                "Keep cleanup review as manual approval evidence only; any real delete still needs a separate approval."
                if artifact_cleanup_review_done
                else "review cleanup candidates manually before any separately approved delete executor"
            ),
        ),
        _storage_physical_durable_evidence_recipe_row(
            "duckdb_post_migration_validation_required",
            passed=duckdb_read_validation_done,
            source_contract="storage_duckdb_read_validation",
            evidence=(
                f"duckdb_read_validation_status={duckdb_read_validation.get('status')}; "
                f"contract_ready_count={duckdb_read_validation.get('contract_ready_count')}"
            ),
            required_evidence="post-migration DuckDB read-only query contract for every canonical dataset",
            next_step=(
                "Keep this as read-only DuckDB query contract evidence; physical writers and promotion remain separate."
                if duckdb_read_validation_done
                else "validate migrated datasets through FastAPI/DuckDB wrappers after physical storage tasks complete"
            ),
        ),
        _storage_physical_durable_evidence_recipe_row(
            "production_promotion_review_required",
            passed=production_promotion_review_done,
            source_contract="storage_production_promotion_review",
            status="review_visible_production_still_blocked" if production_promotion_review_done else "blocked",
            evidence=(
                f"promotion_review_status={production_promotion_review.get('status')}; "
                f"scope_hash_short={production_promotion_review.get('physical_execution_scope_hash_short')}; "
                f"production_blocker_count={production_promotion_review.get('production_blocker_count')}"
            ),
            required_evidence="release review proving production_storage_complete may flip only after all physical evidence passes",
            next_step=(
                "Keep production_storage_complete=false; this review only records the promotion boundary."
                if production_promotion_review_done
                else "hold production_storage_complete=false until explicit promotion review is recorded"
            ),
        ),
        _storage_physical_durable_evidence_recipe_row(
            "no_provider_trade_action_secret_boundary",
            passed=no_external_boundary,
            source_contract="storage_physical_execution_recipe",
            evidence="durable evidence recipe is local/cache-only and does not call providers, models, GitHub, trades, or action mutation.",
            required_evidence="provider/model/GitHub/trade/action/key boundaries remain false in overview, rows, and push gate",
            next_step="preserve no-provider/no-trade/no-secret boundary while adding future explicit execution evidence",
        ),
    ]
    blocked_rows = [row["evidence_key"] for row in rows if row.get("production_blocker")]
    return {
        "schema_version": STORAGE_PHYSICAL_DURABLE_EVIDENCE_SCHEMA_VERSION,
        "scope": "local_storage_physical_durable_evidence_recipe_no_write_no_delete_no_provider",
        "status": (
            "storage_current_result_direct_evidence_complete_full_migration_pending"
            if current_result_storage_acceptance_ready and production_promotion_review_done
            else "storage_physical_durable_evidence_recipe_ready_production_pending"
            if local_recipe_ready
            else "storage_physical_durable_evidence_recipe_blocked_local_contract"
        ),
        "ltg": "LTG-05/LTG-11",
        "local_recipe_ready": local_recipe_ready,
        "durable_evidence_complete": False,
        "durable_promotion_ready": False,
        "current_result_storage_acceptance_ready": bool(
            current_result_storage_acceptance_ready and production_promotion_review_done
        ),
        "current_result_storage_direct_evidence_complete": current_result_storage_acceptance_ready,
        "full_storage_migration_pending": True,
        "production_storage_complete": False,
        "physical_execution_request_ready": execution_request_visible,
        "physical_execution_request_status": execution_request.get("status"),
        "current_result_atomic_parquet_promotion_done": current_result_atomic_promotion_done,
        "current_result_atomic_receipt_direct_evidence": current_result_atomic_receipt_direct_evidence,
        "current_result_atomic_parquet_promotion_status": current_result_atomic_promotion.get("status"),
        "current_result_atomic_parquet_task_id": current_result_atomic_promotion.get(
            "latest_receipt_task_id"
        ),
        "current_result_atomic_parquet_symbol": current_result_atomic_promotion.get("expected_symbol"),
        "current_result_atomic_parquet_result_version": current_result_atomic_promotion.get(
            "expected_result_version"
        ),
        "current_result_atomic_parquet_duckdb_readback_verified": (
            current_result_atomic_promotion.get("duckdb_readback_verified") is True
        ),
        "current_result_atomic_parquet_manifest_version_ready": (
            current_result_atomic_promotion.get("manifest_current_version_ready") is True
        ),
        "current_result_atomic_parquet_manifest_version_count": int(
            current_result_atomic_promotion.get("manifest_version_count") or 0
        ),
        "physical_schema_validation_done": schema_acceptance_done,
        "schema_validation_acceptance_evidence_status": schema_acceptance_status,
        "schema_migration_executed": schema_migration_done,
        "schema_migration_execution_status": schema_migration_execution.get("status"),
        "schema_migration_noop_verified": bool(
            schema_migration_execution.get("schema_migration_noop_verified") is True
        ),
        "dataset_version_manifest_validated": manifest_validation_done,
        "dataset_version_manifest_validate_status": manifest_validation.get("status"),
        "dataset_version_manifest_validated_count": int(manifest_validation.get("validated_dataset_count") or 0),
        "partition_migration_executed": partition_migration_execution_done,
        "partition_migration_execution_status": partition_execution.get("status"),
        "partition_migration_execution_count": int(partition_execution.get("partition_migration_executed_count") or 0),
        "partition_migration_metadata_validation_done": partition_migration_metadata_validation_done,
        "partition_migration_metadata_validation_status": partition_migration_metadata.get("status"),
        "partition_migration_metadata_validated_count": int(
            partition_migration_metadata.get("partition_migration_metadata_validated_count") or 0
        ),
        "partition_migration_dataset_count": int(partition_migration_metadata.get("dataset_count") or 0),
        "physical_compaction_executed": physical_compaction_execution_done,
        "physical_compaction_execution_status": compaction_execution.get("status"),
        "physical_compaction_execution_count": int(
            compaction_execution.get("physical_compaction_executed_count") or 0
        ),
        "physical_compaction_execution": compaction_execution,
        "physical_compaction_metadata_validation_done": physical_compaction_metadata_validation_done,
        "physical_compaction_metadata_validation_status": compaction_metadata.get("status"),
        "physical_compaction_metadata_validated_count": int(
            compaction_metadata.get("physical_compaction_metadata_validated_count") or 0
        ),
        "physical_compaction_not_needed_count": int(compaction_metadata.get("compaction_not_needed_count") or 0),
        "physical_compaction_dataset_count": int(compaction_metadata.get("dataset_count") or 0),
        "cache_ttl_refresh_executed": False,
        "cache_ttl_refresh_metadata_validation_done": cache_ttl_refresh_metadata_validation_done,
        "cache_ttl_refresh_metadata_validation_status": cache_ttl_metadata.get("status"),
        "cache_ttl_refresh_recommended_count": int(cache_ttl_metadata.get("refresh_recommended_count") or 0),
        "cache_ttl_refresh_executed_count": int(cache_ttl_metadata.get("refresh_executed_count") or 0),
        "cache_ttl_dataset_count": int(cache_ttl_metadata.get("dataset_count") or 0),
        "artifact_cleanup_review_done": artifact_cleanup_review_done,
        "artifact_cleanup_review_status": cleanup_review.get("status"),
        "artifact_cleanup_review_required_step_count": int(cleanup_review.get("required_review_step_count") or 0),
        "artifact_cleanup_delete_executed": False,
        "duckdb_read_validation_done": duckdb_read_validation_done,
        "duckdb_read_validation_status": duckdb_read_validation.get("status"),
        "duckdb_read_validation_contract_ready_count": int(duckdb_read_validation.get("contract_ready_count") or 0),
        "production_promotion_review_done": production_promotion_review_done,
        "production_promotion_review_status": production_promotion_review.get("status"),
        "production_promotion_review_ready": production_promotion_review.get("local_promotion_review_ready") is True,
        "production_promotion_review_production_blocker_count": int(
            production_promotion_review.get("production_blocker_count") or 0
        ),
        "dataset_version_manifest_written_by_recipe": False,
        "physical_task_created_by_request": False,
        "physical_task_executed_by_request": False,
        "provider_refresh_called_by_recipe": False,
        "cache_get_writes_files": False,
        "writes_parquet": False,
        "writes_manifest": False,
        "deletes_artifacts": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "evidence_key_count": len(rows),
        "durable_evidence_blocker_count": len(blocked_rows),
        "production_blocker_count": len(blocked_rows),
        "evidence_keys": [row["evidence_key"] for row in rows],
        "missing_durable_evidence": blocked_rows,
        "required_evidence": [
            "physical schema validation acceptance packet",
            "canonical current-result atomic Parquet promotion receipt and pointer readback",
            "dataset version manifest write and validation receipts",
            "schema migration before/after metadata",
            "partition migration artifact metadata",
            "physical compaction ledger",
            "TTL refresh/provider task ledger",
            "cleanup approval/delete receipt if needed",
            "DuckDB post-migration read-only query contract",
            "production promotion review",
        ],
        "not_allowed_next_steps": [
            "treat_durable_recipe_as_physical_execution",
            "create_storage_write_from_get_cache",
            "write_parquet_from_recipe",
            "write_manifest_from_recipe",
            "delete_artifacts_from_recipe",
            "call_Tushare_from_recipe",
            "call_DeepSeek_from_recipe",
            "call_GitHub_from_recipe",
            "mark_production_storage_complete_from_recipe",
        ],
        "rows": rows,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_physical_durable_evidence_recipe",
            endpoint="GET /api/storage",
            status=(
                "storage_physical_durable_evidence_recipe_ready_production_pending"
                if local_recipe_ready
                else "storage_physical_durable_evidence_recipe_blocked_local_contract"
            ),
            row_count=len(rows),
        ),
        "note": "This durable evidence recipe is a local LTG-05 checklist. It does not write Parquet, write manifests, delete artifacts, refresh providers, call models, call GitHub, trade, mutate strategy action, or complete production storage.",
    }


def _storage_physical_execution_request_row(
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
        "evidence": evidence,
        "next_action": next_action,
        "required_before_physical_execution": True,
        "request_only": True,
        "writes_parquet": False,
        "writes_manifest": False,
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "runs_commands": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def storage_physical_execution_request_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload_safe = payload_safe or {}
    production_readiness = storage_production_readiness()
    blocker_audit = storage_production_blocker_audit(production_readiness)
    readiness_receipt = storage_production_readiness_receipt(production_readiness, blocker_audit)
    activation_receipt = storage_physical_migration_activation_receipt(
        production_readiness,
        blocker_audit,
        readiness_receipt,
    )
    execution_recipe = storage_physical_execution_recipe(
        production_readiness,
        blocker_audit,
        activation_receipt,
    )
    approved_by_user = payload_safe.get("approved_by_user") is True
    latest_scope_hash = str(execution_recipe.get("physical_execution_scope_hash") or "")
    requested_scope_hash = str(payload_safe.get("physical_execution_scope_hash") or payload_safe.get("scope_hash") or "")
    requested_hash_matches_latest = bool(latest_scope_hash and requested_scope_hash == latest_scope_hash)
    recipe_ready = execution_recipe.get("local_recipe_ready") is True
    activation_ready = activation_receipt.get("local_activation_receipt_ready") is True
    if not approved_by_user:
        status = "storage_physical_execution_request_blocked_user_confirmation_required"
    elif not activation_ready:
        status = "storage_physical_execution_request_blocked_activation_receipt"
    elif not recipe_ready:
        status = "storage_physical_execution_request_blocked_recipe_not_ready"
    elif not requested_scope_hash:
        status = "storage_physical_execution_request_blocked_scope_hash_required"
    elif not requested_hash_matches_latest:
        status = "storage_physical_execution_request_blocked_scope_hash_mismatch"
    else:
        status = "storage_physical_execution_request_ready_manual_physical_tasks_pending"
    ready = status == "storage_physical_execution_request_ready_manual_physical_tasks_pending"
    rows = [
        _storage_physical_execution_request_row(
            "user_confirmation_bound",
            passed=approved_by_user,
            status="passed" if approved_by_user else "blocked_confirmation_required",
            evidence=f"approved_by_user={approved_by_user}",
            next_action="Require an explicit button POST before binding any physical storage execution request.",
        ),
        _storage_physical_execution_request_row(
            "activation_receipt_visible",
            passed=activation_ready,
            status="passed" if activation_ready else "blocked_missing_activation_receipt",
            evidence=f"activation_status={activation_receipt.get('status')}",
            next_action="Keep schema, manifest, partition, compaction, TTL, cleanup, and promotion prerequisites visible.",
        ),
        _storage_physical_execution_request_row(
            "physical_execution_recipe_ready",
            passed=recipe_ready,
            status="passed" if recipe_ready else "blocked_recipe_not_ready",
            evidence=f"recipe_status={execution_recipe.get('status')}; phase_count={execution_recipe.get('phase_count')}",
            next_action="Use the local physical execution recipe as a sequence contract only.",
        ),
        _storage_physical_execution_request_row(
            "physical_execution_scope_hash_bound",
            passed=requested_hash_matches_latest,
            status="passed" if requested_hash_matches_latest else "blocked_scope_hash_mismatch_or_missing",
            evidence=f"requested_scope_hash_short={requested_scope_hash[:12]}; latest_scope_hash_short={latest_scope_hash[:12]}",
            next_action="Regenerate the request from the current Storage page if the execution recipe changes.",
        ),
        _storage_physical_execution_request_row(
            "manual_physical_execution_still_pending",
            passed=True,
            status="passed_request_only",
            evidence="request ticket binds future physical execution phases but does not run them.",
            next_action="Submit separate explicit physical storage tasks only after reviewing this request ticket.",
        ),
        _storage_physical_execution_request_row(
            "no_write_delete_provider_trade_action_secret_boundary",
            passed=True,
            status="passed_no_side_effects",
            evidence="request ticket does not write Parquet, write manifests, delete artifacts, refresh providers, call models, call GitHub, trade, mutate action, or include secrets.",
            next_action="Preserve these false side-effect flags in every future physical storage task.",
        ),
    ]
    return {
        "schema_version": "command_center_3_storage_physical_execution_request.v1",
        "packet_key": STORAGE_PHYSICAL_EXECUTION_REQUEST_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_physical_execution_request",
        "scope": "local_storage_physical_execution_request_no_write_no_delete_no_provider",
        "ltg": "LTG-05/LTG-11",
        "local_execution_request_ready": ready,
        "ready_for_manual_physical_task_submission": ready,
        "approved_by_user": approved_by_user,
        "requires_user_confirmation": True,
        "requested_scope_hash_matches_latest": requested_hash_matches_latest,
        "physical_execution_scope_hash": latest_scope_hash if requested_hash_matches_latest else "",
        "physical_execution_scope_hash_short": latest_scope_hash[:12] if latest_scope_hash else "",
        "requested_scope_hash_short": requested_scope_hash[:12],
        "target_storage_task_route": "POST /api/storage/physical-execution/phase-a",
        "target_storage_task_type": "run_storage_physical_execution_phase_a",
        "target_phases": list(execution_recipe.get("allowed_execution_sequence") or []),
        "target_phase_count": int(execution_recipe.get("phase_count") or 0),
        "required_evidence": list(execution_recipe.get("required_evidence") or []),
        "source_activation_receipt_status": activation_receipt.get("status"),
        "source_execution_recipe_status": execution_recipe.get("status"),
        "source_execution_recipe_schema_version": execution_recipe.get("schema_version"),
        "source_execution_recipe_scope": execution_recipe.get("scope"),
        "source_production_blocker_count": blocker_audit.get("blocking_criterion_count"),
        "not_allowed_next_steps": [
            "treat_execution_request_as_physical_storage_execution",
            "write_parquet_from_execution_request",
            "write_manifest_from_execution_request",
            "delete_artifacts_from_execution_request",
            "refresh_providers_from_execution_request",
            "call_Tushare_from_execution_request",
            "call_DeepSeek_from_execution_request",
            "call_GitHub_from_execution_request",
            "mark_production_storage_complete_from_execution_request",
        ],
        "request_params_safe": {
            "source": payload_safe.get("source") or "storage_page_button",
            "approved_by_user": approved_by_user,
            "physical_execution_scope_hash_short": requested_scope_hash[:12],
            "external_sources_allowed": False,
            "write_parquet_allowed": False,
            "write_manifest_allowed": False,
            "delete_allowed": False,
        },
        "rows": rows,
        "physical_task_created": False,
        "physical_task_executed": False,
        "physical_execution_implemented": False,
        "production_storage_complete": False,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "artifact_cleanup_delete_executed": False,
        "writes_parquet": False,
        "writes_manifest": False,
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "runs_commands": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_physical_execution_request",
            endpoint="POST /api/storage/physical-execution-request",
            status=status,
            row_count=len(rows),
        ),
        "warnings": [
            "POST /api/storage/physical-execution-request 只生成本地 physical execution request ticket；不会写 Parquet、写 manifest 或删除文件。",
            "storage physical execution request 不调用 Tushare、DeepSeek、GitHub，不执行真实交易，不修改 strategy action。",
        ],
    }


def _missing_storage_physical_execution_request(now: str | None = None) -> dict[str, Any]:
    rows = [
        _storage_physical_execution_request_row(
            "physical_execution_request_visible",
            passed=False,
            status="blocked_missing_execution_request",
            evidence="No button-gated storage physical execution request ticket has been recorded yet.",
            next_action="Generate a request ticket from the current physical execution recipe before future physical storage tasks.",
        )
    ]
    return {
        "schema_version": "command_center_3_storage_physical_execution_request.v1",
        "packet_key": STORAGE_PHYSICAL_EXECUTION_REQUEST_PACKET_KEY,
        "task_id": "",
        "status": "storage_physical_execution_request_missing",
        "mode": "cache_only_missing_placeholder",
        "scope": "local_storage_physical_execution_request_no_write_no_delete_no_provider",
        "ltg": "LTG-05/LTG-11",
        "local_execution_request_ready": False,
        "ready_for_manual_physical_task_submission": False,
        "approved_by_user": False,
        "requires_user_confirmation": True,
        "requested_scope_hash_matches_latest": False,
        "physical_execution_scope_hash": "",
        "physical_execution_scope_hash_short": "",
        "requested_scope_hash_short": "",
        "target_storage_task_route": "POST /api/storage/physical-execution/phase-a",
        "target_storage_task_type": "run_storage_physical_execution_phase_a",
        "target_phases": list(STORAGE_PHYSICAL_EXECUTION_PHASES),
        "target_phase_count": len(STORAGE_PHYSICAL_EXECUTION_PHASES),
        "rows": rows,
        "physical_task_created": False,
        "physical_task_executed": False,
        "physical_execution_implemented": False,
        "production_storage_complete": False,
        "writes_parquet": False,
        "writes_manifest": False,
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "runs_commands": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_physical_execution_request",
            endpoint="GET /api/storage",
            status="storage_physical_execution_request_missing",
            row_count=len(rows),
            now=now,
        ),
        "warnings": [
            "Storage physical execution request ticket 尚未生成；这不是生产 storage 完成证据。",
        ],
    }


def storage_physical_execution_request_evidence() -> dict[str, Any]:
    packet, read_status = _read_storage_meta_packet_no_init(STORAGE_PHYSICAL_EXECUTION_REQUEST_PACKET_KEY)
    if read_status != "packet_present" or not isinstance(packet, Mapping):
        return _missing_storage_physical_execution_request()
    evidence = dict(packet)
    evidence["read_status"] = read_status
    evidence.setdefault("local_execution_request_ready", False)
    evidence.setdefault("production_storage_complete", False)
    evidence.setdefault("external_calls_triggered", False)
    evidence.setdefault("tushare_called", False)
    evidence.setdefault("deepseek_called", False)
    evidence.setdefault("github_called", False)
    evidence.setdefault("does_not_execute_trades", True)
    evidence.setdefault("does_not_modify_strategy_action", True)
    evidence.setdefault("contains_secret", False)
    return evidence


def run_storage_physical_execution_request_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "approved_by_user": payload_map.get("approved_by_user") is True,
        "physical_execution_scope_hash": str(
            payload_map.get("physical_execution_scope_hash") or payload_map.get("scope_hash") or ""
        ),
        "confirm_physical_execution": payload_map.get("confirm_physical_execution") is True,
        "confirm_local_durable_write": payload_map.get("confirm_local_durable_write") is True,
        "confirm_scope_hash": str(payload_map.get("confirm_scope_hash") or ""),
        "result_version": str(payload_map.get("result_version") or ""),
        "sample_rows": list(payload_map.get("sample_rows") or []) if isinstance(payload_map.get("sample_rows"), list) else [],
        "inject_failure_after_stage": str(payload_map.get("inject_failure_after_stage") or ""),
        "external_sources_allowed": False,
        "write_parquet_allowed": payload_map.get("confirm_local_durable_write") is True,
        "write_manifest_allowed": payload_map.get("confirm_local_durable_write") is True,
        "delete_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_physical_execution_request",
        output_packet_key=STORAGE_PHYSICAL_EXECUTION_REQUEST_PACKET_KEY,
        payload=task_payload,
        current_step="storage_physical_execution_request_queued",
        warnings=[
            "storage physical execution request 只生成本地请求 ticket；不会写 Parquet、写 manifest、删除文件或调用外部源。",
            "任何真实 physical execution 必须是后续单独按钮任务；本任务不修改 strategy action、不执行真实交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="building_storage_physical_execution_request_ticket",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_physical_execution_request_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(STORAGE_PHYSICAL_EXECUTION_REQUEST_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_physical_execution_request_packet_persist_failed",
            error_message_safe="storage_physical_execution_request_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_physical_execution_request_packet_failed_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=str(packet.get("status") or "storage_physical_execution_request_recorded"),
        call_ledger=packet["call_ledger"],
        warning="storage_physical_execution_request_recorded_no_write_no_delete_no_external_call",
    ) or task


def _storage_physical_execution_phase_a_row(
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
        "evidence": evidence,
        "next_action": next_action,
        "phase_a_local_evidence": True,
        "production_blocker": bool(production_blocker),
        "writes_parquet": False,
        "writes_manifest": False,
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "reads_row_payloads": False,
        "runs_commands": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _storage_v04_scope_component(scope_hash: str) -> str:
    text = str(scope_hash or "").strip()
    if text and all(char.isalnum() or char in {"_", "-"} for char in text) and len(text) <= 96:
        return text
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _storage_v04_sha256_json(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _storage_v04_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _storage_v04_acceptance_rows(payload_safe: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_rows = payload_safe.get("sample_rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raw_rows = [
            {"ts_code": "000001.SZ", "trade_date": "20260710", "metric": "storage_acceptance", "value": 1.0, "stage": "baseline"},
            {"ts_code": "000002.SZ", "trade_date": "20260710", "metric": "storage_acceptance", "value": 2.0, "stage": "baseline"},
            {"ts_code": "600000.SH", "trade_date": "20260710", "metric": "storage_acceptance", "value": 3.0, "stage": "baseline"},
        ]
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows):
        source = row if isinstance(row, Mapping) else {}
        rows.append(
            {
                "ts_code": str(source.get("ts_code") or source.get("symbol") or f"LOCAL{index:03d}.SZ").strip().upper(),
                "trade_date": str(source.get("trade_date") or "20260710").replace("-", "")[:8],
                "metric": str(source.get("metric") or "storage_acceptance")[:64],
                "value": float(source.get("value") if _storage_v04_finite_number(source.get("value")) else index + 1),
                "stage": str(source.get("stage") or "baseline")[:64],
            }
        )
    return rows


def _storage_v04_write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{hashlib.sha256(str(path).encode('utf-8')).hexdigest()[:12]}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str), encoding="utf-8")
    temp_path.replace(path)


def _storage_v04_path_label(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(V04_ACCEPTANCE_ROOT.resolve())
    except (OSError, ValueError):
        return path.name
    return f"v04_acceptance/{relative.as_posix()}"


def _storage_v04_sanitize_paths(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _storage_v04_sanitize_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_storage_v04_sanitize_paths(item) for item in value]
    if isinstance(value, str) and Path(value).is_absolute():
        return _storage_v04_path_label(Path(value))
    return value


def _storage_v04_physical_execution(
    *,
    task_id: str,
    payload_safe: Mapping[str, Any],
    scope_hash: str,
) -> dict[str, Any]:
    import pandas as pd

    scope_component = _storage_v04_scope_component(scope_hash)
    acceptance_dir = V04_ACCEPTANCE_ROOT / scope_component
    if not acceptance_dir.resolve().is_relative_to(V04_ACCEPTANCE_ROOT.resolve()):
        raise ValueError("invalid_v04_acceptance_scope")
    rows = _storage_v04_acceptance_rows(payload_safe)
    frame = pd.DataFrame(rows, columns=V04_STORAGE_ACCEPTANCE_COLUMNS)
    dataset_root = acceptance_dir / "parquet"
    dataset_name = "storage_phase_a_sample"
    write_result = parquet_store.write_dataset(frame, root=dataset_root, name=dataset_name)
    parquet_path = Path(str(write_result.get("path") or parquet_store.dataset_path(root=dataset_root, name=dataset_name)))
    schema = parquet_store.dataset_schema_metadata(root=dataset_root, name=dataset_name)
    duckdb_readback = duckdb_store.query_parquet_dataset(
        parquet_path,
        ts_code=rows[0]["ts_code"],
        start_date=rows[0]["trade_date"],
        end_date=rows[-1]["trade_date"],
        projection_columns=V04_STORAGE_ACCEPTANCE_COLUMNS,
        limit=100,
    )
    duckdb_query_parity = bool(
        duckdb_readback.get("status") == "ready"
        and int(duckdb_readback.get("row_count") or 0) >= 1
        and duckdb_readback.get("safe_parameter_binding") is True
        and set(duckdb_readback.get("projected_columns") or []) == set(V04_STORAGE_ACCEPTANCE_COLUMNS)
    )
    durable_sqlite_path = acceptance_dir / "durable.sqlite"
    durable_store = SQLiteMetaStore(durable_sqlite_path)
    durable_packet = {
        "schema_version": "storage_v04_durable_packet.v1",
        "status": "ready",
        "scope_hash_short": scope_hash[:12],
        "row_count": len(rows),
        "columns": list(V04_STORAGE_ACCEPTANCE_COLUMNS),
        "contains_secret": False,
    }
    durable_task = {
        "task_id": f"{task_id}-v04-durable-readback",
        "task_type": "storage_v04_durable_sqlite_readback",
        "status": "success",
        "current_step": "durable_sqlite_packet_task_log_written",
        "task_log": [
            {
                "event": "storage_v04_durable_sqlite_readback",
                "scope_hash_short": scope_hash[:12],
                "row_count": len(rows),
                "contains_secret": False,
            }
        ],
        "contains_secret": False,
    }
    durable_store.write_packet("storage_v04_acceptance_packet", durable_packet)
    durable_store.write_task_status(durable_task)
    durable_packet_readback = SQLiteMetaStore(durable_sqlite_path).read_packet("storage_v04_acceptance_packet") or {}
    durable_task_readback = SQLiteMetaStore(durable_sqlite_path).read_task_status(durable_task["task_id"]) or {}
    sqlite_readback_verified = bool(
        durable_packet_readback.get("row_count") == len(rows)
        and durable_task_readback.get("status") == "success"
        and len(durable_task_readback.get("task_log") or []) == 1
    )
    version_id = str(payload_safe.get("result_version") or f"v04_{scope_component}")[:96]
    current_before = parquet_store.versioned_dataset_pointer(
        root=acceptance_dir / "current_result",
        name="storage_v04_current_result",
        pointer="current",
    )
    if payload_safe.get("inject_failure_after_stage") == "parquet_write_before_atomic_promote":
        failure_marker = acceptance_dir / "failed_tmp_marker.json"
        failure_marker.write_text(
            json.dumps(
                {
                    "status": "injected_failure_before_atomic_promote",
                    "scope_hash_short": scope_hash[:12],
                    "temporary_file": True,
                    "contains_secret": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return {
            "status": "storage_v04_physical_execution_injected_failure_current_unchanged",
            "scope_component": scope_component,
            "acceptance_dir": _storage_v04_path_label(acceptance_dir),
            "parquet_path": _storage_v04_path_label(parquet_path),
            "row_count": len(rows),
            "columns": list(V04_STORAGE_ACCEPTANCE_COLUMNS),
            "schema": _storage_v04_sanitize_paths(schema),
            "duckdb_readback": _storage_v04_sanitize_paths(duckdb_readback),
            "duckdb_query_parity": duckdb_query_parity,
            "sqlite_readback_verified": sqlite_readback_verified,
            "atomic_promoted": False,
            "current_before": _storage_v04_sanitize_paths(current_before),
            "current_after": _storage_v04_sanitize_paths(
                parquet_store.versioned_dataset_pointer(
                    root=acceptance_dir / "current_result",
                    name="storage_v04_current_result",
                    pointer="current",
                )
            ),
            "last_good_after": _storage_v04_sanitize_paths(
                parquet_store.versioned_dataset_pointer(
                    root=acceptance_dir / "current_result",
                    name="storage_v04_current_result",
                    pointer="last_good",
                )
            ),
            "temporary_failure_marker": _storage_v04_path_label(failure_marker),
            "temporary_files_identified": failure_marker.exists(),
            "writes_parquet": True,
            "writes_manifest": False,
            "contains_secret": False,
            "external_calls_triggered": False,
        }
    promote_result = parquet_store.atomic_promote_versioned_dataset(
        frame,
        root=acceptance_dir / "current_result",
        name="storage_v04_current_result",
        version_id=version_id,
        required_columns=V04_STORAGE_ACCEPTANCE_COLUMNS,
        lineage={
            "scope_hash_short": scope_hash[:12],
            "source_task_id": task_id,
            "row_count": len(rows),
            "query_parity_verified": duckdb_query_parity,
            "sqlite_readback_verified": sqlite_readback_verified,
        },
    )
    current_after = parquet_store.versioned_dataset_pointer(
        root=acceptance_dir / "current_result",
        name="storage_v04_current_result",
        pointer="current",
    )
    last_good_after = parquet_store.versioned_dataset_pointer(
        root=acceptance_dir / "current_result",
        name="storage_v04_current_result",
        pointer="last_good",
    )
    manifest = {
        "schema_version": "storage_v04_durable_execution_manifest.v1",
        "scope_hash_short": scope_hash[:12],
        "dataset": dataset_name,
        "row_count": len(rows),
        "columns": list(V04_STORAGE_ACCEPTANCE_COLUMNS),
        "parquet_sha256": hashlib.sha256(parquet_path.read_bytes()).hexdigest() if parquet_path.exists() else "",
        "duckdb_query_parity": duckdb_query_parity,
        "sqlite_readback_verified": sqlite_readback_verified,
        "atomic_promoted": promote_result.get("atomic_promoted") is True,
        "current_version_id": str(current_after.get("version_id") or ""),
        "last_good_version_id": str(last_good_after.get("version_id") or ""),
        "contains_secret": False,
    }
    manifest["manifest_sha256"] = _storage_v04_sha256_json(manifest)
    _storage_v04_write_json_atomic(acceptance_dir / "manifest.json", manifest)
    return {
        "status": "storage_v04_physical_execution_success"
        if promote_result.get("atomic_promoted") is True and duckdb_query_parity and sqlite_readback_verified
        else "storage_v04_physical_execution_degraded",
        "scope_component": scope_component,
        "acceptance_dir": _storage_v04_path_label(acceptance_dir),
        "parquet_path": _storage_v04_path_label(parquet_path),
        "row_count": len(rows),
        "columns": list(V04_STORAGE_ACCEPTANCE_COLUMNS),
        "schema": _storage_v04_sanitize_paths(schema),
        "duckdb_readback": _storage_v04_sanitize_paths(duckdb_readback),
        "duckdb_query_parity": duckdb_query_parity,
        "sqlite_readback_verified": sqlite_readback_verified,
        "durable_sqlite_path": _storage_v04_path_label(durable_sqlite_path),
        "manifest": manifest,
        "manifest_path": _storage_v04_path_label(acceptance_dir / "manifest.json"),
        "promote_result": _storage_v04_sanitize_paths(promote_result),
        "atomic_promoted": promote_result.get("atomic_promoted") is True,
        "current_before": _storage_v04_sanitize_paths(current_before),
        "current_after": _storage_v04_sanitize_paths(current_after),
        "last_good_after": _storage_v04_sanitize_paths(last_good_after),
        "last_good_preserved": promote_result.get("last_good_preserved") is True,
        "writes_parquet": True,
        "writes_manifest": True,
        "contains_secret": False,
        "external_calls_triggered": False,
    }


def storage_physical_execution_phase_a_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
    physical_execution_request: Mapping[str, Any] | None = None,
    durable_evidence_recipe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload_safe = payload_safe or {}
    execution_request = dict(physical_execution_request or storage_physical_execution_request_evidence())
    durable_recipe = dict(
        durable_evidence_recipe or storage_physical_durable_evidence_recipe(physical_execution_request=execution_request)
    )
    approved_by_user = payload_safe.get("approved_by_user") is True
    latest_scope_hash = str(execution_request.get("physical_execution_scope_hash") or "")
    requested_scope_hash = str(payload_safe.get("physical_execution_scope_hash") or payload_safe.get("scope_hash") or "")
    request_ready = (
        execution_request.get("schema_version") == "command_center_3_storage_physical_execution_request.v1"
        and execution_request.get("local_execution_request_ready") is True
        and execution_request.get("requested_scope_hash_matches_latest") is True
        and execution_request.get("production_storage_complete") is False
    )
    scope_matches = bool(latest_scope_hash and requested_scope_hash == latest_scope_hash)
    durable_recipe_visible = (
        durable_recipe.get("schema_version") == STORAGE_PHYSICAL_DURABLE_EVIDENCE_SCHEMA_VERSION
        and durable_recipe.get("local_recipe_ready") is True
        and int(durable_recipe.get("evidence_key_count") or 0) == len(STORAGE_PHYSICAL_DURABLE_EVIDENCE_KEYS)
        and durable_recipe.get("production_storage_complete") is False
    )
    no_side_effects = (
        execution_request.get("external_calls_triggered") is False
        and durable_recipe.get("external_calls_triggered") is False
        and execution_request.get("tushare_called") is False
        and durable_recipe.get("tushare_called") is False
        and execution_request.get("deepseek_called") is False
        and durable_recipe.get("deepseek_called") is False
        and execution_request.get("github_called") is False
        and durable_recipe.get("github_called") is False
        and execution_request.get("does_not_execute_trades") is True
        and durable_recipe.get("does_not_execute_trades") is True
        and execution_request.get("does_not_modify_strategy_action") is True
        and durable_recipe.get("does_not_modify_strategy_action") is True
        and execution_request.get("contains_secret") is False
        and durable_recipe.get("contains_secret") is False
    )
    if not approved_by_user:
        status = "storage_physical_execution_phase_a_blocked_user_confirmation_required"
    elif not request_ready:
        status = "storage_physical_execution_phase_a_blocked_request_not_ready"
    elif not requested_scope_hash:
        status = "storage_physical_execution_phase_a_blocked_scope_hash_required"
    elif not scope_matches:
        status = "storage_physical_execution_phase_a_blocked_scope_hash_mismatch"
    elif not durable_recipe_visible:
        status = "storage_physical_execution_phase_a_blocked_durable_evidence"
    elif not no_side_effects:
        status = "storage_physical_execution_phase_a_blocked_boundary_regression"
    else:
        status = "storage_physical_execution_phase_a_ready_local_evidence_production_pending"
    ready = status == "storage_physical_execution_phase_a_ready_local_evidence_production_pending"
    v04_physical_confirmation = bool(
        payload_safe.get("confirm_physical_execution") is True
        and payload_safe.get("confirm_local_durable_write") is True
        and payload_safe.get("confirm_scope_hash") == requested_scope_hash
    )
    v04_result: dict[str, Any] = {"status": "not_requested", "atomic_promoted": False}
    v04_execution_attempted = ready and v04_physical_confirmation
    if v04_execution_attempted:
        try:
            v04_result = _storage_v04_physical_execution(
                task_id=str(task_id or ""),
                payload_safe=payload_safe,
                scope_hash=latest_scope_hash,
            )
        except Exception as exc:
            v04_result = {
                "status": "storage_v04_physical_execution_failed_safe",
                "error_message_safe": type(exc).__name__,
                "atomic_promoted": False,
                "external_calls_triggered": False,
                "contains_secret": False,
            }
        status = (
            "storage_physical_execution_phase_a_v04_durable_execution_success"
            if v04_result.get("status") == "storage_v04_physical_execution_success"
            else str(v04_result.get("status") or "storage_physical_execution_phase_a_v04_durable_execution_failed")
        )
        ready = v04_result.get("status") == "storage_v04_physical_execution_success"
    rows = [
        _storage_physical_execution_phase_a_row(
            "user_confirmation_bound",
            passed=approved_by_user,
            status="passed" if approved_by_user else "blocked_confirmation_required",
            evidence=f"approved_by_user={approved_by_user}",
            next_action="Run Phase A only from explicit POST after reviewing the request ticket.",
            production_blocker=not approved_by_user,
        ),
        _storage_physical_execution_phase_a_row(
            "physical_execution_request_ready",
            passed=request_ready,
            status="passed" if request_ready else "blocked_request_not_ready",
            evidence=f"request_status={execution_request.get('status')}",
            next_action="Bind Phase A to the latest physical execution request before collecting local evidence.",
            production_blocker=not request_ready,
        ),
        _storage_physical_execution_phase_a_row(
            "physical_execution_scope_hash_bound",
            passed=scope_matches,
            status="passed" if scope_matches else "blocked_scope_hash_mismatch_or_missing",
            evidence=f"requested_scope_hash_short={requested_scope_hash[:12]}; latest_scope_hash_short={latest_scope_hash[:12]}",
            next_action="Regenerate Phase A from the current Storage page if the request scope changes.",
            production_blocker=not scope_matches,
        ),
        _storage_physical_execution_phase_a_row(
            "durable_local_evidence_complete",
            passed=durable_recipe_visible,
            status="passed_local_durable_recipe_visible" if durable_recipe_visible else "blocked_durable_evidence_incomplete",
            evidence=(
                f"durable_status={durable_recipe.get('status')}; "
                f"evidence_key_count={durable_recipe.get('evidence_key_count')}; "
                f"production_blocker_count={durable_recipe.get('production_blocker_count')}"
            ),
            next_action="Keep the durable evidence recipe visible; production blockers remain separate from Phase A local evidence.",
            production_blocker=not durable_recipe_visible,
        ),
        _storage_physical_execution_phase_a_row(
            "no_write_delete_provider_trade_action_secret_boundary",
            passed=no_side_effects,
            status="passed_no_side_effects" if no_side_effects else "blocked_boundary_regression",
            evidence="Phase A reads SQLite evidence only and writes no storage artifacts.",
            next_action="Preserve false side-effect flags before any later physical writer task.",
            production_blocker=not no_side_effects,
        ),
        _storage_physical_execution_phase_a_row(
            "production_storage_stays_pending",
            passed=True,
            status="passed_production_pending",
            evidence="Phase A is local evidence consolidation; production_storage_complete remains false.",
            next_action="Only a later release/promotion gate may decide whether production storage can close.",
        ),
    ]
    blocker_count = sum(1 for row in rows if row.get("production_blocker"))
    return {
        "schema_version": "command_center_3_storage_physical_execution_phase_a.v1",
        "packet_key": STORAGE_PHYSICAL_EXECUTION_PHASE_A_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_physical_execution_phase_a",
        "scope": (
            "local_storage_v04_durable_execution_no_delete_no_provider"
            if v04_execution_attempted
            else "local_storage_physical_execution_phase_a_no_write_no_delete_no_provider"
        ),
        "ltg": "LTG-05",
        "local_phase_a_execution_ready": ready,
        "phase_a_local_evidence_done": ready,
        "phase_a_local_evidence_stage_count": int(durable_recipe.get("evidence_key_count") or 0) if ready else 0,
        "phase_a_blocker_count": blocker_count,
        "approved_by_user": approved_by_user,
        "requested_scope_hash_matches_latest": scope_matches,
        "physical_execution_scope_hash": latest_scope_hash if scope_matches else "",
        "physical_execution_scope_hash_short": latest_scope_hash[:12] if latest_scope_hash else "",
        "requested_scope_hash_short": requested_scope_hash[:12],
        "source_physical_execution_request_status": execution_request.get("status"),
        "source_durable_evidence_status": durable_recipe.get("status"),
        "source_durable_evidence_key_count": int(durable_recipe.get("evidence_key_count") or 0),
        "source_durable_evidence_production_blocker_count": int(durable_recipe.get("production_blocker_count") or 0),
        "direct_evidence_layer": "L3_local_storage_physical_execution_phase_a",
        "rows": rows,
        "not_allowed_next_steps": [
            "treat_phase_a_as_production_storage_complete",
            "write_parquet_from_phase_a",
            "write_manifest_from_phase_a",
            "delete_artifacts_from_phase_a",
            "refresh_providers_from_phase_a",
            "call_Tushare_from_phase_a",
            "call_DeepSeek_from_phase_a",
            "call_GitHub_from_phase_a",
            "mutate_strategy_action_from_phase_a",
        ],
        "physical_task_created": ready,
        "physical_task_executed": ready,
        "physical_execution_implemented": ready,
        "v04_physical_execution": v04_result,
        "v04_durable_storage_executed": v04_result.get("status") == "storage_v04_physical_execution_success",
        "v04_duckdb_query_parity": v04_result.get("duckdb_query_parity") is True,
        "v04_sqlite_readback_verified": v04_result.get("sqlite_readback_verified") is True,
        "v04_atomic_current_promoted": v04_result.get("atomic_promoted") is True,
        "v04_last_good_preserved": v04_result.get("last_good_preserved") is True,
        "physical_execution_complete": False,
        "production_storage_complete": False,
        "writes_parquet": v04_result.get("writes_parquet") is True,
        "writes_manifest": v04_result.get("writes_manifest") is True,
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "runs_commands": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "request_params_safe": {
            "source": payload_safe.get("source") or "storage_page_button",
            "approved_by_user": approved_by_user,
            "physical_execution_scope_hash_short": requested_scope_hash[:12],
            "phase": "phase_a_local_evidence_consolidation",
            "external_sources_allowed": False,
            "write_parquet_allowed": v04_physical_confirmation,
            "write_manifest_allowed": v04_physical_confirmation,
            "delete_allowed": False,
        },
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_physical_execution_phase_a",
            endpoint="POST /api/storage/physical-execution/phase-a",
            status=status,
            row_count=int(v04_result.get("row_count") or len(rows)),
        ),
        "warnings": [
            (
                "v0.4 双确认已执行 gitignored 本地 Parquet、SQLite 与 manifest 验收写入；未删除文件或调用外部源。"
                if v04_result.get("status") == "storage_v04_physical_execution_success"
                else "未完成 v0.4 durable current 提升；现有 current/last-good 保持可回放。"
                if v04_execution_attempted
                else "未提供 v0.4 双确认；Phase A 仅记录既有本地 evidence，不写 durable acceptance artifacts。"
            ),
            "Phase A 不是 production storage complete；真实生产提升仍需后续独立 gate。",
        ],
    }


def storage_physical_execution_phase_a_evidence() -> dict[str, Any]:
    packet, read_status = _read_storage_meta_packet_no_init(STORAGE_PHYSICAL_EXECUTION_PHASE_A_PACKET_KEY)
    if read_status != "packet_present" or not isinstance(packet, Mapping):
        return {
            "schema_version": "command_center_3_storage_physical_execution_phase_a.v1",
            "packet_key": STORAGE_PHYSICAL_EXECUTION_PHASE_A_PACKET_KEY,
            "status": "storage_physical_execution_phase_a_missing",
            "local_phase_a_execution_ready": False,
            "phase_a_local_evidence_done": False,
            "phase_a_local_evidence_stage_count": 0,
            "phase_a_blocker_count": 1,
            "production_storage_complete": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "rows": [
                _storage_physical_execution_phase_a_row(
                    "phase_a_evidence_visible",
                    passed=False,
                    status="blocked_missing_phase_a",
                    evidence="No button-gated storage physical execution Phase A packet has been recorded yet.",
                    next_action="Run Phase A after physical execution request and durable evidence are ready.",
                    production_blocker=True,
                )
            ],
        }
    evidence = dict(packet)
    evidence["read_status"] = read_status
    evidence.setdefault("local_phase_a_execution_ready", False)
    evidence.setdefault("phase_a_local_evidence_done", False)
    evidence.setdefault("production_storage_complete", False)
    evidence.setdefault("external_calls_triggered", False)
    evidence.setdefault("tushare_called", False)
    evidence.setdefault("deepseek_called", False)
    evidence.setdefault("github_called", False)
    evidence.setdefault("does_not_execute_trades", True)
    evidence.setdefault("does_not_modify_strategy_action", True)
    evidence.setdefault("contains_secret", False)
    return evidence


def run_storage_physical_execution_phase_a_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "approved_by_user": payload_map.get("approved_by_user") is True,
        "physical_execution_scope_hash": str(
            payload_map.get("physical_execution_scope_hash") or payload_map.get("scope_hash") or ""
        ),
        "confirm_physical_execution": payload_map.get("confirm_physical_execution") is True,
        "confirm_local_durable_write": payload_map.get("confirm_local_durable_write") is True,
        "confirm_scope_hash": str(payload_map.get("confirm_scope_hash") or ""),
        "result_version": str(payload_map.get("result_version") or ""),
        "sample_rows": list(payload_map.get("sample_rows") or []) if isinstance(payload_map.get("sample_rows"), list) else [],
        "inject_failure_after_stage": str(payload_map.get("inject_failure_after_stage") or ""),
        "external_sources_allowed": False,
        "write_parquet_allowed": payload_map.get("confirm_local_durable_write") is True,
        "write_manifest_allowed": payload_map.get("confirm_local_durable_write") is True,
        "delete_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_physical_execution_phase_a",
        output_packet_key=STORAGE_PHYSICAL_EXECUTION_PHASE_A_PACKET_KEY,
        payload=task_payload,
        current_step="storage_physical_execution_phase_a_queued",
        warnings=[
            "v0.4 durable 写入仅在 scope 匹配且双确认时执行；否则 Phase A 只记录既有本地 evidence。",
            "Phase A 不修改 strategy action、不执行真实交易，也不代表 production storage 完成。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.55,
        current_step="building_storage_physical_execution_phase_a_evidence",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_physical_execution_phase_a_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(STORAGE_PHYSICAL_EXECUTION_PHASE_A_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_physical_execution_phase_a_packet_persist_failed",
            error_message_safe="storage_physical_execution_phase_a_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_physical_execution_phase_a_failed_no_external_call",
        ) or task
    succeeded = packet.get("local_phase_a_execution_ready") is True
    return task_service.update_task_status(
        task["task_id"],
        status="success" if succeeded else "failed",
        progress=1.0,
        current_step=str(packet.get("status") or "storage_physical_execution_phase_a_recorded"),
        error_message_safe=None if succeeded else str(packet.get("status") or "storage_physical_execution_phase_a_blocked"),
        call_ledger=packet["call_ledger"],
        warning=(
            "storage_physical_execution_phase_a_v04_durable_execution_success"
            if succeeded
            else "storage_physical_execution_phase_a_no_current_overwrite_review_packet"
        ),
    ) or task


def _storage_current_result_lineage() -> tuple[dict[str, Any], str]:
    packet, read_status = _read_storage_meta_packet_no_init(CURRENT_RESULT_LINEAGE_PACKET_KEY)
    if read_status not in {"packet_present", "packet_missing"}:
        return {}, "candidate_packet_read_failed"
    if not isinstance(packet, Mapping):
        return {}, "candidate_packet_missing"
    lineage = packet.get("search_quant_canonical_result_lineage")
    if not isinstance(lineage, Mapping):
        return {}, "canonical_lineage_missing"
    return dict(lineage), "canonical_lineage_present"


def _storage_current_result_row(lineage: Mapping[str, Any], *, promoted_at: str) -> dict[str, Any]:
    return {
        "task_id": str(lineage.get("task_id") or ""),
        "user_confirm_task_id": str(lineage.get("user_confirm_task_id") or ""),
        "task_family_id": str(lineage.get("task_family_id") or ""),
        "symbol": str(lineage.get("symbol") or ""),
        "scope_hash": str(lineage.get("scope_hash") or ""),
        "provider_call_ledger_ids_json": json.dumps(
            [str(item) for item in list(lineage.get("provider_call_ledger_ids") or [])],
            ensure_ascii=False,
            sort_keys=True,
        ),
        "input_packet_keys_json": json.dumps(
            [str(item) for item in list(lineage.get("input_packet_keys") or [])],
            ensure_ascii=False,
            sort_keys=True,
        ),
        "output_packet_keys_json": json.dumps(
            [str(item) for item in list(lineage.get("output_packet_keys") or [])],
            ensure_ascii=False,
            sort_keys=True,
        ),
        "data_date": str(lineage.get("data_date") or ""),
        "freshness_state": str(lineage.get("freshness_state") or ""),
        "model_ledger_id": str(lineage.get("model_ledger_id") or ""),
        "result_version": str(lineage.get("result_version") or ""),
        "facts_packet_key": str(lineage.get("facts_packet_key") or ""),
        "facts_package_hash": str(lineage.get("facts_package_hash") or ""),
        "deepseek_status": str(lineage.get("deepseek_status") or ""),
        "promoted_at": promoted_at,
    }


def _storage_current_result_duckdb_readback(
    current_pointer: Mapping[str, Any],
    *,
    symbol: str,
    result_version: str,
) -> dict[str, Any]:
    artifact_path = str(current_pointer.get("artifact_path") or "")
    if current_pointer.get("status") != "ready" or not artifact_path:
        return {
            "status": "current_pointer_missing",
            "verified": False,
            "row_count": 0,
            "symbol": "",
            "result_version": "",
            "data_date": "",
            "freshness_state": "",
            "facts_package_hash": "",
            "model_ledger_id": "",
            "external_calls_triggered": False,
        }
    query = duckdb_store.query_parquet_dataset(
        artifact_path,
        limit=2,
        projection_columns=[
            "symbol",
            "result_version",
            "data_date",
            "freshness_state",
            "facts_package_hash",
            "model_ledger_id",
        ],
    )
    rows = list(query.get("rows") or [])
    first = dict(rows[0]) if len(rows) == 1 and isinstance(rows[0], Mapping) else {}
    verified = bool(
        query.get("status") == "ready"
        and query.get("query_wrapper") == "duckdb_filtered_parquet.v1"
        and query.get("safe_parameter_binding") is True
        and query.get("external_calls_triggered") is False
        and int(query.get("row_count") or 0) == 1
        and str(first.get("symbol") or "") == symbol
        and str(first.get("result_version") or "") == result_version
    )
    return {
        "status": "verified" if verified else str(query.get("status") or "readback_failed"),
        "verified": verified,
        "row_count": int(query.get("row_count") or 0),
        "symbol": str(first.get("symbol") or ""),
        "result_version": str(first.get("result_version") or ""),
        "data_date": str(first.get("data_date") or ""),
        "freshness_state": str(first.get("freshness_state") or ""),
        "facts_package_hash": str(first.get("facts_package_hash") or ""),
        "model_ledger_id": str(first.get("model_ledger_id") or ""),
        "query_wrapper": str(query.get("query_wrapper") or ""),
        "safe_parameter_binding": query.get("safe_parameter_binding") is True,
        "projected_columns": list(query.get("projected_columns") or []),
        "missing_projected_columns": list(query.get("missing_projected_columns") or []),
        "external_calls_triggered": False,
    }


def storage_current_result_atomic_promotion_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload_safe = payload_safe or {}
    approved_by_user = payload_safe.get("approved_by_user") is True
    expected_symbol = str(payload_safe.get("expected_symbol") or "").strip().upper()
    expected_result_version = str(payload_safe.get("expected_result_version") or "").strip()
    lineage, lineage_read_status = _storage_current_result_lineage()
    symbol = str(lineage.get("symbol") or "").strip().upper()
    result_version = str(lineage.get("result_version") or "").strip()
    lineage_ready = bool(
        lineage.get("schema_version")
        == "candidate_radar_search_quant_projection_canonical_result_lineage.v1"
        and lineage.get("current_result_promoted") is True
        and lineage.get("factor_next_same_result_ready") is True
        and lineage.get("same_task_fact_model_result_version_ready") is True
        and lineage.get("old_task_can_overwrite_current") is False
        and lineage.get("facts_package_status") == "ready"
        and lineage.get("does_not_execute_trades") is True
        and lineage.get("does_not_modify_strategy_action") is True
        and lineage.get("contains_secret") is False
        and symbol
        and result_version
    )
    symbol_matches = bool(expected_symbol and symbol == expected_symbol)
    result_version_matches = bool(expected_result_version and result_version == expected_result_version)
    if not approved_by_user:
        status = "storage_current_result_atomic_promotion_blocked_user_confirmation_required"
    elif not expected_symbol or not expected_result_version:
        status = "storage_current_result_atomic_promotion_blocked_expected_lineage_required"
    elif not lineage_ready:
        status = "storage_current_result_atomic_promotion_blocked_canonical_lineage_not_ready"
    elif not symbol_matches:
        status = "storage_current_result_atomic_promotion_blocked_symbol_mismatch"
    elif not result_version_matches:
        status = "storage_current_result_atomic_promotion_blocked_result_version_mismatch"
    else:
        status = "storage_current_result_atomic_promotion_ready_to_write"

    promoted_at = _now_iso()
    write_result: dict[str, Any] = {
        "status": "not_executed",
        "atomic_promoted": False,
        "writes_parquet": False,
        "writes_pointer": False,
        "external_calls_triggered": False,
    }
    current_before_write = parquet_store.versioned_dataset_pointer(
        root=PARQUET_ROOT,
        name=CURRENT_RESULT_LINEAGE_DATASET,
        pointer="current",
    )
    current_already_matches = bool(
        current_before_write.get("status") == "ready"
        and current_before_write.get("version_id") == result_version
        and (current_before_write.get("lineage") or {}).get("symbol") == symbol
    )
    if status == "storage_current_result_atomic_promotion_ready_to_write":
        if current_already_matches:
            manifest_result = parquet_store.ensure_versioned_dataset_manifest_entry(
                root=PARQUET_ROOT,
                name=CURRENT_RESULT_LINEAGE_DATASET,
            )
            write_result = {
                "status": "atomic_current_reused_manifest_ready"
                if manifest_result.get("manifest_entry_ready") is True
                else str(manifest_result.get("status") or "manifest_entry_validation_failed"),
                "atomic_promoted": manifest_result.get("manifest_entry_ready") is True,
                "writes_parquet": False,
                "writes_manifest": manifest_result.get("writes_manifest") is True,
                "writes_pointer": False,
                "artifact_reused": True,
                "current_pointer_unchanged": True,
                "last_good_preserved": parquet_store.versioned_dataset_pointer(
                    root=PARQUET_ROOT,
                    name=CURRENT_RESULT_LINEAGE_DATASET,
                    pointer="last_good",
                ).get("status")
                == "ready",
                "version_manifest": manifest_result.get("version_manifest") or {},
                "external_calls_triggered": False,
            }
        else:
            try:
                import pandas as pd

                row = _storage_current_result_row(lineage, promoted_at=promoted_at)
                write_result = parquet_store.atomic_promote_versioned_dataset(
                    pd.DataFrame([row], columns=CURRENT_RESULT_LINEAGE_REQUIRED_COLUMNS),
                    root=PARQUET_ROOT,
                    name=CURRENT_RESULT_LINEAGE_DATASET,
                    version_id=result_version,
                    required_columns=CURRENT_RESULT_LINEAGE_REQUIRED_COLUMNS,
                    lineage={
                        "task_id": str(lineage.get("task_id") or ""),
                        "symbol": symbol,
                        "scope_hash": str(lineage.get("scope_hash") or ""),
                        "result_version": result_version,
                        "facts_package_hash": str(lineage.get("facts_package_hash") or ""),
                        "model_ledger_id": str(lineage.get("model_ledger_id") or ""),
                        "source_packet_key": CURRENT_RESULT_LINEAGE_PACKET_KEY,
                    },
                )
            except Exception as exc:
                write_result = {
                    "status": "atomic_promotion_failed",
                    "atomic_promoted": False,
                    "writes_parquet": False,
                    "writes_manifest": False,
                    "writes_pointer": False,
                    "error_message_safe": type(exc).__name__,
                    "external_calls_triggered": False,
                }
        status = (
            "storage_current_result_atomic_promotion_success"
            if write_result.get("atomic_promoted") is True
            else "storage_current_result_atomic_promotion_write_failed"
        )

    promoted = status == "storage_current_result_atomic_promotion_success"
    current_pointer = (
        parquet_store.versioned_dataset_pointer(
            root=PARQUET_ROOT,
            name=CURRENT_RESULT_LINEAGE_DATASET,
            pointer="current",
        )
        if promoted
        else {}
    )
    last_good_pointer = (
        parquet_store.versioned_dataset_pointer(
            root=PARQUET_ROOT,
            name=CURRENT_RESULT_LINEAGE_DATASET,
            pointer="last_good",
        )
        if promoted
        else {}
    )
    duckdb_readback = _storage_current_result_duckdb_readback(
        current_pointer,
        symbol=symbol,
        result_version=result_version,
    )
    version_manifest = parquet_store.versioned_dataset_manifest(
        root=PARQUET_ROOT,
        name=CURRENT_RESULT_LINEAGE_DATASET,
    )
    manifest_current_version_ready = any(
        item.get("version_id") == result_version and item.get("valid") is True
        for item in list(version_manifest.get("versions") or [])
        if isinstance(item, Mapping)
    )
    call_ledger = [
        {
            "api": "local_storage_current_result_atomic_promotion",
            "endpoint": "POST /api/storage/current-result/atomic-promote",
            "source_type": "local_storage_writer",
            "external": False,
            "call_status": status,
            "dataset": CURRENT_RESULT_LINEAGE_DATASET,
            "symbol": symbol,
            "result_version": result_version,
            "row_count": int(write_result.get("row_count") or 0),
            "writes_parquet": write_result.get("writes_parquet") is True,
            "writes_pointer": write_result.get("writes_pointer") is True,
            "writes_manifest": write_result.get("writes_manifest") is True,
            "atomic_promoted": promoted,
            "last_good_preserved": write_result.get("last_good_preserved") is True,
            "duckdb_readback_verified": duckdb_readback.get("verified") is True,
            "manifest_current_version_ready": manifest_current_version_ready,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    ]
    return {
        "schema_version": "command_center_3_storage_current_result_atomic_promotion.v1",
        "packet_key": STORAGE_CURRENT_RESULT_ATOMIC_PROMOTION_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_atomic_parquet_promotion",
        "scope": "canonical_search_result_lineage_to_versioned_parquet",
        "ltg": "LTG-05",
        "approved_by_user": approved_by_user,
        "lineage_read_status": lineage_read_status,
        "canonical_lineage_ready": lineage_ready,
        "expected_symbol": expected_symbol,
        "expected_result_version": expected_result_version,
        "symbol": symbol,
        "result_version": result_version,
        "symbol_matches": symbol_matches,
        "result_version_matches": result_version_matches,
        "source_packet_key": CURRENT_RESULT_LINEAGE_PACKET_KEY,
        "dataset": CURRENT_RESULT_LINEAGE_DATASET,
        "physical_write_executed": promoted,
        "atomic_current_promoted": promoted,
        "last_good_preserved": write_result.get("last_good_preserved") is True,
        "current_pointer": current_pointer,
        "last_good_pointer": last_good_pointer,
        "duckdb_readback": duckdb_readback,
        "duckdb_readback_verified": duckdb_readback.get("verified") is True,
        "version_manifest": version_manifest,
        "manifest_current_version_ready": manifest_current_version_ready,
        "manifest_version_count": int(version_manifest.get("version_count") or 0),
        "write_result": write_result,
        "production_storage_complete": False,
        "provider_refresh_executed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": call_ledger,
        "warnings": [
            "This explicit POST writes only canonical result lineage to ignored local versioned Parquet storage.",
            "A successful atomic promotion is LTG-05 direct local physical evidence, not production storage completion.",
        ],
    }


def run_storage_current_result_atomic_promotion_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_atomic_promotion",
        "approved_by_user": payload_map.get("approved_by_user") is True,
        "expected_symbol": str(payload_map.get("expected_symbol") or "").strip().upper(),
        "expected_result_version": str(payload_map.get("expected_result_version") or "").strip(),
        "external_sources_allowed": False,
        "write_parquet_allowed": True,
        "delete_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_current_result_atomic_promotion",
        output_packet_key=STORAGE_CURRENT_RESULT_ATOMIC_PROMOTION_PACKET_KEY,
        payload=task_payload,
        current_step="storage_current_result_atomic_promotion_queued",
        warnings=[
            "This task may write ignored local Parquet and atomic current/last-good pointers after canonical-lineage validation.",
            "It never refreshes providers, calls models, deletes artifacts, trades, or mutates strategy action.",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="validating_canonical_result_before_atomic_storage_promotion",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_current_result_atomic_promotion_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(STORAGE_CURRENT_RESULT_ATOMIC_PROMOTION_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_current_result_atomic_promotion_packet_persist_failed",
            error_message_safe="storage_atomic_promotion_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="physical_write_may_have_completed_but_sqlite_receipt_failed",
        ) or task
    succeeded = packet.get("physical_write_executed") is True
    return task_service.update_task_status(
        task["task_id"],
        status="success" if succeeded else "failed",
        progress=1.0,
        current_step=str(packet.get("status") or "storage_current_result_atomic_promotion_finished"),
        error_message_safe=None if succeeded else str(packet.get("status") or "storage_atomic_promotion_blocked"),
        call_ledger=packet["call_ledger"],
        warning=(
            "canonical_result_lineage_atomically_promoted_to_local_parquet"
            if succeeded
            else "canonical_result_lineage_not_promoted_current_pointer_unchanged"
        ),
    ) or task


def storage_current_result_retention_cleanup_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload_map = payload_safe if isinstance(payload_safe, Mapping) else {}
    try:
        max_versions = max(2, min(int(payload_map.get("max_versions") or CURRENT_RESULT_MAX_VERSIONS), 100))
    except (TypeError, ValueError):
        max_versions = CURRENT_RESULT_MAX_VERSIONS
    expected_candidate_version_ids = [
        str(value)
        for value in list(payload_map.get("expected_candidate_version_ids") or [])
        if str(value)
    ]
    result = parquet_store.execute_versioned_dataset_retention_cleanup(
        root=PARQUET_ROOT,
        name=CURRENT_RESULT_LINEAGE_DATASET,
        max_versions=max_versions,
        expected_plan_hash=str(payload_map.get("expected_plan_hash") or ""),
        expected_candidate_version_ids=expected_candidate_version_ids,
        approved_by_user=payload_map.get("approved_by_user") is True,
    )
    succeeded = result.get("delete_executed") is True
    status = (
        "storage_current_result_retention_cleanup_success"
        if succeeded
        else str(result.get("status") or "storage_current_result_retention_cleanup_blocked")
    )
    call_ledger = [
        {
            "api": "local_storage_current_result_retention_cleanup",
            "endpoint": "POST /api/storage/current-result/retention-cleanup",
            "source_type": "local_storage_retention_executor",
            "external": False,
            "call_status": status,
            "dataset": CURRENT_RESULT_LINEAGE_DATASET,
            "plan_hash": str(result.get("plan_hash") or ""),
            "candidate_version_ids": list(result.get("candidate_version_ids") or []),
            "protected_version_ids": list(result.get("protected_version_ids") or []),
            "deleted_version_count": int(result.get("deleted_version_count") or 0),
            "delete_executed": succeeded,
            "recovery_execution": result.get("recovery_execution") is True,
            "cleanup_journal_status": str(result.get("cleanup_journal_status") or ""),
            "writes_manifest": result.get("writes_manifest") is True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    ]
    return {
        "schema_version": "command_center_3_storage_current_result_retention_cleanup.v1",
        "packet_key": STORAGE_CURRENT_RESULT_RETENTION_CLEANUP_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_version_retention_cleanup",
        "scope": "current_result_versions_bound_to_plan_hash",
        "ltg": "LTG-05",
        "approved_by_user": payload_map.get("approved_by_user") is True,
        "max_versions": max_versions,
        "expected_plan_hash": str(payload_map.get("expected_plan_hash") or ""),
        "expected_candidate_version_ids": expected_candidate_version_ids,
        "cleanup_result": result,
        "delete_executed": succeeded,
        "deleted_version_count": int(result.get("deleted_version_count") or 0),
        "deleted_version_ids": list(result.get("deleted_version_ids") or []),
        "protected_version_ids": list(result.get("protected_version_ids") or []),
        "recovery_execution": result.get("recovery_execution") is True,
        "cleanup_journal_status": str(result.get("cleanup_journal_status") or ""),
        "current_version_id": str(result.get("current_version_id") or ""),
        "last_good_version_id": str(result.get("last_good_version_id") or ""),
        "production_storage_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": call_ledger,
        "warnings": [
            "Retention cleanup deletes only immutable versions bound to the current plan hash.",
            "Current and last-good pointers are protected; cleanup never refreshes providers or completes production storage.",
        ],
    }


def run_storage_current_result_retention_cleanup_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_current_result_retention_cleanup",
        "approved_by_user": payload_map.get("approved_by_user") is True,
        "expected_plan_hash": str(payload_map.get("expected_plan_hash") or ""),
        "expected_candidate_version_ids": [
            str(value)
            for value in list(payload_map.get("expected_candidate_version_ids") or [])
            if str(value)
        ],
        "max_versions": payload_map.get("max_versions") or CURRENT_RESULT_MAX_VERSIONS,
        "external_sources_allowed": False,
        "delete_versioned_artifacts_allowed": payload_map.get("approved_by_user") is True,
    }
    task = task_service.create_task_record(
        "run_storage_current_result_retention_cleanup",
        output_packet_key=STORAGE_CURRENT_RESULT_RETENTION_CLEANUP_PACKET_KEY,
        payload=task_payload,
        current_step="storage_current_result_retention_cleanup_queued",
        warnings=[
            "This task requires explicit approval plus an exact current plan hash and candidate list.",
            "It cannot delete current/last-good, call external sources, trade, or mutate strategy action.",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.4,
        current_step="revalidating_retention_plan_and_protected_pointers",
    )
    payload_for_execution = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_current_result_retention_cleanup_packet(
        task_id=task["task_id"],
        payload_safe=payload_for_execution,
    )
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(
            STORAGE_CURRENT_RESULT_RETENTION_CLEANUP_PACKET_KEY,
            packet,
        )
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_current_result_retention_cleanup_receipt_persist_failed",
            error_message_safe="storage_retention_cleanup_receipt_write_failed",
            call_ledger=packet["call_ledger"],
            warning="cleanup_result_recording_failed_review_local_manifest_before_retry",
        ) or task
    succeeded = packet.get("delete_executed") is True
    return task_service.update_task_status(
        task["task_id"],
        status="success" if succeeded else "failed",
        progress=1.0,
        current_step=str(packet.get("status") or "storage_current_result_retention_cleanup_finished"),
        error_message_safe=None if succeeded else str(packet.get("status") or "retention_cleanup_blocked"),
        call_ledger=packet["call_ledger"],
        warning=(
            "bound_retention_candidates_deleted_current_last_good_preserved"
            if succeeded
            else "retention_cleanup_not_executed_or_incomplete"
        ),
    ) or task


def storage_current_result_atomic_promotion_evidence() -> dict[str, Any]:
    lineage, lineage_read_status = _storage_current_result_lineage()
    receipt, receipt_read_status = _read_storage_meta_packet_no_init(
        STORAGE_CURRENT_RESULT_ATOMIC_PROMOTION_PACKET_KEY
    )
    receipt = dict(receipt) if isinstance(receipt, Mapping) else {}
    cleanup_receipt, cleanup_receipt_read_status = _read_storage_meta_packet_no_init(
        STORAGE_CURRENT_RESULT_RETENTION_CLEANUP_PACKET_KEY
    )
    cleanup_receipt = dict(cleanup_receipt) if isinstance(cleanup_receipt, Mapping) else {}
    current_pointer = parquet_store.versioned_dataset_pointer(
        root=PARQUET_ROOT,
        name=CURRENT_RESULT_LINEAGE_DATASET,
        pointer="current",
    )
    last_good_pointer = parquet_store.versioned_dataset_pointer(
        root=PARQUET_ROOT,
        name=CURRENT_RESULT_LINEAGE_DATASET,
        pointer="last_good",
    )
    version_manifest = parquet_store.versioned_dataset_manifest(
        root=PARQUET_ROOT,
        name=CURRENT_RESULT_LINEAGE_DATASET,
    )
    resolved_current = parquet_store.resolve_versioned_dataset_current(
        root=PARQUET_ROOT,
        name=CURRENT_RESULT_LINEAGE_DATASET,
    )
    symbol = str(lineage.get("symbol") or "")
    result_version = str(lineage.get("result_version") or "")
    resolved_pointer = dict(resolved_current.get("selected_pointer") or {})
    ttl_state = parquet_store.versioned_dataset_ttl_status(
        resolved_pointer,
        ttl_seconds=CURRENT_RESULT_TTL_SECONDS,
    )
    retention_plan = parquet_store.versioned_dataset_retention_plan(
        root=PARQUET_ROOT,
        name=CURRENT_RESULT_LINEAGE_DATASET,
        max_versions=CURRENT_RESULT_MAX_VERSIONS,
    )
    cleanup_journal = parquet_store.versioned_dataset_retention_cleanup_journal(
        root=PARQUET_ROOT,
        name=CURRENT_RESULT_LINEAGE_DATASET,
    )
    cleanup_journal_summary = {
        "status": str(cleanup_journal.get("status") or "missing"),
        "plan_hash": str(cleanup_journal.get("plan_hash") or ""),
        "max_versions": int(cleanup_journal.get("max_versions") or CURRENT_RESULT_MAX_VERSIONS),
        "candidate_version_ids": list(cleanup_journal.get("candidate_version_ids") or []),
        "protected_version_ids": list(cleanup_journal.get("protected_version_ids") or []),
        "pending_artifact_count": int(cleanup_journal.get("pending_artifact_count") or 0),
        "recovery_ready": cleanup_journal.get("recovery_ready") is True,
        "cleanup_completed": cleanup_journal.get("cleanup_completed") is True,
        "protected_version_conflict": cleanup_journal.get("protected_version_conflict") is True,
        "writes_files": False,
        "external_calls_triggered": False,
    }
    resolved_symbol = str((resolved_pointer.get("lineage") or {}).get("symbol") or symbol)
    resolved_result_version = str(resolved_pointer.get("version_id") or result_version)
    duckdb_readback = _storage_current_result_duckdb_readback(
        resolved_pointer,
        symbol=resolved_symbol,
        result_version=resolved_result_version,
    )
    current_version_id = str(current_pointer.get("version_id") or "")
    last_good_version_id = str(last_good_pointer.get("version_id") or "")
    current_pointer_lineage = dict(current_pointer.get("lineage") or {})
    current_pointer_symbol = str(current_pointer_lineage.get("symbol") or "")
    current_pointer_ready = bool(
        current_pointer.get("status") == "ready"
        and current_version_id
        and current_pointer_symbol
        and resolved_current.get("selected_pointer_kind") == "current"
    )
    manifest_current_version_ready = any(
        item.get("version_id") == (current_version_id or result_version) and item.get("valid") is True
        for item in list(version_manifest.get("versions") or [])
        if isinstance(item, Mapping)
    )
    last_good_pointer_ready = bool(
        last_good_pointer.get("status") == "ready"
        and last_good_version_id
        and last_good_version_id != current_version_id
    )
    retention_protected_ids = set(retention_plan.get("protected_version_ids") or [])
    retention_protects_current_and_last_good = bool(
        current_version_id
        and last_good_version_id
        and {current_version_id, last_good_version_id}.issubset(retention_protected_ids)
    )
    canonical_ready = bool(
        lineage.get("current_result_promoted") is True
        and lineage.get("factor_next_same_result_ready") is True
        and lineage.get("same_task_fact_model_result_version_ready") is True
        and lineage.get("old_task_can_overwrite_current") is False
        and lineage.get("facts_package_status") == "ready"
        and lineage.get("does_not_execute_trades") is True
        and lineage.get("does_not_modify_strategy_action") is True
        and lineage.get("contains_secret") is False
        and symbol
        and result_version
    )
    current_matches = bool(
        current_pointer.get("status") == "ready"
        and current_pointer.get("version_id") == result_version
        and (current_pointer.get("lineage") or {}).get("symbol") == symbol
    )
    atomic_promotion_current = bool(current_matches or current_pointer_ready)
    current_result_storage_acceptance_ready = bool(
        atomic_promotion_current
        and last_good_pointer_ready
        and retention_protects_current_and_last_good
        and duckdb_readback.get("verified") is True
        and manifest_current_version_ready
        and int(version_manifest.get("version_count") or 0) >= 2
        and cleanup_journal_summary["protected_version_conflict"] is False
        and cleanup_journal_summary["recovery_ready"] is False
        and cleanup_journal_summary["pending_artifact_count"] == 0
    )
    degraded_recovery_active = resolved_current.get("degraded_recovery_active") is True
    can_launch = bool(canonical_ready and not current_matches and not degraded_recovery_active)
    if degraded_recovery_active:
        status = "storage_current_result_atomic_promotion_degraded_last_good_active"
    elif can_launch:
        status = "storage_current_result_atomic_promotion_ready_for_explicit_post"
    elif atomic_promotion_current:
        status = "storage_current_result_atomic_promotion_current"
    elif canonical_ready:
        status = "storage_current_result_atomic_promotion_ready_for_explicit_post"
    else:
        status = "storage_current_result_atomic_promotion_waiting_canonical_result"
    return {
        "schema_version": "command_center_3_storage_current_result_atomic_promotion_evidence.v1",
        "status": status,
        "lineage_read_status": lineage_read_status,
        "receipt_read_status": receipt_read_status,
        "canonical_lineage_ready": canonical_ready,
        "can_launch_atomic_promotion": can_launch,
        "atomic_promotion_current": atomic_promotion_current,
        "expected_symbol": symbol or resolved_symbol,
        "expected_result_version": result_version or resolved_result_version,
        "facts_package_hash": str(lineage.get("facts_package_hash") or current_pointer_lineage.get("facts_package_hash") or ""),
        "model_ledger_id": str(lineage.get("model_ledger_id") or current_pointer_lineage.get("model_ledger_id") or ""),
        "latest_receipt_status": receipt.get("status") or "missing",
        "latest_receipt_task_id": receipt.get("task_id") or "",
        "current_pointer": current_pointer,
        "last_good_pointer": last_good_pointer,
        "last_good_pointer_ready": last_good_pointer_ready,
        "current_last_good_distinct": bool(
            current_version_id and last_good_version_id and current_version_id != last_good_version_id
        ),
        "resolved_current": resolved_current,
        "resolved_pointer_kind": str(resolved_current.get("selected_pointer_kind") or ""),
        "resolved_symbol": resolved_symbol,
        "resolved_result_version": resolved_result_version,
        "degraded_recovery_active": degraded_recovery_active,
        "no_valid_version_available": resolved_current.get("no_valid_version_available") is True,
        "duckdb_readback": duckdb_readback,
        "duckdb_readback_verified": duckdb_readback.get("verified") is True,
        "version_manifest": version_manifest,
        "manifest_current_version_ready": manifest_current_version_ready,
        "manifest_version_count": int(version_manifest.get("version_count") or 0),
        "retention_protects_current_and_last_good": retention_protects_current_and_last_good,
        "current_result_storage_acceptance_ready": current_result_storage_acceptance_ready,
        "current_result_storage_acceptance_status": (
            "current_result_storage_acceptance_ready"
            if current_result_storage_acceptance_ready
            else "current_result_storage_acceptance_pending_second_valid_version_or_recovery_guard"
        ),
        "ttl_state": ttl_state,
        "ttl_status": str(ttl_state.get("status") or "ttl_source_unavailable"),
        "ttl_age_seconds": ttl_state.get("age_seconds"),
        "ttl_seconds": int(ttl_state.get("ttl_seconds") or CURRENT_RESULT_TTL_SECONDS),
        "ttl_refresh_recommended": ttl_state.get("refresh_recommended") is True,
        "retention_plan": retention_plan,
        "retention_status": str(retention_plan.get("status") or "retention_plan_unavailable"),
        "retention_max_versions": int(
            retention_plan.get("effective_max_versions") or CURRENT_RESULT_MAX_VERSIONS
        ),
        "retention_protected_version_ids": list(retention_plan.get("protected_version_ids") or []),
        "retention_cleanup_candidate_count": int(
            retention_plan.get("cleanup_candidate_count") or 0
        ),
        "retention_delete_executed": False,
        "retention_cleanup_journal": cleanup_journal_summary,
        "retention_cleanup_journal_status": cleanup_journal_summary["status"],
        "retention_cleanup_recovery_ready": cleanup_journal_summary["recovery_ready"],
        "retention_cleanup_pending_artifact_count": cleanup_journal_summary["pending_artifact_count"],
        "retention_cleanup_completed": cleanup_journal_summary["cleanup_completed"],
        "latest_retention_cleanup_receipt_status": cleanup_receipt.get("status") or "missing",
        "latest_retention_cleanup_receipt_read_status": cleanup_receipt_read_status,
        "latest_retention_cleanup_task_id": cleanup_receipt.get("task_id") or "",
        "latest_retention_deleted_version_count": int(
            cleanup_receipt.get("deleted_version_count") or 0
        ),
        "physical_write_executed": atomic_promotion_current,
        "production_storage_complete": False,
        "cache_only": True,
        "cache_get_writes_files": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def storage_current_result_cache() -> dict[str, Any]:
    evidence = storage_current_result_atomic_promotion_evidence()
    resolution = dict(evidence.get("resolved_current") or {})
    selected = dict(resolution.get("selected_pointer") or {})
    readback = dict(evidence.get("duckdb_readback") or {})
    row = {
        "symbol": str(readback.get("symbol") or ""),
        "result_version": str(readback.get("result_version") or ""),
        "facts_package_hash": str(readback.get("facts_package_hash") or ""),
        "model_ledger_id": str(readback.get("model_ledger_id") or ""),
    }
    selected_lineage = dict(selected.get("lineage") or {})
    readback_ready = bool(
        evidence.get("duckdb_readback_verified") is True
        and row["symbol"]
        and row["result_version"]
    )
    if resolution.get("degraded_recovery_active") is True and readback_ready:
        status = "storage_current_result_cache_degraded_last_good"
    elif resolution.get("selected_pointer_kind") == "current" and readback_ready:
        status = "storage_current_result_cache_ready_current"
    elif resolution.get("no_valid_version_available") is True:
        status = "storage_current_result_cache_missing"
    else:
        status = "storage_current_result_cache_waiting_validated_artifact"
    packet = {
        "schema_version": "command_center_3_storage_current_result_cache.v1",
        "status": status,
        "store": "versioned_parquet_duckdb",
        "dataset": CURRENT_RESULT_LINEAGE_DATASET,
        "symbol": row["symbol"] if readback_ready else "",
        "result_version": row["result_version"] if readback_ready else "",
        "facts_package_hash": row["facts_package_hash"] if readback_ready else "",
        "model_ledger_id": row["model_ledger_id"] if readback_ready else "",
        "data_date": str(readback.get("data_date") or selected_lineage.get("data_date") or "") if readback_ready else "",
        "freshness_state": str(readback.get("freshness_state") or selected_lineage.get("freshness_state") or "") if readback_ready else "",
        "selected_pointer_kind": str(resolution.get("selected_pointer_kind") or ""),
        "selected_version_id": str(resolution.get("selected_version_id") or ""),
        "selected_artifact_sha256": str(selected.get("artifact_sha256") or ""),
        "degraded_recovery_active": resolution.get("degraded_recovery_active") is True,
        "no_valid_version_available": resolution.get("no_valid_version_available") is True,
        "result": row if readback_ready else {},
        "result_row_count": 1 if readback_ready else 0,
        "duckdb_readback_verified": readback_ready,
        "manifest_status": str((evidence.get("version_manifest") or {}).get("status") or "missing"),
        "manifest_version_count": int(evidence.get("manifest_version_count") or 0),
        "ttl_status": str(evidence.get("ttl_status") or "ttl_source_unavailable"),
        "ttl_age_seconds": evidence.get("ttl_age_seconds"),
        "ttl_seconds": int(evidence.get("ttl_seconds") or CURRENT_RESULT_TTL_SECONDS),
        "ttl_refresh_recommended": evidence.get("ttl_refresh_recommended") is True,
        "retention_status": str(evidence.get("retention_status") or "retention_plan_unavailable"),
        "retention_max_versions": int(
            evidence.get("retention_max_versions") or CURRENT_RESULT_MAX_VERSIONS
        ),
        "retention_protected_version_ids": list(
            evidence.get("retention_protected_version_ids") or []
        ),
        "retention_cleanup_candidate_count": int(
            evidence.get("retention_cleanup_candidate_count") or 0
        ),
        "retention_delete_executed": False,
        "retention_cleanup_journal_status": str(
            evidence.get("retention_cleanup_journal_status") or "missing"
        ),
        "retention_cleanup_recovery_ready": evidence.get("retention_cleanup_recovery_ready") is True,
        "retention_cleanup_pending_artifact_count": int(
            evidence.get("retention_cleanup_pending_artifact_count") or 0
        ),
        "retention_cleanup_completed": evidence.get("retention_cleanup_completed") is True,
        "source_atomic_task_id": str(evidence.get("latest_receipt_task_id") or ""),
        "source_result_task_id": str(selected_lineage.get("task_id") or ""),
        "source_scope_hash": str(selected_lineage.get("scope_hash") or ""),
        "source_atomic_status": str(evidence.get("status") or ""),
        "resolution_blockers": list(resolution.get("blockers") or []),
        "cache_only": True,
        "cache_get_creates_task": False,
        "cache_get_writes_files": False,
        "cache_get_refreshes_stale_result": False,
        "cache_get_deletes_versions": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    return _attach_storage_lineage(
        packet,
        api="local_storage_current_result_cache",
        endpoint="GET /api/storage/current-result",
        dataset=CURRENT_RESULT_LINEAGE_DATASET,
        row_count=packet["result_row_count"],
        path=_path_label(Path(str(selected.get("artifact_path") or "")))
        if selected.get("artifact_path")
        else "",
    )


def _storage_production_promotion_review_row(
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
        "production_blocker": bool(production_blocker),
        "local_ready": bool(passed) or bool(production_blocker),
        "evidence": evidence,
        "next_action": next_action,
        "writes_parquet": False,
        "writes_manifest": False,
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def storage_production_promotion_review_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload_safe = payload_safe or {}
    production_readiness = storage_production_readiness()
    blocker_audit = storage_production_blocker_audit(production_readiness)
    readiness_receipt = storage_production_readiness_receipt(production_readiness, blocker_audit)
    activation_receipt = storage_physical_migration_activation_receipt(
        production_readiness,
        blocker_audit,
        readiness_receipt,
    )
    execution_recipe = storage_physical_execution_recipe(
        production_readiness,
        blocker_audit,
        activation_receipt,
    )
    execution_request = storage_physical_execution_request_evidence()
    durable_recipe = storage_physical_durable_evidence_recipe(
        production_readiness,
        blocker_audit,
        activation_receipt,
        execution_recipe,
        execution_request,
    )
    current_result_atomic_promotion = storage_current_result_atomic_promotion_evidence()
    current_result_atomic_promotion_done = bool(
        durable_recipe.get("current_result_atomic_parquet_promotion_done") is True
        and current_result_atomic_promotion.get("atomic_promotion_current") is True
        and current_result_atomic_promotion.get("physical_write_executed") is True
        and current_result_atomic_promotion.get("duckdb_readback_verified") is True
        and current_result_atomic_promotion.get("manifest_current_version_ready") is True
        and current_result_atomic_promotion.get("production_storage_complete") is False
        and current_result_atomic_promotion.get("external_calls_triggered") is False
    )
    current_result_storage_acceptance_ready = bool(
        current_result_atomic_promotion_done
        and current_result_atomic_promotion.get("current_result_storage_acceptance_ready") is True
        and current_result_atomic_promotion.get("last_good_pointer_ready") is True
        and current_result_atomic_promotion.get("retention_protects_current_and_last_good") is True
    )
    approved_by_user = payload_safe.get("approved_by_user") is True
    latest_scope_hash = str(
        execution_request.get("physical_execution_scope_hash")
        or execution_recipe.get("physical_execution_scope_hash")
        or ""
    )
    requested_scope_hash = str(payload_safe.get("physical_execution_scope_hash") or payload_safe.get("scope_hash") or "")
    request_ready = bool(
        execution_request.get("local_execution_request_ready") is True
        and execution_request.get("requested_scope_hash_matches_latest") is True
        and execution_request.get("physical_task_created") is False
        and execution_request.get("physical_task_executed") is False
    )
    requested_hash_matches_latest = bool(latest_scope_hash and requested_scope_hash == latest_scope_hash and request_ready)
    durable_visible = durable_recipe.get("schema_version") == STORAGE_PHYSICAL_DURABLE_EVIDENCE_SCHEMA_VERSION
    pre_review_missing = [str(key) for key in durable_recipe.get("missing_durable_evidence") or []]
    remaining_durable_evidence = [key for key in pre_review_missing if key != "production_promotion_review_required"]
    no_side_effect_boundary = bool(
        durable_recipe.get("external_calls_triggered") is False
        and durable_recipe.get("tushare_called") is False
        and durable_recipe.get("deepseek_called") is False
        and durable_recipe.get("github_called") is False
        and durable_recipe.get("writes_parquet") is False
        and durable_recipe.get("writes_manifest") is False
        and durable_recipe.get("deletes_artifacts") is False
        and durable_recipe.get("does_not_execute_trades") is True
        and durable_recipe.get("does_not_modify_strategy_action") is True
        and durable_recipe.get("contains_secret") is False
        and execution_request.get("external_calls_triggered") is False
        and execution_request.get("tushare_called") is False
        and execution_request.get("deepseek_called") is False
        and execution_request.get("github_called") is False
        and execution_request.get("does_not_execute_trades") is True
        and execution_request.get("does_not_modify_strategy_action") is True
        and execution_request.get("contains_secret") is False
    )
    if not approved_by_user:
        status = "storage_production_promotion_review_blocked_user_confirmation_required"
    elif not request_ready:
        status = "storage_production_promotion_review_blocked_physical_execution_request"
    elif not requested_scope_hash:
        status = "storage_production_promotion_review_blocked_scope_hash_required"
    elif not requested_hash_matches_latest:
        status = "storage_production_promotion_review_blocked_scope_hash_mismatch"
    elif not durable_visible:
        status = "storage_production_promotion_review_blocked_durable_evidence_recipe"
    elif not no_side_effect_boundary:
        status = "storage_production_promotion_review_blocked_boundary_regression"
    elif current_result_storage_acceptance_ready:
        status = "storage_current_result_acceptance_ready_full_storage_pending"
    else:
        status = "storage_production_promotion_review_ready_production_still_blocked"
    local_review_ready = status in {
        "storage_production_promotion_review_ready_production_still_blocked",
        "storage_current_result_acceptance_ready_full_storage_pending",
    }
    rows = [
        _storage_production_promotion_review_row(
            "explicit_production_promotion_review_task",
            passed=approved_by_user,
            status="passed_explicit_post" if approved_by_user else "blocked_confirmation_required",
            evidence=f"approved_by_user={approved_by_user}",
            next_action="Require an explicit POST before recording any production promotion review.",
        ),
        _storage_production_promotion_review_row(
            "physical_execution_request_visible",
            passed=request_ready,
            status="passed_execution_request_visible" if request_ready else "blocked_missing_execution_request",
            evidence=f"request_status={execution_request.get('status')}",
            next_action="Record a scope-bound physical execution request ticket before review.",
        ),
        _storage_production_promotion_review_row(
            "physical_execution_scope_hash_bound",
            passed=requested_hash_matches_latest,
            status="passed_scope_bound" if requested_hash_matches_latest else "blocked_scope_hash_mismatch_or_missing",
            evidence=(
                f"requested_scope_hash_short={requested_scope_hash[:12]}; "
                f"latest_scope_hash_short={latest_scope_hash[:12]}"
            ),
            next_action="Regenerate the review from the current Storage page if the execution request changes.",
        ),
        _storage_production_promotion_review_row(
            "durable_evidence_recipe_visible",
            passed=durable_visible,
            status="passed_durable_recipe_visible" if durable_visible else "blocked_missing_durable_recipe",
            evidence=(
                f"durable_recipe_status={durable_recipe.get('status')}; "
                f"pre_review_blocker_count={durable_recipe.get('production_blocker_count')}"
            ),
            next_action="Keep durable evidence rows visible before any production claim.",
        ),
        _storage_production_promotion_review_row(
            "current_result_atomic_parquet_evidence_reviewed",
            passed=current_result_atomic_promotion_done,
            status="passed_local_atomic_parquet_direct_evidence"
            if current_result_atomic_promotion_done
            else "pending_atomic_parquet_direct_evidence",
            evidence=(
                f"status={current_result_atomic_promotion.get('status')}; "
                f"task_id={current_result_atomic_promotion.get('latest_receipt_task_id')}; "
                f"symbol={current_result_atomic_promotion.get('expected_symbol')}; "
                f"result_version={current_result_atomic_promotion.get('expected_result_version')}; "
                f"duckdb_readback_verified={current_result_atomic_promotion.get('duckdb_readback_verified')}; "
                f"manifest_current_version_ready={current_result_atomic_promotion.get('manifest_current_version_ready')}; "
                f"last_good_pointer_ready={current_result_atomic_promotion.get('last_good_pointer_ready')}; "
                f"current_result_storage_acceptance_ready={current_result_storage_acceptance_ready}"
            ),
            next_action=(
                "Retain this pointer/receipt proof and continue the remaining storage stages."
                if current_result_atomic_promotion_done
                else "Run the explicit canonical-result atomic promotion before production review."
            ),
            production_blocker=not current_result_atomic_promotion_done,
        ),
        _storage_production_promotion_review_row(
            "remaining_direct_evidence_reviewed",
            passed=not remaining_durable_evidence,
            status="passed_all_current_direct_evidence_reviewed"
            if not remaining_durable_evidence
            else "pending_remaining_durable_evidence",
            evidence=f"remaining_durable_evidence={remaining_durable_evidence}",
            next_action="Finish remaining direct evidence before any production storage promotion.",
            production_blocker=bool(remaining_durable_evidence),
        ),
        _storage_production_promotion_review_row(
            "production_completion_stays_blocked",
            passed=False,
            status="production_storage_still_blocked",
            evidence="This review never flips production_storage_complete.",
            next_action="Use a separate production gate before marking storage production complete.",
            production_blocker=True,
        ),
        _storage_production_promotion_review_row(
            "no_provider_model_github_trade_secret_boundary",
            passed=no_side_effect_boundary,
            status="passed_no_side_effects" if no_side_effect_boundary else "blocked_boundary_regression",
            evidence="Review reads local receipts only and does not write data, call providers/models/GitHub, trade, or expose secrets.",
            next_action="Preserve cache/render read-only and explicit POST task boundaries.",
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if not row.get("passed") and not row.get("production_blocker")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    promotion_review_scope_input = {
        "schema_version": "command_center_3_storage_production_promotion_review.v1",
        "physical_execution_scope_hash": latest_scope_hash,
        "durable_evidence_schema_version": durable_recipe.get("schema_version"),
        "pre_review_missing_durable_evidence": pre_review_missing,
        "remaining_durable_evidence": remaining_durable_evidence,
        "current_result_atomic_parquet_promotion_done": current_result_atomic_promotion_done,
        "current_result_storage_acceptance_ready": current_result_storage_acceptance_ready,
        "current_result_storage_direct_evidence_complete": current_result_storage_acceptance_ready,
        "full_storage_migration_pending": True,
        "current_result_atomic_parquet_task_id": str(
            current_result_atomic_promotion.get("latest_receipt_task_id") or ""
        ),
        "current_result_atomic_parquet_result_version": str(
            current_result_atomic_promotion.get("expected_result_version") or ""
        ),
        "current_result_atomic_parquet_duckdb_readback_verified": (
            current_result_atomic_promotion.get("duckdb_readback_verified") is True
        ),
        "current_result_atomic_parquet_manifest_version_ready": (
            current_result_atomic_promotion.get("manifest_current_version_ready") is True
        ),
        "production_storage_complete": False,
    }
    call_ledger = _storage_cache_call_ledger(
        "local_storage_production_promotion_review",
        endpoint="POST /api/storage/production-promotion-review",
        status=status,
        row_count=len(rows),
    )
    call_ledger[0]["request_params_safe"] = {
        "source": payload_safe.get("source") or "storage_page_button",
        "approved_by_user": approved_by_user,
        "reviewer": _safe_scalar(payload_safe.get("reviewer")) or "",
        "physical_execution_scope_hash_short": requested_scope_hash[:12],
        "local_review_ready": local_review_ready,
        "write_parquet_allowed": False,
        "write_manifest_allowed": False,
        "delete_allowed": False,
        "external_sources_allowed": False,
    }
    return {
        "schema_version": "command_center_3_storage_production_promotion_review.v1",
        "packet_key": STORAGE_PRODUCTION_PROMOTION_REVIEW_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_storage_production_promotion_review",
        "scope": "button_gated_local_storage_production_promotion_review_no_write_no_external_call",
        "route": "POST /api/storage/production-promotion-review",
        "task_type": "run_storage_production_promotion_review",
        "ltg": "LTG-05/LTG-11",
        "explicit_production_promotion_review_done": local_review_ready,
        "local_promotion_review_ready": local_review_ready,
        "approved_by_user": approved_by_user,
        "requires_user_confirmation": True,
        "physical_execution_request_visible": request_ready,
        "durable_evidence_recipe_visible": durable_visible,
        "requested_physical_execution_scope_hash_matches_latest": requested_hash_matches_latest,
        "physical_execution_scope_hash": latest_scope_hash if requested_hash_matches_latest else "",
        "physical_execution_scope_hash_short": latest_scope_hash[:12] if latest_scope_hash else "",
        "requested_physical_execution_scope_hash_short": requested_scope_hash[:12],
        "promotion_review_scope_hash": _json_sha256(promotion_review_scope_input),
        "promotion_review_scope_hash_input_includes_secret": False,
        "pre_review_missing_durable_evidence": pre_review_missing,
        "remaining_durable_evidence": remaining_durable_evidence,
        "current_result_atomic_parquet_promotion_done": current_result_atomic_promotion_done,
        "current_result_storage_acceptance_ready": current_result_storage_acceptance_ready,
        "current_result_storage_direct_evidence_complete": current_result_storage_acceptance_ready,
        "full_storage_migration_pending": True,
        "current_result_atomic_parquet_task_id": str(
            current_result_atomic_promotion.get("latest_receipt_task_id") or ""
        ),
        "current_result_atomic_parquet_symbol": str(
            current_result_atomic_promotion.get("expected_symbol") or ""
        ),
        "current_result_atomic_parquet_result_version": str(
            current_result_atomic_promotion.get("expected_result_version") or ""
        ),
        "durable_evidence_blocker_count_before_review": int(durable_recipe.get("production_blocker_count") or 0),
        "local_blocker_count": len(local_blockers),
        "local_blockers": local_blockers,
        "production_blocker_count": len(production_blockers),
        "production_blockers": production_blockers,
        "ready_to_mark_production_storage_complete": False,
        "production_storage_complete": False,
        "durable_evidence_complete": False,
        "durable_promotion_ready": False,
        "physical_task_created": False,
        "physical_task_executed": False,
        "source_physical_task_created": bool(
            current_result_atomic_promotion.get("latest_receipt_task_id")
        ),
        "source_physical_task_executed": current_result_atomic_promotion_done,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "artifact_cleanup_delete_executed": False,
        "writes_parquet": False,
        "writes_manifest": False,
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "runs_commands": False,
        "reads_row_payloads": False,
        "reads_env_files": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "not_allowed_next_steps": [
            "treat_production_promotion_review_as_storage_production_complete",
            "write_parquet_from_promotion_review",
            "write_manifest_from_promotion_review",
            "delete_artifacts_from_promotion_review",
            "refresh_providers_from_promotion_review",
            "call_Tushare_from_promotion_review",
            "call_DeepSeek_from_promotion_review",
            "call_GitHub_from_promotion_review",
            "execute_trades_from_promotion_review",
            "modify_strategy_action_from_promotion_review",
        ],
        "rows": rows,
        "call_ledger": call_ledger,
        "warnings": [
            "Storage production promotion review 只记录本地 promotion boundary；不会写 Parquet、写 manifest、删除文件或调用外部源。",
            "该 review 不代表 production storage 完成，production_storage_complete 必须保持 false。",
        ],
    }


def _missing_storage_production_promotion_review(now: str | None = None) -> dict[str, Any]:
    rows = [
        _storage_production_promotion_review_row(
            "production_promotion_review_visible",
            passed=False,
            status="blocked_missing_promotion_review",
            evidence="No button-gated storage production promotion review has been recorded yet.",
            next_action="Record the explicit promotion review after the physical execution request is scope-bound.",
        )
    ]
    return {
        "schema_version": "command_center_3_storage_production_promotion_review.v1",
        "packet_key": STORAGE_PRODUCTION_PROMOTION_REVIEW_PACKET_KEY,
        "task_id": "",
        "status": "storage_production_promotion_review_missing",
        "mode": "cache_only_missing_placeholder",
        "scope": "button_gated_local_storage_production_promotion_review_no_write_no_external_call",
        "route": "POST /api/storage/production-promotion-review",
        "task_type": "run_storage_production_promotion_review",
        "ltg": "LTG-05/LTG-11",
        "explicit_production_promotion_review_done": False,
        "local_promotion_review_ready": False,
        "approved_by_user": False,
        "requires_user_confirmation": True,
        "physical_execution_request_visible": False,
        "durable_evidence_recipe_visible": False,
        "requested_physical_execution_scope_hash_matches_latest": False,
        "physical_execution_scope_hash": "",
        "physical_execution_scope_hash_short": "",
        "promotion_review_scope_hash": "",
        "promotion_review_scope_hash_input_includes_secret": False,
        "remaining_durable_evidence": ["production_promotion_review_required"],
        "local_blocker_count": 1,
        "production_blocker_count": 1,
        "ready_to_mark_production_storage_complete": False,
        "production_storage_complete": False,
        "durable_evidence_complete": False,
        "durable_promotion_ready": False,
        "writes_parquet": False,
        "writes_manifest": False,
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "runs_commands": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_production_promotion_review",
            endpoint="GET /api/storage",
            status="storage_production_promotion_review_missing",
            row_count=len(rows),
            now=now,
        ),
        "warnings": [
            "Storage production promotion review 尚未生成；这不是 production storage 完成证据。",
        ],
    }


def storage_production_promotion_review_evidence() -> dict[str, Any]:
    packet, read_status = _read_storage_meta_packet_no_init(STORAGE_PRODUCTION_PROMOTION_REVIEW_PACKET_KEY)
    if read_status != "packet_present" or not isinstance(packet, Mapping):
        return _missing_storage_production_promotion_review()
    evidence = dict(packet)
    evidence["read_status"] = read_status
    evidence.setdefault("local_promotion_review_ready", False)
    evidence.setdefault("production_storage_complete", False)
    evidence.setdefault("ready_to_mark_production_storage_complete", False)
    evidence.setdefault("external_calls_triggered", False)
    evidence.setdefault("tushare_called", False)
    evidence.setdefault("deepseek_called", False)
    evidence.setdefault("github_called", False)
    evidence.setdefault("does_not_execute_trades", True)
    evidence.setdefault("does_not_modify_strategy_action", True)
    evidence.setdefault("contains_secret", False)
    return evidence


def run_storage_production_promotion_review_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "approved_by_user": payload_map.get("approved_by_user") is True,
        "reviewer": _safe_scalar(payload_map.get("reviewer")) or "",
        "physical_execution_scope_hash": str(
            payload_map.get("physical_execution_scope_hash") or payload_map.get("scope_hash") or ""
        ),
        "external_sources_allowed": False,
        "write_parquet_allowed": False,
        "write_manifest_allowed": False,
        "delete_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_production_promotion_review",
        output_packet_key=STORAGE_PRODUCTION_PROMOTION_REVIEW_PACKET_KEY,
        payload=task_payload,
        current_step="storage_production_promotion_review_queued",
        warnings=[
            "storage production promotion review 只生成本地审查 receipt；不会写 Parquet、写 manifest、删除文件或调用外部源。",
            "该任务不修改 strategy action、不执行真实交易，不代表 production storage 完成。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="building_storage_production_promotion_review",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_production_promotion_review_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(STORAGE_PRODUCTION_PROMOTION_REVIEW_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_production_promotion_review_packet_persist_failed",
            error_message_safe="storage_production_promotion_review_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_production_promotion_review_failed_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=str(packet.get("status") or "storage_production_promotion_review_recorded"),
        call_ledger=packet["call_ledger"],
        warning="storage_production_promotion_review_recorded_no_write_no_delete_no_external_call",
    ) or task


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = _safe_scalar(value) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _storage_cache_warning(endpoint: str) -> str:
    return f"{endpoint} 只读取本地 storage cache；不会调用 Tushare、DeepSeek、GitHub 或真实交易接口。"


def _storage_cache_call_ledger(
    api: str,
    *,
    endpoint: str,
    status: Any = None,
    dataset: Any = None,
    row_count: Any = None,
    path: Any = None,
    now: str | None = None,
) -> list[dict[str, Any]]:
    row: dict[str, Any] = {
        "api": api,
        "endpoint": endpoint,
        "source_type": "local_storage_cache",
        "external": False,
        "call_status": _safe_scalar(status) or "cache_read",
        "local_fetched_at": now or _now_iso(),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    safe_dataset = _safe_scalar(dataset)
    if safe_dataset:
        row["dataset"] = safe_dataset
    safe_path = _safe_scalar(path)
    if safe_path:
        row["path"] = safe_path
    if isinstance(row_count, int):
        row["row_count"] = row_count
    return [row]


def _attach_storage_lineage(
    packet: dict[str, Any],
    *,
    api: str,
    endpoint: str,
    dataset: Any = None,
    row_count: Any = None,
    path: Any = None,
) -> dict[str, Any]:
    packet["call_ledger"] = _storage_cache_call_ledger(
        api,
        endpoint=endpoint,
        status=packet.get("status") or packet.get("metadata_status") or packet.get("store"),
        dataset=dataset if dataset is not None else packet.get("dataset"),
        row_count=row_count if row_count is not None else packet.get("row_count"),
        path=path if path is not None else packet.get("path"),
    )
    packet["warnings"] = [_storage_cache_warning(endpoint)]
    return packet


def storage_dataset_catalog() -> dict[str, Any]:
    catalog = dataset_catalog()
    implementation_status = dataset_implementation_status()
    production_readiness = storage_production_readiness()
    production_blocker_audit = storage_production_blocker_audit(production_readiness)
    production_readiness_receipt = storage_production_readiness_receipt(
        production_readiness,
        production_blocker_audit,
    )
    physical_migration_activation_receipt = storage_physical_migration_activation_receipt(
        production_readiness,
        production_blocker_audit,
        production_readiness_receipt,
    )
    physical_execution_recipe = storage_physical_execution_recipe(
        production_readiness,
        production_blocker_audit,
        physical_migration_activation_receipt,
    )
    physical_execution_request = storage_physical_execution_request_evidence()
    physical_durable_evidence_recipe = storage_physical_durable_evidence_recipe(
        production_readiness,
        production_blocker_audit,
        physical_migration_activation_receipt,
        physical_execution_recipe,
        physical_execution_request,
    )
    physical_execution_phase_a = storage_physical_execution_phase_a_evidence()
    production_promotion_review = storage_production_promotion_review_evidence()
    artifact_hygiene = storage_artifact_hygiene_status()
    dataset_version_policy = storage_dataset_version_policy()
    dataset_version_manifest_evidence = storage_dataset_version_manifest_evidence_audit()
    backtest_results_schema_seed_evidence = storage_backtest_results_schema_seed_evidence()
    schema_validation_acceptance_evidence = production_readiness.get("schema_validation_acceptance_evidence") or {}
    schema_migration_preflight = storage_schema_migration_preflight()
    schema_migration_execution_evidence = production_readiness.get("schema_migration_execution_evidence") or {}
    duckdb_query_service = duckdb_query_service_policy()
    packet = {
        "schema_version": "command_center_3_storage_dataset_catalog.v1",
        "store": "parquet_duckdb",
        "status": "ready",
        "mode": "cache_only",
        "dataset_catalog": catalog,
        "dataset_implementation_status": implementation_status,
        "production_readiness": production_readiness,
        "storage_production_blocker_audit": production_blocker_audit,
        "storage_production_blocker_rows": production_blocker_audit["rows"],
        "storage_production_readiness_receipt": production_readiness_receipt,
        "storage_production_readiness_receipt_rows": production_readiness_receipt["rows"],
        "storage_physical_migration_activation_receipt": physical_migration_activation_receipt,
        "storage_physical_migration_activation_rows": physical_migration_activation_receipt["rows"],
        "storage_physical_execution_recipe": physical_execution_recipe,
        "storage_physical_execution_recipe_rows": physical_execution_recipe["rows"],
        "storage_physical_execution_recipe_status": physical_execution_recipe["status"],
        "storage_physical_execution_recipe_ready": physical_execution_recipe["local_recipe_ready"],
        "storage_physical_execution_request": physical_execution_request,
        "storage_physical_execution_request_rows": physical_execution_request.get("rows") or [],
        "storage_physical_execution_request_status": physical_execution_request.get("status"),
        "storage_physical_execution_request_ready": physical_execution_request.get("local_execution_request_ready"),
        "storage_physical_durable_evidence_recipe": physical_durable_evidence_recipe,
        "storage_physical_durable_evidence_rows": physical_durable_evidence_recipe["rows"],
        "storage_physical_durable_evidence_recipe_status": physical_durable_evidence_recipe["status"],
        "storage_physical_durable_evidence_recipe_ready": physical_durable_evidence_recipe["local_recipe_ready"],
        "storage_physical_durable_evidence_production_blocker_count": physical_durable_evidence_recipe[
            "production_blocker_count"
        ],
        "storage_physical_execution_phase_a": physical_execution_phase_a,
        "storage_physical_execution_phase_a_rows": physical_execution_phase_a.get("rows") or [],
        "storage_physical_execution_phase_a_status": physical_execution_phase_a.get("status"),
        "storage_physical_execution_phase_a_ready": physical_execution_phase_a.get(
            "local_phase_a_execution_ready"
        ),
        "storage_production_promotion_review": production_promotion_review,
        "storage_production_promotion_review_rows": production_promotion_review.get("rows") or [],
        "storage_production_promotion_review_status": production_promotion_review.get("status"),
        "storage_production_promotion_review_ready": production_promotion_review.get(
            "local_promotion_review_ready"
        ),
        "artifact_hygiene": artifact_hygiene,
        "artifact_cleanup_review_contract": artifact_hygiene["artifact_cleanup_review_contract"],
        "artifact_cleanup_review_rows": artifact_hygiene["artifact_cleanup_review_rows"],
        "schema_validation_acceptance_evidence": schema_validation_acceptance_evidence,
        "schema_validation_acceptance_evidence_rows": schema_validation_acceptance_evidence.get("rows") or [],
        "schema_validation_acceptance_evidence_status": schema_validation_acceptance_evidence.get("status"),
        "schema_validation_acceptance_accepted_dataset_count": schema_validation_acceptance_evidence.get(
            "accepted_dataset_count"
        ),
        "schema_validation_acceptance_blocked_dataset_count": schema_validation_acceptance_evidence.get(
            "blocked_dataset_count"
        ),
        "dataset_version_policy": dataset_version_policy,
        "dataset_version_rows": dataset_version_policy["rows"],
        "dataset_version_status_counts": dataset_version_policy["status_counts"],
        "dataset_version_manifest_evidence_audit": dataset_version_manifest_evidence,
        "dataset_version_manifest_evidence_rows": dataset_version_manifest_evidence["rows"],
        "dataset_version_manifest_evidence_status_counts": dataset_version_manifest_evidence["status_counts"],
        "backtest_results_schema_seed_evidence": backtest_results_schema_seed_evidence,
        "backtest_results_schema_seed_status": backtest_results_schema_seed_evidence.get("status"),
        "backtest_results_schema_seed_ready": backtest_results_schema_seed_evidence.get(
            "schema_seed_ready_for_schema_acceptance"
        ),
        "schema_migration_preflight": schema_migration_preflight,
        "schema_migration_rows": schema_migration_preflight["rows"],
        "schema_migration_status_counts": schema_migration_preflight["status_counts"],
        "schema_migration_execution_evidence": schema_migration_execution_evidence,
        "schema_migration_execution_status": schema_migration_execution_evidence.get("status"),
        "schema_migration_task_executed": schema_migration_execution_evidence.get("schema_migration_executed"),
        "duckdb_query_service": duckdb_query_service,
        "duckdb_query_service_rows": duckdb_query_service["rows"],
        "duckdb_query_service_status": duckdb_query_service["status"],
        "supported_datasets": list(CANONICAL_PARQUET_DATASETS),
        "supported_aliases": sorted(key for key, value in SUPPORTED_PARQUET_DATASETS.items() if key != value),
        "dataset_count": len(catalog),
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }
    return _attach_storage_lineage(
        packet,
        api="local_storage_dataset_catalog_cache",
        endpoint="GET /api/storage/catalog",
        row_count=len(catalog),
    )


def parquet_dataset_status(
    dataset: str,
    *,
    limit: int = 100,
    cursor: str | int | None = None,
    ts_code: str | None = None,
    trade_date: str | int | None = None,
    start_date: str | int | None = None,
    end_date: str | int | None = None,
) -> dict[str, Any]:
    selected = _canonical_dataset(dataset)
    if not selected:
        return _attach_storage_lineage(
            {
                "schema_version": "command_center_3_storage_dataset.v1",
                "status": "unsupported_dataset",
                "dataset": str(dataset or ""),
                "supported_datasets": list(CANONICAL_PARQUET_DATASETS),
                "supported_aliases": sorted(key for key, value in SUPPORTED_PARQUET_DATASETS.items() if key != value),
                "cache_only": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_modify_strategy_action": True,
                "does_not_execute_trades": True,
            },
            api="local_storage_dataset_cache",
            endpoint=f"GET /api/storage/{dataset}",
            dataset=str(dataset or ""),
            row_count=0,
        )
    path = parquet_store.dataset_path(root=PARQUET_ROOT, name=selected)
    metadata = parquet_store.dataset_metadata(root=PARQUET_ROOT, name=selected)
    cache_ttl = _cache_ttl_status(selected, path, metadata)
    schema_contract = _schema_contract(selected)
    dataset_version_policy = _dataset_version_policy_row(selected, metadata=metadata)
    schema_migration = _schema_migration_row(selected, metadata=metadata)
    partition_plan = _partition_plan(selected)
    compaction_plan = _compaction_plan(selected, path, metadata)
    query = duckdb_store.query_parquet_dataset(
        path,
        limit=limit,
        cursor=cursor,
        projection_columns=_dataset_query_projection_columns(selected),
        ts_code=ts_code,
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
    )
    metadata["path"] = _path_label(path)
    query["path"] = _path_label(path)
    packet = {
        "schema_version": "command_center_3_storage_dataset.v1",
        "store": "parquet_duckdb",
        "status": metadata.get("status", "missing"),
        "dataset": selected,
        "metadata": metadata,
        "cache_ttl": cache_ttl,
        "schema_contract": schema_contract,
        "dataset_version_policy": dataset_version_policy,
        "schema_migration": schema_migration,
        "partition_plan": partition_plan,
        "compaction_plan": compaction_plan,
        "query": query,
        "query_service_policy": _duckdb_query_service_row(selected),
        "query_wrapper": query.get("query_wrapper"),
        "query_filters": query.get("query_filters") or {},
        "applied_filters": query.get("applied_filters") or [],
        "skipped_filters": query.get("skipped_filters") or [],
        "query_result_contract": query.get("query_result_contract") or {},
        "page_info": query.get("page_info") or {},
        "projected_columns": query.get("projected_columns") or [],
        "missing_projected_columns": query.get("missing_projected_columns") or [],
        "row_count": int(query.get("row_count") or 0),
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }
    return _attach_storage_lineage(
        packet,
        api="local_storage_dataset_cache",
        endpoint=f"GET /api/storage/{selected}",
        dataset=selected,
        row_count=packet["row_count"],
        path=metadata["path"],
    )


def _duckdb_read_validation_row(dataset: str, packet: Mapping[str, Any]) -> dict[str, Any]:
    contract = packet.get("query_result_contract") if isinstance(packet.get("query_result_contract"), Mapping) else {}
    policy = packet.get("query_service_policy") if isinstance(packet.get("query_service_policy"), Mapping) else {}
    contract_ready = (
        contract.get("schema_version") == "duckdb_query_result_contract.v1"
        and packet.get("query_wrapper") == "duckdb_filtered_parquet.v1"
        and policy.get("safe_parameter_binding") is True
        and policy.get("query_result_contract_enabled") is True
        and packet.get("cache_only") is True
        and packet.get("external_calls_triggered") is False
        and packet.get("tushare_called") is False
        and packet.get("deepseek_called") is False
        and packet.get("github_called") is False
        and packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
    )
    return {
        "dataset": dataset,
        "status": packet.get("status") or "missing",
        "query_wrapper": packet.get("query_wrapper") or "",
        "query_result_contract_schema_version": contract.get("schema_version") or "",
        "row_count": int(packet.get("row_count") or 0),
        "returned_row_count": int(contract.get("returned_row_count") or 0),
        "contract_ready": contract_ready,
        "safe_parameter_binding": policy.get("safe_parameter_binding") is True,
        "typed_projection_enabled": policy.get("typed_projection_enabled") is True,
        "cursor_pagination_enabled": policy.get("cursor_pagination_enabled") is True,
        "frontend_executes_query": policy.get("frontend_executes_query") is True,
        "cache_get_writes_files": policy.get("cache_get_writes_files") is True,
        "writes_parquet_on_get": policy.get("writes_parquet_on_get") is True,
        "cache_only": packet.get("cache_only") is True,
        "external_calls_triggered": packet.get("external_calls_triggered") is True,
        "tushare_called": packet.get("tushare_called") is True,
        "deepseek_called": packet.get("deepseek_called") is True,
        "github_called": packet.get("github_called") is True,
        "does_not_execute_trades": packet.get("does_not_execute_trades") is True,
        "does_not_modify_strategy_action": packet.get("does_not_modify_strategy_action") is True,
    }


def storage_duckdb_read_validation_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload_safe = payload_safe or {}
    limit = 1
    rows = [
        _duckdb_read_validation_row(dataset, parquet_dataset_status(dataset, limit=limit))
        for dataset in CANONICAL_PARQUET_DATASETS
    ]
    contract_ready_count = sum(1 for row in rows if row["contract_ready"])
    ready_dataset_count = sum(1 for row in rows if row["status"] == "ready")
    dependency = duckdb_store.dependency_status()
    local_ready = bool(
        dependency.get("available")
        and contract_ready_count == len(CANONICAL_PARQUET_DATASETS)
        and all(row["frontend_executes_query"] is False for row in rows)
        and all(row["cache_get_writes_files"] is False for row in rows)
        and all(row["writes_parquet_on_get"] is False for row in rows)
        and all(row["external_calls_triggered"] is False for row in rows)
        and all(row["tushare_called"] is False for row in rows)
        and all(row["deepseek_called"] is False for row in rows)
        and all(row["github_called"] is False for row in rows)
        and all(row["does_not_execute_trades"] is True for row in rows)
        and all(row["does_not_modify_strategy_action"] is True for row in rows)
    )
    status = (
        "storage_duckdb_read_validation_ready_local_query_contract"
        if local_ready
        else "storage_duckdb_read_validation_blocked_local_query_contract"
    )
    return {
        "schema_version": "command_center_3_storage_duckdb_read_validation.v1",
        "packet_key": DUCKDB_READ_VALIDATION_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": status,
        "mode": "button_gated_local_duckdb_read_validation",
        "scope": "local_storage_duckdb_read_validation_no_write_no_provider",
        "ltg": "LTG-05",
        "local_duckdb_read_validation_ready": local_ready,
        "duckdb_dependency_available": dependency.get("available") is True,
        "dataset_count": len(rows),
        "contract_ready_count": contract_ready_count,
        "ready_dataset_count": ready_dataset_count,
        "limit": limit,
        "rows": rows,
        "query_result_contract_schema_version": "duckdb_query_result_contract.v1",
        "query_wrapper": "duckdb_filtered_parquet.v1",
        "safe_parameter_binding": True,
        "typed_projection_enabled": True,
        "cursor_pagination_enabled": True,
        "frontend_executes_query": False,
        "cache_get_writes_files": False,
        "writes_parquet_on_get": False,
        "writes_parquet": False,
        "writes_manifest": False,
        "deletes_artifacts": False,
        "refreshes_providers": False,
        "reads_env_files": False,
        "reads_row_payloads_for_metrics": False,
        "schema_migration_executed": False,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "artifact_cleanup_delete_executed": False,
        "post_migration_validation_done": False,
        "production_storage_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "request_params_safe": {
            "source": payload_safe.get("source") or "storage_page_button",
            "limit": limit,
            "external_sources_allowed": False,
            "write_parquet_allowed": False,
            "write_manifest_allowed": False,
            "delete_allowed": False,
        },
        "call_ledger": _storage_cache_call_ledger(
            "local_storage_duckdb_read_validation",
            endpoint="POST /api/storage/duckdb-read/validate",
            status=status,
            row_count=len(rows),
        ),
        "warnings": [
            "DuckDB read validation 只验证本地 Parquet 查询合同；不会写 Parquet、写 manifest、删除文件或刷新 provider。",
            "该 receipt 是 LTG-05 read-path direct evidence，不代表 schema migration、partition、compaction 或 production storage 完成。",
        ],
    }


def storage_duckdb_read_validation_evidence() -> dict[str, Any]:
    packet, read_status = _read_storage_meta_packet_no_init(DUCKDB_READ_VALIDATION_PACKET_KEY)
    if read_status != "packet_present" or not isinstance(packet, Mapping):
        return {
            "schema_version": "command_center_3_storage_duckdb_read_validation.v1",
            "packet_key": DUCKDB_READ_VALIDATION_PACKET_KEY,
            "status": "storage_duckdb_read_validation_missing",
            "local_duckdb_read_validation_ready": False,
            "dataset_count": 0,
            "contract_ready_count": 0,
            "ready_dataset_count": 0,
            "production_storage_complete": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    evidence = dict(packet)
    evidence["read_status"] = read_status
    evidence.setdefault("local_duckdb_read_validation_ready", False)
    evidence.setdefault("production_storage_complete", False)
    evidence.setdefault("external_calls_triggered", False)
    evidence.setdefault("tushare_called", False)
    evidence.setdefault("deepseek_called", False)
    evidence.setdefault("github_called", False)
    evidence.setdefault("does_not_execute_trades", True)
    evidence.setdefault("does_not_modify_strategy_action", True)
    evidence.setdefault("contains_secret", False)
    return evidence


def run_storage_duckdb_read_validation_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    task_payload = {
        "source": payload_map.get("source") or "storage_page_button",
        "external_sources_allowed": False,
        "write_parquet_allowed": False,
        "write_manifest_allowed": False,
        "delete_allowed": False,
    }
    task = task_service.create_task_record(
        "run_storage_duckdb_read_validation",
        output_packet_key=DUCKDB_READ_VALIDATION_PACKET_KEY,
        payload=task_payload,
        current_step="storage_duckdb_read_validation_queued",
        warnings=[
            "storage DuckDB read validation 只执行本地只读查询合同检查；不会写 Parquet、写 manifest、删除文件或调用外部源。",
            "该任务不修改 strategy action、不执行真实交易，不代表 production storage 完成。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="running_storage_duckdb_read_validation",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = storage_duckdb_read_validation_packet(task_id=task["task_id"], payload_safe=payload_safe)
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(DUCKDB_READ_VALIDATION_PACKET_KEY, packet)
    except Exception:
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="storage_duckdb_read_validation_packet_persist_failed",
            error_message_safe="storage_duckdb_read_validation_sqlite_write_failed",
            call_ledger=packet["call_ledger"],
            warning="storage_duckdb_read_validation_failed_no_external_call",
        ) or task
    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=str(packet.get("status") or "storage_duckdb_read_validation_recorded"),
        call_ledger=packet["call_ledger"],
        warning="storage_duckdb_read_validation_recorded_no_write_no_external_call",
    ) or task


def factor_values_status(
    *,
    limit: int = 100,
    cursor: str | int | None = None,
    ts_code: str | None = None,
    trade_date: str | int | None = None,
    start_date: str | int | None = None,
    end_date: str | int | None = None,
) -> dict[str, Any]:
    packet = parquet_dataset_status(
        "factor_values",
        limit=limit,
        cursor=cursor,
        ts_code=ts_code,
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
    )
    packet["schema_version"] = "command_center_3_storage_factor_values.v1"
    return _attach_storage_lineage(
        packet,
        api="local_storage_factor_values_cache",
        endpoint="GET /api/storage/factor-values",
        dataset="factor_values",
        row_count=packet.get("row_count"),
        path=(packet.get("metadata") or {}).get("path") if isinstance(packet.get("metadata"), Mapping) else packet.get("path"),
    )


def sqlite_meta_status(*, limit: int = 50) -> dict[str, Any]:
    path = SQLITE_META_PATH
    packet_safe_columns = ["packet_key", "updated_at", "schema_version", "status", "mode", "payload_bytes"]
    task_safe_columns = [
        "task_id",
        "updated_at",
        "task_type",
        "status",
        "progress",
        "current_step",
        "output_packet_key",
        "backend",
        "storage_source",
        "payload_bytes",
    ]
    base = {
        "schema_version": "command_center_3_storage_sqlite_meta.v1",
        "store": "sqlite_meta",
        "path": _path_label(path),
        "metadata_safe_columns": {
            "packet_metadata": packet_safe_columns,
            "task_metadata": task_safe_columns,
        },
        "metadata_source_rows": [],
        "metadata_is_payload_only": False,
        "does_not_return_payload_json": True,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }
    if not path.exists():
        return _attach_storage_lineage(
            {
                **base,
                "status": "missing",
                "packet_count": 0,
                "task_count": 0,
                "packet_metadata": [],
                "task_metadata": [],
            },
            api="local_storage_sqlite_meta_cache",
            endpoint="GET /api/storage/sqlite-meta",
            row_count=0,
            path=base["path"],
        )
    try:
        store = SQLiteMetaStore(path)
        packet_metadata = store.list_packet_metadata()
        task_metadata = [{**item, "storage_source": "sqlite_meta"} for item in store.list_task_metadata()]
    except Exception as exc:
        return _attach_storage_lineage(
            {
                **base,
                "status": "read_failed",
                "packet_count": 0,
                "task_count": 0,
                "packet_metadata": [],
                "task_metadata": [],
                "error_message_safe": _safe_error_message(exc),
            },
            api="local_storage_sqlite_meta_cache",
            endpoint="GET /api/storage/sqlite-meta",
            row_count=0,
            path=base["path"],
        )
    return _attach_storage_lineage(
        {
            **base,
            "status": "ready",
            "packet_count": len(packet_metadata),
            "task_count": len(task_metadata),
            "packet_metadata": packet_metadata[:limit],
            "task_metadata": task_metadata[:limit],
            "packet_status_counts": _count_values(item.get("status") for item in packet_metadata),
            "task_status_counts": _count_values(item.get("status") for item in task_metadata),
            "metadata_source_rows": [
                {
                    "source": "packet_metadata",
                    "row_count": len(packet_metadata),
                    "storage_source": "sqlite_meta",
                    "payload_json_returned": False,
                    "safe_columns": packet_safe_columns,
                },
                {
                    "source": "task_metadata",
                    "row_count": len(task_metadata),
                    "storage_source": "sqlite_meta",
                    "payload_json_returned": False,
                    "safe_columns": task_safe_columns,
                },
            ],
        },
        api="local_storage_sqlite_meta_cache",
        endpoint="GET /api/storage/sqlite-meta",
        row_count=len(packet_metadata) + len(task_metadata),
        path=base["path"],
    )


def storage_overview(*, limit: int = 20) -> dict[str, Any]:
    datasets = [parquet_dataset_status(name, limit=limit) for name in CANONICAL_PARQUET_DATASETS]
    sqlite_meta = sqlite_meta_status(limit=limit)
    implementation_status = dataset_implementation_status()
    artifact_hygiene = storage_artifact_hygiene_status()
    production_readiness = storage_production_readiness(sqlite_meta)
    production_blocker_audit = storage_production_blocker_audit(production_readiness)
    production_readiness_receipt = storage_production_readiness_receipt(
        production_readiness,
        production_blocker_audit,
    )
    physical_migration_activation_receipt = storage_physical_migration_activation_receipt(
        production_readiness,
        production_blocker_audit,
        production_readiness_receipt,
    )
    physical_execution_recipe = storage_physical_execution_recipe(
        production_readiness,
        production_blocker_audit,
        physical_migration_activation_receipt,
    )
    physical_execution_request = storage_physical_execution_request_evidence()
    physical_durable_evidence_recipe = storage_physical_durable_evidence_recipe(
        production_readiness,
        production_blocker_audit,
        physical_migration_activation_receipt,
        physical_execution_recipe,
        physical_execution_request,
    )
    physical_execution_phase_a = storage_physical_execution_phase_a_evidence()
    current_result_atomic_promotion = storage_current_result_atomic_promotion_evidence()
    production_promotion_review = storage_production_promotion_review_evidence()
    dataset_version_policy = storage_dataset_version_policy()
    dataset_version_manifest_evidence = storage_dataset_version_manifest_evidence_audit()
    backtest_results_schema_seed_evidence = storage_backtest_results_schema_seed_evidence()
    schema_validation_acceptance_evidence = production_readiness.get("schema_validation_acceptance_evidence") or {}
    schema_migration_preflight = storage_schema_migration_preflight()
    schema_migration_execution_evidence = production_readiness.get("schema_migration_execution_evidence") or {}
    duckdb_query_service = duckdb_query_service_policy()
    packet = {
        "schema_version": "command_center_3_storage_overview.v1",
        "store": "parquet_duckdb",
        "status": "cache_ready",
        "metadata_store": "sqlite_meta",
        "datasets": datasets,
        "dataset_catalog": dataset_catalog(),
        "dataset_implementation_status": implementation_status,
        "supported_datasets": list(CANONICAL_PARQUET_DATASETS),
        "supported_aliases": sorted(key for key, value in SUPPORTED_PARQUET_DATASETS.items() if key != value),
        "dataset_count": len(CANONICAL_PARQUET_DATASETS),
        "dataset_status": {item["dataset"]: item["metadata"]["status"] for item in datasets},
        "dataset_ttl_status": {item["dataset"]: item["cache_ttl"]["ttl_state"] for item in datasets},
        "dataset_ttl_state_counts": _count_values(item["cache_ttl"]["ttl_state"] for item in datasets),
        "dataset_schema_contract_status": {item["dataset"]: item["schema_contract"]["status"] for item in datasets},
        "dataset_version_policy": dataset_version_policy,
        "dataset_version_rows": dataset_version_policy["rows"],
        "dataset_version_status": {item["dataset"]: item["dataset_version_policy"]["version_status"] for item in datasets},
        "dataset_version_status_counts": dataset_version_policy["status_counts"],
        "dataset_version_declared_count": dataset_version_policy["target_version_declared_count"],
        "physical_dataset_version_validated_count": dataset_version_policy["physical_dataset_version_validated_count"],
        "dataset_version_migration_executed_count": dataset_version_policy["dataset_version_migration_executed_count"],
        "dataset_version_manifest_evidence_audit": dataset_version_manifest_evidence,
        "dataset_version_manifest_evidence_rows": dataset_version_manifest_evidence["rows"],
        "dataset_version_manifest_evidence_status_counts": dataset_version_manifest_evidence["status_counts"],
        "dataset_version_manifest_evidence_status": dataset_version_manifest_evidence["status"],
        "dataset_version_manifest_evidence_validated_count": dataset_version_manifest_evidence["validated_dataset_count"],
        "dataset_version_manifest_evidence_validated": dataset_version_manifest_evidence["dataset_version_manifest_validated"],
        "backtest_results_schema_seed_evidence": backtest_results_schema_seed_evidence,
        "backtest_results_schema_seed_status": backtest_results_schema_seed_evidence.get("status"),
        "backtest_results_schema_seed_ready": backtest_results_schema_seed_evidence.get(
            "schema_seed_ready_for_schema_acceptance"
        ),
        "dataset_partition_plan_status": {item["dataset"]: item["partition_plan"]["status"] for item in datasets},
        "dataset_compaction_status": {item["dataset"]: item["compaction_plan"]["status"] for item in datasets},
        "manual_compaction_recommended_count": sum(1 for item in datasets if item["compaction_plan"]["manual_compaction_recommended"]),
        "dataset_implementation_state_counts": implementation_status["state_counts"],
        "dataset_parquet_status_counts": implementation_status["parquet_status_counts"],
        "schema_migration_preflight": schema_migration_preflight,
        "schema_migration_rows": schema_migration_preflight["rows"],
        "schema_migration_status_counts": schema_migration_preflight["status_counts"],
        "schema_migration_preflight_status": schema_migration_preflight["status"],
        "schema_migration_executed_count": schema_migration_preflight["migration_executed_count"],
        "schema_migration_execution_evidence": schema_migration_execution_evidence,
        "schema_migration_execution_status": schema_migration_execution_evidence.get("status"),
        "schema_migration_task_executed": schema_migration_execution_evidence.get("schema_migration_executed"),
        "schema_migration_rewrite_executed": schema_migration_execution_evidence.get(
            "schema_migration_rewrite_executed"
        ),
        "schema_migration_preflight_physical_validation_done_count": schema_migration_preflight[
            "physical_validation_done_count"
        ],
        "schema_validation_acceptance_evidence": schema_validation_acceptance_evidence,
        "schema_validation_acceptance_evidence_rows": schema_validation_acceptance_evidence.get("rows") or [],
        "schema_validation_acceptance_evidence_status": schema_validation_acceptance_evidence.get("status"),
        "schema_validation_acceptance_accepted_dataset_count": schema_validation_acceptance_evidence.get(
            "accepted_dataset_count"
        ),
        "schema_validation_acceptance_blocked_dataset_count": schema_validation_acceptance_evidence.get(
            "blocked_dataset_count"
        ),
        "physical_schema_validation_done": production_readiness.get("physical_schema_validation_done"),
        "physical_schema_validation_done_count": production_readiness.get("physical_schema_validation_done_count"),
        "duckdb_query_service": duckdb_query_service,
        "duckdb_query_service_rows": duckdb_query_service["rows"],
        "duckdb_query_service_status": duckdb_query_service["status"],
        "duckdb_query_wrapper": duckdb_query_service["query_wrapper"],
        "duckdb_query_max_limit": duckdb_query_service["max_limit"],
        "production_readiness": production_readiness,
        "storage_production_blocker_audit": production_blocker_audit,
        "storage_production_blocker_rows": production_blocker_audit["rows"],
        "storage_production_blocker_count": production_blocker_audit["blocking_criterion_count"],
        "storage_production_readiness_receipt": production_readiness_receipt,
        "storage_production_readiness_receipt_rows": production_readiness_receipt["rows"],
        "storage_production_readiness_receipt_status": production_readiness_receipt["status"],
        "storage_production_readiness_receipt_ready": production_readiness_receipt["local_receipt_ready"],
        "storage_physical_migration_activation_receipt": physical_migration_activation_receipt,
        "storage_physical_migration_activation_rows": physical_migration_activation_receipt["rows"],
        "storage_physical_migration_activation_status": physical_migration_activation_receipt["status"],
        "storage_physical_migration_activation_ready": physical_migration_activation_receipt[
            "local_activation_receipt_ready"
        ],
        "storage_physical_execution_recipe": physical_execution_recipe,
        "storage_physical_execution_recipe_rows": physical_execution_recipe["rows"],
        "storage_physical_execution_recipe_status": physical_execution_recipe["status"],
        "storage_physical_execution_recipe_ready": physical_execution_recipe["local_recipe_ready"],
        "storage_physical_execution_pending_phase_count": physical_execution_recipe["pending_phase_count"],
        "storage_physical_execution_request": physical_execution_request,
        "storage_physical_execution_request_rows": physical_execution_request.get("rows") or [],
        "storage_physical_execution_request_status": physical_execution_request.get("status"),
        "storage_physical_execution_request_ready": physical_execution_request.get("local_execution_request_ready"),
        "storage_physical_durable_evidence_recipe": physical_durable_evidence_recipe,
        "storage_physical_durable_evidence_rows": physical_durable_evidence_recipe["rows"],
        "storage_physical_durable_evidence_recipe_status": physical_durable_evidence_recipe["status"],
        "storage_physical_durable_evidence_recipe_ready": physical_durable_evidence_recipe["local_recipe_ready"],
        "storage_physical_durable_evidence_production_blocker_count": physical_durable_evidence_recipe[
            "production_blocker_count"
        ],
        "storage_physical_execution_phase_a": physical_execution_phase_a,
        "storage_physical_execution_phase_a_rows": physical_execution_phase_a.get("rows") or [],
        "storage_physical_execution_phase_a_status": physical_execution_phase_a.get("status"),
        "storage_physical_execution_phase_a_ready": physical_execution_phase_a.get(
            "local_phase_a_execution_ready"
        ),
        "storage_current_result_atomic_promotion": current_result_atomic_promotion,
        "storage_current_result_atomic_promotion_status": current_result_atomic_promotion.get("status"),
        "storage_current_result_atomic_promotion_can_launch": current_result_atomic_promotion.get(
            "can_launch_atomic_promotion"
        ),
        "storage_current_result_atomic_promotion_current": current_result_atomic_promotion.get(
            "atomic_promotion_current"
        ),
        "storage_production_promotion_review": production_promotion_review,
        "storage_production_promotion_review_rows": production_promotion_review.get("rows") or [],
        "storage_production_promotion_review_status": production_promotion_review.get("status"),
        "storage_production_promotion_review_ready": production_promotion_review.get(
            "local_promotion_review_ready"
        ),
        "artifact_hygiene": artifact_hygiene,
        "artifact_cleanup_review_contract": artifact_hygiene["artifact_cleanup_review_contract"],
        "artifact_cleanup_review_rows": artifact_hygiene["artifact_cleanup_review_rows"],
        "artifact_cleanup_review_status": artifact_hygiene["artifact_cleanup_review_status"],
        "artifact_cleanup_review_required_step_count": artifact_hygiene["artifact_cleanup_review_required_step_count"],
        "artifact_cleanup_delete_executed_count": artifact_hygiene["artifact_cleanup_delete_executed_count"],
        "artifact_hygiene_status": artifact_hygiene["status"],
        "artifact_hygiene_present_count": artifact_hygiene["present_artifact_count"],
        "artifact_hygiene_review_required_count": artifact_hygiene["review_required_count"],
        "sqlite_meta": sqlite_meta,
        "metadata_status": sqlite_meta["status"],
        "packet_metadata_count": sqlite_meta["packet_count"],
        "task_metadata_count": sqlite_meta["task_count"],
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }
    return _attach_storage_lineage(
        packet,
        api="local_storage_overview_cache",
        endpoint="GET /api/storage",
        row_count=sum(int(item.get("row_count") or 0) for item in datasets),
    )


SENSITIVE_VALUE_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer ",
    "deepseek",
    "github_token",
    "password",
    "secret",
    "token",
    "tushare",
)
ERROR_STACK_MARKERS = ("traceback", 'file "', "line ", "exception")


def _looks_sensitive_or_stack(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in SENSITIVE_VALUE_MARKERS) or any(marker in lowered for marker in ERROR_STACK_MARKERS)


def _safe_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        text = value.strip()
        if _looks_sensitive_or_stack(text):
            return None
        return text[:500]
    return None


def _safe_error_message(exc: Exception) -> str:
    message = str(exc).splitlines()[0][:240]
    if not message or _looks_sensitive_or_stack(message):
        return "local parquet factor_values write failed"
    return message


def _schema_validation_for_rows(dataset: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    contract = _schema_contract(dataset)
    required_columns = [str(item) for item in contract.get("required_columns") or []]
    available_columns = sorted({str(key) for row in rows if isinstance(row, Mapping) for key in row.keys()})
    missing_columns = [column for column in required_columns if column not in available_columns]
    status = "valid" if not missing_columns else "missing_required_columns"
    return {
        "dataset": dataset,
        "schema_version": contract.get("schema_version"),
        "status": status,
        "required_columns": required_columns,
        "available_columns": available_columns,
        "missing_required_columns": missing_columns,
        "row_count": len(rows),
        "blocks_write": bool(missing_columns),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def _factor_value_rows_from_hub(hub_packet: Any) -> list[dict[str, Any]]:
    hub = hub_packet if isinstance(hub_packet, Mapping) else {}
    runtime = hub.get("runtime") if isinstance(hub.get("runtime"), Mapping) else {}
    universe = hub.get("universe") if isinstance(hub.get("universe"), Mapping) else {}
    items = universe.get("items") if isinstance(universe.get("items"), list) else []
    ts_code = str(items[0]) if items else "current_target"
    calculated_at = runtime.get("calculated_at") or hub.get("updated_at")
    trade_date = runtime.get("trade_date") or hub.get("trade_date") or hub.get("data_date")
    packet_key = hub.get("packet_key") or "command_center_factor_quant_hub_packet"
    source = hub.get("cache_source") or hub.get("mode") or "factor_quant_hub"
    rows = []
    for item in runtime.get("factor_values") or []:
        if not isinstance(item, Mapping):
            continue
        data_status = item.get("data_status") or item.get("status")
        item_ts_code = item.get("ts_code") or item.get("symbol") or item.get("ticker") or ts_code
        rows.append(
            {
                "ts_code": _safe_scalar(item_ts_code),
                "trade_date": _safe_scalar(item.get("trade_date") or trade_date),
                "factor_key": _safe_scalar(item.get("factor_key")),
                "factor_name": _safe_scalar(item.get("factor_name")),
                "category": _safe_scalar(item.get("category")),
                "raw_value": _safe_scalar(item.get("raw_value")),
                "zscore": _safe_scalar(item.get("zscore")),
                "rank_pct": _safe_scalar(item.get("rank_pct")),
                "direction": _safe_scalar(item.get("direction")),
                "status": _safe_scalar(item.get("status")),
                "data_status": _safe_scalar(data_status),
                "status_note": _safe_scalar(item.get("status_note")),
                "pit_validated": bool(item.get("pit_validated")),
                "excluded_from_score": bool(item.get("excluded_from_score")),
                "calculated_at": _safe_scalar(calculated_at),
                "packet_key": _safe_scalar(packet_key),
                "source_packet": _safe_scalar(item.get("source_packet") or "runtime.factor_values"),
                "source": _safe_scalar(item.get("source") or source),
                "source_mode": _safe_scalar(hub.get("mode")),
            }
        )
    return rows


def persist_factor_values_from_hub(hub_packet: Any) -> dict[str, Any]:
    rows = _factor_value_rows_from_hub(hub_packet)
    schema_validation = _schema_validation_for_rows("factor_values", rows)
    if not rows:
        return {
            "status": "empty",
            "dataset": "factor_values",
            "schema_version": schema_validation.get("schema_version"),
            "schema_validation": schema_validation,
            "schema_validation_status": schema_validation.get("status"),
            "row_count": 0,
            "path": _path_label(parquet_store.dataset_path(root=PARQUET_ROOT, name="factor_values")),
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_modify_strategy_action": True,
            "does_not_execute_trades": True,
        }
    if schema_validation.get("blocks_write"):
        return {
            "status": "schema_invalid",
            "dataset": "factor_values",
            "schema_version": schema_validation.get("schema_version"),
            "schema_validation": schema_validation,
            "schema_validation_status": schema_validation.get("status"),
            "row_count": 0,
            "path": _path_label(parquet_store.dataset_path(root=PARQUET_ROOT, name="factor_values")),
            "error_message_safe": "factor_values schema missing required columns",
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_modify_strategy_action": True,
            "does_not_execute_trades": True,
        }
    dependency = parquet_store.dependency_status()
    if not dependency.get("available"):
        return {
            "status": "dependency_missing",
            "dataset": "factor_values",
            "schema_version": schema_validation.get("schema_version"),
            "schema_validation": schema_validation,
            "schema_validation_status": schema_validation.get("status"),
            "row_count": 0,
            "path": _path_label(parquet_store.dataset_path(root=PARQUET_ROOT, name="factor_values")),
            "dependency": dependency,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_modify_strategy_action": True,
            "does_not_execute_trades": True,
        }
    try:
        import pandas as pd

        result = parquet_store.write_dataset(pd.DataFrame(rows), root=PARQUET_ROOT, name="factor_values")
    except Exception as exc:
        result = {
            "status": "failed",
            "path": str(parquet_store.dataset_path(root=PARQUET_ROOT, name="factor_values")),
            "row_count": 0,
            "error_message_safe": _safe_error_message(exc),
        }
    result.update(
        {
            "dataset": "factor_values",
            "schema_version": schema_validation.get("schema_version"),
            "schema_validation": schema_validation,
            "schema_validation_status": schema_validation.get("status"),
            "path": _path_label(Path(result.get("path") or parquet_store.dataset_path(root=PARQUET_ROOT, name="factor_values"))),
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_modify_strategy_action": True,
            "does_not_execute_trades": True,
        }
    )
    return result
