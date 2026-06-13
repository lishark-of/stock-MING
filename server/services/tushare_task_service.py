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
VALIDATION_TARGET_GROUPS = (
    ("trade_calendar", "交易日历", CALENDAR_REFRESH_APIS),
    ("margin_financing", "融资融券", MARGIN_REFRESH_APIS),
    ("dragon_tiger", "龙虎榜/机构席位", DRAGON_TIGER_REFRESH_APIS),
    ("limit_emotion", "涨跌停/情绪", LIMIT_EMOTION_REFRESH_APIS),
    ("chip_distribution", "筹码分布", CHIP_REFRESH_APIS),
    ("financial_disclosure", "财务披露", FINANCIAL_DISCLOSURE_REFRESH_APIS),
    ("hard_risk", "硬风险公告", HARD_RISK_REFRESH_APIS),
)
PROVIDER_TARGET_SAMPLE_REQUIREMENTS = {
    "trade_calendar": {
        "sample_window": "long_window_covering_open_closed_rows_weekends_holidays_and_latest_completed_session",
        "context_groups": (("start_date",), ("end_date",)),
        "required_success_evidence": (
            "open_and_closed_calendar_rows",
            "latest_completed_trade_date_resolved",
            "holiday_and_weekend_boundary_covered",
        ),
        "required_failure_evidence": (
            "empty_window_distinguished",
            "parse_failure_safe",
            "fallback_calendar_warning_visible",
        ),
    },
    "margin_financing": {
        "sample_window": "target_stock_trade_date_or_start_end_window",
        "context_groups": (("ts_code",), ("trade_date", "start_date"), ("trade_date", "end_date")),
        "required_success_evidence": (
            "target_stock_margin_rows_or_valid_empty_window",
            "row_count_and_data_date_recorded",
            "permission_state_distinguished",
        ),
        "required_failure_evidence": (
            "permission_denied_distinguished",
            "empty_window_distinguished",
            "missing_ts_code_preflight_blocked",
        ),
    },
    "dragon_tiger": {
        "sample_window": "target_stock_trade_date_with_top_list_and_top_inst_cross_check",
        "context_groups": (("ts_code",), ("trade_date",)),
        "required_success_evidence": (
            "top_list_trade_date_rows_or_valid_empty",
            "top_inst_trade_date_rows_or_valid_empty",
            "institution_seat_result_semantics_visible",
        ),
        "required_failure_evidence": (
            "permission_denied_distinguished",
            "empty_window_distinguished",
            "parse_failure_safe",
        ),
    },
    "limit_emotion": {
        "sample_window": "target_stock_limit_window_with_limit_type_where_supported",
        "context_groups": (("ts_code",), ("trade_date", "start_date"), ("trade_date", "end_date")),
        "required_success_evidence": (
            "stk_limit_rows_or_valid_empty",
            "limit_list_d_rows_or_valid_empty",
            "limit_cpt_list_rows_or_valid_empty",
        ),
        "required_failure_evidence": (
            "limit_type_or_empty_window_distinguished",
            "permission_denied_distinguished",
            "parse_failure_safe",
        ),
    },
    "chip_distribution": {
        "sample_window": "target_stock_chip_window_with_cyq_perf_and_cyq_chips",
        "context_groups": (("ts_code",), ("trade_date", "start_date"), ("trade_date", "end_date")),
        "required_success_evidence": (
            "cyq_perf_rows_or_valid_empty",
            "cyq_chips_rows_or_valid_empty",
            "chip_date_context_recorded",
        ),
        "required_failure_evidence": (
            "permission_denied_distinguished",
            "empty_window_distinguished",
            "parse_failure_safe",
        ),
    },
    "financial_disclosure": {
        "sample_window": "target_stock_announcement_or_period_window_for_forecast_and_fina_indicator",
        "context_groups": (("ts_code",), ("ann_date", "period", "start_date"), ("ann_date", "period", "end_date")),
        "required_success_evidence": (
            "forecast_rows_or_valid_empty",
            "fina_indicator_rows_or_valid_empty",
            "announcement_or_period_context_recorded",
        ),
        "required_failure_evidence": (
            "permission_denied_distinguished",
            "empty_window_distinguished",
            "parse_failure_safe",
        ),
    },
    "hard_risk": {
        "sample_window": "target_stock_announcement_float_pledge_and_survival_windows",
        "context_groups": (("ts_code",), ("ann_date", "float_date", "trade_date", "end_date", "start_date")),
        "required_success_evidence": (
            "announcement_rows_or_valid_empty",
            "holder_float_pledge_rows_or_valid_empty",
            "survival_status_rows_or_valid_empty",
        ),
        "required_failure_evidence": (
            "permission_denied_distinguished",
            "empty_window_distinguished",
            "parse_failure_safe",
        ),
    },
}
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
DATE_CONTEXT_PARAMS = ("trade_date", "start_date", "end_date", "ann_date", "period", "float_date")
PAYLOAD_CONTROL_KEYS = ("apis", "include_extended", "include_calendar", "ticker", "symbol")
CALL_LEDGER_REQUIRED_FIELDS = (
    "api",
    "request_params_safe",
    "row_count",
    "data_date",
    "local_fetched_at",
    "call_status",
    "error_message_safe",
)
ACCEPTANCE_SAFE_TERMINAL_STATUSES = {"success", "empty", "failed"}
EXPECTED_FAILURE_MODE_QA = (
    (
        "empty_result_or_no_record",
        "empty / no record / empty window",
        "selected API returned ok with zero rows; this is validated_empty and not a data sample.",
    ),
    (
        "permission_denied",
        "permission denied",
        "provider error text indicates permission or access denial; safe error text must still be redacted.",
    ),
    (
        "parse_failed_or_invalid_result",
        "parse failure / invalid result",
        "adapter returned an invalid result shape or parse/decode failure.",
    ),
    (
        "missing_required_parameter",
        "missing required parameter",
        "preflight blocked a selected API before an external call.",
    ),
    (
        "provider_error_safe",
        "provider error",
        "provider failed for another safe, redacted reason.",
    ),
    (
        "matrix_only_not_requested",
        "matrix only / not requested",
        "unselected APIs remain capability rows and must not be marked verified.",
    ),
)


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _safe_text(value: Any, *, limit: int = 300) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if any(marker in lowered for marker in SECRET_MARKERS) or any(marker in lowered for marker in STACK_MARKERS):
        return "tushare_error_redacted_safe"
    return text[:limit]


