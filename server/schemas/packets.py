from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiEnvelope(BaseModel):
    ok: bool = True
    data: Any = Field(default_factory=dict)
    error: str | None = None
    call_ledger: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def envelope(
    data: Any = None,
    *,
    ok: bool = True,
    error: str | None = None,
    call_ledger: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    model = ApiEnvelope(
        ok=ok,
        data={} if data is None else data,
        error=error,
        call_ledger=list(call_ledger or []),
        warnings=list(warnings or []),
    )
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()
