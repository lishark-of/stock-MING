from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.constant_time import bytes_eq
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from storage.sqlite_meta import SQLiteMetaStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
REGISTRY_PACKET_KEY = "command_center_3_external_production_attestation_registry"
REGISTRY_SCHEMA_VERSION = "command_center_3_external_production_attestation_registry.v1"
ENVELOPE_SCHEMA_VERSION = "command_center_3_external_production_attestation_envelope.v1"
STATEMENT_SCHEMA_VERSION = "command_center_3_external_production_attestation_statement.v1"

# The application never writes this directory.  Production provisioning must
# install the public key and its fingerprint outside the repository under an
# independently administered, root-owned path.
TRUST_ROOT = Path("/Library/Application Support/stock-MING/production-trust")
TRUST_ANCHOR = Path("/Library/Application Support")
PUBLIC_KEY_PATH = TRUST_ROOT / "ed25519-public.pem"
FINGERPRINT_PATH = TRUST_ROOT / "ed25519-public.sha256"
IMPORT_LOCK_PATH = PROJECT_ROOT / ".stock_ming_3" / "external_trust" / "import.lock"
TRUSTED_OWNER_UIDS = frozenset({0})

PRODUCTION_TRUST_BLOCKERS = (
    "external_monotonic_anchor_unavailable",
    "trusted_head_key_epoch_unavailable",
    "production_consumer_not_wired",
)
CANONICAL_STORAGE_TTL_SECONDS = {
    "factor_values": 6 * 60 * 60,
    "daily": 24 * 60 * 60,
    "daily_basic": 24 * 60 * 60,
    "moneyflow": 24 * 60 * 60,
    "trade_cal": 14 * 24 * 60 * 60,
    "backtest_results": 30 * 24 * 60 * 60,
}
CANONICAL_STORAGE_DATASETS = frozenset(CANONICAL_STORAGE_TTL_SECONDS)
STORAGE_REFRESH_ATTESTATION_MAX_AGE_SECONDS = 15 * 60
FACTOR_RESULT_DATASET = "factor_values"
CANDIDATE_RADAR_PACKET_KEY = "command_center_3_candidate_radar_cache"


def _local_only_trust_state(*, local_integrity_ready: bool = False) -> dict[str, Any]:
    return {
        "ready": False,
        "local_integrity_ready": local_integrity_ready,
        "external_signature_verified": local_integrity_ready,
        "external_trust_verified": False,
        "production_trusted": False,
        "snapshot_rollback_resistant": False,
        "blockers": list(PRODUCTION_TRUST_BLOCKERS),
    }

ALLOWED_KINDS = frozenset(
    {
        "storage_ttl_resolution",
        "worker_runtime_lineage",
        "factor_full_market_lineage",
        "candidate_radar_lineage",
    }
)
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:/-]{1,160}$")
_ENVELOPE_KEYS = {
    "schema_version",
    "algorithm",
    "key_fingerprint_sha256",
    "statement",
    "signature_base64",
}
_STATEMENT_KEYS = {
    "schema_version",
    "attestation_kind",
    "head_full",
    "nonce_digest",
    "scope_hash",
    "task_id",
    "subject",
    "artifact_digest",
    "monotonic_counter",
    "previous_attestation_digest",
    "issued_at",
    "expires_at",
    "claims",
}
_SENSITIVE_KEY_FRAGMENTS = (
    "private",
    "password",
    "authorization",
    "bearer",
    "credential",
    "access_key",
    "api_key",
    "token",
    "secret",
)
_CLAIM_DIGEST_FIELDS = frozenset(
    {
        "redis_transport_digest",
        "celery_task_ids_digest",
        "universe_digest",
        "metric_validation_digest",
        "browser_evidence_digest",
        "performance_evidence_digest",
        "legacy_retirement_evidence_digest",
    }
)

