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


def _safe_limit(value: int | str | None) -> int:
    try:
        parsed = int(value or 1000)
    except (TypeError, ValueError):
        parsed = 1000
    return max(1, min(parsed, 10000))


def _parse_cursor(value: str | int | None) -> tuple[int, str, str]:
    text = str(value or "").strip()
    if not text:
        return 0, "", "not_provided"
    raw = text
    if text.startswith("offset:"):
        text = text.split(":", 1)[1]
    if not text.isdigit():
        return 0, raw[:80], "invalid_reset_to_zero"
    return max(0, int(text)), raw[:80], "accepted"


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


def _select_projection_columns(columns: list[str], projection_columns: list[str] | None) -> tuple[list[str], list[str], bool]:
    requested = [str(column).strip() for column in projection_columns or [] if str(column).strip()]
    if not requested:
        return list(columns), [], False
    available = set(columns)
    selected = [column for column in requested if column in available]
    missing = [column for column in requested if column not in available]
    return selected, missing, True


def _order_columns(columns: list[str]) -> list[str]:
    preferred = ("trade_date", "cal_date", "run_date", "ts_code", "factor_key", "strategy_key", "universe")
    return [column for column in preferred if column in columns]


def _empty_query_contract(
    *,
    status: str,
    limit: int,
    cursor: str = "",
    cursor_status: str = "not_provided",
    offset: int = 0,
    projected_columns: list[str] | None = None,
    missing_projected_columns: list[str] | None = None,
    projection_requested: bool = False,
    order_columns: list[str] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    return {
        "status": status,
        "rows": rows,
        "row_count": 0,
        "returned_row_count": 0,
        "projected_columns": projected_columns or [],
        "missing_projected_columns": missing_projected_columns or [],
        "projection_requested": projection_requested,
        "query_result_contract": {
            "schema_version": "duckdb_query_result_contract.v1",
            "status": status,
            "row_count": 0,
            "returned_row_count": 0,
            "projected_columns": projected_columns or [],
            "missing_projected_columns": missing_projected_columns or [],
            "order_columns": order_columns or [],
            "limit": limit,
            "cursor": cursor,
            "offset": offset,
            "has_more": False,
            "next_cursor": "",
            "safe_limit_enforced": True,
            "safe_parameter_binding": True,
            "external_calls_triggered": False,
        },
        "page_info": {
            "limit": limit,
            "cursor": cursor,
            "cursor_status": cursor_status,
            "offset": offset,
            "has_more": False,
            "next_cursor": "",
            "returned_row_count": 0,
        },
        "safe_limit_enforced": True,
        "safe_parameter_binding": True,
    }


def query_parquet_dataset(
    parquet_path: str | Path,
    *,
    limit: int = 1000,
    cursor: str | int | None = None,
    projection_columns: list[str] | None = None,
    ts_code: str | None = None,
    trade_date: str | int | None = None,
    start_date: str | int | None = None,
    end_date: str | int | None = None,
) -> dict[str, Any]:
    status = dependency_status()
    query_filters = {
        "limit": limit,
        "cursor": str(cursor or "").strip() or None,
        "ts_code": str(ts_code or "").strip() or None,
        "trade_date": _normalize_date(trade_date) or None,
        "start_date": _normalize_date(start_date) or None,
        "end_date": _normalize_date(end_date) or None,
    }
    safe_limit = _safe_limit(limit)
    safe_offset, safe_cursor, cursor_status = _parse_cursor(cursor)
    if not status["available"]:
        return {
            "status": "dependency_missing",
            "path": str(parquet_path),
            "external_calls_triggered": False,
            "query_filters": query_filters,
            "applied_filters": [],
            "skipped_filters": [],
            "query_wrapper": "duckdb_filtered_parquet.v1",
            **_empty_query_contract(
                status="dependency_missing",
                limit=safe_limit,
                cursor=safe_cursor,
                cursor_status=cursor_status,
                offset=safe_offset,
                projection_requested=bool(projection_columns),
            ),
            **status,
        }
    path = Path(parquet_path)
    if not path.exists():
        return {
            "status": "missing",
            "path": str(path),
            "error_message_safe": "",
            "external_calls_triggered": False,
            "query_filters": query_filters,
            "applied_filters": [],
            "skipped_filters": [],
            "query_wrapper": "duckdb_filtered_parquet.v1",
            **_empty_query_contract(
                status="missing",
                limit=safe_limit,
                cursor=safe_cursor,
                cursor_status=cursor_status,
                offset=safe_offset,
                projection_requested=bool(projection_columns),
            ),
        }
    import duckdb

    path_text = str(path).replace("'", "''")
    try:
        with duckdb.connect(database=":memory:", read_only=False) as connection:
            columns = list(connection.execute(f"SELECT * FROM read_parquet('{path_text}') LIMIT 0").df().columns)
            projected_columns, missing_projected_columns, projection_requested = _select_projection_columns(
                columns,
                projection_columns,
            )
            if projection_requested and not projected_columns:
                return {
                    "status": "projection_missing",
                    "path": str(path),
                    "external_calls_triggered": False,
                    "query_filters": query_filters,
                    "applied_filters": [],
                    "skipped_filters": [],
                    "query_wrapper": "duckdb_filtered_parquet.v1",
                    "available_columns": columns,
                    **_empty_query_contract(
                        status="projection_missing",
                        limit=safe_limit,
                        cursor=safe_cursor,
                        cursor_status=cursor_status,
                        offset=safe_offset,
                        projected_columns=[],
                        missing_projected_columns=missing_projected_columns,
                        projection_requested=True,
                    ),
                }
            conditions, params, applied_filters, skipped_filters = _build_filters(
                columns,
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
            )
            where_sql = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            order_columns = _order_columns(columns)
            order_sql = (
                " ORDER BY " + ", ".join(f"CAST({_quote_identifier(column)} AS VARCHAR)" for column in order_columns)
                if order_columns
                else ""
            )
            select_sql = ", ".join(_quote_identifier(column) for column in projected_columns)
            fetch_limit = safe_limit + 1
            sql = f"SELECT {select_sql} FROM read_parquet('{path_text}'){where_sql}{order_sql} LIMIT {fetch_limit} OFFSET {safe_offset}"
            fetched_rows = connection.execute(sql, params).df().to_dict("records")
            has_more = len(fetched_rows) > safe_limit
            rows = fetched_rows[:safe_limit]
    except Exception as exc:
        return {
            "status": "read_failed",
            "path": str(path),
            "error_message_safe": str(exc).splitlines()[0][:240],
            "external_calls_triggered": False,
            "query_filters": query_filters,
            "applied_filters": [],
            "skipped_filters": [],
            "query_wrapper": "duckdb_filtered_parquet.v1",
            **_empty_query_contract(
                status="read_failed",
                limit=safe_limit,
                cursor=safe_cursor,
                cursor_status=cursor_status,
                offset=safe_offset,
                projection_requested=bool(projection_columns),
            ),
        }
    next_cursor = f"offset:{safe_offset + safe_limit}" if has_more else ""
    page_info = {
        "limit": safe_limit,
        "cursor": safe_cursor,
        "cursor_status": cursor_status,
        "offset": safe_offset,
        "has_more": has_more,
        "next_cursor": next_cursor,
        "returned_row_count": len(rows),
    }
    result_contract = {
        "schema_version": "duckdb_query_result_contract.v1",
        "status": "ready",
        "row_count": len(rows),
        "returned_row_count": len(rows),
        "projected_columns": projected_columns,
        "missing_projected_columns": missing_projected_columns,
        "order_columns": order_columns,
        "limit": safe_limit,
        "cursor": safe_cursor,
        "offset": safe_offset,
        "has_more": has_more,
        "next_cursor": next_cursor,
        "safe_limit_enforced": True,
        "safe_parameter_binding": True,
        "external_calls_triggered": False,
    }
    return {
        "status": "ready",
        "rows": rows,
        "row_count": len(rows),
        "returned_row_count": len(rows),
        "path": str(path),
        "external_calls_triggered": False,
        "query_filters": query_filters,
        "applied_filters": applied_filters,
        "skipped_filters": skipped_filters,
        "query_wrapper": "duckdb_filtered_parquet.v1",
        "available_columns": columns,
        "projected_columns": projected_columns,
        "missing_projected_columns": missing_projected_columns,
        "order_columns": order_columns,
        "projection_requested": projection_requested,
        "query_result_contract": result_contract,
        "page_info": page_info,
        "limit": safe_limit,
        "safe_limit_enforced": True,
        "safe_parameter_binding": True,
    }


def query_factor_values(
    parquet_path: str | Path,
    *,
    limit: int = 1000,
    cursor: str | int | None = None,
    projection_columns: list[str] | None = None,
    ts_code: str | None = None,
    trade_date: str | int | None = None,
    start_date: str | int | None = None,
    end_date: str | int | None = None,
) -> dict[str, Any]:
    return query_parquet_dataset(
        parquet_path,
        limit=limit,
        cursor=cursor,
        projection_columns=projection_columns,
        ts_code=ts_code,
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
    )
