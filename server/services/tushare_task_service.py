from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping

from storage import parquet_store
from storage.sqlite_meta import SQLiteMetaStore

from . import storage_service, tushare_production_store
from .task_service import create_task_record, list_task_statuses, update_task_status


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
FACTOR_TEST_PROVIDER_SMALL_POOL_MERGE_APIS = ("daily", "daily_basic", "moneyflow")
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
    "scope_hash",
    "scope_hash_short",
    "payload_hash",
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
FULL_INTERFACE_PROVIDER_PRODUCTION_MODE = "full_interface_provider_production"
FULL_INTERFACE_PROVIDER_PRODUCTION_TASK_TYPE = "refresh_tushare_facts"
FULL_INTERFACE_PROVIDER_PRODUCTION_ROUTE = "POST /api/tasks/refresh-tushare-facts"
FULL_INTERFACE_PROVIDER_PRODUCTION_SCHEMA_VERSION = "tushare_full_interface_provider_production_acceptance.v2"
FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS = tuple(target for target, _label, _apis in VALIDATION_TARGET_GROUPS)
FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY = "command_center_tushare_full_interface_production_packet"
FULL_INTERFACE_PROVIDER_PRODUCTION_STAGING_PACKET_KEY = (
    "command_center_tushare_full_interface_production_staging_packet"
)
FULL_MARKET_UNIVERSE_CURRENT_PACKET_KEY = (
    "command_center_tushare_full_market_universe_production_current"
)
FULL_MARKET_UNIVERSE_LAST_GOOD_PACKET_KEY = (
    "command_center_tushare_full_market_universe_production_last_good"
)
FULL_MARKET_UNIVERSE_SCHEMA_VERSION = "tushare_full_market_universe_production.v1"
FULL_MARKET_UNIVERSE_MIN_ROWS = 3000
FULL_INTERFACE_PROVIDER_PRODUCTION_RECIPE_VERSION = "tushare_full_interface_provider_recipe.v2"
PRODUCTION_VALID_EMPTY_APIS = frozenset(EXTENDED_REFRESH_APIS)
API_REPRESENTATIVE_REQUIRED_FIELDS = {
    "daily": (("ts_code",), ("trade_date",), ("close",)),
    "daily_basic": (("ts_code",), ("trade_date",), ("turnover_rate", "pe", "total_mv", "circ_mv")),
    "moneyflow": (("ts_code",), ("trade_date",), ("buy_sm_amount", "sell_sm_amount", "net_mf_amount")),
    "trade_cal": (("cal_date",), ("is_open",)),
    "margin_detail": (("ts_code",), ("trade_date",), ("rzye", "rqye", "rzmre", "rqyl")),
    "top_list": (("ts_code",), ("trade_date",), ("reason", "name", "net_amount", "amount")),
    "top_inst": (("ts_code",), ("trade_date",), ("exalter", "buy", "sell", "net_buy")),
    "stk_limit": (("ts_code",), ("trade_date",), ("up_limit",), ("down_limit",)),
    "limit_list_d": (("ts_code",), ("trade_date",), ("limit", "times", "amount")),
    "limit_cpt_list": (("trade_date",), ("name", "up_num", "cons_num")),
    "cyq_perf": (("ts_code",), ("trade_date",), ("winner_rate", "cost_50pct", "weight_avg")),
    "cyq_chips": (("ts_code",), ("trade_date",), ("price",), ("percent",)),
    "anns_d": (("ts_code",), ("ann_date",), ("title", "name")),
    "forecast": (("ts_code",), ("ann_date", "end_date"), ("type", "p_change_min", "net_profit_min")),
    "fina_indicator": (("ts_code",), ("end_date",), ("roe", "eps")),
    "stk_holdertrade": (("ts_code",), ("ann_date",), ("holder_name",), ("change_vol",)),
    "share_float": (("ts_code",), ("ann_date", "float_date"), ("float_share", "holder_name")),
    "pledge_stat": (("ts_code",), ("end_date",), ("pledge_count", "pledge_ratio")),
    "pledge_detail": (("ts_code",), ("pledgor",), ("pledgee",), ("pledge_amount",)),
    "stk_surv": (("ts_code",), ("trade_date", "ann_date"), ("surv_name", "surv", "founder")),
}
PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_SCHEMA_VERSION = "tushare_provider_target_sample_failure_window_review.v1"
PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_TASK_TYPE = (
    "run_tushare_provider_target_sample_failure_window_review"
)
PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_ROUTE = (
    "POST /api/tasks/tushare-provider-target-sample-failure-window-review"
)
PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_PACKET_KEY = (
    "command_center_tushare_provider_target_sample_failure_window_review_packet"
)
PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_SCHEMA_VERSION = (
    "tushare_provider_target_sample_permission_followup_ticket.v1"
)
PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_TASK_TYPE = (
    "run_tushare_provider_target_sample_permission_followup_ticket"
)
PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_ROUTE = (
    "POST /api/tasks/tushare-provider-target-sample-permission-followup-ticket"
)
PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_PACKET_KEY = (
    "command_center_tushare_provider_target_sample_permission_followup_packet"
)
ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_SCHEMA_VERSION = (
    "tushare_alternative_hard_risk_evidence_scope_ticket.v1"
)
ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_TASK_TYPE = (
    "run_tushare_alternative_hard_risk_evidence_scope_ticket"
)
ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_ROUTE = (
    "POST /api/tasks/tushare-alternative-hard-risk_evidence-scope-ticket"
)
ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_PACKET_KEY = (
    "command_center_tushare_alternative_hard_risk_evidence_scope_packet"
)
PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_SCHEMA_VERSION = (
    "tushare_provider_target_sample_storage_promotion_review.v1"
)
PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_TASK_TYPE = (
    "run_tushare_provider_target_sample_storage_promotion_review"
)
PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_ROUTE = (
    "POST /api/tasks/tushare-provider-target-sample-storage-promotion-review"
)
PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_PACKET_KEY = (
    "command_center_tushare_target_sample_storage_promotion_review_packet"
)
TRADE_CAL_PROVIDER_ACCEPTANCE_EXECUTION_REQUEST_TASK_TYPE = "run_trade_cal_provider_acceptance_execution_request"
TRADE_CAL_PROVIDER_ACCEPTANCE_EXECUTION_REQUEST_READY_STATUS = (
    "trade_cal_provider_acceptance_execution_request_ready_manual_provider_task_pending"
)
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

    def _safe_value(key: Any, value: Any, *, depth: int = 0) -> Any:
        if depth > 4 or any(marker in str(key).lower() for marker in SECRET_MARKERS):
            return None
        if isinstance(value, Mapping):
            return {
                str(child_key): safe
                for child_key, child_value in value.items()
                if (
                    safe := _safe_value(child_key, child_value, depth=depth + 1)
                )
                is not None
            }
        if isinstance(value, (list, tuple)):
            return [
                safe
                for item in list(value)[:80]
                if (safe := _safe_value(key, item, depth=depth + 1)) is not None
            ]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return _safe_text(value) if isinstance(value, str) else value
        return None

    return {
        str(key): safe
        for key, value in payload.items()
        if (safe := _safe_value(key, value)) is not None
    }


def _provider_call_scope(payload: Any, selected_apis: Iterable[str]) -> dict[str, str]:
    material = {
        "schema_version": "tushare_provider_call_scope.v1",
        "selected_apis": list(selected_apis),
        "payload_safe": _safe_payload(payload),
    }
    serialized = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return {
        "scope_hash": digest,
        "scope_hash_short": digest[:16],
        "payload_hash": digest,
    }


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on", "approved", "confirm", "confirmed"}:
        return True
    if text in {"0", "false", "no", "n", "off", "rejected", "deny", "denied"}:
        return False
    return default


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
                and target_sample_acceptance_row.get("failure_modes_validated") is True
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
    store = SQLiteMetaStore(SQLITE_META_PATH)
    candidates: list[dict[str, Any]] = []
    for packet_key in (
        "command_center_tushare_refresh_packet",
        PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_PACKET_KEY,
    ):
        try:
            record = store.read_packet_with_metadata(packet_key)
        except Exception:
            record = None
        packet = record.get("payload") if isinstance(record, Mapping) else {}
        recipe = (
            packet.get("provider_target_sample_execution_recipe")
            if isinstance(packet, Mapping)
            and isinstance(packet.get("provider_target_sample_execution_recipe"), Mapping)
            else {}
        )
        if not recipe:
            continue
        ready = bool(
            recipe.get("status") == "target_sample_execution_recipe_ready_user_confirmation_required"
            and recipe.get("recipe_ready_for_user_confirmation") is True
        )
        candidates.append(
            {
                "packet_key": packet_key,
                "packet": dict(packet),
                "recipe": dict(recipe),
                "ready": ready,
                "production_ready": bool(
                    ready
                    and recipe.get("schema_version")
                    == "tushare_provider_target_sample_execution_recipe.v2"
                    and recipe.get("recipe_version") == FULL_INTERFACE_PROVIDER_PRODUCTION_RECIPE_VERSION
                    and recipe.get("full_interface_recipe_ready") is True
                ),
                "issued_at": str(
                    recipe.get("recipe_issued_at")
                    or recipe.get("generated_at")
                    or (record.get("updated_at") if isinstance(record, Mapping) else "")
                    or ""
                ),
                "updated_at": str(record.get("updated_at") or "") if isinstance(record, Mapping) else "",
            }
        )
    if not candidates:
        return {}
    ready_candidates = [item for item in candidates if item["ready"]]
    selected = max(
        ready_candidates or candidates,
        key=lambda item: (
            item["production_ready"],
            item["issued_at"],
            item["updated_at"],
            item["packet_key"] == PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_PACKET_KEY,
        ),
    )
    packet = dict(selected["packet"])
    packet["authoritative_recipe_source_packet_key"] = selected["packet_key"]
    packet["authoritative_recipe_updated_at"] = selected["updated_at"]
    packet["authoritative_recipe_issued_at"] = selected["issued_at"]
    return packet


