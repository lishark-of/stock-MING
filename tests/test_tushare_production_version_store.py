import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.services import tushare_production_store as store
from server.services import tushare_task_service


def _datasets(*, recent_listing=False):
    symbols = (
        ("600000.SH", "SSE", "19910101"),
        ("000001.SZ", "SZSE", "19910101"),
        ("430001.BJ", "BSE", "20260709" if recent_listing else "19910101"),
    )
    dates = ("20260708", "20260709", "20260710")
    stock = [
        {
            "ts_code": code,
            "exchange": exchange,
            "list_status": "L",
            "list_date": list_date,
            "name": "sample",
        }
        for code, exchange, list_date in symbols
    ]
    daily = [
        {"ts_code": code, "trade_date": date, "close": 10, "amount": 1}
        for code, _exchange, list_date in symbols
        for date in dates
        if date >= list_date
    ]
    daily_basic = [
        {
            "ts_code": code,
            "trade_date": dates[-1],
            "turnover_rate": 1,
            "total_mv": 1,
            "circ_mv": 1,
        }
        for code, _exchange, _list_date in symbols
    ]
    moneyflow = [
        {
            "ts_code": code,
            "trade_date": date,
            "buy_lg_amount": 1,
            "sell_lg_amount": 1,
        }
        for code, _exchange, list_date in symbols
        for date in dates
        if date >= list_date
    ]
    return {
        "stock_basic": stock,
        "trade_cal": [
            {"exchange": "SSE", "cal_date": date, "is_open": 1}
            for date in dates
        ],
        "daily": daily,
        "daily_basic": daily_basic,
        "moneyflow": moneyflow,
    }


