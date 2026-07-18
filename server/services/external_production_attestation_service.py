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
HEAD_KEY_EPOCH_SCHEMA_VERSION = "command_center_3_external_head_key_epoch.v1"
MONOTONIC_ANCHOR_SCHEMA_VERSION = "command_center_3_external_monotonic_high_water.v1"

# The application never writes this directory.  Production provisioning must
# install the public key and its fingerprint outside the repository under an
# independently administered, root-owned path.
TRUST_ROOT = Path("/Library/Application Support/stock-MING/production-trust")
TRUST_ANCHOR = Path("/Library/Application Support")
PUBLIC_KEY_PATH = TRUST_ROOT / "ed25519-public.pem"
FINGERPRINT_PATH = TRUST_ROOT / "ed25519-public.sha256"
KEY_HISTORY_ROOT = TRUST_ROOT / "key-history"
HEAD_KEY_EPOCH_PATH = TRUST_ROOT / "head-key-epoch.json"
MONOTONIC_ANCHOR_PATH = TRUST_ROOT / "monotonic-high-water.json"
IMPORT_LOCK_PATH = PROJECT_ROOT / ".stock_ming_3" / "external_trust" / "import.lock"
TRUSTED_OWNER_UIDS = frozenset({0})

PRODUCTION_TRUST_BLOCKERS = (
    "external_monotonic_anchor_unavailable",
    "trusted_head_key_epoch_unavailable",
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
FACTOR_RESULT_DATASET = "full_market_factor_research_results"
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
        "tushare_provider_execution_authorization",
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
_HEAD_KEY_EPOCH_KEYS = {
    "schema_version",
    "algorithm",
    "epoch",
    "head_full",
    "key_fingerprint_sha256",
    "valid_from",
    "expires_at",
    "nonce_digest",
    "previous_epoch_digest",
    "signature_base64",
}
_MONOTONIC_ANCHOR_KEYS = {
    "schema_version",
    "algorithm",
    "epoch",
    "head_full",
    "key_fingerprint_sha256",
    "epoch_digest",
    "monotonic_counter",
    "cas_previous_counter",
    "previous_attestation_digest",
    "cas_previous_attestation_digest",
    "attestation_id",
    "nonce_digest",
    "issued_at",
    "expires_at",
    "signature_base64",
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
        "candidate_cache_write_task_digest",
        "phase_a_packet_digest",
        "approval_scope_hash",
        "execution_recipe_scope_hash",
        "selected_api_digest",
        "target_group_digest",
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
        "phase_a_packet_digest": str,
        "phase_a_task_id": str,
        "external_calls_triggered": bool,
        "does_not_execute_trades": bool,
    },
    "worker_runtime_lineage": {
        "worker_run_id": str,
        "provider_version_digest": str,
        "universe_digest": str,
        "validated_trade_date": str,
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
        "candidate_cache_write_task_digest": str,
        "universe_digest": str,
        "candidate_row_count": int,
        "browser_evidence_digest": str,
        "performance_evidence_digest": str,
        "legacy_retirement_evidence_digest": str,
        "candidate_radar_production_replacement": bool,
        "candidate_is_not_buy_instruction": bool,
        "does_not_execute_trades": bool,
    },
    "tushare_provider_execution_authorization": {
        "approval_scope_hash": str,
        "execution_recipe_scope_hash": str,
        "selected_api_digest": str,
        "target_group_digest": str,
        "provider_attempt_id": str,
        "provider_version_id": str,
        "trade_cal_repeat_authorized": bool,
        "provider_max_calls": int,
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


def _current_clean_head_full() -> str:
    head = _current_head_full()
    if not head:
        return ""
    try:
        tracked_status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        return ""
    return head if not tracked_status else ""


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


def _load_trusted_event_public_key(
    *,
    epoch: Any,
    fingerprint: Any,
) -> tuple[Ed25519PublicKey | None, dict[str, Any]]:
    """Load the current key or an externally retained historical public key."""

    fingerprint_text = str(fingerprint or "").lower()
    if type(epoch) is not int or epoch < 1 or not _HEX_64.fullmatch(fingerprint_text):
        return None, {"status": "trusted_key_history_binding_invalid"}
    current_key, current_trust = _load_trusted_public_key()
    if current_key is None:
        return None, current_trust
    if current_trust.get("key_fingerprint_sha256") == fingerprint_text:
        return current_key, current_trust
    history_ready, history_status = _trusted_path_status(KEY_HISTORY_ROOT, directory=True)
    key_path = KEY_HISTORY_ROOT / f"{epoch:08d}-{fingerprint_text}.pem"
    key_ready, key_status = _trusted_path_status(key_path, directory=False)
    if not history_ready or not key_ready:
        return None, {
            "status": "trusted_key_history_material_unavailable_or_untrusted",
            "key_history_status": history_status,
            "historical_public_key_status": key_status,
        }
    try:
        key_bytes = key_path.read_bytes()
    except Exception:
        return None, {"status": "trusted_key_history_material_read_failed"}
    if len(key_bytes) > 16_384 or b"PRIVATE KEY" in key_bytes:
        return None, {"status": "trusted_key_history_material_shape_invalid"}
    try:
        key = serialization.load_pem_public_key(key_bytes)
    except Exception:
        return None, {"status": "trusted_key_history_public_key_parse_failed"}
    if not isinstance(key, Ed25519PublicKey):
        return None, {"status": "trusted_key_history_public_key_algorithm_invalid"}
    actual_fingerprint = _sha256_bytes(
        key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    if not bytes_eq(actual_fingerprint.encode("ascii"), fingerprint_text.encode("ascii")):
        return None, {"status": "trusted_key_history_public_key_fingerprint_mismatch"}
    return key, {
        "status": "trusted_historical_public_key_verified",
        "key_fingerprint_sha256": actual_fingerprint,
        "private_key_generated": False,
        "private_key_loaded": False,
        "contains_secret": False,
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


def _signed_document_material(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in document.items()
        if key != "signature_base64"
    }


def _verify_document_signature(
    key: Ed25519PublicKey,
    document: Mapping[str, Any],
) -> bool:
    try:
        signature = base64.b64decode(
            str(document.get("signature_base64") or ""),
            validate=True,
        )
        if len(signature) != 64:
            return False
        key.verify(signature, _canonical_bytes(_signed_document_material(document)))
    except (ValueError, binascii.Error, InvalidSignature):
        return False
    except Exception:
        return False
    return True


def _read_trusted_document(
    path: Path,
    *,
    expected_keys: set[str],
) -> tuple[dict[str, Any], str]:
    ready, status = _trusted_path_status(path, directory=False)
    if not ready:
        return {}, status
    try:
        raw = path.read_bytes()
        parsed = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}, "read_or_json_invalid"
    if len(raw) > 64 * 1024 or not isinstance(parsed, dict) or set(parsed) != expected_keys:
        return {}, "shape_invalid"
    return dict(parsed), "trusted"


def _verify_head_key_epoch(
    key: Ed25519PublicKey,
    trust: Mapping[str, Any],
    *,
    head_full: str,
    prior_events: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    epoch, read_status = _read_trusted_document(
        HEAD_KEY_EPOCH_PATH,
        expected_keys=_HEAD_KEY_EPOCH_KEYS,
    )
    valid_from = _parse_utc(epoch.get("valid_from"))
    expires_at = _parse_utc(epoch.get("expires_at"))
    epoch_number = epoch.get("epoch")
    previous_epoch_digest = str(epoch.get("previous_epoch_digest") or "").lower()
    epoch_digest = _sha256(_signed_document_material(epoch)) if epoch else ""
    prior_last = prior_events[-1] if prior_events else {}
    prior_epoch = prior_last.get("head_key_epoch")
    prior_epoch_digest = str(prior_last.get("head_key_epoch_digest") or "").lower()
    if prior_events:
        epoch_chain_ready = bool(
            type(prior_epoch) is int
            and _digest_ready(prior_epoch_digest)
            and (
                (epoch_number == prior_epoch and epoch_digest == prior_epoch_digest)
                or (
                    epoch_number == prior_epoch + 1
                    and previous_epoch_digest == prior_epoch_digest
                )
            )
        )
    else:
        epoch_chain_ready = bool(
            epoch_number == 1 and previous_epoch_digest == "0" * 64
        )
    shape_ready = bool(
        epoch.get("schema_version") == HEAD_KEY_EPOCH_SCHEMA_VERSION
        and epoch.get("algorithm") == "Ed25519"
        and type(epoch_number) is int
        and 1 <= epoch_number < 2**63
        and epoch.get("head_full") == head_full
        and epoch.get("key_fingerprint_sha256") == trust.get("key_fingerprint_sha256")
        and _digest_ready(epoch.get("nonce_digest"))
        and valid_from is not None
        and expires_at is not None
        and valid_from < expires_at
        and (expires_at - valid_from).total_seconds() <= 31 * 24 * 60 * 60
        and valid_from.timestamp() - 60 <= now.timestamp() <= expires_at.timestamp()
        and epoch_chain_ready
    )
    signature_ready = shape_ready and _verify_document_signature(key, epoch)
    if not signature_ready:
        return {
            "ready": False,
            "status": "trusted_head_key_epoch_invalid",
            "read_status": read_status,
        }
    return {
        "ready": True,
        "status": "trusted_head_key_epoch_verified",
        "epoch": epoch_number,
        "epoch_digest": epoch_digest,
        "previous_epoch_digest": previous_epoch_digest,
        "document": dict(epoch),
        "valid_from": epoch["valid_from"],
        "expires_at": epoch["expires_at"],
        "nonce_digest": epoch["nonce_digest"],
        "key_fingerprint_sha256": epoch["key_fingerprint_sha256"],
    }


def _verify_monotonic_anchor(
    key: Ed25519PublicKey,
    trust: Mapping[str, Any],
    epoch: Mapping[str, Any],
    verified: Mapping[str, Any],
    *,
    prior_events: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    anchor, read_status = _read_trusted_document(
        MONOTONIC_ANCHOR_PATH,
        expected_keys=_MONOTONIC_ANCHOR_KEYS,
    )
    prior_last = prior_events[-1] if prior_events else {}
    previous_counter = int(prior_last.get("monotonic_counter") or 0)
    previous_attestation = str(prior_last.get("attestation_id") or "")
    issued_at = _parse_utc(anchor.get("issued_at"))
    expires_at = _parse_utc(anchor.get("expires_at"))
    epoch_valid_from = _parse_utc(epoch.get("valid_from"))
    epoch_expires_at = _parse_utc(epoch.get("expires_at"))
    shape_ready = bool(
        anchor.get("schema_version") == MONOTONIC_ANCHOR_SCHEMA_VERSION
        and anchor.get("algorithm") == "Ed25519"
        and anchor.get("epoch") == epoch.get("epoch")
        and anchor.get("head_full") == verified.get("head_full")
        and anchor.get("key_fingerprint_sha256") == trust.get("key_fingerprint_sha256")
        and anchor.get("epoch_digest") == epoch.get("epoch_digest")
        and anchor.get("monotonic_counter") == verified.get("monotonic_counter")
        and anchor.get("cas_previous_counter") == previous_counter
        and anchor.get("monotonic_counter") == previous_counter + 1
        and anchor.get("previous_attestation_digest") == previous_attestation
        and anchor.get("cas_previous_attestation_digest") == previous_attestation
        and anchor.get("attestation_id") == verified.get("attestation_id")
        and anchor.get("nonce_digest") == verified.get("nonce_digest")
        and anchor.get("issued_at") == verified.get("issued_at")
        and anchor.get("expires_at") == verified.get("expires_at")
        and issued_at is not None
        and expires_at is not None
        and epoch_valid_from is not None
        and epoch_expires_at is not None
        and epoch_valid_from <= issued_at < expires_at <= epoch_expires_at
        and issued_at.timestamp() - 60 <= now.timestamp() <= expires_at.timestamp()
    )
    signature_ready = shape_ready and _verify_document_signature(key, anchor)
    if not signature_ready:
        return {
            "ready": False,
            "status": "external_monotonic_anchor_invalid_or_cas_mismatch",
            "read_status": read_status,
        }
    return {
        "ready": True,
        "status": "external_monotonic_anchor_verified",
        "anchor_digest": _sha256(_signed_document_material(anchor)),
        "epoch": anchor["epoch"],
        "monotonic_counter": anchor["monotonic_counter"],
        "cas_previous_counter": anchor["cas_previous_counter"],
        "attestation_id": anchor["attestation_id"],
        "previous_attestation_digest": anchor["previous_attestation_digest"],
        "nonce_digest": anchor["nonce_digest"],
    }


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
        if (
            claims.get("dataset") != subject
            or subject not in CANONICAL_STORAGE_DATASETS
            or not _SAFE_ID.fullmatch(str(claims.get("phase_a_task_id") or ""))
        ):
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
            and _HEX_64.fullmatch(str(claims.get("provider_version_digest") or ""))
            and _HEX_64.fullmatch(str(claims.get("universe_digest") or ""))
            and re.fullmatch(r"[0-9]{8}", str(claims.get("validated_trade_date") or ""))
            and claims.get("eligible_worker_count", 0) > 0
            and claims.get("batch_count", 0) > 0
            and claims.get("row_count", 0) > 0
        )
    if kind == "candidate_radar_lineage":
        return bool(
            subject == CANDIDATE_RADAR_PACKET_KEY
            and claims.get("candidate_cache_packet_key") == subject
            and _HEX_64.fullmatch(
                str(claims.get("candidate_cache_write_task_digest") or "")
            )
            and claims.get("candidate_row_count", 0) > 0
            and claims.get("candidate_radar_production_replacement") is True
            and claims.get("candidate_is_not_buy_instruction") is True
        )
    if kind == "tushare_provider_execution_authorization":
        return bool(
            subject == "tushare-full-interface-provider-execution"
            and _SAFE_ID.fullmatch(str(claims.get("provider_attempt_id") or ""))
            and len(str(claims.get("provider_attempt_id") or "")) == 32
            and _SAFE_ID.fullmatch(str(claims.get("provider_version_id") or ""))
            and str(claims.get("provider_version_id") or "").endswith(
                f"-{claims.get('provider_attempt_id')}"
            )
            and claims.get("trade_cal_repeat_authorized") is True
            and 1 <= claims.get("provider_max_calls", 0) <= 300
        )
    return True


def _verify_envelope(
    envelope: Any,
    *,
    prior_events: list[dict[str, Any]],
    enforce_freshness: bool,
    enforce_current_head: bool = True,
    expected_kind: str | None = None,
    verification_key: Ed25519PublicKey | None = None,
    verification_trust: Mapping[str, Any] | None = None,
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
    if verification_key is None and verification_trust is None:
        key, trust = _load_trusted_public_key()
    elif verification_key is not None and verification_trust is not None:
        key, trust = verification_key, dict(verification_trust)
    else:
        return {"ready": False, "status": "signed_envelope_verification_key_invalid"}
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


def _verify_stored_epoch_binding(
    event: Mapping[str, Any],
    *,
    key: Ed25519PublicKey,
    prior_event: Mapping[str, Any] | None,
) -> bool:
    document = event.get("head_key_epoch_document")
    if not isinstance(document, Mapping) or set(document) != _HEAD_KEY_EPOCH_KEYS:
        return False
    epoch_number = document.get("epoch")
    epoch_digest = _sha256(_signed_document_material(document))
    previous_epoch_digest = str(document.get("previous_epoch_digest") or "").lower()
    issued_at = _parse_utc(event.get("issued_at"))
    valid_from = _parse_utc(document.get("valid_from"))
    expires_at = _parse_utc(document.get("expires_at"))
    fingerprint = str(event.get("key_fingerprint_sha256") or "").lower()
    base_ready = bool(
        document.get("schema_version") == HEAD_KEY_EPOCH_SCHEMA_VERSION
        and document.get("algorithm") == "Ed25519"
        and type(epoch_number) is int
        and epoch_number >= 1
        and document.get("head_full") == event.get("head_full")
        and document.get("key_fingerprint_sha256") == fingerprint
        and event.get("head_key_epoch") == epoch_number
        and event.get("head_key_epoch_digest") == epoch_digest
        and event.get("head_key_previous_epoch_digest") == previous_epoch_digest
        and _digest_ready(document.get("nonce_digest"))
        and valid_from is not None
        and expires_at is not None
        and issued_at is not None
        and valid_from <= issued_at <= expires_at
        and valid_from < expires_at
        and (expires_at - valid_from).total_seconds() <= 31 * 24 * 60 * 60
        and _verify_document_signature(key, document)
    )
    if not base_ready:
        return False
    if prior_event is None:
        return epoch_number == 1 and previous_epoch_digest == "0" * 64
    prior_epoch = prior_event.get("head_key_epoch")
    prior_epoch_digest = str(prior_event.get("head_key_epoch_digest") or "").lower()
    prior_fingerprint = str(prior_event.get("key_fingerprint_sha256") or "").lower()
    return bool(
        type(prior_epoch) is int
        and _digest_ready(prior_epoch_digest)
        and (
            (
                epoch_number == prior_epoch
                and epoch_digest == prior_epoch_digest
                and fingerprint == prior_fingerprint
            )
            or (
                epoch_number == prior_epoch + 1
                and previous_epoch_digest == prior_epoch_digest
            )
        )
    )


def _trusted_registry_packet(
    events: list[dict[str, Any]],
    *,
    verified: Mapping[str, Any],
    epoch: Mapping[str, Any],
    anchor: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "packet_key": REGISTRY_PACKET_KEY,
        "status": "external_attestation_registry_production_trust_verified",
        "head_full": verified["head_full"],
        "event_count": len(events),
        "last_attestation_id": verified["attestation_id"],
        "last_monotonic_counter": verified["monotonic_counter"],
        "head_key_epoch": epoch["epoch"],
        "head_key_epoch_digest": epoch["epoch_digest"],
        "monotonic_anchor_digest": anchor["anchor_digest"],
        "events": events,
        "external_signature_verified": True,
        "external_trust_verified": True,
        "production_trusted": True,
        "snapshot_rollback_resistant": True,
        "blockers": [],
        "private_key_generated": False,
        "private_key_loaded": False,
        "external_calls_triggered": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
    }


def prepare_external_trusted_attestation(
    payload: Any,
    *,
    expected_kind: str,
) -> dict[str, Any]:
    """Verify externally provisioned epoch/high-water proof without writing.

    The caller must atomically persist the returned registry packet with its
    production consumer.  This function never creates keys, epochs, anchors,
    approvals, registry rows, or consumer rows.
    """

    if not isinstance(payload, Mapping) or set(payload) != {"signed_envelope"}:
        return {
            **_local_only_trust_state(),
            "status": "signed_envelope_only_required",
            "writes_performed": False,
        }
    registry = validate_registry()
    if registry.get("read_status") not in {"meta_missing", "packet_missing", "packet_present"}:
        return {
            **_local_only_trust_state(),
            "status": "external_attestation_registry_fail_closed",
            "writes_performed": False,
        }
    if registry.get("read_status") == "packet_present" and registry.get("local_integrity_ready") is not True:
        return {
            **_local_only_trust_state(),
            "status": "external_attestation_registry_existing_state_invalid",
            "writes_performed": False,
        }
    # Keep the externally verified epoch/anchor metadata on historical rows.
    # validate_registry() deliberately reconstructs envelope facts, so using
    # its rows here would silently discard the proof binding after event one.
    registry_source, _ = _read_registry_no_init()
    prior_events = list(registry_source.get("events") or [])
    envelope = payload["signed_envelope"]
    existing_index = next(
        (
            index
            for index, row in enumerate(prior_events)
            if row.get("signed_envelope") == envelope
        ),
        None,
    )
    idempotent = existing_index is not None
    if idempotent:
        if existing_index != len(prior_events) - 1:
            return {
                **_local_only_trust_state(),
                "status": "external_attestation_replay_not_current_high_water",
                "writes_performed": False,
            }
        prior_for_verification = prior_events[:-1]
    else:
        prior_for_verification = prior_events
    verified = _verify_envelope(
        envelope,
        prior_events=prior_for_verification,
        enforce_freshness=True,
        expected_kind=expected_kind,
    )
    if verified.get("ready") is not True:
        return {
            **verified,
            **_local_only_trust_state(),
            "writes_performed": False,
        }
    if verified.get("attestation_kind") == "tushare_provider_execution_authorization":
        claims = verified.get("claims") if isinstance(verified.get("claims"), Mapping) else {}
        attempt_id = str(claims.get("provider_attempt_id") or "")
        version_id = str(claims.get("provider_version_id") or "")
        prior_provider_events = [
            row
            for row in prior_events
            if isinstance(row, Mapping)
            and row.get("attestation_kind")
            == "tushare_provider_execution_authorization"
        ]
        if any(
            isinstance(row.get("claims"), Mapping)
            and (
                row["claims"].get("provider_attempt_id") == attempt_id
                or row["claims"].get("provider_version_id") == version_id
            )
            for row in prior_provider_events
        ):
            return {
                **verified,
                **_local_only_trust_state(local_integrity_ready=True),
                "status": "provider_execution_attempt_or_version_replayed",
                "writes_performed": False,
            }
    key, trust = _load_trusted_public_key()
    if key is None:
        return {**trust, **_local_only_trust_state(), "writes_performed": False}
    now = datetime.now(timezone.utc)
    epoch = _verify_head_key_epoch(
        key,
        trust,
        head_full=str(verified["head_full"]),
        prior_events=prior_for_verification,
        now=now,
    )
    if epoch.get("ready") is not True:
        return {
            **verified,
            **_local_only_trust_state(local_integrity_ready=True),
            "status": str(epoch.get("status") or "trusted_head_key_epoch_invalid"),
            "writes_performed": False,
        }
    anchor = _verify_monotonic_anchor(
        key,
        trust,
        epoch,
        verified,
        prior_events=prior_for_verification,
        now=now,
    )
    if anchor.get("ready") is not True:
        return {
            **verified,
            **_local_only_trust_state(local_integrity_ready=True),
            "status": str(anchor.get("status") or "external_monotonic_anchor_invalid"),
            "writes_performed": False,
        }
    stored_event = dict(verified)
    for key_name in (
        "ready",
        "status",
        "external_trust_verified",
        "production_trusted",
        "snapshot_rollback_resistant",
        "blockers",
    ):
        stored_event.pop(key_name, None)
    stored_event.update(
        {
            "head_key_epoch": epoch["epoch"],
            "head_key_epoch_digest": epoch["epoch_digest"],
            "head_key_previous_epoch_digest": epoch["previous_epoch_digest"],
            "head_key_epoch_document": dict(epoch["document"]),
            "monotonic_anchor_digest": anchor["anchor_digest"],
            "external_trust_verified": True,
            "production_trusted": True,
            "snapshot_rollback_resistant": True,
            "blockers": [],
        }
    )
    events = prior_events if idempotent else [*prior_events, stored_event]
    if idempotent:
        events[-1] = stored_event
    registry_packet = _trusted_registry_packet(
        events,
        verified=verified,
        epoch=epoch,
        anchor=anchor,
    )
    return {
        **verified,
        "ready": True,
        "status": "external_production_attestation_trust_proof_verified",
        "local_integrity_ready": True,
        "external_trust_verified": True,
        "production_trusted": True,
        "snapshot_rollback_resistant": True,
        "blockers": [],
        "head_key_epoch": epoch["epoch"],
        "head_key_epoch_digest": epoch["epoch_digest"],
        "monotonic_anchor_digest": anchor["anchor_digest"],
        "idempotent_reuse": idempotent,
        "writes_performed": False,
        "_registry_packet": registry_packet,
    }


def validate_trusted_registry(
    *,
    head_mode: str = "current",
    expected_head_full: str | None = None,
) -> dict[str, Any]:
    """Validate the persisted trust chain without reapplying issuance freshness.

    Freshness is mandatory when an envelope is first consumed by
    ``prepare_external_trusted_attestation``.  Once the envelope, signed key
    epoch, and monotonic high-water anchor have been atomically persisted,
    durable verification instead proves their signatures and exact chain
    bindings.  Requiring an already-consumed envelope to remain inside its
    short issuance window would make immutable production evidence expire.
    """

    if head_mode not in {"current", "history"}:
        return {
            **_local_only_trust_state(),
            "status": "external_attestation_head_mode_invalid",
            "historical_integrity_ready": False,
            "head_mode": head_mode,
            "blockers": ["external_attestation_head_mode_invalid"],
        }
    expected_head = str(expected_head_full or "").lower()
    if (
        head_mode == "history"
        and not expected_head
        or expected_head
        and not _HEX_40.fullmatch(expected_head)
    ):
        return {
            **_local_only_trust_state(),
            "status": "external_attestation_expected_head_invalid",
            "historical_integrity_ready": False,
            "head_mode": head_mode,
            "blockers": ["external_attestation_expected_head_invalid"],
        }

    registry = validate_registry()
    events = list(registry.get("events") or [])
    if registry.get("local_integrity_ready") is not True or not events:
        return {
            **registry,
            "ready": False,
            "external_trust_verified": False,
            "production_trusted": False,
            "snapshot_rollback_resistant": False,
            "blockers": list(PRODUCTION_TRUST_BLOCKERS),
        }
    latest = events[-1]
    # Historical audit must not depend on whichever checkout happens to be
    # active now.  It validates the persisted signed chain and binds the
    # selected historical event separately below.  Current promotion still
    # requires the actual clean checkout and an exact expected-head match.
    runtime_head_full = (
        _current_clean_head_full()
        if head_mode == "current"
        else str(latest.get("head_full") or "").lower()
    )
    selected_head_ready = bool(
        not expected_head
        or (head_mode == "current" and runtime_head_full == expected_head)
        or (
            head_mode == "history"
            and any(event.get("head_full") == expected_head for event in events)
        )
    )
    source, _ = _read_registry_no_init()
    source_events = source.get("events") if isinstance(source.get("events"), list) else []
    source_latest = (
        source_events[-1]
        if source_events and isinstance(source_events[-1], Mapping)
        else {}
    )
    prior = events[-2] if len(events) > 1 else {}
    anchor, anchor_read_status = _read_trusted_document(
        MONOTONIC_ANCHOR_PATH,
        expected_keys=_MONOTONIC_ANCHOR_KEYS,
    )
    verification_key, _ = _load_trusted_event_public_key(
        epoch=latest.get("head_key_epoch"),
        fingerprint=latest.get("key_fingerprint_sha256"),
    )
    anchor_issued_at = _parse_utc(anchor.get("issued_at"))
    anchor_expires_at = _parse_utc(anchor.get("expires_at"))
    epoch_document = latest.get("head_key_epoch_document")
    epoch_valid_from = _parse_utc(
        epoch_document.get("valid_from") if isinstance(epoch_document, Mapping) else None
    )
    epoch_expires_at = _parse_utc(
        epoch_document.get("expires_at") if isinstance(epoch_document, Mapping) else None
    )
    previous_counter = int(prior.get("monotonic_counter") or 0)
    previous_attestation = str(prior.get("attestation_id") or "")
    anchor_ready = bool(
        anchor_read_status == "trusted"
        and verification_key is not None
        and _HEX_40.fullmatch(runtime_head_full)
        and selected_head_ready
        and latest.get("head_full") == runtime_head_full
        and anchor.get("head_full") == runtime_head_full
        and anchor.get("schema_version") == MONOTONIC_ANCHOR_SCHEMA_VERSION
        and anchor.get("algorithm") == "Ed25519"
        and anchor.get("epoch") == latest.get("head_key_epoch")
        and anchor.get("head_full") == latest.get("head_full")
        and anchor.get("key_fingerprint_sha256")
        == latest.get("key_fingerprint_sha256")
        and anchor.get("epoch_digest") == latest.get("head_key_epoch_digest")
        and anchor.get("monotonic_counter") == latest.get("monotonic_counter")
        and anchor.get("cas_previous_counter") == previous_counter
        and anchor.get("monotonic_counter") == previous_counter + 1
        and anchor.get("previous_attestation_digest") == previous_attestation
        and anchor.get("cas_previous_attestation_digest") == previous_attestation
        and anchor.get("attestation_id") == latest.get("attestation_id")
        and anchor.get("nonce_digest") == latest.get("nonce_digest")
        and anchor.get("issued_at") == latest.get("issued_at")
        and anchor.get("expires_at") == latest.get("expires_at")
        and anchor_issued_at is not None
        and anchor_expires_at is not None
        and epoch_valid_from is not None
        and epoch_expires_at is not None
        and epoch_valid_from <= anchor_issued_at < anchor_expires_at <= epoch_expires_at
        and _verify_document_signature(verification_key, anchor)
    )
    anchor_digest = _sha256(_signed_document_material(anchor)) if anchor_ready else ""
    metadata_ready = bool(
        anchor_ready
        and source.get("head_full") == runtime_head_full
        and source.get("production_trusted") is True
        and source.get("snapshot_rollback_resistant") is True
        and source.get("head_key_epoch") == latest.get("head_key_epoch")
        and source.get("head_key_epoch_digest") == latest.get("head_key_epoch_digest")
        and source.get("monotonic_anchor_digest") == anchor_digest
        and source.get("last_attestation_id") == latest.get("attestation_id")
        and source_latest.get("head_key_epoch") == latest.get("head_key_epoch")
        and source_latest.get("head_key_epoch_digest") == latest.get("head_key_epoch_digest")
        and source_latest.get("monotonic_anchor_digest") == anchor_digest
        and source_latest.get("external_trust_verified") is True
        and source_latest.get("production_trusted") is True
        and source_latest.get("snapshot_rollback_resistant") is True
    )
    historical_integrity_ready = metadata_ready
    production_ready = metadata_ready and head_mode == "current"
    return {
        **latest,
        "ready": production_ready,
        "status": (
            "external_attestation_registry_production_trust_verified"
            if production_ready
            else "external_attestation_registry_historical_integrity_verified_non_promotable"
            if historical_integrity_ready
            else "external_attestation_registry_trust_metadata_mismatch"
        ),
        "production_trusted": production_ready,
        "snapshot_rollback_resistant": historical_integrity_ready,
        "historical_integrity_ready": historical_integrity_ready,
        "persisted_validation_ignores_envelope_freshness": True,
        "head_mode": head_mode,
        "expected_head_full": expected_head,
        "runtime_head_full": runtime_head_full,
        "blockers": []
        if historical_integrity_ready
        else [
            (
                "external_attestation_expected_historical_head_missing"
                if head_mode == "history" and not selected_head_ready
                else "external_attestation_expected_current_head_mismatch"
                if head_mode == "current" and not selected_head_ready
                else "external_attestation_current_clean_head_mismatch"
                if head_mode == "current"
                and latest.get("head_full") != runtime_head_full
                else "external_monotonic_anchor_unavailable"
            )
        ],
    }


def validate_registry() -> dict[str, Any]:
    source, read_status = _read_registry_no_init()
    events = source.get("events") if isinstance(source.get("events"), list) else []
    production_registry = source.get("production_trusted") is True
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
        verification_key: Ed25519PublicKey | None = None
        verification_trust: Mapping[str, Any] | None = None
        epoch_binding_ready = True
        if production_registry:
            verification_key, verification_trust = _load_trusted_event_public_key(
                epoch=event.get("head_key_epoch"),
                fingerprint=event.get("key_fingerprint_sha256"),
            )
            epoch_binding_ready = bool(
                verification_key is not None
                and _verify_stored_epoch_binding(
                    event,
                    key=verification_key,
                    prior_event=validated[-1] if validated else None,
                )
                and event.get("external_trust_verified") is True
                and event.get("production_trusted") is True
                and event.get("snapshot_rollback_resistant") is True
            )
        result = _verify_envelope(
            event["signed_envelope"],
            prior_events=validated,
            enforce_freshness=False,
            enforce_current_head=False,
            verification_key=verification_key,
            verification_trust=verification_trust,
        )
        if (
            not result.get("ready")
            or result.get("attestation_id") != event.get("attestation_id")
            or not epoch_binding_ready
        ):
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
        if production_registry:
            result.update(
                {
                    "head_key_epoch": event["head_key_epoch"],
                    "head_key_epoch_digest": event["head_key_epoch_digest"],
                    "head_key_previous_epoch_digest": event[
                        "head_key_previous_epoch_digest"
                    ],
                    "head_key_epoch_document": dict(event["head_key_epoch_document"]),
                    "monotonic_anchor_digest": event["monotonic_anchor_digest"],
                    "external_trust_verified": True,
                    "production_trusted": True,
                    "snapshot_rollback_resistant": True,
                    "blockers": [],
                }
            )
        validated.append(result)
    local_integrity_ready = bool(
        source.get("schema_version") == REGISTRY_SCHEMA_VERSION
        and read_status == "packet_present"
        and events
        and len(events) == len(validated)
        and source.get("last_attestation_id") == validated[-1]["attestation_id"]
        and source.get("last_monotonic_counter") == validated[-1]["monotonic_counter"]
    )
    canonical_events: list[dict[str, Any]] = []
    if local_integrity_ready and production_registry:
        for result in validated:
            canonical_event = dict(result)
            for key_name in (
                "ready",
                "status",
                "external_trust_verified",
                "production_trusted",
                "snapshot_rollback_resistant",
                "blockers",
            ):
                canonical_event.pop(key_name, None)
            canonical_event.update(
                {
                    "external_trust_verified": True,
                    "production_trusted": True,
                    "snapshot_rollback_resistant": True,
                    "blockers": [],
                }
            )
            canonical_events.append(canonical_event)
    canonical_registry = (
        _trusted_registry_packet(
            canonical_events,
            verified=canonical_events[-1],
            epoch={
                "epoch": canonical_events[-1]["head_key_epoch"],
                "epoch_digest": canonical_events[-1]["head_key_epoch_digest"],
            },
            anchor={
                "anchor_digest": canonical_events[-1]["monotonic_anchor_digest"],
            },
        )
        if canonical_events
        else {}
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
        "canonical_registry": canonical_registry,
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
        registry_source, _ = _read_registry_no_init()
        if registry_source.get("production_trusted") is True:
            return {
                **_local_only_trust_state(local_integrity_ready=True),
                "status": "trusted_registry_requires_atomic_consumer_import",
                "writes_performed": False,
                "external_calls_triggered": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
            }
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
        "planned_consumers": [
            "storage",
            "worker",
            "factor",
            "candidate_radar",
            "tushare_provider_execution_authorization",
        ],
        "production_consumers_wired": [
            "storage_ttl",
            "worker",
            "factor",
            "candidate_radar",
            "tushare_provider_execution_authorization",
        ],
        "post_accepts_signed_envelope_only": True,
        "caller_boolean_cannot_promote": True,
        "local_hmac_cannot_promote": True,
        "external_signature_is_local_integrity_only": True,
        "storage_ttl_requires_external_epoch_anchor_and_atomic_consumer": True,
        "production_trusted": False,
        "snapshot_rollback_resistant": False,
        "production_blockers": list(PRODUCTION_TRUST_BLOCKERS),
        "application_generates_private_key": False,
        "application_loads_private_key": False,
        "get_writes_performed": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
    }
