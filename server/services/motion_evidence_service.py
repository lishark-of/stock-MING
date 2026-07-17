"""Fail-closed LTG-14 current-head motion evidence validation.

The explicit browser runner owns a versioned HMAC key, an append-only event
chain, and an independent terminal high-water anchor.  This reader never
creates or repairs evidence.  It opens every trusted file with ``O_NOFOLLOW``
and recomputes the pinned six-route/four-viewport matrix, performance budgets,
network silence, PNG pixels, source/build identity, report digest, chain MAC,
and terminal anchor instead of trusting runner status booleans.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import struct
import subprocess
import zlib
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


REPORT_SCHEMA = "command_center_3_motion_browser_qa_result.v7"
TRACE_SCHEMA = "command_center_3_motion_browser_performance_trace.v6"
STATE_SCHEMA = "command_center_3_motion_runner_attestation_state.v3"
EVENT_SCHEMA = "command_center_3_motion_runner_attestation_event.v3"
ANCHOR_SCHEMA = "command_center_3_motion_runner_high_water_anchor.v2"
IDENTITY_SCHEMA = "command_center_3_motion_runner_installation_identity.v1"
TERMINAL_SCHEMA = "command_center_3_motion_runner_terminal_high_water.v1"
DIST_MANIFEST_SCHEMA = "command_center_3_motion_dist_manifest.v1"
SERVICE_IDENTITY_SCHEMA = "command_center_3_motion_frontend_service_identity.v1"
PACKAGE_BINDING_SCHEMA = "command_center_3_motion_package_binding.v1"
FASTAPI_IDENTITY_SCHEMA = "command_center_3_motion_fastapi_service_identity.v1"
TRUST_DIR_NAME = ".runner_attestation_v4"
KEY_FILE_NAME = "runner.key"
STATE_FILE_NAME = "state.json"
ANCHOR_FILE_NAME = "high_water.json"
IDENTITY_FILE_NAME = ".runner_installation_identity.json"
TERMINAL_FILE_NAME = ".runner_terminal_high_water.json"

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_HEAD_FULL = re.compile(r"^[0-9a-f]{40}$")
_RUN_ID = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{3}Z-(normal|reduced)$")
_ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
_ALLOWED_PORTS = {4173, 8710}
_ALLOWED_METHODS = {"GET"}
CANONICAL_TEST_VECTOR = {"a": [0, 1, 500_000, 100_000], "b": {"enabled": True, "name": "动效"}, "z": None}
CANONICAL_TEST_JSON = '{"a":[0,1,500000,100000],"b":{"enabled":true,"name":"动效"},"z":null}'
CANONICAL_TEST_SHA256 = "d2f24c1ce9fd8f27a693ba2e09f7291c2535eb30f5e037e2627c1a928e3ddb1b"
_PERFORMANCE_BUDGETS = {
    "route_transition_observed_us": 500_000,
    "largest_motion_layout_shift_ppm": 100_000,
    "long_task_over_50ms_count": 0,
    "candidate_radar_first_stable_us": 1_200_000,
}
_FASTAPI_HEALTH_CONTRACT = {
    "service": "stock-MING Command Center 3.0",
    "status": "ok",
    "cache_only": True,
    "read_only": True,
    "external_calls_on_startup": False,
    "external_calls_triggered": False,
    "tushare_called": False,
    "deepseek_called": False,
    "github_called": False,
    "provider_or_model_calls": False,
    "real_trading_enabled": False,
    "does_not_execute_trades": True,
    "does_not_modify_strategy_action": True,
    "does_not_modify_operation_zones": True,
    "contains_secret": False,
    "ledger_api": "local_health_check",
    "ledger_external": False,
    "ledger_external_calls_triggered": False,
    "ledger_tushare_called": False,
    "ledger_deepseek_called": False,
    "ledger_github_called": False,
    "ledger_does_not_execute_trades": True,
    "ledger_does_not_modify_strategy_action": True,
}
_ROUTES: dict[str, dict[str, Any]] = {
    "#home": {"label": "Command Center", "risk": "page staging and status summary clarity", "heading": "今日作战台", "anchor": "#home-p1-symbol-confirm", "marker": "state_rail", "minimum": 1, "fragment": "home/home-p1-symbol-confirm"},
    "#next-session-chart": {"label": "Next Session Map", "risk": "chart update clarity and reduced-motion chart updates", "heading": "次日图谱", "anchor": "#next-session-chart", "marker": "route_stage", "minimum": 1, "fragment": "next-session-chart"},
    "#candidates": {"label": "Candidate Radar", "risk": "radar result cluster and runtime-budget visibility", "heading": "下一票雷达", "anchor": "#candidate-pool", "marker": "radar_cluster", "minimum": 1, "fragment": "candidates/candidate-pool"},
    "#worker": {"label": "Worker Runtime", "risk": "runtime evidence visibility and production-blocker readability", "heading": "Worker 运行时", "anchor": ".route-stage", "marker": "route_stage", "minimum": 1, "fragment": "worker"},
    "#tasks": {"label": "Task Monitor", "risk": "task phase confirmation and progress readability", "heading": "Task Monitor / 任务监控", "anchor": ".route-stage", "marker": "route_stage", "minimum": 1, "fragment": "tasks"},
    "#audit": {"label": "Call Ledger Audit", "risk": "motion audit rows and warning density", "heading": "调用审计", "anchor": ".route-stage", "marker": "route_stage", "minimum": 1, "fragment": "audit"},
}
_VIEWPORTS = {
    "desktop": (1440, 900),
    "laptop": (1280, 800),
    "tablet": (834, 1112),
    "mobile": (390, 844),
}
_MARKER_KEYS = {"route_stage", "motion_surface", "state_rail", "chart_frame", "radar_cluster", "task_panel"}
_NETWORK_KEYS = {
    "event_index", "event_type", "request_id", "session_id", "phase", "route", "viewport", "method", "url",
    "protocol", "hostname", "port", "path", "allowed", "status_code",
    "content_type", "body_sha256", "body_size_bytes", "dist_path",
    "expected_dist_sha256", "body_matches_dist", "body_schema_valid", "purpose",
    "response_semantic_summary", "response_semantic_digest", "failure_text",
}
_REPORT_KEYS = {
    "schema_version", "status", "scope", "run_id", "generated_at",
    "expected_head_full", "head_full", "worktree_clean", "run_mode",
    "reduced_motion", "base_url", "artifact_root", "selected_route",
    "frontend_source_digest", "build_identity_digest", "route_count",
    "viewport_count", "qa_matrix_count", "passed_count",
    "review_required_count", "console_error_count", "visual_qa_complete",
    "browser_performance_verified", "performance_budgets",
    "visual_acceptance_criteria", "rows", "errors", "warmup_request_count",
    "warmup_request_ledger", "warmup_navigation_count", "warmup_navigation_ledger",
    "manifest_request_count", "manifest_request_ledger", "late_network_events", "inflight_request_ids",
    "network_event_count", "request_failed_count", "websocket_count",
    "service_workers_blocked", "dist_manifest", "frontend_service_identity", "fastapi_service_identity",
    "package_binding", "raw_trace", "screenshots", "cache_only",
    "starts_no_servers", "local_urls_only", "external_calls_triggered",
    "tushare_called", "deepseek_called", "github_called",
    "does_not_execute_trades", "does_not_modify_strategy_action", "note",
    "report_digest", "runner_attestation",
}
_ROW_KEYS = {
    "route", "label", "viewport", "width", "height", "url", "risk_focus",
    "status", "visual_qa_complete", "performance_trace_complete",
    "route_transition_observed_us", "visual_settle_wait_ms",
    "route_transition_budget_us", "navigation_animation_count",
    "navigation_animation_wait_completed", "long_task_over_50ms_count",
    "largest_motion_layout_shift_ppm", "visible_element_count",
    "audited_first_viewport_element_count", "clipped_count", "offscreen_count",
    "clipped_rows", "offscreen_rows", "horizontal_overflow_px", "overlap_count",
    "overlap_rows", "unnamed_interactive_count", "unnamed_interactive_rows",
    "concealed_motion_content_count", "concealed_motion_content_rows",
    "expected_heading", "heading_text", "expected_heading_paint_visible", "expected_anchor",
    "expected_anchor_ready", "expected_anchor_paint_visible", "expected_anchor_sticky_clearance",
    "route_cache_boundary_required", "route_cache_boundary_present",
    "route_cache_ready", "route_cache_not_busy", "route_cache_shell_visible",
    "route_cache_overlay_absent", "route_cache_not_degraded", "route_cache_content_visible", "motion_marker_name", "motion_marker_minimum",
    "motion_marker_minimum_ready", "long_task_observer_ready",
    "layout_shift_observer_ready", "request_count", "request_ledger",
    "post_request_count", "post_request_urls", "motion_markers", "screenshot_path",
}
_SCREENSHOT_KEYS = {"path", "sha256", "size_bytes", "route", "viewport", "width", "height"}
_RAW_TRACE_KEYS = {"path", "sha256", "size_bytes"}
_ATTESTATION_KEYS = {
    "sequence_no", "previous_event_mac", "event_mac", "state_schema_version",
    "anchor_schema_version", "identity_schema_version", "terminal_schema_version",
}
_STATE_KEYS = {"schema_version", "updated_at", "events"}
_ANCHOR_KEYS = {
    "schema_version", "installation_id", "sequence_no", "updated_at",
    "latest_event_mac", "state_digest", "anchor_mac",
}
_IDENTITY_KEYS = {"schema_version", "installation_id", "created_at", "identity_mac"}
_TERMINAL_KEYS = {
    "schema_version", "installation_id", "sequence_no", "updated_at",
    "latest_event_mac", "state_digest", "anchor_digest", "terminal_mac",
}
_EVENT_KEYS = {
    "schema_version", "sequence_no", "created_at", "report_relpath",
    "report_digest", "head_full", "run_mode", "frontend_source_digest",
    "build_identity_digest", "dist_manifest_digest", "entry_graph_digest",
    "frontend_service_identity_digest", "package_identity_digest",
    "previous_event_mac", "event_mac",
}
_TRACE_KEYS = {
    "schema_version", "generated_at", "head_full", "run_mode",
    "frontend_source_digest", "build_identity_digest", "row_count", "rows",
    "warmup_request_count", "warmup_request_ledger", "warmup_navigation_count",
    "warmup_navigation_ledger", "manifest_request_count", "manifest_request_ledger",
    "late_network_events", "inflight_request_ids", "network_event_count", "request_failed_count",
    "websocket_count", "dist_manifest_digest", "frontend_service_identity_digest",
    "fastapi_service_identity_digest", "package_identity_digest", "error_count", "errors",
}
_DIST_MANIFEST_KEYS = {
    "schema_version", "entry_html", "entries", "entry_graph",
    "entry_graph_digest", "manifest_digest",
}
_DIST_ENTRY_KEYS = {"path", "sha256", "size_bytes", "content_type"}
_SERVICE_IDENTITY_KEYS = {
    "schema_version", "listener_pid", "protocol", "hostname", "port", "base_url",
    "process_cwd", "command_sha256", "served_root", "served_root_manifest_digest",
    "identity_digest",
}
_PACKAGE_BINDING_KEYS = {
    "schema_version", "head_full", "build_receipt_sha256", "package_manifest_digest",
    "artifact_set_sha256", "app_bundle_sha256", "app_executable_sha256", "dmg_sha256",
    "production_package_complete", "identity_digest",
}
_FASTAPI_IDENTITY_KEYS = {
    "schema_version", "endpoint", "status_code", "content_type", "service",
    "response_body_sha256", "response_size_bytes", "health_contract_digest",
    "health_schema_valid", "identity_digest",
}
_WARMUP_NAVIGATION_KEYS = {"sequence_no", "viewport", "url"}
_ELEMENT_ROW_KEYS = {
    "tag", "className", "text", "x", "y", "width", "height", "display",
    "visibility", "opacity_ppm", "clipped", "offscreen",
}
_OVERLAP_ROW_KEYS = {"left", "right"}
FASTAPI_RESPONSE_SEMANTIC_SCHEMA = "command_center_3_motion_fastapi_response_semantic.v3"
_FASTAPI_RESPONSE_SEMANTIC_KEYS = {
    "schema_version", "endpoint", "method", "status_code", "raw_body_sha256",
    "raw_body_size_bytes", "envelope_state", "envelope_ok", "error_code",
    "data_schema_version", "data_packet_key", "data_status", "data_cache_source",
    "ledger_count", "ledger_rows_typed",
    "ledger_sources_allowlisted", "ledger_current_external_count",
    "ledger_current_provider_count", "ledger_current_model_count",
    "ledger_current_worker_count", "ledger_current_trade_count", "task_post_count",
    "data_current_read_flags_valid", "strict_current_read_contract",
    "strict_current_read_valid", "historical_provenance_count",
    "secret_bearing_field_count", "ledger_contract_rows",
}
_FASTAPI_LEDGER_CONTRACT_KEYS = {
    "api", "source", "method", "path", "external", "provider", "model",
    "worker", "trade", "task_post", "secret",
}
_FASTAPI_STRICT_CURRENT_READ_ENDPOINTS = {
    "/api/desktop/preflight-cache",
    "/api/factor-quant/cache",
    "/api/next-session/cache",
    "/api/worker/cache",
}
_FASTAPI_CACHE_CONTRACTS = {
    "/api/audit/cache": ("call_ledger_audit_cache.v1", "command_center_3_call_ledger_audit_cache", False),
    "/api/audit/user-route-qa": ("command_center_3_user_route_qa_evidence_cache.v1", "command_center_3_user_route_qa_evidence_cache", False),
    "/api/bootstrap/status": ("command_center_bootstrap_runtime_mode.v1", "command_center_3_bootstrap_runtime_mode_packet", False),
    "/api/desktop/preflight-cache": ("desktop_shell_preflight_cache.v1", "command_center_3_desktop_shell_preflight_cache", False),
    "/api/factor-quant/cache": ("factor_quant_hub.v1", "command_center_factor_quant_hub_packet", False),
    "/api/next-session/cache": ("next_session_projection.v1", "command_center_next_session_projection_packet", True),
    "/api/position/cache": ("position_context_cache.v1", "command_center_3_position_context_cache", False),
    "/api/candidate-radar/cache": ("candidate_radar_cache.v1", "command_center_3_candidate_radar_cache", False),
    "/api/storage": ("command_center_3_storage_overview.v1", "", False),
    "/api/storage/catalog": ("command_center_3_storage_dataset_catalog.v1", "", False),
    "/api/storage/current-result": ("command_center_3_storage_current_result_cache.v1", "", False),
    "/api/data-health/cache": ("data_health_timeline_cache.v1", "command_center_3_data_health_timeline_cache", False),
    "/api/migration/status": ("command_center_3_migration_status.v2", "command_center_3_migration_status", False),
    "/api/tasks": ("command_center_3_task_status_index.v1", "command_center_3_task_status_index", False),
    "/api/tasks/catalog": ("command_center_3_task_catalog.v1", "command_center_3_task_catalog", False),
    "/api/worker/cache": ("worker_runtime_cache.v1", "command_center_3_worker_runtime_cache", False),
    "/api/packets": ("command_center_3_packet_index.v1", "", False),
    "/api/packets/command_center_etf_packet": ("", "command_center_etf_packet", True),
    "/api/packets/command_center_margin_packet": ("", "command_center_margin_packet", True),
    "/api/packets/command_center_margin_etf_refresh_receipt": ("", "command_center_margin_etf_refresh_receipt", True),
}

# This is the closed response-ledger surface observed by the six audited routes.
# Do not accept arbitrary ``local_*`` names: every raw envelope ledger row must
# be an ordered, unique member of the explicit allowlist for its exact GET
# endpoint.  Some button-gated local review receipts are optional, so requiring
# every allowlisted API on every read would reject a clean cache with no such
# receipt.  The primary cache-read API is always required first.  The home route
# currently consumes twenty cache endpoints, including the read-only migration
# status cache consumed by the ordinary home and health views.
_FASTAPI_LEDGER_APIS: dict[str, tuple[str, ...]] = {
    "/api/audit/cache": ("local_call_ledger_audit_cache",),
    "/api/audit/user-route-qa": ("GET /api/audit/user-route-qa",),
    "/api/bootstrap/status": ("local_bootstrap_runtime_mode_cache",),
    "/api/desktop/preflight-cache": ("local_desktop_shell_preflight_cache",),
    "/api/factor-quant/cache": ("local_factor_quant_cache",),
    "/api/next-session/cache": ("local_next_session_cache",),
    "/api/position/cache": ("local_position_context_cache",),
    "/api/candidate-radar/cache": (
        "local_candidate_radar_cache", "local_candidate_radar_legacy_parity_acceptance_receipt",
        "local_candidate_radar_production_activation_receipt",
        "local_candidate_radar_quant_projection_execution_request",
        "local_candidate_radar_provider_parity_execution_request", "local_candidate_radar_worker_execution_recipe",
        "local_candidate_radar_worker_execution_request", "local_candidate_radar_full_pool_worker_fallback_preview",
        "local_candidate_radar_deep_scan_worker_fallback_preview",
        "local_candidate_radar_worker_runtime_linked_evidence", "local_candidate_radar_next_execution_recipe",
        "local_candidate_radar_durable_evidence_recipe",
        "local_candidate_radar_production_replacement_review_preview",
        "local_candidate_radar_production_promotion_dry_run_preview",
        "local_candidate_radar_legacy_retirement_review_preview",
        "local_candidate_radar_production_promotion_review_preview",
        "local_candidate_radar_production_stage_scope_manifest",
    ),
    "/api/storage": ("local_storage_overview_cache",),
    "/api/storage/catalog": ("local_storage_dataset_catalog_cache",),
    "/api/storage/current-result": ("local_storage_current_result_cache",),
    "/api/data-health/cache": ("local_data_health_timeline_cache", "local_freshness_durable_evidence_recipe"),
    "/api/migration/status": ("local_migration_status_cache",),
    "/api/tasks": ("local_task_status_index",),
    "/api/tasks/catalog": ("local_task_catalog_cache",),
    "/api/worker/cache": ("local_worker_runtime_cache",),
    "/api/packets": ("local_packet_registry_cache",),
    "/api/packets/command_center_etf_packet": ("local_packet_cache_read",),
    "/api/packets/command_center_margin_packet": ("local_packet_cache_read",),
    "/api/packets/command_center_margin_etf_refresh_receipt": ("local_packet_cache_read",),
}
_FASTAPI_HEALTH_LEDGER_APIS = ("local_health_check",)
_FASTAPI_CACHE_ENDPOINT_COUNT = 20

_MAX_PNG_FILE_BYTES = 16 * 1024 * 1024
_MAX_PNG_IDAT_BYTES = 12 * 1024 * 1024
_MAX_PNG_DECODED_BYTES = 64 * 1024 * 1024


def _reject_float(_: str) -> Any:
    raise ValueError("motion evidence JSON permits integers only")


def _canonical_bytes(value: Any) -> bytes:
    def validate(item: Any) -> None:
        if isinstance(item, float):
            raise ValueError("motion canonical JSON permits integers only")
        if isinstance(item, list):
            for child in item:
                validate(child)
        elif isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("motion canonical JSON keys must be strings")
                validate(child)

    validate(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def canonical_vector_valid() -> bool:
    return _canonical_bytes(CANONICAL_TEST_VECTOR).decode("utf-8") == CANONICAL_TEST_JSON and _digest(CANONICAL_TEST_VECTOR) == CANONICAL_TEST_SHA256


def _exact_keys(value: Any, expected: set[str]) -> bool:
    return isinstance(value, Mapping) and set(value) == expected


def _utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0


def _safe_relative_path(root: Path, raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        return None
    rel = Path(raw)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        return None
    candidate = root.joinpath(*rel.parts)
    try:
        root_stat = os.lstat(root)
        if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
            return None
        current = root
        for part in rel.parts[:-1]:
            current = current / part
            current_stat = os.lstat(current)
            if not stat.S_ISDIR(current_stat.st_mode) or stat.S_ISLNK(current_stat.st_mode):
                return None
    except OSError:
        return None
    return candidate


def _secure_read(path: Path, *, mode: int | None = None, max_bytes: int | None = None) -> tuple[bytes, os.stat_result] | None:
    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
            return None
        if mode is not None and stat.S_IMODE(before.st_mode) != mode:
            return None
        if max_bytes is not None and before.st_size > max_bytes:
            return None
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        try:
            during = os.fstat(fd)
            if not stat.S_ISREG(during.st_mode) or (before.st_dev, before.st_ino) != (during.st_dev, during.st_ino):
                return None
            if max_bytes is not None and during.st_size > max_bytes:
                return None
            chunks = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            os.close(fd)
        after = os.lstat(path)
        if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size):
            return None
        return b"".join(chunks), during
    except OSError:
        return None


def _read_json(path: Path, *, mode: int | None = None) -> Any:
    opened = _secure_read(path, mode=mode)
    if opened is None:
        return None
    try:
        return json.loads(opened[0].decode("utf-8"), parse_float=_reject_float, parse_constant=_reject_float)
    except (UnicodeDecodeError, ValueError, TypeError):
        return None


def _file_digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tree_digest(root: Path) -> str:
    rows: list[dict[str, str]] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirs.sort()
        files.sort()
        for name in list(dirs):
            child = current_path / name
            if stat.S_ISLNK(os.lstat(child).st_mode):
                raise ValueError("frontend identity contains a symlink")
        for name in files:
            path = current_path / name
            opened = _secure_read(path)
            if opened is None:
                raise ValueError("frontend identity contains an unsafe file")
            rows.append({"path": path.relative_to(root).as_posix(), "sha256": _file_digest_bytes(opened[0])})
    return _digest(rows)


def _web_content_type(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}.get(suffix, "")


def _dist_manifest(project_root: Path) -> dict[str, Any] | None:
    dist_root = project_root / "desktop" / "dist"
    try:
        if not dist_root.is_dir() or dist_root.is_symlink():
            return None
        entries: list[dict[str, Any]] = []
        for path in sorted(dist_root.rglob("*"), key=lambda item: item.relative_to(dist_root).as_posix()):
            if path.is_dir():
                if path.is_symlink():
                    return None
                continue
            relpath = path.relative_to(dist_root).as_posix()
            content_type = _web_content_type(relpath)
            if not content_type:
                continue
            opened = _secure_read(path)
            if opened is None:
                return None
            entries.append(
                {
                    "path": relpath,
                    "sha256": _file_digest_bytes(opened[0]),
                    "size_bytes": len(opened[0]),
                    "content_type": content_type,
                }
            )
        graph = [str(item["path"]) for item in entries]
        if not entries or "index.html" not in graph:
            return None
        unsigned = {
            "schema_version": DIST_MANIFEST_SCHEMA,
            "entry_html": "index.html",
            "entries": entries,
            "entry_graph": graph,
            "entry_graph_digest": _digest(graph),
        }
        return {**unsigned, "manifest_digest": _digest(unsigned)}
    except (OSError, ValueError):
        return None


def _frontend_identity(project_root: Path) -> tuple[str, str, dict[str, Any]] | None:
    frontend = project_root / "desktop"
    source_root = frontend / "src"
    dist_root = frontend / "dist"
    try:
        if not source_root.is_dir() or not dist_root.is_dir() or source_root.is_symlink() or dist_root.is_symlink():
            return None
        manifest = _dist_manifest(project_root)
        if manifest is None:
            return None
        source_digest = _tree_digest(source_root)
        inputs = []
        for name in ("package.json", "package-lock.json", "vite.config.ts", "tsconfig.json"):
            path = frontend / name
            opened = _secure_read(path)
            if opened is not None:
                inputs.append({"path": f"desktop/{name}", "sha256": _file_digest_bytes(opened[0])})
        return (
            source_digest,
            _digest(
                {
                    "frontend_source_digest": source_digest,
                    "dist_digest": _tree_digest(dist_root),
                    "dist_manifest_digest": manifest["manifest_digest"],
                    "build_inputs": inputs,
                }
            ),
            manifest,
        )
    except (OSError, ValueError):
        return None


def _decode_png(data: bytes) -> tuple[int, int] | None:
    if len(data) < 45 or len(data) > _MAX_PNG_FILE_BYTES or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    offset = 8
    ihdr: tuple[int, int, int, int, int, int, int] | None = None
    idat: list[bytes] = []
    idat_size = 0
    chunk_count = 0
    seen_iend = False
    while offset < len(data):
        chunk_count += 1
        if chunk_count > 4096:
            return None
        if offset + 12 > len(data):
            return None
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        if length > _MAX_PNG_FILE_BYTES:
            return None
        end = offset + 12 + length
        if end > len(data):
            return None
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected_crc:
            return None
        if kind == b"IHDR":
            if ihdr is not None or length != 13 or offset != 8:
                return None
            ihdr = (*struct.unpack(">IIBBBBB", payload),)
        elif kind == b"IDAT":
            if ihdr is None or seen_iend:
                return None
            idat.append(payload)
            idat_size += len(payload)
            if idat_size > _MAX_PNG_IDAT_BYTES:
                return None
        elif kind == b"IEND":
            if length != 0 or ihdr is None or not idat or end != len(data):
                return None
            seen_iend = True
        offset = end
    if ihdr is None or not seen_iend:
        return None
    width, height, bit_depth, color_type, compression, png_filter, interlace = ihdr
    if width <= 0 or height <= 0 or width > 4096 or height > 4096:
        return None
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None or bit_depth not in {1, 2, 4, 8, 16} or compression != 0 or png_filter != 0 or interlace != 0:
        return None
    row_bytes = (width * channels * bit_depth + 7) // 8
    expected_size = height * (row_bytes + 1)
    if expected_size <= 0 or expected_size > _MAX_PNG_DECODED_BYTES:
        return None
    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(b"".join(idat), expected_size + 1)
        if decompressor.unconsumed_tail or not decompressor.eof:
            return None
        decoded += decompressor.flush()
    except zlib.error:
        return None
    if len(decoded) != expected_size:
        return None
    if any(decoded[row * (row_bytes + 1)] > 4 for row in range(height)):
        return None
    return width, height


def _valid_local_url(raw: Any, expected_fragment: str | None = None) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme == "http" and parsed.hostname in _ALLOWED_HOSTS and port in _ALLOWED_PORTS
        and parsed.username is None and parsed.password is None and parsed.query == ""
        and parsed.path in ({"", "/"} if expected_fragment is None else {"/"})
        and (expected_fragment is None or parsed.fragment == expected_fragment)
    )


def _valid_local_network_url(raw: Any) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme == "http"
        and parsed.hostname in _ALLOWED_HOSTS
        and port in _ALLOWED_PORTS
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and parsed.path.startswith("/")
    )


def _dist_manifest_valid(value: Any) -> bool:
    if not _exact_keys(value, _DIST_MANIFEST_KEYS) or value.get("schema_version") != DIST_MANIFEST_SCHEMA:
        return False
    entries = value.get("entries")
    graph = value.get("entry_graph")
    if not isinstance(entries, list) or not isinstance(graph, list) or value.get("entry_html") != "index.html":
        return False
    paths: list[str] = []
    for entry in entries:
        if not _exact_keys(entry, _DIST_ENTRY_KEYS):
            return False
        path = entry.get("path")
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or "\\" in path
            or any(part in {"", ".", ".."} for part in Path(path).parts)
            or _web_content_type(path) != entry.get("content_type")
            or not isinstance(entry.get("sha256"), str)
            or not _HEX_64.fullmatch(entry["sha256"])
            or type(entry.get("size_bytes")) is not int
            or entry["size_bytes"] < 0
        ):
            return False
        paths.append(path)
    if paths != sorted(set(paths)) or graph != paths or "index.html" not in graph:
        return False
    unsigned = {key: value[key] for key in sorted(_DIST_MANIFEST_KEYS - {"manifest_digest"})}
    return bool(
        value.get("entry_graph_digest") == _digest(graph)
        and value.get("manifest_digest") == _digest(unsigned)
    )


def _service_identity_valid(value: Any, *, base_url: Any, manifest_digest: Any) -> bool:
    if not _exact_keys(value, _SERVICE_IDENTITY_KEYS) or value.get("schema_version") != SERVICE_IDENTITY_SCHEMA:
        return False
    unsigned = {key: value[key] for key in sorted(_SERVICE_IDENTITY_KEYS - {"identity_digest"})}
    return bool(
        type(value.get("listener_pid")) is int
        and value["listener_pid"] > 1
        and value.get("protocol") == "http:"
        and value.get("hostname") in _ALLOWED_HOSTS
        and value.get("port") == "4173"
        and value.get("base_url") == base_url
        and value.get("process_cwd") == "desktop"
        and value.get("served_root") == "desktop/dist"
        and value.get("served_root_manifest_digest") == manifest_digest
        and isinstance(value.get("command_sha256"), str)
        and _HEX_64.fullmatch(value["command_sha256"])
        and value.get("identity_digest") == _digest(unsigned)
    )


def _fastapi_identity_valid(value: Any) -> bool:
    if not _exact_keys(value, _FASTAPI_IDENTITY_KEYS) or value.get("schema_version") != FASTAPI_IDENTITY_SCHEMA:
        return False
    unsigned = {key: value[key] for key in sorted(_FASTAPI_IDENTITY_KEYS - {"identity_digest"})}
    try:
        parsed = urlsplit(str(value.get("endpoint") or ""))
    except ValueError:
        return False
    return bool(
        parsed.scheme == "http"
        and parsed.hostname == "127.0.0.1"
        and parsed.port == 8710
        and parsed.path == "/health"
        and not parsed.query
        and not parsed.fragment
        and parsed.username is None
        and parsed.password is None
        and type(value.get("status_code")) is int
        and value.get("status_code") == 200
        and value.get("content_type") == "application/json"
        and value.get("service") == "stock-MING Command Center 3.0"
        and isinstance(value.get("response_body_sha256"), str)
        and _HEX_64.fullmatch(value["response_body_sha256"])
        and type(value.get("response_size_bytes")) is int
        and 2 <= value["response_size_bytes"] <= 1024 * 1024
        and value.get("health_contract_digest") == _digest(_FASTAPI_HEALTH_CONTRACT)
        and type(value.get("health_schema_valid")) is bool
        and value.get("health_schema_valid") is True
        and value.get("identity_digest") == _digest(unsigned)
    )


def _package_binding_valid(value: Any, *, expected_head_full: Any) -> bool:
    if not _exact_keys(value, _PACKAGE_BINDING_KEYS) or value.get("schema_version") != PACKAGE_BINDING_SCHEMA:
        return False
    unsigned = {key: value[key] for key in sorted(_PACKAGE_BINDING_KEYS - {"identity_digest"})}
    return bool(
        value.get("head_full") == expected_head_full
        and value.get("production_package_complete") is True
        and all(isinstance(value.get(name), str) and _HEX_64.fullmatch(value[name]) for name in (
            "build_receipt_sha256", "package_manifest_digest", "artifact_set_sha256",
            "app_bundle_sha256", "app_executable_sha256", "dmg_sha256",
        ))
        and value.get("identity_digest") == _digest(unsigned)
    )


def _formal_package_binding(evidence_root: Path, expected_head_full: str) -> dict[str, Any] | None:
    try:
        from server.services.tauri_package_verifier import validate_tauri_production_package

        verification = validate_tauri_production_package(
            evidence_root,
            expected_head_full=expected_head_full,
            write_manifest=False,
        )
        package_root = evidence_root / "desktop_runtime"
        build_path = package_root / "tauri_build_receipt.json"
        manifest_path = package_root / "tauri_production_package_manifest.json"
        pointer_path = package_root / "tauri_production_package_pointer.json"
        build_opened = _secure_read(build_path)
        manifest = _read_json(manifest_path)
        pointer = _read_json(pointer_path)
        if build_opened is None or not isinstance(manifest, Mapping) or not isinstance(pointer, Mapping):
            return None
        manifest_material = dict(manifest)
        manifest_digest = manifest_material.pop("manifest_digest", None)
        if (
            verification.get("production_package_complete") is not True
            or verification.get("head_full") != expected_head_full
            or not isinstance(manifest_digest, str)
            or manifest_digest != _digest(manifest_material)
            or manifest.get("head_full") != expected_head_full
            or manifest.get("production_package_complete") is not True
            or pointer.get("head_full") != expected_head_full
            or pointer.get("manifest_digest") != manifest_digest
            or pointer.get("artifact_set_sha256") != verification.get("artifact_set_sha256")
            or pointer.get("immutable") is not True
        ):
            return None
        unsigned = {
            "schema_version": PACKAGE_BINDING_SCHEMA,
            "head_full": expected_head_full,
            "build_receipt_sha256": _file_digest_bytes(build_opened[0]),
            "package_manifest_digest": manifest_digest,
            "artifact_set_sha256": verification.get("artifact_set_sha256"),
            "app_bundle_sha256": verification.get("app_bundle_sha256"),
            "app_executable_sha256": verification.get("app_executable_sha256"),
            "dmg_sha256": verification.get("dmg_sha256"),
            "production_package_complete": True,
        }
        if not all(isinstance(unsigned.get(name), str) and _HEX_64.fullmatch(unsigned[name]) for name in (
            "build_receipt_sha256", "package_manifest_digest", "artifact_set_sha256",
            "app_bundle_sha256", "app_executable_sha256", "dmg_sha256",
        )):
            return None
        return {**unsigned, "identity_digest": _digest(unsigned)}
    except (OSError, ValueError, TypeError):
        return None


def _repository_is_exact_clean(project_root: Path, expected_head_full: str) -> bool:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project_root, capture_output=True, text=True, timeout=10, check=False
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(
        head.returncode == 0
        and head.stdout.strip() == expected_head_full
        and status_result.returncode == 0
        and not status_result.stdout.strip()
    )


def current_repository_head(project_root: Path) -> str | None:
    """Return the exact local HEAD for read-only evidence consumers."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = result.stdout.strip()
    return head if result.returncode == 0 and _HEAD_FULL.fullmatch(head) else None