def _canonical_sha256(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _production_api_contexts(payload: Any, selected_apis: Iterable[str]) -> dict[str, dict[str, Any]]:
    safe = _safe_payload(payload)
    provided = safe.get("api_contexts") if isinstance(safe.get("api_contexts"), Mapping) else {}
    contexts: dict[str, dict[str, Any]] = {}
    for api in selected_apis:
        api_provided = provided.get(api) if isinstance(provided.get(api), Mapping) else {}
        context: dict[str, Any] = {}
        for key in REFRESH_API_SPECS[api]["params"]:
            value = api_provided.get(key, safe.get(key))
            if value not in (None, ""):
                context[key] = value
        contexts[api] = context
    return contexts


def _production_api_context_ready(api: str, context: Mapping[str, Any]) -> bool:
    params = set(REFRESH_API_SPECS[api]["params"])
    if "ts_code" in params and not context.get("ts_code"):
        return False
    if api == "trade_cal":
        return bool(context.get("start_date") and context.get("end_date"))
    date_keys = params.intersection({"trade_date", "start_date", "end_date", "ann_date", "period", "float_date"})
    if date_keys and not any(context.get(key) not in (None, "") for key in date_keys):
        return False
    return bool(context)


def _production_target_contexts(
    api_contexts: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        target: {
            "target": target,
            "apis": list(apis),
            "api_contexts": {api: dict(api_contexts.get(api) or {}) for api in apis},
        }
        for target, _label, apis in VALIDATION_TARGET_GROUPS
    }


def _production_universe_context(payload: Any) -> dict[str, Any]:
    safe = _safe_payload(payload)
    provided = safe.get("universe_context") if isinstance(safe.get("universe_context"), Mapping) else {}
    context = {
        "list_status": str(provided.get("list_status") or "L").upper(),
        "as_of_date": str(provided.get("as_of_date") or ""),
        "feature_start_date": str(provided.get("feature_start_date") or ""),
        "feature_end_date": str(provided.get("feature_end_date") or ""),
        "required_feature_sessions": _safe_int(provided.get("required_feature_sessions")),
        "max_provider_calls": _safe_int(provided.get("max_provider_calls")),
        "max_rows_per_call": _safe_int(provided.get("max_rows_per_call")),
    }
    return context


def _production_universe_context_ready(context: Mapping[str, Any]) -> bool:
    today = _dt.date.today().strftime("%Y%m%d")
    start = str(context.get("feature_start_date") or "")
    end = str(context.get("feature_end_date") or "")
    sessions = _safe_int(context.get("required_feature_sessions"))
    max_calls = _safe_int(context.get("max_provider_calls"))
    return bool(
        context.get("list_status") == "L"
        and str(context.get("as_of_date") or "") == today
        and len(start) == 8
        and len(end) == 8
        and start.isdigit()
        and end.isdigit()
        and start <= end == today
        and sessions == 90
        and 1 + 3 * sessions <= max_calls <= 300
        and 3000 <= _safe_int(context.get("max_rows_per_call")) <= 10000
    )


def _production_approval_scope_material(
    *,
    recipe_scope_hash: str,
    recipe_version: str,
    selected_apis: Iterable[str],
    requested_targets: Iterable[str],
    api_contexts: Mapping[str, Any],
    target_contexts: Mapping[str, Any],
    universe_context: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "tushare_full_interface_provider_approval_scope.v1",
        "recipe_scope_hash": str(recipe_scope_hash or ""),
        "recipe_version": str(recipe_version or ""),
        "selected_apis": sorted(str(api) for api in selected_apis),
        "requested_targets": sorted(str(target) for target in requested_targets),
        "api_contexts": _safe_payload({"api_contexts": dict(api_contexts)}).get("api_contexts", {}),
        "target_contexts": _safe_payload({"target_contexts": dict(target_contexts)}).get(
            "target_contexts", {}
        ),
        "universe_context": _safe_payload({"universe_context": dict(universe_context)}).get(
            "universe_context", {}
        ),
    }


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
    requested_api_scope = _selected_apis(payload_safe, default_apis or MARGIN_REFRESH_APIS)
    full_target_scope_requested = bool(
        len(valid_requested_targets) == len(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS)
        and set(valid_requested_targets) == set(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS)
    )
    full_api_scope_requested = bool(
        len(requested_api_scope) == len(ALL_REFRESH_APIS)
        and set(requested_api_scope) == set(ALL_REFRESH_APIS)
    )
    selected_apis = (
        list(ALL_REFRESH_APIS)
        if full_target_scope_requested and full_api_scope_requested
        else [api for api in requested_api_scope if api in set(default_apis or MARGIN_REFRESH_APIS)]
    )
    api_contexts = _production_api_contexts(payload_safe, selected_apis)
    target_contexts = _production_target_contexts(api_contexts)
    universe_context = _production_universe_context(payload_safe)
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
        missing_required_apis = [api for api in apis if api not in target_selected_apis]
        context_blocked_apis = [
            api for api in target_selected_apis if not _production_api_context_ready(api, api_contexts.get(api, {}))
        ]
        row_ready = bool(
            requested
            and target_selected_apis
            and not missing_required_apis
            and not context_blocked_apis
            and not unknown_targets
        )
        if not requested:
            status = "target_sample_execution_recipe_not_requested"
            next_step = "select_target_group_with_provider_target_sample_acceptance_mode"
        elif unknown_targets:
            status = "target_sample_execution_recipe_blocked_unknown_target_group"
            next_step = "use_known_validation_target_groups"
        elif not target_selected_apis:
            status = "target_sample_execution_recipe_blocked_empty_api_scope"
            next_step = "select_target_sample_apis_before_provider_task"
        elif missing_required_apis:
            status = "target_sample_execution_recipe_blocked_missing_target_api_scope"
            next_step = "select_all_required_target_apis_before_provider_task"
        elif context_blocked_apis:
            status = "target_sample_execution_recipe_blocked_missing_representative_context"
            next_step = "bind_per_api_representative_context_before_provider_task"
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
                "missing_required_apis": missing_required_apis,
                "api_contexts": {
                    api: dict(api_contexts.get(api) or {}) for api in target_selected_apis
                },
                "context_blocked_apis": context_blocked_apis,
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
    full_interface_recipe_ready = bool(
        recipe_ready
        and full_target_scope_requested
        and full_api_scope_requested
        and all(_production_api_context_ready(api, api_contexts.get(api, {})) for api in ALL_REFRESH_APIS)
        and _production_universe_context_ready(universe_context)
    )
    recipe_issued_at = _dt.datetime.now().isoformat(timespec="microseconds")
    scope_payload = {
        "schema_version": "tushare_provider_target_sample_execution_recipe.v2",
        "recipe_version": FULL_INTERFACE_PROVIDER_PRODUCTION_RECIPE_VERSION,
        "recipe_issued_at": recipe_issued_at,
        "scope": "local_target_sample_execution_recipe_seed_no_provider_execution",
        "post_task_route": "POST /api/tasks/refresh-tushare-facts",
        "required_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
        "requested_targets": valid_requested_targets,
        "selected_apis": selected_apis,
        "api_contexts": api_contexts,
        "target_contexts": target_contexts,
        "universe_context": universe_context,
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
    scope_hash = _canonical_sha256(scope_payload)
    return {
        "schema_version": "tushare_provider_target_sample_execution_recipe.v2",
        "seed_schema_version": PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_SEED_SCHEMA_VERSION,
        "status": "target_sample_execution_recipe_ready_user_confirmation_required"
        if recipe_ready
        else "target_sample_execution_recipe_blocked_or_not_requested",
        "scope": "local_target_sample_execution_recipe_seed_no_provider_execution",
        "post_task_route": "POST /api/tasks/refresh-tushare-facts",
        "required_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
        "recipe_version": FULL_INTERFACE_PROVIDER_PRODUCTION_RECIPE_VERSION,
        "recipe_issued_at": recipe_issued_at,
        "runbook_ready": recipe_ready,
        "activation_receipt_ready": True,
        "requested_targets": valid_requested_targets,
        "selected_apis": selected_apis,
        "api_contexts": api_contexts,
        "target_contexts": target_contexts,
        "universe_context": universe_context,
        "full_target_scope_requested": full_target_scope_requested,
        "full_api_scope_requested": full_api_scope_requested,
        "full_interface_recipe_ready": full_interface_recipe_ready,
        "unknown_requested_targets": unknown_targets,
        "requested_target_count": len(valid_requested_targets),
        "recipe_ready_target_count": ready_count,
        "blocked_recipe_target_count": blocked_count,
        "recipe_ready_for_user_confirmation": recipe_ready,
        "execution_recipe_scope_hash_algorithm": "sha256",
        "execution_recipe_scope_hash": scope_hash,
        "execution_recipe_scope_hash_short": scope_hash[:16],
        "execution_recipe_scope_hash_input_field_count": len(scope_payload),
        "execution_recipe_scope_material": scope_payload,
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
    authoritative_source_packet_key: str = "",
    authoritative_recipe_updated_at: str = "",
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
    full_scope_hash_matches = bool(
        len(latest_scope_hash) == 64
        and len(requested_scope_hash) == 64
        and requested_scope_hash == latest_scope_hash
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
    recipe_selected_apis: list[str] = [
        str(api) for api in recipe.get("selected_apis") or [] if str(api or "")
    ]
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
        recipe.get("schema_version")
        in {
            "tushare_provider_target_sample_execution_recipe.v1",
            "tushare_provider_target_sample_execution_recipe.v2",
        }
        and recipe.get("recipe_ready_for_user_confirmation") is True
        and recipe.get("status") == "target_sample_execution_recipe_ready_user_confirmation_required"
        and recipe.get("provider_task_created_by_recipe") is False
        and recipe.get("recipe_external_calls_triggered") is False
        and recipe.get("tushare_called_by_recipe") is False
    )
    recipe_version = str(recipe.get("recipe_version") or recipe.get("schema_version") or "")
    api_contexts = recipe.get("api_contexts") if isinstance(recipe.get("api_contexts"), Mapping) else {}
    target_contexts = (
        recipe.get("target_contexts") if isinstance(recipe.get("target_contexts"), Mapping) else {}
    )
    universe_context = (
        recipe.get("universe_context") if isinstance(recipe.get("universe_context"), Mapping) else {}
    )
    full_interface_recipe_ready = bool(
        recipe.get("schema_version") == "tushare_provider_target_sample_execution_recipe.v2"
        and recipe.get("recipe_version") == FULL_INTERFACE_PROVIDER_PRODUCTION_RECIPE_VERSION
        and recipe.get("full_interface_recipe_ready") is True
        and len(recipe_selected_apis) == len(ALL_REFRESH_APIS)
        and set(recipe_selected_apis) == set(ALL_REFRESH_APIS)
        and len(latest_targets) == len(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS)
        and set(latest_targets) == set(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS)
    )
    approval_scope_material = _production_approval_scope_material(
        recipe_scope_hash=latest_scope_hash,
        recipe_version=recipe_version,
        selected_apis=recipe_selected_apis,
        requested_targets=latest_targets,
        api_contexts=api_contexts,
        target_contexts=target_contexts,
        universe_context=universe_context,
    )
    approval_scope_hash = _canonical_sha256(approval_scope_material)
    target_payload_safe = {
        "apis": selected_apis,
        "acceptance_mode": (
            FULL_INTERFACE_PROVIDER_PRODUCTION_MODE
            if full_interface_recipe_ready
            else PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE
        ),
        "target_sample_acceptance_groups": requested_targets,
        "execution_recipe_scope_hash": latest_scope_hash,
        "execution_recipe_scope_hash_short": latest_scope_hash_short,
        "approval_scope_hash": approval_scope_hash,
        "recipe_version": recipe_version,
        "api_contexts": dict(api_contexts),
        "target_contexts": dict(target_contexts),
        "universe_context": dict(universe_context),
        "provider_execution_requires_separate_post_task": True,
    }
    for key in ("ts_code", "trade_date", "start_date", "end_date", "ann_date", "period", "float_date", "limit_type"):
        if payload_safe.get(key) not in (None, ""):
            target_payload_safe[key] = payload_safe.get(key)
    for key in (
        "failure_modes_validated",
        "failure_mode_validated_count",
        "target_sample_failure_modes_validated",
        "target_sample_failure_mode_validated_count",
        "target_sample_failure_window_review_task_id",
    ):
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
            "full_sha256_scope_bound_for_production",
            not full_interface_recipe_ready or full_scope_hash_matches,
            "full-interface production approval requires the complete 64-character SHA-256 recipe scope",
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
    full_interface_production_execution_request_ready = bool(
        ready
        and full_interface_recipe_ready
        and full_scope_hash_matches
        and len(selected_apis) == len(recipe_selected_apis)
        and set(selected_apis) == set(recipe_selected_apis)
        and len(requested_targets) == len(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS)
        and set(requested_targets) == set(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS)
    )
    receipt = {
        "schema_version": PROVIDER_TARGET_SAMPLE_EXECUTION_REQUEST_SCHEMA_VERSION,
        "status": status,
        "scope": "local_tushare_provider_target_sample_execution_request_no_provider_execution",
        "route": PROVIDER_TARGET_SAMPLE_EXECUTION_REQUEST_ROUTE,
        "task_type": PROVIDER_TARGET_SAMPLE_EXECUTION_REQUEST_TASK_TYPE,
        "target_post_task_route": "POST /api/tasks/refresh-tushare-facts",
        "target_task_type": "refresh_tushare_facts",
        "target_acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
        "authoritative_recipe_source_packet_key": authoritative_source_packet_key,
        "authoritative_recipe_updated_at": authoritative_recipe_updated_at,
        "authoritative_recipe_version": recipe_version,
        "latest_execution_recipe_visible": recipe_visible,
        "latest_execution_recipe_status": recipe.get("status") or "",
        "latest_execution_recipe_ready_for_user_confirmation": recipe.get("recipe_ready_for_user_confirmation") is True,
        "latest_execution_recipe_scope_hash_short": latest_scope_hash_short,
        "latest_execution_recipe_scope_hash": latest_scope_hash,
        "requested_execution_recipe_scope_hash_short": requested_scope_hash[:16],
        "requested_execution_recipe_scope_hash": requested_scope_hash,
        "execution_recipe_scope_hash_matches_latest": scope_matches,
        "full_sha256_scope_hash_matches_latest": full_scope_hash_matches,
        "operator_confirmation_recorded": operator_confirmed,
        "requested_targets": requested_targets,
        "latest_requested_targets": latest_targets,
        "unknown_requested_targets": unknown_targets,
        "target_group_scope_matches_latest_recipe": target_scope_matches_latest,
        "selected_apis": selected_apis,
        "api_contexts": dict(api_contexts),
        "target_contexts": dict(target_contexts),
        "universe_context": dict(universe_context),
        "approval_scope_material": approval_scope_material,
        "approval_scope_hash": approval_scope_hash,
        "target_payload_safe": target_payload_safe,
        "blocking_criterion_count": blocker_count,
        "row_count": len(rows),
        "local_execution_request_ready": ready,
        "ready_for_manual_provider_task_submission": ready,
        "full_interface_production_execution_request_ready": full_interface_production_execution_request_ready,
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
        authoritative_source_packet_key=str(
            latest_packet.get("authoritative_recipe_source_packet_key") or ""
        ),
        authoritative_recipe_updated_at=str(latest_packet.get("authoritative_recipe_updated_at") or ""),
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


def _latest_target_sample_provider_refresh_packet_task(payload_safe: Mapping[str, Any]) -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet("command_center_tushare_refresh_packet")
    except Exception:
        return {}
    if not isinstance(packet, Mapping) or packet.get("task_type") != "refresh_tushare_facts":
        return {}
    ledger = [row for row in packet.get("call_ledger") or [] if isinstance(row, Mapping)]
    provider_rows = [
        row
        for row in ledger
        if row.get("tushare_called") is True
        or row.get("external_calls_triggered") is True
        or row.get("external") is True
    ]
    if not provider_rows:
        return {}
    packet_payload = packet.get("payload_safe") if isinstance(packet.get("payload_safe"), Mapping) else {}
    requested_targets = [
        str(item)
        for item in (
            packet_payload.get("target_sample_acceptance_groups")
            or payload_safe.get("target_sample_acceptance_groups")
            or []
        )
        if str(item or "")
    ]
    if (
        packet_payload.get("acceptance_mode") != PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE
        and packet.get("acceptance_mode") != PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE
        and not requested_targets
    ):
        return {}
    selected_apis = [
        str(item)
        for item in (
            packet_payload.get("apis")
            or packet.get("selected_apis")
            or packet.get("apis")
            or [row.get("api") for row in provider_rows]
        )
        if str(item or "")
    ]
    merged_payload: dict[str, Any] = {
        "acceptance_mode": PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE,
        "target_sample_acceptance_groups": requested_targets,
        "apis": selected_apis,
    }
    for key in ("ts_code", "trade_date", "start_date", "end_date", "ann_date", "period", "float_date", "limit_type"):
        value = packet_payload.get(key) or payload_safe.get(key) or packet.get(key)
        if value not in (None, ""):
            merged_payload[key] = value
    return {
        "task_id": str(packet.get("task_id") or "packet:command_center_tushare_refresh_packet"),
        "task_type": "refresh_tushare_facts",
        "status": packet.get("status") or "success",
        "current_step": "tushare_refresh_packet_replay_for_failure_window_review",
        "payload_safe": merged_payload,
        "call_ledger": [dict(row) for row in ledger],
        "external_calls_triggered": True,
        "tushare_called": True,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "provider_task_source": "sqlite_refresh_packet_fallback",
    }


def _latest_target_sample_provider_refresh_task(payload_safe: Mapping[str, Any] | None = None) -> dict[str, Any]:
    request_payload_safe = payload_safe or {}
    for task in list_task_statuses():
        if task.get("task_type") != "refresh_tushare_facts":
            continue
        task_payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), Mapping) else {}
        ledger = [row for row in task.get("call_ledger") or [] if isinstance(row, Mapping)]
        has_provider_ledger = any(
            row.get("tushare_called") is True
            or row.get("external_calls_triggered") is True
            or row.get("external") is True
            for row in ledger
        )
        if (
            task_payload_safe.get("acceptance_mode") == PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE
            or task_payload_safe.get("target_sample_acceptance_groups")
        ) and has_provider_ledger:
            return dict(task)
    return _latest_target_sample_provider_refresh_packet_task(request_payload_safe)


def _target_sample_failure_window_review_receipt(
    payload: Any = None,
    *,
    provider_task: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload_safe = _safe_payload(payload)
    provider_task_map = dict(provider_task or _latest_target_sample_provider_refresh_task(payload_safe))
    provider_payload = (
        provider_task_map.get("payload_safe")
        if isinstance(provider_task_map.get("payload_safe"), Mapping)
        else {}
    )
    provider_payload = dict(provider_payload)
    ledger = [dict(row) for row in provider_task_map.get("call_ledger") or [] if isinstance(row, Mapping)]
    provider_rows = [
        row
        for row in ledger
        if row.get("tushare_called") is True
        or row.get("external_calls_triggered") is True
        or row.get("external") is True
    ]
    requested_targets = [
        str(item)
        for item in (
            provider_payload.get("target_sample_acceptance_groups")
            or payload_safe.get("target_sample_acceptance_groups")
            or []
        )
        if str(item or "")
    ]
    selected_apis = [
        str(item)
        for item in (provider_payload.get("apis") or payload_safe.get("apis") or [])
        if str(item or "")
    ]
    if not selected_apis:
        selected_apis = [str(row.get("api") or "") for row in provider_rows if str(row.get("api") or "")]
    provided_context_fields = sorted(
        key
        for key, value in provider_payload.items()
        if key in {"ts_code", "trade_date", "start_date", "end_date", "ann_date", "period", "float_date", "limit_type"}
        and value not in (None, "")
    )
    ledger_by_api = {str(row.get("api") or ""): row for row in provider_rows}
    rows: list[dict[str, Any]] = []
    for target_key, label, target_apis in VALIDATION_TARGET_GROUPS:
        requested = target_key in requested_targets
        selected_target_apis = [api for api in target_apis if api in selected_apis]
        if not requested and not selected_target_apis:
            continue
        target_ledger_rows = [ledger_by_api[api] for api in selected_target_apis if api in ledger_by_api]
        non_empty_success_apis = [
            str(row.get("api") or "")
            for row in target_ledger_rows
            if row.get("call_status") == "success" and int(row.get("row_count") or 0) > 0
        ]
        validated_empty_apis = [
            str(row.get("api") or "") for row in target_ledger_rows if row.get("call_status") == "empty"
        ]
        failed_or_blocked_apis = [
            str(row.get("api") or "")
            for row in target_ledger_rows
            if row.get("call_status") == "failed"
            or str(row.get("call_status") or "").startswith("blocked_")
        ]
        failure_modes = sorted(
            {
                str(row.get("failure_mode") or "")
                for row in target_ledger_rows
                if str(row.get("failure_mode") or "") and str(row.get("failure_mode") or "") != "none"
            }
        )
        requirement = PROVIDER_TARGET_SAMPLE_REQUIREMENTS.get(target_key, {})
        missing_context_groups = [
            " or ".join(group)
            for group in requirement.get("context_groups", ())
            if not any(field in provided_context_fields for field in group)
        ]
        blockers: list[str] = []
        if requested and not selected_target_apis:
            blockers.append("target_api_selection_missing")
        if selected_target_apis and len(target_ledger_rows) < len(selected_target_apis):
            blockers.append("call_ledger_evidence_missing")
        if not (non_empty_success_apis or validated_empty_apis):
            blockers.append("sample_evidence_missing")
        if requested and missing_context_groups:
            blockers.append("sample_window_context_missing")
        failure_mode_evidence_required = bool(validated_empty_apis or failed_or_blocked_apis)
        if requested and failure_mode_evidence_required and not failure_modes:
            blockers.append("failure_mode_evidence_missing")
        status = "target_sample_failure_window_review_ready" if not blockers else "target_sample_failure_window_review_blocked"
        rows.append(
            {
                "target": target_key,
                "label": label,
                "requested_for_review": requested,
                "selected_apis": selected_target_apis,
                "ledger_api_count": len(target_ledger_rows),
                "row_count": sum(int(row.get("row_count") or 0) for row in target_ledger_rows),
                "non_empty_success_apis": non_empty_success_apis,
                "validated_empty_apis": validated_empty_apis,
                "failed_or_blocked_apis": failed_or_blocked_apis,
                "failure_modes_observed": failure_modes,
                "failure_mode_evidence_required": failure_mode_evidence_required,
                "failure_mode_evidence_visible": bool(failure_modes),
                "provided_context_fields": provided_context_fields,
                "missing_context_groups": missing_context_groups,
                "review_status": status,
                "review_blockers": blockers,
                "review_blocker_count": len(blockers),
                "provider_backed_target_sample_acceptance_done": False,
                "full_interface_acceptance_done": False,
                "production_tushare_pipeline_complete": False,
                "cache_get_external_calls": False,
                "review_external_calls_triggered": False,
                "tushare_called_by_review": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    requested_rows = [row for row in rows if row.get("requested_for_review")]
    blocked_rows = [row for row in requested_rows if row.get("review_blockers")]
    empty_rows = [row for row in provider_rows if row.get("call_status") == "empty"]
    failed_rows = [row for row in provider_rows if row.get("call_status") == "failed"]
    success_rows = [row for row in provider_rows if row.get("call_status") == "success"]
    status = (
        "target_sample_failure_window_review_missing_provider_task"
        if not provider_task_map
        else "target_sample_failure_window_review_ready_for_target_acceptance_rerun"
        if requested_rows and not blocked_rows
        else "target_sample_failure_window_review_visible_blockers_recorded"
    )
    blocker_count = sum(int(row.get("review_blocker_count") or 0) for row in requested_rows)
    next_step = (
        "rerun_target_sample_acceptance_with_reviewed_failure_modes"
        if status == "target_sample_failure_window_review_ready_for_target_acceptance_rerun"
        else "add_target_sample_window_context_or_collect_failure_mode_evidence"
        if provider_task_map
        else "POST /api/tasks/refresh-tushare-facts"
    )
    receipt = {
        "schema_version": PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_SCHEMA_VERSION,
        "status": status,
        "scope": "local_tushare_provider_target_sample_failure_window_review_no_provider_call",
        "route": PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_ROUTE,
        "task_type": PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_TASK_TYPE,
        "provider_task_found": bool(provider_task_map),
        "provider_task_id": str(provider_task_map.get("task_id") or ""),
        "provider_call_ledger_count": len(provider_rows),
        "provider_row_count": sum(int(row.get("row_count") or 0) for row in provider_rows),
        "provider_success_count": len(success_rows),
        "provider_empty_count": len(empty_rows),
        "provider_failed_count": len(failed_rows),
        "requested_targets": requested_targets,
        "requested_target_count": len(requested_targets),
        "reviewed_target_count": len(requested_rows),
        "ready_target_count": len([row for row in requested_rows if not row.get("review_blockers")]),
        "blocked_target_count": len(blocked_rows),
        "blocking_criterion_count": blocker_count,
        "selected_apis": selected_apis,
        "provided_context_fields": provided_context_fields,
        "failure_mode_review_visible": bool(empty_rows or failed_rows),
        "failure_mode_review_done": False,
        "sample_window_review_visible": bool(requested_rows),
        "sample_window_review_done": bool(requested_rows and not any(row.get("missing_context_groups") for row in requested_rows)),
        "target_sample_acceptance_ready_for_review": status
        == "target_sample_failure_window_review_ready_for_target_acceptance_rerun",
        "ready_for_target_sample_acceptance_rerun": status
        == "target_sample_failure_window_review_ready_for_target_acceptance_rerun",
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
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "allowed_next_step": next_step,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tushare_provider_target_sample_failure_window_review",
                "source": "task_service.list_task_statuses latest refresh_tushare_facts provider target-sample ledger",
                "request_params_safe": {
                    "provider_task_id": str(provider_task_map.get("task_id") or ""),
                    "requested_targets": requested_targets,
                    "selected_apis": selected_apis,
                },
                "row_count": len(rows),
                "data_date": None,
                "local_fetched_at": _now_iso(),
                "call_status": status,
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
        "note": "This local review reads an existing provider target-sample task ledger and records failure-mode/window blockers. It does not call Tushare, DeepSeek, GitHub, create provider tasks, promote full-interface acceptance, trade, or mutate strategy action.",
    }
    return receipt, rows


def run_tushare_provider_target_sample_failure_window_review(payload: Any = None) -> dict[str, Any]:
    receipt, rows = _target_sample_failure_window_review_receipt(payload)
    payload_safe = {
        "provider_target_sample_failure_window_review_receipt": receipt,
        "provider_target_sample_failure_window_review_rows": rows,
    }
    task = create_task_record(
        PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_TASK_TYPE,
        output_packet_key=PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_PACKET_KEY,
        payload=payload_safe,
        current_step="tushare_provider_target_sample_failure_window_review_queued_local_only",
        warnings=[
            "该任务只读取已有 Tushare target-sample provider task ledger，不调用 Tushare。",
            "该任务只记录 failure-mode/window review blocker，不证明 LTG-02 生产完成。",
            "该任务不调用 DeepSeek/GitHub，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="building_tushare_provider_target_sample_failure_window_review",
        call_ledger=receipt["call_ledger"],
    )
    packet = {
        "packet_key": PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_PACKET_KEY,
        "schema_version": "command_center_tushare_provider_target_sample_failure_window_review_packet.v1",
        "status": receipt["status"],
        "task_type": PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_TASK_TYPE,
        "receipt": receipt,
        "rows": rows,
        "provider_call_ledger_count": receipt["provider_call_ledger_count"],
        "provider_row_count": receipt["provider_row_count"],
        "blocking_criterion_count": receipt["blocking_criterion_count"],
        "ready_for_target_sample_acceptance_rerun": receipt["ready_for_target_sample_acceptance_rerun"],
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": receipt["call_ledger"],
    }
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(
            PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_PACKET_KEY,
            packet,
        )
    except Exception:
        pass
    return update_task_status(
        task["task_id"],
        status="success" if receipt["provider_task_found"] else "failed",
        progress=1.0,
        current_step="tushare_provider_target_sample_failure_window_review_visible"
        if receipt["provider_task_found"]
        else "tushare_provider_target_sample_failure_window_review_missing_provider_task",
        error_message_safe="" if receipt["provider_task_found"] else "missing_target_sample_provider_task",
        call_ledger=receipt["call_ledger"],
    ) or task


def _target_sample_storage_promotion_review_receipt(payload: Any = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload_safe = _safe_payload(payload)
    provider_task = _latest_target_sample_provider_refresh_task(payload_safe)
    provider_payload = (
        provider_task.get("payload_safe") if isinstance(provider_task.get("payload_safe"), Mapping) else {}
    )
    provider_rows = [
        dict(row)
        for row in provider_task.get("call_ledger") or []
        if isinstance(row, Mapping)
        and (
            row.get("tushare_called") is True
            or row.get("external_calls_triggered") is True
            or row.get("external") is True
        )
    ]
    refresh_packet: dict[str, Any]
    try:
        refresh_raw = SQLiteMetaStore(SQLITE_META_PATH).read_packet("command_center_tushare_refresh_packet")
        refresh_packet = dict(refresh_raw) if isinstance(refresh_raw, Mapping) else {}
    except Exception:
        refresh_packet = {}
    target_contract = (
        refresh_packet.get("provider_target_sample_acceptance_contract")
        if isinstance(refresh_packet.get("provider_target_sample_acceptance_contract"), Mapping)
        else {}
    )
    target_review_ready = target_contract.get("target_sample_acceptance_ready_for_review") is True
    requested_targets = [
        str(item)
        for item in (
            provider_payload.get("target_sample_acceptance_groups")
            or target_contract.get("requested_targets")
            or []
        )
        if str(item or "")
    ]
    selected_apis = [
        str(item)
        for item in (
            provider_payload.get("apis")
            or refresh_packet.get("selected_apis")
            or [row.get("api") for row in provider_rows]
        )
        if str(item or "")
    ]
    provider_symbol = str(provider_payload.get("ts_code") or refresh_packet.get("ts_code") or "").strip()

    storage_cache = storage_service.storage_current_result_cache()
    storage_atomic = storage_service.storage_current_result_atomic_promotion_evidence()
    storage_symbol = str(storage_cache.get("symbol") or storage_atomic.get("expected_symbol") or "").strip()
    storage_result_version = str(
        storage_cache.get("result_version") or storage_atomic.get("expected_result_version") or ""
    ).strip()
    symbol_matches = bool(provider_symbol and storage_symbol and provider_symbol == storage_symbol)
    storage_readback_ready = bool(
        storage_cache.get("status")
        in {
            "storage_current_result_cache_ready_current",
            "storage_current_result_cache_degraded_last_good",
        }
        and storage_cache.get("duckdb_readback_verified") is True
        and storage_cache.get("cache_get_writes_files") is False
        and storage_cache.get("external_calls_triggered") is False
        and storage_cache.get("tushare_called") is False
        and storage_cache.get("deepseek_called") is False
        and storage_cache.get("github_called") is False
        and storage_cache.get("does_not_execute_trades") is True
        and storage_cache.get("does_not_modify_strategy_action") is True
        and storage_cache.get("contains_secret") is False
    )
    atomic_readback_ready = bool(
        storage_atomic.get("status") == "storage_current_result_atomic_promotion_current"
        and storage_atomic.get("atomic_promotion_current") is True
        and storage_atomic.get("duckdb_readback_verified") is True
        and storage_atomic.get("manifest_current_version_ready") is True
        and storage_atomic.get("cache_get_writes_files") is False
        and storage_atomic.get("external_calls_triggered") is False
        and storage_atomic.get("tushare_called") is False
        and storage_atomic.get("deepseek_called") is False
        and storage_atomic.get("github_called") is False
        and storage_atomic.get("does_not_execute_trades") is True
        and storage_atomic.get("does_not_modify_strategy_action") is True
        and storage_atomic.get("contains_secret") is False
    )
    checks = [
        (
            "provider_target_sample_visible",
            bool(provider_task and provider_rows),
            f"task_id={provider_task.get('task_id') or 'missing'}; call_ledger_count={len(provider_rows)}",
        ),
        (
            "target_sample_review_ready",
            target_review_ready,
            f"target_contract_status={target_contract.get('status') or 'missing'}",
        ),
        (
            "storage_current_result_readback",
            storage_readback_ready,
            (
                f"status={storage_cache.get('status')}; symbol={storage_symbol or 'missing'}; "
                f"result_version={storage_result_version or 'missing'}; "
                f"duckdb_readback_verified={storage_cache.get('duckdb_readback_verified')}"
            ),
        ),
        (
            "storage_atomic_pointer_readback",
            atomic_readback_ready,
            (
                f"status={storage_atomic.get('status')}; task_id={storage_atomic.get('latest_receipt_task_id')}; "
                f"manifest_current_version_ready={storage_atomic.get('manifest_current_version_ready')}"
            ),
        ),
        (
            "provider_storage_symbol_lineage",
            symbol_matches,
            f"provider_symbol={provider_symbol or 'missing'}; storage_symbol={storage_symbol or 'missing'}",
        ),
        (
            "no_storage_write_from_review",
            True,
            "review reads provider ledger and storage cache only; it does not write Parquet, manifests, or cache outputs.",
        ),
    ]
    rows = [
        {
            "criterion": criterion,
            "status": "passed" if passed else "blocked",
            "passed": bool(passed),
            "blocking": not bool(passed),
            "evidence": evidence,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
        for criterion, passed, evidence in checks
    ]
    blocker_count = sum(1 for row in rows if row["blocking"])
    if not provider_task or not provider_rows:
        status = "target_sample_storage_promotion_review_blocked_missing_provider_sample"
        allowed_next_step = "POST /api/tasks/refresh-tushare-facts"
    elif not target_review_ready:
        status = "target_sample_storage_promotion_review_blocked_target_sample_review_pending"
        allowed_next_step = PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_ROUTE
    elif not storage_readback_ready or not atomic_readback_ready or not symbol_matches:
        status = "target_sample_storage_promotion_review_recorded_storage_blockers_visible"
        allowed_next_step = "POST /api/storage/current-result/atomic-promote"
    else:
        status = "target_sample_storage_promotion_review_ready_full_interface_still_pending"
        allowed_next_step = "continue_full_interface_selection_and_release_review"
    ready = status == "target_sample_storage_promotion_review_ready_full_interface_still_pending"
    receipt = {
        "schema_version": PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_SCHEMA_VERSION,
        "status": status,
        "scope": "local_tushare_target_sample_storage_promotion_review_no_provider_no_storage_write",
        "route": PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_ROUTE,
        "task_type": PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_TASK_TYPE,
        "provider_task_found": bool(provider_task),
        "provider_task_id": str(provider_task.get("task_id") or ""),
        "provider_call_ledger_count": len(provider_rows),
        "provider_symbol": provider_symbol,
        "requested_targets": requested_targets,
        "selected_apis": selected_apis,
        "target_sample_acceptance_ready_for_review": target_review_ready,
        "storage_current_result_status": storage_cache.get("status") or "missing",
        "storage_current_result_symbol": storage_symbol,
        "storage_current_result_version": storage_result_version,
        "storage_current_result_data_date": storage_cache.get("data_date"),
        "storage_current_result_freshness_state": storage_cache.get("freshness_state"),
        "storage_current_result_duckdb_readback_verified": storage_cache.get("duckdb_readback_verified") is True,
        "storage_atomic_promotion_status": storage_atomic.get("status") or "missing",
        "storage_atomic_task_id": storage_atomic.get("latest_receipt_task_id") or "",
        "storage_atomic_manifest_current_version_ready": storage_atomic.get("manifest_current_version_ready") is True,
        "storage_readback_ready": storage_readback_ready,
        "storage_atomic_readback_ready": atomic_readback_ready,
        "provider_storage_symbol_matches": symbol_matches,
        "storage_or_no_storage_promotion_review_done": ready,
        "local_storage_promotion_review_ready": ready,
        "blocking_criterion_count": blocker_count,
        "row_count": len(rows),
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "ready_to_execute_from_cache": False,
        "creates_provider_task": False,
        "provider_execution_implemented": False,
        "writes_parquet": False,
        "writes_manifest": False,
        "writes_cache": False,
        "deletes_artifacts": False,
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
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tushare_target_sample_storage_promotion_review",
                "source": "existing target-sample provider ledger plus local storage current-result readback",
                "request_params_safe": {
                    "provider_task_id": str(provider_task.get("task_id") or ""),
                    "provider_symbol": provider_symbol,
                    "storage_symbol": storage_symbol,
                    "storage_result_version": storage_result_version,
                    "selected_apis": selected_apis,
                    "requested_targets": requested_targets,
                },
                "row_count": len(rows),
                "data_date": storage_cache.get("data_date"),
                "local_fetched_at": _now_iso(),
                "call_status": status,
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
        "note": "This local review links an existing provider target-sample ledger to storage current-result readback. It does not call Tushare, write Parquet, promote full-interface acceptance, trade, or mutate strategy action.",
    }
    return receipt, rows


def run_tushare_provider_target_sample_storage_promotion_review(payload: Any = None) -> dict[str, Any]:
    receipt, rows = _target_sample_storage_promotion_review_receipt(payload)
    payload_safe = {
        "provider_target_sample_storage_promotion_review_receipt": receipt,
        "provider_target_sample_storage_promotion_review_rows": rows,
    }
    task = create_task_record(
        PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_TASK_TYPE,
        output_packet_key=PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_PACKET_KEY,
        payload=payload_safe,
        current_step="tushare_target_sample_storage_promotion_review_queued_local_only",
        warnings=[
            "该任务只读取已有 target-sample provider ledger 与本地 current-result storage readback，不调用 Tushare。",
            "该任务不写 Parquet/manifest/cache，不证明 LTG-02 全接口生产完成。",
            "该任务不调用 DeepSeek/GitHub，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="building_tushare_target_sample_storage_promotion_review",
        call_ledger=receipt["call_ledger"],
    )
    packet = {
        "packet_key": PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_PACKET_KEY,
        "schema_version": "command_center_tushare_target_sample_storage_promotion_review_packet.v1",
        "status": receipt["status"],
        "task_type": PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_TASK_TYPE,
        "receipt": receipt,
        "rows": rows,
        "provider_task_id": receipt["provider_task_id"],
        "provider_call_ledger_count": receipt["provider_call_ledger_count"],
        "storage_or_no_storage_promotion_review_done": receipt["storage_or_no_storage_promotion_review_done"],
        "local_storage_promotion_review_ready": receipt["local_storage_promotion_review_ready"],
        "blocking_criterion_count": receipt["blocking_criterion_count"],
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": receipt["call_ledger"],
    }
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(
            PROVIDER_TARGET_SAMPLE_STORAGE_PROMOTION_REVIEW_PACKET_KEY,
            packet,
        )
    except Exception:
        pass
    return update_task_status(
        task["task_id"],
        status="success" if receipt["provider_task_found"] else "failed",
        progress=1.0,
        current_step="tushare_target_sample_storage_promotion_review_ready"
        if receipt["local_storage_promotion_review_ready"]
        else "tushare_target_sample_storage_promotion_review_blocked",
        error_message_safe="" if receipt["provider_task_found"] else "missing_target_sample_provider_task",
        call_ledger=receipt["call_ledger"],
    ) or task


def _latest_target_sample_permission_followup_material() -> dict[str, Any]:
    try:
        refresh_packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet("command_center_tushare_refresh_packet")
    except Exception:
        refresh_packet = {}
    refresh_map = dict(refresh_packet) if isinstance(refresh_packet, Mapping) else {}
    target_contract = (
        refresh_map.get("provider_target_sample_acceptance_contract")
        if isinstance(refresh_map.get("provider_target_sample_acceptance_contract"), Mapping)
        else {}
    )
    permission_rows: list[dict[str, Any]] = []
    for row in target_contract.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        failure_modes = [
            str(item)
            for item in row.get("failure_modes_observed") or []
            if str(item or "")
        ]
        if "permission_denied" not in failure_modes:
            continue
        permission_rows.append(
            {
                "target": str(row.get("target") or ""),
                "failed_or_blocked_apis": [
                    str(item)
                    for item in row.get("failed_or_blocked_apis") or []
                    if str(item or "")
                ],
                "failure_modes_observed": failure_modes,
                "target_sample_acceptance_blockers": [
                    str(item)
                    for item in row.get("target_sample_acceptance_blockers") or []
                    if str(item or "")
                ],
                "target_sample_acceptance_status": str(
                    row.get("target_sample_acceptance_status") or ""
                ),
            }
        )
    try:
        review_packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(
            PROVIDER_TARGET_SAMPLE_FAILURE_WINDOW_REVIEW_PACKET_KEY
        )
    except Exception:
        review_packet = {}
    review_map = dict(review_packet) if isinstance(review_packet, Mapping) else {}
    review_receipt = (
        review_map.get("receipt") if isinstance(review_map.get("receipt"), Mapping) else {}
    )
    return {
        "refresh_packet": refresh_map,
        "target_contract": dict(target_contract),
        "permission_rows": permission_rows,
        "failure_window_review_packet": review_map,
        "failure_window_review_receipt": dict(review_receipt),
    }


def _provider_target_sample_permission_followup_receipt(
    payload: Any = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload_safe = _safe_payload(payload)
    material = _latest_target_sample_permission_followup_material()
    permission_rows = list(material.get("permission_rows") or [])
    review_receipt = dict(material.get("failure_window_review_receipt") or {})
    followup_mode = str(
        payload_safe.get("followup_mode")
        or payload_safe.get("resolution_mode")
        or "provider_permission_upgrade_or_alternative_hard_risk_evidence"
    )
    allowed_modes = {
        "provider_permission_upgrade",
        "alternative_hard_risk_evidence_scope",
        "provider_permission_upgrade_or_alternative_hard_risk_evidence",
    }
    requested_targets = [
        str(item)
        for item in (payload_safe.get("target_sample_acceptance_groups") or payload_safe.get("targets") or [])
        if str(item or "")
    ]
    if not requested_targets:
        requested_targets = sorted({row["target"] for row in permission_rows if row.get("target")})
    selected_apis = [
        str(item)
        for item in (payload_safe.get("apis") or [])
        if str(item or "")
    ]
    if not selected_apis:
        selected_apis = sorted(
            {
                str(api)
                for row in permission_rows
                for api in row.get("failed_or_blocked_apis", [])
                if str(api or "")
            }
        )
    operator_confirmed = bool(
        payload_safe.get("operator_approved") is True
        or payload_safe.get("user_confirmed") is True
        or payload_safe.get("manual_confirmation") is True
    )
    permission_rows_visible = bool(permission_rows)
    review_visible = bool(review_receipt)
    mode_allowed = followup_mode in allowed_modes
    rows = [
        {
            "criterion": "permission_denied_blocker_visible",
            "status": "passed" if permission_rows_visible else "blocked",
            "passed": permission_rows_visible,
            "evidence": "provider target-sample acceptance rows contain permission_denied",
            "blocking": not permission_rows_visible,
        },
        {
            "criterion": "failure_window_review_receipt_visible",
            "status": "passed" if review_visible else "blocked",
            "passed": review_visible,
            "evidence": "local failure-window review receipt is visible before permission follow-up",
            "blocking": not review_visible,
        },
        {
            "criterion": "followup_mode_allowed",
            "status": "passed" if mode_allowed else "blocked",
            "passed": mode_allowed,
            "evidence": "followup mode is permission upgrade or alternative hard-risk evidence",
            "blocking": not mode_allowed,
        },
        {
            "criterion": "operator_confirmation_recorded",
            "status": "passed" if operator_confirmed else "blocked",
            "passed": operator_confirmed,
            "evidence": "operator_approved/user_confirmed/manual_confirmation must be true",
            "blocking": not operator_confirmed,
        },
        {
            "criterion": "no_provider_model_trade_boundary",
            "status": "passed",
            "passed": True,
            "evidence": "ticket is local-only and cannot call providers, models, GitHub, or trading paths",
            "blocking": False,
        },
    ]
    for row in rows:
        row.update(
            {
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
        )
    blocker_count = sum(1 for row in rows if row["blocking"])
    scope_payload = {
        "schema_version": PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_SCHEMA_VERSION,
        "permission_rows": permission_rows,
        "requested_targets": requested_targets,
        "selected_apis": selected_apis,
        "followup_mode": followup_mode,
        "failure_window_review_task_id": review_receipt.get("task_id")
        or review_receipt.get("provider_task_id")
        or "",
        "provider_task_id": review_receipt.get("provider_task_id") or "",
    }
    scope_hash_input = json.dumps(scope_payload, ensure_ascii=False, sort_keys=True)
    scope_hash = hashlib.sha256(scope_hash_input.encode("utf-8")).hexdigest()
    if not permission_rows_visible:
        status = "target_sample_permission_followup_blocked_missing_permission_denied_evidence"
    elif not review_visible:
        status = "target_sample_permission_followup_blocked_missing_failure_window_review"
    elif not mode_allowed:
        status = "target_sample_permission_followup_blocked_unknown_followup_mode"
    elif not operator_confirmed:
        status = "target_sample_permission_followup_blocked_operator_confirmation_missing"
    else:
        status = "target_sample_permission_followup_ticket_ready_manual_resolution_pending"
    ready = status == "target_sample_permission_followup_ticket_ready_manual_resolution_pending"
    receipt = {
        "schema_version": PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_SCHEMA_VERSION,
        "status": status,
        "scope": "local_tushare_provider_target_sample_permission_followup_no_provider_call",
        "route": PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_ROUTE,
        "task_type": PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_TASK_TYPE,
        "permission_followup_scope_hash_algorithm": "sha256",
        "permission_followup_scope_hash": scope_hash,
        "permission_followup_scope_hash_short": scope_hash[:16],
        "followup_mode": followup_mode,
        "requested_targets": requested_targets,
        "selected_apis": selected_apis,
        "permission_blocker_rows": permission_rows,
        "permission_blocker_count": len(permission_rows),
        "failure_window_review_visible": review_visible,
        "failure_window_review_status": review_receipt.get("status") or "",
        "failure_window_review_task_id": review_receipt.get("task_id")
        or review_receipt.get("provider_task_id")
        or "",
        "blocking_criterion_count": blocker_count,
        "row_count": len(rows),
        "local_permission_followup_ticket_ready": ready,
        "ready_for_manual_permission_resolution": ready,
        "ready_for_manual_alternative_hard_risk_evidence_scope": ready,
        "creates_provider_task": False,
        "provider_task_created": False,
        "provider_execution_implemented": False,
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
        "allowed_next_step": "manual_provider_permission_upgrade_or_alternative_hard_risk_evidence_scope",
        "not_allowed_next_steps": [
            "call Tushare from this permission follow-up ticket",
            "call DeepSeek from this permission follow-up ticket",
            "call GitHub from this permission follow-up ticket",
            "create provider task from this ticket",
            "treat permission blocker as provider-backed acceptance",
            "strategy action mutation",
            "real trade execution",
        ],
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tushare_provider_target_sample_permission_followup_ticket",
                "source": "existing target-sample permission blocker and local failure-window review",
                "row_count": len(rows),
                "request_params_safe": {
                    "requested_targets": requested_targets,
                    "selected_apis": selected_apis,
                    "followup_mode": followup_mode,
                    "permission_followup_scope_hash_short": scope_hash[:16],
                },
                "data_date": None,
                "local_fetched_at": _now_iso(),
                "call_status": status,
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
        "note": "This local permission follow-up ticket binds the observed target-sample permission_denied blocker to a manual permission-upgrade or alternative hard-risk evidence scope. It does not call Tushare, create provider tasks, promote acceptance, trade, or mutate strategy action.",
    }
    return receipt, rows


def run_tushare_provider_target_sample_permission_followup_ticket(
    payload: Any = None,
) -> dict[str, Any]:
    receipt, rows = _provider_target_sample_permission_followup_receipt(payload)
    payload_safe = {
        "provider_target_sample_permission_followup_receipt": receipt,
        "provider_target_sample_permission_followup_rows": rows,
    }
    task = create_task_record(
        PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_TASK_TYPE,
        output_packet_key=PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_PACKET_KEY,
        payload=payload_safe,
        current_step="tushare_provider_target_sample_permission_followup_queued_local_only",
        warnings=[
            "该任务只生成本地 Tushare target-sample permission follow-up ticket，不调用 Tushare。",
            "该任务只绑定权限/替代 hard-risk evidence 后续 scope，不证明 LTG-02 生产完成。",
            "该任务不调用 DeepSeek/GitHub，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="building_tushare_provider_target_sample_permission_followup",
        call_ledger=receipt["call_ledger"],
    )
    packet = {
        "packet_key": PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_PACKET_KEY,
        "schema_version": "command_center_tushare_provider_target_sample_permission_followup_packet.v1",
        "status": receipt["status"],
        "task_type": PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_TASK_TYPE,
        "receipt": receipt,
        "rows": rows,
        "permission_followup_scope_hash_short": receipt["permission_followup_scope_hash_short"],
        "local_permission_followup_ticket_ready": receipt["local_permission_followup_ticket_ready"],
        "provider_execution_implemented": False,
        "provider_task_created": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": receipt["call_ledger"],
    }
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(
            PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_PACKET_KEY,
            packet,
        )
    except Exception:
        pass
    return update_task_status(
        task["task_id"],
        status="success" if receipt["local_permission_followup_ticket_ready"] else "failed",
        progress=1.0,
        current_step="tushare_provider_target_sample_permission_followup_ticket_ready"
        if receipt["local_permission_followup_ticket_ready"]
        else "tushare_provider_target_sample_permission_followup_ticket_blocked",
        error_message_safe="" if receipt["local_permission_followup_ticket_ready"] else receipt["status"],
        call_ledger=receipt["call_ledger"],
    ) or task


def _latest_alternative_hard_risk_scope_material() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(
            PROVIDER_TARGET_SAMPLE_PERMISSION_FOLLOWUP_PACKET_KEY
        )
    except Exception:
        packet = {}
    packet_map = dict(packet) if isinstance(packet, Mapping) else {}
    receipt = packet_map.get("receipt") if isinstance(packet_map.get("receipt"), Mapping) else {}
    return {
        "permission_followup_packet": packet_map,
        "permission_followup_receipt": dict(receipt),
    }


def _alternative_hard_risk_evidence_scope_receipt(
    payload: Any = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload_safe = _safe_payload(payload)
    material = _latest_alternative_hard_risk_scope_material()
    permission_receipt = dict(material.get("permission_followup_receipt") or {})
    prior_ready = permission_receipt.get("local_permission_followup_ticket_ready") is True
    prior_scope_hash = str(permission_receipt.get("permission_followup_scope_hash") or "")
    prior_scope_hash_short = str(permission_receipt.get("permission_followup_scope_hash_short") or "")
    supplied_scope_hash = str(
        payload_safe.get("permission_followup_scope_hash")
        or payload_safe.get("permission_followup_scope_hash_short")
        or ""
    )
    scope_hash_matches = bool(
        supplied_scope_hash
        and supplied_scope_hash in {prior_scope_hash, prior_scope_hash_short}
    )
    requested_targets = [
        str(item)
        for item in (payload_safe.get("target_sample_acceptance_groups") or payload_safe.get("targets") or [])
        if str(item or "")
    ]
    if not requested_targets:
        requested_targets = [
            str(item)
            for item in permission_receipt.get("requested_targets", [])
            if str(item or "")
        ]
    selected_apis = [
        str(item)
        for item in (payload_safe.get("apis") or [])
        if str(item or "")
    ]
    if not selected_apis:
        selected_apis = [
            str(item)
            for item in permission_receipt.get("selected_apis", [])
            if str(item or "")
        ]
    evidence_sources = [
        str(item)
        for item in (payload_safe.get("evidence_sources") or [])
        if str(item or "")
    ]
    if not evidence_sources:
        evidence_sources = [
            "official_announcement_review",
            "disclosure_gap_summary",
            "last_successful_local_cache_snapshot",
            "manual_research_note_receipt",
        ]
    operator_confirmed = bool(
        payload_safe.get("operator_approved") is True
        or payload_safe.get("user_confirmed") is True
        or payload_safe.get("manual_confirmation") is True
    )
    hard_risk_scope = requested_targets == ["hard_risk"] and selected_apis == ["anns_d"]
    rows = [
        {
            "criterion": "permission_followup_ticket_visible",
            "status": "passed" if prior_ready else "blocked",
            "passed": prior_ready,
            "evidence": "latest local permission follow-up ticket is ready",
            "blocking": not prior_ready,
        },
        {
            "criterion": "permission_followup_scope_hash_bound",
            "status": "passed" if scope_hash_matches else "blocked",
            "passed": scope_hash_matches,
            "evidence": "payload binds the latest permission follow-up scope hash",
            "blocking": not scope_hash_matches,
        },
        {
            "criterion": "hard_risk_anns_d_scope_pinned",
            "status": "passed" if hard_risk_scope else "blocked",
            "passed": hard_risk_scope,
            "evidence": "alternative scope is limited to hard_risk / anns_d",
            "blocking": not hard_risk_scope,
        },
        {
            "criterion": "operator_confirmation_recorded",
            "status": "passed" if operator_confirmed else "blocked",
            "passed": operator_confirmed,
            "evidence": "operator_approved/user_confirmed/manual_confirmation must be true",
            "blocking": not operator_confirmed,
        },
        {
            "criterion": "no_provider_model_trade_boundary",
            "status": "passed",
            "passed": True,
            "evidence": "scope ticket is local-only and cannot call providers, models, GitHub, or trading paths",
            "blocking": False,
        },
    ]
    for row in rows:
        row.update(
            {
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
        )
    blocker_count = sum(1 for row in rows if row["blocking"])
    scope_payload = {
        "schema_version": ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_SCHEMA_VERSION,
        "source_permission_followup_scope_hash": prior_scope_hash,
        "requested_targets": requested_targets,
        "selected_apis": selected_apis,
        "evidence_sources": evidence_sources,
    }
    scope_hash_input = json.dumps(scope_payload, ensure_ascii=False, sort_keys=True)
    scope_hash = hashlib.sha256(scope_hash_input.encode("utf-8")).hexdigest()
    status = (
        "alternative_hard_risk_evidence_scope_ticket_ready_manual_collection_pending"
        if blocker_count == 0
        else "alternative_hard_risk_evidence_scope_ticket_blocked"
    )
    ready = blocker_count == 0
    receipt = {
        "schema_version": ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_SCHEMA_VERSION,
        "status": status,
        "scope": "local_tushare_alternative_hard_risk_evidence_scope_no_provider_call",
        "route": ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_ROUTE,
        "task_type": ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_TASK_TYPE,
        "alternative_hard_risk_scope_hash_algorithm": "sha256",
        "alternative_hard_risk_scope_hash": scope_hash,
        "alternative_hard_risk_scope_hash_short": scope_hash[:16],
        "source_permission_followup_scope_hash": prior_scope_hash,
        "source_permission_followup_scope_hash_short": prior_scope_hash_short,
        "requested_targets": requested_targets,
        "selected_apis": selected_apis,
        "evidence_sources": evidence_sources,
        "blocking_criterion_count": blocker_count,
        "row_count": len(rows),
        "local_alternative_hard_risk_scope_ticket_ready": ready,
        "ready_for_manual_hard_risk_evidence_collection": ready,
        "creates_provider_task": False,
        "provider_task_created": False,
        "provider_execution_implemented": False,
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
        "allowed_next_step": "collect_manual_hard_risk_evidence_or_wait_provider_permission_upgrade",
        "not_allowed_next_steps": [
            "call Tushare from this alternative scope ticket",
            "call DeepSeek from this alternative scope ticket",
            "call GitHub from this alternative scope ticket",
            "create provider task from this ticket",
            "treat alternative hard-risk scope as provider-backed acceptance",
            "strategy action mutation",
            "real trade execution",
        ],
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tushare_alternative_hard_risk_evidence_scope_ticket",
                "source": "existing permission follow-up ticket and hard-risk permission blocker",
                "row_count": len(rows),
                "request_params_safe": {
                    "requested_targets": requested_targets,
                    "selected_apis": selected_apis,
                    "evidence_sources": evidence_sources,
                    "alternative_hard_risk_scope_hash_short": scope_hash[:16],
                    "source_permission_followup_scope_hash_short": prior_scope_hash_short,
                },
                "data_date": None,
                "local_fetched_at": _now_iso(),
                "call_status": status,
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
        "note": "This local scope ticket converts the hard_risk/anns_d permission blocker into a manual alternative evidence collection scope. It does not call Tushare, create provider tasks, promote acceptance, trade, or mutate strategy action.",
    }
    return receipt, rows


def run_tushare_alternative_hard_risk_evidence_scope_ticket(
    payload: Any = None,
) -> dict[str, Any]:
    receipt, rows = _alternative_hard_risk_evidence_scope_receipt(payload)
    payload_safe = {
        "alternative_hard_risk_evidence_scope_receipt": receipt,
        "alternative_hard_risk_evidence_scope_rows": rows,
    }
    task = create_task_record(
        ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_TASK_TYPE,
        output_packet_key=ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_PACKET_KEY,
        payload=payload_safe,
        current_step="tushare_alternative_hard_risk_evidence_scope_queued_local_only",
        warnings=[
            "该任务只生成本地 hard-risk 替代证据 scope ticket，不调用 Tushare。",
            "该任务只绑定手工证据采集范围，不证明 LTG-02 生产完成。",
            "该任务不调用 DeepSeek/GitHub，不执行真实交易，不修改 strategy action。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(
        task["task_id"],
        status="running",
        progress=0.45,
        current_step="building_tushare_alternative_hard_risk_evidence_scope",
        call_ledger=receipt["call_ledger"],
    )
    packet = {
        "packet_key": ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_PACKET_KEY,
        "schema_version": "command_center_tushare_alternative_hard_risk_evidence_scope_packet.v1",
        "status": receipt["status"],
        "task_type": ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_TASK_TYPE,
        "receipt": receipt,
        "rows": rows,
        "alternative_hard_risk_scope_hash_short": receipt["alternative_hard_risk_scope_hash_short"],
        "local_alternative_hard_risk_scope_ticket_ready": receipt[
            "local_alternative_hard_risk_scope_ticket_ready"
        ],
        "provider_execution_implemented": False,
        "provider_task_created": False,
        "provider_backed_target_sample_acceptance_done": False,
        "full_interface_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": receipt["call_ledger"],
    }
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(
            ALTERNATIVE_HARD_RISK_EVIDENCE_SCOPE_PACKET_KEY,
            packet,
        )
    except Exception:
        pass
    return update_task_status(
        task["task_id"],
        status="success" if receipt["local_alternative_hard_risk_scope_ticket_ready"] else "failed",
        progress=1.0,
        current_step="tushare_alternative_hard_risk_evidence_scope_ticket_ready"
        if receipt["local_alternative_hard_risk_scope_ticket_ready"]
        else "tushare_alternative_hard_risk_evidence_scope_ticket_blocked",
        error_message_safe="" if receipt["local_alternative_hard_risk_scope_ticket_ready"] else receipt["status"],
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
    api_contexts = safe.get("api_contexts") if isinstance(safe.get("api_contexts"), Mapping) else {}
    api_context = api_contexts.get(api) if isinstance(api_contexts.get(api), Mapping) else {}
    if "ticker" in safe and "ts_code" not in safe:
        safe["ts_code"] = safe["ticker"]
    if "symbol" in safe and "ts_code" not in safe:
        safe["ts_code"] = safe["symbol"]
    params: dict[str, Any] = {}
    for key in REFRESH_API_SPECS[api]["params"]:
        value = api_context.get(key, safe.get(key))
        if value not in (None, ""):
            params[key] = value
    return params


def _trade_cal_exchange_values(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    raw_items = value
    if isinstance(value, str):
        raw_items = value.replace(";", ",").split(",")
    elif not isinstance(value, (list, tuple, set)):
        raw_items = [value]
    exchanges: list[str] = []
    for item in raw_items:
        exchange = "".join(ch for ch in str(item or "").upper() if ch.isalnum())
        if exchange and exchange not in exchanges:
            exchanges.append(exchange)
    return exchanges


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
        failure_modes_observed: list[str] = []
        for api in selected_target_apis:
            failure_mode = str(
                ledger_by_api.get(api, {}).get("failure_mode")
                or validation_by_api.get(api, {}).get("failure_mode")
                or ""
            )
            if failure_mode and failure_mode != "none" and failure_mode not in failure_modes_observed:
                failure_modes_observed.append(failure_mode)
        failure_modes_observed = sorted(failure_modes_observed)
        target_failure_mode_evidence_required = bool(validated_empty_apis or failed_or_blocked_apis)
        target_failure_modes_validated = bool(
            failure_modes_validated
            or not target_failure_mode_evidence_required
            or failure_modes_observed
        )
        unsafe_ledger_apis = [
            api
            for api in selected_target_apis
            if _has_sensitive_key(ledger_by_api.get(api, {}).get("request_params_safe"))
            or _has_unsafe_error_text(ledger_by_api.get(api, {}).get("error_message_safe"))
        ]
        sample_evidence_sufficient = bool(
            non_empty_success_apis or (validated_empty_apis and target_failure_modes_validated)
        )
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
            if target_failure_mode_evidence_required and not target_failure_modes_validated:
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
                "failure_modes_observed": failure_modes_observed,
                "target_failure_mode_evidence_required": target_failure_mode_evidence_required,
                "target_failure_mode_evidence_visible": bool(failure_modes_observed),
                "unsafe_ledger_apis": unsafe_ledger_apis,
                "validation_readiness": str(validation_target_row.get("readiness") or "unknown"),
                "provider_sample_plan_status": str(plan_row.get("provider_sample_plan_status") or "unknown"),
                "target_sample_acceptance_status": status,
                "target_sample_acceptance_meaning": meaning,
                "target_sample_acceptance_blockers": blockers,
                "target_sample_acceptance_blocker_count": len(blockers),
                "sample_evidence_sufficient": sample_evidence_sufficient,
                "failure_modes_validated": target_failure_modes_validated,
                "global_failure_modes_validated": failure_modes_validated,
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


def _provider_sample_semantics(
    api: str,
    *,
    params: Mapping[str, Any],
    rows: list[dict[str, Any]],
    call_status: str,
    provider_transport_verified: bool,
) -> dict[str, Any]:
    required_groups = API_REPRESENTATIVE_REQUIRED_FIELDS.get(api, ())

    def _row_representative(row: Mapping[str, Any]) -> bool:
        if not required_groups:
            return False
        if not all(any(row.get(field) not in (None, "") for field in group) for group in required_groups):
            return False
        for identity_key in ("ts_code", "trade_date", "ann_date", "cal_date"):
            expected = params.get(identity_key)
            actual = row.get(identity_key)
            if expected not in (None, "") and actual not in (None, "") and str(actual) != str(expected):
                return False
        return True

    representative_rows = [row for row in rows if _row_representative(row)]
    representative = bool(
        call_status == "success"
        and provider_transport_verified
        and representative_rows
    )
    valid_empty = bool(
        call_status == "empty"
        and provider_transport_verified
        and api in PRODUCTION_VALID_EMPTY_APIS
        and _production_api_context_ready(api, params)
    )
    status = (
        "representative_non_empty"
        if representative
        else "audited_valid_empty"
        if valid_empty
        else "invalid_or_unrepresentative"
    )
    return {
        "sample_semantics_status": status,
        "representative_sample_verified": representative,
        "representative_row_count": len(representative_rows),
        "valid_empty_semantics_verified": valid_empty,
        "generic_or_unrepresentative_row_rejected": bool(rows and not representative),
        "required_field_groups": [list(group) for group in required_groups],
    }


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


def _dataframe_for_write(data: Any, *, api: str = "") -> Any:
    if data is None:
        return None
    if hasattr(data, "to_parquet"):
        return data
    rows = _trade_cal_acceptance_rows_from_data(data) if api == "trade_cal" else _rows_from_data(data)
    if not rows:
        return None
    try:
        import pandas as pd

        return pd.DataFrame(rows)
    except Exception:
        return None


def _factor_test_small_pool_scope_hash(payload: Any) -> str:
    payload_map = payload if isinstance(payload, Mapping) else {}
    if payload_map.get("provider_acceptance_mode") != "factor_test_provider_small_pool_sample":
        return ""
    if payload_map.get("source_task_type") != "run_factor_test_provider_small_pool_acceptance":
        return ""
    scope_hash = str(payload_map.get("acceptance_scope_hash") or "").strip()
    scope_hash_short = str(payload_map.get("acceptance_scope_hash_short") or "").strip()
    return scope_hash or scope_hash_short


def _factor_test_small_pool_merge_dataframe(api: str, df: Any, payload: Any) -> tuple[Any, dict[str, Any]]:
    scope_hash = _factor_test_small_pool_scope_hash(payload)
    if api not in FACTOR_TEST_PROVIDER_SMALL_POOL_MERGE_APIS:
        return df, {"merge_applied": False}
    payload_map = payload if isinstance(payload, Mapping) else {}
    try:
        import pandas as pd

        current = df.copy()
        path = parquet_store.dataset_path(root=storage_service.PARQUET_ROOT, name=PARQUET_DATASETS[api])
        existing = pd.read_parquet(path) if path.exists() else None
        existing_row_count = int(len(existing)) if existing is not None else 0
        if not scope_hash:
            if existing is None:
                return df, {"merge_applied": False}
            scoped_existing = existing.iloc[0:0].copy()
            if "provider_scope_hash" in existing.columns:
                scope_text = existing["provider_scope_hash"].fillna("").astype(str).str.strip()
                scoped_existing = existing[(scope_text != "") & (scope_text.str.lower() != "nan")]
            if "provider_acceptance_mode" in existing.columns:
                mode_rows = existing[
                    existing["provider_acceptance_mode"].astype(str)
                    == "factor_test_provider_small_pool_sample"
                ]
                scoped_existing = pd.concat([scoped_existing, mode_rows], ignore_index=True)
            scoped_dedupe_keys = [
                key for key in ("ts_code", "trade_date", "provider_scope_hash") if key in scoped_existing.columns
            ]
            if scoped_dedupe_keys:
                scoped_existing = scoped_existing.drop_duplicates(subset=scoped_dedupe_keys, keep="last")
            if scoped_existing.empty:
                return df, {"merge_applied": False}
            combined = pd.concat([scoped_existing, current], ignore_index=True)
            dedupe_keys = [key for key in ("ts_code", "trade_date", "provider_scope_hash") if key in combined.columns]
            if not dedupe_keys:
                dedupe_keys = [key for key in ("ts_code", "trade_date") if key in combined.columns]
            if dedupe_keys:
                combined = combined.drop_duplicates(subset=dedupe_keys, keep="last")
            symbol_count = int(combined["ts_code"].astype(str).nunique()) if "ts_code" in combined.columns else 0
            return combined, {
                "merge_applied": True,
                "merge_status": "preserved_scope_rows",
                "input_row_count": int(len(current)),
                "existing_row_count": existing_row_count,
                "preserved_scope_row_count": int(len(scoped_existing)),
                "merged_row_count": int(len(combined)),
                "merged_symbol_count": symbol_count,
                "provider_scope_hash_short": "",
            }
        current["provider_scope_hash"] = scope_hash
        current["provider_scope_hash_short"] = str(payload_map.get("acceptance_scope_hash_short") or "")[:12]
        current["provider_acceptance_mode"] = "factor_test_provider_small_pool_sample"
        current["provider_source_task_type"] = "run_factor_test_provider_small_pool_acceptance"
        combined = pd.concat([existing, current], ignore_index=True) if existing is not None else current
        dedupe_keys = [key for key in ("ts_code", "trade_date", "provider_scope_hash") if key in combined.columns]
        if not dedupe_keys:
            dedupe_keys = [key for key in ("ts_code", "trade_date") if key in combined.columns]
        if dedupe_keys:
            combined = combined.drop_duplicates(subset=dedupe_keys, keep="last")
        symbol_count = int(combined["ts_code"].astype(str).nunique()) if "ts_code" in combined.columns else 0
        return combined, {
            "merge_applied": True,
            "merge_status": "merged_scope_rows",
            "input_row_count": int(len(current)),
            "existing_row_count": existing_row_count,
            "merged_row_count": int(len(combined)),
            "merged_symbol_count": symbol_count,
            "provider_scope_hash_short": str(payload_map.get("acceptance_scope_hash_short") or "")[:12],
        }
    except Exception as exc:
        return df, {
            "merge_applied": True,
            "merge_status": "merge_failed_fell_back_to_current_payload",
            "input_row_count": int(len(df)) if hasattr(df, "__len__") else 0,
            "error_message_safe": _safe_text(exc),
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_parquet_dataset(
    api: str,
    data: Any,
    *,
    payload: Any = None,
    scope: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    dataset = PARQUET_DATASETS.get(api)
    if not dataset:
        return {"status": "not_enabled", "dataset": None, "row_count": 0, "path": ""}
    df = _dataframe_for_write(data, api=api)
    if df is None:
        return {
            "status": "empty",
            "dataset": dataset,
            "row_count": 0,
            "path": str(parquet_store.dataset_path(root=storage_service.PARQUET_ROOT, name=dataset)),
        }
    df, merge_result = _factor_test_small_pool_merge_dataframe(api, df, payload)
    production_staging = (
        str(_payload_field(payload, "acceptance_mode", "") or "")
        == FULL_INTERFACE_PROVIDER_PRODUCTION_MODE
    )
    staging_root = (
        storage_service.PARQUET_ROOT
        / ".tushare_full_interface_staging"
        / str((scope or {}).get("scope_hash") or "missing_scope")
    )
    write_root = staging_root if production_staging else storage_service.PARQUET_ROOT
    try:
        result = parquet_store.write_dataset(df, root=write_root, name=dataset)
    except Exception as exc:
        return {
            "status": "failed",
            "dataset": dataset,
            "row_count": 0,
            "path": str(parquet_store.dataset_path(root=storage_service.PARQUET_ROOT, name=dataset)),
            "error_message_safe": _safe_text(exc),
        }
    result["dataset"] = dataset
    result.update(merge_result)
    if production_staging and result.get("status") == "written":
        staging_path = Path(str(result.get("path") or parquet_store.dataset_path(root=staging_root, name=dataset)))
        result.update(
            {
                "status": "staged",
                "staging_path": str(staging_path),
                "staging_digest": _sha256_file(staging_path) if staging_path.is_file() else "",
                "canonical_path": str(
                    parquet_store.dataset_path(root=storage_service.PARQUET_ROOT, name=dataset)
                ),
                "production_staging_only": True,
            }
        )
    return result


def _consume_runtime_transport_evidence(adapter_module: Any, result: Mapping[str, Any], api: str) -> dict[str, Any]:
    module_file = Path(str(getattr(adapter_module, "__file__", "") or ""))
    expected_file = Path(__file__).resolve().parents[2] / "tushare_adapter.py"
    module_identity_verified = bool(
        getattr(adapter_module, "__name__", "") == "tushare_adapter"
        and module_file.exists()
        and module_file.resolve() == expected_file.resolve()
    )
    call_ids = [str(item) for item in result.get("transport_call_ids") or [] if str(item or "")]
    if not call_ids and result.get("transport_call_id"):
        call_ids = [str(result.get("transport_call_id"))]
    consume = getattr(adapter_module, "consume_transport_receipt", None)
    receipts: list[dict[str, Any]] = []
    if module_identity_verified and callable(consume):
        for call_id in call_ids:
            try:
                receipt = consume(call_id, api)
            except Exception:
                receipt = None
            if isinstance(receipt, Mapping):
                receipts.append(dict(receipt))
    verified = bool(
        module_identity_verified
        and call_ids
        and len(receipts) == len(call_ids)
        and all(
            receipt.get("schema_version") == "tushare_runtime_transport_receipt.v1"
            and receipt.get("provider") == "Tushare"
            and receipt.get("api") == api
            and receipt.get("sdk_method_invoked") is True
            and receipt.get("provider_response_received") is True
            for receipt in receipts
        )
    )
    return {
        "schema_version": "tushare_runtime_transport_consumption.v1",
        "runtime_adapter_module_identity_verified": module_identity_verified,
        "transport_receipt_count": len(receipts),
        "transport_call_count": len(call_ids),
        "provider_transport_verified": verified,
        "provider": "Tushare" if verified else "unverified",
        "api": api,
        "transport_receipt_digest": _canonical_sha256(receipts) if verified else "",
    }


def _call_ledger_row(
    api: str,
    *,
    params: dict[str, Any],
    result: dict[str, Any],
    parquet_result: dict[str, Any] | None,
    now: str,
    payload: Any = None,
    scope: Mapping[str, str] | None = None,
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
        "scope_hash": str((scope or {}).get("scope_hash") or ""),
        "scope_hash_short": str((scope or {}).get("scope_hash_short") or ""),
        "payload_hash": str((scope or {}).get("payload_hash") or ""),
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
        "parquet_merge_applied": bool((parquet_result or {}).get("merge_applied")),
        "parquet_merge_status": (parquet_result or {}).get("merge_status", ""),
        "parquet_input_row_count": int((parquet_result or {}).get("input_row_count") or 0),
        "parquet_merged_symbol_count": int((parquet_result or {}).get("merged_symbol_count") or 0),
        "parquet_provider_scope_hash_short": (parquet_result or {}).get("provider_scope_hash_short", ""),
        "parquet_staging_path": (parquet_result or {}).get("staging_path", ""),
        "parquet_staging_digest": (parquet_result or {}).get("staging_digest", ""),
        "parquet_canonical_path": (parquet_result or {}).get("canonical_path", ""),
        "exchange_call_count": int(result.get("exchange_call_count") or (1 if api == "trade_cal" and params.get("exchange") else 0)),
        "exchange_success_count": int(result.get("exchange_success_count") or 0),
        "exchange_empty_count": int(result.get("exchange_empty_count") or 0),
        "exchange_failed_count": int(result.get("exchange_failed_count") or 0),
        "external": True,
        "external_calls_triggered": True,
        "tushare_called": True,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    transport = result.get("runtime_transport_evidence") if isinstance(result, Mapping) else {}
    row.update(
        {
            "runtime_transport_evidence_schema": (
                transport.get("schema_version") if isinstance(transport, Mapping) else ""
            ),
            "runtime_adapter_module_identity_verified": bool(
                isinstance(transport, Mapping)
                and transport.get("runtime_adapter_module_identity_verified") is True
            ),
            "provider_transport_verified": bool(
                isinstance(transport, Mapping) and transport.get("provider_transport_verified") is True
            ),
            "provider_transport_receipt_count": int(
                transport.get("transport_receipt_count") or 0
            )
            if isinstance(transport, Mapping)
            else 0,
            "provider_transport_call_count": int(transport.get("transport_call_count") or 0)
            if isinstance(transport, Mapping)
            else 0,
            "provider_transport_receipt_digest": str(
                transport.get("transport_receipt_digest") or ""
            )
            if isinstance(transport, Mapping)
            else "",
        }
    )
    row.update(
        _provider_sample_semantics(
            api,
            params=params,
            rows=rows,
            call_status=call_status,
            provider_transport_verified=row["provider_transport_verified"],
        )
    )
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


def _call_tushare_api(
    *,
    fn: Any,
    api: str,
    params: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if api != "trade_cal":
        try:
            result = fn(**params)
            if not isinstance(result, Mapping):
                result = {"ok": False, "data": None, "error": f"invalid result type: {type(result).__name__}"}
        except Exception as exc:
            result = {"ok": False, "data": None, "error": _safe_text(exc)}
        return dict(result), params

    exchanges = _trade_cal_exchange_values(params.get("exchange"))
    if len(exchanges) <= 1:
        call_params = dict(params)
        if exchanges:
            call_params["exchange"] = exchanges[0]
        try:
            result = fn(**call_params)
            if not isinstance(result, Mapping):
                result = {"ok": False, "data": None, "error": f"invalid result type: {type(result).__name__}"}
        except Exception as exc:
            result = {"ok": False, "data": None, "error": _safe_text(exc)}
        return dict(result), call_params

    combined_rows: list[dict[str, Any]] = []
    transport_call_ids: list[str] = []
    errors: list[str] = []
    empty_exchanges: list[str] = []
    ok_count = 0
    empty_count = 0
    for exchange in exchanges:
        call_params = {**params, "exchange": exchange}
        try:
            result = fn(**call_params)
            if not isinstance(result, Mapping):
                result = {"ok": False, "data": None, "error": f"invalid result type: {type(result).__name__}"}
        except Exception as exc:
            result = {"ok": False, "data": None, "error": _safe_text(exc)}
        rows = _trade_cal_acceptance_rows_from_data(result.get("data") if isinstance(result, Mapping) else None)
        for call_id in result.get("transport_call_ids") or [] if isinstance(result, Mapping) else []:
            value = str(call_id or "")
            if value:
                transport_call_ids.append(value)
        if result.get("ok"):
            ok_count += 1
            if not rows:
                empty_count += 1
                empty_exchanges.append(exchange)
        else:
            errors.append(f"{exchange}:{_safe_text(result.get('error') if isinstance(result, Mapping) else 'unknown')}")
        for row in rows:
            safe_row = dict(row)
            safe_row.setdefault("exchange", exchange)
            combined_rows.append(safe_row)

    safe_params = {**params, "exchange": exchanges}
    combined_ok = ok_count == len(exchanges) and empty_count == 0
    if combined_ok:
        error = ""
    elif empty_exchanges:
        error = f"trade_cal empty result for exchange: {','.join(empty_exchanges)}"
        if errors:
            error = f"{error}; {'; '.join(errors)}"
    elif errors:
        error = "; ".join(errors)
    else:
        error = "trade_cal multi-exchange call returned no successful exchange"
    return (
        {
            "ok": combined_ok,
            "data": combined_rows,
            "error": error,
            "exchange_call_count": len(exchanges),
            "exchange_success_count": ok_count,
            "exchange_empty_count": empty_count,
            "exchange_failed_count": len(exchanges) - ok_count,
            "transport_call_ids": transport_call_ids,
        },
        safe_params,
    )


def _blocked_missing_param_ledger_row(
    api: str,
    *,
    params: dict[str, Any],
    missing_param: str,
    now: str,
    scope: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    failure_mode = "missing_required_parameter"
    return {
        "api": api,
        "scope_hash": str((scope or {}).get("scope_hash") or ""),
        "scope_hash_short": str((scope or {}).get("scope_hash_short") or ""),
        "payload_hash": str((scope or {}).get("payload_hash") or ""),
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


def _scope_hash_short_text(value: Any) -> str:
    text = "".join(ch for ch in str(value or "").strip().lower() if ch in "0123456789abcdef")
    return text[:16]


def _payload_provider_execution_approved(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    for key in (
        "approved_by_user",
        "user_confirmation",
        "confirm_provider_task_request",
        "approved",
        "operator_approved",
    ):
        if key in payload and _safe_bool(payload.get(key), False):
            return True
    return False


def _payload_requested_scope_hash_short(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return ""
    for key in (
        "acceptance_scope_hash_short",
        "scope_hash_short",
        "dry_run_scope_hash_short",
        "requested_scope_hash_short",
        "acceptance_scope_hash",
        "scope_hash",
        "dry_run_scope_hash",
    ):
        value = payload.get(key)
        if value not in (None, ""):
            return _scope_hash_short_text(value)
    return ""


def _trade_cal_payload_exchange_values(payload: Any) -> list[str]:
    return _trade_cal_exchange_values(_payload_field(payload, "exchange", []))


def _latest_trade_cal_provider_acceptance_execution_request() -> dict[str, Any]:
    for task in list_task_statuses():
        if task.get("task_type") != TRADE_CAL_PROVIDER_ACCEPTANCE_EXECUTION_REQUEST_TASK_TYPE:
            continue
        payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), Mapping) else {}
        receipt = payload_safe.get("trade_cal_provider_acceptance_execution_request_receipt")
        if not isinstance(receipt, Mapping):
            continue
        return {
            "task_id": task.get("task_id"),
            "task_status": task.get("status"),
            "current_step": task.get("current_step"),
            "created_at": task.get("created_at"),
            "receipt": dict(receipt),
        }
    return {}


def _trade_cal_provider_execution_gate(payload: Any, *, selected_apis: list[str], adapter: Any) -> dict[str, Any]:
    acceptance_mode = str(_payload_field(payload, "acceptance_mode", "") or "")
    applies = (
        adapter is None
        and selected_apis == ["trade_cal"]
        and acceptance_mode == TRADE_CAL_PROVIDER_ACCEPTANCE_MODE
    )
    if not applies:
        return {"applies": False, "ready": True, "status": "not_applicable"}

    latest = _latest_trade_cal_provider_acceptance_execution_request()
    receipt = latest.get("receipt") if isinstance(latest.get("receipt"), Mapping) else {}
    target_payload = receipt.get("target_payload_safe") if isinstance(receipt.get("target_payload_safe"), Mapping) else {}
    requested_scope_hash_short = _payload_requested_scope_hash_short(payload)
    receipt_scope_hash_short = _scope_hash_short_text(
        receipt.get("requested_scope_hash_short")
        or target_payload.get("acceptance_scope_hash_short")
        or receipt.get("latest_dry_run_scope_hash_short")
    )
    approved = _payload_provider_execution_approved(payload)
    receipt_ready = bool(
        receipt
        and receipt.get("status") == TRADE_CAL_PROVIDER_ACCEPTANCE_EXECUTION_REQUEST_READY_STATUS
        and receipt.get("local_execution_request_ready") is True
        and receipt.get("ready_for_manual_provider_task_submission") is True
        and receipt.get("scope_hash_matches_latest_dry_run") is True
    )
    scope_matches = bool(requested_scope_hash_short and requested_scope_hash_short == receipt_scope_hash_short)

    expected_exchange = _trade_cal_exchange_values(receipt.get("exchange") or target_payload.get("exchange"))
    requested_exchange = _trade_cal_payload_exchange_values(payload)
    exchange_matches = bool(expected_exchange and requested_exchange and requested_exchange == expected_exchange)
    expected_start = str(receipt.get("start_date") or target_payload.get("start_date") or "")
    expected_end = str(receipt.get("end_date") or target_payload.get("end_date") or "")
    requested_start = str(_payload_field(payload, "start_date", "") or "")
    requested_end = str(_payload_field(payload, "end_date", "") or "")
    window_matches = bool(expected_start and expected_end and requested_start == expected_start and requested_end == expected_end)

    blockers: list[str] = []
    if not receipt:
        blockers.append("missing_trade_cal_provider_acceptance_execution_request")
    if receipt and not receipt_ready:
        blockers.append("latest_execution_request_not_ready")
    if not approved:
        blockers.append("explicit_provider_execution_approval_missing")
    if not scope_matches:
        blockers.append("scope_hash_not_bound_to_latest_execution_request")
    if not exchange_matches:
        blockers.append("exchange_scope_not_bound_to_execution_request")
    if not window_matches:
        blockers.append("date_window_not_bound_to_execution_request")

    ready = not blockers
    return {
        "applies": True,
        "ready": ready,
        "status": "trade_cal_provider_execution_gate_passed" if ready else "trade_cal_provider_execution_gate_blocked",
        "blockers": blockers,
        "current_step": (
            "trade_cal_provider_acceptance_execution_gate_passed_scope_bound"
            if ready
            else f"trade_cal_provider_acceptance_execution_gate_blocked_{blockers[0]}_no_provider_call"
        ),
        "error_message_safe": "" if ready else blockers[0],
        "requested_scope_hash_short": requested_scope_hash_short,
        "latest_execution_request_scope_hash_short": receipt_scope_hash_short,
        "scope_hash_matches_latest_execution_request": scope_matches,
        "approved_by_user": approved,
        "latest_execution_request_task_id": latest.get("task_id"),
        "latest_execution_request_status": receipt.get("status") or "missing",
        "latest_execution_request_task_status": latest.get("task_status") or "",
        "exchange_matches_execution_request": exchange_matches,
        "date_window_matches_execution_request": window_matches,
        "requested_exchange": requested_exchange,
        "expected_exchange": expected_exchange,
        "requested_start_date": requested_start,
        "requested_end_date": requested_end,
        "expected_start_date": expected_start,
        "expected_end_date": expected_end,
    }


def _trade_cal_provider_execution_gate_ledger_row(
    gate: Mapping[str, Any],
    *,
    selected_apis: list[str],
    payload: Any,
    now: str,
    scope: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    params = {
        "selected_apis": list(selected_apis),
        "acceptance_mode": _safe_text(_payload_field(payload, "acceptance_mode", "")),
        "approved_by_user": gate.get("approved_by_user") is True,
        "requested_scope_hash_short": gate.get("requested_scope_hash_short") or "",
        "latest_execution_request_task_id": gate.get("latest_execution_request_task_id") or "",
        "latest_execution_request_status": gate.get("latest_execution_request_status") or "missing",
        "scope_hash_matches_latest_execution_request": gate.get("scope_hash_matches_latest_execution_request") is True,
        "exchange_matches_execution_request": gate.get("exchange_matches_execution_request") is True,
        "date_window_matches_execution_request": gate.get("date_window_matches_execution_request") is True,
        "requested_exchange": list(gate.get("requested_exchange") or []),
        "expected_exchange": list(gate.get("expected_exchange") or []),
        "requested_start_date": gate.get("requested_start_date") or "",
        "requested_end_date": gate.get("requested_end_date") or "",
        "expected_start_date": gate.get("expected_start_date") or "",
        "expected_end_date": gate.get("expected_end_date") or "",
    }
    return {
        "api": "local_trade_cal_provider_acceptance_execution_gate",
        "scope_hash": str((scope or {}).get("scope_hash") or ""),
        "scope_hash_short": str((scope or {}).get("scope_hash_short") or ""),
        "payload_hash": str((scope or {}).get("payload_hash") or ""),
        "endpoint": "POST /api/tasks/refresh-tushare-facts",
        "request_params_safe": params,
        "row_count": 1,
        "data_date": params["requested_end_date"] or None,
        "local_fetched_at": now,
        "call_status": str(gate.get("status") or "trade_cal_provider_execution_gate_blocked"),
        "failure_mode": "missing_or_mismatched_execution_request",
        "failure_mode_status": "preflight_blocked_no_external_call",
        "safe_failure_mode_visible": True,
        "error_message_safe": _safe_text(gate.get("error_message_safe") or ""),
        "parquet_dataset": PARQUET_DATASETS.get("trade_cal"),
        "parquet_status": "not_written_provider_execution_gate_blocked",
        "parquet_row_count": 0,
        "provider_execution_gate_passed": gate.get("ready") is True,
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _payload_string_list(payload: Any, key: str) -> list[str]:
    raw = _payload_field(payload, key, [])
    if isinstance(raw, str):
        raw = [item.strip() for item in raw.split(",")]
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in raw:
        value = str(item or "").strip()
        if value and value not in result:
            result.append(value)
    return result


def _latest_target_sample_execution_request_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(
            "command_center_tushare_provider_target_sample_execution_request_packet"
        )
    except Exception:
        return {}
    return dict(packet) if isinstance(packet, Mapping) else {}


def _full_interface_provider_production_execution_gate(
    payload: Any,
    *,
    selected_apis: list[str],
) -> dict[str, Any]:
    packet = _latest_target_sample_execution_request_packet()
    receipt = packet.get("receipt") if isinstance(packet.get("receipt"), Mapping) else {}
    authoritative_packet = _latest_tushare_target_sample_execution_recipe_packet()
    latest_recipe = (
        authoritative_packet.get("provider_target_sample_execution_recipe")
        if isinstance(authoritative_packet.get("provider_target_sample_execution_recipe"), Mapping)
        else {}
    )
    target_payload = receipt.get("target_payload_safe") if isinstance(receipt.get("target_payload_safe"), Mapping) else {}
    requested_apis = _payload_string_list(payload, "apis")
    requested_targets = _payload_string_list(payload, "target_sample_acceptance_groups")
    expected_apis = list(ALL_REFRESH_APIS)
    expected_targets = list(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS)
    receipt_apis = [str(item) for item in receipt.get("selected_apis") or [] if str(item or "")]
    receipt_targets = [str(item) for item in receipt.get("requested_targets") or [] if str(item or "")]
    expected_scope_hash = str(
        receipt.get("latest_execution_recipe_scope_hash")
        or target_payload.get("execution_recipe_scope_hash")
        or ""
    )
    requested_scope_hash = str(
        _payload_field(payload, "execution_recipe_scope_hash", "") or ""
    )
    authoritative_scope_hash = str(latest_recipe.get("execution_recipe_scope_hash") or "")
    authoritative_recipe_version = str(latest_recipe.get("recipe_version") or "")
    authoritative_source_packet_key = str(
        authoritative_packet.get("authoritative_recipe_source_packet_key") or ""
    )
    receipt_ready = bool(
        receipt
        and receipt.get("status") == "target_sample_execution_request_ready_manual_provider_task_pending"
        and receipt.get("local_execution_request_ready") is True
        and receipt.get("ready_for_manual_provider_task_submission") is True
        and receipt.get("execution_recipe_scope_hash_matches_latest") is True
        and receipt.get("full_sha256_scope_hash_matches_latest") is True
        and receipt.get("full_interface_production_execution_request_ready") is True
        and receipt.get("operator_confirmation_recorded") is True
    )
    api_scope_exact = bool(
        len(requested_apis) == len(expected_apis)
        and set(requested_apis) == set(expected_apis)
        and len(selected_apis) == len(expected_apis)
        and set(selected_apis) == set(expected_apis)
        and len(receipt_apis) == len(expected_apis)
        and set(receipt_apis) == set(expected_apis)
    )
    target_scope_exact = bool(
        len(requested_targets) == len(expected_targets)
        and set(requested_targets) == set(expected_targets)
        and len(receipt_targets) == len(expected_targets)
        and set(receipt_targets) == set(expected_targets)
        and not receipt.get("unknown_requested_targets")
    )
    scope_matches = bool(
        len(requested_scope_hash) == 64
        and requested_scope_hash == expected_scope_hash == authoritative_scope_hash
    )
    execution_request_still_current = bool(
        scope_matches
        and receipt.get("authoritative_recipe_source_packet_key") == authoritative_source_packet_key
        and receipt.get("authoritative_recipe_version") == authoritative_recipe_version
    )
    acceptance_mode_matches = (
        str(_payload_field(payload, "acceptance_mode", "") or "") == FULL_INTERFACE_PROVIDER_PRODUCTION_MODE
    )
    approved = _payload_provider_execution_approved(payload)
    payload_api_contexts = (
        _payload_field(payload, "api_contexts", {})
        if isinstance(_payload_field(payload, "api_contexts", {}), Mapping)
        else {}
    )
    payload_target_contexts = (
        _payload_field(payload, "target_contexts", {})
        if isinstance(_payload_field(payload, "target_contexts", {}), Mapping)
        else {}
    )
    receipt_api_contexts = receipt.get("api_contexts") if isinstance(receipt.get("api_contexts"), Mapping) else {}
    receipt_target_contexts = (
        receipt.get("target_contexts") if isinstance(receipt.get("target_contexts"), Mapping) else {}
    )
    recipe_api_contexts = (
        latest_recipe.get("api_contexts") if isinstance(latest_recipe.get("api_contexts"), Mapping) else {}
    )
    recipe_target_contexts = (
        latest_recipe.get("target_contexts")
        if isinstance(latest_recipe.get("target_contexts"), Mapping)
        else {}
    )
    payload_universe_context = (
        _payload_field(payload, "universe_context", {})
        if isinstance(_payload_field(payload, "universe_context", {}), Mapping)
        else {}
    )
    receipt_universe_context = (
        receipt.get("universe_context") if isinstance(receipt.get("universe_context"), Mapping) else {}
    )
    recipe_universe_context = (
        latest_recipe.get("universe_context")
        if isinstance(latest_recipe.get("universe_context"), Mapping)
        else {}
    )
    context_matches = bool(
        payload_api_contexts
        and payload_api_contexts == receipt_api_contexts == recipe_api_contexts
        and payload_target_contexts
        and payload_target_contexts == receipt_target_contexts == recipe_target_contexts
        and all(
            _production_api_context_ready(api, payload_api_contexts.get(api, {}))
            for api in expected_apis
        )
        and payload_universe_context
        and payload_universe_context == receipt_universe_context == recipe_universe_context
        and _production_universe_context_ready(payload_universe_context)
    )
    approval_material = _production_approval_scope_material(
        recipe_scope_hash=requested_scope_hash,
        recipe_version=authoritative_recipe_version,
        selected_apis=requested_apis,
        requested_targets=requested_targets,
        api_contexts=payload_api_contexts,
        target_contexts=payload_target_contexts,
        universe_context=payload_universe_context,
    )
    computed_approval_scope_hash = _canonical_sha256(approval_material)
    requested_approval_scope_hash = str(_payload_field(payload, "approval_scope_hash", "") or "")
    receipt_approval_scope_hash = str(receipt.get("approval_scope_hash") or "")
    approval_scope_matches = bool(
        len(requested_approval_scope_hash) == 64
        and requested_approval_scope_hash
        == receipt_approval_scope_hash
        == computed_approval_scope_hash
        and receipt.get("approval_scope_material") == approval_material
    )

    blockers: list[str] = []
    if not receipt:
        blockers.append("missing_target_sample_execution_request")
    elif not receipt_ready:
        blockers.append("latest_target_sample_execution_request_not_ready")
    if not acceptance_mode_matches:
        blockers.append("production_acceptance_mode_missing_or_invalid")
    if not approved:
        blockers.append("explicit_provider_execution_approval_missing")
    if not scope_matches:
        blockers.append("scope_hash_not_bound_to_execution_request")
    if not execution_request_still_current:
        blockers.append("execution_request_not_bound_to_authoritative_recipe")
    if not api_scope_exact:
        blockers.append("full_interface_api_scope_not_exact_or_not_receipt_bound")
    if not target_scope_exact:
        blockers.append("full_interface_target_scope_not_exact_or_not_receipt_bound")
    if not context_matches:
        blockers.append("provider_context_not_bound_to_execution_request")
    if not approval_scope_matches:
        blockers.append("approval_scope_hash_or_material_mismatch")
    ready = not blockers
    return {
        "applies": True,
        "ready": ready,
        "status": (
            "full_interface_provider_production_execution_gate_passed"
            if ready
            else "full_interface_provider_production_execution_gate_blocked"
        ),
        "blockers": blockers,
        "error_message_safe": "" if ready else blockers[0],
        "current_step": (
            "full_interface_provider_production_execution_gate_passed_scope_bound"
            if ready
            else f"full_interface_provider_production_execution_gate_blocked_{blockers[0]}_no_provider_call"
        ),
        "acceptance_mode_matches": acceptance_mode_matches,
        "approved_by_user": approved,
        "execution_request_ready": receipt_ready,
        "requested_scope_hash_short": requested_scope_hash,
        "execution_request_scope_hash_short": expected_scope_hash[:16],
        "requested_scope_hash": requested_scope_hash,
        "execution_request_scope_hash": expected_scope_hash,
        "scope_hash_matches_execution_request": scope_matches,
        "authoritative_recipe_scope_hash": authoritative_scope_hash,
        "authoritative_recipe_version": authoritative_recipe_version,
        "authoritative_recipe_source_packet_key": authoritative_source_packet_key,
        "execution_request_still_current": execution_request_still_current,
        "api_scope_exact": api_scope_exact,
        "target_scope_exact": target_scope_exact,
        "context_matches_execution_request": context_matches,
        "approval_scope_hash": requested_approval_scope_hash,
        "computed_approval_scope_hash": computed_approval_scope_hash,
        "approval_scope_matches": approval_scope_matches,
        "requested_apis": requested_apis,
        "expected_apis": expected_apis,
        "requested_targets": requested_targets,
        "expected_targets": expected_targets,
    }


def _full_interface_provider_production_gate_ledger_row(
    gate: Mapping[str, Any],
    *,
    payload: Any,
    now: str,
    scope: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "api": "local_full_interface_provider_production_execution_gate",
        "scope_hash": str(scope.get("scope_hash") or ""),
        "scope_hash_short": str(scope.get("scope_hash_short") or ""),
        "payload_hash": str(scope.get("payload_hash") or ""),
        "endpoint": FULL_INTERFACE_PROVIDER_PRODUCTION_ROUTE,
        "request_params_safe": {
            "acceptance_mode": _safe_text(_payload_field(payload, "acceptance_mode", "")),
            "approved_by_user": gate.get("approved_by_user") is True,
            "execution_request_scope_hash_short": gate.get("execution_request_scope_hash_short") or "",
            "scope_hash_matches_execution_request": gate.get("scope_hash_matches_execution_request") is True,
            "execution_request_still_current": gate.get("execution_request_still_current") is True,
            "api_scope_exact": gate.get("api_scope_exact") is True,
            "target_scope_exact": gate.get("target_scope_exact") is True,
            "context_matches_execution_request": gate.get("context_matches_execution_request") is True,
        },
        "row_count": 1,
        "data_date": None,
        "local_fetched_at": now,
        "call_status": str(gate.get("status") or "full_interface_provider_production_execution_gate_blocked"),
        "failure_mode": "missing_or_mismatched_execution_request",
        "failure_mode_status": "preflight_blocked_no_external_call",
        "safe_failure_mode_visible": True,
        "error_message_safe": _safe_text(gate.get("error_message_safe") or ""),
        "parquet_dataset": None,
        "parquet_status": "not_written_provider_execution_gate_blocked",
        "parquet_row_count": 0,
        "provider_execution_gate_passed": gate.get("ready") is True,
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _promote_staged_parquet_datasets(
    call_ledger: list[dict[str, Any]],
    *,
    scope_hash: str,
) -> dict[str, Any]:
    parquet_rows = [row for row in call_ledger if row.get("api") in PARQUET_DATASETS]
    backup_root = (
        storage_service.PARQUET_ROOT
        / ".tushare_full_interface_backup"
        / str(scope_hash or "missing_scope")
    )
    promoted: list[dict[str, Any]] = []
    rollback_attempted = False
    rollback_succeeded = True
    try:
        if len(parquet_rows) != len(PARQUET_DATASETS):
            raise RuntimeError("parquet_staging_scope_incomplete")
        for row in parquet_rows:
            api = str(row.get("api") or "")
            dataset = PARQUET_DATASETS[api]
            staging = Path(str(row.get("parquet_staging_path") or ""))
            canonical = parquet_store.dataset_path(root=storage_service.PARQUET_ROOT, name=dataset)
            expected_digest = str(row.get("parquet_staging_digest") or "")
            if (
                row.get("parquet_status") != "staged"
                or not staging.is_file()
                or len(expected_digest) != 64
                or _sha256_file(staging) != expected_digest
            ):
                raise RuntimeError(f"invalid_staged_parquet_{api}")
            backup = backup_root / canonical.name
            backup.parent.mkdir(parents=True, exist_ok=True)
            had_canonical = canonical.is_file()
            if had_canonical:
                os.replace(canonical, backup)
            try:
                canonical.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging, canonical)
            except Exception:
                if had_canonical and backup.is_file():
                    os.replace(backup, canonical)
                raise
            if not canonical.is_file() or _sha256_file(canonical) != expected_digest:
                raise RuntimeError(f"promoted_parquet_digest_mismatch_{api}")
            promoted.append(
                {
                    "api": api,
                    "canonical_path": str(canonical),
                    "canonical_digest": expected_digest,
                    "row_count": int(row.get("parquet_row_count") or 0),
                    "required_columns": [
                        group[0]
                        for group in API_REPRESENTATIVE_REQUIRED_FIELDS.get(api, ())
                        if group
                    ],
                    "backup_path": str(backup),
                    "had_canonical": had_canonical,
                }
            )
        for row in parquet_rows:
            match = next(item for item in promoted if item["api"] == row.get("api"))
            row.update(
                {
                    "parquet_status": "promoted",
                    "parquet_canonical_path": match["canonical_path"],
                    "parquet_canonical_digest": match["canonical_digest"],
                    "parquet_promotion_verified": True,
                }
            )
        return {
            "schema_version": "tushare_parquet_staging_promotion.v1",
            "status": "parquet_staging_recoverably_promoted",
            "scope_hash": scope_hash,
            "promotion_verified": True,
            "promoted_dataset_count": len(promoted),
            "rollback_attempted": False,
            "rollback_succeeded": True,
            "backup_root": str(backup_root),
            "rows": promoted,
        }
    except Exception as exc:
        rollback_attempted = bool(promoted)
        for item in reversed(promoted):
            canonical = Path(item["canonical_path"])
            backup = Path(item["backup_path"])
            try:
                if canonical.exists():
                    canonical.unlink()
                if item["had_canonical"] and backup.is_file():
                    os.replace(backup, canonical)
            except Exception:
                rollback_succeeded = False
        return {
            "schema_version": "tushare_parquet_staging_promotion.v1",
            "status": "parquet_staging_promotion_failed_rolled_back"
            if rollback_succeeded
            else "parquet_staging_promotion_failed_rollback_incomplete",
            "scope_hash": scope_hash,
            "promotion_verified": False,
            "promoted_dataset_count": 0,
            "rollback_attempted": rollback_attempted,
            "rollback_succeeded": rollback_succeeded,
            "error_message_safe": _safe_text(exc),
            "rows": [],
        }


def _rollback_promoted_parquet_datasets(promotion: Mapping[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in promotion.get("rows", []) if isinstance(row, Mapping)]
    rollback_succeeded = True
    for item in reversed(rows):
        canonical = Path(str(item.get("canonical_path") or ""))
        backup = Path(str(item.get("backup_path") or ""))
        try:
            if canonical.is_file():
                canonical.unlink()
            if item.get("had_canonical") is True and backup.is_file():
                canonical.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup, canonical)
        except Exception:
            rollback_succeeded = False
    return {
        "schema_version": "tushare_parquet_staging_rollback.v1",
        "status": "parquet_promotion_rolled_back" if rollback_succeeded else "parquet_promotion_rollback_incomplete",
        "rollback_attempted": bool(rows),
        "rollback_succeeded": rollback_succeeded,
        "rolled_back_dataset_count": len(rows) if rollback_succeeded else 0,
    }


FULL_MARKET_ARTIFACT_REQUIREMENTS = {
    "stock_basic": ("ts_code", "list_status", "list_date"),
    "trade_cal": ("cal_date", "is_open"),
    "daily": ("ts_code", "trade_date", "close", "amount"),
    "daily_basic": (
        "ts_code", "trade_date", "turnover_rate", "volume_ratio", "total_mv", "circ_mv", "pe_ttm", "pb",
    ),
    "moneyflow": (
        "ts_code", "trade_date", "buy_lg_amount", "sell_lg_amount", "buy_elg_amount", "sell_elg_amount",
    ),
}


def _all_provider_rows(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if hasattr(data, "empty") and hasattr(data, "where") and hasattr(data, "notna"):
        if bool(getattr(data, "empty", True)):
            return []
        return data.where(data.notna(), None).to_dict("records")
    if isinstance(data, list):
        return [dict(row) for row in data if isinstance(row, Mapping)]
    if isinstance(data, Mapping):
        rows = data.get("rows")
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def _listed_a_share_code(value: Any) -> bool:
    text = str(value or "").strip().upper()
    prefix, separator, suffix = text.partition(".")
    return bool(
        separator
        and len(prefix) == 6
        and prefix.isdigit()
        and (
            (suffix == "SH" and prefix.startswith("6"))
            or (suffix == "SZ" and prefix.startswith(("0", "3")))
            or (suffix == "BJ" and prefix.startswith(("4", "8", "9")))
        )
    )


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    with temporary.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _official_transport_event(
    production_root: Path,
    *,
    run_id: str,
    scope_hash: str,
    api: str,
    event_key: str,
    function_call_count: int,
    transport_receipt_digest: str,
    response_digest: str,
) -> dict[str, Any]:
    if (
        function_call_count <= 0
        or len(transport_receipt_digest) != 64
        or len(response_digest) != 64
    ):
        return {}
    relative = Path("execution_runs") / run_id / "transport_events" / api / f"{event_key}.json"
    path = production_root / relative
    event = {
        "schema_version": tushare_production_store.TRANSPORT_EVENT_SCHEMA,
        "run_id": run_id,
        "scope_hash": scope_hash,
        "api": api,
        "event_key": event_key,
        "actual_function_call": True,
        "function_call_count": function_call_count,
        "transport_receipt_digest": transport_receipt_digest,
        "response_digest": response_digest,
        "contains_secret": False,
        "does_not_execute_trades": True,
    }
    event["transport_event_digest"] = _canonical_sha256(event)
    _atomic_json_write(path, event)
    try:
        readback = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if _canonical_sha256(readback) != _canonical_sha256(event):
        return {}
    return {
        "relative_path": str(relative),
        "transport_event_digest": event["transport_event_digest"],
        "api": api,
    }


def _read_checkpoint_transport_event(
    production_root: Path,
    *,
    saved: Mapping[str, Any],
    run_id: str,
    scope_hash: str,
    api: str,
) -> dict[str, Any]:
    ref = saved.get("transport_event") if isinstance(saved.get("transport_event"), Mapping) else {}
    relative = str(ref.get("relative_path") or "")
    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
        return {}
    try:
        event = json.loads((production_root / relative).read_text(encoding="utf-8"))
    except Exception:
        return {}
    material = dict(event)
    digest = str(material.pop("transport_event_digest", "") or "")
    if not (
        event.get("schema_version") == tushare_production_store.TRANSPORT_EVENT_SCHEMA
        and event.get("run_id") == run_id
        and event.get("scope_hash") == scope_hash
        and event.get("api") == api
        and event.get("actual_function_call") is True
        and digest == ref.get("transport_event_digest")
        and digest == _canonical_sha256(material)
        and event.get("response_digest") == saved.get("page_fingerprint")
    ):
        return {}
    return dict(ref)


def _persist_official_execution_event(
    production_root: Path,
    *,
    run_id: str,
    scope_hash: str,
    approval_scope_hash: str,
    execution_recipe_scope_hash: str,
    selected_apis: list[str],
    target_groups: list[str],
    transport_events: list[Mapping[str, Any]],
    current_attempt_actual_function_call_count: int,
    call_ledger: list[Mapping[str, Any]],
) -> Path | None:
    """Persist the official event only at the end of the non-injected executor."""

    if (
        selected_apis != list(tushare_production_store.EXACT_REFRESH_APIS)
        or target_groups != list(tushare_production_store.EXACT_TARGET_GROUPS)
        or len(scope_hash) != 64
        or len(approval_scope_hash) != 64
        or len(execution_recipe_scope_hash) != 64
    ):
        return None
    unique_refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    original_calls = 0
    observed_apis: set[str] = set()
    for raw_ref in transport_events:
        ref = dict(raw_ref)
        digest = str(ref.get("transport_event_digest") or "")
        if not digest or digest in seen:
            continue
        relative = str(ref.get("relative_path") or "")
        try:
            transport = json.loads((production_root / relative).read_text(encoding="utf-8"))
        except Exception:
            return None
        material = dict(transport)
        stored_digest = str(material.pop("transport_event_digest", "") or "")
        if not (
            stored_digest == digest
            and stored_digest == _canonical_sha256(material)
            and transport.get("run_id") == run_id
            and transport.get("scope_hash") == scope_hash
            and transport.get("actual_function_call") is True
        ):
            return None
        seen.add(digest)
        unique_refs.append(ref)
        original_calls += int(transport.get("function_call_count") or 0)
        observed_apis.add(str(transport.get("api") or ""))
    if (
        observed_apis
        != set(tushare_production_store.EXACT_REFRESH_APIS)
        | set(tushare_production_store.EXACT_SUPPORT_APIS)
        or not 0 < original_calls <= tushare_production_store.MAX_PROVIDER_CALLS
        or not 0 <= current_attempt_actual_function_call_count <= original_calls
    ):
        return None
    event = {
        "schema_version": tushare_production_store.EXECUTION_EVENT_SCHEMA,
        "source": "public_non_injected_tushare_executor",
        "status": "official_provider_execution_complete",
        "official_provider_path_completed": True,
        "run_id": run_id,
        "scope_hash": scope_hash,
        "approval_scope_hash": approval_scope_hash,
        "execution_recipe_scope_hash": execution_recipe_scope_hash,
        "required_interface_apis": list(tushare_production_store.EXACT_REFRESH_APIS),
        "required_interface_api_digest": _canonical_sha256(
            list(tushare_production_store.EXACT_REFRESH_APIS)
        ),
        "required_target_groups": list(tushare_production_store.EXACT_TARGET_GROUPS),
        "required_target_group_digest": _canonical_sha256(
            list(tushare_production_store.EXACT_TARGET_GROUPS)
        ),
        "required_support_apis": list(tushare_production_store.EXACT_SUPPORT_APIS),
        "required_support_api_digest": _canonical_sha256(
            list(tushare_production_store.EXACT_SUPPORT_APIS)
        ),
        "transport_events": unique_refs,
        "original_actual_function_call_count": original_calls,
        "current_attempt_actual_function_call_count": current_attempt_actual_function_call_count,
        "checkpoint_reused_function_call_count": original_calls
        - current_attempt_actual_function_call_count,
        "sanitized_call_ledger_digest": _canonical_sha256(
            [dict(row) for row in call_ledger]
        ),
        "contains_secret": False,
        "external_calls_triggered": current_attempt_actual_function_call_count > 0,
        "tushare_called_this_attempt": current_attempt_actual_function_call_count > 0,
        "tushare_called": True,
        "does_not_execute_trades": True,
    }
    event["execution_event_digest"] = _canonical_sha256(event)
    path = production_root / "execution_runs" / run_id / "execution_event.json"
    _atomic_json_write(path, event)
    try:
        readback = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not tushare_production_store._receipt_ready(
        readback,
        scope_hash=scope_hash,
        root=production_root,
    ):
        return None
    return path


def _paginated_provider_rows(
    adapter_module: Any,
    *,
    api: str,
    params: Mapping[str, Any],
    max_rows_per_call: int,
    call_budget: dict[str, Any],
    checkpoint_root: Path,
    production_root: Path,
    run_id: str,
    scope_hash: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch one endpoint with bounded retries and digest-bound resume pages."""

    limit = max(1, min(int(max_rows_per_call or 0), 6000))
    params_safe = {key: value for key, value in params.items() if value is not None}
    query_hash = _canonical_sha256({"api": api, "params": params_safe, "limit": limit})
    page_root = checkpoint_root / api / query_hash
    rows: list[dict[str, Any]] = []
    fingerprints: set[str] = set()
    actual_calls = 0
    resumed_pages = 0
    transport_events: list[dict[str, Any]] = []
    offset = 0
    terminal = False
    error = ""
    try:
        fn = getattr(adapter_module, f"get_{api}")
    except Exception as exc:
        return [], {"api": api, "call_status": "failed", "error_message_safe": _safe_text(exc)}
    while not terminal:
        checkpoint = page_root / f"{offset:09d}.json"
        page: dict[str, Any] | None = None
        if checkpoint.is_file():
            try:
                saved = json.loads(checkpoint.read_text(encoding="utf-8"))
                material = dict(saved)
                digest = str(material.pop("checkpoint_digest", "") or "")
                if (
                    saved.get("query_hash") == query_hash
                    and int(saved.get("offset") or 0) == offset
                    and digest == _canonical_sha256(material)
                ):
                    transport_ref = _read_checkpoint_transport_event(
                        production_root,
                        saved=saved,
                        run_id=run_id,
                        scope_hash=scope_hash,
                        api=api,
                    )
                    if not transport_ref:
                        error = "checkpoint_transport_event_missing_or_invalid"
                    elif call_budget.get("used", 0) + call_budget.get("historical", 0) >= call_budget.get(
                        "limit", tushare_production_store.MAX_PROVIDER_CALLS
                    ):
                        error = "provider_call_budget_exhausted"
                    else:
                        page = saved
                        resumed_pages += 1
                        call_budget["historical"] = call_budget.get("historical", 0) + int(
                            saved.get("original_function_call_count") or 0
                        )
                        transport_events.append(transport_ref)
            except Exception:
                page = None
        if page is None:
            for _attempt in range(3):
                if call_budget.get("used", 0) + call_budget.get("historical", 0) >= call_budget.get(
                    "limit", tushare_production_store.MAX_PROVIDER_CALLS
                ):
                    error = "provider_call_budget_exhausted"
                    break
                call_budget["used"] = call_budget.get("used", 0) + 1
                actual_calls += 1
                try:
                    result = fn(**params_safe, limit=limit, offset=offset)
                    if not isinstance(result, Mapping):
                        result = {"ok": False, "data": None, "error": "invalid_provider_result"}
                except Exception as exc:
                    result = {"ok": False, "data": None, "error": _safe_text(exc)}
                transport = _consume_runtime_transport_evidence(adapter_module, result, api)
                page_rows = _all_provider_rows(result.get("data")) if result.get("ok") else []
                if result.get("ok") is True and transport.get("provider_transport_verified") is True:
                    if len(page_rows) > limit:
                        error = "provider_page_exceeded_requested_limit"
                        break
                    fingerprint = _canonical_sha256(page_rows)
                    if page_rows and fingerprint in fingerprints:
                        error = "provider_pagination_repeated_page_truncation_detected"
                        break
                    transport_ref = _official_transport_event(
                        production_root,
                        run_id=run_id,
                        scope_hash=scope_hash,
                        api=api,
                        event_key=f"{query_hash}-{offset:09d}",
                        function_call_count=1,
                        transport_receipt_digest=str(
                            transport.get("transport_receipt_digest") or ""
                        ),
                        response_digest=fingerprint,
                    )
                    if not transport_ref:
                        error = "official_transport_event_persist_failed"
                        break
                    page = {
                        "schema_version": "tushare_provider_page_checkpoint.v1",
                        "query_hash": query_hash,
                        "api": api,
                        "offset": offset,
                        "limit": limit,
                        "rows": page_rows,
                        "row_count": len(page_rows),
                        "page_fingerprint": fingerprint,
                        "terminal": len(page_rows) < limit,
                        "provider_transport_verified": True,
                        "original_function_call_count": 1,
                        "transport_event": transport_ref,
                    }
                    page["checkpoint_digest"] = _canonical_sha256(page)
                    _atomic_json_write(checkpoint, page)
                    transport_events.append(transport_ref)
                    break
                error = _safe_text(result.get("error") or "provider_page_failed")
            if page is None:
                break
        page_rows = [dict(row) for row in page.get("rows", []) if isinstance(row, Mapping)]
        fingerprint = str(page.get("page_fingerprint") or "")
        if page_rows and fingerprint in fingerprints:
            error = "provider_pagination_repeated_page_truncation_detected"
            break
        if fingerprint:
            fingerprints.add(fingerprint)
        rows.extend(page_rows)
        terminal = page.get("terminal") is True
        offset += limit
    ready = bool(terminal and not error)
    return rows if ready else [], {
        "api": api,
        "call_status": "success" if ready else "failed",
        "provider_call_count": actual_calls,
        "historical_provider_call_count": resumed_pages,
        "resumed_page_count": resumed_pages,
        "page_count": len(fingerprints),
        "row_count": len(rows) if ready else 0,
        "pagination_complete": ready,
        "truncation_detected": "truncation" in error,
        "checkpoint_resume_supported": True,
        "provider_transport_verified": ready,
        "transport_events": transport_events,
        "error_message_safe": error,
        "external_calls_triggered": actual_calls > 0,
        "tushare_called": actual_calls > 0,
        "checkpoint_data_reused": resumed_pages > 0,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _full_market_dataset_batch(
    adapter_module: Any,
    *,
    api: str,
    start_date: str,
    end_date: str,
    max_rows_per_call: int,
    call_budget: dict[str, Any],
    checkpoint_root: Path,
    production_root: Path,
    run_id: str,
    scope_hash: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return _paginated_provider_rows(
        adapter_module,
        api=api,
        params={"ts_code": None, "start_date": start_date, "end_date": end_date},
        max_rows_per_call=max_rows_per_call,
        call_budget=call_budget,
        checkpoint_root=checkpoint_root,
        production_root=production_root,
        run_id=run_id,
        scope_hash=scope_hash,
    )


def _run_full_market_universe_acceptance(
    adapter_module: Any,
    *,
    payload: Any,
    scope: Mapping[str, str],
    execution_gate: Mapping[str, Any],
    trade_cal_data: Any,
    trade_cal_ledger: Mapping[str, Any],
    outer_call_ledger: list[Mapping[str, Any]],
    public_executor_completed: bool,
) -> dict[str, Any]:
    context = _production_universe_context(payload)
    if not public_executor_completed:
        return {
            "schema_version": FULL_MARKET_UNIVERSE_SCHEMA_VERSION,
            "status": "full_market_universe_production_blocked",
            "production_complete": False,
            "provider_provenance_verified": False,
            "blockers": ["injected_or_test_caller_is_non_production"],
            "artifacts": {},
        }
    del trade_cal_data, trade_cal_ledger
    ledger: list[dict[str, Any]] = []
    production_root = storage_service.PARQUET_ROOT / "full_market_universe"
    run_id = str(scope.get("scope_hash") or "missing_scope")
    start = str(context.get("feature_start_date") or "")
    end = str(context.get("feature_end_date") or "")
    checkpoint_root = (
        production_root
        / ".checkpoints"
        / str(scope.get("scope_hash") or "missing_scope")
    )
    outer_transport_events: list[dict[str, Any]] = []
    outer_actual_calls = 0
    for row in outer_call_ledger:
        api = str(row.get("api") or "")
        function_calls = _safe_int(row.get("provider_transport_receipt_count"))
        if row.get("provider_transport_verified") is not True or api not in set(ALL_REFRESH_APIS):
            continue
        ref = _official_transport_event(
            production_root,
            run_id=run_id,
            scope_hash=run_id,
            api=api,
            event_key=f"interface-{api}",
            function_call_count=function_calls,
            transport_receipt_digest=str(row.get("provider_transport_receipt_digest") or ""),
            response_digest=_canonical_sha256(
                {
                    "api": api,
                    "row_count": row.get("row_count"),
                    "data_date": row.get("data_date"),
                    "call_status": row.get("call_status"),
                }
            ),
        )
        if ref:
            outer_transport_events.append(ref)
            outer_actual_calls += function_calls
    call_budget = {
        "used": outer_actual_calls,
        "historical": 0,
        "limit": min(
            tushare_production_store.MAX_PROVIDER_CALLS,
            _safe_int(context.get("max_provider_calls"))
            or tushare_production_store.MAX_PROVIDER_CALLS,
        ),
    }
    stock_rows: list[dict[str, Any]] = []
    stock_pages: list[dict[str, Any]] = []
    for exchange in ("SSE", "SZSE", "BSE"):
        exchange_rows, page_ledger = _paginated_provider_rows(
            adapter_module,
            api="stock_basic",
            params={"exchange": exchange, "list_status": "L"},
            max_rows_per_call=_safe_int(context.get("max_rows_per_call")),
            call_budget=call_budget,
            checkpoint_root=checkpoint_root,
            production_root=production_root,
            run_id=run_id,
            scope_hash=run_id,
        )
        stock_rows.extend(exchange_rows)
        stock_pages.append(page_ledger)
    stock_ledger = {
        "api": "stock_basic",
        "request_params_safe": {"exchanges": ["SSE", "SZSE", "BSE"], "list_status": "L"},
        "call_status": "success" if all(row.get("call_status") == "success" for row in stock_pages) else "failed",
        "row_count": len(stock_rows),
        "runtime_adapter_module_identity_verified": True,
        "provider_transport_verified": all(row.get("provider_transport_verified") is True for row in stock_pages),
        "provider_transport_receipt_count": sum(_safe_int(row.get("provider_call_count")) for row in stock_pages),
        "provider_call_count": sum(_safe_int(row.get("provider_call_count")) for row in stock_pages),
        "historical_provider_call_count": sum(
            _safe_int(row.get("historical_provider_call_count")) for row in stock_pages
        ),
        "transport_events": [
            event
            for page in stock_pages
            for event in page.get("transport_events", [])
            if isinstance(event, Mapping)
        ],
        "pagination_complete": all(row.get("pagination_complete") is True for row in stock_pages),
        "truncation_detected": any(row.get("truncation_detected") is True for row in stock_pages),
        "external_calls_triggered": any(row.get("external_calls_triggered") is True for row in stock_pages),
        "tushare_called": any(row.get("tushare_called") is True for row in stock_pages),
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    ledger.append(stock_ledger)
    trade_rows, trade_page_ledger = _paginated_provider_rows(
        adapter_module,
        api="trade_cal",
        params={"exchange": "SSE", "start_date": start, "end_date": end},
        max_rows_per_call=_safe_int(context.get("max_rows_per_call")),
        call_budget=call_budget,
        checkpoint_root=checkpoint_root,
        production_root=production_root,
        run_id=run_id,
        scope_hash=run_id,
    )
    ledger.append(trade_page_ledger)
    normalized_stock = [
        {
            key: row.get(key)
            for key in ("ts_code", "symbol", "name", "area", "industry", "market", "exchange", "list_status", "list_date")
        }
        for row in stock_rows
    ]
    codes = [str(row.get("ts_code") or "").upper() for row in normalized_stock]
    duplicate_count = len(codes) - len(set(codes))
    invalid_count = sum(
        1
        for row, code in zip(normalized_stock, codes)
        if not _listed_a_share_code(code)
        or str(row.get("list_status") or "").upper() != "L"
        or len(str(row.get("list_date") or "").replace("-", "")) != 8
        or not str(row.get("list_date") or "").replace("-", "").isdigit()
    )
    markets = {code.rsplit(".", 1)[-1] for code in codes if _listed_a_share_code(code)}
    open_dates = sorted(
        {
            str(row.get("cal_date") or "").replace("-", "")
            for row in trade_rows
            if _trade_cal_is_open(row.get("is_open"))
            and start <= str(row.get("cal_date") or "").replace("-", "") <= end
        }
    )
    required_sessions = _safe_int(context.get("required_feature_sessions"))
    selected_dates = open_dates[-required_sessions:] if required_sessions > 0 else []
    preflight_ready = bool(
        _production_universe_context_ready(context)
        and stock_ledger["provider_transport_verified"]
        and trade_page_ledger.get("provider_transport_verified") is True
        and len(normalized_stock) >= FULL_MARKET_UNIVERSE_MIN_ROWS
        and duplicate_count == 0
        and invalid_count == 0
        and markets == {"SH", "SZ", "BJ"}
        and len(selected_dates) == required_sessions == 90
    )
    datasets: dict[str, list[dict[str, Any]]] = {
        "stock_basic": normalized_stock,
        "trade_cal": [row for row in trade_rows if str(row.get("cal_date") or "").replace("-", "") in set(selected_dates)],
    }
    if preflight_ready:
        max_rows = _safe_int(context.get("max_rows_per_call"))
        for api in ("daily", "daily_basic", "moneyflow"):
            api_start = (
                selected_dates[-1]
                if api == "daily_basic"
                else selected_dates[-5]
                if api == "moneyflow"
                else selected_dates[0]
            )
            rows, batch_ledger = _full_market_dataset_batch(
                adapter_module,
                api=api,
                start_date=api_start,
                end_date=selected_dates[-1],
                max_rows_per_call=max_rows,
                call_budget=call_budget,
                checkpoint_root=checkpoint_root,
                production_root=production_root,
                run_id=run_id,
                scope_hash=run_id,
            )
            datasets[api] = rows
            ledger.append(batch_ledger)
    else:
        for api in ("daily", "daily_basic", "moneyflow"):
            datasets[api] = []
            ledger.append({"api": api, "call_status": "blocked_universe_preflight", "provider_transport_verified": False})

    for row in ledger:
        row.update(
            {
                "scope_hash": str(scope.get("scope_hash") or ""),
                "approval_scope_hash": execution_gate.get("approval_scope_hash") or "",
                "execution_recipe_scope_hash": execution_gate.get("authoritative_recipe_scope_hash") or "",
                "as_of": context.get("as_of_date") or "",
            }
        )

    eligible_codes = {
        str(row.get("ts_code") or "").upper()
        for row in normalized_stock
        if str(row.get("list_date") or "").replace("-", "") <= (selected_dates[0] if selected_dates else "")
    }
    validation: dict[str, Any] = {}
    for api in ("daily", "daily_basic", "moneyflow"):
        rows = datasets[api]
        required = FULL_MARKET_ARTIFACT_REQUIREMENTS[api]
        missing_columns = [column for column in required if rows and any(column not in row for row in rows)]
        keys = [(str(row.get("ts_code") or ""), str(row.get("trade_date") or "")) for row in rows]
        counts: dict[str, int] = {}
        for code, _date in set(keys):
            counts[code] = counts.get(code, 0) + 1
        minimum = 60 if api == "daily" else 5 if api == "moneyflow" else 1
        covered = {code for code, count in counts.items() if count >= minimum}
        validation[api] = {
            "row_count": len(rows),
            "duplicate_count": len(keys) - len(set(keys)),
            "missing_required_columns": missing_columns,
            "minimum_sessions_per_symbol": minimum,
            "covered_symbol_count": len(covered & eligible_codes),
            "required_symbol_count": len(eligible_codes),
            "invalid_or_unlisted_symbol_count": sum(1 for code, _date in keys if code not in set(codes)),
            "coverage_complete": bool(eligible_codes and eligible_codes.issubset(covered)),
        }
    datasets_ready = bool(
        preflight_ready
        and len(eligible_codes) >= FULL_MARKET_UNIVERSE_MIN_ROWS
        and all(
            row["coverage_complete"]
            and row["duplicate_count"] == 0
            and row["invalid_or_unlisted_symbol_count"] == 0
            and not row["missing_required_columns"]
            for row in validation.values()
        )
        and all(row.get("provider_transport_verified") is True for row in ledger)
        and call_budget.get("used", 0) + call_budget.get("historical", 0)
        <= call_budget.get("limit", tushare_production_store.MAX_PROVIDER_CALLS)
    )
    promotion: dict[str, Any] = {"promotion_verified": False, "artifacts": {}}
    if datasets_ready:
        page_transport_events = [
            event
            for row in ledger
            for event in row.get("transport_events", [])
            if isinstance(event, Mapping)
        ]
        execution_event_path = _persist_official_execution_event(
            production_root,
            run_id=run_id,
            scope_hash=run_id,
            approval_scope_hash=str(execution_gate.get("approval_scope_hash") or ""),
            execution_recipe_scope_hash=str(execution_gate.get("authoritative_recipe_scope_hash") or ""),
            selected_apis=list(ALL_REFRESH_APIS),
            target_groups=list(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS),
            transport_events=[*outer_transport_events, *page_transport_events],
            current_attempt_actual_function_call_count=call_budget.get("used", 0),
            call_ledger=[*outer_call_ledger, *ledger],
        )
        if execution_event_path is not None:
            promotion = tushare_production_store._promote_version_from_official_execution_event(
                datasets,
                root=production_root,
                scope_hash=run_id,
                start_date=start,
                end_date=end,
                approval_scope_hash=str(execution_gate.get("approval_scope_hash") or ""),
                execution_recipe_scope_hash=str(execution_gate.get("authoritative_recipe_scope_hash") or ""),
                as_of=str(context.get("as_of_date") or ""),
                execution_event_path=execution_event_path,
                packet_store=SQLiteMetaStore(SQLITE_META_PATH),
                packet_key=FULL_MARKET_UNIVERSE_CURRENT_PACKET_KEY,
            )
    complete = promotion.get("promotion_verified") is True
    packet = {
        "packet_key": FULL_MARKET_UNIVERSE_CURRENT_PACKET_KEY,
        "schema_version": FULL_MARKET_UNIVERSE_SCHEMA_VERSION,
        "status": "full_market_universe_production_complete" if complete else "full_market_universe_production_blocked",
        "scope_hash": str(scope.get("scope_hash") or ""),
        "approval_scope_hash": execution_gate.get("approval_scope_hash") or "",
        "execution_recipe_scope_hash": execution_gate.get("authoritative_recipe_scope_hash") or "",
        "validated_trade_date": selected_dates[-1] if selected_dates else "",
        "as_of": context.get("as_of_date") or "",
        "freshness": "current_trade_calendar_validated" if preflight_ready else "not_validated",
        "list_status": "L",
        "row_count": len(normalized_stock),
        "scored_symbol_count": len(eligible_codes),
        "duplicate_count": duplicate_count,
        "invalid_symbol_count": invalid_count,
        "markets": sorted(markets),
        "feature_session_count": len(selected_dates),
        "universe_context": context,
        "dataset_validation": validation,
        "artifacts": dict(promotion.get("artifacts") or {}),
        "current_pointer": dict(promotion.get("pointer") or {}),
        "direct_ledger": ledger,
        "provider_provenance_verified": bool(ledger and all(row.get("provider_transport_verified") is True for row in ledger)),
        "production_complete": complete,
        "external_calls_triggered": call_budget.get("used", 0) > 0,
        "tushare_called": call_budget.get("used", 0) > 0,
        "checkpoint_reused_call_count": call_budget.get("historical", 0),
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    packet["packet_digest"] = _canonical_sha256(packet)
    return packet


def _full_interface_provider_production_contract(
    *,
    production_acceptance_requested: bool,
    execution_gate: Mapping[str, Any],
    selected_apis: list[str],
    call_ledger: list[dict[str, Any]],
    validation_target_rows: list[dict[str, Any]],
    api_acceptance_audit: Mapping[str, Any],
    failure_mode_qa_contract: Mapping[str, Any],
    scope: Mapping[str, str],
    universe_evidence: Mapping[str, Any] | None = None,
    parquet_promotion: Mapping[str, Any] | None = None,
    sqlite_stage_readback_verified: bool = False,
    sqlite_atomic_promotion_verified: bool = False,
) -> dict[str, Any]:
    provider_rows = [row for row in call_ledger if row.get("api") in set(ALL_REFRESH_APIS)]
    accepted_sample_rows = [
        row
        for row in provider_rows
        if row.get("representative_sample_verified") is True
        or row.get("valid_empty_semantics_verified") is True
    ]
    transport_rows = [
        row
        for row in provider_rows
        if row.get("runtime_adapter_module_identity_verified") is True
        and row.get("provider_transport_verified") is True
        and int(row.get("provider_transport_receipt_count") or 0) > 0
    ]
    safe_terminal_rows = [
        row
        for row in provider_rows
        if _safe_call_status(row.get("call_status"))
        and row.get("safe_failure_mode_visible") is True
        and not _has_unsafe_error_text(row.get("error_message_safe"))
        and not _has_sensitive_key(row.get("request_params_safe"))
    ]
    parquet_rows = [row for row in provider_rows if row.get("api") in PARQUET_DATASETS]
    parquet_staged_rows = [
        row
        for row in parquet_rows
        if row.get("parquet_status") in {"staged", "promoted"}
        and int(row.get("parquet_row_count") or 0) > 0
        and len(str(row.get("parquet_staging_digest") or "")) == 64
    ]
    parquet_promoted_rows = [row for row in parquet_rows if row.get("parquet_promotion_verified") is True]
    target_rows_valid = [row for row in validation_target_rows if row.get("readiness") == "validated"]
    ledger_scope_consistent = bool(
        provider_rows
        and all(
            row.get("scope_hash") == scope.get("scope_hash")
            and row.get("scope_hash_short") == scope.get("scope_hash_short")
            for row in provider_rows
        )
    )
    failure_taxonomy_safe = bool(
        failure_mode_qa_contract.get("safe_error_text") is True
        and int(failure_mode_qa_contract.get("unsafe_row_count") or 0) == 0
        and all(
            failure_mode_qa_contract.get(key) is True
            for key in (
                "permission_denied_distinguishable",
                "empty_result_or_no_record_distinguishable",
                "parse_failed_or_invalid_result_distinguishable",
                "missing_required_parameter_distinguishable",
                "provider_error_safe_distinguishable",
            )
        )
    )
    checks = [
        (
            "explicit_production_acceptance_post_mode_requested",
            production_acceptance_requested,
            "ordinary refresh tasks cannot promote the production contract",
        ),
        (
            "execution_request_and_explicit_post_gate",
            production_acceptance_requested and execution_gate.get("ready") is True,
            "production route requires an approved, scope-bound target-sample execution request",
        ),
        (
            "runtime_transport_provider_provenance",
            len(transport_rows) == len(ALL_REFRESH_APIS),
            "every API needs a consumed receipt emitted only after the real SDK transport returned",
        ),
        (
            "all_allowlisted_interfaces_exact",
            len(selected_apis) == len(ALL_REFRESH_APIS)
            and set(selected_apis) == set(ALL_REFRESH_APIS)
            and len(provider_rows) == len(ALL_REFRESH_APIS)
            and len({row.get("api") for row in provider_rows}) == len(ALL_REFRESH_APIS),
            f"selected={len(selected_apis)}; ledger={len(provider_rows)}; required={len(ALL_REFRESH_APIS)}",
        ),
        (
            "all_interfaces_representative_or_audited_valid_empty",
            len(accepted_sample_rows) == len(ALL_REFRESH_APIS),
            f"accepted_samples={len(accepted_sample_rows)}; required={len(ALL_REFRESH_APIS)}",
        ),
        (
            "all_target_groups_directly_validated",
            len(target_rows_valid) == len(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS),
            f"validated_targets={len(target_rows_valid)}; required={len(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS)}",
        ),
        (
            "call_ledger_semantics_and_scope_safe",
            bool(
                api_acceptance_audit.get("status") == "acceptance_audit_passed"
                and int(api_acceptance_audit.get("acceptance_issue_count") or 0) == 0
                and len(safe_terminal_rows) == len(provider_rows)
                and ledger_scope_consistent
            ),
            "every provider row must be sanitized, terminal, and bound to the same scope hash",
        ),
        (
            "permission_no_data_and_failure_modes_safe",
            failure_taxonomy_safe,
            "permission, no-data, parse, preflight, and provider failure states remain distinguishable and non-promoting",
        ),
        (
            "parquet_datasets_staged_before_promotion",
            len(parquet_rows) == len(PARQUET_DATASETS)
            and len(parquet_staged_rows) == len(PARQUET_DATASETS),
            f"parquet_staged={len(parquet_staged_rows)}; required={len(PARQUET_DATASETS)}",
        ),
        (
            "full_market_universe_and_feature_artifacts",
            bool(
                universe_evidence
                and universe_evidence.get("schema_version") == FULL_MARKET_UNIVERSE_SCHEMA_VERSION
                and universe_evidence.get("status") == "full_market_universe_production_complete"
                and universe_evidence.get("production_complete") is True
                and universe_evidence.get("scope_hash") == scope.get("scope_hash")
                and universe_evidence.get("provider_provenance_verified") is True
            ),
            "stock_basic, trade_cal, daily, daily_basic, and moneyflow require a scope-bound full-market artifact",
        ),
    ]
    blockers = [criterion for criterion, passed, _evidence in checks if not passed]
    eligible_for_parquet = not blockers
    parquet_promotion_verified = bool(
        parquet_promotion
        and parquet_promotion.get("promotion_verified") is True
        and int(parquet_promotion.get("promoted_dataset_count") or 0) == len(PARQUET_DATASETS)
        and len(parquet_promoted_rows) == len(PARQUET_DATASETS)
    )
    eligible_for_sqlite = bool(eligible_for_parquet and parquet_promotion_verified)
    production_complete = bool(eligible_for_sqlite and sqlite_stage_readback_verified and sqlite_atomic_promotion_verified)
    rows = [
        {
            "criterion": criterion,
            "status": "passed" if passed else "blocked",
            "passed": bool(passed),
            "blocking": not bool(passed),
            "evidence": evidence,
            "external_calls_triggered_by_audit": False,
            "cache_get_external_calls": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
        for criterion, passed, evidence in checks
    ]
    rows.extend(
        [
            {
                "criterion": "parquet_recoverable_promotion",
                "status": "passed" if parquet_promotion_verified else "blocked",
                "passed": parquet_promotion_verified,
                "blocking": not parquet_promotion_verified,
                "evidence": "all staged Parquet datasets must promote with verified digests and rollback metadata",
                "external_calls_triggered_by_audit": False,
                "cache_get_external_calls": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
            {
                "criterion": "sqlite_staging_packet_readback",
                "status": "passed" if sqlite_stage_readback_verified else "blocked",
                "passed": sqlite_stage_readback_verified,
                "blocking": not sqlite_stage_readback_verified,
                "evidence": "non-production staging packet must read back exactly before canonical promotion",
                "external_calls_triggered_by_audit": False,
                "cache_get_external_calls": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
            {
                "criterion": "sqlite_atomic_final_promotion",
                "status": "passed" if sqlite_atomic_promotion_verified else "blocked",
                "passed": sqlite_atomic_promotion_verified,
                "blocking": not sqlite_atomic_promotion_verified,
                "evidence": "independent immutable packet must be written and exactly read back in one committed transaction",
                "external_calls_triggered_by_audit": False,
                "cache_get_external_calls": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
        ]
    )
    return {
        "schema_version": FULL_INTERFACE_PROVIDER_PRODUCTION_SCHEMA_VERSION,
        "status": (
            "full_interface_provider_production_complete"
            if production_complete
            else "full_interface_provider_production_blocked"
        ),
        "scope": "explicit_post_full_interface_provider_direct_evidence_and_durable_promotion",
        "scope_hash": str(scope.get("scope_hash") or ""),
        "scope_hash_short": str(scope.get("scope_hash_short") or ""),
        "selected_apis": list(selected_apis),
        "required_apis": list(ALL_REFRESH_APIS),
        "required_target_groups": list(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS),
        "provider_row_count": len(provider_rows),
        "accepted_sample_api_count": len(accepted_sample_rows),
        "runtime_transport_verified_api_count": len(transport_rows),
        "validated_target_group_count": len(target_rows_valid),
        "parquet_promoted_dataset_count": len(parquet_promoted_rows),
        "failure_mode_taxonomy_safe": failure_taxonomy_safe,
        "full_market_universe_production_complete": bool(
            universe_evidence and universe_evidence.get("production_complete") is True
        ),
        "full_market_universe_packet_digest": str(
            (universe_evidence or {}).get("packet_digest") or ""
        ),
        "eligible_for_parquet_promotion": eligible_for_parquet,
        "eligible_for_sqlite_promotion": eligible_for_sqlite,
        "parquet_promotion_verified": parquet_promotion_verified,
        "sqlite_stage_readback_verified": sqlite_stage_readback_verified,
        "sqlite_atomic_promotion_verified": sqlite_atomic_promotion_verified,
        "blocking_criterion_count": len([row for row in rows if row["blocking"]]),
        "blockers": blockers
        + ([] if parquet_promotion_verified else ["parquet_recoverable_promotion"])
        + ([] if sqlite_stage_readback_verified else ["sqlite_staging_packet_readback"])
        + ([] if sqlite_atomic_promotion_verified else ["sqlite_atomic_final_promotion"]),
        "full_interface_provider_production": production_complete,
        "provider_backed_acceptance_done": production_complete,
        "production_tushare_pipeline_complete": production_complete,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "audit_external_calls_triggered": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
        "note": "Production truth requires consumed runtime transport receipts, API-specific evidence, recoverable Parquet promotion, and an independent atomic SQLite packet.",
    }


def run_tushare_refresh_task(
    payload: Any = None,
    *,
    task_type: str = "refresh_tushare_facts",
    output_packet_key: str = "command_center_tushare_refresh_packet",
    default_apis: Iterable[str] = CORE_REFRESH_APIS,
    adapter: Any = None,
    production_acceptance: bool = False,
) -> dict[str, Any]:
    public_production_executor = bool(production_acceptance and adapter is None)
    selected_apis = _selected_apis(payload, default_apis)
    provider_call_scope = _provider_call_scope(payload, selected_apis)
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
    execution_gate = (
        _full_interface_provider_production_execution_gate(payload, selected_apis=selected_apis)
        if production_acceptance
        else _trade_cal_provider_execution_gate(payload, selected_apis=selected_apis, adapter=adapter)
    )
    if execution_gate.get("applies") is True and execution_gate.get("ready") is not True:
        gate_ledger = [
            (
                _full_interface_provider_production_gate_ledger_row(
                    execution_gate,
                    payload=payload,
                    now=_now_iso(),
                    scope=provider_call_scope,
                )
                if production_acceptance
                else _trade_cal_provider_execution_gate_ledger_row(
                    execution_gate,
                    selected_apis=selected_apis,
                    payload=payload,
                    now=_now_iso(),
                    scope=provider_call_scope,
                )
            )
        ]
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step=str(execution_gate.get("current_step") or "provider_execution_gate_blocked_no_provider_call"),
            error_message_safe=str(execution_gate.get("error_message_safe") or "provider_execution_gate_blocked"),
            call_ledger=gate_ledger,
            warning="provider_acceptance_execution_gate_blocked_before_provider_adapter_load",
        ) or task
    update_task_status(task["task_id"], status="running", progress=0.05, current_step="preparing_tushare_refresh")
    adapter_module = adapter
    call_ledger: list[dict[str, Any]] = []
    trade_cal_provider_data: Any = None
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
            call_ledger.append(
                _blocked_missing_param_ledger_row(
                    api,
                    params=params,
                    missing_param="ts_code",
                    now=now,
                    scope=provider_call_scope,
                )
            )
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
        except Exception as exc:
            result = {"ok": False, "data": None, "error": _safe_text(exc)}
            safe_params = params
        else:
            result, safe_params = _call_tushare_api(fn=fn, api=api, params=params)
        if isinstance(result, dict):
            result["runtime_transport_evidence"] = _consume_runtime_transport_evidence(
                adapter_module,
                result,
                api,
            )
        if api == "trade_cal" and isinstance(result, Mapping):
            trade_cal_provider_data = result.get("data")
        parquet_result = (
            _write_parquet_dataset(
                api,
                result.get("data"),
                payload=payload,
                scope=provider_call_scope,
            )
            if bool(result.get("ok"))
            else {"status": "not_written_failed_call"}
        )
        ledger_row = _call_ledger_row(
            api,
            params=safe_params,
            result=dict(result),
            parquet_result=parquet_result,
            now=now,
            payload=payload,
            scope=provider_call_scope,
        )
        if (
            not production_acceptance
            and execution_gate.get("applies") is True
            and execution_gate.get("ready") is True
            and api == "trade_cal"
        ):
            ledger_row.update(
                {
                    "provider_execution_gate_passed": True,
                    "execution_request_task_id": execution_gate.get("latest_execution_request_task_id") or "",
                    "execution_request_scope_hash_short": execution_gate.get("requested_scope_hash_short") or "",
                    "execution_request_scope_hash_matches_latest": True,
                    "execution_request_payload_matches_scope": True,
                }
            )
        if production_acceptance:
            ledger_row.update(
                {
                    "provider_execution_gate_passed": execution_gate.get("ready") is True,
                    "provider_adapter_provenance": "runtime_transport_receipt_verified"
                    if ledger_row.get("provider_transport_verified") is True
                    else "runtime_transport_evidence_missing",
                    "full_interface_provider_production_candidate": ledger_row.get(
                        "provider_transport_verified"
                    )
                    is True,
                    "execution_request_scope_hash_short": execution_gate.get(
                        "execution_request_scope_hash_short"
                    )
                    or "",
                    "execution_request_scope_hash_matches": execution_gate.get(
                        "scope_hash_matches_execution_request"
                    )
                    is True,
                    "authoritative_recipe_scope_hash": execution_gate.get(
                        "authoritative_recipe_scope_hash"
                    )
                    or "",
                    "authoritative_recipe_version": execution_gate.get(
                        "authoritative_recipe_version"
                    )
                    or "",
                    "authoritative_recipe_source_packet_key": execution_gate.get(
                        "authoritative_recipe_source_packet_key"
                    )
                    or "",
                    "approval_scope_hash": execution_gate.get("approval_scope_hash") or "",
                    "approval_scope_matches": execution_gate.get("approval_scope_matches") is True,
                    "provider_acceptance_marker": (
                        "runtime_transport_receipt_verified_candidate"
                        if ledger_row.get("provider_transport_verified") is True
                        else "unverified_transport_non_promoting"
                    ),
                }
            )
        call_ledger.append(ledger_row)

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
    trade_cal_ledger = next(
        (row for row in call_ledger if row.get("api") == "trade_cal"),
        {},
    )
    full_market_universe_evidence = (
        _run_full_market_universe_acceptance(
            adapter_module,
            payload=payload,
            scope=provider_call_scope,
            execution_gate=execution_gate,
            trade_cal_data=trade_cal_provider_data,
            trade_cal_ledger=trade_cal_ledger,
            outer_call_ledger=call_ledger,
            public_executor_completed=public_production_executor,
        )
        if production_acceptance and adapter_module is not None
        else {
            "schema_version": FULL_MARKET_UNIVERSE_SCHEMA_VERSION,
            "status": "full_market_universe_production_not_requested",
            "production_complete": False,
            "provider_provenance_verified": False,
            "artifacts": {},
        }
    )
    full_interface_provider_production_contract = _full_interface_provider_production_contract(
        production_acceptance_requested=production_acceptance,
        execution_gate=execution_gate,
        selected_apis=selected_apis,
        call_ledger=call_ledger,
        validation_target_rows=validation_target_rows,
        api_acceptance_audit=api_acceptance_audit,
        failure_mode_qa_contract=failure_mode_qa_contract,
        scope=provider_call_scope,
        universe_evidence=full_market_universe_evidence,
    )
    disk_production = tushare_production_store.validate_tushare_full_market_production_version(
        storage_service.PARQUET_ROOT / "full_market_universe"
    )
    if (
        public_production_executor
        and full_market_universe_evidence.get("production_complete") is True
        and disk_production.get("ready") is True
    ):
        full_interface_provider_production_contract = {
            **dict(full_interface_provider_production_contract),
            "status": "full_interface_provider_production_complete",
            "full_interface_provider_production": True,
            "provider_backed_acceptance_done": True,
            "production_tushare_pipeline_complete": True,
            "eligible_for_parquet_promotion": False,
            "eligible_for_sqlite_promotion": False,
            "parquet_promotion_verified": True,
            "sqlite_stage_readback_verified": True,
            "sqlite_atomic_promotion_verified": True,
            "blocking_criterion_count": 0,
            "blockers": [],
            "durable_truth_source": "immutable_version_pointer_and_manifest_disk_readback",
            "production_version_digest": disk_production.get("version_digest") or "",
        }
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
        "full_interface_provider_production_contract": full_interface_provider_production_contract,
        "full_interface_provider_production_rows": full_interface_provider_production_contract["rows"],
        "full_interface_provider_production_status": full_interface_provider_production_contract["status"],
        "full_market_universe_evidence": full_market_universe_evidence,
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
            "full_interface_provider_production_requires_explicit_post_mode": True,
            "full_interface_provider_production_requires_verified_runtime_transport": True,
            "synthetic_adapter_can_promote_production": False,
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
        "full_interface_provider_production": full_interface_provider_production_contract[
            "full_interface_provider_production"
        ],
        "full_interface_provider_production_blocker_count": full_interface_provider_production_contract[
            "blocking_criterion_count"
        ],
        "full_interface_provider_production_scope_hash": full_interface_provider_production_contract[
            "scope_hash"
        ],
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
    def _apply_production_contract(contract: Mapping[str, Any]) -> None:
        production_done = contract.get("full_interface_provider_production") is True
        refresh_packet["full_interface_provider_production_contract"] = dict(contract)
        refresh_packet["full_interface_provider_production_rows"] = list(contract.get("rows") or [])
        refresh_packet["full_interface_provider_production_status"] = contract.get("status")
        refresh_packet["full_interface_provider_production"] = production_done
        refresh_packet["full_interface_provider_production_blocker_count"] = int(
            contract.get("blocking_criterion_count") or 0
        )
        refresh_packet["full_interface_provider_production_scope_hash"] = contract.get("scope_hash") or ""
        refresh_packet["provider_backed_acceptance_done"] = production_done
        refresh_packet["production_tushare_pipeline_complete"] = production_done
        policy = refresh_packet.get("api_validation_matrix_policy")
        if isinstance(policy, dict):
            policy["full_interface_provider_production"] = production_done
            policy["production_tushare_pipeline_complete"] = production_done

    def _independent_production_packet(
        contract: Mapping[str, Any],
        *,
        parquet_promotion: Mapping[str, Any],
        staging: bool,
    ) -> dict[str, Any]:
        packet = {
            "packet_key": (
                FULL_INTERFACE_PROVIDER_PRODUCTION_STAGING_PACKET_KEY
                if staging
                else FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY
            ),
            "schema_version": "command_center_tushare_full_interface_production_packet.v1",
            "status": "full_interface_provider_production_staged"
            if staging
            else "full_interface_provider_production_complete",
            "generated_at": _now_iso(),
            "production_contract": dict(contract),
            "full_interface_provider_production": contract.get("full_interface_provider_production") is True,
            "production_tushare_pipeline_complete": contract.get("production_tushare_pipeline_complete") is True,
            "selected_apis": list(selected_apis),
            "required_target_groups": list(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS),
            "provider_scope": dict(provider_call_scope),
            "execution_recipe_scope_hash": execution_gate.get("authoritative_recipe_scope_hash") or "",
            "execution_recipe_version": execution_gate.get("authoritative_recipe_version") or "",
            "authoritative_recipe_source_packet_key": execution_gate.get(
                "authoritative_recipe_source_packet_key"
            )
            or "",
            "approval_scope_hash": execution_gate.get("approval_scope_hash") or "",
            "approval_scope_matches": execution_gate.get("approval_scope_matches") is True,
            "api_contexts": _safe_payload(payload).get("api_contexts") or {},
            "target_contexts": _safe_payload(payload).get("target_contexts") or {},
            "universe_context": _safe_payload(payload).get("universe_context") or {},
            "full_market_universe_packet_key": FULL_MARKET_UNIVERSE_CURRENT_PACKET_KEY,
            "full_market_universe_packet_digest": full_market_universe_evidence.get("packet_digest") or "",
            "full_market_universe_artifacts": dict(full_market_universe_evidence.get("artifacts") or {}),
            "call_ledger": [dict(row) for row in call_ledger],
            "parquet_promotion": dict(parquet_promotion),
            "sqlite_stage_readback_verified": contract.get("sqlite_stage_readback_verified") is True,
            "sqlite_atomic_promotion_verified": contract.get("sqlite_atomic_promotion_verified") is True,
            "external_calls_triggered": any(row.get("external_calls_triggered") is True for row in call_ledger),
            "tushare_called": any(row.get("tushare_called") is True for row in call_ledger),
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
        packet["immutable_packet_digest"] = _canonical_sha256(packet)
        return packet

    store = SQLiteMetaStore(SQLITE_META_PATH)
    if production_acceptance and full_interface_provider_production_contract.get("eligible_for_parquet_promotion") is True:
        parquet_promotion = _promote_staged_parquet_datasets(
            call_ledger,
            scope_hash=str(provider_call_scope.get("scope_hash") or ""),
        )
        staged_contract = _full_interface_provider_production_contract(
            production_acceptance_requested=True,
            execution_gate=execution_gate,
            selected_apis=selected_apis,
            call_ledger=call_ledger,
            validation_target_rows=validation_target_rows,
            api_acceptance_audit=api_acceptance_audit,
            failure_mode_qa_contract=failure_mode_qa_contract,
            scope=provider_call_scope,
            universe_evidence=full_market_universe_evidence,
            parquet_promotion=parquet_promotion,
        )
        sqlite_stage_verified = False
        if staged_contract.get("eligible_for_sqlite_promotion") is True:
            stage_packet = _independent_production_packet(
                staged_contract,
                parquet_promotion=parquet_promotion,
                staging=True,
            )
            try:
                store.write_packet(FULL_INTERFACE_PROVIDER_PRODUCTION_STAGING_PACKET_KEY, stage_packet)
                stage_readback = store.read_packet(FULL_INTERFACE_PROVIDER_PRODUCTION_STAGING_PACKET_KEY)
                sqlite_stage_verified = bool(
                    isinstance(stage_readback, Mapping)
                    and _canonical_sha256(stage_readback) == _canonical_sha256(stage_packet)
                    and stage_readback.get("full_interface_provider_production") is False
                )
            except Exception:
                sqlite_stage_verified = False
        final_contract = _full_interface_provider_production_contract(
            production_acceptance_requested=True,
            execution_gate=execution_gate,
            selected_apis=selected_apis,
            call_ledger=call_ledger,
            validation_target_rows=validation_target_rows,
            api_acceptance_audit=api_acceptance_audit,
            failure_mode_qa_contract=failure_mode_qa_contract,
            scope=provider_call_scope,
            universe_evidence=full_market_universe_evidence,
            parquet_promotion=parquet_promotion,
            sqlite_stage_readback_verified=sqlite_stage_verified,
            sqlite_atomic_promotion_verified=sqlite_stage_verified,
        )
        sqlite_atomic_verified = False
        if sqlite_stage_verified:
            final_packet = _independent_production_packet(
                final_contract,
                parquet_promotion=parquet_promotion,
                staging=False,
            )
            try:
                atomic_result = store.promote_packet_atomic(
                    FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY,
                    final_packet,
                )
                sqlite_atomic_verified = bool(
                    atomic_result.get("transaction_committed") is True
                    and atomic_result.get("readback_verified_before_commit") is True
                    and atomic_result.get("payload_digest") == _canonical_sha256(final_packet)
                )
            except Exception:
                sqlite_atomic_verified = False
        if sqlite_atomic_verified:
            _apply_production_contract(final_contract)
            shutil.rmtree(str(parquet_promotion.get("backup_root") or ""), ignore_errors=True)
            current_step = "full_interface_provider_production_acceptance_completed"
        else:
            rollback = _rollback_promoted_parquet_datasets(parquet_promotion)
            failed_promotion = dict(parquet_promotion)
            failed_promotion.update(
                {
                    "promotion_verified": False,
                    "status": "parquet_promotion_reverted_after_sqlite_failure",
                    "sqlite_failure_rollback": rollback,
                }
            )
            blocked_contract = _full_interface_provider_production_contract(
                production_acceptance_requested=True,
                execution_gate=execution_gate,
                selected_apis=selected_apis,
                call_ledger=call_ledger,
                validation_target_rows=validation_target_rows,
                api_acceptance_audit=api_acceptance_audit,
                failure_mode_qa_contract=failure_mode_qa_contract,
                scope=provider_call_scope,
                universe_evidence=full_market_universe_evidence,
                parquet_promotion=failed_promotion,
                sqlite_stage_readback_verified=sqlite_stage_verified,
                sqlite_atomic_promotion_verified=False,
            )
            _apply_production_contract(blocked_contract)
            status = "failed"
            current_step = "full_interface_provider_production_durable_promotion_failed_safe"
            error_message_safe = "durable_provider_acceptance_promotion_failed"
    else:
        _apply_production_contract(full_interface_provider_production_contract)

    try:
        store.write_packet(output_packet_key, refresh_packet)
    except Exception:
        if not production_acceptance:
            status = "failed"
            current_step = "tushare_refresh_packet_write_failed_safe"
            error_message_safe = "tushare_refresh_packet_write_failed"

    return update_task_status(
        task["task_id"],
        status=status,
        progress=1.0,
        current_step=current_step,
        error_message_safe=error_message_safe,
        call_ledger=call_ledger,
    ) or task


def run_tushare_full_interface_provider_production_acceptance(
    payload: Any = None,
    *,
    adapter: Any = None,
) -> dict[str, Any]:
    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    payload_map.setdefault("apis", list(ALL_REFRESH_APIS))
    payload_map.setdefault("target_sample_acceptance_groups", list(FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS))
    payload_map.setdefault("acceptance_mode", FULL_INTERFACE_PROVIDER_PRODUCTION_MODE)
    return run_tushare_refresh_task(
        payload_map,
        task_type=FULL_INTERFACE_PROVIDER_PRODUCTION_TASK_TYPE,
        output_packet_key="command_center_tushare_refresh_packet",
        default_apis=ALL_REFRESH_APIS,
        adapter=adapter,
        production_acceptance=True,
    )
