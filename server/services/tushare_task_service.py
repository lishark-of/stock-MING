from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Iterable, Mapping

from storage import parquet_store
from storage.sqlite_meta import SQLiteMetaStore

from . import storage_service
from .task_service import create_task_record, update_task_status


SQLITE_META_PATH = Path(__file__).resolve().parents[2] / ".stock_ming_3" / "meta.sqlite"
CORE_REFRESH_APIS = ("daily", "daily_basic", "moneyflow")
EXTENDED_REFRESH_APIS = (
    "margin_detail",
    "stk_limit",
    "limit_list_d",
    "limit_cpt_list",
    "cyq_perf",
    "cyq_chips",
    "anns_d",
    "forecast",
    "stk_holdertrade",
    "share_float",
    "pledge_stat",
    "pledge_detail",
)
PARQUET_DATASETS = {
    "daily": "daily",
    "daily_basic": "daily_basic",
    "moneyflow": "moneyflow",
}
REFRESH_API_SPECS = {
    "daily": {"method": "get_daily", "params": ("ts_code", "start_date", "end_date")},
    "daily_basic": {"method": "get_daily_basic", "params": ("ts_code", "start_date", "end_date")},
    "moneyflow": {"method": "get_moneyflow", "params": ("ts_code", "trade_date", "start_date", "end_date")},
    "margin_detail": {"method": "get_margin_detail", "params": ("ts_code", "trade_date", "start_date", "end_date")},
    "stk_limit": {"method": "get_stk_limit", "params": ("ts_code", "trade_date", "start_date", "end_date")},
    "limit_list_d": {"method": "get_limit_list_d", "params": ("ts_code", "trade_date", "start_date", "end_date", "limit_type")},
    "limit_cpt_list": {"method": "get_limit_cpt_list", "params": ("trade_date", "start_date", "end_date")},
    "cyq_perf": {"method": "get_cyq_perf", "params": ("ts_code", "trade_date", "start_date", "end_date")},
    "cyq_chips": {"method": "get_cyq_chips", "params": ("ts_code", "trade_date", "start_date", "end_date")},
    "anns_d": {"method": "get_anns_d", "params": ("ts_code", "ann_date", "start_date", "end_date")},
    "forecast": {"method": "get_forecast", "params": ("ts_code", "ann_date", "start_date", "end_date", "period")},
    "stk_holdertrade": {"method": "get_stk_holdertrade", "params": ("ts_code", "ann_date", "start_date", "end_date", "trade_type", "holder_type")},
    "share_float": {"method": "get_share_float", "params": ("ts_code", "ann_date", "float_date", "start_date", "end_date")},
    "pledge_stat": {"method": "get_pledge_stat", "params": ("ts_code", "end_date")},
    "pledge_detail": {"method": "get_pledge_detail", "params": ("ts_code",)},
}
SECRET_MARKERS = ("token", "api_key", "apikey", "authorization", "bearer", "secret", "password")
STACK_MARKERS = ("traceback", 'file "', " line ", "exception")


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _safe_text(value: Any, *, limit: int = 300) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if any(marker in lowered for marker in SECRET_MARKERS) or any(marker in lowered for marker in STACK_MARKERS):
        return "tushare_error_redacted_safe"
    return text[:limit]


def _safe_payload(payload: Any = None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in SECRET_MARKERS):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[str(key)] = _safe_text(value) if isinstance(value, str) else value
        elif isinstance(value, list):
            result[str(key)] = [_safe_text(item) for item in value if isinstance(item, (str, int, float, bool))][:20]
    return result


def _payload_field(payload: Any, key: str, default: Any = None) -> Any:
    return payload.get(key, default) if isinstance(payload, Mapping) else default


def _selected_apis(payload: Any, default_apis: Iterable[str]) -> list[str]:
    requested = _payload_field(payload, "apis")
    if requested is None and _payload_field(payload, "include_extended") is True:
        requested = list(CORE_REFRESH_APIS + EXTENDED_REFRESH_APIS)
    if requested is None:
        requested = list(default_apis)
    if isinstance(requested, str):
        requested = [item.strip() for item in requested.split(",")]
    if not isinstance(requested, list):
        requested = list(default_apis)
    selected: list[str] = []
    for item in requested:
        key = str(item or "").strip()
        if key in REFRESH_API_SPECS and key not in selected:
            selected.append(key)
    return selected or list(default_apis)


