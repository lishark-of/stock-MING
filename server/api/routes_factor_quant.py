from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.schemas.packets import envelope
from server.services import factor_service


router = APIRouter(prefix="/api/factor-quant")


@router.get("/cache")
def get_factor_quant_cache() -> dict:
    return envelope(factor_service.read_factor_quant_cache())


@router.post("/refresh-data")
def refresh_factor_data(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("refresh_factor_data", payload)
    return envelope({"task_id": task["task_id"], "task": task})


@router.post("/run-light")
def run_factor_light(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_factor_light", payload)
    return envelope({"task_id": task["task_id"], "task": task})


@router.post("/deepseek-explain")
def explain_factor_with_deepseek(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_deepseek_factor_explanation", payload)
    task["warnings"].append("DeepSeek 解释任务当前为 stub；不会生成或覆盖数值。")
    return envelope({"task_id": task["task_id"], "task": task})
