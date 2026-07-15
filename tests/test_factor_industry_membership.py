from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tushare_adapter
from server.services import factor_service
from server.services import task_service
from storage.sqlite_meta import SQLiteMetaStore


class FactorEffectiveDatedIndustryMembershipTests(unittest.TestCase):
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ", "600000.SH", "600001.SH"]
    horizons = ["1d", "5d", "20d"]

    def _memberships(self, *, industry: str | None = None):
        groups = ["bank", "bank", "technology", "technology", "technology"]
        return [
            {
                "ts_code": symbol,
                "in_date": "20240101",
                "out_date": "",
                "industry": industry or groups[index],
            }
            for index, symbol in enumerate(self.symbols)
        ]

    def _metric_rows(self):
        rows = []
        horizon_days = {"1d": 1, "5d": 5, "20d": 20}
        for date_index, signal_date in enumerate(("20250102", "20250103")):
            for horizon in self.horizons:
                for symbol_index, symbol in enumerate(self.symbols):
                    rows.append(
                        {
                            "ts_code": symbol,
                            "signal_date": signal_date,
                            "horizon": horizon,
                            "score": symbol_index + date_index * 0.1 + horizon_days[horizon] * 0.001,
                            "forward_return": (symbol_index - 2) * 0.01
                            + horizon_days[horizon] * 0.0001,
                        }
                    )
        return rows

    def _run(
        self,
        memberships=None,
        metric_rows=None,
        *,
        requested_horizons=None,
        source_contract="tushare_index_member_all.v1",
        interval_semantics="in_date_inclusive_out_date_exclusive",
    ):
        return factor_service._factor_test_effective_dated_industry_neutral_rank_ic(
            self._memberships() if memberships is None else memberships,
            self._metric_rows() if metric_rows is None else metric_rows,
            expected_symbols=self.symbols,
            requested_horizons=requested_horizons or self.horizons,
            source_contract=source_contract,
            interval_semantics=interval_semantics,
        )

    def test_success_computes_1d_5d_20d_pit_industry_neutral_rank_ic(self):
        result = self._run()

        self.assertEqual(
            result["schema_version"],
            "factor_test_effective_dated_industry_neutral_rank_ic.v1",
        )
        self.assertTrue(result["passed"])
        self.assertTrue(result["pit_interval_join_done"])
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["joined_assignment_count"], 30)
        self.assertEqual(result["source_contract"], "tushare_index_member_all.v1")
        self.assertEqual(
            result["interval_semantics"],
            "in_date_inclusive_out_date_exclusive",
        )
        self.assertEqual(result["interval_semantics_resolution"], "explicit_parameter")
        self.assertEqual(set(result["horizon_summaries"]), {"1d", "5d", "20d"})
        for horizon in self.horizons:
            summary = result["horizon_summaries"][horizon]
            self.assertEqual(summary["industry_neutral_period_count"], 2)
            self.assertIsNotNone(summary["industry_neutral_rank_ic_mean"])
            self.assertGreaterEqual(summary["industry_group_count_max"], 2)
            self.assertGreaterEqual(summary["industry_group_size_min"], 2)
        self.assertEqual(
            result["result_version_summary"]["classification_data_digest"],
            result["classification_data_digest"],
        )
        self.assertTrue(result["result_version_summary"]["classification_digest_bound"])
        self.assertFalse(result["uses_current_stock_basic_snapshot"])
        self.assertTrue(result["provider_independent"])
        self.assertTrue(result["small_pool_only"])
        self.assertFalse(result["full_market_validation_done"])
        self.assertFalse(result["production_factor_test_validation_complete"])
        self.assertFalse(result["external_calls_triggered"])

    def test_unknown_source_without_explicit_interval_semantics_fails_closed(self):
        result = self._run(
            source_contract="unreviewed_source.v1",
            interval_semantics="",
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["interval_semantics"], "")
        self.assertEqual(result["interval_semantics_resolution"], "unresolved_fail_closed")
        self.assertIn("interval_semantics_unresolved", result["blockers"])

    def test_index_member_source_without_independent_interval_semantics_fails_closed(self):
        result = self._run(interval_semantics="")

        self.assertFalse(result["passed"])
        self.assertEqual(result["interval_semantics"], "")
        self.assertEqual(result["interval_semantics_resolution"], "unresolved_fail_closed")
        self.assertIn("interval_semantics_unresolved", result["blockers"])

    def test_unsupported_explicit_interval_alias_reports_truthful_resolution(self):
        result = self._run(interval_semantics="inclusive_except_on_rebalance_day")

        self.assertFalse(result["passed"])
        self.assertEqual(result["interval_semantics"], "")
        self.assertEqual(
            result["interval_semantics_resolution"],
            "unsupported_explicit_fail_closed",
        )
        self.assertIn("interval_semantics_unresolved", result["blockers"])

    def test_missing_in_date_with_valid_out_date_is_invalid_not_type_error(self):
        memberships = self._memberships()
        memberships[0].pop("in_date")
        memberships[0]["out_date"] = "20251231"

        result = self._run(memberships=memberships)

        self.assertFalse(result["passed"])
        self.assertEqual(result["invalid_membership_row_count"], 1)
        self.assertIn("invalid_membership_rows", result["blockers"])

    def test_closed_open_same_day_membership_switch_uses_new_industry_without_overlap(self):
        memberships = self._memberships()
        by_symbol = {row["ts_code"]: row for row in memberships}
        by_symbol[self.symbols[0]]["out_date"] = "20250103"
        by_symbol[self.symbols[2]]["out_date"] = "20250103"
        memberships.extend(
            [
                {
                    "ts_code": self.symbols[0],
                    "in_date": "20250103",
                    "out_date": "",
                    "industry": "technology",
                },
                {
                    "ts_code": self.symbols[2],
                    "in_date": "20250103",
                    "out_date": "",
                    "industry": "bank",
                },
            ]
        )

        result = self._run(memberships=memberships)

        self.assertTrue(result["passed"])
        self.assertEqual(result["overlap_interval_count"], 0)
        self.assertEqual(result["overlap_assignment_count"], 0)
        self.assertEqual(result["gap_assignment_count"], 0)

        inclusive = self._run(
            memberships=memberships,
            interval_semantics="in_date_inclusive_out_date_inclusive",
        )
        self.assertFalse(inclusive["passed"])
        self.assertGreater(inclusive["overlap_interval_count"], 0)
        self.assertGreater(inclusive["overlap_assignment_count"], 0)

    def test_duplicate_metric_observation_and_non_exact_period_fail_closed(self):
        rows = self._metric_rows()
        rows.append({**rows[0], "score": 999.0, "forward_return": -0.99})

        result = self._run(metric_rows=rows)

        self.assertFalse(result["passed"])
        self.assertEqual(result["duplicate_metric_row_count"], 1)
        self.assertGreater(result["metric_observation_count_mismatch_period_count"], 0)
        self.assertIn("duplicate_metric_observations", result["blockers"])
        self.assertIn(
            "metric_observation_count_must_equal_expected_five",
            result["blockers"],
        )

    def test_duplicate_metric_hash_is_stable_when_failed_rows_are_reordered(self):
        rows = self._metric_rows()
        rows.append({**rows[0], "score": 999.0, "forward_return": -0.99})

        first = self._run(metric_rows=rows)
        reordered = self._run(metric_rows=list(reversed(rows)))

        self.assertFalse(first["passed"])
        self.assertFalse(reordered["passed"])
        self.assertEqual(first["duplicate_metric_row_count"], 1)
        self.assertEqual(first["metric_data_digest"], reordered["metric_data_digest"])
        self.assertEqual(first["result_version_hash"], reordered["result_version_hash"])

    def test_sub_twelve_decimal_score_swap_changes_hash_and_rank_ic_output(self):
        first_rows = self._metric_rows()
        target_rows = [
            row
            for row in first_rows
            if row["signal_date"] == "20250102"
            and row["horizon"] == "1d"
            and row["ts_code"] in self.symbols[:2]
        ]
        self.assertEqual(len(target_rows), 2)
        low = 1.00000000000005
        high = 1.00000000000045
        self.assertEqual(round(low, 12), round(high, 12))
        target_rows[0]["score"] = low
        target_rows[1]["score"] = high
        second_rows = [dict(row) for row in first_rows]
        second_by_symbol = {
            row["ts_code"]: row
            for row in second_rows
            if row["signal_date"] == "20250102"
            and row["horizon"] == "1d"
            and row["ts_code"] in self.symbols[:2]
        }
        second_by_symbol[self.symbols[0]]["score"] = high
        second_by_symbol[self.symbols[1]]["score"] = low

        first = self._run(metric_rows=first_rows)
        second = self._run(metric_rows=second_rows)

        self.assertTrue(first["passed"])
        self.assertTrue(second["passed"])
        self.assertNotEqual(first["metric_data_digest"], second["metric_data_digest"])
        self.assertNotEqual(first["result_version_hash"], second["result_version_hash"])
        self.assertNotEqual(
            first["horizon_summaries"]["1d"]["industry_neutral_rank_ic_mean"],
            second["horizon_summaries"]["1d"]["industry_neutral_rank_ic_mean"],
        )

    def test_singleton_industry_group_fails_sample_sufficiency(self):
        memberships = self._memberships()
        memberships[-1]["industry"] = "insurance"

        result = self._run(memberships=memberships)

        self.assertFalse(result["passed"])
        self.assertEqual(result["minimum_industry_group_observations_required"], 2)
        self.assertGreater(result["undersized_industry_group_period_count"], 0)
        self.assertEqual(result["industry_group_size_min_observed"], 1)
        self.assertIn("industry_group_sample_too_small", result["blockers"])

    def test_classification_columns_present_are_observed_not_assumed(self):
        memberships = self._memberships()
        for row in memberships:
            row.pop("out_date")

        result = self._run(memberships=memberships)

        self.assertTrue(result["passed"])
        self.assertIn("in_date", result["classification_columns_present"])
        self.assertIn("industry", result["classification_columns_present"])
        self.assertNotIn("out_date", result["classification_columns_present"])

    def test_gap_fails_closed_at_signal_date(self):
        memberships = self._memberships()
        memberships[0]["out_date"] = "20250102"

        result = self._run(memberships=memberships)

        self.assertFalse(result["passed"])
        self.assertGreater(result["gap_assignment_count"], 0)
        self.assertIn("membership_gap_at_signal_date", result["blockers"])
        self.assertFalse(result["pit_interval_join_done"])

    def test_overlap_and_future_effective_rows_fail_closed(self):
        with self.subTest("overlap"):
            memberships = self._memberships()
            memberships[0]["out_date"] = "20251231"
            memberships.append(
                {
                    "ts_code": self.symbols[0],
                    "in_date": "20250101",
                    "out_date": "",
                    "industry": "financial_services",
                }
            )
            result = self._run(memberships=memberships)
            self.assertFalse(result["passed"])
            self.assertGreater(result["overlap_interval_count"], 0)
            self.assertGreater(result["overlap_assignment_count"], 0)
            self.assertIn("overlapping_membership_intervals", result["blockers"])

        with self.subTest("future"):
            memberships = self._memberships()
            memberships[0]["in_date"] = "20250104"
            result = self._run(memberships=memberships)
            self.assertFalse(result["passed"])
            self.assertGreater(result["future_effective_assignment_count"], 0)
            self.assertIn("future_effective_membership_at_signal_date", result["blockers"])

    def test_single_industry_and_unknown_fail_closed(self):
        with self.subTest("single industry"):
            result = self._run(memberships=self._memberships(industry="one-industry"))
            self.assertFalse(result["passed"])
            self.assertGreater(result["single_industry_period_count"], 0)
            self.assertIn("fewer_than_two_industries_by_period", result["blockers"])

        with self.subTest("unknown"):
            memberships = self._memberships()
            memberships[0]["industry"] = "unknown"
            result = self._run(memberships=memberships)
            self.assertFalse(result["passed"])
            self.assertEqual(result["unknown_industry_row_count"], 1)
            self.assertIn("unknown_industry_membership", result["blockers"])

    def test_classification_digest_and_result_version_are_order_stable(self):
        memberships = self._memberships()
        first = self._run(memberships=memberships)
        reordered = self._run(memberships=list(reversed(memberships)))
        reordered_horizons = self._run(requested_horizons=["20d", "1d", "5d"])

        self.assertEqual(first["classification_data_digest"], reordered["classification_data_digest"])
        self.assertEqual(first["result_version_hash"], reordered["result_version_hash"])
        self.assertEqual(first["result_version_hash"], reordered_horizons["result_version_hash"])
        self.assertEqual(reordered_horizons["requested_horizons"], ["1d", "5d", "20d"])

        changed = self._memberships()
        changed[0]["industry"] = "insurance"
        changed_result = self._run(memberships=changed)
        self.assertNotEqual(first["classification_data_digest"], changed_result["classification_data_digest"])
        self.assertNotEqual(first["result_version_hash"], changed_result["result_version_hash"])


