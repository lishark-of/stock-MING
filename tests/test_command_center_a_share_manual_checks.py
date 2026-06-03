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

    def test_dragon_tiger_request_is_button_gated(self):
        request = checks.build_dragon_tiger_check_request("002008", today="2026-06-03")

        self.assertEqual(request["api"], "top_list/top_inst")
        self.assertEqual(request["section"], "dragon_tiger")
        self.assertEqual(request["ts_code"], "002008.SZ")
        self.assertEqual(request["start_date"], "20260504")
        self.assertEqual(request["end_date"], "20260603")
        self.assertEqual(request["refresh_policy"], "button_gated")
        self.assertFalse(request["deepseek_called"])

    def test_moneyflow_request_is_button_gated(self):
        request = checks.build_moneyflow_check_request("002008", today="2026-06-03")

        self.assertEqual(request["api"], "moneyflow")
        self.assertEqual(request["section"], "moneyflow")
        self.assertEqual(request["ts_code"], "002008.SZ")
        self.assertEqual(request["start_date"], "20260524")
        self.assertEqual(request["end_date"], "20260603")
        self.assertEqual(request["refresh_policy"], "button_gated")
        self.assertFalse(request["deepseek_called"])

    def test_limit_cpt_request_is_button_gated(self):
        request = checks.build_limit_cpt_check_request(today="2026-06-03")

        self.assertEqual(request["api"], "limit_cpt_list")
        self.assertEqual(request["section"], "limit_emotion")
        self.assertEqual(request["start_date"], "20260524")
        self.assertEqual(request["end_date"], "20260603")
        self.assertEqual(request["refresh_policy"], "button_gated")
        self.assertFalse(request["deepseek_called"])

    def test_chip_radar_request_is_button_gated(self):
        request = checks.build_chip_radar_check_request("002008", today="2026-06-03")

        self.assertEqual(request["api"], "cyq_perf/cyq_chips")
        self.assertEqual(request["section"], "chip_radar")
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

    def test_moneyflow_result_builds_capability_item(self):
        item = checks.build_moneyflow_capability_item(
            {"ok": True, "rows": 3, "latest_date": "20260603", "api": "moneyflow"},
            latency_ms=11,
        )

        self.assertEqual(item["section"], "moneyflow")
        self.assertEqual(item["label"], "个股资金流")
        self.assertEqual(item["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(item["rows"], 3)
        self.assertEqual(item["latest_date"], "20260603")
        self.assertEqual(item["refresh_policy"], "button_gated")
        self.assertFalse(item["deepseek_called"])

    def test_moneyflow_permission_denied_is_visible(self):
        item = checks.build_moneyflow_capability_item(
            {"ok": False, "error": "抱歉，您没有访问该接口的权限", "api": "moneyflow"},
            latency_ms=11,
        )

        self.assertEqual(item["capability_state"], capability.STATE_PERMISSION_DENIED)
        self.assertTrue(item["permission_likely"])
        self.assertFalse(item["deepseek_called"])

    def test_limit_cpt_result_builds_capability_item(self):
        item = checks.build_limit_cpt_capability_item(
            {"ok": False, "error": "limit_cpt_list 当前权限不足，已在本会话跳过重复请求。", "api": "limit_cpt_list"},
            latency_ms=9,
        )

        self.assertEqual(item["section"], "limit_emotion")
        self.assertEqual(item["label"], "涨跌停/情绪")
        self.assertEqual(item["capability_state"], capability.STATE_DISABLED_THIS_SESSION)
        self.assertEqual(item["refresh_policy"], "button_gated")
        self.assertFalse(item["deepseek_called"])

    def test_chip_radar_result_requires_both_sub_interfaces(self):
        item = checks.build_chip_radar_capability_item(
            {"ok": True, "rows": 2, "latest_date": "20260603", "api": "cyq_perf"},
            {"ok": True, "rows": 3, "latest_date": "20260602", "api": "cyq_chips"},
            latency_ms=15,
        )

        self.assertEqual(item["section"], "chip_radar")
        self.assertEqual(item["label"], "筹码/胜率")
        self.assertEqual(item["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(item["rows"], 5)
        self.assertEqual(item["latest_date"], "20260603")
        self.assertEqual(len(item["sub_items"]), 2)
        self.assertEqual(item["refresh_policy"], "button_gated")
        self.assertFalse(item["deepseek_called"])

    def test_dragon_tiger_result_requires_top_list_and_top_inst(self):
        item = checks.build_dragon_tiger_capability_item(
            {"ok": True, "rows": 1, "latest_date": "20260603", "api": "top_list"},
            {"ok": True, "rows": 2, "latest_date": "20260603", "api": "top_inst"},
            latency_ms=15,
        )

        self.assertEqual(item["section"], "dragon_tiger")
        self.assertEqual(item["label"], "龙虎榜")
        self.assertEqual(item["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(item["rows"], 3)
        self.assertEqual(item["latest_date"], "20260603")
        self.assertEqual(len(item["sub_items"]), 2)
        self.assertEqual(item["refresh_policy"], "button_gated")
        self.assertFalse(item["deepseek_called"])

    def test_dragon_tiger_partial_result_is_fallback_used(self):
        item = checks.build_dragon_tiger_capability_item(
            {"ok": True, "rows": 1, "latest_date": "20260603", "api": "top_list"},
            {"ok": True, "rows": 0, "latest_date": "", "api": "top_inst"},
            latency_ms=15,
        )

        self.assertEqual(item["capability_state"], capability.STATE_FALLBACK_USED)
        self.assertIn("席位明细", item["error"])
        self.assertFalse(item["deepseek_called"])

    def test_dragon_tiger_permission_denied_is_visible(self):
        item = checks.build_dragon_tiger_capability_item(
            {"ok": False, "error": "抱歉，您没有访问该接口的权限", "api": "top_list"},
            {"ok": False, "error": "抱歉，您没有访问该接口的权限", "api": "top_inst"},
            latency_ms=15,
        )

        self.assertEqual(item["capability_state"], capability.STATE_PERMISSION_DENIED)
        self.assertTrue(item["permission_likely"])
        self.assertFalse(item["deepseek_called"])

    def test_chip_radar_partial_result_is_fallback_used(self):
        item = checks.build_chip_radar_capability_item(
            {"ok": True, "rows": 2, "latest_date": "20260603", "api": "cyq_perf"},
            {"ok": True, "rows": 0, "latest_date": "", "api": "cyq_chips"},
            latency_ms=15,
        )

        self.assertEqual(item["capability_state"], capability.STATE_FALLBACK_USED)
        self.assertIn("部分", item["error"])
        self.assertFalse(item["deepseek_called"])

    def test_chip_radar_permission_denied_is_visible(self):
        item = checks.build_chip_radar_capability_item(
            {"ok": False, "error": "抱歉，您没有访问该接口的权限", "api": "cyq_perf"},
            {"ok": False, "error": "抱歉，您没有访问该接口的权限", "api": "cyq_chips"},
            latency_ms=15,
        )

        self.assertEqual(item["capability_state"], capability.STATE_PERMISSION_DENIED)
        self.assertTrue(item["permission_likely"])
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

    def test_merge_replaces_existing_moneyflow_item(self):
        packet = {
            "source": "Tushare A股专业事实",
            "items": [
                {"section": "moneyflow", "label": "个股资金流", "api": "moneyflow", "capability_state": "empty_recent", "status": "近期无数据"},
                {"section": "margin", "label": "融资融券", "api": "margin_detail", "capability_state": "permission_denied", "status": "权限不足"},
            ],
        }
        new_item = checks.build_moneyflow_capability_item({"ok": True, "rows": 3, "latest_date": "20260603"})
        merged = checks.merge_a_share_capability_item(packet, new_item, checked_at="2026-06-03T10:00:00")
        by_section = {item["section"]: item for item in merged["items"]}

        self.assertEqual(by_section["moneyflow"]["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(by_section["margin"]["capability_state"], capability.STATE_PERMISSION_DENIED)
        self.assertEqual(merged["ok_count"], 1)
        self.assertFalse(merged["deepseek_called"])
        json.dumps(merged, ensure_ascii=False)

    def test_merge_replaces_existing_dragon_tiger_item(self):
        packet = {
            "source": "Tushare A股专业事实",
            "items": [
                {"section": "dragon_tiger", "label": "龙虎榜", "api": "top_list/top_inst", "capability_state": "empty_recent", "status": "近期无数据"},
                {"section": "margin", "label": "融资融券", "api": "margin_detail", "capability_state": "permission_denied", "status": "权限不足"},
            ],
        }
        new_item = checks.build_dragon_tiger_capability_item(
            {"ok": True, "rows": 1, "latest_date": "20260603"},
            {"ok": True, "rows": 2, "latest_date": "20260603"},
        )
        merged = checks.merge_a_share_capability_item(packet, new_item, checked_at="2026-06-03T10:00:00")
        by_section = {item["section"]: item for item in merged["items"]}

        self.assertEqual(by_section["dragon_tiger"]["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(by_section["margin"]["capability_state"], capability.STATE_PERMISSION_DENIED)
        self.assertEqual(merged["ok_count"], 1)
        self.assertFalse(merged["deepseek_called"])
        json.dumps(merged, ensure_ascii=False)

    def test_merge_replaces_existing_limit_emotion_item(self):
        packet = {
            "source": "Tushare A股专业事实",
            "items": [
                {"section": "limit_emotion", "label": "涨跌停/情绪", "api": "limit_cpt_list", "capability_state": "disabled_this_session", "status": "本会话跳过"},
                {"section": "margin", "label": "融资融券", "api": "margin_detail", "capability_state": "permission_denied", "status": "权限不足"},
            ],
        }
        new_item = checks.build_limit_cpt_capability_item({"ok": True, "rows": 5, "latest_date": "20260603"})
        merged = checks.merge_a_share_capability_item(packet, new_item, checked_at="2026-06-03T10:00:00")
        by_section = {item["section"]: item for item in merged["items"]}

        self.assertEqual(by_section["limit_emotion"]["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(by_section["margin"]["capability_state"], capability.STATE_PERMISSION_DENIED)
        self.assertEqual(merged["ok_count"], 1)
        self.assertFalse(merged["deepseek_called"])
        json.dumps(merged, ensure_ascii=False)

    def test_merge_replaces_existing_chip_radar_item(self):
        packet = {
            "source": "Tushare A股专业事实",
            "items": [
                {"section": "chip_radar", "label": "筹码/胜率", "api": "cyq_perf/cyq_chips", "capability_state": "empty_recent", "status": "近期无数据"},
                {"section": "limit_emotion", "label": "涨跌停/情绪", "api": "limit_cpt_list", "capability_state": "disabled_this_session", "status": "本会话跳过"},
            ],
        }
        new_item = checks.build_chip_radar_capability_item(
            {"ok": True, "rows": 2, "latest_date": "20260603"},
            {"ok": True, "rows": 3, "latest_date": "20260603"},
        )
        merged = checks.merge_a_share_capability_item(packet, new_item, checked_at="2026-06-03T10:00:00")
        by_section = {item["section"]: item for item in merged["items"]}

        self.assertEqual(by_section["chip_radar"]["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(by_section["limit_emotion"]["capability_state"], capability.STATE_DISABLED_THIS_SESSION)
        self.assertEqual(merged["ok_count"], 1)
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
