from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import task_service


router = APIRouter(prefix="/api/tasks")


@router.get("")
def list_tasks() -> dict:
    return envelope({"tasks": task_service.list_task_statuses()})


@router.get("/catalog")
def get_task_catalog() -> dict:
    return envelope(task_service.build_task_catalog())


@router.get("/{task_id}")
def get_task(task_id: str) -> dict:
    task = task_service.read_task_status(task_id)
    if task is None:
        return envelope({}, ok=False, error="task_not_found")
    return envelope(task)


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, payload: dict[str, Any] | None = None) -> dict:
    task = task_service.cancel_task(task_id, payload)
    if task is None:
        return envelope({}, ok=False, error="task_not_found")
    return envelope({"task_id": task["task_id"], "task": task}, call_ledger=task.get("call_ledger"), warnings=task.get("warnings"))
