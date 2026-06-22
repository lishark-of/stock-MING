from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import legacy_service


router = APIRouter(prefix="/api/legacy")


@router.get("/cache")
def get_legacy_bridge_cache() -> dict:
    packet = legacy_service.read_legacy_bridge_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/audit-observation-dry-run")
def run_legacy_audit_observation_dry_run(payload: dict[str, Any] | None = None) -> dict:
    task = legacy_service.run_legacy_audit_observation_dry_run_task(payload)
    return task_envelope(task)


@router.post("/ordinary-workflow-parity-review")
def review_streamlit_ordinary_workflow_parity(payload: dict[str, Any] | None = None) -> dict:
    task = legacy_service.run_streamlit_ordinary_workflow_parity_review_task(payload)
    return task_envelope(task)


@router.post("/fallback-retirement-review")
def review_streamlit_fallback_retirement(payload: dict[str, Any] | None = None) -> dict:
    task = legacy_service.run_streamlit_fallback_retirement_review_task(payload)
    return task_envelope(task)
