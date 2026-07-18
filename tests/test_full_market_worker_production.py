from __future__ import annotations

import json
import tempfile
import sys
import types
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from server.main import app
from server.services import full_market_worker_service as service
from server.services import task_service
from storage.sqlite_meta import SQLiteMetaStore


SCOPE_HASH = "a" * 64
INDUSTRY_BINDING = {
    "industry_scope_digest": "1" * 64,
    "industry_source_version_digest": "2" * 64,
    "industry_artifact_sha256": "3" * 64,
    "industry_manifest_digest": "4" * 64,
    "industry_pointer_digest": "5" * 64,
    "industry_semantic_evidence_sha256": "6" * 64,
}


def _valid_symbols(count: int) -> list[str]:
    symbols: list[str] = []
    for number in range(1, count + 1):
        symbols.append(f"{number:06d}.SZ")
    return symbols


def _patch_root(root: Path):
    return (
        patch.object(service, "EVIDENCE_ROOT", root),
        patch.object(service, "SQLITE_META_PATH", root / "meta.sqlite"),
        patch.object(service, "PARQUET_ROOT", root / "parquet"),
    )


def _verified_frames(symbols: list[str]) -> dict:
    dates = pd.bdate_range(end="2026-07-10", periods=90)
    date_values = [date.strftime("%Y%m%d") for date in dates]
    return {
        "stock_basic": pd.DataFrame(
            [
                {
                    "ts_code": symbol,
                    "symbol": symbol.split(".")[0],
                    "name": f"fixture-{index}",
                    "market": "主板",
                    "exchange": symbol.split(".")[-1],
                    "list_status": "L",
                    "list_date": "20000101",
                }
                for index, symbol in enumerate(symbols)
            ]
        ),
        "trade_cal": pd.DataFrame({"cal_date": date_values, "is_open": [1] * len(date_values)}),
        "daily": pd.DataFrame(
            [
                {
                    "ts_code": symbol,
                    "trade_date": date,
                    "close": 10 + index * 0.01,
                    "amount": 200000.0,
                }
                for symbol in symbols
                for index, date in enumerate(date_values)
            ]
        ),
        "daily_basic": pd.DataFrame(
            [
                {
                    "ts_code": symbol,
                    "trade_date": date_values[-1],
                    "turnover_rate": 2.0,
                    "volume_ratio": 1.2,
                    "total_mv": 100000.0,
                    "circ_mv": 80000.0,
                    "pe_ttm": 20.0,
                    "pb": 2.0,
                }
                for symbol in symbols
            ]
        ),
        "moneyflow": pd.DataFrame(
            [
                {
                    "ts_code": symbol,
                    "trade_date": date,
                    "buy_lg_amount": 20.0,
                    "sell_lg_amount": 10.0,
                    "buy_elg_amount": 10.0,
                    "sell_elg_amount": 5.0,
                }
                for symbol in symbols
                for date in date_values[-5:]
            ]
        ),
    }


def _shared_provider_result(symbols: list[str], *, ready: bool = True) -> dict:
    symbols = sorted(symbols)
    return {
        "ready": ready,
        "status": "verified" if ready else "blocked",
        "scope_hash": SCOPE_HASH,
        "version_digest": "b" * 64,
        "validated_trade_date": "20260710",
        "as_of": "20260713",
        "symbols": symbols,
        "universe_count": len(symbols),
        "universe_digest": service._canonical_digest(symbols),
        "frames": _verified_frames(symbols),
        "blockers": [] if ready else ["fixture_blocked"],
        **INDUSTRY_BINDING,
    }


def _provider_module(result: dict) -> types.ModuleType:
    module = types.ModuleType("server.services.tushare_production_store")
    module.validate_tushare_full_market_production_version = MagicMock(return_value=result)
    return module


def _score_universe(symbol: str = "000001.SZ") -> dict:
    frames = _verified_frames([symbol])
    return {
        "ready": True,
        "symbols": [symbol],
        "scope_hash": SCOPE_HASH,
        "version_digest": "b" * 64,
        "universe_digest": service._canonical_digest([symbol]),
        "validated_trade_date": "20260710",
        "_frames": frames,
        **INDUSTRY_BINDING,
    }


def _transport_fixture(run_id: str, hostname: str = "worker@host") -> dict:
    core = {
        "ready": True,
        "schema_version": service.TRANSPORT_SCHEMA_VERSION,
        "status": "external_redis_celery_direct_attested",
        "acceptance_run_id": run_id,
        "broker_direct_ping": True,
        "backend_roundtrip_verified": True,
        "backend_delete_verified": True,
        "backend_post_delete_missing": True,
        "registered_task_verified": True,
        "registered_queue_verified": True,
        "eligible_worker_count": 1,
        "eligible_worker_names": [hostname],
        "task_always_eager": False,
        "broker_endpoint_digest": "1" * 64,
        "backend_endpoint_digest": "2" * 64,
        "broker_explicit_host_port": True,
        "backend_explicit_host_port": True,
        "official_runtime_origin_digest": "3" * 64,
        "production_eligible": True,
        "probe_digest": "4" * 64,
        "synthetic_fixture": False,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "redis_celery_direct_transport_probe",
                "call_status": "success",
                "contains_secret": False,
            }
        ],
    }
    event = _transport_event_fixture(core)
    return {
        **core,
        "transport_core_digest": service._canonical_digest(core),
        "execution_event_key": service._execution_event_key(run_id),
        "execution_event_digest": service._canonical_digest(event),
    }


def _transport_event_fixture(transport: dict) -> dict:
    core = service._transport_core(transport)
    workers = sorted(core.get("eligible_worker_names") or [])
    return {
        "packet_key": service._execution_event_key(str(core.get("acceptance_run_id") or "")),
        "schema_version": service.EXECUTION_EVENT_SCHEMA_VERSION,
        "status": "official_redis_celery_transport_execution_succeeded",
        "created_at": "2026-07-13T00:00:00+00:00",
        "acceptance_run_id": core.get("acceptance_run_id"),
        "transport_core_digest": service._canonical_digest(core),
        "official_runtime_origin_digest": core.get("official_runtime_origin_digest"),
        "probe_digest": core.get("probe_digest"),
        "eligible_worker_set_digest": service._canonical_digest(workers),
        "broker_endpoint_digest": core.get("broker_endpoint_digest"),
        "backend_endpoint_digest": core.get("backend_endpoint_digest"),
        "ping_set_get_delete_post_delete_verified": True,
        "synthetic_fixture": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
    }


