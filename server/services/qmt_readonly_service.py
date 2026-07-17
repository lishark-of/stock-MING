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
import hmac
import json
import re
import secrets
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
TASK_COMPLETED_STEP = "qmt_local_decimal_replay_completed_no_external_call"
CANDIDATE_PACKET_KEY = "command_center_3_candidate_radar_cache"
NEXT_SESSION_PACKET_KEY = "command_center_next_session_projection_packet"
CANDIDATE_TASK_TYPE = "run_candidate_radar_full_pool_worker_fallback"
CANDIDATE_TASK_STEP = "candidate_radar_v05_local_batch_ready"
CANDIDATE_LEDGER_FALSE_FIELDS = (
    "external",
    "external_calls_triggered",
    "tushare_called",
    "deepseek_called",
    "github_called",
    "provider_called",
    "model_called",
    "provider_or_model_calls",
    "worker_called",
    "worker_dispatched",
    "qmt_called",
    "qmt_external_connection_attempted",
    "qmt_process_discovered",
    "qmt_client_imported",
    "xtquant_imported",
    "trade_called",
    "trading_called",
    "broker_called",
    "broker_session_opened",
    "account_query_executed",
    "order_called",
    "real_order_submitted",
    "real_order_cancelled",
    "real_trade_executed",
    "real_holdings_modified",
    "real_trading_enabled",
    "contains_secret",
)
CANDIDATE_LEDGER_ZERO_FIELDS = (
    "external_call_count",
    "qmt_connection_count",
    "broker_session_count",
    "real_order_count",
    "real_trade_count",
)
CANDIDATE_LEDGER_TRUE_FIELDS = (
    "does_not_execute_trades",
    "does_not_modify_strategy_action",
    "does_not_modify_holdings",
)
CANDIDATE_TASK_FALSE_FIELDS = CANDIDATE_LEDGER_FALSE_FIELDS
CANDIDATE_TASK_ZERO_FIELDS = CANDIDATE_LEDGER_ZERO_FIELDS
CANDIDATE_TASK_TRUE_FIELDS = CANDIDATE_LEDGER_TRUE_FIELDS
CANONICAL_SOURCE_DURABLE_STORAGE_SOURCES = frozenset({"sqlite_meta", "memory_and_sqlite"})
_CANONICAL_SAFETY_FIELDS = frozenset(
    CANDIDATE_TASK_FALSE_FIELDS + CANDIDATE_TASK_ZERO_FIELDS + CANDIDATE_TASK_TRUE_FIELDS
)
_CANONICAL_ALLOWED_HIGH_RISK_METADATA_FIELDS = frozenset({
    "trade_date",
    "expected_trade_date",
    "provider_backed",
})
_CANONICAL_HIGH_RISK_PREFIXES = (
    "external_",
    "provider_",
    "model_",
    "worker_",
    "qmt_",
    "broker_",
    "account_",
    "order_",
    "trade_",
    "real_order_",
    "real_trade_",
    "secret_",
)
_CANONICAL_NESTED_EXECUTION_PREFIXES = (
    "external_",
    "qmt_",
    "broker_",
    "account_",
    "order_",
    "trade_",
    "real_order_",
    "real_trade_",
)

ALLOWED_SCENARIOS = {"baseline", "stress", "recovery"}
ALLOWED_MAX_FRAMES = {12, 24, 48}
ALLOWED_EVENT_TYPES = {"market_mark", "virtual_intent"}
ALLOWED_SIDES = {"BUY", "SELL"}
SYMBOL_PATTERN = re.compile(r"^[0-9]{6}\.(SH|SZ|BJ)$")
SOURCE_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
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


def _result_integrity_key_path() -> Path:
    return SQLITE_META_PATH.with_name("qmt_replay_result_integrity.key")


def _read_result_integrity_key() -> bytes | None:
    path = _result_integrity_key_path()
    try:
        value = path.read_bytes()
    except OSError:
        return None
    return value if len(value) == 32 else None


def _load_or_create_result_integrity_key() -> bytes:
    existing = _read_result_integrity_key()
    if existing is not None:
        return existing
    path = _result_integrity_key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = secrets.token_bytes(32)
    try:
        with path.open("xb") as handle:
            handle.write(candidate)
        path.chmod(0o600)
        return candidate
    except FileExistsError:
        concurrent = _read_result_integrity_key()
        if concurrent is None:
            raise RuntimeError("qmt_replay_result_integrity_key_invalid")
        return concurrent


def _result_mac(key: bytes, material: Mapping[str, Any]) -> str:
    return hmac.new(key, _canonical_json(material).encode("utf-8"), hashlib.sha256).hexdigest()


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
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "provider_called": False,
        "model_called": False,
        "provider_or_model_calls": False,
        "worker_called": False,
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


def _normalize_source_data_date(value: Any) -> str:
    if not isinstance(value, str):
        raise ReplayValidationError("source_data_date_required")
    text = _required_text(value, code="source_data_date_required", limit=10)
    match = re.fullmatch(r"(\d{4})-?(\d{2})-?(\d{2})", text)
    if not match:
        raise ReplayValidationError("invalid_source_data_date")
    try:
        parsed = _dt.date(*(int(part) for part in match.groups()))
    except ValueError:
        raise ReplayValidationError("invalid_source_data_date") from None
    return parsed.strftime("%Y%m%d")


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
    source_data_date = _normalize_source_data_date(payload.get("source_data_date"))
    source_symbol = _normalize_symbol(payload.get("source_symbol"))
    source_task_id = _required_text(
        payload.get("source_task_id"),
        code="source_task_id_required",
        limit=80,
    )
    if not SOURCE_TASK_ID_PATTERN.fullmatch(source_task_id):
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
        "source_data_date": source_data_date,
        "source_symbol": source_symbol,
        "source_task_id": source_task_id,
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
        "source_data_date": normalized.get("source_data_date"),
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
        "source_data_date": normalized.get("source_data_date"),
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
        "source_data_date": normalized.get("source_data_date"),
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
    virtual_fill_count = packet.get("virtual_fill_count")
    if isinstance(virtual_fill_count, bool) or not isinstance(virtual_fill_count, int) or virtual_fill_count < 0:
        virtual_fill_count = 0
    return {
        "status": packet.get("status"),
        "scope_hash": packet.get("scope_hash"),
        "result_hash": packet.get("result_hash"),
        "result_mac": packet.get("result_mac"),
        "task_id": packet.get("task_id"),
        "generated_at": packet.get("generated_at"),
        "virtual_fill_count": virtual_fill_count,
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


def _read_persisted_source_task_no_init(task_id: str) -> Mapping[str, Any] | None:
    if not SQLITE_META_PATH.exists():
        return None
    try:
        task = SQLiteMetaStore(SQLITE_META_PATH, read_only=True).read_task_status(task_id)
    except Exception:
        return None
    return task if isinstance(task, Mapping) else None


def _read_source_task_history_rows_no_init(task_id: str) -> list[dict[str, Any]]:
    if not SQLITE_META_PATH.exists():
        return []
    connection: sqlite3.Connection | None = None
    try:
        uri = f"file:{SQLITE_META_PATH.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        rows = connection.execute(
            """
            SELECT history_id, task_id, task_type, payload_json, updated_at, payload_digest
            FROM task_status_history
            WHERE task_id = ?
            ORDER BY history_id ASC
            """,
            (task_id,),
        ).fetchall()
    except Exception:
        return []
    finally:
        if connection is not None:
            connection.close()
    return [
        {
            "history_id": row[0],
            "task_id": row[1],
            "task_type": row[2],
            "payload_json": row[3],
            "updated_at": row[4],
            "payload_digest": row[5],
        }
        for row in rows
    ]


def _parse_iso_datetime(value: Any) -> _dt.datetime:
    try:
        parsed = _dt.datetime.fromisoformat(str(value or ""))
    except (TypeError, ValueError) as exc:
        raise ReplayValidationError("canonical_source_task_history_time_invalid") from exc
    return parsed


