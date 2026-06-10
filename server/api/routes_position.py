from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import position_service


router = APIRouter(prefix="/api/position")


@router.get("/cache")
def get_position_context_cache() -> dict:
    packet = position_service.read_position_context_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
