from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from storage.redis_cache import RedisCache
from storage.sqlite_meta import SQLiteMetaStore


class CommandCenter3StorageTests(unittest.TestCase):
    def test_sqlite_packet_and_task_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteMetaStore(Path(tmp) / "meta.sqlite")
            packet = {"packet_key": "demo_packet", "value": 3}
            store.write_packet("demo_packet", packet)
            self.assertEqual(store.read_packet("demo_packet"), packet)
            packet_meta = store.list_packet_metadata()
            self.assertEqual(packet_meta[0]["packet_key"], "demo_packet")
            self.assertGreater(packet_meta[0]["payload_bytes"], 0)

            task = {"task_id": "task-1", "status": "success"}
            store.write_task_status(task)
            self.assertEqual(store.read_task_status("task-1"), task)
            task_meta = store.list_task_metadata()
            self.assertEqual(task_meta[0]["task_id"], "task-1")
            self.assertEqual(task_meta[0]["status"], "success")
            self.assertEqual(store.clear_task_statuses()["deleted_count"], 1)
            self.assertEqual(store.list_task_metadata(), [])

    def test_redis_cache_memory_fallback(self):
        cache = RedisCache(use_memory_fallback=True)
        cache.client = None
        cache.set_json("packet:demo", {"ok": True})
        self.assertEqual(cache.get_json("packet:demo"), {"ok": True})

    def test_parquet_store_gracefully_handles_dependency(self):
        from storage import parquet_store

        status = parquet_store.dependency_status()
        if not status["available"]:
            result = parquet_store.write_dataset(pd.DataFrame({"a": [1]}), name="daily")
            self.assertEqual(result["status"], "dependency_missing")
            return
        with tempfile.TemporaryDirectory() as tmp:
            result = parquet_store.write_dataset(pd.DataFrame({"a": [1]}), root=tmp, name="daily")
            self.assertEqual(result["status"], "written")
            self.assertEqual(result["row_count"], 1)
            self.assertFalse(result["external_calls_triggered"])
            metadata = parquet_store.dataset_metadata(root=tmp, name="daily")
            self.assertEqual(metadata["status"], "ready")

    def test_duckdb_store_gracefully_handles_dependency(self):
        from storage import duckdb_store, parquet_store

        if not duckdb_store.dependency_status()["available"]:
            result = duckdb_store.query_factor_values("missing.parquet")
            self.assertEqual(result["status"], "dependency_missing")
            return
        missing = duckdb_store.query_factor_values("missing.parquet")
        self.assertEqual(missing["status"], "missing")
        self.assertEqual(missing["row_count"], 0)
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        with tempfile.TemporaryDirectory() as tmp:
            out = parquet_store.write_factor_values(pd.DataFrame({"factor_key": ["momentum_20d"]}), root=tmp)
            result = duckdb_store.query_factor_values(out["path"])
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["row_count"], 1)
            generic = duckdb_store.query_parquet_dataset(out["path"])
            self.assertEqual(generic["status"], "ready")
            self.assertFalse(generic["external_calls_triggered"])

    def test_duckdb_store_filters_parquet_by_symbol_and_date_window(self):
        from storage import duckdb_store, parquet_store

        if not duckdb_store.dependency_status()["available"]:
            self.skipTest("duckdb dependency missing")
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        with tempfile.TemporaryDirectory() as tmp:
            out = parquet_store.write_dataset(
                pd.DataFrame(
                    {
                        "ts_code": ["002008.SZ", "002008.SZ", "600519.SH"],
                        "trade_date": ["20260603", "20260611", "20260611"],
                        "close": [10.1, 10.8, 1600.0],
                    }
                ),
                root=tmp,
                name="daily",
            )
            result = duckdb_store.query_parquet_dataset(
                out["path"],
                ts_code="002008.SZ",
                start_date="2026-06-01",
                end_date="2026-06-10",
            )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["query_wrapper"], "duckdb_filtered_parquet.v1")
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["rows"][0]["ts_code"], "002008.SZ")
        self.assertEqual(result["rows"][0]["trade_date"], "20260603")
        self.assertEqual({item["filter"] for item in result["applied_filters"]}, {"ts_code", "start_date", "end_date"})
        self.assertFalse(result["skipped_filters"])
        self.assertFalse(result["external_calls_triggered"])

    def test_parquet_store_writes_partitioned_dataset(self):
        from storage import parquet_store

        if not parquet_store.dependency_status()["available"]:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        with tempfile.TemporaryDirectory() as tmp:
            result = parquet_store.write_partitioned_dataset(
                pd.DataFrame(
                    {
                        "ts_code": ["002008.SZ", "600519.SH"],
                        "trade_date": ["20260611", "20260612"],
                        "factor_key": ["momentum_20d", "volatility_20d"],
                        "raw_value": [0.12, 0.04],
                    }
                ),
                root=tmp,
                name="factor_values",
                partition_columns=["trade_date"],
            )
            metadata = parquet_store.partitioned_dataset_metadata(root=tmp, name="factor_values")

        self.assertEqual(result["status"], "written")
        self.assertTrue(result["partitioned"])
        self.assertEqual(result["partition_columns"], ["trade_date"])
        self.assertEqual(result["row_count"], 2)
        self.assertGreaterEqual(result["file_count"], 1)
        self.assertEqual(metadata["status"], "ready")
        self.assertGreaterEqual(metadata["file_count"], 1)
        self.assertFalse(result["external_calls_triggered"])
        self.assertFalse(metadata["external_calls_triggered"])

    def test_parquet_store_rejects_missing_partition_columns(self):
        from storage import parquet_store

        if not parquet_store.dependency_status()["available"]:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        with tempfile.TemporaryDirectory() as tmp:
            result = parquet_store.write_partitioned_dataset(
                pd.DataFrame({"ts_code": ["002008.SZ"], "raw_value": [0.12]}),
                root=tmp,
                name="factor_values",
                partition_columns=["trade_date"],
            )
            metadata = parquet_store.partitioned_dataset_metadata(root=tmp, name="factor_values")

        self.assertEqual(result["status"], "partition_columns_missing")
        self.assertEqual(result["missing_partition_columns"], ["trade_date"])
        self.assertEqual(result["row_count"], 0)
        self.assertEqual(metadata["status"], "missing")
        self.assertFalse(result["external_calls_triggered"])

    def test_duckdb_store_handles_parallel_cache_reads(self):
        from storage import duckdb_store, parquet_store

        if not duckdb_store.dependency_status()["available"]:
            self.skipTest("duckdb dependency missing")
        if not parquet_store.dependency_status()["available"]:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        with tempfile.TemporaryDirectory() as tmp:
            out = parquet_store.write_factor_values(
                pd.DataFrame(
                    {
                        "factor_key": ["momentum_20d", "volatility_20d"],
                        "raw_value": [0.12, 0.04],
                    }
                ),
                root=tmp,
            )
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(lambda _: duckdb_store.query_factor_values(out["path"]), range(12)))

        self.assertTrue(results)
        for result in results:
            with self.subTest(status=result.get("status")):
                self.assertEqual(result["status"], "ready")
                self.assertEqual(result["row_count"], 2)
                self.assertFalse(result["external_calls_triggered"])

    def test_factor_values_metadata_is_cache_only(self):
        from storage import parquet_store

        with tempfile.TemporaryDirectory() as tmp:
            metadata = parquet_store.factor_values_metadata(root=tmp)

        self.assertEqual(metadata["status"], "missing")
        self.assertFalse(metadata["exists"])
        self.assertFalse(metadata["external_calls_triggered"])


if __name__ == "__main__":
    unittest.main()
