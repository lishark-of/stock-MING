"""Fail-closed full-market effective-dated industry membership evidence.

The existing ``index_member_all`` Factor task is deliberately a bounded raw
sample collector.  It is not, and must never be treated as, the authoritative
full-market classification used by Factor or Candidate Radar production
workers.  This module only reads an externally-produced immutable artifact and
creates local execution-request tickets.  It never calls a provider and never
writes a production pointer.
"""

from __future__ import annotations

import base64
import binascii
import datetime as _dt
import hashlib
import json
import os
import re
import stat
import subprocess
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.constant_time import bytes_eq

from server.services import external_production_attestation_service as external_trust
from server.services.task_service import create_task_record, update_task_status


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
INDUSTRY_ROOT_RELATIVE = Path("full_market_industry_membership")
POINTER_FILE = "pointer.json"

POINTER_SCHEMA_VERSION = "full_market_industry_membership_pointer.v2"
MANIFEST_SCHEMA_VERSION = "full_market_industry_membership_manifest.v2"
ARTIFACT_SCHEMA_VERSION = "full_market_industry_membership_artifact.v1"
PRODUCED_POINTER_SCHEMA_VERSION = "full_market_industry_membership_generation_pointer.v5"
PRODUCED_MANIFEST_SCHEMA_VERSION = "full_market_industry_membership_manifest.v3"
RAW_ARTIFACT_SCHEMA_VERSION = "full_market_industry_membership_raw_artifact.v1"
CALL_LEDGER_SCHEMA_VERSION = "full_market_industry_membership_call_ledger.v1"
PRODUCER_BINDING_SCHEMA_VERSION = "full_market_industry_membership_producer_binding.v1"
PRODUCED_SOURCE_VERSION_SCHEMA_VERSION = (
    "full_market_industry_membership_source_version.v2"
)
SEMANTIC_EVIDENCE_SCHEMA_VERSION = (
    "full_market_industry_membership_out_date_semantic_authority.v2"
)
SEMANTIC_AUTHORITY_ENVELOPE_SCHEMA_VERSION = "industry_out_date_authority_envelope.v1"
SEMANTIC_AUTHORITY_STATEMENT_SCHEMA_VERSION = "industry_out_date_authority_statement.v1"
SEMANTIC_AUTHORITY_PATH = external_trust.TRUST_ROOT / "industry-out-date-authority.json"
SEMANTIC_AUTHORITY_TRUSTED_OWNER_UIDS = frozenset({0})
SCOPE_SCHEMA_VERSION = "full_market_industry_membership_scope.v1"
SOURCE_VERSION_SCHEMA_VERSION = "full_market_industry_membership_source_version.v1"
EXECUTION_REQUEST_SCHEMA_VERSION = (
    "full_market_industry_membership_execution_request.v1"
)
EXECUTION_REQUEST_TASK_TYPE = (
    "run_full_market_industry_membership_execution_request"
)

SOURCE_API = "index_member_all"
SOURCE_SCOPE = "full_market_effective_dated_industry_membership"
RESOLVED_OUT_DATE_SEMANTICS = "effective_to_exclusive"
REQUIRED_EXCHANGES = ("BSE", "SSE", "SZSE")
MINIMUM_ELIGIBLE_SYMBOLS = 3000
TRANSPORT_RECEIPT_SCHEMA_VERSION = "tushare_runtime_transport_receipt.v2"
TRANSPORT_RECEIPT_MAX_AGE_SECONDS = 300
TRANSPORT_RECEIPT_MAX_DURATION_SECONDS = 120

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^[0-9]{8}$")
_SYMBOL = re.compile(r"^[0-9]{6}\.(BJ|SH|SZ)$")
_VERSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PROVIDER_RAW_FIELDS = (
    "l1_code", "l1_name", "l2_code", "l2_name", "l3_code", "l3_name",
    "ts_code", "name", "in_date", "out_date", "is_new",
)
TRANSPORT_RECEIPT_FIELDS = {
    "api", "call_id", "completed_at_utc", "issued_at_utc",
    "official_client_identity_verified", "provider", "provider_response_received",
    "request_params_safe", "schema_version", "sdk_method_invoked",
}
CALL_LEDGER_ROW_FIELDS = {
    "api", "call_id", "call_status", "contains_secret", "failure_mode",
    "no_data", "page_index", "page_rows_digest", "partition",
    "permission_denied", "provider_transport_verified", "raw_end_index",
    "raw_start_index", "request_params_safe", "row_count", "transport_receipt",
    "transport_receipt_digest", "tushare_called", "external_calls_triggered",
    "does_not_execute_trades", "does_not_modify_strategy_action",
}
GENERATION_BINDING_FIELDS = {
    "artifact_sha256",
    "as_of_date",
    "call_ledger_sha256",
    "current_generation",
    "execution_request_digest",
    "manifest_digest",
    "manifest_file",
    "producer_binding_digest",
    "producer_head_full",
    "provider_scope_digest",
    "provider_version_digest",
    "raw_artifact_sha256",
    "scope_digest",
    "semantic_evidence_sha256",
    "source_version_digest",
    "universe_digest",
    "validated_trade_date",
}

