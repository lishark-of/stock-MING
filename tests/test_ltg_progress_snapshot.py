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

    def test_trade_isolation_release_guard_is_visible_in_snapshot_text(self):
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
                "release_gate_current_head_remote_review_state": "current_head_unpushed_for_remote_ci",
                "release_gate_current_blocker_count": 5,
                "release_gate_current_blockers": ["local_commits_not_pushed_for_remote_ci"],
                "strict_closeout_claim_allowed": False,
                "cache_only_readback": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "contains_secret": False,
            },
            "release_gate_remote_review_split_summary": {},
            "ltg11_release_gate_remote_review_handoff_summary": {},
            "ltg_strict_closeout_work_order_summary": {
                "release_gate_current_head_remote_review_state": "current_head_unpushed_for_remote_ci",
                "release_gate_current_blockers": ["local_commits_not_pushed_for_remote_ci"],
                "strict_closeout_claim_allowed": False,
            },
            "ltg12_trade_isolation_release_guard_handoff_summary": {
                "schema_version": "ltg12_trade_isolation_release_guard_handoff_summary.v1",
                "trade_isolation_release_receipt_status": (
                    "trade_isolation_release_receipt_ready_research_release_only"
                ),
                "trade_isolation_release_receipt_ready": True,
                "current_slice_trade_isolation_recheck_ready": True,
                "current_slice_no_broker_no_order_no_action_proof_ready": True,
                "real_trading_connected": False,
                "broker_adapter_connected": False,
                "broker_called": False,
                "order_endpoint_present": False,
                "order_route_present": False,
                "order_submitted": False,
                "trade_execution_api_enabled": False,
                "frontend_trade_controls_present": False,
                "model_or_provider_can_modify_action": False,
                "strategy_action_mutated_by_contract": False,
                "release_receipt_is_trading_approval": False,
                "ready_for_real_trading_integration": False,
                "future_real_trading_requires_separate_project": True,
                "per_slice_trade_isolation_recheck_required": True,
                "cache_get_calls_model": False,
                "cache_get_calls_broker": False,
                "cache_get_calls_order_endpoint": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "next_local_step": "separate approved real-trading integration project only",
            },
        }

        with patch.object(module.migration_status_service, "build_migration_status", return_value=fake_status):
            snapshot = module.build_snapshot()

        trade_guard = snapshot["trade_isolation_release_guard"]
        self.assertEqual(
            trade_guard["trade_isolation_release_receipt_status"],
            "trade_isolation_release_receipt_ready_research_release_only",
        )
        self.assertTrue(trade_guard["trade_isolation_release_receipt_ready"])
        self.assertTrue(trade_guard["current_slice_trade_isolation_recheck_ready"])
        self.assertTrue(trade_guard["no_broker_or_broker_call"])
        self.assertTrue(trade_guard["no_order_endpoint_or_submission"])
        self.assertTrue(trade_guard["no_trade_execution_api"])
        self.assertTrue(trade_guard["no_action_mutation"])
        self.assertFalse(trade_guard["real_trading_connected"])
        self.assertFalse(trade_guard["ready_for_real_trading_integration"])
        self.assertTrue(trade_guard["future_real_trading_requires_separate_project"])
        self.assertFalse(trade_guard["release_receipt_is_trading_approval"])

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            module._print_text(snapshot)
        text = buffer.getvalue()

        self.assertIn("Trade isolation:", text)
        self.assertIn("receipt=trade_isolation_release_receipt_ready_research_release_only", text)
        self.assertIn("recheck_ready=True", text)
        self.assertIn("no_broker=True", text)
        self.assertIn("no_order_endpoint=True", text)
        self.assertIn("no_trade_api=True", text)
        self.assertIn("no_action_mutation=True", text)
        self.assertIn("separate_project=True", text)
        self.assertIn("ready_for_real_trading=False", text)

    def test_trade_cal_provider_acceptance_is_visible_without_completion_claim(self):
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
                "release_gate_current_head_remote_review_state": "current_head_unpushed_for_remote_ci",
                "release_gate_current_blocker_count": 5,
                "release_gate_current_blockers": ["local_commits_not_pushed_for_remote_ci"],
                "strict_closeout_claim_allowed": False,
                "cache_only_readback": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "contains_secret": False,
            },
            "release_gate_remote_review_split_summary": {},
            "ltg11_release_gate_remote_review_handoff_summary": {},
            "ltg12_trade_isolation_release_guard_handoff_summary": {},
            "ltg_strict_closeout_work_order_summary": {
                "release_gate_current_head_remote_review_state": "current_head_unpushed_for_remote_ci",
                "release_gate_current_blockers": ["local_commits_not_pushed_for_remote_ci"],
                "strict_closeout_claim_allowed": False,
            },
            "ltg01_trade_cal_provider_acceptance_evidence_handoff_summary": {
                "schema_version": "ltg01_trade_cal_provider_acceptance_evidence_handoff_summary.v1",
                "status": "provider_acceptance_task_receipt_chain_needed",
                "provider_direct_evidence_layer": "L3_direct_provider_call_ledger",
                "provider_direct_evidence_source": "command_center_tushare_refresh_packet",
                "provider_direct_evidence_status": "success",
                "trade_cal_provider_call_ledger_observed_count": 18,
                "trade_cal_provider_observed_row_count": 1462,
                "failure_mode_provider_evidence_done": True,
                "freshness_replay_provider_evidence_done": False,
                "freshness_replay_scenario_count": 8,
                "provider_backed_acceptance_done_by_blocker_audit": False,
                "provider_backed_acceptance_done_by_durable_recipe": False,
                "provider_evidence_visible": False,
                "durable_recipe_ready": True,
                "durable_promotion_ready": False,
                "latest_dry_run_found": False,
                "latest_dry_run_status": "no_trade_cal_provider_acceptance_dry_run_task_found",
                "latest_execution_request_found": False,
                "latest_execution_request_status": (
                    "no_trade_cal_provider_acceptance_execution_request_task_found"
                ),
                "latest_execution_request_ready_for_manual_provider_task_submission": False,
                "latest_promotion_review_found": False,
                "latest_promotion_review_status": (
                    "no_trade_cal_provider_acceptance_promotion_review_task_found"
                ),
                "latest_promotion_review_ready_for_release": False,
                "requires_explicit_provider_trade_cal_task": True,
                "requires_provider_freshness_replay": True,
                "requires_promotion_review_task": True,
                "requires_release_review_after_remote_green": True,
                "production_freshness_gate_complete": False,
                "strict_closeout_ready": False,
                "cache_get_calls_provider": False,
                "creates_provider_task_from_get": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "does_not_execute_trades": True,
                "next_local_step": "POST /api/data-health/trade-cal-provider-acceptance-dry-run",
                "allowed_next_step": (
                    "collect_direct_trade_cal_provider_call_ledger_replay_failure_mode_and_promotion_evidence"
                ),
                "missing_durable_evidence_item_count": 11,
                "local_evidence_missing_item_count": 6,
            },
        }

        with patch.object(module.migration_status_service, "build_migration_status", return_value=fake_status):
            snapshot = module.build_snapshot()

        trade_cal = snapshot["trade_cal_provider_acceptance"]
        self.assertEqual(trade_cal["status"], "provider_acceptance_task_receipt_chain_needed")
        self.assertEqual(trade_cal["provider_direct_evidence_status"], "success")
        self.assertEqual(trade_cal["trade_cal_provider_call_ledger_observed_count"], 18)
        self.assertEqual(trade_cal["trade_cal_provider_observed_row_count"], 1462)
        self.assertTrue(trade_cal["failure_mode_provider_evidence_done"])
        self.assertFalse(trade_cal["freshness_replay_provider_evidence_done"])
        self.assertFalse(trade_cal["provider_backed_acceptance_done_by_durable_recipe"])
        self.assertFalse(trade_cal["latest_dry_run_found"])
        self.assertFalse(trade_cal["latest_execution_request_found"])
        self.assertFalse(trade_cal["latest_promotion_review_ready_for_release"])
        self.assertFalse(trade_cal["cache_get_calls_provider"])
        self.assertFalse(trade_cal["tushare_called"])
        self.assertEqual(
            trade_cal["next_local_step"],
            "POST /api/data-health/trade-cal-provider-acceptance-dry-run",
        )

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            module._print_text(snapshot)
        text = buffer.getvalue()

        self.assertIn("Trade cal acceptance:", text)
        self.assertIn("status=provider_acceptance_task_receipt_chain_needed", text)
        self.assertIn("direct_provider=success", text)
        self.assertIn("ledger=18", text)
        self.assertIn("rows=1462", text)
        self.assertIn("failure_mode=True", text)
        self.assertIn("replay=False", text)
        self.assertIn("provider_backed=False", text)
        self.assertIn("execution_request=False", text)
        self.assertIn("promotion=False", text)
        self.assertIn("cache_provider=False", text)
        self.assertIn("tushare_called=False", text)
        self.assertIn("next=POST /api/data-health/trade-cal-provider-acceptance-dry-run", text)


if __name__ == "__main__":
    unittest.main()
