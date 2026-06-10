from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path("desktop")


class CommandCenter3FrontendScaffoldTests(unittest.TestCase):
    def test_desktop_scaffold_files_exist(self):
        expected = [
            ROOT / "package.json",
            ROOT / "vite.config.ts",
            ROOT / "src" / "App.tsx",
            ROOT / "src" / "api" / "client.ts",
            ROOT / "src" / "components" / "JsonDetails.tsx",
            ROOT / "src" / "components" / "MetricGrid.tsx",
            ROOT / "src" / "components" / "NextSessionChart.tsx",
            ROOT / "src" / "components" / "TaskStatusPanel.tsx",
            ROOT / "src" / "routes" / "FactorQuantHub.tsx",
            ROOT / "src-tauri" / "tauri.conf.json",
            ROOT / "src-tauri" / "src" / "main.rs",
        ]
        for path in expected:
            with self.subTest(path=path):
                self.assertTrue(path.exists())

    def test_package_scripts_and_dependencies(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("dev", package["scripts"])
        self.assertIn("build", package["scripts"])
        self.assertIn("tauri", package["scripts"])
        self.assertIn("react", package["dependencies"])
        self.assertIn("echarts", package["dependencies"])

    def test_frontend_uses_api_client_and_button_gated_tasks(self):
        source = (ROOT / "src" / "routes" / "FactorQuantHub.tsx").read_text(encoding="utf-8")
        client = (ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")

        self.assertIn("/api/factor-quant/cache", client)
        self.assertIn("/api/factor-quant/refresh-data", source)
        self.assertIn("/api/factor-quant/run-light", source)
        self.assertIn("/api/factor-quant/deepseek-explain", source)
        self.assertIn("多因子量化不是交易建议", source)
        self.assertIn("只整理已有结构化结果", source)
        self.assertIn("summary / support_notes / suppress_notes", source)
        self.assertNotIn("tushare_adapter", source)
        self.assertNotIn("DEEPSEEK", source)
        self.assertNotIn("GITHUB_TOKEN", source)

    def test_read_only_pages_render_structured_cache_without_direct_python_calls(self):
        route_dir = ROOT / "src" / "routes"
        page_names = [
            "CommandCenterHome.tsx",
            "NextSessionMap.tsx",
            "FactorQuantHub.tsx",
            "ChokepointScan.tsx",
            "SerenityMethodRadar.tsx",
            "LegacyTools.tsx",
        ]
        forbidden = ["tushare_adapter", "akshare", "DeepSeek(", "GITHUB_TOKEN", "process.env"]
        for name in page_names:
            source = (route_dir / name).read_text(encoding="utf-8")
            with self.subTest(page=name):
                self.assertIn("PacketCard", source)
                for needle in forbidden:
                    self.assertNotIn(needle, source)

        self.assertIn("MetricGrid", (route_dir / "CommandCenterHome.tsx").read_text(encoding="utf-8"))
        self.assertIn("sqlite_meta", (route_dir / "CommandCenterHome.tsx").read_text(encoding="utf-8"))
        self.assertIn("does_not_modify_action", (route_dir / "NextSessionMap.tsx").read_text(encoding="utf-8"))
        self.assertIn("allow_core_action", (route_dir / "FactorQuantHub.tsx").read_text(encoding="utf-8"))
        self.assertIn("enters_strategy_action", (route_dir / "ChokepointScan.tsx").read_text(encoding="utf-8"))
        self.assertIn("enters_chokepoint_score", (route_dir / "SerenityMethodRadar.tsx").read_text(encoding="utf-8"))

    def test_task_panel_polls_fastapi_task_endpoint(self):
        client = (ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")
        panel = (ROOT / "src" / "components" / "TaskStatusPanel.tsx").read_text(encoding="utf-8")

        self.assertIn("/api/tasks", client)
        self.assertIn("getTask(taskId)", panel)
        self.assertIn("setInterval", panel)
        self.assertIn("local_fallback", panel)
        self.assertIn("onSuccess", panel)

        factor_page = (ROOT / "src" / "routes" / "FactorQuantHub.tsx").read_text(encoding="utf-8")
        self.assertIn("onSuccess={refreshCache}", factor_page)

    def test_next_session_chart_uses_cache_payload_without_trade_mutation(self):
        page = (ROOT / "src" / "routes" / "NextSessionMap.tsx").read_text(encoding="utf-8")
        chart = (ROOT / "src" / "components" / "NextSessionChart.tsx").read_text(encoding="utf-8")

        self.assertIn("NextSessionChart", page)
        self.assertIn("chart_payload", page)
        self.assertIn("uses_real_daily_close", page)
        self.assertIn("is_exact_next_session_packet", page)
        self.assertIn("EChartPanel", chart)
        self.assertIn("historical_points", chart)
        self.assertIn("scenario_series", chart)
        self.assertIn("reference_lines", chart)
        self.assertNotIn("strategy_execution_packet.action", chart)
        self.assertNotIn("operation_zones =", chart)


if __name__ == "__main__":
    unittest.main()
