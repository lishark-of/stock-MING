from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from config import get_config_value, get_deepseek_model


PACKET_KEY = "command_center_3_bootstrap_runtime_mode_packet"
SCHEMA_VERSION = "command_center_bootstrap_runtime_mode.v1"
BOOTSTRAP_MODES = ("cache_only", "manual", "live_light", "live_full")
DEFAULT_MODE = "cache_only"
BOOTSTRAP_STATUS_ROUTE = "GET /api/bootstrap/status"
PLANNED_BOOTSTRAP_TASK_ROUTE = "POST /api/bootstrap/live-startup"


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "bootstrap_runtime_mode_packet_not_json_serializable"}


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
        "bootstrap_task_implemented": False if mode in {"live_light", "live_full"} else None,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


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
        "live_light": "live_light_config_visible_task_pending",
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

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": active_mode,
        "cache_only": active_mode == "cache_only",
        "read_only": True,
        "loaded_at": loaded_at,
        "summary": "Runtime mode cache is read-only. It makes cache_only/manual/live_light/live_full boundaries visible without creating tasks or calling providers.",
        "configured_mode_raw": configured_mode_raw,
        "configured_mode_valid": mode_valid,
        "mode_rows": [_mode_row(mode, active_mode) for mode in BOOTSTRAP_MODES],
        "config_rows": config_rows,
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
            "bootstrap_task_implemented": False,
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
            "live_light_task_implemented": False,
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
                "row_count": len(config_rows),
                "local_fetched_at": loaded_at,
                "call_status": "cache_read",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [
            "GET /api/bootstrap/status 只读展示运行模式；不创建 bootstrap task。",
            "cache_only/manual/live_light/live_full 是模式边界；live_light 仍需后续 POST task 与 worker 验收。",
            "本接口不调用 Tushare、DeepSeek、GitHub，不读取 token/key，不执行真实交易。",
        ],
    }
    return _json_safe(packet)
