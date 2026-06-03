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
        self.assertEqual(vm["decision_summary"], "支持 0｜阻断 0｜缓存 0｜缺失 6")
        self.assertEqual(vm["decision_evidence_queue"][0]["priority"], 1)
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
        self.assertEqual(vm["decision_summary"], "支持 1｜阻断 1｜缓存 1｜缺失 3")
        self.assertEqual(by_key["moneyflow"]["headline"], "主力净流入")
        self.assertEqual(by_key["moneyflow"]["metric"], "+1.25亿")
        self.assertEqual(by_key["moneyflow"]["evidence_state"], "supporting")
        self.assertIn("资金", by_key["moneyflow"]["decision_role"])
        self.assertEqual(by_key["dragon_tiger"]["tone"], "failed")
        self.assertEqual(by_key["dragon_tiger"]["evidence_state"], "blocked")
        self.assertIn("不能支撑加仓", by_key["dragon_tiger"]["decision_signal"])
        self.assertEqual(by_key["margin"]["status_label"], "使用缓存")
        self.assertEqual(by_key["margin"]["evidence_label"], "缓存证据")
        self.assertFalse(any(item["deepseek_called"] for item in vm["items"]))

    def test_decision_evidence_queue_orders_priority_and_blockers_first(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "moneyflow_packet": {"status": "ready", "data_status": "ready", "summary": "资金流可用"},
                "hard_risk_packet": {"status": "failed", "data_status": "missing", "summary": "公告权限不足"},
                "margin_packet": {"status": "partial", "data_status": "cached", "summary": "融资缓存"},
            }
        )
        queue = vm["decision_evidence_queue"]

        self.assertEqual(queue[0]["key"], "hard_risk")
        self.assertEqual(queue[0]["priority"], 1)
        self.assertEqual(queue[0]["evidence_state"], "blocked")
        self.assertEqual(queue[1]["key"], "moneyflow")
        self.assertIn("硬风险", vm["blocker_items"][0]["label"])

    def test_next_evidence_actions_explain_manual_packet_backfill(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "moneyflow_packet": {"status": "ready", "data_status": "ready", "summary": "资金流可用"},
                "hard_risk_packet": {"status": "failed", "data_status": "missing", "summary": "公告权限不足"},
                "margin_packet": {"status": "partial", "data_status": "cached", "summary": "融资缓存"},
                "dragon_tiger_packet": {"status": "waiting", "data_status": "missing", "summary": "待查龙虎榜"},
            }
        )
        actions = vm["next_evidence_actions"]
        dumped = json.dumps(actions, ensure_ascii=False)

        self.assertEqual(actions[0]["key"], "hard_risk")
        self.assertNotIn("moneyflow", {item["key"] for item in actions})
        self.assertIn("高级工具箱", dumped)
        self.assertIn("command_center_hard_risk_packet", dumped)
        self.assertIn("command_center_margin_packet", dumped)
        for item in actions:
            self.assertEqual(item["manual_action"]["refresh_policy"], "button_gated")
            self.assertFalse(item["manual_action"]["deepseek_called"])
            self.assertFalse(item["deepseek_called"])

    def test_home_backfill_actions_filter_to_runnable_button_gated_items(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "hard_risk_packet": {"status": "failed", "data_status": "missing", "summary": "公告权限不足"},
                "margin_packet": {"status": "partial", "data_status": "cached", "summary": "融资缓存"},
                "dragon_tiger_packet": {"status": "waiting", "data_status": "missing", "summary": "待查龙虎榜"},
                "chip_packet": {"status": "waiting", "data_status": "missing", "summary": "待查筹码"},
            }
        )
        actions = evidence_summary.build_home_evidence_backfill_actions(
            vm,
            runnable_keys={"margin", "dragon_tiger", "chip_radar"},
            limit=2,
        )

        self.assertEqual([item["key"] for item in actions], ["margin", "chip_radar"])
        self.assertNotIn("hard_risk", {item["key"] for item in actions})
        for item in actions:
            self.assertEqual(item["manual_action"]["refresh_policy"], "button_gated")
            self.assertFalse(item["deepseek_called"])

    def test_home_backfill_actions_can_include_hard_risk_manual_check(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "hard_risk_packet": {"status": "failed", "data_status": "missing", "summary": "公告权限不足"},
                "margin_packet": {"status": "partial", "data_status": "cached", "summary": "融资缓存"},
            }
        )
        actions = evidence_summary.build_home_evidence_backfill_actions(
            vm,
            runnable_keys={"hard_risk", "margin"},
            limit=2,
        )

        self.assertEqual(actions[0]["key"], "hard_risk")
        self.assertIn("检测公告/硬风险", actions[0]["manual_action"]["button_label"])
        self.assertEqual(actions[0]["manual_action"]["writes_packet"], "command_center_hard_risk_packet")
        self.assertEqual(actions[0]["manual_action"]["refresh_policy"], "button_gated")
        self.assertFalse(actions[0]["deepseek_called"])

    def test_home_evidence_recovery_summary_names_priority_action_and_packets(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "hard_risk_packet": {"status": "failed", "data_status": "missing", "summary": "公告权限不足"},
                "margin_packet": {"status": "partial", "data_status": "cached", "summary": "融资缓存"},
            }
        )
        summary = evidence_summary.build_home_evidence_recovery_summary(
            vm,
            runnable_keys={"hard_risk", "margin"},
            limit=2,
        )
        dumped = json.dumps(summary, ensure_ascii=False)

        self.assertEqual(summary["status"], "needs_recovery")
        self.assertIn("补齐关键 A股证据", summary["title"])
        self.assertEqual(summary["primary_label"], "公告/硬风险")
        self.assertIn("检测公告/硬风险", dumped)
        self.assertIn("command_center_hard_risk_packet", dumped)
        self.assertIn("DeepSeek", summary["summary"])
        self.assertFalse(summary["deepseek_called"])

    def test_home_evidence_recovery_summary_is_ready_when_no_actions(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "hard_risk_packet": {"status": "ready", "data_status": "ready", "risk_state": "暂无硬风险"},
                "moneyflow_packet": {"status": "ready", "data_status": "ready", "summary": "资金可用"},
                "margin_packet": {"status": "ready", "data_status": "ready", "summary": "融资可用"},
                "dragon_tiger_packet": {"status": "ready", "data_status": "ready", "summary": "龙虎榜可用"},
                "limit_emotion_packet": {"status": "ready", "data_status": "ready", "summary": "情绪可用"},
                "chip_packet": {"status": "ready", "data_status": "ready", "summary": "筹码可用"},
            }
        )
        summary = evidence_summary.build_home_evidence_recovery_summary(vm)

        self.assertEqual(summary["status"], "ready")
        self.assertEqual(summary["actions"], [])
        self.assertFalse(summary["deepseek_called"])

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
