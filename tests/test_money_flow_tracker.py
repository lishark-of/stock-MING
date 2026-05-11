import unittest
import sys
import types

sys.modules.setdefault(
    "yfinance",
    types.SimpleNamespace(Ticker=lambda *args, **kwargs: None),
)

from money_flow_tracker import money_flow_coverage


class MoneyFlowTrackerTest(unittest.TestCase):
    def test_a_share_coverage_uses_a_share_fields(self):
        coverage = money_flow_coverage(
            {
                "market_type": "A_SHARE",
                "individual_fund_flow": [{"net": 1}],
                "dragon_tiger": [],
                "block_trade": [{"discount": -2}],
            }
        )

        self.assertEqual(coverage["score"], 66)
        self.assertIn("individual_fund_flow", coverage["available"])
        self.assertIn("dragon_tiger", coverage["missing"])

    def test_hk_coverage_uses_volume_signal(self):
        coverage = money_flow_coverage({"market_type": "HK_STOCK", "volume_signal": {"volume_vs_20d": 1.4}})

        self.assertEqual(coverage["score"], 100)
        self.assertEqual(coverage["available"], ["volume_signal"])


if __name__ == "__main__":
    unittest.main()