def _failure_mode_from_error(value: Any) -> str:
    text = str(value or "").strip().lower()
    if any(marker in text for marker in ("permission", "denied", "forbidden", "unauthorized", "权限", "无权限", "无此权限")):
        return "permission_denied"
    if any(marker in text for marker in ("invalid result", "parse", "json", "decode", "malformed", "schema", "no attribute")):
        return "parse_failed_or_invalid_result"
    if any(marker in text for marker in ("empty", "no data", "no record", "not found", "无数据", "暂无", "没有数据")):
        return "empty_result_or_no_record"
    return "provider_error_safe"


def _failure_mode_status(failure_mode: str) -> str:
    if failure_mode == "none":
        return "success_non_empty"
    if failure_mode == "empty_result_or_no_record":
        return "validated_empty_not_verified_data"
    if failure_mode == "missing_required_parameter":
        return "preflight_blocked_no_external_call"
    if failure_mode in {"permission_denied", "parse_failed_or_invalid_result", "provider_error_safe"}:
        return "validated_failed_safe"
    if failure_mode == "matrix_only_not_requested":
        return "capability_matrix_only"
    return "unknown"


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
                "failure_mode": ledger.get("failure_mode") or ("matrix_only_not_requested" if not selected else "unknown"),
                "failure_mode_status": ledger.get("failure_mode_status") or ("capability_matrix_only" if not selected else "unknown"),
                "safe_failure_mode_visible": bool(ledger.get("safe_failure_mode_visible") or not selected),
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


