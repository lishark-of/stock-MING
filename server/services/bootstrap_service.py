from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from config import get_config_value, get_deepseek_model
from server.services import task_service


PACKET_KEY = "command_center_3_bootstrap_runtime_mode_packet"
SCHEMA_VERSION = "command_center_bootstrap_runtime_mode.v1"
BOOTSTRAP_TASK_PACKET_KEY = "command_center_live_bootstrap_packet"
BOOTSTRAP_TASK_SCHEMA_VERSION = "command_center_live_bootstrap_task.v1"
BOOTSTRAP_TASK_TYPE = "command_center_live_bootstrap"
BOOTSTRAP_ACCEPTANCE_DRY_RUN_PACKET_KEY = "command_center_live_bootstrap_provider_model_acceptance_dry_run_packet"
BOOTSTRAP_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION = "command_center_live_bootstrap_provider_model_acceptance_dry_run.v1"
BOOTSTRAP_ACCEPTANCE_DRY_RUN_TASK_TYPE = "command_center_live_bootstrap_provider_model_acceptance_dry_run"
BOOTSTRAP_MODES = ("cache_only", "manual", "live_light", "live_full")
DEFAULT_MODE = "cache_only"
BOOTSTRAP_STATUS_ROUTE = "GET /api/bootstrap/status"
PLANNED_BOOTSTRAP_TASK_ROUTE = "POST /api/bootstrap/live-startup"
PLANNED_BOOTSTRAP_ACCEPTANCE_DRY_RUN_ROUTE = "POST /api/bootstrap/provider-model-acceptance-dry-run"
DEFAULT_LIGHT_TUSHARE_APIS = ("trade_cal_if_needed", "daily", "daily_basic", "moneyflow")
ACCEPTANCE_DRY_RUN_ALLOWED_APIS = ("trade_cal", "daily", "daily_basic", "moneyflow")
BOOTSTRAP_STAGE_SCHEMA_VERSION = "command_center_live_bootstrap_stage_plan.v1"
BOOTSTRAP_MODEL_LEDGER_SCHEMA_VERSION = "command_center_live_bootstrap_model_ledger_preview.v1"
BOOTSTRAP_PROVIDER_LINKAGE_SCHEMA_VERSION = "command_center_bootstrap_provider_linkage.v1"
BOOTSTRAP_ACTIVATION_RECEIPT_SCHEMA_VERSION = "command_center_live_bootstrap_activation_receipt.v1"
BOOTSTRAP_ACCEPTANCE_RUNBOOK_SCHEMA_VERSION = "command_center_live_bootstrap_provider_model_acceptance_runbook.v1"
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


def _safe_text(value: Any, *, limit: int = 160) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in ("api_key", "apikey", "token", "secret", "password", "authorization", "bearer")):
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


def _recent_live_bootstrap_task(mode: str, *, rate_limit_seconds: int) -> tuple[dict[str, Any] | None, int | None]:
    now = _dt.datetime.now()
    for task in task_service.list_task_statuses():
        if str(task.get("task_type") or "") != BOOTSTRAP_TASK_TYPE:
            continue
        payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
        if str(payload_safe.get("bootstrap_mode") or "") != mode:
            continue
        timestamp = _parse_iso(task.get("finished_at") or task.get("started_at") or task.get("created_at"))
        if timestamp is None:
            continue
        age_seconds = max(0, int((now - timestamp).total_seconds()))
        if age_seconds <= int(rate_limit_seconds):
            return task, age_seconds
    return None, None


def _runtime_mode() -> tuple[str, str, bool]:
    raw = str(_config_value("COMMAND_CENTER_BOOTSTRAP_MODE", DEFAULT_MODE) or DEFAULT_MODE).strip().lower()
    if raw in BOOTSTRAP_MODES:
        return raw, raw, True
    return DEFAULT_MODE, raw, False


