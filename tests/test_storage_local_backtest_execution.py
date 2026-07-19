import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from server.services import storage_service, task_service
from storage import duckdb_store, parquet_store
from storage.sqlite_meta import SQLiteMetaStore


class StorageLocalBacktestExecutionTests(unittest.TestCase):
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

    def _write_daily(self, *, row_count: int = 180) -> None:
        rows = []
        for index in range(row_count):
            close = 10.0 + index * 0.03 + ((index % 11) - 5) * 0.02
            rows.append(
                {
                    "ts_code": "000001.SZ",
                    "trade_date": f"2025{(index // 28) + 1:02d}{(index % 28) + 1:02d}",
                    "open": close - 0.05,
                    "high": close + 0.12,
                    "low": close - 0.12,
                    "close": close,
                    "vol": 100000 + index * 10,
                    "amount": (100000 + index * 10) * close,
                }
            )
        result = parquet_store.write_dataset(
            pd.DataFrame(rows),
            root=storage_service.PARQUET_ROOT,
            name="daily",
        )
        self.assertEqual(result["status"], "written")

    def test_confirmed_scope_bound_local_backtest_writes_real_rows_atomically(self):
        self._write_daily()
        recipe = storage_service.storage_backtest_results_local_execution_recipe("000001.SZ")
        self.assertTrue(recipe["local_execution_ready"])
        self.assertFalse(recipe["reads_row_payloads"])
        self.assertFalse(recipe["external_calls_triggered"])

        blocked = storage_service.run_storage_backtest_results_local_execution_task(
            {
                "source": "focused_test",
                "approved_by_user": True,
                "confirm_local_backtest": True,
                "scope_hash": "0" * 64,
                "ts_code": "000001.SZ",
            }
        )
        self.assertEqual(blocked["status"], "failed")
        self.assertFalse(
            parquet_store.dataset_path(
                root=storage_service.PARQUET_ROOT,
                name="backtest_results",
            ).exists()
        )

        task = storage_service.run_storage_backtest_results_local_execution_task(
            {
                "source": "focused_test_current_scope",
                "approved_by_user": True,
                "confirm_local_backtest": True,
                "scope_hash": recipe["scope_hash"],
                "ts_code": "000001.SZ",
            }
        )
        self.assertEqual(task["status"], "success", task)
        packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.BACKTEST_RESULTS_LOCAL_EXECUTION_PACKET_KEY
        )
        self.assertEqual(packet["status"], "storage_backtest_results_local_execution_success")
        self.assertTrue(packet["local_backtest_executed"])
        self.assertTrue(packet["simulation_only"])
        self.assertEqual(packet["input_row_count"], 180)
        self.assertEqual(packet["normalized_input_row_count"], 180)
        self.assertEqual(packet["result_row_count"], 4)
        self.assertTrue(packet["atomic_parquet_promotion"])
        self.assertTrue(packet["artifact_binding"]["ready"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertFalse(packet["production_storage_complete"])

        readback = duckdb_store.query_parquet_dataset(
            parquet_store.dataset_path(
                root=storage_service.PARQUET_ROOT,
                name="backtest_results",
            ),
            limit=10,
        )
        self.assertEqual(readback["status"], "ready")
        self.assertEqual(readback["row_count"], 4)
        self.assertEqual(
            {row["strategy_key"] for row in readback["rows"]},
            {
                "backtester:default",
                "backtester:free",
                "backtester:dynamic",
                "backtester:tech_growth",
            },
        )
        self.assertTrue(all(row["status"] == "completed_local_research" for row in readback["rows"]))

        before_seed = parquet_store.dataset_path(
            root=storage_service.PARQUET_ROOT,
            name="backtest_results",
        ).read_bytes()
        seed = storage_service.run_storage_backtest_results_schema_seed_task(
            {"source": "focused_preserve_real_results", "confirm_schema_seed": True}
        )
        self.assertEqual(seed["status"], "success")
        seed_packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.BACKTEST_RESULTS_SCHEMA_SEED_PACKET_KEY
        )
        self.assertTrue(seed_packet["existing_schema_preserved"])
        self.assertFalse(seed_packet["schema_seed_write_executed"])
        self.assertEqual(
            parquet_store.dataset_path(
                root=storage_service.PARQUET_ROOT,
                name="backtest_results",
            ).read_bytes(),
            before_seed,
        )

    def test_atomic_writer_preserves_existing_dataset_when_temp_validation_fails(self):
        path = parquet_store.dataset_path(root=storage_service.PARQUET_ROOT, name="backtest_results")
        original = pd.DataFrame(
            [
                {
                    "strategy_key": "backtester:default",
                    "universe": "000001.SZ",
                    "run_date": "20260719",
                    "status": "completed_local_research",
                    "metrics": "{}",
                }
            ]
        )
        parquet_store.write_dataset(original, root=storage_service.PARQUET_ROOT, name="backtest_results")
        original_bytes = path.read_bytes()
        failed = parquet_store.write_dataset_atomic(
            pd.DataFrame([{"strategy_key": "missing-columns"}]),
            root=storage_service.PARQUET_ROOT,
            name="backtest_results",
            required_columns=storage_service.DATASET_SCHEMA_CONTRACTS["backtest_results"]["required_columns"],
        )
        self.assertEqual(failed["status"], "atomic_write_validation_failed")
        self.assertFalse(failed["atomic_promoted"])
        self.assertEqual(path.read_bytes(), original_bytes)

        replacement = original.copy()
        replacement.loc[0, "metrics"] = '{"replacement":true}'
        real_fsync = parquet_store.os.fsync
        fsync_calls = 0

        def fail_directory_sync_once(fd):
            nonlocal fsync_calls
            fsync_calls += 1
            if fsync_calls == 3:
                raise OSError("injected_directory_fsync_failure")
            return real_fsync(fd)

        with patch.object(parquet_store.os, "fsync", side_effect=fail_directory_sync_once):
            failed_after_replace = parquet_store.write_dataset_atomic(
                replacement,
                root=storage_service.PARQUET_ROOT,
                name="backtest_results",
                required_columns=storage_service.DATASET_SCHEMA_CONTRACTS["backtest_results"]["required_columns"],
            )
        self.assertEqual(failed_after_replace["status"], "atomic_write_failed_safe")
        self.assertTrue(failed_after_replace["rollback_performed"])
        self.assertTrue(failed_after_replace["rollback_verified"])
        self.assertFalse(failed_after_replace["rollback_backup_preserved"])
        self.assertEqual(path.read_bytes(), original_bytes)

    def test_invalid_price_rows_cannot_self_seal_completed_backtest_results(self):
        invalid_rows = [
            {
                "ts_code": "000001.SZ",
                "trade_date": "not-a-date",
                "open": 10.0,
                "high": 10.2,
                "low": 9.8,
                "close": 10.1,
                "vol": 100000,
                "amount": 1010000,
            }
            for _ in range(180)
        ]
        parquet_store.write_dataset(
            pd.DataFrame(invalid_rows),
            root=storage_service.PARQUET_ROOT,
            name="daily",
        )
        recipe = storage_service.storage_backtest_results_local_execution_recipe("000001.SZ")
        task = storage_service.run_storage_backtest_results_local_execution_task(
            {
                "source": "focused_invalid_rows_attack",
                "approved_by_user": True,
                "confirm_local_backtest": True,
                "scope_hash": recipe["scope_hash"],
                "ts_code": "000001.SZ",
            }
        )
        self.assertEqual(task["status"], "failed")
        packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.BACKTEST_RESULTS_LOCAL_EXECUTION_PACKET_KEY
        )
        self.assertFalse(packet["local_backtest_executed"])
        self.assertEqual(packet["normalized_input_row_count"], 0)
        self.assertEqual(packet["result_row_count"], 0)
        self.assertFalse(packet["writes_parquet"])
        self.assertFalse(
            parquet_store.dataset_path(
                root=storage_service.PARQUET_ROOT,
                name="backtest_results",
            ).exists()
        )

    def test_identical_duplicate_dates_are_deduped_but_conflicts_fail_closed(self):
        self._write_daily(row_count=140)
        daily_path = parquet_store.dataset_path(
            root=storage_service.PARQUET_ROOT,
            name="daily",
        )
        source = pd.read_parquet(daily_path)
        repeated = pd.concat([source, source.iloc[:20]], ignore_index=True)
        parquet_store.write_dataset(
            repeated,
            root=storage_service.PARQUET_ROOT,
            name="daily",
        )
        recipe = storage_service.storage_backtest_results_local_execution_recipe("000001.SZ")
        succeeded = storage_service.run_storage_backtest_results_local_execution_task(
            {
                "source": "focused_identical_duplicate_rows",
                "approved_by_user": True,
                "confirm_local_backtest": True,
                "scope_hash": recipe["scope_hash"],
                "ts_code": "000001.SZ",
            }
        )
        self.assertEqual(succeeded["status"], "success", succeeded)
        packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.BACKTEST_RESULTS_LOCAL_EXECUTION_PACKET_KEY
        )
        self.assertEqual(packet["pre_dedupe_normalized_input_row_count"], 160)
        self.assertEqual(packet["normalized_input_row_count"], 140)
        self.assertEqual(packet["duplicate_input_row_count"], 20)

        conflict = repeated.copy()
        conflict.loc[len(source), "close"] = float(conflict.loc[len(source), "close"]) + 0.01
        parquet_store.write_dataset(
            conflict,
            root=storage_service.PARQUET_ROOT,
            name="daily",
        )
        conflict_recipe = storage_service.storage_backtest_results_local_execution_recipe(
            "000001.SZ"
        )
        failed = storage_service.run_storage_backtest_results_local_execution_task(
            {
                "source": "focused_conflicting_duplicate_rows",
                "approved_by_user": True,
                "confirm_local_backtest": True,
                "scope_hash": conflict_recipe["scope_hash"],
                "ts_code": "000001.SZ",
            }
        )
        self.assertEqual(failed["status"], "failed")
        failure_packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.BACKTEST_RESULTS_LOCAL_EXECUTION_PACKET_KEY
        )
        self.assertFalse(failure_packet["local_backtest_executed"])
        self.assertEqual(failure_packet["error_message_safe"], "conflicting_duplicate_local_daily_rows")

        nan_conflict = repeated.copy()
        nan_conflict.loc[len(source), "close"] = float("nan")
        parquet_store.write_dataset(
            nan_conflict,
            root=storage_service.PARQUET_ROOT,
            name="daily",
        )
        nan_recipe = storage_service.storage_backtest_results_local_execution_recipe("000001.SZ")
        nan_failed = storage_service.run_storage_backtest_results_local_execution_task(
            {
                "source": "focused_nan_duplicate_attack",
                "approved_by_user": True,
                "confirm_local_backtest": True,
                "scope_hash": nan_recipe["scope_hash"],
                "ts_code": "000001.SZ",
            }
        )
        self.assertEqual(nan_failed["status"], "failed")
        nan_packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.BACKTEST_RESULTS_LOCAL_EXECUTION_PACKET_KEY
        )
        self.assertFalse(nan_packet["local_backtest_executed"])
        self.assertEqual(
            nan_packet["error_message_safe"],
            "raw_local_daily_rows_invalid_or_unparseable",
        )

    def test_symbol_scope_must_be_physically_enforced_and_mixed_rows_are_filtered(self):
        self._write_daily(row_count=140)
        daily_path = parquet_store.dataset_path(
            root=storage_service.PARQUET_ROOT,
            name="daily",
        )
        source = pd.read_parquet(daily_path)
        missing_symbol = source.drop(columns=["ts_code"])
        parquet_store.write_dataset(
            missing_symbol,
            root=storage_service.PARQUET_ROOT,
            name="daily",
        )
        missing_recipe = storage_service.storage_backtest_results_local_execution_recipe(
            "000001.SZ"
        )
        missing = storage_service.run_storage_backtest_results_local_execution_task(
            {
                "source": "focused_missing_symbol_scope",
                "approved_by_user": True,
                "confirm_local_backtest": True,
                "scope_hash": missing_recipe["scope_hash"],
                "ts_code": "000001.SZ",
            }
        )
        self.assertEqual(missing["status"], "failed")
        missing_packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.BACKTEST_RESULTS_LOCAL_EXECUTION_PACKET_KEY
        )
        self.assertEqual(
            missing_packet["error_message_safe"],
            "local_daily_symbol_scope_or_projection_not_enforced",
        )

        mixed = pd.concat(
            [
                source,
                source.assign(ts_code="000002.SZ"),
            ],
            ignore_index=True,
        )
        parquet_store.write_dataset(
            mixed,
            root=storage_service.PARQUET_ROOT,
            name="daily",
        )
        mixed_recipe = storage_service.storage_backtest_results_local_execution_recipe("000001.SZ")
        selected = storage_service.run_storage_backtest_results_local_execution_task(
            {
                "source": "focused_mixed_symbol_scope",
                "approved_by_user": True,
                "confirm_local_backtest": True,
                "scope_hash": mixed_recipe["scope_hash"],
                "ts_code": "000001.SZ",
            }
        )
        self.assertEqual(selected["status"], "success", selected)
        selected_packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.BACKTEST_RESULTS_LOCAL_EXECUTION_PACKET_KEY
        )
        self.assertEqual(selected_packet["input_row_count"], 140)
        self.assertEqual(selected_packet["normalized_input_row_count"], 140)
        self.assertEqual(selected_packet["ts_code"], "000001.SZ")

    def test_non_numeric_activity_rows_and_packet_failure_cannot_publish_orphan_results(self):
        rows = []
        for index in range(180):
            rows.append(
                {
                    "ts_code": "000001.SZ",
                    "trade_date": f"2025{(index // 28) + 1:02d}{(index % 28) + 1:02d}",
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.8,
                    "close": 10.1,
                    "vol": "not-a-number",
                    "amount": "not-a-number",
                }
            )
        parquet_store.write_dataset(
            pd.DataFrame(rows),
            root=storage_service.PARQUET_ROOT,
            name="daily",
        )
        invalid_recipe = storage_service.storage_backtest_results_local_execution_recipe("000001.SZ")
        invalid = storage_service.run_storage_backtest_results_local_execution_task(
            {
                "source": "focused_invalid_activity_attack",
                "approved_by_user": True,
                "confirm_local_backtest": True,
                "scope_hash": invalid_recipe["scope_hash"],
                "ts_code": "000001.SZ",
            }
        )
        self.assertEqual(invalid["status"], "failed")
        self.assertFalse(
            parquet_store.dataset_path(
                root=storage_service.PARQUET_ROOT,
                name="backtest_results",
            ).exists()
        )
        prior_packet = SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
            storage_service.BACKTEST_RESULTS_LOCAL_EXECUTION_PACKET_KEY
        )

        self._write_daily()
        recipe = storage_service.storage_backtest_results_local_execution_recipe("000001.SZ")
        original_write_packet = SQLiteMetaStore.write_packet

        def fail_backtest_packet(store, packet_key, payload):
            if packet_key == storage_service.BACKTEST_RESULTS_LOCAL_EXECUTION_PACKET_KEY:
                raise OSError("injected_packet_persist_failure")
            return original_write_packet(store, packet_key, payload)

        with patch.object(SQLiteMetaStore, "write_packet", new=fail_backtest_packet):
            failed = storage_service.run_storage_backtest_results_local_execution_task(
                {
                    "source": "focused_packet_failure",
                    "approved_by_user": True,
                    "confirm_local_backtest": True,
                    "scope_hash": recipe["scope_hash"],
                    "ts_code": "000001.SZ",
                }
            )
        self.assertEqual(failed["status"], "failed")
        self.assertFalse(
            parquet_store.dataset_path(
                root=storage_service.PARQUET_ROOT,
                name="backtest_results",
            ).exists()
        )
        self.assertEqual(
            SQLiteMetaStore(storage_service.SQLITE_META_PATH).read_packet(
                storage_service.BACKTEST_RESULTS_LOCAL_EXECUTION_PACKET_KEY
            ),
            prior_packet,
        )

    def test_first_publish_packet_failure_and_unlink_failure_is_indeterminate(self):
        self._write_daily()
        recipe = storage_service.storage_backtest_results_local_execution_recipe("000001.SZ")
        dataset_path = parquet_store.dataset_path(
            root=storage_service.PARQUET_ROOT,
            name="backtest_results",
        )
        real_unlink = Path.unlink

        def fail_canonical_unlink(path, *args, **kwargs):
            if path == dataset_path:
                raise OSError("injected_canonical_unlink_failure")
            return real_unlink(path, *args, **kwargs)

        original_write_packet = SQLiteMetaStore.write_packet

        def fail_selected_packet(store, packet_key, payload):
            if packet_key == storage_service.BACKTEST_RESULTS_LOCAL_EXECUTION_PACKET_KEY:
                raise OSError("injected_packet_persist_failure")
            return original_write_packet(store, packet_key, payload)

        with (
            patch.object(SQLiteMetaStore, "write_packet", new=fail_selected_packet),
            patch.object(Path, "unlink", new=fail_canonical_unlink),
        ):
            failed = storage_service.run_storage_backtest_results_local_execution_task(
                {
                    "source": "focused_double_failure",
                    "approved_by_user": True,
                    "confirm_local_backtest": True,
                    "scope_hash": recipe["scope_hash"],
                    "ts_code": "000001.SZ",
                }
            )
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(
            failed["current_step"],
            "storage_backtest_results_local_execution_transaction_rollback_unverified",
        )
        self.assertTrue(
            any("rollback_unverified" in warning for warning in failed.get("warnings", [])),
            failed,
        )
        self.assertTrue(dataset_path.exists())


if __name__ == "__main__":
    unittest.main()
