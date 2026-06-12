from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import candidate_service


router = APIRouter(prefix="/api/candidate-radar")


@router.get("/cache")
def get_candidate_radar_cache() -> dict:
    packet = candidate_service.read_candidate_radar_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/scan-quick")
def scan_candidate_radar_quick(payload: dict[str, Any] | None = None) -> dict:
    task = candidate_service.run_candidate_quick_scan_task(payload)
    return task_envelope(task)
