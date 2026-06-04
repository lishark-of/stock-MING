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
        self.assertEqual(vm["loop_status"]["label"], "证据闭环")
        self.assertEqual(vm["loop_status"]["status"], "partial")
        self.assertEqual(vm["loop_status"]["tone"], "stale")
        self.assertIn("缺失 6", vm["loop_status"]["summary"])
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
        self.assertEqual(vm["radar_card"]["status"], "blocked")
        self.assertEqual(vm["radar_card"]["status_label"], "阻断加仓")
        self.assertIn("低置信度", vm["radar_card"]["confidence_gate"])
        self.assertIn("不能把缺失数据写成利好", vm["radar_card"]["execution_guardrail"])
        self.assertEqual(vm["loop_status"]["status"], "blocked")
        self.assertEqual(vm["loop_status"]["tone"], "failed")
        self.assertEqual(vm["loop_status"]["support_count"], 1)
        self.assertEqual(vm["loop_status"]["blocker_count"], 1)
        self.assertFalse(vm["loop_status"]["deepseek_called"])
        self.assertEqual(vm["loop_status"]["external_call_policy"], "not_triggered")
        core = {item["key"]: item for item in vm["core_evidence_items"]}
        self.assertEqual(list(core), ["dragon_tiger", "margin", "limit_emotion"])
        self.assertEqual(core["dragon_tiger"]["evidence_state"], "blocked")
        self.assertIn("龙虎榜只验证席位行为", core["dragon_tiger"]["guardrail"])
        self.assertEqual(core["dragon_tiger"]["legacy_tab"], "下一票雷达")
        self.assertEqual(core["dragon_tiger"]["writes_packet"], "command_center_dragon_tiger_packet")
        self.assertEqual(core["margin"]["evidence_state"], "cached")
        self.assertIn("融资融券只验证杠杆变化", core["margin"]["guardrail"])
        self.assertEqual(core["limit_emotion"]["evidence_state"], "missing")
        self.assertIn("已刷新 0｜受限 1｜缓存 1｜待验证 1", vm["core_evidence_summary"])
        action_brief = vm["core_evidence_action_brief"]
        self.assertEqual(action_brief["status"], "blocked")
        self.assertEqual(action_brief["headline"], "核心证据阻断加仓")
        self.assertIn("龙虎榜", action_brief["action_summary"])
        brief_items = {item["key"]: item for item in action_brief["items"]}
        self.assertEqual(brief_items["dragon_tiger"]["action_mode"], "block")
        self.assertEqual(brief_items["margin"]["action_label"], "执行前复核")
        self.assertEqual(brief_items["limit_emotion"]["action_mode"], "manual_required")
        self.assertFalse(action_brief["deepseek_called"])
        self.assertFalse(any(item["deepseek_called"] for item in core.values()))
        groups = {item["key"]: item for item in vm["evidence_status_groups"]}
        self.assertEqual(groups["recovered"]["count"], 1)
        self.assertEqual(groups["blocked"]["count"], 1)
        self.assertEqual(groups["cached"]["count"], 1)
        self.assertEqual(groups["manual"]["count"], 3)
        self.assertEqual(groups["recovered"]["items"][0]["writes_packet"], "command_center_moneyflow_packet")
        self.assertIn("缓存只能防白屏", groups["cached"]["summary"])
        self.assertFalse(any(item["deepseek_called"] for item in groups.values()))

    def test_radar_card_marks_cached_or_missing_as_cautious_validation(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "moneyflow_packet": {"status": "ready", "data_status": "ready", "summary": "资金流可用"},
                "margin_packet": {"status": "partial", "data_status": "cached", "summary": "融资缓存"},
            }
        )
        card = vm["radar_card"]

        self.assertEqual(card["status"], "partial")
        self.assertEqual(card["status_label"], "谨慎验证")
        self.assertIn("中低置信度", card["confidence_gate"])
        self.assertIn("不要追高", card["execution_guardrail"])
        self.assertFalse(card["deepseek_called"])

    def test_radar_card_marks_all_ready_as_evidence_chain_ready(self):
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
        card = vm["radar_card"]

        self.assertEqual(card["status"], "ready")
        self.assertEqual(card["status_label"], "可进入证据链")
        self.assertIn("价格纪律", card["execution_guardrail"])
        self.assertEqual(len(card["top_supports"]), 3)
        self.assertEqual(vm["loop_status"]["status"], "ready")
        self.assertEqual(vm["loop_status"]["tone"], "ready")
        self.assertEqual(vm["loop_status"]["support_count"], 6)
        self.assertIn("证据", vm["loop_status"]["manual_note"])
        self.assertIn("已回流：个股资金流、公告/硬风险、融资融券", vm["recovered_evidence_summary"])
        self.assertEqual(vm["core_evidence_summary"], "已刷新 3｜受限 0｜缓存 0｜待验证 0")
        self.assertEqual([item["key"] for item in vm["core_evidence_items"]], ["dragon_tiger", "margin", "limit_emotion"])
        self.assertEqual(vm["recovered_evidence_modules"][0]["label"], "个股资金流")
        self.assertEqual(vm["recovered_evidence_modules"][0]["writes_packet"], "command_center_moneyflow_packet")
        self.assertFalse(vm["recovered_evidence_modules"][0]["deepseek_called"])
        json.dumps(card, ensure_ascii=False)

    def test_recovered_evidence_modules_are_empty_when_no_supporting_packets(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "margin_packet": {"status": "partial", "data_status": "cached", "summary": "融资缓存"},
                "dragon_tiger_packet": {"status": "waiting", "data_status": "missing", "summary": "待查龙虎榜"},
            }
        )

        self.assertEqual(vm["recovered_evidence_modules"], [])
        self.assertIn("暂无已回流", vm["recovered_evidence_summary"])

    def test_core_evidence_action_brief_marks_ready_cached_and_missing_modes(self):
        core_items = [
            {
                "key": "dragon_tiger",
                "label": "龙虎榜",
                "evidence_state": "supporting",
                "tone": "ready",
                "status_label": "已刷新",
                "decision_signal": "龙虎榜可辅助验证。",
                "writes_packet": "command_center_dragon_tiger_packet",
            },
            {
                "key": "margin",
                "label": "融资融券",
                "evidence_state": "cached",
                "tone": "stale",
                "status_label": "使用缓存",
                "writes_packet": "command_center_margin_packet",
            },
            {
                "key": "limit_emotion",
                "label": "涨跌停/情绪",
                "evidence_state": "missing",
                "tone": "missing",
                "status_label": "待验证",
                "writes_packet": "command_center_limit_emotion_packet",
            },
        ]

        brief = evidence_summary.build_core_evidence_action_brief(core_items)
        by_key = {item["key"]: item for item in brief["items"]}

        self.assertEqual(brief["status"], "partial")
        self.assertEqual(brief["headline"], "核心证据仍需复核")
        self.assertIn("融资融券", brief["action_summary"])
        self.assertEqual(by_key["dragon_tiger"]["action_mode"], "support")
        self.assertEqual(by_key["margin"]["action_mode"], "verify_cache")
        self.assertEqual(by_key["limit_emotion"]["action_label"], "待手动补证")
        self.assertEqual(brief["external_call_policy"], "not_triggered")
        self.assertFalse(brief["deepseek_called"])
        json.dumps(brief, ensure_ascii=False)

    def test_latest_chip_recovery_promotes_chip_into_visible_evidence_modules(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "hard_risk_packet": {"status": "ready", "data_status": "ready", "risk_state": "暂无硬风险"},
                "moneyflow_packet": {"status": "ready", "data_status": "ready", "summary": "资金可用"},
                "margin_packet": {"status": "ready", "data_status": "ready", "summary": "融资可用"},
                "dragon_tiger_packet": {"status": "ready", "data_status": "ready", "summary": "龙虎榜可用"},
                "limit_emotion_packet": {"status": "ready", "data_status": "ready", "summary": "情绪可用"},
                "chip_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "pressure_state": "获利盘压力偏高",
                    "winner_rate": 72,
                },
                "latest_recovery_result_notice": {
                    "status": "recovered",
                    "label": "筹码/胜率",
                    "writes_packet": "command_center_chip_packet",
                    "external_call_policy": "button_gated",
                    "deepseek_called": False,
                },
            }
        )

        self.assertEqual(vm["latest_recovery_impact"]["evidence_key"], "chip_radar")
        self.assertEqual(vm["recovered_evidence_modules"][0]["key"], "chip_radar")
        self.assertEqual(vm["recovered_evidence_modules"][0]["label"], "筹码/胜率")
        self.assertEqual(vm["radar_card"]["top_supports"][0]["key"], "chip_radar")
        self.assertIn("已回流：筹码/胜率", vm["recovered_evidence_summary"])
        self.assertFalse(vm["recovered_evidence_modules"][0]["deepseek_called"])

    def test_latest_recovery_result_promotes_recovered_packet_into_radar_card(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "latest_recovery_result_notice": {
                    "status": "recovered",
                    "label": "个股资金流",
                    "message": "个股资金流：可用｜已读取到最近资金流数据。",
                    "writes_packet": "command_center_moneyflow_packet",
                    "external_call_policy": "button_gated",
                    "deepseek_called": False,
                }
            }
        )
        card = vm["radar_card"]

        self.assertEqual(vm["latest_recovery_impact"]["evidence_state"], "supporting")
        self.assertEqual(vm["latest_recovery_impact"]["evidence_key"], "moneyflow")
        self.assertEqual(card["status"], "partial")
        self.assertEqual(card["status_label"], "谨慎验证")
        self.assertIn("最近恢复", card["execution_guardrail"])
        self.assertIn("个股资金流", card["support_text"])
        self.assertFalse(card["latest_recovery_impact"]["deepseek_called"])
        json.dumps(vm, ensure_ascii=False)

    def test_latest_recovery_result_blocks_radar_card_when_recovery_is_restricted(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "latest_recovery_result_notice": {
                    "status": "blocked",
                    "label": "涨跌停/情绪",
                    "message": "涨跌停/情绪：权限不足｜limit_cpt_list 权限不足。",
                    "writes_packet": "command_center_limit_emotion_packet",
                    "external_call_policy": "button_gated",
                    "deepseek_called": False,
                }
            }
        )
        card = vm["radar_card"]

        self.assertEqual(vm["latest_recovery_impact"]["evidence_state"], "blocked")
        self.assertEqual(card["status"], "blocked")
        self.assertEqual(card["status_label"], "阻断加仓")
        self.assertIn("涨跌停/情绪", card["blocker_text"])
        self.assertIn("不能把缺失数据当成利好", card["execution_guardrail"])

    def test_latest_recovery_result_waiting_keeps_radar_card_unverified(self):
        vm = evidence_summary.build_a_share_evidence_radar_view_model(
            {
                "latest_recovery_result_notice": {
                    "status": "waiting",
                    "label": "龙虎榜",
                    "message": "尚未检测到龙虎榜回流结果。",
                    "writes_packet": "command_center_dragon_tiger_packet",
                    "external_call_policy": "not_triggered",
                    "deepseek_called": False,
                }
            }
        )
        card = vm["radar_card"]

        self.assertEqual(vm["latest_recovery_impact"]["evidence_state"], "missing")
        self.assertEqual(card["status"], "partial")
        self.assertIn("龙虎榜", card["recovery_text"])
        self.assertIn("最近恢复", card["execution_guardrail"])

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
        self.assertIn("workspace_mode_v2", dumped)
        self.assertIn("legacy_workspace_selected_tab", dumped)
        self.assertIn("天眼风控", dumped)
        for item in actions:
            self.assertEqual(item["manual_action"]["refresh_policy"], "button_gated")
            self.assertEqual(item["refresh_policy"], "button_gated")
            self.assertEqual(item["workspace_target"], "高级工具箱（旧版保留）")
            self.assertTrue(item["legacy_tab"])
            self.assertIn("主导航切到高级工具箱", item["navigation_label"])
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
        self.assertEqual(actions[0]["legacy_tab"], "天眼风控")
        self.assertEqual(actions[0]["legacy_tab_state_key"], "legacy_workspace_selected_tab")
        self.assertEqual(actions[0]["writes_packet"], "command_center_hard_risk_packet")
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
