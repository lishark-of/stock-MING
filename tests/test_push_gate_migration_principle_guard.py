from __future__ import annotations

import ast
import unittest
from pathlib import Path

from server.services import audit_service


class PushGateMigrationPrincipleGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.script = (root / "scripts" / "push_gate_3_0.sh").read_text(encoding="utf-8")
        self.workflow = (
            root / ".github" / "workflows" / "command-center-3-push-gate.yml"
        ).read_text(encoding="utf-8")

    def test_push_gate_runs_migration_principle_docs_guard_before_desktop_build(self) -> None:
        self.assertIn("Migration principle docs guard", self.script)
        self.assertIn("tests.test_command_center_migration_principles", self.script)
        self.assertIn(
            "migration_principle_docs_guard: passed_no_blind_streamlit_copy_policy_and_commit_checkpoint_surfaces",
            self.script,
        )
        self.assertIn('"migration_principle_docs_guard"', self.script)
        self.assertLess(
            self.script.index('run_step "Python unittest"'),
            self.script.index('run_step "Migration principle docs guard'),
        )
        self.assertLess(
            self.script.index('run_step "Migration principle docs guard'),
            self.script.index('run_step "Desktop build"'),
        )

    def test_push_gate_guard_stays_local_release_boundary_evidence(self) -> None:
        self.assertIn("- did_not_push: true", self.script)
        self.assertIn("- did_not_call_external_providers: true", self.script)
        self.assertIn("- did_not_execute_trades: true", self.script)
        self.assertIn("- local_gate_pass_is_not_remote_ci: true", self.script)
        self.assertIn("- remote_actions_status_known: false", self.script)
        self.assertIn("- latest_remote_run_verified_green: false", self.script)
        self.assertIn("- explicit_user_push_confirmation_before_push: false", self.script)
        self.assertIn("- push_confirmation_state: not_requested_no_push", self.script)
        self.assertIn("- release_claim_decision: blocked_remote_ci_unverified", self.script)
        self.assertIn(
            "This report does not authorize push; explicit user confirmation is still required after local gate review.",
            self.script,
        )
        self.assertIn("Scaffold, preflight, matrix, mock, and sanitizer checks are not production completion evidence.", self.script)
        self.assertIn("local_push_gate_receipt_artifact_policy_scan", self.script)
        self.assertIn("resolve(strict=False)", self.script)
        self.assertIn("must point to a file path, not the repository root", self.script)
        self.assertIn("LOCAL_PUSH_GATE_RECEIPT_PATH inside the repository must be ignored", self.script)
        self.assertLess(
            self.script.index("resolve(strict=False)"),
            self.script.index("git check-ignore"),
        )
        self.assertLess(
            self.script.index('run_step "Local push gate receipt artifact policy"'),
            self.script.index('run_step "Clean worktree check"'),
        )

    def test_local_push_gate_receipt_checks_match_required_checks(self) -> None:
        start = self.script.index('"checks": [')
        end = self.script.index("],", start)
        receipt_checks = set()
        for raw_line in self.script[start:end].splitlines()[1:]:
            line = raw_line.strip().strip(",")
            if line:
                receipt_checks.add(ast.literal_eval(line))

        self.assertEqual(receipt_checks, audit_service.LOCAL_PUSH_GATE_REQUIRED_CHECKS)
        self.assertIn("migration_principle_docs_guard", receipt_checks)
        self.assertIn("local_push_gate_receipt_artifact_policy", receipt_checks)

    def test_release_report_passed_checks_match_receipt_before_final_checks(self) -> None:
        start = self.script.index("## Passed Checks")
        end = self.script.index("## Safety Boundaries", start)
        report_checks = []
        for raw_line in self.script[start:end].splitlines()[1:]:
            line = raw_line.strip()
            if line.startswith("- ") and ":" in line:
                report_checks.append(line[2:].split(":", 1)[0])

        final_checks_after_report = {"release_readiness_report", "clean_worktree_check"}
        self.assertEqual(len(report_checks), len(set(report_checks)))
        self.assertEqual(
            set(report_checks),
            audit_service.LOCAL_PUSH_GATE_REQUIRED_CHECKS - final_checks_after_report,
        )
        self.assertLess(
            self.script.index('run_step "Local push gate receipt artifact policy"'),
            self.script.index('run_step "Release readiness report"'),
        )

    def test_ci_workflow_uploads_failure_diagnostics_without_github_api(self) -> None:
        self.assertIn("PUSH_GATE_LOG_PATH: ${{ runner.temp }}/command-center-3-push-gate.log", self.workflow)
        self.assertIn("PUSH_GATE_REPORT_PATH: ${{ runner.temp }}/command-center-3-push-gate-report.md", self.workflow)
        self.assertIn(
            "LOCAL_PUSH_GATE_RECEIPT_PATH: ${{ runner.temp }}/command-center-3-local-push-gate-run-receipt.json",
            self.workflow,
        )
        self.assertIn('scripts/push_gate_3_0.sh 2>&1 | tee "$PUSH_GATE_LOG_PATH"', self.workflow)
        self.assertIn("Summarize Command Center 3 push gate failure", self.workflow)
        self.assertIn("last_safe_gate_marker", self.workflow)
        self.assertIn("command-center-3-push-gate-failure-summary.md", self.workflow)
        self.assertIn("::error title=Command Center 3 push gate failure::", self.workflow)
        self.assertIn("uses: actions/upload-artifact@v4", self.workflow)
        self.assertIn("if: always()", self.workflow)
        self.assertIn("command-center-3-push-gate-evidence-${{ github.run_id }}", self.workflow)
        self.assertIn("${{ runner.temp }}/command-center-3-push-gate.log", self.workflow)
        self.assertIn("${{ runner.temp }}/command-center-3-push-gate-report.md", self.workflow)
        self.assertIn("${{ runner.temp }}/command-center-3-push-gate-failure-summary.md", self.workflow)
        self.assertIn(
            "${{ runner.temp }}/command-center-3-local-push-gate-run-receipt.json",
            self.workflow,
        )
        self.assertIn("retention-days: 7", self.workflow)
        self.assertNotIn("gh run", self.workflow)
        self.assertNotIn("GITHUB_TOKEN", self.workflow)


if __name__ == "__main__":
    unittest.main()