def _write_valid_immutable_version(
    root: Path,
    *,
    version_id=f"{'c' * 16}-{'1' * 32}",
):
    import pandas as pd
    import pyarrow.parquet as pq

    version_dir = root / "versions" / version_id
    version_dir.mkdir(parents=True)
    for name, rows in _datasets().items():
        pd.DataFrame(rows).to_parquet(version_dir / f"{name}.parquet", index=False)
    frames = {
        name: pq.read_table(version_dir / f"{name}.parquet").to_pandas()
        for name in store.DATASETS
    }
    validation = store.validate_datasets(
        frames,
        start_date="20260708",
        end_date="20260710",
    )
    if not validation["ready"]:
        raise AssertionError(validation["blockers"])
    scope_hash = "a" * 64
    producer_head_full = store._current_head_full()
    attempt_id = "1" * 32
    version_id = version_id or f"{'c' * 16}-{attempt_id}"
    events = []
    for api in (*store.EXACT_REFRESH_APIS, *store.EXACT_SUPPORT_APIS):
        event = {
            "schema_version": store.TRANSPORT_EVENT_SCHEMA,
            "run_id": scope_hash,
            "attempt_id": attempt_id,
            "scope_hash": scope_hash,
            "api": api,
            "actual_function_call": True,
            "function_call_count": 1,
            "request_scope_digest": store._digest_value({"api": api}),
            "transport_receipt_digest": store._digest_value({"receipt": api}),
            "response_digest": store._digest_value({"response": api}),
        }
        event["transport_event_digest"] = store._digest_value(event)
        events.append(event)
    receipt = {
        "schema_version": store.EXECUTION_EVENT_SCHEMA,
        "source": "public_non_injected_tushare_executor",
        "status": "official_provider_execution_complete",
        "official_provider_path_completed": True,
        "run_id": scope_hash,
        "attempt_id": attempt_id,
        "scope_hash": scope_hash,
        "producer_head_full": producer_head_full,
        "approval_scope_hash": "b" * 64,
        "execution_recipe_scope_hash": "c" * 64,
        "required_interface_apis": list(store.EXACT_REFRESH_APIS),
        "required_interface_api_digest": store._digest_value(list(store.EXACT_REFRESH_APIS)),
        "required_target_groups": list(store.EXACT_TARGET_GROUPS),
        "required_target_group_digest": store._digest_value(list(store.EXACT_TARGET_GROUPS)),
        "required_support_apis": list(store.EXACT_SUPPORT_APIS),
        "required_support_api_digest": store._digest_value(list(store.EXACT_SUPPORT_APIS)),
        "provider_rate_limit_strategy": store.PROVIDER_RATE_LIMIT_STRATEGY,
        "provider_max_calls_per_minute": store.PROVIDER_MAX_CALLS_PER_MINUTE,
        "provider_min_call_interval_ms": store.PROVIDER_MIN_CALL_INTERVAL_MS,
        "provider_execution_serial": True,
        "trade_cal_repeat_explicitly_acknowledged": True,
        "trade_cal_prior_ltg01_evidence_reused_as_same_run": False,
        "provider_execution_authorization_attestation_id": "d" * 64,
        "provider_execution_authorization_task_id": (
            f"tushare-provider-request-{'b' * 32}"
        ),
        "provider_execution_authorization_nonce_digest": "e" * 64,
        "provider_execution_authorization_external_signature_verified": True,
        "provider_execution_authorization_production_trusted": True,
        "provider_execution_authorization_snapshot_rollback_resistant": True,
        "provider_execution_authorization_attempt_id": attempt_id,
        "provider_execution_authorization_version_id": version_id,
        "provider_execution_authorization_consumption_packet_key": (
            f"{store.PROVIDER_AUTHORIZATION_PACKET_KEY}:{attempt_id}"
        ),
        "provider_execution_authorization_consumption_digest": "f" * 64,
        "provider_max_calls": 271,
        "transport_evidence": events,
        "original_actual_function_call_count": len(events),
        "current_attempt_actual_function_call_count": len(events),
        "checkpoint_reused_function_call_count": 0,
        "production_dataset_digest": store._digest_value(validation["datasets"]),
        "production_dataset_validation_digest": store._digest_value(
            validation["dataset_validation"]
        ),
        "production_universe_digest": validation["universe_digest"],
        "selected_trade_dates_digest": store._digest_value(validation["selected_trade_dates"]),
        "sanitized_call_ledger_digest": store._digest_value([]),
        "contains_secret": False,
        "external_calls_triggered": True,
        "tushare_called_this_attempt": True,
        "tushare_called": True,
        "does_not_execute_trades": True,
    }
    receipt["execution_event_digest"] = store._digest_value(receipt)
    artifacts = {
        name: store._artifact_summary(version_dir / f"{name}.parquet", name=name)
        for name in store.DATASETS
    }
    scope = {
        "scope_hash": scope_hash,
        "start_date": validation["start_date"],
        "end_date": validation["end_date"],
        "selected_trade_dates": validation["selected_trade_dates"],
        "latest_trade_date": validation["latest_trade_date"],
        "universe_count": validation["universe_count"],
        "universe_digest": validation["universe_digest"],
        "exchanges": validation["exchanges"],
        "current_listed_count": validation["current_listed_count"],
        "current_listed_digest": validation["current_listed_digest"],
        "eligible_universe_count": validation["eligible_universe_count"],
        "eligible_universe_digest": validation["eligible_universe_digest"],
        "excluded_recent_symbols": validation["excluded_recent_symbols"],
        "excluded_recent_count": validation["excluded_recent_count"],
        "excluded_recent_digest": validation["excluded_recent_digest"],
        "scored_universe_policy": validation["scored_universe_policy"],
    }
    lineage = {
        "producer_head_full": producer_head_full,
        "approval_scope_hash": receipt["approval_scope_hash"],
        "execution_recipe_scope_hash": receipt["execution_recipe_scope_hash"],
        "as_of": validation["end_date"],
    }
    version_material = {
        "scope": scope,
        "artifacts": artifacts,
        "dataset_validation": validation["dataset_validation"],
        "official_run_receipt": receipt,
        "lineage": lineage,
    }
    manifest = {
        "schema_version": store.MANIFEST_SCHEMA,
        "version_id": version_id,
        **version_material,
        "version_digest": store._digest_value(version_material),
        "contains_secret": False,
    }
    manifest["manifest_digest"] = store._digest_value(manifest)
    store._atomic_json(version_dir / "manifest.json", manifest)
    pointer = store._pointer_payload(
        version_id,
        manifest["manifest_digest"],
        {},
        producer_head_full=producer_head_full,
    )
    store._atomic_json(root / "pointer.json", pointer)
    return manifest, pointer


