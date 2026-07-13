import argparse
import importlib.util
import os
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tauri_packaged_runtime_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tauri_packaged_runtime_smoke", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TauriPackagedRuntimeSmokeTests(unittest.TestCase):
    @staticmethod
    def _write_app_bundle(
        app_path: Path,
        *,
        version: str = "3.0.0",
        executable_bytes: bytes = b"binary",
    ) -> Path:
        executable = app_path / "Contents/MacOS/stock_ming_command_center"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(executable_bytes)
        executable.chmod(0o755)
        info_plist = {
            "CFBundleIdentifier": "com.stockming.commandcenter",
            "CFBundleShortVersionString": version,
            "CFBundleVersion": version,
            "CFBundleExecutable": executable.name,
        }
        with (app_path / "Contents/Info.plist").open("wb") as handle:
            plistlib.dump(info_plist, handle)
        return executable

    def test_python_executable_path_preserves_virtualenv_symlink(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base_python = root / "python3.12"
            base_python.write_text("", encoding="utf-8")
            venv_python = root / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True)
            venv_python.symlink_to(base_python)

            selected = module._python_executable_path(str(venv_python))

        self.assertEqual(selected, os.path.abspath(str(venv_python)))
        self.assertNotEqual(selected, str(base_python.resolve()))

    def test_api_base_is_strictly_local_8710(self) -> None:
        module = _load_module()
        self.assertEqual(module._local_api_base("http://127.0.0.1:8710"), "http://127.0.0.1:8710")
        self.assertEqual(module._local_api_base("http://localhost:8710/"), "http://localhost:8710")
        with self.assertRaises(ValueError):
            module._local_api_base("https://example.com:8710")
        self.assertEqual(module._local_api_base("http://127.0.0.1:8799"), "http://127.0.0.1:8799")
        with self.assertRaises(ValueError):
            module._local_api_base("http://127.0.0.1:80")

    def test_missing_app_fails_before_process_launch(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            args = argparse.Namespace(
                api_base="http://127.0.0.1:8710",
                app_path=str(Path(temp_dir) / "missing.app"),
                dmg_path=str(Path(temp_dir) / "missing.dmg"),
                python="/usr/bin/python3",
                observe_seconds=0.1,
                build=False,
                build_timeout=1,
                allow_backend_autostart=False,
                expect_backend_offline=False,
                offline_ui_observed=False,
                offline_screenshot_sha256="",
                record_reviews=False,
                write_evidence=False,
            )
            with self.assertRaisesRegex(FileNotFoundError, "packaged_app_executable_missing"):
                module.run_smoke(args)

    def test_runner_keeps_production_and_external_boundaries_explicit(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"production_package_complete": False', source)
        self.assertIn('"backend_offline_packaged_ux_verified": bool(offline_passed)', source)
        self.assertIn("args.offline_ui_observed", source)
        self.assertIn("screenshot_hash_safe", source)
        self.assertIn('"external_calls_triggered": False', source)
        self.assertIn('"does_not_execute_trades": True', source)
        self.assertIn("SECRET_PATTERNS", source)
        self.assertIn('"dmg_mounted_app_codesign_verified"', source)
        self.assertIn('"dmg_mount_readonly_observed"', source)
        self.assertIn('"app_bundle_sha256"', source)
        self.assertIn('"dmg_sha256"', source)
        self.assertIn('"bundle_version_matches_tauri_config"', source)
        self.assertIn('"safe_config_log_evidence"', source)
        self.assertIn('"local_packaged_runtime_evidence_ready": False', source)
        self.assertIn(".offline-backend-intentionally-unavailable", source)
        self.assertIn('"spctl_security_assessment_effective"', source)
        self.assertIn("run_tauri_signing_notarization_review_task", source)
        self.assertNotIn("shell=True", source)

    def test_codesign_parser_distinguishes_adhoc_hardened_runtime(self) -> None:
        module = _load_module()
        observation = module._parse_codesign_observation(
            "\n".join(
                (
                    "CodeDirectory v=20500 flags=0x10002(adhoc,runtime)",
                    "CDHash=2ac8afbd7efabc10de2ef5bd671c0b2044d33a52",
                    "Signature=adhoc",
                    "TeamIdentifier=not set",
                )
            )
        )

        self.assertEqual(observation["codesign_signature_type"], "adhoc")
        self.assertEqual(observation["codesign_flags_observed"], "0x10002(adhoc,runtime)")
        self.assertEqual(observation["codesign_team_identifier_status"], "not_set")
        self.assertFalse(observation["apple_developer_identity_used"])
        self.assertTrue(observation["codesign_cdhash_observed"])

    def test_codesign_parser_does_not_promote_non_developer_id_team(self) -> None:
        module = _load_module()
        observation = module._parse_codesign_observation(
            "\n".join(
                (
                    "CodeDirectory v=20500 flags=0x10000(runtime)",
                    "Signature size=4787",
                    "Authority=Apple Development: Local QA (TEAM123)",
                    "TeamIdentifier=TEAM123",
                    "CDHash=2ac8afbd7efabc10de2ef5bd671c0b2044d33a52",
                )
            )
        )

        self.assertEqual(observation["codesign_signature_type"], "apple_development")
        self.assertFalse(observation["apple_developer_identity_used"])

    def test_bundle_identity_and_fingerprint_bind_current_payload(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            app_path = Path(temp_dir) / "Command Center.app"
            executable = self._write_app_bundle(app_path, executable_bytes=b"first")

            identity = module._read_bundle_identity(app_path)
            first = module._bundle_fingerprint(app_path)
            executable.write_bytes(b"second")
            second = module._bundle_fingerprint(app_path)

        self.assertEqual(identity["bundle_id"], "com.stockming.commandcenter")
        self.assertEqual(identity["version"], "3.0.0")
        self.assertGreater(first["size_bytes"], 0)
        self.assertGreaterEqual(first["file_count"], 2)
        self.assertNotEqual(first["sha256"], second["sha256"])

    def test_dmg_mount_binds_readonly_identity_version_and_executable(self) -> None:
        module = _load_module()
        expected_bytes = b"packaged executable"
        expected_sha256 = module.hashlib.sha256(expected_bytes).hexdigest()
        mounted_path: list[Path] = []

        def fake_run(command, *, cwd=ROOT, timeout=120):
            if command[:2] == ["hdiutil", "attach"]:
                mountpoint = Path(command[command.index("-mountpoint") + 1])
                mounted_path.append(mountpoint)
                self._write_app_bundle(
                    mountpoint / "stock-MING Command Center.app",
                    executable_bytes=expected_bytes,
                )
                return subprocess.CompletedProcess(command, 0, "attached", "")
            if command == ["mount"]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    f"/dev/disk-test on {mounted_path[0]} (apfs, local, read-only)\n",
                    "",
                )
            if command and command[0] in {"codesign", "hdiutil"}:
                return subprocess.CompletedProcess(command, 0, "", "")
            raise AssertionError(command)

        with tempfile.TemporaryDirectory() as temp_dir:
            dmg_path = Path(temp_dir) / "release.dmg"
            dmg_path.write_bytes(b"dmg")
            with mock.patch.object(module, "_run", side_effect=fake_run):
                observation = module._dmg_mounted_app_observation(
                    dmg_path,
                    expected_bundle_id="com.stockming.commandcenter",
                    expected_version="3.0.0",
                    expected_executable_sha256=expected_sha256,
                )

        self.assertTrue(observation["dmg_attached_readonly"])
        self.assertTrue(observation["dmg_mount_readonly_observed"])
        self.assertTrue(observation["dmg_mounted_app_codesign_verified"])
        self.assertTrue(observation["dmg_mounted_bundle_id_matches"])
        self.assertTrue(observation["dmg_mounted_version_matches"])
        self.assertTrue(observation["dmg_mounted_executable_matches"])
        self.assertTrue(observation["dmg_detached"])

    def test_safe_output_redacts_absolute_user_and_temp_paths(self) -> None:
        module = _load_module()
        output = module._safe_output_text(
            f"{Path.home()}/private/app failed at {tempfile.gettempdir()}/mount"
        )

        self.assertNotIn(str(Path.home()), output)
        self.assertNotIn(tempfile.gettempdir(), output)
        self.assertIn("<home>", output)

    def test_spctl_parser_does_not_promote_security_disabled_override(self) -> None:
        module = _load_module()
        observation = module._parse_spctl_observation(
            0,
            "stock-MING Command Center.app: accepted\noverride=security disabled",
        )

        self.assertEqual(observation["spctl_assessment_status"], "unknown")
        self.assertFalse(observation["spctl_security_assessment_effective"])
        self.assertIn("override=security disabled", observation["spctl_message_safe"])

    def test_tauri_and_frontend_expose_default_off_isolated_qa_configuration(self) -> None:
        rust_source = (ROOT / "desktop/src-tauri/src/main.rs").read_text(encoding="utf-8")
        client_source = (ROOT / "desktop/src/api/client.ts").read_text(encoding="utf-8")

        self.assertIn("const FASTAPI_PORT: u16 = 8710", rust_source)
        self.assertIn('env::var("STOCK_MING_PYTHON")', rust_source)
        self.assertIn("external_calls_on_startup", rust_source)
        self.assertIn("provider_or_model_calls", rust_source)
        self.assertIn('const DEFAULT_LOCAL_API_BASE = "http://127.0.0.1:8710"', client_source)
        self.assertIn('const DEFAULT_LOCALHOST_API_BASE = "http://localhost:8710"', client_source)
        self.assertIn("const API_BASE_CANDIDATES = localApiBaseCandidates()", client_source)

    def test_service_signing_review_accepts_honest_other_identity_blocker(self) -> None:
        from server.services import desktop_service

        artifact = {
            "schema_version": "tauri_build_artifact_detection.v1",
            "packaged_app_bundle_detected": True,
            "bundle_app_count": 1,
            "bundle_app_path": "desktop/target/release/Command Center.app",
            "artifact_is_gitignored": True,
        }
        config_log_review = {
            "schema_version": "tauri_config_log_runtime_review.v1",
            "status": "tauri_config_log_runtime_review_ready",
            "config_log_runtime_paths_validated": True,
            "production_package_complete": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }

        review = desktop_service._tauri_signing_notarization_review_contract(
            tauri_build_artifact=artifact,
            config_log_review=config_log_review,
            explicit_review=True,
            explicit_codesign_inspection_completed=True,
            explicit_spctl_assessment_completed=True,
            app_bundle_path_observed=artifact["bundle_app_path"],
            codesign_signature_type="other_identity",
            codesign_flags_observed="0x10000(runtime)",
            codesign_team_identifier_status="set",
            codesign_cdhash_observed="a" * 40,
            spctl_assessment_status="rejected",
            distribution_dmg_detected=True,
        )

        self.assertEqual(review["status"], "tauri_signing_notarization_review_ready_blocked")
        self.assertTrue(review["local_signing_notarization_review_ready"])
        self.assertFalse(review["production_signing_notarization_ready"])
        self.assertFalse(review["production_package_complete"])


if __name__ == "__main__":
    unittest.main()
