from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any


_TASKS: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _safe_payload(payload: Any = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    blocked = {"token", "api_key", "secret", "password", "authorization"}
    safe: dict[str, Any] = {}
    for key, value in payload.items():
        if str(key).lower() in blocked:
            continue
        safe[str(key)] = value
    return safe


def create_task_stub(
    task_type: str,
    *,
    output_packet_key: str = "",
    payload: Any = None,
    current_step: str = "stub_created_no_external_call",
) -> dict[str, Any]:
    now = _now_iso()
    task_id = f"local-{uuid.uuid4().hex[:12]}"
    task = {
        "task_id": task_id,
        "task_type": task_type,
        "status": "success",
        "created_at": now,
        "started_at": now,
        "finished_at": now,
        "progress": 1.0,
        "current_step": current_step,
        "error_message_safe": "",
        "output_packet_key": output_packet_key,
        "payload_safe": _safe_payload(payload),
        "warnings": [
            "Command Center 3.0 MVP 任务接口为本地 stub；没有调用 Tushare、DeepSeek、GitHub 或真实交易接口。"
        ],
    }
    _TASKS[task_id] = task
    return task


def read_task_status(task_id: str) -> dict[str, Any] | None:
    return _TASKS.get(str(task_id))


def list_task_statuses() -> list[dict[str, Any]]:
    return list(_TASKS.values())
