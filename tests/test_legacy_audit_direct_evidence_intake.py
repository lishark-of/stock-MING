import unittest
from pathlib import Path


class LegacyAuditDirectEvidenceIntakeTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.migration_map = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")

    def test_direct_evidence_intake_template_has_required_slots(self):
        self.assertIn("第一轮 Legacy Bug / UX Audit 的直接取证模板", self.migration_map)
        for required_slot in (
            "user_observation",
            "legacy_ux_bug_or_patchwork",
            "data_lineage_observation",
            "replacement_user_path",
            "frozen_legacy_path",
            "evidence_attachment",
            "keep_promotion_decision",
        ):
            self.assertIn(required_slot, self.migration_map)

    def test_first_intake_does_not_promote_seed_rows_to_keep_or_evidence(self):
        for required_boundary in (
            "no_keep_promotion_this_round",
            "不是新 contract、receipt、matrix 或 production evidence",
            "不要求打开 Streamlit",
            "不调用 Tushare/DeepSeek/GitHub",
            "不创建 task",
            "不读取 token/key",
            "不能把 route inventory、本地 receipt、no-feature-loss matrix、mock、sanitizer 或 docs/config scaffold 当作直接 UX/bug evidence",
        ):
            self.assertIn(required_boundary, self.migration_map)

        for allowed_status in (
            "direct_evidence_intake_pending",
            "direct_evidence_observed_redesign_required",
            "blocked_by_lineage",
            "legacy_debug_retained",
            "retire_confirmed",
        ):
            self.assertIn(allowed_status, self.migration_map)

        self.assertIn("`KEEP` 仍然保持禁止", self.migration_map)
        self.assertIn("不能把本轮取证当作生产验收", self.migration_map)

    def test_first_intake_worklist_targets_priority_ordinary_workflows_without_keep_promotion(self):
        self.assertIn("第一轮直接取证工作清单", self.migration_map)
        self.assertIn("不是新合同、不是 receipt、不是 production evidence", self.migration_map)
        self.assertIn("不会把任何 seed row 升级成 `KEEP`", self.migration_map)

        for intake_row in (
            "legacy_intake_home_daily_command",
            "legacy_intake_searched_symbol_quant_projection",
            "legacy_intake_candidate_radar",
            "legacy_intake_next_session_map",
            "legacy_intake_factor_risk_provider_health",
            "legacy_intake_hard_risk_announcement",
            "legacy_intake_discipline_backtest",
            "legacy_intake_margin_etf_leverage",
            "legacy_intake_external_brain_serenity_chokepoint",
        ):
            self.assertIn(intake_row, self.migration_map)

        for workflow in (
            "home/daily command",
            "searched-symbol quant projection",
            "candidate radar",
            "next-session map",
            "factor/risk/provider health",
            "hard risk / announcement risk",
            "discipline/backtest",
            "ETF/leverage",
            "external brain / Serenity / Chokepoint",
        ):
            self.assertIn(workflow, self.migration_map)

        self.assertIn("避免后续 ECharts/operation zones、provider-health 明细、硬风险摘要、回测复盘实验室、杠杆/ETF 风险预算或外脑/RAG/probe 数据 lineage 迁移绕过 Legacy Bug / UX Audit", self.migration_map)
        self.assertIn("外脑/RAG/probe 数据 lineage 迁移绕过 Legacy Bug / UX Audit", self.migration_map)
        self.assertIn("operation_zones 只作为条件，不改 action", self.migration_map)
        self.assertIn("receipt-as-replacement", self.migration_map)
        self.assertIn("local receipt is not replacement evidence", self.migration_map)
        self.assertIn("旧 provider health 大表压过普通摘要", self.migration_map)
        self.assertIn("provider health 明细只进 Settings / Developer / Audit", self.migration_map)
        self.assertIn("missing provider data is not shown as no risk", self.migration_map)
        self.assertIn("旧无数据即低风险", self.migration_map)
        self.assertIn("模型文本覆盖事实", self.migration_map)
        self.assertIn("risk scan does not become action", self.migration_map)
        self.assertIn("旧同步回测阻塞", self.migration_map)
        self.assertIn("深层参数表单", self.migration_map)
        self.assertIn("回测结论混成普通交易建议", self.migration_map)
        self.assertIn("未来若进入普通流必须重设为独立 backtest lab", self.migration_map)
        self.assertIn("synchronous backtest, deep forms and ordinary trading advice are not migrated", self.migration_map)
        self.assertIn("杠杆配置与普通作战建议混杂", self.migration_map)
        self.assertIn("Tushare/DeepSeek 手动刷新路径复杂", self.migration_map)
        self.assertIn("ETF/融资数据缺口像可执行建议", self.migration_map)
        self.assertIn("未来若进入普通流必须重做为 risk-budget subflow", self.migration_map)
        self.assertIn("leverage advice, complex manual Tushare/DeepSeek refresh path and ordinary trading recommendations are not migrated", self.migration_map)
        self.assertIn("RAG/文档投喂/外部 probe 与普通投研动作混杂", self.migration_map)
        self.assertIn("数据 lineage 不清", self.migration_map)
        self.assertIn("模型/外部文本像当前事实或动作建议", self.migration_map)
        self.assertIn("进入普通流前必须单独重设数据 lineage", self.migration_map)
        self.assertIn("RAG/document ingestion, external probe and ordinary research action mix are not migrated", self.migration_map)
        self.assertIn("pending safe screenshot or reviewer note", self.migration_map)
        self.assertGreaterEqual(
            self.migration_map.count("direct_evidence_intake_pending"),
            9,
        )
        self.assertGreaterEqual(
            self.migration_map.count("no_keep_promotion_this_round"),
            9,
        )
        self.assertNotIn("legacy_intake_home_daily_command` | home/daily command | KEEP", self.migration_map)

    def test_first_replacement_ready_decisions_stay_audit_pending_not_keep(self):
        self.assertIn("第一轮分类小表", self.migration_map)
        self.assertIn("REDESIGN_WITH_REPLACEMENT_READY_AUDIT_PENDING", self.migration_map)
        self.assertIn("allow replacement iteration only", self.migration_map)
        self.assertIn("keep legacy/admin/debug fallback", self.migration_map)
        self.assertIn("不能升级 `KEEP`", self.migration_map)
        self.assertIn("不能退掉 Streamlit fallback", self.migration_map)
        self.assertIn("不能把 no-feature-loss / receipt / matrix 当成生产验收", self.migration_map)

        for decision_row in (
            "legacy_decision_home_daily_command_replacement_ready_audit_pending",
            "legacy_decision_searched_symbol_quant_projection_replacement_ready_audit_pending",
            "legacy_decision_next_session_map_replacement_ready_audit_pending",
            "legacy_decision_candidate_radar_replacement_ready_audit_pending",
            "legacy_decision_factor_risk_provider_health_split_audit_pending",
            "legacy_decision_hard_risk_announcement_replacement_ready_audit_pending",
            "legacy_decision_discipline_backtest_legacy_debug_retained_audit_pending",
            "legacy_decision_margin_etf_leverage_legacy_debug_retained_audit_pending",
            "legacy_decision_external_brain_serenity_chokepoint_legacy_debug_retained_audit_pending",
            "legacy_decision_old_ai_strategy_advisor_retired_audit_pending",
        ):
            self.assertIn(decision_row, self.migration_map)

        self.assertIn("capture one safe old-home observation", self.migration_map)
        self.assertIn("confirm no AI-as-action wording", self.migration_map)
        self.assertIn("operation_zones are conditions not orders", self.migration_map)
        self.assertIn("local receipt is not replacement evidence", self.migration_map)
        self.assertIn("candidate is not buy instruction", self.migration_map)
        self.assertIn("provider health detail remains `LEGACY-DEBUG`", self.migration_map)
        self.assertIn("provider detail stays out of ordinary flow", self.migration_map)
        self.assertIn("engineering tables no longer dominate ordinary pages", self.migration_map)
        self.assertIn("allow ordinary risk-gap summary iteration only", self.migration_map)
        self.assertIn("missing data is not shown as no risk", self.migration_map)
        self.assertIn("model text does not override facts", self.migration_map)
        self.assertIn("risk scan does not become action", self.migration_map)
        self.assertIn("discipline/backtest`、`ETF/leverage` 与 `external brain/Serenity/Chokepoint` 仍固定为 `LEGACY-DEBUG`", self.migration_map)
        self.assertIn("block ordinary entry until redesigned", self.migration_map)
        self.assertIn("synchronous backtest, deep forms and ordinary trading advice are not migrated", self.migration_map)
        self.assertIn("ETF/leverage | `LEGACY-DEBUG`", self.migration_map)
        self.assertIn("block ordinary entry until redesigned as risk-budget subflow", self.migration_map)
        self.assertIn("leverage advice, complex manual Tushare/DeepSeek refresh path and ordinary trading recommendations are not migrated", self.migration_map)
        self.assertIn("block ordinary entry until data lineage reset", self.migration_map)
        self.assertIn("keep legacy/admin/debug/advanced fallback only", self.migration_map)
        self.assertIn("RAG/document ingestion, external probe and ordinary research action mix are not migrated", self.migration_map)
        self.assertIn("old AI strategy advisor` 固定为 `RETIRE`", self.migration_map)
        self.assertIn("blocked from ordinary entry; rebuild only as governed research-only explain", self.migration_map)
        self.assertIn("legacy button retired, no ordinary entry", self.migration_map)
        self.assertIn("model-generated trading advice, cross-market facts without lineage, and AI-as-action wording are not migrated", self.migration_map)

    def test_seed_workflows_have_matching_audit_decision_rows_without_keep_promotion(self):
        for seed_workflow, decision_row in (
            ("streamlit_home_daily_summary", "legacy_decision_home_daily_command_replacement_ready_audit_pending"),
            ("legacy_single_stock_room_quant_projection", "legacy_decision_searched_symbol_quant_projection_replacement_ready_audit_pending"),
            ("legacy_candidate_radar", "legacy_decision_candidate_radar_replacement_ready_audit_pending"),
            ("legacy_next_session_chart", "legacy_decision_next_session_map_replacement_ready_audit_pending"),
            ("legacy_factor_risk_provider_health_tables", "legacy_decision_factor_risk_provider_health_split_audit_pending"),
            ("legacy_discipline_backtest_lab", "legacy_decision_discipline_backtest_legacy_debug_retained_audit_pending"),
            ("legacy_margin_etf_leverage_flow", "legacy_decision_margin_etf_leverage_legacy_debug_retained_audit_pending"),
            ("legacy_external_brain_ai_advisor", "legacy_decision_external_brain_serenity_chokepoint_legacy_debug_retained_audit_pending"),
            ("legacy_external_brain_ai_advisor", "legacy_decision_old_ai_strategy_advisor_retired_audit_pending"),
        ):
            self.assertIn(seed_workflow, self.migration_map)
            self.assertIn(decision_row, self.migration_map)

        self.assertGreaterEqual(
            self.migration_map.count("| `direct_evidence_intake_pending` |"),
            10,
        )
        self.assertNotIn("| `KEEP` |", self.migration_map)
        self.assertNotIn("production evidence | `KEEP`", self.migration_map)


if __name__ == "__main__":
    unittest.main()
