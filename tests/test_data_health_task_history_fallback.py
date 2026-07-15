from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from server.services import data_health_service, packet_service, storage_service, task_service, tushare_task_service
from storage.sqlite_meta import SQLiteMetaStore


class DataHealthTaskHistoryFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.db_path = root / "meta.sqlite"
        self.snapshot_path = root / "command_center_latest.json"
        self.snapshot_path.write_text(
            json.dumps({"data_health_timeline": [{"event": "history fallback test"}]}),
            encoding="utf-8",
        )
        self.original_task_path = task_service.SQLITE_META_PATH
        self.original_packet_path = packet_service.SQLITE_META_PATH
        self.original_snapshot_path = packet_service.SNAPSHOT_CACHE_PATH
        self.original_parquet_root = storage_service.PARQUET_ROOT
        task_service.SQLITE_META_PATH = self.db_path
        packet_service.SQLITE_META_PATH = self.db_path
        packet_service.SNAPSHOT_CACHE_PATH = self.snapshot_path
        storage_service.PARQUET_ROOT = root / "parquet"
        task_service._TASKS.clear()
        self.store = SQLiteMetaStore(self.db_path)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        task_service._TASKS.clear()
        task_service.SQLITE_META_PATH = self.original_task_path
        packet_service.SQLITE_META_PATH = self.original_packet_path
        packet_service.SNAPSHOT_CACHE_PATH = self.original_snapshot_path
        storage_service.PARQUET_ROOT = self.original_parquet_root
        self.temp_dir.cleanup()

    @staticmethod
    def _promotion_task(task_id: str, marker: str) -> dict:
        return {
            "task_id": task_id,
            "task_type": data_health_service.TRADE_CAL_PROVIDER_ACCEPTANCE_PROMOTION_REVIEW_TASK_TYPE,
            "status": "success",
            "current_step": marker,
            "created_at": f"2026-07-15T00:00:0{marker[-1]}",
            "finished_at": f"2026-07-15T00:00:0{marker[-1]}",
            "payload_safe": {
                "trade_cal_provider_acceptance_promotion_review_receipt": {
                    "schema_version": (
                        data_health_service.TRADE_CAL_PROVIDER_ACCEPTANCE_PROMOTION_REVIEW_SCHEMA_VERSION
                    ),
                    "status": marker,
                    "blocking_row_count": 0,
                    "allowed_next_step": "explicit_release_review",
                    "promotion_ready_from_audit": True,
                    "promotion_review_ready_for_release": True,
                    "ready_for_production_freshness_release_review": True,
                    "provider_evidence_from_prior_task": True,
                    "production_freshness_gate_complete": True,
                },
                "trade_cal_provider_acceptance_promotion_review_rows": [
                    {"phase": marker, "status": "passed", "passed": True, "production_complete": True}
                ],
            },
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
        }

    def test_live_task_status_takes_priority_over_history(self) -> None:
        self.store.write_task_status(self._promotion_task("history-task", "history-1"))
        self.store.clear_task_statuses(preserve_history=True)
        self.store.write_task_status(self._promotion_task("live-task", "live-2"))

        task = task_service.read_latest_task_status_by_type(
            data_health_service.TRADE_CAL_PROVIDER_ACCEPTANCE_PROMOTION_REVIEW_TASK_TYPE,
            include_history_fallback=True,
            expected_history_receipt_key="trade_cal_provider_acceptance_promotion_review_receipt",
            expected_history_receipt_schema_version=(
                data_health_service.TRADE_CAL_PROVIDER_ACCEPTANCE_PROMOTION_REVIEW_SCHEMA_VERSION
            ),
        )

        self.assertIsNotNone(task)
        self.assertEqual(task["task_id"], "live-task")
        self.assertEqual(task["storage_source"], "sqlite_meta")

    def test_latest_history_row_is_visible_without_rebuilding_live_status(self) -> None:
        self.store.write_task_status(self._promotion_task("history-task", "history-1"))
        self.store.write_task_status(self._promotion_task("history-task", "history-2"))
        self.store.clear_task_statuses(preserve_history=True)

        latest, rows = data_health_service._latest_trade_cal_provider_acceptance_promotion_review_from_tasks()

        self.assertTrue(latest["latest_task_found"])
        self.assertEqual(latest["latest_task_id"], "history-task")
        self.assertEqual(latest["promotion_review_status"], "history-2")
        self.assertEqual(latest["status"], "historical_task_evidence_visible_non_actionable")
        self.assertEqual(latest["storage_source"], "sqlite_task_status_history")
        self.assertTrue(latest["historical_evidence"])
        self.assertTrue(latest["history_integrity_valid"])
        self.assertFalse(latest["current_actionable"])
        self.assertFalse(latest["receipt_visible"])
        self.assertTrue(latest["historical_receipt_visible"])
        self.assertTrue(latest["historical_receipt"]["promotion_review_ready_for_release"])
        self.assertFalse(latest["promotion_ready_from_audit"])
        self.assertFalse(latest["promotion_review_ready_for_release"])
        self.assertFalse(latest["ready_for_production_freshness_release_review"])
        self.assertFalse(latest["provider_evidence_from_prior_task"])
        self.assertFalse(latest["production_freshness_gate_complete"])
        self.assertNotIn("receipt", latest)
        self.assertEqual(latest["latest_task"]["storage_source"], "sqlite_task_status_history")
        self.assertEqual(rows[0]["phase"], "history-2")
        self.assertTrue(rows[0]["historical_evidence"])
        self.assertFalse(rows[0]["current_actionable"])
        self.assertFalse(rows[0]["passed"])
        self.assertFalse(rows[0]["production_complete"])
        self.assertEqual(self.store.list_task_metadata(), [])
        self.assertEqual(self.store.task_status_history_count("history-task"), 2)

    def test_corrupt_newest_target_fails_closed_without_older_success_fallback(self) -> None:
        self.store.write_task_status(self._promotion_task("older-good", "history-1"))
        self.store.write_task_status(self._promotion_task("newest-corrupt", "history-2"))
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT history_id, payload_json FROM task_status_history WHERE task_id = ? ORDER BY history_id DESC LIMIT 1",
                ("newest-corrupt",),
            ).fetchone()
            conn.execute(
                "UPDATE task_status_history SET payload_json = ? WHERE history_id = ?",
                (str(row[1]) + " ", int(row[0])),
            )
        self.store.clear_task_statuses(preserve_history=True)

        latest, rows = data_health_service._latest_trade_cal_provider_acceptance_promotion_review_from_tasks()

        self.assertEqual(latest["latest_task_id"], "newest-corrupt")
        self.assertEqual(latest["status"], "historical_task_evidence_rejected_integrity_failure")
        self.assertEqual(latest["history_integrity_error"], "payload_digest_mismatch")
        self.assertFalse(latest["history_integrity_valid"])
        self.assertFalse(latest["current_actionable"])
        self.assertFalse(latest["receipt_visible"])
        self.assertFalse(latest["historical_receipt_visible"])
        self.assertEqual(latest["historical_receipt"], {})
        self.assertFalse(latest["promotion_review_ready_for_release"])
        self.assertFalse(latest["production_freshness_gate_complete"])
        self.assertEqual(rows, [])

    def test_history_task_id_task_type_and_receipt_bindings_fail_closed(self) -> None:
        corruptions = {
            "task-id": "sql_task_id_payload_task_id_mismatch",
            "task-type": "stored_task_type_payload_task_type_mismatch",
            "receipt-schema": "expected_receipt_schema_version_mismatch",
        }
        for corruption, expected_error in corruptions.items():
            with self.subTest(corruption=corruption):
                self.store.clear_task_statuses(preserve_history=False)
                task = self._promotion_task(f"binding-{corruption}", "history-1")
                if corruption == "receipt-schema":
                    task["payload_safe"]["trade_cal_provider_acceptance_promotion_review_receipt"][
                        "schema_version"
                    ] = "wrong_receipt.v1"
                self.store.write_task_status(task)
                if corruption in {"task-id", "task-type"}:
                    with sqlite3.connect(self.db_path) as conn:
                        row = conn.execute(
                            "SELECT history_id, payload_json FROM task_status_history ORDER BY history_id DESC LIMIT 1"
                        ).fetchone()
                        payload = json.loads(str(row[1]))
                        if corruption == "task-id":
                            payload["task_id"] = "payload-other-task"
                        else:
                            payload["task_type"] = "other_task_type"
                        payload_json = json.dumps(payload, ensure_ascii=False, default=str)
                        payload_digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
                        conn.execute(
                            "UPDATE task_status_history SET payload_json = ?, payload_digest = ? WHERE history_id = ?",
                            (payload_json, payload_digest, int(row[0])),
                        )
                self.store.clear_task_statuses(preserve_history=True)

                latest, rows = (
                    data_health_service._latest_trade_cal_provider_acceptance_promotion_review_from_tasks()
                )

                self.assertEqual(latest["status"], "historical_task_evidence_rejected_integrity_failure")
                self.assertEqual(latest["history_integrity_error"], expected_error)
                self.assertFalse(latest["history_integrity_valid"])
                self.assertFalse(latest["current_actionable"])
                self.assertFalse(latest["production_freshness_gate_complete"])
                self.assertEqual(rows, [])

    def test_stored_task_type_tamper_cannot_hide_newest_target_or_fall_back(self) -> None:
        self.store.write_task_status(self._promotion_task("older-good", "history-1"))
        self.store.write_task_status(self._promotion_task("newest-stored-type-tamper", "history-2"))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE task_status_history SET task_type = ? WHERE task_id = ?",
                ("other_task_type", "newest-stored-type-tamper"),
            )
        self.store.clear_task_statuses(preserve_history=True)

        latest, rows = data_health_service._latest_trade_cal_provider_acceptance_promotion_review_from_tasks()

        self.assertEqual(latest["latest_task_id"], "newest-stored-type-tamper")
        self.assertEqual(latest["status"], "historical_task_evidence_rejected_integrity_failure")
        self.assertEqual(
            latest["history_integrity_error"],
            "stored_task_type_payload_task_type_mismatch",
        )
        self.assertFalse(latest["history_integrity_valid"])
        self.assertFalse(latest["current_actionable"])
        self.assertFalse(latest["production_freshness_gate_complete"])
        self.assertEqual(rows, [])

    def test_history_type_lookup_uses_one_indexed_query(self) -> None:
        self.store.write_task_status(self._promotion_task("history-task", "history-1"))
        self.store.clear_task_statuses(preserve_history=True)
        query_count = 0
        real_connection = sqlite3.connect(self.db_path)

        class CountingConnection:
            def execute(self, *args, **kwargs):
                nonlocal query_count
                query_count += 1
                return real_connection.execute(*args, **kwargs)

            def close(self):
                real_connection.close()

        with patch.object(self.store, "_connect", return_value=CountingConnection()):
            task = self.store.read_latest_task_status_history_by_type(
                data_health_service.TRADE_CAL_PROVIDER_ACCEPTANCE_PROMOTION_REVIEW_TASK_TYPE,
                expected_receipt_key="trade_cal_provider_acceptance_promotion_review_receipt",
                expected_receipt_schema_version=(
                    data_health_service.TRADE_CAL_PROVIDER_ACCEPTANCE_PROMOTION_REVIEW_SCHEMA_VERSION
                ),
            )

        self.assertEqual(query_count, 2)
        self.assertEqual(task["history_schema_probe_query_count"], 1)
        self.assertEqual(task["history_lookup_query_count"], 1)
        plan = self.store.explain_latest_task_status_history_by_type_query(
            data_health_service.TRADE_CAL_PROVIDER_ACCEPTANCE_PROMOTION_REVIEW_TASK_TYPE
        )
        self.assertTrue(any("idx_task_status_history_type_latest" in row for row in plan), plan)
        self.assertTrue(any("idx_task_status_history_payload_type_latest" in row for row in plan), plan)
        self.assertTrue(any("idx_task_status_history_task_latest" in row for row in plan), plan)

    def test_existing_history_schema_is_migrated_and_backfilled_by_type(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy-meta.sqlite"
        task = self._promotion_task("legacy-history", "history-1")
        payload_json = json.dumps(task, ensure_ascii=False, default=str)
        payload_digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        with sqlite3.connect(legacy_path) as conn:
            conn.execute(
                """
                CREATE TABLE task_status_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_digest TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO task_status_history(task_id, payload_json, updated_at, payload_digest) VALUES (?, ?, ?, ?)",
                ("legacy-history", payload_json, "2026-07-15T00:00:01", payload_digest),
            )

        legacy_store = SQLiteMetaStore(legacy_path)
        projection = legacy_store.read_latest_task_status_history_by_type(
            data_health_service.TRADE_CAL_PROVIDER_ACCEPTANCE_PROMOTION_REVIEW_TASK_TYPE,
            expected_receipt_key="trade_cal_provider_acceptance_promotion_review_receipt",
            expected_receipt_schema_version=(
                data_health_service.TRADE_CAL_PROVIDER_ACCEPTANCE_PROMOTION_REVIEW_SCHEMA_VERSION
            ),
        )

        self.assertEqual(projection["task_id"], "legacy-history")
        self.assertTrue(projection["history_integrity_valid"])
        with sqlite3.connect(legacy_path) as conn:
            task_type = conn.execute(
                "SELECT task_type FROM task_status_history WHERE task_id = ?",
                ("legacy-history",),
            ).fetchone()[0]
            indexes = {
                row[1] for row in conn.execute("PRAGMA index_list(task_status_history)").fetchall()
            }
        self.assertEqual(
            task_type,
            data_health_service.TRADE_CAL_PROVIDER_ACCEPTANCE_PROMOTION_REVIEW_TASK_TYPE,
        )
        self.assertIn("idx_task_status_history_task_latest", indexes)
        self.assertIn("idx_task_status_history_type_latest", indexes)

    def test_legacy_get_history_read_keeps_schema_and_indexes_unchanged(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy-readonly-meta.sqlite"
        task = self._promotion_task("legacy-readonly-history", "history-1")
        payload_json = json.dumps(task, ensure_ascii=False, default=str)
        payload_digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        with sqlite3.connect(legacy_path) as conn:
            conn.execute(
                """
                CREATE TABLE task_status_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_digest TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO task_status_history(task_id, payload_json, updated_at, payload_digest) VALUES (?, ?, ?, ?)",
                ("legacy-readonly-history", payload_json, "2026-07-15T00:00:01", payload_digest),
            )
            schema_before = conn.execute(
                "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
            ).fetchall()
            columns_before = conn.execute("PRAGMA table_info(task_status_history)").fetchall()
            indexes_before = conn.execute("PRAGMA index_list(task_status_history)").fetchall()

        with (
            patch.object(task_service, "SQLITE_META_PATH", legacy_path),
            patch.object(packet_service, "SQLITE_META_PATH", legacy_path),
        ):
            response = self.client.get("/api/data-health/cache")

        self.assertEqual(response.status_code, 200)
        latest = response.json()["data"]["latest_trade_cal_provider_acceptance_promotion_review"]
        self.assertEqual(latest["latest_task_id"], "legacy-readonly-history")
        self.assertEqual(latest["storage_source"], "sqlite_task_status_history")
        self.assertEqual(
            latest["latest_task"]["storage_source"],
            "sqlite_task_status_history",
        )
        self.assertEqual(latest["history_integrity_error"], "")
        self.assertFalse(latest["current_actionable"])
        with sqlite3.connect(legacy_path) as conn:
            schema_after = conn.execute(
                "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
            ).fetchall()
            columns_after = conn.execute("PRAGMA table_info(task_status_history)").fetchall()
            indexes_after = conn.execute("PRAGMA index_list(task_status_history)").fetchall()
        self.assertEqual(schema_after, schema_before)
        self.assertEqual(columns_after, columns_before)
        self.assertEqual(indexes_after, indexes_before)

    def test_missing_live_and_history_remains_honestly_missing(self) -> None:
        latest, rows = data_health_service._latest_trade_cal_provider_acceptance_promotion_review_from_tasks()

        self.assertFalse(latest["latest_task_found"])
        self.assertEqual(latest["status"], "no_trade_cal_provider_acceptance_promotion_review_task_found")
        self.assertIsNone(latest["latest_task_id"])
        self.assertEqual(rows, [])

    def test_get_history_fallback_is_read_only_post_zero_and_no_external_call(self) -> None:
        self.store.write_task_status(self._promotion_task("history-task", "history-1"))
        self.store.clear_task_statuses(preserve_history=True)
        live_before = self.store.list_task_metadata()
        history_before = self.store.task_status_history_count()

        with (
            patch.object(task_service, "_persist_task", side_effect=AssertionError("GET created a task")),
            patch.object(
                tushare_task_service,
                "run_tushare_refresh_task",
                side_effect=AssertionError("GET called provider task"),
            ),
            patch.object(
                tushare_task_service,
                "run_tushare_full_interface_provider_production_acceptance",
                side_effect=AssertionError("GET called production provider task"),
            ),
        ):
            response = self.client.get("/api/data-health/cache")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        latest = payload["data"]["latest_trade_cal_provider_acceptance_promotion_review"]
        self.assertEqual(latest["latest_task_id"], "history-task")
        self.assertEqual(latest["storage_source"], "sqlite_task_status_history")
        self.assertFalse(latest["current_actionable"])
        self.assertFalse(latest["promotion_review_ready_for_release"])
        self.assertFalse(latest["ready_for_production_freshness_release_review"])
        self.assertFalse(latest["receipt_visible"])
        self.assertTrue(latest["historical_receipt_visible"])
        self.assertEqual(latest["latest_task"]["storage_source"], "sqlite_task_status_history")
        durable = payload["data"]["freshness_durable_evidence_recipe"]
        self.assertFalse(durable["local_promotion_review_visible"])
        self.assertFalse(durable["local_promotion_review_ready_for_release"])
        self.assertEqual(self.store.list_task_metadata(), live_before)
        self.assertEqual(self.store.task_status_history_count(), history_before)
        self.assertFalse(payload["data"]["external_calls_triggered"])
        self.assertFalse(payload["data"]["tushare_called"])
        self.assertFalse(payload["data"]["deepseek_called"])
        self.assertFalse(payload["data"]["github_called"])


if __name__ == "__main__":
    unittest.main()
