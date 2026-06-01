import ast
import json
import unittest
from pathlib import Path

import command_center_overview_summary as summary


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


class CommandCenterOverviewSummaryTests(unittest.TestCase):
    def test_all_missing_outputs_waiting_overview(self):
        view_model = summary.build_command_center_overview_view_model()

        self.assertEqual(view_model["overall_status_label"], "待刷新")
        self.assertEqual(view_model["overall_status_tone"], "muted")
        self.assertTrue(all(item["state"] == "missing" for item in view_model["coverage_items"]))
        self.assertEqual(view_model["deepseek_text"], "DeepSeek：未调用")
        json.dumps(view_model, ensure_ascii=False)

    def test_partial_ready_outputs_partial_overview(self):
        view_model = summary.build_command_center_overview_view_model(
            live_packet={
                "market": {"status": "ready"},
                "quant": {"last_success": {"summary": "cached"}},
            }
        )

        self.assertEqual(view_model["overall_status_label"], "部分刷新")
        by_key = {item["key"]: item for item in view_model["coverage_items"]}
        self.assertEqual(by_key["market"]["state"], "ready")
        self.assertEqual(by_key["quant"]["state"], "cached")

    def test_all_ready_outputs_refreshed_overview(self):
        live_packet = {
            key: {"status": "ready"}
            for key in ["market", "quant", "discipline", "margin_etf", "next_ticket"]
        }
        view_model = summary.build_command_center_overview_view_model(
            live_packet=live_packet,
            strategy_packet={"status": "ready"},
        )

        self.assertEqual(view_model["overall_status_label"], "已刷新")
        self.assertEqual(view_model["overall_status_tone"], "success")

    def test_errors_are_visible(self):
        view_model = summary.build_command_center_overview_view_model(
            live_packet={"errors": [{"module": "市场", "message": "timeout"}]}
        )

        self.assertEqual(view_model["overall_status_label"], "有错误")
        self.assertEqual(view_model["error_items"][0]["message"], "timeout")

    def test_refresh_summary_errors_are_visible(self):
        view_model = summary.build_command_center_overview_view_model(
            refresh_summary={"finished_at": "2026-06-01T09:30:00", "errors": [{"module": "量化", "message": "cache missing"}]}
        )

        self.assertEqual(view_model["error_items"][0]["module"], "量化")
        self.assertEqual(view_model["error_items"][0]["updated_at"], "2026-06-01T09:30:00")

    def test_stale_items_are_visible(self):
        view_model = summary.build_command_center_overview_view_model(
            live_packet={"market": {"stale": True, "updated_at": "2026-06-01", "source": "缓存"}}
        )

        self.assertEqual(view_model["stale_items"][0]["key"], "market")
        self.assertEqual(view_model["stale_items"][0]["source"], "缓存")

    def test_next_actions_reflect_packet_presence(self):
        view_model = summary.build_command_center_overview_view_model(
            live_packet={"market": {"status": "ready"}},
            strategy_packet={"status": "ready"},
            decision_packet={"status": "ready"},
        )
        by_key = {item["key"]: item for item in view_model["next_action_items"]}

        self.assertEqual(by_key["refresh_basic"]["status"], "ready")
        self.assertEqual(by_key["strategy_execution"]["status"], "ready")
        self.assertEqual(by_key["daily_decision"]["status"], "ready")
        self.assertEqual(by_key["deepseek"]["status"], "optional")

    def test_missing_fields_are_safe(self):
        view_model = summary.build_command_center_overview_view_model(
            live_packet=object(),
            refresh_summary=object(),
            decision_packet=object(),
            strategy_packet=object(),
        )

        self.assertIsInstance(view_model, dict)
        json.dumps(view_model, ensure_ascii=False)

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_overview_summary.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_overview_summary.py: {name}")


if __name__ == "__main__":
    unittest.main()
