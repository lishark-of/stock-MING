from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any

import command_center_quant_packet
from server.services import packet_service


PACKET_KEY = "command_center_3_quant_backtest_cache"
SCHEMA_VERSION = "quant_backtest_cache.v1"
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
        return {"serialization_error_safe": "quant_backtest_cache_not_json_serializable"}


def _is_cache_missing(packet: Any) -> bool:
    return not isinstance(packet, dict) or packet.get("status") == "cache_missing"


def _build_local_quant_packet_from_snapshot() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    if not snapshot:
        return command_center_quant_packet.build_command_center_quant_packet({})
    target = str(snapshot.get("target") or snapshot.get("ticker") or "").strip()
    live_packet = snapshot.get("live_packet") if isinstance(snapshot.get("live_packet"), dict) else snapshot
    return command_center_quant_packet.build_command_center_quant_packet(snapshot, live_packet=live_packet, target=target)


def _metric_items(quant_packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"label": "score", "value": quant_packet.get("score")},
        {"label": "confidence", "value": quant_packet.get("confidence")},
        {"label": "action_state", "value": quant_packet.get("action_state")},
        {"label": "data_status", "value": quant_packet.get("data_status")},
        {"label": "verification_status", "value": quant_packet.get("verification_status")},
    ]


def read_quant_backtest_cache() -> dict[str, Any]:
    cached = packet_service.read_packet("command_center_quant_packet")
    if _is_cache_missing(cached):
        quant_packet = _build_local_quant_packet_from_snapshot()
        cache_source = "local_builder_with_snapshot_context"
    else:
        quant_packet = cached
        cache_source = str(cached.get("cache_source") or "stock_ming_snapshot")

    safe_quant = _safe_value(quant_packet)
    if not isinstance(safe_quant, dict):
        safe_quant = {}
    status = str(safe_quant.get("status") or "cache_missing")
    record_status = "ready" if status in {"ready", "cached", "partial"} else "cache_missing"

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": record_status,
        "mode": "cache_only",
        "cache_only": True,
        "source_packet_key": "command_center_quant_packet",
        "cache_source": cache_source,
        "loaded_at": _now_iso(),
        "quant_packet": safe_quant,
        "metric_items": _metric_items(safe_quant),
        "evidence_items": safe_quant.get("evidence_items") if isinstance(safe_quant.get("evidence_items"), list) else [],
        "risk_notes": safe_quant.get("risk_notes") if isinstance(safe_quant.get("risk_notes"), list) else [],
        "decision_brief": safe_quant.get("decision_brief") if isinstance(safe_quant.get("decision_brief"), dict) else {},
        "backtest_reference": safe_quant.get("backtest_reference"),
        "manual_required_text": safe_quant.get("manual_required_text")
        or "完整量化推演、回测和 DeepSeek 解释必须手动触发。",
        "policy": {
            "cache_api_external_calls": False,
            "does_not_run_backtest": True,
            "does_not_call_deepseek": True,
            "does_not_call_tushare": True,
            "does_not_call_github": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "post_task_required_for_recompute": True,
        },
        "call_ledger": [
            {
                "api": "local_quant_backtest_cache",
                "source_packet_key": "command_center_quant_packet",
                "call_status": "cache_read" if record_status == "ready" else "cache_missing",
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
        "warnings": [
            "GET /api/quant/cache 只读展示本地量化/回测缓存；不会运行 backtester。",
            "回测收益不代表未来收益；量化摘要不得直接改写 strategy action。",
        ],
    }
    return _json_safe(packet)
