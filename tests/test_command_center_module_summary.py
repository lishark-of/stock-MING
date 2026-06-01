import ast
import datetime
import json
import unittest
from pathlib import Path

import command_center_module_summary as module_summary


FORBIDDEN_IMPORTS = {
    "streamlit",
    "pywebview",
    "webview",
    "data_fetcher",
    "backtester",
    "tushare_adapter",
    "yfinance",
    "akshare",
    "tushare",
    "openai",
    "app",
    "command_center_service",
}


class CommandCenterModuleSummaryTests(unittest.TestCase):
    def test_missing_section_outputs_unrefreshed_state(self):
        view_model = module_summary.build_module_summary_view_model(None, module_name="市场环境")

        self.assertEqual(view_model["status"], "missing")
        self.assertEqual(view_model["badge"], "未刷新")
        self.assertEqual(view_model["tone"], "muted")
        self.assertIn("未刷新", view_model["reason"])
        self.assertEqual(view_model["source_text"], "未加载")
        json.dumps(view_model, ensure_ascii=False)

    def test_auto_light_outputs_realtime_light_state(self):
        view_model = module_summary.build_module_summary_view_model(
            {
                "status": "ready",
                "refresh_level": "auto_light",
                "updated_at": "2026-06-01T09:30:00",
                "source": "session_state 聚合",
                "deepseek_called": False,
            }
        )

        self.assertEqual(view_model["status"], "auto_light")
        self.assertEqual(view_model["badge"], "实时轻量")
        self.assertEqual(view_model["deepseek_text"], "DeepSeek：未调用")
        self.assertIn("轻量快照", view_model["reason"])

    def test_manual_basic_today_outputs_today_refreshed_state(self):
        today = datetime.date.today().isoformat()
        view_model = module_summary.build_module_summary_view_model(
            {
                "status": "ok",
                "refresh_level": "manual_basic",
                "updated_at": f"{today}T10:00:00",
                "source": "综合中心基础刷新",
            }
        )

        self.assertEqual(view_model["status"], "manual_basic_today")
        self.assertEqual(view_model["badge"], "今日已刷新")
        self.assertEqual(view_model["tone"], "success")

    def test_failed_with_last_success_uses_cache_and_error_text(self):
        view_model = module_summary.build_module_summary_view_model(
            {
                "status": "failed",
                "last_success": {"summary": "last good"},
                "last_error": "timeout",
                "stale": True,
                "source": "Tushare 市场风格事实包",
            }
        )

        self.assertEqual(view_model["status"], "cached")
        self.assertEqual(view_model["badge"], "使用缓存")
        self.assertEqual(view_model["error_text"], "timeout")
        self.assertTrue(view_model["is_stale"])
        self.assertIn("上次成功", view_model["reason"])

    def test_stale_section_uses_cache(self):
        view_model = module_summary.build_module_summary_view_model(
            {
                "status": "ready",
                "stale": True,
                "updated_at": "2026-05-31T15:00:00",
            }
        )

        self.assertEqual(view_model["status"], "cached")
        self.assertEqual(view_model["badge"], "使用缓存")
        self.assertTrue(view_model["is_stale"])

    def test_missing_source_uses_default_source_text(self):
        self.assertEqual(module_summary.module_source_text({"status": "ok"}), "未加载")

    def test_deepseek_called_false_outputs_not_called(self):
        self.assertEqual(module_summary.module_deepseek_text({"deepseek_called": False}), "DeepSeek：未调用")

    def test_failed_without_cache_outputs_failed_state(self):
        view_model = module_summary.build_module_summary_view_model(
            {"status": "failed", "last_error": "bad packet"}
        )

        self.assertEqual(view_model["status"], "failed")
        self.assertEqual(view_model["badge"], "failed / error")
        self.assertEqual(view_model["tone"], "danger")

    def test_build_all_module_summary_view_model_handles_core_modules(self):
        live_packet = {
            "market": {"refresh_level": "auto_light", "status": "ready"},
            "quant": {"refresh_level": "manual_basic", "status": "ok"},
            "discipline": {"stale": True},
            "margin_etf": {"status": "failed", "last_success": {"summary": "ok"}, "last_error": "timeout"},
            "next_ticket": {},
            "strategy_execution": {"refresh_label": "需要深度刷新"},
        }

        view_model = module_summary.build_all_module_summary_view_model(live_packet)

        self.assertEqual(
            set(view_model["modules"]),
            {"market", "quant", "discipline", "margin_etf", "next_ticket", "strategy_execution"},
        )
        self.assertEqual(view_model["modules"]["market"]["badge"], "实时轻量")
        self.assertEqual(view_model["modules"]["margin_etf"]["badge"], "使用缓存")
        self.assertEqual(view_model["modules"]["strategy_execution"]["badge"], "需要深度刷新")
        json.dumps(view_model, ensure_ascii=False)

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_module_summary.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_module_summary.py: {name}")


if __name__ == "__main__":
    unittest.main()
