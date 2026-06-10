from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import recovery_service


router = APIRouter(prefix="/api/recovery")


@router.get("/cache")
def get_recovery_center_cache() -> dict:
    packet = recovery_service.read_recovery_center_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