def _fastapi_response_semantic_valid(entry: Mapping[str, Any]) -> bool:
    if not (
        len(_FASTAPI_CACHE_CONTRACTS) == _FASTAPI_CACHE_ENDPOINT_COUNT
        and len(_FASTAPI_LEDGER_APIS) == _FASTAPI_CACHE_ENDPOINT_COUNT
        and set(_FASTAPI_CACHE_CONTRACTS) == set(_FASTAPI_LEDGER_APIS)
    ):
        return False
    summary = entry.get("response_semantic_summary")
    if not _exact_keys(summary, _FASTAPI_RESPONSE_SEMANTIC_KEYS):
        return False
    assert isinstance(summary, Mapping)
    endpoint = summary.get("endpoint")
    if not isinstance(endpoint, str):
        return False
    purpose = entry.get("purpose")
    if purpose == "fastapi_health_identity":
        expected_schema = ""
        expected_packet = ""
        cache_missing_allowed = False
        endpoint_allowed = endpoint == "/health"
        expected_ledger_apis = _FASTAPI_HEALTH_LEDGER_APIS
    else:
        contract = _FASTAPI_CACHE_CONTRACTS.get(endpoint)
        if contract is None:
            return False
        expected_schema, expected_packet, cache_missing_allowed = contract
        endpoint_allowed = purpose == "fastapi_cache_read"
        expected_ledger_apis = _FASTAPI_LEDGER_APIS[endpoint]
    integer_names = (
        "status_code", "raw_body_size_bytes", "ledger_count",
        "ledger_current_external_count", "ledger_current_provider_count",
        "ledger_current_model_count", "ledger_current_worker_count",
        "ledger_current_trade_count", "task_post_count", "historical_provenance_count",
        "secret_bearing_field_count",
    )
    if any(type(summary.get(name)) is not int or summary[name] < 0 for name in integer_names):
        return False
    if any(type(summary.get(name)) is not bool for name in (
        "envelope_ok", "ledger_rows_typed", "ledger_sources_allowlisted",
        "data_current_read_flags_valid", "strict_current_read_contract",
        "strict_current_read_valid",
    )):
        return False
    state = summary.get("envelope_state")
    state_valid = bool(
        (state == "ok" and summary.get("envelope_ok") is True and summary.get("error_code") == "")
        or (
            state == "cache_missing"
            and cache_missing_allowed
            and summary.get("envelope_ok") is False
            and summary.get("error_code") == "cache_missing"
        )
    )
    identity_valid = bool(
        (not expected_schema or summary.get("data_schema_version") == expected_schema)
        and (
            not expected_packet
            or summary.get("data_packet_key") == expected_packet
            or (state == "cache_missing" and purpose == "fastapi_cache_read" and endpoint.startswith("/api/packets/") and summary.get("data_packet_key") == "")
        )
    )
    strict_contract_expected = endpoint in _FASTAPI_STRICT_CURRENT_READ_ENDPOINTS
    strict_contract_valid = bool(
        summary.get("strict_current_read_contract") is strict_contract_expected
        and (not strict_contract_expected or summary.get("strict_current_read_valid") is True)
        and (
            not (strict_contract_expected and state == "cache_missing")
            or (
                summary.get("data_status") == "cache_missing"
                and summary.get("data_cache_source") == "cache_missing"
            )
        )
    )
    raw_binding_valid = bool(
        summary.get("schema_version") == FASTAPI_RESPONSE_SEMANTIC_SCHEMA
        and endpoint_allowed
        and summary.get("method") == entry.get("method") == "GET"
        and summary.get("status_code") == entry.get("status_code")
        and summary.get("raw_body_sha256") == entry.get("body_sha256")
        and summary.get("raw_body_size_bytes") == entry.get("body_size_bytes")
        and isinstance(summary.get("raw_body_sha256"), str)
        and _HEX_64.fullmatch(summary["raw_body_sha256"])
        and 2 <= summary["raw_body_size_bytes"] <= 32 * 1024 * 1024
    )
    counters_safe = bool(
        summary.get("ledger_count", 0) > 0
        and summary.get("ledger_rows_typed") is True
        and summary.get("ledger_sources_allowlisted") is True
        and summary.get("data_current_read_flags_valid") is True
        and all(summary.get(name) == 0 for name in (
            "ledger_current_external_count", "ledger_current_provider_count",
            "ledger_current_model_count", "ledger_current_worker_count",
            "ledger_current_trade_count", "task_post_count", "secret_bearing_field_count",
        ))
    )
    ledger_contract_rows = summary.get("ledger_contract_rows")
    ledger_contract_valid = bool(
        isinstance(ledger_contract_rows, list)
        and bool(ledger_contract_rows)
        and len(ledger_contract_rows) <= len(expected_ledger_apis)
        and summary.get("ledger_count") == len(ledger_contract_rows)
    )
    if ledger_contract_valid:
        observed_apis: list[str] = []
        for row in ledger_contract_rows:
            if not _exact_keys(row, _FASTAPI_LEDGER_CONTRACT_KEYS):
                ledger_contract_valid = False
                break
            assert isinstance(row, Mapping)
            if not (
                isinstance(row.get("api"), str)
                and row.get("source") == endpoint
                and row.get("method") == "GET"
                and row.get("path") == endpoint
                and all(type(row.get(name)) is bool and row.get(name) is False for name in (
                    "external", "provider", "model", "worker", "trade", "task_post", "secret",
                ))
            ):
                ledger_contract_valid = False
                break
            observed_apis.append(str(row["api"]))
        expected_positions = {api: index for index, api in enumerate(expected_ledger_apis)}
        observed_positions = [expected_positions.get(api, -1) for api in observed_apis]
        if ledger_contract_valid and not (
            observed_apis[0] == expected_ledger_apis[0]
            and -1 not in observed_positions
            and observed_positions == sorted(set(observed_positions))
        ):
            ledger_contract_valid = False
    digest = entry.get("response_semantic_digest")
    return bool(
        raw_binding_valid
        and state_valid
        and identity_valid
        and strict_contract_valid
        and counters_safe
        and ledger_contract_valid
        and isinstance(digest, str)
        and _HEX_64.fullmatch(digest)
        and digest == _digest(dict(summary))
    )


