import json
import tempfile
import unittest
from pathlib import Path

from server.services import storage_service, task_service, worker_service
from storage import parquet_store
from storage.sqlite_meta import SQLiteMetaStore


class V04DurableStorageRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.original_storage_meta = storage_service.SQLITE_META_PATH
        self.original_storage_parquet = storage_service.PARQUET_ROOT
        self.original_storage_v04 = storage_service.V04_ACCEPTANCE_ROOT
        self.original_worker_meta = worker_service.SQLITE_META_PATH
        self.original_worker_v04 = worker_service.WORKER_V04_RUNTIME_ROOT
        self.original_task_meta = task_service.SQLITE_META_PATH
        storage_service.SQLITE_META_PATH = self.root / "meta.sqlite"
        storage_service.PARQUET_ROOT = self.root / "parquet"
        storage_service.V04_ACCEPTANCE_ROOT = self.root / "v04_acceptance"
        worker_service.SQLITE_META_PATH = self.root / "meta.sqlite"
        worker_service.WORKER_V04_RUNTIME_ROOT = self.root / "v04_acceptance"
        task_service.SQLITE_META_PATH = self.root / "meta.sqlite"
        task_service.clear_task_statuses_for_tests(clear_persisted=True)

    def tearDown(self):
        task_service.clear_task_statuses_for_tests(clear_persisted=True)
        storage_service.SQLITE_META_PATH = self.original_storage_meta
        storage_service.PARQUET_ROOT = self.original_storage_parquet
        storage_service.V04_ACCEPTANCE_ROOT = self.original_storage_v04
        worker_service.SQLITE_META_PATH = self.original_worker_meta
        worker_service.WORKER_V04_RUNTIME_ROOT = self.original_worker_v04
        task_service.SQLITE_META_PATH = self.original_task_meta
        self.tmp.cleanup()

    def _storage_payload(self, scope_hash: str, version: str, *, inject: str = "") -> dict:
        payload = {
            "source": "v04_focused_test",
            "approved_by_user": True,
            "physical_execution_scope_hash": scope_hash,
            "confirm_physical_execution": True,
            "confirm_local_durable_write": True,
            "confirm_scope_hash": scope_hash,
            "result_version": version,
            "sample_rows": [
                {"ts_code": "000001.SZ", "trade_date": "20260710", "metric": "alpha", "value": 1.5, "stage": "s1"},
                {"ts_code": "000002.SZ", "trade_date": "20260710", "metric": "alpha", "value": 2.5, "stage": "s1"},
                {"ts_code": "600000.SH", "trade_date": "20260711", "metric": "alpha", "value": 3.5, "stage": "s2"},
            ],
        }
        if inject:
            payload["inject_failure_after_stage"] = inject
        return payload

    def test_storage_phase_a_executes_physical_parquet_duckdb_sqlite_and_preserves_last_good_on_failure(self):
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("parquet dependency missing")
        recipe = storage_service.storage_physical_execution_recipe()
        scope_hash = recipe["physical_execution_scope_hash"]
        request_task = storage_service.run_storage_physical_execution_request_task(
            {
                "source": "v04_focused_test",
                "approved_by_user": True,
                "physical_execution_scope_hash": scope_hash,
            }
        )
        self.assertEqual(request_task["status"], "success")

        legacy = storage_service.run_storage_physical_execution_phase_a_task(
            {
                "source": "v04_focused_test",
                "approved_by_user": True,
                "physical_execution_scope_hash": scope_hash,
            }
        )
        self.assertEqual(legacy["status"], "success")
        legacy_receipt = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.STORAGE_PHYSICAL_EXECUTION_PHASE_A_PACKET_KEY
        )
        self.assertFalse(legacy_receipt["v04_durable_storage_executed"])
        self.assertFalse(storage_service.V04_ACCEPTANCE_ROOT.exists())

        first = storage_service.run_storage_physical_execution_phase_a_task(
            self._storage_payload(scope_hash, "v04_first")
        )
        second = storage_service.run_storage_physical_execution_phase_a_task(
            self._storage_payload(scope_hash, "v04_second")
        )

        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "success")
        receipt = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.STORAGE_PHYSICAL_EXECUTION_PHASE_A_PACKET_KEY
        )
        result = receipt["v04_physical_execution"]
        manifest = result["manifest"]
        acceptance_dir = storage_service.V04_ACCEPTANCE_ROOT / storage_service._storage_v04_scope_component(scope_hash)
        parquet_path = parquet_store.dataset_path(
            root=acceptance_dir / "parquet",
            name="storage_phase_a_sample",
        )
        self.assertEqual(receipt["status"], "storage_physical_execution_phase_a_v04_durable_execution_success")
        self.assertTrue(parquet_path.exists())
        self.assertTrue((acceptance_dir / "manifest.json").exists())
        self.assertTrue(result["parquet_path"].startswith("v04_acceptance/"))
        self.assertNotIn(str(self.root), json.dumps(receipt, ensure_ascii=False))
        self.assertEqual(result["row_count"], 3)
        self.assertEqual(result["schema"]["status"], "ready")
        self.assertTrue(result["duckdb_query_parity"])
        self.assertTrue(result["sqlite_readback_verified"])
        self.assertTrue(result["atomic_promoted"])
        self.assertTrue(result["last_good_preserved"])
        self.assertEqual(result["current_after"]["version_id"], "v04_second")
        self.assertEqual(result["last_good_after"]["version_id"], "v04_first")
        self.assertEqual(manifest["row_count"], 3)
        self.assertEqual(manifest["columns"], storage_service.V04_STORAGE_ACCEPTANCE_COLUMNS)
        self.assertEqual(manifest["manifest_sha256"], storage_service._storage_v04_sha256_json({k: v for k, v in manifest.items() if k != "manifest_sha256"}))
        self.assertFalse(manifest["contains_secret"])
        self.assertNotIn("000001.SZ", json.dumps(manifest, ensure_ascii=False))

        failed = storage_service.run_storage_physical_execution_phase_a_task(
            self._storage_payload(
                scope_hash,
                "v04_failed",
                inject="parquet_write_before_atomic_promote",
            )
        )
        failed_receipt = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.STORAGE_PHYSICAL_EXECUTION_PHASE_A_PACKET_KEY
        )
        failed_result = failed_receipt["v04_physical_execution"]

        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed_result["status"], "storage_v04_physical_execution_injected_failure_current_unchanged")
        self.assertTrue((acceptance_dir / "failed_tmp_marker.json").exists())
        self.assertEqual(failed_result["current_after"]["version_id"], "v04_second")
        self.assertEqual(failed_result["last_good_after"]["version_id"], "v04_first")
        self.assertFalse(failed_result["atomic_promoted"])
        self.assertFalse(failed_receipt["production_storage_complete"])
        self.assertFalse(failed_receipt["external_calls_triggered"])
        self.assertFalse(failed_receipt["tushare_called"])
        self.assertTrue(failed_receipt["does_not_execute_trades"])

    def _worker_payload(self, scope_hash: str, *, fail_on_symbol: str = "") -> dict:
        pool = [{"symbol": f"{index:06d}.SZ", "weight": index + 1} for index in range(1, 26)]
        payload = {
            "runtime_mode": "v04_local_batch",
            "operator_approved": True,
            "confirm_local_in_process_runtime": True,
            "runtime_scope_hash": scope_hash,
            "confirm_scope_hash": scope_hash,
            "chunk_size": 7,
            "pool": pool,
        }
        if fail_on_symbol:
            payload["fail_on_symbol"] = fail_on_symbol
        return payload

    def test_worker_v04_local_batch_runtime_processes_full_pool_logs_and_preserves_last_good(self):
        scope_hash = "worker-v04-scope"

        blocked = worker_service.run_worker_runtime_qa_execution(
            {
                "runtime_mode": "v04_local_batch",
                "operator_approved": True,
                "runtime_scope_hash": scope_hash,
                "confirm_scope_hash": scope_hash,
                "pool": ["000001.SZ"],
            }
        )
        self.assertEqual(blocked["status"], "failed")
        self.assertFalse(worker_service.WORKER_V04_RUNTIME_ROOT.exists())

        first = worker_service.run_worker_runtime_qa_execution(self._worker_payload(scope_hash))
        second = worker_service.run_worker_runtime_qa_execution(self._worker_payload(scope_hash))
        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "success")
        second_result = second["worker_v04_runtime"]
        self.assertEqual(second_result["pool_count"], 25)
        self.assertEqual(second_result["processed_count"], 25)
        self.assertEqual(second_result["chunk_size"], 7)
        self.assertEqual(second_result["chunk_count"], 4)
        self.assertEqual(second_result["append_only_event_count"], 4)
        runtime_dir = worker_service.WORKER_V04_RUNTIME_ROOT / scope_hash / "worker_runtime"
        event_log_path = runtime_dir / "events.jsonl"
        self.assertTrue(event_log_path.exists())
        self.assertEqual(len(event_log_path.read_text(encoding="utf-8").strip().splitlines()), 8)
        self.assertTrue(second_result["event_log_path"].startswith("v04_acceptance/"))
        self.assertNotIn(str(self.root), json.dumps(second_result, ensure_ascii=False))
        self.assertEqual(second_result["current_after"]["status"], "ready")
        self.assertEqual(second_result["last_good_after"]["status"], "ready")
        self.assertTrue(second_result["local_runtime_not_full_market_claim"])
        self.assertTrue(second_result["local_runtime_is_not_celery_redis_production"])
        self.assertFalse(second_result["celery_worker_started"])
        self.assertFalse(second_result["redis_pinged"])
        self.assertFalse(second_result["external_calls_triggered"])
        self.assertTrue(second_result["does_not_execute_trades"])

        failed = worker_service.run_worker_runtime_qa_execution(
            self._worker_payload(scope_hash, fail_on_symbol="000010.SZ")
        )
        failed_result = failed["worker_v04_runtime"]
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed_result["status"], "worker_v04_local_batch_runtime_failed_partial")
        self.assertLess(failed_result["processed_count"], failed_result["pool_count"])
        self.assertEqual(failed_result["current_after"]["manifest_sha256"], second_result["current_after"]["manifest_sha256"])
        self.assertEqual(failed_result["last_good_after"]["manifest_sha256"], second_result["last_good_after"]["manifest_sha256"])
        self.assertTrue(failed_result["last_good_preserved"])
        self.assertEqual(len(event_log_path.read_text(encoding="utf-8").strip().splitlines()), 10)


if __name__ == "__main__":
    unittest.main()
