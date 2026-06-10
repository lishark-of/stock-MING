from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any

from server.services import packet_service


PACKET_KEY = "command_center_3_legacy_bridge_cache"
SCHEMA_VERSION = "legacy_bridge_cache.v1"
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
        return {"serialization_error_safe": "legacy_bridge_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _rows(value: Any, *, source: str, text_key: str = "label") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        items = value.get("items") or value.get("lanes") or value.get("next_actions") or value.get("priority_items")
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
        return rows[:100]
    for idx, raw in enumerate(_as_list(value), start=1):
        if isinstance(raw, Mapping):
            row = dict(raw)
            row.setdefault("index", idx)
            row.setdefault("source", source)
            rows.append(row)
        elif raw is not None:
            rows.append({"index": idx, "source": source, text_key: _safe_text(raw)})
    return rows[:100]


def _checklist_counts(checklist: Mapping[str, Any], capability: Mapping[str, Any]) -> dict[str, int]:
    checklist_items = _rows(checklist.get("items"), source="legacy_packet_migration_checklist.items")
    done = sum(1 for item in checklist_items if str(item.get("status") or item.get("state") or item.get("tone") or "").lower() in {"done", "ready", "complete", "completed"} or "完成" in str(item.get("status_label") or item.get("label") or ""))
    pending = sum(1 for item in checklist_items if "pending" in str(item.get("status") or item.get("state") or "").lower() or "待" in str(item.get("status_label") or item.get("label") or ""))
    return {
        "checklist_done_count": int(capability.get("checklist_done_count", done)),
        "checklist_pending_count": int(capability.get("checklist_pending_count", pending)),
    }


def read_legacy_bridge_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}

    migration_map = _as_dict(snapshot_map.get("legacy_migration_map"))
    checklist = _as_dict(snapshot_map.get("legacy_packet_migration_checklist"))
    packet_bridge = _as_dict(snapshot_map.get("old_workspace_packet_bridge"))
    capability = _as_dict(snapshot_map.get("old_workspace_capability_overview"))
    absence_ledger = _as_dict(snapshot_map.get("old_workspace_data_absence_ledger"))
    decision_chain = _as_dict(snapshot_map.get("legacy_decision_chain_summary"))
    gap_summary = _as_dict(snapshot_map.get("legacy_a_share_gap_summary"))
    fact_recovery_actions = _rows(snapshot_map.get("legacy_a_share_fact_recovery_actions"), source="legacy_a_share_fact_recovery_actions")

    migration_items = _rows(migration_map.get("items"), source="legacy_migration_map.items")
    migration_lanes = _rows(migration_map.get("lanes"), source="legacy_migration_map.lanes")
    checklist_items = _rows(checklist.get("items"), source="legacy_packet_migration_checklist.items")
    bridge_items = _rows(packet_bridge.get("items"), source="old_workspace_packet_bridge.items")
    capability_items = _rows(capability.get("items"), source="old_workspace_capability_overview.items")
    absence_items = _rows(absence_ledger.get("items"), source="old_workspace_data_absence_ledger.items")
    decision_chain_items = _rows(decision_chain.get("items"), source="legacy_decision_chain_summary.items")
    gap_items = _rows(gap_summary.get("items"), source="legacy_a_share_gap_summary.items")
    checklist_counts = _checklist_counts(checklist, capability)

    has_cache = any(
        bool(item)
        for item in (
            migration_map,
            checklist,
            packet_bridge,
            capability,
            absence_ledger,
            decision_chain,
            gap_summary,
            fact_recovery_actions,
        )
    )
    status = "ready" if migration_map or checklist or packet_bridge or capability else "partial" if has_cache or snapshot else "cache_missing"
    summary = (
        capability.get("summary")
        or packet_bridge.get("summary")
        or checklist.get("summary")
        or migration_map.get("summary")
        or "旧工作台桥接 cache 只读展示；Streamlit 保留为 legacy/admin/debug。"
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
            "legacy_migration_map",
            "legacy_packet_migration_checklist",
            "old_workspace_packet_bridge",
            "old_workspace_capability_overview",
            "old_workspace_data_absence_ledger",
            "legacy_decision_chain_summary",
            "legacy_a_share_gap_summary",
            "legacy_a_share_fact_recovery_actions",
        ],
        "summary": summary,
        "legacy_migration_map": migration_map,
        "legacy_packet_migration_checklist": checklist,
        "old_workspace_packet_bridge": packet_bridge,
        "old_workspace_capability_overview": capability,
        "old_workspace_data_absence_ledger": absence_ledger,
        "legacy_decision_chain_summary": decision_chain,
        "legacy_a_share_gap_summary": gap_summary,
        "migration_items": migration_items,
        "migration_lanes": migration_lanes,
        "checklist_items": checklist_items,
        "bridge_items": bridge_items,
        "capability_items": capability_items,
        "absence_items": absence_items,
        "decision_chain_items": decision_chain_items,
        "gap_items": gap_items,
        "fact_recovery_action_rows": fact_recovery_actions,
        "counts": {
            **checklist_counts,
            "migration_item_count": len(migration_items),
            "migration_lane_count": len(migration_lanes),
            "checklist_item_count": len(checklist_items),
            "bridge_item_count": len(bridge_items),
            "capability_item_count": len(capability_items),
            "absence_item_count": len(absence_items),
            "decision_chain_item_count": len(decision_chain_items),
            "fact_recovery_action_count": len(fact_recovery_actions),
            "decision_ready_count": decision_chain.get("ready_count", 0),
            "decision_waiting_count": decision_chain.get("waiting_count", 0),
            "decision_blocked_count": decision_chain.get("blocked_count", 0),
        },
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_tushare": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_open_streamlit": True,
            "does_not_run_legacy_tools": True,
            "does_not_run_backtest": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_holdings": True,
            "streamlit_role": "legacy/admin/debug",
            "react_tauri_is_primary_entry": True,
            "legacy_bridge_is_not_trade_instruction": True,
            "post_task_required_for_migration_work": True,
        },
        "call_ledger": [
            {
                "api": "local_legacy_bridge_cache",
                "source_snapshot": "command_center_latest.json",
                "row_count": len(migration_items) + len(checklist_items) + len(bridge_items),
                "call_status": "cache_read" if snapshot else "cache_missing",
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
            "GET /api/legacy/cache 只读展示旧工作台桥接和迁移清单；不会打开 Streamlit 或运行旧工具。",
            "Streamlit 仅保留为 legacy/admin/debug；普通主流程迁往 React/Tauri + FastAPI。",
            "本页不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。",
        ],
    }
    if status == "cache_missing":
        packet["warnings"].append("当前没有旧工作台桥接缓存；3.0 cache 页不会自动扫描旧工具。")
    return _json_safe(packet)
