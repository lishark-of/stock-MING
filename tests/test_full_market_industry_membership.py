from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from server.services import full_market_industry_provider_service as provider_service
from server.services import full_market_industry_service as service
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


class _PagedIndustryClient:
    def __init__(self, rows_by_partition: dict[str, list[dict]], *, failure_call: int = 0, failure: str = ""):
        self.rows_by_partition = rows_by_partition
        self.failure_call = failure_call
        self.failure = failure
        self.calls: list[dict] = []
        self.receipts: dict[str, dict] = {}

    def get_index_member_all(self, **params):
        self.calls.append(dict(params))
        ordinal = len(self.calls)
        if self.failure_call == ordinal:
            return {"ok": False, "data": None, "error": self.failure}
        rows = self.rows_by_partition.get(params["is_new"], [])
        page = rows[params["offset"] : params["offset"] + params["limit"]]
        call_id = f"fake-{ordinal}"
        self.receipts[call_id] = {
            "api": service.SOURCE_API,
            "sdk_method_invoked": True,
            "provider_response_received": True,
            "official_client_identity_verified": True,
        }
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


def _write_semantic_only(evidence_root: Path) -> str:
    root = evidence_root / service.INDUSTRY_ROOT_RELATIVE
    relative = "semantics/out-date-v1.json"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    content = {
        "field": "out_date",
        "interval_convention": "effective_from_inclusive_effective_to_exclusive",
        "non_null_boundary": "first_excluded_trade_date",
        "null_meaning": "membership_current_at_validated_trade_date",
    }
    evidence = {
        "schema_version": service.SEMANTIC_EVIDENCE_SCHEMA_VERSION,
        "status": "independently_validated",
        "source_api": service.SOURCE_API,
        "source_scope": service.SOURCE_SCOPE,
        "source_reference": "independent-local-provider-contract:index_member_all.out_date",
        "endpoint_field": "out_date",
        "resolved_semantics": service.RESOLVED_OUT_DATE_SEMANTICS,
        "validation_method": "independent_local_documentation_and_fixture_review",
        "content": content,
        "content_digest": service._digest(content),
    }
    path.write_bytes(service._canonical_bytes(evidence))
    return relative


class FullMarketIndustryProviderRunnerTests(unittest.TestCase):
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

    @staticmethod
    def _run(root: Path, meta_path: Path, task: dict, upstream: dict, client, semantic_file: str):
        payload = {
            "request_task_id": task["task_id"],
            "execute_provider_request": True,
            "acknowledge_external_tushare_call": True,
            "provider_api": service.SOURCE_API,
            "semantic_evidence_file": semantic_file,
        }
        with patch(
            "server.services.tushare_production_store.validate_tushare_full_market_production_version",
            return_value=upstream,
        ), patch.object(
            provider_service,
            "_load_official_index_member_client",
            return_value=client,
        ):
            return provider_service.run_full_market_industry_membership_provider_execution(
                payload,
                evidence_root=root,
                meta_path=meta_path,
            )

    def test_paginated_success_writes_verified_v3_current_and_last_good(self):
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            semantic_file = _write_semantic_only(root)
            task, upstream, meta_path = self._request(root, symbols)
            client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
            result = self._run(root, meta_path, task, upstream, client, semantic_file)
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
            last_good = json.loads(
                (root / service.INDUSTRY_ROOT_RELATIVE / "last_good.json").read_text()
            )
        self.assertEqual(result["status"], "success", result)
        self.assertTrue(receipt["production_pointer_written"])
        self.assertTrue(verified["ready"], verified["blockers"])
        self.assertEqual(pointer, last_good)
        self.assertEqual(pointer["schema_version"], service.PRODUCED_POINTER_SCHEMA_VERSION)
        self.assertEqual([row["row_count"] for row in result["call_ledger"]], [2000, 1000, 0])
        self.assertEqual({row["api"] for row in result["call_ledger"]}, {service.SOURCE_API})

    def test_duplicate_overlap_permission_empty_and_partial_failure_preserve_last_good(self):
        symbols = _symbols()
        attacks = ("duplicate", "overlap", "permission", "empty", "partial")
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                semantic_file = _write_semantic_only(root)
                first_task, upstream, meta_path = self._request(root, symbols)
                first_client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
                first = self._run(root, meta_path, first_task, upstream, first_client, semantic_file)
                self.assertEqual(first["status"], "success", first)
                pointer_path = root / service.INDUSTRY_ROOT_RELATIVE / "last_good.json"
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
                result = self._run(root, meta_path, second_task, upstream, client, semantic_file)
                self.assertEqual(result["status"], "failed", result)
                self.assertEqual(pointer_path.read_bytes(), before)
                self.assertFalse(result["payload_safe"]["production_pointer_written"])
                if attack in {"permission", "empty", "partial"}:
                    self.assertTrue(result["call_ledger"])

    def test_replay_is_call_free_and_path_attack_is_blocked_before_client_load(self):
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            semantic_file = _write_semantic_only(root)
            task, upstream, meta_path = self._request(root, symbols)
            first_client = _PagedIndustryClient({"Y": _provider_rows(symbols), "N": []})
            first = self._run(root, meta_path, task, upstream, first_client, semantic_file)
            self.assertEqual(first["status"], "success", first)
            replay_client = _PagedIndustryClient({"Y": [], "N": []})
            replay = self._run(root, meta_path, task, upstream, replay_client, semantic_file)
            self.assertEqual(replay["status"], "success", replay)
            self.assertTrue(replay["payload_safe"]["replay"])
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
                        "semantic_evidence_file": "../outside.json",
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
                    semantic_file,
                )
            self.assertEqual(blocked["status"], "failed")
            loader.assert_not_called()

    def test_concurrent_same_request_allows_only_one_provider_run(self):
        symbols = _symbols()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            semantic_file = _write_semantic_only(root)
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
                results.append(self._run(root, meta_path, task, upstream, client, semantic_file))

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


if __name__ == "__main__":
    unittest.main()
