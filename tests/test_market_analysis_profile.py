import ast
import json
import unittest
from pathlib import Path

import market_analysis_profile as profile


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


class MarketAnalysisProfileTests(unittest.TestCase):
    def test_identifies_a_share_profile(self):
        market = profile.identify_market_type("002008.SZ")
        result = profile.get_market_analysis_profile(market)

        self.assertEqual(market, "A股")
        self.assertEqual(result["market"], "A股")
        joined = " ".join(result["data_source_priority"] + result["core_features"] + result["indicator_focus"])
        for keyword in ["Tushare", "资金流", "公告", "涨跌停", "龙虎榜", "融资融券"]:
            self.assertIn(keyword, joined)
        self.assertFalse(result["deepseek_called"])
        json.dumps(result, ensure_ascii=False)

    def test_identifies_us_stock_profile(self):
        market = profile.identify_market_type("AAPL")
        result = profile.get_market_analysis_profile(market)

        self.assertEqual(market, "美股")
        joined = " ".join(result["core_features"] + result["indicator_focus"] + result["risk_focus"])
        for keyword in ["财报", "RS", "行业轮动", "宏观利率", "52周新高"]:
            self.assertIn(keyword, joined)
        self.assertFalse(result["deepseek_called"])

    def test_identifies_etf_from_a_share_etf_codes(self):
        for ticker in ["560780.SH", "159801.SZ"]:
            with self.subTest(ticker=ticker):
                market = profile.identify_market_type(ticker)
                result = profile.get_market_analysis_profile(market)
                joined = " ".join(result["core_features"] + result["indicator_focus"])

                self.assertEqual(market, "ETF")
                for keyword in ["跟踪指数", "流动性", "持仓重叠", "主题分类"]:
                    self.assertIn(keyword, joined)
                self.assertFalse(result["deepseek_called"])

    def test_etf_hint_overrides_plain_ticker_market(self):
        self.assertEqual(profile.identify_market_type("AAPL", name="科技ETF"), "ETF")
        self.assertEqual(profile.identify_market_type(packet={"code": "560780.SH", "fund_type": "ETF"}), "ETF")

    def test_unknown_profile_is_safe_and_json_friendly(self):
        result = profile.get_market_analysis_profile("未知市场")

        self.assertEqual(result["market"], "未知市场")
        self.assertFalse(result["deepseek_called"])
        json.dumps(result, ensure_ascii=False)

    def test_app_internal_market_aliases_are_supported(self):
        self.assertEqual(profile.get_market_analysis_profile("A_SHARE_SH")["market"], "A股")
        self.assertEqual(profile.get_market_analysis_profile("A_SHARE_SZ")["market"], "A股")
        self.assertEqual(profile.get_market_analysis_profile("US_STOCK")["market"], "美股")

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("market_analysis_profile.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in market_analysis_profile.py: {name}")


if __name__ == "__main__":
    unittest.main()
