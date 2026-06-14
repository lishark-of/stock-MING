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
BOOTSTRAP_MODES = ("cache_only", "manual", "live_light", "live_full")
DEFAULT_MODE = "cache_only"
BOOTSTRAP_STATUS_ROUTE = "GET /api/bootstrap/status"
PLANNED_BOOTSTRAP_TASK_ROUTE = "POST /api/bootstrap/live-startup"
DEFAULT_LIGHT_TUSHARE_APIS = ("trade_cal_if_needed", "daily", "daily_basic", "moneyflow")


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


def _live_startup_call_ledger(
    *,
    status_packet: dict[str, Any],
    payload_safe: dict[str, Any],
    call_status: str,
    current_step: str,
    now: str,
    reused_task_id: str = "",
    rate_limit_age_seconds: int | None = None,
) -> dict[str, Any]:
    live_light = status_packet.get("live_light") if isinstance(status_packet.get("live_light"), dict) else {}
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
        },
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

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
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
            "live_light_provider_execution_implemented": False,
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
                "bootstrap_task_implemented": True,
                "provider_execution_implemented": False,
            }
        ],
        "warnings": [
            "GET /api/bootstrap/status 只读展示运行模式；不创建 bootstrap task。",
            "POST /api/bootstrap/live-startup 已作为本地 task skeleton 接入；provider 执行、worker 编排和自动前端触发仍待后续验收。",
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
