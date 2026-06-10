from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import worker_service


router = APIRouter(prefix="/api/worker")


@router.get("/cache")
def get_worker_runtime_cache() -> dict:
    packet = worker_service.read_worker_runtime_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
