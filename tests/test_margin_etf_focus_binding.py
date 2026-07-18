import copy
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import command_center_etf_packet
import command_center_home_snapshot as snapshot
import command_center_margin_packet
from server.services import margin_etf_focus_provenance as provenance
from server.services import market_service, packet_service


class MarginEtfFocusBindingTests(unittest.TestCase):
    SAFE = {
        **{field: False for field in provenance.FALSE_SAFETY_FIELDS},
        **{field: True for field in provenance.TRUE_SAFETY_FIELDS},
        "warnings": [],
    }

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.evidence_root = Path(self.temporary.name)
        self.now = dt.datetime(2026, 7, 17, 10, 5, 0, tzinfo=provenance.SHANGHAI)

    def tearDown(self):
        self.temporary.cleanup()

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
            "last_updated": "2026-07-17T10:01:00+08:00",
        }
        return etf, margin, freshness

    def _task(self, etf, margin, *, target="002008.SZ", fetched_at="2026-07-17T10:02:00+08:00"):
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

    def _record(self, etf, margin, freshness, task, *, issued_at="2026-07-17T10:03:00+08:00"):
        with patch("server.services.task_service.read_latest_task_status_by_type", return_value=task):
            binding, digests = snapshot._build_margin_etf_focus_binding(
                etf, margin, freshness, now=self.now
            )
        self.assertTrue(binding)
        receipt = provenance.record_trusted_producer_receipt(
            digests,
            issued_at=issued_at,
            evidence_root=self.evidence_root,
            now=self.now,
        )
        self.assertIsNotNone(receipt)
        return receipt

    def _attach(self, etf, margin, freshness, task=None, *, record=True):
        task = self._task(etf, margin) if task is None else task
        if record:
            self._record(etf, margin, freshness, task)
        with patch("server.services.task_service.read_latest_task_status_by_type", return_value=task):
            return snapshot._attach_margin_etf_focus_binding(
                etf,
                margin,
                freshness,
                now=self.now,
                evidence_root=self.evidence_root,
            )

    def test_canonical_persisted_task_receives_identical_reachable_binding(self):
        etf, margin, freshness = self._packets()
        etf["margin_etf_focus_binding"] = {"attacker": "must_be_replaced"}
        margin["margin_etf_focus_binding"] = {"attacker": "must_be_replaced"}
        bound_etf, bound_margin = self._attach(etf, margin, freshness)

        binding = bound_etf["margin_etf_focus_binding"]
        self.assertEqual(binding, bound_margin["margin_etf_focus_binding"])
        self.assertNotIn("attacker", binding)
        self.assertEqual(binding["projection"]["etf"]["available_cash"], "128000")
        self.assertEqual(binding["source_identity"]["task_type"], provenance.TASK_TYPE)
        self.assertEqual(binding["source_identity"]["ledger_fetched_at"], "2026-07-17T10:02:00+08:00")
        self.assertTrue(binding["producer_receipt"]["verified"])
        self.assertTrue(binding["producer_receipt"]["state_continuity_verified"])
        self.assertTrue(binding["usable_for_risk_budget"])
        self.assertFalse(binding["external_calls_triggered"])

    def test_explicit_post_signer_records_then_get_only_verifies(self):
        etf, margin, freshness = self._packets()
        task = self._task(etf, margin)
        with (
            patch.object(provenance, "EVIDENCE_ROOT", self.evidence_root),
            patch("server.services.packet_service._read_packet_without_margin_etf_binding", side_effect=[etf, margin]),
            patch("server.services.packet_service.load_snapshot_cache", return_value={"data_freshness": freshness}),
            patch("server.services.task_service.read_latest_task_status_by_type", return_value=task),
            patch.object(provenance, "now_shanghai", return_value=self.now),
        ):
            receipt = market_service._record_margin_etf_trusted_receipt(
                issued_at="2026-07-17T10:03:00+08:00"
            )
        self.assertIsNotNone(receipt)
        self.assertEqual(set(receipt), set(provenance._RECEIPT_FIELDS))
        self.assertFalse(any("key" in field.lower() for field in receipt))
        with patch("server.services.task_service.read_latest_task_status_by_type", return_value=task):
            bound, _ = snapshot._attach_margin_etf_focus_binding(
                etf,
                margin,
                freshness,
                now=self.now,
                evidence_root=self.evidence_root,
            )
        self.assertTrue(bound["margin_etf_focus_binding"]["producer_receipt"]["verified"])

    def test_persisted_and_snapshot_forged_bindings_are_stripped_without_trust(self):
        etf, margin, freshness = self._packets()
        forged = {"producer_receipt": {"verified": True}, "usable_for_risk_budget": True}
        etf["margin_etf_focus_binding"] = copy.deepcopy(forged)
        margin["margin_etf_focus_binding"] = copy.deepcopy(forged)

        for source in ("sqlite_meta", "stock_ming_snapshot"):
            with self.subTest(source=source):
                normalized_etf = packet_service._normalize_cached_packet(
                    "command_center_etf_packet", etf, source=source, source_key="etf_packet"
                )
                normalized_margin = packet_service._normalize_cached_packet(
                    "command_center_margin_packet", margin, source=source, source_key="margin_packet"
                )
                self.assertNotIn("margin_etf_focus_binding", normalized_etf)
                self.assertNotIn("margin_etf_focus_binding", normalized_margin)

        with patch("server.services.task_service.read_latest_task_status_by_type", return_value={}):
            bound_etf, bound_margin = snapshot._attach_margin_etf_focus_binding(
                etf,
                margin,
                freshness,
                now=self.now,
                evidence_root=self.evidence_root,
            )
        self.assertNotIn("margin_etf_focus_binding", bound_etf)
        self.assertNotIn("margin_etf_focus_binding", bound_margin)

    def test_hand_json_missing_safety_and_explicit_deepseek_true_fail_closed(self):
        etf, margin, freshness = self._packets()
        for packet, builder in (
            (
                etf,
                lambda value: command_center_etf_packet.build_command_center_etf_packet(
                    {"command_center_etf_packet": value}
                ),
            ),
            (margin, lambda value: command_center_margin_packet.build_command_center_margin_packet({"command_center_margin_packet": value}, target="002008.SZ")),
        ):
            manual = copy.deepcopy(packet)
            for field in provenance.FALSE_SAFETY_FIELDS:
                manual.pop(field, None)
            manual.pop("warnings", None)
            adapted = builder(manual)
            self.assertNotIn("warnings", adapted)
            self.assertFalse(adapted["deepseek_called"])
            self.assertEqual(
                adapted["local_read_safety_provenance"],
                "legacy_builder_inferred_local_read_safety",
            )
            self.assertIsNone(provenance.safety_projection(adapted))
        etf["deepseek_called"] = True
        self.assertNotIn("margin_etf_focus_binding", self._attach(etf, margin, freshness, task={}, record=False)[0])

        etf, margin, _ = self._packets()
        etf.pop("deepseek_called")
        normalized = packet_service._normalize_cached_packet(
            "command_center_etf_packet", etf, source="snapshot", source_key="etf_packet"
        )
        self.assertFalse(normalized["deepseek_called"])
        self.assertNotIn("deepseek_called", normalized["cache_api_explicit_safety_fields"])
        self.assertIsNone(provenance.build_source_projection(normalized, margin, target="002008.SZ"))

    def test_legacy_builder_inferred_safety_provenance_survives_snapshot_alias_normalize(self):
        legacy_etf, legacy_margin, _ = self._packets()
        for packet in (legacy_etf, legacy_margin):
            packet.pop("packet_key")
            for field in (*provenance.FALSE_SAFETY_FIELDS, *provenance.TRUE_SAFETY_FIELDS):
                packet.pop(field)

        built_etf = command_center_etf_packet.build_command_center_etf_packet(
            {"command_center_etf_packet": legacy_etf}
        )
        built_margin = command_center_margin_packet.build_command_center_margin_packet(
            {"command_center_margin_packet": legacy_margin},
            target="002008.SZ",
        )
        for packet in (built_etf, built_margin):
            self.assertFalse(packet["deepseek_called"])
            self.assertEqual(
                packet["local_read_safety_provenance"],
                "legacy_builder_inferred_local_read_safety",
            )
            self.assertIsNone(provenance.safety_projection(packet))

        snapshot_cache = {"etf_packet": built_etf, "margin_packet": built_margin}
        normalized_etf = packet_service._read_snapshot_packet(
            "command_center_etf_packet", snapshot_cache
        )
        normalized_margin = packet_service._read_snapshot_packet(
            "command_center_margin_packet", snapshot_cache
        )
        self.assertIsNotNone(normalized_etf)
        self.assertIsNotNone(normalized_margin)
        for packet in (normalized_etf, normalized_margin):
            self.assertFalse(packet["deepseek_called"])
            self.assertEqual(
                packet["local_read_safety_provenance"],
                "legacy_builder_inferred_local_read_safety",
            )
            self.assertEqual(
                set(packet["cache_api_explicit_safety_fields"]),
                {*provenance.FALSE_SAFETY_FIELDS, *provenance.TRUE_SAFETY_FIELDS},
            )
            self.assertIsNone(provenance.safety_projection(packet))
        self.assertIsNone(
            provenance.build_source_projection(
                normalized_etf,
                normalized_margin,
                target="002008.SZ",
            )
        )

    def test_canonical_native_safety_survives_builder_and_snapshot_alias_normalize(self):
        native_etf, native_margin, _ = self._packets()
        built_etf = command_center_etf_packet.build_command_center_etf_packet(
            {"command_center_etf_packet": native_etf}
        )
        built_margin = command_center_margin_packet.build_command_center_margin_packet(
            {"command_center_margin_packet": native_margin},
            target="002008.SZ",
        )
        snapshot_cache = {"etf_packet": built_etf, "margin_packet": built_margin}
        normalized_etf = packet_service._read_snapshot_packet(
            "command_center_etf_packet", snapshot_cache
        )
        normalized_margin = packet_service._read_snapshot_packet(
            "command_center_margin_packet", snapshot_cache
        )
        self.assertIsNotNone(normalized_etf)
        self.assertIsNotNone(normalized_margin)
        for packet in (normalized_etf, normalized_margin):
            self.assertNotIn("local_read_safety_provenance", packet)
            self.assertIsNotNone(provenance.safety_projection(packet))
        self.assertIsNotNone(
            provenance.build_source_projection(
                normalized_etf,
                normalized_margin,
                target="002008.SZ",
            )
        )

    def test_canonical_packet_key_does_not_bless_builder_inferred_safety(self):
        hand_etf, hand_margin, _ = self._packets()
        for packet in (hand_etf, hand_margin):
            for field in (*provenance.FALSE_SAFETY_FIELDS, *provenance.TRUE_SAFETY_FIELDS):
                packet.pop(field)

        built_etf = command_center_etf_packet.build_command_center_etf_packet(
            {"command_center_etf_packet": hand_etf}
        )
        built_margin = command_center_margin_packet.build_command_center_margin_packet(
            {"command_center_margin_packet": hand_margin},
            target="002008.SZ",
        )
        for packet in (built_etf, built_margin):
            self.assertFalse(packet["deepseek_called"])
            self.assertEqual(
                packet["local_read_safety_provenance"],
                "legacy_builder_inferred_local_read_safety",
            )
        self.assertIsNone(
            provenance.build_source_projection(
                packet_service._normalize_cached_packet(
                    "command_center_etf_packet",
                    built_etf,
                    source="stock_ming_snapshot",
                    source_key="etf_packet",
                ),
                packet_service._normalize_cached_packet(
                    "command_center_margin_packet",
                    built_margin,
                    source="stock_ming_snapshot",
                    source_key="margin_packet",
                ),
                target="002008.SZ",
            )
        )

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
            "inferred_safety_marker_even_null": lambda e, m, f, t: e.update(local_read_safety_provenance=None),
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
                self._record(etf, margin, freshness, task)
                mutate(etf, margin, freshness, task)
                bound_etf, bound_margin = self._attach(etf, margin, freshness, task=task, record=False)
                self.assertNotIn("margin_etf_focus_binding", bound_etf)
                self.assertNotIn("margin_etf_focus_binding", bound_margin)

    def test_2359_to_0000_rollover_is_not_same_day_evidence(self):
        etf, margin, freshness = self._packets()
        etf["updated_at"] = "2026-07-17T23:59:00+08:00"
        margin["updated_at"] = "2026-07-17T23:59:10+08:00"
        task = self._task(etf, margin, fetched_at="2026-07-17T23:59:30+08:00")
        freshness["last_updated"] = "2026-07-18T00:00:00+08:00"
        bound_etf, _ = self._attach(etf, margin, freshness, task=task, record=False)
        self.assertNotIn("margin_etf_focus_binding", bound_etf)

    def test_every_display_value_requires_a_new_real_task_binding(self):
        etf, margin, freshness = self._packets()
        baseline = self._attach(etf, margin, freshness)[0]["margin_etf_focus_binding"]
        changed_etf = copy.deepcopy(etf)
        changed_etf["available_cash"] = 999999
        stale_task_result = self._attach(
            changed_etf, margin, freshness, task=self._task(etf, margin), record=False
        )[0]
        self.assertNotIn("margin_etf_focus_binding", stale_task_result)
        rebound = self._attach(changed_etf, margin, freshness)[0]["margin_etf_focus_binding"]
        self.assertNotEqual(rebound["result_version"], baseline["result_version"])
        self.assertNotEqual(rebound["source_identity"]["source_projection_sha256"], baseline["source_identity"]["source_projection_sha256"])

    def test_coherent_public_hash_self_seal_cannot_replace_trusted_event(self):
        etf, margin, freshness = self._packets()
        task = self._task(etf, margin)
        self._record(etf, margin, freshness, task)
        changed = copy.deepcopy(etf)
        changed["available_cash"] = 999999
        changed_task = self._task(changed, margin)
        with patch("server.services.task_service.read_latest_task_status_by_type", return_value=changed_task):
            _, digests = snapshot._build_margin_etf_focus_binding(
                changed, margin, freshness, now=self.now
            )
        journal = provenance._journal_path(self.evidence_root)
        with sqlite3.connect(journal) as connection:
            previous = connection.execute(
                f"SELECT event_mac FROM {provenance._EVENT_TABLE} WHERE sequence_no = 1"
            ).fetchone()[0]
            unsigned = {
                "sequence_no": 2,
                "schema_version": provenance.PRODUCER_EVENT_SCHEMA_VERSION,
                "semantic_digest": provenance.canonical_digest(digests),
                "issued_at": "2026-07-17T10:04:00+08:00",
                **digests,
                "previous_event_mac": previous,
            }
            event_id = provenance.canonical_digest(unsigned)
            fake_event = {**unsigned, "event_id": event_id, "event_mac": "f" * 64}
            connection.execute(
                f"INSERT INTO {provenance._EVENT_TABLE} ({', '.join(provenance._EVENT_FIELDS)}) "
                f"VALUES ({', '.join('?' for _ in provenance._EVENT_FIELDS)})",
                tuple(fake_event[field] for field in provenance._EVENT_FIELDS),
            )
            connection.commit()
        _, _, state_path = provenance._trust_paths(self.evidence_root)
        fake_state = {
            "schema_version": provenance.PRODUCER_STATE_SCHEMA_VERSION,
            "sequence_no": 2,
            "event_id": event_id,
            "event_mac": "f" * 64,
            "semantic_digest": provenance.canonical_digest(digests),
            "state_mac": "e" * 64,
        }
        state_path.write_text(json.dumps(fake_state), encoding="utf-8")
        state_path.chmod(0o600)
        bound, _ = self._attach(changed, margin, freshness, task=changed_task, record=False)
        self.assertNotIn("margin_etf_focus_binding", bound)

    def test_missing_state_bad_mac_and_journal_rollback_fail_closed(self):
        etf, margin, freshness = self._packets()
        task = self._task(etf, margin)
        self._record(etf, margin, freshness, task)
        etf["margin_etf_focus_binding"] = {"attacker": "must_be_stripped"}
        margin["margin_etf_focus_binding"] = {"attacker": "must_be_stripped"}
        _, _, state_path = provenance._trust_paths(self.evidence_root)
        state_bytes = state_path.read_bytes()
        state_path.unlink()
        self.assertNotIn(
            "margin_etf_focus_binding",
            self._attach(etf, margin, freshness, task=task, record=False)[0],
        )
        state_path.write_bytes(state_bytes)
        state_path.chmod(0o600)

        journal = provenance._journal_path(self.evidence_root)
        with sqlite3.connect(journal) as connection:
            connection.execute(f"DROP TRIGGER {provenance._EVENT_TABLE}_no_update")
            connection.execute(
                f"UPDATE {provenance._EVENT_TABLE} SET event_mac = ? WHERE sequence_no = 1",
                ("a" * 64,),
            )
            connection.commit()
        self.assertNotIn(
            "margin_etf_focus_binding",
            self._attach(etf, margin, freshness, task=task, record=False)[0],
        )

        self.temporary.cleanup()
        self.temporary = tempfile.TemporaryDirectory()
        self.evidence_root = Path(self.temporary.name)
        self._record(etf, margin, freshness, task)
        changed = copy.deepcopy(etf)
        changed["available_cash"] = 999999
        changed_task = self._task(changed, margin)
        self._record(changed, margin, freshness, changed_task, issued_at="2026-07-17T10:04:00+08:00")
        journal = provenance._journal_path(self.evidence_root)
        with sqlite3.connect(journal) as connection:
            connection.execute(f"DROP TRIGGER {provenance._EVENT_TABLE}_no_delete")
            connection.execute(f"DELETE FROM {provenance._EVENT_TABLE} WHERE sequence_no = 2")
            connection.commit()
        self.assertNotIn(
            "margin_etf_focus_binding",
            self._attach(changed, margin, freshness, task=changed_task, record=False)[0],
        )

    def test_same_day_future_chain_and_future_receipt_fail_closed(self):
        etf, margin, freshness = self._packets()
        etf["updated_at"] = "2026-07-17T23:55:00+08:00"
        margin["updated_at"] = "2026-07-17T23:55:01+08:00"
        freshness["last_updated"] = "2026-07-17T23:56:00+08:00"
        task = self._task(etf, margin, fetched_at="2026-07-17T23:57:00+08:00")
        with patch("server.services.task_service.read_latest_task_status_by_type", return_value=task):
            binding, digests = snapshot._build_margin_etf_focus_binding(
                etf, margin, freshness, now=self.now
            )
        self.assertEqual(binding, {})
        self.assertEqual(digests, {})

        etf, margin, freshness = self._packets()
        task = self._task(etf, margin)
        with patch("server.services.task_service.read_latest_task_status_by_type", return_value=task):
            _, digests = snapshot._build_margin_etf_focus_binding(etf, margin, freshness, now=self.now)
        receipt = provenance.record_trusted_producer_receipt(
            digests,
            issued_at="2026-07-17T23:59:00+08:00",
            evidence_root=self.evidence_root,
            now=self.now,
        )
        self.assertIsNone(receipt)


if __name__ == "__main__":
    unittest.main()
