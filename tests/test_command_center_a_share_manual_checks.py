import ast
import datetime as dt
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

    def test_hard_risk_request_is_button_gated(self):
        today = dt.date(2026, 6, 3)
        request = checks.build_hard_risk_check_request("002008", today=today)

        self.assertEqual(request["api"], "anns_d/forecast/stk_holdertrade/share_float/pledge_stat/pledge_detail")
        self.assertEqual(request["section"], "hard_risk")
        self.assertEqual(request["ts_code"], "002008.SZ")
        self.assertEqual(request["ann_start_date"], (today - dt.timedelta(days=90)).strftime("%Y%m%d"))
        self.assertEqual(request["forecast_start_date"], (today - dt.timedelta(days=180)).strftime("%Y%m%d"))
        self.assertEqual(request["holder_start_date"], (today - dt.timedelta(days=180)).strftime("%Y%m%d"))
        self.assertEqual(request["unlock_start_date"], today.strftime("%Y%m%d"))
        self.assertEqual(request["unlock_end_date"], (today + dt.timedelta(days=90)).strftime("%Y%m%d"))
        self.assertEqual(request["end_date"], today.strftime("%Y%m%d"))
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

    def test_hard_risk_fact_packet_from_results_builds_sections(self):
        packet = checks.build_hard_risk_fact_packet_from_results(
            ts_code="002008",
            stock_name="大族激光",
            checked_at="2026-06-03T10:00:00",
            results={
                "anns_d": {
                    "ok": True,
                    "data": [
                        {
                            "ann_date": "20260601",
                            "title": "关于股东减持计划的公告",
                            "url": "https://example.test/ann",
                            "rec_time": "20260601120000",
                        }
                    ],
                },
                "forecast": {
                    "ok": True,
                    "data": [{"ann_date": "20260420", "type": "预减", "p_change_min": -40, "p_change_max": -20}],
                },
                "stk_holdertrade": {
                    "ok": True,
                    "data": [
                        {
                            "ann_date": "20260520",
                            "holder_name": "重要股东",
                            "trade_type": "减持",
                            "change_ratio": 1.2,
                        }
                    ],
                },
                "share_float": {
                    "ok": True,
                    "data": [{"float_date": "20260701", "float_share": 1000, "holder_name": "限售股东"}],
                },
                "pledge_stat": {
                    "ok": True,
                    "data": [{"end_date": "20260531", "pledge_ratio": 20.5}],
                },
                "pledge_detail": {
                    "ok": True,
                    "data": [{"ann_date": "20260515", "holder_name": "控股股东", "pledge_amount": 300}],
                },
            },
        )

        hard = packet["verified_hard_risks"]
        self.assertEqual(packet["stock"]["ts_code"], "002008.SZ")
        self.assertTrue(hard["available"])
        self.assertTrue(hard["announcements"]["available"])
        self.assertTrue(hard["holder_reduction"]["available"])
        self.assertTrue(hard["pledge"]["available"])
        self.assertIn("公告标题线索涉及", "；".join(hard["risk_flags"]))
        self.assertIn("股东减持", "；".join(hard["risk_flags"]))
        self.assertIn("质押比例", "；".join(hard["risk_flags"]))
        self.assertFalse(packet["deepseek_called"])
        self.assertTrue(hard["policy"]["hard_risk_manual_check_is_button_gated"])
        json.dumps(packet, ensure_ascii=False)

    def test_hard_risk_capability_item_is_button_gated_and_partial(self):
        item = checks.build_hard_risk_capability_item(
            {
                "anns_d": {"ok": True, "rows": 2, "latest_date": "20260601", "api": "anns_d"},
                "forecast": {"ok": True, "rows": 0, "latest_date": "", "api": "forecast"},
                "stk_holdertrade": {"ok": False, "error": "抱歉，您没有访问该接口的权限", "api": "stk_holdertrade"},
                "share_float": {"ok": True, "rows": 1, "latest_date": "20260701", "api": "share_float"},
                "pledge_stat": {"ok": True, "rows": 1, "latest_date": "20260531", "api": "pledge_stat"},
                "pledge_detail": {"ok": True, "rows": 0, "latest_date": "", "api": "pledge_detail"},
            },
            latency_ms=18,
        )

        self.assertEqual(item["section"], "hard_risk")
        self.assertEqual(item["label"], "公告/硬风险")
        self.assertEqual(item["capability_state"], capability.STATE_FALLBACK_USED)
        self.assertEqual(item["refresh_policy"], "button_gated")
        self.assertEqual(len(item["sub_items"]), 6)
        self.assertIn("部分公告/硬风险", item["error"])
        self.assertFalse(item["deepseek_called"])

    def test_hard_risk_exception_item_is_safe(self):
        item = checks.build_hard_risk_exception_item("未锁定 A股标的", latency_ms=3)

        self.assertEqual(item["section"], "hard_risk")
        self.assertEqual(item["api"], "anns_d/forecast/stk_holdertrade/share_float/pledge_stat/pledge_detail")
        self.assertEqual(item["refresh_policy"], "button_gated")
        self.assertTrue(item["can_retry"])
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
