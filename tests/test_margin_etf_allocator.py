import unittest

from margin_etf_allocator import calculate_margin_etf_allocation, get_margin_etf_catalog
from etf_data_engine import compare_etfs_within_theme, classify_etf_theme, fetch_etf_holdings_snapshot


class MarginEtfAllocatorTest(unittest.TestCase):
    def test_strong_trend_balanced_account_prefers_rebalance_when_stock_heavy(self):
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

        self.assertEqual(result["action_state"], "只允许调仓，不新增杠杆")
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
        self.assertEqual(result["action_state"], "融资过高，优先降杠杆")
        self.assertEqual(result["recommended_margin_ratio"], 0)
        self.assertTrue(result["risk_flags"])

    def test_catalog_contains_required_groups(self):
        catalog = get_margin_etf_catalog()

        self.assertIn("宽基ETF", catalog)
        self.assertIn("科技成长ETF", catalog)
        self.assertIn("金融券商ETF", catalog)
        self.assertIn("防守ETF", catalog)

    def test_dynamic_etf_scores_raise_growth_bucket(self):
        etf_scores = {
            "data_date": "20260526",
            "data_source": "tushare",
            "rows": [
                {"etf_code": "588000.SH", "etf_name": "科创50 ETF", "bucket": "科技成长ETF", "total_score": 82, "state": "强趋势", "return_20d_pct": 15, "volatility_20d": 18},
                {"etf_code": "512480.SH", "etf_name": "半导体 ETF", "bucket": "科技成长ETF", "total_score": 79, "state": "强趋势", "return_20d_pct": 12, "volatility_20d": 19},
                {"etf_code": "510300.SH", "etf_name": "沪深300 ETF", "bucket": "宽基ETF", "total_score": 63, "state": "温和向上", "return_20d_pct": 6, "volatility_20d": 14},
                {"etf_code": "510500.SH", "etf_name": "中证500 ETF", "bucket": "宽基ETF", "total_score": 61, "state": "温和向上", "return_20d_pct": 5, "volatility_20d": 15},
                {"etf_code": "515180.SH", "etf_name": "红利 ETF", "bucket": "防守ETF", "total_score": 54, "state": "震荡观察", "return_20d_pct": 1, "volatility_20d": 10},
                {"etf_code": "512400.SH", "etf_name": "有色 ETF", "bucket": "商品周期ETF", "total_score": 58, "state": "震荡观察", "return_20d_pct": 2, "volatility_20d": 20},
            ],
        }
        result = calculate_margin_etf_allocation(
            {
                "total_asset": 1000000,
                "cash_balance": 200000,
                "stock_market_value": 450000,
                "etf_market_value": 150000,
                "margin_debt": 80000,
                "available_margin": 50000,
                "maintenance_ratio": 250,
                "margin_interest_rate": 6.8,
                "max_drawdown_pct": 15,
            },
            "强趋势",
            {"style": "平衡", "leverage_mode": "中等使用"},
            etf_scores=etf_scores,
        )

        self.assertEqual(result["data_source"], "tushare")
        self.assertEqual(result["data_date"], "20260526")
        self.assertIn("科技成长ETF", result["dynamic_bucket_weights"])
        self.assertIn("科技成长ETF", result["overweight_buckets"])
        self.assertTrue(result["selected_etf_candidates"]["科技成长ETF"])
        self.assertTrue(result["daily_adjustment_reason"])

    def test_weak_scores_reduce_margin_ratio(self):
        weak_scores = {
            "data_date": "20260526",
            "data_source": "tushare",
            "rows": [
                {"etf_code": "588000.SH", "etf_name": "科创50 ETF", "bucket": "科技成长ETF", "total_score": 42, "state": "破位回避", "return_20d_pct": -8, "volatility_20d": 34},
                {"etf_code": "510300.SH", "etf_name": "沪深300 ETF", "bucket": "宽基ETF", "total_score": 48, "state": "震荡观察", "return_20d_pct": -3, "volatility_20d": 25},
                {"etf_code": "515180.SH", "etf_name": "红利 ETF", "bucket": "防守ETF", "total_score": 51, "state": "温和向上", "return_20d_pct": 2, "volatility_20d": 9},
                {"etf_code": "512400.SH", "etf_name": "有色 ETF", "bucket": "商品周期ETF", "total_score": 44, "state": "震荡观察", "return_20d_pct": -5, "volatility_20d": 31},
            ],
        }
        result = calculate_margin_etf_allocation(
            {
                "total_asset": 1000000,
                "cash_balance": 250000,
                "stock_market_value": 300000,
                "etf_market_value": 150000,
                "margin_debt": 50000,
                "available_margin": 80000,
                "maintenance_ratio": 250,
                "margin_interest_rate": 6.8,
                "max_drawdown_pct": 15,
            },
            "强趋势",
            {"style": "平衡", "leverage_mode": "中等使用"},
            etf_scores=weak_scores,
        )

        self.assertLess(result["recommended_margin_ratio"], 17.5)
        self.assertGreaterEqual(result["recommended_cash_ratio"], 15)
        self.assertTrue(any("趋势偏弱" in item for item in result["daily_adjustment_reason"]))

    def test_input_snapshot_uses_current_margin_fields(self):
        result = calculate_margin_etf_allocation(
            {
                "total_asset": 1000000,
                "cash_balance": 200000,
                "stock_market_value": 450000,
                "etf_market_value": 150000,
                "margin_debt": 80000,
                "available_margin": 50000,
                "maintenance_ratio": 250,
                "margin_interest_rate": 7.0,
                "max_drawdown_pct": 15,
            },
            "强趋势",
            {"style": "平衡", "leverage_mode": "中等使用"},
        )

        self.assertEqual(result["input_snapshot"]["available_margin"], 50000)
        self.assertEqual(result["input_snapshot"]["maintenance_ratio"], 250)
        self.assertEqual(result["input_snapshot"]["margin_interest_rate"], 7.0)
        self.assertTrue(result["input_snapshot"]["available_margin_provided"])
        self.assertTrue(result["input_snapshot"]["maintenance_ratio_provided"])
        self.assertFalse(any("未填写" in item for item in result["notes"]))
        self.assertTrue(any("7.00%" in item for item in result["trigger_conditions"]))

    def test_aggressive_style_in_strong_trend_is_not_forced_to_rebalance(self):
        result = calculate_margin_etf_allocation(
            {
                "total_asset": 1000000,
                "cash_balance": 250000,
                "stock_market_value": 350000,
                "etf_market_value": 250000,
                "margin_debt": 50000,
                "available_margin": 120000,
                "maintenance_ratio": 260,
                "margin_interest_rate": 7.0,
                "max_drawdown_pct": 15,
            },
            "强趋势",
            {"style": "进攻", "leverage_mode": "中等使用"},
        )

        self.assertIn(result["action_state"], {"可小幅融资进攻", "可中等融资进攻", "可用现金进攻，暂不加融资"})
        self.assertNotEqual(result["action_state"], "只允许调仓，不新增杠杆")
        self.assertEqual(result["style_tilt"], "偏进攻")

    def test_classify_semiconductor_equipment_etf(self):
        result = classify_etf_theme(
            {
                "name": "半导体设备ETF广发",
                "benchmark": "国证半导体设备指数",
                "index_code": "980001",
                "fund_type": "股票型ETF",
            }
        )

        self.assertEqual(result["bucket"], "科技成长ETF")
        self.assertEqual(result["theme"], "半导体/芯片")
        self.assertEqual(result["sub_theme"], "半导体设备")

    def test_classify_scitech_semiconductor_etf(self):
        result = classify_etf_theme(
            {
                "name": "科创半导体ETF华夏",
                "benchmark": "科创半导体指数",
                "index_name": "科创半导体指数",
                "fund_type": "股票型ETF",
            }
        )

        self.assertEqual(result["bucket"], "科技成长ETF")
        self.assertEqual(result["theme"], "半导体/芯片")
        self.assertEqual(result["sub_theme"], "科创半导体")

    def test_classify_cross_market_semiconductor_etf(self):
        result = classify_etf_theme(
            {
                "name": "中韩半导体ETF华泰柏瑞",
                "benchmark": "KRX中韩半导体指数",
                "index_name": "KRX中韩半导体指数",
                "fund_type": "QDII-ETF",
                "invest_type": "QDII",
            }
        )

        self.assertEqual(result["bucket"], "科技成长ETF")
        self.assertEqual(result["theme"], "半导体/芯片")
        self.assertEqual(result["sub_theme"], "中韩半导体")

    def test_classify_chip_industry_etf(self):
        result = classify_etf_theme(
            {
                "name": "广发国证半导体芯片ETF",
                "benchmark": "国证半导体芯片指数",
                "index_name": "国证半导体芯片指数",
                "fund_type": "股票型ETF",
            }
        )

        self.assertEqual(result["bucket"], "科技成长ETF")
        self.assertEqual(result["theme"], "半导体/芯片")
        self.assertEqual(result["sub_theme"], "芯片产业")

    def test_classify_chip_etf_not_wide(self):
        result = classify_etf_theme(
            {
                "name": "芯片ETF华夏",
                "benchmark": "中证芯片产业指数",
                "index_name": "中证芯片产业指数",
                "fund_type": "股票型ETF",
            }
        )

        self.assertEqual(result["bucket"], "科技成长ETF")
        self.assertEqual(result["theme"], "半导体/芯片")
        self.assertEqual(result["sub_theme"], "芯片产业")

    def test_classify_broker_etf(self):
        result = classify_etf_theme(
            {
                "name": "证券ETF",
                "benchmark": "中证全指证券公司指数",
                "index_code": "399975",
                "fund_type": "股票型ETF",
            }
        )

        self.assertEqual(result["bucket"], "金融券商ETF")
        self.assertEqual(result["theme"], "券商/证券")

    def test_classify_broker_etf_512000_sh(self):
        result = classify_etf_theme(
            {
                "name": "券商ETF",
                "benchmark": "中证全指证券公司指数",
                "index_name": "中证全指证券公司指数",
                "fund_type": "股票型ETF",
            }
        )

        self.assertEqual(result["bucket"], "金融券商ETF")
        self.assertEqual(result["theme"], "券商/证券")

    def test_classify_manager_name_with_securities_company_does_not_override_benchmark(self):
        result = classify_etf_theme(
            {
                "name": "中银证券中证500ETF",
                "benchmark": "中证500指数",
                "index_name": "中证500",
                "fund_type": "股票型ETF",
            }
        )

        self.assertEqual(result["bucket"], "宽基ETF")
        self.assertEqual(result["theme"], "宽基")
        self.assertIn("跟踪指数/benchmark", result["classification_reason"])

    def test_compare_etfs_within_theme_returns_multiple_products(self):
        score_packet = {
            "rows": [
                {
                    "etf_code": "512480.SH",
                    "etf_name": "半导体ETF",
                    "bucket": "科技成长ETF",
                    "theme": "半导体/芯片",
                    "sub_theme": "半导体/芯片",
                    "manager": "华夏",
                    "benchmark": "中证全指半导体指数",
                    "latest_price": 1.2,
                    "return_20d_pct": 10,
                    "return_60d_pct": 22,
                    "amount_ma20": 180000,
                    "volatility_20d": 18,
                    "trend_score": 28,
                    "total_score": 82,
                    "state": "强趋势",
                    "data_completeness": 95,
                },
                {
                    "etf_code": "560780.SH",
                    "etf_name": "半导体设备ETF广发",
                    "bucket": "科技成长ETF",
                    "theme": "半导体/芯片",
                    "sub_theme": "半导体设备",
                    "manager": "广发",
                    "benchmark": "国证半导体设备指数",
                    "latest_price": 0.98,
                    "return_20d_pct": 8,
                    "return_60d_pct": 18,
                    "amount_ma20": 92000,
                    "volatility_20d": 16,
                    "trend_score": 24,
                    "total_score": 77,
                    "state": "温和向上",
                    "data_completeness": 93,
                },
            ]
        }

        result = compare_etfs_within_theme(score_packet, theme="半导体/芯片")

        self.assertEqual(result["theme"], "半导体/芯片")
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["best_liquidity_etf"], "512480.SH")
        self.assertTrue(result["comparison_reason"])

    def test_holdings_snapshot_graceful_degradation_without_adapter(self):
        result = fetch_etf_holdings_snapshot(["512480.SH", "560780.SH"], tushare_adapter=None)

        self.assertFalse(result["holdings_available"])
        self.assertTrue(result["holdings_errors"])


if __name__ == "__main__":
    unittest.main()
