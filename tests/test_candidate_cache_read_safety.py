from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.api.routes_candidate import get_candidate_radar_cache
from server.services import candidate_service, data_health_service, packet_service, task_service
from storage.sqlite_meta import SQLiteMetaStore


class CandidateCacheReadSafetyTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
