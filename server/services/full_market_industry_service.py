"""Fail-closed full-market effective-dated industry membership evidence.

The existing ``index_member_all`` Factor task is deliberately a bounded raw
sample collector.  It is not, and must never be treated as, the authoritative
full-market classification used by Factor or Candidate Radar production
workers.  This module only reads an externally-produced immutable artifact and
creates local execution-request tickets.  It never calls a provider and never
writes a production pointer.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import subprocess
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from server.services.task_service import create_task_record, update_task_status


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
INDUSTRY_ROOT_RELATIVE = Path("full_market_industry_membership")
POINTER_FILE = "pointer.json"

POINTER_SCHEMA_VERSION = "full_market_industry_membership_pointer.v2"
MANIFEST_SCHEMA_VERSION = "full_market_industry_membership_manifest.v2"
ARTIFACT_SCHEMA_VERSION = "full_market_industry_membership_artifact.v1"
SEMANTIC_EVIDENCE_SCHEMA_VERSION = (
    "full_market_industry_membership_out_date_semantic_evidence.v1"
)
SCOPE_SCHEMA_VERSION = "full_market_industry_membership_scope.v1"
SOURCE_VERSION_SCHEMA_VERSION = "full_market_industry_membership_source_version.v1"
EXECUTION_REQUEST_SCHEMA_VERSION = (
    "full_market_industry_membership_execution_request.v1"
)
EXECUTION_REQUEST_TASK_TYPE = (
    "run_full_market_industry_membership_execution_request"
)

SOURCE_API = "index_member_all"
SOURCE_SCOPE = "full_market_effective_dated_industry_membership"
RESOLVED_OUT_DATE_SEMANTICS = "effective_to_exclusive"
REQUIRED_EXCHANGES = ("BSE", "SSE", "SZSE")
MINIMUM_ELIGIBLE_SYMBOLS = 3000

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^[0-9]{8}$")
_SYMBOL = re.compile(r"^[0-9]{6}\.(BJ|SH|SZ)$")
_VERSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

INDUSTRY_BINDING_DIGEST_KEYS = (
    "industry_scope_digest",
    "industry_source_version_digest",
    "industry_artifact_sha256",
    "industry_manifest_digest",
    "industry_pointer_digest",
    "industry_semantic_evidence_sha256",
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _safe_relative_file(root: Path, value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    relative = Path(text)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    if root.is_symlink():
        return None
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return None
    candidate = root / relative
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except OSError:
        return None
    if resolved.parent != resolved_root and resolved_root not in resolved.parents:
        return None
    if candidate.is_symlink() or not resolved.is_file():
        return None
    return resolved


def _date(value: Any) -> str:
    text = str(value or "").strip().replace("-", "")
    if not _DATE.fullmatch(text):
        return ""
    try:
        _dt.datetime.strptime(text, "%Y%m%d")
    except ValueError:
        return ""
    return text


def _symbols(values: Any) -> tuple[list[str], int, int]:
    raw = list(values) if isinstance(values, Sequence) and not isinstance(values, (str, bytes)) else []
    normalized: list[str] = []
    invalid = 0
    for value in raw:
        symbol = str(value or "").strip().upper()
        if _SYMBOL.fullmatch(symbol):
            normalized.append(symbol)
        else:
            invalid += 1
    unique = sorted(set(normalized))
    return unique, len(normalized) - len(unique), invalid


def _exchange(symbol: str) -> str:
    suffix = symbol.rsplit(".", 1)[-1]
    return {"BJ": "BSE", "SH": "SSE", "SZ": "SZSE"}.get(suffix, "")


def _current_head_full() -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    value = completed.stdout.strip().lower() if completed.returncode == 0 else ""
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else ""


def _interval_blockers(
    rows: list[dict[str, Any]],
    *,
    expected_symbols: list[str],
    validated_trade_date: str,
) -> list[str]:
    blockers: list[str] = []
    by_symbol: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        if set(row) != {
            "effective_from",
            "effective_to",
            "industry_code",
            "source_api",
            "ts_code",
        }:
            blockers.append("artifact_row_schema_not_exact")
            continue
        raw_symbol = row.get("ts_code")
        raw_industry = row.get("industry_code")
        raw_start = row.get("effective_from")
        raw_source_api = row.get("source_api")
        symbol = raw_symbol.strip().upper() if type(raw_symbol) is str else ""
        industry = raw_industry.strip() if type(raw_industry) is str else ""
        start = _date(raw_start) if type(raw_start) is str else ""
        raw_end = row.get("effective_to")
        end_type_valid = raw_end is None or type(raw_end) is str
        end = "" if raw_end in (None, "") else _date(raw_end) if end_type_valid else ""
        if (
            not _SYMBOL.fullmatch(symbol)
            or not industry
            or not start
            or not end_type_valid
            or (raw_end not in (None, "") and not end)
            or (end and start >= end)
            or type(raw_source_api) is not str
            or raw_source_api != SOURCE_API
        ):
            blockers.append("artifact_effective_dated_row_invalid")
            continue
        by_symbol.setdefault(symbol, []).append((start, end))

    artifact_symbols = sorted(by_symbol)
    if artifact_symbols != expected_symbols:
        blockers.append("artifact_symbol_coverage_not_exact")
    active_symbols: list[str] = []
    for symbol, intervals in by_symbol.items():
        intervals.sort()
        previous_end = ""
        active = 0
        for index, (start, end) in enumerate(intervals):
            if previous_end and start < previous_end:
                blockers.append("artifact_effective_intervals_overlap")
            if index > 0 and not previous_end:
                blockers.append("artifact_open_interval_not_terminal")
            previous_end = end
            if start <= validated_trade_date and (not end or validated_trade_date < end):
                active += 1
        if active == 1:
            active_symbols.append(symbol)
        else:
            blockers.append("artifact_as_of_membership_not_exactly_one")
    if sorted(active_symbols) != expected_symbols:
        blockers.append("artifact_as_of_symbol_coverage_not_exact")
    return list(dict.fromkeys(blockers))


def validate_full_market_industry_membership(
    evidence_root: Path,
    *,
    expected_symbols: Any,
    expected_universe_digest: Any,
    expected_validated_trade_date: Any,
) -> dict[str, Any]:
    """Read and verify the current full-market industry pointer without writes."""

    symbols, duplicates, invalid = _symbols(expected_symbols)
    universe_digest = str(expected_universe_digest or "").strip().lower()
    validated_trade_date = _date(expected_validated_trade_date)
    blockers: list[str] = []
    if duplicates or invalid or len(symbols) < MINIMUM_ELIGIBLE_SYMBOLS:
        blockers.append("expected_universe_identity_or_size_invalid")
    if {exchange for symbol in symbols if (exchange := _exchange(symbol))} != set(REQUIRED_EXCHANGES):
        blockers.append("expected_universe_three_exchange_coverage_incomplete")
    if universe_digest != _digest(symbols):
        blockers.append("expected_universe_digest_invalid")
    if not validated_trade_date:
        blockers.append("expected_validated_trade_date_invalid")

    root = evidence_root / INDUSTRY_ROOT_RELATIVE
    pointer_path = root / POINTER_FILE
    root_safe = not evidence_root.is_symlink() and not root.is_symlink()
    pointer = (
        _read_json(pointer_path)
        if root_safe and pointer_path.is_file() and not pointer_path.is_symlink()
        else None
    )
    pointer = dict(pointer) if isinstance(pointer, Mapping) else {}
    pointer_material = {key: value for key, value in pointer.items() if key != "pointer_digest"}
    if set(pointer) != {
        "artifact_sha256",
        "as_of_date",
        "manifest_digest",
        "manifest_file",
        "pointer_digest",
        "schema_version",
        "scope_digest",
        "source_version_digest",
        "semantic_evidence_sha256",
        "universe_digest",
        "validated_trade_date",
        "version_id",
    }:
        blockers.append("industry_pointer_schema_not_exact")
    if pointer.get("schema_version") != POINTER_SCHEMA_VERSION:
        blockers.append("industry_pointer_schema_invalid")
    if pointer.get("pointer_digest") != _digest(pointer_material):
        blockers.append("industry_pointer_digest_invalid")

    manifest_path = _safe_relative_file(root, pointer.get("manifest_file"))
    manifest = _read_json(manifest_path) if manifest_path else None
    manifest = dict(manifest) if isinstance(manifest, Mapping) else {}
    manifest_material = {key: value for key, value in manifest.items() if key != "manifest_digest"}
    required_manifest_keys = {
        "artifact_file",
        "artifact_row_count",
        "artifact_schema_version",
        "artifact_sha256",
        "as_of_date",
        "eligible_symbol_count",
        "exchanges",
        "manifest_digest",
        "out_date_semantics",
        "out_date_semantics_evidence_digest",
        "out_date_semantics_validated",
        "scope",
        "schema_version",
        "scope_digest",
        "source_api",
        "source_scope",
        "source_version_digest",
        "source_version",
        "semantic_evidence_file",
        "semantic_evidence_schema_version",
        "semantic_evidence_sha256",
        "status",
        "universe_digest",
        "validated_trade_date",
        "version_id",
    }
    if set(manifest) != required_manifest_keys:
        blockers.append("industry_manifest_schema_not_exact")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        blockers.append("industry_manifest_schema_invalid")
    if manifest.get("manifest_digest") != _digest(manifest_material):
        blockers.append("industry_manifest_digest_invalid")
    if manifest.get("status") != "full_market_industry_membership_verified":
        blockers.append("industry_manifest_status_invalid")

    semantic_path = _safe_relative_file(root, manifest.get("semantic_evidence_file"))
    semantic_sha256 = _file_digest(semantic_path) if semantic_path else ""
    semantic = _read_json(semantic_path) if semantic_path else None
    semantic = dict(semantic) if isinstance(semantic, Mapping) else {}
    semantic_content = semantic.get("content")
    required_semantic_keys = {
        "content",
        "content_digest",
        "endpoint_field",
        "resolved_semantics",
        "schema_version",
        "source_api",
        "source_reference",
        "source_scope",
        "status",
        "validation_method",
    }
    required_semantic_content = {
        "field": "out_date",
        "interval_convention": "effective_from_inclusive_effective_to_exclusive",
        "non_null_boundary": "first_excluded_trade_date",
        "null_meaning": "membership_current_at_validated_trade_date",
    }
    if set(semantic) != required_semantic_keys:
        blockers.append("industry_semantic_evidence_schema_not_exact")
    if (
        semantic.get("schema_version") != SEMANTIC_EVIDENCE_SCHEMA_VERSION
        or semantic.get("status") != "independently_validated"
        or semantic.get("source_api") != SOURCE_API
        or semantic.get("source_scope") != SOURCE_SCOPE
        or semantic.get("endpoint_field") != "out_date"
        or semantic.get("resolved_semantics") != RESOLVED_OUT_DATE_SEMANTICS
        or semantic.get("validation_method")
        != "independent_local_documentation_and_fixture_review"
        or type(semantic.get("source_reference")) is not str
        or not semantic.get("source_reference", "").strip()
        or type(semantic_content) is not dict
        or semantic_content != required_semantic_content
        or semantic.get("content_digest") != _digest(semantic_content)
    ):
        blockers.append("industry_out_date_semantic_evidence_invalid")
    if (
        manifest.get("semantic_evidence_schema_version")
        != SEMANTIC_EVIDENCE_SCHEMA_VERSION
        or manifest.get("semantic_evidence_sha256") != semantic_sha256
        or pointer.get("semantic_evidence_sha256") != semantic_sha256
    ):
        blockers.append("industry_out_date_semantic_evidence_binding_invalid")

    artifact_path = _safe_relative_file(root, manifest.get("artifact_file"))
    artifact_sha256 = _file_digest(artifact_path) if artifact_path else ""
    artifact = _read_json(artifact_path) if artifact_path else None
    artifact = dict(artifact) if isinstance(artifact, Mapping) else {}
    raw_rows = artifact.get("rows")
    rows = (
        [dict(row) for row in raw_rows]
        if type(raw_rows) is list and all(type(row) is dict for row in raw_rows)
        else []
    )
    if set(artifact) != {"rows", "schema_version"} or artifact.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        blockers.append("industry_artifact_schema_invalid")
    if type(raw_rows) is not list or len(rows) != len(raw_rows):
        blockers.append("industry_artifact_rows_not_exact_objects")
    blockers.extend(
        _interval_blockers(
            rows,
            expected_symbols=symbols,
            validated_trade_date=validated_trade_date,
        )
    )

    as_of_date = _date(manifest.get("as_of_date"))
    exact_bindings = {
        "version_id": manifest.get("version_id"),
        "manifest_digest": manifest.get("manifest_digest"),
        "artifact_sha256": artifact_sha256,
        "scope_digest": manifest.get("scope_digest"),
        "source_version_digest": manifest.get("source_version_digest"),
        "semantic_evidence_sha256": semantic_sha256,
        "universe_digest": universe_digest,
        "validated_trade_date": validated_trade_date,
        "as_of_date": as_of_date,
    }
    for key, expected in exact_bindings.items():
        if pointer.get(key) != expected:
            blockers.append(f"industry_pointer_manifest_{key}_mismatch")
    if manifest.get("artifact_sha256") != artifact_sha256:
        blockers.append("industry_artifact_digest_mismatch")
    if (
        type(manifest.get("artifact_row_count")) is not int
        or manifest.get("artifact_row_count") != len(rows)
    ):
        blockers.append("industry_artifact_row_count_mismatch")
    if manifest.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        blockers.append("industry_artifact_version_binding_invalid")
    if manifest.get("source_api") != SOURCE_API or manifest.get("source_scope") != SOURCE_SCOPE:
        blockers.append("industry_source_api_or_scope_invalid")
    version_id = manifest.get("version_id")
    if type(version_id) is not str or not _VERSION_ID.fullmatch(version_id):
        blockers.append("industry_version_id_invalid")
    scope = manifest.get("scope") if type(manifest.get("scope")) is dict else {}
    expected_scope = {
        "schema_version": SCOPE_SCHEMA_VERSION,
        "source_api": SOURCE_API,
        "source_scope": SOURCE_SCOPE,
        "eligible_symbol_count": len(symbols),
        "exchanges": list(REQUIRED_EXCHANGES),
        "universe_digest": universe_digest,
        "validated_trade_date": validated_trade_date,
        "as_of_date": as_of_date,
    }
    if scope != expected_scope or manifest.get("scope_digest") != _digest(scope):
        blockers.append("industry_scope_binding_invalid")
    if not _HEX_64.fullmatch(str(manifest.get("scope_digest") or "")):
        blockers.append("industry_scope_digest_invalid")
    source_version = (
        manifest.get("source_version")
        if type(manifest.get("source_version")) is dict
        else {}
    )
    expected_source_version = {
        "schema_version": SOURCE_VERSION_SCHEMA_VERSION,
        "version_id": version_id,
        "source_api": SOURCE_API,
        "source_scope": SOURCE_SCOPE,
        "scope_digest": manifest.get("scope_digest"),
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_sha256": artifact_sha256,
        "semantic_evidence_sha256": semantic_sha256,
    }
    if (
        source_version != expected_source_version
        or manifest.get("source_version_digest") != _digest(source_version)
    ):
        blockers.append("industry_source_version_binding_invalid")
    if not _HEX_64.fullmatch(str(manifest.get("source_version_digest") or "")):
        blockers.append("industry_source_version_digest_invalid")
    if manifest.get("universe_digest") != universe_digest:
        blockers.append("industry_universe_digest_mismatch")
    if (
        type(manifest.get("eligible_symbol_count")) is not int
        or manifest.get("eligible_symbol_count") != len(symbols)
    ):
        blockers.append("industry_eligible_symbol_count_mismatch")
    if (
        type(manifest.get("exchanges")) is not list
        or manifest.get("exchanges") != list(REQUIRED_EXCHANGES)
    ):
        blockers.append("industry_three_exchange_manifest_invalid")
    if manifest.get("validated_trade_date") != validated_trade_date:
        blockers.append("industry_validated_trade_date_mismatch")
    if not as_of_date or as_of_date != validated_trade_date:
        blockers.append("industry_as_of_date_not_current_validated_trade_date")
    if (
        manifest.get("out_date_semantics") != RESOLVED_OUT_DATE_SEMANTICS
        or manifest.get("out_date_semantics_validated") is not True
        or manifest.get("out_date_semantics_evidence_digest") != semantic_sha256
    ):
        blockers.append("industry_out_date_semantics_unresolved")

    blockers = list(dict.fromkeys(blockers))
    ready = not blockers
    return {
        "ready": ready,
        "status": (
            "full_market_industry_membership_verified"
            if ready
            else "full_market_industry_membership_blocked"
        ),
        "source_api": SOURCE_API,
        "source_scope": SOURCE_SCOPE,
        "version_id": str(manifest.get("version_id") or ""),
        "scope_digest": str(manifest.get("scope_digest") or ""),
        "source_version_digest": str(manifest.get("source_version_digest") or ""),
        "artifact_sha256": artifact_sha256,
        "universe_digest": universe_digest,
        "manifest_digest": str(manifest.get("manifest_digest") or ""),
        "pointer_digest": str(pointer.get("pointer_digest") or ""),
        "semantic_evidence_sha256": semantic_sha256,
        "eligible_symbol_count": len(symbols),
        "exchanges": sorted({_exchange(symbol) for symbol in symbols if _exchange(symbol)}),
        "validated_trade_date": validated_trade_date,
        "as_of_date": as_of_date,
        "out_date_semantics": str(manifest.get("out_date_semantics") or "unresolved"),
        "small_pool_raw_evidence_accepted": False,
        "production_industry_verified": ready,
        "blockers": blockers,
        "read_only": True,
        "writes_storage": False,
        "provider_execution_triggered": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }


def read_full_market_industry_membership_status(
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """GET-safe composition of provider universe and industry evidence."""

    evidence_root = evidence_root or EVIDENCE_ROOT
    try:
        from server.services.tushare_production_store import (
            validate_tushare_full_market_production_version,
        )

        upstream = validate_tushare_full_market_production_version(evidence_root)
    except Exception as exc:
        upstream = {
            "ready": False,
            "symbols": [],
            "universe_digest": "",
            "validated_trade_date": "",
            "blockers": [f"upstream_provider_verifier_failed_{type(exc).__name__}"],
        }
    result = validate_full_market_industry_membership(
        evidence_root,
        expected_symbols=upstream.get("symbols") or [],
        expected_universe_digest=upstream.get("universe_digest") or "",
        expected_validated_trade_date=upstream.get("validated_trade_date") or "",
    )
    if upstream.get("ready") is not True:
        result["ready"] = False
        result["production_industry_verified"] = False
        result["status"] = "full_market_industry_membership_blocked"
        result["blockers"] = list(
            dict.fromkeys(
                ["upstream_full_market_provider_universe_not_ready"]
                + list(upstream.get("blockers") or [])
                + list(result.get("blockers") or [])
            )
        )
    return result


def create_full_market_industry_membership_execution_request(
    payload: Any = None,
    *,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Create a local request ticket; never execute or self-seal evidence."""

    evidence_root = evidence_root or EVIDENCE_ROOT
    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    try:
        from server.services.tushare_production_store import (
            validate_tushare_full_market_production_version,
        )

        upstream = validate_tushare_full_market_production_version(evidence_root)
    except Exception:
        upstream = {"ready": False, "symbols": [], "blockers": ["provider_universe_unavailable"]}
    symbols, duplicates, invalid = _symbols(upstream.get("symbols") or [])
    provider_scope_digest = str(upstream.get("scope_hash") or "").strip().lower()
    provider_version_digest = str(
        upstream.get("version_digest")
        or upstream.get("artifact_manifest_digest")
        or ""
    ).strip().lower()
    head_full = _current_head_full()
    request_nonce = str(payload_map.get("request_nonce") or "").strip().lower()
    try:
        parsed_nonce = uuid.UUID(request_nonce)
        nonce_valid = parsed_nonce.version == 4 and str(parsed_nonce) == request_nonce
    except (ValueError, AttributeError, TypeError):
        nonce_valid = False
    exchanges = sorted({_exchange(symbol) for symbol in symbols if _exchange(symbol)})
    request_ready = bool(
        payload_map.get("create_execution_request") is True
        and payload_map.get("acknowledge_no_provider_execution") is True
        and nonce_valid
        and upstream.get("ready") is True
        and not duplicates
        and not invalid
        and len(symbols) >= MINIMUM_ELIGIBLE_SYMBOLS
        and exchanges == list(REQUIRED_EXCHANGES)
        and upstream.get("universe_count") == len(symbols)
        and _date(upstream.get("validated_trade_date"))
        and upstream.get("universe_digest") == _digest(symbols)
        and _HEX_64.fullmatch(provider_scope_digest)
        and _HEX_64.fullmatch(provider_version_digest)
        and re.fullmatch(r"[0-9a-f]{40}", head_full)
    )
    scope = {
        "schema_version": "full_market_industry_membership_scope.v1",
        "source_api": SOURCE_API,
        "source_scope": SOURCE_SCOPE,
        "eligible_symbol_count": len(symbols),
        "exchanges": exchanges,
        "universe_digest": str(upstream.get("universe_digest") or ""),
        "provider_scope_digest": provider_scope_digest,
        "provider_version_digest": provider_version_digest,
        "validated_trade_date": _date(upstream.get("validated_trade_date")),
        "requested_out_date_semantics": "unresolved_requires_independent_evidence",
    }
    receipt = {
        "schema_version": EXECUTION_REQUEST_SCHEMA_VERSION,
        "status": (
            "full_market_industry_membership_execution_requested"
            if request_ready
            else "full_market_industry_membership_execution_request_blocked"
        ),
        "task_type": EXECUTION_REQUEST_TASK_TYPE,
        "request_nonce": request_nonce if nonce_valid else "",
        "head_full": head_full,
        "scope": scope,
        "scope_digest": _digest(scope),
        "request_ready": request_ready,
        "provider_execution_triggered": False,
        "provider_task_created": False,
        "production_pointer_written": False,
        "production_industry_verified": False,
        "small_pool_raw_evidence_accepted": False,
        "out_date_semantics_resolved": False,
        "anns_d_required": False,
        "writes_storage": True,
        "writes_only_task_status": True,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "blockers": [] if request_ready else ["execution_request_contract_not_satisfied"],
        "call_ledger": [
            {
                "api": "local_full_market_industry_membership_execution_request",
                "call_status": "request_created" if request_ready else "blocked",
                "external_calls_triggered": False,
                "writes_production_pointer": False,
                "does_not_execute_trades": True,
            }
        ],
    }
    task = create_task_record(
        EXECUTION_REQUEST_TASK_TYPE,
        output_packet_key="command_center_3_full_market_industry_membership_execution_request",
        payload={"execution_request": receipt},
        current_step="full_market_industry_membership_execution_request_created",
        warnings=[
            "该 POST 只创建本地 execution-request；不会调用 index_member_all，也不会写生产 pointer。",
            "小池 raw rows 与 out_date 未定义证据不能满足全市场 PIT 行业分类生产合同。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task
    updated = update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=str(receipt["status"]),
        call_ledger=list(receipt["call_ledger"]),
    ) or task
    updated["payload_safe"] = {"execution_request": receipt}
    return updated


__all__ = (
    "EXECUTION_REQUEST_TASK_TYPE",
    "INDUSTRY_BINDING_DIGEST_KEYS",
    "MINIMUM_ELIGIBLE_SYMBOLS",
    "create_full_market_industry_membership_execution_request",
    "read_full_market_industry_membership_status",
    "validate_full_market_industry_membership",
)
