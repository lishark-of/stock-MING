from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from typing import Any

from config import (
    COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE,
    COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE,
    COMMAND_CENTER_DEFAULT_RUNTIME_MODE,
    COMMAND_CENTER_EXTERNAL_EXECUTION_PROFILES,
    COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPES,
    COMMAND_CENTER_RUNTIME_CONFIG_NAMES,
    COMMAND_CENTER_RUNTIME_MODES,
    CONFIG_NAMES,
    get_config_value,
    get_command_center_runtime_mode_config_contract,
    get_command_center_runtime_mode_state,
    get_command_center_runtime_mode_policies,
    get_deepseek_model,
)
from server.services import factor_service, next_session_service, task_service, tushare_task_service


PACKET_KEY = "command_center_3_bootstrap_runtime_mode_packet"
SCHEMA_VERSION = "command_center_bootstrap_runtime_mode.v1"
BOOTSTRAP_TASK_PACKET_KEY = "command_center_live_bootstrap_packet"
BOOTSTRAP_TASK_SCHEMA_VERSION = "command_center_live_bootstrap_task.v1"
BOOTSTRAP_TASK_TYPE = "command_center_live_bootstrap"
BOOTSTRAP_LATEST_TASK_STATUS_SCHEMA_VERSION = "command_center_live_light_latest_bootstrap_task_status.v1"
BOOTSTRAP_ACCEPTANCE_DRY_RUN_PACKET_KEY = "command_center_live_bootstrap_provider_model_acceptance_dry_run_packet"
BOOTSTRAP_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION = "command_center_live_bootstrap_provider_model_acceptance_dry_run.v1"
BOOTSTRAP_ACCEPTANCE_DRY_RUN_TASK_TYPE = "command_center_live_bootstrap_provider_model_acceptance_dry_run"
BOOTSTRAP_EXECUTION_REQUEST_PACKET_KEY = "command_center_live_bootstrap_provider_model_execution_request_packet"
BOOTSTRAP_EXECUTION_REQUEST_SCHEMA_VERSION = "command_center_live_bootstrap_provider_model_execution_request.v1"
BOOTSTRAP_EXECUTION_REQUEST_TASK_TYPE = "command_center_live_bootstrap_provider_model_execution_request"
SEARCH_SUBMIT_AUTOSTART_CONFIG_KEY = "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"
STARTUP_AUTOSTART_CONFIG_KEY = "COMMAND_CENTER_LIVE_STARTUP_AUTOSTART"
EXTERNAL_EXECUTION_PROFILE_CONFIG_KEY = "COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE"
LIVE_LIGHT_RESEARCH_SCOPE_CONFIG_KEY = "COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE"
PROVIDER_MODEL_ENABLEMENT_CONFIG_KEY = "COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT"
FRONTEND_ENABLEMENT_CONFIG_KEY = "COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT"
BOOTSTRAP_LOCAL_ENV_CONFIG_FALLBACK_KEYS: set[str] = set()
BOOTSTRAP_LATEST_ACCEPTANCE_DRY_RUN_STATUS_SCHEMA_VERSION = (
    "command_center_live_light_latest_acceptance_dry_run_status.v1"
)
BOOTSTRAP_LATEST_EXECUTION_REQUEST_STATUS_SCHEMA_VERSION = "command_center_live_light_latest_execution_request_status.v1"
BOOTSTRAP_MODES = COMMAND_CENTER_RUNTIME_MODES
DEFAULT_MODE = COMMAND_CENTER_DEFAULT_RUNTIME_MODE
EXTERNAL_EXECUTION_PROFILES = COMMAND_CENTER_EXTERNAL_EXECUTION_PROFILES
DEFAULT_EXTERNAL_EXECUTION_PROFILE = COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE
LIVE_LIGHT_RESEARCH_SCOPES = COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPES
DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE = COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE
BOOTSTRAP_STATUS_ROUTE = "GET /api/bootstrap/status"
PLANNED_BOOTSTRAP_TASK_ROUTE = "POST /api/bootstrap/live-startup"
PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE = "POST /api/bootstrap/provider-model-acceptance-dry-run"
PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE = "POST /api/bootstrap/provider-model-execution-request"
BOOTSTRAP_EXECUTION_REQUEST_ROUTE_IMPLEMENTED = True
BOOTSTRAP_EXECUTION_REQUEST_ROUTE_ADAPTER_STATUS = "registered_local_receipt_route"
FUTURE_BOOTSTRAP_PROVIDER_MODEL_ACCEPTANCE_ROUTE = "future POST /api/bootstrap/provider-model-acceptance"
SEARCH_QUANT_PROJECTION_ROUTE = "POST /api/candidate-radar/quant-projection"
SEARCH_QUANT_ACCEPTANCE_DRY_RUN_ROUTE = "POST /api/candidate-radar/quant-projection-acceptance-dry-run"
SEARCH_QUANT_EXECUTION_REQUEST_ROUTE = "POST /api/candidate-radar/quant-projection-execution-request"
SEARCH_QUANT_PROVIDER_MODEL_ROUTE = "POST /api/candidate-radar/quant-projection-provider-model-acceptance"
SEARCH_QUANT_PROJECTION_TASK_TYPE = "run_candidate_radar_quant_projection"
SEARCH_QUANT_PROVIDER_MODEL_TASK_TYPE = "run_candidate_radar_quant_projection_provider_model_acceptance"
SEARCH_QUANT_LATEST_STATUS_SCHEMA_VERSION = "command_center_search_quant_projection_latest_status.v1"
SEARCH_QUANT_PROVIDER_MODEL_LATEST_STATUS_SCHEMA_VERSION = (
    "command_center_search_quant_projection_provider_model_latest_status.v1"
)
SEARCH_QUANT_SUBMIT_AUTOSTART_SCHEMA_VERSION = "command_center_search_quant_projection_submit_autostart_contract.v1"
SEARCH_QUANT_SUBMIT_AUTOSTART_CONFIG_HANDOFF_SCHEMA_VERSION = (
    "command_center_search_quant_projection_submit_autostart_config_handoff.v1"
)
SEARCH_QUANT_SUBMIT_AUTOSTART_CONFIG_PROMOTION_SCHEMA_VERSION = (
    "command_center_search_quant_projection_submit_autostart_config_promotion.v1"
)
BOOTSTRAP_RUNTIME_CONFIG_REFERENCE_SCHEMA_VERSION = "command_center_bootstrap_runtime_config_reference.v1"
SEARCH_QUANT_FRONTEND_WIRING_SCHEMA_VERSION = (
    "command_center_search_quant_projection_frontend_wiring_acceptance_contract.v1"
)
SEARCH_QUANT_UNIFIED_STARTUP_HANDOFF_SCHEMA_VERSION = (
    "command_center_search_quant_projection_unified_startup_handoff_contract.v1"
)
DEFAULT_LIGHT_TUSHARE_APIS = ("trade_cal_if_needed", "daily", "daily_basic", "moneyflow")
ACCEPTANCE_DRY_RUN_ALLOWED_APIS = ("trade_cal", "daily", "daily_basic", "moneyflow")
TUSHARE_ACCEPTANCE_ENV_KEYS = ("TUSHARE_TOKEN",)
DEEPSEEK_ACCEPTANCE_ENV_KEYS = ("DEEPSEEK_API_KEY", "DEEPSEEK_TOKEN_1", "DEEPSEEK_TOKEN_2")
DESKTOP_LIVE_STARTUP_EXECUTION_ENV_KEY = "STOCK_MING_DESKTOP_LIVE_STARTUP_EXECUTION"
DESKTOP_LIVE_LIGHT_DEFAULT_SYMBOLS = ("002008.SZ", "000001.SZ")
BOOTSTRAP_STAGE_SCHEMA_VERSION = "command_center_live_bootstrap_stage_plan.v1"
BOOTSTRAP_MODEL_LEDGER_SCHEMA_VERSION = "command_center_live_bootstrap_model_ledger_preview.v1"
BOOTSTRAP_LOCAL_COMPUTE_HANDOFF_SCHEMA_VERSION = "command_center_live_bootstrap_local_compute_handoff.v1"
BOOTSTRAP_PROVIDER_LINKAGE_SCHEMA_VERSION = "command_center_bootstrap_provider_linkage.v1"
BOOTSTRAP_MODE_TRIGGER_MATRIX_SCHEMA_VERSION = "command_center_bootstrap_mode_trigger_matrix.v1"
BOOTSTRAP_RUNTIME_MODE_ACCEPTANCE_SCHEMA_VERSION = "command_center_bootstrap_runtime_mode_acceptance.v1"
BOOTSTRAP_LIVE_LIGHT_ROLLOUT_ROADMAP_SCHEMA_VERSION = "command_center_live_light_rollout_roadmap.v1"
BOOTSTRAP_TASK_CREATION_INVARIANT_SCHEMA_VERSION = "command_center_bootstrap_task_creation_invariant.v1"
BOOTSTRAP_EXTERNAL_SILENCE_SCHEMA_VERSION = "command_center_runtime_external_silence_contract.v1"
BOOTSTRAP_HARD_BOUNDARY_SCHEMA_VERSION = "command_center_runtime_hard_boundary_contract.v1"
BOOTSTRAP_RUNTIME_CONFIG_OWNERSHIP_SCHEMA_VERSION = (
    "command_center_bootstrap_runtime_config_ownership_invariant.v1"
)
BOOTSTRAP_EVIDENCE_GRADE_SCHEMA_VERSION = "command_center_live_light_evidence_grade_contract.v1"
BOOTSTRAP_LEDGER_CONTRACT_SCHEMA_VERSION = "command_center_live_light_ledger_contract.v1"
BOOTSTRAP_LEDGER_REDACTION_INVARIANT_SCHEMA_VERSION = (
    "command_center_live_light_ledger_redaction_invariant.v1"
)
BOOTSTRAP_CREDENTIAL_PREFLIGHT_SCHEMA_VERSION = "command_center_live_light_credential_preflight_contract.v1"
BOOTSTRAP_EXECUTION_REQUEST_CONTRACT_SCHEMA_VERSION = "command_center_live_light_provider_model_execution_request_contract.v1"
BOOTSTRAP_EXECUTION_REQUEST_HANDOFF_CONTRACT_SCHEMA_VERSION = "command_center_live_light_execution_request_handoff_contract.v1"
BOOTSTRAP_LOCAL_FALLBACK_CONTRACT_SCHEMA_VERSION = "command_center_live_light_local_fallback_contract.v1"
BOOTSTRAP_CACHE_LINEAGE_CONTRACT_SCHEMA_VERSION = "command_center_live_light_cache_lineage_contract.v1"
BOOTSTRAP_OUTPUT_SURFACE_CONTRACT_SCHEMA_VERSION = "command_center_live_light_output_surface_contract.v1"
BOOTSTRAP_RUNTIME_BUDGET_CONTRACT_SCHEMA_VERSION = "command_center_live_light_runtime_budget_contract.v1"
BOOTSTRAP_TASK_LIFECYCLE_CONTRACT_SCHEMA_VERSION = "command_center_live_light_task_lifecycle_contract.v1"
BOOTSTRAP_TASK_QUEUE_BUDGET_CONTRACT_SCHEMA_VERSION = "command_center_live_light_task_queue_budget_contract.v1"
BOOTSTRAP_STARTUP_AUTOSTART_READINESS_SCHEMA_VERSION = (
    "command_center_live_light_startup_autostart_readiness_contract.v1"
)
BOOTSTRAP_SCOPE_INTAKE_CONTRACT_SCHEMA_VERSION = "command_center_live_light_scope_intake_contract.v1"
BOOTSTRAP_STAGE_DEPENDENCY_CONTRACT_SCHEMA_VERSION = "command_center_live_light_stage_dependency_contract.v1"
BOOTSTRAP_FRESHNESS_PROVIDER_GAP_CONTRACT_SCHEMA_VERSION = "command_center_live_light_freshness_provider_gap_contract.v1"
BOOTSTRAP_TASK_CONTROL_CONTRACT_SCHEMA_VERSION = "command_center_live_light_task_control_contract.v1"
BOOTSTRAP_OPERATOR_STATUS_CONTRACT_SCHEMA_VERSION = "command_center_live_light_operator_status_contract.v1"
BOOTSTRAP_OPERATOR_SUMMARY_SCHEMA_VERSION = "command_center_runtime_operator_summary_contract.v1"
BOOTSTRAP_CACHE_FIRST_POLLING_SCHEMA_VERSION = "command_center_runtime_cache_first_polling_contract.v1"
BOOTSTRAP_FRONTEND_ENABLEMENT_GATE_SCHEMA_VERSION = "command_center_live_light_frontend_enablement_gate.v1"
BOOTSTRAP_BROWSER_EVIDENCE_SCHEMA_VERSION = "command_center_live_light_browser_evidence_contract.v1"
BOOTSTRAP_FRONTEND_WIRING_MANIFEST_SCHEMA_VERSION = "command_center_live_light_frontend_wiring_manifest.v1"
BOOTSTRAP_FRONTEND_ACCEPTANCE_RUNBOOK_SCHEMA_VERSION = "command_center_live_light_frontend_acceptance_runbook.v1"
BOOTSTRAP_FRONTEND_ACCEPTANCE_ARTIFACT_SCHEMA_VERSION = (
    "command_center_live_light_frontend_acceptance_artifact_contract.v1"
)
BOOTSTRAP_FRONTEND_ENABLEMENT_PROMOTION_SCHEMA_VERSION = (
    "command_center_live_light_frontend_enablement_promotion_contract.v1"
)
BOOTSTRAP_FRONTEND_ENABLEMENT_RELEASE_SWITCH_SCHEMA_VERSION = (
    "command_center_live_light_frontend_enablement_release_switch_contract.v1"
)
BOOTSTRAP_FRONTEND_ENABLEMENT_CONFIG_PROMOTION_SCHEMA_VERSION = (
    "command_center_live_light_frontend_enablement_config_promotion_contract.v1"
)
BOOTSTRAP_PROMOTION_GATE_CONTRACT_SCHEMA_VERSION = "command_center_live_light_promotion_gate_contract.v1"
BOOTSTRAP_WORKER_DISPATCH_CONTRACT_SCHEMA_VERSION = "command_center_live_light_worker_dispatch_contract.v1"
BOOTSTRAP_UNIFIED_STARTUP_TASK_CONTRACT_SCHEMA_VERSION = (
    "command_center_live_light_unified_startup_task_contract.v1"
)
SEARCH_QUANT_RESULT_SURFACE_CONTRACT_SCHEMA_VERSION = "command_center_search_quant_projection_result_surface_contract.v1"
SEARCH_QUANT_FACTOR_NEXT_HANDOFF_CONTRACT_SCHEMA_VERSION = (
    "command_center_search_quant_projection_factor_next_handoff_contract.v1"
)
SEARCH_QUANT_CACHE_WRITE_PREFLIGHT_CONTRACT_SCHEMA_VERSION = (
    "command_center_search_quant_projection_cache_write_preflight_contract.v1"
)
SEARCH_QUANT_DEEPSEEK_MODEL_PREFLIGHT_CONTRACT_SCHEMA_VERSION = (
    "command_center_search_quant_projection_deepseek_model_preflight_contract.v1"
)
SEARCH_QUANT_DEEPSEEK_OUTPUT_ACCEPTANCE_CONTRACT_SCHEMA_VERSION = (
    "command_center_search_quant_projection_deepseek_output_acceptance_contract.v1"
)
SEARCH_QUANT_DEEPSEEK_READINESS_CONTRACT_SCHEMA_VERSION = (
    "command_center_search_quant_projection_deepseek_readiness_contract.v1"
)
BOOTSTRAP_ACTIVATION_RECEIPT_SCHEMA_VERSION = "command_center_live_bootstrap_activation_receipt.v1"
BOOTSTRAP_ACCEPTANCE_RUNBOOK_SCHEMA_VERSION = "command_center_live_bootstrap_provider_model_acceptance_runbook.v1"
BOOTSTRAP_REAL_ACCEPTANCE_PREFLIGHT_SCHEMA_VERSION = "command_center_live_bootstrap_real_acceptance_preflight_receipt.v1"
DEEPSEEK_EXPLANATION_FIELDS = (
    "summary",
    "support_notes",
    "suppress_notes",
    "conflict_notes",
    "missing_data_notes",
    "discipline_notes",
)


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "bootstrap_runtime_mode_packet_not_json_serializable"}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _config_value(name: str, default: Any = None) -> Any:
    value = get_config_value(name)
    if value is None and name in BOOTSTRAP_LOCAL_ENV_CONFIG_FALLBACK_KEYS:
        value = os.environ.get(name)
    return default if value is None else value


def _bool_config(name: str, default: bool = False) -> tuple[bool, str]:
    raw = _config_value(name)
    if raw is None:
        return bool(default), "default"
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on", "enabled"}:
        return True, "configured"
    if value in {"0", "false", "no", "off", "disabled"}:
        return False, "configured"
    return bool(default), "invalid_defaulted"


def _int_config(name: str, default: int, *, minimum: int, maximum: int) -> tuple[int, str]:
    raw = _config_value(name)
    if raw is None:
        return default, "default"
    try:
        parsed = int(str(raw).strip())
    except ValueError:
        return default, "invalid_defaulted"
    if parsed < minimum:
        return minimum, "clamped_min"
    if parsed > maximum:
        return maximum, "clamped_max"
    return parsed, "configured"


def _enum_config(
    name: str,
    default: str,
    allowed_values: tuple[str, ...],
) -> tuple[str, str, str, bool, bool]:
    raw = _config_value(name)
    if raw is None:
        return default, "default", "", True, False
    raw_text = str(raw).strip()
    safe_text = _safe_text(raw_text, limit=80)
    if safe_text == "[redacted_sensitive_text]":
        return default, "invalid_defaulted", safe_text, False, True
    normalized = raw_text.lower()
    if normalized in allowed_values:
        return normalized, "configured", normalized, True, False
    return default, "invalid_defaulted", safe_text, False, False


def _config_row_display_controls() -> dict[str, Any]:
    return {
        "config_source_of_truth": "server_config_layer",
        "frontend_visible": True,
        "frontend_display_policy": "safe_value_only",
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "operator_change_channel": "server_config_layer_only",
    }


def _safe_text(value: Any, *, limit: int = 160) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in ("api_key", "apikey", "token", "secret", "password", "authorization", "bearer")):
        return "[redacted_sensitive_text]"
    if lower.startswith("sk-") or any(lower.startswith(prefix) for prefix in ("ghp_", "gho_", "ghu_", "ghs_", "ghr_")):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "on", "enabled"}:
        return True
    if lowered in {"0", "false", "no", "off", "disabled"}:
        return False
    return bool(default)


def _safe_symbol(value: Any) -> str:
    text = _safe_text(value, limit=32).upper()
    return "".join(ch for ch in text if ch.isalnum() or ch in {".", "_", "-"})


def _safe_symbol_list(value: Any, *, limit: int) -> list[str]:
    if isinstance(value, str):
        raw_items = value.replace(";", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = []

    seen: set[str] = set()
    symbols: list[str] = []
    for item in raw_items:
        symbol = _safe_symbol(item)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
        if len(symbols) >= limit:
            break
    return symbols


def _safe_api_name(value: Any) -> str:
    text = _safe_text(value, limit=48).lower()
    return "".join(ch for ch in text if ch.isalnum() or ch == "_")


def _safe_api_list(value: Any, *, limit: int) -> list[str]:
    if isinstance(value, str):
        raw_items = value.replace(";", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = []

    seen: set[str] = set()
    apis: list[str] = []
    for item in raw_items:
        api = _safe_api_name(item)
        if not api or api in seen:
            continue
        seen.add(api)
        apis.append(api)
        if len(apis) >= limit:
            break
    return apis


def _sanitize_live_startup_payload(payload: Any, *, symbol_limit: int) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    symbols: list[str] = []

    def append_symbol(symbol: str) -> bool:
        if not symbol or symbol in symbols:
            return False
        if len(symbols) >= symbol_limit:
            return True
        symbols.append(symbol)
        return False

    truncated_by_symbol_limit = False
    for key in ("ts_code", "symbol", "current_target"):
        symbol = _safe_symbol(raw.get(key))
        truncated_by_symbol_limit = append_symbol(symbol) or truncated_by_symbol_limit
    for key in ("symbols", "watchlist", "holdings"):
        for symbol in _safe_symbol_list(raw.get(key), limit=symbol_limit + 1):
            truncated_by_symbol_limit = append_symbol(symbol) or truncated_by_symbol_limit

    requested_modes = _safe_symbol_list(raw.get("modes"), limit=8)
    requested_apis = _safe_symbol_list(raw.get("apis"), limit=16)
    return {
        "source": _safe_text(raw.get("source") or "command_center_3", limit=80),
        "requested_by": _safe_text(raw.get("requested_by") or "local_user", limit=80),
        "symbols": symbols[:symbol_limit],
        "symbol_count": min(len(symbols), symbol_limit),
        "symbol_limit": symbol_limit,
        "truncated_by_symbol_limit": truncated_by_symbol_limit,
        "requested_modes": requested_modes,
        "requested_apis": requested_apis,
        "payload_tushare_requested": _safe_bool(raw.get("tushare"), False),
        "payload_deepseek_requested": _safe_bool(raw.get("deepseek"), False),
        "contains_secret": False,
    }


def _sanitize_acceptance_dry_run_payload(payload: Any, *, symbol_limit: int) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    requested_apis = _safe_api_list(raw.get("apis"), limit=16)
    ignored_apis = [api for api in requested_apis if api not in ACCEPTANCE_DRY_RUN_ALLOWED_APIS]
    selected_apis = [api for api in requested_apis if api in ACCEPTANCE_DRY_RUN_ALLOWED_APIS]
    include_tushare = _safe_bool(raw.get("include_tushare", raw.get("tushare")), bool(selected_apis))
    if include_tushare and not selected_apis:
        selected_apis = list(ACCEPTANCE_DRY_RUN_ALLOWED_APIS)
    include_deepseek = _safe_bool(raw.get("include_deepseek", raw.get("deepseek")), False)
    user_approved = _safe_bool(
        raw.get("approved_by_user", raw.get("user_approval", raw.get("approved"))),
        False,
    )
    symbols = _safe_symbol_list(
        raw.get("symbols") or raw.get("watchlist") or raw.get("holdings") or raw.get("ts_code") or raw.get("symbol"),
        limit=symbol_limit + 1,
    )
    return {
        "schema_version": BOOTSTRAP_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
        "source": _safe_text(raw.get("source") or "command_center_3", limit=80),
        "requested_by": _safe_text(raw.get("requested_by") or "local_user", limit=80),
        "user_approved": user_approved,
        "approval_mode": "explicit_payload_true" if user_approved else "missing_or_false",
        "symbols": symbols[:symbol_limit],
        "symbol_count": min(len(symbols), symbol_limit),
        "symbol_limit": symbol_limit,
        "truncated_by_symbol_limit": len(symbols) > symbol_limit,
        "include_tushare": include_tushare,
        "include_deepseek": include_deepseek,
        "selected_apis": selected_apis,
        "ignored_apis": ignored_apis,
        "allowed_apis": list(ACCEPTANCE_DRY_RUN_ALLOWED_APIS),
        "contains_secret": False,
    }


def _sanitize_execution_request_payload(payload: Any) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    requested_scope_hash = _safe_text(
        raw.get("acceptance_scope_hash") or raw.get("requested_acceptance_scope_hash") or "",
        limit=80,
    )
    requested_apis = _safe_api_list(raw.get("apis") or raw.get("selected_apis"), limit=16)
    user_confirmed = _safe_bool(
        raw.get("confirmed_by_user", raw.get("operator_approved", raw.get("approved_by_user"))),
        False,
    )
    return {
        "schema_version": BOOTSTRAP_EXECUTION_REQUEST_SCHEMA_VERSION,
        "source": _safe_text(raw.get("source") or "command_center_3", limit=80),
        "requested_by": _safe_text(raw.get("requested_by") or "local_user", limit=80),
        "user_confirmed": user_confirmed,
        "confirmation_mode": "explicit_payload_true" if user_confirmed else "missing_or_false",
        "requested_acceptance_scope_hash": requested_scope_hash,
        "requested_acceptance_scope_hash_short": requested_scope_hash[:16] if requested_scope_hash else "",
        "selected_apis": [api for api in requested_apis if api in ACCEPTANCE_DRY_RUN_ALLOWED_APIS],
        "ignored_apis": [api for api in requested_apis if api not in ACCEPTANCE_DRY_RUN_ALLOWED_APIS],
        "include_tushare": _safe_bool(raw.get("include_tushare", raw.get("tushare")), bool(requested_apis)),
        "include_deepseek": _safe_bool(raw.get("include_deepseek", raw.get("deepseek")), False),
        "contains_secret": False,
    }


def _env_key_presence_rows(payload_safe: dict[str, Any]) -> list[dict[str, Any]]:
    specs = [
        {
            "provider": "tushare",
            "required": payload_safe.get("include_tushare") is True,
            "env_keys": list(TUSHARE_ACCEPTANCE_ENV_KEYS),
            "credential_refs": ["tushare_primary_credential"],
        },
        {
            "provider": "deepseek",
            "required": payload_safe.get("include_deepseek") is True,
            "env_keys": list(DEEPSEEK_ACCEPTANCE_ENV_KEYS),
            "credential_refs": [
                "deepseek_primary_credential",
                "deepseek_secondary_credential_1",
                "deepseek_secondary_credential_2",
            ],
        },
    ]
    rows: list[dict[str, Any]] = []
    for spec in specs:
        required = bool(spec["required"])
        env_keys = list(spec["env_keys"])
        present_keys = [key for key in env_keys if key in os.environ]
        present = bool(present_keys)
        if required and present:
            status = "present_no_value_read"
        elif required:
            status = "missing_no_value_read"
        else:
            status = "not_required_not_selected"
        rows.append(
            {
                "schema_version": BOOTSTRAP_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
                "provider": spec["provider"],
                "required_for_selected_dry_run": required,
                "credential_refs": list(spec["credential_refs"]),
                "credential_ref_count": len(spec["credential_refs"]),
                "present": present,
                "present_key_count": len(present_keys),
                "status": status,
                "presence_check_method": "environment_key_membership_only",
                "values_read": False,
                "values_exposed": False,
                "value_lengths_exposed": False,
                "streamlit_config_values_read": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    return rows


def _env_key_presence_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    required_rows = [row for row in rows if row.get("required_for_selected_dry_run") is True]
    present_rows = [row for row in required_rows if row.get("present") is True]
    missing_rows = [row for row in required_rows if row.get("present") is not True]
    return {
        "schema_version": BOOTSTRAP_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
        "status": "all_required_env_keys_present_no_values_read" if not missing_rows else "required_env_key_missing_no_values_read",
        "required_provider_count": len(required_rows),
        "present_provider_count": len(present_rows),
        "missing_provider_count": len(missing_rows),
        "presence_check_method": "environment_key_membership_only",
        "values_read": False,
        "values_exposed": False,
        "value_lengths_exposed": False,
        "streamlit_config_values_read": False,
        "contains_secret": False,
    }


def _acceptance_scope_ticket(*, payload_safe: dict[str, Any], status_packet: dict[str, Any]) -> dict[str, Any]:
    runbook = _dict(status_packet.get("live_light_provider_model_acceptance_runbook"))
    scope_input = {
        "mode": status_packet.get("mode"),
        "route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
        "symbols": list(payload_safe.get("symbols") or []),
        "selected_apis": list(payload_safe.get("selected_apis") or []),
        "ignored_apis": list(payload_safe.get("ignored_apis") or []),
        "include_tushare": payload_safe.get("include_tushare") is True,
        "include_deepseek": payload_safe.get("include_deepseek") is True,
        "deepseek_model": runbook.get("deepseek_model"),
        "symbol_limit": payload_safe.get("symbol_limit"),
        "user_approved": payload_safe.get("user_approved") is True,
        "credential_presence_status": _dict(payload_safe.get("credential_presence_summary")).get("status"),
    }
    serialized = json.dumps(scope_input, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "schema_version": BOOTSTRAP_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
        "scope_hash_algorithm": "sha256",
        "scope_hash": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "scope_hash_short": hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16],
        "scope_hash_input": scope_input,
        "scope_hash_input_field_count": len(scope_input),
        "credential_values_included": False,
        "env_key_names_included": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _parse_iso(value: Any) -> _dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def _recent_live_bootstrap_task(
    mode: str,
    *,
    rate_limit_seconds: int,
    require_desktop_live_execution: bool = False,
) -> tuple[dict[str, Any] | None, int | None]:
    now = _dt.datetime.now()
    for task in task_service.list_task_statuses():
        if str(task.get("task_type") or "") != BOOTSTRAP_TASK_TYPE:
            continue
        payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
        if str(payload_safe.get("bootstrap_mode") or "") != mode:
            continue
        if require_desktop_live_execution and not (
            payload_safe.get("desktop_live_execution_enabled") is True or task.get("tushare_called") is True
        ):
            continue
        timestamp = _parse_iso(task.get("finished_at") or task.get("started_at") or task.get("created_at"))
        if timestamp is None:
            continue
        age_seconds = max(0, int((now - timestamp).total_seconds()))
        if age_seconds <= int(rate_limit_seconds):
            return task, age_seconds
    return None, None


def _desktop_live_startup_execution_enabled() -> bool:
    return str(os.environ.get(DESKTOP_LIVE_STARTUP_EXECUTION_ENV_KEY) or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }


def _live_light_default_date_window() -> dict[str, str]:
    end_date = _dt.date.today()
    start_date = end_date - _dt.timedelta(days=18)
    return {
        "start_date": start_date.strftime("%Y%m%d"),
        "end_date": end_date.strftime("%Y%m%d"),
    }


def _live_light_execution_symbols(payload_safe: dict[str, Any], *, max_symbols: int = 2) -> list[str]:
    symbols = _safe_symbol_list(payload_safe.get("symbols"), limit=max_symbols + 1)
    if not symbols:
        symbols = list(DESKTOP_LIVE_LIGHT_DEFAULT_SYMBOLS)
    deduped: list[str] = []
    for symbol in symbols:
        normalized = _safe_symbol(symbol)
        if normalized and normalized not in deduped:
            deduped.append(normalized)
        if len(deduped) >= max_symbols:
            break
    return deduped


def _extend_task_ledger(target: list[dict[str, Any]], task: dict[str, Any] | None, *, scope: str) -> None:
    if not isinstance(task, dict):
        return
    for row in task.get("call_ledger") or []:
        if isinstance(row, dict):
            target.append({"scope": scope, **row})


def _execute_live_light_tushare_and_local_pipeline(
    *,
    task_id: str,
    payload_safe: dict[str, Any],
    status_packet: dict[str, Any],
    plan: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    del status_packet, plan
    ledgers: list[dict[str, Any]] = []
    symbols = _live_light_execution_symbols(payload_safe)
    date_window = _live_light_default_date_window()
    provider_task_ids: list[str] = []
    factor_task_id = ""
    next_task_id = ""

    task_service.update_task_status(
        task_id,
        status="running",
        progress=0.22,
        current_step="live_bootstrap_calling_tushare_light_refresh",
        call_ledger=ledgers,
    )
    for symbol in symbols:
        tushare_payload = {
            "source": "command_center_live_bootstrap",
            "ts_code": symbol,
            "apis": ["trade_cal", "daily", "daily_basic", "moneyflow"],
            **date_window,
            "desktop_live_light_startup": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
        provider_task = tushare_task_service.run_tushare_refresh_task(
            tushare_payload,
            task_type="refresh_tushare_facts",
            output_packet_key="command_center_tushare_refresh_packet",
            default_apis=("trade_cal", "daily", "daily_basic", "moneyflow"),
        )
        provider_task_ids.append(str(provider_task.get("task_id") or ""))
        _extend_task_ledger(ledgers, provider_task, scope="tushare_light")

    task_service.update_task_status(
        task_id,
        status="running",
        progress=0.58,
        current_step="live_bootstrap_running_factor_light_local_cache",
        call_ledger=ledgers,
    )
    factor_task = factor_service.run_factor_light_task(
        {
            "source": "command_center_live_bootstrap",
            "symbols": symbols,
            "universe_mode": "watchlist",
            "desktop_live_light_startup": True,
        }
    )
    factor_task_id = str(factor_task.get("task_id") or "")
    _extend_task_ledger(ledgers, factor_task, scope="factor_light")

    task_service.update_task_status(
        task_id,
        status="running",
        progress=0.78,
        current_step="live_bootstrap_refreshing_next_session_cache",
        call_ledger=ledgers,
    )
    next_task = next_session_service.create_next_session_task(
        {
            "source": "command_center_live_bootstrap",
            "symbols": symbols,
            "desktop_live_light_startup": True,
        }
    )
    next_task_id = str(next_task.get("task_id") or "")
    _extend_task_ledger(ledgers, next_task, scope="next_session")

    provider_called = any(row.get("tushare_called") is True for row in ledgers)
    provider_success = any(row.get("call_status") in {"success", "empty"} for row in ledgers if row.get("scope") == "tushare_light")
    local_success = (
        str(factor_task.get("status") or "") == "success"
        and str(next_task.get("status") or "") == "success"
    )
    if provider_success and local_success:
        current_step = "live_bootstrap_completed_with_tushare_light_and_local_cache"
    elif provider_called:
        current_step = "live_bootstrap_completed_provider_degraded_local_cache_fallback"
    else:
        current_step = "live_bootstrap_completed_local_cache_fallback_provider_unavailable"

    summary = {
        "desktop_live_execution_enabled": True,
        "symbols": symbols,
        "symbol_count": len(symbols),
        "start_date": date_window["start_date"],
        "end_date": date_window["end_date"],
        "provider_task_ids": [item for item in provider_task_ids if item],
        "factor_task_id": factor_task_id,
        "next_task_id": next_task_id,
        "provider_called": provider_called,
        "provider_success": provider_success,
        "local_success": local_success,
        "deepseek_requested_but_requires_explicit_data_export_approval": payload_safe.get("deepseek_on_open") is True,
        "model_execution_implemented": False,
        "deepseek_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    return current_step, ledgers, summary


def _latest_live_bootstrap_task_status_surface() -> dict[str, Any]:
    latest_task = next(
        (
            task
            for task in task_service.list_task_statuses()
            if task.get("task_type") == BOOTSTRAP_TASK_TYPE
        ),
        None,
    )
    if latest_task is None:
        return {
            "schema_version": BOOTSTRAP_LATEST_TASK_STATUS_SCHEMA_VERSION,
            "status": "no_bootstrap_task_found",
            "lookup_source": "task_service.list_task_statuses",
            "lookup_creates_task": False,
            "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "route_implemented": True,
            "task_found": False,
            "task_id": "",
            "task_status": "",
            "current_step": "",
            "output_packet_key": "",
            "storage_source": "",
            "durable_task_visible": False,
            "memory_only_task_is_durable_evidence": False,
            "bootstrap_mode": "",
            "source": "",
            "symbol_count": 0,
            "symbol_limit": 0,
            "truncated_by_symbol_limit": False,
            "sources_enabled": False,
            "tushare_on_open": False,
            "deepseek_on_open": False,
            "external_execution_profile": DEFAULT_EXTERNAL_EXECUTION_PROFILE,
            "external_execution_profile_provider_stage_allowed": False,
            "external_execution_profile_model_stage_allowed": False,
            "external_execution_profile_executor_implemented": False,
            "bootstrap_stage_count": 0,
            "model_ledger_preview_count": 0,
            "local_compute_handoff_visible": False,
            "local_compute_handoff_schema_version": "",
            "local_compute_handoff_status": "no_bootstrap_task_found",
            "local_compute_handoff_mode_gate": "live_light",
            "local_compute_handoff_mode_gate_satisfied": False,
            "local_compute_handoff_source_switch_satisfied": False,
            "local_compute_handoff_inactive_reason": "",
            "local_compute_handoff_row_count": 0,
            "local_compute_handoff_enabled_row_count": 0,
            "local_compute_handoff_executed_row_count": 0,
            "local_compute_handoff_output_written_row_count": 0,
            "local_compute_handoff_future_local_routes": [],
            "local_compute_handoff_future_task_types": [],
            "local_compute_handoff_output_packet_keys": [],
            "local_compute_handoff_input_packet_keys": [],
            "local_compute_handoff_lineage_contract_schema_version": "",
            "local_compute_handoff_lineage_write_policy": "",
            "local_compute_handoff_lineage_required_field_count": 0,
            "local_compute_handoff_lineage_written_row_count": 0,
            "local_compute_handoff_cache_get_may_write_lineage": False,
            "local_compute_handoff_react_render_may_write_lineage": False,
            "local_compute_handoff_fastapi_startup_may_write_lineage": False,
            "local_compute_handoff_lineage_is_execution_evidence": False,
            "local_compute_handoff_lineage_is_production_evidence": False,
            "local_compute_handoff_replay_executes_local_compute": False,
            "local_compute_handoff_replay_writes_output": False,
            "local_compute_handoff_replay_is_execution_evidence": False,
            "local_compute_handoff_replay_is_production_evidence": False,
            "planned_provider_stage_count": 0,
            "planned_model_stage_count": 0,
            "actual_provider_execution_count": 0,
            "actual_model_call_count": 0,
            "rate_limit_reused_existing_task": False,
            "call_ledger_count": 0,
            "task_success_is_provider_model_evidence": False,
            "task_success_is_production_evidence": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "provider_model_execution_implemented": False,
            "production_live_light_complete": False,
            "is_production_evidence": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "contains_secret": False,
            "credential_values_exposed": False,
            "env_key_names_included": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_prices_positions_or_operation_zones": True,
        }

    payload = _dict(latest_task.get("payload_safe"))
    summary = _dict(payload.get("bootstrap_plan_summary"))
    local_compute_handoff = _dict(payload.get("bootstrap_local_compute_handoff_summary"))
    local_compute_handoff_visible = (
        local_compute_handoff.get("schema_version") == BOOTSTRAP_LOCAL_COMPUTE_HANDOFF_SCHEMA_VERSION
    )
    storage_source = str(latest_task.get("storage_source") or "")
    durable_task_visible = storage_source in {"memory_and_sqlite", "sqlite_meta"}
    current_step = str(latest_task.get("current_step") or "")
    if current_step == "live_bootstrap_plan_recorded_no_provider_execution":
        status = "latest_bootstrap_task_visible_plan_recorded"
    elif current_step == "live_bootstrap_skipped_due_to_rate_limit":
        status = "latest_bootstrap_task_visible_rate_limited_reuse"
    elif current_step.startswith("live_bootstrap_skipped_"):
        status = "latest_bootstrap_task_visible_safe_skip"
    elif current_step.startswith("live_bootstrap_completed_"):
        status = "latest_bootstrap_task_visible_live_light_execution"
    elif current_step.startswith("live_bootstrap_") and "tushare" in current_step:
        status = "latest_bootstrap_task_visible_live_light_execution"
    else:
        status = "latest_bootstrap_task_visible_unknown_step"
    call_ledger = list(latest_task.get("call_ledger") or [])
    provider_execution_observed = any(row.get("tushare_called") is True for row in call_ledger)
    model_execution_observed = any(row.get("deepseek_called") is True for row in call_ledger)
    actual_provider_execution_count = sum(1 for row in call_ledger if row.get("tushare_called") is True)
    actual_model_call_count = sum(1 for row in call_ledger if row.get("deepseek_called") is True)
    return {
        "schema_version": BOOTSTRAP_LATEST_TASK_STATUS_SCHEMA_VERSION,
        "status": status,
        "lookup_source": "task_service.list_task_statuses",
        "lookup_creates_task": False,
        "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "route_implemented": True,
        "task_found": True,
        "task_id": latest_task.get("task_id"),
        "task_status": latest_task.get("status"),
        "current_step": current_step,
        "output_packet_key": latest_task.get("output_packet_key"),
        "storage_source": storage_source,
        "durable_task_visible": durable_task_visible,
        "memory_only_task_is_durable_evidence": False,
        "bootstrap_mode": payload.get("bootstrap_mode"),
        "source": payload.get("source"),
        "symbol_count": int(payload.get("symbol_count") or 0),
        "symbol_limit": int(payload.get("symbol_limit") or 0),
        "truncated_by_symbol_limit": payload.get("truncated_by_symbol_limit") is True,
        "sources_enabled": payload.get("sources_enabled") is True,
        "tushare_on_open": payload.get("tushare_on_open") is True,
        "deepseek_on_open": payload.get("deepseek_on_open") is True,
        "external_execution_profile": str(
            summary.get("external_execution_profile") or DEFAULT_EXTERNAL_EXECUTION_PROFILE
        ),
        "external_execution_profile_provider_stage_allowed": (
            summary.get("external_execution_profile_provider_stage_allowed") is True
        ),
        "external_execution_profile_model_stage_allowed": (
            summary.get("external_execution_profile_model_stage_allowed") is True
        ),
        "external_execution_profile_executor_implemented": provider_execution_observed or model_execution_observed,
        "bootstrap_stage_count": int(summary.get("stage_count") or 0),
        "model_ledger_preview_count": int(summary.get("model_ledger_preview_count") or 0),
        "local_compute_handoff_visible": local_compute_handoff_visible,
        "local_compute_handoff_schema_version": str(local_compute_handoff.get("schema_version") or ""),
        "local_compute_handoff_status": str(local_compute_handoff.get("status") or "local_compute_handoff_not_recorded"),
        "local_compute_handoff_mode_gate": str(local_compute_handoff.get("mode_gate") or "live_light"),
        "local_compute_handoff_mode_gate_satisfied": local_compute_handoff.get("mode_gate_satisfied") is True,
        "local_compute_handoff_source_switch_satisfied": local_compute_handoff.get("source_switch_satisfied") is True,
        "local_compute_handoff_inactive_reason": str(local_compute_handoff.get("inactive_reason") or ""),
        "local_compute_handoff_row_count": int(
            local_compute_handoff.get("handoff_row_count") or summary.get("local_compute_handoff_row_count") or 0
        ),
        "local_compute_handoff_enabled_row_count": int(local_compute_handoff.get("enabled_handoff_row_count") or 0),
        "local_compute_handoff_executed_row_count": int(
            local_compute_handoff.get("executed_handoff_row_count")
            or summary.get("local_compute_handoff_executed_row_count")
            or 0
        ),
        "local_compute_handoff_output_written_row_count": int(
            local_compute_handoff.get("output_written_row_count") or 0
        ),
        "local_compute_handoff_future_local_routes": list(local_compute_handoff.get("future_local_routes") or []),
        "local_compute_handoff_future_task_types": list(local_compute_handoff.get("future_task_types") or []),
        "local_compute_handoff_output_packet_keys": list(local_compute_handoff.get("output_packet_keys") or []),
        "local_compute_handoff_input_packet_keys": list(local_compute_handoff.get("input_packet_keys") or []),
        "local_compute_handoff_lineage_contract_schema_version": str(
            local_compute_handoff.get("lineage_contract_schema_version") or ""
        ),
        "local_compute_handoff_lineage_write_policy": str(
            local_compute_handoff.get("lineage_write_policy") or ""
        ),
        "local_compute_handoff_lineage_required_field_count": int(
            local_compute_handoff.get("lineage_required_field_count") or 0
        ),
        "local_compute_handoff_lineage_written_row_count": int(
            local_compute_handoff.get("lineage_written_row_count") or 0
        ),
        "local_compute_handoff_cache_get_may_write_lineage": (
            local_compute_handoff.get("cache_get_may_write_lineage") is True
        ),
        "local_compute_handoff_react_render_may_write_lineage": (
            local_compute_handoff.get("react_render_may_write_lineage") is True
        ),
        "local_compute_handoff_fastapi_startup_may_write_lineage": (
            local_compute_handoff.get("fastapi_startup_may_write_lineage") is True
        ),
        "local_compute_handoff_lineage_is_execution_evidence": (
            local_compute_handoff.get("lineage_is_execution_evidence") is True
        ),
        "local_compute_handoff_lineage_is_production_evidence": (
            local_compute_handoff.get("lineage_is_production_evidence") is True
        ),
        "local_compute_handoff_replay_executes_local_compute": False,
        "local_compute_handoff_replay_writes_output": False,
        "local_compute_handoff_replay_is_execution_evidence": False,
        "local_compute_handoff_replay_is_production_evidence": False,
        "planned_provider_stage_count": int(summary.get("planned_provider_stage_count") or 0),
        "planned_model_stage_count": int(summary.get("planned_model_stage_count") or 0),
        "actual_provider_execution_count": max(
            int(summary.get("actual_provider_execution_count") or 0),
            actual_provider_execution_count,
        ),
        "actual_model_call_count": max(
            int(summary.get("actual_model_call_count") or 0),
            actual_model_call_count,
        ),
        "rate_limit_reused_existing_task": current_step == "live_bootstrap_skipped_due_to_rate_limit",
        "call_ledger_count": len(call_ledger),
        "task_success_is_provider_model_evidence": provider_execution_observed or model_execution_observed,
        "task_success_is_production_evidence": False,
        "provider_execution_implemented": provider_execution_observed,
        "model_execution_implemented": model_execution_observed,
        "provider_model_execution_implemented": provider_execution_observed or model_execution_observed,
        "production_live_light_complete": False,
        "is_production_evidence": False,
        "external_calls_triggered": latest_task.get("external_calls_triggered") is True,
        "tushare_called": latest_task.get("tushare_called") is True,
        "deepseek_called": latest_task.get("deepseek_called") is True,
        "github_called": latest_task.get("github_called") is True,
        "contains_secret": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "does_not_execute_trades": latest_task.get("does_not_execute_trades") is not False,
        "does_not_modify_strategy_action": latest_task.get("does_not_modify_strategy_action") is not False,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _latest_search_quant_projection_status_surface() -> dict[str, Any]:
    def durable_quant_task(task: dict[str, Any]) -> bool:
        storage_source = str(task.get("storage_source") or "")
        return (
            task.get("task_type") == SEARCH_QUANT_PROJECTION_TASK_TYPE
            and task.get("cache_replay_only") is not True
            and storage_source in {"memory_and_sqlite", "sqlite_meta"}
        )

    latest_task = next(
        (
            task
            for task in task_service.list_task_statuses()
            if durable_quant_task(task)
        ),
        None,
    )
    if latest_task is None:
        return {
            "schema_version": SEARCH_QUANT_LATEST_STATUS_SCHEMA_VERSION,
            "status": "no_quant_projection_task_found",
            "lookup_source": "task_service.list_task_statuses",
            "lookup_creates_task": False,
            "route": SEARCH_QUANT_PROJECTION_ROUTE,
            "route_implemented": True,
            "task_found": False,
            "task_id": "",
            "task_status": "",
            "current_step": "",
            "output_packet_key": "",
            "storage_source": "",
            "durable_task_visible": False,
            "memory_only_task_is_durable_evidence": False,
            "symbol": "",
            "symbol_valid": False,
            "scan_mode": "search_quant_projection",
            "selected_light_apis": [],
            "include_tushare_requested": False,
            "include_deepseek_requested": False,
            "local_receipt_visible": False,
            "provider_model_pending": False,
            "acceptance_dry_run_required": True,
            "execution_request_required": True,
            "provider_model_route": SEARCH_QUANT_PROVIDER_MODEL_ROUTE,
            "result_surface_count": 6,
            "call_ledger_count": 0,
            "call_status": "",
            "task_success_is_provider_model_evidence": False,
            "task_success_is_production_evidence": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "factor_refresh_executed": False,
            "next_session_refresh_executed": False,
            "echarts_payload_refreshed": False,
            "production_quant_projection_complete": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "contains_secret": False,
            "credential_values_exposed": False,
            "env_key_names_included": False,
            "candidate_is_not_buy_instruction": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_prices_positions_or_operation_zones": True,
        }

    call_ledger = list(latest_task.get("call_ledger") or [])
    first_ledger = _dict(call_ledger[0] if call_ledger else {})
    request_params = _dict(first_ledger.get("request_params_safe"))
    storage_source = str(latest_task.get("storage_source") or "")
    durable_task_visible = storage_source in {"memory_and_sqlite", "sqlite_meta"}
    current_step = str(latest_task.get("current_step") or "")
    symbol_valid = request_params.get("symbol_valid") is True
    local_receipt_visible = (
        latest_task.get("status") == "success"
        and current_step == "candidate_radar_quant_projection_ready"
        and symbol_valid
    )
    if local_receipt_visible:
        status = "latest_quant_projection_receipt_visible_provider_model_pending"
    elif current_step == "candidate_radar_quant_projection_blocked_invalid_symbol":
        status = "latest_quant_projection_receipt_blocked_invalid_symbol"
    else:
        status = "latest_quant_projection_task_visible_not_ready"
    return {
        "schema_version": SEARCH_QUANT_LATEST_STATUS_SCHEMA_VERSION,
        "status": status,
        "lookup_source": "task_service.list_task_statuses",
        "lookup_creates_task": False,
        "route": SEARCH_QUANT_PROJECTION_ROUTE,
        "route_implemented": True,
        "task_found": True,
        "task_id": latest_task.get("task_id"),
        "task_status": latest_task.get("status"),
        "current_step": current_step,
        "output_packet_key": latest_task.get("output_packet_key"),
        "storage_source": storage_source,
        "durable_task_visible": durable_task_visible,
        "memory_only_task_is_durable_evidence": False,
        "symbol": request_params.get("symbol") or "",
        "symbol_valid": symbol_valid,
        "scan_mode": request_params.get("scan_mode") or "search_quant_projection",
        "selected_light_apis": list(request_params.get("selected_light_apis") or []),
        "include_tushare_requested": request_params.get("include_tushare_requested") is True,
        "include_deepseek_requested": request_params.get("include_deepseek_requested") is True,
        "local_receipt_visible": local_receipt_visible,
        "provider_model_pending": True,
        "acceptance_dry_run_required": True,
        "execution_request_required": True,
        "provider_model_route": SEARCH_QUANT_PROVIDER_MODEL_ROUTE,
        "result_surface_count": 6,
        "call_ledger_count": len(call_ledger),
        "call_status": first_ledger.get("call_status") or "",
        "task_success_is_provider_model_evidence": False,
        "task_success_is_production_evidence": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "production_quant_projection_complete": False,
        "external_calls_triggered": latest_task.get("external_calls_triggered") is True,
        "tushare_called": latest_task.get("tushare_called") is True,
        "deepseek_called": latest_task.get("deepseek_called") is True,
        "github_called": latest_task.get("github_called") is True,
        "contains_secret": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "candidate_is_not_buy_instruction": True,
        "does_not_execute_trades": latest_task.get("does_not_execute_trades") is not False,
        "does_not_modify_strategy_action": latest_task.get("does_not_modify_strategy_action") is not False,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _latest_search_quant_projection_provider_model_status_surface() -> dict[str, Any]:
    def durable_provider_model_task(task: dict[str, Any]) -> bool:
        storage_source = str(task.get("storage_source") or "")
        return (
            task.get("task_type") == SEARCH_QUANT_PROVIDER_MODEL_TASK_TYPE
            and task.get("cache_replay_only") is not True
            and storage_source in {"memory_and_sqlite", "sqlite_meta"}
        )

    latest_task = next(
        (
            task
            for task in task_service.list_task_statuses()
            if durable_provider_model_task(task)
        ),
        None,
    )
    base = {
        "schema_version": SEARCH_QUANT_PROVIDER_MODEL_LATEST_STATUS_SCHEMA_VERSION,
        "lookup_source": "task_service.list_task_statuses",
        "lookup_creates_task": False,
        "route": SEARCH_QUANT_PROVIDER_MODEL_ROUTE,
        "route_implemented": True,
        "task_type": SEARCH_QUANT_PROVIDER_MODEL_TASK_TYPE,
        "task_catalog_covered": True,
        "status_get_external_calls": False,
        "acceptance_is_not_production_promotion": True,
        "candidate_is_not_buy_instruction": True,
        "contains_secret": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    if latest_task is None:
        return {
            **base,
            "status": "no_quant_projection_provider_model_task_found",
            "task_found": False,
            "task_id": "",
            "task_status": "",
            "current_step": "",
            "output_packet_key": "",
            "storage_source": "",
            "durable_task_visible": False,
            "memory_only_task_is_durable_evidence": False,
            "symbol": "",
            "selected_apis": [],
            "include_deepseek_requested": False,
            "call_ledger_count": 0,
            "provider_call_ledger_count": 0,
            "provider_api_success_count": 0,
            "model_ledger_count": 0,
            "call_status": "",
            "provider_model_acceptance_visible": False,
            "provider_call_ledger_evidence_done": False,
            "tushare_call_ledger_evidence_done": False,
            "deepseek_model_ledger_evidence_done": False,
            "deepseek_output_acceptance_contract_visible": True,
            "deepseek_output_acceptance_required_when_deepseek_used": True,
            "deepseek_output_acceptance_required": False,
            "deepseek_output_acceptance_done": False,
            "deepseek_output_acceptance_status": "not_required_no_task",
            "deepseek_output_cache_written": False,
            "deepseek_output_safe_summary_visible": False,
            "deepseek_skipped_by_default": True,
            "provider_execution_observed": False,
            "model_execution_observed": False,
            "factor_refresh_executed": False,
            "next_session_refresh_executed": False,
            "echarts_payload_refreshed": False,
            "production_quant_projection_complete": False,
            "production_radar_replacement_complete": False,
            "task_success_is_provider_call_evidence": False,
            "task_success_is_model_evidence": False,
            "task_success_is_model_output_evidence": False,
            "task_success_is_provider_model_evidence": False,
            "task_success_is_production_evidence": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    call_ledger = [row for row in _list(latest_task.get("call_ledger")) if isinstance(row, dict)]
    first_ledger = _dict(call_ledger[0] if call_ledger else {})
    request_params = _dict(first_ledger.get("request_params_safe"))
    selected_api_set = {str(api) for api in _list(request_params.get("selected_apis"))}
    provider_ledgers = [
        row
        for row in call_ledger
        if row.get("tushare_called") is True
        and (not selected_api_set or str(row.get("api") or "") in selected_api_set)
    ]
    provider_success_ledgers = [
        row for row in provider_ledgers if str(row.get("call_status") or "") == "success"
    ]
    model_ledgers = [row for row in call_ledger if row.get("deepseek_called") is True]
    storage_source = str(latest_task.get("storage_source") or "")
    durable_task_visible = storage_source in {"memory_and_sqlite", "sqlite_meta"}
    task_success = latest_task.get("status") == "success"
    provider_call_ledger_evidence_done = (
        bool(provider_success_ledgers)
        or request_params.get("tushare_call_ledger_evidence_done") is True
        or request_params.get("provider_call_ledger_evidence_done") is True
    )
    deepseek_model_ledger_evidence_done = (
        bool(model_ledgers) and request_params.get("deepseek_model_ledger_evidence_done") is True
    )
    include_deepseek_requested = request_params.get("include_deepseek") is True
    deepseek_output_acceptance_required = (
        include_deepseek_requested or bool(model_ledgers) or deepseek_model_ledger_evidence_done
    )
    deepseek_output_acceptance_done = (
        bool(model_ledgers)
        and request_params.get("deepseek_output_acceptance_done") is True
        and str(request_params.get("deepseek_output_parse_status") or "") == "passed"
        and str(request_params.get("deepseek_output_sanitizer_status") or "") == "passed"
        and request_params.get("deepseek_output_schema_whitelist_passed") is True
        and request_params.get("deepseek_output_cache_lineage_bound") is True
        and request_params.get("deepseek_output_no_overwrite_bound") is True
    )
    deepseek_output_cache_written = (
        deepseek_output_acceptance_done and request_params.get("deepseek_output_cache_written") is True
    )
    deepseek_output_safe_summary_visible = (
        deepseek_output_acceptance_done and request_params.get("deepseek_output_safe_summary_visible") is True
    )
    if not deepseek_output_acceptance_required:
        deepseek_output_acceptance_status = "not_required_deepseek_skipped"
    elif not deepseek_model_ledger_evidence_done:
        deepseek_output_acceptance_status = "pending_model_ledger"
    elif not deepseek_output_acceptance_done:
        deepseek_output_acceptance_status = "pending_parse_sanitizer_lineage"
    else:
        deepseek_output_acceptance_status = "accepted_safe_output_visible"
    if (
        task_success
        and provider_call_ledger_evidence_done
        and deepseek_model_ledger_evidence_done
        and deepseek_output_acceptance_done
    ):
        status = "latest_quant_projection_provider_model_acceptance_visible"
    elif task_success and provider_call_ledger_evidence_done and deepseek_output_acceptance_required:
        status = "latest_quant_projection_provider_model_task_visible_output_acceptance_pending"
    elif task_success and provider_call_ledger_evidence_done:
        status = "latest_quant_projection_provider_acceptance_visible_deepseek_skipped"
    else:
        status = "latest_quant_projection_provider_model_task_visible_without_complete_evidence"
    task_success_is_model_evidence = task_success and deepseek_model_ledger_evidence_done
    task_success_is_model_output_evidence = task_success and deepseek_output_acceptance_done
    task_success_is_provider_model_evidence = (
        task_success
        and provider_call_ledger_evidence_done
        and deepseek_model_ledger_evidence_done
        and deepseek_output_acceptance_done
    )
    return {
        **base,
        "status": status,
        "task_found": True,
        "task_id": latest_task.get("task_id"),
        "task_status": latest_task.get("status"),
        "current_step": latest_task.get("current_step") or "",
        "output_packet_key": latest_task.get("output_packet_key") or "",
        "storage_source": storage_source,
        "durable_task_visible": durable_task_visible,
        "memory_only_task_is_durable_evidence": False,
        "symbol": request_params.get("symbol") or "",
        "selected_apis": list(request_params.get("selected_apis") or []),
        "include_deepseek_requested": include_deepseek_requested,
        "call_ledger_count": len(call_ledger),
        "provider_call_ledger_count": len(provider_ledgers),
        "provider_api_success_count": len(provider_success_ledgers),
        "model_ledger_count": len(model_ledgers),
        "call_status": first_ledger.get("call_status") or "",
        "provider_model_acceptance_visible": task_success
        and (not deepseek_output_acceptance_required or deepseek_output_acceptance_done),
        "provider_call_ledger_evidence_done": provider_call_ledger_evidence_done,
        "tushare_call_ledger_evidence_done": provider_call_ledger_evidence_done,
        "deepseek_model_ledger_evidence_done": deepseek_model_ledger_evidence_done,
        "deepseek_output_acceptance_contract_visible": True,
        "deepseek_output_acceptance_required_when_deepseek_used": True,
        "deepseek_output_acceptance_required": deepseek_output_acceptance_required,
        "deepseek_output_acceptance_done": deepseek_output_acceptance_done,
        "deepseek_output_acceptance_status": deepseek_output_acceptance_status,
        "deepseek_output_cache_written": deepseek_output_cache_written,
        "deepseek_output_safe_summary_visible": deepseek_output_safe_summary_visible,
        "deepseek_skipped_by_default": latest_task.get("deepseek_called") is not True,
        "provider_execution_observed": latest_task.get("tushare_called") is True,
        "model_execution_observed": latest_task.get("deepseek_called") is True,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "production_quant_projection_complete": False,
        "production_radar_replacement_complete": False,
        "task_success_is_provider_call_evidence": task_success and provider_call_ledger_evidence_done,
        "task_success_is_model_evidence": task_success_is_model_evidence,
        "task_success_is_model_output_evidence": task_success_is_model_output_evidence,
        "task_success_is_provider_model_evidence": task_success_is_provider_model_evidence,
        "task_success_is_production_evidence": False,
        "external_calls_triggered": latest_task.get("external_calls_triggered") is True,
        "tushare_called": latest_task.get("tushare_called") is True,
        "deepseek_called": latest_task.get("deepseek_called") is True,
        "github_called": latest_task.get("github_called") is True,
        "does_not_execute_trades": latest_task.get("does_not_execute_trades") is not False,
        "does_not_modify_strategy_action": latest_task.get("does_not_modify_strategy_action") is not False,
    }


def _runtime_mode() -> tuple[str, str, bool, str, bool]:
    state = get_command_center_runtime_mode_state(DEFAULT_MODE)
    return (
        str(state["mode"]),
        str(state["configured_value_safe"]),
        state["valid"] is True,
        str(state["source"]),
        state["redacted_invalid"] is True,
    )


def _mode_trigger_fields(mode: str) -> dict[str, Any]:
    page_open_policies = {
        "cache_only": "disabled_cache_only",
        "manual": "disabled_requires_explicit_post_task",
        "live_light": "after_cache_render_rate_limited_local_task",
        "live_full": "reserved_disabled_requires_future_authorization",
    }
    search_action_policies = {
        "cache_only": "disabled_cache_only",
        "manual": "explicit_post_task_only",
        "live_light": "explicit_search_action_local_task_provider_model_requires_execution_request",
        "live_full": "reserved_disabled_requires_future_authorization",
    }
    return {
        "trigger_matrix_schema_version": BOOTSTRAP_MODE_TRIGGER_MATRIX_SCHEMA_VERSION,
        "page_open_task_allowed": mode == "live_light",
        "page_open_task_policy": page_open_policies[mode],
        "react_initial_render_creates_task": False,
        "react_mounted_task_allowed_after_cache_render": mode == "live_light",
        "search_input_auto_task_allowed": False,
        "search_input_task_policy": "never_on_typing",
        "search_action_task_allowed": mode in {"manual", "live_light"},
        "search_action_task_policy": search_action_policies[mode],
        "provider_model_execution_without_execution_request_allowed": False,
        "real_trading_task_allowed": False,
    }


def _runtime_mode_policy_by_mode(mode: str) -> dict[str, Any]:
    for row in get_command_center_runtime_mode_policies():
        if row.get("mode") == mode:
            return row
    return {}


def _runtime_mode_policy_rows(active_mode: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in get_command_center_runtime_mode_policies():
        mode = str(row.get("mode") or "")
        rows.append(
            {
                **row,
                "active": mode == active_mode,
                "policy_source": "config.COMMAND_CENTER_RUNTIME_MODE_POLICIES",
                "frontend_visible": True,
                "frontend_editable": False,
                "frontend_writeback_allowed": False,
                "status_endpoint_writeback_allowed": False,
                "cache_get_external_calls": False,
                "react_render_provider_calls": False,
                "fastapi_startup_external_calls": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "is_production_evidence": False,
            }
        )
    return rows


def _mode_row(mode: str, active_mode: str) -> dict[str, Any]:
    policy = _runtime_mode_policy_by_mode(mode)
    external_calls = {
        "cache_only": "none",
        "manual": "selected_post_task_only",
        "live_light": "future_light_tushare_optional_deepseek_task",
        "live_full": "reserved_future_worker_mode",
    }[mode]
    return {
        "mode": mode,
        "active": mode == active_mode,
        "default": mode == DEFAULT_MODE,
        "status": "active" if mode == active_mode else "available",
        "external_calls": external_calls,
        "external_call_rule": policy.get("external_call_rule", external_calls),
        "task_creation_rule": policy.get("task_creation_rule", ""),
        "startup_rule": policy.get("startup_rule", ""),
        "config_policy_default": bool(policy.get("default")),
        "config_policy_use_case": policy.get("use_case", ""),
        "config_policy_source": "config.COMMAND_CENTER_RUNTIME_MODE_POLICIES",
        "cache_get_external_calls": False,
        "react_render_provider_calls": False,
        "post_task_required": mode != "cache_only",
        **_mode_trigger_fields(mode),
        "bootstrap_task_implemented": True if mode == "live_light" else (False if mode == "live_full" else None),
        "provider_execution_implemented": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _runtime_mode_acceptance_contract(active_mode: str) -> dict[str, Any]:
    acceptance_rows = [
        {
            "mode": "cache_only",
            "active": active_mode == "cache_only",
            "acceptance_status": "default_offline_cache_read_only",
            "intended_use": "smoke_ci_fast_local_review",
            "external_call_surface": "none",
            "page_open_task_allowed": False,
            "search_submit_task_allowed": False,
            "manual_button_task_allowed": False,
            "live_light_background_task_allowed": False,
            "provider_model_execution_allowed": False,
            "provider_model_execution_surface": "none",
            "provider_model_direct_execution_allowed": False,
            "provider_model_requires_explicit_post_task": False,
            "acceptance_evidence_required": "status_cache_read_shows_no_task_no_external_calls",
        },
        {
            "mode": "manual",
            "active": active_mode == "manual",
            "acceptance_status": "explicit_post_task_only",
            "intended_use": "operator_controlled_acceptance",
            "external_call_surface": "selected_post_task_only",
            "page_open_task_allowed": False,
            "search_submit_task_allowed": False,
            "manual_button_task_allowed": True,
            "live_light_background_task_allowed": False,
            "provider_model_execution_allowed": True,
            "provider_model_execution_surface": "selected_explicit_post_task_only",
            "provider_model_direct_execution_allowed": False,
            "provider_model_requires_explicit_post_task": True,
            "provider_model_execution_requires_task_contract": True,
            "acceptance_evidence_required": "button_or_explicit_post_payload_only",
        },
        {
            "mode": "live_light",
            "active": active_mode == "live_light",
            "acceptance_status": "bounded_background_task_creation_only",
            "intended_use": "daily_local_light_research",
            "external_call_surface": "post_task_worker_or_local_fallback_only",
            "page_open_task_allowed": True,
            "page_open_task_policy": "after_cache_render_rate_limited_local_task",
            "search_submit_task_allowed": True,
            "search_submit_task_policy": "safe_submit_local_projection_task_provider_model_request_gated",
            "manual_button_task_allowed": True,
            "live_light_background_task_allowed": True,
            "provider_model_execution_allowed": False,
            "provider_model_execution_surface": "execution_request_post_task_only",
            "provider_model_direct_execution_allowed": False,
            "provider_model_requires_explicit_post_task": True,
            "provider_model_execution_requires_task_contract": True,
            "provider_model_execution_requires_execution_request": True,
            "acceptance_evidence_required": "task_id_status_progress_call_model_ledger_visible_nonblocking_ui",
        },
        {
            "mode": "live_full",
            "active": active_mode == "live_full",
            "acceptance_status": "reserved_disabled_requires_future_authorization",
            "intended_use": "future_full_pool_or_deep_scan",
            "external_call_surface": "reserved_none_now",
            "page_open_task_allowed": False,
            "search_submit_task_allowed": False,
            "manual_button_task_allowed": False,
            "live_light_background_task_allowed": False,
            "provider_model_execution_allowed": False,
            "provider_model_execution_surface": "reserved_none_now",
            "provider_model_direct_execution_allowed": False,
            "provider_model_requires_explicit_post_task": False,
            "full_pool_or_deep_scan_allowed": False,
            "acceptance_evidence_required": "reserved_contract_shows_disabled_until_separate_authorization",
        },
    ]
    common_flags = {
        "schema_version": BOOTSTRAP_RUNTIME_MODE_ACCEPTANCE_SCHEMA_VERSION,
        "cache_get_external_calls": False,
        "react_initial_render_creates_task": False,
        "react_render_direct_provider_calls": False,
        "search_typing_creates_task": False,
        "fastapi_startup_creates_task": False,
        "fastapi_startup_external_calls": False,
        "token_key_exposure_allowed": False,
        "raw_config_values_exposed": False,
        "credential_values_exposed": False,
        "radar_candidate_is_buy_instruction": False,
        "deepseek_is_data_source": False,
        "deepseek_may_overwrite_numeric_or_action_fields": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "production_evidence": False,
    }
    acceptance_rows = [{**row, **common_flags} for row in acceptance_rows]
    return {
        "schema_version": BOOTSTRAP_RUNTIME_MODE_ACCEPTANCE_SCHEMA_VERSION,
        "status": "runtime_mode_acceptance_matrix_visible_read_only",
        "mode": active_mode,
        "acceptance_row_count": len(acceptance_rows),
        "active_acceptance_mode": active_mode,
        "acceptance_rows": acceptance_rows,
        "cache_only_default_offline": True,
        "manual_explicit_post_only": True,
        "manual_provider_model_surface": "selected_explicit_post_task_only",
        "manual_provider_model_direct_execution_allowed": False,
        "manual_provider_model_requires_explicit_post_task": True,
        "live_light_bounded_background_task_only": True,
        "live_light_provider_model_surface": "execution_request_post_task_only",
        "live_light_provider_model_direct_execution_allowed": False,
        "live_full_reserved_disabled": True,
        "all_modes_require_post_task_for_external_calls": True,
        "provider_model_direct_execution_allowed": False,
        "provider_model_execution_requires_execution_request": True,
        "frontend_visible": True,
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "cache_get_external_calls": False,
        "react_initial_render_creates_task": False,
        "react_render_direct_provider_calls": False,
        "search_typing_creates_task": False,
        "fastapi_startup_creates_task": False,
        "fastapi_startup_external_calls": False,
        "token_key_exposure_allowed": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "runtime_mode_acceptance_is_production_evidence": False,
        "production_live_light_complete": False,
        "production_live_full_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _live_light_rollout_roadmap_contract(active_mode: str) -> dict[str, Any]:
    rollout_rows = [
        {
            "stage_key": "stage_01_mode_config_contracts",
            "stage_order": 1,
            "status": "local_contract_ready_not_production",
            "current_evidence": [
                "safe_config_contract",
                "runtime_config_reference_contract",
                "runtime_mode_acceptance_contract",
            ],
            "next_action": "keep_config_visible_and_promote_allowlist_only_in_future_file_scope",
            "local_ready": True,
            "implementation_pending": False,
            "production_evidence_complete": False,
        },
        {
            "stage_key": "stage_02_local_bootstrap_skeleton",
            "stage_order": 2,
            "status": "local_task_skeleton_ready_no_provider_execution",
            "current_evidence": [
                PLANNED_BOOTSTRAP_TASK_ROUTE,
                BOOTSTRAP_TASK_TYPE,
                "staged_run_plan",
                "model_ledger_preview",
            ],
            "next_action": "keep_background_task_rate_limited_and_nonblocking",
            "local_ready": True,
            "implementation_pending": False,
            "production_evidence_complete": False,
        },
        {
            "stage_key": "stage_03_search_submit_local_projection",
            "stage_order": 3,
            "status": "backend_local_route_ready_frontend_wiring_pending",
            "current_evidence": [
                SEARCH_QUANT_PROJECTION_ROUTE,
                SEARCH_QUANT_PROJECTION_TASK_TYPE,
                "latest_status_replay",
                "config_handoff_and_promotion_contract",
            ],
            "next_action": "wire_candidate_radar_safe_submit_to_task_receipt_and_polling",
            "local_ready": True,
            "local_ready_scope": "backend_local_route_task_status_replay_and_contracts",
            "frontend_wiring_pending": True,
            "browser_runtime_evidence_pending": True,
            "implementation_pending": True,
            "production_evidence_complete": False,
        },
        {
            "stage_key": "stage_04_frontend_nonblocking_wiring",
            "stage_order": 4,
            "status": "frontend_wiring_and_browser_evidence_pending",
            "current_evidence": [
                "search_quant_projection_frontend_wiring_acceptance_contract",
                "runtime_cache_first_polling_contract",
            ],
            "next_action": "implement_frontend_submit_autostart_with_initial_cache_render_silence_and_task_polling",
            "local_ready": False,
            "implementation_pending": True,
            "production_evidence_complete": False,
        },
        {
            "stage_key": "stage_05_provider_model_execution_request_route",
            "stage_order": 5,
            "status": "execution_request_route_registered_receipt_service_ready",
            "current_evidence": [
                "live_light_provider_model_execution_request_contract",
                "live_light_execution_request_handoff_contract",
                "runtime_operator_summary_contract",
                BOOTSTRAP_EXECUTION_REQUEST_TASK_TYPE,
            ],
            "next_action": "verify_button_gated_route_adapter_before_real_provider_model_task",
            "local_ready": True,
            "local_receipt_service_ready": True,
            "operator_readiness_visible": True,
            "route_implemented": BOOTSTRAP_EXECUTION_REQUEST_ROUTE_IMPLEMENTED,
            "provider_model_task_creation_allowed": False,
            "implementation_pending": False,
            "production_evidence_complete": False,
        },
        {
            "stage_key": "stage_06_tushare_light_provider_acceptance",
            "stage_order": 6,
            "status": "real_tushare_call_ledger_pending_user_approved_run",
            "current_evidence": ["tushare_light_strategy_contract", "provider_model_acceptance_runbook"],
            "next_action": "run_user_approved_tushare_light_sample_with_safe_call_ledger",
            "local_ready": False,
            "implementation_pending": True,
            "production_evidence_complete": False,
        },
        {
            "stage_key": "stage_07_deepseek_pro_after_data_acceptance",
            "stage_order": 7,
            "status": "real_deepseek_model_ledger_pending_user_approved_run",
            "current_evidence": ["deepseek_pro_strategy_contract", "model_ledger_preview"],
            "next_action": "run_user_approved_after_data_ready_deepseek_sample_with_model_ledger",
            "local_ready": False,
            "implementation_pending": True,
            "production_evidence_complete": False,
        },
        {
            "stage_key": "stage_08_cache_lineage_and_output_surfaces",
            "stage_order": 8,
            "status": "durable_lineage_and_output_writeback_pending",
            "current_evidence": [
                "live_light_cache_lineage_contract",
                "live_light_output_surface_contract",
                "live_light_local_fallback_contract",
            ],
            "next_action": "write_only_task_produced_lineage_and_research_outputs_after_provider_model_evidence",
            "local_ready": False,
            "implementation_pending": True,
            "production_evidence_complete": False,
        },
        {
            "stage_key": "stage_09_release_promotion",
            "stage_order": 9,
            "status": "production_promotion_pending_remote_ci_redaction_and_review",
            "current_evidence": ["live_light_promotion_gate_contract", "bootstrap_runtime_contract"],
            "next_action": "promote_only_after_real_ledgers_browser_evidence_redaction_review_and_ci",
            "local_ready": False,
            "implementation_pending": True,
            "production_evidence_complete": False,
        },
    ]
    common_flags = {
        "schema_version": BOOTSTRAP_LIVE_LIGHT_ROLLOUT_ROADMAP_SCHEMA_VERSION,
        "mode": active_mode,
        "creates_task": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "fastapi_startup_creates_task": False,
        "search_typing_creates_task": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    rollout_rows = [{**row, **common_flags} for row in rollout_rows]
    return {
        "schema_version": BOOTSTRAP_LIVE_LIGHT_ROLLOUT_ROADMAP_SCHEMA_VERSION,
        "status": "live_light_rollout_roadmap_visible_execution_pending",
        "mode": active_mode,
        "stage_count": len(rollout_rows),
        "local_ready_stage_count": sum(1 for row in rollout_rows if row["local_ready"]),
        "production_evidence_complete_stage_count": 0,
        "next_implementation_stage_key": "stage_04_frontend_nonblocking_wiring",
        "next_browser_stage_key": "stage_04_frontend_nonblocking_wiring",
        "next_execution_request_stage_key": "stage_05_provider_model_execution_request_route",
        "next_provider_stage_key": "stage_06_tushare_light_provider_acceptance",
        "rollout_rows": rollout_rows,
        "backend_local_search_projection_ready": True,
        "frontend_wiring_pending": True,
        "execution_request_route_pending": False,
        "execution_request_receipt_service_ready": True,
        "execution_request_operator_readiness_visible": True,
        "execution_request_provider_model_task_creation_allowed": False,
        "real_tushare_call_ledger_pending": True,
        "real_deepseek_model_ledger_pending": True,
        "browser_nonblocking_evidence_pending": True,
        "cache_lineage_writeback_pending": True,
        "remote_ci_and_redaction_review_pending": True,
        "provider_model_execution_requires_execution_request": True,
        "rollout_roadmap_is_production_evidence": False,
        "production_live_light_complete": False,
        "frontend_visible": True,
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "creates_task": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "fastapi_startup_creates_task": False,
        "search_typing_creates_task": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _task_creation_invariant_contract(
    *,
    active_mode: str,
    effective_search_submit_autostart: bool,
    live_light_sources_enabled: bool,
) -> dict[str, Any]:
    invariant_rows = [
        {
            "surface_key": "fastapi_startup",
            "surface": "FastAPI startup",
            "task_creation_allowed": False,
            "allowed_modes": [],
            "expected_behavior": "startup_import_and_health_only_no_task",
            "route_or_component": "app startup",
        },
        {
            "surface_key": "get_bootstrap_status",
            "surface": BOOTSTRAP_STATUS_ROUTE,
            "task_creation_allowed": False,
            "allowed_modes": [],
            "expected_behavior": "read_runtime_mode_contracts_only",
            "route_or_component": BOOTSTRAP_STATUS_ROUTE,
        },
        {
            "surface_key": "get_cache_api",
            "surface": "GET cache APIs",
            "task_creation_allowed": False,
            "allowed_modes": [],
            "expected_behavior": "read_cache_only_no_provider_or_task",
            "route_or_component": "GET */cache",
        },
        {
            "surface_key": "react_initial_render",
            "surface": "React initial render",
            "task_creation_allowed": False,
            "allowed_modes": [],
            "expected_behavior": "render_cache_or_loading_state_only",
            "route_or_component": "Command Center React render",
        },
        {
            "surface_key": "react_after_cache_render_live_light_bootstrap",
            "surface": "React mounted after initial cache render",
            "task_creation_allowed": active_mode == "live_light" and live_light_sources_enabled,
            "allowed_modes": ["live_light"],
            "expected_behavior": "create_or_reuse_rate_limited_local_bootstrap_task_only",
            "route_or_component": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "task_type": BOOTSTRAP_TASK_TYPE,
            "requires_initial_cache_render": True,
            "requires_rate_limit": True,
            "creates_provider_model_task": False,
        },
        {
            "surface_key": "search_typing",
            "surface": "search input typing",
            "task_creation_allowed": False,
            "allowed_modes": [],
            "expected_behavior": "normalize_preview_only_no_task",
            "route_or_component": "Candidate Radar search input",
        },
        {
            "surface_key": "safe_search_submit_autostart",
            "surface": "safe searched-symbol submit",
            "task_creation_allowed": active_mode == "live_light" and effective_search_submit_autostart,
            "allowed_modes": ["live_light"],
            "expected_behavior": "create_or_reuse_local_quant_projection_task_only",
            "route_or_component": SEARCH_QUANT_PROJECTION_ROUTE,
            "task_type": SEARCH_QUANT_PROJECTION_TASK_TYPE,
            "requires_safe_symbol": True,
            "requires_submit_autostart_config": True,
            "creates_provider_model_task": False,
        },
        {
            "surface_key": "manual_button_post_task",
            "surface": "manual button or explicit POST payload",
            "task_creation_allowed": active_mode in {"manual", "live_light"},
            "allowed_modes": ["manual", "live_light"],
            "expected_behavior": "explicit_user_action_only_task_route_contract_applies",
            "route_or_component": "POST task routes",
            "requires_user_action": True,
        },
        {
            "surface_key": "task_status_polling",
            "surface": "task status polling",
            "task_creation_allowed": False,
            "allowed_modes": [],
            "expected_behavior": "read_existing_task_status_only",
            "route_or_component": "GET /api/tasks/{task_id}",
        },
    ]
    common_flags = {
        "schema_version": BOOTSTRAP_TASK_CREATION_INVARIANT_SCHEMA_VERSION,
        "active_mode": active_mode,
        "get_creates_task": False,
        "typing_creates_task": False,
        "render_direct_provider_calls": False,
        "external_calls_triggered_by_contract": False,
        "provider_model_execution_requires_execution_request": True,
        "task_success_is_production_evidence": False,
        "radar_candidate_is_buy_instruction": False,
        "token_key_exposure_allowed": False,
        "credential_values_exposed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    invariant_rows = [{**row, **common_flags} for row in invariant_rows]
    allowed_task_surface_count = sum(1 for row in invariant_rows if row["task_creation_allowed"])
    return {
        "schema_version": BOOTSTRAP_TASK_CREATION_INVARIANT_SCHEMA_VERSION,
        "status": "task_creation_invariant_visible_read_only",
        "mode": active_mode,
        "surface_row_count": len(invariant_rows),
        "allowed_task_surface_count": allowed_task_surface_count,
        "invariant_rows": invariant_rows,
        "startup_task_creation_allowed": False,
        "get_status_task_creation_allowed": False,
        "get_cache_task_creation_allowed": False,
        "react_initial_render_task_creation_allowed": False,
        "search_typing_task_creation_allowed": False,
        "task_status_polling_creates_task": False,
        "live_light_after_cache_render_task_requires_rate_limit": True,
        "safe_search_submit_requires_live_light_and_config": True,
        "manual_task_creation_requires_explicit_user_action": True,
        "provider_model_execution_requires_execution_request": True,
        "contract_creates_task": False,
        "contract_is_production_evidence": False,
        "frontend_visible": True,
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_external_silence_contract(
    *,
    active_mode: str,
    task_creation_invariant_contract: dict[str, Any],
) -> dict[str, Any]:
    task_rows = {
        str(row.get("surface_key") or ""): row
        for row in task_creation_invariant_contract.get("invariant_rows", [])
        if isinstance(row, dict)
    }
    silence_rows = [
        {
            "surface_key": "fastapi_startup",
            "surface": "FastAPI startup",
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "silence_requirement": "startup_import_and_health_only",
        },
        {
            "surface_key": "get_bootstrap_status",
            "surface": BOOTSTRAP_STATUS_ROUTE,
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "silence_requirement": "read_contracts_only",
        },
        {
            "surface_key": "get_cache_api",
            "surface": "GET cache APIs",
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "silence_requirement": "read_cache_only",
        },
        {
            "surface_key": "react_initial_render",
            "surface": "React initial render",
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "silence_requirement": "render_cache_or_loading_state_only",
        },
        {
            "surface_key": "react_after_cache_render_live_light_bootstrap",
            "surface": "React after initial cache render",
            "local_backend_post_allowed": active_mode == "live_light",
            "task_creation_allowed": bool(
                task_rows.get("react_after_cache_render_live_light_bootstrap", {}).get("task_creation_allowed")
            ),
            "silence_requirement": "may_post_local_bootstrap_task_only_after_cache_render",
        },
        {
            "surface_key": "search_typing",
            "surface": "search input typing",
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "silence_requirement": "normalize_preview_only",
        },
        {
            "surface_key": "safe_search_submit_autostart",
            "surface": "safe searched-symbol submit",
            "local_backend_post_allowed": active_mode == "live_light",
            "task_creation_allowed": bool(
                task_rows.get("safe_search_submit_autostart", {}).get("task_creation_allowed")
            ),
            "silence_requirement": "may_post_local_projection_task_only",
        },
        {
            "surface_key": "manual_button_post_task",
            "surface": "manual button or explicit POST payload",
            "local_backend_post_allowed": active_mode in {"manual", "live_light"},
            "task_creation_allowed": bool(task_rows.get("manual_button_post_task", {}).get("task_creation_allowed")),
            "silence_requirement": "provider_model_calls_must_stay_inside_task_contract",
        },
        {
            "surface_key": "task_status_polling",
            "surface": "task status polling",
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "silence_requirement": "read_existing_task_status_only",
        },
        {
            "surface_key": "operator_summary_display",
            "surface": "runtime operator summary / mode banner",
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "silence_requirement": "display_safe_summary_only",
        },
    ]
    for row in silence_rows:
        row.update(
            {
                "direct_external_calls_allowed": False,
                "direct_provider_calls_allowed": False,
                "direct_model_calls_allowed": False,
                "github_calls_allowed": False,
                "trading_calls_allowed": False,
                "reads_credential_values": False,
                "safe_summary_only": True,
                "provider_model_execution_requires_post_task": True,
                "provider_model_execution_requires_execution_request": True,
                "row_is_production_evidence": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    local_post_exception_count = sum(1 for row in silence_rows if row["local_backend_post_allowed"])
    return {
        "schema_version": BOOTSTRAP_EXTERNAL_SILENCE_SCHEMA_VERSION,
        "status": "runtime_external_silence_visible_read_only",
        "mode": active_mode,
        "silence_rows": silence_rows,
        "silence_row_count": len(silence_rows),
        "local_post_exception_count": local_post_exception_count,
        "direct_external_call_allowed_count": sum(1 for row in silence_rows if row["direct_external_calls_allowed"]),
        "task_creation_allowed_surface_count": sum(1 for row in silence_rows if row["task_creation_allowed"]),
        "silent_read_surface_count": sum(
            1 for row in silence_rows if not row["local_backend_post_allowed"] and not row["task_creation_allowed"]
        ),
        "provider_model_calls_must_use_post_task_worker_or_local_fallback": True,
        "provider_model_execution_requires_execution_request": True,
        "get_cache_direct_external_calls_allowed": False,
        "react_render_direct_provider_calls_allowed": False,
        "fastapi_startup_external_calls_allowed": False,
        "search_typing_task_creation_allowed": False,
        "task_status_polling_creates_task": False,
        "operator_summary_creates_task": False,
        "frontend_visible": True,
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "contract_creates_task": False,
        "contract_calls_provider_or_model": False,
        "external_silence_contract_is_production_evidence": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _runtime_hard_boundary_contract(
    *,
    active_mode: str,
    runtime_mode_acceptance_contract: dict[str, Any],
    task_creation_invariant_contract: dict[str, Any],
    runtime_external_silence_contract: dict[str, Any],
    live_light_ledger_contract: dict[str, Any],
    live_light_ledger_redaction_invariant_contract: dict[str, Any],
    live_light_evidence_grade_contract: dict[str, Any],
    deepseek_pro_strategy_contract: dict[str, Any],
    search_quant_projection_contract: dict[str, Any],
) -> dict[str, Any]:
    boundary_rows = [
        {
            "boundary_key": "get_cache_api_no_direct_external_calls",
            "source_contracts": ["runtime_external_silence_contract", "task_creation_invariant_contract"],
            "required_state": "blocked",
            "passed": runtime_external_silence_contract.get("get_cache_direct_external_calls_allowed")
            is False
            and task_creation_invariant_contract.get("get_cache_task_creation_allowed") is False,
        },
        {
            "boundary_key": "react_render_no_direct_provider_calls",
            "source_contracts": ["runtime_external_silence_contract", "runtime_mode_acceptance_contract"],
            "required_state": "blocked",
            "passed": runtime_external_silence_contract.get("react_render_direct_provider_calls_allowed")
            is False
            and runtime_mode_acceptance_contract.get("react_render_direct_provider_calls") is False,
        },
        {
            "boundary_key": "fastapi_startup_no_auto_external_calls",
            "source_contracts": ["runtime_external_silence_contract", "runtime_mode_acceptance_contract"],
            "required_state": "blocked",
            "passed": runtime_external_silence_contract.get("fastapi_startup_external_calls_allowed") is False
            and runtime_mode_acceptance_contract.get("fastapi_startup_external_calls") is False,
        },
        {
            "boundary_key": "external_work_requires_post_task_worker_or_local_fallback",
            "source_contracts": ["runtime_external_silence_contract", "runtime_mode_acceptance_contract"],
            "required_state": "required",
            "passed": runtime_external_silence_contract.get(
                "provider_model_calls_must_use_post_task_worker_or_local_fallback"
            )
            is True
            and runtime_mode_acceptance_contract.get("all_modes_require_post_task_for_external_calls")
            is True,
        },
        {
            "boundary_key": "provider_calls_require_call_ledger",
            "source_contracts": ["live_light_ledger_contract"],
            "required_state": "required",
            "passed": live_light_ledger_contract.get("call_ledger_required_for_provider") is True,
        },
        {
            "boundary_key": "deepseek_calls_require_model_ledger",
            "source_contracts": ["live_light_ledger_contract"],
            "required_state": "required",
            "passed": live_light_ledger_contract.get("model_ledger_required_for_deepseek") is True,
        },
        {
            "boundary_key": "deepseek_not_data_source",
            "source_contracts": ["deepseek_pro_strategy_contract", "live_light_ledger_redaction_invariant_contract"],
            "required_state": "blocked",
            "passed": deepseek_pro_strategy_contract.get("deepseek_is_data_source") is False
            and live_light_ledger_redaction_invariant_contract.get("deepseek_is_data_source") is False,
        },
        {
            "boundary_key": "deepseek_no_price_holding_factor_zone_or_action_overwrite",
            "source_contracts": ["deepseek_pro_strategy_contract", "live_light_ledger_redaction_invariant_contract"],
            "required_state": "blocked",
            "passed": deepseek_pro_strategy_contract.get("may_overwrite_price") is False
            and deepseek_pro_strategy_contract.get("may_overwrite_holding") is False
            and deepseek_pro_strategy_contract.get("may_overwrite_factor") is False
            and deepseek_pro_strategy_contract.get("may_overwrite_operation_zones") is False
            and deepseek_pro_strategy_contract.get("may_overwrite_strategy_action") is False
            and live_light_ledger_redaction_invariant_contract.get(
                "deepseek_may_overwrite_prices_positions_factors_zones_or_actions"
            )
            is False,
        },
        {
            "boundary_key": "no_real_trading_or_auto_orders",
            "source_contracts": ["runtime_mode_acceptance_contract", "search_quant_projection_workflow_contract"],
            "required_state": "blocked",
            "passed": runtime_mode_acceptance_contract.get("does_not_execute_trades") is True
            and search_quant_projection_contract.get("does_not_execute_trades") is True
            and search_quant_projection_contract.get("trade_instruction_allowed") is not True,
        },
        {
            "boundary_key": "radar_candidate_not_buy_instruction",
            "source_contracts": ["runtime_mode_acceptance_contract", "search_quant_projection_workflow_contract"],
            "required_state": "blocked",
            "passed": runtime_mode_acceptance_contract.get("radar_candidate_is_buy_instruction") is not True
            and search_quant_projection_contract.get("radar_candidate_is_buy_instruction") is not True,
        },
        {
            "boundary_key": "token_key_never_frontend_log_packet_or_cache",
            "source_contracts": ["live_light_ledger_contract", "live_light_ledger_redaction_invariant_contract"],
            "required_state": "blocked",
            "passed": live_light_ledger_contract.get("frontend_packet_may_contain_token_key") is False
            and live_light_ledger_contract.get("logs_may_contain_token_key") is False
            and live_light_ledger_contract.get("cache_may_contain_token_key") is False
            and live_light_ledger_redaction_invariant_contract.get("task_status_may_contain_token_key")
            is False,
        },
        {
            "boundary_key": "mock_receipt_matrix_sanitizer_not_production_evidence",
            "source_contracts": ["live_light_evidence_grade_contract"],
            "required_state": "blocked",
            "passed": live_light_evidence_grade_contract.get("mock_receipt_matrix_sanitizer_can_promote")
            is False
            and live_light_evidence_grade_contract.get("sanitizer_is_model_correctness_evidence")
            is False,
        },
    ]
    for row in boundary_rows:
        row.update(
            {
                "status": "passed" if row["passed"] else "blocked",
                "row_is_production_evidence": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    passed_count = sum(1 for row in boundary_rows if row["passed"])
    blocking_count = len(boundary_rows) - passed_count
    return {
        "schema_version": BOOTSTRAP_HARD_BOUNDARY_SCHEMA_VERSION,
        "status": "runtime_hard_boundaries_visible_read_only"
        if blocking_count == 0
        else "runtime_hard_boundaries_blocked_review_required",
        "mode": active_mode,
        "boundary_rows": boundary_rows,
        "boundary_row_count": len(boundary_rows),
        "passed_boundary_count": passed_count,
        "blocking_boundary_count": blocking_count,
        "get_cache_api_direct_external_calls_allowed": False,
        "react_render_direct_provider_calls_allowed": False,
        "fastapi_startup_external_calls_allowed": False,
        "external_work_requires_post_task_worker_or_local_fallback": True,
        "call_ledger_required_for_provider_calls": True,
        "model_ledger_required_for_deepseek_calls": True,
        "deepseek_is_data_source": False,
        "deepseek_may_overwrite_price": False,
        "deepseek_may_overwrite_holding": False,
        "deepseek_may_overwrite_factor": False,
        "deepseek_may_overwrite_operation_zones": False,
        "deepseek_may_modify_strategy_action": False,
        "real_trading_allowed": False,
        "auto_order_allowed": False,
        "radar_candidate_is_buy_instruction": False,
        "token_key_frontend_log_packet_cache_allowed": False,
        "mock_receipt_matrix_sanitizer_are_production_evidence": False,
        "frontend_visible": True,
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "contract_creates_task": False,
        "contract_calls_provider_or_model": False,
        "contract_is_production_evidence": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _search_submit_autostart_effective_status(
    *,
    active_mode: str,
    configured_value: bool,
    effective_value: bool,
) -> tuple[str, str]:
    if effective_value:
        return "effective_in_live_light", ""
    if active_mode == "cache_only":
        return "cache_only_submit_autostart_disabled", "cache_only_read_only"
    if active_mode == "manual":
        return "manual_explicit_button_submit_autostart_disabled", "manual_requires_explicit_button"
    if active_mode == "live_full":
        return "live_full_reserved_submit_autostart_disabled", "live_full_reserved_requires_separate_authorization"
    if active_mode != "live_light":
        return "mode_gate_inactive_requires_live_light", "requires_live_light_mode"
    if not configured_value:
        return "source_switch_disabled", "source_switch_false"
    return "blocked_unexpected_source_switch_state", "source_switch_not_effective"


def _live_light_source_switch_effective_status(
    *,
    active_mode: str,
    configured_value: bool,
    effective_value: bool,
) -> tuple[str, str]:
    if effective_value:
        return "effective_in_live_light", ""
    if active_mode == "cache_only":
        return "cache_only_source_switch_disabled", "cache_only_read_only"
    if active_mode == "manual":
        return "manual_source_switch_disabled_explicit_task_only", "manual_requires_explicit_post_task"
    if active_mode == "live_full":
        return "live_full_source_switch_disabled_reserved", "live_full_reserved_requires_separate_authorization"
    if active_mode != "live_light":
        return "mode_gate_inactive_requires_live_light", "requires_live_light_mode"
    if not configured_value:
        return "source_switch_disabled", "source_switch_false"
    return "blocked_unexpected_source_switch_state", "source_switch_not_effective"


def _provider_linkage_rows(
    *,
    active_mode: str,
    live_light_enabled: bool,
    live_light_sources_enabled: bool,
    tushare_on_open: bool,
    deepseek_on_open: bool,
    symbol_limit: int,
    rate_limit_seconds: int,
    deepseek_model: str,
) -> list[dict[str, Any]]:
    live_light_tushare_planned = live_light_enabled and live_light_sources_enabled and tushare_on_open
    live_light_deepseek_planned = live_light_enabled and live_light_sources_enabled and deepseek_on_open
    return [
        {
            "schema_version": BOOTSTRAP_PROVIDER_LINKAGE_SCHEMA_VERSION,
            "linkage_key": "cache_startup_render_boundary",
            "surface": "GET cache / FastAPI startup / React initial render",
            "status": "offline_enforced",
            "mode": active_mode,
            "route": BOOTSTRAP_STATUS_ROUTE,
            "external_calls_allowed": False,
            "external_calls_triggered": False,
            "tushare_allowed": False,
            "deepseek_allowed": False,
            "github_allowed": False,
            "post_task_required": True,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "schema_version": BOOTSTRAP_PROVIDER_LINKAGE_SCHEMA_VERSION,
            "linkage_key": "live_light_bootstrap_task_boundary",
            "surface": "React mounted POST bootstrap task",
            "status": "available_after_cache_render" if live_light_enabled else "inactive_until_live_light",
            "mode": active_mode,
            "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "external_calls_allowed": live_light_sources_enabled,
            "external_calls_triggered": False,
            "post_task_required": True,
            "initial_cache_render_required": True,
            "rate_limit_seconds": rate_limit_seconds,
            "symbol_limit": symbol_limit,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "schema_version": BOOTSTRAP_PROVIDER_LINKAGE_SCHEMA_VERSION,
            "linkage_key": "tushare_light_refresh",
            "surface": "Tushare light refresh",
            "status": "planned_provider_pending_not_executed"
            if live_light_tushare_planned
            else ("skipped_by_config" if live_light_enabled else "skipped_mode_not_live_light"),
            "mode": active_mode,
            "provider": "tushare",
            "default_apis": list(DEFAULT_LIGHT_TUSHARE_APIS),
            "allowed_scope": "current_target_holdings_watchlist_light_only",
            "external_calls_allowed": live_light_tushare_planned,
            "external_calls_triggered": False,
            "tushare_called": False,
            "call_ledger_required": True,
            "request_params_safe_required": True,
            "safe_error_required": True,
            "token_key_exposure_allowed": False,
            "provider_execution_implemented": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "schema_version": BOOTSTRAP_PROVIDER_LINKAGE_SCHEMA_VERSION,
            "linkage_key": "deepseek_pro_after_task",
            "surface": "DeepSeek pro explanation after data readiness",
            "status": "planned_model_pending_not_executed"
            if live_light_deepseek_planned
            else ("skipped_by_config" if live_light_enabled else "skipped_mode_not_live_light"),
            "mode": active_mode,
            "provider": "deepseek",
            "model": deepseek_model,
            "external_calls_allowed": live_light_deepseek_planned,
            "external_calls_triggered": False,
            "deepseek_called": False,
            "model_called": False,
            "model_ledger_required": True,
            "allowed_output_fields": list(DEEPSEEK_EXPLANATION_FIELDS),
            "sanitizer_required": True,
            "parse_failed_discard_required": True,
            "model_execution_implemented": False,
            "does_not_overwrite_numeric_fields": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "schema_version": BOOTSTRAP_PROVIDER_LINKAGE_SCHEMA_VERSION,
            "linkage_key": "github_probe_boundary",
            "surface": "GitHub probe",
            "status": "manual_or_explicit_task_only",
            "mode": active_mode,
            "external_calls_allowed": False,
            "external_calls_triggered": False,
            "github_called": False,
            "live_light_on_open_allowed": False,
            "post_task_required": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "schema_version": BOOTSTRAP_PROVIDER_LINKAGE_SCHEMA_VERSION,
            "linkage_key": "real_trading_boundary",
            "surface": "broker / order / real trading",
            "status": "disconnected",
            "mode": active_mode,
            "external_calls_allowed": False,
            "external_calls_triggered": False,
            "real_trading_connected": False,
            "order_endpoint_present": False,
            "trade_execution_api_enabled": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
    ]


def _activation_receipt_row(criterion: str, status: str, evidence: str, *, passed: bool) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_ACTIVATION_RECEIPT_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_activation_receipt(
    *,
    active_mode: str,
    mode_valid: bool,
    live_light_enabled: bool,
    live_light_sources_enabled: bool,
    tushare_on_open: bool,
    deepseek_on_open: bool,
    symbol_limit: int,
    rate_limit_seconds: int,
    provider_linkage_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    linkage = {str(row.get("linkage_key") or ""): row for row in provider_linkage_rows}
    cache_boundary = linkage.get("cache_startup_render_boundary", {})
    task_boundary = linkage.get("live_light_bootstrap_task_boundary", {})
    github_boundary = linkage.get("github_probe_boundary", {})
    trading_boundary = linkage.get("real_trading_boundary", {})
    rows = [
        _activation_receipt_row(
            "mode_layering_visible",
            "passed" if mode_valid and active_mode in BOOTSTRAP_MODES else "blocked_invalid_mode",
            f"mode={active_mode}; live_light_enabled={live_light_enabled}",
            passed=mode_valid and active_mode in BOOTSTRAP_MODES,
        ),
        _activation_receipt_row(
            "cache_render_boundary_enforced",
            "passed"
            if cache_boundary.get("status") == "offline_enforced"
            and cache_boundary.get("external_calls_allowed") is False
            else "blocked_cache_boundary",
            "GET cache, FastAPI startup, and React initial render stay provider/model/GitHub silent.",
            passed=cache_boundary.get("status") == "offline_enforced"
            and cache_boundary.get("external_calls_allowed") is False,
        ),
        _activation_receipt_row(
            "post_task_boundary_visible",
            "passed"
            if task_boundary.get("route") == PLANNED_BOOTSTRAP_TASK_ROUTE
            and task_boundary.get("post_task_required") is True
            else "blocked_post_task_boundary",
            f"route={task_boundary.get('route')}; sources_enabled={live_light_sources_enabled}",
            passed=task_boundary.get("route") == PLANNED_BOOTSTRAP_TASK_ROUTE
            and task_boundary.get("post_task_required") is True,
        ),
        _activation_receipt_row(
            "tushare_stage_requires_provider_adapter",
            "pending_provider_execution_implementation",
            "Light Tushare is mode-gated and planned, but provider execution and real call ledger evidence are still pending.",
            passed=False,
        ),
        _activation_receipt_row(
            "deepseek_stage_requires_model_execution_gate",
            "pending_model_execution_implementation",
            "DeepSeek pro is optional after data readiness, but model execution, input hash dedupe, and model ledger evidence are still pending.",
            passed=False,
        ),
        _activation_receipt_row(
            "rate_limit_and_symbol_cap_visible",
            "passed" if symbol_limit > 0 and rate_limit_seconds >= 60 else "blocked_rate_limit_or_symbol_cap",
            f"symbol_limit={symbol_limit}; rate_limit_seconds={rate_limit_seconds}",
            passed=symbol_limit > 0 and rate_limit_seconds >= 60,
        ),
        _activation_receipt_row(
            "safe_ledger_required",
            "passed",
            "Provider calls require call_ledger; model calls require model_ledger, safe errors, and hash evidence.",
            passed=True,
        ),
        _activation_receipt_row(
            "github_probe_excluded_from_live_light",
            "passed" if github_boundary.get("live_light_on_open_allowed") is False else "blocked_github_probe_on_open",
            "GitHub probe remains manual/explicit task only and is not part of live_light startup.",
            passed=github_boundary.get("live_light_on_open_allowed") is False,
        ),
        _activation_receipt_row(
            "real_trading_disconnected",
            "passed" if trading_boundary.get("real_trading_connected") is False else "blocked_real_trading_connected",
            "Broker/order/trading chain is disconnected from live_light bootstrap.",
            passed=trading_boundary.get("real_trading_connected") is False,
        ),
        _activation_receipt_row(
            "full_pool_reserved",
            "passed",
            "live_full/full-pool/deep-scan remains reserved and cannot be enabled by page render.",
            passed=True,
        ),
        _activation_receipt_row(
            "token_key_frontend_exposure_blocked",
            "passed",
            "Status cache exposes only safe config keys/flags; token/key values are not read or returned.",
            passed=True,
        ),
        _activation_receipt_row(
            "production_activation_pending",
            "blocked_until_explicit_provider_and_model_acceptance",
            "Production live_light requires explicit provider execution, real call ledger/model ledger, browser-safe UI evidence, and promotion review.",
            passed=False,
        ),
    ]
    blocking_count = sum(1 for row in rows if not row.get("passed"))
    receipt = {
        "schema_version": BOOTSTRAP_ACTIVATION_RECEIPT_SCHEMA_VERSION,
        "status": "live_light_activation_receipt_ready_execution_blocked",
        "scope": "local_live_light_activation_receipt_no_provider_or_model_execution",
        "local_activation_receipt_ready": True,
        "mode": active_mode,
        "live_light_enabled": live_light_enabled,
        "tushare_on_open": bool(tushare_on_open and live_light_enabled),
        "deepseek_on_open": bool(deepseek_on_open and live_light_enabled),
        "allowed_next_step": "explicit_live_light_provider_model_acceptance_design_then_user_approved_task_execution",
        "not_allowed_next_steps": [
            "GET cache provider/model execution",
            "React render direct provider/model call",
            "GitHub probe on live_light open",
            "real trading integration",
            "full-pool/deep-scan on open",
            "treat skeleton/linkage rows as provider execution",
            "treat activation receipt as production completion",
        ],
        "missing_evidence_items": [
            "provider_execution_implementation",
            "real Tushare call ledger for allowed light APIs",
            "DeepSeek model execution gate and model ledger evidence",
            "provider-backed acceptance results",
            "browser/runtime evidence for non-blocking task behavior",
        ],
        "ready_for_provider_execution_design": True,
        "ready_for_provider_execution": False,
        "ready_for_model_execution": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "activation_row_count": len(rows),
        "blocking_criterion_count": blocking_count,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_live_light_activation_receipt",
                "endpoint": BOOTSTRAP_STATUS_ROUTE,
                "row_count": len(rows),
                "blocking_criterion_count": blocking_count,
                "call_status": "local_activation_receipt_ready_execution_blocked",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
    }
    return receipt, rows


def _acceptance_runbook_row(
    *,
    order: int,
    phase_key: str,
    label: str,
    stage_kind: str,
    status: str,
    required_evidence: list[str],
    acceptance_gate: str,
    external_call_expected_when_executed: bool,
    provider: str = "local",
    apis: list[str] | None = None,
    passed: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_ACCEPTANCE_RUNBOOK_SCHEMA_VERSION,
        "order": order,
        "phase_key": phase_key,
        "label": label,
        "stage_kind": stage_kind,
        "provider": provider,
        "apis": apis or [],
        "status": status,
        "passed": bool(passed),
        "acceptance_gate": acceptance_gate,
        "required_evidence": list(required_evidence),
        "external_call_expected_when_executed": bool(external_call_expected_when_executed),
        "external_calls_triggered_by_runbook": False,
        "tushare_called_by_runbook": False,
        "deepseek_called_by_runbook": False,
        "github_called_by_runbook": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_provider_model_acceptance_runbook(
    *,
    active_mode: str,
    live_light_enabled: bool,
    tushare_on_open: bool,
    deepseek_on_open: bool,
    symbol_limit: int,
    rate_limit_seconds: int,
    deepseek_model: str,
    activation_receipt: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = [
        _acceptance_runbook_row(
            order=1,
            phase_key="mode_and_scope_preflight",
            label="confirm live_light mode, symbol cap, rate limit, and bounded scope",
            stage_kind="local_preflight",
            provider="FastAPI bootstrap status",
            status="passed_local_contract_visible",
            passed=True,
            required_evidence=[
                "mode visible",
                "symbol_limit visible",
                "rate_limit_seconds visible",
                "current target / holdings / watchlist scope only",
            ],
            acceptance_gate="local_contract_before_provider_execution",
            external_call_expected_when_executed=False,
        ),
        _acceptance_runbook_row(
            order=2,
            phase_key="explicit_user_approval_required",
            label="require explicit user approval before the first provider/model acceptance run",
            stage_kind="manual_gate",
            status="pending_user_approved_acceptance_run",
            required_evidence=[
                "user-approved task payload",
                "selected symbols",
                "selected provider/model switches",
                "acknowledged cost/rate-limit boundary",
            ],
            acceptance_gate="manual_approval_required",
            external_call_expected_when_executed=False,
        ),
        _acceptance_runbook_row(
            order=3,
            phase_key="server_secret_preflight",
            label="check server-side provider/model credential presence without exposing values",
            stage_kind="server_preflight",
            status="pending_secret_presence_check",
            required_evidence=[
                "credential present/absent boolean only",
                "no token/key value in response",
                "safe error when missing",
            ],
            acceptance_gate="server_only_secret_boundary",
            external_call_expected_when_executed=False,
        ),
        _acceptance_runbook_row(
            order=4,
            phase_key="tushare_trade_cal_acceptance_sample",
            label="run trade_cal if needed and record freshness evidence",
            stage_kind="provider",
            provider="tushare",
            apis=["trade_cal"],
            status="pending_provider_execution",
            required_evidence=[
                "call_ledger api/provider/request_params_safe",
                "row_count",
                "data_date or calendar window",
                "local_fetched_at",
                "call_status",
                "error_message_safe",
                "freshness expected_trade_date evidence",
            ],
            acceptance_gate="provider_call_ledger_required",
            external_call_expected_when_executed=True,
        ),
        _acceptance_runbook_row(
            order=5,
            phase_key="tushare_light_fact_acceptance_sample",
            label="run daily / daily_basic / moneyflow for bounded symbols",
            stage_kind="provider",
            provider="tushare",
            apis=["daily", "daily_basic", "moneyflow"],
            status="pending_provider_execution",
            required_evidence=[
                "one call_ledger row per selected API",
                "permission denied / no record / empty window / parse error separated",
                "no unselected API marked verified",
                "token redaction proof",
            ],
            acceptance_gate="provider_failure_modes_required",
            external_call_expected_when_executed=True,
        ),
        _acceptance_runbook_row(
            order=6,
            phase_key="local_factor_next_session_refresh",
            label="refresh Factor Quant Hub and Next Session cache from prepared evidence",
            stage_kind="local_pipeline",
            provider="local cache pipeline",
            status="pending_local_pipeline_after_provider",
            required_evidence=[
                "factor light runtime status",
                "next-session cache status",
                "freshness state propagation",
                "no strategy action mutation",
            ],
            acceptance_gate="local_pipeline_receipt_required",
            external_call_expected_when_executed=False,
        ),
        _acceptance_runbook_row(
            order=7,
            phase_key="deepseek_pro_model_acceptance_sample",
            label="run optional DeepSeek pro explanation after data readiness",
            stage_kind="model",
            provider="deepseek",
            status="pending_model_execution",
            required_evidence=[
                f"model_used={deepseek_model}",
                "input_hash",
                "output_hash",
                "token_usage",
                "parse_status",
                "six-field sanitizer result",
                "parse_failed discard proof",
            ],
            acceptance_gate="model_ledger_required",
            external_call_expected_when_executed=True,
        ),
        _acceptance_runbook_row(
            order=8,
            phase_key="ui_nonblocking_runtime_acceptance",
            label="prove UI renders from cache first and task failure stays safe",
            stage_kind="frontend_runtime",
            provider="React/FastAPI",
            status="pending_browser_or_runtime_evidence",
            required_evidence=[
                "cache first render visible",
                "task_id displayed",
                "polling visible",
                "rate-limit skipped state",
                "safe error display",
            ],
            acceptance_gate="browser_runtime_evidence_required",
            external_call_expected_when_executed=False,
        ),
        _acceptance_runbook_row(
            order=9,
            phase_key="ledger_redaction_safety_review",
            label="review call/model ledger redaction and action/trade boundaries",
            stage_kind="promotion_review",
            status="pending_safety_review",
            required_evidence=[
                "no token/key in packet/cache/log/frontend",
                "DeepSeek not data source",
                "no numeric/action overwrite",
                "no broker/order path",
            ],
            acceptance_gate="safety_review_required",
            external_call_expected_when_executed=False,
        ),
        _acceptance_runbook_row(
            order=10,
            phase_key="production_promotion_review",
            label="promote live_light only after provider/model/browser evidence is complete",
            stage_kind="promotion_review",
            status="blocked_until_all_acceptance_evidence_present",
            required_evidence=[
                "provider-backed Tushare sample evidence",
                "DeepSeek model ledger evidence",
                "UI non-blocking evidence",
                "secret scan clean",
                "push gate green",
                "explicit user promotion approval",
            ],
            acceptance_gate="production_promotion_blocked",
            external_call_expected_when_executed=False,
        ),
    ]
    runbook = {
        "schema_version": BOOTSTRAP_ACCEPTANCE_RUNBOOK_SCHEMA_VERSION,
        "status": "live_light_provider_model_acceptance_runbook_ready_execution_pending",
        "scope": "local_runbook_no_provider_or_model_execution",
        "mode": active_mode,
        "local_runbook_ready": True,
        "activation_receipt_status": activation_receipt.get("status"),
        "live_light_enabled": live_light_enabled,
        "tushare_on_open": bool(tushare_on_open and live_light_enabled),
        "deepseek_on_open": bool(deepseek_on_open and live_light_enabled),
        "default_light_tushare_apis": list(DEFAULT_LIGHT_TUSHARE_APIS),
        "symbol_limit": symbol_limit,
        "rate_limit_seconds": rate_limit_seconds,
        "deepseek_model": deepseek_model,
        "ready_for_acceptance_design": True,
        "ready_for_user_approved_acceptance_task": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_live_light_complete": False,
        "allowed_next_step": "implement_explicit_provider_model_acceptance_task_then_user_approved_real_run",
        "not_allowed_next_steps": [
            "GET bootstrap status provider/model execution",
            "React render provider/model execution",
            "credential value exposure",
            "GitHub probe as live_light startup",
            "real trading integration",
            "full-pool/deep-scan startup",
            "runbook as provider/model acceptance evidence",
            "runbook as production completion",
        ],
        "missing_evidence_items": [
            "server-side secret presence preflight result",
            "real Tushare provider call ledger",
            "real DeepSeek model ledger",
            "non-blocking browser/runtime evidence",
            "promotion review evidence",
        ],
        "phase_count": len(rows),
        "provider_phase_count": sum(1 for row in rows if row["stage_kind"] == "provider"),
        "model_phase_count": sum(1 for row in rows if row["stage_kind"] == "model"),
        "external_call_expected_phase_count": sum(1 for row in rows if row["external_call_expected_when_executed"]),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_live_light_provider_model_acceptance_runbook",
                "endpoint": BOOTSTRAP_STATUS_ROUTE,
                "row_count": len(rows),
                "provider_phase_count": sum(1 for row in rows if row["stage_kind"] == "provider"),
                "model_phase_count": sum(1 for row in rows if row["stage_kind"] == "model"),
                "call_status": "local_runbook_ready_execution_pending",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
    }
    return runbook, rows


def _acceptance_dry_run_status(
    *,
    phase_key: str,
    stage_kind: str,
    payload_safe: dict[str, Any],
) -> tuple[str, bool]:
    selected_apis = set(payload_safe.get("selected_apis") or [])
    include_deepseek = payload_safe.get("include_deepseek") is True
    if phase_key == "mode_and_scope_preflight":
        return "dry_run_passed_local_scope_visible", True
    if phase_key == "explicit_user_approval_required":
        if payload_safe.get("user_approved") is True:
            return "dry_run_user_approval_recorded_no_execution", True
        return "dry_run_blocked_user_approval_required", False
    if phase_key == "server_secret_preflight":
        presence = _dict(payload_safe.get("credential_presence_summary"))
        if int(presence.get("required_provider_count") or 0) == 0:
            return "dry_run_secret_presence_not_required_no_values_read", True
        if int(presence.get("missing_provider_count") or 0) == 0:
            return "dry_run_secret_presence_checked_no_values_exposed", True
        return "dry_run_secret_presence_missing_no_values_exposed", False
    if phase_key == "tushare_trade_cal_acceptance_sample":
        if "trade_cal" in selected_apis:
            return "dry_run_ready_provider_execution_not_called", False
        return "dry_run_skipped_api_not_selected", True
    if phase_key == "tushare_light_fact_acceptance_sample":
        if selected_apis.intersection({"daily", "daily_basic", "moneyflow"}):
            return "dry_run_ready_provider_execution_not_called", False
        return "dry_run_skipped_api_not_selected", True
    if phase_key == "local_factor_next_session_refresh":
        return "dry_run_ready_local_pipeline_after_provider", False
    if phase_key == "deepseek_pro_model_acceptance_sample":
        if include_deepseek:
            return "dry_run_ready_model_execution_not_called", False
        return "dry_run_skipped_model_not_selected", True
    if phase_key == "ui_nonblocking_runtime_acceptance":
        return "dry_run_ready_browser_runtime_evidence_required", False
    if phase_key == "ledger_redaction_safety_review":
        return "dry_run_ready_safety_review_required", False
    if phase_key == "production_promotion_review":
        return "dry_run_blocked_until_real_provider_model_browser_evidence", False
    if stage_kind in {"provider", "model"}:
        return "dry_run_pending_execution_not_called", False
    return "dry_run_ready", True


def _build_acceptance_dry_run(
    *,
    status_packet: dict[str, Any],
    payload_safe: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    runbook = _dict(status_packet.get("live_light_provider_model_acceptance_runbook"))
    runbook_rows = [row for row in _list(status_packet.get("live_light_provider_model_acceptance_rows")) if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    for row in runbook_rows:
        phase_key = str(row.get("phase_key") or "")
        stage_kind = str(row.get("stage_kind") or "")
        status, passed = _acceptance_dry_run_status(
            phase_key=phase_key,
            stage_kind=stage_kind,
            payload_safe=payload_safe,
        )
        rows.append(
            {
                "schema_version": BOOTSTRAP_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
                "order": row.get("order"),
                "phase_key": phase_key,
                "label": row.get("label"),
                "stage_kind": stage_kind,
                "provider": row.get("provider"),
                "apis": row.get("apis") or [],
                "selected_for_dry_run": (
                    phase_key not in {"tushare_trade_cal_acceptance_sample", "tushare_light_fact_acceptance_sample", "deepseek_pro_model_acceptance_sample"}
                    or (phase_key == "tushare_trade_cal_acceptance_sample" and "trade_cal" in set(payload_safe.get("selected_apis") or []))
                    or (phase_key == "tushare_light_fact_acceptance_sample" and bool(set(payload_safe.get("selected_apis") or []).intersection({"daily", "daily_basic", "moneyflow"})))
                    or (phase_key == "deepseek_pro_model_acceptance_sample" and payload_safe.get("include_deepseek") is True)
                ),
                "status": status,
                "passed": passed,
                "acceptance_gate": row.get("acceptance_gate"),
                "required_evidence": row.get("required_evidence") or [],
                "credential_presence_summary": payload_safe.get("credential_presence_summary")
                if phase_key == "server_secret_preflight"
                else None,
                "external_call_expected_when_executed": bool(row.get("external_call_expected_when_executed")),
                "external_calls_triggered_by_dry_run": False,
                "tushare_called_by_dry_run": False,
                "deepseek_called_by_dry_run": False,
                "github_called_by_dry_run": False,
                "provider_execution_implemented": False,
                "model_execution_implemented": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    blocking_rows = [row for row in rows if row.get("passed") is False]
    selected_provider_rows = [
        row
        for row in rows
        if row.get("stage_kind") == "provider" and row.get("selected_for_dry_run") is True
    ]
    selected_model_rows = [
        row
        for row in rows
        if row.get("stage_kind") == "model" and row.get("selected_for_dry_run") is True
    ]
    credential_presence = _dict(payload_safe.get("credential_presence_summary"))
    credential_missing_count = int(credential_presence.get("missing_provider_count") or 0)
    user_approved = payload_safe.get("user_approved") is True
    if not user_approved:
        status = "acceptance_dry_run_blocked_user_approval_required"
    elif credential_missing_count:
        status = "acceptance_dry_run_blocked_missing_credentials"
    else:
        status = "acceptance_dry_run_ready_execution_pending"
    if not user_approved:
        allowed_next_step = "submit_dry_run_with_explicit_user_approval"
        missing_evidence = ["explicit user approval"]
    elif credential_missing_count:
        allowed_next_step = "configure_server_credentials_then_rerun_dry_run"
        missing_evidence = ["server credential presence for selected providers"]
    else:
        allowed_next_step = "explicit_user_confirmed_real_provider_model_acceptance_task_pending_implementation"
        missing_evidence = [
            "real provider call ledger",
            "real model ledger",
            "browser/runtime nonblocking evidence",
            "ledger redaction safety review",
            "production promotion review",
        ]
    summary = {
        "schema_version": BOOTSTRAP_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
        "status": status,
        "scope": "local_provider_model_acceptance_dry_run_no_external_call",
        "mode": status_packet.get("mode"),
        "runbook_status": runbook.get("status"),
        "acceptance_scope_ticket": payload_safe.get("acceptance_scope_ticket"),
        "acceptance_scope_hash": _dict(payload_safe.get("acceptance_scope_ticket")).get("scope_hash"),
        "acceptance_scope_hash_short": _dict(payload_safe.get("acceptance_scope_ticket")).get("scope_hash_short"),
        "acceptance_scope_hash_algorithm": _dict(payload_safe.get("acceptance_scope_ticket")).get("scope_hash_algorithm"),
        "user_approved": user_approved,
        "selected_apis": payload_safe.get("selected_apis") or [],
        "ignored_apis": payload_safe.get("ignored_apis") or [],
        "include_tushare": payload_safe.get("include_tushare") is True,
        "include_deepseek": payload_safe.get("include_deepseek") is True,
        "symbol_count": payload_safe.get("symbol_count"),
        "credential_presence_status": credential_presence.get("status"),
        "credential_required_provider_count": credential_presence.get("required_provider_count", 0),
        "credential_present_provider_count": credential_presence.get("present_provider_count", 0),
        "credential_missing_provider_count": credential_missing_count,
        "blocked_by_missing_credentials": bool(credential_missing_count),
        "credential_presence_checked_without_value_exposure": True,
        "credential_values_read": False,
        "credential_values_exposed": False,
        "phase_count": len(rows),
        "selected_provider_phase_count": len(selected_provider_rows),
        "selected_model_phase_count": len(selected_model_rows),
        "blocking_phase_count": len(blocking_rows),
        "ready_for_user_approved_real_acceptance": user_approved and not credential_missing_count,
        "allowed_next_step": allowed_next_step,
        "missing_evidence_items": missing_evidence,
        "not_allowed_next_steps": [
            "GET cache provider/model execution",
            "React render provider/model execution",
            "skip credential presence gate",
            "skip explicit user confirmation",
            "promote dry-run to provider-backed acceptance",
            "write token/key material to frontend/log/packet/cache",
            "execute real trades or mutate strategy action",
        ],
        "real_acceptance_task_implemented": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    return summary, rows


def _real_acceptance_preflight_row(
    criterion: str,
    status: str,
    evidence: str,
    *,
    passed: bool,
    blocks_real_execution: bool,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_REAL_ACCEPTANCE_PREFLIGHT_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "blocks_real_execution": bool(blocks_real_execution),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _real_acceptance_preflight_receipt(
    *,
    payload_safe: dict[str, Any],
    summary: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scope_ticket = _dict(payload_safe.get("acceptance_scope_ticket"))
    selected_apis = list(payload_safe.get("selected_apis") or [])
    ignored_apis = list(payload_safe.get("ignored_apis") or [])
    user_approved = payload_safe.get("user_approved") is True
    credentials_ready = int(summary.get("credential_missing_provider_count") or 0) == 0
    dry_run_ready = summary.get("ready_for_user_approved_real_acceptance") is True
    rows = [
        _real_acceptance_preflight_row(
            "scope_ticket_binds_user_confirmation",
            "passed" if scope_ticket.get("scope_hash") and scope_ticket.get("env_key_names_included") is False else "blocked_missing_scope_ticket",
            f"scope_hash_short={scope_ticket.get('scope_hash_short')}; field_count={scope_ticket.get('scope_hash_input_field_count')}",
            passed=bool(scope_ticket.get("scope_hash")) and scope_ticket.get("env_key_names_included") is False,
            blocks_real_execution=not bool(scope_ticket.get("scope_hash")),
        ),
        _real_acceptance_preflight_row(
            "explicit_user_approval_recorded",
            "passed" if user_approved else "blocked_user_approval_required",
            f"user_approved={user_approved}",
            passed=user_approved,
            blocks_real_execution=not user_approved,
        ),
        _real_acceptance_preflight_row(
            "credential_presence_ready_without_value_exposure",
            "passed" if credentials_ready else "blocked_missing_server_credentials",
            f"credential_presence_status={summary.get('credential_presence_status')}; missing={summary.get('credential_missing_provider_count')}",
            passed=credentials_ready,
            blocks_real_execution=not credentials_ready,
        ),
        _real_acceptance_preflight_row(
            "allowed_light_scope_only",
            "passed" if all(api in ACCEPTANCE_DRY_RUN_ALLOWED_APIS for api in selected_apis) else "blocked_unexpected_api",
            f"selected_apis={selected_apis}; ignored_apis={ignored_apis}; symbol_count={summary.get('symbol_count')}",
            passed=all(api in ACCEPTANCE_DRY_RUN_ALLOWED_APIS for api in selected_apis),
            blocks_real_execution=not all(api in ACCEPTANCE_DRY_RUN_ALLOWED_APIS for api in selected_apis),
        ),
        _real_acceptance_preflight_row(
            "provider_execution_task_not_implemented",
            "blocked_real_tushare_execution_pending",
            "Real Tushare provider execution still needs a separate explicit task with provider call ledger evidence.",
            passed=False,
            blocks_real_execution=True,
        ),
        _real_acceptance_preflight_row(
            "model_execution_task_not_implemented",
            "blocked_real_deepseek_execution_pending",
            "Real DeepSeek pro execution still needs model ledger, input/output hash, parse status, and sanitizer evidence.",
            passed=False,
            blocks_real_execution=True,
        ),
        _real_acceptance_preflight_row(
            "browser_nonblocking_evidence_missing",
            "blocked_browser_runtime_evidence_pending",
            "Need browser/runtime proof that cache renders first, task polling is visible, failures are safe, and UI is not blocked.",
            passed=False,
            blocks_real_execution=True,
        ),
        _real_acceptance_preflight_row(
            "ledger_redaction_review_pending",
            "blocked_ledger_redaction_review_pending",
            "Need final review that call/model ledger, packet, cache, frontend, and logs contain no token/key material.",
            passed=False,
            blocks_real_execution=True,
        ),
        _real_acceptance_preflight_row(
            "production_promotion_not_allowed",
            "blocked_until_provider_model_browser_promotion_review",
            "Dry-run readiness is not provider-backed acceptance and not production live_light completion.",
            passed=False,
            blocks_real_execution=True,
        ),
        _real_acceptance_preflight_row(
            "trade_action_boundary_enforced",
            "passed",
            "Real acceptance preflight cannot execute trades or mutate strategy action.",
            passed=True,
            blocks_real_execution=False,
        ),
    ]
    blocking_rows = [row for row in rows if row.get("blocks_real_execution") is True]
    receipt = {
        "schema_version": BOOTSTRAP_REAL_ACCEPTANCE_PREFLIGHT_SCHEMA_VERSION,
        "status": "real_acceptance_preflight_blocked_execution_not_implemented"
        if dry_run_ready
        else "real_acceptance_preflight_blocked_dry_run_not_ready",
        "scope": "local_real_acceptance_preflight_receipt_no_provider_or_model_execution",
        "dry_run_status": summary.get("status"),
        "dry_run_ready_for_user_approved_real_acceptance": dry_run_ready,
        "acceptance_scope_hash": summary.get("acceptance_scope_hash"),
        "acceptance_scope_hash_short": summary.get("acceptance_scope_hash_short"),
        "selected_apis": selected_apis,
        "ignored_apis": ignored_apis,
        "include_tushare": payload_safe.get("include_tushare") is True,
        "include_deepseek": payload_safe.get("include_deepseek") is True,
        "allowed_next_step": "implement_real_provider_model_acceptance_task_then_run_user_confirmed_scope"
        if dry_run_ready
        else summary.get("allowed_next_step"),
        "not_allowed_next_steps": [
            "treat dry-run receipt as provider-backed acceptance",
            "execute provider/model without a separate explicit real task",
            "skip browser nonblocking evidence",
            "skip ledger redaction review",
            "promote live_light production before provider/model/browser evidence",
            "execute real trades or mutate strategy action",
        ],
        "missing_evidence_items": [
            "real Tushare provider call ledger",
            "real DeepSeek model ledger",
            "browser/runtime nonblocking evidence",
            "ledger redaction safety review",
            "production promotion review",
        ],
        "local_receipt_ready": True,
        "ready_to_design_real_task": dry_run_ready,
        "ready_to_execute_real_task": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "browser_runtime_evidence_complete": False,
        "ledger_redaction_review_complete": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_count": len(rows),
        "blocking_row_count": len(blocking_rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_live_light_real_acceptance_preflight_receipt",
                "endpoint": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
                "row_count": len(rows),
                "blocking_row_count": len(blocking_rows),
                "acceptance_scope_hash_short": summary.get("acceptance_scope_hash_short"),
                "call_status": "local_real_acceptance_preflight_blocked_no_external_call",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
    }
    return receipt, rows


def _acceptance_dry_run_call_ledger(
    *,
    payload_safe: dict[str, Any],
    summary: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    missing_credentials = int(summary.get("credential_missing_provider_count") or 0)
    return {
        "api": "local_live_light_provider_model_acceptance_dry_run",
        "endpoint": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
        "request_params_safe": {
            "source": payload_safe.get("source"),
            "requested_by": payload_safe.get("requested_by"),
            "user_approved": payload_safe.get("user_approved"),
            "symbol_count": payload_safe.get("symbol_count"),
            "symbol_limit": payload_safe.get("symbol_limit"),
            "selected_apis": payload_safe.get("selected_apis"),
            "ignored_apis": payload_safe.get("ignored_apis"),
            "include_tushare": payload_safe.get("include_tushare"),
            "include_deepseek": payload_safe.get("include_deepseek"),
            "credential_required_provider_count": summary.get("credential_required_provider_count"),
            "credential_present_provider_count": summary.get("credential_present_provider_count"),
            "credential_missing_provider_count": summary.get("credential_missing_provider_count"),
            "acceptance_scope_hash_short": summary.get("acceptance_scope_hash_short"),
        },
        "row_count": int(summary.get("phase_count") or 0),
        "selected_provider_phase_count": int(summary.get("selected_provider_phase_count") or 0),
        "selected_model_phase_count": int(summary.get("selected_model_phase_count") or 0),
        "blocking_phase_count": int(summary.get("blocking_phase_count") or 0),
        "local_fetched_at": now,
        "call_status": "local_acceptance_dry_run_blocked_missing_credentials_no_external_call"
        if missing_credentials
        else "local_acceptance_dry_run_recorded_no_external_call",
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _latest_acceptance_dry_run_task(requested_scope_hash: str = "") -> dict[str, Any] | None:
    tasks = [
        task
        for task in task_service.list_task_statuses()
        if task.get("task_type") == BOOTSTRAP_ACCEPTANCE_DRY_RUN_TASK_TYPE
    ]
    if requested_scope_hash:
        for task in tasks:
            payload = _dict(task.get("payload_safe"))
            summary = _dict(payload.get("acceptance_dry_run_summary"))
            if str(summary.get("acceptance_scope_hash") or "") == requested_scope_hash:
                return task
    return tasks[0] if tasks else None


def _latest_acceptance_dry_run_status_surface() -> dict[str, Any]:
    latest_task = _latest_acceptance_dry_run_task()
    if latest_task is None:
        return {
            "schema_version": BOOTSTRAP_LATEST_ACCEPTANCE_DRY_RUN_STATUS_SCHEMA_VERSION,
            "status": "no_acceptance_dry_run_receipt_task_found",
            "lookup_source": "task_service.list_task_statuses",
            "lookup_creates_task": False,
            "route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
            "route_implemented": True,
            "receipt_found": False,
            "task_id": "",
            "task_status": "",
            "current_step": "",
            "output_packet_key": "",
            "storage_source": "",
            "durable_receipt_visible": False,
            "memory_only_receipt_is_durable_evidence": False,
            "receipt_status": "",
            "acceptance_scope_hash_short": "",
            "acceptance_scope_hash_algorithm": "",
            "user_approved": False,
            "selected_apis": [],
            "ignored_apis": [],
            "include_tushare": False,
            "include_deepseek": False,
            "credential_presence_status": "",
            "credential_preflight_ready": False,
            "credential_required_provider_count": 0,
            "credential_present_provider_count": 0,
            "credential_missing_provider_count": 0,
            "dry_run_ready_for_execution_request": False,
            "ready_for_user_approved_real_acceptance": False,
            "blocking_phase_count": 0,
            "selected_provider_phase_count": 0,
            "selected_model_phase_count": 0,
            "real_acceptance_preflight_status": "",
            "real_acceptance_preflight_ready_to_execute": False,
            "provider_model_task_created": False,
            "provider_model_task_dispatched": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "provider_model_execution_implemented": False,
            "production_live_light_complete": False,
            "is_production_evidence": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "contains_secret": False,
            "credential_values_exposed": False,
            "env_key_names_included": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_prices_positions_or_operation_zones": True,
        }

    payload = _dict(latest_task.get("payload_safe"))
    summary = _dict(payload.get("acceptance_dry_run_summary"))
    scope_ticket = _dict(payload.get("acceptance_scope_ticket"))
    storage_source = str(latest_task.get("storage_source") or "")
    durable_receipt_visible = storage_source in {"memory_and_sqlite", "sqlite_meta"}
    dry_run_ready = summary.get("ready_for_user_approved_real_acceptance") is True
    credential_missing_count = int(summary.get("credential_missing_provider_count") or 0)
    credential_ready = credential_missing_count == 0
    return {
        "schema_version": BOOTSTRAP_LATEST_ACCEPTANCE_DRY_RUN_STATUS_SCHEMA_VERSION,
        "status": "latest_acceptance_dry_run_receipt_visible_ready"
        if dry_run_ready
        else "latest_acceptance_dry_run_receipt_visible_blocked",
        "lookup_source": "task_service.list_task_statuses",
        "lookup_creates_task": False,
        "route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
        "route_implemented": True,
        "receipt_found": True,
        "task_id": latest_task.get("task_id"),
        "task_status": latest_task.get("status"),
        "current_step": latest_task.get("current_step"),
        "output_packet_key": latest_task.get("output_packet_key"),
        "storage_source": storage_source,
        "durable_receipt_visible": durable_receipt_visible,
        "memory_only_receipt_is_durable_evidence": False,
        "receipt_status": summary.get("status"),
        "acceptance_scope_hash_short": summary.get("acceptance_scope_hash_short")
        or scope_ticket.get("scope_hash_short"),
        "acceptance_scope_hash_algorithm": summary.get("acceptance_scope_hash_algorithm")
        or scope_ticket.get("scope_hash_algorithm"),
        "user_approved": payload.get("user_approved") is True,
        "selected_apis": list(payload.get("selected_apis") or []),
        "ignored_apis": list(payload.get("ignored_apis") or []),
        "include_tushare": payload.get("include_tushare") is True,
        "include_deepseek": payload.get("include_deepseek") is True,
        "credential_presence_status": summary.get("credential_presence_status"),
        "credential_preflight_ready": credential_ready,
        "credential_required_provider_count": int(summary.get("credential_required_provider_count") or 0),
        "credential_present_provider_count": int(summary.get("credential_present_provider_count") or 0),
        "credential_missing_provider_count": credential_missing_count,
        "dry_run_ready_for_execution_request": dry_run_ready,
        "ready_for_user_approved_real_acceptance": dry_run_ready,
        "blocking_phase_count": int(summary.get("blocking_phase_count") or 0),
        "selected_provider_phase_count": int(summary.get("selected_provider_phase_count") or 0),
        "selected_model_phase_count": int(summary.get("selected_model_phase_count") or 0),
        "real_acceptance_preflight_status": summary.get("real_acceptance_preflight_receipt_status"),
        "real_acceptance_preflight_ready_to_execute": summary.get("real_acceptance_preflight_ready_to_execute")
        is True,
        "provider_model_task_created": False,
        "provider_model_task_dispatched": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "provider_model_execution_implemented": False,
        "production_live_light_complete": False,
        "is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _execution_request_row(
    criterion: str,
    status: str,
    evidence: str,
    *,
    passed: bool,
    local_blocker: bool = False,
    production_blocker: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_EXECUTION_REQUEST_SCHEMA_VERSION,
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "local_blocker": bool(local_blocker),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _build_execution_request_receipt(
    *,
    payload_safe: dict[str, Any],
    latest_dry_run_task: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    latest_payload = _dict(latest_dry_run_task.get("payload_safe")) if latest_dry_run_task else {}
    latest_summary = _dict(latest_payload.get("acceptance_dry_run_summary"))
    latest_scope_hash = str(latest_summary.get("acceptance_scope_hash") or "")
    latest_scope_hash_short = str(latest_summary.get("acceptance_scope_hash_short") or "")
    requested_scope_hash = str(payload_safe.get("requested_acceptance_scope_hash") or "")
    scope_matches = bool(requested_scope_hash and requested_scope_hash == latest_scope_hash)
    storage_source = str(latest_dry_run_task.get("storage_source") or "") if latest_dry_run_task else ""
    durable_receipt_visible = storage_source in {"memory_and_sqlite", "sqlite_meta"}
    dry_run_ready = latest_summary.get("ready_for_user_approved_real_acceptance") is True
    credential_missing_count = int(latest_summary.get("credential_missing_provider_count") or 0)
    credential_ready = bool(latest_dry_run_task) and credential_missing_count == 0
    user_confirmed = payload_safe.get("user_confirmed") is True
    selected_apis = list(payload_safe.get("selected_apis") or latest_summary.get("selected_apis") or [])
    ignored_apis = list(payload_safe.get("ignored_apis") or latest_summary.get("ignored_apis") or [])
    include_tushare = payload_safe.get("include_tushare") is True or latest_summary.get("include_tushare") is True
    include_deepseek = payload_safe.get("include_deepseek") is True or latest_summary.get("include_deepseek") is True
    selected_scope_ready = bool(selected_apis or include_tushare or include_deepseek)
    rows = [
        _execution_request_row(
            "latest_acceptance_dry_run_receipt_visible",
            "passed_durable_dry_run_receipt_visible"
            if latest_dry_run_task and durable_receipt_visible
            else "blocked_missing_durable_dry_run_receipt",
            f"task_id={latest_dry_run_task.get('task_id') if latest_dry_run_task else ''}; storage_source={storage_source}",
            passed=bool(latest_dry_run_task) and durable_receipt_visible,
            local_blocker=not (bool(latest_dry_run_task) and durable_receipt_visible),
        ),
        _execution_request_row(
            "acceptance_dry_run_ready",
            "passed_dry_run_ready" if dry_run_ready else "blocked_dry_run_not_ready",
            f"dry_run_status={latest_summary.get('status')}; missing_credentials={credential_missing_count}",
            passed=dry_run_ready,
            local_blocker=not dry_run_ready,
        ),
        _execution_request_row(
            "acceptance_scope_hash_bound",
            "passed_scope_hash_bound" if scope_matches else "blocked_scope_hash_mismatch_or_missing",
            f"requested={payload_safe.get('requested_acceptance_scope_hash_short')}; latest={latest_scope_hash_short}",
            passed=scope_matches,
            local_blocker=not scope_matches,
        ),
        _execution_request_row(
            "explicit_user_confirmation_recorded",
            "passed_user_confirmed" if user_confirmed else "blocked_user_confirmation_required",
            f"user_confirmed={user_confirmed}",
            passed=user_confirmed,
            local_blocker=not user_confirmed,
        ),
        _execution_request_row(
            "credential_preflight_ready",
            "passed_credential_preflight_ready" if credential_ready else "blocked_credential_preflight_not_ready",
            f"credential_presence_status={latest_summary.get('credential_presence_status')}; missing={credential_missing_count}",
            passed=credential_ready,
            local_blocker=not credential_ready,
        ),
        _execution_request_row(
            "selected_provider_model_scope_ready",
            "passed_selected_scope_ready" if selected_scope_ready else "blocked_selected_scope_missing",
            f"selected_apis={selected_apis}; include_deepseek={include_deepseek}",
            passed=selected_scope_ready,
            local_blocker=not selected_scope_ready,
        ),
        _execution_request_row(
            "provider_model_task_not_created",
            "passed_request_only",
            "Execution request records a local receipt only; provider/model task creation remains a future route.",
            passed=True,
            production_blocker=True,
        ),
        _execution_request_row(
            "no_provider_model_trade_secret_boundary",
            "passed_no_side_effects",
            "No Tushare, DeepSeek, GitHub, token/key exposure, real trade, or strategy action mutation.",
            passed=True,
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if row.get("local_blocker")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    local_ready = not local_blockers
    if not latest_dry_run_task:
        status = "execution_request_blocked_missing_acceptance_dry_run"
    elif not user_confirmed:
        status = "execution_request_blocked_user_confirmation_required"
    elif not scope_matches:
        status = "execution_request_blocked_scope_hash_mismatch"
    elif not dry_run_ready:
        status = "execution_request_blocked_dry_run_not_ready"
    elif not credential_ready:
        status = "execution_request_blocked_credential_preflight_not_ready"
    else:
        status = "execution_request_ready_manual_provider_model_task_pending"
    receipt = {
        "schema_version": BOOTSTRAP_EXECUTION_REQUEST_SCHEMA_VERSION,
        "status": status,
        "scope": "local_provider_model_execution_request_no_provider_or_model_execution",
        "route": PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE,
        "task_type": BOOTSTRAP_EXECUTION_REQUEST_TASK_TYPE,
        "acceptance_dry_run_route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
        "target_provider_model_route": FUTURE_BOOTSTRAP_PROVIDER_MODEL_ACCEPTANCE_ROUTE,
        "latest_acceptance_dry_run_task_id": latest_dry_run_task.get("task_id") if latest_dry_run_task else "",
        "latest_acceptance_dry_run_status": latest_summary.get("status"),
        "latest_acceptance_dry_run_storage_source": storage_source,
        "durable_receipt_visible": durable_receipt_visible,
        "memory_only_dry_run_receipt_is_durable_evidence": False,
        "acceptance_scope_hash": latest_scope_hash,
        "acceptance_scope_hash_short": latest_scope_hash_short,
        "acceptance_scope_hash_algorithm": latest_summary.get("acceptance_scope_hash_algorithm"),
        "requested_acceptance_scope_hash": requested_scope_hash,
        "requested_acceptance_scope_hash_short": payload_safe.get("requested_acceptance_scope_hash_short"),
        "requested_acceptance_scope_hash_matches_latest": scope_matches,
        "user_confirmed": user_confirmed,
        "selected_apis": selected_apis,
        "ignored_apis": ignored_apis,
        "include_tushare": include_tushare,
        "include_deepseek": include_deepseek,
        "credential_presence_status": latest_summary.get("credential_presence_status"),
        "credential_required_provider_count": latest_summary.get("credential_required_provider_count", 0),
        "credential_present_provider_count": latest_summary.get("credential_present_provider_count", 0),
        "credential_missing_provider_count": credential_missing_count,
        "credential_preflight_ready": credential_ready,
        "credential_values_read": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "call_ledger_required": True,
        "model_ledger_required_for_deepseek": True,
        "redaction_review_required_before_promotion": True,
        "local_execution_request_ready": local_ready,
        "ready_for_manual_provider_model_task_submission": local_ready,
        "provider_model_task_created": False,
        "provider_model_task_dispatched": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "provider_model_execution_implemented": False,
        "execution_request_route_implemented": BOOTSTRAP_EXECUTION_REQUEST_ROUTE_IMPLEMENTED,
        "production_live_light_complete": False,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "blocking_criteria": local_blockers,
        "row_count": len(rows),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    return receipt, rows


def _execution_request_call_ledger(
    *,
    payload_safe: dict[str, Any],
    receipt: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    return {
        "api": "local_live_light_provider_model_execution_request",
        "endpoint": PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE,
        "request_params_safe": {
            "source": payload_safe.get("source"),
            "requested_by": payload_safe.get("requested_by"),
            "user_confirmed": payload_safe.get("user_confirmed"),
            "latest_acceptance_dry_run_task_id": receipt.get("latest_acceptance_dry_run_task_id"),
            "requested_acceptance_scope_hash_short": receipt.get("requested_acceptance_scope_hash_short"),
            "latest_acceptance_scope_hash_short": receipt.get("acceptance_scope_hash_short"),
            "requested_acceptance_scope_hash_matches_latest": receipt.get(
                "requested_acceptance_scope_hash_matches_latest"
            ),
            "credential_presence_status": receipt.get("credential_presence_status"),
            "credential_missing_provider_count": receipt.get("credential_missing_provider_count"),
            "local_execution_request_ready": receipt.get("local_execution_request_ready"),
            "provider_model_task_created": False,
            "provider_model_task_dispatched": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
        },
        "row_count": int(receipt.get("row_count") or 0),
        "local_blocker_count": int(receipt.get("local_blocker_count") or 0),
        "production_blocker_count": int(receipt.get("production_blocker_count") or 0),
        "local_fetched_at": now,
        "call_status": "local_execution_request_ready_no_external_call"
        if receipt.get("local_execution_request_ready") is True
        else "local_execution_request_blocked_no_external_call",
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _latest_execution_request_status_surface() -> dict[str, Any]:
    latest_task = next(
        (
            task
            for task in task_service.list_task_statuses()
            if task.get("task_type") == BOOTSTRAP_EXECUTION_REQUEST_TASK_TYPE
        ),
        None,
    )
    if latest_task is None:
        return {
            "schema_version": BOOTSTRAP_LATEST_EXECUTION_REQUEST_STATUS_SCHEMA_VERSION,
            "status": "no_execution_request_receipt_task_found",
            "lookup_source": "task_service.list_task_statuses",
            "lookup_creates_task": False,
            "route": PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE,
            "route_implemented": BOOTSTRAP_EXECUTION_REQUEST_ROUTE_IMPLEMENTED,
            "receipt_found": False,
            "task_id": "",
            "task_status": "",
            "current_step": "",
            "storage_source": "",
            "durable_receipt_visible": False,
            "memory_only_receipt_is_durable_evidence": False,
            "local_execution_request_ready": False,
            "scope_hash_matches_latest": False,
            "provider_model_task_created": False,
            "provider_model_task_dispatched": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "contains_secret": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    payload = _dict(latest_task.get("payload_safe"))
    receipt = _dict(payload.get("execution_request_receipt"))
    storage_source = str(latest_task.get("storage_source") or "")
    durable_receipt_visible = storage_source in {"memory_and_sqlite", "sqlite_meta"}
    local_ready = receipt.get("local_execution_request_ready") is True
    return {
        "schema_version": BOOTSTRAP_LATEST_EXECUTION_REQUEST_STATUS_SCHEMA_VERSION,
        "status": "latest_execution_request_receipt_visible_ready"
        if local_ready
        else "latest_execution_request_receipt_visible_blocked",
        "lookup_source": "task_service.list_task_statuses",
        "lookup_creates_task": False,
        "route": PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE,
        "route_implemented": BOOTSTRAP_EXECUTION_REQUEST_ROUTE_IMPLEMENTED,
        "receipt_found": True,
        "task_id": latest_task.get("task_id"),
        "task_status": latest_task.get("status"),
        "current_step": latest_task.get("current_step"),
        "output_packet_key": latest_task.get("output_packet_key"),
        "storage_source": storage_source,
        "durable_receipt_visible": durable_receipt_visible,
        "memory_only_receipt_is_durable_evidence": False,
        "local_execution_request_ready": local_ready,
        "ready_for_manual_provider_model_task_submission": receipt.get(
            "ready_for_manual_provider_model_task_submission"
        )
        is True,
        "receipt_status": receipt.get("status"),
        "latest_acceptance_dry_run_task_id": receipt.get("latest_acceptance_dry_run_task_id"),
        "acceptance_scope_hash_short": receipt.get("acceptance_scope_hash_short"),
        "requested_acceptance_scope_hash_short": receipt.get("requested_acceptance_scope_hash_short"),
        "scope_hash_matches_latest": receipt.get("requested_acceptance_scope_hash_matches_latest") is True,
        "credential_presence_status": receipt.get("credential_presence_status"),
        "credential_preflight_ready": receipt.get("credential_preflight_ready") is True,
        "local_blocker_count": int(receipt.get("local_blocker_count") or 0),
        "production_blocker_count": int(receipt.get("production_blocker_count") or 0),
        "blocking_criteria": list(receipt.get("blocking_criteria") or []),
        "provider_model_task_created": False,
        "provider_model_task_dispatched": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "provider_model_execution_implemented": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _planned_stage_status(mode: str, enabled: bool, stage_kind: str) -> str:
    if mode != "live_light":
        return "skipped_mode_not_live_light"
    if not enabled:
        return "skipped_by_config"
    if stage_kind == "provider":
        return "planned_provider_pending_not_executed"
    if stage_kind == "model":
        return "planned_model_pending_not_executed"
    return "planned_local_step_pending_not_executed"


def _build_live_bootstrap_local_compute_handoff(
    *,
    mode: str,
    sources_enabled: bool,
) -> dict[str, Any]:
    mode_gate_satisfied = mode == "live_light"
    source_switch_satisfied = sources_enabled
    handoff_enabled = mode_gate_satisfied and source_switch_satisfied
    if handoff_enabled:
        status = "local_compute_handoff_visible_execution_pending"
        inactive_reason = ""
    elif not mode_gate_satisfied:
        if mode == "cache_only":
            status = "local_compute_handoff_inactive_cache_only_read_only"
            inactive_reason = "cache_only_read_only"
        elif mode == "manual":
            status = "local_compute_handoff_inactive_manual_explicit_task_only"
            inactive_reason = "manual_requires_explicit_post_task"
        elif mode == "live_full":
            status = "local_compute_handoff_inactive_live_full_reserved"
            inactive_reason = "live_full_reserved_requires_separate_authorization"
        else:
            status = "local_compute_handoff_inactive_requires_live_light"
            inactive_reason = "requires_live_light_mode"
    else:
        status = "local_compute_handoff_inactive_source_switch_false"
        inactive_reason = "source_switch_false"
    required_output_lineage_fields = [
        "source_task_id",
        "source_task_type",
        "source_route",
        "runtime_mode",
        "scope_hash",
        "provider_call_ledger_ids",
        "model_ledger_ids",
        "input_packet_keys",
        "output_packet_key",
        "cache_source",
        "storage_backend",
        "local_fetched_at",
        "freshness_state",
        "data_date",
        "provider_gap",
        "safe_error",
    ]
    rows = [
        {
            "handoff_key": "factor_light_runtime",
            "handoff_order": 1,
            "source_stage": "factor_light_runtime",
            "future_local_route": "POST /api/factor-quant/run-light",
            "future_task_type": "run_factor_light",
            "future_queue": "local_compute",
            "input_surface": "prepared_cache_or_existing_factor_quant_cache",
            "input_packet_keys": ["command_center_factor_quant_hub_packet"],
            "output_packet_key": "command_center_factor_quant_hub_packet",
            "depends_on_stage": "tushare_light_refresh",
            "handoff_status": "local_compute_handoff_pending",
        },
        {
            "handoff_key": "factor_quant_hub_cache_refresh",
            "handoff_order": 2,
            "source_stage": "factor_quant_hub_cache_refresh",
            "future_local_route": "POST /api/factor-quant/run-light",
            "future_task_type": "run_factor_light",
            "future_queue": "local_compute",
            "input_surface": "factor_light_runtime_output_or_existing_cache",
            "input_packet_keys": ["command_center_factor_quant_hub_packet"],
            "output_packet_key": "command_center_factor_quant_hub_packet",
            "depends_on_stage": "factor_light_runtime",
            "handoff_status": "local_cache_write_handoff_pending",
        },
        {
            "handoff_key": "next_session_cache_refresh",
            "handoff_order": 3,
            "source_stage": "next_session_cache_refresh",
            "future_local_route": "POST /api/next-session/generate",
            "future_task_type": "build_next_session_projection",
            "future_queue": "local_compute",
            "input_surface": "factor_light_runtime_output_or_existing_next_session_cache",
            "input_packet_keys": [
                "command_center_factor_quant_hub_packet",
                "command_center_next_session_projection_packet",
            ],
            "output_packet_key": "command_center_next_session_projection_packet",
            "depends_on_stage": "factor_light_runtime",
            "handoff_status": "local_cache_write_handoff_pending",
        },
    ]
    common_flags = {
        "mode": mode,
        "mode_gate": "live_light",
        "mode_gate_satisfied": mode_gate_satisfied,
        "source_switch_satisfied": source_switch_satisfied,
        "inactive_reason": inactive_reason,
        "handoff_effective_status": status,
        "enabled_in_current_mode": handoff_enabled,
        "local_compute_from_existing_cache_allowed": True,
        "local_task_created_now": False,
        "local_compute_executed_now": False,
        "output_written_now": False,
        "cache_get_may_execute": False,
        "react_render_may_execute": False,
        "fastapi_startup_may_execute": False,
        "search_typing_may_execute": False,
        "provider_execution_required": False,
        "model_execution_required": False,
        "provider_rows_synthesized": False,
        "model_output_synthesized": False,
        "output_lineage_required": True,
        "lineage_contract_schema_version": BOOTSTRAP_CACHE_LINEAGE_CONTRACT_SCHEMA_VERSION,
        "lineage_write_policy": "post_task_worker_or_local_pipeline_only",
        "required_output_lineage_fields": list(required_output_lineage_fields),
        "lineage_required_field_count": len(required_output_lineage_fields),
        "lineage_written_now": False,
        "cache_get_may_write_lineage": False,
        "react_render_may_write_lineage": False,
        "fastapi_startup_may_write_lineage": False,
        "lineage_is_execution_evidence": False,
        "lineage_is_production_evidence": False,
        "safe_error_required_when_missing_cache": True,
        "provider_gap_visible_when_provider_data_missing": True,
        "row_is_provider_execution_evidence": False,
        "row_is_model_correctness_evidence": False,
        "row_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    rows = [{**row, **common_flags} for row in rows]
    return {
        "schema_version": BOOTSTRAP_LOCAL_COMPUTE_HANDOFF_SCHEMA_VERSION,
        "status": status,
        "mode": mode,
        "mode_gate": "live_light",
        "mode_gate_satisfied": mode_gate_satisfied,
        "source_switch_satisfied": source_switch_satisfied,
        "inactive_reason": inactive_reason,
        "handoff_rows": rows,
        "handoff_row_count": len(rows),
        "enabled_handoff_row_count": sum(1 for row in rows if row["enabled_in_current_mode"]),
        "executed_handoff_row_count": 0,
        "output_written_row_count": 0,
        "required_handoff_keys": [row["handoff_key"] for row in rows],
        "future_local_routes": sorted({row["future_local_route"] for row in rows}),
        "future_task_types": sorted({row["future_task_type"] for row in rows}),
        "output_packet_keys": sorted({row["output_packet_key"] for row in rows}),
        "input_packet_keys": sorted({packet_key for row in rows for packet_key in row["input_packet_keys"]}),
        "lineage_contract_schema_version": BOOTSTRAP_CACHE_LINEAGE_CONTRACT_SCHEMA_VERSION,
        "lineage_write_policy": "post_task_worker_or_local_pipeline_only",
        "required_output_lineage_fields": list(required_output_lineage_fields),
        "lineage_required_field_count": len(required_output_lineage_fields),
        "lineage_written_row_count": 0,
        "cache_get_may_write_lineage": False,
        "react_render_may_write_lineage": False,
        "fastapi_startup_may_write_lineage": False,
        "lineage_is_execution_evidence": False,
        "lineage_is_production_evidence": False,
        "local_compute_from_existing_cache_allowed": True,
        "bootstrap_task_executes_local_compute_now": False,
        "bootstrap_task_writes_output_now": False,
        "cache_get_may_execute_local_compute": False,
        "react_render_may_execute_local_compute": False,
        "fastapi_startup_may_execute_local_compute": False,
        "search_typing_may_execute_local_compute": False,
        "local_compute_may_synthesize_provider_rows": False,
        "local_compute_may_synthesize_model_output": False,
        "output_lineage_required": True,
        "safe_error_required_when_missing_cache": True,
        "provider_gap_visible_when_provider_data_missing": True,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "handoff_is_provider_execution_evidence": False,
        "handoff_is_model_correctness_evidence": False,
        "handoff_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _build_live_bootstrap_plan(status_packet: dict[str, Any], payload_safe: dict[str, Any]) -> dict[str, Any]:
    live_light = status_packet.get("live_light") if isinstance(status_packet.get("live_light"), dict) else {}
    safe_config = (
        status_packet.get("safe_config_contract")
        if isinstance(status_packet.get("safe_config_contract"), dict)
        else {}
    )
    mode = str(status_packet.get("mode") or DEFAULT_MODE)
    sources_enabled = bool(live_light.get("sources_enabled"))
    external_execution_profile = str(
        safe_config.get("effective_external_execution_profile") or DEFAULT_EXTERNAL_EXECUTION_PROFILE
    )
    provider_stage_allowed_by_profile = (
        safe_config.get("external_execution_profile_provider_stage_allowed") is True
    )
    model_stage_allowed_by_profile = (
        safe_config.get("external_execution_profile_model_stage_allowed") is True
    )
    tushare_source_enabled = mode == "live_light" and sources_enabled and live_light.get("tushare_on_open") is True
    deepseek_source_enabled = mode == "live_light" and sources_enabled and live_light.get("deepseek_on_open") is True
    tushare_enabled = tushare_source_enabled and provider_stage_allowed_by_profile
    deepseek_enabled = deepseek_source_enabled and model_stage_allowed_by_profile
    now = _now_iso()

    stage_specs = [
        {
            "stage_key": "initial_cache_render",
            "label": "initial GET cache render complete before POST",
            "stage_kind": "local",
            "enabled": True,
            "provider": "FastAPI cache",
            "apis": [],
            "depends_on": [],
        },
        {
            "stage_key": "scope_resolution",
            "label": "resolve current target / holdings / watchlist scope",
            "stage_kind": "local",
            "enabled": True,
            "provider": "local task payload",
            "apis": [],
            "depends_on": ["initial_cache_render"],
        },
        {
            "stage_key": "trade_cal_if_needed",
            "label": "refresh trade calendar only if missing or stale",
            "stage_kind": "provider",
            "enabled": tushare_enabled,
            "provider": "tushare",
            "apis": ["trade_cal"],
            "depends_on": ["scope_resolution"],
        },
        {
            "stage_key": "tushare_light_refresh",
            "label": "refresh daily / daily_basic / moneyflow light facts",
            "stage_kind": "provider",
            "enabled": tushare_enabled,
            "provider": "tushare",
            "apis": ["daily", "daily_basic", "moneyflow"],
            "depends_on": ["trade_cal_if_needed"],
        },
        {
            "stage_key": "factor_light_runtime",
            "label": "run Factor light runtime from prepared cache",
            "stage_kind": "local",
            "enabled": sources_enabled,
            "provider": "local factor runtime",
            "apis": [],
            "depends_on": ["tushare_light_refresh"],
        },
        {
            "stage_key": "factor_quant_hub_cache_refresh",
            "label": "refresh Factor Quant Hub cache packet",
            "stage_kind": "local",
            "enabled": sources_enabled,
            "provider": "FastAPI local cache",
            "apis": [],
            "depends_on": ["factor_light_runtime"],
        },
        {
            "stage_key": "next_session_cache_refresh",
            "label": "refresh Next Session cache packet",
            "stage_kind": "local",
            "enabled": sources_enabled,
            "provider": "FastAPI local cache",
            "apis": [],
            "depends_on": ["factor_light_runtime"],
        },
        {
            "stage_key": "deepseek_pro_explanation",
            "label": "optional DeepSeek pro explanation after data readiness",
            "stage_kind": "model",
            "enabled": deepseek_enabled,
            "provider": "deepseek",
            "apis": [],
            "depends_on": ["factor_quant_hub_cache_refresh", "next_session_cache_refresh"],
        },
        {
            "stage_key": "ui_task_polling",
            "label": "React polls task status and shows safe receipt",
            "stage_kind": "local",
            "enabled": True,
            "provider": "FastAPI task API",
            "apis": [],
            "depends_on": ["deepseek_pro_explanation"],
        },
    ]

    stage_rows: list[dict[str, Any]] = []
    for index, spec in enumerate(stage_specs, start=1):
        stage_kind = str(spec["stage_kind"])
        enabled = bool(spec["enabled"])
        if stage_kind == "provider":
            profile_required = "light_provider_or_light_provider_model"
            profile_stage_allowed = provider_stage_allowed_by_profile
            source_switch_enabled = tushare_source_enabled
        elif stage_kind == "model":
            profile_required = "light_provider_model"
            profile_stage_allowed = model_stage_allowed_by_profile
            source_switch_enabled = deepseek_source_enabled
        else:
            profile_required = "any_profile"
            profile_stage_allowed = True
            source_switch_enabled = sources_enabled
        profile_inactive_reason = ""
        if stage_kind in {"provider", "model"} and mode == "live_light":
            if not sources_enabled:
                profile_inactive_reason = "source_switch_false"
            elif not profile_stage_allowed:
                profile_inactive_reason = "external_execution_profile_does_not_allow_stage"
        planned_external_call = mode == "live_light" and enabled and stage_kind in {"provider", "model"}
        stage_rows.append(
            {
                "schema_version": BOOTSTRAP_STAGE_SCHEMA_VERSION,
                "order": index,
                "stage_key": spec["stage_key"],
                "label": spec["label"],
                "stage_kind": stage_kind,
                "status": _planned_stage_status(mode, enabled, stage_kind),
                "execution_status": "not_executed_skeleton_only",
                "provider": spec["provider"],
                "apis": list(spec["apis"]),
                "depends_on": list(spec["depends_on"]),
                "external_execution_profile": external_execution_profile,
                "profile_gate": EXTERNAL_EXECUTION_PROFILE_CONFIG_KEY
                if stage_kind in {"provider", "model"}
                else "",
                "profile_required": profile_required,
                "profile_stage_allowed": profile_stage_allowed,
                "source_switch_enabled": source_switch_enabled,
                "profile_inactive_reason": profile_inactive_reason,
                "planned_external_call": planned_external_call,
                "provider_execution_implemented": False,
                "actual_external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "call_ledger_required": True,
                "model_ledger_required": stage_kind == "model",
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    model_rows = [
        {
            "schema_version": BOOTSTRAP_MODEL_LEDGER_SCHEMA_VERSION,
            "ledger_key": "deepseek_pro_explanation_preview",
            "purpose": "explain",
            "model": str(live_light.get("deepseek_model") or get_deepseek_model("explain")),
            "status": _planned_stage_status(mode, deepseek_enabled, "model"),
            "execution_status": "not_executed_skeleton_only",
            "external_execution_profile": external_execution_profile,
            "profile_required": "light_provider_model",
            "profile_stage_allowed": model_stage_allowed_by_profile,
            "source_switch_enabled": deepseek_source_enabled,
            "profile_inactive_reason": ""
            if model_stage_allowed_by_profile or mode != "live_light" or not sources_enabled
            else "external_execution_profile_does_not_allow_stage",
            "model_call_implemented": False,
            "model_called": False,
            "deepseek_called": False,
            "input_hash_required": True,
            "output_hash_required": True,
            "required_model_ledger_fields": [
                "model_used",
                "status",
                "token_usage",
                "parse_status",
                "cache_hit",
                "input_hash",
                "output_hash",
            ],
            "parse_status_required": True,
            "sanitizer_required": True,
            "allowed_output_fields": list(DEEPSEEK_EXPLANATION_FIELDS),
            "does_not_overwrite_numeric_fields": True,
            "does_not_modify_strategy_action": True,
            "does_not_execute_trades": True,
        }
    ]

    planned_provider_stage_count = sum(1 for row in stage_rows if row["stage_kind"] == "provider" and row["planned_external_call"])
    planned_model_stage_count = sum(1 for row in stage_rows if row["stage_kind"] == "model" and row["planned_external_call"])
    local_compute_handoff = _build_live_bootstrap_local_compute_handoff(
        mode=mode,
        sources_enabled=sources_enabled,
    )
    summary = {
        "stage_count": len(stage_rows),
        "model_ledger_preview_count": len(model_rows),
        "local_compute_handoff_row_count": local_compute_handoff["handoff_row_count"],
        "local_compute_handoff_enabled_row_count": local_compute_handoff["enabled_handoff_row_count"],
        "local_compute_handoff_executed_row_count": local_compute_handoff["executed_handoff_row_count"],
        "local_compute_handoff_lineage_required_field_count": local_compute_handoff[
            "lineage_required_field_count"
        ],
        "local_compute_handoff_lineage_written_row_count": local_compute_handoff["lineage_written_row_count"],
        "symbol_count": int(payload_safe.get("symbol_count") or 0),
        "symbol_limit": int(payload_safe.get("symbol_limit") or 0),
        "external_execution_profile": external_execution_profile,
        "external_execution_profile_provider_stage_allowed": provider_stage_allowed_by_profile,
        "external_execution_profile_model_stage_allowed": model_stage_allowed_by_profile,
        "external_execution_profile_executor_implemented": False,
        "provider_stage_source_switch_enabled": tushare_source_enabled,
        "model_stage_source_switch_enabled": deepseek_source_enabled,
        "planned_provider_stage_count": planned_provider_stage_count,
        "planned_model_stage_count": planned_model_stage_count,
        "actual_provider_execution_count": 0,
        "actual_model_call_count": 0,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }

    return {
        "bootstrap_stage_schema_version": BOOTSTRAP_STAGE_SCHEMA_VERSION,
        "bootstrap_model_ledger_schema_version": BOOTSTRAP_MODEL_LEDGER_SCHEMA_VERSION,
        "bootstrap_local_compute_handoff_schema_version": BOOTSTRAP_LOCAL_COMPUTE_HANDOFF_SCHEMA_VERSION,
        "planned_at": now,
        "bootstrap_stage_rows": stage_rows,
        "bootstrap_model_ledger_preview_rows": model_rows,
        "bootstrap_local_compute_handoff_rows": local_compute_handoff["handoff_rows"],
        "bootstrap_local_compute_handoff_summary": local_compute_handoff,
        "bootstrap_plan_summary": summary,
    }


def _live_startup_call_ledger(
    *,
    status_packet: dict[str, Any],
    payload_safe: dict[str, Any],
    call_status: str,
    current_step: str,
    now: str,
    reused_task_id: str = "",
    rate_limit_age_seconds: int | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_light = status_packet.get("live_light") if isinstance(status_packet.get("live_light"), dict) else {}
    plan_summary = plan.get("bootstrap_plan_summary") if isinstance(plan, dict) and isinstance(plan.get("bootstrap_plan_summary"), dict) else {}
    local_compute_handoff = (
        plan.get("bootstrap_local_compute_handoff_summary")
        if isinstance(plan, dict) and isinstance(plan.get("bootstrap_local_compute_handoff_summary"), dict)
        else {}
    )
    local_compute_handoff_status = str(
        local_compute_handoff.get("status") or "local_compute_handoff_not_recorded"
    )
    local_compute_handoff_mode_gate = str(local_compute_handoff.get("mode_gate") or "live_light")
    local_compute_handoff_inactive_reason = str(local_compute_handoff.get("inactive_reason") or "")
    return {
        "api": "local_bootstrap_live_startup_task",
        "endpoint": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "request_params_safe": {
            "mode": status_packet.get("mode"),
            "source": payload_safe.get("source"),
            "symbol_count": payload_safe.get("symbol_count"),
            "symbol_limit": payload_safe.get("symbol_limit"),
            "tushare_on_open": live_light.get("tushare_on_open") is True,
            "deepseek_on_open": live_light.get("deepseek_on_open") is True,
            "default_light_tushare_apis": list(DEFAULT_LIGHT_TUSHARE_APIS),
            "allow_full_pool": False,
            "rate_limit_seconds": live_light.get("rate_limit_seconds"),
            "reused_task_id": reused_task_id,
            "rate_limit_age_seconds": rate_limit_age_seconds,
            "bootstrap_stage_count": int(plan_summary.get("stage_count") or 0),
            "model_ledger_preview_count": int(plan_summary.get("model_ledger_preview_count") or 0),
            "local_compute_handoff_status": local_compute_handoff_status,
            "local_compute_handoff_mode_gate": local_compute_handoff_mode_gate,
            "local_compute_handoff_mode_gate_satisfied": local_compute_handoff.get("mode_gate_satisfied") is True,
            "local_compute_handoff_source_switch_satisfied": (
                local_compute_handoff.get("source_switch_satisfied") is True
            ),
            "local_compute_handoff_inactive_reason": local_compute_handoff_inactive_reason,
            "local_compute_handoff_row_count": int(plan_summary.get("local_compute_handoff_row_count") or 0),
            "local_compute_handoff_enabled_row_count": int(
                plan_summary.get("local_compute_handoff_enabled_row_count") or 0
            ),
            "local_compute_handoff_executed_row_count": int(
                plan_summary.get("local_compute_handoff_executed_row_count") or 0
            ),
            "local_compute_handoff_output_written_row_count": int(
                local_compute_handoff.get("output_written_row_count") or 0
            ),
            "planned_provider_stage_count": int(plan_summary.get("planned_provider_stage_count") or 0),
            "planned_model_stage_count": int(plan_summary.get("planned_model_stage_count") or 0),
            "external_execution_profile": str(
                plan_summary.get("external_execution_profile") or DEFAULT_EXTERNAL_EXECUTION_PROFILE
            ),
            "external_execution_profile_provider_stage_allowed": (
                plan_summary.get("external_execution_profile_provider_stage_allowed") is True
            ),
            "external_execution_profile_model_stage_allowed": (
                plan_summary.get("external_execution_profile_model_stage_allowed") is True
            ),
            "external_execution_profile_executor_implemented": False,
        },
        "bootstrap_stage_count": int(plan_summary.get("stage_count") or 0),
        "model_ledger_preview_count": int(plan_summary.get("model_ledger_preview_count") or 0),
        "local_compute_handoff_status": local_compute_handoff_status,
        "local_compute_handoff_mode_gate": local_compute_handoff_mode_gate,
        "local_compute_handoff_mode_gate_satisfied": local_compute_handoff.get("mode_gate_satisfied") is True,
        "local_compute_handoff_source_switch_satisfied": (
            local_compute_handoff.get("source_switch_satisfied") is True
        ),
        "local_compute_handoff_inactive_reason": local_compute_handoff_inactive_reason,
        "local_compute_handoff_row_count": int(plan_summary.get("local_compute_handoff_row_count") or 0),
        "local_compute_handoff_enabled_row_count": int(
            plan_summary.get("local_compute_handoff_enabled_row_count") or 0
        ),
        "local_compute_handoff_executed_row_count": int(
            plan_summary.get("local_compute_handoff_executed_row_count") or 0
        ),
        "local_compute_handoff_output_written_row_count": int(
            local_compute_handoff.get("output_written_row_count") or 0
        ),
        "local_compute_handoff_ledger_executes_local_compute": False,
        "local_compute_handoff_ledger_writes_output": False,
        "local_compute_handoff_ledger_is_execution_evidence": False,
        "local_compute_handoff_ledger_is_production_evidence": False,
        "planned_provider_stage_count": int(plan_summary.get("planned_provider_stage_count") or 0),
        "planned_model_stage_count": int(plan_summary.get("planned_model_stage_count") or 0),
        "external_execution_profile": str(
            plan_summary.get("external_execution_profile") or DEFAULT_EXTERNAL_EXECUTION_PROFILE
        ),
        "external_execution_profile_provider_stage_allowed": (
            plan_summary.get("external_execution_profile_provider_stage_allowed") is True
        ),
        "external_execution_profile_model_stage_allowed": (
            plan_summary.get("external_execution_profile_model_stage_allowed") is True
        ),
        "external_execution_profile_executor_implemented": False,
        "row_count": int(payload_safe.get("symbol_count") or 0),
        "data_date": None,
        "local_fetched_at": now,
        "call_status": call_status,
        "current_step": current_step,
        "error_message_safe": "",
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "provider_execution_implemented": False,
        "bootstrap_task_implemented": True,
        "rate_limit_enforced": True,
        "reused_task_id": reused_task_id,
        "rate_limit_age_seconds": rate_limit_age_seconds,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_startup_warnings(mode: str, current_step: str) -> list[str]:
    warnings = [
        "POST /api/bootstrap/live-startup 当前只创建本地 live_light bootstrap task 骨架；不会调用 Tushare、DeepSeek、GitHub。",
        "该任务记录模式、限频、payload 安全摘要和 call_ledger；provider 执行仍是后续长期目标。",
        "任务不会执行真实交易，不会修改 strategy action、价格、持仓或 operation_zones。",
    ]
    if mode != "live_light":
        warnings.append("当前模式不是 live_light；bootstrap task 已安全跳过。")
    elif current_step == "live_bootstrap_skipped_sources_disabled_no_external_call":
        warnings.append("live_light 已启用，但 Tushare/DeepSeek on-open 开关均为 false；任务已安全跳过。")
    elif current_step == "live_bootstrap_skipped_due_to_rate_limit":
        warnings.append("rate limit 内已存在 live_light bootstrap task；本次复用旧任务，不创建重复任务。")
    return warnings


def _live_light_background_task_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    startup_autostart_configured: bool,
    effective_startup_autostart: bool,
    live_light_sources_enabled: bool,
    tushare_on_open: bool,
    deepseek_on_open: bool,
    symbol_limit: int,
    rate_limit_seconds: int,
) -> dict[str, Any]:
    return {
        "schema_version": "command_center_live_light_background_task_contract.v1",
        "status": "ready_local_task_skeleton_no_provider_execution"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_type": BOOTSTRAP_TASK_TYPE,
        "trigger_surface": "react_mounted_after_initial_cache_render_or_search_action",
        "allowed_auto_trigger_mode": "live_light",
        "config_switch": STARTUP_AUTOSTART_CONFIG_KEY,
        "startup_autostart_configured": startup_autostart_configured,
        "startup_autostart_effective": effective_startup_autostart,
        "auto_trigger_allowed": effective_startup_autostart,
        "cache_get_creates_task": False,
        "fastapi_startup_creates_task": False,
        "react_initial_render_creates_task": False,
        "react_render_calls_provider": False,
        "initial_cache_render_required": True,
        "creates_or_reuses_background_task_only": True,
        "task_creation_rate_limited": True,
        "rate_limit_seconds": rate_limit_seconds,
        "rate_limit_reuses_existing_task": True,
        "rate_limit_skip_creates_new_task": False,
        "session_dedupe_required": True,
        "symbol_limit": symbol_limit,
        "symbol_dedupe_required": True,
        "symbol_limit_truncation_required": True,
        "allowed_symbol_sources": ["current_target", "searched_symbol", "symbols", "watchlist", "holdings"],
        "allowed_scope": "current_target_holdings_watchlist_searched_symbol_light_only",
        "full_pool_scope_allowed": False,
        "deep_scan_scope_allowed": False,
        "payload_safe_only": True,
        "payload_secret_fields_dropped": True,
        "sources_enabled": live_light_sources_enabled,
        "tushare_planned": bool(live_light_enabled and live_light_sources_enabled and tushare_on_open),
        "deepseek_planned": bool(live_light_enabled and live_light_sources_enabled and deepseek_on_open),
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "real_provider_model_execution_allowed_now": False,
        "external_calls_must_use_post_task_worker_or_local_fallback": True,
        "call_ledger_required": True,
        "model_ledger_required_for_deepseek": True,
        "ui_nonblocking_required": True,
        "safe_failure_display_required": True,
        "token_key_exposure_allowed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _live_light_startup_autostart_readiness_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    live_light_sources_enabled: bool,
    background_task_contract: dict[str, Any],
    cache_first_polling_contract: dict[str, Any],
) -> dict[str, Any]:
    readiness_rows = [
        {
            "readiness_key": "bootstrap_status_read_before_autostart",
            "readiness_order": 1,
            "required_state": "frontend reads GET /api/bootstrap/status before startup autostart",
            "required_evidence": "mode, source switches, rate limit, and task route are visible before POST",
            "current_blocker": "frontend_startup_wiring_evidence_pending",
            "linked_contract": "runtime_operator_summary_contract",
        },
        {
            "readiness_key": "initial_cache_render_completed",
            "readiness_order": 2,
            "required_state": "initial cache render completes before any startup POST",
            "required_evidence": "cache-first render trace shows no provider/model/network side effect",
            "current_blocker": "browser_cache_first_trace_pending",
            "linked_contract": "runtime_cache_first_polling_contract",
        },
        {
            "readiness_key": "live_light_mode_and_source_switch_effective",
            "readiness_order": 3,
            "required_state": "active mode is live_light and configured source switches are effective",
            "required_evidence": "cache_only/manual/live_full or disabled startup/source switches keep startup autostart disabled",
            "current_blocker": "mode_and_source_switch_browser_evidence_pending",
            "linked_contract": "safe_config_contract",
        },
        {
            "readiness_key": "single_local_post_task_boundary",
            "readiness_order": 4,
            "required_state": "startup autostart may only call POST /api/bootstrap/live-startup",
            "required_evidence": "GET cache, React render, and FastAPI startup create no task",
            "current_blocker": "local_post_boundary_browser_evidence_pending",
            "linked_contract": "live_light_background_task_contract",
        },
        {
            "readiness_key": "rate_limit_and_session_dedupe_visible",
            "readiness_order": 5,
            "required_state": "rate-limit and session dedupe prevent an unbounded task queue",
            "required_evidence": "repeat startup attempts reuse or skip an existing local task",
            "current_blocker": "rate_limit_reuse_trace_pending",
            "linked_contract": "live_light_task_lifecycle_contract",
        },
        {
            "readiness_key": "task_polling_and_safe_failure_visible",
            "readiness_order": 6,
            "required_state": "frontend polls GET /api/tasks/{task_id} and shows safe failure states",
            "required_evidence": "task id, status, progress, safe error, and last-good cache remain visible",
            "current_blocker": "task_polling_failure_recovery_trace_pending",
            "linked_contract": "runtime_cache_first_polling_contract",
        },
        {
            "readiness_key": "provider_model_execution_deferred",
            "readiness_order": 7,
            "required_state": "startup autostart does not execute Tushare or DeepSeek directly",
            "required_evidence": "provider/model stages remain behind execution-request and ledger governance",
            "current_blocker": "provider_model_execution_request_still_required",
            "linked_contract": "live_light_execution_request_handoff_contract",
        },
    ]
    common_flags = {
        "required_before_frontend_startup_autostart": True,
        "condition_currently_satisfied": False,
        "browser_evidence_collected": False,
        "readiness_evidence_complete": False,
        "blocks_frontend_startup_wiring": True,
        "cache_get_creates_task": False,
        "react_initial_render_creates_task": False,
        "react_mounted_may_post_after_cache_render_only": True,
        "fastapi_startup_creates_task": False,
        "search_typing_creates_task": False,
        "creates_provider_model_task": False,
        "frontend_provider_call_allowed": False,
        "frontend_model_call_allowed": False,
        "provider_model_execution_requires_execution_request": True,
        "row_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    condition_satisfied_by_key = {
        "bootstrap_status_read_before_autostart": True,
        "initial_cache_render_completed": bool(cache_first_polling_contract.get("cache_first_render_required")),
        "live_light_mode_and_source_switch_effective": bool(
            live_light_enabled
            and live_light_sources_enabled
            and background_task_contract.get("startup_autostart_effective")
        ),
        "single_local_post_task_boundary": bool(
            background_task_contract.get("creates_or_reuses_background_task_only")
            and background_task_contract.get("cache_get_creates_task") is False
            and background_task_contract.get("react_initial_render_creates_task") is False
        ),
        "rate_limit_and_session_dedupe_visible": bool(
            background_task_contract.get("task_creation_rate_limited")
            and background_task_contract.get("session_dedupe_required")
        ),
        "task_polling_and_safe_failure_visible": bool(cache_first_polling_contract.get("polling_required")),
        "provider_model_execution_deferred": bool(
            background_task_contract.get("provider_execution_implemented") is False
            and background_task_contract.get("model_execution_implemented") is False
        ),
    }
    readiness_rows = [
        {
            **row,
            **common_flags,
            "condition_currently_satisfied": bool(
                condition_satisfied_by_key.get(row["readiness_key"], False)
            ),
        }
        for row in readiness_rows
    ]
    satisfied_count = sum(1 for row in readiness_rows if row["condition_currently_satisfied"])
    return {
        "schema_version": BOOTSTRAP_STARTUP_AUTOSTART_READINESS_SCHEMA_VERSION,
        "status": "startup_autostart_readiness_visible_frontend_wiring_pending"
        if live_light_enabled
        else "startup_autostart_readiness_inactive_until_live_light_mode",
        "mode": active_mode,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_type": BOOTSTRAP_TASK_TYPE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "trigger_surface": "react_mounted_after_initial_cache_render",
        "readiness_rows": readiness_rows,
        "readiness_row_count": len(readiness_rows),
        "condition_satisfied_row_count": satisfied_count,
        "browser_evidence_collected_row_count": 0,
        "readiness_evidence_complete_row_count": 0,
        "blocking_readiness_row_count": len(readiness_rows),
        "required_readiness_keys": [row["readiness_key"] for row in readiness_rows],
        "active_mode_live_light": live_light_enabled,
        "sources_effective": live_light_sources_enabled,
        "startup_autostart_configured": background_task_contract.get("startup_autostart_configured"),
        "startup_autostart_config_effective": background_task_contract.get("startup_autostart_effective"),
        "frontend_startup_autostart_wiring_implemented": False,
        "browser_runtime_evidence_complete": False,
        "startup_autostart_effective_allowed": False,
        "startup_autostart_creates_local_task_only": True,
        "startup_autostart_provider_model_execution_allowed": False,
        "cache_first_render_required": True,
        "bootstrap_status_read_required": True,
        "rate_limit_reuse_required": True,
        "session_dedupe_required": True,
        "task_polling_required": True,
        "safe_failure_display_required": True,
        "linked_background_task_schema_version": background_task_contract.get("schema_version"),
        "linked_background_task_auto_trigger_allowed": background_task_contract.get("auto_trigger_allowed"),
        "linked_background_task_rate_limit_seconds": background_task_contract.get("rate_limit_seconds"),
        "linked_cache_first_polling_schema_version": cache_first_polling_contract.get("schema_version"),
        "linked_cache_first_polling_phase_count": cache_first_polling_contract.get("phase_count"),
        "linked_cache_first_polling_task_creation_allowed_phase_count": cache_first_polling_contract.get(
            "task_creation_allowed_phase_count"
        ),
        "cache_get_creates_task": False,
        "react_initial_render_creates_task": False,
        "react_render_calls_provider": False,
        "fastapi_startup_creates_task": False,
        "search_typing_creates_task": False,
        "creates_provider_model_task": False,
        "frontend_provider_call_allowed": False,
        "frontend_model_call_allowed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "provider_model_execution_requires_execution_request": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
        "contract_is_production_evidence": False,
        "production_live_light_complete": False,
    }


def _live_light_scope_intake_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    symbol_limit: int,
) -> dict[str, Any]:
    allowed_sources = ["current_target", "searched_symbol", "symbols", "watchlist", "holdings"]
    return {
        "schema_version": BOOTSTRAP_SCOPE_INTAKE_CONTRACT_SCHEMA_VERSION,
        "status": "scope_intake_contract_visible_normalization_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "search_quant_projection_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "allowed_symbol_sources": allowed_sources,
        "default_symbol_source_order": allowed_sources,
        "allowed_symbol_pattern_description": "A-share ts_code or existing local symbol id after safe normalization",
        "symbol_limit": symbol_limit,
        "symbol_normalization_required": True,
        "symbol_dedupe_required": True,
        "symbol_limit_truncation_required": True,
        "empty_symbol_list_allowed": True,
        "empty_symbol_list_status": "scope_empty_local_task_allowed_no_provider_execution",
        "scope_hash_required": True,
        "scope_hash_algorithm": "sha256_json_sorted_safe_payload",
        "scope_hash_excludes_secret_fields": True,
        "safe_payload_required": True,
        "secret_like_payload_fields_dropped": True,
        "raw_user_input_logged": False,
        "raw_user_input_cached": False,
        "frontend_packet_may_contain_raw_query": False,
        "cache_get_may_expand_scope": False,
        "react_render_may_expand_scope": False,
        "fastapi_startup_may_expand_scope": False,
        "search_typing_may_create_task": False,
        "explicit_search_action_required": True,
        "full_pool_scope_allowed": False,
        "deep_scan_scope_allowed": False,
        "watchlist_scope_bounded": True,
        "holdings_scope_bounded": True,
        "provider_model_execution_from_scope_intake_allowed": False,
        "scope_intake_is_provider_execution_evidence": False,
        "scope_intake_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_stage_dependency_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    live_light_sources_enabled: bool,
    tushare_on_open: bool,
    deepseek_on_open: bool,
) -> dict[str, Any]:
    stage_sequence = [
        "initial_cache_render",
        "scope_resolution",
        "trade_cal_if_needed",
        "tushare_light_refresh",
        "factor_light_runtime",
        "factor_quant_hub_cache_refresh",
        "next_session_cache_refresh",
        "deepseek_pro_explanation",
        "ui_task_polling",
    ]
    dependency_edges = [
        {
            "from_stage": "initial_cache_render",
            "to_stage": "scope_resolution",
            "gate": "cache_first_render_complete",
        },
        {
            "from_stage": "scope_resolution",
            "to_stage": "trade_cal_if_needed",
            "gate": "safe_scope_hash_ready",
        },
        {
            "from_stage": "trade_cal_if_needed",
            "to_stage": "tushare_light_refresh",
            "gate": "trade_calendar_ready_or_safe_skip",
        },
        {
            "from_stage": "tushare_light_refresh",
            "to_stage": "factor_light_runtime",
            "gate": "tushare_light_facts_ready_or_provider_gap_visible",
        },
        {
            "from_stage": "factor_light_runtime",
            "to_stage": "factor_quant_hub_cache_refresh",
            "gate": "factor_light_runtime_ready_or_safe_skip",
        },
        {
            "from_stage": "factor_light_runtime",
            "to_stage": "next_session_cache_refresh",
            "gate": "factor_light_runtime_ready_or_safe_skip",
        },
        {
            "from_stage": "factor_quant_hub_cache_refresh",
            "to_stage": "deepseek_pro_explanation",
            "gate": "factor_quant_hub_cache_ready",
        },
        {
            "from_stage": "next_session_cache_refresh",
            "to_stage": "deepseek_pro_explanation",
            "gate": "next_session_cache_ready",
        },
        {
            "from_stage": "deepseek_pro_explanation",
            "to_stage": "ui_task_polling",
            "gate": "terminal_or_safe_skip_status_visible",
        },
    ]
    dependency_rows = [
        {
            "order": index,
            "stage_key": stage_key,
            "depends_on": [
                edge["from_stage"] for edge in dependency_edges if edge["to_stage"] == stage_key
            ],
            "dependency_gate": [
                edge["gate"] for edge in dependency_edges if edge["to_stage"] == stage_key
            ],
            "stage_status_must_be_pollable": True,
            "safe_skip_allowed": stage_key
            in {
                "trade_cal_if_needed",
                "tushare_light_refresh",
                "factor_light_runtime",
                "factor_quant_hub_cache_refresh",
                "next_session_cache_refresh",
                "deepseek_pro_explanation",
            },
            "cache_get_may_execute_stage": False,
            "react_render_may_execute_stage": False,
            "fastapi_startup_may_execute_stage": False,
        }
        for index, stage_key in enumerate(stage_sequence, start=1)
    ]
    return {
        "schema_version": BOOTSTRAP_STAGE_DEPENDENCY_CONTRACT_SCHEMA_VERSION,
        "status": "stage_dependency_contract_visible_executor_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_type": BOOTSTRAP_TASK_TYPE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "stage_sequence": stage_sequence,
        "stage_count": len(stage_sequence),
        "dependency_edges": dependency_edges,
        "dependency_edge_count": len(dependency_edges),
        "dependency_rows": dependency_rows,
        "initial_cache_render_first": True,
        "scope_intake_before_provider": True,
        "tushare_before_factor_light": True,
        "factor_light_before_factor_quant_hub": True,
        "factor_light_before_next_session": True,
        "deepseek_after_factor_and_next_ready": True,
        "deepseek_may_run_without_data_ready": False,
        "provider_gap_blocks_deepseek_or_requires_safe_skip": True,
        "safe_skip_propagates_to_dependents": True,
        "ui_polling_after_terminal_or_safe_skip": True,
        "stage_status_history_required": True,
        "stage_safe_error_required": True,
        "stage_provider_gap_visible_required": True,
        "cache_get_may_execute_stage": False,
        "react_render_may_execute_stage": False,
        "fastapi_startup_may_execute_stage": False,
        "tushare_source_switch_enabled": bool(
            live_light_enabled and live_light_sources_enabled and tushare_on_open
        ),
        "deepseek_source_switch_enabled": bool(
            live_light_enabled and live_light_sources_enabled and deepseek_on_open
        ),
        "provider_model_acceptance_requires_execution_request": True,
        "live_light_executor_implemented": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "stage_dependency_contract_is_execution_evidence": False,
        "stage_dependency_contract_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_freshness_provider_gap_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    freshness_state_values = [
        "fresh_provider",
        "cache_hit_fresh",
        "cache_hit_stale",
        "provider_gap",
        "safe_error",
        "credential_missing",
        "permission_denied",
        "empty_result",
        "no_record",
        "skipped_by_mode",
        "skipped_by_source_switch",
        "skipped_by_rate_limit",
        "skipped_budget_exceeded",
    ]
    freshness_rows = [
        {
            "surface_key": "factor_quant_hub_cache",
            "packet_key": "command_center_factor_quant_hub_packet",
            "freshness_state_required": True,
            "provider_gap_visible_required": True,
            "safe_error_visible_required": True,
            "stale_cache_label_required": True,
            "empty_result_may_be_verified": False,
            "no_record_may_be_negative_evidence": False,
            "permission_denied_may_be_verified": False,
            "cache_hit_is_provider_execution_evidence": False,
        },
        {
            "surface_key": "next_session_cache",
            "packet_key": "command_center_next_session_projection_packet",
            "freshness_state_required": True,
            "provider_gap_visible_required": True,
            "safe_error_visible_required": True,
            "stale_cache_label_required": True,
            "empty_result_may_be_verified": False,
            "no_record_may_be_negative_evidence": False,
            "permission_denied_may_be_verified": False,
            "cache_hit_is_provider_execution_evidence": False,
        },
        {
            "surface_key": "deepseek_explanation_cache",
            "packet_key": "command_center_factor_quant_hub_packet:data.deepseek_explanation",
            "freshness_state_required": True,
            "provider_gap_visible_required": True,
            "safe_error_visible_required": True,
            "stale_cache_label_required": False,
            "empty_result_may_be_verified": False,
            "no_record_may_be_negative_evidence": False,
            "permission_denied_may_be_verified": False,
            "cache_hit_is_provider_execution_evidence": False,
            "deepseek_skipped_when_data_not_ready": True,
            "deepseek_skip_is_model_correctness_evidence": False,
        },
    ]
    return {
        "schema_version": BOOTSTRAP_FRESHNESS_PROVIDER_GAP_CONTRACT_SCHEMA_VERSION,
        "status": "freshness_provider_gap_contract_visible_runtime_evidence_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "required_surfaces": [
            "factor_quant_hub_cache",
            "next_session_cache",
            "deepseek_explanation_cache",
        ],
        "freshness_state_values": freshness_state_values,
        "provider_gap_state_values": [
            "credential_missing",
            "permission_denied",
            "empty_result",
            "no_record",
            "safe_error",
            "provider_unavailable",
        ],
        "freshness_rows": freshness_rows,
        "freshness_row_count": len(freshness_rows),
        "freshness_state_visible_required": True,
        "data_date_visible_required": True,
        "local_fetched_at_visible_required": True,
        "cache_source_visible_required": True,
        "provider_gap_visible_required": True,
        "safe_error_visible_required": True,
        "stale_cache_label_required": True,
        "last_good_cache_lineage_required": True,
        "cache_hit_is_provider_execution_evidence": False,
        "cache_hit_is_model_execution_evidence": False,
        "stale_cache_is_freshness_evidence": False,
        "empty_result_may_be_verified": False,
        "empty_result_may_close_provider_gap": False,
        "no_record_may_be_negative_evidence": False,
        "permission_denied_may_be_verified": False,
        "credential_missing_may_be_verified": False,
        "safe_error_may_be_verified": False,
        "provider_gap_may_be_synthesized": False,
        "fallback_may_synthesize_provider_rows": False,
        "fallback_may_synthesize_model_output": False,
        "deepseek_skipped_when_data_not_ready": True,
        "deepseek_skip_is_model_correctness_evidence": False,
        "freshness_contract_is_provider_execution_evidence": False,
        "freshness_contract_is_model_execution_evidence": False,
        "freshness_contract_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_task_lifecycle_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    rate_limit_seconds: int,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_TASK_LIFECYCLE_CONTRACT_SCHEMA_VERSION,
        "status": "task_lifecycle_contract_visible_status_polling_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "task_index_route": "GET /api/tasks",
        "task_type": BOOTSTRAP_TASK_TYPE,
        "output_packet_key": BOOTSTRAP_TASK_PACKET_KEY,
        "lifecycle_surface": "task_service_status_only",
        "allowed_task_statuses": ["pending", "running", "success", "failed", "cancelled"],
        "terminal_task_statuses": ["success", "failed", "cancelled"],
        "success_status_may_still_mean_safe_skip": True,
        "expected_live_light_success_current_step": "live_bootstrap_plan_recorded_no_provider_execution",
        "safe_skip_current_steps": [
            "live_bootstrap_skipped_mode_not_live_light",
            "live_bootstrap_skipped_sources_disabled_no_external_call",
            "live_bootstrap_skipped_due_to_rate_limit",
        ],
        "required_visible_task_fields": [
            "task_id",
            "task_type",
            "status",
            "progress",
            "current_step",
            "error_message_safe",
            "status_history",
            "call_ledger",
            "output_packet_key",
        ],
        "required_status_history_fields": ["status", "progress", "current_step", "at"],
        "progress_min": 0.0,
        "progress_max": 1.0,
        "progress_visible_required": True,
        "current_step_visible_required": True,
        "task_id_visible_required": True,
        "task_status_visible_required": True,
        "status_history_visible_required": True,
        "safe_error_visible_required": True,
        "rate_limit_skipped_state_visible_required": True,
        "rate_limit_reuses_existing_task": True,
        "rate_limit_seconds": rate_limit_seconds,
        "status_get_creates_task": False,
        "status_index_creates_task": False,
        "status_get_calls_provider": False,
        "status_index_calls_provider": False,
        "react_initial_render_creates_task": False,
        "react_render_calls_provider": False,
        "polling_ui_thread_blocking_allowed": False,
        "raw_exception_exposed": False,
        "call_ledger_required": True,
        "call_ledger_visible_safe_summary_only": True,
        "task_success_is_provider_execution_evidence": False,
        "task_success_is_model_execution_evidence": False,
        "task_success_is_production_evidence": False,
        "safe_skip_is_provider_execution_evidence": False,
        "safe_skip_is_production_evidence": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_task_queue_budget_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    startup_autostart_effective: bool,
    rate_limit_seconds: int,
    symbol_limit: int,
    background_task_contract: dict[str, Any],
    task_lifecycle_contract: dict[str, Any],
) -> dict[str, Any]:
    queue_rows = [
        {
            "budget_key": "startup_autostart_gate",
            "budget_order": 1,
            "required_state": "startup autostart is effective only after live_light mode, source switches, and cache-first render",
            "current_policy": "configured_switch_plus_mode_source_gate",
            "linked_contract": "live_light_background_task_contract",
            "condition_currently_satisfied": bool(startup_autostart_effective),
        },
        {
            "budget_key": "single_active_local_startup_task",
            "budget_order": 2,
            "required_state": "a browser session may have at most one active local startup task",
            "current_policy": "max_one_active_local_startup_task_per_session",
            "linked_contract": "live_light_task_lifecycle_contract",
            "condition_currently_satisfied": True,
        },
        {
            "budget_key": "rate_limit_reuse_or_skip",
            "budget_order": 3,
            "required_state": "repeat startup attempts inside the rate window reuse or skip an existing local task",
            "current_policy": "rate_limit_reuses_existing_task_no_new_queue_item",
            "linked_contract": "live_light_task_lifecycle_contract",
            "condition_currently_satisfied": bool(
                background_task_contract.get("rate_limit_reuses_existing_task")
                and task_lifecycle_contract.get("rate_limit_reuses_existing_task")
            ),
        },
        {
            "budget_key": "status_reads_never_enqueue",
            "budget_order": 4,
            "required_state": "GET bootstrap status and task polling routes never create startup tasks",
            "current_policy": "status_surfaces_are_read_only",
            "linked_contract": "runtime_cache_first_polling_contract",
            "condition_currently_satisfied": bool(
                task_lifecycle_contract.get("status_get_creates_task") is False
                and task_lifecycle_contract.get("status_index_creates_task") is False
            ),
        },
        {
            "budget_key": "provider_model_queue_blocked",
            "budget_order": 5,
            "required_state": "startup queue budget cannot create provider/model execution tasks",
            "current_policy": "execution_request_required_before_provider_model_task",
            "linked_contract": "live_light_execution_request_handoff_contract",
            "condition_currently_satisfied": True,
        },
    ]
    common_flags = {
        "max_active_local_startup_tasks_per_session": 1,
        "unbounded_queue_allowed": False,
        "queue_overflow_policy": "reuse_or_skip_existing_local_task",
        "status_get_creates_task": False,
        "task_polling_creates_task": False,
        "search_typing_creates_task": False,
        "react_initial_render_creates_task": False,
        "react_mounted_may_post_after_cache_render_only": True,
        "creates_provider_model_task": False,
        "provider_model_execution_requires_execution_request": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_is_production_evidence": False,
    }
    queue_rows = [{**row, **common_flags} for row in queue_rows]
    condition_satisfied_count = sum(1 for row in queue_rows if row["condition_currently_satisfied"])
    return {
        "schema_version": BOOTSTRAP_TASK_QUEUE_BUDGET_CONTRACT_SCHEMA_VERSION,
        "status": "task_queue_budget_visible_frontend_wiring_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "task_index_route": "GET /api/tasks",
        "task_type": BOOTSTRAP_TASK_TYPE,
        "queue_rows": queue_rows,
        "queue_row_count": len(queue_rows),
        "condition_satisfied_row_count": condition_satisfied_count,
        "max_active_local_startup_tasks_per_session": 1,
        "max_new_tasks_per_rate_limit_window": 1,
        "rate_limit_seconds": rate_limit_seconds,
        "symbol_limit": symbol_limit,
        "startup_autostart_effective": startup_autostart_effective,
        "bounded_queue_required": True,
        "unbounded_queue_allowed": False,
        "queue_overflow_policy": "reuse_or_skip_existing_local_task",
        "rate_limit_reuses_existing_task": True,
        "rate_limit_skip_creates_new_task": False,
        "session_dedupe_required": True,
        "task_polling_required": True,
        "status_get_creates_task": False,
        "task_polling_creates_task": False,
        "search_typing_creates_task": False,
        "cache_get_creates_task": False,
        "fastapi_startup_creates_task": False,
        "react_initial_render_creates_task": False,
        "react_mounted_may_post_after_cache_render_only": True,
        "creates_provider_model_task": False,
        "provider_model_execution_requires_execution_request": True,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "queue_contract_is_execution_evidence": False,
        "queue_contract_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_task_control_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    control_rows = [
        {
            "control_key": "cancel",
            "route": "POST /api/tasks/{task_id}/cancel",
            "allowed_task_statuses": ["pending", "running"],
            "result_status": "cancelled",
            "current_step": "cancelled_by_user_no_external_call",
            "manual_operator_action_required": True,
            "safe_reason_required": True,
            "creates_new_task": False,
            "provider_or_model_execution_allowed": False,
        },
        {
            "control_key": "retry",
            "route": "POST /api/tasks/{task_id}/retry",
            "allowed_task_statuses": ["failed"],
            "result_status": "pending",
            "current_step": "manual_retry_queued_no_external_call",
            "manual_operator_action_required": True,
            "safe_reason_required": True,
            "creates_new_task": True,
            "provider_or_model_execution_allowed": False,
        },
    ]
    return {
        "schema_version": BOOTSTRAP_TASK_CONTROL_CONTRACT_SCHEMA_VERSION,
        "status": "task_control_contract_visible_manual_cancel_retry_only"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "task_index_route": "GET /api/tasks",
        "cancel_route": "POST /api/tasks/{task_id}/cancel",
        "retry_route": "POST /api/tasks/{task_id}/retry",
        "control_rows": control_rows,
        "control_row_count": len(control_rows),
        "cancel_route_available": True,
        "retry_route_available": True,
        "manual_operator_action_required": True,
        "auto_cancel_enabled": False,
        "auto_retry_enabled": False,
        "retry_requires_failed_task": True,
        "retry_creates_new_local_task_only": True,
        "cancel_may_stop_provider_call_in_flight": False,
        "control_reason_sanitized": True,
        "raw_control_reason_logged": False,
        "raw_control_reason_cached": False,
        "credential_values_exposed": False,
        "task_id_sanitized_when_missing": True,
        "control_call_ledger_required": True,
        "control_call_ledger_safe_summary_only": True,
        "status_history_append_required": True,
        "task_log_append_required": True,
        "cache_get_may_cancel_or_retry": False,
        "react_render_may_cancel_or_retry": False,
        "fastapi_startup_may_cancel_or_retry": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "control_contract_is_provider_execution_evidence": False,
        "control_contract_is_model_execution_evidence": False,
        "control_contract_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_operator_status_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    live_light_sources_enabled: bool,
    tushare_on_open: bool,
    deepseek_on_open: bool,
    external_execution_profile: str,
    external_execution_profile_provider_stage_allowed: bool,
    external_execution_profile_model_stage_allowed: bool,
    symbol_limit: int,
    rate_limit_seconds: int,
) -> dict[str, Any]:
    status_rows = [
        {
            "surface_key": "runtime_mode",
            "source": BOOTSTRAP_STATUS_ROUTE,
            "required_fields": ["mode", "configured_mode_valid", "safe_config_contract"],
            "current_value_safe": active_mode,
            "frontend_visible": True,
            "frontend_editable": False,
            "status_get_creates_task": False,
            "provider_or_model_execution_evidence": False,
        },
        {
            "surface_key": "source_switches",
            "source": BOOTSTRAP_STATUS_ROUTE,
            "required_fields": [
                "configured_tushare_on_open",
                "configured_deepseek_on_open",
                "effective_tushare_on_open",
                "effective_deepseek_on_open",
            ],
            "configured_tushare_on_open": tushare_on_open,
            "configured_deepseek_on_open": deepseek_on_open,
            "effective_tushare_on_open": bool(live_light_enabled and tushare_on_open),
            "effective_deepseek_on_open": bool(live_light_enabled and deepseek_on_open),
            "mode_gate": "live_light",
            "frontend_visible": True,
            "frontend_editable": False,
            "provider_or_model_execution_evidence": False,
        },
        {
            "surface_key": "external_execution_profile",
            "source": BOOTSTRAP_STATUS_ROUTE,
            "required_fields": [
                "effective_external_execution_profile",
                "external_execution_profile_provider_stage_allowed",
                "external_execution_profile_model_stage_allowed",
                "rate_limit_seconds",
            ],
            "current_value_safe": external_execution_profile,
            "mode_gate": "live_light_post_task_worker_ledger",
            "source_switches_effective": bool(live_light_sources_enabled),
            "provider_stage_allowed_by_profile": external_execution_profile_provider_stage_allowed,
            "model_stage_allowed_by_profile": external_execution_profile_model_stage_allowed,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "calls_provider_model_now": False,
            "creates_provider_model_task": False,
            "linked_rate_limit_seconds_visible_safe": rate_limit_seconds,
            "frontend_visible": True,
            "frontend_editable": False,
            "provider_or_model_execution_evidence": False,
        },
        {
            "surface_key": "latest_bootstrap_task",
            "source": "GET /api/tasks",
            "required_fields": ["task_id", "status", "progress", "current_step", "output_packet_key"],
            "task_type": BOOTSTRAP_TASK_TYPE,
            "task_status_route": "GET /api/tasks/{task_id}",
            "latest_task_status_may_be_skeleton_or_safe_skip": True,
            "frontend_visible": True,
            "frontend_editable": False,
            "status_get_creates_task": False,
            "provider_or_model_execution_evidence": False,
        },
        {
            "surface_key": "rate_limit_state",
            "source": "GET /api/tasks/{task_id}",
            "required_fields": ["current_step", "call_status", "rate_limit_seconds", "reused_task_id"],
            "rate_limit_seconds": rate_limit_seconds,
            "skipped_current_step": "live_bootstrap_skipped_due_to_rate_limit",
            "rate_limit_reuses_existing_task": True,
            "rate_limit_skip_creates_new_task": False,
            "frontend_visible": True,
            "frontend_editable": False,
            "provider_or_model_execution_evidence": False,
        },
        {
            "surface_key": "safe_error_state",
            "source": "GET /api/tasks/{task_id}",
            "required_fields": ["error_message_safe", "status_history", "warnings"],
            "raw_exception_visible_allowed": False,
            "raw_task_payload_visible_allowed": False,
            "safe_error_visible_required": True,
            "frontend_visible": True,
            "frontend_editable": False,
            "provider_or_model_execution_evidence": False,
        },
        {
            "surface_key": "evidence_boundary_state",
            "source": BOOTSTRAP_STATUS_ROUTE,
            "required_fields": [
                "provider_execution_implemented",
                "model_execution_implemented",
                "production_evidence_pending",
            ],
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "production_evidence_pending": True,
            "frontend_visible": True,
            "frontend_editable": False,
            "provider_or_model_execution_evidence": False,
        },
    ]
    return {
        "schema_version": BOOTSTRAP_OPERATOR_STATUS_CONTRACT_SCHEMA_VERSION,
        "status": "operator_status_contract_visible_read_only_task_status_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "status_route": BOOTSTRAP_STATUS_ROUTE,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "task_index_route": "GET /api/tasks",
        "task_type": BOOTSTRAP_TASK_TYPE,
        "status_rows": status_rows,
        "status_surface_count": len(status_rows),
        "required_operator_surfaces": [row["surface_key"] for row in status_rows],
        "current_mode_visible_required": True,
        "configured_source_switches_visible_required": True,
        "effective_source_switches_visible_required": True,
        "external_execution_profile_visible_required": True,
        "latest_bootstrap_task_id_visible_required": True,
        "latest_bootstrap_task_status_visible_required": True,
        "latest_bootstrap_current_step_visible_required": True,
        "latest_bootstrap_safe_error_visible_required": True,
        "rate_limit_skipped_state_visible_required": True,
        "source_switches_effective": bool(live_light_sources_enabled),
        "tushare_on_open_effective": bool(live_light_enabled and tushare_on_open),
        "deepseek_on_open_effective": bool(live_light_enabled and deepseek_on_open),
        "external_execution_profile": external_execution_profile,
        "external_execution_profile_provider_stage_allowed": external_execution_profile_provider_stage_allowed,
        "external_execution_profile_model_stage_allowed": external_execution_profile_model_stage_allowed,
        "external_execution_profile_executor_implemented": False,
        "external_execution_profile_calls_provider_model_now": False,
        "profile_source_rate_summary_visible_required": True,
        "symbol_limit_visible_safe": symbol_limit,
        "rate_limit_seconds_visible_safe": rate_limit_seconds,
        "operator_status_read_only": True,
        "operator_status_frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_get_creates_task": False,
        "status_get_calls_provider": False,
        "status_get_calls_model": False,
        "task_index_creates_task": False,
        "task_status_get_creates_task": False,
        "react_initial_render_may_block_on_task": False,
        "react_render_direct_provider_calls": False,
        "safe_summary_only": True,
        "raw_config_values_exposed": False,
        "raw_task_payload_visible_allowed": False,
        "raw_exception_visible_allowed": False,
        "raw_prompt_or_raw_model_output_visible_allowed": False,
        "credential_values_exposed": False,
        "credential_env_key_names_exposed": False,
        "latest_task_success_is_provider_model_evidence": False,
        "rate_limit_skip_is_provider_model_evidence": False,
        "operator_status_contract_is_provider_execution_evidence": False,
        "operator_status_contract_is_model_execution_evidence": False,
        "operator_status_contract_is_production_evidence": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_operator_summary_contract(
    *,
    active_mode: str,
    safe_config_contract: dict[str, Any],
    runtime_config_ownership_invariant_contract: dict[str, Any],
    runtime_mode_acceptance_contract: dict[str, Any],
    task_creation_invariant_contract: dict[str, Any],
    live_light_task_control_contract: dict[str, Any],
    live_light_operator_status_contract: dict[str, Any],
    live_light_execution_request_handoff_contract: dict[str, Any],
    live_light_promotion_gate_contract: dict[str, Any],
    runtime_hard_boundary_contract: dict[str, Any],
    latest_bootstrap_task_status: dict[str, Any],
    latest_acceptance_dry_run_status: dict[str, Any],
    latest_execution_request_status: dict[str, Any],
    latest_quant_projection_status: dict[str, Any],
) -> dict[str, Any]:
    row_templates = {
        "cache_only": {
            "operator_label": "Cache only",
            "display_status": "safe_read_only_cache",
            "allowed_operator_actions": ["view_cache", "inspect_status_contracts"],
            "blocked_operator_actions": [
                "page_open_task_creation",
                "safe_search_submit_task_creation",
                "provider_model_execution",
                "config_writeback",
            ],
        },
        "manual": {
            "operator_label": "Manual",
            "display_status": "explicit_post_task_only",
            "allowed_operator_actions": ["view_cache", "click_explicit_task_buttons"],
            "blocked_operator_actions": [
                "page_open_task_creation",
                "search_typing_task_creation",
                "provider_model_execution_without_task_contract",
                "config_writeback",
            ],
        },
        "live_light": {
            "operator_label": "Live light",
            "display_status": "bounded_background_task_after_cache_render",
            "allowed_operator_actions": [
                "view_cache_first",
                "create_or_reuse_rate_limited_bootstrap_task_after_cache_render",
                "safe_search_submit_may_create_local_projection_task",
                "submit_execution_request_before_provider_model_acceptance",
            ],
            "blocked_operator_actions": [
                "react_render_provider_call",
                "provider_model_execution_without_execution_request",
                "full_pool_or_deep_scan_on_open",
                "config_writeback",
                "production_promotion_from_local_contracts",
            ],
        },
        "live_full": {
            "operator_label": "Live full",
            "display_status": "reserved_disabled_requires_future_authorization",
            "allowed_operator_actions": ["view_reserved_state"],
            "blocked_operator_actions": [
                "page_open_task_creation",
                "full_pool_or_deep_scan_on_open",
                "provider_model_execution",
                "config_writeback",
            ],
        },
    }
    acceptance_rows_by_mode = {
        str(row.get("mode") or ""): row
        for row in runtime_mode_acceptance_contract.get("acceptance_rows", [])
        if isinstance(row, dict)
    }
    summary_rows: list[dict[str, Any]] = []
    for mode in BOOTSTRAP_MODES:
        template = row_templates[mode]
        acceptance_row = acceptance_rows_by_mode.get(mode, {})
        summary_rows.append(
            {
                "mode": mode,
                "active": active_mode == mode,
                **template,
                "trigger_policy_summary_visible": True,
                "trigger_policy_source_contract": "runtime_mode_acceptance_contract",
                "page_open_task_allowed": acceptance_row.get("page_open_task_allowed") is True,
                "search_submit_task_allowed": acceptance_row.get("search_submit_task_allowed") is True,
                "manual_button_task_allowed": acceptance_row.get("manual_button_task_allowed") is True,
                "live_light_background_task_allowed": (
                    acceptance_row.get("live_light_background_task_allowed") is True
                ),
                "provider_model_execution_allowed": (
                    acceptance_row.get("provider_model_execution_allowed") is True
                ),
                "provider_model_execution_surface": str(
                    acceptance_row.get("provider_model_execution_surface") or "none"
                ),
                "provider_model_direct_execution_allowed": (
                    acceptance_row.get("provider_model_direct_execution_allowed") is True
                ),
                "provider_model_requires_explicit_post_task": (
                    acceptance_row.get("provider_model_requires_explicit_post_task") is True
                ),
                "provider_model_execution_requires_task_contract": (
                    acceptance_row.get("provider_model_execution_requires_task_contract") is True
                ),
                "provider_model_execution_requires_execution_request": (
                    acceptance_row.get("provider_model_execution_requires_execution_request") is True
                ),
                "full_pool_or_deep_scan_allowed": (
                    acceptance_row.get("full_pool_or_deep_scan_allowed") is True
                ),
                "frontend_visible": True,
                "frontend_editable": False,
                "frontend_writeback_allowed": False,
                "status_endpoint_writeback_allowed": False,
                "cache_get_creates_task": False,
                "react_initial_render_creates_task": False,
                "search_typing_creates_task": False,
                "operator_row_is_production_evidence": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    active_row = next(row for row in summary_rows if row["active"])
    allowed_actions = list(active_row["allowed_operator_actions"])
    blocked_actions = list(active_row["blocked_operator_actions"])
    return {
        "schema_version": BOOTSTRAP_OPERATOR_SUMMARY_SCHEMA_VERSION,
        "status": "runtime_operator_summary_visible_read_only",
        "mode": active_mode,
        "summary_rows": summary_rows,
        "summary_row_count": len(summary_rows),
        "active_mode_operator_label": active_row["operator_label"],
        "active_mode_display_status": active_row["display_status"],
        "release_blocker_summary_visible": True,
        "release_blocker_source_contract": "live_light_promotion_gate_contract",
        "release_real_provider_model_evidence_complete": (
            live_light_promotion_gate_contract.get("real_provider_model_evidence_complete") is True
        ),
        "release_browser_nonblocking_runtime_evidence_required": (
            live_light_promotion_gate_contract.get("browser_nonblocking_runtime_evidence_required") is True
        ),
        "release_ledger_redaction_review_required": (
            live_light_promotion_gate_contract.get("ledger_redaction_review_required") is True
        ),
        "release_fresh_local_gate_run_required": (
            live_light_promotion_gate_contract.get("fresh_local_gate_run_required") is True
        ),
        "release_remote_ci_status_known": (
            live_light_promotion_gate_contract.get("remote_ci_status_known") is True
        ),
        "release_remote_ci_green": live_light_promotion_gate_contract.get("remote_ci_green") is True,
        "release_github_api_called": live_light_promotion_gate_contract.get("github_api_called") is True,
        "release_production_promotion_review_required": (
            live_light_promotion_gate_contract.get("production_promotion_review_required") is True
        ),
        "release_ready_for_promotion": live_light_promotion_gate_contract.get("ready_for_release_promotion")
        is True,
        "release_local_contracts_are_production_evidence": (
            live_light_promotion_gate_contract.get("local_contracts_are_production_evidence") is True
        ),
        "release_blocker_summary_is_production_evidence": False,
        "operator_trigger_policy_summary_visible": True,
        "operator_trigger_policy_source_contract": "runtime_mode_acceptance_contract",
        "active_page_open_task_allowed": active_row["page_open_task_allowed"],
        "active_search_submit_task_allowed": active_row["search_submit_task_allowed"],
        "active_manual_button_task_allowed": active_row["manual_button_task_allowed"],
        "active_live_light_background_task_allowed": active_row["live_light_background_task_allowed"],
        "active_provider_model_execution_allowed": active_row["provider_model_execution_allowed"],
        "active_provider_model_execution_surface": active_row["provider_model_execution_surface"],
        "active_provider_model_direct_execution_allowed": active_row[
            "provider_model_direct_execution_allowed"
        ],
        "active_provider_model_requires_explicit_post_task": active_row[
            "provider_model_requires_explicit_post_task"
        ],
        "active_provider_model_execution_requires_task_contract": active_row[
            "provider_model_execution_requires_task_contract"
        ],
        "active_provider_model_execution_requires_execution_request": active_row[
            "provider_model_execution_requires_execution_request"
        ],
        "active_full_pool_or_deep_scan_allowed": active_row["full_pool_or_deep_scan_allowed"],
        "trigger_policy_summary_is_production_evidence": False,
        "allowed_operator_actions": allowed_actions,
        "blocked_operator_actions": blocked_actions,
        "allowed_operator_action_count": len(allowed_actions),
        "blocked_operator_action_count": len(blocked_actions),
        "mode_rows_visible_required": True,
        "config_rows_visible_required": True,
        "config_ownership_visible_required": True,
        "runtime_vocab_source_visible_required": True,
        "runtime_mode_vocab_source": safe_config_contract.get("runtime_mode_vocab_source"),
        "default_mode_source": safe_config_contract.get("default_mode_source"),
        "external_execution_profile_vocab_source": safe_config_contract.get(
            "external_execution_profile_vocab_source"
        ),
        "external_execution_profile_default_source": safe_config_contract.get(
            "external_execution_profile_default_source"
        ),
        "effective_source_switches_visible_required": True,
        "external_execution_profile_visible_required": True,
        "latest_bootstrap_task_visible_required": True,
        "latest_search_quant_projection_visible_required": True,
        "provider_model_execution_flags_visible_required": True,
        "production_blockers_visible_required": True,
        "hard_boundary_summary_visible": True,
        "hard_boundary_source_contract": "runtime_hard_boundary_contract",
        "hard_boundary_row_count": runtime_hard_boundary_contract.get("boundary_row_count"),
        "hard_boundary_blocking_count": runtime_hard_boundary_contract.get("blocking_boundary_count"),
        "hard_boundary_get_cache_external_calls_allowed": (
            runtime_hard_boundary_contract.get("get_cache_api_direct_external_calls_allowed") is True
        ),
        "hard_boundary_react_render_provider_calls_allowed": (
            runtime_hard_boundary_contract.get("react_render_direct_provider_calls_allowed") is True
        ),
        "hard_boundary_fastapi_startup_external_calls_allowed": (
            runtime_hard_boundary_contract.get("fastapi_startup_external_calls_allowed") is True
        ),
        "hard_boundary_post_task_worker_local_fallback_required": (
            runtime_hard_boundary_contract.get("external_work_requires_post_task_worker_or_local_fallback")
            is True
        ),
        "hard_boundary_call_ledger_required": (
            runtime_hard_boundary_contract.get("call_ledger_required_for_provider_calls") is True
        ),
        "hard_boundary_model_ledger_required_for_deepseek": (
            runtime_hard_boundary_contract.get("model_ledger_required_for_deepseek_calls") is True
        ),
        "hard_boundary_deepseek_is_data_source": (
            runtime_hard_boundary_contract.get("deepseek_is_data_source") is True
        ),
        "hard_boundary_real_trading_allowed": runtime_hard_boundary_contract.get("real_trading_allowed")
        is True,
        "hard_boundary_token_key_frontend_log_packet_cache_allowed": (
            runtime_hard_boundary_contract.get("token_key_frontend_log_packet_cache_allowed") is True
        ),
        "hard_boundary_summary_is_production_evidence": False,
        "safe_config_contract_status": safe_config_contract.get("status"),
        "configured_source_switches_visible": bool(
            safe_config_contract.get("configured_source_switches_visible")
        ),
        "effective_source_switches_mode_gated": bool(
            safe_config_contract.get("effective_source_switches_mode_gated")
        ),
        "effective_sources_enabled": bool(safe_config_contract.get("effective_sources_enabled")),
        "effective_external_execution_profile": safe_config_contract.get("effective_external_execution_profile"),
        "external_execution_profile_provider_stage_allowed": (
            safe_config_contract.get("external_execution_profile_provider_stage_allowed") is True
        ),
        "external_execution_profile_model_stage_allowed": (
            safe_config_contract.get("external_execution_profile_model_stage_allowed") is True
        ),
        "external_execution_profile_executor_implemented": False,
        "external_execution_profile_calls_provider_model_now": False,
        "provider_model_enablement_summary_visible": True,
        "provider_model_enablement_source_config": PROVIDER_MODEL_ENABLEMENT_CONFIG_KEY,
        "provider_model_enablement_configured": bool(
            safe_config_contract.get("configured_provider_model_enablement")
        ),
        "provider_model_enablement_effective": bool(
            safe_config_contract.get("effective_provider_model_enablement")
        ),
        "provider_model_enablement_requires_live_light": (
            safe_config_contract.get("provider_model_enablement_requires_live_light") is True
        ),
        "provider_model_enablement_requires_execution_request": (
            safe_config_contract.get("provider_model_enablement_requires_execution_request") is True
        ),
        "provider_model_enablement_requires_promotion": (
            safe_config_contract.get("provider_model_enablement_requires_promotion") is True
        ),
        "provider_model_enablement_creates_task": (
            safe_config_contract.get("provider_model_enablement_creates_task") is True
        ),
        "provider_model_enablement_creates_provider_model_task": (
            safe_config_contract.get("provider_model_enablement_creates_provider_model_task") is True
        ),
        "provider_model_enablement_calls_provider_model_now": (
            safe_config_contract.get("provider_model_enablement_calls_provider_model_now") is True
        ),
        "provider_model_enablement_frontend_writeback_allowed": (
            safe_config_contract.get("provider_model_enablement_frontend_writeback_allowed") is True
        ),
        "provider_model_enablement_summary_is_production_evidence": False,
        "operator_profile_source_rate_summary_visible": True,
        "operator_profile_source_rate_summary_status": (
            "profile_selected_executor_pending"
            if safe_config_contract.get("effective_sources_enabled") is True
            and safe_config_contract.get("effective_external_execution_profile") != DEFAULT_EXTERNAL_EXECUTION_PROFILE
            else "plan_only_or_sources_disabled"
        ),
        "operator_rate_limit_seconds_visible_safe": live_light_operator_status_contract.get(
            "rate_limit_seconds_visible_safe"
        ),
        "config_ownership_row_count": runtime_config_ownership_invariant_contract.get("ownership_row_count"),
        "config_ownership_audit_id": runtime_config_ownership_invariant_contract.get("ownership_audit_id"),
        "config_reference_audit_id": runtime_config_ownership_invariant_contract.get(
            "linked_runtime_config_reference_audit_id"
        ),
        "config_audit_input_surface": "safe_reference_and_ownership_rows_only",
        "config_audit_visible_required": True,
        "config_audit_includes_raw_values": False,
        "config_audit_includes_credential_values": False,
        "config_audit_is_production_evidence": False,
        "bootstrap_local_env_fallback_count": runtime_config_ownership_invariant_contract.get(
            "bootstrap_local_env_fallback_count"
        ),
        "global_config_allowlist_promotion_pending_count": runtime_config_ownership_invariant_contract.get(
            "global_config_allowlist_promotion_pending_count"
        ),
        "runtime_mode_acceptance_row_count": runtime_mode_acceptance_contract.get("acceptance_row_count"),
        "task_creation_invariant_surface_row_count": task_creation_invariant_contract.get("surface_row_count"),
        "task_creation_invariant_allowed_surface_count": task_creation_invariant_contract.get(
            "allowed_task_surface_count"
        ),
        "task_control_contract_visible": True,
        "task_control_row_count": live_light_task_control_contract.get("control_row_count"),
        "task_control_cancel_route": live_light_task_control_contract.get("cancel_route"),
        "task_control_retry_route": live_light_task_control_contract.get("retry_route"),
        "task_control_manual_only": live_light_task_control_contract.get("manual_operator_action_required")
        is True,
        "task_control_auto_retry_enabled": live_light_task_control_contract.get("auto_retry_enabled") is True,
        "task_control_safe_reason_required": live_light_task_control_contract.get("control_reason_sanitized")
        is True,
        "task_control_call_ledger_required": live_light_task_control_contract.get("control_call_ledger_required")
        is True,
        "task_control_is_production_evidence": False,
        "operator_status_surface_count": live_light_operator_status_contract.get("status_surface_count"),
        "provider_model_handoff_contract_visible": True,
        "provider_model_handoff_row_count": live_light_execution_request_handoff_contract.get("handoff_row_count"),
        "provider_model_handoff_route": live_light_execution_request_handoff_contract.get(
            "execution_request_route"
        ),
        "provider_model_handoff_route_implemented": live_light_execution_request_handoff_contract.get(
            "execution_request_route_implemented"
        )
        is True,
        "provider_model_handoff_receipt_service_implemented": live_light_execution_request_handoff_contract.get(
            "local_execution_request_receipt_service_implemented"
        )
        is True,
        "provider_model_handoff_creates_provider_model_task": live_light_execution_request_handoff_contract.get(
            "execution_request_creates_provider_model_task"
        )
        is True,
        "provider_model_handoff_is_production_evidence": live_light_execution_request_handoff_contract.get(
            "local_handoff_contract_is_production_evidence"
        )
        is True,
        "latest_bootstrap_task_found": latest_bootstrap_task_status.get("task_found") is True,
        "latest_bootstrap_task_status": latest_bootstrap_task_status.get("status"),
        "latest_acceptance_dry_run_visible_required": True,
        "latest_acceptance_dry_run_receipt_found": latest_acceptance_dry_run_status.get("receipt_found")
        is True,
        "latest_acceptance_dry_run_status": latest_acceptance_dry_run_status.get("status"),
        "latest_acceptance_dry_run_ready_for_execution_request": latest_acceptance_dry_run_status.get(
            "dry_run_ready_for_execution_request"
        )
        is True,
        "latest_acceptance_dry_run_lookup_creates_task": latest_acceptance_dry_run_status.get(
            "lookup_creates_task"
        )
        is True,
        "latest_acceptance_dry_run_is_production_evidence": latest_acceptance_dry_run_status.get(
            "is_production_evidence"
        )
        is True,
        "latest_execution_request_visible_required": True,
        "latest_execution_request_receipt_found": latest_execution_request_status.get("receipt_found")
        is True,
        "latest_execution_request_status": latest_execution_request_status.get("status"),
        "latest_execution_request_ready": latest_execution_request_status.get("local_execution_request_ready")
        is True,
        "latest_execution_request_scope_hash_matches_latest": latest_execution_request_status.get(
            "scope_hash_matches_latest"
        )
        is True,
        "latest_execution_request_lookup_creates_task": latest_execution_request_status.get(
            "lookup_creates_task"
        )
        is True,
        "latest_execution_request_is_production_evidence": latest_execution_request_status.get(
            "production_live_light_complete"
        )
        is True,
        "latest_quant_projection_task_found": latest_quant_projection_status.get("task_found") is True,
        "latest_quant_projection_status": latest_quant_projection_status.get("status"),
        "provider_model_task_created": latest_execution_request_status.get("provider_model_task_created")
        is True,
        "provider_model_task_dispatched": latest_execution_request_status.get("provider_model_task_dispatched")
        is True,
        "provider_model_execution_implemented": latest_execution_request_status.get(
            "provider_model_execution_implemented"
        )
        is True,
        "provider_model_operator_summary_is_production_evidence": False,
        "frontend_visible": True,
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "status_get_creates_task": False,
        "cache_get_creates_task": False,
        "react_initial_render_creates_task": False,
        "react_render_direct_provider_calls": False,
        "search_typing_creates_task": False,
        "safe_summary_only": True,
        "raw_config_values_exposed": False,
        "raw_task_payload_visible_allowed": False,
        "raw_prompt_or_raw_model_output_visible_allowed": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "latest_task_success_is_provider_model_evidence": False,
        "operator_summary_is_provider_execution_evidence": False,
        "operator_summary_is_model_execution_evidence": False,
        "operator_summary_is_production_evidence": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_promotion_gate_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    live_light_sources_enabled: bool,
    symbol_limit: int,
    rate_limit_seconds: int,
) -> dict[str, Any]:
    layer_rows = [
        {
            "layer_key": "l1_mode_contract",
            "layer": "L1",
            "status": "passed_local_mode_contract_visible",
            "closes": "runtime_vocabulary_and_forbidden_boundaries_visible",
            "current_evidence": ["safe_config_contract", "mode_rows", "trigger_matrix"],
            "required_evidence": [
                "cache_only/manual/live_light/live_full wording",
                "default-off configuration",
                "GET/render/startup silence",
                "no secret/no trade/no action mutation",
            ],
            "not_enough": ["roadmap paragraph without packet contract"],
            "local_contract_visible": True,
            "real_provider_model_required": False,
            "remote_ci_required": False,
            "production_blocker": False,
        },
        {
            "layer_key": "l2_local_bootstrap_readiness",
            "layer": "L2",
            "status": "passed_local_bootstrap_scaffold_visible_provider_model_pending",
            "closes": "local_task_shape_can_be_audited_before_execution",
            "current_evidence": [
                "local bootstrap task skeleton",
                "staged run plan",
                "rate-limit/session dedupe",
                "model-ledger preview",
                "dry-run/preflight receipts",
            ],
            "required_evidence": [
                "safe config rows",
                "task catalog route",
                "safe payload summary",
                "local call ledger",
                "model-ledger preview",
            ],
            "not_enough": ["skeleton as provider/model acceptance", "dry-run as production evidence"],
            "local_contract_visible": True,
            "real_provider_model_required": False,
            "remote_ci_required": False,
            "production_blocker": False,
        },
        {
            "layer_key": "l3_real_provider_model_evidence",
            "layer": "L3",
            "status": "blocked_real_provider_model_evidence_pending",
            "closes": "bounded_live_light_external_work_actually_ran_under_approved_mode",
            "current_evidence": ["local contracts", "runbook", "acceptance dry-run"],
            "required_evidence": [
                "real Tushare call ledger for trade_cal/daily/daily_basic/moneyflow",
                "real DeepSeek model ledger when enabled",
                "browser nonblocking runtime evidence",
                "ledger redaction review",
                "safe failure rows",
            ],
            "not_enough": ["local receipts", "fixtures", "mocked ledgers", "credential-presence booleans"],
            "local_contract_visible": True,
            "real_provider_model_required": True,
            "remote_ci_required": False,
            "production_blocker": True,
        },
        {
            "layer_key": "l4_release_promotion",
            "layer": "L4",
            "status": "blocked_remote_ci_and_promotion_review_pending",
            "closes": "feature_can_be_promoted_as_reliable_app_workflow",
            "current_evidence": ["local contract gates only"],
            "required_evidence": [
                "fresh local push gate",
                "remote CI green",
                "production promotion review",
                "release-safe documentation",
                "secret/artifact scan",
                "no trading/action mutation regression",
            ],
            "not_enough": ["green local contract script", "one-off manual run"],
            "local_contract_visible": True,
            "real_provider_model_required": True,
            "remote_ci_required": True,
            "production_blocker": True,
        },
    ]
    return {
        "schema_version": BOOTSTRAP_PROMOTION_GATE_CONTRACT_SCHEMA_VERSION,
        "status": "promotion_gate_visible_release_blockers_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "status_route": BOOTSTRAP_STATUS_ROUTE,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "acceptance_dry_run_route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
        "execution_request_route": PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE,
        "provider_model_acceptance_route": FUTURE_BOOTSTRAP_PROVIDER_MODEL_ACCEPTANCE_ROUTE,
        "layer_rows": layer_rows,
        "promotion_layer_count": len(layer_rows),
        "required_layer_order": [row["layer_key"] for row in layer_rows],
        "local_mode_contract_visible": True,
        "local_bootstrap_readiness_visible": True,
        "real_provider_model_evidence_complete": False,
        "production_promotion_review_complete": False,
        "remote_ci_status_known": False,
        "remote_ci_green": False,
        "github_api_called": False,
        "fresh_local_gate_run_required": True,
        "remote_ci_green_required": True,
        "production_promotion_review_required": True,
        "local_contracts_may_pass": True,
        "local_contracts_are_production_evidence": False,
        "provider_model_execution_required_before_promotion": True,
        "browser_nonblocking_runtime_evidence_required": True,
        "ledger_redaction_review_required": True,
        "secret_artifact_scan_required": True,
        "release_safe_docs_required": True,
        "ready_for_provider_execution_design": live_light_enabled,
        "ready_for_local_research_client_iteration": live_light_enabled,
        "ready_for_release_promotion": False,
        "production_live_light_complete": False,
        "allowed_next_step": "collect_real_provider_model_evidence_then_remote_ci_promotion_review",
        "not_allowed_next_steps": [
            "treat local bootstrap skeleton as production evidence",
            "treat acceptance dry-run as real provider/model evidence",
            "promote live_light without remote CI green",
            "promote live_light without ledger redaction review",
            "promote live_light while provider/model execution remains unimplemented",
        ],
        "symbol_limit_visible_safe": symbol_limit,
        "rate_limit_seconds_visible_safe": rate_limit_seconds,
        "source_switches_effective": bool(live_light_sources_enabled),
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _live_light_worker_dispatch_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    live_light_sources_enabled: bool,
) -> dict[str, Any]:
    dispatch_rows = [
        {
            "stage_key": "bootstrap_entrypoint",
            "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "current_runtime": "local_task_skeleton",
            "future_queue": "local_maintenance",
            "worker_dispatch_implemented": False,
            "provider_or_model_execution_allowed_now": False,
            "requires_execution_request": False,
            "safe_ledger_required": True,
        },
        {
            "stage_key": "tushare_light_refresh",
            "route": FUTURE_BOOTSTRAP_PROVIDER_MODEL_ACCEPTANCE_ROUTE,
            "current_runtime": "provider_execution_pending",
            "future_queue": "provider_refresh",
            "allowed_apis": list(ACCEPTANCE_DRY_RUN_ALLOWED_APIS),
            "worker_dispatch_implemented": False,
            "provider_or_model_execution_allowed_now": False,
            "requires_execution_request": True,
            "safe_ledger_required": True,
        },
        {
            "stage_key": "factor_light_runtime",
            "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "current_runtime": "local_compute_pending",
            "future_queue": "local_compute",
            "worker_dispatch_implemented": False,
            "provider_or_model_execution_allowed_now": False,
            "requires_execution_request": False,
            "safe_ledger_required": True,
        },
        {
            "stage_key": "next_session_cache_refresh",
            "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "current_runtime": "local_compute_pending",
            "future_queue": "local_compute",
            "worker_dispatch_implemented": False,
            "provider_or_model_execution_allowed_now": False,
            "requires_execution_request": False,
            "cache_lineage_required": True,
            "safe_ledger_required": True,
        },
        {
            "stage_key": "deepseek_pro_explanation",
            "route": FUTURE_BOOTSTRAP_PROVIDER_MODEL_ACCEPTANCE_ROUTE,
            "current_runtime": "model_execution_pending",
            "future_queue": "model_explain",
            "worker_dispatch_implemented": False,
            "provider_or_model_execution_allowed_now": False,
            "requires_execution_request": True,
            "requires_data_ready": True,
            "model_ledger_required": True,
            "safe_ledger_required": True,
        },
    ]
    return {
        "schema_version": BOOTSTRAP_WORKER_DISPATCH_CONTRACT_SCHEMA_VERSION,
        "status": "worker_dispatch_contract_visible_executor_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_type": BOOTSTRAP_TASK_TYPE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "dispatch_rows": dispatch_rows,
        "dispatch_row_count": len(dispatch_rows),
        "declared_future_queues": [
            "provider_refresh",
            "model_explain",
            "local_compute",
            "local_maintenance",
        ],
        "current_runtime": "local_fallback_task_skeleton",
        "post_task_boundary_required": True,
        "worker_or_local_fallback_required": True,
        "local_fallback_allowed_now": True,
        "celery_dispatch_implemented": False,
        "redis_broker_required_for_current_contract": False,
        "redis_broker_pinged": False,
        "worker_process_started": False,
        "scheduler_auto_dispatch_allowed": False,
        "cache_get_dispatches_worker": False,
        "status_get_dispatches_worker": False,
        "react_render_dispatches_worker": False,
        "fastapi_startup_dispatches_worker": False,
        "page_open_direct_worker_dispatch_allowed": False,
        "react_after_cache_render_may_create_post_task": live_light_enabled,
        "post_task_may_route_to_worker_in_future": True,
        "provider_worker_requires_execution_request": True,
        "model_worker_requires_execution_request": True,
        "provider_worker_requires_call_ledger": True,
        "model_worker_requires_model_ledger": True,
        "local_compute_may_refresh_from_existing_cache": True,
        "local_compute_may_synthesize_provider_rows": False,
        "local_compute_may_synthesize_model_output": False,
        "unbounded_queue_allowed": False,
        "rate_limit_must_apply_before_dispatch": True,
        "session_dedupe_must_apply_before_dispatch": True,
        "source_switches_effective": bool(live_light_sources_enabled),
        "worker_dispatch_contract_is_provider_execution_evidence": False,
        "worker_dispatch_contract_is_model_execution_evidence": False,
        "worker_dispatch_contract_is_production_evidence": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _live_light_unified_startup_task_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    live_light_sources_enabled: bool,
    tushare_on_open: bool,
    deepseek_on_open: bool,
    external_execution_profile: str,
    external_execution_profile_provider_stage_allowed: bool,
    external_execution_profile_model_stage_allowed: bool,
    symbol_limit: int,
    rate_limit_seconds: int,
    deepseek_model: str,
    background_task_contract: dict[str, Any],
    stage_dependency_contract: dict[str, Any],
    worker_dispatch_contract: dict[str, Any],
    startup_readiness_contract: dict[str, Any],
) -> dict[str, Any]:
    stage_rows = [
        {
            "stage_key": "cache_first_status_read",
            "stage_order": 1,
            "stage_kind": "cache_status",
            "route": BOOTSTRAP_STATUS_ROUTE,
            "current_runtime": "read_only_status_cache",
            "required_input": "existing local cache and safe runtime config rows",
            "required_output": "mode, source switches, task route, and limits visible before POST",
            "future_external_provider": None,
            "external_execution_profile": external_execution_profile,
            "profile_required": "any_profile",
            "profile_stage_allowed": True,
            "requires_execution_request_now": False,
            "requires_call_ledger": True,
            "requires_model_ledger": False,
        },
        {
            "stage_key": "startup_task_envelope",
            "stage_order": 2,
            "stage_kind": "local_task",
            "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "current_runtime": "local_task_skeleton",
            "required_input": "cache-first render complete, mode live_light, rate limit window",
            "required_output": "one bounded background task or safe rate-limit reuse",
            "future_external_provider": None,
            "external_execution_profile": external_execution_profile,
            "profile_required": "any_profile",
            "profile_stage_allowed": True,
            "requires_execution_request_now": False,
            "requires_call_ledger": True,
            "requires_model_ledger": False,
        },
        {
            "stage_key": "scope_resolution",
            "stage_order": 3,
            "stage_kind": "local_scope",
            "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "current_runtime": "safe_scope_contract_only",
            "required_input": "current target, searched symbol, symbols, watchlist, or holdings",
            "required_output": "deduped safe scope hash with symbol-limit truncation",
            "future_external_provider": None,
            "external_execution_profile": external_execution_profile,
            "profile_required": "any_profile",
            "profile_stage_allowed": True,
            "requires_execution_request_now": False,
            "requires_call_ledger": True,
            "requires_model_ledger": False,
        },
        {
            "stage_key": "tushare_light_refresh",
            "stage_order": 4,
            "stage_kind": "provider_light",
            "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "current_runtime": "provider_execution_pending",
            "required_input": "safe scope and Tushare source switch",
            "required_output": "fresh provider facts or provider-gap safe state",
            "future_external_provider": "tushare",
            "allowed_apis": list(DEFAULT_LIGHT_TUSHARE_APIS),
            "source_switch_effective": bool(live_light_enabled and live_light_sources_enabled and tushare_on_open),
            "external_execution_profile": external_execution_profile,
            "profile_required": "light_provider_or_light_provider_model",
            "profile_stage_allowed": external_execution_profile_provider_stage_allowed,
            "profile_inactive_reason": ""
            if external_execution_profile_provider_stage_allowed
            else "external_execution_profile_does_not_allow_provider_stage",
            "requires_execution_request_now": True,
            "requires_call_ledger": True,
            "requires_model_ledger": False,
        },
        {
            "stage_key": "factor_light_runtime",
            "stage_order": 5,
            "stage_kind": "local_compute",
            "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "current_runtime": "local_compute_pending",
            "required_input": "provider facts, cache facts, or visible provider-gap safe skip",
            "required_output": "Factor light and Factor Quant Hub cache projection metadata",
            "future_external_provider": None,
            "external_execution_profile": external_execution_profile,
            "profile_required": "any_profile",
            "profile_stage_allowed": True,
            "requires_execution_request_now": False,
            "requires_call_ledger": True,
            "requires_model_ledger": False,
        },
        {
            "stage_key": "next_session_cache_refresh",
            "stage_order": 6,
            "stage_kind": "local_compute",
            "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "current_runtime": "local_compute_pending",
            "required_input": "Factor light runtime or safe skip status",
            "required_output": "Next Session cache and operation map lineage metadata",
            "future_external_provider": None,
            "external_execution_profile": external_execution_profile,
            "profile_required": "any_profile",
            "profile_stage_allowed": True,
            "requires_execution_request_now": False,
            "requires_call_ledger": True,
            "requires_model_ledger": False,
        },
        {
            "stage_key": "deepseek_pro_explanation",
            "stage_order": 7,
            "stage_kind": "model_explanation",
            "route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "current_runtime": "model_execution_pending",
            "required_input": "Factor and Next Session data ready, or explicit safe skip",
            "required_output": "whitelisted explanation fields with model ledger",
            "future_external_provider": "deepseek",
            "source_switch_effective": bool(live_light_enabled and live_light_sources_enabled and deepseek_on_open),
            "external_execution_profile": external_execution_profile,
            "profile_required": "light_provider_model",
            "profile_stage_allowed": external_execution_profile_model_stage_allowed,
            "profile_inactive_reason": ""
            if external_execution_profile_model_stage_allowed
            else "external_execution_profile_does_not_allow_model_stage",
            "deepseek_model": deepseek_model,
            "allowed_output_fields": list(DEEPSEEK_EXPLANATION_FIELDS),
            "requires_execution_request_now": True,
            "requires_call_ledger": True,
            "requires_model_ledger": True,
            "requires_data_ready": True,
            "deepseek_is_data_source": False,
        },
        {
            "stage_key": "ui_polling_and_cache_refresh",
            "stage_order": 8,
            "stage_kind": "ui_status",
            "route": "GET /api/tasks/{task_id}",
            "current_runtime": "status_polling_contract_only",
            "required_input": "created task id or rate-limit reuse state",
            "required_output": "nonblocking task status, safe error, and last-good cache refresh hint",
            "future_external_provider": None,
            "external_execution_profile": external_execution_profile,
            "profile_required": "any_profile",
            "profile_stage_allowed": True,
            "requires_execution_request_now": False,
            "requires_call_ledger": True,
            "requires_model_ledger": False,
        },
    ]
    common_flags = {
        "stage_status_must_be_pollable": True,
        "safe_skip_allowed": True,
        "cache_get_may_execute_stage": False,
        "react_render_may_execute_stage": False,
        "fastapi_startup_may_execute_stage": False,
        "search_typing_may_execute_stage": False,
        "provider_or_model_execution_allowed_now": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "worker_dispatch_implemented": False,
        "local_compute_may_synthesize_provider_rows": False,
        "local_compute_may_synthesize_model_output": False,
        "deepseek_may_overwrite_numeric_or_action_fields": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "row_is_production_evidence": False,
    }
    stage_rows = [{**row, **common_flags} for row in stage_rows]
    required_stage_keys = [row["stage_key"] for row in stage_rows]
    return {
        "schema_version": BOOTSTRAP_UNIFIED_STARTUP_TASK_CONTRACT_SCHEMA_VERSION,
        "status": "unified_startup_task_contract_visible_executor_pending"
        if live_light_enabled
        else "unified_startup_task_contract_inactive_until_live_light_mode",
        "mode": active_mode,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_type": BOOTSTRAP_TASK_TYPE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "trigger_surface": "react_mounted_after_initial_cache_render_or_safe_search_submit",
        "stage_rows": stage_rows,
        "stage_count": len(stage_rows),
        "required_stage_keys": required_stage_keys,
        "mode_gate": "live_light",
        "active_mode_live_light": live_light_enabled,
        "sources_effective": live_light_sources_enabled,
        "symbol_limit": symbol_limit,
        "rate_limit_seconds": rate_limit_seconds,
        "allowed_symbol_sources": ["current_target", "searched_symbol", "symbols", "watchlist", "holdings"],
        "allowed_light_tushare_apis": list(DEFAULT_LIGHT_TUSHARE_APIS),
        "deepseek_model": deepseek_model,
        "deepseek_allowed_output_fields": list(DEEPSEEK_EXPLANATION_FIELDS),
        "external_execution_profile": external_execution_profile,
        "external_execution_profile_provider_stage_allowed": external_execution_profile_provider_stage_allowed,
        "external_execution_profile_model_stage_allowed": external_execution_profile_model_stage_allowed,
        "external_execution_profile_executor_implemented": False,
        "external_execution_profile_calls_provider_model_now": False,
        "provider_stage_planned_by_profile": external_execution_profile_provider_stage_allowed,
        "model_stage_planned_by_profile": external_execution_profile_model_stage_allowed,
        "live_light_background_task_allowed_after_cache_render": live_light_enabled,
        "cache_first_render_required": True,
        "post_task_boundary_required": True,
        "worker_or_local_fallback_required": True,
        "ui_nonblocking_required": True,
        "task_status_polling_required": True,
        "rate_limit_required": True,
        "session_dedupe_required": True,
        "safe_failure_display_required": True,
        "call_ledger_required": True,
        "model_ledger_required_for_deepseek": True,
        "provider_model_execution_requires_execution_request_now": True,
        "future_live_light_provider_model_stage_inside_startup_task": True,
        "future_external_execution_requires_worker_or_local_fallback": True,
        "source_switch_required_for_provider_model_stages": True,
        "external_execution_profile_required_for_provider_model_stages": True,
        "tushare_source_switch_enabled": bool(
            live_light_enabled and live_light_sources_enabled and tushare_on_open
        ),
        "deepseek_source_switch_enabled": bool(
            live_light_enabled and live_light_sources_enabled and deepseek_on_open
        ),
        "cache_get_creates_task": False,
        "status_get_creates_task": False,
        "react_initial_render_creates_task": False,
        "react_render_calls_provider": False,
        "fastapi_startup_creates_task": False,
        "search_typing_creates_task": False,
        "frontend_direct_provider_call_allowed": False,
        "frontend_direct_model_call_allowed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "worker_dispatch_implemented": False,
        "celery_dispatch_implemented": False,
        "scheduler_auto_dispatch_allowed": False,
        "deepseek_is_data_source": False,
        "deepseek_may_overwrite_numeric_or_action_fields": False,
        "radar_candidate_is_buy_instruction": False,
        "token_key_exposure_allowed": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "linked_background_task_schema_version": background_task_contract.get("schema_version"),
        "linked_stage_dependency_schema_version": stage_dependency_contract.get("schema_version"),
        "linked_stage_dependency_stage_count": stage_dependency_contract.get("stage_count"),
        "linked_worker_dispatch_schema_version": worker_dispatch_contract.get("schema_version"),
        "linked_worker_dispatch_row_count": worker_dispatch_contract.get("dispatch_row_count"),
        "linked_startup_readiness_schema_version": startup_readiness_contract.get("schema_version"),
        "linked_startup_readiness_row_count": startup_readiness_contract.get("readiness_row_count"),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
        "unified_startup_task_contract_is_execution_evidence": False,
        "unified_startup_task_contract_is_production_evidence": False,
        "production_live_light_complete": False,
    }


def _search_quant_projection_workflow_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    symbol_limit: int,
    rate_limit_seconds: int,
) -> dict[str, Any]:
    return {
        "schema_version": "command_center_search_quant_projection_workflow_contract.v1",
        "status": "search_quant_projection_task_contract_visible_provider_model_pending",
        "mode": active_mode,
        "surface": "searched_symbol_quant_projection",
        "display_action": "生成 3.0 量化推演",
        "allowed_modes": ["manual", "live_light"],
        "cache_only_allowed_to_create_task": False,
        "manual_requires_explicit_button": True,
        "live_light_requires_explicit_search_action": True,
        "search_input_creates_task": False,
        "react_render_creates_task": False,
        "cache_get_creates_task": False,
        "react_render_calls_provider": False,
        "route_sequence": [
            SEARCH_QUANT_PROJECTION_ROUTE,
            SEARCH_QUANT_ACCEPTANCE_DRY_RUN_ROUTE,
            SEARCH_QUANT_EXECUTION_REQUEST_ROUTE,
            SEARCH_QUANT_PROVIDER_MODEL_ROUTE,
        ],
        "local_projection_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "acceptance_dry_run_route": SEARCH_QUANT_ACCEPTANCE_DRY_RUN_ROUTE,
        "execution_request_route": SEARCH_QUANT_EXECUTION_REQUEST_ROUTE,
        "provider_model_route": SEARCH_QUANT_PROVIDER_MODEL_ROUTE,
        "provider_model_route_requires_execution_request": True,
        "provider_model_route_is_button_gated": True,
        "provider_model_route_may_call_tushare_when_user_approved": True,
        "provider_model_route_may_call_deepseek_when_user_approved": False,
        "deepseek_requires_governed_executor": True,
        "deepseek_governed_executor_pending": True,
        "deepseek_skipped_until_governed_executor": True,
        "automatic_provider_model_execution_allowed": False,
        "allowed_light_apis": list(ACCEPTANCE_DRY_RUN_ALLOWED_APIS),
        "default_symbol_limit": symbol_limit,
        "rate_limit_seconds": rate_limit_seconds,
        "planned_outputs": [
            "Factor Quant Hub cache refresh",
            "Next Session cache refresh",
            "ECharts projection payload",
            "optional DeepSeek pro explanation",
        ],
        "call_ledger_required": True,
        "model_ledger_required_for_deepseek": True,
        "safe_error_required": True,
        "ui_progress_required": True,
        "freshness_visible_required": True,
        "provider_gap_visible_required": True,
        "live_light_bootstrap_can_prepare_context": live_light_enabled,
        "full_pool_or_deep_scan_on_render_allowed": False,
        "radar_candidate_is_buy_instruction": False,
        "deepseek_is_data_source": False,
        "deepseek_may_overwrite_numeric_or_action_fields": False,
        "token_key_exposure_allowed": False,
        "production_quant_projection_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _search_quant_projection_submit_autostart_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    search_submit_autostart_on_submit: bool,
    search_submit_autostart_source: str,
    symbol_limit: int,
    rate_limit_seconds: int,
) -> dict[str, Any]:
    effective_search_submit_autostart = live_light_enabled and search_submit_autostart_on_submit
    if effective_search_submit_autostart:
        status = "ready_after_safe_search_submit_local_task_only"
        readiness_stage = "backend_local_route_ready_frontend_wiring_pending"
    elif live_light_enabled:
        status = "disabled_by_search_submit_autostart_config"
        readiness_stage = "server_config_switch_disabled_frontend_wiring_pending"
    elif active_mode == "cache_only":
        status = "cache_only_submit_autostart_disabled"
        readiness_stage = "cache_only_read_only_no_submit_task"
    elif active_mode == "manual":
        status = "manual_explicit_button_submit_autostart_disabled"
        readiness_stage = "manual_explicit_post_task_only"
    elif active_mode == "live_full":
        status = "live_full_reserved_submit_autostart_disabled"
        readiness_stage = "live_full_reserved_requires_separate_authorization"
    else:
        status = "inactive_until_live_light_mode"
        readiness_stage = "inactive_until_live_light_mode"
    if effective_search_submit_autostart:
        inactive_reason = ""
    elif active_mode == "cache_only":
        inactive_reason = "cache_only_read_only"
    elif active_mode == "manual":
        inactive_reason = "manual_requires_explicit_button"
    elif active_mode == "live_full":
        inactive_reason = "live_full_reserved_requires_separate_authorization"
    elif live_light_enabled:
        inactive_reason = "search_submit_autostart_config_false"
    else:
        inactive_reason = "requires_live_light_mode"
    return {
        "schema_version": SEARCH_QUANT_SUBMIT_AUTOSTART_SCHEMA_VERSION,
        "status": status,
        "mode": active_mode,
        "surface": "searched_symbol_submit",
        "allowed_auto_start_mode": "live_light",
        "config_switch": "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART",
        "config_switch_default": False,
        "config_switch_source": search_submit_autostart_source,
        "server_config_switch_required": True,
        "configured_submit_autostart": search_submit_autostart_on_submit,
        "effective_submit_autostart": effective_search_submit_autostart,
        "display_action": "生成 3.0 量化推演",
        "task_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "task_type": SEARCH_QUANT_PROJECTION_TASK_TYPE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "provider_model_route": SEARCH_QUANT_PROVIDER_MODEL_ROUTE,
        "acceptance_dry_run_route": SEARCH_QUANT_ACCEPTANCE_DRY_RUN_ROUTE,
        "execution_request_route": SEARCH_QUANT_EXECUTION_REQUEST_ROUTE,
        "task_catalog_route": "GET /api/tasks/catalog",
        "task_catalog_task_type": SEARCH_QUANT_PROJECTION_TASK_TYPE,
        "task_catalog_button_gated": True,
        "task_catalog_current_backend": "button_gated_search_quant_projection_chain",
        "task_catalog_external_call_policy": "button_confirmed_tushare_first_chain_deepseek_skipped_or_blocked",
        "task_catalog_possible_external_sources": ["tushare"],
        "task_catalog_future_external_sources": ["deepseek"],
        "task_catalog_confirmed_tushare_first_chain_supported": True,
        "task_catalog_tushare_called_only_from_post_task": True,
        "task_catalog_deepseek_governed_executor_pending": True,
        "task_catalog_cache_ledger_packet_writeback_supported": True,
        "local_projection_route_implemented": True,
        "local_projection_creates_task_status_record": True,
        "local_projection_writes_output_packet_key": "command_center_3_candidate_radar_cache",
        "latest_status_replay_after_submit_required": True,
        "latest_status_replay_route": BOOTSTRAP_STATUS_ROUTE,
        "latest_status_replay_lookup_creates_task": False,
        "autostart_readiness_stage": readiness_stage,
        "inactive_reason": inactive_reason,
        "active_mode_submit_autostart_allowed": effective_search_submit_autostart,
        "search_submit_task_creation_allowed_in_active_mode": effective_search_submit_autostart,
        "backend_local_task_creation_ready": True,
        "frontend_submit_autostart_wiring_implemented": False,
        "ui_can_poll_created_task": True,
        "no_new_frontend_config_switch": False,
        "inherits_bootstrap_mode_config": True,
        "inherits_symbol_limit_and_rate_limit": True,
        "safe_submit_payload_fields": ["symbol", "include_tushare", "include_deepseek"],
        "secret_like_payload_fields_dropped": True,
        "live_light_search_submit_auto_start_allowed": effective_search_submit_autostart,
        "manual_search_submit_auto_start_allowed": False,
        "cache_only_search_submit_auto_start_allowed": False,
        "live_full_search_submit_auto_start_allowed": False,
        "cache_only_read_only": active_mode == "cache_only",
        "cache_only_blocks_local_projection_task": active_mode == "cache_only",
        "manual_requires_explicit_button": active_mode == "manual",
        "manual_mode_blocks_submit_autostart": active_mode == "manual",
        "configured_true_but_cache_only_mode": active_mode == "cache_only" and search_submit_autostart_on_submit,
        "configured_true_but_manual_mode": active_mode == "manual" and search_submit_autostart_on_submit,
        "live_full_reserved": active_mode == "live_full",
        "live_full_requires_separate_authorization": active_mode == "live_full",
        "configured_true_but_reserved_mode": active_mode == "live_full" and search_submit_autostart_on_submit,
        "reserved_mode_blocks_local_projection_task": active_mode == "live_full",
        "reserved_mode_blocks_provider_model_task": active_mode == "live_full",
        "reserved_mode_blocks_full_pool_or_deep_scan": active_mode == "live_full",
        "search_typing_creates_task": False,
        "search_input_change_creates_task": False,
        "react_render_creates_task": False,
        "cache_get_creates_task": False,
        "fastapi_startup_creates_task": False,
        "safe_search_submit_event_required": True,
        "safe_symbol_normalization_required": True,
        "symbol_limit": symbol_limit,
        "symbol_dedupe_required": True,
        "create_or_reuse_local_projection_task_only": True,
        "rate_limit_seconds": rate_limit_seconds,
        "rate_limit_reuses_existing_task": True,
        "rate_limit_skip_creates_new_task": False,
        "session_dedupe_required": True,
        "ui_nonblocking_required": True,
        "task_status_polling_required": True,
        "result_surface_count": 6,
        "local_receipt_only_until_execution_request": True,
        "provider_model_route_requires_execution_request": True,
        "future_provider_model_after_submit_allowed_with_execution_request": True,
        "current_submit_autostart_calls_provider_model": False,
        "provider_model_autostart_without_execution_request_allowed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "factor_refresh_executed": False,
        "next_session_refresh_executed": False,
        "echarts_payload_refreshed": False,
        "production_quant_projection_complete": False,
        "call_ledger_required": True,
        "model_ledger_required_for_deepseek": True,
        "safe_error_required": True,
        "raw_user_query_logged": False,
        "raw_user_query_cached": False,
        "token_key_exposure_allowed": False,
        "radar_candidate_is_buy_instruction": False,
        "deepseek_is_data_source": False,
        "deepseek_may_overwrite_numeric_or_action_fields": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _search_quant_projection_submit_autostart_config_handoff_contract(
    *,
    active_mode: str,
    configured_submit_autostart: bool,
    effective_submit_autostart: bool,
    source: str,
) -> dict[str, Any]:
    global_allowlist_promoted = SEARCH_SUBMIT_AUTOSTART_CONFIG_KEY in CONFIG_NAMES
    bootstrap_fallback_available = SEARCH_SUBMIT_AUTOSTART_CONFIG_KEY in BOOTSTRAP_LOCAL_ENV_CONFIG_FALLBACK_KEYS
    bootstrap_fallback_removed = global_allowlist_promoted and not bootstrap_fallback_available
    return {
        "schema_version": SEARCH_QUANT_SUBMIT_AUTOSTART_CONFIG_HANDOFF_SCHEMA_VERSION,
        "status": (
            "global_config_allowlist_promoted_bootstrap_fallback_removed"
            if bootstrap_fallback_removed
            else "global_config_allowlist_promoted_bootstrap_fallback_removal_pending"
            if global_allowlist_promoted
            else "bootstrap_local_env_fallback_visible_config_allowlist_promotion_pending"
        ),
        "mode": active_mode,
        "config_key": SEARCH_SUBMIT_AUTOSTART_CONFIG_KEY,
        "default_value_safe": False,
        "configured_value_safe": configured_submit_autostart,
        "effective_value_safe": effective_submit_autostart,
        "source": source,
        "current_read_path": (
            "global_config_layer_only"
            if bootstrap_fallback_removed
            else "global_config_layer_with_bootstrap_local_env_fallback_guard"
            if global_allowlist_promoted
            else "config_layer_then_bootstrap_local_env_fallback"
        ),
        "target_read_path": (
            "global_config_layer_only"
            if bootstrap_fallback_removed
            else "global_config_layer_only_after_fallback_removal"
            if global_allowlist_promoted
            else "global_config_layer_only_after_allowlist_promotion"
        ),
        "bootstrap_local_env_fallback_available": bootstrap_fallback_available,
        "bootstrap_local_env_fallback_is_temporary": bootstrap_fallback_available,
        "bootstrap_local_env_fallback_removed": bootstrap_fallback_removed,
        "uses_env_value_when_config_layer_omits_key": (
            bootstrap_fallback_available and not global_allowlist_promoted
        ),
        "fallback_effective_after_global_config_read": (
            bootstrap_fallback_available and not global_allowlist_promoted
        ),
        "global_config_allowlist_promoted": global_allowlist_promoted,
        "global_config_key_registered": global_allowlist_promoted,
        "global_config_allowlist_promotion_pending": not global_allowlist_promoted,
        "config_py_update_pending": not global_allowlist_promoted,
        "fallback_removal_pending": bootstrap_fallback_available and global_allowlist_promoted,
        "fallback_removal_complete": bootstrap_fallback_removed,
        "fallback_removal_allowed_after_global_config_promotion": True,
        "frontend_visible": True,
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "operator_change_channel": "server_config_layer_only",
        "live_light_required_for_effective_autostart": True,
        "cache_only_manual_live_full_effective_false": active_mode != "live_light",
        "task_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "task_type": SEARCH_QUANT_PROJECTION_TASK_TYPE,
        "creates_local_projection_task_only": True,
        "creates_provider_model_task": False,
        "provider_model_execution_requires_execution_request": True,
        "config_handoff_is_production_evidence": False,
        "production_config_complete": False,
        "search_typing_creates_task": False,
        "react_render_creates_task": False,
        "cache_get_creates_task": False,
        "fastapi_startup_creates_task": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _search_quant_projection_submit_autostart_config_promotion_contract(
    *,
    config_handoff_contract: dict[str, Any],
) -> dict[str, Any]:
    global_allowlist_promoted = bool(config_handoff_contract.get("global_config_allowlist_promoted"))
    fallback_removal_pending = bool(config_handoff_contract.get("fallback_removal_pending"))
    fallback_removal_complete = bool(config_handoff_contract.get("fallback_removal_complete"))
    promotion_rows = [
        {
            "step_key": "add_global_config_allowlist_key",
            "target_file": "config.py",
            "required_change": "add COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART to CONFIG_NAMES",
            "status": (
                "passed_global_config_allowlist_key_present"
                if global_allowlist_promoted
                else "pending_file_scope"
            ),
            "requires_future_file_scope": not global_allowlist_promoted,
            "step_complete": global_allowlist_promoted,
            "external_calls_triggered": False,
            "production_evidence": False,
        },
        {
            "step_key": "prove_global_config_read_path",
            "target_file": "tests/test_command_center_3_server.py",
            "required_evidence": "safe config row reads COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART through the global config layer",
            "status": (
                "passed_safe_config_row_reads_global_config_layer"
                if global_allowlist_promoted
                else "pending_after_allowlist"
            ),
            "requires_future_file_scope": False,
            "step_complete": global_allowlist_promoted,
            "external_calls_triggered": False,
            "production_evidence": False,
        },
        {
            "step_key": "remove_bootstrap_local_env_fallback",
            "target_file": "server/services/bootstrap_service.py",
            "required_change": "remove COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART from bootstrap-local fallback after global config read is proven",
            "status": (
                "passed_bootstrap_local_env_fallback_removed"
                if fallback_removal_complete
                else "pending_after_global_config_read"
            ),
            "requires_future_file_scope": False,
            "step_complete": fallback_removal_complete,
            "external_calls_triggered": False,
            "production_evidence": False,
        },
        {
            "step_key": "preserve_safe_config_surface",
            "target_file": "server/services/bootstrap_service.py",
            "required_evidence": "frontend-visible rows stay read-only, safe, mode-gated, and non-writeback",
            "status": (
                "passed_safe_config_surface_read_only"
                if global_allowlist_promoted
                else "pending_regression_guard"
            ),
            "requires_future_file_scope": False,
            "step_complete": global_allowlist_promoted,
            "external_calls_triggered": False,
            "production_evidence": False,
        },
        {
            "step_key": "rerun_validation_gate",
            "target_file": "scripts/bootstrap_runtime_contract.py",
            "required_evidence": "focused tests, bootstrap runtime contract, smoke, diff check, and secret review pass",
            "status": (
                "ready_for_local_validation_after_fallback_removal"
                if fallback_removal_complete
                else "ready_for_local_validation_before_fallback_removal"
                if global_allowlist_promoted
                else "pending_after_promotion"
            ),
            "requires_future_file_scope": False,
            "step_complete": False,
            "external_calls_triggered": False,
            "production_evidence": False,
        },
    ]
    return {
        "schema_version": SEARCH_QUANT_SUBMIT_AUTOSTART_CONFIG_PROMOTION_SCHEMA_VERSION,
        "status": (
            "config_allowlist_promoted_fallback_removed_validation_pending"
            if fallback_removal_complete
            else "config_allowlist_promoted_fallback_removal_pending"
            if global_allowlist_promoted
            else "config_allowlist_promotion_runbook_ready_pending_file_scope"
        ),
        "mode": config_handoff_contract["mode"],
        "config_key": config_handoff_contract["config_key"],
        "current_handoff_status": config_handoff_contract["status"],
        "current_read_path": config_handoff_contract["current_read_path"],
        "target_read_path": config_handoff_contract["target_read_path"],
        "promotion_step_count": len(promotion_rows),
        "promotion_rows": promotion_rows,
        "current_cycle_modifies_global_config_file": False,
        "global_config_file_already_promoted": global_allowlist_promoted,
        "current_cycle_file_limit_respected": True,
        "requires_future_config_py_file_scope": not global_allowlist_promoted,
        "config_py_update_pending": not global_allowlist_promoted,
        "bootstrap_local_env_fallback_removal_pending": fallback_removal_pending,
        "bootstrap_local_env_fallback_removed": fallback_removal_complete,
        "fallback_removal_allowed_after_global_config_promotion": True,
        "global_config_allowlist_promoted": global_allowlist_promoted,
        "global_config_allowlist_promotion_pending": not global_allowlist_promoted,
        "frontend_visible": True,
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "status_get_creates_task": False,
        "react_render_creates_task": False,
        "search_typing_creates_task": False,
        "fastapi_startup_creates_task": False,
        "provider_model_execution_requires_execution_request": True,
        "promotion_contract_is_production_evidence": False,
        "production_config_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _search_quant_projection_frontend_wiring_acceptance_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    search_submit_autostart_on_submit: bool,
    symbol_limit: int,
    rate_limit_seconds: int,
) -> dict[str, Any]:
    effective_search_submit_autostart = live_light_enabled and search_submit_autostart_on_submit
    mode_acceptance_rows = [
        {
            "mode": "cache_only",
            "active": active_mode == "cache_only",
            "frontend_submit_autostart_allowed": False,
            "manual_button_allowed": False,
            "expected_frontend_behavior": "read_cache_only_no_submit_task",
            "task_creation_surface": "none",
            "typing_creates_task": False,
            "render_creates_task": False,
            "cache_get_creates_task": False,
            "provider_model_execution_allowed": False,
            "browser_acceptance_required_before_enable": False,
        },
        {
            "mode": "manual",
            "active": active_mode == "manual",
            "frontend_submit_autostart_allowed": False,
            "manual_button_allowed": True,
            "expected_frontend_behavior": "explicit_button_only",
            "task_creation_surface": "button_click",
            "typing_creates_task": False,
            "render_creates_task": False,
            "cache_get_creates_task": False,
            "provider_model_execution_allowed": False,
            "browser_acceptance_required_before_enable": False,
        },
        {
            "mode": "live_light",
            "active": active_mode == "live_light",
            "frontend_submit_autostart_allowed": effective_search_submit_autostart,
            "manual_button_allowed": True,
            "expected_frontend_behavior": (
                "safe_submit_may_create_or_reuse_local_task"
                if search_submit_autostart_on_submit
                else "explicit_button_until_submit_autostart_config_enabled"
            ),
            "task_creation_surface": (
                "safe_submit_after_bootstrap_status"
                if search_submit_autostart_on_submit
                else "explicit_button_until_autostart_config_enabled"
            ),
            "typing_creates_task": False,
            "render_creates_task": False,
            "cache_get_creates_task": False,
            "provider_model_execution_allowed": False,
            "browser_acceptance_required_before_enable": True,
        },
        {
            "mode": "live_full",
            "active": active_mode == "live_full",
            "frontend_submit_autostart_allowed": False,
            "manual_button_allowed": False,
            "expected_frontend_behavior": "reserved_disabled_requires_future_authorization",
            "task_creation_surface": "none",
            "typing_creates_task": False,
            "render_creates_task": False,
            "cache_get_creates_task": False,
            "provider_model_execution_allowed": False,
            "browser_acceptance_required_before_enable": False,
        },
    ]
    browser_acceptance_rows = [
        {
            "criterion": "initial_cache_render_silent",
            "required_evidence": "browser network trace shows initial render reads cache/status only",
            "expected": "no POST /api/candidate-radar/quant-projection before safe submit",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "typing_does_not_create_task",
            "required_evidence": "typing in searched-symbol input emits no task creation request",
            "expected": "no POST task and no provider/model request",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "safe_submit_creates_single_local_task",
            "required_evidence": "safe submit emits at most one POST /api/candidate-radar/quant-projection",
            "expected": "TaskLaunchReceipt receives task_id from POST response",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "task_status_polling_visible",
            "required_evidence": "TaskStatusPanel polls GET /api/tasks/{task_id}",
            "expected": "task id, status, progress, current_step, and safe error are visible",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "success_refreshes_research_surfaces",
            "required_evidence": "successful task refreshes Candidate Radar cache and bootstrap status",
            "expected": "latest status replay and local projection receipt are visible",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "frontend_provider_model_silence",
            "required_evidence": "browser network trace contains no frontend Tushare/DeepSeek/GitHub calls",
            "expected": "provider/model work remains execution-request gated",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "research_only_boundaries_visible",
            "required_evidence": "UI shows provider/model pending, no-trade, and no-action boundaries",
            "expected": "local receipt is not production evidence or a buy/sell instruction",
            "required_before_wiring_done": True,
        },
    ]
    failure_recovery_rows = [
        {
            "criterion": "invalid_symbol_safe_block",
            "required_ui_surface": "safe validation message and no provider/model request",
            "expected": "invalid symbol does not become production evidence or trade instruction",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "post_failure_preserves_cache",
            "required_ui_surface": "previous Candidate Radar cache stays visible with safe error",
            "expected": "failed submit does not clear research surfaces or hide provider gaps",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "task_failure_safe_error_visible",
            "required_ui_surface": "TaskStatusPanel shows failed/current_step/safe_error",
            "expected": "raw traceback, raw payload, and token/key material remain hidden",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "rate_limit_reuse_visible",
            "required_ui_surface": "existing task id or rate-limit skipped state is visible",
            "expected": "rate-limit hit reuses or skips instead of creating an unbounded queue",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "manual_retry_only",
            "required_ui_surface": "retry requires explicit user action",
            "expected": "frontend wiring does not auto-retry provider/model work",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "stale_cache_fallback_visible",
            "required_ui_surface": "last-good cache remains visible with stale/provider-gap labels",
            "expected": "fallback does not synthesize provider or model facts",
            "required_before_wiring_done": True,
        },
        {
            "criterion": "queue_boundaries_visible",
            "required_ui_surface": "session dedupe, rate limit, and task id are visible",
            "expected": "safe submit cannot create an unbounded local task queue",
            "required_before_wiring_done": True,
        },
    ]
    if effective_search_submit_autostart:
        status = "frontend_wiring_acceptance_pending_backend_ready"
    elif live_light_enabled:
        status = "frontend_wiring_acceptance_pending_config_disabled"
    else:
        status = "inactive_until_live_light_mode"
    return {
        "schema_version": SEARCH_QUANT_FRONTEND_WIRING_SCHEMA_VERSION,
        "status": status,
        "mode": active_mode,
        "surface": "candidate_radar_search_quant_projection",
        "config_switch": "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART",
        "configured_submit_autostart": search_submit_autostart_on_submit,
        "effective_submit_autostart": effective_search_submit_autostart,
        "target_frontend_route": "desktop/src/routes/CandidateRadar.tsx",
        "target_client_helper": "postCandidateRadarQuantProjection",
        "target_task_receipt_component": "TaskLaunchReceipt",
        "target_task_status_component": "TaskStatusPanel",
        "task_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "task_type": SEARCH_QUANT_PROJECTION_TASK_TYPE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "status_replay_route": BOOTSTRAP_STATUS_ROUTE,
        "cache_refresh_route": "GET /api/candidate-radar/cache",
        "manual_button_path_available": True,
        "manual_button_frontend_wiring_implemented": True,
        "manual_confirm_button_frontend_wiring_implemented": True,
        "manual_confirm_button_runtime_ready": True,
        "manual_confirm_button_status": "ready_explicit_confirm_button_posts_quant_projection_task",
        "manual_confirm_button_scope": "P1 searched-symbol confirm button only",
        "p1_manual_confirm_path_ready": True,
        "p1_manual_confirm_path_status": "ready_button_posts_tushare_first_task",
        "manual_button_task_launch_receipt_bound": True,
        "manual_button_task_status_polling_bound": True,
        "manual_button_success_refresh_bound": True,
        "manual_button_path_is_production_evidence": False,
        "manual_button_path_calls_provider_or_model_from_frontend": False,
        "mode_acceptance_rows": mode_acceptance_rows,
        "mode_acceptance_row_count": len(mode_acceptance_rows),
        "mode_acceptance_matrix_visible": True,
        "active_mode_frontend_submit_autostart_allowed": effective_search_submit_autostart,
        "active_mode_expected_frontend_behavior": next(
            row["expected_frontend_behavior"] for row in mode_acceptance_rows if row["active"]
        ),
        "active_mode_task_creation_surface": next(
            row["task_creation_surface"] for row in mode_acceptance_rows if row["active"]
        ),
        "browser_acceptance_rows": browser_acceptance_rows,
        "browser_acceptance_row_count": len(browser_acceptance_rows),
        "browser_acceptance_evidence_required": True,
        "browser_acceptance_evidence_complete": False,
        "browser_network_trace_required": True,
        "browser_viewports_required": ["desktop", "laptop", "tablet", "mobile"],
        "browser_reduced_motion_check_required": True,
        "browser_acceptance_can_promote_frontend_wiring": False,
        "failure_recovery_rows": failure_recovery_rows,
        "failure_recovery_row_count": len(failure_recovery_rows),
        "failure_recovery_evidence_required": True,
        "failure_recovery_evidence_complete": False,
        "safe_error_display_required": True,
        "rate_limit_reuse_visible_required": True,
        "manual_retry_only_required": True,
        "last_good_cache_fallback_required": True,
        "unbounded_task_queue_allowed": False,
        "frontend_submit_autostart_wiring_implemented": False,
        "frontend_runtime_wiring_implemented": True,
        "frontend_runtime_wiring_scope": "manual_confirm_button_ready_autostart_and_browser_acceptance_pending",
        "full_frontend_wiring_implemented": False,
        "full_frontend_wiring_pending_reason": "browser_acceptance_and_submit_autostart_pending",
        "frontend_acceptance_test_implemented": False,
        "browser_runtime_evidence_complete": False,
        "live_light_wiring_allowed": effective_search_submit_autostart,
        "manual_mode_requires_explicit_button": True,
        "cache_only_wiring_disabled": active_mode == "cache_only",
        "live_full_wiring_reserved_disabled": active_mode == "live_full",
        "safe_symbol_required": True,
        "safe_submit_payload_fields": ["symbol", "include_tushare", "include_deepseek"],
        "symbol_limit": symbol_limit,
        "rate_limit_seconds": rate_limit_seconds,
        "must_read_bootstrap_status_before_autostart": True,
        "must_require_live_light_mode": True,
        "must_require_submit_autostart_config_switch": True,
        "must_require_submit_autostart_contract_allowed": True,
        "must_not_create_task_on_typing": True,
        "must_not_create_task_on_react_initial_render": True,
        "must_not_create_task_from_get_cache": True,
        "must_not_call_provider_from_frontend": True,
        "must_set_task_id_from_post_response": True,
        "must_render_task_launch_receipt": True,
        "must_poll_task_status_panel": True,
        "must_refresh_candidate_cache_on_success": True,
        "must_refresh_bootstrap_status_after_task": True,
        "must_show_latest_status_replay": True,
        "must_show_provider_model_pending": True,
        "must_show_no_trade_no_action_boundary": True,
        "provider_model_execution_requires_execution_request": True,
        "frontend_packet_may_contain_token_key": False,
        "raw_user_query_logged": False,
        "raw_user_query_cached": False,
        "local_receipt_is_production_evidence": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_quant_projection_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _search_quant_projection_unified_startup_handoff_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    search_submit_autostart_contract: dict[str, Any],
    search_quant_projection_contract: dict[str, Any],
    frontend_wiring_contract: dict[str, Any],
    unified_startup_task_contract: dict[str, Any],
) -> dict[str, Any]:
    handoff_rows = [
        {
            "handoff_key": "bootstrap_status_precheck",
            "handoff_order": 1,
            "source_contract": "search_quant_projection_frontend_wiring_acceptance_contract",
            "target_contract": "live_light_unified_startup_task_contract",
            "required_state": "frontend reads bootstrap status before submit handoff",
            "maps_to_unified_stage": "cache_first_status_read",
            "current_runtime": "read_only_contract_link",
        },
        {
            "handoff_key": "safe_symbol_scope_intake",
            "handoff_order": 2,
            "source_contract": "search_quant_projection_submit_autostart_contract",
            "target_contract": "live_light_unified_startup_task_contract",
            "required_state": "searched symbol is normalized, deduped, and scope-limited",
            "maps_to_unified_stage": "scope_resolution",
            "current_runtime": "safe_payload_contract_only",
        },
        {
            "handoff_key": "local_projection_receipt",
            "handoff_order": 3,
            "source_contract": "search_quant_projection_workflow_contract",
            "target_contract": "live_light_unified_startup_task_contract",
            "required_state": "safe submit creates or reuses local projection task only",
            "maps_to_unified_stage": "startup_task_envelope",
            "current_runtime": "local_projection_receipt_only",
        },
        {
            "handoff_key": "provider_model_stage_mapping",
            "handoff_order": 4,
            "source_contract": "search_quant_projection_result_surface_contract",
            "target_contract": "live_light_unified_startup_task_contract",
            "required_state": "Tushare, Factor light, Next Session, and DeepSeek stages share one stage vocabulary",
            "maps_to_unified_stage": "tushare_light_refresh/factor_light_runtime/next_session_cache_refresh/deepseek_pro_explanation",
            "current_runtime": "stage_mapping_contract_only",
        },
        {
            "handoff_key": "execution_request_boundary",
            "handoff_order": 5,
            "source_contract": "search_quant_projection_workflow_contract",
            "target_contract": "live_light_unified_startup_task_contract",
            "required_state": "provider/model execution remains behind execution-request and ledger governance",
            "maps_to_unified_stage": "tushare_light_refresh/deepseek_pro_explanation",
            "current_runtime": "provider_model_execution_pending",
        },
        {
            "handoff_key": "ui_polling_refresh",
            "handoff_order": 6,
            "source_contract": "search_quant_projection_frontend_wiring_acceptance_contract",
            "target_contract": "live_light_unified_startup_task_contract",
            "required_state": "UI polls task status and refreshes cache/status without blocking render",
            "maps_to_unified_stage": "ui_polling_and_cache_refresh",
            "current_runtime": "polling_contract_only",
        },
    ]
    common_flags = {
        "handoff_contract_only": True,
        "handoff_implemented_now": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "search_typing_creates_task": False,
        "fastapi_startup_creates_task": False,
        "search_submit_creates_unified_startup_task_now": False,
        "frontend_direct_provider_call_allowed": False,
        "provider_or_model_execution_allowed_now": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "worker_dispatch_implemented": False,
        "call_ledger_required": True,
        "model_ledger_required_for_deepseek": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
        "row_is_production_evidence": False,
    }
    handoff_rows = [{**row, **common_flags} for row in handoff_rows]
    search_submit_allowed = bool(
        search_submit_autostart_contract.get("live_light_search_submit_auto_start_allowed")
    )
    return {
        "schema_version": SEARCH_QUANT_UNIFIED_STARTUP_HANDOFF_SCHEMA_VERSION,
        "status": (
            "search_quant_unified_startup_handoff_visible_frontend_wiring_pending"
            if live_light_enabled and search_submit_allowed
            else "search_quant_unified_startup_handoff_visible_config_disabled"
            if live_light_enabled
            else "inactive_until_live_light_mode"
        ),
        "mode": active_mode,
        "surface": "candidate_radar_search_submit_to_unified_startup",
        "source_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "source_task_type": SEARCH_QUANT_PROJECTION_TASK_TYPE,
        "target_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "target_task_type": BOOTSTRAP_TASK_TYPE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "handoff_rows": handoff_rows,
        "handoff_row_count": len(handoff_rows),
        "required_handoff_keys": [row["handoff_key"] for row in handoff_rows],
        "linked_search_workflow_schema_version": search_quant_projection_contract.get("schema_version"),
        "linked_submit_autostart_schema_version": search_submit_autostart_contract.get("schema_version"),
        "linked_frontend_wiring_schema_version": frontend_wiring_contract.get("schema_version"),
        "linked_unified_startup_schema_version": unified_startup_task_contract.get("schema_version"),
        "linked_unified_startup_stage_count": unified_startup_task_contract.get("stage_count"),
        "search_submit_autostart_allowed": search_submit_allowed,
        "frontend_wiring_implemented": bool(
            frontend_wiring_contract.get("frontend_submit_autostart_wiring_implemented")
        ),
        "browser_runtime_evidence_complete": bool(
            frontend_wiring_contract.get("browser_runtime_evidence_complete")
        ),
        "unified_stage_vocabulary_shared": True,
        "search_submit_creates_local_projection_task_now": True,
        "search_submit_creates_unified_startup_task_now": False,
        "search_submit_fans_out_provider_model_now": False,
        "future_unified_task_handoff_allowed_after_frontend_acceptance": True,
        "future_handoff_requires_execution_request_for_provider_model": True,
        "safe_symbol_scope_required": True,
        "cache_first_status_read_required": True,
        "task_status_polling_required": True,
        "candidate_cache_refresh_required_after_success": True,
        "bootstrap_status_refresh_required_after_success": True,
        "provider_model_execution_requires_execution_request": True,
        "call_ledger_required": True,
        "model_ledger_required_for_deepseek": True,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "search_typing_creates_task": False,
        "fastapi_startup_creates_task": False,
        "frontend_direct_provider_call_allowed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "worker_dispatch_implemented": False,
        "deepseek_is_data_source": False,
        "deepseek_may_overwrite_numeric_or_action_fields": False,
        "radar_candidate_is_buy_instruction": False,
        "token_key_exposure_allowed": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
        "handoff_contract_is_execution_evidence": False,
        "handoff_contract_is_production_evidence": False,
        "production_search_unified_handoff_complete": False,
    }


def _search_quant_projection_result_surface_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    result_surface_rows = [
        {
            "surface_key": "task_progress",
            "required_fields": ["task_id", "status", "progress", "current_step", "safe_error"],
            "source": "GET /api/tasks/{task_id}",
            "provider_model_execution_evidence": False,
        },
        {
            "surface_key": "data_provenance",
            "required_fields": ["source_task_id", "source_route", "source_scope_hash", "call_ledger_ids"],
            "source": "cache_lineage",
            "provider_model_execution_evidence": False,
        },
        {
            "surface_key": "freshness_provider_gap",
            "required_fields": ["freshness_state", "data_date", "provider_gap", "safe_error"],
            "source": "freshness_provider_gap_contract",
            "provider_model_execution_evidence": False,
        },
        {
            "surface_key": "factor_evidence_effects",
            "required_fields": ["support", "suppress", "neutral", "missing"],
            "source": "Factor Quant Hub cache",
            "provider_model_execution_evidence": False,
            "research_only": True,
        },
        {
            "surface_key": "next_session_echarts_projection",
            "required_fields": ["scenario_series", "support_lines", "resistance_lines", "operation_zone_overlays"],
            "source": "Next Session cache",
            "provider_model_execution_evidence": False,
            "operation_zone_action_mode_required": "condition_only",
        },
        {
            "surface_key": "deepseek_status",
            "required_fields": ["status", "model_label", "parse_status", "safe_summary"],
            "source": "search_quant_projection_deepseek_output_acceptance_contract",
            "provider_model_execution_evidence": False,
            "model_correctness_evidence": False,
        },
    ]
    return {
        "schema_version": SEARCH_QUANT_RESULT_SURFACE_CONTRACT_SCHEMA_VERSION,
        "status": "search_quant_projection_result_surface_contract_visible_execution_pending"
        if active_mode in {"manual", "live_light"}
        else "inactive_until_manual_or_live_light_mode",
        "mode": active_mode,
        "display_action": "生成 3.0 量化推演",
        "allowed_modes": ["manual", "live_light"],
        "task_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "provider_model_route": SEARCH_QUANT_PROVIDER_MODEL_ROUTE,
        "provider_model_route_requires_execution_request": True,
        "live_light_bootstrap_can_prepare_context": live_light_enabled,
        "search_input_creates_result_surface": False,
        "search_typing_creates_task": False,
        "react_render_creates_result_surface": False,
        "cache_get_creates_result_surface": False,
        "explicit_search_action_required": True,
        "result_surface_rows": result_surface_rows,
        "result_surface_count": len(result_surface_rows),
        "required_result_surfaces": [row["surface_key"] for row in result_surface_rows],
        "task_progress_visible_required": True,
        "data_provenance_visible_required": True,
        "freshness_state_visible_required": True,
        "provider_gap_visible_required": True,
        "factor_support_suppress_neutral_missing_required": True,
        "next_session_echarts_payload_required": True,
        "deepseek_status_visible_required": True,
        "call_ledger_safe_summary_visible_required": True,
        "model_ledger_safe_summary_visible_when_deepseek_used": True,
        "raw_prompt_or_raw_model_output_visible_allowed": False,
        "token_key_exposure_allowed": False,
        "radar_candidate_is_buy_instruction": False,
        "factor_score_is_buy_instruction": False,
        "deepseek_text_is_buy_instruction": False,
        "trade_instruction_allowed": False,
        "may_overwrite_price": False,
        "may_overwrite_holding": False,
        "may_overwrite_factor": False,
        "may_overwrite_operation_zones": False,
        "may_modify_strategy_action": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "result_surface_contract_is_provider_execution_evidence": False,
        "result_surface_contract_is_model_correctness_evidence": False,
        "result_surface_contract_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _search_quant_projection_factor_next_handoff_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    handoff_rows = [
        {
            "handoff_key": "safe_symbol_scope_bound",
            "handoff_order": 1,
            "source_contract": "search_quant_projection_workflow_contract",
            "target_surface": "factor_next_local_compute_scope",
            "required_state": "searched symbol is normalized, deduped, capped, and bound to a safe scope hash",
            "future_local_route": "",
            "future_task_type": "",
            "input_packet_keys": [],
            "output_packet_key": "",
        },
        {
            "handoff_key": "local_projection_receipt_ready",
            "handoff_order": 2,
            "source_contract": "search_quant_projection_workflow_contract",
            "target_surface": "candidate_radar_quant_projection_receipt",
            "required_state": "local projection receipt is visible before downstream Factor/Next cache handoff",
            "future_local_route": SEARCH_QUANT_PROJECTION_ROUTE,
            "future_task_type": SEARCH_QUANT_PROJECTION_TASK_TYPE,
            "input_packet_keys": [],
            "output_packet_key": "command_center_candidate_radar_quant_projection_receipt",
        },
        {
            "handoff_key": "provider_fact_ledger_or_gap_ready",
            "handoff_order": 3,
            "source_contract": "tushare_light_strategy_contract",
            "target_surface": "factor_next_provider_inputs",
            "required_state": "Tushare light facts have call-ledger rows or explicit provider-gap skips",
            "future_local_route": "",
            "future_task_type": "",
            "input_packet_keys": ["command_center_candidate_radar_quant_projection_receipt"],
            "output_packet_key": "",
        },
        {
            "handoff_key": "factor_light_runtime_pending",
            "handoff_order": 4,
            "source_contract": "live_light_worker_dispatch_contract",
            "target_surface": "factor_light_support_suppress_neutral_missing_rows",
            "required_state": "Factor light local compute may run later from existing governed cache only",
            "future_local_route": "POST /api/factor-quant/run-light",
            "future_task_type": "run_factor_light",
            "input_packet_keys": ["command_center_factor_quant_hub_packet"],
            "output_packet_key": "command_center_factor_quant_hub_packet",
        },
        {
            "handoff_key": "factor_quant_hub_cache_lineage_pending",
            "handoff_order": 5,
            "source_contract": "live_light_cache_lineage_contract",
            "target_surface": "Factor Quant Hub cache",
            "required_state": "Factor Quant Hub cache write needs lineage, freshness, provider-gap, and safe-error fields",
            "future_local_route": "POST /api/factor-quant/run-light",
            "future_task_type": "run_factor_light",
            "input_packet_keys": ["command_center_candidate_radar_quant_projection_receipt"],
            "output_packet_key": "command_center_factor_quant_hub_packet",
        },
        {
            "handoff_key": "next_session_cache_lineage_pending",
            "handoff_order": 6,
            "source_contract": "live_light_cache_lineage_contract",
            "target_surface": "Next Session cache",
            "required_state": "Next Session projection cache write needs lineage, freshness, operation-zone, provider-gap, and safe-error fields",
            "future_local_route": "POST /api/next-session/generate",
            "future_task_type": "build_next_session_projection",
            "input_packet_keys": [
                "command_center_factor_quant_hub_packet",
                "command_center_next_session_projection_packet",
            ],
            "output_packet_key": "command_center_next_session_projection_packet",
        },
    ]
    common_flags = {
        "handoff_contract_only": True,
        "ready_now": False,
        "local_compute_execution_implemented": False,
        "cache_write_implemented": False,
        "local_task_created_now": False,
        "local_compute_executed_now": False,
        "output_written_now": False,
        "cache_get_may_execute_local_compute": False,
        "react_render_may_execute_local_compute": False,
        "search_typing_may_execute_local_compute": False,
        "fastapi_startup_may_execute_local_compute": False,
        "cache_get_may_write_cache": False,
        "react_render_may_write_cache": False,
        "fastapi_startup_may_write_cache": False,
        "call_ledger_required": True,
        "cache_lineage_required": True,
        "provider_gap_visible_required": True,
        "stale_cache_label_required": True,
        "safe_error_required_when_missing_cache": True,
        "provider_model_execution_requires_execution_request": True,
        "feeds_deepseek_readiness_contract": True,
        "deepseek_may_run_before_factor_next_ready": False,
        "row_is_provider_execution_evidence": False,
        "row_is_model_correctness_evidence": False,
        "row_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    handoff_rows = [{**row, **common_flags} for row in handoff_rows]
    return {
        "schema_version": SEARCH_QUANT_FACTOR_NEXT_HANDOFF_CONTRACT_SCHEMA_VERSION,
        "status": "search_quant_factor_next_handoff_visible_cache_write_pending"
        if active_mode in {"manual", "live_light"}
        else "inactive_until_manual_or_live_light_mode",
        "mode": active_mode,
        "display_action": "生成 3.0 量化推演",
        "allowed_modes": ["manual", "live_light"],
        "task_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "future_factor_route": "POST /api/factor-quant/run-light",
        "future_next_session_route": "POST /api/next-session/generate",
        "future_task_types": ["run_factor_light", "build_next_session_projection"],
        "output_packet_keys": [
            "command_center_factor_quant_hub_packet",
            "command_center_next_session_projection_packet",
        ],
        "input_packet_keys": [
            "command_center_candidate_radar_quant_projection_receipt",
            "command_center_factor_quant_hub_packet",
            "command_center_next_session_projection_packet",
        ],
        "handoff_rows": handoff_rows,
        "handoff_row_count": len(handoff_rows),
        "ready_now_row_count": 0,
        "executed_handoff_row_count": 0,
        "output_written_row_count": 0,
        "required_handoff_keys": [row["handoff_key"] for row in handoff_rows],
        "live_light_bootstrap_can_prepare_context": live_light_enabled,
        "requires_safe_symbol_scope": True,
        "requires_local_projection_receipt": True,
        "requires_call_ledger_or_provider_gap": True,
        "requires_factor_light_cache_lineage": True,
        "requires_next_session_cache_lineage": True,
        "requires_stale_cache_label": True,
        "requires_safe_error_when_missing_cache": True,
        "feeds_deepseek_readiness_contract": True,
        "deepseek_may_run_before_factor_next_ready": False,
        "search_input_creates_handoff": False,
        "search_typing_creates_task": False,
        "react_render_executes_factor_next": False,
        "cache_get_executes_factor_next": False,
        "fastapi_startup_executes_factor_next": False,
        "current_search_submit_executes_factor_next_now": False,
        "current_search_submit_writes_factor_next_cache_now": False,
        "local_compute_execution_implemented": False,
        "cache_write_implemented": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "handoff_contract_is_provider_execution_evidence": False,
        "handoff_contract_is_model_correctness_evidence": False,
        "handoff_contract_is_production_evidence": False,
        "token_key_exposure_allowed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _search_quant_projection_cache_write_preflight_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    factor_next_handoff_contract: dict[str, Any],
) -> dict[str, Any]:
    preflight_rows = [
        {
            "preflight_key": "scope_hash_matches_projection_receipt",
            "preflight_order": 1,
            "source_contract": "search_quant_projection_workflow_contract",
            "target_cache": "Factor Quant Hub / Next Session",
            "required_state": "cache write request references the same safe symbol scope hash as the local projection receipt",
            "required_fields": ["source_task_id", "source_task_type", "source_route", "runtime_mode", "scope_hash"],
        },
        {
            "preflight_key": "provider_ledger_or_gap_bound",
            "preflight_order": 2,
            "source_contract": "tushare_light_strategy_contract",
            "target_cache": "Factor Quant Hub / Next Session",
            "required_state": "provider inputs are backed by call-ledger ids or explicit provider-gap rows",
            "required_fields": ["provider_call_ledger_ids", "provider_gap", "safe_error"],
        },
        {
            "preflight_key": "factor_next_handoff_rows_bound",
            "preflight_order": 3,
            "source_contract": "search_quant_projection_factor_next_handoff_contract",
            "target_cache": "Factor Quant Hub / Next Session",
            "required_state": "Factor/Next handoff rows are visible before any cache write is allowed",
            "required_fields": ["handoff_row_count", "required_handoff_keys", "output_packet_keys"],
        },
        {
            "preflight_key": "lineage_fields_complete",
            "preflight_order": 4,
            "source_contract": "live_light_cache_lineage_contract",
            "target_cache": "Factor Quant Hub / Next Session",
            "required_state": "lineage carries input/output packet keys, cache source, storage backend, local fetch time, freshness, and data date",
            "required_fields": [
                "input_packet_keys",
                "output_packet_keys",
                "cache_source",
                "storage_backend",
                "local_fetched_at",
                "freshness_state",
                "data_date",
            ],
        },
        {
            "preflight_key": "stale_cache_and_safe_error_policy_bound",
            "preflight_order": 5,
            "source_contract": "live_light_freshness_provider_gap_contract",
            "target_cache": "Factor Quant Hub / Next Session",
            "required_state": "stale cache fallback, provider gaps, empty rows, and missing cache become visible states rather than synthesized facts",
            "required_fields": ["freshness_state", "stale_cache_label", "provider_gap", "safe_error"],
        },
        {
            "preflight_key": "deepseek_cache_dependency_blocked_until_factor_next_written",
            "preflight_order": 6,
            "source_contract": "search_quant_projection_deepseek_readiness_contract",
            "target_cache": "DeepSeek explanation cache",
            "required_state": "DeepSeek explanation cache cannot be written before Factor Quant Hub and Next Session cache lineage is visible",
            "required_fields": ["model_ledger_ids", "parse_status", "sanitizer_status", "input_hash", "output_hash"],
        },
        {
            "preflight_key": "no_price_position_factor_action_overwrite_guard",
            "preflight_order": 7,
            "source_contract": "runtime_hard_boundary_contract",
            "target_cache": "all searched-symbol output caches",
            "required_state": "cache writes cannot overwrite price, holding, factor source values, operation zones, or strategy action",
            "required_fields": ["write_policy", "target_fields_allowlist", "strategy_action_mutation_allowed"],
        },
    ]
    common_flags = {
        "preflight_contract_only": True,
        "ready_now": False,
        "cache_write_allowed_now": False,
        "cache_write_implemented": False,
        "local_compute_execution_implemented": False,
        "cache_written_now": False,
        "lineage_written_now": False,
        "cache_get_may_write_cache": False,
        "react_render_may_write_cache": False,
        "search_typing_may_write_cache": False,
        "fastapi_startup_may_write_cache": False,
        "post_task_or_worker_required_for_write": True,
        "call_ledger_required": True,
        "cache_lineage_required": True,
        "provider_gap_visible_required": True,
        "safe_error_required": True,
        "stale_cache_label_required": True,
        "row_is_provider_execution_evidence": False,
        "row_is_model_correctness_evidence": False,
        "row_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    preflight_rows = [{**row, **common_flags} for row in preflight_rows]
    output_packet_keys = [
        "command_center_factor_quant_hub_packet",
        "command_center_next_session_projection_packet",
    ]
    return {
        "schema_version": SEARCH_QUANT_CACHE_WRITE_PREFLIGHT_CONTRACT_SCHEMA_VERSION,
        "status": "search_quant_cache_write_preflight_visible_write_pending"
        if active_mode in {"manual", "live_light"}
        else "inactive_until_manual_or_live_light_mode",
        "mode": active_mode,
        "display_action": "生成 3.0 量化推演",
        "allowed_modes": ["manual", "live_light"],
        "task_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "future_factor_route": "POST /api/factor-quant/run-light",
        "future_next_session_route": "POST /api/next-session/generate",
        "target_cache_keys": ["factor_quant_hub_cache", "next_session_projection_cache"],
        "output_packet_keys": output_packet_keys,
        "preflight_rows": preflight_rows,
        "preflight_row_count": len(preflight_rows),
        "ready_now_row_count": 0,
        "cache_written_row_count": 0,
        "lineage_written_row_count": 0,
        "required_preflight_keys": [row["preflight_key"] for row in preflight_rows],
        "linked_factor_next_handoff_schema_version": factor_next_handoff_contract.get("schema_version"),
        "linked_factor_next_handoff_row_count": factor_next_handoff_contract.get("handoff_row_count"),
        "live_light_bootstrap_can_prepare_context": live_light_enabled,
        "requires_scope_hash_match": True,
        "requires_provider_call_ledger_or_gap": True,
        "requires_factor_next_handoff": True,
        "requires_cache_lineage": True,
        "requires_storage_backend": True,
        "requires_freshness_state": True,
        "requires_stale_cache_label": True,
        "requires_safe_error_when_missing_cache": True,
        "requires_no_overwrite_guard": True,
        "feeds_deepseek_readiness_contract": True,
        "deepseek_cache_write_blocked_until_factor_next_cache_lineage": True,
        "cache_get_may_write_cache": False,
        "react_render_may_write_cache": False,
        "search_typing_may_write_cache": False,
        "fastapi_startup_may_write_cache": False,
        "current_search_submit_writes_factor_next_cache_now": False,
        "current_search_submit_writes_deepseek_cache_now": False,
        "cache_write_allowed_now": False,
        "cache_write_implemented": False,
        "local_compute_execution_implemented": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "may_overwrite_price": False,
        "may_overwrite_holding": False,
        "may_overwrite_factor": False,
        "may_overwrite_operation_zones": False,
        "may_modify_strategy_action": False,
        "preflight_contract_is_provider_execution_evidence": False,
        "preflight_contract_is_model_correctness_evidence": False,
        "preflight_contract_is_production_evidence": False,
        "token_key_exposure_allowed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _search_quant_projection_deepseek_model_preflight_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    deepseek_on_open: bool,
    deepseek_model: str,
    cache_write_preflight_contract: dict[str, Any],
) -> dict[str, Any]:
    preflight_rows = [
        {
            "preflight_key": "factor_next_cache_lineage_ready",
            "preflight_order": 1,
            "source_contract": "search_quant_projection_cache_write_preflight_contract",
            "required_state": "Factor Quant Hub and Next Session cache lineage is visible before model explanation",
            "required_fields": ["source_task_id", "scope_hash", "output_packet_keys", "freshness_state", "provider_gap"],
        },
        {
            "preflight_key": "model_input_packet_whitelist_bound",
            "preflight_order": 2,
            "source_contract": "search_quant_projection_result_surface_contract",
            "required_state": "model input is limited to whitelisted research surfaces and safe ledger summaries",
            "required_fields": [
                "data_provenance",
                "freshness_provider_gap",
                "factor_evidence_effects",
                "next_session_echarts_projection",
            ],
        },
        {
            "preflight_key": "prompt_redaction_boundary_bound",
            "preflight_order": 3,
            "source_contract": "live_light_ledger_redaction_invariant_contract",
            "required_state": "raw prompt, raw model output, credential values, and env key names stay out of frontend/log/packet/cache",
            "required_fields": ["input_hash", "credential_values_excluded", "raw_prompt_excluded"],
        },
        {
            "preflight_key": "model_ledger_fields_bound",
            "preflight_order": 4,
            "source_contract": "deepseek_pro_strategy_contract",
            "required_state": "model ledger carries model, purpose, token usage, parse status, cache status, sanitizer status, and hashes",
            "required_fields": [
                "model_used",
                "purpose",
                "token_usage",
                "parse_status",
                "cache_status",
                "sanitizer_status",
                "input_hash",
                "output_hash",
            ],
        },
        {
            "preflight_key": "output_schema_whitelist_bound",
            "preflight_order": 5,
            "source_contract": "deepseek_pro_strategy_contract",
            "required_state": "model output is accepted only if it parses into the six whitelisted explanation fields",
            "required_fields": list(DEEPSEEK_EXPLANATION_FIELDS),
        },
        {
            "preflight_key": "model_cache_lineage_policy_bound",
            "preflight_order": 6,
            "source_contract": "live_light_cache_lineage_contract",
            "required_state": "DeepSeek explanation cache records model ledger ids, parse status, sanitizer status, hashes, freshness, and safe errors",
            "required_fields": [
                "model_ledger_ids",
                "parse_status",
                "sanitizer_status",
                "input_hash",
                "output_hash",
                "freshness_state",
                "safe_error",
            ],
        },
        {
            "preflight_key": "execution_request_and_rate_limit_bound",
            "preflight_order": 7,
            "source_contract": "live_light_execution_request_handoff_contract",
            "required_state": "model call remains behind execution-request, task polling, rate-limit/session dedupe, and no-trade boundaries",
            "required_fields": ["execution_request_id", "scope_hash", "rate_limit_seconds", "task_status_route"],
        },
    ]
    common_flags = {
        "preflight_contract_only": True,
        "ready_now": False,
        "model_call_allowed_now": False,
        "model_execution_implemented": False,
        "model_called_now": False,
        "model_cache_written_now": False,
        "model_ledger_written_now": False,
        "cache_get_may_call_deepseek": False,
        "react_render_may_call_deepseek": False,
        "search_typing_may_call_deepseek": False,
        "fastapi_startup_may_call_deepseek": False,
        "search_submit_may_call_deepseek_now": False,
        "provider_model_execution_requires_execution_request": True,
        "model_ledger_required": True,
        "raw_prompt_visible_allowed": False,
        "raw_model_output_visible_allowed": False,
        "token_key_exposure_allowed": False,
        "deepseek_is_data_source": False,
        "deepseek_may_overwrite_numeric_or_action_fields": False,
        "row_is_model_correctness_evidence": False,
        "row_is_production_evidence": False,
        "external_calls_triggered": False,
        "deepseek_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    preflight_rows = [{**row, **common_flags} for row in preflight_rows]
    return {
        "schema_version": SEARCH_QUANT_DEEPSEEK_MODEL_PREFLIGHT_CONTRACT_SCHEMA_VERSION,
        "status": "search_quant_deepseek_model_preflight_visible_model_call_pending"
        if active_mode in {"manual", "live_light"}
        else "inactive_until_manual_or_live_light_mode",
        "mode": active_mode,
        "display_action": "生成 3.0 量化推演",
        "allowed_modes": ["manual", "live_light"],
        "task_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "provider_model_route": SEARCH_QUANT_PROVIDER_MODEL_ROUTE,
        "provider_model_route_requires_execution_request": True,
        "deepseek_configured_for_live_light": bool(live_light_enabled and deepseek_on_open),
        "deepseek_model_label": deepseek_model,
        "linked_cache_write_preflight_schema_version": cache_write_preflight_contract.get("schema_version"),
        "linked_cache_write_preflight_row_count": cache_write_preflight_contract.get("preflight_row_count"),
        "preflight_rows": preflight_rows,
        "preflight_row_count": len(preflight_rows),
        "ready_now_row_count": 0,
        "model_called_row_count": 0,
        "model_cache_written_row_count": 0,
        "model_ledger_written_row_count": 0,
        "required_preflight_keys": [row["preflight_key"] for row in preflight_rows],
        "required_input_packet_keys": [
            "command_center_factor_quant_hub_packet",
            "command_center_next_session_projection_packet",
        ],
        "allowed_output_fields": list(DEEPSEEK_EXPLANATION_FIELDS),
        "allowed_output_field_count": len(DEEPSEEK_EXPLANATION_FIELDS),
        "required_model_ledger_fields": [
            "model_used",
            "purpose",
            "token_usage",
            "parse_status",
            "cache_status",
            "sanitizer_status",
            "input_hash",
            "output_hash",
        ],
        "requires_cache_write_preflight": True,
        "requires_factor_next_cache_lineage": True,
        "requires_model_input_whitelist": True,
        "requires_prompt_redaction_boundary": True,
        "requires_model_ledger": True,
        "requires_output_schema_whitelist": True,
        "requires_model_cache_lineage": True,
        "requires_execution_request_and_rate_limit": True,
        "safe_skip_allowed_when_preflight_missing": True,
        "cache_get_may_call_deepseek": False,
        "react_render_may_call_deepseek": False,
        "search_typing_may_call_deepseek": False,
        "fastapi_startup_may_call_deepseek": False,
        "search_submit_may_call_deepseek_now": False,
        "current_submit_autostart_calls_model": False,
        "model_call_allowed_now": False,
        "model_execution_implemented": False,
        "deepseek_called": False,
        "model_cache_write_implemented": False,
        "model_ledger_write_implemented": False,
        "raw_prompt_visible_allowed": False,
        "raw_model_output_visible_allowed": False,
        "token_key_exposure_allowed": False,
        "deepseek_is_data_source": False,
        "may_overwrite_price": False,
        "may_overwrite_holding": False,
        "may_overwrite_factor": False,
        "may_overwrite_operation_zones": False,
        "may_modify_strategy_action": False,
        "preflight_contract_is_model_correctness_evidence": False,
        "preflight_contract_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _search_quant_projection_deepseek_output_acceptance_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    deepseek_on_open: bool,
    deepseek_model: str,
    deepseek_model_preflight_contract: dict[str, Any],
) -> dict[str, Any]:
    acceptance_rows = [
        {
            "acceptance_key": "model_ledger_evidence_bound",
            "acceptance_order": 1,
            "source_contract": "search_quant_projection_deepseek_model_preflight_contract",
            "required_state": "model output can be reviewed only with model ledger ids, token usage, parse status, sanitizer status, and input/output hashes",
            "required_fields": [
                "model_used",
                "purpose",
                "token_usage",
                "parse_status",
                "sanitizer_status",
                "input_hash",
                "output_hash",
            ],
        },
        {
            "acceptance_key": "parse_status_gate_bound",
            "acceptance_order": 2,
            "source_contract": "deepseek_pro_strategy_contract",
            "required_state": "parse failure discards model output and produces a visible safe skip rather than displayed text",
            "required_fields": ["parse_status", "parse_error_safe", "safe_skip_reason"],
        },
        {
            "acceptance_key": "sanitizer_status_gate_bound",
            "acceptance_order": 3,
            "source_contract": "live_light_ledger_redaction_invariant_contract",
            "required_state": "sanitizer must pass before any summary field can be cached or displayed",
            "required_fields": ["sanitizer_status", "raw_prompt_excluded", "raw_model_output_excluded"],
        },
        {
            "acceptance_key": "output_schema_whitelist_enforced",
            "acceptance_order": 4,
            "source_contract": "deepseek_pro_strategy_contract",
            "required_state": "accepted output is limited to the six whitelisted explanation fields",
            "required_fields": list(DEEPSEEK_EXPLANATION_FIELDS),
        },
        {
            "acceptance_key": "safe_summary_surface_bound",
            "acceptance_order": 5,
            "source_contract": "search_quant_projection_result_surface_contract",
            "required_state": "UI may show only safe summary/status fields, not raw prompt, raw output, hidden assumptions, or credential material",
            "required_fields": ["status", "model_label", "parse_status", "safe_summary", "safe_error"],
        },
        {
            "acceptance_key": "model_cache_lineage_bound",
            "acceptance_order": 6,
            "source_contract": "live_light_cache_lineage_contract",
            "required_state": "DeepSeek explanation cache lineage references model ledger ids, input/output hashes, cache status, freshness, and safe errors",
            "required_fields": [
                "model_ledger_ids",
                "input_hash",
                "output_hash",
                "cache_status",
                "freshness_state",
                "safe_error",
            ],
        },
        {
            "acceptance_key": "no_numeric_or_action_overwrite_bound",
            "acceptance_order": 7,
            "source_contract": "runtime_hard_boundary_contract",
            "required_state": "accepted explanation text cannot overwrite prices, holdings, factor source values, operation zones, strategy action, or trading intent",
            "required_fields": ["target_fields_allowlist", "strategy_action_mutation_allowed", "trade_instruction_allowed"],
        },
    ]
    common_flags = {
        "acceptance_contract_only": True,
        "ready_now": False,
        "output_accepted_now": False,
        "model_cache_written_now": False,
        "model_ledger_written_now": False,
        "model_called_now": False,
        "parse_passed_now": False,
        "sanitizer_passed_now": False,
        "safe_skip_allowed": True,
        "cache_get_may_accept_model_output": False,
        "react_render_may_accept_model_output": False,
        "search_typing_may_accept_model_output": False,
        "fastapi_startup_may_accept_model_output": False,
        "search_submit_may_accept_model_output_now": False,
        "provider_model_execution_requires_execution_request": True,
        "model_ledger_required": True,
        "model_cache_lineage_required": True,
        "allowed_output_fields_only": True,
        "raw_prompt_visible_allowed": False,
        "raw_model_output_visible_allowed": False,
        "token_key_exposure_allowed": False,
        "deepseek_is_data_source": False,
        "deepseek_may_overwrite_numeric_or_action_fields": False,
        "row_is_model_correctness_evidence": False,
        "row_is_production_evidence": False,
        "external_calls_triggered": False,
        "deepseek_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    acceptance_rows = [{**row, **common_flags} for row in acceptance_rows]
    return {
        "schema_version": SEARCH_QUANT_DEEPSEEK_OUTPUT_ACCEPTANCE_CONTRACT_SCHEMA_VERSION,
        "status": "search_quant_deepseek_output_acceptance_visible_output_pending"
        if active_mode in {"manual", "live_light"}
        else "inactive_until_manual_or_live_light_mode",
        "mode": active_mode,
        "display_action": "生成 3.0 量化推演",
        "allowed_modes": ["manual", "live_light"],
        "task_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "provider_model_route": SEARCH_QUANT_PROVIDER_MODEL_ROUTE,
        "provider_model_route_requires_execution_request": True,
        "deepseek_configured_for_live_light": bool(live_light_enabled and deepseek_on_open),
        "deepseek_model_label": deepseek_model,
        "linked_model_preflight_schema_version": deepseek_model_preflight_contract.get("schema_version"),
        "linked_model_preflight_row_count": deepseek_model_preflight_contract.get("preflight_row_count"),
        "acceptance_rows": acceptance_rows,
        "acceptance_row_count": len(acceptance_rows),
        "ready_now_row_count": 0,
        "output_accepted_row_count": 0,
        "model_cache_written_row_count": 0,
        "model_ledger_written_row_count": 0,
        "required_acceptance_keys": [row["acceptance_key"] for row in acceptance_rows],
        "accepted_output_fields": list(DEEPSEEK_EXPLANATION_FIELDS),
        "accepted_output_field_count": len(DEEPSEEK_EXPLANATION_FIELDS),
        "safe_surface_fields": ["status", "model_label", "parse_status", "safe_summary", "safe_error"],
        "requires_model_preflight": True,
        "requires_model_ledger_evidence": True,
        "requires_parse_status_passed": True,
        "requires_sanitizer_status_passed": True,
        "requires_output_schema_whitelist": True,
        "requires_safe_summary_surface": True,
        "requires_model_cache_lineage": True,
        "requires_no_numeric_or_action_overwrite": True,
        "safe_skip_allowed_when_parse_or_sanitizer_fails": True,
        "cache_get_may_accept_model_output": False,
        "react_render_may_accept_model_output": False,
        "search_typing_may_accept_model_output": False,
        "fastapi_startup_may_accept_model_output": False,
        "search_submit_may_accept_model_output_now": False,
        "model_output_acceptance_implemented": False,
        "model_cache_write_implemented": False,
        "model_ledger_write_implemented": False,
        "model_execution_implemented": False,
        "deepseek_called": False,
        "raw_prompt_visible_allowed": False,
        "raw_model_output_visible_allowed": False,
        "token_key_exposure_allowed": False,
        "deepseek_is_data_source": False,
        "may_overwrite_price": False,
        "may_overwrite_holding": False,
        "may_overwrite_factor": False,
        "may_overwrite_operation_zones": False,
        "may_modify_strategy_action": False,
        "accepted_output_is_buy_sell_instruction": False,
        "acceptance_contract_is_model_correctness_evidence": False,
        "acceptance_contract_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _search_quant_projection_deepseek_readiness_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    deepseek_on_open: bool,
    deepseek_model: str,
) -> dict[str, Any]:
    readiness_rows = [
        {
            "readiness_key": "safe_symbol_scope_bound",
            "readiness_order": 1,
            "required_state": "searched symbol has been normalized, deduped, capped, and bound to a safe scope hash",
            "source_contract": "search_quant_projection_workflow_contract",
            "current_status": "required_before_model_explanation",
        },
        {
            "readiness_key": "provider_call_ledger_ready",
            "readiness_order": 2,
            "required_state": "Tushare light facts have call-ledger rows or explicit provider-gap skips",
            "source_contract": "tushare_light_strategy_contract",
            "current_status": "pending_provider_or_gap_evidence",
        },
        {
            "readiness_key": "factor_light_cache_ready",
            "readiness_order": 3,
            "required_state": "Factor light support/suppress/neutral/missing rows are available with lineage",
            "source_contract": "search_quant_projection_cache_write_preflight_contract",
            "current_status": "pending_local_compute_lineage",
        },
        {
            "readiness_key": "next_session_cache_ready",
            "readiness_order": 4,
            "required_state": "Next Session projection cache is available with freshness and operation-zone lineage",
            "source_contract": "search_quant_projection_cache_write_preflight_contract",
            "current_status": "pending_next_session_lineage",
        },
        {
            "readiness_key": "model_ledger_contract_ready",
            "readiness_order": 5,
            "required_state": "DeepSeek explanation has a model-ledger shape, token usage, parse status, input hash, and output hash",
            "source_contract": "search_quant_projection_deepseek_model_preflight_contract",
            "current_status": "model_ledger_required_before_model_call",
        },
        {
            "readiness_key": "safe_skip_if_data_not_ready",
            "readiness_order": 6,
            "required_state": "missing provider/factor/next-session readiness produces a visible safe skip instead of synthesized explanation",
            "source_contract": "live_light_freshness_provider_gap_contract",
            "current_status": "safe_skip_required",
        },
    ]
    common_flags = {
        "required_before_deepseek_call": True,
        "ready_now": False,
        "safe_skip_allowed": True,
        "cache_get_may_call_deepseek": False,
        "react_render_may_call_deepseek": False,
        "search_typing_may_call_deepseek": False,
        "fastapi_startup_may_call_deepseek": False,
        "search_submit_may_call_deepseek_now": False,
        "provider_model_execution_requires_execution_request": True,
        "model_ledger_required": True,
        "raw_prompt_visible_allowed": False,
        "raw_model_output_visible_allowed": False,
        "token_key_exposure_allowed": False,
        "deepseek_is_data_source": False,
        "deepseek_may_overwrite_numeric_or_action_fields": False,
        "row_is_model_correctness_evidence": False,
        "row_is_production_evidence": False,
        "external_calls_triggered": False,
        "deepseek_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    readiness_rows = [{**row, **common_flags} for row in readiness_rows]
    return {
        "schema_version": SEARCH_QUANT_DEEPSEEK_READINESS_CONTRACT_SCHEMA_VERSION,
        "status": "search_quant_deepseek_readiness_visible_model_execution_pending"
        if active_mode in {"manual", "live_light"}
        else "inactive_until_manual_or_live_light_mode",
        "mode": active_mode,
        "display_action": "生成 3.0 量化推演",
        "allowed_modes": ["manual", "live_light"],
        "task_route": SEARCH_QUANT_PROJECTION_ROUTE,
        "provider_model_route": SEARCH_QUANT_PROVIDER_MODEL_ROUTE,
        "provider_model_route_requires_execution_request": True,
        "live_light_bootstrap_can_prepare_context": live_light_enabled,
        "deepseek_configured_for_live_light": bool(live_light_enabled and deepseek_on_open),
        "deepseek_model_label": deepseek_model,
        "readiness_rows": readiness_rows,
        "readiness_row_count": len(readiness_rows),
        "ready_now_row_count": 0,
        "required_readiness_keys": [row["readiness_key"] for row in readiness_rows],
        "requires_safe_symbol_scope": True,
        "requires_provider_call_ledger_or_gap": True,
        "requires_factor_light_cache": True,
        "requires_next_session_cache": True,
        "requires_model_ledger": True,
        "requires_safe_skip_when_data_not_ready": True,
        "allowed_output_fields": list(DEEPSEEK_EXPLANATION_FIELDS),
        "allowed_output_field_count": len(DEEPSEEK_EXPLANATION_FIELDS),
        "model_ledger_required_fields": [
            "model_used",
            "purpose",
            "token_usage",
            "parse_status",
            "cache_status",
            "sanitizer_status",
            "input_hash",
            "output_hash",
        ],
        "cache_get_may_call_deepseek": False,
        "react_render_may_call_deepseek": False,
        "search_typing_may_call_deepseek": False,
        "fastapi_startup_may_call_deepseek": False,
        "search_submit_may_call_deepseek_now": False,
        "current_submit_autostart_calls_model": False,
        "provider_model_execution_requires_execution_request": True,
        "model_execution_implemented": False,
        "deepseek_called": False,
        "external_calls_triggered": False,
        "raw_prompt_visible_allowed": False,
        "raw_model_output_visible_allowed": False,
        "token_key_exposure_allowed": False,
        "deepseek_is_data_source": False,
        "may_overwrite_price": False,
        "may_overwrite_holding": False,
        "may_overwrite_factor": False,
        "may_overwrite_operation_zones": False,
        "may_modify_strategy_action": False,
        "readiness_contract_is_model_correctness_evidence": False,
        "readiness_contract_is_production_evidence": False,
        "production_deepseek_explanation_complete": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _tushare_light_strategy_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    live_light_sources_enabled: bool,
    tushare_on_open: bool,
    symbol_limit: int,
) -> dict[str, Any]:
    return {
        "schema_version": "command_center_tushare_light_strategy_contract.v1",
        "status": "tushare_light_strategy_visible_provider_execution_pending",
        "mode": active_mode,
        "provider": "tushare",
        "allowed_live_light_startup_apis": list(DEFAULT_LIGHT_TUSHARE_APIS),
        "allowed_acceptance_apis": list(ACCEPTANCE_DRY_RUN_ALLOWED_APIS),
        "allowed_scope": "current_target_holdings_watchlist_light_only",
        "symbol_limit": symbol_limit,
        "live_light_tushare_planned": bool(live_light_enabled and live_light_sources_enabled and tushare_on_open),
        "cache_get_calls_tushare": False,
        "fastapi_startup_calls_tushare": False,
        "react_render_calls_tushare": False,
        "post_task_required": True,
        "call_ledger_required": True,
        "request_params_safe_required": True,
        "safe_error_required": True,
        "provider_execution_implemented": False,
        "production_tushare_light_verified": False,
        "matrix_or_receipt_is_provider_evidence": False,
        "no_record_is_negative_evidence": False,
        "permission_denied_is_verified": False,
        "empty_dataframe_is_verified": False,
        "unselected_api_may_be_marked_verified": False,
        "full_pool_on_open_allowed": False,
        "token_key_exposure_allowed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _deepseek_pro_strategy_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    live_light_sources_enabled: bool,
    deepseek_on_open: bool,
    deepseek_model: str,
) -> dict[str, Any]:
    return {
        "schema_version": "command_center_deepseek_pro_strategy_contract.v1",
        "status": "deepseek_pro_strategy_visible_model_execution_pending",
        "mode": active_mode,
        "provider": "deepseek",
        "model": deepseek_model,
        "purpose": "explain_after_data_ready",
        "allowed_modes": ["manual", "live_light"],
        "live_light_deepseek_planned": bool(live_light_enabled and live_light_sources_enabled and deepseek_on_open),
        "cache_get_calls_deepseek": False,
        "fastapi_startup_calls_deepseek": False,
        "react_render_calls_deepseek": False,
        "post_task_required": True,
        "model_ledger_required": True,
        "required_model_ledger_fields": [
            "model_used",
            "status",
            "token_usage",
            "parse_status",
            "cache_hit",
            "input_hash",
            "output_hash",
        ],
        "input_hash_required": True,
        "output_hash_required": True,
        "token_usage_required": True,
        "parse_status_required": True,
        "cache_hit_or_miss_required": True,
        "sanitizer_required": True,
        "parse_failed_discard_required": True,
        "allowed_output_fields": list(DEEPSEEK_EXPLANATION_FIELDS),
        "allowed_output_fields_only": True,
        "deepseek_is_data_source": False,
        "may_overwrite_price": False,
        "may_overwrite_holding": False,
        "may_overwrite_factor": False,
        "may_overwrite_operation_zones": False,
        "may_overwrite_strategy_action": False,
        "numeric_field_overwrite_allowed": False,
        "buy_sell_instruction_allowed": False,
        "sanitizer_is_model_correctness_evidence": False,
        "prompt_preview_is_model_evidence": False,
        "mock_or_receipt_is_model_evidence": False,
        "model_execution_implemented": False,
        "production_deepseek_pro_verified": False,
        "token_key_exposure_allowed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _ui_nonblocking_runtime_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    rate_limit_seconds: int,
) -> dict[str, Any]:
    return {
        "schema_version": "command_center_ui_nonblocking_runtime_contract.v1",
        "status": "ui_nonblocking_contract_visible_browser_evidence_pending",
        "mode": active_mode,
        "cache_first_render_required": True,
        "initial_cache_render_calls_provider": False,
        "fastapi_startup_external_calls": False,
        "react_initial_render_external_calls": False,
        "react_render_direct_provider_calls": False,
        "get_status_creates_task": False,
        "background_post_task_after_cache_render_only": True,
        "live_light_auto_task_allowed_after_cache_render": live_light_enabled,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "task_polling_required": True,
        "task_id_visible_required": True,
        "task_status_visible_required": True,
        "progress_visible_required": True,
        "safe_error_visible_required": True,
        "rate_limit_skipped_state_visible_required": True,
        "rate_limit_seconds": rate_limit_seconds,
        "ui_thread_blocking_provider_call_allowed": False,
        "streamlit_style_sync_rerun_blocking_allowed": False,
        "browser_runtime_evidence_complete": False,
        "performance_trace_evidence_complete": False,
        "local_contract_only": True,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_ui_nonblocking_verified": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_cache_first_polling_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    effective_search_submit_autostart: bool,
    rate_limit_seconds: int,
    external_silence_contract: dict[str, Any],
    operator_summary_contract: dict[str, Any],
    frontend_wiring_contract: dict[str, Any],
) -> dict[str, Any]:
    phase_rows = [
        {
            "phase_key": "initial_cache_render",
            "phase_order": 1,
            "phase_status": "required",
            "source": "GET cache APIs",
            "frontend_surface": "initial cache render",
            "task_route": "",
            "task_status_route": "",
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "cache_read_required": True,
            "bootstrap_status_read_required": False,
            "safe_submit_required": False,
            "polling_required": False,
            "success_refresh_required": False,
            "last_good_cache_required": True,
            "safe_error_required": False,
            "must_complete_before_local_post": True,
            "rate_limit_required": False,
            "manual_retry_only": False,
        },
        {
            "phase_key": "mode_and_config_status_read",
            "phase_order": 2,
            "phase_status": "required",
            "source": BOOTSTRAP_STATUS_ROUTE,
            "frontend_surface": "read runtime mode and safe config",
            "task_route": "",
            "task_status_route": "",
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "cache_read_required": False,
            "bootstrap_status_read_required": True,
            "safe_submit_required": False,
            "polling_required": False,
            "success_refresh_required": False,
            "last_good_cache_required": False,
            "safe_error_required": False,
            "must_complete_before_local_post": True,
            "rate_limit_required": False,
            "manual_retry_only": False,
        },
        {
            "phase_key": "after_cache_render_bootstrap_post",
            "phase_order": 3,
            "phase_status": "conditional_live_light_only",
            "source": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "frontend_surface": "after cache render live_light bootstrap",
            "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "task_status_route": "GET /api/tasks/{task_id}",
            "local_backend_post_allowed": live_light_enabled,
            "task_creation_allowed": live_light_enabled,
            "cache_read_required": False,
            "bootstrap_status_read_required": True,
            "safe_submit_required": False,
            "polling_required": True,
            "success_refresh_required": True,
            "last_good_cache_required": False,
            "safe_error_required": True,
            "must_complete_before_local_post": False,
            "rate_limit_required": True,
            "manual_retry_only": False,
        },
        {
            "phase_key": "search_submit_local_projection_post",
            "phase_order": 4,
            "phase_status": "conditional_live_light_submit_only",
            "source": SEARCH_QUANT_PROJECTION_ROUTE,
            "frontend_surface": "safe searched-symbol submit",
            "task_route": SEARCH_QUANT_PROJECTION_ROUTE,
            "task_status_route": "GET /api/tasks/{task_id}",
            "local_backend_post_allowed": effective_search_submit_autostart,
            "task_creation_allowed": effective_search_submit_autostart,
            "cache_read_required": False,
            "bootstrap_status_read_required": True,
            "safe_submit_required": True,
            "polling_required": True,
            "success_refresh_required": True,
            "last_good_cache_required": False,
            "safe_error_required": True,
            "must_complete_before_local_post": False,
            "rate_limit_required": True,
            "manual_retry_only": False,
        },
        {
            "phase_key": "task_status_polling",
            "phase_order": 5,
            "phase_status": "required_after_local_post",
            "source": "GET /api/tasks/{task_id}",
            "frontend_surface": "task status panel polling",
            "task_route": "",
            "task_status_route": "GET /api/tasks/{task_id}",
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "cache_read_required": False,
            "bootstrap_status_read_required": False,
            "safe_submit_required": False,
            "polling_required": True,
            "success_refresh_required": False,
            "last_good_cache_required": False,
            "safe_error_required": True,
            "must_complete_before_local_post": False,
            "rate_limit_required": False,
            "manual_retry_only": False,
        },
        {
            "phase_key": "success_refresh_cache_and_status",
            "phase_order": 6,
            "phase_status": "required_after_success",
            "source": "GET cache APIs plus GET /api/bootstrap/status",
            "frontend_surface": "refresh research cache and operator status",
            "task_route": "",
            "task_status_route": "",
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "cache_read_required": True,
            "bootstrap_status_read_required": True,
            "safe_submit_required": False,
            "polling_required": False,
            "success_refresh_required": True,
            "last_good_cache_required": False,
            "safe_error_required": False,
            "must_complete_before_local_post": False,
            "rate_limit_required": False,
            "manual_retry_only": False,
        },
        {
            "phase_key": "failure_recovery_last_good_cache",
            "phase_order": 7,
            "phase_status": "required_on_failure",
            "source": "last-good cache plus safe_error",
            "frontend_surface": "failure recovery without auto retry",
            "task_route": "",
            "task_status_route": "",
            "local_backend_post_allowed": False,
            "task_creation_allowed": False,
            "cache_read_required": True,
            "bootstrap_status_read_required": True,
            "safe_submit_required": False,
            "polling_required": False,
            "success_refresh_required": False,
            "last_good_cache_required": True,
            "safe_error_required": True,
            "must_complete_before_local_post": False,
            "rate_limit_required": False,
            "manual_retry_only": True,
        },
    ]
    common_phase_flags = {
        "react_render_blocks_on_task": False,
        "react_render_direct_provider_calls": False,
        "direct_provider_or_model_call_allowed": False,
        "frontend_provider_call_allowed": False,
        "frontend_model_call_allowed": False,
        "github_call_allowed": False,
        "trading_call_allowed": False,
        "credential_value_read_allowed": False,
        "raw_payload_or_prompt_visible_allowed": False,
        "provider_model_execution_requires_execution_request": True,
        "phase_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    phase_rows = [{**row, **common_phase_flags} for row in phase_rows]
    return {
        "schema_version": BOOTSTRAP_CACHE_FIRST_POLLING_SCHEMA_VERSION,
        "status": "runtime_cache_first_polling_visible_browser_evidence_pending"
        if live_light_enabled
        else "runtime_cache_first_polling_visible_mode_gated",
        "mode": active_mode,
        "phase_rows": phase_rows,
        "phase_count": len(phase_rows),
        "phase_order": [row["phase_key"] for row in phase_rows],
        "cache_first_phase_key": "initial_cache_render",
        "status_read_phase_key": "mode_and_config_status_read",
        "bootstrap_post_phase_key": "after_cache_render_bootstrap_post",
        "search_submit_phase_key": "search_submit_local_projection_post",
        "polling_phase_key": "task_status_polling",
        "success_refresh_phase_key": "success_refresh_cache_and_status",
        "failure_recovery_phase_key": "failure_recovery_last_good_cache",
        "cache_first_render_required": True,
        "post_task_after_cache_render_only": True,
        "safe_search_submit_after_status_gate_only": True,
        "polling_required": True,
        "success_refreshes_cache_and_status": True,
        "failure_recovery_keeps_last_good_cache": True,
        "manual_retry_only_after_failure": True,
        "unbounded_task_queue_allowed": False,
        "rate_limit_seconds": rate_limit_seconds,
        "task_creation_allowed_phase_count": sum(1 for row in phase_rows if row["task_creation_allowed"]),
        "local_backend_post_phase_count": sum(1 for row in phase_rows if row["local_backend_post_allowed"]),
        "direct_external_call_allowed_phase_count": 0,
        "direct_provider_or_model_call_allowed_phase_count": 0,
        "linked_external_silence_schema_version": external_silence_contract.get("schema_version"),
        "linked_external_silence_row_count": external_silence_contract.get("silence_row_count"),
        "linked_operator_summary_schema_version": operator_summary_contract.get("schema_version"),
        "linked_frontend_wiring_schema_version": frontend_wiring_contract.get("schema_version"),
        "frontend_wiring_implemented": False,
        "frontend_acceptance_test_implemented": False,
        "browser_runtime_evidence_pending": True,
        "browser_runtime_evidence_complete": False,
        "performance_trace_evidence_complete": False,
        "contract_creates_task": False,
        "contract_calls_provider_or_model": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "contract_is_production_evidence": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_frontend_enablement_gate_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    rollout_roadmap_contract: dict[str, Any],
    cache_first_polling_contract: dict[str, Any],
    frontend_wiring_contract: dict[str, Any],
    external_silence_contract: dict[str, Any],
) -> dict[str, Any]:
    gate_rows = [
        {
            "gate_key": "stage_04_is_next_implementation",
            "gate_order": 1,
            "gate_type": "roadmap",
            "passed": rollout_roadmap_contract.get("next_implementation_stage_key")
            == "stage_04_frontend_nonblocking_wiring",
            "required_before_enable": True,
            "evidence_required": "live_light_rollout_roadmap_contract",
            "pending_reason": "",
        },
        {
            "gate_key": "live_light_mode_and_safe_config_visible",
            "gate_order": 2,
            "gate_type": "mode_config",
            "passed": live_light_enabled,
            "required_before_enable": True,
            "evidence_required": "safe_config_contract_and_mode_rows",
            "pending_reason": "" if live_light_enabled else "requires_live_light_mode",
        },
        {
            "gate_key": "backend_local_search_projection_ready",
            "gate_order": 3,
            "gate_type": "backend_local",
            "passed": rollout_roadmap_contract.get("backend_local_search_projection_ready") is True,
            "required_before_enable": True,
            "evidence_required": "local_route_task_status_replay_config_handoff",
            "pending_reason": "",
        },
        {
            "gate_key": "cache_first_polling_contract_ready",
            "gate_order": 4,
            "gate_type": "runtime_contract",
            "passed": cache_first_polling_contract.get("phase_count") == 7
            and cache_first_polling_contract.get("cache_first_render_required") is True
            and cache_first_polling_contract.get("polling_required") is True
            and cache_first_polling_contract.get("failure_recovery_keeps_last_good_cache") is True,
            "required_before_enable": True,
            "evidence_required": "runtime_cache_first_polling_contract",
            "pending_reason": "",
        },
        {
            "gate_key": "frontend_wiring_acceptance_contract_ready",
            "gate_order": 5,
            "gate_type": "runtime_contract",
            "passed": frontend_wiring_contract.get("status")
            == "frontend_wiring_acceptance_pending_backend_ready",
            "required_before_enable": True,
            "evidence_required": "search_quant_projection_frontend_wiring_acceptance_contract",
            "pending_reason": "",
        },
        {
            "gate_key": "initial_cache_render_silent_browser_trace",
            "gate_order": 6,
            "gate_type": "browser_evidence",
            "passed": False,
            "required_before_enable": True,
            "evidence_required": "browser_network_trace_no_initial_post_or_provider_call",
            "pending_reason": "browser_network_trace_pending",
        },
        {
            "gate_key": "safe_submit_single_local_post_browser_trace",
            "gate_order": 7,
            "gate_type": "browser_evidence",
            "passed": False,
            "required_before_enable": True,
            "evidence_required": "browser_network_trace_at_most_one_local_post",
            "pending_reason": "browser_network_trace_pending",
        },
        {
            "gate_key": "task_polling_and_success_refresh_browser_trace",
            "gate_order": 8,
            "gate_type": "browser_evidence",
            "passed": False,
            "required_before_enable": True,
            "evidence_required": "visible_task_polling_and_cache_status_refresh",
            "pending_reason": "browser_runtime_evidence_pending",
        },
        {
            "gate_key": "failure_recovery_last_good_cache_browser_trace",
            "gate_order": 9,
            "gate_type": "browser_evidence",
            "passed": False,
            "required_before_enable": True,
            "evidence_required": "safe_error_last_good_cache_and_manual_retry_only",
            "pending_reason": "failure_recovery_evidence_pending",
        },
        {
            "gate_key": "frontend_provider_model_silence_browser_trace",
            "gate_order": 10,
            "gate_type": "browser_evidence",
            "passed": False,
            "required_before_enable": True,
            "evidence_required": "no_frontend_tushare_deepseek_github_or_trading_calls",
            "pending_reason": "browser_network_trace_pending",
        },
        {
            "gate_key": "research_only_boundaries_visible_browser_trace",
            "gate_order": 11,
            "gate_type": "browser_evidence",
            "passed": False,
            "required_before_enable": True,
            "evidence_required": "no_trade_no_action_and_provider_model_pending_visible",
            "pending_reason": "browser_visual_evidence_pending",
        },
        {
            "gate_key": "frontend_code_wiring_implemented",
            "gate_order": 12,
            "gate_type": "frontend_implementation",
            "passed": frontend_wiring_contract.get("manual_button_frontend_wiring_implemented") is True
            and frontend_wiring_contract.get("manual_button_task_launch_receipt_bound") is True
            and frontend_wiring_contract.get("manual_button_task_status_polling_bound") is True
            and frontend_wiring_contract.get("manual_button_success_refresh_bound") is True,
            "required_before_enable": True,
            "evidence_required": "CandidateRadar_task_receipt_task_status_panel_wiring",
            "pending_reason": "",
        },
    ]
    common_gate_flags = {
        "enables_external_call_directly": False,
        "creates_task": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "react_render_direct_provider_calls": False,
        "provider_model_execution_requires_execution_request": True,
        "gate_row_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    gate_rows = [
        {
            **row,
            **common_gate_flags,
            "blocks_enablement": row["required_before_enable"] and not row["passed"],
        }
        for row in gate_rows
    ]
    blocking_rows = [row for row in gate_rows if row["blocks_enablement"]]
    return {
        "schema_version": BOOTSTRAP_FRONTEND_ENABLEMENT_GATE_SCHEMA_VERSION,
        "status": "frontend_enablement_blocked_browser_evidence_pending"
        if live_light_enabled
        else "frontend_enablement_blocked_until_live_light_mode",
        "mode": active_mode,
        "target_stage_key": "stage_04_frontend_nonblocking_wiring",
        "target_frontend_route": "desktop/src/routes/CandidateRadar.tsx",
        "gate_rows": gate_rows,
        "gate_row_count": len(gate_rows),
        "passed_gate_count": sum(1 for row in gate_rows if row["passed"]),
        "blocking_row_count": len(blocking_rows),
        "blocking_gate_keys": [row["gate_key"] for row in blocking_rows],
        "frontend_enablement_allowed": False,
        "frontend_submit_autostart_wiring_can_be_enabled": False,
        "browser_network_trace_required": True,
        "browser_runtime_evidence_complete": False,
        "failure_recovery_evidence_complete": False,
        "frontend_wiring_implemented": False,
        "frontend_acceptance_test_implemented": False,
        "backend_local_search_projection_ready": rollout_roadmap_contract.get(
            "backend_local_search_projection_ready"
        )
        is True,
        "linked_rollout_schema_version": rollout_roadmap_contract.get("schema_version"),
        "linked_cache_first_polling_schema_version": cache_first_polling_contract.get("schema_version"),
        "linked_frontend_wiring_schema_version": frontend_wiring_contract.get("schema_version"),
        "linked_external_silence_schema_version": external_silence_contract.get("schema_version"),
        "next_required_evidence": [
            "browser_network_trace",
            "failure_recovery_browser_trace",
            "research_only_boundary_visual_check",
        ],
        "contract_creates_task": False,
        "contract_calls_provider_or_model": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "contract_is_production_evidence": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_browser_evidence_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    frontend_enablement_gate_contract: dict[str, Any],
    cache_first_polling_contract: dict[str, Any],
    frontend_wiring_contract: dict[str, Any],
    external_silence_contract: dict[str, Any],
) -> dict[str, Any]:
    evidence_rows = [
        {
            "evidence_key": "initial_cache_render_silent_browser_trace",
            "evidence_order": 1,
            "evidence_type": "network_trace",
            "target_surface": "initial_cache_render",
            "required_evidence": "page load network trace with no local task POST and no provider/model calls",
            "allowed_route_patterns": ["GET /api/*/cache", BOOTSTRAP_STATUS_ROUTE],
            "forbidden_route_patterns": [
                "POST /api/bootstrap/live-startup before cache render completes",
                SEARCH_QUANT_PROJECTION_ROUTE,
                "frontend Tushare/DeepSeek/GitHub/trading URL",
            ],
            "required_ui_assertion": "cache content renders before task receipt or status polling",
        },
        {
            "evidence_key": "search_typing_silent_browser_trace",
            "evidence_order": 2,
            "evidence_type": "network_trace",
            "target_surface": "search_input_typing",
            "required_evidence": "typing into Candidate Radar search creates no task and no provider/model call",
            "allowed_route_patterns": ["GET cache/status already in flight"],
            "forbidden_route_patterns": [
                SEARCH_QUANT_PROJECTION_ROUTE,
                PLANNED_BOOTSTRAP_TASK_ROUTE,
                "frontend Tushare/DeepSeek/GitHub/trading URL",
            ],
            "required_ui_assertion": "search text may update locally without task receipt",
        },
        {
            "evidence_key": "safe_submit_single_local_post_browser_trace",
            "evidence_order": 3,
            "evidence_type": "network_trace",
            "target_surface": "safe_searched_symbol_submit",
            "required_evidence": "safe submit emits at most one local quant-projection POST and captures returned task id",
            "allowed_route_patterns": [SEARCH_QUANT_PROJECTION_ROUTE, "GET /api/tasks/{task_id}"],
            "forbidden_route_patterns": [
                "second unbounded local POST for same submit",
                "frontend Tushare/DeepSeek/GitHub/trading URL",
            ],
            "required_ui_assertion": "TaskLaunchReceipt shows the local task id",
        },
        {
            "evidence_key": "task_polling_and_success_refresh_browser_trace",
            "evidence_order": 4,
            "evidence_type": "network_trace_and_ui_state",
            "target_surface": "task_status_polling_success_refresh",
            "required_evidence": "GET /api/tasks/{task_id} polling is visible and success refreshes cache plus bootstrap status",
            "allowed_route_patterns": [
                "GET /api/tasks/{task_id}",
                "GET /api/candidate-radar/cache",
                BOOTSTRAP_STATUS_ROUTE,
            ],
            "forbidden_route_patterns": ["frontend provider/model direct call", "trade/order route"],
            "required_ui_assertion": "task status/progress and refreshed research cache are visible",
        },
        {
            "evidence_key": "failure_recovery_last_good_cache_browser_trace",
            "evidence_order": 5,
            "evidence_type": "failure_recovery_trace",
            "target_surface": "post_or_task_failure",
            "required_evidence": "failed POST or task failure preserves last-good cache, shows safe_error, and keeps retry manual",
            "allowed_route_patterns": ["GET last-good cache", "GET /api/tasks/{task_id}"],
            "forbidden_route_patterns": ["automatic retry POST", "unbounded replacement task", "raw exception leak"],
            "required_ui_assertion": "safe error, stale/last-good label, and manual retry boundary are visible",
        },
        {
            "evidence_key": "frontend_provider_model_secret_silence_browser_trace",
            "evidence_order": 6,
            "evidence_type": "network_trace_and_payload_review",
            "target_surface": "frontend_packet_and_network",
            "required_evidence": "browser trace and packet review show no frontend provider/model/GitHub/trading calls and no token/key material",
            "allowed_route_patterns": ["local FastAPI cache/status/task routes only"],
            "forbidden_route_patterns": [
                "Tushare endpoint",
                "DeepSeek endpoint",
                "GitHub endpoint",
                "Authorization/Bearer/token/key in packet",
            ],
            "required_ui_assertion": "provider/model pending state is visible without raw credentials",
        },
        {
            "evidence_key": "research_only_boundaries_visible_browser_trace",
            "evidence_order": 7,
            "evidence_type": "visual_assertion",
            "target_surface": "candidate_radar_result_surfaces",
            "required_evidence": "visual/browser check shows no-trade, no-action, provider/model pending, and radar candidate non-buy boundaries",
            "allowed_route_patterns": ["read-only UI render"],
            "forbidden_route_patterns": ["trade/order route", "strategy action mutation route"],
            "required_ui_assertion": "research-only/no-trade/no-action boundaries remain visible after task lifecycle",
        },
    ]
    common_evidence_flags = {
        "required_before_frontend_enablement": True,
        "evidence_collected": False,
        "passed": False,
        "blocks_frontend_enablement": True,
        "requires_browser_network_trace": True,
        "frontend_wiring_required": True,
        "creates_task": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "react_render_direct_provider_calls": False,
        "provider_model_execution_requires_execution_request": True,
        "evidence_row_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    evidence_rows = [{**row, **common_evidence_flags} for row in evidence_rows]
    return {
        "schema_version": BOOTSTRAP_BROWSER_EVIDENCE_SCHEMA_VERSION,
        "status": "browser_evidence_contract_visible_collection_pending"
        if live_light_enabled
        else "browser_evidence_contract_inactive_until_live_light_mode",
        "mode": active_mode,
        "target_stage_key": "stage_04_frontend_nonblocking_wiring",
        "target_frontend_route": "desktop/src/routes/CandidateRadar.tsx",
        "evidence_rows": evidence_rows,
        "evidence_row_count": len(evidence_rows),
        "collected_evidence_row_count": 0,
        "passed_evidence_row_count": 0,
        "blocking_evidence_row_count": len(evidence_rows),
        "required_viewports": ["desktop", "laptop", "tablet", "mobile"],
        "network_trace_required": True,
        "failure_recovery_trace_required": True,
        "visual_boundary_check_required": True,
        "browser_evidence_complete": False,
        "failure_recovery_evidence_complete": False,
        "research_only_visual_evidence_complete": False,
        "frontend_wiring_implemented": False,
        "frontend_enablement_allowed_after_browser_evidence": False,
        "contract_can_promote_frontend_enablement": False,
        "linked_frontend_enablement_gate_schema_version": frontend_enablement_gate_contract.get("schema_version"),
        "linked_frontend_enablement_blocking_row_count": frontend_enablement_gate_contract.get(
            "blocking_row_count"
        ),
        "linked_cache_first_polling_schema_version": cache_first_polling_contract.get("schema_version"),
        "linked_frontend_wiring_schema_version": frontend_wiring_contract.get("schema_version"),
        "linked_external_silence_schema_version": external_silence_contract.get("schema_version"),
        "contract_creates_task": False,
        "contract_calls_provider_or_model": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "contract_is_production_evidence": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_frontend_wiring_manifest_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    frontend_enablement_gate_contract: dict[str, Any],
    browser_evidence_contract: dict[str, Any],
    cache_first_polling_contract: dict[str, Any],
    frontend_wiring_contract: dict[str, Any],
) -> dict[str, Any]:
    manifest_rows = [
        {
            "manifest_key": "bootstrap_status_mode_gate",
            "manifest_order": 1,
            "target_file": "desktop/src/routes/CandidateRadar.tsx",
            "target_surface": "Candidate Radar page bootstrap status read",
            "target_helper_or_component": "bootstrap status client read",
            "required_route": BOOTSTRAP_STATUS_ROUTE,
            "required_state": ["active_mode", "effective_submit_autostart", "runtime_frontend_enablement_allowed"],
            "required_behavior": "read status before any live_light safe-submit autostart decision",
            "local_post_allowed_after_behavior": False,
        },
        {
            "manifest_key": "cache_first_initial_render_guard",
            "manifest_order": 2,
            "target_file": "desktop/src/routes/CandidateRadar.tsx",
            "target_surface": "initial cache render",
            "target_helper_or_component": "Candidate Radar cache loader",
            "required_route": "GET /api/candidate-radar/cache",
            "required_state": ["cache_loaded", "initial_render_complete"],
            "required_behavior": "render cached research surfaces before any local POST task",
            "local_post_allowed_after_behavior": False,
        },
        {
            "manifest_key": "safe_submit_handler",
            "manifest_order": 3,
            "target_file": "desktop/src/routes/CandidateRadar.tsx",
            "target_surface": "searched-symbol safe submit",
            "target_helper_or_component": "postCandidateRadarQuantProjection",
            "required_route": SEARCH_QUANT_PROJECTION_ROUTE,
            "required_state": ["safe_symbol", "task_id_from_post_response", "rate_limit_reuse_state"],
            "required_behavior": "create or reuse one local projection task only after explicit safe submit and status gate",
            "local_post_allowed_after_behavior": live_light_enabled,
        },
        {
            "manifest_key": "task_launch_receipt_binding",
            "manifest_order": 4,
            "target_file": "desktop/src/routes/CandidateRadar.tsx",
            "target_surface": "task launch receipt",
            "target_helper_or_component": "TaskLaunchReceipt",
            "required_route": SEARCH_QUANT_PROJECTION_ROUTE,
            "required_state": ["task_id", "task_type", "route", "mode"],
            "required_behavior": "show local task id and local-only receipt after POST response",
            "local_post_allowed_after_behavior": False,
        },
        {
            "manifest_key": "task_status_panel_polling",
            "manifest_order": 5,
            "target_file": "desktop/src/routes/CandidateRadar.tsx",
            "target_surface": "task status panel",
            "target_helper_or_component": "TaskStatusPanel",
            "required_route": "GET /api/tasks/{task_id}",
            "required_state": ["status", "progress", "current_step", "safe_error"],
            "required_behavior": "poll local task status without blocking render or calling providers from React",
            "local_post_allowed_after_behavior": False,
        },
        {
            "manifest_key": "success_refresh_cache_and_status",
            "manifest_order": 6,
            "target_file": "desktop/src/routes/CandidateRadar.tsx",
            "target_surface": "success refresh",
            "target_helper_or_component": "Candidate Radar cache and bootstrap status reload",
            "required_route": "GET /api/candidate-radar/cache + GET /api/bootstrap/status",
            "required_state": ["candidate_cache_refreshed", "bootstrap_status_refreshed"],
            "required_behavior": "refresh research cache and operator status after local task success",
            "local_post_allowed_after_behavior": False,
        },
        {
            "manifest_key": "failure_recovery_last_good_cache",
            "manifest_order": 7,
            "target_file": "desktop/src/routes/CandidateRadar.tsx",
            "target_surface": "failure recovery",
            "target_helper_or_component": "Candidate Radar safe error and stale cache surfaces",
            "required_route": "GET /api/candidate-radar/cache + GET /api/tasks/{task_id}",
            "required_state": ["safe_error", "last_good_cache_visible", "manual_retry_only"],
            "required_behavior": "preserve last-good cache and expose safe error without automatic retry",
            "local_post_allowed_after_behavior": False,
        },
        {
            "manifest_key": "provider_model_pending_boundary",
            "manifest_order": 8,
            "target_file": "desktop/src/routes/CandidateRadar.tsx",
            "target_surface": "research-only boundaries",
            "target_helper_or_component": "provider/model pending and no-trade UI labels",
            "required_route": BOOTSTRAP_STATUS_ROUTE,
            "required_state": ["provider_model_pending", "no_trade", "no_action_mutation"],
            "required_behavior": "show provider/model pending and no-trade/no-action boundaries on result surfaces",
            "local_post_allowed_after_behavior": False,
        },
        {
            "manifest_key": "browser_evidence_hook",
            "manifest_order": 9,
            "target_file": "tests_or_manual_browser_acceptance",
            "target_surface": "browser evidence collection",
            "target_helper_or_component": "network trace and visual assertion harness",
            "required_route": "browser trace over local FastAPI routes",
            "required_state": ["network_trace", "failure_trace", "visual_boundary_check"],
            "required_behavior": "collect the seven runtime_browser_evidence_contract rows before enablement",
            "local_post_allowed_after_behavior": False,
        },
    ]
    common_manifest_flags = {
        "required_before_frontend_enablement": True,
        "implementation_done": False,
        "browser_evidence_required": True,
        "creates_task_from_render": False,
        "creates_task_from_typing": False,
        "cache_get_creates_task": False,
        "react_render_direct_provider_calls": False,
        "frontend_provider_call_allowed": False,
        "frontend_model_call_allowed": False,
        "token_key_exposure_allowed": False,
        "provider_model_execution_requires_execution_request": True,
        "manifest_row_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    manual_button_manifest_done_keys = {
        "bootstrap_status_mode_gate",
        "cache_first_initial_render_guard",
        "safe_submit_handler",
        "task_launch_receipt_binding",
        "task_status_panel_polling",
        "success_refresh_cache_and_status",
        "provider_model_pending_boundary",
    }
    manifest_rows = [
        {
            **row,
            **common_manifest_flags,
            "implementation_done": row["manifest_key"] in manual_button_manifest_done_keys,
            "implementation_scope": (
                "manual_button_path_ready_browser_evidence_pending"
                if row["manifest_key"] in manual_button_manifest_done_keys
                else "pending_browser_or_failure_recovery_evidence"
            ),
        }
        for row in manifest_rows
    ]
    implementation_done_row_count = sum(1 for row in manifest_rows if row["implementation_done"])
    pending_manifest_row_count = len(manifest_rows) - implementation_done_row_count
    return {
        "schema_version": BOOTSTRAP_FRONTEND_WIRING_MANIFEST_SCHEMA_VERSION,
        "status": "frontend_wiring_manifest_manual_button_ready_browser_evidence_pending"
        if live_light_enabled
        else "frontend_wiring_manifest_inactive_until_live_light_mode",
        "mode": active_mode,
        "target_stage_key": "stage_04_frontend_nonblocking_wiring",
        "target_frontend_route": "desktop/src/routes/CandidateRadar.tsx",
        "manifest_rows": manifest_rows,
        "manifest_row_count": len(manifest_rows),
        "implementation_done_row_count": implementation_done_row_count,
        "pending_manifest_row_count": pending_manifest_row_count,
        "manual_button_manifest_implemented": implementation_done_row_count >= len(manual_button_manifest_done_keys),
        "manual_button_manifest_done_keys": sorted(manual_button_manifest_done_keys),
        "required_manifest_keys": [row["manifest_key"] for row in manifest_rows],
        "target_components": ["TaskLaunchReceipt", "TaskStatusPanel"],
        "target_client_helpers": ["postCandidateRadarQuantProjection"],
        "required_local_routes": [
            BOOTSTRAP_STATUS_ROUTE,
            "GET /api/candidate-radar/cache",
            SEARCH_QUANT_PROJECTION_ROUTE,
            "GET /api/tasks/{task_id}",
        ],
        "frontend_wiring_implemented": False,
        "frontend_acceptance_test_implemented": False,
        "browser_evidence_complete": False,
        "frontend_enablement_allowed": False,
        "manifest_can_enable_frontend": False,
        "linked_frontend_enablement_gate_schema_version": frontend_enablement_gate_contract.get("schema_version"),
        "linked_frontend_enablement_allowed": frontend_enablement_gate_contract.get("frontend_enablement_allowed"),
        "linked_browser_evidence_schema_version": browser_evidence_contract.get("schema_version"),
        "linked_browser_evidence_complete": browser_evidence_contract.get("browser_evidence_complete"),
        "linked_cache_first_polling_schema_version": cache_first_polling_contract.get("schema_version"),
        "linked_frontend_wiring_schema_version": frontend_wiring_contract.get("schema_version"),
        "contract_creates_task": False,
        "contract_calls_provider_or_model": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "contract_is_production_evidence": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_frontend_acceptance_runbook_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    frontend_enablement_gate_contract: dict[str, Any],
    browser_evidence_contract: dict[str, Any],
    frontend_wiring_manifest_contract: dict[str, Any],
) -> dict[str, Any]:
    runbook_rows = [
        {
            "runbook_key": "prepare_cache_only_baseline",
            "runbook_order": 1,
            "target_surface": "cache_only baseline load",
            "required_route": "GET /api/candidate-radar/cache + GET /api/bootstrap/status",
            "required_artifact": "cache_only_network_trace.json",
            "required_observation": "cache_only renders cached surfaces without POST, provider, or model traffic",
            "future_collection_local_post_expected": False,
            "future_collection_local_post_route": "",
        },
        {
            "runbook_key": "prepare_live_light_config_probe",
            "runbook_order": 2,
            "target_surface": "live_light bootstrap status config probe",
            "required_route": BOOTSTRAP_STATUS_ROUTE,
            "required_artifact": "live_light_status_packet.json",
            "required_observation": "live_light status exposes mode, gates, and pending rows without execution",
            "future_collection_local_post_expected": False,
            "future_collection_local_post_route": "",
        },
        {
            "runbook_key": "capture_initial_cache_render_silence",
            "runbook_order": 3,
            "target_surface": "Candidate Radar initial cache render",
            "required_route": "GET /api/candidate-radar/cache",
            "required_artifact": "initial_cache_render_trace.json",
            "required_observation": "initial render completes from cache before any local POST task",
            "future_collection_local_post_expected": False,
            "future_collection_local_post_route": "",
        },
        {
            "runbook_key": "capture_search_typing_silence",
            "runbook_order": 4,
            "target_surface": "Candidate Radar search box typing",
            "required_route": "browser trace over local frontend state",
            "required_artifact": "search_typing_trace.json",
            "required_observation": "typing a symbol does not create task traffic or provider/model traffic",
            "future_collection_local_post_expected": False,
            "future_collection_local_post_route": "",
        },
        {
            "runbook_key": "capture_safe_submit_task_lifecycle",
            "runbook_order": 5,
            "target_surface": "Candidate Radar safe submit and task lifecycle",
            "required_route": SEARCH_QUANT_PROJECTION_ROUTE,
            "required_artifact": "safe_submit_task_lifecycle_trace.json",
            "required_observation": "safe submit shows one local POST, task receipt, and task status polling",
            "future_collection_local_post_expected": True,
            "future_collection_local_post_route": SEARCH_QUANT_PROJECTION_ROUTE,
        },
        {
            "runbook_key": "capture_success_refresh",
            "runbook_order": 6,
            "target_surface": "Candidate Radar successful task refresh",
            "required_route": "GET /api/candidate-radar/cache + GET /api/bootstrap/status",
            "required_artifact": "success_refresh_trace.json",
            "required_observation": "successful local task refreshes cache/status without blocking render",
            "future_collection_local_post_expected": False,
            "future_collection_local_post_route": "",
        },
        {
            "runbook_key": "capture_failure_recovery",
            "runbook_order": 7,
            "target_surface": "Candidate Radar task failure recovery",
            "required_route": "GET /api/candidate-radar/cache + GET /api/tasks/{task_id}",
            "required_artifact": "failure_recovery_trace.json",
            "required_observation": "failure keeps last-good cache, safe error, and manual retry only",
            "future_collection_local_post_expected": False,
            "future_collection_local_post_route": "",
        },
        {
            "runbook_key": "capture_research_only_boundaries",
            "runbook_order": 8,
            "target_surface": "research-only browser and network boundaries",
            "required_route": "browser trace over local frontend and FastAPI routes",
            "required_artifact": "research_only_boundary_trace.json",
            "required_observation": "browser proof shows no provider/model/GitHub/trading calls, tokens, or action mutation",
            "future_collection_local_post_expected": False,
            "future_collection_local_post_route": "",
        },
    ]
    common_runbook_flags = {
        "required_before_frontend_enablement": True,
        "runbook_step_complete": False,
        "artifact_collected": False,
        "blocks_frontend_enablement": True,
        "creates_task": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "frontend_provider_call_allowed": False,
        "frontend_model_call_allowed": False,
        "token_key_exposure_allowed": False,
        "provider_model_execution_requires_execution_request": True,
        "runbook_row_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    runbook_rows = [{**row, **common_runbook_flags} for row in runbook_rows]
    return {
        "schema_version": BOOTSTRAP_FRONTEND_ACCEPTANCE_RUNBOOK_SCHEMA_VERSION,
        "status": "frontend_acceptance_runbook_visible_collection_pending"
        if live_light_enabled
        else "frontend_acceptance_runbook_inactive_until_live_light_mode",
        "mode": active_mode,
        "target_stage_key": "stage_04_frontend_nonblocking_wiring",
        "target_frontend_route": "desktop/src/routes/CandidateRadar.tsx",
        "runbook_rows": runbook_rows,
        "runbook_row_count": len(runbook_rows),
        "completed_runbook_row_count": 0,
        "pending_runbook_row_count": len(runbook_rows),
        "required_runbook_keys": [row["runbook_key"] for row in runbook_rows],
        "required_artifacts": [row["required_artifact"] for row in runbook_rows],
        "browser_evidence_contract_required": True,
        "frontend_wiring_manifest_required": True,
        "frontend_enablement_allowed_after_runbook": False,
        "runbook_can_promote_frontend_enablement": False,
        "linked_frontend_enablement_gate_schema_version": frontend_enablement_gate_contract.get("schema_version"),
        "linked_frontend_enablement_allowed": frontend_enablement_gate_contract.get("frontend_enablement_allowed"),
        "linked_browser_evidence_schema_version": browser_evidence_contract.get("schema_version"),
        "linked_browser_evidence_complete": browser_evidence_contract.get("browser_evidence_complete"),
        "linked_frontend_wiring_manifest_schema_version": frontend_wiring_manifest_contract.get("schema_version"),
        "linked_frontend_wiring_manifest_pending_row_count": frontend_wiring_manifest_contract.get(
            "pending_manifest_row_count"
        ),
        "frontend_wiring_implemented": False,
        "browser_evidence_complete": False,
        "contract_creates_task": False,
        "contract_calls_provider_or_model": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "contract_is_production_evidence": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_frontend_acceptance_artifact_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    frontend_acceptance_runbook_contract: dict[str, Any],
    browser_evidence_contract: dict[str, Any],
) -> dict[str, Any]:
    artifact_rows = [
        {
            "artifact_key": "cache_only_network_trace",
            "artifact_order": 1,
            "linked_runbook_key": "prepare_cache_only_baseline",
            "artifact_file": "cache_only_network_trace.json",
            "artifact_kind": "browser_network_trace",
            "required_capture_surface": "cache_only Candidate Radar baseline load",
        },
        {
            "artifact_key": "live_light_status_packet",
            "artifact_order": 2,
            "linked_runbook_key": "prepare_live_light_config_probe",
            "artifact_file": "live_light_status_packet.json",
            "artifact_kind": "bootstrap_status_snapshot",
            "required_capture_surface": "live_light bootstrap status packet",
        },
        {
            "artifact_key": "initial_cache_render_trace",
            "artifact_order": 3,
            "linked_runbook_key": "capture_initial_cache_render_silence",
            "artifact_file": "initial_cache_render_trace.json",
            "artifact_kind": "browser_network_trace",
            "required_capture_surface": "initial cache render network trace",
        },
        {
            "artifact_key": "search_typing_trace",
            "artifact_order": 4,
            "linked_runbook_key": "capture_search_typing_silence",
            "artifact_file": "search_typing_trace.json",
            "artifact_kind": "browser_network_trace",
            "required_capture_surface": "search input typing network trace",
        },
        {
            "artifact_key": "safe_submit_task_lifecycle_trace",
            "artifact_order": 5,
            "linked_runbook_key": "capture_safe_submit_task_lifecycle",
            "artifact_file": "safe_submit_task_lifecycle_trace.json",
            "artifact_kind": "browser_network_and_task_trace",
            "required_capture_surface": "safe submit receipt and task polling trace",
        },
        {
            "artifact_key": "success_refresh_trace",
            "artifact_order": 6,
            "linked_runbook_key": "capture_success_refresh",
            "artifact_file": "success_refresh_trace.json",
            "artifact_kind": "browser_network_trace",
            "required_capture_surface": "successful task cache/status refresh trace",
        },
        {
            "artifact_key": "failure_recovery_trace",
            "artifact_order": 7,
            "linked_runbook_key": "capture_failure_recovery",
            "artifact_file": "failure_recovery_trace.json",
            "artifact_kind": "browser_network_and_failure_trace",
            "required_capture_surface": "last-good cache and safe-error recovery trace",
        },
        {
            "artifact_key": "research_only_boundary_trace",
            "artifact_order": 8,
            "linked_runbook_key": "capture_research_only_boundaries",
            "artifact_file": "research_only_boundary_trace.json",
            "artifact_kind": "browser_network_and_visual_boundary_trace",
            "required_capture_surface": "research-only no-trade/no-action boundary proof",
        },
    ]
    common_artifact_flags = {
        "storage_target": "local_redacted_stage_04_acceptance_artifacts",
        "artifact_manifest_write_pending": True,
        "artifact_collected": False,
        "artifact_exists": False,
        "artifact_hash_recorded": False,
        "artifact_redaction_reviewed": False,
        "allowed_content": [
            "local_route_method_status_timing",
            "redacted_request_response_headers",
            "task_id_and_status_summary",
            "ui_state_assertion_summary",
            "safe_error_summary",
        ],
        "prohibited_content": [
            "credential_values",
            "env_key_names",
            "authorization_headers",
            "raw_provider_response",
            "raw_prompt",
            "raw_model_output",
            "trade_or_order_payload",
        ],
        "required_redaction": [
            "authorization_headers",
            "cookie_headers",
            "token_like_values",
            "api_key_like_values",
            "raw_provider_model_payloads",
        ],
        "required_before_frontend_enablement": True,
        "blocks_frontend_enablement": True,
        "artifact_row_is_production_evidence": False,
        "creates_task": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "frontend_provider_call_allowed": False,
        "frontend_model_call_allowed": False,
        "token_key_exposure_allowed": False,
        "provider_model_execution_requires_execution_request": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    artifact_rows = [{**row, **common_artifact_flags} for row in artifact_rows]
    return {
        "schema_version": BOOTSTRAP_FRONTEND_ACCEPTANCE_ARTIFACT_SCHEMA_VERSION,
        "status": "frontend_acceptance_artifact_contract_visible_collection_pending"
        if live_light_enabled
        else "frontend_acceptance_artifact_contract_inactive_until_live_light_mode",
        "mode": active_mode,
        "target_stage_key": "stage_04_frontend_nonblocking_wiring",
        "target_frontend_route": "desktop/src/routes/CandidateRadar.tsx",
        "artifact_rows": artifact_rows,
        "artifact_row_count": len(artifact_rows),
        "collected_artifact_count": 0,
        "pending_artifact_count": len(artifact_rows),
        "artifact_collection_complete": False,
        "required_artifact_files": [row["artifact_file"] for row in artifact_rows],
        "required_artifact_keys": [row["artifact_key"] for row in artifact_rows],
        "required_storage_target": "local_redacted_stage_04_acceptance_artifacts",
        "artifact_manifest_write_pending": True,
        "artifact_hashes_required": True,
        "artifact_redaction_review_required": True,
        "artifact_redaction_review_complete": False,
        "raw_trace_upload_allowed": False,
        "frontend_packet_may_include_artifact_body": False,
        "frontend_packet_may_include_artifact_hash": True,
        "linked_frontend_acceptance_runbook_schema_version": frontend_acceptance_runbook_contract.get(
            "schema_version"
        ),
        "linked_frontend_acceptance_runbook_pending_row_count": frontend_acceptance_runbook_contract.get(
            "pending_runbook_row_count"
        ),
        "linked_browser_evidence_schema_version": browser_evidence_contract.get("schema_version"),
        "linked_browser_evidence_complete": browser_evidence_contract.get("browser_evidence_complete"),
        "frontend_wiring_implemented": False,
        "browser_evidence_complete": False,
        "contract_creates_task": False,
        "contract_calls_provider_or_model": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "contract_is_production_evidence": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_frontend_enablement_promotion_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    frontend_enablement_gate_contract: dict[str, Any],
    browser_evidence_contract: dict[str, Any],
    frontend_wiring_manifest_contract: dict[str, Any],
    frontend_acceptance_runbook_contract: dict[str, Any],
    frontend_acceptance_artifact_contract: dict[str, Any],
) -> dict[str, Any]:
    promotion_rows = [
        {
            "promotion_key": "frontend_wiring_manifest_implemented",
            "promotion_order": 1,
            "required_source_contract": "runtime_frontend_wiring_manifest_contract",
            "required_evidence": "all Candidate Radar touchpoints implemented and reviewed",
            "current_blocker": "frontend_wiring_manifest_implemented_false",
        },
        {
            "promotion_key": "browser_evidence_collected",
            "promotion_order": 2,
            "required_source_contract": "runtime_browser_evidence_contract",
            "required_evidence": "all browser evidence rows collected with network traces",
            "current_blocker": "browser_evidence_complete_false",
        },
        {
            "promotion_key": "acceptance_runbook_completed",
            "promotion_order": 3,
            "required_source_contract": "runtime_frontend_acceptance_runbook_contract",
            "required_evidence": "all stage 04 acceptance runbook steps completed",
            "current_blocker": "pending_runbook_rows",
        },
        {
            "promotion_key": "acceptance_artifacts_hashed_and_reviewed",
            "promotion_order": 4,
            "required_source_contract": "runtime_frontend_acceptance_artifact_contract",
            "required_evidence": "all artifacts exist, have hashes, and pass redaction review",
            "current_blocker": "pending_artifacts_or_redaction_review",
        },
        {
            "promotion_key": "cache_only_baseline_passed",
            "promotion_order": 5,
            "required_source_contract": "runtime_frontend_acceptance_runbook_contract",
            "required_evidence": "cache_only baseline proves GET/cache/render stay read-only",
            "current_blocker": "cache_only_baseline_trace_pending",
        },
        {
            "promotion_key": "safe_submit_lifecycle_passed",
            "promotion_order": 6,
            "required_source_contract": "runtime_cache_first_polling_contract",
            "required_evidence": "safe submit proves one local POST, receipt, polling, and refresh",
            "current_blocker": "safe_submit_task_lifecycle_trace_pending",
        },
        {
            "promotion_key": "failure_recovery_passed",
            "promotion_order": 7,
            "required_source_contract": "runtime_browser_evidence_contract",
            "required_evidence": "failure path preserves last-good cache, safe error, and manual retry",
            "current_blocker": "failure_recovery_trace_pending",
        },
        {
            "promotion_key": "research_only_boundary_passed",
            "promotion_order": 8,
            "required_source_contract": "runtime_frontend_acceptance_artifact_contract",
            "required_evidence": "no provider/model/GitHub/trading leakage, no secrets, no action mutation",
            "current_blocker": "research_only_boundary_trace_pending",
        },
    ]
    common_promotion_flags = {
        "required_before_frontend_enablement": True,
        "promotion_criterion_met": False,
        "blocks_frontend_enablement": True,
        "creates_task": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "frontend_provider_call_allowed": False,
        "frontend_model_call_allowed": False,
        "token_key_exposure_allowed": False,
        "provider_model_execution_requires_execution_request": True,
        "promotion_row_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    promotion_rows = [{**row, **common_promotion_flags} for row in promotion_rows]
    return {
        "schema_version": BOOTSTRAP_FRONTEND_ENABLEMENT_PROMOTION_SCHEMA_VERSION,
        "status": "frontend_enablement_promotion_visible_blocked"
        if live_light_enabled
        else "frontend_enablement_promotion_inactive_until_live_light_mode",
        "mode": active_mode,
        "target_stage_key": "stage_04_frontend_nonblocking_wiring",
        "target_frontend_route": "desktop/src/routes/CandidateRadar.tsx",
        "promotion_rows": promotion_rows,
        "promotion_row_count": len(promotion_rows),
        "satisfied_promotion_row_count": 0,
        "blocking_promotion_row_count": len(promotion_rows),
        "required_promotion_keys": [row["promotion_key"] for row in promotion_rows],
        "frontend_enablement_allowed": False,
        "promotion_can_enable_frontend": False,
        "browser_evidence_required": True,
        "artifact_redaction_review_required": True,
        "production_promotion_required_after_frontend_enablement": True,
        "linked_frontend_enablement_gate_schema_version": frontend_enablement_gate_contract.get("schema_version"),
        "linked_frontend_enablement_allowed": frontend_enablement_gate_contract.get("frontend_enablement_allowed"),
        "linked_browser_evidence_schema_version": browser_evidence_contract.get("schema_version"),
        "linked_browser_evidence_complete": browser_evidence_contract.get("browser_evidence_complete"),
        "linked_frontend_wiring_manifest_schema_version": frontend_wiring_manifest_contract.get("schema_version"),
        "linked_frontend_wiring_manifest_pending_row_count": frontend_wiring_manifest_contract.get(
            "pending_manifest_row_count"
        ),
        "linked_frontend_acceptance_runbook_schema_version": frontend_acceptance_runbook_contract.get(
            "schema_version"
        ),
        "linked_frontend_acceptance_runbook_pending_row_count": frontend_acceptance_runbook_contract.get(
            "pending_runbook_row_count"
        ),
        "linked_frontend_acceptance_artifact_schema_version": frontend_acceptance_artifact_contract.get(
            "schema_version"
        ),
        "linked_frontend_acceptance_artifact_pending_count": frontend_acceptance_artifact_contract.get(
            "pending_artifact_count"
        ),
        "frontend_wiring_implemented": False,
        "browser_evidence_complete": False,
        "acceptance_runbook_complete": False,
        "acceptance_artifact_collection_complete": False,
        "artifact_redaction_review_complete": False,
        "contract_creates_task": False,
        "contract_calls_provider_or_model": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "contract_is_production_evidence": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_frontend_enablement_release_switch_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    frontend_enablement_configured: bool,
    frontend_enablement_promotion_contract: dict[str, Any],
) -> dict[str, Any]:
    release_switch_rows = [
        {
            "release_switch_key": "frontend_enablement_switch_default_off",
            "release_switch_order": 1,
            "required_state": "COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT default false",
            "required_evidence": "global config layer key exists and remains effective false",
            "current_blocker": "release_switch_default_off_until_promotion_allowed",
        },
        {
            "release_switch_key": "live_light_mode_required",
            "release_switch_order": 2,
            "required_state": "active_mode must be live_light",
            "required_evidence": "cache_only/manual/live_full force frontend enablement off",
            "current_blocker": "mode_gate_or_non_live_light_mode",
        },
        {
            "release_switch_key": "promotion_contract_required",
            "release_switch_order": 3,
            "required_state": "runtime_frontend_enablement_promotion_contract allows enablement",
            "required_evidence": "all stage 04 promotion blockers cleared",
            "current_blocker": "promotion_contract_still_blocking",
        },
        {
            "release_switch_key": "server_config_source_required",
            "release_switch_order": 4,
            "required_state": "server config layer is source of truth",
            "required_evidence": "frontend cannot write enablement state or override server mode",
            "current_blocker": "promotion_evidence_incomplete",
        },
        {
            "release_switch_key": "rollback_on_evidence_regression",
            "release_switch_order": 5,
            "required_state": "evidence regression disables frontend enablement",
            "required_evidence": "failed browser evidence, missing artifact hash, or redaction failure forces off",
            "current_blocker": "rollback_contract_pending",
        },
        {
            "release_switch_key": "research_only_boundary_required",
            "release_switch_order": 6,
            "required_state": "research-only UI boundary remains visible after enablement",
            "required_evidence": "no trade/no action/provider-model pending boundaries remain visible",
            "current_blocker": "research_only_boundary_evidence_pending",
        },
        {
            "release_switch_key": "production_promotion_separate",
            "release_switch_order": 7,
            "required_state": "frontend enablement is not production live_light completion",
            "required_evidence": "real provider/model evidence and release promotion remain separate",
            "current_blocker": "production_promotion_pending",
        },
    ]
    common_switch_flags = {
        "required_before_frontend_enablement": True,
        "release_switch_criterion_met": False,
        "blocks_frontend_enablement": True,
        "effective_frontend_enablement_allowed": False,
        "creates_task": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "frontend_provider_call_allowed": False,
        "frontend_model_call_allowed": False,
        "frontend_writeback_allowed": False,
        "token_key_exposure_allowed": False,
        "provider_model_execution_requires_execution_request": True,
        "release_switch_row_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    release_switch_rows = [{**row, **common_switch_flags} for row in release_switch_rows]
    return {
        "schema_version": BOOTSTRAP_FRONTEND_ENABLEMENT_RELEASE_SWITCH_SCHEMA_VERSION,
        "status": "frontend_enablement_release_switch_visible_default_off"
        if live_light_enabled
        else "frontend_enablement_release_switch_inactive_until_live_light_mode",
        "mode": active_mode,
        "target_stage_key": "stage_04_frontend_nonblocking_wiring",
        "target_frontend_route": "desktop/src/routes/CandidateRadar.tsx",
        "release_switch_key": "COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT",
        "release_switch_rows": release_switch_rows,
        "release_switch_row_count": len(release_switch_rows),
        "satisfied_release_switch_row_count": 0,
        "blocking_release_switch_row_count": len(release_switch_rows),
        "required_release_switch_keys": [row["release_switch_key"] for row in release_switch_rows],
        "release_switch_default_enabled": False,
        "release_switch_configured": frontend_enablement_configured,
        "effective_frontend_enablement_allowed": False,
        "frontend_enablement_allowed": False,
        "release_switch_can_enable_frontend": False,
        "release_switch_source_of_truth": "server_config_layer_global_config_key_default_off",
        "frontend_writeback_allowed": False,
        "cache_only_manual_live_full_force_off": True,
        "rollback_on_evidence_regression_required": True,
        "rollback_if_artifact_redaction_fails": True,
        "rollback_if_browser_evidence_missing": True,
        "rollback_if_research_only_boundary_missing": True,
        "linked_frontend_enablement_promotion_schema_version": frontend_enablement_promotion_contract.get(
            "schema_version"
        ),
        "linked_frontend_enablement_promotion_blocking_row_count": frontend_enablement_promotion_contract.get(
            "blocking_promotion_row_count"
        ),
        "linked_frontend_enablement_promotion_allowed": frontend_enablement_promotion_contract.get(
            "frontend_enablement_allowed"
        ),
        "requires_live_light_mode": True,
        "requires_promotion_allowed": True,
        "requires_browser_evidence_complete": True,
        "requires_artifact_redaction_review_complete": True,
        "requires_operator_opt_in": True,
        "production_promotion_required_after_switch": True,
        "frontend_wiring_implemented": False,
        "browser_evidence_complete": False,
        "acceptance_artifact_collection_complete": False,
        "artifact_redaction_review_complete": False,
        "contract_creates_task": False,
        "contract_calls_provider_or_model": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "contract_is_production_evidence": False,
        "production_live_light_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_frontend_enablement_config_promotion_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    frontend_enablement_configured: bool,
    runtime_config_ownership_invariant_contract: dict[str, Any],
    frontend_enablement_release_switch_contract: dict[str, Any],
) -> dict[str, Any]:
    config_key = FRONTEND_ENABLEMENT_CONFIG_KEY
    global_allowlist_promoted = config_key in CONFIG_NAMES
    ownership_rows = {
        str(row.get("config") or ""): row
        for row in runtime_config_ownership_invariant_contract.get("ownership_rows", [])
        if isinstance(row, dict)
    }
    frontend_enablement_ownership = ownership_rows.get(config_key, {})
    promotion_rows = [
        {
            "step_key": "add_global_config_allowlist_key",
            "step_order": 1,
            "target_file": "config.py",
            "required_change": "add COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT to the global config allowlist",
            "required_evidence": "future server config layer exposes the key without raw env leakage",
            "current_blocker": (
                "none_global_config_allowlist_key_present"
                if global_allowlist_promoted
                else "global_config_allowlist_promotion_pending"
            ),
            "status": (
                "passed_global_config_allowlist_key_present"
                if global_allowlist_promoted
                else "pending_future_global_config_scope"
            ),
            "promotion_step_complete": global_allowlist_promoted,
            "blocks_frontend_enablement": not global_allowlist_promoted,
        },
        {
            "step_key": "prove_default_false_read_path",
            "step_order": 2,
            "target_file": "tests/test_command_center_3_server.py",
            "required_change": "prove default false and effective false come from the global config layer",
            "required_evidence": "no bootstrap-local env fallback or frontend-provided value can enable it",
            "current_blocker": (
                "none_default_false_read_path_proven"
                if global_allowlist_promoted
                else "global_config_read_path_not_proven"
            ),
            "status": (
                "passed_default_false_global_config_read_path"
                if global_allowlist_promoted
                else "pending_future_global_config_scope"
            ),
            "promotion_step_complete": global_allowlist_promoted,
            "blocks_frontend_enablement": not global_allowlist_promoted,
        },
        {
            "step_key": "bind_to_promotion_contract",
            "step_order": 3,
            "target_file": "server/services/bootstrap_service.py",
            "required_change": "bind effective enablement to runtime_frontend_enablement_promotion_contract",
            "required_evidence": "frontend enablement stays false while promotion blockers remain",
            "current_blocker": "frontend_enablement_promotion_still_blocking",
        },
        {
            "step_key": "bind_to_release_switch_rollback",
            "step_order": 4,
            "target_file": "server/services/bootstrap_service.py",
            "required_change": "bind enablement to release-switch rollback conditions",
            "required_evidence": "browser evidence, artifact redaction, and research-only regression force off",
            "current_blocker": "release_switch_rollback_contract_pending",
        },
        {
            "step_key": "block_frontend_writeback",
            "step_order": 5,
            "target_file": "desktop/src/routes/CandidateRadar.tsx",
            "required_change": "keep frontend enablement state display-only",
            "required_evidence": "frontend and status endpoints cannot write config or enablement state",
            "current_blocker": "frontend_writeback_blocking_evidence_pending",
        },
        {
            "step_key": "rerun_validation_gate",
            "step_order": 6,
            "target_file": "scripts/bootstrap_runtime_contract.py",
            "required_change": "rerun focused tests, runtime gate, secret scan, and smoke before enablement",
            "required_evidence": "local gates pass without provider/model/GitHub/trading execution",
            "current_blocker": "validation_gate_not_rerun_after_global_config_promotion",
        },
    ]
    common_promotion_flags = {
        "status": "pending_frontend_enablement_validation_scope",
        "promotion_step_complete": False,
        "blocks_frontend_enablement": True,
        "config_row_is_production_evidence": False,
        "current_cycle_modifies_global_config_file": False,
        "bootstrap_local_env_fallback_allowed": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "fastapi_startup_creates_task": False,
        "search_typing_creates_task": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }
    promotion_rows = [{**common_promotion_flags, **row} for row in promotion_rows]
    completed_promotion_step_count = sum(
        1 for row in promotion_rows if row.get("promotion_step_complete") is True
    )
    return {
        "schema_version": BOOTSTRAP_FRONTEND_ENABLEMENT_CONFIG_PROMOTION_SCHEMA_VERSION,
        "status": "frontend_enablement_config_promotion_visible_global_config_promoted_default_off_validation_pending"
        if live_light_enabled and global_allowlist_promoted
        else "frontend_enablement_config_promotion_visible_pending_global_config_scope"
        if live_light_enabled
        else "frontend_enablement_config_promotion_inactive_until_live_light_mode",
        "mode": active_mode,
        "config_key": config_key,
        "target_stage_key": "stage_04_frontend_nonblocking_wiring",
        "target_frontend_route": "desktop/src/routes/CandidateRadar.tsx",
        "promotion_rows": promotion_rows,
        "promotion_step_count": len(promotion_rows),
        "completed_promotion_step_count": completed_promotion_step_count,
        "pending_promotion_step_count": len(promotion_rows) - completed_promotion_step_count,
        "required_promotion_step_keys": [row["step_key"] for row in promotion_rows],
        "default_value_safe": False,
        "configured_value_safe": frontend_enablement_configured,
        "effective_value_safe": False,
        "bootstrap_local_env_fallback_allowed": False,
        "bootstrap_local_env_fallback_count": 0,
        "global_config_allowlist_promoted": global_allowlist_promoted,
        "global_config_allowlist_promotion_pending": not global_allowlist_promoted,
        "current_cycle_modifies_global_config_file": False,
        "requires_future_config_py_file_scope": not global_allowlist_promoted,
        "config_py_update_pending": not global_allowlist_promoted,
        "effective_frontend_enablement_allowed": False,
        "release_switch_default_enabled": False,
        "frontend_enablement_allowed": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "linked_runtime_config_ownership_schema_version": (
            runtime_config_ownership_invariant_contract.get("schema_version")
        ),
        "linked_runtime_config_ownership_row_count": runtime_config_ownership_invariant_contract.get(
            "ownership_row_count"
        ),
        "linked_frontend_enablement_ownership_status": frontend_enablement_ownership.get("ownership_status"),
        "linked_frontend_enablement_current_read_path": frontend_enablement_ownership.get("current_read_path"),
        "linked_frontend_enablement_target_read_path": frontend_enablement_ownership.get("target_read_path"),
        "linked_frontend_enablement_global_config_allowlist_promotion_pending": frontend_enablement_ownership.get(
            "global_config_allowlist_promotion_pending"
        ),
        "linked_frontend_enablement_bootstrap_local_env_fallback_available": frontend_enablement_ownership.get(
            "bootstrap_local_env_fallback_available"
        ),
        "linked_release_switch_schema_version": frontend_enablement_release_switch_contract.get("schema_version"),
        "linked_release_switch_row_count": frontend_enablement_release_switch_contract.get(
            "release_switch_row_count"
        ),
        "linked_release_switch_blocking_row_count": frontend_enablement_release_switch_contract.get(
            "blocking_release_switch_row_count"
        ),
        "linked_release_switch_effective_allowed": frontend_enablement_release_switch_contract.get(
            "effective_frontend_enablement_allowed"
        ),
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "fastapi_startup_creates_task": False,
        "search_typing_creates_task": False,
        "contract_creates_task": False,
        "contract_calls_provider_or_model": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
        "contract_is_production_evidence": False,
        "production_config_complete": False,
        "production_live_light_complete": False,
    }


def _live_light_local_fallback_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_LOCAL_FALLBACK_CONTRACT_SCHEMA_VERSION,
        "status": "local_fallback_contract_visible_runtime_evidence_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "fallback_surface": "post_task_worker_or_local_pipeline_only",
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "cache_first_render_required": True,
        "fallback_after_provider_error_allowed": True,
        "fallback_after_model_error_allowed": True,
        "fallback_from_get_cache_allowed": False,
        "fallback_from_react_render_allowed": False,
        "fastapi_startup_fallback_refresh_allowed": False,
        "uses_last_good_cache_allowed": True,
        "last_good_cache_lineage_required": True,
        "stale_cache_label_required": True,
        "provider_gap_visible_required": True,
        "safe_error_visible_required": True,
        "rate_limit_skipped_state_visible_required": True,
        "fallback_may_refresh_local_factor_from_existing_cache": True,
        "fallback_may_refresh_next_session_from_existing_cache": True,
        "fallback_may_synthesize_provider_rows": False,
        "fallback_may_synthesize_model_output": False,
        "fallback_is_provider_evidence": False,
        "fallback_is_model_correctness_evidence": False,
        "fallback_is_production_evidence": False,
        "fallback_may_overwrite_price": False,
        "fallback_may_overwrite_holding": False,
        "fallback_may_overwrite_factor": False,
        "fallback_may_overwrite_operation_zones": False,
        "fallback_may_modify_strategy_action": False,
        "fallback_may_create_radar_buy_instruction": False,
        "browser_runtime_evidence_complete": False,
        "performance_trace_evidence_complete": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_cache_lineage_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_CACHE_LINEAGE_CONTRACT_SCHEMA_VERSION,
        "status": "cache_lineage_contract_visible_runtime_evidence_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "required_lineage_fields": [
            "source_task_id",
            "source_task_type",
            "source_route",
            "source_mode",
            "source_scope_hash",
            "provider_call_ledger_ids",
            "model_ledger_ids",
            "input_packet_keys",
            "output_packet_keys",
            "cache_source",
            "storage_backend",
            "local_fetched_at",
            "freshness_state",
            "data_date",
        ],
        "lineage_required_for_factor_quant_hub_cache": True,
        "lineage_required_for_next_session_cache": True,
        "lineage_required_for_deepseek_explanation_cache": True,
        "sqlite_meta_visibility_required": True,
        "snapshot_visibility_allowed_as_fallback": True,
        "memory_only_lineage_is_durable_evidence": False,
        "cache_get_may_write_lineage": False,
        "react_render_may_write_lineage": False,
        "fastapi_startup_may_write_lineage": False,
        "lineage_written_by_post_task_only": True,
        "lineage_must_reference_call_ledger": True,
        "lineage_must_reference_model_ledger_for_deepseek": True,
        "lineage_must_include_safe_error_when_degraded": True,
        "lineage_must_include_provider_gap_when_degraded": True,
        "lineage_must_exclude_credential_values": True,
        "lineage_must_exclude_env_key_names": True,
        "lineage_must_exclude_raw_prompt_or_output": True,
        "lineage_may_overwrite_price": False,
        "lineage_may_overwrite_holding": False,
        "lineage_may_overwrite_factor": False,
        "lineage_may_overwrite_operation_zones": False,
        "lineage_may_modify_strategy_action": False,
        "lineage_is_provider_execution_evidence": False,
        "lineage_is_model_correctness_evidence": False,
        "lineage_is_production_evidence_without_real_ledgers": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_output_surface_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    output_surface_rows = [
        {
            "surface_key": "factor_quant_hub_cache",
            "packet_key": "command_center_factor_quant_hub_packet",
            "nested_path": "",
            "source_stage": "factor_quant_hub_cache_refresh",
            "source_task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "allowed_writer": "post_task_worker_or_local_pipeline_only",
            "lineage_required": True,
            "call_ledger_required": True,
            "model_ledger_required": False,
            "freshness_state_required": True,
            "provider_gap_visible_required": True,
            "safe_error_visible_required": True,
            "cache_get_may_write": False,
            "react_render_may_write": False,
            "fastapi_startup_may_write": False,
            "fallback_may_refresh_from_existing_cache": True,
            "fallback_may_synthesize_provider_rows": False,
            "may_overwrite_price": False,
            "may_overwrite_holding": False,
            "may_overwrite_factor": False,
            "may_overwrite_operation_zones": False,
            "may_modify_strategy_action": False,
            "production_output_ready": False,
        },
        {
            "surface_key": "next_session_cache",
            "packet_key": "command_center_next_session_projection_packet",
            "nested_path": "",
            "source_stage": "next_session_cache_refresh",
            "source_task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "allowed_writer": "post_task_worker_or_local_pipeline_only",
            "lineage_required": True,
            "call_ledger_required": True,
            "model_ledger_required": False,
            "freshness_state_required": True,
            "provider_gap_visible_required": True,
            "safe_error_visible_required": True,
            "cache_get_may_write": False,
            "react_render_may_write": False,
            "fastapi_startup_may_write": False,
            "fallback_may_refresh_from_existing_cache": True,
            "fallback_may_synthesize_provider_rows": False,
            "may_overwrite_price": False,
            "may_overwrite_holding": False,
            "may_overwrite_factor": False,
            "may_overwrite_operation_zones": False,
            "may_modify_strategy_action": False,
            "production_output_ready": False,
        },
        {
            "surface_key": "deepseek_explanation_cache",
            "packet_key": "command_center_factor_quant_hub_packet",
            "nested_path": "data.deepseek_explanation",
            "source_stage": "deepseek_pro_explanation",
            "source_task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "allowed_writer": "post_task_worker_or_local_pipeline_only",
            "lineage_required": True,
            "call_ledger_required": True,
            "model_ledger_required": True,
            "freshness_state_required": True,
            "provider_gap_visible_required": True,
            "safe_error_visible_required": True,
            "allowed_output_fields": list(DEEPSEEK_EXPLANATION_FIELDS),
            "allowed_output_fields_only": True,
            "cache_get_may_write": False,
            "react_render_may_write": False,
            "fastapi_startup_may_write": False,
            "fallback_may_refresh_from_existing_cache": False,
            "fallback_may_synthesize_model_output": False,
            "deepseek_is_data_source": False,
            "may_overwrite_price": False,
            "may_overwrite_holding": False,
            "may_overwrite_factor": False,
            "may_overwrite_operation_zones": False,
            "may_modify_strategy_action": False,
            "production_output_ready": False,
        },
    ]
    return {
        "schema_version": BOOTSTRAP_OUTPUT_SURFACE_CONTRACT_SCHEMA_VERSION,
        "status": "output_surface_contract_visible_runtime_evidence_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "task_status_route": "GET /api/tasks/{task_id}",
        "required_output_surfaces": [
            "factor_quant_hub_cache",
            "next_session_cache",
            "deepseek_explanation_cache",
        ],
        "output_packet_keys": [
            "command_center_factor_quant_hub_packet",
            "command_center_next_session_projection_packet",
            "command_center_factor_quant_hub_packet:data.deepseek_explanation",
        ],
        "output_surface_count": len(output_surface_rows),
        "output_surface_rows": output_surface_rows,
        "output_written_by_post_task_only": True,
        "cache_get_may_write_output": False,
        "react_render_may_write_output": False,
        "fastapi_startup_may_write_output": False,
        "all_outputs_require_lineage": True,
        "all_outputs_require_safe_error_or_provider_gap_when_degraded": True,
        "factor_quant_hub_cache_required": True,
        "next_session_cache_required": True,
        "deepseek_explanation_optional_after_data_ready": True,
        "deepseek_output_fields_whitelisted": True,
        "deepseek_is_data_source": False,
        "fallback_may_synthesize_provider_rows": False,
        "fallback_may_synthesize_model_output": False,
        "may_overwrite_price": False,
        "may_overwrite_holding": False,
        "may_overwrite_factor": False,
        "may_overwrite_operation_zones": False,
        "may_modify_strategy_action": False,
        "radar_candidate_is_buy_instruction": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "output_surface_contract_is_execution_evidence": False,
        "output_surface_contract_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_runtime_budget_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
    symbol_limit: int,
    rate_limit_seconds: int,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_RUNTIME_BUDGET_CONTRACT_SCHEMA_VERSION,
        "status": "runtime_budget_contract_visible_execution_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
        "acceptance_dry_run_route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
        "execution_request_route": PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE,
        "allowed_scope": "current_target_holdings_watchlist_searched_symbol_light_only",
        "symbol_limit": symbol_limit,
        "rate_limit_seconds": rate_limit_seconds,
        "allowed_live_light_tushare_apis": list(DEFAULT_LIGHT_TUSHARE_APIS),
        "allowed_acceptance_apis": list(ACCEPTANCE_DRY_RUN_ALLOWED_APIS),
        "allowed_deepseek_purposes": ["explain_after_data_ready"],
        "provider_budget_surface": "post_task_worker_only",
        "model_budget_surface": "post_data_ready_model_step_only",
        "max_provider_api_count_per_task": len(DEFAULT_LIGHT_TUSHARE_APIS),
        "max_model_call_count_per_task": 1,
        "max_background_task_count_per_rate_window": 1,
        "cache_hit_skips_provider_call_allowed": True,
        "input_hash_dedupe_required": True,
        "scope_hash_dedupe_required": True,
        "model_input_hash_dedupe_required": True,
        "rate_limit_skip_must_reuse_existing_task": True,
        "budget_exceeded_status": "skipped_budget_exceeded_no_external_call",
        "rate_limited_status": "skipped_due_to_rate_limit_reused_existing_task",
        "credential_missing_status": "blocked_missing_credentials_no_external_call",
        "permission_denied_status": "provider_permission_denied_safe_error",
        "empty_result_status": "provider_empty_result_not_verified",
        "no_record_status": "provider_no_record_not_negative_evidence",
        "required_budget_ledger_fields": [
            "scope_hash",
            "input_hash",
            "cache_hit",
            "provider_api_count",
            "model_call_count",
            "token_usage",
            "model_cost_estimate",
            "budget_status",
            "rate_limit_status",
            "safe_error",
        ],
        "token_usage_record_required": True,
        "model_cost_estimate_record_required": True,
        "budget_status_record_required": True,
        "budget_status_values": ["within_budget", "skipped_budget_exceeded", "unknown_until_runtime"],
        "budget_state_visible_required": True,
        "token_usage_visible_safe_summary_only": True,
        "raw_prompt_or_output_budget_log_allowed": False,
        "credential_value_budget_log_allowed": False,
        "env_key_name_budget_log_allowed": False,
        "deepseek_is_data_source": False,
        "deepseek_may_overwrite_price": False,
        "deepseek_may_overwrite_holding": False,
        "deepseek_may_overwrite_factor": False,
        "deepseek_may_overwrite_operation_zones": False,
        "deepseek_may_modify_strategy_action": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "budget_enforcement_implemented": False,
        "budget_contract_is_execution_evidence": False,
        "budget_contract_is_production_evidence": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_evidence_grade_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_EVIDENCE_GRADE_SCHEMA_VERSION,
        "status": "local_evidence_visible_production_evidence_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "local_evidence_grade": "contract_receipt_plan_only",
        "production_evidence_grade": "pending_real_provider_model_runtime_promotion",
        "local_task_skeleton_is_production_evidence": False,
        "activation_receipt_is_production_evidence": False,
        "acceptance_runbook_is_production_evidence": False,
        "provider_linkage_matrix_is_provider_evidence": False,
        "model_ledger_preview_is_model_execution_evidence": False,
        "sanitizer_is_model_correctness_evidence": False,
        "mock_receipt_matrix_sanitizer_can_promote": False,
        "provider_execution_evidence_done": False,
        "model_execution_evidence_done": False,
        "browser_runtime_evidence_done": False,
        "ledger_redaction_review_done": False,
        "production_promotion_review_done": False,
        "production_live_light_complete": False,
        "required_production_evidence": [
            "real Tushare call ledger with safe request params and result status",
            "real DeepSeek model ledger with redacted token usage and prompt/output hashes",
            "provider/model output persistence or cache lineage evidence",
            "browser runtime evidence for cache-first render and nonblocking polling",
            "ledger redaction review",
            "explicit production promotion review",
        ],
        "allowed_next_step": "collect_user_approved_provider_model_runtime_evidence",
        "not_allowed_next_steps": [
            "promote local task skeleton as production evidence",
            "promote activation receipt as provider evidence",
            "promote acceptance runbook as acceptance evidence",
            "promote sanitizer or model-ledger preview as model correctness evidence",
            "mark live_light production complete without real ledgers and promotion review",
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_credential_preflight_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_CREDENTIAL_PREFLIGHT_SCHEMA_VERSION,
        "status": "credential_preflight_contract_visible_post_only"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "status_get_reads_credential_values": False,
        "status_get_checks_credential_presence": False,
        "status_get_exposes_env_key_names": False,
        "status_get_exposes_credential_values": False,
        "credential_presence_check_route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
        "credential_presence_check_requires_post": True,
        "credential_presence_check_requires_user_approval": True,
        "credential_presence_check_method": "environment_key_membership_only",
        "credential_presence_check_reads_values": False,
        "credential_presence_check_exposes_values": False,
        "credential_presence_check_exposes_env_key_names": False,
        "credential_presence_check_exposes_value_lengths": False,
        "safe_provider_labels_only": True,
        "allowed_provider_labels": ["tushare", "deepseek"],
        "frontend_packet_may_contain_token_key": False,
        "logs_may_contain_token_key": False,
        "cache_may_contain_token_key": False,
        "raw_config_dump_allowed": False,
        "provider_execution_allowed_from_preflight": False,
        "model_execution_allowed_from_preflight": False,
        "production_promotion_allowed_from_preflight": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_provider_model_execution_request_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_EXECUTION_REQUEST_CONTRACT_SCHEMA_VERSION,
        "status": "execution_request_contract_visible_provider_model_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "acceptance_dry_run_route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
        "execution_request_route": PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE,
        "target_provider_model_route": FUTURE_BOOTSTRAP_PROVIDER_MODEL_ACCEPTANCE_ROUTE,
        "target_provider_model_task_type": "command_center_live_bootstrap_provider_model_acceptance",
        "dry_run_is_execution_request": False,
        "dry_run_may_call_provider_or_model": False,
        "execution_request_is_provider_execution": False,
        "execution_request_creates_provider_model_task": False,
        "cache_get_initializes_execution_request": False,
        "react_render_initializes_execution_request": False,
        "page_open_initializes_execution_request": False,
        "search_typing_initializes_execution_request": False,
        "requires_latest_acceptance_scope_hash": True,
        "requires_scope_hash_match": True,
        "requires_explicit_user_confirmation": True,
        "requires_credential_preflight_ready": True,
        "requires_selected_provider_or_model_scope": True,
        "requires_call_ledger": True,
        "requires_model_ledger_for_deepseek": True,
        "requires_ledger_redaction_review_before_promotion": True,
        "provider_model_execution_implemented": False,
        "execution_request_route_implemented": BOOTSTRAP_EXECUTION_REQUEST_ROUTE_IMPLEMENTED,
        "local_execution_request_receipt_service_implemented": True,
        "local_execution_request_receipt_task_type": BOOTSTRAP_EXECUTION_REQUEST_TASK_TYPE,
        "local_execution_request_receipt_packet_key": BOOTSTRAP_EXECUTION_REQUEST_PACKET_KEY,
        "local_execution_request_receipt_persists_to_task_status": True,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "automatic_provider_model_execution_allowed": False,
        "production_promotion_allowed_from_execution_request": False,
        "allowed_next_step": "verify_button_gated_execution_request_route_before_provider_model_task",
        "not_allowed_next_steps": [
            "treat acceptance dry-run as execution request",
            "create provider/model task from GET status or React render",
            "execute provider/model without latest scope hash match",
            "execute provider/model without explicit user confirmation",
            "treat execution request as provider/model acceptance evidence",
            "promote live_light production from execution request",
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_execution_request_handoff_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    handoff_rows = [
        {
            "handoff_key": "dry_run_receipt_lookup",
            "source": "task_service_status_or_sqlite_meta",
            "required_before_execution_request": True,
            "required_fields": [
                "latest_acceptance_dry_run_task_id",
                "acceptance_scope_hash",
                "acceptance_scope_hash_short",
                "scope_hash_algorithm",
            ],
            "current_status": "route_registered_durable_lookup_required",
            "local_only": True,
        },
        {
            "handoff_key": "scope_hash_binding",
            "source": "latest_acceptance_scope_hash",
            "required_before_execution_request": True,
            "scope_hash_mismatch_blocks_handoff": True,
            "current_status": "contract_only_no_provider_model_execution",
            "local_only": True,
        },
        {
            "handoff_key": "operator_confirmation",
            "source": "button_gated_execution_request_payload",
            "required_before_execution_request": True,
            "requires_explicit_user_confirmation": True,
            "manual_only": True,
            "current_status": "route_registered_user_confirmation_required",
        },
        {
            "handoff_key": "credential_preflight_summary",
            "source": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
            "required_before_execution_request": True,
            "booleans_only": True,
            "safe_provider_labels_only": True,
            "credential_values_exposed": False,
            "credential_env_key_names_exposed": False,
            "current_status": "safe_summary_required",
        },
        {
            "handoff_key": "provider_model_task_handoff",
            "source": PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE,
            "target_route": FUTURE_BOOTSTRAP_PROVIDER_MODEL_ACCEPTANCE_ROUTE,
            "required_before_provider_model_task": True,
            "creates_provider_model_task_now": False,
            "requires_call_ledger": True,
            "requires_model_ledger_for_deepseek": True,
            "current_status": "target_provider_model_execution_pending",
        },
    ]
    return {
        "schema_version": BOOTSTRAP_EXECUTION_REQUEST_HANDOFF_CONTRACT_SCHEMA_VERSION,
        "status": "execution_request_handoff_contract_visible_route_registered"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "acceptance_dry_run_route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
        "execution_request_route": PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE,
        "target_provider_model_route": FUTURE_BOOTSTRAP_PROVIDER_MODEL_ACCEPTANCE_ROUTE,
        "handoff_rows": handoff_rows,
        "handoff_row_count": len(handoff_rows),
        "required_handoff_fields": [
            "latest_acceptance_dry_run_task_id",
            "acceptance_scope_hash",
            "acceptance_scope_hash_short",
            "scope_hash_algorithm",
            "user_confirmed",
            "selected_providers",
            "selected_model_scope",
            "credential_preflight_ready",
            "credential_presence_status",
            "call_ledger_required",
            "model_ledger_required_for_deepseek",
            "redaction_review_required",
            "safe_payload_only",
        ],
        "dry_run_receipt_required": True,
        "latest_dry_run_task_id_required": True,
        "acceptance_scope_hash_required": True,
        "scope_hash_algorithm_required": True,
        "scope_hash_mismatch_blocks_handoff": True,
        "explicit_user_confirmation_required": True,
        "selected_provider_or_model_scope_required": True,
        "credential_preflight_ready_required": True,
        "credential_presence_booleans_only": True,
        "safe_payload_only": True,
        "durable_receipt_visibility_required": True,
        "memory_only_dry_run_receipt_is_durable_evidence": False,
        "dry_run_is_execution_request": False,
        "execution_request_route_implemented": BOOTSTRAP_EXECUTION_REQUEST_ROUTE_IMPLEMENTED,
        "route_adapter_contract_visible": True,
        "route_adapter_target_file": "server/api/routes_bootstrap.py",
        "route_adapter_function_name": "post_bootstrap_provider_model_execution_request",
        "route_adapter_service_function": "run_provider_model_execution_request",
        "route_adapter_response_envelope": "task_envelope",
        "route_adapter_payload_type": "dict[str, Any] | None",
        "route_adapter_current_status": BOOTSTRAP_EXECUTION_REQUEST_ROUTE_ADAPTER_STATUS,
        "route_adapter_must_be_button_gated": True,
        "route_adapter_accepts_safe_payload_only": True,
        "route_adapter_must_return_task_envelope": True,
        "route_adapter_creates_provider_model_task": False,
        "route_adapter_calls_provider_or_model": False,
        "route_adapter_external_calls_triggered": False,
        "route_adapter_allowed_next_step": "verify_button_gated_route_adapter_then_keep_provider_model_pending",
        "route_adapter_not_allowed_next_steps": [
            "call provider/model from route adapter",
            "create provider/model task from route adapter",
            "read or return credential values",
            "treat route adapter success as provider/model acceptance",
            "promote live_light production from route adapter receipt",
        ],
        "local_execution_request_receipt_service_implemented": True,
        "local_execution_request_receipt_task_type": BOOTSTRAP_EXECUTION_REQUEST_TASK_TYPE,
        "local_execution_request_receipt_packet_key": BOOTSTRAP_EXECUTION_REQUEST_PACKET_KEY,
        "local_execution_request_receipt_persists_to_task_status": True,
        "execution_request_creates_provider_model_task": False,
        "execution_request_receipt_persisted": False,
        "provider_model_task_created": False,
        "status_get_initializes_handoff": False,
        "cache_get_initializes_handoff": False,
        "react_render_initializes_handoff": False,
        "page_open_initializes_handoff": False,
        "search_typing_initializes_handoff": False,
        "fastapi_startup_initializes_handoff": False,
        "call_ledger_required": True,
        "model_ledger_required_for_deepseek": True,
        "redaction_review_required_before_promotion": True,
        "credential_values_exposed": False,
        "credential_env_key_names_exposed": False,
        "local_handoff_contract_is_provider_execution_evidence": False,
        "local_handoff_contract_is_model_execution_evidence": False,
        "local_handoff_contract_is_production_evidence": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "provider_model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _live_light_ledger_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_LEDGER_CONTRACT_SCHEMA_VERSION,
        "status": "ledger_contract_visible_runtime_execution_pending"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "call_ledger_required_for_provider": True,
        "model_ledger_required_for_deepseek": True,
        "required_call_ledger_fields": [
            "api",
            "endpoint",
            "call_status",
            "request_params_safe",
            "external",
            "external_calls_triggered",
            "tushare_called",
            "deepseek_called",
            "github_called",
            "does_not_execute_trades",
            "does_not_modify_strategy_action",
        ],
        "required_model_ledger_fields": [
            "model_used",
            "purpose",
            "status",
            "token_usage",
            "input_hash",
            "output_hash",
            "parse_status",
            "cache_hit",
            "sanitizer_status",
        ],
        "request_params_must_be_safe": True,
        "credential_values_exposed": False,
        "credential_env_key_names_exposed_to_frontend": False,
        "frontend_packet_may_contain_token_key": False,
        "logs_may_contain_token_key": False,
        "cache_may_contain_token_key": False,
        "raw_prompt_or_raw_model_output_exposed": False,
        "prompt_output_hashes_required": True,
        "token_usage_required": True,
        "parse_status_required": True,
        "cache_hit_or_miss_required": True,
        "sanitizer_status_required": True,
        "redaction_review_required_before_promotion": True,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_promotion_allowed_without_ledger": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_light_ledger_redaction_invariant_contract(
    *,
    active_mode: str,
    live_light_enabled: bool,
) -> dict[str, Any]:
    prohibited_fields = [
        "credential_value",
        "credential_env_key_name",
        "credential_material_label",
        "secret_material_label",
        "authorization_header",
        "raw_prompt",
        "raw_model_output",
        "raw_provider_response",
    ]
    allowed_safe_summary_fields = [
        "provider_label",
        "model_name",
        "purpose",
        "call_status",
        "token_usage",
        "input_hash",
        "output_hash",
        "parse_status",
        "sanitizer_status",
        "cache_hit",
        "safe_error",
    ]
    prohibited_surface_rows = [
        {
            "surface_key": "frontend_packet",
            "surface": "GET /api/bootstrap/status packet and React props",
            "safe_summary_only": True,
        },
        {
            "surface_key": "log_line",
            "surface": "application logs and task diagnostics",
            "safe_summary_only": True,
        },
        {
            "surface_key": "cache_payload",
            "surface": "local cache and persisted packet payload",
            "safe_summary_only": True,
        },
        {
            "surface_key": "task_status_payload",
            "surface": "GET /api/tasks/{task_id} status payload",
            "safe_summary_only": True,
        },
        {
            "surface_key": "call_ledger_request_params_safe",
            "surface": "call_ledger request_params_safe",
            "safe_summary_only": True,
        },
        {
            "surface_key": "model_ledger_safe_summary",
            "surface": "model_ledger visible summary",
            "safe_summary_only": True,
        },
    ]
    for row in prohibited_surface_rows:
        row.update(
            {
                "credential_value_allowed": False,
                "credential_env_key_name_allowed": False,
                "token_key_allowed": False,
                "authorization_header_allowed": False,
                "raw_prompt_allowed": False,
                "raw_model_output_allowed": False,
                "raw_provider_response_allowed": False,
                "redacted_safe_summary_required": True,
            }
        )

    required_ledger_rows = [
        {
            "ledger_key": "tushare_call_ledger",
            "required_for": "provider_execution",
            "required_before_promotion": True,
            "production_promotion_blocker_until_complete": True,
        },
        {
            "ledger_key": "deepseek_model_ledger",
            "required_for": "model_execution",
            "required_before_promotion": True,
            "production_promotion_blocker_until_complete": True,
        },
        {
            "ledger_key": "redaction_review",
            "required_for": "secret_and_raw_payload_review",
            "required_before_promotion": True,
            "production_promotion_blocker_until_complete": True,
        },
        {
            "ledger_key": "prompt_output_hashes",
            "required_for": "model_lineage_without_raw_prompt_or_output",
            "required_before_promotion": True,
            "production_promotion_blocker_until_complete": True,
        },
        {
            "ledger_key": "no_action_mutation_flags",
            "required_for": "deepseek_explanation_does_not_modify_actions_or_numeric_sources",
            "required_before_promotion": True,
            "production_promotion_blocker_until_complete": True,
        },
    ]
    for row in required_ledger_rows:
        row.update(
            {
                "status": "pending_real_provider_model_acceptance",
                "contract_row_is_production_evidence": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    return {
        "schema_version": BOOTSTRAP_LEDGER_REDACTION_INVARIANT_SCHEMA_VERSION,
        "status": "ledger_redaction_invariant_visible_promotion_blocking"
        if live_light_enabled
        else "inactive_until_live_light_mode",
        "mode": active_mode,
        "prohibited_fields": prohibited_fields,
        "allowed_safe_summary_fields": allowed_safe_summary_fields,
        "prohibited_surface_rows": prohibited_surface_rows,
        "required_ledger_rows": required_ledger_rows,
        "prohibited_surface_count": len(prohibited_surface_rows),
        "required_ledger_row_count": len(required_ledger_rows),
        "frontend_packet_may_contain_token_key": False,
        "logs_may_contain_token_key": False,
        "cache_may_contain_token_key": False,
        "task_status_may_contain_token_key": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "raw_prompt_or_raw_model_output_exposed": False,
        "raw_provider_response_exposed": False,
        "request_params_must_be_safe": True,
        "safe_summary_only": True,
        "call_ledger_required_for_provider": True,
        "model_ledger_required_for_deepseek": True,
        "redaction_review_required_before_promotion": True,
        "provider_model_execution_requires_execution_request": True,
        "deepseek_is_data_source": False,
        "deepseek_may_overwrite_prices_positions_factors_zones_or_actions": False,
        "production_promotion_allowed_without_redaction_review": False,
        "ledger_redaction_invariant_is_production_evidence": False,
        "production_live_light_complete": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _live_full_reserved_contract(
    *,
    active_mode: str,
    allow_full_pool: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "command_center_live_full_reserved_contract.v1",
        "status": "live_full_reserved_disabled"
        if active_mode == "live_full"
        else "inactive_until_live_full_mode",
        "mode": active_mode,
        "reserved_mode": True,
        "active_mode_requested": active_mode == "live_full",
        "configured_allow_full_pool": allow_full_pool,
        "effective_allow_full_pool": False,
        "future_worker_mode_only": True,
        "separate_authorization_required": True,
        "page_open_task_allowed": False,
        "react_mounted_auto_task_allowed": False,
        "search_input_auto_task_allowed": False,
        "cache_get_creates_task": False,
        "live_light_bootstrap_task_allowed": False,
        "full_pool_on_open_allowed": False,
        "deep_scan_on_open_allowed": False,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "worker_execution_implemented": False,
        "production_live_full_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
        "contains_secret": False,
    }


def _bootstrap_runtime_config_reference_contract(
    *,
    active_mode: str,
    config_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    rows_by_config = {str(row.get("config") or ""): row for row in config_rows}
    startup_autostart_row = rows_by_config.get(STARTUP_AUTOSTART_CONFIG_KEY, {})
    external_execution_profile_row = rows_by_config.get(EXTERNAL_EXECUTION_PROFILE_CONFIG_KEY, {})
    live_light_research_scope_row = rows_by_config.get(LIVE_LIGHT_RESEARCH_SCOPE_CONFIG_KEY, {})
    frontend_enablement_row = rows_by_config.get(FRONTEND_ENABLEMENT_CONFIG_KEY, {})
    provider_model_enablement_row = rows_by_config.get(PROVIDER_MODEL_ENABLEMENT_CONFIG_KEY, {})
    frontend_enablement_allowlist_promoted = FRONTEND_ENABLEMENT_CONFIG_KEY in CONFIG_NAMES
    provider_model_enablement_allowlist_promoted = PROVIDER_MODEL_ENABLEMENT_CONFIG_KEY in CONFIG_NAMES
    live_light_research_scope_allowlist_promoted = LIVE_LIGHT_RESEARCH_SCOPE_CONFIG_KEY in CONFIG_NAMES
    reference_rows = [
        {
            "config": "COMMAND_CENTER_BOOTSTRAP_MODE",
            "category": "runtime_mode",
            "purpose": "select_cache_only_manual_live_light_or_reserved_live_full",
            "default_value_safe": DEFAULT_MODE,
            "effective_value_safe": active_mode,
            "allowed_values": list(BOOTSTRAP_MODES),
            "mode_gate": "none",
            "automation_surface": "mode_boundary_only",
            "cache_only_behavior": "read_cache_only_no_external_calls",
            "manual_behavior": "explicit_post_task_only",
            "live_light_behavior": "bounded_background_task_after_cache_render_or_safe_submit",
            "live_full_behavior": "reserved_disabled_requires_future_authorization",
        },
        {
            "config": "COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN",
            "category": "source_switch",
            "purpose": "allow_live_light_bootstrap_to_plan_tushare_light_refresh",
            "default_value_safe": False,
            "configured_value_safe": rows_by_config["COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN"].get("configured_value_safe"),
            "effective_value_safe": rows_by_config["COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN"].get("effective_value_safe"),
            "mode_gate": "live_light",
            "automation_surface": "post_bootstrap_task_only",
            "creates_provider_model_task": False,
            "provider_execution_requires_execution_request": True,
        },
        {
            "config": "COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN",
            "category": "source_switch",
            "purpose": "allow_live_light_bootstrap_to_plan_deepseek_after_data_ready",
            "default_value_safe": False,
            "configured_value_safe": rows_by_config["COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN"].get("configured_value_safe"),
            "effective_value_safe": rows_by_config["COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN"].get("effective_value_safe"),
            "mode_gate": "live_light",
            "automation_surface": "post_bootstrap_task_after_data_ready_only",
            "creates_provider_model_task": False,
            "model_execution_requires_execution_request": True,
            "deepseek_is_data_source": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART",
            "category": "source_switch",
            "purpose": "allow_live_light_safe_search_submit_to_create_or_reuse_local_projection_task",
            "default_value_safe": False,
            "configured_value_safe": rows_by_config["COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"].get(
                "configured_value_safe"
            ),
            "effective_value_safe": rows_by_config["COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"].get(
                "effective_value_safe"
            ),
            "mode_gate": "live_light",
            "automation_surface": "safe_search_submit_local_projection_task_only",
            "creates_provider_model_task": False,
            "provider_model_execution_requires_execution_request": True,
            "global_config_allowlist_promoted": True,
            "global_config_allowlist_promotion_pending": False,
            "bootstrap_local_env_fallback_removed": True,
            "bootstrap_local_env_fallback_removal_pending": False,
        },
        {
            "config": STARTUP_AUTOSTART_CONFIG_KEY,
            "category": "startup_autostart_switch",
            "purpose": "allow_live_light_after_cache_render_to_create_or_reuse_local_bootstrap_task",
            "default_value_safe": False,
            "configured_value_safe": startup_autostart_row.get("configured_value_safe", False),
            "effective_value_safe": startup_autostart_row.get("effective_value_safe", False),
            "source": startup_autostart_row.get("source", "default"),
            "mode_gate": "live_light_after_cache_render_and_sources_enabled",
            "automation_surface": "react_after_cache_render_local_bootstrap_task_only",
            "creates_local_background_task_only": startup_autostart_row.get(
                "creates_local_background_task_only",
                False,
            ),
            "creates_provider_model_task": False,
            "provider_model_execution_requires_execution_request": True,
            "global_config_allowlist_promoted": STARTUP_AUTOSTART_CONFIG_KEY in CONFIG_NAMES,
            "global_config_allowlist_promotion_pending": STARTUP_AUTOSTART_CONFIG_KEY not in CONFIG_NAMES,
        },
        {
            "config": EXTERNAL_EXECUTION_PROFILE_CONFIG_KEY,
            "category": "external_execution_profile",
            "purpose": "select_future_live_light_light_provider_model_execution_profile_without_running_executor",
            "default_value_safe": DEFAULT_EXTERNAL_EXECUTION_PROFILE,
            "configured_value_safe": external_execution_profile_row.get(
                "configured_value_safe",
                DEFAULT_EXTERNAL_EXECUTION_PROFILE,
            ),
            "effective_value_safe": external_execution_profile_row.get(
                "effective_value_safe",
                DEFAULT_EXTERNAL_EXECUTION_PROFILE,
            ),
            "source": external_execution_profile_row.get("source", "default"),
            "allowed_values": list(EXTERNAL_EXECUTION_PROFILES),
            "mode_gate": "live_light_post_task_worker_ledger",
            "automation_surface": "post_bootstrap_or_search_task_worker_only",
            "provider_stage_allowed_by_profile": external_execution_profile_row.get(
                "provider_stage_allowed_by_profile",
                False,
            ),
            "model_stage_allowed_by_profile": external_execution_profile_row.get(
                "model_stage_allowed_by_profile",
                False,
            ),
            "creates_provider_model_task": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "calls_provider_model_now": False,
            "requires_post_task_worker_or_local_fallback": True,
            "requires_call_ledger": True,
            "requires_model_ledger_for_deepseek": external_execution_profile_row.get(
                "requires_model_ledger_for_deepseek",
                False,
            ),
            "global_config_allowlist_promoted": EXTERNAL_EXECUTION_PROFILE_CONFIG_KEY in CONFIG_NAMES,
            "global_config_allowlist_promotion_pending": EXTERNAL_EXECUTION_PROFILE_CONFIG_KEY not in CONFIG_NAMES,
        },
        {
            "config": LIVE_LIGHT_RESEARCH_SCOPE_CONFIG_KEY,
            "category": "live_light_research_scope",
            "purpose": "select_future_live_light_stage_bundle_without_running_provider_model_or_local_compute",
            "default_value_safe": DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE,
            "configured_value_safe": live_light_research_scope_row.get(
                "configured_value_safe",
                DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE,
            ),
            "effective_value_safe": live_light_research_scope_row.get(
                "effective_value_safe",
                "bootstrap_only",
            ),
            "source": live_light_research_scope_row.get("source", "default"),
            "allowed_values": list(LIVE_LIGHT_RESEARCH_SCOPES),
            "mode_gate": "live_light_research_scope_after_cache_render",
            "automation_surface": "stage_bundle_only_no_execution",
            "provider_stage_allowed_by_scope": live_light_research_scope_row.get(
                "provider_stage_allowed_by_scope",
                False,
            ),
            "factor_light_allowed_by_scope": live_light_research_scope_row.get(
                "factor_light_allowed_by_scope",
                False,
            ),
            "next_session_cache_allowed_by_scope": live_light_research_scope_row.get(
                "next_session_cache_allowed_by_scope",
                False,
            ),
            "model_stage_allowed_by_scope": live_light_research_scope_row.get(
                "model_stage_allowed_by_scope",
                False,
            ),
            "creates_task": False,
            "creates_provider_model_task": False,
            "calls_provider_model_now": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "local_compute_execution_implemented": False,
            "requires_post_task_worker_or_local_fallback": True,
            "requires_call_ledger": True,
            "requires_model_ledger_for_deepseek": live_light_research_scope_row.get(
                "requires_model_ledger_for_deepseek",
                False,
            ),
            "config_row_is_production_evidence": False,
            "global_config_allowlist_promoted": live_light_research_scope_allowlist_promoted,
            "global_config_allowlist_promotion_pending": not live_light_research_scope_allowlist_promoted,
        },
        {
            "config": PROVIDER_MODEL_ENABLEMENT_CONFIG_KEY,
            "category": "provider_model_release_switch",
            "purpose": "default_off_release_switch_for_real_provider_model_task_creation_after_acceptance",
            "default_value_safe": False,
            "configured_value_safe": provider_model_enablement_row.get("configured_value_safe", False),
            "effective_value_safe": False,
            "source": provider_model_enablement_row.get("source", "default"),
            "mode_gate": "live_light_and_provider_model_promotion",
            "automation_surface": "provider_model_task_creation_release_switch_only",
            "release_switch_default_enabled": False,
            "provider_model_task_creation_allowed": False,
            "provider_model_execution_requires_execution_request": True,
            "requires_call_ledger": True,
            "requires_model_ledger_for_deepseek": True,
            "requires_browser_nonblocking_evidence": True,
            "requires_redaction_review": True,
            "frontend_writeback_allowed": False,
            "global_config_allowlist_promoted": provider_model_enablement_allowlist_promoted,
            "global_config_allowlist_promotion_pending": not provider_model_enablement_allowlist_promoted,
            "rollback_on_evidence_regression_required": True,
            "production_promotion_required_after_switch": True,
        },
        {
            "config": FRONTEND_ENABLEMENT_CONFIG_KEY,
            "category": "frontend_release_switch",
            "purpose": "server_side_default_off_release_switch_for_stage_04_frontend_enablement_after_promotion",
            "default_value_safe": False,
            "configured_value_safe": frontend_enablement_row.get("configured_value_safe", False),
            "effective_value_safe": False,
            "source": frontend_enablement_row.get("source", "default"),
            "mode_gate": "live_light_and_frontend_enablement_promotion",
            "automation_surface": "frontend_enablement_release_switch_only_no_task",
            "release_switch_default_enabled": False,
            "frontend_enablement_allowed": False,
            "frontend_writeback_allowed": False,
            "global_config_allowlist_promoted": frontend_enablement_allowlist_promoted,
            "global_config_allowlist_promotion_pending": not frontend_enablement_allowlist_promoted,
            "rollback_on_evidence_regression_required": True,
            "production_promotion_required_after_switch": True,
        },
        {
            "config": "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT",
            "category": "runtime_budget",
            "purpose": "bound_live_light_symbol_scope",
            "default_value_safe": 20,
            "effective_value_safe": rows_by_config["COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT"].get("value_safe"),
            "minimum": 1,
            "maximum": 200,
            "mode_gate": "live_light_runtime_budget",
            "automation_surface": "scope_limit_only",
        },
        {
            "config": "COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS",
            "category": "runtime_budget",
            "purpose": "bound_live_light_background_task_frequency",
            "default_value_safe": 600,
            "effective_value_safe": rows_by_config["COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS"].get("value_safe"),
            "minimum": 60,
            "maximum": 86400,
            "mode_gate": "live_light_runtime_budget",
            "automation_surface": "rate_limit_only",
        },
        {
            "config": "COMMAND_CENTER_LIVE_DEEPSEEK_MODEL",
            "category": "model_label",
            "purpose": "safe_model_label_for_future_deepseek_model_ledger",
            "effective_value_safe": rows_by_config["COMMAND_CENTER_LIVE_DEEPSEEK_MODEL"].get("value_safe"),
            "mode_gate": "future_deepseek_execution_request",
            "automation_surface": "label_only_no_model_call",
            "raw_prompt_or_output_allowed": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_ALLOW_FULL_POOL",
            "category": "reserved_full_mode",
            "purpose": "reserve_future_full_pool_or_deep_scan_authorization",
            "default_value_safe": False,
            "configured_value_safe": rows_by_config["COMMAND_CENTER_LIVE_ALLOW_FULL_POOL"].get("configured_value_safe"),
            "effective_value_safe": False,
            "mode_gate": "live_full_future_authorization",
            "automation_surface": "reserved_disabled",
            "full_pool_on_open_allowed": False,
            "deep_scan_on_open_allowed": False,
        },
    ]
    common_row_flags = {
        "frontend_visible": True,
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "config_source_of_truth": "server_config_layer",
        "raw_value_exposed": False,
        "credential_values_exposed": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "fastapi_startup_creates_task": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    reference_rows = [{**row, **common_row_flags} for row in reference_rows]
    reference_config_names = [str(row.get("config") or "") for row in reference_rows]
    runtime_config_names = list(COMMAND_CENTER_RUNTIME_CONFIG_NAMES)
    runtime_config_names_match_reference_rows = reference_config_names == runtime_config_names
    runtime_config_names_are_allowlisted = set(runtime_config_names).issubset(CONFIG_NAMES)
    config_audit_payload = {
        "mode": active_mode,
        "reference_rows": reference_rows,
        "schema_version": BOOTSTRAP_RUNTIME_CONFIG_REFERENCE_SCHEMA_VERSION,
    }
    config_audit_id = hashlib.sha256(
        json.dumps(config_audit_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    category_counts = {
        category: sum(1 for row in reference_rows if row["category"] == category)
        for category in sorted({row["category"] for row in reference_rows})
    }
    return {
        "schema_version": BOOTSTRAP_RUNTIME_CONFIG_REFERENCE_SCHEMA_VERSION,
        "status": "runtime_config_reference_visible_read_only",
        "mode": active_mode,
        "config_reference_row_count": len(reference_rows),
        "runtime_config_names_source": "config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES",
        "runtime_config_names": runtime_config_names,
        "runtime_config_name_count": len(runtime_config_names),
        "runtime_config_names_match_reference_rows": runtime_config_names_match_reference_rows,
        "runtime_config_names_are_allowlisted": runtime_config_names_are_allowlisted,
        "runtime_config_names_missing_from_allowlist": sorted(set(runtime_config_names) - set(CONFIG_NAMES)),
        "category_counts": category_counts,
        "source_switch_count": category_counts.get("source_switch", 0),
        "runtime_budget_config_count": category_counts.get("runtime_budget", 0),
        "config_audit_id": config_audit_id,
        "config_audit_algorithm": "sha256_safe_reference_rows_v1",
        "config_audit_input_surface": "safe_reference_rows_only",
        "config_audit_row_count": len(reference_rows),
        "config_audit_bound_to_mode": active_mode,
        "config_audit_includes_raw_values": False,
        "config_audit_includes_credential_values": False,
        "config_audit_is_production_evidence": False,
        "reference_rows": reference_rows,
        "frontend_visible": True,
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "config_source_of_truth": "server_config_layer",
        "config_rows_are_operator_guidance_not_controls": True,
        "cache_only_default_offline_priority": True,
        "manual_requires_explicit_post_task": True,
        "live_light_allows_bounded_background_task": True,
        "live_full_reserved_requires_separate_authorization": True,
        "provider_model_execution_requires_execution_request": True,
        "config_reference_is_production_evidence": False,
        "production_config_complete": False,
        "raw_value_exposed": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "fastapi_startup_creates_task": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_prices_positions_or_operation_zones": True,
    }


def _runtime_config_ownership_invariant_contract(
    *,
    active_mode: str,
    runtime_config_reference_contract: dict[str, Any],
    search_submit_config_handoff_contract: dict[str, Any],
    search_submit_config_promotion_contract: dict[str, Any],
) -> dict[str, Any]:
    reference_rows = [
        row for row in runtime_config_reference_contract.get("reference_rows", []) if isinstance(row, dict)
    ]
    fallback_key = str(search_submit_config_handoff_contract.get("config_key") or "")
    search_submit_allowlist_promoted = bool(
        search_submit_config_handoff_contract.get("global_config_allowlist_promoted")
    )
    ownership_rows: list[dict[str, Any]] = []
    for row in reference_rows:
        config_key = str(row.get("config") or "")
        is_search_submit_config = config_key == fallback_key
        is_startup_autostart_config = config_key == STARTUP_AUTOSTART_CONFIG_KEY
        is_external_execution_profile_config = config_key == EXTERNAL_EXECUTION_PROFILE_CONFIG_KEY
        is_live_light_research_scope_config = config_key == LIVE_LIGHT_RESEARCH_SCOPE_CONFIG_KEY
        is_provider_model_enablement_config = config_key == PROVIDER_MODEL_ENABLEMENT_CONFIG_KEY
        uses_bootstrap_fallback = is_search_submit_config and bool(
            search_submit_config_handoff_contract.get("bootstrap_local_env_fallback_available")
        )
        search_submit_fallback_removed = is_search_submit_config and bool(
            search_submit_config_handoff_contract.get("bootstrap_local_env_fallback_removed")
        )
        search_submit_fallback_removal_pending = is_search_submit_config and bool(
            search_submit_config_handoff_contract.get("fallback_removal_pending")
        )
        search_submit_allowlist_promotion_pending = (
            is_search_submit_config and not search_submit_allowlist_promoted
        )
        future_global_key_pending = (
            config_key == FRONTEND_ENABLEMENT_CONFIG_KEY
            and row.get("global_config_allowlist_promotion_pending") is True
        )
        frontend_allowlist_promoted = (
            config_key == FRONTEND_ENABLEMENT_CONFIG_KEY
            and row.get("global_config_allowlist_promoted") is True
        )
        provider_model_enablement_allowlist_promoted = (
            is_provider_model_enablement_config
            and row.get("global_config_allowlist_promoted") is True
        )
        startup_autostart_allowlist_promoted = (
            is_startup_autostart_config
            and row.get("global_config_allowlist_promoted") is True
        )
        external_execution_profile_allowlist_promoted = (
            is_external_execution_profile_config
            and row.get("global_config_allowlist_promoted") is True
        )
        live_light_research_scope_allowlist_promoted = (
            is_live_light_research_scope_config
            and row.get("global_config_allowlist_promoted") is True
        )
        ownership_rows.append(
            {
                "config": config_key,
                "category": row.get("category"),
                "mode_gate": row.get("mode_gate"),
                "ownership_status": (
                    "server_config_layer_owned_global_config_allowlist_promoted"
                    if search_submit_fallback_removed
                    else "server_config_layer_owned_global_config_allowlist_promoted_default_off"
                    if (
                        frontend_allowlist_promoted
                        or startup_autostart_allowlist_promoted
                        or provider_model_enablement_allowlist_promoted
                    )
                    else "server_config_layer_owned_global_config_allowlist_promoted_default_plan_only"
                    if external_execution_profile_allowlist_promoted
                    else "server_config_layer_owned_global_config_allowlist_promoted_default_research_scope"
                    if live_light_research_scope_allowlist_promoted
                    else "global_config_layer_owned_bootstrap_fallback_removal_pending"
                    if search_submit_fallback_removal_pending
                    else "bootstrap_local_env_fallback_visible_global_allowlist_promotion_pending"
                    if search_submit_allowlist_promotion_pending
                    else "future_global_config_key_pending_default_off"
                    if future_global_key_pending
                    else "server_config_layer_owned"
                ),
                "current_read_path": (
                    search_submit_config_handoff_contract.get("current_read_path")
                    if is_search_submit_config
                    else "global_config_layer_default_false_release_switch_guard"
                    if frontend_allowlist_promoted
                    else "global_config_layer_default_false_provider_model_enablement_guard"
                    if provider_model_enablement_allowlist_promoted
                    else "global_config_layer_default_false_startup_autostart_guard"
                    if startup_autostart_allowlist_promoted
                    else "global_config_layer_default_plan_only_external_execution_guard"
                    if external_execution_profile_allowlist_promoted
                    else "global_config_layer_default_live_light_research_scope_guard"
                    if live_light_research_scope_allowlist_promoted
                    else "not_read_effective_default_false_until_global_config_allowlist"
                    if future_global_key_pending
                    else "server_config_layer"
                ),
                "target_read_path": "global_config_layer_only"
                if (
                    is_search_submit_config
                    or future_global_key_pending
                    or frontend_allowlist_promoted
                    or provider_model_enablement_allowlist_promoted
                    or startup_autostart_allowlist_promoted
                    or external_execution_profile_allowlist_promoted
                    or live_light_research_scope_allowlist_promoted
                )
                else "server_config_layer",
                "bootstrap_local_env_fallback_available": uses_bootstrap_fallback,
                "bootstrap_local_env_fallback_is_temporary": uses_bootstrap_fallback,
                "bootstrap_local_env_fallback_removed": search_submit_fallback_removed,
                "global_config_allowlist_promoted": search_submit_allowlist_promoted
                if is_search_submit_config
                else True
                if (
                    frontend_allowlist_promoted
                    or provider_model_enablement_allowlist_promoted
                    or startup_autostart_allowlist_promoted
                    or external_execution_profile_allowlist_promoted
                    or live_light_research_scope_allowlist_promoted
                )
                else False,
                "global_config_allowlist_promotion_pending": (
                    search_submit_allowlist_promotion_pending or future_global_key_pending
                ),
                "fallback_removal_pending": search_submit_fallback_removal_pending,
                "requires_future_config_py_file_scope": (
                    search_submit_allowlist_promotion_pending or future_global_key_pending
                ),
                "fallback_is_production_config_evidence": False,
                "frontend_visible": True,
                "frontend_editable": False,
                "frontend_writeback_allowed": False,
                "status_endpoint_writeback_allowed": False,
                "config_change_channel": "server_config_layer_only",
                "config_source_of_truth": "server_config_layer",
                "safe_value_visible_only": True,
                "raw_value_exposed": False,
                "credential_values_exposed": False,
                "credential_env_key_names_included": False,
                "config_row_is_production_evidence": False,
                "cache_get_creates_task": False,
                "react_render_creates_task": False,
                "fastapi_startup_creates_task": False,
                "search_typing_creates_task": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    fallback_count = sum(1 for row in ownership_rows if row["bootstrap_local_env_fallback_available"])
    promotion_pending_count = sum(1 for row in ownership_rows if row["global_config_allowlist_promotion_pending"])
    future_config_file_scope_required = any(row["requires_future_config_py_file_scope"] for row in ownership_rows)
    fallback_removal_pending = any(row["fallback_removal_pending"] for row in ownership_rows)
    search_submit_fallback_removed = any(
        row["config"] == fallback_key and row["bootstrap_local_env_fallback_removed"] for row in ownership_rows
    )
    ownership_audit_payload = {
        "mode": active_mode,
        "ownership_rows": ownership_rows,
        "linked_runtime_config_reference_audit_id": runtime_config_reference_contract.get("config_audit_id"),
        "schema_version": BOOTSTRAP_RUNTIME_CONFIG_OWNERSHIP_SCHEMA_VERSION,
    }
    ownership_audit_id = hashlib.sha256(
        json.dumps(ownership_audit_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "schema_version": BOOTSTRAP_RUNTIME_CONFIG_OWNERSHIP_SCHEMA_VERSION,
        "status": (
            "runtime_config_ownership_invariant_visible_fallback_removal_pending"
            if fallback_removal_pending
            else "runtime_config_ownership_invariant_visible_search_submit_fallback_removed_frontend_promotion_pending"
            if search_submit_fallback_removed and promotion_pending_count > 0
            else "runtime_config_ownership_invariant_visible_global_config_allowlist_promoted_frontend_default_off"
            if search_submit_fallback_removed
            else "runtime_config_ownership_invariant_visible_config_promotion_pending"
        ),
        "mode": active_mode,
        "ownership_row_count": len(ownership_rows),
        "ownership_rows": ownership_rows,
        "frontend_editable_row_count": sum(1 for row in ownership_rows if row["frontend_editable"]),
        "frontend_writeback_allowed_count": sum(1 for row in ownership_rows if row["frontend_writeback_allowed"]),
        "status_endpoint_writeback_allowed_count": sum(
            1 for row in ownership_rows if row["status_endpoint_writeback_allowed"]
        ),
        "bootstrap_local_env_fallback_count": fallback_count,
        "global_config_allowlist_promotion_pending_count": promotion_pending_count,
        "config_source_of_truth": "server_config_layer",
        "operator_change_channel": "server_config_layer_only",
        "frontend_visible": True,
        "frontend_editable": False,
        "frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "current_cycle_modifies_global_config_file": (
            search_submit_config_promotion_contract.get("current_cycle_modifies_global_config_file") is True
        ),
        "current_cycle_file_limit_respected": True,
        "requires_future_config_py_file_scope": future_config_file_scope_required,
        "bootstrap_local_env_fallback_removal_pending": fallback_removal_pending,
        "bootstrap_local_env_fallback_removed": search_submit_fallback_removed,
        "production_config_complete": False,
        "ownership_invariant_is_production_evidence": False,
        "linked_runtime_config_reference_schema": runtime_config_reference_contract.get("schema_version"),
        "linked_runtime_config_reference_audit_id": runtime_config_reference_contract.get("config_audit_id"),
        "linked_search_submit_config_handoff_schema": search_submit_config_handoff_contract.get("schema_version"),
        "linked_search_submit_config_promotion_schema": search_submit_config_promotion_contract.get(
            "schema_version"
        ),
        "promotion_step_count": search_submit_config_promotion_contract.get("promotion_step_count"),
        "ownership_audit_id": ownership_audit_id,
        "ownership_audit_algorithm": "sha256_safe_ownership_rows_v1",
        "ownership_audit_input_surface": "safe_ownership_rows_and_reference_audit_id_only",
        "ownership_audit_row_count": len(ownership_rows),
        "ownership_audit_includes_raw_values": False,
        "ownership_audit_includes_credential_values": False,
        "ownership_audit_is_production_evidence": False,
        "raw_value_exposed": False,
        "credential_values_exposed": False,
        "credential_env_key_names_included": False,
        "cache_get_creates_task": False,
        "react_render_creates_task": False,
        "fastapi_startup_creates_task": False,
        "search_typing_creates_task": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def read_bootstrap_status_cache() -> dict[str, Any]:
    active_mode, configured_mode_raw_safe, mode_valid, mode_source, mode_raw_redacted = _runtime_mode()
    tushare_on_open, tushare_source = _bool_config("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", False)
    deepseek_on_open, deepseek_source = _bool_config("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", False)
    startup_autostart_configured, startup_autostart_source = _bool_config(STARTUP_AUTOSTART_CONFIG_KEY, False)
    search_submit_autostart_on_submit, search_submit_autostart_source = _bool_config(
        "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART",
        False,
    )
    frontend_enablement_configured, frontend_enablement_source = _bool_config(
        FRONTEND_ENABLEMENT_CONFIG_KEY,
        False,
    )
    provider_model_enablement_configured, provider_model_enablement_source = _bool_config(
        PROVIDER_MODEL_ENABLEMENT_CONFIG_KEY,
        False,
    )
    (
        external_execution_profile_configured,
        external_execution_profile_source,
        external_execution_profile_raw_safe,
        external_execution_profile_valid,
        external_execution_profile_raw_redacted,
    ) = _enum_config(
        EXTERNAL_EXECUTION_PROFILE_CONFIG_KEY,
        DEFAULT_EXTERNAL_EXECUTION_PROFILE,
        EXTERNAL_EXECUTION_PROFILES,
    )
    (
        live_light_research_scope_configured,
        live_light_research_scope_source,
        live_light_research_scope_raw_safe,
        live_light_research_scope_valid,
        live_light_research_scope_raw_redacted,
    ) = _enum_config(
        LIVE_LIGHT_RESEARCH_SCOPE_CONFIG_KEY,
        DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE,
        LIVE_LIGHT_RESEARCH_SCOPES,
    )
    allow_full_pool, full_pool_source = _bool_config("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL", False)
    symbol_limit, symbol_limit_source = _int_config(
        "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT",
        20,
        minimum=1,
        maximum=200,
    )
    rate_limit_seconds, rate_limit_source = _int_config(
        "COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS",
        600,
        minimum=60,
        maximum=86400,
    )
    deepseek_model_raw = _config_value("COMMAND_CENTER_LIVE_DEEPSEEK_MODEL")
    deepseek_model_source = "configured" if deepseek_model_raw else "model_strategy_fallback"
    deepseek_model = _safe_text(deepseek_model_raw or get_deepseek_model("explain"), limit=80)
    deepseek_model_redacted = deepseek_model == "[redacted_sensitive_text]"
    loaded_at = _now_iso()

    live_light_enabled = active_mode == "live_light"
    effective_tushare_on_open = live_light_enabled and tushare_on_open
    effective_deepseek_on_open = live_light_enabled and deepseek_on_open
    live_light_sources_enabled = live_light_enabled and (tushare_on_open or deepseek_on_open)
    effective_startup_autostart = (
        live_light_enabled and startup_autostart_configured and live_light_sources_enabled
    )
    effective_search_submit_autostart = live_light_enabled and search_submit_autostart_on_submit
    effective_external_execution_profile = (
        external_execution_profile_configured
        if live_light_enabled
        else DEFAULT_EXTERNAL_EXECUTION_PROFILE
    )
    effective_live_light_research_scope = (
        live_light_research_scope_configured
        if live_light_enabled
        else "bootstrap_only"
    )
    external_execution_profile_provider_stage_allowed = bool(
        live_light_enabled
        and live_light_sources_enabled
        and effective_external_execution_profile in {"light_provider", "light_provider_model"}
    )
    external_execution_profile_model_stage_allowed = bool(
        live_light_enabled
        and live_light_sources_enabled
        and effective_external_execution_profile == "light_provider_model"
    )
    live_light_research_scope_provider_stage_allowed = bool(
        live_light_enabled
        and live_light_sources_enabled
        and effective_live_light_research_scope in {"provider_factor_next", "provider_factor_next_model"}
    )
    live_light_research_scope_factor_light_allowed = live_light_research_scope_provider_stage_allowed
    live_light_research_scope_next_session_allowed = live_light_research_scope_provider_stage_allowed
    live_light_research_scope_model_stage_allowed = bool(
        live_light_enabled
        and live_light_sources_enabled
        and effective_live_light_research_scope == "provider_factor_next_model"
    )
    effective_frontend_enablement = False
    effective_provider_model_enablement = False
    tushare_effective_status, tushare_inactive_reason = _live_light_source_switch_effective_status(
        active_mode=active_mode,
        configured_value=tushare_on_open,
        effective_value=effective_tushare_on_open,
    )
    deepseek_effective_status, deepseek_inactive_reason = _live_light_source_switch_effective_status(
        active_mode=active_mode,
        configured_value=deepseek_on_open,
        effective_value=effective_deepseek_on_open,
    )
    if not live_light_enabled:
        if active_mode == "cache_only":
            startup_autostart_effective_status = "cache_only_startup_autostart_disabled"
            startup_autostart_inactive_reason = "cache_only_read_only"
        elif active_mode == "manual":
            startup_autostart_effective_status = "manual_startup_autostart_disabled_explicit_task_only"
            startup_autostart_inactive_reason = "manual_requires_explicit_post_task"
        elif active_mode == "live_full":
            startup_autostart_effective_status = "live_full_startup_autostart_disabled_reserved"
            startup_autostart_inactive_reason = "live_full_reserved_requires_separate_authorization"
        else:
            startup_autostart_effective_status = "mode_gate_inactive_requires_live_light"
            startup_autostart_inactive_reason = "requires_live_light_mode"
    elif not startup_autostart_configured:
        startup_autostart_effective_status = "startup_autostart_config_disabled"
        startup_autostart_inactive_reason = "startup_autostart_config_false"
    elif not live_light_sources_enabled:
        startup_autostart_effective_status = "source_switch_disabled"
        startup_autostart_inactive_reason = "source_switch_false"
    else:
        startup_autostart_effective_status = "effective_after_cache_render"
        startup_autostart_inactive_reason = ""
    if not live_light_enabled:
        if active_mode == "cache_only":
            external_execution_profile_effective_status = "cache_only_external_execution_profile_disabled"
            external_execution_profile_inactive_reason = "cache_only_read_only"
        elif active_mode == "manual":
            external_execution_profile_effective_status = (
                "manual_external_execution_profile_disabled_explicit_task_only"
            )
            external_execution_profile_inactive_reason = "manual_requires_explicit_post_task"
        elif active_mode == "live_full":
            external_execution_profile_effective_status = "live_full_external_execution_profile_disabled_reserved"
            external_execution_profile_inactive_reason = "live_full_reserved_requires_separate_authorization"
        else:
            external_execution_profile_effective_status = "mode_gate_inactive_requires_live_light"
            external_execution_profile_inactive_reason = "requires_live_light_mode"
    elif not external_execution_profile_valid:
        external_execution_profile_effective_status = "invalid_profile_defaulted_to_plan_only"
        external_execution_profile_inactive_reason = "invalid_profile_defaulted"
    elif external_execution_profile_configured == DEFAULT_EXTERNAL_EXECUTION_PROFILE:
        external_execution_profile_effective_status = "plan_only_no_provider_model_execution"
        external_execution_profile_inactive_reason = "plan_only_profile"
    elif not live_light_sources_enabled:
        external_execution_profile_effective_status = "source_switch_disabled"
        external_execution_profile_inactive_reason = "source_switch_false"
    else:
        external_execution_profile_effective_status = "profile_selected_executor_pending"
        external_execution_profile_inactive_reason = "execution_engine_pending"
    if not live_light_enabled:
        if active_mode == "cache_only":
            live_light_research_scope_effective_status = "cache_only_live_light_research_scope_disabled"
            live_light_research_scope_inactive_reason = "cache_only_read_only"
        elif active_mode == "manual":
            live_light_research_scope_effective_status = (
                "manual_live_light_research_scope_disabled_explicit_task_only"
            )
            live_light_research_scope_inactive_reason = "manual_requires_explicit_post_task"
        elif active_mode == "live_full":
            live_light_research_scope_effective_status = "live_full_live_light_research_scope_disabled_reserved"
            live_light_research_scope_inactive_reason = "live_full_reserved_requires_separate_authorization"
        else:
            live_light_research_scope_effective_status = "mode_gate_inactive_requires_live_light"
            live_light_research_scope_inactive_reason = "requires_live_light_mode"
    elif not live_light_research_scope_valid:
        live_light_research_scope_effective_status = "invalid_scope_defaulted"
        live_light_research_scope_inactive_reason = "invalid_scope_defaulted"
    elif effective_live_light_research_scope == "bootstrap_only":
        live_light_research_scope_effective_status = "bootstrap_only_no_research_pipeline"
        live_light_research_scope_inactive_reason = "bootstrap_only_scope"
    elif not live_light_sources_enabled:
        live_light_research_scope_effective_status = "source_switch_disabled"
        live_light_research_scope_inactive_reason = "source_switch_false"
    else:
        live_light_research_scope_effective_status = "research_scope_visible_executor_pending"
        live_light_research_scope_inactive_reason = "execution_engine_pending"
    search_submit_autostart_effective_status, search_submit_autostart_inactive_reason = (
        _search_submit_autostart_effective_status(
            active_mode=active_mode,
            configured_value=search_submit_autostart_on_submit,
            effective_value=effective_search_submit_autostart,
        )
    )
    if not live_light_enabled:
        if active_mode == "cache_only":
            frontend_enablement_effective_status = "cache_only_frontend_enablement_disabled"
            frontend_enablement_inactive_reason = "cache_only_read_only"
        elif active_mode == "manual":
            frontend_enablement_effective_status = (
                "manual_frontend_enablement_disabled_explicit_task_only"
            )
            frontend_enablement_inactive_reason = "manual_requires_explicit_post_task"
        elif active_mode == "live_full":
            frontend_enablement_effective_status = "live_full_frontend_enablement_disabled_reserved"
            frontend_enablement_inactive_reason = "live_full_reserved_requires_separate_authorization"
        else:
            frontend_enablement_effective_status = "mode_gate_inactive_requires_live_light"
            frontend_enablement_inactive_reason = "requires_live_light_mode"
    elif frontend_enablement_configured:
        frontend_enablement_effective_status = "release_switch_blocked_until_promotion"
        frontend_enablement_inactive_reason = "frontend_enablement_promotion_required"
    else:
        frontend_enablement_effective_status = "release_switch_default_off"
        frontend_enablement_inactive_reason = "release_switch_default_off"
    if not live_light_enabled:
        if active_mode == "cache_only":
            provider_model_enablement_effective_status = "cache_only_provider_model_enablement_disabled"
            provider_model_enablement_inactive_reason = "cache_only_read_only"
        elif active_mode == "manual":
            provider_model_enablement_effective_status = (
                "manual_provider_model_enablement_disabled_explicit_task_only"
            )
            provider_model_enablement_inactive_reason = "manual_requires_explicit_provider_model_task"
        elif active_mode == "live_full":
            provider_model_enablement_effective_status = "live_full_provider_model_enablement_disabled_reserved"
            provider_model_enablement_inactive_reason = "live_full_reserved_requires_separate_authorization"
        else:
            provider_model_enablement_effective_status = "mode_gate_inactive_requires_live_light"
            provider_model_enablement_inactive_reason = "requires_live_light_mode"
    elif provider_model_enablement_configured:
        provider_model_enablement_effective_status = "release_switch_blocked_until_provider_model_promotion"
        provider_model_enablement_inactive_reason = "provider_model_promotion_required"
    else:
        provider_model_enablement_effective_status = "release_switch_default_off"
        provider_model_enablement_inactive_reason = "release_switch_default_off"
    status = {
        "cache_only": "cache_only_ready_no_bootstrap",
        "manual": "manual_ready_explicit_task_only",
        "live_light": "live_light_config_visible_task_ready_local_only",
        "live_full": "live_full_reserved_disabled",
    }[active_mode]
    if not mode_valid:
        status = "invalid_mode_defaulted_to_cache_only"

    config_rows = [
        {
            "config": "COMMAND_CENTER_BOOTSTRAP_MODE",
            **_config_row_display_controls(),
            "value_type": "enum",
            "value_safe": active_mode,
            "default_value_safe": DEFAULT_MODE,
            "allowed_values": list(BOOTSTRAP_MODES),
            "raw_value_safe": configured_mode_raw_safe,
            "raw_value_valid": mode_valid,
            "raw_value_exposed": False,
            "raw_value_safe_visible": True,
            "raw_invalid_value_redacted": mode_raw_redacted,
            "fallback_value_safe": DEFAULT_MODE if not mode_valid else "",
            "fallback_reason": "invalid_mode_defaulted_to_cache_only" if not mode_valid else "",
            "source": mode_source,
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN",
            **_config_row_display_controls(),
            "value_type": "boolean",
            "value_safe": tushare_on_open,
            "configured_value_safe": tushare_on_open,
            "effective_value_safe": effective_tushare_on_open,
            "mode_gate": "live_light",
            "effective_status": tushare_effective_status,
            "automation_effective": effective_tushare_on_open,
            "inactive_reason": tushare_inactive_reason,
            "default_value_safe": False,
            "allowed_values": [False, True],
            "raw_value_exposed": False,
            "source": tushare_source,
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN",
            **_config_row_display_controls(),
            "value_type": "boolean",
            "value_safe": deepseek_on_open,
            "configured_value_safe": deepseek_on_open,
            "effective_value_safe": effective_deepseek_on_open,
            "mode_gate": "live_light",
            "effective_status": deepseek_effective_status,
            "automation_effective": effective_deepseek_on_open,
            "inactive_reason": deepseek_inactive_reason,
            "default_value_safe": False,
            "allowed_values": [False, True],
            "raw_value_exposed": False,
            "source": deepseek_source,
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART",
            **_config_row_display_controls(),
            "value_type": "boolean",
            "value_safe": search_submit_autostart_on_submit,
            "configured_value_safe": search_submit_autostart_on_submit,
            "effective_value_safe": effective_search_submit_autostart,
            "mode_gate": "live_light",
            "effective_status": search_submit_autostart_effective_status,
            "automation_effective": effective_search_submit_autostart,
            "inactive_reason": search_submit_autostart_inactive_reason,
            "default_value_safe": False,
            "allowed_values": [False, True],
            "raw_value_exposed": False,
            "source": search_submit_autostart_source,
            "scope": "searched_symbol_submit_local_projection_task_only",
            "creates_provider_model_task": False,
            "contains_secret": False,
        },
        {
            "config": STARTUP_AUTOSTART_CONFIG_KEY,
            **_config_row_display_controls(),
            "value_type": "boolean",
            "value_safe": startup_autostart_configured,
            "configured_value_safe": startup_autostart_configured,
            "effective_value_safe": effective_startup_autostart,
            "mode_gate": "live_light_after_cache_render_and_sources_enabled",
            "effective_status": startup_autostart_effective_status,
            "automation_effective": effective_startup_autostart,
            "inactive_reason": startup_autostart_inactive_reason,
            "default_value_safe": False,
            "allowed_values": [False, True],
            "raw_value_exposed": False,
            "source": startup_autostart_source,
            "scope": "react_after_cache_render_live_startup_local_task_only",
            "creates_local_background_task_only": effective_startup_autostart,
            "creates_provider_model_task": False,
            "contains_secret": False,
        },
        {
            "config": EXTERNAL_EXECUTION_PROFILE_CONFIG_KEY,
            **_config_row_display_controls(),
            "value_type": "enum",
            "value_safe": external_execution_profile_configured,
            "configured_value_safe": external_execution_profile_configured,
            "effective_value_safe": effective_external_execution_profile,
            "default_value_safe": DEFAULT_EXTERNAL_EXECUTION_PROFILE,
            "allowed_values": list(EXTERNAL_EXECUTION_PROFILES),
            "raw_value_safe": external_execution_profile_raw_safe,
            "raw_value_valid": external_execution_profile_valid,
            "raw_value_exposed": False,
            "raw_value_safe_visible": not external_execution_profile_valid,
            "raw_invalid_value_redacted": external_execution_profile_raw_redacted,
            "mode_gate": "live_light_post_task_worker_ledger",
            "effective_status": external_execution_profile_effective_status,
            "automation_effective": effective_external_execution_profile != DEFAULT_EXTERNAL_EXECUTION_PROFILE
            and live_light_enabled,
            "inactive_reason": external_execution_profile_inactive_reason,
            "source": external_execution_profile_source,
            "scope": "post_task_worker_or_local_fallback_light_execution_profile_only",
            "provider_stage_allowed_by_profile": external_execution_profile_provider_stage_allowed,
            "model_stage_allowed_by_profile": external_execution_profile_model_stage_allowed,
            "creates_provider_model_task": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "calls_provider_model_now": False,
            "requires_post_task_worker_or_local_fallback": True,
            "requires_call_ledger": True,
            "requires_model_ledger_for_deepseek": (
                effective_external_execution_profile == "light_provider_model"
            ),
            "contains_secret": False,
        },
        {
            "config": LIVE_LIGHT_RESEARCH_SCOPE_CONFIG_KEY,
            **_config_row_display_controls(),
            "value_type": "enum",
            "value_safe": live_light_research_scope_configured,
            "configured_value_safe": live_light_research_scope_configured,
            "effective_value_safe": effective_live_light_research_scope,
            "default_value_safe": DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE,
            "allowed_values": list(LIVE_LIGHT_RESEARCH_SCOPES),
            "raw_value_safe": live_light_research_scope_raw_safe,
            "raw_value_valid": live_light_research_scope_valid,
            "raw_value_exposed": False,
            "raw_value_safe_visible": not live_light_research_scope_valid,
            "raw_invalid_value_redacted": live_light_research_scope_raw_redacted,
            "mode_gate": "live_light_research_scope_after_cache_render",
            "effective_status": live_light_research_scope_effective_status,
            "automation_effective": False,
            "inactive_reason": live_light_research_scope_inactive_reason,
            "source": live_light_research_scope_source,
            "scope": "stage_bundle_only_no_execution",
            "provider_stage_allowed_by_scope": live_light_research_scope_provider_stage_allowed,
            "factor_light_allowed_by_scope": live_light_research_scope_factor_light_allowed,
            "next_session_cache_allowed_by_scope": live_light_research_scope_next_session_allowed,
            "model_stage_allowed_by_scope": live_light_research_scope_model_stage_allowed,
            "creates_task": False,
            "creates_provider_model_task": False,
            "calls_provider_model_now": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "local_compute_execution_implemented": False,
            "requires_post_task_worker_or_local_fallback": True,
            "requires_call_ledger": True,
            "requires_model_ledger_for_deepseek": (
                effective_live_light_research_scope == "provider_factor_next_model"
            ),
            "contains_secret": False,
        },
        {
            "config": PROVIDER_MODEL_ENABLEMENT_CONFIG_KEY,
            **_config_row_display_controls(),
            "value_type": "boolean",
            "value_safe": provider_model_enablement_configured,
            "configured_value_safe": provider_model_enablement_configured,
            "effective_value_safe": effective_provider_model_enablement,
            "mode_gate": "live_light_and_provider_model_promotion",
            "effective_status": provider_model_enablement_effective_status,
            "automation_effective": False,
            "inactive_reason": provider_model_enablement_inactive_reason,
            "default_value_safe": False,
            "allowed_values": [False, True],
            "raw_value_exposed": False,
            "source": provider_model_enablement_source,
            "scope": "provider_model_task_creation_release_switch_only",
            "release_switch_default_enabled": False,
            "provider_model_task_creation_allowed": False,
            "provider_model_execution_requires_execution_request": True,
            "provider_model_execution_requires_task_contract": True,
            "requires_call_ledger": True,
            "requires_model_ledger_for_deepseek": True,
            "requires_browser_nonblocking_evidence": True,
            "requires_redaction_review": True,
            "creates_task": False,
            "creates_provider_model_task": False,
            "calls_provider_model_now": False,
            "frontend_writeback_allowed": False,
            "status_endpoint_writeback_allowed": False,
            "contains_secret": False,
        },
        {
            "config": FRONTEND_ENABLEMENT_CONFIG_KEY,
            **_config_row_display_controls(),
            "value_type": "boolean",
            "value_safe": frontend_enablement_configured,
            "configured_value_safe": frontend_enablement_configured,
            "effective_value_safe": effective_frontend_enablement,
            "mode_gate": "live_light_and_frontend_enablement_promotion",
            "effective_status": frontend_enablement_effective_status,
            "automation_effective": False,
            "inactive_reason": frontend_enablement_inactive_reason,
            "default_value_safe": False,
            "allowed_values": [False, True],
            "raw_value_exposed": False,
            "source": frontend_enablement_source,
            "scope": "frontend_enablement_release_switch_only",
            "release_switch_default_enabled": False,
            "frontend_enablement_allowed": False,
            "frontend_writeback_allowed": False,
            "status_endpoint_writeback_allowed": False,
            "creates_task": False,
            "creates_provider_model_task": False,
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT",
            **_config_row_display_controls(),
            "value_type": "integer",
            "value_safe": symbol_limit,
            "default_value_safe": 20,
            "minimum": 1,
            "maximum": 200,
            "raw_value_exposed": False,
            "source": symbol_limit_source,
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS",
            **_config_row_display_controls(),
            "value_type": "integer",
            "value_safe": rate_limit_seconds,
            "default_value_safe": 600,
            "minimum": 60,
            "maximum": 86400,
            "raw_value_exposed": False,
            "source": rate_limit_source,
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_DEEPSEEK_MODEL",
            **_config_row_display_controls(),
            "value_type": "model_name",
            "value_safe": deepseek_model,
            "default_source": "model_strategy_explain",
            "raw_value_exposed": False,
            "secret_like_raw_redacted": deepseek_model_redacted,
            "source": deepseek_model_source,
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_ALLOW_FULL_POOL",
            **_config_row_display_controls(),
            "value_type": "boolean",
            "value_safe": allow_full_pool,
            "configured_value_safe": allow_full_pool,
            "effective_value_safe": False,
            "mode_gate": "live_full_future_authorization",
            "automation_effective": False,
            "inactive_reason": "live_full_reserved_requires_separate_authorization",
            "default_value_safe": False,
            "allowed_values": [False, True],
            "raw_value_exposed": False,
            "live_full_reserved": True,
            "full_pool_on_open_allowed": False,
            "source": full_pool_source,
            "contains_secret": False,
        },
    ]
    runtime_mode_policy_rows = _runtime_mode_policy_rows(active_mode)
    runtime_mode_config_contract = get_command_center_runtime_mode_config_contract()
    safe_config_contract = {
        "schema_version": "command_center_bootstrap_safe_config_contract.v1",
        "status": "safe_config_visible_invalid_values_redacted"
        if (
            mode_raw_redacted
            or deepseek_model_redacted
            or external_execution_profile_raw_redacted
            or live_light_research_scope_raw_redacted
        )
        else "safe_config_visible",
        "mode": active_mode,
        "config_row_count": len(config_rows),
        "runtime_mode_vocab_source": "config.COMMAND_CENTER_RUNTIME_MODES",
        "runtime_mode_policy_source": "config.COMMAND_CENTER_RUNTIME_MODE_POLICIES",
        "runtime_mode_policy_row_count": len(runtime_mode_policy_rows),
        "runtime_mode_policy_rows_visible": True,
        "runtime_mode_config_contract_visible": True,
        "runtime_mode_config_evidence_factory_name": runtime_mode_config_contract.get("evidence_factory_name"),
        "runtime_mode_config_evidence_factory_rule": runtime_mode_config_contract.get("evidence_factory_rule"),
        "runtime_mode_config_current_acceptance_scope": runtime_mode_config_contract.get("current_acceptance_scope"),
        "runtime_mode_config_current_acceptance_rule": runtime_mode_config_contract.get("current_acceptance_rule"),
        "runtime_mode_config_current_acceptance_excludes": list(
            runtime_mode_config_contract.get("current_acceptance_excludes", [])
        ),
        "allowed_modes": list(BOOTSTRAP_MODES),
        "default_mode_source": "config.COMMAND_CENTER_DEFAULT_RUNTIME_MODE",
        "default_mode": DEFAULT_MODE,
        "mode_value_valid": mode_valid,
        "mode_raw_value_safe": configured_mode_raw_safe,
        "mode_raw_invalid_value_redacted": mode_raw_redacted,
        "invalid_mode_defaults_to_cache_only": not mode_valid and active_mode == DEFAULT_MODE,
        "raw_config_values_exposed": False,
        "secret_like_model_value_redacted": deepseek_model_redacted,
        "token_key_exposure_allowed": False,
        "config_values_are_safe_only": True,
        "config_rows_frontend_visible": True,
        "config_rows_frontend_display_policy": "safe_value_only",
        "config_rows_frontend_editable": False,
        "config_rows_frontend_writeback_allowed": False,
        "status_endpoint_writeback_allowed": False,
        "config_source_of_truth": "server_config_layer",
        "config_change_channel": "server_config_layer_only",
        "config_rows_are_operator_guidance_not_controls": True,
        "configured_source_switches_visible": True,
        "effective_source_switches_mode_gated": True,
        "effective_tushare_on_open": effective_tushare_on_open,
        "effective_deepseek_on_open": effective_deepseek_on_open,
        "configured_search_submit_autostart": search_submit_autostart_on_submit,
        "effective_search_submit_autostart": effective_search_submit_autostart,
        "search_submit_autostart_requires_live_light": True,
        "search_submit_autostart_creates_local_projection_task_only": True,
        "search_submit_autostart_calls_provider_model": False,
        "configured_startup_autostart": startup_autostart_configured,
        "effective_startup_autostart": effective_startup_autostart,
        "startup_autostart_requires_live_light": True,
        "startup_autostart_requires_sources_enabled": True,
        "startup_autostart_creates_local_task_only": True,
        "startup_autostart_calls_provider_model": False,
        "configured_external_execution_profile": external_execution_profile_configured,
        "effective_external_execution_profile": effective_external_execution_profile,
        "external_execution_profile_vocab_source": "config.COMMAND_CENTER_EXTERNAL_EXECUTION_PROFILES",
        "external_execution_profile_default_source": "config.COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE",
        "external_execution_profile_valid": external_execution_profile_valid,
        "external_execution_profile_invalid_value_redacted": external_execution_profile_raw_redacted,
        "external_execution_profile_requires_live_light": True,
        "external_execution_profile_requires_sources_enabled": True,
        "external_execution_profile_provider_stage_allowed": external_execution_profile_provider_stage_allowed,
        "external_execution_profile_model_stage_allowed": external_execution_profile_model_stage_allowed,
        "external_execution_profile_executor_implemented": False,
        "external_execution_profile_calls_provider_model_now": False,
        "external_execution_profile_requires_post_task_worker_or_local_fallback": True,
        "external_execution_profile_requires_call_ledger": True,
        "external_execution_profile_requires_model_ledger_for_deepseek": (
            effective_external_execution_profile == "light_provider_model"
        ),
        "configured_live_light_research_scope": live_light_research_scope_configured,
        "effective_live_light_research_scope": effective_live_light_research_scope,
        "live_light_research_scope_vocab_source": "config.COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPES",
        "live_light_research_scope_default_source": "config.COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE",
        "live_light_research_scope_valid": live_light_research_scope_valid,
        "live_light_research_scope_invalid_value_redacted": live_light_research_scope_raw_redacted,
        "live_light_research_scope_requires_live_light": True,
        "live_light_research_scope_requires_sources_enabled": True,
        "live_light_research_scope_provider_stage_allowed": live_light_research_scope_provider_stage_allowed,
        "live_light_research_scope_factor_light_allowed": live_light_research_scope_factor_light_allowed,
        "live_light_research_scope_next_session_cache_allowed": live_light_research_scope_next_session_allowed,
        "live_light_research_scope_model_stage_allowed": live_light_research_scope_model_stage_allowed,
        "live_light_research_scope_creates_task": False,
        "live_light_research_scope_creates_provider_model_task": False,
        "live_light_research_scope_calls_provider_model_now": False,
        "live_light_research_scope_local_compute_executes_now": False,
        "live_light_research_scope_is_production_evidence": False,
        "configured_provider_model_enablement": provider_model_enablement_configured,
        "effective_provider_model_enablement": effective_provider_model_enablement,
        "provider_model_enablement_requires_live_light": True,
        "provider_model_enablement_requires_execution_request": True,
        "provider_model_enablement_requires_promotion": True,
        "provider_model_enablement_creates_task": False,
        "provider_model_enablement_creates_provider_model_task": False,
        "provider_model_enablement_calls_provider_model_now": False,
        "provider_model_enablement_frontend_writeback_allowed": False,
        "configured_frontend_enablement": frontend_enablement_configured,
        "effective_frontend_enablement": effective_frontend_enablement,
        "frontend_enablement_requires_live_light": True,
        "frontend_enablement_requires_promotion": True,
        "frontend_enablement_creates_task": False,
        "frontend_enablement_frontend_writeback_allowed": False,
        "effective_sources_enabled": effective_tushare_on_open or effective_deepseek_on_open,
        "source_switch_mode_gate": "live_light",
        "manual_or_cache_only_switches_do_not_autostart": active_mode != "live_light",
        "non_live_light_switches_do_not_autostart": active_mode != "live_light",
        "cache_only_switches_do_not_autostart": active_mode == "cache_only",
        "cache_get_creates_task": False,
        "cache_get_external_calls": False,
        "fastapi_startup_external_calls": False,
        "react_render_direct_provider_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    runtime_config_reference_contract = _bootstrap_runtime_config_reference_contract(
        active_mode=active_mode,
        config_rows=config_rows,
    )
    runtime_mode_acceptance_contract = _runtime_mode_acceptance_contract(active_mode)
    live_light_rollout_roadmap_contract = _live_light_rollout_roadmap_contract(active_mode)
    task_creation_invariant_contract = _task_creation_invariant_contract(
        active_mode=active_mode,
        effective_search_submit_autostart=effective_search_submit_autostart,
        live_light_sources_enabled=live_light_sources_enabled,
    )
    runtime_external_silence_contract = _runtime_external_silence_contract(
        active_mode=active_mode,
        task_creation_invariant_contract=task_creation_invariant_contract,
    )
    provider_linkage_rows = _provider_linkage_rows(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        live_light_sources_enabled=live_light_sources_enabled,
        tushare_on_open=tushare_on_open,
        deepseek_on_open=deepseek_on_open,
        symbol_limit=symbol_limit,
        rate_limit_seconds=rate_limit_seconds,
        deepseek_model=deepseek_model,
    )
    activation_receipt, activation_rows = _live_light_activation_receipt(
        active_mode=active_mode,
        mode_valid=mode_valid,
        live_light_enabled=live_light_enabled,
        live_light_sources_enabled=live_light_sources_enabled,
        tushare_on_open=tushare_on_open,
        deepseek_on_open=deepseek_on_open,
        symbol_limit=symbol_limit,
        rate_limit_seconds=rate_limit_seconds,
        provider_linkage_rows=provider_linkage_rows,
    )
    acceptance_runbook, acceptance_rows = _live_light_provider_model_acceptance_runbook(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        tushare_on_open=tushare_on_open,
        deepseek_on_open=deepseek_on_open,
        symbol_limit=symbol_limit,
        rate_limit_seconds=rate_limit_seconds,
        deepseek_model=deepseek_model,
        activation_receipt=activation_receipt,
    )
    background_task_contract = _live_light_background_task_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        startup_autostart_configured=startup_autostart_configured,
        effective_startup_autostart=effective_startup_autostart,
        live_light_sources_enabled=live_light_sources_enabled,
        tushare_on_open=tushare_on_open,
        deepseek_on_open=deepseek_on_open,
        symbol_limit=symbol_limit,
        rate_limit_seconds=rate_limit_seconds,
    )
    live_light_scope_intake_contract = _live_light_scope_intake_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        symbol_limit=symbol_limit,
    )
    live_light_stage_dependency_contract = _live_light_stage_dependency_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        live_light_sources_enabled=live_light_sources_enabled,
        tushare_on_open=tushare_on_open,
        deepseek_on_open=deepseek_on_open,
    )
    live_light_freshness_provider_gap_contract = _live_light_freshness_provider_gap_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    live_light_task_lifecycle_contract = _live_light_task_lifecycle_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        rate_limit_seconds=rate_limit_seconds,
    )
    live_light_task_queue_budget_contract = _live_light_task_queue_budget_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        startup_autostart_effective=effective_startup_autostart,
        rate_limit_seconds=rate_limit_seconds,
        symbol_limit=symbol_limit,
        background_task_contract=background_task_contract,
        task_lifecycle_contract=live_light_task_lifecycle_contract,
    )
    live_light_task_control_contract = _live_light_task_control_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    live_light_operator_status_contract = _live_light_operator_status_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        live_light_sources_enabled=live_light_sources_enabled,
        tushare_on_open=tushare_on_open,
        deepseek_on_open=deepseek_on_open,
        external_execution_profile=effective_external_execution_profile,
        external_execution_profile_provider_stage_allowed=external_execution_profile_provider_stage_allowed,
        external_execution_profile_model_stage_allowed=external_execution_profile_model_stage_allowed,
        symbol_limit=symbol_limit,
        rate_limit_seconds=rate_limit_seconds,
    )
    live_light_promotion_gate_contract = _live_light_promotion_gate_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        live_light_sources_enabled=live_light_sources_enabled,
        symbol_limit=symbol_limit,
        rate_limit_seconds=rate_limit_seconds,
    )
    live_light_worker_dispatch_contract = _live_light_worker_dispatch_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        live_light_sources_enabled=live_light_sources_enabled,
    )
    search_quant_projection_contract = _search_quant_projection_workflow_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        symbol_limit=symbol_limit,
        rate_limit_seconds=rate_limit_seconds,
    )
    search_quant_projection_submit_autostart_contract = _search_quant_projection_submit_autostart_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        search_submit_autostart_on_submit=search_submit_autostart_on_submit,
        search_submit_autostart_source=search_submit_autostart_source,
        symbol_limit=symbol_limit,
        rate_limit_seconds=rate_limit_seconds,
    )
    search_quant_projection_submit_autostart_config_handoff_contract = (
        _search_quant_projection_submit_autostart_config_handoff_contract(
            active_mode=active_mode,
            configured_submit_autostart=search_submit_autostart_on_submit,
            effective_submit_autostart=effective_search_submit_autostart,
            source=search_submit_autostart_source,
        )
    )
    search_quant_projection_submit_autostart_config_promotion_contract = (
        _search_quant_projection_submit_autostart_config_promotion_contract(
            config_handoff_contract=search_quant_projection_submit_autostart_config_handoff_contract,
        )
    )
    runtime_config_ownership_invariant_contract = _runtime_config_ownership_invariant_contract(
        active_mode=active_mode,
        runtime_config_reference_contract=runtime_config_reference_contract,
        search_submit_config_handoff_contract=search_quant_projection_submit_autostart_config_handoff_contract,
        search_submit_config_promotion_contract=search_quant_projection_submit_autostart_config_promotion_contract,
    )
    search_quant_projection_frontend_wiring_acceptance_contract = (
        _search_quant_projection_frontend_wiring_acceptance_contract(
            active_mode=active_mode,
            live_light_enabled=live_light_enabled,
            search_submit_autostart_on_submit=search_submit_autostart_on_submit,
            symbol_limit=symbol_limit,
            rate_limit_seconds=rate_limit_seconds,
        )
    )
    search_quant_projection_result_surface_contract = _search_quant_projection_result_surface_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    search_quant_projection_factor_next_handoff_contract = (
        _search_quant_projection_factor_next_handoff_contract(
            active_mode=active_mode,
            live_light_enabled=live_light_enabled,
        )
    )
    search_quant_projection_cache_write_preflight_contract = (
        _search_quant_projection_cache_write_preflight_contract(
            active_mode=active_mode,
            live_light_enabled=live_light_enabled,
            factor_next_handoff_contract=search_quant_projection_factor_next_handoff_contract,
        )
    )
    search_quant_projection_deepseek_model_preflight_contract = (
        _search_quant_projection_deepseek_model_preflight_contract(
            active_mode=active_mode,
            live_light_enabled=live_light_enabled,
            deepseek_on_open=deepseek_on_open,
            deepseek_model=deepseek_model,
            cache_write_preflight_contract=search_quant_projection_cache_write_preflight_contract,
        )
    )
    search_quant_projection_deepseek_output_acceptance_contract = (
        _search_quant_projection_deepseek_output_acceptance_contract(
            active_mode=active_mode,
            live_light_enabled=live_light_enabled,
            deepseek_on_open=deepseek_on_open,
            deepseek_model=deepseek_model,
            deepseek_model_preflight_contract=search_quant_projection_deepseek_model_preflight_contract,
        )
    )
    search_quant_projection_deepseek_readiness_contract = (
        _search_quant_projection_deepseek_readiness_contract(
            active_mode=active_mode,
            live_light_enabled=live_light_enabled,
            deepseek_on_open=deepseek_on_open,
            deepseek_model=deepseek_model,
        )
    )
    search_quant_projection_latest_status = _latest_search_quant_projection_status_surface()
    search_quant_projection_provider_model_latest_status = (
        _latest_search_quant_projection_provider_model_status_surface()
    )
    tushare_light_strategy_contract = _tushare_light_strategy_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        live_light_sources_enabled=live_light_sources_enabled,
        tushare_on_open=tushare_on_open,
        symbol_limit=symbol_limit,
    )
    deepseek_pro_strategy_contract = _deepseek_pro_strategy_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        live_light_sources_enabled=live_light_sources_enabled,
        deepseek_on_open=deepseek_on_open,
        deepseek_model=deepseek_model,
    )
    ui_nonblocking_runtime_contract = _ui_nonblocking_runtime_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        rate_limit_seconds=rate_limit_seconds,
    )
    live_light_local_fallback_contract = _live_light_local_fallback_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    live_light_cache_lineage_contract = _live_light_cache_lineage_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    live_light_output_surface_contract = _live_light_output_surface_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    live_light_runtime_budget_contract = _live_light_runtime_budget_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        symbol_limit=symbol_limit,
        rate_limit_seconds=rate_limit_seconds,
    )
    live_light_evidence_grade_contract = _live_light_evidence_grade_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    live_light_credential_preflight_contract = _live_light_credential_preflight_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    live_light_provider_model_execution_request_contract = _live_light_provider_model_execution_request_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    live_light_execution_request_handoff_contract = _live_light_execution_request_handoff_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    live_light_latest_bootstrap_task_status = _latest_live_bootstrap_task_status_surface()
    live_light_latest_acceptance_dry_run_status = _latest_acceptance_dry_run_status_surface()
    live_light_latest_execution_request_status = _latest_execution_request_status_surface()
    live_light_ledger_contract = _live_light_ledger_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    live_light_ledger_redaction_invariant_contract = _live_light_ledger_redaction_invariant_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
    )
    runtime_hard_boundary_contract = _runtime_hard_boundary_contract(
        active_mode=active_mode,
        runtime_mode_acceptance_contract=runtime_mode_acceptance_contract,
        task_creation_invariant_contract=task_creation_invariant_contract,
        runtime_external_silence_contract=runtime_external_silence_contract,
        live_light_ledger_contract=live_light_ledger_contract,
        live_light_ledger_redaction_invariant_contract=live_light_ledger_redaction_invariant_contract,
        live_light_evidence_grade_contract=live_light_evidence_grade_contract,
        deepseek_pro_strategy_contract=deepseek_pro_strategy_contract,
        search_quant_projection_contract=search_quant_projection_contract,
    )
    live_full_reserved_contract = _live_full_reserved_contract(
        active_mode=active_mode,
        allow_full_pool=allow_full_pool,
    )
    runtime_operator_summary_contract = _runtime_operator_summary_contract(
        active_mode=active_mode,
        safe_config_contract=safe_config_contract,
        runtime_config_ownership_invariant_contract=runtime_config_ownership_invariant_contract,
        runtime_mode_acceptance_contract=runtime_mode_acceptance_contract,
        task_creation_invariant_contract=task_creation_invariant_contract,
        live_light_task_control_contract=live_light_task_control_contract,
        live_light_operator_status_contract=live_light_operator_status_contract,
        live_light_execution_request_handoff_contract=live_light_execution_request_handoff_contract,
        live_light_promotion_gate_contract=live_light_promotion_gate_contract,
        runtime_hard_boundary_contract=runtime_hard_boundary_contract,
        latest_bootstrap_task_status=live_light_latest_bootstrap_task_status,
        latest_acceptance_dry_run_status=live_light_latest_acceptance_dry_run_status,
        latest_execution_request_status=live_light_latest_execution_request_status,
        latest_quant_projection_status=search_quant_projection_latest_status,
    )
    runtime_cache_first_polling_contract = _runtime_cache_first_polling_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        effective_search_submit_autostart=effective_search_submit_autostart,
        rate_limit_seconds=rate_limit_seconds,
        external_silence_contract=runtime_external_silence_contract,
        operator_summary_contract=runtime_operator_summary_contract,
        frontend_wiring_contract=search_quant_projection_frontend_wiring_acceptance_contract,
    )
    runtime_operator_summary_contract.update(
        {
            "cache_first_polling_summary_visible": True,
            "cache_first_polling_source_contract": "runtime_cache_first_polling_contract",
            "cache_first_polling_schema_version": runtime_cache_first_polling_contract.get(
                "schema_version"
            ),
            "cache_first_polling_phase_count": runtime_cache_first_polling_contract.get("phase_count"),
            "cache_first_polling_cache_first_render_required": (
                runtime_cache_first_polling_contract.get("cache_first_render_required") is True
            ),
            "cache_first_polling_task_polling_required": (
                runtime_cache_first_polling_contract.get("polling_required") is True
            ),
            "cache_first_polling_success_refresh_required": (
                runtime_cache_first_polling_contract.get("success_refreshes_cache_and_status") is True
            ),
            "cache_first_polling_last_good_cache_required": (
                runtime_cache_first_polling_contract.get("failure_recovery_keeps_last_good_cache") is True
            ),
            "cache_first_polling_manual_retry_only_after_failure": (
                runtime_cache_first_polling_contract.get("manual_retry_only_after_failure") is True
            ),
            "cache_first_polling_task_creation_allowed_phase_count": (
                runtime_cache_first_polling_contract.get("task_creation_allowed_phase_count")
            ),
            "cache_first_polling_direct_external_call_allowed_phase_count": (
                runtime_cache_first_polling_contract.get("direct_external_call_allowed_phase_count")
            ),
            "cache_first_polling_browser_evidence_complete": (
                runtime_cache_first_polling_contract.get("browser_runtime_evidence_complete") is True
            ),
            "cache_first_polling_summary_is_production_evidence": False,
        }
    )
    live_light_startup_autostart_readiness_contract = _live_light_startup_autostart_readiness_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        live_light_sources_enabled=live_light_sources_enabled,
        background_task_contract=background_task_contract,
        cache_first_polling_contract=runtime_cache_first_polling_contract,
    )
    live_light_unified_startup_task_contract = _live_light_unified_startup_task_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        live_light_sources_enabled=live_light_sources_enabled,
        tushare_on_open=tushare_on_open,
        deepseek_on_open=deepseek_on_open,
        external_execution_profile=effective_external_execution_profile,
        external_execution_profile_provider_stage_allowed=external_execution_profile_provider_stage_allowed,
        external_execution_profile_model_stage_allowed=external_execution_profile_model_stage_allowed,
        symbol_limit=symbol_limit,
        rate_limit_seconds=rate_limit_seconds,
        deepseek_model=deepseek_model,
        background_task_contract=background_task_contract,
        stage_dependency_contract=live_light_stage_dependency_contract,
        worker_dispatch_contract=live_light_worker_dispatch_contract,
        startup_readiness_contract=live_light_startup_autostart_readiness_contract,
    )
    search_quant_projection_unified_startup_handoff_contract = (
        _search_quant_projection_unified_startup_handoff_contract(
            active_mode=active_mode,
            live_light_enabled=live_light_enabled,
            search_submit_autostart_contract=search_quant_projection_submit_autostart_contract,
            search_quant_projection_contract=search_quant_projection_contract,
            frontend_wiring_contract=search_quant_projection_frontend_wiring_acceptance_contract,
            unified_startup_task_contract=live_light_unified_startup_task_contract,
        )
    )
    runtime_frontend_enablement_gate_contract = _runtime_frontend_enablement_gate_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        rollout_roadmap_contract=live_light_rollout_roadmap_contract,
        cache_first_polling_contract=runtime_cache_first_polling_contract,
        frontend_wiring_contract=search_quant_projection_frontend_wiring_acceptance_contract,
        external_silence_contract=runtime_external_silence_contract,
    )
    runtime_browser_evidence_contract = _runtime_browser_evidence_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        frontend_enablement_gate_contract=runtime_frontend_enablement_gate_contract,
        cache_first_polling_contract=runtime_cache_first_polling_contract,
        frontend_wiring_contract=search_quant_projection_frontend_wiring_acceptance_contract,
        external_silence_contract=runtime_external_silence_contract,
    )
    runtime_frontend_wiring_manifest_contract = _runtime_frontend_wiring_manifest_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        frontend_enablement_gate_contract=runtime_frontend_enablement_gate_contract,
        browser_evidence_contract=runtime_browser_evidence_contract,
        cache_first_polling_contract=runtime_cache_first_polling_contract,
        frontend_wiring_contract=search_quant_projection_frontend_wiring_acceptance_contract,
    )
    runtime_frontend_acceptance_runbook_contract = _runtime_frontend_acceptance_runbook_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        frontend_enablement_gate_contract=runtime_frontend_enablement_gate_contract,
        browser_evidence_contract=runtime_browser_evidence_contract,
        frontend_wiring_manifest_contract=runtime_frontend_wiring_manifest_contract,
    )
    runtime_frontend_acceptance_artifact_contract = _runtime_frontend_acceptance_artifact_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        frontend_acceptance_runbook_contract=runtime_frontend_acceptance_runbook_contract,
        browser_evidence_contract=runtime_browser_evidence_contract,
    )
    runtime_frontend_enablement_promotion_contract = _runtime_frontend_enablement_promotion_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        frontend_enablement_gate_contract=runtime_frontend_enablement_gate_contract,
        browser_evidence_contract=runtime_browser_evidence_contract,
        frontend_wiring_manifest_contract=runtime_frontend_wiring_manifest_contract,
        frontend_acceptance_runbook_contract=runtime_frontend_acceptance_runbook_contract,
        frontend_acceptance_artifact_contract=runtime_frontend_acceptance_artifact_contract,
    )
    runtime_frontend_enablement_release_switch_contract = _runtime_frontend_enablement_release_switch_contract(
        active_mode=active_mode,
        live_light_enabled=live_light_enabled,
        frontend_enablement_configured=frontend_enablement_configured,
        frontend_enablement_promotion_contract=runtime_frontend_enablement_promotion_contract,
    )
    runtime_frontend_enablement_config_promotion_contract = (
        _runtime_frontend_enablement_config_promotion_contract(
            active_mode=active_mode,
            live_light_enabled=live_light_enabled,
            frontend_enablement_configured=frontend_enablement_configured,
            runtime_config_ownership_invariant_contract=runtime_config_ownership_invariant_contract,
            frontend_enablement_release_switch_contract=runtime_frontend_enablement_release_switch_contract,
        )
    )

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "activation_receipt_schema_version": BOOTSTRAP_ACTIVATION_RECEIPT_SCHEMA_VERSION,
        "acceptance_runbook_schema_version": BOOTSTRAP_ACCEPTANCE_RUNBOOK_SCHEMA_VERSION,
        "status": status,
        "mode": active_mode,
        "cache_only": active_mode == "cache_only",
        "read_only": True,
        "loaded_at": loaded_at,
        "summary": "Runtime mode cache is read-only. It makes cache_only/manual/live_light/live_full boundaries visible without creating tasks or calling providers. The live_light POST route is implemented as a local task skeleton only.",
        "configured_mode_raw": configured_mode_raw_safe,
        "configured_mode_raw_safe": configured_mode_raw_safe,
        "configured_mode_valid": mode_valid,
        "configured_mode_invalid_raw_redacted": mode_raw_redacted,
        "safe_config_contract": safe_config_contract,
        "mode_rows": [_mode_row(mode, active_mode) for mode in BOOTSTRAP_MODES],
        "runtime_mode_policy_rows": runtime_mode_policy_rows,
        "config_rows": config_rows,
        "runtime_config_reference_contract": runtime_config_reference_contract,
        "runtime_config_ownership_invariant_contract": runtime_config_ownership_invariant_contract,
        "runtime_operator_summary_contract": runtime_operator_summary_contract,
        "runtime_cache_first_polling_contract": runtime_cache_first_polling_contract,
        "runtime_frontend_enablement_gate_contract": runtime_frontend_enablement_gate_contract,
        "runtime_browser_evidence_contract": runtime_browser_evidence_contract,
        "runtime_frontend_wiring_manifest_contract": runtime_frontend_wiring_manifest_contract,
        "runtime_frontend_acceptance_runbook_contract": runtime_frontend_acceptance_runbook_contract,
        "runtime_frontend_acceptance_artifact_contract": runtime_frontend_acceptance_artifact_contract,
        "runtime_frontend_enablement_promotion_contract": runtime_frontend_enablement_promotion_contract,
        "runtime_frontend_enablement_release_switch_contract": runtime_frontend_enablement_release_switch_contract,
        "runtime_frontend_enablement_config_promotion_contract": (
            runtime_frontend_enablement_config_promotion_contract
        ),
        "runtime_mode_acceptance_contract": runtime_mode_acceptance_contract,
        "live_light_rollout_roadmap_contract": live_light_rollout_roadmap_contract,
        "task_creation_invariant_contract": task_creation_invariant_contract,
        "runtime_external_silence_contract": runtime_external_silence_contract,
        "runtime_hard_boundary_contract": runtime_hard_boundary_contract,
        "provider_linkage_schema_version": BOOTSTRAP_PROVIDER_LINKAGE_SCHEMA_VERSION,
        "provider_linkage_rows": provider_linkage_rows,
        "live_light_activation_receipt": activation_receipt,
        "live_light_activation_rows": activation_rows,
        "live_light_provider_model_acceptance_runbook": acceptance_runbook,
        "live_light_provider_model_acceptance_rows": acceptance_rows,
        "live_light_background_task_contract": background_task_contract,
        "live_light_startup_autostart_readiness_contract": live_light_startup_autostart_readiness_contract,
        "live_light_unified_startup_task_contract": live_light_unified_startup_task_contract,
        "live_light_scope_intake_contract": live_light_scope_intake_contract,
        "live_light_stage_dependency_contract": live_light_stage_dependency_contract,
        "live_light_freshness_provider_gap_contract": live_light_freshness_provider_gap_contract,
        "live_light_task_lifecycle_contract": live_light_task_lifecycle_contract,
        "live_light_task_queue_budget_contract": live_light_task_queue_budget_contract,
        "live_light_task_control_contract": live_light_task_control_contract,
        "live_light_operator_status_contract": live_light_operator_status_contract,
        "live_light_promotion_gate_contract": live_light_promotion_gate_contract,
        "live_light_worker_dispatch_contract": live_light_worker_dispatch_contract,
        "search_quant_projection_workflow_contract": search_quant_projection_contract,
        "search_quant_projection_submit_autostart_contract": search_quant_projection_submit_autostart_contract,
        "search_quant_projection_submit_autostart_config_handoff_contract": (
            search_quant_projection_submit_autostart_config_handoff_contract
        ),
        "search_quant_projection_submit_autostart_config_promotion_contract": (
            search_quant_projection_submit_autostart_config_promotion_contract
        ),
        "search_quant_projection_frontend_wiring_acceptance_contract": (
            search_quant_projection_frontend_wiring_acceptance_contract
        ),
        "search_quant_projection_unified_startup_handoff_contract": (
            search_quant_projection_unified_startup_handoff_contract
        ),
        "search_quant_projection_result_surface_contract": search_quant_projection_result_surface_contract,
        "search_quant_projection_factor_next_handoff_contract": (
            search_quant_projection_factor_next_handoff_contract
        ),
        "search_quant_projection_cache_write_preflight_contract": (
            search_quant_projection_cache_write_preflight_contract
        ),
        "search_quant_projection_deepseek_model_preflight_contract": (
            search_quant_projection_deepseek_model_preflight_contract
        ),
        "search_quant_projection_deepseek_output_acceptance_contract": (
            search_quant_projection_deepseek_output_acceptance_contract
        ),
        "search_quant_projection_deepseek_readiness_contract": (
            search_quant_projection_deepseek_readiness_contract
        ),
        "search_quant_projection_latest_status": search_quant_projection_latest_status,
        "search_quant_projection_provider_model_latest_status": search_quant_projection_provider_model_latest_status,
        "tushare_light_strategy_contract": tushare_light_strategy_contract,
        "deepseek_pro_strategy_contract": deepseek_pro_strategy_contract,
        "ui_nonblocking_runtime_contract": ui_nonblocking_runtime_contract,
        "live_light_local_fallback_contract": live_light_local_fallback_contract,
        "live_light_cache_lineage_contract": live_light_cache_lineage_contract,
        "live_light_output_surface_contract": live_light_output_surface_contract,
        "live_light_runtime_budget_contract": live_light_runtime_budget_contract,
        "live_light_evidence_grade_contract": live_light_evidence_grade_contract,
        "live_light_credential_preflight_contract": live_light_credential_preflight_contract,
        "live_light_provider_model_execution_request_contract": live_light_provider_model_execution_request_contract,
        "live_light_execution_request_handoff_contract": live_light_execution_request_handoff_contract,
        "live_light_latest_bootstrap_task_status": live_light_latest_bootstrap_task_status,
        "live_light_latest_acceptance_dry_run_status": live_light_latest_acceptance_dry_run_status,
        "live_light_latest_execution_request_status": live_light_latest_execution_request_status,
        "live_light_ledger_contract": live_light_ledger_contract,
        "live_light_ledger_redaction_invariant_contract": live_light_ledger_redaction_invariant_contract,
        "live_full_reserved_contract": live_full_reserved_contract,
        "live_light": {
            "enabled": live_light_enabled,
            "tushare_on_open": tushare_on_open if live_light_enabled else False,
            "deepseek_on_open": deepseek_on_open if live_light_enabled else False,
            "sources_enabled": live_light_sources_enabled,
            "symbol_limit": symbol_limit,
            "rate_limit_seconds": rate_limit_seconds,
            "external_execution_profile": effective_external_execution_profile,
            "external_execution_profile_provider_stage_allowed": external_execution_profile_provider_stage_allowed,
            "external_execution_profile_model_stage_allowed": external_execution_profile_model_stage_allowed,
            "external_execution_profile_executor_implemented": False,
            "external_execution_profile_calls_provider_model_now": False,
            "profile_source_rate_summary_visible": True,
            "deepseek_model": deepseek_model,
            "allow_full_pool": allow_full_pool,
            "initial_cache_render_required": True,
            "post_task_required": True,
            "status_route": BOOTSTRAP_STATUS_ROUTE,
            "planned_task_route": PLANNED_BOOTSTRAP_TASK_ROUTE,
            "task_type": BOOTSTRAP_TASK_TYPE,
            "output_packet_key": BOOTSTRAP_TASK_PACKET_KEY,
            "default_light_tushare_apis": list(DEFAULT_LIGHT_TUSHARE_APIS),
            "bootstrap_task_implemented": True,
            "local_task_skeleton_implemented": True,
            "bootstrap_plan_skeleton_implemented": True,
            "model_ledger_preview_implemented": True,
            "provider_linkage_rows_visible": True,
            "activation_receipt_visible": True,
            "provider_model_acceptance_runbook_visible": True,
            "background_task_contract_visible": True,
            "startup_autostart_readiness_contract_visible": True,
            "startup_autostart_readiness_row_count": (
                live_light_startup_autostart_readiness_contract["readiness_row_count"]
            ),
            "startup_autostart_frontend_wiring_implemented": False,
            "startup_autostart_effective_allowed": False,
            "startup_autostart_readiness_is_production_evidence": False,
            "unified_startup_task_contract_visible": True,
            "unified_startup_task_stage_count": live_light_unified_startup_task_contract["stage_count"],
            "unified_startup_task_route": live_light_unified_startup_task_contract["task_route"],
            "unified_startup_task_provider_execution_implemented": False,
            "unified_startup_task_model_execution_implemented": False,
            "unified_startup_task_worker_dispatch_implemented": False,
            "unified_startup_task_is_production_evidence": False,
            "runtime_config_reference_contract_visible": True,
            "runtime_config_reference_row_count": runtime_config_reference_contract["config_reference_row_count"],
            "runtime_config_reference_source_switch_count": runtime_config_reference_contract["source_switch_count"],
            "runtime_config_reference_audit_id": runtime_config_reference_contract["config_audit_id"],
            "runtime_config_reference_audit_uses_safe_rows_only": True,
            "runtime_config_reference_is_production_evidence": False,
            "runtime_mode_policy_rows_visible": True,
            "runtime_mode_policy_source": "config.COMMAND_CENTER_RUNTIME_MODE_POLICIES",
            "runtime_mode_policy_row_count": len(runtime_mode_policy_rows),
            "runtime_mode_policy_is_production_evidence": False,
            "runtime_config_ownership_invariant_contract_visible": True,
            "runtime_config_ownership_row_count": runtime_config_ownership_invariant_contract[
                "ownership_row_count"
            ],
            "runtime_config_ownership_audit_id": runtime_config_ownership_invariant_contract["ownership_audit_id"],
            "runtime_config_ownership_linked_reference_audit_id": runtime_config_ownership_invariant_contract[
                "linked_runtime_config_reference_audit_id"
            ],
            "runtime_config_bootstrap_local_env_fallback_count": (
                runtime_config_ownership_invariant_contract["bootstrap_local_env_fallback_count"]
            ),
            "runtime_config_global_config_allowlist_promotion_pending_count": (
                runtime_config_ownership_invariant_contract[
                    "global_config_allowlist_promotion_pending_count"
                ]
            ),
            "runtime_config_frontend_writeback_allowed": False,
            "runtime_config_production_config_complete": False,
            "runtime_config_ownership_invariant_is_production_evidence": False,
            "runtime_operator_summary_contract_visible": True,
            "runtime_operator_active_mode": runtime_operator_summary_contract["mode"],
            "runtime_operator_active_display_status": runtime_operator_summary_contract["active_mode_display_status"],
            "runtime_operator_release_blocker_summary_visible": True,
            "runtime_operator_release_remote_ci_status_known": runtime_operator_summary_contract[
                "release_remote_ci_status_known"
            ],
            "runtime_operator_release_remote_ci_green": runtime_operator_summary_contract[
                "release_remote_ci_green"
            ],
            "runtime_operator_release_github_api_called": runtime_operator_summary_contract[
                "release_github_api_called"
            ],
            "runtime_operator_release_fresh_local_gate_run_required": runtime_operator_summary_contract[
                "release_fresh_local_gate_run_required"
            ],
            "runtime_operator_release_production_promotion_review_required": runtime_operator_summary_contract[
                "release_production_promotion_review_required"
            ],
            "runtime_operator_release_ready_for_promotion": runtime_operator_summary_contract[
                "release_ready_for_promotion"
            ],
            "runtime_operator_release_local_contracts_are_production_evidence": runtime_operator_summary_contract[
                "release_local_contracts_are_production_evidence"
            ],
            "runtime_operator_release_blocker_summary_is_production_evidence": False,
            "runtime_operator_trigger_policy_summary_visible": True,
            "runtime_operator_active_page_open_task_allowed": runtime_operator_summary_contract[
                "active_page_open_task_allowed"
            ],
            "runtime_operator_active_search_submit_task_allowed": runtime_operator_summary_contract[
                "active_search_submit_task_allowed"
            ],
            "runtime_operator_active_manual_button_task_allowed": runtime_operator_summary_contract[
                "active_manual_button_task_allowed"
            ],
            "runtime_operator_active_live_light_background_task_allowed": runtime_operator_summary_contract[
                "active_live_light_background_task_allowed"
            ],
            "runtime_operator_active_provider_model_execution_allowed": runtime_operator_summary_contract[
                "active_provider_model_execution_allowed"
            ],
            "runtime_operator_active_provider_model_execution_surface": runtime_operator_summary_contract[
                "active_provider_model_execution_surface"
            ],
            "runtime_operator_active_provider_model_direct_execution_allowed": runtime_operator_summary_contract[
                "active_provider_model_direct_execution_allowed"
            ],
            "runtime_operator_active_provider_model_requires_explicit_post_task": (
                runtime_operator_summary_contract["active_provider_model_requires_explicit_post_task"]
            ),
            "runtime_operator_active_provider_model_execution_requires_task_contract": (
                runtime_operator_summary_contract["active_provider_model_execution_requires_task_contract"]
            ),
            "runtime_operator_active_provider_model_execution_requires_execution_request": (
                runtime_operator_summary_contract["active_provider_model_execution_requires_execution_request"]
            ),
            "runtime_operator_active_full_pool_or_deep_scan_allowed": runtime_operator_summary_contract[
                "active_full_pool_or_deep_scan_allowed"
            ],
            "runtime_operator_trigger_policy_summary_is_production_evidence": False,
            "runtime_operator_config_reference_audit_id": runtime_operator_summary_contract[
                "config_reference_audit_id"
            ],
            "runtime_operator_config_ownership_audit_id": runtime_operator_summary_contract[
                "config_ownership_audit_id"
            ],
            "runtime_operator_config_audit_uses_safe_rows_only": True,
            "runtime_operator_external_execution_profile": runtime_operator_summary_contract[
                "effective_external_execution_profile"
            ],
            "runtime_operator_profile_provider_stage_allowed": runtime_operator_summary_contract[
                "external_execution_profile_provider_stage_allowed"
            ],
            "runtime_operator_profile_model_stage_allowed": runtime_operator_summary_contract[
                "external_execution_profile_model_stage_allowed"
            ],
            "runtime_operator_provider_model_enablement_summary_visible": runtime_operator_summary_contract[
                "provider_model_enablement_summary_visible"
            ],
            "runtime_operator_provider_model_enablement_source_config": runtime_operator_summary_contract[
                "provider_model_enablement_source_config"
            ],
            "runtime_operator_provider_model_enablement_configured": runtime_operator_summary_contract[
                "provider_model_enablement_configured"
            ],
            "runtime_operator_provider_model_enablement_effective": runtime_operator_summary_contract[
                "provider_model_enablement_effective"
            ],
            "runtime_operator_provider_model_enablement_requires_live_light": runtime_operator_summary_contract[
                "provider_model_enablement_requires_live_light"
            ],
            "runtime_operator_provider_model_enablement_requires_execution_request": (
                runtime_operator_summary_contract[
                    "provider_model_enablement_requires_execution_request"
                ]
            ),
            "runtime_operator_provider_model_enablement_requires_promotion": runtime_operator_summary_contract[
                "provider_model_enablement_requires_promotion"
            ],
            "runtime_operator_provider_model_enablement_creates_provider_model_task": (
                runtime_operator_summary_contract[
                    "provider_model_enablement_creates_provider_model_task"
                ]
            ),
            "runtime_operator_provider_model_enablement_calls_provider_model_now": (
                runtime_operator_summary_contract["provider_model_enablement_calls_provider_model_now"]
            ),
            "runtime_operator_provider_model_enablement_is_production_evidence": False,
            "runtime_operator_profile_source_rate_summary_visible": True,
            "runtime_operator_profile_source_rate_summary_status": runtime_operator_summary_contract[
                "operator_profile_source_rate_summary_status"
            ],
            "runtime_operator_rate_limit_seconds_visible_safe": runtime_operator_summary_contract[
                "operator_rate_limit_seconds_visible_safe"
            ],
            "runtime_operator_task_control_visible": runtime_operator_summary_contract[
                "task_control_contract_visible"
            ],
            "runtime_operator_task_control_row_count": runtime_operator_summary_contract["task_control_row_count"],
            "runtime_operator_task_control_manual_only": runtime_operator_summary_contract["task_control_manual_only"],
            "runtime_operator_task_control_auto_retry_enabled": runtime_operator_summary_contract[
                "task_control_auto_retry_enabled"
            ],
            "runtime_operator_task_control_is_production_evidence": False,
            "runtime_operator_provider_model_handoff_visible": runtime_operator_summary_contract[
                "provider_model_handoff_contract_visible"
            ],
            "runtime_operator_provider_model_handoff_route_implemented": runtime_operator_summary_contract[
                "provider_model_handoff_route_implemented"
            ],
            "runtime_operator_provider_model_handoff_receipt_service_implemented": (
                runtime_operator_summary_contract["provider_model_handoff_receipt_service_implemented"]
            ),
            "runtime_operator_latest_acceptance_dry_run_receipt_found": runtime_operator_summary_contract[
                "latest_acceptance_dry_run_receipt_found"
            ],
            "runtime_operator_latest_acceptance_dry_run_ready_for_execution_request": (
                runtime_operator_summary_contract["latest_acceptance_dry_run_ready_for_execution_request"]
            ),
            "runtime_operator_latest_execution_request_receipt_found": runtime_operator_summary_contract[
                "latest_execution_request_receipt_found"
            ],
            "runtime_operator_latest_execution_request_ready": runtime_operator_summary_contract[
                "latest_execution_request_ready"
            ],
            "runtime_operator_latest_execution_request_lookup_creates_task": runtime_operator_summary_contract[
                "latest_execution_request_lookup_creates_task"
            ],
            "runtime_operator_provider_model_task_created": runtime_operator_summary_contract[
                "provider_model_task_created"
            ],
            "runtime_operator_provider_model_execution_implemented": runtime_operator_summary_contract[
                "provider_model_execution_implemented"
            ],
            "runtime_operator_provider_model_is_production_evidence": False,
            "runtime_operator_summary_row_count": runtime_operator_summary_contract["summary_row_count"],
            "runtime_operator_allowed_action_count": runtime_operator_summary_contract[
                "allowed_operator_action_count"
            ],
            "runtime_operator_blocked_action_count": runtime_operator_summary_contract[
                "blocked_operator_action_count"
            ],
            "runtime_operator_summary_is_production_evidence": False,
            "runtime_operator_cache_first_polling_summary_visible": runtime_operator_summary_contract[
                "cache_first_polling_summary_visible"
            ],
            "runtime_operator_cache_first_polling_source_contract": runtime_operator_summary_contract[
                "cache_first_polling_source_contract"
            ],
            "runtime_operator_cache_first_polling_phase_count": runtime_operator_summary_contract[
                "cache_first_polling_phase_count"
            ],
            "runtime_operator_cache_first_polling_cache_first_render_required": runtime_operator_summary_contract[
                "cache_first_polling_cache_first_render_required"
            ],
            "runtime_operator_cache_first_polling_task_polling_required": runtime_operator_summary_contract[
                "cache_first_polling_task_polling_required"
            ],
            "runtime_operator_cache_first_polling_last_good_cache_required": runtime_operator_summary_contract[
                "cache_first_polling_last_good_cache_required"
            ],
            "runtime_operator_cache_first_polling_browser_evidence_complete": runtime_operator_summary_contract[
                "cache_first_polling_browser_evidence_complete"
            ],
            "runtime_operator_cache_first_polling_summary_is_production_evidence": False,
            "runtime_external_silence_contract_visible": True,
            "runtime_external_silence_row_count": runtime_external_silence_contract["silence_row_count"],
            "runtime_external_silence_local_post_exception_count": runtime_external_silence_contract[
                "local_post_exception_count"
            ],
            "runtime_external_silence_direct_external_call_allowed_count": (
                runtime_external_silence_contract["direct_external_call_allowed_count"]
            ),
            "runtime_external_silence_is_production_evidence": False,
            "runtime_hard_boundary_contract_visible": True,
            "runtime_hard_boundary_row_count": runtime_hard_boundary_contract["boundary_row_count"],
            "runtime_hard_boundary_blocking_count": runtime_hard_boundary_contract["blocking_boundary_count"],
            "runtime_hard_boundary_get_cache_external_calls_allowed": False,
            "runtime_hard_boundary_react_render_provider_calls_allowed": False,
            "runtime_hard_boundary_fastapi_startup_external_calls_allowed": False,
            "runtime_hard_boundary_post_task_worker_local_fallback_required": True,
            "runtime_hard_boundary_call_ledger_required": True,
            "runtime_hard_boundary_model_ledger_required_for_deepseek": True,
            "runtime_hard_boundary_deepseek_is_data_source": False,
            "runtime_hard_boundary_real_trading_allowed": False,
            "runtime_hard_boundary_token_key_frontend_log_packet_cache_allowed": False,
            "runtime_hard_boundary_contract_is_production_evidence": False,
            "runtime_cache_first_polling_contract_visible": True,
            "runtime_cache_first_polling_phase_count": runtime_cache_first_polling_contract["phase_count"],
            "runtime_cache_first_polling_cache_first_render_required": True,
            "runtime_cache_first_polling_task_polling_required": True,
            "runtime_cache_first_polling_last_good_cache_required": True,
            "runtime_cache_first_polling_browser_evidence_complete": False,
            "runtime_cache_first_polling_is_production_evidence": False,
            "runtime_frontend_enablement_gate_contract_visible": True,
            "runtime_frontend_enablement_allowed": False,
            "runtime_frontend_enablement_blocking_row_count": runtime_frontend_enablement_gate_contract[
                "blocking_row_count"
            ],
            "runtime_frontend_enablement_target_stage_key": runtime_frontend_enablement_gate_contract[
                "target_stage_key"
            ],
            "runtime_frontend_enablement_browser_evidence_complete": False,
            "runtime_frontend_enablement_is_production_evidence": False,
            "runtime_browser_evidence_contract_visible": True,
            "runtime_browser_evidence_row_count": runtime_browser_evidence_contract["evidence_row_count"],
            "runtime_browser_evidence_network_trace_required": True,
            "runtime_browser_evidence_complete": False,
            "runtime_browser_evidence_blocking_row_count": runtime_browser_evidence_contract[
                "blocking_evidence_row_count"
            ],
            "runtime_browser_evidence_is_production_evidence": False,
            "runtime_frontend_wiring_manifest_contract_visible": True,
            "runtime_frontend_wiring_manifest_row_count": runtime_frontend_wiring_manifest_contract[
                "manifest_row_count"
            ],
            "runtime_frontend_wiring_manifest_done_row_count": runtime_frontend_wiring_manifest_contract[
                "implementation_done_row_count"
            ],
            "runtime_frontend_wiring_manifest_pending_row_count": runtime_frontend_wiring_manifest_contract[
                "pending_manifest_row_count"
            ],
            "runtime_frontend_wiring_manifest_manual_button_implemented": runtime_frontend_wiring_manifest_contract[
                "manual_button_manifest_implemented"
            ],
            "runtime_frontend_wiring_manifest_implemented": False,
            "runtime_frontend_wiring_manifest_is_production_evidence": False,
            "runtime_frontend_acceptance_runbook_contract_visible": True,
            "runtime_frontend_acceptance_runbook_row_count": runtime_frontend_acceptance_runbook_contract[
                "runbook_row_count"
            ],
            "runtime_frontend_acceptance_runbook_pending_row_count": (
                runtime_frontend_acceptance_runbook_contract["pending_runbook_row_count"]
            ),
            "runtime_frontend_acceptance_runbook_complete": False,
            "runtime_frontend_acceptance_runbook_is_production_evidence": False,
            "runtime_frontend_acceptance_artifact_contract_visible": True,
            "runtime_frontend_acceptance_artifact_row_count": runtime_frontend_acceptance_artifact_contract[
                "artifact_row_count"
            ],
            "runtime_frontend_acceptance_artifact_pending_count": runtime_frontend_acceptance_artifact_contract[
                "pending_artifact_count"
            ],
            "runtime_frontend_acceptance_artifact_redaction_review_required": True,
            "runtime_frontend_acceptance_artifact_collection_complete": False,
            "runtime_frontend_acceptance_artifact_is_production_evidence": False,
            "runtime_frontend_enablement_promotion_contract_visible": True,
            "runtime_frontend_enablement_promotion_row_count": runtime_frontend_enablement_promotion_contract[
                "promotion_row_count"
            ],
            "runtime_frontend_enablement_promotion_blocking_row_count": (
                runtime_frontend_enablement_promotion_contract["blocking_promotion_row_count"]
            ),
            "runtime_frontend_enablement_promotion_allowed": False,
            "runtime_frontend_enablement_promotion_is_production_evidence": False,
            "runtime_frontend_enablement_release_switch_contract_visible": True,
            "runtime_frontend_enablement_release_switch_row_count": (
                runtime_frontend_enablement_release_switch_contract["release_switch_row_count"]
            ),
            "runtime_frontend_enablement_release_switch_blocking_row_count": (
                runtime_frontend_enablement_release_switch_contract["blocking_release_switch_row_count"]
            ),
            "runtime_frontend_enablement_release_switch_effective_allowed": False,
            "runtime_frontend_enablement_release_switch_is_production_evidence": False,
            "runtime_frontend_enablement_config_promotion_contract_visible": True,
            "runtime_frontend_enablement_config_promotion_step_count": (
                runtime_frontend_enablement_config_promotion_contract["promotion_step_count"]
            ),
            "runtime_frontend_enablement_config_promotion_pending_step_count": (
                runtime_frontend_enablement_config_promotion_contract["pending_promotion_step_count"]
            ),
            "runtime_frontend_enablement_config_promotion_effective_allowed": False,
            "runtime_frontend_enablement_config_promotion_is_production_evidence": False,
            "runtime_mode_acceptance_contract_visible": True,
            "runtime_mode_acceptance_row_count": runtime_mode_acceptance_contract["acceptance_row_count"],
            "runtime_mode_acceptance_is_production_evidence": False,
            "live_light_rollout_roadmap_contract_visible": True,
            "live_light_rollout_roadmap_stage_count": live_light_rollout_roadmap_contract["stage_count"],
            "live_light_rollout_next_implementation_stage_key": (
                live_light_rollout_roadmap_contract["next_implementation_stage_key"]
            ),
            "live_light_rollout_next_execution_request_stage_key": (
                live_light_rollout_roadmap_contract["next_execution_request_stage_key"]
            ),
            "live_light_rollout_execution_request_receipt_service_ready": (
                live_light_rollout_roadmap_contract["execution_request_receipt_service_ready"]
            ),
            "live_light_rollout_execution_request_operator_readiness_visible": (
                live_light_rollout_roadmap_contract["execution_request_operator_readiness_visible"]
            ),
            "live_light_rollout_execution_request_route_pending": (
                live_light_rollout_roadmap_contract["execution_request_route_pending"]
            ),
            "live_light_rollout_execution_request_provider_model_task_creation_allowed": (
                live_light_rollout_roadmap_contract[
                    "execution_request_provider_model_task_creation_allowed"
                ]
            ),
            "live_light_rollout_roadmap_is_production_evidence": False,
            "task_creation_invariant_contract_visible": True,
            "task_creation_invariant_surface_row_count": task_creation_invariant_contract["surface_row_count"],
            "task_creation_invariant_allowed_surface_count": (
                task_creation_invariant_contract["allowed_task_surface_count"]
            ),
            "task_creation_invariant_is_production_evidence": False,
            "background_task_auto_trigger_allowed": background_task_contract["auto_trigger_allowed"],
            "startup_autostart_readiness_contract_visible": True,
            "startup_autostart_readiness_row_count": (
                live_light_startup_autostart_readiness_contract["readiness_row_count"]
            ),
            "startup_autostart_condition_satisfied_row_count": (
                live_light_startup_autostart_readiness_contract["condition_satisfied_row_count"]
            ),
            "startup_autostart_frontend_wiring_implemented": False,
            "startup_autostart_browser_evidence_complete": False,
            "startup_autostart_effective_allowed": False,
            "startup_autostart_readiness_is_production_evidence": False,
            "unified_startup_task_contract_visible": True,
            "unified_startup_task_stage_count": live_light_unified_startup_task_contract["stage_count"],
            "unified_startup_task_route": live_light_unified_startup_task_contract["task_route"],
            "unified_startup_task_provider_execution_implemented": False,
            "unified_startup_task_model_execution_implemented": False,
            "unified_startup_task_worker_dispatch_implemented": False,
            "unified_startup_task_is_production_evidence": False,
            "scope_intake_contract_visible": True,
            "scope_intake_symbol_limit": symbol_limit,
            "scope_intake_symbol_dedupe_required": True,
            "scope_intake_scope_hash_required": True,
            "scope_intake_secret_like_payload_fields_dropped": True,
            "scope_intake_is_production_evidence": False,
            "stage_dependency_contract_visible": True,
            "stage_dependency_stage_count": live_light_stage_dependency_contract["stage_count"],
            "stage_dependency_deepseek_requires_data_ready": True,
            "stage_dependency_safe_skip_required": True,
            "stage_dependency_executor_implemented": False,
            "stage_dependency_contract_is_production_evidence": False,
            "freshness_provider_gap_contract_visible": True,
            "freshness_state_visible_required": True,
            "provider_gap_visible_required": True,
            "stale_cache_label_required": True,
            "empty_or_no_record_is_verified": False,
            "freshness_provider_gap_contract_is_production_evidence": False,
            "task_lifecycle_contract_visible": True,
            "task_status_route": "GET /api/tasks/{task_id}",
            "task_index_route": "GET /api/tasks",
            "task_status_polling_required": True,
            "task_success_is_provider_model_evidence": False,
            "task_success_is_production_evidence": False,
            "task_queue_budget_contract_visible": True,
            "task_queue_budget_row_count": live_light_task_queue_budget_contract["queue_row_count"],
            "task_queue_budget_condition_satisfied_row_count": (
                live_light_task_queue_budget_contract["condition_satisfied_row_count"]
            ),
            "task_queue_budget_max_active_local_startup_tasks_per_session": (
                live_light_task_queue_budget_contract["max_active_local_startup_tasks_per_session"]
            ),
            "task_queue_budget_rate_limit_seconds": live_light_task_queue_budget_contract["rate_limit_seconds"],
            "task_queue_budget_unbounded_queue_allowed": False,
            "task_queue_budget_status_get_creates_task": False,
            "task_queue_budget_task_polling_creates_task": False,
            "task_queue_budget_creates_provider_model_task": False,
            "task_queue_budget_is_production_evidence": False,
            "task_control_contract_visible": True,
            "task_cancel_route": "POST /api/tasks/{task_id}/cancel",
            "task_retry_route": "POST /api/tasks/{task_id}/retry",
            "task_control_manual_only": True,
            "task_control_auto_retry_enabled": False,
            "task_control_is_production_evidence": False,
            "operator_status_contract_visible": True,
            "operator_status_surface_count": live_light_operator_status_contract["status_surface_count"],
            "operator_status_current_mode_visible_required": True,
            "operator_status_effective_source_switches_visible_required": True,
            "operator_status_external_execution_profile_visible_required": True,
            "operator_status_external_execution_profile": live_light_operator_status_contract[
                "external_execution_profile"
            ],
            "operator_status_profile_provider_stage_allowed": live_light_operator_status_contract[
                "external_execution_profile_provider_stage_allowed"
            ],
            "operator_status_profile_model_stage_allowed": live_light_operator_status_contract[
                "external_execution_profile_model_stage_allowed"
            ],
            "operator_status_profile_executor_implemented": False,
            "operator_status_profile_calls_provider_model_now": False,
            "operator_status_profile_source_rate_summary_visible": True,
            "operator_status_latest_task_status_visible_required": True,
            "operator_status_rate_limit_skipped_visible_required": True,
            "operator_status_safe_error_visible_required": True,
            "operator_status_read_only": True,
            "operator_status_is_production_evidence": False,
            "latest_bootstrap_task_status_visible": True,
            "latest_bootstrap_task_found": live_light_latest_bootstrap_task_status["task_found"],
            "latest_bootstrap_task_status": live_light_latest_bootstrap_task_status["status"],
            "latest_bootstrap_task_id": live_light_latest_bootstrap_task_status["task_id"],
            "latest_bootstrap_task_current_step": live_light_latest_bootstrap_task_status["current_step"],
            "latest_bootstrap_task_durable_visible": live_light_latest_bootstrap_task_status["durable_task_visible"],
            "latest_bootstrap_task_lookup_creates_task": False,
            "latest_bootstrap_task_success_is_provider_model_evidence": False,
            "latest_bootstrap_task_is_production_evidence": False,
            "latest_bootstrap_local_compute_handoff_visible": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_visible"
            ],
            "latest_bootstrap_local_compute_handoff_status": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_status"
            ],
            "latest_bootstrap_local_compute_handoff_mode_gate": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_mode_gate"
            ],
            "latest_bootstrap_local_compute_handoff_mode_gate_satisfied": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_mode_gate_satisfied"
            ],
            "latest_bootstrap_local_compute_handoff_source_switch_satisfied": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_source_switch_satisfied"
            ],
            "latest_bootstrap_local_compute_handoff_inactive_reason": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_inactive_reason"
            ],
            "latest_bootstrap_local_compute_handoff_row_count": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_row_count"
            ],
            "latest_bootstrap_local_compute_handoff_enabled_row_count": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_enabled_row_count"
            ],
            "latest_bootstrap_local_compute_handoff_executed_row_count": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_executed_row_count"
            ],
            "latest_bootstrap_local_compute_handoff_output_written_row_count": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_output_written_row_count"
            ],
            "latest_bootstrap_local_compute_handoff_lineage_required_field_count": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_lineage_required_field_count"
            ],
            "latest_bootstrap_local_compute_handoff_lineage_written_row_count": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_lineage_written_row_count"
            ],
            "latest_bootstrap_local_compute_handoff_lineage_write_policy": live_light_latest_bootstrap_task_status[
                "local_compute_handoff_lineage_write_policy"
            ],
            "latest_bootstrap_local_compute_handoff_cache_get_may_write_lineage": False,
            "latest_bootstrap_local_compute_handoff_react_render_may_write_lineage": False,
            "latest_bootstrap_local_compute_handoff_fastapi_startup_may_write_lineage": False,
            "latest_bootstrap_local_compute_handoff_lineage_is_execution_evidence": False,
            "latest_bootstrap_local_compute_handoff_lineage_is_production_evidence": False,
            "latest_bootstrap_local_compute_handoff_executes_compute": False,
            "latest_bootstrap_local_compute_handoff_writes_output": False,
            "latest_bootstrap_local_compute_handoff_is_execution_evidence": False,
            "latest_bootstrap_local_compute_handoff_is_production_evidence": False,
            "promotion_gate_contract_visible": True,
            "promotion_gate_layer_count": live_light_promotion_gate_contract["promotion_layer_count"],
            "promotion_gate_real_provider_model_evidence_complete": False,
            "promotion_gate_remote_ci_green": False,
            "promotion_gate_ready_for_release": False,
            "promotion_gate_contract_is_production_evidence": False,
            "worker_dispatch_contract_visible": True,
            "worker_dispatch_row_count": live_light_worker_dispatch_contract["dispatch_row_count"],
            "worker_dispatch_current_runtime": live_light_worker_dispatch_contract["current_runtime"],
            "worker_dispatch_celery_implemented": False,
            "worker_dispatch_provider_requires_execution_request": True,
            "worker_dispatch_model_requires_execution_request": True,
            "worker_dispatch_is_production_evidence": False,
            "search_quant_projection_workflow_contract_visible": True,
            "search_quant_projection_submit_autostart_contract_visible": True,
            "search_quant_projection_submit_autostart_allowed": search_quant_projection_submit_autostart_contract[
                "live_light_search_submit_auto_start_allowed"
            ],
            "search_quant_projection_submit_autostart_config_switch": (
                "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"
            ),
            "search_quant_projection_submit_autostart_configured": search_submit_autostart_on_submit,
            "search_quant_projection_submit_autostart_effective": effective_search_submit_autostart,
            "search_quant_projection_submit_autostart_config_handoff_visible": True,
            "search_quant_projection_submit_autostart_config_handoff_status": (
                search_quant_projection_submit_autostart_config_handoff_contract["status"]
            ),
            "search_quant_projection_submit_autostart_local_env_fallback_available": (
                search_quant_projection_submit_autostart_config_handoff_contract[
                    "bootstrap_local_env_fallback_available"
                ]
            ),
            "search_quant_projection_submit_autostart_global_config_allowlist_promoted": (
                search_quant_projection_submit_autostart_config_handoff_contract[
                    "global_config_allowlist_promoted"
                ]
            ),
            "search_quant_projection_submit_autostart_config_allowlist_promotion_pending": (
                search_quant_projection_submit_autostart_config_handoff_contract[
                    "global_config_allowlist_promotion_pending"
                ]
            ),
            "search_quant_projection_submit_autostart_config_handoff_is_production_evidence": False,
            "search_quant_projection_submit_autostart_config_promotion_contract_visible": True,
            "search_quant_projection_submit_autostart_config_promotion_status": (
                search_quant_projection_submit_autostart_config_promotion_contract["status"]
            ),
            "search_quant_projection_submit_autostart_config_promotion_step_count": (
                search_quant_projection_submit_autostart_config_promotion_contract["promotion_step_count"]
            ),
            "search_quant_projection_submit_autostart_config_py_update_pending": (
                search_quant_projection_submit_autostart_config_promotion_contract["config_py_update_pending"]
            ),
            "search_quant_projection_submit_autostart_bootstrap_fallback_removal_pending": (
                search_quant_projection_submit_autostart_config_promotion_contract[
                    "bootstrap_local_env_fallback_removal_pending"
                ]
            ),
            "search_quant_projection_submit_autostart_config_promotion_is_production_evidence": False,
            "search_quant_projection_submit_autostart_route": search_quant_projection_submit_autostart_contract[
                "task_route"
            ],
            "search_quant_projection_submit_autostart_readiness_stage": search_quant_projection_submit_autostart_contract[
                "autostart_readiness_stage"
            ],
            "search_quant_projection_submit_autostart_backend_ready": True,
            "search_quant_projection_submit_autostart_frontend_wiring_implemented": False,
            "search_quant_projection_submit_autostart_task_catalog_covered": True,
            "search_quant_projection_submit_autostart_provider_model_pending": True,
            "search_quant_projection_submit_autostart_is_production_evidence": False,
            "search_quant_projection_manual_button_frontend_wiring_implemented": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "manual_button_frontend_wiring_implemented"
                ]
            ),
            "search_quant_projection_manual_confirm_button_frontend_wiring_implemented": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "manual_confirm_button_frontend_wiring_implemented"
                ]
            ),
            "search_quant_projection_manual_confirm_button_runtime_ready": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "manual_confirm_button_runtime_ready"
                ]
            ),
            "search_quant_projection_manual_confirm_button_status": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "manual_confirm_button_status"
                ]
            ),
            "search_quant_projection_p1_manual_confirm_path_ready": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "p1_manual_confirm_path_ready"
                ]
            ),
            "search_quant_projection_p1_manual_confirm_path_status": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "p1_manual_confirm_path_status"
                ]
            ),
            "search_quant_projection_frontend_runtime_wiring_implemented": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "frontend_runtime_wiring_implemented"
                ]
            ),
            "search_quant_projection_frontend_runtime_wiring_scope": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "frontend_runtime_wiring_scope"
                ]
            ),
            "search_quant_projection_manual_button_task_status_polling_bound": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "manual_button_task_status_polling_bound"
                ]
            ),
            "search_quant_projection_manual_button_path_is_production_evidence": False,
            "search_quant_projection_manual_button_path_calls_provider_or_model_from_frontend": False,
            "search_quant_projection_frontend_wiring_acceptance_contract_visible": True,
            "search_quant_projection_frontend_wiring_status": search_quant_projection_frontend_wiring_acceptance_contract[
                "status"
            ],
            "search_quant_projection_frontend_wiring_mode_matrix_visible": True,
            "search_quant_projection_frontend_wiring_mode_row_count": search_quant_projection_frontend_wiring_acceptance_contract[
                "mode_acceptance_row_count"
            ],
            "search_quant_projection_frontend_wiring_active_mode_behavior": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "active_mode_expected_frontend_behavior"
                ]
            ),
            "search_quant_projection_frontend_wiring_browser_acceptance_row_count": (
                search_quant_projection_frontend_wiring_acceptance_contract["browser_acceptance_row_count"]
            ),
            "search_quant_projection_frontend_wiring_browser_network_trace_required": True,
            "search_quant_projection_frontend_wiring_failure_recovery_row_count": (
                search_quant_projection_frontend_wiring_acceptance_contract["failure_recovery_row_count"]
            ),
            "search_quant_projection_frontend_wiring_safe_error_display_required": True,
            "search_quant_projection_frontend_wiring_rate_limit_reuse_visible_required": True,
            "search_quant_projection_frontend_wiring_implemented": False,
            "search_quant_projection_full_frontend_wiring_implemented": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "full_frontend_wiring_implemented"
                ]
            ),
            "search_quant_projection_full_frontend_wiring_pending_reason": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "full_frontend_wiring_pending_reason"
                ]
            ),
            "search_quant_projection_frontend_wiring_browser_evidence_complete": False,
            "search_quant_projection_frontend_wiring_failure_recovery_evidence_complete": False,
            "search_quant_projection_frontend_wiring_is_production_evidence": False,
            "search_quant_projection_unified_startup_handoff_contract_visible": True,
            "search_quant_projection_unified_startup_handoff_row_count": (
                search_quant_projection_unified_startup_handoff_contract["handoff_row_count"]
            ),
            "search_quant_projection_unified_startup_handoff_implemented": False,
            "search_quant_projection_unified_startup_task_created_now": False,
            "search_quant_projection_unified_startup_handoff_is_production_evidence": False,
            "search_quant_projection_result_surface_contract_visible": True,
            "search_quant_projection_result_surface_count": search_quant_projection_result_surface_contract[
                "result_surface_count"
            ],
            "search_quant_projection_result_surfaces_research_only": True,
            "search_quant_projection_result_surface_is_production_evidence": False,
            "search_quant_projection_factor_next_handoff_contract_visible": True,
            "search_quant_projection_factor_next_handoff_row_count": (
                search_quant_projection_factor_next_handoff_contract["handoff_row_count"]
            ),
            "search_quant_projection_factor_next_handoff_ready_now_row_count": (
                search_quant_projection_factor_next_handoff_contract["ready_now_row_count"]
            ),
            "search_quant_projection_factor_next_handoff_output_written_row_count": (
                search_quant_projection_factor_next_handoff_contract["output_written_row_count"]
            ),
            "search_quant_projection_factor_next_handoff_feeds_deepseek_readiness": True,
            "search_quant_projection_factor_next_executes_local_compute_now": False,
            "search_quant_projection_factor_next_writes_cache_now": False,
            "search_quant_projection_factor_next_handoff_is_production_evidence": False,
            "search_quant_projection_cache_write_preflight_contract_visible": True,
            "search_quant_projection_cache_write_preflight_row_count": (
                search_quant_projection_cache_write_preflight_contract["preflight_row_count"]
            ),
            "search_quant_projection_cache_write_preflight_ready_now_row_count": (
                search_quant_projection_cache_write_preflight_contract["ready_now_row_count"]
            ),
            "search_quant_projection_cache_write_preflight_cache_written_row_count": (
                search_quant_projection_cache_write_preflight_contract["cache_written_row_count"]
            ),
            "search_quant_projection_cache_write_preflight_feeds_deepseek_readiness": True,
            "search_quant_projection_cache_write_preflight_writes_cache_now": False,
            "search_quant_projection_cache_write_preflight_is_production_evidence": False,
            "search_quant_projection_deepseek_model_preflight_contract_visible": True,
            "search_quant_projection_deepseek_model_preflight_row_count": (
                search_quant_projection_deepseek_model_preflight_contract["preflight_row_count"]
            ),
            "search_quant_projection_deepseek_model_preflight_ready_now_row_count": (
                search_quant_projection_deepseek_model_preflight_contract["ready_now_row_count"]
            ),
            "search_quant_projection_deepseek_model_preflight_model_called_row_count": (
                search_quant_projection_deepseek_model_preflight_contract["model_called_row_count"]
            ),
            "search_quant_projection_deepseek_model_preflight_allowed_output_field_count": (
                search_quant_projection_deepseek_model_preflight_contract["allowed_output_field_count"]
            ),
            "search_quant_projection_deepseek_model_preflight_requires_model_ledger": True,
            "search_quant_projection_deepseek_model_preflight_calls_model_now": False,
            "search_quant_projection_deepseek_model_preflight_is_production_evidence": False,
            "search_quant_projection_deepseek_output_acceptance_contract_visible": True,
            "search_quant_projection_deepseek_output_acceptance_row_count": (
                search_quant_projection_deepseek_output_acceptance_contract["acceptance_row_count"]
            ),
            "search_quant_projection_deepseek_output_accepted_row_count": (
                search_quant_projection_deepseek_output_acceptance_contract["output_accepted_row_count"]
            ),
            "search_quant_projection_deepseek_output_acceptance_cache_written_row_count": (
                search_quant_projection_deepseek_output_acceptance_contract["model_cache_written_row_count"]
            ),
            "search_quant_projection_deepseek_output_acceptance_safe_field_count": (
                search_quant_projection_deepseek_output_acceptance_contract["accepted_output_field_count"]
            ),
            "search_quant_projection_deepseek_output_acceptance_raw_output_visible_allowed": False,
            "search_quant_projection_deepseek_output_acceptance_is_production_evidence": False,
            "search_quant_projection_deepseek_readiness_contract_visible": True,
            "search_quant_projection_deepseek_readiness_row_count": (
                search_quant_projection_deepseek_readiness_contract["readiness_row_count"]
            ),
            "search_quant_projection_deepseek_ready_now_row_count": (
                search_quant_projection_deepseek_readiness_contract["ready_now_row_count"]
            ),
            "search_quant_projection_deepseek_allowed_output_field_count": (
                search_quant_projection_deepseek_readiness_contract["allowed_output_field_count"]
            ),
            "search_quant_projection_deepseek_requires_model_ledger": True,
            "search_quant_projection_deepseek_calls_model_now": False,
            "search_quant_projection_deepseek_is_production_evidence": False,
            "search_quant_projection_latest_status_visible": True,
            "search_quant_projection_latest_task_found": search_quant_projection_latest_status["task_found"],
            "search_quant_projection_latest_status": search_quant_projection_latest_status["status"],
            "search_quant_projection_latest_task_id": search_quant_projection_latest_status["task_id"],
            "search_quant_projection_latest_symbol": search_quant_projection_latest_status["symbol"],
            "search_quant_projection_latest_local_receipt_visible": search_quant_projection_latest_status[
                "local_receipt_visible"
            ],
            "search_quant_projection_latest_lookup_creates_task": False,
            "search_quant_projection_latest_is_production_evidence": False,
            "search_quant_projection_provider_model_latest_status_visible": True,
            "search_quant_projection_provider_model_latest_task_found": (
                search_quant_projection_provider_model_latest_status["task_found"]
            ),
            "search_quant_projection_provider_model_latest_status": (
                search_quant_projection_provider_model_latest_status["status"]
            ),
            "search_quant_projection_provider_model_latest_task_id": (
                search_quant_projection_provider_model_latest_status["task_id"]
            ),
            "search_quant_projection_provider_model_latest_symbol": (
                search_quant_projection_provider_model_latest_status["symbol"]
            ),
            "search_quant_projection_provider_model_latest_provider_call_ledger_evidence_done": (
                search_quant_projection_provider_model_latest_status["provider_call_ledger_evidence_done"]
            ),
            "search_quant_projection_provider_model_latest_deepseek_model_ledger_evidence_done": (
                search_quant_projection_provider_model_latest_status["deepseek_model_ledger_evidence_done"]
            ),
            "search_quant_projection_provider_model_latest_deepseek_output_acceptance_done": (
                search_quant_projection_provider_model_latest_status["deepseek_output_acceptance_done"]
            ),
            "search_quant_projection_provider_model_latest_deepseek_output_acceptance_status": (
                search_quant_projection_provider_model_latest_status["deepseek_output_acceptance_status"]
            ),
            "search_quant_projection_provider_model_latest_deepseek_output_cache_written": (
                search_quant_projection_provider_model_latest_status["deepseek_output_cache_written"]
            ),
            "search_quant_projection_provider_model_latest_acceptance_visible": (
                search_quant_projection_provider_model_latest_status["provider_model_acceptance_visible"]
            ),
            "search_quant_projection_provider_model_latest_task_success_is_model_output_evidence": (
                search_quant_projection_provider_model_latest_status["task_success_is_model_output_evidence"]
            ),
            "search_quant_projection_provider_model_latest_lookup_creates_task": False,
            "search_quant_projection_provider_model_latest_status_get_external_calls": False,
            "search_quant_projection_provider_model_latest_is_production_evidence": False,
            "tushare_light_strategy_contract_visible": True,
            "tushare_light_strategy_provider_execution_pending": True,
            "deepseek_pro_strategy_contract_visible": True,
            "deepseek_pro_strategy_model_execution_pending": True,
            "ui_nonblocking_runtime_contract_visible": True,
            "local_fallback_contract_visible": True,
            "local_fallback_uses_last_good_cache_allowed": True,
            "local_fallback_stale_cache_label_required": True,
            "local_fallback_provider_gap_visible_required": True,
            "local_fallback_is_production_evidence": False,
            "cache_lineage_contract_visible": True,
            "cache_lineage_required_for_outputs": True,
            "cache_lineage_written_by_post_task_only": True,
            "memory_only_lineage_is_durable_evidence": False,
            "output_surface_contract_visible": True,
            "output_surface_count": live_light_output_surface_contract["output_surface_count"],
            "factor_quant_hub_output_surface_required": True,
            "next_session_output_surface_required": True,
            "deepseek_explanation_output_surface_governed": True,
            "output_surface_written_by_post_task_only": True,
            "output_surface_contract_is_production_evidence": False,
            "runtime_budget_contract_visible": True,
            "runtime_budget_symbol_limit": symbol_limit,
            "runtime_budget_rate_limit_seconds": rate_limit_seconds,
            "runtime_budget_cache_hit_skips_provider_call_allowed": True,
            "runtime_budget_token_usage_record_required": True,
            "runtime_budget_enforcement_implemented": False,
            "runtime_budget_contract_is_production_evidence": False,
            "evidence_grade_contract_visible": True,
            "credential_preflight_contract_visible": True,
            "credential_presence_check_route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
            "status_get_checks_credential_presence": False,
            "credential_presence_check_requires_post": True,
            "credential_presence_check_requires_user_approval": True,
            "provider_model_execution_request_contract_visible": True,
            "provider_model_execution_request_route": PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE,
            "provider_model_acceptance_dry_run_route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
            "provider_model_acceptance_target_route": FUTURE_BOOTSTRAP_PROVIDER_MODEL_ACCEPTANCE_ROUTE,
            "provider_model_acceptance_requires_execution_request": True,
            "provider_model_execution_request_implemented": (
                live_light_provider_model_execution_request_contract["execution_request_route_implemented"]
            ),
            "dry_run_is_execution_request": False,
            "execution_request_handoff_contract_visible": True,
            "execution_request_handoff_row_count": live_light_execution_request_handoff_contract["handoff_row_count"],
            "execution_request_handoff_route_implemented": (
                live_light_execution_request_handoff_contract["execution_request_route_implemented"]
            ),
            "execution_request_receipt_service_implemented": True,
            "execution_request_receipt_task_type": BOOTSTRAP_EXECUTION_REQUEST_TASK_TYPE,
            "execution_request_route_adapter_contract_visible": True,
            "execution_request_route_adapter_target_file": live_light_execution_request_handoff_contract[
                "route_adapter_target_file"
            ],
            "execution_request_route_adapter_service_function": live_light_execution_request_handoff_contract[
                "route_adapter_service_function"
            ],
            "execution_request_route_adapter_response_envelope": live_light_execution_request_handoff_contract[
                "route_adapter_response_envelope"
            ],
            "execution_request_route_adapter_current_status": live_light_execution_request_handoff_contract[
                "route_adapter_current_status"
            ],
            "execution_request_route_adapter_provider_model_task_creation_allowed": False,
            "execution_request_route_adapter_calls_provider_or_model": False,
            "latest_acceptance_dry_run_status_visible": True,
            "latest_acceptance_dry_run_found": live_light_latest_acceptance_dry_run_status["receipt_found"],
            "latest_acceptance_dry_run_status": live_light_latest_acceptance_dry_run_status["status"],
            "latest_acceptance_dry_run_task_id": live_light_latest_acceptance_dry_run_status["task_id"],
            "latest_acceptance_dry_run_ready_for_execution_request": live_light_latest_acceptance_dry_run_status[
                "dry_run_ready_for_execution_request"
            ],
            "latest_acceptance_dry_run_durable_receipt_visible": live_light_latest_acceptance_dry_run_status[
                "durable_receipt_visible"
            ],
            "latest_acceptance_dry_run_lookup_creates_task": False,
            "latest_acceptance_dry_run_is_production_evidence": False,
            "latest_execution_request_status_visible": True,
            "latest_execution_request_found": live_light_latest_execution_request_status["receipt_found"],
            "latest_execution_request_status": live_light_latest_execution_request_status["status"],
            "latest_execution_request_task_id": live_light_latest_execution_request_status["task_id"],
            "latest_execution_request_ready": live_light_latest_execution_request_status[
                "local_execution_request_ready"
            ],
            "latest_execution_request_durable_receipt_visible": live_light_latest_execution_request_status[
                "durable_receipt_visible"
            ],
            "latest_execution_request_lookup_creates_task": False,
            "latest_execution_request_is_production_evidence": False,
            "execution_request_handoff_requires_durable_receipt": True,
            "execution_request_handoff_scope_hash_mismatch_blocks": True,
            "execution_request_handoff_is_production_evidence": False,
            "ledger_contract_visible": True,
            "ui_nonblocking_browser_runtime_evidence_complete": False,
            "ready_for_provider_execution_design": activation_receipt["ready_for_provider_execution_design"],
            "ready_for_acceptance_design": acceptance_runbook["ready_for_acceptance_design"],
            "ready_for_user_approved_acceptance_dry_run_task": True,
            "ready_for_user_approved_acceptance_task": False,
            "ready_for_provider_execution": False,
            "ready_for_model_execution": False,
            "provider_execution_implemented": False,
            "tushare_execution_implemented": False,
            "deepseek_execution_implemented": False,
            "local_artifacts_are_production_evidence": False,
            "production_evidence_pending": True,
            "call_ledger_required": live_light_ledger_contract["call_ledger_required_for_provider"],
            "model_ledger_required": live_light_ledger_contract["model_ledger_required_for_deepseek"],
            "redaction_review_required_before_promotion": True,
            "ledger_redaction_invariant_contract_visible": True,
            "ledger_redaction_prohibited_surface_count": live_light_ledger_redaction_invariant_contract[
                "prohibited_surface_count"
            ],
            "ledger_redaction_required_ledger_row_count": live_light_ledger_redaction_invariant_contract[
                "required_ledger_row_count"
            ],
            "ledger_redaction_review_required_before_promotion": True,
            "ledger_redaction_raw_payload_exposed": False,
            "ledger_redaction_credential_material_exposed": False,
            "ledger_redaction_invariant_is_production_evidence": False,
            "rate_limit_implemented": True,
            "allowed_scope": "current_target_holdings_watchlist_light_only",
            "full_pool_enabled": False,
            "full_pool_reserved": True,
            "safe_failure_display_required": True,
            "token_key_exposure_allowed": False,
        },
        "live_full": {
            "enabled": False,
            "active_mode_requested": active_mode == "live_full",
            "status": live_full_reserved_contract["status"],
            "configured_allow_full_pool": allow_full_pool,
            "effective_allow_full_pool": False,
            "reserved_mode": True,
            "future_worker_mode_only": True,
            "separate_authorization_required": True,
            "full_pool_on_open_allowed": False,
            "deep_scan_on_open_allowed": False,
            "page_open_task_allowed": False,
            "react_mounted_auto_task_allowed": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "worker_execution_implemented": False,
            "production_live_full_complete": False,
        },
        "manual": {
            "enabled": active_mode == "manual",
            "status": "manual_ready_explicit_task_only"
            if active_mode == "manual"
            else "inactive_until_manual_mode",
            "external_call_policy": "explicit_post_task_only",
            "button_gated_post_tasks_only": True,
            "auto_bootstrap_allowed": False,
            "react_mounted_auto_task_allowed": False,
            "cache_get_external_calls": False,
            "react_render_provider_calls": False,
            "live_startup_route_auto_allowed": False,
            "external_calls_require_explicit_post_task": True,
            "provider_execution_may_be_implemented_by_selected_post_task": True,
            "startup_provider_execution_implemented": False,
            "model_execution_requires_explicit_post_task": True,
            "token_key_exposure_allowed": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        "policy": {
            "cache_api_external_calls": False,
            "cache_only_switches_do_not_autostart": active_mode == "cache_only",
            "fastapi_startup_external_calls": False,
            "react_initial_render_external_calls": False,
            "react_render_direct_provider_calls": False,
            "post_task_required_for_external_calls": True,
            "manual_requires_explicit_post_task": True,
            "manual_auto_bootstrap_allowed": False,
            "manual_react_mounted_auto_task_allowed": False,
            "live_light_default_enabled": False,
            "live_light_requires_opt_in": True,
            "live_light_task_implemented": True,
            "live_light_bootstrap_plan_skeleton_implemented": True,
            "live_light_model_ledger_preview_implemented": True,
            "provider_linkage_rows_visible": True,
            "live_light_activation_receipt_visible": True,
            "live_light_provider_model_acceptance_runbook_visible": True,
            "live_light_background_task_contract_visible": True,
            "live_light_startup_autostart_readiness_contract_visible": True,
            "live_light_startup_autostart_readiness_row_count": (
                live_light_startup_autostart_readiness_contract["readiness_row_count"]
            ),
            "live_light_startup_autostart_frontend_wiring_implemented": False,
            "live_light_startup_autostart_effective_allowed": False,
            "live_light_startup_autostart_readiness_is_production_evidence": False,
            "live_light_unified_startup_task_contract_visible": True,
            "live_light_unified_startup_task_stage_count": (
                live_light_unified_startup_task_contract["stage_count"]
            ),
            "live_light_unified_startup_task_route": live_light_unified_startup_task_contract["task_route"],
            "live_light_unified_startup_task_provider_execution_implemented": False,
            "live_light_unified_startup_task_model_execution_implemented": False,
            "live_light_unified_startup_task_worker_dispatch_implemented": False,
            "live_light_unified_startup_task_is_production_evidence": False,
            "safe_config_contract_visible": True,
            "runtime_mode_policy_rows_visible": True,
            "runtime_mode_policy_source": "config.COMMAND_CENTER_RUNTIME_MODE_POLICIES",
            "runtime_mode_policy_row_count": len(runtime_mode_policy_rows),
            "runtime_mode_policy_is_production_evidence": False,
            "runtime_config_reference_contract_visible": True,
            "runtime_config_reference_row_count": runtime_config_reference_contract["config_reference_row_count"],
            "runtime_config_reference_source_switch_count": runtime_config_reference_contract["source_switch_count"],
            "runtime_config_reference_audit_id": runtime_config_reference_contract["config_audit_id"],
            "runtime_config_reference_audit_uses_safe_rows_only": True,
            "runtime_config_reference_is_production_evidence": False,
            "runtime_config_ownership_invariant_contract_visible": True,
            "runtime_config_ownership_row_count": runtime_config_ownership_invariant_contract[
                "ownership_row_count"
            ],
            "runtime_config_ownership_audit_id": runtime_config_ownership_invariant_contract["ownership_audit_id"],
            "runtime_config_ownership_linked_reference_audit_id": runtime_config_ownership_invariant_contract[
                "linked_runtime_config_reference_audit_id"
            ],
            "runtime_config_bootstrap_local_env_fallback_count": (
                runtime_config_ownership_invariant_contract["bootstrap_local_env_fallback_count"]
            ),
            "runtime_config_global_config_allowlist_promotion_pending_count": (
                runtime_config_ownership_invariant_contract[
                    "global_config_allowlist_promotion_pending_count"
                ]
            ),
            "runtime_config_frontend_writeback_allowed": False,
            "runtime_config_production_config_complete": False,
            "runtime_config_ownership_invariant_is_production_evidence": False,
            "runtime_operator_summary_contract_visible": True,
            "runtime_operator_active_mode": runtime_operator_summary_contract["mode"],
            "runtime_operator_active_display_status": runtime_operator_summary_contract["active_mode_display_status"],
            "runtime_operator_release_blocker_summary_visible": True,
            "runtime_operator_release_remote_ci_status_known": runtime_operator_summary_contract[
                "release_remote_ci_status_known"
            ],
            "runtime_operator_release_remote_ci_green": runtime_operator_summary_contract[
                "release_remote_ci_green"
            ],
            "runtime_operator_release_github_api_called": runtime_operator_summary_contract[
                "release_github_api_called"
            ],
            "runtime_operator_release_fresh_local_gate_run_required": runtime_operator_summary_contract[
                "release_fresh_local_gate_run_required"
            ],
            "runtime_operator_release_production_promotion_review_required": runtime_operator_summary_contract[
                "release_production_promotion_review_required"
            ],
            "runtime_operator_release_ready_for_promotion": runtime_operator_summary_contract[
                "release_ready_for_promotion"
            ],
            "runtime_operator_release_local_contracts_are_production_evidence": runtime_operator_summary_contract[
                "release_local_contracts_are_production_evidence"
            ],
            "runtime_operator_release_blocker_summary_is_production_evidence": False,
            "runtime_operator_trigger_policy_summary_visible": True,
            "runtime_operator_active_page_open_task_allowed": runtime_operator_summary_contract[
                "active_page_open_task_allowed"
            ],
            "runtime_operator_active_search_submit_task_allowed": runtime_operator_summary_contract[
                "active_search_submit_task_allowed"
            ],
            "runtime_operator_active_manual_button_task_allowed": runtime_operator_summary_contract[
                "active_manual_button_task_allowed"
            ],
            "runtime_operator_active_live_light_background_task_allowed": runtime_operator_summary_contract[
                "active_live_light_background_task_allowed"
            ],
            "runtime_operator_active_provider_model_execution_allowed": runtime_operator_summary_contract[
                "active_provider_model_execution_allowed"
            ],
            "runtime_operator_active_provider_model_execution_surface": runtime_operator_summary_contract[
                "active_provider_model_execution_surface"
            ],
            "runtime_operator_active_provider_model_direct_execution_allowed": runtime_operator_summary_contract[
                "active_provider_model_direct_execution_allowed"
            ],
            "runtime_operator_active_provider_model_requires_explicit_post_task": (
                runtime_operator_summary_contract["active_provider_model_requires_explicit_post_task"]
            ),
            "runtime_operator_active_provider_model_execution_requires_task_contract": (
                runtime_operator_summary_contract["active_provider_model_execution_requires_task_contract"]
            ),
            "runtime_operator_active_provider_model_execution_requires_execution_request": (
                runtime_operator_summary_contract["active_provider_model_execution_requires_execution_request"]
            ),
            "runtime_operator_active_full_pool_or_deep_scan_allowed": runtime_operator_summary_contract[
                "active_full_pool_or_deep_scan_allowed"
            ],
            "runtime_operator_trigger_policy_summary_is_production_evidence": False,
            "runtime_operator_config_reference_audit_id": runtime_operator_summary_contract[
                "config_reference_audit_id"
            ],
            "runtime_operator_config_ownership_audit_id": runtime_operator_summary_contract[
                "config_ownership_audit_id"
            ],
            "runtime_operator_config_audit_uses_safe_rows_only": True,
            "runtime_operator_external_execution_profile": runtime_operator_summary_contract[
                "effective_external_execution_profile"
            ],
            "runtime_operator_profile_provider_stage_allowed": runtime_operator_summary_contract[
                "external_execution_profile_provider_stage_allowed"
            ],
            "runtime_operator_profile_model_stage_allowed": runtime_operator_summary_contract[
                "external_execution_profile_model_stage_allowed"
            ],
            "runtime_operator_provider_model_enablement_summary_visible": runtime_operator_summary_contract[
                "provider_model_enablement_summary_visible"
            ],
            "runtime_operator_provider_model_enablement_source_config": runtime_operator_summary_contract[
                "provider_model_enablement_source_config"
            ],
            "runtime_operator_provider_model_enablement_configured": runtime_operator_summary_contract[
                "provider_model_enablement_configured"
            ],
            "runtime_operator_provider_model_enablement_effective": runtime_operator_summary_contract[
                "provider_model_enablement_effective"
            ],
            "runtime_operator_provider_model_enablement_requires_live_light": runtime_operator_summary_contract[
                "provider_model_enablement_requires_live_light"
            ],
            "runtime_operator_provider_model_enablement_requires_execution_request": (
                runtime_operator_summary_contract[
                    "provider_model_enablement_requires_execution_request"
                ]
            ),
            "runtime_operator_provider_model_enablement_requires_promotion": runtime_operator_summary_contract[
                "provider_model_enablement_requires_promotion"
            ],
            "runtime_operator_provider_model_enablement_creates_provider_model_task": (
                runtime_operator_summary_contract[
                    "provider_model_enablement_creates_provider_model_task"
                ]
            ),
            "runtime_operator_provider_model_enablement_calls_provider_model_now": (
                runtime_operator_summary_contract["provider_model_enablement_calls_provider_model_now"]
            ),
            "runtime_operator_provider_model_enablement_is_production_evidence": False,
            "runtime_operator_profile_source_rate_summary_visible": True,
            "runtime_operator_profile_source_rate_summary_status": runtime_operator_summary_contract[
                "operator_profile_source_rate_summary_status"
            ],
            "runtime_operator_rate_limit_seconds_visible_safe": runtime_operator_summary_contract[
                "operator_rate_limit_seconds_visible_safe"
            ],
            "runtime_operator_task_control_visible": runtime_operator_summary_contract[
                "task_control_contract_visible"
            ],
            "runtime_operator_task_control_row_count": runtime_operator_summary_contract["task_control_row_count"],
            "runtime_operator_task_control_manual_only": runtime_operator_summary_contract["task_control_manual_only"],
            "runtime_operator_task_control_auto_retry_enabled": runtime_operator_summary_contract[
                "task_control_auto_retry_enabled"
            ],
            "runtime_operator_task_control_is_production_evidence": False,
            "runtime_operator_provider_model_handoff_visible": runtime_operator_summary_contract[
                "provider_model_handoff_contract_visible"
            ],
            "runtime_operator_provider_model_handoff_route_implemented": runtime_operator_summary_contract[
                "provider_model_handoff_route_implemented"
            ],
            "runtime_operator_provider_model_handoff_receipt_service_implemented": (
                runtime_operator_summary_contract["provider_model_handoff_receipt_service_implemented"]
            ),
            "runtime_operator_latest_acceptance_dry_run_receipt_found": runtime_operator_summary_contract[
                "latest_acceptance_dry_run_receipt_found"
            ],
            "runtime_operator_latest_acceptance_dry_run_ready_for_execution_request": (
                runtime_operator_summary_contract["latest_acceptance_dry_run_ready_for_execution_request"]
            ),
            "runtime_operator_latest_execution_request_receipt_found": runtime_operator_summary_contract[
                "latest_execution_request_receipt_found"
            ],
            "runtime_operator_latest_execution_request_ready": runtime_operator_summary_contract[
                "latest_execution_request_ready"
            ],
            "runtime_operator_latest_execution_request_lookup_creates_task": runtime_operator_summary_contract[
                "latest_execution_request_lookup_creates_task"
            ],
            "runtime_operator_provider_model_task_created": runtime_operator_summary_contract[
                "provider_model_task_created"
            ],
            "runtime_operator_provider_model_execution_implemented": runtime_operator_summary_contract[
                "provider_model_execution_implemented"
            ],
            "runtime_operator_provider_model_is_production_evidence": False,
            "runtime_operator_summary_row_count": runtime_operator_summary_contract["summary_row_count"],
            "runtime_operator_allowed_action_count": runtime_operator_summary_contract[
                "allowed_operator_action_count"
            ],
            "runtime_operator_blocked_action_count": runtime_operator_summary_contract[
                "blocked_operator_action_count"
            ],
            "runtime_operator_summary_is_production_evidence": False,
            "runtime_operator_cache_first_polling_summary_visible": runtime_operator_summary_contract[
                "cache_first_polling_summary_visible"
            ],
            "runtime_operator_cache_first_polling_source_contract": runtime_operator_summary_contract[
                "cache_first_polling_source_contract"
            ],
            "runtime_operator_cache_first_polling_phase_count": runtime_operator_summary_contract[
                "cache_first_polling_phase_count"
            ],
            "runtime_operator_cache_first_polling_cache_first_render_required": runtime_operator_summary_contract[
                "cache_first_polling_cache_first_render_required"
            ],
            "runtime_operator_cache_first_polling_task_polling_required": runtime_operator_summary_contract[
                "cache_first_polling_task_polling_required"
            ],
            "runtime_operator_cache_first_polling_last_good_cache_required": runtime_operator_summary_contract[
                "cache_first_polling_last_good_cache_required"
            ],
            "runtime_operator_cache_first_polling_browser_evidence_complete": runtime_operator_summary_contract[
                "cache_first_polling_browser_evidence_complete"
            ],
            "runtime_operator_cache_first_polling_summary_is_production_evidence": False,
            "runtime_external_silence_contract_visible": True,
            "runtime_external_silence_row_count": runtime_external_silence_contract["silence_row_count"],
            "runtime_external_silence_local_post_exception_count": runtime_external_silence_contract[
                "local_post_exception_count"
            ],
            "runtime_external_silence_direct_external_call_allowed_count": (
                runtime_external_silence_contract["direct_external_call_allowed_count"]
            ),
            "runtime_external_silence_is_production_evidence": False,
            "runtime_hard_boundary_contract_visible": True,
            "runtime_hard_boundary_row_count": runtime_hard_boundary_contract["boundary_row_count"],
            "runtime_hard_boundary_blocking_count": runtime_hard_boundary_contract["blocking_boundary_count"],
            "runtime_hard_boundary_get_cache_external_calls_allowed": False,
            "runtime_hard_boundary_react_render_provider_calls_allowed": False,
            "runtime_hard_boundary_fastapi_startup_external_calls_allowed": False,
            "runtime_hard_boundary_post_task_worker_local_fallback_required": True,
            "runtime_hard_boundary_call_ledger_required": True,
            "runtime_hard_boundary_model_ledger_required_for_deepseek": True,
            "runtime_hard_boundary_deepseek_is_data_source": False,
            "runtime_hard_boundary_real_trading_allowed": False,
            "runtime_hard_boundary_token_key_frontend_log_packet_cache_allowed": False,
            "runtime_hard_boundary_contract_is_production_evidence": False,
            "runtime_cache_first_polling_contract_visible": True,
            "runtime_cache_first_polling_phase_count": runtime_cache_first_polling_contract["phase_count"],
            "runtime_cache_first_polling_cache_first_render_required": True,
            "runtime_cache_first_polling_task_polling_required": True,
            "runtime_cache_first_polling_last_good_cache_required": True,
            "runtime_cache_first_polling_browser_evidence_complete": False,
            "runtime_cache_first_polling_is_production_evidence": False,
            "runtime_frontend_enablement_gate_contract_visible": True,
            "runtime_frontend_enablement_allowed": False,
            "runtime_frontend_enablement_blocking_row_count": runtime_frontend_enablement_gate_contract[
                "blocking_row_count"
            ],
            "runtime_frontend_enablement_target_stage_key": runtime_frontend_enablement_gate_contract[
                "target_stage_key"
            ],
            "runtime_frontend_enablement_browser_evidence_complete": False,
            "runtime_frontend_enablement_is_production_evidence": False,
            "runtime_browser_evidence_contract_visible": True,
            "runtime_browser_evidence_row_count": runtime_browser_evidence_contract["evidence_row_count"],
            "runtime_browser_evidence_network_trace_required": True,
            "runtime_browser_evidence_complete": False,
            "runtime_browser_evidence_blocking_row_count": runtime_browser_evidence_contract[
                "blocking_evidence_row_count"
            ],
            "runtime_browser_evidence_is_production_evidence": False,
            "runtime_frontend_wiring_manifest_contract_visible": True,
            "runtime_frontend_wiring_manifest_row_count": runtime_frontend_wiring_manifest_contract[
                "manifest_row_count"
            ],
            "runtime_frontend_wiring_manifest_done_row_count": runtime_frontend_wiring_manifest_contract[
                "implementation_done_row_count"
            ],
            "runtime_frontend_wiring_manifest_pending_row_count": runtime_frontend_wiring_manifest_contract[
                "pending_manifest_row_count"
            ],
            "runtime_frontend_wiring_manifest_manual_button_implemented": runtime_frontend_wiring_manifest_contract[
                "manual_button_manifest_implemented"
            ],
            "runtime_frontend_wiring_manifest_implemented": False,
            "runtime_frontend_wiring_manifest_is_production_evidence": False,
            "runtime_frontend_acceptance_runbook_contract_visible": True,
            "runtime_frontend_acceptance_runbook_row_count": runtime_frontend_acceptance_runbook_contract[
                "runbook_row_count"
            ],
            "runtime_frontend_acceptance_runbook_pending_row_count": (
                runtime_frontend_acceptance_runbook_contract["pending_runbook_row_count"]
            ),
            "runtime_frontend_acceptance_runbook_complete": False,
            "runtime_frontend_acceptance_runbook_is_production_evidence": False,
            "runtime_frontend_acceptance_artifact_contract_visible": True,
            "runtime_frontend_acceptance_artifact_row_count": runtime_frontend_acceptance_artifact_contract[
                "artifact_row_count"
            ],
            "runtime_frontend_acceptance_artifact_pending_count": runtime_frontend_acceptance_artifact_contract[
                "pending_artifact_count"
            ],
            "runtime_frontend_acceptance_artifact_redaction_review_required": True,
            "runtime_frontend_acceptance_artifact_collection_complete": False,
            "runtime_frontend_acceptance_artifact_is_production_evidence": False,
            "runtime_frontend_enablement_promotion_contract_visible": True,
            "runtime_frontend_enablement_promotion_row_count": runtime_frontend_enablement_promotion_contract[
                "promotion_row_count"
            ],
            "runtime_frontend_enablement_promotion_blocking_row_count": (
                runtime_frontend_enablement_promotion_contract["blocking_promotion_row_count"]
            ),
            "runtime_frontend_enablement_promotion_allowed": False,
            "runtime_frontend_enablement_promotion_is_production_evidence": False,
            "runtime_frontend_enablement_release_switch_contract_visible": True,
            "runtime_frontend_enablement_release_switch_row_count": (
                runtime_frontend_enablement_release_switch_contract["release_switch_row_count"]
            ),
            "runtime_frontend_enablement_release_switch_blocking_row_count": (
                runtime_frontend_enablement_release_switch_contract["blocking_release_switch_row_count"]
            ),
            "runtime_frontend_enablement_release_switch_effective_allowed": False,
            "runtime_frontend_enablement_release_switch_is_production_evidence": False,
            "runtime_frontend_enablement_config_promotion_contract_visible": True,
            "runtime_frontend_enablement_config_promotion_step_count": (
                runtime_frontend_enablement_config_promotion_contract["promotion_step_count"]
            ),
            "runtime_frontend_enablement_config_promotion_pending_step_count": (
                runtime_frontend_enablement_config_promotion_contract["pending_promotion_step_count"]
            ),
            "runtime_frontend_enablement_config_promotion_effective_allowed": False,
            "runtime_frontend_enablement_config_promotion_is_production_evidence": False,
            "runtime_mode_acceptance_contract_visible": True,
            "runtime_mode_acceptance_row_count": runtime_mode_acceptance_contract["acceptance_row_count"],
            "runtime_mode_acceptance_is_production_evidence": False,
            "live_light_rollout_roadmap_contract_visible": True,
            "live_light_rollout_roadmap_stage_count": live_light_rollout_roadmap_contract["stage_count"],
            "live_light_rollout_next_implementation_stage_key": (
                live_light_rollout_roadmap_contract["next_implementation_stage_key"]
            ),
            "live_light_rollout_next_execution_request_stage_key": (
                live_light_rollout_roadmap_contract["next_execution_request_stage_key"]
            ),
            "live_light_rollout_execution_request_receipt_service_ready": (
                live_light_rollout_roadmap_contract["execution_request_receipt_service_ready"]
            ),
            "live_light_rollout_execution_request_operator_readiness_visible": (
                live_light_rollout_roadmap_contract["execution_request_operator_readiness_visible"]
            ),
            "live_light_rollout_execution_request_route_pending": (
                live_light_rollout_roadmap_contract["execution_request_route_pending"]
            ),
            "live_light_rollout_execution_request_provider_model_task_creation_allowed": (
                live_light_rollout_roadmap_contract[
                    "execution_request_provider_model_task_creation_allowed"
                ]
            ),
            "live_light_rollout_roadmap_is_production_evidence": False,
            "task_creation_invariant_contract_visible": True,
            "task_creation_invariant_surface_row_count": task_creation_invariant_contract["surface_row_count"],
            "task_creation_invariant_allowed_surface_count": (
                task_creation_invariant_contract["allowed_task_surface_count"]
            ),
            "task_creation_invariant_is_production_evidence": False,
            "live_light_background_task_auto_trigger_allowed": background_task_contract["auto_trigger_allowed"],
            "live_light_background_task_creates_or_reuses_task_only": True,
            "live_light_background_task_rate_limit_reuses_existing_task": True,
            "live_light_background_task_scope_light_only": True,
            "live_light_background_task_full_pool_scope_allowed": False,
            "live_light_background_task_payload_safe_only": True,
            "live_light_startup_autostart_readiness_contract_visible": True,
            "live_light_startup_autostart_readiness_row_count": (
                live_light_startup_autostart_readiness_contract["readiness_row_count"]
            ),
            "live_light_startup_autostart_condition_satisfied_row_count": (
                live_light_startup_autostart_readiness_contract["condition_satisfied_row_count"]
            ),
            "live_light_startup_autostart_frontend_wiring_implemented": False,
            "live_light_startup_autostart_browser_evidence_complete": False,
            "live_light_startup_autostart_effective_allowed": False,
            "live_light_startup_autostart_readiness_is_production_evidence": False,
            "live_light_unified_startup_task_contract_visible": True,
            "live_light_unified_startup_task_stage_count": (
                live_light_unified_startup_task_contract["stage_count"]
            ),
            "live_light_unified_startup_task_route": live_light_unified_startup_task_contract["task_route"],
            "live_light_unified_startup_task_provider_execution_implemented": False,
            "live_light_unified_startup_task_model_execution_implemented": False,
            "live_light_unified_startup_task_worker_dispatch_implemented": False,
            "live_light_unified_startup_task_is_production_evidence": False,
            "live_light_scope_intake_contract_visible": True,
            "live_light_scope_intake_symbol_dedupe_required": True,
            "live_light_scope_intake_scope_hash_required": True,
            "live_light_scope_intake_search_typing_creates_task": False,
            "live_light_scope_intake_secret_like_payload_fields_dropped": True,
            "live_light_scope_intake_is_production_evidence": False,
            "live_light_stage_dependency_contract_visible": True,
            "live_light_stage_dependency_deepseek_requires_data_ready": True,
            "live_light_stage_dependency_safe_skip_required": True,
            "live_light_stage_dependency_executor_implemented": False,
            "live_light_stage_dependency_contract_is_production_evidence": False,
            "live_light_freshness_provider_gap_contract_visible": True,
            "live_light_freshness_state_visible_required": True,
            "live_light_provider_gap_visible_required": True,
            "live_light_stale_cache_label_required": True,
            "live_light_empty_or_no_record_is_verified": False,
            "live_light_freshness_provider_gap_contract_is_production_evidence": False,
            "live_light_task_lifecycle_contract_visible": True,
            "live_light_task_status_polling_required": True,
            "live_light_task_status_route_read_only": True,
            "live_light_task_status_get_creates_task": False,
            "live_light_task_success_is_provider_model_evidence": False,
            "live_light_task_success_is_production_evidence": False,
            "live_light_task_queue_budget_contract_visible": True,
            "live_light_task_queue_budget_row_count": live_light_task_queue_budget_contract["queue_row_count"],
            "live_light_task_queue_budget_condition_satisfied_row_count": (
                live_light_task_queue_budget_contract["condition_satisfied_row_count"]
            ),
            "live_light_task_queue_budget_max_active_local_startup_tasks_per_session": (
                live_light_task_queue_budget_contract["max_active_local_startup_tasks_per_session"]
            ),
            "live_light_task_queue_budget_unbounded_queue_allowed": False,
            "live_light_task_queue_budget_status_get_creates_task": False,
            "live_light_task_queue_budget_task_polling_creates_task": False,
            "live_light_task_queue_budget_creates_provider_model_task": False,
            "live_light_task_queue_budget_is_production_evidence": False,
            "live_light_task_control_contract_visible": True,
            "live_light_task_control_manual_only": True,
            "live_light_task_control_auto_retry_enabled": False,
            "live_light_task_control_is_production_evidence": False,
            "live_light_operator_status_contract_visible": True,
            "live_light_operator_status_current_mode_visible_required": True,
            "live_light_operator_status_effective_source_switches_visible_required": True,
            "live_light_operator_status_external_execution_profile_visible_required": True,
            "live_light_operator_status_external_execution_profile": live_light_operator_status_contract[
                "external_execution_profile"
            ],
            "live_light_operator_status_profile_provider_stage_allowed": live_light_operator_status_contract[
                "external_execution_profile_provider_stage_allowed"
            ],
            "live_light_operator_status_profile_model_stage_allowed": live_light_operator_status_contract[
                "external_execution_profile_model_stage_allowed"
            ],
            "live_light_operator_status_profile_executor_implemented": False,
            "live_light_operator_status_profile_calls_provider_model_now": False,
            "live_light_operator_status_profile_source_rate_summary_visible": True,
            "live_light_operator_status_latest_task_status_visible_required": True,
            "live_light_operator_status_rate_limit_skipped_visible_required": True,
            "live_light_operator_status_safe_error_visible_required": True,
            "live_light_operator_status_read_only": True,
            "live_light_operator_status_is_production_evidence": False,
            "live_light_latest_bootstrap_task_status_visible": True,
            "live_light_latest_bootstrap_task_lookup_creates_task": False,
            "live_light_latest_bootstrap_task_success_is_provider_model_evidence": False,
            "live_light_latest_bootstrap_task_is_production_evidence": False,
            "live_light_latest_bootstrap_local_compute_handoff_visible": True,
            "live_light_latest_bootstrap_local_compute_handoff_lookup_creates_task": False,
            "live_light_latest_bootstrap_local_compute_handoff_executes_compute": False,
            "live_light_latest_bootstrap_local_compute_handoff_writes_output": False,
            "live_light_latest_bootstrap_local_compute_handoff_is_execution_evidence": False,
            "live_light_latest_bootstrap_local_compute_handoff_is_production_evidence": False,
            "live_light_promotion_gate_contract_visible": True,
            "live_light_promotion_gate_real_provider_model_evidence_complete": False,
            "live_light_promotion_gate_remote_ci_green": False,
            "live_light_promotion_gate_ready_for_release": False,
            "live_light_promotion_gate_contract_is_production_evidence": False,
            "live_light_worker_dispatch_contract_visible": True,
            "live_light_worker_dispatch_celery_implemented": False,
            "live_light_worker_dispatch_provider_requires_execution_request": True,
            "live_light_worker_dispatch_model_requires_execution_request": True,
            "live_light_worker_dispatch_is_production_evidence": False,
            "search_quant_projection_workflow_contract_visible": True,
            "search_quant_projection_search_input_creates_task": False,
            "search_quant_projection_requires_explicit_search_action": True,
            "search_quant_projection_submit_autostart_contract_visible": True,
            "search_quant_projection_submit_autostart_allowed": search_quant_projection_submit_autostart_contract[
                "live_light_search_submit_auto_start_allowed"
            ],
            "search_quant_projection_submit_autostart_config_switch": (
                "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"
            ),
            "search_quant_projection_submit_autostart_configured": search_submit_autostart_on_submit,
            "search_quant_projection_submit_autostart_effective": effective_search_submit_autostart,
            "search_quant_projection_submit_autostart_config_handoff_visible": True,
            "search_quant_projection_submit_autostart_local_env_fallback_available": (
                search_quant_projection_submit_autostart_config_handoff_contract[
                    "bootstrap_local_env_fallback_available"
                ]
            ),
            "search_quant_projection_submit_autostart_global_config_allowlist_promoted": (
                search_quant_projection_submit_autostart_config_handoff_contract[
                    "global_config_allowlist_promoted"
                ]
            ),
            "search_quant_projection_submit_autostart_config_allowlist_promotion_pending": (
                search_quant_projection_submit_autostart_config_handoff_contract[
                    "global_config_allowlist_promotion_pending"
                ]
            ),
            "search_quant_projection_submit_autostart_config_handoff_is_production_evidence": False,
            "search_quant_projection_submit_autostart_config_promotion_contract_visible": True,
            "search_quant_projection_submit_autostart_config_promotion_step_count": (
                search_quant_projection_submit_autostart_config_promotion_contract["promotion_step_count"]
            ),
            "search_quant_projection_submit_autostart_config_py_update_pending": (
                search_quant_projection_submit_autostart_config_promotion_contract["config_py_update_pending"]
            ),
            "search_quant_projection_submit_autostart_bootstrap_fallback_removal_pending": (
                search_quant_projection_submit_autostart_config_promotion_contract[
                    "bootstrap_local_env_fallback_removal_pending"
                ]
            ),
            "search_quant_projection_submit_autostart_config_promotion_is_production_evidence": False,
            "search_quant_projection_submit_autostart_search_typing_creates_task": False,
            "search_quant_projection_submit_autostart_provider_model_without_request_allowed": False,
            "search_quant_projection_submit_autostart_backend_ready": True,
            "search_quant_projection_submit_autostart_frontend_wiring_implemented": False,
            "search_quant_projection_submit_autostart_task_catalog_covered": True,
            "search_quant_projection_submit_autostart_latest_status_lookup_creates_task": False,
            "search_quant_projection_submit_autostart_is_production_evidence": False,
            "search_quant_projection_manual_button_frontend_wiring_implemented": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "manual_button_frontend_wiring_implemented"
                ]
            ),
            "search_quant_projection_manual_confirm_button_frontend_wiring_implemented": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "manual_confirm_button_frontend_wiring_implemented"
                ]
            ),
            "search_quant_projection_manual_confirm_button_runtime_ready": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "manual_confirm_button_runtime_ready"
                ]
            ),
            "search_quant_projection_manual_confirm_button_status": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "manual_confirm_button_status"
                ]
            ),
            "search_quant_projection_p1_manual_confirm_path_ready": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "p1_manual_confirm_path_ready"
                ]
            ),
            "search_quant_projection_p1_manual_confirm_path_status": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "p1_manual_confirm_path_status"
                ]
            ),
            "search_quant_projection_frontend_runtime_wiring_implemented": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "frontend_runtime_wiring_implemented"
                ]
            ),
            "search_quant_projection_frontend_runtime_wiring_scope": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "frontend_runtime_wiring_scope"
                ]
            ),
            "search_quant_projection_manual_button_task_status_polling_bound": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "manual_button_task_status_polling_bound"
                ]
            ),
            "search_quant_projection_manual_button_path_is_production_evidence": False,
            "search_quant_projection_manual_button_path_calls_provider_or_model_from_frontend": False,
            "search_quant_projection_frontend_wiring_acceptance_contract_visible": True,
            "search_quant_projection_frontend_wiring_mode_matrix_visible": True,
            "search_quant_projection_frontend_wiring_active_mode_behavior": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "active_mode_expected_frontend_behavior"
                ]
            ),
            "search_quant_projection_frontend_wiring_browser_acceptance_evidence_required": True,
            "search_quant_projection_frontend_wiring_browser_network_trace_required": True,
            "search_quant_projection_frontend_wiring_failure_recovery_evidence_required": True,
            "search_quant_projection_frontend_wiring_unbounded_task_queue_allowed": False,
            "search_quant_projection_frontend_wiring_implemented": False,
            "search_quant_projection_full_frontend_wiring_implemented": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "full_frontend_wiring_implemented"
                ]
            ),
            "search_quant_projection_full_frontend_wiring_pending_reason": (
                search_quant_projection_frontend_wiring_acceptance_contract[
                    "full_frontend_wiring_pending_reason"
                ]
            ),
            "search_quant_projection_frontend_wiring_requires_task_status_polling": True,
            "search_quant_projection_frontend_wiring_browser_evidence_complete": False,
            "search_quant_projection_frontend_wiring_is_production_evidence": False,
            "search_quant_projection_unified_startup_handoff_contract_visible": True,
            "search_quant_projection_unified_startup_handoff_row_count": (
                search_quant_projection_unified_startup_handoff_contract["handoff_row_count"]
            ),
            "search_quant_projection_unified_startup_handoff_implemented": False,
            "search_quant_projection_unified_startup_task_created_now": False,
            "search_quant_projection_unified_startup_handoff_is_production_evidence": False,
            "search_quant_projection_provider_model_route_button_gated": True,
            "search_quant_projection_production_complete": False,
            "search_quant_projection_result_surface_contract_visible": True,
            "search_quant_projection_result_surfaces_research_only": True,
            "search_quant_projection_result_surface_trade_instruction_allowed": False,
            "search_quant_projection_result_surface_contract_is_production_evidence": False,
            "search_quant_projection_factor_next_handoff_contract_visible": True,
            "search_quant_projection_factor_next_handoff_row_count": (
                search_quant_projection_factor_next_handoff_contract["handoff_row_count"]
            ),
            "search_quant_projection_factor_next_handoff_requires_call_ledger_or_gap": True,
            "search_quant_projection_factor_next_handoff_requires_cache_lineage": True,
            "search_quant_projection_factor_next_handoff_feeds_deepseek_readiness": True,
            "search_quant_projection_factor_next_executes_local_compute_now": False,
            "search_quant_projection_factor_next_writes_cache_now": False,
            "search_quant_projection_factor_next_handoff_is_production_evidence": False,
            "search_quant_projection_cache_write_preflight_contract_visible": True,
            "search_quant_projection_cache_write_preflight_row_count": (
                search_quant_projection_cache_write_preflight_contract["preflight_row_count"]
            ),
            "search_quant_projection_cache_write_preflight_requires_scope_hash_match": True,
            "search_quant_projection_cache_write_preflight_requires_cache_lineage": True,
            "search_quant_projection_cache_write_preflight_requires_no_overwrite_guard": True,
            "search_quant_projection_cache_write_preflight_feeds_deepseek_readiness": True,
            "search_quant_projection_cache_write_preflight_writes_cache_now": False,
            "search_quant_projection_cache_write_preflight_is_production_evidence": False,
            "search_quant_projection_deepseek_model_preflight_contract_visible": True,
            "search_quant_projection_deepseek_model_preflight_row_count": (
                search_quant_projection_deepseek_model_preflight_contract["preflight_row_count"]
            ),
            "search_quant_projection_deepseek_model_preflight_requires_cache_write_preflight": True,
            "search_quant_projection_deepseek_model_preflight_requires_model_ledger": True,
            "search_quant_projection_deepseek_model_preflight_raw_prompt_or_output_visible_allowed": False,
            "search_quant_projection_deepseek_model_preflight_calls_model_now": False,
            "search_quant_projection_deepseek_model_preflight_is_production_evidence": False,
            "search_quant_projection_deepseek_output_acceptance_contract_visible": True,
            "search_quant_projection_deepseek_output_acceptance_row_count": (
                search_quant_projection_deepseek_output_acceptance_contract["acceptance_row_count"]
            ),
            "search_quant_projection_deepseek_output_acceptance_requires_model_preflight": True,
            "search_quant_projection_deepseek_output_acceptance_requires_parse_and_sanitizer": True,
            "search_quant_projection_deepseek_output_acceptance_raw_prompt_or_output_visible_allowed": False,
            "search_quant_projection_deepseek_output_acceptance_is_model_correctness_evidence": False,
            "search_quant_projection_deepseek_output_acceptance_is_production_evidence": False,
            "search_quant_projection_deepseek_readiness_contract_visible": True,
            "search_quant_projection_deepseek_readiness_row_count": (
                search_quant_projection_deepseek_readiness_contract["readiness_row_count"]
            ),
            "search_quant_projection_deepseek_ready_now_row_count": (
                search_quant_projection_deepseek_readiness_contract["ready_now_row_count"]
            ),
            "search_quant_projection_deepseek_requires_provider_factor_next_ready": True,
            "search_quant_projection_deepseek_requires_model_ledger": True,
            "search_quant_projection_deepseek_calls_model_now": False,
            "search_quant_projection_deepseek_is_production_evidence": False,
            "search_quant_projection_latest_status_visible": True,
            "search_quant_projection_latest_lookup_creates_task": False,
            "search_quant_projection_latest_is_production_evidence": False,
            "search_quant_projection_provider_model_latest_status_visible": True,
            "search_quant_projection_provider_model_latest_lookup_creates_task": False,
            "search_quant_projection_provider_model_latest_status_get_external_calls": False,
            "search_quant_projection_provider_model_latest_requires_deepseek_output_acceptance": True,
            "search_quant_projection_provider_model_latest_output_cache_write_requires_acceptance": True,
            "search_quant_projection_provider_model_latest_task_success_is_model_output_evidence": (
                search_quant_projection_provider_model_latest_status["task_success_is_model_output_evidence"]
            ),
            "search_quant_projection_provider_model_latest_task_success_is_provider_model_evidence": False,
            "search_quant_projection_provider_model_latest_is_production_evidence": False,
            "tushare_light_strategy_contract_visible": True,
            "tushare_light_strategy_provider_execution_pending": True,
            "tushare_light_strategy_matrix_or_receipt_is_provider_evidence": False,
            "tushare_light_strategy_no_record_is_negative_evidence": False,
            "tushare_light_strategy_unselected_api_verified_allowed": False,
            "deepseek_pro_strategy_contract_visible": True,
            "deepseek_pro_strategy_model_execution_pending": True,
            "deepseek_pro_strategy_deepseek_is_data_source": False,
            "deepseek_pro_strategy_numeric_or_action_overwrite_allowed": False,
            "deepseek_pro_strategy_sanitizer_is_model_correctness_evidence": False,
            "ui_nonblocking_runtime_contract_visible": True,
            "live_light_local_fallback_contract_visible": True,
            "live_light_local_fallback_uses_last_good_cache_allowed": True,
            "live_light_local_fallback_stale_cache_label_required": True,
            "live_light_local_fallback_provider_gap_visible_required": True,
            "live_light_local_fallback_is_production_evidence": False,
            "live_light_cache_lineage_contract_visible": True,
            "live_light_cache_lineage_required_for_outputs": True,
            "live_light_cache_lineage_written_by_post_task_only": True,
            "live_light_memory_only_lineage_is_durable_evidence": False,
            "live_light_output_surface_contract_visible": True,
            "live_light_output_surface_written_by_post_task_only": True,
            "live_light_output_surface_count": live_light_output_surface_contract["output_surface_count"],
            "live_light_factor_quant_hub_output_surface_required": True,
            "live_light_next_session_output_surface_required": True,
            "live_light_deepseek_explanation_output_surface_governed": True,
            "live_light_output_surface_contract_is_production_evidence": False,
            "live_light_runtime_budget_contract_visible": True,
            "live_light_runtime_budget_token_usage_required": True,
            "live_light_runtime_budget_cache_hit_skips_provider_call_allowed": True,
            "live_light_runtime_budget_input_hash_dedupe_required": True,
            "live_light_runtime_budget_rate_limit_reuses_existing_task": True,
            "live_light_runtime_budget_enforcement_implemented": False,
            "live_light_runtime_budget_contract_is_production_evidence": False,
            "live_light_evidence_grade_contract_visible": True,
            "live_light_credential_preflight_contract_visible": True,
            "live_light_status_get_checks_credential_presence": False,
            "live_light_credential_presence_check_requires_post": True,
            "live_light_credential_presence_check_requires_user_approval": True,
            "live_light_credential_values_exposed": False,
            "live_light_provider_model_execution_request_contract_visible": True,
            "live_light_provider_model_acceptance_requires_execution_request": True,
            "live_light_provider_model_execution_request_implemented": (
                live_light_provider_model_execution_request_contract["execution_request_route_implemented"]
            ),
            "live_light_dry_run_is_execution_request": False,
            "live_light_execution_request_requires_latest_scope_hash": True,
            "live_light_execution_request_requires_user_confirmation": True,
            "live_light_execution_request_handoff_contract_visible": True,
            "live_light_execution_request_handoff_route_implemented": (
                live_light_execution_request_handoff_contract["execution_request_route_implemented"]
            ),
            "live_light_execution_request_receipt_service_implemented": True,
            "live_light_execution_request_receipt_persists_to_task_status": True,
            "live_light_execution_request_route_adapter_contract_visible": True,
            "live_light_execution_request_route_adapter_target_file": live_light_execution_request_handoff_contract[
                "route_adapter_target_file"
            ],
            "live_light_execution_request_route_adapter_service_function": (
                live_light_execution_request_handoff_contract["route_adapter_service_function"]
            ),
            "live_light_execution_request_route_adapter_response_envelope": (
                live_light_execution_request_handoff_contract["route_adapter_response_envelope"]
            ),
            "live_light_execution_request_route_adapter_current_status": (
                live_light_execution_request_handoff_contract["route_adapter_current_status"]
            ),
            "live_light_execution_request_route_adapter_provider_model_task_creation_allowed": False,
            "live_light_execution_request_route_adapter_calls_provider_or_model": False,
            "live_light_latest_acceptance_dry_run_status_visible": True,
            "live_light_latest_acceptance_dry_run_lookup_creates_task": False,
            "live_light_latest_acceptance_dry_run_is_production_evidence": False,
            "live_light_latest_execution_request_status_visible": True,
            "live_light_latest_execution_request_lookup_creates_task": False,
            "live_light_latest_execution_request_is_production_evidence": False,
            "live_light_execution_request_handoff_requires_durable_receipt": True,
            "live_light_execution_request_scope_hash_mismatch_blocks_handoff": True,
            "live_light_execution_request_handoff_is_production_evidence": False,
            "live_light_local_artifacts_are_production_evidence": False,
            "live_light_production_evidence_pending": True,
            "live_light_mock_receipt_matrix_sanitizer_can_promote": False,
            "live_light_ledger_contract_visible": True,
            "live_light_call_ledger_required": True,
            "live_light_model_ledger_required": True,
            "live_light_redaction_review_required_before_promotion": True,
            "live_light_production_promotion_allowed_without_ledger": False,
            "live_light_ledger_redaction_invariant_contract_visible": True,
            "live_light_ledger_redaction_prohibited_surface_count": (
                live_light_ledger_redaction_invariant_contract["prohibited_surface_count"]
            ),
            "live_light_ledger_redaction_required_ledger_row_count": (
                live_light_ledger_redaction_invariant_contract["required_ledger_row_count"]
            ),
            "live_light_ledger_redaction_review_required_before_promotion": True,
            "live_light_ledger_redaction_raw_payload_exposed": False,
            "live_light_ledger_redaction_credential_material_exposed": False,
            "live_light_ledger_redaction_invariant_is_production_evidence": False,
            "ui_nonblocking_cache_first_render_required": True,
            "ui_nonblocking_task_polling_required": True,
            "ui_nonblocking_browser_runtime_evidence_complete": False,
            "live_full_reserved_contract_visible": True,
            "live_light_ready_for_provider_execution_design": True,
            "live_light_ready_for_acceptance_design": True,
            "live_light_ready_for_user_approved_acceptance_dry_run_task": True,
            "live_light_ready_for_user_approved_acceptance_task": False,
            "live_light_ready_for_provider_execution": False,
            "live_light_ready_for_model_execution": False,
            "live_light_provider_execution_implemented": False,
            "production_live_light_complete": False,
            "live_full_enabled": False,
            "live_full_reserved": True,
            "live_full_requires_separate_authorization": True,
            "live_full_full_pool_on_open_allowed": False,
            "full_pool_on_open_allowed": False,
            "github_probe_on_open_allowed": False,
            "does_not_call_tushare": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_read_api_keys": True,
            "does_not_expose_credentials": True,
            "raw_config_values_exposed": False,
            "safe_config_contract_visible": True,
            "runtime_config_reference_contract_visible": True,
            "runtime_config_reference_row_count": runtime_config_reference_contract["config_reference_row_count"],
            "runtime_config_reference_source_switch_count": runtime_config_reference_contract["source_switch_count"],
            "runtime_config_reference_audit_id": runtime_config_reference_contract["config_audit_id"],
            "runtime_config_reference_audit_uses_safe_rows_only": True,
            "runtime_config_reference_is_production_evidence": False,
            "runtime_config_ownership_invariant_contract_visible": True,
            "runtime_config_ownership_row_count": runtime_config_ownership_invariant_contract[
                "ownership_row_count"
            ],
            "runtime_config_ownership_audit_id": runtime_config_ownership_invariant_contract["ownership_audit_id"],
            "runtime_config_ownership_linked_reference_audit_id": runtime_config_ownership_invariant_contract[
                "linked_runtime_config_reference_audit_id"
            ],
            "runtime_config_bootstrap_local_env_fallback_count": (
                runtime_config_ownership_invariant_contract["bootstrap_local_env_fallback_count"]
            ),
            "runtime_config_frontend_writeback_allowed": False,
            "runtime_config_production_config_complete": False,
            "runtime_config_ownership_invariant_is_production_evidence": False,
            "runtime_operator_summary_contract_visible": True,
            "runtime_operator_active_mode": runtime_operator_summary_contract["mode"],
            "runtime_operator_active_display_status": runtime_operator_summary_contract["active_mode_display_status"],
            "runtime_operator_release_blocker_summary_visible": True,
            "runtime_operator_release_remote_ci_status_known": runtime_operator_summary_contract[
                "release_remote_ci_status_known"
            ],
            "runtime_operator_release_remote_ci_green": runtime_operator_summary_contract[
                "release_remote_ci_green"
            ],
            "runtime_operator_release_github_api_called": runtime_operator_summary_contract[
                "release_github_api_called"
            ],
            "runtime_operator_release_fresh_local_gate_run_required": runtime_operator_summary_contract[
                "release_fresh_local_gate_run_required"
            ],
            "runtime_operator_release_production_promotion_review_required": runtime_operator_summary_contract[
                "release_production_promotion_review_required"
            ],
            "runtime_operator_release_ready_for_promotion": runtime_operator_summary_contract[
                "release_ready_for_promotion"
            ],
            "runtime_operator_release_local_contracts_are_production_evidence": runtime_operator_summary_contract[
                "release_local_contracts_are_production_evidence"
            ],
            "runtime_operator_release_blocker_summary_is_production_evidence": False,
            "runtime_operator_trigger_policy_summary_visible": True,
            "runtime_operator_active_page_open_task_allowed": runtime_operator_summary_contract[
                "active_page_open_task_allowed"
            ],
            "runtime_operator_active_search_submit_task_allowed": runtime_operator_summary_contract[
                "active_search_submit_task_allowed"
            ],
            "runtime_operator_active_manual_button_task_allowed": runtime_operator_summary_contract[
                "active_manual_button_task_allowed"
            ],
            "runtime_operator_active_live_light_background_task_allowed": runtime_operator_summary_contract[
                "active_live_light_background_task_allowed"
            ],
            "runtime_operator_active_provider_model_execution_allowed": runtime_operator_summary_contract[
                "active_provider_model_execution_allowed"
            ],
            "runtime_operator_active_provider_model_execution_surface": runtime_operator_summary_contract[
                "active_provider_model_execution_surface"
            ],
            "runtime_operator_active_provider_model_direct_execution_allowed": runtime_operator_summary_contract[
                "active_provider_model_direct_execution_allowed"
            ],
            "runtime_operator_active_provider_model_requires_explicit_post_task": (
                runtime_operator_summary_contract["active_provider_model_requires_explicit_post_task"]
            ),
            "runtime_operator_active_provider_model_execution_requires_task_contract": (
                runtime_operator_summary_contract["active_provider_model_execution_requires_task_contract"]
            ),
            "runtime_operator_active_provider_model_execution_requires_execution_request": (
                runtime_operator_summary_contract["active_provider_model_execution_requires_execution_request"]
            ),
            "runtime_operator_active_full_pool_or_deep_scan_allowed": runtime_operator_summary_contract[
                "active_full_pool_or_deep_scan_allowed"
            ],
            "runtime_operator_trigger_policy_summary_is_production_evidence": False,
            "runtime_operator_config_reference_audit_id": runtime_operator_summary_contract[
                "config_reference_audit_id"
            ],
            "runtime_operator_config_ownership_audit_id": runtime_operator_summary_contract[
                "config_ownership_audit_id"
            ],
            "runtime_operator_config_audit_uses_safe_rows_only": True,
            "runtime_operator_external_execution_profile": runtime_operator_summary_contract[
                "effective_external_execution_profile"
            ],
            "runtime_operator_profile_provider_stage_allowed": runtime_operator_summary_contract[
                "external_execution_profile_provider_stage_allowed"
            ],
            "runtime_operator_profile_model_stage_allowed": runtime_operator_summary_contract[
                "external_execution_profile_model_stage_allowed"
            ],
            "runtime_operator_provider_model_enablement_summary_visible": runtime_operator_summary_contract[
                "provider_model_enablement_summary_visible"
            ],
            "runtime_operator_provider_model_enablement_source_config": runtime_operator_summary_contract[
                "provider_model_enablement_source_config"
            ],
            "runtime_operator_provider_model_enablement_configured": runtime_operator_summary_contract[
                "provider_model_enablement_configured"
            ],
            "runtime_operator_provider_model_enablement_effective": runtime_operator_summary_contract[
                "provider_model_enablement_effective"
            ],
            "runtime_operator_provider_model_enablement_requires_live_light": runtime_operator_summary_contract[
                "provider_model_enablement_requires_live_light"
            ],
            "runtime_operator_provider_model_enablement_requires_execution_request": (
                runtime_operator_summary_contract[
                    "provider_model_enablement_requires_execution_request"
                ]
            ),
            "runtime_operator_provider_model_enablement_requires_promotion": runtime_operator_summary_contract[
                "provider_model_enablement_requires_promotion"
            ],
            "runtime_operator_provider_model_enablement_creates_provider_model_task": (
                runtime_operator_summary_contract[
                    "provider_model_enablement_creates_provider_model_task"
                ]
            ),
            "runtime_operator_provider_model_enablement_calls_provider_model_now": (
                runtime_operator_summary_contract["provider_model_enablement_calls_provider_model_now"]
            ),
            "runtime_operator_provider_model_enablement_is_production_evidence": False,
            "runtime_operator_profile_source_rate_summary_visible": True,
            "runtime_operator_profile_source_rate_summary_status": runtime_operator_summary_contract[
                "operator_profile_source_rate_summary_status"
            ],
            "runtime_operator_rate_limit_seconds_visible_safe": runtime_operator_summary_contract[
                "operator_rate_limit_seconds_visible_safe"
            ],
            "runtime_operator_task_control_visible": runtime_operator_summary_contract[
                "task_control_contract_visible"
            ],
            "runtime_operator_task_control_row_count": runtime_operator_summary_contract["task_control_row_count"],
            "runtime_operator_task_control_manual_only": runtime_operator_summary_contract["task_control_manual_only"],
            "runtime_operator_task_control_auto_retry_enabled": runtime_operator_summary_contract[
                "task_control_auto_retry_enabled"
            ],
            "runtime_operator_task_control_is_production_evidence": False,
            "runtime_operator_summary_row_count": runtime_operator_summary_contract["summary_row_count"],
            "runtime_operator_summary_is_production_evidence": False,
            "runtime_operator_cache_first_polling_summary_visible": runtime_operator_summary_contract[
                "cache_first_polling_summary_visible"
            ],
            "runtime_operator_cache_first_polling_source_contract": runtime_operator_summary_contract[
                "cache_first_polling_source_contract"
            ],
            "runtime_operator_cache_first_polling_phase_count": runtime_operator_summary_contract[
                "cache_first_polling_phase_count"
            ],
            "runtime_operator_cache_first_polling_cache_first_render_required": runtime_operator_summary_contract[
                "cache_first_polling_cache_first_render_required"
            ],
            "runtime_operator_cache_first_polling_task_polling_required": runtime_operator_summary_contract[
                "cache_first_polling_task_polling_required"
            ],
            "runtime_operator_cache_first_polling_last_good_cache_required": runtime_operator_summary_contract[
                "cache_first_polling_last_good_cache_required"
            ],
            "runtime_operator_cache_first_polling_browser_evidence_complete": runtime_operator_summary_contract[
                "cache_first_polling_browser_evidence_complete"
            ],
            "runtime_operator_cache_first_polling_summary_is_production_evidence": False,
            "runtime_external_silence_contract_visible": True,
            "runtime_external_silence_row_count": runtime_external_silence_contract["silence_row_count"],
            "runtime_external_silence_direct_external_call_allowed_count": (
                runtime_external_silence_contract["direct_external_call_allowed_count"]
            ),
            "runtime_external_silence_is_production_evidence": False,
            "runtime_hard_boundary_contract_visible": True,
            "runtime_hard_boundary_row_count": runtime_hard_boundary_contract["boundary_row_count"],
            "runtime_hard_boundary_blocking_count": runtime_hard_boundary_contract["blocking_boundary_count"],
            "runtime_hard_boundary_get_cache_external_calls_allowed": False,
            "runtime_hard_boundary_react_render_provider_calls_allowed": False,
            "runtime_hard_boundary_fastapi_startup_external_calls_allowed": False,
            "runtime_hard_boundary_post_task_worker_local_fallback_required": True,
            "runtime_hard_boundary_call_ledger_required": True,
            "runtime_hard_boundary_model_ledger_required_for_deepseek": True,
            "runtime_hard_boundary_deepseek_is_data_source": False,
            "runtime_hard_boundary_real_trading_allowed": False,
            "runtime_hard_boundary_token_key_frontend_log_packet_cache_allowed": False,
            "runtime_hard_boundary_contract_is_production_evidence": False,
            "runtime_cache_first_polling_contract_visible": True,
            "runtime_cache_first_polling_phase_count": runtime_cache_first_polling_contract["phase_count"],
            "runtime_cache_first_polling_cache_first_render_required": True,
            "runtime_cache_first_polling_task_polling_required": True,
            "runtime_cache_first_polling_last_good_cache_required": True,
            "runtime_cache_first_polling_browser_evidence_complete": False,
            "runtime_cache_first_polling_is_production_evidence": False,
            "runtime_frontend_enablement_gate_contract_visible": True,
            "runtime_frontend_enablement_allowed": False,
            "runtime_frontend_enablement_blocking_row_count": runtime_frontend_enablement_gate_contract[
                "blocking_row_count"
            ],
            "runtime_frontend_enablement_target_stage_key": runtime_frontend_enablement_gate_contract[
                "target_stage_key"
            ],
            "runtime_frontend_enablement_browser_evidence_complete": False,
            "runtime_frontend_enablement_is_production_evidence": False,
            "runtime_browser_evidence_contract_visible": True,
            "runtime_browser_evidence_row_count": runtime_browser_evidence_contract["evidence_row_count"],
            "runtime_browser_evidence_network_trace_required": True,
            "runtime_browser_evidence_complete": False,
            "runtime_browser_evidence_blocking_row_count": runtime_browser_evidence_contract[
                "blocking_evidence_row_count"
            ],
            "runtime_browser_evidence_is_production_evidence": False,
            "runtime_frontend_wiring_manifest_contract_visible": True,
            "runtime_frontend_wiring_manifest_row_count": runtime_frontend_wiring_manifest_contract[
                "manifest_row_count"
            ],
            "runtime_frontend_wiring_manifest_done_row_count": runtime_frontend_wiring_manifest_contract[
                "implementation_done_row_count"
            ],
            "runtime_frontend_wiring_manifest_pending_row_count": runtime_frontend_wiring_manifest_contract[
                "pending_manifest_row_count"
            ],
            "runtime_frontend_wiring_manifest_manual_button_implemented": runtime_frontend_wiring_manifest_contract[
                "manual_button_manifest_implemented"
            ],
            "runtime_frontend_wiring_manifest_implemented": False,
            "runtime_frontend_wiring_manifest_is_production_evidence": False,
            "runtime_frontend_acceptance_runbook_contract_visible": True,
            "runtime_frontend_acceptance_runbook_row_count": runtime_frontend_acceptance_runbook_contract[
                "runbook_row_count"
            ],
            "runtime_frontend_acceptance_runbook_pending_row_count": (
                runtime_frontend_acceptance_runbook_contract["pending_runbook_row_count"]
            ),
            "runtime_frontend_acceptance_runbook_complete": False,
            "runtime_frontend_acceptance_runbook_is_production_evidence": False,
            "runtime_frontend_acceptance_artifact_contract_visible": True,
            "runtime_frontend_acceptance_artifact_row_count": runtime_frontend_acceptance_artifact_contract[
                "artifact_row_count"
            ],
            "runtime_frontend_acceptance_artifact_pending_count": runtime_frontend_acceptance_artifact_contract[
                "pending_artifact_count"
            ],
            "runtime_frontend_acceptance_artifact_redaction_review_required": True,
            "runtime_frontend_acceptance_artifact_collection_complete": False,
            "runtime_frontend_acceptance_artifact_is_production_evidence": False,
            "runtime_frontend_enablement_promotion_contract_visible": True,
            "runtime_frontend_enablement_promotion_row_count": runtime_frontend_enablement_promotion_contract[
                "promotion_row_count"
            ],
            "runtime_frontend_enablement_promotion_blocking_row_count": (
                runtime_frontend_enablement_promotion_contract["blocking_promotion_row_count"]
            ),
            "runtime_frontend_enablement_promotion_allowed": False,
            "runtime_frontend_enablement_promotion_is_production_evidence": False,
            "runtime_frontend_enablement_release_switch_contract_visible": True,
            "runtime_frontend_enablement_release_switch_row_count": (
                runtime_frontend_enablement_release_switch_contract["release_switch_row_count"]
            ),
            "runtime_frontend_enablement_release_switch_blocking_row_count": (
                runtime_frontend_enablement_release_switch_contract["blocking_release_switch_row_count"]
            ),
            "runtime_frontend_enablement_release_switch_effective_allowed": False,
            "runtime_frontend_enablement_release_switch_is_production_evidence": False,
            "runtime_frontend_enablement_config_promotion_contract_visible": True,
            "runtime_frontend_enablement_config_promotion_step_count": (
                runtime_frontend_enablement_config_promotion_contract["promotion_step_count"]
            ),
            "runtime_frontend_enablement_config_promotion_pending_step_count": (
                runtime_frontend_enablement_config_promotion_contract["pending_promotion_step_count"]
            ),
            "runtime_frontend_enablement_config_promotion_effective_allowed": False,
            "runtime_frontend_enablement_config_promotion_is_production_evidence": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_prices_positions_or_operation_zones": True,
        },
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_bootstrap_runtime_mode_cache",
                "endpoint": BOOTSTRAP_STATUS_ROUTE,
                "row_count": len(config_rows)
                + len(provider_linkage_rows)
                + runtime_config_reference_contract["config_reference_row_count"]
                + runtime_mode_acceptance_contract["acceptance_row_count"]
                + live_light_rollout_roadmap_contract["stage_count"]
                + task_creation_invariant_contract["surface_row_count"]
                + live_light_startup_autostart_readiness_contract["readiness_row_count"]
                + live_light_unified_startup_task_contract["stage_count"]
                + runtime_cache_first_polling_contract["phase_count"]
                + runtime_frontend_enablement_gate_contract["gate_row_count"]
                + runtime_browser_evidence_contract["evidence_row_count"]
                + runtime_frontend_wiring_manifest_contract["manifest_row_count"]
                + runtime_frontend_acceptance_runbook_contract["runbook_row_count"]
                + runtime_frontend_acceptance_artifact_contract["artifact_row_count"]
                + runtime_frontend_enablement_promotion_contract["promotion_row_count"]
                + runtime_frontend_enablement_release_switch_contract["release_switch_row_count"]
                + runtime_frontend_enablement_config_promotion_contract["promotion_step_count"]
                + len(activation_rows)
                + len(acceptance_rows)
                + live_light_operator_status_contract["status_surface_count"]
                + live_light_promotion_gate_contract["promotion_layer_count"]
                + live_light_worker_dispatch_contract["dispatch_row_count"]
                + live_light_execution_request_handoff_contract["handoff_row_count"]
                + search_quant_projection_submit_autostart_config_promotion_contract["promotion_step_count"],
                "provider_linkage_row_count": len(provider_linkage_rows),
                "runtime_config_reference_row_count": runtime_config_reference_contract["config_reference_row_count"],
                "runtime_config_reference_source_switch_count": runtime_config_reference_contract[
                    "source_switch_count"
                ],
                "runtime_config_reference_audit_id": runtime_config_reference_contract["config_audit_id"],
                "runtime_config_ownership_audit_id": runtime_config_ownership_invariant_contract[
                    "ownership_audit_id"
                ],
                "runtime_config_ownership_linked_reference_audit_id": (
                    runtime_config_ownership_invariant_contract["linked_runtime_config_reference_audit_id"]
                ),
                "runtime_config_reference_is_production_evidence": False,
                "runtime_mode_acceptance_row_count": runtime_mode_acceptance_contract["acceptance_row_count"],
                "runtime_mode_acceptance_is_production_evidence": False,
                "live_light_rollout_roadmap_stage_count": live_light_rollout_roadmap_contract["stage_count"],
                "live_light_rollout_roadmap_next_stage": (
                    live_light_rollout_roadmap_contract["next_implementation_stage_key"]
                ),
                "live_light_rollout_roadmap_is_production_evidence": False,
                "task_creation_invariant_surface_row_count": task_creation_invariant_contract["surface_row_count"],
                "task_creation_invariant_allowed_surface_count": (
                    task_creation_invariant_contract["allowed_task_surface_count"]
                ),
                "task_creation_invariant_is_production_evidence": False,
                "live_light_startup_autostart_readiness_row_count": (
                    live_light_startup_autostart_readiness_contract["readiness_row_count"]
                ),
                "live_light_startup_autostart_readiness_condition_satisfied_row_count": (
                    live_light_startup_autostart_readiness_contract["condition_satisfied_row_count"]
                ),
                "live_light_startup_autostart_readiness_browser_evidence_complete": False,
                "live_light_startup_autostart_readiness_effective_allowed": False,
                "live_light_startup_autostart_readiness_is_production_evidence": False,
                "live_light_unified_startup_task_stage_count": (
                    live_light_unified_startup_task_contract["stage_count"]
                ),
                "live_light_unified_startup_task_route": live_light_unified_startup_task_contract[
                    "task_route"
                ],
                "live_light_unified_startup_task_provider_execution_implemented": False,
                "live_light_unified_startup_task_model_execution_implemented": False,
                "live_light_unified_startup_task_worker_dispatch_implemented": False,
                "live_light_unified_startup_task_is_production_evidence": False,
                "runtime_cache_first_polling_phase_count": runtime_cache_first_polling_contract["phase_count"],
                "runtime_cache_first_polling_task_creation_allowed_phase_count": (
                    runtime_cache_first_polling_contract["task_creation_allowed_phase_count"]
                ),
                "runtime_cache_first_polling_is_production_evidence": False,
                "runtime_frontend_enablement_gate_row_count": runtime_frontend_enablement_gate_contract[
                    "gate_row_count"
                ],
                "runtime_frontend_enablement_blocking_row_count": runtime_frontend_enablement_gate_contract[
                    "blocking_row_count"
                ],
                "runtime_frontend_enablement_allowed": False,
                "runtime_frontend_enablement_is_production_evidence": False,
                "runtime_browser_evidence_row_count": runtime_browser_evidence_contract["evidence_row_count"],
                "runtime_browser_evidence_blocking_row_count": runtime_browser_evidence_contract[
                    "blocking_evidence_row_count"
                ],
                "runtime_browser_evidence_complete": False,
                "runtime_browser_evidence_is_production_evidence": False,
                "runtime_frontend_wiring_manifest_row_count": runtime_frontend_wiring_manifest_contract[
                    "manifest_row_count"
                ],
                "runtime_frontend_wiring_manifest_done_row_count": runtime_frontend_wiring_manifest_contract[
                    "implementation_done_row_count"
                ],
                "runtime_frontend_wiring_manifest_pending_row_count": runtime_frontend_wiring_manifest_contract[
                    "pending_manifest_row_count"
                ],
                "runtime_frontend_wiring_manifest_manual_button_implemented": runtime_frontend_wiring_manifest_contract[
                    "manual_button_manifest_implemented"
                ],
                "runtime_frontend_wiring_manifest_is_production_evidence": False,
                "runtime_frontend_acceptance_runbook_row_count": runtime_frontend_acceptance_runbook_contract[
                    "runbook_row_count"
                ],
                "runtime_frontend_acceptance_runbook_pending_row_count": (
                    runtime_frontend_acceptance_runbook_contract["pending_runbook_row_count"]
                ),
                "runtime_frontend_acceptance_runbook_is_production_evidence": False,
                "runtime_frontend_acceptance_artifact_row_count": runtime_frontend_acceptance_artifact_contract[
                    "artifact_row_count"
                ],
                "runtime_frontend_acceptance_artifact_pending_count": (
                    runtime_frontend_acceptance_artifact_contract["pending_artifact_count"]
                ),
                "runtime_frontend_acceptance_artifact_is_production_evidence": False,
                "runtime_frontend_enablement_promotion_row_count": runtime_frontend_enablement_promotion_contract[
                    "promotion_row_count"
                ],
                "runtime_frontend_enablement_promotion_blocking_row_count": (
                    runtime_frontend_enablement_promotion_contract["blocking_promotion_row_count"]
                ),
                "runtime_frontend_enablement_promotion_is_production_evidence": False,
                "runtime_frontend_enablement_release_switch_row_count": (
                    runtime_frontend_enablement_release_switch_contract["release_switch_row_count"]
                ),
                "runtime_frontend_enablement_release_switch_blocking_row_count": (
                    runtime_frontend_enablement_release_switch_contract["blocking_release_switch_row_count"]
                ),
                "runtime_frontend_enablement_release_switch_is_production_evidence": False,
                "runtime_frontend_enablement_config_promotion_step_count": (
                    runtime_frontend_enablement_config_promotion_contract["promotion_step_count"]
                ),
                "runtime_frontend_enablement_config_promotion_pending_step_count": (
                    runtime_frontend_enablement_config_promotion_contract["pending_promotion_step_count"]
                ),
                "runtime_frontend_enablement_config_promotion_effective_allowed": False,
                "runtime_frontend_enablement_config_promotion_is_production_evidence": False,
                "activation_row_count": len(activation_rows),
                "acceptance_runbook_row_count": len(acceptance_rows),
                "operator_status_surface_count": live_light_operator_status_contract["status_surface_count"],
                "promotion_gate_layer_count": live_light_promotion_gate_contract["promotion_layer_count"],
                "worker_dispatch_row_count": live_light_worker_dispatch_contract["dispatch_row_count"],
                "execution_request_handoff_row_count": live_light_execution_request_handoff_contract[
                    "handoff_row_count"
                ],
                "latest_bootstrap_task_found": live_light_latest_bootstrap_task_status["task_found"],
                "latest_bootstrap_task_status": live_light_latest_bootstrap_task_status["status"],
                "latest_bootstrap_task_lookup_creates_task": False,
                "latest_acceptance_dry_run_receipt_found": live_light_latest_acceptance_dry_run_status["receipt_found"],
                "latest_acceptance_dry_run_receipt_status": live_light_latest_acceptance_dry_run_status["status"],
                "latest_acceptance_dry_run_lookup_creates_task": False,
                "latest_execution_request_receipt_found": live_light_latest_execution_request_status["receipt_found"],
                "latest_execution_request_receipt_status": live_light_latest_execution_request_status["status"],
                "latest_execution_request_lookup_creates_task": False,
                "search_quant_projection_latest_task_found": search_quant_projection_latest_status["task_found"],
                "search_quant_projection_latest_status": search_quant_projection_latest_status["status"],
                "search_quant_projection_latest_lookup_creates_task": False,
                "search_quant_projection_provider_model_latest_task_found": (
                    search_quant_projection_provider_model_latest_status["task_found"]
                ),
                "search_quant_projection_provider_model_latest_status": (
                    search_quant_projection_provider_model_latest_status["status"]
                ),
                "search_quant_projection_provider_model_latest_lookup_creates_task": False,
                "search_quant_projection_provider_model_latest_provider_call_ledger_evidence_done": (
                    search_quant_projection_provider_model_latest_status["provider_call_ledger_evidence_done"]
                ),
                "search_quant_projection_provider_model_latest_deepseek_model_ledger_evidence_done": (
                    search_quant_projection_provider_model_latest_status["deepseek_model_ledger_evidence_done"]
                ),
                "search_quant_projection_provider_model_latest_deepseek_output_acceptance_done": (
                    search_quant_projection_provider_model_latest_status["deepseek_output_acceptance_done"]
                ),
                "search_quant_projection_provider_model_latest_deepseek_output_acceptance_status": (
                    search_quant_projection_provider_model_latest_status["deepseek_output_acceptance_status"]
                ),
                "search_quant_projection_provider_model_latest_deepseek_output_cache_written": (
                    search_quant_projection_provider_model_latest_status["deepseek_output_cache_written"]
                ),
                "search_quant_projection_provider_model_latest_task_success_is_model_output_evidence": (
                    search_quant_projection_provider_model_latest_status["task_success_is_model_output_evidence"]
                ),
                "search_quant_projection_provider_model_latest_task_success_is_provider_model_evidence": (
                    search_quant_projection_provider_model_latest_status["task_success_is_provider_model_evidence"]
                ),
                "search_quant_projection_provider_model_latest_task_success_is_production_evidence": False,
                "search_quant_projection_submit_autostart_allowed": search_quant_projection_submit_autostart_contract[
                    "live_light_search_submit_auto_start_allowed"
                ],
                "search_quant_projection_submit_autostart_configured": search_submit_autostart_on_submit,
                "search_quant_projection_submit_autostart_effective": effective_search_submit_autostart,
                "search_quant_projection_submit_autostart_config_handoff_visible": True,
                "search_quant_projection_submit_autostart_global_config_allowlist_promoted": (
                    search_quant_projection_submit_autostart_config_handoff_contract[
                        "global_config_allowlist_promoted"
                    ]
                ),
                "search_quant_projection_submit_autostart_config_allowlist_promotion_pending": (
                    search_quant_projection_submit_autostart_config_handoff_contract[
                        "global_config_allowlist_promotion_pending"
                    ]
                ),
                "search_quant_projection_submit_autostart_config_handoff_is_production_evidence": False,
                "search_quant_projection_submit_autostart_config_promotion_contract_visible": True,
                "search_quant_projection_submit_autostart_config_promotion_step_count": (
                    search_quant_projection_submit_autostart_config_promotion_contract["promotion_step_count"]
                ),
                "search_quant_projection_submit_autostart_config_py_update_pending": (
                    search_quant_projection_submit_autostart_config_promotion_contract["config_py_update_pending"]
                ),
                "search_quant_projection_submit_autostart_bootstrap_fallback_removal_pending": (
                    search_quant_projection_submit_autostart_config_promotion_contract[
                        "bootstrap_local_env_fallback_removal_pending"
                    ]
                ),
                "search_quant_projection_submit_autostart_config_promotion_is_production_evidence": False,
                "search_quant_projection_submit_autostart_backend_ready": True,
                "search_quant_projection_submit_autostart_frontend_wiring_implemented": False,
                "search_quant_projection_submit_autostart_calls_provider_model": False,
                "search_quant_projection_manual_button_frontend_wiring_implemented": (
                    search_quant_projection_frontend_wiring_acceptance_contract[
                        "manual_button_frontend_wiring_implemented"
                    ]
                ),
                "search_quant_projection_manual_confirm_button_frontend_wiring_implemented": (
                    search_quant_projection_frontend_wiring_acceptance_contract[
                        "manual_confirm_button_frontend_wiring_implemented"
                    ]
                ),
                "search_quant_projection_manual_confirm_button_runtime_ready": (
                    search_quant_projection_frontend_wiring_acceptance_contract[
                        "manual_confirm_button_runtime_ready"
                    ]
                ),
                "search_quant_projection_manual_confirm_button_status": (
                    search_quant_projection_frontend_wiring_acceptance_contract[
                        "manual_confirm_button_status"
                    ]
                ),
                "search_quant_projection_p1_manual_confirm_path_ready": (
                    search_quant_projection_frontend_wiring_acceptance_contract[
                        "p1_manual_confirm_path_ready"
                    ]
                ),
                "search_quant_projection_p1_manual_confirm_path_status": (
                    search_quant_projection_frontend_wiring_acceptance_contract[
                        "p1_manual_confirm_path_status"
                    ]
                ),
                "search_quant_projection_frontend_runtime_wiring_implemented": (
                    search_quant_projection_frontend_wiring_acceptance_contract[
                        "frontend_runtime_wiring_implemented"
                    ]
                ),
                "search_quant_projection_frontend_runtime_wiring_scope": (
                    search_quant_projection_frontend_wiring_acceptance_contract[
                        "frontend_runtime_wiring_scope"
                    ]
                ),
                "search_quant_projection_manual_button_path_calls_provider_or_model_from_frontend": False,
                "search_quant_projection_frontend_wiring_implemented": False,
                "search_quant_projection_full_frontend_wiring_implemented": (
                    search_quant_projection_frontend_wiring_acceptance_contract[
                        "full_frontend_wiring_implemented"
                    ]
                ),
                "search_quant_projection_full_frontend_wiring_pending_reason": (
                    search_quant_projection_frontend_wiring_acceptance_contract[
                        "full_frontend_wiring_pending_reason"
                    ]
                ),
                "search_quant_projection_frontend_wiring_browser_evidence_complete": False,
                "activation_receipt_status": activation_receipt["status"],
                "activation_receipt_ready": activation_receipt["local_activation_receipt_ready"],
                "acceptance_runbook_status": acceptance_runbook["status"],
                "acceptance_runbook_ready": acceptance_runbook["local_runbook_ready"],
                "acceptance_dry_run_route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
                "local_fetched_at": loaded_at,
                "call_status": "cache_read",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "bootstrap_task_implemented": True,
                "provider_execution_implemented": False,
            }
        ],
        "warnings": [
            "GET /api/bootstrap/status 只读展示运行模式；不创建 bootstrap task。",
            "POST /api/bootstrap/live-startup 已作为本地 task skeleton 接入；provider 执行、worker 编排和自动前端触发仍待后续验收。",
            "POST /api/bootstrap/provider-model-acceptance-dry-run 只记录用户批准前的本地验收 dry-run；不调用 provider/model。",
            "POST /api/bootstrap/provider-model-execution-request 已接入本地 route adapter；只生成 execution-request ticket，不创建 provider/model task。",
            "本接口不调用 Tushare、DeepSeek、GitHub，不读取 token/key，不执行真实交易。",
        ],
    }
    return _json_safe(packet)


def run_live_startup_task(payload: Any = None) -> dict[str, Any]:
    status_packet = read_bootstrap_status_cache()
    live_light = status_packet.get("live_light") if isinstance(status_packet.get("live_light"), dict) else {}
    mode = str(status_packet.get("mode") or DEFAULT_MODE)
    symbol_limit = int(live_light.get("symbol_limit") or 20)
    rate_limit_seconds = int(live_light.get("rate_limit_seconds") or 600)
    payload_safe = _sanitize_live_startup_payload(payload, symbol_limit=symbol_limit)
    payload_safe.update(
        {
            "schema_version": BOOTSTRAP_TASK_SCHEMA_VERSION,
            "bootstrap_mode": mode,
            "tushare_on_open": live_light.get("tushare_on_open") is True,
            "deepseek_on_open": live_light.get("deepseek_on_open") is True,
            "sources_enabled": live_light.get("sources_enabled") is True,
            "default_light_tushare_apis": list(DEFAULT_LIGHT_TUSHARE_APIS),
            "allow_full_pool": False,
            "desktop_live_execution_enabled": _desktop_live_startup_execution_enabled(),
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    )
    plan = _build_live_bootstrap_plan(status_packet, payload_safe)
    payload_safe.update(plan)

    if mode == "live_light":
        recent_task, age_seconds = _recent_live_bootstrap_task(
            mode,
            rate_limit_seconds=rate_limit_seconds,
            require_desktop_live_execution=payload_safe.get("desktop_live_execution_enabled") is True,
        )
        if recent_task is not None:
            now = _now_iso()
            existing_ledger = list(recent_task.get("call_ledger") or [])
            ledger = existing_ledger + [
                _live_startup_call_ledger(
                    status_packet=status_packet,
                    payload_safe=payload_safe,
                    call_status="skipped_due_to_rate_limit_reused_existing_task",
                    current_step="live_bootstrap_skipped_due_to_rate_limit",
                    now=now,
                    reused_task_id=str(recent_task.get("task_id") or ""),
                    rate_limit_age_seconds=age_seconds,
                    plan=plan,
                )
            ]
            updated = task_service.update_task_status(
                str(recent_task.get("task_id") or ""),
                status=str(recent_task.get("status") or "success"),
                progress=float(recent_task.get("progress") or 1.0),
                current_step="live_bootstrap_skipped_due_to_rate_limit",
                call_ledger=ledger,
                warning="live_light_bootstrap_reused_existing_task_due_to_rate_limit_no_external_call",
            )
            return updated or recent_task

    if mode != "live_light":
        current_step = "live_bootstrap_skipped_mode_not_live_light"
        call_status = "skipped_mode_not_live_light"
    elif live_light.get("sources_enabled") is not True:
        current_step = "live_bootstrap_skipped_sources_disabled_no_external_call"
        call_status = "skipped_sources_disabled"
    elif payload_safe.get("desktop_live_execution_enabled") is True:
        current_step = "live_bootstrap_execution_requested"
        call_status = "live_bootstrap_execution_requested"
    else:
        current_step = "live_bootstrap_plan_recorded_no_provider_execution"
        call_status = "local_plan_recorded_no_provider_execution"

    task = task_service.create_task_record(
        BOOTSTRAP_TASK_TYPE,
        output_packet_key=BOOTSTRAP_TASK_PACKET_KEY,
        payload=payload_safe,
        current_step="live_bootstrap_requested_local_only",
        warnings=_live_startup_warnings(mode, current_step),
    )
    now = _now_iso()
    ledger = [
        _live_startup_call_ledger(
            status_packet=status_packet,
            payload_safe=payload_safe,
            call_status=call_status,
            current_step=current_step,
            now=now,
            plan=plan,
        )
    ]
    execution_summary: dict[str, Any] = {}
    if current_step == "live_bootstrap_execution_requested":
        payload_safe["provider_execution_implemented"] = True
        task["payload_safe"]["provider_execution_implemented"] = True
        task["payload_safe"]["desktop_live_execution_enabled"] = True
        execution_step, execution_ledgers, execution_summary = _execute_live_light_tushare_and_local_pipeline(
            task_id=str(task.get("task_id") or ""),
            payload_safe=payload_safe,
            status_packet=status_packet,
            plan=plan,
        )
        current_step = execution_step
        ledger.extend(execution_ledgers)
        task["payload_safe"]["desktop_live_execution_summary"] = execution_summary
        task["payload_safe"]["provider_execution_implemented"] = execution_summary.get("provider_called") is True
        task["payload_safe"]["model_execution_implemented"] = False
        task["payload_safe"]["external_calls_triggered"] = execution_summary.get("provider_called") is True
        task["payload_safe"]["tushare_called"] = execution_summary.get("provider_called") is True
        task["payload_safe"]["deepseek_called"] = False
    return task_service.update_task_status(
        str(task.get("task_id") or ""),
        status="success",
        progress=1.0,
        current_step=current_step,
        output_packet_key=BOOTSTRAP_TASK_PACKET_KEY,
        call_ledger=ledger,
        warning=(
            "DeepSeek live model call requires explicit data-export approval; Tushare/live local cache pipeline ran first."
            if execution_summary.get("deepseek_requested_but_requires_explicit_data_export_approval")
            else None
        ),
    ) or task


def run_provider_model_acceptance_dry_run(payload: Any = None) -> dict[str, Any]:
    status_packet = read_bootstrap_status_cache()
    live_light = _dict(status_packet.get("live_light"))
    symbol_limit = int(live_light.get("symbol_limit") or 20)
    payload_safe = _sanitize_acceptance_dry_run_payload(payload, symbol_limit=symbol_limit)
    payload_safe.update(
        {
            "task_type": BOOTSTRAP_ACCEPTANCE_DRY_RUN_TASK_TYPE,
            "bootstrap_mode": status_packet.get("mode"),
            "route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
            "runbook_schema_version": BOOTSTRAP_ACCEPTANCE_RUNBOOK_SCHEMA_VERSION,
            "dry_run_only": True,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    )
    credential_rows = _env_key_presence_rows(payload_safe)
    credential_summary = _env_key_presence_summary(credential_rows)
    payload_safe["credential_presence_rows"] = credential_rows
    payload_safe["credential_presence_summary"] = credential_summary
    payload_safe["acceptance_scope_ticket"] = _acceptance_scope_ticket(
        payload_safe=payload_safe,
        status_packet=status_packet,
    )
    summary, rows = _build_acceptance_dry_run(status_packet=status_packet, payload_safe=payload_safe)
    real_preflight_receipt, real_preflight_rows = _real_acceptance_preflight_receipt(
        payload_safe=payload_safe,
        summary=summary,
    )
    summary["real_acceptance_preflight_receipt_status"] = real_preflight_receipt["status"]
    summary["real_acceptance_preflight_ready_to_execute"] = real_preflight_receipt["ready_to_execute_real_task"]
    summary["real_acceptance_preflight_blocking_row_count"] = real_preflight_receipt["blocking_row_count"]
    payload_safe["acceptance_dry_run_summary"] = summary
    payload_safe["acceptance_dry_run_rows"] = rows
    payload_safe["real_acceptance_preflight_receipt"] = real_preflight_receipt
    payload_safe["real_acceptance_preflight_rows"] = real_preflight_rows
    current_step = (
        "provider_model_acceptance_dry_run_recorded_user_approval_required_no_external_call"
        if payload_safe.get("user_approved") is not True
        else "provider_model_acceptance_dry_run_blocked_missing_credentials_no_external_call"
        if summary.get("blocked_by_missing_credentials") is True
        else "provider_model_acceptance_dry_run_recorded_user_approval_no_external_call"
    )
    task = task_service.create_task_record(
        BOOTSTRAP_ACCEPTANCE_DRY_RUN_TASK_TYPE,
        output_packet_key=BOOTSTRAP_ACCEPTANCE_DRY_RUN_PACKET_KEY,
        payload=payload_safe,
        current_step="provider_model_acceptance_dry_run_requested_local_only",
        warnings=[
            "provider/model acceptance dry-run 只记录本地预检，不调用 Tushare、DeepSeek、GitHub。",
            "dry-run 只检查服务端环境变量 key 是否存在，不读取或返回 token/key 值。",
            "dry-run 不执行真实交易，不修改 strategy action。",
            "真实 provider/model 验收仍需后续显式任务和用户确认。",
        ],
    )
    now = _now_iso()
    ledger = [_acceptance_dry_run_call_ledger(payload_safe=payload_safe, summary=summary, now=now)]
    return task_service.update_task_status(
        str(task.get("task_id") or ""),
        status="success",
        progress=1.0,
        current_step=current_step,
        output_packet_key=BOOTSTRAP_ACCEPTANCE_DRY_RUN_PACKET_KEY,
        call_ledger=ledger,
    ) or task


def run_provider_model_execution_request(payload: Any = None) -> dict[str, Any]:
    payload_safe = _sanitize_execution_request_payload(payload)
    latest_dry_run_task = _latest_acceptance_dry_run_task(
        str(payload_safe.get("requested_acceptance_scope_hash") or "")
    )
    receipt, rows = _build_execution_request_receipt(
        payload_safe=payload_safe,
        latest_dry_run_task=latest_dry_run_task,
    )
    payload_safe.update(
        {
            "task_type": BOOTSTRAP_EXECUTION_REQUEST_TASK_TYPE,
            "bootstrap_mode": read_bootstrap_status_cache().get("mode"),
            "route": PLANNED_BOOTSTRAP_EXECUTION_REQUEST_ROUTE,
            "acceptance_dry_run_route": PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE,
            "target_provider_model_route": FUTURE_BOOTSTRAP_PROVIDER_MODEL_ACCEPTANCE_ROUTE,
            "execution_request_receipt": receipt,
            "execution_request_rows": rows,
            "execution_request_only": True,
            "provider_model_task_created": False,
            "provider_model_task_dispatched": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    )
    if receipt["status"] == "execution_request_ready_manual_provider_model_task_pending":
        current_step = "provider_model_execution_request_ready_manual_provider_model_task_pending"
    elif receipt["status"] == "execution_request_blocked_scope_hash_mismatch":
        current_step = "provider_model_execution_request_blocked_scope_hash_mismatch_no_external_call"
    elif receipt["status"] == "execution_request_blocked_user_confirmation_required":
        current_step = "provider_model_execution_request_blocked_user_confirmation_required_no_external_call"
    elif receipt["status"] == "execution_request_blocked_missing_acceptance_dry_run":
        current_step = "provider_model_execution_request_blocked_missing_dry_run_no_external_call"
    else:
        current_step = "provider_model_execution_request_blocked_dry_run_not_ready_no_external_call"

    task = task_service.create_task_record(
        BOOTSTRAP_EXECUTION_REQUEST_TASK_TYPE,
        output_packet_key=BOOTSTRAP_EXECUTION_REQUEST_PACKET_KEY,
        payload=payload_safe,
        current_step="provider_model_execution_request_requested_local_only",
        warnings=[
            "provider/model execution-request 只生成本地 scope-bound ticket，不调用 Tushare、DeepSeek、GitHub。",
            "execution-request 不创建 provider/model task；未来 route 仍需显式接入。",
            "execution-request 不读取或返回 token/key 值，不执行真实交易，不修改 strategy action。",
        ],
    )
    now = _now_iso()
    ledger = [_execution_request_call_ledger(payload_safe=payload_safe, receipt=receipt, now=now)]
    return task_service.update_task_status(
        str(task.get("task_id") or ""),
        status="success",
        progress=1.0,
        current_step=current_step,
        output_packet_key=BOOTSTRAP_EXECUTION_REQUEST_PACKET_KEY,
        call_ledger=ledger,
    ) or task
