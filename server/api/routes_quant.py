from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import quant_service


router = APIRouter(prefix="/api/quant")


@router.get("/cache")
def get_quant_backtest_cache() -> dict:
    packet = quant_service.read_quant_backtest_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
