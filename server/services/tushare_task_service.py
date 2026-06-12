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
CALENDAR_REFRESH_APIS = ("trade_cal",)
EXTENDED_REFRESH_APIS = (
    "margin_detail",
    "top_list",
    "top_inst",
    "stk_limit",
    "limit_list_d",
    "limit_cpt_list",
    "cyq_perf",
    "cyq_chips",
    "anns_d",
    "forecast",
    "fina_indicator",
    "stk_holdertrade",
    "share_float",
    "pledge_stat",
    "pledge_detail",
    "stk_surv",
)
CHIP_REFRESH_APIS = ("cyq_perf", "cyq_chips")
MARGIN_REFRESH_APIS = ("margin_detail",)
DRAGON_TIGER_REFRESH_APIS = ("top_list", "top_inst")
LIMIT_EMOTION_REFRESH_APIS = ("stk_limit", "limit_list_d", "limit_cpt_list")
FINANCIAL_DISCLOSURE_REFRESH_APIS = ("forecast", "fina_indicator")
HARD_RISK_REFRESH_APIS = (
    "anns_d",
    "forecast",
    "stk_holdertrade",
    "share_float",
    "pledge_stat",
    "pledge_detail",
    "stk_surv",
)
ALL_REFRESH_APIS = CORE_REFRESH_APIS + CALENDAR_REFRESH_APIS + EXTENDED_REFRESH_APIS
PARQUET_DATASETS = {
    "daily": "daily",
    "daily_basic": "daily_basic",
    "moneyflow": "moneyflow",
    "trade_cal": "trade_cal",
}
REFRESH_API_SPECS = {
    "daily": {"method": "get_daily", "params": ("ts_code", "start_date", "end_date")},
    "daily_basic": {"method": "get_daily_basic", "params": ("ts_code", "start_date", "end_date")},
    "moneyflow": {"method": "get_moneyflow", "params": ("ts_code", "trade_date", "start_date", "end_date")},
    "trade_cal": {"method": "get_trade_cal", "params": ("start_date", "end_date", "exchange")},
    "margin_detail": {"method": "get_margin_detail", "params": ("ts_code", "trade_date", "start_date", "end_date")},
    "top_list": {"method": "get_top_list", "params": ("trade_date", "ts_code")},
    "top_inst": {"method": "get_top_inst", "params": ("trade_date", "ts_code")},
    "stk_limit": {"method": "get_stk_limit", "params": ("ts_code", "trade_date", "start_date", "end_date")},
    "limit_list_d": {"method": "get_limit_list_d", "params": ("ts_code", "trade_date", "start_date", "end_date", "limit_type")},
    "limit_cpt_list": {"method": "get_limit_cpt_list", "params": ("trade_date", "start_date", "end_date")},
    "cyq_perf": {"method": "get_cyq_perf", "params": ("ts_code", "trade_date", "start_date", "end_date")},
    "cyq_chips": {"method": "get_cyq_chips", "params": ("ts_code", "trade_date", "start_date", "end_date")},
    "anns_d": {"method": "get_anns_d", "params": ("ts_code", "ann_date", "start_date", "end_date")},
    "forecast": {"method": "get_forecast", "params": ("ts_code", "ann_date", "start_date", "end_date", "period")},
    "fina_indicator": {"method": "get_fina_indicator", "params": ("ts_code", "ann_date", "start_date", "end_date", "period")},
    "stk_holdertrade": {"method": "get_stk_holdertrade", "params": ("ts_code", "ann_date", "start_date", "end_date", "trade_type", "holder_type")},
    "share_float": {"method": "get_share_float", "params": ("ts_code", "ann_date", "float_date", "start_date", "end_date")},
    "pledge_stat": {"method": "get_pledge_stat", "params": ("ts_code", "end_date")},
    "pledge_detail": {"method": "get_pledge_detail", "params": ("ts_code",)},
    "stk_surv": {"method": "get_stk_surv", "params": ("ts_code", "trade_date", "start_date", "end_date")},
}
SECRET_MARKERS = ("token", "api_key", "apikey", "authorization", "bearer", "secret", "password")
STACK_MARKERS = ("traceback", 'file "', " line ", "exception")
CALL_LEDGER_REQUIRED_FIELDS = (
    "api",
    "request_params_safe",
    "row_count",
    "data_date",
    "local_fetched_at",
    "call_status",
    "error_message_safe",
)


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
        requested = list(ALL_REFRESH_APIS)
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
    if _payload_field(payload, "include_calendar") is True:
        for key in CALENDAR_REFRESH_APIS:
            if key not in selected:
                selected.append(key)
    return selected or list(default_apis)


def _api_group(api: str) -> str:
    if api in CORE_REFRESH_APIS:
        return "core"
    if api in CALENDAR_REFRESH_APIS:
        return "calendar"
    if api in EXTENDED_REFRESH_APIS:
        return "extended"
    return "unknown"


