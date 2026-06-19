from __future__ import annotations

import datetime as _dt
import hashlib
import json
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
TUSHARE_DURABLE_EVIDENCE_SCHEMA_VERSION = "tushare_durable_evidence_recipe.v1"
TUSHARE_DURABLE_EVIDENCE_KEYS = (
    "post_task_route_and_mode_gate",
    "core_light_api_revalidation",
    "trade_calendar_provider_sample",
    "margin_financing_provider_sample",
    "dragon_tiger_provider_sample",
    "limit_emotion_provider_sample",
    "chip_distribution_provider_sample",
    "financial_disclosure_provider_sample",
    "hard_risk_provider_sample",
    "safe_provider_call_ledger",
    "failure_mode_and_parameter_review",
    "full_interface_promotion_review",
    "storage_cache_promotion_review",
)
TUSHARE_DURABLE_EVIDENCE_LABELS = {
    "post_task_route_and_mode_gate": "POST task route and runtime mode gate",
    "core_light_api_revalidation": "core light API release revalidation",
    "trade_calendar_provider_sample": "trade_cal provider target sample",
    "margin_financing_provider_sample": "margin financing provider target sample",
    "dragon_tiger_provider_sample": "dragon-tiger provider target sample",
    "limit_emotion_provider_sample": "limit/emotion provider target sample",
    "chip_distribution_provider_sample": "chip distribution provider target sample",
    "financial_disclosure_provider_sample": "financial disclosure provider target sample",
    "hard_risk_provider_sample": "hard-risk provider target sample",
    "safe_provider_call_ledger": "safe provider call ledger",
    "failure_mode_and_parameter_review": "failure-mode and parameter review",
    "full_interface_promotion_review": "full-interface promotion review",
    "storage_cache_promotion_review": "storage/cache promotion review",
}
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
TRADE_CAL_PROVIDER_ACCEPTANCE_MODE = "provider_backed_trade_cal_long_window"
PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE = "provider_target_sample_acceptance"
PROVIDER_TARGET_SAMPLE_EXECUTION_REQUEST_SCHEMA_VERSION = "tushare_provider_target_sample_execution_request.v1"
PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_SEED_SCHEMA_VERSION = "tushare_provider_target_sample_execution_recipe_seed.v1"
PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_SEED_TASK_TYPE = "run_tushare_provider_target_sample_execution_recipe_seed"
PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_SEED_ROUTE = "POST /api/tasks/tushare-provider-target-sample-execution-recipe-seed"
PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_PACKET_KEY = "command_center_tushare_provider_target_sample_execution_recipe_packet"
PROVIDER_TARGET_SAMPLE_EXECUTION_REQUEST_TASK_TYPE = "run_tushare_provider_target_sample_execution_request"
PROVIDER_TARGET_SAMPLE_EXECUTION_REQUEST_ROUTE = "POST /api/tasks/tushare-provider-target-sample-execution-request"
TRADE_CAL_PROVIDER_ACCEPTANCE_MIN_WINDOW_DAYS = 730
TRADE_CAL_PROVIDER_ACCEPTANCE_MIN_FAILURE_MODES = len(EXPECTED_FAILURE_MODE_QA)
TRADE_CAL_PROVIDER_ACCEPTANCE_MIN_REPLAY_SCENARIOS = 8
TRADE_CAL_PROVIDER_ACCEPTANCE_MAX_ROWS = 10000
PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MIN_FAILURE_MODES = len(EXPECTED_FAILURE_MODE_QA)
PROVIDER_TARGET_SAMPLE_ACCEPTANCE_GROUP_KEYS = (
    "target_sample_acceptance_groups",
    "target_sample_groups",
    "provider_target_groups",
    "validation_target_groups",
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


def _provider_acceptance_promotion_row(
    criterion: str,
    passed: bool,
    *,
    evidence: str,
    required_for_promotion: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "required_for_promotion": bool(required_for_promotion),
        "evidence": evidence,
        "audit_external_calls_triggered": False,
        "cache_get_external_calls": False,
        "tushare_called_by_audit": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _provider_acceptance_promotion_audit(
    *,
    api_validation_rows: list[dict[str, Any]],
    validation_target_rows: list[dict[str, Any]],
    api_acceptance_audit: dict[str, Any],
    provider_target_sample_plan_contract: dict[str, Any],
    provider_acceptance_readiness_audit: dict[str, Any],
    call_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_rows = [row for row in api_validation_rows if row.get("selected")]
    matrix_only_rows = [row for row in api_validation_rows if row.get("validation_scope") == "capability_matrix_only"]
    success_non_empty_rows = [
        row
        for row in selected_rows
        if row.get("call_status") == "success" and int(row.get("row_count") or 0) > 0
    ]
    validated_targets = [row for row in validation_target_rows if row.get("readiness") == "validated"]
    target_count = len(validation_target_rows)
    api_count = len(api_validation_rows)
    all_declared_selected = bool(api_count and len(selected_rows) == api_count and not matrix_only_rows)
    all_success_non_empty = bool(all_declared_selected and len(success_non_empty_rows) == api_count)
    all_targets_validated = bool(target_count and len(validated_targets) == target_count)
    semantic_audit_passed = bool(
        api_acceptance_audit.get("status") == "acceptance_audit_passed"
        and int(api_acceptance_audit.get("acceptance_issue_count") or 0) == 0
    )
    safe_boundaries = bool(
        api_acceptance_audit.get("safe_request_params")
        and api_acceptance_audit.get("safe_errors_redacted")
        and api_acceptance_audit.get("non_parquet_interfaces_do_not_claim_writes")
    )
    target_sample_plan_complete = bool(
        provider_target_sample_plan_contract.get("ready_to_execute_target_count") == target_count
        and int(provider_target_sample_plan_contract.get("pending_or_blocked_target_count") or 0) == 0
    )
    explicit_provider_marker = any(
        row.get("provider_backed_acceptance_done") is True
        or row.get("provider_backed_full_interface_acceptance_done") is True
        or row.get("production_tushare_pipeline_complete") is True
        or row.get("provider_acceptance_marker") == "provider_backed_full_interface_acceptance"
        for row in call_ledger
    )
    failure_mode_evidence = any(
        row.get("failure_mode_acceptance_done") is True
        or int(row.get("failure_mode_validated_count") or 0) >= len(EXPECTED_FAILURE_MODE_QA)
        for row in call_ledger
    )
    provider_evidence_rows = [
        row
        for row in call_ledger
        if row.get("external_calls_triggered") is True
        and row.get("tushare_called") is True
        and row.get("call_status") == "success"
        and int(row.get("row_count") or 0) > 0
    ]
    rows = [
        _provider_acceptance_promotion_row(
            "all_declared_apis_selected",
            all_declared_selected,
            evidence=f"selected={len(selected_rows)}; declared={api_count}; matrix_only={len(matrix_only_rows)}",
        ),
        _provider_acceptance_promotion_row(
            "all_declared_apis_success_non_empty",
            all_success_non_empty,
            evidence=f"success_non_empty={len(success_non_empty_rows)}; declared={api_count}",
        ),
        _provider_acceptance_promotion_row(
            "all_target_groups_validated",
            all_targets_validated,
            evidence=f"validated_targets={len(validated_targets)}; target_count={target_count}",
        ),
        _provider_acceptance_promotion_row(
            "call_ledger_semantic_audit_passed",
            semantic_audit_passed,
            evidence=f"api_acceptance_audit={api_acceptance_audit.get('status')}; issues={api_acceptance_audit.get('acceptance_issue_count')}",
        ),
        _provider_acceptance_promotion_row(
            "safe_params_errors_and_parquet_scope",
            safe_boundaries,
            evidence=(
                f"safe_request_params={api_acceptance_audit.get('safe_request_params')}; "
                f"safe_errors_redacted={api_acceptance_audit.get('safe_errors_redacted')}; "
                f"non_parquet_interfaces_do_not_claim_writes={api_acceptance_audit.get('non_parquet_interfaces_do_not_claim_writes')}"
            ),
        ),
        _provider_acceptance_promotion_row(
            "target_sample_plan_has_no_pending_groups",
            target_sample_plan_complete,
            evidence=(
                f"ready_targets={provider_target_sample_plan_contract.get('ready_to_execute_target_count')}; "
                f"pending_targets={provider_target_sample_plan_contract.get('pending_or_blocked_target_count')}"
            ),
        ),
        _provider_acceptance_promotion_row(
            "explicit_provider_backed_acceptance_marker",
            explicit_provider_marker,
            evidence="Provider-backed production acceptance requires an explicit marker from the acceptance run.",
        ),
        _provider_acceptance_promotion_row(
            "failure_mode_acceptance_evidence",
            failure_mode_evidence,
            evidence="Permission, empty/no-record, parse, missing-parameter, provider-error, and success modes must be evidenced before promotion.",
        ),
        _provider_acceptance_promotion_row(
            "readiness_audit_still_local",
            provider_acceptance_readiness_audit.get("schema_version")
            == "tushare_provider_acceptance_readiness_audit.v1"
            and provider_acceptance_readiness_audit.get("audit_external_calls_triggered") is False
            and provider_acceptance_readiness_audit.get("provider_backed_acceptance_done") is False,
            evidence="Provider readiness is a local blocker audit; it cannot promote provider-backed acceptance by itself.",
            required_for_promotion=False,
        ),
        _provider_acceptance_promotion_row(
            "trade_and_action_boundary",
            True,
            evidence="Promotion audit never executes trades and never mutates strategy action.",
            required_for_promotion=False,
        ),
    ]
    blockers = [row["criterion"] for row in rows if row["required_for_promotion"] and not row["passed"]]
    promotion_ready = not blockers
    return {
        "schema_version": "tushare_provider_acceptance_promotion_audit.v1",
        "status": "provider_acceptance_promotion_ready" if promotion_ready else "provider_acceptance_promotion_pending",
        "scope": "local_call_ledger_promotion_audit_no_provider_execution",
        "promotion_ready": promotion_ready,
        "provider_backed_acceptance_done": promotion_ready,
        "production_tushare_pipeline_complete": False,
        "api_count": api_count,
        "selected_api_count": len(selected_rows),
        "matrix_only_api_count": len(matrix_only_rows),
        "success_non_empty_api_count": len(success_non_empty_rows),
        "target_count": target_count,
        "validated_target_count": len(validated_targets),
        "target_sample_plan_complete": target_sample_plan_complete,
        "explicit_provider_marker_found": explicit_provider_marker,
        "failure_mode_evidence_done": failure_mode_evidence,
        "provider_evidence_row_count": len(provider_evidence_rows),
        "semantic_acceptance_audit_passed": semantic_audit_passed,
        "safe_boundaries": safe_boundaries,
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "rows": rows,
        "cache_get_external_calls": False,
        "audit_external_calls_triggered": False,
        "tushare_called_by_audit": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This promotion audit reads existing call_ledger evidence only. Matrix rows, local QA, fake adapter samples, and readiness audits cannot promote provider-backed acceptance without explicit full-interface evidence.",
    }


def _provider_evidence_gap_row(
    *,
    target: str,
    label: str,
    apis: list[str],
    selected_apis: list[str],
    missing_required_apis: list[str],
    missing_call_ledger_apis: list[str],
    non_empty_success_apis: list[str],
    validated_empty_apis: list[str],
    failed_or_blocked_apis: list[str],
    validation_readiness: str,
    sample_plan_status: str,
    promotion_ready: bool,
    failure_mode_evidence_done: bool,
    target_sample_acceptance_status: str,
    target_sample_acceptance_ready_for_review: bool,
    target_sample_acceptance_blockers: list[str],
    required_success_evidence: list[str],
    required_failure_evidence: list[str],
) -> dict[str, Any]:
    blockers: list[str] = []
    if not selected_apis:
        blockers.append("target_api_selection_missing")
    if missing_required_apis:
        blockers.append("target_api_selection_incomplete")
    if missing_call_ledger_apis:
        blockers.append("call_ledger_evidence_missing")
    if not non_empty_success_apis:
        blockers.append("non_empty_success_sample_missing")
    if validation_readiness != "validated":
        blockers.append("target_validation_not_complete")
    if sample_plan_status != "ready_to_execute_provider_sample":
        blockers.append("provider_sample_plan_not_ready")
    if not failure_mode_evidence_done:
        blockers.append("failure_mode_evidence_missing")
    if not promotion_ready:
        blockers.append("provider_promotion_not_ready")
    if not blockers:
        gap_status = "provider_evidence_gap_review_ready"
    elif target_sample_acceptance_ready_for_review and blockers == ["provider_promotion_not_ready"]:
        gap_status = "target_sample_ready_promotion_pending"
    elif not selected_apis:
        gap_status = "matrix_only_gap_pending"
    elif missing_required_apis:
        gap_status = "partial_selection_gap_pending"
    elif missing_call_ledger_apis:
        gap_status = "call_ledger_gap_pending"
    elif failed_or_blocked_apis:
        gap_status = "failed_or_blocked_evidence_gap_pending"
    elif not non_empty_success_apis:
        gap_status = "non_empty_sample_gap_pending"
    else:
        gap_status = "provider_acceptance_gap_pending"
    return {
        "target": target,
        "label": label,
        "apis": apis,
        "selected_apis": selected_apis,
        "missing_required_apis": missing_required_apis,
        "missing_call_ledger_apis": missing_call_ledger_apis,
        "non_empty_success_apis": non_empty_success_apis,
        "validated_empty_apis": validated_empty_apis,
        "failed_or_blocked_apis": failed_or_blocked_apis,
        "validation_readiness": validation_readiness,
        "sample_plan_status": sample_plan_status,
        "gap_status": gap_status,
        "gap_blockers": blockers,
        "gap_blocker_count": len(blockers),
        "required_success_evidence": required_success_evidence,
        "required_failure_evidence": required_failure_evidence,
        "provider_promotion_ready": promotion_ready,
        "failure_mode_evidence_done": failure_mode_evidence_done,
        "target_sample_acceptance_status": target_sample_acceptance_status,
        "target_sample_acceptance_ready_for_review": target_sample_acceptance_ready_for_review,
        "target_sample_acceptance_blockers": target_sample_acceptance_blockers,
        "target_sample_review_ready_not_promotion": bool(target_sample_acceptance_ready_for_review and not promotion_ready),
        "provider_backed_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "audit_external_calls_triggered": False,
        "tushare_called_by_audit": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _provider_evidence_gap_audit(
    *,
    api_validation_rows: list[dict[str, Any]],
    validation_target_rows: list[dict[str, Any]],
    provider_target_sample_plan_contract: dict[str, Any],
    provider_acceptance_promotion_audit: dict[str, Any],
    call_ledger: list[dict[str, Any]],
    provider_target_sample_acceptance_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation_by_api = {str(row.get("api") or ""): row for row in api_validation_rows}
    target_by_key = {str(row.get("target") or ""): row for row in validation_target_rows}
    sample_plan_by_target = {
        str(row.get("target") or ""): row for row in provider_target_sample_plan_contract.get("rows", [])
    }
    target_sample_acceptance_contract = provider_target_sample_acceptance_contract or {}
    target_sample_acceptance_by_target = {
        str(row.get("target") or ""): row for row in target_sample_acceptance_contract.get("rows", [])
        if isinstance(row, Mapping)
    }
    ledger_by_api = {str(row.get("api") or ""): row for row in call_ledger}
    promotion_ready = bool(provider_acceptance_promotion_audit.get("promotion_ready"))
    failure_mode_evidence_done = bool(provider_acceptance_promotion_audit.get("failure_mode_evidence_done"))

    rows: list[dict[str, Any]] = []
    for target_key, label, apis in VALIDATION_TARGET_GROUPS:
        target_apis = list(apis)
        api_rows = [validation_by_api[api] for api in target_apis if api in validation_by_api]
        selected_apis = [str(row.get("api")) for row in api_rows if row.get("selected")]
        missing_required_apis = [api for api in target_apis if api not in selected_apis]
        missing_call_ledger_apis = [
            api for api in selected_apis if api not in ledger_by_api or not validation_by_api.get(api, {}).get("called")
        ]
        non_empty_success_apis = [
            str(row.get("api"))
            for row in api_rows
            if row.get("call_status") == "success" and int(row.get("row_count") or 0) > 0
        ]
        validated_empty_apis = [str(row.get("api")) for row in api_rows if row.get("call_status") == "empty"]
        failed_or_blocked_apis = [
            str(row.get("api"))
            for row in api_rows
            if row.get("call_status") == "failed" or str(row.get("call_status") or "").startswith("blocked_")
        ]
        target_row = target_by_key.get(target_key, {})
        sample_plan_row = sample_plan_by_target.get(target_key, {})
        target_sample_acceptance_row = target_sample_acceptance_by_target.get(target_key, {})
        target_sample_acceptance_status = str(
            target_sample_acceptance_row.get("target_sample_acceptance_status")
            or "target_sample_acceptance_not_requested"
        )
        target_sample_acceptance_ready = (
            target_sample_acceptance_status == "target_sample_acceptance_ready_for_review"
        )
        target_failure_mode_evidence_done = bool(
            failure_mode_evidence_done
            or (
                target_sample_acceptance_ready
                and target_sample_acceptance_contract.get("failure_modes_validated") is True
            )
        )
        rows.append(
            _provider_evidence_gap_row(
                target=target_key,
                label=label,
                apis=target_apis,
                selected_apis=selected_apis,
                missing_required_apis=missing_required_apis,
                missing_call_ledger_apis=missing_call_ledger_apis,
                non_empty_success_apis=non_empty_success_apis,
                validated_empty_apis=validated_empty_apis,
                failed_or_blocked_apis=failed_or_blocked_apis,
                validation_readiness=str(target_row.get("readiness") or "unknown"),
                sample_plan_status=str(sample_plan_row.get("provider_sample_plan_status") or "unknown"),
                promotion_ready=promotion_ready,
                failure_mode_evidence_done=target_failure_mode_evidence_done,
                target_sample_acceptance_status=target_sample_acceptance_status,
                target_sample_acceptance_ready_for_review=target_sample_acceptance_ready,
                target_sample_acceptance_blockers=list(
                    target_sample_acceptance_row.get("target_sample_acceptance_blockers") or []
                ),
                required_success_evidence=list(sample_plan_row.get("required_success_evidence") or []),
                required_failure_evidence=list(sample_plan_row.get("required_failure_evidence") or []),
            )
        )

    target_with_gap_count = sum(1 for row in rows if int(row.get("gap_blocker_count") or 0) > 0)
    gap_blocker_count = sum(int(row.get("gap_blocker_count") or 0) for row in rows)
    target_sample_ready_count = sum(1 for row in rows if row.get("target_sample_acceptance_ready_for_review"))
    target_sample_requested_count = int(target_sample_acceptance_contract.get("requested_target_count") or 0)
    return {
        "schema_version": "tushare_provider_evidence_gap_audit.v1",
        "status": "provider_evidence_gaps_cleared_for_review" if target_with_gap_count == 0 else "provider_evidence_gaps_pending",
        "scope": "local_provider_evidence_gap_ledger_no_provider_execution",
        "target_count": len(rows),
        "target_with_gap_count": target_with_gap_count,
        "gap_blocker_count": gap_blocker_count,
        "target_sample_acceptance_requested_count": target_sample_requested_count,
        "target_sample_acceptance_ready_count": target_sample_ready_count,
        "target_sample_acceptance_status": target_sample_acceptance_contract.get(
            "status",
            "target_sample_acceptance_not_requested",
        ),
        "target_sample_acceptance_ready_for_review": bool(
            target_sample_acceptance_contract.get("target_sample_acceptance_ready_for_review")
        ),
        "provider_promotion_ready": promotion_ready,
        "failure_mode_evidence_done": failure_mode_evidence_done,
        "provider_backed_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "full_interface_acceptance_done": False,
        "cache_get_external_calls": False,
        "audit_external_calls_triggered": False,
        "tushare_called_by_audit": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
        "note": "This audit is a local target-domain evidence gap ledger. It does not call Tushare and cannot promote provider-backed full-interface acceptance by itself.",
    }


def _provider_sample_readiness_receipt_row(
    criterion: str,
    status: str,
    passed: bool,
    *,
    evidence: str,
    required_before_promotion: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "required_before_promotion": bool(required_before_promotion),
        "evidence": evidence,
        "cache_get_external_calls": False,
        "receipt_external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _provider_sample_readiness_receipt(
    *,
    provider_target_sample_plan_contract: dict[str, Any],
    provider_target_sample_acceptance_contract: dict[str, Any] | None = None,
    provider_acceptance_readiness_audit: dict[str, Any],
    provider_acceptance_promotion_audit: dict[str, Any],
    provider_evidence_gap_audit: dict[str, Any],
) -> dict[str, Any]:
    ready_target_count = int(provider_target_sample_plan_contract.get("ready_to_execute_target_count") or 0)
    pending_target_count = int(provider_target_sample_plan_contract.get("pending_or_blocked_target_count") or 0)
    target_count = int(provider_target_sample_plan_contract.get("target_count") or 0)
    gap_blocker_count = int(provider_evidence_gap_audit.get("gap_blocker_count") or 0)
    target_sample_acceptance = provider_target_sample_acceptance_contract or {}
    target_sample_acceptance_ready_count = int(target_sample_acceptance.get("ready_target_count") or 0)
    target_sample_acceptance_requested_count = int(target_sample_acceptance.get("requested_target_count") or 0)
    target_sample_acceptance_ready = bool(target_sample_acceptance.get("target_sample_acceptance_ready_for_review"))
    promotion_ready = bool(provider_acceptance_promotion_audit.get("promotion_ready"))
    readiness_local_safe = bool(
        provider_acceptance_readiness_audit.get("schema_version") == "tushare_provider_acceptance_readiness_audit.v1"
        and provider_acceptance_readiness_audit.get("audit_external_calls_triggered") is False
        and provider_acceptance_readiness_audit.get("provider_backed_acceptance_done") is False
    )
    sample_plan_local_safe = bool(
        provider_target_sample_plan_contract.get("schema_version") == "tushare_provider_target_sample_plan_contract.v1"
        and provider_target_sample_plan_contract.get("plan_external_calls_triggered") is False
        and provider_target_sample_plan_contract.get("provider_backed_acceptance_done") is False
    )
    gap_audit_local_safe = bool(
        provider_evidence_gap_audit.get("schema_version") == "tushare_provider_evidence_gap_audit.v1"
        and provider_evidence_gap_audit.get("audit_external_calls_triggered") is False
        and provider_evidence_gap_audit.get("provider_backed_acceptance_done") is False
    )
    ready_for_explicit_provider_sample_task = bool(
        ready_target_count > 0
        and sample_plan_local_safe
        and readiness_local_safe
        and gap_audit_local_safe
    )
    gap_rows = provider_evidence_gap_audit.get("rows", [])
    missing_evidence_items = sorted(
        {
            str(blocker)
            for row in gap_rows
            if isinstance(row, Mapping)
            for blocker in row.get("gap_blockers", [])
            if blocker
        }
        | {str(blocker) for blocker in provider_acceptance_promotion_audit.get("blockers", []) if blocker}
    )
    rows = [
        _provider_sample_readiness_receipt_row(
            "button_gated_post_task_boundary",
            "passed_static_policy",
            True,
            evidence="Provider samples may only be gathered by explicit POST task; GET cache and render cannot call Tushare.",
            required_before_promotion=False,
        ),
        _provider_sample_readiness_receipt_row(
            "sample_plan_has_ready_targets",
            "ready_for_explicit_provider_sample" if ready_target_count > 0 else "blocked_no_ready_target",
            ready_target_count > 0,
            evidence=f"ready_targets={ready_target_count}; pending_targets={pending_target_count}; target_count={target_count}",
        ),
        _provider_sample_readiness_receipt_row(
            "local_contracts_are_no_provider_call",
            "passed_no_provider_call" if sample_plan_local_safe and readiness_local_safe and gap_audit_local_safe else "blocked_external_boundary",
            sample_plan_local_safe and readiness_local_safe and gap_audit_local_safe,
            evidence="sample plan, readiness audit, and evidence gap audit are local/read-only contracts.",
        ),
        _provider_sample_readiness_receipt_row(
            "provider_evidence_gaps_visible",
            "passed_gaps_visible" if gap_blocker_count > 0 or promotion_ready else "blocked_gap_ledger_missing",
            gap_blocker_count > 0 or promotion_ready,
            evidence=f"gap_status={provider_evidence_gap_audit.get('status')}; gap_blocker_count={gap_blocker_count}",
        ),
        _provider_sample_readiness_receipt_row(
            "target_sample_acceptance_review_evidence",
            "ready_for_review_not_promotion"
            if target_sample_acceptance_ready
            else "not_requested_or_blocked",
            target_sample_acceptance_ready,
            evidence=(
                f"acceptance_status={target_sample_acceptance.get('status', 'target_sample_acceptance_not_requested')}; "
                f"requested_targets={target_sample_acceptance_requested_count}; "
                f"ready_targets={target_sample_acceptance_ready_count}"
            ),
            required_before_promotion=False,
        ),
        _provider_sample_readiness_receipt_row(
            "provider_promotion_evidence_ticket",
            "ready_for_promotion_review" if promotion_ready else "pending_provider_execution_evidence",
            promotion_ready,
            evidence=(
                f"promotion_status={provider_acceptance_promotion_audit.get('status')}; "
                f"promotion_blockers={provider_acceptance_promotion_audit.get('blocking_criterion_count')}; "
                f"provider_evidence_rows={provider_acceptance_promotion_audit.get('provider_evidence_row_count')}"
            ),
        ),
        _provider_sample_readiness_receipt_row(
            "matrix_and_local_qa_not_acceptance",
            "enforced_not_provider_acceptance",
            True,
            evidence="Matrix rows, failure-mode QA, request-parameter QA, target sample plans, and local gap ledgers cannot be promoted by themselves.",
            required_before_promotion=False,
        ),
        _provider_sample_readiness_receipt_row(
            "trade_and_action_boundary",
            "passed",
            True,
            evidence="Receipt never executes trades and never mutates strategy action.",
            required_before_promotion=False,
        ),
    ]
    blocked_rows = [row["criterion"] for row in rows if row["required_before_promotion"] and not row["passed"]]
    return {
        "schema_version": "tushare_provider_sample_readiness_receipt.v1",
        "status": "provider_sample_receipt_ready_for_promotion_review"
        if promotion_ready
        else "provider_sample_receipt_ready_execution_pending"
        if ready_for_explicit_provider_sample_task
        else "provider_sample_receipt_blocked",
        "scope": "local_provider_sample_readiness_receipt_no_provider_execution",
        "ready_for_explicit_provider_sample_task": ready_for_explicit_provider_sample_task,
        "allowed_next_step": "review_prior_full_interface_provider_evidence"
        if promotion_ready
        else "explicit_post_task_target_sample_acceptance"
        if ready_for_explicit_provider_sample_task
        else "complete_target_sample_payload_and_selection",
        "not_allowed_next_steps": [
            "GET cache provider refresh",
            "React render provider refresh",
            "matrix-only acceptance promotion",
            "fake/local adapter acceptance promotion",
            "local QA acceptance promotion",
            "strategy action mutation",
            "real trade execution",
        ],
        "target_count": target_count,
        "ready_target_count": ready_target_count,
        "pending_or_blocked_target_count": pending_target_count,
        "target_sample_acceptance_requested_count": target_sample_acceptance_requested_count,
        "target_sample_acceptance_ready_count": target_sample_acceptance_ready_count,
        "target_sample_acceptance_ready_for_review": target_sample_acceptance_ready,
        "provider_evidence_gap_blocker_count": gap_blocker_count,
        "provider_promotion_ready": promotion_ready,
        "provider_backed_acceptance_done": promotion_ready,
        "production_tushare_pipeline_complete": False,
        "full_interface_acceptance_done": False,
        "provider_refresh_called_by_receipt": False,
        "cache_get_external_calls": False,
        "receipt_external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_count": len(rows),
        "blocked_readiness_count": len(blocked_rows),
        "blocked_readiness_items": blocked_rows,
        "missing_evidence_items": missing_evidence_items,
        "rows": rows,
        "note": "This receipt summarizes the next safe LTG-02 provider-sample step. It never calls Tushare and cannot promote matrix, fake adapter, local QA, or gap-ledger evidence to production acceptance.",
    }


def _provider_sample_activation_receipt_row(
    criterion: str,
    status: str,
    passed: bool,
    *,
    evidence: str,
    required_before_activation: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "required_before_activation": bool(required_before_activation),
        "evidence": evidence,
        "cache_get_external_calls": False,
        "receipt_external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _provider_sample_activation_receipt(
    *,
    provider_target_sample_plan_contract: dict[str, Any],
    provider_sample_readiness_receipt: dict[str, Any],
    provider_acceptance_promotion_audit: dict[str, Any],
    provider_evidence_gap_audit: dict[str, Any],
) -> dict[str, Any]:
    ready_for_explicit_task = bool(provider_sample_readiness_receipt.get("ready_for_explicit_provider_sample_task"))
    promotion_ready = bool(provider_acceptance_promotion_audit.get("promotion_ready"))
    target_count = int(provider_target_sample_plan_contract.get("target_count") or 0)
    ready_target_count = int(provider_target_sample_plan_contract.get("ready_to_execute_target_count") or 0)
    pending_target_count = int(provider_target_sample_plan_contract.get("pending_or_blocked_target_count") or 0)
    gap_blocker_count = int(provider_evidence_gap_audit.get("gap_blocker_count") or 0)
    local_activation_receipt_ready = bool(
        provider_sample_readiness_receipt.get("schema_version") == "tushare_provider_sample_readiness_receipt.v1"
        and provider_sample_readiness_receipt.get("provider_refresh_called_by_receipt") is False
        and provider_target_sample_plan_contract.get("schema_version") == "tushare_provider_target_sample_plan_contract.v1"
        and provider_target_sample_plan_contract.get("plan_external_calls_triggered") is False
        and provider_evidence_gap_audit.get("schema_version") == "tushare_provider_evidence_gap_audit.v1"
        and provider_evidence_gap_audit.get("audit_external_calls_triggered") is False
    )
    rows = [
        _provider_sample_activation_receipt_row(
            "sample_readiness_receipt_visible",
            "passed_local_receipt" if local_activation_receipt_ready else "blocked_readiness_receipt",
            local_activation_receipt_ready,
            evidence=(
                f"sample_receipt_status={provider_sample_readiness_receipt.get('status')}; "
                f"ready_for_explicit_task={ready_for_explicit_task}"
            ),
        ),
        _provider_sample_activation_receipt_row(
            "explicit_post_task_required",
            "passed_static_policy" if ready_for_explicit_task else "blocked_no_ready_target",
            ready_for_explicit_task,
            evidence="Only a future explicit POST task may gather target-domain Tushare provider samples.",
        ),
        _provider_sample_activation_receipt_row(
            "provider_execution_evidence_required",
            "pending_provider_execution_evidence",
            False,
            evidence=(
                f"provider_evidence_rows={provider_acceptance_promotion_audit.get('provider_evidence_row_count')}; "
                f"promotion_ready={promotion_ready}"
            ),
        ),
        _provider_sample_activation_receipt_row(
            "promotion_review_required",
            "ready_for_promotion_review" if promotion_ready else "pending_promotion_review",
            promotion_ready,
            evidence=(
                f"promotion_status={provider_acceptance_promotion_audit.get('status')}; "
                f"promotion_blockers={provider_acceptance_promotion_audit.get('blocking_criterion_count')}"
            ),
        ),
        _provider_sample_activation_receipt_row(
            "target_gap_ledger_visible",
            "passed_gaps_visible" if gap_blocker_count > 0 or promotion_ready else "blocked_gap_ledger_missing",
            gap_blocker_count > 0 or promotion_ready,
            evidence=f"gap_status={provider_evidence_gap_audit.get('status')}; gap_blocker_count={gap_blocker_count}",
        ),
        _provider_sample_activation_receipt_row(
            "matrix_and_local_qa_not_acceptance",
            "enforced_not_provider_acceptance",
            True,
            evidence="Matrix rows, local QA, sample plans, evidence gaps, and this activation receipt are not provider-backed acceptance.",
            required_before_activation=False,
        ),
        _provider_sample_activation_receipt_row(
            "cache_render_provider_boundary",
            "passed_no_provider_call",
            True,
            evidence="GET cache and React render do not call Tushare, DeepSeek, or GitHub and do not create provider tasks.",
            required_before_activation=False,
        ),
        _provider_sample_activation_receipt_row(
            "production_completion_boundary",
            "enforced_not_complete",
            True,
            evidence="Provider sample activation receipt cannot mark production_tushare_pipeline_complete=true.",
            required_before_activation=False,
        ),
        _provider_sample_activation_receipt_row(
            "no_trade_or_action_boundary",
            "passed",
            True,
            evidence="Receipt does not execute trades and does not mutate strategy action.",
            required_before_activation=False,
        ),
    ]
    blocking_rows = [row for row in rows if row["required_before_activation"] and not row["passed"]]
    missing_evidence_items = sorted(
        {
            *[str(item) for item in provider_sample_readiness_receipt.get("missing_evidence_items", []) if item],
            *[str(item) for item in provider_acceptance_promotion_audit.get("blockers", []) if item],
            "explicit provider target-sample task execution",
            "safe provider call ledger rows for every target domain",
            "explicit provider-backed full-interface acceptance marker",
        }
    )
    return {
        "schema_version": "tushare_provider_sample_activation_receipt.v1",
        "status": "provider_sample_activation_ready_execution_pending"
        if local_activation_receipt_ready and ready_for_explicit_task
        else "provider_sample_activation_blocked_local_readiness"
        if local_activation_receipt_ready
        else "provider_sample_activation_blocked_local_contract",
        "scope": "local_provider_sample_activation_receipt_no_provider_execution",
        "local_activation_receipt_ready": local_activation_receipt_ready,
        "ready_for_explicit_provider_sample_task": ready_for_explicit_task,
        "allowed_next_step": "explicit_post_task_target_sample_acceptance"
        if ready_for_explicit_task
        else "complete_target_sample_payload_and_selection",
        "not_allowed_next_steps": [
            "GET cache provider refresh",
            "React render provider refresh",
            "direct Tushare call from page render",
            "matrix-only acceptance promotion",
            "fake/local adapter acceptance promotion",
            "local QA acceptance promotion",
            "activation receipt as production Tushare completion",
            "strategy action mutation",
            "real trade execution",
        ],
        "missing_evidence_items": missing_evidence_items,
        "target_count": target_count,
        "ready_target_count": ready_target_count,
        "pending_or_blocked_target_count": pending_target_count,
        "provider_evidence_gap_blocker_count": gap_blocker_count,
        "provider_acceptance_task_executed_by_receipt": False,
        "provider_refresh_called_by_receipt": False,
        "provider_task_created_by_receipt": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "receipt_external_calls_triggered": False,
        "external_calls_triggered": False,
        "tushare_called_by_receipt": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "provider_backed_acceptance_done": promotion_ready,
        "production_tushare_pipeline_complete": False,
        "full_interface_acceptance_done": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "blocking_criterion_count": len(blocking_rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tushare_provider_sample_activation_receipt",
                "source": "tushare local provider sample contracts",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_activation_receipt_provider_execution_pending",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This receipt is a local activation checklist for future explicit Tushare provider-sample acceptance. It does not call Tushare, create tasks, promote local evidence, execute trades, mutate action, or prove production completion.",
    }


def _provider_target_sample_runbook_contract(
    *,
    selected_apis: Iterable[str],
    payload: Any,
    provider_target_sample_plan_contract: dict[str, Any],
    provider_target_sample_acceptance_contract: dict[str, Any],
    provider_evidence_gap_audit: dict[str, Any],
    provider_sample_activation_receipt: dict[str, Any],
) -> dict[str, Any]:
    safe_payload = _safe_payload(payload)
    acceptance_mode = str(
        safe_payload.get("acceptance_mode")
        or safe_payload.get("provider_acceptance_mode")
        or "standard_refresh"
    )
    explicit_acceptance_mode = acceptance_mode == PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE
    requested_targets = list(provider_target_sample_acceptance_contract.get("requested_targets") or [])
    selected_set = set(selected_apis)
    plan_by_target = {
        str(row.get("target") or ""): row
        for row in provider_target_sample_plan_contract.get("rows", [])
        if isinstance(row, Mapping)
    }
    acceptance_by_target = {
        str(row.get("target") or ""): row
        for row in provider_target_sample_acceptance_contract.get("rows", [])
        if isinstance(row, Mapping)
    }
    gap_by_target = {
        str(row.get("target") or ""): row
        for row in provider_evidence_gap_audit.get("rows", [])
        if isinstance(row, Mapping)
    }
    activation_local_safe = bool(
        provider_sample_activation_receipt.get("schema_version") == "tushare_provider_sample_activation_receipt.v1"
        and provider_sample_activation_receipt.get("receipt_external_calls_triggered") is False
        and provider_sample_activation_receipt.get("provider_refresh_called_by_receipt") is False
        and provider_sample_activation_receipt.get("production_tushare_pipeline_complete") is False
    )
    rows: list[dict[str, Any]] = []
    for target_key, label, apis in VALIDATION_TARGET_GROUPS:
        target_apis = list(apis)
        requested = target_key in requested_targets
        plan_row = plan_by_target.get(target_key, {})
        acceptance_row = acceptance_by_target.get(target_key, {})
        gap_row = gap_by_target.get(target_key, {})
        selected_target_apis = [api for api in target_apis if api in selected_set]
        acceptance_ready = (
            acceptance_row.get("target_sample_acceptance_status") == "target_sample_acceptance_ready_for_review"
        )
        plan_ready = plan_row.get("provider_sample_plan_status") == "ready_to_execute_provider_sample"
        if not requested:
            runbook_status = "target_sample_runbook_not_requested"
            next_step = "select_target_group_with_provider_target_sample_acceptance_mode"
        elif not explicit_acceptance_mode:
            runbook_status = "target_sample_runbook_blocked_acceptance_mode_missing"
            next_step = "set_acceptance_mode_provider_target_sample_acceptance"
        elif not plan_ready:
            runbook_status = "target_sample_runbook_blocked_plan_not_ready"
            next_step = "complete_target_payload_context_and_api_selection"
        elif not acceptance_ready:
            runbook_status = "target_sample_runbook_blocked_review_evidence_missing"
            next_step = "run_explicit_post_task_and_review_call_ledger"
        else:
            runbook_status = "target_sample_runbook_ready_provider_review_pending"
            next_step = "explicit_provider_sample_evidence_review_then_promotion_audit"
        rows.append(
            {
                "target": target_key,
                "label": label,
                "requested_for_runbook": requested,
                "post_task_route": "POST /api/tasks/refresh-tushare-facts",
                "required_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
                "acceptance_mode_present": explicit_acceptance_mode,
                "required_apis": target_apis,
                "selected_apis": selected_target_apis,
                "missing_required_apis": [api for api in target_apis if api not in selected_target_apis],
                "required_context_groups": list(plan_row.get("required_context_groups") or []),
                "provided_context_fields": list(plan_row.get("provided_context_fields") or []),
                "missing_context_groups": list(plan_row.get("missing_context_groups") or []),
                "evidence_checklist": [
                    "button_gated_post_task_only",
                    "safe_request_params_without_token_or_key",
                    "call_ledger_required_fields_present",
                    "row_count_data_date_local_fetched_at_visible",
                    "non_empty_or_valid_empty_sample_evidence",
                    "failure_mode_evidence_visible",
                    "safe_error_message_redacted",
                    "gap_ledger_visible",
                    "promotion_audit_required",
                    "no_trade_no_strategy_action_mutation",
                ],
                "target_sample_acceptance_status": str(
                    acceptance_row.get("target_sample_acceptance_status")
                    or "target_sample_acceptance_not_requested"
                ),
                "target_sample_acceptance_ready_for_review": acceptance_ready,
                "target_sample_acceptance_blockers": list(
                    acceptance_row.get("target_sample_acceptance_blockers") or []
                ),
                "provider_sample_plan_status": str(
                    plan_row.get("provider_sample_plan_status") or "matrix_only_plan_pending"
                ),
                "provider_evidence_gap_status": str(gap_row.get("gap_status") or "matrix_only_gap_pending"),
                "provider_promotion_blockers": list(gap_row.get("gap_blockers") or []),
                "runbook_status": runbook_status,
                "next_step": next_step,
                "provider_backed_acceptance_done": False,
                "full_interface_acceptance_done": False,
                "production_tushare_pipeline_complete": False,
                "cache_get_external_calls": False,
                "react_render_external_calls": False,
                "runbook_external_calls_triggered": False,
                "tushare_called_by_runbook": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    requested_rows = [row for row in rows if row.get("requested_for_runbook")]
    ready_rows = [
        row
        for row in requested_rows
        if row.get("runbook_status") == "target_sample_runbook_ready_provider_review_pending"
    ]
    blocked_rows = [
        row
        for row in requested_rows
        if row.get("runbook_status") != "target_sample_runbook_ready_provider_review_pending"
    ]
    runbook_ready = bool(requested_rows and len(ready_rows) == len(requested_rows) and activation_local_safe)
    return {
        "schema_version": "tushare_provider_target_sample_runbook_contract.v1",
        "status": "target_sample_runbook_ready_provider_review_pending"
        if runbook_ready
        else "target_sample_runbook_blocked_or_not_requested",
        "scope": "local_target_sample_provider_runbook_no_provider_execution",
        "post_task_route": "POST /api/tasks/refresh-tushare-facts",
        "required_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
        "explicit_acceptance_mode": explicit_acceptance_mode,
        "requested_targets": requested_targets,
        "requested_target_count": len(requested_targets),
        "runbook_ready_target_count": len(ready_rows),
        "blocked_runbook_target_count": len(blocked_rows),
        "target_sample_acceptance_ready_count": int(
            provider_target_sample_acceptance_contract.get("ready_target_count") or 0
        ),
        "runbook_ready": runbook_ready,
        "allowed_next_step": "explicit_provider_sample_evidence_review_then_promotion_audit"
        if runbook_ready
        else "complete_explicit_target_sample_payload_selection_and_review_evidence",
        "not_allowed_next_steps": [
            "GET cache provider refresh",
            "React render provider refresh",
            "direct Tushare call from page render",
            "runbook as provider-backed acceptance",
            "runbook as full-interface acceptance",
            "fake/local adapter acceptance promotion",
            "strategy action mutation",
            "real trade execution",
        ],
        "provider_backed_acceptance_done": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "runbook_external_calls_triggered": False,
        "tushare_called_by_runbook": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_count": len(rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tushare_provider_target_sample_runbook",
                "source": "tushare target sample acceptance and gap contracts",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_runbook_provider_execution_pending",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This runbook is a local checklist for explicit target-domain Tushare provider sample review. It does not call Tushare, create tasks, promote fake/local evidence, execute trades, mutate action, or prove production completion.",
    }


def _provider_target_sample_execution_recipe(
    *,
    provider_target_sample_runbook_contract: dict[str, Any],
    provider_sample_activation_receipt: dict[str, Any],
) -> dict[str, Any]:
    runbook_rows = [
        row
        for row in provider_target_sample_runbook_contract.get("rows", [])
        if isinstance(row, Mapping)
    ]
    requested_rows = [row for row in runbook_rows if row.get("requested_for_runbook") is True]
    ready_rows = [
        row
        for row in requested_rows
        if row.get("runbook_status") == "target_sample_runbook_ready_provider_review_pending"
    ]
    activation_local_safe = bool(
        provider_sample_activation_receipt.get("schema_version") == "tushare_provider_sample_activation_receipt.v1"
        and provider_sample_activation_receipt.get("receipt_external_calls_triggered") is False
        and provider_sample_activation_receipt.get("provider_refresh_called_by_receipt") is False
        and provider_sample_activation_receipt.get("provider_task_created_by_receipt") is False
        and provider_sample_activation_receipt.get("production_tushare_pipeline_complete") is False
    )
    runbook_ready = bool(provider_target_sample_runbook_contract.get("runbook_ready"))
    recipe_ready = bool(requested_rows and len(ready_rows) == len(requested_rows) and runbook_ready and activation_local_safe)
    phase_keys = [
        "manual_operator_confirmation",
        "scope_ticket_and_payload_review",
        "explicit_post_task_execution",
        "safe_provider_call_ledger_capture",
        "target_sample_row_review",
        "failure_mode_review",
        "provider_promotion_audit",
        "storage_and_cache_promotion_review",
    ]
    rows: list[dict[str, Any]] = []
    for row in runbook_rows:
        requested = row.get("requested_for_runbook") is True
        row_ready = bool(
            requested
            and row.get("runbook_status") == "target_sample_runbook_ready_provider_review_pending"
            and activation_local_safe
        )
        if not requested:
            recipe_status = "target_sample_execution_recipe_not_requested"
            next_step = "select_target_group_with_provider_target_sample_acceptance_mode"
        elif not activation_local_safe:
            recipe_status = "target_sample_execution_recipe_blocked_activation_receipt"
            next_step = "repair_local_activation_receipt_before_execution"
        elif not row_ready:
            recipe_status = "target_sample_execution_recipe_blocked_runbook"
            next_step = str(row.get("next_step") or "complete_runbook_review_evidence")
        else:
            recipe_status = "target_sample_execution_recipe_ready_user_confirmation_required"
            next_step = "manual_confirm_then_execute_post_task_and_review_promotion"
        rows.append(
            {
                "target": row.get("target"),
                "label": row.get("label"),
                "requested_for_execution_recipe": requested,
                "post_task_route": "POST /api/tasks/refresh-tushare-facts",
                "required_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
                "selected_apis": list(row.get("selected_apis") or []),
                "missing_required_apis": list(row.get("missing_required_apis") or []),
                "phase_keys": phase_keys,
                "pending_phase_keys": phase_keys,
                "required_evidence": [
                    "manual approval for the selected target domain",
                    "safe request payload without token or key values",
                    "call_ledger api/provider/request_params_safe/row_count/data_date/local_fetched_at/call_status/error_message_safe",
                    "non-empty sample rows or explicitly classified valid-empty evidence",
                    "failure-mode evidence for empty, permission, parse, provider, and missing-param cases",
                    "promotion audit that still keeps production_tushare_pipeline_complete=false until full-interface evidence exists",
                    "storage promotion review before Parquet/cache promotion",
                ],
                "not_allowed_next_steps": [
                    "call Tushare from this recipe",
                    "create provider task from this recipe",
                    "GET cache provider refresh",
                    "React render provider refresh",
                    "runbook as provider-backed acceptance",
                    "target sample as full-interface acceptance",
                    "fake/local adapter promotion",
                    "strategy action mutation",
                    "real trade execution",
                ],
                "runbook_status": row.get("runbook_status"),
                "execution_recipe_status": recipe_status,
                "next_step": next_step,
                "provider_promotion_blockers": list(row.get("provider_promotion_blockers") or []),
                "recipe_ready_for_user_confirmation": row_ready,
                "provider_task_created_by_recipe": False,
                "provider_execution_implemented_by_recipe": False,
                "provider_call_ledger_evidence_done_by_recipe": False,
                "provider_backed_target_sample_acceptance_done": False,
                "full_interface_acceptance_done": False,
                "production_tushare_pipeline_complete": False,
                "cache_get_external_calls": False,
                "react_render_external_calls": False,
                "recipe_external_calls_triggered": False,
                "tushare_called_by_recipe": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
            }
        )
    ready_count = sum(1 for row in rows if row.get("recipe_ready_for_user_confirmation") is True)
    blocked_count = sum(
        1
        for row in rows
        if row.get("requested_for_execution_recipe") is True
        and row.get("recipe_ready_for_user_confirmation") is not True
    )
    requested_targets = list(provider_target_sample_runbook_contract.get("requested_targets") or [])
    scope_payload = {
        "schema_version": "tushare_provider_target_sample_execution_recipe.v1",
        "scope": "local_target_sample_execution_recipe_no_provider_execution",
        "post_task_route": "POST /api/tasks/refresh-tushare-facts",
        "required_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
        "requested_targets": requested_targets,
        "phase_keys": phase_keys,
        "target_rows": [
            {
                "target": row.get("target"),
                "requested_for_execution_recipe": row.get("requested_for_execution_recipe") is True,
                "selected_apis": sorted(str(api) for api in row.get("selected_apis") or []),
                "execution_recipe_status": row.get("execution_recipe_status"),
                "recipe_ready_for_user_confirmation": row.get("recipe_ready_for_user_confirmation") is True,
            }
            for row in rows
            if row.get("requested_for_execution_recipe") is True
        ],
    }
    scope_hash_input = json.dumps(scope_payload, ensure_ascii=False, sort_keys=True)
    scope_hash = hashlib.sha256(scope_hash_input.encode("utf-8")).hexdigest()
    return {
        "schema_version": "tushare_provider_target_sample_execution_recipe.v1",
        "status": "target_sample_execution_recipe_ready_user_confirmation_required"
        if recipe_ready
        else "target_sample_execution_recipe_blocked_or_not_requested",
        "scope": "local_target_sample_execution_recipe_no_provider_execution",
        "post_task_route": "POST /api/tasks/refresh-tushare-facts",
        "required_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
        "runbook_ready": runbook_ready,
        "activation_receipt_ready": activation_local_safe,
        "requested_targets": requested_targets,
        "requested_target_count": len(requested_rows),
        "recipe_ready_target_count": ready_count,
        "blocked_recipe_target_count": blocked_count,
        "recipe_ready_for_user_confirmation": recipe_ready,
        "execution_recipe_scope_hash_algorithm": "sha256",
        "execution_recipe_scope_hash": scope_hash,
        "execution_recipe_scope_hash_short": scope_hash[:16],
        "execution_recipe_scope_hash_input_field_count": len(scope_payload),
        "allowed_next_step": "manual_confirm_then_execute_post_task_and_review_promotion"
        if recipe_ready
        else "complete_target_sample_runbook_and_activation_receipt",
        "phase_keys": phase_keys,
        "pending_phase_keys": phase_keys,
        "not_allowed_next_steps": [
            "call Tushare from this recipe",
            "create provider task from this recipe",
            "GET cache provider refresh",
            "React render provider refresh",
            "recipe as provider-backed acceptance",
            "recipe as full-interface acceptance",
            "strategy action mutation",
            "real trade execution",
        ],
        "provider_task_created_by_recipe": False,
        "provider_execution_implemented_by_recipe": False,
        "provider_call_ledger_evidence_done_by_recipe": False,
        "provider_backed_acceptance_done": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "recipe_external_calls_triggered": False,
        "tushare_called_by_recipe": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "row_count": len(rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tushare_provider_target_sample_execution_recipe",
                "source": "tushare provider target sample runbook and activation receipt",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_execution_recipe_provider_execution_pending",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This recipe fixes the operator-confirmed order for a future explicit Tushare target-sample acceptance run. It does not call Tushare, create tasks, promote local/fake evidence, execute trades, mutate action, or prove production completion.",
    }


def _latest_tushare_refresh_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet("command_center_tushare_refresh_packet")
    except Exception:
        return {}
    return dict(packet) if isinstance(packet, Mapping) else {}


def _direct_evidence_rows_from_packet(packet: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(packet, Mapping):
        return []
    candidates = list(packet.get("prior_direct_evidence_rows") or []) + list(packet.get("call_ledger") or [])
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        call_status = str(row.get("call_status") or "").lower()
        is_direct = (
            row.get("external_calls_triggered") is True
            or row.get("tushare_called") is True
            or row.get("provider_backed_long_window_acceptance_done") is True
            or row.get("provider_backed_trade_cal_acceptance_done") is True
            or call_status in ACCEPTANCE_SAFE_TERMINAL_STATUSES
        )
        if not is_direct:
            continue
        signature = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
        if signature in seen:
            continue
        seen.add(signature)
        rows.append(row)
    return rows[:80]


def _latest_tushare_target_sample_execution_recipe_packet() -> dict[str, Any]:
    refresh_packet = _latest_tushare_refresh_packet()
    recipe = refresh_packet.get("provider_target_sample_execution_recipe") if isinstance(refresh_packet, Mapping) else {}
    if isinstance(recipe, Mapping) and recipe:
        return refresh_packet
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_PACKET_KEY)
    except Exception:
        packet = {}
    return dict(packet) if isinstance(packet, Mapping) else {}


def _provider_target_sample_execution_recipe_seed(payload: Any = None) -> dict[str, Any]:
    payload_safe = _safe_payload(payload)
    target_specs = {target: (label, tuple(apis)) for target, label, apis in VALIDATION_TARGET_GROUPS}
    requested_targets, unknown_targets = _target_sample_acceptance_requested_targets(payload_safe)
    if not requested_targets and not unknown_targets:
        requested_targets = ["margin_financing"]
    valid_requested_targets = [target for target in requested_targets if target in target_specs]
    default_apis: list[str] = []
    for target in valid_requested_targets:
        for api in target_specs[target][1]:
            if api not in default_apis:
                default_apis.append(api)
    selected_apis = [
        api
        for api in _selected_apis(payload_safe, default_apis or MARGIN_REFRESH_APIS)
        if api in set(default_apis or MARGIN_REFRESH_APIS)
    ]
    phase_keys = [
        "manual_operator_confirmation",
        "scope_ticket_and_payload_review",
        "explicit_post_task_execution",
        "safe_provider_call_ledger_capture",
        "target_sample_row_review",
        "failure_mode_review",
        "provider_promotion_audit",
        "storage_and_cache_promotion_review",
    ]
    rows: list[dict[str, Any]] = []
    for target, (label, apis) in target_specs.items():
        requested = target in valid_requested_targets
        target_selected_apis = [api for api in selected_apis if api in apis]
        row_ready = bool(requested and target_selected_apis and not unknown_targets)
        if not requested:
            status = "target_sample_execution_recipe_not_requested"
            next_step = "select_target_group_with_provider_target_sample_acceptance_mode"
        elif unknown_targets:
            status = "target_sample_execution_recipe_blocked_unknown_target_group"
            next_step = "use_known_validation_target_groups"
        elif not target_selected_apis:
            status = "target_sample_execution_recipe_blocked_empty_api_scope"
            next_step = "select_target_sample_apis_before_provider_task"
        else:
            status = "target_sample_execution_recipe_ready_user_confirmation_required"
            next_step = "manual_confirm_then_execute_post_task_and_review_promotion"
        rows.append(
            {
                "target": target,
                "label": label,
                "requested_for_execution_recipe": requested,
                "post_task_route": "POST /api/tasks/refresh-tushare-facts",
                "required_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
                "selected_apis": target_selected_apis,
                "missing_required_apis": [],
                "phase_keys": phase_keys,
                "pending_phase_keys": phase_keys,
                "required_evidence": [
                    "manual approval for the selected target domain",
                    "safe request payload without token or key values",
                    "future provider call_ledger evidence",
                    "failure-mode evidence before promotion",
                    "storage promotion review before Parquet/cache promotion",
                ],
                "not_allowed_next_steps": [
                    "call Tushare from this recipe seed",
                    "create provider task from this recipe seed",
                    "GET cache provider refresh",
                    "React render provider refresh",
                    "recipe seed as provider-backed acceptance",
                    "recipe seed as full-interface acceptance",
                    "strategy action mutation",
                    "real trade execution",
                ],
                "runbook_status": "target_sample_runbook_ready_provider_review_pending" if row_ready else status,
                "execution_recipe_status": status,
                "next_step": next_step,
                "provider_promotion_blockers": ["provider_promotion_not_ready"] if requested else [],
                "recipe_ready_for_user_confirmation": row_ready,
                "provider_task_created_by_recipe": False,
                "provider_execution_implemented_by_recipe": False,
                "provider_call_ledger_evidence_done_by_recipe": False,
                "provider_backed_target_sample_acceptance_done": False,
                "full_interface_acceptance_done": False,
                "production_tushare_pipeline_complete": False,
                "cache_get_external_calls": False,
                "react_render_external_calls": False,
                "recipe_external_calls_triggered": False,
                "tushare_called_by_recipe": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
            }
        )
    ready_count = sum(1 for row in rows if row.get("recipe_ready_for_user_confirmation") is True)
    blocked_count = sum(
        1
        for row in rows
        if row.get("requested_for_execution_recipe") is True
        and row.get("recipe_ready_for_user_confirmation") is not True
    )
    recipe_ready = bool(valid_requested_targets and ready_count == len(valid_requested_targets) and not unknown_targets)
    scope_payload = {
        "schema_version": "tushare_provider_target_sample_execution_recipe.v1",
        "scope": "local_target_sample_execution_recipe_seed_no_provider_execution",
        "post_task_route": "POST /api/tasks/refresh-tushare-facts",
        "required_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
        "requested_targets": valid_requested_targets,
        "phase_keys": phase_keys,
        "target_rows": [
            {
                "target": row.get("target"),
                "requested_for_execution_recipe": row.get("requested_for_execution_recipe") is True,
                "selected_apis": sorted(str(api) for api in row.get("selected_apis") or []),
                "execution_recipe_status": row.get("execution_recipe_status"),
                "recipe_ready_for_user_confirmation": row.get("recipe_ready_for_user_confirmation") is True,
            }
            for row in rows
            if row.get("requested_for_execution_recipe") is True
        ],
    }
    scope_hash_input = json.dumps(scope_payload, ensure_ascii=False, sort_keys=True)
    scope_hash = hashlib.sha256(scope_hash_input.encode("utf-8")).hexdigest()
    return {
        "schema_version": "tushare_provider_target_sample_execution_recipe.v1",
        "seed_schema_version": PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_SEED_SCHEMA_VERSION,
        "status": "target_sample_execution_recipe_ready_user_confirmation_required"
        if recipe_ready
        else "target_sample_execution_recipe_blocked_or_not_requested",
        "scope": "local_target_sample_execution_recipe_seed_no_provider_execution",
        "post_task_route": "POST /api/tasks/refresh-tushare-facts",
        "required_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
        "runbook_ready": recipe_ready,
        "activation_receipt_ready": True,
        "requested_targets": valid_requested_targets,
        "unknown_requested_targets": unknown_targets,
        "requested_target_count": len(valid_requested_targets),
        "recipe_ready_target_count": ready_count,
        "blocked_recipe_target_count": blocked_count,
        "recipe_ready_for_user_confirmation": recipe_ready,
        "execution_recipe_scope_hash_algorithm": "sha256",
        "execution_recipe_scope_hash": scope_hash,
        "execution_recipe_scope_hash_short": scope_hash[:16],
        "execution_recipe_scope_hash_input_field_count": len(scope_payload),
        "allowed_next_step": "manual_confirm_then_execute_post_task_and_review_promotion"
        if recipe_ready
        else "repair_target_sample_execution_recipe_seed",
        "phase_keys": phase_keys,
        "pending_phase_keys": phase_keys,
        "not_allowed_next_steps": [
            "call Tushare from this recipe seed",
            "create provider task from this recipe seed",
            "GET cache provider refresh",
            "React render provider refresh",
            "recipe seed as provider-backed acceptance",
            "recipe seed as full-interface acceptance",
            "strategy action mutation",
            "real trade execution",
        ],
        "provider_task_created_by_recipe": False,
        "provider_execution_implemented_by_recipe": False,
        "provider_call_ledger_evidence_done_by_recipe": False,
        "provider_backed_acceptance_done": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "recipe_external_calls_triggered": False,
        "tushare_called_by_recipe": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "row_count": len(rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tushare_provider_target_sample_execution_recipe_seed",
                "source": "operator selected target sample groups and APIs",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_execution_recipe_seed_ready_provider_execution_pending"
                if recipe_ready
                else "local_execution_recipe_seed_blocked",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This local seed restores a target-sample execution recipe for a future explicit provider task. It does not call Tushare, create provider tasks, promote acceptance, execute trades, or mutate strategy action.",
    }


def run_tushare_provider_target_sample_execution_recipe_seed(payload: Any = None) -> dict[str, Any]:
    recipe = _provider_target_sample_execution_recipe_seed(payload)
    rows = list(recipe.get("rows") or [])
    packet_key = PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_PACKET_KEY
    payload_safe = {
        "provider_target_sample_execution_recipe": recipe,
        "provider_target_sample_execution_rows": rows,
    }
    task = create_task_record(
        PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_SEED_TASK_TYPE,
        output_packet_key=packet_key,
        payload=payload_safe,
        current_step="tushare_provider_target_sample_execution_recipe_seed_queued_local_only",
        warnings=[
            "该任务只生成本地 Tushare target-sample execution recipe seed，不调用 Tushare。",
            "该任务不创建 provider task，不写 Parquet，不证明 LTG-02 生产完成。",
            "该任务不调用 DeepSeek/GitHub，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="building_tushare_provider_target_sample_execution_recipe_seed",
        call_ledger=recipe["call_ledger"],
    )
    packet = {
        "packet_key": packet_key,
        "schema_version": "command_center_tushare_provider_target_sample_execution_recipe_packet.v1",
        "status": "target_sample_execution_recipe_seed_ready_no_provider_call"
        if recipe.get("recipe_ready_for_user_confirmation") is True
        else "target_sample_execution_recipe_seed_blocked",
        "task_type": PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_SEED_TASK_TYPE,
        "provider_target_sample_execution_recipe": recipe,
        "provider_target_sample_execution_rows": rows,
        "provider_target_sample_execution_status": recipe.get("status"),
        "provider_target_sample_execution_ready": recipe.get("recipe_ready_for_user_confirmation") is True,
        "provider_target_sample_execution_ready_count": recipe.get("recipe_ready_target_count", 0),
        "provider_target_sample_execution_blocker_count": recipe.get("blocked_recipe_target_count", 0),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": recipe["call_ledger"],
    }
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(packet_key, packet)
    except Exception:
        pass
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="tushare_provider_target_sample_execution_recipe_seed_ready"
        if recipe.get("recipe_ready_for_user_confirmation") is True
        else "tushare_provider_target_sample_execution_recipe_seed_blocked",
        call_ledger=recipe["call_ledger"],
    ) or task


def _provider_target_sample_execution_request_receipt(
    payload: Any,
    *,
    latest_execution_recipe: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload_safe = _safe_payload(payload)
    recipe = dict(latest_execution_recipe or {})
    recipe_visible = bool(recipe)
    latest_scope_hash = str(recipe.get("execution_recipe_scope_hash") or "")
    latest_scope_hash_short = str(recipe.get("execution_recipe_scope_hash_short") or latest_scope_hash[:16])
    requested_scope_hash = str(
        payload_safe.get("execution_recipe_scope_hash")
        or payload_safe.get("execution_recipe_scope_hash_short")
        or payload_safe.get("scope_hash")
        or ""
    ).strip()
    scope_matches = bool(
        latest_scope_hash
        and requested_scope_hash
        and requested_scope_hash in {latest_scope_hash, latest_scope_hash_short}
    )
    operator_confirmed = bool(
        payload_safe.get("operator_approved") is True
        or payload_safe.get("user_confirmed") is True
        or payload_safe.get("manual_confirmation") is True
    )
    payload_targets, unknown_targets = _target_sample_acceptance_requested_targets(payload_safe)
    latest_targets = [str(item) for item in recipe.get("requested_targets") or [] if str(item or "")]
    requested_targets = payload_targets or latest_targets
    latest_rows = [row for row in recipe.get("rows", []) if isinstance(row, Mapping)]
    recipe_selected_apis: list[str] = []
    for row in latest_rows:
        if row.get("requested_for_execution_recipe") is not True:
            continue
        for api in row.get("selected_apis") or []:
            key = str(api or "")
            if key and key not in recipe_selected_apis:
                recipe_selected_apis.append(key)
    selected_apis = _selected_apis(payload_safe, recipe_selected_apis)
    target_scope_matches_latest = bool(latest_targets and sorted(requested_targets) == sorted(latest_targets))
    recipe_ready = bool(
        recipe.get("schema_version") == "tushare_provider_target_sample_execution_recipe.v1"
        and recipe.get("recipe_ready_for_user_confirmation") is True
        and recipe.get("status") == "target_sample_execution_recipe_ready_user_confirmation_required"
        and recipe.get("provider_task_created_by_recipe") is False
        and recipe.get("recipe_external_calls_triggered") is False
        and recipe.get("tushare_called_by_recipe") is False
    )
    target_payload_safe = {
        "apis": selected_apis,
        "acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
        "target_sample_acceptance_groups": requested_targets,
        "execution_recipe_scope_hash_short": latest_scope_hash_short,
        "provider_execution_requires_separate_post_task": True,
    }
    for key in ("ts_code", "trade_date", "start_date", "end_date", "ann_date", "period", "float_date", "limit_type"):
        if payload_safe.get(key) not in (None, ""):
            target_payload_safe[key] = payload_safe.get(key)

    checks = [
        (
            "latest_execution_recipe_visible",
            recipe_visible,
            "latest command_center_tushare_refresh_packet exposes provider_target_sample_execution_recipe",
        ),
        (
            "latest_execution_recipe_ready",
            recipe_ready,
            "recipe is ready for user confirmation and did not create/call provider work",
        ),
        (
            "execution_recipe_scope_hash_bound",
            scope_matches,
            "request must include the latest full or short execution_recipe_scope_hash",
        ),
        (
            "operator_confirmation_recorded",
            operator_confirmed,
            "operator_approved/user_confirmed/manual_confirmation must be true",
        ),
        (
            "target_group_scope_matches_latest_recipe",
            target_scope_matches_latest and not unknown_targets,
            "requested target groups must match the latest recipe and use known groups",
        ),
        (
            "target_payload_safe",
            bool(selected_apis and not _has_sensitive_key(target_payload_safe)),
            "future provider payload contains only selected APIs, known target groups, and safe date/symbol context",
        ),
        (
            "provider_task_still_pending",
            True,
            "this request does not create the future refresh_tushare_facts provider task",
        ),
        (
            "provider_call_ledger_still_required",
            True,
            "real provider acceptance still needs call_ledger evidence after a separate provider task",
        ),
        (
            "production_promotion_still_blocked",
            True,
            "full-interface production promotion remains blocked until durable provider evidence exists",
        ),
        (
            "no_external_no_secret_no_trade_boundary",
            True,
            "request is local-only, keeps credentials hidden, and cannot trade or mutate strategy action",
        ),
    ]
    rows = [
        {
            "criterion": criterion,
            "status": "passed" if passed else "blocked",
            "passed": bool(passed),
            "evidence": evidence,
            "blocking": not bool(passed),
            "cache_get_external_calls": False,
            "react_render_external_calls": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "contains_secret": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
        for criterion, passed, evidence in checks
    ]
    blocker_count = sum(1 for row in rows if row["blocking"])
    if not recipe_visible:
        status = "target_sample_execution_request_blocked_missing_latest_recipe"
        allowed_next_step = "run_or_restore_refresh_tushare_facts_target_sample_recipe"
    elif not recipe_ready:
        status = "target_sample_execution_request_blocked_recipe_not_ready"
        allowed_next_step = "repair_latest_target_sample_execution_recipe"
    elif not scope_matches:
        status = "target_sample_execution_request_blocked_scope_hash_mismatch"
        allowed_next_step = "copy_latest_execution_recipe_scope_hash_then_confirm"
    elif not operator_confirmed:
        status = "target_sample_execution_request_blocked_operator_confirmation_missing"
        allowed_next_step = "set_operator_approved_true_after_manual_review"
    elif unknown_targets or not target_scope_matches_latest:
        status = "target_sample_execution_request_blocked_target_scope_mismatch"
        allowed_next_step = "use_target_groups_from_latest_execution_recipe"
    elif not selected_apis:
        status = "target_sample_execution_request_blocked_empty_api_scope"
        allowed_next_step = "select_target_sample_apis_before_provider_task"
    else:
        status = "target_sample_execution_request_ready_manual_provider_task_pending"
        allowed_next_step = "manually_submit_refresh_tushare_facts_provider_target_sample_task"
    ready = status == "target_sample_execution_request_ready_manual_provider_task_pending"
    receipt = {
        "schema_version": PROVIDER_TARGET_SAMPLE_EXECUTION_REQUEST_SCHEMA_VERSION,
        "status": status,
        "scope": "local_tushare_provider_target_sample_execution_request_no_provider_execution",
        "route": PROVIDER_TARGET_SAMPLE_EXECUTION_REQUEST_ROUTE,
        "task_type": PROVIDER_TARGET_SAMPLE_EXECUTION_REQUEST_TASK_TYPE,
        "target_post_task_route": "POST /api/tasks/refresh-tushare-facts",
        "target_task_type": "refresh_tushare_facts",
        "target_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
        "latest_execution_recipe_visible": recipe_visible,
        "latest_execution_recipe_status": recipe.get("status") or "",
        "latest_execution_recipe_ready_for_user_confirmation": recipe.get("recipe_ready_for_user_confirmation") is True,
        "latest_execution_recipe_scope_hash_short": latest_scope_hash_short,
        "requested_execution_recipe_scope_hash_short": requested_scope_hash[:16],
        "execution_recipe_scope_hash_matches_latest": scope_matches,
        "operator_confirmation_recorded": operator_confirmed,
        "requested_targets": requested_targets,
        "latest_requested_targets": latest_targets,
        "unknown_requested_targets": unknown_targets,
        "target_group_scope_matches_latest_recipe": target_scope_matches_latest,
        "selected_apis": selected_apis,
        "target_payload_safe": target_payload_safe,
        "blocking_criterion_count": blocker_count,
        "row_count": len(rows),
        "local_execution_request_ready": ready,
        "ready_for_manual_provider_task_submission": ready,
        "ready_to_execute_from_cache": False,
        "creates_provider_task": False,
        "provider_task_created": False,
        "provider_task_executed_by_request": False,
        "provider_execution_implemented": False,
        "provider_call_ledger_evidence_done": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_read": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "allowed_next_step": allowed_next_step,
        "not_allowed_next_steps": [
            "call Tushare from this request",
            "call DeepSeek from this request",
            "call GitHub from this request",
            "create provider task from this request",
            "GET cache provider refresh",
            "React render provider refresh",
            "execution request as provider-backed acceptance",
            "execution request as full-interface production completion",
            "strategy action mutation",
            "real trade execution",
        ],
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tushare_provider_target_sample_execution_request",
                "source": "latest target-sample execution recipe and explicit operator confirmation",
                "row_count": len(rows),
                "request_params_safe": {
                    "requested_targets": requested_targets,
                    "selected_apis": selected_apis,
                    "execution_recipe_scope_hash_short": latest_scope_hash_short,
                },
                "data_date": None,
                "local_fetched_at": _now_iso(),
                "call_status": "local_execution_request_provider_task_pending",
                "error_message_safe": "",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This local execution-request ticket binds manual approval and the latest recipe scope for a future provider target-sample task. It does not call Tushare, create that task, promote acceptance, execute trades, or mutate strategy action.",
    }
    return receipt, rows


def run_tushare_provider_target_sample_execution_request(payload: Any = None) -> dict[str, Any]:
    latest_packet = _latest_tushare_target_sample_execution_recipe_packet()
    latest_recipe = latest_packet.get("provider_target_sample_execution_recipe")
    receipt, rows = _provider_target_sample_execution_request_receipt(
        payload,
        latest_execution_recipe=latest_recipe if isinstance(latest_recipe, Mapping) else None,
    )
    packet_key = "command_center_tushare_provider_target_sample_execution_request_packet"
    payload_safe = {
        "provider_target_sample_execution_request_receipt": receipt,
        "provider_target_sample_execution_request_rows": rows,
    }
    task = create_task_record(
        PROVIDER_TARGET_SAMPLE_EXECUTION_REQUEST_TASK_TYPE,
        output_packet_key=packet_key,
        payload=payload_safe,
        current_step="tushare_provider_target_sample_execution_request_queued_local_only",
        warnings=[
            "该任务只生成本地 Tushare target-sample execution-request ticket，不调用 Tushare。",
            "该任务不创建 provider task，不写 Parquet，不证明 LTG-02 生产完成。",
            "该任务不调用 DeepSeek/GitHub，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="building_tushare_provider_target_sample_execution_request",
        call_ledger=receipt["call_ledger"],
    )
    packet = {
        "packet_key": packet_key,
        "schema_version": "command_center_tushare_provider_target_sample_execution_request_packet.v1",
        "status": receipt["status"],
        "task_type": PROVIDER_TARGET_SAMPLE_EXECUTION_REQUEST_TASK_TYPE,
        "receipt": receipt,
        "rows": rows,
        "local_execution_request_ready": receipt["local_execution_request_ready"],
        "ready_for_manual_provider_task_submission": receipt["ready_for_manual_provider_task_submission"],
        "provider_execution_implemented": False,
        "provider_task_executed_by_request": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "call_ledger": receipt["call_ledger"],
    }
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(packet_key, packet)
    except Exception:
        pass
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="tushare_provider_target_sample_execution_request_ready"
        if receipt["local_execution_request_ready"]
        else "tushare_provider_target_sample_execution_request_blocked",
        call_ledger=receipt["call_ledger"],
    ) or task


def _tushare_durable_evidence_recipe_row(
    evidence_key: str,
    *,
    current_status: str,
    target_status: str,
    local_prerequisite_visible: bool,
    direct_provider_evidence_required: bool,
    missing_evidence: list[str],
    target_group: str | None = None,
    selected_apis: list[str] | None = None,
) -> dict[str, Any]:
    production_blocker = bool(direct_provider_evidence_required or not local_prerequisite_visible)
    return {
        "evidence_key": evidence_key,
        "evidence_label": TUSHARE_DURABLE_EVIDENCE_LABELS[evidence_key],
        "target_group": target_group or "",
        "scope": "tushare_durable_evidence_recipe",
        "current_status": current_status,
        "target_status": target_status,
        "selected_apis": list(selected_apis or []),
        "local_prerequisite_visible": bool(local_prerequisite_visible),
        "direct_provider_evidence_required": bool(direct_provider_evidence_required),
        "production_blocker": production_blocker,
        "missing_evidence": list(missing_evidence),
        "provider_backed_acceptance_done": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "provider_task_created_by_recipe": False,
        "provider_execution_implemented_by_recipe": False,
        "provider_refresh_called_by_recipe": False,
        "provider_call_ledger_evidence_done": False,
        "failure_mode_evidence_done": False,
        "request_parameter_provider_window_done": False,
        "parquet_promotion_done": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "recipe_external_calls_triggered": False,
        "tushare_called_by_recipe": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _tushare_durable_evidence_recipe(
    *,
    selected_apis: list[str],
    api_validation_rows: list[dict[str, Any]],
    validation_target_rows: list[dict[str, Any]],
    api_acceptance_audit: dict[str, Any],
    failure_mode_qa_contract: dict[str, Any],
    request_parameter_qa_contract: dict[str, Any],
    provider_target_sample_plan_contract: dict[str, Any],
    provider_target_sample_acceptance_contract: dict[str, Any],
    provider_acceptance_readiness_audit: dict[str, Any],
    provider_acceptance_promotion_audit: dict[str, Any],
    provider_evidence_gap_audit: dict[str, Any],
    provider_sample_activation_receipt: dict[str, Any],
    provider_target_sample_runbook_contract: dict[str, Any],
    provider_target_sample_execution_recipe: dict[str, Any],
) -> dict[str, Any]:
    selected_set = set(selected_apis)
    target_rows_by_key = {str(row.get("target") or ""): row for row in validation_target_rows}
    gap_rows_by_key = {
        str(row.get("target") or ""): row
        for row in provider_evidence_gap_audit.get("rows", [])
        if isinstance(row, Mapping)
    }
    runbook_rows_by_key = {
        str(row.get("target") or ""): row
        for row in provider_target_sample_runbook_contract.get("rows", [])
        if isinstance(row, Mapping)
    }
    execution_rows_by_key = {
        str(row.get("target") or ""): row
        for row in provider_target_sample_execution_recipe.get("rows", [])
        if isinstance(row, Mapping)
    }
    local_recipe_ready = bool(
        api_acceptance_audit.get("schema_version") == "tushare_api_acceptance_audit.v1"
        and failure_mode_qa_contract.get("schema_version") == "tushare_failure_mode_qa_contract.v1"
        and request_parameter_qa_contract.get("schema_version") == "tushare_request_parameter_qa_contract.v1"
        and provider_target_sample_plan_contract.get("schema_version")
        == "tushare_provider_target_sample_plan_contract.v1"
        and provider_target_sample_acceptance_contract.get("schema_version")
        == "tushare_provider_target_sample_acceptance_contract.v1"
        and provider_acceptance_readiness_audit.get("schema_version")
        == "tushare_provider_acceptance_readiness_audit.v1"
        and provider_acceptance_promotion_audit.get("schema_version")
        == "tushare_provider_acceptance_promotion_audit.v1"
        and provider_evidence_gap_audit.get("schema_version") == "tushare_provider_evidence_gap_audit.v1"
        and provider_sample_activation_receipt.get("schema_version")
        == "tushare_provider_sample_activation_receipt.v1"
        and provider_target_sample_runbook_contract.get("schema_version")
        == "tushare_provider_target_sample_runbook_contract.v1"
        and provider_target_sample_execution_recipe.get("schema_version")
        == "tushare_provider_target_sample_execution_recipe.v1"
    )
    route_gate_visible = bool(
        provider_sample_activation_receipt.get("receipt_external_calls_triggered") is False
        and provider_target_sample_execution_recipe.get("post_task_route") == "POST /api/tasks/refresh-tushare-facts"
        and provider_target_sample_execution_recipe.get("provider_task_created_by_recipe") is False
    )
    core_selected_count = sum(1 for api in CORE_REFRESH_APIS if api in selected_set)
    core_local_visible = bool(
        core_selected_count == len(CORE_REFRESH_APIS)
        or api_acceptance_audit.get("core_light_path_acceptance_done") is True
        or api_acceptance_audit.get("selected_api_count", 0)
    )
    rows = [
        _tushare_durable_evidence_recipe_row(
            "post_task_route_and_mode_gate",
            current_status="local_gate_visible" if route_gate_visible else "route_gate_missing",
            target_status="explicit POST task and runtime mode gate stay visible before provider execution",
            local_prerequisite_visible=route_gate_visible,
            direct_provider_evidence_required=False,
            missing_evidence=[] if route_gate_visible else ["explicit POST route and no-cache/render provider boundary"],
        ),
        _tushare_durable_evidence_recipe_row(
            "core_light_api_revalidation",
            current_status="light_path_visible" if core_local_visible else "core_light_revalidation_pending",
            target_status="daily/daily_basic/moneyflow are release-revalidated with safe call ledger rows",
            local_prerequisite_visible=core_local_visible,
            direct_provider_evidence_required=True,
            missing_evidence=[
                "daily/daily_basic/moneyflow release revalidation call ledger",
                "safe row_count/data_date/local_fetched_at/call_status evidence",
                "no token/key and no strategy action mutation review",
            ],
            selected_apis=[api for api in CORE_REFRESH_APIS if api in selected_set],
        ),
    ]
    for target, label, apis in VALIDATION_TARGET_GROUPS:
        evidence_key = f"{target}_provider_sample"
        target_row = target_rows_by_key.get(target, {})
        gap_row = gap_rows_by_key.get(target, {})
        runbook_row = runbook_rows_by_key.get(target, {})
        execution_row = execution_rows_by_key.get(target, {})
        target_selected_apis = [api for api in apis if api in selected_set]
        local_prereq_visible = bool(
            target_row
            and provider_target_sample_plan_contract.get("schema_version")
            == "tushare_provider_target_sample_plan_contract.v1"
            and provider_evidence_gap_audit.get("schema_version") == "tushare_provider_evidence_gap_audit.v1"
        )
        if execution_row.get("recipe_ready_for_user_confirmation") is True:
            current_status = "target_sample_recipe_ready_provider_execution_pending"
        elif gap_row.get("target_sample_acceptance_ready_for_review") is True:
            current_status = "target_sample_review_ready_promotion_pending"
        elif target_selected_apis:
            current_status = "target_sample_local_evidence_visible_provider_pending"
        else:
            current_status = "target_sample_provider_evidence_pending"
        rows.append(
            _tushare_durable_evidence_recipe_row(
                evidence_key,
                current_status=current_status,
                target_status=f"{label} has provider-backed target sample, failure-mode evidence, and promotion review",
                local_prerequisite_visible=local_prereq_visible,
                direct_provider_evidence_required=True,
                missing_evidence=[
                    "explicit provider target-sample POST task",
                    "safe provider call ledger for required APIs",
                    "non-empty sample or classified valid-empty evidence",
                    "failure-mode evidence for permission/empty/parse/provider/missing-param cases",
                    "promotion review that keeps full-interface completion separate",
                ],
                target_group=target,
                selected_apis=target_selected_apis,
            )
        )
        rows[-1]["gap_status"] = gap_row.get("gap_status", "provider_evidence_pending")
        rows[-1]["runbook_status"] = runbook_row.get("runbook_status", "target_sample_runbook_pending")
        rows[-1]["execution_recipe_status"] = execution_row.get(
            "execution_recipe_status",
            "target_sample_execution_recipe_not_requested",
        )
    safe_call_ledger_visible = bool(
        api_acceptance_audit.get("safe_request_params") is True
        and api_acceptance_audit.get("safe_errors_redacted") is True
        and api_acceptance_audit.get("selected_interfaces_have_call_ledger") is True
    )
    failure_and_params_visible = bool(
        failure_mode_qa_contract.get("schema_version") == "tushare_failure_mode_qa_contract.v1"
        and request_parameter_qa_contract.get("schema_version") == "tushare_request_parameter_qa_contract.v1"
    )
    rows.extend(
        [
            _tushare_durable_evidence_recipe_row(
                "safe_provider_call_ledger",
                current_status="local_semantic_audit_visible"
                if safe_call_ledger_visible
                else "safe_provider_call_ledger_pending",
                target_status="all provider rows include safe request params, row count, data date, status, and redacted errors",
                local_prerequisite_visible=safe_call_ledger_visible,
                direct_provider_evidence_required=True,
                missing_evidence=[
                    "safe provider call ledger for every selected API",
                    "row_count/data_date/local_fetched_at/call_status fields",
                    "redacted error_message_safe review",
                ],
            ),
            _tushare_durable_evidence_recipe_row(
                "failure_mode_and_parameter_review",
                current_status="local_failure_parameter_qa_visible"
                if failure_and_params_visible
                else "failure_parameter_qa_pending",
                target_status="provider-backed permission, empty, parse, provider-error, and required-param states are reviewed",
                local_prerequisite_visible=failure_and_params_visible,
                direct_provider_evidence_required=True,
                missing_evidence=[
                    "provider-backed failure-mode evidence",
                    "provider request window/parameter evidence",
                    "permission/no-record/empty/parse/provider-error classification",
                ],
            ),
            _tushare_durable_evidence_recipe_row(
                "full_interface_promotion_review",
                current_status="promotion_ready"
                if provider_acceptance_promotion_audit.get("promotion_ready") is True
                else "promotion_review_pending",
                target_status="all target groups and selected interfaces are promoted only after direct provider evidence",
                local_prerequisite_visible=provider_acceptance_promotion_audit.get("schema_version")
                == "tushare_provider_acceptance_promotion_audit.v1",
                direct_provider_evidence_required=True,
                missing_evidence=[
                    "explicit full-interface provider-backed acceptance marker",
                    "all declared APIs selected and reviewed",
                    "promotion audit with zero provider blockers",
                ],
            ),
            _tushare_durable_evidence_recipe_row(
                "storage_cache_promotion_review",
                current_status="storage_promotion_pending",
                target_status="Parquet/cache promotion is reviewed after provider acceptance and does not commit data artifacts",
                local_prerequisite_visible=provider_acceptance_readiness_audit.get("schema_version")
                == "tushare_provider_acceptance_readiness_audit.v1",
                direct_provider_evidence_required=True,
                missing_evidence=[
                    "storage/cache promotion review",
                    "Parquet dataset scope review for enabled datasets",
                    "artifact scan proving parquet/db/cache outputs stay out of git",
                ],
            ),
        ]
    )
    blocked_rows = [row for row in rows if row["production_blocker"]]
    return {
        "schema_version": TUSHARE_DURABLE_EVIDENCE_SCHEMA_VERSION,
        "status": "tushare_durable_evidence_recipe_ready_provider_pending"
        if local_recipe_ready
        else "tushare_durable_evidence_recipe_blocked_local_contract",
        "scope": "local_tushare_durable_evidence_recipe_no_provider_execution",
        "ltg": "LTG-02",
        "local_recipe_ready": local_recipe_ready,
        "durable_evidence_complete": False,
        "durable_promotion_ready": False,
        "provider_backed_acceptance_done": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "provider_task_created_by_recipe": False,
        "provider_execution_implemented_by_recipe": False,
        "provider_refresh_called_by_recipe": False,
        "provider_call_ledger_evidence_done": False,
        "failure_mode_evidence_done": False,
        "request_parameter_provider_window_done": False,
        "parquet_promotion_done": False,
        "allowed_next_step": "collect_provider_target_sample_call_ledger_failure_mode_full_interface_storage_promotion_evidence",
        "not_allowed_next_steps": [
            "treat durable recipe as provider-backed Tushare acceptance",
            "treat target-sample execution recipe as provider execution",
            "treat matrix/mock/local QA as full-interface acceptance",
            "call Tushare from GET cache",
            "call Tushare from React render",
            "set production_tushare_pipeline_complete from local recipe",
            "promote unselected interfaces as verified",
            "write token/key material to frontend/log/packet/cache",
        ],
        "row_count": len(rows),
        "durable_evidence_blocker_count": len(blocked_rows),
        "blocking_evidence_keys": [row["evidence_key"] for row in blocked_rows],
        "missing_durable_evidence": sorted({item for row in blocked_rows for item in row["missing_evidence"]}),
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "recipe_external_calls_triggered": False,
        "tushare_called_by_recipe": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tushare_durable_evidence_recipe",
                "source": "tushare local audits, target-sample runbook, execution recipe, and stage scope",
                "row_count": len(rows),
                "durable_evidence_blocker_count": len(blocked_rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_durable_evidence_recipe_provider_pending",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This durable evidence recipe fixes the LTG-02 production acceptance proof bundle. It does not call Tushare, create tasks, promote matrix/mock/local evidence, write Parquet, execute trades, mutate strategy action, or prove production Tushare completion.",
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


def _truthy_payload_flag(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y", "passed", "done"}


def _target_sample_acceptance_requested_targets(payload: Any) -> tuple[list[str], list[str]]:
    safe_payload = _safe_payload(payload)
    raw: Any = None
    for key in PROVIDER_TARGET_SAMPLE_ACCEPTANCE_GROUP_KEYS:
        if key in safe_payload:
            raw = safe_payload.get(key)
            break
    if raw is None and "target_sample_acceptance_group" in safe_payload:
        raw = safe_payload.get("target_sample_acceptance_group")
    if raw is None:
        return [], []

    if isinstance(raw, str):
        values = [item.strip() for item in raw.replace(";", ",").split(",")]
    elif isinstance(raw, list):
        values = [str(item).strip() for item in raw]
    else:
        values = [str(raw).strip()]

    known_targets = {target for target, _label, _apis in VALIDATION_TARGET_GROUPS}
    requested: list[str] = []
    unknown: list[str] = []
    for value in values:
        if not value:
            continue
        if value in known_targets and value not in requested:
            requested.append(value)
        elif value not in known_targets and value not in unknown:
            unknown.append(value)
    return requested, unknown


def _target_sample_failure_mode_evidence(payload: Any) -> tuple[bool, int]:
    safe_payload = _safe_payload(payload)
    count = _safe_int(
        safe_payload.get("target_sample_failure_mode_validated_count")
        or safe_payload.get("target_sample_failure_mode_count")
        or safe_payload.get("failure_mode_validated_count")
        or safe_payload.get("failure_mode_count")
    )
    validated = (
        _truthy_payload_flag(safe_payload.get("target_sample_failure_modes_validated"))
        or _truthy_payload_flag(safe_payload.get("failure_modes_validated"))
        or _truthy_payload_flag(safe_payload.get("failure_mode_qa_passed"))
    ) and count >= PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MIN_FAILURE_MODES
    return validated, count


def _provider_target_sample_acceptance_contract(
    *,
    selected_apis: Iterable[str],
    payload: Any,
    api_validation_rows: list[dict[str, Any]],
    validation_target_rows: list[dict[str, Any]],
    provider_target_sample_plan_contract: dict[str, Any],
    call_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    safe_payload = _safe_payload(payload)
    acceptance_mode = str(
        safe_payload.get("acceptance_mode")
        or safe_payload.get("provider_acceptance_mode")
        or "standard_refresh"
    )
    explicit_acceptance_mode = acceptance_mode == PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE
    requested_targets, unknown_targets = _target_sample_acceptance_requested_targets(payload)
    failure_modes_validated, failure_mode_count = _target_sample_failure_mode_evidence(payload)
    validation_by_api = {str(row.get("api") or ""): row for row in api_validation_rows}
    target_by_key = {str(row.get("target") or ""): row for row in validation_target_rows}
    sample_plan_by_target = {
        str(row.get("target") or ""): row for row in provider_target_sample_plan_contract.get("rows", [])
    }
    ledger_by_api = {str(row.get("api") or ""): row for row in call_ledger}
    source_task_external_calls = any(row.get("external_calls_triggered") is True for row in call_ledger)
    source_task_tushare_called = any(row.get("tushare_called") is True for row in call_ledger)

    rows: list[dict[str, Any]] = []
    for target_key, label, apis in VALIDATION_TARGET_GROUPS:
        requested = target_key in requested_targets
        target_apis = list(apis)
        plan_row = sample_plan_by_target.get(target_key, {})
        validation_target_row = target_by_key.get(target_key, {})
        selected_target_apis = [api for api in target_apis if api in set(selected_apis)]
        missing_required_apis = [api for api in target_apis if api not in selected_target_apis]
        missing_call_ledger_apis = [api for api in selected_target_apis if api not in ledger_by_api]
        non_empty_success_apis = [
            api
            for api in selected_target_apis
            if validation_by_api.get(api, {}).get("call_status") == "success"
            and int(validation_by_api.get(api, {}).get("row_count") or 0) > 0
        ]
        validated_empty_apis = [
            api for api in selected_target_apis if validation_by_api.get(api, {}).get("call_status") == "empty"
        ]
        failed_or_blocked_apis = [
            api
            for api in selected_target_apis
            if validation_by_api.get(api, {}).get("call_status") == "failed"
            or str(validation_by_api.get(api, {}).get("call_status") or "").startswith("blocked_")
        ]
        unsafe_ledger_apis = [
            api
            for api in selected_target_apis
            if _has_sensitive_key(ledger_by_api.get(api, {}).get("request_params_safe"))
            or _has_unsafe_error_text(ledger_by_api.get(api, {}).get("error_message_safe"))
        ]
        sample_evidence_sufficient = bool(non_empty_success_apis or (validated_empty_apis and failure_modes_validated))
        blockers: list[str] = []
        if requested:
            if not explicit_acceptance_mode:
                blockers.append("explicit_target_sample_acceptance_mode_missing")
            if missing_required_apis:
                blockers.append("target_api_selection_incomplete")
            if missing_call_ledger_apis:
                blockers.append("call_ledger_evidence_missing")
            if str(plan_row.get("provider_sample_plan_status") or "") != "ready_to_execute_provider_sample":
                blockers.append("target_sample_plan_not_ready")
            if str(validation_target_row.get("readiness") or "") != "validated":
                blockers.append("target_validation_not_complete")
            if failed_or_blocked_apis:
                blockers.append("failed_or_blocked_api_evidence_present")
            if not sample_evidence_sufficient:
                blockers.append("non_empty_or_valid_empty_sample_evidence_missing")
            if not failure_modes_validated:
                blockers.append("failure_mode_evidence_missing")
            if unsafe_ledger_apis:
                blockers.append("unsafe_ledger_evidence")
        if not requested:
            status = "target_sample_acceptance_not_requested"
            meaning = "该目标域本次未进入显式 target-sample acceptance；不得显示为验收完成。"
        elif blockers:
            status = "target_sample_acceptance_blocked"
            meaning = "该目标域已有显式样本验收请求，但证据仍不足或存在阻断项。"
        else:
            status = "target_sample_acceptance_ready_for_review"
            meaning = "该目标域具备可审查的按钮任务样本证据；仍不是全接口生产验收。"
        rows.append(
            {
                "target": target_key,
                "label": label,
                "apis": target_apis,
                "requested_for_acceptance": requested,
                "selected_apis": selected_target_apis,
                "missing_required_apis": missing_required_apis,
                "missing_call_ledger_apis": missing_call_ledger_apis,
                "non_empty_success_apis": non_empty_success_apis,
                "validated_empty_apis": validated_empty_apis,
                "failed_or_blocked_apis": failed_or_blocked_apis,
                "unsafe_ledger_apis": unsafe_ledger_apis,
                "validation_readiness": str(validation_target_row.get("readiness") or "unknown"),
                "provider_sample_plan_status": str(plan_row.get("provider_sample_plan_status") or "unknown"),
                "target_sample_acceptance_status": status,
                "target_sample_acceptance_meaning": meaning,
                "target_sample_acceptance_blockers": blockers,
                "target_sample_acceptance_blocker_count": len(blockers),
                "sample_evidence_sufficient": sample_evidence_sufficient,
                "failure_modes_validated": failure_modes_validated,
                "failure_mode_validated_count": failure_mode_count,
                "provider_backed_target_sample_acceptance_done": False,
                "provider_backed_acceptance_done": False,
                "production_tushare_pipeline_complete": False,
                "full_interface_acceptance_done": False,
                "acceptance_contract_external_calls_triggered": False,
                "cache_get_external_calls": False,
                "react_render_external_calls": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    requested_rows = [row for row in rows if row.get("requested_for_acceptance")]
    ready_rows = [
        row
        for row in requested_rows
        if row.get("target_sample_acceptance_status") == "target_sample_acceptance_ready_for_review"
    ]
    blocked_rows = [
        row
        for row in requested_rows
        if row.get("target_sample_acceptance_status") == "target_sample_acceptance_blocked"
    ]
    contract_blockers = sorted(
        {
            *[str(item) for item in unknown_targets],
            *[
                str(blocker)
                for row in blocked_rows
                for blocker in row.get("target_sample_acceptance_blockers", [])
                if blocker
            ],
        }
    )
    if explicit_acceptance_mode and not requested_targets:
        contract_blockers.append("requested_target_groups_missing")
    ready_for_review = bool(
        explicit_acceptance_mode
        and requested_rows
        and not unknown_targets
        and len(ready_rows) == len(requested_rows)
    )
    status = (
        "target_sample_acceptance_ready_for_review"
        if ready_for_review
        else "target_sample_acceptance_blocked"
        if explicit_acceptance_mode
        else "target_sample_acceptance_not_requested"
    )
    return {
        "schema_version": "tushare_provider_target_sample_acceptance_contract.v1",
        "status": status,
        "scope": "local_target_sample_acceptance_evidence_no_provider_promotion",
        "acceptance_mode": acceptance_mode,
        "explicit_acceptance_mode": explicit_acceptance_mode,
        "requested_targets": requested_targets,
        "unknown_requested_targets": unknown_targets,
        "requested_target_count": len(requested_targets),
        "ready_target_count": len(ready_rows),
        "blocked_target_count": len(blocked_rows),
        "target_sample_acceptance_ready_for_review": ready_for_review,
        "target_sample_acceptance_done": ready_for_review,
        "provider_backed_target_sample_acceptance_done": False,
        "provider_backed_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "full_interface_acceptance_done": False,
        "failure_modes_validated": failure_modes_validated,
        "failure_mode_validated_count": failure_mode_count,
        "required_failure_mode_count": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MIN_FAILURE_MODES,
        "contract_blockers": contract_blockers,
        "blocking_criterion_count": len(contract_blockers),
        "source_task_external_calls_triggered": source_task_external_calls,
        "source_task_tushare_called": source_task_tushare_called,
        "acceptance_contract_external_calls_triggered": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_count": len(rows),
        "rows": rows,
        "note": "Explicit target-sample acceptance records reviewable target-domain evidence from the button task only. It does not call Tushare by itself, does not promote fake/local evidence, and is not full-interface production acceptance.",
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


def _trade_cal_acceptance_rows_from_data(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if hasattr(data, "empty") and hasattr(data, "where") and hasattr(data, "notna"):
        if bool(getattr(data, "empty", True)):
            return []
        return data.head(TRADE_CAL_PROVIDER_ACCEPTANCE_MAX_ROWS).where(data.notna(), None).to_dict("records")
    if isinstance(data, list):
        return [dict(item) for item in data if isinstance(item, Mapping)][:TRADE_CAL_PROVIDER_ACCEPTANCE_MAX_ROWS]
    if isinstance(data, Mapping):
        rows = data.get("rows")
        if isinstance(rows, list):
            return [dict(item) for item in rows if isinstance(item, Mapping)][:TRADE_CAL_PROVIDER_ACCEPTANCE_MAX_ROWS]
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


def _parse_trade_cal_date(value: Any) -> _dt.date | None:
    text = str(value or "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        try:
            return _dt.datetime.strptime(digits[:8], "%Y%m%d").date()
        except ValueError:
            return None
    try:
        return _dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _trade_cal_is_open(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "open", "交易"}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _trade_cal_provider_acceptance_fields(
    api: str,
    *,
    params: dict[str, Any],
    rows: list[dict[str, Any]],
    payload: Any,
    call_status: str,
) -> dict[str, Any]:
    if api != "trade_cal":
        return {}

    safe_payload = _safe_payload(payload)
    acceptance_mode = str(
        safe_payload.get("acceptance_mode")
        or safe_payload.get("provider_acceptance_mode")
        or "standard_refresh"
    )
    explicit_acceptance_mode = acceptance_mode == TRADE_CAL_PROVIDER_ACCEPTANCE_MODE
    dates = sorted(
        {
            parsed
            for parsed in (_parse_trade_cal_date(row.get("cal_date") or row.get("trade_date") or row.get("date")) for row in rows)
            if parsed is not None
        }
    )
    open_dates = sorted(
        {
            parsed
            for row in rows
            if _trade_cal_is_open(row.get("is_open", 1))
            for parsed in [_parse_trade_cal_date(row.get("cal_date") or row.get("trade_date") or row.get("date"))]
            if parsed is not None
        }
    )
    closed_dates = sorted(
        {
            parsed
            for row in rows
            if not _trade_cal_is_open(row.get("is_open", 1))
            for parsed in [_parse_trade_cal_date(row.get("cal_date") or row.get("trade_date") or row.get("date"))]
            if parsed is not None
        }
    )
    start_date = dates[0] if dates else None
    end_date = dates[-1] if dates else None
    window_days = ((end_date - start_date).days + 1) if start_date and end_date else 0
    latest_completed = max((day for day in open_dates if day <= _dt.date.today()), default=max(open_dates, default=None))
    schema_fields_present = bool(rows) and all(
        isinstance(row, Mapping) and "cal_date" in row and "is_open" in row for row in rows
    )
    failure_mode_count = _safe_int(safe_payload.get("failure_mode_validated_count") or safe_payload.get("failure_mode_count"))
    replay_scenario_count = _safe_int(
        safe_payload.get("freshness_replay_scenario_count") or safe_payload.get("replay_scenario_count")
    )
    freshness_replay_passed = (
        safe_payload.get("freshness_replay_passed") is True
        or safe_payload.get("freshness_gate_replay_passed") is True
    ) and replay_scenario_count >= TRADE_CAL_PROVIDER_ACCEPTANCE_MIN_REPLAY_SCENARIOS
    failure_modes_validated = (
        safe_payload.get("failure_modes_validated") is True
        or safe_payload.get("failure_mode_qa_passed") is True
    ) and failure_mode_count >= TRADE_CAL_PROVIDER_ACCEPTANCE_MIN_FAILURE_MODES
    minimum_window_days_passed = window_days >= TRADE_CAL_PROVIDER_ACCEPTANCE_MIN_WINDOW_DAYS
    provider_backed_done = bool(
        explicit_acceptance_mode
        and call_status == "success"
        and schema_fields_present
        and minimum_window_days_passed
        and open_dates
        and closed_dates
        and latest_completed
        and freshness_replay_passed
        and failure_modes_validated
    )
    blockers = []
    if not explicit_acceptance_mode:
        blockers.append("explicit_acceptance_mode_missing")
    if call_status != "success":
        blockers.append("trade_cal_call_not_success")
    if not schema_fields_present:
        blockers.append("cal_date_is_open_schema_missing")
    if not minimum_window_days_passed:
        blockers.append("minimum_730_day_window_missing")
    if not open_dates:
        blockers.append("open_day_rows_missing")
    if not closed_dates:
        blockers.append("closed_day_rows_missing")
    if not latest_completed:
        blockers.append("latest_completed_trade_date_missing")
    if not freshness_replay_passed:
        blockers.append("freshness_replay_evidence_missing")
    if not failure_modes_validated:
        blockers.append("failure_mode_evidence_missing")

    return {
        "acceptance_mode": acceptance_mode,
        "provider_called": call_status in {"success", "empty", "failed"},
        "provider_acceptance_marker": TRADE_CAL_PROVIDER_ACCEPTANCE_MODE if provider_backed_done else "",
        "provider_backed_long_window_acceptance_done": provider_backed_done,
        "provider_backed_trade_cal_acceptance_done": provider_backed_done,
        "production_freshness_gate_complete": False,
        "production_tushare_pipeline_complete": False,
        "trade_cal_schema_fields_present": schema_fields_present,
        "window_start": start_date.isoformat() if start_date else None,
        "window_end": end_date.isoformat() if end_date else None,
        "window_days": window_days,
        "minimum_acceptance_window_days": TRADE_CAL_PROVIDER_ACCEPTANCE_MIN_WINDOW_DAYS,
        "minimum_window_days_passed": minimum_window_days_passed,
        "open_day_count": len(open_dates),
        "closed_day_count": len(closed_dates),
        "latest_completed_trade_date": latest_completed.isoformat() if latest_completed else None,
        "latest_completed_trade_date_resolved": bool(latest_completed),
        "freshness_replay_passed": freshness_replay_passed,
        "freshness_replay_scenario_count": replay_scenario_count,
        "failure_modes_validated": failure_modes_validated,
        "failure_mode_validated_count": failure_mode_count,
        "provider_acceptance_required_failure_mode_count": TRADE_CAL_PROVIDER_ACCEPTANCE_MIN_FAILURE_MODES,
        "provider_acceptance_required_replay_scenario_count": TRADE_CAL_PROVIDER_ACCEPTANCE_MIN_REPLAY_SCENARIOS,
        "provider_acceptance_blockers": blockers,
        "provider_acceptance_blocker_count": len(blockers),
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


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


def _call_ledger_row(
    api: str,
    *,
    params: dict[str, Any],
    result: dict[str, Any],
    parquet_result: dict[str, Any] | None,
    now: str,
    payload: Any = None,
) -> dict[str, Any]:
    data = result.get("data") if isinstance(result, Mapping) else None
    rows = _rows_from_data(data)
    acceptance_rows = _trade_cal_acceptance_rows_from_data(data) if api == "trade_cal" else rows
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
    row = {
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
    row.update(
        _trade_cal_provider_acceptance_fields(
            api,
            params=params,
            rows=acceptance_rows,
            payload=payload,
            call_status=call_status,
        )
    )
    return row


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
    try:
        previous_packet_raw = SQLiteMetaStore(SQLITE_META_PATH).read_packet(output_packet_key)
    except Exception:
        previous_packet_raw = {}
    previous_packet = dict(previous_packet_raw) if isinstance(previous_packet_raw, Mapping) else {}
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
        call_ledger.append(
            _call_ledger_row(
                api,
                params=params,
                result=dict(result),
                parquet_result=parquet_result,
                now=now,
                payload=payload,
            )
        )

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
    provider_target_sample_acceptance_contract = _provider_target_sample_acceptance_contract(
        selected_apis=selected_apis,
        payload=payload,
        api_validation_rows=api_validation_rows,
        validation_target_rows=validation_target_rows,
        provider_target_sample_plan_contract=provider_target_sample_plan_contract,
        call_ledger=call_ledger,
    )
    provider_acceptance_readiness_audit = _provider_acceptance_readiness_audit(
        api_validation_rows=api_validation_rows,
        validation_target_rows=validation_target_rows,
        api_acceptance_audit=api_acceptance_audit,
    )
    provider_acceptance_promotion_audit = _provider_acceptance_promotion_audit(
        api_validation_rows=api_validation_rows,
        validation_target_rows=validation_target_rows,
        api_acceptance_audit=api_acceptance_audit,
        provider_target_sample_plan_contract=provider_target_sample_plan_contract,
        provider_acceptance_readiness_audit=provider_acceptance_readiness_audit,
        call_ledger=call_ledger,
    )
    provider_evidence_gap_audit = _provider_evidence_gap_audit(
        api_validation_rows=api_validation_rows,
        validation_target_rows=validation_target_rows,
        provider_target_sample_plan_contract=provider_target_sample_plan_contract,
        provider_acceptance_promotion_audit=provider_acceptance_promotion_audit,
        call_ledger=call_ledger,
        provider_target_sample_acceptance_contract=provider_target_sample_acceptance_contract,
    )
    provider_sample_readiness_receipt = _provider_sample_readiness_receipt(
        provider_target_sample_plan_contract=provider_target_sample_plan_contract,
        provider_target_sample_acceptance_contract=provider_target_sample_acceptance_contract,
        provider_acceptance_readiness_audit=provider_acceptance_readiness_audit,
        provider_acceptance_promotion_audit=provider_acceptance_promotion_audit,
        provider_evidence_gap_audit=provider_evidence_gap_audit,
    )
    provider_sample_activation_receipt = _provider_sample_activation_receipt(
        provider_target_sample_plan_contract=provider_target_sample_plan_contract,
        provider_sample_readiness_receipt=provider_sample_readiness_receipt,
        provider_acceptance_promotion_audit=provider_acceptance_promotion_audit,
        provider_evidence_gap_audit=provider_evidence_gap_audit,
    )
    provider_target_sample_runbook_contract = _provider_target_sample_runbook_contract(
        selected_apis=selected_apis,
        payload=payload,
        provider_target_sample_plan_contract=provider_target_sample_plan_contract,
        provider_target_sample_acceptance_contract=provider_target_sample_acceptance_contract,
        provider_evidence_gap_audit=provider_evidence_gap_audit,
        provider_sample_activation_receipt=provider_sample_activation_receipt,
    )
    provider_target_sample_execution_recipe = _provider_target_sample_execution_recipe(
        provider_target_sample_runbook_contract=provider_target_sample_runbook_contract,
        provider_sample_activation_receipt=provider_sample_activation_receipt,
    )
    tushare_durable_evidence_recipe = _tushare_durable_evidence_recipe(
        selected_apis=selected_apis,
        api_validation_rows=api_validation_rows,
        validation_target_rows=validation_target_rows,
        api_acceptance_audit=api_acceptance_audit,
        failure_mode_qa_contract=failure_mode_qa_contract,
        request_parameter_qa_contract=request_parameter_qa_contract,
        provider_target_sample_plan_contract=provider_target_sample_plan_contract,
        provider_target_sample_acceptance_contract=provider_target_sample_acceptance_contract,
        provider_acceptance_readiness_audit=provider_acceptance_readiness_audit,
        provider_acceptance_promotion_audit=provider_acceptance_promotion_audit,
        provider_evidence_gap_audit=provider_evidence_gap_audit,
        provider_sample_activation_receipt=provider_sample_activation_receipt,
        provider_target_sample_runbook_contract=provider_target_sample_runbook_contract,
        provider_target_sample_execution_recipe=provider_target_sample_execution_recipe,
    )
    prior_direct_evidence_rows = _direct_evidence_rows_from_packet(previous_packet)
    direct_evidence_rows = _direct_evidence_rows_from_packet(
        {"prior_direct_evidence_rows": prior_direct_evidence_rows, "call_ledger": call_ledger}
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
        "provider_target_sample_acceptance_contract": provider_target_sample_acceptance_contract,
        "provider_target_sample_acceptance_rows": provider_target_sample_acceptance_contract["rows"],
        "provider_target_sample_acceptance_status": provider_target_sample_acceptance_contract["status"],
        "provider_acceptance_readiness_audit": provider_acceptance_readiness_audit,
        "provider_acceptance_readiness_rows": provider_acceptance_readiness_audit["rows"],
        "provider_acceptance_readiness_status": provider_acceptance_readiness_audit["status"],
        "provider_acceptance_promotion_audit": provider_acceptance_promotion_audit,
        "provider_acceptance_promotion_rows": provider_acceptance_promotion_audit["rows"],
        "provider_acceptance_promotion_status": provider_acceptance_promotion_audit["status"],
        "provider_evidence_gap_audit": provider_evidence_gap_audit,
        "provider_evidence_gap_rows": provider_evidence_gap_audit["rows"],
        "provider_evidence_gap_status": provider_evidence_gap_audit["status"],
        "provider_sample_readiness_receipt": provider_sample_readiness_receipt,
        "provider_sample_readiness_rows": provider_sample_readiness_receipt["rows"],
        "provider_sample_readiness_status": provider_sample_readiness_receipt["status"],
        "provider_sample_activation_receipt": provider_sample_activation_receipt,
        "provider_sample_activation_rows": provider_sample_activation_receipt["rows"],
        "provider_sample_activation_status": provider_sample_activation_receipt["status"],
        "provider_target_sample_runbook_contract": provider_target_sample_runbook_contract,
        "provider_target_sample_runbook_rows": provider_target_sample_runbook_contract["rows"],
        "provider_target_sample_runbook_status": provider_target_sample_runbook_contract["status"],
        "provider_target_sample_execution_recipe": provider_target_sample_execution_recipe,
        "provider_target_sample_execution_rows": provider_target_sample_execution_recipe["rows"],
        "provider_target_sample_execution_status": provider_target_sample_execution_recipe["status"],
        "tushare_durable_evidence_recipe": tushare_durable_evidence_recipe,
        "tushare_durable_evidence_rows": tushare_durable_evidence_recipe["rows"],
        "tushare_durable_evidence_status": tushare_durable_evidence_recipe["status"],
        "api_validation_matrix_policy": {
            "scope": "selected APIs use real task call_ledger; unselected APIs are capability matrix only.",
            "selected_apis": list(selected_apis),
            "matrix_only_apis": [row["api"] for row in api_validation_rows if row.get("validation_scope") == "capability_matrix_only"],
            "target_readiness_scope": "目标领域 readiness 只汇总本次按钮任务的 call_ledger；matrix_only 不代表真实验证。",
            "acceptance_audit_scope": "api_acceptance_audit 只审计 call_ledger 语义和安全边界，不发起 provider 调用。",
            "provider_acceptance_readiness_scope": "provider_acceptance_readiness_audit 只汇总生产验收阻断项；不把 fake/local/matrix 证据当 provider-backed acceptance。",
            "provider_acceptance_promotion_scope": "provider_acceptance_promotion_audit 只读已有 call_ledger；没有显式 full-interface provider-backed evidence 不允许提升。",
            "provider_evidence_gap_scope": "provider_evidence_gap_audit 只读本地 call_ledger/target/sample-plan/promotion 证据，列出目标域缺口；不调用 provider，不提升验收。",
            "failure_mode_qa_scope": "failure_mode_qa_contract 只分类现有 call_ledger 的 empty/permission/parse/missing-param/provider-error 状态；不发起 provider 调用。",
            "request_parameter_qa_scope": "request_parameter_qa_contract 只审计安全参数、ts_code 预检和日期上下文字段；不发起 provider 调用。",
            "provider_target_sample_plan_scope": "provider_target_sample_plan_contract 只声明未来真实样本验收所需目标域、接口、窗口上下文和证据；不发起 provider 调用。",
            "provider_target_sample_acceptance_scope": "provider_target_sample_acceptance_contract 只审查显式 target-sample acceptance payload 和本次按钮任务 call_ledger；不调用 provider，不提升为全接口生产验收。",
            "call_ledger_required_fields": list(CALL_LEDGER_REQUIRED_FIELDS),
            "cache_get_external_calls": False,
            "button_gated_external_calls_only": True,
            "does_not_claim_unselected_apis_verified": True,
            "full_interface_acceptance_done": api_acceptance_audit["full_interface_acceptance_done"],
            "provider_backed_acceptance_done": provider_acceptance_readiness_audit["provider_backed_acceptance_done"],
            "provider_acceptance_promotion_ready": provider_acceptance_promotion_audit["promotion_ready"],
            "provider_acceptance_promotion_calls_provider": False,
            "provider_evidence_gap_calls_provider": False,
            "provider_evidence_gaps_pending": provider_evidence_gap_audit["target_with_gap_count"] > 0,
            "provider_target_sample_acceptance_calls_provider": False,
            "provider_target_sample_acceptance_ready_for_review": provider_target_sample_acceptance_contract[
                "target_sample_acceptance_ready_for_review"
            ],
            "provider_target_sample_acceptance_is_full_interface_acceptance": False,
            "provider_sample_readiness_receipt_scope": "provider_sample_readiness_receipt 只说明下一步显式 POST 样本验收是否可执行；不调用 provider，不提升生产验收。",
            "provider_sample_readiness_receipt_calls_provider": False,
            "provider_sample_ready_for_explicit_task": provider_sample_readiness_receipt[
                "ready_for_explicit_provider_sample_task"
            ],
            "provider_sample_activation_receipt_scope": "provider_sample_activation_receipt 是显式 provider 样本验收前的本地清单；不调用 provider，不创建任务，不证明生产完成。",
            "provider_sample_activation_receipt_calls_provider": False,
            "provider_sample_activation_receipt_is_not_completion": True,
            "provider_target_sample_runbook_scope": "provider_target_sample_runbook_contract 只固定显式目标域 provider 样本验收清单和 promotion blocker；不调用 provider，不证明生产完成。",
            "provider_target_sample_runbook_calls_provider": False,
            "provider_target_sample_runbook_is_not_acceptance": True,
            "provider_target_sample_execution_recipe_scope": "provider_target_sample_execution_recipe 只固定下一次显式 provider target-sample 执行顺序和证据清单；不调用 provider、不创建任务、不证明生产完成。",
            "provider_target_sample_execution_recipe_calls_provider": False,
            "provider_target_sample_execution_recipe_creates_task": False,
            "provider_target_sample_execution_recipe_is_not_acceptance": True,
            "tushare_durable_evidence_recipe_scope": "tushare_durable_evidence_recipe 只固定 LTG-02 全接口生产验收证据缺口；不调用 provider、不创建任务、不证明生产完成。",
            "tushare_durable_evidence_recipe_calls_provider": False,
            "tushare_durable_evidence_recipe_creates_task": False,
            "tushare_durable_evidence_recipe_is_not_acceptance": True,
            "tushare_durable_evidence_recipe_is_not_production_completion": True,
            "production_tushare_pipeline_complete": provider_acceptance_readiness_audit["production_tushare_pipeline_complete"],
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        "call_ledger": call_ledger,
        "prior_direct_evidence_rows": direct_evidence_rows,
        "prior_direct_evidence_row_count": len(direct_evidence_rows),
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
        "provider_target_sample_acceptance_ready_for_review": provider_target_sample_acceptance_contract[
            "target_sample_acceptance_ready_for_review"
        ],
        "provider_target_sample_acceptance_requested_count": provider_target_sample_acceptance_contract[
            "requested_target_count"
        ],
        "provider_target_sample_acceptance_ready_count": provider_target_sample_acceptance_contract["ready_target_count"],
        "provider_target_sample_acceptance_blocker_count": provider_target_sample_acceptance_contract[
            "blocking_criterion_count"
        ],
        "provider_acceptance_production_blocker_count": provider_acceptance_readiness_audit["production_blocker_count"],
        "provider_acceptance_promotion_blocker_count": provider_acceptance_promotion_audit["blocking_criterion_count"],
        "provider_acceptance_promotion_ready": provider_acceptance_promotion_audit["promotion_ready"],
        "provider_acceptance_promotion_evidence_row_count": provider_acceptance_promotion_audit["provider_evidence_row_count"],
        "provider_evidence_gap_target_count": provider_evidence_gap_audit["target_count"],
        "provider_evidence_gap_target_with_gap_count": provider_evidence_gap_audit["target_with_gap_count"],
        "provider_evidence_gap_blocker_count": provider_evidence_gap_audit["gap_blocker_count"],
        "provider_evidence_gap_target_sample_ready_count": provider_evidence_gap_audit[
            "target_sample_acceptance_ready_count"
        ],
        "provider_sample_readiness_status": provider_sample_readiness_receipt["status"],
        "provider_sample_ready_for_explicit_task": provider_sample_readiness_receipt[
            "ready_for_explicit_provider_sample_task"
        ],
        "provider_sample_readiness_blocker_count": provider_sample_readiness_receipt["blocked_readiness_count"],
        "provider_sample_activation_status": provider_sample_activation_receipt["status"],
        "provider_sample_activation_ready_for_explicit_task": provider_sample_activation_receipt[
            "ready_for_explicit_provider_sample_task"
        ],
        "provider_sample_activation_blocker_count": provider_sample_activation_receipt["blocking_criterion_count"],
        "provider_target_sample_runbook_status": provider_target_sample_runbook_contract["status"],
        "provider_target_sample_runbook_ready": provider_target_sample_runbook_contract["runbook_ready"],
        "provider_target_sample_runbook_ready_count": provider_target_sample_runbook_contract[
            "runbook_ready_target_count"
        ],
        "provider_target_sample_runbook_blocker_count": provider_target_sample_runbook_contract[
            "blocked_runbook_target_count"
        ],
        "provider_target_sample_execution_status": provider_target_sample_execution_recipe["status"],
        "provider_target_sample_execution_ready": provider_target_sample_execution_recipe[
            "recipe_ready_for_user_confirmation"
        ],
        "provider_target_sample_execution_ready_count": provider_target_sample_execution_recipe[
            "recipe_ready_target_count"
        ],
        "provider_target_sample_execution_blocker_count": provider_target_sample_execution_recipe[
            "blocked_recipe_target_count"
        ],
        "tushare_durable_evidence_recipe_ready": tushare_durable_evidence_recipe["local_recipe_ready"],
        "tushare_durable_evidence_blocker_count": tushare_durable_evidence_recipe[
            "durable_evidence_blocker_count"
        ],
        "tushare_durable_evidence_row_count": tushare_durable_evidence_recipe["row_count"],
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
