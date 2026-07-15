"""Fail-closed, current-HEAD production release promotion journal.

The journal is an explicit local state transition after independently recorded
local-gate, remote-CI, allowlist, and release-review evidence.  Read paths never
create the SQLite file.  Promotion performs no network or provider work and
does not accept caller-supplied evidence booleans.

The install-local HMAC key and terminal state protect the journal from callers
that can write generic SQLite rows but cannot read or replace files in the
mode-0700 trust directory.  A process running as the owning OS account and
able to read that key is inside, not outside, this trust boundary.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import stat
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.services import audit_service


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
JOURNAL_NAME = "production_release_promotion.sqlite"
PROMOTION_SCOPE = "command_center_3_current_head_release"
EVENT_SCHEMA_VERSION = "command_center_3_production_release_promotion_event.v2"
VALIDATION_SCHEMA_VERSION = "command_center_3_production_release_promotion_validation.v2"

_REMOTE_CI_SCOPE = "ignored_manual_remote_ci_review_receipt_no_cache_github_api"
_REMOTE_CI_RECEIPT_WRITER = "scripts/record_remote_ci_review_receipt.py"
_REMOTE_CI_WORKFLOW_NAME = "Command Center 3 Push Gate"
_REMOTE_CI_RUN_URL_PREFIX = "https://github.com/lishark-of/stock-MING/actions/runs/"
_REMOTE_CI_ARTIFACT_PREFIX = "command-center-3-push-gate-evidence-"
_LOCAL_GATE_SCOPE = "ignored_local_push_gate_run_receipt_no_push_no_github_api"
_LOCAL_GATE_REMOTE_NOTE = (
    "local push gate pass is not remote CI green; inspect matching remote Actions run "
    "before release."
)
_ALLOWLIST_SCOPE = "ignored_manual_secret_artifact_allowlist_review_no_cache_github_api"
_ALLOWLIST_RECEIPT_WRITER = "scripts/record_secret_artifact_allowlist_review_receipt.py"
_RELEASE_REVIEW_SCOPE = "ignored_manual_release_gate_review_no_cache_github_api"
_RELEASE_REVIEW_RECEIPT_WRITER = "scripts/record_release_gate_review_receipt.py"
_JOURNAL_INVALID_BLOCKER = "production_release_promotion_journal_corrupt_or_not_sqlite"
_TRUST_KEY_MISSING_BLOCKER = "production_release_promotion_trusted_writer_key_missing"
_TRUST_KEY_PERMISSIONS_BLOCKER = (
    "production_release_promotion_trusted_writer_key_permissions_invalid"
)
_TRUST_KEY_CORRUPT_BLOCKER = "production_release_promotion_trusted_writer_key_corrupt"
_TRUST_STATE_MISSING_BLOCKER = "production_release_promotion_trusted_writer_state_missing"
_TRUST_STATE_PERMISSIONS_BLOCKER = (
    "production_release_promotion_trusted_writer_state_permissions_invalid"
)
_TRUST_STATE_CORRUPT_BLOCKER = "production_release_promotion_trusted_writer_state_corrupt"
_TRUST_DIRECTORY_NAME = ".production_release_promotion_trust"
_TRUST_KEY_NAME = "writer.key"
_TRUST_STATE_NAME = "writer.state"
_TRUST_KEY_BYTES = 32
_TRUST_STATE_SCHEMA_VERSION = "command_center_3_production_release_trusted_writer_state.v1"

_EVENT_TABLE = "production_release_promotion_events"
_CURRENT_TABLE = "production_release_promotion_current"
_EVENT_NO_UPDATE_TRIGGER = "production_release_promotion_events_no_update"
_EVENT_NO_DELETE_TRIGGER = "production_release_promotion_events_no_delete"
_EVENT_TABLE_DDL = (
    f"CREATE TABLE {_EVENT_TABLE} ("
    "event_id TEXT PRIMARY KEY, sequence_no INTEGER NOT NULL, "
    "semantic_digest TEXT NOT NULL, schema_version TEXT NOT NULL, scope TEXT NOT NULL, "
    "head_full TEXT NOT NULL, local_gate_digest TEXT NOT NULL, "
    "remote_ci_digest TEXT NOT NULL, allowlist_digest TEXT NOT NULL, "
    "release_review_digest TEXT NOT NULL, remote_run_id TEXT NOT NULL, "
    "remote_artifact_digest TEXT NOT NULL, approved_by_user INTEGER NOT NULL "
    "CHECK (approved_by_user = 1), promoted_at_utc TEXT NOT NULL, "
    "previous_event_mac TEXT NOT NULL, event_mac TEXT NOT NULL)"
)
_CURRENT_TABLE_DDL = (
    f"CREATE TABLE {_CURRENT_TABLE} ("
    "scope TEXT PRIMARY KEY, event_id TEXT NOT NULL, sequence_no INTEGER NOT NULL, "
    "head_full TEXT NOT NULL, promoted_at_utc TEXT NOT NULL, event_mac TEXT NOT NULL, "
    "FOREIGN KEY(event_id) "
    f"REFERENCES {_EVENT_TABLE}(event_id))"
)
_EVENT_NO_UPDATE_TRIGGER_DDL = (
    f"CREATE TRIGGER {_EVENT_NO_UPDATE_TRIGGER} BEFORE UPDATE ON {_EVENT_TABLE} "
    "BEGIN SELECT RAISE(ABORT, 'production release promotion events are append-only'); END"
)
_EVENT_NO_DELETE_TRIGGER_DDL = (
    f"CREATE TRIGGER {_EVENT_NO_DELETE_TRIGGER} BEFORE DELETE ON {_EVENT_TABLE} "
    "BEGIN SELECT RAISE(ABORT, 'production release promotion events are append-only'); END"
)
_CREATE_EVENT_TABLE_DDL = _EVENT_TABLE_DDL.replace(
    "CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1
)
_CREATE_CURRENT_TABLE_DDL = _CURRENT_TABLE_DDL.replace(
    "CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1
)
_CREATE_EVENT_NO_UPDATE_TRIGGER_DDL = _EVENT_NO_UPDATE_TRIGGER_DDL.replace(
    "CREATE TRIGGER ", "CREATE TRIGGER IF NOT EXISTS ", 1
)
_CREATE_EVENT_NO_DELETE_TRIGGER_DDL = _EVENT_NO_DELETE_TRIGGER_DDL.replace(
    "CREATE TRIGGER ", "CREATE TRIGGER IF NOT EXISTS ", 1
)
_EXPECTED_EVENT_TABLE_INFO = (
    (0, "event_id", "TEXT", 0, None, 1),
    (1, "sequence_no", "INTEGER", 1, None, 0),
    (2, "semantic_digest", "TEXT", 1, None, 0),
    (3, "schema_version", "TEXT", 1, None, 0),
    (4, "scope", "TEXT", 1, None, 0),
    (5, "head_full", "TEXT", 1, None, 0),
    (6, "local_gate_digest", "TEXT", 1, None, 0),
    (7, "remote_ci_digest", "TEXT", 1, None, 0),
    (8, "allowlist_digest", "TEXT", 1, None, 0),
    (9, "release_review_digest", "TEXT", 1, None, 0),
    (10, "remote_run_id", "TEXT", 1, None, 0),
    (11, "remote_artifact_digest", "TEXT", 1, None, 0),
    (12, "approved_by_user", "INTEGER", 1, None, 0),
    (13, "promoted_at_utc", "TEXT", 1, None, 0),
    (14, "previous_event_mac", "TEXT", 1, None, 0),
    (15, "event_mac", "TEXT", 1, None, 0),
)
_EXPECTED_CURRENT_TABLE_INFO = (
    (0, "scope", "TEXT", 0, None, 1),
    (1, "event_id", "TEXT", 1, None, 0),
    (2, "sequence_no", "INTEGER", 1, None, 0),
    (3, "head_full", "TEXT", 1, None, 0),
    (4, "promoted_at_utc", "TEXT", 1, None, 0),
    (5, "event_mac", "TEXT", 1, None, 0),
)
_EXPECTED_EVENT_INDEXES = ((f"sqlite_autoindex_{_EVENT_TABLE}_1", 1, "pk", 0),)
_EXPECTED_CURRENT_INDEXES = ((f"sqlite_autoindex_{_CURRENT_TABLE}_1", 1, "pk", 0),)
_EXPECTED_CURRENT_FOREIGN_KEYS = (
    (0, 0, _EVENT_TABLE, "event_id", "event_id", "NO ACTION", "NO ACTION", "NONE"),
)

_SAFETY_FIELDS = (
    "external_calls_triggered",
    "tushare_called",
    "deepseek_called",
    "github_called",
    "github_api_called",
    "contains_secret",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_head(value: object) -> str:
    candidate = str(value or "").strip().lower()
    if len(candidate) not in {40, 64} or any(
        char not in "0123456789abcdef" for char in candidate
    ):
        return ""
    return candidate


def _current_head(project_root: Path = PROJECT_ROOT) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return _normalize_head(result.stdout) if result.returncode == 0 else ""


def _resolve_head(expected_head_full: object | None) -> tuple[str, list[str]]:
    if expected_head_full is not None:
        head_full = _normalize_head(expected_head_full)
        if not head_full:
            return "", ["release_promotion_expected_head_invalid"]
        return head_full, []
    head_full = _current_head()
    if not head_full:
        return "", ["release_promotion_current_git_head_unavailable"]
    return head_full, []


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    encoded = json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return encoded.encode("utf-8")


def _trusted_event_mac(secret: bytes, material: Mapping[str, Any]) -> str:
    return hmac.new(secret, _canonical_bytes(material), hashlib.sha256).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _receipt_type_blockers(
    evidence_key: str,
    receipt: Mapping[str, Any],
    field_types: Mapping[str, type],
    *,
    string_list_fields: tuple[str, ...] = (),
) -> list[str]:
    invalid = []
    for field, expected_type in field_types.items():
        value = receipt.get(field)
        if expected_type is bool:
            valid = type(value) is bool
        elif expected_type is int:
            valid = type(value) is int
        else:
            valid = isinstance(value, expected_type)
        if not valid:
            invalid.append(field)
    for field in string_list_fields:
        value = receipt.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            invalid.append(field)
    blockers = [f"{evidence_key}_receipt_field_types_invalid"] if invalid else []
    expected_fields = set(field_types).union(string_list_fields)
    if set(receipt) != expected_fields:
        blockers.append(f"{evidence_key}_receipt_fields_not_exact_formal_schema")
    return blockers


def _valid_utc_second(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value


def _valid_ascii_decimal(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and value
        and all("0" <= char <= "9" for char in value)
    )


def _valid_short_head(value: object, head_full: str, *, exact_eight: bool) -> bool:
    if not isinstance(value, str):
        return False
    if exact_eight:
        return value == head_full[:8]
    return 7 <= len(value) <= 12 and head_full.startswith(value)


def _receipt_material(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Bind every exact-schema field, including timestamps and safe manual notes."""
    return {field: receipt[field] for field in sorted(receipt)}


