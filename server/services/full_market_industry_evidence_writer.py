from __future__ import annotations

import datetime as dt
import hashlib
import os
import shutil
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore

from . import task_service
from . import full_market_industry_generation_attestation as generation_trust
from .full_market_industry_service import (
    ARTIFACT_SCHEMA_VERSION,
    CALL_LEDGER_SCHEMA_VERSION,
    INDUSTRY_ROOT_RELATIVE,
    POINTER_FILE,
    PRODUCED_MANIFEST_SCHEMA_VERSION,
    PRODUCED_POINTER_SCHEMA_VERSION,
    PRODUCED_SOURCE_VERSION_SCHEMA_VERSION,
    PRODUCER_BINDING_SCHEMA_VERSION,
    RAW_ARTIFACT_SCHEMA_VERSION,
    REQUIRED_EXCHANGES,
    RESOLVED_OUT_DATE_SEMANTICS,
    SCOPE_SCHEMA_VERSION,
    SEMANTIC_EVIDENCE_SCHEMA_VERSION,
    SOURCE_API,
    SOURCE_SCOPE,
    _canonical_bytes,
    _current_head_full,
    _digest,
    _generation_binding,
    _read_json,
    validate_full_market_industry_membership,
)


PROVIDER_EXECUTION_TASK_TYPE = "run_full_market_industry_membership_provider_execution"


