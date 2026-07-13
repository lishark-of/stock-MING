"""Caller-supplied QMT export compatibility and deterministic local replay.

This module deliberately has no QMT, broker, network, process, credential, or
real-order integration.  The only executable path reduces caller-supplied,
sanitized JSON with ``Decimal`` arithmetic and persists local evidence after an
explicit POST.  Cache reads use SQLite read-only mode and never initialize the
database.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore

from . import task_service


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
CACHE_PACKET_KEY = "command_center_3_qmt_replay_cache"
CURRENT_PACKET_KEY = "command_center_3_qmt_replay_current"
LAST_GOOD_PACKET_KEY = "command_center_3_qmt_replay_last_good"
REQUEST_SCHEMA_VERSION = "qmt_readonly_local_replay_request.v1"
RESULT_SCHEMA_VERSION = "qmt_readonly_local_replay_result.v1"
CACHE_SCHEMA_VERSION = "qmt_readonly_local_replay_cache.v1"
TASK_TYPE = "run_qmt_readonly_local_replay"

ALLOWED_SCENARIOS = {"baseline", "stress", "recovery"}
ALLOWED_MAX_FRAMES = {12, 24, 48}
ALLOWED_EVENT_TYPES = {"market_mark", "virtual_intent"}
ALLOWED_SIDES = {"BUY", "SELL"}
SYMBOL_PATTERN = re.compile(r"^[0-9]{6}\.(SH|SZ|BJ)$")
SOURCE_HASH_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
SOURCE_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,120}$")
SOURCE_TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
MONEY_QUANTUM = Decimal("0.01")
PRICE_QUANTUM = Decimal("0.0001")
BPS_DENOMINATOR = Decimal("10000")
MAX_POSITIONS = 20

_FORBIDDEN_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "credential",
    "authorization",
    "session",
    "broker",
)
_FORBIDDEN_EXACT_KEYS = {
    "account",
    "account_id",
    "accountid",
    "api_key",
    "apikey",
    "order_id",
    "order_ref",
    "order_sysid",
    "cancel_order",
    "qmt_path",
    "install_path",
}


class ReplayValidationError(ValueError):
    """Safe validation failure whose message is an allowlisted error code."""


def _now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _boundary_flags() -> dict[str, Any]:
    return {
        "external_calls_triggered": False,
        "external_call_count": 0,
        "qmt_called": False,
        "qmt_connection_count": 0,
        "qmt_external_connection_attempted": False,
        "qmt_process_discovered": False,
        "qmt_client_imported": False,
        "xtquant_imported": False,
        "broker_called": False,
        "broker_session_opened": False,
        "broker_session_count": 0,
        "account_query_executed": False,
        "real_order_submitted": False,
        "real_order_count": 0,
        "real_order_cancelled": False,
        "real_trade_executed": False,
        "real_trade_count": 0,
        "real_holdings_modified": False,
        "real_trading_enabled": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "worker_dispatched": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
    }


def _local_call_ledger(
    *,
    call_status: str,
    row_count: int = 0,
    scope_hash: str = "",
    task_id: str = "",
    error_message_safe: str = "",
) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_qmt_readonly_decimal_replay",
            "source": "caller_supplied_sanitized_export_or_bound_local_lineage",
            "request_params_safe": {
                "scope_hash": scope_hash,
                "caller_supplied_export_only": True,
                "external_qmt_connection_allowed": False,
            },
            "row_count": int(row_count),
            "task_id": task_id,
            "local_fetched_at": _now_iso(),
            "call_status": call_status,
            "error_message_safe": error_message_safe,
            "external": False,
            **_boundary_flags(),
        }
    ]


def _scan_forbidden_keys(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key or "").strip().lower()
            if key in _FORBIDDEN_EXACT_KEYS or any(part in key for part in _FORBIDDEN_KEY_PARTS):
                raise ReplayValidationError("forbidden_sensitive_or_connection_field")
            _scan_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_forbidden_keys(child, path=f"{path}[{index}]")


def _required_text(value: Any, *, code: str, limit: int = 160) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit:
        raise ReplayValidationError(code)
    return text


def _decimal(value: Any, *, code: str, minimum: Decimal = Decimal("0")) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ReplayValidationError(code)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ReplayValidationError(code) from None
    if not parsed.is_finite() or parsed < minimum:
        raise ReplayValidationError(code)
    return parsed


def _integer(value: Any, *, code: str, minimum: int = 0) -> int:
    parsed = _decimal(value, code=code, minimum=Decimal(minimum))
    if parsed != parsed.to_integral_value():
        raise ReplayValidationError(code)
    result = int(parsed)
    if result < minimum:
        raise ReplayValidationError(code)
    return result


def _money(value: Decimal) -> str:
    return format(value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP), "f")


def _price(value: Decimal) -> str:
    return format(value.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP), "f")


def _normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise ReplayValidationError("invalid_a_share_symbol")
    return symbol


def _normalize_as_of(value: Any) -> str:
    text = _required_text(value, code="snapshot_as_of_required", limit=80)
    try:
        parsed = _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ReplayValidationError("invalid_snapshot_as_of") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReplayValidationError("snapshot_as_of_timezone_required")
    return parsed.isoformat(timespec="seconds")


def _normalize_positions(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_POSITIONS:
        raise ReplayValidationError("invalid_position_count")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ReplayValidationError("invalid_position_row")
        symbol = _normalize_symbol(raw.get("symbol"))
        if symbol in seen:
            raise ReplayValidationError("duplicate_position_symbol")
        seen.add(symbol)
        quantity = _integer(raw.get("quantity"), code="invalid_position_quantity")
        available = _integer(
            raw.get("available_quantity", quantity),
            code="invalid_available_quantity",
        )
        if available > quantity:
            raise ReplayValidationError("available_quantity_exceeds_quantity")
        average_cost = _decimal(raw.get("average_cost", "0"), code="invalid_average_cost")
        rows.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "available_quantity": available,
                "average_cost": _price(average_cost),
            }
        )
    return sorted(rows, key=lambda row: row["symbol"])


def _normalize_events(value: Any, *, max_frames: int, snapshot_present: bool) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not snapshot_present:
        raise ReplayValidationError("events_require_sanitized_snapshot")
    if not isinstance(value, list) or len(value) > max_frames:
        raise ReplayValidationError("invalid_event_count")
    rows: list[dict[str, Any]] = []
    for expected_seq, raw in enumerate(value, start=1):
        if not isinstance(raw, Mapping):
            raise ReplayValidationError("invalid_event_row")
        seq = _integer(raw.get("seq"), code="invalid_event_seq", minimum=1)
        if seq != expected_seq:
            raise ReplayValidationError("event_seq_must_be_contiguous_from_one")
        event_type = str(raw.get("event_type") or "").strip().lower()
        if event_type not in ALLOWED_EVENT_TYPES:
            raise ReplayValidationError("unsupported_event_type")
        symbol = _normalize_symbol(raw.get("symbol"))
        if event_type == "market_mark":
            price = _decimal(raw.get("price"), code="invalid_market_mark_price", minimum=Decimal("0.0001"))
            rows.append(
                {
                    "seq": seq,
                    "event_type": event_type,
                    "symbol": symbol,
                    "price": _price(price),
                }
            )
            continue
        side = str(raw.get("side") or "").strip().upper()
        if side not in ALLOWED_SIDES:
            raise ReplayValidationError("invalid_virtual_intent_side")
        quantity = _integer(raw.get("quantity"), code="invalid_virtual_intent_quantity", minimum=1)
        limit_price = _decimal(
            raw.get("limit_price"),
            code="invalid_virtual_intent_limit_price",
            minimum=Decimal("0.0001"),
        )
        rows.append(
            {
                "seq": seq,
                "event_type": event_type,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "limit_price": _price(limit_price),
            }
        )
    return rows


def _normalize_request(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReplayValidationError("payload_must_be_object")
    _scan_forbidden_keys(payload)
    if payload.get("approved_by_user") is not True:
        raise ReplayValidationError("approved_by_user_required")
    mode = str(payload.get("mode") or "").strip()
    if mode != "local_research_replay":
        raise ReplayValidationError("local_research_replay_mode_required")
    scenario = str(payload.get("scenario") or "").strip().lower()
    if scenario not in ALLOWED_SCENARIOS:
        raise ReplayValidationError("invalid_replay_scenario")
    max_frames = _integer(payload.get("max_frames"), code="invalid_max_frames", minimum=1)
    if max_frames not in ALLOWED_MAX_FRAMES:
        raise ReplayValidationError("invalid_max_frames")
    source_result_version = _required_text(
        payload.get("source_result_version"),
        code="source_result_version_required",
        limit=120,
    )
    if not SOURCE_VERSION_PATTERN.fullmatch(source_result_version):
        raise ReplayValidationError("invalid_source_result_version")
    source_scope_hash = _required_text(
        payload.get("source_scope_hash"),
        code="source_scope_hash_required",
        limit=128,
    )
    if not SOURCE_HASH_PATTERN.fullmatch(source_scope_hash):
        raise ReplayValidationError("invalid_source_scope_hash")
    source_symbol = None
    if payload.get("source_symbol") not in (None, ""):
        source_symbol = _normalize_symbol(payload.get("source_symbol"))
    source_task_id = str(payload.get("source_task_id") or "").strip()
    if source_task_id and not SOURCE_TASK_ID_PATTERN.fullmatch(source_task_id):
        raise ReplayValidationError("invalid_source_task_id")

    snapshot_raw = payload.get("snapshot")
    snapshot_present = snapshot_raw is not None
    snapshot: dict[str, Any] | None = None
    if snapshot_present:
        if not isinstance(snapshot_raw, Mapping):
            raise ReplayValidationError("snapshot_must_be_object")
        snapshot = {
            "as_of": _normalize_as_of(snapshot_raw.get("as_of")),
            "cash": _money(_decimal(snapshot_raw.get("cash"), code="invalid_snapshot_cash")),
            "positions": _normalize_positions(snapshot_raw.get("positions")),
        }
    events = _normalize_events(payload.get("events"), max_frames=max_frames, snapshot_present=snapshot_present)

    simulation_raw = payload.get("simulation") or {}
    if not isinstance(simulation_raw, Mapping):
        raise ReplayValidationError("simulation_must_be_object")
    fee_bps = _decimal(simulation_raw.get("fee_bps", "5"), code="invalid_fee_bps")
    slippage_bps = _decimal(simulation_raw.get("slippage_bps", "10"), code="invalid_slippage_bps")
    if fee_bps > Decimal("100") or slippage_bps > Decimal("100"):
        raise ReplayValidationError("simulation_bps_out_of_bounds")
    buy_lot_size = _integer(simulation_raw.get("buy_lot_size", 100), code="invalid_buy_lot_size", minimum=1)
    if buy_lot_size != 100:
        raise ReplayValidationError("buy_lot_size_must_be_100")

    return {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "approved_by_user": True,
        "mode": mode,
        "scenario": scenario,
        "max_frames": max_frames,
        "source_result_version": source_result_version,
        "source_scope_hash": source_scope_hash,
        "source_symbol": source_symbol,
        "source_task_id": source_task_id or None,
        "snapshot": snapshot,
        "events": events,
        "simulation": {
            "fee_bps": _price(fee_bps),
            "slippage_bps": _price(slippage_bps),
            "buy_lot_size": buy_lot_size,
        },
    }


def _reject_event(event: Mapping[str, Any], *, reason: str) -> tuple[dict[str, Any], dict[str, Any]]:
    ledger = {
        "seq": event.get("seq"),
        "event_type": event.get("event_type"),
        "symbol": event.get("symbol"),
        "status": "excluded",
        "reason": reason,
        "virtual_fill_created": False,
        "real_order_submitted": False,
        "real_trade_executed": False,
    }
    research = {
        "seq": event.get("seq"),
        "event": "excluded",
        "symbol": event.get("symbol"),
        "reason": reason,
    }
    return ledger, research


def _decimal_replay(normalized: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = normalized.get("snapshot")
    events = list(normalized.get("events") or [])
    if not isinstance(snapshot, Mapping):
        event = "watch" if normalized.get("scenario") == "stress" else "observe"
        return {
            "source_mode": "bound_local_lineage_reference_no_export_rows",
            "initial_cash": "0.00",
            "final_cash": "0.00",
            "initial_position_count": 0,
            "final_positions": [],
            "event_count": 0,
            "event_ledger": [],
            "research_events": [
                {
                    "seq": 0,
                    "event": event,
                    "symbol": None,
                    "reason": "source_scope_bound_but_no_caller_supplied_export_events",
                }
            ],
            "virtual_fills": [],
            "virtual_fill_count": 0,
            "accepted_virtual_intent_count": 0,
            "excluded_virtual_intent_count": 0,
        }

    cash = Decimal(str(snapshot.get("cash") or "0"))
    positions: dict[str, dict[str, Any]] = {
        str(row["symbol"]): {
            "quantity": int(row["quantity"]),
            "available_quantity": int(row["available_quantity"]),
            "average_cost": Decimal(str(row["average_cost"])),
        }
        for row in snapshot.get("positions") or []
    }
    marks: dict[str, Decimal] = {}
    ledger: list[dict[str, Any]] = []
    research_events: list[dict[str, Any]] = []
    virtual_fills: list[dict[str, Any]] = []
    accepted = 0
    excluded = 0
    fee_bps = Decimal(str((normalized.get("simulation") or {}).get("fee_bps") or "0"))
    slippage_bps = Decimal(str((normalized.get("simulation") or {}).get("slippage_bps") or "0"))
    lot_size = int((normalized.get("simulation") or {}).get("buy_lot_size") or 100)

    for event in events:
        seq = int(event["seq"])
        symbol = str(event["symbol"])
        if event["event_type"] == "market_mark":
            mark = Decimal(str(event["price"]))
            marks[symbol] = mark
            ledger.append(
                {
                    "seq": seq,
                    "event_type": "market_mark",
                    "symbol": symbol,
                    "status": "observed",
                    "mark_price": _price(mark),
                    "virtual_fill_created": False,
                    "real_order_submitted": False,
                    "real_trade_executed": False,
                }
            )
            research_events.append(
                {"seq": seq, "event": "observe", "symbol": symbol, "reason": "market_mark_replayed_locally"}
            )
            continue

        side = str(event["side"])
        quantity = int(event["quantity"])
        limit_price = Decimal(str(event["limit_price"]))
        mark = marks.get(symbol)
        if mark is None:
            rejected, research = _reject_event(event, reason="market_mark_required_before_virtual_intent")
            ledger.append(rejected)
            research_events.append(research)
            excluded += 1
            continue
        if side == "BUY" and quantity % lot_size:
            rejected, research = _reject_event(event, reason="buy_quantity_must_use_100_share_lot")
            ledger.append(rejected)
            research_events.append(research)
            excluded += 1
            continue

        slip_multiplier = Decimal("1") + (slippage_bps / BPS_DENOMINATOR)
        if side == "SELL":
            slip_multiplier = Decimal("1") - (slippage_bps / BPS_DENOMINATOR)
        virtual_price = (mark * slip_multiplier).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)
        limit_crossed = virtual_price <= limit_price if side == "BUY" else virtual_price >= limit_price
        if not limit_crossed:
            rejected, research = _reject_event(event, reason="virtual_limit_not_crossed")
            ledger.append(rejected)
            research_events.append(research)
            excluded += 1
            continue

        notional = (virtual_price * Decimal(quantity)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        fee = (notional * fee_bps / BPS_DENOMINATOR).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        position = positions.setdefault(
            symbol,
            {"quantity": 0, "available_quantity": 0, "average_cost": Decimal("0")},
        )
        if side == "BUY":
            debit = notional + fee
            if debit > cash:
                rejected, research = _reject_event(event, reason="insufficient_virtual_cash_no_leverage")
                ledger.append(rejected)
                research_events.append(research)
                excluded += 1
                if position["quantity"] == 0:
                    positions.pop(symbol, None)
                continue
            old_quantity = int(position["quantity"])
            new_quantity = old_quantity + quantity
            old_cost_value = position["average_cost"] * Decimal(old_quantity)
            position["average_cost"] = ((old_cost_value + debit) / Decimal(new_quantity)).quantize(
                PRICE_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
            position["quantity"] = new_quantity
            # A newly simulated A-share buy is deliberately not sellable in the
            # same replay; available_quantity models the exported T+1 boundary.
            cash = (cash - debit).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        else:
            if quantity > int(position["available_quantity"]):
                rejected, research = _reject_event(event, reason="virtual_sell_exceeds_available_quantity_no_short")
                ledger.append(rejected)
                research_events.append(research)
                excluded += 1
                if position["quantity"] == 0:
                    positions.pop(symbol, None)
                continue
            credit = notional - fee
            cash = (cash + credit).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
            position["quantity"] = int(position["quantity"]) - quantity
            position["available_quantity"] = int(position["available_quantity"]) - quantity
            if position["quantity"] == 0:
                positions.pop(symbol, None)

        fill = {
            "seq": seq,
            "fill_type": "virtual_fill",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "virtual_price": _price(virtual_price),
            "notional": _money(notional),
            "fee": _money(fee),
            "cash_after": _money(cash),
            "local_arithmetic_only": True,
            "real_order_submitted": False,
            "real_trade_executed": False,
        }
        virtual_fills.append(fill)
        ledger.append(
            {
                "seq": seq,
                "event_type": "virtual_intent",
                "symbol": symbol,
                "side": side,
                "status": "virtual_fill",
                "reason": "deterministic_local_arithmetic_only",
                "virtual_fill_created": True,
                "cash_after": _money(cash),
                "real_order_submitted": False,
                "real_trade_executed": False,
            }
        )
        research_events.append(
            {
                "seq": seq,
                "event": "watch",
                "symbol": symbol,
                "reason": "virtual_fill_is_research_only_not_an_order",
            }
        )
        accepted += 1

    final_positions = [
        {
            "symbol": symbol,
            "quantity": int(row["quantity"]),
            "available_quantity": int(row["available_quantity"]),
            "average_cost": _price(row["average_cost"]),
            "last_mark": _price(marks[symbol]) if symbol in marks else None,
        }
        for symbol, row in sorted(positions.items())
    ]
    return {
        "source_mode": "caller_supplied_sanitized_export",
        "initial_cash": str(snapshot.get("cash") or "0.00"),
        "final_cash": _money(cash),
        "initial_position_count": len(snapshot.get("positions") or []),
        "final_positions": final_positions,
        "event_count": len(events),
        "event_ledger": ledger,
        "research_events": research_events,
        "virtual_fills": virtual_fills,
        "virtual_fill_count": len(virtual_fills),
        "accepted_virtual_intent_count": accepted,
        "excluded_virtual_intent_count": excluded,
    }


def _scope_payload(normalized: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": normalized.get("schema_version"),
        "mode": normalized.get("mode"),
        "scenario": normalized.get("scenario"),
        "max_frames": normalized.get("max_frames"),
        "source_result_version": normalized.get("source_result_version"),
        "source_scope_hash": normalized.get("source_scope_hash"),
        "source_symbol": normalized.get("source_symbol"),
        "source_task_id": normalized.get("source_task_id"),
        "snapshot": normalized.get("snapshot"),
        "events": normalized.get("events"),
        "simulation": normalized.get("simulation"),
    }


def _deterministic_core(normalized: Mapping[str, Any]) -> dict[str, Any]:
    scope_payload = _scope_payload(normalized)
    scope_hash = _sha256(scope_payload)
    replay = _decimal_replay(normalized)
    virtual_research_events = list(replay.get("research_events") or [])
    replay["virtual_research_events"] = virtual_research_events
    source_lineage = {
        "source_symbol": normalized.get("source_symbol"),
        "source_task_id": normalized.get("source_task_id"),
        "source_result_version": normalized.get("source_result_version"),
        "source_scope_hash": normalized.get("source_scope_hash"),
    }
    safety_boundary = _boundary_flags()
    core = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "local_export_contract_and_replay_verified"
        if normalized.get("snapshot") is not None
        else "local_scope_replay_verified_export_pending",
        "mode": "local_research_replay",
        "scenario": normalized.get("scenario"),
        "max_frames": normalized.get("max_frames"),
        "source_result_version": normalized.get("source_result_version"),
        "source_scope_hash": normalized.get("source_scope_hash"),
        "source_lineage": source_lineage,
        "scope_hash": scope_hash,
        "replay": replay,
        "virtual_fill_count": int(replay.get("virtual_fill_count") or 0),
        "research_event_count": len(replay.get("research_events") or []),
        "virtual_research_events": virtual_research_events,
        "allowed_research_events": ["observe", "watch", "excluded"],
        "caller_supplied_export_compatibility_verified": normalized.get("snapshot") is not None,
        "external_qmt_integration_verified": False,
        "paper_trading_sandbox_ready": False,
        "safety_boundary": safety_boundary,
        **_boundary_flags(),
    }
    core["result_hash"] = _sha256(core)
    return core


def _packet_summary(packet: Any) -> dict[str, Any] | None:
    if not isinstance(packet, Mapping):
        return None
    return {
        "status": packet.get("status"),
        "scope_hash": packet.get("scope_hash"),
        "result_hash": packet.get("result_hash"),
        "task_id": packet.get("task_id"),
        "generated_at": packet.get("generated_at"),
        "virtual_fill_count": int(packet.get("virtual_fill_count") or 0),
    }


def _read_packet_no_init(packet_key: str) -> tuple[Any, str]:
    if not SQLITE_META_PATH.exists():
        return None, "meta_missing"
    connection: sqlite3.Connection | None = None
    try:
        uri = f"file:{SQLITE_META_PATH.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        row = connection.execute(
            "SELECT payload_json FROM packets WHERE packet_key = ?",
            (packet_key,),
        ).fetchone()
    except Exception:
        return None, "packet_read_failed"
    finally:
        if connection is not None:
            connection.close()
    if row is None:
        return None, "packet_missing"
    try:
        parsed = json.loads(row[0])
    except Exception:
        return None, "packet_decode_failed"
    return parsed, "packet_present"


def _persist_success_packets(packet: Mapping[str, Any]) -> None:
    # SQLiteMetaStore is intentionally constructed only inside POST execution.
    SQLiteMetaStore(SQLITE_META_PATH)
    now = _now_iso()
    payload = json.dumps(dict(packet), ensure_ascii=False, sort_keys=True, default=str)
    with sqlite3.connect(SQLITE_META_PATH) as connection:
        connection.executemany(
            "INSERT OR REPLACE INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?)",
            [
                (CURRENT_PACKET_KEY, payload, now),
                (LAST_GOOD_PACKET_KEY, payload, now),
            ],
        )


def _persist_current_packet(packet: Mapping[str, Any]) -> None:
    SQLiteMetaStore(SQLITE_META_PATH).write_packet(CURRENT_PACKET_KEY, dict(packet))


def _failed_packet(
    *,
    error_code: str,
    task_id: str = "",
    call_status: str = "local_replay_blocked_safe",
) -> dict[str, Any]:
    ledger = _local_call_ledger(
        call_status=call_status,
        task_id=task_id,
        error_message_safe=error_code,
    )
    return {
        "packet_key": CURRENT_PACKET_KEY,
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "local_replay_blocked_safe",
        "mode": "local_research_replay",
        "generated_at": _now_iso(),
        "task_id": task_id or None,
        "error_message_safe": error_code,
        "scope_hash": "",
        "result_hash": "",
        "virtual_fill_count": 0,
        "research_event_count": 0,
        "source_lineage": {
            "source_symbol": None,
            "source_task_id": None,
            "source_result_version": None,
            "source_scope_hash": None,
        },
        "virtual_research_events": [],
        "external_qmt_integration_verified": False,
        "paper_trading_sandbox_ready": False,
        "safety_boundary": _boundary_flags(),
        **_boundary_flags(),
        "call_ledger": ledger,
        "warnings": [
            "本地 QMT replay 请求被安全阻断；未连接 QMT、broker 或账户 session，未提交或撤销任何真实委托。"
        ],
    }


def _safe_failure_task_payload(payload: Any, *, error_code: str) -> dict[str, Any]:
    source = payload if isinstance(payload, Mapping) else {}
    scenario = str(source.get("scenario") or "").strip().lower()
    return {
        "request_schema_version": REQUEST_SCHEMA_VERSION,
        "approved_by_user": source.get("approved_by_user") is True,
        "mode_is_local_research_replay": source.get("mode") == "local_research_replay",
        "scenario": scenario if scenario in ALLOWED_SCENARIOS else "invalid",
        "validation_status": "blocked",
        "error_message_safe": error_code,
        "raw_snapshot_stored_in_task_audit": False,
        "external_qmt_connection_allowed": False,
    }


def run_qmt_readonly_local_replay(payload: Any = None) -> dict[str, Any]:
    try:
        normalized = _normalize_request(payload)
    except ReplayValidationError as exc:
        error_code = str(exc) or "invalid_local_replay_request"
        task = task_service.create_task_record(
            TASK_TYPE,
            output_packet_key=CURRENT_PACKET_KEY,
            payload=_safe_failure_task_payload(payload, error_code=error_code),
            current_step="qmt_local_replay_validation_blocked_no_external_call",
            warnings=["请求验证失败；原始快照未写入 task audit，未连接 QMT 或 broker。"],
        )
        ledger = _local_call_ledger(
            call_status="local_replay_validation_blocked",
            task_id=str(task.get("task_id") or ""),
            error_message_safe=error_code,
        )
        task_service.update_task_status(
            str(task.get("task_id") or ""),
            status="failed",
            progress=1.0,
            current_step="qmt_local_replay_validation_failed_safe",
            error_message_safe=error_code,
            call_ledger=ledger,
        )
        packet = _failed_packet(error_code=error_code, task_id=str(task.get("task_id") or ""))
        try:
            _persist_current_packet(packet)
        except Exception:
            packet.setdefault("warnings", []).append("qmt_replay_failed_packet_persist_failed_safe")
        return packet

    scope_payload = _scope_payload(normalized)
    scope_hash = _sha256(scope_payload)
    safe_task_payload = {
        "request_schema_version": REQUEST_SCHEMA_VERSION,
        "approved_by_user": True,
        "mode": normalized["mode"],
        "scenario": normalized["scenario"],
        "max_frames": normalized["max_frames"],
        "source_result_version": normalized["source_result_version"],
        "source_scope_hash": normalized["source_scope_hash"],
        "source_symbol": normalized["source_symbol"],
        "source_task_id": normalized["source_task_id"],
        "scope_hash": scope_hash,
        "position_count": len((normalized.get("snapshot") or {}).get("positions") or []),
        "event_count": len(normalized.get("events") or []),
        "raw_snapshot_stored_in_task_audit": False,
        "external_qmt_connection_allowed": False,
    }
    task = task_service.create_task_record(
        TASK_TYPE,
        output_packet_key=CURRENT_PACKET_KEY,
        payload=safe_task_payload,
        current_step="qmt_local_decimal_replay_queued_no_external_call",
        warnings=[
            "任务仅回放 caller-supplied 脱敏 export 或绑定的本地 lineage；不会发现、导入、启动或连接外部 QMT。"
        ],
    )
    task_id = str(task.get("task_id") or "")
    task_service.update_task_status(
        task_id,
        status="running",
        progress=0.5,
        current_step="qmt_local_decimal_replay_running_no_external_call",
    )

    try:
        core = _deterministic_core(normalized)
        ledger = _local_call_ledger(
            call_status="local_decimal_replay_completed",
            row_count=int((core.get("replay") or {}).get("event_count") or 0),
            scope_hash=str(core.get("scope_hash") or ""),
            task_id=task_id,
        )
        packet = {
            "packet_key": CURRENT_PACKET_KEY,
            **core,
            "generated_at": _now_iso(),
            "task_id": task_id,
            "task_status": "success",
            "call_ledger": ledger,
            "warnings": [
                "virtual_fill 仅为 Decimal 本地算术证据，不是委托、成交、持仓变更或 QMT 外部集成证据。",
                "外部 QMT read-only 连接、broker/session/account query 和真实交易均未实现。",
            ],
        }
        _persist_success_packets(packet)
    except Exception:
        error_code = "local_replay_or_persistence_failed_safe"
        failed_ledger = _local_call_ledger(
            call_status="local_replay_failed_safe",
            scope_hash=scope_hash,
            task_id=task_id,
            error_message_safe=error_code,
        )
        task_service.update_task_status(
            task_id,
            status="failed",
            progress=1.0,
            current_step="qmt_local_decimal_replay_failed_safe",
            error_message_safe=error_code,
            call_ledger=failed_ledger,
        )
        packet = _failed_packet(error_code=error_code, task_id=task_id)
        try:
            _persist_current_packet(packet)
        except Exception:
            packet.setdefault("warnings", []).append("qmt_replay_failed_packet_persist_failed_safe")
        return packet

    task_service.update_task_status(
        task_id,
        status="success",
        progress=1.0,
        current_step="qmt_local_decimal_replay_completed_no_external_call",
        output_packet_key=CURRENT_PACKET_KEY,
        call_ledger=packet["call_ledger"],
        warning="qmt_local_replay_completed_without_external_qmt_or_trade_execution",
    )
    return packet


def read_qmt_replay_cache() -> dict[str, Any]:
    current, current_source = _read_packet_no_init(CURRENT_PACKET_KEY)
    last_good, last_good_source = _read_packet_no_init(LAST_GOOD_PACKET_KEY)
    success_statuses = {
        "local_export_contract_and_replay_verified",
        "local_scope_replay_verified_export_pending",
    }
    current_ok = isinstance(current, Mapping) and current.get("status") in success_statuses
    last_good_ok = isinstance(last_good, Mapping) and last_good.get("status") in success_statuses
    selected = current if current_ok else last_good if last_good_ok else current if isinstance(current, Mapping) else None
    ledger = _local_call_ledger(call_status="cache_read_no_external_call")
    if not isinstance(selected, Mapping):
        return {
            "packet_key": CACHE_PACKET_KEY,
            "schema_version": CACHE_SCHEMA_VERSION,
            "status": "cache_missing",
            "mode": "cache_only",
            "cache_only": True,
            "read_only": True,
            "cache_source": current_source,
            "current_packet_source": current_source,
            "last_good_packet_source": last_good_source,
            "current_result_summary": None,
            "last_good_result_summary": None,
            "scope_hash": "",
            "result_hash": "",
            "virtual_fill_count": 0,
            "research_event_count": 0,
            "source_lineage": {
                "source_symbol": None,
                "source_task_id": None,
                "source_result_version": None,
                "source_scope_hash": None,
            },
            "virtual_research_events": [],
            "external_qmt_integration_verified": False,
            "paper_trading_sandbox_ready": False,
            "safety_boundary": _boundary_flags(),
            **_boundary_flags(),
            "call_ledger": ledger,
            "warnings": ["尚无本地 QMT replay 缓存；GET 未创建目录、数据库、任务或外部连接。"],
        }

    packet = dict(selected)
    selected_status = str(packet.get("status") or "")
    packet.update(
        {
            "packet_key": CACHE_PACKET_KEY,
            "schema_version": CACHE_SCHEMA_VERSION,
            "status": "ready_cache_replay" if current_ok else "degraded_last_good_replay" if last_good_ok else "latest_attempt_blocked",
            "selected_result_status": selected_status,
            "mode": "cache_only",
            "cache_only": True,
            "read_only": True,
            "cache_source": "sqlite_meta_read_only",
            "current_packet_source": current_source,
            "last_good_packet_source": last_good_source,
            "current_result_summary": _packet_summary(current),
            "last_good_result_summary": _packet_summary(last_good),
            **_boundary_flags(),
            "call_ledger": ledger,
            "warnings": [
                "GET 仅回放 SQLite 中的本地 current/last-good 结果，不创建任务、不连接 QMT、不执行真实交易。"
            ],
        }
    )
    return packet
