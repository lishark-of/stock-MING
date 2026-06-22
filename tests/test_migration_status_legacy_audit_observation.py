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

    def test_migration_status_page_exposes_button_gated_first_round_workbench(self) -> None:
        root = Path(__file__).resolve().parents[1]
        client_source = (root / "desktop" / "src" / "api" / "client.ts").read_text(encoding="utf-8")
        migration_source = (
            root / "desktop" / "src" / "routes" / "MigrationStatus.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("postLegacyAuditObservationDryRun", client_source)
        self.assertIn("/api/legacy/audit-observation-dry-run", client_source)
        self.assertIn("Legacy audit first-round workbench", migration_source)
        self.assertIn("focus workflow / required fields / safe attachment sources", migration_source)
        self.assertIn("legacyAuditFirstRoundFocusRows", migration_source)
        self.assertIn("legacyAuditRequiredFieldRows", migration_source)
        self.assertIn("legacyAuditAttachmentSourceRows", migration_source)
        self.assertIn("legacyAuditLatestObservation", migration_source)
        self.assertIn("legacyAuditLatestObservationRows", migration_source)
        self.assertIn("launchLegacyAuditObservationDryRun", migration_source)
        self.assertIn("postLegacyAuditObservationDryRun", migration_source)
        self.assertIn(
            'legacyAuditObservationFocusWorkflow = "searched-symbol quant projection"',
            migration_source,
        )
        self.assertIn(
            'legacyAuditObservationNextClick = "记录搜票量化观察 dry-run"',
            migration_source,
        )
        self.assertIn("只允许 redacted reviewer note；不贴 raw packet/raw log/token/key/未脱敏模型输出", migration_source)
        self.assertIn("只生成本地 observation dry-run；不打开 Streamlit、不调用 provider/model、不升级 KEEP 或 ordinary entry", migration_source)
        self.assertIn(
            "<button onClick={launchLegacyAuditObservationDryRun}>{legacyAuditObservationNextClick}</button>",
            migration_source,
        )
        self.assertIn("redacted_reviewer_note: migration-status-observation-dry-run", migration_source)
        self.assertIn("direct_evidence_observed_redesign_required", migration_source)
        self.assertIn("no_keep_promotion_this_round", migration_source)
        self.assertIn("TaskLaunchReceipt receipt={legacyAuditObservationReceipt}", migration_source)
        self.assertIn("TaskStatusPanel taskId={legacyAuditObservationTaskId}", migration_source)
        self.assertIn('label: "KEEP review"', migration_source)
        self.assertIn('label: "Streamlit fallback"', migration_source)
        self.assertIn("Latest observation 只是 direct-evidence intake 回放", migration_source)
        self.assertIn("KEEP review、ordinary entry 和 Streamlit fallback retirement 都保持 blocked", migration_source)
        self.assertIn("直到单独补齐完整 Legacy Bug / UX Audit 直接证据", migration_source)
        self.assertIn("must_collect_before_keep_or_ordinary_entry_review", migration_source)
        self.assertIn("safe_reference_allowed", migration_source)
        self.assertIn("forbidden_raw_or_generated_source", migration_source)
        self.assertIn("raw_content_allowed", migration_source)
        self.assertNotIn("postLegacyAuditObservationDryRun()", migration_source)
        self.assertNotIn("keep_promotion_allowed_this_round: true", migration_source)
        self.assertNotIn("streamlit_fallback_retirement_allowed: true", migration_source)


if __name__ == "__main__":
    unittest.main()
