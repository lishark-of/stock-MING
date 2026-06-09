import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_next_session_projection as projection


DAILY_ROWS = [
    {"trade_date": f"2026-05-{day:02d}", "open": 90 + day, "high": 92 + day, "low": 88 + day, "close": 90 + day, "vol": 1000 + day, "amount": 2000 + day}
    for day in range(1, 29)
]


LINEAGE = {
    "schema_version": "a_share_fact_lineage_summary.v1",
    "items": [
        {"fact_key": "moneyflow", "fact_name": "资金流", "status": "verified", "data_date": "2026-05-28", "local_fetched_at": "2026-05-28T15:10:00", "source_interfaces": ["tushare.moneyflow"], "enters_projection": True, "enters_deepseek_prompt": True, "enters_core_action": False},
        {"fact_key": "dragon_tiger", "fact_name": "龙虎榜", "status": "blocked", "data_date": None, "local_fetched_at": "2026-05-28T15:10:00", "source_interfaces": ["tushare.top_list"], "enters_projection": True, "enters_deepseek_prompt": True, "enters_core_action": False},
        {"fact_key": "margin", "fact_name": "融资融券", "status": "pending", "source_interfaces": ["tushare.margin_detail"], "enters_projection": True, "enters_deepseek_prompt": True, "enters_core_action": False},
        {"fact_key": "hard_risk", "fact_name": "公告/硬风险", "status": "missing", "source_interfaces": ["tushare.anns"], "enters_projection": True, "enters_deepseek_prompt": True, "enters_core_action": False},
        {"fact_key": "limit_emotion", "fact_name": "涨跌停/情绪", "status": "cached", "source_interfaces": ["tushare.stk_limit"], "enters_projection": True, "enters_deepseek_prompt": True, "enters_core_action": False},
        {"fact_key": "chip_radar", "fact_name": "筹码/胜率", "status": "stale", "source_interfaces": ["tushare.cyq_perf"], "enters_projection": True, "enters_deepseek_prompt": True, "enters_core_action": False},
        {"fact_key": "volume_amount", "fact_name": "成交额/成交量", "status": "verified", "source_interfaces": ["tushare.daily"], "enters_projection": True, "enters_deepseek_prompt": True, "enters_core_action": False},
    ],
}


CALL_LEDGER = {
    "schema_version": "a_share_fact_call_ledger.v1",
    "items": [
        {"fact_key": "moneyflow", "fact_name": "资金流", "source_interfaces": ["tushare.moneyflow"], "source_packet": "command_center_moneyflow_packet", "call_status": "verified_present", "row_count": 1, "data_date": "2026-05-28", "local_fetched_at": "2026-05-28T15:40:00", "lineage_status": "verified"},
        {"fact_key": "dragon_tiger", "fact_name": "龙虎榜", "source_interfaces": ["tushare.top_list", "tushare.top_inst"], "source_packet": "command_center_dragon_tiger_packet", "call_status": "verified_no_record", "row_count": 0, "data_date": "2026-05-28", "local_fetched_at": "2026-05-28T15:40:00", "lineage_status": "verified", "is_market_absence_meaningful": True},
        {"fact_key": "margin", "fact_name": "融资融券", "source_interfaces": ["tushare.margin_detail"], "source_packet": "command_center_margin_packet", "call_status": "permission_denied", "row_count": 0, "local_fetched_at": "2026-05-28T15:40:00", "lineage_status": "blocked", "error_type": "permission_denied"},
        {
            "fact_key": "hard_risk",
            "fact_name": "公告/硬风险",
            "scope": "target_stock",
            "target_ts_code": "002008.SZ",
            "symbol_filter_applied": True,
            "target_match_count": 0,
            "market_row_count": 1322,
            "source_interfaces": ["tushare.anns_d", "tushare.pledge_stat"],
            "source_packet": "command_center_hard_risk_packet",
            "call_status": "verified_no_record",
            "row_count": 0,
            "local_fetched_at": "2026-05-28T15:40:00",
            "lineage_status": "verified",
            "is_target_stock_evidence": True,
            "is_market_context_evidence": True,
            "scope_breakdown": [
                {"scope": "target_stock", "call_status": "verified_no_record", "row_count": 0, "target_match_count": 0, "is_target_stock_evidence": True},
                {"scope": "market_context", "call_status": "verified_present", "row_count": 1322, "target_match_count": 0, "is_market_context_evidence": True},
            ],
            "scope_note": "目标股无记录；市场/概念上下文另列，不能当作目标股事实。",
        },
        {
            "fact_key": "limit_emotion",
            "fact_name": "涨跌停/情绪",
            "scope": "target_stock",
            "target_ts_code": "002008.SZ",
            "symbol_filter_applied": True,
            "target_match_count": 0,
            "market_row_count": 21,
            "source_interfaces": ["tushare.stk_limit", "tushare.limit_cpt_list"],
            "source_packet": "command_center_limit_emotion_packet",
            "call_status": "verified_no_record",
            "row_count": 0,
            "local_fetched_at": "2026-05-28T15:40:00",
            "lineage_status": "verified",
            "is_target_stock_evidence": True,
            "is_market_context_evidence": False,
            "is_industry_or_concept_evidence": True,
            "scope_breakdown": [
                {"scope": "target_stock", "call_status": "verified_no_record", "row_count": 0, "target_match_count": 0, "is_target_stock_evidence": True},
                {"scope": "industry_or_concept", "call_status": "verified_present", "row_count": 21, "target_match_count": 0, "is_industry_or_concept_evidence": True},
            ],
        },
    ],
}


