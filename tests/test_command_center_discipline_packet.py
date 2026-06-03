import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_discipline_packet as discipline_packet


def _backtest_report(action="继续观察", max_drawdown=-12, win_rate=62):
    return {
        "ticker": "002008.SZ",
        "summary": "规则历史表现可参考。",
        "metrics": {
            "round_trip_win_rate": win_rate,
            "max_drawdown_pct": max_drawdown,
            "sharpe": 1.1,
            "trade_count": 12,
        },
        "latest_signal": {
            "action": action,
            "reason": "趋势站稳且未明显过热",
        },
        "trader_brief": {
            "action": action,
            "warnings": ["高 beta 过热不追"],
            "plain_summary": "当前建议：继续观察。",
        },
        "date_range": {"end": "2026-06-03"},
    }


class CommandCenterDisciplinePacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = discipline_packet.build_command_center_discipline_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertEqual(packet["action_state"], "待刷新")
        self.assertEqual(packet["backtest_status"], "待手动运行回测")
        self.assertEqual(packet["cache_state"], "missing")
        self.assertEqual(packet["metric_items"][0]["value"], "待验证")
        self.assertEqual(packet["evidence_items"][0]["value"], "待刷新")
        self.assertIn("不会自动跑回测", packet["backtest_required_text"])
        self.assertFalse(packet["deepseek_called"])

    def test_cached_backtest_builds_ready_packet(self):
        packet = discipline_packet.build_command_center_discipline_packet(
            {
                "last_backtest_report": _backtest_report(),
                "last_multi_backtest": {"summary": "多参数回测整体稳定；回撤可控。"},
            },
            target="002008.SZ",
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["win_rate"], 62)
        self.assertEqual(packet["max_drawdown"], 12)
        self.assertEqual(packet["trade_count"], 12)
        self.assertEqual(packet["backtest_status"], "已读取回测缓存")
        self.assertEqual(packet["cache_state"], "ready")
        self.assertEqual(packet["date_range"]["end"], "2026-06-03")
        self.assertTrue(any(item["label"] == "胜率" and item["value"] == "62%" for item in packet["metric_items"]))
        self.assertTrue(any(item["label"] == "回测区间" for item in packet["evidence_items"]))
        self.assertIn(packet["action_state"], {"允许小幅试探", "只观察"})
        self.assertTrue(packet["key_rules"])
        self.assertIn("高 beta 过热不追", packet["warnings"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_reduce_signal_or_high_drawdown_is_conservative(self):
        reduce_packet = discipline_packet.build_command_center_discipline_packet(
            {"last_backtest_report": _backtest_report(action="减仓", max_drawdown=-10)},
            target="002008.SZ",
        )
        drawdown_packet = discipline_packet.build_command_center_discipline_packet(
            {"last_backtest_report": _backtest_report(action="继续观察", max_drawdown=-25)},
            target="002008.SZ",
        )

        self.assertEqual(reduce_packet["action_state"], "降风险")
        self.assertEqual(drawdown_packet["action_state"], "降风险")
        self.assertIn("历史最大回撤偏高", " ".join(drawdown_packet["warnings"]))

    def test_target_mismatch_ignores_backtest_report(self):
        packet = discipline_packet.build_command_center_discipline_packet(
            {"last_backtest_report": _backtest_report()},
            target="000001.SZ",
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")

    def test_existing_packet_is_preserved_without_mutating_input(self):
        state = {
            "command_center_discipline_packet": {
                "status": "ready",
                "target": "002008.SZ",
                "summary": "saved",
                "key_rules": ["规则 A"],
                "warnings": ["风险 B"],
                "max_drawdown": 8,
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(state)

        packet = discipline_packet.build_command_center_discipline_packet(state)

        self.assertEqual(state, original)
        self.assertEqual(packet["key_rules"], ["规则 A"])
        self.assertEqual(packet["warnings"], ["风险 B"])
        self.assertTrue(packet["metric_items"])
        self.assertTrue(packet["evidence_items"])
        self.assertFalse(packet["deepseek_called"])

    def test_existing_packet_target_mismatch_is_not_reused(self):
        packet = discipline_packet.build_command_center_discipline_packet(
            {
                "command_center_discipline_packet": {
                    "status": "ready",
                    "target": "002008.SZ",
                    "summary": "old",
                    "key_rules": ["旧标的规则"],
                }
            },
            target="000001.SZ",
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_discipline_packet.py").read_text(encoding="utf-8"))
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
