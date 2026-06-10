from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any

from server.services import packet_service


PACKET_KEY = "command_center_3_position_context_cache"
SCHEMA_VERSION = "position_context_cache.v1"
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
    if depth > 4:
        return "[truncated]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            _safe_text(key, limit=80): _safe_value(val, depth=depth + 1)
            for key, val in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_safe_value(item, depth=depth + 1) for item in value[:40]]
    if isinstance(value, tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:40]]
    return _safe_text(value)


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "position_context_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_mapping(snapshot: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = snapshot.get(key)
        if isinstance(value, dict) and value:
            safe = _safe_value(value)
            return safe if isinstance(safe, dict) else {}
    return {}


def _position_summary(holding_action: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ticker": holding_action.get("ticker") or snapshot.get("target") or snapshot.get("ticker"),
        "name": holding_action.get("name"),
        "shares": holding_action.get("shares"),
        "cost": holding_action.get("cost"),
        "current_price": holding_action.get("current_price"),
        "floating_pnl": holding_action.get("floating_pnl"),
        "floating_pnl_text": holding_action.get("floating_pnl_text"),
        "investment_horizon": holding_action.get("investment_horizon"),
        "cached_action_state": holding_action.get("action_state"),
        "source": "holding_action cache",
    }


def _status(holding_action: Mapping[str, Any], snapshot: Mapping[str, Any]) -> str:
    if holding_action and any(holding_action.get(key) not in (None, "", [], {}) for key in ("ticker", "shares", "cost", "current_price", "action_state")):
        return "ready"
    if snapshot:
        return "partial"
    return "cache_missing"


def read_position_context_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    holding_action = _first_mapping(snapshot_map, "holding_action")
    status = _status(holding_action, snapshot_map)
    call_status = "cache_read" if snapshot else "cache_missing"

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "snapshot_available": bool(snapshot),
        "source_snapshot_path": str(packet_service.SNAPSHOT_CACHE_PATH.name),
        "position_summary": _position_summary(holding_action, snapshot_map),
        "holding_action": holding_action,
        "position_risk_budget": _first_mapping(snapshot_map, "position_risk_budget"),
        "risk_breakdown": _first_mapping(snapshot_map, "risk_breakdown"),
        "safety_line": _first_mapping(snapshot_map, "safety_line"),
        "today_action": _first_mapping(snapshot_map, "today_action", "decision_packet"),
        "strategy_context": _first_mapping(snapshot_map, "strategy_packet"),
        "data_freshness": _first_mapping(snapshot_map, "data_freshness"),
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_tushare": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_run_backtest": True,
            "does_not_recalculate_position": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_holdings": True,
            "source": "local command_center_latest snapshot",
        },
        "call_ledger": [
            {
                "api": "local_position_context_cache",
                "source_snapshot": "command_center_latest.json",
                "call_status": call_status,
                "local_fetched_at": _now_iso(),
                "external": False,
            }
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/position/cache 只读展示本地持仓画像和首页快照摘要。",
            "本页不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，也不会修改持仓或 strategy action。",
            "价格、成本和浮盈亏均来自既有缓存；无缓存时显示缺口，不自动刷新。",
        ],
    }
    if status == "cache_missing":
        packet["warnings"].append("当前没有本地持仓画像缓存；请在 legacy/admin/debug 或后续按钮任务中生成。")
    return _json_safe(packet)
