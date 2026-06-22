import unittest
from pathlib import Path

import config


class HandoffRuntimeCycleScopeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.protocol = (self.root / "docs" / "codex_handoff_protocol.md").read_text(
            encoding="utf-8"
        )
        self.goals = (self.root / "docs" / "command_center_3_long_term_goals.md").read_text(
            encoding="utf-8"
        )
        self.example = (self.root / ".streamlit" / "secrets.example.toml").read_text(
            encoding="utf-8"
        )

    def test_docs_config_cycles_stay_small_and_checkpointed(self):
        self.assertIn(
            "at most one main target and one supporting target",
            self.protocol,
        )
        self.assertIn("modify no more than five files", self.protocol)
        self.assertIn("end with a `Checkpoint`", self.protocol)
        self.assertIn("Cycle scope: main target, supporting target, changed file count", self.protocol)
        self.assertIn("Migration checkpoint answers", self.protocol)

        for question in (
            "What user capability was preserved",
            "What legacy UX problem was removed",
            "Which legacy bug or patchwork path was intentionally not migrated",
            "What became simpler for a non-technical user",
            "Which real blocker was reduced",
        ):
            self.assertIn(question, self.protocol)

    def test_runtime_wording_cycles_cannot_claim_live_light_implementation(self):
        self.assertIn(
            "Docs/config/runtime-mode wording cycles may define the mode vocabulary",
            self.protocol,
        )
        self.assertIn("not a full `live_light` implementation", self.protocol)
        self.assertIn("not a provider/model executor", self.protocol)
        self.assertIn("not frontend wiring completion", self.protocol)
        self.assertIn("not production acceptance evidence", self.protocol)
        self.assertIn("Production-evidence boundary", self.protocol)

    def test_runtime_mode_config_source_matches_documented_operator_defaults(self):
        self.assertEqual(
            config.COMMAND_CENTER_RUNTIME_MODES,
            ("cache_only", "manual", "live_light", "live_full"),
        )
        self.assertEqual(config.COMMAND_CENTER_DEFAULT_RUNTIME_MODE, "cache_only")
        self.assertIn(
            "`cache_only` remains the safe default for smoke, CI, quick reads",
            self.goals,
        )
        self.assertIn("`manual` is the explicit-control mode", self.goals)
        self.assertIn("`live_full` is a reserved vocabulary item", self.goals)

        self.assertIn('COMMAND_CENTER_BOOTSTRAP_MODE = "cache_only"', self.example)
        self.assertIn("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART = false", self.example)
        self.assertIn("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART = false", self.example)
        self.assertIn("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT = false", self.example)
        self.assertIn("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT = false", self.example)
        self.assertIn("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL = false", self.example)

    def test_mode_policy_rows_keep_external_work_task_gated(self):
        rows = {row["mode"]: row for row in config.get_command_center_runtime_mode_policies()}

        for mode in ("cache_only", "manual", "live_light", "live_full"):
            self.assertEqual(
                rows[mode]["fastapi_startup_rule"],
                "no_provider_model_worker_trade_or_task_creation",
            )
            self.assertEqual(
                rows[mode]["search_typing_rule"],
                "no_task_provider_model_call_config_write_or_cache_write",
            )
            self.assertEqual(
                rows[mode]["cache_get_rule"],
                "read_only_no_provider_model_worker_or_trade",
            )
            self.assertEqual(
                rows[mode]["react_render_rule"],
                "read_only_no_provider_model_worker_or_trade",
            )
            self.assertEqual(
                rows[mode]["effective_external_call_rule"],
                "effective_external_call_requires_mode_task_gate_ledgers_redaction_and_promotion",
            )

        self.assertEqual(rows["cache_only"]["external_call_rule"], "none")
        self.assertEqual(rows["manual"]["external_call_rule"], "explicit_post_task_only")
        self.assertEqual(
            rows["live_light"]["task_creation_rule"],
            "after_cache_render_rate_limited_local_task_only",
        )
        self.assertEqual(rows["live_full"]["task_creation_rule"], "disabled_until_separate_authorization")


if __name__ == "__main__":
    unittest.main()
