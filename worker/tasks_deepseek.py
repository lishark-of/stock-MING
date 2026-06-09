from __future__ import annotations

from typing import Any

from server.services.task_service import create_task_stub
from worker.celery_app import task


@task("run_deepseek_factor_explanation")
def run_deepseek_factor_explanation(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    task_record = create_task_stub(
        "run_deepseek_factor_explanation",
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=payload,
    )
    task_record["warnings"].append("DeepSeek 任务骨架未调用模型；后续只允许按钮触发解释，不覆盖数值。")
    return task_record
