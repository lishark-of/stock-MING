from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from storage.sqlite_meta import SQLiteMetaStore
from server.api import routes_next_session
from server.services import next_session_replacement_promotion_service as promotion


HEAD = "a" * 40
PROVIDER_SCOPE = "b" * 64
DATASET_VERSION = "c" * 64
DAILY_ROWS_DIGEST = "d" * 64
TRADE_CALENDAR_DIGEST = "e" * 64


def _source_task() -> dict:
    return {
        "task_id": "provider-task-current-head",
        "task_type": "run_tushare_full_market_production",
        "status": "success",
        "head_full": HEAD,
        "symbol": "000001.SZ",
        "data_date": "20260301",
        "provider_scope_hash": PROVIDER_SCOPE,
        "dataset_version_digest": DATASET_VERSION,
        "daily_rows_digest": DAILY_ROWS_DIGEST,
        "trade_calendar_digest": TRADE_CALENDAR_DIGEST,
        "external_calls_triggered": True,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }


def _packet(source_task: dict) -> dict:
    historical = [
        {
            "x": (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
            "price": 10.0 + index,
            "source": "tushare.daily.close",
        }
        for index in range(60)
    ]
    return {
        "schema_version": "next_session_projection.v1",
        "packet_key": "command_center_next_session_projection_packet",
        "status": "ready_cache_replay",
        "chart_payload": {
            "status": "ready",
            "is_exact_next_session_packet": True,
            "uses_real_daily_close": True,
            "historical_points": historical,
            "reference_lines": [{"name": "latest_close"}],
            "operation_zones": [{"name": "observe"}],
            "chart_maturity": {
                "status": "ready",
                "has_real_60d_close": True,
                "scenario_anchor_count": 2,
                "scenario_anchored_count": 2,
            },
            "chart_contract": {
                "cache_only": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "frontend_computes_trade_action": False,
                "does_not_modify_action": True,
                "does_not_modify_operation_zones": True,
            },
        },
        "chart_summary": {
            "is_exact_next_session_packet": True,
            "uses_real_daily_close": True,
        },
        "next_session_same_packet_signal_capability_coverage": {
            "schema_version": "next_session_same_packet_signal_capability_coverage.v1",
            "status": "same_packet_signal_capability_coverage_ready",
            "same_packet": True,
            "lineage_bound": True,
            "direct_evidence_ready": True,
            "required_feature_group_count": 9,
            "retained_feature_group_count": 9,
            "missing_feature_groups": [],
        },
        "production_replacement_provenance": {
            "schema_version": "next_session_production_replacement_provenance.v1",
            "status": "authoritative_provider_dataset_current_head",
            "head_full": HEAD,
            "source_task_id": source_task["task_id"],
            "source_task_status": "success",
            "source_task_digest": promotion._digest(source_task),
            "symbol": "000001.SZ",
            "data_date": "20260301",
            "provider_scope_hash": PROVIDER_SCOPE,
            "dataset_version_digest": DATASET_VERSION,
            "daily_rows_digest": DAILY_ROWS_DIGEST,
            "trade_calendar_digest": TRADE_CALENDAR_DIGEST,
            "provider_backed": True,
            "authoritative_dataset": True,
            "trade_calendar_validated": True,
            "synthetic_fixture": False,
            "local_preview": False,
        },
        "contains_secret": False,
    }


def _authoritative() -> dict:
    return {
        "ready": True,
        "blockers": [],
        "symbol": "000001.SZ",
        "data_date": "20260301",
        "provider_scope_hash": PROVIDER_SCOPE,
        "dataset_version_digest": DATASET_VERSION,
        "daily_rows_digest": DAILY_ROWS_DIGEST,
        "trade_calendar_digest": TRADE_CALENDAR_DIGEST,
        "validated_trade_date": "20260301",
        "row_count": 60,
    }


class NextSessionReplacementPromotionFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / ".stock_ming_3"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def assert_structurally_blocked(self, result: dict) -> None:
        self.assertFalse(result["production_replacement_complete"])
        self.assertFalse(result["next_session_production_replacement"])
        self.assertIn("external_trusted_approval_capability_unavailable", result["blockers"])
        self.assertIn("rollback_resistant_high_water_unavailable", result["blockers"])

    def test_get_validation_is_zero_write_and_structurally_fail_closed(self) -> None:
        before = set(self.base.iterdir())
        result = promotion.validate_next_session_production_replacement(
            self.root,
            expected_head_full=HEAD,
            project_root=self.base,
        )
        self.assert_structurally_blocked(result)
        self.assertEqual(before, set(self.base.iterdir()))
        self.assertTrue(result["read_only"])
        self.assertFalse(result["writes_storage"])

    def test_in_process_approval_and_writer_calls_cannot_self_seal(self) -> None:
        with patch.object(promotion, "_current_head", return_value=HEAD):
            preview = promotion.validate_next_session_production_replacement(
                self.root,
                expected_head_full=HEAD,
                project_root=self.base,
            )
            approval = promotion.record_next_session_replacement_approval_ticket(
                evidence_root=self.root,
                expected_head_full=HEAD,
                semantic_digest=preview["approval_semantic_digest"],
                review_id=preview["approval_review_id"],
                approved_by_user=True,
                project_root=self.base,
            )
            written = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=self.base,
            )
        self.assertFalse(approval["ticket_written"])
        self.assertFalse(approval["production_eligible"])
        self.assertTrue(approval["local_qa_only"])
        self.assert_structurally_blocked(written)
        self.assertFalse(written["promotion_written"])
        self.assertFalse(written["writes_storage"])
        self.assertFalse(self.root.exists())

    def test_whole_tree_rollback_or_forged_local_tree_never_becomes_production(self) -> None:
        journal = self.root / promotion.ROOT_NAME
        events = journal / promotion.EVENTS_NAME
        trust = journal / promotion.TRUST_NAME
        events.mkdir(parents=True, mode=0o700)
        trust.mkdir(mode=0o700)
        (trust / promotion.KEY_NAME).write_bytes(b"x" * 32)
        os.chmod(trust / promotion.KEY_NAME, 0o600)
        forged_snapshot = self.base / "forged-snapshot"
        shutil.copytree(self.root, forged_snapshot)
        shutil.rmtree(self.root)
        shutil.copytree(forged_snapshot, self.root)
        result = promotion.validate_next_session_production_replacement(
            self.root,
            expected_head_full=HEAD,
            project_root=self.base,
        )
        self.assert_structurally_blocked(result)
        self.assertEqual(result["event_id"], "")

    def test_forged_ready_prerequisites_and_old_event_still_cannot_promote(self) -> None:
        self.root.mkdir(mode=0o700)
        forged = self.root / promotion.ROOT_NAME / promotion.EVENTS_NAME
        forged.mkdir(parents=True, mode=0o700)
        (forged / "00000001.json").write_text(
            json.dumps({"status": "next_session_production_replacement_promoted"}),
            encoding="utf-8",
        )
        os.chmod(forged / "00000001.json", 0o600)
        prerequisites = {
            "ready": True,
            "head_full": HEAD,
            "semantic_digest": "f" * 64,
            "material": {},
            "next_packet": {"ready": True},
            "motion_pair": {"ready": True},
            "streamlit_retirement": {"ready": True},
            "remote_ci": {"ready": True},
            "blockers": [],
        }
        before = (forged / "00000001.json").read_bytes()
        with patch.object(promotion, "_collect_prerequisites", return_value=prerequisites):
            validated = promotion.validate_next_session_production_replacement(
                self.root,
                expected_head_full=HEAD,
                project_root=self.base,
            )
            promoted = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=self.base,
            )
        self.assert_structurally_blocked(validated)
        self.assert_structurally_blocked(promoted)
        self.assertFalse(promoted["promotion_written"])
        self.assertFalse(promoted["writes_storage"])
        self.assertEqual((forged / "00000001.json").read_bytes(), before)

    def test_unpersisted_or_mismatched_source_task_is_not_lineage(self) -> None:
        source_task = _source_task()
        packet = _packet(source_task)
        absent, absent_blockers = promotion._next_packet_evidence(
            packet,
            head_full=HEAD,
            authoritative=_authoritative(),
            source_task={},
        )
        self.assertFalse(absent["immutable_source_task_status_verified"])
        self.assertFalse(absent["authoritative_current_head_lineage"])
        self.assertIn("next_session_authoritative_current_head_lineage_missing_or_invalid", absent_blockers)

        mismatched = dict(source_task)
        mismatched["dataset_version_digest"] = "0" * 64
        rejected, _ = promotion._next_packet_evidence(
            packet,
            head_full=HEAD,
            authoritative=_authoritative(),
            source_task=mismatched,
        )
        self.assertFalse(rejected["immutable_source_task_status_verified"])

    def test_source_task_requires_current_and_append_only_history_readback(self) -> None:
        self.root.mkdir(mode=0o700)
        task = _source_task()
        store = SQLiteMetaStore(self.root / "meta.sqlite")
        store.write_task_status(task)
        self.assertEqual(
            promotion._read_immutable_source_task_status(self.root, task["task_id"]),
            task,
        )
        connection = store._connect()
        try:
            changed = {**task, "status": "failed"}
            connection.execute(
                "UPDATE task_status SET payload_json = ? WHERE task_id = ?",
                (json.dumps(changed), task["task_id"]),
            )
            connection.commit()
        finally:
            connection.close()
        self.assertEqual(promotion._read_immutable_source_task_status(self.root, task["task_id"]), {})

    def test_root_or_descendant_symlink_is_rejected(self) -> None:
        actual = self.base / "actual"
        actual.mkdir()
        symlink_root = self.base / "linked-evidence"
        symlink_root.symlink_to(actual, target_is_directory=True)
        result = promotion.validate_next_session_production_replacement(
            symlink_root,
            expected_head_full=HEAD,
            project_root=self.base,
        )
        self.assert_structurally_blocked(result)
        self.assertIn("next_session_replacement_evidence_root_symlink_invalid", result["blockers"])

        self.root.mkdir(mode=0o700)
        (self.root / "linked-child").symlink_to(actual, target_is_directory=True)
        descendant = promotion.validate_next_session_production_replacement(
            self.root,
            expected_head_full=HEAD,
            project_root=self.base,
        )
        self.assertIn("next_session_replacement_evidence_tree_symlink_invalid", descendant["blockers"])

    def test_handwritten_remote_json_is_not_production_evidence(self) -> None:
        release_root = self.root / "release_gate"
        release_root.mkdir(parents=True)
        raw = {
            "head_full": HEAD,
            "actions_status": "completed",
            "actions_conclusion": "success",
            "review_authorized": True,
        }
        path = release_root / "remote_ci_review_receipt.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        result = promotion.validate_next_session_production_replacement(
            self.root,
            expected_head_full=HEAD,
            project_root=self.base,
        )
        self.assert_structurally_blocked(result)
        self.assertFalse(result["remote_ci_evidence"].get("ready", False))
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), raw)

    def test_routes_keep_get_read_only_and_post_local_qa_fail_closed(self) -> None:
        blocked = {
            "status": "next_session_production_replacement_blocked",
            "production_replacement_complete": False,
            "promotion_written": False,
            "idempotent_replay": False,
            "blockers": list(promotion.STRUCTURAL_PRODUCTION_BLOCKERS),
        }
        with patch.object(
            routes_next_session.next_session_replacement_promotion_service,
            "validate_next_session_production_replacement",
            return_value=blocked,
        ):
            get_result = routes_next_session.get_next_session_production_replacement()
        with patch.object(
            routes_next_session.next_session_replacement_promotion_service,
            "promote_next_session_production_replacement",
            return_value=blocked,
        ):
            post_result = routes_next_session.promote_next_session_production_replacement(
                {"approved_by_user": True}
            )
        self.assertEqual(get_result["call_ledger"][0]["mode"], "read_only_validation")
        self.assertEqual(
            post_result["call_ledger"][0]["mode"],
            "local_qa_review_only_production_fail_closed",
        )
        self.assertFalse(get_result["data"]["production_replacement_complete"])
        self.assertFalse(post_result["call_ledger"][0]["promotion_written"])


if __name__ == "__main__":
    unittest.main()
