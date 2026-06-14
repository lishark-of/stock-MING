from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import audit_service


router = APIRouter(prefix="/api/audit")


@router.get("/cache")
def get_call_ledger_audit_cache() -> dict:
    packet = audit_service.read_call_ledger_audit_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/motion-browser-qa-review")
def review_motion_browser_qa(payload: dict | None = None) -> dict:
    task = audit_service.run_motion_browser_qa_review_task(payload)
    return envelope({"task_id": task["task_id"], "task": task}, call_ledger=task.get("call_ledger"), warnings=task.get("warnings"))

@router.post("/motion-production-promotion-dry-run")
def create_motion_production_promotion_dry_run(payload: dict | None = None) -> dict:
    task = audit_service.run_motion_production_promotion_dry_run_task(payload)
    return envelope({"task_id": task["task_id"], "task": task}, call_ledger=task.get("call_ledger"), warnings=task.get("warnings"))
