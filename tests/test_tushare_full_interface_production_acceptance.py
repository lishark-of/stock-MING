import tempfile
import unittest
import datetime as dt
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
