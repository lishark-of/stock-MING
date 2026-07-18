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
from server.services import external_production_consumer_service as phase2_consumers
from server.services import full_market_worker_service
from server.services import storage_service
from server.services import tushare_task_service
from server.services import tushare_production_store
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
        self.stack.enter_context(
            patch.object(
                external,
                "_current_clean_head_full",
                return_value=external._current_head_full(),
            )
        )
        self.stack.enter_context(patch.object(storage_service, "SQLITE_META_PATH", self.db_path))
        self.stack.enter_context(
            patch.object(tushare_production_store, "SQLITE_META_PATH", self.db_path)
        )
        self.stack.enter_context(patch.object(storage_service, "PARQUET_ROOT", self.root / "parquet"))
        self.stack.enter_context(
            patch.multiple(
                phase2_consumers,
                EVIDENCE_ROOT=self.root,
                SQLITE_META_PATH=self.db_path,
                PARQUET_ROOT=self.root / "parquet",
            )
        )

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
        storage_service.PARQUET_ROOT.mkdir(parents=True, exist_ok=True)
        for dataset in storage_service.CANONICAL_PARQUET_DATASETS:
            path = storage_service.parquet_store.dataset_path(
                root=storage_service.PARQUET_ROOT,
                name=dataset,
            )
            if not path.exists():
                path.write_bytes(f"physical:{dataset}:v1".encode("utf-8"))
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

    def _install_phase2_source(
        self,
        consumer: str,
        *,
        wrong_dataset: bool = False,
        generation_number: int = 1,
    ) -> dict:
        generation = (
            f"worker-generation-{generation_number}"
            if consumer == "radar"
            else f"{consumer}-generation-{generation_number}"
        )
        dataset = (
            full_market_worker_service.FACTOR_RESULT_DATASET
            if consumer == "factor"
            else full_market_worker_service.RESULT_DATASET
        )
        config = phase2_consumers._CONFIG[consumer]
        store = SQLiteMetaStore(self.db_path)
        previous_packet = store.read_packet(config["current_key"]) or {}
        pointer_root = self.root / "parquet" / dataset
        previous_pointer = (
            json.loads((pointer_root / "current.json").read_text(encoding="utf-8"))
            if previous_packet and (pointer_root / "current.json").is_file()
            else {}
        )
        artifact = self.root / "parquet" / dataset / "versions" / f"{generation}.parquet"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(
            f"{'worker' if consumer == 'radar' else consumer}:{generation}:immutable-artifact".encode(
                "utf-8"
            )
        )
        artifact_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        pointer = {
            "schema_version": "stock_ming_versioned_parquet_pointer.v1",
            "dataset": dataset,
            "version_id": generation,
            "artifact_relpath": str(artifact.relative_to(self.root / "parquet")),
            "artifact_sha256": artifact_digest,
            "row_count": 3000 if consumer == "factor" else 8,
            "columns": ["ts_code"],
            "lineage": {"generation": generation},
            "contains_secret": False,
        }
        (pointer_root / "current.json").write_text(json.dumps(pointer), encoding="utf-8")
        (pointer_root / "last_good.json").write_text(
            json.dumps(
                {
                    **(previous_pointer or pointer),
                    "pointer_kind": "last_good",
                }
            ),
            encoding="utf-8",
        )
        scope_hash = hashlib.sha256(f"scope:{consumer}".encode()).hexdigest()
        run_id = f"{consumer}-run-{generation_number}"
        if consumer == "worker":
            packet = {
                "acceptance_run_id": run_id,
                "provider_scope_hash": scope_hash,
                "provider_version_digest": "8" * 64,
                "universe_digest": "9" * 64,
                "validated_trade_date": "20260710",
                "result_dataset": "wrong_dataset" if wrong_dataset else dataset,
                "result_version_id": generation,
                "result_artifact_sha256": artifact_digest,
                "result_row_count": 8,
                "transport_attestation_digest": "1" * 64,
                "celery_task_ids": ["celery-1", "celery-2"],
                "worker_task_ids": ["worker-1", "worker-2"],
                "batch_count": 2,
                "production_worker_complete": True,
            }
        elif consumer == "factor":
            packet = {
                "acceptance_run_id": run_id,
                "provider_scope_hash": scope_hash,
                "result_dataset": "wrong_dataset" if wrong_dataset else dataset,
                "result_version_id": generation,
                "result_artifact_sha256": artifact_digest,
                "universe_digest": "2" * 64,
                "universe_count": 3000,
                "neutralization_audit_digest": "3" * 64,
                "full_market_factor_research": True,
            }
        else:
            request_bundle_id = hashlib.sha256(
                f"radar-request:{generation}".encode()
            ).hexdigest()
            bundle_digest = hashlib.sha256(
                f"radar-bundle:{generation}".encode()
            ).hexdigest()
            source_output_hash = hashlib.sha256(
                f"radar-output:{generation}".encode()
            ).hexdigest()
            candidate_rows_digest = hashlib.sha256(
                f"radar-rows:{generation}".encode()
            ).hexdigest()
            binding = {
                "cache_write_task_id": "radar-cache-write-1",
                "acceptance_run_id": run_id,
                "source_result_dataset": "wrong_dataset" if wrong_dataset else dataset,
                "source_result_version_id": generation,
                "source_result_artifact_sha256": artifact_digest,
                "source_result_output_hash": source_output_hash,
                "universe_digest": "4" * 64,
                "candidate_row_count": 8,
                "candidate_rows_digest": candidate_rows_digest,
                "browser_visual_evidence_digest": "5" * 64,
                "browser_performance_evidence_digest": "6" * 64,
                "legacy_retirement_evidence_digest": "7" * 64,
            }
            binding["binding_digest"] = phase2_consumers._digest(binding)
            packet = {
                "packet_key": "command_center_3_candidate_radar_cache",
                "head_full": external._current_head_full(),
                "request_bundle_id": request_bundle_id,
                "bundle_digest": bundle_digest,
                "full_market_worker_replacement": binding,
            }
            task = {
                "task_id": binding["cache_write_task_id"],
                "task_type": "publish_candidate_radar_full_market_cache",
                "status": "success",
                "progress": 1.0,
                "output_packet_key": "command_center_3_candidate_radar_cache",
                "acceptance_run_id": run_id,
                "source_result_version_id": generation,
                "source_result_output_hash": source_output_hash,
                "candidate_rows_digest": candidate_rows_digest,
                "payload_safe": {
                    "request_bundle_id": request_bundle_id,
                    "bundle_digest": bundle_digest,
                    "head_full": external._current_head_full(),
                    "source_result_version_id": generation,
                },
                "global_candidate_cache_overwritten": True,
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
            }
            task["task_binding_digest"] = phase2_consumers._digest(task)
            store.write_task_status(task)
        store.write_packet(config["current_key"], packet)
        store.write_packet(
            config["source_last_good_key"],
            dict(previous_packet or packet),
        )
        return phase2_consumers.build_consumer_attestation_material(consumer)

    def _phase2_envelope(
        self,
        consumer: str,
        counter: int,
        previous: str,
        *,
        head_full: str | None = None,
    ) -> dict:
        material = phase2_consumers.build_consumer_attestation_material(consumer)
        envelope = self._envelope(
            str(material["attestation_kind"]),
            str(material["subject"]),
            counter,
            previous,
            claims=dict(material["claims"]),
            head_full=head_full,
        )
        envelope["statement"].update(
            {
                "task_id": material["task_id"],
                "scope_hash": material["scope_hash"],
                "artifact_digest": material["artifact_digest"],
            }
        )
        return self._resign(envelope)

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
                "provider_version_digest": "8" * 64,
                "universe_digest": "9" * 64,
                "validated_trade_date": "20260710",
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
        if kind == "tushare_provider_execution_authorization":
            return {
                "approval_scope_hash": "a" * 64,
                "execution_recipe_scope_hash": "b" * 64,
                "selected_api_digest": "c" * 64,
                "target_group_digest": "d" * 64,
                "provider_attempt_id": "1" * 32,
                "provider_version_id": f"{'b' * 16}-{'1' * 32}",
                "trade_cal_repeat_authorized": True,
                "provider_max_calls": 271,
                "does_not_execute_trades": True,
            }
        return {
            "candidate_cache_packet_key": "command_center_3_candidate_radar_cache",
            "cache_write_task_id": "candidate-cache-write-1",
            "candidate_cache_write_task_digest": "9" * 64,
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
        physical = (
            storage_service._storage_dataset_physical_binding(subject)
            if kind == "storage_ttl_resolution"
            else {}
        )
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
            "artifact_digest": (
                str(physical["artifact_digest"])
                if physical.get("ready") is True
                else hashlib.sha256(f"artifact:{kind}:{subject}".encode("utf-8")).hexdigest()
            ),
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
        SQLiteMetaStore(self.db_path).write_packet(
            storage_service.CACHE_TTL_REFRESH_EVIDENCE_PACKET_KEY,
            {
                "schema_version": storage_service.CACHE_TTL_REFRESH_EVIDENCE_SCHEMA_VERSION,
                "head_full": "0" * 40,
                "rows": [],
            },
        )
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
            progress = storage_service.storage_cache_ttl_refresh_evidence()
            self.assertEqual(progress["production_verified_dataset_count"], counter)
            self.assertEqual(
                progress["production_unresolved"],
                storage_service.CANONICAL_PARQUET_DATASETS[counter:],
            )
            self.assertEqual(progress["ready"], counter == len(storage_service.CANONICAL_PARQUET_DATASETS))

        validation = storage_service.storage_cache_ttl_refresh_evidence()
        self.assertTrue(validation["ready"])
        self.assertEqual(validation["production_verified_dataset_count"], 6)
        self.assertEqual(validation["production_unresolved"], [])
        self.assertEqual(validation["verified_dataset_count"], 0)
        self.assertEqual(
            validation["unresolved_datasets"],
            storage_service.CANONICAL_PARQUET_DATASETS,
        )
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
        audit = storage_service.storage_production_blocker_audit()
        ttl_row = next(
            row for row in audit["rows"] if row["criterion"] == "cache_ttl_refresh_pipeline_executed"
        )
        self.assertTrue(ttl_row["passed"])
        self.assertFalse(ttl_row["production_blocker"])
        self.assertEqual(audit["cache_ttl_production_verified_dataset_count"], 6)
        self.assertEqual(audit["cache_ttl_production_unresolved"], [])

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
        self.assertTrue(validation["ready"])
        self.assertEqual(validation["production_verified_dataset_count"], 6)
        self.assertEqual(validation["production_unresolved"], [])
        self.assertTrue(validation["production_storage_complete"])
        self.assertTrue(validation["production_trusted"])

    def test_tushare_replacement_invalidates_physical_attestations_until_reattested(self) -> None:
        self._install_phase_a()
        previous = ""
        counter = 0
        for dataset in storage_service.CANONICAL_PARQUET_DATASETS:
            counter += 1
            signed = self._envelope("storage_ttl_resolution", dataset, counter, previous)
            self._install_external_proof(signed)
            result = storage_service.import_storage_cache_ttl_external_attestation(
                {"signed_envelope": signed}
            )
            previous = result["attestation_id"]
        self.assertTrue(storage_service.storage_cache_ttl_refresh_evidence()["ready"])

        store = SQLiteMetaStore(self.db_path)
        exact_consumer = store.read_packet(
            storage_service.STORAGE_TTL_PRODUCTION_CONSUMER_PACKET_KEY
        )
        mismatched_consumer = json.loads(json.dumps(exact_consumer))
        mismatched_consumer["rows"][0]["physical_pointer_digest"] = "0" * 64
        store.write_packet(
            storage_service.STORAGE_TTL_PRODUCTION_CONSUMER_PACKET_KEY,
            mismatched_consumer,
        )
        mismatched = storage_service.storage_cache_ttl_refresh_evidence()
        self.assertFalse(mismatched["ready"])
        self.assertEqual(mismatched["production_verified_dataset_count"], 5)
        self.assertEqual(mismatched["production_unresolved"], ["factor_values"])
        store.write_packet(
            storage_service.STORAGE_TTL_PRODUCTION_CONSUMER_PACKET_KEY,
            exact_consumer,
        )

        ledger: list[dict] = []
        staging_root = self.root / "tushare-staging"
        staging_root.mkdir()
        for api, dataset in tushare_task_service.PARQUET_DATASETS.items():
            staging = staging_root / f"{dataset}.parquet"
            staging.write_bytes(f"tushare:{dataset}:v2".encode("utf-8"))
            ledger.append(
                {
                    "api": api,
                    "parquet_status": "staged",
                    "parquet_staging_path": str(staging),
                    "parquet_staging_digest": hashlib.sha256(staging.read_bytes()).hexdigest(),
                    "parquet_row_count": 1,
                }
            )
        promotion = tushare_task_service._promote_staged_parquet_datasets(
            ledger,
            scope_hash="b" * 64,
        )
        self.assertTrue(promotion["promotion_verified"], promotion)
        self.assertEqual(promotion["promoted_dataset_count"], 4)

        invalidated = storage_service.storage_cache_ttl_refresh_evidence()
        self.assertFalse(invalidated["ready"])
        self.assertFalse(invalidated["production_storage_complete"])
        self.assertEqual(invalidated["production_verified_dataset_count"], 2)
        self.assertEqual(
            invalidated["production_unresolved"],
            ["daily", "daily_basic", "moneyflow", "trade_cal"],
        )
        audit = storage_service.storage_production_blocker_audit()
        ttl_row = next(
            row for row in audit["rows"] if row["criterion"] == "cache_ttl_refresh_pipeline_executed"
        )
        self.assertFalse(ttl_row["passed"])
        self.assertTrue(ttl_row["production_blocker"])

        for dataset in ("daily", "daily_basic", "moneyflow", "trade_cal"):
            counter += 1
            signed = self._envelope("storage_ttl_resolution", dataset, counter, previous)
            self._install_external_proof(signed)
            result = storage_service.import_storage_cache_ttl_external_attestation(
                {"signed_envelope": signed}
            )
            previous = result["attestation_id"]
        reattested = storage_service.storage_cache_ttl_refresh_evidence()
        self.assertTrue(reattested["ready"])
        self.assertEqual(reattested["production_verified_dataset_count"], 6)
        self.assertEqual(reattested["production_unresolved"], [])

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
            [
                "storage",
                "worker",
                "factor",
                "candidate_radar",
                "tushare_provider_execution_authorization",
            ],
        )
        self.assertEqual(
            contract["production_consumers_wired"],
            ["storage_ttl", "tushare_provider_execution_authorization"],
        )
        self.assertFalse(contract["application_generates_private_key"])
        self.assertTrue(contract["caller_boolean_cannot_promote"])

    def test_tushare_provider_authorization_requires_external_trust_and_repeat_claim(self) -> None:
        subject = "tushare-full-interface-provider-execution"
        signed = self._envelope(
            "tushare_provider_execution_authorization",
            subject,
            1,
            "",
        )
        self._install_external_proof(signed)
        prepared = external.prepare_external_trusted_attestation(
            {"signed_envelope": signed},
            expected_kind="tushare_provider_execution_authorization",
        )
        self.assertTrue(prepared["ready"], prepared)
        self.assertTrue(prepared["production_trusted"])
        self.assertTrue(prepared["snapshot_rollback_resistant"])
        self.assertTrue(prepared["claims"]["trade_cal_repeat_authorized"])

    def test_tushare_provider_authorization_is_exact_bound_and_consumed_once(self) -> None:
        head = external._current_head_full()
        approval_scope = "a" * 64
        recipe_scope = "b" * 64
        execution_request_id = f"tushare-provider-request-{approval_scope[:32]}"
        selected_apis = list(tushare_task_service.ALL_REFRESH_APIS)
        requested_targets = list(
            tushare_task_service.FULL_INTERFACE_PROVIDER_PRODUCTION_TARGETS
        )
        claims = {
            "approval_scope_hash": approval_scope,
            "execution_recipe_scope_hash": recipe_scope,
            "selected_api_digest": tushare_task_service._canonical_sha256(
                sorted(selected_apis)
            ),
            "target_group_digest": tushare_task_service._canonical_sha256(
                sorted(requested_targets)
            ),
            "provider_attempt_id": "1" * 32,
            "provider_version_id": f"{recipe_scope[:16]}-{'1' * 32}",
            "trade_cal_repeat_authorized": True,
            "provider_max_calls": 271,
            "does_not_execute_trades": True,
        }
        signed = self._envelope(
            "tushare_provider_execution_authorization",
            "tushare-full-interface-provider-execution",
            1,
            "",
            claims=claims,
            head_full=head,
        )
        signed["statement"]["scope_hash"] = approval_scope
        signed["statement"]["artifact_digest"] = recipe_scope
        signed["statement"]["task_id"] = execution_request_id
        signed["signature_base64"] = base64.b64encode(
            self.private_key.sign(external._canonical_bytes(signed["statement"]))
        ).decode("ascii")
        self._install_external_proof(signed)
        with patch.multiple(
            tushare_task_service,
            SQLITE_META_PATH=self.db_path,
        ):
            mismatched = tushare_task_service._consume_trusted_provider_execution_authorization(
                {"signed_provider_execution_authorization": signed},
                producer_head_full=head,
                execution_request_authorization_id=execution_request_id,
                approval_scope_hash=approval_scope,
                execution_recipe_scope_hash=recipe_scope,
                selected_apis=selected_apis,
                requested_targets=requested_targets,
                max_provider_calls=270,
                provider_attempt_id=claims["provider_attempt_id"],
                provider_version_id=claims["provider_version_id"],
            )
            first = tushare_task_service._consume_trusted_provider_execution_authorization(
                {"signed_provider_execution_authorization": signed},
                producer_head_full=head,
                execution_request_authorization_id=execution_request_id,
                approval_scope_hash=approval_scope,
                execution_recipe_scope_hash=recipe_scope,
                selected_apis=selected_apis,
                requested_targets=requested_targets,
                max_provider_calls=271,
                provider_attempt_id=claims["provider_attempt_id"],
                provider_version_id=claims["provider_version_id"],
            )
            second = tushare_task_service._consume_trusted_provider_execution_authorization(
                {"signed_provider_execution_authorization": signed},
                producer_head_full=head,
                execution_request_authorization_id=execution_request_id,
                approval_scope_hash=approval_scope,
                execution_recipe_scope_hash=recipe_scope,
                selected_apis=selected_apis,
                requested_targets=requested_targets,
                max_provider_calls=271,
                provider_attempt_id=claims["provider_attempt_id"],
                provider_version_id=claims["provider_version_id"],
            )
        self.assertFalse(mismatched["ready"])
        self.assertFalse(mismatched["writes_performed"])
        self.assertTrue(first["ready"], first)
        self.assertTrue(first["production_trusted"])
        self.assertFalse(second["ready"])
        self.assertFalse(second["writes_performed"])
        receipt = {
            "provider_execution_authorization_attestation_id": first[
                "attestation_id"
            ],
            "provider_execution_authorization_nonce_digest": first[
                "authorization_nonce_digest"
            ],
            "provider_execution_authorization_task_id": execution_request_id,
            "producer_head_full": head,
            "approval_scope_hash": approval_scope,
            "execution_recipe_scope_hash": recipe_scope,
            "required_interface_apis": selected_apis,
            "required_target_groups": requested_targets,
            "provider_max_calls": 271,
            "attempt_id": claims["provider_attempt_id"],
            "provider_execution_authorization_attempt_id": claims[
                "provider_attempt_id"
            ],
            "provider_execution_authorization_version_id": claims[
                "provider_version_id"
            ],
            "provider_execution_authorization_consumption_packet_key": first[
                "consumption_packet_key"
            ],
            "provider_execution_authorization_consumption_digest": first[
                "consumption_digest"
            ],
        }
        self.assertTrue(
            tushare_production_store._trusted_provider_authorization_ready(receipt)
        )
        with patch.object(
            external,
            "_current_clean_head_full",
            side_effect=AssertionError(
                "historical verification must not inspect the active checkout"
            ),
        ):
            historical = external.validate_trusted_registry(
                head_mode="history",
                expected_head_full=head,
            )
            self.assertFalse(historical["ready"])
            self.assertTrue(historical["historical_integrity_ready"], historical)
            self.assertFalse(historical["production_trusted"])
            self.assertTrue(
                tushare_production_store._trusted_provider_authorization_ready(
                    receipt,
                    head_mode="history",
                    expected_head_full=head,
                )
            )
        for field, value in (
            ("provider_max_calls", 270),
            ("attempt_id", "2" * 32),
            ("provider_execution_authorization_attempt_id", "2" * 32),
            (
                "provider_execution_authorization_version_id",
                f"{recipe_scope[:16]}-{'2' * 32}",
            ),
            (
                "provider_execution_authorization_consumption_packet_key",
                f"{tushare_task_service.PROVIDER_AUTHORIZATION_PACKET_KEY}:{'2' * 32}",
            ),
            ("provider_execution_authorization_consumption_digest", "0" * 64),
        ):
            with self.subTest(field=field):
                self.assertFalse(
                    tushare_production_store._trusted_provider_authorization_ready(
                        {**receipt, field: value}
                    )
                )
        self.assertFalse(
            tushare_production_store._trusted_provider_authorization_ready(
                {
                    **receipt,
                    "provider_execution_authorization_attestation_id": "0" * 64,
                }
            )
        )

    def test_provider_attempt_and_version_are_unique_across_signed_history(self) -> None:
        subject = "tushare-full-interface-provider-execution"
        claims = self._claims("tushare_provider_execution_authorization", subject)
        first_envelope = self._envelope(
            "tushare_provider_execution_authorization",
            subject,
            1,
            "",
            claims=dict(claims),
        )
        self._install_external_proof(first_envelope)
        first = external.prepare_external_trusted_attestation(
            {"signed_envelope": first_envelope},
            expected_kind="tushare_provider_execution_authorization",
        )
        self.assertTrue(first["ready"], first)
        registry_packet = first.pop("_registry_packet")
        SQLiteMetaStore(self.db_path).promote_packet_atomic(
            external.REGISTRY_PACKET_KEY,
            registry_packet,
        )

        second_envelope = self._envelope(
            "tushare_provider_execution_authorization",
            subject,
            2,
            first["attestation_id"],
            claims=dict(claims),
            nonce_seed="second-nonce-same-attempt",
        )
        self._install_external_proof(second_envelope)
        second = external.prepare_external_trusted_attestation(
            {"signed_envelope": second_envelope},
            expected_kind="tushare_provider_execution_authorization",
        )
        self.assertFalse(second["ready"])
        self.assertEqual(
            second["status"], "provider_execution_attempt_or_version_replayed"
        )
        self.assertFalse(second["writes_performed"])
        self.assertEqual(external.validate_registry()["event_count"], 1)

    def test_persisted_trust_survives_envelope_ttl_but_not_head_change(self) -> None:
        subject = "tushare-full-interface-provider-execution"
        envelope = self._envelope(
            "tushare_provider_execution_authorization",
            subject,
            1,
            "",
        )
        self._install_external_proof(envelope)
        prepared = external.prepare_external_trusted_attestation(
            {"signed_envelope": envelope},
            expected_kind="tushare_provider_execution_authorization",
        )
        self.assertTrue(prepared["ready"], prepared)
        SQLiteMetaStore(self.db_path).promote_packet_atomic(
            external.REGISTRY_PACKET_KEY,
            prepared.pop("_registry_packet"),
        )

        class _FutureDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                value = datetime.now(tz)
                return value + timedelta(days=1)

        with patch.object(external, "datetime", _FutureDateTime):
            durable = external.validate_trusted_registry()
        self.assertTrue(durable["ready"], durable)
        self.assertTrue(durable["persisted_validation_ignores_envelope_freshness"])

        with patch.object(
            external, "_current_clean_head_full", return_value="a" * 40
        ):
            wrong_head = external.validate_trusted_registry()
        self.assertFalse(wrong_head["ready"])
        self.assertIn(
            "external_attestation_current_clean_head_mismatch",
            wrong_head["blockers"],
        )

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

    def test_phase2_consumers_bind_exact_sources_and_gets_are_zero_write(self) -> None:
        previous = ""
        promoted: dict[str, dict] = {}
        for counter, consumer in enumerate(("worker", "factor", "radar"), start=1):
            material = self._install_phase2_source(consumer)
            self.assertTrue(material["ready"])
            self.assertFalse(phase2_consumers.validate_consumer(consumer)["ready"])
            envelope = self._phase2_envelope(consumer, counter, previous)
            self._install_external_proof(envelope)
            result = phase2_consumers.import_and_promote_consumer(
                consumer, {"signed_envelope": envelope}
            )
            self.assertTrue(result["ready"], result)
            self.assertTrue(result["promotion_written"])
            self.assertTrue(result["snapshot_rollback_resistant"])
            self.assertTrue(result["current_pointer"]["immutable"])
            self.assertTrue(result["last_good_pointer"]["immutable"])
            self.assertEqual(
                result["last_good_pointer"]["consumer_packet_digest"],
                phase2_consumers._digest(
                    result["last_good_pointer"]["consumer_packet"]
                ),
            )
            promoted[consumer] = result
            previous = str(result["current_pointer"]["attestation_id"])

        status = phase2_consumers.read_phase2_status()
        self.assertTrue(status["ready"])
        self.assertEqual(status["ready_count"], 3)
        before = self.db_path.read_bytes()
        client = TestClient(app)
        self.assertEqual(
            client.get("/api/audit/external-production-consumers").status_code,
            200,
        )
        self.assertEqual(
            client.get(
                "/api/audit/external-production-consumers/worker/attestation-material"
            ).status_code,
            200,
        )
        self.assertEqual(before, self.db_path.read_bytes())

        local_worker = {
            "ready": True,
            "status": "local_worker_verified",
            "full_market_worker_runtime": True,
            "celery_redis_runtime": True,
            "authoritative_candidate_cache_replacement": True,
            "blockers": [],
            "candidate_radar_replacement_blockers": [],
        }
        with patch.object(
            full_market_worker_service,
            "_validate_full_market_worker_local_fact",
            return_value=local_worker,
        ), patch.object(
            phase2_consumers,
            "validate_consumer",
            side_effect=lambda consumer, **_: promoted[consumer],
        ):
            worker = full_market_worker_service.validate_full_market_worker_production_fact(
                self.root
            )
        self.assertTrue(worker["ready"], worker)
        self.assertTrue(worker["candidate_radar_production_replacement"])
        self.assertTrue(worker["local_runtime_fact_ready"])
        self.assertTrue(worker["production_trusted"])

        with patch.object(
            full_market_worker_service,
            "_validate_factor_full_market_local_fact",
            return_value={"ready": True, "status": "local_factor_verified", "blockers": []},
        ), patch.object(
            phase2_consumers,
            "validate_consumer",
            return_value=promoted["factor"],
        ):
            factor = full_market_worker_service.validate_factor_full_market_research_fact(
                self.root
            )
        self.assertTrue(factor["ready"])
        self.assertTrue(factor["local_full_market_factor_research"])
        self.assertTrue(factor["production_trusted"])

    def test_phase2_atomic_failure_partial_state_and_missing_anchor_fail_closed(self) -> None:
        self._install_phase2_source("worker")
        envelope = self._phase2_envelope("worker", 1, "")
        self._install_external_proof(envelope)
        with patch.object(
            phase2_consumers,
            "_write_packets_atomic",
            side_effect=RuntimeError("injected-before-commit"),
        ):
            failed = phase2_consumers.import_and_promote_consumer(
                "worker", {"signed_envelope": envelope}
            )
        self.assertFalse(failed["ready"])
        self.assertFalse(failed["writes_performed"])
        store = SQLiteMetaStore(self.db_path, read_only=True)
        consumer_key, current_key, _ = phase2_consumers._consumer_keys("worker")
        self.assertIsNone(store.read_packet(external.REGISTRY_PACKET_KEY))
        self.assertIsNone(store.read_packet(consumer_key))

        promoted = phase2_consumers.import_and_promote_consumer(
            "worker", {"signed_envelope": envelope}
        )
        self.assertTrue(promoted["ready"], promoted)
        saved_current = promoted["current_pointer"]
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("DELETE FROM packets WHERE packet_key = ?", (current_key,))
        partial = phase2_consumers.validate_consumer("worker")
        self.assertFalse(partial["ready"])
        self.assertIn("external_consumer_atomic_current_last_good_missing", partial["blockers"])

        repair_rejected = phase2_consumers.import_and_promote_consumer(
            "worker", {"signed_envelope": envelope}
        )
        self.assertFalse(repair_rejected["ready"])
        self.assertFalse(repair_rejected["writes_performed"])
        SQLiteMetaStore(self.db_path).write_packet(current_key, saved_current)
        self.assertTrue(phase2_consumers.validate_consumer("worker")["ready"])
        self.trust_root.chmod(0o755)
        self.anchor_path.unlink()
        self.trust_root.chmod(0o555)
        missing_anchor = phase2_consumers.validate_consumer("worker")
        self.assertFalse(missing_anchor["ready"])
        self.assertFalse(missing_anchor["production_trusted"])

    def test_phase2_wrong_dataset_and_old_head_never_write(self) -> None:
        wrong_factor = self._install_phase2_source("factor", wrong_dataset=True)
        self.assertFalse(wrong_factor["ready"])
        blocked = phase2_consumers.import_and_promote_consumer("factor", {})
        self.assertFalse(blocked["ready"])
        self.assertFalse(blocked["writes_performed"])

        self._install_phase2_source("worker")
        old_head = "a" * 40
        envelope = self._phase2_envelope("worker", 1, "", head_full=old_head)
        self._install_external_proof(envelope, epoch_head=old_head)
        rejected = phase2_consumers.import_and_promote_consumer(
            "worker", {"signed_envelope": envelope}
        )
        self.assertFalse(rejected["ready"])
        self.assertFalse(rejected["writes_performed"])
        consumer_key, _, _ = phase2_consumers._consumer_keys("worker")
        self.assertIsNone(SQLiteMetaStore(self.db_path, read_only=True).read_packet(consumer_key))

    def test_phase2_registry_rollback_never_validates(self) -> None:
        self._install_phase2_source("worker")
        first_envelope = self._phase2_envelope("worker", 1, "")
        self._install_external_proof(first_envelope)
        first = phase2_consumers.import_and_promote_consumer(
            "worker", {"signed_envelope": first_envelope}
        )
        self.assertTrue(first["ready"], first)
        store = SQLiteMetaStore(self.db_path)
        registry_snapshot = store.read_packet(external.REGISTRY_PACKET_KEY)

        self._install_phase2_source("factor")
        second_envelope = self._phase2_envelope(
            "factor", 2, str(first["current_pointer"]["attestation_id"])
        )
        self._install_external_proof(second_envelope)
        second = phase2_consumers.import_and_promote_consumer(
            "factor", {"signed_envelope": second_envelope}
        )
        self.assertTrue(second["ready"], second)
        store.write_packet(external.REGISTRY_PACKET_KEY, registry_snapshot)
        rollback = phase2_consumers.validate_consumer("factor")
        self.assertFalse(rollback["ready"])
        self.assertFalse(rollback["snapshot_rollback_resistant"])
        self.assertFalse(rollback["production_trusted"])

    def test_phase2_same_consumer_promotion_preserves_immutable_last_good(self) -> None:
        previous = ""
        counter = 0
        for consumer in ("worker", "factor", "radar"):
            counter += 1
            self._install_phase2_source(consumer, generation_number=1)
            first_envelope = self._phase2_envelope(consumer, counter, previous)
            self._install_external_proof(first_envelope)
            first = phase2_consumers.import_and_promote_consumer(
                consumer, {"signed_envelope": first_envelope}
            )
            self.assertTrue(first["ready"], first)
            previous = str(first["current_pointer"]["attestation_id"])

            counter += 1
            self._install_phase2_source(consumer, generation_number=2)
            second_envelope = self._phase2_envelope(consumer, counter, previous)
            registry_before = SQLiteMetaStore(self.db_path, read_only=True).read_packet(
                external.REGISTRY_PACKET_KEY
            )
            source = phase2_consumers.build_consumer_attestation_material(consumer)
            for digest_field in (
                "source_last_good_packet_digest",
                "last_good_artifact_file_digest",
            ):
                mismatched_source = json.loads(json.dumps(source))
                mismatched_source[digest_field] = "b" * 64
                source_material = {
                    key: value
                    for key, value in mismatched_source.items()
                    if key
                    not in {
                        "artifact_digest",
                        "ready",
                        "status",
                        "claims",
                        "writes_performed",
                    }
                }
                mismatched_source["artifact_digest"] = phase2_consumers._digest(
                    source_material
                )
                mismatched_envelope = self._envelope(
                    str(mismatched_source["attestation_kind"]),
                    str(mismatched_source["subject"]),
                    counter,
                    previous,
                    claims=dict(mismatched_source["claims"]),
                    nonce_seed=digest_field,
                )
                mismatched_envelope["statement"].update(
                    {
                        "task_id": mismatched_source["task_id"],
                        "scope_hash": mismatched_source["scope_hash"],
                        "artifact_digest": mismatched_source["artifact_digest"],
                    }
                )
                self._resign(mismatched_envelope)
                self._install_external_proof(mismatched_envelope)
                with patch.object(
                    phase2_consumers,
                    "_source_binding",
                    return_value=mismatched_source,
                ):
                    digest_rejected = phase2_consumers.import_and_promote_consumer(
                        consumer,
                        {"signed_envelope": mismatched_envelope},
                    )
                self.assertFalse(
                    digest_rejected["ready"],
                    (consumer, digest_field, digest_rejected),
                )
                self.assertFalse(digest_rejected["writes_performed"])
                self.assertEqual(
                    SQLiteMetaStore(self.db_path, read_only=True).read_packet(
                        external.REGISTRY_PACKET_KEY
                    ),
                    registry_before,
                )
            self._install_external_proof(second_envelope)
            _, current_key, _ = phase2_consumers._consumer_keys(consumer)
            tampered_previous = json.loads(json.dumps(first["current_pointer"]))
            if consumer == "worker":
                tampered_previous["generation"] = "worker-generation-0"
            elif consumer == "factor":
                tampered_previous["consumer"] = "worker"
                tampered_previous["consumer_packet"]["consumer"] = "worker"
                tampered_previous["consumer_packet_digest"] = phase2_consumers._digest(
                    tampered_previous["consumer_packet"]
                )
            else:
                source_binding = tampered_previous["consumer_packet"]["source_binding"]
                source_binding["generation"] = "worker-generation-0"
                source_material = {
                    key: value
                    for key, value in source_binding.items()
                    if key != "artifact_digest"
                }
                source_binding["artifact_digest"] = phase2_consumers._digest(source_material)
                tampered_previous["generation"] = "worker-generation-0"
                tampered_previous["consumer_packet_digest"] = phase2_consumers._digest(
                    tampered_previous["consumer_packet"]
                )
            SQLiteMetaStore(self.db_path).write_packet(current_key, tampered_previous)
            rejected = phase2_consumers.import_and_promote_consumer(
                consumer, {"signed_envelope": second_envelope}
            )
            self.assertFalse(rejected["ready"], (consumer, rejected))
            self.assertFalse(rejected["writes_performed"])
            self.assertEqual(
                SQLiteMetaStore(self.db_path, read_only=True).read_packet(
                    external.REGISTRY_PACKET_KEY
                ),
                registry_before,
            )
            SQLiteMetaStore(self.db_path).write_packet(
                current_key,
                first["current_pointer"],
            )
            second = phase2_consumers.import_and_promote_consumer(
                consumer, {"signed_envelope": second_envelope}
            )
            self.assertTrue(second["ready"], second)
            expected_generation = (
                "worker-generation-2"
                if consumer == "radar"
                else f"{consumer}-generation-2"
            )
            self.assertEqual(second["current_pointer"]["generation"], expected_generation)
            self.assertEqual(
                second["last_good_pointer"]["attestation_id"],
                first["current_pointer"]["attestation_id"],
            )
            self.assertEqual(
                second["last_good_pointer"]["generation"],
                first["current_pointer"]["generation"],
            )
            self.assertEqual(
                second["last_good_pointer"]["consumer_packet_digest"],
                phase2_consumers._digest(
                    second["last_good_pointer"]["consumer_packet"]
                ),
            )
            previous = str(second["current_pointer"]["attestation_id"])

    def test_phase2_last_good_field_mismatches_fail_for_every_consumer(self) -> None:
        previous = ""
        for counter, consumer in enumerate(("worker", "factor", "radar"), start=1):
            self._install_phase2_source(consumer)
            envelope = self._phase2_envelope(consumer, counter, previous)
            self._install_external_proof(envelope)
            promoted = phase2_consumers.import_and_promote_consumer(
                consumer, {"signed_envelope": envelope}
            )
            self.assertTrue(promoted["ready"], promoted)
            previous = str(promoted["current_pointer"]["attestation_id"])
            _, _, last_good_key = phase2_consumers._consumer_keys(consumer)
            original = promoted["last_good_pointer"]

            for mismatch in (
                "outer_attestation_id",
                "outer_generation",
                "embedded_attestation_id",
                "embedded_generation_reseal",
                "cross_consumer_reseal",
                "packet_key",
                "monotonic_counter",
                "monotonic_counter_bool",
                "head_key_epoch",
                "head_key_epoch_bool",
                "head_key_epoch_digest",
                "monotonic_anchor_digest",
                "production_trusted",
                "snapshot_rollback_resistant",
                "does_not_execute_trades",
            ):
                tampered = json.loads(json.dumps(original))
                if mismatch == "outer_attestation_id":
                    tampered["attestation_id"] = "f" * 64
                elif mismatch == "outer_generation":
                    tampered["generation"] = "wrong-generation"
                elif mismatch == "embedded_attestation_id":
                    tampered["consumer_packet"]["attestation_id"] = "e" * 64
                    tampered["consumer_packet_digest"] = phase2_consumers._digest(
                        tampered["consumer_packet"]
                    )
                elif mismatch == "embedded_generation_reseal":
                    tampered["consumer_packet"]["source_binding"][
                        "generation"
                    ] = "resealed-generation"
                    tampered["generation"] = "resealed-generation"
                    tampered["consumer_packet_digest"] = phase2_consumers._digest(
                        tampered["consumer_packet"]
                    )
                elif mismatch == "cross_consumer_reseal":
                    other_consumer = "factor" if consumer != "factor" else "worker"
                    tampered["consumer"] = other_consumer
                    tampered["consumer_packet"]["consumer"] = other_consumer
                    tampered["consumer_packet_digest"] = phase2_consumers._digest(
                        tampered["consumer_packet"]
                    )
                else:
                    packet = tampered["consumer_packet"]
                    if mismatch == "packet_key":
                        packet["packet_key"] = "wrong-consumer-packet-key"
                    elif mismatch == "monotonic_counter":
                        packet["monotonic_counter"] += 100
                    elif mismatch == "monotonic_counter_bool":
                        packet["monotonic_counter"] = True
                    elif mismatch == "head_key_epoch":
                        packet["head_key_epoch"] += 100
                    elif mismatch == "head_key_epoch_bool":
                        packet["head_key_epoch"] = True
                    elif mismatch in {
                        "head_key_epoch_digest",
                        "monotonic_anchor_digest",
                    }:
                        packet[mismatch] = "d" * 64
                    else:
                        packet[mismatch] = False
                    tampered["consumer_packet_digest"] = phase2_consumers._digest(packet)
                SQLiteMetaStore(self.db_path).write_packet(last_good_key, tampered)
                result = phase2_consumers.validate_consumer(consumer)
                self.assertFalse(result["ready"], (consumer, mismatch, result))
                self.assertFalse(result["production_trusted"])

            SQLiteMetaStore(self.db_path).write_packet(last_good_key, original)
            self.assertTrue(phase2_consumers.validate_consumer(consumer)["ready"])
            source = phase2_consumers.build_consumer_attestation_material(consumer)
            self.assertTrue(
                phase2_consumers._previous_current_matches_source_last_good(
                    original,
                    source,
                )
            )
            for digest_field in (
                "source_last_good_packet_digest",
                "last_good_artifact_file_digest",
            ):
                mismatched_source = dict(source)
                mismatched_source[digest_field] = "c" * 64
                self.assertFalse(
                    phase2_consumers._previous_current_matches_source_last_good(
                        original,
                        mismatched_source,
                    ),
                    (consumer, digest_field),
                )

    def test_phase2_strict_registry_matrix_rejects_every_consumer(self) -> None:
        previous = ""
        for counter, consumer in enumerate(("worker", "factor", "radar"), start=1):
            self._install_phase2_source(consumer)
            envelope = self._phase2_envelope(consumer, counter, previous)
            self._install_external_proof(envelope)
            promoted = phase2_consumers.import_and_promote_consumer(
                consumer, {"signed_envelope": envelope}
            )
            self.assertTrue(promoted["ready"], promoted)
            previous = str(promoted["current_pointer"]["attestation_id"])
            registry = SQLiteMetaStore(self.db_path, read_only=True).read_packet(
                external.REGISTRY_PACKET_KEY
            )
            canonical_registry = external.validate_registry()["canonical_registry"]
            packet = promoted["current_pointer"]["consumer_packet"]
            event = next(
                row
                for row in registry["events"]
                if row["attestation_id"] == packet["attestation_id"]
            )
            self.assertTrue(
                phase2_consumers._strict_registry_consumer_matches(
                    consumer,
                    registry,
                    canonical_registry,
                    packet,
                    event,
                )
            )
            mutations = {
                "unexpected_unsigned_field": "tampered",
                "schema_version": "wrong-schema",
                "packet_key": "wrong-registry-key",
                "status": "wrong-status",
                "head_full": "a" * 40,
                "event_count": True,
                "last_attestation_id": "b" * 64,
                "last_monotonic_counter": True,
                "head_key_epoch": True,
                "head_key_epoch_digest": "c" * 64,
                "monotonic_anchor_digest": "d" * 64,
                "external_signature_verified": False,
                "external_trust_verified": False,
                "production_trusted": False,
                "snapshot_rollback_resistant": False,
                "private_key_generated": True,
                "private_key_loaded": True,
                "external_calls_triggered": True,
                "contains_secret": True,
                "does_not_execute_trades": False,
                "blockers": ["tampered"],
            }
            for field, bad_value in mutations.items():
                tampered = json.loads(json.dumps(registry))
                tampered[field] = bad_value
                self.assertFalse(
                    phase2_consumers._strict_registry_consumer_matches(
                        consumer,
                        tampered,
                        canonical_registry,
                        packet,
                        event,
                    ),
                    (consumer, field),
                )
            for field in ("last_monotonic_counter", "head_key_epoch"):
                for bad_value in (False, 0, -1, 2**63):
                    tampered = json.loads(json.dumps(registry))
                    tampered[field] = bad_value
                    self.assertFalse(
                        phase2_consumers._strict_registry_consumer_matches(
                            consumer,
                            tampered,
                            canonical_registry,
                            packet,
                            event,
                        ),
                        (consumer, field, bad_value),
                    )
            for event_index in range(len(registry["events"])):
                tampered = json.loads(json.dumps(registry))
                tampered["events"][event_index]["unsigned_extra"] = "tampered"
                self.assertFalse(
                    phase2_consumers._strict_registry_consumer_matches(
                        consumer,
                        tampered,
                        canonical_registry,
                        packet,
                        event,
                    ),
                    (consumer, "history_or_cross_consumer", event_index),
                )
                for field in ("monotonic_counter", "head_key_epoch"):
                    for bad_value in (True, 0, 2**63):
                        tampered = json.loads(json.dumps(registry))
                        tampered["events"][event_index][field] = bad_value
                        self.assertFalse(
                            phase2_consumers._strict_registry_consumer_matches(
                                consumer,
                                tampered,
                                canonical_registry,
                                packet,
                                event,
                            ),
                            (consumer, event_index, field, bad_value),
                        )
            for field in ("monotonic_counter", "head_key_epoch"):
                for bad_value in (True, 0, -1, 2**63):
                    tampered_packet = json.loads(json.dumps(packet))
                    tampered_packet[field] = bad_value
                    self.assertFalse(
                        phase2_consumers._strict_registry_consumer_matches(
                            consumer,
                            registry,
                            canonical_registry,
                            tampered_packet,
                            event,
                        ),
                        (consumer, "packet", field, bad_value),
                    )
            if len(registry["events"]) > 1:
                tampered = json.loads(json.dumps(registry))
                tampered["events"][0]["cross_consumer_unsigned_extra"] = True
                SQLiteMetaStore(self.db_path).write_packet(
                    external.REGISTRY_PACKET_KEY,
                    tampered,
                )
                cross_consumer = phase2_consumers.validate_consumer(consumer)
                self.assertFalse(cross_consumer["ready"], cross_consumer)
                self.assertFalse(cross_consumer["production_trusted"])
                SQLiteMetaStore(self.db_path).write_packet(
                    external.REGISTRY_PACKET_KEY,
                    registry,
                )
                self.assertTrue(phase2_consumers.validate_consumer(consumer)["ready"])

    def test_phase2_source_counts_reject_bool_and_numeric_strings(self) -> None:
        cases = (
            ("worker", ("batch_count", True)),
            ("worker", ("result_row_count", "8")),
            ("worker", ("celery_task_ids", 1)),
            ("worker", ("worker_task_ids", "worker-1")),
            ("factor", ("universe_count", "3000")),
            ("radar", ("candidate_row_count", True)),
        )
        for consumer, (field, bad_value) in cases:
            with self.subTest(consumer=consumer, field=field):
                self._install_phase2_source(consumer)
                config = phase2_consumers._CONFIG[consumer]
                store = SQLiteMetaStore(self.db_path)
                packet = store.read_packet(config["current_key"])
                if consumer == "radar":
                    binding = packet["full_market_worker_replacement"]
                    binding[field] = bad_value
                    binding["binding_digest"] = phase2_consumers._digest(
                        {
                            key: value
                            for key, value in binding.items()
                            if key != "binding_digest"
                        }
                    )
                else:
                    packet[field] = bad_value
                store.write_packet(config["current_key"], packet)
                self.assertFalse(
                    phase2_consumers.build_consumer_attestation_material(consumer)[
                        "ready"
                    ]
                )
                if field == "celery_task_ids":
                    before = self.db_path.read_bytes()
                    response = TestClient(app).get(
                        "/api/audit/external-production-consumers/worker/attestation-material"
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(response.json()["data"]["ready"])
                    self.assertEqual(before, self.db_path.read_bytes())
        identity = phase2_consumers._source_identity(
            "worker",
            {"celery_task_ids": 1, "worker_task_ids": []},
        )
        self.assertEqual(identity["claims"]["eligible_worker_count"], 0)

    def test_phase2_typed_bool_number_registry_bypass_is_blocked(self) -> None:
        previous = ""
        for counter, consumer in enumerate(("worker", "factor"), start=1):
            self._install_phase2_source(consumer)
            envelope = self._phase2_envelope(consumer, counter, previous)
            self._install_external_proof(envelope)
            promoted = phase2_consumers.import_and_promote_consumer(
                consumer, {"signed_envelope": envelope}
            )
            self.assertTrue(promoted["ready"], promoted)
            previous = str(promoted["current_pointer"]["attestation_id"])
            store = SQLiteMetaStore(self.db_path)
            registry = store.read_packet(external.REGISTRY_PACKET_KEY)
            tampered = json.loads(json.dumps(registry))
            signed_claim = tampered["events"][0]["signed_envelope"]["statement"][
                "claims"
            ]["does_not_execute_trades"]
            self.assertIs(signed_claim, True)
            tampered["events"][0]["claims"]["does_not_execute_trades"] = 1
            store.write_packet(external.REGISTRY_PACKET_KEY, tampered)
            result = phase2_consumers.validate_consumer(consumer)
            self.assertFalse(result["ready"], (consumer, result))
            self.assertFalse(result["production_trusted"])
            store.write_packet(external.REGISTRY_PACKET_KEY, registry)
            self.assertTrue(phase2_consumers.validate_consumer(consumer)["ready"])

    def test_worker_production_post_exposes_three_external_trust_states(self) -> None:
        client = TestClient(app)
        local_packet = {
            "status": "full_market_worker_production_complete",
            "acceptance_run_id": "worker-run-1",
            "result_version_id": "worker-generation-1",
            "production_worker_complete": True,
            "full_market_worker_runtime": True,
            "celery_redis_runtime": True,
            "local_production_worker_complete": True,
            "local_full_market_worker_runtime": True,
            "local_celery_redis_runtime": True,
            "call_ledger": [],
        }
        states = {
            "missing": {
                "ready": False,
                "production_trusted": False,
                "snapshot_rollback_resistant": False,
                "local_runtime_fact_ready": True,
                "external_production_consumer": {"ready": False},
            },
            "mismatch": {
                "ready": True,
                "production_trusted": True,
                "snapshot_rollback_resistant": True,
                "local_runtime_fact_ready": True,
                "external_production_consumer": {
                    "ready": True,
                    "subject": "other-run",
                    "generation": "other-generation",
                },
            },
            "ready": {
                "ready": True,
                "production_trusted": True,
                "snapshot_rollback_resistant": True,
                "local_runtime_fact_ready": True,
                "external_production_consumer": {
                    "ready": True,
                    "subject": "worker-run-1",
                    "generation": "worker-generation-1",
                },
            },
        }
        for state, fact in states.items():
            with self.subTest(state=state), patch.object(
                full_market_worker_service,
                "run_full_market_worker_production_acceptance",
                return_value=local_packet,
            ), patch.object(
                full_market_worker_service,
                "validate_full_market_worker_production_fact",
                return_value=fact,
            ):
                response = client.post(
                    "/api/worker/full-market-production-acceptance",
                    json={"operator_approved": True},
                )
            data = response.json()["data"]
            expected = state == "ready"
            expected_status = {
                "missing": "full_market_worker_production_acceptance_external_consumer_missing",
                "mismatch": "full_market_worker_production_acceptance_external_consumer_subject_generation_mismatch",
                "ready": "full_market_worker_production_acceptance_external_trust_verified",
            }[state]
            self.assertEqual(data["status"], expected_status)
            self.assertEqual(
                data["external_consumer_state"],
                {
                    "missing": "missing",
                    "mismatch": "subject_generation_mismatch",
                    "ready": "verified",
                }[state],
            )
            self.assertEqual(data["external_consumer_missing"], state == "missing")
            self.assertEqual(data["external_consumer_exact_source_match"], expected)
            self.assertEqual(data["external_consumer_verified"], expected)
            self.assertEqual(data["ready"], expected)
            self.assertEqual(data["production_worker_complete"], expected)
            self.assertEqual(data["full_market_worker_runtime"], expected)
            self.assertEqual(data["celery_redis_runtime"], expected)
            self.assertTrue(data["local_production_worker_complete"])
            self.assertTrue(data["local_full_market_worker_runtime"])
            self.assertTrue(data["local_celery_redis_runtime"])


if __name__ == "__main__":
    unittest.main()
