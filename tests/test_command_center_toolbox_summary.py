import ast
import json
import unittest
from pathlib import Path

import command_center_toolbox_summary as toolbox


FORBIDDEN_IMPORTS = {
    "streamlit",
    "app",
    "command_center_service",
    "strategy_execution_service",
    "command_center_decision_engine",
    "tushare_adapter",
    "tushare",
    "akshare",
    "yfinance",
    "data_fetcher",
    "backtester",
    "openai",
}


class CommandCenterToolboxSummaryTests(unittest.TestCase):
    def test_advanced_toolbox_entry_is_manual_and_json_friendly(self):
        packet = toolbox.build_advanced_toolbox_entry()
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["status"], "ready")
        self.assertFalse(packet["deepseek_called"])
        self.assertIn("综合推演中心仍是默认主入口", packet["summary"])
        self.assertIn("不会自动触发 DeepSeek", packet["manual_note"])
        self.assertIn("Tushare 拉满或 token 可用", packet["data_gap_note"])
        self.assertIn("数据源体检", dumped)
        self.assertIn("下一票雷达", dumped)
        self.assertIn("capability_map", packet)
        self.assertTrue(packet["items"])

    def test_toolbox_items_are_button_gated_and_packet_mapped(self):
        packet = toolbox.build_advanced_toolbox_entry()

        for item in packet["items"]:
            self.assertEqual(item["trigger_policy"], "button_gated")
            self.assertEqual(item["deepseek_policy"], "manual_only")
            self.assertTrue(item["packet"])
            self.assertTrue(item["gate"])
            self.assertTrue(item["data_dependencies"])
            self.assertTrue(item["common_missing_reasons"])
            self.assertTrue(item["safe_empty_state"])
            self.assertFalse(item["capability_summary"]["deepseek_called"])

    def test_can_filter_toolbox_items(self):
        packet = toolbox.build_advanced_toolbox_entry(keys=["data_healthcheck"])

        self.assertEqual(len(packet["items"]), 1)
        self.assertEqual(packet["items"][0]["label"], "数据源体检")
        self.assertEqual(packet["capability_map"][0]["key"], "data_healthcheck")

    def test_legacy_tool_capability_map_explains_why_old_data_can_be_missing(self):
        capability_map = toolbox.build_legacy_tool_capability_map()
        dumped = json.dumps(capability_map, ensure_ascii=False)

        self.assertIn("Tushare moneyflow", dumped)
        self.assertIn("top_list", dumped)
        self.assertIn("limit_cpt_list", dumped)
        self.assertIn("Tushare token 可用不等于", dumped)
        self.assertIn("权限不足", dumped)
        self.assertIn("非交易日", dumped)
        self.assertIn("使用缓存", dumped)

    def test_filtered_capability_map_keeps_manual_gate(self):
        capability_map = toolbox.build_legacy_tool_capability_map(keys=["next_ticket_radar"])

        self.assertEqual(len(capability_map), 1)
        self.assertEqual(capability_map[0]["key"], "next_ticket_radar")
        self.assertIn("按钮", capability_map[0]["manual_gate"])
        self.assertFalse(capability_map[0]["deepseek_called"])

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_toolbox_summary.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        self.assertTrue(FORBIDDEN_IMPORTS.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