def _validate_source_task_authoritative_history(
    source_task: Mapping[str, Any],
    persisted_projection: Mapping[str, Any],
) -> None:
    expected_events = (
        ("pending", 0.0, "candidate_radar_full_pool_worker_fallback_queued"),
        ("running", 0.2, "candidate_radar_v05_local_batch_reading_supplied_pool"),
        ("running", 0.45, "candidate_radar_v05_local_batch_running_v04_runtime"),
        ("success", 1.0, CANDIDATE_TASK_STEP),
    )
    status_history = source_task.get("status_history")
    task_log = source_task.get("task_log")
    if not isinstance(status_history, list) or not isinstance(task_log, list):
        raise ReplayValidationError("canonical_source_task_history_invalid")
    if len(status_history) != len(expected_events) or len(task_log) != len(expected_events):
        raise ReplayValidationError("canonical_source_task_history_invalid")
    previous_at: _dt.datetime | None = None
    for index, (expected_status, expected_progress, expected_step) in enumerate(expected_events):
        status_row = status_history[index]
        log_row = task_log[index]
        if not isinstance(status_row, Mapping) or not isinstance(log_row, Mapping):
            raise ReplayValidationError("canonical_source_task_history_invalid")
        if (
            status_row.get("status") != expected_status
            or type(status_row.get("progress")) is not float
            or status_row.get("progress") != expected_progress
            or status_row.get("current_step") != expected_step
            or log_row.get("event") != ("task_created" if index == 0 else "task_status_updated")
            or log_row.get("status") != expected_status
            or log_row.get("current_step") != expected_step
            or log_row.get("at") != status_row.get("at")
            or log_row.get("external") is not False
            or log_row.get("external_calls_triggered") is not False
            or log_row.get("contains_secret") is not False
            or log_row.get("stack_trace_included") is not False
        ):
            raise ReplayValidationError("canonical_source_task_history_invalid")
        current_at = _parse_iso_datetime(status_row.get("at"))
        if previous_at is not None and current_at < previous_at:
            raise ReplayValidationError("canonical_source_task_history_time_invalid")
        previous_at = current_at
    if (
        source_task.get("created_at") != status_history[0].get("at")
        or source_task.get("started_at") != status_history[1].get("at")
        or source_task.get("finished_at") != status_history[-1].get("at")
    ):
        raise ReplayValidationError("canonical_source_task_history_time_invalid")

    durable_rows = _read_source_task_history_rows_no_init(str(source_task.get("task_id") or ""))
    if len(durable_rows) < len(expected_events):
        raise ReplayValidationError("canonical_source_task_durable_history_invalid")
    previous_payload: Mapping[str, Any] | None = None
    previous_history_id = 0
    previous_updated_at: _dt.datetime | None = None
    for durable_row in durable_rows:
        payload_json = durable_row.get("payload_json")
        digest = durable_row.get("payload_digest")
        if not isinstance(payload_json, str) or hashlib.sha256(payload_json.encode("utf-8")).hexdigest() != digest:
            raise ReplayValidationError("canonical_source_task_durable_history_digest_invalid")
        try:
            payload = json.loads(payload_json)
        except Exception as exc:
            raise ReplayValidationError("canonical_source_task_durable_history_invalid") from exc
        if (
            not isinstance(payload, Mapping)
            or durable_row.get("task_id") != source_task.get("task_id")
            or durable_row.get("task_type") != CANDIDATE_TASK_TYPE
            or payload.get("task_id") != source_task.get("task_id")
            or payload.get("task_type") != CANDIDATE_TASK_TYPE
            or type(durable_row.get("history_id")) is not int
            or durable_row.get("history_id") <= previous_history_id
        ):
            raise ReplayValidationError("canonical_source_task_durable_history_invalid")
        durable_time = _parse_iso_datetime(durable_row.get("updated_at"))
        if previous_updated_at is not None and durable_time < previous_updated_at:
            raise ReplayValidationError("canonical_source_task_history_time_invalid")
        embedded_history = payload.get("status_history")
        embedded_log = payload.get("task_log")
        if not isinstance(embedded_history, list) or not isinstance(embedded_log, list):
            raise ReplayValidationError("canonical_source_task_durable_history_invalid")
        if previous_payload is not None:
            previous_status = previous_payload.get("status_history")
            previous_log = previous_payload.get("task_log")
            if (
                not isinstance(previous_status, list)
                or not isinstance(previous_log, list)
                or embedded_history[: len(previous_status)] != previous_status
                or embedded_log[: len(previous_log)] != previous_log
            ):
                raise ReplayValidationError("canonical_source_task_durable_history_not_append_only")
        if embedded_history:
            latest = embedded_history[-1]
            if (
                not isinstance(latest, Mapping)
                or payload.get("status") != latest.get("status")
                or payload.get("progress") != latest.get("progress")
                or payload.get("current_step") != latest.get("current_step")
            ):
                raise ReplayValidationError("canonical_source_task_durable_history_invalid")
            latest_at = _parse_iso_datetime(latest.get("at"))
            if abs((durable_time - latest_at).total_seconds()) > 1.0:
                raise ReplayValidationError("canonical_source_task_history_time_invalid")
        previous_payload = payload
        previous_history_id = int(durable_row["history_id"])
        previous_updated_at = durable_time
    previous_projection = {
        str(key): value
        for key, value in (previous_payload or {}).items()
        if key != "storage_source"
    }
    if previous_payload is None or _canonical_json(previous_projection) != _canonical_json(persisted_projection):
        raise ReplayValidationError("canonical_source_task_durable_history_current_mismatch")


