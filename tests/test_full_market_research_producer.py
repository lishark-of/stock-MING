from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from server.services import full_market_research_producer_service as service
from server.services import task_service
from storage.sqlite_meta import SQLiteMetaStore
from tests.test_full_market_industry_membership import (
    _symbols as _industry_symbols,
    _install_semantic_authority,
    _write_evidence,
)


def _provider(*, count: int = 3000) -> dict:
    symbols = [f"{600000 + index:06d}.SH" for index in range(count)]
    return {
        "ready": True,
        "status": "production_version_verified",
        "blockers": [],
        "scope_hash": "a" * 64,
        "version_digest": "b" * 64,
        "universe_digest": service._digest(sorted(symbols)),
        "artifact_manifest_digest": "d" * 64,
        "universe_count": count,
        "validated_trade_date": "20260717",
        "symbols": symbols,
    }


def _industry() -> dict:
    return {
        "ready": True,
        "status": "full_market_industry_membership_verified",
        "scope_digest": "1" * 64,
        "source_version_digest": "2" * 64,
        "artifact_sha256": "3" * 64,
        "manifest_digest": "4" * 64,
        "pointer_digest": "e" * 64,
        "semantic_evidence_sha256": "6" * 64,
        "blockers": [],
        "read_only": True,
        "writes_storage": False,
        "external_calls_triggered": False,
    }


def _request_pair(contract: dict) -> tuple[dict, dict]:
    factor = service._request_packet(
        contract,
        output_kind=service.FACTOR_OUTPUT_CONTRACT["output_kind"],
        target_dataset=service.FACTOR_TARGET_DATASET,
        target_packet_key=service.FACTOR_TARGET_PACKET_KEY,
        output_contract_digest=service.FACTOR_OUTPUT_CONTRACT_DIGEST,
        request_digest=contract["factor_request_digest"],
    )
    radar = service._request_packet(
        contract,
        output_kind=service.RADAR_OUTPUT_CONTRACT["output_kind"],
        target_dataset=service.RADAR_TARGET_DATASET,
        target_packet_key=service.RADAR_TARGET_PACKET_KEY,
        output_contract_digest=service.RADAR_OUTPUT_CONTRACT_DIGEST,
        request_digest=contract["radar_request_digest"],
    )
    return factor, radar


class FullMarketResearchProducerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.industry_patcher = patch.object(
            service,
            "validate_full_market_industry_membership",
            return_value=_industry(),
        )
        self.industry_patcher.start()
        self.addCleanup(self.industry_patcher.stop)

    def test_contract_fails_closed_when_provider_pointer_is_missing(self):
        blocked = {
            "ready": False,
            "status": "production_version_blocked",
            "blockers": ["pointer_missing_or_invalid"],
            "scope_hash": "",
            "version_digest": "",
            "universe_digest": "",
            "artifact_manifest_digest": "",
            "universe_count": 0,
            "validated_trade_date": "",
            "symbols": [],
        }
        with patch.object(
            service,
            "validate_tushare_full_market_production_version",
            return_value=blocked,
        ):
            contract = service.build_full_market_factor_radar_map_reduce_contract(
                {"effective_dated_industry_membership_digest": "e" * 64}
            )

        self.assertFalse(contract["execution_request_ready"])
        self.assertFalse(contract["dispatch_allowed"])
        self.assertFalse(contract["production_complete"])
        self.assertIn("pointer_missing_or_invalid", contract["blockers"])
        self.assertIn(service.EXTERNAL_LINEAGE_BLOCKER, contract["blockers"])
        self.assertFalse(contract["external_calls_triggered"])

    def test_exact_provider_pointer_builds_two_independent_requests_only(self):
        with patch.object(
            service,
            "validate_tushare_full_market_production_version",
            return_value=_provider(),
        ):
            contract = service.build_full_market_factor_radar_map_reduce_contract(
                {"effective_dated_industry_membership_digest": "e" * 64}
            )

        self.assertTrue(contract["execution_request_scope_ready"])
        self.assertFalse(contract["execution_request_ready"])
        self.assertFalse(contract["dispatch_allowed"])
        self.assertFalse(contract["factor_production_complete"])
        self.assertFalse(contract["candidate_radar_production_replacement"])
        self.assertTrue(contract["output_contracts_are_independent"])
        self.assertNotEqual(
            contract["factor_output_contract_digest"],
            contract["radar_output_contract_digest"],
        )
        self.assertEqual(
            contract["factor_output_contract"]["required_metrics"],
            [
                "cross_sectional_rank",
                "cross_sectional_zscore",
                "industry_neutral_score",
                "size_neutral_score",
                "combined_factor_score",
            ],
        )
        self.assertIn(
            "deep_scan_score",
            contract["radar_output_contract"]["required_fields"],
        )
        self.assertTrue(
            contract["shared_scope_material"][
                "effective_dated_industry_membership_verified"
            ]
        )
        self.assertNotIn(
            "authoritative_effective_dated_industry_membership_missing",
            contract["blockers"],
        )

    def test_provider_claiming_ready_below_3000_is_rejected(self):
        with patch.object(
            service,
            "validate_tushare_full_market_production_version",
            return_value=_provider(count=2999),
        ):
            contract = service.build_full_market_factor_radar_map_reduce_contract(
                {"effective_dated_industry_membership_digest": "e" * 64}
            )

        self.assertFalse(contract["execution_request_ready"])
        self.assertIn(
            "authoritative_provider_universe_below_3000",
            contract["blockers"],
        )

    def test_caller_industry_digest_cannot_self_seal_authoritative_evidence(self):
        with patch.object(
            service,
            "validate_tushare_full_market_production_version",
            return_value=_provider(),
        ):
            contract = service.build_full_market_factor_radar_map_reduce_contract(
                {"effective_dated_industry_membership_digest": "9" * 64}
            )

        self.assertEqual(
            contract["shared_scope_material"][
                "requested_effective_dated_industry_membership_digest"
            ],
            "e" * 64,
        )
        self.assertFalse(contract["execution_request_ready"])
        self.assertFalse(contract["production_prerequisites_ready"])
        self.assertIn("requested_industry_pointer_digest_mismatch", contract["blockers"])

    def test_missing_effective_dated_industry_digest_blocks_shared_dispatch(self):
        with patch.object(
            service,
            "validate_tushare_full_market_production_version",
            return_value=_provider(),
        ):
            contract = service.build_full_market_factor_radar_map_reduce_contract({})

        self.assertTrue(contract["execution_request_scope_ready"])
        self.assertFalse(contract["execution_request_ready"])
        self.assertNotIn(
            "effective_dated_industry_membership_digest_missing",
            contract["blockers"],
        )

    def test_factor_request_cannot_be_relabelled_as_radar(self):
        with patch.object(
            service,
            "validate_tushare_full_market_production_version",
            return_value=_provider(),
        ):
            contract = service.build_full_market_factor_radar_map_reduce_contract(
                {"effective_dated_industry_membership_digest": "e" * 64}
            )
        factor, radar = _request_pair(contract)
        self.assertTrue(
            service._validate_independent_output_requests(factor, radar, contract)["ready"]
        )
        tampered = dict(radar)
        tampered["output_contract_digest"] = service.FACTOR_OUTPUT_CONTRACT_DIGEST
        tampered["packet_digest"] = service._child_packet_digest(tampered)
        audit = service._validate_independent_output_requests(factor, tampered, contract)
        self.assertFalse(audit["ready"])
        self.assertIn("radar_authoritative_fields_exact", audit["blockers"])
        self.assertIn("output_digests_are_distinct", audit["blockers"])
        self.assertFalse(audit["factor_rows_accepted_as_radar"])
        self.assertFalse(audit["radar_rows_accepted_as_factor"])

    def test_independence_validator_rejects_reused_or_forged_bindings(self):
        with patch.object(
            service,
            "validate_tushare_full_market_production_version",
            return_value=_provider(),
        ):
            contract = service.build_full_market_factor_radar_map_reduce_contract(
                {"effective_dated_industry_membership_digest": "e" * 64}
            )
        factor, radar = _request_pair(contract)
        attacks = {
            "same_request_digest": ("request_digest", factor["request_digest"]),
            "wrong_head": ("head_full", "f" * 40),
            "wrong_provider": ("provider_version_digest", "9" * 64),
            "fake_industry_verified": ("effective_dated_industry_membership_verified", False),
        }
        for name, (field, value) in attacks.items():
            with self.subTest(name=name):
                tampered = dict(radar)
                tampered[field] = value
                tampered["packet_digest"] = service._child_packet_digest(tampered)
                audit = service._validate_independent_output_requests(
                    factor, tampered, contract
                )
                self.assertFalse(audit["ready"])
        reused_packet_digest = dict(radar)
        reused_packet_digest["packet_digest"] = factor["packet_digest"]
        audit = service._validate_independent_output_requests(
            factor, reused_packet_digest, contract
        )
        self.assertFalse(audit["ready"])
        self.assertIn("packet_digests_are_distinct", audit["blockers"])
        missing_head = dict(radar)
        missing_head.pop("head_full")
        missing_head["packet_digest"] = service._child_packet_digest(missing_head)
        self.assertFalse(
            service._validate_independent_output_requests(
                factor, missing_head, contract
            )["ready"]
        )

    def test_public_validator_rebuilds_authoritative_contract(self):
        with patch.object(
            service,
            "validate_tushare_full_market_production_version",
            return_value=_provider(),
        ):
            contract = service.build_full_market_factor_radar_map_reduce_contract(
                {"effective_dated_industry_membership_digest": "e" * 64}
            )
            factor, radar = _request_pair(contract)
            self.assertTrue(
                service.validate_independent_output_requests(factor, radar)["ready"]
            )
            forged = dict(factor)
            forged["provider_scope_hash"] = "9" * 64
            forged["packet_digest"] = service._child_packet_digest(forged)
            self.assertFalse(
                service.validate_independent_output_requests(forged, radar)["ready"]
            )

    def test_public_validator_rejects_cross_bundle_splicing(self):
        with patch.object(
            service,
            "validate_tushare_full_market_production_version",
            return_value=_provider(),
        ):
            first = service.build_full_market_factor_radar_map_reduce_contract(
                {"effective_dated_industry_membership_digest": "e" * 64}
            )
            second = service.build_full_market_factor_radar_map_reduce_contract(
                {"effective_dated_industry_membership_digest": "f" * 64}
            )
            factor_first, radar_first = _request_pair(first)
            factor_second, radar_second = _request_pair(second)
            self.assertTrue(
                service.validate_independent_output_requests(factor_first, radar_first)[
                    "ready"
                ]
            )
            self.assertFalse(
                service.validate_independent_output_requests(factor_second, radar_second)[
                    "ready"
                ]
            )
            self.assertFalse(
                service.validate_independent_output_requests(factor_first, radar_second)[
                    "ready"
                ]
            )
            self.assertFalse(
                service.validate_independent_output_requests(factor_second, radar_first)[
                    "ready"
                ]
            )

    def test_explicit_post_writes_only_three_local_request_packets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta_path = root / "meta.sqlite"
            with (
                patch.object(service, "SQLITE_META_PATH", meta_path),
                patch.object(task_service, "SQLITE_META_PATH", meta_path),
                patch.object(
                    service,
                    "validate_tushare_full_market_production_version",
                    return_value=_provider(),
                ),
            ):
                task = service.run_full_market_factor_radar_map_reduce_request(
                    {"effective_dated_industry_membership_digest": "e" * 64},
                    evidence_root=root,
                    meta_path=meta_path,
                )

            store = SQLiteMetaStore(meta_path, read_only=True)
            factor = store.read_packet(service.FACTOR_REQUEST_PACKET_KEY)
            radar = store.read_packet(service.RADAR_REQUEST_PACKET_KEY)
            coordinator = store.read_packet(service.COORDINATOR_PACKET_KEY)
            self.assertEqual(task["status"], "success")
            self.assertTrue(factor)
            self.assertTrue(radar)
            self.assertTrue(coordinator)
            self.assertNotEqual(factor["packet_digest"], radar["packet_digest"])
            self.assertFalse(factor["writes_target_dataset"])
            self.assertFalse(radar["writes_target_packet"])
            self.assertFalse(coordinator["production_complete"])
            self.assertIsNone(store.read_packet(service.FACTOR_TARGET_PACKET_KEY))
            self.assertIsNone(store.read_packet(service.RADAR_TARGET_PACKET_KEY))
            self.assertFalse(task["external_calls_triggered"])
            self.assertFalse(task["tushare_called"])
            self.assertFalse(task["deepseek_called"])
            self.assertFalse(task["github_called"])
            self.assertTrue(task["does_not_execute_trades"])

    def test_route_is_post_only_and_does_not_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            with (
                patch.object(service, "SQLITE_META_PATH", meta_path),
                patch.object(task_service, "SQLITE_META_PATH", meta_path),
                patch.object(
                    service,
                    "validate_tushare_full_market_production_version",
                    return_value=_provider(),
                ),
            ):
                client = TestClient(app)
                get_response = client.get(
                    "/api/worker/full-market-factor-radar-map-reduce-request"
                )
                post_response = client.post(
                    "/api/worker/full-market-factor-radar-map-reduce-request",
                    json={"effective_dated_industry_membership_digest": "e" * 64},
                )

            self.assertEqual(get_response.status_code, 405)
            self.assertEqual(post_response.status_code, 200)
            payload = post_response.json()["data"]
            self.assertFalse(payload["external_calls_triggered"])
            self.assertFalse(payload["tushare_called"])
            self.assertTrue(payload["does_not_execute_trades"])

    def test_repeated_identical_request_reuses_one_atomic_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta_path = root / "meta.sqlite"
            payload = {"effective_dated_industry_membership_digest": "e" * 64}
            with (
                patch.object(service, "SQLITE_META_PATH", meta_path),
                patch.object(task_service, "SQLITE_META_PATH", meta_path),
                patch.object(
                    service,
                    "validate_tushare_full_market_production_version",
                    return_value=_provider(),
                ),
            ):
                first = service.run_full_market_factor_radar_map_reduce_request(
                    payload, evidence_root=root, meta_path=meta_path
                )
                first_packets = {
                    key: SQLiteMetaStore(meta_path, read_only=True).read_packet(key)
                    for key in (
                        service.FACTOR_REQUEST_PACKET_KEY,
                        service.RADAR_REQUEST_PACKET_KEY,
                        service.COORDINATOR_PACKET_KEY,
                    )
                }
                second = service.run_full_market_factor_radar_map_reduce_request(
                    payload, evidence_root=root, meta_path=meta_path
                )

            store = SQLiteMetaStore(meta_path, read_only=True)
            self.assertEqual(first["task_id"], second["task_id"])
            self.assertEqual(
                first["payload_safe"]["request_bundle_id"],
                second["payload_safe"]["request_bundle_id"],
            )
            task_ids = {
                str(item.get("task_id") or "") for item in store.list_task_metadata()
            }
            tasks = [store.read_task_status(task_id) for task_id in task_ids]
            self.assertEqual(len(task_ids), 3)
            self.assertEqual(len({task["idempotency_key"] for task in tasks}), 3)
            self.assertEqual(store.task_status_history_count(), 3)
            for key, packet in first_packets.items():
                self.assertEqual(store.read_packet(key), packet)

    def test_preexisting_partial_or_corrupt_packet_matrix_fails_closed(self):
        packet_keys = (
            service.FACTOR_REQUEST_PACKET_KEY,
            service.RADAR_REQUEST_PACKET_KEY,
            service.COORDINATOR_PACKET_KEY,
        )
        payload = {"effective_dated_industry_membership_digest": "e" * 64}
        for mask in range(1, 1 << len(packet_keys)):
            with self.subTest(mask=mask), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                meta_path = root / "meta.sqlite"
                store = SQLiteMetaStore(meta_path)
                seeded: dict[str, dict] = {}
                for index, packet_key in enumerate(packet_keys):
                    if mask & (1 << index):
                        packet = {
                            "request_bundle_id": "0" * 64,
                            "bundle_digest": "1" * 64,
                            "sentinel": packet_key,
                        }
                        store.write_packet(packet_key, packet)
                        seeded[packet_key] = packet
                with (
                    patch.object(service, "SQLITE_META_PATH", meta_path),
                    patch.object(task_service, "SQLITE_META_PATH", meta_path),
                    patch.object(
                        service,
                        "validate_tushare_full_market_production_version",
                        return_value=_provider(),
                    ),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "idempotent_bundle_partial_or_conflicting_state"
                    ):
                        service.run_full_market_factor_radar_map_reduce_request(
                            payload, evidence_root=root, meta_path=meta_path
                        )
                persisted = SQLiteMetaStore(meta_path, read_only=True)
                for packet_key in packet_keys:
                    self.assertEqual(persisted.read_packet(packet_key), seeded.get(packet_key))
                self.assertEqual(persisted.list_task_metadata(), [])
                self.assertEqual(persisted.task_status_history_count(), 0)

    def test_preexisting_partial_task_and_history_matrix_fails_closed(self):
        payload = {"effective_dated_industry_membership_digest": "e" * 64}
        with tempfile.TemporaryDirectory() as source_tmp:
            source_root = Path(source_tmp)
            source_meta = source_root / "meta.sqlite"
            with (
                patch.object(service, "SQLITE_META_PATH", source_meta),
                patch.object(task_service, "SQLITE_META_PATH", source_meta),
                patch.object(
                    service,
                    "validate_tushare_full_market_production_version",
                    return_value=_provider(),
                ),
            ):
                service.run_full_market_factor_radar_map_reduce_request(
                    payload, evidence_root=source_root, meta_path=source_meta
                )
            with sqlite3.connect(source_meta) as connection:
                packet_rows = connection.execute(
                    "SELECT packet_key, payload_json, updated_at FROM packets ORDER BY packet_key"
                ).fetchall()
                task_rows = connection.execute(
                    "SELECT task_id, payload_json, updated_at FROM task_status ORDER BY task_id"
                ).fetchall()
                history_rows = connection.execute(
                    """
                    SELECT task_id, task_type, payload_json, updated_at, payload_digest
                    FROM task_status_history ORDER BY task_id
                    """
                ).fetchall()

            cases = {
                "one_exact_packet": (packet_rows[:1], [], []),
                "all_packets_one_task": (packet_rows, task_rows[:1], []),
                "all_packets_all_tasks_partial_history": (
                    packet_rows,
                    task_rows,
                    history_rows[:2],
                ),
                "orphan_task": ([], task_rows[:1], []),
                "orphan_history": ([], [], history_rows[:1]),
            }
            for name, (seed_packets, seed_tasks, seed_history) in cases.items():
                with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    meta_path = root / "meta.sqlite"
                    SQLiteMetaStore(meta_path)
                    with sqlite3.connect(meta_path) as connection:
                        connection.executemany(
                            "INSERT INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?)",
                            seed_packets,
                        )
                        connection.executemany(
                            "INSERT INTO task_status(task_id, payload_json, updated_at) VALUES (?, ?, ?)",
                            seed_tasks,
                        )
                        connection.executemany(
                            """
                            INSERT INTO task_status_history(
                                task_id, task_type, payload_json, updated_at, payload_digest
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            seed_history,
                        )
                        connection.commit()
                    before_counts = (
                        len(seed_packets),
                        len(seed_tasks),
                        len(seed_history),
                    )
                    with (
                        patch.object(service, "SQLITE_META_PATH", meta_path),
                        patch.object(task_service, "SQLITE_META_PATH", meta_path),
                        patch.object(
                            service,
                            "validate_tushare_full_market_production_version",
                            return_value=_provider(),
                        ),
                    ):
                        with self.assertRaises(RuntimeError):
                            service.run_full_market_factor_radar_map_reduce_request(
                                payload, evidence_root=root, meta_path=meta_path
                            )
                    with sqlite3.connect(meta_path) as connection:
                        after_counts = tuple(
                            connection.execute(
                                f"SELECT COUNT(*) FROM {table}"
                            ).fetchone()[0]
                            for table in (
                                "packets",
                                "task_status",
                                "task_status_history",
                            )
                        )
                    self.assertEqual(after_counts, before_counts)

    def test_different_bundle_is_blocked_without_breaking_current_bundle_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta_path = root / "meta.sqlite"
            first_payload = {
                "effective_dated_industry_membership_digest": "e" * 64
            }
            different_payload = {
                "effective_dated_industry_membership_digest": "f" * 64
            }
            with (
                patch.object(service, "SQLITE_META_PATH", meta_path),
                patch.object(task_service, "SQLITE_META_PATH", meta_path),
                patch.object(
                    service,
                    "validate_tushare_full_market_production_version",
                    return_value=_provider(),
                ),
            ):
                first = service.run_full_market_factor_radar_map_reduce_request(
                    first_payload, evidence_root=root, meta_path=meta_path
                )
                store = SQLiteMetaStore(meta_path, read_only=True)
                packet_snapshot = {
                    key: store.read_packet(key)
                    for key in (
                        service.FACTOR_REQUEST_PACKET_KEY,
                        service.RADAR_REQUEST_PACKET_KEY,
                        service.COORDINATOR_PACKET_KEY,
                    )
                }
                with self.assertRaisesRegex(
                    RuntimeError, "idempotent_bundle_partial_or_conflicting_state"
                ):
                    service.run_full_market_factor_radar_map_reduce_request(
                        different_payload, evidence_root=root, meta_path=meta_path
                    )
                replay = service.run_full_market_factor_radar_map_reduce_request(
                    first_payload, evidence_root=root, meta_path=meta_path
                )

            persisted = SQLiteMetaStore(meta_path, read_only=True)
            self.assertEqual(replay["task_id"], first["task_id"])
            self.assertEqual(len(persisted.list_task_metadata()), 3)
            self.assertEqual(persisted.task_status_history_count(), 3)
            for key, packet in packet_snapshot.items():
                self.assertEqual(persisted.read_packet(key), packet)

    def test_concurrent_identical_requests_commit_once_and_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta_path = root / "meta.sqlite"
            payload = {"effective_dated_industry_membership_digest": "e" * 64}
            SQLiteMetaStore(meta_path)

            def run_once() -> dict:
                return service.run_full_market_factor_radar_map_reduce_request(
                    payload, evidence_root=root, meta_path=meta_path
                )

            with (
                patch.object(service, "SQLITE_META_PATH", meta_path),
                patch.object(task_service, "SQLITE_META_PATH", meta_path),
                patch.object(
                    service,
                    "validate_tushare_full_market_production_version",
                    return_value=_provider(),
                ),
                ThreadPoolExecutor(max_workers=6) as executor,
            ):
                results = list(executor.map(lambda _: run_once(), range(12)))

            store = SQLiteMetaStore(meta_path, read_only=True)
            self.assertEqual(len({item["task_id"] for item in results}), 1)
            self.assertEqual(len(store.list_task_metadata()), 3)
            self.assertEqual(store.task_status_history_count(), 3)
            factor = store.read_packet(service.FACTOR_REQUEST_PACKET_KEY)
            radar = store.read_packet(service.RADAR_REQUEST_PACKET_KEY)
            with patch.object(
                service,
                "validate_tushare_full_market_production_version",
                return_value=_provider(),
            ):
                self.assertTrue(
                    service.validate_independent_output_requests(
                        factor, radar, evidence_root=root
                    )["ready"]
                )

    def test_packet_and_task_bundle_rolls_back_on_each_packet_write_failure(self):
        for blocked_key in (
            service.FACTOR_REQUEST_PACKET_KEY,
            service.RADAR_REQUEST_PACKET_KEY,
            service.COORDINATOR_PACKET_KEY,
        ):
            with (
                self.subTest(blocked_key=blocked_key),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp)
                meta_path = root / "meta.sqlite"
                SQLiteMetaStore(meta_path)
                with sqlite3.connect(meta_path) as connection:
                    connection.execute(
                        f"""
                        CREATE TRIGGER fail_bundle_packet
                        BEFORE INSERT ON packets
                        WHEN NEW.packet_key = '{blocked_key}'
                        BEGIN
                            SELECT RAISE(ABORT, 'injected_bundle_packet_failure');
                        END
                        """
                    )
                    connection.commit()
                with (
                    patch.object(service, "SQLITE_META_PATH", meta_path),
                    patch.object(task_service, "SQLITE_META_PATH", meta_path),
                    patch.object(
                        service,
                        "validate_tushare_full_market_production_version",
                        return_value=_provider(),
                    ),
                ):
                    with self.assertRaises(sqlite3.IntegrityError):
                        service.run_full_market_factor_radar_map_reduce_request(
                            {"effective_dated_industry_membership_digest": "e" * 64},
                            evidence_root=root,
                            meta_path=meta_path,
                        )
                store = SQLiteMetaStore(meta_path, read_only=True)
                self.assertIsNone(store.read_packet(service.FACTOR_REQUEST_PACKET_KEY))
                self.assertIsNone(store.read_packet(service.RADAR_REQUEST_PACKET_KEY))
                self.assertIsNone(store.read_packet(service.COORDINATOR_PACKET_KEY))
                self.assertEqual(store.list_task_metadata(), [])
                with sqlite3.connect(meta_path) as connection:
                    history_count = connection.execute(
                        "SELECT COUNT(*) FROM task_status_history"
                    ).fetchone()[0]
                self.assertEqual(history_count, 0)

    def test_packet_and_task_bundle_rolls_back_on_each_task_write_failure(self):
        for blocked_task_type in (
            service.FACTOR_TASK_TYPE,
            service.RADAR_TASK_TYPE,
            service.COORDINATOR_TASK_TYPE,
        ):
            with (
                self.subTest(task_type=blocked_task_type),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp)
                meta_path = root / "meta.sqlite"
                SQLiteMetaStore(meta_path)
                with sqlite3.connect(meta_path) as connection:
                    connection.execute(
                        f"""
                        CREATE TRIGGER fail_bundle_task
                        BEFORE INSERT ON task_status
                        WHEN json_extract(NEW.payload_json, '$.task_type') = '{blocked_task_type}'
                        BEGIN
                            SELECT RAISE(ABORT, 'injected_bundle_task_failure');
                        END
                        """
                    )
                    connection.commit()
                with (
                    patch.object(service, "SQLITE_META_PATH", meta_path),
                    patch.object(task_service, "SQLITE_META_PATH", meta_path),
                    patch.object(
                        service,
                        "validate_tushare_full_market_production_version",
                        return_value=_provider(),
                    ),
                ):
                    with self.assertRaises(sqlite3.IntegrityError):
                        service.run_full_market_factor_radar_map_reduce_request(
                            {"effective_dated_industry_membership_digest": "e" * 64},
                            evidence_root=root,
                            meta_path=meta_path,
                        )
                store = SQLiteMetaStore(meta_path, read_only=True)
                self.assertIsNone(store.read_packet(service.FACTOR_REQUEST_PACKET_KEY))
                self.assertIsNone(store.read_packet(service.RADAR_REQUEST_PACKET_KEY))
                self.assertIsNone(store.read_packet(service.COORDINATOR_PACKET_KEY))
                self.assertEqual(store.list_task_metadata(), [])
                with sqlite3.connect(meta_path) as connection:
                    history_count = connection.execute(
                        "SELECT COUNT(*) FROM task_status_history"
                    ).fetchone()[0]
                self.assertEqual(history_count, 0)

    def test_packet_and_task_bundle_rolls_back_on_each_history_write_failure(self):
        for blocked_task_type in (
            service.FACTOR_TASK_TYPE,
            service.RADAR_TASK_TYPE,
            service.COORDINATOR_TASK_TYPE,
        ):
            with (
                self.subTest(task_type=blocked_task_type),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp)
                meta_path = root / "meta.sqlite"
                SQLiteMetaStore(meta_path)
                with sqlite3.connect(meta_path) as connection:
                    connection.execute(
                        f"""
                        CREATE TRIGGER fail_bundle_history
                        BEFORE INSERT ON task_status_history
                        WHEN NEW.task_type = '{blocked_task_type}'
                        BEGIN
                            SELECT RAISE(ABORT, 'injected_bundle_history_failure');
                        END
                        """
                    )
                    connection.commit()
                with (
                    patch.object(service, "SQLITE_META_PATH", meta_path),
                    patch.object(task_service, "SQLITE_META_PATH", meta_path),
                    patch.object(
                        service,
                        "validate_tushare_full_market_production_version",
                        return_value=_provider(),
                    ),
                ):
                    with self.assertRaises(sqlite3.IntegrityError):
                        service.run_full_market_factor_radar_map_reduce_request(
                            {"effective_dated_industry_membership_digest": "e" * 64},
                            evidence_root=root,
                            meta_path=meta_path,
                        )
                with sqlite3.connect(meta_path) as connection:
                    counts = [
                        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        for table in ("packets", "task_status", "task_status_history")
                    ]
                self.assertEqual(counts, [0, 0, 0])

    def test_idempotent_reuse_fails_closed_on_corrupt_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta_path = root / "meta.sqlite"
            payload = {"effective_dated_industry_membership_digest": "e" * 64}
            with (
                patch.object(service, "SQLITE_META_PATH", meta_path),
                patch.object(task_service, "SQLITE_META_PATH", meta_path),
                patch.object(
                    service,
                    "validate_tushare_full_market_production_version",
                    return_value=_provider(),
                ),
            ):
                first = service.run_full_market_factor_radar_map_reduce_request(
                    payload, evidence_root=root, meta_path=meta_path
                )
                with sqlite3.connect(meta_path) as connection:
                    connection.execute(
                        """
                        UPDATE task_status_history
                        SET payload_digest = ?
                        WHERE task_id = ?
                        """,
                        ("0" * 64, first["task_id"]),
                    )
                    connection.commit()
                with self.assertRaisesRegex(
                    RuntimeError, "idempotent_bundle_history_binding_invalid"
                ):
                    service.run_full_market_factor_radar_map_reduce_request(
                        payload, evidence_root=root, meta_path=meta_path
                    )
            with sqlite3.connect(meta_path) as connection:
                counts = [
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ("packets", "task_status", "task_status_history")
                ]
            self.assertEqual(counts, [3, 3, 3])

    def test_idempotent_reuse_rejects_corrupt_terminal_task_wrapper(self):
        attacks = (
            "invalid_created_at",
            "missing_finished_at",
            "empty_status_history",
            "external_task_log",
        )
        payload = {"effective_dated_industry_membership_digest": "e" * 64}
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                meta_path = root / "meta.sqlite"
                with (
                    patch.object(service, "SQLITE_META_PATH", meta_path),
                    patch.object(task_service, "SQLITE_META_PATH", meta_path),
                    patch.object(
                        service,
                        "validate_tushare_full_market_production_version",
                        return_value=_provider(),
                    ),
                ):
                    first = service.run_full_market_factor_radar_map_reduce_request(
                        payload, evidence_root=root, meta_path=meta_path
                    )
                    with sqlite3.connect(meta_path) as connection:
                        row = connection.execute(
                            "SELECT payload_json FROM task_status WHERE task_id = ?",
                            (first["task_id"],),
                        ).fetchone()
                        task = json.loads(str(row[0]))
                        if attack == "invalid_created_at":
                            task["created_at"] = "not-a-time"
                        elif attack == "missing_finished_at":
                            task["finished_at"] = None
                        elif attack == "empty_status_history":
                            task["status_history"] = []
                        else:
                            task["task_log"] = [{"external_calls_triggered": True}]
                        task_json = json.dumps(
                            task,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        task_digest = hashlib.sha256(
                            task_json.encode("utf-8")
                        ).hexdigest()
                        connection.execute(
                            "UPDATE task_status SET payload_json = ? WHERE task_id = ?",
                            (task_json, first["task_id"]),
                        )
                        connection.execute(
                            """
                            UPDATE task_status_history
                            SET payload_json = ?, payload_digest = ?
                            WHERE task_id = ?
                            """,
                            (task_json, task_digest, first["task_id"]),
                        )
                        connection.commit()
                    with self.assertRaisesRegex(
                        RuntimeError, "idempotent_bundle_task_binding_invalid"
                    ):
                        service.run_full_market_factor_radar_map_reduce_request(
                            payload, evidence_root=root, meta_path=meta_path
                        )
                with sqlite3.connect(meta_path) as connection:
                    counts = tuple(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {table}"
                        ).fetchone()[0]
                        for table in (
                            "packets",
                            "task_status",
                            "task_status_history",
                        )
                    )
                self.assertEqual(counts, (3, 3, 3))

    def test_task_catalog_exposes_only_the_local_request_boundary(self):
        row = next(
            item
            for item in task_service.TASK_CATALOG
            if item.get("task_type") == service.COORDINATOR_TASK_TYPE
        )
        self.assertEqual(
            row["route"],
            "POST /api/worker/full-market-factor-radar-map-reduce-request",
        )
        self.assertTrue(row["button_gated"])
        self.assertEqual(row["possible_external_sources"], [])
        self.assertFalse(row["provider_refresh_executed"])
        self.assertFalse(row["worker_execution_triggered"])
        self.assertFalse(row["production_complete"])
        self.assertFalse(row["cache_get_external_calls"])
        self.assertTrue(row["factor_and_radar_outputs_are_independent"])


class FullMarketResearchProducerIndustryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        _install_semantic_authority(self.stack)

    def tearDown(self) -> None:
        self.stack.close()

    def test_real_pointer_binds_both_producer_requests_end_to_end(self) -> None:
        symbols = _industry_symbols()
        provider = {
            "ready": True,
            "status": "production_version_verified",
            "blockers": [],
            "scope_hash": "a" * 64,
            "version_digest": "b" * 64,
            "universe_digest": service._digest(symbols),
            "artifact_manifest_digest": "d" * 64,
            "universe_count": len(symbols),
            "validated_trade_date": "20260717",
            "symbols": symbols,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_evidence(root, symbols)
            with patch.object(
                service,
                "validate_tushare_full_market_production_version",
                return_value=provider,
            ):
                contract = service.build_full_market_factor_radar_map_reduce_contract(
                    {}, evidence_root=root
                )
                factor, radar = _request_pair(contract)
                audit = service.validate_independent_output_requests(
                    factor, radar, evidence_root=root
                )

        shared = contract["shared_scope_material"]
        self.assertTrue(contract["execution_request_scope_ready"], contract["blockers"])
        self.assertTrue(shared["effective_dated_industry_membership_verified"])
        self.assertEqual(
            shared["industry_input_digest"],
            service._digest(
                {
                    key: shared[key]
                    for key in service.INDUSTRY_BINDING_DIGEST_KEYS
                }
            ),
        )
        for key in service.INDUSTRY_BINDING_DIGEST_KEYS:
            self.assertEqual(factor[key], shared[key])
            self.assertEqual(radar[key], shared[key])
        self.assertEqual(
            factor["factor_batch_input_digest"],
            shared["full_market_batch_input_digest"],
        )
        self.assertEqual(
            radar["radar_full_market_input_digest"],
            shared["full_market_batch_input_digest"],
        )
        self.assertTrue(audit["ready"], audit["blockers"])


if __name__ == "__main__":
    unittest.main()
