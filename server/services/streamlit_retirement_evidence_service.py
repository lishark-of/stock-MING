"""Trusted, read-only validation for LTG-10 packaged ordinary-flow evidence.

The explicit recorder never accepts a caller-provided report.  It first proves
that the fixed packaged-runner implementation is available, then creates a
private one-shot challenge and passes its nonce to the child over an inherited
pipe.  Only a nonce-bound response from that exact child process, including an
attestation returned by the launched packaged application, may be sealed.
GET paths only validate the sealed chain; public JSON, task payloads, SQLite
rows, screenshots, and caller booleans cannot promote Streamlit retirement.
"""

from __future__ import annotations

import ast
import html
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import shutil
import stat
import subprocess
import tempfile
import unicodedata
import zlib
from collections.abc import Mapping
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import tauri_package_verifier
from .tauri_package_verifier import validate_tauri_production_package


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
RUNNER_PATH = PROJECT_ROOT / "scripts" / "streamlit_retirement_packaged_qa_runner.mjs"
PACKAGED_APP_EXECUTABLE_RELATIVE = Path(
    "desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app/Contents/MacOS/stock_ming_command_center"
)
TRUSTED_SOURCE_RELATIVES = (
    Path("app.py"),
    Path("desktop/src/main.tsx"),
    Path("desktop/src/styles.css"),
    Path("desktop/src/App.tsx"),
    Path("desktop/src/components/ProductSurface.css"),
    Path("desktop/src/components/Layout.tsx"),
    Path("desktop/src/api/client.ts"),
    Path("desktop/src/components/BackendOfflineNotice.tsx"),
    Path("desktop/src/components/ChartSafetyStrip.tsx"),
    Path("desktop/src/components/DataLineageTable.tsx"),
    Path("desktop/src/components/DeepSeekModelStrategyLedger.tsx"),
    Path("desktop/src/components/EChartPanel.tsx"),
    Path("desktop/src/components/JsonDetails.tsx"),
    Path("desktop/src/components/MetricGrid.tsx"),
    Path("desktop/src/components/NextSessionChart.tsx"),
    Path("desktop/src/components/PacketCard.tsx"),
    Path("desktop/src/components/PageStateBanner.tsx"),
    Path("desktop/src/components/RouteCacheLoadingBoundary.tsx"),
    Path("desktop/src/components/StateClarityRail.tsx"),
    Path("desktop/src/components/StatusBadge.tsx"),
    Path("desktop/src/components/TaskBoundarySummary.tsx"),
    Path("desktop/src/components/TaskLaunchReceipt.tsx"),
    Path("desktop/src/components/TaskStatusPanel.tsx"),
    Path("desktop/src/routes/CommandCenterHome.tsx"),
    Path("desktop/src/routes/CommandCenterHome.css"),
    Path("desktop/src/routes/CandidateRadar.tsx"),
    Path("desktop/src/routes/CandidateRadar.css"),
    Path("desktop/src/routes/FactorQuantHub.tsx"),
    Path("desktop/src/routes/NextSessionMap.tsx"),
    Path("desktop/src/routes/MarginEtf.tsx"),
    Path("desktop/src/routes/QmtReplayLab.tsx"),
    Path("desktop/src/routes/LegacyTools.tsx"),
    Path("desktop/src-tauri/Cargo.lock"),
    Path("desktop/src-tauri/Cargo.toml"),
    Path("desktop/src-tauri/src/main.rs"),
    Path("desktop/src-tauri/src/ltg10_packaged_qa.rs"),
    Path("desktop/src-tauri/src/ltg10_packaged_qa_init.js"),
    Path("scripts/record_streamlit_retirement_packaged_attestation.py"),
    Path("scripts/record_streamlit_retirement_visual_review.py"),
    Path("scripts/streamlit_retirement_packaged_qa_runner.mjs"),
    Path("server/services/legacy_service.py"),
    Path("server/services/tauri_package_verifier.py"),
    Path("server/services/streamlit_retirement_evidence_service.py"),
    Path("server/services/v1_closeout_service.py"),
)
EVENT_ROOT_RELATIVE = Path("streamlit_retirement/events_v3")
VISUAL_REVIEW_ROOT_RELATIVE = Path("streamlit_retirement/visual_review")
VISUAL_REVIEW_PENDING_RELATIVE = VISUAL_REVIEW_ROOT_RELATIVE / "pending"
VISUAL_REVIEW_EVENT_ROOT_RELATIVE = VISUAL_REVIEW_ROOT_RELATIVE / "events"
VISUAL_REVIEW_STATE_RELATIVE = VISUAL_REVIEW_ROOT_RELATIVE / "event.state"
TRUST_ROOT_RELATIVE = Path("streamlit_retirement/.packaged_runner_trust")
SESSION_ROOT_RELATIVE = Path("streamlit_retirement/.packaged_runner_sessions")
TRUST_KEY_NAME = "writer.key"
TRUST_STATE_NAME = "writer.v3.state"
LEGACY_TRUST_STATE_NAMES = {"writer.state"}
TRUST_KEY_BYTES = 32
EVENT_SCHEMA = "streamlit_retirement_packaged_attestation_event.v4"
STATE_SCHEMA = "streamlit_retirement_packaged_attestation_state.v2"
VISUAL_REVIEW_MANIFEST_SCHEMA = "streamlit_retirement_visual_review_manifest.v2"
VISUAL_REVIEW_EVENT_SCHEMA = "streamlit_retirement_visual_review_event.v2"
VISUAL_REVIEW_STATE_SCHEMA = "streamlit_retirement_visual_review_state.v1"
CHALLENGE_SCHEMA = "streamlit_retirement_packaged_runner_challenge.v6"
ATTESTATION_SCHEMA = "streamlit_retirement_packaged_runner_attestation.v7"
APP_ATTESTATION_SCHEMA = "streamlit_retirement_packaged_app_attestation.v7"
RUNNER_SCHEMA = "streamlit_retirement_packaged_runner.v4"
SOURCE_SCHEMA = "streamlit_retirement_source_ast_contract.v5"
FINAL_NETWORK_GUARD = "quiesce_tracked_intervals_then_deny_all_then_exit"
MAX_TRUSTED_NATIVE_PAYLOAD_BYTES = 192 * 1024 * 1024
TRUSTED_RUNNER_FAILURE_PREFIX = "packaged Tauri native adapter failed closed:"
TRUSTED_RUNNER_SAFE_FAILURE_CODES = frozenset(
    {
        "qa_descriptor_invalid",
        "input_frame_invalid",
        "input_contract_invalid",
        "challenge_contract_invalid",
        "runner_parent_identity_invalid",
        "package_identity_invalid",
        "document_instrumentation_unavailable",
        "viewport_measurement_invalid",
        "route_navigation_invalid",
        "observation_invalid",
        "snapshot_invalid",
        "network_seal_invalid",
        "native_output_invalid",
        "unknown",
    }
)
EXPECTED_IMPORT_MANIFEST_DIGEST = "2136c935ff75b56ca26fc8ad48285afdcb3846d7cf8659f6e3feb9c6bb8e0df8"
EXPECTED_ROUTES = (
    ("#home", "CommandCenterHome"),
    ("#candidates", "CandidateRadar"),
    ("#factor", "FactorQuantHub"),
    ("#next", "NextSessionMap"),
    ("#marginEtf", "MarginEtf"),
    ("#qmt-replay", "QmtReplayLab"),
)
EXPECTED_ROUTE_HEADINGS = {
    "#home": "今日作战台",
    "#candidates": "下一票雷达",
    "#factor": "股票量化推演",
    "#next": "次日图谱",
    "#marginEtf": "ETF / 融资",
    "#qmt-replay": "QMT 本地回放",
}
EXPECTED_VIEWPORTS = {"desktop": (1440, 820), "mobile": (390, 844)}
FORBIDDEN_ORDINARY_COMPONENT_IDS = (
    "LegacyTools",
    "AdminTools",
    "SystemMigration",
    "legacy",
    "admin",
    "system",
)
COMPONENT_COUNT_SELECTOR = "[data-ltg10-component-id]"
COMPONENT_ATTRIBUTE_SELECTOR = "[data-ltg10-component-id]@data-ltg10-component-id"
ROOT_COMPONENT_COUNT_SELECTOR = "#root [data-ltg10-component-id]"
BODY_NON_ROOT_SURFACE_SELECTOR = "body > :not(#root):not(script):not(style):not(link):not(meta):not(template)"
BODY_HTML_SELECTOR = "body"
FORBIDDEN_BODY_TOKENS = ("LegacyTools", "AdminTools", "SystemMigration")
FORBIDDEN_COMPONENT_SELECTOR = (
    "[data-ltg10-component-id='LegacyTools'],"
    "[data-ltg10-component-id='AdminTools'],"
    "[data-ltg10-component-id='SystemMigration'],"
    "[data-ltg10-component-id='legacy'],"
    "[data-ltg10-component-id='admin'],"
    "[data-ltg10-component-id='system']"
)
CHALLENGE_FIELDS = {
    "schema_version",
    "challenge_id",
    "nonce_digest",
    "created_at_utc",
    "head_full",
    "runner_source_sha256",
    "source_contract_digest",
    "ordinary_component_map_digest",
    "package_head_full",
    "artifact_set_sha256",
    "app_bundle_sha256",
    "app_executable_sha256",
    "dmg_sha256",
    "app_executable_path",
    "app_bundle_path",
    "dmg_path",
    "bundle_identifier",
    "bundle_version",
    "expected_routes",
    "expected_viewports",
    "production_required",
    "browser_or_vite_substitute_allowed",
    "external_calls_allowed",
    "challenge_digest",
}
ATTESTATION_FIELDS = {
    "schema_version",
    "status",
    "attestation_mode",
    "runner_identity",
    "runner_pid",
    "runner_executable_path",
    "runner_source_sha256",
    "generated_at",
    "challenge_id",
    "challenge_digest",
    "nonce_digest",
    "runner_response_sha256",
    "source_contract_digest",
    "ordinary_component_map_digest",
    "head_full",
    "runtime_surface",
    "protocol",
    "package_head_full",
    "artifact_set_sha256",
    "app_bundle_sha256",
    "app_executable_sha256",
    "dmg_sha256",
    "app_attestation",
    "app_exit_confirmed",
    "app_exit_code",
    "app_exit_signal",
    "route_count",
    "viewport_count",
    "qa_matrix_count",
    "passed_count",
    "review_required_count",
    "network_ledger_complete",
    "network_seal_audit",
    "rows",
    "external_calls_triggered",
    "tushare_called",
    "deepseek_called",
    "github_called",
    "does_not_execute_trades",
    "does_not_modify_strategy_action",
    "contains_secret",
    "payload_size_bytes",
}
ROW_FIELDS = {
    "route",
    "component",
    "viewport",
    "width",
    "height",
    "observed_inner_width",
    "observed_inner_height",
    "device_pixel_ratio",
    "native_inner_width_px",
    "native_inner_height_px",
    "screenshot_pixel_width",
    "screenshot_pixel_height",
    "observed_url",
    "runtime_surface",
    "protocol",
    "observation_started_monotonic_ns",
    "observation_finished_monotonic_ns",
    "dom_ledger",
    "task_post_count_before",
    "task_post_count_after",
    "navigation_post_count",
    "network_ledger",
    "pending_request_count",
    "quiet_window_ms",
    "quiet_elapsed_ms",
    "instrumentation_integrity",
    "attach_shadow_calls",
    "custom_element_events",
    "dynamic_frame_events",
    "post_seal_capture",
    "deny_all_network_guard_at_observation",
    "late_event_count_at_observation",
    "denied_attempt_count_at_observation",
    "denied_interval_registration_count_at_observation",
    "network_ledger_complete",
    "screenshot_path",
    "screenshot_byte_length",
    "screenshot_sha256",
    "screenshot_native_snapshot",
    "row_hmac_sha256",
}
DOM_FIELDS = {"sequence", "kind", "selector", "value"}
NETWORK_FIELDS = {
    "sequence",
    "request_id",
    "observed_monotonic_ns",
    "phase",
    "method",
    "url",
    "resource_type",
    "status",
    "task_request",
    "pending_count_after",
}
NETWORK_SEAL_FIELDS = {
    "sealed",
    "pending_request_count",
    "quiet_window_ms",
    "quiet_elapsed_ms",
    "instrumentation_integrity",
    "late_event_count",
    "late_events",
    "deny_all_network_guard",
    "denied_attempt_count",
    "denied_attempts",
    "final_window_ms",
    "final_window_elapsed_ms",
    "ledger_count",
    "ledger_digest_material",
    "guard_mode",
    "interval_registration_count",
    "interval_clear_count",
    "tracked_interval_count",
    "quiesced_interval_count",
    "active_interval_count_after_quiesce",
    "interval_registry_integrity",
    "quiesce_started_at_monotonic_ns",
    "quiesce_completed_at_monotonic_ns",
    "quiesce_complete",
    "denied_interval_registration_count",
}
APP_ATTESTATION_FIELDS = {
    "schema_version",
    "status",
    "pid",
    "parent_pid",
    "parent_executable_path",
    "executable_path",
    "executable_sha256",
    "bundle_sha256",
    "artifact_set_sha256",
    "dmg_sha256",
    "head_full",
    "challenge_digest",
    "nonce_digest",
    "response_sha256",
    "source_contract_digest",
    "ordinary_component_map_digest",
    "route_payload_sha256",
    "network_seal_sha256",
    "native_snapshot_api",
    "final_network_guard",
    "final_window_ms",
    "exit_after_output",
    "expected_exit_code",
    "exit_contract_sha256",
    "output_frame_magic",
    "output_frame_version",
    "output_frame_codec",
    "output_frame_flags",
    "output_frame_reserved",
    "output_frame_compressed_bytes",
    "output_frame_uncompressed_bytes",
    "output_frame_raw_json_sha256",
    "output_frame_transport_response_sha256",
}
APP_TRANSPORT_ATTESTATION_FIELDS = {
    "output_frame_magic",
    "output_frame_version",
    "output_frame_codec",
    "output_frame_flags",
    "output_frame_reserved",
    "output_frame_compressed_bytes",
    "output_frame_uncompressed_bytes",
    "output_frame_raw_json_sha256",
}
EVENT_FIELDS = {
    "schema_version",
    "status",
    "sequence_no",
    "previous_event_mac",
    "event_id",
    "event_mac",
    "head_full",
    "recorded_at_utc",
    "runner_source_sha256",
    "source_contract_digest",
    "fallback_disposition",
    "artifact_set_sha256",
    "app_bundle_sha256",
    "app_executable_sha256",
    "dmg_sha256",
    "route_matrix_digest",
    "screenshot_set_digest",
    "network_ledger_digest",
    "route_count",
    "viewport_count",
    "qa_matrix_count",
    "visual_review_required",
    "visual_review_event_id",
    "canvas_present_count",
    "screenshot_manifest_digest",
    "external_calls_triggered",
    "does_not_execute_trades",
    "contains_secret",
}
VISUAL_REVIEW_MANIFEST_FIELDS = {
    "schema_version",
    "status",
    "review_id",
    "created_at_utc",
    "head_full",
    "runner_source_sha256",
    "source_contract_digest",
    "artifact_set_sha256",
    "app_bundle_sha256",
    "app_executable_sha256",
    "dmg_sha256",
    "app_attestation_digest",
    "route_matrix_digest",
    "screenshot_set_digest",
    "network_ledger_digest",
    "route_count",
    "viewport_count",
    "qa_matrix_count",
    "canvas_present_count",
    "screenshot_rows",
    "manifest_digest",
    "manifest_mac",
}
VISUAL_REVIEW_EVENT_FIELDS = {
    "schema_version",
    "status",
    "sequence_no",
    "previous_event_mac",
    "event_id",
    "event_mac",
    "head_full",
    "approved_at_utc",
    "review_id",
    "manifest_digest",
    "artifact_set_sha256",
    "app_bundle_sha256",
    "app_executable_sha256",
    "dmg_sha256",
    "app_attestation_digest",
    "route_matrix_digest",
    "screenshot_set_digest",
    "screenshot_count",
    "reviewed_screenshots",
    "canvas_present_count",
    "approved_by_user",
    "no_legacy_surface",
    "no_streamlit_surface",
    "no_admin_surface",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _nonce_bound_response_valid(value: Mapping[str, Any], nonce: bytes, *, response_field: str) -> bool:
    material = dict(value)
    observed = str(material.pop(response_field, ""))
    expected = hashlib.sha256(nonce + _canonical_bytes(material)).hexdigest()
    return _valid_sha256(observed) and hmac.compare_digest(observed, expected)


def _valid_sha256(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and text == text.lower() and all(char in "0123456789abcdef" for char in text)


def _normalize_head(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if len(text) == 40 and all(char in "0123456789abcdef" for char in text) else ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _valid_utc(value: object) -> bool:
    text = str(value or "")
    if not text.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def _git_head_full(project_root: Path = PROJECT_ROOT) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return _normalize_head(result.stdout) if result.returncode == 0 else ""


def _trusted_sources_match_commit(project_root: Path, head_full: str) -> bool:
    expected = _normalize_head(head_full)
    if not expected or _git_head_full(project_root) != expected:
        return False
    for relative in TRUSTED_SOURCE_RELATIVES:
        current, blocker = _secure_read_file(
            project_root / relative,
            max_bytes=4 * 1024 * 1024,
            require_single_link=False,
        )
        if current is None or blocker:
            return False
        try:
            committed = subprocess.run(
                ["git", "show", f"{expected}:{relative.as_posix()}"],
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if committed.returncode != 0 or committed.stdout != current:
            return False
    return True


def _owned_by_current_user(metadata: os.stat_result) -> bool:
    getuid = getattr(os, "getuid", None)
    return getuid is None or metadata.st_uid == getuid()


def _directory_chain_secure(root: Path, directory: Path, *, leaf_mode: int | None = None) -> bool:
    """Reject symlinks and non-owned directories below one resolved evidence root."""

    resolved_root = root.resolve()
    try:
        relative = directory.relative_to(resolved_root)
    except ValueError:
        return False
    current = resolved_root
    parts = relative.parts
    for index, part in enumerate(parts):
        current = current / part
        try:
            metadata = current.lstat()
        except OSError:
            return False
        if not (
            stat.S_ISDIR(metadata.st_mode)
            and not stat.S_ISLNK(metadata.st_mode)
            and _owned_by_current_user(metadata)
        ):
            return False
        if leaf_mode is not None and index == len(parts) - 1:
            if stat.S_IMODE(metadata.st_mode) != leaf_mode:
                return False
    return True


def _ensure_private_directory_below(
    root: Path,
    relative: Path,
    *,
    leaf_mode: int = 0o700,
) -> tuple[Path | None, str]:
    """Create a private directory chain one component at a time, never through symlinks."""

    resolved_root = root.resolve()
    try:
        root_metadata = resolved_root.lstat()
    except OSError:
        return None, "private_directory_root_missing_or_insecure"
    if not (
        stat.S_ISDIR(root_metadata.st_mode)
        and not stat.S_ISLNK(root_metadata.st_mode)
        and _owned_by_current_user(root_metadata)
    ):
        return None, "private_directory_root_missing_or_insecure"
    current = resolved_root
    for index, part in enumerate(relative.parts):
        if part in {"", ".", ".."}:
            return None, "private_directory_relative_path_invalid"
        current = current / part
        is_leaf = index == len(relative.parts) - 1
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            try:
                os.mkdir(current, leaf_mode if is_leaf else 0o700)
                metadata = current.lstat()
            except OSError:
                return None, "private_directory_create_failed"
        except OSError:
            return None, "private_directory_insecure"
        mode = stat.S_IMODE(metadata.st_mode)
        if not (
            stat.S_ISDIR(metadata.st_mode)
            and not stat.S_ISLNK(metadata.st_mode)
            and _owned_by_current_user(metadata)
            and (mode == leaf_mode if is_leaf else mode & 0o022 == 0)
        ):
            return None, "private_directory_insecure"
    return current, ""


def _secure_read_file(
    path: Path,
    *,
    require_mode: int | None = None,
    max_bytes: int = 64 * 1024 * 1024,
    require_single_link: bool = True,
) -> tuple[bytes | None, str]:
    """Read one regular file through one no-follow descriptor.

    lstat/fstat identity binding and a single descriptor make path replacement
    unable to substitute bytes between validation and hashing.
    """

    try:
        before = path.lstat()
    except FileNotFoundError:
        return None, "file_missing"
    except OSError:
        return None, "file_unreadable"
    if not (
        stat.S_ISREG(before.st_mode)
        and not stat.S_ISLNK(before.st_mode)
        and _owned_by_current_user(before)
        and (not require_single_link or before.st_nlink == 1)
        and 0 <= before.st_size <= max_bytes
        and (require_mode is None or stat.S_IMODE(before.st_mode) == require_mode)
    ):
        return None, "file_metadata_invalid"
    flags = os.O_RDONLY | int(getattr(os, "O_CLOEXEC", 0)) | int(getattr(os, "O_NOFOLLOW", 0))
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if not (
            stat.S_ISREG(opened.st_mode)
            and opened.st_dev == before.st_dev
            and opened.st_ino == before.st_ino
            and opened.st_size == before.st_size
            and _owned_by_current_user(opened)
            and (not require_single_link or opened.st_nlink == 1)
            and (require_mode is None or stat.S_IMODE(opened.st_mode) == require_mode)
        ):
            return None, "file_identity_changed"
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                return None, "file_too_large"
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
        ):
            return None, "file_changed_during_read"
        data = b"".join(chunks)
        return (data, "") if len(data) == opened.st_size else (None, "file_short_read")
    except OSError:
        return None, "file_open_failed"
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _path_under(root: Path, value: object, *, required_prefix: Path) -> Path | None:
    text = str(value or "").strip()
    relative = Path(text)
    if not text or relative.is_absolute():
        return None
    try:
        normalized = Path(os.path.normpath(text))
        normalized.relative_to(required_prefix)
        resolved_root = root.resolve()
        candidate = resolved_root / normalized
        candidate.parent.resolve().relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    return candidate if _directory_chain_secure(resolved_root, candidate.parent) else None


def _png_bytes_valid(data: bytes, expected_size: tuple[int, int]) -> bool:
    if len(data) < 67 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return False
    offset = 8
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(data):
        if offset + 12 > len(data):
            return False
        length = int.from_bytes(data[offset : offset + 4], "big")
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if length > 32 * 1024 * 1024 or end > len(data):
            return False
        payload = data[offset + 8 : offset + 8 + length]
        observed_crc = int.from_bytes(data[offset + 8 + length : end], "big")
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != observed_crc:
            return False
        chunks.append((kind, payload))
        offset = end
        if kind == b"IEND":
            break
    if offset != len(data) or not chunks or chunks[0][0] != b"IHDR" or chunks[-1] != (b"IEND", b""):
        return False
    if len(chunks[0][1]) != 13 or not any(kind == b"IDAT" and payload for kind, payload in chunks):
        return False
    width = int.from_bytes(chunks[0][1][:4], "big")
    height = int.from_bytes(chunks[0][1][4:8], "big")
    if (width, height) != expected_size:
        return False
    try:
        from PIL import Image

        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG" or image.size != expected_size:
                return False
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            if image.format != "PNG" or image.size != expected_size:
                return False
            rgba = image.convert("RGBA")
            extrema = rgba.getextrema()
            alpha_histogram = rgba.getchannel("A").histogram()
            nontransparent = sum(alpha_histogram[1:])
            if extrema[3][1] == 0 or nontransparent < expected_size[0] * expected_size[1] // 2:
                return False
            rgb = rgba.convert("RGB")
            if all(low == high for low, high in rgb.getextrema()):
                return False
            luminance = rgba.convert("L")
            histogram = luminance.histogram()
            total = sum(histogram)
            mean = sum(index * count for index, count in enumerate(histogram)) / max(total, 1)
            variance = sum(((index - mean) ** 2) * count for index, count in enumerate(histogram)) / max(total, 1)
            if variance < 4.0:
                return False
            return luminance.getbbox() is not None
    except Exception:
        return False


def _measured_viewport_ready(
    row: Mapping[str, Any], expected_dimensions: tuple[int, int] | None
) -> tuple[bool, tuple[int, int] | None]:
    dpr = row.get("device_pixel_ratio")
    ready = bool(
        expected_dimensions is not None
        and type(row.get("observed_inner_width")) is int
        and type(row.get("observed_inner_height")) is int
        and (row.get("observed_inner_width"), row.get("observed_inner_height")) == expected_dimensions
        and type(dpr) in {int, float}
        and not isinstance(dpr, bool)
        and math.isfinite(float(dpr))
        and 1.0 <= float(dpr) <= 4.0
    )
    return (
        ready,
        (
            round(expected_dimensions[0] * float(dpr)),
            round(expected_dimensions[1] * float(dpr)),
        )
        if ready and expected_dimensions is not None
        else None,
    )


def _normalized_visible_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(
        char
        for char in normalized
        if not _default_ignorable(ord(char))
    )


def _default_ignorable(codepoint: int) -> bool:
    return any(
        lower <= codepoint <= upper
        for lower, upper in (
            (0x00AD, 0x00AD),
            (0x034F, 0x034F),
            (0x061C, 0x061C),
            (0x115F, 0x1160),
            (0x17B4, 0x17B5),
            (0x180B, 0x180F),
            (0x200B, 0x200F),
            (0x202A, 0x202E),
            (0x2060, 0x206F),
            (0x3164, 0x3164),
            (0xFE00, 0xFE0F),
            (0xFEFF, 0xFEFF),
            (0xFFA0, 0xFFA0),
            (0xFFF0, 0xFFF8),
            (0x1BCA0, 0x1BCA3),
            (0x1D173, 0x1D17A),
            (0xE0000, 0xE0FFF),
        )
    )


def _json_rows(value: object) -> list[dict[str, Any]] | None:
    if not isinstance(value, str):
        return None
    try:
        decoded = json.loads(value)
    except Exception:
        return None
    if not isinstance(decoded, list) or not all(isinstance(row, Mapping) for row in decoded):
        return None
    return [dict(row) for row in decoded]


def _runner_source_sha256(project_root: Path = PROJECT_ROOT) -> str:
    path = project_root / "scripts" / RUNNER_PATH.name
    data, blocker = _secure_read_file(path, require_single_link=False, max_bytes=2 * 1024 * 1024)
    return hashlib.sha256(data).hexdigest() if data is not None and not blocker else ""


def _inspect_typescript_source(project_root: Path) -> tuple[dict[str, Any] | None, str]:
    runner_path = project_root / "scripts" / RUNNER_PATH.name
    try:
        result = subprocess.run(
            ["node", str(runner_path), "--inspect-source", "--json", "--project-root", str(project_root)],
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "source_ast_runner_unavailable"
    try:
        payload = json.loads(result.stdout)
    except Exception:
        return None, "source_ast_output_invalid"
    if result.returncode != 0 or not isinstance(payload, Mapping):
        return None, "source_ast_contract_blocked"
    expected_fields = {
        "schema_version",
        "status",
        "ordinary_routes",
        "ordinary_components",
        "ordinary_component_root_ids",
        "ordinary_route_headings",
        "ordinary_component_source_sha256",
        "ordinary_component_import_manifest",
        "ordinary_component_import_manifest_digest",
        "ordinary_component_map_digest",
        "active_route_binding",
        "component_root_identity_attribute",
        "legacy_route_group",
        "legacy_route_primary",
        "legacy_component_root_id",
        "legacy_component_source_sha256",
        "forbidden_ordinary_component_ids",
        "tauri_default_route",
        "layout_source_sha256",
        "app_source_sha256",
        "trusted_reachable_source_sha256",
        "trusted_reachable_source_digest",
        "native_escape_policy",
        "runner_source_sha256",
        "blockers",
        "source_contract_digest",
    }
    material = dict(payload)
    observed_digest = material.pop("source_contract_digest", "")
    expected_routes = [route.removeprefix("#") for route, _ in EXPECTED_ROUTES]
    expected_components = {route.removeprefix("#"): component for route, component in EXPECTED_ROUTES}
    expected_headings = {route.removeprefix("#"): heading for route, heading in EXPECTED_ROUTE_HEADINGS.items()}
    component_source_hashes = payload.get("ordinary_component_source_sha256")
    import_manifest = payload.get("ordinary_component_import_manifest")
    trusted_reachable_hashes = payload.get("trusted_reachable_source_sha256")
    if not (
        set(payload) == expected_fields
        and payload.get("schema_version") == SOURCE_SCHEMA
        and payload.get("status") == "source_ast_contract_verified"
        and payload.get("ordinary_routes") == expected_routes
        and payload.get("ordinary_components") == expected_components
        and payload.get("ordinary_component_root_ids") == expected_components
        and payload.get("ordinary_route_headings") == expected_headings
        and isinstance(component_source_hashes, Mapping)
        and set(component_source_hashes) == set(expected_routes)
        and all(_valid_sha256(value) for value in component_source_hashes.values())
        and isinstance(import_manifest, Mapping)
        and set(import_manifest) == set(expected_routes)
        and all(isinstance(rows, list) and rows for rows in import_manifest.values())
        and payload.get("ordinary_component_import_manifest_digest")
        == _digest(import_manifest)
        == EXPECTED_IMPORT_MANIFEST_DIGEST
        and payload.get("ordinary_component_map_digest") == _digest(expected_components)
        and payload.get("active_route_binding") == "ROUTE_COMPONENTS[route]"
        and payload.get("component_root_identity_attribute") == "data-ltg10-component-id"
        and payload.get("legacy_route_group") == "系统迁移"
        and payload.get("legacy_route_primary") is False
        and payload.get("legacy_component_root_id") == "LegacyTools"
        and _valid_sha256(payload.get("legacy_component_source_sha256"))
        and payload.get("forbidden_ordinary_component_ids") == list(FORBIDDEN_ORDINARY_COMPONENT_IDS)
        and payload.get("tauri_default_route") == "home"
        and payload.get("blockers") == []
        and _valid_sha256(payload.get("layout_source_sha256"))
        and _valid_sha256(payload.get("app_source_sha256"))
        and isinstance(trusted_reachable_hashes, Mapping)
        and bool(trusted_reachable_hashes)
        and all(isinstance(path, str) and _valid_sha256(value) for path, value in trusted_reachable_hashes.items())
        and payload.get("trusted_reachable_source_digest") == _digest(trusted_reachable_hashes)
        and payload.get("native_escape_policy")
        == "no_prototype_descriptor_reflect_lookup_call_apply_bind_or_network_native_alias"
        and payload.get("runner_source_sha256") == _runner_source_sha256(project_root)
        and observed_digest == _digest(material)
    ):
        return None, "source_ast_contract_invalid"
    return dict(payload), ""


def _simple_python_value(node: ast.AST, names: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return names.get(node.id, object())
    if isinstance(node, ast.Dict):
        result: dict[str, Any] = {}
        for key_node, value_node in zip(node.keys, node.values):
            key = _simple_python_value(key_node, names) if key_node is not None else object()
            value = _simple_python_value(value_node, names)
            if not isinstance(key, str) or isinstance(value, object) and type(value) is object:
                return object()
            result[key] = value
        return result
    return object()


def _python_fallback_contract(project_root: Path) -> tuple[dict[str, Any] | None, str]:
    app_path = project_root / "app.py"
    service_path = project_root / "server/services/legacy_service.py"
    try:
        app_tree = ast.parse(app_path.read_text(encoding="utf-8"), filename=str(app_path))
        service_tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    except (OSError, SyntaxError):
        return None, "streamlit_admin_debug_source_unparseable"
    names: dict[str, Any] = {}
    assignment_counts: dict[str, int] = {}
    for statement in app_tree.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            continue
        name = statement.targets[0].id
        assignment_counts[name] = assignment_counts.get(name, 0) + 1
        names[name] = _simple_python_value(statement.value, names)
    expected_policy = {
        "official_primary_entry": "React/Vite/Tauri + FastAPI",
        "streamlit_role": "legacy/admin/debug",
        "streamlit_is_primary_entry": False,
        "startup_external_calls": False,
        "startup_task_creation": False,
        "startup_real_trading": False,
        "can_bypass_strategy_guardrails": False,
    }
    matching_service_policies = []
    for node in ast.walk(service_tree):
        if isinstance(node, ast.Dict):
            value = _simple_python_value(node, {})
            if isinstance(value, dict) and "streamlit_role" in value:
                matching_service_policies.append(value)
    service_policy_ready = len(matching_service_policies) == 1 and all(
        matching_service_policies[0].get(key) == value
        for key, value in {
            "streamlit_role": "legacy/admin/debug",
            "official_primary_entry": "React/Vite/Tauri + FastAPI",
            "streamlit_is_official_primary_entry": False,
            "react_tauri_is_primary_entry": True,
        }.items()
    )
    ready = bool(
        assignment_counts.get("STREAMLIT_LEGACY_MODE_STATUS") == 1
        and assignment_counts.get("COMMAND_CENTER_3_OFFICIAL_ENTRY") == 1
        and assignment_counts.get("STREAMLIT_LEGACY_EXIT_POLICY") == 1
        and names.get("STREAMLIT_LEGACY_MODE_STATUS") == "legacy/admin/debug"
        and names.get("COMMAND_CENTER_3_OFFICIAL_ENTRY") == "React/Vite/Tauri + FastAPI"
        and names.get("STREAMLIT_LEGACY_EXIT_POLICY") == expected_policy
        and service_policy_ready
    )
    if not ready:
        return None, "streamlit_admin_debug_policy_not_ast_verified"
    material = {
        "schema_version": "streamlit_admin_debug_python_ast_contract.v1",
        "fallback_disposition": "admin_debug_only_retained",
        "app_source_sha256": hashlib.sha256(app_path.read_bytes()).hexdigest(),
        "legacy_service_source_sha256": hashlib.sha256(service_path.read_bytes()).hexdigest(),
    }
    return {**material, "contract_digest": _digest(material)}, ""


def _source_contract(project_root: Path) -> tuple[dict[str, Any] | None, str]:
    typescript_contract, blocker = _inspect_typescript_source(project_root)
    if blocker or typescript_contract is None:
        return None, blocker
    python_contract, blocker = _python_fallback_contract(project_root)
    if blocker or python_contract is None:
        return None, blocker
    material = {
        "schema_version": "streamlit_retirement_combined_source_contract.v3",
        "typescript_contract_digest": typescript_contract["source_contract_digest"],
        "python_contract_digest": python_contract["contract_digest"],
        "ordinary_component_map_digest": typescript_contract["ordinary_component_map_digest"],
        "fallback_disposition": python_contract["fallback_disposition"],
        "runner_source_sha256": typescript_contract["runner_source_sha256"],
    }
    return {**material, "source_contract_digest": _digest(material)}, ""


def _local_network_row(row: Mapping[str, Any], expected_sequence: int) -> bool:
    if set(row) != NETWORK_FIELDS or type(row.get("sequence")) is not int or row.get("sequence") != expected_sequence:
        return False
    if type(row.get("observed_monotonic_ns")) is not int or int(row["observed_monotonic_ns"]) <= 0:
        return False
    if not re.fullmatch(r"(?:request|resource)-[1-9][0-9]*", str(row.get("request_id") or "")):
        return False
    if row.get("phase") not in {"navigation", "settle"}:
        return False
    if str(row.get("method") or "").upper() not in {"GET", "OPTIONS"}:
        return False
    if str(row.get("resource_type") or "") not in {"document", "fetch", "xhr", "script", "stylesheet", "image", "font", "other"}:
        return False
    if type(row.get("status")) is not int or not 0 <= int(row["status"]) <= 599:
        return False
    method = str(row.get("method") or "").upper()
    url = str(row.get("url") or "")
    expected_task = method in {"POST", "PUT", "PATCH", "DELETE"} or bool(
        re.search(r"/api/(?:tasks?|.*(?:task|review|execute|launch))", url, re.IGNORECASE)
    )
    if row.get("task_request") is not expected_task:
        return False
    if type(row.get("pending_count_after")) is not int or int(row["pending_count_after"]) < 0:
        return False
    parsed = urlparse(url)
    if parsed.scheme == "tauri":
        return bool(
            parsed.hostname in {"localhost", None}
            and not parsed.port
            and (not parsed.fragment or f"#{parsed.fragment}" in {route for route, _ in EXPECTED_ROUTES})
            and parsed.fragment != "legacy"
        )
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        and parsed.port != 8501
    )


def _network_ledger_complete(rows: list[Any]) -> bool:
    if len(rows) < 2 or not all(
        isinstance(row, Mapping) and _local_network_row(row, index)
        for index, row in enumerate(rows, 1)
    ):
        return False
    requests: dict[str, list[Mapping[str, Any]]] = {}
    pending_count = 0
    for row in rows:
        if row.get("resource_type") in {"fetch", "xhr"}:
            pending_count += 1 if row.get("phase") == "navigation" else -1
        if pending_count < 0 or row.get("pending_count_after") != pending_count:
            return False
        requests.setdefault(str(row.get("request_id") or ""), []).append(row)
    return pending_count == 0 and all(
        len(entries) == 2
        and entries[0].get("phase") == "navigation"
        and entries[1].get("phase") == "settle"
        and entries[0].get("method") == entries[1].get("method")
        and entries[0].get("resource_type") == entries[1].get("resource_type")
        for entries in requests.values()
    )


def _network_seal_ready(value: object) -> bool:
    if not isinstance(value, Mapping) or set(value) != NETWORK_SEAL_FIELDS:
        return False
    ledger = value.get("ledger_digest_material") if isinstance(value.get("ledger_digest_material"), list) else []
    return bool(
        value.get("sealed") is True
        and value.get("pending_request_count") == 0
        and type(value.get("quiet_window_ms")) is int
        and int(value.get("quiet_window_ms") or 0) >= 500
        and type(value.get("quiet_elapsed_ms")) in {int, float}
        and not isinstance(value.get("quiet_elapsed_ms"), bool)
        and float(value.get("quiet_elapsed_ms") or 0) >= int(value.get("quiet_window_ms") or 0)
        and value.get("instrumentation_integrity") is True
        and value.get("late_event_count") == 0
        and value.get("late_events") == []
        and value.get("deny_all_network_guard") is True
        and value.get("denied_attempt_count") == 0
        and value.get("denied_attempts") == []
        and value.get("guard_mode") == FINAL_NETWORK_GUARD
        and type(value.get("interval_registration_count")) is int
        and int(value.get("interval_registration_count") or 0) >= 0
        and type(value.get("interval_clear_count")) is int
        and value.get("interval_registration_count") == value.get("interval_clear_count")
        and type(value.get("tracked_interval_count")) is int
        and int(value.get("tracked_interval_count") or 0) >= 0
        and type(value.get("quiesced_interval_count")) is int
        and value.get("tracked_interval_count") == value.get("quiesced_interval_count")
        and type(value.get("active_interval_count_after_quiesce")) is int
        and value.get("active_interval_count_after_quiesce") == 0
        and value.get("interval_registry_integrity") is True
        and type(value.get("quiesce_started_at_monotonic_ns")) is int
        and int(value.get("quiesce_started_at_monotonic_ns") or 0) > 0
        and type(value.get("quiesce_completed_at_monotonic_ns")) is int
        and int(value.get("quiesce_completed_at_monotonic_ns") or 0)
        >= int(value.get("quiesce_started_at_monotonic_ns") or 0)
        and value.get("quiesce_complete") is True
        and type(value.get("denied_interval_registration_count")) is int
        and value.get("denied_interval_registration_count") == 0
        and type(value.get("final_window_ms")) is int
        and int(value.get("final_window_ms") or 0) >= 10_500
        and type(value.get("final_window_elapsed_ms")) in {int, float}
        and not isinstance(value.get("final_window_elapsed_ms"), bool)
        and float(value.get("final_window_elapsed_ms") or 0) >= int(value.get("final_window_ms") or 0)
        and type(value.get("ledger_count")) is int
        and value.get("ledger_count") == len(ledger)
        and _network_ledger_complete(ledger)
    )


def _network_seal_matches_last_row(value: object, last_network_ledger: list[Any]) -> bool:
    return bool(
        _network_seal_ready(value)
        and isinstance(value, Mapping)
        and value.get("ledger_digest_material") == last_network_ledger
    )


def _dom_ledger_ready(rows: list[Any], route: str, expected_component: str) -> tuple[bool, str, str]:
    if not rows or not all(isinstance(item, Mapping) for item in rows):
        return False, "", ""
    normalized = [dict(item) for item in rows]
    if not all(
        set(item) == DOM_FIELDS
        and type(item.get("sequence")) is int
        and item.get("sequence") == index
        and item.get("kind")
        in {"exists", "count", "attribute", "text", "html", "accessibility", "computed", "pseudo", "canvas"}
        and isinstance(item.get("selector"), str)
        for index, item in enumerate(normalized, 1)
    ):
        return False, "", ""
    exact = {(item["kind"], item["selector"]): item.get("value") for item in normalized}
    heading = exact.get(("text", "[data-ltg10-route-heading]"))
    heading_route = exact.get(("attribute", "[data-ltg10-route-heading]@data-ltg10-route-heading"))
    heading_tag = exact.get(("attribute", "[data-ltg10-route-heading]@tagName"))
    actual_component = exact.get(("attribute", COMPONENT_ATTRIBUTE_SELECTOR))
    body_html = exact.get(("html", BODY_HTML_SELECTOR))
    body_text = exact.get(("text", "body@innerText"))
    accessibility = _json_rows(exact.get(("accessibility", "body@accessibility-tree")))
    computed = _json_rows(exact.get(("computed", "body@computed-style-tree")))
    pseudo = _json_rows(exact.get(("pseudo", "body@pseudo-content")))
    canvas = _json_rows(exact.get(("canvas", "body@canvas-inventory")))
    normalized_surfaces = _normalized_visible_text(
        "\n".join(
            str(value or "")
            for value in (
                body_html,
                body_text,
                json.dumps(accessibility or [], ensure_ascii=False, sort_keys=True),
                json.dumps(computed or [], ensure_ascii=False, sort_keys=True),
                json.dumps(pseudo or [], ensure_ascii=False, sort_keys=True),
            )
        )
    ).casefold()
    component_selector = f'[data-ltg10-component-id="{expected_component}"]'
    component_styles = [row for row in computed or [] if row.get("selector") == component_selector]
    heading_selector = f'[data-ltg10-route-heading="{route.removeprefix("#")}"]'
    heading_styles = [row for row in computed or [] if row.get("selector") == heading_selector]
    accessibility_ready = bool(
        accessibility
        and all(
            set(row) == {"selector", "tag", "role", "name", "aria_hidden", "aria_current", "disabled", "visible"}
            and isinstance(row.get("selector"), str)
            and isinstance(row.get("visible"), bool)
            for row in accessibility
        )
        and any(row.get("visible") is True and str(row.get("name") or "").strip() for row in accessibility)
    )
    computed_ready = bool(
        computed
        and all(
            set(row)
            == {
                "selector",
                "display",
                "visibility",
                "opacity",
                "overflow",
                "color",
                "background_color",
                "before",
                "after",
                "visible",
                "viewport_intersection",
                "clipped",
                "content_visibility",
                "occluded",
                "color_alpha",
            }
            and isinstance(row.get("selector"), str)
            and isinstance(row.get("visible"), bool)
            and type(row.get("viewport_intersection")) in {int, float}
            and not isinstance(row.get("viewport_intersection"), bool)
            and isinstance(row.get("clipped"), bool)
            and isinstance(row.get("content_visibility"), str)
            and isinstance(row.get("occluded"), bool)
            and type(row.get("color_alpha")) in {int, float}
            and not isinstance(row.get("color_alpha"), bool)
            for row in computed
        )
        and len(component_styles) == 1
        and component_styles[0].get("visible") is True
        and component_styles[0].get("display") != "none"
        and component_styles[0].get("visibility") != "hidden"
    )
    pseudo_ready = bool(
        pseudo is not None
        and all(
            set(row) == {"selector", "before", "after", "visible"}
            and isinstance(row.get("selector"), str)
            and isinstance(row.get("visible"), bool)
            for row in pseudo
        )
    )
    canvas_ready = bool(
        canvas is not None
        and all(
            set(row) == {"index", "width", "height", "css_width", "css_height", "visible"}
            and type(row.get("index")) is int
            and type(row.get("width")) is int
            and type(row.get("height")) is int
            and isinstance(row.get("visible"), bool)
            for row in canvas
        )
    )
    ready = bool(
        len(exact) == len(normalized)
        and exact.get(("exists", "#root")) is True
        and exact.get(("count", "button[data-route-active='true']")) == 1
        and exact.get(("attribute", "button[data-route-active='true']@data-route-key")) == route.removeprefix("#")
        and exact.get(("count", "[data-ltg10-route-heading]")) == 1
        and heading_route == route.removeprefix("#")
        and heading_tag in {"h1", "h2"}
        and isinstance(heading, str)
        and heading.strip() == EXPECTED_ROUTE_HEADINGS.get(route)
        and len(heading_styles) == 1
        and heading_styles[0].get("visible") is True
        and float(heading_styles[0].get("viewport_intersection") or 0) > 0
        and heading_styles[0].get("content_visibility") != "hidden"
        and heading_styles[0].get("occluded") is False
        and float(heading_styles[0].get("color_alpha") or 0) > 0
        and exact.get(("count", COMPONENT_COUNT_SELECTOR)) == 1
        and exact.get(("count", ROOT_COMPONENT_COUNT_SELECTOR)) == 1
        and actual_component == expected_component
        and actual_component not in FORBIDDEN_ORDINARY_COMPONENT_IDS
        and exact.get(("count", FORBIDDEN_COMPONENT_SELECTOR)) == 0
        and exact.get(("count", "button[data-route-key='legacy'][data-route-active='true']")) == 0
        and exact.get(("count", "[data-streamlit-surface],iframe[src*='streamlit']")) == 0
        and exact.get(("count", BODY_NON_ROOT_SURFACE_SELECTOR)) == 0
        and exact.get(("count", "body@frame-surface-count")) == 0
        and exact.get(("count", "body@open-shadow-root-count")) == 0
        and exact.get(("count", "body@attach-shadow-call-count")) == 0
        and exact.get(("count", "body@custom-element-event-count")) == 0
        and exact.get(("count", "body@custom-element-surface-count")) == 0
        and exact.get(("count", "body@dynamic-frame-create-count")) == 0
        and isinstance(body_html, str)
        and body_html.count("data-ltg10-component-id=") == 1
        and f'data-ltg10-component-id="{expected_component}"' in body_html
        and isinstance(body_text, str)
        and body_text.strip()
        and accessibility_ready
        and computed_ready
        and pseudo_ready
        and canvas_ready
        and not any(_normalized_visible_text(token).casefold() in normalized_surfaces for token in FORBIDDEN_BODY_TOKENS)
    )
    return ready, str(heading or "").strip(), str(actual_component or "").strip()


def _dom_canvas_present_count(rows: list[Any]) -> int | None:
    if not rows or not all(isinstance(item, Mapping) for item in rows):
        return None
    matches = [
        item.get("value")
        for item in rows
        if item.get("kind") == "canvas" and item.get("selector") == "body@canvas-inventory"
    ]
    if len(matches) != 1:
        return None
    canvas = _json_rows(matches[0])
    return len(canvas) if canvas is not None else None


def _task_post_counts_zero(row: Mapping[str, Any]) -> bool:
    return bool(
        type(row.get("task_post_count_before")) is int
        and type(row.get("task_post_count_after")) is int
        and type(row.get("navigation_post_count")) is int
        and row.get("task_post_count_before") == 0
        and row.get("task_post_count_after") == 0
        and row.get("navigation_post_count") == 0
    )


def _post_seal_capture_ready(row: Mapping[str, Any], index: int, total: int) -> bool:
    expected = total > 0 and index == total - 1
    return bool(
        row.get("post_seal_capture") is expected
        and row.get("deny_all_network_guard_at_observation") is expected
        and type(row.get("late_event_count_at_observation")) is int
        and row.get("late_event_count_at_observation") == 0
        and type(row.get("denied_attempt_count_at_observation")) is int
        and row.get("denied_attempt_count_at_observation") == 0
        and type(row.get("denied_interval_registration_count_at_observation")) is int
        and row.get("denied_interval_registration_count_at_observation") == 0
    )


def _runner_row_hmac_valid(row: Mapping[str, Any], nonce: bytes) -> bool:
    if set(row) != ROW_FIELDS:
        return False
    material = dict(row)
    observed = str(material.pop("row_hmac_sha256", ""))
    expected = hmac.new(nonce, _canonical_bytes(material), hashlib.sha256).hexdigest()
    return _valid_sha256(observed) and hmac.compare_digest(observed, expected)


def _exact_tauri_route_url(value: object, route: str) -> bool:
    parsed = urlparse(str(value or ""))
    return bool(
        parsed.scheme == "tauri"
        and parsed.netloc == "localhost"
        and parsed.path in {"", "/"}
        and parsed.params == ""
        and parsed.query == ""
        and parsed.fragment == route.removeprefix("#")
    )


def _validate_trusted_runner_attestation(
    session_root: Path,
    *,
    attestation: Mapping[str, Any],
    challenge: Mapping[str, Any],
    nonce: bytes,
    expected_runner_pid: int,
    expected_runner_executable: Path,
    expected_head_full: str,
    package: Mapping[str, Any],
    project_root: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    if set(attestation) != ATTESTATION_FIELDS:
        return None, ["trusted_runner_attestation_schema_fields_invalid"]
    report = dict(attestation)
    actual_head = _git_head_full(project_root)
    if actual_head != expected_head_full:
        blockers.append("actual_git_head_does_not_match_expected")
    runner_hash = _runner_source_sha256(project_root)
    challenge_material = dict(challenge)
    observed_challenge_digest = str(challenge_material.pop("challenge_digest", ""))
    nonce_digest = hashlib.sha256(nonce).hexdigest()
    expected_component_map_digest = _digest(
        {route.removeprefix("#"): component for route, component in EXPECTED_ROUTES}
    )
    if not (
        set(challenge) == CHALLENGE_FIELDS
        and challenge.get("schema_version") == CHALLENGE_SCHEMA
        and challenge.get("challenge_digest") == _digest(challenge_material)
        and report.get("schema_version") == ATTESTATION_SCHEMA
        and report.get("status")
        in {
            "actual_packaged_tauri_ordinary_flow_passed",
            "actual_packaged_tauri_ordinary_flow_awaiting_visual_review",
        }
        and report.get("attestation_mode") == "production_packaged_tauri_nonce_bound"
        and report.get("runner_identity") == "scripts/streamlit_retirement_packaged_qa_runner.mjs"
        and type(report.get("runner_pid")) is int
        and report.get("runner_pid") == expected_runner_pid
        and Path(str(report.get("runner_executable_path") or "")).resolve() == expected_runner_executable.resolve()
        and report.get("runner_source_sha256") == runner_hash
        and _valid_utc(report.get("generated_at"))
        and report.get("challenge_id") == challenge.get("challenge_id")
        and report.get("challenge_digest") == observed_challenge_digest
        and report.get("nonce_digest") == nonce_digest == challenge.get("nonce_digest")
        and _nonce_bound_response_valid(report, nonce, response_field="runner_response_sha256")
        and _normalize_head(report.get("head_full")) == expected_head_full
        and report.get("runtime_surface") == "actual_packaged_tauri_react"
        and report.get("protocol") == "tauri:"
        and report.get("app_exit_confirmed") is True
        and report.get("app_exit_code") == 0
        and report.get("app_exit_signal") == ""
        and _normalize_head(report.get("package_head_full")) == expected_head_full
        and Path(str(challenge.get("app_executable_path") or "")).resolve()
        == (project_root / PACKAGED_APP_EXECUTABLE_RELATIVE).resolve()
        and Path(str(challenge.get("app_bundle_path") or "")).resolve()
        == (
            project_root
            / "desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app"
        ).resolve()
    ):
        blockers.append("trusted_runner_identity_nonce_or_head_invalid")
    if not (
        report.get("source_contract_digest") == challenge.get("source_contract_digest")
        and report.get("ordinary_component_map_digest")
        == challenge.get("ordinary_component_map_digest")
        == expected_component_map_digest
    ):
        blockers.append("trusted_runner_component_or_source_binding_invalid")
    package_hashes = {
        "artifact_set_sha256": package.get("artifact_set_sha256"),
        "app_bundle_sha256": package.get("app_bundle_sha256"),
        "app_executable_sha256": package.get("app_executable_sha256"),
        "dmg_sha256": package.get("dmg_sha256"),
    }
    measured_package = tauri_package_verifier.measure_fixed_tauri_package_artifacts(project_root)
    if not (
        package.get("production_package_complete") is True
        and _normalize_head(package.get("head_full")) == expected_head_full
        and not measured_package.get("blockers")
        and all(_valid_sha256(value) for value in package_hashes.values())
        and all(measured_package.get(key) == value for key, value in package_hashes.items())
        and challenge.get("app_executable_path") == measured_package.get("app_executable_path")
        and challenge.get("app_bundle_path") == measured_package.get("app_path")
        and challenge.get("dmg_path") == measured_package.get("dmg_path")
        and challenge.get("bundle_identifier") == measured_package.get("bundle_identifier")
        and challenge.get("bundle_version") == measured_package.get("bundle_version")
        and package.get("bundle_identifier") == measured_package.get("bundle_identifier")
        and package.get("bundle_version") == measured_package.get("bundle_version")
        and all(challenge.get(key) == value for key, value in package_hashes.items())
        and all(report.get(key) == value for key, value in package_hashes.items())
    ):
        blockers.append("formal_package_verifier_binding_invalid")
    app = report.get("app_attestation") if isinstance(report.get("app_attestation"), Mapping) else {}
    native_app = {
        key: value
        for key, value in app.items()
        if key not in APP_TRANSPORT_ATTESTATION_FIELDS
        and key != "output_frame_transport_response_sha256"
    }
    transport_material = {
        key: app.get(key)
        for key in APP_TRANSPORT_ATTESTATION_FIELDS
    }
    observed_transport_response = str(app.get("output_frame_transport_response_sha256") or "")
    expected_transport_response = hashlib.sha256(
        nonce + _canonical_bytes(transport_material)
    ).hexdigest()
    transport_attestation_ready = bool(
        app.get("output_frame_magic") == "LTG10QA1"
        and app.get("output_frame_version") == 1
        and app.get("output_frame_codec") == "gzip_deterministic_v1"
        and app.get("output_frame_flags") == 0
        and app.get("output_frame_reserved") == 0
        and type(app.get("output_frame_compressed_bytes")) is int
        and 0 < int(app.get("output_frame_compressed_bytes") or 0) <= 64 * 1024 * 1024
        and type(app.get("output_frame_uncompressed_bytes")) is int
        and 0 < int(app.get("output_frame_uncompressed_bytes") or 0) <= MAX_TRUSTED_NATIVE_PAYLOAD_BYTES
        and _valid_sha256(app.get("output_frame_raw_json_sha256"))
        and _valid_sha256(observed_transport_response)
        and hmac.compare_digest(observed_transport_response, expected_transport_response)
        and int(report.get("payload_size_bytes") or 0)
        >= 96 + int(app.get("output_frame_compressed_bytes") or 0)
    )
    app_executable = Path(str(app.get("executable_path") or ""))
    app_parent_executable = Path(str(app.get("parent_executable_path") or ""))
    node_executable = shutil.which("node")
    executable_data, executable_blocker = _secure_read_file(
        app_executable,
        max_bytes=512 * 1024 * 1024,
        require_single_link=False,
    )
    network_seal_value = report.get("network_seal_audit") if isinstance(report.get("network_seal_audit"), Mapping) else {}
    exit_contract = {
        "final_network_guard": FINAL_NETWORK_GUARD,
        "final_window_ms": app.get("final_window_ms"),
        "exit_after_output": True,
        "expected_exit_code": 0,
    }
    if not (
        set(app) == APP_ATTESTATION_FIELDS
        and transport_attestation_ready
        and app.get("schema_version") == APP_ATTESTATION_SCHEMA
        and app.get("status") == "packaged_tauri_app_nonce_attested"
        and type(app.get("pid")) is int
        and int(app.get("pid") or 0) > 1
        and type(app.get("parent_pid")) is int
        and app.get("parent_pid") == report.get("runner_pid") == expected_runner_pid
        and app_parent_executable.is_absolute()
        and node_executable is not None
        and app_parent_executable.resolve() == Path(node_executable).resolve()
        and app_executable.is_absolute()
        and app_executable.resolve() == (project_root / PACKAGED_APP_EXECUTABLE_RELATIVE).resolve()
        and executable_data is not None
        and not executable_blocker
        and hashlib.sha256(executable_data).hexdigest() == app.get("executable_sha256") == package_hashes["app_executable_sha256"]
        and app.get("bundle_sha256") == package_hashes["app_bundle_sha256"]
        and app.get("artifact_set_sha256") == package_hashes["artifact_set_sha256"]
        and app.get("dmg_sha256") == package_hashes["dmg_sha256"]
        and _normalize_head(app.get("head_full")) == expected_head_full
        and app.get("challenge_digest") == observed_challenge_digest
        and app.get("nonce_digest") == nonce_digest
        and app.get("source_contract_digest") == challenge.get("source_contract_digest")
        and app.get("ordinary_component_map_digest")
        == challenge.get("ordinary_component_map_digest")
        == expected_component_map_digest
        and _valid_sha256(app.get("route_payload_sha256"))
        and app.get("network_seal_sha256") == _digest(report.get("network_seal_audit"))
        and app.get("native_snapshot_api")
        == "WKWebView.takeSnapshotWithConfiguration.afterScreenUpdates"
        and app.get("final_network_guard") == FINAL_NETWORK_GUARD
        and app.get("final_window_ms") == network_seal_value.get("final_window_ms")
        and app.get("exit_after_output") is True
        and app.get("expected_exit_code") == 0
        and app.get("exit_contract_sha256") == _digest(exit_contract)
        and _nonce_bound_response_valid(native_app, nonce, response_field="response_sha256")
    ):
        blockers.append("packaged_tauri_app_nonce_attestation_invalid")
    source, source_blocker = _source_contract(project_root)
    if source is None:
        blockers.append(source_blocker or "source_contract_invalid")
    elif not (
        report.get("runner_source_sha256") == source.get("runner_source_sha256")
        and challenge.get("source_contract_digest")
        == report.get("source_contract_digest")
        == app.get("source_contract_digest")
        == source.get("source_contract_digest")
        and challenge.get("ordinary_component_map_digest")
        == report.get("ordinary_component_map_digest")
        == app.get("ordinary_component_map_digest")
        == source.get("ordinary_component_map_digest")
        == expected_component_map_digest
    ):
        blockers.append("runner_source_or_component_map_not_bound_to_source_contract")

    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    expected_pairs = {
        (route, viewport)
        for route, _component in EXPECTED_ROUTES
        for viewport in EXPECTED_VIEWPORTS
    }
    expected_components = dict(EXPECTED_ROUTES)
    observed_pairs: set[tuple[str, str]] = set()
    screenshot_hashes: list[str] = []
    network_ledgers: list[list[dict[str, Any]]] = []
    sanitized_rows: list[dict[str, Any]] = []
    native_rows: list[dict[str, Any]] = []
    visual_review_rows: list[dict[str, Any]] = []
    canvas_present_count = 0
    expected_count = len(expected_pairs)
    for row_index, row_value in enumerate(rows):
        if not isinstance(row_value, Mapping) or set(row_value) != ROW_FIELDS:
            blockers.append("raw_runner_row_schema_invalid")
            continue
        if not _runner_row_hmac_valid(row_value, nonce):
            blockers.append("trusted_runner_route_row_hmac_invalid")
        row = dict(row_value)
        row.pop("row_hmac_sha256", None)
        route = str(row.get("route") or "")
        viewport = str(row.get("viewport") or "")
        pair = (route, viewport)
        if pair in observed_pairs:
            blockers.append("raw_runner_route_viewport_duplicate")
        observed_pairs.add(pair)
        expected_dimensions = EXPECTED_VIEWPORTS.get(viewport)
        network = row.get("network_ledger") if isinstance(row.get("network_ledger"), list) else []
        network_ready = bool(
            _network_ledger_complete(network)
            and any(urlparse(str(item.get("url") or "")).scheme == "tauri" for item in network if isinstance(item, Mapping))
            and all(str(item.get("method") or "").upper() not in {"POST", "PUT", "PATCH", "DELETE", "CONNECT"} for item in network if isinstance(item, Mapping))
        )
        dom = row.get("dom_ledger") if isinstance(row.get("dom_ledger"), list) else []
        expected_component = str(expected_components.get(route) or "")
        dom_ready, route_heading, actual_component = _dom_ledger_ready(
            dom,
            route,
            expected_component,
        )
        row_canvas_count = _dom_canvas_present_count(dom)
        if row_canvas_count is None:
            blockers.append("trusted_runner_canvas_inventory_invalid")
        else:
            canvas_present_count += row_canvas_count
        screenshot_path = _path_under(
            session_root,
            row.get("screenshot_path"),
            required_prefix=Path("screenshots"),
        )
        screenshot_sha = str(row.get("screenshot_sha256") or "")
        screenshot_data: bytes | None = None
        if screenshot_path is not None and screenshot_path.suffix.lower() == ".png" and _valid_sha256(screenshot_sha):
            screenshot_data, screenshot_blocker = _secure_read_file(screenshot_path, max_bytes=32 * 1024 * 1024)
            if screenshot_blocker:
                screenshot_data = None
        measured_size_ready, expected_physical = _measured_viewport_ready(row, expected_dimensions)
        screenshot_ready = bool(
            screenshot_data is not None
            and hashlib.sha256(screenshot_data).hexdigest() == screenshot_sha
            and type(row.get("screenshot_byte_length")) is int
            and row.get("screenshot_byte_length") == len(screenshot_data)
            and row.get("screenshot_native_snapshot") is True
            and expected_physical is not None
            and row.get("native_inner_width_px") == expected_physical[0]
            and row.get("native_inner_height_px") == expected_physical[1]
            and row.get("screenshot_pixel_width") == expected_physical[0]
            and row.get("screenshot_pixel_height") == expected_physical[1]
            and _png_bytes_valid(screenshot_data, expected_physical)
        )
        if not (
            pair in expected_pairs
            and row.get("component") == expected_component == actual_component
            and expected_dimensions is not None
            and type(row.get("width")) is int
            and type(row.get("height")) is int
            and (row.get("width"), row.get("height")) == expected_dimensions
            and measured_size_ready
            and _exact_tauri_route_url(row.get("observed_url"), route)
            and row.get("runtime_surface") == "actual_packaged_tauri_react"
            and row.get("protocol") == "tauri:"
            and type(row.get("observation_started_monotonic_ns")) is int
            and type(row.get("observation_finished_monotonic_ns")) is int
            and 0 < int(row.get("observation_started_monotonic_ns") or 0) < int(row.get("observation_finished_monotonic_ns") or 0)
            and dom_ready
            and _task_post_counts_zero(row)
            and row.get("pending_request_count") == 0
            and type(row.get("quiet_window_ms")) is int
            and int(row.get("quiet_window_ms") or 0) >= 500
            and type(row.get("quiet_elapsed_ms")) in {int, float}
            and not isinstance(row.get("quiet_elapsed_ms"), bool)
            and float(row.get("quiet_elapsed_ms") or 0) >= int(row.get("quiet_window_ms") or 0)
            and row.get("instrumentation_integrity") is True
            and row.get("attach_shadow_calls") == []
            and row.get("custom_element_events") == []
            and row.get("dynamic_frame_events") == []
            and _post_seal_capture_ready(row, row_index, expected_count)
            and row.get("network_ledger_complete") is True
            and network_ready
            and screenshot_ready
        ):
            blockers.append("trusted_runner_dom_network_task_or_screenshot_invalid")
        screenshot_hashes.append(screenshot_sha)
        network_ledgers.append([dict(item) for item in network if isinstance(item, Mapping)])
        sanitized_rows.append(
            {
                "route": route,
                "component": row.get("component"),
                "actual_component_id": actual_component,
                "viewport": viewport,
                "width": row.get("width"),
                "height": row.get("height"),
                "observed_inner_width": row.get("observed_inner_width"),
                "observed_inner_height": row.get("observed_inner_height"),
                "device_pixel_ratio": row.get("device_pixel_ratio"),
                "native_inner_width_px": row.get("native_inner_width_px"),
                "native_inner_height_px": row.get("native_inner_height_px"),
                "screenshot_pixel_width": row.get("screenshot_pixel_width"),
                "screenshot_pixel_height": row.get("screenshot_pixel_height"),
                "route_heading": route_heading,
                "dom_ledger_digest": _digest(dom),
            }
        )
        native_row = dict(row)
        native_row.pop("screenshot_path", None)
        native_row["screenshot_index"] = len(native_rows)
        native_rows.append(native_row)
        visual_review_rows.append(
            {
                "sequence": len(visual_review_rows) + 1,
                "route": route,
                "component": row.get("component"),
                "viewport": viewport,
                "source_screenshot_path": str(screenshot_path) if screenshot_path is not None else "",
                "screenshot_sha256": screenshot_sha,
                "pixel_width": row.get("screenshot_pixel_width"),
                "pixel_height": row.get("screenshot_pixel_height"),
            }
        )
    seal_audit = report.get("network_seal_audit")
    seal_ready = _network_seal_ready(seal_audit)
    if not seal_ready or not network_ledgers or not _network_seal_matches_last_row(seal_audit, network_ledgers[-1]):
        blockers.append("trusted_runner_final_network_quiet_seal_invalid")
    if app.get("route_payload_sha256") != _digest(native_rows):
        blockers.append("packaged_tauri_app_route_payload_binding_invalid")
    if observed_pairs != expected_pairs or len(set(screenshot_hashes)) != expected_count:
        blockers.append("trusted_runner_exact_route_matrix_or_screenshot_set_invalid")
    if not (
        type(report.get("route_count")) is int
        and report.get("route_count") == len(EXPECTED_ROUTES)
        and type(report.get("viewport_count")) is int
        and report.get("viewport_count") == len(EXPECTED_VIEWPORTS)
        and type(report.get("qa_matrix_count")) is int
        and report.get("qa_matrix_count") == expected_count
        and type(report.get("passed_count")) is int
        and report.get("passed_count") == expected_count
        and type(report.get("review_required_count")) is int
        and report.get("review_required_count") == canvas_present_count
        and report.get("status")
        == (
            "actual_packaged_tauri_ordinary_flow_awaiting_visual_review"
            if canvas_present_count > 0
            else "actual_packaged_tauri_ordinary_flow_passed"
        )
        and len(rows) == expected_count
        and report.get("network_ledger_complete") is True
        and seal_ready
    ):
        blockers.append("trusted_runner_counts_or_network_completion_invalid")
    if not (
        report.get("external_calls_triggered") is False
        and report.get("tushare_called") is False
        and report.get("deepseek_called") is False
        and report.get("github_called") is False
        and report.get("does_not_execute_trades") is True
        and report.get("does_not_modify_strategy_action") is True
        and report.get("contains_secret") is False
    ):
        blockers.append("trusted_runner_safety_boundary_invalid")
    if not (
        type(report.get("payload_size_bytes")) is int
        and 0 < int(report.get("payload_size_bytes") or 0) <= MAX_TRUSTED_NATIVE_PAYLOAD_BYTES
    ):
        blockers.append("trusted_runner_payload_size_invalid")
    if blockers or source is None:
        return None, sorted(set(blockers))
    return {
        "head_full": expected_head_full,
        "runner_source_sha256": runner_hash,
        "source_contract_digest": source["source_contract_digest"],
        "fallback_disposition": source["fallback_disposition"],
        **package_hashes,
        "route_matrix_digest": _digest(sanitized_rows),
        "screenshot_set_digest": _digest(sorted(screenshot_hashes)),
        "network_ledger_digest": _digest(network_ledgers),
        "route_count": len(EXPECTED_ROUTES),
        "viewport_count": len(EXPECTED_VIEWPORTS),
        "qa_matrix_count": expected_count,
        "payload_size_bytes": int(report.get("payload_size_bytes") or 0),
        "visual_review_required": canvas_present_count > 0,
        "canvas_present_count": canvas_present_count,
        "visual_review_rows": visual_review_rows,
        "app_attestation_digest": _digest(app),
    }, []


def _trusted_runner_capability(project_root: Path) -> tuple[dict[str, Any] | None, str]:
    """Read the fixed runner's no-write preflight before creating a session."""

    runner_path = project_root / "scripts" / RUNNER_PATH.name
    try:
        result = subprocess.run(
            ["node", str(runner_path), "--print-capability", "--json", "--project-root", str(project_root)],
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "trusted_runner_capability_unavailable"
    try:
        payload = json.loads(result.stdout)
    except Exception:
        return None, "trusted_runner_capability_output_invalid"
    fields = {
        "schema_version",
        "status",
        "mode",
        "platform",
        "packaged_app_present",
        "packaged_dom_driver_supported",
        "actual_packaged_tauri_launch_allowed",
        "production_nonce_attestation_supported",
        "challenge_transport",
        "public_raw_report_accepted",
        "writes_evidence",
        "creates_trust_key",
        "starts_servers",
        "opens_browser",
        "runtime_surface_required",
        "vite_or_browser_substitute_allowed",
        "runner_source_sha256",
        "blockers",
        "external_calls_triggered",
        "does_not_execute_trades",
    }
    if not (
        result.returncode == 0
        and isinstance(payload, Mapping)
        and set(payload) == fields
        and payload.get("schema_version") == RUNNER_SCHEMA
        and payload.get("mode") == "capability_preflight_no_launch"
        and payload.get("challenge_transport") == "inherited_fd_and_private_0700_session"
        and payload.get("public_raw_report_accepted") is False
        and payload.get("writes_evidence") is False
        and payload.get("creates_trust_key") is False
        and payload.get("starts_servers") is False
        and payload.get("opens_browser") is False
        and payload.get("runtime_surface_required") == "actual_packaged_tauri_react"
        and payload.get("vite_or_browser_substitute_allowed") is False
        and payload.get("runner_source_sha256") == _runner_source_sha256(project_root)
        and isinstance(payload.get("blockers"), list)
        and payload.get("external_calls_triggered") is False
        and payload.get("does_not_execute_trades") is True
    ):
        return None, "trusted_runner_capability_contract_invalid"
    ready = bool(
        payload.get("status") == "packaged_tauri_nonce_attestation_capable"
        and payload.get("packaged_app_present") is True
        and payload.get("packaged_dom_driver_supported") is True
        and payload.get("actual_packaged_tauri_launch_allowed") is True
        and payload.get("production_nonce_attestation_supported") is True
        and payload.get("blockers") == []
    )
    return dict(payload), "" if ready else "packaged_tauri_dom_or_nonce_attestation_unavailable"


def _build_runner_challenge(
    *,
    nonce: bytes,
    expected_head_full: str,
    package: Mapping[str, Any],
    source: Mapping[str, Any],
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    measured = tauri_package_verifier.measure_fixed_tauri_package_artifacts(project_root)
    identity_fields = (
        "artifact_set_sha256",
        "app_bundle_sha256",
        "app_executable_sha256",
        "dmg_sha256",
    )
    fixed_project_root = project_root.absolute()
    expected_paths = {
        "app_path": str(fixed_project_root / tauri_package_verifier.FIXED_APP_RELATIVE),
        "dmg_path": str(fixed_project_root / tauri_package_verifier.FIXED_DMG_RELATIVE),
        "app_executable_path": str(
            fixed_project_root
            / tauri_package_verifier.FIXED_APP_RELATIVE
            / "Contents"
            / "MacOS"
            / tauri_package_verifier.FIXED_EXECUTABLE_NAME
        ),
    }
    if (
        measured.get("blockers")
        or any(not _valid_sha256(measured.get(field)) for field in identity_fields)
        or any(package.get(field) != measured.get(field) for field in identity_fields)
        or any(measured.get(field) != expected for field, expected in expected_paths.items())
        or package.get("bundle_identifier") != measured.get("bundle_identifier")
        or package.get("bundle_version") != measured.get("bundle_version")
    ):
        raise ValueError("fixed_package_disk_identity_not_current")
    material = {
        "schema_version": CHALLENGE_SCHEMA,
        "challenge_id": secrets.token_hex(16),
        "nonce_digest": hashlib.sha256(nonce).hexdigest(),
        "created_at_utc": _utc_now(),
        "head_full": expected_head_full,
        "runner_source_sha256": source["runner_source_sha256"],
        "source_contract_digest": source["source_contract_digest"],
        "ordinary_component_map_digest": source["ordinary_component_map_digest"],
        "package_head_full": expected_head_full,
        "artifact_set_sha256": measured["artifact_set_sha256"],
        "app_bundle_sha256": measured["app_bundle_sha256"],
        "app_executable_sha256": measured["app_executable_sha256"],
        "dmg_sha256": measured["dmg_sha256"],
        "app_executable_path": measured["app_executable_path"],
        "app_bundle_path": measured["app_path"],
        "dmg_path": measured["dmg_path"],
        "bundle_identifier": measured["bundle_identifier"],
        "bundle_version": measured["bundle_version"],
        "expected_routes": [route for route, _component in EXPECTED_ROUTES],
        "expected_viewports": {
            name: {"width": dimensions[0], "height": dimensions[1]}
            for name, dimensions in EXPECTED_VIEWPORTS.items()
        },
        "production_required": True,
        "browser_or_vite_substitute_allowed": False,
        "external_calls_allowed": False,
    }
    return {**material, "challenge_digest": _digest(material)}


def _prepare_private_runner_session(
    evidence_root: Path,
    *,
    project_root: Path,
    challenge: Mapping[str, Any],
) -> tuple[Path | None, Path | None, Path | None, str]:
    sessions, blocker = _ensure_private_directory_below(
        evidence_root,
        SESSION_ROOT_RELATIVE,
        leaf_mode=0o700,
    )
    if sessions is None:
        return None, None, None, blocker or "trusted_runner_session_directory_insecure"
    try:
        session = Path(tempfile.mkdtemp(prefix="session-", dir=sessions))
        os.chmod(session, 0o700)
    except OSError:
        return None, None, None, "trusted_runner_session_create_failed"
    runner_bytes, blocker = _secure_read_file(
        project_root / "scripts" / RUNNER_PATH.name,
        max_bytes=2 * 1024 * 1024,
        require_single_link=False,
    )
    if runner_bytes is None or blocker or hashlib.sha256(runner_bytes).hexdigest() != challenge.get("runner_source_sha256"):
        shutil.rmtree(session, ignore_errors=True)
        return None, None, None, "trusted_runner_source_identity_invalid"
    runner_copy = session / "trusted_runner.mjs"
    challenge_path = session / "challenge.json"
    blocker = _atomic_private_file(runner_copy, runner_bytes, replace=False)
    if not blocker:
        blocker = _atomic_private_file(challenge_path, _canonical_bytes(challenge), replace=False)
    if blocker:
        shutil.rmtree(session, ignore_errors=True)
        return None, None, None, blocker
    return session, runner_copy, challenge_path, ""


def _execute_trusted_runner_session(
    *,
    session_root: Path,
    runner_executable: Path,
    challenge_path: Path,
    nonce: bytes,
    project_root: Path,
) -> tuple[dict[str, Any] | None, int, str]:
    """Spawn the exact private runner copy and pass the nonce only by pipe."""

    try:
        session_metadata = session_root.lstat()
    except OSError:
        return None, 0, "trusted_runner_session_directory_insecure"
    if not (
        stat.S_ISDIR(session_metadata.st_mode)
        and not stat.S_ISLNK(session_metadata.st_mode)
        and stat.S_IMODE(session_metadata.st_mode) == 0o700
        and _owned_by_current_user(session_metadata)
    ):
        return None, 0, "trusted_runner_session_directory_insecure"
    runner_data, runner_blocker = _secure_read_file(
        runner_executable,
        require_mode=0o600,
        max_bytes=2 * 1024 * 1024,
    )
    challenge_data, challenge_blocker = _secure_read_file(
        challenge_path,
        require_mode=0o600,
        max_bytes=64 * 1024,
    )
    if not (
        runner_executable.parent.resolve() == session_root.resolve()
        and runner_executable.name == "trusted_runner.mjs"
        and runner_data is not None
        and not runner_blocker
        and hashlib.sha256(runner_data).hexdigest() == _runner_source_sha256(project_root)
    ):
        return None, 0, "trusted_runner_session_executable_identity_invalid"
    if not (
        challenge_path.parent.resolve() == session_root.resolve()
        and challenge_path.name == "challenge.json"
        and challenge_data is not None
        and not challenge_blocker
    ):
        return None, 0, "trusted_runner_session_challenge_identity_invalid"
    try:
        challenge = json.loads(challenge_data)
    except Exception:
        return None, 0, "trusted_runner_session_challenge_invalid"
    if not isinstance(challenge, Mapping) or set(challenge) != CHALLENGE_FIELDS:
        return None, 0, "trusted_runner_session_challenge_invalid"
    node = shutil.which("node")
    if not node:
        return None, 0, "trusted_runner_node_runtime_unavailable"
    read_fd, write_fd = os.pipe()
    app_in_read_fd, app_in_write_fd = os.pipe()
    app_out_read_fd, app_out_write_fd = os.pipe()
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [
                str(Path(node).resolve()),
                str(runner_executable),
                "--trusted-session",
                "--challenge-file",
                str(challenge_path),
                "--nonce-fd",
                str(read_fd),
                "--app-in-read-fd",
                str(app_in_read_fd),
                "--app-in-write-fd",
                str(app_in_write_fd),
                "--app-out-read-fd",
                str(app_out_read_fd),
                "--app-out-write-fd",
                str(app_out_write_fd),
                "--project-root",
                str(project_root),
                "--json",
            ],
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(
                read_fd,
                app_in_read_fd,
                app_in_write_fd,
                app_out_read_fd,
                app_out_write_fd,
            ),
        )
        os.close(read_fd)
        read_fd = -1
        os.close(app_in_read_fd)
        app_in_read_fd = -1
        os.close(app_in_write_fd)
        app_in_write_fd = -1
        os.close(app_out_read_fd)
        app_out_read_fd = -1
        os.close(app_out_write_fd)
        app_out_write_fd = -1
        offset = 0
        while offset < len(nonce):
            offset += os.write(write_fd, nonce[offset:])
        os.close(write_fd)
        write_fd = -1
        stdout, _stderr = process.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()
            process.communicate()
        return None, int(process.pid if process is not None else 0), "trusted_runner_session_timeout"
    except OSError:
        if process is not None:
            process.kill()
            process.communicate()
        return None, int(process.pid if process is not None else 0), "trusted_runner_session_launch_failed"
    finally:
        if read_fd >= 0:
            os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)
        for descriptor in (
            app_in_read_fd,
            app_in_write_fd,
            app_out_read_fd,
            app_out_write_fd,
        ):
            if descriptor >= 0:
                os.close(descriptor)
    if process is None or process.returncode != 0:
        return (
            None,
            int(process.pid if process is not None else 0),
            _trusted_runner_failure_blocker(stdout),
        )
    try:
        payload = json.loads(stdout)
    except Exception:
        return None, process.pid, "trusted_runner_session_output_invalid"
    return (dict(payload), process.pid, "") if isinstance(payload, Mapping) else (None, process.pid, "trusted_runner_session_output_invalid")


def _trusted_runner_failure_blocker(stdout: str | None) -> str:
    """Return only an allowlisted child category; never expose runner output."""

    generic = "trusted_runner_session_failed_closed"
    try:
        payload = json.loads(stdout or "")
    except Exception:
        return generic
    expected_fields = {
        "schema_version",
        "status",
        "error_safe",
        "writes_evidence",
        "creates_trust_key",
        "external_calls_triggered",
        "does_not_execute_trades",
    }
    if not (
        isinstance(payload, Mapping)
        and set(payload) == expected_fields
        and payload.get("schema_version") == RUNNER_SCHEMA
        and payload.get("status") == "packaged_tauri_runner_failed_closed"
        and payload.get("writes_evidence") is False
        and payload.get("creates_trust_key") is False
        and payload.get("external_calls_triggered") is False
        and payload.get("does_not_execute_trades") is True
    ):
        return generic
    error_safe = payload.get("error_safe")
    if not isinstance(error_safe, str) or not error_safe.startswith(TRUSTED_RUNNER_FAILURE_PREFIX):
        return generic
    code = error_safe.removeprefix(TRUSTED_RUNNER_FAILURE_PREFIX)
    if code not in TRUSTED_RUNNER_SAFE_FAILURE_CODES:
        return generic
    return f"{generic}:{code}"


def _trust_paths(evidence_root: Path) -> tuple[Path, Path, Path]:
    directory = evidence_root.resolve() / TRUST_ROOT_RELATIVE
    return directory, directory / TRUST_KEY_NAME, directory / TRUST_STATE_NAME


def _event_root(evidence_root: Path) -> Path:
    return evidence_root.resolve() / EVENT_ROOT_RELATIVE


def _load_secret(evidence_root: Path) -> tuple[bytes | None, str]:
    directory, key_path, _state_path = _trust_paths(evidence_root)
    try:
        metadata = directory.lstat()
    except FileNotFoundError:
        return None, "trusted_runner_key_missing"
    except OSError:
        return None, "trusted_runner_key_corrupt"
    if not _directory_chain_secure(evidence_root, directory, leaf_mode=0o700):
        return None, "trusted_runner_directory_permissions_invalid"
    if not (
        stat.S_ISDIR(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) == 0o700
        and _owned_by_current_user(metadata)
    ):
        return None, "trusted_runner_directory_permissions_invalid"
    data, blocker = _secure_read_file(key_path, require_mode=0o600, max_bytes=TRUST_KEY_BYTES)
    if data is None or blocker or len(data) != TRUST_KEY_BYTES:
        return None, "trusted_runner_key_corrupt_or_insecure"
    try:
        entries = {entry.name for entry in directory.iterdir()}
    except OSError:
        return None, "trusted_runner_key_corrupt"
    if not entries.issubset({TRUST_KEY_NAME, TRUST_STATE_NAME, *LEGACY_TRUST_STATE_NAMES}) or TRUST_KEY_NAME not in entries:
        return None, "trusted_runner_directory_contains_unexpected_entries"
    return data, ""


def _atomic_private_file(path: Path, data: bytes, *, replace: bool) -> str:
    temporary = path.parent / f".{path.name}.{secrets.token_hex(12)}.tmp"
    descriptor = -1
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | int(getattr(os, "O_CLOEXEC", 0)) | int(getattr(os, "O_NOFOLLOW", 0))
        descriptor = os.open(temporary, flags, 0o600)
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path, follow_symlinks=False)
            temporary.unlink()
        directory_descriptor = os.open(path.parent, os.O_RDONLY | int(getattr(os, "O_DIRECTORY", 0)))
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        return ""
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        return "private_file_atomic_write_failed"


def _create_secret(evidence_root: Path) -> tuple[bytes | None, str]:
    directory, key_path, _state_path = _trust_paths(evidence_root)
    if key_path.exists():
        return _load_secret(evidence_root)
    ensured, blocker = _ensure_private_directory_below(
        evidence_root,
        TRUST_ROOT_RELATIVE,
        leaf_mode=0o700,
    )
    if ensured is None or ensured != directory:
        return None, blocker or "trusted_runner_directory_create_failed"
    secret = secrets.token_bytes(TRUST_KEY_BYTES)
    blocker = _atomic_private_file(key_path, secret, replace=False)
    return (None, blocker) if blocker else _load_secret(evidence_root)


def _event_mac(secret: bytes, event_without_mac: Mapping[str, Any]) -> str:
    return hmac.new(secret, _canonical_bytes(event_without_mac), hashlib.sha256).hexdigest()


def _visual_review_state_path(evidence_root: Path) -> Path:
    return evidence_root / VISUAL_REVIEW_STATE_RELATIVE


def _visual_review_row_valid(row: object, expected_sequence: int) -> bool:
    fields = {
        "sequence", "route", "component", "viewport", "screenshot_path", "screenshot_sha256",
        "pixel_width", "pixel_height",
    }
    return bool(
        isinstance(row, Mapping)
        and set(row) == fields
        and row.get("sequence") == expected_sequence
        and (row.get("route"), row.get("viewport"))
        in {(route, viewport) for route, _component in EXPECTED_ROUTES for viewport in EXPECTED_VIEWPORTS}
        and row.get("component") == dict(EXPECTED_ROUTES).get(row.get("route"))
        and isinstance(row.get("screenshot_path"), str)
        and _valid_sha256(row.get("screenshot_sha256"))
        and type(row.get("pixel_width")) is int
        and int(row.get("pixel_width") or 0) > 0
        and type(row.get("pixel_height")) is int
        and int(row.get("pixel_height") or 0) > 0
    )


def _persist_visual_review_manifest(
    evidence_root: Path,
    secret: bytes,
    derived: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    evidence_root = evidence_root.resolve()
    source_rows = derived.get("visual_review_rows") if isinstance(derived.get("visual_review_rows"), list) else []
    if not (
        derived.get("visual_review_required") is True
        and type(derived.get("canvas_present_count")) is int
        and int(derived.get("canvas_present_count") or 0) > 0
        and len(source_rows) == len(EXPECTED_ROUTES) * len(EXPECTED_VIEWPORTS)
    ):
        return None, "visual_review_not_required_or_matrix_missing"
    review_id = _digest(
        {
            field: derived.get(field)
            for field in (
                "head_full", "runner_source_sha256", "source_contract_digest", "artifact_set_sha256",
                "app_bundle_sha256", "app_executable_sha256", "dmg_sha256", "app_attestation_digest", "route_matrix_digest",
                "screenshot_set_digest", "network_ledger_digest", "canvas_present_count",
            )
        }
    )
    relative_root = VISUAL_REVIEW_PENDING_RELATIVE / review_id
    review_root, blocker = _ensure_private_directory_below(evidence_root, relative_root, leaf_mode=0o700)
    if review_root is None:
        return None, blocker or "visual_review_directory_insecure"
    screenshot_root, blocker = _ensure_private_directory_below(
        evidence_root, relative_root / "screenshots", leaf_mode=0o700
    )
    if screenshot_root is None:
        return None, blocker or "visual_review_screenshot_directory_insecure"
    durable_rows: list[dict[str, Any]] = []
    for index, source_row in enumerate(source_rows, 1):
        if not isinstance(source_row, Mapping):
            return None, "visual_review_source_row_invalid"
        source_path = Path(str(source_row.get("source_screenshot_path") or ""))
        data, read_blocker = _secure_read_file(source_path, require_mode=0o600, max_bytes=32 * 1024 * 1024)
        if data is None or read_blocker or hashlib.sha256(data).hexdigest() != source_row.get("screenshot_sha256"):
            return None, "visual_review_source_screenshot_invalid"
        filename = f"{index:02d}-{str(source_row.get('route') or '').removeprefix('#')}-{source_row.get('viewport')}.png"
        target = screenshot_root / filename
        if target.exists():
            existing, existing_blocker = _secure_read_file(target, require_mode=0o600, max_bytes=32 * 1024 * 1024)
            if existing is None or existing_blocker or existing != data:
                return None, "visual_review_existing_screenshot_mismatch"
        else:
            blocker = _atomic_private_file(target, data, replace=False)
            if blocker:
                return None, blocker
        row = {
            "sequence": index,
            "route": source_row.get("route"),
            "component": source_row.get("component"),
            "viewport": source_row.get("viewport"),
            "screenshot_path": str(target.relative_to(review_root)),
            "screenshot_sha256": source_row.get("screenshot_sha256"),
            "pixel_width": source_row.get("pixel_width"),
            "pixel_height": source_row.get("pixel_height"),
        }
        if not _visual_review_row_valid(row, index):
            return None, "visual_review_durable_row_invalid"
        durable_rows.append(row)
    base = {
        "schema_version": VISUAL_REVIEW_MANIFEST_SCHEMA,
        "status": "awaiting_visual_review",
        "review_id": review_id,
        "created_at_utc": _utc_now(),
        **{
            field: derived.get(field)
            for field in (
                "head_full", "runner_source_sha256", "source_contract_digest", "artifact_set_sha256",
                "app_bundle_sha256", "app_executable_sha256", "dmg_sha256", "app_attestation_digest", "route_matrix_digest",
                "screenshot_set_digest", "network_ledger_digest", "route_count", "viewport_count", "qa_matrix_count",
                "canvas_present_count",
            )
        },
        "screenshot_rows": durable_rows,
    }
    manifest_digest = _digest(base)
    material = {**base, "manifest_digest": manifest_digest}
    manifest = {**material, "manifest_mac": _event_mac(secret, material)}
    manifest_path = review_root / "manifest.json"
    if manifest_path.exists():
        observed, load_blocker = _load_visual_review_manifest(evidence_root, secret, review_id)
        return (observed, load_blocker) if observed is not None else (None, load_blocker)
    blocker = _atomic_private_file(manifest_path, _canonical_bytes(manifest), replace=False)
    return (None, blocker) if blocker else (manifest, "")


def _load_visual_review_manifest(
    evidence_root: Path, secret: bytes, review_id: str
) -> tuple[dict[str, Any] | None, str]:
    evidence_root = evidence_root.resolve()
    if not _valid_sha256(review_id):
        return None, "visual_review_id_invalid"
    review_root = evidence_root / VISUAL_REVIEW_PENDING_RELATIVE / review_id
    if not _directory_chain_secure(evidence_root, review_root, leaf_mode=0o700):
        return None, "visual_review_directory_insecure"
    data, blocker = _secure_read_file(review_root / "manifest.json", require_mode=0o600, max_bytes=128 * 1024)
    if data is None or blocker:
        return None, "visual_review_manifest_missing_or_insecure"
    try:
        manifest = json.loads(data)
    except Exception:
        return None, "visual_review_manifest_invalid"
    if not isinstance(manifest, Mapping) or set(manifest) != VISUAL_REVIEW_MANIFEST_FIELDS:
        return None, "visual_review_manifest_schema_invalid"
    material = dict(manifest)
    observed_mac = str(material.pop("manifest_mac", ""))
    digest_material = dict(material)
    observed_digest = str(digest_material.pop("manifest_digest", ""))
    rows = manifest.get("screenshot_rows") if isinstance(manifest.get("screenshot_rows"), list) else []
    if not (
        manifest.get("schema_version") == VISUAL_REVIEW_MANIFEST_SCHEMA
        and manifest.get("status") == "awaiting_visual_review"
        and manifest.get("review_id") == review_id
        and _valid_utc(manifest.get("created_at_utc"))
        and _normalize_head(manifest.get("head_full")) == manifest.get("head_full")
        and all(
            _valid_sha256(manifest.get(field))
            for field in (
                "runner_source_sha256", "source_contract_digest", "artifact_set_sha256",
                "app_bundle_sha256", "app_executable_sha256", "dmg_sha256",
                "app_attestation_digest", "route_matrix_digest", "screenshot_set_digest",
                "network_ledger_digest",
            )
        )
        and observed_digest == _digest(digest_material)
        and _valid_sha256(observed_mac)
        and hmac.compare_digest(observed_mac, _event_mac(secret, material))
        and len(rows) == len(EXPECTED_ROUTES) * len(EXPECTED_VIEWPORTS)
        and all(_visual_review_row_valid(row, index) for index, row in enumerate(rows, 1))
        and len({(row.get("route"), row.get("viewport")) for row in rows}) == len(rows)
        and manifest.get("screenshot_set_digest")
        == _digest(sorted(str(row.get("screenshot_sha256") or "") for row in rows))
        and all(
            len(
                {
                    (row.get("pixel_width"), row.get("pixel_height"))
                    for row in rows
                    if row.get("viewport") == viewport
                }
            )
            == 1
            for viewport in EXPECTED_VIEWPORTS
        )
        and type(manifest.get("canvas_present_count")) is int
        and int(manifest.get("canvas_present_count") or 0) > 0
    ):
        return None, "visual_review_manifest_authentication_failed"
    for row in rows:
        screenshot = _path_under(review_root, row.get("screenshot_path"), required_prefix=Path("screenshots"))
        screenshot_data, screenshot_blocker = _secure_read_file(screenshot, require_mode=0o600, max_bytes=32 * 1024 * 1024) if screenshot else (None, "invalid")
        if not (
            screenshot_data is not None
            and not screenshot_blocker
            and hashlib.sha256(screenshot_data).hexdigest() == row.get("screenshot_sha256")
            and _png_bytes_valid(screenshot_data, (int(row["pixel_width"]), int(row["pixel_height"])))
        ):
            return None, "visual_review_screenshot_authentication_failed"
    return dict(manifest), ""


def _state_material(sequence_no: int, event_id: str, event_mac: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA,
        "sequence_no": sequence_no,
        "event_id": event_id,
        "event_mac": event_mac,
    }


def _load_state(evidence_root: Path, secret: bytes) -> tuple[dict[str, Any] | None, str]:
    _directory, _key_path, state_path = _trust_paths(evidence_root)
    data, blocker = _secure_read_file(state_path, require_mode=0o600, max_bytes=4096)
    if data is None:
        return None, "trusted_runner_state_missing_or_insecure"
    try:
        state = json.loads(data)
    except Exception:
        return None, "trusted_runner_state_corrupt"
    fields = {"schema_version", "sequence_no", "event_id", "event_mac", "state_mac"}
    if not isinstance(state, Mapping) or set(state) != fields:
        return None, "trusted_runner_state_corrupt"
    material = _state_material(state.get("sequence_no"), state.get("event_id"), state.get("event_mac"))
    if not (
        state.get("schema_version") == STATE_SCHEMA
        and type(state.get("sequence_no")) is int
        and int(state["sequence_no"]) > 0
        and _valid_sha256(state.get("event_id"))
        and _valid_sha256(state.get("event_mac"))
        and _valid_sha256(state.get("state_mac"))
        and hmac.compare_digest(str(state["state_mac"]), _event_mac(secret, material))
    ):
        return None, "trusted_runner_state_corrupt"
    return dict(state), ""


def _write_state(evidence_root: Path, secret: bytes, event: Mapping[str, Any]) -> str:
    _directory, _key_path, state_path = _trust_paths(evidence_root)
    material = _state_material(int(event["sequence_no"]), str(event["event_id"]), str(event["event_mac"]))
    payload = {**material, "state_mac": _event_mac(secret, material)}
    return _atomic_private_file(state_path, _canonical_bytes(payload), replace=True)


def _load_event_chain(evidence_root: Path, secret: bytes) -> tuple[list[dict[str, Any]], str]:
    root = _event_root(evidence_root)
    try:
        metadata = root.lstat()
    except FileNotFoundError:
        return [], "trusted_runner_event_chain_missing"
    except OSError:
        return [], "trusted_runner_event_chain_corrupt"
    if not _directory_chain_secure(evidence_root, root, leaf_mode=0o700):
        return [], "trusted_runner_event_directory_insecure"
    if not (
        stat.S_ISDIR(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) == 0o700
        and _owned_by_current_user(metadata)
    ):
        return [], "trusted_runner_event_directory_insecure"
    paths = sorted(root.iterdir())
    if not paths or any(path.name != f"{index:08d}.json" for index, path in enumerate(paths, 1)):
        return [], "trusted_runner_event_sequence_invalid"
    events: list[dict[str, Any]] = []
    previous_mac = ""
    for sequence_no, path in enumerate(paths, 1):
        data, blocker = _secure_read_file(path, require_mode=0o600, max_bytes=64 * 1024)
        if data is None or blocker:
            return [], "trusted_runner_event_file_insecure"
        try:
            event = json.loads(data)
        except Exception:
            return [], "trusted_runner_event_json_invalid"
        if not isinstance(event, Mapping) or set(event) != EVENT_FIELDS:
            return [], "trusted_runner_event_schema_invalid"
        material = dict(event)
        observed_mac = str(material.pop("event_mac", ""))
        id_material = dict(material)
        observed_id = str(id_material.pop("event_id", ""))
        if not (
            event.get("schema_version") == EVENT_SCHEMA
            and event.get("status") == "streamlit_primary_retirement_direct_evidence_sealed"
            and type(event.get("sequence_no")) is int
            and event.get("sequence_no") == sequence_no
            and event.get("previous_event_mac") == previous_mac
            and _normalize_head(event.get("head_full")) == event.get("head_full")
            and all(
                _valid_sha256(event.get(field))
                for field in (
                    "runner_source_sha256",
                    "source_contract_digest",
                    "artifact_set_sha256",
                    "app_bundle_sha256",
                    "app_executable_sha256",
                    "dmg_sha256",
                    "route_matrix_digest",
                    "screenshot_set_digest",
                    "network_ledger_digest",
                )
            )
            and type(event.get("route_count")) is int
            and event.get("route_count") == len(EXPECTED_ROUTES)
            and type(event.get("viewport_count")) is int
            and event.get("viewport_count") == len(EXPECTED_VIEWPORTS)
            and type(event.get("qa_matrix_count")) is int
            and event.get("qa_matrix_count") == len(EXPECTED_ROUTES) * len(EXPECTED_VIEWPORTS)
            and isinstance(event.get("visual_review_required"), bool)
            and type(event.get("canvas_present_count")) is int
            and int(event.get("canvas_present_count") or 0) >= 0
            and _valid_sha256(event.get("screenshot_manifest_digest"))
            and (
                (
                    event.get("visual_review_required") is True
                    and int(event.get("canvas_present_count") or 0) > 0
                    and _valid_sha256(event.get("visual_review_event_id"))
                )
                or (
                    event.get("visual_review_required") is False
                    and event.get("canvas_present_count") == 0
                    and event.get("visual_review_event_id") == ""
                )
            )
            and _valid_sha256(observed_id)
            and observed_id == _digest(id_material)
            and _valid_sha256(observed_mac)
            and hmac.compare_digest(observed_mac, _event_mac(secret, material))
            and _valid_utc(event.get("recorded_at_utc"))
            and event.get("fallback_disposition") == "admin_debug_only_retained"
            and event.get("external_calls_triggered") is False
            and event.get("does_not_execute_trades") is True
            and event.get("contains_secret") is False
        ):
            return [], "trusted_runner_event_authentication_failed"
        events.append(dict(event))
        previous_mac = observed_mac
    state, blocker = _load_state(evidence_root, secret)
    latest = events[-1]
    if blocker or state is None or not (
        state.get("sequence_no") == latest.get("sequence_no")
        and state.get("event_id") == latest.get("event_id")
        and state.get("event_mac") == latest.get("event_mac")
    ):
        return [], blocker or "trusted_runner_terminal_state_mismatch"
    return events, ""


def _write_visual_review_state(evidence_root: Path, secret: bytes, event: Mapping[str, Any]) -> str:
    evidence_root = evidence_root.resolve()
    path = _visual_review_state_path(evidence_root)
    material = {
        "schema_version": VISUAL_REVIEW_STATE_SCHEMA,
        "sequence_no": event.get("sequence_no"),
        "event_id": event.get("event_id"),
        "event_mac": event.get("event_mac"),
    }
    payload = {**material, "state_mac": _event_mac(secret, material)}
    return _atomic_private_file(path, _canonical_bytes(payload), replace=True)


def _load_visual_review_event_chain(
    evidence_root: Path, secret: bytes
) -> tuple[list[dict[str, Any]], str]:
    evidence_root = evidence_root.resolve()
    root = evidence_root / VISUAL_REVIEW_EVENT_ROOT_RELATIVE
    if not _directory_chain_secure(evidence_root, root, leaf_mode=0o700):
        return [], "visual_review_event_directory_insecure"
    try:
        paths = sorted(root.iterdir())
    except OSError:
        return [], "visual_review_event_chain_missing"
    if not paths or any(path.name != f"{index:08d}.json" for index, path in enumerate(paths, 1)):
        return [], "visual_review_event_sequence_invalid"
    events: list[dict[str, Any]] = []
    previous_mac = ""
    for sequence_no, path in enumerate(paths, 1):
        data, blocker = _secure_read_file(path, require_mode=0o600, max_bytes=128 * 1024)
        if data is None or blocker:
            return [], "visual_review_event_file_insecure"
        try:
            event = json.loads(data)
        except Exception:
            return [], "visual_review_event_json_invalid"
        if not isinstance(event, Mapping) or set(event) != VISUAL_REVIEW_EVENT_FIELDS:
            return [], "visual_review_event_schema_invalid"
        material = dict(event)
        observed_mac = str(material.pop("event_mac", ""))
        id_material = dict(material)
        observed_id = str(id_material.pop("event_id", ""))
        screenshots = event.get("reviewed_screenshots") if isinstance(event.get("reviewed_screenshots"), list) else []
        if not (
            event.get("schema_version") == VISUAL_REVIEW_EVENT_SCHEMA
            and event.get("status") == "visual_review_approved_by_user"
            and event.get("sequence_no") == sequence_no
            and event.get("previous_event_mac") == previous_mac
            and _normalize_head(event.get("head_full")) == event.get("head_full")
            and _valid_utc(event.get("approved_at_utc"))
            and all(
                _valid_sha256(event.get(field))
                for field in (
                    "review_id", "manifest_digest", "artifact_set_sha256", "app_bundle_sha256",
                    "app_executable_sha256", "dmg_sha256", "app_attestation_digest", "route_matrix_digest", "screenshot_set_digest",
                )
            )
            and event.get("screenshot_count") == len(EXPECTED_ROUTES) * len(EXPECTED_VIEWPORTS)
            and len(screenshots) == event.get("screenshot_count")
            and all(_visual_review_row_valid(row, index) for index, row in enumerate(screenshots, 1))
            and type(event.get("canvas_present_count")) is int
            and int(event.get("canvas_present_count") or 0) > 0
            and event.get("approved_by_user") is True
            and event.get("no_legacy_surface") is True
            and event.get("no_streamlit_surface") is True
            and event.get("no_admin_surface") is True
            and observed_id == _digest(id_material)
            and _valid_sha256(observed_mac)
            and hmac.compare_digest(observed_mac, _event_mac(secret, material))
        ):
            return [], "visual_review_event_authentication_failed"
        events.append(dict(event))
        previous_mac = observed_mac
    state_data, blocker = _secure_read_file(
        _visual_review_state_path(evidence_root), require_mode=0o600, max_bytes=4096
    )
    try:
        state = json.loads(state_data) if state_data is not None and not blocker else None
    except Exception:
        state = None
    latest = events[-1]
    fields = {"schema_version", "sequence_no", "event_id", "event_mac", "state_mac"}
    if not isinstance(state, Mapping) or set(state) != fields:
        return [], "visual_review_state_missing_or_corrupt"
    material = {field: state.get(field) for field in ("schema_version", "sequence_no", "event_id", "event_mac")}
    if not (
        state.get("schema_version") == VISUAL_REVIEW_STATE_SCHEMA
        and state.get("sequence_no") == latest.get("sequence_no")
        and state.get("event_id") == latest.get("event_id")
        and state.get("event_mac") == latest.get("event_mac")
        and _valid_sha256(state.get("state_mac"))
        and hmac.compare_digest(str(state.get("state_mac")), _event_mac(secret, material))
    ):
        return [], "visual_review_terminal_state_mismatch"
    return events, ""


def _public_summary(
    *,
    ready: bool,
    expected_head_full: str,
    event: Mapping[str, Any] | None,
    blockers: list[str],
    pending_visual_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = event if isinstance(event, Mapping) else {}
    pending = pending_visual_review if isinstance(pending_visual_review, Mapping) else {}
    awaiting_visual = not ready and bool(pending)
    return {
        "schema_version": "streamlit_primary_retirement_validation.v2",
        "status": (
            "streamlit_primary_retirement_direct_evidence_verified"
            if ready
            else "awaiting_visual_review" if awaiting_visual else "streamlit_primary_retirement_blocked"
        ),
        "streamlit_primary_retired": ready,
        "head_full": expected_head_full,
        "fallback_disposition": source.get("fallback_disposition") or "missing",
        "route_count": int(source.get("route_count") or 0) if ready else 0,
        "viewport_count": int(source.get("viewport_count") or 0) if ready else 0,
        "qa_matrix_count": int(source.get("qa_matrix_count") or 0) if ready else 0,
        "artifact_set_sha256": (source.get("artifact_set_sha256") or "") if ready else "",
        "source_contract_digest": (source.get("source_contract_digest") or "") if ready else "",
        "route_matrix_digest": (source.get("route_matrix_digest") or "") if ready else "",
        "visual_review_required": awaiting_visual or source.get("visual_review_required") is True,
        "visual_review_id": pending.get("review_id") or source.get("visual_review_event_id") or "",
        "visual_review_screenshot_rows": pending.get("screenshot_rows") if awaiting_visual else [],
        "blockers": sorted(set(blockers)),
        "trust_boundary": "recorder_spawned_nonce_bound_packaged_runner_same_os_account_trusted_public_files_cannot_self_seal",
        "read_only": True,
        "writes_storage": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }


def _seal_primary_event(
    evidence_root: Path,
    secret: bytes,
    derived: Mapping[str, Any],
    *,
    visual_review_event_id: str = "",
    screenshot_manifest_digest: str,
) -> tuple[dict[str, Any] | None, str]:
    event_root = _event_root(evidence_root)
    ensured, blocker = _ensure_private_directory_below(evidence_root, EVENT_ROOT_RELATIVE, leaf_mode=0o700)
    if ensured is None or ensured != event_root:
        return None, blocker or "trusted_runner_event_directory_insecure"
    existing_paths = sorted(event_root.iterdir())
    events: list[dict[str, Any]] = []
    if existing_paths:
        events, blocker = _load_event_chain(evidence_root, secret)
        if blocker:
            return None, blocker
    latest = events[-1] if events else None
    semantic_fields = (
        "head_full", "runner_source_sha256", "source_contract_digest", "fallback_disposition",
        "artifact_set_sha256", "app_bundle_sha256", "app_executable_sha256", "dmg_sha256", "route_matrix_digest",
        "screenshot_set_digest", "network_ledger_digest", "route_count", "viewport_count", "qa_matrix_count",
    )
    visual_required = bool(derived.get("visual_review_required"))
    semantic = {
        **{field: derived.get(field) for field in semantic_fields},
        "visual_review_required": visual_required,
        "visual_review_event_id": visual_review_event_id if visual_required else "",
        "canvas_present_count": int(derived.get("canvas_present_count") or 0),
        "screenshot_manifest_digest": screenshot_manifest_digest,
    }
    if latest is not None and all(latest.get(field) == value for field, value in semantic.items()):
        return latest, ""
    sequence_no = len(events) + 1
    id_material = {
        "schema_version": EVENT_SCHEMA,
        "status": "streamlit_primary_retirement_direct_evidence_sealed",
        "sequence_no": sequence_no,
        "previous_event_mac": str(latest.get("event_mac") or "") if latest else "",
        "recorded_at_utc": _utc_now(),
        **semantic,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }
    event_id = _digest(id_material)
    material = {**id_material, "event_id": event_id}
    event = {**material, "event_mac": _event_mac(secret, material)}
    blocker = _atomic_private_file(
        event_root / f"{sequence_no:08d}.json", _canonical_bytes(event), replace=False
    )
    if blocker:
        return None, blocker
    blocker = _write_state(evidence_root, secret, event)
    if blocker:
        return None, blocker
    verified, blocker = _load_event_chain(evidence_root, secret)
    return (verified[-1], "") if verified and not blocker else (None, blocker or "trusted_runner_event_chain_missing")


def validate_streamlit_primary_retirement(
    evidence_root: Path | str = EVIDENCE_ROOT,
    *,
    expected_head_full: str,
    tauri_package_verification: Mapping[str, Any] | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """GET-safe validation: never creates keys, events, state, or evidence."""

    root = Path(evidence_root).expanduser().resolve()
    expected = _normalize_head(expected_head_full)
    actual = _git_head_full(project_root)
    blockers: list[str] = []
    if not expected or actual != expected:
        blockers.append("actual_git_head_does_not_match_expected")
    if expected and not _trusted_sources_match_commit(project_root, expected):
        blockers.append("trusted_runner_sources_not_exactly_bound_to_head")
    secret, blocker = _load_secret(root)
    if secret is None:
        blockers.append(blocker or "trusted_runner_key_missing")
        return _public_summary(ready=False, expected_head_full=expected, event=None, blockers=blockers)
    events, blocker = _load_event_chain(root, secret)
    if blocker or not events:
        blockers.append(blocker or "trusted_runner_event_chain_missing")
        return _public_summary(ready=False, expected_head_full=expected, event=None, blockers=blockers)
    latest = events[-1]
    package = validate_tauri_production_package(
        root, expected_head_full=expected, write_manifest=False
    )
    if isinstance(tauri_package_verification, Mapping):
        supplied_package_fields = (
            "production_package_complete",
            "head_full",
            "artifact_set_sha256",
            "app_bundle_sha256",
            "app_executable_sha256",
            "dmg_sha256",
        )
        if any(
            tauri_package_verification.get(field) != package.get(field)
            for field in supplied_package_fields
        ):
            blockers.append("caller_package_verification_not_fresh_fixed_disk_identity")
    if latest.get("head_full") != expected:
        blockers.append("sealed_runner_event_head_not_current")
    if not (
        package.get("production_package_complete") is True
        and _normalize_head(package.get("head_full")) == expected
        and latest.get("artifact_set_sha256") == package.get("artifact_set_sha256")
        and latest.get("app_bundle_sha256") == package.get("app_bundle_sha256")
        and latest.get("app_executable_sha256") == package.get("app_executable_sha256")
        and latest.get("dmg_sha256") == package.get("dmg_sha256")
    ):
        blockers.append("sealed_runner_event_package_binding_not_current")
    source, source_blocker = _source_contract(project_root)
    if source is None or latest.get("source_contract_digest") != source.get("source_contract_digest"):
        blockers.append(source_blocker or "sealed_runner_event_source_contract_not_current")
    if latest.get("visual_review_required") is True:
        visual_events, visual_blocker = _load_visual_review_event_chain(root, secret)
        visual = next(
            (event for event in visual_events if event.get("event_id") == latest.get("visual_review_event_id")),
            None,
        )
        visual_manifest, manifest_blocker = (
            _load_visual_review_manifest(root, secret, str(visual.get("review_id") or ""))
            if visual is not None
            else (None, "visual_review_manifest_missing")
        )
        if visual_blocker or manifest_blocker or visual is None or visual_manifest is None or not (
            visual.get("head_full") == expected
            and visual.get("artifact_set_sha256") == latest.get("artifact_set_sha256")
            and visual.get("app_bundle_sha256") == latest.get("app_bundle_sha256")
            and visual.get("app_executable_sha256") == latest.get("app_executable_sha256")
            and visual.get("dmg_sha256") == latest.get("dmg_sha256")
            and visual.get("route_matrix_digest") == latest.get("route_matrix_digest")
            and visual.get("screenshot_set_digest") == latest.get("screenshot_set_digest")
            and visual.get("manifest_digest") == latest.get("screenshot_manifest_digest")
            and visual_manifest.get("manifest_digest") == visual.get("manifest_digest")
            and visual_manifest.get("screenshot_rows") == visual.get("reviewed_screenshots")
        ):
            blockers.append(visual_blocker or manifest_blocker or "sealed_visual_review_event_not_current")
    ready = not blockers
    return _public_summary(
        ready=ready,
        expected_head_full=expected,
        event=latest if ready else None,
        blockers=blockers,
    )


def record_streamlit_primary_retirement_attestation(
    evidence_root: Path | str = EVIDENCE_ROOT,
    *,
    expected_head_full: str,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Run one private nonce challenge and seal only actual packaged evidence."""

    root = Path(evidence_root).expanduser().resolve()
    expected = _normalize_head(expected_head_full)
    actual = _git_head_full(project_root)
    if not expected or actual != expected:
        return _public_summary(
            ready=False,
            expected_head_full=expected,
            event=None,
            blockers=["actual_git_head_does_not_match_expected"],
        )
    if not _trusted_sources_match_commit(project_root, expected):
        return _public_summary(
            ready=False,
            expected_head_full=expected,
            event=None,
            blockers=["trusted_runner_sources_not_exactly_bound_to_head"],
        )
    package = validate_tauri_production_package(root, expected_head_full=expected, write_manifest=False)
    package_hashes = (
        package.get("artifact_set_sha256"),
        package.get("app_bundle_sha256"),
        package.get("app_executable_sha256"),
        package.get("dmg_sha256"),
    )
    if not (
        package.get("production_package_complete") is True
        and _normalize_head(package.get("head_full")) == expected
        and all(_valid_sha256(value) for value in package_hashes)
    ):
        return _public_summary(
            ready=False,
            expected_head_full=expected,
            event=None,
            blockers=["formal_package_verifier_binding_invalid"],
        )
    source, source_blocker = _source_contract(project_root)
    if source is None:
        return _public_summary(
            ready=False,
            expected_head_full=expected,
            event=None,
            blockers=[source_blocker or "source_contract_invalid"],
        )
    _capability, capability_blocker = _trusted_runner_capability(project_root)
    if capability_blocker:
        return _public_summary(
            ready=False,
            expected_head_full=expected,
            event=None,
            blockers=[capability_blocker],
        )
    nonce = secrets.token_bytes(32)
    try:
        challenge = _build_runner_challenge(
            nonce=nonce,
            expected_head_full=expected,
            package=package,
            source=source,
            project_root=project_root,
        )
    except ValueError:
        return _public_summary(
            ready=False,
            expected_head_full=expected,
            event=None,
            blockers=["fixed_package_disk_identity_not_current"],
        )
    session_root, runner_executable, challenge_path, blocker = _prepare_private_runner_session(
        root,
        project_root=project_root,
        challenge=challenge,
    )
    if session_root is None or runner_executable is None or challenge_path is None:
        return _public_summary(
            ready=False,
            expected_head_full=expected,
            event=None,
            blockers=[blocker or "trusted_runner_session_create_failed"],
        )
    pending_manifest: dict[str, Any] | None = None
    secret: bytes | None = None
    try:
        attestation, runner_pid, blocker = _execute_trusted_runner_session(
            session_root=session_root,
            runner_executable=runner_executable,
            challenge_path=challenge_path,
            nonce=nonce,
            project_root=project_root,
        )
        if attestation is None:
            derived, blockers = None, [blocker or "trusted_runner_session_failed_closed"]
        else:
            derived, blockers = _validate_trusted_runner_attestation(
                session_root,
                attestation=attestation,
                challenge=challenge,
                nonce=nonce,
                expected_runner_pid=runner_pid,
                expected_runner_executable=runner_executable,
                expected_head_full=expected,
                package=package,
                project_root=project_root,
            )
        if derived is not None and derived.get("visual_review_required") is True:
            secret, secret_blocker = _load_secret(root)
            if secret is None and secret_blocker == "trusted_runner_key_missing":
                secret, secret_blocker = _create_secret(root)
            if secret is None:
                derived, blockers = None, [secret_blocker]
            else:
                pending_manifest, manifest_blocker = _persist_visual_review_manifest(root, secret, derived)
                if pending_manifest is None:
                    derived, blockers = None, [manifest_blocker]
    finally:
        nonce = b""
        shutil.rmtree(session_root, ignore_errors=True)
    if derived is None:
        return _public_summary(ready=False, expected_head_full=expected, event=None, blockers=blockers)
    if pending_manifest is not None:
        review_root = root / VISUAL_REVIEW_PENDING_RELATIVE / str(pending_manifest.get("review_id") or "")
        public_manifest = dict(pending_manifest)
        public_manifest["screenshot_rows"] = [
            {**dict(row), "screenshot_path": str(review_root / str(row.get("screenshot_path") or ""))}
            for row in pending_manifest.get("screenshot_rows", [])
            if isinstance(row, Mapping)
        ]
        return _public_summary(
            ready=False,
            expected_head_full=expected,
            event=None,
            blockers=["manual_visual_review_required"],
            pending_visual_review=public_manifest,
        )
    secret, blocker = _load_secret(root)
    if secret is None and blocker == "trusted_runner_key_missing":
        secret, blocker = _create_secret(root)
    if secret is None:
        return _public_summary(ready=False, expected_head_full=expected, event=None, blockers=[blocker])
    event, blocker = _seal_primary_event(
        root,
        secret,
        derived,
        screenshot_manifest_digest=_digest(
            [
                {key: value for key, value in dict(row).items() if key != "source_screenshot_path"}
                for row in (derived.get("visual_review_rows") or [])
                if isinstance(row, Mapping)
            ]
        ),
    )
    return _public_summary(
        ready=event is not None and not blocker,
        expected_head_full=expected,
        event=event,
        blockers=[blocker] if blocker else [],
    )


def record_streamlit_primary_retirement_visual_review(
    evidence_root: Path | str = EVIDENCE_ROOT,
    *,
    expected_head_full: str,
    review_id: str,
    approved_by_user: bool,
    no_legacy_surface: bool,
    no_streamlit_surface: bool,
    no_admin_surface: bool,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Seal a narrow human visual decision over one trusted 12-shot canvas manifest."""

    root = Path(evidence_root).expanduser().resolve()
    expected = _normalize_head(expected_head_full)
    if not (
        expected
        and _git_head_full(project_root) == expected
        and _trusted_sources_match_commit(project_root, expected)
    ):
        return _public_summary(
            ready=False, expected_head_full=expected, event=None,
            blockers=["visual_review_head_or_trusted_source_not_current"],
        )
    if not (
        type(approved_by_user) is bool and approved_by_user is True
        and type(no_legacy_surface) is bool and no_legacy_surface is True
        and type(no_streamlit_surface) is bool and no_streamlit_surface is True
        and type(no_admin_surface) is bool and no_admin_surface is True
    ):
        return _public_summary(
            ready=False, expected_head_full=expected, event=None,
            blockers=["literal_user_visual_review_approval_and_surface_flags_required"],
        )
    secret, blocker = _load_secret(root)
    if secret is None:
        return _public_summary(
            ready=False, expected_head_full=expected, event=None,
            blockers=[blocker or "trusted_runner_key_missing"],
        )
    manifest, blocker = _load_visual_review_manifest(root, secret, review_id)
    if manifest is None:
        return _public_summary(
            ready=False, expected_head_full=expected, event=None,
            blockers=[blocker or "visual_review_manifest_missing"],
        )
    package = validate_tauri_production_package(root, expected_head_full=expected, write_manifest=False)
    source, source_blocker = _source_contract(project_root)
    if not (
        package.get("production_package_complete") is True
        and package.get("head_full") == expected == manifest.get("head_full")
        and all(
            manifest.get(field) == package.get(field)
            for field in ("artifact_set_sha256", "app_bundle_sha256", "app_executable_sha256", "dmg_sha256")
        )
        and source is not None
        and manifest.get("runner_source_sha256") == _runner_source_sha256(project_root)
        and manifest.get("source_contract_digest") == source.get("source_contract_digest")
    ):
        return _public_summary(
            ready=False, expected_head_full=expected, event=None,
            blockers=[source_blocker or "visual_review_manifest_package_or_source_not_current"],
        )
    event_root, blocker = _ensure_private_directory_below(
        root, VISUAL_REVIEW_EVENT_ROOT_RELATIVE, leaf_mode=0o700
    )
    if event_root is None:
        return _public_summary(
            ready=False, expected_head_full=expected, event=None,
            blockers=[blocker or "visual_review_event_directory_insecure"],
        )
    paths = sorted(event_root.iterdir())
    events: list[dict[str, Any]] = []
    if paths:
        events, blocker = _load_visual_review_event_chain(root, secret)
        if blocker:
            return _public_summary(
                ready=False, expected_head_full=expected, event=None, blockers=[blocker]
            )
    latest = events[-1] if events else None
    if latest is None or latest.get("review_id") != review_id:
        sequence_no = len(events) + 1
        id_material = {
            "schema_version": VISUAL_REVIEW_EVENT_SCHEMA,
            "status": "visual_review_approved_by_user",
            "sequence_no": sequence_no,
            "previous_event_mac": str(latest.get("event_mac") or "") if latest else "",
            "head_full": expected,
            "approved_at_utc": _utc_now(),
            "review_id": review_id,
            "manifest_digest": manifest["manifest_digest"],
            "artifact_set_sha256": manifest["artifact_set_sha256"],
            "app_bundle_sha256": manifest["app_bundle_sha256"],
            "app_executable_sha256": manifest["app_executable_sha256"],
            "dmg_sha256": manifest["dmg_sha256"],
            "app_attestation_digest": manifest["app_attestation_digest"],
            "route_matrix_digest": manifest["route_matrix_digest"],
            "screenshot_set_digest": manifest["screenshot_set_digest"],
            "screenshot_count": len(manifest["screenshot_rows"]),
            "reviewed_screenshots": manifest["screenshot_rows"],
            "canvas_present_count": manifest["canvas_present_count"],
            "approved_by_user": True,
            "no_legacy_surface": True,
            "no_streamlit_surface": True,
            "no_admin_surface": True,
        }
        event_id = _digest(id_material)
        material = {**id_material, "event_id": event_id}
        latest = {**material, "event_mac": _event_mac(secret, material)}
        blocker = _atomic_private_file(
            event_root / f"{sequence_no:08d}.json", _canonical_bytes(latest), replace=False
        )
        if not blocker:
            blocker = _write_visual_review_state(root, secret, latest)
        if blocker:
            return _public_summary(
                ready=False, expected_head_full=expected, event=None, blockers=[blocker]
            )
        events, blocker = _load_visual_review_event_chain(root, secret)
        latest = events[-1] if events and not blocker else None
    if latest is None or latest.get("review_id") != review_id:
        return _public_summary(
            ready=False, expected_head_full=expected, event=None,
            blockers=[blocker or "visual_review_event_not_current"],
        )
    derived = {
        field: manifest.get(field)
        for field in (
            "head_full", "runner_source_sha256", "source_contract_digest", "artifact_set_sha256",
            "app_bundle_sha256", "app_executable_sha256", "dmg_sha256", "route_matrix_digest", "screenshot_set_digest",
            "network_ledger_digest", "route_count", "viewport_count", "qa_matrix_count", "canvas_present_count",
        )
    }
    derived.update(
        {
            "fallback_disposition": source["fallback_disposition"],
            "visual_review_required": True,
        }
    )
    primary, blocker = _seal_primary_event(
        root,
        secret,
        derived,
        visual_review_event_id=str(latest.get("event_id") or ""),
        screenshot_manifest_digest=str(manifest.get("manifest_digest") or ""),
    )
    return _public_summary(
        ready=primary is not None and not blocker,
        expected_head_full=expected,
        event=primary,
        blockers=[blocker] if blocker else [],
    )
