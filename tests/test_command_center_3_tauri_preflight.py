from pathlib import Path
import subprocess
import unittest


SCRIPT = Path("scripts/check_tauri_env.sh")
LAUNCHER = Path("scripts/start_command_center_3.command")


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

    def test_command_center_3_launcher_is_local_one_click_and_safe(self):
        source = LAUNCHER.read_text(encoding="utf-8")

        self.assertTrue(LAUNCHER.exists())
        self.assertIn("Command Center 3.0 local launcher", source)
        self.assertIn(
            "P0: local one-click launcher starts/checks FastAPI and React/Vite before opening the page.",
            source,
        )
        self.assertIn(
            "Boundary: one-click startup only links local frontend/backend; it does not enable live_light/provider/model execution.",
            source,
        )
        self.assertIn("scripts/dev_server.sh", source)
        self.assertIn("npm run dev", source)
        self.assertIn("VITE_API_BASE_URL", source)
        self.assertIn("STOCK_MING_ALLOW_SYSTEM_PYTHON", source)
        self.assertIn("desktop/node_modules", source)
        self.assertIn(".stock_ming_3/logs", source)
        self.assertIn("FASTAPI_READY=0", source)
        self.assertIn("VITE_READY=0", source)
        self.assertIn("Command Center 3.0 启动未完成", source)
        self.assertIn("FastAPI log: ${FASTAPI_LOG}", source)
        self.assertIn("React/Vite log: ${VITE_LOG}", source)
        self.assertIn("本地入口不会在前后端未联通时自动打开页面", source)
        self.assertIn('exit 1', source)
        self.assertIn('open "$VITE_URL"', source)
        self.assertIn("no Tushare, DeepSeek, GitHub, or trading call", source)
        self.assertIn("does not enable live_light/provider/model execution", source)
        self.assertNotIn('wait_for_url "FastAPI" "${API_BASE%/}/health" 40 || true', source)
        self.assertNotIn('wait_for_url "React/Vite" "$VITE_URL" 40 || true', source)
        self.assertNotIn("TUSHARE_TOKEN", source)
        self.assertNotIn("DEEPSEEK_API_KEY", source)
        self.assertNotIn("GITHUB_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
