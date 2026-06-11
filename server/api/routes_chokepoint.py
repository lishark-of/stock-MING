from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import cache_envelope
from server.services import packet_service
from server.services.task_service import create_task_stub


router = APIRouter(prefix="/api/chokepoint")


@router.get("/cache")
def get_chokepoint_cache() -> dict:
    packet = packet_service.build_chokepoint_cache()
    return cache_envelope(
        packet,
        route="GET /api/chokepoint/cache",
        missing_message="当前没有产业链瓶颈扫描缓存；GET cache 不会调用 DeepSeek。",
    )


@router.post("/run")
def run_chokepoint_scan(payload: dict[str, Any] | None = None) -> dict:
    task = create_task_stub(
        "run_chokepoint_scan",
        output_packet_key="command_center_chokepoint_scan_packet",
        payload=payload,
        current_step="chokepoint_scan_task_stub_created",
    )
    return task_envelope(task)