def _network_entry_valid(entry: Any, *, phase: str, route: str, viewport: str) -> bool:
    if not _exact_keys(entry, _NETWORK_KEYS):
        return False
    try:
        parsed = urlsplit(str(entry.get("url") or ""))
        parsed_port = parsed.port
    except ValueError:
        return False
    purpose = entry.get("purpose")
    endpoint_valid = bool(
        parsed.scheme == "http"
        and parsed.hostname in _ALLOWED_HOSTS
        and parsed_port in _ALLOWED_PORTS
        and parsed.path == entry.get("path")
        and f"{parsed.scheme}:" == entry.get("protocol")
        and parsed.hostname == entry.get("hostname")
        and str(parsed_port) == str(entry.get("port"))
        and (
            (parsed_port == 4173 and purpose == "vite_preview_dist_resource")
            or (parsed_port == 8710 and parsed.path == "/health" and purpose == "fastapi_health_identity")
            or (parsed_port == 8710 and parsed.path in _FASTAPI_CACHE_CONTRACTS and purpose == "fastapi_cache_read")
        )
    )
    if not (
        type(entry.get("event_index")) is int and entry["event_index"] > 0
        and isinstance(entry.get("request_id"), str) and re.fullmatch(r"[a-z]+:(http|ws):[1-9][0-9]*", entry["request_id"])
        and isinstance(entry.get("session_id"), str) and re.fullmatch(r"[a-z]+:[1-9][0-9]*:(warmup|manifest|route):#[a-z0-9-]+", entry["session_id"])
        and entry.get("phase") == phase and entry.get("route") == route and entry.get("viewport") == viewport
        and entry.get("method") in _ALLOWED_METHODS and entry.get("protocol") == "http:"
        and endpoint_valid
        and isinstance(entry.get("path"), str) and entry["path"].startswith("/")
        and isinstance(entry.get("url"), str) and _valid_local_network_url(entry["url"])
        and type(entry.get("allowed")) is bool
        and type(entry.get("body_schema_valid")) is bool
        and entry.get("event_type") in {"request", "response", "requestfailed"}
    ):
        return False
    if entry.get("event_type") == "request":
        return bool(entry.get("allowed") is True and entry.get("failure_text") == "" and all(entry.get(name) in {None, "", False} for name in (
            "status_code", "content_type", "body_sha256", "body_size_bytes", "dist_path",
            "expected_dist_sha256", "body_matches_dist", "body_schema_valid", "response_semantic_digest",
        )) and entry.get("response_semantic_summary") == {})
    if entry.get("event_type") == "requestfailed":
        return bool(
            entry.get("allowed") is False
            and isinstance(entry.get("failure_text"), str)
            and bool(entry["failure_text"])
            and all(entry.get(name) in {None, "", False} for name in (
                "status_code", "content_type", "body_sha256", "body_size_bytes", "dist_path",
                "expected_dist_sha256", "body_matches_dist", "body_schema_valid", "response_semantic_digest",
            ))
            and entry.get("response_semantic_summary") == {}
        )
    common_response_valid = bool(
        entry.get("allowed") is True
        and entry.get("failure_text") == ""
        and type(entry.get("status_code")) is int
        and 200 <= entry["status_code"] <= 299
        and isinstance(entry.get("content_type"), str)
        and isinstance(entry.get("body_sha256"), str)
        and _HEX_64.fullmatch(entry["body_sha256"])
        and type(entry.get("body_size_bytes")) is int
        and entry["body_size_bytes"] >= 0
        and isinstance(entry.get("dist_path"), str)
        and isinstance(entry.get("expected_dist_sha256"), str)
        and type(entry.get("body_matches_dist")) is bool
        and entry.get("body_schema_valid") is True
    )
    if not common_response_valid:
        return False
    media_type = entry["content_type"].split(";", 1)[0].strip().lower()
    if purpose == "vite_preview_dist_resource":
        return bool(
            media_type in {"text/html", "text/javascript", "application/javascript", "text/css"}
            and bool(entry.get("dist_path"))
            and isinstance(entry.get("expected_dist_sha256"), str)
            and _HEX_64.fullmatch(entry["expected_dist_sha256"])
            and entry.get("body_matches_dist") is True
            and entry.get("response_semantic_summary") == {}
            and entry.get("response_semantic_digest") == ""
        )
    return bool(
        media_type == "application/json"
        and entry.get("dist_path") == ""
        and entry.get("expected_dist_sha256") == ""
        and entry.get("body_matches_dist") is False
        and _fastapi_response_semantic_valid(entry)
    )


