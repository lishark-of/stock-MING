import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_moneyflow_packet as moneyflow_packet


class CommandCenterMoneyflowPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = moneyflow_packet.build_command_center_moneyflow_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不会自动请求", packet["summary"])
        self.assertIn("手动刷新", packet["manual_required_text"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_a_share_professional_moneyflow_is_normalized(self):
        state = {
            "a_share_professional_facts": {
                "moneyflow": {
                    "available": True,
                    "date": "20260603",
                    "main_net_yi": "1.23",
                    "five_day_main_net_yi": "3.45",
                    "large_net_yi": "0.7",
                    "medium_net_yi": "-0.2",
                    "small_net_yi": "-0.1",
                    "direction": "主力回流",
                    "updated_at": "2026-06-03T16:00:00",
                }
            }
        }

        packet = moneyflow_packet.build_command_center_moneyflow_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["main_net_yi"], 1.23)
        self.assertEqual(packet["five_day_main_net_yi"], 3.45)
        self.assertEqual(packet["flow_state"], "主力净流入")
        self.assertIn("不单独构成买入理由", " ".join(packet["risk_notes"]))
        self.assertFalse(packet["deepseek_called"])

    def test_facts_item_empty_recent_stays_missing(self):
        packet = moneyflow_packet.build_command_center_moneyflow_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "moneyflow",
                            "label": "个股资金流",
                            "state": "empty_recent",
                            "status": "近期无数据",
                            "api": "moneyflow",
                            "risk": "近5日未取得可验证个股资金流。",
                        }
                    ]
                }
            }
        )

        self.assertEqual(packet["status"], "partial")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不能把缺失数据当成无资金风险", " ".join(packet["risk_notes"]))

    def test_existing_packet_is_preserved_without_mutating_input(self):
        state = {
            "command_center_moneyflow_packet": {
                "status": "ready",
                "target": "002008.SZ",
                "main_net_yi": "1.5",
                "flow_state": "主力净流入",
                "summary": "saved",
                "risk_notes": ["风险 A"],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(state)

        packet = moneyflow_packet.build_command_center_moneyflow_packet(state, target="002008.SZ")

        self.assertEqual(state, original)
        self.assertEqual(packet["main_net_yi"], 1.5)
        self.assertEqual(packet["summary"], "saved")
        self.assertFalse(packet["deepseek_called"])

    def test_target_mismatch_ignores_existing_payload(self):
        packet = moneyflow_packet.build_command_center_moneyflow_packet(
            {
                "command_center_moneyflow_packet": {
                    "status": "ready",
                    "target": "002008.SZ",
                    "main_net_yi": 1.1,
                }
            },
            target="000001.SZ",
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_moneyflow_packet.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        forbidden = {
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

        self.assertTrue(forbidden.isdisjoint(imports))


if __name__ == "__main__":
    unittest.main()
