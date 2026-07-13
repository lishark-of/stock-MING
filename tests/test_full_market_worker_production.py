from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from server.main import app
from server.services import full_market_worker_service as service
from server.services import task_service
from storage.sqlite_meta import SQLiteMetaStore


SCOPE_HASH = "a" * 64


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


def _provider_ledger(api: str) -> dict:
    return {
        "api": api,
        "call_status": "success",
        "row_count": 1,
        "external_calls_triggered": True,
        "tushare_called": True,
        "real_provider_adapter_used": True,
        "provider_provenance_validator": True,
        "scope_hash": SCOPE_HASH,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _write_synthetic_provider(root: Path, symbols: list[str]) -> None:
    artifact = root / "parquet" / service.PROVIDER_DATASET / "versions" / SCOPE_HASH / "stock_basic.parquet"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "ts_code": symbol,
                "symbol": symbol.split(".")[0],
                "name": f"fixture-{index}",
                "market": "主板",
                "exchange": symbol.split(".")[-1],
                "list_status": "L",
                "delist_date": "",
                "provider_scope_hash": SCOPE_HASH,
            }
            for index, symbol in enumerate(symbols)
        ]
    ).to_parquet(artifact, index=False)
    digest = service._sha256_file(artifact)
    relpath = str(artifact.relative_to(root))
    packet = {
        "schema_version": service.PROVIDER_SCHEMA_VERSION,
        "status": service.PROVIDER_COMPLETE_STATUS,
        "scope_hash": SCOPE_HASH,
        "universe_digest": service._canonical_digest(sorted(set(symbols))),
        "universe_count": len(set(symbols)),
        "validated_trade_date": "20260710",
        "as_of_date": "20260713",
        "artifact_manifest_digest": "b" * 64,
        "stock_basic_artifact_sha256": digest,
        "stock_basic_row_count": len(symbols),
        "trade_calendar_validated": True,
        "provider_provenance_validator": True,
        "real_provider_adapter_used": True,
        "durable_stage_readback_verified": True,
        "durable_final_promotion_verified": True,
        "synthetic_fixture": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "call_ledger": [
            _provider_ledger(api)
            for api in ("stock_basic", "trade_cal", "daily", "daily_basic", "moneyflow")
        ],
        "artifacts": {
            "stock_basic": {
                "path": relpath,
                "sha256": digest,
                "row_count": len(symbols),
                "date_start": "20260710",
                "date_end": "20260710",
                "symbol_count": len(set(symbols)),
            }
        },
    }
    store = SQLiteMetaStore(root / "meta.sqlite")
    store.write_packet(service.PROVIDER_CURRENT_KEY, packet)
    store.write_packet(service.PROVIDER_LAST_GOOD_KEY, packet)
    service._atomic_write_json(
        root / "parquet" / service.PROVIDER_DATASET / "current.json",
        {
            "schema_version": "tushare_full_market_universe_pointer.v1",
            "status": service.PROVIDER_COMPLETE_STATUS,
            "scope_hash": SCOPE_HASH,
            "artifact_relpath": relpath,
            "artifact_sha256": digest,
            "row_count": len(symbols),
            "validated_trade_date": "20260710",
        },
    )


