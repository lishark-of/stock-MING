import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.services import audit_service, data_health_service


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
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            audit_service,
            "REMOTE_CI_REVIEW_RECEIPT_PATH",
            Path(temp_dir) / "missing-remote-ci-review-receipt.json",
        ):
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

    def test_remote_ci_review_receipt_verifies_matching_green_run_without_release_closeout(self):
        current = audit_service._current_git_head_summary()
        clean_worktree = {
            "status": "worktree_clean_release_gate_ready",
            "worktree_clean": True,
            "status_known": True,
            "dirty_file_count": 0,
            "tracked_change_count": 0,
            "untracked_file_count": 0,
            "blocks_local_push_gate_receipt": False,
            "raw_paths_emitted": False,
            "raw_status_lines_emitted": False,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "local-push-gate-receipt.json"
            remote_path = Path(temp_dir) / "remote-ci-review-receipt.json"
            allowlist_path = Path(temp_dir) / "missing-secret-artifact-allowlist-review-receipt.json"
            local_path.write_text(
                json.dumps(
                    {
                        "schema_version": "command_center_3_local_push_gate_run_receipt.v1",
                        "status": "local_push_gate_passed_current_head",
                        "scope": "ignored_local_push_gate_run_receipt_no_push_no_github_api",
                        "branch": current["branch"],
                        "head": current["head"],
                        "head_full": current["head_full"],
                        "checks": sorted(audit_service.LOCAL_PUSH_GATE_REQUIRED_CHECKS),
                        "did_not_push": True,
                        "git_add_dot_used": False,
                        "external_calls_triggered": False,
                        "tushare_called": False,
                        "deepseek_called": False,
                        "github_called": False,
                        "github_api_called": False,
                        "does_not_execute_trades": True,
                        "does_not_modify_strategy_action": True,
                        "contains_secret": False,
                        "local_gate_pass_is_not_ci_status": True,
                        "remote_actions_status_known": False,
                        "latest_remote_run_verified_green": False,
                        "explicit_user_push_confirmation_before_push": False,
                        "push_confirmation_state": "not_requested_no_push",
                        "release_claim_decision": "blocked_remote_ci_unverified",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            remote_path.write_text(
                json.dumps(
                    {
                        "schema_version": "command_center_3_remote_ci_review_receipt.v1",
                        "status": "remote_ci_review_verified_green",
                        "scope": "ignored_manual_remote_ci_review_receipt_no_cache_github_api",
                        "receipt_writer": "scripts/record_remote_ci_review_receipt.py",
                        "branch": current["branch"],
                        "head": current["head_full"][:8],
                        "head_full": current["head_full"],
                        "run_id": 28277376120,
                        "run_url": "https://github.com/lishark-of/stock-MING/actions/runs/28277376120",
                        "workflow_name": "Command Center 3 Push Gate",
                        "event": "push",
                        "actions_status": "completed",
                        "actions_conclusion": "success",
                        "job_name": "push-gate",
                        "job_conclusion": "success",
                        "artifact_name": "command-center-3-push-gate-evidence-28277376120",
                        "artifact_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        "explicit_user_actions_review_authorized": True,
                        "remote_actions_status_known": True,
                        "latest_remote_run_verified_green": True,
                        "release_claim_decision": "remote_ci_green_release_review_pending",
                        "cache_get_external_calls": False,
                        "cache_get_calls_github_api": False,
                        "external_calls_triggered": False,
                        "tushare_called": False,
                        "deepseek_called": False,
                        "github_called": False,
                        "github_api_called": False,
                        "does_not_execute_trades": True,
                        "does_not_modify_strategy_action": True,
                        "contains_secret": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(audit_service, "LOCAL_PUSH_GATE_RUN_RECEIPT_PATH", local_path), patch.object(
                audit_service,
                "REMOTE_CI_REVIEW_RECEIPT_PATH",
                remote_path,
            ), patch.object(
                audit_service,
                "SECRET_ARTIFACT_ALLOWLIST_REVIEW_RECEIPT_PATH",
                allowlist_path,
            ), patch.object(audit_service, "_local_worktree_cleanliness_audit", return_value=(clean_worktree, [])):
                remote = audit_service._read_remote_ci_review_receipt()
                self.assertEqual(remote["status"], "remote_ci_review_verified_green")
                self.assertTrue(remote["remote_actions_status_known"])
                self.assertTrue(remote["latest_remote_run_verified_green"])
                self.assertTrue(remote["head_matches_current"])
                self.assertFalse(remote["github_api_called"])
                self.assertFalse(remote["external_calls_triggered"])
                self.assertTrue(remote["does_not_execute_trades"])
                self.assertFalse(remote["release_review_complete"])
                self.assertFalse(remote["release_gate_complete"])

                packet = audit_service.read_call_ledger_audit_cache()
                release_gate = packet["release_gate_readiness_audit"]
                self.assertEqual(
                    release_gate["status"],
                    "local_gate_ready_remote_ci_reviewed_allowlist_and_release_review_pending",
                )
                self.assertTrue(release_gate["remote_ci_review_ready"])
                self.assertTrue(release_gate["remote_actions_status_known"])
                self.assertTrue(release_gate["latest_remote_run_verified_green"])
                self.assertFalse(release_gate["release_review_complete"])
                self.assertFalse(release_gate["release_gate_complete"])
                self.assertNotIn("remote_ci_review_required_for_release_gate_complete", release_gate["blockers"])
                self.assertIn("release_review_after_remote_ci_green_required", release_gate["blockers"])
                release_gate_rows = {row["criterion"]: row for row in packet["release_gate_readiness_rows"]}
                self.assertTrue(release_gate_rows["remote_ci_review_required_for_release_gate_complete"]["passed"])
                self.assertEqual(
                    release_gate_rows["release_review_after_remote_ci_green_required"]["status"],
                    "pending_release_review",
                )

                receipt = packet["release_gate_push_readiness_receipt"]
                self.assertEqual(
                    receipt["status"],
                    "push_readiness_receipt_ready_remote_ci_reviewed_release_review_pending",
                )
                self.assertTrue(receipt["remote_actions_status_known"])
                self.assertTrue(receipt["latest_remote_run_verified_green"])
                self.assertNotIn("matching_remote_actions_run_status", receipt["missing_evidence_items"])
                self.assertIn("release_review_after_remote_ci_green", receipt["missing_evidence_items"])
                stage_rows = {row["stage_key"]: row for row in packet["release_gate_stage_scope_rows"]}
                self.assertTrue(stage_rows["matching_remote_actions_status"]["stage_complete"])

                local_release_gate = data_health_service._freshness_local_release_gate_evidence()
                self.assertEqual(
                    local_release_gate["status"],
                    "freshness_local_release_gate_observed_remote_ci_reviewed_release_review_pending",
                )
                self.assertTrue(local_release_gate["remote_actions_status_known"])
                self.assertTrue(local_release_gate["latest_remote_run_verified_green"])
                self.assertFalse(local_release_gate["release_review_complete"])
                self.assertFalse(local_release_gate["production_freshness_gate_complete"])

    def test_secret_artifact_allowlist_review_receipt_clears_only_periodic_review(self):
        current = audit_service._current_git_head_summary()
        with tempfile.TemporaryDirectory() as temp_dir:
            receipt_path = Path(temp_dir) / "secret-artifact-allowlist-review-receipt.json"
            script_path = (
                Path(__file__).resolve().parents[1]
                / "scripts"
                / "record_secret_artifact_allowlist_review_receipt.py"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--output",
                    str(receipt_path),
                    "--branch",
                    str(current["branch"]),
                    "--head",
                    str(current["head_full"][:8]),
                    "--head-full",
                    str(current["head_full"]),
                    "--reviewer",
                    "unit_test",
                    "--reviewed-at-utc",
                    "2026-06-29T01:23:45Z",
                    "--review-authorized",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["status"], "secret_artifact_allowlist_review_ready")
            self.assertTrue(summary["periodic_allowlist_review_ready"])
            self.assertFalse(summary["github_api_called"])
            self.assertFalse(summary["external_calls_triggered"])
            self.assertTrue(summary["does_not_execute_trades"])

            script_source = script_path.read_text(encoding="utf-8")
            self.assertNotIn("api.github.com", script_source)
            self.assertNotIn("requests", script_source)
            self.assertNotIn("httpx", script_source)
            self.assertNotIn("curl", script_source)

            with patch.object(
                audit_service,
                "SECRET_ARTIFACT_ALLOWLIST_REVIEW_RECEIPT_PATH",
                receipt_path,
            ), patch.object(
                audit_service,
                "RELEASE_GATE_REVIEW_RECEIPT_PATH",
                Path(temp_dir) / "missing-release-gate-review-receipt.json",
            ):
                receipt = audit_service._read_secret_artifact_allowlist_review_receipt()
                self.assertEqual(receipt["status"], "secret_artifact_allowlist_review_ready")
                self.assertTrue(receipt["head_matches_current"])
                self.assertTrue(receipt["periodic_allowlist_review_ready"])
                self.assertFalse(receipt["release_review_complete"])
                self.assertFalse(receipt["release_gate_complete"])
                self.assertFalse(receipt["github_api_called"])
                self.assertFalse(receipt["external_calls_triggered"])
                self.assertTrue(receipt["does_not_execute_trades"])

                packet = audit_service.read_call_ledger_audit_cache()
                release_gate = packet["release_gate_readiness_audit"]
                self.assertTrue(release_gate["false_positive_allowlist_review_ready"])
                self.assertEqual(
                    release_gate["secret_artifact_allowlist_review_receipt_status"],
                    "secret_artifact_allowlist_review_ready",
                )
                self.assertNotIn("false_positive_allowlist_review_pending", release_gate["soft_blockers"])
                self.assertFalse(release_gate["release_gate_complete"])

                push_receipt = packet["release_gate_push_readiness_receipt"]
                self.assertTrue(push_receipt["periodic_allowlist_review_ready"])
                self.assertNotIn(
                    "periodic_secret_artifact_allowlist_review",
                    push_receipt["missing_evidence_items"],
                )
                self.assertIn(
                    "explicit_user_push_confirmation_before_push",
                    push_receipt["missing_evidence_items"],
                )
                self.assertIn("release_review_after_remote_ci_green", push_receipt["missing_evidence_items"])
                self.assertFalse(push_receipt["github_api_called"])
                self.assertFalse(push_receipt["external_calls_triggered"])
                self.assertTrue(push_receipt["does_not_execute_trades"])

                stage_rows = {row["stage_key"]: row for row in packet["release_gate_stage_scope_rows"]}
                allowlist_row = stage_rows["secret_artifact_allowlist_review"]
                self.assertTrue(allowlist_row["stage_complete"])
                self.assertTrue(allowlist_row["periodic_allowlist_review_ready"])
                self.assertFalse(allowlist_row["release_gate_complete"])
                self.assertFalse(allowlist_row["github_api_called"])
                self.assertFalse(allowlist_row["external_calls_triggered"])
                self.assertTrue(allowlist_row["does_not_execute_trades"])

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
