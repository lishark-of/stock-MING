from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from server.services import task_service
from server.services.task_service import clear_task_statuses_for_tests


class LegacyAuditApiGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self._tmp = tempfile.TemporaryDirectory()
        self.meta_store = Path(self._tmp.name) / "meta.sqlite"
        self._meta_patch = patch.object(task_service, "SQLITE_META_PATH", self.meta_store)
        self._meta_patch.start()
        clear_task_statuses_for_tests(clear_persisted=True)

    def tearDown(self) -> None:
        clear_task_statuses_for_tests(clear_persisted=True)
        self._meta_patch.stop()
        self._tmp.cleanup()

    def test_legacy_cache_keeps_seed_audit_admin_debug_and_read_only(self) -> None:
        self.assertEqual(task_service.list_task_statuses(), [])

        response = self.client.get("/api/legacy/cache")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        packet = body["data"]
        self.assertEqual(task_service.list_task_statuses(), [])

        self.assertEqual(packet["packet_key"], "command_center_3_legacy_bridge_cache")
        self.assertTrue(packet["policy"]["does_not_open_streamlit"])
        self.assertTrue(packet["policy"]["does_not_run_legacy_tools"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])

        entrance_audit = packet["ordinary_entrance_acceptance_audit"]
        module_rows = packet["legacy_bug_ux_module_rows"]
        ordinary_rows = packet["ordinary_entrance_acceptance_rows"]
        self.assertEqual(entrance_audit["legacy_bug_ux_keep_count"], 0)
        self.assertFalse(entrance_audit["ordinary_entrance_acceptance_complete"])
        self.assertFalse(entrance_audit["legacy_modules_enter_ordinary_flow_without_audit"])
        self.assertEqual(
            entrance_audit["legacy_bug_ux_direct_evidence_pending_count"],
            entrance_audit["legacy_bug_ux_module_row_count"],
        )
        self.assertEqual(
            entrance_audit["legacy_bug_ux_keep_upgrade_blocked_count"],
            entrance_audit["legacy_bug_ux_module_row_count"],
        )
        self.assertEqual(
            {row["entrance"] for row in ordinary_rows},
            {"daily_command_center", "stock_quant_projection", "candidate_radar"},
        )
        self.assertTrue(all(row["classification"] == "REDESIGN" for row in ordinary_rows))
        self.assertTrue(all(row["ordinary_page_should_show_summary_only"] for row in ordinary_rows))

        for row in module_rows:
            self.assertNotEqual(row["classification"], "KEEP")
            self.assertEqual(
                row["direct_ux_bug_evidence_source"],
                "seed_only_direct_evidence_pending_before_KEEP",
            )
            self.assertTrue(row["keep_upgrade_blocked_without_direct_evidence"])
            self.assertEqual(row["ordinary_entrance_placement"], row["target_surface"])
            self.assertEqual(row["frozen_legacy_path"], row["legacy_ux_or_bug_path_not_migrated"])

        intake = packet["legacy_audit_first_round_intake"]
        intake_rows = packet["legacy_audit_first_round_intake_rows"]
        self.assertEqual(intake["status"], "legacy_audit_first_round_intake_visible_admin_debug_only")
        self.assertTrue(intake["legacy_admin_debug_surface_only"])
        self.assertFalse(intake["keep_promotion_allowed_this_round"])
        self.assertFalse(intake["ordinary_entry_promotion_allowed_this_round"])
        self.assertNotIn("KEEP", intake["allowed_statuses"])
        self.assertIn("safe_screenshot_reference", intake["safe_attachment_sources"])
        self.assertIn("raw_packet_bodies", intake["forbidden_attachment_sources"])
        self.assertEqual(intake["row_count"], len(intake_rows))
        for row in intake_rows:
            self.assertEqual(row["allowed_initial_status"], "direct_evidence_intake_pending")
            self.assertTrue(row["legacy_admin_debug_surface_only"])
            self.assertFalse(row["keep_promotion_allowed_this_round"])
            self.assertFalse(row["ordinary_entry_promotion_allowed_this_round"])
            self.assertIn("user_observation", row["required_fields"])
            self.assertIn("token_key_credential_values", row["forbidden_attachment_sources"])

        ledger_apis = {row["api"] for row in packet["call_ledger"]}
        self.assertIn("local_legacy_bridge_cache", ledger_apis)
        self.assertIn("local_ordinary_entrance_acceptance_audit", ledger_apis)
        self.assertIn("local_legacy_audit_first_round_intake", ledger_apis)
        for row in packet["call_ledger"]:
            self.assertFalse(row.get("external", False))


if __name__ == "__main__":
    unittest.main()
