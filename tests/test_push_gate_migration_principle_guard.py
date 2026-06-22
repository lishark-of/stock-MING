from __future__ import annotations

import unittest
from pathlib import Path


class PushGateMigrationPrincipleGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.script = (root / "scripts" / "push_gate_3_0.sh").read_text(encoding="utf-8")

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
        self.assertIn("Scaffold, preflight, matrix, mock, and sanitizer checks are not production completion evidence.", self.script)


if __name__ == "__main__":
    unittest.main()
