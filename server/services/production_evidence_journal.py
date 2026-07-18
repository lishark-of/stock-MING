from __future__ import annotations

import datetime as _dt
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRUST_ROOT = PROJECT_ROOT / ".stock_ming_3" / "production_evidence_trust"
KEY_PATH = TRUST_ROOT / "journal.key"
JOURNAL_PATH = TRUST_ROOT / "journal.jsonl"
STATE_PATH = TRUST_ROOT / "state.json"
LOCK_PATH = TRUST_ROOT / "journal.lock"

EVENT_SCHEMA_VERSION = "command_center_3_production_evidence_event.v1"
STATE_SCHEMA_VERSION = "command_center_3_production_evidence_state.v1"
ALLOWED_EVENT_TYPES = {
    "storage_ttl_dataset_resolution",
    "worker_runtime_execution_request",
    "worker_runtime_execution",
    "worker_production_promotion_review",
}
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def current_head_full() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""
    head = completed.stdout.strip().lower()
    return head if _HEX_40.fullmatch(head) else ""


def authorization_nonce_digest(raw_nonce: str) -> str:
    return hashlib.sha256(str(raw_nonce).encode("utf-8")).hexdigest() if raw_nonce else ""


def authorization_nonce_is_strong(raw_nonce: str) -> bool:
    nonce = str(raw_nonce)
    return bool(
        len(nonce) >= 32
        and len(set(nonce)) >= 12
        and not nonce.isspace()
        and nonce.lower() not in {"0" * len(nonce), "1" * len(nonce), "a" * len(nonce)}
    )


def _event_without_mac(event: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dict(event).items() if key != "event_mac"}


def _event_identity_material(event: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dict(event).items() if key not in {"event_id", "event_mac"}}


def _state_without_mac(state: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dict(state).items() if key != "state_mac"}


