import json
import unittest
from pathlib import Path

import command_center_factor_research as factor_research
from config import DEEPSEEK_MODEL_DEFAULTS


class CommandCenterFactorResearchTests(unittest.TestCase):
    def _daily_packet(self, count=70):
        rows = []
        for idx in range(count):
            close = 10 + idx * 0.1
            rows.append(
                {
                    "trade_date": f"2026-03-{(idx % 28) + 1:02d}",
                    "open": close - 0.05,
                    "high": close + 0.12,
                    "low": close - 0.18,
                    "close": close,
                    "vol": 1000 + idx * 10,
                    "amount": 5000 + idx * 30,
                }
            )
        return {"status": "ready", "rows": rows, "row_count": len(rows), "is_real_market_series": True}

    def _daily_basic_packet(self):
        return {
            "status": "ready",
            "rows": [
                {
                    "trade_date": "20260608",
                    "turnover_rate": 3.2,
                    "pe_ttm": 28.5,
                    "pb": 2.1,
                    "ps_ttm": 4.3,
                }
            ],
        }

    def _trade_calendar_packet(self):
        return {
            "status": "ready",
            "rows": [
                {"cal_date": "20260610", "is_open": 1},
                {"cal_date": "20260611", "is_open": 1},
                {"cal_date": "20260612", "is_open": 1},
                {"cal_date": "20260613", "is_open": 0},
                {"cal_date": "20260614", "is_open": 0},
                {"cal_date": "20260615", "is_open": 1},
            ],
        }

    def test_factor_library_is_local_research_only_scaffold(self):
        packet = factor_research.build_factor_library_packet(now="2026-06-09T10:00:00")

        self.assertEqual(packet["packet_key"], "command_center_factor_library_packet")
        self.assertEqual(packet["updated_at"], "2026-06-09T10:00:00")
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertGreaterEqual(packet["factor_count"], 20)
        self.assertLessEqual(packet["factor_count"], 30)
        keys = {item["factor_key"] for item in packet["factors"]}
        self.assertIn("serenity_method_source", keys)
        json.dumps(packet, ensure_ascii=False)

    def test_every_factor_has_required_research_fields_and_no_core_action_usage(self):
        packet = factor_research.build_factor_library_packet()

        for factor in packet["factors"]:
            with self.subTest(factor_key=factor.get("factor_key")):
                self.assertTrue(factor.get("factor_key"))
                self.assertTrue(factor.get("factor_name"))
                self.assertTrue(factor.get("category"))
                self.assertTrue(factor.get("formula_summary"))
                self.assertTrue(factor.get("source_interfaces"))
                self.assertIn("PIT_safe", factor)
                self.assertTrue(factor.get("pit_requirement"))
                self.assertFalse(factor.get("pit_validated"))
                self.assertTrue(factor.get("lookahead_risk_note"))
                self.assertIn(factor.get("first_stage_usage"), {"research_only", "evidence_effect_only"})
                self.assertFalse(factor["enters_core_action"])
                self.assertFalse(factor["enters_strategy_action"])
                self.assertFalse(factor["enters_next_session_projection"])
                self.assertFalse(factor["enters_deepseek_prompt"])

    def test_decision_usage_policy_blocks_trading_projection_and_deepseek_paths(self):
        for packet in [
            factor_research.build_factor_library_packet(),
            factor_research.build_factor_data_ledger_packet(),
            factor_research.build_factor_governance_packet(),
        ]:
            policy = packet["decision_usage_policy"]
            self.assertTrue(policy["display_only"])
            self.assertFalse(policy["enters_strategy_action"])
            self.assertFalse(policy["enters_core_action"])
            self.assertFalse(policy["enters_next_session_projection"])
            self.assertFalse(policy["enters_evidence_effects"])
            self.assertFalse(policy["enters_deepseek_prompt"])
            self.assertIn("不作为交易指令", policy["note"])

    def test_data_ledger_uses_available_packet_presence_without_fetching(self):
        library = factor_research.build_factor_library_packet()
        ledger = factor_research.build_factor_data_ledger_packet(
            factor_library=library,
            available_packets={
                "daily_close_packet": {"status": "cached"},
                "command_center_moneyflow_packet": {"status": "cached"},
            },
            now="2026-06-09T10:30:00",
        )
        by_key = {row["factor_key"]: row for row in ledger["ledger_rows"]}

        self.assertEqual(ledger["packet_key"], "command_center_factor_data_ledger_packet")
        self.assertEqual(ledger["updated_at"], "2026-06-09T10:30:00")
        self.assertFalse(ledger["deepseek_called"])
        self.assertFalse(ledger["tushare_called"])
        self.assertFalse(ledger["external_calls_triggered"])
        self.assertEqual(by_key["momentum_20d"]["status"], "verified_present")
        self.assertFalse(by_key["momentum_20d"]["pit_validated"])
        self.assertFalse(by_key["momentum_20d"]["point_in_time_safe"])
        self.assertEqual(by_key["main_net_5d"]["status"], "verified_present")
        self.assertEqual(by_key["roe_latest"]["status"], "not_loaded")
        self.assertIn("公告日期", by_key["roe_latest"]["pit_requirement"])
        self.assertIn("公告日错位", by_key["roe_latest"]["lookahead_risk_note"])
        for row in ledger["ledger_rows"]:
            self.assertFalse(row["enters_strategy_action"])
            self.assertFalse(row["enters_core_action"])
            self.assertFalse(row["enters_next_session_projection"])
            self.assertFalse(row["enters_deepseek_prompt"])

    def test_governance_defaults_allow_only_research_display(self):
        packet = factor_research.build_factor_governance_packet()

        self.assertTrue(packet["allow_research_display"])
        self.assertFalse(packet["allow_evidence_effects"])
        self.assertFalse(packet["allow_strategy_trace"])
        self.assertFalse(packet["allow_core_action"])
        self.assertIn("因子研究不是交易建议。", packet["risk_boundaries"])

    def test_factor_research_does_not_enter_strategy_projection_or_deepseek_modules(self):
        blocked_files = [
            "strategy_execution_service.py",
            "command_center_next_session_projection.py",
            "analysis_engine.py",
            "command_center_strategy_summary.py",
        ]
        for filename in blocked_files:
            with self.subTest(filename=filename):
                source = Path(filename).read_text(encoding="utf-8")
                self.assertNotIn("command_center_factor_library_packet", source)
                self.assertNotIn("command_center_factor_data_ledger_packet", source)
                self.assertNotIn("factor_research_service", source)

        app_source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("_render_factor_research_lab_panel", app_source)
        self.assertIn("factor_research_service.build_factor_library_packet", app_source)
        self.assertIn("factor_research_service.build_factor_quant_hub_packet", app_source)
        self.assertIn("PIT要求", app_source)
        self.assertIn("治理边界", app_source)
        self.assertIn("2.0 多因子量化图谱", app_source)
        self.assertIn("多因子量化不是交易建议", app_source)
        self.assertIn("不修改 strategy action、价格、持仓或 operation_zones", app_source)
        self.assertIn("查看已缓存多因子图谱（不刷新）", app_source)
        self.assertIn("生成 2.0 多因子量化图谱", app_source)
        self.assertIn("刷新因子数据", app_source)
        self.assertIn("运行 light mode 因子计算", app_source)
        self.assertIn("DeepSeek 整理因子解释", app_source)
        self.assertIn("available_count = max(0", app_source)
        self.assertIn("_factor_table_dataframe", app_source)
        self.assertIn("只读 session/cache；不调用 Tushare、DeepSeek、GitHub。", app_source)
        self.assertIn("按钮门控 Tushare；写入 call_ledger。", app_source)
        self.assertIn("只解释已有结构化结果，不覆盖数值。", app_source)
        self.assertIn("factor evidence 只作为 evidence_effects 预览", app_source)
        self.assertNotIn("运行因子回测", app_source)
        self.assertNotIn("按因子买入", app_source)
        self.assertNotIn("按因子卖出", app_source)

    def test_cache_only_factor_quant_ui_does_not_set_refresh_flags(self):
        source = Path("app.py").read_text(encoding="utf-8")
        cache_block = source.split('cache_only_clicked = st.button("查看已缓存多因子图谱（不刷新）"', 1)[1].split("if refresh_clicked:", 1)[0]

        self.assertIn("if cache_only_clicked:", cache_block)
        self.assertNotIn("_refresh_factor_data_packets", cache_block)
        self.assertNotIn("call_deepseek_non_stream", cache_block)
        self.assertNotIn("probe_github", cache_block.lower())
        self.assertNotIn("refresh_summary", cache_block)

    def test_quant_hub_cache_only_schema_does_not_call_external_sources(self):
        packet = factor_research.build_factor_quant_hub_packet(mode="cache_only", now="2026-06-09T11:00:00")

        self.assertEqual(packet["packet_key"], "command_center_factor_quant_hub_packet")
        self.assertEqual(packet["schema_version"], "factor_quant_hub.v1")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertEqual(packet["runtime"]["available_count"], 0)
        self.assertEqual(packet["runtime"]["missing_count"], len(packet["factor_library"]["factors"]))
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_action"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_operation_zones"])
        self.assertFalse(packet["governance"]["allow_core_action"])
        json.dumps(packet, ensure_ascii=False)

    def test_light_runtime_computes_daily_factors_and_degrades_rank_without_universe(self):
        library = factor_research.build_factor_library_packet()
        runtime = factor_research.build_factor_runtime_packet(
            factor_library=library,
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            moneyflow_packet={"main_net_yi": 1.2},
            mode="light",
            now="2026-06-09T11:05:00",
        )
        values = {item["factor_key"]: item for item in runtime["factor_values"]}

        self.assertIn(values["momentum_20d"]["effect"], {"support", "neutral", "suppress"})
        self.assertEqual(values["amount_20d_rank"]["data_status"], "degraded")
        self.assertIsNone(values["amount_20d_rank"]["zscore"])
        self.assertIsNone(values["amount_20d_rank"]["rank_pct"])
        self.assertEqual(values["turnover_rate"]["raw_value"], 3.2)
        self.assertEqual(values["roe_latest"]["data_status"], "pending_pit")
        self.assertFalse(values["roe_latest"]["pit_validated"])

    def test_factor_test_lab_scaffold_declares_research_metrics_without_external_calls(self):
        packet = factor_research.build_factor_test_packet(mode="light", now="2026-06-09T11:07:00")

        self.assertEqual(packet["packet_key"], "command_center_factor_test_packet")
        self.assertEqual(packet["schema_version"], "factor_test.v2")
        self.assertEqual(packet["phase"], "phase_3_factor_test_lab_scaffold")
        self.assertEqual(packet["status"], "scaffold_ready")
        self.assertEqual(packet["updated_at"], "2026-06-09T11:07:00")
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertFalse(packet["governance"]["allow_core_action"])
        self.assertFalse(packet["governance"]["allow_strategy_trace"])
        self.assertFalse(packet["governance"]["allow_evidence_effects"])

        metric_keys = {item["metric_key"] for item in packet["metric_schema"]}
        self.assertTrue(
            {
                "ic_mean",
                "rank_ic_mean",
                "icir",
                "top_bottom_group_return",
                "group_return_buckets",
                "turnover",
                "cost_adjusted_return",
                "max_drawdown",
                "industry_neutral_ic",
                "market_cap_neutral_ic",
                "sample_split_stability",
                "pit_check",
                "lookahead_check",
            }.issubset(metric_keys)
        )
        self.assertGreaterEqual(len(packet["items"]), 20)
        self.assertEqual(packet["status_counts"]["not_enough_data"], len(packet["items"]))
        self.assertEqual(packet["quality_summary"]["status"], "scaffold_only")
        self.assertEqual(packet["quality_summary"]["computed_item_count"], 0)
        self.assertEqual(packet["quality_summary"]["not_enough_data_count"], len(packet["items"]))
        self.assertFalse(packet["quality_summary"]["allow_core_action"])
        self.assertFalse(packet["quality_summary"]["allow_strategy_trace"])
        self.assertEqual(packet["window_summary"]["valid_pair_count"], 0)
        self.assertGreater(packet["required_metric_gap_counts"]["ic_mean"], 0)
        self.assertIn("small_research", {item["mode"] for item in packet["mode_plan"]})
        self.assertIn("full", {item["mode"] for item in packet["mode_plan"]})
        self.assertEqual(packet["call_ledger"][0]["api"], "local_factor_test_lab_scaffold")
        self.assertFalse(packet["call_ledger"][0]["external"])
        self.assertIn("回测收益不代表未来收益", " ".join(packet["warnings"]))
        json.dumps(packet, ensure_ascii=False)

    def test_factor_test_lab_classifies_supplied_metrics_without_action_leakage(self):
        packet = factor_research.build_factor_test_packet(
            mode="light",
            items=[
                {
                    "factor_key": "momentum_20d",
                    "coverage": 0.92,
                    "missing_rate": 0.04,
                    "ic_mean": 0.031,
                    "ic_std": 0.08,
                    "icir": 0.42,
                    "rank_ic_mean": 0.028,
                    "top_bottom_group_return": 0.055,
                    "group_return_monotonicity": True,
                    "turnover": 0.3,
                    "cost_adjusted_return": 0.032,
                    "max_drawdown": -0.08,
                    "industry_neutral_ic": 0.021,
                    "market_cap_neutral_ic": 0.019,
                    "pit_check": "passed",
                    "lookahead_check": "passed",
                    "strategy_action": "buy",
                    "price": 99,
                },
                {
                    "factor_key": "roe_latest",
                    "coverage": 0.91,
                    "missing_rate": 0.03,
                    "ic_mean": 0.04,
                    "ic_std": 0.1,
                    "icir": 0.5,
                    "rank_ic_mean": 0.04,
                    "top_bottom_group_return": 0.06,
                    "group_return_monotonicity": True,
                    "cost_adjusted_return": 0.04,
                    "pit_check": "failed",
                    "lookahead_check": "pending",
                },
            ],
            now="2026-06-09T11:08:00",
        )
        by_key = {item["factor_key"]: item for item in packet["items"]}

        self.assertEqual(by_key["momentum_20d"]["result_status"], "research_pass")
        self.assertEqual(by_key["roe_latest"]["result_status"], "invalid")
        self.assertNotIn("strategy_action", by_key["momentum_20d"])
        self.assertNotIn("price", by_key["momentum_20d"])
        self.assertFalse(by_key["momentum_20d"]["enters_strategy_action"])
        self.assertFalse(by_key["momentum_20d"]["enters_core_action"])
        self.assertTrue(by_key["momentum_20d"]["does_not_modify_strategy_action"])

    def test_light_mode_factor_ic_metrics_compute_from_local_observations(self):
        observations = []
        for day_index, trade_date in enumerate(["20260601", "20260602", "20260603", "20260604"], start=1):
            for stock_index in range(1, 7):
                observations.append(
                    {
                        "factor_key": "momentum_20d",
                        "ts_code": f"00000{stock_index}.SZ",
                        "trade_date": trade_date,
                        "factor_value": stock_index * 0.1,
                        "forward_return": stock_index * 0.006 + day_index * 0.0003,
                        "transaction_cost": 0.001,
                        "turnover": 0.2 + stock_index * 0.01,
                        "pit_validated": True,
                        "lookahead_check": "passed",
                        "forward_return_horizon": "1d",
                        "strategy_action": "buy",
                    }
                )

        packet = factor_research.compute_light_mode_factor_ic_metrics(
            observations=observations,
            now="2026-06-09T11:09:00",
        )
        row = {item["factor_key"]: item for item in packet["items"]}["momentum_20d"]

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["computed_item_count"], 1)
        self.assertEqual(packet["quality_summary"]["status"], "computed_light_metrics_ready")
        self.assertEqual(packet["quality_summary"]["research_pass_count"], 1)
        self.assertGreater(packet["quality_summary"]["window_summary"]["valid_pair_count"], 0)
        self.assertFalse(packet["quality_summary"]["allow_core_action"])
        self.assertFalse(packet["quality_summary"]["allow_evidence_effects"])
        self.assertEqual(packet["required_metric_gap_counts"]["ic_mean"], len(packet["items"]) - 1)
        self.assertEqual(row["data_status"], "metric_supplied")
        self.assertEqual(row["result_status"], "research_pass")
        self.assertGreater(row["ic_mean"], 0.9)
        self.assertGreater(row["rank_ic_mean"], 0.9)
        self.assertGreater(row["icir"], 0)
        self.assertGreater(row["top_bottom_group_return"], 0)
        self.assertTrue(row["group_return_monotonicity"])
        self.assertEqual([bucket["bucket_key"] for bucket in row["group_return_buckets"]], ["bottom", "middle", "top"])
        self.assertEqual(sum(bucket["count"] for bucket in row["group_return_buckets"]), len(observations))
        self.assertLess(
            row["group_return_buckets"][0]["mean_forward_return"],
            row["group_return_buckets"][-1]["mean_forward_return"],
        )
        self.assertGreater(row["cost_adjusted_return"], 0)
        self.assertEqual(row["pit_check"], "passed")
        self.assertEqual(row["lookahead_check"], "passed")
        self.assertEqual(row["sample_split_stability"]["method"], "chronological_half_split_light_observations")
        self.assertEqual(row["sample_split_stability"]["early_window_date_count"], 2)
        self.assertEqual(row["sample_split_stability"]["recent_window_date_count"], 2)
        self.assertEqual(row["sample_split_stability"]["split_after_trade_date"], "20260602")
        self.assertIsNotNone(row["sample_split_stability"]["early_window_ic"])
        self.assertIsNotNone(row["sample_split_stability"]["recent_window_ic"])
        self.assertIn("light observations", row["sample_split_stability"]["status_note"])
        self.assertNotIn("strategy_action", row)
        self.assertFalse(row["enters_strategy_action"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])

    def test_light_mode_factor_ic_metrics_do_not_pass_without_pit_validation(self):
        observations = [
            {
                "factor_key": "momentum_20d",
                "ts_code": f"00000{index}.SZ",
                "trade_date": "20260601",
                "factor_value": index,
                "forward_return": index * 0.01,
                "pit_validated": False,
                "lookahead_check": "passed",
            }
            for index in range(1, 8)
        ]

        packet = factor_research.compute_light_mode_factor_ic_metrics(observations=observations)
        row = {item["factor_key"]: item for item in packet["items"]}["momentum_20d"]

        self.assertEqual(row["pit_check"], "pending")
        self.assertNotEqual(row["result_status"], "research_pass")
        self.assertFalse(row["enters_strategy_action"])
        self.assertFalse(row["enters_core_action"])

    def test_light_mode_factor_ic_metrics_compute_neutralized_research_metrics(self):
        observations = []
        industries = ["半导体", "设备"]
        for day_index, trade_date in enumerate(["20260601", "20260602", "20260603", "20260604"], start=1):
            for stock_index in range(1, 9):
                local_signal = (stock_index % 4) + day_index * 0.1
                observations.append(
                    {
                        "factor_key": "momentum_20d",
                        "ts_code": f"00000{stock_index}.SZ",
                        "trade_date": trade_date,
                        "factor_value": local_signal + stock_index * 0.03,
                        "forward_return": local_signal * 0.012 + stock_index * 0.0002,
                        "transaction_cost": 0.001,
                        "turnover": 0.18 + stock_index * 0.01,
                        "industry": industries[stock_index % 2],
                        "market_cap": 100 + stock_index * 20,
                        "pit_validated": True,
                        "lookahead_check": "passed",
                    }
                )

        packet = factor_research.compute_light_mode_factor_ic_metrics(
            observations=observations,
            now="2026-06-09T11:09:30",
        )
        row = {item["factor_key"]: item for item in packet["items"]}["momentum_20d"]

        self.assertIsNotNone(row["industry_neutral_ic"])
        self.assertIsNotNone(row["market_cap_neutral_ic"])
        self.assertEqual(row["neutralization_scope"]["industry"], "computed_light_observation_residual_ic")
        self.assertEqual(row["neutralization_scope"]["market_cap"], "computed_light_observation_residual_ic")
        self.assertIn(row["out_of_sample_stability"], {"stable", "weak_recent_window", "unstable_direction"})
        self.assertIn(row["recent_decay"], {"not_detected", "decaying"})
        self.assertFalse(row["enters_strategy_action"])
        self.assertFalse(packet["quality_summary"]["allow_core_action"])

    def test_missing_factors_enter_missing_not_suppress(self):
        runtime = factor_research.build_factor_runtime_packet(
            daily_close_packet={"rows": []},
            daily_basic_packet={},
            mode="light",
            now="2026-06-09T11:10:00",
        )
        score = factor_research.build_factor_score_packet(runtime_packet=runtime)

        self.assertGreater(len(score["missing_factors"]), 0)
        missing_keys = {item["factor_key"] for item in score["missing_factors"]}
        suppress_keys = {item["factor_key"] for item in score["suppress_factors"]}
        self.assertFalse(missing_keys & suppress_keys)

    def test_serenity_and_chokepoint_stay_research_context_and_out_of_composite_score(self):
        runtime = factor_research.build_factor_runtime_packet(
            daily_close_packet=self._daily_packet(),
            mode="light",
            now="2026-06-09T11:15:00",
        )
        values = {item["factor_key"]: item for item in runtime["factor_values"]}
        score = factor_research.build_factor_score_packet(runtime_packet=runtime)
        score_keys = {
            item["factor_key"]
            for group in ("support_factors", "suppress_factors", "neutral_factors")
            for item in score[group]
        }

        self.assertTrue(values["chokepoint_method_hint"]["excluded_from_score"])
        self.assertTrue(values["serenity_method_source"]["excluded_from_score"])
        self.assertNotIn("chokepoint_method_hint", score_keys)
        self.assertNotIn("serenity_method_source", score_keys)

    def test_quant_hub_links_research_context_and_builds_evidence_preview_only(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            chokepoint_packet={"summary": "瓶颈仅研究解释"},
            serenity_packet={"summary": "方法来源基线"},
            call_ledger=[{"api": "daily", "row_count": 70, "data_date": "20260608", "call_status": "verified_present"}],
            now="2026-06-09T11:20:00",
        )

        self.assertTrue(packet["research_context"]["chokepoint"]["available"])
        self.assertFalse(packet["research_context"]["chokepoint"]["enters_composite_score"])
        self.assertTrue(packet["research_context"]["serenity"]["available"])
        self.assertFalse(packet["research_context"]["serenity"]["enters_composite_score"])
        self.assertTrue(packet["next_session_bridge"]["enters_evidence_effects"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_action"])
        self.assertTrue(packet["tushare_called"])
        self.assertEqual(packet["call_ledger"][0]["api"], "daily")

    def test_stale_data_date_blocks_composite_score_support(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            moneyflow_packet={"main_net_yi": 1.2},
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20240131", "call_status": "success"},
                {"api": "daily_basic", "row_count": 22, "data_date": "20240131", "call_status": "success"},
                {"api": "moneyflow", "row_count": 22, "data_date": "20240131", "call_status": "success"},
            ],
            now="2026-06-12T10:00:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["status"], "expired")
        self.assertFalse(gate["usable_for_score"])
        self.assertGreater(gate["max_data_age_days"], 30)
        self.assertEqual(packet["runtime"]["status"], "stale_data")
        self.assertEqual(packet["runtime"]["available_count"], 0)
        self.assertIsNone(packet["score"]["composite_score"])
        self.assertEqual(packet["score"]["support_factors"], [])
        self.assertEqual(packet["score"]["suppress_factors"], [])
        self.assertEqual(packet["next_session_bridge"]["preview"], [])
        self.assertTrue(
            all(not item.get("enters_composite_score") for item in packet["runtime"]["factor_values"])
        )
        self.assertIn("数据时效门控未通过", " ".join(packet["warnings"]))

    def test_fresh_data_date_keeps_score_available(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            moneyflow_packet={"main_net_yi": 1.2},
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260612", "call_status": "success"},
                {"api": "daily_basic", "row_count": 22, "data_date": "20260612", "call_status": "success"},
                {"api": "moneyflow", "row_count": 22, "data_date": "20260612", "call_status": "success"},
            ],
            now="2026-06-12T17:00:00",
        )

        self.assertEqual(packet["data_freshness_gate"]["status"], "fresh")
        self.assertTrue(packet["data_freshness_gate"]["usable_for_score"])
        self.assertIsNotNone(packet["score"]["composite_score"])
        self.assertNotEqual(packet["runtime"]["status"], "stale_data")

    def test_a_share_calendar_uses_previous_trading_day_during_intraday(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=self._trade_calendar_packet(),
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260611", "call_status": "success"},
                {"api": "daily_basic", "row_count": 22, "data_date": "20260611", "call_status": "success"},
            ],
            now="2026-06-12T10:00:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["status"], "fresh")
        self.assertEqual(gate["expected_data_date"], "2026-06-11")
        self.assertEqual(gate["expected_data_date_source"], "previous_completed_trading_day")
        self.assertEqual(gate["latest_completed_trading_day"], "2026-06-11")
        self.assertEqual(gate["next_open_date"], "2026-06-15")
        self.assertEqual(gate["market_phase"], "intraday")
        self.assertEqual(gate["market_session_detail"], "morning_continuous_auction")
        self.assertTrue(gate["calendar_validated"])
        self.assertEqual(gate["calendar_coverage_status"], "validated")
        self.assertFalse(gate["calendar_requires_refresh"])
        self.assertTrue(gate["expected_data_date_available"])
        self.assertTrue(gate["expected_data_date_calendar_validated"])
        self.assertTrue(gate["previous_open_found"])
        self.assertTrue(gate["next_open_found"])
        self.assertFalse(gate["current_eod_available"])
        self.assertFalse(gate["data_update_delay_guard_active"])
        self.assertEqual(gate["data_update_delay_reason"], "intraday_uses_previous_completed_trading_day")
        self.assertEqual(packet["call_ledger"][0]["trading_day_lag"], 0)
        self.assertEqual(packet["call_ledger"][0]["freshness_reason"], "matches_expected_trading_day")
        self.assertFalse(packet["call_ledger"][0]["freshness_blocks_composite_score"])
        self.assertTrue(packet["linked_packets"]["trade_calendar_packet"])

    def test_a_share_calendar_lunch_break_still_uses_previous_trading_day(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=self._trade_calendar_packet(),
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260611", "call_status": "success"},
            ],
            now="2026-06-12T12:05:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["status"], "fresh")
        self.assertEqual(gate["market_phase"], "intraday")
        self.assertEqual(gate["market_session_detail"], "lunch_break")
        self.assertEqual(gate["expected_data_date"], "2026-06-11")
        self.assertFalse(gate["current_eod_available"])
        self.assertFalse(gate["data_update_delay_guard_active"])

    def test_a_share_calendar_pre_market_blocks_same_day_data(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=self._trade_calendar_packet(),
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260612", "call_status": "success"},
            ],
            now="2026-06-12T08:50:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["market_phase"], "pre_open")
        self.assertEqual(gate["market_session_detail"], "before_call_auction")
        self.assertEqual(gate["expected_data_date"], "2026-06-11")
        self.assertTrue(gate["pre_market_guard_active"])
        self.assertFalse(gate["session_allows_current_trading_day_data"])
        self.assertEqual(gate["data_update_delay_reason"], "pre_open_uses_previous_completed_trading_day")
        self.assertEqual(gate["status"], "future_unavailable")
        self.assertFalse(gate["usable_for_score"])
        self.assertEqual(packet["score"]["support_factors"], [])
        self.assertEqual(packet["next_session_bridge"]["preview"], [])

    def test_a_share_calendar_call_auction_blocks_same_day_data(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=self._trade_calendar_packet(),
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260612", "call_status": "success"},
            ],
            now="2026-06-12T09:20:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["market_phase"], "pre_open")
        self.assertEqual(gate["market_session_detail"], "opening_call_auction")
        self.assertEqual(gate["expected_data_date"], "2026-06-11")
        self.assertTrue(gate["pre_market_guard_active"])
        self.assertFalse(gate["session_allows_current_trading_day_data"])
        self.assertEqual(gate["status"], "future_unavailable")
        self.assertFalse(gate["usable_for_score"])

    def test_a_share_calendar_blocks_same_day_data_before_eod_ready(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=self._trade_calendar_packet(),
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260612", "call_status": "success"},
            ],
            now="2026-06-12T10:00:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["status"], "future_unavailable")
        self.assertFalse(gate["usable_for_score"])
        self.assertEqual(gate["expected_data_date"], "2026-06-11")
        self.assertIn("data_date_after_expected_trading_day", gate["blocking_reasons"])
        self.assertEqual(packet["call_ledger"][0]["freshness_reason"], "data_date_after_expected_trading_day")
        self.assertTrue(packet["call_ledger"][0]["freshness_blocks_composite_score"])
        self.assertEqual(packet["score"]["support_factors"], [])
        self.assertEqual(packet["next_session_bridge"]["preview"], [])

    def test_a_share_calendar_blocks_same_day_data_before_eod_ready_after_close(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=self._trade_calendar_packet(),
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260612", "call_status": "success"},
            ],
            now="2026-06-12T15:40:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["market_phase"], "post_close_pending_eod")
        self.assertEqual(gate["market_session_detail"], "post_close_data_delay_window")
        self.assertEqual(gate["expected_data_date"], "2026-06-11")
        self.assertFalse(gate["current_eod_available"])
        self.assertTrue(gate["data_update_delay_guard_active"])
        self.assertEqual(gate["data_update_delay_reason"], "post_close_before_data_ready_time")
        self.assertEqual(gate["status"], "future_unavailable")
        self.assertFalse(gate["usable_for_score"])

    def test_a_share_calendar_accepts_current_trade_date_after_data_ready(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=self._trade_calendar_packet(),
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260612", "call_status": "success"},
            ],
            now="2026-06-12T17:00:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["market_phase"], "post_close_data_ready")
        self.assertEqual(gate["market_session_detail"], "after_eod_data_ready")
        self.assertEqual(gate["expected_data_date"], "2026-06-12")
        self.assertEqual(gate["expected_data_date_source"], "current_trading_day_after_ready_time")
        self.assertTrue(gate["current_eod_available"])
        self.assertFalse(gate["data_update_delay_guard_active"])
        self.assertEqual(gate["data_update_delay_reason"], "after_ready_time_current_trading_day_allowed")
        self.assertEqual(gate["status"], "fresh")
        self.assertTrue(gate["usable_for_score"])

    def test_a_share_provider_delay_grace_blocks_previous_day_after_ready_time(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=self._trade_calendar_packet(),
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260611", "call_status": "success"},
            ],
            now="2026-06-12T17:00:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["status"], "provider_delay_grace")
        self.assertTrue(gate["provider_update_grace_active"])
        self.assertEqual(gate["provider_delay_grace_until"], "18:00")
        self.assertEqual(gate["expected_data_date"], "2026-06-12")
        self.assertFalse(gate["usable_for_score"])
        self.assertEqual(gate["provider_delay_grace_count"], 1)
        self.assertEqual(packet["call_ledger"][0]["freshness_reason"], "provider_delay_grace_previous_completed_trading_day")
        self.assertTrue(packet["call_ledger"][0]["freshness_blocks_composite_score"])
        self.assertIsNone(packet["score"]["composite_score"])
        self.assertEqual(packet["score"]["support_factors"], [])
        self.assertEqual(packet["next_session_bridge"]["preview"], [])

    def test_a_share_provider_delay_grace_expires_after_grace_window(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=self._trade_calendar_packet(),
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260611", "call_status": "success"},
            ],
            now="2026-06-12T18:30:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["status"], "stale")
        self.assertFalse(gate["provider_update_grace_active"])
        self.assertEqual(gate["provider_delay_grace_count"], 0)
        self.assertEqual(packet["call_ledger"][0]["freshness_reason"], "lags_expected_by_1_trading_days")
        self.assertFalse(gate["usable_for_score"])

    def test_a_share_calendar_weekend_expected_date_uses_last_open_day(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=self._trade_calendar_packet(),
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260612", "call_status": "success"},
            ],
            now="2026-06-13T11:00:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["status"], "fresh")
        self.assertEqual(gate["market_phase"], "market_closed")
        self.assertEqual(gate["market_session_detail"], "non_trading_day")
        self.assertEqual(gate["expected_data_date"], "2026-06-12")
        self.assertFalse(gate["today_is_trading_day"])
        self.assertEqual(gate["next_open_date"], "2026-06-15")
        self.assertEqual(gate["days_since_previous_open"], 1)
        self.assertEqual(gate["days_until_next_open"], 2)
        self.assertEqual(gate["market_closed_reason"], "trade_cal_marks_today_closed")
        self.assertTrue(gate["current_eod_available"])
        self.assertEqual(packet["call_ledger"][0]["days_since_previous_open"], 1)
        self.assertEqual(packet["call_ledger"][0]["days_until_next_open"], 2)

    def test_a_share_calendar_weekday_holiday_expected_date_uses_last_open_day(self):
        holiday_calendar = {
            "status": "ready",
            "rows": [
                {"cal_date": "20260611", "is_open": 1},
                {"cal_date": "20260612", "is_open": 0},
                {"cal_date": "20260615", "is_open": 1},
            ],
        }
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=holiday_calendar,
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260611", "call_status": "success"},
            ],
            now="2026-06-12T10:00:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["status"], "fresh")
        self.assertEqual(gate["market_phase"], "market_closed")
        self.assertEqual(gate["market_session_detail"], "non_trading_day")
        self.assertEqual(gate["expected_data_date"], "2026-06-11")
        self.assertFalse(gate["today_is_trading_day"])
        self.assertTrue(gate["calendar_validated"])
        self.assertEqual(gate["days_since_previous_open"], 1)
        self.assertEqual(gate["days_until_next_open"], 3)
        self.assertEqual(gate["market_closed_reason"], "trade_cal_marks_today_closed")
        self.assertEqual(packet["call_ledger"][0]["market_closed_reason"], "trade_cal_marks_today_closed")

    def test_a_share_calendar_missing_previous_open_blocks_current_evidence(self):
        incomplete_calendar = {
            "status": "ready",
            "rows": [
                {"cal_date": "20260612", "is_open": 1},
                {"cal_date": "20260615", "is_open": 1},
            ],
        }
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=incomplete_calendar,
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260612", "call_status": "success"},
            ],
            now="2026-06-12T10:00:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["status"], "unknown")
        self.assertFalse(gate["usable_for_score"])
        self.assertEqual(gate["expected_data_date"], None)
        self.assertFalse(gate["expected_data_date_available"])
        self.assertEqual(gate["expected_data_date_source"], "unavailable")
        self.assertEqual(gate["calendar_coverage_status"], "partial_missing_previous_open")
        self.assertTrue(gate["calendar_requires_refresh"])
        self.assertFalse(gate["previous_open_found"])
        self.assertTrue(gate["next_open_found"])
        self.assertIn("expected_data_date_unavailable", gate["blocking_reasons"])
        self.assertEqual(packet["call_ledger"][0]["freshness_reason"], "expected_data_date_unavailable")
        self.assertTrue(packet["call_ledger"][0]["freshness_blocks_composite_score"])
        self.assertIsNone(packet["score"]["composite_score"])
        self.assertEqual(packet["score"]["support_factors"], [])
        self.assertEqual(packet["next_session_bridge"]["preview"], [])
        self.assertIn("无法确认最近应可得交易日", " ".join(gate["warnings"]))

    def test_a_share_calendar_missing_today_blocks_current_evidence(self):
        incomplete_calendar = {
            "status": "ready",
            "rows": [
                {"cal_date": "20260611", "is_open": 1},
                {"cal_date": "20260615", "is_open": 1},
            ],
        }
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            trade_calendar_packet=incomplete_calendar,
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260611", "call_status": "success"},
            ],
            now="2026-06-12T10:00:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["status"], "unknown")
        self.assertFalse(gate["usable_for_score"])
        self.assertEqual(gate["market_phase"], "calendar_gap")
        self.assertEqual(gate["market_session_detail"], "calendar_gap_missing_today")
        self.assertEqual(gate["expected_data_date"], None)
        self.assertFalse(gate["expected_data_date_available"])
        self.assertFalse(gate["today_calendar_row_found"])
        self.assertEqual(gate["market_closed_reason"], "trade_cal_missing_today")
        self.assertEqual(gate["data_update_delay_reason"], "trade_cal_missing_today_cannot_infer_session")
        self.assertEqual(gate["calendar_coverage_status"], "partial_missing_today")
        self.assertTrue(gate["calendar_requires_refresh"])
        self.assertTrue(gate["previous_open_found"])
        self.assertTrue(gate["next_open_found"])
        self.assertIn("expected_data_date_unavailable", gate["blocking_reasons"])
        self.assertEqual(packet["call_ledger"][0]["freshness_reason"], "expected_data_date_unavailable")
        self.assertTrue(packet["call_ledger"][0]["freshness_blocks_composite_score"])
        self.assertIsNone(packet["score"]["composite_score"])
        self.assertEqual(packet["score"]["support_factors"], [])
        self.assertEqual(packet["next_session_bridge"]["preview"], [])
        self.assertIn("trade_cal 缺少当前日期", " ".join(gate["warnings"]))

    def test_fallback_weekday_calendar_is_marked_unvalidated(self):
        packet = factor_research.build_factor_quant_hub_packet(
            mode="light",
            daily_close_packet=self._daily_packet(),
            daily_basic_packet=self._daily_basic_packet(),
            call_ledger=[
                {"api": "daily", "row_count": 22, "data_date": "20260612", "call_status": "success"},
            ],
            now="2026-06-15T10:00:00",
        )

        gate = packet["data_freshness_gate"]
        self.assertEqual(gate["status"], "fresh")
        self.assertFalse(gate["calendar_validated"])
        self.assertEqual(gate["calendar_source"], "fallback_weekday_calendar")
        self.assertEqual(gate["calendar_coverage_status"], "fallback_weekday_calendar")
        self.assertIn("交易日历未验证", " ".join(gate["warnings"]))

    def test_deepseek_prompt_and_sanitizer_are_explanation_only(self):
        hub = factor_research.build_factor_quant_hub_packet(mode="cache_only")
        prompt = factor_research.build_factor_deepseek_explanation_prompt(hub)
        sanitized = factor_research.sanitize_factor_deepseek_explanation(
            {
                "summary": "只解释",
                "support_notes": ["量能支持"],
                "strategy_action": "买入",
                "price": 99,
                "factor_values": [{"raw_value": 1}],
            },
            model_used=DEEPSEEK_MODEL_DEFAULTS["factor_explain"],
            input_hash=prompt["input_hash"],
        )

        self.assertEqual(
            set(prompt["allowed_top_level_keys"]),
            {
                "summary",
                "support_notes",
                "suppress_notes",
                "conflict_notes",
                "missing_data_notes",
                "discipline_notes",
            },
        )
        self.assertIn("strategy_action", sanitized["ignored_keys"])
        self.assertIn("price", sanitized["ignored_keys"])
        self.assertIn("factor_values", sanitized["ignored_keys"])
        self.assertEqual(sanitized["payload"]["summary"], "只解释")
        self.assertEqual(sanitized["model_used"], DEEPSEEK_MODEL_DEFAULTS["factor_explain"])
        self.assertEqual(sanitized["input_hash"], prompt["input_hash"])
        self.assertTrue(sanitized["output_hash"])
        self.assertGreater(sanitized["token_estimate"], 0)
        self.assertFalse(sanitized["parse_failed"])
        self.assertTrue(sanitized["does_not_override_numeric_values"])
        self.assertTrue(prompt["input_hash"])
        self.assertGreater(prompt["token_estimate"], 0)
        self.assertTrue(prompt["does_not_include_full_packet"])

    def test_deepseek_sanitizer_parse_failed_keeps_hashes_and_allowed_schema(self):
        sanitized = factor_research.sanitize_factor_deepseek_explanation(
            "不是 JSON",
            model_used=DEEPSEEK_MODEL_DEFAULTS["factor_explain"],
            input_hash="abc123",
        )

        self.assertEqual(sanitized["status"], "parse_failed")
        self.assertTrue(sanitized["parse_failed"])
        self.assertEqual(sanitized["model_used"], DEEPSEEK_MODEL_DEFAULTS["factor_explain"])
        self.assertEqual(sanitized["input_hash"], "abc123")
        self.assertTrue(sanitized["output_hash"])
        self.assertGreater(sanitized["token_estimate"], 0)
        self.assertEqual(set(sanitized["payload"]), {
            "summary",
            "support_notes",
            "suppress_notes",
            "conflict_notes",
            "missing_data_notes",
            "discipline_notes",
        })
        self.assertTrue(sanitized["does_not_override_numeric_values"])
        self.assertTrue(sanitized["does_not_output_strategy_action"])


if __name__ == "__main__":
    unittest.main()