def _api_domain(api: str) -> str:
    if api in CORE_REFRESH_APIS:
        return "core_market_data"
    if api in CALENDAR_REFRESH_APIS:
        return "trade_calendar"
    if api == "margin_detail":
        return "margin_financing"
    if api in {"top_list", "top_inst"}:
        return "dragon_tiger"
    if api in {"stk_limit", "limit_list_d", "limit_cpt_list"}:
        return "limit_emotion"
    if api in CHIP_REFRESH_APIS:
        return "chip_distribution"
    if api in {"fina_indicator", "forecast"}:
        return "financial_disclosure"
    if api in HARD_RISK_REFRESH_APIS:
        return "hard_risk"
    return "other_extended"


def _api_capability_rows(selected_apis: Iterable[str] | None = None) -> list[dict[str, Any]]:
    selected = set(selected_apis or [])
    rows: list[dict[str, Any]] = []
    for api, spec in REFRESH_API_SPECS.items():
        params = list(spec.get("params") or [])
        dataset = PARQUET_DATASETS.get(api)
        rows.append(
            {
                "api": api,
                "group": _api_group(api),
                "domain": _api_domain(api),
                "method": spec.get("method"),
                "params": params,
                "requires_ts_code": "ts_code" in params,
                "selected": api in selected,
                "chip_api": api in CHIP_REFRESH_APIS,
                "hard_risk_api": api in HARD_RISK_REFRESH_APIS,
                "parquet_enabled": bool(dataset),
                "parquet_dataset": dataset,
                "runtime_enabled": True,
                "button_gated": True,
                "cache_get_external_calls": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _validation_status(call_status: str) -> str:
    if call_status == "success":
        return "validated_success"
    if call_status == "empty":
        return "validated_empty"
    if call_status == "failed":
        return "validated_failed"
    if call_status.startswith("blocked_"):
        return "blocked"
    if call_status == "not_requested":
        return "not_requested"
    return "unknown"


def _api_validation_rows(selected_apis: Iterable[str], call_ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ledger_by_api = {str(row.get("api") or ""): row for row in call_ledger}
    selected_set = set(selected_apis)
    rows: list[dict[str, Any]] = []
    for capability in _api_capability_rows(selected_apis):
        api = str(capability["api"])
        ledger = ledger_by_api.get(api, {})
        call_status = str(ledger.get("call_status") or ("not_requested" if api not in selected_set else "not_called"))
        selected = api in selected_set
        called = bool(ledger)
        if called and call_status.startswith("blocked_"):
            validation_scope = "preflight_blocked"
        elif called:
            validation_scope = "task_call_result"
        elif selected:
            validation_scope = "selected_not_called"
        else:
            validation_scope = "capability_matrix_only"
        rows.append(
            {
                **capability,
                "called": called,
                "call_status": call_status,
                "validation_status": _validation_status(call_status),
                "validation_scope": validation_scope,
                "result_semantics": "unselected API 只代表能力矩阵，不代表真实调用或数据可用。" if not selected else "selected API 必须以 call_ledger 为准；失败、空数据和缺参不得伪装成 verified。",
                "row_count": int(ledger.get("row_count") or 0),
                "data_date": ledger.get("data_date"),
                "local_fetched_at": ledger.get("local_fetched_at"),
                "error_message_safe": ledger.get("error_message_safe", ""),
                "parquet_status": ledger.get("parquet_status", "not_enabled" if not capability.get("parquet_enabled") else "not_written"),
                "parquet_row_count": int(ledger.get("parquet_row_count") or 0),
                "call_ledger_required_fields": list(CALL_LEDGER_REQUIRED_FIELDS),
                "cache_boundary": "GET cache API 不能调用该接口；只有 POST 按钮任务可以进入刷新管线。",
                "action_boundary": "不会执行真实交易，不会修改 strategy action。",
            }
        )
    return rows


def _api_validation_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_group: dict[str, dict[str, int]] = {}
    by_domain: dict[str, dict[str, int]] = {}
    for row in rows:
        status = str(row.get("validation_status") or "unknown")
        group = str(row.get("group") or "unknown")
        domain = str(row.get("domain") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        group_counts = by_group.setdefault(group, {})
        group_counts[status] = group_counts.get(status, 0) + 1
        domain_counts = by_domain.setdefault(domain, {})
        domain_counts[status] = domain_counts.get(status, 0) + 1
    selected_rows = [row for row in rows if row.get("selected")]
    chip_rows = [row for row in rows if row.get("chip_api")]
    hard_risk_rows = [row for row in rows if row.get("hard_risk_api")]

    def _domain_rows(apis: Iterable[str]) -> list[dict[str, Any]]:
        api_set = set(apis)
        return [row for row in rows if row.get("api") in api_set]

    def _selected_count(apis: Iterable[str]) -> int:
        return len([row for row in _domain_rows(apis) if row.get("selected")])

    def _validated_count(apis: Iterable[str]) -> int:
        return len([row for row in _domain_rows(apis) if str(row.get("validation_status") or "").startswith("validated_")])

    return {
        "status": "ready",
        "api_count": len(rows),
        "selected_api_count": len(selected_rows),
        "core_api_count": len([row for row in rows if row.get("group") == "core"]),
        "calendar_api_count": len([row for row in rows if row.get("group") == "calendar"]),
        "extended_api_count": len([row for row in rows if row.get("group") == "extended"]),
        "parquet_enabled_api_count": len([row for row in rows if row.get("parquet_enabled")]),
        "called_api_count": len([row for row in rows if row.get("called")]),
        "validated_success_count": len([row for row in rows if row.get("validation_status") == "validated_success"]),
        "validated_empty_count": len([row for row in rows if row.get("validation_status") == "validated_empty"]),
        "validated_failed_count": len([row for row in rows if row.get("validation_status") == "validated_failed"]),
        "blocked_count": len([row for row in rows if row.get("validation_status") == "blocked"]),
        "not_requested_count": len([row for row in rows if row.get("validation_status") == "not_requested"]),
        "status_counts": by_status,
        "group_status_counts": by_group,
        "domain_status_counts": by_domain,
        "domain_count": len(by_domain),
        "chip_api_count": len(chip_rows),
        "hard_risk_api_count": len(hard_risk_rows),
        "selected_chip_api_count": len([row for row in chip_rows if row.get("selected")]),
        "selected_hard_risk_api_count": len([row for row in hard_risk_rows if row.get("selected")]),
        "validated_chip_api_count": len([row for row in chip_rows if str(row.get("validation_status") or "").startswith("validated_")]),
        "validated_hard_risk_api_count": len([row for row in hard_risk_rows if str(row.get("validation_status") or "").startswith("validated_")]),
        "selected_margin_api_count": _selected_count(MARGIN_REFRESH_APIS),
        "selected_dragon_tiger_api_count": _selected_count(DRAGON_TIGER_REFRESH_APIS),
        "selected_limit_emotion_api_count": _selected_count(LIMIT_EMOTION_REFRESH_APIS),
        "selected_financial_disclosure_api_count": _selected_count(FINANCIAL_DISCLOSURE_REFRESH_APIS),
        "validated_margin_api_count": _validated_count(MARGIN_REFRESH_APIS),
        "validated_dragon_tiger_api_count": _validated_count(DRAGON_TIGER_REFRESH_APIS),
        "validated_limit_emotion_api_count": _validated_count(LIMIT_EMOTION_REFRESH_APIS),
        "validated_financial_disclosure_api_count": _validated_count(FINANCIAL_DISCLOSURE_REFRESH_APIS),
        "cache_get_external_calls": False,
        "button_gated_external_calls_only": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "matrix_only_api_count": len([row for row in rows if row.get("validation_scope") == "capability_matrix_only"]),
        "task_call_result_count": len([row for row in rows if row.get("validation_scope") == "task_call_result"]),
        "preflight_blocked_count": len([row for row in rows if row.get("validation_scope") == "preflight_blocked"]),
        "does_not_claim_unselected_apis_verified": True,
    }


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

    api_validation_rows = _api_validation_rows(selected_apis, call_ledger)
    api_validation_summary = _api_validation_summary(api_validation_rows)
    refresh_packet = {
        "packet_key": output_packet_key,
        "schema_version": "command_center_tushare_refresh_task.v1",
        "status": status,
        "task_type": task_type,
        "selected_apis": selected_apis,
        "api_groups": {
            "core": list(CORE_REFRESH_APIS),
            "calendar": list(CALENDAR_REFRESH_APIS),
            "extended": list(EXTENDED_REFRESH_APIS),
            "chip": list(CHIP_REFRESH_APIS),
            "margin": list(MARGIN_REFRESH_APIS),
            "dragon_tiger": list(DRAGON_TIGER_REFRESH_APIS),
            "limit_emotion": list(LIMIT_EMOTION_REFRESH_APIS),
            "financial_disclosure": list(FINANCIAL_DISCLOSURE_REFRESH_APIS),
            "hard_risk": list(HARD_RISK_REFRESH_APIS),
            "all": list(REFRESH_API_SPECS.keys()),
            "parquet_enabled": list(PARQUET_DATASETS.keys()),
        },
        "api_capability_rows": _api_capability_rows(selected_apis),
        "api_validation_rows": api_validation_rows,
        "api_validation_summary": api_validation_summary,
        "api_validation_matrix_policy": {
            "scope": "selected APIs use real task call_ledger; unselected APIs are capability matrix only.",
            "selected_apis": list(selected_apis),
            "matrix_only_apis": [row["api"] for row in api_validation_rows if row.get("validation_scope") == "capability_matrix_only"],
            "call_ledger_required_fields": list(CALL_LEDGER_REQUIRED_FIELDS),
            "cache_get_external_calls": False,
            "button_gated_external_calls_only": True,
            "does_not_claim_unselected_apis_verified": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        "call_ledger": call_ledger,
        "call_count": len(call_ledger),
        "success_count": len(success_or_empty),
        "failed_count": len(failed),
        "blocked_count": len(blocked),
        "parquet_enabled_api_count": api_validation_summary["parquet_enabled_api_count"],
        "extended_api_count": api_validation_summary["extended_api_count"],
        "calendar_api_count": api_validation_summary["calendar_api_count"],
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
