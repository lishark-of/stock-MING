import unittest
from pathlib import Path


class CommandCenterMigrationPrincipleDocsTests(unittest.TestCase):
    def test_long_term_goals_record_no_blind_streamlit_copy_policy(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "command_center_3_long_term_goals.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Command Center 3.0 must not copy the old Streamlit app one-to-one", text)
        self.assertIn("preserving useful user capabilities", text)
        self.assertIn("does not mean copying legacy UI", text)
        self.assertIn("historical patchwork", text)

        for classification in ("`KEEP`", "`REDESIGN`", "`LEGACY-DEBUG`", "`RETIRE`"):
            self.assertIn(classification, text)

        self.assertIn("`KEEP` promotion requires direct Legacy Bug / UX Audit evidence", text)
        self.assertIn("observed user action or workflow problem", text)
        self.assertIn("legacy bug / confusing UX / patchwork path being removed", text)
        self.assertIn("data-lineage check", text)
        self.assertIn("replacement ordinary entrance", text)
        self.assertIn("frozen legacy path", text)
        self.assertIn("route inventory, legacy tab names, docs/config/scaffold", text)
        self.assertIn("cannot promote a module to `KEEP` by themselves", text)
        self.assertIn("Direct evidence must stay separate from inventory/scaffold evidence", text)
        self.assertIn("`inventory_or_scaffold_evidence` can orient the audit", text)
        self.assertIn("`direct_user_evidence` tied to a safe screenshot reference", text)
        self.assertIn("can move a row toward `direct_evidence_ready` or a later `KEEP` review", text)

        for entrance in (
            "今日作战台 / Daily Command Center",
            "股票量化推演 / Stock Quant Projection",
            "下一票雷达 / Candidate Radar",
        ):
            self.assertIn(entrance, text)

        for required_state in (
            "next user click",
            "Tushare/cache/DeepSeek/pending",
            "evidence is missing",
            "research-only and not a buy/sell instruction",
            "blocked or degraded",
            "last successful cache/result",
        ):
            self.assertIn(required_state, text)

        self.assertIn("shared ordinary source-state vocabulary", text)
        self.assertIn("`cache`, `Tushare`, `DeepSeek`, `pending`, `degraded`, and `last_successful_cache/result`", text)
        self.assertIn("`DeepSeek` means explanation-only and never a data source or action writer", text)
        self.assertIn("Showing these source-state chips is read-only UI guidance", text)
        self.assertIn("must not create tasks, call provider/model, write cache/config, or promote production evidence", text)
        self.assertIn("Provider/model evidence across the long-term roadmap requires redacted `call_ledger` / `model_ledger` rows", text)
        self.assertIn("Missing ledger rows keep the result local or pending", text)
        self.assertIn("cannot promote `live_light`, LTG completion, Streamlit retirement, or production acceptance", text)
        self.assertIn("Migration reports and ordinary UI summaries must use safe summaries only", text)
        self.assertIn("no raw prompts, raw model output, unredacted provider errors", text)
        self.assertIn("whitelisted fields with `model_ledger` status and redaction review", text)
        self.assertIn("shared ordinary next-click rule", text)
        self.assertIn("one primary safe action per entrance", text)
        self.assertIn("visible disabled/degraded reason", text)
        self.assertIn("from a confirmed symbol to `生成 3.0 量化推演`", text)
        self.assertIn("Search typing, React render, mode banners, source-state chips, DeepSeek text, and radar candidates are not next-click actions", text)
        self.assertIn("Any next click that creates work must go through POST task / worker / local fallback", text)

        self.assertIn("Current Usable-Path Execution Target", text)
        self.assertIn("Command Center 3.0 使用者可用化最短路径", text)
        self.assertIn("not active `14 LTG strict closeout`", text)
        self.assertIn("One-click startup and frontend/backend auto connection", text)
        self.assertIn("Confirmed stock-code button triggers the Tushare-first data chain", text)
        self.assertIn("Small data writes to cache / ledger / packet", text)
        self.assertIn("Candidate Radar, Quant Projection, and Next Session map show interpretable results", text)
        self.assertIn("Ordinary user pages hide or demote engineering audit noise", text)
        self.assertIn("DeepSeek governed executor is completed separately", text)
        self.assertIn("Return to 14 LTG direct evidence / strict closeout", text)
        self.assertIn("P0-P5 progress cannot be reported as all 14 LTGs complete", text)
        self.assertIn("with no one-shot full `live_light` implementation", text)
        self.assertIn("Do not add broad LTG contracts", text)
        self.assertIn("This strategy correction does not complete any LTG", text)
        self.assertIn("not production acceptance evidence", text)
        self.assertIn("`runtime_mode_layering_docs_config_first_slice`", text)
        self.assertIn("update long-term docs, config wording, example config, contracts, and focused tests", text)
        self.assertIn("does not authorize a broad implementation cycle or full `live_light` claim", text)
        self.assertIn("必须在用户摘要区显示 `任务边界`", text)
        self.assertIn("并且早于 Settings / Developer / Audit 细节", text)
        self.assertIn("`GET cache` / React render 只读", text)
        self.assertIn("`manual` 或 `live_light` 补证只能走 `POST task` / worker / local fallback", text)
        self.assertIn("不在页面渲染中直连 Tushare、DeepSeek、GitHub 或交易路径", text)
        self.assertIn("不是 production evidence，也不代表完整 `live_light` 已实现", text)
        self.assertIn("`股票量化推演 / Stock Quant Projection` 的运行模式只读可见性必须与首页和雷达保持一致", text)
        self.assertIn("页面可从 `GET /api/bootstrap/status` 展示 `cache_only/manual/live_light/live_full` 当前口径", text)
        self.assertIn("不得因此创建 `live_light` bootstrap task、调用 provider/model、写配置、写 cache、泄露 token/key 或升级为 production evidence", text)
        self.assertIn("The same `runtime_mode_policy_rows` must carry config-owned boundary fields", text)
        self.assertIn("`fastapi_startup_rule`", text)
        self.assertIn("`search_typing_rule`", text)
        self.assertIn("`cache_get_rule`", text)
        self.assertIn("`react_render_rule`", text)
        self.assertIn("`ledger_rule`", text)
        self.assertIn("`ordinary_entrance_visibility_rule`", text)
        self.assertIn("`ordinary_mode_banner_rule`", text)
        self.assertIn("`production_evidence_rule`", text)
        self.assertIn("require ordinary entrances to show `任务边界` before Settings / Developer / Audit details", text)
        self.assertIn("read-only status banner rather than a task launcher or config writer", text)
        self.assertIn("not proof that full `live_light` has been implemented", text)
        self.assertIn("Runtime config operator table", text)
        self.assertIn("owned by `config.py` and surfaced read-only through `GET /api/bootstrap/status`", text)
        self.assertIn("Source-switch intent for the future light research chain", text)
        self.assertIn("`true` is effective only in `live_light` after cache render and task gating", text)
        self.assertIn("Search typing, GET cache/status, FastAPI startup, and React render remain silent", text)
        self.assertIn("Default-off release switches for later provider/model task creation and frontend automation", text)
        self.assertIn("They stay effective false until execution-request, real ledgers, browser evidence, redaction, rollback, and promotion gates pass", text)
        self.assertIn("This table is config wording, not a new implementation claim", text)
        self.assertIn('do not describe the boundary as a flat "page startup never calls providers"', text)
        self.assertIn("Future docs, tests, and review notes must name the layer being discussed", text)
        self.assertIn(
            "`cache_only` startup/render silence, React-created POST task, provider/model execution inside that task, and production acceptance evidence",
            text,
        )
        self.assertIn("absolute startup ban to runtime-mode layering, not weakened into hidden automation", text)
        self.assertIn(
            "initial render silence, task creation, real Tushare/DeepSeek execution, and production promotion are four different checkpoints",
            text,
        )
        self.assertIn('instead of flattening the boundary back into either "never automate" or "silently automate"', text)
        self.assertIn("Configured source or release switches remain operator intent in this roadmap", text)
        self.assertIn("never become effective merely because configured true", text)
        self.assertIn("`cache_only` forces effective false", text)
        self.assertIn("provider/model execution still waits for execution-request, ledgers, redaction, and promotion", text)
        self.assertIn("configured_true_is_operator_intent_not_effective_external_call", text)
        self.assertIn(
            "effective_external_call_requires_mode_task_gate_ledgers_redaction_and_promotion",
            text,
        )
        self.assertIn("runtime_config_does_not_prove_full_live_light_workflow", text)
        self.assertIn(
            "prove retained signal/capability no-feature-loss coverage, copy old Streamlit UI",
            text,
        )
        self.assertIn("retained signal/capability coverage gaps are auditable without treating old Streamlit UI copy as a goal", text)
        self.assertIn("Full retained signal/capability coverage evidence for the next-session chart is incomplete; visual/UI copy is not the target", text)
        self.assertIn("does not prove retained signal/capability coverage evidence, browser visual QA", text)
        self.assertIn("complete retained signal/capability coverage evidence", text)
        self.assertIn("does not prove retained no-feature-loss coverage", text)
        self.assertIn("`interaction_readiness_audit` distinguishes ready contracts, blockers, and coverage-pending items", text)
        self.assertIn("explicit retained signal/capability no-feature-loss coverage review", text)
        self.assertIn("retained signal/capability no-feature-loss coverage scope is explicit enough to run a future manual coverage review", text)
        self.assertIn("feature-by-feature capability coverage matrix", text)
        self.assertIn("Do not treat `next_session_legacy_parity_execution_recipe` as retained signal/capability coverage completion", text)
        self.assertIn("Next-session map contract is present, but it is still a local no-browser/no-provider guard; browser visual QA, performance trace, retained signal/capability coverage evidence", text)
        self.assertIn("Compare retained next-session signal groups and interaction evidence against Legacy Bug / UX Audit findings", text)
        self.assertIn("old Streamlit UI copy outside the goal", text)
        self.assertNotIn("prove legacy signal/capability parity, copy old Streamlit UI", text)
        self.assertNotIn("Full legacy signal/capability parity for the next-session chart is incomplete", text)
        self.assertNotIn("complete legacy signal/capability parity", text)
        self.assertNotIn("does not prove no-feature-loss parity", text)
        self.assertNotIn("explicit legacy signal/capability parity, browser visual QA", text)
        self.assertNotIn("legacy signal/capability parity completion, browser visual QA", text)
        self.assertNotIn("browser visual QA, performance trace, legacy signal/capability parity, and production ECharts replacement", text)
        self.assertNotIn("prove Streamlit parity", text)
        self.assertNotIn("Streamlit parity gaps", text)
        self.assertNotIn("Full parity with legacy Streamlit chart", text)
        self.assertNotIn("Compare against legacy Streamlit visual expectations", text)
        self.assertNotIn("future Streamlit-to-React comparison scope", text)

    def test_runtime_mode_policy_rows_expose_startup_and_search_typing_boundaries(self):
        import config

        policies = config.get_command_center_runtime_mode_policies()
        by_mode = {row["mode"]: row for row in policies}
        required_fields = (
            "fastapi_startup_rule",
            "search_typing_rule",
            "cache_get_rule",
            "react_render_rule",
            "ledger_rule",
            "ordinary_entrance_visibility_rule",
            "ordinary_mode_banner_rule",
            "configured_switch_rule",
            "effective_external_call_rule",
            "production_evidence_rule",
        )

        self.assertEqual(list(by_mode), list(config.COMMAND_CENTER_RUNTIME_MODES))
        for mode in config.COMMAND_CENTER_RUNTIME_MODES:
            row = by_mode[mode]
            for field in required_fields:
                self.assertIn(field, row)
            self.assertEqual(
                row["fastapi_startup_rule"],
                "no_provider_model_worker_trade_or_task_creation",
            )
            self.assertEqual(
                row["search_typing_rule"],
                "no_task_provider_model_call_config_write_or_cache_write",
            )
            self.assertEqual(
                row["cache_get_rule"],
                "read_only_no_provider_model_worker_or_trade",
            )
            self.assertEqual(
                row["react_render_rule"],
                "read_only_no_provider_model_worker_or_trade",
            )
            self.assertEqual(
                row["configured_switch_rule"],
                "configured_true_is_operator_intent_not_effective_external_call",
            )
            self.assertEqual(
                row["effective_external_call_rule"],
                "effective_external_call_requires_mode_task_gate_ledgers_redaction_and_promotion",
            )
            self.assertEqual(
                row["production_evidence_rule"],
                "config_policy_row_is_not_production_evidence",
            )

        contract = config.get_command_center_runtime_mode_config_contract()
        self.assertEqual(
            contract["fastapi_startup_rule"],
            "no_provider_model_worker_trade_or_task_creation",
        )
        self.assertEqual(
            contract["search_typing_rule"],
            "no_task_provider_model_call_config_write_or_cache_write",
        )
        self.assertEqual(
            contract["live_light_completion_rule"],
            "runtime_config_does_not_prove_full_live_light_workflow",
        )
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertTrue(contract["does_not_execute_trades"])

    def test_legacy_audit_first_round_intake_template_is_config_owned(self):
        import config

        contract = config.get_command_center_legacy_audit_classification_contract()

        self.assertEqual(
            contract["first_round_intake_rule"],
            "first_round_legacy_bug_ux_audit_collects_direct_problem_statement_not_keep_promotion",
        )
        for required_field in (
            "user_observation",
            "legacy_ux_bug_or_patchwork",
            "data_lineage_observation",
            "replacement_user_path",
            "frozen_legacy_path",
            "evidence_attachment",
            "keep_promotion_decision",
        ):
            self.assertIn(required_field, contract["intake_required_fields"])

        for safe_source in (
            "safe_screenshot_reference",
            "redacted_reviewer_note",
            "safe_log_summary",
        ):
            self.assertIn(safe_source, contract["intake_safe_attachment_sources"])

        for forbidden_source in (
            "raw_packet_bodies",
            "raw_logs",
            "token_key_credential_values",
            "unredacted_model_output",
            "generated_artifacts",
        ):
            self.assertIn(forbidden_source, contract["intake_forbidden_attachment_sources"])

        self.assertEqual(
            set(contract["intake_allowed_statuses"]),
            {
                "direct_evidence_intake_pending",
                "direct_evidence_observed_redesign_required",
                "blocked_by_lineage",
                "legacy_debug_retained",
                "retire_confirmed",
            },
        )
        self.assertNotIn("KEEP", contract["intake_allowed_statuses"])
        self.assertIn("hard risk / announcement risk", contract["first_round_focus_workflows"])
        self.assertIn(
            "old AI strategy advisor / cross-market advice button",
            contract["first_round_focus_workflows"],
        )
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertTrue(contract["does_not_execute_trades"])

    def test_migration_status_exposes_legacy_audit_first_round_intake(self):
        from server.services import migration_status_service

        status = migration_status_service.build_migration_status()
        summary = status["legacy_audit_first_round_intake"]
        rows = status["legacy_audit_first_round_intake_rows"]

        self.assertEqual(
            summary["first_round_intake_rule"],
            "first_round_legacy_bug_ux_audit_collects_direct_problem_statement_not_keep_promotion",
        )
        self.assertEqual(summary["focus_workflow_count"], len(rows))
        self.assertGreaterEqual(summary["focus_workflow_count"], 10)
        self.assertFalse(summary["keep_promotion_allowed_this_round"])
        self.assertFalse(summary["ordinary_entry_promotion_allowed_this_round"])
        self.assertEqual(
            summary["production_evidence_rule"],
            "legacy_audit_classification_contract_is_not_production_evidence",
        )
        self.assertFalse(summary["external_calls_triggered"])
        self.assertFalse(summary["tushare_called"])
        self.assertFalse(summary["deepseek_called"])
        self.assertTrue(summary["does_not_execute_trades"])
        self.assertIn("safe_screenshot_reference", summary["safe_attachment_sources"])
        self.assertIn("raw_packet_bodies", summary["forbidden_attachment_sources"])
        self.assertIn("unredacted_model_output", summary["forbidden_attachment_sources"])
        self.assertNotIn("KEEP", summary["allowed_statuses"])

        rows_by_workflow = {row["workflow_group"]: row for row in rows}
        self.assertIn("home/daily command", rows_by_workflow)
        self.assertIn("candidate radar", rows_by_workflow)
        self.assertIn(
            "old AI strategy advisor / cross-market advice button",
            rows_by_workflow,
        )
        for row in rows:
            self.assertEqual(row["allowed_initial_status"], "direct_evidence_intake_pending")
            self.assertFalse(row["keep_promotion_allowed_this_round"])
            self.assertFalse(row["ordinary_entry_promotion_allowed_this_round"])
            self.assertIn("user_observation", row["required_fields"])
            self.assertIn("safe_log_summary", row["safe_attachment_sources"])
            self.assertIn("token_key_credential_values", row["forbidden_attachment_sources"])

        self.assertEqual(
            status["call_ledger"][0]["legacy_audit_first_round_intake_row_count"],
            len(rows),
        )

    def test_legacy_cache_exposes_first_round_intake_as_admin_debug_only(self):
        from server.services import legacy_service

        packet = legacy_service.read_legacy_bridge_cache()
        summary = packet["legacy_audit_first_round_intake"]
        rows = packet["legacy_audit_first_round_intake_rows"]

        self.assertEqual(
            summary["status"],
            "legacy_audit_first_round_intake_visible_admin_debug_only",
        )
        self.assertTrue(summary["legacy_admin_debug_surface_only"])
        self.assertFalse(summary["keep_promotion_allowed_this_round"])
        self.assertFalse(summary["ordinary_entry_promotion_allowed_this_round"])
        self.assertEqual(summary["row_count"], len(rows))
        self.assertEqual(packet["counts"]["legacy_audit_first_round_intake_row_count"], len(rows))
        self.assertIn("safe_screenshot_reference", summary["safe_attachment_sources"])
        self.assertIn("raw_packet_bodies", summary["forbidden_attachment_sources"])
        self.assertNotIn("KEEP", summary["allowed_statuses"])
        self.assertIn(
            "local_legacy_audit_first_round_intake",
            {row["api"] for row in packet["call_ledger"]},
        )
        for row in rows:
            self.assertEqual(row["allowed_initial_status"], "direct_evidence_intake_pending")
            self.assertTrue(row["legacy_admin_debug_surface_only"])
            self.assertFalse(row["keep_promotion_allowed_this_round"])
            self.assertFalse(row["ordinary_entry_promotion_allowed_this_round"])
            self.assertIn("user_observation", row["required_fields"])

    def test_next_session_push_gate_contract_uses_signal_capability_parity_wording(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "scripts" / "next_session_map_contract.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("legacy signal/capability parity review", text)
        self.assertIn("same-packet no-feature-loss evidence", text)
        self.assertIn("does not run a browser and does not refresh market data", text)
        self.assertNotIn("Streamlit parity", text)
        self.assertNotIn("legacy Streamlit parity", text)

    def test_next_session_service_uses_signal_capability_parity_wording(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "server" / "services" / "next_session_service.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("legacy signal/capability parity review", text)
        self.assertIn("same-packet legacy signal/capability parity", text)
        self.assertIn("streamlit_parity_complete", text)
        self.assertNotIn("Streamlit parity", text)
        self.assertNotIn("legacy Streamlit parity", text)

    def test_next_session_packet_status_uses_coverage_evidence_not_legacy_completion(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "server" / "services" / "packet_service.py").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "compatibility field: retained signal/capability coverage evidence 仍未完成",
            text,
        )
        self.assertIn(
            "complete retained signal/capability coverage review before calling the ECharts map a full replacement",
            text,
        )
        self.assertNotIn(
            "complete legacy signal/capability parity review before calling the ECharts map a full replacement",
            text,
        )
        self.assertNotIn("legacy 次日图谱完整交互对齐仍未完成", text)

    def test_next_session_route_ui_uses_retained_coverage_not_legacy_parity_copy(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "desktop" / "src" / "routes" / "NextSessionMap.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "retained signal/capability no-feature-loss coverage review",
            text,
        )
        self.assertIn(
            "不替代 retained signal/capability coverage evidence",
            text,
        )
        self.assertIn(
            "ECharts same-packet retained signal/capability coverage 审查",
            text,
        )
        self.assertIn("审查信号/能力覆盖", text)
        self.assertIn("信号/能力覆盖", text)
        self.assertIn("coverage review", text)
        self.assertIn("coverage 阻断", text)
        self.assertIn("local_retained_coverage_review_ready", text)
        self.assertIn("retained_coverage_complete", text)
        self.assertIn(
            "不证明 retained signal/capability coverage evidence",
            text,
        )
        self.assertNotIn("legacy signal/capability parity", text)
        self.assertNotIn("审查信号/能力 parity", text)
        self.assertNotIn("信号/能力 parity", text)
        self.assertNotIn("parity review", text)
        self.assertNotIn("parity 阻断", text)
        self.assertNotIn("；streamlit_parity_complete:", text)
        self.assertNotIn("local_signal_capability_parity_review_ready", text)
        self.assertNotIn("signal_capability_parity_complete", text)

    def test_candidate_radar_route_ui_uses_coverage_labels_not_legacy_parity_copy(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "desktop" / "src" / "routes" / "CandidateRadar.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("先查看本地候选摘要", text)
        self.assertIn("Provider coverage 验收", text)
        self.assertIn("雷达 provider coverage dry-run", text)
        self.assertIn("Provider、worker、receipt、browser QA、retained coverage 和 production blocker 明细默认收起", text)
        self.assertIn('label: "provider coverage"', text)
        self.assertIn('label: "coverage gap"', text)
        self.assertIn("provider-backed coverage", text)
        self.assertIn("retained coverage 缺口", text)
        self.assertIn("本地 deep review 只审查候选证据、触发/失效、retained coverage、provider 和 freshness 缺口", text)
        self.assertIn("旧雷达 coverage / 输出合同审计", text)
        self.assertIn("旧雷达 coverage inventory", text)
        self.assertIn("旧雷达 coverage 验收收据", text)
        self.assertNotIn("先查看下一票候选池", text)
        self.assertNotIn("Provider parity 验收", text)
        self.assertNotIn("雷达 provider parity dry-run", text)
        self.assertNotIn("legacy parity 和 production blocker", text)
        self.assertNotIn('label: "provider parity"', text)
        self.assertNotIn('label: "parity gap"', text)
        self.assertNotIn("provider-backed parity", text)
        self.assertNotIn("legacy parity 缺口", text)
        self.assertNotIn("本地 deep review 只审查候选证据、触发/失效、legacy parity", text)
        self.assertNotIn("旧雷达 parity / 输出合同审计", text)
        self.assertNotIn("旧雷达 parity inventory", text)
        self.assertNotIn("旧雷达 parity 验收收据", text)

    def test_candidate_radar_demotes_engineering_audit_from_ordinary_first_view(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "desktop" / "src" / "routes" / "CandidateRadar.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("普通用户雷达摘要", text)
        self.assertIn("工程审计明细默认收起；完整 call ledger、release gate 和配置状态", text)
        self.assertIn('href="#audit"', text)
        self.assertIn('href="#settings"', text)
        self.assertIn("Provider、worker、receipt、browser QA、retained coverage 和 production blocker 明细默认收起", text)
        self.assertLess(text.index("普通用户雷达摘要"), text.index("工程审计明细默认收起"))
        self.assertLess(
            text.index("工程审计明细默认收起"),
            text.index('<details className="developer-audit-details">'),
        )
        self.assertLess(text.index("普通用户雷达摘要"), text.index("开发 / 审计指标"))

    def test_candidate_radar_keeps_full_pool_deep_scan_buttons_behind_advanced_details(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "desktop" / "src" / "routes" / "CandidateRadar.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("快速雷达扫描", text)
        self.assertIn("扫描输入股票池", text)
        self.assertIn("高级扫描 / 全池深研", text)
        self.assertIn("全池/深研按钮默认收起；普通用户先运行本地快扫或扫描自选/输入池", text)
        self.assertIn("规划全池扫描", text)
        self.assertIn("整理深研清单", text)
        self.assertLess(text.index("快速雷达扫描"), text.index("扫描输入股票池"))
        self.assertLess(text.index("扫描输入股票池"), text.index("高级扫描 / 全池深研"))
        self.assertLess(text.index("高级扫描 / 全池深研"), text.index("规划全池扫描"))
        advanced_section = text.split("高级扫描 / 全池深研", 1)[1]
        self.assertIn(">整理深研清单</button>", advanced_section)

    def test_candidate_radar_quant_projection_button_shows_disabled_reason(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "desktop" / "src" / "routes" / "CandidateRadar.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("quantProjectionDisabledReason", text)
        self.assertIn("按钮不可用原因：先输入股票代码；输入本身不会创建 task", text)
        self.assertIn("按钮已启用：确认后创建 Tushare-first 按钮门控 POST task；DeepSeek 保持 skipped", text)
        self.assertIn("输入股票代码只做本地校验；不会创建任务，也不会调用 Tushare 或 DeepSeek", text)
        self.assertIn("点击确认才创建 ${quantProjectionSymbolValidation.normalized} 的 Tushare-first POST task；DeepSeek skipped，成功后通过 GET cache 回放", text)
        self.assertIn("按钮门控 Tushare-first POST task / worker 推进，DeepSeek 等 governed executor", text)
        self.assertIn("Tushare ledger 来自 cache / call_ledger 回放", text)
        self.assertIn("DeepSeek 仍需 governed executor，普通页不展示 prompt/output", text)
        self.assertNotIn("确认后立即启动后台投研 task", text)
        self.assertNotIn("后台先拉 Tushare 单票小全量数据", text)
        self.assertNotIn("后端会先跑 Tushare trade_cal / daily / daily_basic / moneyflow", text)
        self.assertIn("disabled={!quantProjectionCanSubmit}", text)
        self.assertIn("quantProjectionSubmitAriaLabel", text)
        self.assertIn("quantProjectionSubmitButtonLabel", text)
        self.assertIn("title={quantProjectionSubmitButtonLabel}", text)
        self.assertIn("aria-label={quantProjectionSubmitAriaLabel}", text)
        self.assertLess(text.index("quantProjectionDisabledReason"), text.index("生成 3.0 量化推演</button>"))
        self.assertLess(text.index("title={quantProjectionSubmitButtonLabel}"), text.index("生成 3.0 量化推演</button>"))
        self.assertLess(
            text.index("生成 3.0 量化推演</button>"),
            text.index('<p className="risk-note" aria-live="polite">{quantProjectionDisabledReason}</p>'),
        )
        self.assertLess(
            text.index('<p className="risk-note" aria-live="polite">{quantProjectionDisabledReason}</p>'),
            text.index("{quantProjectionSubmitHint}"),
        )

    def test_stock_quant_projection_demotes_engineering_audit_from_ordinary_first_view(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "desktop" / "src" / "routes" / "FactorQuantHub.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("普通用户量化推演摘要", text)
        self.assertIn("没有标的时先去", text)
        self.assertIn('href="#candidates"', text)
        self.assertIn("输入代码并点击生成 3.0 量化推演；这个链接只切换本地页面，不创建 task", text)
        self.assertIn("工程审计明细默认收起；完整 factor/provider/model ledger 和配置状态", text)
        self.assertIn('href="#audit"', text)
        self.assertIn('href="#settings"', text)
        self.assertIn("Provider、model、receipt、runbook、QA blocker 和 LTG 细项默认收起", text)
        self.assertLess(text.index("普通用户量化推演摘要"), text.index("没有标的时先去"))
        self.assertLess(text.index("没有标的时先去"), text.index("工程审计明细默认收起"))
        self.assertLess(text.index("普通用户量化推演摘要"), text.index("工程审计明细默认收起"))
        self.assertLess(
            text.index("工程审计明细默认收起"),
            text.index('<details className="developer-audit-details">'),
        )
        self.assertLess(text.index("普通用户量化推演摘要"), text.index("开发 / 审计指标"))

    def test_daily_command_center_demotes_engineering_audit_from_ordinary_first_view(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "desktop" / "src" / "routes" / "CommandCenterHome.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("今日作战台摘要", text)
        self.assertIn("工程审计明细默认收起；完整 call ledger、release gate、runtime mode 和配置状态", text)
        self.assertIn('href="#audit"', text)
        self.assertIn('href="#settings"', text)
        self.assertIn("详细验收记录、开发表格和排障明细默认收起", text)
        self.assertLess(text.index("今日作战台摘要"), text.index("工程审计明细默认收起"))
        self.assertLess(
            text.index("工程审计明细默认收起"),
            text.index('<details className="developer-audit-details">'),
        )
        self.assertLess(text.index("今日作战台摘要"), text.index("开发 / 审计详情"))

    def test_ltg08_completion_boundary_uses_signal_capability_evidence_not_legacy_parity(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "command_center_3_long_term_goals.md").read_text(
            encoding="utf-8"
        )
        section = text.split("## LTG-08: ECharts 次日图谱成熟版", 1)[1].split(
            "## LTG-09:",
            1,
        )[0]

        self.assertIn("retained signal/capability coverage has direct no-feature-loss evidence", section)
        self.assertIn("retained signal/capability no-feature-loss coverage review", section)
        self.assertIn("compatibility-named local no-feature-loss recipe", section)
        self.assertIn("future retained signal/capability coverage scope", section)
        self.assertIn("retained signal/capability coverage review, browser visual QA", section)
        self.assertIn("pending retained signal/capability coverage evidence", section)
        self.assertIn("browser visual QA, performance trace, durable CI/release evidence", section)
        self.assertIn("production promotion review", section)
        self.assertIn("old Streamlit UI copy stays outside the goal", section)
        self.assertNotIn("frontend read-only boundaries, legacy signal/capability parity review", section)
        self.assertNotIn("future legacy signal/capability comparison scope", section)
        self.assertNotIn("hover/click interaction contract, legacy signal/capability parity review", section)
        self.assertNotIn("pending legacy signal/capability parity", section)
        self.assertNotIn("legacy signal/capability parity review remains pending", section)
        self.assertNotIn("legacy parity is actually complete", section)

    def test_ltg08_status_parity_wording_is_compatibility_not_ui_copy(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "server" / "services" / "migration_status_service.py"
        ).read_text(encoding="utf-8")

        self.assertIn("retained signal/capability no-feature-loss coverage recipe exist", source)
        self.assertIn("compatibility field names are not old UI/navigation parity evidence", source)
        self.assertIn(
            "Run explicit same-packet retained signal/capability no-feature-loss coverage review",
            source,
        )
        self.assertIn(
            "same-packet retained signal/capability coverage compatibility field; not old UI/navigation parity evidence",
            source,
        )
        self.assertIn(
            "same-packet retained signal/capability no-feature-loss coverage evidence; compatibility ids are not old UI/navigation parity evidence",
            source,
        )
        self.assertIn("feature-by-feature capability coverage", source)
        self.assertIn(
            "button_task_then_browser_or_coverage_evidence_review",
            source,
        )
        self.assertNotIn(
            "same-packet legacy signal/capability parity as retained signal/capability no-feature-loss coverage evidence",
            source,
        )
        self.assertNotIn(
            "same-packet legacy signal/capability parity compatibility field for retained coverage evidence",
            source,
        )
        self.assertIn(
            "browser visual/performance QA, durable CI/release evidence, and production promotion review",
            source,
        )
        self.assertIn(
            "future explicit next-session retained signal/capability coverage and production replacement tasks",
            source,
        )
        self.assertIn(
            "next_session_browser_visual_performance_and_coverage_evidence_promotion",
            source,
        )
        self.assertIn(
            "retire Streamlit visual path before retained signal/capability coverage evidence",
            source,
        )
        self.assertNotIn("button_task_then_browser_or_parity_execution", source)
        self.assertNotIn("future explicit next-session parity and production replacement tasks", source)
        self.assertNotIn("next_session_browser_visual_performance_and_parity_promotion", source)
        self.assertNotIn("retire Streamlit visual path before parity evidence", source)
        self.assertNotIn("before retiring the Streamlit visual fallback path", source)

    def test_migration_map_records_legacy_audit_and_five_commit_questions(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")

        self.assertIn("## Current Usable-Path Scope", text)
        self.assertIn("Command Center 3.0 使用者可用化最短路径", text)
        self.assertIn("不是 `14 LTG strict closeout`", text)
        self.assertIn("任何 P0-P5 进展都不能被报告为 14 个 LTG 全部完成", text)
        self.assertIn("usable-path priority", text)
        self.assertIn("P0 一键启动和前后端自动联通", text)
        self.assertIn("P1 输入股票代码后确认触发 Tushare-first 数据链", text)
        self.assertIn("只有 confirmed symbol 的按钮/POST task 可以创建或复用搜票量化推演链路", text)
        self.assertIn("typing/render/GET cache 继续静默", text)
        self.assertIn("DeepSeek 默认 skipped", text)
        self.assertIn("P2 小数据写入 cache / ledger / packet", text)
        self.assertIn("P3 候选雷达、量化推演、次日图谱显示可解释结果", text)
        self.assertIn("P4 普通用户页面隐藏或下沉工程审计噪音", text)
        self.assertIn("P5 DeepSeek governed executor 单独补", text)
        self.assertIn("不阻塞 Tushare-first、Factor light、Next Session 基础图谱", text)
        self.assertIn("P6 回到 14 LTG direct evidence / strict closeout", text)
        self.assertIn("每个 cycle 仍遵守一个主目标、一个支撑目标、最多五个文件和 checkpoint 收口", text)
        self.assertIn("不是 provider/model executor、完整 `live_light`、远端 CI 或 production acceptance", text)
        self.assertNotIn("P0-P5 进展都可以被报告为 14 个 LTG 全部完成", text)

        self.assertIn("## Legacy Bug / UX Audit Seed", text)
        self.assertIn("能力保留，不复制旧 Streamlit", text)
        self.assertIn("它不是完成审计，也不是生产验收证据", text)
        self.assertIn("## Ordinary Entrance Acceptance Map", text)
        self.assertIn("Legacy Bug / UX Audit 的覆盖锁定为普通旧工作流组", text)
        self.assertIn("home/daily command", text)
        self.assertIn("searched-symbol quant projection", text)
        self.assertIn("factor/risk/provider health", text)
        self.assertIn("discipline/backtest", text)
        self.assertIn("external brain/AI advisor", text)
        self.assertIn("`direct UX/bug evidence source`", text)
        self.assertIn("`ordinary entrance placement`", text)
        self.assertIn("`frozen legacy path`", text)
        self.assertIn(
            "| legacy workflow | classification | direct UX/bug evidence source | preserve user capability | remove / avoid from legacy | ordinary entrance placement | frozen legacy path |",
            text,
        )
        self.assertIn("seed-only；直接 UX/bug evidence pending before `KEEP`", text)
        self.assertIn(
            "seed-only；browser/performance/retained signal-capability no-feature-loss evidence pending before `KEEP`",
            text,
        )
        self.assertIn(
            "继续补 browser/performance/retained signal-capability no-feature-loss evidence",
            text,
        )
        self.assertIn("旧 Streamlit 首页按钮 / rerun flow 冻结，不搬 UI/state coupling", text)
        self.assertIn("旧同步单票作战室和 AI-as-action 文案冻结", text)
        self.assertIn("旧 fallback 雷达路径、推荐式文案和未证明性能路径冻结", text)
        self.assertIn("旧 Streamlit chart UI 与 receipt-as-replacement 口径冻结", text)
        self.assertIn("旧普通页 provider health 大表和自动探测路径冻结", text)
        self.assertIn("不迁移旧跨市场建议按钮；只允许重建为解释已有证据", text)
        self.assertNotIn("browser/performance/parity evidence pending before `KEEP`", text)
        self.assertNotIn("继续补 browser/performance/parity evidence", text)
        self.assertIn("不能从 route inventory、legacy tab name、本地 receipt 或 no-feature-loss matrix 直接升级为 `KEEP`", text)
        self.assertIn("`KEEP` 提升门槛必须是直接审计证据", text)
        self.assertIn("observed user action / workflow problem", text)
        self.assertIn("被移除的 legacy bug / confusing UX / patchwork path", text)
        self.assertIn("data-lineage check", text)
        self.assertIn("replacement ordinary entrance", text)
        self.assertIn("frozen legacy path", text)
        self.assertIn("`evidence_attachment` 只能引用 safe screenshot、脱敏 reviewer note 或 safe log summary", text)
        self.assertIn("raw packet bodies、raw logs、token/key/credential values", text)
        self.assertIn("未脱敏 model output 或 generated artifacts", text)
        self.assertIn("不能单独把旧模块升级为 `KEEP`", text)
        self.assertIn("运行模式分层和 `live_light` 配置证据只用于解释新 3.0 普通入口的任务边界", text)
        self.assertIn("Mode-layered live-light evidence factory", text)
        self.assertIn("运行模式分层的轻量实时投研证据工厂", text)
        self.assertIn("只表示 runtime vocabulary、safe config rows 和 POST-task evidence boundary 已对齐", text)
        self.assertIn("不能替代 Legacy Bug / UX Audit 的直接用户证据", text)
        self.assertIn("不能把旧 Streamlit workflow 升级为 `KEEP`", text)
        self.assertIn("不能把 `cache_only/manual/live_light/live_full` 可见性、配置行、task skeleton、receipt 或 matrix 当成 production evidence", text)
        self.assertIn("`runtime_mode_config_current_acceptance_scope`", text)
        self.assertIn("`runtime_mode_config_current_acceptance_rule`", text)
        self.assertIn("`runtime_mode_config_current_acceptance_excludes`", text)
        self.assertIn("runtime_mode_vocabulary_config_rows_and_contract_tests_only", text)
        self.assertIn("docs_config_contract_evidence_only_not_live_light_implementation", text)
        self.assertIn("frontend_autostart_wiring", text)
        self.assertIn("provider_model_executor", text)
        self.assertIn("worker_dispatch", text)
        self.assertIn("cache_write_promotion", text)
        self.assertIn("production_acceptance", text)
        self.assertIn("不能把迁移图里的 runtime-mode 可见性升级为前端自启动", text)
        self.assertIn("worker dispatch、cache 写入晋级或生产验收", text)
        self.assertIn(
            "first_round_legacy_bug_ux_audit_collects_direct_problem_statement_not_keep_promotion",
            text,
        )
        self.assertIn("不是散落在文档里的临时表", text)
        self.assertIn("`user_observation`、`legacy_ux_bug_or_patchwork`、`data_lineage_observation`", text)
        self.assertIn("safe screenshot reference、redacted reviewer note 或 safe log summary", text)
        self.assertIn("raw packet bodies、raw logs、token/key/credential values", text)
        self.assertIn("`direct_evidence_observed_redesign_required`", text)
        self.assertIn("不能直接进入 `direct_evidence_ready` 或 `KEEP`", text)
        self.assertIn("retained signal/capability coverage evidence 或生产 ECharts 替代完成", text)
        self.assertIn("retained signal/capability coverage evidence 继续标为 pending", text)
        self.assertIn("retained signal/capability coverage evidence、browser visual QA", text)
        self.assertIn("不能当作 CI evidence、retained signal/capability coverage evidence", text)
        self.assertNotIn("性能 trace、Streamlit parity 或生产 ECharts 替代完成", text)

        for classification in ("`REDESIGN`", "`LEGACY-DEBUG`", "`RETIRE`"):
            self.assertIn(classification, text)

        for entrance in (
            "今日作战台 / Daily Command Center",
            "股票量化推演 / Stock Quant Projection",
            "下一票雷达 / Candidate Radar",
        ):
            self.assertIn(entrance, text)

        self.assertIn("普通入口任务边界也必须留在用户摘要区", text)
        self.assertIn("都要在 Settings / Developer / Audit 细节之前显示 `任务边界`", text)
        self.assertIn("`GET cache` / React render 只读", text)
        self.assertIn("`manual` 或 `live_light` 补证只能走 `POST task` / worker / local fallback", text)
        self.assertIn("不在页面渲染中直连 Tushare、DeepSeek 或交易路径", text)
        self.assertIn("不是 production evidence，也不等于完整 `live_light` 已实现", text)
        self.assertIn("`runtime_mode_policy_rows` 也必须携带", text)
        self.assertIn("`cache_get_rule`", text)
        self.assertIn("`react_render_rule`", text)
        self.assertIn("`ledger_rule`", text)
        self.assertIn("`ordinary_entrance_visibility_rule`", text)
        self.assertIn("`ordinary_mode_banner_rule`", text)
        self.assertIn("`production_evidence_rule`", text)
        self.assertIn("普通入口 `任务边界` 早于 Settings / Developer / Audit", text)
        self.assertIn("ordinary mode banner 只是只读状态提示而不是 task launcher 或 config writer", text)
        self.assertIn("config policy row 不是 production evidence", text)
        self.assertIn("`config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES` 为单一 allowlist 来源", text)
        self.assertIn("`runtime_config_names_source=config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES`", text)
        self.assertIn("`runtime_config_names_match_reference_rows=true`", text)
        self.assertIn("`runtime_config_names_are_allowlisted=true`", text)
        self.assertIn("不能维护第二份 runtime config enum", text)
        self.assertIn("不能前端写回", text)
        self.assertIn("不能把 raw env dump 暴露成配置面板", text)
        self.assertIn("不能把配置表当成 `live_light` production evidence", text)
        self.assertIn("三入口的普通用户摘要必须共享 source-state chips", text)
        self.assertIn("`cache`、`Tushare`、`DeepSeek`、`pending`、`degraded`、`last_successful_cache/result`", text)
        self.assertIn("`DeepSeek` 只表示 explanation-only 且不是数据源或 action writer", text)
        self.assertIn("这些 chips 只是只读 UI 词表", text)
        self.assertIn("不创建 task、不调用 provider/model、不写 cache/config，也不是 production evidence", text)
        self.assertIn("迁移图里的 provider/model evidence 也必须先有 redacted `call_ledger` / `model_ledger` rows", text)
        self.assertIn("缺 ledger 的结果只能保持 `local_or_pending`", text)
        self.assertIn("不能推进 `live_light`、LTG 完成、Streamlit 退场或 production acceptance", text)
        self.assertIn("DeepSeek 文本、model summary 或 explanation status 不能满足 missing evidence", text)
        self.assertIn("不能成为 next-click action", text)
        self.assertIn("不能替代 provider/cache/factor/operation-zone evidence", text)
        self.assertIn("只能在 `model_ledger` 状态和 redaction review 下解释已有证据", text)
        self.assertIn("普通 UI / migration report 只能展示 safe summaries", text)
        self.assertIn("不得暴露 raw prompts、raw model output、unredacted provider errors", text)
        self.assertIn("白名单字段、`model_ledger` 状态和 redaction review", text)
        self.assertIn("三入口还必须共享 next-click 规则", text)
        self.assertIn("每个普通入口只突出一个主下一步动作", text)
        self.assertIn("blocked/degraded 时显示为什么不能点", text)
        self.assertIn("从已确认代码指向 `生成 3.0 量化推演`", text)
        self.assertIn("搜索输入、React render、mode banner、source-state chip、DeepSeek 文本和 radar candidate 都不是 next-click action", text)
        self.assertIn("任何会创建工作的 next click 都必须走 POST task / worker / local fallback", text)
        self.assertIn("`FactorQuantHub.tsx` 还只读读取 `GET /api/bootstrap/status`", text)
        self.assertIn("在普通用户量化推演摘要中展示 `cache_only/manual/live_light/live_full` 当前运行模式", text)
        self.assertIn("该可见性不创建 `POST /api/bootstrap/live-startup`、不调用 provider/model、不写配置或 cache、不泄露 token/key", text)
        self.assertIn("也不是 production evidence 或完整 `live_light` 实现", text)

        for question_fragment in (
            "保留了什么用户能力",
            "移除了什么旧 UX 问题",
            "哪条旧 bug / patchwork 路径没有迁移",
            "普通用户哪里更简单",
            "实际减少了哪个 blocker",
        ):
            self.assertIn(question_fragment, text)

        self.assertIn("不能进入普通入口", text)
        self.assertIn("LTG-13 的 no-feature-loss 只表示有用信号", text)
        self.assertIn("候选分组、扫描范围、证据链", text)
        self.assertIn("它不是旧雷达 UI parity", text)
        self.assertIn("不是旧 fallback 路径 parity", text)
        self.assertIn("不是把候选包装成买入推荐", text)
        self.assertIn("lineage 不清、已知 bug 或历史 patchwork", text)
        self.assertIn("不能用 no-feature-loss 作为照搬理由", text)
        self.assertIn("普通页只展示摘要和缺口；详细合同留在 Settings / Developer / Audit", text)
        self.assertNotIn("详细合同留在 developer/audit", text)
        self.assertIn("不证明 retained signal/capability coverage evidence 或生产替代，也不代表复制旧 Streamlit 图表 UI", text)
        self.assertIn("性能 trace durable promotion、retained signal/capability coverage evidence 和生产替代仍待验收", text)
        self.assertIn("旧 Streamlit 图表 UI/tab 复制不属于验收目标", text)
        self.assertIn("不能理解成复制旧 Streamlit 图表 UI 或旧 tab navigation", text)
        self.assertNotIn("不证明 legacy signal/capability parity 或生产替代", text)
        self.assertNotIn("性能 trace durable promotion、legacy signal/capability parity 和生产替代", text)
        self.assertNotIn("legacy signal/capability parity 继续标为 pending", text)
        self.assertNotIn("CI evidence、legacy signal/capability parity", text)
        self.assertNotIn("不证明 Streamlit parity 或生产替代", text)
        self.assertNotIn("性能 trace durable promotion、Streamlit parity 和生产替代", text)

    def test_ltg10_long_term_goal_uses_capability_replacement_language(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "command_center_3_long_term_goals.md").read_text(
            encoding="utf-8"
        )
        section = text.split("## LTG-10: Streamlit 完全退出普通主流程", 1)[1].split(
            "## LTG-11:", 1
        )[0]

        self.assertIn("ordinary capability replacement evidence", section)
        self.assertIn("Candidate Radar signal/capability replacement evidence", section)
        self.assertIn("provider-backed acceptance", section)
        self.assertIn("explicit_replacement_parity_review_then_streamlit_fallback_retirement_review", section)
        self.assertIn("compatibility id", section)
        self.assertIn("not old Streamlit UI parity", section)
        self.assertNotIn("ordinary workflow replacement parity", section)
        self.assertNotIn("Candidate Radar replacement parity", section)
        self.assertNotIn("prove replacement parity", section)

    def test_ltg13_long_term_goal_uses_signal_capability_provider_evidence_language(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "command_center_3_long_term_goals.md").read_text(
            encoding="utf-8"
        )
        section = text.split("## LTG-13: 下一票雷达快扫生产化", 1)[1].split(
            "## LTG-14:", 1
        )[0]
        table_row = next(
            line for line in text.splitlines() if line.startswith("| LTG-13 |")
        )
        checked_text = table_row + "\n" + section

        self.assertIn("legacy signal/capability acceptance receipt", table_row)
        self.assertIn("provider-backed radar signal/capability dry-run", table_row)
        self.assertIn("provider-backed radar signal/capability acceptance", section)
        self.assertIn("provider-backed radar signal/capability call ledger", section)
        self.assertIn("compatibility ids, not old UI/navigation parity evidence", section)
        self.assertIn("compatibility field for provider-backed radar signal/capability evidence", section)
        self.assertNotIn("provider parity", checked_text)
        self.assertNotIn("provider-backed parity", checked_text)
        self.assertNotIn("legacy parity", checked_text)

    def test_migration_map_ltg10_observed_row_uses_capability_replacement_language(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")
        section = text.split("Migration Status 现在还会从本地静态 Streamlit legacy contract", 1)[1].split(
            "Migration Status 现在还会从本地 release gate 静态 helper", 1
        )[0]

        self.assertIn("ordinary capability replacement evidence", section)
        self.assertIn("Candidate Radar signal/capability replacement evidence", section)
        self.assertIn("provider-backed acceptance", section)
        self.assertNotIn("ordinary workflow parity、Candidate Radar parity、provider-backed parity", section)

    def test_migration_map_ltg13_provider_evidence_uses_signal_capability_language(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")
        browser_review = text.split("LTG-13 Candidate Radar 的本地浏览器 QA", 1)[1].split(
            "运行模式迁移采用", 1
        )[0]
        section = text.split(
            "Candidate Radar 现在还输出 `candidate_radar_production_activation_receipt`",
            1,
        )[1].split(
            "Candidate Radar 现在还提供 `POST /api/candidate-radar/full-pool-worker-scan`",
            1,
        )[0]

        self.assertIn("provider-backed radar signal/capability acceptance", browser_review)
        self.assertIn("provider-backed radar signal/capability acceptance", section)
        self.assertIn("provider-backed radar signal/capability scope ticket", section)
        self.assertIn("provider-backed radar signal/capability call ledger", section)
        self.assertIn("legacy signal/capability", section)
        self.assertNotIn("provider-backed parity", browser_review)
        self.assertNotIn("provider-backed parity", section)
        self.assertNotIn("provider parity scope", section)
        self.assertNotIn("legacy parity", section)

    def test_migration_map_candidate_radar_table_uses_signal_capability_language(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")
        row = text.split("| 下一票候选雷达 |", 1)[1].split(
            "| 风险护栏 / 安全线 |",
            1,
        )[0]

        self.assertIn("legacy signal/capability inventory", row)
        self.assertIn("provider-backed radar signal/capability acceptance", row)
        self.assertIn("provider-backed signal/capability 缺口", row)
        self.assertIn("stage/signal-capability/required-signal/blocker rows", row)
        self.assertNotIn("legacy parity inventory", row)
        self.assertNotIn("provider-backed parity", row)
        self.assertNotIn("stage/parity/required-signal", row)

    def test_migration_map_candidate_radar_route_paragraph_uses_signal_capability_language(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")
        section = text.split("`/api/candidate-radar/cache`", 1)[1].split(
            "Candidate Radar 现在还输出 `candidate_radar_production_activation_receipt`",
            1,
        )[0]

        self.assertIn("legacy signal/capability coverage 阻断项", section)
        self.assertIn("stage rows、signal/capability rows、required signal rows", section)
        self.assertIn("输出字段 signal/capability coverage", section)
        self.assertIn("provider-backed radar signal/capability acceptance", section)
        self.assertIn("旧雷达 signal/capability 不降能验收清单", section)
        self.assertNotIn("legacy parity 阻断项", section)
        self.assertNotIn("parity rows、required signal rows", section)
        self.assertNotIn("输出字段 parity", section)
        self.assertNotIn("provider-backed parity", section)

    def test_migration_map_streamlit_row_keeps_receipts_from_parity_claim(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")
        section = text.split("| Streamlit 旧工作台 |", 1)[1].split(
            "## 当前可用 API", 1
        )[0]

        self.assertIn("ordinary capability replacement evidence", section)
        self.assertIn("receipt/合同通过不等于 Streamlit fallback removal", section)
        self.assertIn("complete ordinary-workflow exit", section)
        self.assertNotIn("fallback removal、replacement parity、admin/debug retirement", section)
        self.assertNotIn(
            "Streamlit fallback removal、replacement parity、admin/debug retirement",
            text,
        )

    def test_migration_map_next_action_queue_uses_ltg10_capability_replacement_label(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")
        section = text.split("| 迁移状态 / 14 个长期目标 |", 1)[1].split(
            "| Command Center 3.0 本地入口 |", 1
        )[0]

        self.assertIn("Streamlit ordinary capability replacement / retirement review", section)
        self.assertNotIn("Streamlit replacement parity/retirement review", section)

    def test_migration_map_runtime_config_intent_is_not_effective_external_call(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")
        section = text.split("运行模式迁移采用", 1)[1].split(
            "运行配置键的漂移防线", 1
        )[0]

        self.assertIn("任何 `configured=true` 都只是 operator intent", section)
        self.assertIn("不是 effective external call", section)
        self.assertIn("`fastapi_startup_rule`", section)
        self.assertIn("`search_typing_rule`", section)
        self.assertIn("`configured_switch_rule`", section)
        self.assertIn("`effective_external_call_rule`", section)
        self.assertIn("FastAPI startup、search typing、GET cache / React render 只读且不创建工作", section)
        self.assertIn("`configured=true` 只是 operator intent 而不是 effective external call", section)
        self.assertIn("effective external work 仍需 mode/task gate、ledger、redaction、promotion gate", section)
        self.assertIn("effective external work 仍需 mode/task gate", section)
        self.assertIn("runtime config 不能证明完整 `live_light` workflow", section)

    def test_app_migration_plan_records_no_blind_copy_and_audit_gate(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "app_migration_plan.md").read_text(encoding="utf-8")

        self.assertIn("Command Center 3.0 must not copy the old Streamlit app one-to-one", text)
        self.assertIn("preserving useful user capabilities", text)
        self.assertIn("does not mean copying legacy UI", text)
        self.assertIn("historical patchwork", text)
        self.assertIn("Legacy Bug / UX Audit", text)
        self.assertIn("`KEEP` promotion requires direct Legacy Bug / UX Audit evidence", text)
        self.assertIn("the specific legacy bug/confusing UX/patchwork path removed", text)
        self.assertIn("data-lineage check", text)
        self.assertIn("replacement ordinary entrance", text)
        self.assertIn("frozen legacy path", text)
        self.assertIn("cannot make a legacy module ordinary-user-ready by themselves", text)
        self.assertIn("Direct evidence attachments must be safe references", text)
        self.assertIn("screenshot reference, redacted reviewer note, or safe log summary", text)
        self.assertIn("Do not attach raw packet bodies, raw logs, token/key/credential values", text)
        self.assertIn("unredacted model output, or generated artifacts", text)
        self.assertIn("Ordinary entrances should share one source-state chip vocabulary", text)
        self.assertIn("`cache`, `Tushare`, `DeepSeek`, `pending`, `degraded`, and `last_successful_cache/result`", text)
        self.assertIn("explanation-only model output", text)
        self.assertIn("Rendering these chips is read-only planning language", text)
        self.assertIn("must not create tasks, call provider/model, write cache/config, or promote production evidence", text)
        self.assertIn("Provider/model evidence in this plan requires redacted `call_ledger` / `model_ledger` rows", text)
        self.assertIn("missing ledger rows keep the result local or pending", text)
        self.assertIn("cannot promote `live_light`, LTG completion, or production acceptance", text)
        self.assertIn("Migration reports must use safe summaries only", text)
        self.assertIn("no raw prompts, raw model output, unredacted provider errors", text)
        self.assertIn("whitelisted fields with `model_ledger` status and redaction review", text)
        self.assertIn("Ordinary entrances should also share one next-click rule", text)
        self.assertIn("show one primary safe action", text)
        self.assertIn("show a clear disabled/degraded reason", text)
        self.assertIn("route a confirmed symbol to `生成 3.0 量化推演`", text)
        self.assertIn("must not behave as hidden next-click actions", text)
        self.assertIn("DeepSeek text, model summaries, or explanation status cannot satisfy missing evidence", text)
        self.assertIn("cannot replace provider/cache/factor/operation-zone evidence", text)
        self.assertIn("may only explain existing evidence with `model_ledger` status and redaction review", text)
        self.assertIn("Any work-creating action remains POST task / worker / local fallback only", text)
        self.assertIn("each ordinary entrance must expose next click", text)
        self.assertIn("Tushare/cache/DeepSeek/pending source state", text)
        self.assertIn("research-only boundary that is not a buy/sell instruction", text)
        self.assertIn("missing evidence", text)
        self.assertIn("blocked/degraded state", text)
        self.assertIn("last successful cache/result", text)
        self.assertIn("普通入口任务边界 must stay visible in the user summary area", text)
        self.assertIn("show `任务边界` before Settings / Developer / Audit details", text)
        self.assertIn("`GET cache` / React render 只读", text)
        self.assertIn("`manual` 或 `live_light` 补证只能走 `POST task` / worker / local fallback", text)
        self.assertIn("must not directly call Tushare、DeepSeek、GitHub 或交易路径 during render", text)
        self.assertIn("not production evidence", text)
        self.assertIn("does not mean the full `live_light` workflow is implemented", text)
        self.assertIn("Mode-layered live-light evidence factory", text)
        self.assertIn("运行模式分层的轻量实时投研证据工厂", text)
        self.assertIn("docs/config wording only", text)
        self.assertIn("cannot replace direct Legacy Bug / UX Audit evidence", text)
        self.assertIn("promote any old Streamlit workflow to `KEEP`", text)
        self.assertIn("prove frontend wiring", text)
        self.assertIn("prove provider/model execution", text)
        self.assertIn("become production acceptance evidence", text)
        self.assertIn("`股票量化推演 / Stock Quant Projection` may also show a read-only runtime-mode banner", text)
        self.assertIn("from `GET /api/bootstrap/status` in its ordinary summary", text)
        self.assertIn("using the same `cache_only/manual/live_light/live_full` vocabulary as the home and radar pages", text)
        self.assertIn("That banner is only a visibility aid", text)
        self.assertIn("must not create `POST /api/bootstrap/live-startup`", text)
        self.assertIn("call provider/model, write config/cache, expose token/key", text)
        self.assertIn("upgrade a local receipt into production evidence", text)
        self.assertIn("The migration plan references `runtime_mode_policy_rows`", text)
        self.assertIn("`fastapi_startup_rule`", text)
        self.assertIn("`search_typing_rule`", text)
        self.assertIn("`cache_get_rule`", text)
        self.assertIn("`react_render_rule`", text)
        self.assertIn("`ledger_rule`", text)
        self.assertIn("`ordinary_entrance_visibility_rule`", text)
        self.assertIn("`ordinary_mode_banner_rule`", text)
        self.assertIn("`configured_switch_rule`", text)
        self.assertIn("`effective_external_call_rule`", text)
        self.assertIn("`production_evidence_rule`", text)
        self.assertIn("ordinary-entry `任务边界` visibility before Settings / Developer / Audit", text)
        self.assertIn("ordinary mode banner read-only status display rather than task launching or config writing", text)
        self.assertIn("`configured=true` as operator intent rather than an effective external call", text)
        self.assertIn("effective external work still requiring mode/task gate plus ledgers/redaction/promotion", text)
        self.assertIn("config policy rows remaining non-production evidence", text)
        self.assertIn("The operator-facing config口径 is", text)
        self.assertIn("server config is the source of truth", text)
        self.assertIn("read-only, non-editable, no-writeback, no-secret, and non-production evidence", text)
        self.assertIn("A configured source switch or release switch is not the same thing as an effective external call", text)
        self.assertIn("`cache_only` forces effective automation false even if every live switch is configured true", text)
        self.assertIn("These runtime config rows and contracts are docs/config handoff evidence only", text)
        self.assertIn("They do not implement provider/model execution", text)
        self.assertIn("do not complete frontend wiring", text)
        self.assertIn("do not collect browser nonblocking evidence", text)
        self.assertIn("do not promote `live_light` or any LTG to production acceptance", text)
        self.assertIn("The checkpoint contract fixes the current release-first priority order as", text)
        self.assertIn("`fix_push_gate_ci_evidence`", text)
        self.assertIn("`legacy_bug_ux_audit_for_streamlit_ordinary_workflows`", text)
        self.assertIn("`rebuild_ltg13_candidate_radar_user_usable_workflow`", text)
        self.assertIn("`searched_symbol_to_generate_3_0_quant_projection`", text)
        self.assertIn("`show_provider_model_cache_pending_state_on_page`", text)
        self.assertIn("`move_engineering_audit_tables_out_of_ordinary_flow`", text)
        self.assertIn("runtime-mode docs/config wording remains a supporting guard", text)
        self.assertIn("not an active priority item that can displace CI review or Legacy Bug / UX Audit", text)
        self.assertIn("`COMMAND_CENTER_LIVE_STARTUP_AUTOSTART`", text)
        self.assertIn("Local bootstrap task-create/reuse guard after cache render, not provider/model authorization", text)
        self.assertIn("`COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART`", text)
        self.assertIn("Safe searched-symbol submit guard for local quant-projection receipt task, not search typing automation", text)
        self.assertIn("`COMMAND_CENTER_LIVE_ALLOW_FULL_POOL`", text)
        self.assertIn("no hidden `live_full` automation in this migration phase", text)
        self.assertIn("`KEEP` means useful and reliable enough to preserve with minimal redesign", text)
        self.assertIn("`REDESIGN` means useful capability but old UX/code should be rebuilt", text)
        self.assertIn("`LEGACY-DEBUG` means keep only for admin/debug/fallback", text)
        self.assertIn("`RETIRE` means freeze or remove from ordinary user workflow", text)

        for classification in ("`KEEP`", "`REDESIGN`", "`LEGACY-DEBUG`", "`RETIRE`"):
            self.assertIn(classification, text)

        for entrance in (
            "今日作战台 / Daily Command Center",
            "股票量化推演 / Stock Quant Projection",
            "下一票雷达 / Candidate Radar",
        ):
            self.assertIn(entrance, text)

        for question_fragment in (
            "what user capability was preserved",
            "what legacy UX problem was removed",
            "which legacy bug or patchwork path was intentionally not migrated",
            "what became simpler for a non-technical user",
            "which real blocker was reduced",
        ):
            self.assertIn(question_fragment, text)

        self.assertIn("not production acceptance evidence", text)
        self.assertIn("does not complete any LTG by itself", text)
        self.assertIn("Preserve runtime-mode automation boundaries", text)
        self.assertIn("Keep GET packet/cache endpoints read-only in every mode", text)
        self.assertIn("Allow `live_light` only for bounded local background task creation", text)
        self.assertIn("backtests, Tushare full scans, full-market scans", text)
        self.assertIn("Preserve useful capabilities, data sources, signals, evidence chains", text)
        self.assertIn("legacy workbench remains fallback/admin/debug", text)
        self.assertIn("Streamlit is retained as fallback/admin/debug", text)
        self.assertIn("must not be described as the primary 3.0 runtime surface", text)
        self.assertIn("not the primary 3.0 surface", text)
        self.assertIn("until the React/Tauri workflow is demonstrably easier", text)
        self.assertIn("Keep the research decision loop clear", text)
        self.assertIn("research-only strategy context", text)
        self.assertIn("explain existing evidence without issuing buy/sell instructions", text)
        self.assertIn("### Option A: pywebview + Streamlit fallback hardening", text)
        self.assertIn("fallback/admin/debug safety path", text)
        self.assertIn("must not become the ordinary-user migration target", text)
        self.assertIn("packet/API-backed 3.0 workflows", text)
        self.assertIn("Reuse boundary: service packets, data adapters, evidence chains", text)
        self.assertIn("radar signal definitions, and ETF research inputs can remain referenceable", text)
        self.assertIn("Streamlit rendering code, confusing navigation, buggy flows", text)
        self.assertIn("must not be reused as ordinary 3.0 UX", text)
        self.assertIn("high for fallback/admin/debug recovery only", text)
        self.assertIn("cannot prove the React/Tauri ordinary workflow is clearer or ready", text)
        self.assertIn("Long term: prioritize a Tauri + React + Python local API pilot around the three ordinary entrances", text)
        self.assertIn("prove those user paths are easier, clearer, and more reliable", text)
        self.assertIn("综合推演中心 2.0 is now a useful packetized evidence source and transition workspace", text)
        self.assertIn("not the target ordinary 3.0 UX", text)
        self.assertIn("recompose its useful packets into the three ordinary entrances", text)
        self.assertIn("Default into a clear 3.0 entry / transition screen", text)
        self.assertIn("three ordinary entrances first", text)
        self.assertIn(
            "legacy fallback must be clearly labeled fallback/admin/debug or rollback",
            text,
        )
        self.assertIn("not a fourth ordinary entrance", text)
        self.assertIn("deeper Streamlit tab navigation", text)
        self.assertNotIn("ordinary users toward the three ordinary entrances or the legacy fallback", text)
        self.assertIn(
            "Keep the Streamlit UI reachable only as fallback/admin/debug",
            text,
        )
        self.assertIn("it is not the ordinary 3.0 UX target", text)
        self.assertIn("Redesign or freeze confusing legacy UX", text)
        self.assertIn("unclear data lineage", text)
        self.assertIn("before they enter an ordinary React/Tauri workflow", text)
        self.assertIn("Preserve useful research capabilities without promoting confusing legacy workflows", text)
        self.assertIn("Rebuild the three ordinary entrances in Tauri + React", text)
        self.assertIn("next click, source state, missing evidence", text)
        self.assertIn(
            "Keep the old Streamlit app reachable only as fallback/admin/debug or rollback path",
            text,
        )
        self.assertIn("do not present it as an ordinary-user advanced entrance", text)
        self.assertNotIn("available as an advanced legacy mode", text)
        self.assertIn("### Phase 5: Audit-gated workflow migration", text)
        self.assertIn("searched-symbol -> `生成 3.0 量化推演`", text)
        self.assertIn("Move detailed engineering contract tables", text)
        self.assertIn("Keep margin ETF, trading discipline, backtest labs", text)
        self.assertIn("Do not remove Streamlit fallback/admin/debug during this stage", text)
        self.assertIn(
            "Do not remove the legacy workbench rollback path, but do not promote it as an ordinary 3.0 entrance",
            text,
        )
        self.assertIn("`LEGACY-DEBUG`", text)
        self.assertIn("Do not bypass DeepSeek, Tushare, AkShare, Supabase, or backtest governance", text)
        self.assertIn("safe params, ledgers, redaction, and no-trade/no-action boundaries", text)
        self.assertIn("Do not bypass service contracts, task governance, ledgers, redaction, or mode gates", text)
        self.assertIn("explicit POST task / worker / local fallback boundaries", text)
        self.assertIn(
            "Every migration phase must preserve a fallback/admin/debug or rollback path without presenting that path as an ordinary workflow, promotion shortcut, or production evidence",
            text,
        )
        self.assertNotIn("Every migration phase must preserve a fallback path.", text)
        self.assertIn("Do not treat docs/config/scaffold/preflight/local receipt, matrix, mock, or sanitizer evidence as production acceptance evidence", text)
        self.assertIn("Do not add broad LTG contracts, receipts, runbooks, or stage-scope manifests unless they directly reduce a current release blocker", text)
        self.assertIn("direct acceptance, safety scans, and no-trade/no-action review", text)
        self.assertIn("Fix push gate / CI evidence", text)
        self.assertIn("local gate or checkpoint evidence is not a substitute", text)
        self.assertIn("current matching remote CI green result or reviewed failure logs", text)
        self.assertIn("Keep the Legacy Bug / UX Audit current", text)
        self.assertIn("Rebuild LTG-13 Candidate Radar as a user-usable workflow", text)
        self.assertIn("searched-symbol -> `生成 3.0 量化推演`", text)
        self.assertIn("Show provider/model/cache/pending state clearly on the page", text)
        self.assertIn("Move excessive engineering audit tables", text)
        self.assertIn("away from ordinary user flow and into Settings / Developer / Audit", text)
        self.assertIn("ordinary pages should keep only user-facing summary", text)
        self.assertIn("missing-evidence, blocked/degraded, last-cache/result, and next-action rows", text)
        self.assertIn("unless an engineering detail directly explains the current decision surface", text)
        self.assertIn("Before any ordinary entrance moves from audit-pending to user-usable", text)
        self.assertIn("capture first-view evidence that next click, source state, missing evidence", text)
        self.assertIn("appear before any engineering audit table", text)
        self.assertIn(
            "Route existence, packet availability, receipt rows, local task success, no-feature-loss matrices, Settings-only detail, or docs/config wording are not promotion evidence",
            text,
        )
        self.assertNotIn(
            "Route existence, packet availability, receipt rows, Settings-only detail, or docs/config wording are not promotion evidence",
            text,
        )
        self.assertIn("Settings / Developer / Audit", text)

        for stale_phase_rule in (
            "Continue to prevent automatic heavy task execution",
            "Keep all heavy tasks button gated",
            "Require explicit user action for DeepSeek calls",
            "Require explicit user action for Tushare full scans and other heavy market scans",
            "Preserve the current business chain and existing legacy workbench while new surfaces mature",
            "preserve all current business flows",
            "Do not change DeepSeek, Tushare, AkShare, Supabase, or backtest business logic",
            "Do not change service contracts",
            "Do not change DeepSeek call logic",
            "Do not change Tushare, AkShare, or Supabase data chains",
            "Do not change the backtest engine",
            "### Phase 5: Gradual module migration",
            "- Migrate margin ETF.",
            "- Migrate trading discipline.",
            "- Migrate quant inference.",
            "Commit the current strategy execution card patch",
            "Add `docs/app_migration_plan.md`",
            "harden `desktop_app.py` startup self-checks",
            "extract the command center adapter from `app.py`",
            "Start a Tauri / React pilot only after the packet and local API boundary is stable",
            "The Streamlit app remains the primary runtime surface",
            "Short term: continue with pywebview + Streamlit polish",
            "### Option A: Continue pywebview + Streamlit polish",
            "This option keeps the current architecture",
            "Fit: best short-term path",
            "Code reuse rate: very high. Existing Streamlit pages",
            "Current feature stability: highest",
            "Keep the trading decision loop clear: refresh data, generate strategy execution advice, generate daily decision",
            "starting only with 综合推演中心 2.0",
            "presents the main trading workflow through packetized service outputs",
            "Default directly into 综合推演中心 2.0",
        ):
            self.assertNotIn(stale_phase_rule, text)

    def test_architecture_records_user_first_react_tauri_migration_boundary(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "command_center_3_architecture.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("架构迁移不是把 Streamlit UI、旧导航、已知 bug 或历史 patchwork 一比一搬到 React/Tauri", text)
        self.assertIn("React route 层的普通用户中心应优先围绕", text)
        self.assertIn("今日作战台 / Daily Command Center", text)
        self.assertIn("股票量化推演 / Stock Quant Projection", text)
        self.assertIn("下一票雷达 / Candidate Radar", text)
        self.assertIn("重组服务 packets、数据源、信号、证据链和研究流程", text)
        self.assertIn("next click、Tushare/cache/DeepSeek/pending source", text)
        self.assertIn("research-only not-buy/sell boundary", text)
        self.assertIn("blocked/degraded state 和 last successful cache/result", text)
        self.assertIn("known bug、difficult-to-use UX、confusing workflow 或 unclear data lineage", text)
        self.assertIn("必须保持 `REDESIGN`、`LEGACY-DEBUG` 或 `RETIRE`", text)
        self.assertIn("直到有直接 UX/bug evidence 证明它可以进入普通 workflow", text)
        self.assertIn("架构层必须区分 `route_inventory_or_scaffold_evidence` 与 `direct_user_evidence`", text)
        self.assertIn("route、packet、receipt、matrix 或 docs/config scaffold 只能说明迁移覆盖方向", text)
        self.assertIn("不能证明普通用户入口更清晰或允许 `KEEP`/退场评审", text)
        self.assertIn("工程合同、receipt、runbook 和 LTG audit 默认进入 Settings / Developer / Audit", text)

    def test_architecture_candidate_radar_uses_signal_capability_provider_language(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "command_center_3_architecture.md").read_text(
            encoding="utf-8"
        )
        section = text.split("`GET /api/candidate-radar/cache`", 1)[1].split(
            "`POST /api/tasks/refresh-tushare-facts`",
            1,
        )[0]

        self.assertIn("legacy signal/capability acceptance", section)
        self.assertIn("输出字段 signal/capability coverage", section)
        self.assertIn("stage/signal-capability/required-signal/blocker rows", section)
        self.assertIn("compatibility route id", section)
        self.assertIn("provider-backed radar signal/capability acceptance", section)
        self.assertIn("provider-backed radar signal/capability scope ticket", section)
        self.assertIn("provider-backed radar signal/capability call ledger", section)
        self.assertIn("legacy signal/capability evidence", section)
        self.assertNotIn("provider-backed parity", section)
        self.assertNotIn("provider parity scope", section)
        self.assertNotIn("provider parity call ledger", section)
        self.assertNotIn("legacy parity", section)
        self.assertNotIn("输出字段 parity", section)
        self.assertNotIn("stage/parity/required-signal", section)

    def test_handoff_protocol_requires_migration_checkpoint_answers(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "codex_handoff_protocol.md").read_text(encoding="utf-8")

        self.assertIn("Migration checkpoint answers", text)
        for question_fragment in (
            "What user capability was preserved",
            "What legacy UX problem was removed",
            "Which legacy bug or patchwork path was intentionally not migrated",
            "What became simpler for a non-technical user",
            "Which real blocker was reduced",
        ):
            self.assertIn(question_fragment, text)

        self.assertIn("Production-evidence boundary", text)
        self.assertIn("docs/config/scaffold/preflight/local receipt evidence", text)
        self.assertIn("real production acceptance evidence", text)
        self.assertIn("Legacy audit promotion gate", text)
        self.assertIn("whether any module was promoted to `KEEP`", text)
        self.assertIn("direct Legacy Bug / UX Audit evidence", text)
        self.assertIn("observed user action/workflow problem", text)
        self.assertIn("removed legacy bug/confusing UX/patchwork path", text)
        self.assertIn("data-lineage check", text)
        self.assertIn("replacement ordinary entrance", text)
        self.assertIn("frozen legacy path", text)
        self.assertIn("at most one main target and one supporting target", text)
        self.assertIn("modify no more than five files", text)
        self.assertIn("end with a `Checkpoint`", text)
        self.assertIn("Cycle scope", text)
        self.assertIn("main target, supporting target, changed file count", text)
        self.assertIn("one-main / one-support / five-file cap", text)
        self.assertIn("checkpoint-style cycle reporting", text)
        self.assertIn("either commit or checkpoint according to scope", text)
        self.assertIn("Checkpoint-only docs/config/runtime-mode wording cycles", text)
        self.assertIn("without forcing a commit unless the user explicitly asks for one", text)
        self.assertIn("explicit no-commit checkpoint status", text)
        self.assertIn("Mode-layered live-light evidence factory", text)
        self.assertIn("运行模式分层的轻量实时投研证据工厂", text)
        self.assertIn("cannot replace direct Legacy Bug / UX Audit evidence", text)
        self.assertIn("cannot turn runtime mode visibility, config rows, task skeletons, receipts, or matrices into production evidence", text)
        self.assertIn("Current execution target", text)
        self.assertIn("pause `14 LTG strict closeout` as the active closeout loop", text)
        self.assertIn("Command Center 3.0 使用者可用化最短路径", text)
        self.assertIn("Current usable-path priority ladder", text)
        self.assertIn("P0 one-click startup and frontend/backend auto connection", text)
        self.assertIn("P1 stock-code confirmation button triggers the Tushare-first data chain", text)
        self.assertIn("P2 small data writes to cache / ledger / packet", text)
        self.assertIn("P3 Candidate Radar, Quant Projection, and Next Session map show interpretable results", text)
        self.assertIn("P4 ordinary user pages hide or demote engineering audit noise", text)
        self.assertIn("P5 DeepSeek governed executor is separate and must not block Tushare or basic maps", text)
        self.assertIn("P6 return to 14 LTG direct evidence / strict closeout", text)
        self.assertIn("Usable-path boundaries", text)
        self.assertIn("page open, search typing, React render, and GET cache stay silent", text)
        self.assertIn("a confirmation click may trigger Tushare through the task path", text)
        self.assertIn("DeepSeek real calls wait for the governed executor", text)
        self.assertIn("token/key material must not enter frontend, logs, packet, or cache", text)
        self.assertIn("this phase must not be reported as all 14 LTGs complete", text)
        self.assertIn("User pastes the returned report to ChatGPT", text)
        self.assertNotIn("User pastes CHATGPT_HANDOFF to ChatGPT", text)
        self.assertIn("Legacy parity means preserving useful user capabilities", text)
        self.assertIn("data sources, signals, evidence chains, and research workflows", text)
        self.assertIn("does not mean copying legacy UI, navigation, bugs, historical patchwork", text)
        self.assertIn("Before any legacy Streamlit workflow is promoted", text)
        self.assertIn("Legacy Bug / UX Audit classification", text)
        self.assertIn("`KEEP`, `REDESIGN`, `LEGACY-DEBUG`, or `RETIRE`", text)
        self.assertIn("known bugs, confusing UX, historical patchwork, or unclear data lineage", text)
        self.assertIn("out of ordinary workflow code", text)
        self.assertIn("Streamlit stays fallback / legacy / admin / debug", text)
        self.assertIn("React/Tauri ordinary entrances are demonstrably easier", text)
        self.assertIn("do not describe Streamlit as the primary 3.0 runtime surface", text)
        self.assertIn("Do not add broad LTG contracts, receipts, runbooks, or stage-scope manifests", text)
        self.assertIn("names the current release blocker they directly reduce", text)
        self.assertIn("must not claim an LTG is complete", text)
        self.assertIn("only direct acceptance evidence can support an LTG closeout claim", text)
        self.assertIn("dirty implementation bundle over the round limit", text)
        self.assertIn("read-only split audit instead of staging the bundle", text)
        self.assertIn("stage only the intended files or hunks", text)
        self.assertIn("Passing local contracts, py_compile, or smoke on the whole dirty bundle is not permission", text)
        self.assertIn("Ordinary-entry promotion evidence gate", text)
        self.assertIn("reported as user-usable or moved from audit-pending to user-usable", text)
        self.assertIn("cite first-view evidence that next click, source state, missing evidence", text)
        self.assertIn("appear before engineering audit tables", text)
        self.assertIn("Route existence, packet availability, receipt rows, local task success", text)
        self.assertIn("Settings-only detail, or docs/config wording are not promotion evidence", text)
        self.assertIn("Runtime-mode boundary", text)
        self.assertIn("cache_only", text)
        self.assertIn("manual", text)
        self.assertIn("live_light", text)
        self.assertIn("GET/cache/render/startup/search typing stayed silent", text)
        self.assertIn("Runtime policy row boundary", text)
        self.assertIn("`runtime_mode_policy_rows` still expose `fastapi_startup_rule`", text)
        self.assertIn("`search_typing_rule`", text)
        self.assertIn("`cache_get_rule`", text)
        self.assertIn("`react_render_rule`", text)
        self.assertIn("`ledger_rule`", text)
        self.assertIn("`ordinary_entrance_visibility_rule`", text)
        self.assertIn("`production_evidence_rule`", text)
        self.assertIn("frontend-visible, non-editable, no-writeback, no-secret, and non-production evidence", text)
        self.assertIn("Ordinary task-boundary visibility", text)
        self.assertIn("`任务边界` remains in the user summary before Settings / Developer / Audit details", text)
        self.assertIn("`GET cache` / React render stayed read-only", text)
        self.assertIn("`manual` or `live_light`补证 path still goes through `POST task` / worker / local fallback", text)
        self.assertIn("Ordinary source-state chips", text)
        self.assertIn("`cache`, `Tushare`, `DeepSeek`, `pending`, `degraded`, and `last_successful_cache/result` remain visible", text)
        self.assertIn("read-only UI guidance", text)
        self.assertIn("did not create tasks, call provider/model, write cache/config, or promote production evidence", text)
        self.assertIn("Ordinary next-click rule", text)
        self.assertIn("what the one primary safe next click is", text)
        self.assertIn("disabled/degraded reasons are visible", text)
        self.assertIn("work-creating click still goes through POST task / worker / local fallback", text)
        self.assertIn("task status and no-trade/no-action boundaries", text)
        self.assertIn("Engineering-audit demotion", text)
        self.assertIn("engineering contract tables, receipt rows, runbooks, and LTG audit surfaces", text)
        self.assertIn("must not become the default ordinary-page body", text)
        self.assertIn("Report the demotion verdicts separately", text)
        self.assertIn("ordinary summary appears before engineering detail", text)
        self.assertIn("Settings / Developer / Audit link remains visible", text)
        self.assertIn("current-decision-surface exception reason", text)
        self.assertIn("Priority alignment", text)
        self.assertIn("which current usable-path priority was advanced", text)
        self.assertIn("P0 one-click startup and frontend/backend auto connection", text)
        self.assertIn("P1 confirmed stock-code Tushare-first data chain", text)
        self.assertIn("P2 cache / ledger / packet write", text)
        self.assertIn("P3 interpretable Candidate Radar / Quant Projection / Next Session map", text)
        self.assertIn("P4 ordinary-page audit-noise demotion", text)
        self.assertIn("P5 DeepSeek governed executor", text)
        self.assertIn("P6 return to 14 LTG direct evidence / strict closeout", text)
        self.assertIn("P0-P5 rounds must not be reported as 14 LTG completion", text)
        self.assertIn("P5 must not block Tushare or basic maps", text)
        self.assertIn("P6 is the explicit return point for strict closeout", text)
        self.assertNotIn("name which current migration priority was advanced (`push gate / CI`", text)
        self.assertIn("CI / release evidence boundary", text)
        self.assertIn("Local tests, local push gate, static workflow files", text)
        self.assertIn("not remote CI evidence", text)
        self.assertIn("matching head SHA/commit with current GitHub Actions green status", text)
        self.assertIn("reviewed failure logs", text)
        self.assertIn("explicit user push confirmation before any push", text)
        self.assertIn("Remote CI unknown rule", text)
        self.assertIn("report remote CI status as unknown", text)
        self.assertIn("do not infer green, red, or release readiness", text)
        self.assertIn("old emails, or previous remote runs", text)
        self.assertIn("local_gate_ready_remote_ci_and_allowlist_pending", text)
        self.assertIn("remote_ci_review_required_for_release_gate_complete", text)
        self.assertIn("`local_gate_ready=true` / `ci_mirror_ready=true` are shape evidence only, not release readiness", text)
        self.assertIn("Ordinary-entrance state", text)
        self.assertIn("Daily Command Center", text)
        self.assertIn("Stock Quant Projection", text)
        self.assertIn("next click, Tushare/cache/DeepSeek/pending source", text)
        self.assertIn("missing evidence, research-only not-buy/sell boundary", text)
        self.assertIn("blocked/degraded state, and last successful cache/result", text)
        architecture = (root / "docs" / "command_center_3_architecture.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`股票量化推演 / Stock Quant Projection` 可以读取 `GET /api/bootstrap/status` 作为只读 runtime-mode banner", architecture)
        self.assertIn("把 `cache_only/manual/live_light/live_full` 当前口径放在普通用户摘要里", architecture)
        self.assertIn("这不是 bootstrap launcher", architecture)
        self.assertIn("不创建 `POST /api/bootstrap/live-startup`", architecture)
        self.assertIn("不调用 provider/model，不写配置或 cache，不暴露 token/key", architecture)
        self.assertIn("不能当成 production evidence 或完整 `live_light` 实现", architecture)
        self.assertIn("任何 `configured=true` 只表示 operator intent", architecture)
        self.assertIn("不是 effective external call", architecture)
        self.assertIn("`configured_switch_rule`", architecture)
        self.assertIn("`effective_external_call_rule`", architecture)
        self.assertIn("effective external work 仍需 mode/task gate、ledger、redaction 和 promotion gate", architecture)
        self.assertIn("runtime config 不能证明完整 `live_light` workflow", architecture)
        self.assertIn("Mode-layered live-light evidence factory", architecture)
        self.assertIn("运行模式分层的轻量实时投研证据工厂", architecture)
        self.assertIn("不是完整 `live_light` provider/model executor", architecture)
        self.assertIn("不是 Legacy Bug / UX Audit 直接证据", architecture)
        self.assertIn("不是 production acceptance evidence", architecture)
        self.assertIn("release_gate_readiness_audit.status=local_gate_ready_remote_ci_and_allowlist_pending", architecture)
        self.assertIn("remote_ci_review_required_for_release_gate_complete", architecture)
        self.assertIn("`local_gate_ready=true` / `ci_mirror_ready=true` 不是 release-ready", architecture)
        self.assertIn("retained signal/capability coverage evidence 未完成边界", architecture)
        self.assertIn("不复制 Streamlit 图表 UI 或旧 tab navigation", architecture)
        self.assertIn("retained signal/capability coverage evidence、browser visual QA", architecture)
        echart_maturity_section = architecture.split(
            "`GET /api/next-session/cache` 已输出 ECharts 成熟版只读合同",
            1,
        )[1].split("- React 已加入受控动效清晰度层", 1)[0]
        self.assertNotIn("legacy signal/capability parity", echart_maturity_section)
        self.assertIn("普通入口状态口径必须保持首屏可审计", architecture)
        self.assertIn("one primary safe next click", architecture)
        self.assertIn("source chip（`cache` / `Tushare` / `DeepSeek` / `pending` / `degraded`）", architecture)
        self.assertIn("missing-evidence row", architecture)
        self.assertIn("research-only/no-buy-sell label", architecture)
        self.assertIn("blocked/degraded reason 和 last successful cache/result", architecture)
        self.assertIn("显示 disabled/degraded reason 与 last known cache", architecture)
        self.assertIn("不是让普通用户回到工程 audit table、legacy tab 或 JSON receipt 里寻找答案", architecture)
        self.assertIn("架构层的 provider/model 证据也必须先有 redacted `call_ledger` / `model_ledger` rows", architecture)
        self.assertIn("缺 ledger 的结果只能显示为 local 或 pending", architecture)
        self.assertIn("不能推进 `live_light`、LTG 完成、Streamlit 退场或 production acceptance", architecture)
        self.assertIn("DeepSeek 文本、model summary 或 explanation status 不能满足 missing evidence", architecture)
        self.assertIn("不能成为 next-click action", architecture)
        self.assertIn("不能替代 provider/cache/factor/operation-zone evidence", architecture)
        self.assertIn("只能在 `model_ledger` 状态和 redaction review 下解释已有证据", architecture)
        self.assertIn("普通 UI 与 migration report 只能展示 safe summaries", architecture)
        self.assertIn("不得暴露 raw prompts、raw model output、unredacted provider errors", architecture)
        self.assertIn("白名单字段、`model_ledger` 状态和 redaction review", architecture)
        self.assertIn("不把旧 Streamlit 图表 UI/tab 复制作为验收目标", architecture)
        self.assertIn("不证明 retained signal/capability coverage evidence 或生产替代完成，不代表复制旧 Streamlit 图表 UI", architecture)
        self.assertIn("不证明 retained signal/capability coverage evidence、durable CI evidence 或 production ECharts replacement", architecture)
        next_session_route_section = architecture.split(
            "- `POST /api/next-session/generate` 已从纯 stub",
            1,
        )[1].split("- `POST /api/factor-quant/run-light`", 1)[0]
        self.assertIn(
            "不证明 retained signal/capability coverage evidence 或生产替代完成",
            next_session_route_section,
        )
        self.assertIn(
            "不证明 retained signal/capability coverage evidence、durable CI evidence 或 production ECharts replacement",
            next_session_route_section,
        )
        self.assertNotIn(
            "不证明 legacy signal/capability parity 或生产替代完成",
            next_session_route_section,
        )

        migration_map = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")
        self.assertIn("Release gate 状态口径", migration_map)
        self.assertIn("local_gate_ready_remote_ci_and_allowlist_pending", migration_map)
        self.assertIn("remote_ci_review_required_for_release_gate_complete", migration_map)
        self.assertIn("`local_gate_ready=true` / `ci_mirror_ready=true` 只证明形状可见，不是 release-ready", migration_map)
        self.assertNotIn(
            "不证明 legacy signal/capability parity、durable CI evidence 或 production ECharts replacement",
            next_session_route_section,
        )
        self.assertIn("经 Legacy Bug / UX Audit 判定应保留的能力、信号组和证据链", architecture)
        self.assertIn("不复制 Streamlit 页面 UI、tab navigation、已知 bug 或历史 patchwork", architecture)
        self.assertIn(
            "Streamlit fallback removal、ordinary capability replacement evidence、admin/debug retirement",
            architecture,
        )
        self.assertIn(
            "streamlit_retirement_readiness_receipt` 只选择下一步 ordinary capability replacement evidence review / fallback-retirement review",
            architecture,
        )
        self.assertIn("这不是旧 UI/navigation parity review", architecture)
        self.assertIn(
            "React/Tauri 普通入口更简单、更清晰、更可靠且 fallback-retirement evidence 通过",
            architecture,
        )
        self.assertNotIn("把 Streamlit 页面逐块迁移到 React/ECharts", architecture)
        self.assertNotIn("browser QA、performance trace、Streamlit parity 和 production replacement", architecture)
        self.assertNotIn("不证明 Streamlit parity 或生产替代完成", architecture)
        self.assertNotIn("不证明 Streamlit parity、durable CI evidence", architecture)
        self.assertNotIn(
            "Streamlit fallback removal、replacement parity、admin/debug retirement",
            architecture,
        )
        self.assertNotIn("显式 parity / fallback-retirement review", architecture)

    def test_ltg13_streamlit_fallback_retirement_requires_signal_capability_not_ui_parity(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "command_center_3_long_term_goals.md").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Need legacy signal/capability acceptance before removing any Streamlit fallback",
            text,
        )
        self.assertIn(
            "Preserve retained signal/capability no-feature-loss evidence before removing any legacy fallback",
            text,
        )
        self.assertIn("legacy UI, navigation, and tab-copy parity are not retirement evidence", text)
        self.assertNotIn("Preserve signal parity before removing any legacy fallback", text)
        self.assertNotIn("Need parity acceptance before removing any Streamlit fallback", text)

    def test_ltg10_status_uses_capability_replacement_not_ui_parity_wording(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "server" / "services" / "migration_status_service.py"
        ).read_text(encoding="utf-8")

        self.assertIn("React/Tauri ordinary capability replacement evidence", source)
        self.assertIn("Candidate Radar signal/capability replacement evidence", source)
        self.assertIn("future explicit ordinary capability replacement", source)
        self.assertIn("ordinary capability replacement evidence", source)
        self.assertIn(
            '"LTG-10": [\n        "React/Tauri ordinary capability replacement evidence"',
            source,
        )
        self.assertNotIn(
            "Run explicit replacement parity and Streamlit fallback retirement reviews",
            source,
        )
        self.assertNotIn('"LTG-10": ["React/Tauri workflow parity"', source)
        self.assertNotIn("delete app.py before replacement parity", source)

    def test_ltg13_status_uses_signal_capability_replacement_not_provider_parity(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "server" / "services" / "migration_status_service.py"
        ).read_text(encoding="utf-8")

        self.assertIn("real provider-backed radar signal/capability replacement execution", source)
        self.assertIn("provider-backed radar signal/capability replacement execution", source)
        self.assertIn(
            "retained legacy signal/capability no-feature-loss coverage evidence",
            source,
        )
        self.assertIn("legacy signal/capability acceptance receipt", source)
        self.assertIn("provider-backed radar signal/capability dry-run ticket", source)
        self.assertIn("provider-backed radar signal/capability call ledger", source)
        self.assertNotIn('"LTG-13": ["provider parity execution"', source)
        self.assertNotIn("real provider-backed radar parity execution", source)
        self.assertNotIn("legacy no-feature-loss parity", source)
        self.assertNotIn("legacy parity receipt", source)
        self.assertNotIn("provider parity dry-run ticket", source)
        self.assertNotIn("provider parity call ledger", source)

    def test_candidate_radar_contract_uses_coverage_ui_labels_not_parity_copy(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "scripts" / "candidate_radar_contract.py"
        ).read_text(encoding="utf-8")

        self.assertIn("雷达 provider coverage dry-run", source)
        self.assertIn("旧雷达 coverage 验收收据", source)
        self.assertIn("provider-backed radar signal/capability call ledger", source)
        self.assertIn("provider-backed radar signal/capability acceptance", source)
        self.assertNotIn('"雷达 provider parity dry-run" in candidate_frontend', source)
        self.assertNotIn('"旧雷达 parity 验收收据" in candidate_frontend', source)
        self.assertNotIn("provider-backed parity acceptance", source)
        self.assertNotIn("provider-backed parity call ledger", source)

    def test_push_gate_guard_covers_commit_checkpoint_surfaces(self):
        root = Path(__file__).resolve().parents[1]
        push_gate = (root / "scripts" / "push_gate_3_0.sh").read_text(encoding="utf-8")
        ci_workflow = (
            root / ".github" / "workflows" / "command-center-3-push-gate.yml"
        ).read_text(encoding="utf-8")
        legacy_service = (root / "server" / "services" / "legacy_service.py").read_text(
            encoding="utf-8"
        )
        legacy_page = (root / "desktop" / "src" / "routes" / "LegacyTools.tsx").read_text(
            encoding="utf-8"
        )
        migration_page = (root / "desktop" / "src" / "routes" / "MigrationStatus.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("Migration principle docs guard", push_gate)
        self.assertIn(
            "Migration principle docs guard: configured_switch_rule / effective_external_call_rule",
            push_gate,
        )
        self.assertIn("tests.test_command_center_migration_principles", push_gate)
        self.assertIn("scripts/push_gate_3_0.sh mirrors", ci_workflow)
        self.assertIn("-m unittest tests.test_command_center_migration_principles", ci_workflow)
        self.assertIn("scripts/bootstrap_runtime_contract.py", ci_workflow)
        self.assertIn("runtime_mode_policy_rows config boundary fields", ci_workflow)
        self.assertIn("configured_switch_rule / effective_external_call_rule", ci_workflow)
        self.assertIn("local_push_gate_receipt_artifact_policy_scan", ci_workflow)
        self.assertIn("LOCAL_PUSH_GATE_RECEIPT_PATH must be ignored", ci_workflow)
        self.assertIn("scripts/push_gate_3_0.sh", ci_workflow)
        self.assertIn("Bootstrap runtime contract", push_gate)
        self.assertIn("scripts/bootstrap_runtime_contract.py", push_gate)
        self.assertIn("local_gate_pass_is_not_remote_ci: true", push_gate)
        self.assertIn("remote_actions_status_known: false", push_gate)
        self.assertIn("latest_remote_run_verified_green: false", push_gate)
        self.assertIn("Local gate pass is not remote CI evidence", push_gate)
        self.assertIn("remote_ci_status_note", push_gate)
        self.assertIn("inspect matching remote Actions run before release", push_gate)

        for question_key in (
            "what_user_capability_was_preserved",
            "what_legacy_ux_problem_was_removed",
            "what_legacy_bug_or_patchwork_path_was_not_migrated",
            "what_became_simpler_for_nontechnical_user",
            "which_real_blocker_was_reduced",
        ):
            self.assertIn(question_key, legacy_service)

        self.assertIn("commit_questions", legacy_service)
        self.assertIn("legacy_audit_first_round_intake", legacy_service)
        self.assertIn("legacy_audit_first_round_intake_rows", legacy_service)
        self.assertIn("legacy_audit_first_round_intake_visible_admin_debug_only", legacy_service)
        self.assertIn("migrationCommitQuestionRows", legacy_page)
        self.assertIn("legacyAuditFirstRoundIntakeRows", legacy_page)
        self.assertIn("Legacy first-round intake", legacy_page)
        self.assertIn("admin/debug only，不升级 KEEP", legacy_page)
        self.assertIn("不让旧模块进入普通入口", legacy_page)
        self.assertIn("迁移 commit checkpoint", legacy_page)
        self.assertIn("required_for_future_migration_commit", legacy_page)
        self.assertIn("不是 production evidence", legacy_page)
        self.assertLess(
            legacy_page.index("普通入口 UX 审计"),
            legacy_page.index("迁移 commit checkpoint"),
        )
        self.assertLess(
            legacy_page.index("迁移 commit checkpoint"),
            legacy_page.index("Legacy first-round intake"),
        )
        self.assertLess(
            legacy_page.index("Legacy first-round intake"),
            legacy_page.index("Legacy 模块 UX/bug 分类"),
        )

        self.assertIn("legacyAuditFirstRoundIntake", migration_page)
        self.assertIn("legacy_audit_first_round_intake_rows", migration_page)
        self.assertIn("Legacy Bug / UX Audit first-round intake", migration_page)
        self.assertIn("第一轮不能升级 KEEP", migration_page)
        self.assertIn("不能让旧模块进入普通用户入口", migration_page)
        self.assertIn("KEEP promotion", migration_page)
        self.assertIn("ordinary entry", migration_page)
        self.assertIn("not_production_evidence", migration_page)
        self.assertLess(
            migration_page.index("14 LTG acceptance runway"),
            migration_page.index("Legacy Bug / UX Audit first-round intake"),
        )
        self.assertLess(
            migration_page.index("Legacy Bug / UX Audit first-round intake"),
            migration_page.index("LTG next acceptance action queue"),
        )


if __name__ == "__main__":
    unittest.main()
