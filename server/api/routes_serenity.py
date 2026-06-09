from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import packet_service
from server.services.task_service import create_task_stub


router = APIRouter(prefix="/api/serenity")


@router.get("/cache")
def get_serenity_cache() -> dict:
    return envelope(packet_service.build_serenity_cache())


@router.post("/github-probe")
def probe_serenity_github(payload: dict[str, Any] | None = None) -> dict:
    task = create_task_stub(
        "probe_serenity_github",
        output_packet_key="command_center_serenity_method_radar_packet",
        payload=payload,
        current_step="serenity_github_probe_task_stub_created",
    )
    return envelope({"task_id": task["task_id"], "task": task})
