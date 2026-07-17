from __future__ import annotations

from copy import deepcopy
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


def cache_read_call_ledger(
    *,
    api: str,
    route: str,
    packet: dict[str, Any],
    existing: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Bind one truthful current GET row while leaving packet provenance untouched."""
    source_row = next(
        (
            deepcopy(row)
            for row in list(existing or [])
            if isinstance(row, dict) and row.get("api") == api
        ),
        {},
    )
    cache_missing = packet.get("status") == "cache_missing"
    try:
        observed_row_count = max(0, int(source_row.get("row_count", 1)))
    except (TypeError, ValueError):
        observed_row_count = 1
    source_row.update(
        {
            "api": api,
            "source": route,
            "route": route,
            "request_method": "GET",
            "row_count": 0 if cache_missing else observed_row_count,
            "call_status": "cache_missing" if cache_missing else "cache_read",
            "external": False,
            "external_calls_triggered": False,
            "external_call_count": 0,
            "provider_or_model_calls": False,
            "provider_called": False,
            "model_called": False,
            "worker_called": False,
            "worker_dispatched": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "qmt_called": False,
            "qmt_connection_count": 0,
            "qmt_external_connection_attempted": False,
            "qmt_process_discovered": False,
            "qmt_client_imported": False,
            "xtquant_imported": False,
            "trade_called": False,
            "trading_called": False,
            "broker_called": False,
            "broker_session_opened": False,
            "broker_session_count": 0,
            "account_query_executed": False,
            "order_called": False,
            "real_order_submitted": False,
            "real_order_count": 0,
            "real_order_cancelled": False,
            "real_trade_executed": False,
            "real_trade_count": 0,
            "real_holdings_modified": False,
            "real_trading_enabled": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_holdings": True,
            "contains_secret": False,
        }
    )
    return [source_row]


def cache_read_packet(
    packet: dict[str, Any],
    *,
    cache_call_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return an unaliased current-read view; nested historical evidence remains intact."""
    return {
        **packet,
        "cache_call_ledger": deepcopy(cache_call_ledger),
        "external": False,
        "external_calls_triggered": False,
        "provider_or_model_calls": False,
        "provider_called": False,
        "model_called": False,
        "worker_called": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "trade_called": False,
        "trading_called": False,
        "broker_called": False,
        "order_called": False,
        "real_trading_enabled": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


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
