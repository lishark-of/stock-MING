import ast
import json
import unittest
from pathlib import Path

import command_center_legacy_packet_sync as sync


class CommandCenterLegacyPacketSyncTests(unittest.TestCase):
    def test_quant_sync_prefers_latest_legacy_result_over_existing_packet(self):
        packet = sync.sync_legacy_quant_packet(
            {
                "command_center_quant_packet": {
                    "status": "ready",
                    "score": 10,
                    "summary": "旧 packet",
                    "target": "002008.SZ",
                },
                "legacy_quant_result": {
                    "status": "completed",
                    "generated_at": "2026-06-03T10:00:00",
                    "target": "002008.SZ",
                    "market_type": "A股",
                    "score": 68,
                    "direction": "偏积极但需验证",
                    "summary": "最新旧版量化结果。",
                },
            },
            target="002008.SZ",
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["score"], 68)
        self.assertEqual(packet["summary"], "最新旧版量化结果。")
        self.assertEqual(packet["data_status"], "ready")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_discipline_sync_prefers_latest_backtest_over_existing_packet(self):
        packet = sync.sync_legacy_discipline_packet(
            {
                "command_center_discipline_packet": {
                    "status": "ready",
                    "summary": "旧纪律 packet",
                    "win_rate": 12,
                    "target": "002008.SZ",
                },
                "last_backtest_report": {
                    "ticker": "002008.SZ",
                    "summary": "最新回测缓存已生成。",
                    "source": "yfinance",
                    "date_range": {"start": "2025-01-01", "end": "2026-06-03"},
                    "metrics": {"win_rate": 62, "max_drawdown": -12, "sharpe": 1.1, "trade_count": 18},
                    "latest_signal": {"action": "继续观察", "reason": "趋势未破坏。"},
                },
                "last_multi_backtest": {"summary": "多模式整体稳定。"},
            },
            target="002008.SZ",
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["summary"], "最新回测缓存已生成。")
        self.assertEqual(packet["win_rate"], 62)
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["updated_at"], "2026-06-03")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_sync_helpers_do_not_mutate_input_state(self):
        state = {
            "command_center_quant_packet": {"status": "ready", "score": 10},
            "legacy_quant_result": {"status": "completed", "score": 70},
        }
        before = json.dumps(state, ensure_ascii=False, sort_keys=True)

        sync.sync_legacy_quant_packet(state)

        after = json.dumps(state, ensure_ascii=False, sort_keys=True)
        self.assertEqual(after, before)

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_legacy_packet_sync.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        forbidden = {
            "streamlit",
            "app",
            "data_fetcher",
            "tushare_adapter",
            "akshare",
            "yfinance",
            "openai",
            "backtester",
            "command_center_service",
        }
        self.assertFalse(forbidden.intersection(imports))


if __name__ == "__main__":
    unittest.main()
