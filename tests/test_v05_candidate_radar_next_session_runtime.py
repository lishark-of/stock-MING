from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from server.services import candidate_service, next_session_service, packet_service, task_service, worker_service
from server.services.task_service import clear_task_statuses_for_tests
from storage.sqlite_meta import SQLiteMetaStore


class CandidateRadarV05RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.meta_path = self.root / ".stock_ming_3" / "meta.sqlite"
        self.snapshot_path = self.root / ".stock_ming_cache" / "command_center_latest.json"
        self.runtime_root = self.root / ".stock_ming_3" / "v04_acceptance"
        self.originals = {
            "candidate_meta": candidate_service.SQLITE_META_PATH,
            "next_meta": next_session_service.SQLITE_META_PATH,
            "packet_meta": packet_service.SQLITE_META_PATH,
            "packet_snapshot": packet_service.SNAPSHOT_CACHE_PATH,
            "task_meta": task_service.SQLITE_META_PATH,
            "worker_meta": worker_service.SQLITE_META_PATH,
            "worker_runtime_root": worker_service.WORKER_V04_RUNTIME_ROOT,
        }
        candidate_service.SQLITE_META_PATH = self.meta_path
        next_session_service.SQLITE_META_PATH = self.meta_path
        packet_service.SQLITE_META_PATH = self.meta_path
        packet_service.SNAPSHOT_CACHE_PATH = self.snapshot_path
        task_service.SQLITE_META_PATH = self.meta_path
        worker_service.SQLITE_META_PATH = self.meta_path
        worker_service.WORKER_V04_RUNTIME_ROOT = self.runtime_root
        clear_task_statuses_for_tests(clear_persisted=False)

    def tearDown(self) -> None:
        clear_task_statuses_for_tests(clear_persisted=False)
        candidate_service.SQLITE_META_PATH = self.originals["candidate_meta"]
        next_session_service.SQLITE_META_PATH = self.originals["next_meta"]
        packet_service.SQLITE_META_PATH = self.originals["packet_meta"]
        packet_service.SNAPSHOT_CACHE_PATH = self.originals["packet_snapshot"]
        task_service.SQLITE_META_PATH = self.originals["task_meta"]
        worker_service.SQLITE_META_PATH = self.originals["worker_meta"]
        worker_service.WORKER_V04_RUNTIME_ROOT = self.originals["worker_runtime_root"]
        clear_task_statuses_for_tests(clear_persisted=False)
        self.tmp.cleanup()

    def _pool(self) -> list[dict[str, object]]:
        return [
            {
                "ticker": f"0000{index:02d}.SZ",
                "name": f"Candidate {index}",
                "score": 20 - index,
                "source": "focused_test_supplied_pool",
                "data_gaps": ["provider_pending"] if index % 4 == 0 else [],
            }
            for index in range(1, 13)
        ]

    def _payload(self, *, fail_on_symbol: str = "") -> dict[str, object]:
        pool = self._pool()
        scan_snapshot, _, _ = candidate_service._snapshot_with_local_candidate_pool(
            {},
            {"full_pool_candidates": pool, "data_date": "2026-07-13"},
            "full_pool_local_scan",
        )
        scope_hash = candidate_service._candidate_v05_scope_hash(
            scan_snapshot["next_ticket_candidates"],
            {"data_date": "2026-07-13"},
        )
        payload: dict[str, object] = {
            "runtime_mode": "v05_candidate_local_batch",
            "operator_approved": True,
            "candidate_scope_hash": scope_hash,
            "scope_hash": scope_hash,
            "confirm_scope_hash": scope_hash,
            "chunk_size": 4,
            "data_date": "2026-07-13",
            "full_pool_candidates": pool,
        }
        if fail_on_symbol:
            payload["fail_on_symbol"] = fail_on_symbol
        return payload

    def test_empty_root_candidate_and_next_get_do_not_create_sqlite_or_artifacts(self) -> None:
        self.assertFalse(self.meta_path.exists())
        self.assertFalse((self.root / ".stock_ming_3").exists())

        candidate_packet = candidate_service.read_candidate_radar_cache()
        next_packet = next_session_service.read_next_session_cache()

        self.assertEqual(candidate_packet["packet_key"], candidate_service.PACKET_KEY)
        self.assertEqual(next_packet["packet_key"], next_session_service.packet_service.next_session_projection.PACKET_KEY)
        self.assertTrue(candidate_packet["read_only"])
        self.assertFalse(candidate_packet["external_calls_triggered"])
        self.assertFalse(next_packet["external_calls_triggered"])
        self.assertFalse(self.meta_path.exists())
        self.assertFalse((self.root / ".stock_ming_3").exists())
        self.assertFalse(self.runtime_root.exists())
        self.assertFalse(list(self.root.rglob("*.sqlite")))
        self.assertFalse(list(self.root.rglob("*.jsonl")))

    def test_scope_hash_binds_result_affecting_candidate_fields(self) -> None:
        pool = self._pool()
        baseline = candidate_service._candidate_v05_scope_hash(pool, {"data_date": "2026-07-13"})
        changed_score = [{**row, "score": 999} if index == 0 else row for index, row in enumerate(pool)]
        changed_gaps = [{**row, "data_gaps": ["different_gap"]} if index == 0 else row for index, row in enumerate(pool)]

        self.assertNotEqual(
            baseline,
            candidate_service._candidate_v05_scope_hash(changed_score, {"data_date": "2026-07-13"}),
        )
        self.assertNotEqual(
            baseline,
            candidate_service._candidate_v05_scope_hash(changed_gaps, {"data_date": "2026-07-13"}),
        )

    def test_v05_post_processes_supplied_pool_updates_next_session_and_preserves_last_good(self) -> None:
        worker_packet_key = worker_service.RUNTIME_QA_EXECUTION_PACKET_KEY
        worker_packet_sentinel = {"schema_version": "worker_packet_sentinel.v1", "status": "preserved"}
        SQLiteMetaStore(self.meta_path).write_packet(worker_packet_key, worker_packet_sentinel)
        task = candidate_service.run_candidate_full_pool_worker_fallback_task(self._payload())

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "candidate_radar_v05_local_batch_ready")
        packet = candidate_service.read_candidate_radar_cache()
        self.assertEqual(packet["status"], "candidate_radar_v05_local_batch_ready")
        counts = packet["candidate_radar_v05_bucket_counts"]
        self.assertEqual(counts["input_count"], 12)
        self.assertEqual(counts["processed_count"], 12)
        self.assertEqual(counts["chunk_count"], 3)
        self.assertEqual(counts["stage_count"], 3)
        self.assertGreater(counts["top_count"], 0)
        self.assertGreater(counts["watch_count"], 0)
        self.assertGreater(counts["excluded_count"], 0)
        self.assertEqual(
            counts["top_count"] + counts["watch_count"] + counts["excluded_count"],
            12,
        )
        runtime = packet["candidate_radar_v05_runtime"]
        self.assertEqual(runtime["status"], "worker_v04_local_batch_runtime_success")
        self.assertTrue(all(row["append_only_write_done"] for row in runtime["stage_rows"]))
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["candidate_is_not_buy_instruction"])

        next_packet = next_session_service.read_next_session_cache()
        lineage = next_packet["candidate_radar_v05_lineage"]
        self.assertEqual(lineage["status"], "same_packet_lineage_ready")
        self.assertEqual(lineage["candidate_task_id"], task["task_id"])
        self.assertEqual(lineage["candidate_scope_hash"], packet["candidate_radar_v05_scope_hash"])
        self.assertEqual(lineage["candidate_result_version"], packet["candidate_radar_v05_result_version"])
        self.assertEqual(lineage["data_date"], "2026-07-13")
        self.assertEqual(next_packet["result_version"], packet["candidate_radar_v05_result_version"])
        self.assertEqual(next_packet["data_date"], "2026-07-13")
        self.assertEqual(next_packet["trade_date"], "2026-07-13")
        self.assertEqual(
            next_packet["freshness_state"]["state"],
            lineage["freshness_state"]["state"],
        )
        self.assertFalse(next_packet["external_calls_triggered"])
        self.assertFalse(next_packet["tushare_called"])
        self.assertFalse(next_packet["deepseek_called"])
        self.assertTrue(next_packet["does_not_modify_strategy_action"])
        self.assertTrue(next_packet["does_not_modify_operation_zones"])
        self.assertEqual(SQLiteMetaStore(self.meta_path).read_packet(worker_packet_key), worker_packet_sentinel)

        # Compatibility P3 summaries may still contain an older result.  They must
        # not overwrite the newer v0.5 same-packet lineage on the Next Session GET.
        store = SQLiteMetaStore(self.meta_path)
        candidate_packet_with_old_p3 = dict(store.read_packet(candidate_service.PACKET_KEY))
        candidate_packet_with_old_p3["search_quant_projection_interpretation_summary"] = {
            "interpretation_ready": True,
            "ordinary_result_summary": "legacy compatibility summary",
            "symbol": "OLD001",
        }
        candidate_packet_with_old_p3["search_quant_result_version_summary"] = {
            "current_result_version": "legacy-qrv",
            "current_result_task_id": "legacy-task",
            "current_result_data_date": "2026-07-07",
            "current_result_freshness_state": "fresh",
        }
        candidate_packet_with_old_p3["search_quant_result_lineage"] = {
            "result_version": "legacy-qrv",
            "task_id": "legacy-task",
        }
        store.write_packet(candidate_service.PACKET_KEY, candidate_packet_with_old_p3)
        normalized_next_packet = next_session_service.read_next_session_cache()
        self.assertEqual(normalized_next_packet["result_version"], packet["candidate_radar_v05_result_version"])
        self.assertEqual(normalized_next_packet["current_result_task_id"], task["task_id"])
        self.assertEqual(normalized_next_packet["data_date"], "2026-07-13")
        self.assertEqual(normalized_next_packet["freshness_state"]["state"], "unknown")

        store = SQLiteMetaStore(self.meta_path)
        last_good_before = store.read_packet(candidate_service.CANDIDATE_V05_LAST_GOOD_PACKET_KEY)
        failed_task = candidate_service.run_candidate_full_pool_worker_fallback_task(
            self._payload(fail_on_symbol="000006.SZ")
        )

        self.assertEqual(failed_task["status"], "failed")
        current_after = store.read_packet(candidate_service.PACKET_KEY)
        last_good_after = store.read_packet(candidate_service.CANDIDATE_V05_LAST_GOOD_PACKET_KEY)
        self.assertEqual(current_after["candidate_radar_v05_result_version"], last_good_before["candidate_radar_v05_result_version"])
        self.assertEqual(last_good_after["candidate_radar_v05_result_version"], last_good_before["candidate_radar_v05_result_version"])
        self.assertEqual(current_after["candidate_radar_v05_bucket_counts"]["processed_count"], 12)

    def test_local_batch_downgrades_unvalidated_snapshot_freshness(self) -> None:
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_path.write_text(
            json.dumps(
                {
                    "data_freshness": {
                        "state": "today",
                        "freshness_state": "fresh",
                        "expected_trade_date": "2026-07-07",
                        "data_date": "2026-07-07",
                        "last_updated": "2026-07-07T17:04:35",
                        "expected_trade_date_calendar_validated": False,
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        task = candidate_service.run_candidate_full_pool_worker_fallback_task(self._payload())
        self.assertEqual(task["status"], "success")
        packet = candidate_service.read_candidate_radar_cache()
        freshness = packet["freshness_state"]
        self.assertEqual(freshness["state"], "stale")
        self.assertEqual(freshness["freshness_state"], "stale")
        self.assertEqual(freshness["label"], "数据日期未按交易日历验证")
        self.assertFalse(freshness["expected_trade_date_calendar_validated"])
        self.assertEqual(freshness["as_of_date"], "2026-07-13")

        next_packet = next_session_service.read_next_session_cache()
        lineage_freshness = next_packet["candidate_radar_v05_lineage"]["freshness_state"]
        self.assertEqual(lineage_freshness["state"], "stale")
        self.assertFalse(lineage_freshness["expected_trade_date_calendar_validated"])


if __name__ == "__main__":
    unittest.main()
