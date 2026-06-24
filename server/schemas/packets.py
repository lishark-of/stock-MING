from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiEnvelope(BaseModel):
    ok: bool = True
    data: Any = Field(default_factory=dict)
    error: Any | None = None
    call_ledger: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def envelope(
    data: Any = None,
    *,
    ok: bool = True,
    error: Any | None = None,
    call_ledger: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    model = ApiEnvelope(
        ok=ok,
        data={} if ok and data is None else data,
        error=error,
        call_ledger=list(call_ledger or []),
        warnings=list(warnings or []),
    )
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def cache_error(code: str, message: str, **details: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def cache_envelope(
    packet: dict[str, Any],
    *,
    route: str,
    missing_message: str,
    call_ledger: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    include_missing_data: bool = False,
) -> dict[str, Any]:
    ledger = list(call_ledger if call_ledger is not None else packet.get("call_ledger") or [])
    route_warnings = list(warnings if warnings is not None else packet.get("warnings") or [])
    if packet.get("status") == "cache_missing":
        return envelope(
            packet if include_missing_data else None,
            ok=False,
            error=cache_error(
                "cache_missing",
                missing_message,
                route=route,
                packet_key=packet.get("packet_key"),
                cache_source=packet.get("cache_source"),
            ),
            call_ledger=ledger,
            warnings=route_warnings,
        )
    return envelope(packet, call_ledger=ledger, warnings=route_warnings)
