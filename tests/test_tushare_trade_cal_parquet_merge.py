from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.services import storage_service, tushare_task_service
from storage import parquet_store


@unittest.skipUnless(parquet_store.dependency_status().get("available"), "Parquet dependencies unavailable")
class TushareTradeCalParquetMergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.original_parquet_root = storage_service.PARQUET_ROOT
        storage_service.PARQUET_ROOT = self.root / "parquet"

    def tearDown(self):
        storage_service.PARQUET_ROOT = self.original_parquet_root
        self.tmp.cleanup()

    @staticmethod
    def _trade_cal_rows(start: str, end: str, *, exchanges: tuple[str, ...] = ("SSE", "SZSE"), is_open: int = 1):
        start_date = dt.datetime.strptime(start, "%Y%m%d").date()
        end_date = dt.datetime.strptime(end, "%Y%m%d").date()
        rows = []
        cursor = start_date
        while cursor <= end_date:
            for exchange in exchanges:
                rows.append(
                    {
                        "exchange": exchange,
                        "cal_date": cursor.strftime("%Y%m%d"),
                        "is_open": is_open,
                        "pretrade_date": (cursor - dt.timedelta(days=1)).strftime("%Y%m%d"),
                    }
                )
            cursor += dt.timedelta(days=1)
        return rows

    def _read_trade_cal(self):
        import pandas as pd

        return pd.read_parquet(storage_service.PARQUET_ROOT / "trade_cal.parquet")

    def test_trade_cal_narrow_sample_merges_without_shortening_existing_window(self):
        long_rows = self._trade_cal_rows("20240715", "20260715")
        long_result = tushare_task_service._write_parquet_dataset("trade_cal", long_rows)
        self.assertEqual(long_result["status"], "written")

        narrow_rows = self._trade_cal_rows("20260417", "20260715")
        narrow_rows[-2]["is_open"] = 0
        narrow_result = tushare_task_service._write_parquet_dataset("trade_cal", narrow_rows)
        self.assertEqual(narrow_result["status"], "written")
        self.assertEqual(narrow_result["merge_status"], "trade_cal_canonical_merged_exchange_cal_date")

        df = self._read_trade_cal()
        self.assertEqual(int(len(df)), len(long_rows))
        self.assertEqual(str(df["cal_date"].min()), "20240715")
        self.assertEqual(str(df["cal_date"].max()), "20260715")
        updated = df[(df["exchange"] == "SSE") & (df["cal_date"].astype(str) == "20260715")]
        self.assertEqual(int(updated.iloc[0]["is_open"]), 0)

    def test_trade_cal_merge_normalizes_mixed_key_dtypes_and_incoming_wins(self):
        import pandas as pd

        existing = pd.DataFrame(
            [
                {
                    "exchange": " sse ",
                    "cal_date": 20260715,
                    "is_open": 1,
                    "pretrade_date": "20260714",
                    "source": "old",
                },
                {
                    "exchange": "SZSE",
                    "cal_date": 20260716,
                    "is_open": 1,
                    "pretrade_date": "20260715",
                    "source": "kept",
                },
            ]
        )
        parquet_store.write_dataset(existing, root=storage_service.PARQUET_ROOT, name="trade_cal")

        result = tushare_task_service._write_parquet_dataset(
            "trade_cal",
            [
                {
                    "exchange": "SSE",
                    "cal_date": "20260715",
                    "is_open": 0,
                    "pretrade_date": "20260714",
                    "source": "incoming",
                }
            ],
        )

        self.assertEqual(result["status"], "written")
        self.assertTrue(result["dedupe_key_normalized"])
        df = self._read_trade_cal()
        self.assertEqual(int(len(df)), 2)
        self.assertNotIn("__trade_cal_exchange_key", set(df.columns))
        self.assertNotIn("__trade_cal_cal_date_key", set(df.columns))
        sse = df[(df["exchange"] == "SSE") & (df["cal_date"].astype(str) == "20260715")]
        self.assertEqual(int(len(sse)), 1)
        self.assertEqual(int(sse.iloc[0]["is_open"]), 0)
        self.assertEqual(str(sse.iloc[0]["source"]), "incoming")

    def test_trade_cal_merge_failure_preserves_existing_canonical(self):
        original_rows = self._trade_cal_rows("20240715", "20240717", exchanges=("SSE",))
        first = tushare_task_service._write_parquet_dataset("trade_cal", original_rows)
        self.assertEqual(first["status"], "written")
        before = (storage_service.PARQUET_ROOT / "trade_cal.parquet").read_bytes()

        with patch.object(tushare_task_service.parquet_store, "write_dataset", wraps=parquet_store.write_dataset) as write:
            with patch("pandas.read_parquet", side_effect=RuntimeError("simulated read failure")):
                failed = tushare_task_service._write_parquet_dataset(
                    "trade_cal",
                    self._trade_cal_rows("20260714", "20260715", exchanges=("SSE",)),
                )
            write.assert_not_called()

        after = (storage_service.PARQUET_ROOT / "trade_cal.parquet").read_bytes()
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["merge_status"], "trade_cal_canonical_merge_failed_preserved_existing")
        self.assertEqual(before, after)
        df = self._read_trade_cal()
        self.assertEqual(list(df["cal_date"].astype(str)), ["20240715", "20240716", "20240717"])