_CLAIM_SCHEMAS: dict[str, dict[str, type | tuple[type, ...]]] = {
    "storage_ttl_resolution": {
        "dataset": str,
        "resolution": str,
        "refresh_task_id": str,
        "before_ttl_state": str,
        "after_ttl_state": str,
        "refresh_executed": bool,
        "provider_call_count": int,
        "fetched_at": str,
        "external_calls_triggered": bool,
        "does_not_execute_trades": bool,
    },
    "worker_runtime_lineage": {
        "worker_run_id": str,
        "redis_transport_digest": str,
        "celery_task_ids_digest": str,
        "eligible_worker_count": int,
        "batch_count": int,
        "row_count": int,
        "does_not_execute_trades": bool,
    },
    "factor_full_market_lineage": {
        "result_dataset": str,
        "result_version_id": str,
        "universe_digest": str,
        "universe_count": int,
        "metric_validation_digest": str,
        "full_market_factor_research": bool,
        "does_not_execute_trades": bool,
    },
    "candidate_radar_lineage": {
        "candidate_cache_packet_key": str,
        "cache_write_task_id": str,
        "universe_digest": str,
        "candidate_row_count": int,
        "browser_evidence_digest": str,
        "performance_evidence_digest": str,
        "legacy_retirement_evidence_digest": str,
        "candidate_radar_production_replacement": bool,
        "candidate_is_not_buy_instruction": bool,
        "does_not_execute_trades": bool,
    },
}


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(value: Mapping[str, Any]) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _digest_ready(value: Any) -> bool:
    text = str(value or "").lower()
    return bool(_HEX_64.fullmatch(text) and text != "0" * 64)


def _current_head_full() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""
    head = result.stdout.strip().lower()
    return head if _HEX_40.fullmatch(head) else ""


def _read_registry_no_init() -> tuple[dict[str, Any], str]:
    if not SQLITE_META_PATH.is_file():
        return {}, "meta_missing"
    connection: sqlite3.Connection | None = None
    try:
        uri = f"file:{SQLITE_META_PATH.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=2)
        row = connection.execute(
            "SELECT payload_json FROM packets WHERE packet_key = ?",
            (REGISTRY_PACKET_KEY,),
        ).fetchone()
        if not row:
            return {}, "packet_missing"
        value = json.loads(str(row[0]))
        return (dict(value), "packet_present") if isinstance(value, dict) else ({}, "packet_invalid")
    except Exception:
        return {}, "read_failed"
    finally:
        if connection is not None:
            connection.close()


def _trusted_path_status(path: Path, *, directory: bool) -> tuple[bool, str]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False, "missing"
    except Exception:
        return False, "stat_failed"
    if stat.S_ISLNK(metadata.st_mode):
        return False, "symlink_rejected"
    if directory and not stat.S_ISDIR(metadata.st_mode):
        return False, "not_directory"
    if not directory and not stat.S_ISREG(metadata.st_mode):
        return False, "not_regular_file"
    if metadata.st_uid not in TRUSTED_OWNER_UIDS:
        return False, "owner_untrusted"
    permissions = stat.S_IMODE(metadata.st_mode)
    if directory:
        if permissions & 0o022:
            return False, "directory_group_or_other_writable"
    elif permissions & 0o222:
        return False, "trusted_file_not_read_only"
    return True, "trusted"


