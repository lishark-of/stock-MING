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
    "backtest_results": "backtest_results",
    "backtest-results": "backtest_results",
}
CANONICAL_PARQUET_DATASETS = ["factor_values", "daily", "daily_basic", "moneyflow", "backtest_results"]


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def parquet_dataset_status(dataset: str, *, limit: int = 100) -> dict[str, Any]:
    selected = _canonical_dataset(dataset)
    if not selected:
        return _attach_storage_lineage(
            {
                "schema_version": "command_center_3_storage_dataset.v1",
                "status": "unsupported_dataset",
                "dataset": str(dataset or ""),
                "supported_datasets": list(CANONICAL_PARQUET_DATASETS),
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
    query = duckdb_store.query_parquet_dataset(path, limit=limit)
    metadata["path"] = _path_label(path)
    query["path"] = _path_label(path)
    packet = {
        "schema_version": "command_center_3_storage_dataset.v1",
        "store": "parquet_duckdb",
        "status": metadata.get("status", "missing"),
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
    return _attach_storage_lineage(
        packet,
        api="local_storage_dataset_cache",
        endpoint=f"GET /api/storage/{selected}",
        dataset=selected,
        row_count=packet["row_count"],
        path=metadata["path"],
    )


def factor_values_status(*, limit: int = 100) -> dict[str, Any]:
    packet = parquet_dataset_status("factor_values", limit=limit)
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
    base = {
        "schema_version": "command_center_3_storage_sqlite_meta.v1",
        "store": "sqlite_meta",
        "path": _path_label(path),
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
        task_metadata = store.list_task_metadata()
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
            "metadata_is_payload_only": False,
            "does_not_return_payload_json": True,
        },
        api="local_storage_sqlite_meta_cache",
        endpoint="GET /api/storage/sqlite-meta",
        row_count=len(packet_metadata) + len(task_metadata),
        path=base["path"],
    )


def storage_overview(*, limit: int = 20) -> dict[str, Any]:
    datasets = [parquet_dataset_status(name, limit=limit) for name in CANONICAL_PARQUET_DATASETS]
    sqlite_meta = sqlite_meta_status(limit=limit)
    packet = {
        "schema_version": "command_center_3_storage_overview.v1",
        "store": "parquet_duckdb",
        "status": "cache_ready",
        "metadata_store": "sqlite_meta",
        "datasets": datasets,
        "dataset_status": {item["dataset"]: item["metadata"]["status"] for item in datasets},
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
    if not rows:
        return {
            "status": "empty",
            "dataset": "factor_values",
            "row_count": 0,
            "path": _path_label(parquet_store.dataset_path(root=PARQUET_ROOT, name="factor_values")),
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
