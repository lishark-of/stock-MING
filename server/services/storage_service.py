from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Mapping

from storage import duckdb_store, parquet_store
from storage.sqlite_meta import SQLiteMetaStore

from . import task_service

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARQUET_ROOT = PROJECT_ROOT / ".stock_ming_3" / "parquet"
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
ARTIFACT_CLEANUP_DRY_RUN_PACKET_KEY = "command_center_3_storage_artifact_cleanup_dry_run_packet"
SCHEMA_VALIDATION_DRY_RUN_PACKET_KEY = "command_center_3_storage_schema_validation_dry_run_packet"
PARTITION_MIGRATION_DRY_RUN_PACKET_KEY = "command_center_3_storage_partition_migration_dry_run_packet"
COMPACTION_DRY_RUN_PACKET_KEY = "command_center_3_storage_compaction_dry_run_packet"
CACHE_TTL_DRY_RUN_PACKET_KEY = "command_center_3_storage_cache_ttl_dry_run_packet"
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
    rows = [_schema_migration_row(dataset) for dataset in CANONICAL_PARQUET_DATASETS]
    return {
        "schema_version": "command_center_3_storage_schema_migration_preflight.v1",
        "status": "preflight_ready"
        if all(row.get("migration_status") == "contract_ready_physical_validation_pending" for row in rows)
        else "contract_gap",
        "scope": "schema_version_migration_contract",
        "mode": "metadata_only_read_only_preflight",
        "dataset_count": len(rows),
        "contract_ready_count": sum(1 for row in rows if row.get("migration_status") == "contract_ready_physical_validation_pending"),
        "physical_validation_done_count": sum(1 for row in rows if row.get("physical_validation_done")),
        "migration_executed_count": sum(1 for row in rows if row.get("schema_migration_executed")),
        "schema_migration_ready_count": sum(1 for row in rows if row.get("schema_migration_ready_for_execution")),
        "manual_migration_task_required": True,
        "schema_migration_task_executed": False,
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
        "note": "Schema migration preflight is contract-only; physical validation and migration remain explicit future tasks.",
    }


def _dataset_version_manifest_path() -> Path:
    return PARQUET_ROOT / DATASET_VERSION_MANIFEST_NAME


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
        "would_write_partitioned_dataset": False,
        "post_dry_run_writes_parquet": False,
        "post_dry_run_reads_row_payloads": False,
        "cache_get_writes_files": False,
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
    packet = {
        "schema_version": "command_center_3_storage_partition_migration_dry_run.v1",
        "packet_key": PARTITION_MIGRATION_DRY_RUN_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": "dry_run_completed",
        "mode": "dry_run",
        "scope": "partition_migration_plan_before_write",
        "dataset_count": len(rows),
        "partition_migration_ready_count": ready_count,
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
        "compaction_executed": False,
        "physical_compaction_executed": False,
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
    }


