from __future__ import annotations

import base64
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from server.main import app
from server.services import full_market_industry_provider_service as provider_service
from server.services import full_market_industry_provider_collector as provider_collector
from server.services import full_market_industry_evidence_writer as evidence_writer
from server.services import full_market_industry_generation_attestation as generation_trust
from server.services import full_market_industry_service as service
from server.services import external_production_attestation_service as external_trust
from server.services import task_service
from storage.sqlite_meta import SQLiteMetaStore


def _symbols() -> list[str]:
    return sorted(
        [f"{600000 + index:06d}.SH" for index in range(1000)]
        + [f"{1 + index:06d}.SZ" for index in range(1000)]
        + [f"{430000 + index:06d}.BJ" for index in range(1000)]
    )


def _upstream(symbols: list[str]) -> dict:
    return {
        "ready": True,
        "symbols": symbols,
        "universe_count": len(symbols),
        "universe_digest": service._digest(symbols),
        "scope_hash": "a" * 64,
        "version_digest": "b" * 64,
        "validated_trade_date": "20260717",
        "blockers": [],
    }


def _semantic_statement() -> dict:
    content = {
        "field": "out_date",
        "interval_convention": "effective_from_inclusive_effective_to_exclusive",
        "non_null_boundary": "first_excluded_trade_date",
        "null_meaning": "membership_current_at_validated_trade_date",
    }
    now = datetime.now(timezone.utc)
    return {
        "schema_version": service.SEMANTIC_AUTHORITY_STATEMENT_SCHEMA_VERSION,
        "status": "externally_attested",
        "authority": "independent_production_semantic_authority",
        "source_api": service.SOURCE_API,
        "source_scope": service.SOURCE_SCOPE,
        "source_reference": "provider-official-contract:index_member_all.out_date:v2026-07",
        "endpoint_field": "out_date",
        "resolved_semantics": service.RESOLVED_OUT_DATE_SEMANTICS,
        "content": content,
        "content_digest": service._digest(content),
        "issued_at_utc": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "expires_at_utc": (now + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
    }


def _install_semantic_authority(stack: ExitStack) -> tuple[Path, Path]:
    trust_parent = Path(stack.enter_context(tempfile.TemporaryDirectory()))
    trust_root = trust_parent / "operator-trust"
    trust_root.mkdir()
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    pem = public_key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    der = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = hashlib.sha256(der).hexdigest()
    key_path = trust_root / "ed25519-public.pem"
    fingerprint_path = trust_root / "ed25519-public.sha256"
    authority_path = trust_root / "industry-out-date-authority.json"
    key_path.write_bytes(pem)
    fingerprint_path.write_text(fingerprint + "\n", encoding="ascii")
    statement = _semantic_statement()
    authority = {
        "schema_version": service.SEMANTIC_AUTHORITY_ENVELOPE_SCHEMA_VERSION,
        "algorithm": "Ed25519",
        "key_fingerprint_sha256": fingerprint,
        "statement": statement,
        "signature_base64": base64.b64encode(
            private_key.sign(service._canonical_bytes(statement))
        ).decode("ascii"),
    }
    authority_path.write_bytes(service._canonical_bytes(authority))
    for path in (key_path, fingerprint_path, authority_path):
        path.chmod(0o444)
    trust_root.chmod(0o555)
    stack.enter_context(
        patch.multiple(
            external_trust,
            TRUST_ROOT=trust_root,
            TRUST_ANCHOR=trust_parent,
            PUBLIC_KEY_PATH=key_path,
            FINGERPRINT_PATH=fingerprint_path,
            TRUSTED_OWNER_UIDS=frozenset({os.getuid()}),
        )
    )
    stack.enter_context(
        patch.multiple(
            service,
            SEMANTIC_AUTHORITY_PATH=authority_path,
            SEMANTIC_AUTHORITY_TRUSTED_OWNER_UIDS=frozenset({os.getuid()}),
        )
    )
    return trust_root, authority_path


class _IndependentGenerationSigner:
    def __init__(self, root: Path, private_key: Ed25519PrivateKey, fingerprint: str):
        self.root = root
        self.private_key = private_key
        self.fingerprint = fingerprint
        self.history_path = root / "attestation-history.json"

    def reset(self) -> None:
        history = {
            "schema_version": generation_trust.HISTORY_SCHEMA_VERSION,
            "events": [],
            "history_digest": generation_trust._digest([]),
        }
        self.root.chmod(0o755)
        self.history_path.chmod(0o644)
        self.history_path.write_bytes(generation_trust._canonical_bytes(history))
        self.history_path.chmod(0o444)
        self.root.chmod(0o555)

    def append(self, claims: dict, **overrides) -> dict:
        statement = {
            **claims,
            "issued_at_utc": (
                datetime.now(timezone.utc) - timedelta(seconds=1)
            ).isoformat().replace("+00:00", "Z"),
            "expires_at_utc": (
                datetime.now(timezone.utc) + timedelta(days=30)
            ).isoformat().replace("+00:00", "Z"),
            **overrides,
        }
        envelope = {
            "schema_version": generation_trust.ENVELOPE_SCHEMA_VERSION,
            "algorithm": "Ed25519",
            "key_fingerprint_sha256": self.fingerprint,
            "statement": statement,
            "signature_base64": base64.b64encode(
                self.private_key.sign(generation_trust._canonical_bytes(statement))
            ).decode("ascii"),
        }
        history = json.loads(self.history_path.read_text())
        history["events"].append(envelope)
        history["history_digest"] = generation_trust._digest(history["events"])
        self.root.chmod(0o755)
        self.history_path.chmod(0o644)
        self.history_path.write_bytes(generation_trust._canonical_bytes(history))
        self.history_path.chmod(0o444)
        self.root.chmod(0o555)
        return envelope


def _install_generation_authority(stack: ExitStack) -> _IndependentGenerationSigner:
    trust_parent = Path(stack.enter_context(tempfile.TemporaryDirectory()))
    trust_root = trust_parent / "generation-trust"
    trust_root.mkdir()
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    pem = public_key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    der = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = hashlib.sha256(der).hexdigest()
    key_path = trust_root / "ed25519-public.pem"
    fingerprint_path = trust_root / "ed25519-public.sha256"
    history_path = trust_root / "attestation-history.json"
    key_path.write_bytes(pem)
    fingerprint_path.write_text(fingerprint + "\n", encoding="ascii")
    history = {
        "schema_version": generation_trust.HISTORY_SCHEMA_VERSION,
        "events": [],
        "history_digest": generation_trust._digest([]),
    }
    history_path.write_bytes(generation_trust._canonical_bytes(history))
    for path in (key_path, fingerprint_path, history_path):
        path.chmod(0o444)
    trust_root.chmod(0o555)
    stack.enter_context(
        patch.multiple(
            generation_trust,
            TRUST_ROOT=trust_root,
            PUBLIC_KEY_PATH=key_path,
            FINGERPRINT_PATH=fingerprint_path,
            HISTORY_PATH=history_path,
            TRUSTED_OWNER_UIDS=frozenset({os.getuid()}),
        )
    )
    return _IndependentGenerationSigner(trust_root, private_key, fingerprint)


def _write_evidence(
    evidence_root: Path,
    symbols: list[str],
    *,
    unresolved_out_date: bool = False,
    rows_override: list[dict] | None = None,
) -> dict:
    root = evidence_root / service.INDUSTRY_ROOT_RELATIVE
    artifact_path = root / "artifacts" / "industry-v1.json"
    manifest_path = root / "manifests" / "industry-v1.json"
    semantic_path = root / "semantics" / "out-date-v1.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    semantic_path.parent.mkdir(parents=True, exist_ok=True)
    rows = rows_override or [
        {
            "ts_code": symbol,
            "industry_code": "SW801010",
            "effective_from": "20200101",
            "effective_to": None,
            "source_api": service.SOURCE_API,
        }
        for symbol in symbols
    ]
    artifact = {
        "schema_version": service.ARTIFACT_SCHEMA_VERSION,
        "rows": rows,
    }
    artifact_path.write_bytes(service._canonical_bytes(artifact))
    artifact_sha256 = service._file_digest(artifact_path)
    semantic_path.write_bytes(service.SEMANTIC_AUTHORITY_PATH.read_bytes())
    semantic_sha256 = service._file_digest(semantic_path)
    scope = {
        "schema_version": service.SCOPE_SCHEMA_VERSION,
        "source_api": service.SOURCE_API,
        "source_scope": service.SOURCE_SCOPE,
        "eligible_symbol_count": len(symbols),
        "exchanges": list(service.REQUIRED_EXCHANGES),
        "universe_digest": service._digest(symbols),
        "validated_trade_date": "20260717",
        "as_of_date": "20260717",
    }
    scope_digest = service._digest(scope)
    source_version = {
        "schema_version": service.SOURCE_VERSION_SCHEMA_VERSION,
        "version_id": "industry-v1",
        "source_api": service.SOURCE_API,
        "source_scope": service.SOURCE_SCOPE,
        "scope_digest": scope_digest,
        "artifact_schema_version": service.ARTIFACT_SCHEMA_VERSION,
        "artifact_sha256": artifact_sha256,
        "semantic_evidence_sha256": semantic_sha256,
    }
    manifest = {
        "schema_version": service.MANIFEST_SCHEMA_VERSION,
        "status": "full_market_industry_membership_verified",
        "version_id": "industry-v1",
        "source_api": service.SOURCE_API,
        "source_scope": service.SOURCE_SCOPE,
        "scope": scope,
        "scope_digest": scope_digest,
        "source_version": source_version,
        "source_version_digest": service._digest(source_version),
        "artifact_file": "artifacts/industry-v1.json",
        "artifact_schema_version": service.ARTIFACT_SCHEMA_VERSION,
        "artifact_sha256": artifact_sha256,
        "artifact_row_count": len(rows),
        "universe_digest": service._digest(symbols),
        "eligible_symbol_count": len(symbols),
        "exchanges": list(service.REQUIRED_EXCHANGES),
        "validated_trade_date": "20260717",
        "as_of_date": "20260717",
        "out_date_semantics": (
            "provider_documentation_unspecified"
            if unresolved_out_date
            else service.RESOLVED_OUT_DATE_SEMANTICS
        ),
        "out_date_semantics_validated": not unresolved_out_date,
        "out_date_semantics_evidence_digest": "e" * 64,
        "semantic_evidence_file": "semantics/out-date-v1.json",
        "semantic_evidence_schema_version": service.SEMANTIC_EVIDENCE_SCHEMA_VERSION,
        "semantic_evidence_sha256": semantic_sha256,
    }
    manifest["out_date_semantics_evidence_digest"] = semantic_sha256
    manifest["manifest_digest"] = service._digest(manifest)
    manifest_path.write_bytes(service._canonical_bytes(manifest))
    pointer = {
        "schema_version": service.POINTER_SCHEMA_VERSION,
        "version_id": manifest["version_id"],
        "manifest_file": "manifests/industry-v1.json",
        "manifest_digest": manifest["manifest_digest"],
        "artifact_sha256": artifact_sha256,
        "scope_digest": manifest["scope_digest"],
        "source_version_digest": manifest["source_version_digest"],
        "semantic_evidence_sha256": semantic_sha256,
        "universe_digest": manifest["universe_digest"],
        "validated_trade_date": manifest["validated_trade_date"],
        "as_of_date": manifest["as_of_date"],
    }
    pointer["pointer_digest"] = service._digest(pointer)
    (root / service.POINTER_FILE).write_bytes(service._canonical_bytes(pointer))
    return {
        "root": root,
        "artifact": artifact_path,
        "manifest": manifest_path,
        "semantic": semantic_path,
    }


def _reseal_evidence(paths: dict[str, Path]) -> None:
    artifact = json.loads(paths["artifact"].read_text(encoding="utf-8"))
    artifact_sha256 = service._file_digest(paths["artifact"])
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    semantic_sha256 = (
        service._file_digest(paths["semantic"])
        if paths["semantic"].is_file()
        else "0" * 64
    )
    manifest["artifact_sha256"] = artifact_sha256
    manifest["artifact_row_count"] = (
        len(artifact.get("rows")) if type(artifact.get("rows")) is list else 0
    )
    manifest["semantic_evidence_sha256"] = semantic_sha256
    manifest["out_date_semantics_evidence_digest"] = semantic_sha256
    source_version = dict(manifest.get("source_version") or {})
    source_version.update(
        {
            "version_id": manifest.get("version_id"),
            "scope_digest": manifest.get("scope_digest"),
            "artifact_sha256": artifact_sha256,
            "semantic_evidence_sha256": semantic_sha256,
        }
    )
    manifest["source_version"] = source_version
    manifest["source_version_digest"] = service._digest(source_version)
    manifest.pop("manifest_digest", None)
    manifest["manifest_digest"] = service._digest(manifest)
    paths["manifest"].write_bytes(service._canonical_bytes(manifest))
    pointer_path = paths["root"] / service.POINTER_FILE
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    for key in (
        "version_id",
        "manifest_digest",
        "artifact_sha256",
        "scope_digest",
        "source_version_digest",
        "semantic_evidence_sha256",
        "universe_digest",
        "validated_trade_date",
        "as_of_date",
    ):
        pointer[key] = manifest[key]
    pointer.pop("pointer_digest", None)
    pointer["pointer_digest"] = service._digest(pointer)
    pointer_path.write_bytes(service._canonical_bytes(pointer))


class FullMarketIndustryMembershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.trust_root, self.authority_path = _install_semantic_authority(self.stack)

    def tearDown(self) -> None:
        self.stack.close()

    def test_exact_full_market_effective_dated_pointer_is_read_only_and_ready(self) -> None:
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            evidence_root = Path(directory)
            paths = _write_evidence(evidence_root, symbols)
            before = {
                path: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in paths.values()
                if isinstance(path, Path) and path.is_file()
            }

            result = service.validate_full_market_industry_membership(
                evidence_root,
                expected_symbols=symbols,
                expected_universe_digest=service._digest(symbols),
                expected_validated_trade_date="20260717",
            )

            self.assertTrue(result["ready"], result["blockers"])
            self.assertTrue(result["production_industry_verified"])
            self.assertEqual(result["eligible_symbol_count"], 3000)
            self.assertEqual(result["exchanges"], list(service.REQUIRED_EXCHANGES))
            self.assertFalse(result["writes_storage"])
            self.assertFalse(result["external_calls_triggered"])
            self.assertFalse((evidence_root / "meta.sqlite").exists())
            after = {
                path: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in before
            }
            self.assertEqual(before, after)

    def test_missing_pointer_and_small_pool_raw_rows_never_promote(self) -> None:
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            evidence_root = Path(directory)
            raw = evidence_root / "factor_test_provider_industry_membership_raw.json"
            raw.write_text(json.dumps({"rows": [{"ts_code": symbols[0]}]}), encoding="utf-8")
            result = service.validate_full_market_industry_membership(
                evidence_root,
                expected_symbols=symbols,
                expected_universe_digest=service._digest(symbols),
                expected_validated_trade_date="20260717",
            )
            self.assertFalse(result["ready"])
            self.assertFalse(result["small_pool_raw_evidence_accepted"])
            self.assertIn("industry_pointer_schema_not_exact", result["blockers"])

    def test_unresolved_out_date_overlap_and_incomplete_coverage_fail_closed(self) -> None:
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            evidence_root = Path(directory)
            rows = [
                {
                    "ts_code": symbol,
                    "industry_code": "SW801010",
                    "effective_from": "20200101",
                    "effective_to": None,
                    "source_api": service.SOURCE_API,
                }
                for symbol in symbols[:-1]
            ]
            rows.extend(
                [
                    {
                        "ts_code": symbols[0],
                        "industry_code": "SW801020",
                        "effective_from": "20250101",
                        "effective_to": "20270101",
                        "source_api": service.SOURCE_API,
                    },
                    {
                        "ts_code": symbols[0],
                        "industry_code": "SW801030",
                        "effective_from": "20260101",
                        "effective_to": None,
                        "source_api": service.SOURCE_API,
                    },
                ]
            )
            _write_evidence(
                evidence_root,
                symbols,
                unresolved_out_date=True,
                rows_override=rows,
            )
            result = service.validate_full_market_industry_membership(
                evidence_root,
                expected_symbols=symbols,
                expected_universe_digest=service._digest(symbols),
                expected_validated_trade_date="20260717",
            )
            self.assertFalse(result["ready"])
            self.assertIn("industry_out_date_semantics_unresolved", result["blockers"])
            self.assertIn("artifact_effective_intervals_overlap", result["blockers"])
            self.assertIn("artifact_symbol_coverage_not_exact", result["blockers"])

    def test_digest_or_as_of_tampering_fails_closed(self) -> None:
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            evidence_root = Path(directory)
            paths = _write_evidence(evidence_root, symbols)
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            manifest["as_of_date"] = "20260716"
            paths["manifest"].write_bytes(service._canonical_bytes(manifest))
            result = service.validate_full_market_industry_membership(
                evidence_root,
                expected_symbols=symbols,
                expected_universe_digest=service._digest(symbols),
                expected_validated_trade_date="20260717",
            )
            self.assertFalse(result["ready"])
            self.assertIn("industry_manifest_digest_invalid", result["blockers"])
            self.assertIn(
                "industry_as_of_date_not_current_validated_trade_date",
                result["blockers"],
            )

    def test_pointer_cannot_escape_root_or_follow_symlinked_manifest(self) -> None:
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            evidence_root = Path(directory)
            paths = _write_evidence(evidence_root, symbols)
            outside = evidence_root / "outside.json"
            outside.write_bytes(paths["manifest"].read_bytes())
            pointer_path = paths["root"] / service.POINTER_FILE
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            pointer["manifest_file"] = "../outside.json"
            pointer.pop("pointer_digest")
            pointer["pointer_digest"] = service._digest(pointer)
            pointer_path.write_bytes(service._canonical_bytes(pointer))
            escaped = service.validate_full_market_industry_membership(
                evidence_root,
                expected_symbols=symbols,
                expected_universe_digest=service._digest(symbols),
                expected_validated_trade_date="20260717",
            )
            self.assertFalse(escaped["ready"])
            self.assertIn("industry_manifest_schema_not_exact", escaped["blockers"])

            pointer["manifest_file"] = "manifests/link.json"
            pointer.pop("pointer_digest")
            pointer["pointer_digest"] = service._digest(pointer)
            pointer_path.write_bytes(service._canonical_bytes(pointer))
            (paths["root"] / "manifests" / "link.json").symlink_to(outside)
            linked = service.validate_full_market_industry_membership(
                evidence_root,
                expected_symbols=symbols,
                expected_universe_digest=service._digest(symbols),
                expected_validated_trade_date="20260717",
            )
            self.assertFalse(linked["ready"])
            self.assertIn("industry_manifest_schema_not_exact", linked["blockers"])

    def test_execution_request_post_writes_only_task_and_never_provider_pointer(self) -> None:
        symbols = _symbols()
        upstream = _upstream(symbols)
        with tempfile.TemporaryDirectory() as directory:
            evidence_root = Path(directory)
            meta_path = evidence_root / "meta.sqlite"
            with patch.object(service, "EVIDENCE_ROOT", evidence_root), patch.object(
                task_service, "SQLITE_META_PATH", meta_path
            ), patch(
                "server.services.tushare_production_store.validate_tushare_full_market_production_version",
                return_value=upstream,
            ) as verifier:
                response = TestClient(app).post(
                    "/api/factor-quant/full-market-industry-membership-execution-request",
                    json={
                        "create_execution_request": True,
                        "acknowledge_no_provider_execution": True,
                        "request_nonce": str(uuid.uuid4()),
                    },
                )
            verifier.assert_called_once_with(evidence_root)
            payload = response.json()["data"]["task"]["payload_safe"]["execution_request"]
            self.assertTrue(payload["request_ready"])
            self.assertFalse(payload["provider_execution_triggered"])
            self.assertFalse(payload["provider_task_created"])
            self.assertFalse(payload["production_pointer_written"])
            self.assertFalse(payload["production_industry_verified"])
            self.assertFalse(payload["anns_d_required"])
            self.assertTrue(meta_path.exists())
            self.assertFalse(
                (evidence_root / service.INDUSTRY_ROOT_RELATIVE / service.POINTER_FILE).exists()
            )

    def test_get_route_is_immutable_and_post_without_exact_literal_stays_local_blocked(self) -> None:
        symbols = _symbols()
        upstream = _upstream(symbols)
        with tempfile.TemporaryDirectory() as directory:
            evidence_root = Path(directory)
            _write_evidence(evidence_root, symbols)
            before = {
                path.relative_to(evidence_root).as_posix(): path.read_bytes()
                for path in evidence_root.rglob("*")
                if path.is_file()
            }
            meta_path = evidence_root / "meta.sqlite"
            with patch.object(service, "EVIDENCE_ROOT", evidence_root), patch.object(
                task_service, "SQLITE_META_PATH", meta_path
            ), patch(
                "server.services.tushare_production_store.validate_tushare_full_market_production_version",
                return_value=upstream,
            ) as verifier:
                get_response = TestClient(app).get(
                    "/api/factor-quant/full-market-industry-membership"
                )
                after_get = {
                    path.relative_to(evidence_root).as_posix(): path.read_bytes()
                    for path in evidence_root.rglob("*")
                    if path.is_file()
                }
                post_response = TestClient(app).post(
                    "/api/factor-quant/full-market-industry-membership-execution-request",
                    json={
                        "create_execution_request": True,
                        "acknowledge_no_provider_execution": False,
                        "request_nonce": str(uuid.uuid4()),
                    },
                )
            self.assertEqual(before, after_get)
            self.assertNotIn("meta.sqlite", after_get)
            self.assertTrue(get_response.json()["data"]["ready"])
            self.assertFalse(get_response.json()["data"]["external_calls_triggered"])
            request = post_response.json()["data"]["task"]["payload_safe"][
                "execution_request"
            ]
            self.assertFalse(request["request_ready"])
            self.assertEqual(
                request["status"],
                "full_market_industry_membership_execution_request_blocked",
            )
            self.assertFalse(request["provider_execution_triggered"])
            self.assertFalse(request["production_pointer_written"])
            self.assertEqual(verifier.call_count, 2)

    def test_radar_and_factor_upstream_require_industry_pointer(self) -> None:
        symbols = _symbols()
        upstream = _upstream(symbols)
        with tempfile.TemporaryDirectory() as directory, patch(
            "server.services.tushare_production_store.validate_tushare_full_market_production_version",
            return_value=upstream,
        ):
            from server.services import full_market_worker_service as worker

            result = worker._authoritative_provider_universe(
                Path(directory),
                minimum_universe_size=service.MINIMUM_ELIGIBLE_SYMBOLS,
                require_industry_membership=True,
            )
            self.assertFalse(result["ready"])
            self.assertFalse(result["industry_membership_verified"])
            self.assertIn(
                "authoritative_full_market_industry_membership_missing_or_invalid",
                result["blockers"],
            )

    def test_scalar_rows_and_object_industry_code_fail_closed(self) -> None:
        symbols = _symbols()
        universe_digest = service._digest(symbols)
        for attack in ("scalar_rows", "object_industry_code"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                paths = _write_evidence(root, symbols)
                artifact = json.loads(paths["artifact"].read_text(encoding="utf-8"))
                if attack == "scalar_rows":
                    artifact["rows"] = 1
                else:
                    artifact["rows"][0]["industry_code"] = {"not": "a-string"}
                paths["artifact"].write_bytes(service._canonical_bytes(artifact))
                _reseal_evidence(paths)
                result = service.validate_full_market_industry_membership(
                    root,
                    expected_symbols=symbols,
                    expected_universe_digest=universe_digest,
                    expected_validated_trade_date="20260717",
                )
                self.assertFalse(result["ready"])
                if attack == "scalar_rows":
                    self.assertIn(
                        "industry_artifact_rows_not_exact_objects",
                        result["blockers"],
                    )
                else:
                    self.assertIn(
                        "artifact_effective_dated_row_invalid",
                        result["blockers"],
                    )

    def test_null_version_and_missing_semantic_artifact_cannot_self_seal(self) -> None:
        symbols = _symbols()
        universe_digest = service._digest(symbols)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _write_evidence(root, symbols)
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            manifest["version_id"] = None
            paths["manifest"].write_bytes(service._canonical_bytes(manifest))
            paths["semantic"].unlink()
            _reseal_evidence(paths)
            result = service.validate_full_market_industry_membership(
                root,
                expected_symbols=symbols,
                expected_universe_digest=universe_digest,
                expected_validated_trade_date="20260717",
            )
            self.assertFalse(result["ready"])
            self.assertIn("industry_version_id_invalid", result["blockers"])
            self.assertIn(
                "industry_out_date_semantic_evidence_binding_invalid",
                result["blockers"],
            )

    def test_symlinked_industry_root_is_rejected_before_pointer_read(self) -> None:
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            evidence_root = Path(directory) / "evidence"
            outside = Path(directory) / "outside"
            evidence_root.mkdir()
            _write_evidence(outside, symbols)
            (evidence_root / service.INDUSTRY_ROOT_RELATIVE).symlink_to(
                outside / service.INDUSTRY_ROOT_RELATIVE,
                target_is_directory=True,
            )
            with patch.object(service, "_read_json", wraps=service._read_json) as reader:
                result = service.validate_full_market_industry_membership(
                    evidence_root,
                    expected_symbols=symbols,
                    expected_universe_digest=service._digest(symbols),
                    expected_validated_trade_date="20260717",
                )
            self.assertFalse(result["ready"])
            reader.assert_not_called()


class _PagedIndustryClient:
    def __init__(
        self,
        rows_by_partition: dict[str, list[dict]],
        *,
        failure_call: int = 0,
        failure: str = "",
        receipt_attack: str = "",
    ):
        self.rows_by_partition = rows_by_partition
        self.failure_call = failure_call
        self.failure = failure
        self.receipt_attack = receipt_attack
        self.calls: list[dict] = []
        self.receipts: dict[str, dict] = {}

    def get_index_member_all(self, **params):
        self.calls.append(dict(params))
        ordinal = len(self.calls)
        if self.failure_call == ordinal:
            return {"ok": False, "data": None, "error": self.failure}
        rows = self.rows_by_partition.get(params["is_new"], [])
        page = rows[params["offset"] : params["offset"] + params["limit"]]
        call_id = "fake-call-reused" if self.receipt_attack == "duplicate" else f"fake-call-{ordinal:04d}"
        completed = datetime.now(timezone.utc)
        if self.receipt_attack == "stale":
            completed -= timedelta(hours=1)
        receipt = {
            "schema_version": service.TRANSPORT_RECEIPT_SCHEMA_VERSION,
            "call_id": call_id,
            "api": service.SOURCE_API,
            "provider": "Tushare",
            "request_params_safe": dict(params),
            "sdk_method_invoked": True,
            "provider_response_received": True,
            "official_client_identity_verified": True,
            "issued_at_utc": (completed - timedelta(milliseconds=1)).isoformat().replace("+00:00", "Z"),
            "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
        }
        if self.receipt_attack == "wrong_params":
            receipt["request_params_safe"] = {**params, "offset": params["offset"] + 1}
        elif self.receipt_attack == "wrong_api":
            receipt["api"] = "daily"
        elif self.receipt_attack == "missing_field":
            receipt.pop("completed_at_utc")
        self.receipts[call_id] = receipt
        return {
            "ok": True,
            "data": page,
            "error": None,
            "transport_call_id": call_id,
        }

    def consume_transport_receipt(self, call_id, api):
        receipt = self.receipts.pop(call_id, None)
        return receipt if receipt and receipt["api"] == api else None


def _provider_rows(symbols: list[str]) -> list[dict]:
    return [
        {
            "l1_code": "801000",
            "l1_name": "一级",
            "l2_code": "801010",
            "l2_name": "二级",
            "l3_code": "801011",
            "l3_name": "三级",
            "ts_code": symbol,
            "name": f"fixture-{index}",
            "in_date": "20200101",
            "out_date": None,
            "is_new": "Y",
        }
        for index, symbol in enumerate(symbols)
    ]


class FullMarketIndustryProviderRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.trust_root, self.authority_path = _install_semantic_authority(self.stack)
        self.generation_signer = _install_generation_authority(self.stack)

    def tearDown(self) -> None:
        self.stack.close()

    def _request(self, root: Path, symbols: list[str]):
        upstream = _upstream(symbols)
        meta_path = root / "meta.sqlite"
        with patch.object(task_service, "SQLITE_META_PATH", meta_path), patch(
            "server.services.tushare_production_store.validate_tushare_full_market_production_version",
            return_value=upstream,
        ):
            task = service.create_full_market_industry_membership_execution_request(
                {
                    "create_execution_request": True,
                    "acknowledge_no_provider_execution": True,
                    "request_nonce": str(uuid.uuid4()),
                },
                evidence_root=root,
            )
        return task, upstream, meta_path

    def _run(
        self,
        root: Path,
        meta_path: Path,
        task: dict,
        upstream: dict,
        client,
        *,
        auto_attest: bool = True,
    ):
        payload = {
            "request_task_id": task["task_id"],
            "execute_provider_request": True,
            "acknowledge_external_tushare_call": True,
            "provider_api": service.SOURCE_API,
        }
        with patch(
            "server.services.tushare_production_store.validate_tushare_full_market_production_version",
            return_value=upstream,
        ), patch.object(
            provider_service,
            "_load_official_index_member_client",
            return_value=client,
        ):
            result = provider_service.run_full_market_industry_membership_provider_execution(
                payload,
                evidence_root=root,
                meta_path=meta_path,
            )
            if (
                auto_attest
                and result.get("payload_safe", {}).get("status")
                == "awaiting_external_generation_attestation"
            ):
                self.generation_signer.append(
                    result["payload_safe"]["generation_attestation_claims"]
                )
                result = provider_service.run_full_market_industry_membership_provider_execution(
                    payload,
                    evidence_root=root,
                    meta_path=meta_path,
                )
            return result

    def test_paginated_success_writes_verified_atomic_generation_pointer(self):
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, upstream, meta_path = self._request(root, symbols)
            client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
            result = self._run(root, meta_path, task, upstream, client)
            receipt = result["payload_safe"]
            verified = service.validate_full_market_industry_membership(
                root,
                expected_symbols=symbols,
                expected_universe_digest=upstream["universe_digest"],
                expected_validated_trade_date=upstream["validated_trade_date"],
            )
            pointer = json.loads(
                (root / service.INDUSTRY_ROOT_RELATIVE / service.POINTER_FILE).read_text()
            )
            legacy_last_good = root / service.INDUSTRY_ROOT_RELATIVE / "last_good.json"
        self.assertEqual(result["status"], "success", result)
        self.assertTrue(receipt["production_pointer_written"])
        self.assertTrue(verified["ready"], verified["blockers"])
        self.assertEqual(pointer["current_generation"], pointer["last_good_generation"])
        self.assertFalse(legacy_last_good.exists())
        self.assertEqual(pointer["schema_version"], service.PRODUCED_POINTER_SCHEMA_VERSION)
        self.assertEqual([row["row_count"] for row in result["call_ledger"]], [2000, 1000, 0])
        self.assertEqual({row["api"] for row in result["call_ledger"]}, {service.SOURCE_API})

    def test_generation_requires_external_signed_chain_before_pointer_promotion(self):
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, upstream, meta_path = self._request(root, symbols)
            client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
            staged = self._run(
                root,
                meta_path,
                task,
                upstream,
                client,
                auto_attest=False,
            )
            self.assertEqual(staged["status"], "failed")
            self.assertEqual(
                staged["payload_safe"]["status"],
                "awaiting_external_generation_attestation",
            )
            pointer_path = root / service.INDUSTRY_ROOT_RELATIVE / service.POINTER_FILE
            self.assertFalse(pointer_path.exists())
            self.assertEqual(
                json.loads(self.generation_signer.history_path.read_text())["events"],
                [],
            )
            self.assertTrue(
                (
                    root
                    / service.INDUSTRY_ROOT_RELATIVE
                    / "versions"
                    / staged["payload_safe"]["version_id"]
                    / "manifest.json"
                ).is_file()
            )
            calls_before = list(client.calls)
            self.generation_signer.append(
                staged["payload_safe"]["generation_attestation_claims"]
            )
            promoted = self._run(
                root,
                meta_path,
                task,
                upstream,
                client,
                auto_attest=False,
            )
            self.assertEqual(promoted["status"], "success", promoted)
            self.assertTrue(pointer_path.is_file())
            self.assertEqual(client.calls, calls_before)
            self.assertTrue(
                promoted["payload_safe"][
                    "resumed_staged_generation_without_provider_call"
                ]
            )

    def test_signed_generation_from_old_runtime_head_is_history_only(self):
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, upstream, meta_path = self._request(root, symbols)
            result = self._run(
                root,
                meta_path,
                task,
                upstream,
                _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []}),
            )
            self.assertEqual(result["status"], "success", result)
            pointer = json.loads(
                (
                    root
                    / service.INDUSTRY_ROOT_RELATIVE
                    / service.POINTER_FILE
                ).read_text()
            )
            manifest = json.loads(
                (
                    root
                    / service.INDUSTRY_ROOT_RELATIVE
                    / pointer["manifest_file"]
                ).read_text()
            )
            signed_head = manifest["producer_binding"]["producer_head_full"]
            changed_head = "f" * 40 if signed_head != "f" * 40 else "e" * 40
            historical = generation_trust.validate_generation_attestation(
                manifest,
                expected_previous_attestation_digest=pointer[
                    "generation_attestation_previous_digest"
                ],
                require_latest=False,
                head_mode="history",
                runtime_head_full="",
            )
            self.assertTrue(historical["ready"], historical["blockers"])
            with patch.object(
                service,
                "_current_head_full",
                return_value=changed_head,
            ):
                current = service.validate_full_market_industry_membership(
                    root,
                    expected_symbols=symbols,
                    expected_universe_digest=upstream["universe_digest"],
                    expected_validated_trade_date=upstream[
                        "validated_trade_date"
                    ],
                )
            self.assertFalse(current["ready"])
            self.assertIn(
                "industry_generation_attestation_runtime_head_mismatch",
                current["blockers"],
            )

    def test_staged_resume_rejects_request_and_manifest_from_old_head(self):
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, upstream, meta_path = self._request(root, symbols)
            client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
            staged = self._run(
                root,
                meta_path,
                task,
                upstream,
                client,
                auto_attest=False,
            )
            self.generation_signer.append(
                staged["payload_safe"]["generation_attestation_claims"]
            )
            signed_head = task["payload_safe"]["execution_request"]["head_full"]
            changed_head = "f" * 40 if signed_head != "f" * 40 else "e" * 40
            calls_before = list(client.calls)
            with patch.object(
                provider_service,
                "_current_head_full",
                return_value=changed_head,
            ), patch.object(
                evidence_writer,
                "_current_head_full",
                return_value=changed_head,
            ), patch.object(
                service,
                "_current_head_full",
                return_value=changed_head,
            ):
                blocked = self._run(
                    root,
                    meta_path,
                    task,
                    upstream,
                    client,
                    auto_attest=False,
                )
            self.assertEqual(blocked["status"], "failed")
            self.assertIn(
                "persisted_execution_request_head_mismatch",
                blocked["payload_safe"]["blockers"],
            )
            self.assertEqual(client.calls, calls_before)
            self.assertFalse(
                (root / service.INDUSTRY_ROOT_RELATIVE / service.POINTER_FILE).exists()
            )

    def test_generation_chain_replay_old_head_and_wrong_previous_fail_closed(self):
        symbols = _symbols()
        for attack in ("replay", "old_head", "wrong_previous"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as directory:
                self.generation_signer.reset()
                root = Path(directory)
                task, upstream, meta_path = self._request(root, symbols)
                client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
                staged = self._run(
                    root,
                    meta_path,
                    task,
                    upstream,
                    client,
                    auto_attest=False,
                )
                claims = staged["payload_safe"]["generation_attestation_claims"]
                if attack == "old_head":
                    self.generation_signer.append(
                        claims,
                        producer_head_full="0" * 40,
                    )
                elif attack == "wrong_previous":
                    self.generation_signer.append(
                        claims,
                        previous_attestation_digest="f" * 64,
                    )
                else:
                    self.generation_signer.append(claims)
                    self.generation_signer.append(claims)
                blocked = self._run(
                    root,
                    meta_path,
                    task,
                    upstream,
                    client,
                    auto_attest=False,
                )
                self.assertEqual(blocked["status"], "failed")
                self.assertEqual(
                    blocked["payload_safe"]["status"],
                    "awaiting_external_generation_attestation",
                )
                self.assertFalse(
                    (root / service.INDUSTRY_ROOT_RELATIVE / service.POINTER_FILE).exists()
                )

    def test_duplicate_overlap_permission_empty_and_partial_failure_preserve_last_good(self):
        symbols = _symbols()
        attacks = ("duplicate", "overlap", "permission", "empty", "partial")
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                first_task, upstream, meta_path = self._request(root, symbols)
                first_client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
                first = self._run(root, meta_path, first_task, upstream, first_client)
                self.assertEqual(first["status"], "success", first)
                pointer_path = root / service.INDUSTRY_ROOT_RELATIVE / service.POINTER_FILE
                before = pointer_path.read_bytes()
                second_task, upstream, meta_path = self._request(root, symbols)
                rows = _provider_rows(symbols)
                if attack == "duplicate":
                    rows.append(dict(rows[0]))
                elif attack == "overlap":
                    overlap = dict(rows[0])
                    overlap["in_date"] = "20210101"
                    overlap["l3_code"] = "801099"
                    rows.append(overlap)
                client = (
                    _PagedIndustryClient({"Y": [], "N": []}, failure_call=1, failure="permission denied")
                    if attack == "permission"
                    else _PagedIndustryClient({"Y": [], "N": []})
                    if attack == "empty"
                    else _PagedIndustryClient({"Y": rows, "N": []}, failure_call=2, failure="network failed")
                    if attack == "partial"
                    else _PagedIndustryClient({"Y": rows, "N": []})
                )
                result = self._run(root, meta_path, second_task, upstream, client)
                self.assertEqual(result["status"], "failed", result)
                self.assertEqual(pointer_path.read_bytes(), before)
                self.assertFalse(result["payload_safe"]["production_pointer_written"])
                if attack in {"permission", "empty", "partial"}:
                    self.assertTrue(result["call_ledger"])

    def test_replay_is_call_free_and_path_attack_is_blocked_before_client_load(self):
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, upstream, meta_path = self._request(root, symbols)
            first_client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
            first = self._run(root, meta_path, task, upstream, first_client)
            self.assertEqual(first["status"], "success", first)
            pointer_path = root / service.INDUSTRY_ROOT_RELATIVE / service.POINTER_FILE
            pointer_before = pointer_path.read_bytes()
            ledger_before = list(first["call_ledger"])
            database_before = meta_path.read_bytes()
            replay_client = _PagedIndustryClient({"Y": [], "N": []})
            replay = self._run(root, meta_path, task, upstream, replay_client)
            self.assertEqual(replay["status"], "success", replay)
            self.assertEqual(replay["task_id"], first["task_id"])
            self.assertEqual(replay["call_ledger"], ledger_before)
            self.assertEqual(pointer_path.read_bytes(), pointer_before)
            self.assertEqual(meta_path.read_bytes(), database_before)
            self.assertEqual(replay_client.calls, [])

            second_task, upstream, meta_path = self._request(root, symbols)
            with patch(
                "server.services.tushare_production_store.validate_tushare_full_market_production_version",
                return_value=upstream,
            ), patch.object(provider_service, "_load_official_index_member_client") as loader:
                blocked = provider_service.run_full_market_industry_membership_provider_execution(
                    {
                        "request_task_id": second_task["task_id"],
                        "execute_provider_request": True,
                        "acknowledge_external_tushare_call": True,
                        "provider_api": service.SOURCE_API,
                        "unexpected_path": "../outside.json",
                    },
                    evidence_root=root,
                    meta_path=meta_path,
                )
            self.assertEqual(blocked["status"], "failed")
            loader.assert_not_called()

            locks = root / service.INDUSTRY_ROOT_RELATIVE / "locks"
            locks.rmdir()
            outside = root / "outside-locks"
            outside.mkdir()
            locks.symlink_to(outside, target_is_directory=True)
            with patch.object(provider_service, "_load_official_index_member_client") as loader:
                blocked = self._run(
                    root,
                    meta_path,
                    second_task,
                    upstream,
                    loader,
                )
            self.assertEqual(blocked["status"], "failed")
            loader.assert_not_called()

    def test_concurrent_same_request_allows_only_one_provider_run(self):
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, upstream, meta_path = self._request(root, symbols)
            client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
            entered = threading.Event()
            release = threading.Event()
            original = client.get_index_member_all

            def delayed(**params):
                entered.set()
                release.wait(timeout=5)
                return original(**params)

            client.get_index_member_all = delayed
            results: list[dict] = []

            def invoke():
                results.append(self._run(root, meta_path, task, upstream, client))

            first = threading.Thread(target=invoke)
            first.start()
            self.assertTrue(entered.wait(timeout=5))
            second = threading.Thread(target=invoke)
            second.start()
            time.sleep(0.05)
            release.set()
            first.join(timeout=10)
            second.join(timeout=10)
            self.assertEqual(len(results), 2)
            self.assertEqual(sum(row["status"] == "success" for row in results), 1)
            self.assertEqual(len(client.calls), 3)

    def test_route_and_catalog_are_explicit_post_only_and_block_before_provider(self):
        catalog = task_service.build_task_catalog()
        route = "POST /api/factor-quant/full-market-industry-membership-provider-execution"
        self.assertIn(route, catalog["route_coverage"]["known_post_routes"])
        self.assertEqual(catalog["route_coverage"]["uncovered_post_routes"], [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            meta_path = root / "meta.sqlite"
            with patch.object(provider_service, "EVIDENCE_ROOT", root), patch.object(
                task_service,
                "SQLITE_META_PATH",
                meta_path,
            ), patch.object(provider_service, "_load_official_index_member_client") as loader:
                response = TestClient(app).post(
                    "/api/factor-quant/full-market-industry-membership-provider-execution",
                    json={
                        "request_task_id": "missing-request",
                        "execute_provider_request": True,
                        "acknowledge_external_tushare_call": True,
                    },
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["task"]["status"], "failed")
            loader.assert_not_called()

    def test_missing_or_forged_external_semantic_authority_never_loads_client(self):
        symbols = _symbols()
        authority_bytes = self.authority_path.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, upstream, meta_path = self._request(root, symbols)
            for attack in ("missing", "forged"):
                with self.subTest(attack=attack):
                    self.trust_root.chmod(0o755)
                    if self.authority_path.exists():
                        self.authority_path.chmod(0o644)
                    self.authority_path.write_bytes(authority_bytes)
                    if attack == "missing":
                        self.authority_path.unlink()
                    else:
                        envelope = json.loads(authority_bytes)
                        envelope["signature_base64"] = base64.b64encode(b"x" * 64).decode("ascii")
                        self.authority_path.write_bytes(service._canonical_bytes(envelope))
                        self.authority_path.chmod(0o444)
                    self.trust_root.chmod(0o555)
                    with patch(
                        "server.services.tushare_production_store.validate_tushare_full_market_production_version",
                        return_value=upstream,
                    ), patch.object(provider_service, "_load_official_index_member_client") as loader:
                        result = provider_service.run_full_market_industry_membership_provider_execution(
                            {
                                "request_task_id": task["task_id"],
                                "execute_provider_request": True,
                                "acknowledge_external_tushare_call": True,
                                "provider_api": service.SOURCE_API,
                            },
                            evidence_root=root,
                            meta_path=meta_path,
                        )
                    self.assertEqual(result["status"], "failed")
                    loader.assert_not_called()
            self.trust_root.chmod(0o755)
            if self.authority_path.exists():
                self.authority_path.chmod(0o644)
            self.authority_path.write_bytes(authority_bytes)
            self.authority_path.chmod(0o444)
            self.trust_root.chmod(0o555)

    def test_receipt_reuse_staleness_wrong_endpoint_params_and_shape_block(self):
        symbols = _symbols()
        for attack in ("duplicate", "stale", "wrong_params", "wrong_api", "missing_field"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                task, upstream, meta_path = self._request(root, symbols)
                client = _PagedIndustryClient(
                    {"Y": _provider_rows(symbols), "N": []},
                    receipt_attack=attack,
                )
                result = self._run(root, meta_path, task, upstream, client)
                self.assertEqual(result["status"], "failed", result)
                self.assertFalse(
                    (root / service.INDUSTRY_ROOT_RELATIVE / service.POINTER_FILE).exists()
                )

    def test_stage_replays_complete_ledger_and_raw_to_normalized_lineage(self):
        symbols = _symbols()
        for attack in ("fewer_ledger", "extra_ledger", "raw_mismatch", "normalized_mismatch"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                task, upstream, _ = self._request(root, symbols)
                client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
                collected, ledger, blockers = provider_collector._collect_provider_pages(client)
                self.assertEqual(blockers, [])
                raw_rows, normalized_rows, blockers = provider_collector._normalize_provider_rows(
                    collected,
                    symbols=symbols,
                    validated_trade_date=upstream["validated_trade_date"],
                )
                self.assertEqual(blockers, [])
                if attack == "fewer_ledger":
                    ledger = ledger[:-1]
                elif attack == "extra_ledger":
                    ledger.append(dict(ledger[-1]))
                elif attack == "raw_mismatch":
                    raw_rows[0] = {**raw_rows[0], "l3_code": "809999"}
                else:
                    normalized_rows[0] = {**normalized_rows[0], "industry_code": "809999"}
                promotion = evidence_writer._promote_provider_evidence(
                    evidence_root=root,
                    request_task_id=task["task_id"],
                    request=task["payload_safe"]["execution_request"],
                    provider={**upstream, "version_digest": upstream["version_digest"]},
                    semantic=service._validated_semantic_authority(),
                    raw_rows=raw_rows,
                    normalized_rows=normalized_rows,
                    call_ledger=ledger,
                )
                self.assertFalse(promotion["ready"], promotion)
                self.assertFalse(
                    (root / service.INDUSTRY_ROOT_RELATIVE / service.POINTER_FILE).exists()
                )

    def test_typed_request_tamper_writes_failed_task_without_provider_or_500(self):
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, upstream, meta_path = self._request(root, symbols)
            tampered = json.loads(json.dumps(task))
            request = tampered["payload_safe"]["execution_request"]
            request["scope"]["eligible_symbol_count"] = "3000"
            request["scope_digest"] = service._digest(request["scope"])
            request["request_digest"] = service._execution_request_digest(request)
            SQLiteMetaStore(meta_path).write_task_status(tampered)
            client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
            result = self._run(root, meta_path, tampered, upstream, client)
            self.assertEqual(result["status"], "failed", result)
            self.assertEqual(client.calls, [])
            persisted = SQLiteMetaStore(meta_path, read_only=True).read_task_status(result["task_id"])
            self.assertEqual(persisted["status"], "failed")

    def test_pointer_swap_failure_preserves_prior_generation_and_fails_closed(self):
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_task, upstream, meta_path = self._request(root, symbols)
            first = self._run(
                root,
                meta_path,
                first_task,
                upstream,
                _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []}),
            )
            self.assertEqual(first["status"], "success")
            pointer_path = root / service.INDUSTRY_ROOT_RELATIVE / service.POINTER_FILE
            pointer_before = pointer_path.read_bytes()
            second_task, upstream, meta_path = self._request(root, symbols)
            with patch.object(evidence_writer, "_atomic_write_bytes", side_effect=OSError("crash")):
                failed = self._run(
                    root,
                    meta_path,
                    second_task,
                    upstream,
                    _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []}),
                )
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(pointer_path.read_bytes(), pointer_before)
            recovered = service.validate_full_market_industry_membership(
                root,
                expected_symbols=symbols,
                expected_universe_digest=upstream["universe_digest"],
                expected_validated_trade_date=upstream["validated_trade_date"],
            )
            self.assertFalse(recovered["ready"])
            self.assertIn(
                "industry_generation_attestation_not_latest",
                recovered["blockers"],
            )

            third_task, upstream, meta_path = self._request(root, symbols)
            promoted = self._run(
                root,
                meta_path,
                third_task,
                upstream,
                _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []}),
            )
            self.assertEqual(promoted["status"], "success", promoted)
            promoted_pointer = json.loads(pointer_path.read_text())
            self.assertNotEqual(
                promoted_pointer["current_generation"],
                promoted_pointer["last_good_generation"],
            )
            prior_manifest_path = (
                root
                / service.INDUSTRY_ROOT_RELATIVE
                / promoted_pointer["last_good_manifest_file"]
            )
            prior_manifest = json.loads(prior_manifest_path.read_text())
            promoted_pointer_bytes = pointer_path.read_bytes()
            pointer_path.write_bytes(pointer_before)
            replayed_pointer = service.validate_full_market_industry_membership(
                root,
                expected_symbols=symbols,
                expected_universe_digest=upstream["universe_digest"],
                expected_validated_trade_date=upstream["validated_trade_date"],
            )
            self.assertFalse(replayed_pointer["ready"])
            self.assertIn(
                "industry_generation_attestation_not_latest",
                replayed_pointer["blockers"],
            )
            pointer_path.write_bytes(promoted_pointer_bytes)
            prior_raw_path = (
                root
                / service.INDUSTRY_ROOT_RELATIVE
                / prior_manifest["raw_artifact_file"]
            )
            prior_raw_bytes = prior_raw_path.read_bytes()
            prior_raw_path.write_bytes(prior_raw_bytes + b" ")
            damaged_recovery = service.validate_full_market_industry_membership(
                root,
                expected_symbols=symbols,
                expected_universe_digest=upstream["universe_digest"],
                expected_validated_trade_date=upstream["validated_trade_date"],
            )
            self.assertFalse(damaged_recovery["ready"])
            self.assertIn(
                "industry_generation_pointer_recovery_invalid",
                damaged_recovery["blockers"],
            )
            prior_raw_path.write_bytes(prior_raw_bytes)

            prior_manifest_bytes = prior_manifest_path.read_bytes()
            for field, replacement in (
                ("provider_scope_digest", "e" * 64),
                ("producer_head_full", "b" * 40),
                ("execution_request_digest", "c" * 64),
                ("semantic_authority_signature_sha256", "d" * 64),
            ):
                with self.subTest(resealed_last_good_field=field):
                    resealed_manifest = json.loads(prior_manifest_bytes)
                    resealed_manifest["producer_binding"][field] = replacement
                    resealed_manifest["producer_binding_digest"] = service._digest(
                        resealed_manifest["producer_binding"]
                    )
                    resealed_manifest["source_version"][
                        "producer_binding_digest"
                    ] = resealed_manifest["producer_binding_digest"]
                    resealed_manifest["source_version_digest"] = service._digest(
                        resealed_manifest["source_version"]
                    )
                    resealed_manifest["manifest_digest"] = service._digest(
                        {
                            key: value
                            for key, value in resealed_manifest.items()
                            if key != "manifest_digest"
                        }
                    )
                    prior_manifest_path.write_bytes(
                        service._canonical_bytes(resealed_manifest)
                    )
                    resealed_pointer = json.loads(promoted_pointer_bytes)
                    resealed_pointer["last_good_manifest_digest"] = (
                        resealed_manifest["manifest_digest"]
                    )
                    resealed_pointer["last_good_binding"]["manifest_digest"] = (
                        resealed_manifest["manifest_digest"]
                    )
                    resealed_pointer["pointer_digest"] = service._digest(
                        {
                            key: value
                            for key, value in resealed_pointer.items()
                            if key != "pointer_digest"
                        }
                    )
                    pointer_path.write_bytes(
                        service._canonical_bytes(resealed_pointer)
                    )
                    resealed = service.validate_full_market_industry_membership(
                        root,
                        expected_symbols=symbols,
                        expected_universe_digest=upstream["universe_digest"],
                        expected_validated_trade_date=upstream[
                            "validated_trade_date"
                        ],
                    )
                    self.assertFalse(resealed["ready"])
                    self.assertIn(
                        "industry_generation_pointer_recovery_invalid",
                        resealed["blockers"],
                    )
                    prior_manifest_path.write_bytes(prior_manifest_bytes)
                    pointer_path.write_bytes(promoted_pointer_bytes)

            split = json.loads(pointer_path.read_text())
            split["last_good_manifest_digest"] = "0" * 64
            split["pointer_digest"] = service._digest(
                {key: value for key, value in split.items() if key != "pointer_digest"}
            )
            pointer_path.write_bytes(service._canonical_bytes(split))
            blocked = service.validate_full_market_industry_membership(
                root,
                expected_symbols=symbols,
                expected_universe_digest=upstream["universe_digest"],
                expected_validated_trade_date=upstream["validated_trade_date"],
            )
            self.assertFalse(blocked["ready"])
            self.assertIn(
                "industry_generation_pointer_recovery_binding_invalid",
                blocked["blockers"],
            )


if __name__ == "__main__":
    unittest.main()