def _fsync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_fsync(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _provider_execution_task(
    *,
    request_digest: str,
    payload: Mapping[str, Any],
    status: str,
    step: str,
    call_ledger: list[dict[str, Any]],
    meta_path: Path,
    error: str = "",
) -> dict[str, Any]:
    base_task_id = f"industry-provider-{request_digest[:20] or 'blocked'}"
    task_id = (
        base_task_id
        if status == "success"
        else f"{base_task_id}-{_digest({'step': step, 'error': error, 'payload': payload})[:12]}"
    )
    task = task_service.build_task_record(
        PROVIDER_EXECUTION_TASK_TYPE,
        task_id=task_id,
        output_packet_key="command_center_3_full_market_industry_membership_provider_execution",
        payload=dict(payload),
        status=status,
        progress=1.0,
        current_step=step,
        warnings=[
            "explicit_POST_only_index_member_all_provider_execution",
            "out_date_semantics_require_independent_evidence_and_are_never_guessed",
        ],
        call_ledger=call_ledger,
    )
    task["backend"] = "explicit_post_scope_bound_index_member_all_runner"
    task["error_message_safe"] = error
    task["external_calls_triggered"] = any(
        row.get("external_calls_triggered") is True for row in call_ledger
    )
    task["tushare_called"] = any(
        row.get("tushare_called") is True for row in call_ledger
    )
    SQLiteMetaStore(meta_path).write_task_status(task)
    return task


def _resume_attested_provider_evidence(
    *,
    evidence_root: Path,
    request: Mapping[str, Any],
    provider: Mapping[str, Any],
    semantic: Mapping[str, Any],
) -> dict[str, Any]:
    root = evidence_root / INDUSTRY_ROOT_RELATIVE
    request_digest = str(request.get("request_digest") or "")
    prefix = f"industry-{provider.get('validated_trade_date')}-{request_digest[:12]}-"
    versions_root = root / "versions"
    candidates = (
        sorted(
            path
            for path in versions_root.iterdir()
            if path.is_dir() and not path.is_symlink() and path.name.startswith(prefix)
        )
        if versions_root.is_dir() and not versions_root.is_symlink()
        else []
    )
    if not candidates:
        return {"ready": False, "status": "no_staged_generation"}
    if len(candidates) != 1:
        return {"ready": False, "status": "staged_generation_set_ambiguous"}
    manifest = _read_json(candidates[0] / "manifest.json")
    manifest = dict(manifest) if isinstance(manifest, Mapping) else {}
    producer_binding = (
        manifest.get("producer_binding")
        if type(manifest.get("producer_binding")) is dict
        else {}
    )
    if (
        manifest.get("version_id") != candidates[0].name
        or producer_binding.get("execution_request_digest") != request_digest
        or producer_binding.get("execution_request_scope_digest")
        != request.get("scope_digest")
        or producer_binding.get("provider_scope_digest") != provider.get("scope_hash")
        or producer_binding.get("provider_version_digest")
        != provider.get("version_digest")
        or manifest.get("universe_digest") != provider.get("universe_digest")
        or manifest.get("validated_trade_date") != provider.get("validated_trade_date")
        or manifest.get("semantic_evidence_sha256") != semantic.get("sha256")
        or producer_binding.get("semantic_authority_signature_sha256")
        != semantic.get("signature_sha256")
    ):
        return {"ready": False, "status": "staged_generation_binding_invalid"}
    previous = validate_full_market_industry_membership(
        evidence_root,
        expected_symbols=provider.get("symbols"),
        expected_universe_digest=provider.get("universe_digest"),
        expected_validated_trade_date=provider.get("validated_trade_date"),
        _generation_attestation_must_be_latest=False,
    )
    previous_pointer_value = _read_json(root / POINTER_FILE)
    previous_pointer = (
        dict(previous_pointer_value)
        if previous.get("ready") is True
        and isinstance(previous_pointer_value, Mapping)
        and previous_pointer_value.get("schema_version")
        == PRODUCED_POINTER_SCHEMA_VERSION
        else {}
    )
    pointer_previous_attestation = (
        str(previous_pointer.get("generation_attestation_digest") or "")
        if previous_pointer
        else generation_trust.ZERO_DIGEST
    )
    attestation_probe = generation_trust.validate_generation_attestation(
        manifest,
        expected_previous_attestation_digest=pointer_previous_attestation,
        require_latest=True,
    )
    previous_attestation = str(
        attestation_probe.get("previous_attestation_digest")
        if attestation_probe.get("attestation_digest")
        else attestation_probe.get("history_head_digest")
        or generation_trust.ZERO_DIGEST
    )
    attestation = generation_trust.validate_generation_attestation(
        manifest,
        expected_previous_attestation_digest=previous_attestation,
        require_latest=True,
    )
    if attestation.get("ready") is not True:
        return {
            "ready": False,
            "status": "awaiting_external_generation_attestation",
            "version_id": manifest.get("version_id"),
            "manifest_digest": manifest.get("manifest_digest"),
            "generation_attestation_claims": attestation.get("claims"),
            "generation_attestation_blockers": attestation.get("blockers"),
        }
    pointer = {
        "schema_version": PRODUCED_POINTER_SCHEMA_VERSION,
        "current_generation": manifest.get("version_id"),
        "version_id": manifest.get("version_id"),
        "manifest_file": f"versions/{manifest.get('version_id')}/manifest.json",
        "manifest_digest": manifest.get("manifest_digest"),
        "artifact_sha256": manifest.get("artifact_sha256"),
        "raw_artifact_sha256": manifest.get("raw_artifact_sha256"),
        "call_ledger_sha256": manifest.get("call_ledger_sha256"),
        "producer_binding_digest": manifest.get("producer_binding_digest"),
        "execution_request_digest": producer_binding.get("execution_request_digest"),
        "generation_attestation_digest": attestation.get("attestation_digest"),
        "generation_attestation_previous_digest": previous_attestation,
        "producer_head_full": producer_binding.get("producer_head_full"),
        "provider_scope_digest": producer_binding.get("provider_scope_digest"),
        "provider_version_digest": producer_binding.get("provider_version_digest"),
        "scope_digest": manifest.get("scope_digest"),
        "source_version_digest": manifest.get("source_version_digest"),
        "semantic_evidence_sha256": manifest.get("semantic_evidence_sha256"),
        "universe_digest": manifest.get("universe_digest"),
        "validated_trade_date": manifest.get("validated_trade_date"),
        "as_of_date": manifest.get("as_of_date"),
        "last_good_generation": manifest.get("version_id"),
        "last_good_manifest_file": f"versions/{manifest.get('version_id')}/manifest.json",
        "last_good_manifest_digest": manifest.get("manifest_digest"),
        "last_good_generation_attestation_digest": attestation.get(
            "attestation_digest"
        ),
    }
    pointer["last_good_binding"] = _generation_binding(pointer)
    if previous_pointer:
        pointer.update(
            {
                "last_good_generation": previous_pointer["current_generation"],
                "last_good_manifest_file": previous_pointer["manifest_file"],
                "last_good_manifest_digest": previous_pointer["manifest_digest"],
                "last_good_generation_attestation_digest": previous_pointer[
                    "generation_attestation_digest"
                ],
                "last_good_binding": _generation_binding(previous_pointer),
            }
        )
    pointer["pointer_digest"] = _digest(pointer)
    _atomic_write_bytes(root / POINTER_FILE, _canonical_bytes(pointer))
    verified = validate_full_market_industry_membership(
        evidence_root,
        expected_symbols=provider.get("symbols"),
        expected_universe_digest=provider.get("universe_digest"),
        expected_validated_trade_date=provider.get("validated_trade_date"),
    )
    ledger = _read_json(candidates[0] / "call-ledger.json")
    ledger_rows = ledger.get("rows") if type(ledger) is dict else []
    if verified.get("ready") is not True or type(ledger_rows) is not list:
        return {
            "ready": False,
            "status": "industry_generation_pointer_readback_failed_closed",
        }
    return {
        "ready": True,
        "status": "full_market_industry_membership_provider_execution_complete",
        "version_id": manifest.get("version_id"),
        "pointer_digest": pointer["pointer_digest"],
        "manifest_digest": manifest.get("manifest_digest"),
        "artifact_sha256": manifest.get("artifact_sha256"),
        "raw_artifact_sha256": manifest.get("raw_artifact_sha256"),
        "call_ledger_sha256": manifest.get("call_ledger_sha256"),
        "producer_binding_digest": manifest.get("producer_binding_digest"),
        "generation_attestation_digest": attestation.get("attestation_digest"),
        "validated": verified,
        "call_ledger": [dict(row) for row in ledger_rows if type(row) is dict],
        "resumed_staged_generation_without_provider_call": True,
    }


def _promote_provider_evidence(
    *,
    evidence_root: Path,
    request_task_id: str,
    request: Mapping[str, Any],
    provider: Mapping[str, Any],
    semantic: Mapping[str, Any],
    raw_rows: list[dict[str, Any]],
    normalized_rows: list[dict[str, Any]],
    call_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    root = evidence_root / INDUSTRY_ROOT_RELATIVE
    request_digest = str(request.get("request_digest") or "")
    raw_artifact = {
        "schema_version": RAW_ARTIFACT_SCHEMA_VERSION,
        "rows": raw_rows,
    }
    artifact = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "rows": normalized_rows,
    }
    ledger_artifact = {
        "schema_version": CALL_LEDGER_SCHEMA_VERSION,
        "rows": call_ledger,
        "ledger_digest": _digest(call_ledger),
    }
    raw_bytes = _canonical_bytes(raw_artifact)
    artifact_bytes = _canonical_bytes(artifact)
    ledger_bytes = _canonical_bytes(ledger_artifact)
    raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    ledger_sha256 = hashlib.sha256(ledger_bytes).hexdigest()
    version_id = (
        f"industry-{provider.get('validated_trade_date')}-"
        f"{request_digest[:12]}-{artifact_sha256[:12]}"
    )
    version_relative = Path("versions") / version_id
    raw_relative = version_relative / "raw.json"
    artifact_relative = version_relative / "artifact.json"
    ledger_relative = version_relative / "call-ledger.json"
    authority_relative = version_relative / "semantic-authority.json"
    manifest_relative = version_relative / "manifest.json"
    scope = {
        "schema_version": SCOPE_SCHEMA_VERSION,
        "source_api": SOURCE_API,
        "source_scope": SOURCE_SCOPE,
        "eligible_symbol_count": len(provider.get("symbols") or []),
        "exchanges": list(REQUIRED_EXCHANGES),
        "universe_digest": provider.get("universe_digest"),
        "validated_trade_date": provider.get("validated_trade_date"),
        "as_of_date": provider.get("validated_trade_date"),
    }
    scope_digest = _digest(scope)
    observed_at_utc = (
        dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    producer_binding = {
        "schema_version": PRODUCER_BINDING_SCHEMA_VERSION,
        "execution_request_task_id": request_task_id,
        "execution_request_digest": request_digest,
        "execution_request_scope_digest": request.get("scope_digest"),
        "producer_head_full": _current_head_full(),
        "provider_scope_digest": provider.get("scope_hash"),
        "provider_version_digest": provider.get("version_digest"),
        "universe_digest": provider.get("universe_digest"),
        "validated_trade_date": provider.get("validated_trade_date"),
        "raw_artifact_sha256": raw_sha256,
        "artifact_sha256": artifact_sha256,
        "semantic_evidence_sha256": semantic.get("sha256"),
        "call_ledger_sha256": ledger_sha256,
        "call_ledger_digest": ledger_artifact["ledger_digest"],
        "collection_observed_at_utc": observed_at_utc,
        "semantic_authority_signature_sha256": semantic.get("signature_sha256"),
    }
    producer_binding_digest = _digest(producer_binding)
    source_version = {
        "schema_version": PRODUCED_SOURCE_VERSION_SCHEMA_VERSION,
        "version_id": version_id,
        "source_api": SOURCE_API,
        "source_scope": SOURCE_SCOPE,
        "scope_digest": scope_digest,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_sha256": artifact_sha256,
        "semantic_evidence_sha256": semantic.get("sha256"),
        "raw_artifact_schema_version": RAW_ARTIFACT_SCHEMA_VERSION,
        "raw_artifact_sha256": raw_sha256,
        "call_ledger_schema_version": CALL_LEDGER_SCHEMA_VERSION,
        "call_ledger_sha256": ledger_sha256,
        "producer_binding_digest": producer_binding_digest,
    }
    manifest = {
        "schema_version": PRODUCED_MANIFEST_SCHEMA_VERSION,
        "status": "full_market_industry_membership_verified",
        "version_id": version_id,
        "source_api": SOURCE_API,
        "source_scope": SOURCE_SCOPE,
        "scope": scope,
        "scope_digest": scope_digest,
        "source_version": source_version,
        "source_version_digest": _digest(source_version),
        "artifact_file": artifact_relative.as_posix(),
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_sha256": artifact_sha256,
        "artifact_row_count": len(normalized_rows),
        "raw_artifact_file": raw_relative.as_posix(),
        "raw_artifact_schema_version": RAW_ARTIFACT_SCHEMA_VERSION,
        "raw_artifact_sha256": raw_sha256,
        "raw_artifact_row_count": len(raw_rows),
        "call_ledger_file": ledger_relative.as_posix(),
        "call_ledger_schema_version": CALL_LEDGER_SCHEMA_VERSION,
        "call_ledger_sha256": ledger_sha256,
        "call_ledger_call_count": len(call_ledger),
        "producer_binding": producer_binding,
        "producer_binding_digest": producer_binding_digest,
        "universe_digest": provider.get("universe_digest"),
        "eligible_symbol_count": len(provider.get("symbols") or []),
        "exchanges": list(REQUIRED_EXCHANGES),
        "validated_trade_date": provider.get("validated_trade_date"),
        "as_of_date": provider.get("validated_trade_date"),
        "out_date_semantics": RESOLVED_OUT_DATE_SEMANTICS,
        "out_date_semantics_validated": True,
        "out_date_semantics_evidence_digest": semantic.get("sha256"),
        "semantic_evidence_file": authority_relative.as_posix(),
        "semantic_evidence_schema_version": SEMANTIC_EVIDENCE_SCHEMA_VERSION,
        "semantic_evidence_sha256": semantic.get("sha256"),
    }
    manifest["manifest_digest"] = _digest(manifest)
    previous_validation = validate_full_market_industry_membership(
        evidence_root,
        expected_symbols=provider.get("symbols"),
        expected_universe_digest=provider.get("universe_digest"),
        expected_validated_trade_date=provider.get("validated_trade_date"),
    )
    previous_pointer = _read_json(root / POINTER_FILE)
    previous_pointer = (
        dict(previous_pointer)
        if previous_validation.get("ready") is True
        and isinstance(previous_pointer, Mapping)
        and previous_pointer.get("schema_version") == PRODUCED_POINTER_SCHEMA_VERSION
        else {}
    )
    pointer_previous_attestation = (
        str(previous_pointer.get("generation_attestation_digest") or "")
        if previous_pointer
        else generation_trust.ZERO_DIGEST
    )
    attestation_probe = generation_trust.validate_generation_attestation(
        manifest,
        expected_previous_attestation_digest=pointer_previous_attestation,
        require_latest=True,
    )
    expected_previous_attestation = str(
        attestation_probe.get("previous_attestation_digest")
        if attestation_probe.get("attestation_digest")
        else attestation_probe.get("history_head_digest")
        or generation_trust.ZERO_DIGEST
    )
    generation_attestation = generation_trust.validate_generation_attestation(
        manifest,
        expected_previous_attestation_digest=expected_previous_attestation,
        require_latest=True,
    )
    pointer = {
        "schema_version": PRODUCED_POINTER_SCHEMA_VERSION,
        "current_generation": version_id,
        "version_id": version_id,
        "manifest_file": manifest_relative.as_posix(),
        "manifest_digest": manifest["manifest_digest"],
        "artifact_sha256": artifact_sha256,
        "raw_artifact_sha256": raw_sha256,
        "call_ledger_sha256": ledger_sha256,
        "producer_binding_digest": producer_binding_digest,
        "execution_request_digest": request_digest,
        "generation_attestation_digest": generation_attestation.get(
            "attestation_digest"
        ),
        "generation_attestation_previous_digest": expected_previous_attestation,
        "producer_head_full": producer_binding["producer_head_full"],
        "provider_scope_digest": producer_binding["provider_scope_digest"],
        "provider_version_digest": producer_binding["provider_version_digest"],
        "scope_digest": scope_digest,
        "source_version_digest": manifest["source_version_digest"],
        "semantic_evidence_sha256": semantic.get("sha256"),
        "universe_digest": provider.get("universe_digest"),
        "validated_trade_date": provider.get("validated_trade_date"),
        "as_of_date": provider.get("validated_trade_date"),
        "last_good_generation": version_id,
        "last_good_generation_attestation_digest": generation_attestation.get(
            "attestation_digest"
        ),
        "last_good_manifest_file": manifest_relative.as_posix(),
        "last_good_manifest_digest": manifest["manifest_digest"],
    }
    pointer["last_good_binding"] = _generation_binding(pointer)
    pointer["pointer_digest"] = _digest(pointer)
    stage_evidence = evidence_root / f".industry-stage-{uuid.uuid4().hex}"
    stage_root = stage_evidence / INDUSTRY_ROOT_RELATIVE
    stage_version = stage_root / version_relative
    final_version = root / version_relative
    try:
        if stage_evidence.is_symlink() or root.is_symlink() or evidence_root.is_symlink():
            return {"ready": False, "status": "industry_evidence_root_unsafe"}
        stage_version.mkdir(parents=True, exist_ok=False)
        _write_fsync(
            stage_root / authority_relative,
            Path(str(semantic.get("path"))).read_bytes(),
        )
        _write_fsync(stage_root / raw_relative, raw_bytes)
        _write_fsync(stage_root / artifact_relative, artifact_bytes)
        _write_fsync(stage_root / ledger_relative, ledger_bytes)
        _write_fsync(stage_root / manifest_relative, _canonical_bytes(manifest))
        _write_fsync(stage_root / POINTER_FILE, _canonical_bytes(pointer))
        _fsync_dir(stage_version)
        _fsync_dir(stage_root)
        staged = validate_full_market_industry_membership(
            stage_evidence,
            expected_symbols=provider.get("symbols"),
            expected_universe_digest=provider.get("universe_digest"),
            expected_validated_trade_date=provider.get("validated_trade_date"),
            _require_generation_attestation=False,
        )
        if staged.get("ready") is not True:
            return {
                "ready": False,
                "status": "industry_staged_evidence_validation_failed",
                "blockers": staged.get("blockers") or [],
            }
        final_version.parent.mkdir(parents=True, exist_ok=True)
        if final_version.exists():
            return {"ready": False, "status": "industry_immutable_version_collision"}
        os.replace(stage_version, final_version)
        _fsync_dir(final_version.parent)
        if generation_attestation.get("ready") is not True:
            return {
                "ready": False,
                "status": "awaiting_external_generation_attestation",
                "version_id": version_id,
                "manifest_digest": manifest["manifest_digest"],
                "generation_attestation_claims": generation_attestation.get(
                    "claims"
                ),
                "generation_attestation_blockers": generation_attestation.get(
                    "blockers"
                ),
                "production_pointer_written": False,
            }
        current_path = root / POINTER_FILE
        final_pointer = dict(pointer)
        if previous_pointer:
            final_pointer.update(
                {
                    "last_good_generation": previous_pointer["current_generation"],
                    "last_good_manifest_file": previous_pointer["manifest_file"],
                    "last_good_manifest_digest": previous_pointer["manifest_digest"],
                    "last_good_generation_attestation_digest": previous_pointer[
                        "generation_attestation_digest"
                    ],
                    "last_good_binding": _generation_binding(previous_pointer),
                }
            )
            final_pointer["pointer_digest"] = _digest(
                {
                    key: value
                    for key, value in final_pointer.items()
                    if key != "pointer_digest"
                }
            )
        _atomic_write_bytes(current_path, _canonical_bytes(final_pointer))
        verified = validate_full_market_industry_membership(
            evidence_root,
            expected_symbols=provider.get("symbols"),
            expected_universe_digest=provider.get("universe_digest"),
            expected_validated_trade_date=provider.get("validated_trade_date"),
        )
        if verified.get("ready") is not True or _read_json(current_path) != final_pointer:
            return {
                "ready": False,
                "status": "industry_generation_pointer_readback_failed_closed",
            }
        return {
            "ready": True,
            "status": "full_market_industry_membership_provider_execution_complete",
            "version_id": version_id,
            "pointer_digest": final_pointer["pointer_digest"],
            "manifest_digest": manifest["manifest_digest"],
            "artifact_sha256": artifact_sha256,
            "raw_artifact_sha256": raw_sha256,
            "call_ledger_sha256": ledger_sha256,
            "producer_binding_digest": producer_binding_digest,
            "validated": verified,
        }
    finally:
        shutil.rmtree(stage_evidence, ignore_errors=True)
