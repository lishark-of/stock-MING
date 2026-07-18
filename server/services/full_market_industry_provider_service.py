from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore

from . import task_service
from .full_market_industry_evidence_writer import (
    PROVIDER_EXECUTION_TASK_TYPE,
    _promote_provider_evidence,
    _provider_execution_task,
)
from .full_market_industry_provider_collector import (
    _collect_provider_pages,
    _current_provider_matches_request,
    _load_official_index_member_client,
    _normalize_provider_rows,
)
from .full_market_industry_service import (
    EVIDENCE_ROOT,
    EXECUTION_REQUEST_SCHEMA_VERSION,
    EXECUTION_REQUEST_TASK_TYPE,
    INDUSTRY_ROOT_RELATIVE,
    MINIMUM_ELIGIBLE_SYMBOLS,
    REQUIRED_EXCHANGES,
    SOURCE_API,
    SOURCE_SCOPE,
    _current_head_full,
    _date,
    _digest,
    _execution_request_digest,
    _validated_semantic_evidence_file,
    validate_full_market_industry_membership,
)


PROVIDER_EXECUTION_SCHEMA_VERSION = "full_market_industry_membership_provider_execution.v1"

def _unsafe_managed_path(evidence_root: Path, meta_path: Path) -> bool:
    root = evidence_root / INDUSTRY_ROOT_RELATIVE
    return meta_path.is_symlink() or any(
        path.is_symlink()
        for path in (evidence_root, root, root / "locks", root / "versions", root / "pointer.json", root / "last_good.json")
    )