def _mode_row(mode: str, active_mode: str) -> dict[str, Any]:
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
        "cache_get_external_calls": False,
        "react_render_provider_calls": False,
        "post_task_required": mode != "cache_only",
        "bootstrap_task_implemented": True if mode == "live_light" else (False if mode == "live_full" else None),
        "provider_execution_implemented": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


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
        return "dry_run_pending_server_secret_presence_check_no_values_read", False
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
    summary = {
        "schema_version": BOOTSTRAP_ACCEPTANCE_DRY_RUN_SCHEMA_VERSION,
        "status": "acceptance_dry_run_ready_execution_pending",
        "scope": "local_provider_model_acceptance_dry_run_no_external_call",
        "mode": status_packet.get("mode"),
        "runbook_status": runbook.get("status"),
        "user_approved": payload_safe.get("user_approved") is True,
        "selected_apis": payload_safe.get("selected_apis") or [],
        "ignored_apis": payload_safe.get("ignored_apis") or [],
        "include_tushare": payload_safe.get("include_tushare") is True,
        "include_deepseek": payload_safe.get("include_deepseek") is True,
        "symbol_count": payload_safe.get("symbol_count"),
        "phase_count": len(rows),
        "selected_provider_phase_count": len(selected_provider_rows),
        "selected_model_phase_count": len(selected_model_rows),
        "blocking_phase_count": len(blocking_rows),
        "ready_for_user_approved_real_acceptance": payload_safe.get("user_approved") is True,
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


def _acceptance_dry_run_call_ledger(
    *,
    payload_safe: dict[str, Any],
    summary: dict[str, Any],
    now: str,
) -> dict[str, Any]:
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
        },
        "row_count": int(summary.get("phase_count") or 0),
        "selected_provider_phase_count": int(summary.get("selected_provider_phase_count") or 0),
        "selected_model_phase_count": int(summary.get("selected_model_phase_count") or 0),
        "blocking_phase_count": int(summary.get("blocking_phase_count") or 0),
        "local_fetched_at": now,
        "call_status": "local_acceptance_dry_run_recorded_no_external_call",
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


def _build_live_bootstrap_plan(status_packet: dict[str, Any], payload_safe: dict[str, Any]) -> dict[str, Any]:
    live_light = status_packet.get("live_light") if isinstance(status_packet.get("live_light"), dict) else {}
    mode = str(status_packet.get("mode") or DEFAULT_MODE)
    sources_enabled = bool(live_light.get("sources_enabled"))
    tushare_enabled = mode == "live_light" and sources_enabled and live_light.get("tushare_on_open") is True
    deepseek_enabled = mode == "live_light" and sources_enabled and live_light.get("deepseek_on_open") is True
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
    summary = {
        "stage_count": len(stage_rows),
        "model_ledger_preview_count": len(model_rows),
        "symbol_count": int(payload_safe.get("symbol_count") or 0),
        "symbol_limit": int(payload_safe.get("symbol_limit") or 0),
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
        "planned_at": now,
        "bootstrap_stage_rows": stage_rows,
        "bootstrap_model_ledger_preview_rows": model_rows,
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
            "planned_provider_stage_count": int(plan_summary.get("planned_provider_stage_count") or 0),
            "planned_model_stage_count": int(plan_summary.get("planned_model_stage_count") or 0),
        },
        "bootstrap_stage_count": int(plan_summary.get("stage_count") or 0),
        "model_ledger_preview_count": int(plan_summary.get("model_ledger_preview_count") or 0),
        "planned_provider_stage_count": int(plan_summary.get("planned_provider_stage_count") or 0),
        "planned_model_stage_count": int(plan_summary.get("planned_model_stage_count") or 0),
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