class TushareProductionVersionStoreTests(unittest.TestCase):
    def setUp(self):
        class _FixtureDate(store._dt.date):
            @classmethod
            def today(cls):
                return cls(2026, 7, 10)

        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "full_market_universe"
        self.constants = patch.multiple(store, MIN_UNIVERSE_ROWS=2, REQUIRED_SESSIONS=3)
        self.constants.start()
        self.head_patch = patch.object(store, "_current_head_full", return_value="f" * 40)
        self.date_patch = patch.object(store._dt, "date", _FixtureDate)
        self.original_authorization_validator = store._trusted_provider_authorization_ready
        self.authorization_patch = patch.object(
            store,
            "_trusted_provider_authorization_ready",
            return_value=True,
        )
        self.head_patch.start()
        self.date_patch.start()
        self.authorization_patch.start()

    def tearDown(self):
        self.authorization_patch.stop()
        self.date_patch.stop()
        self.head_patch.stop()
        self.constants.stop()
        self.tmp.cleanup()

    def test_no_caller_constructible_seal_or_public_promotion_api_exists(self):
        self.assertFalse(hasattr(store, "_seal_official_run"))
        self.assertFalse(hasattr(store, "promote_version"))
        self.assertEqual(
            store.__all__,
            (
                "is_listed_a_share_code",
                "validate_tushare_full_market_production_version",
            ),
        )
        self.assertFalse(store.validate_tushare_full_market_production_version(self.root)["ready"])

    def test_forged_authorization_receipt_cannot_validate_without_trusted_registry(self):
        _write_valid_immutable_version(self.root)
        with patch.object(
            store,
            "_trusted_provider_authorization_ready",
            new=self.original_authorization_validator,
        ):
            result = store.verify_current_version(self.root)
        self.assertFalse(result["ready"])
        self.assertIn("official_provider_receipt_invalid", result["blockers"])

    def test_wrong_exchange_code_families_are_rejected(self):
        for code, exchange in (
            ("000001.SH", "SSE"),
            ("600000.SZ", "SZSE"),
            ("100000.BJ", "BSE"),
            ("610000.SH", "SSE"),
            ("390000.SZ", "SZSE"),
            ("999999.BJ", "BSE"),
        ):
            self.assertFalse(store.is_listed_a_share_code(code))
            self.assertFalse(tushare_task_service._listed_a_share_code(code))
            datasets = _datasets()
            datasets["stock_basic"][0].update({"ts_code": code, "exchange": exchange})
            result = store.validate_datasets(
                datasets,
                start_date="20260708",
                end_date="20260710",
            )
            self.assertIn("stock_basic_exchange_suffix_or_membership_invalid", result["blockers"])

    def test_new_sz_302_family_is_accepted(self):
        self.assertTrue(store.is_listed_a_share_code("302132.SZ"))
        self.assertTrue(tushare_task_service._listed_a_share_code("302132.SZ"))

    def test_task_coverage_minimums_share_the_production_store_session_policy(self):
        self.assertEqual(
            tushare_task_service._full_market_minimum_sessions("daily"),
            store.REQUIRED_SESSIONS,
        )
        self.assertEqual(tushare_task_service._full_market_minimum_sessions("daily_basic"), 1)
        self.assertEqual(
            tushare_task_service._full_market_minimum_sessions("moneyflow"),
            min(5, store.REQUIRED_SESSIONS),
        )

    def test_recent_listings_are_visible_exclusions_not_silent_coverage_reduction(self):
        result = store.validate_datasets(
            _datasets(recent_listing=True),
            start_date="20260708",
            end_date="20260710",
        )
        self.assertTrue(result["ready"], result["blockers"])
        self.assertEqual(result["symbols"], ["000001.SZ", "600000.SH"])
        self.assertEqual(result["excluded_recent_symbols"], ["430001.BJ"])
        self.assertEqual(result["excluded_recent_count"], 1)
        self.assertEqual(len(result["excluded_recent_digest"]), 64)
        self.assertEqual(result["scored_universe_policy"], "listed_L_on_or_before_selected_90_session_start")
        for api in ("daily", "daily_basic", "moneyflow"):
            self.assertNotIn("430001.BJ", {row["ts_code"] for row in result["datasets"][api]})

    def test_stale_rows_and_incomplete_eligible_coverage_fail_closed(self):
        stale = _datasets()
        stale["daily"][0]["trade_date"] = "20200101"
        result = store.validate_datasets(stale, start_date="20260708", end_date="20260710")
        self.assertIn("daily_date_outside_calendar_scope", result["blockers"])

        incomplete = _datasets()
        incomplete["daily_basic"] = incomplete["daily_basic"][:-1]
        result = store.validate_datasets(incomplete, start_date="20260708", end_date="20260710")
        self.assertIn("daily_basic_latest_trade_date_coverage_incomplete", result["blockers"])

    def test_self_signed_checkpoint_without_transport_event_is_not_resumed(self):
        checkpoint_root = Path(self.tmp.name) / "checkpoints"
        params = {"start_date": "20260710", "end_date": "20260710"}
        query_hash = tushare_task_service._canonical_sha256(
            {"api": "daily", "params": params, "limit": 2}
        )
        checkpoint = checkpoint_root / "daily" / query_hash / "000000000.json"
        page = {
            "schema_version": "tushare_provider_page_checkpoint.v1",
            "query_hash": query_hash,
            "api": "daily",
            "offset": 0,
            "limit": 2,
            "rows": [{"ts_code": "000001.SZ", "trade_date": "20260710"}],
            "row_count": 1,
            "page_fingerprint": "f" * 64,
            "terminal": True,
            "provider_transport_verified": True,
            "original_function_call_count": 1,
            "transport_event": {
                "relative_path": "execution_runs/fake/transport_events/daily/fake.json",
                "transport_event_digest": "e" * 64,
                "api": "daily",
            },
        }
        page["checkpoint_digest"] = tushare_task_service._canonical_sha256(page)
        tushare_task_service._atomic_json_write(checkpoint, page)

        class FailingAdapter:
            calls = 0

            def get_daily(self, **_params):
                self.calls += 1
                return {"ok": False, "data": None, "error": "offline"}

        adapter = FailingAdapter()
        rows, ledger = tushare_task_service._paginated_provider_rows(
            adapter,
            api="daily",
            params=params,
            max_rows_per_call=2,
            call_budget={"used": 0, "historical": 0, "limit": 3},
            checkpoint_root=checkpoint_root,
            runtime_event_recorder=lambda **_kwargs: self.fail(
                "a failed provider response must not create runtime evidence"
            ),
        )
        self.assertEqual(rows, [])
        self.assertEqual(ledger["resumed_page_count"], 0)
        self.assertEqual(adapter.calls, 3)
        self.assertFalse(ledger["provider_transport_verified"])

    def test_execution_event_requires_exact_twenty_apis_and_seven_targets(self):
        self.assertEqual(
            store.EXACT_REFRESH_APIS,
            (
                "daily", "daily_basic", "moneyflow", "trade_cal", "margin_detail",
                "top_list", "top_inst", "stk_limit", "limit_list_d", "limit_cpt_list",
                "cyq_perf", "cyq_chips", "anns_d", "forecast", "fina_indicator",
                "stk_holdertrade", "share_float", "pledge_stat", "pledge_detail", "stk_surv",
            ),
        )
        self.assertEqual(
            store.EXACT_TARGET_GROUPS,
            (
                "trade_calendar", "margin_financing", "dragon_tiger", "limit_emotion",
                "chip_distribution", "financial_disclosure", "hard_risk",
            ),
        )
        self.assertFalse(hasattr(tushare_task_service, "_official_transport_event"))
        self.assertFalse(hasattr(tushare_task_service, "_persist_official_execution_event"))
        self.assertFalse(hasattr(store, "_promote_version_from_official_execution_event"))
        result = store._review_external_promotion_request(
            _datasets(),
            root=self.root,
            scope_hash="a" * 64,
        )
        self.assertFalse(result["promotion_verified"])
        self.assertEqual(result["blockers"], ["module_level_promotion_disabled"])

    def test_inline_manifest_evidence_cannot_be_overwritten_by_attempt_files(self):
        manifest, _pointer = _write_valid_immutable_version(self.root)
        first = store.verify_current_version(self.root)
        self.assertTrue(first["ready"], first["blockers"])
        manifest_text = json.dumps(manifest, sort_keys=True)
        self.assertNotIn("execution_runs/", manifest_text)
        self.assertNotIn("transport_event_ref", manifest_text)

        mutable = self.root / ".attempts" / ("a" * 64) / ("1" * 32) / "event.json"
        mutable.parent.mkdir(parents=True)
        mutable.write_text('{"forged":true}', encoding="utf-8")
        mutable.write_text('{"forged":false}', encoding="utf-8")
        second = store.verify_current_version(self.root)
        self.assertTrue(second["ready"], second["blockers"])
        self.assertEqual(first["manifest_digest"], second["manifest_digest"])

    def test_signed_call_budget_cannot_be_exceeded_by_digest_consistent_receipt(self):
        manifest, pointer = _write_valid_immutable_version(self.root)
        receipt = manifest["official_run_receipt"]
        total_calls = sum(
            int(event["function_call_count"])
            for event in receipt["transport_evidence"]
        )
        receipt["provider_max_calls"] = total_calls - 1
        receipt_material = dict(receipt)
        receipt_material.pop("execution_event_digest", None)
        receipt["execution_event_digest"] = store._digest_value(receipt_material)
        version_material = {
            "scope": manifest["scope"],
            "artifacts": manifest["artifacts"],
            "dataset_validation": manifest["dataset_validation"],
            "official_run_receipt": receipt,
            "lineage": manifest["lineage"],
        }
        manifest["version_digest"] = store._digest_value(version_material)
        manifest_material = dict(manifest)
        manifest_material.pop("manifest_digest", None)
        manifest["manifest_digest"] = store._digest_value(manifest_material)
        store._atomic_json(
            self.root / "versions" / manifest["version_id"] / "manifest.json",
            manifest,
        )
        pointer["current_manifest_digest"] = manifest["manifest_digest"]
        pointer["last_good_manifest_digest"] = manifest["manifest_digest"]
        pointer_material = dict(pointer)
        pointer_material.pop("pointer_digest", None)
        pointer["pointer_digest"] = store._digest_value(pointer_material)
        store._atomic_json(self.root / "pointer.json", pointer)

        result = store.verify_current_version(self.root)
        self.assertFalse(result["ready"])
        self.assertIn("official_provider_receipt_invalid", result["blockers"])

    def test_current_head_is_required_but_history_mode_preserves_old_version(self):
        manifest, _pointer = _write_valid_immutable_version(self.root)
        producer_head = manifest["lineage"]["producer_head_full"]
        self.assertTrue(
            store.verify_current_version(self.root)["ready"]
        )
        different_head = "0" * 40 if producer_head != "0" * 40 else "1" * 40
        with patch.object(store, "_current_head_full", return_value=different_head):
            current = store.verify_current_version(self.root)
        self.assertFalse(current["ready"])
        self.assertIn("current_production_version_head_mismatch", current["blockers"])
        historical = store.verify_current_version(
            self.root,
            head_mode="history",
            runtime_head_full=different_head,
        )
        self.assertFalse(historical["ready"])
        self.assertTrue(
            historical["historical_integrity_ready"], historical["blockers"]
        )

    def test_receipt_pointer_and_manifest_producer_heads_must_match(self):
        manifest, pointer = _write_valid_immutable_version(self.root)
        pointer["current_producer_head_full"] = "0" * 40
        pointer_material = dict(pointer)
        pointer_material.pop("pointer_digest", None)
        pointer["pointer_digest"] = store._digest_value(pointer_material)
        store._atomic_json(self.root / "pointer.json", pointer)
        result = store.verify_current_version(
            self.root,
            runtime_head_full=manifest["lineage"]["producer_head_full"],
        )
        self.assertFalse(result["ready"])
        self.assertIn("current_production_version_head_mismatch", result["blockers"])
        self.assertIn("approval_recipe_as_of_lineage_invalid", result["blockers"])

    def test_current_mode_rejects_next_day_but_history_remains_readable(self):
        _write_valid_immutable_version(self.root)

        class _NextDay(store._dt.date):
            @classmethod
            def today(cls):
                return cls(2026, 7, 11)

        with patch.object(store._dt, "date", _NextDay):
            current = store.verify_current_version(self.root)
            historical = store.verify_current_version(
                self.root,
                head_mode="history",
                runtime_head_full="0" * 40,
            )
        self.assertFalse(current["ready"])
        self.assertIn("current_production_version_as_of_stale", current["blockers"])
        self.assertFalse(historical["ready"])
        self.assertTrue(
            historical["historical_integrity_ready"], historical["blockers"]
        )

    def test_first_version_last_good_manifest_digest_is_always_validated(self):
        _manifest, pointer = _write_valid_immutable_version(self.root)
        self.assertTrue(store.verify_current_version(self.root)["ready"])
        pointer["last_good_manifest_digest"] = "f" * 64
        pointer_material = dict(pointer)
        pointer_material.pop("pointer_digest", None)
        pointer["pointer_digest"] = store._digest_value(pointer_material)
        store._atomic_json(self.root / "pointer.json", pointer)
        result = store.verify_current_version(self.root)
        self.assertFalse(result["ready"])
        self.assertIn("last_good_manifest_binding_invalid", result["blockers"])

    def test_double_pointer_restore_is_idempotent_without_production_promotion(self):
        pointer = self.root / "pointer.json"
        original = json.dumps({"current_version": "old"}, sort_keys=True).encode()
        tushare_task_service._atomic_json_write(pointer, {"current_version": "new"})
        self.assertTrue(store._restore_pointer(pointer, original))
        self.assertTrue(store._restore_pointer(pointer, original))
        self.assertEqual(pointer.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
