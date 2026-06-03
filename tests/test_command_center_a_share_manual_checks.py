import ast
import json
import unittest
from pathlib import Path

import command_center_a_share_manual_checks as checks
import market_data_capability as capability


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


class CommandCenterAShareManualChecksTests(unittest.TestCase):
    def test_normalize_a_share_ts_code(self):
        self.assertEqual(checks.normalize_a_share_ts_code("002008"), "002008.SZ")
        self.assertEqual(checks.normalize_a_share_ts_code("600519"), "600519.SH")
        self.assertEqual(checks.normalize_a_share_ts_code("830799"), "830799.BJ")
        self.assertEqual(checks.normalize_a_share_ts_code("600519.SS"), "600519.SH")
        self.assertTrue(checks.is_a_share_ts_code("002008"))
        self.assertFalse(checks.is_a_share_ts_code("AAPL"))

    def test_margin_detail_request_is_button_gated(self):
        request = checks.build_margin_detail_check_request("002008", today="2026-06-03")

        self.assertEqual(request["api"], "margin_detail")
        self.assertEqual(request["section"], "margin")
        self.assertEqual(request["ts_code"], "002008.SZ")
        self.assertEqual(request["start_date"], "20260504")
        self.assertEqual(request["end_date"], "20260603")
        self.assertEqual(request["refresh_policy"], "button_gated")
        self.assertFalse(request["deepseek_called"])

    def test_margin_detail_result_builds_capability_item(self):
        item = checks.build_margin_detail_capability_item(
            {"ok": False, "error": "抱歉，您没有访问该接口的权限", "api": "margin_detail"},
            latency_ms=12,
        )

        self.assertEqual(item["section"], "margin")
        self.assertEqual(item["label"], "融资融券")
        self.assertEqual(item["capability_state"], capability.STATE_PERMISSION_DENIED)
        self.assertEqual(item["refresh_policy"], "button_gated")
        self.assertFalse(item["deepseek_called"])

    def test_merge_replaces_existing_margin_item(self):
        packet = {
            "source": "Tushare A股专业事实",
            "items": [
                {"section": "moneyflow", "label": "个股资金流", "api": "moneyflow", "capability_state": "available", "status": "可用"},
                {"section": "margin", "label": "融资融券", "api": "margin_detail", "capability_state": "permission_denied", "status": "权限不足"},
            ],
        }
        new_item = checks.build_margin_detail_capability_item({"ok": True, "rows": 2, "latest_date": "20260603"})
        merged = checks.merge_a_share_capability_item(packet, new_item, checked_at="2026-06-03T10:00:00")
        by_section = {item["section"]: item for item in merged["items"]}

        self.assertEqual(by_section["moneyflow"]["capability_state"], "available")
        self.assertEqual(by_section["margin"]["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(merged["ok_count"], 2)
        self.assertFalse(merged["deepseek_called"])
        json.dumps(merged, ensure_ascii=False)

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_a_share_manual_checks.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        self.assertTrue(FORBIDDEN_IMPORTS.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
