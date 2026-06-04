import ast
import json
import unittest
from pathlib import Path

import command_center_data_health_ledger as ledger


FORBIDDEN_IMPORTS = {
    "streamlit",
    "app",
    "tushare_adapter",
    "tushare",
    "akshare",
    "yfinance",
    "data_fetcher",
    "backtester",
    "openai",
    "command_center_service",
}


class CommandCenterDataHealthLedgerTests(unittest.TestCase):
    def test_empty_ledger_is_safe_and_manual(self):
        packet = ledger.build_data_health_ledger()

        self.assertEqual(packet["status"], "missing")
        self.assertEqual(packet["rows"], [])
        self.assertIn("不会自动请求外部接口", packet["summary"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_ledger_tracks_interface_state_next_action_and_packet_target(self):
        packet = ledger.build_data_health_ledger(
            data_capability_packet={
                "source": "Unified data capability",
                "checked_at": "2026-06-03T10:00:00",
                "items": [
                    {
                        "provider": "Tushare",
                        "api": "moneyflow",
                        "label": "个股资金流",
                        "capability_state": "available",
                        "status": "可用",
                        "latest_date": "20260603",
                    },
                    {
                        "provider": "Tushare",
                        "api": "margin_detail",
                        "label": "融资融券",
                        "capability_state": "permission_denied",
                        "status": "权限不足",
                        "error": "抱歉，您没有访问该接口的权限",
                    },
                    {
                        "provider": "AkShare",
                        "api": "akshare_manual_refresh",
                        "label": "AkShare 重型刷新",
                        "capability_state": "requires_manual_refresh",
                        "status": "需要手动刷新",
                    },
                ],
            },
            recovery_actions=[
                {
                    "provider": "Tushare",
                    "api": "margin_detail",
                    "label": "融资融券",
                    "action_label": "手动刷新融资融券",
                    "writes_packet": "command_center_margin_packet",
                    "toolbox_entry": "高级工具箱 / 融资 ETF / 融资融券",
                    "diagnostic_answer": "融资融券权限不足；接口接入成功不等于当前账户有权限。",
                    "refresh_policy": "button_gated",
                }
            ],
        )
        rows = {row["label"]: row for row in packet["rows"]}

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["available_count"], 1)
        self.assertEqual(packet["blocked_count"], 1)
        self.assertEqual(packet["manual_count"], 1)
        self.assertEqual(rows["个股资金流"]["last_success_text"], "20260603")
        self.assertEqual(rows["融资融券"]["writes_packet"], "command_center_margin_packet")
        self.assertEqual(rows["融资融券"]["action_label"], "手动刷新融资融券")
        self.assertIn("权限不足", rows["融资融券"]["meaning"])
        self.assertEqual(rows["融资融券"]["root_cause_code"], "permission_scope")
        self.assertEqual(rows["融资融券"]["root_cause_label"], "接口权限/积分")
        self.assertIn("单独权限/积分", rows["融资融券"]["why_previous_full_not_enough"])
        self.assertEqual(rows["AkShare 重型刷新"]["refresh_policy"], "button_gated")
        self.assertTrue(any(group["code"] == "permission_scope" for group in packet["root_cause_groups"]))
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_ledger_dedupes_capability_and_issue_items(self):
        packet = ledger.build_data_health_ledger(
            data_capability_packet={
                "items": [
                    {"provider": "Tushare", "api": "top_list", "label": "龙虎榜", "capability_state": "empty_recent", "status": "近期无数据"},
                ]
            },
            data_issue_explainer={
                "items": [
                    {"provider": "Tushare", "api": "top_list", "label": "龙虎榜", "state": "empty_recent", "status_label": "近期无数据"},
                ]
            },
        )

        self.assertEqual(len(packet["rows"]), 1)
        self.assertEqual(packet["rows"][0]["label"], "龙虎榜")
        self.assertEqual(packet["rows"][0]["state"], "empty_recent")
        self.assertIn("标的", packet["rows"][0]["meaning"])

    def test_impact_summary_turns_blocked_rows_into_decision_guardrail(self):
        packet = ledger.build_data_health_ledger(
            data_capability_packet={
                "items": [
                    {"provider": "Tushare", "api": "margin_detail", "label": "融资融券", "capability_state": "permission_denied", "status": "权限不足"},
                    {"provider": "Tushare", "api": "top_list", "label": "龙虎榜", "capability_state": "empty_recent", "status": "近期无数据"},
                ]
            }
        )

        impact = ledger.build_data_health_impact_summary(packet)

        self.assertEqual(impact["status"], "blocked")
        self.assertEqual(impact["label"], "阻断加仓")
        self.assertIn("融资融券", impact["summary"])
        self.assertIn("不能把缺失数据当成利好", impact["decision_impact"])
        self.assertIn("观察/小额试探", impact["strategy_action"])
        self.assertFalse(impact["deepseek_called"])

    def test_impact_summary_filters_rows_by_market_type(self):
        packet = ledger.build_data_health_ledger(
            data_capability_packet={
                "items": [
                    {"provider": "Tushare", "api": "moneyflow", "label": "个股资金流", "capability_state": "permission_denied", "status": "权限不足"},
                    {"provider": "yfinance", "api": "yfinance_market_data", "label": "美股行情", "capability_state": "requires_manual_refresh", "status": "需要手动刷新"},
                ]
            }
        )

        us_impact = ledger.build_data_health_impact_summary(packet, market_type="美股")
        a_share_impact = ledger.build_data_health_impact_summary(packet, market_type="A股")

        self.assertEqual(us_impact["status"], "partial")
        self.assertIn("美股行情", us_impact["summary"])
        self.assertNotIn("个股资金流", us_impact["summary"])
        self.assertEqual(a_share_impact["status"], "blocked")
        self.assertIn("个股资金流", a_share_impact["summary"])

    def test_visibility_summary_explains_why_tushare_still_has_gaps(self):
        packet = ledger.build_data_health_ledger(
            data_capability_packet={
                "items": [
                    {"provider": "Tushare", "api": "moneyflow", "label": "个股资金流", "capability_state": "available", "status": "可用"},
                    {"provider": "Tushare", "api": "margin_detail", "label": "融资融券", "capability_state": "permission_denied", "status": "权限不足"},
                    {"provider": "Tushare", "api": "limit_cpt_list", "label": "涨跌停/情绪", "capability_state": "disabled_this_session", "status": "本会话跳过"},
                    {"provider": "Tushare", "api": "top_list", "label": "龙虎榜", "capability_state": "empty_recent", "status": "近期无数据"},
                    {"provider": "Tushare", "api": "cyq_perf", "label": "筹码/胜率", "capability_state": "stale_cache", "status": "使用缓存"},
                ]
            }
        )

        summary = ledger.build_data_health_visibility_summary(packet)
        dumped = json.dumps(summary, ensure_ascii=False)

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("Tushare 拉满", summary["headline"])
        self.assertIn("token 或基础行情可用", summary["explanation"])
        self.assertIn("融资融券", summary["permission_labels"])
        self.assertIn("涨跌停/情绪", summary["skipped_labels"])
        self.assertIn("筹码/胜率", summary["cache_labels"])
        self.assertIn("龙虎榜", summary["empty_labels"])
        self.assertEqual(summary["recovery_actions"][0]["label"], "融资融券")
        self.assertEqual(summary["recovery_actions"][0]["legacy_tab"], "融资 ETF")
        self.assertEqual(summary["recovery_actions"][0]["writes_packet"], "command_center_margin_packet")
        self.assertEqual(summary["recovery_actions"][0]["refresh_policy"], "button_gated")
        self.assertTrue(summary["recovery_actions"][0]["manual_check_available"])
        self.assertEqual(summary["recovery_actions"][0]["manual_check_key"], "margin")
        self.assertEqual(summary["recovery_actions"][0]["manual_check_button_label"], "手动检测融资融券")
        self.assertIn("只检测 margin_detail", summary["recovery_actions"][0]["manual_check_instruction"])
        self.assertEqual(summary["recovery_actions"][0]["legacy_workspace_route"]["legacy_tab"], "融资 ETF")
        self.assertEqual(summary["items"][0]["manual_check_key"], "margin")
        self.assertEqual(summary["items"][0]["legacy_workspace_route"]["writes_packet"], "command_center_margin_packet")
        self.assertEqual(summary["items"][0]["root_cause_code"], "permission_scope")
        self.assertIn("单独权限/积分", summary["items"][0]["why_previous_full_not_enough"])
        cause_groups = {item["code"]: item for item in summary["root_cause_groups"]}
        self.assertEqual(cause_groups["permission_scope"]["count"], 1)
        self.assertEqual(cause_groups["permission_scope"]["tone"], "failed")
        self.assertEqual(cause_groups["session_skip"]["count"], 1)
        self.assertEqual(cause_groups["session_skip"]["tone"], "failed")
        self.assertEqual(cause_groups["publish_window"]["count"], 1)
        self.assertEqual(cause_groups["publish_window"]["tone"], "stale")
        self.assertEqual(cause_groups["cache_guard"]["count"], 1)
        self.assertEqual(cause_groups["cache_guard"]["tone"], "stale")
        self.assertIn("手动执行后回流 command_center_margin_packet", summary["recovery_actions"][0]["navigation_label"])
        self.assertEqual(summary["external_call_policy"], "not_triggered")
        self.assertFalse(summary["deepseek_called"])
        self.assertIn("command_center_margin_packet", dumped)

    def test_health_timeline_explains_success_failure_cache_and_manual_routes(self):
        packet = ledger.build_data_health_ledger(
            data_capability_packet={
                "checked_at": "2026-06-04T10:00:00",
                "items": [
                    {"provider": "Tushare", "api": "moneyflow", "label": "个股资金流", "capability_state": "available", "status": "可用", "latest_date": "20260603"},
                    {"provider": "Tushare", "api": "margin_detail", "label": "融资融券", "capability_state": "permission_denied", "status": "权限不足", "error": "抱歉，您没有访问该接口的权限"},
                    {"provider": "Tushare", "api": "top_list", "label": "龙虎榜", "capability_state": "empty_recent", "status": "近期无数据"},
                    {"provider": "AkShare", "api": "akshare_manual_refresh", "label": "AkShare 重型刷新", "capability_state": "requires_manual_refresh", "status": "需要手动刷新"},
                ],
            }
        )

        timeline = ledger.build_data_health_timeline(packet)
        dumped = json.dumps(timeline, ensure_ascii=False)
        by_label = {item["label"]: item for item in timeline["items"]}

        self.assertEqual(timeline["status"], "blocked")
        self.assertEqual(timeline["headline"], "最近失败优先处理")
        self.assertIn("最近失败 1", timeline["summary"])
        self.assertEqual(by_label["融资融券"]["event_type"], "last_failure")
        self.assertIn("权限", by_label["融资融券"]["message"])
        self.assertEqual(by_label["融资融券"]["root_cause_code"], "permission_scope")
        self.assertIn("单独权限/积分", by_label["融资融券"]["why_previous_full_not_enough"])
        self.assertEqual(by_label["融资融券"]["writes_packet"], "command_center_margin_packet")
        self.assertEqual(by_label["个股资金流"]["event_type"], "last_success")
        self.assertEqual(by_label["个股资金流"]["last_success"], "20260603")
        self.assertEqual(by_label["龙虎榜"]["event_type"], "empty_recent")
        self.assertEqual(by_label["AkShare 重型刷新"]["event_type"], "manual_required")
        self.assertEqual(by_label["融资融券"]["external_call_policy"], "not_triggered")
        self.assertFalse(timeline["deepseek_called"])
        self.assertIn("高级工具箱", dumped)

    def test_limit_boundary_apis_route_to_limit_emotion_recovery_packet(self):
        packet = ledger.build_data_health_ledger(
            data_capability_packet={
                "items": [
                    {"provider": "Tushare", "api": "stk_limit", "label": "涨跌停价格边界", "capability_state": "empty_recent", "status": "近期无数据"},
                    {"provider": "Tushare", "api": "limit_list_d", "label": "涨跌停明细", "capability_state": "permission_denied", "status": "权限不足"},
                    {"provider": "Tushare", "api": "limit_cpt_list", "label": "概念涨跌停强度", "capability_state": "disabled_this_session", "status": "本会话跳过"},
                ]
            }
        )

        summary = ledger.build_data_health_visibility_summary(packet, limit=6)
        rows = {item["api"]: item for item in summary["items"]}
        actions = {item["api"]: item for item in summary["recovery_actions"]}

        self.assertEqual(rows["stk_limit"]["writes_packet"], "command_center_limit_emotion_packet")
        self.assertEqual(rows["limit_list_d"]["writes_packet"], "command_center_limit_emotion_packet")
        self.assertEqual(rows["limit_cpt_list"]["writes_packet"], "command_center_limit_emotion_packet")
        self.assertEqual(actions["limit_list_d"]["legacy_tab"], "数据源体检")
        self.assertEqual(actions["limit_list_d"]["manual_check_key"], "limit_emotion")
        self.assertEqual(actions["limit_list_d"]["manual_check_button_label"], "手动检测涨跌停/情绪")
        self.assertIn("只检测 limit_list_d", actions["limit_list_d"]["manual_check_instruction"])
        self.assertEqual(actions["limit_cpt_list"]["legacy_workspace_route"]["legacy_tab"], "数据源体检")
        self.assertEqual(actions["limit_cpt_list"]["legacy_workspace_route"]["refresh_policy"], "button_gated")
        self.assertIn("之前拉满", rows["limit_list_d"]["diagnostic_answer"])
        self.assertIn("本会话跳过重复请求", rows["limit_cpt_list"]["diagnostic_answer"])
        self.assertIn("标的未上榜", rows["stk_limit"]["diagnostic_answer"])
        self.assertIn("不触发 DeepSeek", rows["limit_list_d"]["recovery_button_context"])
        self.assertIn("不能用缺失数据支持加仓", rows["limit_list_d"]["decision_guardrail"])
        self.assertFalse(summary["deepseek_called"])
        json.dumps(summary, ensure_ascii=False)

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_data_health_ledger.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        self.assertTrue(FORBIDDEN_IMPORTS.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
