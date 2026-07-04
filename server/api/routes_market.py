from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import market_service


router = APIRouter(prefix="/api/market")


@router.get("/cache")
def get_market_context_cache() -> dict:
    packet = market_service.read_market_context_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/margin-etf-local-refresh")
def refresh_margin_etf_local_packets(payload: dict[str, Any] | None = None) -> dict:
    task = market_service.run_margin_etf_local_refresh_task(payload)
    return task_envelope(task)