def _validate_exact_safety_boundary(value: Mapping[str, Any], *, code: str) -> None:
    if any(value.get(field) is not False for field in CANDIDATE_TASK_FALSE_FIELDS):
        raise ReplayValidationError(code)
    if any(
        type(value.get(field)) is not int or value.get(field) != 0
        for field in CANDIDATE_TASK_ZERO_FIELDS
    ):
        raise ReplayValidationError(code)
    if any(value.get(field) is not True for field in CANDIDATE_TASK_TRUE_FIELDS):
        raise ReplayValidationError(code)
    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for raw_key, raw_value in node.items():
                key = str(raw_key or "").strip().lower()
                if key in CANDIDATE_TASK_FALSE_FIELDS and raw_value is not False:
                    raise ReplayValidationError(code)
                if key in CANDIDATE_TASK_ZERO_FIELDS and (
                    type(raw_value) is not int or raw_value != 0
                ):
                    raise ReplayValidationError(code)
                if key in CANDIDATE_TASK_TRUE_FIELDS and raw_value is not True:
                    raise ReplayValidationError(code)
                if key == "provider_backed" and raw_value is not False:
                    raise ReplayValidationError(code)
                if "secret" in key and key not in _CANONICAL_SAFETY_FIELDS and raw_value is not False:
                    raise ReplayValidationError(code)
                if key.startswith(_CANONICAL_NESTED_EXECUTION_PREFIXES) and key not in (
                    _CANONICAL_SAFETY_FIELDS | _CANONICAL_ALLOWED_HIGH_RISK_METADATA_FIELDS
                ):
                    if isinstance(raw_value, bool) and raw_value is not False:
                        raise ReplayValidationError(code)
                    if type(raw_value) is int and raw_value != 0:
                        raise ReplayValidationError(code)
                walk(raw_value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(value)


def _candidate_v05_scope_hash_from_task_payload(
    source_pool: list[Any],
    payload_safe: Mapping[str, Any],
) -> str:
    if any(not isinstance(row, Mapping) for row in source_pool):
        raise ReplayValidationError("canonical_source_task_pool_invalid")
    # Reuse the producer's pure normalization and scope projection.  Replaying
    # only the raw rows would omit producer-added rank and data-gap fields and
    # would therefore reject every legitimate persisted v0.5 task.
    from . import candidate_service

    scan_snapshot, _, _ = candidate_service._snapshot_with_local_candidate_pool(
        {},
        payload_safe,
        "full_pool_local_scan",
    )
    normalized_pool = scan_snapshot.get("next_ticket_candidates")
    if not isinstance(normalized_pool, list) or not normalized_pool:
        raise ReplayValidationError("canonical_source_task_pool_invalid")
    return candidate_service._candidate_v05_scope_hash(
        [dict(row) for row in normalized_pool if isinstance(row, Mapping)],
        payload_safe,
    )


def _canonical_runtime_artifact_path(
    path_label: Any,
    *,
    scope_hash: str,
    expected_name: str,
) -> Path:
    label = str(path_label or "").strip()
    relative = Path(label)
    expected_parts = ("v04_acceptance", scope_hash, "worker_runtime", expected_name)
    if relative.is_absolute() or relative.parts != expected_parts:
        raise ReplayValidationError("canonical_candidate_runtime_artifact_path_invalid")
    root = (SQLITE_META_PATH.parent / "v04_acceptance").resolve()
    target = (SQLITE_META_PATH.parent / relative).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ReplayValidationError("canonical_candidate_runtime_artifact_missing")
    return target


def _read_runtime_event_rows(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ReplayValidationError("canonical_candidate_runtime_artifact_read_failed") from exc
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception as exc:
            raise ReplayValidationError("canonical_candidate_runtime_event_log_invalid") from exc
        if not isinstance(row, dict):
            raise ReplayValidationError("canonical_candidate_runtime_event_log_invalid")
        rows.append(row)
    return rows


def _canonical_fresh_lineage(packet: Any, *, lineage_key: str) -> dict[str, Any]:
    if not isinstance(packet, Mapping):
        raise ReplayValidationError("canonical_source_packet_missing")
    lineage = packet.get(lineage_key)
    if not isinstance(lineage, Mapping):
        raise ReplayValidationError("canonical_source_lineage_missing")
    if lineage.get("schema_version") != "candidate_radar_v05_next_session_lineage.v1":
        raise ReplayValidationError("canonical_source_lineage_schema_invalid")
    if lineage.get("status") != "same_packet_lineage_ready":
        raise ReplayValidationError("canonical_source_lineage_status_invalid")
    if lineage.get("candidate_packet_key") != CANDIDATE_PACKET_KEY:
        raise ReplayValidationError("canonical_source_packet_key_invalid")
    _validate_exact_safety_boundary(lineage, code="canonical_source_lineage_boundary_invalid")
    if not all(
        (
            lineage.get("research_only") is True,
            lineage.get("no_buy") is True,
            lineage.get("no_action") is True,
            lineage.get("no_trade") is True,
            lineage.get("does_not_modify_strategy_action") is True,
            lineage.get("does_not_modify_operation_zones") is True,
        )
    ):
        raise ReplayValidationError("canonical_source_boundary_invalid")
    symbol = _normalize_symbol(lineage.get("symbol"))
    task_id = _required_text(lineage.get("candidate_task_id"), code="canonical_source_task_id_invalid", limit=80)
    if not SOURCE_TASK_ID_PATTERN.fullmatch(task_id):
        raise ReplayValidationError("canonical_source_task_id_invalid")
    result_version = _required_text(
        lineage.get("candidate_result_version"),
        code="canonical_source_result_version_invalid",
        limit=120,
    )
    if not SOURCE_VERSION_PATTERN.fullmatch(result_version):
        raise ReplayValidationError("canonical_source_result_version_invalid")
    scope_hash = _required_text(
        lineage.get("candidate_scope_hash"),
        code="canonical_source_scope_hash_invalid",
        limit=64,
    )
    if not SOURCE_HASH_PATTERN.fullmatch(scope_hash):
        raise ReplayValidationError("canonical_source_scope_hash_invalid")
    data_date = _normalize_source_data_date(lineage.get("data_date"))
    freshness = lineage.get("freshness_state")
    if not isinstance(freshness, Mapping):
        raise ReplayValidationError("canonical_source_freshness_missing")
    state = str(freshness.get("state") or "").strip().lower()
    generic_state = str(freshness.get("freshness_state") or "").strip().lower()
    if state not in {"fresh", "current", "today"} or generic_state != state:
        raise ReplayValidationError("canonical_source_freshness_invalid")
    if freshness.get("expected_trade_date_calendar_validated") is not True:
        raise ReplayValidationError("canonical_source_calendar_unvalidated")
    if freshness.get("calendar_validated") not in {None, True}:
        raise ReplayValidationError("canonical_source_calendar_conflict")
    if _normalize_source_data_date(freshness.get("data_date")) != data_date:
        raise ReplayValidationError("canonical_source_freshness_date_mismatch")
    if _normalize_source_data_date(freshness.get("expected_trade_date")) != data_date:
        raise ReplayValidationError("canonical_source_expected_date_mismatch")
    if _normalize_source_data_date(freshness.get("as_of_date")) != data_date:
        raise ReplayValidationError("canonical_source_as_of_date_mismatch")
    return {
        "source_symbol": symbol,
        "source_task_id": task_id,
        "source_result_version": result_version,
        "source_scope_hash": scope_hash,
        "source_data_date": data_date,
        "raw": dict(lineage),
    }


def _validate_canonical_source_binding(normalized: Mapping[str, Any]) -> dict[str, Any]:
    candidate, candidate_source = _read_packet_no_init(CANDIDATE_PACKET_KEY)
    next_session, next_source = _read_packet_no_init(NEXT_SESSION_PACKET_KEY)
    if candidate_source != "packet_present" or next_source != "packet_present":
        raise ReplayValidationError("canonical_candidate_next_packet_missing")
    if not isinstance(candidate, Mapping) or not isinstance(next_session, Mapping):
        raise ReplayValidationError("canonical_candidate_next_packet_invalid")
    _validate_exact_safety_boundary(candidate, code="canonical_candidate_packet_boundary_invalid")
    _validate_exact_safety_boundary(next_session, code="canonical_next_session_packet_boundary_invalid")
    if not isinstance(candidate.get("warnings"), list) or candidate.get("warnings"):
        raise ReplayValidationError("canonical_candidate_warnings_present")
    if not isinstance(next_session.get("warnings"), list) or next_session.get("warnings"):
        raise ReplayValidationError("canonical_next_session_warnings_present")
    if candidate.get("packet_key") != CANDIDATE_PACKET_KEY or candidate.get("schema_version") != "candidate_radar_cache.v1":
        raise ReplayValidationError("canonical_candidate_packet_invalid")
    if candidate.get("status") != "candidate_radar_v05_local_batch_ready":
        raise ReplayValidationError("canonical_candidate_status_invalid")
    if (
        candidate.get("scan_mode") != "v05_candidate_local_batch"
        or candidate.get("mode") != "v05_candidate_local_batch"
        or candidate.get("cache_only") is not True
        or candidate.get("read_only") is not True
    ):
        raise ReplayValidationError("canonical_candidate_mode_invalid")
    if next_session.get("packet_key") != NEXT_SESSION_PACKET_KEY or next_session.get("schema_version") != "next_session_projection.v1":
        raise ReplayValidationError("canonical_next_session_packet_invalid")
    if next_session.get("status") != "ready_cache_replay":
        raise ReplayValidationError("canonical_next_session_status_invalid")
    if next_session.get("mode") != "cache_only" or next_session.get("cache_only") is not True or next_session.get("read_only") is not True:
        raise ReplayValidationError("canonical_next_session_mode_invalid")

    candidate_lineage = _canonical_fresh_lineage(
        candidate,
        lineage_key="candidate_radar_v05_next_session_lineage",
    )
    next_lineage = _canonical_fresh_lineage(
        next_session,
        lineage_key="candidate_radar_v05_lineage",
    )
    if candidate_lineage["raw"] != next_lineage["raw"]:
        raise ReplayValidationError("canonical_candidate_next_lineage_mismatch")
    candidate_freshness = candidate.get("freshness_state")
    next_freshness = next_session.get("freshness_state")
    lineage_freshness = candidate_lineage["raw"].get("freshness_state")
    if not isinstance(candidate_freshness, Mapping) or not isinstance(next_freshness, Mapping):
        raise ReplayValidationError("canonical_source_top_freshness_missing")
    if not (
        _canonical_json(candidate_freshness)
        == _canonical_json(next_freshness)
        == _canonical_json(lineage_freshness)
    ):
        raise ReplayValidationError("canonical_source_top_freshness_mismatch")
    expected = {key: candidate_lineage[key] for key in (
        "source_symbol",
        "source_task_id",
        "source_result_version",
        "source_scope_hash",
        "source_data_date",
    )}
    if _normalize_symbol(candidate.get("latest_confirmed_symbol")) != expected["source_symbol"]:
        raise ReplayValidationError("canonical_candidate_symbol_binding_invalid")
    if _normalize_symbol(next_session.get("latest_confirmed_symbol")) != expected["source_symbol"]:
        raise ReplayValidationError("canonical_next_session_symbol_binding_invalid")
    candidate_top_rows = candidate.get("candidate_radar_v05_top_rows")
    if not isinstance(candidate_top_rows, list) or not candidate_top_rows or not isinstance(candidate_top_rows[0], Mapping):
        raise ReplayValidationError("canonical_candidate_top_row_missing")
    if _normalize_symbol(candidate_top_rows[0].get("symbol")) != expected["source_symbol"]:
        raise ReplayValidationError("canonical_candidate_top_symbol_mismatch")
    observed = {key: normalized.get(key) for key in expected}
    if observed != expected:
        raise ReplayValidationError("canonical_source_request_mismatch")
    if candidate.get("task_id") != expected["source_task_id"] or candidate.get("latest_confirmed_task_id") != expected["source_task_id"]:
        raise ReplayValidationError("canonical_candidate_task_binding_invalid")
    if (
        candidate.get("latest_confirmed_task_status") != "success"
        or candidate.get("latest_confirmed_task_current_step") != CANDIDATE_TASK_STEP
    ):
        raise ReplayValidationError("canonical_candidate_task_status_invalid")
    if candidate.get("candidate_radar_v05_result_version") != expected["source_result_version"]:
        raise ReplayValidationError("canonical_candidate_result_version_mismatch")
    if candidate.get("candidate_radar_v05_scope_hash") != expected["source_scope_hash"]:
        raise ReplayValidationError("canonical_candidate_scope_hash_mismatch")
    if _normalize_source_data_date(candidate.get("trade_date")) != expected["source_data_date"]:
        raise ReplayValidationError("canonical_candidate_data_date_mismatch")
    if next_session.get("source_task_id") != expected["source_task_id"] or next_session.get("result_version") != expected["source_result_version"]:
        raise ReplayValidationError("canonical_next_session_task_result_mismatch")
    if (
        next_session.get("latest_confirmed_task_id") != expected["source_task_id"]
        or next_session.get("latest_confirmed_task_status") != "success"
        or next_session.get("latest_confirmed_task_current_step") != CANDIDATE_TASK_STEP
    ):
        raise ReplayValidationError("canonical_next_session_task_status_invalid")
    if next_session.get("candidate_scope_hash") != expected["source_scope_hash"]:
        raise ReplayValidationError("canonical_next_session_scope_hash_mismatch")
    if _normalize_source_data_date(next_session.get("data_date") or next_session.get("trade_date")) != expected["source_data_date"]:
        raise ReplayValidationError("canonical_next_session_data_date_mismatch")
    chart_payload = next_session.get("chart_payload")
    if not isinstance(chart_payload, Mapping):
        raise ReplayValidationError("canonical_next_session_chart_payload_missing")
    if chart_payload.get("status") != "ready" or chart_payload.get("source_packet") != NEXT_SESSION_PACKET_KEY:
        raise ReplayValidationError("canonical_next_session_chart_payload_invalid")
    if chart_payload.get("is_exact_next_session_packet") is not True:
        raise ReplayValidationError("canonical_next_session_chart_payload_invalid")
    for key in ("symbol", "ts_code", "confirmed_symbol"):
        if _normalize_symbol(chart_payload.get(key)) != expected["source_symbol"]:
            raise ReplayValidationError("canonical_next_session_chart_symbol_mismatch")
    if (
        chart_payload.get("source_task_id") != expected["source_task_id"]
        or chart_payload.get("result_version") != expected["source_result_version"]
        or chart_payload.get("candidate_scope_hash") != expected["source_scope_hash"]
        or _normalize_source_data_date(chart_payload.get("data_date")) != expected["source_data_date"]
        or chart_payload.get("candidate_radar_v05_lineage_status") != "same_packet_lineage_ready"
    ):
        raise ReplayValidationError("canonical_next_session_chart_binding_invalid")

    source_task = task_service.read_task_status(expected["source_task_id"])
    if not isinstance(source_task, Mapping):
        raise ReplayValidationError("canonical_source_task_missing")
    if source_task.get("storage_source") not in CANONICAL_SOURCE_DURABLE_STORAGE_SOURCES:
        raise ReplayValidationError("canonical_source_task_not_durable")
    persisted_source_task = _read_persisted_source_task_no_init(expected["source_task_id"])
    if not isinstance(persisted_source_task, Mapping):
        raise ReplayValidationError("canonical_source_task_not_durable")
    accessor_projection = {
        str(key): value
        for key, value in source_task.items()
        if key != "storage_source"
    }
    persisted_projection = {
        str(key): value
        for key, value in persisted_source_task.items()
        if key != "storage_source"
    }
    if _canonical_json(accessor_projection) != _canonical_json(persisted_projection):
        raise ReplayValidationError("canonical_source_task_memory_sqlite_mismatch")
    if source_task.get("task_type") != CANDIDATE_TASK_TYPE:
        raise ReplayValidationError("canonical_source_task_type_invalid")
    if (
        source_task.get("status") != "success"
        or source_task.get("current_step") != CANDIDATE_TASK_STEP
        or type(source_task.get("progress")) is not float
        or source_task.get("progress") != 1.0
        or source_task.get("error_message_safe") != ""
        or not isinstance(source_task.get("finished_at"), str)
        or not str(source_task.get("finished_at") or "").strip()
    ):
        raise ReplayValidationError("canonical_source_task_status_invalid")
    _validate_source_task_authoritative_history(source_task, persisted_projection)
    if source_task.get("output_packet_key") != CANDIDATE_PACKET_KEY:
        raise ReplayValidationError("canonical_source_task_output_invalid")
    if source_task.get("cache_replay_only") is True:
        raise ReplayValidationError("canonical_source_task_not_durable")
    _validate_exact_safety_boundary(source_task, code="canonical_source_task_boundary_invalid")
    payload_safe = source_task.get("payload_safe")
    if not isinstance(payload_safe, Mapping):
        raise ReplayValidationError("canonical_source_task_payload_invalid")
    expected_input_hash = hashlib.sha256(
        json.dumps(
            {"task_type": CANDIDATE_TASK_TYPE, "payload_safe": dict(payload_safe)},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:16]
    if source_task.get("input_hash") != expected_input_hash:
        raise ReplayValidationError("canonical_source_task_input_hash_invalid")
    status_history = source_task.get("status_history")
    if not isinstance(status_history, list) or not status_history or not isinstance(status_history[-1], Mapping):
        raise ReplayValidationError("canonical_source_task_history_invalid")
    if (
        status_history[-1].get("status") != "success"
        or status_history[-1].get("current_step") != CANDIDATE_TASK_STEP
        or type(status_history[-1].get("progress")) is not float
        or status_history[-1].get("progress") != 1.0
    ):
        raise ReplayValidationError("canonical_source_task_history_invalid")
    if payload_safe.get("runtime_mode") != "v05_candidate_local_batch" or payload_safe.get("operator_approved") is not True:
        raise ReplayValidationError("canonical_source_task_payload_invalid")
    if payload_safe.get("candidate_scope_hash") != expected["source_scope_hash"]:
        raise ReplayValidationError("canonical_source_task_scope_mismatch")
    if payload_safe.get("confirm_scope_hash") != expected["source_scope_hash"]:
        raise ReplayValidationError("canonical_source_task_confirmation_mismatch")
    if _normalize_source_data_date(payload_safe.get("data_date") or payload_safe.get("trade_date")) != expected["source_data_date"]:
        raise ReplayValidationError("canonical_source_task_data_date_mismatch")
    source_pool = payload_safe.get("full_pool_candidates")
    if not isinstance(source_pool, list):
        raise ReplayValidationError("canonical_source_task_pool_invalid")
    if _candidate_v05_scope_hash_from_task_payload(source_pool, payload_safe) != expected["source_scope_hash"]:
        raise ReplayValidationError("canonical_source_task_scope_not_derived")
    raw_pool_count = len(source_pool)
    source_pool_symbols: list[str] = []
    for row in source_pool:
        if not isinstance(row, Mapping):
            raise ReplayValidationError("canonical_source_task_pool_invalid")
        try:
            symbol = _normalize_symbol(row.get("ticker") or row.get("symbol"))
        except ReplayValidationError as exc:
            raise ReplayValidationError("canonical_source_task_pool_invalid") from exc
        if symbol not in source_pool_symbols:
            source_pool_symbols.append(symbol)
    source_pool_symbol_set = set(source_pool_symbols)
    if not source_pool_symbol_set or expected["source_symbol"] not in source_pool_symbol_set:
        raise ReplayValidationError("canonical_source_symbol_not_in_task_pool")
    task_ledger = source_task.get("call_ledger")
    if not isinstance(task_ledger, list) or len(task_ledger) != 1 or not isinstance(task_ledger[0], Mapping):
        raise ReplayValidationError("canonical_source_task_ledger_invalid")
    task_ledger_row = task_ledger[0]
    if task_ledger_row.get("api") != "local_candidate_radar_v05_local_batch":
        raise ReplayValidationError("canonical_source_task_ledger_api_invalid")
    if task_ledger_row.get("call_status") != "candidate_radar_v05_local_batch_success":
        raise ReplayValidationError("canonical_source_task_ledger_status_invalid")
    processed_count = task_ledger_row.get("row_count")
    if type(processed_count) is not int or processed_count <= 0:
        raise ReplayValidationError("canonical_source_task_ledger_rows_invalid")
    if any(task_ledger_row.get(field) is not False for field in CANDIDATE_LEDGER_FALSE_FIELDS):
        raise ReplayValidationError("canonical_source_task_ledger_boundary_invalid")
    if any(
        type(task_ledger_row.get(field)) is not int or task_ledger_row.get(field) != 0
        for field in CANDIDATE_LEDGER_ZERO_FIELDS
    ):
        raise ReplayValidationError("canonical_source_task_ledger_boundary_invalid")
    if any(task_ledger_row.get(field) is not True for field in CANDIDATE_LEDGER_TRUE_FIELDS):
        raise ReplayValidationError("canonical_source_task_ledger_boundary_invalid")
    if (
        task_ledger_row.get("source_snapshot") != "payload.full_pool_candidates"
        or task_ledger_row.get("data_date") is not None
        or task_ledger_row.get("error_message_safe") != ""
        or not isinstance(task_ledger_row.get("local_fetched_at"), str)
        or not str(task_ledger_row.get("local_fetched_at") or "").strip()
    ):
        raise ReplayValidationError("canonical_source_task_ledger_invalid")
    if processed_count != len(source_pool_symbol_set):
        raise ReplayValidationError("canonical_source_processed_count_mismatch")
    request_params = task_ledger_row.get("request_params_safe")
    if not isinstance(request_params, Mapping):
        raise ReplayValidationError("canonical_source_task_ledger_request_invalid")
    expected_request_values = {
        "scan_mode": "v05_candidate_local_batch",
        "runtime_mode": "v05_candidate_local_batch",
        "local_worker_fallback_only": True,
        "operator_approved": True,
        "candidate_scope_hash_short": expected["source_scope_hash"][:12],
        "scope_hash_matches": True,
        "input_candidate_count": raw_pool_count,
        "normalized_candidate_count": processed_count,
        "processed_candidate_count": processed_count,
        "external_sources_allowed": False,
        "provider_backed_acceptance_done": False,
        "deepseek_model_execution_done": False,
        "production_full_pool_scan_done": False,
        "next_session_task_status": "success",
        "next_session_lineage_status": "same_packet_lineage_ready",
    }
    if any(request_params.get(key) != value for key, value in expected_request_values.items()):
        raise ReplayValidationError("canonical_source_task_ledger_request_invalid")
    local_pool_audit = candidate.get("local_candidate_pool_audit")
    if not isinstance(local_pool_audit, Mapping):
        raise ReplayValidationError("canonical_candidate_pool_audit_invalid")
    if (
        local_pool_audit.get("input_source") != task_ledger_row.get("source_snapshot")
        or local_pool_audit.get("input_candidate_count") != raw_pool_count
        or local_pool_audit.get("normalized_candidate_count") != processed_count
        or local_pool_audit.get("duplicate_candidate_count") != raw_pool_count - processed_count
        or any(local_pool_audit.get(field) != 0 for field in (
            "disabled_candidate_count",
            "invalid_candidate_count",
            "truncated_candidate_count",
            "skipped_candidate_count",
        ))
    ):
        raise ReplayValidationError("canonical_candidate_pool_audit_invalid")
    bucket_counts = candidate.get("candidate_radar_v05_bucket_counts")
    if not isinstance(bucket_counts, Mapping):
        raise ReplayValidationError("canonical_candidate_bucket_counts_invalid")
    for field in ("input_count", "processed_count", "top_count", "watch_count", "excluded_count"):
        if type(bucket_counts.get(field)) is not int or bucket_counts.get(field) < 0:
            raise ReplayValidationError("canonical_candidate_bucket_counts_invalid")
    if bucket_counts.get("input_count") != processed_count or bucket_counts.get("processed_count") != processed_count:
        raise ReplayValidationError("canonical_candidate_bucket_counts_mismatch")
    if sum(bucket_counts.get(field) for field in ("top_count", "watch_count", "excluded_count")) != processed_count:
        raise ReplayValidationError("canonical_candidate_bucket_counts_mismatch")
    bucket_rows: list[Mapping[str, Any]] = []
    for key, count_field in (
        ("candidate_radar_v05_top_rows", "top_count"),
        ("candidate_radar_v05_watch_rows", "watch_count"),
        ("candidate_radar_v05_excluded_rows", "excluded_count"),
    ):
        rows = candidate.get(key)
        if not isinstance(rows, list) or len(rows) != bucket_counts.get(count_field):
            raise ReplayValidationError("canonical_candidate_bucket_rows_mismatch")
        if any(not isinstance(row, Mapping) for row in rows):
            raise ReplayValidationError("canonical_candidate_bucket_rows_mismatch")
        bucket_rows.extend(rows)
    try:
        bucket_symbol_set = {_normalize_symbol(row.get("symbol")) for row in bucket_rows}
    except ReplayValidationError as exc:
        raise ReplayValidationError("canonical_candidate_bucket_rows_mismatch") from exc
    if len(bucket_rows) != processed_count or bucket_symbol_set != source_pool_symbol_set:
        raise ReplayValidationError("canonical_candidate_bucket_rows_mismatch")
    runtime = candidate.get("candidate_radar_v05_runtime")
    if not isinstance(runtime, Mapping) or runtime.get("status") != "worker_v04_local_batch_runtime_success":
        raise ReplayValidationError("canonical_candidate_runtime_invalid")
    if (
        type(runtime.get("pool_count")) is not int
        or runtime.get("pool_count") != processed_count
        or type(runtime.get("processed_count")) is not int
        or runtime.get("processed_count") != processed_count
    ):
        raise ReplayValidationError("canonical_candidate_runtime_count_mismatch")
    manifest = runtime.get("manifest")
    if not isinstance(manifest, Mapping):
        raise ReplayValidationError("canonical_candidate_runtime_manifest_invalid")
    expected_manifest_keys = {
        "schema_version",
        "status",
        "task_id",
        "runtime_scope_hash_short",
        "pool_count",
        "processed_count",
        "chunk_size",
        "chunk_count",
        "stage_count",
        "failed_symbol",
        "result_checksum",
        "append_only_event_count",
        "local_runtime_not_full_market_claim",
        "local_runtime_is_not_celery_redis_production",
        "contains_secret",
        "external_calls_triggered",
        "manifest_sha256",
    }
    if set(manifest) != expected_manifest_keys:
        raise ReplayValidationError("canonical_candidate_runtime_manifest_invalid")
    stage_rows = runtime.get("stage_rows")
    if not isinstance(stage_rows, list) or not stage_rows or any(not isinstance(row, Mapping) for row in stage_rows):
        raise ReplayValidationError("canonical_candidate_runtime_manifest_invalid")
    if (
        manifest.get("schema_version") != "worker_v04_local_batch_runtime_manifest.v1"
        or manifest.get("status") != "worker_v04_local_batch_runtime_success"
        or manifest.get("runtime_scope_hash_short") != expected["source_scope_hash"][:12]
        or manifest.get("pool_count") != processed_count
        or manifest.get("processed_count") != processed_count
        or manifest.get("failed_symbol") != ""
        or manifest.get("stage_count") != len(stage_rows)
        or manifest.get("append_only_event_count") != len(stage_rows)
        or runtime.get("append_only_event_count") != len(stage_rows)
        or runtime.get("chunk_count") != len(stage_rows)
        or manifest.get("chunk_count") != len(stage_rows)
        or request_params.get("chunk_count") != len(stage_rows)
        or request_params.get("stage_count") != len(stage_rows)
        or bucket_counts.get("chunk_count") != len(stage_rows)
        or bucket_counts.get("stage_count") != len(stage_rows)
        or manifest.get("local_runtime_not_full_market_claim") is not True
        or manifest.get("local_runtime_is_not_celery_redis_production") is not True
        or manifest.get("contains_secret") is not False
        or manifest.get("external_calls_triggered") is not False
    ):
        raise ReplayValidationError("canonical_candidate_runtime_manifest_invalid")
    if any(
        row.get("status") != "success"
        or row.get("append_only_write_done") is not True
        or type(row.get("processed_count")) is not int
        or row.get("processed_count") <= 0
        or not isinstance(row.get("event_sha256"), str)
        or not SOURCE_HASH_PATTERN.fullmatch(str(row.get("event_sha256")))
        for row in stage_rows
    ) or sum(int(row.get("processed_count") or 0) for row in stage_rows) != processed_count:
        raise ReplayValidationError("canonical_candidate_runtime_manifest_invalid")
    manifest_sha256 = manifest.get("manifest_sha256")
    manifest_hash_material = {
        str(key): value
        for key, value in manifest.items()
        if key not in {"status", "manifest_sha256"}
    }
    if not isinstance(manifest_sha256, str) or _sha256(manifest_hash_material) != manifest_sha256:
        raise ReplayValidationError("canonical_candidate_runtime_manifest_invalid")
    if (
        task_ledger_row.get("runtime_manifest_path") != runtime.get("manifest_path")
        or task_ledger_row.get("runtime_event_log_path") != runtime.get("event_log_path")
        or task_ledger_row.get("runtime_manifest_sha256") != manifest_sha256
    ):
        raise ReplayValidationError("canonical_source_task_runtime_binding_invalid")
    worker_task_id = str(manifest.get("task_id") or "")
    if not SOURCE_TASK_ID_PATTERN.fullmatch(worker_task_id):
        raise ReplayValidationError("canonical_candidate_runtime_manifest_invalid")
    runtime_dir_label = f"v04_acceptance/{expected['source_scope_hash']}/worker_runtime"
    if runtime.get("runtime_dir") != runtime_dir_label:
        raise ReplayValidationError("canonical_candidate_runtime_artifact_path_invalid")
    manifest_path = _canonical_runtime_artifact_path(
        runtime.get("manifest_path"),
        scope_hash=expected["source_scope_hash"],
        expected_name=f"manifest_{worker_task_id}.json",
    )
    event_log_path = _canonical_runtime_artifact_path(
        runtime.get("event_log_path"),
        scope_hash=expected["source_scope_hash"],
        expected_name="events.jsonl",
    )
    manifest_file_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    event_log_file_sha256 = hashlib.sha256(event_log_path.read_bytes()).hexdigest()
    if (
        runtime.get("manifest_file_sha256") != manifest_file_sha256
        or runtime.get("event_log_file_sha256") != event_log_file_sha256
        or task_ledger_row.get("runtime_manifest_file_sha256") != manifest_file_sha256
        or task_ledger_row.get("runtime_event_log_file_sha256") != event_log_file_sha256
    ):
        raise ReplayValidationError("canonical_candidate_runtime_artifact_digest_invalid")
    try:
        disk_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReplayValidationError("canonical_candidate_runtime_manifest_file_invalid") from exc
    if not isinstance(disk_manifest, Mapping) or _canonical_json(disk_manifest) != _canonical_json(manifest):
        raise ReplayValidationError("canonical_candidate_runtime_manifest_file_mismatch")
    event_rows = _read_runtime_event_rows(event_log_path)
    if len(event_rows) < len(stage_rows):
        raise ReplayValidationError("canonical_candidate_runtime_event_log_invalid")
    current_event_rows = event_rows[-len(stage_rows) :]
    for stage_row, event_row in zip(stage_rows, current_event_rows, strict=True):
        expected_event_keys = {
            "schema_version",
            "task_id",
            "chunk_index",
            "chunk_size",
            "processed_count",
            "stage_status",
            "failed_symbol",
            "runtime_scope_hash_short",
            "contains_secret",
            "external_calls_triggered",
            "tushare_called",
            "deepseek_called",
            "github_called",
            "redis_pinged",
            "celery_started",
            "does_not_execute_trades",
            "does_not_modify_strategy_action",
            "event_sha256",
        }
        event_hash_material = {
            str(key): value
            for key, value in event_row.items()
            if key != "event_sha256"
        }
        if (
            set(event_row) != expected_event_keys
            or event_row.get("schema_version") != "worker_v04_local_batch_event.v1"
            or event_row.get("task_id") != worker_task_id
            or event_row.get("chunk_index") != stage_row.get("chunk_index")
            or event_row.get("chunk_size") != stage_row.get("chunk_size")
            or event_row.get("processed_count") != stage_row.get("processed_count")
            or event_row.get("stage_status") != stage_row.get("status")
            or event_row.get("failed_symbol") != ""
            or event_row.get("runtime_scope_hash_short") != expected["source_scope_hash"][:12]
            or event_row.get("event_sha256") != stage_row.get("event_sha256")
            or _sha256(event_hash_material) != event_row.get("event_sha256")
            or event_row.get("contains_secret") is not False
            or event_row.get("external_calls_triggered") is not False
            or event_row.get("tushare_called") is not False
            or event_row.get("deepseek_called") is not False
            or event_row.get("github_called") is not False
            or event_row.get("redis_pinged") is not False
            or event_row.get("celery_started") is not False
            or event_row.get("does_not_execute_trades") is not True
            or event_row.get("does_not_modify_strategy_action") is not True
        ):
            raise ReplayValidationError("canonical_candidate_runtime_event_log_mismatch")
    candidate_ledger = candidate.get("call_ledger")
    if not isinstance(candidate_ledger, list) or len(candidate_ledger) != 1 or not isinstance(candidate_ledger[0], Mapping):
        raise ReplayValidationError("canonical_candidate_ledger_invalid")
    candidate_ledger_row = candidate_ledger[0]
    _validate_exact_safety_boundary(candidate_ledger_row, code="canonical_candidate_ledger_boundary_invalid")
    candidate_request = candidate_ledger_row.get("request_params_safe")
    if not isinstance(candidate_request, Mapping):
        raise ReplayValidationError("canonical_candidate_ledger_invalid")
    task_core = {
        key: value
        for key, value in task_ledger_row.items()
        if key != "request_params_safe"
    }
    candidate_core = {
        key: value
        for key, value in candidate_ledger_row.items()
        if key != "request_params_safe"
    }
    if _canonical_json(task_core) != _canonical_json(candidate_core):
        raise ReplayValidationError("canonical_candidate_task_ledger_mismatch")
    expected_candidate_request = {
        key: value
        for key, value in request_params.items()
        if key not in {"next_session_task_status", "next_session_lineage_status"}
    }
    if _canonical_json(candidate_request) != _canonical_json(expected_candidate_request):
        raise ReplayValidationError("canonical_candidate_task_ledger_mismatch")
    next_ledger = next_session.get("call_ledger")
    if not isinstance(next_ledger, list) or len(next_ledger) != 1 or not isinstance(next_ledger[0], Mapping):
        raise ReplayValidationError("canonical_next_session_ledger_invalid")
    next_ledger_row = next_ledger[0]
    _validate_exact_safety_boundary(next_ledger_row, code="canonical_next_session_ledger_boundary_invalid")
    if next_ledger_row.get("does_not_modify_operation_zones") is not True:
        raise ReplayValidationError("canonical_next_session_ledger_boundary_invalid")
    if (
        next_ledger_row.get("api") != "local_next_session_candidate_v05_lineage"
        or next_ledger_row.get("source_snapshot") != CANDIDATE_PACKET_KEY
        or next_ledger_row.get("call_status") != "candidate_radar_v05_lineage_ready"
        or next_ledger_row.get("row_count") != 1
        or _normalize_source_data_date(next_ledger_row.get("data_date")) != expected["source_data_date"]
        or next_ledger_row.get("error_message_safe") != ""
    ):
        raise ReplayValidationError("canonical_next_session_ledger_invalid")
    next_request = next_ledger_row.get("request_params_safe")
    expected_next_request = {
        "source_task_id": expected["source_task_id"],
        "result_version": expected["source_result_version"],
        "candidate_scope_hash": expected["source_scope_hash"],
        "symbol": expected["source_symbol"],
        "source_packet_key": CANDIDATE_PACKET_KEY,
        "target_packet_key": NEXT_SESSION_PACKET_KEY,
    }
    if not isinstance(next_request, Mapping):
        raise ReplayValidationError("canonical_next_session_ledger_invalid")
    next_request_projection = {str(key): value for key, value in next_request.items() if key != "data_date"}
    if (
        _canonical_json(next_request_projection) != _canonical_json(expected_next_request)
        or _normalize_source_data_date(next_request.get("data_date")) != expected["source_data_date"]
    ):
        raise ReplayValidationError("canonical_next_session_ledger_invalid")
    coverage = candidate.get("candidate_radar_v05_coverage")
    if not isinstance(coverage, Mapping):
        raise ReplayValidationError("canonical_candidate_coverage_invalid")
    if coverage.get("signal_retained_coverage") != "local_supplied_pool_rows_scored_and_bucketed":
        raise ReplayValidationError("canonical_candidate_coverage_invalid")
    if coverage.get("gap_status") != "provider_deepseek_celery_redis_browser_release_evidence_pending":
        raise ReplayValidationError("canonical_candidate_coverage_invalid")
    derived_result_version = "candidate-v05-" + hashlib.sha256(
        json.dumps(
            {
                "scope_hash": expected["source_scope_hash"],
                "task_id": expected["source_task_id"],
                "processed": processed_count,
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:16]
    if derived_result_version != expected["source_result_version"]:
        raise ReplayValidationError("canonical_source_result_version_not_task_derived")
    return expected


_RESULT_HASH_FIELDS = (
    "schema_version",
    "status",
    "mode",
    "scenario",
    "max_frames",
    "source_result_version",
    "source_scope_hash",
    "source_data_date",
    "source_lineage",
    "scope_hash",
    "replay",
    "virtual_fill_count",
    "research_event_count",
    "virtual_research_events",
    "allowed_research_events",
    "caller_supplied_export_compatibility_verified",
    "external_qmt_integration_verified",
    "paper_trading_sandbox_ready",
    "safety_boundary",
    *_boundary_flags().keys(),
)


def _result_hash_material(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {field: packet.get(field) for field in _RESULT_HASH_FIELDS}


def _result_mac_material(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "result": _result_hash_material(packet),
        "packet_key": packet.get("packet_key"),
        "generated_at": packet.get("generated_at"),
        "task_id": packet.get("task_id"),
        "task_status": packet.get("task_status"),
        "call_ledger": packet.get("call_ledger"),
        "warnings": packet.get("warnings"),
        "notices": packet.get("notices"),
    }


def _result_call_ledger_integrity(packet: Mapping[str, Any]) -> bool:
    ledger = packet.get("call_ledger")
    if not isinstance(ledger, list) or len(ledger) != 1 or not isinstance(ledger[0], Mapping):
        return False
    row = ledger[0]
    expected_keys = {
        "api",
        "source",
        "request_params_safe",
        "row_count",
        "task_id",
        "local_fetched_at",
        "call_status",
        "error_message_safe",
        "external",
        *_boundary_flags().keys(),
    }
    replay = packet.get("replay")
    return set(row) == expected_keys and row.get("api") == "local_qmt_readonly_decimal_replay" and row.get(
        "source"
    ) == "caller_supplied_sanitized_export_or_bound_local_lineage" and row.get("request_params_safe") == {
        "scope_hash": packet.get("scope_hash"),
        "caller_supplied_export_only": True,
        "external_qmt_connection_allowed": False,
    } and row.get("row_count") == (replay.get("event_count") if isinstance(replay, Mapping) else None) and row.get(
        "task_id"
    ) == packet.get("task_id") and isinstance(row.get("local_fetched_at"), str) and bool(
        str(row.get("local_fetched_at")).strip()
    ) and row.get("call_status") == "local_decimal_replay_completed" and row.get(
        "error_message_safe"
    ) == "" and row.get("external") is False and all(
        row.get(key) == value for key, value in _boundary_flags().items()
    )


def _result_packet_integrity(packet: Any) -> tuple[bool, str]:
    if not isinstance(packet, Mapping):
        return False, "result_packet_missing"
    if packet.get("packet_key") != CURRENT_PACKET_KEY:
        return False, "result_packet_key_invalid"
    task_id = packet.get("task_id")
    if not isinstance(task_id, str) or not SOURCE_TASK_ID_PATTERN.fullmatch(task_id):
        return False, "result_task_id_invalid"
    if packet.get("task_status") != "success":
        return False, "result_task_status_invalid"
    if not isinstance(packet.get("generated_at"), str):
        return False, "result_generated_at_invalid"
    if packet.get("schema_version") != RESULT_SCHEMA_VERSION:
        return False, "result_schema_invalid"
    if packet.get("status") not in {
        "local_export_contract_and_replay_verified",
        "local_scope_replay_verified_export_pending",
    }:
        return False, "result_status_invalid"
    if packet.get("mode") != "local_research_replay":
        return False, "result_mode_invalid"
    if packet.get("scenario") not in ALLOWED_SCENARIOS or packet.get("max_frames") not in ALLOWED_MAX_FRAMES:
        return False, "result_scope_invalid"
    if not isinstance(packet.get("source_result_version"), str) or not SOURCE_VERSION_PATTERN.fullmatch(
        str(packet.get("source_result_version"))
    ):
        return False, "result_version_invalid"
    if not isinstance(packet.get("source_scope_hash"), str) or not SOURCE_HASH_PATTERN.fullmatch(
        str(packet.get("source_scope_hash"))
    ):
        return False, "result_source_scope_invalid"
    if not isinstance(packet.get("scope_hash"), str) or not SOURCE_HASH_PATTERN.fullmatch(str(packet.get("scope_hash"))):
        return False, "result_scope_hash_invalid"
    try:
        source_data_date = _normalize_source_data_date(packet.get("source_data_date"))
        source_symbol = _normalize_symbol(packet.get("source_lineage", {}).get("source_symbol"))
    except (ReplayValidationError, AttributeError):
        return False, "result_lineage_invalid"
    lineage = packet.get("source_lineage")
    if not isinstance(lineage, Mapping):
        return False, "result_lineage_invalid"
    source_task_id = lineage.get("source_task_id")
    if not isinstance(source_task_id, str) or not SOURCE_TASK_ID_PATTERN.fullmatch(source_task_id):
        return False, "result_lineage_task_invalid"
    expected_lineage = {
        "source_symbol": source_symbol,
        "source_task_id": source_task_id,
        "source_result_version": packet.get("source_result_version"),
        "source_scope_hash": packet.get("source_scope_hash"),
        "source_data_date": source_data_date,
    }
    if dict(lineage) != expected_lineage:
        return False, "result_lineage_mismatch"
    if packet.get("source_data_date") != source_data_date:
        return False, "result_data_date_not_canonical"
    boundary = _boundary_flags()
    if packet.get("safety_boundary") != boundary or any(packet.get(key) != value for key, value in boundary.items()):
        return False, "result_boundary_invalid"
    replay = packet.get("replay")
    events = packet.get("virtual_research_events")
    if not isinstance(replay, Mapping) or not isinstance(events, list):
        return False, "result_events_invalid"
    if replay.get("research_events") != events or replay.get("virtual_research_events") != events:
        return False, "result_events_mismatch"
    if packet.get("research_event_count") != len(events) or len(events) > int(packet.get("max_frames") or 0):
        return False, "result_event_count_invalid"
    if not all(isinstance(event, Mapping) for event in events):
        return False, "result_event_row_invalid"
    expected_sequences = [0] if len(events) == 1 and events[0].get("seq") == 0 else list(range(1, len(events) + 1))
    for index, event in enumerate(events):
        if event.get("seq") != expected_sequences[index] or event.get("event") not in {"observe", "watch", "excluded"}:
            return False, "result_event_contract_invalid"
        symbol = event.get("symbol")
        if symbol is not None and (not isinstance(symbol, str) or not SYMBOL_PATTERN.fullmatch(symbol)):
            return False, "result_event_symbol_invalid"
        if not isinstance(event.get("reason"), str) or not str(event.get("reason")).strip():
            return False, "result_event_reason_invalid"
    if packet.get("allowed_research_events") != ["observe", "watch", "excluded"]:
        return False, "result_allowed_events_invalid"
    if packet.get("warnings") != [] or not isinstance(packet.get("notices"), list):
        return False, "result_message_contract_invalid"
    if not _result_call_ledger_integrity(packet):
        return False, "result_call_ledger_invalid"
    result_hash = packet.get("result_hash")
    if not isinstance(result_hash, str) or not SOURCE_HASH_PATTERN.fullmatch(result_hash):
        return False, "result_hash_invalid"
    if _sha256(_result_hash_material(packet)) != result_hash:
        return False, "result_hash_mismatch"
    integrity_key = _read_result_integrity_key()
    if integrity_key is None:
        return False, "result_integrity_key_missing_or_invalid"
    result_mac = packet.get("result_mac")
    if not isinstance(result_mac, str) or not SOURCE_HASH_PATTERN.fullmatch(result_mac):
        return False, "result_mac_invalid"
    expected_mac = _result_mac(integrity_key, _result_mac_material(packet))
    if not hmac.compare_digest(result_mac, expected_mac):
        return False, "result_mac_mismatch"
    return True, "result_integrity_validated"


def _without_accessor_metadata(task: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(task)
    row.pop("storage_source", None)
    return row


_HISTORY_PROJECTION_METADATA_FIELDS = frozenset(
    {
        "storage_source",
        "historical_evidence",
        "current_actionable",
        "history_integrity_valid",
        "history_integrity_error",
        "history_id",
        "history_updated_at",
        "history_payload_digest",
        "history_actual_payload_digest",
        "history_lookup_query_count",
        "history_task_type_binding_source",
    }
)


def _history_payload_projection(history: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in history.items()
        if key not in _HISTORY_PROJECTION_METADATA_FIELDS
    }


def _read_persisted_result_task_and_history(task_id: str) -> tuple[Any, Any, str]:
    if not SQLITE_META_PATH.exists():
        return None, None, "result_task_sqlite_missing"
    try:
        store = SQLiteMetaStore(SQLITE_META_PATH, read_only=True)
        persisted = store.read_task_status(task_id)
        history = store.read_latest_task_status_history(task_id)
    except Exception:
        return None, None, "result_task_sqlite_read_failed"
    if not isinstance(persisted, Mapping):
        return None, None, "result_task_persisted_missing"
    if not isinstance(history, Mapping):
        return dict(persisted), None, "result_task_final_history_missing"
    if history.get("history_integrity_valid") is not True or history.get("history_integrity_error") != "":
        return dict(persisted), dict(history), "result_task_final_history_integrity_invalid"
    if history.get("task_id") != task_id or history.get("task_type") != TASK_TYPE:
        return dict(persisted), dict(history), "result_task_final_history_identity_invalid"
    return dict(persisted), dict(history), "result_task_sqlite_history_validated"


def _result_task_binding(packet: Any) -> tuple[bool, str]:
    if not isinstance(packet, Mapping):
        return False, "result_task_packet_missing"
    task_id = packet.get("task_id")
    if not isinstance(task_id, str) or not SOURCE_TASK_ID_PATTERN.fullmatch(task_id):
        return False, "result_task_id_invalid"

    accessor = task_service.read_task_status(task_id)
    if not isinstance(accessor, Mapping):
        return False, "result_task_accessor_missing"
    persisted, final_history, read_status = _read_persisted_result_task_and_history(task_id)
    if not isinstance(persisted, Mapping):
        return False, read_status
    if not isinstance(final_history, Mapping):
        return False, read_status
    if read_status != "result_task_sqlite_history_validated":
        return False, read_status
    accessor_core = _without_accessor_metadata(accessor)
    persisted_core = _without_accessor_metadata(persisted)
    history_core = _without_accessor_metadata(_history_payload_projection(final_history))
    if accessor_core != persisted_core:
        return False, "result_task_accessor_sqlite_mismatch"
    if history_core != persisted_core:
        return False, "result_task_final_history_mismatch"

    if persisted.get("task_id") != task_id or persisted.get("task_type") != TASK_TYPE:
        return False, "result_task_identity_mismatch"
    if (
        persisted.get("status") != "success"
        or type(persisted.get("progress")) is not float
        or persisted.get("progress") != 1.0
    ):
        return False, "result_task_status_invalid"
    if persisted.get("current_step") != TASK_COMPLETED_STEP:
        return False, "result_task_step_invalid"
    if persisted.get("output_packet_key") != CURRENT_PACKET_KEY:
        return False, "result_task_output_invalid"
    if persisted.get("error_message_safe") != "":
        return False, "result_task_error_not_empty"
    if not isinstance(persisted.get("finished_at"), str) or not str(persisted.get("finished_at") or "").strip():
        return False, "result_task_finished_at_invalid"

    payload = persisted.get("payload_safe")
    lineage = packet.get("source_lineage")
    if not isinstance(payload, Mapping) or not isinstance(lineage, Mapping):
        return False, "result_task_payload_invalid"
    replay = packet.get("replay")
    if not isinstance(replay, Mapping):
        return False, "result_task_replay_missing"
    expected_payload = {
        "request_schema_version": REQUEST_SCHEMA_VERSION,
        "approved_by_user": True,
        "mode": packet.get("mode"),
        "scenario": packet.get("scenario"),
        "max_frames": packet.get("max_frames"),
        "source_result_version": packet.get("source_result_version"),
        "source_scope_hash": packet.get("source_scope_hash"),
        "source_data_date": packet.get("source_data_date"),
        "source_symbol": lineage.get("source_symbol"),
        "source_task_id": lineage.get("source_task_id"),
        "scope_hash": packet.get("scope_hash"),
        "position_count": replay.get("initial_position_count"),
        "event_count": replay.get("event_count"),
        "raw_snapshot_stored_in_task_audit": False,
        "external_qmt_connection_allowed": False,
    }
    if set(payload) != set(expected_payload) or any(
        payload.get(key) != value for key, value in expected_payload.items()
    ):
        return False, "result_task_payload_mismatch"
    if any(
        type(payload.get(key)) is not int
        or type(replay.get(replay_key)) is not int
        or payload.get(key) < 0
        for key, replay_key in (
            ("position_count", "initial_position_count"),
            ("event_count", "event_count"),
        )
    ):
        return False, "result_task_payload_mismatch"
    expected_input_hash = hashlib.sha256(
        json.dumps(
            {"task_type": TASK_TYPE, "payload_safe": dict(payload)},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:16]
    if persisted.get("input_hash") != expected_input_hash:
        return False, "result_task_input_hash_invalid"

    if persisted.get("call_ledger") != packet.get("call_ledger"):
        return False, "result_task_call_ledger_mismatch"
    if any(
        (
            persisted.get("external_calls_triggered") is not False,
            persisted.get("deepseek_called") is not False,
            persisted.get("tushare_called") is not False,
            persisted.get("github_called") is not False,
            persisted.get("does_not_execute_trades") is not True,
            persisted.get("does_not_modify_strategy_action") is not True,
        )
    ):
        return False, "result_task_boundary_invalid"

    status_history = persisted.get("status_history")
    task_log = persisted.get("task_log")
    if (
        not isinstance(status_history, list)
        or len(status_history) != 3
        or any(not isinstance(row, Mapping) for row in status_history)
    ):
        return False, "result_task_status_history_invalid"
    if (
        not isinstance(task_log, list)
        or len(task_log) != 3
        or any(not isinstance(row, Mapping) for row in task_log)
    ):
        return False, "result_task_log_invalid"
    expected_lifecycle = (
        (
            "pending",
            0.0,
            "qmt_local_decimal_replay_queued_no_external_call",
            "local task record created without external work",
        ),
        (
            "running",
            0.5,
            "qmt_local_decimal_replay_running_no_external_call",
            "local task status updated",
        ),
        (
            "success",
            1.0,
            TASK_COMPLETED_STEP,
            "qmt_local_replay_completed_without_external_qmt_or_trade_execution",
        ),
    )
    for index, (expected_status, expected_progress, expected_step, expected_message) in enumerate(expected_lifecycle):
        history_row = status_history[index]
        log_row = task_log[index]
        if set(history_row) != {"status", "progress", "current_step", "at"} or any(
            (
                history_row.get("status") != expected_status,
                type(history_row.get("progress")) is not float,
                history_row.get("progress") != expected_progress,
                history_row.get("current_step") != expected_step,
                not isinstance(history_row.get("at"), str),
                not str(history_row.get("at") or "").strip(),
            )
        ):
            return False, "result_task_status_history_invalid"
        if set(log_row) != {
            "event",
            "status",
            "current_step",
            "message_safe",
            "at",
            "external",
            "external_calls_triggered",
            "contains_secret",
            "stack_trace_included",
        } or any(
            (
                log_row.get("event") != ("task_created" if index == 0 else "task_status_updated"),
                log_row.get("status") != expected_status,
                log_row.get("current_step") != expected_step,
                log_row.get("message_safe") != expected_message,
                log_row.get("at") != history_row.get("at"),
                log_row.get("external") is not False,
                log_row.get("external_calls_triggered") is not False,
                log_row.get("contains_secret") is not False,
                log_row.get("stack_trace_included") is not False,
            )
        ):
            return False, "result_task_log_invalid"
    lifecycle_times = [str(row.get("at")) for row in status_history]
    try:
        parsed_times = [_dt.datetime.fromisoformat(value) for value in lifecycle_times]
    except (TypeError, ValueError):
        return False, "result_task_lifecycle_time_invalid"
    if parsed_times != sorted(parsed_times):
        return False, "result_task_lifecycle_time_invalid"
    if any(
        (
            persisted.get("created_at") != lifecycle_times[0],
            persisted.get("started_at") != lifecycle_times[1],
            persisted.get("finished_at") != lifecycle_times[2],
        )
    ):
        return False, "result_task_lifecycle_time_invalid"
    return True, "result_task_sqlite_binding_validated"


def _current_source_lineage_binding(packet: Any) -> tuple[bool, str]:
    if not isinstance(packet, Mapping):
        return False, "current_source_result_missing"
    lineage = packet.get("source_lineage")
    if not isinstance(lineage, Mapping):
        return False, "current_source_lineage_missing"
    try:
        _validate_canonical_source_binding(
            {
                "source_symbol": lineage.get("source_symbol"),
                "source_task_id": lineage.get("source_task_id"),
                "source_result_version": packet.get("source_result_version"),
                "source_scope_hash": packet.get("source_scope_hash"),
                "source_data_date": packet.get("source_data_date"),
            }
        )
    except ReplayValidationError as exc:
        return False, str(exc) or "current_source_lineage_not_current"
    except Exception:
        return False, "current_source_lineage_read_failed"
    return True, "current_source_lineage_validated"


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
            "source_data_date": None,
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
        _validate_canonical_source_binding(normalized)
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
        "source_data_date": normalized["source_data_date"],
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
        integrity_key = _load_or_create_result_integrity_key()
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
            "warnings": [],
            "notices": [
                "virtual_fill 仅为 Decimal 本地算术证据，不是委托、成交、持仓变更或 QMT 外部集成证据。",
                "外部 QMT read-only 连接、broker/session/account query 和真实交易均未实现。",
            ],
        }
        packet["result_mac"] = _result_mac(integrity_key, _result_mac_material(packet))
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
        current_step=TASK_COMPLETED_STEP,
        output_packet_key=CURRENT_PACKET_KEY,
        call_ledger=packet["call_ledger"],
        warning="qmt_local_replay_completed_without_external_qmt_or_trade_execution",
    )
    return packet


def read_qmt_replay_cache() -> dict[str, Any]:
    current, current_source = _read_packet_no_init(CURRENT_PACKET_KEY)
    last_good, last_good_source = _read_packet_no_init(LAST_GOOD_PACKET_KEY)
    current_ok, current_integrity = _result_packet_integrity(current)
    last_good_ok, last_good_integrity = _result_packet_integrity(last_good)
    current_task_ok, current_task_binding = (
        _result_task_binding(current) if current_ok else (False, "result_task_not_checked_invalid_result")
    )
    last_good_task_ok, last_good_task_binding = (
        _result_task_binding(last_good) if last_good_ok else (False, "result_task_not_checked_invalid_result")
    )
    current_result_ok = current_ok and current_task_ok
    last_good_result_ok = last_good_ok and last_good_task_ok
    current_present = current_source == "packet_present"
    selected = current if current_result_ok else last_good if not current_present and last_good_result_ok else None
    ledger = _local_call_ledger(call_status="cache_read_no_external_call")
    if not isinstance(selected, Mapping):
        invalid_current = current_present and not current_result_ok
        invalid_last_good = (
            not current_present
            and last_good_source == "packet_present"
            and not last_good_result_ok
        )
        blocked_available_result = invalid_current or invalid_last_good
        if invalid_current:
            blocked_status = current_integrity if not current_ok else current_task_binding
            blocked_task_status = current_task_binding if current_ok else "result_task_not_checked_invalid_result"
        elif invalid_last_good:
            blocked_status = last_good_integrity if not last_good_ok else last_good_task_binding
            blocked_task_status = (
                last_good_task_binding if last_good_ok else "result_task_not_checked_invalid_result"
            )
        else:
            blocked_status = "result_packet_missing"
            blocked_task_status = "result_task_not_checked_invalid_result"
        return {
            "packet_key": CACHE_PACKET_KEY,
            "schema_version": CACHE_SCHEMA_VERSION,
            "status": "latest_attempt_blocked" if blocked_available_result else "cache_missing",
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
                "source_data_date": None,
            },
            "virtual_research_events": [],
            "result_integrity_validated": False,
            "result_integrity_status": blocked_status,
            "result_task_binding_validated": False,
            "result_task_binding_status": blocked_task_status,
            "lineage_validation": {
                "schema_version": "qmt_readonly_source_lineage_validation.v1",
                "status": "blocked_invalid_result" if blocked_available_result else "waiting_for_first_result",
                "passed": False,
            },
            "external_qmt_integration_verified": False,
            "paper_trading_sandbox_ready": False,
            "safety_boundary": _boundary_flags(),
            **_boundary_flags(),
            "call_ledger": ledger,
            "warnings": (
                [
                    f"qmt_replay_{'current' if invalid_current else 'last_good'}_result_blocked:{blocked_status}"
                ]
                if blocked_available_result
                else []
            ),
            "notices": ["尚无本地 QMT replay 缓存；GET 未创建目录、数据库、任务或外部连接。"],
        }

    packet = dict(selected)
    selected_status = str(packet.get("status") or "")
    selected_is_current = current_result_ok
    selected_task_binding = current_task_binding if selected_is_current else last_good_task_binding
    source_current, source_lineage_status = _current_source_lineage_binding(packet)
    cache_status = (
        "historical_isolated_replay"
        if not source_current
        else "ready_cache_replay"
        if selected_is_current
        else "degraded_last_good_replay"
    )
    packet.update(
        {
            "packet_key": CACHE_PACKET_KEY,
            "schema_version": CACHE_SCHEMA_VERSION,
            "status": cache_status,
            "selected_result_status": selected_status,
            "mode": "cache_only",
            "cache_only": True,
            "read_only": True,
            "cache_source": "sqlite_meta_read_only",
            "current_packet_source": current_source,
            "last_good_packet_source": last_good_source,
            "current_result_summary": _packet_summary(current),
            "last_good_result_summary": _packet_summary(last_good),
            "result_integrity_validated": True,
            "result_integrity_status": current_integrity if selected_is_current else last_good_integrity,
            "result_task_binding_validated": True,
            "result_task_binding_status": selected_task_binding,
            "lineage_validation": {
                "schema_version": "qmt_readonly_source_lineage_validation.v1",
                "status": "source_result_current_and_validated" if source_current else "historical_source_lineage_isolated",
                "passed": source_current,
            },
            **_boundary_flags(),
            "call_ledger": ledger,
            "warnings": [] if source_current else [f"qmt_replay_source_historical_isolated:{source_lineage_status}"],
            "notices": [
                "源 Candidate/Next 已变更；该 replay 仅作历史隔离研究证据，不是当前 ready 结果。"
                if not source_current
                else "GET 仅回放 SQLite 中的本地 current/last-good 结果，不创建任务、不连接 QMT、不执行真实交易。"
            ],
        }
    )
    return packet
