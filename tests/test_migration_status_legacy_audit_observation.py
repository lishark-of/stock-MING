from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.services import legacy_service, migration_status_service, task_service
from server.services.task_service import clear_task_statuses_for_tests


class MigrationStatusLegacyAuditObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.meta_store = Path(self._tmp.name) / "meta.sqlite"
        self._meta_patch = patch.object(task_service, "SQLITE_META_PATH", self.meta_store)
        self._meta_patch.start()
        clear_task_statuses_for_tests(clear_persisted=True)

    def tearDown(self) -> None:
        clear_task_statuses_for_tests(clear_persisted=True)
        self._meta_patch.stop()
        self._tmp.cleanup()

    def test_migration_status_replays_latest_observation_without_promotion(self) -> None:
        missing_status = migration_status_service.build_migration_status()
        missing_latest = missing_status["legacy_audit_latest_observation"]
        self.assertEqual(
            missing_latest["status"],
            "no_legacy_audit_observation_dry_run_task_found",
        )
        self.assertFalse(missing_latest["latest_task_found"])
        self.assertFalse(missing_latest["lookup_creates_task"])
        self.assertEqual(missing_latest["row_count"], 0)
        self.assertFalse(missing_status["legacy_audit_latest_observation_visible"])

        task = legacy_service.run_legacy_audit_observation_dry_run_task(
            {
                "workflow_group": "searched-symbol quant projection",
                "user_observation": "Reviewer searched 000001.SZ and had to jump through legacy tabs before projection.",
                "legacy_ux_bug_or_patchwork": "Legacy projection path hides the next click and mixes debug copy into ordinary flow.",
                "data_lineage_observation": "Cache/provider/pending states were partly visible; DeepSeek wording needed explanation-only guardrails.",
                "replacement_user_path": "股票量化推演 / Stock Quant Projection -> 生成 3.0 量化推演",
                "frozen_legacy_path": "legacy single-stock room synchronous projection",
                "evidence_attachment": "safe_log_summary: migration-status-observation-note",
                "evidence_attachment_type": "safe_log_summary",
                "requested_status": "direct_evidence_observed_redesign_required",
                "keep_promotion_decision": "no_keep_promotion_this_round",
                "requested_by": "local-reviewer",
                "api_key": "SHOULD_DROP",
            }
        )
        self.assertEqual(task["status"], "success")
        task_count_before_status = len(task_service.list_task_statuses())

        status = migration_status_service.build_migration_status()

        self.assertEqual(len(task_service.list_task_statuses()), task_count_before_status)
        latest = status["legacy_audit_latest_observation"]
        rows = status["legacy_audit_latest_observation_rows"]
        self.assertEqual(
            latest["status"],
            "latest_legacy_audit_observation_visible_recorded",
        )
        self.assertFalse(latest["lookup_creates_task"])
        self.assertTrue(latest["latest_task_found"])
        self.assertEqual(latest["task_id"], task["task_id"])
        self.assertEqual(latest["workflow_group"], "searched-symbol quant projection")
        self.assertEqual(latest["proposed_status"], "direct_evidence_observed_redesign_required")
        self.assertTrue(latest["direct_user_evidence_recorded"])
        self.assertFalse(latest["direct_evidence_ready_for_keep_review"])
        self.assertFalse(latest["keep_promotion_allowed_this_round"])
        self.assertFalse(latest["ordinary_entry_promotion_allowed_this_round"])
        self.assertFalse(latest["streamlit_fallback_retirement_allowed"])
        self.assertFalse(latest["production_evidence"])
        self.assertFalse(latest["external_calls_triggered"])
        self.assertFalse(latest["tushare_called"])
        self.assertFalse(latest["deepseek_called"])
        self.assertFalse(latest["github_called"])
        self.assertTrue(latest["does_not_open_streamlit"])
        self.assertTrue(latest["does_not_run_legacy_tools"])
        self.assertTrue(latest["does_not_execute_trades"])
        self.assertTrue(latest["does_not_modify_strategy_action"])
        self.assertFalse(latest["contains_secret"])
        self.assertEqual(latest["row_count"], len(rows))
        self.assertGreater(len(rows), 0)

        ledger = status["call_ledger"][0]
        self.assertFalse(ledger["external"])
        self.assertFalse(ledger["external_calls_triggered"])
        self.assertTrue(ledger["legacy_audit_latest_observation_found"])
        self.assertEqual(ledger["legacy_audit_latest_observation_row_count"], len(rows))
        self.assertTrue(ledger["legacy_audit_latest_observation_direct_user_evidence_recorded"])
        self.assertTrue(status["legacy_audit_latest_observation_visible"])
        self.assertTrue(status["legacy_audit_latest_observation_direct_user_evidence_recorded"])
        self.assertTrue(status["legacy_audit_latest_observation_is_not_keep_promotion"])
        self.assertTrue(status["legacy_audit_latest_observation_is_not_streamlit_retirement"])

        rendered = json.dumps(status, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", rendered)
        self.assertNotIn("api_key", rendered)


if __name__ == "__main__":
    unittest.main()
