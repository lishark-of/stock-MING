from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from server.services import production_evidence_journal as journal
from server.services import storage_service, worker_service
from storage.sqlite_meta import SQLiteMetaStore


class ProductionEvidenceJournalTests(unittest.TestCase):
    def _paths(self, root: Path) -> dict[str, Path]:
        trust = root / "trust"
        return {
            "TRUST_ROOT": trust,
            "KEY_PATH": trust / "journal.key",
            "JOURNAL_PATH": trust / "journal.jsonl",
            "STATE_PATH": trust / "state.json",
            "LOCK_PATH": trust / "journal.lock",
        }

    def _patch_paths(self, root: Path):
        values = self._paths(root)
        return patch.multiple(journal, **values)

    def test_hmac_journal_consumes_nonce_once_and_fails_closed_on_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self._patch_paths(Path(directory)):
            head = journal.current_head_full()
            scope_hash = "1" * 64
            payload_digest = "2" * 64
            nonce = "worker-request-nonce-0123456789-ABCDEFG"
            recorded = journal.record_event(
                event_type="worker_runtime_execution_request",
                expected_head_full=head,
                authorization_nonce=nonce,
                subject="task-1",
                scope_hash=scope_hash,
                payload_digest=payload_digest,
            )
            self.assertTrue(recorded["ready"])
            self.assertFalse(recorded["production_trusted"])
            self.assertNotIn(nonce, journal.JOURNAL_PATH.read_text(encoding="utf-8"))
            replay = journal.record_event(
                event_type="worker_runtime_execution",
                expected_head_full=head,
                authorization_nonce=nonce,
                subject="task-2",
                scope_hash=scope_hash,
                payload_digest=payload_digest,
            )
            self.assertEqual(replay["status"], "production_evidence_nonce_already_consumed")
            events = [json.loads(line) for line in journal.JOURNAL_PATH.read_text(encoding="utf-8").splitlines()]
            events[0]["head_full"] = "0" * 40
            journal.JOURNAL_PATH.write_text(json.dumps(events[0]) + "\n", encoding="utf-8")
            self.assertFalse(journal.validate_journal()["ready"])

    def test_snapshot_rollback_nonce_replay_remains_local_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self._patch_paths(Path(directory)):
            head = journal.current_head_full()
            first = journal.record_event(
                event_type="worker_runtime_execution_request",
                expected_head_full=head,
                authorization_nonce="rollback-first-nonce-0123456789-ABCDEFG",
                subject="request-1",
                scope_hash="1" * 64,
                payload_digest="2" * 64,
            )
            self.assertTrue(first["local_integrity_ready"])
            snapshot = {
                path: path.read_bytes()
                for path in (journal.KEY_PATH, journal.JOURNAL_PATH, journal.STATE_PATH)
            }
            replay_nonce = "rollback-replay-nonce-0123456789-ABCDEFG"
            second = journal.record_event(
                event_type="worker_runtime_execution",
                expected_head_full=head,
                authorization_nonce=replay_nonce,
                subject="execution-1",
                scope_hash="3" * 64,
                payload_digest="4" * 64,
            )
            self.assertTrue(second["local_integrity_ready"])
            for path, payload in snapshot.items():
                path.write_bytes(payload)
            replay_after_rollback = journal.record_event(
                event_type="worker_runtime_execution",
                expected_head_full=head,
                authorization_nonce=replay_nonce,
                subject="execution-1",
                scope_hash="3" * 64,
                payload_digest="4" * 64,
            )
            self.assertTrue(replay_after_rollback["local_integrity_ready"])
            self.assertFalse(replay_after_rollback["production_trusted"])
            self.assertFalse(journal.validate_journal()["snapshot_rollback_resistant"])

    def test_state_anchor_write_failure_returns_precise_fail_closed_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self._patch_paths(Path(directory)):
            original_atomic_write = journal._atomic_write

            def fail_state_anchor(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
                if path == journal.STATE_PATH:
                    raise OSError("injected state anchor failure")
                original_atomic_write(path, payload, mode=mode)

            with patch.object(journal, "_atomic_write", side_effect=fail_state_anchor):
                result = journal.record_event(
                    event_type="worker_runtime_execution_request",
                    expected_head_full=journal.current_head_full(),
                    authorization_nonce="state-anchor-failure-0123456789-ABCDEFG",
                    subject="request-state-failure",
                    scope_hash="1" * 64,
                    payload_digest="2" * 64,
                )

            self.assertFalse(result["ready"])
            self.assertFalse(result["local_integrity_ready"])
            self.assertFalse(result["production_trusted"])
            self.assertEqual(
                result["status"],
                "production_evidence_state_write_failed_journal_fail_closed",
            )
            self.assertTrue(result["journal_append_succeeded"])
            self.assertFalse(result["state_anchor_write_succeeded"])
            self.assertTrue(result["trusted_recovery_required"])
            self.assertTrue(journal.JOURNAL_PATH.exists())
            self.assertFalse(journal.STATE_PATH.exists())
            self.assertFalse(journal.validate_journal()["ready"])


class StorageTtlProductionEvidenceTests(unittest.TestCase):
    def _patch_paths(self, root: Path):
        trust = root / "trust"
        return patch.multiple(
            journal,
            TRUST_ROOT=trust,
            KEY_PATH=trust / "journal.key",
            JOURNAL_PATH=trust / "journal.jsonl",
            STATE_PATH=trust / "state.json",
            LOCK_PATH=trust / "journal.lock",
        )

    def _row(self, dataset: str, head: str, index: int) -> dict:
        row = {
            "dataset": dataset,
            "resolution": "fresh_no_refresh_required",
            "refresh_task_id": f"ttl-task-{index}",
            "refresh_scope_hash": f"{index + 1:064x}",
            "artifact_sha256": f"{index + 101:064x}",
            "before_ttl_state": "fresh",
            "after_ttl_state": "fresh",
            "refresh_executed": False,
            "provider_call_count": 0,
            "fetched_at": "2026-07-18T00:00:00+00:00",
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }
        material = storage_service._storage_cache_ttl_resolution_material(row, head)
        row["payload_digest"] = storage_service._json_sha256(material)
        event = journal.record_event(
            event_type="storage_ttl_dataset_resolution",
            expected_head_full=head,
            authorization_nonce=f"storage-ttl-{dataset}-0123456789-ABCDEFG",
            subject=dataset,
            scope_hash=row["refresh_scope_hash"],
            payload_digest=row["payload_digest"],
        )
        self.assertTrue(event["ready"])
        row["journal_event_id"] = event["event_id"]
        return row

    def test_ttl_requires_every_canonical_dataset_on_current_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self._patch_paths(Path(directory)):
            db_path = Path(directory) / "meta.sqlite"
            head = journal.current_head_full()
            rows = [self._row(dataset, head, index) for index, dataset in enumerate(storage_service.CANONICAL_PARQUET_DATASETS)]
            SQLiteMetaStore(db_path).write_packet(
                storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY,
                {
                    "schema_version": storage_service.CACHE_TTL_REFRESH_EVIDENCE_SCHEMA_VERSION,
                    "head_full": head,
                    "rows": rows,
                },
            )
            with patch.object(storage_service, "SQLITE_META_PATH", db_path):
                journal_before = journal.JOURNAL_PATH.read_bytes()
                state_before = journal.STATE_PATH.read_bytes()
                ready = storage_service.storage_cache_ttl_refresh_evidence()
                self.assertTrue(ready["local_ttl_resolution_evidence_ready"])
                self.assertFalse(ready["production_ttl_evidence_ready"])
                self.assertFalse(ready["production_trust_boundary_satisfied"])
                self.assertEqual(ready["verified_dataset_count"], len(storage_service.CANONICAL_PARQUET_DATASETS))
                self.assertEqual(ready["refresh_executed_count"], 0)
                blocker_audit = storage_service.storage_production_blocker_audit()
                ttl_row = next(
                    row
                    for row in blocker_audit["rows"]
                    if row["criterion"] == "cache_ttl_refresh_pipeline_executed"
                )
                self.assertFalse(ttl_row["passed"])
                self.assertTrue(ttl_row["production_blocker"])
                self.assertIn("production_trust=false", ttl_row["current_status"])
                self.assertEqual(journal.JOURNAL_PATH.read_bytes(), journal_before)
                self.assertEqual(journal.STATE_PATH.read_bytes(), state_before)
                packet = SQLiteMetaStore(db_path).read_packet(storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY)
                packet["rows"] = packet["rows"][:-1]
                SQLiteMetaStore(db_path).write_packet(storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY, packet)
                blocked = storage_service.storage_cache_ttl_refresh_evidence()
                self.assertFalse(blocked["production_ttl_evidence_ready"])
                self.assertEqual(blocked["verified_dataset_count"], len(storage_service.CANONICAL_PARQUET_DATASETS) - 1)

    def test_caller_mapping_cannot_self_seal_storage_production(self) -> None:
        crafted = {
            "status": "foundation_ready",
            "schema_migration_dataset_count": 1,
            "physical_schema_validation_done_count": 1,
            "schema_migration_executed_count": 1,
            "physical_dataset_version_validated_count": 1,
            "dataset_version_migration_executed_count": 1,
            "dataset_version_manifest_present_count": 1,
            "dataset_version_manifest_evidence_validated": True,
            "dataset_version_manifest_evidence_validated_count": 1,
            "partition_migration_executed_count": 1,
            "compaction_executed_count": 1,
            "cache_ttl_resolution_verified_count": 1,
            "cache_ttl_refresh_per_dataset_evidence": {
                "production_ttl_evidence_ready": True,
                "unresolved_datasets": [],
            },
            "duckdb_query_service_status": "service_ready",
            "artifact_hygiene_policy": "path_only_manual_cleanup_no_delete_on_get",
            "artifact_cleanup_review_status": "manual_review_ready_no_candidates",
            "artifact_cleanup_manual_review_required": True,
            "artifact_cleanup_delete_executed_count": 0,
            "artifact_cleanup_delete_command_generated": False,
            "external_calls_triggered": False,
            "schema_validation_dry_run_writes_parquet": False,
            "compaction_dry_run_writes_parquet": False,
            "cache_ttl_dry_run_writes_parquet": False,
        }
        authoritative_local = {
            "status": "foundation_ready",
            "schema_migration_dataset_count": len(storage_service.CANONICAL_PARQUET_DATASETS),
            "duckdb_query_service_status": "service_ready",
            "artifact_hygiene_policy": "path_only_manual_cleanup_no_delete_on_get",
            "artifact_cleanup_review_status": "manual_review_ready_no_candidates",
            "artifact_cleanup_manual_review_required": True,
            "artifact_cleanup_delete_executed_count": 0,
            "artifact_cleanup_delete_command_generated": False,
            "external_calls_triggered": False,
            "schema_validation_dry_run_writes_parquet": False,
            "compaction_dry_run_writes_parquet": False,
            "cache_ttl_dry_run_writes_parquet": False,
        }
        with patch.object(
            storage_service,
            "storage_production_readiness",
            return_value=authoritative_local,
        ):
            result = storage_service.storage_production_blocker_audit(crafted)

        self.assertTrue(result["caller_supplied_readiness_rejected"])
        self.assertEqual(result["dataset_count"], len(storage_service.CANONICAL_PARQUET_DATASETS))
        self.assertEqual(result["status"], "storage_production_blocked")
        self.assertFalse(result["production_storage_complete"])
        self.assertIn("trusted_external_storage_production_validator_missing", result["blockers"])
        validation = result["authoritative_production_fact_validation"]
        self.assertFalse(validation["ready"])
        self.assertFalse(validation["trusted_external_production_validator_ready"])


class WorkerProductionGovernanceTests(unittest.TestCase):
    def test_execution_request_requires_exact_head_nonce_and_verified_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trust = Path(directory) / "trust"
            with patch.multiple(
                journal,
                TRUST_ROOT=trust,
                KEY_PATH=trust / "journal.key",
                JOURNAL_PATH=trust / "journal.jsonl",
                STATE_PATH=trust / "state.json",
                LOCK_PATH=trust / "journal.lock",
            ):
                head = journal.current_head_full()
                task_id = "request-task"
                plan_scope = "1" * 64
                runtime_scope = "2" * 64
                event_scope = worker_service._json_sha256(
                    {
                        "head_full": head,
                        "evidence_plan_scope_hash": plan_scope,
                        "runtime_qa_scope_hash": runtime_scope,
                    }
                )
                material = worker_service._worker_trusted_event_material(
                    event_type="worker_runtime_execution_request",
                    head_full=head,
                    task_id=task_id,
                    evidence_plan_scope_hash=plan_scope,
                    runtime_qa_scope_hash=runtime_scope,
                )
                payload_digest = worker_service._json_sha256(material)
                nonce = "worker-request-exact-head-0123456789-ABCDE"
                event = journal.record_event(
                    event_type="worker_runtime_execution_request",
                    expected_head_full=head,
                    authorization_nonce=nonce,
                    subject=task_id,
                    scope_hash=event_scope,
                    payload_digest=payload_digest,
                )
                receipt = worker_service._worker_runtime_qa_execution_request_receipt(
                    production_evidence_plan={
                        "evidence_plan_ready": True,
                        "scope_ticket_sha256": plan_scope,
                        "status": "ready",
                    },
                    runtime_qa_execution_recipe={
                        "local_recipe_ready": True,
                        "runtime_qa_scope_hash": runtime_scope,
                        "status": "ready",
                    },
                    explicit_request=True,
                    task_id=task_id,
                    payload_safe={
                        "operator_approved": True,
                        "evidence_plan_scope_hash": plan_scope,
                        "runtime_qa_scope_hash": runtime_scope,
                        "expected_head_full": head,
                        "authorization_nonce_digest": journal.authorization_nonce_digest(nonce),
                        "trusted_event_id": event["event_id"],
                        "trusted_event_subject": task_id,
                        "trusted_event_scope_hash": event_scope,
                        "trusted_event_payload_digest": payload_digest,
                    },
                )
                self.assertTrue(receipt["local_integrity_execution_request_ready"])
                self.assertFalse(receipt["trusted_production_execution_request_ready"])
                self.assertFalse(receipt["production_trust_boundary_satisfied"])
                self.assertTrue(receipt["expected_head_matches_current"])
                self.assertTrue(receipt["local_integrity_event_verified"])
                self.assertFalse(receipt["trusted_event_verified"])

    def test_local_execution_request_does_not_equal_trusted_production_request(self) -> None:
        plan = {"evidence_plan_ready": True, "scope_ticket_sha256": "1" * 64, "status": "ready"}
        recipe = {"local_recipe_ready": True, "runtime_qa_scope_hash": "2" * 64, "status": "ready"}
        receipt = worker_service._worker_runtime_qa_execution_request_receipt(
            production_evidence_plan=plan,
            runtime_qa_execution_recipe=recipe,
            explicit_request=True,
            task_id="request-task",
            payload_safe={
                "operator_approved": True,
                "evidence_plan_scope_hash": "1" * 64,
                "runtime_qa_scope_hash": "2" * 64,
            },
        )
        self.assertTrue(receipt["local_execution_request_ready"])
        self.assertFalse(receipt["trusted_production_execution_request_ready"])
        self.assertFalse(receipt["authorization_nonce_raw_persisted"])

    def test_promotion_requires_literal_user_approval_not_broad_operator_flag(self) -> None:
        receipt = worker_service._worker_production_promotion_review_receipt(
            runtime_durable_evidence_recipe={"local_recipe_ready": True, "missing_durable_evidence": []},
            runtime_qa_execution={
                "schema_version": worker_service.RUNTIME_QA_EXECUTION_SCHEMA_VERSION,
                "local_runtime_qa_execution_done": True,
                "local_fallback_round_trip_verified": True,
                "production_worker_complete": False,
                "external_calls_triggered": False,
            },
            payload_safe={"operator_approved": True},
            task_id="review-task",
            reviewed_at="2026-07-18T00:00:00+00:00",
        )
        self.assertFalse(receipt["approved_by_user"])
        self.assertTrue(receipt["local_promotion_review_ready"])
        self.assertFalse(receipt["trusted_production_promotion_review_ready"])

    def test_self_signed_runtime_claim_cannot_promote_worker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trust = Path(directory) / "trust"
            with patch.multiple(
                journal,
                TRUST_ROOT=trust,
                KEY_PATH=trust / "journal.key",
                JOURNAL_PATH=trust / "journal.jsonl",
                STATE_PATH=trust / "state.json",
                LOCK_PATH=trust / "journal.lock",
            ):
                head = journal.current_head_full()
                task_id = "self-sealed-runtime"
                event = journal.record_event(
                    event_type="worker_runtime_execution",
                    expected_head_full=head,
                    authorization_nonce="self-sealed-runtime-0123456789-ABCDEFG",
                    subject=task_id,
                    scope_hash="5" * 64,
                    payload_digest="6" * 64,
                )
                receipt = worker_service._worker_production_promotion_review_receipt(
                    runtime_durable_evidence_recipe={
                        "local_recipe_ready": True,
                        "missing_durable_evidence": [],
                        "status": "local_recipe_ready",
                    },
                    runtime_qa_execution={
                        "schema_version": worker_service.RUNTIME_QA_EXECUTION_SCHEMA_VERSION,
                        "local_runtime_qa_execution_done": True,
                        "local_fallback_round_trip_verified": True,
                        "production_worker_complete": False,
                        "external_calls_triggered": False,
                        "head_full": head,
                        "trusted_event_id": event["event_id"],
                        "trusted_event_subject": task_id,
                        "trusted_event_scope_hash": "5" * 64,
                        "trusted_event_payload_digest": "6" * 64,
                        "worker_started": True,
                        "celery_worker_started": True,
                        "redis_pinged": True,
                        "task_dispatched": True,
                    },
                    payload_safe={
                        "operator_approved": True,
                        "approved_by_user": True,
                        "expected_head_full": head,
                    },
                    task_id="promotion-review",
                    reviewed_at="2026-07-18T00:00:00+00:00",
                )
                self.assertTrue(receipt["local_runtime_execution_claim_integrity_verified"])
                self.assertFalse(receipt["trusted_runtime_execution_verified"])
                self.assertFalse(receipt["trusted_production_promotion_review_ready"])
                self.assertFalse(receipt["production_worker_complete"])


if __name__ == "__main__":
    unittest.main()
