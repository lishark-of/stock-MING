from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
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
        self.epoch_path = self.trust_root / "head-key-epoch.json"
        self.anchor_path = self.trust_root / "monotonic-high-water.json"
        self.key_history_root = self.trust_root / "key-history"
        self.phase_a_digest = "9" * 64
        self.phase_a_task_id = "phase-a-task-1"
        self.private_key = Ed25519PrivateKey.generate()
        self.fingerprint = self._install_public_key()
        self.stack.enter_context(
            patch.multiple(
                external,
                TRUST_ROOT=self.trust_root,
                TRUST_ANCHOR=self.root,
                PUBLIC_KEY_PATH=self.trust_root / "ed25519-public.pem",
                FINGERPRINT_PATH=self.trust_root / "ed25519-public.sha256",
                KEY_HISTORY_ROOT=self.key_history_root,
                HEAD_KEY_EPOCH_PATH=self.epoch_path,
                MONOTONIC_ANCHOR_PATH=self.anchor_path,
                IMPORT_LOCK_PATH=self.lock_path,
                SQLITE_META_PATH=self.db_path,
                TRUSTED_OWNER_UIDS=frozenset({os.getuid()}),
            )
        )
        self.stack.enter_context(patch.object(storage_service, "SQLITE_META_PATH", self.db_path))
        self.stack.enter_context(patch.object(storage_service, "PARQUET_ROOT", self.root / "parquet"))

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

    def _replace_public_key(self, private_key: Ed25519PrivateKey) -> str:
        public_key = private_key.public_key()
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
        self.trust_root.chmod(0o755)
        key_path.unlink()
        fingerprint_path.unlink()
        key_path.write_bytes(pem)
        fingerprint_path.write_text(fingerprint + "\n", encoding="ascii")
        key_path.chmod(0o444)
        fingerprint_path.chmod(0o444)
        self.trust_root.chmod(0o555)
        return fingerprint

    def _install_history_key(
        self,
        *,
        epoch: int,
        private_key: Ed25519PrivateKey,
        fingerprint: str,
    ) -> None:
        pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.trust_root.chmod(0o755)
        self.key_history_root.mkdir(mode=0o755, exist_ok=True)
        path = self.key_history_root / f"{epoch:08d}-{fingerprint}.pem"
        path.write_bytes(pem)
        path.chmod(0o444)
        self.key_history_root.chmod(0o555)
        self.trust_root.chmod(0o555)

    def _install_phase_a(self) -> dict:
        packet = {
            "schema_version": storage_service.STORAGE_PHASE_A_PACKET_SCHEMA_VERSION,
            "packet_key": storage_service.STORAGE_PHYSICAL_EXECUTION_PHASE_A_PACKET_KEY,
            "head_full": external._current_head_full(),
            "task_id": self.phase_a_task_id,
            "status": "storage_physical_execution_phase_a_v04_durable_execution_success",
            "phase_a_local_evidence_done": True,
            "physical_task_created": True,
            "physical_task_executed": True,
            "v04_durable_storage_executed": True,
            "v04_duckdb_query_parity": True,
            "v04_sqlite_readback_verified": True,
            "v04_atomic_current_promoted": True,
            "production_storage_complete": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
        self.phase_a_digest = storage_service._external_packet_digest(packet)
        SQLiteMetaStore(self.db_path).write_packet(
            storage_service.STORAGE_PHYSICAL_EXECUTION_PHASE_A_PACKET_KEY,
            packet,
        )
        return packet

    def _attestation_id(self, envelope: dict) -> str:
        signature = base64.b64decode(envelope["signature_base64"])
        return external._sha256(
            {
                "statement": envelope["statement"],
                "key_fingerprint_sha256": envelope["key_fingerprint_sha256"],
                "signature_sha256": hashlib.sha256(signature).hexdigest(),
            }
        )

    def _install_external_proof(
        self,
        envelope: dict,
        *,
        epoch_number: int = 1,
        proof_key: Ed25519PrivateKey | None = None,
        fingerprint: str | None = None,
        epoch_head: str | None = None,
        previous_epoch_digest: str | None = None,
    ) -> tuple[dict, dict]:
        signing_key = proof_key or self.private_key
        resolved_fingerprint = fingerprint or self.fingerprint
        now = datetime.now(timezone.utc)
        existing_epoch = (
            json.loads(self.epoch_path.read_text(encoding="utf-8"))
            if self.epoch_path.exists()
            else {}
        )
        reuse_epoch = bool(
            proof_key is None
            and fingerprint is None
            and epoch_head is None
            and existing_epoch.get("epoch") == epoch_number
            and existing_epoch.get("head_full") == envelope["statement"]["head_full"]
            and existing_epoch.get("key_fingerprint_sha256") == resolved_fingerprint
        )
        if reuse_epoch:
            epoch = existing_epoch
        else:
            epoch = {
                "schema_version": external.HEAD_KEY_EPOCH_SCHEMA_VERSION,
                "algorithm": "Ed25519",
                "epoch": epoch_number,
                "head_full": epoch_head or envelope["statement"]["head_full"],
                "key_fingerprint_sha256": resolved_fingerprint,
                "valid_from": (now - timedelta(minutes=1)).isoformat(),
                "expires_at": (now + timedelta(days=1)).isoformat(),
                "nonce_digest": hashlib.sha256(f"epoch:{epoch_number}".encode()).hexdigest(),
                "previous_epoch_digest": (
                    "0" * 64
                    if epoch_number == 1
                    else previous_epoch_digest or "a" * 64
                ),
            }
            epoch["signature_base64"] = base64.b64encode(
                signing_key.sign(external._canonical_bytes(epoch))
            ).decode("ascii")
        epoch_digest = external._sha256(external._signed_document_material(epoch))
        statement = envelope["statement"]
        anchor = {
            "schema_version": external.MONOTONIC_ANCHOR_SCHEMA_VERSION,
            "algorithm": "Ed25519",
            "epoch": epoch_number,
            "head_full": statement["head_full"],
            "key_fingerprint_sha256": resolved_fingerprint,
            "epoch_digest": epoch_digest,
            "monotonic_counter": statement["monotonic_counter"],
            "cas_previous_counter": statement["monotonic_counter"] - 1,
            "previous_attestation_digest": statement["previous_attestation_digest"],
            "cas_previous_attestation_digest": statement["previous_attestation_digest"],
            "attestation_id": self._attestation_id(envelope),
            "nonce_digest": statement["nonce_digest"],
            "issued_at": statement["issued_at"],
            "expires_at": statement["expires_at"],
        }
        anchor["signature_base64"] = base64.b64encode(
            signing_key.sign(external._canonical_bytes(anchor))
        ).decode("ascii")
        self.trust_root.chmod(0o755)
        if self.epoch_path.exists():
            self.epoch_path.unlink()
        if self.anchor_path.exists():
            self.anchor_path.unlink()
        self.epoch_path.write_text(json.dumps(epoch), encoding="utf-8")
        self.anchor_path.write_text(json.dumps(anchor), encoding="utf-8")
        self.epoch_path.chmod(0o444)
        self.anchor_path.chmod(0o444)
        self.trust_root.chmod(0o555)
        return epoch, anchor

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
                "fetched_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
                "phase_a_packet_digest": self.phase_a_digest,
                "phase_a_task_id": self.phase_a_task_id,
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
                "result_dataset": "full_market_factor_research_results",
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
        fingerprint: str | None = None,
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
            "key_fingerprint_sha256": fingerprint or self.fingerprint,
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

    def test_idempotent_replay_still_requires_exact_valid_envelope(self) -> None:
        signed = self._envelope("worker_runtime_lineage", "worker-run-1", 1, "")
        imported = self._import(signed)
        self.assertTrue(imported["local_integrity_ready"])

        attacks = []
        for field, value in (("schema_version", "evil.v1"), ("algorithm", "RSA")):
            attack = {**signed, "statement": dict(signed["statement"])}
            attack[field] = value
            attacks.append(attack)
        extra = {**signed, "statement": dict(signed["statement"]), "production": True}
        attacks.append(extra)

        for attack in attacks:
            with self.subTest(keys=sorted(attack), algorithm=attack.get("algorithm")):
                rejected = self._import(attack)
                self.assertFalse(rejected["local_integrity_ready"])
                self.assertFalse(rejected["writes_performed"])
        registry = external.validate_registry()
        self.assertTrue(registry["local_integrity_ready"])
        self.assertEqual(registry["event_count"], 1)

    def test_storage_ttl_timestamp_semantics_are_bounded_by_resolution(self) -> None:
        now = datetime.now(timezone.utc)
        ancient = self._claims("storage_ttl_resolution", "daily")
        ancient["fetched_at"] = "2000-01-01T00:00:00+00:00"
        rejected = self._import(
            self._envelope("storage_ttl_resolution", "daily", 1, "", claims=ancient)
        )
        self.assertFalse(rejected["local_integrity_ready"])
        self.assertEqual(rejected["status"], "signed_statement_contract_invalid")

        within_ttl = self._claims("storage_ttl_resolution", "factor_values")
        within_ttl["fetched_at"] = (now - timedelta(hours=5)).isoformat()
        accepted = self._import(
            self._envelope(
                "storage_ttl_resolution", "factor_values", 1, "", claims=within_ttl
            )
        )
        self.assertTrue(accepted["local_integrity_ready"])

        refreshed = self._claims("storage_ttl_resolution", "daily")
        refreshed.update(
            {
                "resolution": "refreshed",
                "refresh_task_id": "refresh-daily-v2",
                "before_ttl_state": "stale",
                "after_ttl_state": "fresh",
                "refresh_executed": True,
                "provider_call_count": 1,
                "fetched_at": (now - timedelta(minutes=16)).isoformat(),
                "external_calls_triggered": True,
            }
        )
        stale_refresh = self._import(
            self._envelope(
                "storage_ttl_resolution",
                "daily",
                2,
                accepted["attestation_id"],
                claims=refreshed,
            )
        )
        self.assertFalse(stale_refresh["local_integrity_ready"])
        self.assertEqual(stale_refresh["status"], "signed_statement_contract_invalid")

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
        registry = external.validate_registry()
        self.assertFalse(registry["production_trusted"])
        self.assertFalse(registry["external_trust_verified"])
        self.assertFalse(registry["snapshot_rollback_resistant"])
        self.assertEqual(registry["blockers"], list(external.PRODUCTION_TRUST_BLOCKERS))
        unchanged = store.read_packet(external.REGISTRY_PACKET_KEY)
        self.assertEqual(unchanged["events"][0]["attestation_id"], "0" * 64)
        self.assertEqual(len(unchanged["events"]), 1)

    def test_storage_six_dataset_consumer_is_atomic_and_production_trusted(self) -> None:
        phase_a = self._install_phase_a()
        previous = ""
        for counter, dataset in enumerate(storage_service.CANONICAL_PARQUET_DATASETS, start=1):
            signed = self._envelope(
                "storage_ttl_resolution",
                dataset,
                counter,
                previous,
            )
            self._install_external_proof(signed)
            result = storage_service.import_storage_cache_ttl_external_attestation(
                {"signed_envelope": signed}
            )
            self.assertTrue(result["consumer_readback_verified"])
            self.assertTrue(result["snapshot_rollback_resistant"])
            self.assertFalse(result["pointers_written"])
            self.assertEqual(result["ready"], counter == len(storage_service.CANONICAL_PARQUET_DATASETS))
            previous = result["attestation_id"]

        validation = storage_service.storage_cache_ttl_refresh_evidence()
        self.assertTrue(validation["production_ttl_evidence_ready"])
        self.assertTrue(validation["production_trust_boundary_satisfied"])
        self.assertTrue(validation["snapshot_rollback_resistant"])
        self.assertTrue(validation["production_storage_complete"])
        fact = storage_service.validate_storage_production_fact(
            phase_a,
            expected_head_full=external._current_head_full(),
        )
        self.assertTrue(fact["ready"])
        self.assertTrue(fact["production_storage_complete"])
        self.assertTrue(fact["trusted_external_production_validator_ready"])
        self.assertIsNone(
            SQLiteMetaStore(self.db_path).read_packet(
                storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY
            )
        )

    def test_storage_pair_post_commit_exception_reconciles_production_truth(self) -> None:
        self._install_phase_a()
        previous = ""
        datasets = list(storage_service.CANONICAL_PARQUET_DATASETS)
        original_promote = SQLiteMetaStore.promote_packet_pair_atomic
        result: dict = {}
        for counter, dataset in enumerate(datasets, start=1):
            signed = self._envelope(
                "storage_ttl_resolution",
                dataset,
                counter,
                previous,
            )
            self._install_external_proof(signed)
            if counter == len(datasets):
                def commit_then_raise(store: SQLiteMetaStore, *args: object) -> dict:
                    original_promote(store, *args)
                    raise RuntimeError("injected_post_commit_pair_failure")

                with patch.object(
                    SQLiteMetaStore,
                    "promote_packet_pair_atomic",
                    new=commit_then_raise,
                ):
                    result = storage_service.import_storage_cache_ttl_external_attestation(
                        {"signed_envelope": signed}
                    )
            else:
                result = storage_service.import_storage_cache_ttl_external_attestation(
                    {"signed_envelope": signed}
                )
            previous = result["attestation_id"]

        self.assertTrue(result["ready"], result)
        self.assertTrue(result["production_trusted"])
        self.assertTrue(result["production_storage_complete"])
        self.assertTrue(result["writes_performed"])
        self.assertTrue(result["post_commit_exception_reconciled"])
        validation = storage_service.storage_cache_ttl_refresh_evidence()
        self.assertTrue(validation["production_storage_complete"])
        self.assertTrue(validation["production_trusted"])

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
        self.assertEqual(contract["production_consumers_wired"], ["storage_ttl"])
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

    def test_external_high_water_detects_registry_rollback_and_replay(self) -> None:
        phase_a = self._install_phase_a()
        first_envelope = self._envelope("storage_ttl_resolution", "daily", 1, "")
        self._install_external_proof(first_envelope)
        first = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": first_envelope}
        )
        store = SQLiteMetaStore(self.db_path)
        first_registry = store.read_packet(external.REGISTRY_PACKET_KEY)

        second_envelope = self._envelope(
            "storage_ttl_resolution",
            "daily_basic",
            2,
            first["attestation_id"],
        )
        self._install_external_proof(second_envelope)
        second = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": second_envelope}
        )
        self.assertTrue(second["consumer_readback_verified"])
        store.write_packet(external.REGISTRY_PACKET_KEY, first_registry)

        trusted = external.validate_trusted_registry()
        self.assertFalse(trusted["ready"])
        self.assertFalse(trusted["production_trusted"])
        fact = storage_service.validate_storage_production_fact(
            phase_a,
            expected_head_full=external._current_head_full(),
        )
        self.assertFalse(fact["ready"])
        replay = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": first_envelope}
        )
        self.assertFalse(replay["ready"])
        self.assertFalse(replay["storage_packet_written"])

    def test_epoch_rotation_and_wrong_head_proofs_fail_before_write(self) -> None:
        self._install_phase_a()
        envelope = self._envelope("storage_ttl_resolution", "daily", 1, "")
        self._install_external_proof(envelope, epoch_head="0" * 40)
        wrong_head_epoch = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": envelope}
        )
        self.assertFalse(wrong_head_epoch["ready"])
        self.assertEqual(wrong_head_epoch["status"], "trusted_head_key_epoch_invalid")

        self._install_external_proof(envelope)
        first = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": envelope}
        )
        self.assertTrue(first["consumer_readback_verified"])

        rotated_envelope = self._envelope(
            "storage_ttl_resolution",
            "daily_basic",
            2,
            first["attestation_id"],
        )
        self._install_external_proof(rotated_envelope, epoch_number=2)
        broken_epoch_chain = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": rotated_envelope}
        )
        self.assertFalse(broken_epoch_chain["ready"])
        self.assertEqual(broken_epoch_chain["status"], "trusted_head_key_epoch_invalid")

        rotated_key = Ed25519PrivateKey.generate()
        rotated_der = rotated_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self._install_external_proof(
            rotated_envelope,
            epoch_number=2,
            proof_key=rotated_key,
            fingerprint=hashlib.sha256(rotated_der).hexdigest(),
        )
        wrong_rotation = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": rotated_envelope}
        )
        self.assertFalse(wrong_rotation["ready"])
        self.assertEqual(wrong_rotation["status"], "trusted_head_key_epoch_invalid")
        registry = SQLiteMetaStore(self.db_path).read_packet(external.REGISTRY_PACKET_KEY)
        self.assertEqual(registry["last_attestation_id"], first["attestation_id"])
        self.assertEqual(registry["last_monotonic_counter"], 1)

    def test_trusted_key_history_allows_exact_epoch_key_rotation(self) -> None:
        self._install_phase_a()
        first_envelope = self._envelope("storage_ttl_resolution", "daily", 1, "")
        self._install_external_proof(first_envelope)
        first = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": first_envelope}
        )
        self.assertTrue(first["consumer_readback_verified"])
        first_registry = SQLiteMetaStore(self.db_path).read_packet(external.REGISTRY_PACKET_KEY)
        first_epoch_digest = first_registry["events"][0]["head_key_epoch_digest"]

        old_key = self.private_key
        old_fingerprint = self.fingerprint
        rotated_key = Ed25519PrivateKey.generate()
        rotated_fingerprint = self._replace_public_key(rotated_key)
        missing_history = external.validate_registry()
        self.assertFalse(missing_history["local_integrity_ready"])
        self._install_history_key(
            epoch=1,
            private_key=old_key,
            fingerprint=old_fingerprint,
        )
        second_envelope = self._envelope(
            "storage_ttl_resolution",
            "daily_basic",
            2,
            first["attestation_id"],
            private_key=rotated_key,
            fingerprint=rotated_fingerprint,
        )
        self._install_external_proof(
            second_envelope,
            epoch_number=2,
            proof_key=rotated_key,
            fingerprint=rotated_fingerprint,
            previous_epoch_digest=first_epoch_digest,
        )
        second = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": second_envelope}
        )
        self.assertTrue(second["consumer_readback_verified"], second)
        registry = external.validate_registry()
        self.assertTrue(registry["local_integrity_ready"])
        self.assertEqual(registry["event_count"], 2)
        self.assertEqual(registry["events"][0]["key_fingerprint_sha256"], old_fingerprint)
        self.assertEqual(
            registry["events"][1]["key_fingerprint_sha256"],
            rotated_fingerprint,
        )

    def test_registry_atomic_write_failure_leaves_registry_consumer_and_pointer_unchanged(self) -> None:
        self._install_phase_a()
        store = SQLiteMetaStore(self.db_path)
        pointer = storage_service.PARQUET_ROOT / "daily" / "current.json"
        pointer.parent.mkdir(parents=True)
        pointer.write_text('{"sentinel":true}', encoding="utf-8")
        envelope = self._envelope("storage_ttl_resolution", "daily", 1, "")
        self._install_external_proof(envelope)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TRIGGER fail_second_packet_insert
                BEFORE INSERT ON packets
                WHEN NEW.packet_key = 'command_center_3_storage_ttl_production_consumer'
                BEGIN
                    SELECT RAISE(ABORT, 'injected_second_packet_write_failure');
                END
                """
            )
        result = storage_service.import_storage_cache_ttl_external_attestation(
            {"signed_envelope": envelope}
        )
        self.assertFalse(result["ready"])
        self.assertFalse(result["writes_performed"])
        self.assertEqual(result["status"], "storage_ttl_registry_consumer_atomic_write_failed")
        self.assertIsNone(store.read_packet(external.REGISTRY_PACKET_KEY))
        self.assertIsNone(
            store.read_packet(storage_service.STORAGE_TTL_PRODUCTION_CONSUMER_PACKET_KEY)
        )
        self.assertEqual(pointer.read_text(encoding="utf-8"), '{"sentinel":true}')

    def test_post_commit_exception_is_reconciled_and_retry_is_idempotent(self) -> None:
        signed = self._envelope("worker_runtime_lineage", "worker-run-retry", 1, "")
        original_promote = SQLiteMetaStore.promote_packet_atomic

        def commit_then_raise(store: SQLiteMetaStore, packet_key: str, packet: dict) -> dict:
            original_promote(store, packet_key, packet)
            raise RuntimeError("injected_post_commit_failure")

        with patch.object(
            external.SQLiteMetaStore,
            "promote_packet_atomic",
            new=commit_then_raise,
        ):
            first = self._import(signed)
        self.assertTrue(first["writes_performed"])
        self.assertTrue(first["local_integrity_ready"])
        self.assertEqual(
            first["status"],
            "external_attestation_imported_after_write_exception_reconciled",
        )

        replay = self._import(signed)
        self.assertTrue(replay["local_integrity_ready"])
        self.assertFalse(replay["writes_performed"])
        self.assertEqual(
            replay["status"],
            "external_attestation_already_imported_local_integrity_only",
        )
        registry = external.validate_registry()
        self.assertTrue(registry["local_integrity_ready"])
        self.assertEqual(registry["event_count"], 1)
        self.assertEqual(registry["last_monotonic_counter"], 1)
        self.assertFalse(registry["production_trusted"])

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
