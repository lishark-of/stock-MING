"""Fail-closed LTG-08 production replacement promotion evidence.

The read path validates fixed-disk evidence and an install-local HMAC journal.
It never creates keys, files, tasks, browser runs, or network calls.  The write
path accepts one literal user approval only after independently re-reading the
current Next Session packet, trusted Motion pair, sealed LTG-10 visual event,
and matching remote CI receipt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import secrets
import stat
import subprocess
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import (
    motion_evidence_service,
    release_promotion_service,
    streamlit_retirement_evidence_service,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
ROOT_NAME = "next_session_replacement_promotion"
EVENTS_NAME = "events"
TRUST_NAME = ".writer_trust"
KEY_NAME = "writer.key"
STATE_NAME = "writer.state"

EVENT_SCHEMA = "next_session_production_replacement_event.v1"
STATE_SCHEMA = "next_session_production_replacement_state.v1"
VALIDATION_SCHEMA = "next_session_production_replacement_validation.v1"
SCOPE = "ltg08_next_session_current_head_production_replacement"

_HEAD = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EVENT_FILE = re.compile(r"^[0-9]{8}\.json$")
_REQUIRED_VIEWPORTS = {"desktop", "laptop", "tablet", "mobile"}
_REQUIRED_FEATURE_COUNT = 9
_MIN_PRODUCTION_CLOSE_POINTS = 60

_EVENT_FIELDS = {
    "schema_version",
    "status",
    "sequence_no",
    "event_id",
    "semantic_digest",
    "scope",
    "head_full",
    "next_packet_digest",
    "motion_pair_digest",
    "streamlit_retirement_digest",
    "remote_ci_digest",
    "remote_run_id",
    "remote_artifact_digest",
    "approved_by_user",
    "recorded_at_utc",
    "previous_event_mac",
    "event_mac",
}
_STATE_FIELDS = {
    "schema_version",
    "sequence_no",
    "event_id",
    "event_mac",
    "updated_at_utc",
    "state_mac",
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


def _mac(secret: bytes, value: Any) -> str:
    return hmac.new(secret, _canonical_bytes(value), hashlib.sha256).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _valid_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.microsecond == 0


def _normalize_head(value: object) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if _HEAD.fullmatch(candidate) else ""


def _current_head(project_root: Path = PROJECT_ROOT) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return _normalize_head(result.stdout) if result.returncode == 0 else ""


def _paths(evidence_root: Path | str) -> tuple[Path, Path, Path, Path]:
    root = Path(evidence_root).expanduser().resolve() / ROOT_NAME
    trust = root / TRUST_NAME
    return root, root / EVENTS_NAME, trust / KEY_NAME, trust / STATE_NAME


def _owned_by_user(metadata: os.stat_result) -> bool:
    getuid = getattr(os, "getuid", None)
    return getuid is None or metadata.st_uid == getuid()


def _secure_regular(path: Path, *, mode: int, max_bytes: int = 4 * 1024 * 1024) -> bytes | None:
    try:
        before = path.lstat()
    except OSError:
        return None
    if not (
        stat.S_ISREG(before.st_mode)
        and not stat.S_ISLNK(before.st_mode)
        and stat.S_IMODE(before.st_mode) == mode
        and _owned_by_user(before)
        and before.st_nlink == 1
        and before.st_size <= max_bytes
    ):
        return None
    flags = os.O_RDONLY | int(getattr(os, "O_CLOEXEC", 0)) | int(getattr(os, "O_NOFOLLOW", 0))
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or opened.st_size != before.st_size
        ):
            return None
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        return data if len(data) <= max_bytes else None
    except OSError:
        return None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_json(path: Path, *, mode: int = 0o600) -> dict[str, Any]:
    data = _secure_regular(path, mode=mode)
    try:
        value = json.loads(data) if data is not None else None
    except (TypeError, ValueError):
        value = None
    return dict(value) if isinstance(value, Mapping) else {}


def _directory_valid(path: Path, *, mode: int = 0o700) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return bool(
        stat.S_ISDIR(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) == mode
        and _owned_by_user(metadata)
    )


def _evidence_anchor_valid(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return bool(
        stat.S_ISDIR(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) & 0o022 == 0
        and _owned_by_user(metadata)
    )


def _read_secret(evidence_root: Path | str) -> tuple[bytes | None, str]:
    root, events, key_path, _ = _paths(evidence_root)
    trust = key_path.parent
    if not root.exists() and not trust.exists() and not key_path.exists():
        return None, "next_session_replacement_trusted_writer_key_missing"
    if not (_directory_valid(root) and _directory_valid(events) and _directory_valid(trust)):
        return None, "next_session_replacement_trust_directory_invalid"
    try:
        root_names = {entry.name for entry in root.iterdir()}
        trust_names = {entry.name for entry in trust.iterdir()}
    except OSError:
        return None, "next_session_replacement_trust_directory_invalid"
    if root_names != {EVENTS_NAME, TRUST_NAME} or not trust_names.issubset({KEY_NAME, STATE_NAME}):
        return None, "next_session_replacement_trust_directory_invalid"
    secret = _secure_regular(key_path, mode=0o600, max_bytes=32)
    if secret is None:
        return None, "next_session_replacement_trusted_writer_key_invalid"
    if len(secret) != 32:
        return None, "next_session_replacement_trusted_writer_key_invalid"
    return secret, ""


def _create_secret(evidence_root: Path | str) -> tuple[bytes | None, str]:
    root, events, key_path, _ = _paths(evidence_root)
    trust = key_path.parent
    evidence_directory = root.parent

    def ensure_private_directory(path: Path) -> bool:
        try:
            path.mkdir(mode=0o700, exist_ok=False)
        except FileExistsError:
            pass
        except OSError:
            return False
        return _directory_valid(path)

    try:
        try:
            evidence_directory.mkdir(mode=0o700, exist_ok=False)
        except FileExistsError:
            pass
        if not _evidence_anchor_valid(evidence_directory):
            return None, "next_session_replacement_evidence_directory_invalid"
        if not ensure_private_directory(root):
            return None, "next_session_replacement_trust_directory_invalid"
        if not ensure_private_directory(events):
            return None, "next_session_replacement_trust_directory_invalid"
        if not ensure_private_directory(trust):
            return None, "next_session_replacement_trust_directory_invalid"
        if key_path.exists():
            return _read_secret(evidence_root)
        secret = secrets.token_bytes(32)
        descriptor = os.open(
            key_path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | int(getattr(os, "O_CLOEXEC", 0))
            | int(getattr(os, "O_NOFOLLOW", 0)),
            0o600,
        )
        try:
            offset = 0
            while offset < len(secret):
                offset += os.write(descriptor, secret[offset:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        return None, "next_session_replacement_trusted_writer_key_create_failed"
    verified, blocker = _read_secret(evidence_root)
    return (verified, blocker) if verified is not None else (None, blocker)


def _atomic_private_json(path: Path, value: Mapping[str, Any], *, replace: bool) -> str:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | int(getattr(os, "O_CLOEXEC", 0))
            | int(getattr(os, "O_NOFOLLOW", 0)),
            0o600,
        )
        data = _canonical_bytes(dict(value)) + b"\n"
        try:
            offset = 0
            while offset < len(data):
                offset += os.write(descriptor, data[offset:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
            descriptor = -1
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path, follow_symlinks=False)
            temporary.unlink()
        directory_descriptor = os.open(
            path.parent,
            os.O_RDONLY | int(getattr(os, "O_DIRECTORY", 0)),
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        return ""
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return "next_session_replacement_journal_write_failed"


def _read_next_packet() -> dict[str, Any]:
    from . import next_session_service

    packet = next_session_service.read_next_session_cache()
    return dict(packet) if isinstance(packet, Mapping) else {}


def _valid_production_close_points(rows: object) -> bool:
    if not isinstance(rows, list) or len(rows) < _MIN_PRODUCTION_CLOSE_POINTS:
        return False
    observed_dates: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) < {"x", "price"}:
            return False
        date_text = str(row.get("x") or "").strip()
        normalized = date_text.replace("-", "")
        if not re.fullmatch(r"[0-9]{8}", normalized):
            return False
        try:
            datetime.strptime(normalized, "%Y%m%d")
        except ValueError:
            return False
        price = row.get("price")
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            return False
        if not math.isfinite(float(price)) or float(price) <= 0:
            return False
        observed_dates.append(normalized)
    return len(set(observed_dates)) == len(observed_dates) and observed_dates == sorted(observed_dates)


def _next_packet_evidence(packet: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    chart = packet.get("chart_payload") if isinstance(packet.get("chart_payload"), Mapping) else {}
    summary = packet.get("chart_summary") if isinstance(packet.get("chart_summary"), Mapping) else {}
    maturity = chart.get("chart_maturity") if isinstance(chart.get("chart_maturity"), Mapping) else {}
    contract = chart.get("chart_contract") if isinstance(chart.get("chart_contract"), Mapping) else {}
    coverage = (
        packet.get("next_session_same_packet_signal_capability_coverage")
        if isinstance(packet.get("next_session_same_packet_signal_capability_coverage"), Mapping)
        else {}
    )
    historical = chart.get("historical_points") if isinstance(chart.get("historical_points"), list) else []
    anchor_count = int(maturity.get("scenario_anchor_count") or 0)
    anchored_count = int(maturity.get("scenario_anchored_count") or 0)
    exact_packet = bool(
        packet.get("schema_version") == "next_session_projection.v1"
        and packet.get("packet_key") == "command_center_next_session_projection_packet"
        and chart.get("status") == "ready"
        and chart.get("is_exact_next_session_packet") is True
        and summary.get("is_exact_next_session_packet") is True
    )
    real_close = bool(
        chart.get("uses_real_daily_close") is True
        and summary.get("uses_real_daily_close") is True
        and maturity.get("has_real_60d_close") is True
        and _valid_production_close_points(historical)
    )
    production_maturity = bool(
        maturity.get("status") in {"ready", "production_ready"}
        and anchor_count > 0
        and anchor_count == anchored_count
        and len(chart.get("reference_lines") or []) > 0
        and len(chart.get("operation_zones") or []) > 0
    )
    retained = bool(
        coverage.get("schema_version") == "next_session_same_packet_signal_capability_coverage.v1"
        and coverage.get("status") == "same_packet_signal_capability_coverage_ready"
        and coverage.get("same_packet") is True
        and coverage.get("lineage_bound") is True
        and coverage.get("direct_evidence_ready") is True
        and coverage.get("required_feature_group_count") == _REQUIRED_FEATURE_COUNT
        and coverage.get("retained_feature_group_count") == _REQUIRED_FEATURE_COUNT
        and coverage.get("missing_feature_groups") == []
    )
    safe = bool(
        contract.get("cache_only") is True
        and contract.get("external_calls_triggered") is False
        and contract.get("tushare_called") is False
        and contract.get("deepseek_called") is False
        and contract.get("github_called") is False
        and contract.get("does_not_execute_trades") is True
        and contract.get("frontend_computes_trade_action") is False
        and contract.get("does_not_modify_action") is True
        and contract.get("does_not_modify_operation_zones") is True
        and packet.get("contains_secret") is not True
    )
    material = {
        "schema_version": packet.get("schema_version"),
        "packet_key": packet.get("packet_key"),
        "status": packet.get("status"),
        "chart_payload": chart,
        "chart_summary": summary,
        "retained_coverage": coverage,
    }
    blockers: list[str] = []
    if not exact_packet:
        blockers.append("next_session_exact_packet_missing")
    if not real_close:
        blockers.append("next_session_real_close_60_sessions_missing")
    if not production_maturity:
        blockers.append("next_session_production_maturity_missing")
    if not retained:
        blockers.append("next_session_same_packet_9_of_9_coverage_missing")
    if not safe:
        blockers.append("next_session_read_only_safety_boundary_invalid")
    return {
        "ready": not blockers,
        "digest": _digest(material) if not blockers else "",
        "exact_packet": exact_packet,
        "real_close_60_sessions": real_close,
        "production_maturity": production_maturity,
        "same_packet_coverage_9_of_9": retained,
        "safe_boundary": safe,
        "historical_point_count": len(historical),
        "scenario_anchor_count": anchor_count,
        "scenario_anchored_count": anchored_count,
    }, blockers


def _motion_evidence(root: Path, head_full: str, project_root: Path) -> tuple[dict[str, Any], list[str]]:
    result = motion_evidence_service.validate_current_motion_evidence(
        root,
        expected_head_full=head_full,
        project_root=project_root,
    )
    next_rows = (
        result.get("validated_route_rows", {}).get("#next-session-chart", [])
        if isinstance(result.get("validated_route_rows"), Mapping)
        else []
    )
    modes = {row.get("reduced_motion") for row in next_rows if isinstance(row, Mapping)}
    viewports = {
        (bool(row.get("reduced_motion")), str(row.get("viewport") or ""))
        for row in next_rows
        if isinstance(row, Mapping)
    }
    route_ready = bool(
        len(next_rows) == 8
        and modes == {False, True}
        and all((mode, viewport) in viewports for mode in (False, True) for viewport in _REQUIRED_VIEWPORTS)
        and all(
            row.get("status") == "passed"
            and row.get("visual_qa_complete") is True
            and row.get("performance_trace_complete") is True
            and row.get("long_task_over_50ms_count") == 0
            and row.get("clipped_count") == 0
            for row in next_rows
            if isinstance(row, Mapping)
        )
    )
    material = {
        key: result.get(key)
        for key in (
            "schema_version",
            "status",
            "expected_head_full",
            "frontend_source_digest",
            "build_identity_digest",
            "dist_manifest_digest",
            "package_identity_digest",
            "normal_run_id",
            "reduced_run_id",
        )
    }
    material["next_route_rows_digest"] = _digest(next_rows) if next_rows else ""
    blockers = list(result.get("blockers") or [])
    if result.get("motion_current_head_pair_verified") is not True or not route_ready:
        blockers.append("next_session_current_head_motion_pair_missing_or_incomplete")
    return {
        "ready": not blockers,
        "digest": _digest(material) if not blockers else "",
        "normal_run_id": result.get("normal_run_id") or "",
        "reduced_run_id": result.get("reduced_run_id") or "",
        "next_route_row_count": len(next_rows),
    }, sorted(set(str(item) for item in blockers if item))


def _streamlit_evidence(root: Path, head_full: str, project_root: Path) -> tuple[dict[str, Any], list[str]]:
    result = streamlit_retirement_evidence_service.validate_streamlit_primary_retirement(
        root,
        expected_head_full=head_full,
        project_root=project_root,
    )
    ready = bool(
        result.get("streamlit_primary_retired") is True
        and result.get("head_full") == head_full
        and result.get("fallback_disposition") == "admin_debug_only_retained"
        and result.get("route_count") == 6
        and result.get("visual_review_required") is True
        and bool(result.get("visual_review_id"))
    )
    material = {
        key: result.get(key)
        for key in (
            "schema_version",
            "status",
            "head_full",
            "fallback_disposition",
            "route_count",
            "viewport_count",
            "qa_matrix_count",
            "artifact_set_sha256",
            "source_contract_digest",
            "route_matrix_digest",
            "visual_review_id",
        )
    }
    blockers = list(result.get("blockers") or [])
    if not ready:
        blockers.append("ltg10_sealed_visual_retirement_not_current")
    return {
        "ready": not blockers,
        "digest": _digest(material) if not blockers else "",
        "visual_review_event_id": result.get("visual_review_id") or "",
        "fallback_disposition": result.get("fallback_disposition") or "",
    }, sorted(set(str(item) for item in blockers if item))


def _remote_ci_evidence(root: Path, head_full: str) -> tuple[dict[str, Any], list[str]]:
    result = release_promotion_service.validate_release_prerequisites(
        root,
        expected_head_full=head_full,
    )
    rows = result.get("rows") if isinstance(result.get("rows"), list) else []
    remote = next(
        (row for row in rows if isinstance(row, Mapping) and row.get("evidence_key") == "remote_ci"),
        {},
    )
    ready = bool(
        remote.get("ready") is True
        and _SHA256.fullmatch(str(remote.get("semantic_digest") or ""))
        and str(result.get("remote_run_id") or "").isdigit()
        and str(result.get("remote_artifact_digest") or "").startswith("sha256:")
    )
    blockers = list(remote.get("blockers") or [])
    if not ready:
        blockers.append("matching_remote_ci_current_head_missing")
    return {
        "ready": ready,
        "digest": str(remote.get("semantic_digest") or "") if ready else "",
        "run_id": str(result.get("remote_run_id") or "") if ready else "",
        "artifact_digest": str(result.get("remote_artifact_digest") or "") if ready else "",
    }, sorted(set(str(item) for item in blockers if item))


def _collect_prerequisites(
    evidence_root: Path,
    *,
    expected_head_full: str,
    project_root: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    actual = _current_head(project_root)
    if not expected_head_full or actual != expected_head_full:
        blockers.append("next_session_replacement_expected_head_not_current")
    packet_fact, packet_blockers = _next_packet_evidence(_read_next_packet())
    motion_fact, motion_blockers = _motion_evidence(evidence_root, expected_head_full, project_root)
    streamlit_fact, streamlit_blockers = _streamlit_evidence(evidence_root, expected_head_full, project_root)
    remote_fact, remote_blockers = _remote_ci_evidence(evidence_root, expected_head_full)
    blockers.extend(packet_blockers + motion_blockers + streamlit_blockers + remote_blockers)
    material = {
        "scope": SCOPE,
        "head_full": expected_head_full,
        "next_packet_digest": packet_fact.get("digest") or "",
        "motion_pair_digest": motion_fact.get("digest") or "",
        "streamlit_retirement_digest": streamlit_fact.get("digest") or "",
        "remote_ci_digest": remote_fact.get("digest") or "",
        "remote_run_id": remote_fact.get("run_id") or "",
        "remote_artifact_digest": remote_fact.get("artifact_digest") or "",
    }
    blockers = sorted(set(blockers))
    return {
        "ready": not blockers,
        "head_full": expected_head_full,
        "material": material,
        "semantic_digest": _digest(material) if not blockers else "",
        "next_packet": packet_fact,
        "motion_pair": motion_fact,
        "streamlit_retirement": streamlit_fact,
        "remote_ci": remote_fact,
        "blockers": blockers,
    }


def _event_without_mac(event: Mapping[str, Any]) -> dict[str, Any]:
    return {key: event.get(key) for key in sorted(_EVENT_FIELDS - {"event_mac"})}


def _load_chain(evidence_root: Path | str, secret: bytes) -> tuple[list[dict[str, Any]], str]:
    _, events_root, _, state_path = _paths(evidence_root)
    if not _directory_valid(events_root):
        return [], "next_session_replacement_events_directory_invalid"
    try:
        paths = sorted(events_root.iterdir())
    except OSError:
        return [], "next_session_replacement_events_directory_invalid"
    if any(not _EVENT_FILE.fullmatch(path.name) for path in paths):
        return [], "next_session_replacement_event_set_invalid"
    events: list[dict[str, Any]] = []
    previous_mac = ""
    previous_timestamp = ""
    for sequence, path in enumerate(paths, start=1):
        if path.name != f"{sequence:08d}.json":
            return [], "next_session_replacement_event_sequence_invalid"
        event = _read_json(path)
        if set(event) != _EVENT_FIELDS:
            return [], "next_session_replacement_event_schema_invalid"
        unsigned = _event_without_mac(event)
        expected_id = _digest({key: value for key, value in unsigned.items() if key != "event_id"})
        if not (
            event.get("schema_version") == EVENT_SCHEMA
            and event.get("status") == "next_session_production_replacement_promoted"
            and event.get("sequence_no") == sequence
            and event.get("scope") == SCOPE
            and _normalize_head(event.get("head_full")) == event.get("head_full")
            and all(
                _SHA256.fullmatch(str(event.get(field) or ""))
                for field in (
                    "event_id",
                    "semantic_digest",
                    "next_packet_digest",
                    "motion_pair_digest",
                    "streamlit_retirement_digest",
                    "remote_ci_digest",
                    "event_mac",
                )
            )
            and str(event.get("remote_run_id") or "").isdigit()
            and str(event.get("remote_artifact_digest") or "").startswith("sha256:")
            and event.get("approved_by_user") is True
            and _valid_timestamp(event.get("recorded_at_utc"))
            and (not previous_timestamp or str(event["recorded_at_utc"]) >= previous_timestamp)
            and event.get("previous_event_mac") == previous_mac
            and event.get("event_id") == expected_id
            and hmac.compare_digest(str(event.get("event_mac") or ""), _mac(secret, unsigned))
        ):
            return [], "next_session_replacement_event_authentication_failed"
        events.append(event)
        previous_mac = str(event["event_mac"])
        previous_timestamp = str(event["recorded_at_utc"])
    if not events:
        return [], "next_session_replacement_event_missing"
    state = _read_json(state_path)
    if set(state) != _STATE_FIELDS:
        return [], "next_session_replacement_state_invalid"
    unsigned_state = {key: state.get(key) for key in sorted(_STATE_FIELDS - {"state_mac"})}
    latest = events[-1]
    if not (
        state.get("schema_version") == STATE_SCHEMA
        and state.get("sequence_no") == latest.get("sequence_no")
        and state.get("event_id") == latest.get("event_id")
        and state.get("event_mac") == latest.get("event_mac")
        and state.get("updated_at_utc") == latest.get("recorded_at_utc")
        and _SHA256.fullmatch(str(state.get("state_mac") or ""))
        and hmac.compare_digest(str(state.get("state_mac") or ""), _mac(secret, unsigned_state))
    ):
        return [], "next_session_replacement_state_authentication_failed"
    return events, ""


def _public_summary(
    *,
    prerequisites: Mapping[str, Any],
    event: Mapping[str, Any] | None,
    blockers: list[str],
) -> dict[str, Any]:
    ready = event is not None and not blockers
    return {
        "schema_version": VALIDATION_SCHEMA,
        "status": (
            "next_session_production_replacement_promoted_current_head"
            if ready
            else "next_session_production_replacement_blocked"
        ),
        "scope": SCOPE,
        "head_full": prerequisites.get("head_full") or "",
        "production_replacement_complete": ready,
        "next_session_production_replacement": ready,
        "event_id": event.get("event_id") if ready and event else "",
        "sequence_no": event.get("sequence_no") if ready and event else 0,
        "next_packet_digest": event.get("next_packet_digest") if ready and event else "",
        "motion_pair_digest": event.get("motion_pair_digest") if ready and event else "",
        "streamlit_retirement_digest": event.get("streamlit_retirement_digest") if ready and event else "",
        "remote_ci_digest": event.get("remote_ci_digest") if ready and event else "",
        "remote_run_id": event.get("remote_run_id") if ready and event else "",
        "remote_artifact_digest": event.get("remote_artifact_digest") if ready and event else "",
        "next_packet_evidence": prerequisites.get("next_packet") or {},
        "motion_pair_evidence": prerequisites.get("motion_pair") or {},
        "streamlit_retirement_evidence": prerequisites.get("streamlit_retirement") or {},
        "remote_ci_evidence": prerequisites.get("remote_ci") or {},
        "blockers": sorted(set(blockers)),
        "read_only": True,
        "writes_storage": False,
        "creates_task": False,
        "opens_streamlit": False,
        "opens_browser": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "contains_secret": False,
    }


def validate_next_session_production_replacement(
    evidence_root: Path | str = EVIDENCE_ROOT,
    *,
    expected_head_full: str | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Read-only validation; never creates or repairs trust material."""

    root = Path(evidence_root).expanduser().resolve()
    head_full = _normalize_head(expected_head_full) if expected_head_full is not None else _current_head(project_root)
    prerequisites = _collect_prerequisites(
        root,
        expected_head_full=head_full,
        project_root=project_root,
    )
    blockers = list(prerequisites.get("blockers") or [])
    secret, trust_blocker = _read_secret(root)
    event: Mapping[str, Any] | None = None
    if secret is None:
        blockers.append(trust_blocker or "next_session_replacement_trusted_writer_key_missing")
    else:
        events, chain_blocker = _load_chain(root, secret)
        if chain_blocker:
            blockers.append(chain_blocker)
        elif events:
            latest = events[-1]
            material = prerequisites.get("material") if isinstance(prerequisites.get("material"), Mapping) else {}
            if not (
                prerequisites.get("ready") is True
                and latest.get("semantic_digest") == prerequisites.get("semantic_digest")
                and all(latest.get(key) == material.get(key) for key in material)
            ):
                blockers.append("next_session_replacement_event_evidence_binding_mismatch")
            else:
                event = latest
    return _public_summary(prerequisites=prerequisites, event=event, blockers=blockers)


