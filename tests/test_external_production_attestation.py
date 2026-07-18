from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from server.main import app
from server.services import external_production_attestation_service as external
from server.services import storage_service
from storage.sqlite_meta import SQLiteMetaStore


class ExternalProductionAttestationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.trust_root = self.root / "operator-trust"
        self.db_path = self.root / "state" / "meta.sqlite"
        self.lock_path = self.root / "state" / "external-trust.lock"
        self.private_key = Ed25519PrivateKey.generate()
        self.fingerprint = self._install_public_key()
        self.stack.enter_context(
            patch.multiple(
                external,
                TRUST_ROOT=self.trust_root,
                TRUST_ANCHOR=self.root,
                PUBLIC_KEY_PATH=self.trust_root / "ed25519-public.pem",
                FINGERPRINT_PATH=self.trust_root / "ed25519-public.sha256",
                IMPORT_LOCK_PATH=self.lock_path,
                SQLITE_META_PATH=self.db_path,
                TRUSTED_OWNER_UIDS=frozenset({os.getuid()}),
            )
        )
        self.stack.enter_context(patch.object(storage_service, "SQLITE_META_PATH", self.db_path))

    def tearDown(self) -> None:
        self.stack.close()

    def _install_public_key(self) -> str:
        self.trust_root.mkdir(parents=True)
        public_key = self.private_key.public_key()
        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        der = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        fingerprint = hashlib.sha256(der).hexdigest()
        key_path = self.trust_root / "ed25519-public.pem"
        fingerprint_path = self.trust_root / "ed25519-public.sha256"
        key_path.write_bytes(pem)
        fingerprint_path.write_text(fingerprint + "\n", encoding="ascii")
        key_path.chmod(0o444)
        fingerprint_path.chmod(0o444)
        self.trust_root.chmod(0o555)
        return fingerprint

    def _claims(self, kind: str, subject: str) -> dict:
        if kind == "storage_ttl_resolution":
            return {
                "dataset": subject,
                "resolution": "fresh_no_refresh_required",
                "refresh_task_id": f"refresh-{subject}",
                "before_ttl_state": "fresh",
                "after_ttl_state": "fresh",
                "refresh_executed": False,
                "provider_call_count": 0,
                "fetched_at": "2026-07-18T00:00:00+00:00",
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
            }
        if kind == "worker_runtime_lineage":
            return {
                "worker_run_id": subject,
                "redis_transport_digest": "1" * 64,
                "celery_task_ids_digest": "2" * 64,
                "eligible_worker_count": 2,
                "batch_count": 3,
                "row_count": 4000,
                "does_not_execute_trades": True,
            }
        if kind == "factor_full_market_lineage":
            return {
                "result_dataset": "factor_values",
                "result_version_id": subject,
                "universe_digest": "3" * 64,
                "universe_count": 4000,
                "metric_validation_digest": "4" * 64,
                "full_market_factor_research": True,
                "does_not_execute_trades": True,
            }
        return {
            "candidate_cache_packet_key": "command_center_3_candidate_radar_cache",
            "cache_write_task_id": "candidate-cache-write-1",
            "universe_digest": "5" * 64,
            "candidate_row_count": 120,
            "browser_evidence_digest": "6" * 64,
            "performance_evidence_digest": "7" * 64,
            "legacy_retirement_evidence_digest": "8" * 64,
            "candidate_radar_production_replacement": True,
            "candidate_is_not_buy_instruction": True,
            "does_not_execute_trades": True,
        }

    def _envelope(
        self,
        kind: str,
        subject: str,
        counter: int,
        previous: str,
        *,
        claims: dict | None = None,
        nonce_seed: str = "",
        head_full: str | None = None,
        private_key: Ed25519PrivateKey | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc)
        resolved_claims = claims or self._claims(kind, subject)
        statement = {
            "schema_version": external.STATEMENT_SCHEMA_VERSION,
            "attestation_kind": kind,
            "head_full": head_full or external._current_head_full(),
            "nonce_digest": hashlib.sha256(
                f"nonce:{counter}:{kind}:{subject}:{nonce_seed}".encode("utf-8")
            ).hexdigest(),
            "scope_hash": hashlib.sha256(f"scope:{kind}:{subject}".encode("utf-8")).hexdigest(),
            "task_id": (
                str(resolved_claims["refresh_task_id"])
                if kind == "storage_ttl_resolution"
                else str(resolved_claims["cache_write_task_id"])
                if kind == "candidate_radar_lineage"
                else f"task-{counter}-{subject}"
            ),
            "subject": subject,
            "artifact_digest": hashlib.sha256(f"artifact:{kind}:{subject}".encode("utf-8")).hexdigest(),
            "monotonic_counter": counter,
            "previous_attestation_digest": previous,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
            "claims": resolved_claims,
        }
        signature = (private_key or self.private_key).sign(external._canonical_bytes(statement))
        return {
            "schema_version": external.ENVELOPE_SCHEMA_VERSION,
            "algorithm": "Ed25519",
            "key_fingerprint_sha256": self.fingerprint,
            "statement": statement,
            "signature_base64": base64.b64encode(signature).decode("ascii"),
        }

    def _import(self, envelope: dict, *, kind: str | None = None) -> dict:
        return external.import_signed_attestation(
            {"signed_envelope": envelope},
            expected_kind=kind,
        )

    def _resign(self, envelope: dict) -> dict:
        envelope["signature_base64"] = base64.b64encode(
            self.private_key.sign(external._canonical_bytes(envelope["statement"]))
        ).decode("ascii")
        return envelope

    def test_get_is_zero_write_and_missing_key_never_self_seals(self) -> None:
        self.trust_root.chmod(0o755)
        (self.trust_root / "ed25519-public.pem").unlink()
        (self.trust_root / "ed25519-public.sha256").unlink()
        self.trust_root.rmdir()
        status = external.read_external_attestation_status()
        self.assertFalse(status["ready"])
        self.assertFalse(status["get_writes_performed"])
        self.assertFalse(self.db_path.exists())
        self.assertFalse(self.lock_path.exists())

        result = self._import(self._envelope("worker_runtime_lineage", "worker-run-1", 1, ""))
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "external_trust_material_unavailable_or_untrusted")
        self.assertFalse(result["private_key_generated"])
        self.assertFalse(result["private_key_loaded"])
        self.assertFalse(any(self.root.rglob("*private*")))

    def test_valid_import_is_idempotent_and_caller_boolean_is_rejected(self) -> None:
        signed = self._envelope("worker_runtime_lineage", "worker-run-1", 1, "")
        imported = self._import(signed)
        self.assertFalse(imported["ready"])
        self.assertTrue(imported["local_integrity_ready"])
        self.assertTrue(imported["external_signature_verified"])
        self.assertFalse(imported["external_trust_verified"])
        self.assertFalse(imported["production_trusted"])
        self.assertTrue(imported["writes_performed"])
        database_before = self.db_path.read_bytes()

        replay = self._import(signed)
        self.assertFalse(replay["ready"])
        self.assertTrue(replay["local_integrity_ready"])
        self.assertEqual(replay["status"], "external_attestation_already_imported_local_integrity_only")
        self.assertFalse(replay["writes_performed"])
        self.assertEqual(self.db_path.read_bytes(), database_before)

        crafted = external.import_signed_attestation(
            {"signed_envelope": signed, "approved_by_user": True}
        )
        self.assertFalse(crafted["ready"])
        self.assertEqual(crafted["status"], "signed_envelope_only_required")

    def test_wrong_key_controls_signature_and_chain_fail_closed(self) -> None:
        key_path = self.trust_root / "ed25519-public.pem"
        key_bytes = key_path.read_bytes()
        self.trust_root.chmod(0o755)
        key_path.unlink()
        symlink_target = self.root / "untrusted-public.pem"
        symlink_target.write_bytes(key_bytes)
        symlink_target.chmod(0o444)
        key_path.symlink_to(symlink_target)
        self.trust_root.chmod(0o555)
        symlinked = self._import(self._envelope("worker_runtime_lineage", "worker-run-1", 1, ""))
        self.assertFalse(symlinked["ready"])
        self.assertEqual(symlinked["public_key_status"], "symlink_rejected")
        self.trust_root.chmod(0o755)
        key_path.unlink()
        key_path.write_bytes(key_bytes)
        key_path.chmod(0o444)
        self.trust_root.chmod(0o555)

        with patch.object(external, "TRUSTED_OWNER_UIDS", frozenset({os.getuid() + 1000})):
            wrong_owner = self._import(
                self._envelope("worker_runtime_lineage", "worker-run-1", 1, "")
            )
        self.assertFalse(wrong_owner["ready"])
        self.assertEqual(wrong_owner["public_key_status"], "owner_untrusted")

        key_path.chmod(0o644)
        untrusted = self._import(self._envelope("worker_runtime_lineage", "worker-run-1", 1, ""))
        self.assertFalse(untrusted["ready"])
        self.assertEqual(untrusted["public_key_status"], "trusted_file_not_read_only")
        key_path.chmod(0o444)

        wrong_key = Ed25519PrivateKey.generate()
        bad_signature = self._import(
            self._envelope(
                "worker_runtime_lineage",
                "worker-run-1",
                1,
                "",
                private_key=wrong_key,
            )
        )
        self.assertFalse(bad_signature["ready"])
        self.assertEqual(bad_signature["status"], "signed_envelope_signature_invalid")

        out_of_order = self._import(
            self._envelope("worker_runtime_lineage", "worker-run-2", 2, "")
        )
        self.assertFalse(out_of_order["ready"])
        self.assertEqual(out_of_order["status"], "signed_statement_monotonic_chain_invalid")

        first_envelope = self._envelope("worker_runtime_lineage", "worker-run-1", 1, "")
        first = self._import(first_envelope)
        self.assertTrue(first["local_integrity_ready"])
        replay_nonce = self._envelope(
            "worker_runtime_lineage",
            "worker-run-1",
            2,
            first["attestation_id"],
        )
        replay_nonce["statement"]["nonce_digest"] = first_envelope["statement"]["nonce_digest"]
        replay_nonce["signature_base64"] = base64.b64encode(
            self.private_key.sign(external._canonical_bytes(replay_nonce["statement"]))
        ).decode("ascii")
        blocked = self._import(replay_nonce)
        self.assertFalse(blocked["ready"])
        self.assertEqual(blocked["status"], "signed_statement_nonce_replayed")

    def test_sensitive_or_extra_claims_and_wrong_head_are_rejected(self) -> None:
        claims = self._claims("worker_runtime_lineage", "worker-run-1")
        claims["api_key"] = "must-not-be-stored"
        extra = self._import(
            self._envelope("worker_runtime_lineage", "worker-run-1", 1, "", claims=claims)
        )
        self.assertFalse(extra["ready"])
        self.assertEqual(extra["status"], "signed_statement_contract_invalid")

        sensitive = self._claims("worker_runtime_lineage", "worker-run-1")
        sensitive["worker_run_id"] = "secret-value"
        rejected = self._import(
            self._envelope("worker_runtime_lineage", "worker-run-1", 1, "", claims=sensitive)
        )
        self.assertFalse(rejected["ready"])
        self.assertEqual(rejected["status"], "signed_statement_contract_invalid")

        wrong_head = self._import(
            self._envelope(
                "worker_runtime_lineage",
                "worker-run-1",
                1,
                "",
                head_full="0" * 40,
            )
        )
        self.assertFalse(wrong_head["ready"])
        self.assertEqual(wrong_head["status"], "signed_statement_contract_invalid")

    def test_invalid_existing_registry_is_never_destructively_recovered(self) -> None:
        first = self._import(
            self._envelope("worker_runtime_lineage", "worker-run-1", 1, "")
        )
        self.assertTrue(first["local_integrity_ready"])
        store = SQLiteMetaStore(self.db_path)
        packet = store.read_packet(external.REGISTRY_PACKET_KEY)
        packet["events"][0]["attestation_id"] = "0" * 64
        store.write_packet(external.REGISTRY_PACKET_KEY, packet)

        second = self._import(
            self._envelope(
                "worker_runtime_lineage",
                "worker-run-2",
                2,
                first["attestation_id"],
            )
        )
        self.assertFalse(second["ready"])
        self.assertEqual(
            second["status"],
            "external_attestation_registry_existing_state_invalid",
        )
        unchanged = store.read_packet(external.REGISTRY_PACKET_KEY)
        self.assertEqual(unchanged["events"][0]["attestation_id"], "0" * 64)
        self.assertEqual(len(unchanged["events"]), 1)

    def test_storage_imports_are_local_integrity_only_and_never_write_consumer(self) -> None:
        previous = ""
        imported_rows: list[dict] = []
        for counter, dataset in enumerate(storage_service.CANONICAL_PARQUET_DATASETS, start=1):
            signed = self._envelope(
                "storage_ttl_resolution",
                dataset,
                counter,
                previous,
            )
            result = storage_service.import_storage_cache_ttl_external_attestation(
                {"signed_envelope": signed}
            )
            self.assertFalse(result["ready"])
            self.assertTrue(result["local_integrity_ready"])
            self.assertFalse(result["production_trusted"])
            self.assertFalse(result["storage_packet_written"])
            self.assertTrue(result["consumer_state_unchanged"])
            imported_rows.append(result)
            previous = result["attestation_id"]
        validation = storage_service.storage_cache_ttl_refresh_evidence()
        self.assertFalse(validation["production_ttl_evidence_ready"])
        self.assertFalse(validation["production_trust_boundary_satisfied"])
        self.assertEqual(validation["external_attestation_verified_dataset_count"], 0)
        self.assertFalse(
            SQLiteMetaStore(self.db_path).read_packet(
                storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY
            )
        )
        registry = external.validate_registry()
        self.assertTrue(registry["local_integrity_ready"])
        self.assertFalse(registry["production_trusted"])
        self.assertEqual(registry["last_monotonic_counter"], len(storage_service.CANONICAL_PARQUET_DATASETS))
        self.assertFalse(validation["refresh_executed_by_validator"])
        self.assertFalse(validation["external_calls_triggered_by_validator"])

        rows = []
        for imported in imported_rows:
            claims = imported["claims"]
            row = {
                "dataset": claims["dataset"],
                "resolution": claims["resolution"],
                "refresh_task_id": claims["refresh_task_id"],
                "refresh_scope_hash": imported["scope_hash"],
                "artifact_sha256": imported["artifact_digest"],
                "before_ttl_state": claims["before_ttl_state"],
                "after_ttl_state": claims["after_ttl_state"],
                "refresh_executed": claims["refresh_executed"],
                "provider_call_count": claims["provider_call_count"],
                "fetched_at": claims["fetched_at"],
                "external_calls_triggered": claims["external_calls_triggered"],
                "does_not_execute_trades": claims["does_not_execute_trades"],
                "external_attestation_id": imported["attestation_id"],
            }
            row["payload_digest"] = storage_service._json_sha256(
                storage_service._storage_cache_ttl_resolution_material(
                    row, imported["head_full"]
                )
            )
            rows.append(row)
        SQLiteMetaStore(self.db_path).write_packet(
            storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY,
            {
                "schema_version": storage_service.CACHE_TTL_REFRESH_EVIDENCE_SCHEMA_VERSION,
                "head_full": imported_rows[-1]["head_full"],
                "rows": rows,
            },
        )
        caller_wired = storage_service.storage_cache_ttl_refresh_evidence()
        self.assertEqual(
            caller_wired["external_attestation_verified_dataset_count"],
            len(storage_service.CANONICAL_PARQUET_DATASETS),
        )
        self.assertFalse(caller_wired["production_ttl_evidence_ready"])
        self.assertFalse(caller_wired["production_trust_boundary_satisfied"])
        self.assertFalse(caller_wired["production_trusted"])
        self.assertIn("production_consumer_not_wired", caller_wired["production_blockers"])

    def test_worker_factor_and_radar_lineages_stay_local_integrity_only(self) -> None:
        previous = ""
        rows = (
            ("worker_runtime_lineage", "worker-run-1"),
            ("factor_full_market_lineage", "factor-version-1"),
            ("candidate_radar_lineage", "command_center_3_candidate_radar_cache"),
        )
        for counter, (kind, subject) in enumerate(rows, start=1):
            result = self._import(self._envelope(kind, subject, counter, previous))
            self.assertFalse(result["ready"])
            self.assertTrue(result["local_integrity_ready"])
            previous = result["attestation_id"]
            lineage = external.validate_attested_lineage(
                attestation_kind=kind,
                subject=subject,
                scope_hash=result["scope_hash"],
                task_id=result["task_id"],
                artifact_digest=result["artifact_digest"],
            )
            self.assertFalse(lineage["ready"])
            self.assertTrue(lineage["local_integrity_ready"])
            self.assertFalse(lineage["production_trusted"])
            self.assertFalse(lineage["writes_performed"])
            self.assertFalse(lineage["contains_secret"])
            missing_binding = external.validate_attested_lineage(
                attestation_kind=kind,
                subject=subject,
            )
            self.assertFalse(missing_binding["ready"])
            self.assertEqual(
                missing_binding["status"],
                "external_attested_lineage_exact_bindings_required",
            )
        contract = external.external_attestation_contract()
        self.assertEqual(
            contract["planned_consumers"],
            ["storage", "worker", "factor", "candidate_radar"],
        )
        self.assertEqual(contract["production_consumers_wired"], [])
        self.assertFalse(contract["application_generates_private_key"])
        self.assertTrue(contract["caller_boolean_cannot_promote"])

    def test_registry_rollback_is_detected_as_local_only_not_production_trust(self) -> None:
        first_envelope = self._envelope("worker_runtime_lineage", "worker-run-1", 1, "")
        first = self._import(first_envelope)
        self.assertTrue(first["local_integrity_ready"])
        store = SQLiteMetaStore(self.db_path)
        snapshot = store.read_packet(external.REGISTRY_PACKET_KEY)
        second = self._import(
            self._envelope(
                "factor_full_market_lineage",
                "factor-version-1",
                2,
                first["attestation_id"],
            )
        )
        self.assertTrue(second["local_integrity_ready"])
        store.write_packet(external.REGISTRY_PACKET_KEY, snapshot)

        rolled_back = external.validate_registry()
        self.assertTrue(rolled_back["local_integrity_ready"])
        self.assertFalse(rolled_back["ready"])
        self.assertFalse(rolled_back["production_trusted"])
        self.assertFalse(rolled_back["snapshot_rollback_resistant"])
        self.assertEqual(rolled_back["last_monotonic_counter"], 1)
        self.assertIn("external_monotonic_anchor_unavailable", rolled_back["blockers"])

    def test_concurrent_branches_commit_at_most_one_atomic_successor(self) -> None:
        first = self._import(
            self._envelope("worker_runtime_lineage", "worker-run-1", 1, "")
        )
        branches = (
            self._envelope(
                "worker_runtime_lineage",
                "worker-run-2a",
                2,
                first["attestation_id"],
                nonce_seed="a",
            ),
            self._envelope(
                "worker_runtime_lineage",
                "worker-run-2b",
                2,
                first["attestation_id"],
                nonce_seed="b",
            ),
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self._import, branches))
        self.assertEqual(sum(row.get("local_integrity_ready") is True for row in results), 1)
        self.assertEqual(sum(row.get("writes_performed") is True for row in results), 1)
        registry = external.validate_registry()
        self.assertTrue(registry["local_integrity_ready"])
        self.assertEqual(registry["last_monotonic_counter"], 2)
        self.assertEqual(registry["event_count"], 2)
        self.assertFalse(registry["production_trusted"])

    def test_new_head_can_continue_local_chain_without_claiming_key_epoch_trust(self) -> None:
        first = self._import(
            self._envelope("worker_runtime_lineage", "worker-run-1", 1, "")
        )
        new_head = "a" * 40 if external._current_head_full() != "a" * 40 else "b" * 40
        with patch.object(external, "_current_head_full", return_value=new_head):
            second = self._import(
                self._envelope(
                    "worker_runtime_lineage",
                    "worker-run-2",
                    2,
                    first["attestation_id"],
                    head_full=new_head,
                )
            )
            self.assertTrue(second["local_integrity_ready"])
            self.assertFalse(second["production_trusted"])
            registry = external.validate_registry()
            self.assertTrue(registry["local_integrity_ready"])
            self.assertEqual(registry["last_monotonic_counter"], 2)
            lineage = external.validate_attested_lineage(
                attestation_kind="worker_runtime_lineage",
                subject="worker-run-2",
                scope_hash=second["scope_hash"],
                task_id=second["task_id"],
                artifact_digest=second["artifact_digest"],
            )
            self.assertTrue(lineage["local_integrity_ready"])
            self.assertFalse(lineage["ready"])
            self.assertIn("trusted_head_key_epoch_unavailable", lineage["blockers"])

    def test_storage_update_retry_and_invalid_semantics_never_touch_consumer_packet(self) -> None:
        store = SQLiteMetaStore(self.db_path)
        sentinel = {"schema_version": "sentinel.v1", "head_full": external._current_head_full(), "rows": []}
        store.write_packet(storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY, sentinel)
        first_envelope = self._envelope("storage_ttl_resolution", "daily", 1, "")
        first = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": first_envelope}
        )
        self.assertTrue(first["local_integrity_ready"])
        self.assertEqual(
            store.read_packet(storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY), sentinel
        )
        replay = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": first_envelope}
        )
        self.assertTrue(replay["local_integrity_ready"])
        self.assertFalse(replay["writes_performed"])

        refreshed = self._claims("storage_ttl_resolution", "daily")
        refreshed.update(
            {
                "resolution": "refreshed",
                "refresh_task_id": "refresh-daily-v2",
                "before_ttl_state": "stale",
                "after_ttl_state": "fresh",
                "refresh_executed": True,
                "provider_call_count": 1,
                "external_calls_triggered": True,
            }
        )
        second = storage_service.import_storage_cache_ttl_external_attestation(
            {
                "signed_envelope": self._envelope(
                    "storage_ttl_resolution",
                    "daily",
                    2,
                    first["attestation_id"],
                    claims=refreshed,
                )
            }
        )
        self.assertTrue(second["local_integrity_ready"])
        self.assertFalse(second["storage_packet_written"])
        self.assertEqual(
            store.read_packet(storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY), sentinel
        )
        before_registry = store.read_packet(external.REGISTRY_PACKET_KEY)
        invalid = storage_service.import_storage_cache_ttl_external_attestation(
            {
                "signed_envelope": self._envelope(
                    "storage_ttl_resolution",
                    "unknown_dataset",
                    3,
                    second["attestation_id"],
                )
            }
        )
        self.assertFalse(invalid["local_integrity_ready"])
        self.assertFalse(invalid["writes_performed"])
        self.assertEqual(store.read_packet(external.REGISTRY_PACKET_KEY), before_registry)
        self.assertEqual(
            store.read_packet(storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY), sentinel
        )

    def test_registry_atomic_write_failure_leaves_registry_and_consumer_unchanged(self) -> None:
        store = SQLiteMetaStore(self.db_path)
        sentinel = {"schema_version": "sentinel.v1", "rows": []}
        store.write_packet(storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY, sentinel)
        with patch.object(
            external.SQLiteMetaStore,
            "promote_packet_atomic",
            side_effect=RuntimeError("injected_atomic_write_failure"),
        ):
            result = storage_service.import_storage_cache_ttl_external_attestation(
                {
                    "signed_envelope": self._envelope(
                        "storage_ttl_resolution", "daily", 1, ""
                    )
                }
            )
        self.assertFalse(result["local_integrity_ready"])
        self.assertFalse(result["writes_performed"])
        self.assertEqual(result["status"], "external_attestation_registry_write_failed")
        self.assertIsNone(store.read_packet(external.REGISTRY_PACKET_KEY))
        self.assertEqual(
            store.read_packet(storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY), sentinel
        )

    def test_semantic_relationship_attacks_are_rejected_before_write(self) -> None:
        attacks: list[dict] = []
        bad_time = self._claims("storage_ttl_resolution", "daily")
        bad_time["fetched_at"] = "not-a-timestamp"
        attacks.append(
            self._envelope("storage_ttl_resolution", "daily", 1, "", claims=bad_time)
        )
        bad_factor = self._claims("factor_full_market_lineage", "factor-version-1")
        bad_factor["result_dataset"] = "unrelated_dataset"
        attacks.append(
            self._envelope(
                "factor_full_market_lineage", "factor-version-1", 1, "", claims=bad_factor
            )
        )
        bad_radar = self._envelope(
            "candidate_radar_lineage",
            external.CANDIDATE_RADAR_PACKET_KEY,
            1,
            "",
        )
        bad_radar["statement"]["task_id"] = "different-task"
        attacks.append(self._resign(bad_radar))
        zero_scope = self._envelope("worker_runtime_lineage", "worker-run-1", 1, "")
        zero_scope["statement"]["scope_hash"] = "0" * 64
        attacks.append(self._resign(zero_scope))

        for envelope in attacks:
            with self.subTest(kind=envelope["statement"]["attestation_kind"]):
                result = self._import(envelope)
                self.assertFalse(result["local_integrity_ready"])
                self.assertFalse(result["writes_performed"])
                self.assertEqual(result["status"], "signed_statement_contract_invalid")
                self.assertFalse(self.db_path.exists())

    def test_get_and_post_routes_preserve_zero_write_and_exact_envelope_boundary(self) -> None:
        client = TestClient(app)
        response = client.get("/api/audit/external-production-attestation")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["get_writes_performed"])
        self.assertFalse(self.db_path.exists())

        signed = self._envelope("worker_runtime_lineage", "worker-run-1", 1, "")
        rejected = client.post(
            "/api/audit/external-production-attestation",
            json={"signed_envelope": signed, "production": True},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertFalse(rejected.json()["data"]["ready"])
        accepted = client.post(
            "/api/audit/external-production-attestation",
            json={"signed_envelope": signed},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertFalse(accepted.json()["data"]["ready"])
        self.assertTrue(accepted.json()["data"]["local_integrity_ready"])
        self.assertFalse(accepted.json()["data"]["production_trusted"])


if __name__ == "__main__":
    unittest.main()
