from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import strategy_service


router = APIRouter(prefix="/api/strategy")


@router.get("/cache")
def get_strategy_trace_cache() -> dict:
    packet = strategy_service.read_strategy_trace_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
