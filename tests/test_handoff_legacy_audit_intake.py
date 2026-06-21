import unittest
from pathlib import Path


class HandoffLegacyAuditIntakeTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.protocol = (root / "docs" / "codex_handoff_protocol.md").read_text(
            encoding="utf-8"
        )
        self.long_term_goals = (
            root / "docs" / "command_center_3_long_term_goals.md"
        ).read_text(encoding="utf-8")

    def test_handoff_requires_legacy_direct_evidence_intake_slots(self):
        self.assertIn("Legacy direct-evidence intake", self.protocol)
        for slot in (
            "user_observation",
            "legacy_ux_bug_or_patchwork",
            "data_lineage_observation",
            "replacement_user_path",
            "frozen_legacy_path",
            "evidence_attachment",
            "keep_promotion_decision",
        ):
            self.assertIn(slot, self.protocol)
        self.assertIn("Separate `inventory_or_scaffold_evidence` from `direct_user_evidence`", self.protocol)
        self.assertIn("tied to an observed user action/workflow problem", self.protocol)
        self.assertIn("the checkpoint must keep direct evidence pending", self.protocol)
        self.assertIn("must not promote `KEEP`", self.protocol)
        self.assertIn("Legacy evidence attachment safety", self.protocol)
        self.assertIn("safe screenshot reference", self.protocol)
        self.assertIn("redacted reviewer note", self.protocol)
        self.assertIn("safe log summary", self.protocol)
        self.assertIn("never paste raw packet bodies, raw logs, token/key/credential values", self.protocol)
        self.assertIn("unredacted model output, or generated artifacts", self.protocol)

    def test_first_pass_intake_cannot_be_reported_as_keep_promotion(self):
        self.assertIn("no_keep_promotion_this_round", self.protocol)
        for forbidden_evidence in (
            "seed inventory",
            "route inventory",
            "local receipts",
            "no-feature-loss matrix",
            "mock",
            "sanitizer",
            "docs/config scaffold",
            "checklist wording",
        ):
            self.assertIn(forbidden_evidence, self.protocol)
        self.assertIn("must not be described as direct UX/bug evidence", self.protocol)

    def test_handoff_protocol_keeps_mode_layered_runtime_boundary(self):
        self.assertIn("Runtime automation is mode-layered, not an absolute startup ban", self.protocol)
        self.assertIn("`cache_only` is the default", self.protocol)
        self.assertIn("FastAPI startup, and GET cache/status routes stay read-only", self.protocol)
        self.assertIn("`manual` allows external work only through an explicit user button or POST task", self.protocol)
        self.assertIn("`live_light` may create or reuse one bounded local background POST task after cache render", self.protocol)
        self.assertIn("provider/model work must still go through the task contract", self.protocol)
        self.assertIn("`live_full` is reserved and default-off", self.protocol)
        self.assertIn("requires separate authorization before any full-pool, deep-scan, or broad automatic provider/model work", self.protocol)
        self.assertIn("Any permitted provider/model external work must produce redacted `call_ledger` / `model_ledger` rows", self.protocol)
        self.assertIn("missing ledger rows keep the result local or pending", self.protocol)
        self.assertIn("cannot promote `live_light`, LTG completion, or production acceptance", self.protocol)
        self.assertIn("Provider/model handoff reports must use safe summaries only", self.protocol)
        self.assertIn("do not paste raw prompts, raw model output, unredacted provider errors", self.protocol)
        self.assertIn("credential-like values, or raw packet bodies into checkpoints", self.protocol)
        self.assertIn("whitelisted fields with `model_ledger` status and redaction review", self.protocol)
        self.assertIn("Full backtests, full-market scans, heavy Tushare/AkShare/yfinance/Supabase refreshes", self.protocol)
        self.assertIn("any real trading path remain explicit-button or separately authorized work", self.protocol)
        self.assertIn("DeepSeek is never a data source", self.protocol)
        self.assertIn("DeepSeek text, model summaries, or explanation status cannot satisfy missing evidence", self.protocol)
        self.assertIn("cannot become a next-click action", self.protocol)
        self.assertIn("cannot replace provider/cache/factor/operation-zone evidence", self.protocol)
        self.assertIn("only explain existing evidence with `model_ledger` status and redaction state", self.protocol)

    def test_handoff_protocol_separates_configured_true_from_effective_external_call(self):
        self.assertIn("configured=true", self.protocol)
        self.assertIn("operator intent, not effective external calls", self.protocol)
        self.assertIn("become effective only after the current runtime mode, task gate, ledgers, redaction, and promotion rules allow them", self.protocol)
        self.assertIn("`cache_only` forces effective automation false", self.protocol)
        self.assertIn("`manual` remains explicit-button/POST only", self.protocol)
        self.assertIn("`live_light` remains bounded local task creation after cache render", self.protocol)
        self.assertIn("`live_full` remains reserved", self.protocol)
        self.assertIn("`live_full` remains reserved with no hidden automation", self.protocol)
        self.assertIn("configured source/release switches remain operator intent rather than effective external calls", self.protocol)
        self.assertIn("Configured/effective switch checkpoint", self.protocol)
        self.assertIn("report the configured value separately from the effective external-call verdict", self.protocol)
        self.assertIn("do not summarize `configured=true` as `live_light` enabled", self.protocol)
        self.assertIn("permission for render/startup/search typing to call providers/models", self.protocol)
        self.assertIn("`configured_switch_rule`", self.protocol)
        self.assertIn("`effective_external_call_rule`", self.protocol)

    def test_checkpoint_report_requires_cycle_scope_and_runtime_boundaries(self):
        self.assertIn("at most one main target and one supporting target", self.protocol)
        self.assertIn("modify no more than five files", self.protocol)
        self.assertIn("end with a `Checkpoint` that states the evidence boundary", self.protocol)
        self.assertIn("Cycle scope: main target, supporting target, changed file count", self.protocol)
        self.assertIn("Runtime-mode boundary", self.protocol)
        self.assertIn("Runtime policy row boundary", self.protocol)
        self.assertIn("Configured/effective switch checkpoint", self.protocol)
        self.assertIn("Ordinary task-boundary visibility", self.protocol)
        self.assertIn("Ordinary source-state chips", self.protocol)
        self.assertIn("Report all six chip verdicts separately", self.protocol)
        self.assertIn("do not collapse `pending`, `degraded`, or `last_successful_cache/result`", self.protocol)
        self.assertIn("tooltip-only state, hidden tab, or engineering table", self.protocol)
        self.assertIn("Ordinary next-click rule", self.protocol)
        self.assertIn("Report the four next-click verdicts separately", self.protocol)
        self.assertIn("primary action, disabled/degraded reason", self.protocol)
        self.assertIn("POST task / worker / local fallback boundary", self.protocol)
        self.assertIn("task-status plus no-trade/no-action visibility", self.protocol)
        self.assertIn("Engineering-audit demotion", self.protocol)
        self.assertIn("engineering contract tables, receipt rows, runbooks, and LTG audit surfaces", self.protocol)
        self.assertIn("remain behind Settings / Developer / Audit", self.protocol)
        self.assertIn("must not become the default ordinary-page body", self.protocol)
        self.assertIn("Report the demotion verdicts separately", self.protocol)
        self.assertIn("ordinary summary appears before engineering detail", self.protocol)
        self.assertIn("Settings / Developer / Audit link remains visible", self.protocol)
        self.assertIn("current-decision-surface exception reason", self.protocol)
        self.assertIn("Priority alignment", self.protocol)
        self.assertIn("One recommended next small patch", self.protocol)

    def test_checkpoint_report_separates_local_validation_from_remote_ci_evidence(self):
        self.assertIn("CI / release evidence boundary", self.protocol)
        self.assertIn("only local validation or a matching current remote CI review", self.protocol)
        self.assertIn("Local tests, local push gate, static workflow files, checklist wording, receipts", self.protocol)
        self.assertIn("stage-scope rows are not remote CI evidence", self.protocol)
        self.assertIn("matching head SHA/commit with current GitHub Actions green status or reviewed failure logs", self.protocol)
        self.assertIn("explicit user push confirmation before any push", self.protocol)
        self.assertIn("Remote CI unknown rule", self.protocol)
        self.assertIn("if the user did not explicitly request GitHub/Actions inspection", self.protocol)
        self.assertIn("report remote CI status as unknown", self.protocol)
        self.assertIn("do not infer green, red, or release readiness from local validation", self.protocol)
        self.assertIn("workflow-file presence, old emails, or previous remote runs", self.protocol)

    def test_long_term_goal_parity_wording_means_capability_not_legacy_ui_copy(self):
        self.assertIn("chart capability parity", self.long_term_goals)
        self.assertIn(
            "React/Tauri capability parity, Legacy Bug / UX Audit evidence, and fallback safety",
            self.long_term_goals,
        )
        self.assertIn(
            "no-feature-loss signal/capability parity recipe (not Streamlit UI copy)",
            self.long_term_goals,
        )
        self.assertIn(
            "React/ECharts replaces Streamlit main next-session visual after Legacy Bug / UX Audit and no signal-group loss proof",
            self.long_term_goals,
        )
        self.assertIn(
            "signal/capability no-feature-loss QA, legacy parity acceptance receipt (not old radar UI/navigation copy)",
            self.long_term_goals,
        )
        self.assertIn("preserve legacy signal groups", self.long_term_goals)


if __name__ == "__main__":
    unittest.main()
