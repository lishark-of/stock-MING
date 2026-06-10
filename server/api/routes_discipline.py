from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import discipline_service


router = APIRouter(prefix="/api/discipline")


@router.get("/cache")
def get_discipline_loop_cache() -> dict:
    packet = discipline_service.read_discipline_loop_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
