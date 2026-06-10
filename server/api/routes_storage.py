from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import storage_service


router = APIRouter(prefix="/api/storage")


@router.get("")
def get_storage_overview(limit: int = 20) -> dict:
    return envelope(storage_service.storage_overview(limit=limit))


@router.get("/factor-values")
def get_factor_values_status(limit: int = 100) -> dict:
    return envelope(storage_service.factor_values_status(limit=limit))


@router.get("/sqlite-meta")
def get_sqlite_meta_status(limit: int = 100) -> dict:
    return envelope(storage_service.sqlite_meta_status(limit=limit))


@router.get("/{dataset}")
def get_parquet_dataset_status(dataset: str, limit: int = 100) -> dict:
    return envelope(storage_service.parquet_dataset_status(dataset, limit=limit))