def _load_trusted_public_key() -> tuple[Ed25519PublicKey | None, dict[str, Any]]:
    root_ready, root_status = _trusted_path_status(TRUST_ROOT, directory=True)
    key_ready, key_status = _trusted_path_status(PUBLIC_KEY_PATH, directory=False)
    fingerprint_ready, fingerprint_status = _trusted_path_status(FINGERPRINT_PATH, directory=False)
    base_status = {
        "trust_root_outside_repo": False,
        "trust_root_status": root_status,
        "public_key_status": key_status,
        "fingerprint_status": fingerprint_status,
        "private_key_generated": False,
        "private_key_loaded": False,
        "contains_secret": False,
    }
    try:
        root_resolved = TRUST_ROOT.resolve(strict=True)
        project_resolved = PROJECT_ROOT.resolve(strict=True)
        root_literal = TRUST_ROOT.absolute()
        anchor_literal = TRUST_ANCHOR.absolute()
        outside_repo = bool(
            root_literal.is_relative_to(anchor_literal)
            and not root_resolved.is_relative_to(project_resolved)
        )
    except Exception:
        outside_repo = False
    base_status["trust_root_outside_repo"] = outside_repo
    ancestor_chain_ready = False
    if outside_repo:
        current = root_literal
        ancestor_chain_ready = True
        while True:
            current_ready, _ = _trusted_path_status(current, directory=True)
            if not current_ready:
                ancestor_chain_ready = False
                break
            if current == anchor_literal:
                break
            if current.parent == current:
                ancestor_chain_ready = False
                break
            current = current.parent
    base_status["trusted_ancestor_chain_verified"] = ancestor_chain_ready
    if not (root_ready and key_ready and fingerprint_ready and outside_repo and ancestor_chain_ready):
        return None, {**base_status, "status": "external_trust_material_unavailable_or_untrusted"}
    try:
        key_bytes = PUBLIC_KEY_PATH.read_bytes()
        fingerprint_text = FINGERPRINT_PATH.read_text(encoding="ascii").strip().lower()
    except Exception:
        return None, {**base_status, "status": "external_trust_material_read_failed"}
    if len(key_bytes) > 16_384 or not _HEX_64.fullmatch(fingerprint_text):
        return None, {**base_status, "status": "external_trust_material_shape_invalid"}
    if b"PRIVATE KEY" in key_bytes:
        return None, {**base_status, "status": "private_key_material_rejected"}
    try:
        key = serialization.load_pem_public_key(key_bytes)
    except Exception:
        return None, {**base_status, "status": "external_public_key_parse_failed"}
    if not isinstance(key, Ed25519PublicKey):
        return None, {**base_status, "status": "external_public_key_algorithm_invalid"}
    actual_fingerprint = _sha256_bytes(
        key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    if not bytes_eq(actual_fingerprint.encode("ascii"), fingerprint_text.encode("ascii")):
        return None, {**base_status, "status": "external_public_key_fingerprint_mismatch"}
    return key, {
        **base_status,
        "status": "external_public_key_verified",
        "key_fingerprint_sha256": actual_fingerprint,
    }


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _claims_ready(
    kind: str,
    claims: Any,
    *,
    subject: str,
    issued_at: datetime | None,
) -> bool:
    if not isinstance(claims, Mapping):
        return False
    schema = _CLAIM_SCHEMAS.get(kind, {})
    if set(claims) != set(schema):
        return False
    if any(any(fragment in str(key).lower() for fragment in _SENSITIVE_KEY_FRAGMENTS) for key in claims):
        return False
    for key, expected_type in schema.items():
        value = claims.get(key)
        if isinstance(value, bool) and expected_type is int:
            return False
        if not isinstance(value, expected_type):
            return False
        if isinstance(value, str) and (not value or len(value) > 256):
            return False
        if isinstance(value, str) and any(fragment in value.lower() for fragment in _SENSITIVE_KEY_FRAGMENTS):
            return False
        if key in _CLAIM_DIGEST_FIELDS and not _digest_ready(value):
            return False
        if isinstance(value, int) and value < 0:
            return False
    if claims.get("does_not_execute_trades") is not True:
        return False
    if kind == "storage_ttl_resolution":
        if claims.get("dataset") != subject or subject not in CANONICAL_STORAGE_DATASETS:
            return False
        fetched_at = _parse_utc(claims.get("fetched_at"))
        if fetched_at is None or issued_at is None:
            return False
        age_seconds = (issued_at - fetched_at).total_seconds()
        if age_seconds < 0:
            return False
        resolution = claims.get("resolution")
        if resolution == "fresh_no_refresh_required":
            return bool(
                age_seconds <= CANONICAL_STORAGE_TTL_SECONDS[subject]
                and claims.get("before_ttl_state") == "fresh"
                and claims.get("after_ttl_state") == "fresh"
                and claims.get("refresh_executed") is False
                and claims.get("provider_call_count") == 0
                and claims.get("external_calls_triggered") is False
            )
        if resolution == "refreshed":
            return bool(
                age_seconds <= STORAGE_REFRESH_ATTESTATION_MAX_AGE_SECONDS
                and claims.get("before_ttl_state") in {"stale", "missing"}
                and claims.get("after_ttl_state") == "fresh"
                and claims.get("refresh_executed") is True
                and claims.get("provider_call_count") > 0
                and claims.get("external_calls_triggered") is True
            )
        return False
    if kind == "factor_full_market_lineage":
        return bool(
            claims.get("result_dataset") == FACTOR_RESULT_DATASET
            and claims.get("result_version_id") == subject
            and claims.get("universe_count", 0) >= 3000
            and claims.get("full_market_factor_research") is True
        )
    if kind == "worker_runtime_lineage":
        return bool(
            claims.get("worker_run_id") == subject
            and claims.get("eligible_worker_count", 0) > 0
            and claims.get("batch_count", 0) > 0
            and claims.get("row_count", 0) > 0
        )
    if kind == "candidate_radar_lineage":
        return bool(
            subject == CANDIDATE_RADAR_PACKET_KEY
            and claims.get("candidate_cache_packet_key") == subject
            and claims.get("candidate_row_count", 0) > 0
            and claims.get("candidate_radar_production_replacement") is True
            and claims.get("candidate_is_not_buy_instruction") is True
        )
    return True


def _verify_envelope(
    envelope: Any,
    *,
    prior_events: list[dict[str, Any]],
    enforce_freshness: bool,
    enforce_current_head: bool = True,
    expected_kind: str | None = None,
) -> dict[str, Any]:
    if not isinstance(envelope, Mapping) or set(envelope) != _ENVELOPE_KEYS:
        return {"ready": False, "status": "signed_envelope_shape_invalid"}
    statement = envelope.get("statement")
    if not isinstance(statement, Mapping) or set(statement) != _STATEMENT_KEYS:
        return {"ready": False, "status": "signed_statement_shape_invalid"}
    statement = dict(statement)
    kind = str(statement.get("attestation_kind") or "")
    head_full = str(statement.get("head_full") or "").lower()
    nonce_digest = str(statement.get("nonce_digest") or "").lower()
    scope_hash = str(statement.get("scope_hash") or "").lower()
    artifact_digest = str(statement.get("artifact_digest") or "").lower()
    task_id = str(statement.get("task_id") or "")
    subject = str(statement.get("subject") or "")
    previous_digest = str(statement.get("previous_attestation_digest") or "").lower()
    counter = statement.get("monotonic_counter")
    issued_at = _parse_utc(statement.get("issued_at"))
    expires_at = _parse_utc(statement.get("expires_at"))
    if not (
        envelope.get("schema_version") == ENVELOPE_SCHEMA_VERSION
        and envelope.get("algorithm") == "Ed25519"
        and statement.get("schema_version") == STATEMENT_SCHEMA_VERSION
        and kind in ALLOWED_KINDS
        and (expected_kind is None or kind == expected_kind)
        and _HEX_40.fullmatch(head_full)
        and (not enforce_current_head or head_full == _current_head_full())
        and _digest_ready(nonce_digest)
        and _digest_ready(scope_hash)
        and _digest_ready(artifact_digest)
        and _SAFE_ID.fullmatch(task_id)
        and _SAFE_ID.fullmatch(subject)
        and not any(fragment in task_id.lower() for fragment in _SENSITIVE_KEY_FRAGMENTS)
        and not any(fragment in subject.lower() for fragment in _SENSITIVE_KEY_FRAGMENTS)
        and isinstance(counter, int)
        and not isinstance(counter, bool)
        and 1 <= counter < 2**63
        and issued_at is not None
        and expires_at is not None
        and issued_at < expires_at
        and (expires_at - issued_at).total_seconds() <= 900
        and _claims_ready(
            kind,
            statement.get("claims"),
            subject=subject,
            issued_at=issued_at,
        )
        and (
            kind != "storage_ttl_resolution"
            or statement.get("claims", {}).get("refresh_task_id") == task_id
        )
        and (
            kind != "candidate_radar_lineage"
            or statement.get("claims", {}).get("cache_write_task_id") == task_id
        )
    ):
        return {"ready": False, "status": "signed_statement_contract_invalid"}
    if enforce_freshness:
        now = datetime.now(timezone.utc)
        if not (issued_at.timestamp() - 60 <= now.timestamp() <= expires_at.timestamp()):
            return {"ready": False, "status": "signed_statement_expired_or_not_yet_valid"}
    prior_last = prior_events[-1] if prior_events else {}
    expected_counter = int(prior_last.get("monotonic_counter") or 0) + 1
    expected_previous = str(prior_last.get("attestation_id") or "")
    if counter != expected_counter or previous_digest != expected_previous:
        return {"ready": False, "status": "signed_statement_monotonic_chain_invalid"}
    if any(row.get("nonce_digest") == nonce_digest for row in prior_events):
        return {"ready": False, "status": "signed_statement_nonce_replayed"}
    key, trust = _load_trusted_public_key()
    if key is None:
        return {**trust, "ready": False}
    if envelope.get("key_fingerprint_sha256") != trust.get("key_fingerprint_sha256"):
        return {**trust, "ready": False, "status": "signed_envelope_key_fingerprint_mismatch"}
    try:
        signature = base64.b64decode(str(envelope.get("signature_base64") or ""), validate=True)
    except (ValueError, binascii.Error):
        return {**trust, "ready": False, "status": "signed_envelope_signature_encoding_invalid"}
    if len(signature) != 64:
        return {**trust, "ready": False, "status": "signed_envelope_signature_length_invalid"}
    try:
        key.verify(signature, _canonical_bytes(statement))
    except InvalidSignature:
        return {**trust, "ready": False, "status": "signed_envelope_signature_invalid"}
    except Exception:
        return {**trust, "ready": False, "status": "signed_envelope_verification_failed"}
    attestation_id = _sha256(
        {
            "statement": statement,
            "key_fingerprint_sha256": trust["key_fingerprint_sha256"],
            "signature_sha256": _sha256_bytes(signature),
        }
    )
    return {
        "ready": True,
        "status": "external_production_attestation_verified",
        "attestation_id": attestation_id,
        "attestation_kind": kind,
        "head_full": head_full,
        "nonce_digest": nonce_digest,
        "scope_hash": scope_hash,
        "task_id": task_id,
        "subject": subject,
        "artifact_digest": artifact_digest,
        "monotonic_counter": counter,
        "previous_attestation_digest": previous_digest,
        "issued_at": statement["issued_at"],
        "expires_at": statement["expires_at"],
        "claims": dict(statement["claims"]),
        "key_fingerprint_sha256": trust["key_fingerprint_sha256"],
        "signature_sha256": _sha256_bytes(signature),
        "signed_envelope": dict(envelope),
        "local_integrity_ready": True,
        "external_trust_verified": False,
        "external_signature_verified": True,
        "production_trusted": False,
        "snapshot_rollback_resistant": False,
        "blockers": list(PRODUCTION_TRUST_BLOCKERS),
        "private_key_generated": False,
        "private_key_loaded": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
    }


def validate_registry() -> dict[str, Any]:
    source, read_status = _read_registry_no_init()
    events = source.get("events") if isinstance(source.get("events"), list) else []
    validated: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping) or not isinstance(event.get("signed_envelope"), Mapping):
            return {
                **_local_only_trust_state(),
                "status": "external_attestation_registry_event_invalid",
                "read_status": read_status,
                "event_count": len(events),
                "writes_performed": False,
                "private_key_generated": False,
                "private_key_loaded": False,
                "external_calls_triggered": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
            }
        result = _verify_envelope(
            event["signed_envelope"],
            prior_events=validated,
            enforce_freshness=False,
            enforce_current_head=False,
        )
        if not result.get("ready") or result.get("attestation_id") != event.get("attestation_id"):
            return {
                **_local_only_trust_state(),
                "status": "external_attestation_registry_chain_invalid",
                "read_status": read_status,
                "event_count": len(events),
                "writes_performed": False,
                "private_key_generated": False,
                "private_key_loaded": False,
                "external_calls_triggered": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
            }
        validated.append(result)
    local_integrity_ready = bool(
        source.get("schema_version") == REGISTRY_SCHEMA_VERSION
        and read_status == "packet_present"
        and events
        and len(events) == len(validated)
        and source.get("last_attestation_id") == validated[-1]["attestation_id"]
        and source.get("last_monotonic_counter") == validated[-1]["monotonic_counter"]
    )
    return {
        "ready": False,
        "local_integrity_ready": local_integrity_ready,
        "status": "external_attestation_registry_local_integrity_verified"
        if local_integrity_ready
        else "external_attestation_registry_missing_or_empty",
        "read_status": read_status,
        "head_full": _current_head_full(),
        "event_count": len(validated),
        "last_attestation_id": validated[-1]["attestation_id"] if validated else "",
        "last_monotonic_counter": validated[-1]["monotonic_counter"] if validated else 0,
        "events": validated if local_integrity_ready else [],
        "external_signature_verified": local_integrity_ready,
        "external_trust_verified": False,
        "production_trusted": False,
        "snapshot_rollback_resistant": False,
        "blockers": list(PRODUCTION_TRUST_BLOCKERS),
        "private_key_generated": False,
        "private_key_loaded": False,
        "writes_performed": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
    }


