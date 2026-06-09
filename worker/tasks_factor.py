from __future__ import annotations

from typing import Any

from server.services.task_service import create_task_stub
from worker.celery_app import task


@task("refresh_factor_data")
def refresh_factor_data(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return create_task_stub("refresh_factor_data", output_packet_key="command_center_factor_quant_hub_packet", payload=payload)


@task("run_factor_light")
def run_factor_light(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return create_task_stub("run_factor_light", output_packet_key="command_center_factor_quant_hub_packet", payload=payload)
