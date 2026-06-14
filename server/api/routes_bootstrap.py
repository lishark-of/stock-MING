from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import bootstrap_service


router = APIRouter(prefix="/api/bootstrap")


@router.get("/status")
def get_bootstrap_status() -> dict:
    packet = bootstrap_service.read_bootstrap_status_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/live-startup")
def post_bootstrap_live_startup(payload: dict[str, Any] | None = None) -> dict:
    task = bootstrap_service.run_live_startup_task(payload)
    return task_envelope(task)


@router.post("/provider-model-acceptance-dry-run")
def post_bootstrap_provider_model_acceptance_dry_run(payload: dict[str, Any] | None = None) -> dict:
    task = bootstrap_service.run_provider_model_acceptance_dry_run(payload)
    return task_envelope(task)