class FactorIndustryMembershipProviderPreflightTests(unittest.TestCase):
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ", "600000.SH", "600001.SH"]
    source_scope_hash = "a" * 64

    def _factor_tests(self):
        return {
            "provider_small_pool_acceptance_receipt": {
                "acceptance_scope_hash": self.source_scope_hash,
                "acceptance_scope_hash_short": self.source_scope_hash[:16],
                "start_date": "20250101",
                "end_date": "20250331",
                "symbols_with_core_rows": list(self.symbols),
                "sample_rows_collected": True,
                "provider_call_ledger_evidence_done": True,
                "external_calls_triggered": True,
                "tushare_called": True,
                "provider_execution_implemented": True,
                "provider_backed_small_pool_validation_done": True,
                "fixture_provider_authorized": False,
            }
        }

    def _live_source_packet(self, *, mode: str = ""):
        ledger = []
        for index, api in enumerate(("daily", "daily_basic")):
            ledger.append(
                {
                    "api": api,
                    "call_status": "success",
                    "row_count": 59,
                    "external": True,
                    "external_calls_triggered": True,
                    "tushare_called": True,
                    "provider_transport_verified": True,
                    "runtime_adapter_module_identity_verified": True,
                    "provider_transport_call_count": 1,
                    "provider_transport_receipt_count": 1,
                    "provider_transport_receipt_digest": f"{index + 1:064x}",
                    "request_params_safe": {
                        "ts_code": self.symbols[0],
                        "start_date": "20250101",
                        "end_date": "20250331",
                    },
                }
            )
        packet = {
            "schema_version": factor_service.FACTOR_TEST_PROVIDER_SMALL_POOL_LIVE_PACKET_SCHEMA_VERSION,
            "status": "success",
            "packet_key": factor_service.FACTOR_TEST_PROVIDER_SMALL_POOL_PACKET_KEY,
            "task_type": factor_service.FACTOR_TEST_PROVIDER_SMALL_POOL_LIVE_PACKET_TASK_TYPE,
            "call_count": 2,
            "success_count": 2,
            "failed_count": 0,
            "blocked_count": 0,
            "call_ledger": ledger,
            "external_calls_triggered": True,
            "tushare_called": True,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
        if mode:
            packet["provider_execution_mode"] = mode
        return packet

    @staticmethod
    def _credential_present():
        return {
            "schema_version": "factor_test_provider_small_pool_credential_presence.v1",
            "status": "credential_present",
            "server_side_tushare_credential_present": True,
            "credential_value_exposed": False,
            "env_key_name_exposed": False,
        }

    def _preflight(self, payload, now):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            with patch.object(factor_service, "SQLITE_META_PATH", meta_path), patch.object(
                factor_service,
                "_factor_test_credential_presence",
                side_effect=self._credential_present,
            ):
                return factor_service._factor_test_provider_industry_membership_preflight(
                    payload, self._factor_tests(), now
                )

    def _authorized_preflight(self):
        first = self._preflight({}, "2026-07-15T10:00:00")
        payload = {
            "approved_by_user": True,
            "authorize_live_provider_call": True,
            "provider_run_approved_by_user": True,
            "acceptance_scope_hash": self.source_scope_hash,
            "industry_scope_hash": first["industry_scope_hash"],
        }
        return self._preflight(payload, "2026-07-15T10:00:01")

    def _execute_injected(self, mode: str):
        receipt = self._authorized_preflight()

        class FakeAdapter:
            def __init__(self):
                self.calls = []

            def get_index_member_all(inner_self, **params):
                inner_self.calls.append(dict(params))
                if mode == "permission":
                    return {"ok": False, "data": None, "error": "permission denied"}
                if mode == "no_data":
                    return {"ok": True, "data": [], "error": None}
                if mode == "partial" and len(inner_self.calls) > 1:
                    return {"ok": True, "data": [], "error": None}
                row = {
                    "l1_code": "801780.SI",
                    "l1_name": "银行",
                    "l2_code": "801782.SI",
                    "l2_name": "国有大型银行Ⅱ",
                    "l3_code": "851911.SI",
                    "l3_name": "国有大型银行Ⅲ",
                    "ts_code": params["ts_code"],
                    "name": "sample",
                    "in_date": "20210101" if params["is_new"] == "Y" else "20150101",
                    "out_date": "" if params["is_new"] == "Y" else "20210101",
                    "is_new": params["is_new"],
                }
                return {
                    "ok": True,
                    "data": [row, dict(row)] if mode == "duplicate" else [row],
                    "error": None,
                }

        adapter = FakeAdapter()
        executed, rows, ledger = (
            factor_service._factor_test_provider_industry_membership_execute(
                receipt,
                "2026-07-15T10:00:03",
                task_id="local-test",
                adapter=adapter,
            )
        )
        return executed, rows, ledger, adapter

    def _authoritative_artifacts(self, task_id: str, marker: str):
        executed, rows, ledger, _ = self._execute_injected("success")
        scope_hash = executed["industry_scope_hash"]
        for row in rows:
            row["name"] = marker
            row["provider_raw_fields"]["name"] = marker
        for index, item in enumerate(ledger):
            item.update(
                {
                    "task_id": task_id,
                    "scope_hash": scope_hash,
                    "call_status": "success",
                    "provider_transport_verified": True,
                    "official_client_identity_verified": True,
                    "provider_transport_call_count": 1,
                    "provider_transport_receipt_count": 1,
                    "provider_transport_receipt_digest": f"{index + 1:064x}",
                    "provider_source_row_count": 1,
                    "provider_stored_row_count": 1,
                    "provider_row_overflow": False,
                    "provider_non_mapping_row_count": 0,
                    "provider_declared_actual_row_count_mismatch": False,
                    "external": True,
                    "external_calls_triggered": True,
                    "tushare_called": True,
                }
            )
        executed.update(
            {
                "task_id": task_id,
                "provider_call_ledger_evidence_done": True,
                "provider_industry_membership_raw_rows_collected": True,
                "provider_transport_complete": True,
                "provider_duplicate_raw_row_count": 0,
                "provider_raw_row_count": len(rows),
                "provider_original_raw_row_count": len(rows),
                "provider_unique_raw_row_count": len(rows),
                "provider_call_count": len(ledger),
                "provider_success_call_count": len(ledger),
                "provider_empty_call_count": 0,
                "provider_failed_call_count": 0,
                "provider_transport_verified_call_count": len(ledger),
                "provider_raw_rows_digest": factor_service._factor_test_industry_evidence_digest(rows),
                "provider_call_ledger_digest": factor_service._factor_test_industry_evidence_digest(ledger),
                "provider_transport_receipt_set_digest": factor_service._factor_test_industry_evidence_digest(
                    [item["provider_transport_receipt_digest"] for item in ledger]
                ),
            }
        )
        return executed, rows, ledger

    def _seed_authoritative_source_packet(self, meta_path: Path):
        store = SQLiteMetaStore(meta_path)
        store.write_packet(
            "command_center_factor_quant_hub_packet",
            {"factor_tests": self._factor_tests()},
        )
        store.write_packet(
            factor_service.FACTOR_TEST_PROVIDER_SMALL_POOL_PACKET_KEY,
            self._live_source_packet(),
        )

    def _run_controlled_live(self, meta_path: Path, task_id: str, marker: str, *, fail=False):
        receipt = self._authorized_preflight()

        class FakePro:
            def index_member_all(_self, **params):
                if fail:
                    raise RuntimeError("permission denied test fixture")
                return tushare_adapter.pd.DataFrame(
                    [
                        {
                            "l1_code": "801780.SI",
                            "l1_name": "银行",
                            "l2_code": "801782.SI",
                            "l2_name": "国有大型银行Ⅱ",
                            "l3_code": "851911.SI",
                            "l3_name": "国有大型银行Ⅲ",
                            "ts_code": params["ts_code"],
                            "name": marker,
                            "in_date": "20210101" if params["is_new"] == "Y" else "20150101",
                            "out_date": "" if params["is_new"] == "Y" else "20210101",
                            "is_new": params["is_new"],
                        }
                    ]
                )

        with patch.object(tushare_adapter, "_get_pro_client", return_value=(FakePro(), None)):
            return factor_service._run_factor_test_provider_industry_membership_live_and_persist(
                receipt,
                "2026-07-15T10:30:00",
                task_id=task_id,
                meta_path=meta_path,
            )

    def test_adapter_calls_only_documented_index_member_all_parameters(self):
        with patch.object(tushare_adapter, "_call_pro", return_value={"ok": True}) as call:
            result = tushare_adapter.get_index_member_all(
                l1_code=" 801010.si ",
                l2_code="801012.si",
                l3_code="850111.si",
                ts_code="600000.ss",
                is_new="n",
            )

        self.assertTrue(result["ok"])
        call.assert_called_once_with(
            "index_member_all",
            l1_code="801010.SI",
            l2_code="801012.SI",
            l3_code="850111.SI",
            ts_code="600000.SH",
            is_new="N",
        )

    def test_preflight_is_scope_bound_and_does_not_resolve_out_date_semantics(self):
        receipt = self._preflight({}, "2026-07-15T10:00:00")

        self.assertTrue(receipt["preflight_ready"])
        self.assertFalse(receipt["execution_authorized"])
        self.assertEqual(receipt["expected_provider_call_count"], 10)
        self.assertEqual(receipt["maximum_provider_call_count"], 10)
        self.assertEqual(receipt["provider_api"], "index_member_all")
        self.assertEqual(
            receipt["source_out_date_endpoint_semantics"],
            "provider_documentation_unspecified",
        )
        self.assertTrue(receipt["pit_promotion_fail_closed"])
        self.assertFalse(receipt["pit_eligible_membership_rows_written"])
        self.assertFalse(receipt["external_calls_triggered"])
        self.assertFalse(receipt["tushare_called"])

    def test_missing_or_fixture_live_source_packet_blocks_without_creating_trust(self):
        for mode in ("missing", "fake_provider_fixture"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                meta_path = Path(tmp) / "meta.sqlite"
                store = SQLiteMetaStore(meta_path)
                store.write_packet(
                    "command_center_factor_quant_hub_packet",
                    {"factor_tests": self._factor_tests()},
                )
                if mode != "missing":
                    store.write_packet(
                        factor_service.FACTOR_TEST_PROVIDER_SMALL_POOL_PACKET_KEY,
                        self._live_source_packet(mode=mode),
                    )
                with patch.object(
                    factor_service, "SQLITE_META_PATH", meta_path
                ), patch.object(
                    factor_service,
                    "_factor_test_credential_presence",
                    side_effect=self._credential_present,
                ):
                    receipt = factor_service._factor_test_provider_industry_membership_preflight(
                        {}, self._factor_tests(), "2026-07-15T10:00:00"
                    )
                self.assertFalse(receipt["preflight_ready"])
                self.assertFalse(receipt["execution_authorized"])
                self.assertTrue(
                    any(
                        blocker.startswith("source_live_small_pool_")
                        for blocker in receipt["authorization_blockers"]
                    )
                )
                trust_directory, _key, _state = (
                    factor_service._factor_test_industry_trust_paths(meta_path)
                )
                self.assertFalse(trust_directory.exists())

    def test_exact_double_scope_and_three_flags_authorize_execution(self):
        receipt = self._authorized_preflight()

        self.assertTrue(receipt["execution_authorized"])
        self.assertEqual(receipt["authorization_blockers"], [])
        self.assertTrue(receipt["requested_source_acceptance_scope_hash_matches"])
        self.assertTrue(receipt["requested_industry_scope_hash_matches"])

        bad = self._preflight(
            {
                "approved_by_user": True,
                "authorize_live_provider_call": True,
                "provider_run_approved_by_user": True,
                "acceptance_scope_hash": self.source_scope_hash,
                "industry_scope_hash": "b" * 64,
            },
            "2026-07-15T10:00:02",
        )
        self.assertFalse(bad["execution_authorized"])
        self.assertIn("industry_scope_hash_missing_or_mismatch", bad["authorization_blockers"])

    def test_injected_executor_preflights_exact_ten_calls_but_is_not_provider_evidence(self):
        receipt = self._authorized_preflight()

        class FakeAdapter:
            def __init__(self):
                self.calls = []

            def get_index_member_all(self, **params):
                self.calls.append(dict(params))
                symbol = params["ts_code"]
                is_new = params["is_new"]
                return {
                    "ok": True,
                    "data": [
                        {
                            "l1_code": "801780.SI",
                            "l1_name": "银行",
                            "l2_code": "801782.SI",
                            "l2_name": "国有大型银行Ⅱ",
                            "l3_code": "851911.SI",
                            "l3_name": "国有大型银行Ⅲ",
                            "ts_code": symbol,
                            "name": "sample",
                            "in_date": "20210101" if is_new == "Y" else "20150101",
                            "out_date": "" if is_new == "Y" else "20210101",
                            "is_new": is_new,
                        }
                    ],
                    "error": None,
                }

        adapter = FakeAdapter()
        executed, rows, ledger = (
            factor_service._factor_test_provider_industry_membership_execute(
                receipt,
                "2026-07-15T10:00:03",
                task_id="local-test",
                adapter=adapter,
            )
        )

        self.assertEqual(len(adapter.calls), 10)
        self.assertEqual(
            adapter.calls,
            [
                {"ts_code": symbol, "is_new": is_new}
                for symbol in sorted(self.symbols)
                for is_new in ("Y", "N")
            ],
        )
        self.assertEqual(len(ledger), 10)
        self.assertEqual(len(rows), 10)
        self.assertTrue(executed["provider_symbol_coverage_complete"])
        self.assertFalse(executed["provider_call_ledger_evidence_done"])
        self.assertFalse(executed["provider_backed_pit_industry_membership_done"])
        self.assertTrue(executed["pit_promotion_fail_closed"])
        self.assertTrue(all(row["pit_eligible"] is False for row in rows))
        self.assertTrue(all(row["external_calls_triggered"] is False for row in ledger))
        self.assertTrue(all(row["tushare_called"] is False for row in ledger))

    def test_injected_permission_no_data_and_partial_fail_closed(self):
        for mode, expected_status in (
            ("permission", "degraded_permission_denied"),
            ("no_data", "degraded_no_data"),
            ("partial", "degraded_partial_result"),
        ):
            with self.subTest(mode=mode):
                executed, _rows, ledger, _adapter = self._execute_injected(mode)
                self.assertIn(expected_status, executed["status"])
                self.assertFalse(executed["provider_call_ledger_evidence_done"])
                self.assertFalse(executed["provider_industry_membership_raw_rows_collected"])
                self.assertTrue(all(row["tushare_called"] is False for row in ledger))
        permission, _rows, _ledger, _adapter = self._execute_injected("permission")
        self.assertIn("permission_denied", permission["provider_failure_modes"])
        no_data, _rows, _ledger, _adapter = self._execute_injected("no_data")
        self.assertEqual(no_data["provider_empty_call_count"], 10)
        partial, _rows, _ledger, _adapter = self._execute_injected("partial")
        self.assertTrue(partial["provider_partial_result_detected"])

    def test_duplicate_raw_rows_are_preserved_and_block_authoritative_evidence(self):
        executed, rows, ledger, _adapter = self._execute_injected("duplicate")

        self.assertEqual(len(rows), 20)
        self.assertEqual(executed["provider_original_raw_row_count"], 20)
        self.assertEqual(executed["provider_unique_raw_row_count"], 10)
        self.assertEqual(executed["provider_duplicate_raw_row_count"], 10)
        self.assertIn("duplicate_provider_raw_rows", executed["evidence_blockers"])
        self.assertFalse(executed["provider_call_ledger_evidence_done"])
        self.assertEqual(rows[0]["provider_raw_fields"], rows[1]["provider_raw_fields"])
        self.assertNotEqual(rows[0]["provider_row_ordinal"], rows[1]["provider_row_ordinal"])
        self.assertTrue(all(row["tushare_called"] is False for row in ledger))

    def test_provider_specific_extractor_keeps_201_and_2000_and_blocks_2001(self):
        for count in (201, 2000):
            extracted = factor_service._factor_test_provider_industry_membership_rows(
                [{"ordinal": index} for index in range(count)]
            )
            self.assertEqual(extracted["provider_source_row_count"], count)
            self.assertEqual(extracted["provider_stored_row_count"], count)
            self.assertEqual(len(extracted["rows"]), count)
            self.assertFalse(extracted["provider_row_overflow"])

        overflow = factor_service._factor_test_provider_industry_membership_rows(
            [{"ordinal": index} for index in range(2001)]
        )
        self.assertEqual(overflow["provider_source_row_count"], 2001)
        self.assertEqual(overflow["provider_stored_row_count"], 2000)
        self.assertEqual(len(overflow["rows"]), 2000)
        self.assertTrue(overflow["provider_row_overflow"])

        mismatch = factor_service._factor_test_provider_industry_membership_rows(
            {"row_count": 2, "rows": [{"ordinal": 0}]}
        )
        self.assertTrue(mismatch["provider_declared_actual_row_count_mismatch"])

        receipt = self._authorized_preflight()

        class OverflowAdapter:
            calls = 0

            def get_index_member_all(inner_self, **params):
                inner_self.calls += 1
                count = 2001 if inner_self.calls == 1 else 1
                return {
                    "ok": True,
                    "data": [
                        {
                            "l1_code": "801780.SI",
                            "l1_name": "银行",
                            "l2_code": "801782.SI",
                            "l2_name": "国有大型银行Ⅱ",
                            "l3_code": f"85{index:04d}.SI",
                            "l3_name": f"行业{index}",
                            "ts_code": params["ts_code"],
                            "name": "sample",
                            "in_date": f"{20200101 + index}",
                            "out_date": "",
                            "is_new": params["is_new"],
                        }
                        for index in range(count)
                    ],
                    "error": None,
                }

        executed, rows, ledger = factor_service._factor_test_provider_industry_membership_execute(
            receipt,
            "2026-07-15T10:20:00",
            task_id="overflow-test",
            adapter=OverflowAdapter(),
        )
        self.assertEqual(len(rows), 2009)
        self.assertEqual(ledger[0]["provider_source_row_count"], 2001)
        self.assertEqual(ledger[0]["provider_stored_row_count"], 2000)
        self.assertTrue(ledger[0]["provider_row_overflow"])
        self.assertIn(
            "provider_row_count_exceeds_official_2000_limit",
            executed["schema_blockers"],
        )
        self.assertFalse(executed["provider_call_ledger_evidence_done"])

    def test_direct_caller_cannot_self_seal_forged_provider_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            forged = self._authoritative_artifacts("forged-no-real-provider", "forged")
            with self.assertRaisesRegex(
                RuntimeError,
                "trust_key_missing|trusted_secret_missing_or_mismatch",
            ):
                factor_service._persist_factor_test_provider_industry_membership_event(
                    *forged,
                    meta_path=meta_path,
                )
            state = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertFalse(state["current_valid"])
            self.assertFalse(state["last_good_valid"])

    def test_fake_production_client_never_creates_trust_or_promotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            executed, _rows, ledger, persisted = self._run_controlled_live(
                meta_path,
                "fake-pro-task",
                "fake",
            )
            trust_directory, _key_path, _state_path = (
                factor_service._factor_test_industry_trust_paths(meta_path)
            )
            self.assertFalse(trust_directory.exists())
            self.assertFalse(persisted["authoritative_current_promoted"])
            self.assertFalse(executed["provider_call_ledger_evidence_done"])
            self.assertIn(
                "authority_runtime_transport_semantics_invalid",
                executed["authority_validation_blockers"],
            )
            self.assertTrue(
                all(row["official_client_identity_verified"] is False for row in ledger)
            )
            state = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertFalse(state["current_valid"])

    def test_direct_sqlite_event_injection_is_not_authoritative(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            forged = factor_service._factor_test_provider_industry_membership_event(
                *self._authoritative_artifacts("sqlite-forged", "forged")
            )
            store = SQLiteMetaStore(meta_path)
            store.write_packet(
                f"{factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_EVENT_PACKET_PREFIX}{forged['event_digest']}",
                forged,
            )
            store.write_packet(
                factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_CURRENT_PACKET_KEY,
                forged,
            )
            store.write_packet(
                factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_LAST_GOOD_PACKET_KEY,
                forged,
            )

            state = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertFalse(state["current_valid"])
            self.assertFalse(state["last_good_valid"])

    def test_one_row_plus_ten_forged_success_ledgers_fails_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            receipt, rows, ledger = self._authoritative_artifacts(
                "one-row-forged",
                "forged",
            )
            rows = rows[:1]
            for index, item in enumerate(ledger):
                item["row_count"] = 1 if index == 0 else 0
                item["provider_source_row_count"] = 1 if index == 0 else 0
                item["provider_stored_row_count"] = 1 if index == 0 else 0
            receipt.update(
                {
                    "provider_raw_row_count": 1,
                    "provider_original_raw_row_count": 1,
                    "provider_unique_raw_row_count": 1,
                    "provider_raw_rows_digest": factor_service._factor_test_industry_evidence_digest(rows),
                    "provider_call_ledger_digest": factor_service._factor_test_industry_evidence_digest(ledger),
                    "provider_transport_receipt_set_digest": factor_service._factor_test_industry_evidence_digest(
                        [item["provider_transport_receipt_digest"] for item in ledger]
                    ),
                }
            )
            blockers = factor_service._factor_test_provider_industry_membership_authority_blockers(
                receipt,
                rows,
                ledger,
                meta_path=meta_path,
            )
            self.assertIn(
                "authority_each_exact_call_requires_non_empty_rows",
                blockers,
            )

    def test_authority_requires_all_three_literal_approvals(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            receipt, rows, ledger = self._authoritative_artifacts(
                "approval-forged",
                "forged",
            )
            receipt["scope_ticket"] = dict(receipt["scope_ticket"])
            receipt["scope_ticket"]["approved_by_user"] = 1
            blockers = factor_service._factor_test_provider_industry_membership_authority_blockers(
                receipt,
                rows,
                ledger,
                meta_path=meta_path,
            )
            self.assertIn(
                "authority_three_approvals_or_scope_confirmation_missing",
                blockers,
            )

    def test_factor_owned_current_last_good_and_failure_preservation_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            secret, blocker = factor_service._create_factor_test_industry_trusted_secret(
                meta_path
            )
            self.assertTrue(secret)
            self.assertEqual(blocker, "")
            trust_directory, key_path, _state_path = (
                factor_service._factor_test_industry_trust_paths(meta_path)
            )
            self.assertEqual(trust_directory.stat().st_mode & 0o777, 0o700)
            self.assertEqual(key_path.stat().st_mode & 0o777, 0o600)
            first = self._authoritative_artifacts("task-first", "first")
            first_write = factor_service._persist_factor_test_provider_industry_membership_event(
                *first,
                meta_path=meta_path,
                trusted_secret=secret,
            )
            self.assertTrue(first_write["authoritative_current_promoted"])
            _directory, _key_path, state_path = (
                factor_service._factor_test_industry_trust_paths(meta_path)
            )
            self.assertEqual(state_path.stat().st_mode & 0o777, 0o600)

            second = self._authoritative_artifacts("task-second", "second")
            second_write = factor_service._persist_factor_test_provider_industry_membership_event(
                *second,
                meta_path=meta_path,
                trusted_secret=secret,
            )
            self.assertTrue(second_write["authoritative_current_promoted"])

            failed_receipt, _failed_rows, _failed_ledger, failed_write = self._run_controlled_live(
                meta_path,
                "task-failed",
                "failed",
                fail=True,
            )
            self.assertFalse(failed_write["authoritative_current_promoted"])
            self.assertFalse(failed_receipt["provider_call_ledger_evidence_done"])

            restarted = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertTrue(restarted["current_valid"])
            self.assertTrue(restarted["last_good_valid"])
            self.assertEqual(restarted["current"]["task_id"], "task-second")
            self.assertEqual(restarted["last_good"]["task_id"], "task-first")
            self.assertNotEqual(
                restarted["current"]["event_digest"],
                restarted["last_good"]["event_digest"],
            )

    def test_deleting_early_authoritative_event_invalidates_full_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            secret, blocker = factor_service._create_factor_test_industry_trusted_secret(
                meta_path
            )
            self.assertTrue(secret)
            self.assertEqual(blocker, "")
            writes = []
            for index in range(1, 4):
                writes.append(
                    factor_service._persist_factor_test_provider_industry_membership_event(
                        *self._authoritative_artifacts(
                            f"chain-task-{index}", f"chain-{index}"
                        ),
                        meta_path=meta_path,
                        trusted_secret=secret,
                    )
                )
            before = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertTrue(before["current_valid"])
            with sqlite3.connect(meta_path) as connection:
                connection.execute(
                    "DELETE FROM packets WHERE packet_key = ?",
                    (writes[0]["event_packet_key"],),
                )
                connection.commit()
            after = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertFalse(after["current_valid"])
            self.assertFalse(after["last_good_valid"])
            self.assertIn(
                "full_chain_sequence_gap_truncation_or_rollback",
                after["current_blockers"],
            )

    def test_post_live_persistence_exception_preserves_actual_rows_and_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            secret, blocker = factor_service._create_factor_test_industry_trusted_secret(
                meta_path
            )
            self.assertTrue(secret)
            self.assertEqual(blocker, "")
            factor_service._persist_factor_test_provider_industry_membership_event(
                *self._authoritative_artifacts("before-persist-failure", "before"),
                meta_path=meta_path,
                trusted_secret=secret,
            )
            before = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            with patch.object(
                factor_service,
                "_persist_factor_test_provider_industry_membership_event",
                side_effect=RuntimeError("post-live persistence test failure"),
            ):
                executed, rows, ledger, persisted = self._run_controlled_live(
                    meta_path,
                    "post-live-persist-failure",
                    "actual",
                )
            self.assertEqual(len(ledger), 10)
            self.assertEqual(len(rows), 10)
            self.assertTrue(all(item["external_calls_triggered"] for item in ledger))
            self.assertTrue(all(item["tushare_called"] for item in ledger))
            self.assertTrue(executed["actual_provider_call_ledger_preserved"])
            self.assertTrue(executed["actual_provider_raw_rows_preserved"])
            self.assertFalse(persisted["authoritative_current_promoted"])
            self.assertEqual(
                executed["status"],
                "factor_test_provider_industry_membership_authority_or_persistence_failed_safe",
            )
            after = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertTrue(after["current_valid"])
            self.assertEqual(
                after["current"]["event_digest"], before["current"]["event_digest"]
            )

            update_calls = []

            def record_update(task_id, **kwargs):
                update_calls.append({"task_id": task_id, **kwargs})
                return {
                    "task_id": task_id,
                    "task_type": factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_TASK_TYPE,
                    "status": kwargs.get("status"),
                    "call_ledger": list(kwargs.get("call_ledger") or []),
                }

            payload = {
                "approved_by_user": True,
                "authorize_live_provider_call": True,
                "provider_run_approved_by_user": True,
                "acceptance_scope_hash": self.source_scope_hash,
                "industry_scope_hash": executed["industry_scope_hash"],
            }
            with patch.object(
                factor_service, "SQLITE_META_PATH", meta_path
            ), patch.object(
                factor_service,
                "read_factor_quant_cache",
                return_value={"factor_tests": self._factor_tests()},
            ), patch.object(
                factor_service,
                "_factor_test_credential_presence",
                side_effect=self._credential_present,
            ), patch.object(
                factor_service,
                "create_task_record",
                return_value={"task_id": "task-final-projection"},
            ), patch.object(
                factor_service,
                "update_task_status",
                side_effect=record_update,
            ), patch.object(
                factor_service,
                "_run_factor_test_provider_industry_membership_live_and_persist",
                return_value=(executed, rows, ledger, persisted),
            ):
                projected = factor_service.run_factor_test_provider_industry_membership_task(
                    payload
                )
            self.assertEqual(projected["status"], "failed")
            self.assertTrue(projected["payload_safe"]["external_calls_triggered"])
            self.assertTrue(projected["payload_safe"]["tushare_called"])
            self.assertEqual(len(update_calls[-1]["call_ledger"]), 10)
            self.assertTrue(
                all(
                    item["external_calls_triggered"]
                    for item in update_calls[-1]["call_ledger"]
                )
            )

    def test_trust_state_write_failure_rolls_back_current_last_good_and_new_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            secret, blocker = factor_service._create_factor_test_industry_trusted_secret(
                meta_path
            )
            self.assertTrue(secret)
            self.assertEqual(blocker, "")
            factor_service._persist_factor_test_provider_industry_membership_event(
                *self._authoritative_artifacts("rollback-first", "first"),
                meta_path=meta_path,
                trusted_secret=secret,
            )
            before = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            second = self._authoritative_artifacts("rollback-second", "second")
            second_digest = factor_service._factor_test_provider_industry_membership_event(
                *second
            )["event_digest"]
            with patch.object(
                factor_service,
                "_write_factor_test_industry_trusted_state",
                return_value="test_trust_state_write_failure",
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "test_trust_state_write_failure"
                ):
                    factor_service._persist_factor_test_provider_industry_membership_event(
                        *second,
                        meta_path=meta_path,
                        trusted_secret=secret,
                    )
            after = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertTrue(after["current_valid"])
            self.assertTrue(after["last_good_valid"])
            self.assertEqual(
                after["current"]["event_digest"], before["current"]["event_digest"]
            )
            self.assertEqual(
                after["last_good"]["event_digest"], before["last_good"]["event_digest"]
            )
            self.assertIsNone(
                SQLiteMetaStore(meta_path, read_only=True).read_packet(
                    f"{factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_EVENT_PACKET_PREFIX}{second_digest}"
                )
            )

    def test_trusted_terminal_state_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            secret, blocker = factor_service._create_factor_test_industry_trusted_secret(
                meta_path
            )
            self.assertTrue(secret)
            self.assertEqual(blocker, "")
            artifacts = self._authoritative_artifacts("state-tamper", "valid")
            factor_service._persist_factor_test_provider_industry_membership_event(
                *artifacts,
                meta_path=meta_path,
                trusted_secret=secret,
            )
            before = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertTrue(before["current_valid"])
            _directory, _key_path, state_path = factor_service._factor_test_industry_trust_paths(
                meta_path
            )
            state_path.write_text("{}", encoding="utf-8")
            state_path.chmod(0o600)
            after = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertFalse(after["current_valid"])
            self.assertFalse(after["last_good_valid"])

    def test_trusted_state_invalid_json_permissions_and_exact_types_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            secret, blocker = factor_service._create_factor_test_industry_trusted_secret(
                meta_path
            )
            self.assertTrue(secret)
            self.assertEqual(blocker, "")
            factor_service._persist_factor_test_provider_industry_membership_event(
                *self._authoritative_artifacts("state-types", "valid"),
                meta_path=meta_path,
                trusted_secret=secret,
            )
            _directory, _key_path, state_path = factor_service._factor_test_industry_trust_paths(
                meta_path
            )
            original = state_path.read_text(encoding="utf-8")
            original_state = json.loads(original)
            cases = {
                "invalid_json": "{not-json",
                "bool_as_int": json.dumps({**original_state, "sequence_no": True}),
                "string_as_int": json.dumps({**original_state, "sequence_no": "1"}),
                "list_as_int": json.dumps({**original_state, "sequence_no": []}),
                "object_as_int": json.dumps({**original_state, "sequence_no": {}}),
                "list_as_mac": json.dumps({**original_state, "event_mac": []}),
            }
            for label, content in cases.items():
                with self.subTest(label=label):
                    state_path.write_text(content, encoding="utf-8")
                    state_path.chmod(0o600)
                    state = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                        meta_path
                    )
                    self.assertFalse(state["current_valid"])
                    self.assertFalse(state["last_good_valid"])
                    self.assertTrue(state["current_blockers"])
                    state_path.write_text(original, encoding="utf-8")
                    state_path.chmod(0o600)
            state_path.chmod(0o644)
            permissions = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertFalse(permissions["current_valid"])
            self.assertIn(
                "industry_provider_trust_state_permissions_invalid",
                permissions["current_blockers"],
            )

    def test_current_and_event_invalid_json_and_exact_types_never_escape_reader(self):
        mutation_cases = {
            "raw_count_bool": ("raw_row_count", True),
            "raw_count_string": ("raw_row_count", "10"),
            "raw_count_list": ("raw_row_count", []),
            "raw_count_object": ("raw_row_count", {}),
            "sequence_bool": ("sequence_no", True),
            "sequence_list": ("sequence_no", []),
            "receipt_count_object": ("receipt.provider_raw_row_count", {}),
            "ledger_count_string": ("call_ledger.0.row_count", "1"),
        }
        for label, (field, value) in mutation_cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                meta_path = Path(tmp) / "meta.sqlite"
                self._seed_authoritative_source_packet(meta_path)
                secret, _ = factor_service._create_factor_test_industry_trusted_secret(meta_path)
                written = factor_service._persist_factor_test_provider_industry_membership_event(
                    *self._authoritative_artifacts(f"event-{label}", "valid"),
                    meta_path=meta_path,
                    trusted_secret=secret,
                )
                with sqlite3.connect(meta_path) as connection:
                    raw = connection.execute(
                        "SELECT payload_json FROM packets WHERE packet_key = ?",
                        (factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_CURRENT_PACKET_KEY,),
                    ).fetchone()[0]
                    current = json.loads(raw)
                    if field.startswith("receipt."):
                        current["receipt"][field.split(".", 1)[1]] = value
                    elif field.startswith("call_ledger.0."):
                        current["call_ledger"][0][field.rsplit(".", 1)[1]] = value
                    else:
                        current[field] = value
                    connection.execute(
                        "UPDATE packets SET payload_json = ? WHERE packet_key = ?",
                        (
                            json.dumps(current),
                            factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_CURRENT_PACKET_KEY,
                        ),
                    )
                    connection.commit()
                state = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                    meta_path
                )
                self.assertFalse(state["current_valid"])
                self.assertTrue(state["current_blockers"])
                self.assertEqual(written["raw_row_count"], 10)

        for packet_kind in ("current", "event"):
            with self.subTest(packet_kind=packet_kind), tempfile.TemporaryDirectory() as tmp:
                meta_path = Path(tmp) / "meta.sqlite"
                self._seed_authoritative_source_packet(meta_path)
                secret, _ = factor_service._create_factor_test_industry_trusted_secret(meta_path)
                written = factor_service._persist_factor_test_provider_industry_membership_event(
                    *self._authoritative_artifacts(f"json-{packet_kind}", "valid"),
                    meta_path=meta_path,
                    trusted_secret=secret,
                )
                packet_key = (
                    factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_CURRENT_PACKET_KEY
                    if packet_kind == "current"
                    else written["event_packet_key"]
                )
                with sqlite3.connect(meta_path) as connection:
                    connection.execute(
                        "UPDATE packets SET payload_json = ? WHERE packet_key = ?",
                        ("{invalid-json", packet_key),
                    )
                    connection.commit()
                state = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                    meta_path
                )
                self.assertFalse(state["current_valid"])
                self.assertFalse(state["last_good_valid"])
                self.assertTrue(state["current_blockers"])
                with patch.object(factor_service, "SQLITE_META_PATH", meta_path):
                    attached = factor_service._attach_factor_test_provider_industry_membership_authoritative_state(
                        {"factor_tests": {}}
                    )
                attached_state = attached["factor_tests"][
                    "provider_industry_membership_authoritative_state"
                ]
                self.assertFalse(attached_state["current_valid"])
                self.assertTrue(attached_state["current_blockers"])

    def test_factor_owned_final_projection_survives_task_restart_after_live_persist_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            self._seed_authoritative_source_packet(meta_path)
            secret, _ = factor_service._create_factor_test_industry_trusted_secret(meta_path)
            factor_service._persist_factor_test_provider_industry_membership_event(
                *self._authoritative_artifacts("projection-before", "before"),
                meta_path=meta_path,
                trusted_secret=secret,
            )
            before = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            with patch.object(
                factor_service,
                "_persist_factor_test_provider_industry_membership_event",
                side_effect=RuntimeError("post-live projection persistence failure"),
            ):
                executed, rows, ledger, persisted = self._run_controlled_live(
                    meta_path,
                    "projection-live-failed",
                    "actual",
                )
            payload = {
                "approved_by_user": True,
                "authorize_live_provider_call": True,
                "provider_run_approved_by_user": True,
                "acceptance_scope_hash": self.source_scope_hash,
                "industry_scope_hash": executed["industry_scope_hash"],
            }
            task_service._TASKS.clear()
            try:
                with patch.object(
                    factor_service, "SQLITE_META_PATH", meta_path
                ), patch.object(
                    task_service, "SQLITE_META_PATH", meta_path
                ), patch.object(
                    factor_service,
                    "read_factor_quant_cache",
                    return_value={"factor_tests": self._factor_tests()},
                ), patch.object(
                    factor_service,
                    "_factor_test_credential_presence",
                    side_effect=self._credential_present,
                ), patch.object(
                    factor_service,
                    "_run_factor_test_provider_industry_membership_live_and_persist",
                    return_value=(executed, rows, ledger, persisted),
                ):
                    projected = factor_service.run_factor_test_provider_industry_membership_task(
                        payload
                    )
                self.assertEqual(projected["status"], "failed")
                self.assertEqual(len(projected["payload_safe"]["provider_industry_membership_rows"]), 10)
                self.assertEqual(len(projected["call_ledger"]), 10)
                self.assertTrue(projected["external_calls_triggered"])
                self.assertTrue(projected["tushare_called"])
                task_id = projected["task_id"]
                task_service._TASKS.clear()
                with patch.object(task_service, "SQLITE_META_PATH", meta_path):
                    restarted = task_service.read_task_status(task_id)
                self.assertEqual(restarted["storage_source"], "sqlite_meta")
                self.assertEqual(len(restarted["payload_safe"]["provider_industry_membership_rows"]), 10)
                self.assertEqual(
                    len(restarted["payload_safe"]["provider_industry_membership_call_ledger"]),
                    10,
                )
                self.assertEqual(len(restarted["call_ledger"]), 10)
                self.assertTrue(restarted["external_calls_triggered"])
                self.assertTrue(restarted["tushare_called"])
                self.assertFalse(restarted["provider_evidence_authoritative"])
                after = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                    meta_path
                )
                self.assertTrue(after["current_valid"])
                self.assertEqual(
                    after["current"]["event_digest"], before["current"]["event_digest"]
                )
            finally:
                task_service._TASKS.clear()

    def test_authoritative_reader_is_zero_write_when_trust_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta_path = root / "meta.sqlite"
            before = list(root.iterdir())
            missing = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertFalse(missing["current_valid"])
            self.assertEqual(list(root.iterdir()), before)

            SQLiteMetaStore(meta_path)
            before_names = sorted(path.name for path in root.iterdir())
            before_mtime = meta_path.stat().st_mtime_ns
            no_trust = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertFalse(no_trust["current_valid"])
            self.assertEqual(sorted(path.name for path in root.iterdir()), before_names)
            self.assertEqual(meta_path.stat().st_mtime_ns, before_mtime)

    def test_generic_task_payload_forgery_cannot_create_authoritative_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.sqlite"
            store = SQLiteMetaStore(meta_path)
            store.write_task_status(
                {
                    "task_id": "forged-task",
                    "task_type": factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_TASK_TYPE,
                    "status": "success",
                    "payload_safe": {
                        "provider_industry_membership_receipt": {
                            "schema_version": "factor_test_provider_industry_membership_receipt.v1",
                            "provider_call_ledger_evidence_done": True,
                        },
                        "provider_industry_membership_rows": [{"ts_code": "600000.SH"}],
                    },
                }
            )

            state = factor_service._read_factor_test_provider_industry_membership_authoritative_state(
                meta_path
            )
            self.assertFalse(state["current_valid"])
            self.assertFalse(state["last_good_valid"])
            self.assertEqual(
                state["status"],
                "authoritative_provider_industry_membership_missing_or_invalid",
            )

    def test_task_lifecycle_keeps_payload_immutable_and_projects_external_flags(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            task_service,
            "SQLITE_META_PATH",
            Path(tmp) / "meta.sqlite",
        ):
            task = task_service.create_task_record(
                factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_TASK_TYPE,
                payload={"immutable_scope": "scope-a"},
            )
            updated = task_service.update_task_status(
                task["task_id"],
                status="success",
                progress=1.0,
                current_step="provider_evidence_recorded",
                call_ledger=[
                    {
                        "api": "index_member_all",
                        "external": True,
                        "external_calls_triggered": True,
                        "tushare_called": True,
                        "deepseek_called": False,
                        "github_called": False,
                        "does_not_execute_trades": True,
                        "does_not_modify_strategy_action": True,
                    }
                ],
            )

            self.assertEqual(updated["payload_safe"], {"immutable_scope": "scope-a"})
            self.assertTrue(updated["external_calls_triggered"])
            self.assertTrue(updated["tushare_called"])
            self.assertFalse(updated["deepseek_called"])
            self.assertTrue(updated["does_not_execute_trades"])
            with self.assertRaises(TypeError):
                task_service.update_task_status(
                    task["task_id"],
                    status="success",
                    payload_safe={"forged": True},
                )

    def test_task_catalog_registers_only_explicit_post_provider_path(self):
        catalog = task_service.build_task_catalog()
        by_type = {row["task_type"]: row for row in catalog["tasks"]}
        task = by_type[factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_TASK_TYPE]

        self.assertEqual(task["route"], factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_ROUTE)
        self.assertEqual(task["allowed_tushare_apis"], ["index_member_all"])
        self.assertEqual(task["expected_provider_call_count"], 10)
        self.assertTrue(task["pit_promotion_fail_closed"])
        self.assertFalse(task["cache_get_external_calls"])
        self.assertFalse(task["react_render_direct_provider_calls"])
        self.assertTrue(task["does_not_execute_trades"])


if __name__ == "__main__":
    unittest.main()
