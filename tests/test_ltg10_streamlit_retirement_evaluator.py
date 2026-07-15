from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from server.services import streamlit_retirement_evidence_service as retirement
from server.services import tauri_package_verifier
from server.services import v1_closeout_service


ROOT = Path(__file__).resolve().parents[1]
HEAD = retirement._git_head_full(ROOT)
OLD_HEAD = "c" * 40
ARTIFACT_SET = "a" * 64
APP_BUNDLE = "b" * 64
DMG_SHA = "e" * 64
NODE_MODULES = os.environ.get("STOCK_MING_DESKTOP_NODE_MODULES", str(ROOT / "desktop/node_modules"))


def _package(*, ready: bool = True, head_full: str = HEAD, executable_sha: str = "d" * 64) -> dict:
    return {
        "schema_version": "tauri_production_package_manifest.v1",
        "status": "tauri_production_package_verified" if ready else "tauri_production_package_blocked",
        "production_package_complete": ready,
        "head_full": head_full,
        "artifact_set_sha256": ARTIFACT_SET,
        "app_bundle_sha256": APP_BUNDLE,
        "app_executable_sha256": executable_sha,
        "dmg_sha256": DMG_SHA,
        "bundle_identifier": "com.stockming.commandcenter",
        "bundle_version": "3.0.0",
        "blockers": [] if ready else ["packaged_app_or_dmg_missing"],
    }


def _measured_package(package: dict, project_root: Path = ROOT) -> dict:
    return {
        "app_path": str(project_root / tauri_package_verifier.FIXED_APP_RELATIVE),
        "dmg_path": str(project_root / tauri_package_verifier.FIXED_DMG_RELATIVE),
        "app_executable_path": str(
            project_root
            / tauri_package_verifier.FIXED_APP_RELATIVE
            / "Contents/MacOS"
            / tauri_package_verifier.FIXED_EXECUTABLE_NAME
        ),
        "artifact_set_sha256": package["artifact_set_sha256"],
        "app_bundle_sha256": package["app_bundle_sha256"],
        "app_executable_sha256": package["app_executable_sha256"],
        "dmg_sha256": package["dmg_sha256"],
        "bundle_identifier": package["bundle_identifier"],
        "bundle_version": package["bundle_version"],
        "blockers": [],
    }


def _build_challenge(*, nonce: bytes, package: dict, source: dict) -> dict:
    with patch.object(
        retirement.tauri_package_verifier,
        "measure_fixed_tauri_package_artifacts",
        return_value=_measured_package(package),
    ):
        return retirement._build_runner_challenge(
            nonce=nonce,
            expected_head_full=HEAD,
            package=package,
            source=source,
        )


def _copy_source_contract(root: Path) -> None:
    for relative in (
        Path("app.py"),
        Path("desktop/src/App.tsx"),
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
        Path("desktop/src/components/StateClarityRail.tsx"),
        Path("desktop/src/components/StatusBadge.tsx"),
        Path("desktop/src/components/TaskBoundarySummary.tsx"),
        Path("desktop/src/components/TaskLaunchReceipt.tsx"),
        Path("desktop/src/components/TaskStatusPanel.tsx"),
        Path("desktop/src/routes/CommandCenterHome.tsx"),
        Path("desktop/src/routes/CandidateRadar.tsx"),
        Path("desktop/src/routes/FactorQuantHub.tsx"),
        Path("desktop/src/routes/NextSessionMap.tsx"),
        Path("desktop/src/routes/MarginEtf.tsx"),
        Path("desktop/src/routes/QmtReplayLab.tsx"),
        Path("desktop/src/routes/LegacyTools.tsx"),
        Path("desktop/package.json"),
        Path("server/services/legacy_service.py"),
        Path("scripts/streamlit_retirement_packaged_qa_runner.mjs"),
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)


def _dom_ledger(route: str) -> list[dict]:
    components = dict(retirement.EXPECTED_ROUTES)
    route_key = route.removeprefix("#")
    heading = retirement.EXPECTED_ROUTE_HEADINGS[route]
    component_selector = f'[data-ltg10-component-id="{components[route]}"]'
    heading_selector = f'[data-ltg10-route-heading="{route_key}"]'
    rows = [
        ("exists", "#root", True),
        ("count", "button[data-route-active='true']", 1),
        ("attribute", "button[data-route-active='true']@data-route-key", route_key),
        ("count", "[data-ltg10-route-heading]", 1),
        ("attribute", "[data-ltg10-route-heading]@data-ltg10-route-heading", route_key),
        ("attribute", "[data-ltg10-route-heading]@tagName", "h1"),
        ("text", "[data-ltg10-route-heading]", heading),
        ("count", retirement.COMPONENT_COUNT_SELECTOR, 1),
        ("attribute", retirement.COMPONENT_ATTRIBUTE_SELECTOR, components[route]),
        ("count", retirement.FORBIDDEN_COMPONENT_SELECTOR, 0),
        ("count", "button[data-route-key='legacy'][data-route-active='true']", 0),
        ("count", "[data-streamlit-surface],iframe[src*='streamlit']", 0),
        ("count", retirement.ROOT_COMPONENT_COUNT_SELECTOR, 1),
        ("count", retirement.BODY_NON_ROOT_SURFACE_SELECTOR, 0),
        ("count", "body@frame-surface-count", 0),
        ("count", "body@open-shadow-root-count", 0),
        ("count", "body@attach-shadow-call-count", 0),
        ("count", "body@custom-element-event-count", 0),
        ("count", "body@custom-element-surface-count", 0),
        ("count", "body@dynamic-frame-create-count", 0),
        ("html", retirement.BODY_HTML_SELECTOR, f'<div id="root"><div data-ltg10-component-id="{components[route]}"><h1 data-ltg10-route-heading="{route_key}">{heading}</h1>ordinary route content</div></div>'),
        ("text", "body@innerText", f"{heading} ordinary route content"),
        ("accessibility", "body@accessibility-tree", json.dumps([
            {"selector": component_selector, "tag": "div", "role": "main", "name": "ordinary route content", "aria_hidden": "", "aria_current": "", "disabled": False, "visible": True},
            {"selector": heading_selector, "tag": "h1", "role": "heading", "name": heading, "aria_hidden": "", "aria_current": "", "disabled": False, "visible": True},
        ])),
        ("computed", "body@computed-style-tree", json.dumps([
            {"selector": component_selector, "display": "block", "visibility": "visible", "opacity": "1", "overflow": "visible", "color": "rgb(1, 2, 3)", "background_color": "rgb(255, 255, 255)", "before": "none", "after": "none", "visible": True, "viewport_intersection": 80000.0, "clipped": False, "content_visibility": "visible", "occluded": False, "color_alpha": 1.0},
            {"selector": heading_selector, "display": "block", "visibility": "visible", "opacity": "1", "overflow": "visible", "color": "rgb(1, 2, 3)", "background_color": "rgba(0, 0, 0, 0)", "before": "none", "after": "none", "visible": True, "viewport_intersection": 10000.0, "clipped": False, "content_visibility": "visible", "occluded": False, "color_alpha": 1.0},
        ])),
        ("pseudo", "body@pseudo-content", json.dumps([
            {"selector": component_selector, "before": "none", "after": "none", "visible": True},
            {"selector": heading_selector, "before": "none", "after": "none", "visible": True},
        ])),
        ("canvas", "body@canvas-inventory", "[]"),
    ]
    return [
        {"sequence": index, "kind": kind, "selector": selector, "value": value}
        for index, (kind, selector, value) in enumerate(rows, 1)
    ]


def _network_ledger(route: str = "#home") -> list[dict]:
    return [
        {"sequence": 1, "request_id": "request-1", "observed_monotonic_ns": 100, "phase": "navigation", "method": "GET", "url": f"tauri://localhost/{route}", "resource_type": "document", "status": 0, "task_request": False, "pending_count_after": 0},
        {"sequence": 2, "request_id": "request-1", "observed_monotonic_ns": 101, "phase": "settle", "method": "GET", "url": f"tauri://localhost/{route}", "resource_type": "document", "status": 200, "task_request": False, "pending_count_after": 0},
    ]


def _network_seal(route: str = "#home") -> dict:
    ledger = _network_ledger(route)
    return {"sealed": True, "pending_request_count": 0, "quiet_window_ms": 650, "quiet_elapsed_ms": 1400.0, "instrumentation_integrity": True, "late_event_count": 0, "late_events": [], "deny_all_network_guard": True, "denied_attempt_count": 0, "denied_attempts": [], "final_window_ms": 10750, "final_window_elapsed_ms": 10850.0, "ledger_count": len(ledger), "ledger_digest_material": ledger}


