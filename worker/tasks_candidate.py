from __future__ import annotations

import os
from typing import Any

from server.services import candidate_service
from server.services.task_service import create_task_stub
from worker.celery_app import task


@task("run_candidate_radar_full_pool_plan")
def run_candidate_radar_full_pool_plan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return create_task_stub("run_candidate_radar_full_pool_plan", output_packet_key="command_center_3_candidate_radar_cache", payload=payload)


@task("run_candidate_radar_full_pool_local_scan", bind=True)
def run_candidate_radar_full_pool_local_scan(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, dict) else {}
    if payload_map.get("full_market_worker_acceptance") is True:
        from server.services import full_market_worker_service

        delivery_info = self.request.delivery_info if isinstance(self.request.delivery_info, dict) else {}
        runtime = {
            "celery_request_id": str(self.request.id or ""),
            "worker_hostname": str(getattr(self.request, "hostname", "") or ""),
            "worker_pid": os.getpid(),
            "worker_queue": str(delivery_info.get("routing_key") or ""),
            "delivery_redelivered": delivery_info.get("redelivered") is True,
            "bound_task_request": True,
            "synthetic_fixture": False,
        }
        return full_market_worker_service.execute_candidate_radar_batch_worker(
            payload_map,
            runtime=runtime,
        )
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
