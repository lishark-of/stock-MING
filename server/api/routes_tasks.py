from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import task_service


router = APIRouter(prefix="/api/tasks")


@router.get("/{task_id}")
def get_task(task_id: str) -> dict:
    task = task_service.read_task_status(task_id)
    if task is None:
        return envelope({}, ok=False, error="task_not_found")
    return envelope(task)