class CommandCenterNextSessionProjectionTests(unittest.TestCase):
    def _packet(self, **overrides):
        kwargs = {
            "target": "002008.SZ",
            "daily_close_packet": {
                "status": "ready",
                "rows": DAILY_ROWS,
                "source_interface": "tushare.daily",
                "updated_at": "2026-05-28T15:30:00",
                "is_real_market_series": True,
            },
            "home_snapshot": {"a_share_fact_lineage_summary": LINEAGE},
            "a_share_fact_lineage_summary": LINEAGE,
            "a_share_fact_call_ledger": CALL_LEDGER,
            "position_profile": {"shares": 3000, "cost_price": 98, "margin_ratio_pct": 30},
            "strategy_packet": {"action": "只观察", "add_condition": "回踩不破再观察", "reduce_condition": "跌破支撑降风险", "invalidation_condition": "市场转弱失效"},
            "decision_packet": {"overall_action": "持仓观察"},
            "recent_trade_reviews": [{"user_note": "上次追高后回撤，避免再次追高", "user_decision": "观察"}],
            "now": "2026-05-28T16:00:00",
        }
        kwargs.update(overrides)
        return projection.build_next_session_operation_projection_packet(**kwargs)

    def test_real_daily_close_enters_chart_render_model(self):
        packet = self._packet()
        daily = packet["data_lineage"]["daily_close"]

        self.assertEqual(packet["schema_version"], projection.SCHEMA_VERSION)
        self.assertTrue(daily["is_real_market_series"])
        self.assertEqual(daily["source_interface"], "tushare.daily")
        self.assertEqual(daily["row_count"], len(DAILY_ROWS))
        self.assertEqual(daily["start_date"], "2026-05-01")
        self.assertEqual(daily["end_date"], "2026-05-28")
        self.assertEqual(daily["latest_close"], 118)
        self.assertEqual(packet["chart_render_model"]["historical_series"][-1]["price"], 118)

    def test_missing_daily_does_not_draw_synthetic_history(self):
        packet = self._packet(daily_close_packet={"status": "missing", "rows": []})

        self.assertEqual(packet["status"], "missing_daily_close")
        self.assertFalse(packet["data_lineage"]["daily_close"]["is_real_market_series"])
        self.assertEqual(packet["chart_render_model"]["historical_series"], [])
        self.assertIn("真实日线缺失", " ".join(packet["warnings"]))
        self.assertTrue(packet["scenario_paths"])

    def test_a_share_fact_lineage_keeps_seven_fact_classes_and_call_statuses(self):
        packet = self._packet()
        items = packet["data_lineage"]["a_share_fact_lineage_summary"]["items"]
        statuses = {item["fact_key"]: item["status"] for item in items}
        call_statuses = {item["fact_key"]: item.get("call_status") for item in items}

        self.assertEqual(set(statuses), {key for key, _ in projection.REQUIRED_FACT_KEYS})
        self.assertEqual(call_statuses["dragon_tiger"], "verified_no_record")
        self.assertEqual(statuses["dragon_tiger"], "verified")
        self.assertEqual(statuses["margin"], "blocked")
        self.assertIn("融资融券", packet["scenario_paths"][0]["invalid_conditions"][-1])

    def test_quant_context_does_not_modify_strategy_action(self):
        strategy = {"action": "降风险", "add_condition": "不要加仓"}
        packet = self._packet(strategy_packet=strategy)

        self.assertEqual(strategy["action"], "降风险")
        self.assertEqual(packet["quant_context"]["suggested_action"], "降风险")
        self.assertTrue(packet["data_lineage"]["strategy_execution_packet"]["does_not_modify_action"])

    def test_position_context_uses_user_position_profile_with_lineage(self):
        packet = self._packet()
        position = packet["position_context"]

        self.assertEqual(position["shares"], 3000.0)
        self.assertEqual(position["cost_price"], 98.0)
        self.assertEqual(position["financing_ratio"], 30.0)
        self.assertIn("position_profile", position["source_packet"])
        self.assertTrue(position["is_user_verified_position"])
        self.assertFalse(position["conflict_flags"])

    def test_position_context_detects_snapshot_conflict_and_downgrades_actions(self):
        packet = self._packet(
            home_snapshot={
                "a_share_fact_lineage_summary": LINEAGE,
                "holding_action": {"shares": 4100, "cost_price": 113, "margin_ratio": 0.11, "current_price": 118},
            },
            position_profile={"shares": 3000, "cost_price": 98, "margin_ratio_pct": 30},
        )
        position = packet["position_context"]

        self.assertIn("shares_conflict", position["conflict_flags"])
        self.assertIn("cost_price_conflict", position["conflict_flags"])
        self.assertIn("financing_ratio_conflict", position["conflict_flags"])
        for path in packet["scenario_paths"]:
            plan = path["operation_plan"]
            self.assertEqual(plan["primary_action"], "verify")
            self.assertEqual(plan["position_change"], "none")
            self.assertNotIn(plan["primary_action"], {"reduce", "add", "stop_loss"})
            self.assertIn("持仓来源冲突", path["confidence_note"])

    def test_fact_call_ledger_distinguishes_verified_no_record_and_permission(self):
        packet = self._packet()
        ledger_items = packet["data_lineage"]["a_share_fact_call_ledger"]["items"]
        by_key = {item["fact_key"]: item for item in ledger_items}
        lineage_items = packet["data_lineage"]["a_share_fact_lineage_summary"]["items"]
        lineage_by_key = {item["fact_key"]: item for item in lineage_items}

        self.assertEqual(by_key["moneyflow"]["call_status"], "verified_present")
        self.assertEqual(by_key["dragon_tiger"]["call_status"], "verified_no_record")
        self.assertEqual(by_key["margin"]["call_status"], "permission_denied")
        self.assertEqual(lineage_by_key["dragon_tiger"]["status"], "verified")
        self.assertEqual(lineage_by_key["margin"]["status"], "blocked")
        self.assertTrue(by_key["dragon_tiger"]["is_market_absence_meaningful"])

    def test_hard_risk_market_rows_do_not_become_target_stock_verified_present(self):
        packet = self._packet()
        hard = {item["fact_key"]: item for item in packet["data_lineage"]["a_share_fact_call_ledger"]["items"]}["hard_risk"]

        self.assertEqual(hard["scope"], "target_stock")
        self.assertEqual(hard["call_status"], "verified_no_record")
        self.assertEqual(hard["row_count"], 0)
        self.assertEqual(hard["target_match_count"], 0)
        self.assertEqual(hard["market_row_count"], 1322)
        self.assertNotEqual(hard["call_status"], "verified_present")
        breakdown = {item["scope"]: item for item in hard["scope_breakdown"]}
        self.assertEqual(breakdown["market_context"]["call_status"], "verified_present")
        self.assertEqual(breakdown["market_context"]["row_count"], 1322)

    def test_limit_emotion_target_and_concept_context_are_separated(self):
        packet = self._packet()
        limit = {item["fact_key"]: item for item in packet["data_trust_summary"]["facts"]}["limit_emotion"]
        breakdown = {item["scope"]: item for item in limit["scope_breakdown"]}

        self.assertEqual(limit["call_status"], "verified_no_record")
        self.assertEqual(limit["scope"], "target_stock")
        self.assertEqual(breakdown["target_stock"]["row_count"], 0)
        self.assertEqual(breakdown["industry_or_concept"]["call_status"], "verified_present")
        self.assertEqual(breakdown["industry_or_concept"]["row_count"], 21)

    def test_next_session_limit_context_clamps_next_day_zone(self):
        limit_context = {
            "source": "estimated_from_latest_close",
            "up_limit": 132.95,
            "down_limit": 108.77,
            "limit_pct": 10,
            "is_estimated": True,
        }
        zone = projection._clamp_next_session_zone(
            {
                "next_session_low": 106.91,
                "next_session_high": 133.85,
                "five_to_ten_day_zone": [104.0, 140.0],
            },
            limit_context,
        )

        self.assertEqual(zone["next_session_low"], 108.77)
        self.assertEqual(zone["next_session_high"], 132.95)
        self.assertIn("已按上下限截断", zone["note"])
        self.assertEqual(zone["five_to_ten_day_zone"], [104.0, 140.0])
        self.assertEqual(zone["five_to_ten_day_zone_label"], "5~10 日情景区间")

    def test_chart_points_anchor_at_latest_close_and_axis_is_dynamic(self):
        packet = self._packet()
        latest_close = packet["data_lineage"]["daily_close"]["latest_close"]
        chart = packet["chart_render_model"]

        for path in packet["scenario_paths"]:
            self.assertEqual(path["chart_points"][0]["price"], latest_close)
            self.assertEqual(path["chart_points"][0]["x"], "T0")
            self.assertEqual([point["x"] for point in path["chart_points"]], ["T0", "T+1_open", "T+1_intraday", "T+1_close"])
            self.assertIn("extended_chart_points", path)
        self.assertEqual(chart["historical_series"][-1]["source"], "tushare.daily.close")
        self.assertNotEqual(chart["y_axis_range"], [0, 200])

    def test_human_data_summary_hides_machine_status_by_default(self):
        packet = self._packet()
        human = " ".join(packet["data_trust_summary"]["human_summary"])

        self.assertIn("真实日线：已接入", human)
        self.assertIn("资金流：已返回", human)
        self.assertNotIn("target_stock verified_present", human)
        self.assertEqual(packet["data_trust_summary"]["technical_expander_label"], "展开查看技术血缘")

    def test_evidence_effects_do_not_turn_no_record_or_concept_context_negative(self):
        packet = self._packet()
        effects = [effect for path in packet["scenario_paths"] for effect in path["evidence_effects"]]
        by_key_scope = {(item["fact_key"], item["scope"]): item for item in effects}

        self.assertEqual(by_key_scope[("dragon_tiger", "target_stock")]["effect"], "neutral")
        self.assertEqual(by_key_scope[("limit_emotion", "industry_or_concept")]["effect"], "neutral")

        ledger = copy.deepcopy(CALL_LEDGER)
        for item in ledger["items"]:
            if item.get("fact_key") == "hard_risk":
                item.update(
                    {
                        "call_status": "verified_present",
                        "row_count": 1322,
                        "target_match_count": 1322,
                        "market_row_count": 1322,
                        "scope_breakdown": [
                            {"scope": "target_stock", "call_status": "verified_present", "row_count": 1322, "target_match_count": 1322}
                        ],
                    }
                )
        packet = self._packet(a_share_fact_call_ledger=ledger)
        hard_effects = [
            effect
            for path in packet["scenario_paths"]
            for effect in path["evidence_effects"]
            if effect.get("fact_key") == "hard_risk"
        ]
        self.assertTrue(hard_effects)
        self.assertNotEqual(hard_effects[0]["effect"], "suppress")
        self.assertEqual(hard_effects[0]["effect"], "neutral_with_watch")

    def test_trade_lab_bias_enters_operation_discipline(self):
        packet = self._packet()
        trade_lab = packet["trade_lab_context"]
        no_chase_zone = next(item for item in packet["operation_zones"] if item["zone_key"] == "do_not_chase_zone")

        self.assertIn("追高风险", trade_lab["behavior_bias"])
        self.assertIn("禁止追高", no_chase_zone["zone_name"])
        self.assertEqual(no_chase_zone["source"], "trade_lab_discipline")

    def test_deepseek_prompt_is_json_only_and_contains_required_context(self):
        packet = self._packet()
        prompt = projection.build_next_session_deepseek_prompt(packet)
        text = prompt["system_prompt"] + prompt["user_prompt"]

        self.assertFalse(prompt["deepseek_called"])
        self.assertTrue(prompt["required_json_only"])
        for term in ["position_context", "daily_close", "quant_context", "trade_lab_context", "a_share_fact_lineage_summary"]:
            self.assertIn(term, text)
        self.assertIn("不要添加输入之外的事实", text)
        self.assertIn("不得把缺失、待验证、阻断、权限不足、成功无记录的数据当作已验证利好", text)
        self.assertIn("command_center_next_session_projection_packet", prompt["cache_key"])
        self.assertIn("position_hash", prompt["component_hashes"])
        self.assertIn("a_share_fact_lineage_hash", prompt["component_hashes"])
        self.assertIn("a_share_fact_call_ledger", text)
        self.assertIn("顶层键只允许", text)
        self.assertIn("a_share_fact_call_ledger_hash", prompt["component_hashes"])

    def test_deepseek_json_parse_failure_keeps_deterministic_projection(self):
        packet = self._packet()
        before_paths = packet["scenario_paths"]
        enhanced = projection.merge_deepseek_next_session_projection(packet, "不是 JSON", called_at="2026-05-28T16:10:00")

        self.assertTrue(enhanced["deepseek_called"])
        self.assertEqual(enhanced["deepseek_synthesis"]["status"], "parse_failed")
        self.assertEqual(enhanced["scenario_paths"], before_paths)

    def test_deepseek_fenced_json_and_text_wrapped_json_can_be_extracted(self):
        fenced, error = projection.extract_deepseek_projection_json('```json\n{"scenario_paths": [], "operation_zones": []}\n```')
        wrapped, wrapped_error = projection.extract_deepseek_projection_json('说明文字 {"scenario_paths": [], "operation_zones": []} 结束')

        self.assertFalse(error)
        self.assertFalse(wrapped_error)
        self.assertEqual(fenced["scenario_paths"], [])
        self.assertEqual(wrapped["operation_zones"], [])

    def test_deepseek_json_success_records_hashes_without_overwriting_history(self):
        packet = self._packet()
        history = packet["chart_render_model"]["historical_series"]
        enhanced = projection.merge_deepseek_next_session_projection(
            packet,
            {
                "summary": "按输入 JSON 整理操作图谱。",
                "scenario_paths": packet["scenario_paths"],
                "operation_zones": packet["operation_zones"],
                "annotations": [{"text": "只解释输入，不验证外部事实。"}],
                "warnings": ["不要把情景路径当确定性预测。"],
            },
            called_at="2026-05-28T16:10:00",
            input_hash="abc123",
        )

        synthesis = enhanced["deepseek_synthesis"]
        self.assertEqual(synthesis["status"], "success")
        self.assertEqual(synthesis["input_hash"], "abc123")
        self.assertTrue(synthesis["output_hash"])
        self.assertEqual(enhanced["chart_render_model"]["historical_series"], history)

    def test_deepseek_merge_whitelist_rejects_verified_market_overrides(self):
        packet = self._packet()
        enhanced = projection.merge_deepseek_next_session_projection(
            packet,
            {
                "summary": "只整理路径。",
                "latest_close": 999,
                "row_count": 1,
                "source_interface": "deepseek.fake",
                "position_context": {"shares": 1, "cost_price": 1, "current_price": 999},
                "data_lineage": {"daily_close": {"latest_close": 999}},
                "quant_context": {"suggested_action": "满仓"},
                "strategy_execution_packet": {"action": "满仓"},
                "scenario_paths": packet["scenario_paths"],
                "operation_zones": packet["operation_zones"],
            },
            called_at="2026-05-28T16:10:00",
            input_hash="abc123",
        )

        self.assertEqual(enhanced["data_lineage"]["daily_close"]["latest_close"], 118)
        self.assertEqual(enhanced["data_lineage"]["daily_close"]["row_count"], len(DAILY_ROWS))
        self.assertEqual(enhanced["data_lineage"]["daily_close"]["source_interface"], "tushare.daily")
        self.assertEqual(enhanced["position_context"]["shares"], 3000.0)
        self.assertEqual(enhanced["position_context"]["cost_price"], 98.0)
        self.assertEqual(enhanced["quant_context"]["suggested_action"], "只观察")
        synthesis = enhanced["deepseek_synthesis"]
        self.assertEqual(synthesis["status"], "success")
        for key in ["latest_close", "position_context", "strategy_execution_packet"]:
            self.assertIn(key, synthesis["blocked_immutable_keys"])
            self.assertIn(key, synthesis["ignored_top_level_keys"])

        enhanced = projection.merge_deepseek_next_session_projection(
            packet,
            {
                "summary": "只整理路径。",
                "next_session_limit_context": {"up_limit": 999, "down_limit": 1},
                "scenario_paths": packet["scenario_paths"],
                "operation_zones": packet["operation_zones"],
            },
            called_at="2026-05-28T16:10:00",
            input_hash="abc123",
        )
        self.assertEqual(enhanced["next_session_limit_context"], packet["next_session_limit_context"])

    def test_ui_copy_contains_safe_terms_and_avoids_forbidden_terms(self):
        copy = projection.next_session_projection_ui_copy()
        joined = json.dumps(copy, ensure_ascii=False)

        for term in projection.UI_REQUIRED_LABELS:
            self.assertIn(term, joined)
        for term in projection.FORBIDDEN_UI_LABELS:
            self.assertNotIn(term, joined)

    def test_app_makes_next_session_projection_primary_and_legacy_trend_folded(self):
        source = Path("app.py").read_text()
        next_index = source.index("render_next_session_operation_projection(next_session_projection_packet)")
        legacy_index = source.index("render_command_center_projection_chart(projection_packet, home_compact=True)")

        self.assertLess(next_index, legacy_index)
        self.assertIn('"生成次日操作图谱"', source)
        self.assertIn('"AI 整理说明"', source)
        self.assertIn('st.expander("高级操作", expanded=False)', source)
        self.assertIn('st.expander("高级工具箱 / 开发调试 / 旧版兼容视图", expanded=False)', source)
        self.assertIn("此为旧版兼容视图，主判断请以次日操作图谱为准。", source)
        self.assertIn("示意路径，不是真实价格预测。", source)
        self.assertNotIn('st.markdown("### 未来 5~10 日趋势推演")', source)
        self.assertNotIn('"DeepSeek 整理次日操作图谱"', source)

    def test_ui_data_trust_summary_shows_scope_and_position_conflict_warning(self):
        source = Path("visual_components.py").read_text()
        packet = self._packet()
        hard = {item["fact_key"]: item for item in packet["data_trust_summary"]["facts"]}["hard_risk"]
        scopes = {item["scope"] for item in hard["scope_breakdown"]}

        self.assertIn("数据可信度摘要", source)
        self.assertIn("展开查看技术血缘", source)
        self.assertIn("范围", source)
        self.assertIn("市场行数", source)
        self.assertIn("_next_session_position_change_label", source)
        self.assertIn("strong_change", source)
        self.assertIn("5~10 日情景区间", source)
        self.assertIn("extended_label}：{extended_text}", source)
        self.assertEqual(scopes, {"target_stock", "market_context"})
        self.assertIn("持仓来源冲突：当前仅输出观察/核验路径，不生成强操作建议。", source)

    def test_legacy_action_guard_marks_strong_actions_conditional_for_passive_main_action(self):
        guarded = projection.guard_legacy_projection_action(
            "分批减仓",
            main_action="等待",
            position_context={"conflict_flags": []},
        )

        self.assertTrue(guarded["is_strong_action"])
        self.assertTrue(guarded["is_condition_only"])
        self.assertIn("条件触发动作", guarded["display_action"])
        self.assertIn("触发条件满足", guarded["guard_note"])

        add_small = projection.guard_legacy_projection_action("add_small", main_action="observe", position_context={})
        self.assertIn("条件触发动作", add_small["display_action"])

    def test_legacy_action_guard_blocks_strong_actions_when_position_conflicts(self):
        guarded = projection.guard_legacy_projection_action(
            "stop_loss",
            main_action="只观察",
            position_context={"conflict_flags": ["shares_conflict"]},
        )

        self.assertEqual(guarded["normalized_action"], "verify")
        self.assertEqual(guarded["display_action"], "核验/观察")
        self.assertTrue(guarded["is_blocked_by_position_conflict"])
        self.assertIn("持仓来源冲突", guarded["guard_note"])

    def test_legacy_position_compare_detects_projection_conflicts(self):
        comparison = projection.compare_legacy_position_with_projection(
            {"holding_units": 4100, "cost_price": 113, "margin_ratio": 0.11, "current_price": 120.86},
            {"shares": 3000, "cost_price": 98, "financing_ratio": 30, "current_price": 120.86},
        )

        self.assertTrue(comparison["has_conflict"])
        self.assertIn("shares_conflict", comparison["conflict_flags"])
        self.assertIn("cost_price_conflict", comparison["conflict_flags"])
        self.assertIn("financing_ratio_conflict", comparison["conflict_flags"])
        self.assertIn("旧模块持仓口径", comparison["note"])

    def test_app_route_helpers_and_entry_buttons_are_wired(self):
        source = Path("app.py").read_text()

        for name in [
            "init_command_center_route",
            "set_command_center_route",
            "get_command_center_route",
            "preserve_command_center_route",
        ]:
            self.assertIn(f"def {name}", source)
        self.assertIn('"command_center_route"', source)
        self.assertIn('"next_session_projection"', source)
        self.assertIn('"command_center_active_anchor"', source)
        self.assertIn('"next_session_operation_map"', source)
        self.assertIn('"next_session_projection_expanded"', source)
        self.assertIn('st.expander("高级操作", expanded=False)', source)
        self.assertIn("previous_route = preserve_command_center_route", source)

    def test_command_center_home_clears_legacy_route_without_resetting_next_session(self):
        source = Path("app.py").read_text()

        self.assertIn('if selected_nav == "综合推演中心 2.0":', source)
        self.assertIn("active_route = get_command_center_route(st.session_state)", source)
        self.assertIn('if active_route not in {"home", "next_session_projection"}:', source)
        self.assertIn('set_command_center_route(st.session_state, "home")', source)
        self.assertIn('elif selected_nav == "高级工具箱入口":', source)
        self.assertIn('set_command_center_route(st.session_state, "advanced_tools")', source)

    def test_unified_base_routes_and_legacy_quant_are_folded(self):
        source = Path("app.py").read_text()

        for label, route in [
            ("产业链联动", "structured_data"),
            ("情景推演", "single_stock_projection"),
            ("持仓体检", "trade_discipline_lab"),
            ("资金面", "structured_data"),
            ("深度挖掘", "advanced_tools"),
        ]:
            self.assertIn(label, source)
            self.assertIn(route, source)
        self.assertIn("COMMAND_CENTER_BASE_ROUTE_MAP.get(base_view", source)
        self.assertIn("高级工具箱 / 开发调试 / 旧版量化推演兼容视图", source)
        self.assertIn("旧版量化推演兼容视图 / 单票作战室", source)
        self.assertIn('expanded=bool(st.session_state.get("legacy_single_stock_lab_expanded"))', source)
        self.assertIn("打开旧版量化推演兼容视图", source)
        self.assertIn('"量化推演"', source)
        self.assertIn("legacy_compat_active_tab", source)

    def test_deepseek_counter_and_current_projection_status_are_separated(self):
        source = Path("app.py").read_text()

        self.assertIn("当前图谱 DeepSeek", source)
        self.assertIn("本会话 DeepSeek 累计调用", source)
        self.assertIn("高级调试计数器", source)
        self.assertIn("_command_center_projection_deepseek_status", source)
        self.assertIn("DeepSeek 全局计数只放入高级调试计数器", source)
        self.assertNotIn("DeepSeek 调用次数", source)

    def test_legacy_trade_instruction_copy_uses_guarded_reference_language(self):
        source = Path("app.py").read_text()

        self.assertIn("旧版兼容推演｜不作为当前交易指令", source)
        self.assertIn("guard_legacy_projection_action", source)
        self.assertIn("旧规则估值参考", source)
        self.assertIn('c6.metric("旧规则估值参考"', source)
        self.assertNotIn("止盈/减仓参考", source)
        self.assertIn("该价格不是当前减仓触发价", source)

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_next_session_projection.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in {"streamlit", "tushare_adapter", "data_fetcher", "openai", "app"}:
            self.assertNotIn(name, imports)


if __name__ == "__main__":
    unittest.main()
