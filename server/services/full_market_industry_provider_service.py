from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore

from . import task_service
from .full_market_industry_evidence_writer import (
    _promote_provider_evidence,
    _provider_execution_task,
    _resume_attested_provider_evidence,
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
    _validated_semantic_authority,
    validate_full_market_industry_membership,
)


PROVIDER_EXECUTION_SCHEMA_VERSION = "full_market_industry_membership_provider_execution.v1"
_EXECUTION_PAYLOAD_KEYS = {
    "acknowledge_external_tushare_call",
    "execute_provider_request",
    "provider_api",
    "request_task_id",
}
_REQUEST_KEYS = {
    "anns_d_required",
    "blockers",
    "call_ledger",
    "does_not_execute_trades",
    "does_not_modify_strategy_action",
    "external_calls_triggered",
    "head_full",
    "out_date_semantics_resolved",
    "production_industry_verified",
    "production_pointer_written",
    "provider_execution_triggered",
    "provider_task_created",
    "request_digest",
    "request_nonce",
    "request_ready",
    "schema_version",
    "scope",
    "scope_digest",
    "small_pool_raw_evidence_accepted",
    "status",
    "task_type",
    "writes_only_task_status",
    "writes_storage",
}
_SCOPE_KEYS = {
    "eligible_symbol_count",
    "exchanges",
    "provider_scope_digest",
    "provider_version_digest",
    "requested_out_date_semantics",
    "schema_version",
    "source_api",
    "source_scope",
    "universe_digest",
    "validated_trade_date",
}


def _unsafe_managed_path(evidence_root: Path, meta_path: Path) -> bool:
    root = evidence_root / INDUSTRY_ROOT_RELATIVE
    return meta_path.is_symlink() or any(
        path.is_symlink()
        for path in (
            evidence_root,
            root,
            root / "locks",
            root / "versions",
            root / "pointer.json",
            root / "last_good.json",
        )
    )


