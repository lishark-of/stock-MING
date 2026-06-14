from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import worker_service


router = APIRouter(prefix="/api/worker")


@router.get("/cache")
def get_worker_runtime_cache() -> dict:
    packet = worker_service.read_worker_runtime_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


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
