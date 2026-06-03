import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_market_packet as market_packet


class CommandCenterMarketPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = market_packet.build_command_center_market_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不在页面打开时自动请求", packet["summary"])
        self.assertFalse(packet["deepseek_called"])

    def test_legacy_market_style_fact_packet_is_normalized(self):
        packet = market_packet.build_command_center_market_packet(
            {
                "legacy_market_style_fact_packet": {
                    "trade_date": "20260603",
                    "market_state": "修复",
                    "risk_switch": "适合轻仓试错",
                    "limit_up_count": 42,
                    "limit_down_count": 3,
                    "break_limit_count": 9,
                    "break_limit_rate": 0.18,
                    "max_consecutive_limit": 4,
                    "verified_sources": ["Tushare limit_list_d", "Tushare moneyflow"],
                    "missing_sources": ["Tushare top_list: 最近交易日无龙虎榜返回"],
                    "concept_strength_top": [{"name": "机器人", "rank": 1}],
                    "dragon_tiger_activity": {"list_count": 0},
                    "moneyflow_samples": {"positive_samples": [{"name": "A"}], "negative_samples": []},
                    "updated_at": "2026-06-03T10:00:00",
                }
            }
        )

        self.assertEqual(packet["status"], "partial")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["market_state"], "修复")
        self.assertEqual(packet["action_state"], "轻仓验证")
        self.assertEqual(packet["limit_up_count"], 42)
        self.assertEqual(packet["positive_moneyflow_sample_count"], 1)
        self.assertIn("数据缺口", " ".join(packet["risk_notes"]))
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_defensive_market_is_conservative(self):
        packet = market_packet.build_command_center_market_packet(
            {
                "legacy_market_style_fact_packet": {
                    "market_state": "退潮",
                    "risk_switch": "适合防守观察",
                    "limit_up_count": 8,
                    "limit_down_count": 12,
                    "break_limit_count": 10,
                    "break_limit_rate": 0.5,
                    "verified_sources": ["Tushare limit_list_d"],
                }
            }
        )

        self.assertEqual(packet["action_state"], "防守观察")
        self.assertTrue(any("炸板率偏高" in item for item in packet["risk_notes"]))
        self.assertTrue(any("跌停家数偏多" in item for item in packet["risk_notes"]))

    def test_existing_packet_is_preserved_without_mutating_input(self):
        state = {
            "command_center_market_packet": {
                "status": "ready",
                "market_state": "分歧",
                "verified_sources": ["source A"],
                "missing_sources": [],
                "risk_notes": ["note"],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(state)

        packet = market_packet.build_command_center_market_packet(state)

        self.assertEqual(state, original)
        self.assertEqual(packet["market_state"], "分歧")
        self.assertFalse(packet["deepseek_called"])

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_market_packet.py").read_text(encoding="utf-8"))
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
            "command_center_service",
        }

        self.assertTrue(forbidden.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