def _atomic_write(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
    finally:
        temporary.unlink(missing_ok=True)


def _append_line(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, mode)
    try:
        with os.fdopen(descriptor, "ab", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(path, mode)
    except Exception:
        raise


def _load_key(*, create: bool) -> bytes:
    try:
        key = KEY_PATH.read_bytes()
    except FileNotFoundError:
        if not create:
            return b""
        TRUST_ROOT.mkdir(parents=True, exist_ok=True)
        key = os.urandom(32)
        _atomic_write(KEY_PATH, key)
    except Exception:
        return b""
    return key if len(key) == 32 else b""


def _read_events() -> list[dict[str, Any]]:
    if not JOURNAL_PATH.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with JOURNAL_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    return []
                events.append(value)
    except Exception:
        return []
    return events


def _read_state() -> dict[str, Any]:
    try:
        value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def validate_journal() -> dict[str, Any]:
    key = _load_key(create=False)
    events = _read_events()
    state = _read_state()
    if not key or not events or not state:
        return {
            "ready": False,
            "local_integrity_ready": False,
            "production_trusted": False,
            "snapshot_rollback_resistant": False,
            "status": "production_evidence_journal_missing_or_empty",
            "event_count": 0,
            "last_event_mac": "",
            "writes_performed": False,
        }
    previous_mac = ""
    seen_ids: set[str] = set()
    seen_nonce_digests: set[str] = set()
    for index, event in enumerate(events, start=1):
        unsigned = _event_without_mac(event)
        expected_mac = hmac.new(key, _canonical_bytes(unsigned), hashlib.sha256).hexdigest()
        event_id = str(event.get("event_id") or "")
        nonce_digest = str(event.get("authorization_nonce_digest") or "")
        if not (
            event.get("schema_version") == EVENT_SCHEMA_VERSION
            and event.get("sequence") == index
            and event.get("event_type") in ALLOWED_EVENT_TYPES
            and _HEX_40.fullmatch(str(event.get("head_full") or ""))
            and _HEX_64.fullmatch(str(event.get("scope_hash") or ""))
            and _HEX_64.fullmatch(str(event.get("payload_digest") or ""))
            and _HEX_64.fullmatch(nonce_digest)
            and event.get("raw_nonce_stored") is False
            and "authorization_nonce" not in event
            and event.get("previous_event_mac") == previous_mac
            and event_id == _sha256(_event_identity_material(event))
            and event_id not in seen_ids
            and nonce_digest not in seen_nonce_digests
            and hmac.compare_digest(str(event.get("event_mac") or ""), expected_mac)
        ):
            return {
                "ready": False,
                "local_integrity_ready": False,
                "production_trusted": False,
                "snapshot_rollback_resistant": False,
                "status": "production_evidence_journal_invalid",
                "event_count": len(events),
                "invalid_sequence": index,
                "last_event_mac": previous_mac,
                "writes_performed": False,
            }
        seen_ids.add(event_id)
        seen_nonce_digests.add(nonce_digest)
        previous_mac = expected_mac
    expected_state_mac = hmac.new(key, _canonical_bytes(_state_without_mac(state)), hashlib.sha256).hexdigest()
    state_ready = bool(
        state.get("schema_version") == STATE_SCHEMA_VERSION
        and state.get("sequence") == len(events)
        and state.get("event_count") == len(events)
        and state.get("last_event_mac") == previous_mac
        and hmac.compare_digest(str(state.get("state_mac") or ""), expected_state_mac)
    )
    return {
        "ready": state_ready,
        "local_integrity_ready": state_ready,
        "production_trusted": False,
        "snapshot_rollback_resistant": False,
        "status": "production_evidence_journal_verified" if state_ready else "production_evidence_state_invalid",
        "event_count": len(events),
        "last_event_mac": previous_mac,
        "writes_performed": False,
        "events": events if state_ready else [],
    }


def record_event(
    *,
    event_type: str,
    expected_head_full: str,
    authorization_nonce: str,
    subject: str,
    scope_hash: str,
    payload_digest: str,
) -> dict[str, Any]:
    head_full = current_head_full()
    nonce_digest = authorization_nonce_digest(authorization_nonce)
    if event_type not in ALLOWED_EVENT_TYPES:
        return {"ready": False, "local_integrity_ready": False, "production_trusted": False, "status": "production_evidence_event_type_invalid", "writes_performed": False}
    if not (_HEX_40.fullmatch(expected_head_full) and expected_head_full == head_full):
        return {"ready": False, "local_integrity_ready": False, "production_trusted": False, "status": "production_evidence_head_mismatch", "writes_performed": False}
    if not authorization_nonce_is_strong(authorization_nonce):
        return {"ready": False, "local_integrity_ready": False, "production_trusted": False, "status": "production_evidence_nonce_weak_or_missing", "writes_performed": False}
    if not (_HEX_64.fullmatch(scope_hash) and _HEX_64.fullmatch(payload_digest)):
        return {"ready": False, "local_integrity_ready": False, "production_trusted": False, "status": "production_evidence_digest_invalid", "writes_performed": False}
    TRUST_ROOT.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        key = _load_key(create=True)
        if not key:
            return {"ready": False, "local_integrity_ready": False, "production_trusted": False, "status": "production_evidence_key_unavailable", "writes_performed": False}
        existing = validate_journal()
        events = existing.get("events") if existing.get("ready") is True else []
        if (JOURNAL_PATH.exists() or STATE_PATH.exists()) and existing.get("ready") is not True:
            return {"ready": False, "local_integrity_ready": False, "production_trusted": False, "status": "production_evidence_journal_fail_closed", "writes_performed": False}
        if any(row.get("authorization_nonce_digest") == nonce_digest for row in events):
            return {"ready": False, "local_integrity_ready": False, "production_trusted": False, "status": "production_evidence_nonce_already_consumed", "writes_performed": False}
        previous_mac = str(events[-1].get("event_mac") or "") if events else ""
        event = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "sequence": len(events) + 1,
            "event_type": event_type,
            "head_full": head_full,
            "subject": str(subject)[:160],
            "scope_hash": scope_hash,
            "payload_digest": payload_digest,
            "authorization_nonce_digest": nonce_digest,
            "raw_nonce_stored": False,
            "previous_event_mac": previous_mac,
            "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }
        event["event_id"] = _sha256(_event_identity_material(event))
        event["event_mac"] = hmac.new(key, _canonical_bytes(event), hashlib.sha256).hexdigest()
        _append_line(
            JOURNAL_PATH,
            (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"),
        )
        state = {
            "schema_version": STATE_SCHEMA_VERSION,
            "sequence": event["sequence"],
            "event_count": event["sequence"],
            "last_event_mac": event["event_mac"],
        }
        state["state_mac"] = hmac.new(key, _canonical_bytes(state), hashlib.sha256).hexdigest()
        try:
            _atomic_write(STATE_PATH, _canonical_bytes(state))
        except Exception:
            # The durable journal line may already exist.  Do not pretend the
            # event was committed and do not attempt an unsafe rollback; the
            # missing/mismatched state anchor deliberately makes subsequent
            # validation fail closed until trusted recovery.
            return {
                "ready": False,
                "local_integrity_ready": False,
                "production_trusted": False,
                "snapshot_rollback_resistant": False,
                "status": "production_evidence_state_write_failed_journal_fail_closed",
                "event_id": event["event_id"],
                "head_full": head_full,
                "writes_performed": True,
                "journal_append_succeeded": True,
                "state_anchor_write_succeeded": False,
                "trusted_recovery_required": True,
            }
        verified = validate_journal()
        if verified.get("ready") is not True:
            return {"ready": False, "local_integrity_ready": False, "production_trusted": False, "status": "production_evidence_event_post_write_validation_failed", "writes_performed": True}
        return {
            "ready": True,
            "local_integrity_ready": True,
            "production_trusted": False,
            "snapshot_rollback_resistant": False,
            "status": "production_evidence_event_recorded",
            "event_id": event["event_id"],
            "event_type": event_type,
            "head_full": head_full,
            "authorization_nonce_digest": nonce_digest,
            "raw_nonce_stored": False,
            "sequence": event["sequence"],
            "writes_performed": True,
        }


def validate_event(
    event_id: str,
    *,
    event_type: str,
    head_full: str,
    subject: str,
    scope_hash: str,
    payload_digest: str,
) -> dict[str, Any]:
    journal = validate_journal()
    match = next(
        (
            row
            for row in journal.get("events") or []
            if row.get("event_id") == event_id
            and row.get("event_type") == event_type
            and row.get("head_full") == head_full
            and row.get("subject") == subject
            and row.get("scope_hash") == scope_hash
            and row.get("payload_digest") == payload_digest
        ),
        None,
    )
    return {
        "ready": bool(journal.get("ready") is True and match),
        "local_integrity_ready": bool(journal.get("ready") is True and match),
        "production_trusted": False,
        "snapshot_rollback_resistant": False,
        "status": "production_evidence_event_verified" if match else "production_evidence_event_missing_or_mismatch",
        "journal_status": journal.get("status"),
        "event": dict(match) if isinstance(match, dict) else {},
        "writes_performed": False,
    }
