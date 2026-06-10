from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any

import command_center_data_capability_console as data_capability_console
import command_center_data_capability_dashboard as data_capability_dashboard
from server.services import packet_service


PACKET_KEY = "command_center_3_data_capability_cache"
SCHEMA_VERSION = "data_capability_cache.v1"
SENSITIVE_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password", "passwd", "credential", "authorization")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _is_sensitive_key(key: Any) -> bool:
    lower = str(key or "").lower()
    return any(part in lower for part in SENSITIVE_KEY_PARTS)


def _safe_text(value: Any, *, limit: int = 1000) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in SENSITIVE_TEXT_MARKERS):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[truncated]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            _safe_text(key, limit=100): _safe_value(val, depth=depth + 1)
            for key, val in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_safe_value(item, depth=depth + 1) for item in value[:80]]
    if isinstance(value, tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:80]]
    return _safe_text(value)


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "data_capability_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_mapping(snapshot: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = snapshot.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def read_data_capability_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    data_capability = _first_mapping(
        snapshot,
        "data_capability",
        "command_center_data_capability_packet",
        "a_share_professional_data_capability",
        "provider_data_capability",
    )
    data_gap_report = _first_mapping(snapshot, "data_gap_report", "command_center_data_gap_report")
    cached_console = _first_mapping(snapshot, "data_capability_console", "command_center_data_capability_console")
    cached_health_ledger = _first_mapping(snapshot, "data_health_ledger", "command_center_data_health_ledger")

    dashboard = data_capability_dashboard.build_data_capability_dashboard_view_model(data_capability, data_gap_report)
    if cached_console:
        console = cached_console
        console_source = "stock_ming_snapshot"
    else:
        console = data_capability_console.build_data_capability_console_packet(
            data_capability_packet=data_capability,
            data_gap_report=data_gap_report,
        )
        console_source = "local_builder_with_snapshot_context" if snapshot else "local_builder"

    health_ledger = cached_health_ledger or _as_dict(console.get("data_health_ledger"))
    safe_dashboard = _safe_value(dashboard)
    safe_console = _safe_value(console)
    safe_health = _safe_value(health_ledger)
    safe_dashboard = safe_dashboard if isinstance(safe_dashboard, dict) else {}
    safe_console = safe_console if isinstance(safe_console, dict) else {}
    safe_health = safe_health if isinstance(safe_health, dict) else {}

    status = str(safe_console.get("status") or safe_dashboard.get("status") or "missing")
    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "cache_only",
        "cache_only": True,
        "loaded_at": _now_iso(),
        "source_snapshot_available": bool(snapshot),
        "dashboard_source": "local_builder_with_snapshot_context" if snapshot else "local_builder",
        "console_source": console_source,
        "dashboard": safe_dashboard,
        "console": safe_console,
        "data_health_ledger": safe_health,
        "provider_cards": safe_dashboard.get("provider_cards") or safe_console.get("provider_cards") or [],
        "recovery_actions": safe_console.get("recovery_actions") or [],
        "counts": {
            "available": safe_dashboard.get("available_count", safe_console.get("available_count", 0)),
            "restricted": safe_dashboard.get("restricted_count", safe_console.get("blocked_count", 0)),
            "pending": safe_dashboard.get("pending_count", 0),
            "blocked": safe_console.get("blocked_count", 0),
            "manual": safe_console.get("manual_count", 0),
            "stale": safe_console.get("stale_count", 0),
        },
        "policy": {
            "cache_api_external_calls": False,
            "does_not_ping_tushare": True,
            "does_not_ping_akshare": True,
            "does_not_ping_yfinance": True,
            "does_not_ping_supabase": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_run_backtest": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "post_task_required_for_refresh": True,
        },
        "call_ledger": [
            {
                "api": "local_data_capability_cache",
                "dashboard_source": "local_builder_with_snapshot_context" if snapshot else "local_builder",
                "console_source": console_source,
                "call_status": "cache_read" if snapshot else "local_builder_no_snapshot",
                "local_fetched_at": _now_iso(),
                "external": False,
            }
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "akshare_called": False,
        "yfinance_called": False,
        "supabase_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "warnings": [
            "GET /api/data-capability/cache 只读整理本地数据能力检测结果；不会 ping 外部接口。",
            "数据能力缺口只用于风险降级和手动恢复建议，不直接覆盖 strategy action。",
        ],
    }
    return _json_safe(packet)
