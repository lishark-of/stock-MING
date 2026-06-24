import unittest
from pathlib import Path


class BackendOfflineNoticeGuidanceTests(unittest.TestCase):
    def test_backend_offline_notice_points_to_local_launcher_without_external_work(self):
        root = Path(__file__).resolve().parents[1]
        notice = (
            root / "desktop" / "src" / "components" / "BackendOfflineNotice.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("本地后端未连接", notice)
        self.assertIn('const COMMAND_CENTER_3_LAUNCHER_PATH = "scripts/start_command_center_3.command"', notice)
        self.assertIn('const COMMAND_CENTER_3_CHECK_ONLY_LAUNCHER_PATH = "scripts/check_command_center_3.command"', notice)
        self.assertIn('const COMMAND_CENTER_3_DESKTOP_SHORTCUT = "stock-MING Command Center 3.command"', notice)
        self.assertIn("COMMAND_CENTER_3_CHECK_ONLY_COMMAND", notice)
        self.assertIn("COMMAND_CENTER_3_CHECK_ONLY_COMMAND = COMMAND_CENTER_3_CHECK_ONLY_LAUNCHER_PATH", notice)
        self.assertNotIn("COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY=1 scripts/start_command_center_3.command", notice)
        self.assertIn("先安全自检：运行", notice)
        self.assertIn("{COMMAND_CENTER_3_CHECK_ONLY_COMMAND}", notice)
        self.assertIn("它只打印本机 API/Vite/open route", notice)
        self.assertIn("不启动 FastAPI/Vite、不探测 URL、不打开浏览器、不创建 task", notice)
        self.assertIn("下一步：请双击桌面快捷方式", notice)
        self.assertIn("{COMMAND_CENTER_3_DESKTOP_SHORTCUT}", notice)
        self.assertIn("{COMMAND_CENTER_3_LAUNCHER_PATH}", notice)
        self.assertIn("API_BASE_CANDIDATE_DISPLAY_URLS", notice)
        self.assertIn("CONFIGURED_API_BASE_DISPLAY_URL", notice)
        self.assertIn("前端已自动尝试本机 FastAPI 地址", notice)
        self.assertIn("配置地址显示为", notice)
        self.assertIn("启动器会等待 FastAPI 和页面都 ready 后才打开入口", notice)
        self.assertIn("先按这四步恢复本地联通", notice)
        self.assertIn("当前画面只显示离线保护状态", notice)
        self.assertIn("恢复联通后：先看系统健康是否变绿，再去下一票雷达输入代码", notice)
        self.assertIn("点击“确认并生成 3.0 量化推演”创建 Tushare-first 按钮门控任务", notice)
        self.assertIn("ordinaryRecoveryGateSteps", notice)
        self.assertIn("P0 恢复闸门", notice)
        self.assertIn('aria-label="backend offline p0 recovery gate checklist"', notice)
        self.assertIn("未 ready：停在离线保护，不直接进入雷达、量化推演或次日图谱", notice)
        self.assertIn("四段 ready：刷新本页或系统健康页，确认本地前后端已联通", notice)
        self.assertIn("输入代码只做本地校验，确认按钮才进入 P1 Tushare-first task", notice)
        self.assertIn("任务完成后再看 cache / ledger / packet；DeepSeek 仍等 governed executor", notice)
        self.assertIn("刚运行启动器后仍离线", notice)
        self.assertIn("旧的 React/Vite dev server 复用了不同后端地址", notice)
        self.assertIn("只想先自检入口配置时", notice)
        self.assertIn("check-only 安全自检", notice)
        self.assertIn("不会启动 FastAPI/Vite、不会打开浏览器、不会创建 task", notice)
        self.assertIn('aria-label="backend offline local recovery links"', notice)
        self.assertIn('href="#desktop"', notice)
        self.assertIn('href="#health"', notice)
        self.assertIn('href="#candidates"', notice)
        self.assertIn("联通变绿后去下一票雷达", notice)
        self.assertIn('aria-label="open candidate radar after backend recovery"', notice)
        self.assertIn('href="#recovery"', notice)
        self.assertIn("这些入口只切换本地页面", notice)
        self.assertIn("不会启动 FastAPI/Vite", notice)
        self.assertIn("不会创建 task", notice)
        self.assertIn(".stock_ming_3/logs/command_center_3_vite.log", notice)
        self.assertIn("连接地址：{apiBase}", notice)
        self.assertIn("不会调用 Tushare、DeepSeek 或 GitHub", notice)
        self.assertIn("不会执行真实交易，也不会修改 strategy action", notice)
        self.assertNotIn("fetch(", notice)
        self.assertNotIn("TUSHARE_TOKEN", notice)
        self.assertNotIn("DEEPSEEK_API_KEY", notice)
        self.assertNotIn("GITHUB_TOKEN", notice)

    def test_api_client_falls_back_only_to_local_fastapi_base(self):
        root = Path(__file__).resolve().parents[1]
        client = (root / "desktop" / "src" / "api" / "client.ts").read_text(encoding="utf-8")

        self.assertIn('const DEFAULT_LOCAL_API_BASE = "http://127.0.0.1:8710"', client)
        self.assertIn('const DEFAULT_LOCALHOST_API_BASE = "http://localhost:8710"', client)
        self.assertIn("function isLocalApiBase", client)
        self.assertIn('["127.0.0.1", "localhost", "::1", "[::1]"].includes(parsed.hostname)', client)
        self.assertIn("function localApiBaseCandidates", client)
        self.assertIn("const API_BASE_CANDIDATES = localApiBaseCandidates()", client)
        self.assertIn("sameApiBase(candidate, DEFAULT_LOCALHOST_API_BASE)", client)
        self.assertIn("for (const apiBase of API_BASE_CANDIDATES)", client)
        self.assertIn("fetch(`${apiBase}${path}`", client)
        self.assertIn("attempted_api_bases: attemptedApiBases", client)
        self.assertIn("default_localhost_api_base: safeApiBaseDisplay(DEFAULT_LOCALHOST_API_BASE)", client)
        self.assertIn("frontend_backend_auto_link_candidate_count: attemptedApiBases.length", client)
        self.assertIn("frontend_backend_auto_link_attempted: true", client)
        self.assertIn("frontend_backend_auto_link_success: false", client)
        self.assertIn("frontend_backend_auto_link_next_action", client)
        self.assertIn("frontend_backend_check_only_command", client)
        self.assertIn("frontend_backend_check_only_creates_task: false", client)
        self.assertIn("scripts/check_command_center_3.command", client)
        self.assertNotIn("COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY=1 scripts/start_command_center_3.command", client)
        self.assertIn('frontend_backend_auto_link_scope: "local_fastapi_only"', client)
        self.assertIn("page_render_external_calls: false", client)
        self.assertIn("provider_or_model_calls: false", client)
        self.assertIn("本地 FastAPI 后端暂未连接；已尝试本机地址", client)
        self.assertIn("stock-MING Command Center 3.command", client)
        self.assertNotIn("fetch(`${API_BASE}${path}`", client)

    def test_page_state_banner_hides_raw_backend_offline_error_from_ordinary_user(self):
        root = Path(__file__).resolve().parents[1]
        page_state = (
            root / "desktop" / "src" / "components" / "PageStateBanner.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn('import { useEffect, useState } from "react";', page_state)
        self.assertIn('import { BACKEND_OFFLINE_ERROR, getHealth } from "../api/client";', page_state)
        self.assertIn("const isBackendOffline = Boolean(error?.includes(BACKEND_OFFLINE_ERROR))", page_state)
        self.assertIn("本地后端未连接；请按上方步骤使用本地启动器恢复连接。", page_state)
        self.assertIn("const BACKEND_RECONNECT_POLL_MS = 3000", page_state)
        self.assertIn("const BACKEND_RECONNECT_MAX_ATTEMPTS = 20", page_state)
        self.assertIn("command_center_3_backend_reconnect_once", page_state)
        self.assertIn("void getHealth()", page_state)
        self.assertIn('String(res.data?.status ?? "") === "ok"', page_state)
        self.assertIn("window.location.reload()", page_state)
        self.assertIn('data-backend-reconnect-status={reconnectStatus}', page_state)
        self.assertIn("每 3 秒只读检查本机 FastAPI /health", page_state)
        self.assertIn("external_calls_triggered=false，不创建 task", page_state)
        self.assertIn(": error}</p>", page_state)
        self.assertNotIn("<p>{error}</p>", page_state)
        self.assertNotIn("postBootstrapLiveStartup", page_state)
        self.assertNotIn("postCandidateRadarQuantProjection", page_state)

    def test_p0_health_and_desktop_pages_surface_backend_offline_recovery(self):
        root = Path(__file__).resolve().parents[1]
        pages = {
            "desktop": root / "desktop" / "src" / "routes" / "DesktopShellPreflight.tsx",
            "health": root / "desktop" / "src" / "routes" / "HealthStatus.tsx",
        }

        for name, path in pages.items():
            with self.subTest(name=name):
                source = path.read_text(encoding="utf-8")
                self.assertIn('import BackendOfflineNotice from "../components/BackendOfflineNotice";', source)
                self.assertIn("<BackendOfflineNotice", source)
                self.assertIn("res.error ?? \"\"", source)
                self.assertNotIn("postBootstrapLiveStartup", source)
                self.assertNotIn("launchLiveBootstrap", source)


if __name__ == "__main__":
    unittest.main()
