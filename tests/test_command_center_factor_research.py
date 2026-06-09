import json
import unittest
from pathlib import Path

import command_center_factor_research as factor_research


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
            }
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
        self.assertTrue(sanitized["does_not_override_numeric_values"])


if __name__ == "__main__":
    unittest.main()
