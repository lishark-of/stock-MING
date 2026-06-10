from __future__ import annotations

from pathlib import Path
from typing import Any


def dependency_status() -> dict[str, Any]:
    try:
        import duckdb  # noqa: F401
    except Exception as exc:
        return {"available": False, "error_message_safe": str(exc)}
    return {"available": True, "error_message_safe": ""}


def query_parquet_dataset(parquet_path: str | Path, *, limit: int = 1000) -> dict[str, Any]:
    status = dependency_status()
    if not status["available"]:
        return {"status": "dependency_missing", "rows": [], **status}
    path = Path(parquet_path)
    if not path.exists():
        return {
            "status": "missing",
            "rows": [],
            "row_count": 0,
            "path": str(path),
            "error_message_safe": "",
            "external_calls_triggered": False,
        }
    import duckdb

    safe_limit = max(1, min(int(limit or 1000), 10000))
    path_text = str(path).replace("'", "''")
    sql = f"SELECT * FROM read_parquet('{path_text}') LIMIT {safe_limit}"
    rows = duckdb.sql(sql).df().to_dict("records")
    return {"status": "ready", "rows": rows, "row_count": len(rows), "path": str(path), "external_calls_triggered": False}


def query_factor_values(parquet_path: str | Path, *, limit: int = 1000) -> dict[str, Any]:
    return query_parquet_dataset(parquet_path, limit=limit)
