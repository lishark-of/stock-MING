import json
import unittest

from server.services import audit_service


class AuditGateLocalWorktreeTests(unittest.TestCase):
    def test_local_worktree_cleanliness_audit_suppresses_file_paths(self):
        audit, rows = audit_service._local_worktree_cleanliness_audit(
            [
                " M docs/private_release_note.md",
                "M  desktop/src/routes/CallLedgerAudit.tsx",
                "?? tests/private_fixture.py",
            ]
        )

        self.assertEqual(audit["schema_version"], "command_center_3_local_worktree_cleanliness_audit.v1")
        self.assertEqual(audit["status"], "worktree_dirty_clean_gate_blocked")
        self.assertEqual(audit["scope"], "local_git_status_short_no_github_api_no_push")
        self.assertFalse(audit["worktree_clean"])
        self.assertTrue(audit["status_known"])
        self.assertEqual(audit["dirty_file_count"], 3)
        self.assertEqual(audit["tracked_change_count"], 2)
        self.assertEqual(audit["untracked_file_count"], 1)
        self.assertEqual(audit["modified_file_count"], 2)
        self.assertFalse(audit["raw_paths_emitted"])
        self.assertFalse(audit["raw_status_lines_emitted"])
        self.assertTrue(audit["blocks_local_push_gate_receipt"])
        self.assertTrue(audit["release_hygiene_blocker"])
        self.assertTrue(audit["did_not_push"])
        self.assertFalse(audit["github_api_called"])
        self.assertFalse(audit["external_calls_triggered"])
        self.assertTrue(audit["does_not_execute_trades"])
        self.assertTrue(audit["does_not_modify_strategy_action"])
        self.assertEqual(audit["call_ledger"][0]["api"], "local_git_status_short_worktree_cleanliness")
        self.assertFalse(audit["call_ledger"][0]["external"])

        status_rows = {row["status_code"]: row for row in rows}
        self.assertEqual(status_rows["_M"]["count"], 1)
        self.assertEqual(status_rows["M_"]["count"], 1)
        self.assertEqual(status_rows["??"]["count"], 1)
        for row in rows:
            self.assertFalse(row["raw_paths_emitted"])
            self.assertFalse(row["raw_status_lines_emitted"])

        serialized = json.dumps({"audit": audit, "rows": rows}, ensure_ascii=False)
        for forbidden_fragment in (
            "private_release_note",
            "CallLedgerAudit.tsx",
            "private_fixture",
        ):
            self.assertNotIn(forbidden_fragment, serialized)

    def test_remote_ci_review_seed_is_local_non_evidence(self):
        seed = audit_service._remote_ci_review_seed_contract()

        self.assertEqual(seed["schema_version"], "command_center_3_remote_ci_review_seed.v1")
        self.assertEqual(seed["status"], "blocked_remote_ci_unverified")
        self.assertEqual(seed["scope"], "local_checkpoint_seed_row_no_github_api_no_push")
        self.assertTrue(seed["release_claim_blocked"])
        self.assertFalse(seed["remote_actions_status_known"])
        self.assertFalse(seed["latest_remote_run_verified_green"])
        self.assertFalse(seed["safe_failure_logs_reviewed"])
        self.assertTrue(seed["local_gate_pass_is_not_ci_status"])
        self.assertTrue(seed["seed_row_is_not_remote_ci_evidence"])
        self.assertTrue(seed["did_not_push"])
        self.assertFalse(seed["github_api_called"])
        self.assertFalse(seed["external_calls_triggered"])
        self.assertFalse(seed["tushare_called"])
        self.assertFalse(seed["deepseek_called"])
        self.assertTrue(seed["does_not_execute_trades"])
        self.assertTrue(seed["does_not_modify_strategy_action"])
        self.assertEqual(seed["call_ledger"][0]["api"], "local_remote_ci_review_seed_contract")
        self.assertFalse(seed["call_ledger"][0]["external"])

        seed_row = seed["seed_row"]
        self.assertEqual(seed_row["remote_status"], "remote_ci_unverified")
        self.assertEqual(seed_row["failed_step_or_green_status"], "not_reviewed")
        self.assertEqual(seed_row["release_claim_decision"], "blocked_remote_ci_unverified")


if __name__ == "__main__":
    unittest.main()
