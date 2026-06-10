from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import desktop_service


router = APIRouter(prefix="/api/desktop")


@router.get("/preflight-cache")
def get_desktop_shell_preflight_cache() -> dict:
    packet = desktop_service.read_desktop_shell_preflight_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
