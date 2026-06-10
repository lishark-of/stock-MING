from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any

from server.services import packet_service


PACKET_KEY = "command_center_3_discipline_loop_cache"
SCHEMA_VERSION = "discipline_loop_cache.v1"
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
        return {"serialization_error_safe": "discipline_loop_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _rows(value: Any, *, source: str, text_key: str = "label") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        items = value.get("items") or value.get("steps") or value.get("rules")
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


def _refresh_counts(steps: list[Any]) -> dict[str, int]:
    completed = skipped = failed = running = 0
    for raw in steps:
        item = _as_dict(raw)
        status = str(item.get("status") or "").lower()
        label = str(item.get("label") or "")
        if status in {"completed", "success", "ready"} or "完成" in label:
            completed += 1
        elif status in {"skipped", "skip"} or "跳过" in label:
            skipped += 1
        elif status in {"failed", "error"} or item.get("error"):
            failed += 1
        elif status in {"running", "pending"}:
            running += 1
    return {"completed": completed, "skipped": skipped, "failed": failed, "running": running}


def read_discipline_loop_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}

    discipline_packet = _as_dict(snapshot_map.get("discipline_packet"))
    decision_loop_status = _as_dict(snapshot_map.get("decision_loop_status"))
    today_action = _as_dict(snapshot_map.get("today_action"))
    decision_packet = _as_dict(snapshot_map.get("decision_packet"))
    strategy_packet = _as_dict(snapshot_map.get("strategy_packet"))
    full_refresh_steps = _as_list(snapshot_map.get("full_refresh_steps"))
    errors = _as_list(snapshot_map.get("errors"))
    latest_recovery_result_notice = _as_dict(snapshot_map.get("latest_recovery_result_notice"))
    home_data_issue_brief = _as_dict(snapshot_map.get("home_data_issue_brief"))
    data_issue_explainer = _as_dict(snapshot_map.get("data_issue_explainer"))

    discipline_metric_rows = _rows(discipline_packet.get("metric_items"), source="discipline_packet.metric_items")
    discipline_rule_rows = _rows(discipline_packet.get("key_rules"), source="discipline_packet.key_rules", text_key="rule")
    decision_loop_rows = _rows(decision_loop_status.get("items"), source="decision_loop_status.items")
    recovery_queue_rows = _rows(decision_loop_status.get("recovery_queue"), source="decision_loop_status.recovery_queue")
    recovery_action_rows = _rows(decision_loop_status.get("recovery_actions"), source="decision_loop_status.recovery_actions")
    refresh_step_rows = _rows(full_refresh_steps, source="full_refresh_steps", text_key="step")
    error_rows = _rows(errors, source="errors", text_key="error")
    refresh_counts = _refresh_counts(full_refresh_steps)

    has_cache = any(
        bool(item)
        for item in (
            discipline_packet,
            decision_loop_status,
            today_action,
            decision_packet,
            strategy_packet,
            full_refresh_steps,
            errors,
            latest_recovery_result_notice,
            home_data_issue_brief,
            data_issue_explainer,
        )
    )
    status = "ready" if discipline_packet or decision_loop_status or today_action else "partial" if has_cache or snapshot else "cache_missing"
    summary = (
        discipline_packet.get("summary")
        or decision_loop_status.get("summary")
        or decision_packet.get("reason_summary")
        or "交易纪律 / 决策闭环 cache 只读展示；页面打开不会运行回测或重算 action。"
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
            "discipline_packet",
            "decision_loop_status",
            "today_action",
            "decision_packet",
            "strategy_packet",
            "full_refresh_steps",
            "errors",
            "latest_recovery_result_notice",
            "home_data_issue_brief",
            "data_issue_explainer",
        ],
        "summary": summary,
        "discipline_packet": discipline_packet,
        "decision_loop_status": decision_loop_status,
        "today_action": today_action,
        "decision_packet": decision_packet,
        "strategy_packet": strategy_packet,
        "latest_recovery_result_notice": latest_recovery_result_notice,
        "home_data_issue_brief": home_data_issue_brief,
        "data_issue_explainer": data_issue_explainer,
        "discipline_metric_rows": discipline_metric_rows,
        "discipline_rule_rows": discipline_rule_rows,
        "decision_loop_rows": decision_loop_rows,
        "recovery_queue_rows": recovery_queue_rows,
        "recovery_action_rows": recovery_action_rows,
        "refresh_step_rows": refresh_step_rows,
        "error_rows": error_rows,
        "counts": {
            "discipline_metric_count": len(discipline_metric_rows),
            "discipline_rule_count": len(discipline_rule_rows),
            "decision_loop_item_count": len(decision_loop_rows),
            "recovery_queue_count": len(recovery_queue_rows),
            "recovery_action_count": len(recovery_action_rows),
            "refresh_step_count": len(refresh_step_rows),
            "refresh_completed_count": refresh_counts["completed"],
            "refresh_skipped_count": refresh_counts["skipped"],
            "refresh_failed_count": refresh_counts["failed"],
            "refresh_running_count": refresh_counts["running"],
            "error_count": len(error_rows),
            "loop_ready_count": decision_loop_status.get("ready_count", 0),
            "loop_waiting_count": decision_loop_status.get("waiting_count", 0),
            "loop_blocked_count": decision_loop_status.get("blocked_count", 0),
            "loop_manual_count": decision_loop_status.get("manual_count", 0),
        },
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_tushare": True,
            "does_not_call_akshare": True,
            "does_not_call_yfinance": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_run_backtest": True,
            "does_not_run_full_refresh": True,
            "does_not_recompute_action": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_decision_packet": True,
            "does_not_modify_holdings": True,
            "discipline_cache_is_not_trade_instruction": True,
            "post_task_required_for_recheck": True,
        },
        "call_ledger": [
            {
                "api": "local_discipline_loop_cache",
                "source_snapshot": "command_center_latest.json",
                "row_count": len(discipline_metric_rows) + len(decision_loop_rows) + len(refresh_step_rows),
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
        "does_not_modify_decision_packet": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/discipline/cache 只读展示交易纪律与决策闭环缓存；不会运行回测或满血刷新。",
            "纪律分数和胜率只用于约束与复盘，不直接生成买卖指令。",
            "本页不调用 Tushare、AkShare、yfinance、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。",
        ],
    }
    if status == "cache_missing":
        packet["warnings"].append("当前没有交易纪律 / 决策闭环缓存；3.0 cache 页不会自动运行回测。")
    return _json_safe(packet)
