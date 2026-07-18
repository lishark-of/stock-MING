from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from server.services import full_market_industry_service as service
from server.services import task_service


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
    semantic_content = {
        "field": "out_date",
        "interval_convention": "effective_from_inclusive_effective_to_exclusive",
        "non_null_boundary": "first_excluded_trade_date",
        "null_meaning": "membership_current_at_validated_trade_date",
    }
    semantic = {
        "schema_version": service.SEMANTIC_EVIDENCE_SCHEMA_VERSION,
        "status": "independently_validated",
        "source_api": service.SOURCE_API,
        "source_scope": service.SOURCE_SCOPE,
        "source_reference": "local-test-provider-contract:index_member_all.out_date",
        "endpoint_field": "out_date",
        "resolved_semantics": service.RESOLVED_OUT_DATE_SEMANTICS,
        "validation_method": "independent_local_documentation_and_fixture_review",
        "content": semantic_content,
        "content_digest": service._digest(semantic_content),
    }
    semantic_path.write_bytes(service._canonical_bytes(semantic))
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
                "industry_out_date_semantic_evidence_invalid",
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


if __name__ == "__main__":
    unittest.main()
