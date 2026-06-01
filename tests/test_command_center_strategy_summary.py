import ast
import json
import unittest
from pathlib import Path

import command_center_strategy_summary as summary


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
    "strategy_execution_service",
}


class CommandCenterStrategySummaryTests(unittest.TestCase):
    def test_empty_packet_uses_waiting_defaults(self):
        view_model = summary.build_strategy_summary_view_model(None)

        self.assertEqual(view_model["status"], "waiting")
        self.assertEqual(view_model["status_label"], "待生成")
        self.assertEqual(view_model["action_label"], "尚未生成")
        self.assertEqual(view_model["confidence_label"], "待生成")
        self.assertEqual(len(view_model["path_items"]), 3)
        json.dumps(view_model, ensure_ascii=False)

    def test_status_labels_cover_waiting_ready_failed(self):
        self.assertEqual(summary.strategy_status_label({"status": "waiting"}), "待生成")
        self.assertEqual(summary.strategy_status_label({"status": "ready"}), "策略建议已生成")
        self.assertEqual(summary.strategy_status_label({"status": "failed"}), "失败后缓存")

    def test_action_and_confidence_tones(self):
        self.assertEqual(summary.strategy_action_tone({"action": "等待"}), "warning")
        self.assertEqual(summary.strategy_action_tone({"action": "小幅进攻"}), "success")
        self.assertEqual(summary.strategy_action_tone({"action": "只观察"}), "warning")
        self.assertEqual(summary.strategy_action_tone({"action": "降风险"}), "danger")
        self.assertEqual(summary.strategy_confidence_tone({"confidence": "低"}), "muted")
        self.assertEqual(summary.strategy_confidence_tone({"confidence": "中"}), "warning")
        self.assertEqual(summary.strategy_confidence_tone({"confidence": "高"}), "success")

    def test_missing_paths_use_default_three_paths(self):
        paths = summary.build_strategy_path_items({})

        self.assertEqual(len(paths), 3)
        self.assertEqual(paths[0]["name"], "乐观路径")

    def test_missing_discipline_and_risk_budget_are_safe(self):
        view_model = summary.build_strategy_summary_view_model({"status": "ready"})

        self.assertTrue(view_model["discipline_items"])
        self.assertTrue(view_model["risk_budget_items"])
        self.assertEqual(view_model["risk_budget_items"][0]["label"], "仓位建议")

    def test_data_status_items_cover_missing_cached_ready(self):
        items = summary.build_strategy_data_status_items({
            "data_status": {
                "quant": "ready",
                "backtest": "cached",
                "live_packet": "missing",
            }
        })
        by_key = {item["key"]: item for item in items}

        self.assertEqual(by_key["quant"]["state"], "ready")
        self.assertEqual(by_key["backtest"]["state"], "cached")
        self.assertEqual(by_key["live_packet"]["state"], "missing")

    def test_deepseek_false_and_last_error_are_visible(self):
        view_model = summary.build_strategy_summary_view_model({
            "deepseek_called": False,
            "last_error": "timeout",
            "status": "failed",
        })

        self.assertEqual(view_model["deepseek_text"], "DeepSeek：未调用")
        self.assertEqual(view_model["last_error_text"], "timeout")
        self.assertIn("上次生成失败：timeout", view_model["warning_items"])

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_strategy_summary.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_strategy_summary.py: {name}")


if __name__ == "__main__":
    unittest.main()
