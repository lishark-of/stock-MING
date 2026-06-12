from __future__ import annotations

from pathlib import Path
from typing import Any


def dependency_status() -> dict[str, Any]:
    try:
        import duckdb  # noqa: F401
    except Exception as exc:
        return {"available": False, "error_message_safe": str(exc)}
    return {"available": True, "error_message_safe": ""}


def _normalize_date(value: str | int | None) -> str:
    text = str(value or "").strip()
    return "".join(ch for ch in text if ch.isdigit())


def _quote_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _date_column(columns: list[str]) -> str:
    for candidate in ("trade_date", "cal_date", "data_date", "ann_date", "end_date"):
        if candidate in columns:
            return candidate
    return ""


def _build_filters(
    columns: list[str],
    *,
    ts_code: str | None = None,
    trade_date: str | int | None = None,
    start_date: str | int | None = None,
    end_date: str | int | None = None,
) -> tuple[list[str], list[Any], list[dict[str, Any]], list[dict[str, Any]]]:
    conditions: list[str] = []
    params: list[Any] = []
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    requested_ts_code = str(ts_code or "").strip()
    if requested_ts_code:
        if "ts_code" in columns:
            conditions.append(f"CAST({_quote_identifier('ts_code')} AS VARCHAR) = ?")
            params.append(requested_ts_code)
            applied.append({"filter": "ts_code", "column": "ts_code", "value": requested_ts_code})
        else:
            skipped.append({"filter": "ts_code", "reason": "column_missing", "value": requested_ts_code})

    date_column = _date_column(columns)
    date_filters = [
        ("trade_date", "=", _normalize_date(trade_date)),
        ("start_date", ">=", _normalize_date(start_date)),
        ("end_date", "<=", _normalize_date(end_date)),
    ]
    for filter_name, operator, value in date_filters:
        if not value:
            continue
        if date_column:
            conditions.append(f"CAST({_quote_identifier(date_column)} AS VARCHAR) {operator} ?")
            params.append(value)
            applied.append({"filter": filter_name, "column": date_column, "operator": operator, "value": value})
        else:
            skipped.append({"filter": filter_name, "reason": "date_column_missing", "value": value})

    return conditions, params, applied, skipped


def query_parquet_dataset(
    parquet_path: str | Path,
    *,
    limit: int = 1000,
    ts_code: str | None = None,
    trade_date: str | int | None = None,
    start_date: str | int | None = None,
    end_date: str | int | None = None,
) -> dict[str, Any]:
    status = dependency_status()
    query_filters = {
        "ts_code": str(ts_code or "").strip() or None,
        "trade_date": _normalize_date(trade_date) or None,
        "start_date": _normalize_date(start_date) or None,
        "end_date": _normalize_date(end_date) or None,
    }
    if not status["available"]:
        return {
            "status": "dependency_missing",
            "rows": [],
            "row_count": 0,
            "path": str(parquet_path),
            "external_calls_triggered": False,
            "query_filters": query_filters,
            "applied_filters": [],
            "skipped_filters": [],
            "query_wrapper": "duckdb_filtered_parquet.v1",
            **status,
        }
    path = Path(parquet_path)
    if not path.exists():
        return {
            "status": "missing",
            "rows": [],
            "row_count": 0,
            "path": str(path),
            "error_message_safe": "",
            "external_calls_triggered": False,
            "query_filters": query_filters,
            "applied_filters": [],
            "skipped_filters": [],
            "query_wrapper": "duckdb_filtered_parquet.v1",
        }
    import duckdb

    safe_limit = max(1, min(int(limit or 1000), 10000))
    path_text = str(path).replace("'", "''")
    try:
        with duckdb.connect(database=":memory:", read_only=False) as connection:
            columns = list(connection.execute(f"SELECT * FROM read_parquet('{path_text}') LIMIT 0").df().columns)
            conditions, params, applied_filters, skipped_filters = _build_filters(
                columns,
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
            )
            where_sql = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"SELECT * FROM read_parquet('{path_text}'){where_sql} LIMIT {safe_limit}"
            rows = connection.execute(sql, params).df().to_dict("records")
    except Exception as exc:
        return {
            "status": "read_failed",
            "rows": [],
            "row_count": 0,
            "path": str(path),
            "error_message_safe": str(exc).splitlines()[0][:240],
            "external_calls_triggered": False,
            "query_filters": query_filters,
            "applied_filters": [],
            "skipped_filters": [],
            "query_wrapper": "duckdb_filtered_parquet.v1",
        }
    return {
        "status": "ready",
        "rows": rows,
        "row_count": len(rows),
        "path": str(path),
        "external_calls_triggered": False,
        "query_filters": query_filters,
        "applied_filters": applied_filters,
        "skipped_filters": skipped_filters,
        "query_wrapper": "duckdb_filtered_parquet.v1",
        "limit": safe_limit,
    }


def query_factor_values(
    parquet_path: str | Path,
    *,
    limit: int = 1000,
    ts_code: str | None = None,
    trade_date: str | int | None = None,
    start_date: str | int | None = None,
    end_date: str | int | None = None,
) -> dict[str, Any]:
    return query_parquet_dataset(
        parquet_path,
        limit=limit,
        ts_code=ts_code,
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
    )
