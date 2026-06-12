from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Mapping

from storage import duckdb_store, parquet_store
from storage.sqlite_meta import SQLiteMetaStore

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARQUET_ROOT = PROJECT_ROOT / ".stock_ming_3" / "parquet"
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
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
        partition_plan = _partition_plan(dataset)
        compaction_plan = _compaction_plan(dataset, parquet_store.dataset_path(root=PARQUET_ROOT, name=dataset), metadata)
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
        "local_pipeline_dataset_count": sum(1 for row in rows if row.get("implementation_state") == "local_pipeline_enabled"),
        "future_button_gated_dataset_count": sum(1 for row in rows if row.get("implementation_state") == "future_button_gated"),
        "catalog_only_dataset_count": sum(1 for row in rows if row.get("implementation_state") == "catalog_only"),
        "parquet_ready_dataset_count": sum(1 for row in rows if row.get("parquet_status") == "ready"),
        "parquet_missing_dataset_count": sum(1 for row in rows if row.get("parquet_status") == "missing"),
        "tushare_capable_dataset_count": sum(1 for row in rows if row.get("tushare_capable")),
        "local_compute_capable_dataset_count": sum(1 for row in rows if row.get("local_compute_capable")),
        "schema_contract_ready_count": sum(1 for row in rows if row.get("schema_contract_status") == "contract_ready"),
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
            "status": "local_ready",
            "current_coverage": "Parquet cache endpoints expose audit-only TTL state and stale reason without auto-refreshing GET cache.",
            "next_action": "wire TTL state into task scheduling hints while keeping refresh explicit and button-gated.",
            "external_calls_triggered": False,
        },
        {
            "control": "parquet_compaction",
            "status": "audit_ready",
            "current_coverage": "dataset cache endpoints expose audit-only compaction plans; GET cache never rewrites Parquet files.",
            "next_action": "add explicit manual compaction task after partitioned layout is enabled.",
            "external_calls_triggered": False,
        },
    ]


def storage_production_readiness(sqlite_meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
    parquet_dependency = parquet_store.dependency_status()
    duckdb_dependency = duckdb_store.dependency_status()
    sqlite_status = str((sqlite_meta or {}).get("status") or ("ready" if SQLITE_META_PATH.exists() else "missing"))
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
        "schema_contract_policy": "canonical datasets expose local schema contracts; physical validation remains explicit and non-refreshing.",
        "cache_ttl_policy": "audit_only_no_auto_refresh",
        "compaction_policy": "audit_only_manual_task_required",
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
    packet = {
        "schema_version": "command_center_3_storage_dataset_catalog.v1",
        "store": "parquet_duckdb",
        "status": "ready",
        "mode": "cache_only",
        "dataset_catalog": catalog,
        "dataset_implementation_status": implementation_status,
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
    production_readiness = storage_production_readiness(sqlite_meta)
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
        "dataset_partition_plan_status": {item["dataset"]: item["partition_plan"]["status"] for item in datasets},
        "dataset_compaction_status": {item["dataset"]: item["compaction_plan"]["status"] for item in datasets},
        "manual_compaction_recommended_count": sum(1 for item in datasets if item["compaction_plan"]["manual_compaction_recommended"]),
        "dataset_implementation_state_counts": implementation_status["state_counts"],
        "dataset_parquet_status_counts": implementation_status["parquet_status_counts"],
        "production_readiness": production_readiness,
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
