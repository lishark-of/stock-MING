import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_etf_packet as etf_packet


class CommandCenterEtfPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = etf_packet.build_command_center_etf_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertFalse(packet["recommended_etfs"])
        self.assertFalse(packet["deepseek_called"])
        self.assertIn("不自动全量发现", packet["summary"])

    def test_allocation_candidates_are_flattened_to_top_three(self):
        state = {
            "legacy_margin_etf_allocation_result": {
                "recommended_margin_ratio": 25,
                "recommended_cash_ratio": 20,
                "selected_etf_candidates": {
                    "科技成长ETF": [
                        {"etf_code": "512480.SH", "etf_name": "半导体 ETF", "total_score": 78},
                        {"etf_code": "560780.SH", "etf_name": "半导体设备ETF广发", "total_score": 74},
                    ],
                    "防守ETF": [
                        {"etf_code": "518880.SH", "etf_name": "黄金 ETF", "total_score": 66},
                        {"etf_code": "511880.SH", "etf_name": "银华日利", "total_score": 60},
                    ],
                },
            },
            "legacy_margin_etf_daily_packet": {
                "updated_at": "2026-06-03T10:00:00",
                "daily_dataset": {"status": "manual_basic_local_config"},
            },
        }

        packet = etf_packet.build_command_center_etf_packet(state)

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["recommended_margin_ratio"], 25)
        self.assertEqual(packet["recommended_cash_ratio"], 20)
        self.assertEqual(len(packet["recommended_etfs"]), 3)
        self.assertEqual(packet["recommended_etfs"][0]["code"], "512480.SH")
        self.assertEqual(packet["recommended_etfs"][0]["bucket"], "科技成长ETF")
        self.assertEqual(packet["recommended_etfs"][0]["status_label"], "只观察不追")
        self.assertTrue(packet["recommended_etfs"][0]["evidence_items"])
        self.assertIn("流动性", "；".join(packet["recommended_etfs"][0]["data_gaps"]))
        self.assertIn("不会自动全量发现", packet["recommended_etfs"][0]["manual_required_text"])
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["cache_state"], "ready")
        self.assertIn("不会自动全量发现", packet["manual_required_text"])
        self.assertFalse(packet["deepseek_called"])

    def test_risk_state_is_conservative_when_current_ratio_exceeds_recommendation(self):
        packet = etf_packet.build_command_center_etf_packet(
            {
                "legacy_margin_etf_allocation_result": {
                    "current_margin_debt_ratio": 30,
                    "recommended_margin_ratio": 20,
                    "selected_etf_candidates": [
                        {"code": "560780.SH", "name": "半导体设备ETF广发", "score": 72},
                    ],
                    "watch_not_chase_etfs": ["半导体 ETF 不追高"],
                }
            }
        )

        self.assertIn("降融资", packet["risk_state"])
        self.assertIn("半导体 ETF 不追高", packet["watch_not_chase"])

    def test_existing_packet_is_normalized_without_mutating_input(self):
        existing = {
            "command_center_etf_packet": {
                "status": "ready",
                "source": "saved",
                "recommended_etfs": [{"etf_code": "159801.SZ", "etf_name": "芯片ETF", "total_score": 70}],
                "watch_not_chase": ["不追高"],
                "risk_notes": ["保持现金缓冲"],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(existing)

        packet = etf_packet.build_command_center_etf_packet(existing)

        self.assertEqual(existing, original)
        self.assertEqual(packet["recommended_etfs"][0]["code"], "159801.SZ")
        self.assertTrue(packet["recommended_etfs"][0]["evidence_items"])
        self.assertIn("不会自动全量发现", packet["manual_required_text"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_score_packet_can_supply_candidates_when_allocation_has_no_selected_items(self):
        packet = etf_packet.build_command_center_etf_packet(
            {
                "legacy_margin_etf_daily_packet": {
                    "score_packet": {
                        "rows": [
                            {"etf_code": "588000.SH", "etf_name": "科创50ETF", "total_score": 68},
                        ]
                    },
                    "daily_dataset": {"status": "manual_basic_local_config"},
                }
            }
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["recommended_etfs"][0]["code"], "588000.SH")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_etf_packet.py").read_text(encoding="utf-8"))
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
