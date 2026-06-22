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
        self.assertIn("every checkpoint cycle, including UI/frontend, docs/config, tests, and scaffold slices", self.protocol)
        self.assertIn(
            "at most one main target and one supporting target",
            self.protocol,
        )
        self.assertIn("modify no more than five files", self.protocol)
        self.assertIn("end with a `Checkpoint`", self.protocol)
        self.assertIn("Larger work must be split into separate cycles", self.protocol)
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
        self.assertIn("Runtime automation is mode-layered, not an absolute startup ban", self.protocol)
        self.assertIn("Runtime layer wording", self.protocol)
        self.assertIn("do not summarize the boundary as either flat startup prohibition or hidden automation", self.protocol)
        self.assertIn("initial cache/render/startup/search-typing silence", self.protocol)
        self.assertIn("local POST task creation/reuse", self.protocol)
        self.assertIn("real provider/model execution inside the task", self.protocol)
        self.assertIn("production promotion evidence are separate checkpoints", self.protocol)
        self.assertIn("not a full `live_light` implementation", self.protocol)
        self.assertIn("not a provider/model executor", self.protocol)
        self.assertIn("not frontend wiring completion", self.protocol)
        self.assertIn("not production acceptance evidence", self.protocol)
        self.assertIn("Production-evidence boundary", self.protocol)

    def test_push_gate_ci_rounds_keep_remote_ci_evidence_separate(self):
        self.assertIn("CI / release evidence boundary", self.protocol)
        self.assertIn(
            "evidence is only local validation or a matching current remote CI review",
            self.protocol,
        )
        self.assertIn(
            "Local tests, local push gate, static workflow files, checklist wording, receipts, and stage-scope rows are not remote CI evidence",
            self.protocol,
        )
        self.assertIn("Release or production-replacement claims remain blocked", self.protocol)
        self.assertIn("matching head SHA/commit with current GitHub Actions green status", self.protocol)
        self.assertIn("reviewed failure logs", self.protocol)
        self.assertIn("explicit user push confirmation before any push", self.protocol)
        self.assertIn("Release gate status wording", self.protocol)
        self.assertIn("local_gate_ready_remote_ci_and_allowlist_pending", self.protocol)
        self.assertIn("remote_ci_review_required_for_release_gate_complete", self.protocol)
        self.assertIn(
            "`local_gate_ready=true` / `ci_mirror_ready=true` are shape evidence only, not release readiness",
            self.protocol,
        )
        self.assertIn("Remote CI unknown rule", self.protocol)
        self.assertIn(
            "if the user did not explicitly request GitHub/Actions inspection in the round",
            self.protocol,
        )
        self.assertIn("report remote CI status as unknown", self.protocol)
        self.assertIn("do not infer green, red, or release readiness", self.protocol)

    def test_release_hygiene_cleanup_respects_five_file_split_guard(self):
        self.assertIn("Release-hygiene cleanup is still subject to the same five-file cap", self.protocol)
        self.assertIn("If a P0 release/push-gate slice spans more than five touched files", self.protocol)
        self.assertIn("first report a split audit", self.protocol)
        self.assertIn("stage only the selected release-hygiene files or precise hunks", self.protocol)
        self.assertIn("leave unrelated dirty files out", self.protocol)
        self.assertIn("report remote CI as unknown", self.protocol)
        self.assertIn("matching remote Actions evidence", self.protocol)
        self.assertIn("must not use `tests/test_command_center_3_server.py` as a whole-file shortcut", self.protocol)
        for excluded_hunk_family in (
            "config as app_config",
            "LTG-08/LTG-10 ordinary wording",
            "task catalog count changes",
            "provider-model/bootstrap/live_light/search_quant/candidate-radar workflow hunks",
            "unrelated runtime-mode or ordinary-entrance implementation changes",
        ):
            self.assertIn(excluded_hunk_family, self.protocol)

    def test_p0_release_hygiene_first_slice_is_documented_without_whole_mixed_test_file(self):
        self.assertIn("The first release-hygiene cleanup slice must stay within the five-file cycle cap", self.goals)
        self.assertIn(".github/workflows/command-center-3-push-gate.yml", self.goals)
        self.assertIn("scripts/push_gate_3_0.sh", self.goals)
        self.assertIn("server/services/audit_service.py", self.goals)
        self.assertIn("tests/test_push_gate_migration_principle_guard.py", self.goals)
        self.assertIn("plus only the release-gate hunks in `tests/test_command_center_3_server.py`", self.goals)
        self.assertIn("tests/test_audit_gate_migration_principle_guard.py` remains the next release-hygiene guard slice", self.goals)
        self.assertIn("Do not stage the whole `tests/test_command_center_3_server.py` mixed diff", self.goals)
        for included_hunk_family in (
            "LTG-11 local release-gate helper/check-count update",
            "push-gate script/report/artifact-policy assertions",
            "local worktree/receipt boundary tests",
            "FastAPI release-gate readiness rows",
            "motion durable current-head local release-gate fixture",
        ):
            self.assertIn(included_hunk_family, self.goals)
        for excluded_hunk_family in (
            "unrelated runtime-mode",
            "provider-model",
            "bootstrap",
            "live_light",
            "search_quant",
            "candidate-radar",
            "ordinary-entry wording",
            "task-catalog hunks",
        ):
            self.assertIn(excluded_hunk_family, self.goals)

    def test_runtime_acceptance_scope_checkpoint_keeps_config_slice_narrow(self):
        self.assertIn("Runtime config acceptance scope checkpoint", self.protocol)
        self.assertIn("`runtime_mode_config_current_acceptance_scope`", self.protocol)
        self.assertIn("`runtime_mode_config_current_acceptance_rule`", self.protocol)
        self.assertIn("`runtime_mode_config_current_acceptance_excludes`", self.protocol)
        self.assertIn(
            "runtime_mode_vocabulary_config_rows_and_contract_tests_only",
            self.protocol,
        )
        self.assertIn(
            "docs_config_contract_evidence_only_not_live_light_implementation",
            self.protocol,
        )
        for excluded_surface in (
            "frontend_autostart_wiring",
            "provider_model_executor",
            "worker_dispatch",
            "cache_write_promotion",
            "production_acceptance",
        ):
            self.assertIn(excluded_surface, self.protocol)
        self.assertIn("checkpoint drift guards only", self.protocol)
        self.assertIn("cannot be reported as frontend autostart wiring", self.protocol)
        self.assertIn("provider/model execution", self.protocol)
        self.assertIn("worker dispatch", self.protocol)
        self.assertIn("cache-write promotion", self.protocol)
        self.assertIn("production acceptance evidence", self.protocol)

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

    def test_migration_map_binds_runtime_modes_to_ordinary_entrances_without_live_light_claim(self):
        migration_map = (self.root / "docs" / "migration_map.md").read_text(encoding="utf-8")

        self.assertIn("运行模式进入普通入口时按同一张迁移图解释", migration_map)
        self.assertIn("不是完整 `live_light` 实现", migration_map)
        self.assertIn("不新增 production evidence", migration_map)
        self.assertIn("不绕过 Legacy Bug / UX Audit", migration_map)
        for entrance in (
            "今日作战台 / Daily Command Center",
            "股票量化推演 / Stock Quant Projection",
            "下一票雷达 / Candidate Radar",
        ):
            self.assertIn(entrance, migration_map)
        for mode in ("`cache_only`", "`manual`", "`live_light`", "`live_full`"):
            self.assertIn(mode, migration_map)

        self.assertIn("FastAPI startup、GET cache/status、React render、search typing 都不创建 task", migration_map)
        self.assertIn("confirmed symbol 后点击 `生成 3.0 量化推演` 才能创建本地 task", migration_map)
        self.assertIn("safe searched-symbol submit 只能创建或复用本地 quant-projection task", migration_map)
        self.assertIn("provider/model 执行仍需 POST task / worker / local fallback", migration_map)
        self.assertIn("`call_ledger` / `model_ledger`", migration_map)
        self.assertIn("需要未来单独授权", migration_map)
        self.assertIn("不能成为 task launcher、config editor、provider/model executor、交易入口", migration_map)


if __name__ == "__main__":
    unittest.main()
