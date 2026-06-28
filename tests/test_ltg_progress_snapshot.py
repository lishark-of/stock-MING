import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "ltg_progress_snapshot.py"


def _load_snapshot_module():
    spec = importlib.util.spec_from_file_location(
        "ltg_progress_snapshot_under_test",
        SNAPSHOT_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LtgProgressSnapshotTests(unittest.TestCase):
    def test_release_gate_remote_review_split_is_visible_in_snapshot_text(self):
        module = _load_snapshot_module()
        fake_status = {
            "packet_key": "fake_packet",
            "mode": "test",
            "loaded_at": "2026-06-28T12:35:19Z",
            "long_term_goal_summary": {
                "strict_closeout": "0/14",
                "strict_closeout_done_count": 0,
                "strict_closeout_total_count": 14,
                "strict_closeout_remaining_count": 14,
            },
            "api_policy": {
                "cache_only": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "contains_secret": False,
            },
            "long_term_goal_rows": [],
            "ltg_acceptance_runway_rows": [],
            "ltg_next_acceptance_action_rows": [],
            "ltg_strict_closeout_evidence_spine_rows": [],
            "ltg_strict_closeout_evidence_spine_summary": {
                "schema_version": "ltg_strict_closeout_evidence_spine_summary.v1",
                "spine_visible_count": 14,
                "spine_total_count": 14,
                "strict_closeout_work_order_visible_count": 14,
                "strict_closeout_work_order_total_count": 14,
                "all_rows_have_strict_closeout_work_order": True,
                "all_rows_have_next_evidence_action": True,
                "all_rows_keep_one_ltg_scope": True,
                "release_gate_current_head_remote_review_state": (
                    "remote_ci_green_local_gate_recheck_required"
                ),
                "release_gate_current_blocker_count": 5,
                "release_gate_current_blockers": [
                    "worktree_dirty",
                    "remote_ci_green_local_gate_recheck_required",
                ],
                "strict_closeout_claim_allowed": False,
                "cache_only_readback": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "contains_secret": False,
            },
            "release_gate_remote_review_split_summary": {
                "status": "release_gate_remote_ci_green_local_gate_recheck_required",
                "current_head_publish_status": "current_head_has_no_unpushed_commits_for_remote_ci",
                "current_head_origin_ahead_count": 0,
                "current_head_push_required_before_remote_review": False,
                "remote_review_status": "remote_review_green_local_gate_recheck_required",
                "remote_actions_status_known": True,
                "latest_remote_run_verified_green": True,
                "remote_ci_green_for_current_head": True,
                "remote_ci_review_receipt_status": "remote_ci_review_verified_green",
                "remote_ci_review_receipt_head_matches_current": True,
                "remote_ci_review_receipt_run_id": "28322176181",
                "remote_ci_artifact_digest_pending": False,
                "remote_ci_green_local_gate_recheck_required": True,
                "fresh_local_gate_run_observed": False,
                "required_local_gate_checks_present": True,
                "local_worktree_clean": False,
                "local_worktree_dirty_file_count": 1,
                "local_worktree_blocks_local_gate_receipt": True,
                "local_push_gate_report_reached_clean_worktree_check": False,
                "release_review_blocked_by_local_gate_recheck": True,
                "strict_closeout_ready": False,
            },
            "ltg11_release_gate_remote_review_handoff_summary": {
                "schema_version": "ltg11_release_gate_remote_review_handoff_summary.v1",
                "status": "release_gate_remote_review_green_local_gate_recheck_required",
                "requires_current_head_local_gate_recheck": True,
                "requires_clean_worktree_before_local_gate": True,
                "next_local_step": "rerun_local_push_gate_after_clean_worktree_for_current_head",
                "next_publish_step": "inspect_matching_remote_actions_after_push",
            },
            "ltg_strict_closeout_work_order_summary": {
                "release_gate_current_head_remote_review_state": (
                    "remote_ci_green_local_gate_recheck_required"
                ),
                "release_gate_current_blockers": [
                    "head_mismatch",
                    "required_checks_missing",
                    "worktree_dirty",
                    "remote_ci_green_local_gate_recheck_required",
                    "clean_worktree_required_before_release_review_after_remote_ci_green",
                ],
                "release_gate_local_push_gate_report_is_not_pass_receipt": True,
                "strict_closeout_claim_allowed": False,
            },
        }

        with patch.object(module.migration_status_service, "build_migration_status", return_value=fake_status):
            snapshot = module.build_snapshot()

        release_gate = snapshot["release_gate_remote_review"]
        self.assertEqual(
            release_gate["status"],
            "release_gate_remote_review_green_local_gate_recheck_required",
        )
        self.assertEqual(
            release_gate["current_head_publish_status"],
            "current_head_has_no_unpushed_commits_for_remote_ci",
        )
        self.assertFalse(release_gate["current_head_push_required_before_remote_review"])
        self.assertEqual(release_gate["remote_review_status"], "remote_review_green_local_gate_recheck_required")
        self.assertTrue(release_gate["remote_ci_green_for_current_head"])
        self.assertTrue(release_gate["requires_current_head_local_gate_recheck"])
        self.assertEqual(release_gate["local_worktree_dirty_file_count"], 1)
        self.assertEqual(release_gate["release_gate_current_blocker_count"], 5)
        self.assertEqual(
            release_gate["next_local_step"],
            "rerun_local_push_gate_after_clean_worktree_for_current_head",
        )

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            module._print_text(snapshot)
        text = buffer.getvalue()

        self.assertIn("Release gate:", text)
        self.assertIn("publish_status=current_head_has_no_unpushed_commits_for_remote_ci", text)
        self.assertIn("push_required=False", text)
        self.assertIn("remote_status=remote_review_green_local_gate_recheck_required", text)
        self.assertIn("remote_green=True", text)
        self.assertIn("local_recheck=True", text)
        self.assertIn("dirty_files=1", text)
        self.assertIn("next_local=rerun_local_push_gate_after_clean_worktree_for_current_head", text)


if __name__ == "__main__":
    unittest.main()
