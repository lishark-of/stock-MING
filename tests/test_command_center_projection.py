import ast
import json
import unittest
from pathlib import Path

import command_center_projection as projection


FORBIDDEN_IMPORTS = {
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


class CommandCenterProjectionTests(unittest.TestCase):
    def test_missing_data_outputs_waiting_fallback(self):
        packet = projection.build_projection_packet(now="2026-06-01T09:30:00")

        self.assertEqual(packet["status"], "waiting")
        self.assertTrue(packet["is_fallback"])
        self.assertIn("示例路径", packet["note"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_generates_three_paths(self):
        packet = projection.build_projection_packet(
            decision_packet={
                "status": "ready",
                "overall_action": "小幅进攻",
                "risk_level": "中",
                "market_bias": "偏强",
                "updated_at": "2026-06-01T09:30:00",
            },
            strategy_packet={
                "status": "ready",
                "action": "小幅试探",
                "confidence": "中",
            },
            now="2026-06-01T09:30:00",
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(len(packet["paths"]), 3)
        self.assertEqual([path["name"] for path in packet["paths"]], ["乐观路径", "中性路径", "谨慎路径"])

    def test_each_path_has_probability_points_action_and_trigger(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "等待", "updated_at": "2026-06-01T09:30:00"},
            strategy_packet={
                "next_5_10_day_paths": [
                    {"name": "乐观路径", "condition": "放量突破", "action": "小额试探"},
                    {"name": "中性路径", "condition": "继续横盘", "action": "只观察"},
                    {"name": "谨慎路径", "condition": "跌破纪律线", "action": "降风险"},
                ]
            },
        )

        for path in packet["paths"]:
            self.assertIn("probability", path)
            self.assertIn("points", path)
            self.assertIn("action", path)
            self.assertIn("trigger", path)
            self.assertTrue(path["points"])
            self.assertEqual(path["points"][0]["t"], 0)

    def test_deepseek_called_is_always_false_for_projection_build(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察", "deepseek_called": True},
            strategy_packet={"action": "等待", "deepseek_called": True},
        )

        self.assertFalse(packet["deepseek_called"])

    def test_horizon_days_is_clamped_to_five_to_ten(self):
        short = projection.build_projection_packet(horizon_days=3)
        long = projection.build_projection_packet(horizon_days=30)

        self.assertEqual(short["horizon_days"], 5)
        self.assertEqual(long["horizon_days"], 10)
        self.assertEqual(long["paths"][0]["points"][-1]["t"], 10)

    def test_cached_status_from_stale_home_snapshot(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察"},
            home_snapshot={"data_freshness": {"state": "stale"}, "timestamp": "2026-05-31T10:00:00"},
        )

        self.assertEqual(packet["status"], "cached")

    def test_fallback_tolerates_non_mapping_inputs(self):
        packet = projection.build_projection_packet(
            decision_packet=object(),
            strategy_packet=object(),
            live_packet=object(),
            home_snapshot=object(),
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(len(packet["historical"]), 11)
        self.assertEqual(len(packet["paths"]), 3)

    def test_build_from_state_reads_cached_packets(self):
        packet = projection.build_projection_packet_from_state(
            {
                "command_center_decision_packet": {"overall_action": "降风险", "updated_at": "2026-06-01T10:00:00"},
                "strategy_execution_packet": {"action": "降风险", "confidence": "低"},
            }
        )

        self.assertEqual(packet["status"], "ready")
        self.assertGreater(packet["paths"][2]["probability"], packet["paths"][0]["probability"])

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_projection.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_projection.py: {name}")


if __name__ == "__main__":
    unittest.main()