def _minimal_attestation(
    *,
    nonce: bytes,
    challenge: dict,
    package: dict,
    app_executable: Path,
    runner_executable: Path,
    runner_pid: int,
    reported_pid: int | None = None,
) -> dict:
    app = {
        "schema_version": retirement.APP_ATTESTATION_SCHEMA,
        "status": "packaged_tauri_app_nonce_attested",
        "pid": 999,
        "parent_pid": runner_pid,
        "parent_executable_path": str(runner_executable.resolve()),
        "executable_path": str(app_executable.resolve()),
        "executable_sha256": package["app_executable_sha256"],
        "bundle_sha256": package["app_bundle_sha256"],
        "artifact_set_sha256": package["artifact_set_sha256"],
        "dmg_sha256": package["dmg_sha256"],
        "head_full": HEAD,
        "challenge_digest": challenge["challenge_digest"],
        "nonce_digest": hashlib.sha256(nonce).hexdigest(),
        "source_contract_digest": challenge["source_contract_digest"],
        "ordinary_component_map_digest": challenge["ordinary_component_map_digest"],
        "route_payload_sha256": retirement._digest([]),
        "network_seal_sha256": retirement._digest(_network_seal()),
        "native_snapshot_api": "WKWebView.takeSnapshotWithConfiguration.afterScreenUpdates",
        "final_network_guard": "deny_all_then_exit",
        "final_window_ms": 10750,
        "exit_after_output": True,
        "expected_exit_code": 0,
    }
    app["exit_contract_sha256"] = retirement._digest({
        "final_network_guard": "deny_all_then_exit",
        "final_window_ms": 10750,
        "exit_after_output": True,
        "expected_exit_code": 0,
    })
    app["response_sha256"] = hashlib.sha256(nonce + retirement._canonical_bytes(app)).hexdigest()
    report = {
        "schema_version": retirement.ATTESTATION_SCHEMA,
        "status": "actual_packaged_tauri_ordinary_flow_passed",
        "attestation_mode": "production_packaged_tauri_nonce_bound",
        "runner_identity": "scripts/streamlit_retirement_packaged_qa_runner.mjs",
        "runner_pid": reported_pid if reported_pid is not None else runner_pid,
        "runner_executable_path": str(runner_executable.resolve()),
        "runner_source_sha256": retirement._runner_source_sha256(ROOT),
        "generated_at": "2026-07-15T09:00:00Z",
        "challenge_id": challenge["challenge_id"],
        "challenge_digest": challenge["challenge_digest"],
        "nonce_digest": hashlib.sha256(nonce).hexdigest(),
        "source_contract_digest": challenge["source_contract_digest"],
        "ordinary_component_map_digest": challenge["ordinary_component_map_digest"],
        "head_full": HEAD,
        "runtime_surface": "actual_packaged_tauri_react",
        "protocol": "tauri:",
        "package_head_full": HEAD,
        "artifact_set_sha256": package["artifact_set_sha256"],
        "app_bundle_sha256": package["app_bundle_sha256"],
        "app_executable_sha256": package["app_executable_sha256"],
        "dmg_sha256": package["dmg_sha256"],
        "app_attestation": app,
        "app_exit_confirmed": True,
        "app_exit_code": 0,
        "app_exit_signal": "",
        "route_count": 6,
        "viewport_count": 2,
        "qa_matrix_count": 12,
        "passed_count": 12,
        "review_required_count": 0,
        "network_ledger_complete": True,
        "network_seal_audit": _network_seal(),
        "rows": [],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    report["runner_response_sha256"] = hashlib.sha256(
        nonce + retirement._canonical_bytes(report)
    ).hexdigest()
    return report


class StreamlitRetirementEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(os.environ, {"STOCK_MING_DESKTOP_NODE_MODULES": NODE_MODULES})
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()

    def test_runner_plan_capability_and_trusted_mode_fail_before_nonce_or_launch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            runner = project / "scripts/streamlit_retirement_packaged_qa_runner.mjs"
            for relative in (
                Path("scripts/streamlit_retirement_packaged_qa_runner.mjs"),
                Path("desktop/src-tauri/src/ltg10_packaged_qa.rs"),
                Path("desktop/src-tauri/src/ltg10_packaged_qa_init.js"),
                Path("desktop/src-tauri/src/main.rs"),
            ):
                destination = project / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            common = ["--project-root", str(project), "--json"]
            plan = subprocess.run(
                ["node", str(runner), "--print-plan", *common],
                cwd=project,
                check=True,
                text=True,
                capture_output=True,
            )
            capability = subprocess.run(
                ["node", str(runner), "--print-capability", *common],
                cwd=project,
                check=True,
                text=True,
                capture_output=True,
            )
            blocked = subprocess.run(
                [
                    "node",
                    str(runner),
                    "--trusted-session",
                    "--challenge-file",
                    "/definitely/not/read.json",
                    "--nonce-fd",
                    "9999",
                    *common,
                ],
                cwd=project,
                check=False,
                text=True,
                capture_output=True,
            )
        plan_payload = json.loads(plan.stdout)
        capability_payload = json.loads(capability.stdout)
        blocked_payload = json.loads(blocked.stdout)

        self.assertEqual(plan_payload["qa_matrix_count"], 12)
        self.assertFalse(plan_payload["public_raw_report_accepted"])
        self.assertEqual(plan_payload["evidence_transport"], "recorder_private_one_shot_session_only")
        self.assertFalse(capability_payload["packaged_dom_driver_supported"])
        self.assertFalse(capability_payload["production_nonce_attestation_supported"])
        self.assertEqual(capability_payload["challenge_transport"], "inherited_fd_and_private_0700_session")
        self.assertFalse(capability_payload["public_raw_report_accepted"])
        self.assertEqual(blocked.returncode, 2)
        self.assertFalse(blocked_payload["attempted_launch"])
        self.assertFalse(blocked_payload["nonce_read"])
        self.assertFalse(blocked_payload["challenge_read"])
        self.assertFalse(blocked_payload["raw_report_written"])

    def test_recorder_on_unsupported_macos_writes_no_session_key_event_or_raw(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_root = Path(temp_dir) / "evidence"
            with patch.object(retirement, "_trusted_sources_match_commit", return_value=True), patch.object(
                retirement, "validate_tauri_production_package", return_value=_package()
            ), patch.object(
                retirement,
                "_trusted_runner_capability",
                return_value=(None, "packaged_tauri_dom_or_nonce_attestation_unavailable"),
            ):
                result = retirement.record_streamlit_primary_retirement_attestation(
                    evidence_root,
                    expected_head_full=HEAD,
                    project_root=ROOT,
                )
            self.assertFalse(evidence_root.exists())

        self.assertFalse(result["streamlit_primary_retired"])
        self.assertIn("packaged_tauri_dom_or_nonce_attestation_unavailable", result["blockers"])

    def test_dirty_or_wrong_head_trusted_sources_block_before_capability_or_writes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_root = Path(temp_dir) / "evidence"
            with patch.object(retirement, "_trusted_sources_match_commit", return_value=False), patch.object(
                retirement, "_trusted_runner_capability"
            ) as capability:
                result = retirement.record_streamlit_primary_retirement_attestation(
                    evidence_root,
                    expected_head_full=HEAD,
                    project_root=ROOT,
                )
            capability.assert_not_called()
            self.assertFalse(evidence_root.exists())

        self.assertFalse(result["streamlit_primary_retired"])
        self.assertEqual(result["blockers"], ["trusted_runner_sources_not_exactly_bound_to_head"])

    def test_public_json_synthetic_png_and_sqlite_boolean_cannot_self_seal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            public = root / "streamlit_retirement/raw"
            public.mkdir(parents=True)
            (public / "packaged_ordinary_flow.json").write_text(
                json.dumps({"status": "actual_packaged_tauri_ordinary_flow_passed", "streamlit_primary_retired": True}),
                encoding="utf-8",
            )
            (public / "synthetic.png").write_bytes(b"not-a-runner-owned-image")
            with sqlite3.connect(root / "meta.sqlite") as connection:
                connection.execute("CREATE TABLE packets (packet_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL)")
                connection.execute(
                    "INSERT INTO packets VALUES (?, ?)",
                    ("streamlit_primary_retired", json.dumps({"streamlit_primary_retired": True, "head_full": HEAD})),
                )
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            with patch.object(retirement, "_trusted_sources_match_commit", return_value=True), patch.object(
                retirement, "validate_tauri_production_package", return_value=_package()
            ):
                recorded = retirement.record_streamlit_primary_retirement_attestation(
                    root,
                    expected_head_full=HEAD,
                    project_root=ROOT,
                )
                validated = retirement.validate_streamlit_primary_retirement(
                    root,
                    expected_head_full=HEAD,
                    tauri_package_verification=_package(),
                    project_root=ROOT,
                )
            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))

        self.assertFalse(recorded["streamlit_primary_retired"])
        self.assertFalse(validated["streamlit_primary_retired"])
        self.assertIn("trusted_runner_key_missing", validated["blockers"])
        self.assertEqual(before, after)

    def test_canvas_manifest_requires_hmac_human_review_and_public_forge_cannot_promote(self):
        source, blocker = retirement._source_contract(ROOT)
        self.assertEqual(blocker, "")
        assert source is not None
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            root.mkdir()
            session = Path(temp_dir) / "session"
            session.mkdir(mode=0o700)
            source_rows = []
            hashes = []
            for index, (route, component) in enumerate(
                (pair for viewport in retirement.EXPECTED_VIEWPORTS for pair in retirement.EXPECTED_ROUTES),
                1,
            ):
                viewport = list(retirement.EXPECTED_VIEWPORTS)[(index - 1) // len(retirement.EXPECTED_ROUTES)]
                image = Image.new("RGBA", (32, 32), (0, 0, 0, 255))
                pixels = image.load()
                for y in range(32):
                    for x in range(32):
                        pixels[x, y] = ((x * 13 + y + index) % 256, (x + y * 11 + index) % 256, (x * 7 + y * 3 + index) % 256, 255)
                path = session / f"{index:02d}.png"
                image.save(path, format="PNG")
                path.chmod(0o600)
                screenshot_sha = hashlib.sha256(path.read_bytes()).hexdigest()
                hashes.append(screenshot_sha)
                source_rows.append({
                    "sequence": index,
                    "route": route,
                    "component": component,
                    "viewport": viewport,
                    "source_screenshot_path": str(path),
                    "screenshot_sha256": screenshot_sha,
                    "pixel_width": 32,
                    "pixel_height": 32,
                })
            derived = {
                "head_full": HEAD,
                "runner_source_sha256": retirement._runner_source_sha256(ROOT),
                "source_contract_digest": source["source_contract_digest"],
                "fallback_disposition": source["fallback_disposition"],
                "artifact_set_sha256": ARTIFACT_SET,
                "app_bundle_sha256": APP_BUNDLE,
                "app_executable_sha256": "d" * 64,
                "dmg_sha256": DMG_SHA,
                "app_attestation_digest": "e" * 64,
                "route_matrix_digest": "f" * 64,
                "screenshot_set_digest": retirement._digest(sorted(hashes)),
                "network_ledger_digest": "1" * 64,
                "route_count": 6,
                "viewport_count": 2,
                "qa_matrix_count": 12,
                "visual_review_required": True,
                "canvas_present_count": 3,
                "visual_review_rows": source_rows,
            }
            secret, blocker = retirement._create_secret(root)
            self.assertEqual(blocker, "")
            assert secret is not None
            manifest, blocker = retirement._persist_visual_review_manifest(root, secret, derived)
            self.assertEqual(blocker, "")
            assert manifest is not None
            public_forge = root / "caller_visual_review.json"
            public_forge.write_text(json.dumps({"approved_by_user": True, "streamlit_primary_retired": True}), encoding="utf-8")
            with patch.object(retirement, "_trusted_sources_match_commit", return_value=True), patch.object(
                retirement, "validate_tauri_production_package", return_value=_package()
            ):
                rejected = retirement.record_streamlit_primary_retirement_visual_review(
                    root,
                    expected_head_full=HEAD,
                    review_id=manifest["review_id"],
                    approved_by_user=True,
                    no_legacy_surface=True,
                    no_streamlit_surface=True,
                    no_admin_surface=False,
                    project_root=ROOT,
                )
                approved = retirement.record_streamlit_primary_retirement_visual_review(
                    root,
                    expected_head_full=HEAD,
                    review_id=manifest["review_id"],
                    approved_by_user=True,
                    no_legacy_surface=True,
                    no_streamlit_surface=True,
                    no_admin_surface=True,
                    project_root=ROOT,
                )
                validated = retirement.validate_streamlit_primary_retirement(
                    root,
                    expected_head_full=HEAD,
                    tauri_package_verification=_package(),
                    project_root=ROOT,
                )
                reviewed_screenshot = (
                    root
                    / retirement.VISUAL_REVIEW_PENDING_RELATIVE
                    / manifest["review_id"]
                    / manifest["screenshot_rows"][0]["screenshot_path"]
                )
                reviewed_screenshot.unlink()
                tampered = retirement.validate_streamlit_primary_retirement(
                    root,
                    expected_head_full=HEAD,
                    tauri_package_verification=_package(),
                    project_root=ROOT,
                )
            self.assertTrue(approved["streamlit_primary_retired"], approved)
            self.assertTrue(validated["streamlit_primary_retired"], validated)
            self.assertFalse(tampered["streamlit_primary_retired"])
            self.assertIn("visual_review_screenshot_authentication_failed", tampered["blockers"])
            events, event_blocker = retirement._load_visual_review_event_chain(root, secret)

        self.assertFalse(rejected["streamlit_primary_retired"])
        self.assertIn("literal_user_visual_review_approval_and_surface_flags_required", rejected["blockers"])
        self.assertTrue(approved["streamlit_primary_retired"])
        self.assertEqual(event_blocker, "")
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["approved_by_user"])
        self.assertEqual(events[0]["screenshot_count"], 12)
        self.assertEqual(events[0]["reviewed_screenshots"], manifest["screenshot_rows"])

    def test_private_child_process_nonce_handshake_is_explicitly_nonproduction_and_replay_safe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = Path(temp_dir) / "session"
            session.mkdir(mode=0o700)
            fixture = session / "trusted_runner.mjs"
            fixture.write_text(
                """
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
const args = process.argv.slice(2);
const fd = Number.parseInt(args[args.indexOf('--nonce-fd') + 1], 10);
const nonce = readFileSync(fd);
const payload = {
  schema_version: 'trusted_runner_nonce_handshake_test.v1',
  status: 'nonce_handshake_observed_non_production',
  production_ready: false,
  nonce_digest: createHash('sha256').update(nonce).digest('hex')
};
process.stdout.write(JSON.stringify(payload));
""".strip(),
                encoding="utf-8",
            )
            fixture.chmod(0o600)
            nonce = os.urandom(32)
            read_fd, write_fd = os.pipe()
            process = subprocess.Popen(
                ["node", str(fixture), "--nonce-fd", str(read_fd)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                pass_fds=(read_fd,),
            )
            os.close(read_fd)
            os.write(write_fd, nonce)
            os.close(write_fd)
            stdout, _stderr = process.communicate(timeout=10)
            payload = json.loads(stdout)

        self.assertEqual(process.returncode, 0)
        self.assertGreater(process.pid, 1)
        self.assertFalse(payload["production_ready"])
        self.assertEqual(payload["nonce_digest"], hashlib.sha256(nonce).hexdigest())
        self.assertNotEqual(payload["nonce_digest"], hashlib.sha256(os.urandom(32)).hexdigest())
        self.assertEqual(set(payload), {"schema_version", "status", "production_ready", "nonce_digest"})

    def test_nonce_bound_response_rejects_replay_and_tamper(self):
        nonce = os.urandom(32)
        value = {"status": "non_production_handshake_only", "production_ready": False}
        value["response_sha256"] = hashlib.sha256(nonce + retirement._canonical_bytes(value)).hexdigest()
        self.assertTrue(retirement._nonce_bound_response_valid(value, nonce, response_field="response_sha256"))
        self.assertFalse(
            retirement._nonce_bound_response_valid(value, os.urandom(32), response_field="response_sha256")
        )
        value["production_ready"] = True
        self.assertFalse(retirement._nonce_bound_response_valid(value, nonce, response_field="response_sha256"))

    def test_each_native_route_row_requires_nonce_hmac_and_rejects_tamper(self):
        nonce = os.urandom(32)
        row = {
            "route": "#home",
            "component": "CommandCenterHome",
            "viewport": "desktop",
            "width": 1440,
            "height": 900,
            "observed_inner_width": 1440,
            "observed_inner_height": 900,
            "device_pixel_ratio": 1.0,
            "native_inner_width_px": 1440,
            "native_inner_height_px": 900,
            "screenshot_pixel_width": 1440,
            "screenshot_pixel_height": 900,
            "observed_url": "tauri://localhost/#home",
            "runtime_surface": "actual_packaged_tauri_react",
            "protocol": "tauri:",
            "observation_started_monotonic_ns": 1,
            "observation_finished_monotonic_ns": 2,
            "dom_ledger": _dom_ledger("#home"),
            "task_post_count_before": 0,
            "task_post_count_after": 0,
            "navigation_post_count": 0,
            "pending_request_count": 0,
            "quiet_window_ms": 650,
            "quiet_elapsed_ms": 1300.0,
            "instrumentation_integrity": True,
            "attach_shadow_calls": [],
            "custom_element_events": [],
            "dynamic_frame_events": [],
            "network_ledger_complete": True,
            "network_ledger": _network_ledger(),
            "screenshot_path": "screenshots/01-home-desktop.png",
            "screenshot_byte_length": 123,
            "screenshot_sha256": "a" * 64,
            "screenshot_native_snapshot": True,
        }
        row["row_hmac_sha256"] = hashlib.sha256(b"placeholder").hexdigest()
        material = dict(row)
        material.pop("row_hmac_sha256")
        import hmac

        row["row_hmac_sha256"] = hmac.new(
            nonce,
            retirement._canonical_bytes(material),
            hashlib.sha256,
        ).hexdigest()
        self.assertTrue(retirement._runner_row_hmac_valid(row, nonce))
        self.assertFalse(retirement._runner_row_hmac_valid({**row, "route": "#legacy"}, nonce))
        self.assertFalse(retirement._runner_row_hmac_valid(row, os.urandom(32)))

    def test_nonce_attestation_binds_component_map_and_source_digest(self):
        source, blocker = retirement._source_contract(ROOT)
        self.assertEqual(blocker, "")
        assert source is not None
        nonce = os.urandom(32)
        challenge = _build_challenge(nonce=nonce, package=_package(), source=source)
        self.assertEqual(challenge["source_contract_digest"], source["source_contract_digest"])
        self.assertEqual(
            challenge["ordinary_component_map_digest"],
            retirement._digest(
                {route.removeprefix("#"): component for route, component in retirement.EXPECTED_ROUTES}
            ),
        )
        challenge_material = dict(challenge)
        observed_challenge_digest = challenge_material.pop("challenge_digest")
        self.assertEqual(observed_challenge_digest, retirement._digest(challenge_material))
        for field in ("source_contract_digest", "ordinary_component_map_digest"):
            with self.subTest(challenge_field=field):
                tampered = dict(challenge_material)
                tampered[field] = "0" * 64
                self.assertNotEqual(observed_challenge_digest, retirement._digest(tampered))

        report = {
            "source_contract_digest": challenge["source_contract_digest"],
            "ordinary_component_map_digest": challenge["ordinary_component_map_digest"],
        }
        report["runner_response_sha256"] = hashlib.sha256(
            nonce + retirement._canonical_bytes(report)
        ).hexdigest()
        self.assertTrue(
            retirement._nonce_bound_response_valid(report, nonce, response_field="runner_response_sha256")
        )
        for field in ("source_contract_digest", "ordinary_component_map_digest"):
            with self.subTest(attestation_field=field):
                tampered = dict(report)
                tampered[field] = "f" * 64
                self.assertFalse(
                    retirement._nonce_bound_response_valid(
                        tampered,
                        nonce,
                        response_field="runner_response_sha256",
                    )
                )

    def test_runner_challenge_rejects_forged_or_alternate_fixed_package_identity(self):
        source, blocker = retirement._source_contract(ROOT)
        self.assertEqual(blocker, "")
        assert source is not None
        package = _package()
        measured = _measured_package(package)
        attacks = (
            {**measured, "artifact_set_sha256": "0" * 64},
            {**measured, "app_path": str(ROOT / "alternate.app")},
            {**measured, "dmg_path": str(ROOT / "alternate.dmg")},
        )
        for attack in attacks:
            with self.subTest(attack=attack):
                with patch.object(
                    retirement.tauri_package_verifier,
                    "measure_fixed_tauri_package_artifacts",
                    return_value=attack,
                ):
                    with self.assertRaisesRegex(ValueError, "fixed_package_disk_identity_not_current"):
                        retirement._build_runner_challenge(
                            nonce=os.urandom(32),
                            expected_head_full=HEAD,
                            package=package,
                            source=source,
                        )

    def test_dom_network_and_task_ledgers_are_raw_exact_and_post_zero(self):
        ready, heading, actual_component = retirement._dom_ledger_ready(
            _dom_ledger("#home"),
            "#home",
            "CommandCenterHome",
        )
        self.assertTrue(ready)
        self.assertEqual(heading, "今日作战台")
        self.assertEqual(actual_component, "CommandCenterHome")
        def changed(kind: str, selector: str, value: object) -> list[dict]:
            rows = _dom_ledger("#home")
            target = next(row for row in rows if row["kind"] == kind and row["selector"] == selector)
            target["value"] = value
            return rows

        for kind, selector, value in (
            ("attribute", "button[data-route-active='true']@data-route-key", "legacy"),
            ("attribute", retirement.COMPONENT_ATTRIBUTE_SELECTOR, "LegacyTools"),
            ("count", retirement.FORBIDDEN_COMPONENT_SELECTOR, 1),
            ("count", retirement.ROOT_COMPONENT_COUNT_SELECTOR, 0),
            ("count", retirement.BODY_NON_ROOT_SURFACE_SELECTOR, 1),
            ("count", "body@frame-surface-count", 1),
            ("count", "body@open-shadow-root-count", 1),
            ("count", "body@attach-shadow-call-count", 1),
            ("count", "body@custom-element-event-count", 1),
            ("count", "body@custom-element-surface-count", 1),
            ("count", "body@dynamic-frame-create-count", 1),
            ("text", "[data-ltg10-route-heading]", "fake heading"),
            ("attribute", "[data-ltg10-route-heading]@tagName", "div"),
        ):
            with self.subTest(selector=selector, value=value):
                self.assertFalse(retirement._dom_ledger_ready(changed(kind, selector, value), "#home", "CommandCenterHome")[0])

        body_inventory = changed(
            "html",
            retirement.BODY_HTML_SELECTOR,
            '<div id="root"><div data-ltg10-component-id="CommandCenterHome">ordinary</div></div><div>SystemMigration</div>',
        )
        self.assertFalse(retirement._dom_ledger_ready(body_inventory, "#home", "CommandCenterHome")[0])

        for kind, selector, attack in (
            ("accessibility", "body@accessibility-tree", "Admin\u034fTools"),
            ("pseudo", "body@pseudo-content", "&quot;SystemMigration&quot;"),
        ):
            rows = _dom_ledger("#home")
            target = next(row for row in rows if row["kind"] == kind and row["selector"] == selector)
            payload = json.loads(target["value"])
            payload[0]["name" if kind == "accessibility" else "before"] = attack
            target["value"] = json.dumps(payload)
            self.assertFalse(retirement._dom_ledger_ready(rows, "#home", "CommandCenterHome")[0])

        hidden_heading = _dom_ledger("#home")
        computed = next(row for row in hidden_heading if row["kind"] == "computed")
        computed_rows = json.loads(computed["value"])
        computed_rows[1]["visible"] = False
        computed_rows[1]["display"] = "none"
        computed["value"] = json.dumps(computed_rows)
        self.assertFalse(retirement._dom_ledger_ready(hidden_heading, "#home", "CommandCenterHome")[0])

        for field, value in (
            ("viewport_intersection", 0.0),
            ("content_visibility", "hidden"),
            ("occluded", True),
            ("color_alpha", 0.0),
        ):
            with self.subTest(heading_visibility_field=field):
                rows = _dom_ledger("#home")
                computed = next(row for row in rows if row["kind"] == "computed")
                computed_rows = json.loads(computed["value"])
                computed_rows[1][field] = value
                computed["value"] = json.dumps(computed_rows)
                self.assertFalse(retirement._dom_ledger_ready(rows, "#home", "CommandCenterHome")[0])

        network = _network_ledger()
        self.assertTrue(retirement._network_ledger_complete(network))
        self.assertTrue(retirement._local_network_row(network[0], 1))
        self.assertFalse(retirement._network_ledger_complete([{**network[0], "url": "http://localhost:8501/"}, network[1]]))
        self.assertFalse(retirement._network_ledger_complete([network[0]]))
        delayed_post = [*network, {**network[0], "sequence": 3, "request_id": "request-2", "method": "POST", "task_request": True}]
        self.assertFalse(retirement._network_ledger_complete(delayed_post))
        self.assertTrue(retirement._network_seal_ready(_network_seal()))
        self.assertFalse(retirement._network_seal_ready({**_network_seal(), "late_event_count": 1, "late_events": [{"kind": "fetch"}]}))
        self.assertFalse(retirement._network_seal_ready({**_network_seal(), "denied_attempt_count": 1, "denied_attempts": [{"kind": "fetch"}]}))
        self.assertFalse(retirement._network_seal_ready({**_network_seal(), "final_window_elapsed_ms": 10_000.0}))
        late_get = [
            *_network_ledger(),
            {"sequence": 3, "request_id": "request-2", "observed_monotonic_ns": 102, "phase": "navigation", "method": "GET", "url": "http://127.0.0.1:8710/api/health", "resource_type": "fetch", "status": 0, "task_request": False, "pending_count_after": 1},
            {"sequence": 4, "request_id": "request-2", "observed_monotonic_ns": 103, "phase": "settle", "method": "GET", "url": "http://127.0.0.1:8710/api/health", "resource_type": "fetch", "status": 200, "task_request": False, "pending_count_after": 0},
        ]
        late_get_seal = {**_network_seal(), "ledger_count": len(late_get), "ledger_digest_material": late_get}
        self.assertTrue(retirement._network_seal_ready(late_get_seal))
        self.assertFalse(retirement._network_seal_matches_last_row(late_get_seal, _network_ledger()))
        websocket = {**late_get[2], "method": "CONNECT", "resource_type": "websocket", "task_request": False}
        self.assertFalse(retirement._local_network_row(websocket, 3))
        self.assertTrue(
            retirement._task_post_counts_zero(
                {"task_post_count_before": 0, "task_post_count_after": 0, "navigation_post_count": 0}
            )
        )

    def test_native_png_requires_exact_dimensions_integrity_and_visual_content(self):
        viewport_row = {
            "observed_inner_width": 390,
            "observed_inner_height": 844,
            "device_pixel_ratio": 2.0,
        }
        self.assertEqual(retirement._measured_viewport_ready(viewport_row, (390, 844)), (True, (780, 1688)))
        self.assertFalse(retirement._measured_viewport_ready({**viewport_row, "observed_inner_width": 391}, (390, 844))[0])
        self.assertFalse(retirement._measured_viewport_ready({**viewport_row, "device_pixel_ratio": 0.0}, (390, 844))[0])
        self.assertFalse(retirement._measured_viewport_ready({**viewport_row, "device_pixel_ratio": float("nan")}, (390, 844))[0])
        solid = Image.new("RGBA", (390, 844), (255, 255, 255, 255))
        solid_bytes = BytesIO()
        solid.save(solid_bytes, format="PNG")
        self.assertFalse(retirement._png_bytes_valid(solid_bytes.getvalue(), (390, 844)))

        gradient = Image.new("RGBA", (390, 844), (0, 0, 0, 255))
        pixels = gradient.load()
        for y in range(844):
            for x in range(390):
                pixels[x, y] = ((x * 7 + y) % 256, (x + y * 3) % 256, (x * 5 + y * 11) % 256, 255)
        gradient_bytes = BytesIO()
        gradient.save(gradient_bytes, format="PNG")
        payload = gradient_bytes.getvalue()
        self.assertTrue(retirement._png_bytes_valid(payload, (390, 844)))
        self.assertFalse(retirement._png_bytes_valid(payload, (1440, 900)))
        self.assertFalse(retirement._png_bytes_valid(payload[:-1] + b"x", (390, 844)))
        self.assertFalse(
            retirement._task_post_counts_zero(
                {"task_post_count_before": 7, "task_post_count_after": 7, "navigation_post_count": 0}
            )
        )

    def test_wrong_runner_pid_executable_and_old_package_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = Path(temp_dir) / "session"
            screenshots = session / "screenshots"
            screenshots.mkdir(parents=True, mode=0o700)
            app_executable = Path(temp_dir) / "actual-app"
            app_executable.write_bytes(b"packaged executable bytes")
            executable_sha = hashlib.sha256(app_executable.read_bytes()).hexdigest()
            package = _package(executable_sha=executable_sha)
            source, blocker = retirement._source_contract(ROOT)
            self.assertEqual(blocker, "")
            assert source is not None
            nonce = os.urandom(32)
            challenge = _build_challenge(nonce=nonce, package=package, source=source)
            expected_runner = session / "trusted_runner.mjs"
            expected_runner.write_bytes((ROOT / "scripts/streamlit_retirement_packaged_qa_runner.mjs").read_bytes())
            expected_runner.chmod(0o600)
            wrong_runner = session / "fake-runner.mjs"
            wrong_runner.write_text("// fake", encoding="utf-8")
            wrong_runner.chmod(0o600)
            report = _minimal_attestation(
                nonce=nonce,
                challenge=challenge,
                package=package,
                app_executable=app_executable,
                runner_executable=wrong_runner,
                runner_pid=1234,
                reported_pid=9999,
            )
            with patch.object(
                retirement.tauri_package_verifier,
                "measure_fixed_tauri_package_artifacts",
                return_value=_measured_package(package),
            ):
                derived, blockers = retirement._validate_trusted_runner_attestation(
                    session,
                    attestation=report,
                    challenge=challenge,
                    nonce=nonce,
                    expected_runner_pid=1234,
                    expected_runner_executable=expected_runner,
                    expected_head_full=HEAD,
                    package=package,
                    project_root=ROOT,
                )
                old_package = {**package, "head_full": OLD_HEAD}
                _derived_old, old_blockers = retirement._validate_trusted_runner_attestation(
                    session,
                    attestation=report,
                    challenge=challenge,
                    nonce=nonce,
                    expected_runner_pid=1234,
                    expected_runner_executable=expected_runner,
                    expected_head_full=HEAD,
                    package=old_package,
                    project_root=ROOT,
                )

        self.assertIsNone(derived)
        self.assertIn("trusted_runner_identity_nonce_or_head_invalid", blockers)
        self.assertIn("formal_package_verifier_binding_invalid", old_blockers)

    def test_fake_runner_file_is_rejected_before_process_launch_or_nonce_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = Path(temp_dir) / "session"
            session.mkdir(mode=0o700)
            runner = session / "trusted_runner.mjs"
            runner.write_text("process.stdout.write('{}')", encoding="utf-8")
            runner.chmod(0o600)
            source, blocker = retirement._source_contract(ROOT)
            self.assertEqual(blocker, "")
            assert source is not None
            nonce = os.urandom(32)
            challenge_value = _build_challenge(nonce=nonce, package=_package(), source=source)
            challenge = session / "challenge.json"
            challenge.write_bytes(retirement._canonical_bytes(challenge_value))
            challenge.chmod(0o600)
            payload, pid, blocker = retirement._execute_trusted_runner_session(
                session_root=session,
                runner_executable=runner,
                challenge_path=challenge,
                nonce=nonce,
                project_root=ROOT,
            )

        self.assertIsNone(payload)
        self.assertEqual(pid, 0)
        self.assertEqual(blocker, "trusted_runner_session_executable_identity_invalid")

    def test_symlinked_private_session_parent_is_rejected_without_external_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            root.mkdir()
            outside = Path(temp_dir) / "outside"
            outside.mkdir(mode=0o755)
            (root / "streamlit_retirement").symlink_to(outside, target_is_directory=True)
            source, blocker = retirement._source_contract(ROOT)
            self.assertEqual(blocker, "")
            assert source is not None
            nonce = os.urandom(32)
            challenge = _build_challenge(nonce=nonce, package=_package(), source=source)
            session, runner, challenge_path, blocker = retirement._prepare_private_runner_session(
                root,
                project_root=ROOT,
                challenge=challenge,
            )
            outside_entries = list(outside.iterdir())
            outside_mode = stat.S_IMODE(outside.stat().st_mode)

        self.assertIsNone(session)
        self.assertIsNone(runner)
        self.assertIsNone(challenge_path)
        self.assertEqual(blocker, "private_directory_insecure")
        self.assertEqual(outside_entries, [])
        self.assertEqual(outside_mode, 0o755)

    def test_typescript_ast_contract_is_exact_and_maps_real_components(self):
        result, blocker = retirement._inspect_typescript_source(ROOT)
        self.assertEqual(blocker, "")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["ordinary_routes"], ["home", "candidates", "factor", "next", "marginEtf", "qmt-replay"])
        self.assertEqual(result["ordinary_components"]["home"], "CommandCenterHome")
        self.assertEqual(result["ordinary_component_root_ids"], result["ordinary_components"])
        self.assertEqual(result["active_route_binding"], "ROUTE_COMPONENTS[route]")
        self.assertEqual(result["component_root_identity_attribute"], "data-ltg10-component-id")
        self.assertEqual(
            result["ordinary_component_import_manifest_digest"],
            retirement.EXPECTED_IMPORT_MANIFEST_DIGEST,
        )
        self.assertEqual(set(result["ordinary_component_import_manifest"]), set(result["ordinary_routes"]))
        self.assertEqual(result["legacy_component_root_id"], "LegacyTools")
        self.assertEqual(result["legacy_route_group"], "系统迁移")
        self.assertFalse(result["legacy_route_primary"])

    def test_import_specifier_kind_local_and_duplicate_manifest_is_exact(self):
        mutations = (
            lambda source: 'import type { TaskCreationEnvelope as ExtraEnvelope } from "../api/client";\n' + source,
            lambda source: source.replace(
                'import { useEffect, useState } from "react";',
                'import type { useEffect, useState } from "react";',
                1,
            ),
            lambda source: source.replace(
                'import { useEffect, useState } from "react";',
                'import { useEffect as observeEffect, useState } from "react";',
                1,
            ),
            lambda source: 'import * as ReactRuntime from "react";\n' + source,
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp_dir:
                project = Path(temp_dir) / "project"
                _copy_source_contract(project)
                component_path = project / "desktop/src/routes/CommandCenterHome.tsx"
                source = component_path.read_text(encoding="utf-8")
                component_path.write_text(mutation(source), encoding="utf-8")
                result, blocker = retirement._inspect_typescript_source(project)
                self.assertIsNone(result)
                self.assertEqual(blocker, "source_ast_contract_blocked")

    def test_native_adapter_has_no_public_driver_or_environment_qa_surface(self):
        native = (ROOT / "desktop/src-tauri/src/ltg10_packaged_qa.rs").read_text(encoding="utf-8")
        init = (ROOT / "desktop/src-tauri/src/ltg10_packaged_qa_init.js").read_text(encoding="utf-8")
        main = (ROOT / "desktop/src-tauri/src/main.rs").read_text(encoding="utf-8")
        runner = (ROOT / "scripts/streamlit_retirement_packaged_qa_runner.mjs").read_text(encoding="utf-8")
        for token in (
            "eval_with_callback",
            "set_size",
            "with_webview",
            "takeSnapshotWithConfiguration_completionHandler",
            "--ltg10-qa-in-fd",
            "--ltg10-qa-out-fd",
            "S_IFIFO",
            "proc_pidpath",
        ):
            self.assertIn(token, native)
        for token in ("fetch", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon", "Worker", "serviceWorker", "ServiceWorkerContainer", "PerformanceObserver"):
            self.assertIn(token, init)
        self.assertIn("append_invoke_initialization_script", main)
        self.assertIn("os.pipe()", (ROOT / "server/services/streamlit_retirement_evidence_service.py").read_text())
        self.assertIn("WKWebView.takeSnapshotWithConfiguration.afterScreenUpdates", runner)
        for forbidden in ("webdriverio", "wdio", "open_devtools", "devtools", "Safari inspector"):
            self.assertNotIn(forbidden, f"{native}\n{init}\n{runner}")
        self.assertNotIn("std::env::var", native)
        self.assertNotIn("127.0.0.1", native)
        self.assertNotIn("8710", native)

    def test_document_start_prototype_guards_execute_and_delayed_network_is_denied(self):
        init_path = ROOT / "desktop/src-tauri/src/ltg10_packaged_qa_init.js"
        harness = r"""
const fs = require('node:fs');
const vm = require('node:vm');
let clock = 0;
const nativeCalls = { fetch: 0, xhr: 0, websocket: 0, eventsource: 0, worker: 0, beacon: 0, serviceworker: 0 };
class Window {}
class FakeTarget { addEventListener() {} }
class XMLHttpRequest extends FakeTarget { open() {} send() { nativeCalls.xhr += 1; } }
class WebSocket extends FakeTarget { constructor() { super(); nativeCalls.websocket += 1; } }
class EventSource extends FakeTarget { constructor() { super(); nativeCalls.eventsource += 1; } }
class Worker extends FakeTarget { constructor() { super(); nativeCalls.worker += 1; } terminate() {} }
class ServiceWorkerContainer { register() { nativeCalls.serviceworker += 1; return Promise.resolve({}); } }
class Navigator { constructor() { this.serviceWorker = new ServiceWorkerContainer(); } sendBeacon() { nativeCalls.beacon += 1; return true; } }
class CustomElementRegistry { define() {} }
class Element { constructor() { this.tagName = 'DIV'; } attachShadow() { return {}; } }
class Document {
  createElement() { return new Element(); }
  createElementNS() { return new Element(); }
  querySelector(selector) { return selector === '#root' ? root : null; }
  querySelectorAll() { return []; }
}
const root = { contains: () => true };
const document = new Document();
document.body = { innerHTML: '', innerText: '', querySelectorAll: () => [] };
const navigator = new Navigator();
const customElements = new CustomElementRegistry();
Window.prototype.fetch = async function() { nativeCalls.fetch += 1; return { status: 200, url: 'tauri://localhost/#home' }; };
const sandbox = {
  Window, XMLHttpRequest, WebSocket, EventSource, Worker, ServiceWorkerContainer, Navigator, CustomElementRegistry, Element, Document,
  navigator, customElements, document, location: { href: 'tauri://localhost/#home', hash: '#home' },
  performance: { timeOrigin: 1, now: () => clock }, URL, Proxy, Reflect, DOMException, TypeError,
  MutationObserver: class { observe() {} }, PerformanceObserver: class { constructor(callback) { this.callback = callback; } observe() {} },
  Node: { ELEMENT_NODE: 1 }, CSS: { escape: (value) => String(value) },
  getComputedStyle: () => ({ display: 'block', visibility: 'visible', opacity: '1', overflow: 'visible', overflowX: 'visible', overflowY: 'visible', color: 'rgb(0,0,0)', backgroundColor: 'white', contentVisibility: 'visible', content: 'none' }),
  setTimeout, clearTimeout, setImmediate, console, Map, Set, Array, Object, String, Number, Boolean, Math, JSON, Promise
};
Object.setPrototypeOf(sandbox, Window.prototype);
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), sandbox, { filename: process.argv[2] });
(async () => {
  clock = 2_000;
  const api = sandbox.__STOCK_MING_LTG10_QA__;
  const token = api.beginSeal();
  await new Promise((resolve) => setImmediate(resolve));
  const started = api.takeObservation(token);
  const descriptorsLocked = [
    [sandbox.Window.prototype, 'fetch'], [sandbox.XMLHttpRequest.prototype, 'open'], [sandbox.XMLHttpRequest.prototype, 'send'],
    [sandbox.XMLHttpRequest.prototype, 'constructor'], [sandbox.WebSocket.prototype, 'constructor'],
    [sandbox.EventSource.prototype, 'constructor'], [sandbox.Worker.prototype, 'constructor'],
    [sandbox.Navigator.prototype, 'sendBeacon'], [sandbox.ServiceWorkerContainer.prototype, 'register'],
    [sandbox.CustomElementRegistry.prototype, 'define']
  ].every(([owner, key]) => { const d = Object.getOwnPropertyDescriptor(owner, key); return d && d.writable === false && d.configurable === false; });
  clock += 10_100;
  const attempts = [];
  for (const Constructor of [sandbox.WebSocket.prototype.constructor, sandbox.EventSource.prototype.constructor, sandbox.Worker.prototype.constructor]) {
    try { new Constructor('http://127.0.0.1:8710/late'); } catch { attempts.push(true); }
  }
  const xhr = new sandbox.XMLHttpRequest.prototype.constructor();
  xhr.open('GET', 'http://127.0.0.1:8710/late');
  try { xhr.send(); } catch { attempts.push(true); }
  attempts.push((await sandbox.Window.prototype.fetch.call(sandbox, 'http://127.0.0.1:8710/late').then(() => false, () => true)));
  attempts.push(sandbox.Navigator.prototype.sendBeacon.call(sandbox.navigator, 'http://127.0.0.1:8710/late') === false);
  attempts.push((await sandbox.ServiceWorkerContainer.prototype.register.call(sandbox.navigator.serviceWorker, 'http://127.0.0.1:8710/late-sw.js').then(() => false, () => true)));
  const seal = api.verifySeal();
  process.stdout.write(JSON.stringify({
    descriptorsLocked, startedReady: started.status === 'ready' && started.value.hook_integrity === true,
    attempts, denied: seal.denied_attempt_count, late: seal.late_event_count, nativeCalls
  }));
})().catch((error) => { console.error(error); process.exit(1); });
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "prototype_guard.cjs"
            path.write_text(harness, encoding="utf-8")
            result = subprocess.run(
                ["node", str(path), str(init_path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                timeout=20,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["descriptorsLocked"])
        self.assertTrue(payload["startedReady"])
        self.assertEqual(payload["attempts"], [True] * 7)
        self.assertEqual(payload["denied"], 7)
        self.assertGreaterEqual(payload["late"], 7)
        self.assertEqual(payload["nativeCalls"], {"fetch": 0, "xhr": 0, "websocket": 0, "eventsource": 0, "worker": 0, "beacon": 0, "serviceworker": 0})

    def test_active_route_binding_alias_conditional_and_component_root_mutations_fail_ast(self):
        mutations = (
            (
                "dot_legacy",
                lambda app: app.replace(
                    "const ActiveRoute = ROUTE_COMPONENTS[route];",
                    "const ActiveRoute = ROUTE_COMPONENTS.legacy;",
                    1,
                ),
            ),
            (
                "indirect_alias",
                lambda app: app.replace(
                    "const ActiveRoute = ROUTE_COMPONENTS[route];",
                    "const selectedRoute = route;\n  const ActiveRoute = ROUTE_COMPONENTS[selectedRoute];",
                    1,
                ),
            ),
            (
                "conditional_fallback",
                lambda app: app.replace(
                    "const ActiveRoute = ROUTE_COMPONENTS[route];",
                    'const ActiveRoute = route === "home" ? ROUTE_COMPONENTS[route] : ROUTE_COMPONENTS.legacy;',
                    1,
                ),
            ),
        )
        for name, mutation in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                project = Path(temp_dir) / "project"
                _copy_source_contract(project)
                app_path = project / "desktop/src/App.tsx"
                app = app_path.read_text(encoding="utf-8")
                changed = mutation(app)
                self.assertNotEqual(changed, app)
                app_path.write_text(changed, encoding="utf-8")
                result, blocker = retirement._inspect_typescript_source(project)
                self.assertIsNone(result)
                self.assertEqual(blocker, "source_ast_contract_blocked")

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            _copy_source_contract(project)
            component_path = project / "desktop/src/routes/CommandCenterHome.tsx"
            component = component_path.read_text(encoding="utf-8")
            changed = component.replace(
                'data-ltg10-component-id="CommandCenterHome"',
                'data-ltg10-component-id="LegacyTools"',
                1,
            )
            self.assertNotEqual(changed, component)
            component_path.write_text(changed, encoding="utf-8")
            result, blocker = retirement._inspect_typescript_source(project)
        self.assertIsNone(result)
        self.assertEqual(blocker, "source_ast_contract_blocked")

    def test_p0_active_route_reassignment_direct_map_conditional_shadow_and_portal_fail_ast(self):
        app_mutations = (
            (
                "let_then_assign_legacy",
                lambda app: app.replace(
                    "const ActiveRoute = ROUTE_COMPONENTS[route];",
                    "let ActiveRoute = ROUTE_COMPONENTS[route];\n  ActiveRoute = ROUTE_COMPONENTS.legacy;",
                    1,
                ),
            ),
            (
                "direct_route_map_member_render",
                lambda app: app.replace(
                    "<ActiveRoute key={route} />",
                    "<><ActiveRoute key={route} /><ROUTE_COMPONENTS.legacy /></>",
                    1,
                ),
            ),
            (
                "conditional_rendered_route",
                lambda app: app.replace(
                    "const ActiveRoute = ROUTE_COMPONENTS[route];",
                    (
                        "const ActiveRoute = ROUTE_COMPONENTS[route];\n"
                        '  const RenderedRoute = route === "home" ? ActiveRoute : ROUTE_COMPONENTS.legacy;'
                    ),
                    1,
                ).replace("<ActiveRoute key={route} />", "<RenderedRoute key={route} />", 1),
            ),
            (
                "nested_active_route_shadow",
                lambda app: app.replace(
                    "const ActiveRoute = ROUTE_COMPONENTS[route];",
                    (
                        "const ActiveRoute = ROUTE_COMPONENTS[route];\n"
                        "  const shadow = () => { const ActiveRoute = ROUTE_COMPONENTS.legacy; return ActiveRoute; };\n"
                        "  void shadow;"
                    ),
                    1,
                ),
            ),
            (
                "const_assignment_attempt",
                lambda app: app.replace(
                    "const ActiveRoute = ROUTE_COMPONENTS[route];",
                    "const ActiveRoute = ROUTE_COMPONENTS[route];\n  ActiveRoute = ROUTE_COMPONENTS.legacy;",
                    1,
                ),
            ),
        )
        for name, mutation in app_mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                project = Path(temp_dir) / "project"
                _copy_source_contract(project)
                app_path = project / "desktop/src/App.tsx"
                app = app_path.read_text(encoding="utf-8")
                changed = mutation(app)
                self.assertNotEqual(changed, app)
                app_path.write_text(changed, encoding="utf-8")
                result, blocker = retirement._inspect_typescript_source(project)
                self.assertIsNone(result)
                self.assertEqual(blocker, "source_ast_contract_blocked")

        portal_mutations = (
            (
                "direct_create_portal",
                'import { createPortal } from "react-dom";',
                "createPortal",
            ),
            (
                "aliased_create_portal",
                'import { createPortal as sendOutside } from "react-dom";',
                "sendOutside",
            ),
        )
        for name, import_line, portal_name in portal_mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                project = Path(temp_dir) / "project"
                _copy_source_contract(project)
                component_path = project / "desktop/src/routes/CommandCenterHome.tsx"
                component = component_path.read_text(encoding="utf-8")
                changed = f"{import_line}\n{component}"
                changed = changed.replace(
                    "export default function CommandCenterHome() {",
                    (
                        "export default function CommandCenterHome() {\n"
                        f'  const portalEscape = {portal_name}(<div>SystemMigration LegacyTools</div>, document.body);'
                    ),
                    1,
                ).replace(
                    '<div data-ltg10-component-id="CommandCenterHome">',
                    '<div data-ltg10-component-id="CommandCenterHome">{portalEscape}',
                    1,
                )
                self.assertNotEqual(changed, component)
                component_path.write_text(changed, encoding="utf-8")
                result, blocker = retirement._inspect_typescript_source(project)
                self.assertIsNone(result)
                self.assertEqual(blocker, "source_ast_contract_blocked")

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            _copy_source_contract(project)
            component_path = project / "desktop/src/routes/CommandCenterHome.tsx"
            component = component_path.read_text(encoding="utf-8")
            changed = component.replace(
                "export default function CommandCenterHome() {",
                (
                    "export default function CommandCenterHome() {\n"
                    "  const PacketCard = () => <div>SystemMigration</div>;"
                ),
                1,
            )
            self.assertNotEqual(changed, component)
            component_path.write_text(changed, encoding="utf-8")
            result, blocker = retirement._inspect_typescript_source(project)
        self.assertIsNone(result)
        self.assertEqual(blocker, "source_ast_contract_blocked")

    def test_ordinary_ast_rejects_frames_srcdoc_shadow_custom_elements_and_legacy_urls(self):
        injections = {
            "neutral_iframe": '  const forbiddenSurface = <iframe src="about:blank" />;\n  void forbiddenSurface;',
            "local_iframe": '  const forbiddenSurface = <iframe src="http://127.0.0.1:8710/" />;\n  void forbiddenSurface;',
            "srcdoc": '  const forbiddenSurface = <iframe srcDoc="neutral" />;\n  void forbiddenSurface;',
            "object": '  const forbiddenSurface = <object data="about:blank" />;\n  void forbiddenSurface;',
            "embed": '  const forbiddenSurface = <embed src="about:blank" />;\n  void forbiddenSurface;',
            "webview": '  const forbiddenSurface = <webview src="about:blank" />;\n  void forbiddenSurface;',
            "portal_tag": '  const forbiddenSurface = <portal src="about:blank" />;\n  void forbiddenSurface;',
            "open_shadow": '  document.createElement("div").attachShadow({ mode: "open" });',
            "closed_shadow": '  document.createElement("div").attachShadow({ mode: "closed" });',
            "custom_registry": '  customElements.define("unsafe-panel", class extends HTMLElement {});',
            "custom_element": '  const forbiddenSurface = <unsafe-panel />;\n  void forbiddenSurface;',
            "legacy_tauri": '  const forbiddenUrl = "tauri://localhost/#legacy";\n  void forbiddenUrl;',
            "streamlit_localhost": '  const forbiddenUrl = "http://localhost:8501/";\n  void forbiddenUrl;',
        }
        for name, injection in injections.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                project = Path(temp_dir) / "project"
                _copy_source_contract(project)
                component_path = project / "desktop/src/routes/CommandCenterHome.tsx"
                component = component_path.read_text(encoding="utf-8")
                changed = component.replace(
                    "export default function CommandCenterHome() {",
                    f"export default function CommandCenterHome() {{\n{injection}",
                    1,
                )
                component_path.write_text(changed, encoding="utf-8")
                result, blocker = retirement._inspect_typescript_source(project)
                self.assertIsNone(result)
                self.assertEqual(blocker, "source_ast_contract_blocked")

    def test_ordinary_ast_rejects_prototype_descriptor_reflect_alias_and_timer_network_escapes(self):
        injections = {
            "prototype_constructor": "  const escape = WebSocket.prototype.constructor; void escape;",
            "descriptor": "  const escape = Object.getOwnPropertyDescriptor(window, 'fetch'); void escape;",
            "reflect": "  const escape = Reflect.get(window, 'fetch'); void escape;",
            "lookup_getter": "  const escape = window.__lookupGetter__('fetch'); void escape;",
            "native_alias": "  const escape = fetch; void escape;",
            "native_call": "  fetch.call(window, '/api/health');",
            "native_apply": "  fetch.apply(window, ['/api/health']);",
            "native_bind": "  const escape = fetch.bind(window); void escape;",
            "delayed_network": "  window.setTimeout(() => fetch('/api/health'), 10_000);",
            "service_worker_register": "  navigator.serviceWorker.register('/late-sw.js');",
        }
        for name, injection in injections.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                project = Path(temp_dir) / "project"
                _copy_source_contract(project)
                component_path = project / "desktop/src/routes/CommandCenterHome.tsx"
                source = component_path.read_text(encoding="utf-8")
                component_path.write_text(
                    source.replace(
                        "export default function CommandCenterHome() {",
                        f"export default function CommandCenterHome() {{\n{injection}",
                        1,
                    ),
                    encoding="utf-8",
                )
                result, blocker = retirement._inspect_typescript_source(project)
                self.assertIsNone(result)
                self.assertEqual(blocker, "source_ast_contract_blocked")

    def test_ordinary_ast_rejects_computed_native_and_new_realm_escapes(self):
        injections = {
            "computed_fetch_plus_11s_timer": (
                "  const escape = window['fe' + 'tch']; "
                "window.setTimeout(() => escape('/api/health'), 11_000);"
            ),
            "computed_descriptor": (
                "  const escape = Object['getOwn' + 'PropertyDescriptor'](window, 'fetch'); void escape;"
            ),
            "computed_popup_fetch": (
                "  const popup = window['op' + 'en']('about:blank'); "
                "const escape = popup?.['fe' + 'tch']; void escape;"
            ),
            "template_computed_fetch_alias": (
                "  const ltg10EscapePrefix = 'fe'; "
                "const ltg10EscapeName = `${ltg10EscapePrefix}tch`; "
                "const ltg10EscapeCarrier: Record<string, unknown> = {}; "
                "const escape = ltg10EscapeCarrier[ltg10EscapeName]; void escape;"
            ),
            "dynamic_receiver_alias": (
                "  const root = self; const nativeName = String(Date.now()); "
                "const escape = root[nativeName]; void escape;"
            ),
            "dynamic_computed_callee": (
                "  const methods: Record<string, () => void> = {}; "
                "const nativeName = String(Date.now()); methods[nativeName]();"
            ),
            "new_realm_content_window": (
                "  const frame = document.querySelector('iframe'); "
                "const escape = frame?.contentWindow; void escape;"
            ),
            "parent_frames_popup": "  const escape = parent.frames[0].open; void escape;",
            "let_receiver_detached_dynamic_callee": (
                "  let realm = window; const nativeName = String(Date.now()); "
                "const callee = realm[nativeName]; callee();"
            ),
            "let_popup_detached_dynamic_callee": (
                "  let realm = window.open('about:blank'); const nativeName = String(Date.now()); "
                "const callee = realm?.[nativeName]; callee?.();"
            ),
            "let_content_window_detached_dynamic_callee": (
                "  const frame = document.querySelector('iframe'); let realm = frame?.contentWindow; "
                "const nativeName = String(Date.now()); const callee = realm?.[nativeName]; callee?.();"
            ),
            "computed_service_worker_register": (
                "  const registry = navigator['service' + 'Worker']; "
                "registry['reg' + 'ister']('/late-sw.js');"
            ),
        }
        for name, injection in injections.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                project = Path(temp_dir) / "project"
                _copy_source_contract(project)
                component_path = project / "desktop/src/routes/CommandCenterHome.tsx"
                source = component_path.read_text(encoding="utf-8")
                component_path.write_text(
                    source.replace(
                        "export default function CommandCenterHome() {",
                        f"export default function CommandCenterHome() {{\n{injection}",
                        1,
                    ),
                    encoding="utf-8",
                )
                result, blocker = retirement._inspect_typescript_source(project)
                self.assertIsNone(result)
                self.assertEqual(blocker, "source_ast_contract_blocked")

    def test_ordinary_ast_keeps_safe_computed_data_access_green(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            _copy_source_contract(project)
            component_path = project / "desktop/src/routes/CommandCenterHome.tsx"
            source = component_path.read_text(encoding="utf-8")
            component_path.write_text(
                source.replace(
                    "export default function CommandCenterHome() {",
                    (
                        "export default function CommandCenterHome() {\n"
                        "  const safeRows: Record<string, string> = {}; "
                        "const safeKey = String(Date.now()); const safeValue = safeRows[safeKey]; void safeValue;"
                    ),
                    1,
                ),
                encoding="utf-8",
            )
            result, blocker = retirement._inspect_typescript_source(project)
        self.assertEqual(blocker, "")
        self.assertIsNotNone(result)

    def test_legacytools_alias_ordinary_reachability_and_normalization_alias_fail_ast(self):
        mutations = (
            lambda app, layout: layout.replace(
                '      { key: "home", label: "今日作战台" },',
                '      { key: "home", label: "今日作战台" },\n      { key: "legacy", label: "Legacy Alias" },',
                1,
            ),
            lambda app, layout: (
                app.replace(
                    'const ROUTE_STORAGE_KEY = "stock_ming_command_center_3_route";',
                    'const LegacyToolsAlias = LegacyTools;\nconst ROUTE_STORAGE_KEY = "stock_ming_command_center_3_route";',
                    1,
                ),
                layout,
            ),
            lambda app, layout: (
                app.replace(
                    'if (cleaned === "next-session-chart") return "next";',
                    'if (cleaned === "old-legacy") return "legacy";\n  if (cleaned === "next-session-chart") return "next";',
                    1,
                ),
                layout,
            ),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with tempfile.TemporaryDirectory() as temp_dir:
                    project = Path(temp_dir) / "project"
                    _copy_source_contract(project)
                    app_path = project / "desktop/src/App.tsx"
                    layout_path = project / "desktop/src/components/Layout.tsx"
                    app = app_path.read_text(encoding="utf-8")
                    layout = layout_path.read_text(encoding="utf-8")
                    changed = mutation(app, layout)
                    if isinstance(changed, tuple):
                        app, layout = changed
                    else:
                        layout = changed
                    app_path.write_text(app, encoding="utf-8")
                    layout_path.write_text(layout, encoding="utf-8")
                    result, blocker = retirement._inspect_typescript_source(project)
                self.assertIsNone(result)
                self.assertEqual(blocker, "source_ast_contract_blocked")

    def test_old_v1_event_schema_and_missing_state_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            trust, key_path, _state_path = retirement._trust_paths(root)
            trust.mkdir(parents=True, mode=0o700)
            trust.chmod(0o700)
            key_path.write_bytes(os.urandom(retirement.TRUST_KEY_BYTES))
            key_path.chmod(0o600)
            events = retirement._event_root(root)
            events.mkdir(parents=True, mode=0o700)
            events.chmod(0o700)
            event = events / "00000001.json"
            event.write_text(json.dumps({"schema_version": "streamlit_retirement_packaged_attestation_event.v1"}), encoding="utf-8")
            event.chmod(0o600)
            result = retirement.validate_streamlit_primary_retirement(
                root,
                expected_head_full=HEAD,
                tauri_package_verification=_package(),
                project_root=ROOT,
            )

        self.assertFalse(result["streamlit_primary_retired"])
        self.assertIn("trusted_runner_event_schema_invalid", result["blockers"])

    def test_v1_fact_remains_false_without_real_packaged_runner_attestation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            root.mkdir()
            (root / "caller.json").write_text(json.dumps({"streamlit_primary_retired": True}), encoding="utf-8")
            with patch.object(v1_closeout_service, "validate_tauri_production_package", return_value=_package()):
                evaluation = v1_closeout_service.build_v1_closeout_evaluation(
                    evidence_root=root,
                    expected_head_full=HEAD,
                )

        facts = {row["evidence_key"]: row["observed"] for row in evaluation["production_fact_rows"]}
        self.assertFalse(facts["streamlit_primary_retired"])
        self.assertFalse(evaluation["streamlit_primary_retirement_summary"]["streamlit_primary_retired"])


if __name__ == "__main__":
    unittest.main()
