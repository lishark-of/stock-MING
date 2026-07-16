from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import cache_read_call_ledger, cache_read_packet, envelope
from server.services import desktop_service


router = APIRouter(prefix="/api/desktop")


def _desktop_shell_preflight_envelope(route: str) -> dict:
    packet = desktop_service.read_desktop_shell_preflight_cache()
    current_ledger = cache_read_call_ledger(
        api="local_desktop_shell_preflight_cache",
        route=route,
        packet=packet,
        existing=packet.get("cache_call_ledger") or packet.get("call_ledger"),
    )
    response_packet = cache_read_packet(packet, cache_call_ledger=current_ledger)
    return envelope(response_packet, call_ledger=current_ledger, warnings=packet.get("warnings"))


@router.get("/preflight-cache")
def get_desktop_shell_preflight_cache() -> dict:
    return _desktop_shell_preflight_envelope("GET /api/desktop/preflight-cache")


@router.get("/preflight")
def get_desktop_shell_preflight_alias() -> dict:
    return _desktop_shell_preflight_envelope("GET /api/desktop/preflight")


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
