from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from server.services import candidate_service, motion_evidence_service, next_session_service, v1_closeout_service


HEAD = "a" * 40
OTHER_HEAD = "b" * 40
SOURCE = "c" * 64
BUILD = "d" * 64
PACKAGE = "e" * 64
ROUTES = ("#home", "#next-session-chart", "#candidates", "#worker", "#tasks", "#audit")
VIEWPORTS = ("desktop", "laptop", "tablet", "mobile")
DIMENSIONS = {"desktop": (1440, 900), "laptop": (1280, 800), "tablet": (834, 1112), "mobile": (390, 844)}
ROUTE_EXPECTATIONS = {
    "#home": ("今日作战台", "#home-p1-symbol-confirm", "state_rail", "home/home-p1-symbol-confirm"),
    "#next-session-chart": ("次日图谱", "#next-session-chart", "route_stage", "next-session-chart"),
    "#candidates": ("下一票雷达", "#candidate-pool", "radar_cluster", "candidates/candidate-pool"),
    "#worker": ("Worker 运行时", ".route-stage", "route_stage", "worker"),
    "#tasks": ("Task Monitor / 任务监控", ".route-stage", "route_stage", "tasks"),
    "#audit": ("调用审计", ".route-stage", "route_stage", "audit"),
}
ROUTE_LABELS = {
    "#home": "Command Center", "#next-session-chart": "Next Session Map",
    "#candidates": "Candidate Radar", "#worker": "Worker Runtime",
    "#tasks": "Task Monitor", "#audit": "Call Ledger Audit",
}
ROUTE_RISKS = {
    "#home": "page staging and status summary clarity",
    "#next-session-chart": "chart update clarity and reduced-motion chart updates",
    "#candidates": "radar result cluster and runtime-budget visibility",
    "#worker": "runtime evidence visibility and production-blocker readability",
    "#tasks": "task phase confirmation and progress readability",
    "#audit": "motion audit rows and warning density",
}


def _dist_manifest() -> dict:
    entries = [
        {"path": "assets/app.css", "sha256": hashlib.sha256(b"css").hexdigest(), "size_bytes": 3, "content_type": "text/css"},
        {"path": "assets/app.js", "sha256": hashlib.sha256(b"js").hexdigest(), "size_bytes": 2, "content_type": "text/javascript"},
        {"path": "index.html", "sha256": hashlib.sha256(b"html").hexdigest(), "size_bytes": 4, "content_type": "text/html"},
    ]
    graph = [item["path"] for item in entries]
    unsigned = {
        "schema_version": motion_evidence_service.DIST_MANIFEST_SCHEMA,
        "entry_html": "index.html",
        "entries": entries,
        "entry_graph": graph,
        "entry_graph_digest": motion_evidence_service._digest(graph),
    }
    return {**unsigned, "manifest_digest": motion_evidence_service._digest(unsigned)}


def _service_identity(manifest: dict) -> dict:
    unsigned = {
        "schema_version": motion_evidence_service.SERVICE_IDENTITY_SCHEMA,
        "listener_pid": 1234,
        "protocol": "http:",
        "hostname": "127.0.0.1",
        "port": "4173",
        "base_url": "http://127.0.0.1:4173",
        "process_cwd": "desktop",
        "command_sha256": "f" * 64,
        "served_root": "desktop/dist",
        "served_root_manifest_digest": manifest["manifest_digest"],
    }
    return {**unsigned, "identity_digest": motion_evidence_service._digest(unsigned)}


def _package_binding(head: str) -> dict:
    unsigned = {
        "schema_version": motion_evidence_service.PACKAGE_BINDING_SCHEMA,
        "head_full": head,
        "build_receipt_sha256": "1" * 64,
        "package_manifest_digest": "2" * 64,
        "artifact_set_sha256": PACKAGE,
        "app_bundle_sha256": "3" * 64,
        "app_executable_sha256": "4" * 64,
        "dmg_sha256": "5" * 64,
        "production_package_complete": True,
    }
    return {**unsigned, "identity_digest": motion_evidence_service._digest(unsigned)}


def _fastapi_identity() -> dict:
    unsigned = {
        "schema_version": motion_evidence_service.FASTAPI_IDENTITY_SCHEMA,
        "endpoint": "http://127.0.0.1:8710/health",
        "status_code": 200,
        "content_type": "application/json",
        "service": "stock-MING Command Center 3.0",
        "response_body_sha256": "6" * 64,
        "response_size_bytes": 1024,
        "health_contract_digest": motion_evidence_service._digest(motion_evidence_service._FASTAPI_HEALTH_CONTRACT),
        "health_schema_valid": True,
    }
    return {**unsigned, "identity_digest": motion_evidence_service._digest(unsigned)}


def _network_entry(
    *, index: int, event_type: str, phase: str, route: str, viewport: str,
    path: str, entry: dict | None,
) -> dict:
    is_response = event_type == "response"
    body = {"index.html": b"html", "assets/app.js": b"js", "assets/app.css": b"css"}.get(entry["path"] if entry else "", b"")
    url_path = "/" if path == "index.html" else f"/{path}"
    request_number = (index + 1) // 2
    session_number = 1 if phase == "warmup" else 2
    return {
        "event_index": index,
        "event_type": event_type,
        "request_id": f"{viewport}:http:{request_number}",
        "session_id": f"{viewport}:{session_number}:{phase}:{route}",
        "phase": phase,
        "route": route,
        "viewport": viewport,
        "method": "GET",
        "url": f"http://127.0.0.1:4173{url_path}",
        "protocol": "http:",
        "hostname": "127.0.0.1",
        "port": "4173",
        "path": url_path,
        "purpose": "vite_preview_dist_resource",
        "allowed": True,
        "status_code": 200 if is_response else None,
        "content_type": entry["content_type"] if is_response and entry else "",
        "body_sha256": hashlib.sha256(body).hexdigest() if is_response else "",
        "body_size_bytes": len(body) if is_response else None,
        "dist_path": entry["path"] if is_response and entry else "",
        "expected_dist_sha256": entry["sha256"] if is_response and entry else "",
        "body_matches_dist": is_response and entry is not None,
        "body_schema_valid": is_response and entry is not None,
        "response_semantic_summary": {},
        "response_semantic_digest": "",
        "failure_text": "",
    }


def _fastapi_semantic_summary(
    *, path: str, body_sha256: str, body_size_bytes: int, status_code: int = 200,
    envelope_state: str = "ok", historical_provenance_count: int = 0,
) -> dict:
    schema, packet, _cache_missing = motion_evidence_service._FASTAPI_CACHE_CONTRACTS[path]
    ledger_apis = motion_evidence_service._FASTAPI_LEDGER_APIS[path]
    summary = {
        "schema_version": motion_evidence_service.FASTAPI_RESPONSE_SEMANTIC_SCHEMA,
        "endpoint": path,
        "method": "GET",
        "status_code": status_code,
        "raw_body_sha256": body_sha256,
        "raw_body_size_bytes": body_size_bytes,
        "envelope_state": envelope_state,
        "envelope_ok": envelope_state == "ok",
        "error_code": "cache_missing" if envelope_state == "cache_missing" else "",
        "data_schema_version": schema,
        "data_packet_key": packet,
        "data_status": "cache_missing" if envelope_state == "cache_missing" else "ready",
        "data_cache_source": "cache_missing" if envelope_state == "cache_missing" else "sqlite",
        "ledger_count": len(ledger_apis),
        "ledger_rows_typed": True,
        "ledger_sources_allowlisted": True,
        "ledger_current_external_count": 0,
        "ledger_current_provider_count": 0,
        "ledger_current_model_count": 0,
        "ledger_current_worker_count": 0,
        "ledger_current_trade_count": 0,
        "task_post_count": 0,
        "data_current_read_flags_valid": True,
        "strict_current_read_contract": path in motion_evidence_service._FASTAPI_STRICT_CURRENT_READ_ENDPOINTS,
        "strict_current_read_valid": True,
        "historical_provenance_count": historical_provenance_count,
        "secret_bearing_field_count": 0,
        "ledger_contract_rows": [
            {
                "api": api,
                "source": path,
                "method": "GET",
                "path": path,
                "external": False,
                "provider": False,
                "model": False,
                "worker": False,
                "trade": False,
                "task_post": False,
                "secret": False,
            }
            for api in ledger_apis
        ],
    }
    if envelope_state == "cache_missing" and path.startswith("/api/packets/"):
        summary["data_schema_version"] = ""
        summary["data_packet_key"] = ""
    return summary