def _network_pairing_blockers(entries: list[Any]) -> list[str]:
    blockers: list[str] = []
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("request_id"), str):
            blockers.append("network_request_id_missing")
            continue
        grouped.setdefault(entry["request_id"], []).append(entry)
    for request_id, group in grouped.items():
        requests = [entry for entry in group if entry.get("event_type") == "request"]
        terminals = [entry for entry in group if entry.get("event_type") in {"response", "requestfailed"}]
        unexpected = [entry for entry in group if entry.get("event_type") not in {"request", "response", "requestfailed"}]
        if len(requests) != 1:
            blockers.append(f"network_request_count_invalid:{request_id}")
            continue
        if len(terminals) != 1 or unexpected:
            blockers.append(f"network_terminal_count_invalid:{request_id}")
            continue
        request = requests[0]
        terminal = terminals[0]
        if type(request.get("event_index")) is not int or type(terminal.get("event_index")) is not int or terminal["event_index"] <= request["event_index"]:
            blockers.append(f"network_terminal_order_invalid:{request_id}")
        for key in ("request_id", "session_id", "phase", "route", "viewport", "method", "url", "protocol", "hostname", "port", "path", "purpose"):
            if terminal.get(key) != request.get(key) or type(terminal.get(key)) is not type(request.get(key)):
                blockers.append(f"network_origin_mismatch:{request_id}:{key}")
    return blockers


