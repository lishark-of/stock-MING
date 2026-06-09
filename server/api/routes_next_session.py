from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import next_session_service


router = APIRouter(prefix="/api/next-session")


@router.get("/cache")
def get_next_session_cache() -> dict:
    return envelope(next_session_service.read_next_session_cache())


@router.post("/generate")
def generate_next_session(payload: dict[str, Any] | None = None) -> dict:
    task = next_session_service.create_next_session_task(payload)
    return envelope({"task_id": task["task_id"], "task": task})
