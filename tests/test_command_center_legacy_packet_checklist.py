import ast
import json
import unittest
from pathlib import Path

import command_center_legacy_packet_checklist as checklist


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


class CommandCenterLegacyPacketChecklistTests(unittest.TestCase):
    def test_empty_checklist_is_json_friendly_and_manual_safe(self):
        packet = checklist.build_legacy_packet_migration_checklist()
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["title"], "旧工作台能力迁移清单")
        self.assertEqual(len(packet["items"]), 7)
        self.assertFalse(packet["deepseek_called"])
        self.assertEqual(packet["external_call_policy"], "not_triggered")
        self.assertIn("不会自动调用 Tushare", packet["safe_mode_text"])
        self.assertIn("个股资金流", dumped)
        self.assertIn("龙虎榜", dumped)
        self.assertIn("涨跌停", dumped)
        self.assertIn("融资融券", dumped)
        self.assertIn("筹码/胜率", dumped)
        self.assertIn("纪律/回测", dumped)
        self.assertIn("下一票雷达", dumped)
        self.assertTrue(all(item["refresh_policy"] == "button_gated" for item in packet["items"]))
        self.assertTrue(all(item["external_call_policy"] == "not_triggered" for item in packet["items"]))
        self.assertTrue(all(item["deepseek_called"] is False for item in packet["items"]))

    def test_ready_moneyflow_packet_is_marked_as_packet_ready(self):
        packet = checklist.build_legacy_packet_migration_checklist(
            {
                "moneyflow_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "summary": "资金流已回流",
                }
            }
        )
        by_key = {item["key"]: item for item in packet["items"]}

        self.assertEqual(by_key["moneyflow"]["migration_state"], "packet_ready")
        self.assertEqual(by_key["moneyflow"]["migration_label"], "已回流")
        self.assertEqual(by_key["moneyflow"]["target_packet"], "command_center_moneyflow_packet")
        self.assertIn("复核日期", by_key["moneyflow"]["next_action"])

    def test_permission_denied_recovery_action_blocks_margin_packet(self):
        packet = checklist.build_legacy_packet_migration_checklist(
            {
                "data_recovery_center": {
                    "actions": [
                        {
                            "label": "融资融券",
                            "writes_packet": "command_center_margin_packet",
                            "status_label": "权限不足",
                            "summary": "Tushare margin_detail 权限不足",
                        }
                    ]
                }
            }
        )
        by_key = {item["key"]: item for item in packet["items"]}
        margin = by_key["margin"]

        self.assertEqual(margin["migration_state"], "blocked")
        self.assertEqual(margin["tone"], "failed")
        self.assertEqual(margin["writes_packet"], "command_center_margin_packet")
        self.assertIn("权限", margin["next_action"])
        self.assertIn("融资比例", margin["decision_guardrail"])

    def test_discipline_and_radar_stay_button_gated(self):
        packet = checklist.build_legacy_packet_migration_checklist(
            {
                "legacy_migration_map": {
                    "items": [
                        {
                            "key": "discipline_backtest",
                            "label": "纪律/回测",
                            "writes_packet": "command_center_discipline_packet",
                            "migration_state": "manual_required",
                        },
                        {
                            "key": "next_ticket_radar",
                            "label": "下一票雷达",
                            "command_center_packets": ["command_center_radar_packet"],
                            "migration_state": "wired_waiting_data",
                        },
                    ]
                }
            }
        )
        by_key = {item["key"]: item for item in packet["items"]}

        self.assertEqual(by_key["discipline_backtest"]["migration_state"], "manual_required")
        self.assertEqual(by_key["discipline_backtest"]["refresh_policy"], "button_gated")
        self.assertEqual(by_key["next_ticket_radar"]["migration_state"], "wired_waiting_data")
        self.assertEqual(by_key["next_ticket_radar"]["refresh_policy"], "button_gated")
        self.assertFalse(by_key["next_ticket_radar"]["deepseek_called"])

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_legacy_packet_checklist.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        self.assertTrue(FORBIDDEN_IMPORTS.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
