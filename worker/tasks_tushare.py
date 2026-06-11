from __future__ import annotations

from typing import Any

from server.services.tushare_task_service import run_tushare_refresh_task
from worker.celery_app import task


@task("refresh_tushare_facts")
def refresh_tushare_facts(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_tushare_refresh_task(payload)
