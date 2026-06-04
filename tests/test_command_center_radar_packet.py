import ast
import json
import unittest
from pathlib import Path

import command_center_radar_packet as radar


class CommandCenterRadarPacketTests(unittest.TestCase):
    def test_builds_top_three_candidates_from_scan_cache(self):
        packet = radar.build_command_center_radar_packet(
            {
                "radar_scan_status": "completed",
                "radar_scan_results": {
                    "generated_at": "2026-06-03T10:00:00",
                    "rule_rows": [
                        {
                            "candidate": {"ticker": "300750.SZ", "name": "宁德时代"},
                            "score": {
                                "total_score": 82,
                                "battle_state": "等验证",
                                "battle_state_reason": "趋势较强但等待量能确认。",
                                "trigger_conditions": ["放量站稳 MA20", "行业强于指数"],
                                "invalid_conditions": ["跌破 MA20", "资金流转弱"],
                            },
                            "candidate_context": {"scan_source": "手动候选池"},
                        },
                        {"candidate": {"ticker": "512480.SH", "name": "半导体 ETF"}, "score": {"total_score": 76, "battle_state": "只观察"}},
                        {"candidate": {"ticker": "600519.SH", "name": "贵州茅台"}, "score": {"total_score": 69, "battle_state": "暂不纳入"}},
                        {"candidate": {"ticker": "000001.SZ", "name": "平安银行"}, "score": {"total_score": 50, "battle_state": "暂不纳入"}},
                    ],
                    "summary": {"note": "规则雷达缓存展示。", "deepseek_called": False},
                },
            }
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["display_count"], 3)
        self.assertEqual(packet["top_candidates"][0]["ticker"], "300750.SZ")
        self.assertEqual(packet["top_candidates"][0]["status_label"], "等验证")
        self.assertEqual(packet["top_candidates"][0]["tone"], "stale")
        self.assertEqual(packet["top_candidates"][0]["trigger_condition"], "放量站稳 MA20；行业强于指数")
        self.assertEqual(packet["top_candidates"][0]["invalidation_condition"], "跌破 MA20；资金流转弱")
        self.assertTrue(packet["top_candidates"][0]["evidence_items"])
        self.assertIn("不会自动全市场扫描", packet["top_candidates"][0]["manual_required_text"])
        self.assertIn("不会自动全市场扫描", packet["manual_required_text"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_waiting_packet_when_cache_missing(self):
        packet = radar.build_command_center_radar_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["top_candidates"], [])
        self.assertIn("不会自动全市场扫描", packet["summary"])
        self.assertEqual(packet["cache_state"], "missing")
        self.assertFalse(packet["deepseek_called"])

    def test_builds_from_top_candidates_cache_shape(self):
        packet = radar.build_command_center_radar_packet(
            {
                "radar_scan_results": {
                    "generated_at": "2026-06-03T10:00:00",
                    "top_candidates": [
                        {
                            "ticker": "300750.SZ",
                            "name": "宁德时代",
                            "score": 82,
                            "action_state": "等验证",
                            "trigger_condition": "放量站稳 MA20",
                            "invalidation_condition": "跌破 MA20",
                        }
                    ],
                    "summary": {"source_mode": "下一票雷达本地缓存", "deepseek_called": False},
                },
            }
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["display_count"], 1)
        self.assertEqual(packet["top_candidates"][0]["ticker"], "300750.SZ")
        self.assertEqual(packet["top_candidates"][0]["status_label"], "等验证")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_existing_packet_is_preserved_without_mutation(self):
        existing = {
            "status": "ready",
            "top_candidates": [{"ticker": "A", "name": "Alpha"}],
            "deepseek_called": False,
        }
        state = {"command_center_radar_packet": existing}
        packet = radar.build_command_center_radar_packet(state)

        self.assertIsNot(packet, existing)
        self.assertEqual(packet["top_candidates"][0]["ticker"], "A")
        self.assertEqual(existing, state["command_center_radar_packet"])

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_radar_packet.py").read_text(encoding="utf-8"))
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
