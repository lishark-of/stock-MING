from __future__ import annotations

from typing import Any

from server.schemas.packets import envelope


def task_envelope(task: dict[str, Any]) -> dict[str, Any]:
    return envelope(
        {"task_id": task["task_id"], "task": task},
        call_ledger=task.get("call_ledger"),
        warnings=task.get("warnings"),
    )
