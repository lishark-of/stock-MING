from __future__ import annotations

import unittest

from server.services import factor_service


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
        interval_semantics="",
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
        self.assertEqual(result["interval_semantics_resolution"], "source_contract_default")
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
        result = self._run(source_contract="unreviewed_source.v1")

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


if __name__ == "__main__":
    unittest.main()