def _safe_type_fields(*, cache_fields: bool = False) -> dict[str, type]:
    fields = {field: bool for field in _SAFETY_FIELDS}
    fields.update(
        {
            "does_not_execute_trades": bool,
            "does_not_modify_strategy_action": bool,
        }
    )
    if cache_fields:
        fields.update(
            {
                "cache_get_external_calls": bool,
                "cache_get_calls_github_api": bool,
            }
        )
    return fields


def _safe_boundary(receipt: Mapping[str, Any], *, cache_fields: bool = False) -> bool:
    false_fields = list(_SAFETY_FIELDS)
    if cache_fields:
        false_fields.extend(("cache_get_external_calls", "cache_get_calls_github_api"))
    return bool(
        all(receipt.get(field) is False for field in false_fields)
        and receipt.get("does_not_execute_trades") is True
        and receipt.get("does_not_modify_strategy_action") is True
    )


def _valid_sha256(value: object, *, prefix: bool = False) -> bool:
    candidate = str(value or "").lower()
    if prefix:
        if not candidate.startswith("sha256:"):
            return False
        candidate = candidate.removeprefix("sha256:")
    return len(candidate) == 64 and all(char in "0123456789abcdef" for char in candidate)


def _valid_lower_sha256(value: object, *, prefix: bool = False) -> bool:
    return bool(
        isinstance(value, str)
        and value == value.lower()
        and _valid_sha256(value, prefix=prefix)
    )


