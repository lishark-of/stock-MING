from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import candidate_service


router = APIRouter(prefix="/api/candidate-radar")


@router.get("/cache")
def get_candidate_radar_cache() -> dict:
    packet = candidate_service.read_candidate_radar_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/scan-quick")
def scan_candidate_radar_quick(payload: dict[str, Any] | None = None) -> dict:
    task = candidate_service.run_candidate_quick_scan_task(payload)
    return task_envelope(task)


@router.post("/quant-projection")
def project_candidate_radar_quant(payload: dict[str, Any] | None = None) -> dict:
    task = candidate_service.run_candidate_quant_projection_task(payload)
    return task_envelope(task)


@router.post("/quant-projection-acceptance-dry-run")
def dry_run_candidate_radar_quant_acceptance(payload: dict[str, Any] | None = None) -> dict:
    task = candidate_service.run_candidate_quant_projection_acceptance_dry_run_task(payload)
    return task_envelope(task)


@router.post("/provider-parity-dry-run")
def dry_run_candidate_radar_provider_parity(payload: dict[str, Any] | None = None) -> dict:
    task = candidate_service.run_candidate_provider_parity_dry_run_task(payload)
    return task_envelope(task)


@router.post("/worker-execution-request")
def request_candidate_radar_worker_execution(payload: dict[str, Any] | None = None) -> dict:
    task = candidate_service.run_candidate_worker_execution_request_task(payload)
    return task_envelope(task)


@router.post("/full-pool-plan")
def plan_candidate_radar_full_pool(payload: dict[str, Any] | None = None) -> dict:
    task = candidate_service.run_candidate_full_pool_plan_task(payload)
    return task_envelope(task)


@router.post("/full-pool-local-scan")
def scan_candidate_radar_full_pool_local(payload: dict[str, Any] | None = None) -> dict:
    task = candidate_service.run_candidate_full_pool_local_scan_task(payload)
    return task_envelope(task)


@router.post("/deep-scan-plan")
def plan_candidate_radar_deep_scan(payload: dict[str, Any] | None = None) -> dict:
    task = candidate_service.run_candidate_deep_scan_plan_task(payload)
    return task_envelope(task)


@router.post("/deep-scan-local-review")
def review_candidate_radar_deep_scan_local(payload: dict[str, Any] | None = None) -> dict:
    task = candidate_service.run_candidate_deep_scan_local_review_task(payload)
    return task_envelope(task)


@router.post("/browser-qa-review")
def review_candidate_radar_browser_qa(payload: dict[str, Any] | None = None) -> dict:
    task = candidate_service.run_candidate_browser_qa_review_task(payload)
    return task_envelope(task)
