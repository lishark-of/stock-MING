from pathlib import Path
import os
import subprocess
import tempfile
import unittest

from server.services import desktop_service


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
            "P0: local one-click launcher starts/checks FastAPI, bootstrap status, desktop preflight cache, and React/Vite before opening the page.",
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
        self.assertIn('APP_URL="${COMMAND_CENTER_3_APP_URL:-${VITE_URL%/}/#home}"', source)
        self.assertIn("safe_display_open_url", source)
        self.assertIn('APP_URL_DISPLAY="$(safe_display_open_url "$APP_URL")"', source)
        self.assertIn("Open route: ${APP_URL_DISPLAY}", source)
        self.assertIn("simple local open routes like #home may be shown", source)
        self.assertIn("Open target: ordinary Command Center home route (#home)", source)
        self.assertIn("startup does not land on developer/audit details from localStorage", source)
        self.assertIn("FASTAPI_READY=0", source)
        self.assertIn("API_STATUS_READY=0", source)
        self.assertIn("DESKTOP_PREFLIGHT_READY=0", source)
        self.assertIn("VITE_READY=0", source)
        self.assertIn("command_center_health_ready", source)
        self.assertIn("wait_for_command_center_health", source)
        self.assertIn("bootstrap_status_ready", source)
        self.assertIn("wait_for_bootstrap_status", source)
        self.assertIn("desktop_preflight_cache_ready", source)
        self.assertIn("wait_for_desktop_preflight_cache", source)
        self.assertIn("vite_command_center_ready", source)
        self.assertIn("wait_for_vite_command_center", source)
        self.assertIn('data.get("service") != "stock-MING Command Center 3.0"', source)
        self.assertIn('data.get("external_calls_on_startup") is not False', source)
        self.assertIn("command_center_3_bootstrap_runtime_mode_packet", source)
        self.assertIn("command_center_bootstrap_runtime_mode.v1", source)
        self.assertIn("command_center_3_desktop_shell_preflight_cache", source)
        self.assertIn("desktop_shell_preflight_cache.v1", source)
        self.assertIn('launcher.get("status") != "local_one_click_launcher_ready"', source)
        self.assertIn("stock-MING Command Center 3.0", source)
        self.assertIn("/src/main.tsx", source)
        self.assertIn("Health check: /health must return stock-MING Command Center 3.0 JSON", source)
        self.assertIn("Desktop preflight check: /api/desktop/preflight-cache must return command_center_3_desktop_shell_preflight_cache JSON", source)
        self.assertIn("Vite must serve stock-MING Command Center 3.0 index HTML", source)
        self.assertIn("COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY", source)
        self.assertIn("Check only: ${LAUNCHER_CHECK_ONLY}", source)
        self.assertIn("Check-only mode: resolved launcher configuration without starting FastAPI", source)
        self.assertIn("probing URLs, writing logs, opening a browser, creating tasks", source)
        self.assertIn("unset COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY and rerun this launcher", source)
        self.assertIn("wait for all four readiness checks", source)
        self.assertLess(
            source.index('if [ "$LAUNCHER_CHECK_ONLY" = "1" ]; then'),
            source.index('mkdir -p "$LOG_DIR"'),
        )
        self.assertIn("COMMAND_CENTER_3_LAUNCHER_SKIP_OPEN", source)
        self.assertIn("Browser open:", source)
        self.assertIn('if [ "$LAUNCHER_SKIP_OPEN" = "1" ]; then', source)
        self.assertIn("skip-open 已启用，请手动打开普通首页 ${APP_URL_DISPLAY}", source)
        self.assertIn("Skip-open mode: FastAPI, bootstrap status, desktop preflight cache, and React/Vite are ready", source)
        self.assertIn("browser was not opened automatically", source)
        self.assertIn('wait_for_command_center_health "FastAPI" "${API_BASE%/}/health" 40', source)
        self.assertIn('wait_for_bootstrap_status "${API_BASE%/}/api/bootstrap/status" 40', source)
        self.assertIn('wait_for_desktop_preflight_cache "${API_BASE%/}/api/desktop/preflight-cache" 40', source)
        self.assertIn('wait_for_vite_command_center "$VITE_URL" 40', source)
        self.assertIn("FastAPI port has a response, but it is not Command Center 3.0 health JSON", source)
        self.assertIn("React/Vite port has a response, but it is not the Command Center 3.0 frontend", source)
        self.assertIn("Command Center 3.0 启动未完成", source)
        self.assertIn("API status ready=${API_STATUS_READY}", source)
        self.assertIn("desktop preflight ready=${DESKTOP_PREFLIGHT_READY}", source)
        self.assertIn("FastAPI log: ${FASTAPI_LOG}", source)
        self.assertIn("React/Vite log: ${VITE_LOG}", source)
        self.assertIn("print_post_startup_readback_checklist", source)
        self.assertIn("启动后复核清单", source)
        self.assertIn("FastAPI health：${API_HEALTH_DISPLAY} 已返回 Command Center 3.0 JSON", source)
        self.assertIn("Bootstrap status：${BOOTSTRAP_STATUS_DISPLAY} 已返回 runtime-mode packet", source)
        self.assertIn("Desktop preflight cache：${DESKTOP_PREFLIGHT_DISPLAY} 已返回一键启动 packet", source)
        self.assertIn("React/Vite 前端：${VITE_URL_DISPLAY} 已返回 Command Center 3.0 HTML；页面会打开普通首页 ${APP_URL_DISPLAY}", source)
        self.assertIn("联通后下一步：打开下一票雷达（#candidates），输入股票代码", source)
        self.assertIn("只有确认按钮会创建 Tushare-first POST task", source)
        self.assertIn("DeepSeek 仍保持 governed/pending", source)
        self.assertIn("启动后复核只读本地 GET 结果；不创建 task", source)
        self.assertIn("可操作诊断", source)
        self.assertIn("FastAPI：${API_HEALTH_DISPLAY} 未返回 Command Center 3.0 健康 JSON", source)
        self.assertIn("Bootstrap status：${BOOTSTRAP_STATUS_DISPLAY} 未返回 runtime-mode packet", source)
        self.assertIn("Desktop preflight cache：${DESKTOP_PREFLIGHT_DISPLAY} 未返回一键启动 packet", source)
        self.assertIn("React/Vite：${VITE_URL_DISPLAY} 未返回 Command Center 3.0 前端 HTML", source)
        self.assertIn("下一步：先关闭占用 8710/5173 的本地进程", source)
        self.assertIn("本地入口不会在前后端未联通或 Vite 端口不是 Command Center 3.0 页面时自动打开页面", source)
        self.assertIn('exit 1', source)
        self.assertIn('open "$APP_URL"', source)
        self.assertIn("请在浏览器打开：${APP_URL_DISPLAY}", source)
        self.assertNotIn('open "$VITE_URL"', source)
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

    def test_command_center_3_launcher_check_only_does_not_start_or_open(self):
        env = {
            **os.environ,
            "COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY": "1",
            "COMMAND_CENTER_3_LAUNCHER_SKIP_OPEN": "1",
        }
        result = subprocess.run(
            ["bash", str(LAUNCHER)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        output = result.stdout

        self.assertIn("Command Center 3.0 local launcher", output)
        self.assertIn("Check only: 1", output)
        self.assertIn("Browser open: skipped", output)
        self.assertIn("Check-only mode: resolved launcher configuration without starting FastAPI", output)
        self.assertIn("starting React/Vite", output)
        self.assertIn("probing URLs", output)
        self.assertIn("opening a browser", output)
        self.assertIn("creating tasks", output)
        self.assertIn("calling providers/models", output)
        self.assertIn("health=http://127.0.0.1:8710/health", output)
        self.assertIn("bootstrap=http://127.0.0.1:8710/api/bootstrap/status", output)
        self.assertIn("desktop_preflight=http://127.0.0.1:8710/api/desktop/preflight-cache", output)
        self.assertIn("frontend=http://127.0.0.1:5173", output)
        self.assertIn("open_route=http://127.0.0.1:5173/#home", output)
        self.assertIn("unset COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY and rerun this launcher", output)
        self.assertIn("wait for all four readiness checks", output)
        self.assertNotIn("Starting FastAPI...", output)
        self.assertNotIn("Starting React/Vite...", output)
        self.assertNotIn("Command Center 3.0 入口已启动", output)

    def test_command_center_3_launcher_check_only_redacts_open_url_query(self):
        env = {
            **os.environ,
            "COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY": "1",
            "COMMAND_CENTER_3_LAUNCHER_SKIP_OPEN": "1",
            "COMMAND_CENTER_3_APP_URL": "http://127.0.0.1:5173/?raw_payload=SHOULD_NOT_SHOW#home",
        }
        result = subprocess.run(
            ["bash", str(LAUNCHER)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        output = result.stdout

        self.assertIn("Open route: http://127.0.0.1:5173/#home", output)
        self.assertIn("open_route=http://127.0.0.1:5173/#home", output)
        self.assertNotIn("SHOULD_NOT_SHOW", output)
        self.assertNotIn("raw_payload", output)

    def test_command_center_3_shortcut_installer_is_safe_and_verifiable(self):
        source = Path("scripts/install_command_center_3_desktop_shortcut.sh").read_text(encoding="utf-8")

        self.assertIn("Install safety: existing non-symlink target will not be overwritten.", source)
        self.assertIn("desktop target already exists and is not a symlink", source)
        self.assertIn("STOCK_MING_DESKTOP_SHORTCUT_NAME", source)
        self.assertIn("Boundary: installer stopped before changing files", source)
        self.assertIn("Install verification: shortcut symlink points to the local launcher.", source)
        self.assertIn("Double-click checklist: launcher checks FastAPI /health, bootstrap status, desktop preflight cache, and React/Vite before opening the page.", source)
        self.assertIn("shortcut install does not start FastAPI/Vite, create tasks, enable live_light, or execute trading", source)
        self.assertNotIn("npm run dev", source)
        self.assertNotIn("scripts/dev_server.sh", source)
        self.assertNotIn("open \"$VITE_URL\"", source)
        self.assertNotIn("TUSHARE_TOKEN", source)
        self.assertNotIn("DEEPSEEK_API_KEY", source)

    def test_command_center_3_shortcut_installer_runs_in_temp_desktop_only(self):
        launcher = Path("scripts/start_command_center_3.command").resolve()
        with tempfile.TemporaryDirectory() as temp_desktop:
            env = {**os.environ, "STOCK_MING_DESKTOP_DIR": temp_desktop}
            result = subprocess.run(
                ["bash", "scripts/install_command_center_3_desktop_shortcut.sh"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )
            target = Path(temp_desktop) / "stock-MING Command Center 3.command"

            self.assertTrue(target.is_symlink())
            self.assertEqual(Path(os.readlink(target)), launcher)
            self.assertIn("Command Center 3.0 desktop shortcut installed.", result.stdout)
            self.assertIn("Install verification: shortcut symlink points to the local launcher.", result.stdout)
            self.assertIn("Double-click checklist: launcher checks FastAPI /health, bootstrap status, desktop preflight cache, and React/Vite before opening the page.", result.stdout)
            self.assertIn("Boundary: shortcut install does not start FastAPI/Vite", result.stdout)

    def test_command_center_3_shortcut_installer_does_not_overwrite_regular_file(self):
        with tempfile.TemporaryDirectory() as temp_desktop:
            target = Path(temp_desktop) / "stock-MING Command Center 3.command"
            target.write_text("keep me", encoding="utf-8")
            env = {**os.environ, "STOCK_MING_DESKTOP_DIR": temp_desktop}
            result = subprocess.run(
                ["bash", "scripts/install_command_center_3_desktop_shortcut.sh"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(target.is_symlink())
            self.assertEqual(target.read_text(encoding="utf-8"), "keep me")
            self.assertIn("desktop target already exists and is not a symlink", result.stdout)
            self.assertIn("Boundary: installer stopped before changing files", result.stdout)

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
                    self.assertIn("FastAPI：${API_HEALTH_DISPLAY} 未返回 Command Center 3.0 健康 JSON", source)
                    self.assertIn("Bootstrap status：${BOOTSTRAP_STATUS_DISPLAY} 未返回 runtime-mode packet", source)
                    self.assertIn("Desktop preflight cache：${DESKTOP_PREFLIGHT_DISPLAY} 未返回一键启动 packet", source)
                    self.assertIn("React/Vite：${VITE_URL_DISPLAY} 未返回 Command Center 3.0 前端 HTML", source)
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

    def test_p0_post_startup_readback_checklist_is_visible_and_read_only(self):
        launcher = LAUNCHER.read_text(encoding="utf-8")
        page = DESKTOP_PREFLIGHT_PAGE.read_text(encoding="utf-8")
        health = HEALTH_PAGE.read_text(encoding="utf-8")
        home = HOME_PAGE.read_text(encoding="utf-8")

        self.assertIn("启动后复核清单", launcher)
        self.assertIn("Desktop preflight cache：${DESKTOP_PREFLIGHT_DISPLAY} 已返回一键启动 packet", launcher)
        self.assertIn("启动后复核清单", page)
        self.assertIn("p0StartupReadyMetrics", page)
        self.assertIn('aria-label="p0 ordinary one click readiness"', page)
        self.assertIn("一键启动就绪", page)
        self.assertIn('label: "启动入口"', page)
        self.assertIn('label: "后端状态"', page)
        self.assertIn('label: "前端页面"', page)
        self.assertIn('label: "打开策略"', page)
        self.assertIn('label: "普通下一步"', page)
        self.assertIn('aria-label="p0 ordinary primary action"', page)
        self.assertIn("去下一票雷达确认代码", page)
        self.assertIn("留在一键启动预检排障", page)
        self.assertIn("只切换到下一票雷达；输入代码不外联，点击确认才创建 Tushare-first POST task", page)
        self.assertIn("React render 不启动 FastAPI/Vite、不创建 task、不调用 provider/model", page)
        self.assertIn("当前联通：", page)
        self.assertIn("需要处理：", page)
        self.assertIn("本页只回读本地状态，不主动探测当前运行时", page)
        self.assertIn("p0PostStartupReadbackRows", page)
        self.assertIn("p0_post_startup_readback_rows", page)
        self.assertIn("p0ToP1OrdinaryHandoffRows", page)
        self.assertIn("p0_to_p1_ordinary_handoff_rows", page)
        self.assertIn("p0OrdinaryConnectionRows", page)
        self.assertIn("p0_ordinary_connection_rows", page)
        self.assertIn("p0FailureDiagnosticRows", page)
        self.assertIn("p0_failure_diagnostic_rows", page)
        self.assertIn('aria-label="p0 ordinary frontend backend connection checklist"', page)
        self.assertIn("前后端联通状态", page)
        self.assertIn("普通用户先看 FastAPI、Bootstrap status、Desktop preflight cache、React/Vite 四段是否 ready", page)
        self.assertIn("工程行表仍在开发 / 审计详情", page)
        self.assertIn('环节: "FastAPI"', page)
        self.assertIn('环节: "Bootstrap status"', page)
        self.assertIn('环节: "React/Vite"', page)
        self.assertIn("预检页只读 GET cache，不启动 FastAPI、不创建 task", page)
        self.assertIn('aria-label="p0 ordinary startup failure diagnostics"', page)
        self.assertIn("启动失败定位", page)
        self.assertIn("如果页面没有自动打开，按失败段看对应日志和端口", page)
        self.assertIn("这张表只读本地 cache，不补跑启动器、不创建 task", page)
        self.assertIn('失败段: "FastAPI /health"', page)
        self.assertIn('失败段: "Bootstrap status"', page)
        self.assertIn('失败段: "React/Vite HTML"', page)
        self.assertIn('失败段: "端口和日志指引"', page)
        self.assertIn(".stock_ming_3/logs/command_center_3_fastapi.log / 8710", page)
        self.assertIn(".stock_ming_3/logs/command_center_3_vite.log / 5173", page)
        self.assertIn("不启动服务、不创建 POST task、不外联", page)
        self.assertIn('aria-label="p0 post startup readback checklist"', page)
        self.assertIn("这张清单与启动器成功日志对齐", page)
        self.assertIn("页面只回读本地 GET 结果，不补跑启动器、不创建 task", page)
        self.assertIn('复核项: "FastAPI health"', page)
        self.assertIn('复核项: "Bootstrap status"', page)
        self.assertIn('复核项: "React/Vite 前端"', page)
        self.assertIn("GET /health 返回 Command Center 3.0 JSON，且 external_calls_on_startup=false", page)
        self.assertIn("GET /api/bootstrap/status 返回 runtime-mode packet", page)
        self.assertIn("Vite 返回 Command Center 3.0 HTML", page)
        self.assertIn("只读健康检查，不启动服务、不创建 task", page)
        self.assertIn("只读运行模式，不写配置、不启用 live_light", page)
        self.assertIn("只读前端入口，不调用 Tushare/DeepSeek/GitHub、不执行真实交易", page)
        self.assertIn('aria-label="p0 to p1 ordinary handoff"', page)
        self.assertIn("联通后搜票路径", page)
        self.assertIn("真正的 Tushare-first 工作仍要到下一票雷达点击确认按钮", page)
        self.assertIn("确认按钮才是 P1 工作入口", page)
        self.assertIn("结果来自 cache / ledger / packet", page)
        self.assertIn("p0PostStartupReadbackRows", health)
        self.assertIn("p0_post_startup_readback_rows", health)
        self.assertIn("p0ToP1OrdinaryHandoffRows", health)
        self.assertIn("p0_to_p1_ordinary_handoff_rows", health)
        self.assertIn("p0FailureDiagnosticRows", health)
        self.assertIn("p0_failure_diagnostic_rows", health)
        self.assertIn('aria-label="health p0 post startup readback checklist"', health)
        self.assertIn('aria-label="health p0 to p1 ordinary handoff"', health)
        self.assertIn('aria-label="health p0 startup recovery steps"', health)
        self.assertIn('aria-label="health p0 startup failure diagnostics"', health)
        self.assertIn("如果一键入口没有打开页面，按失败段看对应日志和端口", health)
        self.assertIn("健康页只读展示，不补跑启动器、不创建 task", health)
        self.assertIn("这张表来自 desktop preflight 的 p0_recovery_steps", health)
        self.assertIn("系统健康页只回读本地 GET 结果，不补跑启动器、不创建 task", health)
        self.assertIn("真正的 Tushare-first 工作仍要到下一票雷达点击确认按钮", health)
        self.assertIn("健康页只读展示恢复动作，不补跑启动器、不创建 task", health)
        self.assertIn("dailyCommandP0RecoveryRows", home)
        self.assertIn("p0_recovery_steps", home)
        self.assertIn('aria-label="daily command p0 startup recovery steps"', home)
        self.assertIn("一键启动恢复步骤", home)
        self.assertIn("页面没打开或联通异常时，先按三步恢复", home)
        self.assertIn("这张表只读展示，不补跑启动器", home)
        self.assertIn("首页不启动 FastAPI/Vite、不创建 task、不调用 provider/model", home)
        self.assertLess(health.index("启动后复核清单"), health.index("联通后搜票路径"))
        self.assertLess(health.index("联通后搜票路径"), health.index("一键启动恢复步骤"))
        self.assertLess(home.index("P0 到 P1 快速行动"), home.index("一键启动恢复步骤"))
        self.assertLess(home.index("一键启动恢复步骤"), home.index("<summary>开发 / 审计详情</summary>"))
        self.assertLess(page.index("前后端联通状态"), page.index("<summary>开发 / 审计详情</summary>"))
        self.assertLess(page.index("启动失败定位"), page.index("<summary>开发 / 审计详情</summary>"))
        self.assertLess(page.index("一键启动就绪"), page.index("<summary>开发 / 审计详情</summary>"))
        self.assertLess(page.index("启动后复核清单"), page.index("<summary>开发 / 审计详情</summary>"))
        self.assertLess(page.index("联通后搜票路径"), page.index("<summary>开发 / 审计详情</summary>"))
        self.assertLess(page.index("<summary>开发 / 审计详情</summary>"), page.index("DeepSeek governed executor required before real call"))
        self.assertLess(page.index("<summary>开发 / 审计详情</summary>"), page.index("frontend_backend_connection_ready / blocker_count"))
        self.assertLess(page.index("启动后复核清单"), page.index("开发 / 审计详情：P0 联通明细"))
        self.assertNotIn("postBootstrapLiveStartup", page)
        self.assertNotIn("postBootstrapLiveStartup", health)
        home_summary = home[
            home.index('title="今日作战台摘要"') : home.index("<summary>开发 / 审计详情</summary>")
        ]
        self.assertNotIn("postBootstrapLiveStartup", home_summary)

    def test_p0_quick_action_handoff_requires_confirm_button(self):
        packet = desktop_service.read_desktop_shell_preflight_cache()
        handoff_rows = packet["p0_to_p1_ordinary_handoff_rows"]
        quick_rows = packet["p0_ordinary_quick_action_rows"]

        self.assertEqual(len(handoff_rows), 4)
        self.assertEqual(len(quick_rows), 4)
        self.assertTrue(packet["policy"]["p0_to_p1_ordinary_handoff_rows_are_cache_only"])
        self.assertTrue(packet["policy"]["p0_ordinary_quick_action_rows_are_cache_only"])
        self.assertTrue(packet["policy"]["p0_to_p1_ordinary_handoff_rows_do_not_create_task"])
        self.assertTrue(packet["policy"]["p0_ordinary_quick_action_rows_do_not_create_task"])

        for row in handoff_rows + quick_rows:
            self.assertEqual(row["frontend_backend_auto_link_scope"], "local_fastapi_only")
            self.assertIn("四段 ready 后只切换到 #candidates", row["P0交接证据"])
            self.assertIn("输入股票代码保持静默", row["P0交接证据"])
            self.assertIn("确认按钮才创建 Tushare-first POST task", row["P0交接证据"])
            self.assertIn("FastAPI health + bootstrap status", row["成功信号"])
            self.assertFalse(row["page_open_creates_task"])
            self.assertFalse(row["react_render_creates_task"])
            self.assertFalse(row["get_cache_creates_task"])
            self.assertFalse(row["search_input_external_calls"])
            self.assertTrue(row["confirm_button_required_for_tushare_task"])
            self.assertFalse(row["live_light_or_deepseek_enabled_by_p0"])
            self.assertFalse(row["external_calls_triggered"])
            self.assertFalse(row["tushare_called"])
            self.assertFalse(row["deepseek_called"])
            self.assertFalse(row["github_called"])
            self.assertFalse(row["loads_token_or_key"])
            self.assertFalse(row["strict_closeout_evidence"])
            self.assertFalse(row["release_ready_evidence"])
            self.assertTrue(row["does_not_execute_trades"])
            self.assertTrue(row["does_not_modify_strategy_action"])


if __name__ == "__main__":
    unittest.main()
