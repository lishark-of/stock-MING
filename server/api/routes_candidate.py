from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import candidate_service


router = APIRouter(prefix="/api/candidate-radar")


@router.get("/cache")
def get_candidate_radar_cache() -> dict:
    packet = candidate_service.read_candidate_radar_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
