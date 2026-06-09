from __future__ import annotations

from typing import Any

from server.services.task_service import create_task_stub
from worker.celery_app import task


@task("refresh_tushare_facts")
def refresh_tushare_facts(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return create_task_stub("refresh_tushare_facts", output_packet_key="a_share_fact_lineage_summary", payload=payload)
