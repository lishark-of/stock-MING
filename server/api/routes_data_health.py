from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import data_health_service


router = APIRouter(prefix="/api/data-health")


@router.get("/cache")
def get_data_health_timeline_cache() -> dict:
    packet = data_health_service.read_data_health_timeline_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
