from __future__ import annotations

from typing import Any

from . import packet_service
from .task_service import create_task_stub


def read_factor_quant_cache() -> dict[str, Any]:
    return packet_service.build_factor_quant_cache()


def create_factor_task(task_type: str, payload: Any = None) -> dict[str, Any]:
    return create_task_stub(
        task_type,
        output_packet_key="command_center_factor_quant_hub_packet",
        payload=payload,
        current_step="factor_quant_task_stub_created",
    )
