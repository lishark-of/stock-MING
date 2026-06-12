from __future__ import annotations

from typing import Any

from server.services.task_service import create_task_stub
from worker.celery_app import task


@task("run_candidate_radar_full_pool_plan")
def run_candidate_radar_full_pool_plan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return create_task_stub("run_candidate_radar_full_pool_plan", output_packet_key="command_center_3_candidate_radar_cache", payload=payload)