def _worker_batch_fixture(
    universe: dict,
    symbols: list[str],
    *,
    run_id: str,
    batch_index: int,
    batch_count: int,
    hostname: str = "worker@host",
):
    task_id = f"fmw-{run_id}-{batch_index:04d}-{uuid.uuid4().hex}"
    challenge_id = uuid.uuid4().hex
    batch = {
        "acceptance_run_id": run_id,
        "batch_index": batch_index,
        "batch_count": batch_count,
        "symbols": list(symbols),
        "batch_symbol_hash": service._canonical_digest(symbols),
        "batch_input_hash": service._batch_input_hash(universe, symbols),
        **INDUSTRY_BINDING,
        "industry_input_digest": service._industry_input_digest(universe),
        "celery_task_id": task_id,
        "worker_challenge_id": challenge_id,
    }
    runtime = {
        "bound_task_request": True,
        "synthetic_fixture": False,
        "celery_request_id": task_id,
        "worker_hostname": hostname,
        "worker_pid": 4242,
        "worker_queue": service.CANDIDATE_QUEUE,
        "worker_challenge_id": challenge_id,
        "worker_challenge_consumed": True,
        "worker_execution_proof": "e" * 64,
    }
    rows = service._score_candidate_rows(universe, symbols)
    task = {
        "task_id": f"candidate-worker-{task_id}",
        "task_type": service.CANDIDATE_TASK_TYPE,
        "status": "success",
        "current_step": "candidate_radar_full_market_batch_completed",
        "synthetic_fixture": False,
        "runtime_provenance": runtime,
        "worker_runtime_digest": service._canonical_digest(runtime),
        "payload_safe": {
            "acceptance_run_id": run_id,
            "celery_dispatch_id": task_id,
            "batch_index": batch_index,
            "batch_count": batch_count,
            "batch_symbol_count": len(symbols),
            "batch_symbol_hash": batch["batch_symbol_hash"],
            "batch_input_hash": batch["batch_input_hash"],
            "universe_digest": universe["universe_digest"],
            "provider_scope_hash": universe["scope_hash"],
            "provider_version_digest": universe["version_digest"],
            **INDUSTRY_BINDING,
            "industry_input_digest": service._industry_input_digest(universe),
            "worker_challenge_id": challenge_id,
        },
        "candidate_rows": rows,
        "candidate_output_hash": service._canonical_digest(rows),
        "batch_input_hash": batch["batch_input_hash"],
        "feature_contract_digest": service.FEATURE_CONTRACT_DIGEST,
        "call_ledger": [
            {
                "api": "local_candidate_radar_full_market_scoring",
                "call_status": "success",
                "row_count": len(rows),
                "external_calls_triggered": False,
                "contains_secret": False,
            }
        ],
    }
    transport = _transport_fixture(run_id, hostname)
    success = {
        **batch,
        "worker_task_id": task["task_id"],
        "candidate_output_hash": task["candidate_output_hash"],
        "candidate_row_count": len(rows),
        "worker_hostname": hostname,
        "worker_pid": 4242,
        "worker_queue": service.CANDIDATE_QUEUE,
    }
    chain = {
        "acceptance_run_id": run_id,
        "batch_index": batch_index,
        "batch_input_hash": batch["batch_input_hash"],
        "celery_task_id": task_id,
        "dispatch_result_id": task_id,
        "async_result_id": task_id,
        "async_result_state": "SUCCESS",
        "persisted_task_digest": service._canonical_digest(task),
        "candidate_output_hash": task["candidate_output_hash"],
        "worker_runtime_digest": task["worker_runtime_digest"],
        "worker_challenge_id": challenge_id,
        "worker_challenge_consumed": True,
        "worker_execution_proof_verified": True,
        "transport_attestation_digest": service._canonical_digest(transport),
        "transport_attestation": dict(transport),
        "eligible_worker_names": [hostname],
    }
    success["dispatch_chain"] = chain
    success["dispatch_chain_digest"] = service._canonical_digest(chain)
    return batch, task, transport, success


def _worker_fixture(
    symbols: list[str],
    *,
    run_id: str = "workerfixture123",
    hostname: str = "worker@host",
):
    shared = _shared_provider_result(symbols)
    universe = {
        **shared,
        "_frames": shared["frames"],
        "minimum_universe_size": service.DEFAULT_MINIMUM_UNIVERSE_SIZE,
    }
    batch, task, transport, success = _worker_batch_fixture(
        universe,
        symbols,
        run_id=run_id,
        batch_index=0,
        batch_count=1,
        hostname=hostname,
    )
    return universe, batch, task, transport, success


class _DirectConnection:
    connected = True

    class _Channel:
        def __init__(self):
            self.client = _DirectRedis()

        def close(self):
            return None

    def ensure_connection(self, max_retries=0):
        return self

    def channel(self):
        return self._Channel()

    def release(self):
        return None


class _DirectRedis:
    def __init__(self):
        self.values = {}

    def ping(self):
        return True

    def set(self, key, value, ex=30):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        self.values.pop(key, None)


class _DispatchResult:
    def __init__(self, task_id: str):
        self.id = task_id

    def get(self, timeout=None):
        raise TimeoutError("worker result did not arrive")


class _DispatchControl:
    def __init__(self):
        self.revoked: list[tuple[str, bool]] = []

    def revoke(self, task_id: str, terminate: bool = False):
        self.revoked.append((task_id, terminate))


class _PartialDispatchApp:
    def __init__(self):
        from celery import Celery

        self.control = _DispatchControl()
        self.sent: list[str] = []
        self.app = Celery("partial-dispatch-test", broker="memory://", backend="cache+memory://")

    def send_task(self, name, args, task_id, queue, routing_key):
        self.sent.append(task_id)
        if len(self.sent) == 2:
            raise ConnectionError("broker stopped after first accepted task")
        return self.app.AsyncResult(task_id)


class _TimeoutApp:
    def __init__(self):
        self.control = _DispatchControl()
        self.sent: list[str] = []

    def send_task(self, name, args, task_id, queue, routing_key):
        self.sent.append(task_id)
        return _DispatchResult(task_id)


