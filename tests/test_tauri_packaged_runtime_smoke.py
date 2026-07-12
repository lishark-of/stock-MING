import argparse
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tauri_packaged_runtime_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tauri_packaged_runtime_smoke", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TauriPackagedRuntimeSmokeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
