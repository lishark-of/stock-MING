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
            ROOT / "src" / "routes" / "HealthStatus.tsx",
            ROOT / "src" / "routes" / "MigrationStatus.tsx",
            ROOT / "src" / "routes" / "PacketRegistry.tsx",
            ROOT / "src" / "routes" / "StorageOverview.tsx",
            ROOT / "src" / "routes" / "TaskCatalog.tsx",
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
        self.assertIn("/api/migration/status", client)
        self.assertIn("/api/storage", client)
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
            "HealthStatus.tsx",
            "NextSessionMap.tsx",
            "FactorQuantHub.tsx",
            "ChokepointScan.tsx",
            "SerenityMethodRadar.tsx",
            "PacketRegistry.tsx",
            "MigrationStatus.tsx",
            "StorageOverview.tsx",
            "TaskCatalog.tsx",
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
        home_source = (route_dir / "CommandCenterHome.tsx").read_text(encoding="utf-8")
        self.assertIn("sqlite_meta", home_source)
        self.assertIn("Parquet / DuckDB Storage", home_source)
        self.assertIn("daily / moneyflow / factor_values", home_source)
        self.assertIn("Command Center 3.0 迁移基线", home_source)
        self.assertIn("只读展示，不重新估算", home_source)
        self.assertIn("DeepSeek 模型策略", home_source)
        self.assertIn("deepseek_model_strategy", home_source)
        self.assertIn("progress_baseline", home_source)
        self.assertIn("external_calls_triggered", home_source)
        self.assertIn("不展示 token/key", home_source)
        self.assertNotIn("DEEPSEEK_API_KEY", home_source)
        self.assertIn("does_not_modify_action", (route_dir / "NextSessionMap.tsx").read_text(encoding="utf-8"))
        self.assertIn("allow_core_action", (route_dir / "FactorQuantHub.tsx").read_text(encoding="utf-8"))
        self.assertIn("enters_strategy_action", (route_dir / "ChokepointScan.tsx").read_text(encoding="utf-8"))
        self.assertIn("enters_chokepoint_score", (route_dir / "SerenityMethodRadar.tsx").read_text(encoding="utf-8"))
        migration_source = (route_dir / "MigrationStatus.tsx").read_text(encoding="utf-8")
        self.assertIn("getMigrationStatus", migration_source)
        self.assertIn("只读、不重新估算、不外联", migration_source)
        self.assertIn("does_not_execute_trades", migration_source)
        self.assertNotIn("postTask", migration_source)

        app_source = (ROOT / "src" / "App.tsx").read_text(encoding="utf-8")
        layout_source = (ROOT / "src" / "components" / "Layout.tsx").read_text(encoding="utf-8")
        self.assertIn("HealthStatus", app_source)
        self.assertIn("PacketRegistry", app_source)
        self.assertIn("MigrationStatus", app_source)
        self.assertIn("StorageOverview", app_source)
        self.assertIn("TaskCatalog", app_source)
        self.assertIn('"health"', layout_source)
        self.assertIn('"packets"', layout_source)
        self.assertIn('"migration"', layout_source)
        self.assertIn('"storage"', layout_source)
        self.assertIn('"tasks"', layout_source)
        self.assertIn("健康", layout_source)
        self.assertIn("Packet", layout_source)
        self.assertIn("迁移状态", layout_source)
        self.assertIn("存储层", layout_source)
        self.assertIn("任务目录", layout_source)

    def test_task_panel_polls_fastapi_task_endpoint(self):
        client = (ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")
        panel = (ROOT / "src" / "components" / "TaskStatusPanel.tsx").read_text(encoding="utf-8")

        self.assertIn("/api/tasks", client)
        self.assertIn("/api/tasks/catalog", client)
        self.assertIn("getTask(taskId)", panel)
        self.assertIn("setInterval", panel)
        self.assertIn("local_fallback", panel)
        self.assertIn("onSuccess", panel)
        self.assertIn("call_ledger", panel)
        self.assertIn("status_history", panel)
        self.assertIn("external_calls_triggered", panel)
        self.assertIn("does_not_execute_trades", panel)
        self.assertIn("does_not_modify_strategy_action", panel)
        self.assertIn("DataLineageTable", panel)

    def test_health_page_reads_startup_state_without_external_calls(self):
        page = (ROOT / "src" / "routes" / "HealthStatus.tsx").read_text(encoding="utf-8")

        self.assertIn("getHealth", page)
        self.assertIn("getMigrationStatus", page)
        self.assertIn("GET /health 只读", page)
        self.assertIn("external_calls_on_startup", page)
        self.assertIn("real_trading_enabled", page)
        self.assertIn("deepseek_model_strategy", page)
        self.assertIn("不在调用点硬编码", page)
        self.assertIn("不展示密钥", page)
        self.assertNotIn("postTask", page)
        self.assertNotIn("tushare_adapter", page)
        self.assertNotIn("DEEPSEEK_API_KEY", page)
        self.assertNotIn("GITHUB_TOKEN", page)

        factor_page = (ROOT / "src" / "routes" / "FactorQuantHub.tsx").read_text(encoding="utf-8")
        self.assertIn("onSuccess={refreshCache}", factor_page)
        home_source = (ROOT / "src" / "routes" / "CommandCenterHome.tsx").read_text(encoding="utf-8")
        self.assertIn("getTaskCatalog", home_source)
        self.assertIn("POST task 才可能触发外部请求", home_source)
        self.assertIn("call_ledger_required_for_all", home_source)

        task_catalog_page = (ROOT / "src" / "routes" / "TaskCatalog.tsx").read_text(encoding="utf-8")
        self.assertIn("getTaskCatalog", task_catalog_page)
        self.assertIn("getTasks", task_catalog_page)
        self.assertIn("GET /api/tasks", task_catalog_page)
        self.assertIn("任务记录", task_catalog_page)
        self.assertIn("call_ledger_required_for_all", task_catalog_page)
        self.assertIn("POST task 才可能触发外部请求", task_catalog_page)
        self.assertIn("does_not_execute_trades", task_catalog_page)
        self.assertIn("does_not_modify_strategy_action", task_catalog_page)
        self.assertNotIn("postTask", task_catalog_page)

    def test_storage_page_reads_storage_cache_without_external_calls(self):
        page = (ROOT / "src" / "routes" / "StorageOverview.tsx").read_text(encoding="utf-8")

        self.assertIn("getStorageOverview", page)
        self.assertIn("getFactorValuesStorage", page)
        self.assertIn("Parquet / DuckDB Storage", page)
        self.assertIn("daily / moneyflow / factor_values", page)
        self.assertIn("cache API 永不外联", page)
        self.assertIn("external_calls_triggered", page)
        self.assertIn("does_not_execute_trades", page)
        self.assertIn("does_not_modify_strategy_action", page)
        self.assertNotIn("postTask", page)
        self.assertNotIn("tushare_adapter", page)
        self.assertNotIn("DEEPSEEK", page)
        self.assertNotIn("GITHUB_TOKEN", page)

    def test_chokepoint_page_shows_research_only_task_boundaries(self):
        page = (ROOT / "src" / "routes" / "ChokepointScan.tsx").read_text(encoding="utf-8")

        self.assertIn("getChokepointCache", page)
        self.assertIn("/api/chokepoint/run", page)
        self.assertIn("GET cache 不运行瓶颈扫描", page)
        self.assertIn("cache API 永不外联", page)
        self.assertIn("手动 POST task", page)
        self.assertIn("DeepSeek 只可整理解释，不作为数据源", page)
        self.assertIn("研究解释不进入 strategy action", page)
        self.assertIn("不写回次日操作图谱", page)
        self.assertIn("不执行真实交易", page)
        self.assertIn("cache_api_external_calls_triggered", page)
        self.assertIn("legacy_analysis_method_cache", page)
        self.assertIn("DataLineageTable", page)
        self.assertNotIn("tushare_adapter", page)
        self.assertNotIn("DEEPSEEK_API_KEY", page)
        self.assertNotIn("GITHUB_TOKEN", page)

    def test_packet_registry_page_reads_packet_cache_without_external_calls(self):
        client = (ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")
        page = (ROOT / "src" / "routes" / "PacketRegistry.tsx").read_text(encoding="utf-8")

        self.assertIn("/api/packets", client)
        self.assertIn("encodeURIComponent(packetKey)", client)
        self.assertIn("getPackets", page)
        self.assertIn("getPacket", page)
        self.assertIn("GET /api/packets", page)
        self.assertIn("GET /api/packets/{packet_key} 永不外联", page)
        self.assertIn("cache API 永不外联", page)
        self.assertIn("does_not_modify_strategy_action", page)
        self.assertNotIn("postTask", page)
        self.assertNotIn("tushare_adapter", page)
        self.assertNotIn("DEEPSEEK", page)
        self.assertNotIn("GITHUB_TOKEN", page)

    def test_serenity_page_shows_local_baseline_and_decision_boundaries(self):
        page = (ROOT / "src" / "routes" / "SerenityMethodRadar.tsx").read_text(encoding="utf-8")

        self.assertIn("getSerenityCache", page)
        self.assertIn("/api/serenity/github-probe", page)
        self.assertIn("本地方法来源基线", page)
        self.assertIn("GitHub 当前状态为未校验", page)
        self.assertIn("手动 POST task", page)
        self.assertIn("防幻觉演进", page)
        self.assertIn("方法归纳", page)
        self.assertIn("决策边界", page)
        self.assertIn("技术血缘", page)
        self.assertIn("source_type", page)
        self.assertIn("user_screenshot_baseline", page)
        self.assertIn("enters_strategy_action", page)
        self.assertIn("enters_chokepoint_score", page)
        self.assertIn("enters_next_session_projection", page)
        self.assertIn("enters_deepseek_prompt", page)
        self.assertNotIn("tushare_adapter", page)
        self.assertNotIn("DEEPSEEK_API_KEY", page)

    def test_legacy_page_declares_streamlit_as_guarded_legacy_surface(self):
        page = (ROOT / "src" / "routes" / "LegacyTools.tsx").read_text(encoding="utf-8")

        self.assertIn("legacy/admin/debug", page)
        self.assertIn("普通主流程请使用 Command Center 3", page)
        self.assertIn("不会创建任务", page)
        self.assertIn("不调用 Tushare、DeepSeek 或 GitHub", page)
        self.assertIn("不会绕过 strategy_execution_packet", page)
        self.assertIn("真实交易", page)
        self.assertIn("自动下单", page)
        self.assertIn("DataLineageTable", page)
        self.assertNotIn("postTask", page)
        self.assertNotIn("tushare_adapter", page)
        self.assertNotIn("DEEPSEEK_API_KEY", page)
        self.assertNotIn("GITHUB_TOKEN", page)

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
