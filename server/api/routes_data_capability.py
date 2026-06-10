from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import data_capability_service


router = APIRouter(prefix="/api/data-capability")


@router.get("/cache")
def get_data_capability_cache() -> dict:
    packet = data_capability_service.read_data_capability_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
