from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from storage.sqlite_meta import SQLiteMetaStore
from server.api import routes_next_session
from server.services import next_session_external_promotion_service as external_promotion
from server.services import next_session_production_packet_service as producer
from server.services import next_session_replacement_promotion_service as replacement


HEAD = "a" * 40


def _tree_snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    if not root.exists():
        return {}
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            payload = path.read_bytes()
            metadata = path.stat()
            result[str(path.relative_to(root))] = (
                metadata.st_size,
                metadata.st_mtime_ns,
                hashlib.sha256(payload).hexdigest(),
            )
    return result


def _base_packet() -> dict:
    coverage_keys = [
        "latest_close_anchor",
        "scenario_paths",
        "reference_and_limit_lines",
        "operation_zones_and_guardrails",
        "position_conflict_warnings",
        "freshness_and_data_trust",
        "deepseek_status_display",
        "hover_click_drilldown",
        "read_only_action_boundary",
    ]
    rows = [
        {
            "coverage_key": key,
            "retained": True,
            "direct_observation": True,
            "same_packet": True,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_operation_zones": True,
            "contains_secret": False,
        }
        for key in coverage_keys
    ]
    coverage = {
        "schema_version": "next_session_same_packet_signal_capability_coverage.v1",
        "status": "same_packet_signal_capability_coverage_ready",
        "same_packet": True,
        "lineage_bound": True,
        "direct_evidence_ready": True,
        "required_feature_group_count": 9,
        "retained_feature_group_count": 9,
        "missing_feature_groups": [],
        "rows": rows,
    }
    return {
        "packet_key": producer.PACKET_KEY,
        "schema_version": "next_session_projection.v1",
        "status": "ready_cache_replay",
        "symbol": "000001.SZ",
        "chart_payload": {
            "status": "ready",
            "is_exact_next_session_packet": True,
            "uses_real_daily_close": False,
            "historical_points": [],
            "scenario_series": [{"scenario_key": "neutral", "points": [{"x": "T+1", "price": 10.0}]}],
            "reference_lines": [{"key": "latest", "value": 10.0}],
            "operation_zones": [{"zone_key": "observe", "price_range": [9.5, 10.5]}],
            "chart_maturity": {
                "status": "ready",
                "has_real_60d_close": False,
                "scenario_anchor_count": 1,
                "scenario_anchored_count": 1,
            },
            "chart_contract": {
                "cache_only": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "frontend_computes_trade_action": False,
                "does_not_modify_action": True,
                "does_not_modify_operation_zones": True,
            },
        },
        "chart_summary": {"is_exact_next_session_packet": True, "uses_real_daily_close": False},
        "next_session_same_packet_signal_capability_coverage": coverage,
        "next_session_same_packet_signal_capability_coverage_rows": rows,
        "contains_secret": False,
    }


