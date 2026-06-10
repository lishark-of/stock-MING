from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any


_TASKS: dict[str, dict[str, Any]] = {}
TASK_STATUSES = {"pending", "running", "success", "failed", "cancelled"}
SECRET_KEYWORDS = ("token", "api_key", "secret", "password", "authorization", "bearer", "cookie")


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _is_secret_key(key: Any) -> bool:
    lowered = str(key).lower()
    return any(marker in lowered for marker in SECRET_KEYWORDS)


def _safe_value(key: Any, value: Any) -> Any:
    if _is_secret_key(key):
        return None
    if isinstance(value, dict):
        return {str(child_key): safe for child_key, child_value in value.items() if (safe := _safe_value(child_key, child_value)) is not None}
    if isinstance(value, list):
        return [_safe_value(key, item) for item in value]
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
    return task


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
    return _TASKS.get(str(task_id))


def list_task_statuses() -> list[dict[str, Any]]:
    return list(_TASKS.values())


def clear_task_statuses_for_tests() -> None:
    _TASKS.clear()
