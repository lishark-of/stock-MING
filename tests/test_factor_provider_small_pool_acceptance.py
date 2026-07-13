import tempfile
import unittest
from pathlib import Path

from server.services import factor_service, packet_service, task_service
from storage.sqlite_meta import SQLiteMetaStore


class FactorProviderSmallPoolAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "meta.sqlite"
        self.original_factor_meta_path = factor_service.SQLITE_META_PATH
        self.original_packet_meta_path = packet_service.SQLITE_META_PATH
        self.original_task_meta_path = task_service.SQLITE_META_PATH
        factor_service.SQLITE_META_PATH = self.db_path
        packet_service.SQLITE_META_PATH = self.db_path
        task_service.SQLITE_META_PATH = self.db_path
        task_service._TASKS.clear()

    def tearDown(self):
        task_service._TASKS.clear()
        factor_service.SQLITE_META_PATH = self.original_factor_meta_path
        packet_service.SQLITE_META_PATH = self.original_packet_meta_path
        task_service.SQLITE_META_PATH = self.original_task_meta_path
        self.tmp.cleanup()

    def _seed_execution_request(self, symbols):
        SQLiteMetaStore(self.db_path).write_packet(
            "command_center_factor_quant_hub_packet",
            {
                "packet_key": "command_center_factor_quant_hub_packet",
                "factor_tests": {
                    "provider_small_pool_execution_request_receipt": {
                        "schema_version": "factor_test_provider_small_pool_execution_request.v1",
                        "status": "factor_test_provider_small_pool_execution_request_ready_manual_provider_task_pending",
                        "local_execution_request_ready": True,
                        "acceptance_scope_hash": "scope-bound-small-pool-v03",
                        "acceptance_scope_hash_short": "scope-v03",
                        "symbols": symbols,
                        "symbol_count": len(symbols),
                        "start_date": "20260401",
                        "end_date": "20260629",
                        "window_days": 90,
                        "metrics": list(factor_service.FACTOR_TEST_PROVIDER_SMALL_POOL_REQUIRED_METRICS),
                        "forward_return_horizons": ["1d", "5d"],
                        "required_datasets": list(factor_service.FACTOR_TEST_PROVIDER_SMALL_POOL_ALLOWED_DATASETS),
                    }
                },
                "call_ledger": [],
                "warnings": [],
            },
        )

    def _fixture(self, symbols):
        trade_dates = ["20260623", "20260624", "20260625", "20260626"]
        daily = {}
        daily_basic = {}
        for symbol_index, symbol in enumerate(symbols):
            daily[symbol] = []
            daily_basic[symbol] = []
            base = 10.0 + symbol_index
            for day_index, trade_date in enumerate(trade_dates):
                close = base + day_index * (0.1 + symbol_index * 0.02)
                daily[symbol].append(
                    {
                        "ts_code": symbol,
                        "trade_date": trade_date,
                        "open": close - 0.03,
                        "high": close + 0.06,
                        "low": close - 0.06,
                        "close": round(close, 4),
                        "pct_chg": round(0.2 + symbol_index * 0.1, 4),
                    }
                )
                daily_basic[symbol].append(
                    {
                        "ts_code": symbol,
                        "trade_date": trade_date,
                        "turnover_rate": round(1.0 + symbol_index * 0.2, 4),
                        "total_mv": 100000 + symbol_index * 1000,
                    }
                )
        return {
            "trade_cal": [{"cal_date": trade_date, "is_open": 1, "exchange": "SSE"} for trade_date in trade_dates],
            "daily": daily,
            "daily_basic": daily_basic,
        }

    def test_post_acceptance_task_uses_fake_provider_fixture_and_cache_readback_without_external_calls(self):
        symbols = ["000001.SZ", "000002.SZ", "600000.SH", "600519.SH", "300750.SZ"]
        self._seed_execution_request(symbols)

        task = factor_service.run_factor_test_provider_small_pool_acceptance_task(
            {
                "approved_by_user": True,
                "scope_hash": "scope-bound-small-pool-v03",
                "provider_mode": "fake",
                "fake_provider_approved_by_user": True,
                "provider_fixture": self._fixture(symbols),
            }
        )

        self.assertEqual(task["status"], "success")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        receipt = task["payload_safe"]["provider_small_pool_acceptance_receipt"]
        self.assertEqual(
            receipt["status"],
            "factor_test_provider_small_pool_acceptance_provider_sample_ready_research_metrics_pending_controls",
        )
        self.assertEqual(receipt["sample_symbol_count"], 5)
        self.assertEqual(set(receipt["symbols_with_core_rows"]), set(symbols))
        self.assertTrue(receipt["provider_call_ledger_evidence_done"])
        self.assertTrue(receipt["sample_rows_collected"])
        self.assertFalse(receipt["production_factor_test_validation_complete"])
        self.assertEqual(receipt["research_metrics"]["status"], "computed_research_only")
        self.assertEqual(receipt["research_metrics"]["decision_usage"], "no-buy/no-action/no-trade")
        self.assertEqual(receipt["research_metrics"]["pit"]["status"], "pending_provider_lineage_review")
        self.assertEqual(receipt["research_metrics"]["survivorship_bias"]["status"], "pending_universe_membership_evidence")
        self.assertEqual(receipt["research_metrics"]["industry_neutralization"]["status"], "pending_industry_classification_evidence")

        provider_ledger = [
            row for row in receipt["call_ledger"] if row.get("api") in {"trade_cal", "daily", "daily_basic"}
        ]
        self.assertEqual({row["api"] for row in provider_ledger}, {"trade_cal", "daily", "daily_basic"})
        self.assertNotIn("moneyflow", {row["api"] for row in provider_ledger})
        self.assertTrue(
            all(row["call_status"] in {"success", "permission_denied", "no_data", "parse_error", "stale"} for row in provider_ledger)
        )
        self.assertTrue(all(row["external_calls_triggered"] is False for row in provider_ledger))
        self.assertTrue(all(row["tushare_called"] is False for row in provider_ledger))

        cached = factor_service.read_factor_quant_cache()
        cached_receipt = cached["factor_tests"]["provider_small_pool_acceptance_receipt"]
        self.assertEqual(cached_receipt["status"], receipt["status"])
        self.assertFalse(cached["external_calls_triggered"])
        self.assertFalse(cached["tushare_called"])

    def test_small_pool_dry_run_clamps_symbols_and_blocks_windows_over_ninety_days(self):
        payload = {
            "approved_by_user": True,
            "symbols": ["000001.SZ", "000002.SZ", "600000.SH", "600519.SH", "300750.SZ", "002594.SZ"],
            "start_date": "20260301",
            "end_date": "20260629",
        }

        payload_safe = factor_service._factor_test_provider_small_pool_dry_run_payload(
            payload,
            "2026-06-29T10:00:00",
        )
        receipt, _rows = factor_service._factor_test_provider_small_pool_dry_run_receipt(
            payload_safe,
            "2026-06-29T10:00:00",
        )

        self.assertEqual(payload_safe["symbol_limit"], 5)
        self.assertEqual(payload_safe["symbol_count"], 5)
        self.assertEqual(payload_safe["ignored_symbols"], ["002594.SZ"])
        self.assertEqual(payload_safe["maximum_window_days"], 90)
        self.assertEqual(payload_safe["required_datasets"], ["factor_values", "daily", "daily_basic", "trade_cal"])
        self.assertEqual(receipt["status"], "provider_small_pool_dry_run_blocked_preflight")
        self.assertIn("window_scope_bounded", receipt["blocking_criteria"])


if __name__ == "__main__":
    unittest.main()
