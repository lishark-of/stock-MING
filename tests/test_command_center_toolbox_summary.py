import ast
import json
import unittest
from pathlib import Path

import command_center_toolbox_summary as toolbox


FORBIDDEN_IMPORTS = {
    "streamlit",
    "app",
    "command_center_service",
    "strategy_execution_service",
    "command_center_decision_engine",
    "tushare_adapter",
    "tushare",
    "akshare",
    "yfinance",
    "data_fetcher",
    "backtester",
    "openai",
}


def sample_data_capability_packet():
    return {
        "source": "Unified data capability",
        "items": [
            {
                "provider": "Tushare",
                "api": "moneyflow",
                "label": "个股资金流",
                "capability_state": "available",
                "status": "可用",
            },
            {
                "provider": "Tushare",
                "api": "margin_detail",
                "label": "融资融券",
                "capability_state": "permission_denied",
                "status": "权限不足",
            },
            {
                "provider": "Tushare",
                "api": "top_list",
                "label": "龙虎榜",
                "capability_state": "stale_cache",
                "status": "使用缓存",
            },
            {
                "provider": "Tushare",
                "api": "limit_cpt_list",
                "label": "涨跌停/情绪",
                "capability_state": "disabled_this_session",
                "status": "本会话跳过",
            },
            {
                "provider": "AkShare",
                "api": "akshare_manual_refresh",
                "label": "AkShare 重型刷新",
                "capability_state": "requires_manual_refresh",
                "status": "需要手动刷新",
            },
        ],
    }


class CommandCenterToolboxSummaryTests(unittest.TestCase):
    def test_advanced_toolbox_entry_is_manual_and_json_friendly(self):
        packet = toolbox.build_advanced_toolbox_entry()
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["status"], "ready")
        self.assertFalse(packet["deepseek_called"])
        self.assertIn("综合推演中心仍是默认主入口", packet["summary"])
        self.assertIn("不会自动触发 DeepSeek", packet["manual_note"])
        self.assertIn("Tushare 拉满或 token 可用", packet["data_gap_note"])
        self.assertIn("数据源体检", dumped)
        self.assertIn("下一票雷达", dumped)
        self.assertIn("capability_map", packet)
        self.assertTrue(packet["items"])

    def test_toolbox_items_are_button_gated_and_packet_mapped(self):
        packet = toolbox.build_advanced_toolbox_entry()

        for item in packet["items"]:
            self.assertEqual(item["trigger_policy"], "button_gated")
            self.assertEqual(item["deepseek_policy"], "manual_only")
            self.assertTrue(item["packet"])
            self.assertTrue(item["gate"])
            self.assertTrue(item["data_dependencies"])
            self.assertTrue(item["common_missing_reasons"])
            self.assertTrue(item["safe_empty_state"])
            self.assertFalse(item["capability_summary"]["deepseek_called"])

    def test_can_filter_toolbox_items(self):
        packet = toolbox.build_advanced_toolbox_entry(keys=["data_healthcheck"])

        self.assertEqual(len(packet["items"]), 1)
        self.assertEqual(packet["items"][0]["label"], "数据源体检")
        self.assertEqual(packet["capability_map"][0]["key"], "data_healthcheck")

    def test_legacy_tool_capability_map_explains_why_old_data_can_be_missing(self):
        capability_map = toolbox.build_legacy_tool_capability_map()
        dumped = json.dumps(capability_map, ensure_ascii=False)

        self.assertIn("Tushare moneyflow", dumped)
        self.assertIn("top_list", dumped)
        self.assertIn("limit_cpt_list", dumped)
        self.assertIn("Tushare token 可用不等于", dumped)
        self.assertIn("权限不足", dumped)
        self.assertIn("非交易日", dumped)
        self.assertIn("使用缓存", dumped)

    def test_filtered_capability_map_keeps_manual_gate(self):
        capability_map = toolbox.build_legacy_tool_capability_map(keys=["next_ticket_radar"])

        self.assertEqual(len(capability_map), 1)
        self.assertEqual(capability_map[0]["key"], "next_ticket_radar")
        self.assertIn("按钮", capability_map[0]["manual_gate"])
        self.assertFalse(capability_map[0]["deepseek_called"])

    def test_toolbox_entry_reads_existing_capability_packet_without_external_calls(self):
        packet = toolbox.build_advanced_toolbox_entry(data_capability_packet=sample_data_capability_packet())
        by_key = {item["key"]: item["capability_status"] for item in packet["items"]}
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(by_key["next_ticket_radar"]["status_label"], "本会话跳过")
        self.assertEqual(by_key["margin_etf"]["status_label"], "权限不足")
        self.assertGreaterEqual(by_key["data_healthcheck"]["manual_count"], 1)
        self.assertTrue(any(item["key"] == "endpoint_permission" for item in by_key["margin_etf"]["issue_explainer"]["root_cause_items"]))
        self.assertTrue(any(item["key"] == "session_skip" for item in by_key["next_ticket_radar"]["issue_explainer"]["root_cause_items"]))
        self.assertIn("个股资金流", dumped)
        self.assertIn("使用缓存", dumped)
        self.assertIn("需要手动刷新", dumped)
        self.assertIn("Tushare token 可用不等于", dumped)
        self.assertFalse(packet["deepseek_called"])

    def test_tool_capability_status_is_missing_when_no_local_check_matches(self):
        packet = toolbox.build_advanced_toolbox_entry(
            keys=["cloud_brain"],
            data_capability_packet=sample_data_capability_packet(),
        )
        status = packet["items"][0]["capability_status"]

        self.assertEqual(status["status"], "missing")
        self.assertEqual(status["status_label"], "待检测")
        self.assertEqual(status["issue_explainer"]["root_cause_items"][0]["key"], "not_checked")
        self.assertIn("不会自动请求外部接口", status["summary"])

    def test_legacy_capability_map_includes_status_view_model(self):
        capability_map = toolbox.build_legacy_tool_capability_map(
            keys=["margin_etf"],
            data_capability_packet=sample_data_capability_packet(),
        )

        self.assertEqual(capability_map[0]["capability_status"]["status_label"], "权限不足")
        self.assertFalse(capability_map[0]["capability_status"]["deepseek_called"])

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_toolbox_summary.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        self.assertTrue(FORBIDDEN_IMPORTS.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
