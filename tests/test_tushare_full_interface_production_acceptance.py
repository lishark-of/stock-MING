import tempfile
import unittest
import datetime as dt
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from server.api import routes_tasks
from server.services import storage_service, task_service, tushare_task_service
from storage.sqlite_meta import SQLiteMetaStore


def _representative_row(api: str) -> dict:
    values = {
        "ts_code": "000001.SZ",
        "trade_date": "20260710",
        "ann_date": "20260710",
        "cal_date": "20260710",
        "end_date": "20260710",
        "float_date": "20260710",
        "is_open": 1,
        "name": "sample",
        "title": "sample",
        "reason": "sample",
        "exalter": "sample",
        "holder_name": "sample",
        "pledgor": "sample",
        "surv_name": "sample",
        "type": "sample",
    }
    row = {key: value for key, value in values.items() if key in {"ts_code", "trade_date", "ann_date", "cal_date", "end_date", "float_date", "is_open"}}
    for group in tushare_task_service.API_REPRESENTATIVE_REQUIRED_FIELDS[api]:
        field = group[0]
        row[field] = values.get(field, 1)
    return row


class _FakeFullInterfaceAdapter:
    def __init__(self, *, empty_api: str = "", failed_api: str = "", generic: bool = False):
        self.calls: list[str] = []
        self.empty_api = empty_api
        self.failed_api = failed_api
        self.generic = generic

    def __getattr__(self, name):
        if not name.startswith("get_"):
            raise AttributeError(name)

        def _call(**_params):
            api = name.removeprefix("get_")
            self.calls.append(api)
            if api == self.failed_api:
                return {"ok": False, "data": None, "error": "permission denied"}
            if api == self.empty_api:
                return {"ok": True, "data": [], "error": ""}
            if api == "stock_basic":
                return {
                    "ok": True,
                    "data": [{"ts_code": "000001.SZ", "list_status": "L", "list_date": "19910403"}],
                    "error": "",
                }
            return {"ok": True, "data": [{"value": 1} if self.generic else _representative_row(api)], "error": ""}

        return _call


class TushareFullInterfaceProductionAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "meta.sqlite"
        self.original_tushare_meta_path = tushare_task_service.SQLITE_META_PATH
        self.original_task_meta_path = task_service.SQLITE_META_PATH
        self.original_parquet_root = storage_service.PARQUET_ROOT
        tushare_task_service.SQLITE_META_PATH = self.db_path
        task_service.SQLITE_META_PATH = self.db_path
        storage_service.PARQUET_ROOT = self.root / "parquet"
        task_service._TASKS.clear()

    def tearDown(self):
        task_service._TASKS.clear()
        tushare_task_service.SQLITE_META_PATH = self.original_tushare_meta_path
        task_service.SQLITE_META_PATH = self.original_task_meta_path
        storage_service.PARQUET_ROOT = self.original_parquet_root
        self.tmp.cleanup()

    def test_real_adapter_v2_receipt_is_verified_by_formal_consumer(self):
        import tushare_adapter
        from tushare.pro.client import DataApi

        pro = DataApi("test-only-no-network", timeout=1)
        pro.daily = lambda **_params: tushare_adapter.pd.DataFrame(
            [{"ts_code": "000001.SZ", "trade_date": "20260717", "close": 10.0}]
        )
        tushare_adapter._TRANSPORT_RECEIPTS.clear()
        with patch.object(tushare_adapter, "_get_pro_client", return_value=(pro, None)):
            result = tushare_adapter._call_pro("daily", trade_date="20260717")
        self.assertEqual(
            result["transport_receipt_version"],
            "tushare_runtime_transport_receipt.v2",
        )
        transport = tushare_task_service._consume_runtime_transport_evidence(
            tushare_adapter,
            result,
            "daily",
        )
        self.assertTrue(transport["runtime_adapter_module_identity_verified"])
        self.assertTrue(transport["provider_transport_verified"])
        self.assertTrue(transport["official_client_identity_verified"])
        self.assertEqual(transport["provider"], "Tushare")
        self.assertEqual(transport["transport_receipt_count"], 1)
        self.assertEqual(len(transport["transport_receipt_digest"]), 64)

        with patch.object(tushare_adapter, "_get_pro_client", return_value=(pro, None)):
            tampered_result = tushare_adapter._call_pro(
                "daily", trade_date="20260717"
            )
        call_id = tampered_result["transport_call_id"]
        tushare_adapter._TRANSPORT_RECEIPTS[call_id]["provider"] = "not-tushare"
        tampered = tushare_task_service._consume_runtime_transport_evidence(
            tushare_adapter,
            tampered_result,
            "daily",
        )
        self.assertFalse(tampered["provider_transport_verified"])
        self.assertFalse(tampered["official_client_identity_verified"])

    def test_stock_basic_missing_status_uses_explicit_request_filter_provenance(self):
        normalized = tushare_task_service._normalize_stock_basic_row(
            {"ts_code": "000001.SZ", "list_date": "19910403"},
            requested_list_status="L",
        )
        self.assertEqual(normalized["list_status"], "L")
        self.assertEqual(normalized["list_status_source"], "request_filter")

        contradictory = tushare_task_service._normalize_stock_basic_row(
            {"ts_code": "000001.SZ", "list_status": "D", "list_date": "19910403"},
            requested_list_status="L",
        )
        self.assertEqual(contradictory["list_status"], "D")
        self.assertEqual(contradictory["list_status_source"], "provider_response")

    def test_full_market_daily_batches_bind_one_validated_trade_date_per_call(self):
        calls = []

        def fake_batch(_adapter, *, api, params, **_kwargs):
            calls.append((api, dict(params)))
            return [{"ts_code": "000001.SZ", "trade_date": params["trade_date"]}], {
                "api": api,
                "call_status": "success",
                "provider_call_count": 1,
                "historical_provider_call_count": 0,
                "resumed_page_count": 0,
                "page_count": 1,
                "pagination_complete": True,
                "truncation_detected": False,
                "provider_transport_verified": True,
                "external_calls_triggered": True,
                "tushare_called": True,
            }

        with patch.object(tushare_task_service, "_paginated_provider_rows", side_effect=fake_batch):
            rows, ledger = tushare_task_service._full_market_dataset_trade_date_batches(
                object(),
                api="daily",
                trade_dates=["20260710", "20260713"],
                max_rows_per_call=5000,
                call_budget={"used": 0, "historical": 0, "limit": 10},
                checkpoint_root=self.root / "checkpoints",
                runtime_event_recorder=lambda **_kwargs: {},
            )

        self.assertEqual(calls, [("daily", {"trade_date": "20260710"}), ("daily", {"trade_date": "20260713"})])
        self.assertEqual([row["trade_date"] for row in rows], ["20260710", "20260713"])
        self.assertEqual(ledger["batch_count"], 2)
        self.assertEqual(ledger["provider_call_count"], 2)
        self.assertTrue(ledger["provider_transport_verified"])

    def test_full_market_daily_basic_uses_the_same_trade_date_batches(self):
        calls = []

        def fake_batch(_adapter, *, api, params, **_kwargs):
            calls.append((api, dict(params)))
            return [{"ts_code": "000001.SZ", "trade_date": params["trade_date"]}], {
                "api": api,
                "call_status": "success",
                "provider_call_count": 1,
                "historical_provider_call_count": 0,
                "resumed_page_count": 0,
                "page_count": 1,
                "pagination_complete": True,
                "truncation_detected": False,
                "provider_transport_verified": True,
                "external_calls_triggered": True,
                "tushare_called": True,
            }

        with patch.object(tushare_task_service, "_paginated_provider_rows", side_effect=fake_batch):
            rows, ledger = tushare_task_service._full_market_dataset_trade_date_batches(
                object(),
                api="daily_basic",
                trade_dates=["20260710", "20260713"],
                max_rows_per_call=5000,
                call_budget={"used": 0, "historical": 0, "limit": 10},
                checkpoint_root=self.root / "checkpoints_daily_basic",
                runtime_event_recorder=lambda **_kwargs: {},
            )

        self.assertEqual(calls, [("daily_basic", {"trade_date": "20260710"}), ("daily_basic", {"trade_date": "20260713"})])
        self.assertEqual([row["trade_date"] for row in rows], ["20260710", "20260713"])
        self.assertEqual(ledger["batch_count"], 2)
        self.assertTrue(ledger["provider_transport_verified"])

    def _contexts(self):
        today = dt.date.today().strftime("%Y%m%d")
        values = {
            "ts_code": "000001.SZ",
            "trade_date": "20260710",
            "start_date": "20260101",
            "end_date": today,
            "ann_date": "20260710",
            "period": "20260630",
            "float_date": "20260710",
            "limit_type": "U",
            "trade_type": "IN",
            "holder_type": "C",
            "exchange": "SSE",
        }
        return {
            api: {key: values[key] for key in spec["params"] if key in values}
            for api, spec in tushare_task_service.REFRESH_API_SPECS.items()
        }

    def _seed_payload(self):
        today = dt.date.today().strftime("%Y%m%d")
        return {
            "apis": list(tushare_task_service.ALL_REFRESH_APIS),
            "target_sample_acceptance_groups": list(tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS),
            "api_contexts": self._contexts(),
            "universe_context": {
                "list_status": "L",
                "as_of_date": today,
                "feature_start_date": "20260101",
                "feature_end_date": today,
                "required_feature_sessions": 90,
                "max_provider_calls": 280,
                "max_rows_per_call": 10000,
            },
        }

    def _seed_request_chain(self):
        seed = tushare_task_service.run_tushare_provider_target_sample_execution_recipe_seed(self._seed_payload())
        self.assertEqual(seed["status"], "success")
        seed_packet = SQLiteMetaStore(self.db_path).read_packet(
            tushare_task_service.PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_PACKET_KEY
        )
        recipe = seed_packet["provider_target_sample_execution_recipe"]
        self.assertTrue(recipe["full_interface_recipe_ready"])
        self.assertEqual(len(recipe["execution_recipe_scope_hash"]), 64)
        request = tushare_task_service.run_tushare_provider_target_sample_execution_request(
            {
                "execution_recipe_scope_hash": recipe["execution_recipe_scope_hash"],
                "operator_approved": True,
                "apis": list(tushare_task_service.ALL_REFRESH_APIS),
                "target_sample_acceptance_groups": list(tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS),
            }
        )
        self.assertEqual(request["status"], "success")
        packet = SQLiteMetaStore(self.db_path).read_packet(
            "command_center_tushare_provider_target_sample_execution_request_packet"
        )
        receipt = packet["receipt"]
        self.assertTrue(receipt["full_interface_production_execution_request_ready"])
        payload = dict(receipt["target_payload_safe"])
        payload["approved_by_user"] = True
        return payload, recipe, receipt

    @staticmethod
    def _staged_parquet_result(api, _data, *, payload=None, scope=None):
        del payload, scope
        dataset = tushare_task_service.PARQUET_DATASETS.get(api)
        if dataset:
            return {
                "status": "staged",
                "dataset": dataset,
                "row_count": 1,
                "staging_path": "/tmp/not-promoted-in-fake-test",
                "staging_digest": "a" * 64,
                "canonical_path": "/tmp/not-promoted-in-fake-test-final",
            }
        return {"status": "not_enabled", "dataset": None, "row_count": 0, "path": ""}

    def _seed_existing_production_state(self):
        store = SQLiteMetaStore(self.db_path)
        packets = {
            tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY: {
                "status": "existing-production",
                "immutable": "production",
            },
            tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_STAGING_PACKET_KEY: {
                "status": "existing-staging",
                "immutable": "staging",
            },
            tushare_task_service.FULL_MARKET_UNIVERSE_CURRENT_PACKET_KEY: {
                "status": "existing-current",
                "immutable": "current",
            },
            tushare_task_service.FULL_MARKET_UNIVERSE_LAST_GOOD_PACKET_KEY: {
                "status": "existing-last-good",
                "immutable": "last-good",
            },
        }
        for key, packet in packets.items():
            store.write_packet(key, packet)
        production_root = storage_service.PARQUET_ROOT / "full_market_universe"
        staging_path = production_root / ".attempts" / "existing" / "staging.bin"
        pointer_path = production_root / "pointer.json"
        staging_path.parent.mkdir(parents=True, exist_ok=True)
        staging_path.write_bytes(b"existing-staging-bytes")
        pointer_path.write_bytes(
            json.dumps({"status": "existing-pointer"}, sort_keys=True).encode("utf-8")
        )
        return packets, {
            staging_path: staging_path.read_bytes(),
            pointer_path: pointer_path.read_bytes(),
        }

    def _assert_existing_production_state_unchanged(self, packets, files):
        store = SQLiteMetaStore(self.db_path)
        for key, packet in packets.items():
            self.assertEqual(store.read_packet(key), packet, key)
        for path, content in files.items():
            self.assertEqual(path.read_bytes(), content, str(path))

    def test_missing_execution_request_blocks_before_adapter_load_or_call(self):
        adapter = _FakeFullInterfaceAdapter()
        payload = self._seed_payload()
        payload.update({"approved_by_user": True, "acceptance_mode": tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_MODE})
        task = tushare_task_service.run_tushare_full_interface_provider_production_acceptance(payload, adapter=adapter)

        self.assertEqual(task["status"], "failed")
        self.assertEqual(adapter.calls, [])
        self.assertIn("missing_target_sample_execution_request", task["current_step"])
        self.assertIsNone(SQLiteMetaStore(self.db_path).read_packet(tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY))

    def test_real_seed_request_chain_calls_exact_scope_but_injected_adapter_never_promotes(self):
        payload, recipe, receipt = self._seed_request_chain()
        adapter = _FakeFullInterfaceAdapter()
        with patch.object(tushare_task_service, "_write_parquet_dataset", side_effect=self._staged_parquet_result):
            task = tushare_task_service.run_tushare_full_interface_provider_production_acceptance(payload, adapter=adapter)

        self.assertEqual(task["status"], "success")
        self.assertEqual(set(tushare_task_service.ALL_REFRESH_APIS), set(adapter.calls) - {"stock_basic"})
        self.assertEqual(adapter.calls.count("stock_basic"), 0)
        self.assertEqual(receipt["latest_execution_recipe_scope_hash"], recipe["execution_recipe_scope_hash"])
        packet = SQLiteMetaStore(self.db_path).read_packet("command_center_tushare_refresh_packet")
        contract = packet["full_interface_provider_production_contract"]
        self.assertFalse(contract["full_interface_provider_production"])
        self.assertIn("runtime_transport_provider_provenance", contract["blockers"])
        self.assertIn("all_interfaces_representative_or_audited_valid_empty", contract["blockers"])
        self.assertTrue(all(row["provider_transport_verified"] is False for row in task["call_ledger"]))
        self.assertIsNone(SQLiteMetaStore(self.db_path).read_packet(tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY))
        production_root = storage_service.PARQUET_ROOT / "full_market_universe"
        self.assertFalse((production_root / "pointer.json").exists())
        self.assertFalse((production_root / "execution_runs").exists())

    def test_separate_anns_permission_is_probed_first_and_failure_stops_all_remaining_calls(self):
        payload, _recipe, _receipt = self._seed_request_chain()
        adapter = _FakeFullInterfaceAdapter(failed_api="anns_d")
        with patch.object(
            tushare_task_service,
            "_run_full_market_universe_acceptance",
            side_effect=AssertionError("upstream permission failure must block full-market calls"),
        ):
            task = tushare_task_service.run_tushare_full_interface_provider_production_acceptance(
                payload,
                adapter=adapter,
            )

        self.assertEqual(task["status"], "failed")
        self.assertEqual(adapter.calls, ["anns_d"])
        self.assertIn("anns_d_permission_denied", task["current_step"])
        self.assertEqual(len(task["call_ledger"]), 1)
        self.assertEqual(task["call_ledger"][0]["failure_mode"], "permission_denied")
        packet = SQLiteMetaStore(self.db_path).read_packet("command_center_tushare_refresh_packet")
        self.assertEqual(packet["selected_apis"], list(tushare_task_service.ALL_REFRESH_APIS))
        self.assertEqual(packet["provider_execution_order"][0], "anns_d")
        self.assertEqual(len(packet["provider_execution_order"]), len(tushare_task_service.ALL_REFRESH_APIS))
        self.assertEqual(set(packet["provider_execution_order"]), set(tushare_task_service.ALL_REFRESH_APIS))
        self.assertTrue(packet["provider_failure_stop_enforced"])
        self.assertEqual(packet["provider_failure_stop"]["failed_api"], "anns_d")
        self.assertTrue(packet["provider_failure_stop"]["remaining_interfaces_not_called"])
        self.assertFalse(packet["provider_failure_stop"]["production_promotion_allowed"])
        self.assertEqual(
            packet["full_market_universe_evidence"]["status"],
            "full_market_universe_production_blocked_upstream_interface_failure",
        )
        self.assertFalse((storage_service.PARQUET_ROOT / "full_market_universe" / "pointer.json").exists())

    def test_valid_empty_anns_evidence_does_not_trigger_failure_stop(self):
        payload, _recipe, _receipt = self._seed_request_chain()
        adapter = _FakeFullInterfaceAdapter(empty_api="anns_d")
        with patch.object(tushare_task_service, "_write_parquet_dataset", side_effect=self._staged_parquet_result):
            task = tushare_task_service.run_tushare_full_interface_provider_production_acceptance(
                payload,
                adapter=adapter,
            )

        self.assertEqual(task["status"], "success")
        self.assertEqual(adapter.calls[0], "anns_d")
        self.assertEqual(set(adapter.calls), set(tushare_task_service.ALL_REFRESH_APIS))
        packet = SQLiteMetaStore(self.db_path).read_packet("command_center_tushare_refresh_packet")
        self.assertEqual(packet["provider_failure_stop"], {})
        self.assertTrue(packet["provider_failure_stop_enforced"])
        anns = next(row for row in task["call_ledger"] if row["api"] == "anns_d")
        self.assertEqual(anns["call_status"], "empty")
        self.assertFalse(anns["valid_empty_semantics_verified"])
        self.assertFalse(anns["provider_transport_verified"])

    def test_failure_stop_distinguishes_retryable_unknown_and_terminal_states(self):
        for call_status, failure_mode in (
            ("success", ""),
            ("success", "none"),
            ("empty", ""),
            ("empty", "empty_result_or_no_record"),
        ):
            with self.subTest(valid=(call_status, failure_mode)):
                self.assertEqual(
                    tushare_task_service._production_provider_failure_stop(
                        {
                            "api": "anns_d",
                            "call_status": call_status,
                            "failure_mode": failure_mode,
                        }
                    ),
                    {},
                )

        terminal_modes = (
            "permission_denied",
            "parse_failed_or_invalid_result",
            "provider_error_safe",
            "missing_required_parameter",
        )
        for failure_mode in terminal_modes:
            with self.subTest(terminal=failure_mode):
                terminal = tushare_task_service._production_provider_failure_stop(
                    {
                        "api": "anns_d",
                        "call_status": "failed",
                        "failure_mode": failure_mode,
                    }
                )
                self.assertTrue(terminal["terminal_provider_failure"])
                self.assertFalse(terminal["retryable_provider_state"])
                self.assertFalse(terminal["provider_call_status_contract_error"])
                self.assertEqual(terminal["stop_classification"], "terminal_provider_failure")

        for call_status in ("retry_pending", "rate_limited_retryable"):
            for failure_mode in ("", call_status):
                with self.subTest(retryable=(call_status, failure_mode)):
                    retryable = tushare_task_service._production_provider_failure_stop(
                        {
                            "api": "anns_d",
                            "call_status": call_status,
                            "failure_mode": failure_mode,
                        }
                    )
                    self.assertFalse(retryable["terminal_provider_failure"])
                    self.assertTrue(retryable["retryable_provider_state"])
                    self.assertFalse(retryable["provider_call_status_contract_error"])
                    self.assertFalse(retryable["automatic_retry"])
                    self.assertFalse(retryable["automatic_retry_allowed"])
                    self.assertTrue(retryable["manual_retry_requires_explicit_task"])

        contradictory_pairs = (
            ("failed", "future_failure_taxonomy"),
            ("retry_pending", "future_failure_taxonomy"),
            ("rate_limited_retryable", "permission_denied"),
            ("success", "permission_denied"),
            ("empty", "provider_error_safe"),
            ("future_provider_state", "future_failure_taxonomy"),
        )
        for call_status, failure_mode in contradictory_pairs:
            with self.subTest(contract_error=(call_status, failure_mode)):
                blocked = tushare_task_service._production_provider_failure_stop(
                    {
                        "api": "anns_d",
                        "call_status": call_status,
                        "failure_mode": failure_mode,
                    }
                )
                self.assertFalse(blocked["terminal_provider_failure"])
                self.assertFalse(blocked["retryable_provider_state"])
                self.assertTrue(blocked["provider_call_status_contract_error"])
                self.assertEqual(
                    blocked["stop_classification"],
                    "provider_call_status_contract_error",
                )
                self.assertEqual(
                    blocked["failure_mode"],
                    "provider_call_status_contract_error",
                )
                self.assertFalse(blocked["automatic_retry"])

    def test_retryable_and_unknown_states_stop_remaining_provider_scope(self):
        cases = (
            (
                "failed",
                "permission_denied",
                "stopped_anns_d_permission_denied_safe",
                "terminal",
            ),
            (
                "failed",
                "parse_failed_or_invalid_result",
                "stopped_anns_d_parse_failed_or_invalid_result_safe",
                "terminal",
            ),
            (
                "failed",
                "provider_error_safe",
                "stopped_anns_d_provider_error_safe_safe",
                "terminal",
            ),
            (
                "failed",
                "missing_required_parameter",
                "stopped_anns_d_missing_required_parameter_safe",
                "terminal",
            ),
            ("retry_pending", "", "paused_anns_d_retry_pending_safe", "retryable"),
            (
                "rate_limited_retryable",
                "",
                "paused_anns_d_rate_limited_retryable_safe",
                "retryable",
            ),
            (
                "failed",
                "future_failure_taxonomy",
                "blocked_anns_d_call_status_contract_error_safe",
                "contract_error",
            ),
            (
                "retry_pending",
                "future_failure_taxonomy",
                "blocked_anns_d_call_status_contract_error_safe",
                "contract_error",
            ),
            (
                "rate_limited_retryable",
                "permission_denied",
                "blocked_anns_d_call_status_contract_error_safe",
                "contract_error",
            ),
            (
                "success",
                "permission_denied",
                "blocked_anns_d_call_status_contract_error_safe",
                "contract_error",
            ),
            (
                "empty",
                "provider_error_safe",
                "blocked_anns_d_call_status_contract_error_safe",
                "contract_error",
            ),
            (
                "future_provider_state",
                "future_failure_taxonomy",
                "blocked_anns_d_call_status_contract_error_safe",
                "contract_error",
            ),
        )
        for call_status, failure_mode, expected_step, expected_class in cases:
            with self.subTest(pair=(call_status, failure_mode)):
                task_service._TASKS.clear()
                payload, _recipe, _receipt = self._seed_request_chain()
                existing_packets, existing_files = self._seed_existing_production_state()
                adapter = _FakeFullInterfaceAdapter()

                def ledger_row(api, *, params, now, scope=None, **_kwargs):
                    return {
                        "api": api,
                        "scope_hash": str((scope or {}).get("scope_hash") or ""),
                        "scope_hash_short": str((scope or {}).get("scope_hash_short") or ""),
                        "request_params_safe": params,
                        "row_count": 0,
                        "data_date": None,
                        "local_fetched_at": now,
                        "call_status": call_status,
                        "failure_mode": failure_mode,
                        "failure_mode_status": "unknown",
                        "safe_failure_mode_visible": True,
                        "error_message_safe": call_status,
                        "provider_transport_verified": False,
                        "runtime_adapter_module_identity_verified": False,
                        "parquet_status": "not_written_non_success_state",
                        "external": True,
                        "external_calls_triggered": True,
                        "tushare_called": True,
                        "deepseek_called": False,
                        "github_called": False,
                        "does_not_execute_trades": True,
                        "does_not_modify_strategy_action": True,
                    }

                with patch.object(
                    tushare_task_service,
                    "_call_ledger_row",
                    side_effect=ledger_row,
                ), patch.object(
                    tushare_task_service,
                    "_run_full_market_universe_acceptance",
                    side_effect=AssertionError(
                        "non-success provider state must stop before full-market calls"
                    ),
                ):
                    task = tushare_task_service.run_tushare_full_interface_provider_production_acceptance(
                        payload,
                        adapter=adapter,
                    )

                self.assertEqual(task["status"], "failed")
                self.assertEqual(adapter.calls, ["anns_d"])
                self.assertIn(expected_step, task["current_step"])
                packet = SQLiteMetaStore(self.db_path).read_packet(
                    "command_center_tushare_refresh_packet"
                )
                stop = packet["provider_failure_stop"]
                self.assertTrue(stop["remaining_interfaces_not_called"])
                self.assertTrue(stop["full_market_universe_not_called"])
                self.assertFalse(stop["production_promotion_allowed"])
                self.assertFalse(stop["automatic_retry"])
                if expected_class == "terminal":
                    self.assertTrue(stop["terminal_provider_failure"])
                    self.assertFalse(stop["retryable_provider_state"])
                    self.assertFalse(stop["provider_call_status_contract_error"])
                elif expected_class == "retryable":
                    self.assertFalse(stop["terminal_provider_failure"])
                    self.assertTrue(stop["retryable_provider_state"])
                    self.assertFalse(stop["provider_call_status_contract_error"])
                else:
                    self.assertFalse(stop["terminal_provider_failure"])
                    self.assertFalse(stop["retryable_provider_state"])
                    self.assertTrue(stop["provider_call_status_contract_error"])
                self._assert_existing_production_state_unchanged(
                    existing_packets,
                    existing_files,
                )

    def test_newer_ready_seed_is_authoritative_over_stale_refresh_recipe(self):
        stale = tushare_task_service._provider_target_sample_execution_recipe_seed(self._seed_payload())
        stale["recipe_issued_at"] = "2000-01-01T00:00:00.000000"
        stale["execution_recipe_scope_hash"] = "f" * 64
        SQLiteMetaStore(self.db_path).write_packet(
            "command_center_tushare_refresh_packet",
            {"provider_target_sample_execution_recipe": stale},
        )
        payload, recipe, receipt = self._seed_request_chain()
        self.assertEqual(
            receipt["authoritative_recipe_source_packet_key"],
            tushare_task_service.PROVIDER_TARGET_SAMPLE_EXECUTION_RECIPE_PACKET_KEY,
        )
        gate = tushare_task_service._full_interface_provider_production_execution_gate(
            payload, selected_apis=list(tushare_task_service.ALL_REFRESH_APIS)
        )
        self.assertTrue(gate["ready"])
        self.assertEqual(gate["authoritative_recipe_scope_hash"], recipe["execution_recipe_scope_hash"])

    def test_api_context_or_approval_hash_tampering_blocks_before_provider(self):
        payload, _recipe, _receipt = self._seed_request_chain()
        payload["api_contexts"] = {key: dict(value) for key, value in payload["api_contexts"].items()}
        payload["api_contexts"]["daily"]["end_date"] = "19990101"
        adapter = _FakeFullInterfaceAdapter()
        task = tushare_task_service.run_tushare_full_interface_provider_production_acceptance(payload, adapter=adapter)
        self.assertEqual(task["status"], "failed")
        self.assertEqual(adapter.calls, [])
        self.assertTrue(
            "provider_context_not_bound_to_execution_request" in task["current_step"]
            or "approval_scope_hash_or_material_mismatch" in task["current_step"]
        )

    def test_patched_runtime_methods_and_sdk_local_rejection_have_no_transport_proof(self):
        payload, _recipe, _receipt = self._seed_request_chain()
        import tushare_adapter

        with ExitStack() as stack:
            for api, spec in tushare_task_service.REFRESH_API_SPECS.items():
                stack.enter_context(
                    patch.object(
                        tushare_adapter,
                        spec["method"],
                        return_value={"ok": True, "data": [_representative_row(api)], "error": ""},
                    )
                )
            stack.enter_context(
                patch.object(
                    tushare_adapter,
                    "get_stock_basic",
                    return_value={"ok": True, "data": [{"ts_code": "000001.SZ", "list_status": "L", "list_date": "19910403"}], "error": ""},
                )
            )
            stack.enter_context(patch.object(tushare_task_service, "_write_parquet_dataset", side_effect=self._staged_parquet_result))
            task = tushare_task_service.run_tushare_full_interface_provider_production_acceptance(payload)
        self.assertTrue(all(row["runtime_adapter_module_identity_verified"] for row in task["call_ledger"]))
        self.assertTrue(all(row["provider_transport_verified"] is False for row in task["call_ledger"]))
        production_root = storage_service.PARQUET_ROOT / "full_market_universe"
        self.assertFalse((production_root / "pointer.json").exists())
        self.assertFalse((production_root / "execution_runs").exists())

        task_service._TASKS.clear()
        with ExitStack() as stack:
            for spec in tushare_task_service.REFRESH_API_SPECS.values():
                stack.enter_context(
                    patch.object(
                        tushare_adapter,
                        spec["method"],
                        return_value={"ok": False, "data": None, "error": "sdk rejected local parameter"},
                    )
                )
            stack.enter_context(
                patch.object(
                    tushare_adapter,
                    "get_stock_basic",
                    return_value={"ok": False, "data": None, "error": "sdk rejected local parameter"},
                )
            )
            rejected = tushare_task_service.run_tushare_full_interface_provider_production_acceptance(payload)
        self.assertTrue(all(row["provider_transport_verified"] is False for row in rejected["call_ledger"]))
        self.assertIsNone(SQLiteMetaStore(self.db_path).read_packet(tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY))

    def test_generic_rows_rejected_and_valid_empty_is_explicitly_limited(self):
        generic = tushare_task_service._provider_sample_semantics(
            "daily",
            params=self._contexts()["daily"],
            rows=[{"ts_code": "000001.SZ"}],
            call_status="success",
            provider_transport_verified=True,
        )
        self.assertFalse(generic["representative_sample_verified"])
        self.assertTrue(generic["generic_or_unrepresentative_row_rejected"])
        valid_empty = tushare_task_service._provider_sample_semantics(
            "margin_detail",
            params=self._contexts()["margin_detail"],
            rows=[],
            call_status="empty",
            provider_transport_verified=True,
        )
        invalid_core_empty = tushare_task_service._provider_sample_semantics(
            "daily",
            params=self._contexts()["daily"],
            rows=[],
            call_status="empty",
            provider_transport_verified=True,
        )
        self.assertTrue(valid_empty["valid_empty_semantics_verified"])
        self.assertFalse(invalid_core_empty["valid_empty_semantics_verified"])

    def test_strict_contract_has_a_reachable_verified_evidence_path(self):
        scope = {"scope_hash": "d" * 64, "scope_hash_short": "d" * 16}
        ledger = []
        for api in tushare_task_service.ALL_REFRESH_APIS:
            ledger.append(
                {
                    "api": api,
                    "call_status": "success",
                    "runtime_adapter_module_identity_verified": True,
                    "provider_transport_verified": True,
                    "provider_transport_receipt_count": 1,
                    "representative_sample_verified": True,
                    "valid_empty_semantics_verified": False,
                    "safe_failure_mode_visible": True,
                    "error_message_safe": "",
                    "request_params_safe": {},
                    "scope_hash": scope["scope_hash"],
                    "scope_hash_short": scope["scope_hash_short"],
                    "parquet_status": "staged" if api in tushare_task_service.PARQUET_DATASETS else "not_enabled",
                    "parquet_row_count": 1 if api in tushare_task_service.PARQUET_DATASETS else 0,
                    "parquet_staging_digest": "e" * 64 if api in tushare_task_service.PARQUET_DATASETS else "",
                }
            )
        failure = {
            "safe_error_text": True,
            "unsafe_row_count": 0,
            "permission_denied_distinguishable": True,
            "empty_result_or_no_record_distinguishable": True,
            "parse_failed_or_invalid_result_distinguishable": True,
            "missing_required_parameter_distinguishable": True,
            "provider_error_safe_distinguishable": True,
        }
        kwargs = {
            "production_acceptance_requested": True,
            "execution_gate": {"ready": True},
            "selected_apis": list(tushare_task_service.ALL_REFRESH_APIS),
            "call_ledger": ledger,
            "validation_target_rows": [
                {"readiness": "validated"}
                for _ in tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS
            ],
            "api_acceptance_audit": {"status": "acceptance_audit_passed", "acceptance_issue_count": 0},
            "failure_mode_qa_contract": failure,
            "scope": scope,
            "universe_evidence": {
                "schema_version": tushare_task_service.FULL_MARKET_UNIVERSE_SCHEMA_VERSION,
                "status": "full_market_universe_production_complete",
                "production_complete": True,
                "scope_hash": scope["scope_hash"],
                "provider_provenance_verified": True,
                "packet_digest": "f" * 64,
            },
        }
        staged = tushare_task_service._full_interface_provider_production_contract(**kwargs)
        self.assertTrue(staged["eligible_for_parquet_promotion"])
        self.assertFalse(staged["full_interface_provider_production"])
        for row in ledger:
            if row["api"] in tushare_task_service.PARQUET_DATASETS:
                row["parquet_status"] = "promoted"
                row["parquet_promotion_verified"] = True
        final = tushare_task_service._full_interface_provider_production_contract(
            **kwargs,
            parquet_promotion={"promotion_verified": True, "promoted_dataset_count": 4},
            sqlite_stage_readback_verified=True,
            sqlite_atomic_promotion_verified=True,
        )
        self.assertTrue(final["full_interface_provider_production"])
        self.assertEqual(final["blocking_criterion_count"], 0)

    def test_permission_and_empty_are_safe_but_non_promoting(self):
        payload, _recipe, _receipt = self._seed_request_chain()
        adapter = _FakeFullInterfaceAdapter(empty_api="margin_detail", failed_api="top_list")
        with patch.object(tushare_task_service, "_write_parquet_dataset", side_effect=self._staged_parquet_result):
            task = tushare_task_service.run_tushare_full_interface_provider_production_acceptance(payload, adapter=adapter)
        ledger = {row["api"]: row for row in task["call_ledger"]}
        self.assertEqual(ledger["margin_detail"]["failure_mode"], "empty_result_or_no_record")
        self.assertEqual(ledger["top_list"]["failure_mode"], "permission_denied")
        self.assertTrue(ledger["top_list"]["safe_failure_mode_visible"])
        self.assertNotIn("top_inst", adapter.calls)
        self.assertNotIn("stock_basic", adapter.calls)
        self.assertIsNone(SQLiteMetaStore(self.db_path).read_packet(tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY))

    def test_parquet_partial_promotion_restores_canonical_files(self):
        storage_service.PARQUET_ROOT.mkdir(parents=True)
        ledger = []
        original = {}
        for index, api in enumerate(tushare_task_service.PARQUET_DATASETS):
            dataset = tushare_task_service.PARQUET_DATASETS[api]
            canonical = storage_service.PARQUET_ROOT / f"{dataset}.parquet"
            canonical.write_bytes(f"old-{api}".encode())
            original[api] = canonical.read_bytes()
            staging = self.root / "staging" / f"{dataset}.parquet"
            staging.parent.mkdir(parents=True, exist_ok=True)
            if index < 3:
                staging.write_bytes(f"new-{api}".encode())
            ledger.append(
                {
                    "api": api,
                    "parquet_status": "staged",
                    "parquet_staging_path": str(staging),
                    "parquet_staging_digest": tushare_task_service._sha256_file(staging) if staging.exists() else "a" * 64,
                }
            )
        result = tushare_task_service._promote_staged_parquet_datasets(ledger, scope_hash="b" * 64)
        self.assertFalse(result["promotion_verified"])
        self.assertTrue(result["rollback_succeeded"])
        for api, dataset in tushare_task_service.PARQUET_DATASETS.items():
            self.assertEqual((storage_service.PARQUET_ROOT / f"{dataset}.parquet").read_bytes(), original[api])

    def test_sqlite_commit_and_rollback_failure_preserve_last_good(self):
        store = SQLiteMetaStore(self.db_path)
        store.write_packet(tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY, {"version": "last-good"})
        original_connect = store._connect

        class _ConnectionProxy:
            def __init__(self, connection):
                self.connection = connection
            def execute(self, *args, **kwargs):
                return self.connection.execute(*args, **kwargs)
            def commit(self):
                raise RuntimeError("forced commit failure")
            def rollback(self):
                raise RuntimeError("forced rollback failure")
            def close(self):
                self.connection.close()

        with patch.object(store, "_connect", side_effect=lambda: _ConnectionProxy(original_connect())):
            with self.assertRaises(RuntimeError):
                store.promote_packet_atomic(
                    tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY,
                    {"version": "forged-new"},
                )
        self.assertEqual(
            SQLiteMetaStore(self.db_path).read_packet(tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY),
            {"version": "last-good"},
        )
        store.write_packet(tushare_task_service.FULL_MARKET_UNIVERSE_CURRENT_PACKET_KEY, {"version": "universe-current"})
        store.write_packet(tushare_task_service.FULL_MARKET_UNIVERSE_LAST_GOOD_PACKET_KEY, {"version": "universe-last-good"})
        with patch.object(store, "_connect", side_effect=lambda: _ConnectionProxy(original_connect())):
            with self.assertRaises(RuntimeError):
                store.promote_packet_pair_atomic(
                    tushare_task_service.FULL_MARKET_UNIVERSE_CURRENT_PACKET_KEY,
                    {"version": "forged-current"},
                    tushare_task_service.FULL_MARKET_UNIVERSE_LAST_GOOD_PACKET_KEY,
                    {"version": "forged-last-good"},
                )
        check = SQLiteMetaStore(self.db_path)
        self.assertEqual(check.read_packet(tushare_task_service.FULL_MARKET_UNIVERSE_CURRENT_PACKET_KEY), {"version": "universe-current"})
        self.assertEqual(check.read_packet(tushare_task_service.FULL_MARKET_UNIVERSE_LAST_GOOD_PACKET_KEY), {"version": "universe-last-good"})

    def test_ordinary_refresh_preserves_independent_last_good_packet(self):
        store = SQLiteMetaStore(self.db_path)
        last_good = {"status": "full_interface_provider_production_complete", "immutable": True}
        store.write_packet(tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY, last_good)
        universe_last_good = {"status": "full_market_universe_production_complete", "immutable": True}
        store.write_packet(tushare_task_service.FULL_MARKET_UNIVERSE_LAST_GOOD_PACKET_KEY, universe_last_good)
        tushare_task_service.run_tushare_refresh_task(
            {"apis": ["daily"], "ts_code": "000001.SZ", "start_date": "20260701", "end_date": "20260710"},
            adapter=_FakeFullInterfaceAdapter(),
        )
        self.assertEqual(store.read_packet(tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_PACKET_KEY), last_good)
        self.assertEqual(store.read_packet(tushare_task_service.FULL_MARKET_UNIVERSE_LAST_GOOD_PACKET_KEY), universe_last_good)

    def test_catalog_get_is_cache_only_and_exposes_explicit_production_post(self):
        with patch.object(
            tushare_task_service,
            "run_tushare_full_interface_provider_production_acceptance",
            side_effect=AssertionError("GET must not enter production executor"),
        ):
            response = routes_tasks.get_task_catalog()
        self.assertTrue(response["ok"])
        self.assertFalse(response["data"]["external_calls_triggered"])
        catalog = {item["task_type"]: item for item in response["data"]["tasks"]}
        self.assertEqual(catalog["refresh_tushare_facts"]["full_interface_provider_production_route"], "POST /api/tasks/refresh-tushare-facts")


if __name__ == "__main__":
    unittest.main()