def _request_contract(
    task: Any,
    *,
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    task_map = dict(task) if isinstance(task, Mapping) else {}
    request = (
        dict(task_map.get("payload_safe", {}).get("execution_request", {}))
        if isinstance(task_map.get("payload_safe"), Mapping)
        and isinstance(task_map.get("payload_safe", {}).get("execution_request"), Mapping)
        else {}
    )
    scope = request.get("scope") if type(request.get("scope")) is dict else {}
    blockers: list[str] = []
    if task_map.get("task_type") != EXECUTION_REQUEST_TASK_TYPE:
        blockers.append("persisted_execution_request_task_invalid")
    if task_map.get("status") != "success" or request.get("request_ready") is not True:
        blockers.append("persisted_execution_request_not_ready")
    if request.get("schema_version") != EXECUTION_REQUEST_SCHEMA_VERSION:
        blockers.append("persisted_execution_request_schema_invalid")
    if request.get("task_type") != EXECUTION_REQUEST_TASK_TYPE:
        blockers.append("persisted_execution_request_type_invalid")
    if request.get("scope_digest") != _digest(scope):
        blockers.append("persisted_execution_request_scope_digest_invalid")
    if request.get("request_digest") != _execution_request_digest(request):
        blockers.append("persisted_execution_request_digest_invalid")
    if request.get("head_full") != _current_head_full():
        blockers.append("persisted_execution_request_head_mismatch")
    if scope.get("source_api") != SOURCE_API or scope.get("source_scope") != SOURCE_SCOPE:
        blockers.append("persisted_execution_request_endpoint_or_scope_invalid")
    if scope.get("eligible_symbol_count", 0) < MINIMUM_ELIGIBLE_SYMBOLS:
        blockers.append("persisted_execution_request_universe_below_3000")
    if scope.get("exchanges") != list(REQUIRED_EXCHANGES):
        blockers.append("persisted_execution_request_exchange_scope_invalid")
    if not _date(scope.get("validated_trade_date")):
        blockers.append("persisted_execution_request_validated_date_invalid")
    if payload.get("execute_provider_request") is not True:
        blockers.append("explicit_provider_execution_approval_missing")
    if payload.get("acknowledge_external_tushare_call") is not True:
        blockers.append("explicit_external_call_acknowledgement_missing")
    if payload.get("provider_api") not in (None, "", SOURCE_API):
        blockers.append("provider_endpoint_not_allowlisted")
    return request, list(dict.fromkeys(blockers))

def run_full_market_industry_membership_provider_execution(
    payload: Any = None,
    *,
    evidence_root: Path | None = None,
    meta_path: Path | None = None,
) -> dict[str, Any]:
    """Consume one persisted request from an explicit POST and call only index_member_all."""

    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    evidence_root = Path(evidence_root or EVIDENCE_ROOT)
    meta_path = Path(meta_path or task_service.SQLITE_META_PATH)
    request_task_id = str(payload_map.get("request_task_id") or "").strip()
    task = (
        SQLiteMetaStore(meta_path, read_only=True).read_task_status(request_task_id)
        if request_task_id
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", request_task_id)
        and meta_path.is_file()
        else None
    )
    request, blockers = _request_contract(task, payload=payload_map)
    request_digest = str(request.get("request_digest") or "")
    base_payload = {
        "schema_version": PROVIDER_EXECUTION_SCHEMA_VERSION,
        "request_task_id": request_task_id,
        "request_digest": request_digest,
        "provider_api": SOURCE_API,
        "provider_execution_triggered": False,
        "production_pointer_written": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    if _unsafe_managed_path(evidence_root, meta_path):
        blockers.append("industry_evidence_root_unsafe")
    provider: dict[str, Any] = {}
    if not blockers:
        provider, provider_blockers = _current_provider_matches_request(
            evidence_root,
            request,
        )
        blockers.extend(provider_blockers)
    semantic: dict[str, Any] = {}
    if not blockers:
        semantic = _validated_semantic_evidence_file(
            evidence_root / INDUSTRY_ROOT_RELATIVE,
            payload_map.get("semantic_evidence_file"),
        )
        blockers.extend(semantic.get("blockers") or [])
    if blockers:
        return _provider_execution_task(
            request_digest=request_digest,
            payload={**base_payload, "status": "provider_execution_blocked", "blockers": list(dict.fromkeys(blockers))},
            status="failed",
            step="full_market_industry_provider_execution_blocked_before_call",
            call_ledger=[],
            meta_path=meta_path,
            error=str(list(dict.fromkeys(blockers))[0]),
        )

    existing = validate_full_market_industry_membership(
        evidence_root,
        expected_symbols=provider.get("symbols"),
        expected_universe_digest=provider.get("universe_digest"),
        expected_validated_trade_date=provider.get("validated_trade_date"),
    )
    if (
        existing.get("ready") is True
        and existing.get("execution_request_digest") == request_digest
    ):
        return _provider_execution_task(
            request_digest=request_digest,
            payload={
                **base_payload,
                "status": "provider_execution_replayed_existing_immutable_version",
                "replay": True,
                "pointer_digest": existing.get("pointer_digest"),
            },
            status="success",
            step="full_market_industry_provider_execution_replayed_no_call",
            call_ledger=[],
            meta_path=meta_path,
        )

    root = evidence_root / INDUSTRY_ROOT_RELATIVE
    lock_path = root / "locks" / f"{request_digest}.lock"
    lock_descriptor: int | None = None
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
        os.write(lock_descriptor, request_task_id.encode("utf-8"))
        os.fsync(lock_descriptor)
    except OSError as exc:
        lock_status = (
            "provider_execution_concurrent_request_blocked"
            if isinstance(exc, FileExistsError)
            else "provider_execution_lock_failed_no_call"
        )
        return _provider_execution_task(
            request_digest=request_digest,
            payload={**base_payload, "status": lock_status},
            status="failed",
            step=lock_status,
            call_ledger=[],
            meta_path=meta_path,
            error=lock_status,
        )
    try:
        try:
            client = _load_official_index_member_client()
        except Exception as exc:
            return _provider_execution_task(
                request_digest=request_digest,
                payload={
                    **base_payload,
                    "status": "provider_adapter_load_failed_no_call",
                    "blockers": [
                        f"provider_adapter_load_failed_{type(exc).__name__}"
                    ],
                },
                status="failed",
                step="full_market_industry_provider_adapter_load_failed_no_call",
                call_ledger=[],
                meta_path=meta_path,
                error=f"provider_adapter_load_failed_{type(exc).__name__}",
            )
        collected_rows, call_ledger, collection_blockers = _collect_provider_pages(client)
        if collection_blockers:
            return _provider_execution_task(
                request_digest=request_digest,
                payload={
                    **base_payload,
                    "status": "provider_execution_failed_no_promotion",
                    "blockers": collection_blockers,
                    "provider_execution_triggered": True,
                    "external_calls_triggered": True,
                    "tushare_called": True,
                },
                status="failed",
                step="full_market_industry_provider_execution_failed_no_promotion",
                call_ledger=call_ledger,
                meta_path=meta_path,
                error=collection_blockers[0],
            )
        raw_rows, normalized_rows, row_blockers = _normalize_provider_rows(
            collected_rows,
            symbols=list(provider.get("symbols") or []),
            validated_trade_date=str(provider.get("validated_trade_date") or ""),
        )
        if row_blockers:
            return _provider_execution_task(
                request_digest=request_digest,
                payload={
                    **base_payload,
                    "status": "provider_output_validation_failed_no_promotion",
                    "blockers": row_blockers,
                    "provider_execution_triggered": True,
                    "external_calls_triggered": True,
                    "tushare_called": True,
                },
                status="failed",
                step="full_market_industry_provider_output_invalid_no_promotion",
                call_ledger=call_ledger,
                meta_path=meta_path,
                error=row_blockers[0],
            )
        try:
            promotion = _promote_provider_evidence(
                evidence_root=evidence_root, request_task_id=request_task_id,
                request=request, provider=provider, semantic=semantic,
                raw_rows=raw_rows, normalized_rows=normalized_rows,
                call_ledger=call_ledger,
            )
        except Exception as exc:
            promotion = {"ready": False, "status": f"provider_evidence_promotion_failed_{type(exc).__name__}"}
        ready = promotion.get("ready") is True
        return _provider_execution_task(
            request_digest=request_digest,
            payload={
                **base_payload,
                **promotion,
                "provider_execution_triggered": True,
                "production_pointer_written": ready,
                "external_calls_triggered": True,
                "tushare_called": True,
            },
            status="success" if ready else "failed",
            step=str(promotion.get("status") or "provider_evidence_promotion_failed"),
            call_ledger=call_ledger,
            meta_path=meta_path,
            error="" if ready else str(promotion.get("status") or "promotion_failed"),
        )
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
        lock_path.unlink(missing_ok=True)
