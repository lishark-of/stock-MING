from __future__ import annotations

from pathlib import Path
from typing import Any

from storage import duckdb_store, parquet_store

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARQUET_ROOT = PROJECT_ROOT / ".stock_ming_3" / "parquet"
SUPPORTED_PARQUET_DATASETS = {
    "factor_values": "factor_values",
    "factor-values": "factor_values",
    "daily": "daily",
    "moneyflow": "moneyflow",
}


def _path_label(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _canonical_dataset(dataset: str) -> str:
    key = str(dataset or "").strip().lower().replace(" ", "_")
    if key not in SUPPORTED_PARQUET_DATASETS:
        return ""
    return SUPPORTED_PARQUET_DATASETS[key]


def parquet_dataset_status(dataset: str, *, limit: int = 100) -> dict[str, Any]:
    selected = _canonical_dataset(dataset)
    if not selected:
        return {
            "schema_version": "command_center_3_storage_dataset.v1",
            "status": "unsupported_dataset",
            "dataset": str(dataset or ""),
            "supported_datasets": ["factor_values", "daily", "moneyflow"],
            "cache_only": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_modify_strategy_action": True,
            "does_not_execute_trades": True,
        }
    path = parquet_store.dataset_path(root=PARQUET_ROOT, name=selected)
    metadata = parquet_store.dataset_metadata(root=PARQUET_ROOT, name=selected)
    query = duckdb_store.query_parquet_dataset(path, limit=limit)
    metadata["path"] = _path_label(path)
    query["path"] = _path_label(path)
    return {
        "schema_version": "command_center_3_storage_dataset.v1",
        "store": "parquet_duckdb",
        "dataset": selected,
        "metadata": metadata,
        "query": query,
        "row_count": int(query.get("row_count") or 0),
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }


def factor_values_status(*, limit: int = 100) -> dict[str, Any]:
    packet = parquet_dataset_status("factor_values", limit=limit)
    packet["schema_version"] = "command_center_3_storage_factor_values.v1"
    return packet


def storage_overview(*, limit: int = 20) -> dict[str, Any]:
    datasets = [parquet_dataset_status(name, limit=limit) for name in ("factor_values", "daily", "moneyflow")]
    return {
        "schema_version": "command_center_3_storage_overview.v1",
        "store": "parquet_duckdb",
        "datasets": datasets,
        "dataset_status": {item["dataset"]: item["metadata"]["status"] for item in datasets},
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
    }