def promote_next_session_production_replacement(
    payload: Any = None,
    *,
    evidence_root: Path | str = EVIDENCE_ROOT,
    expected_head_full: str | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Append one current-evidence event after literal user approval."""

    request = dict(payload) if isinstance(payload, Mapping) else {}
    approved = set(request) == {"approved_by_user"} and request.get("approved_by_user") is True
    root = Path(evidence_root).expanduser().resolve()
    head_full = _normalize_head(expected_head_full) if expected_head_full is not None else _current_head(project_root)
    prerequisites = _collect_prerequisites(
        root,
        expected_head_full=head_full,
        project_root=project_root,
    )
    blockers = list(prerequisites.get("blockers") or [])
    if not approved:
        blockers.insert(0, "explicit_user_next_session_replacement_approval_required")
    if blockers:
        result = _public_summary(prerequisites=prerequisites, event=None, blockers=blockers)
        result.update({"promotion_written": False, "idempotent_replay": False})
        return result
    secret, blocker = _read_secret(root)
    if secret is None and blocker == "next_session_replacement_trusted_writer_key_missing":
        secret, blocker = _create_secret(root)
    if secret is None:
        result = _public_summary(prerequisites=prerequisites, event=None, blockers=[blocker])
        result.update({"promotion_written": False, "idempotent_replay": False})
        return result
    events, chain_blocker = _load_chain(root, secret)
    if chain_blocker == "next_session_replacement_event_missing":
        events, chain_blocker = [], ""
    if chain_blocker:
        result = _public_summary(prerequisites=prerequisites, event=None, blockers=[chain_blocker])
        result.update({"promotion_written": False, "idempotent_replay": False})
        return result
    material = dict(prerequisites["material"])
    semantic_digest = str(prerequisites["semantic_digest"])
    latest = events[-1] if events else None
    if latest is not None and latest.get("semantic_digest") == semantic_digest:
        result = validate_next_session_production_replacement(
            root,
            expected_head_full=head_full,
            project_root=project_root,
        )
        result.update({"promotion_written": False, "idempotent_replay": True, "read_only": False, "writes_storage": False})
        return result
    sequence = len(events) + 1
    recorded_at = _now_iso()
    if latest is not None and recorded_at < str(latest.get("recorded_at_utc") or ""):
        result = _public_summary(
            prerequisites=prerequisites,
            event=None,
            blockers=["next_session_replacement_writer_clock_moved_backwards"],
        )
        result.update({"promotion_written": False, "idempotent_replay": False})
        return result
    event: dict[str, Any] = {
        "schema_version": EVENT_SCHEMA,
        "status": "next_session_production_replacement_promoted",
        "sequence_no": sequence,
        "event_id": "",
        "semantic_digest": semantic_digest,
        "scope": SCOPE,
        **material,
        "approved_by_user": True,
        "recorded_at_utc": recorded_at,
        "previous_event_mac": str(latest.get("event_mac") or "") if latest else "",
        "event_mac": "",
    }
    event["event_id"] = _digest({key: value for key, value in _event_without_mac(event).items() if key != "event_id"})
    event["event_mac"] = _mac(secret, _event_without_mac(event))
    _, events_root, _, state_path = _paths(root)
    blocker = _atomic_private_json(events_root / f"{sequence:08d}.json", event, replace=False)
    if blocker:
        result = _public_summary(prerequisites=prerequisites, event=None, blockers=[blocker])
        result.update({"promotion_written": False, "idempotent_replay": False})
        return result
    unsigned_state = {
        "schema_version": STATE_SCHEMA,
        "sequence_no": sequence,
        "event_id": event["event_id"],
        "event_mac": event["event_mac"],
        "updated_at_utc": recorded_at,
    }
    state = {**unsigned_state, "state_mac": _mac(secret, unsigned_state)}
    blocker = _atomic_private_json(state_path, state, replace=True)
    if blocker:
        result = _public_summary(prerequisites=prerequisites, event=None, blockers=[blocker])
        result.update({"promotion_written": True, "idempotent_replay": False})
        return result
    result = validate_next_session_production_replacement(
        root,
        expected_head_full=head_full,
        project_root=project_root,
    )
    result.update({"promotion_written": True, "idempotent_replay": False, "read_only": False, "writes_storage": True})
    return result


__all__ = [
    "promote_next_session_production_replacement",
    "validate_next_session_production_replacement",
]
