from __future__ import annotations

from pathlib import Path
from typing import Any

from storage import duckdb_store, parquet_store

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARQUET_ROOT = PROJECT_ROOT / ".stock_ming_3" / "parquet"


def _path_label(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def factor_values_status(*, limit: int = 100) -> dict[str, Any]:
    path = parquet_store.factor_values_path(root=PARQUET_ROOT)
    metadata = parquet_store.factor_values_metadata(root=PARQUET_ROOT)
    query = duckdb_store.query_factor_values(path, limit=limit)
    metadata["path"] = _path_label(path)
    query["path"] = _path_label(path)
    return {
        "schema_version": "command_center_3_storage_factor_values.v1",
        "store": "parquet_duckdb",
        "dataset": "factor_values",
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
