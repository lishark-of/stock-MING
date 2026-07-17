import copy
import unittest
from unittest.mock import patch

import command_center_etf_packet
import command_center_home_snapshot as snapshot
import command_center_margin_packet
from server.services import margin_etf_focus_provenance as provenance
from server.services import packet_service


class MarginEtfFocusBindingTests(unittest.TestCase):
    SAFE = {
        **{field: False for field in provenance.FALSE_SAFETY_FIELDS},
        **{field: True for field in provenance.TRUE_SAFETY_FIELDS},
        "warnings": [],
    }

    def _packets(self, date_text="20260717"):
        etf = {
            **self.SAFE,
            "packet_key": "command_center_etf_packet",
            "status": "ready",
            "data_status": "ready",
            "data_date": date_text,
            "updated_at": "2026-07-17T10:00:00+08:00",
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
            **self.SAFE,
            "packet_key": "command_center_margin_packet",
            "status": "ready",
            "data_status": "ready",
            "trade_date": date_text,
            "updated_at": "2026-07-17T10:00:01+08:00",
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
            "last_updated": "2026-07-17T10:02:00+08:00",
        }
        return etf, margin, freshness

    def _task(self, etf, margin, *, target="002008.SZ", fetched_at="2026-07-17T10:01:00+08:00"):
        source_projection = provenance.build_source_projection(etf, margin, target=target)
        self.assertIsNotNone(source_projection)
        source_sha = provenance.canonical_digest(source_projection)
        result_version = f"margin-etf-source:{source_sha}"
        scope_hash = provenance.canonical_digest(
            provenance.build_source_scope_material(target=target, source_projection_sha256=source_sha)
        )
        payload = {
            "source": "margin_etf_page_button",
            "mode": "local_packet_replay",
            "requested_packet_keys": list(provenance.REQUESTED_PACKET_KEYS),
            "target": target,
            "source_identity": provenance.SOURCE_IDENTITY,
            "source_result_version": result_version,
            "source_projection_sha256": source_sha,
            "scope_hash": scope_hash,
            "scope_hash_short": scope_hash[:12],
            "degraded_reason": "",
            "external_sources_allowed": False,
            "provider_refresh_allowed": False,
            "model_call_allowed": False,
            "trade_allowed": False,
        }
        task_id = "local-margin-etf-1"
        ledger = {
            "api": "local_margin_etf_packet_refresh",
            "endpoint": provenance.TASK_ROUTE,
            "task_id": task_id,
            "task_type": provenance.TASK_TYPE,
            "output_packet_key": provenance.TASK_OUTPUT_PACKET_KEY,
            "request_params_safe": payload,
            "target": target,
            "source_identity": provenance.SOURCE_IDENTITY,
            "source_result_version": result_version,
            "source_projection_sha256": source_sha,
            "scope_hash": scope_hash,
            "scope_hash_short": scope_hash[:12],
            "row_count": len(source_projection["etf"]["recommended_etfs"]),
            "data_date": source_projection["etf"]["data_date"],
            "local_fetched_at": fetched_at,
            "call_status": "local_packet_replay_ready",
            "failure_mode": "",
            "error_message_safe": "",
            **{field: False for field in snapshot.MARGIN_ETF_FOCUS_FALSE_SAFETY_FIELDS},
            **{field: True for field in snapshot.MARGIN_ETF_FOCUS_TRUE_SAFETY_FIELDS},
        }
        return {
            "task_id": task_id,
            "task_type": provenance.TASK_TYPE,
            "storage_source": "sqlite_meta",
            "status": "success",
            "progress": 1.0,
            "current_step": "margin_etf_local_packet_replay_ready_no_external_call",
            "output_packet_key": provenance.TASK_OUTPUT_PACKET_KEY,
            "payload_safe": payload,
            "call_ledger": [ledger],
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    def _attach(self, etf, margin, freshness, task=None):
        task = self._task(etf, margin) if task is None else task
        with patch("server.services.task_service.read_latest_task_status_by_type", return_value=task):
            return snapshot._attach_margin_etf_focus_binding(etf, margin, freshness)

    def test_canonical_persisted_task_receives_identical_reachable_binding(self):
        etf, margin, freshness = self._packets()
        bound_etf, bound_margin = self._attach(etf, margin, freshness)

        binding = bound_etf["margin_etf_focus_binding"]
        self.assertEqual(binding, bound_margin["margin_etf_focus_binding"])
        self.assertEqual(binding["projection"]["etf"]["available_cash"], "128000")
        self.assertEqual(binding["source_identity"]["task_type"], provenance.TASK_TYPE)
        self.assertEqual(binding["source_identity"]["ledger_fetched_at"], "2026-07-17T10:01:00+08:00")
        self.assertTrue(binding["usable_for_risk_budget"])
        self.assertFalse(binding["external_calls_triggered"])

    def test_hand_json_missing_safety_and_explicit_deepseek_true_fail_closed(self):
        etf, margin, freshness = self._packets()
        for packet, builder in (
            (etf, command_center_etf_packet._apply_etf_packet_contract),
            (margin, lambda value: command_center_margin_packet.build_command_center_margin_packet({"command_center_margin_packet": value}, target="002008.SZ")),
        ):
            manual = copy.deepcopy(packet)
            for field in provenance.FALSE_SAFETY_FIELDS:
                manual.pop(field, None)
            manual.pop("warnings", None)
            adapted = builder(manual)
            self.assertNotIn("warnings", adapted)
            self.assertNotIn("deepseek_called", adapted)
        etf["deepseek_called"] = True
        self.assertNotIn("margin_etf_focus_binding", self._attach(etf, margin, freshness, task={})[0])

        etf, margin, _ = self._packets()
        etf.pop("deepseek_called")
        normalized = packet_service._normalize_cached_packet(
            "command_center_etf_packet", etf, source="snapshot", source_key="etf_packet"
        )
        self.assertFalse(normalized["deepseek_called"])
        self.assertNotIn("deepseek_called", normalized["cache_api_explicit_safety_fields"])
        self.assertIsNone(provenance.build_source_projection(normalized, margin, target="002008.SZ"))

    def test_binding_and_provenance_truth_table_fail_closed(self):
        mutations = {
            "missing_task": lambda e, m, f, t: t.clear(),
            "memory_only_task": lambda e, m, f, t: t.update(storage_source="memory"),
            "hand_task_scope": lambda e, m, f, t: t["payload_safe"].update(scope_hash="a" * 64),
            "ledger_scope": lambda e, m, f, t: t["call_ledger"][0].update(scope_hash="a" * 64),
            "ledger_task": lambda e, m, f, t: t["call_ledger"][0].update(task_id="other-task"),
            "ledger_external": lambda e, m, f, t: t["call_ledger"][0].update(external_calls_triggered=True),
            "ledger_deepseek": lambda e, m, f, t: t["call_ledger"][0].update(deepseek_called=True),
            "packet_warning": lambda e, m, f, t: e.update(warnings=["unsafe"]),
            "missing_warning_field": lambda e, m, f, t: e.pop("warnings"),
            "packet_deepseek": lambda e, m, f, t: e.update(deepseek_called=True),
            "wrong_etf_packet_key": lambda e, m, f, t: e.update(packet_key="manual_etf_packet"),
            "wrong_margin_packet_key": lambda e, m, f, t: m.update(packet_key="manual_margin_packet"),
            "data_status_alias_only": lambda e, m, f, t: (e.pop("data_status"), e.update(cache_state="ready")),
            "naive_packet_timestamp": lambda e, m, f, t: e.update(updated_at="2026-07-17T10:00:00"),
            "different_packet_dates": lambda e, m, f, t: m.update(trade_date="20260716"),
            "calendar_not_validated": lambda e, m, f, t: f.update(expected_trade_date_calendar_validated=False),
            "future_packet": lambda e, m, f, t: e.update(updated_at="2026-07-17T10:01:01+08:00"),
            "cross_midnight": lambda e, m, f, t: f.update(last_updated="2026-07-18T00:00:00+08:00"),
            "blank_candidate": lambda e, m, f, t: e.update(recommended_etfs=[{"code": "", "name": "", "reason": ""}]),
            "boolean_cash": lambda e, m, f, t: e.update(available_cash=True),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                etf, margin, freshness = self._packets()
                task = self._task(etf, margin)
                mutate(etf, margin, freshness, task)
                bound_etf, bound_margin = self._attach(etf, margin, freshness, task=task)
                self.assertNotIn("margin_etf_focus_binding", bound_etf)
                self.assertNotIn("margin_etf_focus_binding", bound_margin)

    def test_2359_to_0000_rollover_is_not_same_day_evidence(self):
        etf, margin, freshness = self._packets()
        etf["updated_at"] = "2026-07-17T23:59:00+08:00"
        margin["updated_at"] = "2026-07-17T23:59:10+08:00"
        task = self._task(etf, margin, fetched_at="2026-07-17T23:59:30+08:00")
        freshness["last_updated"] = "2026-07-18T00:00:00+08:00"
        bound_etf, _ = self._attach(etf, margin, freshness, task=task)
        self.assertNotIn("margin_etf_focus_binding", bound_etf)

    def test_every_display_value_requires_a_new_real_task_binding(self):
        etf, margin, freshness = self._packets()
        baseline = self._attach(etf, margin, freshness)[0]["margin_etf_focus_binding"]
        changed_etf = copy.deepcopy(etf)
        changed_etf["available_cash"] = 999999
        stale_task_result = self._attach(changed_etf, margin, freshness, task=self._task(etf, margin))[0]
        self.assertNotIn("margin_etf_focus_binding", stale_task_result)
        rebound = self._attach(changed_etf, margin, freshness)[0]["margin_etf_focus_binding"]
        self.assertNotEqual(rebound["result_version"], baseline["result_version"])
        self.assertNotEqual(rebound["source_identity"]["source_projection_sha256"], baseline["source_identity"]["source_projection_sha256"])


if __name__ == "__main__":
    unittest.main()
