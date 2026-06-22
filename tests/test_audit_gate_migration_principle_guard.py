from __future__ import annotations

import unittest

from server.services import audit_service


class AuditGateMigrationPrincipleGuardTests(unittest.TestCase):
    def test_release_gate_audit_tracks_migration_principle_guard(self) -> None:
        audit, rows, workflow_rows = audit_service._release_gate_readiness_audit()

        self.assertEqual(audit["schema_version"], "command_center_3_release_gate_readiness_audit.v1")
        self.assertEqual(audit["scope"], "local_static_push_gate_contract_not_ci_status")
        self.assertTrue(audit["migration_principle_docs_guard_exists"])
        self.assertTrue(audit["migration_principle_docs_guard_step"])
        self.assertTrue(audit["migration_principle_docs_guard_order"])
        self.assertTrue(audit["migration_principle_docs_guard_is_local"])
        self.assertTrue(audit["migration_principle_commit_checkpoint_surfaces"])
        self.assertTrue(audit["ci_mirror_includes_migration_principle_docs_guard"])
        self.assertFalse(audit["github_api_called"])
        self.assertFalse(audit["external_calls_triggered"])
        self.assertFalse(audit["tushare_called"])
        self.assertFalse(audit["deepseek_called"])
        self.assertTrue(audit["does_not_execute_trades"])
        self.assertTrue(audit["does_not_modify_strategy_action"])

        row_by_criterion = {row["criterion"]: row for row in rows}
        for criterion in (
            "migration_principle_docs_guard_exists",
            "migration_principle_docs_guard_step",
            "migration_principle_docs_guard_order",
            "migration_principle_docs_guard_is_local",
            "migration_principle_commit_checkpoint_surfaces",
            "ci_mirror_migration_principle_docs_guard",
        ):
            self.assertTrue(row_by_criterion[criterion]["passed"])
            self.assertFalse(row_by_criterion[criterion]["production_blocker"])
            self.assertTrue(row_by_criterion[criterion]["evidence"])

        self.assertTrue(
            any(row.get("contains_migration_principle_docs_guard_step") for row in workflow_rows)
        )
        self.assertTrue(all(row.get("external_calls_triggered") is False for row in workflow_rows))

    def test_audit_cache_keeps_remote_ci_unknown_until_reviewed(self) -> None:
        packet = audit_service.read_call_ledger_audit_cache()
        seed = packet["remote_ci_review_seed_contract"]

        self.assertEqual(seed["schema_version"], "command_center_3_remote_ci_review_seed.v1")
        self.assertEqual(seed["status"], "blocked_remote_ci_unverified")
        self.assertEqual(seed["remote_status"], "remote_ci_unverified")
        self.assertTrue(seed["release_claim_blocked"])
        self.assertFalse(seed["remote_actions_status_known"])
        self.assertFalse(seed["latest_remote_run_verified_green"])
        self.assertFalse(seed["github_api_called"])
        self.assertFalse(seed["external_calls_triggered"])
        self.assertEqual(packet["remote_ci_review_seed_rows"][0]["remote_status"], "remote_ci_unverified")
        self.assertTrue(packet["counts"]["remote_ci_review_seed_release_claim_blocked"])
        self.assertFalse(packet["counts"]["remote_ci_review_seed_remote_status_known"])
        self.assertTrue(packet["policy"]["remote_ci_review_seed_row_is_not_remote_ci_evidence"])


if __name__ == "__main__":
    unittest.main()
