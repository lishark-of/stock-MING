from __future__ import annotations

from typing import Any

from server.services import factor_service
from worker.celery_app import task


@task("run_deepseek_factor_explanation")
def run_deepseek_factor_explanation(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return factor_service.create_factor_task("run_deepseek_factor_explanation", payload)