def _dataset_and_task() -> tuple[dict, dict]:
    dates = [(date(2026, 1, 1) + timedelta(days=index)).strftime("%Y%m%d") for index in range(60)]
    daily_rows = [
        {"ts_code": "000001.SZ", "trade_date": value, "close": float(10 + index)}
        for index, value in enumerate(dates)
    ]
    calendar_rows = [{"cal_date": value, "is_open": 1} for value in dates]
    normalized_daily = [
        {"ts_code": row["ts_code"], "trade_date": row["trade_date"], "close": round(row["close"], 8)}
        for row in daily_rows
    ]
    normalized_calendar = [dict(row) for row in calendar_rows]
    call_ledger = [
        {
            "api": "daily",
            "call_status": "success",
            "external_calls_triggered": True,
            "tushare_called": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    receipt_observed = (now - timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    receipt_completed = (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    task_finished = now.isoformat().replace("+00:00", "Z")
    verified = {
        "ready": True,
        "blockers": [],
        "scope_hash": "b" * 64,
        "version_digest": "c" * 64,
        "validated_trade_date": dates[-1],
        "official_call_ledger_digest": producer._digest(call_ledger),
        "official_execution_event_digest": "d" * 64,
        "official_receipt_observed_at_utc": receipt_observed,
        "official_receipt_completed_at_utc": receipt_completed,
        "symbols": ["000001.SZ"],
        "frames": {
            "daily": pd.DataFrame(daily_rows),
            "trade_cal": pd.DataFrame(calendar_rows),
        },
    }
    task = {
        "task_id": "provider-task-current-head",
        "task_type": "refresh_tushare_facts",
        "status": "success",
        "progress": 1.0,
        "output_packet_key": "command_center_tushare_refresh_packet",
        "payload_safe": {"acceptance_mode": "full_interface_provider_production"},
        "call_ledger": call_ledger,
        "finished_at": task_finished,
        "external_calls_triggered": True,
        "tushare_called": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    return verified, task


class NextSessionProductionPacketProducerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / ".stock_ming_3"
        self.db = self.root / "meta.sqlite"
        self.store = SQLiteMetaStore(self.db)
        self.store.write_packet(producer.PACKET_KEY, _base_packet())
        self.verified, self.task = _dataset_and_task()
        self.store.write_task_status(self.task)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_explicit_post_producer_binds_current_history_dataset_and_coverage(self) -> None:
        with (
            patch.object(replacement, "_current_head", return_value=HEAD),
            patch.object(
                producer,
                "_current_shanghai_date",
                return_value=datetime.strptime(
                    self.verified["validated_trade_date"], "%Y%m%d"
                ).date(),
            ),
            patch.object(
                producer.tushare_production_store,
                "validate_tushare_full_market_production_version",
                return_value=self.verified,
            ),
        ):
            result = producer.produce_next_session_production_packet(
                {"source_task_id": self.task["task_id"]},
                evidence_root=self.root,
                project_root=self.base,
                sqlite_path=self.db,
            )
        self.assertTrue(result["packet_written"], result["blockers"])
        packet = SQLiteMetaStore(self.db, read_only=True).read_packet(producer.PACKET_KEY)
        provenance = packet["production_replacement_provenance"]
        self.assertEqual(provenance["schema_version"], producer.PROVENANCE_SCHEMA)
        self.assertEqual(packet["result_version"], provenance["result_version"])
        self.assertEqual(packet["packet_scope_hash"], provenance["packet_scope_hash"])
        self.assertEqual(packet["coverage_rows_digest"], provenance["coverage_rows_digest"])
        self.assertEqual(
            provenance["source_task_payload_digest"],
            replacement._digest(self.task["payload_safe"]),
        )
        authoritative = {
            "ready": True,
            "blockers": [],
            "symbol": provenance["symbol"],
            "data_date": provenance["data_date"],
            "provider_scope_hash": provenance["provider_scope_hash"],
            "dataset_version_digest": provenance["dataset_version_digest"],
            "daily_rows_digest": provenance["daily_rows_digest"],
            "trade_calendar_digest": provenance["trade_calendar_digest"],
            "source_task_call_ledger_digest": provenance["source_task_call_ledger_digest"],
            "official_execution_event_digest": provenance["official_execution_event_digest"],
            "source_task_finished_at": provenance["source_task_finished_at"],
            "provider_receipt_observed_at_utc": provenance[
                "provider_receipt_observed_at_utc"
            ],
            "provider_receipt_completed_at_utc": provenance[
                "provider_receipt_completed_at_utc"
            ],
            "authoritative_calendar_as_of_date": provenance[
                "authoritative_calendar_as_of_date"
            ],
            "authoritative_current_trade_date": provenance[
                "authoritative_current_trade_date"
            ],
            "validated_trade_date": provenance["data_date"],
            "row_count": 60,
        }
        evidence, blockers = replacement._next_packet_evidence(
            packet,
            head_full=HEAD,
            authoritative=authoritative,
            source_task=self.task,
        )
        self.assertTrue(evidence["exact_result_version_scope_coverage_binding"], blockers)
        self.assertEqual(blockers, [])
        packet["result_version"] = "next-session-prod-" + "0" * 24
        tampered, tampered_blockers = replacement._next_packet_evidence(
            packet,
            head_full=HEAD,
            authoritative=authoritative,
            source_task=self.task,
        )
        self.assertFalse(tampered["exact_result_version_scope_coverage_binding"])
        self.assertIn(
            "next_session_exact_result_version_scope_coverage_binding_invalid",
            tampered_blockers,
        )

    def test_current_history_mismatch_fails_without_packet_write(self) -> None:
        connection = self.store._connect()
        try:
            changed = {**self.task, "status": "failed"}
            connection.execute(
                "UPDATE task_status SET payload_json = ? WHERE task_id = ?",
                (json.dumps(changed), self.task["task_id"]),
            )
            connection.commit()
        finally:
            connection.close()
        before = SQLiteMetaStore(self.db, read_only=True).read_packet(producer.PACKET_KEY)
        with (
            patch.object(replacement, "_current_head", return_value=HEAD),
            patch.object(
                producer,
                "_current_shanghai_date",
                return_value=datetime.strptime(
                    self.verified["validated_trade_date"], "%Y%m%d"
                ).date(),
            ),
            patch.object(
                producer.tushare_production_store,
                "validate_tushare_full_market_production_version",
                return_value=self.verified,
            ),
        ):
            result = producer.produce_next_session_production_packet(
                {"source_task_id": self.task["task_id"]},
                evidence_root=self.root,
                project_root=self.base,
                sqlite_path=self.db,
            )
        self.assertFalse(result["packet_written"])
        self.assertIn("next_session_production_source_task_current_history_invalid", result["blockers"])
        self.assertEqual(
            SQLiteMetaStore(self.db, read_only=True).read_packet(producer.PACKET_KEY),
            before,
        )

    def test_packet_postcommit_exception_reconciles_exact_readback(self) -> None:
        original = SQLiteMetaStore.promote_packet_atomic

        def commit_then_raise(store: SQLiteMetaStore, packet_key: str, packet: dict) -> dict:
            original(store, packet_key, packet)
            raise OSError("injected_postcommit_response_loss")

        with (
            patch.object(replacement, "_current_head", return_value=HEAD),
            patch.object(
                producer,
                "_current_shanghai_date",
                return_value=datetime.strptime(
                    self.verified["validated_trade_date"], "%Y%m%d"
                ).date(),
            ),
            patch.object(
                producer.tushare_production_store,
                "validate_tushare_full_market_production_version",
                return_value=self.verified,
            ),
            patch.object(SQLiteMetaStore, "promote_packet_atomic", new=commit_then_raise),
        ):
            result = producer.produce_next_session_production_packet(
                {"source_task_id": self.task["task_id"]},
                evidence_root=self.root,
                project_root=self.base,
                sqlite_path=self.db,
            )
        self.assertTrue(result["packet_written"], result["blockers"])
        self.assertTrue(result["postcommit_reconciled"])

    def test_packet_postcommit_mismatch_fails_closed(self) -> None:
        original = SQLiteMetaStore.promote_packet_atomic

        def mismatch_then_raise(store: SQLiteMetaStore, packet_key: str, packet: dict) -> dict:
            original(store, packet_key, {**packet, "result_version": "forged-postcommit"})
            raise OSError("injected_partial_or_mismatched_commit")

        with (
            patch.object(replacement, "_current_head", return_value=HEAD),
            patch.object(
                producer,
                "_current_shanghai_date",
                return_value=datetime.strptime(
                    self.verified["validated_trade_date"], "%Y%m%d"
                ).date(),
            ),
            patch.object(
                producer.tushare_production_store,
                "validate_tushare_full_market_production_version",
                return_value=self.verified,
            ),
            patch.object(SQLiteMetaStore, "promote_packet_atomic", new=mismatch_then_raise),
        ):
            result = producer.produce_next_session_production_packet(
                {"source_task_id": self.task["task_id"]},
                evidence_root=self.root,
                project_root=self.base,
                sqlite_path=self.db,
            )
        self.assertFalse(result["packet_written"])
        self.assertIn(
            "next_session_production_packet_atomic_write_failed_readback_mismatch",
            result["blockers"],
        )

    def test_stale_or_missing_task_receipt_freshness_fails_closed(self) -> None:
        stale = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=30)
        for missing in (False, True):
            with self.subTest(missing=missing):
                task = dict(self.task)
                task["finished_at"] = "" if missing else stale.isoformat().replace("+00:00", "Z")
                self.store.write_task_status(task)
                verified = dict(self.verified)
                verified["official_receipt_observed_at_utc"] = (
                    "" if missing else (stale - timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
                )
                verified["official_receipt_completed_at_utc"] = (
                    "" if missing else (stale - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
                )
                with (
                    patch.object(replacement, "_current_head", return_value=HEAD),
                    patch.object(
                        producer,
                        "_current_shanghai_date",
                        return_value=datetime.strptime(
                            verified["validated_trade_date"], "%Y%m%d"
                        ).date(),
                    ),
                    patch.object(
                        producer.tushare_production_store,
                        "validate_tushare_full_market_production_version",
                        return_value=verified,
                    ),
                ):
                    result = producer.produce_next_session_production_packet(
                        {"source_task_id": task["task_id"]},
                        evidence_root=self.root,
                        project_root=self.base,
                        sqlite_path=self.db,
                    )
                self.assertFalse(result["packet_written"])
                expected = (
                    "next_session_production_freshness_timestamps_missing"
                    if missing
                    else "next_session_production_source_task_or_receipt_stale"
                )
                self.assertIn(expected, result["blockers"])

    def test_months_old_dataset_cannot_be_current_production_packet(self) -> None:
        data_date = datetime.strptime(self.verified["validated_trade_date"], "%Y%m%d").date()
        with (
            patch.object(replacement, "_current_head", return_value=HEAD),
            patch.object(
                producer,
                "_current_shanghai_date",
                return_value=data_date + timedelta(days=90),
            ),
            patch.object(
                producer.tushare_production_store,
                "validate_tushare_full_market_production_version",
                return_value=self.verified,
            ),
        ):
            result = producer.produce_next_session_production_packet(
                {"source_task_id": self.task["task_id"]},
                evidence_root=self.root,
                project_root=self.base,
                sqlite_path=self.db,
            )
        self.assertFalse(result["packet_written"])
        self.assertIn("next_session_production_calendar_not_current", result["blockers"])


class NextSessionExternalPromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.evidence = self.base / "evidence"
        self.trust_root = self.base / "external-trust"
        self.trust_root.mkdir(mode=0o700)
        self.approval_path = self.trust_root / "approval.json"
        self.high_water_path = self.trust_root / "high-water.json"
        self.finalization_path = self.trust_root / "finalization.json"
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.fingerprint = hashlib.sha256(
            self.public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        ).hexdigest()
        self.key_history = {(1, self.fingerprint): self.public_key}
        self.patches = [
            patch.object(external_promotion, "APPROVAL_PATH", self.approval_path),
            patch.object(external_promotion, "HIGH_WATER_PATH", self.high_water_path),
            patch.object(external_promotion, "FINALIZATION_PATH", self.finalization_path),
            patch.object(external_promotion, "TRUSTED_OWNER_UIDS", frozenset({os.getuid()})),
            patch.object(
                external_promotion.external_trust,
                "_load_trusted_public_key",
                return_value=(
                    self.public_key,
                    {
                        "status": "external_public_key_verified",
                        "key_fingerprint_sha256": self.fingerprint,
                    },
                ),
            ),
            patch.object(
                external_promotion.external_trust,
                "_load_trusted_event_public_key",
                side_effect=self._load_event_key,
            ),
        ]
        for item in self.patches:
            item.start()
        material = {
                "scope": external_promotion.SCOPE,
                "head_full": HEAD,
                "next_packet_digest": "1" * 64,
                "motion_pair_digest": "2" * 64,
                "streamlit_retirement_digest": "3" * 64,
                "remote_ci_digest": "4" * 64,
                "remote_run_id": "123",
                "remote_artifact_digest": "sha256:" + "5" * 64,
                "release_promotion_event_id": "6" * 64,
        }
        self.prerequisites = {
            "ready": True,
            "head_full": HEAD,
            "semantic_digest": external_promotion._digest(material),
            "material": material,
        }

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def _load_event_key(self, *, epoch: object, fingerprint: object) -> tuple:
        key = self.key_history.get((epoch, fingerprint))
        if key is None:
            return None, {"status": "trusted_key_history_material_unavailable_or_untrusted"}
        return key, {
            "status": "trusted_historical_public_key_verified",
            "key_fingerprint_sha256": fingerprint,
        }

    def _sign(self, schema: str, statement: dict) -> dict:
        signature = self.private_key.sign(external_promotion._canonical_bytes(statement))
        return {
            "schema_version": schema,
            "algorithm": "Ed25519",
            "key_fingerprint_sha256": self.fingerprint,
            "key_epoch": statement["key_epoch"],
            "statement": statement,
            "signature_base64": base64.b64encode(signature).decode("ascii"),
        }

    def _write_external_pair(
        self,
        *,
        nonce: str,
        sequence_no: int = 1,
        previous: str = "",
        issued: datetime | None = None,
        high_water_issued: datetime | None = None,
        key_epoch: int = 1,
    ) -> tuple[dict, dict]:
        proposal = external_promotion.build_proposal(self.prerequisites, self.evidence)
        issued = issued or datetime.now(timezone.utc).replace(microsecond=0)
        high_water_issued = high_water_issued or issued
        approval = {
            "schema_version": external_promotion.APPROVAL_STATEMENT_SCHEMA,
            "status": "next_session_replacement_approved",
            "scope": external_promotion.SCOPE,
            "head_full": HEAD,
            "semantic_digest": self.prerequisites["semantic_digest"],
            "review_id": proposal["approval_review_id"],
            "approval_id": "",
            "nonce_digest": nonce,
            "approved_by_user": True,
            "issued_at": issued.isoformat().replace("+00:00", "Z"),
            "expires_at": (issued + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "key_epoch": key_epoch,
        }
        approval["approval_id"] = external_promotion._digest(
            {key: approval[key] for key in sorted(approval) if key != "approval_id"}
        )
        event_proposal = {
            "scope": external_promotion.SCOPE,
            "sequence_no": sequence_no,
            "previous_event_id": previous,
            "head_full": HEAD,
            "semantic_digest": self.prerequisites["semantic_digest"],
            "approval_id": approval["approval_id"],
            "approval_review_id": proposal["approval_review_id"],
            "approval_nonce_digest": nonce,
        }
        high_water = {
            "schema_version": external_promotion.HIGH_WATER_STATEMENT_SCHEMA,
            "status": "next_session_replacement_high_water_committed",
            "scope": external_promotion.SCOPE,
            "head_full": HEAD,
            "semantic_digest": self.prerequisites["semantic_digest"],
            "event_id": external_promotion._digest(event_proposal),
            "sequence_no": sequence_no,
            "previous_event_id": previous,
            "approval_id": approval["approval_id"],
            "nonce_digest": nonce,
            "issued_at": high_water_issued.isoformat().replace("+00:00", "Z"),
            "key_epoch": key_epoch,
        }
        approval_envelope = self._sign(external_promotion.APPROVAL_ENVELOPE_SCHEMA, approval)
        high_water_envelope = self._sign(external_promotion.HIGH_WATER_ENVELOPE_SCHEMA, high_water)
        for path, value in (
            (self.approval_path, approval_envelope),
            (self.high_water_path, high_water_envelope),
        ):
            path.chmod(0o600) if path.exists() else None
            path.write_text(json.dumps(value), encoding="utf-8")
            path.chmod(0o400)
        return approval_envelope, high_water_envelope

    def _write_finalization(self, event: dict, **overrides: object) -> dict:
        issued = datetime.now(timezone.utc)
        prepared_at = datetime.fromisoformat(event["recorded_at_utc"].replace("Z", "+00:00"))
        if issued <= prepared_at:
            issued = prepared_at + timedelta(microseconds=1)
        statement = {
            "schema_version": external_promotion.FINALIZATION_STATEMENT_SCHEMA,
            "status": "next_session_replacement_external_finalized",
            "scope": external_promotion.SCOPE,
            "head_full": event["head_full"],
            "event_id": event["event_id"],
            "sequence_no": event["sequence_no"],
            "commit_generation": event["commit_generation"],
            "prepared_event_digest": event["prepared_event_digest"],
            "semantic_digest": event["semantic_digest"],
            "approval_signature_digest": event["approval_signature_digest"],
            "high_water_signature_digest": event["high_water_signature_digest"],
            "approval_nonce_digest": event["approval_nonce_digest"],
            "key_epoch": event["key_epoch"],
            "issued_at": issued.isoformat().replace("+00:00", "Z"),
            "expires_at": (issued + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "external_counter": event["expected_external_counter"],
            "previous_finalization_digest": event["previous_finalization_digest"],
        }
        statement.update(overrides)
        signature = self.private_key.sign(external_promotion._canonical_bytes(statement))
        envelope = {
            "schema_version": external_promotion.FINALIZATION_ENVELOPE_SCHEMA,
            "algorithm": "Ed25519",
            "key_fingerprint_sha256": self.fingerprint,
            "key_epoch": event["key_epoch"],
            "statement": statement,
            "signature_base64": base64.b64encode(signature).decode("ascii"),
        }
        self.finalization_path.chmod(0o600) if self.finalization_path.exists() else None
        self.finalization_path.write_text(json.dumps(envelope), encoding="utf-8")
        self.finalization_path.chmod(0o400)
        return envelope

    def test_signed_external_pair_is_required_and_get_validation_is_zero_write(self) -> None:
        missing = external_promotion.validate_current_promotion(
            self.prerequisites,
            evidence_root=self.evidence,
        )
        self.assertFalse(missing["ready"])
        self.assertFalse(self.evidence.exists())
        self._write_external_pair(nonce="7" * 64)
        written = external_promotion.append_promotion_event(
            {"approved_by_user": True},
            self.prerequisites,
            evidence_root=self.evidence,
        )
        self.assertFalse(written["promotion_written"])
        self.assertTrue(written["prepared_event_written"], written["blockers"])
        self.assertFalse(written["ready"])
        awaiting = external_promotion.validate_current_promotion(
            self.prerequisites, evidence_root=self.evidence
        )
        self.assertFalse(awaiting["ready"])
        self._write_finalization(written["event"])
        before = _tree_snapshot(self.evidence)
        validated = external_promotion.validate_current_promotion(
            self.prerequisites,
            evidence_root=self.evidence,
        )
        after = _tree_snapshot(self.evidence)
        self.assertTrue(validated["ready"], validated["blockers"])
        self.assertEqual(before, after)
        self.assertFalse(validated["writes_storage"])

    def test_forgery_rollback_and_nonce_replay_fail_closed(self) -> None:
        self._write_external_pair(nonce="8" * 64)
        first = external_promotion.append_promotion_event(
            {"approved_by_user": True},
            self.prerequisites,
            evidence_root=self.evidence,
        )
        self.assertTrue(first["prepared_event_written"])
        first_event_id = first["event_id"]
        self._write_finalization(first["event"])

        self._write_external_pair(nonce="8" * 64, sequence_no=2, previous=first_event_id)
        replay = external_promotion.append_promotion_event(
            {"approved_by_user": True},
            self.prerequisites,
            evidence_root=self.evidence,
        )
        self.assertFalse(replay.get("prepared_event_written", False))
        self.assertIn("next_session_replacement_approval_nonce_replayed", replay["blockers"])
        self.assertEqual(len(list((self.evidence / external_promotion.JOURNAL_NAME / "events").glob("*.json"))), 1)

        rolled_back = external_promotion.validate_current_promotion(
            self.prerequisites,
            evidence_root=self.evidence,
        )
        self.assertTrue(rolled_back["ready"], rolled_back["blockers"])

        event_path = self.evidence / external_promotion.JOURNAL_NAME / "events" / "00000001.json"
        event_path.chmod(0o600)
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["approval_envelope"]["statement"]["head_full"] = "b" * 40
        event_path.write_text(json.dumps(event), encoding="utf-8")
        forged = external_promotion.validate_current_promotion(
            self.prerequisites,
            evidence_root=self.evidence,
        )
        self.assertFalse(forged["ready"])
        self.assertIn("external_envelope_signature_invalid", forged["blockers"])

    def test_caller_cannot_supply_approval_or_high_water(self) -> None:
        result = external_promotion.append_promotion_event(
            {
                "approved_by_user": True,
                "approval_envelope": {"approved": True},
                "high_water": {"counter": 1},
            },
            self.prerequisites,
            evidence_root=self.evidence,
        )
        self.assertFalse(result["promotion_written"])
        self.assertFalse(self.evidence.exists())

    def test_local_final_residue_cannot_replace_external_receipt(self) -> None:
        self._write_external_pair(nonce="d" * 64)
        prepared = external_promotion.append_promotion_event(
            {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
        )
        residue = self.evidence / external_promotion.JOURNAL_NAME / "commits"
        residue.mkdir(mode=0o700)
        (residue / "final.json").write_text(
            json.dumps({"status": "locally_finalized", "ready": True}), encoding="utf-8"
        )
        validated = external_promotion.validate_current_promotion(
            self.prerequisites, evidence_root=self.evidence
        )
        self.assertTrue(prepared["prepared_event_written"])
        self.assertFalse(validated["ready"])
        self.assertFalse(validated["production_replacement_complete"])
        self.assertIn("external_next_session_finalization_missing", validated["blockers"])

    def test_api_audit_labels_phase_a_as_prepared_not_promoted(self) -> None:
        ledger = routes_next_session._replacement_promotion_ledger(
            {
                "status": "next_session_production_replacement_prepared_awaiting_external_finalization",
                "prepared_event_written": True,
                "promotion_written": False,
                "production_replacement_complete": False,
            },
            request_method="POST",
        )[0]
        self.assertEqual(
            ledger["mode"], "prepared_event_append_awaiting_external_finalization"
        )
        self.assertTrue(ledger["prepared_event_written"])
        self.assertFalse(ledger["promotion_written"])
        self.assertEqual(ledger["row_count"], 0)

    def test_receipt_must_bind_prepared_order_head_counter_and_previous(self) -> None:
        self._write_external_pair(nonce="e" * 64)
        prepared = external_promotion.append_promotion_event(
            {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
        )["event"]
        prepared_at = datetime.fromisoformat(prepared["recorded_at_utc"].replace("Z", "+00:00"))
        cases = (
            {"head_full": "b" * 40},
            {"external_counter": 2},
            {"previous_finalization_digest": "f" * 64},
            {
                "issued_at": (prepared_at - timedelta(seconds=1)).isoformat().replace(
                    "+00:00", "Z"
                )
            },
        )
        for override in cases:
            with self.subTest(override=override):
                self._write_finalization(prepared, **override)
                validated = external_promotion.validate_current_promotion(
                    self.prerequisites, evidence_root=self.evidence
                )
                self.assertFalse(validated["ready"])
                self.assertIn(
                    "external_next_session_finalization_contract_invalid",
                    validated["blockers"],
                )

    def test_receipt_numeric_fields_reject_bool(self) -> None:
        self._write_external_pair(nonce="3" * 64)
        prepared = external_promotion.append_promotion_event(
            {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
        )["event"]
        for field in ("sequence_no", "external_counter", "key_epoch"):
            with self.subTest(field=field):
                self._write_finalization(prepared, **{field: True})
                validated = external_promotion.validate_current_promotion(
                    self.prerequisites, evidence_root=self.evidence
                )
                self.assertFalse(validated["ready"])
                self.assertIn(
                    "external_next_session_finalization_contract_invalid",
                    validated["blockers"],
                )

    def test_future_high_water_is_rejected_before_prepare(self) -> None:
        self._write_external_pair(
            nonce="4" * 64,
            issued=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        result = external_promotion.append_promotion_event(
            {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
        )
        self.assertFalse(result.get("prepared_event_written", False))
        self.assertIn("external_next_session_high_water_issued_in_future", result["blockers"])

    def test_key_rotation_uses_storage_history_and_missing_history_fails_closed(self) -> None:
        self._write_external_pair(nonce="5" * 64)
        first = external_promotion.append_promotion_event(
            {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
        )
        self._write_finalization(first["event"])
        self.assertTrue(
            external_promotion.validate_current_promotion(
                self.prerequisites, evidence_root=self.evidence
            )["ready"]
        )

        self.private_key = Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.fingerprint = hashlib.sha256(
            self.public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        ).hexdigest()
        self.key_history[(2, self.fingerprint)] = self.public_key
        self._write_external_pair(
            nonce="6" * 64,
            sequence_no=2,
            previous=first["event_id"],
            key_epoch=2,
        )
        second = external_promotion.append_promotion_event(
            {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
        )
        self.assertTrue(second["prepared_event_written"], second["blockers"])
        self.assertEqual(second["event"]["key_epoch"], 2)
        self._write_finalization(second["event"])
        rotated = external_promotion.validate_current_promotion(
            self.prerequisites, evidence_root=self.evidence
        )
        self.assertTrue(rotated["ready"], rotated["blockers"])

        self.key_history = {
            binding: key for binding, key in self.key_history.items() if binding[0] != 1
        }
        missing_history = external_promotion.validate_current_promotion(
            self.prerequisites, evidence_root=self.evidence
        )
        self.assertFalse(missing_history["ready"])
        self.assertIn(
            "trusted_key_history_material_unavailable_or_untrusted",
            missing_history["blockers"],
        )

    def test_postcommit_full_journal_validation_controls_written_claim(self) -> None:
        self._write_external_pair(nonce="a" * 64)
        original = external_promotion._read_events
        calls = 0

        def fail_postcommit(root: Path) -> tuple[list[dict], list[str]]:
            nonlocal calls
            calls += 1
            if calls >= 4:
                return [], ["injected_postcommit_journal_failure"]
            return original(root)

        with patch.object(external_promotion, "_read_events", side_effect=fail_postcommit):
            result = external_promotion.append_promotion_event(
                {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
            )
        self.assertFalse(result["prepared_event_written"])
        self.assertFalse(result["promotion_written"])
        self.assertIn(
            "next_session_prepared_event_postcommit_journal_validation_failed",
            result["blockers"],
        )

    def test_old_receipt_replay_cannot_finalize_new_prepared_generation(self) -> None:
        self._write_external_pair(nonce="1" * 64)
        first = external_promotion.append_promotion_event(
            {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
        )
        old_receipt = self._write_finalization(first["event"])
        self._write_external_pair(
            nonce="2" * 64, sequence_no=2, previous=first["event_id"]
        )
        second = external_promotion.append_promotion_event(
            {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
        )
        self.assertTrue(second["prepared_event_written"], second["blockers"])
        self.assertNotEqual(
            first["event"]["commit_generation"], second["event"]["commit_generation"]
        )
        self.assertEqual(second["event"]["expected_external_counter"], 2)
        self.assertEqual(
            second["event"]["previous_finalization_digest"],
            external_promotion._digest(old_receipt),
        )
        validated = external_promotion.validate_current_promotion(
            self.prerequisites, evidence_root=self.evidence
        )
        self.assertFalse(validated["ready"])
        self.assertIn(
            "external_next_session_finalization_contract_invalid", validated["blockers"]
        )

    def test_wrong_key_old_head_and_expired_authority_fail_closed(self) -> None:
        trusted_private_key = self.private_key
        self.private_key = Ed25519PrivateKey.generate()
        self._write_external_pair(nonce="9" * 64)
        wrong_key = external_promotion.append_promotion_event(
            {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
        )
        self.assertFalse(wrong_key["promotion_written"])
        self.assertIn("external_envelope_signature_invalid", wrong_key["blockers"])

        self.private_key = trusted_private_key
        self._write_external_pair(nonce="a" * 64)
        new_prerequisites = json.loads(json.dumps(self.prerequisites))
        new_prerequisites["head_full"] = "b" * 40
        new_prerequisites["material"]["head_full"] = "b" * 40
        new_prerequisites["semantic_digest"] = external_promotion._digest(
            new_prerequisites["material"]
        )
        old_head = external_promotion.append_promotion_event(
            {"approved_by_user": True}, new_prerequisites, evidence_root=self.evidence
        )
        self.assertFalse(old_head["promotion_written"])
        self.assertIn("external_next_session_approval_contract_invalid", old_head["blockers"])

        self._write_external_pair(
            nonce="b" * 64,
            issued=datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=30),
        )
        expired = external_promotion.append_promotion_event(
            {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
        )
        self.assertFalse(expired["promotion_written"])
        self.assertIn("external_next_session_approval_expired_or_not_yet_valid", expired["blockers"])

    def test_link_commit_cleanup_exception_reconciles_truthfully(self) -> None:
        self._write_external_pair(nonce="c" * 64)
        original_unlink = Path.unlink

        def fail_temp_cleanup(path: Path, *args: object, **kwargs: object) -> None:
            if path.name.startswith(".00000001.json.") and path.name.endswith(".tmp"):
                raise OSError("injected_cleanup_failure")
            original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", new=fail_temp_cleanup):
            written = external_promotion.append_promotion_event(
                {"approved_by_user": True}, self.prerequisites, evidence_root=self.evidence
            )
        self.assertTrue(written["prepared_event_written"], written["blockers"])
        self.assertFalse(written["ready"])
        self.assertTrue(written["postcommit_reconciled"])
        validated = external_promotion.validate_current_promotion(
            self.prerequisites, evidence_root=self.evidence
        )
        self.assertFalse(validated["ready"])


if __name__ == "__main__":
    unittest.main()
