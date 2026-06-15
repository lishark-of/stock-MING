from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import data_health_service


router = APIRouter(prefix="/api/data-health")


@router.get("/cache")
def get_data_health_timeline_cache() -> dict:
    packet = data_health_service.read_data_health_timeline_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/trade-cal-provider-acceptance-dry-run")
def post_trade_cal_provider_acceptance_dry_run(payload: dict[str, Any] | None = None) -> dict:
    task = data_health_service.run_trade_cal_provider_acceptance_dry_run(payload)
    return task_envelope(task)


@router.post("/trade-cal-provider-acceptance-execution-request")
def post_trade_cal_provider_acceptance_execution_request(payload: dict[str, Any] | None = None) -> dict:
    task = data_health_service.run_trade_cal_provider_acceptance_execution_request(payload)
    return task_envelope(task)


@router.post("/producer-cache-refresh-execution-request")
def post_producer_cache_refresh_execution_request(payload: dict[str, Any] | None = None) -> dict:
    task = data_health_service.run_producer_cache_refresh_execution_request(payload)
    return task_envelope(task)


@router.post("/producer-cache-refresh")
def post_producer_cache_refresh(payload: dict[str, Any] | None = None) -> dict:
    task = data_health_service.run_producer_cache_refresh(payload)
    return task_envelope(task)
