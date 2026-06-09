from __future__ import annotations

from typing import Any

from server.services.task_service import create_task_stub
from worker.celery_app import task


@task("run_chokepoint_scan")
def run_chokepoint_scan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return create_task_stub("run_chokepoint_scan", output_packet_key="command_center_chokepoint_scan_packet", payload=payload)


@task("probe_serenity_github")
def probe_serenity_github(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return create_task_stub("probe_serenity_github", output_packet_key="command_center_serenity_method_radar_packet", payload=payload)
