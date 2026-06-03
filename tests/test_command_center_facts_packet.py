import ast
import json
import unittest
from pathlib import Path

import command_center_facts_packet as facts


class CommandCenterFactsPacketTests(unittest.TestCase):
    def test_a_share_facts_packet_keeps_available_and_restricted_facts(self):
        packet = facts.build_a_share_facts_packet(
            {
                "stock_code": "002008",
                "stock_name": "大族激光",
                "moneyflow": {
                    "available": True,
                    "source": "Tushare",
                    "api": "moneyflow",
                    "date": "20260602",
                    "main_net_yi": "1.23",
                    "updated_at": "2026-06-02T10:00:00",
                },
                "margin": {
                    "available": False,
                    "source": "Tushare",
                    "api": "margin_detail",
                    "error": "抱歉，您没有访问该接口的权限",
                },
                "dragon_tiger": {"available": False, "message": "近30日未见龙虎榜上榜记录"},
            },
            data_capability_packet={
                "items": [
                    {"section": "moneyflow", "label": "个股资金流", "api": "moneyflow", "capability_state": "available", "status": "可用"},
                    {"section": "margin", "label": "融资融券", "api": "margin_detail", "capability_state": "permission_denied", "status": "权限不足"},
                    {"section": "dragon_tiger", "label": "龙虎榜", "api": "top_list", "capability_state": "empty_recent", "status": "近期无数据"},
                ]
            },
            target="002008.SZ",
            name="大族激光",
        )
        by_key = {item["key"]: item for item in packet["items"]}

        self.assertEqual(packet["market"], "A股")
        self.assertEqual(packet["ticker"], "002008.SZ")
        self.assertEqual(by_key["moneyflow"]["state"], "available")
        self.assertIn("主力净额", by_key["moneyflow"]["evidence"])
        self.assertEqual(by_key["margin"]["state"], "permission_denied")
        self.assertIn("权限", by_key["margin"]["status"])
        self.assertEqual(by_key["dragon_tiger"]["state"], "empty_recent")
        self.assertIn("个股资金流", packet["available_items"])
        self.assertEqual(packet["restricted_items"][0]["label"], "融资融券")
        self.assertIn("龙虎榜", packet["pending_items"][0]["label"])
        self.assertIn("受限/失败：融资融券", packet["gap_summary"])
        self.assertTrue(any("权限不足" in item for item in packet["next_manual_checks"]))
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_command_center_facts_packet_can_fallback_to_capability_only(self):
        packet = facts.build_command_center_facts_packet(
            {
                "a_share_professional_data_capability": {
                    "items": [
                        {"section": "limit_emotion", "label": "涨跌停/情绪", "api": "limit_cpt_list", "capability_state": "disabled_this_session", "status": "本会话跳过"},
                    ]
                }
            },
            target="002008.SZ",
        )
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["status"], "partial")
        self.assertIn("涨跌停", dumped)
        self.assertIn("本会话跳过", dumped)
        self.assertTrue(any("本会话已跳过" in item for item in packet["next_manual_checks"]))
        self.assertFalse(packet["deepseek_called"])

    def test_existing_packet_is_enriched_with_gap_summary(self):
        packet = facts.build_command_center_facts_packet(
            {
                "command_center_facts_packet": {
                    "status": "partial",
                    "items": [
                        {"key": "moneyflow", "label": "个股资金流", "state": "available", "status": "通过"},
                        {"key": "chip_radar", "label": "筹码/胜率", "state": "unknown", "status": "待验证", "api": "cyq_perf"},
                    ],
                    "deepseek_called": True,
                }
            },
            target="002008.SZ",
        )

        self.assertIn("个股资金流", packet["available_items"])
        self.assertEqual(packet["pending_items"][0]["label"], "筹码/胜率")
        self.assertIn("待验证", packet["gap_summary"])
        self.assertFalse(packet["deepseek_called"])

    def test_empty_and_non_mapping_inputs_are_safe(self):
        packet = facts.build_a_share_facts_packet(object(), object(), target="AAPL")

        self.assertEqual(packet["market"], "A股")
        self.assertEqual(len(packet["items"]), 5)
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_facts_packet.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        forbidden = {
            "streamlit",
            "app",
            "tushare_adapter",
            "tushare",
            "akshare",
            "yfinance",
            "data_fetcher",
            "backtester",
            "openai",
        }
        self.assertTrue(forbidden.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
