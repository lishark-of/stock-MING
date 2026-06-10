from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import storage_service


router = APIRouter(prefix="/api/storage")


@router.get("")
def get_storage_overview(limit: int = 20) -> dict:
    packet = storage_service.storage_overview(limit=limit)
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.get("/factor-values")
def get_factor_values_status(limit: int = 100) -> dict:
    packet = storage_service.factor_values_status(limit=limit)
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.get("/sqlite-meta")
def get_sqlite_meta_status(limit: int = 100) -> dict:
    packet = storage_service.sqlite_meta_status(limit=limit)
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.get("/{dataset}")
def get_parquet_dataset_status(dataset: str, limit: int = 100) -> dict:
    packet = storage_service.parquet_dataset_status(dataset, limit=limit)
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
