from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from storage import parquet_store
from server.services import storage_service


@unittest.skipUnless(parquet_store.dependency_status().get("available"), "Parquet dependencies unavailable")
class StoragePartitionExecutionTests(unittest.TestCase):
    def test_partition_execution_writes_readback_and_preserves_source(self):
        import pandas as pd

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            parquet_root = root / ".stock_ming_3" / "parquet"
            parquet_root.mkdir(parents=True)
            source = parquet_root / "daily.parquet"
            frame = pd.DataFrame(
                [
                    {"ts_code": "000001.SZ", "trade_date": "20260714", "close": 10.0},
                    {"ts_code": "000002.SZ", "trade_date": "20260715", "close": 11.0},
                ]
            )
            frame.to_parquet(source, index=False)
            rows = [
                {
                    "dataset": "daily",
                    "source_parquet_path": ".stock_ming_3/parquet/daily.parquet",
                    "schema_version": "storage.daily.v1",
                    "partition_columns": ["trade_date"],
                    "row_count_metadata": len(frame),
                }
            ]
            with patch.object(storage_service, "PROJECT_ROOT", root), patch.object(
                storage_service, "PARQUET_ROOT", parquet_root
            ):
                result = storage_service._execute_partition_migration(rows=rows, scope_hash="test-scope")

            self.assertEqual(result["status"], "partition_migration_execution_complete")
            self.assertEqual(result["partition_migration_executed_count"], 1)
            self.assertTrue(result["partition_migration_executed"])
            self.assertTrue((parquet_root / "daily").is_dir())
            self.assertTrue(source.is_file())
            self.assertEqual(result["rows"][0]["source_row_count"], 2)
            self.assertEqual(result["rows"][0]["target_row_count"], 2)
            self.assertTrue(result["rows"][0]["schema_columns_match"])
            self.assertTrue(result["rows"][0]["row_count_match"])
            self.assertEqual(result["rows"][0]["status"], "partition_migration_executed")

    def test_compaction_execution_rewrites_partition_and_reads_back(self):
        import pandas as pd

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            parquet_root = root / ".stock_ming_3" / "parquet"
            parquet_root.mkdir(parents=True)
            source = parquet_root / "daily.parquet"
            frame = pd.DataFrame(
                [
                    {"ts_code": "000001.SZ", "trade_date": "20260714", "close": 10.0},
                    {"ts_code": "000002.SZ", "trade_date": "20260715", "close": 11.0},
                ]
            )
            frame.to_parquet(source, index=False)
            parquet_store.write_partitioned_dataset(
                frame,
                root=parquet_root,
                name="daily",
                partition_columns=["trade_date"],
            )
            rows = [{"dataset": "daily"}]
            with patch.object(storage_service, "PROJECT_ROOT", root), patch.object(
                storage_service, "PARQUET_ROOT", parquet_root
            ):
                result = storage_service._execute_storage_compaction(rows=rows, scope_hash="compact-scope")

            self.assertEqual(result["status"], "physical_compaction_execution_complete")
            self.assertEqual(result["physical_compaction_executed_count"], 1)
            self.assertTrue(result["physical_compaction_executed"])
            self.assertTrue(source.is_file())
            self.assertEqual(result["rows"][0]["source_row_count"], 2)
            self.assertEqual(result["rows"][0]["target_row_count"], 2)
            self.assertTrue(result["rows"][0]["schema_columns_match"])
            self.assertTrue(result["rows"][0]["row_count_match"])
            self.assertEqual(result["rows"][0]["status"], "physical_compaction_executed")


if __name__ == "__main__":
    unittest.main()
