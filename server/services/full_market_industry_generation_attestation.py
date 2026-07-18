from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.constant_time import bytes_eq

from . import external_production_attestation_service as external_trust


TRUST_ROOT = external_trust.TRUST_ROOT / "industry-generation"
PUBLIC_KEY_PATH = TRUST_ROOT / "ed25519-public.pem"
FINGERPRINT_PATH = TRUST_ROOT / "ed25519-public.sha256"
HISTORY_PATH = TRUST_ROOT / "attestation-history.json"
TRUSTED_OWNER_UIDS = frozenset({0})

HISTORY_SCHEMA_VERSION = "industry_generation_attestation_history.v1"
ENVELOPE_SCHEMA_VERSION = "industry_generation_attestation_envelope.v1"
STATEMENT_SCHEMA_VERSION = "industry_generation_attestation_statement.v1"
ZERO_DIGEST = "0" * 64
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^[0-9]{8}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_VERSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ENVELOPE_FIELDS = {
    "algorithm",
    "key_fingerprint_sha256",
    "schema_version",
    "signature_base64",
    "statement",
}
_STATEMENT_FIELDS = {
    "artifact_sha256",
    "attestation_kind",
    "call_ledger_sha256",
    "execution_request_digest",
    "execution_request_scope_digest",
    "execution_request_task_id",
    "expires_at_utc",
    "generation_id",
    "issued_at_utc",
    "manifest_digest",
    "previous_attestation_digest",
    "producer_binding_digest",
    "producer_head_full",
    "provider_scope_digest",
    "provider_version_digest",
    "raw_artifact_sha256",
    "schema_version",
    "semantic_authority_sha256",
    "semantic_authority_signature_sha256",
    "source_version_digest",
    "universe_digest",
    "validated_trade_date",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _timestamp(value: Any) -> dt.datetime | None:
    if type(value) is not str:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _trusted_path(path: Path, *, directory: bool) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(metadata.st_mode) or metadata.st_uid not in TRUSTED_OWNER_UIDS:
        return False
    if directory:
        return stat.S_ISDIR(metadata.st_mode) and not stat.S_IMODE(metadata.st_mode) & 0o022
    return (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_nlink == 1
        and not stat.S_IMODE(metadata.st_mode) & 0o222
        and metadata.st_size <= 4 * 1024 * 1024
    )


def _read_trusted(path: Path) -> bytes | None:
    if not _trusted_path(TRUST_ROOT, directory=True) or not _trusted_path(
        path, directory=False
    ):
        return None
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            value = handle.read(4 * 1024 * 1024 + 1)
    except OSError:
        return None
    return value if len(value) <= 4 * 1024 * 1024 else None


def _trusted_public_key() -> tuple[Ed25519PublicKey | None, str]:
    key_bytes = _read_trusted(PUBLIC_KEY_PATH)
    fingerprint_bytes = _read_trusted(FINGERPRINT_PATH)
    if key_bytes is None or fingerprint_bytes is None:
        return None, ""
    fingerprint = fingerprint_bytes.decode("ascii", errors="ignore").strip().lower()
    try:
        key = serialization.load_pem_public_key(key_bytes)
        der = key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    except (TypeError, ValueError):
        return None, ""
    actual = hashlib.sha256(der).hexdigest()
    if (
        not isinstance(key, Ed25519PublicKey)
        or not _HEX_64.fullmatch(fingerprint)
        or not bytes_eq(actual.encode("ascii"), fingerprint.encode("ascii"))
    ):
        return None, ""
    return key, actual


def generation_claims(
    manifest: Mapping[str, Any],
    *,
    previous_attestation_digest: str,
) -> dict[str, Any]:
    producer = (
        manifest.get("producer_binding")
        if type(manifest.get("producer_binding")) is dict
        else {}
    )
    return {
        "schema_version": STATEMENT_SCHEMA_VERSION,
        "attestation_kind": "full_market_industry_generation",
        "generation_id": manifest.get("version_id"),
        "manifest_digest": manifest.get("manifest_digest"),
        "producer_binding_digest": manifest.get("producer_binding_digest"),
        "source_version_digest": manifest.get("source_version_digest"),
        "artifact_sha256": manifest.get("artifact_sha256"),
        "raw_artifact_sha256": manifest.get("raw_artifact_sha256"),
        "call_ledger_sha256": manifest.get("call_ledger_sha256"),
        "provider_scope_digest": producer.get("provider_scope_digest"),
        "provider_version_digest": producer.get("provider_version_digest"),
        "producer_head_full": producer.get("producer_head_full"),
        "execution_request_digest": producer.get("execution_request_digest"),
        "execution_request_scope_digest": producer.get(
            "execution_request_scope_digest"
        ),
        "execution_request_task_id": producer.get("execution_request_task_id"),
        "universe_digest": manifest.get("universe_digest"),
        "validated_trade_date": manifest.get("validated_trade_date"),
        "semantic_authority_sha256": manifest.get("semantic_evidence_sha256"),
        "semantic_authority_signature_sha256": producer.get(
            "semantic_authority_signature_sha256"
        ),
        "previous_attestation_digest": previous_attestation_digest,
    }


def validate_generation_attestation(
    manifest: Mapping[str, Any],
    *,
    expected_previous_attestation_digest: str,
    require_latest: bool,
) -> dict[str, Any]:
    key, fingerprint = _trusted_public_key()
    history_bytes = _read_trusted(HISTORY_PATH)
    blockers: list[str] = []
    if key is None:
        blockers.append("industry_generation_attestation_public_key_unavailable")
    try:
        history = json.loads(history_bytes) if history_bytes is not None else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        history = None
    history = dict(history) if type(history) is dict else {}
    events_value = history.get("events")
    events = events_value if type(events_value) is list else []
    if (
        set(history) != {"events", "history_digest", "schema_version"}
        or history.get("schema_version") != HISTORY_SCHEMA_VERSION
        or type(events_value) is not list
        or history.get("history_digest") != _digest(events)
    ):
        blockers.append("industry_generation_attestation_history_invalid")
    previous = ZERO_DIGEST
    seen_generations: set[str] = set()
    verified_events: list[dict[str, Any]] = []
    now = dt.datetime.now(dt.timezone.utc)
    for envelope_value in events:
        envelope = envelope_value if type(envelope_value) is dict else {}
        statement = (
            envelope.get("statement")
            if type(envelope.get("statement")) is dict
            else {}
        )
        issued = _timestamp(statement.get("issued_at_utc"))
        expires = _timestamp(statement.get("expires_at_utc"))
        generation_id = statement.get("generation_id")
        signature = b""
        try:
            signature = base64.b64decode(
                str(envelope.get("signature_base64") or ""), validate=True
            )
            if len(signature) != 64 or key is None:
                raise ValueError("invalid generation signature")
            key.verify(signature, _canonical_bytes(statement))
        except (ValueError, binascii.Error, InvalidSignature):
            blockers.append("industry_generation_attestation_signature_invalid")
        if (
            set(envelope) != _ENVELOPE_FIELDS
            or envelope.get("schema_version") != ENVELOPE_SCHEMA_VERSION
            or envelope.get("algorithm") != "Ed25519"
            or envelope.get("key_fingerprint_sha256") != fingerprint
            or set(statement) != _STATEMENT_FIELDS
            or statement.get("schema_version") != STATEMENT_SCHEMA_VERSION
            or statement.get("attestation_kind")
            != "full_market_industry_generation"
            or not _VERSION_ID.fullmatch(str(generation_id or ""))
            or generation_id in seen_generations
            or statement.get("previous_attestation_digest") != previous
            or issued is None
            or expires is None
            or issued > now + dt.timedelta(seconds=30)
            or issued >= expires
            or (expires - issued).total_seconds() > 366 * 24 * 60 * 60
            or not _HEX_40.fullmatch(str(statement.get("producer_head_full") or ""))
            or not _DATE.fullmatch(
                str(statement.get("validated_trade_date") or "")
            )
            or not _SAFE_ID.fullmatch(
                str(statement.get("execution_request_task_id") or "")
            )
            or not all(
                _HEX_64.fullmatch(str(statement.get(field) or ""))
                for field in _STATEMENT_FIELDS
                if field.endswith("_digest") or field.endswith("_sha256")
            )
        ):
            blockers.append("industry_generation_attestation_contract_invalid")
        attestation_digest = _digest(envelope)
        previous = attestation_digest
        if type(generation_id) is str:
            seen_generations.add(generation_id)
        verified_events.append(
            {
                "attestation_digest": attestation_digest,
                "statement": dict(statement),
            }
        )
    claims = generation_claims(
        manifest,
        previous_attestation_digest=expected_previous_attestation_digest,
    )
    target = next(
        (
            event
            for event in verified_events
            if event["statement"].get("generation_id") == manifest.get("version_id")
        ),
        None,
    )
    target_statement = target.get("statement") if target else {}
    target_contract = {
        key: value for key, value in target_statement.items() if key not in {
            "issued_at_utc",
            "expires_at_utc",
        }
    }
    if target is None or target_contract != claims:
        blockers.append("industry_generation_attestation_generation_binding_invalid")
    if target and require_latest and target is not verified_events[-1]:
        blockers.append("industry_generation_attestation_not_latest")
    if target and require_latest:
        expires = _timestamp(target_statement.get("expires_at_utc"))
        if expires is None or now > expires:
            blockers.append("industry_generation_attestation_expired")
    blockers = list(dict.fromkeys(blockers))
    return {
        "ready": not blockers,
        "attestation_digest": target.get("attestation_digest") if target else "",
        "previous_attestation_digest": target_statement.get(
            "previous_attestation_digest", ""
        ),
        "history_head_digest": previous,
        "claims": claims,
        "blockers": blockers,
        "semantic_authority_is_separate": True,
        "application_generates_generation_signatures": False,
    }
