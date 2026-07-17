from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import stat
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from numbers import Number
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
TASK_TYPE = "refresh_margin_etf_local_packets"
TASK_ROUTE = "POST /api/market/margin-etf-local-refresh"
TASK_OUTPUT_PACKET_KEY = "command_center_margin_etf_refresh_receipt"
SOURCE_IDENTITY = "margin_etf_local_packet_replay.v1"
SOURCE_PROJECTION_SCHEMA_VERSION = "margin_etf_source_projection.v1"
REQUESTED_PACKET_KEYS = ["command_center_etf_packet", "command_center_margin_packet"]
FALSE_SAFETY_FIELDS = (
    "external",
    "external_calls_triggered",
    "provider_or_model_calls",
    "provider_called",
    "model_called",
    "worker_called",
    "tushare_called",
    "deepseek_called",
    "github_called",
    "trade_called",
    "trading_called",
    "broker_called",
    "order_called",
    "real_trading_enabled",
    "contains_secret",
)
TRUE_SAFETY_FIELDS = ("does_not_execute_trades", "does_not_modify_strategy_action")
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_TARGET_RE = re.compile(r"^\d{6}\.(?:SH|SZ|BJ)$")
_ETF_RE = re.compile(r"^\d{6}\.(?:SH|SZ)$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_FUTURE_SKEW_SECONDS = 120

PRODUCER_RECEIPT_SCHEMA_VERSION = "margin_etf_trusted_producer_receipt.v1"
PRODUCER_EVENT_SCHEMA_VERSION = "margin_etf_trusted_producer_event.v1"
PRODUCER_STATE_SCHEMA_VERSION = "margin_etf_trusted_producer_state.v1"
PRODUCER_JOURNAL_NAME = "margin_etf_trusted_producer.sqlite"
_TRUST_DIRECTORY_NAME = ".margin_etf_trusted_producer"
_TRUST_KEY_NAME = "producer.bin"
_TRUST_STATE_NAME = "producer.state"
_TRUST_KEY_BYTES = 32
_EVENT_TABLE = "margin_etf_trusted_producer_events"
_EVENT_FIELDS = (
    "sequence_no",
    "event_id",
    "schema_version",
    "semantic_digest",
    "issued_at",
    "task_sha256",
    "scope_sha256",
    "ledger_sha256",
    "source_projection_sha256",
    "projection_sha256",
    "binding_sha256",
    "previous_event_mac",
    "event_mac",
)
_RECEIPT_FIELDS = (
    "schema_version",
    "event_id",
    "sequence_no",
    "issued_at",
    "semantic_digest",
    "event_mac",
    "task_sha256",
    "scope_sha256",
    "ledger_sha256",
    "source_projection_sha256",
    "projection_sha256",
    "binding_sha256",
    "verified",
    "state_continuity_verified",
)
_EVIDENCE_DIGEST_FIELDS = (
    "task_sha256",
    "scope_sha256",
    "ledger_sha256",
    "source_projection_sha256",
    "projection_sha256",
    "binding_sha256",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def now_shanghai() -> dt.datetime:
    return dt.datetime.now(SHANGHAI)


def now_shanghai_iso() -> str:
    return now_shanghai().replace(microsecond=0).isoformat()


def timestamp_not_future(
    value: Any,
    *,
    now: dt.datetime | None = None,
    max_future_skew_seconds: int = MAX_FUTURE_SKEW_SECONDS,
) -> bool:
    parsed = strict_timestamp_shanghai(value)
    observed_now = (now or now_shanghai()).astimezone(SHANGHAI)
    return bool(
        parsed is not None
        and parsed <= observed_now + dt.timedelta(seconds=max_future_skew_seconds)
    )


def _journal_path(evidence_root: Path | None = None) -> Path:
    return (evidence_root or EVIDENCE_ROOT) / PRODUCER_JOURNAL_NAME


def _trust_paths(evidence_root: Path | None = None) -> tuple[Path, Path, Path]:
    trust_directory = (evidence_root or EVIDENCE_ROOT) / _TRUST_DIRECTORY_NAME
    return (
        trust_directory,
        trust_directory / _TRUST_KEY_NAME,
        trust_directory / _TRUST_STATE_NAME,
    )


def _private_file(path: Path) -> bool:
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return False
    return path.is_file() and not path.is_symlink() and mode == 0o600


def _private_directory(path: Path) -> bool:
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return False
    return path.is_dir() and not path.is_symlink() and mode == 0o700


def _read_trust_key(evidence_root: Path | None = None) -> bytes | None:
    trust_directory, key_path, _ = _trust_paths(evidence_root)
    if not _private_directory(trust_directory) or not _private_file(key_path):
        return None
    try:
        secret = key_path.read_bytes()
    except OSError:
        return None
    return secret if len(secret) == _TRUST_KEY_BYTES else None


def _create_trust_key(evidence_root: Path | None = None) -> bytes | None:
    trust_directory, key_path, _ = _trust_paths(evidence_root)
    try:
        trust_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(trust_directory, 0o700)
    except OSError:
        return None
    existing = _read_trust_key(evidence_root)
    if existing is not None:
        return existing
    temporary = trust_directory / f".{secrets.token_hex(12)}.tmp"
    descriptor = -1
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        secret = secrets.token_bytes(_TRUST_KEY_BYTES)
        os.write(descriptor, secret)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, key_path)
        os.chmod(key_path, 0o600)
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        return None
    return _read_trust_key(evidence_root)


def _state_without_mac(
    *, sequence_no: int, event_id: str, event_mac: str, semantic_digest: str
) -> dict[str, Any]:
    return {
        "schema_version": PRODUCER_STATE_SCHEMA_VERSION,
        "sequence_no": sequence_no,
        "event_id": event_id,
        "event_mac": event_mac,
        "semantic_digest": semantic_digest,
    }


def _state_mac(secret: bytes, material: Mapping[str, Any]) -> str:
    return hmac.new(secret, canonical_bytes(material), hashlib.sha256).hexdigest()


def _read_trust_state(
    secret: bytes, evidence_root: Path | None = None
) -> dict[str, Any] | None:
    _, _, state_path = _trust_paths(evidence_root)
    if not _private_file(state_path):
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(state, Mapping) or set(state) != {
        "schema_version", "sequence_no", "event_id", "event_mac", "semantic_digest", "state_mac"
    }:
        return None
    sequence_no = state.get("sequence_no")
    if (
        state.get("schema_version") != PRODUCER_STATE_SCHEMA_VERSION
        or type(sequence_no) is not int
        or sequence_no < 1
        or not strict_hash(state.get("event_id"))
        or not strict_hash(state.get("event_mac"))
        or not strict_hash(state.get("semantic_digest"))
        or not strict_hash(state.get("state_mac"))
    ):
        return None
    unsigned = _state_without_mac(
        sequence_no=sequence_no,
        event_id=str(state["event_id"]),
        event_mac=str(state["event_mac"]),
        semantic_digest=str(state["semantic_digest"]),
    )
    expected = _state_mac(secret, unsigned)
    return dict(state) if hmac.compare_digest(str(state["state_mac"]), expected) else None


def _write_trust_state(
    secret: bytes,
    *,
    sequence_no: int,
    event_id: str,
    event_mac: str,
    semantic_digest: str,
    evidence_root: Path | None = None,
) -> bool:
    trust_directory, _, state_path = _trust_paths(evidence_root)
    unsigned = _state_without_mac(
        sequence_no=sequence_no,
        event_id=event_id,
        event_mac=event_mac,
        semantic_digest=semantic_digest,
    )
    payload = {**unsigned, "state_mac": _state_mac(secret, unsigned)}
    temporary = trust_directory / f".{secrets.token_hex(12)}.tmp"
    descriptor = -1
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        encoded = canonical_bytes(payload)
        os.write(descriptor, encoded)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, state_path)
        os.chmod(state_path, 0o600)
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        return False
    return True


