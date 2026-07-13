from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import qmt_readonly_service


router = APIRouter(prefix="/api/qmt-replay")


@router.get("/cache")
def get_qmt_replay_cache() -> dict:
    packet = qmt_readonly_service.read_qmt_replay_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/local-simulate")
def run_qmt_local_simulate(payload: dict[str, Any] | None = None) -> dict:
    packet = qmt_readonly_service.run_qmt_readonly_local_replay(payload or {})
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
