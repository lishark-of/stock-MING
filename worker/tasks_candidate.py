from __future__ import annotations

from typing import Any

from server.services import candidate_service
from server.services.task_service import create_task_stub
from worker.celery_app import task


@task("run_candidate_radar_full_pool_plan")
def run_candidate_radar_full_pool_plan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return create_task_stub("run_candidate_radar_full_pool_plan", output_packet_key="command_center_3_candidate_radar_cache", payload=payload)


@task("run_candidate_radar_full_pool_local_scan")
def run_candidate_radar_full_pool_local_scan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return candidate_service.run_candidate_full_pool_local_scan_task(payload)


@task("run_candidate_radar_deep_scan_plan")
def run_candidate_radar_deep_scan_plan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return create_task_stub("run_candidate_radar_deep_scan_plan", output_packet_key="command_center_3_candidate_radar_cache", payload=payload)


@task("run_candidate_radar_deep_scan_local_review")
def run_candidate_radar_deep_scan_local_review(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return create_task_stub(
        "run_candidate_radar_deep_scan_local_review",
        output_packet_key="command_center_3_candidate_radar_cache",
        payload=payload,
    )


@task("run_candidate_radar_deep_scan_worker_fallback")
def run_candidate_radar_deep_scan_worker_fallback(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return candidate_service.run_candidate_deep_scan_worker_fallback_task(payload)
