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


@router.get("/{task_id}/logs")
def get_task_logs(task_id: str) -> dict:
    packet = task_service.build_task_log_packet(task_id)
    if packet is None:
        return envelope(
            {},
            ok=False,
            error="task_not_found",
            call_ledger=task_service.task_not_found_call_ledger(task_id, api="local_task_log_lookup"),
            warnings=task_service.task_not_found_warnings("GET /api/tasks/{task_id}/logs"),
        )
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


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


@router.post("/{task_id}/retry")
def retry_task(task_id: str, payload: dict[str, Any] | None = None) -> dict:
    result = task_service.retry_task(task_id, payload)
    if result is None:
        return envelope(
            {},
            ok=False,
            error="task_not_found",
            call_ledger=task_service.task_not_found_call_ledger(task_id, api="local_task_retry"),
            warnings=task_service.task_not_found_warnings("POST /api/tasks/{task_id}/retry"),
        )
    if not result.get("ok"):
        return envelope(
            {"task": result.get("task")},
            ok=False,
            error=result.get("error") or "manual_retry_not_eligible",
            call_ledger=result.get("call_ledger"),
            warnings=result.get("warnings"),
        )
    task = result["task"]
    return envelope(
        {"task_id": task["task_id"], "task": task, "source_task_id": task.get("retry_source_task_id")},
        call_ledger=result.get("call_ledger") or task.get("call_ledger"),
        warnings=result.get("warnings") or task.get("warnings"),
    )
