from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from server.services import full_market_research_producer_service as service
from server.services import task_service
from storage.sqlite_meta import SQLiteMetaStore


def _provider(*, count: int = 3000) -> dict:
    return {
        "ready": True,
        "status": "production_version_verified",
        "blockers": [],
        "scope_hash": "a" * 64,
        "version_digest": "b" * 64,
        "universe_digest": "c" * 64,
        "artifact_manifest_digest": "d" * 64,
        "universe_count": count,
        "validated_trade_date": "20260717",
        "symbols": [f"{600000 + index:06d}.SH" for index in range(count)],
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
    factor["task_id"] = "local-" + "1" * 12
    radar["task_id"] = "local-" + "2" * 12
    factor["packet_digest"] = service._digest(
        {key: value for key, value in factor.items() if key != "packet_digest"}
    )
    radar["packet_digest"] = service._digest(
        {key: value for key, value in radar.items() if key != "packet_digest"}
    )
    return factor, radar


class FullMarketResearchProducerTests(unittest.TestCase):
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
        self.assertFalse(
            contract["shared_scope_material"][
                "effective_dated_industry_membership_verified"
            ]
        )
        self.assertIn(
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
            "9" * 64,
        )
        self.assertFalse(contract["execution_request_ready"])
        self.assertFalse(contract["production_prerequisites_ready"])
        self.assertIn(
            "authoritative_effective_dated_industry_membership_missing",
            contract["blockers"],
        )

    def test_missing_effective_dated_industry_digest_blocks_shared_dispatch(self):
        with patch.object(
            service,
            "validate_tushare_full_market_production_version",
            return_value=_provider(),
        ):
            contract = service.build_full_market_factor_radar_map_reduce_contract({})

        self.assertFalse(contract["execution_request_ready"])
        self.assertIn(
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
        tampered["packet_digest"] = service._digest(
            {key: value for key, value in tampered.items() if key != "packet_digest"}
        )
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
            "fake_industry_verified": ("effective_dated_industry_membership_verified", True),
        }
        for name, (field, value) in attacks.items():
            with self.subTest(name=name):
                tampered = dict(radar)
                tampered[field] = value
                tampered["packet_digest"] = service._digest(
                    {key: item for key, item in tampered.items() if key != "packet_digest"}
                )
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
        missing_head["packet_digest"] = service._digest(
            {key: item for key, item in missing_head.items() if key != "packet_digest"}
        )
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
            forged["packet_digest"] = service._digest(
                {key: value for key, value in forged.items() if key != "packet_digest"}
            )
            self.assertFalse(
                service.validate_independent_output_requests(forged, radar)["ready"]
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


if __name__ == "__main__":
    unittest.main()
