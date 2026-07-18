from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.schemas.packets import cache_read_call_ledger, cache_read_packet, envelope
from server.services import worker_service


router = APIRouter(prefix="/api/worker")


@router.get("/cache")
def get_worker_runtime_cache() -> dict:
    packet = worker_service.read_worker_runtime_cache()
    current_ledger = cache_read_call_ledger(
        api="local_worker_runtime_cache",
        route="GET /api/worker/cache",
        packet=packet,
        existing=packet.get("cache_call_ledger") or packet.get("call_ledger"),
    )
    response_packet = cache_read_packet(packet, cache_call_ledger=current_ledger)
    return envelope(response_packet, call_ledger=current_ledger, warnings=packet.get("warnings"))


@router.post("/synthetic-healthcheck")
def run_worker_synthetic_healthcheck(payload: dict[str, Any] | None = None) -> dict:
    packet = worker_service.run_worker_synthetic_healthcheck(payload or {})
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/activation-review")
def run_worker_activation_review(payload: dict[str, Any] | None = None) -> dict:
    packet = worker_service.run_worker_activation_review(payload or {})
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/production-evidence-plan")
def run_worker_production_evidence_plan(payload: dict[str, Any] | None = None) -> dict:
    packet = worker_service.run_worker_production_evidence_plan(payload or {})
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/runtime-qa-execution-request")
def run_worker_runtime_qa_execution_request(payload: dict[str, Any] | None = None) -> dict:
    packet = worker_service.run_worker_runtime_qa_execution_request(payload or {})
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/runtime-qa-dry-run")
def run_worker_runtime_qa_dry_run(payload: dict[str, Any] | None = None) -> dict:
    packet = worker_service.run_worker_runtime_qa_dry_run(payload or {})
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/runtime-qa-execution")
def run_worker_runtime_qa_execution(payload: dict[str, Any] | None = None) -> dict:
    packet = worker_service.run_worker_runtime_qa_execution(payload or {})
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/production-promotion-review")
def run_worker_production_promotion_review(payload: dict[str, Any] | None = None) -> dict:
    packet = worker_service.run_worker_production_promotion_review(payload or {})
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/full-market-production-acceptance")
def run_full_market_production_acceptance(payload: dict[str, Any] | None = None) -> dict:
    from server.services import full_market_worker_service

    local_packet = full_market_worker_service.run_full_market_worker_production_acceptance(
        payload or {}
    )
    packet = full_market_worker_service.public_full_market_worker_acceptance_response(
        local_packet
    )
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/full-market-factor-radar-map-reduce-request")
def run_full_market_factor_radar_map_reduce_request(
    payload: dict[str, Any] | None = None,
) -> dict:
    from server.services import full_market_research_producer_service

    task = full_market_research_producer_service.run_full_market_factor_radar_map_reduce_request(
        payload or {}
    )
    return envelope(task, call_ledger=task.get("call_ledger"), warnings=task.get("warnings"))


@router.post("/full-market-factor-execution")
def run_full_market_factor_execution(
    payload: dict[str, Any] | None = None,
) -> dict:
    from server.services import full_market_research_producer_service

    packet = full_market_research_producer_service.execute_full_market_factor_research(
        payload or {}
    )
    return envelope(
        packet,
        call_ledger=packet.get("call_ledger"),
        warnings=packet.get("warnings"),
    )


@router.post("/candidate-radar-authoritative-cache-publish")
def publish_candidate_radar_authoritative_cache(
    payload: dict[str, Any] | None = None,
) -> dict:
    from server.services import full_market_worker_service

    packet = full_market_worker_service.publish_candidate_radar_authoritative_cache(
        payload or {}
    )
    return envelope(
        packet,
        call_ledger=packet.get("call_ledger"),
        warnings=packet.get("warnings"),
    )
