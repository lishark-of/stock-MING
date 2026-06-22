import unittest
from pathlib import Path

import config


class RuntimeConfigAllowlistTests(unittest.TestCase):
    def test_runtime_config_names_are_single_safe_allowlist(self):
        expected = (
            "COMMAND_CENTER_BOOTSTRAP_MODE",
            "COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN",
            "COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN",
            "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART",
            "COMMAND_CENTER_LIVE_STARTUP_AUTOSTART",
            "COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE",
            "COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE",
            "COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT",
            "COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT",
            "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT",
            "COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS",
            "COMMAND_CENTER_LIVE_DEEPSEEK_MODEL",
            "COMMAND_CENTER_LIVE_ALLOW_FULL_POOL",
        )

        self.assertEqual(config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES, expected)
        self.assertEqual(len(config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES), 13)
        self.assertEqual(len(set(config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES)), 13)
        self.assertLessEqual(set(config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES), config.CONFIG_NAMES)

        for name in config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES:
            self.assertNotIn("TOKEN", name)
            self.assertNotIn("API_KEY", name)
            self.assertNotIn("PASSWORD", name)
            self.assertNotIn("SECRET", name)

    def test_runtime_mode_policies_keep_cache_render_read_only(self):
        policies = config.get_command_center_runtime_mode_policies()
        rows = {row["mode"]: row for row in policies}

        self.assertEqual(set(rows), {"cache_only", "manual", "live_light", "live_full"})
        self.assertEqual(config.COMMAND_CENTER_DEFAULT_RUNTIME_MODE, "cache_only")
        self.assertTrue(rows["cache_only"]["default"])
        self.assertFalse(rows["manual"]["default"])
        self.assertFalse(rows["live_light"]["default"])
        self.assertFalse(rows["live_full"]["default"])

        for row in rows.values():
            self.assertEqual(row["cache_get_rule"], "read_only_no_provider_model_worker_or_trade")
            self.assertEqual(row["react_render_rule"], "read_only_no_provider_model_worker_or_trade")
            self.assertEqual(
                row["ordinary_entrance_visibility_rule"],
                "show_task_boundary_in_user_summary_before_settings_developer_audit",
            )
            self.assertEqual(
                row["ordinary_mode_banner_rule"],
                "read_only_status_banner_not_task_launcher_or_config_writer",
            )
            self.assertEqual(
                row["configured_switch_rule"],
                "configured_true_is_operator_intent_not_effective_external_call",
            )
            self.assertEqual(
                row["effective_external_call_rule"],
                "effective_external_call_requires_mode_task_gate_ledgers_redaction_and_promotion",
            )
            self.assertEqual(row["production_evidence_rule"], "config_policy_row_is_not_production_evidence")

        self.assertEqual(rows["cache_only"]["external_call_rule"], "none")
        self.assertEqual(rows["manual"]["external_call_rule"], "explicit_post_task_only")
        self.assertEqual(rows["live_light"]["task_creation_rule"], "after_cache_render_rate_limited_local_task_only")
        self.assertEqual(rows["live_full"]["startup_rule"], "reserved_no_startup_task")

    def test_live_light_bootstrap_task_contract_matches_mode_policy_rows(self):
        policies = config.get_command_center_runtime_mode_policies()
        rows = {row["mode"]: row for row in policies}
        contract = config.get_command_center_live_light_bootstrap_task_contract()

        self.assertEqual(contract["mode"], "live_light")
        self.assertEqual(contract["task_route"], "POST /api/bootstrap/live-startup")
        self.assertEqual(contract["trigger_surface"], "after_initial_cache_render_only")
        self.assertEqual(
            rows["live_light"]["task_creation_rule"],
            "after_cache_render_rate_limited_local_task_only",
        )
        self.assertEqual(
            contract["task_creation_rule"],
            "create_or_reuse_one_rate_limited_local_task_after_cache_render",
        )
        self.assertEqual(
            contract["queue_budget_rule"],
            "one_active_or_recent_task_per_session_and_rate_window",
        )
        self.assertEqual(contract["cache_first_rule"], "render_existing_cache_before_task_creation")
        self.assertEqual(
            rows["cache_only"]["task_creation_rule"],
            "no_task_from_startup_render_get_cache_or_search",
        )
        self.assertEqual(contract["cache_only_rule"], "cache_only_never_creates_bootstrap_task")
        self.assertEqual(rows["manual"]["task_creation_rule"], "button_or_explicit_payload_only")
        self.assertEqual(contract["manual_mode_rule"], "manual_mode_requires_explicit_button_or_post_task")
        self.assertEqual(rows["live_full"]["task_creation_rule"], "disabled_until_separate_authorization")
        self.assertEqual(contract["live_full_rule"], "live_full_reserved_disabled_no_bootstrap_task")
        self.assertEqual(contract["search_typing_rule"], "search_typing_never_creates_bootstrap_task")
        self.assertEqual(
            contract["provider_model_execution_rule"],
            "future_provider_model_execution_requires_execution_request_and_ledgers",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "bootstrap_task_contract_is_not_execution_or_production_evidence",
        )
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["provider_execution_implemented"])
        self.assertFalse(contract["model_execution_implemented"])
        self.assertFalse(contract["worker_dispatch_implemented"])
        self.assertFalse(contract["contains_secret"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertTrue(contract["does_not_modify_strategy_action"])

    def test_runtime_mode_policy_row_docs_carry_configured_switch_boundary(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "command_center_3_long_term_goals.md").read_text(
            encoding="utf-8"
        )
        architecture_text = (root / "docs" / "command_center_3_architecture.md").read_text(
            encoding="utf-8"
        )
        app_plan_text = (root / "docs" / "app_migration_plan.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("`configured_switch_rule`", text)
        self.assertIn("`effective_external_call_rule`", text)
        self.assertIn("`configured=true` is operator intent", text)
        self.assertIn("rather than an effective external call", text)
        self.assertIn("mode/task gate plus ledgers/redaction/promotion", text)
        self.assertIn("Current docs/config cycle acceptance is deliberately narrower than full `live_light`", text)
        self.assertIn("target-stage vocabulary", text)
        self.assertIn("non-production-evidence wording", text)
        self.assertIn("Runtime mode layering replaces the old flat startup-external-call ban", text)
        self.assertIn("| `cache_only` | smoke, CI, quick offline review |", text)
        self.assertIn("| `manual` | operator-controlled research acceptance |", text)
        self.assertIn("| `live_light` | local daily light research client |", text)
        self.assertIn("| `live_full` | future full-pool/deep-scan mode |", text)
        self.assertIn("This cycle defines vocabulary/config/task boundary only", text)
        self.assertIn("provider/model execution, frontend autostart wiring, worker dispatch", text)
        self.assertIn("cache-write promotion, and production acceptance remain excluded", text)
        self.assertIn("Must not be enabled by config visibility, task skeletons, receipts, matrices", text)
        self.assertIn("`evidence_factory_name`", text)
        self.assertIn("`evidence_factory_rule`", text)
        self.assertIn("runtime_vocabulary_safe_config_rows_and_post_task_boundary_only_not_execution", text)
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
        self.assertIn("`runtime_mode_config_current_acceptance_scope`", architecture_text)
        self.assertIn("docs_config_contract_evidence_only_not_live_light_implementation", architecture_text)
        self.assertIn("status/operator 漂移防线", architecture_text)
        self.assertIn("不能作为 production evidence", architecture_text)
        self.assertIn("`runtime_mode_config_current_acceptance_scope`", app_plan_text)
        self.assertIn("runtime_mode_vocabulary_config_rows_and_contract_tests_only", app_plan_text)
        self.assertIn("docs_config_contract_evidence_only_not_live_light_implementation", app_plan_text)
        self.assertIn("frontend_autostart_wiring", app_plan_text)
        self.assertIn("provider_model_executor", app_plan_text)
        self.assertIn("worker_dispatch", app_plan_text)
        self.assertIn("cache_write_promotion", app_plan_text)
        self.assertIn("production_acceptance", app_plan_text)
        self.assertIn("App planning must not turn those rows into frontend autostart wiring", app_plan_text)
        self.assertIn("production acceptance evidence", app_plan_text)

    def test_runtime_mode_config_contract_is_not_execution_evidence(self):
        contract = config.get_command_center_runtime_mode_config_contract()

        self.assertEqual(contract["config_key"], "COMMAND_CENTER_BOOTSTRAP_MODE")
        self.assertEqual(contract["default_mode"], "cache_only")
        self.assertEqual(contract["allowed_modes"], ["cache_only", "manual", "live_light", "live_full"])
        self.assertEqual(
            contract["evidence_factory_name"],
            "Mode-layered live-light evidence factory / 运行模式分层的轻量实时投研证据工厂",
        )
        self.assertEqual(
            contract["evidence_factory_rule"],
            "runtime_vocabulary_safe_config_rows_and_post_task_boundary_only_not_execution",
        )
        self.assertEqual(
            contract["current_acceptance_scope"],
            "runtime_mode_vocabulary_config_rows_and_contract_tests_only",
        )
        self.assertEqual(
            contract["current_acceptance_rule"],
            "docs_config_contract_evidence_only_not_live_light_implementation",
        )
        self.assertEqual(
            contract["current_acceptance_excludes"],
            [
                "frontend_autostart_wiring",
                "provider_model_executor",
                "worker_dispatch",
                "cache_write_promotion",
                "production_acceptance",
            ],
        )
        self.assertEqual(contract["invalid_value_rule"], "redact_invalid_value_and_fallback_to_cache_only")
        self.assertEqual(contract["live_full_rule"], "reserved_disabled_requires_separate_authorization")
        self.assertEqual(
            contract["configured_switch_rule"],
            "configured_true_is_operator_intent_not_effective_external_call",
        )
        self.assertEqual(
            contract["effective_external_call_rule"],
            "effective_external_call_requires_mode_task_gate_ledgers_redaction_and_promotion",
        )
        self.assertEqual(
            contract["live_light_completion_rule"],
            "runtime_config_does_not_prove_full_live_light_workflow",
        )
        self.assertEqual(contract["production_evidence_rule"], "runtime_config_contract_is_not_production_evidence")
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["contains_secret"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertTrue(contract["does_not_modify_strategy_action"])

    def test_runtime_example_documents_default_off_mode_layering(self):
        example = Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.example.toml"
        text = example.read_text(encoding="utf-8")

        for name in config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES:
            self.assertIn(f"{name} =", text)

        self.assertIn('COMMAND_CENTER_BOOTSTRAP_MODE = "cache_only"', text)
        self.assertIn("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART = false", text)
        self.assertIn('COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE = "plan_only"', text)
        self.assertIn('COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE = "provider_factor_next_model"', text)
        self.assertIn("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL = false", text)
        self.assertIn("cache_only is the safe default", text)
        self.assertIn("live_light must remain opt-in and task/ledger governed", text)
        self.assertIn("manual: explicit button or POST task only", text)
        self.assertIn("Configured live switches remain display-only in manual", text)
        self.assertIn("no page-open", text)
        self.assertIn("startup, or searched-symbol autostart is effective without explicit POST", text)
        self.assertIn("cache_only has highest priority", text)
        self.assertIn("configured live switches may be shown safely", text)
        self.assertIn("effective automation, task creation, provider/model calls, and live profiles", text)
        self.assertIn("must stay false/plan_only/bootstrap_only in cache_only", text)
        self.assertIn("live_full: reserved and disabled until separate authorization", text)
        self.assertIn("config rows are operator guidance, not production evidence or frontend secrets", text)
        self.assertIn("Server config remains the source of truth", text)
        self.assertIn("Status/UI surfaces may show only", text)
        self.assertIn("safe defaults and redacted config summaries", text)
        self.assertIn("invalid runtime mode values must", text)
        self.assertIn("fall back to cache_only as [invalid_redacted] with no frontend edit/writeback", text)
        self.assertIn("Credential presence may be shown only as booleans or safe labels", text)
        self.assertIn("Raw values", text)
        self.assertIn("env key names, token/key text, hashes, prompts, and provider errors", text)
        self.assertIn("out of frontend state, logs, packets, cache, receipts, and checkpoints", text)
        self.assertIn("Tushare light planning may name trade_cal when needed, daily, daily_basic", text)
        self.assertIn("and moneyflow only as task-scoped target interfaces", text)
        self.assertIn("empty or permission-denied", text)
        self.assertIn("results stay pending/degraded until redacted call_ledger evidence proves them", text)
        self.assertIn("A configured true value is operator intent only", text)
        self.assertIn("Runtime config never authorizes real trading", text)
        self.assertIn("auto orders", text)
        self.assertIn("buy/sell", text)
        self.assertIn("broker calls", text)
        self.assertIn("strategy action mutation in any mode", text)
        self.assertIn("Current acceptance markers are emitted by GET /api/bootstrap/status, not set here", text)
        self.assertIn("runtime_mode_config_current_acceptance_scope", text)
        self.assertIn("runtime_mode_vocabulary_config_rows_and_contract_tests_only", text)
        self.assertIn("runtime_mode_config_current_acceptance_rule", text)
        self.assertIn("docs_config_contract_evidence_only_not_live_light_implementation", text)
        self.assertIn("runtime_mode_config_current_acceptance_excludes", text)
        self.assertIn("frontend_autostart_wiring, provider_model_executor, worker_dispatch", text)
        self.assertIn("cache_write_promotion, production_acceptance", text)
        self.assertIn("They are checkpoint drift guards only, not private config keys", text)
        self.assertIn("provider/model execution, worker dispatch, cache-write", text)
        self.assertIn("promotion, or production acceptance evidence", text)
        self.assertIn("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE values plan_only", text)
        self.assertIn("light_provider, and light_provider_model are future profile labels only", text)
        self.assertIn(
            "they are not executors, release switches, provider/model proof, or production evidence",
            text,
        )
        self.assertIn("Provider/model and frontend enablement are default-off release switches", text)
        self.assertIn("configured true still stays effective false until execution-request", text)
        self.assertIn("ledgers, browser evidence, redaction, rollback, and promotion gates pass", text)
        self.assertIn("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE names the target live_light chain only", text)
        self.assertIn('use "bootstrap_only" for contract-only local inspections with no stage bundle', text)
        self.assertIn("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART is only a local task-create/reuse guard", text)
        self.assertIn("even true is not provider/model execution authorization", text)
        self.assertIn("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART is only for a confirmed symbol", text)
        self.assertIn("never search typing, render, startup, or GET cache/status", text)
        self.assertIn("Confirmed submit must normalize one A-share symbol", text)
        self.assertIn("drop raw query text", text)
        self.assertIn("raw search text must not enter logs, cache, frontend packets, or task receipts", text)
        self.assertIn("Symbol limit, rate limit, and DeepSeek model label are budget/display settings only", text)
        self.assertIn("they do not authorize provider/model calls, expose credentials, or bypass task ledgers", text)
        self.assertIn("Symbol/rate budgets cap local task scope", text)
        self.assertIn("require reuse/skip behavior on", text)
        self.assertIn("rate-window hits", text)
        self.assertIn("must not create an unbounded task queue", text)
        self.assertIn("beyond current target, searched symbol, holdings, watchlist, or explicit symbols", text)
        self.assertIn("DeepSeek remains explanation-only in live_light planning", text)
        self.assertIn("not a data source", text)
        self.assertIn("never allowed to overwrite prices, holdings, factors, operation_zones", text)
        self.assertIn("or strategy action", text)
        self.assertIn("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL remains a reserved intent flag", text)
        self.assertIn("not enable full-pool or deep-scan work without separate live_full", text)
        self.assertIn("authorization, explicit worker task, ledgers, and promotion evidence", text)
        self.assertIn("Optional local live_light opt-in recipe for a private config copy only", text)
        self.assertIn("Mode-layered live-light evidence factory vocabulary", text)
        self.assertIn("research-client experiments", text)
        self.assertIn("not a production executor or a committed default", text)
        self.assertIn("Keep this recipe commented in the example file", text)
        self.assertIn("cache_only remains the", text)
        self.assertIn("committed default", text)
        self.assertIn("Do not uncomment the bundle here", text)
        self.assertIn("A local operator may copy these values deliberately", text)
        self.assertIn("one bounded local POST bootstrap task after", text)
        self.assertIn("cache render", text)
        self.assertIn("provider/model execution still requires execution-request", text)
        self.assertIn("call/model ledgers, redaction, browser nonblocking evidence, rollback, and", text)
        self.assertIn("promotion gates", text)
        self.assertIn("This recipe does not prove full live_light implementation", text)
        self.assertIn("frontend wiring", text)
        self.assertIn("provider execution", text)
        self.assertIn("DeepSeek execution", text)
        self.assertIn("cache writes", text)
        self.assertIn("worker dispatch", text)
        self.assertIn("remote", text)
        self.assertIn("release readiness", text)
        self.assertIn("production acceptance", text)
        self.assertIn('# COMMAND_CENTER_BOOTSTRAP_MODE = "live_light"', text)
        self.assertIn("# COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN = true", text)
        self.assertIn("# COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN = true", text)
        self.assertIn("# COMMAND_CENTER_LIVE_STARTUP_AUTOSTART = true", text)
        self.assertIn("# COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART = false", text)
        self.assertIn('# COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE = "light_provider_model"', text)
        self.assertIn('# COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE = "provider_factor_next_model"', text)
        self.assertIn("# COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT = false", text)
        self.assertIn("# COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT = false", text)
        self.assertIn("# COMMAND_CENTER_LIVE_ALLOW_FULL_POOL = false", text)
        self.assertLess(
            text.index('COMMAND_CENTER_BOOTSTRAP_MODE = "cache_only"'),
            text.index('# COMMAND_CENTER_BOOTSTRAP_MODE = "live_light"'),
        )
        self.assertIn(
            "Effective external work still requires mode/task gates, ledgers, redaction, and promotion",
            text,
        )
        self.assertIn(
            "Runtime config does not prove the full live_light workflow has been implemented",
            text,
        )

    def test_desktop_launcher_does_not_override_runtime_config_defaults(self):
        launcher = Path(__file__).resolve().parents[1] / "scripts" / "start_command_center_3.command"
        text = launcher.read_text(encoding="utf-8")

        self.assertIn("server config controls runtime mode", text)
        self.assertIn("cache_only remains the safe default unless explicitly configured", text)
        self.assertIn("does not set live_light defaults", text)
        self.assertIn("no Tushare, DeepSeek, GitHub, or trading call", text)
        self.assertIn("runtime_mode_config_current_acceptance_* markers are status/checkpoint drift guards", text)
        self.assertIn("not launcher config or live_light enablement", text)
        self.assertNotIn("live_light startup is enabled for desktop use", text)
        self.assertNotIn("STOCK_MING_DESKTOP_LIVE_STARTUP_EXECUTION", text)
        self.assertNotIn(":-live_light", text)
        self.assertNotIn(":-true", text)
        self.assertNotIn(":-light_provider_model", text)
        self.assertNotIn(":-provider_factor_next_model", text)

        for name in config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES:
            self.assertNotIn(f"export {name}", text)


if __name__ == "__main__":
    unittest.main()
