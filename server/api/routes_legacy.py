from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import legacy_service


router = APIRouter(prefix="/api/legacy")


@router.get("/cache")
def get_legacy_bridge_cache() -> dict:
    packet = legacy_service.read_legacy_bridge_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
