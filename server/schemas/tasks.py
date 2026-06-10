from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TaskStatus = Literal["pending", "running", "success", "failed", "cancelled"]


class TaskRecord(BaseModel):
    task_id: str
    task_type: str
    status: TaskStatus = "pending"
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    progress: float = 0.0
    current_step: str = "queued"
    error_message_safe: str = ""
    output_packet_key: str = ""
    payload_safe: dict[str, Any] = Field(default_factory=dict)
    call_ledger: list[dict[str, Any]] = Field(default_factory=list)
    backend: str = "local_fallback"
    external_calls_triggered: bool = False
    deepseek_called: bool = False
    tushare_called: bool = False
    github_called: bool = False
    does_not_execute_trades: bool = True
    does_not_modify_strategy_action: bool = True
    status_history: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