def _score_universe(symbol: str = "000001.SZ") -> dict:
    dates = pd.bdate_range("2026-04-20", periods=service.MIN_DAILY_SESSIONS)
    date_values = [date.strftime("%Y%m%d") for date in dates]
    daily = pd.DataFrame(
        {
            "ts_code": [symbol] * len(dates),
            "trade_date": date_values,
            "close": [10 + index * 0.05 for index in range(len(dates))],
            "amount": [200000.0] * len(dates),
            "provider_scope_hash": [SCOPE_HASH] * len(dates),
        }
    )
    basic = pd.DataFrame(
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
                "provider_scope_hash": SCOPE_HASH,
            }
        ]
    )
    flow = pd.DataFrame(
        [
            {
                "ts_code": symbol,
                "trade_date": date,
                "buy_lg_amount": 20.0,
                "sell_lg_amount": 10.0,
                "buy_elg_amount": 10.0,
                "sell_elg_amount": 5.0,
                "provider_scope_hash": SCOPE_HASH,
            }
            for date in date_values[-service.MIN_MONEYFLOW_SESSIONS :]
        ]
    )
    return {
        "ready": True,
        "symbols": [symbol],
        "scope_hash": SCOPE_HASH,
        "universe_digest": service._canonical_digest([symbol]),
        "validated_trade_date": date_values[-1],
        "_frames": {"daily": daily, "daily_basic": basic, "moneyflow": flow},
    }


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
        self.control = _DispatchControl()
        self.sent: list[str] = []

    def send_task(self, name, args, task_id, queue, routing_key):
        self.sent.append(task_id)
        if len(self.sent) == 2:
            raise ConnectionError("broker stopped after first accepted task")
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

            _write_synthetic_provider(root, _valid_symbols(7))
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2], patch.object(
                service, "_load_celery_app"
            ) as loader:
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
            _write_synthetic_provider(root, ["000001.SH", "600000.SZ", "200001.SZ", "900001.SH"])
            universe = service._authoritative_provider_universe(
                root,
                minimum_universe_size=service.DEFAULT_MINIMUM_UNIVERSE_SIZE,
            )
            self.assertFalse(universe["ready"])
            self.assertIn("provider_current_strict_validation_failed", universe["blockers"])
            self.assertIn("provider_stock_basic_contains_invalid_a_share_codes", universe["blockers"])

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
        self.assertEqual(attestation["status"], "registered_task_or_queue_missing")

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
        self.assertNotEqual(set(row), {"ts_code"})

    def test_partial_resume_without_worker_task_is_rejected(self) -> None:
        symbols = _valid_symbols(service.MIN_BATCH_SIZE)
        universe = {
            "scope_hash": SCOPE_HASH,
            "universe_digest": service._canonical_digest(symbols),
        }
        checkpoint = {
            "schema_version": service.CHECKPOINT_SCHEMA_VERSION,
            "synthetic_fixture": False,
            "acceptance_run_id": "resume123",
            "provider_scope_hash": SCOPE_HASH,
            "universe_digest": universe["universe_digest"],
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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                self.assertEqual(
                    service._validated_resume_successes(checkpoint, universe=universe, batches=[symbols]),
                    [],
                )

    def test_partition_keeps_every_batch_within_real_worker_bounds(self) -> None:
        batches = service._partition_symbols(_valid_symbols(3001), 100)
        self.assertEqual(sum(len(batch) for batch in batches), 3001)
        self.assertTrue(all(service.MIN_BATCH_SIZE <= len(batch) <= service.MAX_BATCH_SIZE for batch in batches))

    def test_partial_dispatch_revokes_and_quarantines_accepted_task(self) -> None:
        batches = [
            _valid_symbols(service.MIN_BATCH_SIZE),
            _valid_symbols(service.MIN_BATCH_SIZE * 2)[service.MIN_BATCH_SIZE :],
        ]
        universe = {
            "scope_hash": SCOPE_HASH,
            "universe_digest": service._canonical_digest(sorted(set(sum(batches, [])))),
            "minimum_universe_size": service.DEFAULT_MINIMUM_UNIVERSE_SIZE,
        }
        app = _PartialDispatchApp()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _patch_root(root)[0], _patch_root(root)[1], _patch_root(root)[2]:
                successes, dispatched = service._dispatch_batches(
                    app,
                    batches=batches,
                    run_id="partialdispatch123",
                    universe=universe,
                    timeout_seconds=60,
                )
                quarantine = SQLiteMetaStore(root / "meta.sqlite").read_packet(
                    f"{service.ATTEMPT_PACKET_KEY}:quarantine:partialdispatch123"
                )
        self.assertEqual(successes, [])
        self.assertEqual(dispatched, ["fmw-partialdispatch123-0000"])
        self.assertEqual(app.control.revoked, [("fmw-partialdispatch123-0000", False)])
        self.assertEqual(quarantine["status"], "late_results_quarantined")
        self.assertEqual(quarantine["reason"], "dispatch_exception")
        self.assertFalse(quarantine["global_candidate_cache_overwritten"])

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
            with (
                _patch_root(root)[0],
                _patch_root(root)[1],
                _patch_root(root)[2],
                patch.object(service, "validate_full_market_worker_production_fact", return_value={"ready": False}),
                patch.object(service, "_restore_pointer", return_value=False),
                patch.object(service, "_restore_packet", return_value=False),
            ):
                result = service._promote_candidate_results(
                    run_id="doublefail123",
                    universe=universe,
                    transport=transport,
                    checkpoint=checkpoint,
                    result_rows=rows,
                )
            self.assertFalse(result["production_worker_complete"])
            self.assertFalse(result["pointer_rollback_verified"])
            self.assertFalse(result["packet_rollback_verified"])
            fact = service.validate_full_market_worker_production_fact(root)
            self.assertFalse(fact["ready"])
            self.assertEqual(store.read_packet(service.LAST_GOOD_PACKET_KEY), old_good)

    def test_task_catalog_and_route_cover_explicit_post(self) -> None:
        catalog = {row["task_type"]: row for row in task_service.TASK_CATALOG}
        item = catalog["run_candidate_radar_full_market_production_acceptance"]
        self.assertEqual(item["route"], "POST /api/worker/full-market-production-acceptance")
        self.assertTrue(item["requires_provider_current_and_last_good"])
        methods = {route.path: route.methods for route in app.routes}
        self.assertEqual(methods["/api/worker/full-market-production-acceptance"], {"POST"})
        response = TestClient(app).get("/api/tasks/catalog")
        self.assertEqual(response.status_code, 200)
        routed_catalog = {
            row["task_type"]: row for row in response.json()["data"]["tasks"]
        }
        self.assertIn("run_candidate_radar_full_market_production_acceptance", routed_catalog)
        self.assertFalse(response.json()["data"]["external_calls_triggered"])


if __name__ == "__main__":
    unittest.main()
