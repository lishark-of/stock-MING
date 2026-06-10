from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import envelope
from server.services import factor_service


router = APIRouter(prefix="/api/factor-quant")


@router.get("/cache")
def get_factor_quant_cache() -> dict:
    packet = factor_service.read_factor_quant_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.post("/refresh-data")
def refresh_factor_data(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("refresh_factor_data", payload)
    return task_envelope(task)


@router.post("/run-light")
def run_factor_light(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_factor_light", payload)
    return task_envelope(task)


@router.post("/deepseek-explain")
def explain_factor_with_deepseek(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_deepseek_factor_explanation", payload)
    return task_envelope(task)
