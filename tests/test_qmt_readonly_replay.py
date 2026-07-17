from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from server.services import qmt_readonly_service as service
from server.services import task_service


SOURCE_HASH = "a" * 64
SOURCE_TASK_ID = "local-source-task-123"
SOURCE_DATA_DATE = "20260710"
SOURCE_SYMBOL = "600519.SH"
SOURCE_PROCESSED_COUNT = 1
SOURCE_RESULT_VERSION = "candidate-v05-" + hashlib.sha256(
    json.dumps(
        {"scope_hash": SOURCE_HASH, "task_id": SOURCE_TASK_ID, "processed": SOURCE_PROCESSED_COUNT},
        sort_keys=True,
        default=str,
    ).encode("utf-8")
).hexdigest()[:16]


def _payload(*, scenario: str = "baseline") -> dict:
    return {
        "approved_by_user": True,
        "mode": "local_research_replay",
        "scenario": scenario,
        "max_frames": 12,
        "source_result_version": SOURCE_RESULT_VERSION,
        "source_scope_hash": SOURCE_HASH,
        "source_data_date": SOURCE_DATA_DATE,
        "source_symbol": SOURCE_SYMBOL,
        "source_task_id": SOURCE_TASK_ID,
        "snapshot": {
            "as_of": "2026-07-13T15:00:00+08:00",
            "cash": "100000.00",
            "positions": [],
        },
        "events": [
            {
                "seq": 1,
                "event_type": "market_mark",
                "symbol": "600519.SH",
                "price": "10.0000",
            },
            {
                "seq": 2,
                "event_type": "virtual_intent",
                "symbol": "600519.SH",
                "side": "BUY",
                "quantity": 100,
                "limit_price": "10.1000",
            },
        ],
        "simulation": {"fee_bps": 5, "slippage_bps": 10, "buy_lot_size": 100},
    }


class QmtReadonlyReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "nested" / "meta.sqlite"
        self.service_db_patch = patch.object(service, "SQLITE_META_PATH", self.db_path)
        self.task_db_patch = patch.object(task_service, "SQLITE_META_PATH", self.db_path)
        self.service_db_patch.start()
        self.task_db_patch.start()
        task_service._TASKS.clear()
        self.canonical_patch = patch.object(
            service,
            "_validate_canonical_source_binding",
            return_value={
                "source_symbol": SOURCE_SYMBOL,
                "source_task_id": SOURCE_TASK_ID,
                "source_result_version": SOURCE_RESULT_VERSION,
                "source_scope_hash": SOURCE_HASH,
                "source_data_date": SOURCE_DATA_DATE,
            },
        )
        self.canonical_patch.start()
        self.canonical_patch_active = True

    def tearDown(self) -> None:
        task_service._TASKS.clear()
        if self.canonical_patch_active:
            self.canonical_patch.stop()
        self.task_db_patch.stop()
        self.service_db_patch.stop()
        self.temp_dir.cleanup()

    def _use_real_canonical_validation(self) -> None:
        if self.canonical_patch_active:
            self.canonical_patch.stop()
            self.canonical_patch_active = False

    def _seed_canonical_source(self, *, task_status: str = "success") -> None:
        task = task_service.build_task_record(
            service.CANDIDATE_TASK_TYPE,
            task_id=SOURCE_TASK_ID,
            output_packet_key=service.CANDIDATE_PACKET_KEY,
            payload={
                "runtime_mode": "v05_candidate_local_batch",
                "operator_approved": True,
                "candidate_scope_hash": SOURCE_HASH,
                "confirm_scope_hash": SOURCE_HASH,
                "data_date": SOURCE_DATA_DATE,
                "full_pool_candidates": [{"ticker": SOURCE_SYMBOL}],
            },
            status=task_status,
            progress=1.0,
            current_step=service.CANDIDATE_TASK_STEP if task_status == "success" else "candidate_source_failed",
            call_ledger=[{
                "api": "local_candidate_radar_v05_local_batch",
                "call_status": "candidate_radar_v05_local_batch_success",
                "row_count": SOURCE_PROCESSED_COUNT,
                **{field: False for field in service.CANDIDATE_LEDGER_FALSE_FIELDS},
                **{field: 0 for field in service.CANDIDATE_LEDGER_ZERO_FIELDS},
                **{field: True for field in service.CANDIDATE_LEDGER_TRUE_FIELDS},
            }],
        )
        task_service._persist_task(task)
        lineage = {
            "schema_version": "candidate_radar_v05_next_session_lineage.v1",
            "status": "same_packet_lineage_ready",
            "candidate_packet_key": service.CANDIDATE_PACKET_KEY,
            "candidate_task_id": SOURCE_TASK_ID,
            "candidate_scope_hash": SOURCE_HASH,
            "candidate_result_version": SOURCE_RESULT_VERSION,
            "symbol": SOURCE_SYMBOL,
            "data_date": SOURCE_DATA_DATE,
            "freshness_state": {
                "state": "fresh",
                "freshness_state": "fresh",
                "data_date": SOURCE_DATA_DATE,
                "expected_trade_date": SOURCE_DATA_DATE,
                "expected_trade_date_calendar_validated": True,
                "calendar_validated": True,
            },
            "research_only": True,
            "no_buy": True,
            "no_action": True,
            "no_trade": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_modify_strategy_action": True,
            "does_not_modify_operation_zones": True,
            "contains_secret": False,
        }
        store = service.SQLiteMetaStore(self.db_path)
        store.write_packet(
            service.CANDIDATE_PACKET_KEY,
            {
                "packet_key": service.CANDIDATE_PACKET_KEY,
                "schema_version": "candidate_radar_cache.v1",
                "status": "candidate_radar_v05_local_batch_ready",
                "scan_mode": "v05_candidate_local_batch",
                "task_id": SOURCE_TASK_ID,
                "latest_confirmed_task_id": SOURCE_TASK_ID,
                "latest_confirmed_task_status": "success",
                "candidate_radar_v05_result_version": SOURCE_RESULT_VERSION,
                "candidate_radar_v05_scope_hash": SOURCE_HASH,
                "trade_date": SOURCE_DATA_DATE,
                "candidate_radar_v05_next_session_lineage": copy.deepcopy(lineage),
            },
        )
        store.write_packet(
            service.NEXT_SESSION_PACKET_KEY,
            {
                "packet_key": service.NEXT_SESSION_PACKET_KEY,
                "schema_version": "next_session_projection.v1",
                "status": "ready_cache_replay",
                "mode": "cache_only",
                "cache_only": True,
                "read_only": True,
                "source_task_id": SOURCE_TASK_ID,
                "result_version": SOURCE_RESULT_VERSION,
                "candidate_scope_hash": SOURCE_HASH,
                "data_date": SOURCE_DATA_DATE,
                "candidate_radar_v05_lineage": copy.deepcopy(lineage),
            },
        )

    def test_empty_cache_get_creates_no_directory_database_or_task(self):
        before = sorted(str(path.relative_to(self.temp_dir.name)) for path in Path(self.temp_dir.name).rglob("*"))
        task_count_before = len(task_service._TASKS)

        packet = service.read_qmt_replay_cache()

        after = sorted(str(path.relative_to(self.temp_dir.name)) for path in Path(self.temp_dir.name).rglob("*"))
        self.assertEqual(packet["status"], "cache_missing")
        self.assertEqual(before, after)
        self.assertFalse(self.db_path.parent.exists())
        self.assertEqual(len(task_service._TASKS), task_count_before)
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["qmt_called"])
        self.assertFalse(packet["real_order_submitted"])

    def test_same_export_replay_has_stable_scope_result_and_decimal_state(self):
        first = service.run_qmt_readonly_local_replay(_payload())
        second = service.run_qmt_readonly_local_replay(_payload())

        self.assertEqual(first["status"], "local_export_contract_and_replay_verified")
        self.assertEqual(first["scope_hash"], second["scope_hash"])
        self.assertEqual(first["result_hash"], second["result_hash"])
        self.assertEqual(first["replay"]["final_cash"], "98998.50")
        self.assertEqual(first["replay"]["virtual_fill_count"], 1)
        self.assertEqual(first["replay"]["virtual_fills"][0]["fill_type"], "virtual_fill")
        self.assertEqual(first["replay"]["final_positions"][0]["quantity"], 100)
        self.assertEqual(first["replay"]["final_positions"][0]["available_quantity"], 0)
        self.assertFalse(first["qmt_external_connection_attempted"])
        self.assertFalse(first["broker_session_opened"])
        self.assertFalse(first["real_trade_executed"])
        self.assertEqual(
            first["source_lineage"],
            {
                "source_symbol": "600519.SH",
                "source_task_id": "local-source-task-123",
                "source_result_version": SOURCE_RESULT_VERSION,
                "source_scope_hash": SOURCE_HASH,
                "source_data_date": "20260710",
            },
        )
        self.assertEqual(first["safety_boundary"]["real_order_count"], 0)
        self.assertFalse(first["safety_boundary"]["qmt_external_connection_attempted"])
        self.assertEqual(first["virtual_research_events"], first["replay"]["research_events"])
        self.assertEqual(first["replay"]["virtual_research_events"], first["replay"]["research_events"])

        task = task_service.read_task_status(str(first["task_id"]))
        safe_payload = task.get("payload_safe") or {}
        serialized = json.dumps(safe_payload, ensure_ascii=False)
        self.assertNotIn("snapshot", safe_payload)
        self.assertNotIn("positions", safe_payload)
        self.assertNotIn("100000", serialized)
        self.assertTrue(safe_payload["raw_snapshot_stored_in_task_audit"] is False)
        self.assertEqual(safe_payload["scope_hash"], first["scope_hash"])

    def test_frontend_scope_only_contract_emits_bounded_research_event(self):
        payload = {
            "approved_by_user": True,
            "mode": "local_research_replay",
            "scenario": "stress",
            "max_frames": 24,
            "source_result_version": "candidate-next.v1",
            "source_scope_hash": SOURCE_HASH,
            "source_data_date": "20260710",
            "source_symbol": "600519.SH",
            "source_task_id": "local-source-task-123",
        }

        packet = service.run_qmt_readonly_local_replay(payload)

        self.assertEqual(packet["status"], "local_scope_replay_verified_export_pending")
        self.assertFalse(packet["caller_supplied_export_compatibility_verified"])
        self.assertEqual(packet["virtual_fill_count"], 0)
        self.assertEqual(packet["replay"]["research_events"][0]["event"], "watch")
        self.assertIn(
            packet["replay"]["research_events"][0]["event"],
            {"observe", "watch", "excluded"},
        )

    def test_buy_lot_and_no_short_constraints_exclude_virtual_intents(self):
        payload = _payload()
        payload["snapshot"] = {
            "as_of": "2026-07-13T15:00:00+08:00",
            "cash": "100000.00",
            "positions": [],
        }
        payload["events"] = [
            {"seq": 1, "event_type": "market_mark", "symbol": "000001.SZ", "price": "10"},
            {
                "seq": 2,
                "event_type": "virtual_intent",
                "symbol": "000001.SZ",
                "side": "BUY",
                "quantity": 50,
                "limit_price": "11",
            },
            {
                "seq": 3,
                "event_type": "virtual_intent",
                "symbol": "000001.SZ",
                "side": "SELL",
                "quantity": 100,
                "limit_price": "9",
            },
        ]

        packet = service.run_qmt_readonly_local_replay(payload)

        self.assertEqual(packet["replay"]["virtual_fill_count"], 0)
        self.assertEqual(packet["replay"]["excluded_virtual_intent_count"], 2)
        reasons = {row.get("reason") for row in packet["replay"]["event_ledger"]}
        self.assertIn("buy_quantity_must_use_100_share_lot", reasons)
        self.assertIn("virtual_sell_exceeds_available_quantity_no_short", reasons)
        self.assertEqual(packet["replay"]["final_cash"], "100000.00")
        self.assertEqual(packet["replay"]["final_positions"], [])

    def test_insufficient_cash_never_creates_leverage_or_negative_cash(self):
        payload = _payload()
        payload["snapshot"]["cash"] = "1.00"

        packet = service.run_qmt_readonly_local_replay(payload)

        self.assertEqual(packet["status"], "local_export_contract_and_replay_verified")
        self.assertEqual(packet["replay"]["virtual_fill_count"], 0)
        self.assertEqual(packet["replay"]["final_cash"], "1.00")
        self.assertEqual(packet["replay"]["final_positions"], [])
        self.assertEqual(
            packet["replay"]["event_ledger"][1]["reason"],
            "insufficient_virtual_cash_no_leverage",
        )

    def test_invalid_sequence_and_forbidden_connection_fields_fail_closed(self):
        invalid_seq = _payload()
        invalid_seq["events"][1]["seq"] = 3
        blocked_seq = service.run_qmt_readonly_local_replay(invalid_seq)
        self.assertEqual(blocked_seq["status"], "local_replay_blocked_safe")
        self.assertEqual(blocked_seq["error_message_safe"], "event_seq_must_be_contiguous_from_one")

        forbidden = _payload()
        forbidden["snapshot"]["account_id"] = "SHOULD_NOT_PERSIST"
        blocked_sensitive = service.run_qmt_readonly_local_replay(forbidden)
        self.assertEqual(blocked_sensitive["status"], "local_replay_blocked_safe")
        serialized = json.dumps(blocked_sensitive, ensure_ascii=False)
        self.assertNotIn("SHOULD_NOT_PERSIST", serialized)
        self.assertFalse(blocked_sensitive["qmt_client_imported"])
        self.assertFalse(blocked_sensitive["broker_called"])
        self.assertFalse(blocked_sensitive["real_order_submitted"])

    def test_cross_instance_cache_readback_replays_persisted_result(self):
        written = service.run_qmt_readonly_local_replay(_payload())
        task_service._TASKS.clear()

        cached = service.read_qmt_replay_cache()

        self.assertEqual(cached["status"], "ready_cache_replay")
        self.assertEqual(cached["result_hash"], written["result_hash"])
        self.assertEqual(cached["scope_hash"], written["scope_hash"])
        self.assertEqual(cached["current_result_summary"]["result_hash"], written["result_hash"])
        self.assertEqual(cached["last_good_result_summary"]["result_hash"], written["result_hash"])
        self.assertEqual(cached["source_lineage"], written["source_lineage"])
        self.assertEqual(cached["safety_boundary"], written["safety_boundary"])
        self.assertEqual(cached["virtual_research_events"], written["virtual_research_events"])

    def test_optional_source_lineage_rejects_unsafe_symbol_and_task_id(self):
        invalid_symbol = _payload()
        invalid_symbol["source_symbol"] = "600519"
        blocked_symbol = service.run_qmt_readonly_local_replay(invalid_symbol)
        self.assertEqual(blocked_symbol["error_message_safe"], "invalid_a_share_symbol")

        invalid_task = _payload()
        invalid_task["source_task_id"] = "unsafe task id with spaces"
        blocked_task = service.run_qmt_readonly_local_replay(invalid_task)
        self.assertEqual(blocked_task["error_message_safe"], "invalid_source_task_id")
        self.assertNotIn("unsafe task id", json.dumps(blocked_task, ensure_ascii=False))

    def test_persistence_failure_keeps_last_good_but_blocks_latest_cache(self):
        good = service.run_qmt_readonly_local_replay(_payload())
        changed = _payload(scenario="recovery")

        with patch.object(service, "_persist_success_packets", side_effect=OSError("simulated")):
            failed = service.run_qmt_readonly_local_replay(changed)

        cached = service.read_qmt_replay_cache()
        self.assertEqual(failed["status"], "local_replay_blocked_safe")
        self.assertEqual(failed["error_message_safe"], "local_replay_or_persistence_failed_safe")
        self.assertEqual(cached["status"], "latest_attempt_blocked")
        self.assertEqual(cached["result_hash"], "")
        self.assertFalse(cached["result_integrity_validated"])
        self.assertIn("result_task_status_invalid", cached["warnings"][0])
        persisted_last_good, persisted_status = service._read_packet_no_init(service.LAST_GOOD_PACKET_KEY)
        self.assertEqual(persisted_status, "packet_present")
        self.assertEqual(persisted_last_good["result_hash"], good["result_hash"])

    def test_result_integrity_rejects_manual_status_event_and_hash_self_seal(self):
        packet = service.run_qmt_readonly_local_replay(_payload())
        valid, status = service._result_packet_integrity(packet)
        self.assertTrue(valid)
        self.assertEqual(status, "result_integrity_validated")

        for mutate, expected in (
            (lambda row: row.update(status="ready_cache_replay"), "result_status_invalid"),
            (lambda row: row["virtual_research_events"][0].update(event="buy"), "result_event_contract_invalid"),
            (lambda row: row["source_lineage"].update(source_data_date="20260709"), "result_lineage_mismatch"),
            (lambda row: row.update(result_hash="b" * 64), "result_hash_mismatch"),
        ):
            forged = copy.deepcopy(packet)
            mutate(forged)
            self.assertEqual(service._result_packet_integrity(forged), (False, expected))

        forged = copy.deepcopy(packet)
        forged["virtual_research_events"][0]["event"] = "buy"
        forged["replay"]["research_events"][0]["event"] = "buy"
        forged["replay"]["virtual_research_events"][0]["event"] = "buy"
        forged["result_hash"] = service._sha256(service._result_hash_material(forged))
        valid, reason = service._result_packet_integrity(forged)
        self.assertFalse(valid)
        self.assertEqual(reason, "result_event_contract_invalid")

        self_sealed = copy.deepcopy(packet)
        self_sealed["virtual_research_events"][0]["reason"] = "manually_rewritten_but_schema_valid"
        self_sealed["replay"]["research_events"][0]["reason"] = "manually_rewritten_but_schema_valid"
        self_sealed["replay"]["virtual_research_events"][0]["reason"] = "manually_rewritten_but_schema_valid"
        self_sealed["result_hash"] = service._sha256(service._result_hash_material(self_sealed))
        valid, reason = service._result_packet_integrity(self_sealed)
        self.assertFalse(valid)
        self.assertEqual(reason, "result_mac_mismatch")

        forged_ledger = copy.deepcopy(packet)
        forged_ledger["call_ledger"][0]["provider_called"] = True
        valid, reason = service._result_packet_integrity(forged_ledger)
        self.assertFalse(valid)
        self.assertEqual(reason, "result_call_ledger_invalid")

        service._persist_current_packet(forged)
        cached = service.read_qmt_replay_cache()
        self.assertEqual(cached["status"], "latest_attempt_blocked")
        self.assertFalse(cached["result_integrity_validated"])
        self.assertEqual(cached["virtual_research_events"], [])

    def test_missing_install_local_integrity_key_blocks_cache_readback(self):
        service.run_qmt_readonly_local_replay(_payload())
        key_path = service._result_integrity_key_path()
        self.assertTrue(key_path.exists())
        key_path.unlink()

        cached = service.read_qmt_replay_cache()

        self.assertEqual(cached["status"], "latest_attempt_blocked")
        self.assertEqual(cached["result_integrity_status"], "result_integrity_key_missing_or_invalid")
        self.assertFalse(cached["result_integrity_validated"])

    def test_post_requires_real_canonical_candidate_next_and_source_task(self):
        self._use_real_canonical_validation()

        missing = service.run_qmt_readonly_local_replay(_payload())
        self.assertEqual(missing["status"], "local_replay_blocked_safe")
        self.assertEqual(missing["error_message_safe"], "canonical_candidate_next_packet_missing")

        self._seed_canonical_source()
        accepted = service.run_qmt_readonly_local_replay(_payload())
        self.assertEqual(accepted["status"], "local_export_contract_and_replay_verified")
        self.assertEqual(service._result_packet_integrity(accepted), (True, "result_integrity_validated"))

        for field, value in (
            ("source_task_id", "nonexistent-candidate-task"),
            ("source_result_version", "forged-result.v1"),
            ("source_scope_hash", "f" * 64),
            ("source_data_date", "20260709"),
        ):
            forged = _payload()
            forged[field] = value
            blocked = service.run_qmt_readonly_local_replay(forged)
            self.assertEqual(blocked["status"], "local_replay_blocked_safe", field)
            self.assertEqual(blocked["error_message_safe"], "canonical_source_request_mismatch", field)

    def test_canonical_source_task_must_be_real_success_not_cache_replay(self):
        self._use_real_canonical_validation()
        self._seed_canonical_source(task_status="failed")

        blocked = service.run_qmt_readonly_local_replay(_payload())

        self.assertEqual(blocked["status"], "local_replay_blocked_safe")
        self.assertEqual(blocked["error_message_safe"], "canonical_source_task_status_invalid")

        task = task_service.read_task_status(SOURCE_TASK_ID)
        self.assertIsNotNone(task)
        task["status"] = "success"
        task["current_step"] = service.CANDIDATE_TASK_STEP
        task["status_history"][-1]["status"] = "success"
        task["status_history"][-1]["current_step"] = service.CANDIDATE_TASK_STEP
        task["storage_source"] = "candidate_cache_replay"
        task["cache_replay_only"] = True
        real_read_task_status = task_service.read_task_status
        with patch.object(
            task_service,
            "read_task_status",
            side_effect=lambda task_id: task if task_id == SOURCE_TASK_ID else real_read_task_status(task_id),
        ):
            replay_blocked = service.run_qmt_readonly_local_replay(_payload())
        self.assertEqual(replay_blocked["error_message_safe"], "canonical_source_task_not_durable")

    def test_canonical_source_rejects_task_ledger_and_result_self_sealing(self):
        self._use_real_canonical_validation()
        self._seed_canonical_source()

        task = task_service._TASKS[SOURCE_TASK_ID]
        task["call_ledger"][0]["broker_session_opened"] = True
        unsafe_ledger = service.run_qmt_readonly_local_replay(_payload())
        self.assertEqual(unsafe_ledger["error_message_safe"], "canonical_source_task_ledger_boundary_invalid")

        task["call_ledger"][0]["broker_session_opened"] = False
        forged_result_version = "candidate-v05-" + "f" * 16
        store = service.SQLiteMetaStore(self.db_path)
        candidate = store.read_packet(service.CANDIDATE_PACKET_KEY)
        next_session = store.read_packet(service.NEXT_SESSION_PACKET_KEY)
        candidate["candidate_radar_v05_result_version"] = forged_result_version
        candidate["candidate_radar_v05_next_session_lineage"]["candidate_result_version"] = forged_result_version
        next_session["result_version"] = forged_result_version
        next_session["candidate_radar_v05_lineage"]["candidate_result_version"] = forged_result_version
        store.write_packet(service.CANDIDATE_PACKET_KEY, candidate)
        store.write_packet(service.NEXT_SESSION_PACKET_KEY, next_session)
        forged_payload = _payload()
        forged_payload["source_result_version"] = forged_result_version

        self_sealed = service.run_qmt_readonly_local_replay(forged_payload)

        self.assertEqual(self_sealed["error_message_safe"], "canonical_source_result_version_not_task_derived")

    def test_source_data_date_is_required_real_and_canonical(self):
        for value in (None, "2026-02-30", "x20260710", 20260710):
            payload = _payload()
            payload["source_data_date"] = value
            blocked = service.run_qmt_readonly_local_replay(payload)
            self.assertEqual(blocked["status"], "local_replay_blocked_safe")
            self.assertIn(blocked["error_message_safe"], {"source_data_date_required", "invalid_source_data_date"})

        payload = _payload()
        payload["source_data_date"] = "2026-07-10"
        accepted = service.run_qmt_readonly_local_replay(payload)
        self.assertEqual(accepted["source_data_date"], "20260710")
        self.assertEqual(accepted["source_lineage"]["source_data_date"], "20260710")

    def test_api_routes_and_task_catalog_expose_one_button_gated_post(self):
        client = TestClient(app)
        missing = client.get("/api/qmt-replay/cache").json()["data"]
        self.assertEqual(missing["status"], "cache_missing")
        created = client.post("/api/qmt-replay/local-simulate", json=_payload()).json()["data"]
        self.assertEqual(created["status"], "local_export_contract_and_replay_verified")

        catalog = task_service.build_task_catalog()
        rows = {row["task_type"]: row for row in catalog["tasks"]}
        row = rows[service.TASK_TYPE]
        self.assertEqual(row["route"], "POST /api/qmt-replay/local-simulate")
        self.assertTrue(row["button_gated"])
        self.assertEqual(row["possible_external_sources"], [])
        self.assertEqual(row["future_external_sources"], ["qmt"])
        self.assertFalse(row["qmt_connector_implemented"])
        self.assertTrue(row["does_not_execute_trades"])

    def test_service_imports_no_network_process_environment_or_qmt_client(self):
        tree = ast.parse(inspect.getsource(service))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
        self.assertTrue(
            imported_roots.isdisjoint(
                {"os", "socket", "subprocess", "requests", "httpx", "urllib", "xtquant", "xttrader"}
            )
        )
        source = inspect.getsource(service)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("getenv(", source)
        self.assertNotIn("create_connection(", source)
        self.assertNotIn("Popen(", source)


if __name__ == "__main__":
    unittest.main()
