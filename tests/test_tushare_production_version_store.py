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


class TushareProductionVersionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "full_market_universe"
        self.constants = patch.multiple(store, MIN_UNIVERSE_ROWS=2, REQUIRED_SESSIONS=3)
        self.constants.start()

    def tearDown(self):
        self.constants.stop()
        self.tmp.cleanup()

    def test_no_caller_constructible_seal_or_public_promotion_api_exists(self):
        self.assertFalse(hasattr(store, "_seal_official_run"))
        self.assertFalse(hasattr(store, "promote_version"))
        self.assertEqual(store.__all__, ("validate_tushare_full_market_production_version",))
        self.assertFalse(store.validate_tushare_full_market_production_version(self.root)["ready"])

    def test_wrong_exchange_code_families_are_rejected(self):
        for code, exchange in (
            ("000001.SH", "SSE"),
            ("600000.SZ", "SZSE"),
            ("100000.BJ", "BSE"),
        ):
            datasets = _datasets()
            datasets["stock_basic"][0].update({"ts_code": code, "exchange": exchange})
            result = store.validate_datasets(
                datasets,
                start_date="20260708",
                end_date="20260710",
            )
            self.assertIn("stock_basic_exchange_suffix_or_membership_invalid", result["blockers"])

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
            production_root=self.root,
            run_id="a" * 64,
            scope_hash="a" * 64,
        )
        self.assertEqual(rows, [])
        self.assertEqual(ledger["resumed_page_count"], 0)
        self.assertEqual(adapter.calls, 3)
        self.assertFalse(ledger["provider_transport_verified"])

    def test_checkpoint_resume_uses_prior_event_without_claiming_new_call(self):
        scope_hash = "a" * 64
        params = {"start_date": "20260710", "end_date": "20260710"}
        query_hash = tushare_task_service._canonical_sha256(
            {"api": "daily", "params": params, "limit": 2}
        )
        rows = [{"ts_code": "000001.SZ", "trade_date": "20260710"}]
        fingerprint = tushare_task_service._canonical_sha256(rows)
        ref = tushare_task_service._official_transport_event(
            self.root,
            run_id=scope_hash,
            scope_hash=scope_hash,
            api="daily",
            event_key=f"{query_hash}-000000000",
            function_call_count=1,
            transport_receipt_digest="b" * 64,
            response_digest=fingerprint,
        )
        checkpoint_root = Path(self.tmp.name) / "resume-checkpoints"
        checkpoint = checkpoint_root / "daily" / query_hash / "000000000.json"
        page = {
            "schema_version": "tushare_provider_page_checkpoint.v1",
            "query_hash": query_hash,
            "api": "daily",
            "offset": 0,
            "limit": 2,
            "rows": rows,
            "row_count": 1,
            "page_fingerprint": fingerprint,
            "terminal": True,
            "provider_transport_verified": True,
            "original_function_call_count": 1,
            "transport_event": ref,
        }
        page["checkpoint_digest"] = tushare_task_service._canonical_sha256(page)
        tushare_task_service._atomic_json_write(checkpoint, page)

        class MustNotCallAdapter:
            def get_daily(self, **_params):
                raise AssertionError("checkpoint resume must not call provider")

        result_rows, ledger = tushare_task_service._paginated_provider_rows(
            MustNotCallAdapter(),
            api="daily",
            params=params,
            max_rows_per_call=2,
            call_budget={"used": 0, "historical": 0, "limit": 3},
            checkpoint_root=checkpoint_root,
            production_root=self.root,
            run_id=scope_hash,
            scope_hash=scope_hash,
        )
        self.assertEqual(result_rows, rows)
        self.assertEqual(ledger["provider_call_count"], 0)
        self.assertEqual(ledger["historical_provider_call_count"], 1)
        self.assertFalse(ledger["tushare_called"])
        self.assertFalse(ledger["external_calls_triggered"])
        self.assertTrue(ledger["checkpoint_data_reused"])

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
        missing = tushare_task_service._persist_official_execution_event(
            self.root,
            run_id="a" * 64,
            scope_hash="a" * 64,
            approval_scope_hash="b" * 64,
            execution_recipe_scope_hash="c" * 64,
            selected_apis=list(store.EXACT_REFRESH_APIS[:-1]),
            target_groups=list(store.EXACT_TARGET_GROUPS),
            transport_events=[],
            current_attempt_actual_function_call_count=0,
            call_ledger=[],
        )
        self.assertIsNone(missing)
        fake_api = list(store.EXACT_REFRESH_APIS)
        fake_api[-1] = "fake_api"
        fake = tushare_task_service._persist_official_execution_event(
            self.root,
            run_id="a" * 64,
            scope_hash="a" * 64,
            approval_scope_hash="b" * 64,
            execution_recipe_scope_hash="c" * 64,
            selected_apis=fake_api,
            target_groups=list(store.EXACT_TARGET_GROUPS),
            transport_events=[],
            current_attempt_actual_function_call_count=0,
            call_ledger=[],
        )
        self.assertIsNone(fake)
        wrong_targets = tushare_task_service._persist_official_execution_event(
            self.root,
            run_id="a" * 64,
            scope_hash="a" * 64,
            approval_scope_hash="b" * 64,
            execution_recipe_scope_hash="c" * 64,
            selected_apis=list(store.EXACT_REFRESH_APIS),
            target_groups=[*store.EXACT_TARGET_GROUPS[:-1], "fake_target"],
            transport_events=[],
            current_attempt_actual_function_call_count=0,
            call_ledger=[],
        )
        self.assertIsNone(wrong_targets)

    def test_double_pointer_restore_is_idempotent_without_production_promotion(self):
        pointer = self.root / "pointer.json"
        original = json.dumps({"current_version": "old"}, sort_keys=True).encode()
        tushare_task_service._atomic_json_write(pointer, {"current_version": "new"})
        self.assertTrue(store._restore_pointer(pointer, original))
        self.assertTrue(store._restore_pointer(pointer, original))
        self.assertEqual(pointer.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
