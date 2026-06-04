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
        self.assertEqual(rows["AkShare 重型刷新"]["refresh_policy"], "button_gated")
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
        self.assertEqual(summary["external_call_policy"], "not_triggered")
        self.assertFalse(summary["deepseek_called"])
        self.assertIn("command_center_margin_packet", dumped)

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
