from __future__ import annotations

import datetime as _dt
import uuid
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore


_TASKS: dict[str, dict[str, Any]] = {}
TASK_STATUSES = {"pending", "running", "success", "failed", "cancelled"}
SECRET_KEYWORDS = ("token", "api_key", "secret", "password", "authorization", "bearer", "cookie")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")
SQLITE_META_PATH = Path(__file__).resolve().parents[2] / ".stock_ming_3" / "meta.sqlite"

TASK_CATALOG = [
    {
        "task_type": "refresh_factor_data",
        "route": "POST /api/factor-quant/refresh-data",
        "label": "刷新因子数据",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_fallback_stub",
        "external_call_policy": "button_gated_tushare_capable",
        "possible_external_sources": ["tushare"],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_factor_light",
        "route": "POST /api/factor-quant/run-light",
        "label": "运行 light mode 因子计算",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_light_pipeline",
        "external_call_policy": "local_cache_only_current_mvp",
        "possible_external_sources": [],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_deepseek_factor_explanation",
        "route": "POST /api/factor-quant/deepseek-explain",
        "label": "DeepSeek 整理因子解释",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "guarded_prompt_or_payload_sanitizer",
        "external_call_policy": "manual_deepseek_capable_current_no_model_call",
        "possible_external_sources": ["deepseek"],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "build_next_session_projection",
        "route": "POST /api/next-session/generate",
        "label": "生成次日操作图谱",
        "output_packet_key": "command_center_next_session_projection_packet",
        "button_gated": True,
        "current_backend": "local_fallback_stub",
        "external_call_policy": "button_gated_refresh_capable",
        "possible_external_sources": ["tushare"],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_chokepoint_scan",
        "route": "POST /api/chokepoint/run",
        "label": "运行产业链瓶颈扫描",
        "output_packet_key": "command_center_chokepoint_scan_packet",
        "button_gated": True,
        "current_backend": "local_fallback_stub",
        "external_call_policy": "manual_deepseek_capable",
        "possible_external_sources": ["deepseek"],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "probe_serenity_github",
        "route": "POST /api/serenity/github-probe",
        "label": "校验 Serenity GitHub 当前状态",
        "output_packet_key": "command_center_serenity_method_radar_packet",
        "button_gated": True,
        "current_backend": "local_fallback_stub",
        "external_call_policy": "manual_github_probe_capable",
        "possible_external_sources": ["github"],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
]


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def build_task_catalog() -> dict[str, Any]:
    return {
        "packet_key": "command_center_3_task_catalog",
        "schema_version": "command_center_3_task_catalog.v1",
        "status": "ready",
        "tasks": [dict(item) for item in TASK_CATALOG],
        "task_count": len(TASK_CATALOG),
        "policy": {
            "get_catalog_cache_only": True,
            "all_tasks_button_gated": all(bool(item.get("button_gated")) for item in TASK_CATALOG),
            "call_ledger_required_for_all": all(bool(item.get("call_ledger_required")) for item in TASK_CATALOG),
            "supports_local_task_cancel": True,
            "cancel_task_external_calls": False,
            "post_task_may_trigger_external_request": True,
            "cache_api_external_calls": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        },
        "external_sources": sorted({source for item in TASK_CATALOG for source in item.get("possible_external_sources", [])}),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
    }


def _is_secret_key(key: Any) -> bool:
    lowered = str(key).lower()
    return any(marker in lowered for marker in SECRET_KEYWORDS)


def _safe_text(value: Any, *, limit: int = 500) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in SENSITIVE_TEXT_MARKERS):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _safe_value(key: Any, value: Any) -> Any:
    if _is_secret_key(key):
        return None
    if isinstance(value, dict):
        return {str(child_key): safe for child_key, child_value in value.items() if (safe := _safe_value(child_key, child_value)) is not None}
    if isinstance(value, list):
        return [_safe_value(key, item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    return value


def _safe_payload(payload: Any = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {str(key): safe for key, value in payload.items() if (safe := _safe_value(key, value)) is not None}


def _status_event(status: str, *, progress: float, current_step: str, at: str | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "progress": float(progress),
        "current_step": current_step,
        "at": at or _now_iso(),
    }


def _persist_task(task: dict[str, Any]) -> dict[str, Any]:
    _TASKS[str(task["task_id"])] = task
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_task_status(task)
    except Exception:
        task.setdefault("warnings", []).append("task_metadata_sqlite_write_failed_safe")
    return task


def _read_persisted_task(task_id: str) -> dict[str, Any] | None:
    try:
        task = SQLiteMetaStore(SQLITE_META_PATH).read_task_status(str(task_id))
    except Exception:
        return None
    return task if isinstance(task, dict) else None


def _list_persisted_tasks() -> list[dict[str, Any]]:
    try:
        store = SQLiteMetaStore(SQLITE_META_PATH)
        tasks = [task for item in store.list_task_metadata() if (task := store.read_task_status(str(item.get("task_id") or "")))]
    except Exception:
        return []
    return [task for task in tasks if isinstance(task, dict)]


def _stub_call_ledger(task_type: str, now: str) -> list[dict[str, Any]]:
    return [
        {
            "api": task_type,
            "request_params_safe": {},
            "row_count": 0,
            "data_date": None,
            "local_fetched_at": now,
            "call_status": "stub_not_called",
            "error_message_safe": "",
        }
    ]


def _cancel_call_ledger(task_id: str, now: str, *, reason_safe: str = "") -> dict[str, Any]:
    return {
        "api": "local_task_cancel",
        "task_id": str(task_id),
        "request_params_safe": {"reason": reason_safe} if reason_safe else {},
        "row_count": 0,
        "data_date": None,
        "local_fetched_at": now,
        "call_status": "cancelled_locally_no_external_call",
        "error_message_safe": "",
        "external": False,
    }


def build_task_record(
    task_type: str,
    *,
    task_id: str | None = None,
    output_packet_key: str = "",
    payload: Any = None,
    status: str = "pending",
    progress: float = 0.0,
    current_step: str = "queued",
    warnings: list[str] | None = None,
    call_ledger: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected_status = status if status in TASK_STATUSES else "pending"
    now = _now_iso()
    record = {
        "task_id": task_id or f"local-{uuid.uuid4().hex[:12]}",
        "task_type": task_type,
        "status": selected_status,
        "created_at": now,
        "started_at": now if selected_status in {"running", "success", "failed"} else None,
        "finished_at": now if selected_status in {"success", "failed", "cancelled"} else None,
        "progress": max(0.0, min(1.0, float(progress))),
        "current_step": current_step,
        "error_message_safe": "",
        "output_packet_key": output_packet_key,
        "payload_safe": _safe_payload(payload),
        "warnings": list(warnings or []),
        "call_ledger": list(call_ledger or []),
        "backend": "local_fallback",
        "external_calls_triggered": False,
        "deepseek_called": False,
        "tushare_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "status_history": [_status_event(selected_status, progress=progress, current_step=current_step, at=now)],
    }
    return record


def create_task_record(
    task_type: str,
    *,
    output_packet_key: str = "",
    payload: Any = None,
    current_step: str = "queued",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    task = build_task_record(
        task_type,
        output_packet_key=output_packet_key,
        payload=payload,
        status="pending",
        progress=0.0,
        current_step=current_step,
        warnings=warnings,
    )
    return _persist_task(task)


def update_task_status(
    task_id: str,
    *,
    status: str,
    progress: float | None = None,
    current_step: str | None = None,
    error_message_safe: str | None = None,
    output_packet_key: str | None = None,
    call_ledger: list[dict[str, Any]] | None = None,
    warning: str | None = None,
) -> dict[str, Any] | None:
    task = read_task_status(task_id)
    if task is None:
        return None
    if status not in TASK_STATUSES:
        status = "failed"
        error_message_safe = error_message_safe or "invalid_task_status"
    now = _now_iso()
    task["status"] = status
    if progress is not None:
        task["progress"] = max(0.0, min(1.0, float(progress)))
    if current_step is not None:
        task["current_step"] = current_step
    if error_message_safe is not None:
        task["error_message_safe"] = str(error_message_safe)[:500]
    if output_packet_key is not None:
        task["output_packet_key"] = output_packet_key
    if call_ledger is not None:
        task["call_ledger"] = list(call_ledger)
    if warning:
        task.setdefault("warnings", []).append(warning)
    if status in {"running", "success", "failed"} and not task.get("started_at"):
        task["started_at"] = now
    if status in {"success", "failed", "cancelled"}:
        task["finished_at"] = now
    task.setdefault("status_history", []).append(
        _status_event(status, progress=float(task.get("progress") or 0.0), current_step=str(task.get("current_step") or ""), at=now)
    )
    return _persist_task(task)


def cancel_task(task_id: str, payload: Any = None) -> dict[str, Any] | None:
    task = read_task_status(task_id)
    if task is None:
        return None

    payload_safe = _safe_payload(payload)
    reason_safe = _safe_text(payload_safe.get("reason", "")) if isinstance(payload_safe, dict) else ""
    now = _now_iso()
    existing_ledger = list(task.get("call_ledger") or [])
    cancel_ledger = existing_ledger + [_cancel_call_ledger(str(task_id), now, reason_safe=reason_safe)]
    terminal = {"success", "failed", "cancelled"}
    if task.get("status") in terminal:
        task["call_ledger"] = cancel_ledger
        task.setdefault("warnings", []).append("task_cancel_noop_already_terminal")
        task["external_calls_triggered"] = False
        task["deepseek_called"] = False
        task["tushare_called"] = False
        task["github_called"] = False
        task["does_not_execute_trades"] = True
        task["does_not_modify_strategy_action"] = True
        return _persist_task(task)

    return update_task_status(
        str(task_id),
        status="cancelled",
        progress=float(task.get("progress") or 0.0),
        current_step="cancelled_by_user_no_external_call",
        error_message_safe="",
        call_ledger=cancel_ledger,
        warning="task_cancelled_locally_no_external_call",
    )


def create_task_stub(
    task_type: str,
    *,
    output_packet_key: str = "",
    payload: Any = None,
    current_step: str = "stub_created_no_external_call",
) -> dict[str, Any]:
    now = _now_iso()
    task = build_task_record(
        task_type,
        output_packet_key=output_packet_key,
        payload=payload,
        status="pending",
        progress=0.0,
        current_step="queued",
        warnings=["Command Center 3.0 MVP 任务接口为本地 lifecycle stub；没有调用 Tushare、DeepSeek、GitHub 或真实交易接口。"],
    )
    _persist_task(task)
    update_task_status(task["task_id"], status="running", progress=0.5, current_step="local_fallback_running")
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=current_step,
        call_ledger=_stub_call_ledger(task_type, now),
    ) or task


def read_task_status(task_id: str) -> dict[str, Any] | None:
    return _TASKS.get(str(task_id)) or _read_persisted_task(str(task_id))


def list_task_statuses() -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for task in _list_persisted_tasks():
        task_id = str(task.get("task_id") or "")
        if task_id:
            merged[task_id] = task
    for task_id, task in _TASKS.items():
        merged[str(task_id)] = task
    return sorted(
        merged.values(),
        key=lambda item: str(item.get("finished_at") or item.get("started_at") or item.get("created_at") or ""),
        reverse=True,
    )


def clear_task_statuses_for_tests(*, clear_persisted: bool = False) -> None:
    _TASKS.clear()
    if not clear_persisted:
        return
    try:
        SQLiteMetaStore(SQLITE_META_PATH).clear_task_statuses()
    except Exception:
        return
