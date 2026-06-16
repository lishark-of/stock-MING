from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import desktop_service


router = APIRouter(prefix="/api/desktop")


@router.get("/preflight-cache")
def get_desktop_shell_preflight_cache() -> dict:
    packet = desktop_service.read_desktop_shell_preflight_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


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
