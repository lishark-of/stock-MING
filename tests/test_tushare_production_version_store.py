import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.services import tushare_production_store as store
from server.services import storage_service, tushare_task_service


class _PacketStore:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.packet = None

    def promote_packet_atomic(self, _key, packet):
        if self.fail:
            raise RuntimeError("forced packet failure")
        self.packet = copy.deepcopy(packet)
        return {"transaction_committed": True}

    def read_packet(self, _key):
        return copy.deepcopy(self.packet)


def _datasets(marker=0):
    symbols = (
        ("600000.SH", "SSE"),
        ("000001.SZ", "SZSE"),
        ("430001.BJ", "BSE"),
    )
    dates = ("20260708", "20260709", "20260710")
    stock = [
        {
            "ts_code": code,
            "exchange": exchange,
            "list_status": "L",
            "list_date": "19910101",
            "name": f"sample-{marker}",
        }
        for code, exchange in symbols
    ]
    daily = [
        {"ts_code": code, "trade_date": date, "close": 10 + marker, "amount": 1}
        for code, _exchange in symbols
        for date in dates
    ]
    daily_basic = [
        {
            "ts_code": code,
            "trade_date": dates[-1],
            "turnover_rate": 1,
            "total_mv": 1,
            "circ_mv": 1,
        }
        for code, _exchange in symbols
    ]
    moneyflow = [
        {
            "ts_code": code,
            "trade_date": date,
            "buy_lg_amount": 1,
            "sell_lg_amount": 1,
        }
        for code, _exchange in symbols
        for date in dates
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


def _seal(scope_hash):
    ledger = [
        {"api": api, "provider_transport_verified": True, "provider_call_count": 1}
        for api in store.DATASETS
    ]
    return store._seal_official_run(
        call_ledger=ledger,
        scope_hash=scope_hash,
        approval_scope_hash="a" * 64,
        execution_recipe_scope_hash="b" * 64,
        required_interface_apis=list(store.DATASETS),
        public_executor_completed=True,
    )


class TushareProductionVersionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "full_market_universe"
        self.constants = patch.multiple(
            store,
            MIN_UNIVERSE_ROWS=3,
            REQUIRED_SESSIONS=3,
            MIN_FULL_INTERFACE_APIS=5,
        )
        self.constants.start()

    def tearDown(self):
        self.constants.stop()
        self.tmp.cleanup()

    def _promote(self, datasets, *, scope="c" * 64, packet_store=None):
        return store.promote_version(
            datasets,
            root=self.root,
            scope_hash=scope,
            start_date="20260708",
            end_date="20260710",
            approval_scope_hash="a" * 64,
            execution_recipe_scope_hash="b" * 64,
            as_of="20260710",
            seal=_seal(scope),
            packet_store=packet_store or _PacketStore(),
            packet_key="production",
        )

    def test_forged_one_row_and_row_scope_counterexamples_fail_closed(self):
        one = {name: rows[:1] for name, rows in _datasets().items()}
        self.assertFalse(store.validate_datasets(one, start_date="20260708", end_date="20260710")["ready"])

        wrong_suffix = _datasets()
        wrong_suffix["stock_basic"][0]["ts_code"] = "600000.SZ"
        result = store.validate_datasets(wrong_suffix, start_date="20260708", end_date="20260710")
        self.assertIn("stock_basic_exchange_suffix_or_membership_invalid", result["blockers"])

        stale = _datasets()
        stale["daily"][0]["trade_date"] = "20200101"
        result = store.validate_datasets(stale, start_date="20260708", end_date="20260710")
        self.assertIn("daily_date_outside_calendar_scope", result["blockers"])

        missing_latest = _datasets()
        missing_latest["daily_basic"] = missing_latest["daily_basic"][:-1]
        result = store.validate_datasets(missing_latest, start_date="20260708", end_date="20260710")
        self.assertIn("daily_basic_latest_trade_date_coverage_incomplete", result["blockers"])

    def test_second_promotion_keeps_previous_immutable_last_good(self):
        first = self._promote(_datasets(1), scope="c" * 64)
        self.assertTrue(first["promotion_verified"])
        first_version = first["version_id"]
        second = self._promote(_datasets(2), scope="d" * 64)
        self.assertTrue(second["promotion_verified"])
        pointer = json.loads((self.root / "pointer.json").read_text())
        self.assertEqual(pointer["current_version"], second["version_id"])
        self.assertEqual(pointer["last_good_version"], first_version)
        verified = store.validate_tushare_full_market_production_version(self.root, include_frames=True)
        self.assertTrue(verified["ready"], verified["blockers"])
        self.assertEqual(set(verified["frames"]), set(store.DATASETS))

    def test_packet_failure_and_double_rollback_restore_exact_pointer(self):
        first = self._promote(_datasets(1))
        before = (self.root / "pointer.json").read_bytes()
        last_failure = None
        for marker in (2, 3):
            result = self._promote(_datasets(marker), scope=str(marker) * 64, packet_store=_PacketStore(fail=True))
            last_failure = result
            self.assertFalse(result["promotion_verified"])
            self.assertTrue(result["rollback_succeeded"])
            self.assertEqual((self.root / "pointer.json").read_bytes(), before)
        self.assertTrue(store.rollback_promotion(last_failure))
        self.assertTrue(store.rollback_promotion(last_failure))
        self.assertEqual((self.root / "pointer.json").read_bytes(), before)

    def test_digest_and_partial_move_failure_never_switch_pointer(self):
        first = self._promote(_datasets(1))
        before = (self.root / "pointer.json").read_bytes()
        with patch.object(store, "_sha256_file", side_effect=RuntimeError("digest failure")):
            failed = self._promote(_datasets(2), scope="e" * 64)
        self.assertFalse(failed["promotion_verified"])
        self.assertEqual((self.root / "pointer.json").read_bytes(), before)

        real_digest = store._sha256_file
        digest_calls = 0

        def fail_during_pointer_readback(path):
            nonlocal digest_calls
            digest_calls += 1
            if digest_calls > len(store.DATASETS):
                raise RuntimeError("post-pointer digest failure")
            return real_digest(path)

        with patch.object(store, "_sha256_file", side_effect=fail_during_pointer_readback):
            failed = self._promote(_datasets(2), scope="e" * 64)
        self.assertFalse(failed["promotion_verified"])
        self.assertTrue(failed["rollback_succeeded"])
        self.assertEqual((self.root / "pointer.json").read_bytes(), before)

    def test_ordinary_refresh_write_leaves_production_version_untouched(self):
        promoted = self._promote(_datasets(1))
        self.assertTrue(promoted["promotion_verified"])
        before = (self.root / "pointer.json").read_bytes()
        with patch.object(storage_service, "PARQUET_ROOT", self.root.parent):
            result = tushare_task_service._write_parquet_dataset(
                "daily",
                _datasets(9)["daily"],
                payload={"acceptance_mode": "ordinary_refresh"},
                scope={"scope_hash": "ordinary"},
            )
        self.assertEqual(result["status"], "written")
        self.assertEqual((self.root / "pointer.json").read_bytes(), before)
        self.assertTrue(store.validate_tushare_full_market_production_version(self.root)["ready"])

        real_replace = store.os.replace

        def fail_version_move(source, destination):
            if Path(destination).parent.name == "versions":
                raise RuntimeError("partial move failure")
            return real_replace(source, destination)

        with patch.object(store.os, "replace", side_effect=fail_version_move):
            failed = self._promote(_datasets(3), scope="f" * 64)
        self.assertFalse(failed["promotion_verified"])
        self.assertEqual((self.root / "pointer.json").read_bytes(), before)

    def test_repeated_page_is_detected_as_truncation_and_checkpoint_resumes(self):
        class Adapter:
            def get_daily(self, **_params):
                return {"ok": True, "data": [{"ts_code": "000001.SZ", "trade_date": "20260710"}]}

        with patch.object(
            tushare_task_service,
            "_consume_runtime_transport_evidence",
            return_value={"provider_transport_verified": True},
        ):
            rows, ledger = tushare_task_service._paginated_provider_rows(
                Adapter(),
                api="daily",
                params={"start_date": "20260710", "end_date": "20260710"},
                max_rows_per_call=1,
                call_budget={"used": 0},
                checkpoint_root=Path(self.tmp.name) / "checkpoints",
            )
        self.assertEqual(rows, [])
        self.assertFalse(ledger["pagination_complete"])
        self.assertTrue(ledger["truncation_detected"])

        class OnePageAdapter:
            calls = 0

            def get_daily(self, **_params):
                self.calls += 1
                return {"ok": True, "data": [{"ts_code": "000001.SZ", "trade_date": "20260710"}]}

        checkpoint_root = Path(self.tmp.name) / "resume-checkpoints"
        adapter = OnePageAdapter()
        with patch.object(
            tushare_task_service,
            "_consume_runtime_transport_evidence",
            return_value={"provider_transport_verified": True},
        ):
            first_rows, first_ledger = tushare_task_service._paginated_provider_rows(
                adapter,
                api="daily",
                params={"start_date": "20260710", "end_date": "20260710"},
                max_rows_per_call=2,
                call_budget={"used": 0},
                checkpoint_root=checkpoint_root,
            )
            second_rows, second_ledger = tushare_task_service._paginated_provider_rows(
                adapter,
                api="daily",
                params={"start_date": "20260710", "end_date": "20260710"},
                max_rows_per_call=2,
                call_budget={"used": 0},
                checkpoint_root=checkpoint_root,
            )
        self.assertEqual(first_rows, second_rows)
        self.assertEqual(adapter.calls, 1)
        self.assertTrue(first_ledger["pagination_complete"])
        self.assertEqual(second_ledger["resumed_page_count"], 1)


if __name__ == "__main__":
    unittest.main()