def _request_contract(
    task: Any,
    *,
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    task_map = dict(task) if type(task) is dict else {}
    payload_safe = (
        task_map.get("payload_safe")
        if type(task_map.get("payload_safe")) is dict
        else {}
    )
    request = (
        dict(payload_safe.get("execution_request"))
        if type(payload_safe.get("execution_request")) is dict
        else {}
    )
    scope = request.get("scope") if type(request.get("scope")) is dict else {}
    blockers: list[str] = []
    request_task_id = payload.get("request_task_id")
    if (
        type(request_task_id) is not str
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", request_task_id)
        or task_map.get("task_id") != request_task_id
        or task_map.get("task_type") != EXECUTION_REQUEST_TASK_TYPE
        or type(task_map.get("status")) is not str
        or set(payload_safe) != {"execution_request"}
    ):
        blockers.append("persisted_execution_request_task_invalid")
    if set(request) != _REQUEST_KEYS or set(scope) != _SCOPE_KEYS:
        blockers.append("persisted_execution_request_shape_invalid")
    if (
        task_map.get("status") != "success"
        or request.get("request_ready") is not True
        or request.get("status") != "full_market_industry_membership_execution_requested"
        or request.get("blockers") != []
    ):
        blockers.append("persisted_execution_request_not_ready")
    if request.get("schema_version") != EXECUTION_REQUEST_SCHEMA_VERSION:
        blockers.append("persisted_execution_request_schema_invalid")
    if request.get("task_type") != EXECUTION_REQUEST_TASK_TYPE:
        blockers.append("persisted_execution_request_type_invalid")
    if (
        type(request.get("scope_digest")) is not str
        or request.get("scope_digest") != _digest(scope)
    ):
        blockers.append("persisted_execution_request_scope_digest_invalid")
    if (
        type(request.get("request_digest")) is not str
        or request.get("request_digest") != _execution_request_digest(request)
    ):
        blockers.append("persisted_execution_request_digest_invalid")
    if request.get("head_full") != _current_head_full():
        blockers.append("persisted_execution_request_head_mismatch")
    if (
        type(scope.get("source_api")) is not str
        or type(scope.get("source_scope")) is not str
        or scope.get("source_api") != SOURCE_API
        or scope.get("source_scope") != SOURCE_SCOPE
    ):
        blockers.append("persisted_execution_request_endpoint_or_scope_invalid")
    if (
        type(scope.get("eligible_symbol_count")) is not int
        or isinstance(scope.get("eligible_symbol_count"), bool)
        or scope.get("eligible_symbol_count", 0) < MINIMUM_ELIGIBLE_SYMBOLS
    ):
        blockers.append("persisted_execution_request_universe_below_3000")
    if type(scope.get("exchanges")) is not list or scope.get("exchanges") != list(
        REQUIRED_EXCHANGES
    ):
        blockers.append("persisted_execution_request_exchange_scope_invalid")
    if not _date(scope.get("validated_trade_date")):
        blockers.append("persisted_execution_request_validated_date_invalid")
    string_scope_keys = (
        "provider_scope_digest",
        "provider_version_digest",
        "universe_digest",
        "validated_trade_date",
        "requested_out_date_semantics",
        "schema_version",
    )
    if any(type(scope.get(key)) is not str for key in string_scope_keys):
        blockers.append("persisted_execution_request_scope_types_invalid")
    boolean_request_keys = (
        "request_ready",
        "provider_execution_triggered",
        "provider_task_created",
        "production_pointer_written",
        "production_industry_verified",
        "small_pool_raw_evidence_accepted",
        "out_date_semantics_resolved",
        "anns_d_required",
        "writes_storage",
        "writes_only_task_status",
        "external_calls_triggered",
        "does_not_execute_trades",
        "does_not_modify_strategy_action",
    )
    if any(type(request.get(key)) is not bool for key in boolean_request_keys):
        blockers.append("persisted_execution_request_boolean_types_invalid")
    request_string_keys = (
        "head_full", "request_digest", "request_nonce", "schema_version",
        "scope_digest", "status", "task_type",
    )
    request_ledger = request.get("call_ledger")
    ledger_row = (
        request_ledger[0]
        if type(request_ledger) is list
        and len(request_ledger) == 1
        and type(request_ledger[0]) is dict
        else {}
    )
    if (
        any(type(request.get(key)) is not str for key in request_string_keys)
        or not re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            str(request.get("request_nonce") or ""),
        )
        or set(ledger_row) != {
            "api", "call_status", "does_not_execute_trades",
            "external_calls_triggered", "writes_production_pointer",
        }
        or ledger_row.get("api") != "local_full_market_industry_membership_execution_request"
        or ledger_row.get("call_status") != "request_created"
        or ledger_row.get("external_calls_triggered") is not False
        or ledger_row.get("writes_production_pointer") is not False
        or ledger_row.get("does_not_execute_trades") is not True
    ):
        blockers.append("persisted_execution_request_scalar_types_invalid")
    if (
        any(
            request.get(key) is not False
            for key in (
                "provider_execution_triggered", "provider_task_created",
                "production_pointer_written", "production_industry_verified",
                "small_pool_raw_evidence_accepted", "out_date_semantics_resolved",
                "anns_d_required", "external_calls_triggered",
            )
        )
        or any(
            request.get(key) is not True
            for key in (
                "request_ready", "writes_storage", "writes_only_task_status",
                "does_not_execute_trades", "does_not_modify_strategy_action",
            )
        )
    ):
        blockers.append("persisted_execution_request_values_invalid")
    if set(payload) != _EXECUTION_PAYLOAD_KEYS:
        blockers.append("provider_execution_payload_shape_invalid")
    if payload.get("execute_provider_request") is not True:
        blockers.append("explicit_provider_execution_approval_missing")
    if payload.get("acknowledge_external_tushare_call") is not True:
        blockers.append("explicit_external_call_acknowledgement_missing")
    if type(payload.get("provider_api")) is not str or payload.get("provider_api") != SOURCE_API:
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
    unsafe_path = _unsafe_managed_path(evidence_root, meta_path)
    try:
        task = (
            SQLiteMetaStore(meta_path, read_only=True).read_task_status(request_task_id)
            if not unsafe_path
            and request_task_id
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", request_task_id)
            and meta_path.is_file()
            else None
        )
    except Exception:
        task = None
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
    if unsafe_path:
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
        semantic = _validated_semantic_authority()
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
        success_task_id = f"industry-provider-{request_digest[:20]}"
        try:
            prior = SQLiteMetaStore(meta_path, read_only=True).read_task_status(success_task_id)
        except Exception:
            prior = None
        prior_payload = prior.get("payload_safe") if type(prior) is dict else None
        if (
            type(prior) is dict
            and prior.get("status") == "success"
            and prior.get("task_id") == success_task_id
            and type(prior_payload) is dict
            and prior_payload.get("request_digest") == request_digest
            and type(prior.get("call_ledger")) is list
            and prior.get("call_ledger")
        ):
            return dict(prior)
        return _provider_execution_task(
            request_digest=request_digest,
            payload={**base_payload, "status": "provider_replay_success_history_missing"},
            status="failed",
            step="provider_replay_success_history_missing",
            call_ledger=[],
            meta_path=meta_path,
            error="provider_replay_success_history_missing",
        )

    try:
        resumed = _resume_attested_provider_evidence(
            evidence_root=evidence_root,
            request=request,
            provider=provider,
            semantic=semantic,
        )
    except Exception as exc:
        resumed = {
            "ready": False,
            "status": f"staged_generation_resume_failed_{type(exc).__name__}",
        }
    if resumed.get("status") != "no_staged_generation":
        resumed_ready = resumed.get("ready") is True
        resumed_ledger = (
            [dict(row) for row in resumed.get("call_ledger") or []]
            if type(resumed.get("call_ledger")) is list
            else []
        )
        return _provider_execution_task(
            request_digest=request_digest,
            payload={
                **base_payload,
                **resumed,
                "provider_execution_triggered": False,
                "production_pointer_written": resumed_ready,
                "external_calls_triggered": False,
                "tushare_called": False,
            },
            status="success" if resumed_ready else "failed",
            step=str(resumed.get("status") or "staged_generation_resume_blocked"),
            call_ledger=resumed_ledger,
            meta_path=meta_path,
            error="" if resumed_ready else str(resumed.get("status") or "resume_blocked"),
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