class FullMarketWorkerProductionTests(unittest.TestCase):
    def test_route_missing_or_seven_symbol_universe_is_zero_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2], patch.object(
                service, "_load_celery_app"
            ) as loader:
                response = TestClient(app).post(
                    "/api/worker/full-market-production-acceptance",
                    json={"operator_approved": True, "symbols": _valid_symbols(4000)},
                )
            self.assertEqual(response.json()["data"]["dispatch_count"], 0)
            loader.assert_not_called()

            provider_module = _provider_module(_shared_provider_result(_valid_symbols(7)))
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2], patch.dict(
                sys.modules,
                {"server.services.tushare_production_store": provider_module},
            ), patch.object(service, "_load_celery_app") as loader:
                response = TestClient(app).post(
                    "/api/worker/full-market-production-acceptance",
                    json={
                        "operator_approved": True,
                        "minimum_universe_size": 7,
                        "symbols": _valid_symbols(4000),
                    },
                )
            payload = response.json()["data"]
            self.assertEqual(payload["status"], "authoritative_full_market_universe_missing_or_below_threshold")
            self.assertEqual(payload["dispatch_count"], 0)
            loader.assert_not_called()

    def test_synthetic_provider_and_invalid_exchange_prefix_never_promote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            symbols = ["000001.SH", "600000.SZ", "200001.SZ", "900001.SH"]
            provider_module = _provider_module(_shared_provider_result(symbols))
            with patch.dict(
                sys.modules,
                {"server.services.tushare_production_store": provider_module},
            ):
                universe = service._authoritative_provider_universe(
                    root,
                    minimum_universe_size=service.DEFAULT_MINIMUM_UNIVERSE_SIZE,
                )
            self.assertFalse(universe["ready"])
            self.assertIn("shared_provider_universe_identity_invalid", universe["blockers"])

    def test_provider_contract_is_consumed_only_through_shared_verifier(self) -> None:
        symbols = _valid_symbols(service.MIN_BATCH_SIZE)
        shared = _shared_provider_result(symbols)
        provider_module = _provider_module(shared)
        verifier = provider_module.validate_tushare_full_market_production_version
        with patch.dict(
            sys.modules,
            {"server.services.tushare_production_store": provider_module},
        ):
            universe = service._authoritative_provider_universe(
                Path("/not/read/by/worker"),
                minimum_universe_size=service.MIN_BATCH_SIZE,
                include_frames=True,
            )
        verifier.assert_called_once_with(Path("/not/read/by/worker"), include_frames=True)
        self.assertTrue(universe["ready"])
        self.assertEqual(universe["version_digest"], shared["version_digest"])
        self.assertEqual(set(universe["_frames"]), set(service.REQUIRED_PROVIDER_FRAMES))

    def test_boolean_only_and_missing_candidate_packets_never_promote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = {
                "schema_version": service.SCHEMA_VERSION,
                "status": "full_market_worker_production_complete",
                "full_market_worker_runtime": True,
                "celery_redis_runtime": True,
                "candidate_radar_production_replacement": True,
                "production_worker_complete": True,
                "direct_provenance_complete": True,
                "synthetic_fixture": False,
                "global_candidate_cache_overwritten": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
            }
            fake["production_binding_digest"] = service._canonical_digest(fake)
            store = SQLiteMetaStore(root / "meta.sqlite")
            store.write_packet(service.PACKET_KEY, fake)
            store.write_packet(service.LAST_GOOD_PACKET_KEY, fake)
            fact = service.validate_full_market_worker_production_fact(root)
            self.assertFalse(fact["ready"])
            self.assertFalse(fact["candidate_radar_production_replacement"])
            self.assertIn("bound_worker_task_outputs", fact["blockers"])

    def test_worker_packet_radar_claim_requires_cache_and_external_lineage(self) -> None:
        self.assertEqual(
            service._candidate_radar_replacement_claim_fields(
                authoritative_cache_validated=False,
                external_lineage_validated=False,
            ),
            {
                "candidate_radar_production_replacement": False,
                "global_candidate_cache_overwritten": False,
            },
        )
        self.assertFalse(
            service._candidate_radar_replacement_claim_fields(
                authoritative_cache_validated=True,
                external_lineage_validated=False,
            )["candidate_radar_production_replacement"]
        )
        self.assertFalse(
            service._candidate_radar_replacement_claim_fields(
                authoritative_cache_validated=False,
                external_lineage_validated=True,
            )["candidate_radar_production_replacement"]
        )
        self.assertTrue(
            service._candidate_radar_replacement_claim_fields(
                authoritative_cache_validated=True,
                external_lineage_validated=True,
            )["candidate_radar_production_replacement"]
        )

    def test_candidate_worker_output_needs_exact_authoritative_cache_binding(self) -> None:
        acceptance_run_id = uuid.uuid4().hex
        worker_packet = {
            "acceptance_run_id": acceptance_run_id,
            "result_version_id": f"fmw-{acceptance_run_id}",
            "result_artifact_sha256": "a" * 64,
            "result_output_hash": "b" * 64,
            "provider_version_digest": "c" * 64,
            "universe_digest": "d" * 64,
        }
        candidate_rows = [{"ts_code": "000001.SZ", "score": 91}]
        cache_packet = {
            "packet_key": service.CANDIDATE_CACHE_PACKET_KEY,
            "schema_version": service.CANDIDATE_CACHE_SCHEMA_VERSION,
            "status": "candidate_radar_full_market_replacement_ready",
            "cache_only": True,
            "candidate_rows": candidate_rows,
            "candidate_is_not_buy_instruction": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "global_candidate_cache_overwritten": False,
        }
        self.assertFalse(
            service._candidate_cache_replacement_ready(cache_packet, worker_packet, {})
        )

        cache_write_task_id = uuid.uuid4().hex
        output_binding_digest = service._canonical_digest(
            {
                "event_kind": service.RADAR_LINEAGE_EVENT_KIND,
                "acceptance_run_id": worker_packet["acceptance_run_id"],
                "source_result_dataset": service.RESULT_DATASET,
                "source_result_version_id": worker_packet["result_version_id"],
                "source_result_artifact_sha256": worker_packet["result_artifact_sha256"],
                "source_result_output_hash": worker_packet["result_output_hash"],
                "provider_version_digest": worker_packet["provider_version_digest"],
                "universe_digest": worker_packet["universe_digest"],
            }
        )
        common_evidence = {
            "head_full": service._current_head_full(),
            "acceptance_run_id": acceptance_run_id,
            "source_output_binding_digest": output_binding_digest,
            "contains_secret": False,
            "does_not_execute_trades": True,
        }
        deep_scan_evidence = {
            **common_evidence,
            "schema_version": "candidate_radar_deep_scan_worker_execution_evidence.v1",
            "status": "candidate_radar_deep_scan_worker_execution_verified",
            "worker_execution_verified": True,
            "full_pool_scan_verified": True,
            "deep_scan_verified": True,
        }
        browser_visual_evidence = {
            **common_evidence,
            "schema_version": "candidate_radar_browser_visual_qa_evidence.v1",
            "status": "candidate_radar_browser_visual_qa_passed",
            "route": "#candidates",
            "visual_qa_passed": True,
            "screenshot_count": 2,
            "review_id": "5" * 64,
        }
        browser_performance_evidence = {
            **common_evidence,
            "schema_version": "candidate_radar_browser_performance_evidence.v1",
            "status": "candidate_radar_browser_performance_passed",
            "route": "#candidates",
            "performance_passed": True,
            "p95_ms": 80.0,
            "p95_budget_ms": 120.0,
        }
        legacy_retirement_evidence = {
            **common_evidence,
            "schema_version": "candidate_radar_legacy_retirement_evidence.v1",
            "status": "candidate_radar_legacy_fallback_retired",
            "legacy_fallback_retired": True,
            "legacy_fallback_required": False,
            "streamlit_primary_surface_present": False,
        }
        evidence_digests = {
            "deep_scan_execution_evidence_digest": service._canonical_digest(
                deep_scan_evidence
            ),
            "browser_visual_evidence_digest": service._canonical_digest(
                browser_visual_evidence
            ),
            "browser_performance_evidence_digest": service._canonical_digest(
                browser_performance_evidence
            ),
            "legacy_retirement_evidence_digest": service._canonical_digest(
                legacy_retirement_evidence
            ),
        }
        binding = {
            "schema_version": service.CANDIDATE_CACHE_REPLACEMENT_SCHEMA_VERSION,
            "status": "authoritative_candidate_cache_replaced",
            "global_candidate_cache_overwritten": True,
            "cache_write_task_id": cache_write_task_id,
            "acceptance_run_id": worker_packet["acceptance_run_id"],
            "source_result_dataset": service.RESULT_DATASET,
            "source_result_version_id": worker_packet["result_version_id"],
            "source_result_artifact_sha256": worker_packet["result_artifact_sha256"],
            "source_result_output_hash": worker_packet["result_output_hash"],
            "provider_version_digest": worker_packet["provider_version_digest"],
            "universe_digest": worker_packet["universe_digest"],
            "candidate_row_count": len(candidate_rows),
            "candidate_rows_digest": service._canonical_digest(candidate_rows),
            "contains_secret": False,
            "does_not_execute_trades": True,
            **evidence_digests,
        }
        binding["binding_digest"] = service._canonical_digest(binding)
        cache_packet["full_market_worker_replacement"] = binding
        cache_write_task = {
            "schema_version": "candidate_radar_full_market_cache_write_task.v1",
            "task_id": cache_write_task_id,
            "task_type": "publish_candidate_radar_full_market_cache",
            "status": "success",
            "output_packet_key": service.CANDIDATE_CACHE_PACKET_KEY,
            "acceptance_run_id": worker_packet["acceptance_run_id"],
            "source_result_version_id": worker_packet["result_version_id"],
            "source_result_output_hash": worker_packet["result_output_hash"],
            "candidate_rows_digest": service._canonical_digest(candidate_rows),
            "global_candidate_cache_overwritten": True,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
            "contains_secret": False,
            **evidence_digests,
        }
        cache_write_task["task_binding_digest"] = service._canonical_digest(cache_write_task)
        self.assertFalse(
            service._candidate_cache_replacement_ready(
                cache_packet,
                worker_packet,
                cache_write_task,
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            evidence_root = Path(directory)
            cache_packet["global_candidate_cache_overwritten"] = True
            cache_packet_digest = service._canonical_digest(cache_packet)
            cache_write_task_digest = service._canonical_digest(cache_write_task)
            with patch.object(
                service,
                "_official_orchestrator_state",
                return_value={"transport_event_persisted": True},
            ):
                rejected = service._persist_official_production_lineage_event(
                    evidence_root,
                    capability=object(),
                    run_id=acceptance_run_id,
                    event_kind=service.RADAR_LINEAGE_EVENT_KIND,
                    worker_packet_digest=service._canonical_digest(worker_packet),
                    output_binding_digest=output_binding_digest,
                    candidate_cache_packet_digest=cache_packet_digest,
                    candidate_cache_write_task_digest=cache_write_task_digest,
                    deep_scan_execution_evidence=deep_scan_evidence,
                    browser_visual_evidence=browser_visual_evidence,
                    browser_performance_evidence={
                        **browser_performance_evidence,
                        "p95_ms": 121.0,
                    },
                    legacy_retirement_evidence=legacy_retirement_evidence,
                    global_candidate_cache_overwritten=True,
                    deep_scan_worker_execution_verified=True,
                    browser_visual_qa_verified=True,
                    browser_performance_verified=True,
                    legacy_fallback_retired=True,
                )
                self.assertFalse(rejected["production_eligible"])
                self.assertEqual(
                    rejected["blockers"],
                    [service.PRODUCTION_LINEAGE_EXTERNAL_RUNNER_BLOCKER],
                )
                event = service._persist_official_production_lineage_event(
                    evidence_root,
                    capability=object(),
                    run_id=acceptance_run_id,
                    event_kind=service.RADAR_LINEAGE_EVENT_KIND,
                    worker_packet_digest=service._canonical_digest(worker_packet),
                    output_binding_digest=output_binding_digest,
                    candidate_cache_packet_digest=cache_packet_digest,
                    candidate_cache_write_task_digest=cache_write_task_digest,
                    deep_scan_execution_evidence=deep_scan_evidence,
                    browser_visual_evidence=browser_visual_evidence,
                    browser_performance_evidence=browser_performance_evidence,
                    legacy_retirement_evidence=legacy_retirement_evidence,
                    global_candidate_cache_overwritten=True,
                    deep_scan_worker_execution_verified=True,
                    browser_visual_qa_verified=True,
                    browser_performance_verified=True,
                    legacy_fallback_retired=True,
                )
            self.assertFalse(event["production_eligible"])
            self.assertFalse(event["writes_storage"])
            self.assertEqual(
                event["status"],
                "external_trusted_production_lineage_runner_required",
            )
            self.assertFalse((evidence_root / "meta.sqlite").exists())
            self.assertFalse(service._lineage_key_path(evidence_root).exists())
            self.assertFalse(
                service._candidate_cache_replacement_ready(
                    cache_packet,
                    worker_packet,
                    cache_write_task,
                    evidence_root=evidence_root,
                )
            )
            with patch.object(service, "_current_head_full", return_value="f" * 40):
                self.assertFalse(
                    service._candidate_cache_replacement_ready(
                        cache_packet,
                        worker_packet,
                        cache_write_task,
                        evidence_root=evidence_root,
                    )
                )
            cache_packet["global_candidate_cache_overwritten"] = False
            self.assertFalse(
                service._candidate_cache_replacement_ready(
                    cache_packet,
                    worker_packet,
                    cache_write_task,
                    evidence_root=evidence_root,
                )
            )
            cache_packet["global_candidate_cache_overwritten"] = True
            cache_packet["candidate_rows"][0]["score"] = 92
            self.assertFalse(
                service._candidate_cache_replacement_ready(
                    cache_packet,
                    worker_packet,
                    cache_write_task,
                    evidence_root=evidence_root,
                )
            )

    def test_candidate_worker_packet_cannot_satisfy_factor_full_market_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate_packet = {
                "schema_version": service.SCHEMA_VERSION,
                "status": "full_market_worker_production_complete",
                "full_market_worker_runtime": True,
                "candidate_radar_production_replacement": True,
                "production_worker_complete": True,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
            }
            store = SQLiteMetaStore(root / "meta.sqlite")
            store.write_packet(service.FACTOR_PACKET_KEY, candidate_packet)
            store.write_packet(service.FACTOR_LAST_GOOD_PACKET_KEY, candidate_packet)

            fact = service.validate_factor_full_market_research_fact(root)

            self.assertFalse(fact["ready"])
            self.assertFalse(fact["full_market_factor_research"])
            self.assertFalse(fact["candidate_radar_output_accepted_as_factor"])
            self.assertIn("factor_worker_packet_direct_binding", fact["blockers"])

    def test_factor_metric_contract_awaits_external_trusted_lineage_runner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            symbols = ["000001.SZ", "000002.SZ", "600000.SH", "600001.SH"]
            universe_digest = service._canonical_digest(symbols)
            rows = [
                {
                    "ts_code": symbol,
                    "cross_sectional_rank": index + 1,
                    "cross_sectional_zscore": (-1.0, 1.0, -1.0, 1.0)[index],
                    "industry_neutral_score": (-1.0, 1.0, -1.0, 1.0)[index],
                    "size_neutral_score": (1.0, -1.0, -1.0, 1.0)[index],
                    "combined_factor_score": (0.5, -0.5, -0.5, 0.5)[index],
                    "industry_code": ("bank", "bank", "tech", "tech")[index],
                    "market_cap": (1.0, 4.0, 2.0, 8.0)[index],
                    "does_not_execute_trades": True,
                }
                for index, symbol in enumerate(symbols)
            ]
            result_output_hash = service._canonical_digest(rows)
            metric_audit = service._factor_metric_validation_audit(
                rows,
                universe_digest=universe_digest,
                result_output_hash=result_output_hash,
            )
            self.assertTrue(metric_audit["ready"], metric_audit["blockers"])
            run_id = uuid.uuid4().hex
            industry_input_digest = service._canonical_digest(INDUSTRY_BINDING)
            factor_batch_input_digest = service._canonical_digest(
                {
                    "provider_scope_hash": "a" * 64,
                    "provider_version_digest": "b" * 64,
                    "universe_digest": universe_digest,
                    "validated_trade_date": "20260710",
                    "symbols": symbols,
                    "industry_binding": INDUSTRY_BINDING,
                    "industry_input_digest": industry_input_digest,
                }
            )
            packet = {
                "schema_version": service.FACTOR_SCHEMA_VERSION,
                "status": "factor_full_market_worker_production_complete",
                "acceptance_run_id": run_id,
                "output_kind": "factor_full_market_cross_sectional_research",
                "factor_output_contract": service.FACTOR_OUTPUT_CONTRACT,
                "factor_output_contract_digest": service.FACTOR_OUTPUT_CONTRACT_DIGEST,
                "full_market_factor_research": True,
                "full_market_worker_runtime": True,
                "candidate_radar_production_replacement": False,
                "provider_scope_hash": "a" * 64,
                "provider_version_digest": "b" * 64,
                "universe_digest": universe_digest,
                "universe_count": len(symbols),
                "validated_trade_date": "20260710",
                **INDUSTRY_BINDING,
                "industry_input_digest": industry_input_digest,
                "factor_batch_input_digest": factor_batch_input_digest,
                "result_version_id": f"factor-{run_id}",
                "result_artifact_sha256": "c" * 64,
                "result_output_hash": result_output_hash,
                "metric_validation_audit": metric_audit,
                "neutralization_audit_digest": metric_audit["audit_digest"],
                "synthetic_fixture": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
            }
            packet["production_binding_digest"] = service._canonical_digest(packet)
            store = SQLiteMetaStore(root / "meta.sqlite")
            store.write_packet(service.FACTOR_PACKET_KEY, packet)
            store.write_packet(service.FACTOR_LAST_GOOD_PACKET_KEY, packet)
            artifact_path = root / "factor.parquet"
            artifact_path.write_bytes(b"verified-by-mocked-pointer-reader")
            pointer = {
                "status": "ready",
                "version_id": packet["result_version_id"],
                "artifact_path": str(artifact_path),
                "artifact_sha256_matches": True,
                "artifact_sha256": packet["result_artifact_sha256"],
                "lineage": {
                    "factor_output_contract_digest": service.FACTOR_OUTPUT_CONTRACT_DIGEST,
                    "universe_digest": universe_digest,
                    "provider_version_digest": packet["provider_version_digest"],
                    "validated_trade_date": "20260710",
                    **INDUSTRY_BINDING,
                    "industry_input_digest": industry_input_digest,
                    "factor_batch_input_digest": factor_batch_input_digest,
                    "neutralization_audit_digest": metric_audit["audit_digest"],
                },
            }
            universe = {
                "ready": True,
                "symbols": symbols,
                "universe_count": len(symbols),
                "scope_hash": packet["provider_scope_hash"],
                "version_digest": packet["provider_version_digest"],
                "universe_digest": universe_digest,
                "validated_trade_date": "20260710",
                **INDUSTRY_BINDING,
                "blockers": [],
            }
            with patch.object(
                service,
                "_official_orchestrator_state",
                return_value={"transport_event_persisted": True},
            ):
                event = service._persist_official_production_lineage_event(
                    root,
                    capability=object(),
                    run_id=run_id,
                    event_kind=service.FACTOR_LINEAGE_EVENT_KIND,
                    worker_packet_digest=service._canonical_digest(packet),
                    output_binding_digest=service._factor_output_binding_digest(packet),
                    factor_output_contract_digest=service.FACTOR_OUTPUT_CONTRACT_DIGEST,
                    neutralization_audit_digest=metric_audit["audit_digest"],
                )
            self.assertFalse(event["production_eligible"])
            self.assertFalse(event["writes_storage"])
            self.assertFalse(service._lineage_key_path(root).exists())
            with patch.object(
                service,
                "_authoritative_provider_universe",
                return_value=universe,
            ), patch.object(
                service.parquet_store,
                "versioned_dataset_pointer",
                return_value=pointer,
            ), patch.object(pd, "read_parquet", return_value=pd.DataFrame(rows)):
                fact = service.validate_factor_full_market_research_fact(root)
            self.assertFalse(fact["ready"])
            self.assertFalse(fact["trusted_lineage_event_observed"])
            self.assertEqual(
                fact["blockers"],
                [service.PRODUCTION_LINEAGE_EXTERNAL_RUNNER_BLOCKER],
            )
            stale_packet = dict(packet)
            stale_packet.pop("industry_pointer_digest")
            stale_packet["production_binding_digest"] = service._canonical_digest(
                {
                    key: value
                    for key, value in stale_packet.items()
                    if key != "production_binding_digest"
                }
            )
            store.write_packet(service.FACTOR_PACKET_KEY, stale_packet)
            store.write_packet(service.FACTOR_LAST_GOOD_PACKET_KEY, stale_packet)
            with patch.object(
                service,
                "_authoritative_provider_universe",
                return_value=universe,
            ), patch.object(
                service.parquet_store,
                "versioned_dataset_pointer",
                return_value=pointer,
            ), patch.object(pd, "read_parquet", return_value=pd.DataFrame(rows)):
                stale_fact = service.validate_factor_full_market_research_fact(root)
            self.assertIn("factor_worker_packet_direct_binding", stale_fact["blockers"])

    def test_radar_batch_input_hash_binds_pointer_and_semantic_digests(self) -> None:
        universe = _score_universe()
        symbols = list(universe["symbols"])
        baseline = service._batch_input_hash(universe, symbols)
        for key in (
            "industry_pointer_digest",
            "industry_semantic_evidence_sha256",
        ):
            with self.subTest(key=key):
                tampered = dict(universe)
                tampered[key] = "f" * 64
                self.assertNotEqual(
                    baseline,
                    service._batch_input_hash(tampered, symbols),
                )

    def test_introspected_runner_capability_cannot_promote_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            closure_values = [
                cell.cell_contents
                for cell in (
                    service.run_full_market_worker_production_acceptance.__closure__ or ()
                )
            ]
            register = next(
                value
                for value in closure_values
                if callable(value) and getattr(value, "__name__", "") == "register"
            )
            run_id = uuid.uuid4().hex
            capability, state = register(run_id)
            state["transport_event_persisted"] = True
            self.assertTrue(service._official_orchestrator_state(capability, run_id))
            event = service._persist_official_production_lineage_event(
                root,
                capability=capability,
                run_id=run_id,
                event_kind=service.FACTOR_LINEAGE_EVENT_KIND,
                worker_packet_digest="a" * 64,
                output_binding_digest="b" * 64,
                factor_output_contract_digest=service.FACTOR_OUTPUT_CONTRACT_DIGEST,
                neutralization_audit_digest="c" * 64,
            )
            self.assertFalse(event["production_eligible"])
            self.assertFalse(event["external_trusted_runner_observed"])
            self.assertFalse(event["writes_storage"])
            self.assertEqual(
                event["blockers"],
                [service.PRODUCTION_LINEAGE_EXTERNAL_RUNNER_BLOCKER],
            )
            self.assertFalse((root / "meta.sqlite").exists())
            self.assertFalse(service._lineage_key_path(root).exists())
            self.assertEqual(
                service._matching_production_lineage_event(
                    root,
                    event_kind=service.FACTOR_LINEAGE_EVENT_KIND,
                    run_id=run_id,
                    worker_packet_digest="a" * 64,
                    output_binding_digest="b" * 64,
                ),
                {},
            )

    def test_sealed_lineage_writer_preserves_existing_key_and_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key_path = service._lineage_key_path(root)
            key_path.parent.mkdir(parents=True)
            key_path.write_bytes(b"k" * 32)
            key_path.chmod(0o600)
            database_path = root / "meta.sqlite"
            database_path.write_bytes(b"preexisting-database-sentinel")
            key_before = key_path.read_bytes()
            database_before = database_path.read_bytes()
            mode_before = key_path.stat().st_mode & 0o777

            event = service._persist_official_production_lineage_event(
                root,
                capability=object(),
                run_id=uuid.uuid4().hex,
                event_kind=service.RADAR_LINEAGE_EVENT_KIND,
                worker_packet_digest="a" * 64,
                output_binding_digest="b" * 64,
            )

            self.assertFalse(event["production_eligible"])
            self.assertEqual(key_path.read_bytes(), key_before)
            self.assertEqual(key_path.stat().st_mode & 0o777, mode_before)
            self.assertEqual(database_path.read_bytes(), database_before)

    def test_factor_metric_audit_rejects_nonfinite_and_false_neutralization(self) -> None:
        rows = [
            {
                "ts_code": f"{index + 1:06d}.SZ",
                "cross_sectional_rank": index + 1,
                "cross_sectional_zscore": float("nan") if index == 0 else float(index),
                "industry_neutral_score": 2.0,
                "size_neutral_score": float(index),
                "combined_factor_score": float(index),
                "industry_code": "same-industry",
                "market_cap": float(index + 1),
                "does_not_execute_trades": True,
            }
            for index in range(4)
        ]
        audit = service._factor_metric_validation_audit(
            rows,
            universe_digest="a" * 64,
            result_output_hash="b" * 64,
        )
        self.assertFalse(audit["ready"])
        self.assertIn("metric_numeric_finite_complete", audit["blockers"])
        self.assertIn("neutralization_input_coverage", audit["blockers"])

    def test_fake_eager_and_patched_inspector_transport_fail(self) -> None:
        self.assertFalse(service._transport_probe(object(), acceptance_run_id="runtime123")["ready"])
        try:
            from celery import Celery
        except Exception:
            self.skipTest("celery dependency missing")
        eager = Celery("eager", broker="redis://127.0.0.1:6379/15", backend="redis://127.0.0.1:6379/15")
        eager.conf.task_always_eager = True
        self.assertFalse(service._transport_probe(eager, acceptance_run_id="runtime123")["ready"])

        patched = Celery("patched", broker="redis://127.0.0.1:6379/15", backend="redis://127.0.0.1:6379/15")
        patched.connection_for_write = lambda: _DirectConnection()
        patched.backend.__dict__["client"] = _DirectRedis()
        patched.control.inspect = MagicMock(return_value=MagicMock())
        attestation = service._transport_probe(patched, acceptance_run_id="runtime123")
        self.assertFalse(attestation["ready"])
        self.assertEqual(attestation["status"], "injected_or_caller_supplied_transport_non_production")

    def test_missing_explicit_redis_port_blocks_before_official_app_construction(self) -> None:
        with patch.dict(
            service.os.environ,
            {
                "COMMAND_CENTER_REDIS_URL": "redis://127.0.0.1/15",
                "COMMAND_CENTER_CELERY_BROKER_URL": "redis://127.0.0.1/15",
                "COMMAND_CENTER_CELERY_RESULT_BACKEND": "redis://127.0.0.1/15",
            },
        ), patch("celery.Celery") as constructor:
            app_value, attestation = service._build_and_probe_official_transport(
                acceptance_run_id="0" * 32,
            )
        self.assertIsNone(app_value)
        self.assertEqual(attestation["status"], "explicit_redis_host_and_port_required")
        constructor.assert_not_called()

    def test_result_returned_after_global_deadline_is_rejected(self) -> None:
        class Clock:
            value = 0.0

            def __call__(self):
                return self.value

        clock = Clock()

        class LateResult:
            def get(self, timeout=None):
                clock.value = 181.0
                return {"status": "success"}

        with self.assertRaisesRegex(TimeoutError, "global_result_deadline_exceeded_after_response"):
            service._get_result_before_deadline(LateResult(), deadline=180.0, clock=clock)

    def test_bound_worker_rejects_synthetic_runtime_before_provider_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            symbols = _valid_symbols(service.MIN_BATCH_SIZE)
            payload = {
                "full_market_worker_acceptance": True,
                "celery_dispatch_id": "fmw-synthetic-0000",
                "symbols": symbols,
                "batch_symbol_hash": service._canonical_digest(symbols),
                "feature_contract_digest": service.FEATURE_CONTRACT_DIGEST,
            }
            runtime = {
                "celery_request_id": "fmw-synthetic-0000",
                "worker_hostname": "fixture",
                "worker_pid": 1,
                "worker_queue": service.CANDIDATE_QUEUE,
                "bound_task_request": True,
                "synthetic_fixture": True,
            }
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2], patch.object(
                service, "_authoritative_provider_universe", side_effect=AssertionError("must not read provider")
            ):
                result = service.execute_candidate_radar_batch_worker(payload, runtime=runtime)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["synthetic_fixture"])

    def test_scoring_uses_historical_features_not_universe_echo(self) -> None:
        universe = _score_universe()
        rows = service._score_candidate_rows(universe, universe["symbols"])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertGreater(row["score"], 0)
        self.assertEqual(row["feature_contract_digest"], service.FEATURE_CONTRACT_DIGEST)
        self.assertIn("ma60", row)
        self.assertIn("five_day_main_net_amount", row)
        self.assertEqual(row["radar_scoring_contract"], "next_stock_radar.score_candidate")
        self.assertTrue(row["battle_state"])
        self.assertNotEqual(set(row), {"ts_code"})

    def test_worker_task_recomputes_radar_rows_and_rejects_forged_score(self) -> None:
        symbols = _valid_symbols(service.MIN_BATCH_SIZE)
        universe, batch, task, transport, _success = _worker_fixture(symbols)
        ready, rows = service._validate_worker_task(
            task,
            batch=batch,
            universe=universe,
            transport=transport,
        )
        self.assertTrue(ready)
        self.assertEqual(rows, service._score_candidate_rows(universe, symbols))

        forged = dict(task)
        forged_rows = [dict(row) for row in task["candidate_rows"]]
        forged_rows[0]["score"] = 99 if forged_rows[0]["score"] != 99 else 1
        forged["candidate_rows"] = forged_rows
        forged["candidate_output_hash"] = service._canonical_digest(forged_rows)
        ready, _ = service._validate_worker_task(
            forged,
            batch=batch,
            universe=universe,
            transport=transport,
        )
        self.assertFalse(ready)

    def test_worker_hostname_must_match_inspected_eligible_worker(self) -> None:
        symbols = _valid_symbols(service.MIN_BATCH_SIZE)
        universe, batch, task, _transport, _success = _worker_fixture(symbols)
        ready, _ = service._validate_worker_task(
            task,
            batch=batch,
            universe=universe,
            transport={"eligible_worker_names": ["different@host"]},
        )
        self.assertFalse(ready)

        _universe, batch, task, transport, success = _worker_fixture(symbols)
        forged = json.loads(json.dumps(success))
        forged_attestation = forged["dispatch_chain"]["transport_attestation"]
        forged_attestation["eligible_worker_names"] = ["different@host"]
        forged_attestation["eligible_worker_count"] = 1
        forged["dispatch_chain"]["transport_attestation_digest"] = service._canonical_digest(
            forged_attestation
        )
        forged["dispatch_chain_digest"] = service._canonical_digest(forged["dispatch_chain"])
        self.assertFalse(
            service._dispatch_chain_ready(
                forged,
                task,
                run_id=batch["acceptance_run_id"],
                transport=transport,
            )
        )
        self.assertFalse(
            service._transport_execution_event_ready(
                transport,
                {},
                run_id=batch["acceptance_run_id"],
            )
        )

    def test_missing_or_duplicate_batch_results_never_cover_the_universe(self) -> None:
        all_symbols = _valid_symbols(service.MIN_BATCH_SIZE * 2)
        batches = [
            all_symbols[: service.MIN_BATCH_SIZE],
            all_symbols[service.MIN_BATCH_SIZE :],
        ]
        shared = _shared_provider_result(all_symbols)
        universe = {
            **shared,
            "_frames": shared["frames"],
            "minimum_universe_size": service.DEFAULT_MINIMUM_UNIVERSE_SIZE,
        }
        run_id = "batchcoverage123"
        transport = _transport_fixture(run_id)
        tasks: list[dict] = []
        successes: list[dict] = []
        for batch_index, symbols in enumerate(batches):
            _batch, task, _transport, success = _worker_batch_fixture(
                universe,
                symbols,
                run_id=run_id,
                batch_index=batch_index,
                batch_count=len(batches),
            )
            tasks.append(task)
            successes.append(success)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                store = SQLiteMetaStore(root / "meta.sqlite")
                for task in tasks:
                    store.write_task_status(task)
                complete = service._result_rows_from_batches(
                    successes,
                    universe=universe,
                    transport=transport,
                    execution_event=_transport_event_fixture(transport),
                )
                missing = service._result_rows_from_batches(
                    successes[:1],
                    universe=universe,
                    transport=transport,
                    execution_event=_transport_event_fixture(transport),
                )
                duplicate = service._result_rows_from_batches(
                    [successes[0], successes[0], successes[1]],
                    universe=universe,
                    transport=transport,
                    execution_event=_transport_event_fixture(transport),
                )
        self.assertEqual(len(complete), len(all_symbols))
        self.assertEqual(missing, [])
        self.assertEqual(duplicate, [])

    def test_partial_resume_without_worker_task_is_rejected(self) -> None:
        symbols = _valid_symbols(service.MIN_BATCH_SIZE)
        shared = _shared_provider_result(symbols)
        universe = {
            **shared,
            "_frames": shared["frames"],
            "minimum_universe_size": service.DEFAULT_MINIMUM_UNIVERSE_SIZE,
        }
        transport = {"eligible_worker_names": ["worker@host"]}
        checkpoint = {
            "schema_version": service.CHECKPOINT_SCHEMA_VERSION,
            "status": "partial_failure_resume_available",
            "resume_available": True,
            "synthetic_fixture": False,
            "acceptance_run_id": "resume123",
            "provider_scope_hash": SCOPE_HASH,
            "provider_version_digest": universe["version_digest"],
            "universe_digest": universe["universe_digest"],
            "transport_attestation_digest": service._canonical_digest(transport),
            "feature_contract_digest": service.FEATURE_CONTRACT_DIGEST,
            "batch_count": 1,
            "successful_batches": [
                {
                    "batch_index": 0,
                    "celery_task_id": "fmw-resume123-0000",
                    "worker_task_id": "missing-worker-task",
                }
            ],
        }
        checkpoint["checkpoint_binding_digest"] = service._canonical_digest(checkpoint)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                self.assertEqual(
                    service._validated_resume_successes(
                        checkpoint,
                        run_id="resume123",
                        universe=universe,
                        batches=[symbols],
                        transport=transport,
                        execution_event={},
                    ),
                    [],
                )

    def test_quarantined_late_task_is_never_reused_by_resume(self) -> None:
        symbols = _valid_symbols(service.MIN_BATCH_SIZE)
        universe, _batch, task, transport, success = _worker_fixture(
            symbols,
            run_id="quarantineresume123",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                store = SQLiteMetaStore(root / "meta.sqlite")
                store.write_task_status(task)
                checkpoint = service._write_checkpoint(
                    run_id="quarantineresume123",
                    universe=universe,
                    batches=[symbols],
                    successes=[success],
                    status="partial_failure_resume_available",
                    transport=transport,
                )
                before = service._validated_resume_successes(
                    checkpoint,
                    run_id="quarantineresume123",
                    universe=universe,
                    batches=[symbols],
                    transport=transport,
                    execution_event=_transport_event_fixture(transport),
                    resume_proof_verifier=lambda _success, _task: True,
                )
                app = _PartialDispatchApp()
                service._revoke_and_quarantine(
                    app,
                    [success["celery_task_id"]],
                    "quarantineresume123",
                    "late_result",
                )
                after = service._validated_resume_successes(
                    checkpoint,
                    run_id="quarantineresume123",
                    universe=universe,
                    batches=[symbols],
                    transport=transport,
                    execution_event=_transport_event_fixture(transport),
                    resume_proof_verifier=lambda _success, _task: True,
                )
        self.assertEqual(len(before), 1)
        self.assertEqual(after, [])

    def test_shape_valid_forged_resume_without_redis_receipt_is_rejected(self) -> None:
        symbols = _valid_symbols(service.MIN_BATCH_SIZE)
        run_id = uuid.uuid4().hex
        universe, _batch, task, transport, success = _worker_fixture(symbols, run_id=run_id)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                store = SQLiteMetaStore(root / "meta.sqlite")
                store.write_task_status(task)
                checkpoint = service._write_checkpoint(
                    run_id=run_id,
                    universe=universe,
                    batches=[symbols],
                    successes=[success],
                    status="partial_failure_resume_available",
                    transport=transport,
                )
                verifier = MagicMock(return_value=False)
                resumed = service._validated_resume_successes(
                    checkpoint,
                    run_id=run_id,
                    universe=universe,
                    batches=[symbols],
                    transport=transport,
                    execution_event=_transport_event_fixture(transport),
                    resume_proof_verifier=verifier,
                )
        self.assertEqual(resumed, [])
        verifier.assert_called_once()

    def test_public_resume_without_external_receipt_never_promotes(self) -> None:
        symbols = _valid_symbols(service.MIN_BATCH_SIZE)
        run_id = uuid.uuid4().hex
        universe, _batch, task, transport, success = _worker_fixture(symbols, run_id=run_id)
        client = MagicMock()
        client.get.return_value = None
        fake_app = types.SimpleNamespace(
            backend=types.SimpleNamespace(client=client),
            close=MagicMock(),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                store = SQLiteMetaStore(root / "meta.sqlite")
                sentinel = {"status": "existing-production", "marker": "preserve"}
                store.write_packet(service.PACKET_KEY, sentinel)
                store.write_packet(service.LAST_GOOD_PACKET_KEY, sentinel)
                store.write_packet(service._transport_key(run_id), transport)
                store.write_packet(
                    service._execution_event_key(run_id),
                    _transport_event_fixture(transport),
                )
                store.write_task_status(task)
                service._write_checkpoint(
                    run_id=run_id,
                    universe=universe,
                    batches=[symbols],
                    successes=[success],
                    status="partial_failure_resume_available",
                    transport=transport,
                )
                with patch.object(
                    service,
                    "_authoritative_provider_universe",
                    return_value=universe,
                ), patch.object(
                    service,
                    "_build_and_probe_official_transport",
                    return_value=(fake_app, transport),
                ):
                    result = service.run_full_market_worker_production_acceptance(
                        {"operator_approved": True, "resume_run_id": run_id}
                    )
                self.assertEqual(
                    result["status"],
                    "full_market_worker_resume_checkpoint_invalid",
                )
                self.assertEqual(result["dispatch_count"], 0)
                self.assertEqual(store.read_packet(service.PACKET_KEY), sentinel)
                self.assertEqual(store.read_packet(service.LAST_GOOD_PACKET_KEY), sentinel)
        client.get.assert_called()

    def test_partition_keeps_every_batch_within_real_worker_bounds(self) -> None:
        batches = service._partition_symbols(_valid_symbols(3001), 100)
        self.assertEqual(sum(len(batch) for batch in batches), 3001)
        self.assertTrue(all(service.MIN_BATCH_SIZE <= len(batch) <= service.MAX_BATCH_SIZE for batch in batches))

    def test_uuid4_identity_and_independent_rollback_steps(self) -> None:
        value = "123456781234423481234567890abcde"
        self.assertEqual(service._normalize_uuid4(value), value)
        self.assertEqual(service._normalize_uuid4("not-a-uuid"), "")
        snapshots = {
            name: service._promotion_snapshot_entry(name, {})
            for name in service._promotion_snapshot_targets()
        }
        journal = {
            "schema_version": service.PROMOTION_JOURNAL_SCHEMA_VERSION,
            "status": "current_pointer_promoted",
            "acceptance_run_id": value,
            "snapshots": snapshots,
            "contains_secret": False,
        }
        journal["journal_binding_digest"] = service._canonical_digest(
            {
                "schema_version": service.PROMOTION_JOURNAL_SCHEMA_VERSION,
                "acceptance_run_id": value,
                "snapshots": snapshots,
            }
        )
        with patch.object(
            service,
            "_restore_pointer",
            side_effect=[False, True],
        ) as restore_pointer, patch.object(
            service,
            "_restore_packet",
            side_effect=[False, True],
        ) as restore_packet, patch.object(
            service,
            "_update_promotion_journal",
            side_effect=lambda packet, status, **fields: {**packet, "status": status, **fields},
        ):
            rollback = service._rollback_from_promotion_journal(journal, reason="counterexample")
        self.assertEqual(restore_pointer.call_count, 2)
        self.assertEqual(restore_packet.call_count, 2)
        self.assertFalse(rollback["complete"])
        self.assertEqual(
            rollback["results"],
            {
                "current_pointer": False,
                "last_good_pointer": True,
                "current_packet": False,
                "last_good_packet": True,
            },
        )

    def test_invalid_or_unknown_journal_recovers_with_zero_mutations(self) -> None:
        run_id = uuid.uuid4().hex
        pointer_values = {
            "current": {"marker": "current-pointer"},
            "last_good": {"marker": "last-good-pointer"},
        }
        packet_values = {
            service.PACKET_KEY: {"marker": "current-packet"},
            service.LAST_GOOD_PACKET_KEY: {"marker": "last-good-packet"},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                store = SQLiteMetaStore(root / "meta.sqlite")
                for key, value in packet_values.items():
                    store.write_packet(key, value)
                for pointer, value in pointer_values.items():
                    service._atomic_write_json(
                        root / "parquet" / service.RESULT_DATASET / f"{pointer}.json",
                        value,
                    )
                snapshots = {
                    name: service._promotion_snapshot_entry(name, {})
                    for name in service._promotion_snapshot_targets()
                }
                binding = service._canonical_digest(
                    {
                        "schema_version": service.PROMOTION_JOURNAL_SCHEMA_VERSION,
                        "acceptance_run_id": run_id,
                        "snapshots": snapshots,
                    }
                )
                invalid_journals = {
                    "missing_snapshot_digests": {
                        "schema_version": service.PROMOTION_JOURNAL_SCHEMA_VERSION,
                        "status": "current_pointer_promoted",
                        "acceptance_run_id": run_id,
                        "snapshots": {name: {} for name in snapshots},
                        "journal_binding_digest": binding,
                        "contains_secret": False,
                    },
                    "unknown_status": {
                        "schema_version": service.PROMOTION_JOURNAL_SCHEMA_VERSION,
                        "status": "forged",
                        "acceptance_run_id": run_id,
                        "snapshots": snapshots,
                        "journal_binding_digest": binding,
                        "contains_secret": False,
                    },
                }
                for name, journal in invalid_journals.items():
                    with self.subTest(name=name):
                        service._atomic_write_json(service._promotion_journal_path(), journal)
                        with patch.object(service, "_restore_pointer") as restore_pointer, patch.object(
                            service,
                            "_restore_packet",
                        ) as restore_packet:
                            recovery = service._recover_interrupted_promotion()
                        self.assertFalse(recovery["ready"])
                        self.assertEqual(recovery["status"], "promotion_journal_invalid")
                        restore_pointer.assert_not_called()
                        restore_packet.assert_not_called()
                        for key, value in packet_values.items():
                            self.assertEqual(store.read_packet(key), value)
                        for pointer, value in pointer_values.items():
                            self.assertEqual(
                                service._read_json(
                                    root / "parquet" / service.RESULT_DATASET / f"{pointer}.json"
                                ),
                                value,
                            )

    def test_partial_dispatch_revokes_and_quarantines_accepted_task(self) -> None:
        batches = [
            _valid_symbols(service.MIN_BATCH_SIZE),
            _valid_symbols(service.MIN_BATCH_SIZE * 2)[service.MIN_BATCH_SIZE :],
        ]
        universe = {
            "scope_hash": SCOPE_HASH,
            "version_digest": "b" * 64,
            "universe_digest": service._canonical_digest(sorted(set(sum(batches, [])))),
            "minimum_universe_size": service.DEFAULT_MINIMUM_UNIVERSE_SIZE,
            "_frames": _verified_frames(sorted(set(sum(batches, [])))),
        }
        transport = {"eligible_worker_names": ["worker@host"]}
        app = _PartialDispatchApp()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                successes, dispatched = service._dispatch_batches(
                    app,
                    batches=batches,
                    run_id="partialdispatch123",
                    universe=universe,
                    transport=transport,
                    timeout_seconds=60,
                    challenge_issuer=lambda _spec: uuid.uuid4().hex,
                    challenge_verifier=lambda _task, _spec: True,
                    challenge_cleanup=lambda _ids: None,
                )
                quarantine = SQLiteMetaStore(root / "meta.sqlite").read_packet(
                    f"{service.ATTEMPT_PACKET_KEY}:quarantine:partialdispatch123"
                )
        self.assertEqual(successes, [])
        self.assertEqual(len(dispatched), 1)
        self.assertTrue(dispatched[0].startswith("fmw-partialdispatch123-0000-"))
        self.assertRegex(dispatched[0].rsplit("-", 1)[-1], r"^[0-9a-f]{32}$")
        self.assertEqual(app.control.revoked, [(dispatched[0], False)])
        self.assertEqual(quarantine["status"], "late_results_quarantined")
        self.assertEqual(quarantine["reason"], "dispatch_exception")
        self.assertFalse(quarantine["global_candidate_cache_overwritten"])

    def test_timeout_late_task_id_is_quarantined_and_not_reused(self) -> None:
        symbols = _valid_symbols(service.MIN_BATCH_SIZE)
        shared = _shared_provider_result(symbols)
        universe = {
            **shared,
            "_frames": shared["frames"],
            "minimum_universe_size": service.DEFAULT_MINIMUM_UNIVERSE_SIZE,
        }
        transport = {"eligible_worker_names": ["worker@host"]}
        app = _TimeoutApp()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                first_success, first_ids = service._dispatch_batches(
                    app,
                    batches=[symbols],
                    run_id="timeoutlate123",
                    universe=universe,
                    transport=transport,
                    timeout_seconds=60,
                    challenge_issuer=lambda _spec: uuid.uuid4().hex,
                    challenge_verifier=lambda _task, _spec: True,
                    challenge_cleanup=lambda _ids: None,
                )
                second_success, second_ids = service._dispatch_batches(
                    app,
                    batches=[symbols],
                    run_id="timeoutlate123",
                    universe=universe,
                    transport=transport,
                    timeout_seconds=60,
                    challenge_issuer=lambda _spec: uuid.uuid4().hex,
                    challenge_verifier=lambda _task, _spec: True,
                    challenge_cleanup=lambda _ids: None,
                )
                quarantine = SQLiteMetaStore(root / "meta.sqlite").read_packet(
                    service._quarantine_key("timeoutlate123")
                )
        self.assertEqual(first_success, [])
        self.assertEqual(second_success, [])
        self.assertNotEqual(first_ids, second_ids)
        self.assertEqual(set(quarantine["celery_task_ids"]), {first_ids[0], second_ids[0]})

    def test_blocked_after_good_and_double_rollback_failure_do_not_promote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_good = {"status": "old-good", "marker": "preserve"}
            store = SQLiteMetaStore(root / "meta.sqlite")
            store.write_packet(service.PACKET_KEY, old_good)
            store.write_packet(service.LAST_GOOD_PACKET_KEY, old_good)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                service._blocked_attempt("new_attempt_blocked", run_id="blocked123")
            self.assertEqual(store.read_packet(service.PACKET_KEY), old_good)
            self.assertEqual(store.read_packet(service.LAST_GOOD_PACKET_KEY), old_good)

            rows = [
                {
                    "ts_code": "000001.SZ",
                    "score": 50,
                    "rough_score": 50,
                    "full_market_rank": 1,
                    "batch_index": 0,
                    "celery_task_id": "fmw-double-0000",
                    "worker_task_id": "worker-double",
                    "candidate_is_not_buy_instruction": True,
                    "does_not_execute_trades": True,
                }
            ]
            universe = {
                "scope_hash": SCOPE_HASH,
                "universe_digest": service._canonical_digest(["000001.SZ"]),
                "universe_count": 1,
                "minimum_universe_size": service.DEFAULT_MINIMUM_UNIVERSE_SIZE,
                "validated_trade_date": "20260710",
            }
            checkpoint = {
                "batch_count": 1,
                "successful_batches": [
                    {"celery_task_id": "fmw-double-0000", "worker_task_id": "worker-double"}
                ],
            }
            transport = {"status": "fixture-not-direct"}
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2], patch.object(
                service,
                "_restore_pointer",
            ) as restore_pointer, patch.object(service, "_restore_packet") as restore_packet:
                result = service._promote_candidate_results(
                    run_id="doublefail123",
                    universe=universe,
                    transport=transport,
                    checkpoint=checkpoint,
                    result_rows=rows,
                )
            self.assertFalse(result["production_worker_complete"])
            self.assertEqual(result["status"], "full_market_worker_module_level_promotion_disabled")
            restore_pointer.assert_not_called()
            restore_packet.assert_not_called()
            fact = service.validate_full_market_worker_production_fact(root)
            self.assertFalse(fact["ready"])
            self.assertEqual(store.read_packet(service.LAST_GOOD_PACKET_KEY), old_good)

    def test_module_level_self_seal_cannot_create_production_truth(self) -> None:
        run_id = uuid.uuid4().hex
        symbols = _valid_symbols(service.MIN_BATCH_SIZE)
        universe, batch, _task, transport, success = _worker_fixture(symbols, run_id=run_id)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = SQLiteMetaStore(root / "meta.sqlite")
            sentinel = {"status": "existing-last-good", "marker": "preserve"}
            store.write_packet(service.PACKET_KEY, sentinel)
            store.write_packet(service.LAST_GOOD_PACKET_KEY, sentinel)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                persisted_transport, persisted_event = service._persist_transport_execution_event_atomic(
                    run_id,
                    transport,
                )
                worker_result = service.execute_candidate_radar_batch_worker(
                    {
                        **batch,
                        "celery_dispatch_id": batch["celery_task_id"],
                        "full_market_worker_acceptance": True,
                        "feature_contract_digest": service.FEATURE_CONTRACT_DIGEST,
                        "universe_digest": universe["universe_digest"],
                        "provider_scope_hash": universe["scope_hash"],
                        "provider_version_digest": universe["version_digest"],
                    },
                    runtime={
                        "bound_task_request": True,
                        "synthetic_fixture": False,
                        "celery_request_id": batch["celery_task_id"],
                        "worker_hostname": "worker@host",
                        "worker_pid": 999,
                        "worker_queue": service.CANDIDATE_QUEUE,
                        "worker_challenge_consumed": True,
                        "worker_execution_proof": "f" * 64,
                    },
                )
                promoted = service._promote_candidate_results(
                    run_id=run_id,
                    universe=universe,
                    transport=transport,
                    checkpoint={"batch_count": 1, "successful_batches": [success]},
                    result_rows=service._score_candidate_rows(universe, symbols),
                )
                fact = service.validate_full_market_worker_production_fact(root)
            self.assertEqual((persisted_transport, persisted_event), ({}, {}))
            self.assertEqual(worker_result["status"], "failed")
            self.assertEqual(promoted["status"], "full_market_worker_module_level_promotion_disabled")
            self.assertFalse(fact["ready"])
            self.assertEqual(store.read_packet(service.PACKET_KEY), sentinel)
            self.assertEqual(store.read_packet(service.LAST_GOOD_PACKET_KEY), sentinel)

    def test_task_catalog_and_route_cover_explicit_post(self) -> None:
        from server.services import worker_service

        catalog = {row["task_type"]: row for row in task_service.TASK_CATALOG}
        item = catalog["run_candidate_radar_full_market_production_acceptance"]
        self.assertEqual(item["route"], "POST /api/worker/full-market-production-acceptance")
        self.assertTrue(item["requires_provider_current_and_last_good"])
        self.assertTrue(item["call_ledger_required"])
        self.assertEqual(
            worker_service._queue_for_task_type(
                "run_candidate_radar_full_market_production_acceptance"
            ),
            "worker_production",
        )
        # Newer FastAPI/Starlette versions can expose internal included routers
        # in ``app.routes`` instead of flattening their concrete children. Walk
        # the route tree so this contract remains version-independent while
        # still asserting the actual POST route.
        def concrete_routes(routes):
            for route in routes:
                effective = getattr(route, "effective_route_contexts", None)
                if effective is not None:
                    yield from (
                        context
                        for context in effective()
                        if hasattr(context, "path") and hasattr(context, "methods")
                    )
                    continue
                children = getattr(route, "routes", None)
                if children is not None:
                    yield from concrete_routes(children)
                elif hasattr(route, "path") and hasattr(route, "methods"):
                    yield route

        methods = {
            route.path: route.methods
            for route in concrete_routes(app.routes)
        }
        self.assertEqual(methods["/api/worker/full-market-production-acceptance"], {"POST"})
        response = TestClient(app).get("/api/tasks/catalog")
        self.assertEqual(response.status_code, 200)
        routed_catalog = {
            row["task_type"]: row for row in response.json()["data"]["tasks"]
        }
        self.assertIn("run_candidate_radar_full_market_production_acceptance", routed_catalog)
        self.assertFalse(response.json()["data"]["external_calls_triggered"])

    def test_bound_task_fallback_preserves_legacy_payload_signature(self) -> None:
        from worker import celery_app as celery_module

        with patch.object(celery_module, "celery_app", None):
            @celery_module.task("legacy-signature-proof", bind=True)
            def bound(_self, payload=None):
                return payload

            payload = {"symbols": ["000001.SZ"]}
            self.assertEqual(bound(payload), payload)


if __name__ == "__main__":
    unittest.main()