def read_bootstrap_status_cache() -> dict[str, Any]:
    active_mode, configured_mode_raw, mode_valid = _runtime_mode()
    tushare_on_open, tushare_source = _bool_config("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", False)
    deepseek_on_open, deepseek_source = _bool_config("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", False)
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
    deepseek_model = str(_config_value("COMMAND_CENTER_LIVE_DEEPSEEK_MODEL") or get_deepseek_model("explain"))
    loaded_at = _now_iso()

    live_light_enabled = active_mode == "live_light"
    live_light_sources_enabled = live_light_enabled and (tushare_on_open or deepseek_on_open)
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
            "value_safe": active_mode,
            "raw_value_valid": mode_valid,
            "source": "configured" if configured_mode_raw != DEFAULT_MODE or active_mode != DEFAULT_MODE else "default",
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN",
            "value_safe": tushare_on_open,
            "source": tushare_source,
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN",
            "value_safe": deepseek_on_open,
            "source": deepseek_source,
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT",
            "value_safe": symbol_limit,
            "source": symbol_limit_source,
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS",
            "value_safe": rate_limit_seconds,
            "source": rate_limit_source,
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_DEEPSEEK_MODEL",
            "value_safe": deepseek_model,
            "source": "configured" if _config_value("COMMAND_CENTER_LIVE_DEEPSEEK_MODEL") else "model_strategy_fallback",
            "contains_secret": False,
        },
        {
            "config": "COMMAND_CENTER_LIVE_ALLOW_FULL_POOL",
            "value_safe": allow_full_pool,
            "source": full_pool_source,
            "contains_secret": False,
        },
    ]
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
        "configured_mode_raw": configured_mode_raw,
        "configured_mode_valid": mode_valid,
        "mode_rows": [_mode_row(mode, active_mode) for mode in BOOTSTRAP_MODES],
        "config_rows": config_rows,
        "provider_linkage_schema_version": BOOTSTRAP_PROVIDER_LINKAGE_SCHEMA_VERSION,
        "provider_linkage_rows": provider_linkage_rows,
        "live_light_activation_receipt": activation_receipt,
        "live_light_activation_rows": activation_rows,
        "live_light_provider_model_acceptance_runbook": acceptance_runbook,
        "live_light_provider_model_acceptance_rows": acceptance_rows,
        "live_light": {
            "enabled": live_light_enabled,
            "tushare_on_open": tushare_on_open if live_light_enabled else False,
            "deepseek_on_open": deepseek_on_open if live_light_enabled else False,
            "sources_enabled": live_light_sources_enabled,
            "symbol_limit": symbol_limit,
            "rate_limit_seconds": rate_limit_seconds,
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
            "ready_for_provider_execution_design": activation_receipt["ready_for_provider_execution_design"],
            "ready_for_acceptance_design": acceptance_runbook["ready_for_acceptance_design"],
            "ready_for_user_approved_acceptance_dry_run_task": True,
            "ready_for_user_approved_acceptance_task": False,
            "ready_for_provider_execution": False,
            "ready_for_model_execution": False,
            "provider_execution_implemented": False,
            "tushare_execution_implemented": False,
            "deepseek_execution_implemented": False,
            "rate_limit_implemented": True,
            "allowed_scope": "current_target_holdings_watchlist_light_only",
            "full_pool_enabled": False,
            "full_pool_reserved": True,
            "safe_failure_display_required": True,
            "token_key_exposure_allowed": False,
        },
        "policy": {
            "cache_api_external_calls": False,
            "fastapi_startup_external_calls": False,
            "react_initial_render_external_calls": False,
            "react_render_direct_provider_calls": False,
            "post_task_required_for_external_calls": True,
            "live_light_default_enabled": False,
            "live_light_requires_opt_in": True,
            "live_light_task_implemented": True,
            "live_light_bootstrap_plan_skeleton_implemented": True,
            "live_light_model_ledger_preview_implemented": True,
            "provider_linkage_rows_visible": True,
            "live_light_activation_receipt_visible": True,
            "live_light_provider_model_acceptance_runbook_visible": True,
            "live_light_ready_for_provider_execution_design": True,
            "live_light_ready_for_acceptance_design": True,
            "live_light_ready_for_user_approved_acceptance_dry_run_task": True,
            "live_light_ready_for_user_approved_acceptance_task": False,
            "live_light_ready_for_provider_execution": False,
            "live_light_ready_for_model_execution": False,
            "live_light_provider_execution_implemented": False,
            "production_live_light_complete": False,
            "live_full_enabled": False,
            "full_pool_on_open_allowed": False,
            "github_probe_on_open_allowed": False,
            "does_not_call_tushare": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_read_api_keys": True,
            "does_not_expose_credentials": True,
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
                "row_count": len(config_rows) + len(provider_linkage_rows) + len(activation_rows) + len(acceptance_rows),
                "provider_linkage_row_count": len(provider_linkage_rows),
                "activation_row_count": len(activation_rows),
                "acceptance_runbook_row_count": len(acceptance_rows),
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
            "provider_execution_implemented": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    )
    plan = _build_live_bootstrap_plan(status_packet, payload_safe)
    payload_safe.update(plan)

    if mode == "live_light":
        recent_task, age_seconds = _recent_live_bootstrap_task(mode, rate_limit_seconds=rate_limit_seconds)
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
    return task_service.update_task_status(
        str(task.get("task_id") or ""),
        status="success",
        progress=1.0,
        current_step=current_step,
        output_packet_key=BOOTSTRAP_TASK_PACKET_KEY,
        call_ledger=ledger,
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
    summary, rows = _build_acceptance_dry_run(status_packet=status_packet, payload_safe=payload_safe)
    payload_safe["acceptance_dry_run_summary"] = summary
    payload_safe["acceptance_dry_run_rows"] = rows
    current_step = (
        "provider_model_acceptance_dry_run_recorded_user_approval_no_external_call"
        if payload_safe.get("user_approved") is True
        else "provider_model_acceptance_dry_run_recorded_user_approval_required_no_external_call"
    )
    task = task_service.create_task_record(
        BOOTSTRAP_ACCEPTANCE_DRY_RUN_TASK_TYPE,
        output_packet_key=BOOTSTRAP_ACCEPTANCE_DRY_RUN_PACKET_KEY,
        payload=payload_safe,
        current_step="provider_model_acceptance_dry_run_requested_local_only",
        warnings=[
            "provider/model acceptance dry-run 只记录本地预检，不调用 Tushare、DeepSeek、GitHub。",
            "dry-run 不读取 token/key 值，不执行真实交易，不修改 strategy action。",
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
