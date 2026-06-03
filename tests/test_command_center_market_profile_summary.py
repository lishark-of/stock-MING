import ast
import json
import unittest
from pathlib import Path

import command_center_market_profile_summary as summary


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


class CommandCenterMarketProfileSummaryTests(unittest.TestCase):
    def test_builds_a_share_profile_evidence_strip(self):
        packet = summary.build_market_profile_evidence_strip(
            ticker="002008.SZ",
            live_packet={"market": {"status": "ready"}, "quant": {"status": "ready"}},
            decision_packet={"status": "ready", "overall_action": "只观察"},
        )
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["market_type"], "A股")
        self.assertEqual(packet["market_label"], "A股个股")
        self.assertEqual(packet["status"], "ready")
        for keyword in ["Tushare", "资金流", "公告", "涨跌停", "龙虎榜", "融资融券"]:
            self.assertIn(keyword, dumped)
        self.assertFalse(packet["deepseek_called"])

    def test_builds_us_profile_without_a_share_board_terms(self):
        packet = summary.build_market_profile_evidence_strip(
            ticker="AAPL",
            live_packet={"market": {"status": "ready"}},
        )
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["market_type"], "美股")
        for keyword in ["财报", "RS", "行业轮动", "宏观利率", "52周新高"]:
            self.assertIn(keyword, dumped)
        self.assertNotIn("龙虎榜", dumped)
        self.assertNotIn("涨跌停", dumped)
        self.assertFalse(packet["deepseek_called"])

    def test_builds_etf_profile_from_explicit_market_type(self):
        packet = summary.build_market_profile_evidence_strip(
            market_type="ETF",
            ticker="560780.SH",
            live_packet={"margin_etf": {"status": "ready"}},
        )
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["market_type"], "ETF")
        for keyword in ["跟踪指数", "流动性", "持仓重叠", "主题"]:
            self.assertIn(keyword, dumped)
        self.assertFalse(packet["deepseek_called"])

    def test_uses_home_snapshot_holding_when_ticker_missing(self):
        packet = summary.build_market_profile_evidence_strip(
            home_snapshot={
                "holding_action": {
                    "ticker": "002008.SZ",
                    "name": "大族激光",
                }
            }
        )

        self.assertEqual(packet["ticker"], "002008.SZ")
        self.assertEqual(packet["name"], "大族激光")
        self.assertEqual(packet["market_type"], "A股")

    def test_unknown_market_is_safe_and_json_friendly(self):
        packet = summary.build_market_profile_evidence_strip()

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["market_label"], "市场类型待确认")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_reuses_analysis_method_packet(self):
        packet = summary.build_market_profile_evidence_strip(
            ticker="AAPL",
            analysis_method_packet={
                "market": "美股",
                "summary": "美股分析框架已有可用证据。",
                "methods": [
                    {
                        "name": "相对强弱 RS / 行业轮动",
                        "status": "通过",
                        "evidence": "RS 已刷新。",
                        "risk": "行业退潮",
                        "action_hint": "强于行业才进入候选。",
                        "fit": "核心",
                    }
                ],
                "data_coverage": {"market": "ready"},
            },
        )

        self.assertEqual(packet["summary"], "美股分析框架已有可用证据。")
        self.assertEqual(packet["method_items"][0]["name"], "相对强弱 RS / 行业轮动")
        self.assertEqual(packet["method_items"][0]["tone"], "ready")

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_market_profile_summary.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_market_profile_summary.py: {name}")


if __name__ == "__main__":
    unittest.main()
