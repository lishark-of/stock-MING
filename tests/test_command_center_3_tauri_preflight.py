from pathlib import Path
import subprocess
import unittest


SCRIPT = Path("scripts/check_tauri_env.sh")
LAUNCHER = Path("scripts/start_command_center_3.command")
DESKTOP_PREFLIGHT_PAGE = Path("desktop/src/routes/DesktopShellPreflight.tsx")
HEALTH_PAGE = Path("desktop/src/routes/HealthStatus.tsx")
HOME_PAGE = Path("desktop/src/routes/CommandCenterHome.tsx")


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
        self.assertIn("API_STATUS_READY=0", source)
        self.assertIn("VITE_READY=0", source)
        self.assertIn("command_center_health_ready", source)
        self.assertIn("wait_for_command_center_health", source)
        self.assertIn("bootstrap_status_ready", source)
        self.assertIn("wait_for_bootstrap_status", source)
        self.assertIn("vite_command_center_ready", source)
        self.assertIn("wait_for_vite_command_center", source)
        self.assertIn('data.get("service") != "stock-MING Command Center 3.0"', source)
        self.assertIn('data.get("external_calls_on_startup") is not False', source)
        self.assertIn("command_center_3_bootstrap_runtime_mode_packet", source)
        self.assertIn("command_center_bootstrap_runtime_mode.v1", source)
        self.assertIn("stock-MING Command Center 3.0", source)
        self.assertIn("/src/main.tsx", source)
        self.assertIn("Health check: /health must return stock-MING Command Center 3.0 JSON", source)
        self.assertIn("Vite must serve stock-MING Command Center 3.0 index HTML", source)
        self.assertIn('wait_for_command_center_health "FastAPI" "${API_BASE%/}/health" 40', source)
        self.assertIn('wait_for_bootstrap_status "${API_BASE%/}/api/bootstrap/status" 40', source)
        self.assertIn('wait_for_vite_command_center "$VITE_URL" 40', source)
        self.assertIn("FastAPI port has a response, but it is not Command Center 3.0 health JSON", source)
        self.assertIn("React/Vite port has a response, but it is not the Command Center 3.0 frontend", source)
        self.assertIn("Command Center 3.0 启动未完成", source)
        self.assertIn("API status ready=${API_STATUS_READY}", source)
        self.assertIn("FastAPI log: ${FASTAPI_LOG}", source)
        self.assertIn("React/Vite log: ${VITE_LOG}", source)
        self.assertIn("可操作诊断", source)
        self.assertIn("FastAPI：${API_BASE%/}/health 未返回 Command Center 3.0 健康 JSON", source)
        self.assertIn("Bootstrap status：${API_BASE%/}/api/bootstrap/status 未返回 runtime-mode packet", source)
        self.assertIn("React/Vite：${VITE_URL} 未返回 Command Center 3.0 前端 HTML", source)
        self.assertIn("下一步：先关闭占用 8710/5173 的本地进程", source)
        self.assertIn("本地入口不会在前后端未联通或 Vite 端口不是 Command Center 3.0 页面时自动打开页面", source)
        self.assertIn('exit 1', source)
        self.assertIn('open "$VITE_URL"', source)
        self.assertIn("no Tushare, DeepSeek, GitHub, or trading call", source)
        self.assertIn("does not enable live_light/provider/model execution", source)
        self.assertNotIn('wait_for_url "FastAPI" "${API_BASE%/}/health" 40 || true', source)
        self.assertNotIn('wait_for_url "FastAPI status API" "${API_BASE%/}/api/bootstrap/status" 40 || true', source)
        self.assertNotIn('wait_for_url "React/Vite" "$VITE_URL" 40 || true', source)
        self.assertNotIn('wait_for_url "FastAPI" "${API_BASE%/}/health" 40', source)
        self.assertNotIn('wait_for_url "React/Vite" "$VITE_URL" 40', source)
        self.assertNotIn("TUSHARE_TOKEN", source)
        self.assertNotIn("DEEPSEEK_API_KEY", source)
        self.assertNotIn("GITHUB_TOKEN", source)

    def test_p0_startup_diagnostics_are_consistent_across_launcher_and_ordinary_pages(self):
        sources = {
            "launcher": LAUNCHER.read_text(encoding="utf-8"),
            "desktop_preflight": DESKTOP_PREFLIGHT_PAGE.read_text(encoding="utf-8"),
            "health": HEALTH_PAGE.read_text(encoding="utf-8"),
            "daily_command": HOME_PAGE.read_text(encoding="utf-8"),
        }
        shared_diagnostics = [
            "FastAPI /health Command Center 3.0 JSON",
            "bootstrap status runtime-mode packet",
            "React/Vite Command Center 3.0 HTML",
            "8710/5173 port occupancy guidance",
        ]

        for surface, source in sources.items():
            with self.subTest(surface=surface):
                if surface == "launcher":
                    self.assertIn("FastAPI：${API_BASE%/}/health 未返回 Command Center 3.0 健康 JSON", source)
                    self.assertIn("Bootstrap status：${API_BASE%/}/api/bootstrap/status 未返回 runtime-mode packet", source)
                    self.assertIn("React/Vite：${VITE_URL} 未返回 Command Center 3.0 前端 HTML", source)
                    self.assertIn("下一步：先关闭占用 8710/5173 的本地进程", source)
                    self.assertIn("external_calls_on_startup", source)
                else:
                    for diagnostic in shared_diagnostics:
                        self.assertIn(diagnostic, source)
                    self.assertIn("diagnostic_surfaces", source)
                    self.assertIn("success_condition", source)
                    self.assertIn("blocked_next_action", source)
                    self.assertIn("GET", source)
                    if surface == "daily_command":
                        summary_start = source.index('title="今日作战台摘要"')
                        summary_end = source.index("<summary>开发 / 审计详情</summary>", summary_start)
                        ordinary_summary = source[summary_start:summary_end]
                        self.assertNotIn("postBootstrapLiveStartup", ordinary_summary)
                        self.assertNotIn("launchLiveBootstrap", ordinary_summary)
                    else:
                        self.assertNotIn("postBootstrapLiveStartup", source)

                self.assertNotIn("TUSHARE_TOKEN", source)
                self.assertNotIn("DEEPSEEK_API_KEY", source)
                self.assertNotIn("GITHUB_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