INDUSTRY_BINDING_DIGEST_KEYS = (
    "industry_scope_digest",
    "industry_source_version_digest",
    "industry_artifact_sha256",
    "industry_manifest_digest",
    "industry_pointer_digest",
    "industry_semantic_evidence_sha256",
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _generation_binding(pointer: Mapping[str, Any]) -> dict[str, Any]:
    return {key: pointer.get(key) for key in sorted(GENERATION_BINDING_FIELDS)}


def _execution_request_digest(value: Mapping[str, Any]) -> str:
    return _digest(
        {
            key: item
            for key, item in value.items()
            if key not in {"contains_secret", "request_digest"}
        }
    )


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _safe_relative_file(root: Path, value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    relative = Path(text)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    if root.is_symlink():
        return None
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return None
    candidate = root / relative
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except OSError:
        return None
    if resolved.parent != resolved_root and resolved_root not in resolved.parents:
        return None
    if candidate.is_symlink() or not resolved.is_file():
        return None
    return resolved


def _utc_timestamp(value: Any) -> _dt.datetime | None:
    text = value if type(value) is str else ""
    if not text.endswith("Z"):
        return None
    try:
        parsed = _dt.datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed.astimezone(_dt.timezone.utc) if parsed.tzinfo else None


def _read_semantic_authority() -> tuple[dict[str, Any], str]:
    path = SEMANTIC_AUTHORITY_PATH
    try:
        metadata = path.lstat()
    except OSError:
        return {}, "industry_semantic_authority_missing"
    if not (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and metadata.st_uid in SEMANTIC_AUTHORITY_TRUSTED_OWNER_UIDS
        and stat.S_IMODE(metadata.st_mode) & 0o222 == 0
        and metadata.st_nlink == 1
        and metadata.st_size <= 1024 * 1024
    ):
        return {}, "industry_semantic_authority_file_untrusted"
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | int(getattr(os, "O_CLOEXEC", 0))
            | int(getattr(os, "O_NOFOLLOW", 0)),
        )
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino, opened.st_size) != (
            metadata.st_dev, metadata.st_ino, metadata.st_size,
        ):
            return {}, "industry_semantic_authority_changed_during_read"
        value = json.loads(os.read(descriptor, metadata.st_size + 1))
        return (dict(value), "") if type(value) is dict else ({}, "industry_semantic_authority_invalid")
    except Exception:
        return {}, "industry_semantic_authority_unreadable"
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _validated_semantic_authority() -> dict[str, Any]:
    envelope, read_blocker = _read_semantic_authority()
    blockers = [read_blocker] if read_blocker else []
    envelope_keys = {
        "algorithm", "key_fingerprint_sha256", "schema_version",
        "signature_base64", "statement",
    }
    statement_keys = {
        "authority", "content", "content_digest", "endpoint_field",
        "expires_at_utc", "issued_at_utc", "resolved_semantics",
        "schema_version", "source_api", "source_reference", "source_scope",
        "status",
    }
    statement = envelope.get("statement") if type(envelope.get("statement")) is dict else {}
    content = statement.get("content") if type(statement.get("content")) is dict else {}
    required_content = {
        "field": "out_date",
        "interval_convention": "effective_from_inclusive_effective_to_exclusive",
        "non_null_boundary": "first_excluded_trade_date",
        "null_meaning": "membership_current_at_validated_trade_date",
    }
    issued = _utc_timestamp(statement.get("issued_at_utc"))
    expires = _utc_timestamp(statement.get("expires_at_utc"))
    now = _dt.datetime.now(_dt.timezone.utc)
    if (
        set(envelope) != envelope_keys
        or envelope.get("schema_version") != SEMANTIC_AUTHORITY_ENVELOPE_SCHEMA_VERSION
        or envelope.get("algorithm") != "Ed25519"
        or set(statement) != statement_keys
        or statement.get("schema_version") != SEMANTIC_AUTHORITY_STATEMENT_SCHEMA_VERSION
        or statement.get("status") != "externally_attested"
        or statement.get("authority") != "independent_production_semantic_authority"
        or statement.get("source_api") != SOURCE_API
        or statement.get("source_scope") != SOURCE_SCOPE
        or statement.get("endpoint_field") != "out_date"
        or statement.get("resolved_semantics") != RESOLVED_OUT_DATE_SEMANTICS
        or type(statement.get("source_reference")) is not str
        or not statement.get("source_reference", "").strip()
        or content != required_content
        or statement.get("content_digest") != _digest(content)
        or issued is None
        or expires is None
        or not (issued <= now <= expires)
        or (expires - issued).total_seconds() > 366 * 24 * 60 * 60
    ):
        blockers.append("industry_semantic_authority_contract_invalid")
    key, trust = external_trust._load_trusted_public_key()
    fingerprint = str(trust.get("key_fingerprint_sha256") or "")
    if key is None:
        blockers.append(str(trust.get("status") or "industry_semantic_authority_key_unavailable"))
    elif not (
        _HEX_64.fullmatch(fingerprint)
        and type(envelope.get("key_fingerprint_sha256")) is str
        and bytes_eq(envelope["key_fingerprint_sha256"].encode(), fingerprint.encode())
    ):
        blockers.append("industry_semantic_authority_key_mismatch")
    signature = b""
    try:
        signature = base64.b64decode(str(envelope.get("signature_base64") or ""), validate=True)
        if len(signature) != 64:
            raise ValueError("invalid signature length")
        if key is not None:
            key.verify(signature, _canonical_bytes(statement))
    except (ValueError, binascii.Error, InvalidSignature):
        blockers.append("industry_semantic_authority_signature_invalid")
    except Exception:
        blockers.append("industry_semantic_authority_verification_failed")
    blockers = list(dict.fromkeys(blockers))
    return {
        "ready": not blockers,
        "path": SEMANTIC_AUTHORITY_PATH if not blockers else None,
        "sha256": _file_digest(SEMANTIC_AUTHORITY_PATH) if not blockers else "",
        "content_digest": str(statement.get("content_digest") or ""),
        "source_reference": str(statement.get("source_reference") or ""),
        "signature_sha256": hashlib.sha256(signature).hexdigest() if signature and not blockers else "",
        "blockers": blockers,
    }


def _date(value: Any) -> str:
    text = str(value or "").strip().replace("-", "")
    if not _DATE.fullmatch(text):
        return ""
    try:
        _dt.datetime.strptime(text, "%Y%m%d")
    except ValueError:
        return ""
    return text


def _provider_raw_row(source: Mapping[str, Any]) -> dict[str, Any] | None:
    if type(source) is not dict or any(
        isinstance(source.get(field), (Mapping, list, tuple, set))
        for field in PROVIDER_RAW_FIELDS
    ):
        return None
    return {
        field: None if source.get(field) is None else str(source.get(field)).strip()
        for field in PROVIDER_RAW_FIELDS
    }


