from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import packet_service
from server.services.task_service import create_task_stub


router = APIRouter(prefix="/api/serenity")


@router.get("/cache")
def get_serenity_cache() -> dict:
    packet = packet_service.build_serenity_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/github-probe")
def probe_serenity_github(payload: dict[str, Any] | None = None) -> dict:
    task = create_task_stub(
        "probe_serenity_github",
        output_packet_key="command_center_serenity_method_radar_packet",
        payload=payload,
        current_step="serenity_github_probe_task_stub_created",
    )
    return task_envelope(task)
