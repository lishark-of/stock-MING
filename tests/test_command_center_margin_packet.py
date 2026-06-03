import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_margin_packet as margin_packet


class CommandCenterMarginPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = margin_packet.build_command_center_margin_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不会自动请求", packet["summary"])
        self.assertIn("手动刷新", packet["manual_required_text"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_a_share_professional_margin_is_normalized(self):
        state = {
            "a_share_professional_facts": {
                "margin": {
                    "available": True,
                    "date": "20260603",
                    "financing_balance_yi": "12.3",
                    "financing_buy_yi": "1.2",
                    "margin_balance_yi": "13.5",
                    "short_sell_volume": "20000",
                    "updated_at": "2026-06-03T16:00:00",
                }
            }
        }

        packet = margin_packet.build_command_center_margin_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["financing_balance_yi"], 12.3)
        self.assertEqual(packet["financing_buy_yi"], 1.2)
        self.assertEqual(packet["leverage_state"], "融资买入增加")
        self.assertIn("不等于主力资金", " ".join(packet["risk_notes"]))
        self.assertFalse(packet["deepseek_called"])

    def test_permission_denied_stays_missing_and_conservative(self):
        packet = margin_packet.build_command_center_margin_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "margin",
                            "label": "融资融券",
                            "state": "permission_denied",
                            "status": "权限不足",
                            "api": "margin_detail",
                            "risk": "抱歉，您没有访问该接口的权限。",
                        }
                    ]
                }
            }
        )

        self.assertEqual(packet["status"], "failed")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不能假设杠杆资金改善", " ".join(packet["risk_notes"]))

    def test_existing_packet_is_preserved_without_mutating_input(self):
        state = {
            "command_center_margin_packet": {
                "status": "ready",
                "target": "002008.SZ",
                "financing_balance_yi": "10",
                "financing_buy_yi": "0.5",
                "leverage_state": "融资买入增加",
                "summary": "saved",
                "risk_notes": ["风险 A"],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(state)

        packet = margin_packet.build_command_center_margin_packet(state, target="002008.SZ")

        self.assertEqual(state, original)
        self.assertEqual(packet["financing_balance_yi"], 10)
        self.assertEqual(packet["summary"], "saved")
        self.assertFalse(packet["deepseek_called"])

    def test_target_mismatch_ignores_existing_payload(self):
        packet = margin_packet.build_command_center_margin_packet(
            {
                "command_center_margin_packet": {
                    "status": "ready",
                    "target": "002008.SZ",
                    "financing_balance_yi": 10,
                }
            },
            target="000001.SZ",
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_margin_packet.py").read_text(encoding="utf-8"))
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
