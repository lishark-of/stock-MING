from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any

import command_center_evidence_summary as evidence_summary
from server.services import packet_service


PACKET_KEY = "command_center_3_a_share_evidence_cache"
SCHEMA_VERSION = "a_share_evidence_cache.v1"
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
        return {"serialization_error_safe": "a_share_evidence_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _counts(radar: Mapping[str, Any], lineage: Mapping[str, Any]) -> dict[str, Any]:
    lineage_counts = _as_dict(lineage.get("counts"))
    return {
        "ready": radar.get("ready_count", 0),
        "cached": radar.get("cached_count", 0),
        "failed": radar.get("failed_count", 0),
        "missing": radar.get("missing_count", 0),
        "lineage_verified": lineage_counts.get("verified", 0),
        "lineage_blocked": lineage_counts.get("blocked", 0),
        "lineage_missing": lineage_counts.get("missing", 0),
        "lineage_cached": lineage_counts.get("cached", 0),
    }


def read_a_share_evidence_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    cached_radar = _as_dict(snapshot.get("command_center_evidence_radar_packet") or snapshot.get("a_share_evidence_packet"))
    if cached_radar:
        radar = cached_radar
        radar_source = "stock_ming_snapshot"
    else:
        radar = evidence_summary.build_a_share_evidence_radar_view_model(snapshot)
        radar_source = "local_builder_with_snapshot_context" if snapshot else "local_builder"

    cached_lineage = _as_dict(snapshot.get("a_share_fact_lineage_summary"))
    if cached_lineage:
        lineage = cached_lineage
        lineage_source = "stock_ming_snapshot"
    else:
        lineage = evidence_summary.build_a_share_fact_lineage_summary(snapshot, radar)
        lineage_source = "local_builder_with_snapshot_context" if snapshot else "local_builder"

    recovery_summary = evidence_summary.build_home_evidence_recovery_summary(radar)
    safe_radar = _safe_value(radar)
    safe_lineage = _safe_value(lineage)
    safe_recovery = _safe_value(recovery_summary)
    safe_radar = safe_radar if isinstance(safe_radar, dict) else {}
    safe_lineage = safe_lineage if isinstance(safe_lineage, dict) else {}
    safe_recovery = safe_recovery if isinstance(safe_recovery, dict) else {}
    status = "ready" if safe_radar or safe_lineage else "cache_missing"

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "cache_only",
        "cache_only": True,
        "loaded_at": _now_iso(),
        "source_snapshot_available": bool(snapshot),
        "evidence_radar_source": radar_source,
        "fact_lineage_source": lineage_source,
        "evidence_radar": safe_radar,
        "fact_lineage": safe_lineage,
        "recovery_summary": safe_recovery,
        "counts": _counts(safe_radar, safe_lineage),
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_tushare": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_run_backtest": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "post_task_required_for_refresh": True,
            "lineage_enters_core_action": False,
        },
        "call_ledger": [
            {
                "api": "local_a_share_evidence_cache",
                "radar_source": radar_source,
                "lineage_source": lineage_source,
                "call_status": "cache_read" if snapshot else "local_builder_no_snapshot",
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
            "GET /api/evidence/cache 只读整理本地 A 股证据雷达和事实血缘；不会刷新 Tushare。",
            "事实血缘只进入证据解释和路径置信度说明，不直接覆盖 strategy action。",
        ],
    }
    return _json_safe(packet)
