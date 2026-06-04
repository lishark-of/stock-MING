import json
import unittest

import command_center_overview_summary as overview
import data_capability_registry as registry
import data_capability_service as service


class CommandCenterDataCapabilityIntegrationTests(unittest.TestCase):
    def test_governance_packet_preserves_required_status_buckets(self):
        payload = registry.build_initial_capability_registry(target="002008.SZ", market_type="A_SHARE")
        for name, status in [
            ("Tushare 个股资金流", registry.STATUS_AVAILABLE),
            ("Tushare 融资融券", registry.STATUS_NO_PERMISSION),
            ("Tushare 涨跌停", registry.STATUS_NO_DATA),
            ("Tushare 筹码/胜率", registry.STATUS_CACHED),
            ("AkShare 个股资金", registry.STATUS_FAILED),
            ("yfinance 行情", registry.STATUS_SKIPPED),
        ]:
            payload = registry.update_capability_status(payload, name, status, last_error=f"{name}:{status}")

        packet = service.build_data_capability_packet(payload)
        by_name = {item["name"]: item for item in packet["items"]}
        groups = packet["status_groups"]

        self.assertEqual(by_name["Tushare 融资融券"]["governance_status"], "no_permission")
        self.assertEqual(by_name["Tushare 涨跌停"]["governance_status"], "no_data")
        self.assertEqual(by_name["Tushare 筹码/胜率"]["governance_status"], "cached")
        self.assertEqual(by_name["yfinance 行情"]["governance_status"], "skipped")
        self.assertIn("Tushare 个股资金流", groups["available"])
        self.assertIn("AkShare 个股资金", groups["failed"])
        json.dumps(packet, ensure_ascii=False)

    def test_overview_displays_all_capability_buckets_and_manual_deepseek(self):
        packet = {
            "items": [
                {"label": "Tushare 个股资金流", "api": "moneyflow", "governance_status": "available"},
                {"label": "AkShare 资金穿透", "api": "akshare_money_flow", "governance_status": "failed"},
                {"label": "Tushare 融资融券", "api": "margin_detail", "governance_status": "no_permission"},
                {"label": "yfinance 行情", "api": "yfinance_quote", "governance_status": "cached"},
                {"label": "Tushare 涨跌停", "api": "limit_cpt_list", "governance_status": "no_data"},
                {"label": "Supabase 历史记录", "api": "trade_history", "governance_status": "skipped"},
                {"label": "Supabase 回测缓存", "api": "backtest_cache", "governance_status": "unknown"},
            ]
        }

        vm = overview.build_command_center_overview_view_model(
            data_capability_packet=packet,
            deepseek_summary="人工点击生成的解释缓存",
        )
        summary = vm["data_capability_summary_text"]

        self.assertIn("可用：Tushare 个股资金流", summary)
        self.assertIn("失败：AkShare 资金穿透", summary)
        self.assertIn("权限不足：Tushare 融资融券", summary)
        self.assertIn("缓存：yfinance 行情", summary)
        self.assertIn("无数据：Tushare 涨跌停", summary)
        self.assertIn("跳过：Supabase 历史记录", summary)
        self.assertIn("未知：Supabase 回测缓存", summary)
        self.assertEqual(vm["deepseek_text"], "DeepSeek：手动解释")
        json.dumps(vm, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
