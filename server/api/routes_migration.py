from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import migration_status_service


router = APIRouter(prefix="/api/migration")


@router.get("/status")
def get_migration_status() -> dict:
    packet = migration_status_service.build_migration_status()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
