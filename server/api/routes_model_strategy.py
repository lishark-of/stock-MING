from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import model_strategy_service


router = APIRouter(prefix="/api/model-strategy")


@router.get("/cache")
def get_deepseek_model_strategy_cache() -> dict:
    packet = model_strategy_service.read_deepseek_model_strategy_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
