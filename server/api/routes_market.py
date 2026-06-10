from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import market_service


router = APIRouter(prefix="/api/market")


@router.get("/cache")
def get_market_context_cache() -> dict:
    packet = market_service.read_market_context_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
