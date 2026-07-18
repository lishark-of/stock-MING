from __future__ import annotations

import tempfile
import unittest
import uuid
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from server.main import app
from server.services import full_market_research_producer_service as producer
from server.services import full_market_worker_service as worker
from server.services import task_service
from storage import parquet_store
from storage.sqlite_meta import SQLiteMetaStore


HEAD = "a" * 40
REQUEST_BUNDLE = "b" * 64
WORKER_ATTESTATION = "c" * 64
WORKER_ARTIFACT = "d" * 64
VALIDATED_DATE = "20260710"


def _symbols(count: int = 3000) -> list[str]:
    values = [f"{600000 + index:06d}.SH" for index in range(count)]
    return sorted(values)


def _industry_rows(symbols: list[str]) -> list[dict[str, object]]:
    return [
        {
            "effective_from": "20200101",
            "effective_to": None,
            "industry_code": f"I{index % 10:02d}",
            "source_api": "index_member_all",
            "ts_code": symbol,
        }
        for index, symbol in enumerate(symbols)
    ]


def _factor_rows(symbols: list[str]) -> list[dict[str, object]]:
    midpoint = (len(symbols) - 1) / 2.0
    return [
        {
            "ts_code": symbol,
            "data_date": VALIDATED_DATE,
            "cross_sectional_rank": index + 1,
            "cross_sectional_zscore": (index - midpoint) / max(1.0, len(symbols) / 3.0),
            "industry_code": f"I{index % 10:02d}",
            "industry_neutral_score": -1.0 if (index // 10) % 2 == 0 else 1.0,
            "market_cap": float(1000 + index),
            "size_neutral_score": -1.0 if index % 2 == 0 else 1.0,
            "combined_factor_score": (index - midpoint) / max(1.0, len(symbols)),
            "provider_version_digest": "e" * 64,
            "industry_pointer_digest": "f" * 64,
            "factor_batch_input_digest": "0" * 64,
            "source_dataset_digest": "1" * 64,
            "pit_validated": True,
            "research_only": True,
            "does_not_execute_trades": True,
        }
        for index, symbol in enumerate(symbols)
    ]


class FactorComputationTests(unittest.TestCase):
    def test_real_cross_sectional_computation_passes_metric_audit(self) -> None:
        symbols = _symbols(60)
        daily_rows: list[dict[str, object]] = []
        basic_rows: list[dict[str, object]] = []
        for symbol_index, symbol in enumerate(symbols):
            for day in range(21):
                daily_rows.append(
                    {
                        "ts_code": symbol,
                        "trade_date": f"202606{10 + day:02d}",
                        "close": 10.0 + symbol_index * 0.03 + day * (0.01 + symbol_index * 0.0002),
                        "amount": 1000.0 + symbol_index * 13.0 + day,
                    }
                )
            basic_rows.append(
                {
                    "ts_code": symbol,
                    "trade_date": "20260630",
                    "total_mv": 10000.0 + symbol_index * symbol_index * 7.0 + symbol_index,
                    "pb": 0.8 + symbol_index * 0.025,
                }
            )
        rows = producer._compute_factor_rows(
            {"daily": pd.DataFrame(daily_rows), "daily_basic": pd.DataFrame(basic_rows)},
            symbols=symbols,
            validated_trade_date="20260630",
            industry_rows=_industry_rows(symbols),
            provider_version_digest="e" * 64,
            industry_pointer_digest="f" * 64,
            factor_batch_input_digest="0" * 64,
            source_dataset_digest="1" * 64,
        )
        audit = worker._factor_metric_validation_audit(
            rows,
            universe_digest=producer._digest(symbols),
            result_output_hash=producer._digest(rows),
        )
        self.assertEqual(len(rows), len(symbols))
        self.assertTrue(audit["ready"], audit["blockers"])
        self.assertEqual(sorted(int(row["cross_sectional_rank"]) for row in rows), list(range(1, 61)))
        self.assertTrue(all(row["pit_validated"] is True for row in rows))


class FactorExecutorTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
        symbols = _symbols()
        industry_rows = _industry_rows(symbols)
        industry_binding = {
            "industry_scope_digest": "2" * 64,
            "industry_source_version_digest": "3" * 64,
            "industry_artifact_sha256": "4" * 64,
            "industry_manifest_digest": "5" * 64,
            "industry_pointer_digest": "f" * 64,
            "industry_semantic_evidence_sha256": "6" * 64,
        }
        industry_input_digest = producer._digest(industry_binding)
        universe = {
            "ready": True,
            "symbols": symbols,
            "universe_count": len(symbols),
            "universe_digest": producer._digest(symbols),
            "scope_hash": "7" * 64,
            "version_digest": "e" * 64,
            "validated_trade_date": VALIDATED_DATE,
            "frames": {
                "daily": pd.DataFrame([{"ts_code": symbols[0], "trade_date": VALIDATED_DATE, "close": 1.0, "amount": 1.0}]),
                "daily_basic": pd.DataFrame([{"ts_code": symbols[0], "trade_date": VALIDATED_DATE, "total_mv": 1.0, "pb": 1.0}]),
            },
        }
        factor_batch_digest = producer._digest(
            {
                "provider_scope_hash": universe["scope_hash"],
                "provider_version_digest": universe["version_digest"],
                "universe_digest": universe["universe_digest"],
                "validated_trade_date": universe["validated_trade_date"],
                "symbols": symbols,
                "industry_binding": industry_binding,
                "industry_input_digest": industry_input_digest,
            }
        )
        source_dataset_digest = producer._digest(
            {
                name: producer._frame_records(universe["frames"][name], symbols=symbols)
                for name in ("daily", "daily_basic")
            }
        )
        factor_request = {
            "head_full": HEAD,
            "request_bundle_id": REQUEST_BUNDLE,
            "task_id": "local-123456789abc",
            "target_dataset": producer.FACTOR_TARGET_DATASET,
            "output_contract_digest": producer.FACTOR_OUTPUT_CONTRACT_DIGEST,
            "factor_batch_input_digest": factor_batch_digest,
        }
        store = SQLiteMetaStore(root / "meta.sqlite")
        store.write_packet(producer.FACTOR_REQUEST_PACKET_KEY, factor_request)
        store.write_packet(producer.RADAR_REQUEST_PACKET_KEY, {"request_bundle_id": REQUEST_BUNDLE})
        payload = {
            "approved_by_user": True,
            "head_full": HEAD,
            "acceptance_run_id": uuid.uuid4().hex,
            "request_bundle_id": REQUEST_BUNDLE,
            "factor_task_id": factor_request["task_id"],
            "worker_attestation_id": WORKER_ATTESTATION,
            "worker_run_id": uuid.uuid4().hex,
        }
        industry = {
            "ready": True,
            "scope_digest": industry_binding["industry_scope_digest"],
            "source_version_digest": industry_binding[
                "industry_source_version_digest"
            ],
            "artifact_sha256": industry_binding["industry_artifact_sha256"],
            "manifest_digest": industry_binding["industry_manifest_digest"],
            "pointer_digest": industry_binding["industry_pointer_digest"],
            "semantic_evidence_sha256": industry_binding[
                "industry_semantic_evidence_sha256"
            ],
        }
        return payload, {
            "universe": universe,
            "industry": industry,
            "factor_batch_input_digest": factor_batch_digest,
            "source_dataset_digest": source_dataset_digest,
        }, industry_rows

    @staticmethod
    def _bound_rows(fixture: dict[str, object]) -> list[dict[str, object]]:
        rows = _factor_rows(_symbols())
        for row in rows:
            row["factor_batch_input_digest"] = fixture["factor_batch_input_digest"]
            row["source_dataset_digest"] = fixture["source_dataset_digest"]
        return rows

    def _patches(self, fixture: dict[str, object], industry_rows: list[dict[str, object]], rows: list[dict[str, object]]):
        return (
            patch.object(producer, "_repository_state", return_value={"head_full": HEAD, "clean": True}),
            patch.object(producer, "validate_independent_output_requests", return_value={"ready": True}),
            patch.object(
                producer,
                "_worker_trust_binding",
                return_value={
                    "ready": True,
                    "attestation_id": WORKER_ATTESTATION,
                    "artifact_digest": WORKER_ARTIFACT,
                    "scope_hash": "7" * 64,
                    "claims": {
                        "row_count": 3000,
                        "provider_version_digest": "e" * 64,
                        "universe_digest": fixture["universe"]["universe_digest"],
                        "validated_trade_date": VALIDATED_DATE,
                    },
                },
            ),
            patch.object(producer, "validate_tushare_full_market_production_version", return_value=fixture["universe"]),
            patch.object(producer, "validate_full_market_industry_membership", return_value=fixture["industry"]),
            patch.object(producer, "_industry_rows", return_value=(industry_rows, producer._digest(industry_rows))),
            patch.object(producer, "_compute_factor_rows", return_value=rows),
        )

    def test_executor_persists_factor_dataset_packet_and_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, fixture, industry_rows = self._fixture(root)
            rows = self._bound_rows(fixture)
            with ExitStack() as stack:
                for patcher in self._patches(fixture, industry_rows, rows):
                    stack.enter_context(patcher)
                result = producer.execute_full_market_factor_research(payload, evidence_root=root)

            self.assertTrue(result["ready"], result.get("blockers"))
            self.assertTrue(result["writes_storage"])
            self.assertFalse(result["external_calls_triggered"])
            pointer = parquet_store.versioned_dataset_pointer(
                root=root / "parquet", name=producer.FACTOR_TARGET_DATASET, pointer="current"
            )
            self.assertEqual(pointer["status"], "ready")
            self.assertEqual(pointer["row_count"], 3000)
            store = SQLiteMetaStore(root / "meta.sqlite", read_only=True)
            packet = store.read_packet(producer.FACTOR_TARGET_PACKET_KEY)
            self.assertEqual(packet, store.read_packet(f"{producer.FACTOR_TARGET_PACKET_KEY}_last_good"))
            self.assertEqual(packet["source_request_bundle_id"], REQUEST_BUNDLE)
            self.assertEqual(packet["result_artifact_sha256"], pointer["artifact_sha256"])
            self.assertTrue(packet["metric_validation_audit"]["ready"])
            self.assertIsNotNone(store.read_task_status(payload["acceptance_run_id"]))

    def test_strict_approval_and_head_fail_before_any_write(self) -> None:
        for approval, head in ((1, HEAD), (True, "9" * 40)):
            with self.subTest(approval=approval, head=head), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                payload = {
                    "approved_by_user": approval,
                    "head_full": head,
                    "acceptance_run_id": uuid.uuid4().hex,
                    "request_bundle_id": REQUEST_BUNDLE,
                    "factor_task_id": "local-123456789abc",
                    "worker_attestation_id": WORKER_ATTESTATION,
                    "worker_run_id": uuid.uuid4().hex,
                }
                with patch.object(producer, "_repository_state", return_value={"head_full": HEAD, "clean": True}):
                    result = producer.execute_full_market_factor_research(payload, evidence_root=root)
                self.assertFalse(result["ready"])
                self.assertFalse(result["writes_storage"])
                self.assertFalse((root / "meta.sqlite").exists())
                self.assertFalse((root / "parquet").exists())

    def test_sqlite_failure_rolls_back_all_parquet_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, fixture, industry_rows = self._fixture(root)
            rows = self._bound_rows(fixture)
            patches = self._patches(fixture, industry_rows, rows)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patch.object(
                SQLiteMetaStore,
                "write_packet_task_bundle_atomic",
                side_effect=RuntimeError("injected"),
            ):
                result = producer.execute_full_market_factor_research(payload, evidence_root=root)
            self.assertFalse(result["ready"])
            dataset_root = root / "parquet" / producer.FACTOR_TARGET_DATASET
            self.assertFalse((dataset_root / "current.json").exists())
            self.assertFalse((dataset_root / "last_good.json").exists())
            self.assertFalse((dataset_root / "manifest.json").exists())
            self.assertEqual(list((dataset_root / "versions").glob("*.parquet")), [])
            self.assertFalse(producer._factor_execution_journal_path(root).exists())

    def test_concurrent_identical_posts_serialize_and_reuse_one_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, fixture, industry_rows = self._fixture(root)
            rows = self._bound_rows(fixture)
            with ExitStack() as stack:
                for patcher in self._patches(fixture, industry_rows, rows):
                    stack.enter_context(patcher)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(
                        pool.map(
                            lambda _: producer.execute_full_market_factor_research(
                                payload, evidence_root=root
                            ),
                            range(2),
                        )
                    )
            self.assertTrue(all(result["ready"] for result in results), results)
            versions = list(
                (
                    root
                    / "parquet"
                    / producer.FACTOR_TARGET_DATASET
                    / "versions"
                ).glob("*.parquet")
            )
            self.assertEqual(len(versions), 1)
            self.assertFalse(producer._factor_execution_journal_path(root).exists())

    def test_committed_journal_finalize_crash_recovers_on_next_explicit_post(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, fixture, industry_rows = self._fixture(root)
            rows = self._bound_rows(fixture)
            original_write = producer._write_factor_execution_journal
            call_count = 0

            def crash_on_finalize(write_root, journal):
                nonlocal call_count
                call_count += 1
                if call_count == 3:
                    raise RuntimeError("injected_finalize_crash")
                return original_write(write_root, journal)

            with ExitStack() as stack:
                for patcher in self._patches(fixture, industry_rows, rows):
                    stack.enter_context(patcher)
                stack.enter_context(
                    patch.object(
                        producer,
                        "_write_factor_execution_journal",
                        side_effect=crash_on_finalize,
                    )
                )
                interrupted = producer.execute_full_market_factor_research(
                    payload, evidence_root=root
                )
                recovered = producer.execute_full_market_factor_research(
                    payload, evidence_root=root
                )
            self.assertEqual(
                interrupted["status"],
                "factor_full_market_executor_commit_recovery_required",
            )
            self.assertTrue(interrupted["writes_storage"])
            self.assertTrue(recovered["ready"], recovered)
            self.assertFalse(producer._factor_execution_journal_path(root).exists())
            pointer = parquet_store.versioned_dataset_pointer(
                root=root / "parquet",
                name=producer.FACTOR_TARGET_DATASET,
                pointer="current",
            )
            packet = SQLiteMetaStore(root / "meta.sqlite", read_only=True).read_packet(
                producer.FACTOR_TARGET_PACKET_KEY
            )
            self.assertEqual(pointer["version_id"], packet["result_version_id"])
            self.assertEqual(
                pointer["artifact_sha256"], packet["result_artifact_sha256"]
            )

    def test_nested_factor_dataset_symlink_is_rejected_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            parquet = root / "parquet"
            parquet.mkdir()
            (parquet / producer.FACTOR_TARGET_DATASET).symlink_to(outside)
            payload = {
                "approved_by_user": True,
                "head_full": HEAD,
                "acceptance_run_id": uuid.uuid4().hex,
                "request_bundle_id": REQUEST_BUNDLE,
                "factor_task_id": "local-123456789abc",
                "worker_attestation_id": WORKER_ATTESTATION,
                "worker_run_id": uuid.uuid4().hex,
            }
            with patch.object(
                producer,
                "_repository_state",
                return_value={"head_full": HEAD, "clean": True},
            ):
                result = producer.execute_full_market_factor_research(
                    payload, evidence_root=root
                )
            self.assertFalse(result["ready"])
            self.assertEqual(list(outside.iterdir()), [])

    def test_external_worker_provider_identity_mismatch_matrix_fails_before_promotion(self) -> None:
        cases = {
            "scope_hash": "8" * 64,
            "provider_version_digest": "9" * 64,
            "universe_digest": "0" * 64,
            "validated_trade_date": "20260709",
        }
        for field, bad_value in cases.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                payload, fixture, industry_rows = self._fixture(root)
                rows = self._bound_rows(fixture)
                patchers = self._patches(fixture, industry_rows, rows)
                trust = {
                    "ready": True,
                    "attestation_id": WORKER_ATTESTATION,
                    "artifact_digest": WORKER_ARTIFACT,
                    "scope_hash": "7" * 64,
                    "claims": {
                        "row_count": 3000,
                        "provider_version_digest": "e" * 64,
                        "universe_digest": fixture["universe"]["universe_digest"],
                        "validated_trade_date": VALIDATED_DATE,
                    },
                }
                if field == "scope_hash":
                    trust[field] = bad_value
                else:
                    trust["claims"][field] = bad_value
                with ExitStack() as stack:
                    for index, patcher in enumerate(patchers):
                        if index != 2:
                            stack.enter_context(patcher)
                    stack.enter_context(
                        patch.object(
                            producer,
                            "_worker_trust_binding",
                            return_value=trust,
                        )
                    )
                    result = producer.execute_full_market_factor_research(
                        payload, evidence_root=root
                    )
                self.assertFalse(result["ready"])
                self.assertIn(
                    "factor_executor_worker_provider_scope_or_count_mismatch",
                    result["blockers"],
                )
                self.assertFalse((root / "parquet").exists())

    def test_route_is_post_only_and_cataloged(self) -> None:
        safe_result = {
            "ready": False,
            "status": "factor_full_market_executor_blocked",
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }
        with patch.object(
            producer,
            "execute_full_market_factor_research",
            return_value=safe_result,
        ):
            client = TestClient(app)
            get_response = client.get("/api/worker/full-market-factor-execution")
            post_response = client.post(
                "/api/worker/full-market-factor-execution", json={}
            )
        self.assertEqual(get_response.status_code, 405)
        self.assertEqual(post_response.status_code, 200)
        self.assertFalse(post_response.json()["data"]["external_calls_triggered"])
        row = next(
            item
            for item in task_service.TASK_CATALOG
            if item.get("task_type") == producer.FACTOR_EXECUTION_TASK_TYPE
        )
        self.assertEqual(row["route"], "POST /api/worker/full-market-factor-execution")
        self.assertTrue(row["button_gated"])
        self.assertEqual(row["possible_external_sources"], [])
        self.assertFalse(row["provider_refresh_executed"])
        self.assertFalse(row["worker_execution_triggered"])
        self.assertFalse(row["production_complete"])


if __name__ == "__main__":
    unittest.main()
