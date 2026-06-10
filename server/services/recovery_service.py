from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any

from server.services import packet_service


PACKET_KEY = "command_center_3_recovery_center_cache"
SCHEMA_VERSION = "recovery_center_cache.v1"
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
        return {"serialization_error_safe": "recovery_center_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _rows(value: Any, *, source: str, text_key: str = "label") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        items = value.get("items") or value.get("actions") or value.get("rows")
        if isinstance(items, list):
            return _rows(items, source=source, text_key=text_key)
        for key, val in value.items():
            if isinstance(val, Mapping):
                row = dict(val)
                row.setdefault("key", key)
                row.setdefault("source", source)
                rows.append(row)
            elif isinstance(val, list):
                rows.extend(_rows(val, source=f"{source}.{key}", text_key=text_key))
        return rows[:80]
    for idx, raw in enumerate(_as_list(value), start=1):
        if isinstance(raw, Mapping):
            row = dict(raw)
            row.setdefault("index", idx)
            row.setdefault("source", source)
            rows.append(row)
        elif raw is not None:
            rows.append({"index": idx, "source": source, text_key: _safe_text(raw)})
    return rows[:80]


def _timeline_rows(*values: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, value in enumerate(values, start=1):
        rows.extend(_rows(value, source=f"timeline_{idx}", text_key="event"))
    return rows[:120]


def read_recovery_center_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}

    data_recovery_center = _as_dict(snapshot_map.get("data_recovery_center"))
    data_recovery_actions = _rows(snapshot_map.get("data_recovery_actions"), source="data_recovery_actions")
    tool_recovery_actions = _rows(snapshot_map.get("tool_recovery_actions"), source="tool_recovery_actions")
    timeline_rows = _timeline_rows(
        snapshot_map.get("recovery_result_timeline"),
        snapshot_map.get("command_center_recovery_result_timeline"),
        snapshot_map.get("data_health_timeline"),
        snapshot_map.get("command_center_data_health_timeline"),
    )
    health_timeline_actions = _rows(
        snapshot_map.get("data_health_timeline_recovery_actions")
        or snapshot_map.get("command_center_data_health_timeline_recovery_actions"),
        source="data_health_timeline_recovery_actions",
    )
    evidence_recovery_rows = _rows(snapshot_map.get("a_share_evidence_recovery_ledger"), source="a_share_evidence_recovery_ledger")
    a_share_fact_summary = _as_dict(snapshot_map.get("a_share_fact_recovery_summary"))
    legacy_actions = _rows(
        snapshot_map.get("legacy_a_share_fact_recovery_actions")
        or snapshot_map.get("legacy_a_share_gap_summary"),
        source="legacy_a_share_fact_recovery_actions",
    )
    provider_matrix_rows = _rows(snapshot_map.get("provider_recovery_matrix"), source="provider_recovery_matrix")
    old_workspace_absence = _as_dict(snapshot_map.get("old_workspace_data_absence_ledger"))
    data_gap_report = _as_dict(snapshot_map.get("data_gap_report"))
    recovery_status = _as_dict(snapshot_map.get("recovery_result_status_strip"))

    action_rows = (
        data_recovery_actions
        + tool_recovery_actions
        + health_timeline_actions
        + evidence_recovery_rows
        + legacy_actions
        + provider_matrix_rows
    )[:160]
    has_specific_cache = any(
        bool(item)
        for item in (
            data_recovery_center,
            action_rows,
            timeline_rows,
            a_share_fact_summary,
            old_workspace_absence,
            data_gap_report,
            recovery_status,
        )
    )
    status = "ready" if action_rows or timeline_rows or recovery_status else "partial" if has_specific_cache or snapshot else "cache_missing"
    summary = (
        data_recovery_center.get("summary")
        or recovery_status.get("summary")
        or a_share_fact_summary.get("summary")
        or "数据恢复中心 cache 只读展示；页面打开不会自动刷新或探测接口。"
    )

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "snapshot_available": bool(snapshot),
        "source_packet_keys": [
            "data_recovery_center",
            "data_recovery_actions",
            "tool_recovery_actions",
            "recovery_result_timeline",
            "data_health_timeline",
            "data_health_timeline_recovery_actions",
            "a_share_evidence_recovery_ledger",
            "a_share_fact_recovery_summary",
            "legacy_a_share_fact_recovery_actions",
            "provider_recovery_matrix",
            "old_workspace_data_absence_ledger",
            "data_gap_report",
            "recovery_result_status_strip",
        ],
        "summary": summary,
        "data_recovery_center": data_recovery_center,
        "recovery_result_status_strip": recovery_status,
        "action_rows": action_rows,
        "timeline_rows": timeline_rows,
        "data_recovery_actions": data_recovery_actions,
        "tool_recovery_actions": tool_recovery_actions,
        "health_timeline_actions": health_timeline_actions,
        "evidence_recovery_rows": evidence_recovery_rows,
        "legacy_actions": legacy_actions,
        "provider_matrix_rows": provider_matrix_rows,
        "a_share_fact_recovery_summary": a_share_fact_summary,
        "old_workspace_data_absence_ledger": old_workspace_absence,
        "data_gap_report": data_gap_report,
        "counts": {
            "action_count": len(action_rows),
            "timeline_count": len(timeline_rows),
            "data_recovery_action_count": len(data_recovery_actions),
            "tool_recovery_action_count": len(tool_recovery_actions),
            "evidence_recovery_count": len(evidence_recovery_rows),
            "legacy_action_count": len(legacy_actions),
            "provider_recovery_count": len(provider_matrix_rows),
            "data_gap_count": len(_as_list(data_gap_report.get("items")) or _as_list(data_gap_report.get("gaps"))),
        },
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_tushare": True,
            "does_not_call_akshare": True,
            "does_not_call_yfinance": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_probe_providers": True,
            "does_not_run_recovery_actions": True,
            "does_not_refresh_data": True,
            "does_not_run_backtest": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_holdings": True,
            "recovery_actions_are_manual_guidance": True,
            "post_task_required_for_refresh": True,
        },
        "call_ledger": [
            {
                "api": "local_recovery_center_cache",
                "source_snapshot": "command_center_latest.json",
                "row_count": len(action_rows),
                "timeline_count": len(timeline_rows),
                "call_status": "cache_read" if snapshot else "cache_missing",
                "local_fetched_at": _now_iso(),
                "external": False,
            }
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "akshare_called": False,
        "yfinance_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/recovery/cache 只读展示本地恢复路线；不会自动刷新数据或探测接口。",
            "恢复动作只是手动建议；必须通过后续按钮门控任务才能触发外部请求。",
            "本页不调用 Tushare、AkShare、yfinance、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。",
        ],
    }
    if status == "cache_missing":
        packet["warnings"].append("当前没有数据恢复中心缓存；3.0 cache 页不会自动创建恢复任务。")
    return _json_safe(packet)
