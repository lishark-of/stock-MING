import ast
import json
import unittest
from pathlib import Path

import command_center_analysis_methods as methods


FORBIDDEN_IMPORTS = {
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


class CommandCenterAnalysisMethodsTests(unittest.TestCase):
    def test_a_share_packet_uses_a_share_methods_without_deepseek(self):
        packet = methods.build_analysis_method_packet(
            ticker="002008.SZ",
            live_packet={"market": {"status": "ready"}, "quant": {"status": "ready"}},
            strategy_packet={"status": "ready", "action": "等待验证"},
            decision_packet={"status": "ready", "overall_action": "只观察"},
            now="2026-06-01T09:30:00",
        )

        self.assertEqual(packet["market"], "A股")
        self.assertFalse(packet["deepseek_called"])
        names = [item["name"] for item in packet["methods"]]
        self.assertIn("资金流 / 机构行为", names)
        joined = json.dumps(packet, ensure_ascii=False)
        self.assertIn("龙虎榜", joined)
        self.assertIn("融资融券", joined)
        json.dumps(packet, ensure_ascii=False)

    def test_us_packet_uses_earnings_rs_and_macro_not_a_share_board_terms(self):
        packet = methods.build_analysis_method_packet(
            ticker="AAPL",
            live_packet={"market": {"status": "ready"}},
            now="2026-06-01T09:30:00",
        )

        self.assertEqual(packet["market"], "美股")
        joined = json.dumps(packet, ensure_ascii=False)
        self.assertIn("财报", joined)
        self.assertIn("RS", joined)
        self.assertIn("宏观", joined)
        self.assertNotIn("龙虎榜口径判断美股", packet["summary"])
        self.assertFalse(packet["deepseek_called"])

    def test_etf_packet_marks_etf_allocation_applicable(self):
        packet = methods.build_analysis_method_packet(
            ticker="560780.SH",
            live_packet={"margin_etf": {"status": "ready"}},
            now="2026-06-01T09:30:00",
        )

        self.assertEqual(packet["market"], "ETF")
        by_name = {item["name"]: item for item in packet["methods"]}
        self.assertEqual(by_name["ETF 赛道配置"]["status"], "通过")
        self.assertIn("跟踪指数", json.dumps(packet, ensure_ascii=False))

    def test_insufficient_data_is_pending_not_fake_pass(self):
        packet = methods.build_analysis_method_packet(ticker="AAPL", now="2026-06-01T09:30:00")

        statuses = {item["status"] for item in packet["methods"]}
        self.assertIn("待验证", statuses)
        self.assertNotIn("通过", statuses)
        self.assertIn("等待数据刷新", packet["summary"])

    def test_risk_context_flags_risk_budget_failure(self):
        packet = methods.build_analysis_method_packet(
            ticker="002008.SZ",
            strategy_packet={"status": "ready", "action": "降风险", "summary": "回撤过高"},
            decision_packet={"status": "ready", "overall_action": "降风险", "risk_level": "高"},
        )
        by_name = {item["name"]: item for item in packet["methods"]}

        self.assertEqual(by_name["风险预算 / 仓位管理"]["status"], "失败")
        self.assertIn("风险项", packet["summary"])

    def test_packet_tolerates_non_mapping_inputs(self):
        packet = methods.build_analysis_method_packet(
            market_type="ETF",
            live_packet=object(),
            strategy_packet=object(),
            decision_packet=object(),
        )

        self.assertIsInstance(packet, dict)
        self.assertEqual(packet["data_coverage"]["market"], "missing")
        json.dumps(packet, ensure_ascii=False)

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_analysis_methods.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_analysis_methods.py: {name}")


if __name__ == "__main__":
    unittest.main()

