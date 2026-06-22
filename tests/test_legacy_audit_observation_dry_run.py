from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from server.services import task_service
from server.services.task_service import clear_task_statuses_for_tests


class LegacyAuditObservationDryRunTests(unittest.TestCase):
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

    def _task_from_response(self, response):
        body = response.json()
        self.assertTrue(body["ok"])
        return body["data"]["task"]

    def test_observation_dry_run_records_safe_note_without_keep_promotion(self) -> None:
        catalog_entry = next(
            item
            for item in task_service.TASK_CATALOG
            if item["task_type"] == "run_legacy_audit_observation_dry_run"
        )
        self.assertEqual(catalog_entry["route"], "POST /api/legacy/audit-observation-dry-run")
        self.assertTrue(catalog_entry["button_gated"])
        self.assertTrue(catalog_entry["first_round_observation_dry_run_only"])
        self.assertFalse(catalog_entry["keep_promotion_allowed"])
        self.assertFalse(catalog_entry["ordinary_entry_promotion_allowed"])

        response = self.client.post(
            "/api/legacy/audit-observation-dry-run",
            json={
                "workflow_group": "searched-symbol quant projection",
                "user_observation": "Reviewer saw user search 000001.SZ, then hunt through legacy tabs before projection.",
                "legacy_ux_bug_or_patchwork": "Deep tab/radio navigation and blocking projection hide the next click.",
                "data_lineage_observation": "Factor/cache/pending states were visible, but DeepSeek text could read like action.",
                "replacement_user_path": "股票量化推演 / Stock Quant Projection -> 生成 3.0 量化推演",
                "frozen_legacy_path": "legacy single-stock room synchronous projection and AI-as-action copy",
                "evidence_attachment": "safe_log_summary: reviewer-note-2026-06-22-searched-symbol",
                "evidence_attachment_type": "safe_log_summary",
                "requested_status": "direct_evidence_observed_redesign_required",
                "keep_promotion_decision": "no_keep_promotion_this_round",
                "requested_by": "local-reviewer",
                "api_key": "SHOULD_DROP",
                "raw_packet_bodies": "SHOULD_DROP",
            },
        )

        self.assertEqual(response.status_code, 200)
        task = self._task_from_response(response)
        self.assertEqual(task["task_type"], "run_legacy_audit_observation_dry_run")
        self.assertEqual(task["status"], "success")
        self.assertEqual(
            task["current_step"],
            "legacy_audit_observation_dry_run_recorded_no_keep_promotion",
        )
        self.assertEqual(
            task["output_packet_key"],
            "command_center_3_legacy_audit_observation_dry_run_packet",
        )
        payload = task["payload_safe"]
        receipt = payload["legacy_audit_observation_receipt"]
        rows = {row["criterion"]: row for row in payload["legacy_audit_observation_rows"]}

        self.assertEqual(receipt["status"], "legacy_audit_observation_dry_run_recorded_no_keep_promotion")
        self.assertEqual(receipt["workflow_group"], "searched-symbol quant projection")
        self.assertTrue(receipt["workflow_group_known"])
        self.assertEqual(receipt["proposed_status"], "direct_evidence_observed_redesign_required")
        self.assertTrue(receipt["direct_user_evidence_recorded"])
        self.assertFalse(receipt["direct_evidence_ready_for_keep_review"])
        self.assertFalse(receipt["keep_promotion_allowed_this_round"])
        self.assertFalse(receipt["ordinary_entry_promotion_allowed_this_round"])
        self.assertFalse(receipt["streamlit_fallback_retirement_allowed"])
        self.assertFalse(receipt["production_evidence"])
        self.assertTrue(receipt["observation_dry_run_only"])
        self.assertFalse(receipt["opens_streamlit"])
        self.assertFalse(receipt["runs_legacy_tools"])
        self.assertFalse(receipt["creates_followup_tasks"])
        self.assertFalse(receipt["external_calls_triggered"])
        self.assertTrue(rows["required_intake_fields_present"]["passed"])
        self.assertTrue(rows["workflow_group_in_first_round_scope"]["passed"])
        self.assertTrue(rows["safe_evidence_attachment_source"]["passed"])
        self.assertTrue(rows["no_keep_or_ordinary_promotion_this_round"]["passed"])

        ledger = task["call_ledger"][0]
        self.assertEqual(ledger["api"], "local_legacy_audit_observation_dry_run")
        self.assertEqual(ledger["call_status"], "legacy_audit_observation_dry_run_recorded_no_keep_promotion")
        self.assertFalse(ledger["external"])
        self.assertFalse(ledger["tushare_called"])
        self.assertFalse(ledger["deepseek_called"])
        self.assertFalse(ledger["github_called"])
        self.assertTrue(ledger["does_not_open_streamlit"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])

        rendered = json.dumps(task, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", rendered)
        self.assertNotIn("api_key", rendered)
        self.assertNotIn("raw_packet_bodies", rendered)

    def test_keep_request_is_blocked_even_with_complete_payload(self) -> None:
        response = self.client.post(
            "/api/legacy/audit-observation-dry-run",
            json={
                "workflow_group": "candidate radar",
                "user_observation": "Reviewer saw candidate labels read like recommendations.",
                "legacy_ux_bug_or_patchwork": "Candidate copy was action-like and full-pool boundary was unclear.",
                "data_lineage_observation": "Last radar cache was visible but provider/browser evidence was pending.",
                "replacement_user_path": "下一票雷达 / Candidate Radar",
                "frozen_legacy_path": "legacy recommendation-style radar copy",
                "evidence_attachment": "redacted_reviewer_note: radar-note-2026-06-22",
                "evidence_attachment_type": "redacted_reviewer_note",
                "requested_status": "KEEP",
                "keep_promotion_decision": "KEEP",
            },
        )

        self.assertEqual(response.status_code, 200)
        task = self._task_from_response(response)
        receipt = task["payload_safe"]["legacy_audit_observation_receipt"]
        self.assertEqual(
            task["current_step"],
            "legacy_audit_observation_dry_run_blocked_keep_promotion_not_allowed",
        )
        self.assertEqual(
            receipt["status"],
            "legacy_audit_observation_dry_run_blocked_keep_promotion_not_allowed",
        )
        self.assertTrue(receipt["keep_request_rejected"])
        self.assertFalse(receipt["direct_user_evidence_recorded"])
        self.assertFalse(receipt["keep_promotion_allowed_this_round"])
        self.assertFalse(receipt["ordinary_entry_promotion_allowed_this_round"])
        self.assertFalse(receipt["streamlit_fallback_retirement_allowed"])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])


if __name__ == "__main__":
    unittest.main()
