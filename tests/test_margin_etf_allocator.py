import unittest

from margin_etf_allocator import calculate_margin_etf_allocation, get_margin_etf_catalog


class MarginEtfAllocatorTest(unittest.TestCase):
    def test_strong_trend_balanced_account_allows_small_margin(self):
        result = calculate_margin_etf_allocation(
            {
                "total_asset": 1000000,
                "cash_balance": 200000,
                "stock_market_value": 600000,
                "etf_market_value": 100000,
                "margin_debt": 100000,
                "available_margin": 0,
                "maintenance_ratio": 0,
                "margin_interest_rate": 6.8,
                "max_drawdown_pct": 15,
            },
            "强趋势",
            {"style": "平衡", "leverage_mode": "中等使用"},
        )

        self.assertEqual(result["action_state"], "只允许调仓")
        self.assertGreater(result["recommended_margin_ratio"], 0)
        self.assertIn("宽基ETF", result["recommended_etf_allocation"])
        self.assertIn("科技成长ETF", result["recommended_etf_allocation"])
        self.assertGreater(result["risk_budget_score"], 0)

    def test_weak_market_high_margin_forces_deleverage(self):
        result = calculate_margin_etf_allocation(
            {
                "total_asset": 1000000,
                "cash_balance": 100000,
                "stock_market_value": 700000,
                "etf_market_value": 100000,
                "margin_debt": 450000,
                "available_margin": 5000,
                "maintenance_ratio": 170,
                "margin_interest_rate": 7.2,
                "max_drawdown_pct": 10,
            },
            "弱势",
            {"style": "进攻", "leverage_mode": "火力全开，但默认关闭"},
        )

        self.assertTrue(result["need_deleverage"])
        self.assertEqual(result["action_state"], "融资过高，建议降杠杆")
        self.assertEqual(result["recommended_margin_ratio"], 0)
        self.assertTrue(result["risk_flags"])

    def test_catalog_contains_required_groups(self):
        catalog = get_margin_etf_catalog()

        self.assertIn("宽基ETF", catalog)
        self.assertIn("科技成长ETF", catalog)
        self.assertIn("防守ETF", catalog)


if __name__ == "__main__":
    unittest.main()
