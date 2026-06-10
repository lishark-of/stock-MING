from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import packet_service


router = APIRouter(prefix="/api/packets")


@router.get("")
def list_packets() -> dict:
    index = packet_service.list_packets()
    return envelope(index, call_ledger=packet_service.packet_index_call_ledger(index), warnings=index.get("warnings"))


@router.get("/{packet_key}")
def get_packet(packet_key: str) -> dict:
    packet = packet_service.read_packet(packet_key)
    return envelope(packet, call_ledger=packet_service.packet_detail_call_ledger(packet), warnings=packet.get("warnings"))
