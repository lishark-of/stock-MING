from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import audit_service


router = APIRouter(prefix="/api/audit")


@router.get("/cache")
def get_call_ledger_audit_cache() -> dict:
    packet = audit_service.read_call_ledger_audit_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
