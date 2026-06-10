from __future__ import annotations

from fastapi import APIRouter, Query

from server.schemas.packets import envelope
from server.services import trade_review_service


router = APIRouter(prefix="/api/trade-review")


@router.get("/cache")
def get_trade_review_cache(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    packet = trade_review_service.read_trade_review_cache(limit=limit)
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
