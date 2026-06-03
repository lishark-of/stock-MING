import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_chip_packet as chip_packet


class CommandCenterChipPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = chip_packet.build_command_center_chip_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不会自动请求", packet["summary"])
        self.assertIn("手动刷新", packet["manual_required_text"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_a_share_professional_chip_radar_is_normalized(self):
        state = {
            "a_share_professional_facts": {
                "chip_radar": {
                    "available": True,
                    "trade_date": "20260603",
                    "winner_rate": "72.5",
                    "weight_avg": "23.4",
                    "cost_5pct": "19.8",
                    "cost_50pct": "23.3",
                    "cost_95pct": "27.9",
                    "current_vs_weight_avg_pct": "6.2",
                    "chip_band_width": "14.5",
                    "chip_pressure_comment": "获利盘压力偏高。",
                    "chip_structure_comment": "筹码成本带相对收敛。",
                    "chips_top_areas": [
                        {"price": "23.2", "percent": "12.4"},
                        {"price": "24.1", "percent": "8.1"},
                    ],
                    "updated_at": "2026-06-03T16:00:00",
                }
            }
        }

        packet = chip_packet.build_command_center_chip_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["winner_rate"], 72.5)
        self.assertEqual(packet["weight_avg"], 23.4)
        self.assertEqual(packet["pressure_state"], "获利盘压力偏高")
        self.assertEqual(len(packet["chips_top_areas"]), 2)
        self.assertIn("获利盘比例偏高", " ".join(packet["risk_notes"]))
        self.assertFalse(packet["deepseek_called"])

    def test_facts_item_permission_or_empty_state_stays_missing(self):
        packet = chip_packet.build_command_center_chip_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "chip_radar",
                            "label": "筹码/胜率",
                            "state": "empty_recent",
                            "status": "近期无数据",
                            "api": "cyq_perf/cyq_chips",
                            "risk": "暂未取得可验证筹码/胜率数据。",
                        }
                    ]
                }
            }
        )

        self.assertEqual(packet["status"], "partial")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不能写筹码压力", " ".join(packet["risk_notes"]))

    def test_existing_packet_is_preserved_without_mutating_input(self):
        state = {
            "command_center_chip_packet": {
                "status": "ready",
                "target": "002008.SZ",
                "winner_rate": "55",
                "weight_avg": "22",
                "pressure_state": "中性待验证",
                "summary": "saved",
                "risk_notes": ["风险 A"],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(state)

        packet = chip_packet.build_command_center_chip_packet(state, target="002008.SZ")

        self.assertEqual(state, original)
        self.assertEqual(packet["winner_rate"], 55)
        self.assertEqual(packet["summary"], "saved")
        self.assertFalse(packet["deepseek_called"])

    def test_target_mismatch_ignores_existing_payload(self):
        packet = chip_packet.build_command_center_chip_packet(
            {
                "command_center_chip_packet": {
                    "status": "ready",
                    "target": "002008.SZ",
                    "winner_rate": 60,
                }
            },
            target="000001.SZ",
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_chip_packet.py").read_text(encoding="utf-8"))
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
