from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import cache_envelope, envelope
from server.services import packet_service


router = APIRouter(prefix="/api/packets")


@router.get("")
def list_packets() -> dict:
    index = packet_service.list_packets()
    return envelope(index, call_ledger=packet_service.packet_index_call_ledger(index), warnings=index.get("warnings"))


@router.get("/{packet_key}")
def get_packet(packet_key: str) -> dict:
    packet = packet_service.read_packet(packet_key)
    return cache_envelope(
        packet,
        route="GET /api/packets/{packet_key}",
        missing_message="未发现该 packet 的本地缓存；GET 详情接口不会触发外部刷新。",
        call_ledger=packet_service.packet_detail_call_ledger(packet),
        warnings=packet.get("warnings"),
    )
