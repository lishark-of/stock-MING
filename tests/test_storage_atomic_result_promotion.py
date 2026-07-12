import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from server.services import migration_status_service, storage_service, task_service
from storage import duckdb_store, parquet_store
from storage.sqlite_meta import SQLiteMetaStore


class StorageAtomicResultPromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.original_storage_meta = storage_service.SQLITE_META_PATH
        self.original_storage_parquet = storage_service.PARQUET_ROOT
        self.original_task_meta = task_service.SQLITE_META_PATH
        storage_service.SQLITE_META_PATH = self.root / "meta.sqlite"
        storage_service.PARQUET_ROOT = self.root / "parquet"
        task_service.SQLITE_META_PATH = storage_service.SQLITE_META_PATH
        task_service.clear_task_statuses_for_tests(clear_persisted=True)

    def tearDown(self):
        task_service.clear_task_statuses_for_tests(clear_persisted=True)
        storage_service.SQLITE_META_PATH = self.original_storage_meta
        storage_service.PARQUET_ROOT = self.original_storage_parquet
        task_service.SQLITE_META_PATH = self.original_task_meta
        self.temp_dir.cleanup()

    @staticmethod
    def _lineage(*, symbol: str, result_version: str, ready: bool = True) -> dict:
        return {
            "schema_version": "candidate_radar_search_quant_projection_canonical_result_lineage.v1",
            "task_id": f"local-{result_version}",
            "user_confirm_task_id": f"confirm-{result_version}",
            "task_family_id": f"family-{result_version}",
            "symbol": symbol,
            "scope_hash": "a" * 64,
            "provider_call_ledger_ids": ["pcl-1", "pcl-2"],
            "input_packet_keys": ["facts-input"],
            "output_packet_keys": ["candidate", "factor", "next"],
            "data_date": "20260711",
            "freshness_state": "fresh_provider",
            "model_ledger_id": "mlg-safe",
            "result_version": result_version,
            "facts_packet_key": "facts-packet",
            "facts_package_status": "ready" if ready else "partial_provider",
            "facts_package_hash": f"qfp-{result_version}",
            "factor_next_same_result_ready": ready,
            "same_task_fact_model_result_version_ready": ready,
            "current_result_promoted": ready,
            "old_task_can_overwrite_current": False,
            "deepseek_status": "success" if ready else "skipped_missing_facts",
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }

    def _write_candidate_packet(self, lineage: dict) -> None:
        SQLiteMetaStore(storage_service.SQLITE_META_PATH).write_packet(
            storage_service.CURRENT_RESULT_LINEAGE_PACKET_KEY,
            {"search_quant_canonical_result_lineage": lineage},
        )

    def test_versioned_parquet_atomic_pointer_preserves_last_good(self):
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("parquet dependency missing")
        first = pd.DataFrame([{"symbol": "000001.SZ", "result_version": "qrv_first"}])
        second = pd.DataFrame([{"symbol": "601318.SH", "result_version": "qrv_second"}])

        first_result = parquet_store.atomic_promote_versioned_dataset(
            first,
            root=self.root / "parquet",
            name="research_result_lineage",
            version_id="qrv_first",
            required_columns=["symbol", "result_version"],
            lineage={"symbol": "000001.SZ", "result_version": "qrv_first"},
        )
        second_result = parquet_store.atomic_promote_versioned_dataset(
            second,
            root=self.root / "parquet",
            name="research_result_lineage",
            version_id="qrv_second",
            required_columns=["symbol", "result_version"],
            lineage={"symbol": "601318.SH", "result_version": "qrv_second"},
        )

        self.assertTrue(first_result["atomic_promoted"])
        self.assertTrue(second_result["atomic_promoted"])
        self.assertTrue(second_result["last_good_preserved"])
        self.assertEqual(second_result["current_pointer"]["version_id"], "qrv_second")
        self.assertEqual(second_result["last_good_pointer"]["version_id"], "qrv_first")
        manifest = parquet_store.versioned_dataset_manifest(
            root=self.root / "parquet",
            name="research_result_lineage",
        )
        self.assertEqual(manifest["status"], "ready")
        self.assertEqual(manifest["version_count"], 2)
        self.assertEqual(manifest["valid_version_count"], 2)
        self.assertEqual(
            {item["version_id"] for item in manifest["versions"]},
            {"qrv_first", "qrv_second"},
        )
        self.assertTrue(all(item["artifact_sha256_matches"] for item in manifest["versions"]))
        current = duckdb_store.query_parquet_dataset(second_result["current_pointer"]["artifact_path"])
        last_good = duckdb_store.query_parquet_dataset(second_result["last_good_pointer"]["artifact_path"])
        self.assertEqual(current["rows"][0]["symbol"], "601318.SH")
        self.assertEqual(last_good["rows"][0]["symbol"], "000001.SZ")
        self.assertFalse(second_result["external_calls_triggered"])

        Path(second_result["artifact_path"]).write_bytes(b"corrupted-current")
        resolution = parquet_store.resolve_versioned_dataset_current(
            root=self.root / "parquet",
            name="research_result_lineage",
        )
        recovered = duckdb_store.query_parquet_dataset(resolution["selected_artifact_path"])
        self.assertEqual(
            resolution["status"],
            "resolved_last_good_after_current_failure",
        )
        self.assertEqual(resolution["current_pointer"]["status"], "artifact_checksum_mismatch")
        self.assertEqual(resolution["selected_pointer_kind"], "last_good")
        self.assertEqual(resolution["selected_version_id"], "qrv_first")
        self.assertTrue(resolution["degraded_recovery_active"])
        self.assertFalse(resolution["writes_files"])
        self.assertEqual(recovered["rows"][0]["symbol"], "000001.SZ")
        cache = storage_service.storage_current_result_cache()
        self.assertEqual(cache["status"], "storage_current_result_cache_degraded_last_good")
        self.assertEqual(cache["selected_pointer_kind"], "last_good")
        self.assertEqual(cache["symbol"], "000001.SZ")
        self.assertEqual(cache["result_version"], "qrv_first")
        self.assertEqual(cache["facts_package_hash"], "")
        self.assertEqual(cache["model_ledger_id"], "")
        self.assertEqual(cache["result"]["symbol"], "000001.SZ")
        self.assertTrue(cache["degraded_recovery_active"])

    def test_current_result_get_is_cache_only_when_missing(self):
        from fastapi.testclient import TestClient
        from server.main import app

        before = len(task_service.list_task_statuses())
        response = TestClient(app).get("/api/storage/current-result").json()
        after = len(task_service.list_task_statuses())

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["status"], "storage_current_result_cache_missing")
        self.assertEqual(packet["symbol"], "")
        self.assertEqual(packet["result_version"], "")
        self.assertEqual(packet["data_date"], "")
        self.assertEqual(packet["freshness_state"], "")
        self.assertEqual(packet["result"], {})
        self.assertEqual(packet["result_row_count"], 0)
        self.assertTrue(packet["cache_only"])
        self.assertFalse(packet["cache_get_creates_task"])
        self.assertFalse(packet["cache_get_writes_files"])
        self.assertFalse(packet["cache_get_refreshes_stale_result"])
        self.assertFalse(packet["cache_get_deletes_versions"])
        self.assertEqual(packet["ttl_status"], "ttl_source_unavailable")
        self.assertEqual(packet["retention_status"], "retention_plan_blocked_manifest_unavailable")
        self.assertFalse(packet["external_calls_triggered"])
        self.assertEqual(before, after)
        self.assertEqual(response["call_ledger"][0]["endpoint"], "GET /api/storage/current-result")

    def test_ttl_and_retention_plan_are_read_only_and_protect_live_pointers(self):
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("parquet dependency missing")
        for index in range(1, 4):
            version_id = f"qrv_{index}"
            frame = pd.DataFrame([{"symbol": "000001.SZ", "result_version": version_id}])
            promoted = parquet_store.atomic_promote_versioned_dataset(
                frame,
                root=self.root / "parquet",
                name="research_result_lineage",
                version_id=version_id,
                required_columns=["symbol", "result_version"],
                lineage={"symbol": "000001.SZ", "result_version": version_id},
            )
            self.assertTrue(promoted["atomic_promoted"])

        current = parquet_store.versioned_dataset_pointer(
            root=self.root / "parquet",
            name="research_result_lineage",
            pointer="current",
        )
        promoted_at = datetime.fromisoformat(str(current["promoted_at"]))
        fresh = parquet_store.versioned_dataset_ttl_status(
            current,
            ttl_seconds=3600,
            now=promoted_at + timedelta(minutes=30),
        )
        stale = parquet_store.versioned_dataset_ttl_status(
            current,
            ttl_seconds=3600,
            now=promoted_at + timedelta(hours=2),
        )
        retention = parquet_store.versioned_dataset_retention_plan(
            root=self.root / "parquet",
            name="research_result_lineage",
            max_versions=2,
        )
        dataset_root = self.root / "parquet" / "research_result_lineage"
        files_before_get = sorted(str(path.relative_to(dataset_root)) for path in dataset_root.rglob("*"))

        from fastapi.testclient import TestClient
        from server.main import app

        packet = TestClient(app).get("/api/storage/current-result").json()["data"]
        files_after_get = sorted(str(path.relative_to(dataset_root)) for path in dataset_root.rglob("*"))

        self.assertEqual(fresh["status"], "fresh")
        self.assertFalse(fresh["refresh_recommended"])
        self.assertEqual(stale["status"], "stale")
        self.assertTrue(stale["refresh_recommended"])
        self.assertFalse(stale["auto_refresh_on_get"])
        self.assertFalse(stale["writes_files"])
        self.assertEqual(retention["status"], "retention_cleanup_candidates_ready")
        self.assertEqual(retention["protected_version_ids"], ["qrv_2", "qrv_3"])
        self.assertEqual(retention["cleanup_candidate_count"], 1)
        self.assertEqual(retention["cleanup_candidates"][0]["version_id"], "qrv_1")
        self.assertFalse(retention["delete_executed"])
        self.assertFalse(retention["auto_cleanup"])
        self.assertFalse(retention["writes_files"])
        self.assertEqual(files_before_get, files_after_get)
        self.assertEqual(packet["selected_version_id"], "qrv_3")
        self.assertEqual(packet["ttl_status"], "fresh")
        self.assertEqual(packet["retention_protected_version_ids"], ["qrv_2", "qrv_3"])
        self.assertFalse(packet["cache_get_refreshes_stale_result"])
        self.assertFalse(packet["cache_get_deletes_versions"])
        self.assertFalse(packet["retention_delete_executed"])

    def test_retention_cleanup_resumes_from_journal_after_delete_interruption(self):
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("parquet dependency missing")
        for index in range(1, 4):
            version_id = f"qrv_recovery_{index}"
            parquet_store.atomic_promote_versioned_dataset(
                pd.DataFrame([{"symbol": "601318.SH", "result_version": version_id}]),
                root=self.root / "parquet",
                name="research_result_lineage",
                version_id=version_id,
                required_columns=["symbol", "result_version"],
                lineage={"symbol": "601318.SH", "result_version": version_id},
            )
        plan = parquet_store.versioned_dataset_retention_plan(
            root=self.root / "parquet",
            name="research_result_lineage",
            max_versions=2,
        )
        request = {
            "root": self.root / "parquet",
            "name": "research_result_lineage",
            "max_versions": 2,
            "expected_plan_hash": plan["plan_hash"],
            "expected_candidate_version_ids": plan["cleanup_candidate_version_ids"],
            "approved_by_user": True,
        }

        with patch("storage.parquet_store._delete_version_artifact", side_effect=OSError("simulated")):
            interrupted = parquet_store.execute_versioned_dataset_retention_cleanup(**request)

        journal = parquet_store.versioned_dataset_retention_cleanup_journal(
            root=self.root / "parquet",
            name="research_result_lineage",
        )
        journal_path = Path(journal["journal_path"])
        journal_before_get = journal_path.read_bytes()
        cache = storage_service.storage_current_result_cache()
        journal_after_get = journal_path.read_bytes()
        candidate_path = (
            self.root
            / "parquet"
            / "research_result_lineage"
            / "versions"
            / "qrv_recovery_1.parquet"
        )

        self.assertEqual(interrupted["status"], "retention_cleanup_partial_orphaned_artifacts")
        self.assertFalse(interrupted["delete_executed"])
        self.assertEqual(interrupted["cleanup_journal_status"], "partial")
        self.assertEqual(journal["status"], "partial")
        self.assertTrue(journal["recovery_ready"])
        self.assertEqual(journal["pending_artifact_count"], 1)
        self.assertTrue(candidate_path.exists())
        self.assertTrue(cache["retention_cleanup_recovery_ready"])
        self.assertEqual(cache["retention_cleanup_pending_artifact_count"], 1)
        self.assertEqual(journal_before_get, journal_after_get)

        recovered = parquet_store.execute_versioned_dataset_retention_cleanup(**request)
        journal_after = parquet_store.versioned_dataset_retention_cleanup_journal(
            root=self.root / "parquet",
            name="research_result_lineage",
        )
        current = parquet_store.versioned_dataset_pointer(
            root=self.root / "parquet",
            name="research_result_lineage",
            pointer="current",
        )
        last_good = parquet_store.versioned_dataset_pointer(
            root=self.root / "parquet",
            name="research_result_lineage",
            pointer="last_good",
        )

        self.assertEqual(recovered["status"], "retention_cleanup_recovered")
        self.assertTrue(recovered["delete_executed"])
        self.assertTrue(recovered["recovery_execution"])
        self.assertFalse(recovered["writes_manifest"])
        self.assertFalse(candidate_path.exists())
        self.assertEqual(journal_after["status"], "completed")
        self.assertTrue(journal_after["cleanup_completed"])
        self.assertFalse(journal_after["recovery_ready"])
        self.assertEqual(journal_after["pending_artifact_count"], 0)
        self.assertEqual(current["version_id"], "qrv_recovery_3")
        self.assertEqual(last_good["version_id"], "qrv_recovery_2")

    def test_invalid_version_does_not_move_current_pointer(self):
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("parquet dependency missing")
        good = pd.DataFrame([{"symbol": "000001.SZ", "result_version": "qrv_good"}])
        parquet_store.atomic_promote_versioned_dataset(
            good,
            root=self.root / "parquet",
            name="research_result_lineage",
            version_id="qrv_good",
            required_columns=["symbol", "result_version"],
        )
        invalid = pd.DataFrame([{"symbol": "601318.SH"}])
        result = parquet_store.atomic_promote_versioned_dataset(
            invalid,
            root=self.root / "parquet",
            name="research_result_lineage",
            version_id="qrv_invalid",
            required_columns=["symbol", "result_version"],
        )
        current = parquet_store.versioned_dataset_pointer(
            root=self.root / "parquet",
            name="research_result_lineage",
            pointer="current",
        )

        self.assertEqual(result["status"], "validation_failed")
        self.assertTrue(result["current_pointer_unchanged"])
        self.assertEqual(current["version_id"], "qrv_good")

        conflict = pd.DataFrame([{"symbol": "601318.SH", "result_version": "qrv_good"}])
        conflict_result = parquet_store.atomic_promote_versioned_dataset(
            conflict,
            root=self.root / "parquet",
            name="research_result_lineage",
            version_id="qrv_good",
            required_columns=["symbol", "result_version"],
        )
        current_after_conflict = parquet_store.versioned_dataset_pointer(
            root=self.root / "parquet",
            name="research_result_lineage",
            pointer="current",
        )
        self.assertEqual(conflict_result["status"], "version_conflict")
        self.assertTrue(conflict_result["current_pointer_unchanged"])
        self.assertEqual(current_after_conflict["version_id"], "qrv_good")

    def test_version_manifest_detects_artifact_corruption(self):
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("parquet dependency missing")
        frame = pd.DataFrame([{"symbol": "000001.SZ", "result_version": "qrv_corrupt"}])
        promoted = parquet_store.atomic_promote_versioned_dataset(
            frame,
            root=self.root / "parquet",
            name="research_result_lineage",
            version_id="qrv_corrupt",
            required_columns=["symbol", "result_version"],
        )
        Path(promoted["artifact_path"]).write_bytes(b"corrupted")

        manifest = parquet_store.versioned_dataset_manifest(
            root=self.root / "parquet",
            name="research_result_lineage",
        )

        self.assertEqual(manifest["status"], "manifest_validation_failed")
        self.assertEqual(manifest["valid_version_count"], 0)
        self.assertFalse(manifest["versions"][0]["artifact_sha256_matches"])
        resolution = parquet_store.resolve_versioned_dataset_current(
            root=self.root / "parquet",
            name="research_result_lineage",
        )
        self.assertEqual(resolution["status"], "no_valid_version_available")
        self.assertTrue(resolution["no_valid_version_available"])
        self.assertFalse(resolution["degraded_recovery_active"])

    def test_task_promotes_only_matching_canonical_lineage(self):
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("parquet dependency missing")
        lineage = self._lineage(symbol="601318.SH", result_version="qrv_canonical")
        self._write_candidate_packet(lineage)

        task = storage_service.run_storage_current_result_atomic_promotion_task(
            {
                "source": "focused_test",
                "approved_by_user": True,
                "expected_symbol": "601318.SH",
                "expected_result_version": "qrv_canonical",
            }
        )
        receipt = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.STORAGE_CURRENT_RESULT_ATOMIC_PROMOTION_PACKET_KEY
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(receipt["status"], "storage_current_result_atomic_promotion_success")
        self.assertTrue(receipt["physical_write_executed"])
        self.assertTrue(receipt["atomic_current_promoted"])
        self.assertTrue(receipt["duckdb_readback_verified"])
        self.assertTrue(receipt["manifest_current_version_ready"])
        self.assertEqual(receipt["manifest_version_count"], 1)
        self.assertEqual(receipt["version_manifest"]["status"], "ready")
        self.assertEqual(receipt["duckdb_readback"]["status"], "verified")
        self.assertEqual(receipt["duckdb_readback"]["row_count"], 1)
        self.assertEqual(receipt["duckdb_readback"]["symbol"], "601318.SH")
        self.assertEqual(receipt["duckdb_readback"]["result_version"], "qrv_canonical")
        self.assertEqual(receipt["current_pointer"]["version_id"], "qrv_canonical")
        self.assertEqual(receipt["current_pointer"]["lineage"]["symbol"], "601318.SH")
        self.assertFalse(receipt["production_storage_complete"])
        self.assertFalse(receipt["external_calls_triggered"])
        self.assertFalse(receipt["tushare_called"])
        self.assertFalse(receipt["deepseek_called"])
        self.assertTrue(receipt["does_not_execute_trades"])
        overview = storage_service.storage_overview(limit=5)
        visible = overview["storage_current_result_atomic_promotion"]
        self.assertEqual(visible["status"], "storage_current_result_atomic_promotion_current")
        self.assertTrue(visible["atomic_promotion_current"])
        self.assertTrue(visible["duckdb_readback_verified"])
        self.assertTrue(visible["manifest_current_version_ready"])
        self.assertFalse(visible["can_launch_atomic_promotion"])
        self.assertEqual(visible["current_pointer"]["version_id"], "qrv_canonical")
        from fastapi.testclient import TestClient
        from server.main import app

        cache_response = TestClient(app).get("/api/storage/current-result").json()
        cache = cache_response["data"]
        self.assertEqual(cache["status"], "storage_current_result_cache_ready_current")
        self.assertEqual(cache["selected_pointer_kind"], "current")
        self.assertEqual(cache["symbol"], "601318.SH")
        self.assertEqual(cache["result_version"], "qrv_canonical")
        self.assertEqual(cache["facts_package_hash"], "qfp-qrv_canonical")
        self.assertEqual(cache["model_ledger_id"], "mlg-safe")
        self.assertEqual(cache["data_date"], "20260711")
        self.assertEqual(cache["freshness_state"], "fresh_provider")
        self.assertEqual(cache["result"]["symbol"], "601318.SH")
        self.assertEqual(cache["result"]["result_version"], "qrv_canonical")
        self.assertEqual(cache["result_row_count"], 1)
        self.assertTrue(cache["duckdb_readback_verified"])
        self.assertFalse(cache["cache_get_creates_task"])
        self.assertFalse(cache["cache_get_writes_files"])
        self.assertFalse(cache["external_calls_triggered"])
        durable = storage_service.storage_physical_durable_evidence_recipe()
        durable_rows = {row["evidence_key"]: row for row in durable["rows"]}
        self.assertTrue(durable["current_result_atomic_parquet_promotion_done"])
        self.assertNotIn(
            "current_result_atomic_parquet_promotion_required",
            durable["missing_durable_evidence"],
        )
        self.assertEqual(
            durable_rows["current_result_atomic_parquet_promotion_required"]["status"],
            "passed_local_atomic_parquet_direct_evidence",
        )
        promotion_review = storage_service.storage_production_promotion_review_packet(
            payload_safe={"approved_by_user": False}
        )
        promotion_rows = {row["criterion"]: row for row in promotion_review["rows"]}
        self.assertTrue(promotion_review["current_result_atomic_parquet_promotion_done"])
        self.assertTrue(promotion_review["source_physical_task_executed"])
        self.assertTrue(
            promotion_rows["current_result_atomic_parquet_evidence_reviewed"]["passed"]
        )
        self.assertFalse(promotion_review["production_storage_complete"])

        blocked = storage_service.run_storage_current_result_atomic_promotion_task(
            {
                "source": "focused_test_mismatch",
                "approved_by_user": True,
                "expected_symbol": "000001.SZ",
                "expected_result_version": "qrv_canonical",
            }
        )
        current = parquet_store.versioned_dataset_pointer(
            root=storage_service.PARQUET_ROOT,
            name=storage_service.CURRENT_RESULT_LINEAGE_DATASET,
            pointer="current",
        )
        self.assertEqual(blocked["status"], "failed")
        self.assertEqual(current["version_id"], "qrv_canonical")

    def test_degraded_lineage_is_not_promoted(self):
        lineage = self._lineage(symbol="000000.SZ", result_version="qrv_degraded", ready=False)
        self._write_candidate_packet(lineage)
        task = storage_service.run_storage_current_result_atomic_promotion_task(
            {
                "source": "focused_test_degraded",
                "approved_by_user": True,
                "expected_symbol": "000000.SZ",
                "expected_result_version": "qrv_degraded",
            }
        )
        receipt = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.STORAGE_CURRENT_RESULT_ATOMIC_PROMOTION_PACKET_KEY
        )

        self.assertEqual(task["status"], "failed")
        self.assertEqual(
            receipt["status"],
            "storage_current_result_atomic_promotion_blocked_canonical_lineage_not_ready",
        )
        self.assertFalse(receipt["physical_write_executed"])
        self.assertFalse(
            (storage_service.PARQUET_ROOT / storage_service.CURRENT_RESULT_LINEAGE_DATASET / "current.json").exists()
        )

    def test_two_real_versions_reach_current_result_storage_acceptance(self):
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("parquet dependency missing")

        task_ids = []
        for symbol, version in (("601318.SH", "qrv_first"), ("600519.SH", "qrv_second")):
            self._write_candidate_packet(self._lineage(symbol=symbol, result_version=version))
            task = storage_service.run_storage_current_result_atomic_promotion_task(
                {
                    "source": "focused_current_result_acceptance",
                    "approved_by_user": True,
                    "expected_symbol": symbol,
                    "expected_result_version": version,
                }
            )
            self.assertEqual(task["status"], "success")
            task_ids.append(task["task_id"])

        evidence = storage_service.storage_current_result_atomic_promotion_evidence()
        self.assertTrue(evidence["current_result_storage_acceptance_ready"])
        self.assertEqual(evidence["current_result_storage_acceptance_status"], "current_result_storage_acceptance_ready")
        self.assertTrue(evidence["last_good_pointer_ready"])
        self.assertTrue(evidence["current_last_good_distinct"])
        self.assertTrue(evidence["retention_protects_current_and_last_good"])
        self.assertEqual(evidence["current_pointer"]["version_id"], "qrv_second")
        self.assertEqual(evidence["last_good_pointer"]["version_id"], "qrv_first")
        self.assertEqual(evidence["manifest_version_count"], 2)
        self.assertTrue(evidence["duckdb_readback_verified"])
        self.assertEqual(evidence["latest_receipt_task_id"], task_ids[-1])

        recipe = storage_service.storage_physical_execution_recipe()
        request_task = storage_service.run_storage_physical_execution_request_task(
            {
                "source": "focused_current_result_acceptance",
                "approved_by_user": True,
                "physical_execution_scope_hash": recipe["physical_execution_scope_hash"],
            }
        )
        self.assertEqual(request_task["status"], "success")
        request = storage_service.storage_physical_execution_request_evidence()
        review_task = storage_service.run_storage_production_promotion_review_task(
            {
                "approved_by_user": True,
                "physical_execution_scope_hash": request["physical_execution_scope_hash"],
            }
        )
        self.assertEqual(review_task["status"], "success")
        review = storage_service.storage_production_promotion_review_evidence()
        self.assertEqual(review["status"], "storage_current_result_acceptance_ready_full_storage_pending")
        self.assertTrue(review["current_result_storage_acceptance_ready"])
        self.assertTrue(review["current_result_storage_direct_evidence_complete"])
        self.assertTrue(review["full_storage_migration_pending"])
        self.assertFalse(review["production_storage_complete"])
        self.assertGreater(review["production_blocker_count"], 0)
        durable = storage_service.storage_physical_durable_evidence_recipe()
        self.assertEqual(
            durable["status"],
            "storage_current_result_direct_evidence_complete_full_migration_pending",
        )
        self.assertTrue(durable["current_result_storage_acceptance_ready"])
        self.assertTrue(durable["current_result_storage_direct_evidence_complete"])
        self.assertTrue(durable["full_storage_migration_pending"])
        self.assertFalse(durable["production_storage_complete"])

    def test_atomic_evidence_uses_current_pointer_when_canonical_packet_is_missing(self):
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("parquet dependency missing")

        for symbol, version in (("601318.SH", "qrv_first"), ("600519.SH", "qrv_second")):
            self._write_candidate_packet(self._lineage(symbol=symbol, result_version=version))
            task = storage_service.run_storage_current_result_atomic_promotion_task(
                {
                    "source": "focused_current_result_pointer_replay",
                    "approved_by_user": True,
                    "expected_symbol": symbol,
                    "expected_result_version": version,
                }
            )
            self.assertEqual(task["status"], "success")

        SQLiteMetaStore(storage_service.SQLITE_META_PATH).write_packet(
            storage_service.CURRENT_RESULT_LINEAGE_PACKET_KEY,
            {"search_quant_canonical_result_lineage_archived": True},
        )

        evidence = storage_service.storage_current_result_atomic_promotion_evidence()

        self.assertEqual(
            evidence["status"],
            "storage_current_result_atomic_promotion_current",
        )
        self.assertFalse(evidence["canonical_lineage_ready"])
        self.assertFalse(evidence["can_launch_atomic_promotion"])
        self.assertTrue(evidence["atomic_promotion_current"])
        self.assertTrue(evidence["physical_write_executed"])
        self.assertTrue(evidence["duckdb_readback_verified"])
        self.assertTrue(evidence["manifest_current_version_ready"])
        self.assertEqual(evidence["expected_symbol"], "600519.SH")
        self.assertEqual(evidence["expected_result_version"], "qrv_second")
        self.assertEqual(evidence["resolved_symbol"], "600519.SH")
        self.assertEqual(evidence["resolved_result_version"], "qrv_second")
        self.assertTrue(evidence["last_good_pointer_ready"])
        self.assertTrue(evidence["retention_protects_current_and_last_good"])
        self.assertTrue(evidence["current_result_storage_acceptance_ready"])

        durable = storage_service.storage_physical_durable_evidence_recipe()
        self.assertFalse(durable["current_result_atomic_parquet_promotion_done"])
        self.assertFalse(durable["current_result_storage_direct_evidence_complete"])
        self.assertFalse(durable["current_result_storage_acceptance_ready"])
        self.assertFalse(durable["production_storage_complete"])

    def test_task_catalog_exposes_physical_writer_without_external_sources(self):
        catalog = task_service.build_task_catalog()
        row = next(
            item
            for item in catalog["tasks"]
            if item.get("task_type") == "run_storage_current_result_atomic_promotion"
        )
        self.assertEqual(row["route"], "POST /api/storage/current-result/atomic-promote")
        self.assertTrue(row["writes_parquet_on_post"])
        self.assertTrue(row["writes_manifest_on_post"])
        self.assertEqual(row["manifest_scope"], "dataset_local_immutable_version_inventory")
        self.assertTrue(row["writes_atomic_current_pointer_on_post"])
        self.assertTrue(row["preserves_last_good_pointer"])
        self.assertEqual(row["possible_external_sources"], [])
        self.assertFalse(row["production_storage_complete"])
        self.assertTrue(row["does_not_execute_trades"])
        self.assertTrue(row["does_not_modify_strategy_action"])


if __name__ == "__main__":
    unittest.main()
