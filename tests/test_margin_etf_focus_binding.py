import datetime as dt
import json
import unittest
from unittest.mock import patch

import command_center_home_snapshot as snapshot


class MarginEtfFocusBindingTests(unittest.TestCase):
    IDENTITY = {
        "source_task_id": "margin-etf-task-20260717",
        "source_scope_hash": "a" * 64,
        "source_identity": "margin-etf-local-replay-20260717",
        "source_result_version": "margin-etf-source-v1",
        "target": "002008.SZ",
    }
    SAFE = {
        "external": False,
        "external_calls_triggered": False,
        "provider_or_model_calls": False,
        "provider_called": False,
        "model_called": False,
        "worker_called": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "trade_called": False,
        "trading_called": False,
        "broker_called": False,
        "order_called": False,
        "real_trading_enabled": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "warnings": [],
    }

    def _packets(self, date_text="20260717"):
        etf = {
            **self.IDENTITY,
            **self.SAFE,
            "status": "ready",
            "data_status": "ready",
            "data_date": date_text,
            "updated_at": "2026-07-17T10:00:00",
            "source": "融资 ETF 本地配置快照",
            "verification_status": "已验证",
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
            **self.IDENTITY,
            **self.SAFE,
            "status": "ready",
            "data_status": "ready",
            "trade_date": date_text,
            "updated_at": "2026-07-17T10:00:01",
            "source": "Tushare margin_detail 缓存",
            "verification_status": "已验证",
            "financing_balance_yi": 12.3,
            "financing_buy_yi": 1.2,
            "margin_balance_yi": 14.5,
        }
        freshness = {
            "freshness_state": "fresh",
            "expected_trade_date": date_text,
            "expected_trade_date_calendar_validated": True,
            "last_updated": "2026-07-17T10:02:00",
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
        self.assertEqual(etf_binding["schema_version"], "margin_etf_focus_binding.v2")
        self.assertEqual(etf_binding["producer"], "command_center_home_snapshot.margin_etf_focus_binding")
        self.assertEqual(etf_binding["projection"]["etf"]["available_cash"], 128000)
        self.assertEqual(etf_binding["projection"]["source_identity"]["task_id"], self.IDENTITY["source_task_id"])
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
            "etf_unverified": lambda e, m, f: e.update(verification_status="待验证"),
            "etf_warning": lambda e, m, f: e.update(warnings=["unsafe"]),
            "margin_warning": lambda e, m, f: m.update(warnings=["unsafe"]),
            "etf_external": lambda e, m, f: e.update(external_calls_triggered=True),
            "margin_provider": lambda e, m, f: m.update(provider_called=True),
            "trade_boundary_false": lambda e, m, f: e.update(does_not_execute_trades=False),
            "different_task": lambda e, m, f: m.update(source_task_id="other-task"),
            "different_scope": lambda e, m, f: m.update(source_scope_hash="b" * 64),
            "different_target": lambda e, m, f: m.update(target="000001.SZ"),
            "different_source": lambda e, m, f: m.update(source_identity="other-source"),
            "different_result": lambda e, m, f: m.update(source_result_version="other-result"),
            "old_etf_updated_at": lambda e, m, f: e.update(updated_at="2026-07-16T10:00:00"),
            "future_margin_updated_at": lambda e, m, f: m.update(updated_at="2026-07-18T10:00:00"),
            "blank_candidate": lambda e, m, f: e.update(recommended_etfs=[{"code": "", "name": "", "reason": ""}]),
            "boolean_cash": lambda e, m, f: e.update(available_cash=True),
            "boolean_ratio": lambda e, m, f: e.update(recommended_cash_ratio=True),
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

    def test_result_identity_changes_with_every_displayed_projection_value(self):
        etf, margin, freshness = self._packets()
        baseline = snapshot._attach_margin_etf_focus_binding(etf, margin, freshness)[0]["margin_etf_focus_binding"]
        mutations = {
            "cash": lambda packet: packet.update(available_cash=999999),
            "cash_ratio": lambda packet: packet.update(recommended_cash_ratio=31),
            "current_margin": lambda packet: packet.update(current_margin_ratio=8),
            "recommended_margin": lambda packet: packet.update(recommended_margin_ratio=9),
            "allow_margin": lambda packet: packet.update(allow_new_margin=True),
            "candidate_code": lambda packet: packet["recommended_etfs"][0].update(code="510500.SH"),
            "candidate_name": lambda packet: packet["recommended_etfs"][0].update(name="中证 500 ETF"),
            "candidate_reason": lambda packet: packet["recommended_etfs"][0].update(reason="不同研究理由"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                changed_etf, changed_margin, changed_freshness = self._packets()
                mutate(changed_etf)
                changed = snapshot._attach_margin_etf_focus_binding(
                    changed_etf,
                    changed_margin,
                    changed_freshness,
                )[0]["margin_etf_focus_binding"]
                self.assertNotEqual(changed["result_version"], baseline["result_version"])
                self.assertNotEqual(changed["producer_run_id"], baseline["producer_run_id"])

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
                **self.IDENTITY,
                **self.SAFE,
                "status": "ready",
                "data_status": "ready",
                "data_date": compact,
                "updated_at": f"{iso}T10:00:00",
                "source": "融资 ETF 本地配置快照",
                "verification_status": "已验证",
                "recommended_cash_ratio": 22,
                "current_margin_ratio": 9,
                "recommended_margin_ratio": 10,
                "allow_new_margin": False,
                "available_cash": 128000,
                "recommended_etfs": [
                    {"code": "510300.SH", "name": "沪深 300 ETF", "reason": "宽基研究样本", "state": "观察"},
                ],
            },
            "command_center_margin_packet": {
                **self.IDENTITY,
                **self.SAFE,
                "status": "ready",
                "data_status": "ready",
                "trade_date": compact,
                "updated_at": f"{iso}T10:00:01",
                "source": "Tushare margin_detail 缓存",
                "financing_balance_yi": 12.3,
                "financing_buy_yi": 1.2,
                "margin_balance_yi": 14.5,
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
