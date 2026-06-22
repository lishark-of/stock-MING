import json
import tempfile
import unittest
from pathlib import Path

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

    def test_local_push_gate_receipt_missing_or_unreadable_has_uniform_freshness_blockers(self):
        original_path = audit_service.LOCAL_PUSH_GATE_RUN_RECEIPT_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                missing_path = Path(temp_dir) / "missing-local-push-gate-receipt.json"
                audit_service.LOCAL_PUSH_GATE_RUN_RECEIPT_PATH = missing_path
                missing = audit_service._read_local_push_gate_run_receipt()

                self.assertEqual(missing["status"], "local_push_gate_run_receipt_missing")
                self.assertEqual(missing["read_status"], "receipt_missing")
                self.assertFalse(missing["fresh_local_gate_run_observed"])
                self.assertFalse(missing["boundary_flags_valid"])
                self.assertFalse(missing["safety_boundary_flags_valid"])
                self.assertFalse(missing["push_confirmation_boundary_valid"])
                self.assertEqual(missing["freshness_blockers"], ["receipt_missing"])
                self.assertEqual(missing["freshness_blocker_count"], 1)
                self.assertTrue(missing["did_not_push"])
                self.assertFalse(missing["github_api_called"])
                self.assertFalse(missing["external_calls_triggered"])
                self.assertTrue(missing["does_not_execute_trades"])

                unreadable_path = Path(temp_dir) / "unreadable-local-push-gate-receipt.json"
                unreadable_path.write_text("{", encoding="utf-8")
                audit_service.LOCAL_PUSH_GATE_RUN_RECEIPT_PATH = unreadable_path
                unreadable = audit_service._read_local_push_gate_run_receipt()

                self.assertEqual(unreadable["status"], "local_push_gate_run_receipt_unreadable")
                self.assertEqual(unreadable["read_status"], "receipt_read_failed")
                self.assertFalse(unreadable["fresh_local_gate_run_observed"])
                self.assertFalse(unreadable["boundary_flags_valid"])
                self.assertFalse(unreadable["safety_boundary_flags_valid"])
                self.assertFalse(unreadable["push_confirmation_boundary_valid"])
                self.assertEqual(unreadable["freshness_blockers"], ["receipt_read_failed"])
                self.assertEqual(unreadable["freshness_blocker_count"], 1)
                self.assertTrue(unreadable["did_not_push"])
                self.assertFalse(unreadable["github_api_called"])
                self.assertFalse(unreadable["external_calls_triggered"])
                self.assertTrue(unreadable["does_not_execute_trades"])
            finally:
                audit_service.LOCAL_PUSH_GATE_RUN_RECEIPT_PATH = original_path

    def test_push_readiness_keeps_explicit_push_confirmation_pending(self):
        packet = audit_service.read_call_ledger_audit_cache()
        receipt = packet["release_gate_push_readiness_receipt"]

        self.assertFalse(receipt["explicit_user_push_confirmation_before_push"])
        self.assertEqual(receipt["push_confirmation_state"], "not_requested_no_push")
        self.assertEqual(receipt["release_claim_decision"], "blocked_remote_ci_unverified")
        self.assertIn(
            "explicit_user_push_confirmation_before_push",
            receipt["missing_evidence_items"],
        )
        self.assertIn(
            "push without explicit user confirmation after local gate review",
            receipt["not_allowed_next_steps"],
        )
        self.assertTrue(receipt["did_not_push"])
        self.assertFalse(receipt["github_api_called"])
        self.assertFalse(receipt["external_calls_triggered"])
        self.assertFalse(receipt["tushare_called"])
        self.assertFalse(receipt["deepseek_called"])
        self.assertTrue(receipt["does_not_execute_trades"])

        stage_rows = {row["stage_key"]: row for row in packet["release_gate_stage_scope_rows"]}
        approval_row = stage_rows["explicit_push_approval_boundary"]
        self.assertFalse(approval_row["stage_complete"])
        self.assertFalse(approval_row["explicit_user_push_confirmation_before_push"])
        self.assertEqual(approval_row["push_confirmation_state"], "not_requested_no_push")

    def test_push_readiness_surfaces_local_receipt_freshness_blockers(self):
        original_path = audit_service.LOCAL_PUSH_GATE_RUN_RECEIPT_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                audit_service.LOCAL_PUSH_GATE_RUN_RECEIPT_PATH = (
                    Path(temp_dir) / "missing-local-push-gate-receipt.json"
                )
                packet = audit_service.read_call_ledger_audit_cache()
                receipt = packet["release_gate_push_readiness_receipt"]

                self.assertEqual(
                    receipt["local_push_gate_run_receipt_freshness_blockers"],
                    ["receipt_missing"],
                )
                self.assertEqual(receipt["local_push_gate_run_receipt_freshness_blocker_count"], 1)
                self.assertIn("fresh_local_push_gate_command_output", receipt["missing_evidence_items"])

                row = {
                    item["criterion"]: item
                    for item in packet["release_gate_push_readiness_rows"]
                }["fresh_local_gate_run_required_before_push"]
                self.assertIn("freshness_blockers=['receipt_missing']", row["evidence"])
                self.assertFalse(row["passed"])
                self.assertEqual(row["status"], "pending_local_gate_run")
            finally:
                audit_service.LOCAL_PUSH_GATE_RUN_RECEIPT_PATH = original_path


if __name__ == "__main__":
    unittest.main()
