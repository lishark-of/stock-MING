import json
import unittest

import pandas as pd

from analysis_engine import build_ai_context_payload


class AnalysisEnginePayloadTest(unittest.TestCase):
    def test_payload_is_json_serializable_and_dedupes_news(self):
        payload = build_ai_context_payload(
            {"theme": "AI算力", "position": "上游", "risk_transmission": "订单下修"},
            {"valuation_flag": "估值未触发明显高危标签"},
            [
                {"title": "订单增长", "url": "https://example.com/a", "sentiment": "利多"},
                {"title": "订单增长", "url": "https://example.com/a", "sentiment": "利多"},
            ],
            "跌破MA20减仓",
            technical={"ma20": 10, "ma60": 9},
            scenario={"p10": 8, "p50": 10, "p90": 12},
            data_quality={"score": 80, "grade": "高"},
            money_flow={"summary": {"positive": ["主力净流入"], "negative": []}},
            research_links=[
                {"title": "研报风险", "risk": "订单波动"},
                {"title": "研报风险", "risk": "订单波动"},
            ],
        )

        encoded = json.dumps(payload, ensure_ascii=False)

        self.assertIn("stock_ming_single_stock_analysis", encoded)
        self.assertEqual(len(payload["recent_news"]), 1)
        self.assertEqual(len(payload["research_links"]), 1)
        self.assertTrue(payload["analysis_requirements"]["no_fabricated_news"])

    def test_payload_compacts_backtest_dataframes_for_json(self):
        payload = build_ai_context_payload(
            {"ticker": "002158"},
            {},
            [],
            [],
            backtest_report={
                "summary": "mock",
                "metrics": {"total_return_pct": 1.5},
                "signals": pd.DataFrame({"date": pd.date_range("2026-01-01", periods=2), "signal": ["WAIT", "BUY"]}),
                "trades": pd.DataFrame({"date": pd.date_range("2026-01-02", periods=1), "action": ["BUY"]}),
            },
        )

        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)

        self.assertIn("backtest_report", encoded)
        self.assertNotIn("signals", payload["backtest_report"])
        self.assertEqual(payload["backtest_report"]["recent_trades"][0]["action"], "BUY")

    def test_payload_includes_cloud_memory_context(self):
        payload = build_ai_context_payload(
            {"ticker": "NVDA"},
            {},
            [],
            "",
            cloud_memory_context=[
                {
                    "memory_type": "strategy",
                    "match_level": "ticker",
                    "source": "manual-feed",
                    "core_view": "AI服务器订单需要验证",
                }
            ],
        )

        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)

        self.assertIn("cloud_memory_context", payload)
        self.assertEqual(payload["cloud_memory_context"][0]["match_level"], "ticker")
        self.assertIn("历史", payload["cloud_memory_usage_note"])
        self.assertIn("cloud_memory_context", encoded)


if __name__ == "__main__":
    unittest.main()
