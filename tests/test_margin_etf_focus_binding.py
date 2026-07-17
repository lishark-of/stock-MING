import datetime as dt
import json
import unittest
from unittest.mock import patch

import command_center_home_snapshot as snapshot


class MarginEtfFocusBindingTests(unittest.TestCase):
    def _packets(self, date_text="20260717"):
        etf = {
            "status": "ready",
            "data_status": "ready",
            "data_date": date_text,
            "recommended_cash_ratio": 22,
            "current_margin_ratio": 9,
            "recommended_margin_ratio": 10,
            "allow_new_margin": False,
            "available_cash": 128000,
            "recommended_etfs": [
                {"code": "510300.SH", "name": "沪深 300 ETF", "reason": "宽基研究样本"},
            ],
        }
        margin = {
            "status": "ready",
            "data_status": "ready",
            "trade_date": date_text,
            "verification_status": "已验证",
            "financing_balance_yi": 12.3,
        }
        freshness = {
            "freshness_state": "fresh",
            "expected_trade_date": date_text,
            "expected_trade_date_calendar_validated": True,
        }
        return etf, margin, freshness

    def test_canonical_current_packets_receive_identical_reachable_binding(self):
        etf, margin, freshness = self._packets()

        bound_etf, bound_margin = snapshot._attach_margin_etf_focus_binding(etf, margin, freshness)

        etf_binding = bound_etf["margin_etf_focus_binding"]
        margin_binding = bound_margin["margin_etf_focus_binding"]
        self.assertEqual(etf_binding, margin_binding)
        self.assertEqual(etf_binding["data_date"], "20260717")
        self.assertEqual(etf_binding["expected_trade_date"], "20260717")
        self.assertTrue(etf_binding["same_margin_etf_packet_date_bound"])
        self.assertTrue(etf_binding["calendar_validated"])
        self.assertTrue(etf_binding["usable_for_risk_budget"])
        self.assertEqual(etf_binding["available_cash"], 128000)
        self.assertIsInstance(etf_binding["producer_run_id"], str)
        self.assertIsInstance(etf_binding["result_version"], str)
        self.assertTrue(etf_binding["result_version"].startswith("margin-etf:"))
        self.assertFalse(etf_binding["external_calls_triggered"])
        self.assertTrue(etf_binding["does_not_execute_trades"])
        json.dumps(bound_etf, ensure_ascii=False)

    def test_binding_truth_table_fails_closed(self):
        mutations = {
            "different_packet_dates": lambda e, m, f: m.update(trade_date="20260716"),
            "invalid_etf_date": lambda e, m, f: e.update(data_date="20260230"),
            "hyphenated_packet_date": lambda e, m, f: e.update(data_date="2026-07-17"),
            "numeric_packet_date": lambda e, m, f: e.update(data_date=20260717),
            "boolean_packet_date": lambda e, m, f: e.update(data_date=True),
            "calendar_not_validated": lambda e, m, f: f.update(expected_trade_date_calendar_validated=False),
            "calendar_string_true": lambda e, m, f: f.update(expected_trade_date_calendar_validated="true"),
            "numeric_expected_date": lambda e, m, f: f.update(expected_trade_date=20260717),
            "invalid_expected_date": lambda e, m, f: f.update(expected_trade_date="20261301"),
            "freshness_unknown": lambda e, m, f: f.update(freshness_state="unknown"),
            "margin_partial": lambda e, m, f: m.update(status="partial"),
            "margin_unverified": lambda e, m, f: m.update(verification_status="待验证"),
            "no_etf_candidates": lambda e, m, f: e.update(recommended_etfs=[]),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                etf, margin, freshness = self._packets()
                mutate(etf, margin, freshness)
                bound_etf, bound_margin = snapshot._attach_margin_etf_focus_binding(etf, margin, freshness)
                self.assertNotIn("margin_etf_focus_binding", bound_etf)
                self.assertNotIn("margin_etf_focus_binding", bound_margin)

    def test_updated_at_is_never_used_as_a_packet_data_date(self):
        etf, margin, freshness = self._packets()
        etf.pop("data_date")
        margin.pop("trade_date")
        etf["updated_at"] = "2026-07-17T10:00:00"
        margin["updated_at"] = "2026-07-17T10:00:01"

        bound_etf, bound_margin = snapshot._attach_margin_etf_focus_binding(etf, margin, freshness)

        self.assertNotIn("margin_etf_focus_binding", bound_etf)
        self.assertNotIn("margin_etf_focus_binding", bound_margin)

    def test_home_snapshot_produces_binding_without_provider_or_model_calls(self):
        today = dt.date.today()
        iso = today.isoformat()
        compact = today.strftime("%Y%m%d")
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "只观察",
                "updated_at": f"{iso}T10:00:00",
            },
            "command_center_etf_packet": {
                "status": "ready",
                "data_status": "ready",
                "data_date": compact,
                "recommended_cash_ratio": 22,
                "current_margin_ratio": 9,
                "recommended_margin_ratio": 10,
                "allow_new_margin": False,
                "recommended_etfs": [
                    {"code": "510300.SH", "name": "沪深 300 ETF", "state": "观察"},
                ],
            },
            "command_center_margin_packet": {
                "status": "ready",
                "data_status": "ready",
                "trade_date": compact,
                "financing_balance_yi": 12.3,
            },
        }
        expected = {
            "expected_data_date": iso,
            "expected_data_date_source": "local_trade_calendar_cache",
            "expected_data_date_calendar_validated": True,
        }

        with patch("command_center_factor_research._expected_data_date", return_value=expected):
            payload = snapshot.build_home_action_snapshot(
                state,
                target="002008.SZ",
                now=f"{iso}T10:02:00",
            )

        self.assertEqual(
            payload["etf_packet"]["margin_etf_focus_binding"],
            payload["margin_packet"]["margin_etf_focus_binding"],
        )
        binding = payload["etf_packet"]["margin_etf_focus_binding"]
        self.assertEqual(binding["data_date"], compact)
        self.assertEqual(binding["expected_trade_date"], compact)
        self.assertTrue(binding["usable_for_risk_budget"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(binding["external_calls_triggered"])


if __name__ == "__main__":
    unittest.main()