def _evidence_result(
    key: str,
    *,
    ready: bool,
    material: Mapping[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "evidence_key": key,
        "ready": bool(ready),
        "semantic_digest": _digest(material) if ready else "",
        "blockers": blockers,
        "contains_secret": False,
    }


def _validate_evidence_fail_closed(
    evidence_key: str,
    validator: Any,
    *args: Any,
) -> dict[str, Any]:
    try:
        result = validator(*args)
    except Exception:
        return _evidence_result(
            evidence_key,
            ready=False,
            material={},
            blockers=[f"{evidence_key}_receipt_validation_failed_safe"],
        )
    if not isinstance(result, Mapping):
        return _evidence_result(
            evidence_key,
            ready=False,
            material={},
            blockers=[f"{evidence_key}_receipt_validation_failed_safe"],
        )
    return dict(result)


def _validate_local_gate(receipt: Mapping[str, Any], head_full: str) -> dict[str, Any]:
    field_types = {
        "schema_version": str,
        "status": str,
        "scope": str,
        "generated_at_utc": str,
        "branch": str,
        "head": str,
        "head_full": str,
        "did_not_push": bool,
        "git_add_dot_used": bool,
        "explicit_user_push_confirmation_before_push": bool,
        "push_confirmation_state": str,
        "release_claim_decision": str,
        "latest_remote_run_verified_green": bool,
        "local_gate_pass_is_not_ci_status": bool,
        "origin_ahead_count": str,
        "remote_actions_status_known": bool,
        "remote_ci_status_note": str,
        "report_path": str,
        **_safe_type_fields(),
    }
    blockers = _receipt_type_blockers(
        "local_push_gate",
        receipt,
        field_types,
        string_list_fields=("checks",),
    )
    raw_checks = receipt.get("checks")
    checks = (
        {item for item in raw_checks if isinstance(item, str)}
        if isinstance(raw_checks, list)
        else set()
    )
    missing_checks = sorted(audit_service.LOCAL_PUSH_GATE_REQUIRED_CHECKS.difference(checks))
    material = _receipt_material(receipt)
    if receipt.get("schema_version") != audit_service.LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION:
        blockers.append("local_gate_schema_invalid")
    if receipt.get("status") != "local_push_gate_passed_current_head":
        blockers.append("local_gate_status_not_passed")
    if receipt.get("head_full") != head_full:
        blockers.append("local_gate_head_mismatch")
    if missing_checks or len(raw_checks or []) != len(audit_service.LOCAL_PUSH_GATE_REQUIRED_CHECKS):
        blockers.append("local_gate_required_checks_missing")
    if not (
        receipt.get("scope") == _LOCAL_GATE_SCOPE
        and receipt.get("branch") == "main"
        and _valid_short_head(receipt.get("head"), head_full, exact_eight=False)
        and _valid_utc_second(receipt.get("generated_at_utc"))
        and (
            receipt.get("origin_ahead_count") == "unknown"
            or _valid_ascii_decimal(receipt.get("origin_ahead_count"))
        )
        and bool(str(receipt.get("report_path") or "").strip())
    ):
        blockers.append("local_gate_formal_recorder_identity_invalid")
    if not _safe_boundary(receipt):
        blockers.append("local_gate_safety_boundary_invalid")
    if not (
        receipt.get("did_not_push") is True
        and receipt.get("git_add_dot_used") is False
        and receipt.get("explicit_user_push_confirmation_before_push") is False
        and receipt.get("push_confirmation_state") == "not_requested_no_push"
        and receipt.get("release_claim_decision") == "blocked_remote_ci_unverified"
        and receipt.get("local_gate_pass_is_not_ci_status") is True
        and receipt.get("remote_actions_status_known") is False
        and receipt.get("latest_remote_run_verified_green") is False
        and receipt.get("remote_ci_status_note") == _LOCAL_GATE_REMOTE_NOTE
    ):
        blockers.append("local_gate_push_boundary_invalid")
    return _evidence_result("local_push_gate", ready=not blockers, material=material, blockers=blockers)


def _validate_remote_ci(receipt: Mapping[str, Any], head_full: str) -> dict[str, Any]:
    field_types = {
        "schema_version": str,
        "status": str,
        "scope": str,
        "reviewed_at_utc": str,
        "receipt_writer": str,
        "branch": str,
        "head": str,
        "head_full": str,
        "workflow_name": str,
        "event": str,
        "run_id": int,
        "run_url": str,
        "safe_failure_log_excerpt_or_green_run_url": str,
        "actions_status": str,
        "actions_conclusion": str,
        "job_name": str,
        "job_conclusion": str,
        "artifact_name": str,
        "artifact_digest": str,
        "artifact_digest_verified": bool,
        "artifact_digest_review_status": str,
        "failed_step_or_green_status": str,
        "explicit_user_actions_review_authorized": bool,
        "remote_actions_status_known": bool,
        "latest_remote_run_verified_green": bool,
        "remote_ci_job_page_green_observed": bool,
        "remote_ci_artifact_digest_pending": bool,
        "remote_ci_run_observed_for_current_head": bool,
        "remote_ci_run_in_progress_for_current_head": bool,
        "remote_ci_no_matching_run_found_for_current_head": bool,
        "remote_ci_run_lookup_attempted": bool,
        "remote_ci_lookup_source": str,
        "remote_ci_failure_reviewed_for_current_head": bool,
        "remote_ci_failure_artifact_download_status": str,
        "remote_ci_failure_artifact_download_blocked": bool,
        "release_claim_decision": str,
        "remote_ci_review_receipt_is_not_release_review": bool,
        "release_review_complete": bool,
        "release_gate_complete": bool,
        "production_release_complete": bool,
        **_safe_type_fields(cache_fields=True),
    }
    blockers = _receipt_type_blockers(
        "remote_ci",
        receipt,
        field_types,
    )
    raw_run_id = receipt.get("run_id")
    run_id = (
        str(raw_run_id)
        if isinstance(raw_run_id, int) and not isinstance(raw_run_id, bool)
        else ""
    )
    artifact_name = str(receipt.get("artifact_name") or "")
    artifact_digest = str(receipt.get("artifact_digest") or "")
    run_url = str(receipt.get("run_url") or "")
    expected_run_url = f"{_REMOTE_CI_RUN_URL_PREFIX}{run_id}" if run_id else ""
    expected_artifact_name = f"{_REMOTE_CI_ARTIFACT_PREFIX}{run_id}" if run_id else ""
    material = _receipt_material(receipt)
    if receipt.get("schema_version") != audit_service.REMOTE_CI_REVIEW_RECEIPT_SCHEMA_VERSION:
        blockers.append("remote_ci_schema_invalid")
    if receipt.get("status") != "remote_ci_review_verified_green":
        blockers.append("remote_ci_status_not_verified_green")
    if not head_full or receipt.get("head_full") != head_full:
        blockers.append("remote_ci_head_mismatch")
    if not (
        receipt.get("scope") == _REMOTE_CI_SCOPE
        and receipt.get("receipt_writer") == _REMOTE_CI_RECEIPT_WRITER
        and receipt.get("branch") == "main"
        and _valid_short_head(receipt.get("head"), head_full, exact_eight=True)
        and _valid_utc_second(receipt.get("reviewed_at_utc"))
    ):
        blockers.append("remote_ci_formal_recorder_identity_invalid")
    if not (
        receipt.get("workflow_name") == _REMOTE_CI_WORKFLOW_NAME
        and receipt.get("event") == "push"
        and receipt.get("actions_status") == "completed"
        and receipt.get("actions_conclusion") == "success"
        and receipt.get("job_name") == "push-gate"
        and receipt.get("job_conclusion") == "success"
    ):
        blockers.append("remote_ci_run_not_successful_push_gate")
    if not (
        run_id
        and int(run_id) > 0
        and run_url == expected_run_url
        and receipt.get("safe_failure_log_excerpt_or_green_run_url") == expected_run_url
        and artifact_name == expected_artifact_name
        and _valid_sha256(artifact_digest, prefix=True)
        and artifact_digest == artifact_digest.lower()
    ):
        blockers.append("remote_ci_artifact_identity_invalid")
    if not (
        receipt.get("artifact_digest_review_status") == "sha256_digest_recorded"
        and receipt.get("failed_step_or_green_status") == "green"
        and receipt.get("remote_ci_lookup_source") == ""
        and receipt.get("remote_ci_failure_artifact_download_status") == ""
        and receipt.get("release_claim_decision") == "remote_ci_green_release_review_pending"
    ):
        blockers.append("remote_ci_attestation_status_inconsistent")
    required_true = (
        "artifact_digest_verified",
        "explicit_user_actions_review_authorized",
        "remote_actions_status_known",
        "latest_remote_run_verified_green",
        "remote_ci_job_page_green_observed",
        "remote_ci_run_observed_for_current_head",
        "remote_ci_review_receipt_is_not_release_review",
    )
    required_false = (
        "remote_ci_artifact_digest_pending",
        "remote_ci_run_in_progress_for_current_head",
        "remote_ci_no_matching_run_found_for_current_head",
        "remote_ci_run_lookup_attempted",
        "remote_ci_failure_reviewed_for_current_head",
        "remote_ci_failure_artifact_download_blocked",
        "release_review_complete",
        "release_gate_complete",
        "production_release_complete",
    )
    if not (
        all(receipt.get(field) is True for field in required_true)
        and all(receipt.get(field) is False for field in required_false)
    ):
        blockers.append("remote_ci_attestation_flags_inconsistent")
    if not _safe_boundary(receipt, cache_fields=True):
        blockers.append("remote_ci_safety_boundary_invalid")
    result = _evidence_result("remote_ci", ready=not blockers, material=material, blockers=blockers)
    result.update({"run_id": run_id, "artifact_digest": artifact_digest})
    return result


def _validate_allowlist(receipt: Mapping[str, Any], head_full: str) -> dict[str, Any]:
    field_types = {
        "schema_version": str,
        "status": str,
        "scope": str,
        "reviewed_at_utc": str,
        "receipt_writer": str,
        "reviewer": str,
        "branch": str,
        "head": str,
        "head_full": str,
        "manual_review_note_safe": str,
        "explicit_user_allowlist_review_authorized": bool,
        "periodic_allowlist_review_ready": bool,
        "false_positive_allowlist_review_ready": bool,
        "high_risk_secret_scan_status": str,
        "secret_keyword_review_status": str,
        "generated_artifact_scan_status": str,
        "release_review_complete": bool,
        "release_gate_complete": bool,
        "production_release_complete": bool,
        **_safe_type_fields(cache_fields=True),
    }
    blockers = _receipt_type_blockers(
        "allowlist",
        receipt,
        field_types,
    )
    material = _receipt_material(receipt)
    if receipt.get("schema_version") != audit_service.SECRET_ARTIFACT_ALLOWLIST_REVIEW_RECEIPT_SCHEMA_VERSION:
        blockers.append("allowlist_schema_invalid")
    if receipt.get("status") != "secret_artifact_allowlist_review_ready":
        blockers.append("allowlist_status_not_ready")
    if receipt.get("head_full") != head_full:
        blockers.append("allowlist_head_mismatch")
    if not (
        receipt.get("scope") == _ALLOWLIST_SCOPE
        and receipt.get("receipt_writer") == _ALLOWLIST_RECEIPT_WRITER
        and receipt.get("branch") == "main"
        and _valid_short_head(receipt.get("head"), head_full, exact_eight=True)
        and _valid_utc_second(receipt.get("reviewed_at_utc"))
        and bool(str(receipt.get("reviewer") or "").strip())
    ):
        blockers.append("allowlist_formal_recorder_identity_invalid")
    if receipt.get("explicit_user_allowlist_review_authorized") is not True:
        blockers.append("allowlist_review_not_authorized")
    if receipt.get("high_risk_secret_scan_status") not in (
        "clean",
        "passed_no_high_risk_values",
    ):
        blockers.append("allowlist_high_risk_scan_invalid")
    if receipt.get("secret_keyword_review_status") != "reviewed_no_high_risk_values":
        blockers.append("allowlist_keyword_review_invalid")
    if receipt.get("generated_artifact_scan_status") not in (
        "clean",
        "clean_or_allowed_assets_only",
    ):
        blockers.append("allowlist_artifact_scan_invalid")
    if not (
        receipt.get("periodic_allowlist_review_ready") is True
        and receipt.get("false_positive_allowlist_review_ready") is True
        and receipt.get("release_review_complete") is False
        and receipt.get("release_gate_complete") is False
        and receipt.get("production_release_complete") is False
    ):
        blockers.append("allowlist_completed_review_attestations_missing")
    if not _safe_boundary(receipt, cache_fields=True):
        blockers.append("allowlist_safety_boundary_invalid")
    return _evidence_result("allowlist", ready=not blockers, material=material, blockers=blockers)


def _validate_release_review(
    receipt: Mapping[str, Any],
    head_full: str,
    remote_ci: Mapping[str, Any],
) -> dict[str, Any]:
    field_types = {
        "schema_version": str,
        "status": str,
        "scope": str,
        "reviewed_at_utc": str,
        "receipt_writer": str,
        "reviewer": str,
        "branch": str,
        "head": str,
        "head_full": str,
        "manual_review_note_safe": str,
        "remote_run_id": str,
        "remote_artifact_digest": str,
        "decision": str,
        "explicit_user_release_review_authorized": bool,
        "release_review_complete": bool,
        "release_gate_complete": bool,
        "strict_closeout_ready": bool,
        "can_close_goal": bool,
        "production_release_complete": bool,
        **_safe_type_fields(cache_fields=True),
    }
    blockers = _receipt_type_blockers(
        "release_review",
        receipt,
        field_types,
    )
    material = _receipt_material(receipt)
    if receipt.get("schema_version") != audit_service.RELEASE_GATE_REVIEW_RECEIPT_SCHEMA_VERSION:
        blockers.append("release_review_schema_invalid")
    if receipt.get("status") != "release_gate_review_ready":
        blockers.append("release_review_status_not_ready")
    if receipt.get("head_full") != head_full:
        blockers.append("release_review_head_mismatch")
    if not (
        receipt.get("scope") == _RELEASE_REVIEW_SCOPE
        and receipt.get("receipt_writer") == _RELEASE_REVIEW_RECEIPT_WRITER
        and receipt.get("branch") == "main"
        and _valid_short_head(receipt.get("head"), head_full, exact_eight=True)
        and _valid_utc_second(receipt.get("reviewed_at_utc"))
        and bool(str(receipt.get("reviewer") or "").strip())
    ):
        blockers.append("release_review_formal_recorder_identity_invalid")
    if receipt.get("explicit_user_release_review_authorized") is not True:
        blockers.append("release_review_not_authorized")
    if receipt.get("decision") != "release_review_complete_strict_closeout_blocked":
        blockers.append("release_review_decision_invalid")
    if not (
        receipt.get("release_review_complete") is True
        and receipt.get("release_gate_complete") is False
        and receipt.get("strict_closeout_ready") is False
        and receipt.get("can_close_goal") is False
        and receipt.get("production_release_complete") is False
    ):
        blockers.append("release_review_not_complete")
    if not (
        remote_ci.get("ready") is True
        and receipt.get("remote_run_id") == remote_ci.get("run_id")
        and receipt.get("remote_artifact_digest") == remote_ci.get("artifact_digest")
    ):
        blockers.append("release_review_remote_evidence_mismatch")
    if not _safe_boundary(receipt, cache_fields=True):
        blockers.append("release_review_safety_boundary_invalid")
    return _evidence_result("release_review", ready=not blockers, material=material, blockers=blockers)


def validate_release_prerequisites(
    evidence_root: Path | str = EVIDENCE_ROOT,
    *,
    expected_head_full: str | None = None,
) -> dict[str, Any]:
    """Validate formal evidence from disk without creating tasks or storage."""
    root = Path(evidence_root).expanduser().resolve()
    head_full, head_blockers = _resolve_head(expected_head_full)
    release_root = root / "release_gate"
    local_gate = _validate_evidence_fail_closed(
        "local_push_gate",
        _validate_local_gate,
        _read_json(release_root / "local_push_gate_run_receipt.json"),
        head_full,
    )
    remote_ci = _validate_evidence_fail_closed(
        "remote_ci",
        _validate_remote_ci,
        _read_json(release_root / "remote_ci_review_receipt.json"),
        head_full,
    )
    allowlist = _validate_evidence_fail_closed(
        "allowlist",
        _validate_allowlist,
        _read_json(release_root / "secret_artifact_allowlist_review_receipt.json"),
        head_full,
    )
    release_review = _validate_evidence_fail_closed(
        "release_review",
        _validate_release_review,
        _read_json(release_root / "release_gate_review_receipt.json"),
        head_full,
        remote_ci,
    )
    rows = [local_gate, remote_ci, allowlist, release_review]
    blockers = list(head_blockers) + [
        blocker
        for row in rows
        for blocker in row.get("blockers", [])
        if isinstance(blocker, str)
    ]
    return {
        "schema_version": "command_center_3_release_promotion_prerequisites.v1",
        "status": "release_promotion_prerequisites_ready" if not blockers else "release_promotion_prerequisites_blocked",
        "head_full": head_full,
        "ready": not blockers,
        "rows": rows,
        "blockers": blockers,
        "remote_run_id": remote_ci.get("run_id", ""),
        "remote_artifact_digest": remote_ci.get("artifact_digest", ""),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _journal_path(evidence_root: Path | str) -> Path:
    return Path(evidence_root).expanduser().resolve() / "release_gate" / JOURNAL_NAME


def _trust_paths(evidence_root: Path | str) -> tuple[Path, Path]:
    release_root = Path(evidence_root).expanduser().resolve() / "release_gate"
    trust_directory = release_root / _TRUST_DIRECTORY_NAME
    return trust_directory, trust_directory / _TRUST_KEY_NAME


def _trust_state_path(evidence_root: Path | str) -> Path:
    trust_directory, _ = _trust_paths(evidence_root)
    return trust_directory / _TRUST_STATE_NAME


def _owned_by_current_user(metadata: os.stat_result) -> bool:
    getuid = getattr(os, "getuid", None)
    return getuid is None or metadata.st_uid == getuid()


def _load_trusted_writer_secret(
    evidence_root: Path | str,
) -> tuple[bytes | None, str]:
    """Read the install-local writer key without creating or repairing anything."""
    trust_directory, key_path = _trust_paths(evidence_root)
    try:
        directory_metadata = trust_directory.lstat()
    except FileNotFoundError:
        return None, _TRUST_KEY_MISSING_BLOCKER
    except OSError:
        return None, _TRUST_KEY_CORRUPT_BLOCKER
    if not (
        stat.S_ISDIR(directory_metadata.st_mode)
        and not stat.S_ISLNK(directory_metadata.st_mode)
        and stat.S_IMODE(directory_metadata.st_mode) == 0o700
        and _owned_by_current_user(directory_metadata)
    ):
        return None, _TRUST_KEY_PERMISSIONS_BLOCKER
    try:
        key_metadata = key_path.lstat()
    except FileNotFoundError:
        return None, _TRUST_KEY_MISSING_BLOCKER
    except OSError:
        return None, _TRUST_KEY_CORRUPT_BLOCKER
    if not (
        stat.S_ISREG(key_metadata.st_mode)
        and not stat.S_ISLNK(key_metadata.st_mode)
        and stat.S_IMODE(key_metadata.st_mode) == 0o600
        and _owned_by_current_user(key_metadata)
    ):
        return None, _TRUST_KEY_PERMISSIONS_BLOCKER
    try:
        entry_names = {entry.name for entry in trust_directory.iterdir()}
    except OSError:
        return None, _TRUST_KEY_CORRUPT_BLOCKER
    if _TRUST_KEY_NAME not in entry_names or not entry_names.issubset(
        {_TRUST_KEY_NAME, _TRUST_STATE_NAME}
    ):
        return None, _TRUST_KEY_CORRUPT_BLOCKER
    flags = os.O_RDONLY
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW", "O_NOATIME"):
        flags |= int(getattr(os, flag_name, 0))
    descriptor = -1
    try:
        descriptor = os.open(key_path, flags)
        opened_metadata = os.fstat(descriptor)
        if not (
            stat.S_ISREG(opened_metadata.st_mode)
            and opened_metadata.st_dev == key_metadata.st_dev
            and opened_metadata.st_ino == key_metadata.st_ino
            and stat.S_IMODE(opened_metadata.st_mode) == 0o600
            and _owned_by_current_user(opened_metadata)
        ):
            return None, _TRUST_KEY_PERMISSIONS_BLOCKER
        secret = b""
        while len(secret) <= _TRUST_KEY_BYTES:
            chunk = os.read(descriptor, _TRUST_KEY_BYTES + 1 - len(secret))
            if not chunk:
                break
            secret += chunk
    except OSError:
        return None, _TRUST_KEY_CORRUPT_BLOCKER
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(secret) != _TRUST_KEY_BYTES:
        return None, _TRUST_KEY_CORRUPT_BLOCKER
    return secret, ""


def _create_trusted_writer_secret(
    evidence_root: Path | str,
) -> tuple[bytes | None, str]:
    """Atomically install the key; only an approved POST may call this helper."""
    trust_directory, key_path = _trust_paths(evidence_root)
    try:
        trust_directory.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError:
        existing, blocker = _load_trusted_writer_secret(evidence_root)
        if existing is not None or blocker != _TRUST_KEY_MISSING_BLOCKER:
            return existing, blocker
    except OSError:
        return None, _TRUST_KEY_CORRUPT_BLOCKER

    # mkdir honours umask by removing permissions; never broaden them here.
    try:
        directory_metadata = trust_directory.lstat()
    except OSError:
        return None, _TRUST_KEY_CORRUPT_BLOCKER
    if not (
        stat.S_ISDIR(directory_metadata.st_mode)
        and stat.S_IMODE(directory_metadata.st_mode) == 0o700
        and _owned_by_current_user(directory_metadata)
    ):
        return None, _TRUST_KEY_PERMISSIONS_BLOCKER
    try:
        if any(trust_directory.iterdir()):
            return None, _TRUST_KEY_CORRUPT_BLOCKER
    except OSError:
        return None, _TRUST_KEY_CORRUPT_BLOCKER

    temporary_path = trust_directory / f".{_TRUST_KEY_NAME}.{secrets.token_hex(12)}.tmp"
    descriptor = -1
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        for flag_name in ("O_CLOEXEC", "O_NOFOLLOW"):
            flags |= int(getattr(os, flag_name, 0))
        descriptor = os.open(temporary_path, flags, 0o600)
        secret = secrets.token_bytes(_TRUST_KEY_BYTES)
        offset = 0
        while offset < len(secret):
            offset += os.write(descriptor, secret[offset:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        try:
            os.link(temporary_path, key_path, follow_symlinks=False)
        except FileExistsError:
            temporary_path.unlink(missing_ok=True)
            return _load_trusted_writer_secret(evidence_root)
        temporary_path.unlink()
        directory_flags = os.O_RDONLY | int(getattr(os, "O_DIRECTORY", 0))
        directory_descriptor = os.open(trust_directory, directory_flags)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)
        return None, _TRUST_KEY_CORRUPT_BLOCKER
    return _load_trusted_writer_secret(evidence_root)


def _trusted_writer_state_material(
    *,
    sequence_no: int,
    event_id: str,
    event_mac: str,
) -> dict[str, Any]:
    return {
        "schema_version": _TRUST_STATE_SCHEMA_VERSION,
        "sequence_no": sequence_no,
        "event_id": event_id,
        "event_mac": event_mac,
    }


def _load_trusted_writer_state(
    evidence_root: Path | str,
    trusted_writer_secret: bytes,
) -> tuple[dict[str, Any] | None, str]:
    state_path = _trust_state_path(evidence_root)
    try:
        metadata = state_path.lstat()
    except FileNotFoundError:
        return None, _TRUST_STATE_MISSING_BLOCKER
    except OSError:
        return None, _TRUST_STATE_CORRUPT_BLOCKER
    if not (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) == 0o600
        and _owned_by_current_user(metadata)
    ):
        return None, _TRUST_STATE_PERMISSIONS_BLOCKER
    flags = os.O_RDONLY
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW", "O_NOATIME"):
        flags |= int(getattr(os, flag_name, 0))
    descriptor = -1
    try:
        descriptor = os.open(state_path, flags)
        opened_metadata = os.fstat(descriptor)
        if not (
            stat.S_ISREG(opened_metadata.st_mode)
            and opened_metadata.st_dev == metadata.st_dev
            and opened_metadata.st_ino == metadata.st_ino
            and stat.S_IMODE(opened_metadata.st_mode) == 0o600
            and _owned_by_current_user(opened_metadata)
        ):
            return None, _TRUST_STATE_PERMISSIONS_BLOCKER
        payload = b""
        while len(payload) <= 4096:
            chunk = os.read(descriptor, 4097 - len(payload))
            if not chunk:
                break
            payload += chunk
    except OSError:
        return None, _TRUST_STATE_CORRUPT_BLOCKER
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not payload or len(payload) > 4096:
        return None, _TRUST_STATE_CORRUPT_BLOCKER
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None, _TRUST_STATE_CORRUPT_BLOCKER
    if not isinstance(decoded, Mapping) or set(decoded) != {
        "schema_version",
        "sequence_no",
        "event_id",
        "event_mac",
        "state_mac",
    }:
        return None, _TRUST_STATE_CORRUPT_BLOCKER
    state = dict(decoded)
    if not (
        state.get("schema_version") == _TRUST_STATE_SCHEMA_VERSION
        and type(state.get("sequence_no")) is int
        and int(state["sequence_no"]) > 0
        and _valid_lower_sha256(state.get("event_id"))
        and _valid_lower_sha256(state.get("event_mac"))
        and _valid_lower_sha256(state.get("state_mac"))
    ):
        return None, _TRUST_STATE_CORRUPT_BLOCKER
    material = _trusted_writer_state_material(
        sequence_no=int(state["sequence_no"]),
        event_id=str(state["event_id"]),
        event_mac=str(state["event_mac"]),
    )
    expected_mac = _trusted_event_mac(trusted_writer_secret, material)
    if not hmac.compare_digest(str(state["state_mac"]), expected_mac):
        return None, _TRUST_STATE_CORRUPT_BLOCKER
    return state, ""


def _write_trusted_writer_state(
    evidence_root: Path | str,
    trusted_writer_secret: bytes,
    *,
    sequence_no: int,
    event_id: str,
    event_mac: str,
) -> str:
    trust_directory, _ = _trust_paths(evidence_root)
    state_path = _trust_state_path(evidence_root)
    material = _trusted_writer_state_material(
        sequence_no=sequence_no,
        event_id=event_id,
        event_mac=event_mac,
    )
    payload = {
        **material,
        "state_mac": _trusted_event_mac(trusted_writer_secret, material),
    }
    encoded = _canonical_bytes(payload)
    temporary_path = trust_directory / f".{_TRUST_STATE_NAME}.{secrets.token_hex(12)}.tmp"
    descriptor = -1
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        for flag_name in ("O_CLOEXEC", "O_NOFOLLOW"):
            flags |= int(getattr(os, flag_name, 0))
        descriptor = os.open(temporary_path, flags, 0o600)
        offset = 0
        while offset < len(encoded):
            offset += os.write(descriptor, encoded[offset:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary_path, state_path)
        directory_flags = os.O_RDONLY | int(getattr(os, "O_DIRECTORY", 0))
        directory_descriptor = os.open(trust_directory, directory_flags)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)
        return _TRUST_STATE_CORRUPT_BLOCKER
    loaded, blocker = _load_trusted_writer_state(
        evidence_root,
        trusted_writer_secret,
    )
    if blocker or loaded is None:
        return blocker or _TRUST_STATE_CORRUPT_BLOCKER
    return ""


def _connect_read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _normalize_ddl(value: object) -> str:
    return " ".join(str(value or "").split())


def _expected_journal_schema_material() -> dict[str, Any]:
    return {
        "objects": [
            ("table", _CURRENT_TABLE, _CURRENT_TABLE, _normalize_ddl(_CURRENT_TABLE_DDL)),
            ("table", _EVENT_TABLE, _EVENT_TABLE, _normalize_ddl(_EVENT_TABLE_DDL)),
            (
                "trigger",
                _EVENT_NO_DELETE_TRIGGER,
                _EVENT_TABLE,
                _normalize_ddl(_EVENT_NO_DELETE_TRIGGER_DDL),
            ),
            (
                "trigger",
                _EVENT_NO_UPDATE_TRIGGER,
                _EVENT_TABLE,
                _normalize_ddl(_EVENT_NO_UPDATE_TRIGGER_DDL),
            ),
        ],
        "event_table_info": list(_EXPECTED_EVENT_TABLE_INFO),
        "current_table_info": list(_EXPECTED_CURRENT_TABLE_INFO),
        "event_indexes": list(_EXPECTED_EVENT_INDEXES),
        "current_indexes": list(_EXPECTED_CURRENT_INDEXES),
        "event_foreign_keys": [],
        "current_foreign_keys": list(_EXPECTED_CURRENT_FOREIGN_KEYS),
    }


def _event_semantic_material(
    *,
    schema_version: str,
    scope: str,
    head_full: str,
    local_gate_digest: str,
    remote_ci_digest: str,
    allowlist_digest: str,
    release_review_digest: str,
    remote_run_id: str,
    remote_artifact_digest: str,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "scope": scope,
        "head_full": head_full,
        "local_gate_digest": local_gate_digest,
        "remote_ci_digest": remote_ci_digest,
        "allowlist_digest": allowlist_digest,
        "release_review_digest": release_review_digest,
        "remote_run_id": remote_run_id,
        "remote_artifact_digest": remote_artifact_digest,
        "approved_by_user": True,
    }


def _canonical_event_material(
    semantic_material: Mapping[str, Any],
    *,
    sequence_no: int,
    semantic_digest: str,
    promoted_at_utc: str,
    previous_event_mac: str,
) -> dict[str, Any]:
    return {
        **dict(semantic_material),
        "sequence_no": sequence_no,
        "semantic_digest": semantic_digest,
        "promoted_at_utc": promoted_at_utc,
        "previous_event_mac": previous_event_mac,
    }


def _event_authentication_material(
    canonical_event: Mapping[str, Any],
    *,
    event_id: str,
) -> dict[str, Any]:
    return {**dict(canonical_event), "event_id": event_id}


def _journal_row_integrity_blocker(
    connection: sqlite3.Connection,
    trusted_writer_secret: bytes,
    trusted_writer_state: Mapping[str, Any] | None,
) -> str:
    """Authenticate the pointer and every chained append-only event."""
    event_columns = (
        "event_id, sequence_no, semantic_digest, schema_version, scope, head_full, "
        "local_gate_digest, "
        "remote_ci_digest, allowlist_digest, release_review_digest, remote_run_id, "
        "remote_artifact_digest, approved_by_user, promoted_at_utc, previous_event_mac, "
        "event_mac"
    )
    events = connection.execute(
        f"SELECT {event_columns} FROM {_EVENT_TABLE} ORDER BY sequence_no, rowid"
    ).fetchall()
    pointers = connection.execute(
        f"SELECT scope, event_id, sequence_no, head_full, promoted_at_utc, event_mac "
        f"FROM {_CURRENT_TABLE}"
    ).fetchall()
    if not events:
        return "" if not pointers and trusted_writer_state is None else _JOURNAL_INVALID_BLOCKER
    if len(pointers) != 1 or trusted_writer_state is None:
        return _JOURNAL_INVALID_BLOCKER

    event_by_id: dict[str, tuple[Any, ...]] = {}
    observed_event_macs: set[str] = set()
    previous_event_mac = ""
    previous_timestamp = ""
    for expected_sequence, event in enumerate(events, start=1):
        if len(event) != 16:
            return _JOURNAL_INVALID_BLOCKER
        (
            event_id,
            sequence_no,
            semantic_digest,
            schema_version,
            scope,
            head_full,
            local_gate_digest,
            remote_ci_digest,
            allowlist_digest,
            release_review_digest,
            remote_run_id,
            remote_artifact_digest,
            approved_by_user,
            promoted_at_utc,
            stored_previous_event_mac,
            event_mac,
        ) = event
        string_fields = (
            event_id,
            semantic_digest,
            schema_version,
            scope,
            head_full,
            local_gate_digest,
            remote_ci_digest,
            allowlist_digest,
            release_review_digest,
            remote_run_id,
            remote_artifact_digest,
            promoted_at_utc,
            stored_previous_event_mac,
            event_mac,
        )
        if not all(type(value) is str for value in string_fields):
            return _JOURNAL_INVALID_BLOCKER
        if not (
            type(sequence_no) is int
            and sequence_no == expected_sequence
            and schema_version == EVENT_SCHEMA_VERSION
            and scope == PROMOTION_SCOPE
            and _normalize_head(head_full) == head_full
            and all(
                _valid_lower_sha256(value)
                for value in (
                    event_id,
                    semantic_digest,
                    local_gate_digest,
                    remote_ci_digest,
                    allowlist_digest,
                    release_review_digest,
                )
            )
            and _valid_ascii_decimal(remote_run_id)
            and int(remote_run_id) > 0
            and _valid_lower_sha256(remote_artifact_digest, prefix=True)
            and type(approved_by_user) is int
            and approved_by_user == 1
            and _valid_utc_second(promoted_at_utc)
            and (not previous_timestamp or promoted_at_utc >= previous_timestamp)
            and stored_previous_event_mac == previous_event_mac
            and (
                (sequence_no == 1 and stored_previous_event_mac == "")
                or (
                    sequence_no > 1
                    and _valid_lower_sha256(stored_previous_event_mac)
                )
            )
            and _valid_lower_sha256(event_mac)
            and event_mac not in observed_event_macs
        ):
            return _JOURNAL_INVALID_BLOCKER
        semantic_material = _event_semantic_material(
            schema_version=schema_version,
            scope=scope,
            head_full=head_full,
            local_gate_digest=local_gate_digest,
            remote_ci_digest=remote_ci_digest,
            allowlist_digest=allowlist_digest,
            release_review_digest=release_review_digest,
            remote_run_id=remote_run_id,
            remote_artifact_digest=remote_artifact_digest,
        )
        if semantic_digest != _digest(semantic_material):
            return _JOURNAL_INVALID_BLOCKER
        canonical_event = _canonical_event_material(
            semantic_material,
            sequence_no=sequence_no,
            semantic_digest=semantic_digest,
            promoted_at_utc=promoted_at_utc,
            previous_event_mac=stored_previous_event_mac,
        )
        expected_event_id = _digest(canonical_event)
        expected_event_mac = _trusted_event_mac(
            trusted_writer_secret,
            _event_authentication_material(canonical_event, event_id=expected_event_id),
        )
        if not (
            event_id == expected_event_id
            and event_id not in event_by_id
            and hmac.compare_digest(event_mac, expected_event_mac)
        ):
            return _JOURNAL_INVALID_BLOCKER
        event_by_id[event_id] = event
        observed_event_macs.add(event_mac)
        previous_event_mac = event_mac
        previous_timestamp = promoted_at_utc

    (
        pointer_scope,
        pointer_event_id,
        pointer_sequence,
        pointer_head,
        pointer_timestamp,
        pointer_event_mac,
    ) = pointers[0]
    if not all(
        type(value) is str
        for value in (
            pointer_scope,
            pointer_event_id,
            pointer_head,
            pointer_timestamp,
            pointer_event_mac,
        )
    ):
        return _JOURNAL_INVALID_BLOCKER
    if type(pointer_sequence) is not int:
        return _JOURNAL_INVALID_BLOCKER
    pointed_event = event_by_id.get(pointer_event_id)
    if not (
        pointer_scope == PROMOTION_SCOPE
        and pointed_event is not None
        and pointer_sequence == len(events)
        and pointer_sequence == pointed_event[1]
        and pointer_head == pointed_event[5]
        and _normalize_head(pointer_head) == pointer_head
        and _valid_utc_second(pointer_timestamp)
        and pointer_timestamp == pointed_event[13]
        and pointer_event_mac == pointed_event[15]
        and hmac.compare_digest(pointer_event_mac, previous_event_mac)
        and trusted_writer_state.get("sequence_no") == pointer_sequence
        and trusted_writer_state.get("event_id") == pointer_event_id
        and trusted_writer_state.get("event_mac") == pointer_event_mac
    ):
        return _JOURNAL_INVALID_BLOCKER
    return ""


def _journal_schema_material(connection: sqlite3.Connection) -> dict[str, Any]:
    objects = [
        (str(row[0]), str(row[1]), str(row[2]), _normalize_ddl(row[3]))
        for row in connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
    ]

    def table_info(table: str) -> list[tuple[Any, ...]]:
        return [tuple(row) for row in connection.execute(f"PRAGMA table_info({table})")]

    def indexes(table: str) -> list[tuple[Any, ...]]:
        return [
            (str(row[1]), int(row[2]), str(row[3]), int(row[4]))
            for row in connection.execute(f"PRAGMA index_list({table})")
        ]

    def foreign_keys(table: str) -> list[tuple[Any, ...]]:
        return [tuple(row) for row in connection.execute(f"PRAGMA foreign_key_list({table})")]

    return {
        "objects": objects,
        "event_table_info": table_info(_EVENT_TABLE),
        "current_table_info": table_info(_CURRENT_TABLE),
        "event_indexes": indexes(_EVENT_TABLE),
        "current_indexes": indexes(_CURRENT_TABLE),
        "event_foreign_keys": foreign_keys(_EVENT_TABLE),
        "current_foreign_keys": foreign_keys(_CURRENT_TABLE),
    }


def _existing_journal_state(
    path: Path,
    trusted_writer_secret: bytes | None,
    trusted_writer_state: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    state = {"blocker": "", "schema_fingerprint": ""}
    if not path.exists():
        return state
    if not path.is_file():
        state["blocker"] = _JOURNAL_INVALID_BLOCKER
        return state
    try:
        with path.open("rb") as stream:
            if stream.read(16) != b"SQLite format 3\x00":
                state["blocker"] = _JOURNAL_INVALID_BLOCKER
                return state
        with _connect_read_only(path) as connection:
            quick_check = connection.execute("PRAGMA quick_check").fetchone()
            if quick_check != ("ok",):
                state["blocker"] = _JOURNAL_INVALID_BLOCKER
                return state
            schema_material = _journal_schema_material(connection)
            state["schema_fingerprint"] = _digest(schema_material)
            expected_material = _expected_journal_schema_material()
            if (
                schema_material != expected_material
                or state["schema_fingerprint"] != _digest(expected_material)
                or connection.execute("PRAGMA foreign_key_check").fetchall()
                or (
                    trusted_writer_secret is not None
                    and _journal_row_integrity_blocker(
                        connection,
                        trusted_writer_secret,
                        trusted_writer_state,
                    )
                )
            ):
                state["blocker"] = _JOURNAL_INVALID_BLOCKER
    except (OSError, sqlite3.Error):
        state["blocker"] = _JOURNAL_INVALID_BLOCKER
    return state


def validate_production_release_promotion(
    evidence_root: Path | str = EVIDENCE_ROOT,
    *,
    expected_head_full: str | None = None,
) -> dict[str, Any]:
    """Revalidate the current pointer and every bound prerequisite, read-only."""
    prerequisites = validate_release_prerequisites(
        evidence_root,
        expected_head_full=expected_head_full,
    )
    head_full = str(prerequisites.get("head_full") or "")
    path = _journal_path(evidence_root)
    blockers = list(prerequisites.get("blockers") or [])
    pointer: tuple[Any, ...] | None = None
    event: tuple[Any, ...] | None = None
    trusted_writer_secret, trust_blocker = _load_trusted_writer_secret(evidence_root)
    trusted_writer_state: dict[str, Any] | None = None
    if trust_blocker:
        blockers.append(trust_blocker)
    elif trusted_writer_secret is not None:
        trusted_writer_state, state_blocker = _load_trusted_writer_state(
            evidence_root,
            trusted_writer_secret,
        )
        if state_blocker:
            blockers.append(state_blocker)
    journal_state = _existing_journal_state(
        path,
        trusted_writer_secret,
        trusted_writer_state,
    )
    journal_blocker = journal_state["blocker"]
    if not path.exists():
        blockers.append("production_release_promotion_journal_missing")
    elif journal_blocker:
        blockers.append(journal_blocker)
    elif trusted_writer_secret is not None:
        try:
            with _connect_read_only(path) as connection:
                pointer = connection.execute(
                    "SELECT event_id, sequence_no, head_full, promoted_at_utc, event_mac "
                    "FROM production_release_promotion_current WHERE scope = ?",
                    (PROMOTION_SCOPE,),
                ).fetchone()
                if pointer:
                    event = connection.execute(
                        "SELECT event_id, sequence_no, semantic_digest, schema_version, "
                        "scope, head_full, "
                        "local_gate_digest, remote_ci_digest, "
                        "allowlist_digest, release_review_digest, remote_run_id, "
                        "remote_artifact_digest, approved_by_user, promoted_at_utc, "
                        "previous_event_mac, event_mac "
                        "FROM production_release_promotion_events WHERE event_id = ?",
                        (pointer[0],),
                    ).fetchone()
        except (OSError, sqlite3.Error):
            blockers.append(_JOURNAL_INVALID_BLOCKER)
    if pointer is None and path.is_file() and not journal_blocker:
        blockers.append("production_release_current_pointer_missing")
    if pointer is not None and pointer[2] != head_full:
        blockers.append("production_release_pointer_head_mismatch")
    if pointer is not None and event is None:
        blockers.append("production_release_event_missing")
    if event is not None:
        rows = {str(row.get("evidence_key")): row for row in prerequisites.get("rows", [])}
        semantic_material = _event_semantic_material(
            schema_version=EVENT_SCHEMA_VERSION,
            scope=PROMOTION_SCOPE,
            head_full=head_full,
            local_gate_digest=str(
                rows.get("local_push_gate", {}).get("semantic_digest", "")
            ),
            remote_ci_digest=str(rows.get("remote_ci", {}).get("semantic_digest", "")),
            allowlist_digest=str(rows.get("allowlist", {}).get("semantic_digest", "")),
            release_review_digest=str(
                rows.get("release_review", {}).get("semantic_digest", "")
            ),
            remote_run_id=str(prerequisites.get("remote_run_id", "")),
            remote_artifact_digest=str(
                prerequisites.get("remote_artifact_digest", "")
            ),
        )
        expected_semantic_digest = _digest(semantic_material)
        expected_semantic_fields = (
            EVENT_SCHEMA_VERSION,
            PROMOTION_SCOPE,
            head_full,
            semantic_material["local_gate_digest"],
            semantic_material["remote_ci_digest"],
            semantic_material["allowlist_digest"],
            semantic_material["release_review_digest"],
            semantic_material["remote_run_id"],
            semantic_material["remote_artifact_digest"],
            1,
        )
        if event[2] != expected_semantic_digest or event[3:13] != expected_semantic_fields:
            blockers.append("production_release_event_evidence_binding_mismatch")
        if not (
            _valid_utc_second(pointer[3] if pointer else None)
            and _valid_utc_second(event[13])
            and pointer is not None
            and pointer[1] == event[1]
            and pointer[3] == event[13]
            and pointer[4] == event[15]
        ):
            blockers.append("production_release_promotion_timestamp_invalid")
    ready = bool(prerequisites.get("ready") is True and event is not None and not blockers)
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "status": "production_release_promoted_current_head" if ready else "production_release_promotion_blocked",
        "scope": PROMOTION_SCOPE,
        "head_full": head_full,
        "journal_present": path.is_file(),
        "journal_schema_fingerprint": journal_state["schema_fingerprint"],
        "event_id": str(event[0]) if event else "",
        "release_promotion_current_head": ready,
        "release_gate_complete": ready,
        "release_review_complete": ready,
        "production_release_complete": ready,
        "blockers": sorted(set(blockers)),
        "read_only": True,
        "writes_storage": False,
        "creates_task": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def promote_production_release(
    payload: Any = None,
    *,
    evidence_root: Path | str = EVIDENCE_ROOT,
    expected_head_full: str | None = None,
) -> dict[str, Any]:
    """Atomically append and point to a validated current-HEAD promotion."""
    request = dict(payload) if isinstance(payload, Mapping) else {}
    approved = request.get("approved_by_user") is True
    prerequisites = validate_release_prerequisites(
        evidence_root,
        expected_head_full=expected_head_full,
    )
    if not approved or prerequisites.get("ready") is not True:
        blockers = list(prerequisites.get("blockers") or [])
        if not approved:
            blockers.insert(0, "explicit_user_production_promotion_approval_required")
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "status": "production_release_promotion_blocked",
            "scope": PROMOTION_SCOPE,
            "head_full": prerequisites.get("head_full", ""),
            "promotion_written": False,
            "release_promotion_current_head": False,
            "blockers": blockers,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "github_api_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    path = _journal_path(evidence_root)
    trusted_writer_secret, trust_blocker = _load_trusted_writer_secret(evidence_root)
    if trusted_writer_secret is None and trust_blocker == _TRUST_KEY_MISSING_BLOCKER:
        if path.exists():
            unauthenticated_state = _existing_journal_state(path, None)
            unauthenticated_blockers = [trust_blocker]
            if unauthenticated_state["blocker"]:
                unauthenticated_blockers.append(unauthenticated_state["blocker"])
            return {
                "schema_version": VALIDATION_SCHEMA_VERSION,
                "status": "production_release_promotion_blocked",
                "scope": PROMOTION_SCOPE,
                "head_full": prerequisites.get("head_full", ""),
                "journal_present": True,
                "promotion_written": False,
                "release_promotion_current_head": False,
                "blockers": unauthenticated_blockers,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "github_api_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
            }
        trusted_writer_secret, trust_blocker = _create_trusted_writer_secret(evidence_root)
    if trusted_writer_secret is None:
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "status": "production_release_promotion_blocked",
            "scope": PROMOTION_SCOPE,
            "head_full": prerequisites.get("head_full", ""),
            "journal_present": path.exists(),
            "promotion_written": False,
            "release_promotion_current_head": False,
            "blockers": [trust_blocker or _TRUST_KEY_CORRUPT_BLOCKER],
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "github_api_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    trusted_writer_state, state_blocker = _load_trusted_writer_state(
        evidence_root,
        trusted_writer_secret,
    )
    if state_blocker and state_blocker != _TRUST_STATE_MISSING_BLOCKER:
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "status": "production_release_promotion_blocked",
            "scope": PROMOTION_SCOPE,
            "head_full": prerequisites.get("head_full", ""),
            "journal_present": path.exists(),
            "promotion_written": False,
            "release_promotion_current_head": False,
            "blockers": [state_blocker],
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "github_api_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    if not path.exists() and trusted_writer_state is not None:
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "status": "production_release_promotion_blocked",
            "scope": PROMOTION_SCOPE,
            "head_full": prerequisites.get("head_full", ""),
            "journal_present": False,
            "promotion_written": False,
            "release_promotion_current_head": False,
            "blockers": [_JOURNAL_INVALID_BLOCKER],
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "github_api_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    journal_state = _existing_journal_state(
        path,
        trusted_writer_secret,
        trusted_writer_state,
    )
    journal_blocker = journal_state["blocker"]
    if journal_blocker:
        journal_blockers = [journal_blocker]
        if state_blocker:
            journal_blockers.insert(0, state_blocker)
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "status": "production_release_promotion_blocked",
            "scope": PROMOTION_SCOPE,
            "head_full": prerequisites.get("head_full", ""),
            "journal_present": path.exists(),
            "journal_schema_fingerprint": journal_state["schema_fingerprint"],
            "promotion_written": False,
            "release_promotion_current_head": False,
            "blockers": journal_blockers,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "github_api_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    rows = {str(row.get("evidence_key")): row for row in prerequisites.get("rows", [])}
    semantic_material = _event_semantic_material(
        schema_version=EVENT_SCHEMA_VERSION,
        scope=PROMOTION_SCOPE,
        head_full=str(prerequisites["head_full"]),
        local_gate_digest=str(rows["local_push_gate"]["semantic_digest"]),
        remote_ci_digest=str(rows["remote_ci"]["semantic_digest"]),
        allowlist_digest=str(rows["allowlist"]["semantic_digest"]),
        release_review_digest=str(rows["release_review"]["semantic_digest"]),
        remote_run_id=str(prerequisites["remote_run_id"]),
        remote_artifact_digest=str(prerequisites["remote_artifact_digest"]),
    )
    semantic_digest = _digest(semantic_material)
    path.parent.mkdir(parents=True, exist_ok=True)
    inserted = False
    pointer_changed = False
    event_id = ""
    new_sequence_no = 0
    new_event_mac = ""
    integrity_blocked = False
    try:
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(_CREATE_EVENT_TABLE_DDL)
            connection.execute(_CREATE_CURRENT_TABLE_DDL)
            connection.execute(_CREATE_EVENT_NO_UPDATE_TRIGGER_DDL)
            connection.execute(_CREATE_EVENT_NO_DELETE_TRIGGER_DDL)
            if (
                _journal_schema_material(connection)
                != _expected_journal_schema_material()
                or connection.execute("PRAGMA foreign_key_check").fetchall()
                or _journal_row_integrity_blocker(
                    connection,
                    trusted_writer_secret,
                    trusted_writer_state,
                )
            ):
                integrity_blocked = True
                raise sqlite3.IntegrityError("journal integrity validation failed")
            latest = connection.execute(
                "SELECT event_id, sequence_no, semantic_digest, promoted_at_utc, event_mac "
                "FROM production_release_promotion_events ORDER BY sequence_no DESC LIMIT 1"
            ).fetchone()
            if latest is not None and latest[2] == semantic_digest:
                event_id = str(latest[0])
            else:
                sequence_no = int(latest[1]) + 1 if latest is not None else 1
                previous_event_mac = str(latest[4]) if latest is not None else ""
                promoted_at = _now_iso()
                if latest is not None and promoted_at < str(latest[3]):
                    integrity_blocked = True
                    raise sqlite3.IntegrityError("trusted writer clock moved backwards")
                canonical_event = _canonical_event_material(
                    semantic_material,
                    sequence_no=sequence_no,
                    semantic_digest=semantic_digest,
                    promoted_at_utc=promoted_at,
                    previous_event_mac=previous_event_mac,
                )
                event_id = _digest(canonical_event)
                event_mac = _trusted_event_mac(
                    trusted_writer_secret,
                    _event_authentication_material(canonical_event, event_id=event_id),
                )
                new_sequence_no = sequence_no
                new_event_mac = event_mac
                connection.execute(
                    "INSERT INTO production_release_promotion_events "
                    "(event_id, sequence_no, semantic_digest, schema_version, scope, "
                    "head_full, local_gate_digest, remote_ci_digest, allowlist_digest, "
                    "release_review_digest, remote_run_id, remote_artifact_digest, "
                    "approved_by_user, promoted_at_utc, previous_event_mac, event_mac) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
                    (
                        event_id,
                        sequence_no,
                        semantic_digest,
                        EVENT_SCHEMA_VERSION,
                        PROMOTION_SCOPE,
                        semantic_material["head_full"],
                        semantic_material["local_gate_digest"],
                        semantic_material["remote_ci_digest"],
                        semantic_material["allowlist_digest"],
                        semantic_material["release_review_digest"],
                        semantic_material["remote_run_id"],
                        semantic_material["remote_artifact_digest"],
                        promoted_at,
                        previous_event_mac,
                        event_mac,
                    ),
                )
                inserted = True
                connection.execute(
                    "INSERT INTO production_release_promotion_current "
                    "(scope, event_id, sequence_no, head_full, promoted_at_utc, event_mac) "
                    "VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(scope) DO UPDATE SET event_id=excluded.event_id, "
                    "sequence_no=excluded.sequence_no, head_full=excluded.head_full, "
                    "promoted_at_utc=excluded.promoted_at_utc, event_mac=excluded.event_mac",
                    (
                        PROMOTION_SCOPE,
                        event_id,
                        sequence_no,
                        semantic_material["head_full"],
                        promoted_at,
                        event_mac,
                    ),
                )
                pointer_changed = True
            connection.commit()
    except (OSError, sqlite3.Error):
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "status": "production_release_promotion_blocked",
            "scope": PROMOTION_SCOPE,
            "head_full": prerequisites.get("head_full", ""),
            "journal_present": path.exists(),
            "promotion_written": False,
            "release_promotion_current_head": False,
            "blockers": [
                _JOURNAL_INVALID_BLOCKER
                if integrity_blocked
                else "production_release_promotion_journal_write_failed"
            ],
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "github_api_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    if inserted:
        state_write_blocker = _write_trusted_writer_state(
            evidence_root,
            trusted_writer_secret,
            sequence_no=new_sequence_no,
            event_id=event_id,
            event_mac=new_event_mac,
        )
        if state_write_blocker:
            return {
                "schema_version": VALIDATION_SCHEMA_VERSION,
                "status": "production_release_promotion_blocked",
                "scope": PROMOTION_SCOPE,
                "head_full": prerequisites.get("head_full", ""),
                "journal_present": path.exists(),
                "promotion_written": True,
                "idempotent_replay": False,
                "release_promotion_current_head": False,
                "blockers": [state_write_blocker],
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "github_api_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
            }
    result = validate_production_release_promotion(
        evidence_root,
        expected_head_full=str(semantic_material["head_full"]),
    )
    result.update(
        {
            "promotion_written": inserted or pointer_changed,
            "idempotent_replay": not inserted and not pointer_changed,
            "read_only": False,
            "writes_storage": True,
        }
    )
    return result
