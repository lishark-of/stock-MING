from __future__ import annotations

import ast
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


def _payload(*, scenario: str = "baseline") -> dict:
    return {
        "approved_by_user": True,
        "mode": "local_research_replay",
        "scenario": scenario,
        "max_frames": 12,
        "source_result_version": "candidate-next.v1",
        "source_scope_hash": SOURCE_HASH,
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

    def tearDown(self) -> None:
        task_service._TASKS.clear()
        self.task_db_patch.stop()
        self.service_db_patch.stop()
        self.temp_dir.cleanup()

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

    def test_persistence_failure_keeps_last_good_and_surfaces_degraded_cache(self):
        good = service.run_qmt_readonly_local_replay(_payload())
        changed = _payload(scenario="recovery")

        with patch.object(service, "_persist_success_packets", side_effect=OSError("simulated")):
            failed = service.run_qmt_readonly_local_replay(changed)

        cached = service.read_qmt_replay_cache()
        self.assertEqual(failed["status"], "local_replay_blocked_safe")
        self.assertEqual(failed["error_message_safe"], "local_replay_or_persistence_failed_safe")
        self.assertEqual(cached["status"], "degraded_last_good_replay")
        self.assertEqual(cached["result_hash"], good["result_hash"])
        self.assertEqual(cached["last_good_result_summary"]["result_hash"], good["result_hash"])
        self.assertEqual(cached["current_result_summary"]["status"], "local_replay_blocked_safe")

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
