from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.main import app
from server.services import audit_service, release_promotion_service, v1_closeout_service


def _head_full() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
    ).strip()


def _safe_boundary(*, cache_fields: bool = False) -> dict:
    payload = {
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    if cache_fields:
        payload.update(
            {
                "cache_get_external_calls": False,
                "cache_get_calls_github_api": False,
            }
        )
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class ReleasePromotionJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.evidence_root = Path(self.temp_dir.name) / ".stock_ming_3"
        self.release_root = self.evidence_root / "release_gate"
        self.head = _head_full()
        self.run_id = "29399999999"
        self.artifact_digest = "sha256:" + "a" * 64
        self._seed_formal_evidence()

    def _seed_formal_evidence(self, *, tamper_release_completion: bool = False) -> None:
        _write_json(
            self.release_root / "local_push_gate_run_receipt.json",
            {
                "schema_version": audit_service.LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION,
                "status": "local_push_gate_passed_current_head",
                "scope": "ignored_local_push_gate_run_receipt_no_push_no_github_api",
                "generated_at_utc": "2026-07-15T00:00:00Z",
                "branch": "main",
                "head": self.head[:8],
                "head_full": self.head,
                "origin_ahead_count": "0",
                "report_path": ".stock_ming_3/release_gate/local_push_gate_report.md",
                "checks": sorted(audit_service.LOCAL_PUSH_GATE_REQUIRED_CHECKS),
                "did_not_push": True,
                "git_add_dot_used": False,
                "local_gate_pass_is_not_ci_status": True,
                "remote_actions_status_known": False,
                "latest_remote_run_verified_green": False,
                "explicit_user_push_confirmation_before_push": False,
                "push_confirmation_state": "not_requested_no_push",
                "release_claim_decision": "blocked_remote_ci_unverified",
                "remote_ci_status_note": (
                    "local push gate pass is not remote CI green; inspect matching remote "
                    "Actions run before release."
                ),
                **_safe_boundary(),
            },
        )

        _write_json(
            self.release_root / "remote_ci_review_receipt.json",
            {
                "schema_version": audit_service.REMOTE_CI_REVIEW_RECEIPT_SCHEMA_VERSION,
                "status": "remote_ci_review_verified_green",
                "scope": "ignored_manual_remote_ci_review_receipt_no_cache_github_api",
                "reviewed_at_utc": "2026-07-15T00:01:00Z",
                "receipt_writer": "scripts/record_remote_ci_review_receipt.py",
                "branch": "main",
                "head": self.head[:8],
                "head_full": self.head,
                "workflow_name": "Command Center 3 Push Gate",
                "event": "push",
                "run_id": int(self.run_id),
                "run_url": f"https://github.com/lishark-of/stock-MING/actions/runs/{self.run_id}",
                "actions_status": "completed",
                "actions_conclusion": "success",
                "job_name": "push-gate",
                "job_conclusion": "success",
                "artifact_name": f"command-center-3-push-gate-evidence-{self.run_id}",
                "artifact_digest": self.artifact_digest,
                "artifact_digest_verified": True,
                "artifact_digest_review_status": "sha256_digest_recorded",
                "failed_step_or_green_status": "green",
                "safe_failure_log_excerpt_or_green_run_url": (
                    f"https://github.com/lishark-of/stock-MING/actions/runs/{self.run_id}"
                ),
                "explicit_user_actions_review_authorized": True,
                "remote_actions_status_known": True,
                "latest_remote_run_verified_green": True,
                "remote_ci_job_page_green_observed": True,
                "remote_ci_artifact_digest_pending": False,
                "remote_ci_run_observed_for_current_head": True,
                "remote_ci_run_in_progress_for_current_head": False,
                "remote_ci_no_matching_run_found_for_current_head": False,
                "remote_ci_run_lookup_attempted": False,
                "remote_ci_lookup_source": "",
                "remote_ci_failure_reviewed_for_current_head": False,
                "remote_ci_failure_artifact_download_status": "",
                "remote_ci_failure_artifact_download_blocked": False,
                "release_claim_decision": "remote_ci_green_release_review_pending",
                "remote_ci_review_receipt_is_not_release_review": True,
                "release_review_complete": False,
                "release_gate_complete": False,
                "production_release_complete": False,
                **_safe_boundary(cache_fields=True),
            },
        )
        _write_json(
            self.release_root / "secret_artifact_allowlist_review_receipt.json",
            {
                "schema_version": audit_service.SECRET_ARTIFACT_ALLOWLIST_REVIEW_RECEIPT_SCHEMA_VERSION,
                "status": "secret_artifact_allowlist_review_ready",
                "scope": "ignored_manual_secret_artifact_allowlist_review_no_cache_github_api",
                "reviewed_at_utc": "2026-07-15T00:02:00Z",
                "receipt_writer": "scripts/record_secret_artifact_allowlist_review_receipt.py",
                "reviewer": "local-reviewer",
                "branch": "main",
                "head": self.head[:8],
                "head_full": self.head,
                "manual_review_note_safe": "reviewed",
                "explicit_user_allowlist_review_authorized": True,
                "periodic_allowlist_review_ready": True,
                "false_positive_allowlist_review_ready": True,
                "high_risk_secret_scan_status": "passed_no_high_risk_values",
                "secret_keyword_review_status": "reviewed_no_high_risk_values",
                "generated_artifact_scan_status": "clean_or_allowed_assets_only",
                "release_review_complete": False,
                "release_gate_complete": False,
                "production_release_complete": False,
                **_safe_boundary(cache_fields=True),
            },
        )
        _write_json(
            self.release_root / "release_gate_review_receipt.json",
            {
                "schema_version": audit_service.RELEASE_GATE_REVIEW_RECEIPT_SCHEMA_VERSION,
                "status": "release_gate_review_ready",
                "scope": "ignored_manual_release_gate_review_no_cache_github_api",
                "reviewed_at_utc": "2026-07-15T00:03:00Z",
                "receipt_writer": "scripts/record_release_gate_review_receipt.py",
                "reviewer": "local-reviewer",
                "branch": "main",
                "head": self.head[:8],
                "head_full": self.head,
                "manual_review_note_safe": "reviewed",
                "remote_run_id": self.run_id,
                "remote_artifact_digest": self.artifact_digest,
                "decision": "release_review_complete_strict_closeout_blocked",
                "explicit_user_release_review_authorized": True,
                "release_review_complete": True,
                "release_gate_complete": tamper_release_completion,
                "strict_closeout_ready": False,
                "can_close_goal": False,
                "production_release_complete": tamper_release_completion,
                **_safe_boundary(cache_fields=True),
            },
        )

    def _reset_promotion_storage(self) -> None:
        (self.release_root / release_promotion_service.JOURNAL_NAME).unlink(
            missing_ok=True
        )
        trust_directory, _ = release_promotion_service._trust_paths(self.evidence_root)
        shutil.rmtree(trust_directory, ignore_errors=True)

    def _advance_remote_evidence(self) -> None:
        next_run_id = str(int(self.run_id) + 1)
        remote_path = self.release_root / "remote_ci_review_receipt.json"
        remote = json.loads(remote_path.read_text(encoding="utf-8"))
        remote.update(
            {
                "run_id": int(next_run_id),
                "run_url": (
                    "https://github.com/lishark-of/stock-MING/actions/runs/"
                    f"{next_run_id}"
                ),
                "safe_failure_log_excerpt_or_green_run_url": (
                    "https://github.com/lishark-of/stock-MING/actions/runs/"
                    f"{next_run_id}"
                ),
                "artifact_name": (
                    f"command-center-3-push-gate-evidence-{next_run_id}"
                ),
            }
        )
        _write_json(remote_path, remote)
        review_path = self.release_root / "release_gate_review_receipt.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["remote_run_id"] = next_run_id
        _write_json(review_path, review)

    def test_read_only_validation_does_not_create_journal_or_trust_true_json_flags(self) -> None:
        self._seed_formal_evidence(tamper_release_completion=True)
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        result = release_promotion_service.validate_production_release_promotion(
            self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(result["release_promotion_current_head"])
        self.assertIn("production_release_promotion_journal_missing", result["blockers"])
        self.assertFalse(journal.exists())

        evaluation = v1_closeout_service.build_v1_closeout_evaluation(
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        facts = {row["evidence_key"]: row["observed"] for row in evaluation["production_fact_rows"]}
        self.assertFalse(facts["release_promotion_current_head"])
        self.assertFalse(evaluation["production_release_promotion_summary"]["writes_storage"])
        self.assertFalse(journal.exists())

    def test_api_separates_read_only_get_from_explicit_post(self) -> None:
        operations = app.openapi()["paths"]["/api/audit/production-release-promotion"]
        self.assertIn("get", operations)
        self.assertIn("post", operations)

    def test_explicit_approval_is_required_before_any_write(self) -> None:
        result = release_promotion_service.promote_production_release(
            {"approved_by_user": False, "release_gate_complete": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(result["promotion_written"])
        self.assertIn("explicit_user_production_promotion_approval_required", result["blockers"])
        self.assertFalse((self.release_root / release_promotion_service.JOURNAL_NAME).exists())
        trust_directory, key_path = release_promotion_service._trust_paths(
            self.evidence_root
        )
        self.assertFalse(trust_directory.exists())
        self.assertFalse(key_path.exists())

    def test_get_is_zero_write_before_and_after_key_installation(self) -> None:
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        trust_directory, key_path = release_promotion_service._trust_paths(
            self.evidence_root
        )
        before_receipts = {
            path.name: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.release_root.glob("*.json")
        }
        first_get = release_promotion_service.validate_production_release_promotion(
            self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(first_get["release_promotion_current_head"])
        self.assertFalse(journal.exists())
        self.assertFalse(trust_directory.exists())
        self.assertEqual(
            before_receipts,
            {
                path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.release_root.glob("*.json")
            },
        )

        created = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(created["release_promotion_current_head"])
        before_journal = (journal.read_bytes(), journal.stat().st_mtime_ns)
        before_key = (key_path.read_bytes(), key_path.stat().st_mtime_ns)
        state_path = release_promotion_service._trust_state_path(self.evidence_root)
        before_state = (state_path.read_bytes(), state_path.stat().st_mtime_ns)
        before_entries = sorted(path.name for path in trust_directory.iterdir())
        second_get = release_promotion_service.validate_production_release_promotion(
            self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(second_get["release_promotion_current_head"])
        self.assertEqual(before_journal, (journal.read_bytes(), journal.stat().st_mtime_ns))
        self.assertEqual(before_key, (key_path.read_bytes(), key_path.stat().st_mtime_ns))
        self.assertEqual(
            before_state,
            (state_path.read_bytes(), state_path.stat().st_mtime_ns),
        )
        self.assertEqual(
            before_entries,
            sorted(path.name for path in trust_directory.iterdir()),
        )

    def test_public_digest_and_exact_schema_cannot_self_seal_without_key(self) -> None:
        prerequisites = release_promotion_service.validate_release_prerequisites(
            self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(prerequisites["ready"])
        rows = {
            row["evidence_key"]: row
            for row in prerequisites["rows"]
        }
        semantic_material = release_promotion_service._event_semantic_material(
            schema_version=release_promotion_service.EVENT_SCHEMA_VERSION,
            scope=release_promotion_service.PROMOTION_SCOPE,
            head_full=self.head,
            local_gate_digest=rows["local_push_gate"]["semantic_digest"],
            remote_ci_digest=rows["remote_ci"]["semantic_digest"],
            allowlist_digest=rows["allowlist"]["semantic_digest"],
            release_review_digest=rows["release_review"]["semantic_digest"],
            remote_run_id=prerequisites["remote_run_id"],
            remote_artifact_digest=prerequisites["remote_artifact_digest"],
        )
        semantic_digest = release_promotion_service._digest(semantic_material)
        promoted_at = "2026-07-15T00:04:00Z"
        canonical_event = release_promotion_service._canonical_event_material(
            semantic_material,
            sequence_no=1,
            semantic_digest=semantic_digest,
            promoted_at_utc=promoted_at,
            previous_event_mac="",
        )
        public_event_id = release_promotion_service._digest(canonical_event)
        fabricated_mac = "f" * 64
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        with sqlite3.connect(journal) as connection:
            connection.execute(release_promotion_service._CREATE_EVENT_TABLE_DDL)
            connection.execute(release_promotion_service._CREATE_CURRENT_TABLE_DDL)
            connection.execute(
                release_promotion_service._CREATE_EVENT_NO_UPDATE_TRIGGER_DDL
            )
            connection.execute(
                release_promotion_service._CREATE_EVENT_NO_DELETE_TRIGGER_DDL
            )
            connection.execute(
                "INSERT INTO production_release_promotion_events VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    public_event_id,
                    1,
                    semantic_digest,
                    release_promotion_service.EVENT_SCHEMA_VERSION,
                    release_promotion_service.PROMOTION_SCOPE,
                    self.head,
                    semantic_material["local_gate_digest"],
                    semantic_material["remote_ci_digest"],
                    semantic_material["allowlist_digest"],
                    semantic_material["release_review_digest"],
                    semantic_material["remote_run_id"],
                    semantic_material["remote_artifact_digest"],
                    1,
                    promoted_at,
                    "",
                    fabricated_mac,
                ),
            )
            connection.execute(
                "INSERT INTO production_release_promotion_current VALUES "
                "(?, ?, ?, ?, ?, ?)",
                (
                    release_promotion_service.PROMOTION_SCOPE,
                    public_event_id,
                    1,
                    self.head,
                    promoted_at,
                    fabricated_mac,
                ),
            )
        before = journal.read_bytes()
        trust_directory, key_path = release_promotion_service._trust_paths(
            self.evidence_root
        )

        read_result = release_promotion_service.validate_production_release_promotion(
            self.evidence_root,
            expected_head_full=self.head,
        )
        post_result = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(read_result["release_promotion_current_head"])
        self.assertFalse(post_result["promotion_written"])
        self.assertIn(
            release_promotion_service._TRUST_KEY_MISSING_BLOCKER,
            read_result["blockers"],
        )
        self.assertIn(
            release_promotion_service._TRUST_KEY_MISSING_BLOCKER,
            post_result["blockers"],
        )
        self.assertFalse(trust_directory.exists())
        self.assertFalse(key_path.exists())
        self.assertEqual(journal.read_bytes(), before)

    def test_valid_promotion_is_append_only_bound_and_idempotent(self) -> None:
        first = release_promotion_service.promote_production_release(
            {"approved_by_user": True, "production_release_complete": False},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(first["release_promotion_current_head"])
        self.assertTrue(first["promotion_written"])
        self.assertFalse(first["idempotent_replay"])
        self.assertEqual(len(first["journal_schema_fingerprint"]), 64)
        self.assertNotIn("event_mac", first)
        trust_directory, key_path = release_promotion_service._trust_paths(
            self.evidence_root
        )
        self.assertEqual(os.stat(trust_directory).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(key_path).st_mode & 0o777, 0o600)
        key_before = key_path.read_bytes()
        state_path = release_promotion_service._trust_state_path(self.evidence_root)
        state_before = state_path.read_bytes()
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        journal_before = (journal.read_bytes(), journal.stat().st_mtime_ns)

        second = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(second["release_promotion_current_head"])
        self.assertTrue(second["idempotent_replay"])
        with sqlite3.connect(journal) as connection:
            event_count = connection.execute(
                "SELECT COUNT(*) FROM production_release_promotion_events"
            ).fetchone()[0]
            pointer_count = connection.execute(
                "SELECT COUNT(*) FROM production_release_promotion_current"
            ).fetchone()[0]
        self.assertEqual(event_count, 1)
        self.assertEqual(pointer_count, 1)
        self.assertEqual(key_path.read_bytes(), key_before)
        self.assertEqual(state_path.read_bytes(), state_before)
        self.assertEqual(
            (journal.read_bytes(), journal.stat().st_mtime_ns),
            journal_before,
        )
        self.assertNotIn("event_mac", second)

        remote = json.loads((self.release_root / "remote_ci_review_receipt.json").read_text())
        remote["artifact_digest"] = "sha256:" + "b" * 64
        _write_json(self.release_root / "remote_ci_review_receipt.json", remote)
        stale = release_promotion_service.validate_production_release_promotion(
            self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(stale["release_promotion_current_head"])
        self.assertIn("release_review_remote_evidence_mismatch", stale["blockers"])

    def test_event_history_has_canonical_append_only_triggers(self) -> None:
        promoted = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(promoted["release_promotion_current_head"])
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        with sqlite3.connect(journal) as connection:
            triggers = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' ORDER BY name"
            ).fetchall()
            self.assertEqual(
                triggers,
                [
                    (release_promotion_service._EVENT_NO_DELETE_TRIGGER,),
                    (release_promotion_service._EVENT_NO_UPDATE_TRIGGER,),
                ],
            )
            event_id = promoted["event_id"]
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE production_release_promotion_events "
                    "SET promoted_at_utc = ? WHERE event_id = ?",
                    ("2026-07-15T01:00:00Z", event_id),
                )
            connection.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM production_release_promotion_events WHERE event_id = ?",
                    (event_id,),
                )
            connection.rollback()

        validated = release_promotion_service.validate_production_release_promotion(
            self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(validated["release_promotion_current_head"])

    def test_trigger_schema_tampering_blocks_get_and_post_without_repair(self) -> None:
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        cases = ("missing_required_trigger", "unexpected_extra_trigger")
        for case in cases:
            with self.subTest(case=case):
                self._reset_promotion_storage()
                created = release_promotion_service.promote_production_release(
                    {"approved_by_user": True},
                    evidence_root=self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertTrue(created["release_promotion_current_head"])
                with sqlite3.connect(journal) as connection:
                    if case == "missing_required_trigger":
                        connection.execute(
                            f"DROP TRIGGER {release_promotion_service._EVENT_NO_DELETE_TRIGGER}"
                        )
                    else:
                        connection.execute(
                            "CREATE TRIGGER unexpected_current_delete "
                            "BEFORE DELETE ON production_release_promotion_current "
                            "BEGIN SELECT RAISE(ABORT, 'unexpected'); END"
                        )
                before = journal.read_bytes()
                read_result = release_promotion_service.validate_production_release_promotion(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                write_result = release_promotion_service.promote_production_release(
                    {"approved_by_user": True},
                    evidence_root=self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertFalse(read_result["release_promotion_current_head"])
                self.assertFalse(write_result["promotion_written"])
                self.assertIn(
                    "production_release_promotion_journal_corrupt_or_not_sqlite",
                    read_result["blockers"],
                )
                self.assertIn(
                    "production_release_promotion_journal_corrupt_or_not_sqlite",
                    write_result["blockers"],
                )
                self.assertEqual(journal.read_bytes(), before)

    def test_invalid_or_mismatched_promotion_timestamps_fail_closed(self) -> None:
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        cases = ("invalid_event_timestamp", "pointer_timestamp_mismatch")
        for case in cases:
            with self.subTest(case=case):
                self._reset_promotion_storage()
                created = release_promotion_service.promote_production_release(
                    {"approved_by_user": True},
                    evidence_root=self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertTrue(created["release_promotion_current_head"])
                with sqlite3.connect(journal) as connection:
                    if case == "invalid_event_timestamp":
                        connection.execute(
                            f"DROP TRIGGER {release_promotion_service._EVENT_NO_UPDATE_TRIGGER}"
                        )
                        connection.execute(
                            "UPDATE production_release_promotion_events "
                            "SET promoted_at_utc = '2026-07-15T00:00:00+00:00'"
                        )
                        connection.execute(
                            release_promotion_service._EVENT_NO_UPDATE_TRIGGER_DDL
                        )
                    else:
                        connection.execute(
                            "UPDATE production_release_promotion_current "
                            "SET promoted_at_utc = '2026-07-15T00:00:00Z'"
                        )
                before = journal.read_bytes()
                read_result = release_promotion_service.validate_production_release_promotion(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                write_result = release_promotion_service.promote_production_release(
                    {"approved_by_user": True},
                    evidence_root=self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertFalse(read_result["release_promotion_current_head"])
                self.assertFalse(write_result["promotion_written"])
                self.assertIn(
                    "production_release_promotion_journal_corrupt_or_not_sqlite",
                    read_result["blockers"],
                )
                self.assertEqual(journal.read_bytes(), before)

    def test_fabricated_noncurrent_history_row_fails_closed(self) -> None:
        created = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(created["release_promotion_current_head"])
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        with sqlite3.connect(journal) as connection:
            original = connection.execute(
                "SELECT event_id, sequence_no, semantic_digest, schema_version, scope, "
                "head_full, local_gate_digest, remote_ci_digest, allowlist_digest, "
                "release_review_digest, remote_run_id, remote_artifact_digest, "
                "approved_by_user, promoted_at_utc, previous_event_mac, event_mac "
                "FROM production_release_promotion_events"
            ).fetchone()
            semantic_material = release_promotion_service._event_semantic_material(
                schema_version=original[3],
                scope=original[4],
                head_full=original[5],
                local_gate_digest=original[6],
                remote_ci_digest=original[7],
                allowlist_digest=original[8],
                release_review_digest=original[9],
                remote_run_id=original[10],
                remote_artifact_digest=original[11],
            )
            semantic_digest = release_promotion_service._digest(semantic_material)
            canonical_event = release_promotion_service._canonical_event_material(
                semantic_material,
                sequence_no=2,
                semantic_digest=semantic_digest,
                promoted_at_utc=original[13],
                previous_event_mac=original[15],
            )
            public_event_id = release_promotion_service._digest(canonical_event)
            fabricated_mac = "f" * 64
            connection.execute(
                "INSERT INTO production_release_promotion_events VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    public_event_id,
                    2,
                    semantic_digest,
                    *original[3:13],
                    original[13],
                    original[15],
                    fabricated_mac,
                ),
            )
            connection.execute(
                "UPDATE production_release_promotion_current SET event_id = ?, "
                "sequence_no = 2, promoted_at_utc = ?, event_mac = ?",
                (public_event_id, original[13], fabricated_mac),
            )
        before = journal.read_bytes()

        result = release_promotion_service.validate_production_release_promotion(
            self.evidence_root,
            expected_head_full=self.head,
        )
        post_result = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(result["release_promotion_current_head"])
        self.assertFalse(post_result["promotion_written"])
        self.assertIn(
            "production_release_promotion_journal_corrupt_or_not_sqlite",
            result["blockers"],
        )
        self.assertEqual(journal.read_bytes(), before)

    def test_same_second_events_still_require_latest_sequence_pointer(self) -> None:
        same_second = "2026-07-15T00:04:00Z"
        with patch.object(
            release_promotion_service,
            "_now_iso",
            return_value=same_second,
        ):
            first = release_promotion_service.promote_production_release(
                {"approved_by_user": True},
                evidence_root=self.evidence_root,
                expected_head_full=self.head,
            )
            self.assertTrue(first["release_promotion_current_head"])
            self._advance_remote_evidence()
            second = release_promotion_service.promote_production_release(
                {"approved_by_user": True},
                evidence_root=self.evidence_root,
                expected_head_full=self.head,
            )
        self.assertTrue(second["release_promotion_current_head"])
        self.assertNotEqual(first["event_id"], second["event_id"])
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        with sqlite3.connect(journal) as connection:
            events = connection.execute(
                "SELECT event_id, sequence_no, head_full, promoted_at_utc, event_mac "
                "FROM production_release_promotion_events ORDER BY sequence_no"
            ).fetchall()
            self.assertEqual([row[1] for row in events], [1, 2])
            self.assertEqual([row[3] for row in events], [same_second, same_second])
            connection.execute(
                "UPDATE production_release_promotion_current SET event_id = ?, "
                "sequence_no = ?, head_full = ?, promoted_at_utc = ?, event_mac = ?",
                events[0],
            )
        before = journal.read_bytes()

        read_result = release_promotion_service.validate_production_release_promotion(
            self.evidence_root,
            expected_head_full=self.head,
        )
        post_result = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(read_result["release_promotion_current_head"])
        self.assertFalse(post_result["promotion_written"])
        self.assertIn(
            "production_release_promotion_journal_corrupt_or_not_sqlite",
            read_result["blockers"],
        )
        self.assertEqual(journal.read_bytes(), before)

    def test_missing_insecure_or_corrupt_writer_key_fails_closed(self) -> None:
        cases = (
            (
                "missing",
                release_promotion_service._TRUST_KEY_MISSING_BLOCKER,
            ),
            (
                "file_permissions",
                release_promotion_service._TRUST_KEY_PERMISSIONS_BLOCKER,
            ),
            (
                "directory_permissions",
                release_promotion_service._TRUST_KEY_PERMISSIONS_BLOCKER,
            ),
            (
                "corrupt_length",
                release_promotion_service._TRUST_KEY_CORRUPT_BLOCKER,
            ),
            (
                "wrong_same_length_secret",
                release_promotion_service._TRUST_STATE_CORRUPT_BLOCKER,
            ),
        )
        for case, blocker in cases:
            with self.subTest(case=case):
                self._reset_promotion_storage()
                created = release_promotion_service.promote_production_release(
                    {"approved_by_user": True},
                    evidence_root=self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertTrue(created["release_promotion_current_head"])
                journal = self.release_root / release_promotion_service.JOURNAL_NAME
                trust_directory, key_path = release_promotion_service._trust_paths(
                    self.evidence_root
                )
                if case == "missing":
                    key_path.unlink()
                elif case == "file_permissions":
                    key_path.chmod(0o644)
                elif case == "directory_permissions":
                    trust_directory.chmod(0o755)
                elif case == "corrupt_length":
                    key_path.write_bytes(b"short-key-material")
                else:
                    original_key = key_path.read_bytes()
                    key_path.write_bytes(
                        bytes([original_key[0] ^ 0x01]) + original_key[1:]
                    )
                journal_before = journal.read_bytes()
                key_before = key_path.read_bytes() if key_path.is_file() else None
                key_mode_before = (
                    key_path.stat().st_mode & 0o777 if key_path.exists() else None
                )
                directory_mode_before = trust_directory.stat().st_mode & 0o777

                read_result = release_promotion_service.validate_production_release_promotion(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                post_result = release_promotion_service.promote_production_release(
                    {"approved_by_user": True},
                    evidence_root=self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertFalse(read_result["release_promotion_current_head"])
                self.assertFalse(post_result["promotion_written"])
                self.assertIn(blocker, read_result["blockers"])
                self.assertIn(blocker, post_result["blockers"])
                self.assertEqual(journal.read_bytes(), journal_before)
                self.assertEqual(
                    key_path.read_bytes() if key_path.is_file() else None,
                    key_before,
                )
                self.assertEqual(
                    key_path.stat().st_mode & 0o777 if key_path.exists() else None,
                    key_mode_before,
                )
                self.assertEqual(
                    trust_directory.stat().st_mode & 0o777,
                    directory_mode_before,
                )

    def test_missing_insecure_or_corrupt_trusted_terminal_state_fails_closed(self) -> None:
        cases = (
            (
                "missing",
                release_promotion_service._TRUST_STATE_MISSING_BLOCKER,
            ),
            (
                "permissions",
                release_promotion_service._TRUST_STATE_PERMISSIONS_BLOCKER,
            ),
            (
                "corrupt",
                release_promotion_service._TRUST_STATE_CORRUPT_BLOCKER,
            ),
        )
        for case, blocker in cases:
            with self.subTest(case=case):
                self._reset_promotion_storage()
                created = release_promotion_service.promote_production_release(
                    {"approved_by_user": True},
                    evidence_root=self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertTrue(created["release_promotion_current_head"])
                journal = self.release_root / release_promotion_service.JOURNAL_NAME
                state_path = release_promotion_service._trust_state_path(
                    self.evidence_root
                )
                if case == "missing":
                    state_path.unlink()
                elif case == "permissions":
                    state_path.chmod(0o644)
                else:
                    state_path.write_bytes(b"not-canonical-trusted-state")
                journal_before = journal.read_bytes()
                state_before = state_path.read_bytes() if state_path.is_file() else None
                state_mode_before = (
                    state_path.stat().st_mode & 0o777
                    if state_path.exists()
                    else None
                )

                read_result = release_promotion_service.validate_production_release_promotion(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                post_result = release_promotion_service.promote_production_release(
                    {"approved_by_user": True},
                    evidence_root=self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertFalse(read_result["release_promotion_current_head"])
                self.assertFalse(post_result["promotion_written"])
                self.assertIn(blocker, read_result["blockers"])
                self.assertIn(blocker, post_result["blockers"])
                self.assertEqual(journal.read_bytes(), journal_before)
                self.assertEqual(
                    state_path.read_bytes() if state_path.is_file() else None,
                    state_before,
                )
                self.assertEqual(
                    state_path.stat().st_mode & 0o777
                    if state_path.exists()
                    else None,
                    state_mode_before,
                )

    def test_trusted_terminal_state_detects_history_truncation(self) -> None:
        first = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(first["release_promotion_current_head"])
        self._advance_remote_evidence()
        second = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(second["release_promotion_current_head"])
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        with sqlite3.connect(journal) as connection:
            events = connection.execute(
                "SELECT event_id, sequence_no, head_full, promoted_at_utc, event_mac "
                "FROM production_release_promotion_events ORDER BY sequence_no"
            ).fetchall()
            connection.execute(
                f"DROP TRIGGER {release_promotion_service._EVENT_NO_DELETE_TRIGGER}"
            )
            connection.execute(
                "UPDATE production_release_promotion_current SET event_id = ?, "
                "sequence_no = ?, head_full = ?, promoted_at_utc = ?, event_mac = ?",
                events[0],
            )
            connection.execute(
                "DELETE FROM production_release_promotion_events WHERE sequence_no = 2"
            )
            connection.execute(release_promotion_service._EVENT_NO_DELETE_TRIGGER_DDL)
        before = journal.read_bytes()

        result = release_promotion_service.validate_production_release_promotion(
            self.evidence_root,
            expected_head_full=self.head,
        )
        post_result = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(result["release_promotion_current_head"])
        self.assertFalse(post_result["promotion_written"])
        self.assertIn(
            "production_release_promotion_journal_corrupt_or_not_sqlite",
            result["blockers"],
        )
        self.assertEqual(journal.read_bytes(), before)

    def test_remote_ci_requires_formal_recorder_and_consistent_green_attestations(self) -> None:
        path = self.release_root / "remote_ci_review_receipt.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        cases = (
            ("receipt_writer", "scripts/hand_written_receipt.py"),
            ("latest_remote_run_verified_green", False),
            ("remote_actions_status_known", False),
            ("remote_ci_job_page_green_observed", False),
            ("remote_ci_run_observed_for_current_head", False),
            ("artifact_digest_verified", False),
        )
        for field, value in cases:
            with self.subTest(field=field):
                tampered = dict(original)
                tampered[field] = value
                _write_json(path, tampered)
                result = release_promotion_service.validate_release_prerequisites(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertFalse(result["ready"])
                remote = next(
                    row for row in result["rows"] if row["evidence_key"] == "remote_ci"
                )
                self.assertFalse(remote["ready"])
        _write_json(path, original)

    def test_remote_ci_identity_uses_exact_structured_values(self) -> None:
        path = self.release_root / "remote_ci_review_receipt.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        cases = (
            (
                "run_url",
                f"https://github.com/lishark-of/stock-MING/actions/runs/1{self.run_id}",
            ),
            ("artifact_name", f"command-center-3-push-gate-evidence-{self.run_id}-extra"),
            ("run_id", f"{self.run_id}"),
            ("artifact_digest", self.artifact_digest + "0"),
        )
        for field, value in cases:
            with self.subTest(field=field):
                tampered = dict(original)
                tampered[field] = value
                _write_json(path, tampered)
                result = release_promotion_service.validate_release_prerequisites(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertFalse(result["ready"])
                self.assertIn("remote_ci_artifact_identity_invalid", result["blockers"])
        _write_json(path, original)

    def test_changed_valid_remote_identity_invalidates_old_event(self) -> None:
        promoted = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(promoted["release_promotion_current_head"])

        next_run_id = str(int(self.run_id) + 1)
        remote_path = self.release_root / "remote_ci_review_receipt.json"
        remote = json.loads(remote_path.read_text(encoding="utf-8"))
        remote.update(
            {
                "run_id": int(next_run_id),
                "run_url": f"https://github.com/lishark-of/stock-MING/actions/runs/{next_run_id}",
                "safe_failure_log_excerpt_or_green_run_url": (
                    f"https://github.com/lishark-of/stock-MING/actions/runs/{next_run_id}"
                ),
                "artifact_name": f"command-center-3-push-gate-evidence-{next_run_id}",
            }
        )
        _write_json(remote_path, remote)
        review_path = self.release_root / "release_gate_review_receipt.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["remote_run_id"] = next_run_id
        _write_json(review_path, review)

        stale = release_promotion_service.validate_production_release_promotion(
            self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(stale["release_promotion_current_head"])
        self.assertIn("production_release_event_evidence_binding_mismatch", stale["blockers"])

    def test_head_change_invalidates_pointer(self) -> None:
        release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        result = release_promotion_service.validate_production_release_promotion(
            self.evidence_root,
            expected_head_full="f" * 40,
        )
        self.assertFalse(result["release_promotion_current_head"])
        self.assertIn("production_release_pointer_head_mismatch", result["blockers"])

    def test_invalid_expected_head_never_falls_back_to_git(self) -> None:
        invalid_heads = ("a" * 39, "a" * 41, "a" * 63, "a" * 65, "g" * 40)
        for invalid_head in invalid_heads:
            with self.subTest(length=len(invalid_head)):
                with patch.object(
                    release_promotion_service,
                    "_current_head",
                    return_value=self.head,
                ):
                    result = release_promotion_service.validate_release_prerequisites(
                        self.evidence_root,
                        expected_head_full=invalid_head,
                    )
                self.assertFalse(result["ready"])
                self.assertEqual(result["head_full"], "")
                self.assertIn("release_promotion_expected_head_invalid", result["blockers"])
        self.assertEqual(release_promotion_service._normalize_head("a" * 64), "a" * 64)

    def test_unavailable_git_head_and_empty_receipt_head_fail_closed(self) -> None:
        with patch.object(release_promotion_service, "_current_head", return_value=""):
            result = release_promotion_service.validate_release_prerequisites(
                self.evidence_root,
            )
        self.assertFalse(result["ready"])
        self.assertIn("release_promotion_current_git_head_unavailable", result["blockers"])

        remote_path = self.release_root / "remote_ci_review_receipt.json"
        remote = json.loads(remote_path.read_text(encoding="utf-8"))
        remote["head"] = ""
        remote["head_full"] = ""
        _write_json(remote_path, remote)
        receipt_result = release_promotion_service.validate_release_prerequisites(
            self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(receipt_result["ready"])
        self.assertIn("remote_ci_head_mismatch", receipt_result["blockers"])

    def test_corrupt_or_non_journal_sqlite_blocks_get_and_post_without_rewrite(self) -> None:
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        journal.parent.mkdir(parents=True, exist_ok=True)
        cases = (b"not a sqlite journal", None)
        for payload in cases:
            with self.subTest(kind="bytes" if payload else "wrong_schema"):
                journal.unlink(missing_ok=True)
                if payload is not None:
                    journal.write_bytes(payload)
                else:
                    with sqlite3.connect(journal) as connection:
                        connection.execute("CREATE TABLE unrelated(value TEXT)")
                before = journal.read_bytes()
                read_result = release_promotion_service.validate_production_release_promotion(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                write_result = release_promotion_service.promote_production_release(
                    {"approved_by_user": True},
                    evidence_root=self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertFalse(read_result["release_promotion_current_head"])
                self.assertFalse(write_result["release_promotion_current_head"])
                self.assertFalse(write_result["promotion_written"])
                self.assertIn(
                    "production_release_promotion_journal_corrupt_or_not_sqlite",
                    read_result["blockers"],
                )
                self.assertIn(
                    "production_release_promotion_journal_corrupt_or_not_sqlite",
                    write_result["blockers"],
                )
                self.assertEqual(journal.read_bytes(), before)

    def test_exact_columns_with_wrong_constraints_are_never_rebuilt_or_appended(self) -> None:
        journal = self.release_root / release_promotion_service.JOURNAL_NAME
        cases = {
            "missing_primary_keys": (
                release_promotion_service._EVENT_TABLE_DDL.replace(
                    "event_id TEXT PRIMARY KEY", "event_id TEXT"
                ),
                release_promotion_service._CURRENT_TABLE_DDL.replace(
                    "scope TEXT PRIMARY KEY", "scope TEXT"
                ),
            ),
            "wrong_not_null": (
                release_promotion_service._EVENT_TABLE_DDL.replace(
                    "schema_version TEXT NOT NULL", "schema_version TEXT"
                ),
                release_promotion_service._CURRENT_TABLE_DDL,
            ),
            "wrong_type": (
                release_promotion_service._EVENT_TABLE_DDL.replace(
                    "approved_by_user INTEGER", "approved_by_user TEXT"
                ),
                release_promotion_service._CURRENT_TABLE_DDL,
            ),
            "missing_approval_check": (
                release_promotion_service._EVENT_TABLE_DDL.replace(
                    " CHECK (approved_by_user = 1)", ""
                ),
                release_promotion_service._CURRENT_TABLE_DDL,
            ),
            "missing_foreign_key": (
                release_promotion_service._EVENT_TABLE_DDL,
                release_promotion_service._CURRENT_TABLE_DDL.replace(
                    ", FOREIGN KEY(event_id) REFERENCES "
                    "production_release_promotion_events(event_id)",
                    "",
                ),
            ),
        }
        for name, (event_ddl, current_ddl) in cases.items():
            with self.subTest(name=name):
                journal.unlink(missing_ok=True)
                with sqlite3.connect(journal) as connection:
                    connection.execute(event_ddl)
                    connection.execute(current_ddl)
                    event_values = (
                        "duplicate-event",
                        1,
                        "0" * 64,
                        release_promotion_service.EVENT_SCHEMA_VERSION,
                        release_promotion_service.PROMOTION_SCOPE,
                        self.head,
                        "a" * 64,
                        "b" * 64,
                        "c" * 64,
                        "d" * 64,
                        self.run_id,
                        self.artifact_digest,
                        1,
                        "2026-07-15T00:00:00Z",
                        "",
                        "e" * 64,
                    )
                    connection.execute(
                        "INSERT INTO production_release_promotion_events VALUES "
                        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        event_values,
                    )
                    if name == "missing_primary_keys":
                        connection.execute(
                            "INSERT INTO production_release_promotion_events VALUES "
                            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            event_values,
                        )
                    count_before = connection.execute(
                        "SELECT COUNT(*) FROM production_release_promotion_events"
                    ).fetchone()[0]
                bytes_before = journal.read_bytes()

                read_result = release_promotion_service.validate_production_release_promotion(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                write_result = release_promotion_service.promote_production_release(
                    {"approved_by_user": True},
                    evidence_root=self.evidence_root,
                    expected_head_full=self.head,
                )

                self.assertIn(
                    "production_release_promotion_journal_corrupt_or_not_sqlite",
                    read_result["blockers"],
                )
                self.assertIn(
                    "production_release_promotion_journal_corrupt_or_not_sqlite",
                    write_result["blockers"],
                )
                self.assertFalse(write_result["promotion_written"])
                self.assertEqual(journal.read_bytes(), bytes_before)
                with sqlite3.connect(journal) as connection:
                    count_after = connection.execute(
                        "SELECT COUNT(*) FROM production_release_promotion_events"
                    ).fetchone()[0]
                self.assertEqual(count_after, count_before)

    def test_allowlist_pending_or_incomplete_review_never_becomes_ready(self) -> None:
        path = self.release_root / "secret_artifact_allowlist_review_receipt.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        cases = (
            ("secret_keyword_review_status", "secret_keyword_review_contract_ready_manual_review_pending"),
            ("periodic_allowlist_review_ready", False),
            ("false_positive_allowlist_review_ready", False),
        )
        for field, value in cases:
            with self.subTest(field=field):
                receipt = dict(original)
                receipt[field] = value
                _write_json(path, receipt)
                result = release_promotion_service.validate_release_prerequisites(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                allowlist = next(
                    row for row in result["rows"] if row["evidence_key"] == "allowlist"
                )
                self.assertFalse(result["ready"])
                self.assertFalse(allowlist["ready"])
        _write_json(path, original)

    def test_receipt_type_corruption_is_total_fail_closed_without_exception(self) -> None:
        cases = (
            ("local_push_gate_run_receipt.json", "checks", None, "local_push_gate"),
            ("local_push_gate_run_receipt.json", "status", [], "local_push_gate"),
            ("remote_ci_review_receipt.json", "status", [], "remote_ci"),
            ("remote_ci_review_receipt.json", "run_url", {}, "remote_ci"),
            (
                "secret_artifact_allowlist_review_receipt.json",
                "status",
                [],
                "allowlist",
            ),
            ("release_gate_review_receipt.json", "status", [], "release_review"),
        )
        for filename, field, value, evidence_key in cases:
            with self.subTest(filename=filename, field=field):
                self._seed_formal_evidence()
                path = self.release_root / filename
                receipt = json.loads(path.read_text(encoding="utf-8"))
                receipt[field] = value
                _write_json(path, receipt)
                result = release_promotion_service.validate_release_prerequisites(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                post_result = release_promotion_service.promote_production_release(
                    {"approved_by_user": True},
                    evidence_root=self.evidence_root,
                    expected_head_full=self.head,
                )
                row = next(
                    item for item in result["rows"] if item["evidence_key"] == evidence_key
                )
                self.assertFalse(result["ready"])
                self.assertFalse(post_result["promotion_written"])
                self.assertFalse(row["ready"])
                self.assertIn(
                    f"{evidence_key}_receipt_field_types_invalid",
                    row["blockers"],
                )

        remote_path = self.release_root / "remote_ci_review_receipt.json"
        remote_path.write_bytes(b"\xff\xfeinvalid-json")
        unreadable = release_promotion_service.validate_release_prerequisites(
            self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(unreadable["ready"])
        remote = next(
            row for row in unreadable["rows"] if row["evidence_key"] == "remote_ci"
        )
        self.assertFalse(remote["ready"])
        unreadable_post = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertFalse(unreadable_post["promotion_written"])

    def test_every_formal_receipt_field_rejects_object_type(self) -> None:
        receipts = (
            ("local_push_gate_run_receipt.json", "local_push_gate"),
            ("remote_ci_review_receipt.json", "remote_ci"),
            ("secret_artifact_allowlist_review_receipt.json", "allowlist"),
            ("release_gate_review_receipt.json", "release_review"),
        )
        for filename, evidence_key in receipts:
            path = self.release_root / filename
            original = json.loads(path.read_text(encoding="utf-8"))
            for field in original:
                with self.subTest(filename=filename, field=field):
                    tampered = dict(original)
                    tampered[field] = {"unexpected": "object"}
                    _write_json(path, tampered)
                    result = release_promotion_service.validate_release_prerequisites(
                        self.evidence_root,
                        expected_head_full=self.head,
                    )
                    row = next(
                        item
                        for item in result["rows"]
                        if item["evidence_key"] == evidence_key
                    )
                    self.assertFalse(row["ready"])
                    self.assertIn(
                        f"{evidence_key}_receipt_field_types_invalid",
                        row["blockers"],
                    )
            _write_json(path, original)

    def test_unknown_or_missing_receipt_fields_fail_exact_schema_closed(self) -> None:
        receipts = (
            ("local_push_gate_run_receipt.json", "local_push_gate"),
            ("remote_ci_review_receipt.json", "remote_ci"),
            ("secret_artifact_allowlist_review_receipt.json", "allowlist"),
            ("release_gate_review_receipt.json", "release_review"),
        )
        for filename, evidence_key in receipts:
            path = self.release_root / filename
            original = json.loads(path.read_text(encoding="utf-8"))
            cases = []
            with_array = dict(original)
            with_array["unexpected_array"] = ["not", "formal"]
            cases.append(with_array)
            with_object = dict(original)
            with_object["unexpected_object"] = {"not": "formal"}
            cases.append(with_object)
            missing = dict(original)
            missing.pop(next(iter(original)))
            cases.append(missing)
            for index, tampered in enumerate(cases):
                with self.subTest(filename=filename, case=index):
                    _write_json(path, tampered)
                    result = release_promotion_service.validate_release_prerequisites(
                        self.evidence_root,
                        expected_head_full=self.head,
                    )
                    row = next(
                        item
                        for item in result["rows"]
                        if item["evidence_key"] == evidence_key
                    )
                    self.assertFalse(row["ready"])
                    self.assertIn(
                        f"{evidence_key}_receipt_fields_not_exact_formal_schema",
                        row["blockers"],
                    )
            _write_json(path, original)
        self.assertFalse(
            (self.release_root / release_promotion_service.JOURNAL_NAME).exists()
        )

    def test_formal_identity_timestamp_and_completion_values_fail_closed(self) -> None:
        cases = (
            (
                "local_push_gate_run_receipt.json",
                "generated_at_utc",
                "2026-07-15T00:00:00+00:00",
                "local_push_gate",
                "local_gate_formal_recorder_identity_invalid",
            ),
            (
                "local_push_gate_run_receipt.json",
                "remote_ci_status_note",
                "remote CI green",
                "local_push_gate",
                "local_gate_push_boundary_invalid",
            ),
            (
                "remote_ci_review_receipt.json",
                "remote_ci_lookup_source",
                "manual_lookup",
                "remote_ci",
                "remote_ci_attestation_status_inconsistent",
            ),
            (
                "remote_ci_review_receipt.json",
                "reviewed_at_utc",
                "not-a-time",
                "remote_ci",
                "remote_ci_formal_recorder_identity_invalid",
            ),
            (
                "secret_artifact_allowlist_review_receipt.json",
                "receipt_writer",
                "scripts/hand_written.py",
                "allowlist",
                "allowlist_formal_recorder_identity_invalid",
            ),
            (
                "secret_artifact_allowlist_review_receipt.json",
                "production_release_complete",
                True,
                "allowlist",
                "allowlist_completed_review_attestations_missing",
            ),
            (
                "release_gate_review_receipt.json",
                "branch",
                "feature",
                "release_review",
                "release_review_formal_recorder_identity_invalid",
            ),
            (
                "release_gate_review_receipt.json",
                "strict_closeout_ready",
                True,
                "release_review",
                "release_review_not_complete",
            ),
        )
        for filename, field, value, evidence_key, blocker in cases:
            with self.subTest(filename=filename, field=field):
                self._seed_formal_evidence()
                path = self.release_root / filename
                receipt = json.loads(path.read_text(encoding="utf-8"))
                receipt[field] = value
                _write_json(path, receipt)
                result = release_promotion_service.validate_release_prerequisites(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                row = next(
                    item for item in result["rows"] if item["evidence_key"] == evidence_key
                )
                self.assertFalse(row["ready"])
                self.assertIn(blocker, row["blockers"])

    def test_local_ahead_count_rejects_unicode_digits(self) -> None:
        path = self.release_root / "local_push_gate_run_receipt.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for value in ("１２", "١٢", "²"):
            with self.subTest(value=value):
                receipt = dict(original)
                receipt["origin_ahead_count"] = value
                _write_json(path, receipt)
                result = release_promotion_service.validate_release_prerequisites(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                local_gate = next(
                    row
                    for row in result["rows"]
                    if row["evidence_key"] == "local_push_gate"
                )
                self.assertFalse(local_gate["ready"])
                self.assertIn(
                    "local_gate_formal_recorder_identity_invalid",
                    local_gate["blockers"],
                )
        _write_json(path, original)

    def test_timestamp_and_safe_metadata_changes_invalidate_old_event(self) -> None:
        promoted = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(promoted["release_promotion_current_head"])
        cases = (
            (
                "local_push_gate_run_receipt.json",
                "generated_at_utc",
                "2026-07-16T00:00:00Z",
            ),
            (
                "remote_ci_review_receipt.json",
                "reviewed_at_utc",
                "2026-07-16T00:01:00Z",
            ),
            (
                "secret_artifact_allowlist_review_receipt.json",
                "manual_review_note_safe",
                "reviewed again",
            ),
            (
                "release_gate_review_receipt.json",
                "reviewer",
                "second-local-reviewer",
            ),
        )
        for filename, field, value in cases:
            path = self.release_root / filename
            original = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(filename=filename, field=field):
                changed = dict(original)
                changed[field] = value
                _write_json(path, changed)
                stale = release_promotion_service.validate_production_release_promotion(
                    self.evidence_root,
                    expected_head_full=self.head,
                )
                self.assertFalse(stale["release_promotion_current_head"])
                self.assertIn(
                    "production_release_event_evidence_binding_mismatch",
                    stale["blockers"],
                )
            _write_json(path, original)

    def test_every_same_type_formal_field_change_invalidates_old_event(self) -> None:
        promoted = release_promotion_service.promote_production_release(
            {"approved_by_user": True},
            evidence_root=self.evidence_root,
            expected_head_full=self.head,
        )
        self.assertTrue(promoted["release_promotion_current_head"])
        filenames = (
            "local_push_gate_run_receipt.json",
            "remote_ci_review_receipt.json",
            "secret_artifact_allowlist_review_receipt.json",
            "release_gate_review_receipt.json",
        )
        for filename in filenames:
            path = self.release_root / filename
            original = json.loads(path.read_text(encoding="utf-8"))
            for field, value in original.items():
                with self.subTest(filename=filename, field=field):
                    changed = dict(original)
                    if type(value) is bool:
                        changed[field] = not value
                    elif type(value) is int:
                        changed[field] = value + 1
                    elif isinstance(value, str):
                        changed[field] = value + "-changed"
                    elif isinstance(value, list):
                        changed[field] = [*value, "unexpected_formal_field_value"]
                    else:
                        self.fail(f"unhandled formal receipt type for {filename}:{field}")
                    _write_json(path, changed)
                    stale = release_promotion_service.validate_production_release_promotion(
                        self.evidence_root,
                        expected_head_full=self.head,
                    )
                    self.assertFalse(stale["release_promotion_current_head"])
                _write_json(path, original)

    def test_apple_distribution_blocks_ltg09_but_not_ltg11(self) -> None:
        version_rows = [
            {"version": f"v0.{index}", "local_direct_evidence_ready": True}
            for index in range(1, 8)
        ]
        facts = {
            "remote_ci_current_head": True,
            "release_promotion_current_head": True,
            "desktop_production_package": True,
            "developer_signing_notarization": False,
            "qmt_research_isolation": True,
        }
        rows = {row["id"]: row for row in v1_closeout_service._build_ltg_rows(version_rows, facts)}
        self.assertTrue(rows["LTG-11"]["production_complete"])
        self.assertFalse(rows["LTG-09"]["production_complete"])
        self.assertEqual(rows["LTG-09"]["missing_production_evidence"], ["developer_signing_notarization"])


if __name__ == "__main__":
    unittest.main()