def _element_row_valid(value: Any) -> bool:
    return bool(
        _exact_keys(value, _ELEMENT_ROW_KEYS)
        and all(isinstance(value.get(key), str) for key in ("tag", "className", "text", "display", "visibility"))
        and bool(value.get("tag"))
        and all(type(value.get(key)) is int for key in ("x", "y", "width", "height", "opacity_ppm"))
        and value.get("width", -1) >= 0
        and value.get("height", -1) >= 0
        and 0 <= value.get("opacity_ppm", -1) <= 1_000_000
        and type(value.get("clipped")) is bool
        and type(value.get("offscreen")) is bool
    )


def _event_without_mac(event: Mapping[str, Any]) -> dict[str, Any]:
    return {key: event[key] for key in sorted(_EVENT_KEYS - {"event_mac"})}


def _report_without_seals(report: Mapping[str, Any]) -> dict[str, Any]:
    return {key: report[key] for key in sorted(_REPORT_KEYS - {"report_digest", "runner_attestation"})}


def _row_recomputed_pass(row: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not _exact_keys(row, _ROW_KEYS):
        return False, ["row_schema_fields_invalid"]
    assert isinstance(row, Mapping)
    route = row.get("route")
    viewport = row.get("viewport")
    config = _ROUTES.get(str(route))
    dimensions = _VIEWPORTS.get(str(viewport))
    if config is None or dimensions is None:
        return False, ["route_or_viewport_invalid"]
    width, height = dimensions
    exact_values = {
        "label": config["label"], "risk_focus": config["risk"],
        "width": width, "height": height, "expected_heading": config["heading"],
        "heading_text": config["heading"], "expected_anchor": config["anchor"],
        "motion_marker_name": config["marker"], "motion_marker_minimum": config["minimum"],
    }
    for key, expected in exact_values.items():
        if row.get(key) != expected or (isinstance(expected, int) and type(row.get(key)) is not int):
            reasons.append(f"{key}_invalid")
    if not _valid_local_url(row.get("url"), config["fragment"]):
        reasons.append("url_invalid")
    if row.get("status") not in {"passed", "review_required"} or not isinstance(row.get("status"), str):
        reasons.append("status_invalid")
    for key in ("visual_qa_complete", "performance_trace_complete"):
        if type(row.get(key)) is not bool:
            reasons.append(f"{key}_type_invalid")
    if type(row.get("visual_settle_wait_ms")) is not int or row.get("visual_settle_wait_ms") not in {80, 500}:
        reasons.append("visual_settle_wait_ms_invalid")
    expected_budget = _PERFORMANCE_BUDGETS["candidate_radar_first_stable_us"] if route == "#candidates" else _PERFORMANCE_BUDGETS["route_transition_observed_us"]
    integer_limits = {
        "route_transition_observed_us": (0, expected_budget),
        "route_transition_budget_us": (expected_budget, expected_budget),
        "long_task_over_50ms_count": (0, 0),
        "largest_motion_layout_shift_ppm": (0, _PERFORMANCE_BUDGETS["largest_motion_layout_shift_ppm"]),
        "clipped_count": (0, 0), "horizontal_overflow_px": (0, 0),
        "overlap_count": (0, 0), "unnamed_interactive_count": (0, 0),
        "concealed_motion_content_count": (0, 0),
    }
    for key, (minimum, maximum) in integer_limits.items():
        if type(row.get(key)) is not int or not minimum <= row[key] <= maximum:
            reasons.append(f"{key}_budget_failed")
    for key in (
        "expected_heading_paint_visible", "expected_anchor_ready", "expected_anchor_paint_visible", "expected_anchor_sticky_clearance",
        "route_cache_ready", "route_cache_not_busy", "route_cache_shell_visible",
        "route_cache_overlay_absent", "route_cache_not_degraded", "route_cache_content_visible", "motion_marker_minimum_ready",
        "long_task_observer_ready", "layout_shift_observer_ready", "performance_trace_complete",
    ):
        if type(row.get(key)) is not bool or row.get(key) is not True:
            reasons.append(f"{key}_invalid")
    boundary_required = route in {"#home", "#next-session-chart", "#candidates", "#tasks"}
    if type(row.get("route_cache_boundary_required")) is not bool or row.get("route_cache_boundary_required") is not boundary_required:
        reasons.append("route_cache_boundary_required_invalid")
    if type(row.get("route_cache_boundary_present")) is not bool or row.get("route_cache_boundary_present") is not boundary_required:
        reasons.append("route_cache_boundary_present_invalid")
    for key in ("visible_element_count", "audited_first_viewport_element_count"):
        if type(row.get(key)) is not int or row.get(key) < 1:
            reasons.append(f"{key}_invalid")
    if type(row.get("navigation_animation_count")) is not int or row.get("navigation_animation_count") < 1:
        reasons.append("navigation_animation_count_invalid")
    if type(row.get("navigation_animation_wait_completed")) is not bool or row.get("navigation_animation_wait_completed") is not True:
        reasons.append("navigation_animation_wait_incomplete")
    markers = row.get("motion_markers")
    if not _exact_keys(markers, _MARKER_KEYS) or any(type(value) is not int or value < 0 for value in markers.values()):
        reasons.append("motion_markers_invalid")
    elif markers.get(config["marker"], 0) < config["minimum"]:
        reasons.append("motion_marker_minimum_failed")
    ledger = row.get("request_ledger")
    if not isinstance(ledger, list) or type(row.get("request_count")) is not int or row.get("request_count") != len(ledger):
        reasons.append("request_ledger_count_invalid")
    elif any(not _network_entry_valid(item, phase="route", route=str(route), viewport=str(viewport)) for item in ledger):
        reasons.append("request_ledger_invalid")
    if type(row.get("post_request_count")) is not int or row.get("post_request_count") != 0 or row.get("post_request_urls") != []:
        reasons.append("post_request_silence_invalid")
    count_rows = {
        "clipped_count": "clipped_rows",
        "offscreen_count": "offscreen_rows",
        "overlap_count": "overlap_rows",
        "unnamed_interactive_count": "unnamed_interactive_rows",
        "concealed_motion_content_count": "concealed_motion_content_rows",
    }
    for count_key, rows_key in count_rows.items():
        nested = row.get(rows_key)
        if not isinstance(nested, list) or type(row.get(count_key)) is not int or row[count_key] != len(nested):
            reasons.append(f"{rows_key}_count_or_type_invalid")
            continue
        if rows_key == "overlap_rows":
            if any(not _exact_keys(item, _OVERLAP_ROW_KEYS) or not _element_row_valid(item.get("left")) or not _element_row_valid(item.get("right")) for item in nested):
                reasons.append("overlap_rows_schema_invalid")
        elif any(not _element_row_valid(item) for item in nested):
            reasons.append(f"{rows_key}_schema_invalid")
    for key in ("clipped_rows", "overlap_rows", "unnamed_interactive_rows", "concealed_motion_content_rows"):
        if row.get(key) != []:
            reasons.append(f"{key}_not_empty")
    for key in ("visible_element_count", "audited_first_viewport_element_count", "offscreen_count"):
        if type(row.get(key)) is not int or row.get(key) < 0:
            reasons.append(f"{key}_invalid")
    screenshot = row.get("screenshot_path")
    route_name = str(route).removeprefix("#")
    if not isinstance(screenshot, str) or not re.fullmatch(
        rf"[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}T[0-9]{{2}}-[0-9]{{2}}-[0-9]{{2}}-[0-9]{{3}}Z-(normal|reduced)/{re.escape(str(viewport))}/{re.escape(route_name)}\.png",
        screenshot,
    ):
        reasons.append("screenshot_path_invalid")
    return not reasons, reasons


def validate_current_motion_evidence(
    evidence_root: Path,
    *,
    expected_head_full: str | None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Validate the unique latest current-head normal/reduced pair, read-only."""

    motion_root = evidence_root / "motion_qa"
    trust_dir = motion_root / TRUST_DIR_NAME
    key_path = trust_dir / KEY_FILE_NAME
    state_path = trust_dir / STATE_FILE_NAME
    anchor_path = trust_dir / ANCHOR_FILE_NAME
    identity_path = motion_root / IDENTITY_FILE_NAME
    terminal_path = motion_root / TERMINAL_FILE_NAME
    blockers: list[str] = []
    if not canonical_vector_valid():
        blockers.append("canonicalization_self_test_failed")
    if not isinstance(expected_head_full, str) or not _HEAD_FULL.fullmatch(expected_head_full):
        blockers.append("expected_head_full_invalid")
    try:
        trust_stat = os.lstat(trust_dir)
        if not stat.S_ISDIR(trust_stat.st_mode) or stat.S_ISLNK(trust_stat.st_mode) or stat.S_IMODE(trust_stat.st_mode) != 0o700:
            blockers.append("runner_trust_dir_missing_or_mode_invalid")
    except OSError:
        blockers.append("runner_trust_dir_missing_or_mode_invalid")
    lock_path = trust_dir / "append.lock"
    try:
        os.lstat(lock_path)
        blockers.append("runner_write_in_progress")
    except OSError:
        pass
    key_opened = _secure_read(key_path, mode=0o600)
    key = key_opened[0] if key_opened is not None else b""
    if len(key) != 32:
        blockers.append("runner_key_missing_or_invalid")
    identity = _read_json(identity_path, mode=0o600)
    if not _exact_keys(identity, _IDENTITY_KEYS):
        blockers.append("runner_installation_identity_schema_invalid")
        identity = {}
    unsigned_identity = {name: identity.get(name) for name in sorted(_IDENTITY_KEYS - {"identity_mac"})}
    try:
        expected_identity_mac = hmac.new(key, _canonical_bytes(unsigned_identity), hashlib.sha256).hexdigest() if len(key) == 32 else ""
    except ValueError:
        expected_identity_mac = ""
    if not (
        identity.get("schema_version") == IDENTITY_SCHEMA
        and isinstance(identity.get("installation_id"), str)
        and _HEX_64.fullmatch(identity["installation_id"])
        and _utc_timestamp(identity.get("created_at"))
        and isinstance(identity.get("identity_mac"), str)
        and hmac.compare_digest(identity.get("identity_mac", ""), expected_identity_mac)
    ):
        blockers.append("runner_installation_identity_invalid")
    installation_id = str(identity.get("installation_id") or "")
    state = _read_json(state_path, mode=0o600)
    if not _exact_keys(state, _STATE_KEYS):
        blockers.append("runner_state_schema_fields_invalid")
        state = {}
    if state.get("schema_version") != STATE_SCHEMA:
        blockers.append("runner_state_schema_version_invalid")
    if not _utc_timestamp(state.get("updated_at")):
        blockers.append("runner_state_updated_at_invalid")
    events = state.get("events") if isinstance(state.get("events"), list) else []
    if not isinstance(state.get("events"), list):
        blockers.append("runner_state_events_invalid")

    previous_mac = "0" * 64
    previous_created_at = ""
    valid_events: list[Mapping[str, Any]] = []
    report_relpaths: set[str] = set()
    for index, event in enumerate(events, start=1):
        if not _exact_keys(event, _EVENT_KEYS):
            blockers.append("runner_event_schema_fields_invalid")
            break
        assert isinstance(event, Mapping)
        if event.get("schema_version") != EVENT_SCHEMA or type(event.get("sequence_no")) is not int or event.get("sequence_no") != index:
            blockers.append("runner_event_identity_invalid")
        if event.get("previous_event_mac") != previous_mac:
            blockers.append("runner_event_chain_invalid")
        if not _utc_timestamp(event.get("created_at")):
            blockers.append("runner_event_created_at_invalid")
        elif previous_created_at and str(event["created_at"]) < previous_created_at:
            blockers.append("runner_event_created_at_not_monotonic")
        for name in (
            "report_digest", "frontend_source_digest", "build_identity_digest",
            "dist_manifest_digest", "entry_graph_digest", "frontend_service_identity_digest",
            "package_identity_digest", "previous_event_mac", "event_mac",
        ):
            if not isinstance(event.get(name), str) or not _HEX_64.fullmatch(event[name]):
                blockers.append(f"runner_event_{name}_invalid")
        if not isinstance(event.get("head_full"), str) or not _HEAD_FULL.fullmatch(event["head_full"]):
            blockers.append("runner_event_head_invalid")
        if event.get("run_mode") not in {"normal", "reduced"}:
            blockers.append("runner_event_mode_invalid")
        if _safe_relative_path(motion_root, event.get("report_relpath")) is None or event.get("report_relpath") in report_relpaths:
            blockers.append("runner_event_report_path_invalid_or_reused")
        try:
            expected_mac = hmac.new(key, _canonical_bytes(_event_without_mac(event)), hashlib.sha256).hexdigest() if len(key) == 32 else ""
        except ValueError:
            expected_mac = ""
        if not hmac.compare_digest(str(event.get("event_mac") or ""), expected_mac):
            blockers.append("runner_event_mac_invalid")
        previous_mac = str(event.get("event_mac") or "")
        previous_created_at = str(event.get("created_at") or "")
        report_relpaths.add(str(event.get("report_relpath") or ""))
        valid_events.append(event)
    if events and state.get("updated_at") != events[-1].get("created_at"):
        blockers.append("runner_state_updated_at_not_latest_event")

    anchor = _read_json(anchor_path, mode=0o600)
    if not _exact_keys(anchor, _ANCHOR_KEYS):
        blockers.append("runner_high_water_anchor_schema_invalid")
        anchor = {}
    unsigned_anchor = {key_name: anchor.get(key_name) for key_name in sorted(_ANCHOR_KEYS - {"anchor_mac"})}
    try:
        expected_anchor_mac = hmac.new(key, _canonical_bytes(unsigned_anchor), hashlib.sha256).hexdigest() if len(key) == 32 else ""
        state_digest = _digest(state) if _exact_keys(state, _STATE_KEYS) else ""
    except ValueError:
        expected_anchor_mac = ""
        state_digest = ""
    if not (
        anchor.get("schema_version") == ANCHOR_SCHEMA
        and anchor.get("installation_id") == installation_id
        and type(anchor.get("sequence_no")) is int and anchor.get("sequence_no") == len(events)
        and anchor.get("updated_at") == state.get("updated_at")
        and anchor.get("latest_event_mac") == (events[-1].get("event_mac") if events else "0" * 64)
        and anchor.get("state_digest") == state_digest
        and isinstance(anchor.get("anchor_mac"), str)
        and hmac.compare_digest(anchor.get("anchor_mac", ""), expected_anchor_mac)
    ):
        blockers.append("runner_high_water_anchor_invalid_or_rollback_detected")

    terminal = _read_json(terminal_path, mode=0o600)
    if not _exact_keys(terminal, _TERMINAL_KEYS):
        blockers.append("runner_terminal_high_water_schema_invalid")
        terminal = {}
    unsigned_terminal = {name: terminal.get(name) for name in sorted(_TERMINAL_KEYS - {"terminal_mac"})}
    try:
        expected_terminal_mac = hmac.new(key, _canonical_bytes(unsigned_terminal), hashlib.sha256).hexdigest() if len(key) == 32 else ""
        anchor_digest = _digest(anchor) if _exact_keys(anchor, _ANCHOR_KEYS) else ""
    except ValueError:
        expected_terminal_mac = ""
        anchor_digest = ""
    if not (
        terminal.get("schema_version") == TERMINAL_SCHEMA
        and terminal.get("installation_id") == installation_id
        and type(terminal.get("sequence_no")) is int
        and terminal.get("sequence_no") == len(events)
        and terminal.get("updated_at") == state.get("updated_at")
        and terminal.get("latest_event_mac") == (events[-1].get("event_mac") if events else "0" * 64)
        and terminal.get("state_digest") == state_digest
        and terminal.get("anchor_digest") == anchor_digest
        and isinstance(terminal.get("terminal_mac"), str)
        and hmac.compare_digest(terminal.get("terminal_mac", ""), expected_terminal_mac)
    ):
        blockers.append("runner_terminal_high_water_invalid_or_rollback_detected")

    latest_by_mode: dict[str, Mapping[str, Any]] = {}
    if isinstance(expected_head_full, str):
        for event in valid_events:
            if event.get("head_full") == expected_head_full and event.get("run_mode") in {"normal", "reduced"}:
                latest_by_mode[str(event["run_mode"])] = event
    if set(latest_by_mode) != {"normal", "reduced"}:
        blockers.append("current_head_normal_reduced_pair_missing")
    terminal_pair = events[-2:] if len(events) >= 2 else []
    if not (
        len(terminal_pair) == 2
        and {event.get("run_mode") for event in terminal_pair} == {"normal", "reduced"}
        and all(event.get("head_full") == expected_head_full for event in terminal_pair)
        and {event.get("event_mac") for event in terminal_pair}
        == {event.get("event_mac") for event in latest_by_mode.values()}
    ):
        blockers.append("current_head_pair_not_terminal_high_water")

    reports: dict[str, Mapping[str, Any]] = {}
    selected_paths: set[Path] = set()
    for mode in ("normal", "reduced"):
        event = latest_by_mode.get(mode)
        if event is None:
            continue
        report_path = _safe_relative_path(motion_root, event.get("report_relpath"))
        if report_path is None:
            continue
        selected_paths.add(report_path)
        report = _read_json(report_path, mode=0o600)
        if not _exact_keys(report, _REPORT_KEYS):
            blockers.append(f"{mode}:report_schema_fields_invalid")
            continue
        assert isinstance(report, Mapping)
        basic = {
            "schema_version": REPORT_SCHEMA, "scope": "explicit_local_browser_visual_performance_run",
            "expected_head_full": expected_head_full, "head_full": expected_head_full,
            "worktree_clean": True, "run_mode": mode, "reduced_motion": mode == "reduced",
            "artifact_root": ".stock_ming_3/motion_qa", "selected_route": "all",
            "route_count": 6, "viewport_count": 4, "qa_matrix_count": 24,
            "cache_only": True, "starts_no_servers": True, "local_urls_only": True,
            "external_calls_triggered": False, "tushare_called": False,
            "deepseek_called": False, "github_called": False,
            "does_not_execute_trades": True, "does_not_modify_strategy_action": True,
            "warmup_navigation_count": 4, "service_workers_blocked": True,
            "request_failed_count": 0, "websocket_count": 0,
        }
        for name, expected in basic.items():
            if report.get(name) != expected or (isinstance(expected, bool) and type(report.get(name)) is not bool) or (isinstance(expected, int) and not isinstance(expected, bool) and type(report.get(name)) is not int):
                blockers.append(f"{mode}:report_{name}_invalid")
        if report.get("run_mode") != mode:
            blockers.append(f"{mode}:report_mode_mismatch")
        if not isinstance(report.get("run_id"), str) or not _RUN_ID.fullmatch(report["run_id"]) or not report["run_id"].endswith(f"-{mode}"):
            blockers.append(f"{mode}:report_run_id_invalid")
        if not _utc_timestamp(report.get("generated_at")) or report.get("generated_at") != event.get("created_at"):
            blockers.append(f"{mode}:report_timestamp_invalid")
        if not _valid_local_url(report.get("base_url")):
            blockers.append(f"{mode}:report_base_url_invalid")
        if report.get("performance_budgets") != _PERFORMANCE_BUDGETS:
            blockers.append(f"{mode}:report_budgets_invalid")
        for name in ("frontend_source_digest", "build_identity_digest", "report_digest"):
            if not isinstance(report.get(name), str) or not _HEX_64.fullmatch(report[name]):
                blockers.append(f"{mode}:report_{name}_invalid")
        try:
            recomputed_digest = _digest(_report_without_seals(report))
        except ValueError:
            recomputed_digest = ""
        if not hmac.compare_digest(str(report.get("report_digest") or ""), recomputed_digest) or report.get("report_digest") != event.get("report_digest"):
            blockers.append(f"{mode}:report_digest_or_event_binding_invalid")
        dist_manifest = report.get("dist_manifest")
        if not _dist_manifest_valid(dist_manifest):
            blockers.append(f"{mode}:dist_manifest_invalid")
            dist_manifest = {}
        service_identity = report.get("frontend_service_identity")
        if not _service_identity_valid(
            service_identity,
            base_url=report.get("base_url"),
            manifest_digest=dist_manifest.get("manifest_digest"),
        ):
            blockers.append(f"{mode}:frontend_service_identity_invalid")
            service_identity = {}
        fastapi_identity = report.get("fastapi_service_identity")
        if not _fastapi_identity_valid(fastapi_identity):
            blockers.append(f"{mode}:fastapi_service_identity_invalid")
            fastapi_identity = {}
        package_binding = report.get("package_binding")
        if not _package_binding_valid(package_binding, expected_head_full=expected_head_full):
            blockers.append(f"{mode}:package_binding_invalid")
            package_binding = {}
        event_bindings = {
            "head_full": report.get("head_full"),
            "run_mode": report.get("run_mode"),
            "frontend_source_digest": report.get("frontend_source_digest"),
            "build_identity_digest": report.get("build_identity_digest"),
            "dist_manifest_digest": dist_manifest.get("manifest_digest"),
            "entry_graph_digest": dist_manifest.get("entry_graph_digest"),
            "frontend_service_identity_digest": service_identity.get("identity_digest"),
            "package_identity_digest": package_binding.get("identity_digest"),
        }
        for name, observed in event_bindings.items():
            if observed != event.get(name):
                blockers.append(f"{mode}:report_event_{name}_mismatch")
        attestation = report.get("runner_attestation")
        if not _exact_keys(attestation, _ATTESTATION_KEYS) or not (
            attestation.get("sequence_no") == event.get("sequence_no")
            and attestation.get("previous_event_mac") == event.get("previous_event_mac")
            and attestation.get("event_mac") == event.get("event_mac")
            and attestation.get("state_schema_version") == STATE_SCHEMA
            and attestation.get("anchor_schema_version") == ANCHOR_SCHEMA
            and attestation.get("identity_schema_version") == IDENTITY_SCHEMA
            and attestation.get("terminal_schema_version") == TERMINAL_SCHEMA
        ):
            blockers.append(f"{mode}:report_attestation_invalid")

        rows = report.get("rows")
        recomputed_passes: list[bool] = []
        matrix: set[tuple[str, str]] = set()
        if not isinstance(rows, list) or len(rows) != 24:
            blockers.append(f"{mode}:report_rows_invalid")
            rows = []
        for row in rows:
            passed, reasons = _row_recomputed_pass(row)
            recomputed_passes.append(passed)
            if isinstance(row, Mapping):
                matrix.add((str(row.get("route")), str(row.get("viewport"))))
                if row.get("status") != ("passed" if passed else "review_required") or type(row.get("visual_qa_complete")) is not bool or row.get("visual_qa_complete") is not passed:
                    blockers.append(f"{mode}:row_claim_mismatch:{row.get('route')}:{row.get('viewport')}")
            for reason in reasons:
                blockers.append(f"{mode}:row:{row.get('route') if isinstance(row, Mapping) else 'invalid'}:{row.get('viewport') if isinstance(row, Mapping) else 'invalid'}:{reason}")
        expected_matrix = {(route, viewport) for route in _ROUTES for viewport in _VIEWPORTS}
        if matrix != expected_matrix:
            blockers.append(f"{mode}:exact_route_viewport_matrix_invalid")
        passed_count = sum(recomputed_passes)
        report_claims = {
            "passed_count": passed_count,
            "review_required_count": 24 - passed_count,
            "console_error_count": len(report.get("errors")) if isinstance(report.get("errors"), list) else -1,
            "visual_qa_complete": passed_count == 24 and report.get("errors") == [],
            "browser_performance_verified": passed_count == 24 and report.get("errors") == [],
            "status": "motion_browser_qa_passed" if passed_count == 24 and report.get("errors") == [] else "motion_browser_qa_review_required",
        }
        for name, expected in report_claims.items():
            if report.get(name) != expected or (isinstance(expected, bool) and type(report.get(name)) is not bool) or (isinstance(expected, int) and not isinstance(expected, bool) and type(report.get(name)) is not int):
                blockers.append(f"{mode}:report_recomputed_{name}_mismatch")

        warmup = report.get("warmup_request_ledger")
        if not isinstance(warmup, list) or type(report.get("warmup_request_count")) is not int or report.get("warmup_request_count") != len(warmup):
            blockers.append(f"{mode}:warmup_request_ledger_invalid")
            warmup = []
        elif any(not _network_entry_valid(item, phase="warmup", route="#health", viewport=str(item.get("viewport")) if isinstance(item, Mapping) else "") for item in warmup):
            blockers.append(f"{mode}:warmup_request_entry_invalid")
        manifest_ledger = report.get("manifest_request_ledger")
        if not isinstance(manifest_ledger, list) or type(report.get("manifest_request_count")) is not int or report.get("manifest_request_count") != len(manifest_ledger):
            blockers.append(f"{mode}:manifest_request_ledger_invalid")
            manifest_ledger = []
        elif any(not _network_entry_valid(item, phase="manifest", route="#manifest", viewport=str(item.get("viewport")) if isinstance(item, Mapping) else "") for item in manifest_ledger):
            blockers.append(f"{mode}:manifest_request_entry_invalid")
        warmup_navigation = report.get("warmup_navigation_ledger")
        if not isinstance(warmup_navigation, list) or len(warmup_navigation) != 4:
            blockers.append(f"{mode}:warmup_navigation_ledger_invalid")
            warmup_navigation = []
        else:
            observed_viewports: set[str] = set()
            for item in warmup_navigation:
                if not _exact_keys(item, _WARMUP_NAVIGATION_KEYS):
                    blockers.append(f"{mode}:warmup_navigation_entry_invalid")
                    continue
                viewport = str(item.get("viewport"))
                observed_viewports.add(viewport)
                expected_warmup = str(report.get("base_url") or "").rstrip("/") + "/#health"
                if item.get("sequence_no") != 1 or viewport not in _VIEWPORTS or item.get("url") != expected_warmup:
                    blockers.append(f"{mode}:warmup_navigation_entry_invalid:{viewport}")
            if observed_viewports != set(_VIEWPORTS):
                blockers.append(f"{mode}:warmup_navigation_viewport_matrix_invalid")
        if report.get("late_network_events") != []:
            blockers.append(f"{mode}:late_network_events_detected")
        if report.get("inflight_request_ids") != []:
            blockers.append(f"{mode}:inflight_requests_detected")

        route_events = [
            entry
            for row in rows
            if isinstance(row, Mapping) and isinstance(row.get("request_ledger"), list)
            for entry in row["request_ledger"]
        ]
        all_network_events = list(warmup) + list(manifest_ledger) + route_events
        for pairing_blocker in _network_pairing_blockers(all_network_events):
            blockers.append(f"{mode}:{pairing_blocker}")
        for item in all_network_events:
            if (
                isinstance(item, Mapping)
                and item.get("event_type") == "response"
                and item.get("purpose") in {"fastapi_health_identity", "fastapi_cache_read"}
                and not _fastapi_response_semantic_valid(item)
            ):
                blockers.append(f"{mode}:fastapi_response_envelope_safety_invalid:{item.get('request_id') or 'missing'}")
        if type(report.get("network_event_count")) is not int or report.get("network_event_count") != len(all_network_events):
            blockers.append(f"{mode}:network_event_count_invalid")
        request_failed_count = sum(1 for item in all_network_events if isinstance(item, Mapping) and item.get("event_type") == "requestfailed")
        websocket_count = sum(1 for item in all_network_events if isinstance(item, Mapping) and item.get("event_type") == "websocket")
        if report.get("request_failed_count") != request_failed_count or request_failed_count != 0:
            blockers.append(f"{mode}:request_failed_event_detected")
        if report.get("websocket_count") != websocket_count or websocket_count != 0:
            blockers.append(f"{mode}:websocket_event_detected")
        event_indices_by_viewport: dict[str, list[int]] = {name: [] for name in _VIEWPORTS}
        for item in all_network_events:
            if isinstance(item, Mapping) and item.get("viewport") in event_indices_by_viewport and type(item.get("event_index")) is int:
                event_indices_by_viewport[str(item["viewport"])].append(item["event_index"])
        for viewport, indices in event_indices_by_viewport.items():
            if not indices or sorted(indices) != list(range(1, max(indices) + 1)) or len(indices) != len(set(indices)):
                blockers.append(f"{mode}:network_event_sequence_invalid:{viewport}")
            warmup_roots = [
                item for item in warmup
                if isinstance(item, Mapping) and item.get("viewport") == viewport
                and item.get("path") == "/" and item.get("method") == "GET"
            ]
            if sum(1 for item in warmup_roots if item.get("event_type") == "request") != 1 or sum(
                1 for item in warmup_roots if item.get("event_type") == "response"
            ) != 1:
                blockers.append(f"{mode}:warmup_health_navigation_network_identity_invalid:{viewport}")

        manifest_entries = {
            str(item.get("path")): item
            for item in dist_manifest.get("entries", [])
            if isinstance(item, Mapping)
        }
        for item in all_network_events:
            if not isinstance(item, Mapping) or item.get("event_type") != "response":
                continue
            content_type = str(item.get("content_type") or "").split(";", 1)[0].strip().lower()
            if content_type not in {"text/html", "text/javascript", "application/javascript", "text/css"}:
                continue
            dist_path = str(item.get("dist_path") or "")
            expected = manifest_entries.get(dist_path)
            if not (
                expected
                and item.get("expected_dist_sha256") == expected.get("sha256")
                and item.get("body_sha256") == expected.get("sha256")
                and item.get("body_size_bytes") == expected.get("size_bytes")
                and item.get("body_matches_dist") is True
            ):
                blockers.append(f"{mode}:served_static_response_not_bound_to_dist:{dist_path or 'missing'}")
        for viewport in _VIEWPORTS:
            covered = {
                str(item.get("dist_path"))
                for item in all_network_events
                if isinstance(item, Mapping)
                and item.get("event_type") == "response"
                and item.get("viewport") == viewport
                and item.get("body_matches_dist") is True
            }
            if covered != set(dist_manifest.get("entry_graph", [])):
                blockers.append(f"{mode}:served_entry_import_graph_incomplete:{viewport}")

        raw = report.get("raw_trace") if isinstance(report.get("raw_trace"), Mapping) else {}
        raw_path = _safe_relative_path(motion_root, raw.get("path"))
        raw_opened = _secure_read(raw_path, mode=0o600) if raw_path is not None else None
        if raw_opened is None:
            blockers.append(f"{mode}:raw_trace_missing")
        else:
            if type(raw.get("size_bytes")) is not int or raw.get("size_bytes") != len(raw_opened[0]) or raw.get("sha256") != _file_digest_bytes(raw_opened[0]):
                blockers.append(f"{mode}:raw_trace_size_or_digest_mismatch")
            trace = _read_json(raw_path, mode=0o600)
            if not _exact_keys(trace, _TRACE_KEYS) or not (
                trace.get("schema_version") == TRACE_SCHEMA and trace.get("generated_at") == report.get("generated_at")
                and trace.get("head_full") == expected_head_full and trace.get("run_mode") == mode
                and trace.get("frontend_source_digest") == report.get("frontend_source_digest")
                and trace.get("build_identity_digest") == report.get("build_identity_digest")
                and type(trace.get("row_count")) is int and trace.get("row_count") == 24
                and trace.get("rows") == report.get("rows")
                and type(trace.get("warmup_request_count")) is int and trace.get("warmup_request_count") == len(warmup)
                and trace.get("warmup_request_ledger") == warmup
                and trace.get("warmup_navigation_count") == 4
                and trace.get("warmup_navigation_ledger") == warmup_navigation
                and trace.get("manifest_request_count") == len(manifest_ledger)
                and trace.get("manifest_request_ledger") == manifest_ledger
                and trace.get("late_network_events") == []
                and trace.get("inflight_request_ids") == []
                and trace.get("network_event_count") == len(all_network_events)
                and trace.get("request_failed_count") == 0
                and trace.get("websocket_count") == 0
                and trace.get("dist_manifest_digest") == dist_manifest.get("manifest_digest")
                and trace.get("frontend_service_identity_digest") == service_identity.get("identity_digest")
                and trace.get("fastapi_service_identity_digest") == fastapi_identity.get("identity_digest")
                and trace.get("package_identity_digest") == package_binding.get("identity_digest")
                and trace.get("error_count") == 0 and trace.get("errors") == []
            ):
                blockers.append(f"{mode}:raw_trace_binding_invalid")

        screenshots = report.get("screenshots")
        screenshot_bindings: set[tuple[str, str, str]] = set()
        if not isinstance(screenshots, list) or len(screenshots) != 24:
            blockers.append(f"{mode}:screenshots_invalid")
            screenshots = []
        for item in screenshots:
            if not _exact_keys(item, _SCREENSHOT_KEYS):
                blockers.append(f"{mode}:screenshot_schema_invalid")
                continue
            route = str(item.get("route"))
            viewport = str(item.get("viewport"))
            dimensions = _VIEWPORTS.get(viewport)
            path = _safe_relative_path(motion_root, item.get("path"))
            opened = _secure_read(path, mode=0o600, max_bytes=_MAX_PNG_FILE_BYTES) if path is not None else None
            if route not in _ROUTES or dimensions is None or opened is None:
                blockers.append(f"{mode}:screenshot_missing_or_unsafe")
                continue
            decoded = _decode_png(opened[0])
            if not (
                decoded == dimensions and item.get("width") == dimensions[0] and item.get("height") == dimensions[1]
                and type(item.get("width")) is int and type(item.get("height")) is int
                and type(item.get("size_bytes")) is int and item.get("size_bytes") == len(opened[0])
                and item.get("sha256") == _file_digest_bytes(opened[0])
            ):
                blockers.append(f"{mode}:screenshot_png_dimension_or_digest_invalid")
            if item.get("sha256") != _file_digest_bytes(opened[0]):
                blockers.append(f"{mode}:screenshot_digest_mismatch")
            screenshot_bindings.add((route, viewport, str(item.get("path"))))
        row_bindings = {(str(row.get("route")), str(row.get("viewport")), str(row.get("screenshot_path"))) for row in rows if isinstance(row, Mapping)}
        if screenshot_bindings != row_bindings or len(screenshot_bindings) != 24:
            blockers.append(f"{mode}:screenshot_row_binding_invalid")
        reports[mode] = report

    if motion_root.is_dir() and not motion_root.is_symlink():
        for current, dirs, files in os.walk(motion_root, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(current) / name).is_symlink()]
            if "motion_browser_qa_report.json" not in files:
                continue
            path = Path(current) / "motion_browser_qa_report.json"
            if path in selected_paths:
                continue
            candidate = _read_json(path)
            if isinstance(candidate, Mapping) and candidate.get("head_full") == expected_head_full:
                registered = {_safe_relative_path(motion_root, event.get("report_relpath")) for event in valid_events if event.get("head_full") == expected_head_full}
                if path not in registered:
                    blockers.append("unregistered_current_head_report_detected")

    if len(reports) == 2:
        normal, reduced = reports["normal"], reports["reduced"]
        for name in (
            "head_full", "frontend_source_digest", "build_identity_digest", "base_url",
            "dist_manifest", "package_binding",
        ):
            if normal.get(name) != reduced.get(name):
                blockers.append(f"pair_{name}_mismatch")
        if project_root is not None:
            current_identity = _frontend_identity(project_root)
            if current_identity is None:
                blockers.append("current_frontend_source_or_build_missing")
            else:
                if normal.get("frontend_source_digest") != current_identity[0]:
                    blockers.append("current_frontend_source_digest_mismatch")
                if normal.get("build_identity_digest") != current_identity[1]:
                    blockers.append("current_frontend_build_identity_mismatch")
                if normal.get("dist_manifest") != current_identity[2]:
                    blockers.append("current_dist_manifest_mismatch")
            if (project_root / ".git").exists():
                if not isinstance(expected_head_full, str) or not _repository_is_exact_clean(project_root, expected_head_full):
                    blockers.append("current_repository_head_or_cleanliness_mismatch")
                current_package = _formal_package_binding(evidence_root, str(expected_head_full or ""))
                if current_package is None:
                    blockers.append("current_formal_package_binding_missing_or_invalid")
                elif normal.get("package_binding") != current_package:
                    blockers.append("current_formal_package_binding_mismatch")

    blockers = sorted(set(blockers))
    ready = not blockers and len(reports) == 2
    validated_route_rows: dict[str, list[dict[str, Any]]] = {route: [] for route in _ROUTES}
    if ready:
        for mode in ("normal", "reduced"):
            report = reports[mode]
            for row in report.get("rows", []):
                if not isinstance(row, Mapping) or row.get("route") not in validated_route_rows:
                    continue
                validated_route_rows[str(row["route"])].append(
                    {
                        "run_id": report.get("run_id"),
                        "generated_at": report.get("generated_at"),
                        "reduced_motion": mode == "reduced",
                        "route": row.get("route"),
                        "label": row.get("label"),
                        "viewport": row.get("viewport"),
                        "width": row.get("width"),
                        "height": row.get("height"),
                        "status": row.get("status"),
                        "visual_qa_complete": row.get("visual_qa_complete"),
                        "performance_trace_complete": row.get("performance_trace_complete"),
                        "route_transition_observed_us": row.get("route_transition_observed_us"),
                        "route_transition_budget_us": row.get("route_transition_budget_us"),
                        "long_task_over_50ms_count": row.get("long_task_over_50ms_count"),
                        "largest_motion_layout_shift_ppm": row.get("largest_motion_layout_shift_ppm"),
                        "clipped_count": row.get("clipped_count"),
                        "offscreen_count": row.get("offscreen_count"),
                        "screenshot_path": row.get("screenshot_path"),
                    }
                )
    return {
        "schema_version": "command_center_3_motion_current_head_evidence_validation.v2",
        "status": "motion_current_head_normal_reduced_pair_verified" if ready else "motion_current_head_evidence_blocked",
        "expected_head_full": expected_head_full,
        "motion_current_head_pair_verified": ready,
        "normal_mode_verified": ready and "normal" in reports,
        "reduced_mode_verified": ready and "reduced" in reports,
        "frontend_source_digest": reports.get("normal", {}).get("frontend_source_digest"),
        "build_identity_digest": reports.get("normal", {}).get("build_identity_digest"),
        "dist_manifest_digest": (
            reports.get("normal", {}).get("dist_manifest", {}).get("manifest_digest")
            if isinstance(reports.get("normal", {}).get("dist_manifest"), Mapping)
            else None
        ),
        "package_identity_digest": (
            reports.get("normal", {}).get("package_binding", {}).get("identity_digest")
            if isinstance(reports.get("normal", {}).get("package_binding"), Mapping)
            else None
        ),
        "normal_run_id": reports.get("normal", {}).get("run_id"),
        "reduced_run_id": reports.get("reduced", {}).get("run_id"),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "validated_route_rows": validated_route_rows if ready else {},
        "trust_boundary": "runner_owned_hmac_chain_and_independent_high_water_anchor_same_os_user_with_trust_dir_access_is_trusted",
        "reader_created_or_repaired_trust_material": False,
        "key_or_fingerprint_exposed": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
