from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import migration_status_service


router = APIRouter(prefix="/api/migration")


@router.get("/status")
def get_migration_status() -> dict:
    packet = migration_status_service.build_migration_status()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/tushare-deepseek-linkage-review")
def post_tushare_deepseek_linkage_review(payload: dict[str, Any] | None = None) -> dict:
    task = migration_status_service.run_tushare_deepseek_linkage_review(payload)
    return task_envelope(task)
