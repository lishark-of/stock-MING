from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import storage_service


router = APIRouter(prefix="/api/storage")


@router.get("")
def get_storage_overview(limit: int = 20) -> dict:
    packet = storage_service.storage_overview(limit=limit)
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.get("/factor-values")
def get_factor_values_status(
    limit: int = 100,
    cursor: str | None = None,
    ts_code: str | None = None,
    trade_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    packet = storage_service.factor_values_status(
        limit=limit,
        cursor=cursor,
        ts_code=ts_code,
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
    )
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.get("/sqlite-meta")
def get_sqlite_meta_status(limit: int = 100) -> dict:
    packet = storage_service.sqlite_meta_status(limit=limit)
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.get("/catalog")
def get_storage_dataset_catalog() -> dict:
    packet = storage_service.storage_dataset_catalog()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/artifact-hygiene/dry-run")
def run_storage_artifact_cleanup_dry_run(payload: dict[str, Any] | None = None) -> dict:
    task = storage_service.run_storage_artifact_cleanup_dry_run_task(payload)
    return task_envelope(task)


@router.post("/schema-validation/dry-run")
def run_storage_schema_validation_dry_run(payload: dict[str, Any] | None = None) -> dict:
    task = storage_service.run_storage_schema_validation_dry_run_task(payload)
    return task_envelope(task)


@router.post("/schema-validation/acceptance")
def run_storage_schema_validation_acceptance(payload: dict[str, Any] | None = None) -> dict:
    task = storage_service.run_storage_schema_validation_acceptance_task(payload)
    return task_envelope(task)


@router.post("/dataset-version-manifest/dry-run")
def run_storage_dataset_version_manifest_dry_run(payload: dict[str, Any] | None = None) -> dict:
    task = storage_service.run_storage_dataset_version_manifest_dry_run_task(payload)
    return task_envelope(task)


@router.post("/dataset-version-manifest/review")
def run_storage_dataset_version_manifest_review(payload: dict[str, Any] | None = None) -> dict:
    task = storage_service.run_storage_dataset_version_manifest_review_task(payload)
    return task_envelope(task)


@router.post("/dataset-version-manifest/write")
def run_storage_dataset_version_manifest_write(payload: dict[str, Any] | None = None) -> dict:
    task = storage_service.run_storage_dataset_version_manifest_write_task(payload)
    return task_envelope(task)


@router.post("/dataset-version-manifest/validate")
def run_storage_dataset_version_manifest_validate(payload: dict[str, Any] | None = None) -> dict:
    task = storage_service.run_storage_dataset_version_manifest_validate_task(payload)
    return task_envelope(task)


@router.post("/partition-migration/dry-run")
def run_storage_partition_migration_dry_run(payload: dict[str, Any] | None = None) -> dict:
    task = storage_service.run_storage_partition_migration_dry_run_task(payload)
    return task_envelope(task)


@router.post("/compaction/dry-run")
def run_storage_compaction_dry_run(payload: dict[str, Any] | None = None) -> dict:
    task = storage_service.run_storage_compaction_dry_run_task(payload)
    return task_envelope(task)


@router.post("/cache-ttl/dry-run")
def run_storage_cache_ttl_dry_run(payload: dict[str, Any] | None = None) -> dict:
    task = storage_service.run_storage_cache_ttl_dry_run_task(payload)
    return task_envelope(task)


@router.get("/{dataset}")
def get_parquet_dataset_status(
    dataset: str,
    limit: int = 100,
    cursor: str | None = None,
    ts_code: str | None = None,
    trade_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    packet = storage_service.parquet_dataset_status(
        dataset,
        limit=limit,
        cursor=cursor,
        ts_code=ts_code,
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
    )
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))
