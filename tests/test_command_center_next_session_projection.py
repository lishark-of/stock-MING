import ast
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
        self.assertIn('st.expander("旧版趋势推演兼容视图", expanded=False)', source)
        self.assertIn("此为旧版兼容视图，主判断请以次日操作图谱为准。", source)
        self.assertIn("示意路径，不是真实价格预测。", source)

    def test_ui_data_trust_summary_shows_scope_and_position_conflict_warning(self):
        source = Path("visual_components.py").read_text()
        packet = self._packet()
        hard = {item["fact_key"]: item for item in packet["data_trust_summary"]["facts"]}["hard_risk"]
        scopes = {item["scope"] for item in hard["scope_breakdown"]}

        self.assertIn("数据可信度摘要", source)
        self.assertIn("scope_breakdown", source)
        self.assertIn("范围", source)
        self.assertIn("市场行数", source)
        self.assertEqual(scopes, {"target_stock", "market_context"})
        self.assertIn("持仓来源冲突：当前仅输出观察/核验路径，不生成强操作建议。", source)

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
