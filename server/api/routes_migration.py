from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import migration_status_service


router = APIRouter(prefix="/api/migration")


@router.get("/status")
def get_migration_status() -> dict:
    return envelope(migration_status_service.build_migration_status())
