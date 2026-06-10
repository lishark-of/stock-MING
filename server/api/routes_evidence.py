from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import evidence_service


router = APIRouter(prefix="/api/evidence")


@router.get("/cache")
def get_a_share_evidence_cache() -> dict:
    packet = evidence_service.read_a_share_evidence_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