def _health_semantic_summary(*, body_sha256: str, body_size_bytes: int, status_code: int = 200) -> dict:
    return {
        "schema_version": motion_evidence_service.FASTAPI_RESPONSE_SEMANTIC_SCHEMA,
        "endpoint": "/health",
        "method": "GET",
        "status_code": status_code,
        "raw_body_sha256": body_sha256,
        "raw_body_size_bytes": body_size_bytes,
        "envelope_state": "ok",
        "envelope_ok": True,
        "error_code": "",
        "data_schema_version": "",
        "data_packet_key": "",
        "data_status": "healthy",
        "data_cache_source": "local",
        "ledger_count": 1,
        "ledger_rows_typed": True,
        "ledger_sources_allowlisted": True,
        "ledger_current_external_count": 0,
        "ledger_current_provider_count": 0,
        "ledger_current_model_count": 0,
        "ledger_current_worker_count": 0,
        "ledger_current_trade_count": 0,
        "task_post_count": 0,
        "data_current_read_flags_valid": True,
        "strict_current_read_contract": False,
        "strict_current_read_valid": True,
        "historical_provenance_count": 0,
        "secret_bearing_field_count": 0,
        "ledger_contract_rows": [
            {
                "api": "local_health_check",
                "source": "/health",
                "method": "GET",
                "path": "/health",
                "external": False,
                "provider": False,
                "model": False,
                "worker": False,
                "trade": False,
                "task_post": False,
                "secret": False,
            }
        ],
    }


def _fastapi_network_entry(
    *, index: int, event_type: str, viewport: str, path: str = "/api/audit/cache",
) -> dict:
    is_response = event_type == "response"
    body = b'{"call_ledger":[{"external":false}],"data":{},"error":null,"ok":true,"warnings":[]}'
    body_sha256 = hashlib.sha256(body).hexdigest()
    summary = _fastapi_semantic_summary(path=path, body_sha256=body_sha256, body_size_bytes=len(body)) if is_response else {}
    return {
        "event_index": index,
        "event_type": event_type,
        "request_id": f"{viewport}:http:2",
        "session_id": f"{viewport}:1:warmup:#health",
        "phase": "warmup",
        "route": "#health",
        "viewport": viewport,
        "method": "GET",
        "url": f"http://127.0.0.1:8710{path}",
        "protocol": "http:",
        "hostname": "127.0.0.1",
        "port": "8710",
        "path": path,
        "purpose": "fastapi_cache_read",
        "allowed": True,
        "status_code": 200 if is_response else None,
        "content_type": "application/json" if is_response else "",
        "body_sha256": body_sha256 if is_response else "",
        "body_size_bytes": len(body) if is_response else None,
        "dist_path": "",
        "expected_dist_sha256": "",
        "body_matches_dist": False,
        "body_schema_valid": is_response,
        "response_semantic_summary": summary,
        "response_semantic_digest": motion_evidence_service._digest(summary) if is_response else "",
        "failure_text": "",
    }


def _png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    pixels = b"".join(b"\0" + b"\0" * (width * 4) for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")


def _png_bomb(width: int, height: int) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    oversized = b"\0" * (height * (width * 4 + 1) + 4096)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(oversized)) + chunk(b"IEND", b"")


