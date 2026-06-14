from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import bootstrap_service


router = APIRouter(prefix="/api/bootstrap")


@router.get("/status")
def get_bootstrap_status() -> dict:
    packet = bootstrap_service.read_bootstrap_status_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
