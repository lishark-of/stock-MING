from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import storage_service


router = APIRouter(prefix="/api/storage")


@router.get("/factor-values")
def get_factor_values_status(limit: int = 100) -> dict:
    return envelope(storage_service.factor_values_status(limit=limit))