def _request_params_for_api(api: str, payload: Any) -> dict[str, Any]:
    safe = _safe_payload(payload)
    if "ticker" in safe and "ts_code" not in safe:
        safe["ts_code"] = safe["ticker"]
    if "symbol" in safe and "ts_code" not in safe:
        safe["ts_code"] = safe["symbol"]
    params: dict[str, Any] = {}
    for key in REFRESH_API_SPECS[api]["params"]:
        value = safe.get(key)
        if value not in (None, ""):
            params[key] = value
    return params


def _rows_from_data(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if hasattr(data, "empty") and hasattr(data, "where") and hasattr(data, "notna"):
        if bool(getattr(data, "empty", True)):
            return []
        return data.head(200).where(data.notna(), None).to_dict("records")
    if isinstance(data, list):
        return [dict(item) for item in data if isinstance(item, Mapping)][:200]
    if isinstance(data, Mapping):
        rows = data.get("rows")
        if isinstance(rows, list):
            return [dict(item) for item in rows if isinstance(item, Mapping)][:200]
        return [dict(data)]
    return []


def _row_count(data: Any) -> int:
    try:
        if hasattr(data, "__len__"):
            return int(len(data))
    except Exception:
        return 0
    return len(_rows_from_data(data))


def _data_date(rows: list[dict[str, Any]]) -> Any:
    for row in rows:
        for key in ("trade_date", "ann_date", "end_date", "float_date", "cal_date", "date"):
            value = row.get(key)
            if value not in (None, ""):
                return value
    return None


def _dataframe_for_write(data: Any) -> Any:
    if data is None:
        return None
    if hasattr(data, "to_parquet"):
        return data
    rows = _rows_from_data(data)
    if not rows:
        return None
    try:
        import pandas as pd

        return pd.DataFrame(rows)
    except Exception:
        return None


def _write_parquet_dataset(api: str, data: Any) -> dict[str, Any]:
    dataset = PARQUET_DATASETS.get(api)
    if not dataset:
        return {"status": "not_enabled", "dataset": None, "row_count": 0, "path": ""}
    df = _dataframe_for_write(data)
    if df is None:
        return {
            "status": "empty",
            "dataset": dataset,
            "row_count": 0,
            "path": str(parquet_store.dataset_path(root=storage_service.PARQUET_ROOT, name=dataset)),
        }
    try:
        result = parquet_store.write_dataset(df, root=storage_service.PARQUET_ROOT, name=dataset)
    except Exception as exc:
        return {
            "status": "failed",
            "dataset": dataset,
            "row_count": 0,
            "path": str(parquet_store.dataset_path(root=storage_service.PARQUET_ROOT, name=dataset)),
            "error_message_safe": _safe_text(exc),
        }
    result["dataset"] = dataset
    return result


def _call_ledger_row(api: str, *, params: dict[str, Any], result: dict[str, Any], parquet_result: dict[str, Any] | None, now: str) -> dict[str, Any]:
    data = result.get("data") if isinstance(result, Mapping) else None
    rows = _rows_from_data(data)
    ok = bool(result.get("ok")) if isinstance(result, Mapping) else False
    row_count = _row_count(data)
    error = "" if ok else _safe_text(result.get("error") if isinstance(result, Mapping) else "invalid_tushare_result")
    if ok and row_count > 0:
        call_status = "success"
    elif ok:
        call_status = "empty"
    else:
        call_status = "failed"
    return {
        "api": api,
        "request_params_safe": params,
        "row_count": row_count,
        "data_date": _data_date(rows),
        "local_fetched_at": now,
        "call_status": call_status,
        "error_message_safe": error,
        "parquet_dataset": (parquet_result or {}).get("dataset"),
        "parquet_status": (parquet_result or {}).get("status", "not_enabled"),
        "parquet_row_count": int((parquet_result or {}).get("row_count") or 0),
        "external": True,
        "external_calls_triggered": True,
        "tushare_called": True,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _blocked_missing_param_ledger_row(api: str, *, params: dict[str, Any], missing_param: str, now: str) -> dict[str, Any]:
    return {
        "api": api,
        "request_params_safe": params,
        "row_count": 0,
        "data_date": None,
        "local_fetched_at": now,
        "call_status": f"blocked_missing_{missing_param}",
        "error_message_safe": f"missing_required_{missing_param}",
        "parquet_dataset": PARQUET_DATASETS.get(api),
        "parquet_status": "not_written_missing_required_param",
        "parquet_row_count": 0,
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def run_tushare_refresh_task(
    payload: Any = None,
    *,
    task_type: str = "refresh_tushare_facts",
    output_packet_key: str = "command_center_tushare_refresh_packet",
    default_apis: Iterable[str] = CORE_REFRESH_APIS,
    adapter: Any = None,
) -> dict[str, Any]:
    selected_apis = _selected_apis(payload, default_apis)
    task = create_task_record(
        task_type,
        output_packet_key=output_packet_key,
        payload=_safe_payload(payload),
        current_step="tushare_refresh_queued_button_gated",
        warnings=[
            "Tushare refresh 只能由 POST 按钮任务触发；GET cache API 不会进入本管线。",
            "任务只记录安全 request_params_safe 与 error_message_safe，不读取或打印 token/key。",
            "刷新结果不修改 strategy action，不执行真实交易。",
        ],
    )
    update_task_status(task["task_id"], status="running", progress=0.05, current_step="preparing_tushare_refresh")
    adapter_module = adapter
    call_ledger: list[dict[str, Any]] = []
    for index, api in enumerate(selected_apis, start=1):
        params = _request_params_for_api(api, payload)
        progress = 0.05 + (index - 1) / max(len(selected_apis), 1) * 0.85
        update_task_status(
            task["task_id"],
            status="running",
            progress=progress,
            current_step=f"calling_tushare_{api}",
            call_ledger=call_ledger,
        )
        now = _now_iso()
        if "ts_code" in REFRESH_API_SPECS[api]["params"] and not params.get("ts_code"):
            call_ledger.append(_blocked_missing_param_ledger_row(api, params=params, missing_param="ts_code", now=now))
            continue
        if adapter_module is None:
            update_task_status(
                task["task_id"],
                status="running",
                progress=progress,
                current_step="loading_tushare_adapter",
                call_ledger=call_ledger,
            )
            import tushare_adapter as adapter_module
        try:
            fn = getattr(adapter_module, str(REFRESH_API_SPECS[api]["method"]))
            result = fn(**params)
            if not isinstance(result, Mapping):
                result = {"ok": False, "data": None, "error": f"invalid result type: {type(result).__name__}"}
        except Exception as exc:
            result = {"ok": False, "data": None, "error": _safe_text(exc)}
        parquet_result = _write_parquet_dataset(api, result.get("data")) if bool(result.get("ok")) else {"status": "not_written_failed_call"}
        call_ledger.append(_call_ledger_row(api, params=params, result=dict(result), parquet_result=parquet_result, now=now))

    success_or_empty = [row for row in call_ledger if row.get("call_status") in {"success", "empty"}]
    failed = [row for row in call_ledger if row.get("call_status") == "failed"]
    blocked = [row for row in call_ledger if str(row.get("call_status") or "").startswith("blocked_")]
    current_step = "tushare_refresh_completed"
    status = "success"
    error_message_safe = ""
    if failed and success_or_empty:
        current_step = "tushare_refresh_partial_safe"
        error_message_safe = _safe_text(failed[0].get("error_message_safe") or "")
    elif failed and not success_or_empty:
        status = "failed"
        current_step = "tushare_refresh_failed_safe"
        error_message_safe = _safe_text(failed[0].get("error_message_safe") or "tushare_refresh_failed")
    elif blocked and not success_or_empty:
        status = "failed"
        current_step = "tushare_refresh_blocked_missing_params"
        error_message_safe = _safe_text(blocked[0].get("error_message_safe") or "missing_required_params")

    refresh_packet = {
        "packet_key": output_packet_key,
        "schema_version": "command_center_tushare_refresh_task.v1",
        "status": status,
        "task_type": task_type,
        "selected_apis": selected_apis,
        "call_ledger": call_ledger,
        "call_count": len(call_ledger),
        "success_count": len(success_or_empty),
        "failed_count": len(failed),
        "blocked_count": len(blocked),
        "external_calls_triggered": any(row.get("external_calls_triggered") is True for row in call_ledger),
        "tushare_called": any(row.get("tushare_called") is True for row in call_ledger),
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "warnings": [
            "该 packet 仅记录按钮门控 Tushare 刷新审计，不是交易信号。",
            "失败或空数据不会被伪装成 verified，不会污染 strategy action。",
        ],
    }
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(output_packet_key, refresh_packet)
    except Exception:
        pass

    return update_task_status(
        task["task_id"],
        status=status,
        progress=1.0,
        current_step=current_step,
        error_message_safe=error_message_safe,
        call_ledger=call_ledger,
    ) or task
