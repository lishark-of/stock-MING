import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_quant_packet as quant_packet


def _backtest_report():
    return {
        "ticker": "002008.SZ",
        "summary": "回测缓存显示趋势纪律可参考。",
        "metrics": {
            "round_trip_win_rate": 62,
            "max_drawdown_pct": -12,
        },
    }


class CommandCenterQuantPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = quant_packet.build_command_center_quant_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertEqual(packet["action_state"], "待刷新")
        self.assertIn("手动触发", packet["manual_required_text"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_legacy_quant_result_is_normalized(self):
        state = {
            "legacy_quant_result": {
                "status": "completed",
                "generated_at": "2026-06-03T10:00:00",
                "target": "002008.SZ",
                "market_type": "A股",
                "score": 68,
                "direction": "偏积极但需验证",
                "summary": "轻量量化摘要已生成。",
                "source": "综合推演中心轻量摘要",
                "deepseek_called": True,
            },
            "last_backtest_report": _backtest_report(),
        }

        packet = quant_packet.build_command_center_quant_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["score"], 68)
        self.assertEqual(packet["direction"], "偏积极但需验证")
        self.assertEqual(packet["action_state"], "轻仓验证")
        self.assertIn(packet["confidence"], {"低", "中"})
        self.assertIn("回测缓存", packet["backtest_reference"])
        self.assertFalse(packet["deepseek_called"])

    def test_defensive_quant_result_stays_conservative(self):
        packet = quant_packet.build_command_center_quant_packet(
            {
                "legacy_quant_result": {
                    "status": "completed",
                    "score": 45,
                    "direction": "偏防守",
                    "summary": "风险偏高。",
                }
            }
        )

        self.assertEqual(packet["action_state"], "防守观察")
        self.assertEqual(packet["confidence"], "低")
        self.assertIn("缺少回测缓存", " ".join(packet["risk_notes"]))

    def test_existing_packet_is_preserved_without_mutating_input(self):
        state = {
            "command_center_quant_packet": {
                "status": "ready",
                "target": "002008.SZ",
                "summary": "saved",
                "score": "66",
                "direction": "轻仓验证",
                "evidence_items": ["证据 A"],
                "risk_notes": ["风险 B"],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(state)

        packet = quant_packet.build_command_center_quant_packet(state, target="002008.SZ")

        self.assertEqual(state, original)
        self.assertEqual(packet["score"], 66)
        self.assertEqual(packet["evidence_items"], ["证据 A"])
        self.assertEqual(packet["risk_notes"], ["风险 B"])
        self.assertFalse(packet["deepseek_called"])

    def test_target_mismatch_ignores_legacy_quant_result(self):
        packet = quant_packet.build_command_center_quant_packet(
            {
                "legacy_quant_result": {
                    "status": "completed",
                    "target": "002008.SZ",
                    "score": 68,
                }
            },
            target="000001.SZ",
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_quant_packet.py").read_text(encoding="utf-8"))
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
