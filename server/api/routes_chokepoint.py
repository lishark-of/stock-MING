from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import packet_service
from server.services.task_service import create_task_stub


router = APIRouter(prefix="/api/chokepoint")


@router.get("/cache")
def get_chokepoint_cache() -> dict:
    packet = packet_service.build_chokepoint_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/run")
def run_chokepoint_scan(payload: dict[str, Any] | None = None) -> dict:
    task = create_task_stub(
        "run_chokepoint_scan",
        output_packet_key="command_center_chokepoint_scan_packet",
        payload=payload,
        current_step="chokepoint_scan_task_stub_created",
    )
    return task_envelope(task)
