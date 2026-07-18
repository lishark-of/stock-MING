from __future__ import annotations

import hashlib, os, shutil, uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore

from . import task_service
from .full_market_industry_service import (
    ARTIFACT_SCHEMA_VERSION, CALL_LEDGER_SCHEMA_VERSION, INDUSTRY_ROOT_RELATIVE,
    POINTER_FILE, PRODUCED_MANIFEST_SCHEMA_VERSION, PRODUCED_POINTER_SCHEMA_VERSION,
    PRODUCED_SOURCE_VERSION_SCHEMA_VERSION, PRODUCER_BINDING_SCHEMA_VERSION,
    RAW_ARTIFACT_SCHEMA_VERSION, REQUIRED_EXCHANGES, RESOLVED_OUT_DATE_SEMANTICS,
    SCOPE_SCHEMA_VERSION, SEMANTIC_EVIDENCE_SCHEMA_VERSION, SOURCE_API, SOURCE_SCOPE,
    _canonical_bytes, _current_head_full, _digest, _read_json,
    validate_full_market_industry_membership,
)
PROVIDER_EXECUTION_TASK_TYPE = "run_full_market_industry_membership_provider_execution"
def _atomic_write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
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
    task = task_service.build_task_record(
        PROVIDER_EXECUTION_TASK_TYPE,
        task_id=f"industry-provider-{request_digest[:20] or 'blocked'}",
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
        "semantic_evidence_file": semantic.get("relative_file"),
        "semantic_evidence_schema_version": SEMANTIC_EVIDENCE_SCHEMA_VERSION,
        "semantic_evidence_sha256": semantic.get("sha256"),
    }
    manifest["manifest_digest"] = _digest(manifest)
    pointer = {
        "schema_version": PRODUCED_POINTER_SCHEMA_VERSION,
        "version_id": version_id,
        "manifest_file": manifest_relative.as_posix(),
        "manifest_digest": manifest["manifest_digest"],
        "artifact_sha256": artifact_sha256,
        "raw_artifact_sha256": raw_sha256,
        "call_ledger_sha256": ledger_sha256,
        "producer_binding_digest": producer_binding_digest,
        "execution_request_digest": request_digest,
        "producer_head_full": producer_binding["producer_head_full"],
        "provider_scope_digest": producer_binding["provider_scope_digest"],
        "provider_version_digest": producer_binding["provider_version_digest"],
        "scope_digest": scope_digest,
        "source_version_digest": manifest["source_version_digest"],
        "semantic_evidence_sha256": semantic.get("sha256"),
        "universe_digest": provider.get("universe_digest"),
        "validated_trade_date": provider.get("validated_trade_date"),
        "as_of_date": provider.get("validated_trade_date"),
    }
    pointer["pointer_digest"] = _digest(pointer)
    stage_evidence = evidence_root / f".industry-stage-{uuid.uuid4().hex}"
    stage_root = stage_evidence / INDUSTRY_ROOT_RELATIVE
    stage_version = stage_root / version_relative
    final_version = root / version_relative
    try:
        if stage_evidence.is_symlink() or root.is_symlink() or evidence_root.is_symlink():
            return {"ready": False, "status": "industry_evidence_root_unsafe"}
        stage_version.mkdir(parents=True, exist_ok=False)
        semantic_stage = stage_root / str(semantic.get("relative_file") or "")
        semantic_stage.parent.mkdir(parents=True, exist_ok=True)
        semantic_stage.write_bytes(Path(str(semantic.get("path"))).read_bytes())
        (stage_root / raw_relative).write_bytes(raw_bytes)
        (stage_root / artifact_relative).write_bytes(artifact_bytes)
        (stage_root / ledger_relative).write_bytes(ledger_bytes)
        (stage_root / manifest_relative).write_bytes(_canonical_bytes(manifest))
        (stage_root / POINTER_FILE).write_bytes(_canonical_bytes(pointer))
        staged = validate_full_market_industry_membership(
            stage_evidence,
            expected_symbols=provider.get("symbols"),
            expected_universe_digest=provider.get("universe_digest"),
            expected_validated_trade_date=provider.get("validated_trade_date"),
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
        current_path = root / POINTER_FILE
        last_good_path = root / "last_good.json"
        current_before = current_path.read_bytes() if current_path.is_file() else None
        last_good_before = last_good_path.read_bytes() if last_good_path.is_file() else None
        try:
            _atomic_write_bytes(current_path, _canonical_bytes(pointer))
            _atomic_write_bytes(last_good_path, _canonical_bytes(pointer))
        except Exception:
            if current_before is None:
                current_path.unlink(missing_ok=True)
            else:
                _atomic_write_bytes(current_path, current_before)
            if last_good_before is None:
                last_good_path.unlink(missing_ok=True)
            else:
                _atomic_write_bytes(last_good_path, last_good_before)
            raise
        verified = validate_full_market_industry_membership(
            evidence_root,
            expected_symbols=provider.get("symbols"),
            expected_universe_digest=provider.get("universe_digest"),
            expected_validated_trade_date=provider.get("validated_trade_date"),
        )
        if (
            verified.get("ready") is not True
            or _read_json(last_good_path) != pointer
        ):
            if current_before is None:
                current_path.unlink(missing_ok=True)
            else:
                _atomic_write_bytes(current_path, current_before)
            if last_good_before is None:
                last_good_path.unlink(missing_ok=True)
            else:
                _atomic_write_bytes(last_good_path, last_good_before)
            return {
                "ready": False,
                "status": "industry_pointer_readback_validation_failed_rolled_back",
            }
        return {
            "ready": True,
            "status": "full_market_industry_membership_provider_execution_complete",
            "version_id": version_id,
            "pointer_digest": pointer["pointer_digest"],
            "manifest_digest": manifest["manifest_digest"],
            "artifact_sha256": artifact_sha256,
            "raw_artifact_sha256": raw_sha256,
            "call_ledger_sha256": ledger_sha256,
            "producer_binding_digest": producer_binding_digest,
            "validated": verified,
        }
    finally:
        shutil.rmtree(stage_evidence, ignore_errors=True)
