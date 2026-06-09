from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import packet_service


router = APIRouter(prefix="/api/packets")


@router.get("")
def list_packets() -> dict:
    return envelope(packet_service.list_packets())


@router.get("/{packet_key}")
def get_packet(packet_key: str) -> dict:
    return envelope(packet_service.read_packet(packet_key))
