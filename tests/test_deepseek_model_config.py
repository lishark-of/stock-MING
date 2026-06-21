import ast
import os
import re
import unittest
from pathlib import Path

import command_center_next_session_projection as next_session_projection
import command_center_projection as projection
import config
from server.services import model_strategy_service


class DeepSeekModelConfigTests(unittest.TestCase):
    def setUp(self):
        self._original_env = {
            key: os.environ.get(key)
            for key in (
                "DEEPSEEK_DEFAULT_MODEL",
                "DEEPSEEK_EXPLAIN_MODEL",
                "DEEPSEEK_FAST_MODEL",
                "DEEPSEEK_FACTOR_EXPLAIN_MODE",
                "DEEPSEEK_AUTO_EXPLAIN_ENABLED",
                "COMMAND_CENTER_BOOTSTRAP_MODE",
            )
        }
        self._original_loader = config._load_local_streamlit_secrets
        self._original_streamlit_secret = config._get_streamlit_secret
        config._load_local_streamlit_secrets = lambda: {}
        config._get_streamlit_secret = lambda name, default=None: default
        for key in self._original_env:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        config._load_local_streamlit_secrets = self._original_loader
        config._get_streamlit_secret = self._original_streamlit_secret

    def test_default_strategy_uses_pro_for_explain_and_flash_for_fast(self):
        self.assertEqual(config.get_deepseek_model("default"), "deepseek-v4-pro")
        self.assertEqual(config.get_deepseek_model("explain"), "deepseek-v4-pro")
        self.assertEqual(config.get_deepseek_model("projection"), "deepseek-v4-pro")
        self.assertEqual(config.get_deepseek_model("fast"), "deepseek-v4-flash")
        self.assertEqual(config.get_deepseek_model("healthcheck"), "deepseek-v4-flash")

        strategy = config.get_deepseek_model_strategy()

        self.assertEqual(strategy["explain"], "deepseek-v4-pro")
        self.assertEqual(strategy["projection"], "deepseek-v4-pro")
        self.assertEqual(strategy["factor_explain"], "deepseek-v4-pro")
        self.assertEqual(strategy["fast"], "deepseek-v4-flash")
        self.assertEqual(strategy["healthcheck"], "deepseek-v4-flash")
        self.assertEqual(strategy["feeder"], "deepseek-v4-flash")
        self.assertFalse(strategy["contains_secret"])

    def test_env_overrides_model_strategy_without_hardcoded_callsite_names(self):
        os.environ["DEEPSEEK_DEFAULT_MODEL"] = "custom-default"
        os.environ["DEEPSEEK_EXPLAIN_MODEL"] = "custom-explain"
        os.environ["DEEPSEEK_FAST_MODEL"] = "custom-fast"

        self.assertEqual(config.get_deepseek_model("default"), "custom-default")
        self.assertEqual(config.get_deepseek_model("explain"), "custom-explain")
        self.assertEqual(config.get_deepseek_model("projection"), "custom-explain")
        self.assertEqual(config.get_deepseek_model("feeder"), "custom-fast")
        self.assertEqual(config.get_deepseek_model("healthcheck"), "custom-fast")

    def test_streamlit_secret_example_documents_model_strategy_keys(self):
        example = Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.example.toml"
        text = example.read_text(encoding="utf-8")

        self.assertIn('DEEPSEEK_EXPLAIN_MODEL = "deepseek-v4-pro"', text)
        self.assertIn('DEEPSEEK_FACTOR_EXPLAIN_MODE = "manual_only"', text)
        self.assertIn("DEEPSEEK_AUTO_EXPLAIN_ENABLED = false", text)
        self.assertIn('DEEPSEEK_FAST_MODEL = "deepseek-v4-flash"', text)
        self.assertIn('DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-pro"', text)

    def test_streamlit_secret_example_documents_runtime_mode_config_keys(self):
        example = Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.example.toml"
        text = example.read_text(encoding="utf-8")

        for key in config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES:
            self.assertIn(f"{key} =", text)

        self.assertIn('COMMAND_CENTER_BOOTSTRAP_MODE = "cache_only"', text)
        self.assertIn("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART = false", text)
        self.assertIn('COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE = "plan_only"', text)
        self.assertIn(
            'COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE = "provider_factor_next_model"',
            text,
        )
        self.assertIn("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT = 20", text)
        self.assertIn("COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS = 600", text)
        self.assertIn('COMMAND_CENTER_LIVE_DEEPSEEK_MODEL = "deepseek-v4-pro"', text)
        self.assertIn("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL = false", text)
        self.assertIn("cache_only is the safe default", text)
        self.assertIn("live_light must remain opt-in and task/ledger governed", text)
        self.assertIn("cache_only: smoke/CI/quick view, no external calls or task creation", text)
        self.assertIn("manual: explicit button or POST task only", text)
        self.assertIn("live_light: bounded background POST task after cache render, ledger required", text)
        self.assertIn("live_full: reserved and disabled until separate authorization", text)
        self.assertIn("Tushare/DeepSeek source switches remain ineffective outside live_light", text)
        self.assertIn("not production evidence or frontend secrets", text)
        self.assertIn("Live-light research scope / provider-model enablement are stage vocabulary only", text)
        self.assertIn("they do not create tasks, call provider/model, write cache, or prove production", text)

    def test_factor_explain_mode_defaults_to_manual_only_and_validates_values(self):
        self.assertEqual(config.get_deepseek_factor_explain_mode(), "manual_only")
        self.assertFalse(config.get_deepseek_auto_explain_enabled())

        os.environ["DEEPSEEK_FACTOR_EXPLAIN_MODE"] = "auto_after_task"
        os.environ["DEEPSEEK_AUTO_EXPLAIN_ENABLED"] = "true"
        self.assertEqual(config.get_deepseek_factor_explain_mode(), "auto_after_task")
        self.assertTrue(config.get_deepseek_auto_explain_enabled())

        os.environ["DEEPSEEK_FACTOR_EXPLAIN_MODE"] = "surprise_mode"
        os.environ["DEEPSEEK_AUTO_EXPLAIN_ENABLED"] = "0"
        self.assertEqual(config.get_deepseek_factor_explain_mode(), "manual_only")
        self.assertFalse(config.get_deepseek_auto_explain_enabled())

    def test_command_center_runtime_mode_policies_define_layered_external_rules(self):
        rows = config.get_command_center_runtime_mode_policies()
        by_mode = {row["mode"]: row for row in rows}

        self.assertEqual([row["mode"] for row in rows], list(config.COMMAND_CENTER_RUNTIME_MODES))
        self.assertEqual(
            [row["mode"] for row in rows if row["default"]],
            [config.COMMAND_CENTER_DEFAULT_RUNTIME_MODE],
        )
        self.assertEqual(by_mode["cache_only"]["external_call_rule"], "none")
        self.assertEqual(by_mode["cache_only"]["startup_rule"], "read_existing_cache_only")
        self.assertEqual(
            by_mode["cache_only"]["page_open_rule"],
            "no_task_creation_read_existing_cache_only",
        )
        self.assertEqual(
            by_mode["cache_only"]["search_submit_rule"],
            "no_task_creation_show_existing_cache_only",
        )
        self.assertEqual(by_mode["manual"]["external_call_rule"], "explicit_post_task_only")
        self.assertEqual(by_mode["manual"]["startup_rule"], "page_open_and_search_do_not_autostart")
        self.assertEqual(
            by_mode["manual"]["page_open_rule"],
            "no_page_open_task_explicit_button_or_post_task_only",
        )
        self.assertEqual(
            by_mode["manual"]["search_submit_rule"],
            "explicit_confirmed_symbol_button_or_post_task_only",
        )
        self.assertEqual(
            by_mode["live_light"]["external_call_rule"],
            "auditable_background_post_task_worker_or_local_fallback",
        )
        self.assertEqual(
            by_mode["live_light"]["task_creation_rule"],
            "after_cache_render_rate_limited_local_task_only",
        )
        self.assertEqual(
            by_mode["live_light"]["page_open_rule"],
            "after_cache_render_may_create_one_bounded_local_post_task_when_effective",
        )
        self.assertEqual(
            by_mode["live_light"]["search_submit_rule"],
            "confirmed_symbol_submit_may_create_or_reuse_local_quant_projection_task_when_effective",
        )
        self.assertEqual(by_mode["live_full"]["external_call_rule"], "reserved_future_authorization")
        self.assertEqual(by_mode["live_full"]["startup_rule"], "reserved_no_startup_task")
        self.assertEqual(by_mode["live_full"]["page_open_rule"], "reserved_no_page_open_task")
        self.assertEqual(by_mode["live_full"]["search_submit_rule"], "reserved_no_search_submit_task")
        for row in rows:
            self.assertEqual(
                row["cache_get_rule"],
                "read_only_no_provider_model_worker_or_trade",
            )
            self.assertEqual(
                row["react_render_rule"],
                "read_only_no_provider_model_worker_or_trade",
            )
            self.assertEqual(
                row["ordinary_entrance_visibility_rule"],
                "show_task_boundary_in_user_summary_before_settings_developer_audit",
            )
            self.assertEqual(
                row["ordinary_mode_banner_rule"],
                "read_only_status_banner_not_task_launcher_or_config_writer",
            )
            self.assertEqual(
                row["production_evidence_rule"],
                "config_policy_row_is_not_production_evidence",
            )
        self.assertEqual(
            by_mode["cache_only"]["ledger_rule"],
            "no_external_call_no_ledger_required",
        )
        self.assertEqual(
            by_mode["manual"]["ledger_rule"],
            "call_ledger_and_model_ledger_required_for_external_work",
        )
        self.assertEqual(
            by_mode["live_light"]["ledger_rule"],
            "call_ledger_and_model_ledger_required_for_external_work",
        )
        self.assertEqual(
            by_mode["live_full"]["ledger_rule"],
            "reserved_future_authorization_required",
        )

    def test_command_center_runtime_mode_state_defaults_and_redacts_invalid_values(self):
        state = config.get_command_center_runtime_mode_state()

        self.assertEqual(state["mode"], "cache_only")
        self.assertEqual(state["configured_value_safe"], "cache_only")
        self.assertTrue(state["valid"])
        self.assertEqual(state["source"], "default")
        self.assertFalse(state["redacted_invalid"])
        self.assertEqual(state["allowed_modes"], list(config.COMMAND_CENTER_RUNTIME_MODES))
        self.assertFalse(state["contains_secret"])

        os.environ["COMMAND_CENTER_BOOTSTRAP_MODE"] = "manual"
        manual_state = config.get_command_center_runtime_mode_state()

        self.assertEqual(manual_state["mode"], "manual")
        self.assertEqual(manual_state["configured_value_safe"], "manual")
        self.assertTrue(manual_state["valid"])
        self.assertEqual(manual_state["source"], "configured")

        os.environ["COMMAND_CENTER_BOOTSTRAP_MODE"] = "token=SHOULD_NOT_LEAK"
        invalid_state = config.get_command_center_runtime_mode_state()

        self.assertEqual(invalid_state["mode"], "cache_only")
        self.assertEqual(invalid_state["configured_value_safe"], "[invalid_redacted]")
        self.assertFalse(invalid_state["valid"])
        self.assertEqual(invalid_state["source"], "configured_invalid_defaulted")
        self.assertTrue(invalid_state["redacted_invalid"])
        self.assertNotIn("SHOULD_NOT_LEAK", str(invalid_state))
        self.assertFalse(invalid_state["contains_secret"])

    def test_command_center_runtime_mode_config_contract_is_read_only_and_not_evidence(self):
        contract = config.get_command_center_runtime_mode_config_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_runtime_mode_config_contract.v1",
        )
        self.assertEqual(contract["config_key"], "COMMAND_CENTER_BOOTSTRAP_MODE")
        self.assertEqual(contract["default_mode"], "cache_only")
        self.assertEqual(contract["allowed_modes"], list(config.COMMAND_CENTER_RUNTIME_MODES))
        self.assertEqual(
            contract["policy_row_count"],
            len(config.COMMAND_CENTER_RUNTIME_MODE_POLICIES),
        )
        self.assertEqual(contract["read_function"], "get_command_center_runtime_mode_state()")
        self.assertEqual(
            contract["invalid_value_rule"],
            "redact_invalid_value_and_fallback_to_cache_only",
        )
        self.assertEqual(
            contract["frontend_visibility_rule"],
            "read_only_mode_banner_no_frontend_edit_or_writeback",
        )
        self.assertEqual(
            contract["live_light_rule"],
            "after_cache_render_may_create_bounded_local_post_task_only",
        )
        self.assertEqual(
            contract["live_full_rule"],
            "reserved_disabled_requires_separate_authorization",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "runtime_config_contract_is_not_production_evidence",
        )
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertFalse(contract["contains_secret"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertTrue(contract["does_not_modify_strategy_action"])

    def test_command_center_live_light_bootstrap_task_contract_is_bounded_and_non_executing(self):
        contract = config.get_command_center_live_light_bootstrap_task_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_live_light_bootstrap_task_contract.v1",
        )
        self.assertEqual(contract["mode"], "live_light")
        self.assertEqual(contract["task_route"], "POST /api/bootstrap/live-startup")
        self.assertEqual(contract["task_type"], "command_center_live_bootstrap")
        self.assertEqual(contract["task_status_route"], "GET /api/tasks/{task_id}")
        self.assertEqual(contract["trigger_surface"], "after_initial_cache_render_only")
        self.assertEqual(contract["mode_gate"], "COMMAND_CENTER_BOOTSTRAP_MODE=live_light")
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
            contract["ui_rule"],
            "nonblocking_status_polling_with_last_successful_cache_fallback",
        )
        self.assertEqual(
            contract["provider_model_execution_rule"],
            "future_provider_model_execution_requires_execution_request_and_ledgers",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "bootstrap_task_contract_is_not_execution_or_production_evidence",
        )
        self.assertEqual(
            contract["allowed_external_execution_profiles"],
            list(config.COMMAND_CENTER_EXTERNAL_EXECUTION_PROFILES),
        )
        self.assertEqual(
            contract["default_external_execution_profile"],
            config.COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE,
        )
        self.assertEqual(
            contract["allowed_research_scopes"],
            list(config.COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPES),
        )
        self.assertEqual(
            contract["default_research_scope"],
            config.COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE,
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

    def test_command_center_search_quant_projection_task_contract_is_local_receipt_only(self):
        contract = config.get_command_center_search_quant_projection_task_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_search_quant_projection_task_contract.v1",
        )
        self.assertEqual(contract["next_click_label"], "生成 3.0 量化推演")
        self.assertEqual(contract["task_route"], "POST /api/candidate-radar/quant-projection")
        self.assertEqual(contract["task_type"], "run_candidate_radar_quant_projection")
        self.assertEqual(contract["task_status_route"], "GET /api/tasks/{task_id}")
        self.assertEqual(contract["output_packet_key"], "command_center_3_candidate_radar_cache")
        self.assertEqual(
            contract["receipt_schema_version"],
            "candidate_radar_search_quant_projection_receipt.v1",
        )
        self.assertEqual(
            contract["trigger_surface"],
            "explicit_confirmed_symbol_submit_or_live_light_safe_submit",
        )
        self.assertEqual(
            contract["mode_gate_rule"],
            "manual_explicit_button_or_live_light_effective_search_submit_autostart",
        )
        self.assertEqual(
            contract["search_submit_autostart_config_key"],
            "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART",
        )
        self.assertEqual(
            contract["symbol_rule"],
            "confirmed_single_a_share_symbol_normalize_suffix_and_drop_raw_query",
        )
        self.assertEqual(contract["typing_rule"], "search_typing_never_creates_task")
        self.assertEqual(
            contract["task_creation_rule"],
            "create_or_reuse_local_quant_projection_receipt_task_only",
        )
        self.assertEqual(
            contract["provider_model_execution_rule"],
            "provider_model_acceptance_requires_dry_run_execution_request_and_ledgers",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "search_quant_projection_contract_is_not_provider_model_or_production_evidence",
        )
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["provider_execution_implemented"])
        self.assertFalse(contract["model_execution_implemented"])
        self.assertFalse(contract["contains_secret"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertTrue(contract["does_not_modify_strategy_action"])
        self.assertTrue(contract["candidate_is_not_buy_instruction"])

    def test_command_center_daily_command_ordinary_workflow_contract_is_cache_first_summary(self):
        contract = config.get_command_center_daily_command_ordinary_workflow_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_daily_command_ordinary_workflow_contract.v1",
        )
        self.assertEqual(contract["ordinary_entrance"], "Daily Command Center")
        self.assertEqual(
            contract["preserved_capabilities"],
            [
                "today_focus_pool",
                "risk_summary",
                "cache_status",
                "provider_health_summary",
                "missing_evidence_prompt",
                "last_successful_cache",
            ],
        )
        self.assertEqual(contract["primary_next_click"], "review_today_cache_or_missing_evidence")
        self.assertEqual(
            contract["summary_rule"],
            "daily_command_center_shows_today_summary_before_engineering_detail",
        )
        self.assertEqual(
            contract["source_state_rule"],
            "daily_summary_shows_cache_provider_pending_or_degraded_state",
        )
        self.assertEqual(
            contract["missing_evidence_rule"],
            "daily_summary_missing_evidence_must_be_visible",
        )
        self.assertEqual(contract["last_cache_rule"], "last_successful_daily_cache_must_remain_visible")
        self.assertEqual(
            contract["research_boundary_rule"],
            "daily_summary_is_research_only_no_buy_sell_instruction",
        )
        self.assertEqual(
            contract["provider_health_rule"],
            "provider_health_detail_moves_to_settings_config_health_or_audit",
        )
        self.assertEqual(
            contract["legacy_freeze_rule"],
            "legacy_home_rerun_buttons_and_engineering_tables_are_frozen",
        )
        self.assertEqual(
            contract["not_migrated_legacy_paths"],
            [
                "streamlit_multi_button_rerun_flow",
                "provider_health_auto_probe_on_home_render",
                "engineering_status_tables_before_decision_summary",
                "ai_text_as_operation_instruction",
                "unclear_next_step_home_layout",
            ],
        )
        self.assertEqual(
            contract["required_visible_fields"],
            [
                "today_focus_pool",
                "risk_summary",
                "source_state",
                "missing_evidence",
                "blocked_or_degraded_reason",
                "last_successful_cache/result",
                "next_click",
                "research_only_boundary",
                "task_boundary",
            ],
        )
        self.assertEqual(
            contract["task_creation_rule"],
            "daily_command_center_ordinary_workflow_never_creates_tasks_on_render",
        )
        self.assertEqual(
            contract["cache_get_rule"],
            "daily_command_center_get_cache_replays_latest_status_only",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "daily_command_center_ordinary_workflow_contract_is_not_provider_model_or_production_evidence",
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
        self.assertTrue(contract["daily_summary_is_not_buy_instruction"])

    def test_command_center_stock_quant_projection_ordinary_workflow_contract_is_confirmed_symbol_path(self):
        contract = config.get_command_center_stock_quant_projection_ordinary_workflow_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_stock_quant_projection_ordinary_workflow_contract.v1",
        )
        self.assertEqual(contract["ordinary_entrance"], "Stock Quant Projection")
        self.assertEqual(
            contract["preserved_capabilities"],
            [
                "searched_symbol_single_stock_research",
                "factor_support_suppress_neutral_missing",
                "next_session_operation_zones",
                "optional_deepseek_explanation",
                "risk_budget_visibility",
            ],
        )
        self.assertEqual(contract["primary_next_click"], "生成 3.0 量化推演")
        self.assertEqual(
            contract["symbol_confirmation_rule"],
            "confirmed_single_a_share_symbol_required_before_submit",
        )
        self.assertEqual(contract["typing_rule"], "search_typing_never_creates_task_or_provider_model_call")
        self.assertEqual(
            contract["task_route_rule"],
            "work_creating_submit_uses_search_quant_projection_task_contract",
        )
        self.assertEqual(
            contract["nonblocking_rule"],
            "render_cache_then_show_task_status_and_last_successful_result",
        )
        self.assertEqual(
            contract["source_state_rule"],
            "projection_rows_show_cache_provider_model_pending_or_degraded_state",
        )
        self.assertEqual(
            contract["missing_evidence_rule"],
            "missing_provider_model_factor_next_echarts_or_browser_evidence_must_be_visible",
        )
        self.assertEqual(
            contract["research_boundary_rule"],
            "quant_projection_is_research_only_no_buy_sell_instruction",
        )
        self.assertEqual(
            contract["legacy_freeze_rule"],
            "legacy_sync_single_stock_room_and_ai_as_action_copy_are_frozen",
        )
        self.assertEqual(
            contract["user_usable_entry_rule"],
            "stock_quant_projection_user_usable_entry_requires_confirmed_symbol_cache_task_status_and_research_boundary",
        )
        self.assertEqual(
            contract["promotion_blocker_rule"],
            "stock_quant_projection_cannot_promote_from_search_typing_ai_text_or_local_receipt_only",
        )
        self.assertEqual(
            contract["user_usable_required_evidence"],
            [
                "confirmed_single_a_share_symbol_visible",
                "generate_3_0_quant_projection_button_or_disabled_reason_visible",
                "cache_result_or_last_successful_result_visible",
                "task_status_visible_after_submit",
                "provider_model_cache_pending_state_visible",
                "factor_next_echarts_or_browser_missing_evidence_visible",
                "deepseek_explanation_status_is_optional_and_explanation_only_visible",
                "research_only_no_buy_sell_or_strategy_action_boundary_visible",
            ],
        )
        self.assertEqual(
            contract["forbidden_promotion_evidence"],
            [
                "search_typing_only",
                "ai_text_as_action_only",
                "local_quant_projection_receipt_only",
                "provider_model_scope_ticket_only",
                "legacy_single_stock_room_ui_parity_only",
                "docs_config_scaffold_only",
            ],
        )
        self.assertEqual(
            contract["not_migrated_legacy_paths"],
            [
                "old_tab_radio_deep_navigation",
                "synchronous_blocking_projection",
                "conflicting_position_context",
                "deepseek_overwrites_numbers_or_strategy_action",
                "ai_text_as_trade_instruction",
            ],
        )
        self.assertEqual(
            contract["required_visible_fields"],
            [
                "confirmed_symbol",
                "next_click",
                "source_state",
                "missing_evidence",
                "last_successful_result",
                "task_status",
                "factor_support_suppress_neutral_missing",
                "next_session_operation_zones",
                "deepseek_state",
                "research_only_boundary",
            ],
        )
        self.assertEqual(
            contract["task_creation_rule"],
            "stock_quant_projection_ordinary_workflow_never_creates_tasks_on_typing_or_render",
        )
        self.assertEqual(
            contract["cache_get_rule"],
            "stock_quant_projection_get_cache_replays_latest_status_only",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "stock_quant_projection_ordinary_workflow_contract_is_not_provider_model_or_production_evidence",
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
        self.assertTrue(contract["projection_is_not_buy_instruction"])
        self.assertFalse(contract["production_quant_projection_complete"])

    def test_command_center_candidate_radar_ordinary_workflow_contract_is_user_usable_not_recommendation(self):
        contract = config.get_command_center_candidate_radar_ordinary_workflow_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_candidate_radar_ordinary_workflow_contract.v1",
        )
        self.assertEqual(contract["ordinary_entrance"], "Candidate Radar")
        self.assertEqual(
            contract["preserved_capabilities"],
            [
                "Top/Watch/Excluded candidate groups",
                "scoring_reason",
                "scan_scope",
                "candidate_pool_source",
                "no_feature_loss_visibility",
            ],
        )
        self.assertEqual(
            contract["primary_next_click"],
            "review_last_radar_cache_or_button_gated_quick_scan",
        )
        self.assertEqual(
            contract["quick_scan_rule"],
            "quick_scan_must_be_button_gated_post_task_or_local_fallback",
        )
        self.assertEqual(contract["last_cache_rule"], "last_radar_cache_visible_before_scan_action")
        self.assertEqual(
            contract["coverage_gap_rule"],
            "missing_full_pool_deep_scan_browser_ci_or_provider_evidence_must_be_visible",
        )
        self.assertEqual(
            contract["source_state_rule"],
            "candidate_rows_show_provider_cache_pending_or_degraded_state",
        )
        self.assertEqual(contract["research_boundary_rule"], "radar_candidate_is_not_buy_instruction")
        self.assertEqual(
            contract["legacy_freeze_rule"],
            "legacy_fallback_recommendation_copy_is_frozen_until_replacement_evidence",
        )
        self.assertEqual(
            contract["user_usable_entry_rule"],
            "candidate_radar_user_usable_entry_requires_cache_scope_source_gap_and_no_buy_boundary",
        )
        self.assertEqual(
            contract["promotion_blocker_rule"],
            "candidate_radar_cannot_promote_from_legacy_ui_or_local_receipt_only",
        )
        self.assertEqual(
            contract["user_usable_required_evidence"],
            [
                "last_radar_cache_visible",
                "scan_scope_and_candidate_pool_source_visible",
                "top_watch_excluded_groups_visible",
                "scoring_reason_visible",
                "provider_cache_pending_or_degraded_state_visible",
                "missing_full_pool_deep_scan_browser_ci_or_provider_evidence_visible",
                "candidate_is_not_buy_instruction_visible",
                "quick_scan_button_or_disabled_reason_visible",
            ],
        )
        self.assertEqual(
            contract["forbidden_promotion_evidence"],
            [
                "old_streamlit_radar_ui_parity_only",
                "legacy_fallback_path_only",
                "no_feature_loss_matrix_only",
                "local_receipt_only",
                "stage_scope_manifest_only",
                "browser_artifact_without_provider_or_worker_evidence",
            ],
        )
        self.assertEqual(
            contract["not_migrated_legacy_paths"],
            [
                "recommendation_style_candidate_copy",
                "page_render_full_pool_scan",
                "page_render_deep_scan",
                "unclear_legacy_fallback_lineage",
                "performance_timeout_as_success",
            ],
        )
        self.assertEqual(
            contract["required_visible_fields"],
            [
                "candidate_group",
                "scoring_reason",
                "scan_scope",
                "candidate_pool_source",
                "source_state",
                "missing_evidence",
                "last_radar_cache",
                "task_status",
                "research_only_boundary",
            ],
        )
        self.assertEqual(
            contract["task_creation_rule"],
            "candidate_radar_ordinary_workflow_never_creates_tasks_on_render",
        )
        self.assertEqual(
            contract["cache_get_rule"],
            "candidate_radar_get_cache_replays_latest_status_only",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "candidate_radar_ordinary_workflow_contract_is_not_production_replacement_evidence",
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
        self.assertTrue(contract["candidate_is_not_buy_instruction"])
        self.assertFalse(contract["production_radar_replacement_complete"])
        self.assertFalse(contract["legacy_retirement_ready"])

    def test_command_center_ordinary_workflow_registry_contract_indexes_three_user_entrances(self):
        contract = config.get_command_center_ordinary_workflow_registry_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_ordinary_workflow_registry_contract.v1",
        )
        self.assertEqual(
            [row["entrance_key"] for row in contract["ordinary_entrances"]],
            ["daily_command_center", "stock_quant_projection", "candidate_radar"],
        )
        rows = {row["entrance_key"]: row for row in contract["ordinary_entrances"]}
        self.assertEqual(
            rows["daily_command_center"]["workflow_contract"],
            "COMMAND_CENTER_DAILY_COMMAND_ORDINARY_WORKFLOW_CONTRACT",
        )
        self.assertEqual(
            rows["daily_command_center"]["read_function"],
            "get_command_center_daily_command_ordinary_workflow_contract()",
        )
        self.assertEqual(
            rows["daily_command_center"]["primary_next_click"],
            "review_today_cache_or_missing_evidence",
        )
        self.assertEqual(rows["daily_command_center"]["work_creation_surface"], "none_from_render")
        self.assertEqual(
            rows["stock_quant_projection"]["workflow_contract"],
            "COMMAND_CENTER_STOCK_QUANT_PROJECTION_ORDINARY_WORKFLOW_CONTRACT",
        )
        self.assertEqual(
            rows["stock_quant_projection"]["read_function"],
            "get_command_center_stock_quant_projection_ordinary_workflow_contract()",
        )
        self.assertEqual(rows["stock_quant_projection"]["primary_next_click"], "生成 3.0 量化推演")
        self.assertEqual(
            rows["stock_quant_projection"]["work_creation_surface"],
            "confirmed_symbol_submit_post_task_or_local_fallback",
        )
        self.assertEqual(
            rows["candidate_radar"]["workflow_contract"],
            "COMMAND_CENTER_CANDIDATE_RADAR_ORDINARY_WORKFLOW_CONTRACT",
        )
        self.assertEqual(
            rows["candidate_radar"]["read_function"],
            "get_command_center_candidate_radar_ordinary_workflow_contract()",
        )
        self.assertEqual(
            rows["candidate_radar"]["primary_next_click"],
            "review_last_radar_cache_or_button_gated_quick_scan",
        )
        self.assertEqual(
            rows["candidate_radar"]["work_creation_surface"],
            "button_gated_quick_scan_post_task_or_local_fallback",
        )
        self.assertEqual(
            contract["registry_rule"],
            "three_ordinary_entrances_are_the_primary_user_workflow",
        )
        self.assertEqual(
            contract["placement_rule"],
            "ordinary_registry_rows_appear_before_settings_developer_audit",
        )
        self.assertEqual(
            contract["shared_summary_rule"],
            (
                "each_registered_entrance_shows_next_click_source_state_missing_evidence_"
                "research_boundary_blocked_degraded_and_last_successful_result"
            ),
        )
        self.assertEqual(contract["task_creation_rule"], "ordinary_workflow_registry_never_creates_tasks")
        self.assertEqual(contract["cache_write_rule"], "ordinary_workflow_registry_never_writes_cache_or_config")
        self.assertEqual(
            contract["production_evidence_rule"],
            "ordinary_workflow_registry_contract_is_not_production_evidence",
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

    def test_command_center_ordinary_source_state_display_contract_lists_per_entrance_fields(self):
        contract = config.get_command_center_ordinary_source_state_display_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_ordinary_source_state_display_contract.v1",
        )
        rows = {row["entrance_key"]: row for row in contract["ordinary_entrances"]}
        self.assertEqual(set(rows), {"daily_command_center", "stock_quant_projection", "candidate_radar"})
        self.assertEqual(
            rows["daily_command_center"]["display_fields"],
            [
                "cache_status",
                "provider_health_summary",
                "deepseek_explanation_state",
                "pending_or_missing_evidence",
                "degraded_reason",
                "last_successful_cache/result",
            ],
        )
        self.assertEqual(
            rows["stock_quant_projection"]["display_fields"],
            [
                "cache_result_state",
                "tushare_provider_state",
                "factor_state",
                "next_session_state",
                "deepseek_state",
                "pending_or_missing_evidence",
                "degraded_reason",
                "last_successful_result",
            ],
        )
        self.assertEqual(
            rows["candidate_radar"]["display_fields"],
            [
                "candidate_cache_state",
                "provider_parity_state",
                "scan_scope_state",
                "deepseek_deep_scan_state",
                "pending_or_missing_evidence",
                "degraded_reason",
                "last_radar_cache",
            ],
        )
        self.assertEqual(
            contract["shared_state_rule"],
            "provider_model_cache_pending_states_must_be_visible_in_ordinary_summary",
        )
        self.assertEqual(
            contract["provider_rule"],
            "tushare_state_requires_call_ledger_or_provider_pending_marker",
        )
        self.assertEqual(
            contract["model_rule"],
            "deepseek_state_is_explanation_only_with_model_ledger_or_pending_marker",
        )
        self.assertEqual(
            contract["cache_rule"],
            "cache_state_must_show_freshness_and_last_successful_pointer",
        )
        self.assertEqual(
            contract["pending_rule"],
            "pending_state_must_name_missing_evidence_or_next_allowed_task",
        )
        self.assertEqual(
            contract["degraded_rule"],
            "degraded_state_must_show_blocker_and_safe_fallback",
        )
        self.assertEqual(contract["non_action_rule"], "source_state_display_is_not_next_click_or_trade_action")
        self.assertEqual(
            contract["page_visibility_rule"],
            "ordinary_source_state_page_visibility_requires_provider_model_cache_pending_last_successful_and_blocker_rows",
        )
        self.assertEqual(
            contract["promotion_blocker_rule"],
            "ordinary_source_state_cannot_promote_from_hidden_tabs_tooltips_or_engineering_tables_only",
        )
        self.assertEqual(
            contract["page_visibility_required_evidence"],
            [
                "source_state_visible_in_ordinary_summary",
                "cache_freshness_and_last_successful_pointer_visible",
                "tushare_call_ledger_or_provider_pending_marker_visible",
                "deepseek_model_ledger_or_pending_marker_visible",
                "pending_missing_evidence_or_next_allowed_task_visible",
                "degraded_blocker_and_safe_fallback_visible",
                "no_trade_no_action_boundary_visible_next_to_state",
                "settings_developer_audit_link_for_detail_visible",
            ],
        )
        self.assertEqual(
            contract["forbidden_page_visibility_evidence"],
            [
                "engineering_audit_table_only",
                "settings_detail_only",
                "tooltip_only",
                "hidden_tab_only",
                "local_receipt_only",
                "docs_config_scaffold_only",
            ],
        )
        self.assertEqual(contract["task_creation_rule"], "ordinary_source_state_display_never_creates_tasks")
        self.assertEqual(contract["cache_write_rule"], "ordinary_source_state_display_never_writes_cache_or_config")
        self.assertEqual(
            contract["production_evidence_rule"],
            "ordinary_source_state_display_contract_is_not_provider_model_or_production_evidence",
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

    def test_command_center_ordinary_source_state_contract_is_read_only_vocabulary(self):
        contract = config.get_command_center_ordinary_source_state_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_ordinary_source_state_contract.v1",
        )
        self.assertEqual(
            contract["ordinary_entrances"],
            ["Daily Command Center", "Stock Quant Projection", "Candidate Radar"],
        )
        self.assertEqual(
            contract["vocabulary"],
            ["cache", "Tushare", "DeepSeek", "pending", "degraded", "last_successful_cache/result"],
        )
        self.assertEqual(contract["cache"], "visible_value_from_local_packet_or_cache")
        self.assertEqual(
            contract["Tushare"],
            "provider_backed_or_provider_pending_market_data_with_call_ledger_status",
        )
        self.assertEqual(
            contract["DeepSeek"],
            "explanation_only_model_output_never_data_source_or_action_writer",
        )
        self.assertEqual(contract["pending"], "missing_not_run_or_waiting_evidence")
        self.assertEqual(contract["degraded"], "stale_failed_or_partial_source_with_visible_blocker")
        self.assertEqual(contract["last_successful_cache/result"], "latest_safe_fallback_result")
        self.assertEqual(contract["ui_rule"], "read_only_source_state_chips_in_ordinary_summary")
        self.assertEqual(
            contract["missing_evidence_rule"],
            "pending_or_degraded_state_must_show_missing_evidence_or_blocker",
        )
        self.assertEqual(
            contract["deepseek_boundary"],
            "deepseek_never_overwrites_price_holding_factor_operation_zone_or_strategy_action",
        )
        self.assertEqual(contract["task_creation_rule"], "source_state_chips_never_create_tasks")
        self.assertEqual(contract["cache_write_rule"], "source_state_chips_never_write_cache_or_config")
        self.assertEqual(
            contract["production_evidence_rule"],
            "source_state_contract_is_not_provider_model_or_production_evidence",
        )
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["provider_execution_implemented"])
        self.assertFalse(contract["model_execution_implemented"])
        self.assertFalse(contract["contains_secret"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertTrue(contract["does_not_modify_strategy_action"])

    def test_command_center_ordinary_next_click_contract_is_single_action_and_research_only(self):
        contract = config.get_command_center_ordinary_next_click_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_ordinary_next_click_contract.v1",
        )
        rows = {row["entrance_key"]: row for row in contract["ordinary_entrances"]}
        self.assertEqual(set(rows), {"daily_command_center", "stock_quant_projection", "candidate_radar"})
        self.assertEqual(
            rows["daily_command_center"]["primary_next_click"],
            "review_today_cache_or_missing_evidence",
        )
        self.assertFalse(rows["daily_command_center"]["work_creating"])
        self.assertEqual(rows["stock_quant_projection"]["primary_next_click"], "生成 3.0 量化推演")
        self.assertTrue(rows["stock_quant_projection"]["work_creating"])
        self.assertEqual(
            rows["stock_quant_projection"]["task_contract"],
            "COMMAND_CENTER_SEARCH_QUANT_PROJECTION_TASK_CONTRACT",
        )
        self.assertEqual(
            rows["candidate_radar"]["primary_next_click"],
            "review_last_radar_cache_or_button_gated_quick_scan",
        )
        self.assertEqual(
            rows["candidate_radar"]["work_creating"],
            "button_gated_when_quick_scan_selected",
        )
        self.assertEqual(
            contract["one_primary_action_rule"],
            "one_primary_safe_action_per_ordinary_entrance",
        )
        self.assertEqual(
            contract["blocked_reason_rule"],
            "disabled_or_degraded_reason_visible_before_click",
        )
        self.assertEqual(
            contract["non_action_surfaces"],
            [
                "search_typing",
                "react_render",
                "mode_banner",
                "source_state_chip",
                "deepseek_text",
                "radar_candidate",
            ],
        )
        self.assertEqual(
            contract["work_creation_rule"],
            "work_creating_next_click_must_use_post_task_worker_or_local_fallback",
        )
        self.assertEqual(contract["task_status_rule"], "work_creating_next_click_must_show_task_status")
        self.assertEqual(
            contract["research_boundary_rule"],
            "next_click_is_research_only_no_buy_sell_instruction",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "ordinary_next_click_contract_is_not_execution_or_production_evidence",
        )
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["provider_execution_implemented"])
        self.assertFalse(contract["model_execution_implemented"])
        self.assertFalse(contract["contains_secret"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertTrue(contract["does_not_modify_strategy_action"])
        self.assertFalse(contract["radar_candidate_is_buy_instruction"])

    def test_command_center_ordinary_research_boundary_contract_blocks_trade_interpretation(self):
        contract = config.get_command_center_ordinary_research_boundary_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_ordinary_research_boundary_contract.v1",
        )
        self.assertEqual(
            contract["ordinary_entrances"],
            ["Daily Command Center", "Stock Quant Projection", "Candidate Radar"],
        )
        self.assertEqual(contract["boundary_label"], "research_only_not_buy_sell_instruction")
        self.assertEqual(contract["ui_rule"], "show_research_only_boundary_in_ordinary_summary")
        self.assertEqual(
            contract["deepseek_rule"],
            "deepseek_text_is_explanation_only_not_data_source_or_action",
        )
        self.assertEqual(contract["factor_rule"], "factor_scores_are_research_evidence_not_trade_action")
        self.assertEqual(contract["radar_rule"], "radar_candidate_is_not_buy_instruction")
        self.assertEqual(contract["next_session_rule"], "operation_zones_are_conditions_not_orders")
        self.assertEqual(contract["task_receipt_rule"], "task_receipts_are_evidence_not_trade_instruction")
        self.assertEqual(
            contract["forbidden_interpretations"],
            [
                "buy_signal",
                "sell_signal",
                "position_order",
                "broker_order",
                "strategy_action_mutation",
                "deepseek_as_data_source",
            ],
        )
        self.assertEqual(
            contract["mutation_rule"],
            "never_modify_strategy_action_prices_positions_factors_or_operation_zones",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "research_boundary_contract_is_not_execution_or_production_evidence",
        )
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["provider_execution_implemented"])
        self.assertFalse(contract["model_execution_implemented"])
        self.assertFalse(contract["contains_secret"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertTrue(contract["does_not_modify_strategy_action"])
        self.assertFalse(contract["radar_candidate_is_buy_instruction"])
        self.assertFalse(contract["deepseek_text_is_buy_instruction"])
        self.assertFalse(contract["factor_score_is_buy_instruction"])

    def test_command_center_ordinary_evidence_fallback_contract_keeps_missing_state_visible(self):
        contract = config.get_command_center_ordinary_evidence_fallback_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_ordinary_evidence_fallback_contract.v1",
        )
        self.assertEqual(
            contract["ordinary_entrances"],
            ["Daily Command Center", "Stock Quant Projection", "Candidate Radar"],
        )
        self.assertEqual(
            contract["missing_evidence_rule"],
            "missing_evidence_must_be_visible_before_action",
        )
        self.assertEqual(
            contract["blocked_state_rule"],
            "blocked_state_must_show_blocker_and_allowed_next_step",
        )
        self.assertEqual(
            contract["degraded_state_rule"],
            "degraded_state_must_show_stale_failed_or_partial_source",
        )
        self.assertEqual(
            contract["last_successful_rule"],
            "last_successful_cache_or_result_must_remain_visible_as_fallback",
        )
        self.assertEqual(
            contract["fallback_boundary_rule"],
            "fallback_is_display_only_not_current_provider_model_evidence",
        )
        self.assertEqual(
            contract["required_visible_fields"],
            [
                "missing_evidence",
                "blocked_reason",
                "degraded_reason",
                "last_successful_cache/result",
                "freshness_state",
                "task_status",
            ],
        )
        self.assertEqual(
            contract["non_evidence_states"],
            [
                "pending",
                "degraded",
                "stale",
                "failed",
                "partial",
                "last_successful_cache/result",
            ],
        )
        self.assertEqual(
            contract["task_creation_rule"],
            "evidence_fallback_display_never_creates_tasks",
        )
        self.assertEqual(
            contract["cache_write_rule"],
            "evidence_fallback_display_never_writes_cache_or_config",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "evidence_fallback_contract_is_not_provider_model_or_production_evidence",
        )
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["provider_execution_implemented"])
        self.assertFalse(contract["model_execution_implemented"])
        self.assertFalse(contract["contains_secret"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertTrue(contract["does_not_modify_strategy_action"])

    def test_command_center_legacy_audit_classification_contract_blocks_seed_only_keep(self):
        contract = config.get_command_center_legacy_audit_classification_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_legacy_audit_classification_contract.v1",
        )
        self.assertEqual(contract["classifications"], ["KEEP", "REDESIGN", "LEGACY-DEBUG", "RETIRE"])
        self.assertEqual(
            contract["ordinary_workflow_scope"],
            [
                "home/daily command",
                "searched-symbol quant projection",
                "candidate radar",
                "next-session map",
                "factor/risk/provider health",
                "discipline/backtest",
                "ETF/leverage",
                "external brain/AI advisor",
            ],
        )
        self.assertEqual(
            contract["keep_promotion_rule"],
            "keep_requires_direct_legacy_bug_ux_audit_evidence",
        )
        self.assertEqual(
            contract["redesign_rule"],
            "useful_capability_rebuild_old_ux_or_code_before_ordinary_flow",
        )
        self.assertEqual(
            contract["legacy_debug_rule"],
            "admin_debug_fallback_only_not_ordinary_flow",
        )
        self.assertEqual(
            contract["retire_rule"],
            "freeze_or_remove_from_ordinary_user_workflow",
        )
        self.assertEqual(
            contract["seed_only_rule"],
            "seed_inventory_receipt_matrix_or_docs_config_cannot_promote_keep",
        )
        self.assertEqual(
            contract["direct_evidence_rule"],
            "direct_evidence_row_required_before_keep_or_ordinary_entry",
        )
        self.assertEqual(
            contract["seed_status_rule"],
            "seed_only_rows_default_to_redesign_legacy_debug_or_retire",
        )
        self.assertEqual(
            contract["lineage_rule"],
            "unclear_data_lineage_blocks_ordinary_entry_until_redesigned_or_frozen",
        )
        self.assertEqual(
            contract["scope_rule"],
            "audit_scope_tracks_workflow_group_not_legacy_file_or_tab_count",
        )
        self.assertEqual(
            contract["ordinary_entry_rule"],
            "ordinary_entry_requires_replacement_entrance_and_frozen_legacy_path",
        )
        self.assertEqual(
            contract["keep_entry_rule"],
            "keep_requires_direct_evidence_and_no_open_bug_or_lineage_blocker",
        )
        self.assertEqual(
            contract["redesign_entry_rule"],
            "redesign_requires_replacement_workflow_before_ordinary_entry",
        )
        self.assertEqual(
            contract["transition_rules"],
            [
                "seed_only_cannot_transition_to_keep",
                "direct_evidence_ready_can_transition_to_keep_only_with_all_required_fields",
                "blocked_by_lineage_transitions_to_redesign_legacy_debug_or_retire",
                "known_bug_or_patchwork_without_replacement_stays_redesign_or_retire",
                "legacy_debug_and_retire_do_not_enter_ordinary_user_flow",
            ],
        )
        self.assertEqual(
            contract["ordinary_entry_allowed_after_audit"],
            ["KEEP", "REDESIGN_WITH_REPLACEMENT_READY"],
        )
        self.assertEqual(
            contract["ordinary_entry_forbidden_after_audit"],
            [
                "LEGACY-DEBUG",
                "RETIRE",
                "seed_only",
                "blocked_by_lineage",
                "REDESIGN_WITHOUT_REPLACEMENT_READY",
            ],
        )
        self.assertEqual(
            contract["streamlit_fallback_rule"],
            "streamlit_remains_fallback_admin_debug_until_react_tauri_workflow_is_easier_clearer_more_reliable",
        )
        self.assertEqual(
            contract["streamlit_primary_surface_rule"],
            "streamlit_must_not_be_primary_3_0_runtime_or_target_ux",
        )
        self.assertEqual(
            contract["fallback_retirement_rule"],
            "fallback_retirement_requires_replacement_workflow_direct_evidence_and_rollback_plan",
        )
        self.assertEqual(
            contract["fallback_retirement_required_evidence"],
            [
                "react_tauri_replacement_workflow_ready",
                "ordinary_entry_easier_clearer_more_reliable_evidence",
                "direct_legacy_bug_ux_audit_complete",
                "provider_model_cache_pending_state_visible",
                "last_successful_cache_or_result_visible",
                "rollback_or_admin_debug_path_retained_until_promotion",
            ],
        )
        self.assertEqual(
            contract["fallback_retirement_forbidden_evidence"],
            [
                "streamlit_ui_polish_only",
                "route_inventory_only",
                "local_receipt_only",
                "stage_scope_manifest_only",
                "no_feature_loss_matrix_only",
                "docs_config_scaffold_only",
            ],
        )
        self.assertEqual(
            contract["evidence_statuses"],
            [
                "seed_only",
                "direct_evidence_pending",
                "direct_evidence_ready",
                "blocked_by_lineage",
                "frozen_or_retired",
            ],
        )
        self.assertEqual(
            contract["forbidden_keep_evidence_sources"],
            [
                "route_inventory_only",
                "legacy_tab_name_only",
                "docs_config_scaffold_only",
                "local_receipt_only",
                "no_feature_loss_matrix_only",
                "mock_sanitizer_or_preflight_only",
            ],
        )
        self.assertEqual(
            contract["required_evidence_fields"],
            [
                "observed_user_action_or_workflow_problem",
                "legacy_bug_confusing_ux_or_patchwork_removed",
                "data_lineage_check",
                "replacement_ordinary_entrance",
                "frozen_legacy_path",
            ],
        )
        self.assertEqual(
            contract["row_evidence_rule"],
            "legacy_audit_row_requires_scope_status_direct_source_lineage_replacement_and_freeze_decision",
        )
        self.assertEqual(
            contract["row_required_fields"],
            [
                "workflow_group",
                "legacy_surface_or_module",
                "observed_user_action_or_workflow_problem",
                "direct_ux_bug_evidence_source",
                "classification",
                "evidence_status",
                "data_lineage_check",
                "replacement_ordinary_entrance",
                "frozen_legacy_path",
                "ordinary_entry_decision",
                "next_action",
            ],
        )
        self.assertEqual(
            contract["forbidden_row_completion_evidence"],
            [
                "file_inventory_only",
                "legacy_tab_count_only",
                "route_exists_only",
                "local_receipt_only",
                "docs_config_scaffold_only",
                "no_feature_loss_matrix_only",
            ],
        )
        self.assertEqual(
            contract["seed_rows_rule"],
            "legacy_audit_seed_rows_cover_ordinary_workflow_scope_without_keep_promotion",
        )
        self.assertEqual(
            contract["seed_row_promotion_rule"],
            "legacy_audit_seed_rows_are_not_direct_evidence_or_production_evidence",
        )
        seed_rows = {row["workflow_group"]: row for row in contract["seed_rows"]}
        self.assertEqual(set(seed_rows), set(contract["ordinary_workflow_scope"]))
        self.assertTrue(
            all(set(contract["row_required_fields"]).issubset(set(row)) for row in contract["seed_rows"])
        )
        self.assertTrue(all(row["classification"] != "KEEP" for row in contract["seed_rows"]))
        self.assertTrue(all(row["evidence_status"] == "seed_only" for row in contract["seed_rows"]))
        self.assertTrue(
            all(row["direct_ux_bug_evidence_source"] == "direct_ux_bug_evidence_pending" for row in contract["seed_rows"])
        )
        self.assertEqual(
            seed_rows["home/daily command"]["replacement_ordinary_entrance"],
            "Daily Command Center",
        )
        self.assertEqual(
            seed_rows["searched-symbol quant projection"]["replacement_ordinary_entrance"],
            "Stock Quant Projection",
        )
        self.assertEqual(
            seed_rows["candidate radar"]["replacement_ordinary_entrance"],
            "Candidate Radar",
        )
        self.assertEqual(
            seed_rows["discipline/backtest"]["ordinary_entry_decision"],
            "not_promoted_legacy_debug",
        )
        self.assertEqual(
            seed_rows["external brain/AI advisor"]["classification"],
            "RETIRE",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "legacy_audit_classification_contract_is_not_production_evidence",
        )
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["provider_execution_implemented"])
        self.assertFalse(contract["model_execution_implemented"])
        self.assertFalse(contract["contains_secret"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertTrue(contract["does_not_modify_strategy_action"])

    def test_command_center_migration_checkpoint_contract_requires_five_user_facing_answers(self):
        contract = config.get_command_center_migration_checkpoint_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_migration_checkpoint_contract.v1",
        )
        self.assertEqual(
            contract["required_questions"],
            [
                "what_user_capability_was_preserved",
                "what_legacy_ux_problem_was_removed",
                "what_legacy_bug_or_patchwork_path_was_not_migrated",
                "what_became_simpler_for_nontechnical_user",
                "which_real_blocker_was_reduced",
            ],
        )
        self.assertEqual(
            contract["checkpoint_rule"],
            "every_future_migration_checkpoint_must_answer_five_questions",
        )
        self.assertEqual(
            contract["keep_gate_rule"],
            "cannot_promote_keep_or_ordinary_flow_without_checkpoint_answers",
        )
        self.assertEqual(
            contract["release_blocker_rule"],
            "broad_contract_receipt_runbook_or_manifest_requires_named_release_blocker",
        )
        self.assertEqual(
            contract["scope_rule"],
            "checkpoint_answers_must_reference_the_touched_user_workflow_or_release_blocker",
        )
        self.assertEqual(
            contract["non_evidence_rule"],
            "checkpoint_answers_are_planning_evidence_not_production_acceptance",
        )
        self.assertEqual(
            contract["priority_order"],
            [
                "fix_push_gate_ci_evidence",
                "legacy_bug_ux_audit_for_streamlit_ordinary_workflows",
                "rebuild_ltg13_candidate_radar_user_usable_workflow",
                "searched_symbol_to_generate_3_0_quant_projection",
                "show_provider_model_cache_pending_state_on_page",
                "move_engineering_audit_tables_out_of_ordinary_flow",
            ],
        )
        self.assertEqual(
            contract["priority_rule"],
            "future_migration_slices_follow_current_priority_order_or_name_blocker_exception",
        )
        self.assertEqual(
            contract["ci_rule"],
            "remote_ci_unverified_remains_release_blocker_until_current_green_or_reviewed_logs",
        )
        self.assertEqual(
            contract["ci_required_evidence"],
            [
                "matching_head_sha_or_commit",
                "current_remote_actions_green_or_failed_step_reviewed",
                "fresh_local_push_gate_result_for_current_head",
                "safe_failure_log_excerpt_or_green_run_url",
                "explicit_user_push_confirmation_before_push",
            ],
        )
        self.assertEqual(
            contract["ci_non_evidence_sources"],
            [
                "local_unit_tests_only",
                "checkpoint_answer_only",
                "static_workflow_file_presence_only",
                "ci_failure_email_without_matching_run_logs",
                "old_remote_green_run_for_different_head",
                "local_receipt_or_stage_scope_manifest_only",
            ],
        )
        self.assertEqual(
            contract["ci_review_row_rule"],
            "remote_ci_review_row_requires_head_status_log_local_gate_push_decision",
        )
        self.assertEqual(
            contract["ci_review_required_fields"],
            [
                "head_sha_or_commit",
                "remote_run_url_or_id",
                "remote_status",
                "failed_step_or_green_status",
                "safe_failure_log_excerpt_or_green_run_url",
                "local_gate_result_for_same_head",
                "push_confirmation_state",
                "release_claim_decision",
                "next_action",
            ],
        )
        self.assertEqual(
            contract["ci_review_forbidden_completion_evidence"],
            [
                "old_run_without_matching_head",
                "email_subject_only",
                "local_gate_pass_only",
                "workflow_yaml_presence_only",
                "unreviewed_failed_step",
                "unchecked_artifact_or_secret_scan",
            ],
        )
        self.assertEqual(
            contract["ci_review_seed_row_rule"],
            "remote_ci_review_seed_row_keeps_p0_blocked_until_matching_remote_run_review",
        )
        self.assertEqual(
            set(contract["ci_review_seed_row"]),
            set(contract["ci_review_required_fields"]),
        )
        self.assertEqual(
            contract["ci_review_seed_row"]["head_sha_or_commit"],
            "pending_current_head_sha",
        )
        self.assertEqual(
            contract["ci_review_seed_row"]["remote_run_url_or_id"],
            "pending_remote_actions_run",
        )
        self.assertEqual(contract["ci_review_seed_row"]["remote_status"], "remote_ci_unverified")
        self.assertEqual(contract["ci_review_seed_row"]["failed_step_or_green_status"], "not_reviewed")
        self.assertEqual(
            contract["ci_review_seed_row"]["local_gate_result_for_same_head"],
            "pending_fresh_local_push_gate_for_current_head",
        )
        self.assertEqual(
            contract["ci_review_seed_row"]["push_confirmation_state"],
            "not_requested_no_push",
        )
        self.assertEqual(
            contract["ci_review_seed_row"]["release_claim_decision"],
            "blocked_remote_ci_unverified",
        )
        self.assertEqual(
            contract["release_claim_rule"],
            "release_or_production_replacement_claim_requires_current_remote_ci_green_or_reviewed_failure_logs",
        )
        self.assertEqual(
            contract["push_rule"],
            "push_requires_explicit_user_confirmation_after_local_gate_review",
        )
        self.assertEqual(
            contract["github_api_rule"],
            "ci_checkpoint_contract_never_calls_github_or_fetches_actions_logs",
        )
        self.assertEqual(
            contract["legacy_audit_rule"],
            "legacy_bug_ux_audit_precedes_major_ordinary_workflow_migration",
        )
        self.assertEqual(
            contract["ordinary_flow_rule"],
            "ordinary_user_workflow_slices_precede_extra_engineering_scaffold",
        )
        self.assertEqual(
            contract["forbidden_shortcuts"],
            [
                "claiming_ltg_complete_from_docs_config_scaffold",
                "using_receipt_matrix_or_sanitizer_as_production_evidence",
                "copying_legacy_ui_without_ux_bug_audit",
                "omitting_blocker_reduction",
                "starting_new_broad_ltg_surface_without_named_current_release_blocker",
                "treating_local_gate_or_checkpoint_as_remote_ci_green",
            ],
        )
        self.assertEqual(
            contract["task_creation_rule"],
            "migration_checkpoint_contract_never_creates_tasks",
        )
        self.assertEqual(
            contract["cache_write_rule"],
            "migration_checkpoint_contract_never_writes_cache_or_config",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "migration_checkpoint_contract_is_not_production_evidence",
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

    def test_command_center_ordinary_audit_placement_contract_demotes_engineering_detail(self):
        contract = config.get_command_center_ordinary_audit_placement_contract()

        self.assertEqual(
            contract["schema_version"],
            "command_center_ordinary_audit_placement_contract.v1",
        )
        self.assertEqual(
            contract["ordinary_entrances"],
            ["Daily Command Center", "Stock Quant Projection", "Candidate Radar"],
        )
        self.assertEqual(
            contract["ordinary_summary_allowed_fields"],
            [
                "next_click",
                "source_state",
                "missing_evidence",
                "research_only_boundary",
                "blocked_or_degraded_reason",
                "last_successful_cache/result",
                "task_boundary",
            ],
        )
        self.assertEqual(contract["audit_detail_surfaces"], ["Settings", "Developer", "Audit"])
        self.assertEqual(
            contract["demoted_detail_types"],
            [
                "engineering_contract_tables",
                "receipt_rows",
                "runbooks",
                "LTG_audit_surfaces",
                "lineage_details",
            ],
        )
        self.assertEqual(
            contract["ordinary_promotion_required_evidence"],
            [
                "next_click_visible_before_audit_detail",
                "source_state_visible_before_audit_detail",
                "missing_evidence_visible_before_audit_detail",
                "research_only_boundary_visible_before_audit_detail",
                "blocked_or_degraded_reason_visible_before_audit_detail",
                "last_successful_cache_or_result_visible_before_audit_detail",
                "task_boundary_visible_before_audit_detail",
                "settings_developer_audit_link_visible_for_details",
            ],
        )
        self.assertEqual(
            contract["ordinary_first_view_forbidden_surfaces"],
            [
                "engineering_contract_table_as_primary_surface",
                "receipt_rows_as_primary_surface",
                "runbook_as_primary_surface",
                "ltg_audit_table_as_primary_surface",
                "legacy_route_inventory_as_primary_surface",
            ],
        )
        self.assertEqual(
            contract["placement_rule"],
            "ordinary_pages_show_user_summary_before_engineering_audit_details",
        )
        self.assertEqual(
            contract["promotion_rule"],
            "ordinary_entry_promotion_requires_user_summary_fields_before_engineering_detail",
        )
        self.assertEqual(
            contract["demotion_rule"],
            "detailed_engineering_audit_tables_move_to_settings_developer_audit",
        )
        self.assertEqual(
            contract["first_view_rule"],
            "ordinary_first_view_shows_next_click_state_gaps_boundary_and_last_success_before_audit",
        )
        self.assertEqual(
            contract["exception_rule"],
            "ordinary_pages_include_engineering_detail_only_for_current_decision_surface",
        )
        self.assertEqual(
            contract["dominance_rule"],
            "engineering_contract_tables_must_not_dominate_ordinary_pages",
        )
        self.assertEqual(
            contract["audit_demotion_rule"],
            "ordinary_first_view_must_not_be_engineering_audit_dashboard",
        )
        self.assertEqual(
            contract["audit_demotion_required_evidence"],
            [
                "ordinary_summary_rendered_before_any_engineering_table",
                "engineering_contract_tables_demoted_to_settings_developer_audit",
                "receipt_rows_demoted_to_settings_developer_audit",
                "runbooks_demoted_to_settings_developer_audit",
                "ltg_audit_surfaces_demoted_to_settings_developer_audit",
                "current_decision_surface_exception_reason_visible_when_detail_stays",
                "settings_developer_audit_link_visible_after_summary",
            ],
        )
        self.assertEqual(
            contract["forbidden_audit_demotion_evidence"],
            [
                "audit_table_before_user_summary",
                "receipt_rows_before_next_click",
                "runbook_before_source_state",
                "ltg_audit_as_default_page_body",
                "all_details_hidden_without_audit_link",
                "local_receipt_only",
                "docs_config_scaffold_only",
            ],
        )
        self.assertEqual(
            contract["task_creation_rule"],
            "audit_placement_display_never_creates_tasks",
        )
        self.assertEqual(
            contract["cache_write_rule"],
            "audit_placement_display_never_writes_cache_or_config",
        )
        self.assertEqual(
            contract["production_evidence_rule"],
            "ordinary_audit_placement_contract_is_not_production_evidence",
        )
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["provider_execution_implemented"])
        self.assertFalse(contract["model_execution_implemented"])
        self.assertFalse(contract["contains_secret"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertTrue(contract["does_not_modify_strategy_action"])

    def test_runtime_mode_policy_docs_reference_config_source(self):
        root = Path(__file__).resolve().parents[1]
        long_term_goals = (root / "docs" / "command_center_3_long_term_goals.md").read_text(
            encoding="utf-8"
        )
        migration_map = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")
        app_plan = (root / "docs" / "app_migration_plan.md").read_text(encoding="utf-8")
        architecture = (root / "docs" / "command_center_3_architecture.md").read_text(encoding="utf-8")
        handoff_protocol = (root / "docs" / "codex_handoff_protocol.md").read_text(
            encoding="utf-8"
        )

        for text in (long_term_goals, migration_map, architecture):
            self.assertIn("COMMAND_CENTER_RUNTIME_MODE_POLICIES", text)
            self.assertIn("COMMAND_CENTER_RUNTIME_MODES", text)
            self.assertIn("COMMAND_CENTER_DEFAULT_RUNTIME_MODE", text)

        for text in (long_term_goals, migration_map, app_plan):
            self.assertIn("COMMAND_CENTER_RUNTIME_MODE_CONFIG_CONTRACT", text)
            self.assertIn("get_command_center_runtime_mode_config_contract()", text)
            self.assertIn("redact_invalid_value_and_fallback_to_cache_only", text)
            self.assertIn("[invalid_redacted]", text)
            self.assertIn("read_only_mode_banner_no_frontend_edit_or_writeback", text)
            self.assertIn("reserved_disabled_requires_separate_authorization", text)
            self.assertIn("runtime_config_contract_is_not_production_evidence", text)
            self.assertIn("COMMAND_CENTER_LIVE_LIGHT_BOOTSTRAP_TASK_CONTRACT", text)
            self.assertIn("get_command_center_live_light_bootstrap_task_contract()", text)
            self.assertIn("after_initial_cache_render_only", text)
            self.assertIn(
                "create_or_reuse_one_rate_limited_local_task_after_cache_render",
                text,
            )
            self.assertIn("one_active_or_recent_task_per_session_and_rate_window", text)
            self.assertIn(
                "future_provider_model_execution_requires_execution_request_and_ledgers",
                text,
            )
            self.assertIn("bootstrap_task_contract_is_not_execution_or_production_evidence", text)
            self.assertIn("COMMAND_CENTER_SEARCH_QUANT_PROJECTION_TASK_CONTRACT", text)
            self.assertIn("get_command_center_search_quant_projection_task_contract()", text)
            self.assertIn("explicit_confirmed_symbol_submit_or_live_light_safe_submit", text)
            self.assertIn(
                "manual_explicit_button_or_live_light_effective_search_submit_autostart",
                text,
            )
            self.assertIn(
                "confirmed_single_a_share_symbol_normalize_suffix_and_drop_raw_query",
                text,
            )
            self.assertIn("create_or_reuse_local_quant_projection_receipt_task_only", text)
            self.assertIn(
                "provider_model_acceptance_requires_dry_run_execution_request_and_ledgers",
                text,
            )
            self.assertIn(
                "search_quant_projection_contract_is_not_provider_model_or_production_evidence",
                text,
            )
            self.assertIn("COMMAND_CENTER_DAILY_COMMAND_ORDINARY_WORKFLOW_CONTRACT", text)
            self.assertIn("get_command_center_daily_command_ordinary_workflow_contract()", text)
            self.assertIn("daily_command_center_shows_today_summary_before_engineering_detail", text)
            self.assertIn("daily_summary_missing_evidence_must_be_visible", text)
            self.assertIn("last_successful_daily_cache_must_remain_visible", text)
            self.assertIn("provider_health_detail_moves_to_settings_config_health_or_audit", text)
            self.assertIn("daily_command_center_ordinary_workflow_never_creates_tasks_on_render", text)
            self.assertIn(
                "daily_command_center_ordinary_workflow_contract_is_not_provider_model_or_production_evidence",
                text,
            )
            self.assertIn("COMMAND_CENTER_STOCK_QUANT_PROJECTION_ORDINARY_WORKFLOW_CONTRACT", text)
            self.assertIn("get_command_center_stock_quant_projection_ordinary_workflow_contract()", text)
            self.assertIn("confirmed_single_a_share_symbol_required_before_submit", text)
            self.assertIn("search_typing_never_creates_task_or_provider_model_call", text)
            self.assertIn("render_cache_then_show_task_status_and_last_successful_result", text)
            self.assertIn(
                "missing_provider_model_factor_next_echarts_or_browser_evidence_must_be_visible",
                text,
            )
            self.assertIn("stock_quant_projection_ordinary_workflow_never_creates_tasks_on_typing_or_render", text)
            self.assertIn(
                "stock_quant_projection_ordinary_workflow_contract_is_not_provider_model_or_production_evidence",
                text,
            )
            self.assertIn(
                "stock_quant_projection_user_usable_entry_requires_confirmed_symbol_cache_task_status_and_research_boundary",
                text,
            )
            self.assertIn(
                "stock_quant_projection_cannot_promote_from_search_typing_ai_text_or_local_receipt_only",
                text,
            )
            self.assertIn("confirmed_single_a_share_symbol_visible", text)
            self.assertIn("generate_3_0_quant_projection_button_or_disabled_reason_visible", text)
            self.assertIn("cache_result_or_last_successful_result_visible", text)
            self.assertIn("task_status_visible_after_submit", text)
            self.assertIn("provider_model_cache_pending_state_visible", text)
            self.assertIn("factor_next_echarts_or_browser_missing_evidence_visible", text)
            self.assertIn("deepseek_explanation_status_is_optional_and_explanation_only_visible", text)
            self.assertIn("research_only_no_buy_sell_or_strategy_action_boundary_visible", text)
            self.assertIn("search_typing_only", text)
            self.assertIn("ai_text_as_action_only", text)
            self.assertIn("legacy_single_stock_room_ui_parity_only", text)
            self.assertIn("COMMAND_CENTER_CANDIDATE_RADAR_ORDINARY_WORKFLOW_CONTRACT", text)
            self.assertIn("get_command_center_candidate_radar_ordinary_workflow_contract()", text)
            self.assertIn("quick_scan_must_be_button_gated_post_task_or_local_fallback", text)
            self.assertIn("last_radar_cache_visible_before_scan_action", text)
            self.assertIn(
                "missing_full_pool_deep_scan_browser_ci_or_provider_evidence_must_be_visible",
                text,
            )
            self.assertIn(
                "candidate_radar_user_usable_entry_requires_cache_scope_source_gap_and_no_buy_boundary",
                text,
            )
            self.assertIn("candidate_radar_cannot_promote_from_legacy_ui_or_local_receipt_only", text)
            self.assertIn("last_radar_cache_visible", text)
            self.assertIn("scan_scope_and_candidate_pool_source_visible", text)
            self.assertIn("top_watch_excluded_groups_visible", text)
            self.assertIn("provider_cache_pending_or_degraded_state_visible", text)
            self.assertIn("candidate_is_not_buy_instruction_visible", text)
            self.assertIn("quick_scan_button_or_disabled_reason_visible", text)
            self.assertIn("old_streamlit_radar_ui_parity_only", text)
            self.assertIn("legacy_fallback_path_only", text)
            self.assertIn("browser_artifact_without_provider_or_worker_evidence", text)
            self.assertIn("candidate_radar_ordinary_workflow_never_creates_tasks_on_render", text)
            self.assertIn(
                "candidate_radar_ordinary_workflow_contract_is_not_production_replacement_evidence",
                text,
            )
            self.assertIn("COMMAND_CENTER_ORDINARY_WORKFLOW_REGISTRY_CONTRACT", text)
            self.assertIn("get_command_center_ordinary_workflow_registry_contract()", text)
            self.assertIn("three_ordinary_entrances_are_the_primary_user_workflow", text)
            self.assertIn("ordinary_registry_rows_appear_before_settings_developer_audit", text)
            self.assertIn(
                (
                    "each_registered_entrance_shows_next_click_source_state_missing_evidence_"
                    "research_boundary_blocked_degraded_and_last_successful_result"
                ),
                text,
            )
            self.assertIn("ordinary_workflow_registry_never_creates_tasks", text)
            self.assertIn("ordinary_workflow_registry_contract_is_not_production_evidence", text)
            self.assertIn("COMMAND_CENTER_ORDINARY_SOURCE_STATE_DISPLAY_CONTRACT", text)
            self.assertIn("get_command_center_ordinary_source_state_display_contract()", text)
            self.assertIn("provider_model_cache_pending_states_must_be_visible_in_ordinary_summary", text)
            self.assertIn("tushare_state_requires_call_ledger_or_provider_pending_marker", text)
            self.assertIn("deepseek_state_is_explanation_only_with_model_ledger_or_pending_marker", text)
            self.assertIn("cache_state_must_show_freshness_and_last_successful_pointer", text)
            self.assertIn("pending_state_must_name_missing_evidence_or_next_allowed_task", text)
            self.assertIn(
                "ordinary_source_state_page_visibility_requires_provider_model_cache_pending_last_successful_and_blocker_rows",
                text,
            )
            self.assertIn(
                "ordinary_source_state_cannot_promote_from_hidden_tabs_tooltips_or_engineering_tables_only",
                text,
            )
            self.assertIn("source_state_visible_in_ordinary_summary", text)
            self.assertIn("cache_freshness_and_last_successful_pointer_visible", text)
            self.assertIn("tushare_call_ledger_or_provider_pending_marker_visible", text)
            self.assertIn("deepseek_model_ledger_or_pending_marker_visible", text)
            self.assertIn("pending_missing_evidence_or_next_allowed_task_visible", text)
            self.assertIn("degraded_blocker_and_safe_fallback_visible", text)
            self.assertIn("no_trade_no_action_boundary_visible_next_to_state", text)
            self.assertIn("settings_developer_audit_link_for_detail_visible", text)
            self.assertIn("engineering_audit_table_only", text)
            self.assertIn("settings_detail_only", text)
            self.assertIn("tooltip_only", text)
            self.assertIn("hidden_tab_only", text)
            self.assertIn("ordinary_source_state_display_never_creates_tasks", text)
            self.assertIn(
                "ordinary_source_state_display_contract_is_not_provider_model_or_production_evidence",
                text,
            )
            self.assertIn("COMMAND_CENTER_ORDINARY_SOURCE_STATE_CONTRACT", text)
            self.assertIn("get_command_center_ordinary_source_state_contract()", text)
            self.assertIn("read_only_source_state_chips_in_ordinary_summary", text)
            self.assertIn(
                "provider_backed_or_provider_pending_market_data_with_call_ledger_status",
                text,
            )
            self.assertIn(
                "explanation_only_model_output_never_data_source_or_action_writer",
                text,
            )
            self.assertIn("pending_or_degraded_state_must_show_missing_evidence_or_blocker", text)
            self.assertIn("source_state_chips_never_create_tasks", text)
            self.assertIn("source_state_chips_never_write_cache_or_config", text)
            self.assertIn("source_state_contract_is_not_provider_model_or_production_evidence", text)
            self.assertIn("COMMAND_CENTER_ORDINARY_NEXT_CLICK_CONTRACT", text)
            self.assertIn("get_command_center_ordinary_next_click_contract()", text)
            self.assertIn("one_primary_safe_action_per_ordinary_entrance", text)
            self.assertIn("disabled_or_degraded_reason_visible_before_click", text)
            self.assertIn("work_creating_next_click_must_use_post_task_worker_or_local_fallback", text)
            self.assertIn("work_creating_next_click_must_show_task_status", text)
            self.assertIn("next_click_is_research_only_no_buy_sell_instruction", text)
            self.assertIn("ordinary_next_click_contract_is_not_execution_or_production_evidence", text)
            self.assertIn("COMMAND_CENTER_ORDINARY_RESEARCH_BOUNDARY_CONTRACT", text)
            self.assertIn("get_command_center_ordinary_research_boundary_contract()", text)
            self.assertIn("research_only_not_buy_sell_instruction", text)
            self.assertIn("show_research_only_boundary_in_ordinary_summary", text)
            self.assertIn("deepseek_text_is_explanation_only_not_data_source_or_action", text)
            self.assertIn("factor_scores_are_research_evidence_not_trade_action", text)
            self.assertIn("operation_zones_are_conditions_not_orders", text)
            self.assertIn("never_modify_strategy_action_prices_positions_factors_or_operation_zones", text)
            self.assertIn("research_boundary_contract_is_not_execution_or_production_evidence", text)
            self.assertIn("COMMAND_CENTER_ORDINARY_EVIDENCE_FALLBACK_CONTRACT", text)
            self.assertIn("get_command_center_ordinary_evidence_fallback_contract()", text)
            self.assertIn("missing_evidence_must_be_visible_before_action", text)
            self.assertIn("blocked_state_must_show_blocker_and_allowed_next_step", text)
            self.assertIn("degraded_state_must_show_stale_failed_or_partial_source", text)
            self.assertIn("last_successful_cache_or_result_must_remain_visible_as_fallback", text)
            self.assertIn("fallback_is_display_only_not_current_provider_model_evidence", text)
            self.assertIn("evidence_fallback_display_never_creates_tasks", text)
            self.assertIn("evidence_fallback_contract_is_not_provider_model_or_production_evidence", text)
            self.assertIn("COMMAND_CENTER_LEGACY_AUDIT_CLASSIFICATION_CONTRACT", text)
            self.assertIn("get_command_center_legacy_audit_classification_contract()", text)
            self.assertIn("keep_requires_direct_legacy_bug_ux_audit_evidence", text)
            self.assertIn("seed_inventory_receipt_matrix_or_docs_config_cannot_promote_keep", text)
            self.assertIn("direct_evidence_row_required_before_keep_or_ordinary_entry", text)
            self.assertIn("seed_only_rows_default_to_redesign_legacy_debug_or_retire", text)
            self.assertIn(
                "unclear_data_lineage_blocks_ordinary_entry_until_redesigned_or_frozen",
                text,
            )
            self.assertIn("audit_scope_tracks_workflow_group_not_legacy_file_or_tab_count", text)
            self.assertIn("ordinary_entry_requires_replacement_entrance_and_frozen_legacy_path", text)
            self.assertIn("keep_requires_direct_evidence_and_no_open_bug_or_lineage_blocker", text)
            self.assertIn("redesign_requires_replacement_workflow_before_ordinary_entry", text)
            self.assertIn("seed_only_cannot_transition_to_keep", text)
            self.assertIn(
                "direct_evidence_ready_can_transition_to_keep_only_with_all_required_fields",
                text,
            )
            self.assertIn(
                "blocked_by_lineage_transitions_to_redesign_legacy_debug_or_retire",
                text,
            )
            self.assertIn(
                "known_bug_or_patchwork_without_replacement_stays_redesign_or_retire",
                text,
            )
            self.assertIn("legacy_debug_and_retire_do_not_enter_ordinary_user_flow", text)
            self.assertIn("REDESIGN_WITH_REPLACEMENT_READY", text)
            self.assertIn("REDESIGN_WITHOUT_REPLACEMENT_READY", text)
            self.assertIn(
                "streamlit_remains_fallback_admin_debug_until_react_tauri_workflow_is_easier_clearer_more_reliable",
                text,
            )
            self.assertIn("streamlit_must_not_be_primary_3_0_runtime_or_target_ux", text)
            self.assertIn(
                "fallback_retirement_requires_replacement_workflow_direct_evidence_and_rollback_plan",
                text,
            )
            self.assertIn("react_tauri_replacement_workflow_ready", text)
            self.assertIn("ordinary_entry_easier_clearer_more_reliable_evidence", text)
            self.assertIn("rollback_or_admin_debug_path_retained_until_promotion", text)
            self.assertIn("streamlit_ui_polish_only", text)
            self.assertIn("stage_scope_manifest_only", text)
            self.assertIn("direct_evidence_ready", text)
            self.assertIn("blocked_by_lineage", text)
            self.assertIn("route_inventory_only", text)
            self.assertIn("mock_sanitizer_or_preflight_only", text)
            self.assertIn(
                "legacy_audit_row_requires_scope_status_direct_source_lineage_replacement_and_freeze_decision",
                text,
            )
            self.assertIn("workflow_group", text)
            self.assertIn("legacy_surface_or_module", text)
            self.assertIn("direct_ux_bug_evidence_source", text)
            self.assertIn("ordinary_entry_decision", text)
            self.assertIn("next_action", text)
            self.assertIn("file_inventory_only", text)
            self.assertIn("legacy_tab_count_only", text)
            self.assertIn("route_exists_only", text)
            self.assertIn("legacy_audit_seed_rows_cover_ordinary_workflow_scope_without_keep_promotion", text)
            self.assertIn("legacy_audit_seed_rows_are_not_direct_evidence_or_production_evidence", text)
            self.assertIn("streamlit_home_daily_summary", text)
            self.assertIn("legacy_single_stock_room_quant_projection", text)
            self.assertIn("legacy_candidate_radar", text)
            self.assertIn("legacy_next_session_chart", text)
            self.assertIn("legacy_factor_risk_provider_health_tables", text)
            self.assertIn("legacy_discipline_backtest_lab", text)
            self.assertIn("legacy_margin_etf_leverage_flow", text)
            self.assertIn("legacy_external_brain_ai_advisor", text)
            self.assertIn("not_promoted_seed_only", text)
            self.assertIn("not_promoted_legacy_debug", text)
            self.assertIn("not_promoted_retire", text)
            self.assertIn("legacy_audit_classification_contract_is_not_production_evidence", text)
            self.assertIn("COMMAND_CENTER_MIGRATION_CHECKPOINT_CONTRACT", text)
            self.assertIn("get_command_center_migration_checkpoint_contract()", text)
            self.assertIn("every_future_migration_checkpoint_must_answer_five_questions", text)
            self.assertIn("what_user_capability_was_preserved", text)
            self.assertIn("what_legacy_ux_problem_was_removed", text)
            self.assertIn("what_legacy_bug_or_patchwork_path_was_not_migrated", text)
            self.assertIn("what_became_simpler_for_nontechnical_user", text)
            self.assertIn("which_real_blocker_was_reduced", text)
            self.assertIn("fix_push_gate_ci_evidence", text)
            self.assertIn("legacy_bug_ux_audit_for_streamlit_ordinary_workflows", text)
            self.assertIn("rebuild_ltg13_candidate_radar_user_usable_workflow", text)
            self.assertIn("searched_symbol_to_generate_3_0_quant_projection", text)
            self.assertIn("show_provider_model_cache_pending_state_on_page", text)
            self.assertIn("move_engineering_audit_tables_out_of_ordinary_flow", text)
            self.assertIn(
                "future_migration_slices_follow_current_priority_order_or_name_blocker_exception",
                text,
            )
            self.assertIn(
                "remote_ci_unverified_remains_release_blocker_until_current_green_or_reviewed_logs",
                text,
            )
            self.assertIn("matching_head_sha_or_commit", text)
            self.assertIn("current_remote_actions_green_or_failed_step_reviewed", text)
            self.assertIn("fresh_local_push_gate_result_for_current_head", text)
            self.assertIn("safe_failure_log_excerpt_or_green_run_url", text)
            self.assertIn("explicit_user_push_confirmation_before_push", text)
            self.assertIn("local_unit_tests_only", text)
            self.assertIn("checkpoint_answer_only", text)
            self.assertIn("static_workflow_file_presence_only", text)
            self.assertIn("ci_failure_email_without_matching_run_logs", text)
            self.assertIn("old_remote_green_run_for_different_head", text)
            self.assertIn("local_receipt_or_stage_scope_manifest_only", text)
            self.assertIn(
                "remote_ci_review_row_requires_head_status_log_local_gate_push_decision",
                text,
            )
            self.assertIn("remote_run_url_or_id", text)
            self.assertIn("remote_status", text)
            self.assertIn("failed_step_or_green_status", text)
            self.assertIn("local_gate_result_for_same_head", text)
            self.assertIn("push_confirmation_state", text)
            self.assertIn("release_claim_decision", text)
            self.assertIn("old_run_without_matching_head", text)
            self.assertIn("email_subject_only", text)
            self.assertIn("local_gate_pass_only", text)
            self.assertIn("workflow_yaml_presence_only", text)
            self.assertIn("unreviewed_failed_step", text)
            self.assertIn("unchecked_artifact_or_secret_scan", text)
            self.assertIn(
                "remote_ci_review_seed_row_keeps_p0_blocked_until_matching_remote_run_review",
                text,
            )
            self.assertIn("pending_current_head_sha", text)
            self.assertIn("pending_remote_actions_run", text)
            self.assertIn("remote_ci_unverified", text)
            self.assertIn("not_reviewed", text)
            self.assertIn("pending_fresh_local_push_gate_for_current_head", text)
            self.assertIn("not_requested_no_push", text)
            self.assertIn("blocked_remote_ci_unverified", text)
            self.assertIn(
                "release_or_production_replacement_claim_requires_current_remote_ci_green_or_reviewed_failure_logs",
                text,
            )
            self.assertIn("push_requires_explicit_user_confirmation_after_local_gate_review", text)
            self.assertIn("ci_checkpoint_contract_never_calls_github_or_fetches_actions_logs", text)
            self.assertIn("treating_local_gate_or_checkpoint_as_remote_ci_green", text)
            self.assertIn(
                "legacy_bug_ux_audit_precedes_major_ordinary_workflow_migration",
                text,
            )
            self.assertIn(
                "ordinary_user_workflow_slices_precede_extra_engineering_scaffold",
                text,
            )
            self.assertIn(
                "broad_contract_receipt_runbook_or_manifest_requires_named_release_blocker",
                text,
            )
            self.assertIn("migration_checkpoint_contract_is_not_production_evidence", text)
            self.assertIn("COMMAND_CENTER_ORDINARY_AUDIT_PLACEMENT_CONTRACT", text)
            self.assertIn("get_command_center_ordinary_audit_placement_contract()", text)
            self.assertIn("ordinary_pages_show_user_summary_before_engineering_audit_details", text)
            self.assertIn(
                "ordinary_entry_promotion_requires_user_summary_fields_before_engineering_detail",
                text,
            )
            self.assertIn(
                "ordinary_first_view_shows_next_click_state_gaps_boundary_and_last_success_before_audit",
                text,
            )
            self.assertIn("next_click_visible_before_audit_detail", text)
            self.assertIn("source_state_visible_before_audit_detail", text)
            self.assertIn("missing_evidence_visible_before_audit_detail", text)
            self.assertIn("research_only_boundary_visible_before_audit_detail", text)
            self.assertIn("last_successful_cache_or_result_visible_before_audit_detail", text)
            self.assertIn("settings_developer_audit_link_visible_for_details", text)
            self.assertIn("engineering_contract_table_as_primary_surface", text)
            self.assertIn("receipt_rows_as_primary_surface", text)
            self.assertIn("legacy_route_inventory_as_primary_surface", text)
            self.assertIn("detailed_engineering_audit_tables_move_to_settings_developer_audit", text)
            self.assertIn("engineering_contract_tables_must_not_dominate_ordinary_pages", text)
            self.assertIn("ordinary_first_view_must_not_be_engineering_audit_dashboard", text)
            self.assertIn("ordinary_summary_rendered_before_any_engineering_table", text)
            self.assertIn("engineering_contract_tables_demoted_to_settings_developer_audit", text)
            self.assertIn("receipt_rows_demoted_to_settings_developer_audit", text)
            self.assertIn("runbooks_demoted_to_settings_developer_audit", text)
            self.assertIn("ltg_audit_surfaces_demoted_to_settings_developer_audit", text)
            self.assertIn("current_decision_surface_exception_reason_visible_when_detail_stays", text)
            self.assertIn("settings_developer_audit_link_visible_after_summary", text)
            self.assertIn("audit_table_before_user_summary", text)
            self.assertIn("receipt_rows_before_next_click", text)
            self.assertIn("runbook_before_source_state", text)
            self.assertIn("ltg_audit_as_default_page_body", text)
            self.assertIn("all_details_hidden_without_audit_link", text)
            self.assertIn("audit_placement_display_never_creates_tasks", text)
            self.assertIn("ordinary_audit_placement_contract_is_not_production_evidence", text)

        self.assertIn("get_command_center_runtime_mode_state()", long_term_goals)
        self.assertIn("runtime_mode_policy_rows", migration_map)
        self.assertIn("runtime_mode_policy_rows", architecture)
        self.assertIn("page_open_rule", migration_map)
        self.assertIn("search_submit_rule", migration_map)
        self.assertIn("external-call、task-creation、startup、page-open 和 search-submit", migration_map)
        self.assertIn("page open 和 confirmed search submit 是 mode-specific trigger surfaces", migration_map)
        self.assertIn("不是 render/search-typing 副作用", migration_map)
        self.assertIn("page_open_rule", app_plan)
        self.assertIn("search_submit_rule", app_plan)
        self.assertIn("config wording, not frontend wiring", app_plan)
        self.assertIn("page open and safe searched-symbol submit are mode-specific trigger surfaces", app_plan)
        self.assertIn("search typing, React render, FastAPI startup, GET cache", app_plan)
        self.assertIn("page_open_rule", architecture)
        self.assertIn("search_submit_rule", architecture)
        self.assertIn("page-open / search-submit", architecture)
        self.assertIn("page open 和 confirmed search submit 是 mode-specific trigger surfaces", architecture)
        self.assertIn("不是 render/search-typing 副作用", architecture)
        self.assertIn("page_open_rule", handoff_protocol)
        self.assertIn("search_submit_rule", handoff_protocol)
        self.assertIn(
            "page open and confirmed search submit remain mode-specific trigger surfaces",
            handoff_protocol,
        )
        self.assertIn("render/search-typing side effects", handoff_protocol)
        for field in (
            "cache_get_rule",
            "react_render_rule",
            "ledger_rule",
            "ordinary_entrance_visibility_rule",
            "ordinary_mode_banner_rule",
            "production_evidence_rule",
        ):
            self.assertIn(field, architecture)
        self.assertIn("GET/cache 与 React render 只读", architecture)
        self.assertIn("普通入口要在 Settings / Developer / Audit 之前显示 `任务边界`", architecture)
        self.assertIn("ordinary mode banner 只读显示运行模式", architecture)
        self.assertIn("config policy row 不是 production evidence", architecture)
        self.assertIn("不创建 task、不写配置、不调用 Tushare/DeepSeek/GitHub", architecture)
        self.assertIn("不能提升完整 `live_light` 完成度", architecture)

    def test_legacy_migration_docs_use_mode_layered_automation_language(self):
        root = Path(__file__).resolve().parents[1]
        docs = [
            (root / "docs" / "codex_handoff_protocol.md").read_text(encoding="utf-8"),
            (root / "docs" / "app_migration_plan.md").read_text(encoding="utf-8"),
        ]
        old_absolute_phrases = (
            "DeepSeek must not run automatically when a page opens",
            "Tushare cross-sectional scans must not run automatically when a page opens",
            "DeepSeek must never run automatically",
            "Full-market scans must never run automatically",
            "Tushare cross-section scans must never run automatically",
        )

        for text in docs:
            for phrase in old_absolute_phrases:
                self.assertNotIn(phrase, text)
            self.assertIn("cache_only", text)
            self.assertIn("manual", text)
            self.assertIn("live_light", text)
            self.assertIn("POST task", text)

    def test_model_strategy_reference_helper_is_configurable_and_secret_free(self):
        os.environ["DEEPSEEK_DEFAULT_MODEL"] = "custom-default"
        os.environ["DEEPSEEK_EXPLAIN_MODEL"] = "custom-explain"

        factor_ref = model_strategy_service.build_deepseek_model_strategy_ref("factor_explain")
        fallback_ref = model_strategy_service.build_deepseek_model_strategy_ref("unknown-purpose")

        self.assertEqual(factor_ref["purpose"], "factor_explain")
        self.assertEqual(factor_ref["model"], "custom-explain")
        self.assertIn("DEEPSEEK_EXPLAIN_MODEL", factor_ref["config_keys"])
        self.assertEqual(factor_ref["active_config_key"], "DEEPSEEK_EXPLAIN_MODEL")
        self.assertTrue(factor_ref["uses_configured_value"])
        self.assertTrue(factor_ref["does_not_hardcode_model"])
        self.assertFalse(factor_ref["contains_secret"])

        self.assertEqual(fallback_ref["purpose"], "default")
        self.assertEqual(fallback_ref["model"], "custom-default")
        self.assertIn("DEEPSEEK_DEFAULT_MODEL", fallback_ref["config_keys"])

    def test_projection_merges_default_to_configured_model(self):
        os.environ["DEEPSEEK_EXPLAIN_MODEL"] = "custom-projection-model"

        packet = projection.merge_deepseek_projection_overlay(
            {"paths": [{"name": "乐观路径"}, {"name": "中性路径"}, {"name": "谨慎路径"}]},
            {"paths": []},
            raw_text="{}",
        )
        self.assertEqual(packet["deepseek_projection"]["model"], "custom-projection-model")

        next_packet = next_session_projection.merge_deepseek_next_session_projection(
            {"packet_key": "command_center_next_session_projection_packet"},
            "{}",
        )
        self.assertEqual(next_packet["deepseek_synthesis"]["model"], "custom-projection-model")

    def test_deepseek_model_names_are_centralized_outside_docs_and_tests(self):
        root = Path(__file__).resolve().parents[1]
        allowed = {
            root / "config.py",
            Path(__file__).resolve(),
            root / "docs" / "command_center_3_architecture.md",
        }
        source_suffixes = {".py", ".ts", ".tsx", ".js", ".jsx"}
        model_literal_pattern = re.compile(
            r"\bdeepseek-(?:v\d+[a-z0-9_-]*|chat|reasoner|coder)\b",
            re.IGNORECASE,
        )
        offenders = []

        for path in root.rglob("*"):
            if path in allowed or path.suffix not in source_suffixes:
                continue
            if any(part in {".git", ".venv", "__pycache__", "node_modules", "dist"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in model_literal_pattern.finditer(text):
                offenders.append(f"{path.relative_to(root)} contains {match.group(0)}")

        self.assertEqual(offenders, [])

    def test_chat_completion_calls_use_configured_deepseek_model(self):
        root = Path(__file__).resolve().parents[1]
        offenders = []

        def attr_chain(node):
            parts = []
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return list(reversed(parts))

        for path in root.rglob("*.py"):
            if any(part in {".git", ".venv", "__pycache__", "node_modules", "dist"} for part in path.parts):
                continue
            if path.parts[-2:-1] == ("tests",):
                continue

            text = path.read_text(encoding="utf-8", errors="ignore")
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                offenders.append(f"{path.relative_to(root)} cannot be parsed: {exc}")
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                chain = attr_chain(node.func)
                if chain[-3:] != ["chat", "completions", "create"]:
                    continue

                model_keywords = [kw for kw in node.keywords if kw.arg == "model"]
                if model_keywords:
                    for keyword in model_keywords:
                        value_source = ast.get_source_segment(text, keyword.value) or ""
                        if "get_deepseek_model(" not in value_source:
                            offenders.append(
                                f"{path.relative_to(root)}:{node.lineno} model is not from get_deepseek_model"
                            )
                    continue

                has_kwargs = any(kw.arg is None for kw in node.keywords)
                if has_kwargs and (
                    '"model": get_deepseek_model(' in text or "'model': get_deepseek_model(" in text
                ):
                    continue

                offenders.append(f"{path.relative_to(root)}:{node.lineno} missing configured model keyword")

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
