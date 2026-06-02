import ast
import json
import unittest
from pathlib import Path

import market_data_capability as capability


class MarketDataCapabilityTests(unittest.TestCase):
    def test_permission_error_is_classified(self):
        item = capability.build_capability_item("limit_cpt_list", error="当前权限不足，需要 8000 积分")

        self.assertEqual(item["capability_state"], capability.STATE_PERMISSION_DENIED)
        self.assertEqual(item["status"], "权限不足")
        self.assertTrue(item["permission_likely"])
        self.assertTrue(item["should_skip_session"])

    def test_empty_recent_is_not_treated_as_failure(self):
        item = capability.build_capability_item("top_list", ok=True, rows=0)

        self.assertEqual(item["capability_state"], capability.STATE_EMPTY_RECENT)
        self.assertEqual(item["status"], "近期无数据")
        self.assertIn("非交易日", item["action_hint"])

    def test_missing_token_is_not_configuration_not_permission(self):
        item = capability.build_capability_item("daily", error="缺少 TUSHARE_TOKEN 配置")

        self.assertEqual(item["capability_state"], capability.STATE_NOT_CONFIGURED)
        self.assertEqual(item["status"], "未配置")
        self.assertFalse(item["permission_likely"])

    def test_cached_and_session_skipped_states_are_explicit(self):
        cached = capability.build_capability_item("moneyflow", ok=True, rows=12, cached=True)
        skipped = capability.build_capability_item("limit_cpt_list", error="limit_cpt_list 当前权限不足，已在本会话跳过重复请求。")

        self.assertEqual(cached["capability_state"], capability.STATE_STALE_CACHE)
        self.assertEqual(cached["status"], "使用缓存")
        self.assertEqual(skipped["capability_state"], capability.STATE_DISABLED_THIS_SESSION)
        self.assertEqual(skipped["status"], "本会话跳过")

    def test_requires_manual_refresh_state(self):
        item = capability.build_capability_item("margin_detail", requires_manual_refresh=True)

        self.assertEqual(item["capability_state"], capability.STATE_REQUIRES_MANUAL_REFRESH)
        self.assertEqual(item["status"], "需要手动刷新")
        self.assertIn("页面打开不自动调用", item["action_hint"])

    def test_summarize_tushare_result_handles_dict_rows(self):
        result = {"ok": True, "rows": 5, "latest_date": "20260602", "source": "Tushare"}
        item = capability.summarize_tushare_result("moneyflow", result=result, latency_ms=23)

        self.assertEqual(item["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(item["rows"], 5)
        self.assertEqual(item["latest_date"], "20260602")
        self.assertEqual(item["latency_ms"], 23)

    def test_packet_summary_counts_key_states(self):
        items = [
            capability.build_capability_item("daily", ok=True, rows=10),
            capability.build_capability_item("limit_cpt_list", error="权限不足"),
            capability.build_capability_item("top_list", ok=True, rows=0),
            capability.build_capability_item("moneyflow", ok=True, rows=3, cached=True),
        ]
        packet = capability.build_tushare_capability_packet(items, checked_at="2026-06-02T21:30:00")

        self.assertEqual(packet["ok_count"], 1)
        self.assertEqual(packet["permission_denied_count"], 1)
        self.assertEqual(packet["empty_count"], 1)
        self.assertEqual(packet["cache_count"], 1)
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_forbidden_imports(self):
        tree = ast.parse(Path("market_data_capability.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        forbidden = {
            "streamlit",
            "app",
            "tushare_adapter",
            "tushare",
            "akshare",
            "yfinance",
            "data_fetcher",
            "backtester",
            "openai",
        }
        self.assertTrue(forbidden.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
