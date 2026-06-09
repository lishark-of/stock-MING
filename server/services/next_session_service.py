from __future__ import annotations

from typing import Any

from . import packet_service
from .task_service import create_task_stub


def read_next_session_cache() -> dict[str, Any]:
    return packet_service.build_next_session_cache()


def create_next_session_task(payload: Any = None) -> dict[str, Any]:
    return create_task_stub(
        "build_next_session_projection",
        output_packet_key="command_center_next_session_projection_packet",
        payload=payload,
        current_step="next_session_projection_task_stub_created",
    )
