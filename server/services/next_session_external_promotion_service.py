"""Verify externally provisioned LTG-08 authority and seal local events.

This module owns no signing key and never creates approval or high-water
artifacts.  Production operators provision two root-owned, read-only signed
JSON envelopes outside the repository.  The application may append a local
event only when both envelopes exactly bind the current prerequisite digest.
"""

from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import json
import os
import re
import stat
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.constant_time import bytes_eq

from . import external_production_attestation_service as external_trust


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
TRUST_ROOT = external_trust.TRUST_ROOT
APPROVAL_PATH = TRUST_ROOT / "next-session-replacement-approval.json"
HIGH_WATER_PATH = TRUST_ROOT / "next-session-replacement-high-water.json"
JOURNAL_NAME = "next_session_replacement_promotion"
EVENTS_NAME = "events"
LOCK_NAME = "append.lock"
SCOPE = "ltg08_next_session_current_head_production_replacement"
APPROVAL_ENVELOPE_SCHEMA = "next_session_external_approval_envelope.v1"
APPROVAL_STATEMENT_SCHEMA = "next_session_external_approval_statement.v1"
HIGH_WATER_ENVELOPE_SCHEMA = "next_session_external_high_water_envelope.v1"
HIGH_WATER_STATEMENT_SCHEMA = "next_session_external_high_water_statement.v1"
EVENT_SCHEMA = "next_session_production_replacement_event.v2"
TRUSTED_OWNER_UIDS = frozenset({0})
_HEAD = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_EVENT_FILE = re.compile(r"^[0-9]{8}\.json$")
_ENVELOPE_FIELDS = {
    "schema_version",
    "algorithm",
    "key_fingerprint_sha256",
    "statement",
    "signature_base64",
}
_APPROVAL_FIELDS = {
    "schema_version",
    "status",
    "scope",
    "head_full",
    "semantic_digest",
    "review_id",
    "approval_id",
    "nonce_digest",
    "approved_by_user",
    "issued_at",
    "expires_at",
}
_HIGH_WATER_FIELDS = {
    "schema_version",
    "status",
    "scope",
    "head_full",
    "semantic_digest",
    "event_id",
    "sequence_no",
    "previous_event_id",
    "approval_id",
    "nonce_digest",
    "issued_at",
}
_EVENT_FIELDS = {
    "schema_version",
    "status",
    "scope",
    "sequence_no",
    "event_id",
    "previous_event_id",
    "head_full",
    "semantic_digest",
    "next_packet_digest",
    "motion_pair_digest",
    "streamlit_retirement_digest",
    "remote_ci_digest",
    "remote_run_id",
    "remote_artifact_digest",
    "release_promotion_event_id",
    "approval_id",
    "approval_review_id",
    "approval_nonce_digest",
    "approval_signature_digest",
    "high_water_signature_digest",
    "key_fingerprint_sha256",
    "recorded_at_utc",
    "approval_envelope",
    "high_water_envelope",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _timestamp(value: object) -> datetime | None:
    text = str(value or "")
    if not text.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _read_trusted_json(path: Path) -> tuple[dict[str, Any], str]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {}, "missing"
    except OSError:
        return {}, "unreadable"
    if not (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and metadata.st_uid in TRUSTED_OWNER_UIDS
        and stat.S_IMODE(metadata.st_mode) & 0o222 == 0
        and metadata.st_nlink == 1
        and metadata.st_size <= 1024 * 1024
    ):
        return {}, "untrusted_file"
    flags = os.O_RDONLY | int(getattr(os, "O_CLOEXEC", 0)) | int(getattr(os, "O_NOFOLLOW", 0))
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if opened.st_dev != metadata.st_dev or opened.st_ino != metadata.st_ino:
            return {}, "file_changed_during_read"
        data = os.read(descriptor, metadata.st_size + 1)
        value = json.loads(data)
        return (dict(value), "verified_read") if isinstance(value, Mapping) else ({}, "invalid_json")
    except Exception:
        return {}, "unreadable"
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _directory_ready(path: Path, *, private: bool) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    permissions = stat.S_IMODE(metadata.st_mode)
    return bool(
        stat.S_ISDIR(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and metadata.st_uid == os.getuid()
        and (permissions == 0o700 if private else permissions & 0o022 == 0)
    )


def _read_local_event(path: Path) -> tuple[dict[str, Any], os.stat_result | None]:
    try:
        before = path.lstat()
    except OSError:
        return {}, None
    if not (
        stat.S_ISREG(before.st_mode)
        and not stat.S_ISLNK(before.st_mode)
        and stat.S_IMODE(before.st_mode) == 0o600
        and before.st_uid == os.getuid()
        and before.st_nlink == 1
        and before.st_size <= 4 * 1024 * 1024
    ):
        return {}, None
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | int(getattr(os, "O_CLOEXEC", 0)) | int(getattr(os, "O_NOFOLLOW", 0)),
        )
        opened = os.fstat(descriptor)
        if (
            opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or opened.st_size != before.st_size
        ):
            return {}, None
        data = os.read(descriptor, before.st_size + 1)
        value = json.loads(data)
        return (dict(value), opened) if isinstance(value, Mapping) else ({}, None)
    except Exception:
        return {}, None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _verify_signature(envelope: Mapping[str, Any], *, schema: str) -> tuple[bool, str, str]:
    if set(envelope) != _ENVELOPE_FIELDS or envelope.get("schema_version") != schema:
        return False, "external_envelope_shape_invalid", ""
    if envelope.get("algorithm") != "Ed25519":
        return False, "external_envelope_algorithm_invalid", ""
    key, trust = external_trust._load_trusted_public_key()
    if key is None:
        return False, str(trust.get("status") or "external_public_key_unavailable"), ""
    fingerprint = str(trust.get("key_fingerprint_sha256") or "")
    if not (
        _DIGEST.fullmatch(fingerprint)
        and isinstance(envelope.get("key_fingerprint_sha256"), str)
        and bytes_eq(
            str(envelope.get("key_fingerprint_sha256")).encode("ascii", "ignore"),
            fingerprint.encode("ascii"),
        )
    ):
        return False, "external_envelope_key_fingerprint_mismatch", ""
    try:
        signature = base64.b64decode(str(envelope.get("signature_base64") or ""), validate=True)
    except (ValueError, binascii.Error):
        return False, "external_envelope_signature_encoding_invalid", ""
    if len(signature) != 64:
        return False, "external_envelope_signature_length_invalid", ""
    statement = envelope.get("statement")
    if not isinstance(statement, Mapping):
        return False, "external_envelope_statement_invalid", ""
    try:
        key.verify(signature, _canonical_bytes(statement))
    except InvalidSignature:
        return False, "external_envelope_signature_invalid", ""
    except Exception:
        return False, "external_envelope_verification_failed", ""
    return True, "external_envelope_signature_verified", hashlib.sha256(signature).hexdigest()


def _review_id(head_full: str, semantic_digest: str) -> str:
    return _digest({"scope": SCOPE, "head_full": head_full, "semantic_digest": semantic_digest})


def _read_events(evidence_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    events_root = evidence_root / JOURNAL_NAME / EVENTS_NAME
    if not events_root.exists():
        return [], []
    try:
        metadata = events_root.lstat()
        paths = sorted(events_root.iterdir())
    except OSError:
        return [], ["next_session_promotion_events_unreadable"]
    if not (
        stat.S_ISDIR(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) == 0o700
        and metadata.st_uid == os.getuid()
    ):
        return [], ["next_session_promotion_events_directory_invalid"]
    if any(not _EVENT_FILE.fullmatch(path.name) for path in paths):
        return [], ["next_session_promotion_event_set_invalid"]
    events: list[dict[str, Any]] = []
    previous_id = ""
    nonces: set[str] = set()
    blockers: list[str] = []
    for sequence, path in enumerate(paths, start=1):
        value, metadata = _read_local_event(path)
        if metadata is None:
            blockers.append("next_session_promotion_event_unreadable")
            break
        if not (
            path.name == f"{sequence:08d}.json"
            and isinstance(value, Mapping)
            and set(value) == _EVENT_FIELDS
        ):
            blockers.append("next_session_promotion_event_schema_invalid")
            break
        event = dict(value)
        approval = event.get("approval_envelope")
        high_water = event.get("high_water_envelope")
        approval_ok, approval_status, approval_signature_digest = _verify_signature(
            approval if isinstance(approval, Mapping) else {},
            schema=APPROVAL_ENVELOPE_SCHEMA,
        )
        high_water_ok, high_water_status, high_water_signature_digest = _verify_signature(
            high_water if isinstance(high_water, Mapping) else {},
            schema=HIGH_WATER_ENVELOPE_SCHEMA,
        )
        approval_statement = approval.get("statement") if isinstance(approval, Mapping) else {}
        high_water_statement = high_water.get("statement") if isinstance(high_water, Mapping) else {}
        if not approval_ok:
            blockers.append(approval_status)
        if not high_water_ok:
            blockers.append(high_water_status)
        proposal = {
            "scope": event.get("scope"),
            "sequence_no": event.get("sequence_no"),
            "previous_event_id": event.get("previous_event_id"),
            "head_full": event.get("head_full"),
            "semantic_digest": event.get("semantic_digest"),
            "approval_id": event.get("approval_id"),
            "approval_review_id": event.get("approval_review_id"),
            "approval_nonce_digest": event.get("approval_nonce_digest"),
        }
        expected_event_id = _digest(proposal)
        expected_semantic_digest = _digest(
            {
                "scope": event.get("scope"),
                "head_full": event.get("head_full"),
                "next_packet_digest": event.get("next_packet_digest"),
                "motion_pair_digest": event.get("motion_pair_digest"),
                "streamlit_retirement_digest": event.get("streamlit_retirement_digest"),
                "remote_ci_digest": event.get("remote_ci_digest"),
                "remote_run_id": event.get("remote_run_id"),
                "remote_artifact_digest": event.get("remote_artifact_digest"),
                "release_promotion_event_id": event.get("release_promotion_event_id"),
            }
        )
        nonce = str(event.get("approval_nonce_digest") or "")
        if not (
            event.get("schema_version") == EVENT_SCHEMA
            and event.get("status") == "next_session_production_replacement_promoted"
            and event.get("scope") == SCOPE
            and event.get("sequence_no") == sequence
            and event.get("previous_event_id") == previous_id
            and event.get("event_id") == expected_event_id
            and event.get("semantic_digest") == expected_semantic_digest
            and _HEAD.fullmatch(str(event.get("head_full") or ""))
            and _DIGEST.fullmatch(str(event.get("semantic_digest") or ""))
            and _DIGEST.fullmatch(nonce)
            and nonce not in nonces
            and event.get("approval_signature_digest") == approval_signature_digest
            and event.get("high_water_signature_digest") == high_water_signature_digest
            and event.get("key_fingerprint_sha256") == approval.get("key_fingerprint_sha256")
            and approval.get("key_fingerprint_sha256") == high_water.get("key_fingerprint_sha256")
            and isinstance(approval_statement, Mapping)
            and isinstance(high_water_statement, Mapping)
            and approval_statement.get("approval_id") == event.get("approval_id")
            and approval_statement.get("review_id") == event.get("approval_review_id")
            and approval_statement.get("nonce_digest") == nonce
            and high_water_statement.get("event_id") == event.get("event_id")
            and high_water_statement.get("sequence_no") == sequence
            and high_water_statement.get("previous_event_id") == previous_id
            and high_water_statement.get("approval_id") == event.get("approval_id")
            and high_water_statement.get("nonce_digest") == nonce
            and high_water_statement.get("head_full") == event.get("head_full")
            and high_water_statement.get("semantic_digest") == event.get("semantic_digest")
            and event.get("recorded_at_utc") == high_water_statement.get("issued_at")
        ):
            blockers.append("next_session_promotion_event_authentication_failed")
            break
        events.append(event)
        previous_id = str(event["event_id"])
        nonces.add(nonce)
    return events if not blockers else [], sorted(set(blockers))


def build_proposal(prerequisites: Mapping[str, Any], evidence_root: Path | str) -> dict[str, Any]:
    root = Path(evidence_root).expanduser().absolute()
    events, blockers = _read_events(root)
    head_full = str(prerequisites.get("head_full") or "")
    semantic_digest = str(prerequisites.get("semantic_digest") or "")
    material = prerequisites.get("material")
    material = dict(material) if isinstance(material, Mapping) else {}
    if (
        prerequisites.get("ready") is not True
        or not _HEAD.fullmatch(head_full)
        or not _DIGEST.fullmatch(semantic_digest)
        or material.get("scope") != SCOPE
        or material.get("head_full") != head_full
        or _digest(material) != semantic_digest
    ):
        blockers.append("next_session_promotion_prerequisites_not_ready")
    sequence_no = len(events) + 1
    previous_event_id = str(events[-1].get("event_id") or "") if events else ""
    review_id = _review_id(head_full, semantic_digest) if not blockers else ""
    return {
        "ready": not blockers,
        "scope": SCOPE,
        "sequence_no": sequence_no,
        "previous_event_id": previous_event_id,
        "head_full": head_full,
        "semantic_digest": semantic_digest,
        "approval_review_id": review_id,
        "blockers": sorted(set(blockers)),
    }


def _verify_external_pair(
    proposal: Mapping[str, Any],
    *,
    enforce_freshness: bool,
) -> dict[str, Any]:
    approval, approval_read_status = _read_trusted_json(APPROVAL_PATH)
    high_water, high_water_read_status = _read_trusted_json(HIGH_WATER_PATH)
    blockers: list[str] = []
    if approval_read_status != "verified_read":
        blockers.append(f"external_next_session_approval_{approval_read_status}")
    if high_water_read_status != "verified_read":
        blockers.append(f"external_next_session_high_water_{high_water_read_status}")
    approval_ok, approval_status, approval_signature_digest = _verify_signature(
        approval,
        schema=APPROVAL_ENVELOPE_SCHEMA,
    )
    high_water_ok, high_water_status, high_water_signature_digest = _verify_signature(
        high_water,
        schema=HIGH_WATER_ENVELOPE_SCHEMA,
    )
    if not approval_ok:
        blockers.append(approval_status)
    if not high_water_ok:
        blockers.append(high_water_status)
    approval_statement = approval.get("statement") if isinstance(approval.get("statement"), Mapping) else {}
    high_water_statement = high_water.get("statement") if isinstance(high_water.get("statement"), Mapping) else {}
    if set(approval_statement) != _APPROVAL_FIELDS:
        blockers.append("external_next_session_approval_statement_shape_invalid")
    if set(high_water_statement) != _HIGH_WATER_FIELDS:
        blockers.append("external_next_session_high_water_statement_shape_invalid")
    approval_material = {
        key: approval_statement.get(key)
        for key in sorted(_APPROVAL_FIELDS - {"approval_id"})
    }
    approval_id = _digest(approval_material) if set(approval_statement) == _APPROVAL_FIELDS else ""
    issued_at = _timestamp(approval_statement.get("issued_at"))
    expires_at = _timestamp(approval_statement.get("expires_at"))
    high_water_issued_at = _timestamp(high_water_statement.get("issued_at"))
    if not (
        approval_statement.get("schema_version") == APPROVAL_STATEMENT_SCHEMA
        and approval_statement.get("status") == "next_session_replacement_approved"
        and approval_statement.get("scope") == SCOPE
        and approval_statement.get("head_full") == proposal.get("head_full")
        and approval_statement.get("semantic_digest") == proposal.get("semantic_digest")
        and approval_statement.get("review_id") == proposal.get("approval_review_id")
        and approval_statement.get("approval_id") == approval_id
        and _DIGEST.fullmatch(approval_id)
        and _DIGEST.fullmatch(str(approval_statement.get("nonce_digest") or ""))
        and approval_statement.get("approved_by_user") is True
        and issued_at is not None
        and expires_at is not None
        and issued_at < expires_at
        and (expires_at - issued_at).total_seconds() <= 900
    ):
        blockers.append("external_next_session_approval_contract_invalid")
    event_proposal = {
        "scope": SCOPE,
        "sequence_no": proposal.get("sequence_no"),
        "previous_event_id": proposal.get("previous_event_id"),
        "head_full": proposal.get("head_full"),
        "semantic_digest": proposal.get("semantic_digest"),
        "approval_id": approval_id,
        "approval_review_id": proposal.get("approval_review_id"),
        "approval_nonce_digest": approval_statement.get("nonce_digest"),
    }
    event_id = _digest(event_proposal)
    if not (
        high_water_statement.get("schema_version") == HIGH_WATER_STATEMENT_SCHEMA
        and high_water_statement.get("status") == "next_session_replacement_high_water_committed"
        and high_water_statement.get("scope") == SCOPE
        and high_water_statement.get("head_full") == proposal.get("head_full")
        and high_water_statement.get("semantic_digest") == proposal.get("semantic_digest")
        and high_water_statement.get("event_id") == event_id
        and high_water_statement.get("sequence_no") == proposal.get("sequence_no")
        and high_water_statement.get("previous_event_id") == proposal.get("previous_event_id")
        and high_water_statement.get("approval_id") == approval_id
        and high_water_statement.get("nonce_digest") == approval_statement.get("nonce_digest")
        and high_water_issued_at is not None
        and issued_at is not None
        and expires_at is not None
        and issued_at <= high_water_issued_at <= expires_at
    ):
        blockers.append("external_next_session_high_water_contract_invalid")
    if enforce_freshness and issued_at is not None and expires_at is not None:
        now = datetime.now(timezone.utc)
        if not (issued_at <= now <= expires_at):
            blockers.append("external_next_session_approval_expired_or_not_yet_valid")
    return {
        "ready": not blockers,
        "event_id": event_id if not blockers else "",
        "approval_id": approval_id if not blockers else "",
        "nonce_digest": str(approval_statement.get("nonce_digest") or "") if not blockers else "",
        "approval_signature_digest": approval_signature_digest if not blockers else "",
        "high_water_signature_digest": high_water_signature_digest if not blockers else "",
        "key_fingerprint_sha256": str(approval.get("key_fingerprint_sha256") or "") if not blockers else "",
        "recorded_at_utc": str(high_water_statement.get("issued_at") or "") if not blockers else "",
        "approval_envelope": approval if not blockers else {},
        "high_water_envelope": high_water if not blockers else {},
        "blockers": sorted(set(blockers)),
    }


def validate_current_promotion(
    prerequisites: Mapping[str, Any],
    *,
    evidence_root: Path | str = EVIDENCE_ROOT,
) -> dict[str, Any]:
    root = Path(evidence_root).expanduser().absolute()
    events, blockers = _read_events(root)
    proposal = build_proposal(prerequisites, root)
    latest = events[-1] if events else {}
    if not latest:
        blockers.append("next_session_production_replacement_event_missing")
    elif not (
        latest.get("head_full") == prerequisites.get("head_full")
        and latest.get("semantic_digest") == prerequisites.get("semantic_digest")
    ):
        blockers.append("next_session_production_replacement_event_not_current")
    external_pair = _verify_external_pair(
        {
            "scope": SCOPE,
            "sequence_no": latest.get("sequence_no"),
            "previous_event_id": latest.get("previous_event_id"),
            "head_full": latest.get("head_full"),
            "semantic_digest": latest.get("semantic_digest"),
            "approval_review_id": latest.get("approval_review_id"),
        },
        enforce_freshness=False,
    ) if latest else {"ready": False, "blockers": ["external_next_session_authority_missing"]}
    blockers.extend(external_pair.get("blockers") or [])
    if latest and not (
        external_pair.get("ready") is True
        and external_pair.get("event_id") == latest.get("event_id")
        and external_pair.get("approval_envelope") == latest.get("approval_envelope")
        and external_pair.get("high_water_envelope") == latest.get("high_water_envelope")
    ):
        blockers.append("next_session_external_high_water_does_not_match_latest_event")
    ready = bool(prerequisites.get("ready") is True and latest and not blockers)
    return {
        "ready": ready,
        "production_replacement_complete": ready,
        "status": "next_session_production_replacement_promoted_current_head"
        if ready
        else "next_session_production_replacement_blocked",
        "event": latest if ready else {},
        "event_count": len(events),
        "proposal": proposal,
        "external_approval_verified": external_pair.get("ready") is True,
        "rollback_resistant_high_water_verified": external_pair.get("ready") is True,
        "blockers": sorted(set(blockers)),
        "writes_storage": False,
        "private_key_generated": False,
        "private_key_loaded": False,
        "contains_secret": False,
    }


def _reconcile_event_commit(
    event_path: Path,
    event: Mapping[str, Any],
    prerequisites: Mapping[str, Any],
    *,
    evidence_root: Path,
    write_error: bool,
) -> dict[str, Any]:
    """Return success only when the exact committed event is current and valid."""

    readback, _metadata = _read_local_event(event_path)
    if readback != dict(event):
        # A hard-link commit can succeed before temporary-link cleanup fails.
        # Verify those exact bytes without trusting the extra link, then replace
        # only the formal path with a fresh single-link inode containing the
        # same canonical event.  The orphan remains outside the event set.
        try:
            metadata = event_path.lstat()
            descriptor = os.open(
                event_path,
                os.O_RDONLY
                | int(getattr(os, "O_CLOEXEC", 0))
                | int(getattr(os, "O_NOFOLLOW", 0)),
            )
            try:
                raw = os.read(descriptor, metadata.st_size + 1)
            finally:
                os.close(descriptor)
            raw_value = json.loads(raw)
            if not (
                stat.S_ISREG(metadata.st_mode)
                and not stat.S_ISLNK(metadata.st_mode)
                and stat.S_IMODE(metadata.st_mode) == 0o600
                and metadata.st_uid == os.getuid()
                and metadata.st_nlink > 1
                and raw_value == dict(event)
            ):
                raise OSError("postcommit_event_not_exact")
            repair = event_path.parent.parent / f".reconcile.{uuid.uuid4().hex}.tmp"
            repair_descriptor = os.open(
                repair,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | int(getattr(os, "O_CLOEXEC", 0))
                | int(getattr(os, "O_NOFOLLOW", 0)),
                0o600,
            )
            try:
                data = _canonical_bytes(event) + b"\n"
                offset = 0
                while offset < len(data):
                    offset += os.write(repair_descriptor, data[offset:])
                os.fsync(repair_descriptor)
            finally:
                os.close(repair_descriptor)
            os.replace(repair, event_path)
            readback, _metadata = _read_local_event(event_path)
        except (OSError, ValueError, json.JSONDecodeError):
            readback = {}
    if readback != dict(event):
        return {
            "ready": False,
            "status": "next_session_production_replacement_event_write_failed",
            "promotion_written": False,
            "blockers": [
                "next_session_promotion_event_postcommit_readback_mismatch"
                if event_path.exists()
                else "next_session_promotion_event_exclusive_write_failed"
            ],
        }
    validated = validate_current_promotion(prerequisites, evidence_root=evidence_root)
    if not (
        validated.get("ready") is True
        and validated.get("event", {}).get("event_id") == event.get("event_id")
    ):
        return {
            **validated,
            "ready": False,
            "promotion_written": False,
            "blockers": sorted(
                set(
                    [
                        *(validated.get("blockers") or []),
                        "next_session_promotion_event_postcommit_validation_failed",
                    ]
                )
            ),
        }
    return {
        **validated,
        "promotion_written": True,
        "event_id": str(event.get("event_id") or ""),
        "postcommit_reconciled": write_error,
    }


def append_promotion_event(
    payload: Any,
    prerequisites: Mapping[str, Any],
    *,
    evidence_root: Path | str = EVIDENCE_ROOT,
) -> dict[str, Any]:
    request = dict(payload) if isinstance(payload, Mapping) else {}
    if set(request) != {"approved_by_user"} or request.get("approved_by_user") is not True:
        return {
            "ready": False,
            "status": "next_session_production_replacement_approval_action_required",
            "promotion_written": False,
            "blockers": ["explicit_user_next_session_replacement_approval_required"],
        }
    root = Path(evidence_root).expanduser().absolute()
    initial_proposal = build_proposal(prerequisites, root)
    if initial_proposal.get("ready") is not True:
        return {
            "ready": False,
            "status": "next_session_production_replacement_prerequisites_blocked",
            "promotion_written": False,
            "blockers": initial_proposal.get("blockers") or [],
        }
    journal_root = root / JOURNAL_NAME
    events_root = journal_root / EVENTS_NAME
    try:
        if root.exists() and not _directory_ready(root, private=False):
            raise OSError("evidence_root_invalid")
        root.mkdir(mode=0o700, exist_ok=True)
        if not _directory_ready(root, private=False):
            raise OSError("evidence_root_invalid")
        if journal_root.exists() and not _directory_ready(journal_root, private=True):
            raise OSError("journal_root_invalid")
        journal_root.mkdir(mode=0o700, exist_ok=True)
        if not _directory_ready(journal_root, private=True):
            raise OSError("journal_root_invalid")
        if events_root.exists() and not _directory_ready(events_root, private=True):
            raise OSError("events_root_invalid")
        events_root.mkdir(mode=0o700, exist_ok=True)
        if not _directory_ready(events_root, private=True):
            raise OSError("events_root_invalid")
    except OSError:
        return {
            "ready": False,
            "status": "next_session_production_replacement_journal_unavailable",
            "promotion_written": False,
            "blockers": ["next_session_promotion_journal_directory_invalid"],
        }
    lock_path = journal_root / LOCK_NAME
    lock_descriptor = -1
    try:
        lock_descriptor = os.open(
            lock_path,
            os.O_RDWR
            | os.O_CREAT
            | int(getattr(os, "O_CLOEXEC", 0))
            | int(getattr(os, "O_NOFOLLOW", 0)),
            0o600,
        )
        lock_metadata = os.fstat(lock_descriptor)
        if not (
            stat.S_ISREG(lock_metadata.st_mode)
            and stat.S_IMODE(lock_metadata.st_mode) == 0o600
            and lock_metadata.st_uid == os.getuid()
            and lock_metadata.st_nlink == 1
        ):
            raise OSError("lock_file_invalid")
    except OSError:
        if lock_descriptor >= 0:
            os.close(lock_descriptor)
        return {
            "ready": False,
            "status": "next_session_production_replacement_journal_unavailable",
            "promotion_written": False,
            "blockers": ["next_session_promotion_lock_file_invalid"],
        }
    with os.fdopen(lock_descriptor, "a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        proposal = build_proposal(prerequisites, root)
        if proposal.get("ready") is not True:
            return {
                "ready": False,
                "status": "next_session_production_replacement_prerequisites_blocked",
                "promotion_written": False,
                "blockers": proposal.get("blockers") or [],
            }
        external_pair = _verify_external_pair(proposal, enforce_freshness=True)
        if external_pair.get("ready") is not True:
            return {
                "ready": False,
                "status": "next_session_production_replacement_external_authority_blocked",
                "promotion_written": False,
                "blockers": external_pair.get("blockers") or [],
            }
        prior_events, event_blockers = _read_events(root)
        if event_blockers:
            return {
                "ready": False,
                "status": "next_session_production_replacement_journal_invalid",
                "promotion_written": False,
                "blockers": event_blockers,
            }
        if any(
            event.get("approval_nonce_digest") == external_pair.get("nonce_digest")
            for event in prior_events
        ):
            return {
                "ready": False,
                "status": "next_session_production_replacement_nonce_replayed",
                "promotion_written": False,
                "blockers": ["next_session_replacement_approval_nonce_replayed"],
            }
        material = prerequisites.get("material") if isinstance(prerequisites.get("material"), Mapping) else {}
        event = {
            "schema_version": EVENT_SCHEMA,
            "status": "next_session_production_replacement_promoted",
            "scope": SCOPE,
            "sequence_no": proposal["sequence_no"],
            "event_id": external_pair["event_id"],
            "previous_event_id": proposal["previous_event_id"],
            "head_full": proposal["head_full"],
            "semantic_digest": proposal["semantic_digest"],
            "next_packet_digest": str(material.get("next_packet_digest") or ""),
            "motion_pair_digest": str(material.get("motion_pair_digest") or ""),
            "streamlit_retirement_digest": str(material.get("streamlit_retirement_digest") or ""),
            "remote_ci_digest": str(material.get("remote_ci_digest") or ""),
            "remote_run_id": str(material.get("remote_run_id") or ""),
            "remote_artifact_digest": str(material.get("remote_artifact_digest") or ""),
            "release_promotion_event_id": str(material.get("release_promotion_event_id") or ""),
            "approval_id": external_pair["approval_id"],
            "approval_review_id": proposal["approval_review_id"],
            "approval_nonce_digest": external_pair["nonce_digest"],
            "approval_signature_digest": external_pair["approval_signature_digest"],
            "high_water_signature_digest": external_pair["high_water_signature_digest"],
            "key_fingerprint_sha256": external_pair["key_fingerprint_sha256"],
            "recorded_at_utc": external_pair["recorded_at_utc"],
            "approval_envelope": external_pair["approval_envelope"],
            "high_water_envelope": external_pair["high_water_envelope"],
        }
        event_path = events_root / f"{proposal['sequence_no']:08d}.json"
        temporary = journal_root / f".{event_path.name}.{uuid.uuid4().hex}.tmp"
        descriptor = -1
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | int(getattr(os, "O_NOFOLLOW", 0)),
                0o600,
            )
            data = _canonical_bytes(event) + b"\n"
            offset = 0
            while offset < len(data):
                offset += os.write(descriptor, data[offset:])
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            os.link(temporary, event_path, follow_symlinks=False)
            temporary.unlink()
        except OSError:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            return _reconcile_event_commit(
                event_path,
                event,
                prerequisites,
                evidence_root=root,
                write_error=True,
            )
    return _reconcile_event_commit(
        event_path,
        event,
        prerequisites,
        evidence_root=root,
        write_error=False,
    )


__all__ = ["append_promotion_event", "build_proposal", "validate_current_promotion"]
