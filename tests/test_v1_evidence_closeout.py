from __future__ import annotations

import json
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from server.services import v1_closeout_service
from tests.test_motion_current_head_evidence import write_attested_pair


def _safe_boundary(*, external: bool = False, tushare: bool = False) -> dict:
    return {
        "external_calls_triggered": external,
        "tushare_called": tushare,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(str(path.stat().st_mode & 0o777).encode("ascii"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_packets(path: Path, packets: dict[str, dict], tasks: list[dict] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE packets (packet_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?)",
            [
                (packet_key, json.dumps(payload), "2026-07-13T00:00:00+00:00")
                for packet_key, payload in packets.items()
            ],
        )
        if tasks is not None:
            connection.execute(
                "CREATE TABLE task_status "
                "(task_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            connection.executemany(
                "INSERT INTO task_status(task_id, payload_json, updated_at) VALUES (?, ?, ?)",
                [
                    (f"fixture-{index}", json.dumps(payload), "2026-07-13T00:00:00+00:00")
                    for index, payload in enumerate(tasks)
                ],
            )


def _qmt_receipt() -> dict:
    payload = {
        "schema_version": "qmt_readonly_local_replay_result.v1",
        "status": "local_scope_replay_verified_export_pending",
        "mode": "local_research_replay",
        "external_call_count": 0,
        "qmt_called": False,
        "qmt_connection_count": 0,
        "qmt_external_connection_attempted": False,
        "qmt_process_discovered": False,
        "qmt_client_imported": False,
        "xtquant_imported": False,
        "broker_called": False,
        "broker_session_opened": False,
        "broker_session_count": 0,
        "account_query_executed": False,
        "real_order_submitted": False,
        "real_order_count": 0,
        "real_order_cancelled": False,
        "real_trade_executed": False,
        "real_trade_count": 0,
        "real_holdings_modified": False,
        "real_trading_enabled": False,
        "external_qmt_integration_verified": False,
        "paper_trading_sandbox_ready": False,
        "worker_dispatched": False,
        "does_not_modify_holdings": True,
    }
    payload.update(_safe_boundary())
    return payload


def _seed_complete_local_versions(root: Path) -> None:
    user_qa = {
        "schema_version": "command_center_3_user_route_qa_result.v1",
        "status": "user_route_qa_passed",
        "passed_count": 2,
        **_safe_boundary(),
    }
    _write_json(
        root / "user_route_home_after_collapse_smoke" / "fixture" / "user_route_qa_report.json",
        user_qa,
    )
    _write_json(
        root / "user_route_factor_after_amend_smoke" / "fixture" / "user_route_qa_report.json",
        user_qa,
    )
    provider_base = {
        "schema_version": "command_center_tushare_refresh_task.v1",
        "status": "success",
        "call_count": 1,
        "success_count": 1,
        "failed_count": 0,
        "blocked_count": 0,
        **_safe_boundary(external=True, tushare=True),
    }
    trade_cal = {**provider_base, "selected_apis": ["trade_cal"], "production_tushare_pipeline_complete": False}
    factor = {
        **provider_base,
        "call_count": 2,
        "success_count": 2,
        "selected_apis": ["daily", "daily_basic"],
        "production_tushare_pipeline_complete": False,
    }
    _write_packets(
        root / "meta.sqlite",
        {
            "command_center_trade_cal_provider_acceptance_packet": trade_cal,
            "command_center_factor_test_provider_small_pool_tushare_packet": factor,
            "command_center_3_qmt_replay_current": _qmt_receipt(),
        },
    )

    storage = {
        "schema_version": "command_center_3_storage_physical_execution_phase_a.v1",
        "status": "storage_v04_physical_execution_injected_failure_current_unchanged",
        "production_storage_complete": False,
        **_safe_boundary(),
    }
    worker = {
        "schema_version": "worker_v04_local_batch_runtime_packet.v1",
        "status": "worker_v04_local_batch_runtime_success",
        "pool_count": 60,
        "processed_count": 60,
        "contains_secret": False,
    }
    _write_packets(
        root / "v04_acceptance_runtime" / "runtime_meta.sqlite",
        {
            "command_center_3_storage_physical_execution_phase_a_packet": storage,
            "command_center_3_worker_runtime_qa_execution_packet": worker,
        },
        tasks=[
            {
                "task_type": "run_storage_physical_execution_phase_a",
                "status": "success",
                "current_step": "storage_physical_execution_phase_a_v04_durable_execution_success",
            }
        ],
    )
    _write_json(
        root / "v04_acceptance_runtime" / "fixture" / "manifest.json",
        {
            "schema_version": "storage_v04_durable_execution_manifest.v1",
            "row_count": 8,
            "contains_secret": False,
        },
    )

    candidate = {
        "schema_version": "candidate_radar_cache.v1",
        "status": "candidate_radar_v05_local_batch_ready",
        **_safe_boundary(),
    }
    next_session = {
        "schema_version": "next_session_projection.v1",
        "status": "ready_cache_replay",
        "next_session_browser_qa_evidence_ready": True,
        "production_replacement_complete": False,
        **_safe_boundary(),
    }
    _write_packets(
        root / "v05_acceptance_runtime" / "meta.sqlite",
        {
            "command_center_3_candidate_radar_v05_last_good_packet": candidate,
            "command_center_next_session_projection_packet": next_session,
        },
    )

    desktop_base = {
        "schema_version": "tauri_packaged_runtime_smoke.v1",
        "status": "tauri_packaged_runtime_smoke_passed",
        "local_packaged_runtime_evidence_ready": True,
        "dmg_checksum_verified": True,
        "production_package_complete": False,
        "developer_id_signing_verified": False,
        "notarization_ticket_detected": False,
        **_safe_boundary(),
    }
    _write_json(root / "desktop_runtime" / "tauri_packaged_runtime_offline_smoke.json", desktop_base)
    _write_json(root / "desktop_runtime" / "tauri_packaged_runtime_online_smoke.json", desktop_base)
    write_attested_pair(root, head=v1_closeout_service._read_current_head_full())


class V1EvidenceCloseoutTests(unittest.TestCase):
    def test_full_interface_closeout_validator_accepts_only_consistent_independent_packet(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scope_hash = "a" * 64
            recipe_hash = "b" * 64
            selected = sorted(v1_closeout_service._FULL_INTERFACE_APIS)
            targets = sorted(v1_closeout_service._FULL_INTERFACE_TARGETS)
            approval_material = {
                "schema_version": "tushare_full_interface_provider_approval_scope.v1",
                "recipe_scope_hash": recipe_hash,
                "recipe_version": "tushare_full_interface_provider_recipe.v2",
                "selected_apis": selected,
                "requested_targets": targets,
                "api_contexts": {},
                "target_contexts": {},
                "universe_context": {},
            }
            approval_hash = v1_closeout_service._canonical_digest(approval_material)
            ledger = [
                {
                    "api": api,
                    "runtime_adapter_module_identity_verified": True,
                    "provider_transport_verified": True,
                    "provider_transport_receipt_count": 1,
                    "representative_sample_verified": True,
                    "valid_empty_semantics_verified": False,
                    "scope_hash": scope_hash,
                    "authoritative_recipe_scope_hash": recipe_hash,
                    "approval_scope_hash": approval_hash,
                    "approval_scope_matches": True,
                    "request_params_safe": {},
                }
                for api in selected
            ]
            parquet_rows = []
            import pandas as pd

            parquet_payloads = {
                "daily": {"ts_code": "000001.SZ", "trade_date": "20260710", "close": 10.0},
                "daily_basic": {"ts_code": "000001.SZ", "trade_date": "20260710", "turnover_rate": 1.0},
                "moneyflow": {"ts_code": "000001.SZ", "trade_date": "20260710", "buy_sm_amount": 1.0},
                "trade_cal": {"cal_date": "20260710", "is_open": 1},
            }
            for api in sorted(v1_closeout_service._PARQUET_APIS):
                path = root / f"{api}.parquet"
                pd.DataFrame([parquet_payloads[api]]).to_parquet(path, index=False)
                parquet_rows.append(
                    {
                        "api": api,
                        "canonical_path": str(path),
                        "canonical_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "row_count": 1,
                        "required_columns": list(parquet_payloads[api]),
                    }
                )
            packet = {
                "schema_version": "command_center_tushare_full_interface_production_packet.v1",
                "status": "full_interface_provider_production_complete",
                "full_interface_provider_production": True,
                "production_tushare_pipeline_complete": True,
                "selected_apis": selected,
                "required_target_groups": targets,
                "provider_scope": {"scope_hash": scope_hash},
                "execution_recipe_scope_hash": recipe_hash,
                "execution_recipe_version": "tushare_full_interface_provider_recipe.v2",
                "approval_scope_matches": True,
                "approval_scope_hash": approval_hash,
                "api_contexts": {},
                "target_contexts": {},
                "universe_context": {},
                "production_contract": {
                    "schema_version": "tushare_full_interface_provider_production_acceptance.v2",
                    "status": "full_interface_provider_production_complete",
                    "scope_hash": scope_hash,
                    "full_interface_provider_production": True,
                    "production_tushare_pipeline_complete": True,
                    "parquet_promotion_verified": True,
                    "sqlite_stage_readback_verified": True,
                    "sqlite_atomic_promotion_verified": True,
                    "blocking_criterion_count": 0,
                    "blockers": [],
                },
                "call_ledger": ledger,
                "parquet_promotion": {
                    "promotion_verified": True,
                    "promoted_dataset_count": 4,
                    "rows": parquet_rows,
                },
                "sqlite_stage_readback_verified": True,
                "sqlite_atomic_promotion_verified": True,
                **_safe_boundary(external=True, tushare=True),
            }
            packet["immutable_packet_digest"] = v1_closeout_service._canonical_digest(packet)
            self.assertTrue(v1_closeout_service._legacy_full_interface_packet_internally_consistent(packet))
            packet["call_ledger"][0]["provider_transport_verified"] = False
            self.assertFalse(v1_closeout_service._legacy_full_interface_packet_internally_consistent(packet))

    def test_missing_evidence_stays_false_without_creating_storage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "missing"
            packet = v1_closeout_service.build_v1_closeout_evaluation(evidence_root=root)

            self.assertFalse(root.exists())
            self.assertFalse(packet["local_direct_evidence_ready"])
            self.assertEqual(packet["strict_closeout"], "0/14")
            self.assertTrue(all(row["can_close"] is False for row in packet["ltg_closure_rows"]))
            self.assertFalse(packet["external_calls_triggered"])
            self.assertFalse(packet["writes_storage"])

    def test_v1_exposes_sanitized_factor_and_radar_validator_blockers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            worker = v1_closeout_service.full_market_worker_service
            _write_packets(
                root / "meta.sqlite",
                {
                    worker.PACKET_KEY: {
                        "status": "full_market_worker_production_complete",
                        "candidate_radar_production_replacement": True,
                        "global_candidate_cache_overwritten": True,
                    },
                    worker.FACTOR_PACKET_KEY: {
                        "status": "factor_full_market_worker_production_complete",
                        "full_market_factor_research": True,
                    },
                },
            )
            packet = v1_closeout_service.build_v1_closeout_evaluation(
                evidence_root=root
            )

        factor = packet["factor_full_market_research_summary"]
        radar = packet["candidate_radar_production_replacement_summary"]
        self.assertEqual(
            factor["validator"],
            "validate_factor_full_market_research_fact",
        )
        self.assertEqual(
            radar["validator"],
            "validate_full_market_worker_production_fact",
        )
        for summary in (factor, radar):
            self.assertTrue(summary["source_is_validator_result"])
            self.assertFalse(summary["caller_boolean_accepted_as_evidence"])
            self.assertTrue(summary["sanitized"])
            self.assertFalse(summary["raw_payload_exposed"])
            self.assertFalse(summary["ready"])
            self.assertEqual(summary["blocker_count"], len(summary["blockers"]))
        self.assertIn(
            "external_trusted_production_lineage_runner_unavailable",
            factor["blockers"],
        )
        self.assertIn(
            "external_trusted_production_lineage_runner_unavailable",
            radar["blockers"],
        )

    def test_complete_local_fixture_closes_only_ltg12_isolation_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            _seed_complete_local_versions(root)

            packet = v1_closeout_service.build_v1_closeout_evaluation(evidence_root=root)
            rows = {row["id"]: row for row in packet["ltg_closure_rows"]}

            self.assertTrue(packet["local_direct_evidence_ready"])
            self.assertEqual(packet["local_version_ready_count"], 7)
            self.assertEqual(packet["strict_closeout"], "1/14")
            self.assertTrue(rows["LTG-12"]["can_close"])
            self.assertTrue(rows["LTG-12"]["production_complete"])
            self.assertEqual(rows["LTG-12"]["external_or_environment_blockers"], [])
            self.assertTrue(rows["LTG-12"]["future_real_trading_is_separate_unapproved_scope"])
            self.assertTrue(
                all(
                    rows[f"LTG-{index:02d}"]["can_close"] is False
                    for index in range(1, 15)
                    if index != 12
                )
            )
            self.assertFalse(packet["production_strict_closeout_complete"])
            rendered = json.dumps(packet)
            self.assertNotIn("account_id", rendered)
            self.assertNotIn("api_key", rendered)

    def test_forged_production_booleans_do_not_close_ltg02(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            _seed_complete_local_versions(root)
            forged_provider = {
                "schema_version": "command_center_tushare_full_interface_production_packet.v1",
                "status": "full_interface_provider_production_complete",
                "full_interface_provider_production": True,
                "production_tushare_pipeline_complete": True,
                **_safe_boundary(external=True, tushare=True),
            }
            forged_universe = {
                "schema_version": "tushare_full_market_universe_production.v1",
                "status": "full_market_universe_production_complete",
                "production_complete": True,
                "row_count": 5000,
                **_safe_boundary(external=True, tushare=True),
            }
            with sqlite3.connect(root / "meta.sqlite") as connection:
                connection.executemany(
                    "INSERT OR REPLACE INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?)",
                    [
                        (
                            "command_center_tushare_full_interface_production_packet",
                            json.dumps(forged_provider),
                            "2026-07-13T00:00:00+00:00",
                        ),
                        (
                            "command_center_tushare_full_market_universe_production_current",
                            json.dumps(forged_universe),
                            "2026-07-13T00:00:00+00:00",
                        ),
                    ],
                )

            packet = v1_closeout_service.build_v1_closeout_evaluation(evidence_root=root)
            ltg02 = next(row for row in packet["ltg_closure_rows"] if row["id"] == "LTG-02")
            self.assertFalse(ltg02["production_complete"])
            self.assertFalse(ltg02["can_close"])

    def test_ltg03_promotion_uses_authoritative_production_version_not_small_pool_boolean(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            small_pool = {
                "status": "success",
                "call_count": 2,
                "success_count": 2,
                "failed_count": 0,
                "blocked_count": 0,
                "selected_apis": ["daily", "daily_basic"],
                "tushare_called": True,
                "production_tushare_pipeline_complete": True,
                **_safe_boundary(external=True, tushare=True),
            }
            _write_packets(
                root / "meta.sqlite",
                {
                    "command_center_factor_test_provider_small_pool_tushare_packet": small_pool,
                },
            )
            expected_head = "a" * 40

            with patch.object(
                v1_closeout_service,
                "validate_tushare_full_market_production_version",
                return_value={"ready": False, "blockers": ["authoritative_version_missing"]},
            ):
                _, blocked_facts, _ = v1_closeout_service._build_version_rows(
                    root,
                    expected_head_full=expected_head,
                )
            self.assertTrue(blocked_facts["factor_small_pool_provider_direct"])
            self.assertFalse(blocked_facts["factor_production_promotion"])

            small_pool.pop("production_tushare_pipeline_complete")
            (root / "meta.sqlite").unlink()
            _write_packets(
                root / "meta.sqlite",
                {
                    "command_center_factor_test_provider_small_pool_tushare_packet": small_pool,
                },
            )
            with patch.object(
                v1_closeout_service,
                "validate_tushare_full_market_production_version",
                return_value={"ready": True, "blockers": []},
            ):
                _, ready_facts, _ = v1_closeout_service._build_version_rows(
                    root,
                    expected_head_full=expected_head,
                )
            self.assertTrue(ready_facts["factor_small_pool_provider_direct"])
            self.assertTrue(ready_facts["factor_production_promotion"])

    def test_single_storage_boolean_cannot_create_production_fact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            head = "a" * 40
            _write_packets(
                root / "v04_acceptance_runtime" / "runtime_meta.sqlite",
                {
                    "command_center_3_storage_physical_execution_phase_a_packet": {
                        "schema_version": "command_center_3_storage_physical_execution_phase_a.v1",
                        "head_full": head,
                        "status": "storage_v04_physical_execution_success",
                        "production_storage_complete": True,
                        **_safe_boundary(),
                    }
                },
            )

            _, facts, context = v1_closeout_service._build_version_rows(
                root,
                expected_head_full=head,
            )

            self.assertFalse(facts["production_storage"])
            validation = context["storage_production_fact_validation"]
            self.assertTrue(validation["exact_schema_validated"])
            self.assertTrue(validation["current_head_binding_validated"])
            self.assertFalse(validation["trusted_external_production_validator_ready"])
            self.assertFalse(validation["production_storage_complete"])
            self.assertIn(
                "trusted_external_storage_production_validator_missing",
                validation["blockers"],
            )
            self.assertIn(
                "untrusted_local_production_storage_claim_rejected",
                validation["blockers"],
            )

    def test_candidate_worker_runtime_cannot_close_ltg04_factor_universe(self):
        version_rows = [
            {
                "version": version,
                "local_direct_evidence_ready": True,
            }
            for version in ("v0.1", "v0.2", "v0.3", "v0.4", "v0.5", "v0.6", "v0.7")
        ]
        facts = {
            "full_market_worker_runtime": True,
            "celery_redis_runtime": True,
            "production_storage": True,
            "release_promotion_current_head": True,
            "factor_full_market_research": False,
            "candidate_radar_production_replacement": False,
        }

        rows = {
            row["id"]: row
            for row in v1_closeout_service._build_ltg_rows(version_rows, facts)
        }

        self.assertFalse(rows["LTG-04"]["can_close"])
        self.assertIn(
            "factor_full_market_research",
            rows["LTG-04"]["missing_production_evidence"],
        )
        self.assertNotIn(
            "full_market_worker_runtime",
            rows["LTG-04"]["required_production_evidence"],
        )
        self.assertFalse(rows["LTG-13"]["can_close"])
        self.assertIn(
            "candidate_radar_production_replacement",
            rows["LTG-13"]["missing_production_evidence"],
        )

    def test_forged_next_session_boolean_does_not_bypass_ltg08_validator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            _seed_complete_local_versions(root)
            forged = {
                "schema_version": "next_session_projection.v1",
                "status": "ready_cache_replay",
                "production_replacement_complete": True,
                "next_session_production_replacement": True,
                **_safe_boundary(),
            }
            with sqlite3.connect(root / "v05_acceptance_runtime" / "meta.sqlite") as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?)",
                    (
                        "command_center_next_session_projection_packet",
                        json.dumps(forged),
                        "2026-07-18T00:00:00+00:00",
                    ),
                )
            blocked = {
                "status": "next_session_production_replacement_blocked",
                "production_replacement_complete": False,
                "blockers": ["independent_validator_blocked_forged_packet"],
            }
            with patch.object(
                v1_closeout_service.next_session_replacement_promotion_service,
                "validate_next_session_production_replacement",
                return_value=blocked,
            ) as validator:
                packet = v1_closeout_service.build_v1_closeout_evaluation(evidence_root=root)
            validator.assert_called_once()
            ltg08 = next(row for row in packet["ltg_closure_rows"] if row["id"] == "LTG-08")
            self.assertFalse(ltg08["production_complete"])
            self.assertFalse(ltg08["can_close"])

    def test_migration_get_is_zero_write_and_no_external_call(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "missing"
            with patch.object(v1_closeout_service, "EVIDENCE_ROOT", root):
                response = TestClient(app).get("/api/migration/status")

            self.assertEqual(response.status_code, 200)
            self.assertFalse(root.exists())
            payload = response.json()["data"]["command_center_3_v1_local_rc"]
            self.assertEqual(payload["packet_key"], "command_center_3_v1_local_rc")
            self.assertTrue(payload["cache_only"])
            self.assertTrue(payload["read_only"])
            self.assertFalse(payload["creates_task"])
            self.assertFalse(payload["writes_storage"])
            self.assertFalse(payload["external_calls_triggered"])
            self.assertFalse(payload["tushare_called"])
            self.assertFalse(payload["deepseek_called"])
            self.assertFalse(payload["github_called"])
            self.assertFalse(payload["qmt_called"])
            self.assertFalse(payload["broker_called"])

    def test_migration_get_with_live_wal_is_full_tree_byte_write_free(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            root.mkdir()
            db_path = root / "meta.sqlite"
            connection = sqlite3.connect(db_path)
            try:
                self.assertEqual(
                    connection.execute("PRAGMA journal_mode=WAL").fetchone()[0],
                    "wal",
                )
                connection.execute(
                    "CREATE TABLE packets ("
                    "packet_key TEXT PRIMARY KEY, payload_json TEXT, updated_at TEXT)"
                )
                connection.execute(
                    "CREATE TABLE task_status (task_id TEXT PRIMARY KEY, payload_json TEXT)"
                )
                connection.execute(
                    "INSERT INTO packets VALUES (?, ?, ?)",
                    (
                        "command_center_deepseek_provider_benchmark_current",
                        json.dumps({"status": "caller_boolean_must_not_be_trusted"}),
                        "2026-07-18T00:00:00+00:00",
                    ),
                )
                connection.commit()
                self.assertTrue(Path(f"{db_path}-wal").is_file())
                self.assertTrue(Path(f"{db_path}-shm").is_file())
                before = _tree_digest(root)

                with patch.object(v1_closeout_service, "EVIDENCE_ROOT", root):
                    response = TestClient(app).get("/api/migration/status")

                after = _tree_digest(root)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(after, before)
                payload = response.json()["data"]["command_center_3_v1_local_rc"]
                self.assertFalse(payload["writes_storage"])
                self.assertFalse(
                    payload["factor_full_market_research_summary"]["ready"]
                )
                self.assertFalse(
                    payload["candidate_radar_production_replacement_summary"]["ready"]
                )
            finally:
                connection.close()

    def test_migration_get_rejects_symlinked_evidence_root_without_tree_writes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            container = Path(temp_dir)
            actual_root = container / "actual-evidence"
            _write_packets(
                actual_root / "meta.sqlite",
                {
                    "command_center_3_factor_full_market_worker_production_acceptance": {
                        "status": "caller_boolean_must_not_be_trusted",
                        "full_market_factor_research": True,
                    },
                    "command_center_3_candidate_radar_cache": {
                        "status": "caller_boolean_must_not_be_trusted",
                        "global_candidate_cache_overwritten": True,
                    },
                },
            )
            evidence_root = container / "evidence"
            evidence_root.symlink_to(actual_root, target_is_directory=True)
            before = _tree_digest(container)

            with patch.object(v1_closeout_service, "EVIDENCE_ROOT", evidence_root):
                response = TestClient(app).get("/api/migration/status")

            after = _tree_digest(container)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(after, before)
            payload = response.json()["data"]["command_center_3_v1_local_rc"]
            self.assertFalse(payload["writes_storage"])
            self.assertFalse(
                payload["factor_full_market_research_summary"]["ready"]
            )
            self.assertFalse(
                payload["candidate_radar_production_replacement_summary"]["ready"]
            )


if __name__ == "__main__":
    unittest.main()
