from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import risk_service


router = APIRouter(prefix="/api/risk")


@router.get("/cache")
def get_risk_guardrails_cache() -> dict:
    packet = risk_service.read_risk_guardrails_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