def import_signed_attestation(payload: Any, *, expected_kind: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or set(payload) != {"signed_envelope"}:
        return {
            **_local_only_trust_state(),
            "status": "signed_envelope_only_required",
            "writes_performed": False,
            "external_calls_triggered": False,
            "contains_secret": False,
            "does_not_execute_trades": True,
        }
    IMPORT_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with IMPORT_LOCK_PATH.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        registry = validate_registry()
        prior_events = registry.get("events") if registry.get("local_integrity_ready") is True else []
        if registry.get("read_status") not in {"meta_missing", "packet_missing", "packet_present"}:
            return {
                **_local_only_trust_state(),
                "status": "external_attestation_registry_fail_closed",
                "writes_performed": False,
                "external_calls_triggered": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
            }
        if (
            registry.get("read_status") == "packet_present"
            and registry.get("local_integrity_ready") is not True
        ):
            return {
                **_local_only_trust_state(),
                "status": "external_attestation_registry_existing_state_invalid",
                "writes_performed": False,
                "external_calls_triggered": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
            }
        envelope = payload["signed_envelope"]
        existing = next(
            (
                row
                for row in prior_events
                if isinstance(envelope, Mapping)
                and set(envelope) == _ENVELOPE_KEYS
                and isinstance(envelope.get("statement"), Mapping)
                and set(envelope["statement"]) == _STATEMENT_KEYS
                and row.get("signed_envelope") == envelope
            ),
            None,
        )
        if existing:
            if expected_kind is not None and existing.get("attestation_kind") != expected_kind:
                return {
                    **_local_only_trust_state(),
                    "status": "external_production_attestation_kind_mismatch",
                    "writes_performed": False,
                    "external_calls_triggered": False,
                    "contains_secret": False,
                    "does_not_execute_trades": True,
                }
            return {
                **existing,
                "ready": False,
                "local_integrity_ready": True,
                "external_signature_verified": True,
                "external_trust_verified": False,
                "production_trusted": False,
                "snapshot_rollback_resistant": False,
                "blockers": list(PRODUCTION_TRUST_BLOCKERS),
                "status": "external_attestation_already_imported_local_integrity_only",
                "writes_performed": False,
            }
        verified = _verify_envelope(
            envelope,
            prior_events=list(prior_events),
            enforce_freshness=True,
            expected_kind=expected_kind,
        )
        if verified.get("ready") is not True:
            return {
                **verified,
                **_local_only_trust_state(),
                "writes_performed": False,
                "external_calls_triggered": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
            }
        stored_event = dict(verified)
        stored_event.pop("ready", None)
        stored_event.pop("status", None)
        events = [*prior_events, stored_event]
        packet = {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "packet_key": REGISTRY_PACKET_KEY,
            "status": "external_attestation_registry_local_integrity_verified",
            "head_full": _current_head_full(),
            "event_count": len(events),
            "last_attestation_id": verified["attestation_id"],
            "last_monotonic_counter": verified["monotonic_counter"],
            "events": events,
            "external_signature_verified": True,
            "external_trust_verified": False,
            "production_trusted": False,
            "snapshot_rollback_resistant": False,
            "blockers": list(PRODUCTION_TRUST_BLOCKERS),
            "private_key_generated": False,
            "private_key_loaded": False,
            "external_calls_triggered": False,
            "contains_secret": False,
            "does_not_execute_trades": True,
        }
        try:
            SQLiteMetaStore(SQLITE_META_PATH).promote_packet_atomic(REGISTRY_PACKET_KEY, packet)
        except Exception:
            readback = validate_registry()
            if (
                readback.get("local_integrity_ready") is True
                and readback.get("last_attestation_id") == verified["attestation_id"]
                and readback.get("last_monotonic_counter") == verified["monotonic_counter"]
            ):
                return {
                    **verified,
                    "ready": False,
                    "local_integrity_ready": True,
                    "external_signature_verified": True,
                    "external_trust_verified": False,
                    "production_trusted": False,
                    "snapshot_rollback_resistant": False,
                    "blockers": list(PRODUCTION_TRUST_BLOCKERS),
                    "status": "external_attestation_imported_after_write_exception_reconciled",
                    "writes_performed": True,
                    "external_calls_triggered": False,
                }
            return {
                **_local_only_trust_state(),
                "status": "external_attestation_registry_write_failed",
                "writes_performed": False,
                "external_calls_triggered": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
            }
        readback = validate_registry()
        if not (
            readback.get("local_integrity_ready") is True
            and readback.get("last_attestation_id") == verified["attestation_id"]
            and readback.get("last_monotonic_counter") == verified["monotonic_counter"]
        ):
            return {
                **_local_only_trust_state(),
                "status": "external_attestation_registry_readback_failed",
                "writes_performed": True,
                "external_calls_triggered": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
            }
        return {
            **verified,
            "ready": False,
            "local_integrity_ready": True,
            "external_signature_verified": True,
            "external_trust_verified": False,
            "production_trusted": False,
            "snapshot_rollback_resistant": False,
            "blockers": list(PRODUCTION_TRUST_BLOCKERS),
            "status": "external_attestation_imported_local_integrity_only",
            "writes_performed": True,
            "external_calls_triggered": False,
        }


def validate_attested_lineage(
    *,
    attestation_kind: str,
    subject: str,
    scope_hash: str = "",
    task_id: str = "",
    artifact_digest: str = "",
) -> dict[str, Any]:
    attestation_kind = str(attestation_kind or "")
    subject = str(subject or "")
    scope_hash = str(scope_hash or "").lower()
    task_id = str(task_id or "")
    artifact_digest = str(artifact_digest or "").lower()
    bindings_ready = bool(
        attestation_kind in ALLOWED_KINDS
        and _SAFE_ID.fullmatch(subject)
        and _digest_ready(scope_hash)
        and _SAFE_ID.fullmatch(task_id)
        and _digest_ready(artifact_digest)
    )
    registry = validate_registry()
    event = next(
        (
            row
            for row in reversed(registry.get("events") or [])
            if row.get("attestation_kind") == attestation_kind
            and row.get("subject") == subject
        ),
        None,
    )
    current_head = _current_head_full()
    local_integrity_ready = bool(
        bindings_ready
        and event
        and event.get("head_full") == current_head
        and event.get("scope_hash") == scope_hash
        and event.get("task_id") == task_id
        and event.get("artifact_digest") == artifact_digest
    )
    return {
        "ready": False,
        "local_integrity_ready": bool(
            registry.get("local_integrity_ready") is True and local_integrity_ready
        ),
        "status": "external_attested_lineage_local_integrity_only"
        if local_integrity_ready
        else (
            "external_attested_lineage_exact_bindings_required"
            if not bindings_ready
            else "external_attested_lineage_missing_or_mismatch"
        ),
        "attestation_kind": attestation_kind,
        "subject": subject,
        "head_full": event.get("head_full") if isinstance(event, Mapping) else "",
        "attestation_id": event.get("attestation_id") if isinstance(event, Mapping) else "",
        "scope_hash": event.get("scope_hash") if isinstance(event, Mapping) else "",
        "task_id": event.get("task_id") if isinstance(event, Mapping) else "",
        "artifact_digest": event.get("artifact_digest") if isinstance(event, Mapping) else "",
        "claims": dict(event.get("claims") or {}) if isinstance(event, Mapping) else {},
        "external_signature_verified": bool(
            registry.get("local_integrity_ready") is True and local_integrity_ready
        ),
        "external_trust_verified": False,
        "production_trusted": False,
        "snapshot_rollback_resistant": False,
        "blockers": list(PRODUCTION_TRUST_BLOCKERS),
        "private_key_generated": False,
        "private_key_loaded": False,
        "writes_performed": False,
        "external_calls_triggered": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
    }


def read_external_attestation_status() -> dict[str, Any]:
    registry = validate_registry()
    return {
        "packet_key": REGISTRY_PACKET_KEY,
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "status": registry.get("status"),
        "ready": False,
        "local_integrity_ready": registry.get("local_integrity_ready") is True,
        "head_full": registry.get("head_full") or _current_head_full(),
        "event_count": int(registry.get("event_count") or 0),
        "last_monotonic_counter": int(registry.get("last_monotonic_counter") or 0),
        "attestation_kinds": sorted(
            {
                str(row.get("attestation_kind") or "")
                for row in registry.get("events") or []
                if row.get("attestation_kind")
            }
        ),
        "get_writes_performed": False,
        "external_signature_verified": registry.get("local_integrity_ready") is True,
        "external_trust_verified": False,
        "production_trusted": False,
        "snapshot_rollback_resistant": False,
        "blockers": list(PRODUCTION_TRUST_BLOCKERS),
        "private_key_generated": False,
        "private_key_loaded": False,
        "external_calls_triggered": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "contract": external_attestation_contract(),
    }


def external_attestation_contract() -> dict[str, Any]:
    """Return the sanitized, shared consumer contract without trust material."""

    return {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "algorithm": "Ed25519",
        "allowed_attestation_kinds": sorted(ALLOWED_KINDS),
        "required_bindings": [
            "exact_current_head_full",
            "fresh_unique_nonce_digest",
            "scope_hash",
            "task_id",
            "subject",
            "artifact_digest",
            "monotonic_counter",
            "previous_attestation_digest",
        ],
        "claim_fields_by_kind": {
            kind: sorted(schema)
            for kind, schema in sorted(_CLAIM_SCHEMAS.items())
        },
        "planned_consumers": ["storage", "worker", "factor", "candidate_radar"],
        "production_consumers_wired": [],
        "post_accepts_signed_envelope_only": True,
        "caller_boolean_cannot_promote": True,
        "local_hmac_cannot_promote": True,
        "external_signature_is_local_integrity_only": True,
        "production_trusted": False,
        "snapshot_rollback_resistant": False,
        "production_blockers": list(PRODUCTION_TRUST_BLOCKERS),
        "application_generates_private_key": False,
        "application_loads_private_key": False,
        "get_writes_performed": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
    }