def _validation_target_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_api = {str(row.get("api") or ""): row for row in rows}
    target_rows: list[dict[str, Any]] = []
    for target_key, label, apis in VALIDATION_TARGET_GROUPS:
        api_rows = [by_api[api] for api in apis if api in by_api]
        selected_rows = [row for row in api_rows if row.get("selected")]
        called_rows = [row for row in api_rows if row.get("called")]
        validated_rows = [row for row in api_rows if str(row.get("validation_status") or "").startswith("validated_")]
        failed_rows = [row for row in api_rows if row.get("validation_status") == "validated_failed"]
        blocked_rows = [row for row in api_rows if row.get("validation_status") == "blocked"]
        if not selected_rows:
            readiness = "matrix_only"
            meaning = "仅展示能力矩阵；本次没有请求该领域接口，不能视为真实验证。"
        elif blocked_rows:
            readiness = "blocked"
            meaning = "本次任务被缺参或预检阻断，没有产生外部调用结果。"
        elif failed_rows and validated_rows:
            readiness = "partial_failed"
            meaning = "部分接口返回成功或空数据，至少一个接口失败；以 call_ledger 为准。"
        elif failed_rows:
            readiness = "failed"
            meaning = "已请求但接口失败；不得伪装成 verified。"
        elif len(called_rows) < len(selected_rows):
            readiness = "selected_not_called"
            meaning = "已被选择但缺少 call_ledger 结果；不得视为 verified。"
        elif len(validated_rows) == len(selected_rows):
            readiness = "validated"
            meaning = "本次选择的该领域接口都有 call_ledger 结果；success/empty 都只代表已验证调用状态。"
        elif validated_rows:
            readiness = "partial"
            meaning = "本次只验证了该领域的部分接口。"
        else:
            readiness = "unknown"
            meaning = "状态未知；不得进入交易判断。"
        target_rows.append(
            {
                "target": target_key,
                "label": label,
                "apis": list(apis),
                "selected_apis": [str(row.get("api")) for row in selected_rows],
                "called_api_count": len(called_rows),
                "selected_api_count": len(selected_rows),
                "validated_api_count": len(validated_rows),
                "failed_api_count": len(failed_rows),
                "blocked_api_count": len(blocked_rows),
                "readiness": readiness,
                "readiness_meaning": meaning,
                "cache_get_external_calls": False,
                "button_gated_external_calls_only": True,
                "does_not_claim_unselected_apis_verified": True,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return target_rows


def _validation_target_summary(target_rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in target_rows:
        readiness = str(row.get("readiness") or "unknown")
        counts[readiness] = counts.get(readiness, 0) + 1
    return {
        "status": "ready",
        "target_count": len(target_rows),
        "readiness_counts": counts,
        "validated_target_count": counts.get("validated", 0),
        "partial_or_failed_target_count": sum(counts.get(key, 0) for key in ("partial", "partial_failed", "failed", "blocked", "selected_not_called")),
        "matrix_only_target_count": counts.get("matrix_only", 0),
        "cache_get_external_calls": False,
        "button_gated_external_calls_only": True,
        "does_not_claim_unselected_apis_verified": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _safe_call_status(status: Any) -> bool:
    text = str(status or "")
    return text in ACCEPTANCE_SAFE_TERMINAL_STATUSES or text.startswith("blocked_")


def _has_sensitive_key(mapping: Any) -> bool:
    if not isinstance(mapping, Mapping):
        return False
    return any(any(marker in str(key).lower() for marker in SECRET_MARKERS) for key in mapping)


def _has_unsafe_error_text(value: Any) -> bool:
    text = str(value or "").lower()
    return any(marker in text for marker in SECRET_MARKERS) or any(marker in text for marker in STACK_MARKERS)


def _api_acceptance_audit_rows(api_validation_rows: list[dict[str, Any]], call_ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ledger_by_api = {str(row.get("api") or ""): row for row in call_ledger}
    rows: list[dict[str, Any]] = []
    for validation in api_validation_rows:
        api = str(validation.get("api") or "")
        ledger = ledger_by_api.get(api, {})
        selected = bool(validation.get("selected"))
        called = bool(validation.get("called"))
        call_status = str(validation.get("call_status") or "")
        validation_status = str(validation.get("validation_status") or "")
        validation_scope = str(validation.get("validation_scope") or "")
        failure_mode = str(validation.get("failure_mode") or ledger.get("failure_mode") or "unknown")
        failure_mode_status = str(validation.get("failure_mode_status") or ledger.get("failure_mode_status") or "unknown")
        missing_required_fields = [
            field
            for field in CALL_LEDGER_REQUIRED_FIELDS
            if called and field not in ledger
        ]
        unsafe_request_params = _has_sensitive_key(ledger.get("request_params_safe"))
        unsafe_error_message = _has_unsafe_error_text(ledger.get("error_message_safe"))
        false_verified = bool(not selected and (called or validation_status.startswith("validated_")))
        selected_missing_ledger = bool(selected and not called)
        false_parquet_claim = bool(
            not validation.get("parquet_enabled")
            and (
                validation.get("parquet_status") == "written"
                or int(validation.get("parquet_row_count") or 0) > 0
            )
        )
        invalid_call_status = bool(called and not _safe_call_status(call_status))
        failure_state_visible = bool(call_status == "failed" and validation_status == "validated_failed")
        blocked_state_visible = bool(call_status.startswith("blocked_") and validation_status == "blocked")
        empty_state_visible = bool(call_status == "empty" and validation_status == "validated_empty")
        success_state_visible = bool(call_status == "success" and validation_status == "validated_success")
        issue_count = sum(
            1
            for flag in (
                bool(missing_required_fields),
                unsafe_request_params,
                unsafe_error_message,
                false_verified,
                selected_missing_ledger,
                false_parquet_claim,
                invalid_call_status,
            )
            if flag
        )
        rows.append(
            {
                "api": api,
                "domain": validation.get("domain"),
                "group": validation.get("group"),
                "selected": selected,
                "called": called,
                "validation_status": validation_status,
                "validation_scope": validation_scope,
                "call_status": call_status,
                "failure_mode": failure_mode,
                "failure_mode_status": failure_mode_status,
                "safe_failure_mode_visible": bool(validation.get("safe_failure_mode_visible")),
                "row_count": int(validation.get("row_count") or 0),
                "data_date": validation.get("data_date"),
                "local_fetched_at": validation.get("local_fetched_at"),
                "missing_required_fields": missing_required_fields,
                "required_field_gap_count": len(missing_required_fields),
                "request_params_safe_has_secret_key": unsafe_request_params,
                "error_message_safe_has_unsafe_text": unsafe_error_message,
                "unselected_false_verified": false_verified,
                "selected_missing_call_ledger": selected_missing_ledger,
                "false_parquet_write_claim": false_parquet_claim,
                "invalid_call_status": invalid_call_status,
                "safe_failure_state_visible": failure_state_visible,
                "safe_blocked_state_visible": blocked_state_visible,
                "safe_empty_state_visible": empty_state_visible,
                "safe_success_state_visible": success_state_visible,
                "matrix_only_not_verified": bool(validation_scope == "capability_matrix_only" and not validation_status.startswith("validated_")),
                "safe_terminal_state": bool((not called and not selected) or (called and _safe_call_status(call_status))),
                "acceptance_issue_count": issue_count,
                "acceptance_status": "passed" if issue_count == 0 else "blocked",
                "acceptance_meaning": (
                    "call_ledger semantic audit passed; this does not promote the API to production data."
                    if issue_count == 0
                    else "call_ledger semantic audit found a blocker; do not treat this API as accepted."
                ),
                "audit_external_calls_triggered": False,
                "cache_get_external_calls": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _api_acceptance_audit(api_validation_rows: list[dict[str, Any]], call_ledger: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _api_acceptance_audit_rows(api_validation_rows, call_ledger)
    acceptance_issue_count = sum(int(row.get("acceptance_issue_count") or 0) for row in rows)
    selected_rows = [row for row in rows if row.get("selected")]
    called_rows = [row for row in rows if row.get("called")]
    matrix_only_rows = [row for row in rows if row.get("validation_scope") == "capability_matrix_only"]
    selected_missing_rows = [row for row in rows if row.get("selected_missing_call_ledger")]
    unsafe_param_rows = [row for row in rows if row.get("request_params_safe_has_secret_key")]
    unsafe_error_rows = [row for row in rows if row.get("error_message_safe_has_unsafe_text")]
    false_verified_rows = [row for row in rows if row.get("unselected_false_verified")]
    false_parquet_rows = [row for row in rows if row.get("false_parquet_write_claim")]
    required_gap_rows = [row for row in rows if int(row.get("required_field_gap_count") or 0) > 0]
    invalid_status_rows = [row for row in rows if row.get("invalid_call_status")]
    successful_selected_rows = [
        row
        for row in selected_rows
        if row.get("called")
        and row.get("call_status") == "success"
        and row.get("validation_status") == "validated_success"
        and int(row.get("row_count") or 0) > 0
    ]
    full_interface_acceptance_done = bool(
        len(selected_rows) == len(REFRESH_API_SPECS)
        and selected_rows
        and len(successful_selected_rows) == len(selected_rows)
        and acceptance_issue_count == 0
    )
    return {
        "schema_version": "tushare_api_acceptance_audit.v1",
        "status": "acceptance_audit_passed" if acceptance_issue_count == 0 else "acceptance_audit_blocked",
        "scope": "local_call_ledger_semantic_audit_not_provider_call",
        "api_count": len(rows),
        "selected_api_count": len(selected_rows),
        "called_api_count": len(called_rows),
        "matrix_only_api_count": len(matrix_only_rows),
        "selected_missing_call_ledger_count": len(selected_missing_rows),
        "required_field_gap_count": len(required_gap_rows),
        "unsafe_request_param_count": len(unsafe_param_rows),
        "unsafe_error_message_count": len(unsafe_error_rows),
        "false_verified_count": len(false_verified_rows),
        "false_parquet_write_claim_count": len(false_parquet_rows),
        "invalid_call_status_count": len(invalid_status_rows),
        "safe_success_state_count": len([row for row in rows if row.get("safe_success_state_visible")]),
        "safe_empty_state_count": len([row for row in rows if row.get("safe_empty_state_visible")]),
        "safe_failure_state_count": len([row for row in rows if row.get("safe_failure_state_visible")]),
        "safe_blocked_state_count": len([row for row in rows if row.get("safe_blocked_state_visible")]),
        "successful_selected_api_count": len(successful_selected_rows),
        "matrix_only_not_verified_count": len([row for row in matrix_only_rows if row.get("matrix_only_not_verified")]),
        "acceptance_issue_count": acceptance_issue_count,
        "selected_interfaces_have_call_ledger": not selected_missing_rows,
        "does_not_claim_unselected_apis_verified": not false_verified_rows,
        "safe_errors_redacted": not unsafe_error_rows,
        "safe_request_params": not unsafe_param_rows,
        "non_parquet_interfaces_do_not_claim_writes": not false_parquet_rows,
        "call_ledger_required_fields": list(CALL_LEDGER_REQUIRED_FIELDS),
        "full_interface_acceptance_done": full_interface_acceptance_done,
        "full_interface_acceptance_scope": "all declared APIs must be selected, called, and validated with non-empty successful samples before this can be true.",
        "provider_validation_done_in_this_task": any(row.get("external_calls_triggered") is True for row in call_ledger),
        "audit_external_calls_triggered": False,
        "cache_get_external_calls": False,
        "audit_calls_tushare": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
        "note": "This audit validates call_ledger semantics only. It does not call Tushare and does not convert matrix/preflight/mock states into production acceptance.",
    }


def _failure_mode_qa_contract(
    api_validation_rows: list[dict[str, Any]],
    call_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    observed_by_mode: dict[str, list[dict[str, Any]]] = {}
    for row in api_validation_rows:
        mode = str(row.get("failure_mode") or "unknown")
        observed_by_mode.setdefault(mode, []).append(row)
    rows: list[dict[str, Any]] = []
    for mode, label, acceptance_meaning in EXPECTED_FAILURE_MODE_QA:
        matching = observed_by_mode.get(mode, [])
        rows.append(
            {
                "mode": mode,
                "label": label,
                "status": "observed" if matching else "ready_not_observed",
                "matching_api_count": len(matching),
                "matching_apis": [str(row.get("api") or "") for row in matching],
                "acceptance_meaning": acceptance_meaning,
                "distinguishable": True,
                "does_not_mark_verified": mode != "success_non_empty",
                "cache_get_external_calls": False,
                "qa_external_calls_triggered": False,
                "tushare_called_by_qa": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    unsafe_rows = [
        row
        for row in call_ledger
        if _has_unsafe_error_text(row.get("error_message_safe")) or _has_sensitive_key(row.get("request_params_safe"))
    ]
    selected_rows = [row for row in api_validation_rows if row.get("selected")]
    called_rows = [row for row in api_validation_rows if row.get("called")]
    observed_modes = sorted(mode for mode, mode_rows in observed_by_mode.items() if mode_rows and mode != "none")
    return {
        "schema_version": "tushare_failure_mode_qa_contract.v1",
        "status": "failure_mode_qa_ready_provider_acceptance_pending" if not unsafe_rows else "failure_mode_qa_blocked",
        "scope": "local_call_ledger_failure_mode_classification_not_provider_acceptance",
        "selected_api_count": len(selected_rows),
        "called_api_count": len(called_rows),
        "observed_mode_count": len(observed_modes),
        "observed_modes": observed_modes,
        "permission_denied_distinguishable": True,
        "empty_result_or_no_record_distinguishable": True,
        "parse_failed_or_invalid_result_distinguishable": True,
        "missing_required_parameter_distinguishable": True,
        "provider_error_safe_distinguishable": True,
        "matrix_only_not_requested_distinguishable": True,
        "safe_error_text": not unsafe_rows,
        "unsafe_row_count": len(unsafe_rows),
        "provider_backed_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "qa_external_calls_triggered": False,
        "tushare_called_by_qa": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_count": len(rows),
        "rows": rows,
        "note": "Failure mode QA classifies existing call_ledger rows only. It does not call Tushare and does not prove provider-backed production acceptance.",
    }


def _provider_acceptance_readiness_row(
    criterion: str,
    status: str,
    passed: bool,
    *,
    evidence: str,
    production_blocker: bool = False,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "audit_external_calls_triggered": False,
        "cache_get_external_calls": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _provider_acceptance_readiness_audit(
    *,
    api_validation_rows: list[dict[str, Any]],
    validation_target_rows: list[dict[str, Any]],
    api_acceptance_audit: dict[str, Any],
) -> dict[str, Any]:
    api_count = len(api_validation_rows)
    selected_count = int(api_acceptance_audit.get("selected_api_count") or 0)
    matrix_only_count = int(api_acceptance_audit.get("matrix_only_api_count") or 0)
    successful_selected_count = int(api_acceptance_audit.get("successful_selected_api_count") or 0)
    acceptance_issue_count = int(api_acceptance_audit.get("acceptance_issue_count") or 0)
    validated_targets = [row for row in validation_target_rows if row.get("readiness") == "validated"]
    partial_or_blocked_targets = [
        row
        for row in validation_target_rows
        if row.get("readiness") in {"partial", "partial_failed", "failed", "blocked", "selected_not_called"}
    ]
    matrix_only_targets = [row for row in validation_target_rows if row.get("readiness") == "matrix_only"]
    all_apis_selected = bool(api_count and selected_count == api_count)
    all_selected_success_non_empty = bool(
        all_apis_selected
        and successful_selected_count == selected_count
        and selected_count > 0
    )
    all_targets_validated = bool(validation_target_rows and len(validated_targets) == len(validation_target_rows))
    semantic_audit_passed = api_acceptance_audit.get("status") == "acceptance_audit_passed" and acceptance_issue_count == 0
    no_secret_or_parquet_issues = bool(
        api_acceptance_audit.get("safe_errors_redacted")
        and api_acceptance_audit.get("safe_request_params")
        and api_acceptance_audit.get("non_parquet_interfaces_do_not_claim_writes")
    )
    provider_backed_acceptance_done = False
    rows = [
        _provider_acceptance_readiness_row(
            "post_task_button_gate",
            "passed",
            True,
            evidence="refresh pipeline is entered only from POST task; GET cache remains read-only.",
        ),
        _provider_acceptance_readiness_row(
            "call_ledger_semantic_audit",
            "passed" if semantic_audit_passed else "blocked",
            semantic_audit_passed,
            evidence=f"api_acceptance_audit={api_acceptance_audit.get('status')}; issues={acceptance_issue_count}",
            production_blocker=not semantic_audit_passed,
        ),
        _provider_acceptance_readiness_row(
            "all_declared_apis_selected",
            "passed" if all_apis_selected else "blocked",
            all_apis_selected,
            evidence=f"selected={selected_count}; declared={api_count}; matrix_only={matrix_only_count}",
            production_blocker=not all_apis_selected,
        ),
        _provider_acceptance_readiness_row(
            "all_selected_success_non_empty",
            "passed" if all_selected_success_non_empty else "blocked",
            all_selected_success_non_empty,
            evidence=f"successful_non_empty={successful_selected_count}; selected={selected_count}",
            production_blocker=not all_selected_success_non_empty,
        ),
        _provider_acceptance_readiness_row(
            "all_target_groups_validated",
            "passed" if all_targets_validated else "blocked",
            all_targets_validated,
            evidence=f"validated_targets={len(validated_targets)}; target_count={len(validation_target_rows)}; matrix_only_targets={len(matrix_only_targets)}; partial_or_blocked_targets={len(partial_or_blocked_targets)}",
            production_blocker=not all_targets_validated,
        ),
        _provider_acceptance_readiness_row(
            "provider_backed_acceptance_evidence",
            "blocked",
            provider_backed_acceptance_done,
            evidence="provider_backed_acceptance_done=false; local/fake adapter and semantic audit evidence are not production provider acceptance.",
            production_blocker=True,
        ),
        _provider_acceptance_readiness_row(
            "safe_params_errors_and_parquet_scope",
            "passed" if no_secret_or_parquet_issues else "blocked",
            no_secret_or_parquet_issues,
            evidence=(
                f"safe_request_params={api_acceptance_audit.get('safe_request_params')}; "
                f"safe_errors_redacted={api_acceptance_audit.get('safe_errors_redacted')}; "
                f"non_parquet_interfaces_do_not_claim_writes={api_acceptance_audit.get('non_parquet_interfaces_do_not_claim_writes')}"
            ),
            production_blocker=not no_secret_or_parquet_issues,
        ),
        _provider_acceptance_readiness_row(
            "trade_and_action_boundary",
            "passed",
            True,
            evidence="refresh packet remains no-trade and does_not_modify_strategy_action=true.",
        ),
    ]
    blocker_count = sum(1 for row in rows if row.get("production_blocker"))
    return {
        "schema_version": "tushare_provider_acceptance_readiness_audit.v1",
        "status": "provider_acceptance_pending" if blocker_count else "provider_acceptance_ready",
        "scope": "local_readiness_not_provider_backed_full_interface_acceptance",
        "api_count": api_count,
        "selected_api_count": selected_count,
        "matrix_only_api_count": matrix_only_count,
        "successful_selected_api_count": successful_selected_count,
        "target_count": len(validation_target_rows),
        "validated_target_count": len(validated_targets),
        "matrix_only_target_count": len(matrix_only_targets),
        "partial_or_blocked_target_count": len(partial_or_blocked_targets),
        "semantic_acceptance_audit_passed": semantic_audit_passed,
        "full_interface_acceptance_done": bool(api_acceptance_audit.get("full_interface_acceptance_done")),
        "provider_backed_acceptance_done": provider_backed_acceptance_done,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "audit_external_calls_triggered": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "production_blocker_count": blocker_count,
        "rows": rows,
        "note": "This readiness audit keeps provider acceptance pending until all declared APIs have real non-empty provider samples and target groups are validated by an explicit production acceptance run.",
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


def _required_preflight_params(api: str) -> list[str]:
    params = list(REFRESH_API_SPECS[api].get("params") or [])
    return ["ts_code"] if "ts_code" in params else []


def _request_parameter_qa_contract(selected_apis: Iterable[str], payload: Any) -> dict[str, Any]:
    selected_set = set(selected_apis)
    safe_payload = _safe_payload(payload)
    raw_payload_has_sensitive_key = _has_sensitive_key(payload)
    rows: list[dict[str, Any]] = []
    for api, spec in REFRESH_API_SPECS.items():
        declared_params = list(spec.get("params") or [])
        params = _request_params_for_api(api, payload)
        selected = api in selected_set
        required_preflight = _required_preflight_params(api)
        missing_required = [key for key in required_preflight if not params.get(key)]
        provided_param_keys = sorted(params)
        date_context_params = [key for key in declared_params if key in DATE_CONTEXT_PARAMS]
        provided_date_context = [key for key in date_context_params if key in params]
        alias_used = bool(
            "ts_code" in params
            and (
                ("ticker" in safe_payload and safe_payload.get("ticker") == params.get("ts_code"))
                or ("symbol" in safe_payload and safe_payload.get("symbol") == params.get("ts_code"))
            )
        )
        unsafe_request_params = _has_sensitive_key(params)
        if not selected:
            status = "matrix_only"
        elif missing_required:
            status = "preflight_blocked_missing_required_param"
        elif unsafe_request_params:
            status = "blocked_unsafe_request_params"
        else:
            status = "request_params_safe"
        rows.append(
            {
                "api": api,
                "domain": _api_domain(api),
                "method": spec.get("method"),
                "selected": selected,
                "status": status,
                "declared_param_keys": declared_params,
                "provided_param_keys": provided_param_keys,
                "required_preflight_params": required_preflight,
                "missing_required_preflight_params": missing_required,
                "date_context_params": date_context_params,
                "provided_date_context_params": provided_date_context,
                "date_context_present": bool(provided_date_context),
                "ts_code_alias_supported": alias_used,
                "request_params_safe_has_secret_key": unsafe_request_params,
                "raw_payload_sensitive_keys_dropped": raw_payload_has_sensitive_key,
                "payload_control_keys": [key for key in PAYLOAD_CONTROL_KEYS if key in safe_payload],
                "provider_acceptance_requirement": (
                    "provider-backed acceptance must verify the exact interface-specific ts_code/date/period window and row_count semantics; this local contract does not call Tushare."
                ),
                "cache_get_external_calls": False,
                "qa_external_calls_triggered": False,
                "tushare_called_by_qa": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    selected_rows = [row for row in rows if row.get("selected")]
    missing_required_rows = [row for row in selected_rows if row.get("missing_required_preflight_params")]
    unsafe_param_rows = [row for row in selected_rows if row.get("request_params_safe_has_secret_key")]
    selected_with_date_context = [row for row in selected_rows if row.get("date_context_present")]
    matrix_only_rows = [row for row in rows if row.get("status") == "matrix_only"]
    return {
        "schema_version": "tushare_request_parameter_qa_contract.v1",
        "status": "request_parameter_qa_ready_provider_acceptance_pending"
        if not unsafe_param_rows
        else "request_parameter_qa_blocked",
        "scope": "local_request_parameter_contract_not_provider_call",
        "api_count": len(rows),
        "selected_api_count": len(selected_rows),
        "matrix_only_api_count": len(matrix_only_rows),
        "missing_required_preflight_api_count": len(missing_required_rows),
        "unsafe_request_param_api_count": len(unsafe_param_rows),
        "selected_with_date_context_count": len(selected_with_date_context),
        "raw_payload_sensitive_keys_dropped": raw_payload_has_sensitive_key,
        "safe_payload_key_count": len(safe_payload),
        "preflight_required_param_policy": "current local preflight blocks missing ts_code only; date windows are contract-visible and required for provider-backed production acceptance.",
        "date_context_params": list(DATE_CONTEXT_PARAMS),
        "provider_backed_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "qa_external_calls_triggered": False,
        "tushare_called_by_qa": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_count": len(rows),
        "rows": rows,
        "note": "Request parameter QA validates local safe parameter contracts only. It does not call Tushare and does not prove provider-backed production acceptance.",
    }


def _provider_target_sample_plan_contract(
    *,
    selected_apis: Iterable[str],
    payload: Any,
    api_validation_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_set = set(selected_apis)
    validation_by_api = {str(row.get("api") or ""): row for row in api_validation_rows}
    safe_payload = _safe_payload(payload)
    if "ticker" in safe_payload and "ts_code" not in safe_payload:
        safe_payload["ts_code"] = safe_payload["ticker"]
    if "symbol" in safe_payload and "ts_code" not in safe_payload:
        safe_payload["ts_code"] = safe_payload["symbol"]
    provided_context_fields = sorted(
        key
        for key, value in safe_payload.items()
        if key in {"ts_code", "trade_date", "start_date", "end_date", "ann_date", "period", "float_date", "limit_type"}
        and value not in (None, "")
    )

    rows: list[dict[str, Any]] = []
    for target_key, label, apis in VALIDATION_TARGET_GROUPS:
        requirement = PROVIDER_TARGET_SAMPLE_REQUIREMENTS[target_key]
        target_apis = list(apis)
        selected_target_apis = [api for api in target_apis if api in selected_set]
        missing_target_apis = [api for api in target_apis if api not in selected_set]
        target_validation_rows = [validation_by_api[api] for api in target_apis if api in validation_by_api]
        selected_rows = [row for row in target_validation_rows if row.get("selected")]
        called_rows = [row for row in selected_rows if row.get("called")]
        non_empty_success_rows = [
            row
            for row in selected_rows
            if row.get("call_status") == "success" and int(row.get("row_count") or 0) > 0
        ]
        empty_or_failed_rows = [
            row
            for row in selected_rows
            if row.get("call_status") in {"empty", "failed"} or str(row.get("call_status") or "").startswith("blocked_")
        ]
        missing_required_rows = [
            row
            for row in selected_rows
            if str(row.get("call_status") or "").startswith("blocked_missing_")
            or row.get("failure_mode") == "missing_required_parameter"
        ]
        missing_context_groups = [
            " or ".join(group)
            for group in requirement["context_groups"]
            if not any(field in provided_context_fields for field in group)
        ]
        if not selected_target_apis:
            plan_status = "matrix_only_plan_pending"
            plan_meaning = "本次没有选择该目标域接口；只展示未来 provider 样本验收计划。"
        elif missing_target_apis:
            plan_status = "partial_selection_plan_pending"
            plan_meaning = "只选择了该目标域部分接口；未来真实验收必须覆盖该目标域全部接口。"
        elif missing_required_rows:
            plan_status = "blocked_missing_required_params"
            plan_meaning = "本次选择存在 ts_code 等必需参数缺口；不能进入真实 provider 样本验收。"
        elif missing_context_groups:
            plan_status = "sample_window_context_pending"
            plan_meaning = "接口已选择且必需预检参数安全，但还缺真实样本窗口上下文。"
        else:
            plan_status = "ready_to_execute_provider_sample"
            plan_meaning = "本地计划认为该目标域具备未来按钮任务验收所需参数上下文；仍需真实 provider-backed 样本证明。"
        rows.append(
            {
                "target": target_key,
                "label": label,
                "apis": target_apis,
                "selected_apis": selected_target_apis,
                "missing_target_apis": missing_target_apis,
                "sample_window": requirement["sample_window"],
                "required_context_groups": [" or ".join(group) for group in requirement["context_groups"]],
                "provided_context_fields": provided_context_fields,
                "missing_context_groups": missing_context_groups,
                "required_success_evidence": list(requirement["required_success_evidence"]),
                "required_failure_evidence": list(requirement["required_failure_evidence"]),
                "called_api_count": len(called_rows),
                "non_empty_success_api_count": len(non_empty_success_rows),
                "empty_or_failed_api_count": len(empty_or_failed_rows),
                "missing_required_param_api_count": len(missing_required_rows),
                "all_target_apis_selected": not missing_target_apis and bool(selected_target_apis),
                "provider_sample_plan_status": plan_status,
                "provider_sample_plan_meaning": plan_meaning,
                "provider_backed_acceptance_done": False,
                "provider_sample_acceptance_status": "provider_execution_pending",
                "production_tushare_pipeline_complete": False,
                "cache_get_external_calls": False,
                "plan_external_calls_triggered": False,
                "tushare_called_by_plan": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    status_counts: dict[str, int] = {}
    for row in rows:
        row_status = str(row.get("provider_sample_plan_status") or "unknown")
        status_counts[row_status] = status_counts.get(row_status, 0) + 1
    ready_count = status_counts.get("ready_to_execute_provider_sample", 0)
    blocked_count = sum(
        status_counts.get(key, 0)
        for key in (
            "matrix_only_plan_pending",
            "partial_selection_plan_pending",
            "blocked_missing_required_params",
            "sample_window_context_pending",
        )
    )
    return {
        "schema_version": "tushare_provider_target_sample_plan_contract.v1",
        "status": "local_plan_ready_provider_execution_pending",
        "scope": "local_target_sample_plan_not_provider_call",
        "target_count": len(rows),
        "ready_to_execute_target_count": ready_count,
        "pending_or_blocked_target_count": blocked_count,
        "status_counts": status_counts,
        "selected_api_count": len(selected_set),
        "declared_api_count": len(REFRESH_API_SPECS),
        "provider_backed_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "plan_external_calls_triggered": False,
        "tushare_called_by_plan": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_count": len(rows),
        "rows": rows,
        "note": "Provider target sample plan declares future real Tushare sample requirements only. It does not call Tushare and does not prove provider-backed acceptance.",
    }


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
    raw_error = result.get("error") if isinstance(result, Mapping) else "invalid_tushare_result"
    error = "" if ok else _safe_text(raw_error)
    if ok and row_count > 0:
        call_status = "success"
        failure_mode = "none"
    elif ok:
        call_status = "empty"
        failure_mode = "empty_result_or_no_record"
    else:
        call_status = "failed"
        failure_mode = _failure_mode_from_error(raw_error)
    return {
        "api": api,
        "request_params_safe": params,
        "row_count": row_count,
        "data_date": _data_date(rows),
        "local_fetched_at": now,
        "call_status": call_status,
        "failure_mode": failure_mode,
        "failure_mode_status": _failure_mode_status(failure_mode),
        "safe_failure_mode_visible": True,
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
    failure_mode = "missing_required_parameter"
    return {
        "api": api,
        "request_params_safe": params,
        "row_count": 0,
        "data_date": None,
        "local_fetched_at": now,
        "call_status": f"blocked_missing_{missing_param}",
        "failure_mode": failure_mode,
        "failure_mode_status": _failure_mode_status(failure_mode),
        "safe_failure_mode_visible": True,
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
    if task.get("dedupe_reused_existing"):
        return task
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
    validation_target_rows = _validation_target_rows(api_validation_rows)
    validation_target_summary = _validation_target_summary(validation_target_rows)
    api_acceptance_audit = _api_acceptance_audit(api_validation_rows, call_ledger)
    failure_mode_qa_contract = _failure_mode_qa_contract(api_validation_rows, call_ledger)
    request_parameter_qa_contract = _request_parameter_qa_contract(selected_apis, payload)
    provider_target_sample_plan_contract = _provider_target_sample_plan_contract(
        selected_apis=selected_apis,
        payload=payload,
        api_validation_rows=api_validation_rows,
    )
    provider_acceptance_readiness_audit = _provider_acceptance_readiness_audit(
        api_validation_rows=api_validation_rows,
        validation_target_rows=validation_target_rows,
        api_acceptance_audit=api_acceptance_audit,
    )
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
        "api_validation_target_rows": validation_target_rows,
        "api_validation_target_summary": validation_target_summary,
        "api_acceptance_audit": api_acceptance_audit,
        "api_acceptance_audit_rows": api_acceptance_audit["rows"],
        "api_acceptance_audit_status": api_acceptance_audit["status"],
        "failure_mode_qa_contract": failure_mode_qa_contract,
        "failure_mode_qa_rows": failure_mode_qa_contract["rows"],
        "failure_mode_qa_status": failure_mode_qa_contract["status"],
        "request_parameter_qa_contract": request_parameter_qa_contract,
        "request_parameter_qa_rows": request_parameter_qa_contract["rows"],
        "request_parameter_qa_status": request_parameter_qa_contract["status"],
        "provider_target_sample_plan_contract": provider_target_sample_plan_contract,
        "provider_target_sample_plan_rows": provider_target_sample_plan_contract["rows"],
        "provider_target_sample_plan_status": provider_target_sample_plan_contract["status"],
        "provider_acceptance_readiness_audit": provider_acceptance_readiness_audit,
        "provider_acceptance_readiness_rows": provider_acceptance_readiness_audit["rows"],
        "provider_acceptance_readiness_status": provider_acceptance_readiness_audit["status"],
        "api_validation_matrix_policy": {
            "scope": "selected APIs use real task call_ledger; unselected APIs are capability matrix only.",
            "selected_apis": list(selected_apis),
            "matrix_only_apis": [row["api"] for row in api_validation_rows if row.get("validation_scope") == "capability_matrix_only"],
            "target_readiness_scope": "目标领域 readiness 只汇总本次按钮任务的 call_ledger；matrix_only 不代表真实验证。",
            "acceptance_audit_scope": "api_acceptance_audit 只审计 call_ledger 语义和安全边界，不发起 provider 调用。",
            "provider_acceptance_readiness_scope": "provider_acceptance_readiness_audit 只汇总生产验收阻断项；不把 fake/local/matrix 证据当 provider-backed acceptance。",
            "failure_mode_qa_scope": "failure_mode_qa_contract 只分类现有 call_ledger 的 empty/permission/parse/missing-param/provider-error 状态；不发起 provider 调用。",
            "request_parameter_qa_scope": "request_parameter_qa_contract 只审计安全参数、ts_code 预检和日期上下文字段；不发起 provider 调用。",
            "provider_target_sample_plan_scope": "provider_target_sample_plan_contract 只声明未来真实样本验收所需目标域、接口、窗口上下文和证据；不发起 provider 调用。",
            "call_ledger_required_fields": list(CALL_LEDGER_REQUIRED_FIELDS),
            "cache_get_external_calls": False,
            "button_gated_external_calls_only": True,
            "does_not_claim_unselected_apis_verified": True,
            "full_interface_acceptance_done": api_acceptance_audit["full_interface_acceptance_done"],
            "provider_backed_acceptance_done": provider_acceptance_readiness_audit["provider_backed_acceptance_done"],
            "production_tushare_pipeline_complete": provider_acceptance_readiness_audit["production_tushare_pipeline_complete"],
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
        "api_acceptance_issue_count": api_acceptance_audit["acceptance_issue_count"],
        "api_acceptance_audit_passed": api_acceptance_audit["status"] == "acceptance_audit_passed",
        "failure_mode_qa_observed_mode_count": failure_mode_qa_contract["observed_mode_count"],
        "failure_mode_qa_unsafe_row_count": failure_mode_qa_contract["unsafe_row_count"],
        "request_parameter_qa_missing_required_count": request_parameter_qa_contract["missing_required_preflight_api_count"],
        "request_parameter_qa_unsafe_param_count": request_parameter_qa_contract["unsafe_request_param_api_count"],
        "full_interface_acceptance_done": api_acceptance_audit["full_interface_acceptance_done"],
        "provider_target_sample_plan_ready_count": provider_target_sample_plan_contract["ready_to_execute_target_count"],
        "provider_target_sample_plan_pending_count": provider_target_sample_plan_contract["pending_or_blocked_target_count"],
        "provider_acceptance_production_blocker_count": provider_acceptance_readiness_audit["production_blocker_count"],
        "provider_backed_acceptance_done": provider_acceptance_readiness_audit["provider_backed_acceptance_done"],
        "production_tushare_pipeline_complete": provider_acceptance_readiness_audit["production_tushare_pipeline_complete"],
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