def storage_compaction_dry_run_packet(
    *,
    task_id: str | None = None,
    payload_safe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [_compaction_dry_run_row(dataset) for dataset in CANONICAL_PARQUET_DATASETS]
    status_counts = _count_values(row.get("compaction_dry_run_status") for row in rows)
    ready_count = sum(1 for row in rows if row.get("compaction_ready"))
    packet = {
        "schema_version": "command_center_3_storage_compaction_dry_run.v1",
        "packet_key": COMPACTION_DRY_RUN_PACKET_KEY,
        "task_id": str(task_id or ""),
        "status": "dry_run_completed",
        "mode": "dry_run",
        "scope": "parquet_compaction_plan_before_rewrite",
        "dataset_count": len(rows),
        "compaction_ready_count": ready_count,
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
        "manual_compaction_task_required": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
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
            "next_action": "add an explicit manifest writer/validator task after physical schema validation is stable.",
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


def storage_artifact_hygiene_status() -> dict[str, Any]:
    rows = [_artifact_hygiene_row(target) for target in LOCAL_ARTIFACT_HYGIENE_TARGETS]
    review_required = [row for row in rows if row.get("status") == "review_required_type_mismatch"]
    present_rows = [row for row in rows if row.get("exists")]
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
    duckdb_dependency = duckdb_store.dependency_status()
    sqlite_status = str((sqlite_meta or {}).get("status") or ("ready" if SQLITE_META_PATH.exists() else "missing"))
    artifact_hygiene = storage_artifact_hygiene_status()
    schema_migration_preflight = storage_schema_migration_preflight()
    dataset_version_policy = storage_dataset_version_policy()
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
            "component": "dataset_version_policy",
            "status": dataset_version_policy["status"],
            "production_role": "dataset version manifest policy before production reads/writes claim physical versioning",
            "current_backend": "read_only_contract_matrix_no_manifest_write",
            "blocking_for_cache_read": False,
            "next_action": "add explicit manifest writer/validator task after schema validation dry-run passes.",
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
            "status": "available" if duckdb_dependency.get("available") else "dependency_missing",
            "production_role": "query Parquet without loading large DataFrames into UI state",
            "current_backend": "duckdb_read_parquet",
            "blocking_for_cache_read": False,
            "next_action": "wrap common factor/date/universe queries before full Factor Test Lab.",
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
            "next_action": "add explicit dry-run cleanup task; keep GET storage read-only.",
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
        "schema_version_policy": "packet metadata and factor_values require explicit schema_version before production migration.",
        "dataset_version_policy": "contract_only_manifest_write_requires_explicit_task",
        "dataset_version_policy_status": dataset_version_policy["status"],
        "dataset_version_policy_dataset_count": dataset_version_policy["dataset_count"],
        "dataset_version_declared_count": dataset_version_policy["target_version_declared_count"],
        "dataset_version_manifest_present_count": dataset_version_policy["version_manifest_present_count"],
        "physical_dataset_version_validated_count": dataset_version_policy["physical_dataset_version_validated_count"],
        "dataset_version_migration_executed_count": dataset_version_policy["dataset_version_migration_executed_count"],
        "dataset_version_manifest_written_on_get": False,
        "schema_contract_policy": "canonical datasets expose local schema contracts; physical validation remains explicit and non-refreshing.",
        "schema_migration_policy": "preflight_only_no_physical_migration_on_get",
        "schema_migration_preflight_status": schema_migration_preflight["status"],
        "schema_migration_dataset_count": schema_migration_preflight["dataset_count"],
        "schema_migration_executed_count": schema_migration_preflight["migration_executed_count"],
        "physical_schema_validation_done_count": schema_migration_preflight["physical_validation_done_count"],
        "schema_validation_dry_run_route": "POST /api/storage/schema-validation/dry-run",
        "schema_validation_dry_run_button_gated": True,
        "schema_validation_dry_run_writes_parquet": False,
        "schema_validation_dry_run_reads_row_payloads": False,
        "partition_migration_dry_run_route": "POST /api/storage/partition-migration/dry-run",
        "partition_migration_dry_run_button_gated": True,
        "partition_migration_dry_run_writes_parquet": False,
        "partition_migration_dry_run_reads_row_payloads": False,
        "cache_ttl_policy": "dry_run_button_gated_no_auto_refresh",
        "cache_ttl_dry_run_route": "POST /api/storage/cache-ttl/dry-run",
        "cache_ttl_dry_run_button_gated": True,
        "cache_ttl_dry_run_writes_parquet": False,
        "cache_ttl_dry_run_reads_row_payloads": False,
        "cache_ttl_refresh_executed_count": 0,
        "compaction_policy": "dry_run_button_gated_no_parquet_rewrite",
        "compaction_dry_run_route": "POST /api/storage/compaction/dry-run",
        "compaction_dry_run_button_gated": True,
        "compaction_dry_run_writes_parquet": False,
        "compaction_dry_run_reads_row_payloads": False,
        "compaction_executed_count": 0,
        "artifact_hygiene_policy": "path_only_manual_cleanup_no_delete_on_get",
        "artifact_hygiene_status": artifact_hygiene["status"],
        "artifact_hygiene_present_count": artifact_hygiene["present_artifact_count"],
        "artifact_cleanup_dry_run_route": "POST /api/storage/artifact-hygiene/dry-run",
        "artifact_cleanup_dry_run_button_gated": True,
        "artifact_cleanup_dry_run_deletes_files": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "Storage production readiness is diagnostic only; it does not create datasets or connect to external services.",
    }


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
    artifact_hygiene = storage_artifact_hygiene_status()
    dataset_version_policy = storage_dataset_version_policy()
    schema_migration_preflight = storage_schema_migration_preflight()
    packet = {
        "schema_version": "command_center_3_storage_dataset_catalog.v1",
        "store": "parquet_duckdb",
        "status": "ready",
        "mode": "cache_only",
        "dataset_catalog": catalog,
        "dataset_implementation_status": implementation_status,
        "production_readiness": production_readiness,
        "artifact_hygiene": artifact_hygiene,
        "dataset_version_policy": dataset_version_policy,
        "dataset_version_rows": dataset_version_policy["rows"],
        "dataset_version_status_counts": dataset_version_policy["status_counts"],
        "schema_migration_preflight": schema_migration_preflight,
        "schema_migration_rows": schema_migration_preflight["rows"],
        "schema_migration_status_counts": schema_migration_preflight["status_counts"],
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
        "query_wrapper": query.get("query_wrapper"),
        "query_filters": query.get("query_filters") or {},
        "applied_filters": query.get("applied_filters") or [],
        "skipped_filters": query.get("skipped_filters") or [],
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


def factor_values_status(
    *,
    limit: int = 100,
    ts_code: str | None = None,
    trade_date: str | int | None = None,
    start_date: str | int | None = None,
    end_date: str | int | None = None,
) -> dict[str, Any]:
    packet = parquet_dataset_status(
        "factor_values",
        limit=limit,
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
    dataset_version_policy = storage_dataset_version_policy()
    schema_migration_preflight = storage_schema_migration_preflight()
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
        "physical_schema_validation_done_count": schema_migration_preflight["physical_validation_done_count"],
        "production_readiness": production_readiness,
        "artifact_hygiene": artifact_hygiene,
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
        rows.append(
            {
                "ts_code": ts_code,
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
