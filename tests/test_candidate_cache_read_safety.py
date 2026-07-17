from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from server.api.routes_candidate import get_candidate_radar_cache
from server.services import candidate_service, data_health_service, motion_evidence_service, packet_service, task_service
from server.services.request_local_memo import request_local_memo_scope
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

    def test_candidate_cache_reuses_one_build_only_inside_request_scope(self) -> None:
        build_count = 0

        def build_packet() -> dict:
            nonlocal build_count
            build_count += 1
            return {"packet_key": candidate_service.PACKET_KEY, "build_count": build_count}

        @request_local_memo_scope
        def read_twice() -> tuple[dict, dict]:
            return candidate_service.read_candidate_radar_cache(), candidate_service.read_candidate_radar_cache()

        with patch.object(candidate_service, "_read_candidate_radar_cache_uncached", side_effect=build_packet):
            first_a, first_b = read_twice()
            second_a, second_b = read_twice()

        self.assertIs(first_a, first_b)
        self.assertIs(second_a, second_b)
        self.assertIsNot(first_a, second_a)
        self.assertEqual((first_a["build_count"], second_a["build_count"]), (1, 2))
        self.assertEqual(build_count, 2)

    def test_candidate_cache_cross_request_rereads_new_deleted_and_corrupt_motion_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="candidate_motion_reread_") as tmp:
            report_path = Path(tmp) / "motion_browser_qa_report.json"
            build_count = 0

            def build_packet() -> dict:
                nonlocal build_count
                build_count += 1
                if not report_path.exists():
                    status = "motion_evidence_missing"
                else:
                    try:
                        status = str(json.loads(report_path.read_text(encoding="utf-8"))["status"])
                    except (OSError, ValueError, KeyError, TypeError):
                        status = "motion_evidence_corrupt"
                return {
                    "packet_key": candidate_service.PACKET_KEY,
                    "build_count": build_count,
                    "motion_status": status,
                }

            @request_local_memo_scope
            def request_read() -> dict:
                first = candidate_service.read_candidate_radar_cache()
                self.assertIs(first, candidate_service.read_candidate_radar_cache())
                return first

            with patch.object(candidate_service, "_read_candidate_radar_cache_uncached", side_effect=build_packet):
                self.assertEqual(request_read()["motion_status"], "motion_evidence_missing")
                report_path.write_text('{"status":"motion_evidence_ready"}', encoding="utf-8")
                self.assertEqual(request_read()["motion_status"], "motion_evidence_ready")
                report_path.unlink()
                self.assertEqual(request_read()["motion_status"], "motion_evidence_missing")
                report_path.write_text("{broken", encoding="utf-8")
                self.assertEqual(request_read()["motion_status"], "motion_evidence_corrupt")

            self.assertEqual(build_count, 4)

    def test_candidate_cache_two_continuous_atomic_replaces_never_reuse_cross_request_packet(self) -> None:
        with tempfile.TemporaryDirectory(prefix="candidate_double_replace_") as tmp:
            root = Path(tmp)
            evidence_path = root / "motion_browser_qa_report.json"
            evidence_path.write_text('{"generation":1}', encoding="utf-8")

            def replace(version: int) -> None:
                replacement = root / f"replacement-{version}.json"
                replacement.write_text(json.dumps({"generation": version}), encoding="utf-8")
                os.replace(replacement, evidence_path)

            def build_packet() -> dict:
                return json.loads(evidence_path.read_text(encoding="utf-8"))

            @request_local_memo_scope
            def request_read() -> dict:
                return candidate_service.read_candidate_radar_cache()

            with patch.object(candidate_service, "_read_candidate_radar_cache_uncached", side_effect=build_packet):
                first = request_read()
                replace(2)
                second = request_read()
                replace(3)
                third = request_read()

            self.assertEqual([first["generation"], second["generation"], third["generation"]], [1, 2, 3])

    def test_candidate_cache_request_local_recursion_falls_through_without_deadlock(self) -> None:
        build_count = 0

        def build_packet() -> dict:
            nonlocal build_count
            build_count += 1
            if build_count == 1:
                nested = candidate_service.read_candidate_radar_cache()
                return {"packet_key": candidate_service.PACKET_KEY, "nested_generation": nested["generation"]}
            return {"packet_key": candidate_service.PACKET_KEY, "generation": build_count}

        @request_local_memo_scope
        def request_read() -> dict:
            return candidate_service.read_candidate_radar_cache()

        result: list[dict] = []
        error: list[BaseException] = []

        def run() -> None:
            try:
                result.append(request_read())
            except BaseException as exc:  # pragma: no cover - assertion below reports it
                error.append(exc)

        with patch.object(candidate_service, "_read_candidate_radar_cache_uncached", side_effect=build_packet):
            thread = threading.Thread(target=run)
            thread.start()
            thread.join(timeout=2)

        self.assertFalse(thread.is_alive(), "candidate request-local recursion must not deadlock")
        self.assertEqual(error, [])
        self.assertEqual(result, [{"packet_key": candidate_service.PACKET_KEY, "nested_generation": 2}])
        self.assertEqual(build_count, 2)

    def test_candidate_durable_evidence_attachment_is_idempotent(self) -> None:
        contract = {
            "row_count": 0,
            "durable_evidence_blocker_count": 1,
            "local_recipe_ready": True,
            "status": "candidate_radar_durable_evidence_recipe_ready_production_pending",
        }
        packet = {
            "counts": {},
            "policy": {},
            "call_ledger": [
                candidate_service._candidate_call_ledger_row(
                    api="local_candidate_radar_cache",
                    source_snapshot="sqlite_meta_candidate_radar_packet",
                    row_count=1,
                    call_status="cache_read",
                ),
                {"api": "local_candidate_radar_durable_evidence_recipe", "call_status": "stale"},
                {"api": "local_candidate_radar_production_replacement_review_preview"},
                {"api": "local_candidate_radar_durable_evidence_recipe", "call_status": "duplicate"},
            ],
            "warnings": [],
        }
        with patch.object(
            candidate_service,
            "_candidate_radar_durable_evidence_recipe",
            return_value=(contract, []),
        ):
            once = candidate_service._attach_candidate_radar_durable_evidence_recipe(packet)
            twice = candidate_service._attach_candidate_radar_durable_evidence_recipe(once)

        apis = [row.get("api") for row in twice["call_ledger"]]
        self.assertEqual(apis[0], "local_candidate_radar_cache")
        self.assertEqual(apis.count("local_candidate_radar_durable_evidence_recipe"), 1)
        self.assertLess(
            apis.index("local_candidate_radar_durable_evidence_recipe"),
            apis.index("local_candidate_radar_production_replacement_review_preview"),
        )
        self.assertEqual(
            twice["call_ledger"][apis.index("local_candidate_radar_durable_evidence_recipe")]["call_status"],
            contract["status"],
        )

    def test_persisted_quick_scan_history_does_not_replace_current_get_ledger(self) -> None:
        persisted = {
            "packet_key": candidate_service.PACKET_KEY,
            "schema_version": candidate_service.SCHEMA_VERSION,
            "status": "ready",
            "scan_mode": "quick_cache_scan",
            "candidate_rows": [],
            "call_ledger": [
                candidate_service._candidate_call_ledger_row(
                    api="local_candidate_radar_quick_scan",
                    source_snapshot="command_center_latest.json",
                    row_count=0,
                    call_status="quick_scan_completed",
                )
            ],
            "counts": {},
            "policy": {},
            "warnings": [],
        }

        view = candidate_service._cache_view_from_persisted(persisted)
        apis = [row.get("api") for row in view["call_ledger"]]

        self.assertEqual(apis[0], "local_candidate_radar_cache")
        self.assertNotIn("local_candidate_radar_quick_scan", apis)
        self.assertEqual(len(apis), len(set(apis)))
        allowlist = motion_evidence_service._FASTAPI_LEDGER_APIS["/api/candidate-radar/cache"]
        self.assertEqual([allowlist.index(api) for api in apis], sorted(allowlist.index(api) for api in apis))


if __name__ == "__main__":
    unittest.main()
