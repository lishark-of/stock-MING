from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from server.api.routes_candidate import get_candidate_radar_cache
from server.services import candidate_service, data_health_service, packet_service, task_service
from storage.sqlite_meta import SQLiteMetaStore


class CandidateCacheReadSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        candidate_service._clear_candidate_radar_cache_memo()

    def tearDown(self) -> None:
        candidate_service._clear_candidate_radar_cache_memo()

    @staticmethod
    def _file_state(path: Path) -> tuple[bool, int, int, str]:
        if not path.exists():
            return False, 0, 0, ""
        payload = path.read_bytes()
        stat = path.stat()
        return True, stat.st_size, stat.st_mtime_ns, hashlib.sha256(payload).hexdigest()

    def test_candidate_get_uses_read_only_sqlite_without_db_or_wal_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="candidate_get_read_only_") as tmp:
            root = Path(tmp)
            db_path = root / "meta.sqlite"
            snapshot_path = root / "command_center_latest.json"
            snapshot = {
                "timestamp": "2026-07-17T09:30:00",
                "data_freshness": {
                    "state": "stale",
                    "expected_trade_date": "2026-07-17",
                    "data_date": "2026-07-16",
                    "expected_trade_date_calendar_validated": False,
                },
            }
            snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
            packet = {
                "packet_key": candidate_service.PACKET_KEY,
                "schema_version": candidate_service.SCHEMA_VERSION,
                "status": "ready",
                "scan_mode": "quick_cache_scan",
                "source_snapshot_hash": candidate_service._snapshot_fingerprint(snapshot),
                "candidate_rows": [],
                "counts": {},
                "policy": {},
                "call_ledger": [],
                "warnings": [],
                "freshness_state": {
                    "state": "stale",
                    "expected_trade_date": "2026-07-17",
                    "data_date": "2026-07-16",
                    "expected_trade_date_calendar_validated": False,
                },
            }
            SQLiteMetaStore(db_path).write_packet(candidate_service.PACKET_KEY, packet)
            tracked_paths = [
                db_path,
                Path(f"{db_path}-wal"),
                Path(f"{db_path}-shm"),
                Path(f"{db_path}-journal"),
            ]
            before = {str(path): self._file_state(path) for path in tracked_paths}

            with (
                patch.object(candidate_service, "SQLITE_META_PATH", db_path),
                patch.object(packet_service, "SNAPSHOT_CACHE_PATH", snapshot_path),
                patch.object(
                    SQLiteMetaStore,
                    "_init",
                    side_effect=AssertionError("candidate GET must not initialize or migrate SQLite"),
                ),
            ):
                response = get_candidate_radar_cache()

            after = {str(path): self._file_state(path) for path in tracked_paths}
            self.assertEqual(response["data"]["schema_version"], candidate_service.SCHEMA_VERSION)
            self.assertTrue(response["data"]["read_only"])
            self.assertEqual(before, after)

    def test_data_health_freshness_packet_uses_dedicated_key_without_overwriting_candidate_schema(self) -> None:
        source_snapshot = {
            "timestamp": "2026-07-17T09:30:00",
            "data_freshness": {
                "state": "fresh",
                "expected_trade_date": "2026-07-17",
                "data_date": "2026-07-17",
            },
            "radar_packet": {
                "status": "ready",
                "expected_trade_date": "2026-07-17",
                "data_date": "2026-07-17",
                "freshness_state": "fresh",
            },
            "a_share_evidence_packet": {
                "status": "ready",
                "expected_trade_date": "2026-07-17",
                "data_date": "2026-07-17",
                "freshness_state": "fresh",
            },
            "market_packet": {
                "status": "ready",
                "expected_trade_date": "2026-07-17",
                "data_date": "2026-07-17",
                "freshness_state": "fresh",
            },
        }
        _, _, packets = data_health_service._build_local_producer_cache_refresh_packets(
            source_snapshot,
            target="002008.SZ",
            now="2026-07-17T09:30:00",
        )
        freshness_key = data_health_service.CANDIDATE_RADAR_FRESHNESS_PACKET_KEY
        self.assertIn(freshness_key, packets)
        self.assertNotIn(candidate_service.PACKET_KEY, packets)
        self.assertEqual(packets[freshness_key]["schema_version"], "current_evidence_producer_cache_packet.v1")
        self.assertEqual(packets[freshness_key]["producer"], "candidate_radar")

        with tempfile.TemporaryDirectory(prefix="candidate_key_isolation_") as tmp:
            db_path = Path(tmp) / "meta.sqlite"
            canonical = {
                "packet_key": candidate_service.PACKET_KEY,
                "schema_version": candidate_service.SCHEMA_VERSION,
                "status": "ready",
                "sentinel": "canonical_candidate_packet_must_survive",
            }
            store = SQLiteMetaStore(db_path)
            store.write_packet(candidate_service.PACKET_KEY, canonical)
            for packet_key, packet in packets.items():
                store.write_packet(packet_key, packet)

            self.assertEqual(store.read_packet(candidate_service.PACKET_KEY), canonical)
            self.assertEqual(
                store.read_packet(freshness_key)["schema_version"],
                "current_evidence_producer_cache_packet.v1",
            )

    def test_candidate_task_replay_wrong_or_missing_schema_fails_closed_without_builder_recursion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="candidate_replay_fail_closed_") as tmp:
            root = Path(tmp)
            db_path = root / "meta.sqlite"
            snapshot_path = root / "command_center_latest.json"
            snapshot_path.write_text(
                json.dumps(
                    {
                        candidate_service.PACKET_KEY: {
                            "packet_key": candidate_service.PACKET_KEY,
                            "schema_version": "current_evidence_producer_cache_packet.v1",
                            "status": "ready",
                        }
                    }
                ),
                encoding="utf-8",
            )
            SQLiteMetaStore(db_path).write_packet(
                candidate_service.PACKET_KEY,
                {
                    "packet_key": candidate_service.PACKET_KEY,
                    "schema_version": "current_evidence_producer_cache_packet.v1",
                    "status": "ready",
                },
            )

            with (
                patch.object(task_service, "SQLITE_META_PATH", db_path),
                patch.object(packet_service, "SNAPSHOT_CACHE_PATH", snapshot_path),
                patch.object(
                    candidate_service,
                    "read_candidate_radar_cache",
                    side_effect=AssertionError("task replay must never call the candidate builder"),
                ) as builder,
            ):
                self.assertIsNone(task_service._candidate_cache_replay_packet())
                builder.assert_not_called()

            missing_db_path = root / "missing.sqlite"
            snapshot_path.write_text("{}", encoding="utf-8")
            with (
                patch.object(task_service, "SQLITE_META_PATH", missing_db_path),
                patch.object(packet_service, "SNAPSHOT_CACHE_PATH", snapshot_path),
                patch.object(
                    candidate_service,
                    "read_candidate_radar_cache",
                    side_effect=AssertionError("task replay must never call the candidate builder"),
                ) as builder,
            ):
                self.assertIsNone(task_service._candidate_cache_replay_packet())
                builder.assert_not_called()

    def test_candidate_cache_memo_reuses_one_build_across_repeated_reads(self) -> None:
        with tempfile.TemporaryDirectory(prefix="candidate_memo_repeat_") as tmp:
            root = Path(tmp)
            snapshot_path = root / "command_center_latest.json"
            snapshot_path.write_text("{}", encoding="utf-8")
            build_count = 0

            def build_packet(*_args, **_kwargs) -> dict:
                nonlocal build_count
                build_count += 1
                return {"packet_key": candidate_service.PACKET_KEY, "build_count": build_count}

            with (
                patch.object(candidate_service, "SQLITE_META_PATH", root / "meta.sqlite"),
                patch.object(packet_service, "SNAPSHOT_CACHE_PATH", snapshot_path),
                patch.object(candidate_service, "_build_candidate_radar_packet", side_effect=build_packet),
            ):
                packets = [candidate_service.read_candidate_radar_cache() for _ in range(21)]

            self.assertEqual(build_count, 1)
            self.assertEqual({packet["build_count"] for packet in packets}, {1})

    def test_candidate_cache_memo_singleflights_eight_threads(self) -> None:
        with tempfile.TemporaryDirectory(prefix="candidate_memo_threads_") as tmp:
            root = Path(tmp)
            snapshot_path = root / "command_center_latest.json"
            snapshot_path.write_text("{}", encoding="utf-8")
            build_count = 0
            count_lock = threading.Lock()
            start_barrier = threading.Barrier(8)

            def build_packet(*_args, **_kwargs) -> dict:
                nonlocal build_count
                with count_lock:
                    build_count += 1
                    current_build = build_count
                time.sleep(0.05)
                return {
                    "packet_key": candidate_service.PACKET_KEY,
                    "build_count": current_build,
                    "nested": {"rows": []},
                }

            def read_packet() -> dict:
                start_barrier.wait(timeout=2)
                return candidate_service.read_candidate_radar_cache()

            with (
                patch.object(candidate_service, "SQLITE_META_PATH", root / "meta.sqlite"),
                patch.object(packet_service, "SNAPSHOT_CACHE_PATH", snapshot_path),
                patch.object(candidate_service, "_build_candidate_radar_packet", side_effect=build_packet),
                ThreadPoolExecutor(max_workers=8) as pool,
            ):
                packets = list(pool.map(lambda _: read_packet(), range(8)))

            self.assertEqual(build_count, 1)
            self.assertEqual({packet["build_count"] for packet in packets}, {1})
            self.assertEqual(len({id(packet) for packet in packets}), 8)
            self.assertEqual(len({id(packet["nested"]) for packet in packets}), 8)

    def test_candidate_cache_memo_returns_independent_json_copies(self) -> None:
        with tempfile.TemporaryDirectory(prefix="candidate_memo_copy_") as tmp:
            root = Path(tmp)
            snapshot_path = root / "command_center_latest.json"
            snapshot_path.write_text("{}", encoding="utf-8")
            build_count = 0

            def build_packet() -> dict:
                nonlocal build_count
                build_count += 1
                return {
                    "packet_key": candidate_service.PACKET_KEY,
                    "nested": {"rows": [{"value": 1}]},
                }

            with (
                patch.object(candidate_service, "SQLITE_META_PATH", root / "meta.sqlite"),
                patch.object(packet_service, "SNAPSHOT_CACHE_PATH", snapshot_path),
                patch.object(candidate_service, "_read_candidate_radar_cache_uncached", side_effect=build_packet),
            ):
                first = candidate_service.read_candidate_radar_cache()
                first["nested"]["rows"][0]["value"] = 99
                second = candidate_service.read_candidate_radar_cache()

            self.assertEqual(build_count, 1)
            self.assertEqual(second["nested"]["rows"][0]["value"], 1)
            self.assertIsNot(first, second)
            self.assertIsNot(first["nested"], second["nested"])

    def test_candidate_cache_memo_invalidates_on_same_size_atomic_snapshot_replace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="candidate_memo_snapshot_replace_") as tmp:
            root = Path(tmp)
            snapshot_path = root / "command_center_latest.json"
            snapshot_path.write_text('{"v":1}', encoding="utf-8")
            original_stat = snapshot_path.stat()
            build_count = 0

            def build_packet() -> dict:
                nonlocal build_count
                build_count += 1
                return {"packet_key": candidate_service.PACKET_KEY, "build_count": build_count}

            with (
                patch.object(candidate_service, "SQLITE_META_PATH", root / "meta.sqlite"),
                patch.object(packet_service, "SNAPSHOT_CACHE_PATH", snapshot_path),
                patch.object(candidate_service, "_read_candidate_radar_cache_uncached", side_effect=build_packet),
            ):
                first = candidate_service.read_candidate_radar_cache()
                replacement = root / "replacement.json"
                replacement.write_text('{"v":2}', encoding="utf-8")
                self.assertEqual(replacement.stat().st_size, original_stat.st_size)
                os.replace(replacement, snapshot_path)
                self.assertNotEqual(snapshot_path.stat().st_ino, original_stat.st_ino)
                second = candidate_service.read_candidate_radar_cache()

            self.assertEqual(first["build_count"], 1)
            self.assertEqual(second["build_count"], 2)
            self.assertEqual(build_count, 2)

    def test_candidate_cache_memo_invalidates_on_canonical_sqlite_or_wal_change_but_not_shm(self) -> None:
        with tempfile.TemporaryDirectory(prefix="candidate_memo_sqlite_wal_") as tmp:
            root = Path(tmp)
            snapshot_path = root / "command_center_latest.json"
            snapshot_path.write_text("{}", encoding="utf-8")
            sqlite_path = root / "meta.sqlite"
            store = SQLiteMetaStore(sqlite_path)
            store.write_packet("unrelated_seed_packet", {"schema_version": "seed.v1"})
            wal_path = Path(f"{sqlite_path}-wal")
            shm_path = Path(f"{sqlite_path}-shm")
            build_count = 0

            def build_packet() -> dict:
                nonlocal build_count
                build_count += 1
                return {"packet_key": candidate_service.PACKET_KEY, "build_count": build_count}

            with (
                patch.object(candidate_service, "SQLITE_META_PATH", sqlite_path),
                patch.object(packet_service, "SNAPSHOT_CACHE_PATH", snapshot_path),
                patch.object(candidate_service, "_read_candidate_radar_cache_uncached", side_effect=build_packet),
            ):
                self.assertEqual(candidate_service.read_candidate_radar_cache()["build_count"], 1)
                store.write_packet(
                    candidate_service.PACKET_KEY,
                    {
                        "packet_key": candidate_service.PACKET_KEY,
                        "schema_version": candidate_service.SCHEMA_VERSION,
                        "status": "ready",
                    },
                )
                self.assertEqual(candidate_service.read_candidate_radar_cache()["build_count"], 2)
                wal_path.write_bytes(b"wal-created")
                self.assertEqual(candidate_service.read_candidate_radar_cache()["build_count"], 3)
                shm_path.write_bytes(b"shm-must-not-be-a-generation-input")
                self.assertEqual(candidate_service.read_candidate_radar_cache()["build_count"], 3)

            self.assertEqual(build_count, 3)

    def test_candidate_cache_memo_does_not_publish_build_crossing_generation_change(self) -> None:
        with tempfile.TemporaryDirectory(prefix="candidate_memo_generation_race_") as tmp:
            root = Path(tmp)
            snapshot_path = root / "command_center_latest.json"
            snapshot_path.write_text('{"v":1}', encoding="utf-8")
            build_count = 0

            def build_packet() -> dict:
                nonlocal build_count
                build_count += 1
                current_build = build_count
                if current_build == 1:
                    replacement = root / "replacement-during-build.json"
                    replacement.write_text('{"v":2}', encoding="utf-8")
                    os.replace(replacement, snapshot_path)
                return {"packet_key": candidate_service.PACKET_KEY, "build_count": current_build}

            with (
                patch.object(candidate_service, "SQLITE_META_PATH", root / "meta.sqlite"),
                patch.object(packet_service, "SNAPSHOT_CACHE_PATH", snapshot_path),
                patch.object(candidate_service, "_read_candidate_radar_cache_uncached", side_effect=build_packet),
            ):
                first = candidate_service.read_candidate_radar_cache()
                second = candidate_service.read_candidate_radar_cache()

            self.assertEqual(build_count, 2)
            self.assertEqual(first["build_count"], 2)
            self.assertEqual(second["build_count"], 2)


if __name__ == "__main__":
    unittest.main()
