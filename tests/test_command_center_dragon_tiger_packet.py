import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_dragon_tiger_packet as dragon_packet


class CommandCenterDragonTigerPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = dragon_packet.build_command_center_dragon_tiger_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不会自动请求", packet["summary"])
        self.assertIn("手动刷新", packet["manual_required_text"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_a_share_professional_dragon_tiger_is_normalized(self):
        state = {
            "a_share_professional_facts": {
                "dragon_tiger": {
                    "available": True,
                    "latest_date": "20260603",
                    "reason": "日涨幅偏离值达7%",
                    "close": "25.6",
                    "pct_change": "9.8",
                    "buy_amount_yi": "2.4",
                    "sell_amount_yi": "1.1",
                    "net_buy_amount_yi": "1.3",
                    "inst_summary": "席位3条，净买入1.3亿",
                    "inst_rows": [
                        {"name": "机构专用", "buy": "120000000", "sell": "20000000", "net_buy": "100000000"}
                    ],
                    "updated_at": "2026-06-03T16:00:00",
                }
            }
        }

        packet = dragon_packet.build_command_center_dragon_tiger_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["net_buy_amount_yi"], 1.3)
        self.assertEqual(packet["activity_state"], "席位净买入")
        self.assertEqual(packet["inst_rows"][0]["name"], "机构专用")
        self.assertIn("不单独构成买入理由", " ".join(packet["risk_notes"]))
        self.assertFalse(packet["deepseek_called"])

    def test_empty_recent_is_not_treated_as_support(self):
        packet = dragon_packet.build_command_center_dragon_tiger_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "dragon_tiger",
                            "label": "龙虎榜",
                            "state": "empty_recent",
                            "status": "近期无数据",
                            "api": "top_list",
                            "risk": "近30日未见龙虎榜上榜记录",
                        }
                    ]
                }
            }
        )

        self.assertEqual(packet["status"], "partial")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不等于机构支持", " ".join(packet["risk_notes"]))

    def test_existing_packet_is_preserved_without_mutating_input(self):
        state = {
            "command_center_dragon_tiger_packet": {
                "status": "ready",
                "target": "002008.SZ",
                "net_buy_amount_yi": "1.2",
                "activity_state": "席位净买入",
                "summary": "saved",
                "risk_notes": ["风险 A"],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(state)

        packet = dragon_packet.build_command_center_dragon_tiger_packet(state, target="002008.SZ")

        self.assertEqual(state, original)
        self.assertEqual(packet["net_buy_amount_yi"], 1.2)
        self.assertEqual(packet["summary"], "saved")
        self.assertFalse(packet["deepseek_called"])

    def test_target_mismatch_ignores_existing_payload(self):
        packet = dragon_packet.build_command_center_dragon_tiger_packet(
            {
                "command_center_dragon_tiger_packet": {
                    "status": "ready",
                    "target": "002008.SZ",
                    "net_buy_amount_yi": 1.1,
                }
            },
            target="000001.SZ",
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_dragon_tiger_packet.py").read_text(encoding="utf-8"))
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
