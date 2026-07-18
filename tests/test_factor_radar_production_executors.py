from __future__ import annotations

import tempfile
import sqlite3
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


def _radar_symbols() -> list[str]:
    return sorted(
        [f"{600000 + index:06d}.SH" for index in range(1000)]
        + [f"{index:06d}.SZ" for index in range(1000)]
        + [f"{430000 + index:06d}.BJ" for index in range(1000)]
    )


def _worker_rows(symbols: list[str]) -> list[dict[str, object]]:
    return [
        {
            "ts_code": symbol,
            "data_date": VALIDATED_DATE,
            "score": 100 - (index % 101),
            "rough_score": 80 - (index % 31),
            "risk_score": index % 17,
            "full_market_rank": index + 1,
            "trigger_conditions_json": '["量价确认","趋势延续"]',
            "invalid_conditions_json": '["跌破支撑"]',
            "candidate_is_not_buy_instruction": True,
            "does_not_execute_trades": True,
        }
        for index, symbol in enumerate(symbols)
    ]


class RadarAuthoritativeCacheWriterTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[dict[str, object], dict[str, object]]:
        symbols = _radar_symbols()
        rows = _worker_rows(symbols)
        run_id = uuid.uuid4().hex
        promotion = parquet_store.atomic_promote_versioned_dataset(
            pd.DataFrame(rows),
            root=root / "parquet",
            name=worker.RESULT_DATASET,
            version_id=f"fmw-{run_id}",
            lineage={"head_full": HEAD, "acceptance_run_id": run_id},
        )
        self.assertTrue(promotion["atomic_promoted"])
        packet = {
            "schema_version": worker.SCHEMA_VERSION,
            "status": "full_market_worker_production_complete",
            "head_full": HEAD,
            "acceptance_run_id": run_id,
            "provider_scope_hash": "7" * 64,
            "provider_version_digest": "8" * 64,
            "universe_digest": worker._canonical_digest(symbols),
            "universe_count": len(symbols),
            "validated_trade_date": VALIDATED_DATE,
            "result_dataset": worker.RESULT_DATASET,
            "result_version_id": promotion["version_id"],
            "result_artifact_sha256": promotion["artifact_sha256"],
            "result_output_hash": worker._canonical_digest(rows),
            "result_row_count": len(rows),
            "candidate_is_not_buy_instruction": True,
            "does_not_execute_trades": True,
        }
        SQLiteMetaStore(root / "meta.sqlite").write_packet(worker.PACKET_KEY, packet)
        payload = {
            "approved_by_user": True,
            "head_full": HEAD,
            "cache_write_task_id": uuid.uuid4().hex,
            "worker_attestation_id": WORKER_ATTESTATION,
            "worker_run_id": run_id,
            "browser_visual_evidence_digest": "9" * 64,
            "browser_performance_evidence_digest": "a" * 64,
            "legacy_retirement_evidence_digest": "b" * 64,
        }
        trust = {
            "ready": True,
            "attestation_id": WORKER_ATTESTATION,
            "artifact_digest": WORKER_ARTIFACT,
            "generation": packet["result_version_id"],
            "artifact_file_digest": packet["result_artifact_sha256"],
            "scope_hash": packet["provider_scope_hash"],
            "claims": {"row_count": len(rows)},
        }
        return payload, trust

    def test_writer_persists_exact_cache_task_and_reuses_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, trust = self._fixture(root)
            with (
                patch.object(worker, "_repository_clean_at_head", return_value=True),
                patch.object(worker, "_trusted_worker_consumer_binding", return_value=trust),
            ):
                first = worker.publish_candidate_radar_authoritative_cache(
                    payload, evidence_root=root
                )
                second = worker.publish_candidate_radar_authoritative_cache(
                    payload, evidence_root=root
                )
            self.assertTrue(first["ready"], first.get("blockers"))
            self.assertTrue(first["writes_storage"])
            self.assertEqual(second["status"], "candidate_radar_authoritative_cache_write_reused")
            self.assertFalse(second["writes_storage"])
            store = SQLiteMetaStore(root / "meta.sqlite", read_only=True)
            packet = store.read_packet(worker.CANDIDATE_CACHE_PACKET_KEY)
            self.assertEqual(
                packet,
                store.read_packet(worker.CANDIDATE_CACHE_LAST_GOOD_PACKET_KEY),
            )
            self.assertEqual(len(packet["candidate_rows"]), 3000)
            self.assertEqual(
                sorted(row["full_market_rank"] for row in packet["candidate_rows"]),
                list(range(1, 3001)),
            )
            task = store.read_task_status(payload["cache_write_task_id"])
            self.assertEqual(task["acceptance_run_id"], payload["worker_run_id"])
            self.assertEqual(task["task_type"], worker.RADAR_CACHE_WRITE_TASK_TYPE)
            self.assertFalse(first["candidate_radar_production_replacement"])
            self.assertTrue(first["external_radar_attestation_pending"])
            connection = sqlite3.connect(root / "meta.sqlite")
            connection.execute(
                "DELETE FROM packets WHERE packet_key = ?",
                (worker.CANDIDATE_CACHE_LAST_GOOD_PACKET_KEY,),
            )
            connection.commit()
            connection.close()
            with (
                patch.object(worker, "_repository_clean_at_head", return_value=True),
                patch.object(worker, "_trusted_worker_consumer_binding", return_value=trust),
            ):
                missing_last_good = worker.publish_candidate_radar_authoritative_cache(
                    payload, evidence_root=root
                )
            self.assertFalse(missing_last_good["ready"])
            self.assertNotEqual(
                missing_last_good["status"],
                "candidate_radar_authoritative_cache_write_reused",
            )

    def test_strict_bool_and_worker_artifact_tamper_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "approved_by_user": 1,
                "head_full": HEAD,
                "cache_write_task_id": uuid.uuid4().hex,
                "worker_attestation_id": WORKER_ATTESTATION,
                "worker_run_id": uuid.uuid4().hex,
                "browser_visual_evidence_digest": "9" * 64,
                "browser_performance_evidence_digest": "a" * 64,
                "legacy_retirement_evidence_digest": "b" * 64,
            }
            with patch.object(worker, "_repository_clean_at_head", return_value=True):
                result = worker.publish_candidate_radar_authoritative_cache(
                    payload, evidence_root=root
                )
            self.assertFalse(result["ready"])
            self.assertFalse((root / "meta.sqlite").exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, trust = self._fixture(root)
            store = SQLiteMetaStore(root / "meta.sqlite")
            packet = store.read_packet(worker.PACKET_KEY)
            packet["result_output_hash"] = "0" * 64
            store.write_packet(worker.PACKET_KEY, packet)
            with (
                patch.object(worker, "_repository_clean_at_head", return_value=True),
                patch.object(worker, "_trusted_worker_consumer_binding", return_value=trust),
            ):
                result = worker.publish_candidate_radar_authoritative_cache(
                    payload, evidence_root=root
                )
            self.assertFalse(result["ready"])
            self.assertIsNone(
                SQLiteMetaStore(root / "meta.sqlite", read_only=True).read_packet(
                    worker.CANDIDATE_CACHE_PACKET_KEY
                )
            )

    def test_atomic_write_failure_never_leaves_candidate_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, trust = self._fixture(root)
            with (
                patch.object(worker, "_repository_clean_at_head", return_value=True),
                patch.object(worker, "_trusted_worker_consumer_binding", return_value=trust),
                patch.object(
                    SQLiteMetaStore,
                    "promote_packet_pair_task_bundle_atomic",
                    side_effect=RuntimeError("injected"),
                ),
            ):
                result = worker.publish_candidate_radar_authoritative_cache(
                    payload, evidence_root=root
                )
            self.assertFalse(result["ready"])
            self.assertIsNone(
                SQLiteMetaStore(root / "meta.sqlite", read_only=True).read_packet(
                    worker.CANDIDATE_CACHE_PACKET_KEY
                )
            )

    def test_legacy_cache_is_replaced_atomically_and_concurrent_retry_reuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, trust = self._fixture(root)
            store = SQLiteMetaStore(root / "meta.sqlite")
            store.write_packet(
                worker.CANDIDATE_CACHE_PACKET_KEY,
                {
                    "packet_key": worker.CANDIDATE_CACHE_PACKET_KEY,
                    "status": "legacy_candidate_cache",
                    "candidate_rows": [],
                },
            )

            def publish() -> dict[str, object]:
                return worker.publish_candidate_radar_authoritative_cache(
                    payload, evidence_root=root
                )

            with (
                patch.object(worker, "_repository_clean_at_head", return_value=True),
                patch.object(worker, "_trusted_worker_consumer_binding", return_value=trust),
                ThreadPoolExecutor(max_workers=2) as pool,
            ):
                results = [future.result() for future in [pool.submit(publish), pool.submit(publish)]]

            self.assertEqual(sum(result.get("writes_storage") is True for result in results), 1)
            self.assertEqual(
                sum(
                    result.get("status")
                    == "candidate_radar_authoritative_cache_write_reused"
                    for result in results
                ),
                1,
            )
            current = store.read_packet(worker.CANDIDATE_CACHE_PACKET_KEY)
            last_good = store.read_packet(worker.CANDIDATE_CACHE_LAST_GOOD_PACKET_KEY)
            self.assertEqual(current, last_good)
            self.assertEqual(current.get("status"), "candidate_radar_full_market_replacement_ready")

    def test_worker_external_claims_bind_exact_provider_universe_and_date(self) -> None:
        packet = {
            "result_version_id": "worker-v1",
            "provider_scope_hash": "7" * 64,
            "result_artifact_sha256": "8" * 64,
            "provider_version_digest": "9" * 64,
            "universe_digest": "a" * 64,
            "validated_trade_date": VALIDATED_DATE,
            "result_row_count": 3000,
        }
        run_id = uuid.uuid4().hex
        attestation_id = "b" * 64
        consumer = {
            "ready": True,
            "production_trusted": True,
            "snapshot_rollback_resistant": True,
            "head_full": HEAD,
            "current_pointer": {
                "attestation_id": attestation_id,
                "consumer_packet": {
                    "attestation_id": attestation_id,
                    "source_binding": {
                        "head_full": HEAD,
                        "dataset": worker.RESULT_DATASET,
                        "generation": packet["result_version_id"],
                        "scope_hash": packet["provider_scope_hash"],
                        "source_current_packet_digest": worker._canonical_digest(packet),
                        "current_artifact_file_digest": packet["result_artifact_sha256"],
                        "artifact_digest": "c" * 64,
                    },
                    "claims": {
                        "worker_run_id": run_id,
                        "provider_version_digest": packet["provider_version_digest"],
                        "universe_digest": packet["universe_digest"],
                        "validated_trade_date": packet["validated_trade_date"],
                        "row_count": packet["result_row_count"],
                        "does_not_execute_trades": True,
                    },
                },
            },
        }
        with patch.object(
            worker.external_production_consumer_service,
            "validate_consumer",
            return_value=consumer,
        ):
            accepted = worker._trusted_worker_consumer_binding(
                Path("/unused"),
                head_full=HEAD,
                attestation_id=attestation_id,
                run_id=run_id,
                worker_packet=packet,
            )
            for field in (
                "provider_version_digest",
                "universe_digest",
                "validated_trade_date",
            ):
                claims = consumer["current_pointer"]["consumer_packet"]["claims"]
                original = claims[field]
                claims[field] = "0" * len(str(original))
                rejected = worker._trusted_worker_consumer_binding(
                    Path("/unused"),
                    head_full=HEAD,
                    attestation_id=attestation_id,
                    run_id=run_id,
                    worker_packet=packet,
                )
                self.assertFalse(rejected["ready"], field)
                claims[field] = original
        self.assertTrue(accepted["ready"])

    def test_upstream_pointer_or_packet_drift_fails_before_candidate_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, trust = self._fixture(root)
            pointer = parquet_store.versioned_dataset_pointer(
                root=root / "parquet", name=worker.RESULT_DATASET, pointer="current"
            )
            drifted_pointer = {**pointer, "artifact_sha256": "0" * 64}
            with (
                patch.object(worker, "_repository_clean_at_head", return_value=True),
                patch.object(worker, "_trusted_worker_consumer_binding", return_value=trust),
                patch.object(
                    worker.external_production_consumer_service,
                    "validate_consumer",
                    return_value={},
                ),
                patch.object(
                    worker.parquet_store,
                    "versioned_dataset_pointer",
                    side_effect=[pointer, drifted_pointer],
                ),
            ):
                result = worker.publish_candidate_radar_authoritative_cache(
                    payload, evidence_root=root
                )
            self.assertEqual(
                result.get("blockers"),
                ["candidate_cache_writer_upstream_changed_before_commit"],
            )
            self.assertIsNone(
                SQLiteMetaStore(root / "meta.sqlite", read_only=True).read_packet(
                    worker.CANDIDATE_CACHE_PACKET_KEY
                )
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, trust = self._fixture(root)
            original_promote = SQLiteMetaStore.promote_packet_pair_task_bundle_atomic

            def mutate_upstream_before_cas(
                store: SQLiteMetaStore, **kwargs: object
            ) -> dict[str, object]:
                writable = SQLiteMetaStore(root / "meta.sqlite")
                upstream = writable.read_packet(worker.PACKET_KEY)
                upstream["acceptance_run_id"] = uuid.uuid4().hex
                writable.write_packet(worker.PACKET_KEY, upstream)
                return original_promote(store, **kwargs)

            with (
                patch.object(worker, "_repository_clean_at_head", return_value=True),
                patch.object(worker, "_trusted_worker_consumer_binding", return_value=trust),
                patch.object(
                    SQLiteMetaStore,
                    "promote_packet_pair_task_bundle_atomic",
                    mutate_upstream_before_cas,
                ),
            ):
                result = worker.publish_candidate_radar_authoritative_cache(
                    payload, evidence_root=root
                )
            self.assertFalse(result["ready"])
            self.assertIsNone(
                SQLiteMetaStore(root / "meta.sqlite", read_only=True).read_packet(
                    worker.CANDIDATE_CACHE_PACKET_KEY
                )
            )

    def test_symlinked_worker_artifact_and_boolean_score_are_rejected(self) -> None:
        row = _worker_rows(["600000.SH"])[0]
        row["score"] = True
        self.assertEqual(
            worker._authoritative_radar_candidate_rows(
                [row], validated_trade_date=VALIDATED_DATE
            ),
            [],
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, trust = self._fixture(root)
            pointer = parquet_store.versioned_dataset_pointer(
                root=root / "parquet", name=worker.RESULT_DATASET, pointer="current"
            )
            artifact = Path(pointer["artifact_path"])
            outside = root / "outside.parquet"
            artifact.replace(outside)
            artifact.symlink_to(outside)
            with (
                patch.object(worker, "_repository_clean_at_head", return_value=True),
                patch.object(worker, "_trusted_worker_consumer_binding", return_value=trust),
            ):
                result = worker.publish_candidate_radar_authoritative_cache(
                    payload, evidence_root=root
                )
            self.assertFalse(result["ready"])
            self.assertIsNone(
                SQLiteMetaStore(root / "meta.sqlite", read_only=True).read_packet(
                    worker.CANDIDATE_CACHE_PACKET_KEY
                )
            )

    def test_external_factor_lineage_requires_exact_scope_binding(self) -> None:
        run_id = uuid.uuid4().hex
        factor_packet = {
            "acceptance_run_id": run_id,
            "provider_scope_hash": "1" * 64,
            "result_version_id": "factor-v1",
            "result_artifact_sha256": "2" * 64,
            "factor_output_contract_digest": "3" * 64,
            "neutralization_audit_digest": "4" * 64,
            "universe_digest": "5" * 64,
            "universe_count": 3000,
        }
        packet_digest = worker._canonical_digest(factor_packet)
        output_digest = worker._factor_output_binding_digest(factor_packet)
        consumer = {
            "ready": True,
            "production_trusted": True,
            "snapshot_rollback_resistant": True,
            "head_full": HEAD,
            "current_pointer": {
                "attestation_id": "6" * 64,
                "consumer_packet": {
                    "attestation_id": "6" * 64,
                    "source_binding": {
                        "head_full": HEAD,
                        "dataset": worker.FACTOR_RESULT_DATASET,
                        "generation": factor_packet["result_version_id"],
                        "scope_hash": factor_packet["provider_scope_hash"],
                        "source_current_packet_digest": packet_digest,
                        "current_artifact_file_digest": factor_packet[
                            "result_artifact_sha256"
                        ],
                        "artifact_digest": "7" * 64,
                    },
                    "claims": {
                        "result_dataset": worker.FACTOR_RESULT_DATASET,
                        "result_version_id": factor_packet["result_version_id"],
                        "universe_digest": factor_packet["universe_digest"],
                        "universe_count": 3000,
                        "metric_validation_digest": factor_packet[
                            "neutralization_audit_digest"
                        ],
                        "full_market_factor_research": True,
                        "does_not_execute_trades": True,
                    },
                },
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(worker, "_current_head_full", return_value=HEAD)
                )
                stack.enter_context(
                    patch.object(
                        worker, "_read_packet_no_init", return_value=factor_packet
                    )
                )
                stack.enter_context(
                    patch.object(
                        worker.external_production_consumer_service,
                        "validate_consumer",
                        return_value=consumer,
                    )
                )
                accepted = worker._matching_production_lineage_event(
                    Path(tmp),
                    event_kind=worker.FACTOR_LINEAGE_EVENT_KIND,
                    run_id=run_id,
                    worker_packet_digest=packet_digest,
                    output_binding_digest=output_digest,
                )
                consumer["current_pointer"]["consumer_packet"]["source_binding"][
                    "scope_hash"
                ] = "8" * 64
                rejected = worker._matching_production_lineage_event(
                    Path(tmp),
                    event_kind=worker.FACTOR_LINEAGE_EVENT_KIND,
                    run_id=run_id,
                    worker_packet_digest=packet_digest,
                    output_binding_digest=output_digest,
                )
        self.assertTrue(accepted["external_trust_verified"])
        self.assertEqual(rejected, {})

    def test_external_radar_lineage_requires_exact_cache_and_task_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, trust = self._fixture(root)
            with (
                patch.object(worker, "_repository_clean_at_head", return_value=True),
                patch.object(worker, "_trusted_worker_consumer_binding", return_value=trust),
            ):
                written = worker.publish_candidate_radar_authoritative_cache(
                    payload, evidence_root=root
                )
            self.assertTrue(written["ready"])
            store = SQLiteMetaStore(root / "meta.sqlite", read_only=True)
            worker_packet = store.read_packet(worker.PACKET_KEY)
            cache_packet = store.read_packet(worker.CANDIDATE_CACHE_PACKET_KEY)
            binding = cache_packet["full_market_worker_replacement"]
            task = store.read_task_status(binding["cache_write_task_id"])
            output_digest = worker._canonical_digest(
                {
                    "event_kind": worker.RADAR_LINEAGE_EVENT_KIND,
                    "acceptance_run_id": worker_packet["acceptance_run_id"],
                    "source_result_dataset": worker.RESULT_DATASET,
                    "source_result_version_id": worker_packet["result_version_id"],
                    "source_result_artifact_sha256": worker_packet[
                        "result_artifact_sha256"
                    ],
                    "source_result_output_hash": worker_packet["result_output_hash"],
                    "provider_version_digest": worker_packet["provider_version_digest"],
                    "universe_digest": worker_packet["universe_digest"],
                }
            )
            consumer = {
                "ready": True,
                "production_trusted": True,
                "snapshot_rollback_resistant": True,
                "head_full": HEAD,
                "current_pointer": {
                    "attestation_id": "d" * 64,
                    "consumer_packet": {
                        "attestation_id": "d" * 64,
                        "source_binding": {
                            "head_full": HEAD,
                            "dataset": worker.RESULT_DATASET,
                            "generation": worker_packet["result_version_id"],
                            "scope_hash": binding["binding_digest"],
                            "source_current_packet_digest": worker._canonical_digest(
                                cache_packet
                            ),
                            "current_artifact_file_digest": worker_packet[
                                "result_artifact_sha256"
                            ],
                            "artifact_digest": "e" * 64,
                        },
                        "claims": {
                            "candidate_cache_packet_key": worker.CANDIDATE_CACHE_PACKET_KEY,
                            "cache_write_task_id": binding["cache_write_task_id"],
                            "candidate_cache_write_task_digest": worker._canonical_digest(
                                task
                            ),
                            "universe_digest": worker_packet["universe_digest"],
                            "candidate_row_count": binding["candidate_row_count"],
                            "browser_evidence_digest": binding[
                                "browser_visual_evidence_digest"
                            ],
                            "performance_evidence_digest": binding[
                                "browser_performance_evidence_digest"
                            ],
                            "legacy_retirement_evidence_digest": binding[
                                "legacy_retirement_evidence_digest"
                            ],
                            "candidate_radar_production_replacement": True,
                            "candidate_is_not_buy_instruction": True,
                            "does_not_execute_trades": True,
                        },
                    },
                },
            }
            with (
                patch.object(worker, "_current_head_full", return_value=HEAD),
                patch.object(
                    worker.external_production_consumer_service,
                    "validate_consumer",
                    return_value=consumer,
                ),
            ):
                event = worker._matching_production_lineage_event(
                    root,
                    event_kind=worker.RADAR_LINEAGE_EVENT_KIND,
                    run_id=worker_packet["acceptance_run_id"],
                    worker_packet_digest=worker._canonical_digest(worker_packet),
                    output_binding_digest=output_digest,
                )
                tampered_task = {
                    **task,
                    "does_not_modify_strategy_action": False,
                }
                tampered_task["task_binding_digest"] = worker._canonical_digest(
                    {
                        key: value
                        for key, value in tampered_task.items()
                        if key != "task_binding_digest"
                    }
                )
                with patch.object(
                    worker, "_read_task_no_init", return_value=tampered_task
                ):
                    rejected_task = worker._matching_production_lineage_event(
                        root,
                        event_kind=worker.RADAR_LINEAGE_EVENT_KIND,
                        run_id=worker_packet["acceptance_run_id"],
                        worker_packet_digest=worker._canonical_digest(worker_packet),
                        output_binding_digest=output_digest,
                    )
                consumer["current_pointer"]["consumer_packet"]["source_binding"][
                    "source_current_packet_digest"
                ] = "f" * 64
                rejected = worker._matching_production_lineage_event(
                    root,
                    event_kind=worker.RADAR_LINEAGE_EVENT_KIND,
                    run_id=worker_packet["acceptance_run_id"],
                    worker_packet_digest=worker._canonical_digest(worker_packet),
                    output_binding_digest=output_digest,
                )
            self.assertEqual(
                event["candidate_cache_packet_digest"],
                worker._canonical_digest(cache_packet),
            )
            self.assertEqual(
                event["candidate_cache_write_task_digest"],
                worker._canonical_digest(task),
            )
            self.assertEqual(rejected_task, {})
            self.assertEqual(rejected, {})

    def test_route_is_post_only_and_cataloged(self) -> None:
        safe_result = {
            "ready": False,
            "status": "candidate_radar_authoritative_cache_write_blocked",
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }
        with patch.object(
            worker,
            "publish_candidate_radar_authoritative_cache",
            return_value=safe_result,
        ):
            client = TestClient(app)
            get_response = client.get(
                "/api/worker/candidate-radar-authoritative-cache-publish"
            )
            post_response = client.post(
                "/api/worker/candidate-radar-authoritative-cache-publish", json={}
            )
        self.assertEqual(get_response.status_code, 405)
        self.assertEqual(post_response.status_code, 200)
        self.assertFalse(post_response.json()["data"]["external_calls_triggered"])
        row = next(
            item
            for item in task_service.TASK_CATALOG
            if item.get("task_type") == worker.RADAR_CACHE_WRITE_TASK_TYPE
        )
        self.assertEqual(
            row["route"],
            "POST /api/worker/candidate-radar-authoritative-cache-publish",
        )
        self.assertEqual(row["possible_external_sources"], [])
        self.assertFalse(row["candidate_radar_production_replacement"])
        self.assertFalse(row["production_complete"])


if __name__ == "__main__":
    unittest.main()
