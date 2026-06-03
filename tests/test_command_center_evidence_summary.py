import ast
import json
import unittest
from pathlib import Path

import command_center_evidence_summary as evidence_summary


class CommandCenterEvidenceSummaryTests(unittest.TestCase):
    def test_missing_snapshot_builds_waiting_radar(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model({})

        self.assertEqual(len(vm["items"]), 6)
        self.assertEqual(vm["ready_count"], 0)
        self.assertEqual(vm["missing_count"], 6)
        self.assertIn("待验证 6 项", vm["summary"])
        self.assertFalse(vm["deepseek_called"])
        json.dumps(vm, ensure_ascii=False)

    def test_ready_and_failed_packets_are_summarized(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "moneyflow_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "flow_state": "主力净流入",
                    "five_day_main_net_yi": 1.25,
                    "risk_notes": ["资金流只作验证线索。"],
                    "source": "Tushare moneyflow 缓存",
                    "updated_at": "2026-06-03T10:00:00",
                },
                "dragon_tiger_packet": {
                    "status": "failed",
                    "data_status": "missing",
                    "activity_state": "近期无上榜或不可用",
                    "risk_notes": ["近期无龙虎榜记录不等于机构支持。"],
                },
                "margin_packet": {
                    "status": "partial",
                    "data_status": "cached",
                    "leverage_state": "杠杆余额可参考",
                    "financing_balance_yi": 12.3,
                },
            }
        )
        by_key = {item["key"]: item for item in vm["items"]}

        self.assertEqual(vm["ready_count"], 1)
        self.assertEqual(vm["cached_count"], 1)
        self.assertEqual(vm["failed_count"], 1)
        self.assertEqual(by_key["moneyflow"]["headline"], "主力净流入")
        self.assertEqual(by_key["moneyflow"]["metric"], "+1.25亿")
        self.assertEqual(by_key["dragon_tiger"]["tone"], "failed")
        self.assertEqual(by_key["margin"]["status_label"], "使用缓存")
        self.assertFalse(any(item["deepseek_called"] for item in vm["items"]))

    def test_limit_and_chip_specific_headlines_are_visible(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "limit_emotion_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "emotion_state": "接近涨停/追高区",
                    "distance_to_up_pct": 2.1,
                },
                "chip_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "pressure_state": "获利盘压力偏高",
                    "winner_rate": 72,
                },
            }
        )
        by_key = {item["key"]: item for item in vm["items"]}

        self.assertEqual(by_key["limit_emotion"]["headline"], "接近涨停/追高区")
        self.assertEqual(by_key["chip_radar"]["headline"], "获利盘压力偏高")
        self.assertEqual(by_key["chip_radar"]["metric"], "72.00%")

    def test_hard_risk_packet_headline_and_count_are_visible(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "hard_risk_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "risk_state": "风险线索存在",
                    "risk_item_count": 2,
                    "risk_notes": ["公告标题线索涉及：减持。"],
                    "source": "Tushare 硬风险缓存",
                    "updated_at": "2026-06-03T10:00:00",
                },
            }
        )
        by_key = {item["key"]: item for item in vm["items"]}

        self.assertEqual(by_key["hard_risk"]["headline"], "风险线索存在")
        self.assertEqual(by_key["hard_risk"]["metric"], "2项")
        self.assertIn("减持", by_key["hard_risk"]["risk_text"])
        self.assertFalse(by_key["hard_risk"]["deepseek_called"])

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_evidence_summary.py").read_text(encoding="utf-8"))
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
