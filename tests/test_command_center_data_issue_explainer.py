import ast
import json
import unittest
from pathlib import Path

import command_center_data_issue_explainer as explainer


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


class CommandCenterDataIssueExplainerTests(unittest.TestCase):
    def test_empty_input_is_safe_and_does_not_ping_external_sources(self):
        packet = explainer.build_data_issue_explainer_packet()

        self.assertEqual(packet["status"], "missing")
        self.assertIn("不会自动 ping", packet["short_answer"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_permission_and_session_skip_explain_tushare_config_confusion(self):
        packet = explainer.build_data_issue_explainer_packet(
            data_capability_packet={
                "source": "Tushare",
                "items": [
                    {
                        "label": "融资融券",
                        "api": "margin_detail",
                        "provider": "Tushare",
                        "capability_state": "permission_denied",
                        "status": "权限不足",
                        "error": "抱歉，您没有访问该接口的权限",
                    },
                    {
                        "label": "涨跌停/情绪",
                        "api": "limit_cpt_list",
                        "provider": "Tushare",
                        "capability_state": "disabled_this_session",
                        "status": "本会话跳过",
                    },
                ],
            }
        )
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["restricted_count"], 2)
        self.assertIn("Tushare 配置成功只代表 token 可用", packet["short_answer"])
        self.assertIn("额外权限/积分", packet["short_answer"])
        self.assertIn("接口权限/积分问题", dumped)
        self.assertIn("本会话跳过重复请求", dumped)
        self.assertTrue(any(item["key"] == "endpoint_permission" for item in packet["root_cause_items"]))
        self.assertTrue(any(item["key"] == "session_skip" for item in packet["root_cause_items"]))
        self.assertEqual(packet["provider_diagnostic_cards"][0]["provider"], "Tushare")
        self.assertEqual(packet["provider_diagnostic_cards"][0]["blocked_count"], 2)
        self.assertIn("不是“没拉满”", packet["provider_diagnostic_cards"][0]["answer"])
        self.assertIn("单独权限或积分", packet["provider_diagnostic_cards"][0]["answer"])
        self.assertIn("防卡顿", packet["provider_diagnostic_cards"][0]["answer"])
        interface_rows = {item["api"]: item for item in packet["interface_diagnostic_items"]}
        self.assertEqual(interface_rows["margin_detail"]["cause_key"], "permission_or_points")
        self.assertIn("token 可用", interface_rows["margin_detail"]["diagnostic_answer"])
        self.assertIn("专业接口已开通", interface_rows["margin_detail"]["diagnostic_answer"])
        self.assertEqual(interface_rows["limit_cpt_list"]["cause_key"], "session_skip")
        self.assertIn("本会话跳过重复请求", interface_rows["limit_cpt_list"]["diagnostic_answer"])
        self.assertFalse(interface_rows["limit_cpt_list"]["deepseek_called"])
        self.assertFalse(packet["deepseek_called"])

    def test_empty_recent_is_explained_as_no_recent_record_not_positive_signal(self):
        packet = explainer.build_data_issue_explainer_packet(
            data_capability_packet={
                "source": "Tushare",
                "items": [
                    {
                        "label": "龙虎榜",
                        "api": "top_list",
                        "provider": "Tushare",
                        "capability_state": "empty_recent",
                        "status": "近期无数据",
                    }
                ],
            }
        )
        item = packet["items"][0]

        self.assertEqual(packet["pending_count"], 1)
        self.assertIn("接口可用也可能搜不到", packet["short_answer"])
        self.assertEqual(packet["root_cause_items"][0]["key"], "empty_recent")
        self.assertIn("标的未上榜", item["meaning"])
        self.assertIn("无记录不能写成利好", item["decision_impact"])
        interface_row = packet["interface_diagnostic_items"][0]
        self.assertEqual(interface_row["cause_key"], "no_recent_record")
        self.assertIn("接口可读但近窗口无记录", interface_row["diagnostic_answer"])
        self.assertIn("标的未上榜", interface_row["diagnostic_answer"])
        self.assertIn("不能写成利好", interface_row["decision_impact"])
        self.assertEqual(packet["provider_diagnostic_cards"][0]["pending_count"], 1)
        self.assertIn("非交易日", packet["provider_diagnostic_cards"][0]["answer"])
        self.assertIn("标的未上榜", packet["provider_diagnostic_cards"][0]["answer"])

    def test_cache_and_fallback_are_marked_as_not_realtime(self):
        packet = explainer.build_data_issue_explainer_packet(
            data_capability_packet={
                "source": "Unified data capability",
                "items": [
                    {"label": "个股资金流", "provider": "Tushare", "capability_state": "stale_cache", "status": "使用缓存"},
                    {"label": "公告风险", "provider": "Tushare", "capability_state": "fallback_used", "status": "替代口径"},
                ],
            }
        )
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["pending_count"], 2)
        self.assertIn("缓存或替代口径", packet["short_answer"])
        self.assertTrue(any(item["key"] == "cache_or_fallback" for item in packet["root_cause_items"]))
        causes = {item["cause_key"] for item in packet["interface_diagnostic_items"]}
        self.assertEqual(causes, {"cache_or_fallback"})
        self.assertIn("不是实时数据", dumped)
        self.assertIn("不能等同于原始接口事实", dumped)

    def test_not_checked_root_cause_explains_no_auto_ping(self):
        packet = explainer.build_data_issue_explainer_packet()

        self.assertEqual(packet["root_cause_items"][0]["key"], "not_checked")
        self.assertIn("不会自动请求外部接口", packet["root_cause_items"][0]["detail"])
        self.assertFalse(packet["deepseek_called"])

    def test_refresh_errors_are_visible_as_failed_items(self):
        packet = explainer.build_data_issue_explainer_packet(
            refresh_summary={
                "error_items": [
                    {"module": "下一票雷达", "message": "scan failed", "source": "unit"},
                ]
            }
        )

        self.assertEqual(packet["restricted_count"], 1)
        self.assertEqual(packet["items"][0]["label"], "下一票雷达")
        self.assertEqual(packet["items"][0]["state"], "failed")
        self.assertIn("不能支撑加仓", packet["items"][0]["decision_impact"])

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_data_issue_explainer.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        self.assertTrue(FORBIDDEN_IMPORTS.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
