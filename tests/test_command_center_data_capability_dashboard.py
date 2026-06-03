import ast
import json
import unittest
from pathlib import Path

import command_center_data_capability_dashboard as dashboard


class CommandCenterDataCapabilityDashboardTests(unittest.TestCase):
    def test_empty_dashboard_is_safe_and_manual(self):
        vm = dashboard.build_data_capability_dashboard_view_model({}, {})

        self.assertEqual(vm["status"], "missing")
        self.assertIn("不会自动请求", vm["summary"])
        self.assertEqual(vm["provider_cards"], [])
        self.assertFalse(vm["deepseek_called"])
        json.dumps(vm, ensure_ascii=False)

    def test_provider_cards_group_tushare_supabase_akshare_and_yfinance(self):
        vm = dashboard.build_data_capability_dashboard_view_model(
            {
                "source": "Unified data capability",
                "items": [
                    {"provider": "Tushare", "api": "moneyflow", "label": "个股资金流", "capability_state": "available", "status": "可用"},
                    {"provider": "Tushare", "api": "limit_cpt_list", "label": "涨跌停/情绪", "capability_state": "disabled_this_session", "status": "本会话跳过"},
                    {"provider": "Supabase", "api": "brain_memory", "label": "brain_memory", "capability_state": "not_configured", "status": "未配置"},
                    {"provider": "AkShare", "api": "akshare_manual_refresh", "label": "AkShare 重型刷新", "capability_state": "requires_manual_refresh", "status": "需要手动刷新"},
                    {"provider": "yfinance", "api": "yfinance_market_data", "label": "yfinance 行情/新闻", "capability_state": "requires_manual_refresh", "status": "需要手动刷新"},
                ],
            }
        )
        by_provider = {card["provider"]: card for card in vm["provider_cards"]}
        dumped = json.dumps(vm, ensure_ascii=False)

        self.assertEqual(vm["status"], "partial")
        self.assertEqual(by_provider["Tushare"]["available_count"], 1)
        self.assertEqual(by_provider["Tushare"]["restricted_count"], 1)
        self.assertIn("Supabase", by_provider)
        self.assertIn("AkShare", by_provider)
        self.assertIn("yfinance", by_provider)
        self.assertIn("本会话", dumped)
        self.assertIn("需要手动刷新", dumped)
        self.assertFalse(vm["deepseek_called"])

    def test_gap_report_items_are_used_when_capability_items_are_missing(self):
        vm = dashboard.build_data_capability_dashboard_view_model(
            {},
            {
                "items": [
                    {"provider": "Tushare", "label": "融资融券", "api": "margin_detail", "state": "permission_denied", "status": "权限不足"},
                    {"provider": "Tushare", "label": "龙虎榜", "api": "top_list", "state": "empty_recent", "status": "近期无数据"},
                ],
                "next_manual_checks": ["融资融券权限不足：不要把缺失数据当成利好。"],
            },
        )

        self.assertEqual(vm["restricted_count"], 1)
        self.assertEqual(vm["pending_count"], 1)
        self.assertTrue(any("权限不足" in item for item in vm["manual_actions"]))
        self.assertFalse(vm["deepseek_called"])

    def test_state_normalization_handles_chinese_status_text(self):
        item = dashboard.normalize_capability_item({"provider": "Tushare", "label": "limit_cpt_list", "status": "本会话跳过"})

        self.assertEqual(item["state"], "disabled_this_session")
        self.assertEqual(item["tone"], "failed")
        self.assertIn("手动重试", item["action_hint"])

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_data_capability_dashboard.py").read_text(encoding="utf-8"))
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