def _normalized_provider_row(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if set(raw) != set(PROVIDER_RAW_FIELDS) or any(
        value is not None and type(value) is not str for value in raw.values()
    ):
        return None
    symbol = str(raw.get("ts_code") or "").upper()
    effective_from = _date(raw.get("in_date"))
    raw_out_date = raw.get("out_date")
    effective_to = _date(raw_out_date) if raw_out_date else None
    industry_code = next(
        (str(raw.get(key) or "").strip() for key in ("l3_code", "l2_code", "l1_code") if raw.get(key)),
        "",
    )
    if (
        not _SYMBOL.fullmatch(symbol)
        or not effective_from
        or (raw_out_date and not effective_to)
        or not industry_code
        or raw.get("is_new") not in {"Y", "N"}
    ):
        return None
    return {
        "effective_from": effective_from,
        "effective_to": effective_to,
        "industry_code": industry_code,
        "source_api": SOURCE_API,
        "ts_code": symbol,
    }


def _transport_receipt_blockers(
    receipt: Any,
    *,
    expected_call_id: str,
    expected_params: Mapping[str, Any],
    seen_call_ids: set[str],
    reference_time: _dt.datetime | None = None,
) -> list[str]:
    row = dict(receipt) if type(receipt) is dict else {}
    call_id = row.get("call_id") if type(row.get("call_id")) is str else ""
    issued = _utc_timestamp(row.get("issued_at_utc"))
    completed = _utc_timestamp(row.get("completed_at_utc"))
    reference = reference_time or _dt.datetime.now(_dt.timezone.utc)
    blockers: list[str] = []
    if (
        set(row) != TRANSPORT_RECEIPT_FIELDS
        or row.get("schema_version") != TRANSPORT_RECEIPT_SCHEMA_VERSION
        or row.get("api") != SOURCE_API
        or row.get("provider") != "Tushare"
        or call_id != expected_call_id
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", call_id)
        or type(row.get("request_params_safe")) is not dict
        or row.get("request_params_safe") != dict(expected_params)
        or row.get("sdk_method_invoked") is not True
        or row.get("provider_response_received") is not True
        or row.get("official_client_identity_verified") is not True
    ):
        blockers.append("provider_transport_receipt_contract_invalid")
    if call_id in seen_call_ids:
        blockers.append("provider_transport_receipt_call_id_reused")
    if (
        issued is None
        or completed is None
        or issued > completed
        or (completed - issued).total_seconds() > TRANSPORT_RECEIPT_MAX_DURATION_SECONDS
        or completed > reference + _dt.timedelta(seconds=30)
        or (reference - completed).total_seconds() > TRANSPORT_RECEIPT_MAX_AGE_SECONDS
    ):
        blockers.append("provider_transport_receipt_freshness_invalid")
    if call_id:
        seen_call_ids.add(call_id)
    return blockers


def _provider_ledger_replay_blockers(
    raw_rows: list[dict[str, Any]],
    normalized_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    *,
    observed_at: _dt.datetime | None,
) -> list[str]:
    blockers: list[str] = []
    seen_call_ids: set[str] = set()
    cursor = 0
    partition_index = 0
    expected_page = 0
    terminal = False
    partitions = ("Y", "N")
    for ledger in ledger_rows:
        if terminal:
            partition_index += 1
            expected_page = 0
            terminal = False
        partition = partitions[partition_index] if partition_index < len(partitions) else ""
        params = {
            "is_new": partition,
            "limit": 2000,
            "offset": expected_page * 2000,
        }
        count = ledger.get("row_count")
        start = ledger.get("raw_start_index")
        end = ledger.get("raw_end_index")
        call_id = ledger.get("call_id") if type(ledger.get("call_id")) is str else ""
        receipt = ledger.get("transport_receipt")
        if (
            set(ledger) != CALL_LEDGER_ROW_FIELDS
            or partition not in partitions
            or ledger.get("api") != SOURCE_API
            or ledger.get("partition") != partition
            or ledger.get("page_index") != expected_page
            or ledger.get("request_params_safe") != params
            or type(count) is not int
            or isinstance(count, bool)
            or not 0 <= count <= 2000
            or start != cursor
            or end != cursor + count
            or end > len(raw_rows)
            or ledger.get("provider_transport_verified") is not True
            or ledger.get("permission_denied") is not False
            or ledger.get("external_calls_triggered") is not True
            or ledger.get("tushare_called") is not True
            or ledger.get("contains_secret") is not False
            or ledger.get("does_not_execute_trades") is not True
            or ledger.get("does_not_modify_strategy_action") is not True
        ):
            blockers.append("industry_call_ledger_page_contract_invalid")
            break
        page_rows = raw_rows[start:end]
        if (
            ledger.get("page_rows_digest") != _digest(page_rows)
            or any(row.get("is_new") != partition for row in page_rows)
        ):
            blockers.append("industry_call_ledger_raw_page_binding_invalid")
        if count == 0:
            if ledger.get("call_status") != "no_data" or ledger.get("no_data") is not True:
                blockers.append("industry_call_ledger_terminal_status_invalid")
            terminal = True
        else:
            if ledger.get("call_status") != "success" or ledger.get("no_data") is not False:
                blockers.append("industry_call_ledger_success_status_invalid")
            terminal = count < 2000
        if ledger.get("failure_mode") != "none":
            blockers.append("industry_call_ledger_failure_mode_invalid")
        blockers.extend(
            _transport_receipt_blockers(
                receipt,
                expected_call_id=call_id,
                expected_params=params,
                seen_call_ids=seen_call_ids,
                reference_time=observed_at,
            )
        )
        if ledger.get("transport_receipt_digest") != _digest(receipt):
            blockers.append("industry_call_ledger_receipt_digest_invalid")
        cursor = end
        expected_page += 1
    if partition_index != 1 or not terminal or cursor != len(raw_rows):
        blockers.append("industry_call_ledger_partition_replay_incomplete")
    recomputed = [_normalized_provider_row(row) for row in raw_rows]
    if any(row is None for row in recomputed):
        blockers.append("industry_raw_to_normalized_replay_invalid")
    else:
        expected = sorted(
            recomputed,
            key=lambda row: (
                row["ts_code"], row["effective_from"],
                str(row["effective_to"] or ""), row["industry_code"],
            ),
        )
        if expected != normalized_rows:
            blockers.append("industry_raw_to_normalized_replay_mismatch")
    return list(dict.fromkeys(blockers))


def _symbols(values: Any) -> tuple[list[str], int, int]:
    raw = list(values) if isinstance(values, Sequence) and not isinstance(values, (str, bytes)) else []
    normalized: list[str] = []
    invalid = 0
    for value in raw:
        symbol = str(value or "").strip().upper()
        if _SYMBOL.fullmatch(symbol):
            normalized.append(symbol)
        else:
            invalid += 1
    unique = sorted(set(normalized))
    return unique, len(normalized) - len(unique), invalid


def _exchange(symbol: str) -> str:
    suffix = symbol.rsplit(".", 1)[-1]
    return {"BJ": "BSE", "SH": "SSE", "SZ": "SZSE"}.get(suffix, "")


def _current_head_full() -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    value = completed.stdout.strip().lower() if completed.returncode == 0 else ""
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else ""


def _interval_blockers(
    rows: list[dict[str, Any]],
    *,
    expected_symbols: list[str],
    validated_trade_date: str,
) -> list[str]:
    blockers: list[str] = []
    by_symbol: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        if set(row) != {
            "effective_from",
            "effective_to",
            "industry_code",
            "source_api",
            "ts_code",
        }:
            blockers.append("artifact_row_schema_not_exact")
            continue
        raw_symbol = row.get("ts_code")
        raw_industry = row.get("industry_code")
        raw_start = row.get("effective_from")
        raw_source_api = row.get("source_api")
        symbol = raw_symbol.strip().upper() if type(raw_symbol) is str else ""
        industry = raw_industry.strip() if type(raw_industry) is str else ""
        start = _date(raw_start) if type(raw_start) is str else ""
        raw_end = row.get("effective_to")
        end_type_valid = raw_end is None or type(raw_end) is str
        end = "" if raw_end in (None, "") else _date(raw_end) if end_type_valid else ""
        if (
            not _SYMBOL.fullmatch(symbol)
            or not industry
            or not start
            or not end_type_valid
            or (raw_end not in (None, "") and not end)
            or (end and start >= end)
            or type(raw_source_api) is not str
            or raw_source_api != SOURCE_API
        ):
            blockers.append("artifact_effective_dated_row_invalid")
            continue
        by_symbol.setdefault(symbol, []).append((start, end))

    artifact_symbols = sorted(by_symbol)
    if artifact_symbols != expected_symbols:
        blockers.append("artifact_symbol_coverage_not_exact")
    active_symbols: list[str] = []
    for symbol, intervals in by_symbol.items():
        intervals.sort()
        previous_end = ""
        active = 0
        for index, (start, end) in enumerate(intervals):
            if previous_end and start < previous_end:
                blockers.append("artifact_effective_intervals_overlap")
            if index > 0 and not previous_end:
                blockers.append("artifact_open_interval_not_terminal")
            previous_end = end
            if start <= validated_trade_date and (not end or validated_trade_date < end):
                active += 1
        if active == 1:
            active_symbols.append(symbol)
        else:
            blockers.append("artifact_as_of_membership_not_exactly_one")
    if sorted(active_symbols) != expected_symbols:
        blockers.append("artifact_as_of_symbol_coverage_not_exact")
    return list(dict.fromkeys(blockers))


def validate_full_market_industry_membership(
    evidence_root: Path,
    *,
    expected_symbols: Any,
    expected_universe_digest: Any,
    expected_validated_trade_date: Any,
    _pointer_override: Mapping[str, Any] | None = None,
    _validate_last_good: bool = True,
) -> dict[str, Any]:
    """Read and verify the current full-market industry pointer without writes."""

    symbols, duplicates, invalid = _symbols(expected_symbols)
    universe_digest = str(expected_universe_digest or "").strip().lower()
    validated_trade_date = _date(expected_validated_trade_date)
    blockers: list[str] = []
    if duplicates or invalid or len(symbols) < MINIMUM_ELIGIBLE_SYMBOLS:
        blockers.append("expected_universe_identity_or_size_invalid")
    if {exchange for symbol in symbols if (exchange := _exchange(symbol))} != set(REQUIRED_EXCHANGES):
        blockers.append("expected_universe_three_exchange_coverage_incomplete")
    if universe_digest != _digest(symbols):
        blockers.append("expected_universe_digest_invalid")
    if not validated_trade_date:
        blockers.append("expected_validated_trade_date_invalid")

    root = evidence_root / INDUSTRY_ROOT_RELATIVE
    pointer_path = root / POINTER_FILE
    root_safe = not evidence_root.is_symlink() and not root.is_symlink()
    pointer = _pointer_override
    if pointer is None:
        pointer = (
            _read_json(pointer_path)
            if root_safe and pointer_path.is_file() and not pointer_path.is_symlink()
            else None
        )
    pointer = dict(pointer) if isinstance(pointer, Mapping) else {}
    pointer_material = {key: value for key, value in pointer.items() if key != "pointer_digest"}
    legacy_pointer_keys = {
        "artifact_sha256",
        "as_of_date",
        "manifest_digest",
        "manifest_file",
        "pointer_digest",
        "schema_version",
        "scope_digest",
        "source_version_digest",
        "semantic_evidence_sha256",
        "universe_digest",
        "validated_trade_date",
        "version_id",
    }
    produced_pointer_keys = legacy_pointer_keys | {
        "call_ledger_sha256",
        "current_generation",
        "execution_request_digest",
        "last_good_binding",
        "last_good_generation",
        "last_good_manifest_digest",
        "last_good_manifest_file",
        "producer_binding_digest",
        "producer_head_full",
        "provider_scope_digest",
        "provider_version_digest",
        "raw_artifact_sha256",
    }
    produced_pointer = pointer.get("schema_version") == PRODUCED_POINTER_SCHEMA_VERSION
    if produced_pointer and (root / "last_good.json").exists():
        blockers.append("industry_legacy_split_last_good_present")
    if set(pointer) != (produced_pointer_keys if produced_pointer else legacy_pointer_keys):
        blockers.append("industry_pointer_schema_not_exact")
    if pointer.get("schema_version") not in {
        POINTER_SCHEMA_VERSION,
        PRODUCED_POINTER_SCHEMA_VERSION,
    }:
        blockers.append("industry_pointer_schema_invalid")
    if pointer.get("pointer_digest") != _digest(pointer_material):
        blockers.append("industry_pointer_digest_invalid")

    manifest_path = _safe_relative_file(root, pointer.get("manifest_file"))
    manifest = _read_json(manifest_path) if manifest_path else None
    manifest = dict(manifest) if isinstance(manifest, Mapping) else {}
    manifest_material = {key: value for key, value in manifest.items() if key != "manifest_digest"}
    legacy_manifest_keys = {
        "artifact_file",
        "artifact_row_count",
        "artifact_schema_version",
        "artifact_sha256",
        "as_of_date",
        "eligible_symbol_count",
        "exchanges",
        "manifest_digest",
        "out_date_semantics",
        "out_date_semantics_evidence_digest",
        "out_date_semantics_validated",
        "scope",
        "schema_version",
        "scope_digest",
        "source_api",
        "source_scope",
        "source_version_digest",
        "source_version",
        "semantic_evidence_file",
        "semantic_evidence_schema_version",
        "semantic_evidence_sha256",
        "status",
        "universe_digest",
        "validated_trade_date",
        "version_id",
    }
    produced_manifest_keys = legacy_manifest_keys | {
        "call_ledger_call_count",
        "call_ledger_file",
        "call_ledger_schema_version",
        "call_ledger_sha256",
        "producer_binding",
        "producer_binding_digest",
        "raw_artifact_file",
        "raw_artifact_row_count",
        "raw_artifact_schema_version",
        "raw_artifact_sha256",
    }
    produced_manifest = manifest.get("schema_version") == PRODUCED_MANIFEST_SCHEMA_VERSION
    if produced_manifest != produced_pointer:
        blockers.append("industry_pointer_manifest_schema_generation_mismatch")
    if set(manifest) != (
        produced_manifest_keys if produced_manifest else legacy_manifest_keys
    ):
        blockers.append("industry_manifest_schema_not_exact")
    if manifest.get("schema_version") not in {
        MANIFEST_SCHEMA_VERSION,
        PRODUCED_MANIFEST_SCHEMA_VERSION,
    }:
        blockers.append("industry_manifest_schema_invalid")
    if manifest.get("manifest_digest") != _digest(manifest_material):
        blockers.append("industry_manifest_digest_invalid")
    if manifest.get("status") != "full_market_industry_membership_verified":
        blockers.append("industry_manifest_status_invalid")

    semantic_validation = _validated_semantic_authority()
    semantic_sha256 = str(semantic_validation.get("sha256") or "")
    blockers.extend(semantic_validation.get("blockers") or [])
    semantic_copy_path = _safe_relative_file(root, manifest.get("semantic_evidence_file"))
    semantic_copy_sha256 = _file_digest(semantic_copy_path) if semantic_copy_path else ""
    if (
        manifest.get("semantic_evidence_schema_version")
        != SEMANTIC_EVIDENCE_SCHEMA_VERSION
        or manifest.get("semantic_evidence_sha256") != semantic_sha256
        or pointer.get("semantic_evidence_sha256") != semantic_sha256
        or semantic_copy_sha256 != semantic_sha256
    ):
        blockers.append("industry_out_date_semantic_evidence_binding_invalid")

    artifact_path = _safe_relative_file(root, manifest.get("artifact_file"))
    artifact_sha256 = _file_digest(artifact_path) if artifact_path else ""
    artifact = _read_json(artifact_path) if artifact_path else None
    artifact = dict(artifact) if isinstance(artifact, Mapping) else {}
    raw_rows = artifact.get("rows")
    rows = (
        [dict(row) for row in raw_rows]
        if type(raw_rows) is list and all(type(row) is dict for row in raw_rows)
        else []
    )
    if set(artifact) != {"rows", "schema_version"} or artifact.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        blockers.append("industry_artifact_schema_invalid")
    if type(raw_rows) is not list or len(rows) != len(raw_rows):
        blockers.append("industry_artifact_rows_not_exact_objects")
    blockers.extend(
        _interval_blockers(
            rows,
            expected_symbols=symbols,
            validated_trade_date=validated_trade_date,
        )
    )

    raw_artifact_sha256 = ""
    call_ledger_sha256 = ""
    producer_binding: dict[str, Any] = {}
    raw_provider_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    if produced_manifest:
        raw_artifact_path = _safe_relative_file(
            root,
            manifest.get("raw_artifact_file"),
        )
        raw_artifact_sha256 = (
            _file_digest(raw_artifact_path) if raw_artifact_path else ""
        )
        raw_artifact = _read_json(raw_artifact_path) if raw_artifact_path else None
        raw_artifact = (
            dict(raw_artifact) if isinstance(raw_artifact, Mapping) else {}
        )
        raw_provider_rows_value = raw_artifact.get("rows")
        raw_provider_rows = (
            [dict(row) for row in raw_provider_rows_value]
            if type(raw_provider_rows_value) is list
            and all(type(row) is dict for row in raw_provider_rows_value)
            else []
        )
        if (
            set(raw_artifact) != {"rows", "schema_version"}
            or raw_artifact.get("schema_version") != RAW_ARTIFACT_SCHEMA_VERSION
            or type(raw_provider_rows_value) is not list
            or len(raw_provider_rows) != len(raw_provider_rows_value)
            or manifest.get("raw_artifact_schema_version")
            != RAW_ARTIFACT_SCHEMA_VERSION
            or type(manifest.get("raw_artifact_row_count")) is not int
            or manifest.get("raw_artifact_row_count") != len(raw_provider_rows)
            or manifest.get("raw_artifact_sha256") != raw_artifact_sha256
        ):
            blockers.append("industry_raw_artifact_binding_invalid")

        call_ledger_path = _safe_relative_file(
            root,
            manifest.get("call_ledger_file"),
        )
        call_ledger_sha256 = (
            _file_digest(call_ledger_path) if call_ledger_path else ""
        )
        call_ledger_artifact = (
            _read_json(call_ledger_path) if call_ledger_path else None
        )
        call_ledger_artifact = (
            dict(call_ledger_artifact)
            if isinstance(call_ledger_artifact, Mapping)
            else {}
        )
        ledger_rows_value = call_ledger_artifact.get("rows")
        ledger_rows = (
            [dict(row) for row in ledger_rows_value]
            if type(ledger_rows_value) is list
            and all(type(row) is dict for row in ledger_rows_value)
            else []
        )
        if (
            set(call_ledger_artifact) != {
                "ledger_digest",
                "rows",
                "schema_version",
            }
            or call_ledger_artifact.get("schema_version")
            != CALL_LEDGER_SCHEMA_VERSION
            or type(ledger_rows_value) is not list
            or len(ledger_rows) != len(ledger_rows_value)
            or call_ledger_artifact.get("ledger_digest") != _digest(ledger_rows)
            or manifest.get("call_ledger_schema_version")
            != CALL_LEDGER_SCHEMA_VERSION
            or type(manifest.get("call_ledger_call_count")) is not int
            or manifest.get("call_ledger_call_count") != len(ledger_rows)
            or manifest.get("call_ledger_sha256") != call_ledger_sha256
        ):
            blockers.append("industry_call_ledger_binding_invalid")

        producer_binding = (
            dict(manifest.get("producer_binding"))
            if type(manifest.get("producer_binding")) is dict
            else {}
        )
        expected_producer_binding_keys = {
            "artifact_sha256",
            "call_ledger_digest",
            "call_ledger_sha256",
            "collection_observed_at_utc",
            "execution_request_digest",
            "execution_request_scope_digest",
            "execution_request_task_id",
            "producer_head_full",
            "provider_scope_digest",
            "provider_version_digest",
            "raw_artifact_sha256",
            "schema_version",
            "semantic_evidence_sha256",
            "semantic_authority_signature_sha256",
            "universe_digest",
            "validated_trade_date",
        }
        if (
            set(producer_binding) != expected_producer_binding_keys
            or producer_binding.get("schema_version")
            != PRODUCER_BINDING_SCHEMA_VERSION
            or producer_binding.get("raw_artifact_sha256")
            != raw_artifact_sha256
            or producer_binding.get("artifact_sha256") != artifact_sha256
            or producer_binding.get("call_ledger_sha256") != call_ledger_sha256
            or producer_binding.get("call_ledger_digest")
            != call_ledger_artifact.get("ledger_digest")
            or producer_binding.get("semantic_evidence_sha256")
            != semantic_sha256
            or producer_binding.get("semantic_authority_signature_sha256")
            != semantic_validation.get("signature_sha256")
            or producer_binding.get("universe_digest") != universe_digest
            or producer_binding.get("validated_trade_date")
            != validated_trade_date
            or not re.fullmatch(
                r"[0-9a-f]{40}",
                str(producer_binding.get("producer_head_full") or ""),
            )
            or not all(
                _HEX_64.fullmatch(str(producer_binding.get(key) or ""))
                for key in (
                    "execution_request_digest",
                    "execution_request_scope_digest",
                    "provider_scope_digest",
                    "provider_version_digest",
                )
            )
            or type(producer_binding.get("execution_request_task_id")) is not str
            or not producer_binding.get("execution_request_task_id")
            or manifest.get("producer_binding_digest")
            != _digest(producer_binding)
        ):
            blockers.append("industry_producer_binding_invalid")
        observed_at = _utc_timestamp(producer_binding.get("collection_observed_at_utc"))
        if observed_at is None:
            blockers.append("industry_collection_observed_at_invalid")
        blockers.extend(
            _provider_ledger_replay_blockers(
                raw_provider_rows,
                rows,
                ledger_rows,
                observed_at=observed_at,
            )
        )

    as_of_date = _date(manifest.get("as_of_date"))
    exact_bindings = {
        "version_id": manifest.get("version_id"),
        "manifest_digest": manifest.get("manifest_digest"),
        "artifact_sha256": artifact_sha256,
        "scope_digest": manifest.get("scope_digest"),
        "source_version_digest": manifest.get("source_version_digest"),
        "semantic_evidence_sha256": semantic_sha256,
        "universe_digest": universe_digest,
        "validated_trade_date": validated_trade_date,
        "as_of_date": as_of_date,
    }
    if produced_manifest:
        exact_bindings.update(
            {
                "raw_artifact_sha256": raw_artifact_sha256,
                "call_ledger_sha256": call_ledger_sha256,
                "producer_binding_digest": manifest.get(
                    "producer_binding_digest"
                ),
                "execution_request_digest": producer_binding.get(
                    "execution_request_digest"
                ),
                "producer_head_full": producer_binding.get("producer_head_full"),
                "provider_scope_digest": producer_binding.get(
                    "provider_scope_digest"
                ),
                "provider_version_digest": producer_binding.get(
                    "provider_version_digest"
                ),
            }
        )
    for key, expected in exact_bindings.items():
        if pointer.get(key) != expected:
            blockers.append(f"industry_pointer_manifest_{key}_mismatch")
    if manifest.get("artifact_sha256") != artifact_sha256:
        blockers.append("industry_artifact_digest_mismatch")
    if (
        type(manifest.get("artifact_row_count")) is not int
        or manifest.get("artifact_row_count") != len(rows)
    ):
        blockers.append("industry_artifact_row_count_mismatch")
    if manifest.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        blockers.append("industry_artifact_version_binding_invalid")
    if manifest.get("source_api") != SOURCE_API or manifest.get("source_scope") != SOURCE_SCOPE:
        blockers.append("industry_source_api_or_scope_invalid")
    version_id = manifest.get("version_id")
    if type(version_id) is not str or not _VERSION_ID.fullmatch(version_id):
        blockers.append("industry_version_id_invalid")
    if produced_manifest:
        last_good_id = pointer.get("last_good_generation")
        last_good_file = pointer.get("last_good_manifest_file")
        last_good_path = _safe_relative_file(root, last_good_file)
        last_good = _read_json(last_good_path) if last_good_path else None
        last_good = dict(last_good) if isinstance(last_good, Mapping) else {}
        last_good_binding = (
            pointer.get("last_good_binding")
            if type(pointer.get("last_good_binding")) is dict
            else {}
        )
        last_good_material = {
            key: value for key, value in last_good.items() if key != "manifest_digest"
        }
        if (
            pointer.get("current_generation") != version_id
            or pointer.get("manifest_file") != f"versions/{version_id}/manifest.json"
            or type(last_good_id) is not str
            or not _VERSION_ID.fullmatch(last_good_id)
            or last_good_file != f"versions/{last_good_id}/manifest.json"
            or last_good.get("schema_version") != PRODUCED_MANIFEST_SCHEMA_VERSION
            or last_good.get("version_id") != last_good_id
            or last_good.get("manifest_digest") != _digest(last_good_material)
            or pointer.get("last_good_manifest_digest")
            != last_good.get("manifest_digest")
            or set(last_good_binding) != GENERATION_BINDING_FIELDS
            or last_good_binding.get("current_generation") != last_good_id
            or last_good_binding.get("manifest_file") != last_good_file
            or last_good_binding.get("manifest_digest")
            != pointer.get("last_good_manifest_digest")
        ):
            blockers.append("industry_generation_pointer_recovery_binding_invalid")
        if last_good_id == version_id and (
            last_good != manifest
            or last_good_binding != _generation_binding(pointer)
        ):
            blockers.append("industry_generation_pointer_same_generation_split")
        if (
            _validate_last_good
            and type(last_good_id) is str
            and _VERSION_ID.fullmatch(last_good_id)
            and last_good_id != version_id
        ):
            recovery_pointer = {
                **last_good_binding,
                "schema_version": PRODUCED_POINTER_SCHEMA_VERSION,
                "version_id": last_good_id,
                "last_good_generation": last_good_id,
                "last_good_manifest_file": last_good_file,
                "last_good_manifest_digest": last_good.get("manifest_digest"),
                "last_good_binding": dict(last_good_binding),
            }
            recovery_pointer["pointer_digest"] = _digest(recovery_pointer)
            recovery = validate_full_market_industry_membership(
                evidence_root,
                expected_symbols=symbols,
                expected_universe_digest=universe_digest,
                expected_validated_trade_date=validated_trade_date,
                _pointer_override=recovery_pointer,
                _validate_last_good=False,
            )
            if recovery.get("ready") is not True:
                blockers.append("industry_generation_pointer_recovery_invalid")
                blockers.extend(recovery.get("blockers") or [])
    scope = manifest.get("scope") if type(manifest.get("scope")) is dict else {}
    expected_scope = {
        "schema_version": SCOPE_SCHEMA_VERSION,
        "source_api": SOURCE_API,
        "source_scope": SOURCE_SCOPE,
        "eligible_symbol_count": len(symbols),
        "exchanges": list(REQUIRED_EXCHANGES),
        "universe_digest": universe_digest,
        "validated_trade_date": validated_trade_date,
        "as_of_date": as_of_date,
    }
    if scope != expected_scope or manifest.get("scope_digest") != _digest(scope):
        blockers.append("industry_scope_binding_invalid")
    if not _HEX_64.fullmatch(str(manifest.get("scope_digest") or "")):
        blockers.append("industry_scope_digest_invalid")
    source_version = (
        manifest.get("source_version")
        if type(manifest.get("source_version")) is dict
        else {}
    )
    expected_source_version = {
        "schema_version": (
            PRODUCED_SOURCE_VERSION_SCHEMA_VERSION
            if produced_manifest
            else SOURCE_VERSION_SCHEMA_VERSION
        ),
        "version_id": version_id,
        "source_api": SOURCE_API,
        "source_scope": SOURCE_SCOPE,
        "scope_digest": manifest.get("scope_digest"),
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_sha256": artifact_sha256,
        "semantic_evidence_sha256": semantic_sha256,
    }
    if produced_manifest:
        expected_source_version.update(
            {
                "raw_artifact_schema_version": RAW_ARTIFACT_SCHEMA_VERSION,
                "raw_artifact_sha256": raw_artifact_sha256,
                "call_ledger_schema_version": CALL_LEDGER_SCHEMA_VERSION,
                "call_ledger_sha256": call_ledger_sha256,
                "producer_binding_digest": manifest.get(
                    "producer_binding_digest"
                ),
            }
        )
    if (
        source_version != expected_source_version
        or manifest.get("source_version_digest") != _digest(source_version)
    ):
        blockers.append("industry_source_version_binding_invalid")
    if not _HEX_64.fullmatch(str(manifest.get("source_version_digest") or "")):
        blockers.append("industry_source_version_digest_invalid")
    if manifest.get("universe_digest") != universe_digest:
        blockers.append("industry_universe_digest_mismatch")
    if (
        type(manifest.get("eligible_symbol_count")) is not int
        or manifest.get("eligible_symbol_count") != len(symbols)
    ):
        blockers.append("industry_eligible_symbol_count_mismatch")
    if (
        type(manifest.get("exchanges")) is not list
        or manifest.get("exchanges") != list(REQUIRED_EXCHANGES)
    ):
        blockers.append("industry_three_exchange_manifest_invalid")
    if manifest.get("validated_trade_date") != validated_trade_date:
        blockers.append("industry_validated_trade_date_mismatch")
    if not as_of_date or as_of_date != validated_trade_date:
        blockers.append("industry_as_of_date_not_current_validated_trade_date")
    if (
        manifest.get("out_date_semantics") != RESOLVED_OUT_DATE_SEMANTICS
        or manifest.get("out_date_semantics_validated") is not True
        or manifest.get("out_date_semantics_evidence_digest") != semantic_sha256
    ):
        blockers.append("industry_out_date_semantics_unresolved")

    blockers = list(dict.fromkeys(blockers))
    ready = not blockers
    return {
        "ready": ready,
        "status": (
            "full_market_industry_membership_verified"
            if ready
            else "full_market_industry_membership_blocked"
        ),
        "source_api": SOURCE_API,
        "source_scope": SOURCE_SCOPE,
        "version_id": str(manifest.get("version_id") or ""),
        "scope_digest": str(manifest.get("scope_digest") or ""),
        "source_version_digest": str(manifest.get("source_version_digest") or ""),
        "artifact_sha256": artifact_sha256,
        "universe_digest": universe_digest,
        "manifest_digest": str(manifest.get("manifest_digest") or ""),
        "pointer_digest": str(pointer.get("pointer_digest") or ""),
        "semantic_evidence_sha256": semantic_sha256,
        "raw_artifact_sha256": raw_artifact_sha256,
        "call_ledger_sha256": call_ledger_sha256,
        "producer_binding_digest": str(
            manifest.get("producer_binding_digest") or ""
        ),
        "execution_request_digest": str(
            producer_binding.get("execution_request_digest") or ""
        ),
        "eligible_symbol_count": len(symbols),
        "exchanges": sorted({_exchange(symbol) for symbol in symbols if _exchange(symbol)}),
        "validated_trade_date": validated_trade_date,
        "as_of_date": as_of_date,
        "out_date_semantics": str(manifest.get("out_date_semantics") or "unresolved"),
        "small_pool_raw_evidence_accepted": False,
        "production_industry_verified": ready,
        "blockers": blockers,
        "read_only": True,
        "writes_storage": False,
        "provider_execution_triggered": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }


def read_full_market_industry_membership_status(
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """GET-safe composition of provider universe and industry evidence."""

    evidence_root = evidence_root or EVIDENCE_ROOT
    try:
        from server.services.tushare_production_store import (
            validate_tushare_full_market_production_version,
        )

        upstream = validate_tushare_full_market_production_version(evidence_root)
    except Exception as exc:
        upstream = {
            "ready": False,
            "symbols": [],
            "universe_digest": "",
            "validated_trade_date": "",
            "blockers": [f"upstream_provider_verifier_failed_{type(exc).__name__}"],
        }
    result = validate_full_market_industry_membership(
        evidence_root,
        expected_symbols=upstream.get("symbols") or [],
        expected_universe_digest=upstream.get("universe_digest") or "",
        expected_validated_trade_date=upstream.get("validated_trade_date") or "",
    )
    if upstream.get("ready") is not True:
        result["ready"] = False
        result["production_industry_verified"] = False
        result["status"] = "full_market_industry_membership_blocked"
        result["blockers"] = list(
            dict.fromkeys(
                ["upstream_full_market_provider_universe_not_ready"]
                + list(upstream.get("blockers") or [])
                + list(result.get("blockers") or [])
            )
        )
    return result


def create_full_market_industry_membership_execution_request(
    payload: Any = None,
    *,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Create a local request ticket; never execute or self-seal evidence."""

    evidence_root = evidence_root or EVIDENCE_ROOT
    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    try:
        from server.services.tushare_production_store import (
            validate_tushare_full_market_production_version,
        )

        upstream = validate_tushare_full_market_production_version(evidence_root)
    except Exception:
        upstream = {"ready": False, "symbols": [], "blockers": ["provider_universe_unavailable"]}
    symbols, duplicates, invalid = _symbols(upstream.get("symbols") or [])
    provider_scope_digest = str(upstream.get("scope_hash") or "").strip().lower()
    provider_version_digest = str(
        upstream.get("version_digest")
        or upstream.get("artifact_manifest_digest")
        or ""
    ).strip().lower()
    head_full = _current_head_full()
    request_nonce = str(payload_map.get("request_nonce") or "").strip().lower()
    try:
        parsed_nonce = uuid.UUID(request_nonce)
        nonce_valid = parsed_nonce.version == 4 and str(parsed_nonce) == request_nonce
    except (ValueError, AttributeError, TypeError):
        nonce_valid = False
    exchanges = sorted({_exchange(symbol) for symbol in symbols if _exchange(symbol)})
    request_ready = bool(
        payload_map.get("create_execution_request") is True
        and payload_map.get("acknowledge_no_provider_execution") is True
        and nonce_valid
        and upstream.get("ready") is True
        and not duplicates
        and not invalid
        and len(symbols) >= MINIMUM_ELIGIBLE_SYMBOLS
        and exchanges == list(REQUIRED_EXCHANGES)
        and upstream.get("universe_count") == len(symbols)
        and _date(upstream.get("validated_trade_date"))
        and upstream.get("universe_digest") == _digest(symbols)
        and _HEX_64.fullmatch(provider_scope_digest)
        and _HEX_64.fullmatch(provider_version_digest)
        and re.fullmatch(r"[0-9a-f]{40}", head_full)
    )
    scope = {
        "schema_version": "full_market_industry_membership_scope.v1",
        "source_api": SOURCE_API,
        "source_scope": SOURCE_SCOPE,
        "eligible_symbol_count": len(symbols),
        "exchanges": exchanges,
        "universe_digest": str(upstream.get("universe_digest") or ""),
        "provider_scope_digest": provider_scope_digest,
        "provider_version_digest": provider_version_digest,
        "validated_trade_date": _date(upstream.get("validated_trade_date")),
        "requested_out_date_semantics": "unresolved_requires_independent_evidence",
    }
    receipt = {
        "schema_version": EXECUTION_REQUEST_SCHEMA_VERSION,
        "status": (
            "full_market_industry_membership_execution_requested"
            if request_ready
            else "full_market_industry_membership_execution_request_blocked"
        ),
        "task_type": EXECUTION_REQUEST_TASK_TYPE,
        "request_nonce": request_nonce if nonce_valid else "",
        "head_full": head_full,
        "scope": scope,
        "scope_digest": _digest(scope),
        "request_ready": request_ready,
        "provider_execution_triggered": False,
        "provider_task_created": False,
        "production_pointer_written": False,
        "production_industry_verified": False,
        "small_pool_raw_evidence_accepted": False,
        "out_date_semantics_resolved": False,
        "anns_d_required": False,
        "writes_storage": True,
        "writes_only_task_status": True,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "blockers": [] if request_ready else ["execution_request_contract_not_satisfied"],
        "call_ledger": [
            {
                "api": "local_full_market_industry_membership_execution_request",
                "call_status": "request_created" if request_ready else "blocked",
                "external_calls_triggered": False,
                "writes_production_pointer": False,
                "does_not_execute_trades": True,
            }
        ],
    }
    receipt["request_digest"] = _execution_request_digest(receipt)
    task = create_task_record(
        EXECUTION_REQUEST_TASK_TYPE,
        output_packet_key="command_center_3_full_market_industry_membership_execution_request",
        payload={"execution_request": receipt},
        current_step="full_market_industry_membership_execution_request_created",
        warnings=[
            "该 POST 只创建本地 execution-request；不会调用 index_member_all，也不会写生产 pointer。",
            "小池 raw rows 与 out_date 未定义证据不能满足全市场 PIT 行业分类生产合同。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    updated = update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=str(receipt["status"]),
        call_ledger=list(receipt["call_ledger"]),
    ) or task
    updated["payload_safe"] = {"execution_request": receipt}
    return updated




__all__ = (
    "EXECUTION_REQUEST_TASK_TYPE",
    "INDUSTRY_BINDING_DIGEST_KEYS",
    "MINIMUM_ELIGIBLE_SYMBOLS",
    "create_full_market_industry_membership_execution_request",
    "read_full_market_industry_membership_status",
    "validate_full_market_industry_membership",
)
