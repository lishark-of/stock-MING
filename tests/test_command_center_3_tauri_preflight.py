from pathlib import Path
import subprocess
import unittest


SCRIPT = Path("scripts/check_tauri_env.sh")


class CommandCenter3TauriPreflightTests(unittest.TestCase):
    def test_preflight_script_is_read_only_and_documents_safety(self):
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertTrue(SCRIPT.exists())
        self.assertIn("Command Center 3.0 Tauri preflight", source)
        self.assertIn("rustc", source)
        self.assertIn("cargo", source)
        self.assertIn("cargo_lock", source)
        self.assertIn("tauri_icon", source)
        self.assertIn("VITE_API_BASE_URL", source)
        self.assertIn("fastapi_dev_command=scripts/dev_server.sh", source)
        self.assertIn("tauri_dev_command=cd desktop && npm run tauri dev", source)
        self.assertIn("tauri_build_command=cd desktop && npm run tauri build", source)
        self.assertIn("backend_autostart=false", source)
        self.assertIn("fastapi_sidecar_autostart=false", source)
        self.assertIn("production_package_build_attempted=false", source)
        self.assertIn("tauri_build_artifact_status=", source)
        self.assertIn("tauri_build_artifact_path=desktop/src-tauri/target/release/stock_ming_command_center", source)
        self.assertIn("token_bundle_policy=frontend_never_stores_tokens", source)
        self.assertIn("external_calls_triggered=false", source)
        self.assertIn("secrets_loaded=false", source)
        self.assertIn("real_trading_triggered=false", source)
        self.assertIn("frontend_uses_fastapi_only=true", source)
        self.assertIn("tauri_package_build_required_for_production=true", source)
        self.assertNotIn("npm install", source)
        self.assertNotIn("npm run tauri dev >/dev/null", source)
        self.assertNotIn("cargo build", source)

    def test_preflight_script_runs_without_requiring_rust(self):
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout

        self.assertIn("Command Center 3.0 Tauri preflight", output)
        self.assertIn("tauri_dev_ready=", output)
        self.assertIn("cargo_lock=", output)
        self.assertIn("tauri_icon=", output)
        self.assertIn("fastapi_dev_command=scripts/dev_server.sh", output)
        self.assertIn("tauri_build_command=cd desktop && npm run tauri build", output)
        self.assertIn("backend_autostart=false", output)
        self.assertIn("fastapi_sidecar_autostart=false", output)
        self.assertIn("production_package_build_attempted=false", output)
        self.assertIn("tauri_build_artifact_status=", output)
        self.assertIn("tauri_build_artifact_path=desktop/src-tauri/target/release/stock_ming_command_center", output)
        self.assertIn("token_bundle_policy=frontend_never_stores_tokens", output)
        self.assertIn("external_calls_triggered=false", output)
        self.assertIn("secrets_loaded=false", output)
        self.assertIn("real_trading_triggered=false", output)
        self.assertIn("frontend_uses_fastapi_only=true", output)
        self.assertIn("tauri_package_build_required_for_production=true", output)


if __name__ == "__main__":
    unittest.main()
