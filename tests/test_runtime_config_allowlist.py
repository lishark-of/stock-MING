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
            self.assertEqual(row["production_evidence_rule"], "config_policy_row_is_not_production_evidence")

        self.assertEqual(rows["cache_only"]["external_call_rule"], "none")
        self.assertEqual(rows["manual"]["external_call_rule"], "explicit_post_task_only")
        self.assertEqual(rows["live_light"]["task_creation_rule"], "after_cache_render_rate_limited_local_task_only")
        self.assertEqual(rows["live_full"]["startup_rule"], "reserved_no_startup_task")

    def test_runtime_mode_config_contract_is_not_execution_evidence(self):
        contract = config.get_command_center_runtime_mode_config_contract()

        self.assertEqual(contract["config_key"], "COMMAND_CENTER_BOOTSTRAP_MODE")
        self.assertEqual(contract["default_mode"], "cache_only")
        self.assertEqual(contract["allowed_modes"], ["cache_only", "manual", "live_light", "live_full"])
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
        self.assertIn("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT = false", text)
        self.assertIn("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL = false", text)
        self.assertIn("cache_only is the safe default", text)
        self.assertIn("live_light must remain opt-in and task/ledger governed", text)
        self.assertIn("live_full: reserved and disabled until separate authorization", text)
        self.assertIn("config rows are operator guidance, not production evidence or frontend secrets", text)
        self.assertIn("A configured true value is operator intent only", text)
        self.assertIn(
            "Effective external work still requires mode/task gates, ledgers, redaction, and promotion",
            text,
        )
        self.assertIn(
            "Runtime config does not prove the full live_light workflow has been implemented",
            text,
        )


if __name__ == "__main__":
    unittest.main()
