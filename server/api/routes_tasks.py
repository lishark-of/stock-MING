from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import task_service, tushare_task_service


router = APIRouter(prefix="/api/tasks")


@router.get("")
def list_tasks() -> dict:
    index = task_service.build_task_status_index()
    return envelope(index, call_ledger=index.get("call_ledger"), warnings=index.get("warnings"))


@router.get("/catalog")
def get_task_catalog() -> dict:
    catalog = task_service.build_task_catalog()
    return envelope(catalog, call_ledger=catalog.get("call_ledger"), warnings=catalog.get("warnings"))


@router.post("/refresh-tushare-facts")
def refresh_tushare_facts(payload: dict[str, Any] | None = None) -> dict:
    task = tushare_task_service.run_tushare_refresh_task(payload)
    return task_envelope(task)


@router.get("/{task_id}")
def get_task(task_id: str) -> dict:
    task = task_service.read_task_status(task_id)
    if task is None:
        return envelope(
            {},
            ok=False,
            error="task_not_found",
            call_ledger=task_service.task_not_found_call_ledger(task_id),
            warnings=task_service.task_not_found_warnings("GET /api/tasks/{task_id}"),
        )
    return envelope(task, call_ledger=task.get("call_ledger"), warnings=task.get("warnings"))


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, payload: dict[str, Any] | None = None) -> dict:
    task = task_service.cancel_task(task_id, payload)
    if task is None:
        return envelope(
            {},
            ok=False,
            error="task_not_found",
            call_ledger=task_service.task_not_found_call_ledger(task_id, api="local_task_cancel"),
            warnings=task_service.task_not_found_warnings("POST /api/tasks/{task_id}/cancel"),
        )
    return task_envelope(task)