def _write_json(path: Path, value: object, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def _rows(motion_root: Path, run_id: str, mode: str) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    screenshots: list[dict] = []
    for route in ROUTES:
        for viewport in VIEWPORTS:
            width, height = DIMENSIONS[viewport]
            heading, anchor, marker, fragment = ROUTE_EXPECTATIONS[route]
            relpath = f"{run_id}/{viewport}/{route.removeprefix('#')}.png"
            screenshot = motion_root / relpath
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            screenshot.write_bytes(_png(width, height))
            screenshot.chmod(0o600)
            digest = hashlib.sha256(screenshot.read_bytes()).hexdigest()
            screenshots.append(
                {
                    "path": relpath,
                    "sha256": digest,
                    "size_bytes": screenshot.stat().st_size,
                    "route": route,
                    "viewport": viewport,
                    "width": width,
                    "height": height,
                }
            )
            rows.append(
                {
                    "route": route,
                    "label": ROUTE_LABELS[route],
                    "viewport": viewport,
                    "width": width,
                    "height": height,
                    "url": f"http://127.0.0.1:4173/#{fragment}",
                    "risk_focus": ROUTE_RISKS[route],
                    "status": "passed",
                    "visual_qa_complete": True,
                    "performance_trace_complete": True,
                    "route_transition_observed_us": 1,
                    "visual_settle_wait_ms": 80 if mode == "reduced" else 500,
                    "route_transition_budget_us": 1_200_000 if route == "#candidates" else 500_000,
                    "navigation_animation_count": 1,
                    "navigation_animation_wait_completed": True,
                    "long_task_over_50ms_count": 0,
                    "largest_motion_layout_shift_ppm": 0,
                    "visible_element_count": 1,
                    "audited_first_viewport_element_count": 1,
                    "clipped_count": 0,
                    "offscreen_count": 0,
                    "clipped_rows": [],
                    "offscreen_rows": [],
                    "horizontal_overflow_px": 0,
                    "overlap_count": 0,
                    "overlap_rows": [],
                    "unnamed_interactive_count": 0,
                    "unnamed_interactive_rows": [],
                    "concealed_motion_content_count": 0,
                    "concealed_motion_content_rows": [],
                    "expected_heading": heading,
                    "heading_text": heading,
                    "expected_anchor": anchor,
                    "expected_anchor_ready": True,
                    "motion_marker_name": marker,
                    "motion_marker_minimum": 1,
                    "motion_marker_minimum_ready": True,
                    "long_task_observer_ready": True,
                    "layout_shift_observer_ready": True,
                    "request_count": 0,
                    "request_ledger": [],
                    "post_request_count": 0,
                    "post_request_urls": [],
                    "motion_markers": {
                        "route_stage": 1,
                        "motion_surface": 0,
                        "state_rail": 1 if route == "#home" else 0,
                        "chart_frame": 0,
                        "radar_cluster": 1 if route == "#candidates" else 0,
                        "task_panel": 0,
                    },
                    "screenshot_path": relpath,
                }
            )
    return rows, screenshots


def write_attested_pair(
    root: Path,
    *,
    head: str = HEAD,
    modes: tuple[str, str] = ("normal", "reduced"),
    sources: tuple[str, str] = (SOURCE, SOURCE),
    builds: tuple[str, str] = (BUILD, BUILD),
    dist_manifest: dict | None = None,
) -> None:
    motion_root = root / "motion_qa"
    trust = motion_root / motion_evidence_service.TRUST_DIR_NAME
    trust.mkdir(parents=True, mode=0o700)
    trust.chmod(0o700)
    key = b"k" * 32
    installation_id = "9" * 64
    installation_created_at = "2026-07-15T11:59:59.000Z"
    key_path = trust / motion_evidence_service.KEY_FILE_NAME
    key_path.write_bytes(key)
    key_path.chmod(0o600)
    unsigned_identity = {
        "schema_version": motion_evidence_service.IDENTITY_SCHEMA,
        "installation_id": installation_id,
        "created_at": installation_created_at,
    }
    _write_json(
        motion_root / motion_evidence_service.IDENTITY_FILE_NAME,
        {
            **unsigned_identity,
            "identity_mac": hmac.new(key, motion_evidence_service._canonical_bytes(unsigned_identity), hashlib.sha256).hexdigest(),
        },
        mode=0o600,
    )
    events = []
    previous = "0" * 64
    manifest = dist_manifest or _dist_manifest()
    service_identity = _service_identity(manifest)
    fastapi_identity = _fastapi_identity()
    package_binding = _package_binding(head)
    for index, (mode, source, build) in enumerate(zip(modes, sources, builds), start=1):
        stamp = f"2026-07-15T12-00-00-00{index - 1}Z-{mode}"
        generated_at = f"2026-07-15T12:00:00.00{index - 1}Z"
        rows, screenshots = _rows(motion_root, stamp, mode)
        warmup_ledger: list[dict] = []
        manifest_ledger: list[dict] = []
        warmup_navigation: list[dict] = []
        for viewport in VIEWPORTS:
            event_index = 1
            index_entry = next(item for item in manifest["entries"] if item["path"] == "index.html")
            warmup_ledger.append(_network_entry(index=event_index, event_type="request", phase="warmup", route="#health", viewport=viewport, path="index.html", entry=None))
            event_index += 1
            warmup_ledger.append(_network_entry(index=event_index, event_type="response", phase="warmup", route="#health", viewport=viewport, path="index.html", entry=index_entry))
            event_index += 1
            warmup_ledger.append(_fastapi_network_entry(index=event_index, event_type="request", viewport=viewport))
            event_index += 1
            warmup_ledger.append(_fastapi_network_entry(index=event_index, event_type="response", viewport=viewport))
            warmup_navigation.append({"sequence_no": 1, "viewport": viewport, "url": "http://127.0.0.1:4173/#health"})
            for dist_entry in manifest["entries"]:
                event_index += 1
                manifest_ledger.append(_network_entry(index=event_index, event_type="request", phase="manifest", route="#manifest", viewport=viewport, path=dist_entry["path"], entry=None))
                event_index += 1
                manifest_ledger.append(_network_entry(index=event_index, event_type="response", phase="manifest", route="#manifest", viewport=viewport, path=dist_entry["path"], entry=dist_entry))
        all_network_events = warmup_ledger + manifest_ledger
        trace = {
            "schema_version": motion_evidence_service.TRACE_SCHEMA,
            "generated_at": generated_at,
            "head_full": head,
            "run_mode": mode,
            "frontend_source_digest": source,
            "build_identity_digest": build,
            "row_count": 24,
            "rows": rows,
            "warmup_request_count": len(warmup_ledger),
            "warmup_request_ledger": warmup_ledger,
            "warmup_navigation_count": 4,
            "warmup_navigation_ledger": warmup_navigation,
            "manifest_request_count": len(manifest_ledger),
            "manifest_request_ledger": manifest_ledger,
            "late_network_events": [],
            "inflight_request_ids": [],
            "network_event_count": len(all_network_events),
            "request_failed_count": 0,
            "websocket_count": 0,
            "dist_manifest_digest": manifest["manifest_digest"],
            "frontend_service_identity_digest": service_identity["identity_digest"],
            "fastapi_service_identity_digest": fastapi_identity["identity_digest"],
            "package_identity_digest": package_binding["identity_digest"],
            "error_count": 0,
            "errors": [],
        }
        trace_relpath = f"{stamp}/motion_performance_trace.json"
        trace_path = motion_root / trace_relpath
        _write_json(trace_path, trace, mode=0o600)
        unsigned_report = {
            "schema_version": motion_evidence_service.REPORT_SCHEMA,
            "status": "motion_browser_qa_passed",
            "scope": "explicit_local_browser_visual_performance_run",
            "run_id": stamp,
            "generated_at": generated_at,
            "expected_head_full": head,
            "head_full": head,
            "worktree_clean": True,
            "run_mode": mode,
            "reduced_motion": mode == "reduced",
            "base_url": "http://127.0.0.1:4173",
            "artifact_root": ".stock_ming_3/motion_qa",
            "selected_route": "all",
            "frontend_source_digest": source,
            "build_identity_digest": build,
            "route_count": 6,
            "viewport_count": 4,
            "qa_matrix_count": 24,
            "passed_count": 24,
            "review_required_count": 0,
            "console_error_count": 0,
            "visual_qa_complete": True,
            "browser_performance_verified": True,
            "performance_budgets": {
                "route_transition_observed_us": 500_000,
                "largest_motion_layout_shift_ppm": 100_000,
                "long_task_over_50ms_count": 0,
                "candidate_radar_first_stable_us": 1_200_000,
            },
            "visual_acceptance_criteria": ["clarity"],
            "rows": rows,
            "errors": [],
            "warmup_request_count": len(warmup_ledger),
            "warmup_request_ledger": warmup_ledger,
            "warmup_navigation_count": 4,
            "warmup_navigation_ledger": warmup_navigation,
            "manifest_request_count": len(manifest_ledger),
            "manifest_request_ledger": manifest_ledger,
            "late_network_events": [],
            "inflight_request_ids": [],
            "network_event_count": len(all_network_events),
            "request_failed_count": 0,
            "websocket_count": 0,
            "service_workers_blocked": True,
            "dist_manifest": manifest,
            "frontend_service_identity": service_identity,
            "fastapi_service_identity": fastapi_identity,
            "package_binding": package_binding,
            "raw_trace": {
                "path": trace_relpath,
                "sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest(),
                "size_bytes": trace_path.stat().st_size,
            },
            "screenshots": screenshots,
            "cache_only": True,
            "starts_no_servers": True,
            "local_urls_only": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "note": "attested local motion QA",
        }
        report_digest = motion_evidence_service._digest(unsigned_report)
        report_relpath = f"{stamp}/motion_browser_qa_report.json"
        unsigned_event = {
            "schema_version": motion_evidence_service.EVENT_SCHEMA,
            "sequence_no": index,
            "created_at": generated_at,
            "report_relpath": report_relpath,
            "report_digest": report_digest,
            "head_full": head,
            "run_mode": mode,
            "frontend_source_digest": source,
            "build_identity_digest": build,
            "dist_manifest_digest": manifest["manifest_digest"],
            "entry_graph_digest": manifest["entry_graph_digest"],
            "frontend_service_identity_digest": service_identity["identity_digest"],
            "package_identity_digest": package_binding["identity_digest"],
            "previous_event_mac": previous,
        }
        event_mac = hmac.new(
            key,
            motion_evidence_service._canonical_bytes(unsigned_event),
            hashlib.sha256,
        ).hexdigest()
        event = {**unsigned_event, "event_mac": event_mac}
        report = {
            **unsigned_report,
            "report_digest": report_digest,
            "runner_attestation": {
                "sequence_no": index,
                "previous_event_mac": previous,
                "event_mac": event_mac,
                "state_schema_version": motion_evidence_service.STATE_SCHEMA,
                "anchor_schema_version": motion_evidence_service.ANCHOR_SCHEMA,
                "identity_schema_version": motion_evidence_service.IDENTITY_SCHEMA,
                "terminal_schema_version": motion_evidence_service.TERMINAL_SCHEMA,
            },
        }
        _write_json(motion_root / report_relpath, report, mode=0o600)
        events.append(event)
        previous = event_mac
    _write_json(
        trust / motion_evidence_service.STATE_FILE_NAME,
        {
            "schema_version": motion_evidence_service.STATE_SCHEMA,
            "updated_at": "2026-07-15T12:00:00.001Z",
            "events": events,
        },
        mode=0o600,
    )
    state = json.loads((trust / motion_evidence_service.STATE_FILE_NAME).read_text(encoding="utf-8"))
    unsigned_anchor = {
        "schema_version": motion_evidence_service.ANCHOR_SCHEMA,
        "installation_id": installation_id,
        "sequence_no": len(events),
        "updated_at": state["updated_at"],
        "latest_event_mac": events[-1]["event_mac"],
        "state_digest": motion_evidence_service._digest(state),
    }
    anchor = {
        **unsigned_anchor,
        "anchor_mac": hmac.new(key, motion_evidence_service._canonical_bytes(unsigned_anchor), hashlib.sha256).hexdigest(),
    }
    _write_json(trust / motion_evidence_service.ANCHOR_FILE_NAME, anchor, mode=0o600)
    unsigned_terminal = {
        "schema_version": motion_evidence_service.TERMINAL_SCHEMA,
        "installation_id": installation_id,
        "sequence_no": len(events),
        "updated_at": state["updated_at"],
        "latest_event_mac": events[-1]["event_mac"],
        "state_digest": motion_evidence_service._digest(state),
        "anchor_digest": motion_evidence_service._digest(anchor),
    }
    _write_json(
        motion_root / motion_evidence_service.TERMINAL_FILE_NAME,
        {
            **unsigned_terminal,
            "terminal_mac": hmac.new(key, motion_evidence_service._canonical_bytes(unsigned_terminal), hashlib.sha256).hexdigest(),
        },
        mode=0o600,
    )


def _sync_trace_network_from_report(root: Path, report: dict) -> None:
    motion_root = root / "motion_qa"
    trace_path = motion_root / report["raw_trace"]["path"]
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    for key in (
        "rows", "warmup_request_count", "warmup_request_ledger",
        "manifest_request_count", "manifest_request_ledger", "late_network_events",
        "inflight_request_ids", "network_event_count", "request_failed_count", "websocket_count",
    ):
        trace[key] = report[key]
    _write_json(trace_path, trace, mode=0o600)


def _resign_all(root: Path) -> None:
    motion_root = root / "motion_qa"
    trust = motion_root / motion_evidence_service.TRUST_DIR_NAME
    key = (trust / motion_evidence_service.KEY_FILE_NAME).read_bytes()
    state_path = trust / motion_evidence_service.STATE_FILE_NAME
    state = json.loads(state_path.read_text(encoding="utf-8"))
    previous = "0" * 64
    resigned_events: list[dict] = []
    for event in state["events"]:
        report_path = motion_root / event["report_relpath"]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        raw_path = motion_root / report["raw_trace"]["path"]
        report["raw_trace"]["sha256"] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        report["raw_trace"]["size_bytes"] = raw_path.stat().st_size
        report_digest = motion_evidence_service._digest(motion_evidence_service._report_without_seals(report))
        unsigned_event = {
            key_name: event[key_name]
            for key_name in sorted(motion_evidence_service._EVENT_KEYS - {"event_mac"})
        }
        unsigned_event["report_digest"] = report_digest
        unsigned_event["previous_event_mac"] = previous
        event_mac = hmac.new(
            key,
            motion_evidence_service._canonical_bytes(unsigned_event),
            hashlib.sha256,
        ).hexdigest()
        resigned_event = {**unsigned_event, "event_mac": event_mac}
        report["report_digest"] = report_digest
        report["runner_attestation"] = {
            "sequence_no": resigned_event["sequence_no"],
            "previous_event_mac": previous,
            "event_mac": event_mac,
            "state_schema_version": motion_evidence_service.STATE_SCHEMA,
            "anchor_schema_version": motion_evidence_service.ANCHOR_SCHEMA,
            "identity_schema_version": motion_evidence_service.IDENTITY_SCHEMA,
            "terminal_schema_version": motion_evidence_service.TERMINAL_SCHEMA,
        }
        _write_json(report_path, report, mode=0o600)
        resigned_events.append(resigned_event)
        previous = event_mac
    state = {
        "schema_version": motion_evidence_service.STATE_SCHEMA,
        "updated_at": resigned_events[-1]["created_at"],
        "events": resigned_events,
    }
    _write_json(state_path, state, mode=0o600)
    identity = json.loads((motion_root / motion_evidence_service.IDENTITY_FILE_NAME).read_text(encoding="utf-8"))
    unsigned_anchor = {
        "schema_version": motion_evidence_service.ANCHOR_SCHEMA,
        "installation_id": identity["installation_id"],
        "sequence_no": len(resigned_events),
        "updated_at": state["updated_at"],
        "latest_event_mac": resigned_events[-1]["event_mac"],
        "state_digest": motion_evidence_service._digest(state),
    }
    anchor = {
        **unsigned_anchor,
        "anchor_mac": hmac.new(key, motion_evidence_service._canonical_bytes(unsigned_anchor), hashlib.sha256).hexdigest(),
    }
    _write_json(trust / motion_evidence_service.ANCHOR_FILE_NAME, anchor, mode=0o600)
    unsigned_terminal = {
        "schema_version": motion_evidence_service.TERMINAL_SCHEMA,
        "installation_id": identity["installation_id"],
        "sequence_no": len(resigned_events),
        "updated_at": state["updated_at"],
        "latest_event_mac": resigned_events[-1]["event_mac"],
        "state_digest": motion_evidence_service._digest(state),
        "anchor_digest": motion_evidence_service._digest(anchor),
    }
    _write_json(
        motion_root / motion_evidence_service.TERMINAL_FILE_NAME,
        {
            **unsigned_terminal,
            "terminal_mac": hmac.new(key, motion_evidence_service._canonical_bytes(unsigned_terminal), hashlib.sha256).hexdigest(),
        },
        mode=0o600,
    )


class MotionCurrentHeadEvidenceTests(unittest.TestCase):
    def test_runner_uses_one_warmup_navigation_observers_secure_png_and_report_first_commit(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "scripts" / "motion_browser_qa_runner.mjs").read_text(encoding="utf-8")
        self.assertEqual(source.count("page.goto("), 1)
        self.assertIn("window.location.hash = hash", source)
        self.assertIn('observer.observe({ type: "layout-shift", buffered: true })', source)
        self.assertIn('observer.observe({ type: "longtask", buffered: true })', source)
        self.assertIn("document.getAnimations()", source)
        self.assertIn("exactLocalUrl(request.url())", source)
        self.assertIn("ALLOWED_READ_METHODS", source)
        self.assertIn('new Set(["GET"])', source)
        self.assertNotIn('"5173"', source)
        self.assertNotIn('"OPTIONS"', source)
        self.assertIn("decodePng(screenshotBytes, viewport.width, viewport.height)", source)
        self.assertIn("fsConstants.O_NOFOLLOW", source)
        self.assertIn('serviceWorkers: "block"', source)
        self.assertIn('context.on("response"', source)
        self.assertIn('context.on("requestfailed"', source)
        self.assertIn('page.on("websocket"', source)
        self.assertIn("context.routeWebSocket", source)
        self.assertIn("requestOrigins = new WeakMap()", source)
        self.assertIn("inflightRequests = new Map()", source)
        self.assertIn('page.waitForLoadState("networkidle"', source)
        self.assertIn("FastAPI health identity", source)
        self.assertIn("await response.body()", source)
        self.assertIn('"--untracked-files=all"', source)
        self.assertIn("frontendServiceIdentity", source)
        self.assertIn("formalPackageBinding", source)
        self.assertIn("--initialize-runner-trust", source)
        self.assertIn("--self-test-fastapi-validator", source)
        self.assertIn("FASTAPI_CACHE_CONTRACTS", source)
        self.assertIn("response_semantic_summary", source)
        self.assertIn("historical_provenance_count", source)
        self.assertIn("ledger_contract_rows", source)
        self.assertIn("FASTAPI_CACHE_ENDPOINT_COUNT = 21", source)
        self.assertNotIn("/^(local_", source)
        self.assertIn("MAX_PNG_DECODED_BYTES", source)
        self.assertIn("maxOutputLength", source)
        self.assertLess(
            source.index("await atomicJson(reportPath, report"),
            source.index("await atomicJson(statePath, nextState"),
        )
        self.assertLess(
            source.index("await atomicJson(statePath, nextState"),
            source.index("await atomicJson(anchorPath, anchor"),
        )

    def test_valid_current_head_normal_reduced_pair_is_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertTrue(result["motion_current_head_pair_verified"])
            self.assertEqual(result["blockers"], [])
            self.assertEqual(result["frontend_source_digest"], SOURCE)
            self.assertEqual(result["build_identity_digest"], BUILD)
            self.assertEqual(len(result["validated_route_rows"]["#candidates"]), 8)
            self.assertEqual(len(result["validated_route_rows"]["#next-session-chart"]), 8)

            evaluation = v1_closeout_service.build_v1_closeout_evaluation(
                evidence_root=root,
                expected_head_full=HEAD,
            )
            facts = {row["evidence_key"]: row["observed"] for row in evaluation["production_fact_rows"]}
            self.assertTrue(facts["motion_production_promoted"])
            self.assertTrue(evaluation["motion_current_head_evidence_summary"]["motion_current_head_pair_verified"])

    def test_old_head_and_duplicate_mode_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root, head=OTHER_HEAD)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertFalse(result["motion_current_head_pair_verified"])
            self.assertIn("current_head_normal_reduced_pair_missing", result["blockers"])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root, modes=("normal", "normal"))
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertFalse(result["motion_current_head_pair_verified"])
            self.assertIn("current_head_normal_reduced_pair_missing", result["blockers"])

    def test_copied_or_manually_modified_report_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            source = next((root / "motion_qa").glob("*-normal/motion_browser_qa_report.json"))
            copied = root / "motion_qa" / "copied" / "motion_browser_qa_report.json"
            copied.parent.mkdir()
            copied.write_bytes(source.read_bytes())
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertFalse(result["motion_current_head_pair_verified"])
            self.assertIn("unregistered_current_head_report_detected", result["blockers"])

            copied.unlink()
            report = json.loads(source.read_text(encoding="utf-8"))
            report["production_motion_complete"] = True
            _write_json(source, report, mode=0o600)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertFalse(result["motion_current_head_pair_verified"])
            self.assertIn("normal:report_schema_fields_invalid", result["blockers"])

    def test_source_build_mismatch_and_missing_raw_trace_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root, sources=(SOURCE, "e" * 64))
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertFalse(result["motion_current_head_pair_verified"])
            self.assertIn("pair_frontend_source_digest_mismatch", result["blockers"])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            next((root / "motion_qa").glob("*-reduced/motion_performance_trace.json")).unlink()
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertFalse(result["motion_current_head_pair_verified"])
            self.assertIn("reduced:raw_trace_missing", result["blockers"])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            screenshot = next((root / "motion_qa").glob("*-normal/desktop/*.png"))
            screenshot.write_bytes(b"tampered screenshot")
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertFalse(result["motion_current_head_pair_verified"])
            self.assertIn("normal:screenshot_digest_mismatch", result["blockers"])

    def test_type_confusion_bad_mode_and_missing_trust_material_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            report_path = next((root / "motion_qa").glob("*-reduced/motion_browser_qa_report.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["qa_matrix_count"] = True
            report["run_mode"] = "normal"
            _write_json(report_path, report, mode=0o600)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertFalse(result["motion_current_head_pair_verified"])
            self.assertIn("reduced:report_qa_matrix_count_invalid", result["blockers"])
            self.assertIn("reduced:report_mode_mismatch", result["blockers"])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            before = set(root.rglob("*"))
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            after = set(root.rglob("*"))
            self.assertFalse(result["motion_current_head_pair_verified"])
            self.assertEqual(before, after)
            self.assertFalse(result["reader_created_or_repaired_trust_material"])
            self.assertFalse(result["key_or_fingerprint_exposed"])

    def test_current_source_and_build_are_recomputed_not_caller_asserted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            root = base / "evidence"
            project = base / "project"
            (project / "desktop" / "src").mkdir(parents=True)
            (project / "desktop" / "dist" / "assets").mkdir(parents=True)
            (project / "desktop" / "src" / "App.tsx").write_text("export const App = 1;\n", encoding="utf-8")
            (project / "desktop" / "dist" / "index.html").write_bytes(b"html")
            (project / "desktop" / "dist" / "assets" / "app.js").write_bytes(b"js")
            (project / "desktop" / "dist" / "assets" / "app.css").write_bytes(b"css")
            (project / "desktop" / "package.json").write_text("{}\n", encoding="utf-8")
            identity = motion_evidence_service._frontend_identity(project)
            self.assertIsNotNone(identity)
            assert identity is not None
            source, build, manifest = identity
            write_attested_pair(root, sources=(source, source), builds=(build, build), dist_manifest=manifest)
            result = motion_evidence_service.validate_current_motion_evidence(
                root,
                expected_head_full=HEAD,
                project_root=project,
            )
            self.assertTrue(result["motion_current_head_pair_verified"])

            (project / "desktop" / "src" / "App.tsx").write_text("export const App = 2;\n", encoding="utf-8")
            result = motion_evidence_service.validate_current_motion_evidence(
                root,
                expected_head_full=HEAD,
                project_root=project,
            )
            self.assertFalse(result["motion_current_head_pair_verified"])
            self.assertIn("current_frontend_source_digest_mismatch", result["blockers"])
            self.assertIn("current_frontend_build_identity_mismatch", result["blockers"])

    def test_high_water_anchor_detects_suffix_rollback_and_active_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            trust = root / "motion_qa" / motion_evidence_service.TRUST_DIR_NAME
            state_path = trust / motion_evidence_service.STATE_FILE_NAME
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["events"] = state["events"][:-1]
            state["updated_at"] = state["events"][-1]["created_at"]
            _write_json(state_path, state, mode=0o600)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertIn("runner_high_water_anchor_invalid_or_rollback_detected", result["blockers"])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            trust = root / "motion_qa" / motion_evidence_service.TRUST_DIR_NAME
            state_path = trust / motion_evidence_service.STATE_FILE_NAME
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["events"] = state["events"][1:]
            state["updated_at"] = state["events"][-1]["created_at"]
            _write_json(state_path, state, mode=0o600)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertIn("runner_event_identity_invalid", result["blockers"])
            self.assertIn("runner_event_chain_invalid", result["blockers"])
            self.assertIn("runner_terminal_high_water_invalid_or_rollback_detected", result["blockers"])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            lock = root / "motion_qa" / motion_evidence_service.TRUST_DIR_NAME / "append.lock"
            lock.write_text("locked\n", encoding="utf-8")
            lock.chmod(0o600)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertIn("runner_write_in_progress", result["blockers"])

    def test_secure_png_rejects_symlink_wrong_viewport_and_trailing_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            screenshot = next((root / "motion_qa").glob("*-normal/desktop/*.png"))
            target = screenshot.with_name("target.png")
            target.write_bytes(screenshot.read_bytes())
            target.chmod(0o600)
            screenshot.unlink()
            screenshot.symlink_to(target.name)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertIn("normal:screenshot_missing_or_unsafe", result["blockers"])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            screenshot = next((root / "motion_qa").glob("*-normal/desktop/*.png"))
            screenshot.write_bytes(_png(10, 10) + b"trailing")
            screenshot.chmod(0o600)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertIn("normal:screenshot_png_dimension_or_digest_invalid", result["blockers"])

    def test_validator_recomputes_metrics_markers_network_and_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            report_path = next((root / "motion_qa").glob("*-normal/motion_browser_qa_report.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            row = report["rows"][0]
            row["route_transition_observed_us"] = 999_999
            row["motion_markers"]["state_rail"] = 0
            row["request_count"] = 1
            row["request_ledger"] = [{
                "event_index": 9, "event_type": "request", "phase": "route", "route": "#home", "viewport": "desktop",
                "method": "POST", "url": "https://example.com/leak", "protocol": "https:", "hostname": "example.com", "port": "443",
                "path": "/leak", "allowed": False, "status_code": None, "content_type": "", "body_sha256": "",
                "body_size_bytes": None, "dist_path": "", "expected_dist_sha256": "", "body_matches_dist": False,
                "failure_text": "blocked",
            }]
            _write_json(report_path, report, mode=0o600)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            joined = "\n".join(result["blockers"])
            self.assertIn("route_transition_observed_us_budget_failed", joined)
            self.assertIn("motion_marker_minimum_failed", joined)
            self.assertIn("request_ledger_invalid", joined)
            self.assertIn("row_claim_mismatch", joined)

    def test_integer_only_canonical_vector_and_float_report_fail_closed(self) -> None:
        self.assertTrue(motion_evidence_service.canonical_vector_valid())
        with self.assertRaises(ValueError):
            motion_evidence_service._canonical_bytes({"metric": 0.1})
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            report_path = next((root / "motion_qa").glob("*-normal/motion_browser_qa_report.json"))
            text = report_path.read_text(encoding="utf-8").replace('"route_transition_observed_us": 1', '"route_transition_observed_us": 1.5', 1)
            report_path.write_text(text, encoding="utf-8")
            report_path.chmod(0o600)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertIn("normal:report_schema_fields_invalid", result["blockers"])

    def test_fake_localhost_response_and_incomplete_entry_graph_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            report_path = next((root / "motion_qa").glob("*-normal/motion_browser_qa_report.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            response = next(item for item in report["manifest_request_ledger"] if item["event_type"] == "response")
            response["body_sha256"] = "0" * 64
            response["body_matches_dist"] = False
            _write_json(report_path, report, mode=0o600)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertTrue(any("served_static_response_not_bound_to_dist" in item for item in result["blockers"]))
            self.assertTrue(any("served_entry_import_graph_incomplete" in item for item in result["blockers"]))

    def test_network_pairing_rejects_missing_duplicate_and_cross_phase_terminals(self) -> None:
        manifest = _dist_manifest()
        entry = next(item for item in manifest["entries"] if item["path"] == "index.html")
        request = _network_entry(
            index=1, event_type="request", phase="warmup", route="#health",
            viewport="desktop", path="index.html", entry=None,
        )
        response = _network_entry(
            index=2, event_type="response", phase="warmup", route="#health",
            viewport="desktop", path="index.html", entry=entry,
        )
        self.assertTrue(any("network_terminal_count_invalid" in item for item in motion_evidence_service._network_pairing_blockers([request])))
        duplicate = {**response, "event_index": 3}
        self.assertTrue(any("network_terminal_count_invalid" in item for item in motion_evidence_service._network_pairing_blockers([request, response, duplicate])))
        delayed = {
            **response,
            "session_id": "desktop:3:route:#home",
            "phase": "route",
            "route": "#home",
        }
        cross_phase = motion_evidence_service._network_pairing_blockers([request, delayed])
        self.assertTrue(any("network_origin_mismatch" in item and item.endswith(":session_id") for item in cross_phase))
        self.assertTrue(any("network_origin_mismatch" in item and item.endswith(":phase") for item in cross_phase))

    def test_fastapi_rows_require_formal_health_json_2xx_and_5173_is_forbidden(self) -> None:
        base = {
            "event_index": 1,
            "event_type": "request",
            "request_id": "desktop:http:1",
            "session_id": "desktop:1:warmup:#health",
            "phase": "warmup",
            "route": "#health",
            "viewport": "desktop",
            "method": "GET",
            "url": "http://127.0.0.1:8710/health",
            "protocol": "http:",
            "hostname": "127.0.0.1",
            "port": "8710",
            "path": "/health",
            "purpose": "fastapi_health_identity",
            "allowed": True,
            "status_code": None,
            "content_type": "",
            "body_sha256": "",
            "body_size_bytes": None,
            "dist_path": "",
            "expected_dist_sha256": "",
            "body_matches_dist": False,
            "body_schema_valid": False,
            "response_semantic_summary": {},
            "response_semantic_digest": "",
            "failure_text": "",
        }
        summary = _health_semantic_summary(body_sha256="7" * 64, body_size_bytes=128)
        response = {
            **base,
            "event_index": 2,
            "event_type": "response",
            "status_code": 200,
            "content_type": "application/json; charset=utf-8",
            "body_sha256": "7" * 64,
            "body_size_bytes": 128,
            "body_schema_valid": True,
            "response_semantic_summary": summary,
            "response_semantic_digest": motion_evidence_service._digest(summary),
        }
        self.assertTrue(motion_evidence_service._network_entry_valid(base, phase="warmup", route="#health", viewport="desktop"))
        self.assertTrue(motion_evidence_service._network_entry_valid(response, phase="warmup", route="#health", viewport="desktop"))
        self.assertFalse(motion_evidence_service._network_entry_valid({**response, "status_code": 500}, phase="warmup", route="#health", viewport="desktop"))
        self.assertFalse(motion_evidence_service._network_entry_valid({**response, "body_schema_valid": False}, phase="warmup", route="#health", viewport="desktop"))
        dev = {
            **base,
            "url": "http://127.0.0.1:5173/",
            "port": "5173",
            "path": "/",
            "purpose": "vite_dev_resource",
        }
        self.assertFalse(motion_evidence_service._network_entry_valid(dev, phase="warmup", route="#health", viewport="desktop"))
        self.assertTrue(motion_evidence_service._fastapi_identity_valid(_fastapi_identity()))
        self.assertFalse(motion_evidence_service._fastapi_identity_valid({**_fastapi_identity(), "status_code": 204}))

    def test_resigned_fastapi_semantic_attacks_fail_independent_validation(self) -> None:
        mutations = {
            "external": lambda row: row.update(ledger_current_external_count=1),
            "provider": lambda row: row.update(ledger_current_provider_count=1),
            "model": lambda row: row.update(ledger_current_model_count=1),
            "worker": lambda row: row.update(ledger_current_worker_count=1),
            "trade": lambda row: row.update(ledger_current_trade_count=1),
            "task_post": lambda row: row.update(task_post_count=1),
            "secret": lambda row: row.update(secret_bearing_field_count=1),
            "unknown_endpoint": lambda row: row.update(endpoint="/api/evil/cache"),
            "raw_body_mismatch": lambda row: row.update(raw_body_sha256="f" * 64),
            "schema_mismatch": lambda row: row.update(data_schema_version="malicious.v1"),
            "ledger_contract_field_missing": lambda row: row["ledger_contract_rows"][0].pop("worker"),
            "ledger_contract_unrelated_source": lambda row: row["ledger_contract_rows"][0].update(source="/api/tasks"),
            "ledger_contract_api_not_endpoint_owned": lambda row: row["ledger_contract_rows"][0].update(api="local_unrelated_cache"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                write_attested_pair(root)
                report_path = next((root / "motion_qa").glob("*-normal/motion_browser_qa_report.json"))
                report = json.loads(report_path.read_text(encoding="utf-8"))
                response = next(
                    item for item in report["warmup_request_ledger"]
                    if item["event_type"] == "response" and item["purpose"] == "fastapi_cache_read"
                )
                self.assertTrue(response["body_schema_valid"])
                mutate(response["response_semantic_summary"])
                response["response_semantic_digest"] = motion_evidence_service._digest(
                    response["response_semantic_summary"]
                )
                _write_json(report_path, report, mode=0o600)
                _sync_trace_network_from_report(root, report)
                _resign_all(root)

                result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
                joined = "\n".join(result["blockers"])
                self.assertFalse(result["motion_current_head_pair_verified"])
                self.assertIn("normal:fastapi_response_envelope_safety_invalid", joined)
                self.assertNotIn("report_digest_or_event_binding_invalid", joined)
                self.assertNotIn("runner_event_mac_invalid", joined)

    def test_endpoint_and_ledger_contract_surfaces_are_exact_and_drift_closed(self) -> None:
        self.assertEqual(len(motion_evidence_service._FASTAPI_CACHE_CONTRACTS), 20)
        self.assertEqual(set(motion_evidence_service._FASTAPI_CACHE_CONTRACTS), set(motion_evidence_service._FASTAPI_LEDGER_APIS))
        summary = _fastapi_semantic_summary(
            path="/api/audit/cache",
            body_sha256="a" * 64,
            body_size_bytes=128,
        )
        entry = {
            "method": "GET", "status_code": 200, "body_sha256": "a" * 64,
            "body_size_bytes": 128, "purpose": "fastapi_cache_read",
            "response_semantic_summary": summary,
            "response_semantic_digest": motion_evidence_service._digest(summary),
        }
        self.assertTrue(motion_evidence_service._fastapi_response_semantic_valid(entry))
        optional = _fastapi_semantic_summary(
            path="/api/next-session/cache", body_sha256="b" * 64, body_size_bytes=256,
        )
        optional["ledger_contract_rows"] = [optional["ledger_contract_rows"][0]]
        optional["ledger_count"] = 1
        optional_entry = {
            "method": "GET", "status_code": 200, "body_sha256": "b" * 64,
            "body_size_bytes": 256, "purpose": "fastapi_cache_read",
            "response_semantic_summary": optional,
            "response_semantic_digest": motion_evidence_service._digest(optional),
        }
        self.assertTrue(motion_evidence_service._fastapi_response_semantic_valid(optional_entry))

        migration = _fastapi_semantic_summary(
            path="/api/migration/status", body_sha256="c" * 64, body_size_bytes=512,
        )
        migration_entry = {
            "method": "GET", "status_code": 200, "body_sha256": "c" * 64,
            "body_size_bytes": 512, "purpose": "fastapi_cache_read",
            "response_semantic_summary": migration,
            "response_semantic_digest": motion_evidence_service._digest(migration),
        }
        self.assertTrue(motion_evidence_service._fastapi_response_semantic_valid(migration_entry))
        optional["strict_current_read_valid"] = False
        optional_entry["response_semantic_digest"] = motion_evidence_service._digest(optional)
        self.assertFalse(motion_evidence_service._fastapi_response_semantic_valid(optional_entry))
        optional["strict_current_read_valid"] = True
        optional["ledger_contract_rows"].append(
            {
                **optional["ledger_contract_rows"][0],
                "api": "local_next_session_production_stage_scope_manifest",
            }
        )
        optional["ledger_count"] = 2
        optional_entry["response_semantic_digest"] = motion_evidence_service._digest(optional)
        self.assertFalse(motion_evidence_service._fastapi_response_semantic_valid(optional_entry))
        missing = _fastapi_semantic_summary(
            path="/api/next-session/cache", body_sha256="c" * 64, body_size_bytes=256,
            envelope_state="cache_missing",
        )
        missing["data_status"] = "ready"
        missing_entry = {
            "method": "GET", "status_code": 200, "body_sha256": "c" * 64,
            "body_size_bytes": 256, "purpose": "fastapi_cache_read",
            "path": "/api/next-session/cache", "response_semantic_summary": missing,
            "response_semantic_digest": motion_evidence_service._digest(missing),
        }
        self.assertFalse(motion_evidence_service._fastapi_response_semantic_valid(missing_entry))
        original = motion_evidence_service._FASTAPI_LEDGER_APIS.pop("/api/audit/cache")
        try:
            self.assertFalse(motion_evidence_service._fastapi_response_semantic_valid(entry))
        finally:
            motion_evidence_service._FASTAPI_LEDGER_APIS["/api/audit/cache"] = original

    def test_candidate_and_next_consumers_block_v1_and_accept_only_verified_v6_rows(self) -> None:
        def trusted_rows(route: str, label: str) -> list[dict]:
            rows = []
            for reduced in (False, True):
                for viewport, (width, height) in DIMENSIONS.items():
                    rows.append(
                        {
                            "run_id": f"trusted-{'reduced' if reduced else 'normal'}",
                            "generated_at": "2026-07-16T00:00:00Z",
                            "reduced_motion": reduced,
                            "route": route,
                            "label": label,
                            "viewport": viewport,
                            "width": width,
                            "height": height,
                            "status": "passed",
                            "visual_qa_complete": True,
                            "performance_trace_complete": True,
                            "route_transition_observed_us": 1,
                            "route_transition_budget_us": 500_000,
                            "long_task_over_50ms_count": 0,
                            "largest_motion_layout_shift_ppm": 0,
                            "clipped_count": 0,
                            "offscreen_count": 0,
                            "screenshot_path": f"trusted/{viewport}/{route.removeprefix('#')}.png",
                        }
                    )
            return rows

        with tempfile.TemporaryDirectory() as temp_dir:
            motion_root = Path(temp_dir) / "motion_qa"
            legacy_dir = motion_root / "legacy"
            legacy_dir.mkdir(parents=True)
            (legacy_dir / "motion_browser_qa_report.json").write_text(
                json.dumps({"schema_version": "command_center_3_motion_browser_qa_result.v1", "status": "motion_browser_qa_passed"}),
                encoding="utf-8",
            )
            blocked = {
                "status": "motion_current_head_evidence_blocked",
                "motion_current_head_pair_verified": False,
                "blockers": ["current_head_pair_not_terminal_high_water"],
                "validated_route_rows": {},
            }
            with (
                mock.patch.object(candidate_service, "MOTION_QA_ARTIFACT_ROOT", motion_root),
                mock.patch.object(next_session_service, "MOTION_QA_ARTIFACT_ROOT", motion_root),
                mock.patch.object(motion_evidence_service, "current_repository_head", return_value=HEAD),
                mock.patch.object(motion_evidence_service, "validate_current_motion_evidence", return_value=blocked),
            ):
                candidate_summary, candidate_rows = candidate_service._candidate_browser_qa_evidence_summary()
                next_summary, next_rows = next_session_service._next_session_browser_qa_evidence_summary()
            self.assertEqual(candidate_rows, [])
            self.assertEqual(next_rows, [])
            self.assertFalse(candidate_summary["candidate_browser_qa_evidence_ready"])
            self.assertFalse(next_summary["next_browser_qa_evidence_ready"])
            self.assertEqual(candidate_summary["legacy_v1_compatibility_status"], "blocked_not_promotion_evidence")
            self.assertEqual(next_summary["legacy_v1_compatibility_status"], "blocked_not_promotion_evidence")

            verified = {
                "status": "motion_current_head_normal_reduced_pair_verified",
                "motion_current_head_pair_verified": True,
                "blockers": [],
                "normal_run_id": "trusted-normal",
                "reduced_run_id": "trusted-reduced",
                "validated_route_rows": {
                    "#candidates": trusted_rows("#candidates", "Candidate Radar"),
                    "#next-session-chart": trusted_rows("#next-session-chart", "Next Session Map"),
                },
            }
            with (
                mock.patch.object(candidate_service, "MOTION_QA_ARTIFACT_ROOT", motion_root),
                mock.patch.object(next_session_service, "MOTION_QA_ARTIFACT_ROOT", motion_root),
                mock.patch.object(motion_evidence_service, "current_repository_head", return_value=HEAD),
                mock.patch.object(motion_evidence_service, "validate_current_motion_evidence", return_value=verified),
            ):
                candidate_summary, candidate_rows = candidate_service._candidate_browser_qa_evidence_summary()
                next_summary, next_rows = next_session_service._next_session_browser_qa_evidence_summary()
            self.assertTrue(candidate_summary["candidate_browser_qa_evidence_ready"])
            self.assertTrue(next_summary["next_browser_qa_evidence_ready"])
            self.assertEqual(len(candidate_rows), 8)
            self.assertEqual(len(next_rows), 8)
            self.assertTrue(all(row["reads_current_head_v6_validation_only"] for row in candidate_rows + next_rows))
            candidate_review = candidate_service._candidate_browser_qa_review_contract(
                candidate_summary,
                candidate_rows,
                explicit_review=True,
                task_id="current-head-review",
                reviewed_at="2026-07-16T00:00:00Z",
            )
            self.assertEqual(candidate_review["status"], "candidate_browser_qa_review_ready_local_artifact")
            self.assertTrue(candidate_review["local_browser_qa_review_ready"])
            self.assertFalse(candidate_review["reads_ignored_local_reports_only"])
            self.assertTrue(candidate_review["reads_current_head_terminal_v6_pair_only"])
            self.assertIn(
                "current_head_terminal_v6_pair_policy_preserved",
                {row["criterion"] for row in candidate_review["rows"]},
            )

    def test_resigned_historical_cache_provenance_is_not_current_get_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            for report_path in (root / "motion_qa").glob("*/motion_browser_qa_report.json"):
                report = json.loads(report_path.read_text(encoding="utf-8"))
                response = next(
                    item for item in report["warmup_request_ledger"]
                    if item["event_type"] == "response" and item["purpose"] == "fastapi_cache_read"
                )
                response["response_semantic_summary"]["historical_provenance_count"] = 7
                response["response_semantic_digest"] = motion_evidence_service._digest(
                    response["response_semantic_summary"]
                )
                _write_json(report_path, report, mode=0o600)
                _sync_trace_network_from_report(root, report)
            _resign_all(root)

            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertTrue(result["motion_current_head_pair_verified"], result["blockers"])

    def test_resigned_delayed_response_and_inflight_claim_fail_semantic_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            report_path = next((root / "motion_qa").glob("*-normal/motion_browser_qa_report.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            response_index = next(
                index
                for index, item in enumerate(report["manifest_request_ledger"])
                if item["event_type"] == "response" and item["viewport"] == "desktop"
            )
            delayed = report["manifest_request_ledger"].pop(response_index)
            delayed["session_id"] = "desktop:3:route:#home"
            delayed["phase"] = "route"
            delayed["route"] = "#home"
            report["manifest_request_count"] -= 1
            report["rows"][0]["request_ledger"].append(delayed)
            report["rows"][0]["request_count"] += 1
            report["inflight_request_ids"] = [delayed["request_id"]]
            _write_json(report_path, report, mode=0o600)
            _sync_trace_network_from_report(root, report)
            _resign_all(root)

            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            joined = "\n".join(result["blockers"])
            self.assertFalse(result["motion_current_head_pair_verified"])
            self.assertIn("normal:inflight_requests_detected", joined)
            self.assertIn("normal:network_origin_mismatch", joined)
            self.assertNotIn("report_digest_or_event_binding_invalid", joined)
            self.assertNotIn("runner_event_mac_invalid", joined)

    def test_external_get_websocket_service_worker_late_event_and_zero_warmup_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            report_path = next((root / "motion_qa").glob("*-normal/motion_browser_qa_report.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            external = {
                "event_index": 9, "event_type": "request", "phase": "route", "route": "#home", "viewport": "desktop",
                "method": "GET", "url": "https://example.com/leak", "protocol": "https:", "hostname": "example.com", "port": "443",
                "path": "/leak", "allowed": False, "status_code": None, "content_type": "", "body_sha256": "",
                "body_size_bytes": None, "dist_path": "", "expected_dist_sha256": "", "body_matches_dist": False,
                "failure_text": "blocked",
            }
            websocket = {**external, "event_index": 10, "event_type": "websocket", "method": "GET", "failure_text": "websocket_forbidden"}
            report["rows"][0]["request_ledger"] = [external, websocket]
            report["rows"][0]["request_count"] = 2
            report["late_network_events"] = [external]
            report["service_workers_blocked"] = False
            report["warmup_navigation_count"] = 0
            report["warmup_navigation_ledger"] = []
            _write_json(report_path, report, mode=0o600)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            joined = "\n".join(result["blockers"])
            self.assertIn("request_ledger_invalid", joined)
            self.assertIn("late_network_events_detected", joined)
            self.assertIn("report_service_workers_blocked_invalid", joined)
            self.assertIn("report_warmup_navigation_count_invalid", joined)
            self.assertIn("warmup_navigation_ledger_invalid", joined)

    def test_anchor_or_trust_deletion_cannot_silently_start_a_new_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            trust = root / "motion_qa" / motion_evidence_service.TRUST_DIR_NAME
            (trust / motion_evidence_service.ANCHOR_FILE_NAME).unlink()
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertIn("runner_high_water_anchor_schema_invalid", result["blockers"])
            self.assertIn("runner_terminal_high_water_invalid_or_rollback_detected", result["blockers"])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            shutil.rmtree(root / "motion_qa" / motion_evidence_service.TRUST_DIR_NAME)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertIn("runner_trust_dir_missing_or_mode_invalid", result["blockers"])
            self.assertIn("runner_key_missing_or_invalid", result["blockers"])
            self.assertTrue((root / "motion_qa" / motion_evidence_service.IDENTITY_FILE_NAME).exists())
            self.assertTrue((root / "motion_qa" / motion_evidence_service.TERMINAL_FILE_NAME).exists())

    def test_bounded_png_decoder_rejects_inflate_bomb(self) -> None:
        bomb = _png_bomb(1440, 900)
        self.assertLess(len(bomb), 100_000)
        self.assertIsNone(motion_evidence_service._decode_png(bomb))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_attested_pair(root)
            screenshot = next((root / "motion_qa").glob("*-normal/desktop/*.png"))
            screenshot.write_bytes(bomb)
            screenshot.chmod(0o600)
            result = motion_evidence_service.validate_current_motion_evidence(root, expected_head_full=HEAD)
            self.assertIn("normal:screenshot_png_dimension_or_digest_invalid", result["blockers"])

    def test_repository_cleanliness_includes_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Motion QA Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "motion-qa@example.invalid"], cwd=root, check=True)
            (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=root, check=True)
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            self.assertTrue(motion_evidence_service._repository_is_exact_clean(root, head))
            (root / "untracked.txt").write_text("must block\n", encoding="utf-8")
            self.assertFalse(motion_evidence_service._repository_is_exact_clean(root, head))


if __name__ == "__main__":
    unittest.main()
