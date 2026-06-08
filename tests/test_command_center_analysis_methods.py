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
        for ticker in ["560780.SH", "159801.SZ"]:
            with self.subTest(ticker=ticker):
                packet = methods.build_analysis_method_packet(
                    ticker=ticker,
                    live_packet={"margin_etf": {"status": "ready"}},
                    now="2026-06-01T09:30:00",
                )

                self.assertEqual(packet["market"], "ETF")
                by_name = {item["name"]: item for item in packet["methods"]}
                self.assertEqual(by_name["ETF 赛道配置"]["status"], "通过")
                self.assertIn("跟踪指数", json.dumps(packet, ensure_ascii=False))

    def test_internal_app_market_aliases_map_to_profiles(self):
        a_share = methods.build_analysis_method_packet(market_type="A_SHARE_SH", ticker="002008.SS")
        us_stock = methods.build_analysis_method_packet(market_type="US_STOCK", ticker="AAPL")

        self.assertEqual(a_share["market"], "A股")
        self.assertEqual(us_stock["market"], "美股")
        self.assertIn("龙虎榜", json.dumps(a_share, ensure_ascii=False))
        self.assertIn("52周新高", json.dumps(us_stock, ensure_ascii=False))

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

    def test_unknown_market_does_not_pretend_to_be_a_share_or_us_stock(self):
        packet = methods.build_analysis_method_packet(market_type="", ticker="", now="2026-06-01T09:30:00")

        self.assertEqual(packet["market"], "未知")
        self.assertIn("等待数据刷新", packet["summary"])
        self.assertFalse(packet["deepseek_called"])

    def test_home_summary_keeps_a_share_method_layer_visible(self):
        packet = methods.build_analysis_method_packet(
            ticker="002008.SZ",
            live_packet={"market": {"status": "ready"}, "quant": {"status": "ready"}},
            strategy_packet={"status": "ready", "action": "等待验证"},
            decision_packet={"status": "ready", "overall_action": "只观察"},
            now="2026-06-01T09:30:00",
        )
        view_model = methods.build_home_analysis_method_summary(packet)
        dumped = json.dumps(view_model, ensure_ascii=False)

        self.assertEqual(view_model["market"], "A股")
        self.assertIn("A股个股", view_model["headline"])
        self.assertIn("资金流", dumped)
        self.assertIn("MA20", dumped)
        self.assertFalse(view_model["deepseek_called"])
        self.assertNotIn("packet", dumped)

    def test_home_summary_keeps_us_stock_terms_separate_from_a_share(self):
        packet = methods.build_analysis_method_packet(
            ticker="AAPL",
            live_packet={"market": {"status": "ready"}},
            now="2026-06-01T09:30:00",
        )
        view_model = methods.build_home_analysis_method_summary(packet)
        dumped = json.dumps(view_model, ensure_ascii=False)

        self.assertEqual(view_model["market"], "美股")
        self.assertIn("美股个股", view_model["headline"])
        self.assertIn("52周新高", dumped)
        self.assertIn("财报", dumped)
        self.assertNotIn("龙虎榜", dumped)
        self.assertNotIn("涨跌停", dumped)
        self.assertFalse(view_model["deepseek_called"])

    def test_home_summary_keeps_etf_allocation_prominent(self):
        packet = methods.build_analysis_method_packet(
            ticker="560780.SH",
            live_packet={"margin_etf": {"status": "ready"}},
            now="2026-06-01T09:30:00",
        )
        view_model = methods.build_home_analysis_method_summary(packet)
        dumped = json.dumps(view_model, ensure_ascii=False)

        self.assertEqual(view_model["market"], "ETF")
        self.assertIn("ETF / 基金", view_model["headline"])
        self.assertIn("ETF 赛道配置", dumped)
        self.assertIn("流动性", dumped)
        self.assertFalse(view_model["deepseek_called"])

    def test_chokepoint_score_matrix_has_15_dimensions(self):
        weights = methods.get_chokepoint_score_weights()

        self.assertEqual(len(weights), 15)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)
        self.assertIn("customer_qualification_strictness", weights)
        self.assertIn("supplier_scarcity", weights)

    def test_chokepoint_prompt_forces_cold_filter_and_downgrade(self):
        prompt_packet = methods.build_chokepoint_prompt_packet("英伟达金刚石散热")
        prompt = prompt_packet["prompt"]

        self.assertIn("半导体级大尺寸 CVD", prompt)
        self.assertIn("培育钻石", prompt)
        self.assertIn(methods.FORCED_DOWNGRADE_MESSAGE, prompt)
        self.assertFalse(prompt_packet["deepseek_called"])

    def test_precision_downgrade_rejects_broad_diamond_candidate(self):
        candidates = methods.apply_precision_downgrade_to_candidates(
            [
                {
                    "name": "力量钻石",
                    "ticker": "301071.SZ",
                    "tier": "Tier 1 真瓶颈",
                    "evidence_level": "新闻线索",
                    "substantive_capacity_evidence": True,
                    "matched_node": "培育钻石",
                }
            ]
        )

        self.assertTrue(candidates[0]["downgrade_required"])
        self.assertEqual(candidates[0]["tier"], "Tier 3 情绪蹭热点")
        self.assertEqual(candidates[0]["downgrade_notice"], methods.FORCED_DOWNGRADE_MESSAGE)

    def test_bayesian_trigger_updates_money_flow_and_hard_disclosure_differently(self):
        money_only = methods.trigger_bayesian_chokepoint_update(
            "300179.SZ",
            money_flow_event={"source": "money_flow_tracker", "event_type": "money_flow", "主力净流入": 50000000},
            now="2026-06-01T09:30:00",
        )
        hard_disclosure = methods.trigger_bayesian_chokepoint_update(
            "300179.SZ",
            data_fetcher_event={
                "source": "data_fetcher",
                "event_type": "announcement",
                "text": "公告披露半导体级 CVD 产线投资、新增设备订单和客户认证进展。",
            },
            now="2026-06-01T09:30:00",
        )

        self.assertGreater(money_only["dimension_scores"]["a_share_microstructure_heat"], 35)
        self.assertGreater(hard_disclosure["posterior_probability"], money_only["posterior_probability"])
        self.assertGreater(hard_disclosure["dimension_scores"]["disclosure_evidence_quality"], 30)

    def test_chokepoint_scan_packet_parses_json_and_keeps_anti_thesis(self):
        raw = json.dumps(
            {
                "specificity_status": "ok",
                "technical_chokepoint_nodes": [
                    {
                        "node": "半导体级大尺寸 CVD 金刚石衬底",
                        "why_it_blocks": "高热流密度散热需要低缺陷衬底",
                        "technical_specificity": "CVD 生长和良率爬坡",
                    }
                ],
                "candidate_stocks": [
                    {
                        "name": "四方达",
                        "ticker": "300179.SZ",
                        "tier": "Tier 2 待核实瓶颈",
                        "substantive_capacity_evidence": False,
                    }
                ],
                "anti_thesis": ["设备周期长", "客户认证失败", "资金拔估值套现"],
            },
            ensure_ascii=False,
        )

        packet = methods.build_chokepoint_scan_packet("英伟达金刚石散热", raw_llm_response=raw, ticker="300179.SZ")

        self.assertEqual(packet["specificity_status"], "ok")
        self.assertTrue(packet["deepseek_called"])
        self.assertEqual(len(packet["anti_thesis"]), 3)
        self.assertTrue(packet["candidate_stocks"][0]["downgrade_required"])
        json.dumps(packet, ensure_ascii=False)

    def test_advanced_pricing_interfaces_return_json_friendly_payloads(self):
        jump = methods.calculate_jump_diffusion(
            spot_price=20,
            drift=0.05,
            volatility=0.45,
            jump_intensity=1.2,
            jump_mean=0.10,
            horizon_days=20,
        )
        option = methods.calculate_real_options(
            project_value=100,
            exercise_cost=70,
            time_to_expiry_years=2,
            volatility=0.8,
        )

        self.assertGreater(jump["expected_terminal_price"], 0)
        self.assertGreater(option["option_value"], 0)
        json.dumps({"jump": jump, "option": option}, ensure_ascii=False)

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
