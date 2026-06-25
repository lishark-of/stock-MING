from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import desktop_service


router = APIRouter(prefix="/api/desktop")


def _desktop_shell_preflight_envelope() -> dict:
    packet = desktop_service.read_desktop_shell_preflight_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.get("/preflight-cache")
def get_desktop_shell_preflight_cache() -> dict:
    return _desktop_shell_preflight_envelope()


@router.get("/preflight")
def get_desktop_shell_preflight_alias() -> dict:
    return _desktop_shell_preflight_envelope()


@router.post("/tauri-package-artifact-review")
def review_tauri_package_artifact(payload: dict[str, Any] | None = None) -> dict:
    task = desktop_service.run_tauri_package_artifact_review_task(payload)
    return task_envelope(task)


@router.post("/tauri-packaged-runtime-launch-review")
def review_tauri_packaged_runtime_launch(payload: dict[str, Any] | None = None) -> dict:
    task = desktop_service.run_tauri_packaged_runtime_launch_review_task(payload)
    return task_envelope(task)


@router.post("/tauri-backend-offline-packaged-ux-review")
def review_tauri_backend_offline_packaged_ux(payload: dict[str, Any] | None = None) -> dict:
    task = desktop_service.run_tauri_backend_offline_packaged_ux_review_task(payload)
    return task_envelope(task)


@router.post("/tauri-backend-startup-runtime-review")
def review_tauri_backend_startup_runtime(payload: dict[str, Any] | None = None) -> dict:
    task = desktop_service.run_tauri_backend_startup_runtime_review_task(payload)
    return task_envelope(task)


@router.post("/tauri-config-log-runtime-review")
def review_tauri_config_log_runtime(payload: dict[str, Any] | None = None) -> dict:
    task = desktop_service.run_tauri_config_log_runtime_review_task(payload)
    return task_envelope(task)


@router.post("/tauri-signing-notarization-review")
def review_tauri_signing_notarization(payload: dict[str, Any] | None = None) -> dict:
    task = desktop_service.run_tauri_signing_notarization_review_task(payload)
    return task_envelope(task)


@router.post("/tauri-production-package-promotion-review")
def review_tauri_production_package_promotion(payload: dict[str, Any] | None = None) -> dict:
    task = desktop_service.run_tauri_production_package_promotion_review_task(payload)
    return task_envelope(task)