def _event_without_mac(event: Mapping[str, Any]) -> dict[str, Any]:
    return {field: event.get(field) for field in _EVENT_FIELDS if field != "event_mac"}


def _event_mac(secret: bytes, event: Mapping[str, Any]) -> str:
    return hmac.new(secret, canonical_bytes(_event_without_mac(event)), hashlib.sha256).hexdigest()


def _create_journal_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_EVENT_TABLE} (
            sequence_no INTEGER PRIMARY KEY,
            event_id TEXT NOT NULL UNIQUE,
            schema_version TEXT NOT NULL,
            semantic_digest TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            task_sha256 TEXT NOT NULL,
            scope_sha256 TEXT NOT NULL,
            ledger_sha256 TEXT NOT NULL,
            source_projection_sha256 TEXT NOT NULL,
            projection_sha256 TEXT NOT NULL,
            binding_sha256 TEXT NOT NULL,
            previous_event_mac TEXT NOT NULL,
            event_mac TEXT NOT NULL
        )
        """
    )
    connection.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS {_EVENT_TABLE}_no_update
        BEFORE UPDATE ON {_EVENT_TABLE}
        BEGIN SELECT RAISE(ABORT, 'trusted producer events are append-only'); END
        """
    )
    connection.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS {_EVENT_TABLE}_no_delete
        BEFORE DELETE ON {_EVENT_TABLE}
        BEGIN SELECT RAISE(ABORT, 'trusted producer events are append-only'); END
        """
    )


def _read_verified_events(
    secret: bytes,
    *,
    evidence_root: Path | None = None,
    now: dt.datetime | None = None,
) -> list[dict[str, Any]] | None:
    journal = _journal_path(evidence_root)
    if not journal.is_file() or journal.is_symlink():
        return None
    try:
        uri = f"file:{journal.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            rows = connection.execute(
                f"SELECT {', '.join(_EVENT_FIELDS)} FROM {_EVENT_TABLE} ORDER BY sequence_no"
            ).fetchall()
    except (OSError, sqlite3.DatabaseError):
        return None
    if not rows:
        return None
    events: list[dict[str, Any]] = []
    previous_mac = ""
    previous_issued: dt.datetime | None = None
    for index, row in enumerate(rows, start=1):
        event = dict(zip(_EVENT_FIELDS, row, strict=True))
        issued = strict_timestamp_shanghai(event.get("issued_at"))
        if (
            type(event.get("sequence_no")) is not int
            or event.get("sequence_no") != index
            or event.get("schema_version") != PRODUCER_EVENT_SCHEMA_VERSION
            or not all(strict_hash(event.get(field)) for field in (
                "event_id", "semantic_digest", *_EVIDENCE_DIGEST_FIELDS, "event_mac"
            ))
            or event.get("previous_event_mac") != previous_mac
            or issued is None
            or (previous_issued is not None and issued < previous_issued)
            or not timestamp_not_future(event.get("issued_at"), now=now)
            or not hmac.compare_digest(str(event.get("event_mac")), _event_mac(secret, event))
        ):
            return None
        event_identity = canonical_digest({
            key: event[key] for key in _EVENT_FIELDS if key not in {"event_id", "event_mac"}
        })
        if not hmac.compare_digest(str(event["event_id"]), event_identity):
            return None
        events.append(event)
        previous_mac = str(event["event_mac"])
        previous_issued = issued
    state = _read_trust_state(secret, evidence_root)
    latest = events[-1]
    if not state or not (
        state.get("sequence_no") == latest["sequence_no"]
        and state.get("event_id") == latest["event_id"]
        and state.get("event_mac") == latest["event_mac"]
        and state.get("semantic_digest") == latest["semantic_digest"]
    ):
        return None
    return events


def _validated_evidence_digests(value: Any) -> dict[str, str] | None:
    if not isinstance(value, Mapping) or set(value) != set(_EVIDENCE_DIGEST_FIELDS):
        return None
    result = {field: strict_hash(value.get(field)) for field in _EVIDENCE_DIGEST_FIELDS}
    return result if all(result.values()) else None


def record_trusted_producer_receipt(
    evidence_digests: Mapping[str, Any],
    *,
    issued_at: Any,
    evidence_root: Path | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any] | None:
    """Append one authenticated producer event. Only an explicit POST calls this."""

    digests = _validated_evidence_digests(evidence_digests)
    issued_text = canonical_timestamp_shanghai(issued_at)
    observed_now = now or now_shanghai()
    if not digests or not issued_text or not timestamp_not_future(issued_text, now=observed_now):
        return None
    root = evidence_root or EVIDENCE_ROOT
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    secret = _create_trust_key(root)
    if secret is None:
        return None
    journal = _journal_path(root)
    state_exists = _trust_paths(root)[2].exists()
    if journal.exists() != state_exists:
        return None
    existing_events = _read_verified_events(secret, evidence_root=root, now=observed_now) if journal.exists() else []
    if existing_events is None:
        return None
    semantic_digest = canonical_digest(digests)
    if existing_events and existing_events[-1]["semantic_digest"] == semantic_digest:
        return producer_receipt_metadata(existing_events[-1])
    previous = existing_events[-1] if existing_events else None
    sequence_no = int(previous["sequence_no"]) + 1 if previous else 1
    previous_event_mac = str(previous["event_mac"]) if previous else ""
    unsigned = {
        "sequence_no": sequence_no,
        "schema_version": PRODUCER_EVENT_SCHEMA_VERSION,
        "semantic_digest": semantic_digest,
        "issued_at": issued_text,
        **digests,
        "previous_event_mac": previous_event_mac,
    }
    event_id = canonical_digest(unsigned)
    event = {**unsigned, "event_id": event_id, "event_mac": ""}
    event["event_mac"] = _event_mac(secret, event)
    try:
        with sqlite3.connect(journal) as connection:
            connection.execute("BEGIN IMMEDIATE")
            _create_journal_schema(connection)
            connection.execute(
                f"INSERT INTO {_EVENT_TABLE} ({', '.join(_EVENT_FIELDS)}) VALUES ({', '.join('?' for _ in _EVENT_FIELDS)})",
                tuple(event[field] for field in _EVENT_FIELDS),
            )
            connection.commit()
    except sqlite3.DatabaseError:
        return None
    if not _write_trust_state(
        secret,
        sequence_no=sequence_no,
        event_id=event_id,
        event_mac=str(event["event_mac"]),
        semantic_digest=semantic_digest,
        evidence_root=root,
    ):
        return None
    verified = _read_verified_events(secret, evidence_root=root, now=observed_now)
    return producer_receipt_metadata(verified[-1]) if verified else None


def producer_receipt_metadata(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": PRODUCER_RECEIPT_SCHEMA_VERSION,
        "event_id": event.get("event_id"),
        "sequence_no": event.get("sequence_no"),
        "issued_at": event.get("issued_at"),
        "semantic_digest": event.get("semantic_digest"),
        "event_mac": event.get("event_mac"),
        **{field: event.get(field) for field in _EVIDENCE_DIGEST_FIELDS},
        "verified": True,
        "state_continuity_verified": True,
    }


def read_verified_producer_receipt(
    expected_digests: Mapping[str, Any],
    *,
    evidence_root: Path | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any] | None:
    """Read-only validation; it never creates trust material or a journal."""

    expected = _validated_evidence_digests(expected_digests)
    root = evidence_root or EVIDENCE_ROOT
    secret = _read_trust_key(root)
    if expected is None or secret is None:
        return None
    events = _read_verified_events(secret, evidence_root=root, now=now)
    if not events:
        return None
    latest = events[-1]
    if any(latest.get(field) != expected[field] for field in _EVIDENCE_DIGEST_FIELDS):
        return None
    if latest.get("semantic_digest") != canonical_digest(expected):
        return None
    metadata = producer_receipt_metadata(latest)
    return metadata if set(metadata) == set(_RECEIPT_FIELDS) else None


def strict_text(value: Any, *, limit: int = 160) -> str:
    if not isinstance(value, str) or value != value.strip() or not value or len(value) > limit:
        return ""
    return value


def strict_identity(value: Any, *, limit: int = 160) -> str:
    text = strict_text(value, limit=limit)
    return text if text and _IDENTITY_RE.fullmatch(text) else ""


def strict_hash(value: Any) -> str:
    text = strict_text(value, limit=64)
    return text if _HASH_RE.fullmatch(text) else ""


def strict_target(value: Any) -> str:
    text = strict_text(value, limit=9)
    return text if _TARGET_RE.fullmatch(text) else ""


def strict_yyyymmdd(value: Any) -> str:
    text = strict_text(value, limit=8)
    if len(text) != 8 or not text.isdigit():
        return ""
    try:
        parsed = dt.datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return ""
    return text if parsed.strftime("%Y%m%d") == text else ""


def strict_timestamp_shanghai(value: Any) -> dt.datetime | None:
    text = strict_text(value, limit=64)
    if not text or "T" not in text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(SHANGHAI)


def canonical_timestamp_shanghai(value: Any) -> str:
    parsed = strict_timestamp_shanghai(value)
    return parsed.isoformat(timespec="seconds") if parsed is not None else ""


def strict_decimal_text(value: Any, *, minimum: float, maximum: float) -> str:
    if isinstance(value, bool) or not isinstance(value, Number):
        return ""
    number = float(value)
    if not math.isfinite(number) or number < minimum or number > maximum:
        return ""
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return ""
    text = format(decimal, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def safety_projection(packet: Mapping[str, Any]) -> dict[str, bool] | None:
    explicit_fields = packet.get("cache_api_explicit_safety_fields")
    required_fields = {*FALSE_SAFETY_FIELDS, *TRUE_SAFETY_FIELDS}
    if explicit_fields is not None and (
        not isinstance(explicit_fields, list)
        or not all(isinstance(field, str) for field in explicit_fields)
        or set(explicit_fields) != required_fields
    ):
        return None
    if not isinstance(packet.get("warnings"), list) or packet.get("warnings") != []:
        return None
    if not all(packet.get(field) is False for field in FALSE_SAFETY_FIELDS):
        return None
    if not all(packet.get(field) is True for field in TRUE_SAFETY_FIELDS):
        return None
    return {
        **{field: False for field in FALSE_SAFETY_FIELDS},
        **{field: True for field in TRUE_SAFETY_FIELDS},
    }


def _candidate_projection(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        return []
    result: list[dict[str, str]] = []
    for raw in value[:3]:
        if not isinstance(raw, Mapping):
            return []
        code = strict_text(raw.get("code"), limit=9)
        name = strict_text(raw.get("name"), limit=120)
        reason = strict_text(raw.get("reason"), limit=500)
        if not _ETF_RE.fullmatch(code) or not name or not reason:
            return []
        result.append({"code": code, "name": name, "reason": reason})
    return result


def build_source_projection(
    etf_packet: Any,
    margin_packet: Any,
    *,
    target: Any,
) -> dict[str, Any] | None:
    if not isinstance(etf_packet, Mapping) or not isinstance(margin_packet, Mapping):
        return None
    target_text = strict_target(target)
    etf_safety = safety_projection(etf_packet)
    margin_safety = safety_projection(margin_packet)
    etf_date = strict_yyyymmdd(etf_packet.get("data_date"))
    margin_date = strict_yyyymmdd(margin_packet.get("trade_date"))
    etf_updated = canonical_timestamp_shanghai(etf_packet.get("updated_at"))
    margin_updated = canonical_timestamp_shanghai(margin_packet.get("updated_at"))
    candidates = _candidate_projection(etf_packet.get("recommended_etfs"))
    available_cash = strict_decimal_text(etf_packet.get("available_cash"), minimum=0, maximum=1_000_000_000_000_000)
    recommended_cash_ratio = strict_decimal_text(etf_packet.get("recommended_cash_ratio"), minimum=0, maximum=100)
    current_margin_ratio = strict_decimal_text(etf_packet.get("current_margin_ratio"), minimum=0, maximum=100)
    recommended_margin_ratio = strict_decimal_text(etf_packet.get("recommended_margin_ratio"), minimum=0, maximum=100)
    financing_balance = strict_decimal_text(margin_packet.get("financing_balance_yi"), minimum=0, maximum=1_000_000_000)
    financing_buy = strict_decimal_text(margin_packet.get("financing_buy_yi"), minimum=-1_000_000_000, maximum=1_000_000_000)
    margin_balance = strict_decimal_text(margin_packet.get("margin_balance_yi"), minimum=0, maximum=1_000_000_000)
    margin_fields_present = all(
        margin_packet.get(field) not in (None, "")
        for field in ("financing_balance_yi", "financing_buy_yi", "margin_balance_yi")
    )
    source_labels = {
        "etf": strict_text(etf_packet.get("source"), limit=240),
        "margin": strict_text(margin_packet.get("source"), limit=240),
    }
    ready = bool(
        target_text
        and etf_packet.get("packet_key") == "command_center_etf_packet"
        and margin_packet.get("packet_key") == "command_center_margin_packet"
        and etf_safety
        and margin_safety
        and etf_date
        and etf_date == margin_date
        and etf_updated
        and margin_updated
        and strict_text(etf_packet.get("status"), limit=32).lower() == "ready"
        and strict_text(etf_packet.get("data_status"), limit=32).lower() == "ready"
        and strict_text(margin_packet.get("status"), limit=32).lower() == "ready"
        and strict_text(margin_packet.get("data_status"), limit=32).lower() == "ready"
        and strict_text(etf_packet.get("verification_status"), limit=32) == "已验证"
        and strict_text(margin_packet.get("verification_status"), limit=32) == "已验证"
        and source_labels["etf"]
        and source_labels["margin"]
        and candidates
        and available_cash
        and recommended_cash_ratio
        and current_margin_ratio
        and recommended_margin_ratio
        and margin_fields_present
        and financing_balance
        and financing_buy
        and margin_balance
        and isinstance(etf_packet.get("allow_new_margin"), bool)
    )
    if not ready:
        return None
    return {
        "schema_version": SOURCE_PROJECTION_SCHEMA_VERSION,
        "target": target_text,
        "packet_keys": list(REQUESTED_PACKET_KEYS),
        "etf": {
            "status": "ready",
            "data_status": "ready",
            "data_date": etf_date,
            "updated_at": etf_updated,
            "source": source_labels["etf"],
            "verification_status": "已验证",
            "available_cash": available_cash,
            "recommended_cash_ratio": recommended_cash_ratio,
            "current_margin_ratio": current_margin_ratio,
            "recommended_margin_ratio": recommended_margin_ratio,
            "allow_new_margin": etf_packet.get("allow_new_margin"),
            "recommended_etfs": candidates,
            "safety": etf_safety,
            "warnings": [],
        },
        "margin": {
            "status": "ready",
            "data_status": "ready",
            "trade_date": margin_date,
            "updated_at": margin_updated,
            "source": source_labels["margin"],
            "verification_status": "已验证",
            "financing_balance_yi": financing_balance,
            "financing_buy_yi": financing_buy,
            "margin_balance_yi": margin_balance,
            "safety": margin_safety,
            "warnings": [],
        },
    }


def build_source_scope_material(*, target: str, source_projection_sha256: str) -> dict[str, Any]:
    result_version = f"margin-etf-source:{source_projection_sha256}"
    return {
        "route": TASK_ROUTE,
        "mode": "local_packet_replay",
        "requested_packet_keys": list(REQUESTED_PACKET_KEYS),
        "target": target,
        "source_identity": SOURCE_IDENTITY,
        "source_result_version": result_version,
        "source_projection_sha256": source_projection_sha256,
    }
