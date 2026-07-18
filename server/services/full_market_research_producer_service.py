from __future__ import annotations

import hashlib
import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any, Mapping

from storage.sqlite_meta import SQLiteMetaStore

from . import task_service
from .tushare_production_store import (
    REQUIRED_SESSIONS,
    validate_tushare_full_market_production_version,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
SQLITE_META_PATH = EVIDENCE_ROOT / "meta.sqlite"

COORDINATOR_TASK_TYPE = "run_full_market_factor_radar_map_reduce_request"
FACTOR_TASK_TYPE = "run_factor_full_market_map_reduce_request"
RADAR_TASK_TYPE = "run_candidate_radar_authoritative_map_reduce_request"

COORDINATOR_PACKET_KEY = "command_center_3_full_market_factor_radar_map_reduce_request"
FACTOR_REQUEST_PACKET_KEY = "command_center_3_factor_full_market_map_reduce_request"
RADAR_REQUEST_PACKET_KEY = "command_center_3_candidate_radar_map_reduce_request"

FACTOR_TARGET_PACKET_KEY = "command_center_3_factor_full_market_worker_production_acceptance"
FACTOR_TARGET_DATASET = "full_market_factor_research_results"
RADAR_TARGET_PACKET_KEY = "command_center_3_candidate_radar_cache"
RADAR_TARGET_DATASET = "full_market_candidate_radar_results"

SCHEMA_VERSION = "full_market_factor_radar_map_reduce_request.v1"
CHILD_SCHEMA_VERSION = "full_market_map_reduce_child_request.v1"
EXTERNAL_LINEAGE_BLOCKER = "external_trusted_production_lineage_runner_unavailable"
MINIMUM_UNIVERSE_SIZE = 3000
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


FACTOR_OUTPUT_CONTRACT: dict[str, Any] = {
    "schema_version": "factor_full_market_map_reduce_output.v1",
    "output_kind": "factor_full_market_cross_sectional_research",
    "target_dataset": FACTOR_TARGET_DATASET,
    "target_packet_key": FACTOR_TARGET_PACKET_KEY,
    "required_metrics": [
        "cross_sectional_rank",
        "cross_sectional_zscore",
        "industry_neutral_score",
        "size_neutral_score",
        "combined_factor_score",
    ],
    "requires_effective_dated_industry_membership": True,
    "requires_full_universe_symbol_coverage": True,
    "candidate_radar_rows_are_not_factor_rows": True,
    "research_only": True,
    "does_not_execute_trades": True,
}

RADAR_OUTPUT_CONTRACT: dict[str, Any] = {
    "schema_version": "candidate_radar_authoritative_map_reduce_output.v1",
    "output_kind": "candidate_radar_full_market_deep_scan",
    "target_dataset": RADAR_TARGET_DATASET,
    "target_packet_key": RADAR_TARGET_PACKET_KEY,
    "required_fields": [
        "ts_code",
        "data_date",
        "deep_scan_score",
        "rough_score",
        "risk_score",
        "trigger_conditions_json",
        "invalid_conditions_json",
    ],
    "requires_full_universe_symbol_coverage": True,
    "requires_authoritative_candidate_cache_write": True,
    "factor_rows_are_not_candidate_radar_rows": True,
    "candidate_is_not_buy_instruction": True,
    "research_only": True,
    "does_not_execute_trades": True,
}


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


FACTOR_OUTPUT_CONTRACT_DIGEST = _digest(FACTOR_OUTPUT_CONTRACT)
RADAR_OUTPUT_CONTRACT_DIGEST = _digest(RADAR_OUTPUT_CONTRACT)


def _current_head_full() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    value = result.stdout.strip().lower() if result.returncode == 0 else ""
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else ""


def _safe_digest(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if _HEX_64.fullmatch(text) else ""


def _provider_contract(evidence_root: Path) -> dict[str, Any]:
    raw = validate_tushare_full_market_production_version(
        evidence_root,
        include_frames=False,
    )
    provider = dict(raw) if isinstance(raw, Mapping) else {}
    symbols = [str(item).strip().upper() for item in provider.get("symbols") or []]
    blockers = [str(item) for item in provider.get("blockers") or [] if str(item)]
    required_digests = {
        "provider_scope_hash": _safe_digest(provider.get("scope_hash")),
        "provider_version_digest": _safe_digest(provider.get("version_digest")),
        "universe_digest": _safe_digest(provider.get("universe_digest")),
        "artifact_manifest_digest": _safe_digest(provider.get("artifact_manifest_digest")),
    }
    universe_count = int(provider.get("universe_count") or 0)
    validated_trade_date = str(provider.get("validated_trade_date") or "")
    if provider.get("ready") is not True:
        blockers.append("authoritative_provider_pointer_not_ready")
    if universe_count < MINIMUM_UNIVERSE_SIZE:
        blockers.append("authoritative_provider_universe_below_3000")
    if len(symbols) != universe_count or len(set(symbols)) != universe_count:
        blockers.append("authoritative_provider_symbol_identity_invalid")
    if any(not value for value in required_digests.values()):
        blockers.append("authoritative_provider_digest_binding_incomplete")
    if not (len(validated_trade_date) == 8 and validated_trade_date.isdigit()):
        blockers.append("authoritative_provider_trade_date_invalid")
    blockers = list(dict.fromkeys(blockers))
    return {
        "ready": not blockers,
        "status": (
            "authoritative_provider_pointer_ready_for_shared_map_reduce"
            if not blockers
            else "authoritative_provider_pointer_blocked"
        ),
        "universe_count": universe_count,
        "minimum_universe_size": MINIMUM_UNIVERSE_SIZE,
        "required_sessions": REQUIRED_SESSIONS,
        "validated_trade_date": validated_trade_date,
        **required_digests,
        "blockers": blockers,
        "read_only": True,
        "writes_storage": False,
        "external_calls_triggered": False,
    }


def build_full_market_factor_radar_map_reduce_contract(
    payload: Any = None,
    *,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    root = Path(evidence_root or EVIDENCE_ROOT)
    provider = _provider_contract(root)
    head_full = _current_head_full()
    requested_industry_digest = _safe_digest(
        payload_map.get("effective_dated_industry_membership_digest")
    )
    blockers = list(provider.get("blockers") or [])
    if not head_full:
        blockers.append("current_head_binding_missing")
    if not requested_industry_digest:
        blockers.append("effective_dated_industry_membership_digest_missing")
    # A caller-provided digest is request material, not evidence.  The current
    # repository has no full-market, effective-dated industry pointer that an
    # independent verifier can read back, so the producer remains fail closed.
    blockers.append("authoritative_effective_dated_industry_membership_missing")
    blockers.append(EXTERNAL_LINEAGE_BLOCKER)
    shared_material = {
        "schema_version": SCHEMA_VERSION,
        "head_full": head_full,
        "provider_scope_hash": provider.get("provider_scope_hash"),
        "provider_version_digest": provider.get("provider_version_digest"),
        "universe_digest": provider.get("universe_digest"),
        "artifact_manifest_digest": provider.get("artifact_manifest_digest"),
        "universe_count": provider.get("universe_count"),
        "required_sessions": REQUIRED_SESSIONS,
        "validated_trade_date": provider.get("validated_trade_date"),
        "requested_effective_dated_industry_membership_digest": requested_industry_digest,
        "effective_dated_industry_membership_verified": False,
        "factor_output_contract_digest": FACTOR_OUTPUT_CONTRACT_DIGEST,
        "radar_output_contract_digest": RADAR_OUTPUT_CONTRACT_DIGEST,
    }
    shared_scope_hash = _digest(shared_material)
    factor_request_material = {
        **shared_material,
        "output_kind": FACTOR_OUTPUT_CONTRACT["output_kind"],
        "target_dataset": FACTOR_TARGET_DATASET,
        "target_packet_key": FACTOR_TARGET_PACKET_KEY,
        "output_contract_digest": FACTOR_OUTPUT_CONTRACT_DIGEST,
    }
    radar_request_material = {
        **shared_material,
        "output_kind": RADAR_OUTPUT_CONTRACT["output_kind"],
        "target_dataset": RADAR_TARGET_DATASET,
        "target_packet_key": RADAR_TARGET_PACKET_KEY,
        "output_contract_digest": RADAR_OUTPUT_CONTRACT_DIGEST,
    }
    request_scope_ready = bool(
        provider.get("ready") is True and head_full and requested_industry_digest
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "full_market_factor_radar_execution_request_recorded_authoritative_inputs_pending"
            if request_scope_ready
            else "full_market_factor_radar_execution_request_blocked"
        ),
        "head_full": head_full,
        "provider": provider,
        "shared_scope_hash": shared_scope_hash,
        "shared_scope_material": shared_material,
        "factor_output_contract": dict(FACTOR_OUTPUT_CONTRACT),
        "factor_output_contract_digest": FACTOR_OUTPUT_CONTRACT_DIGEST,
        "factor_request_digest": _digest(factor_request_material),
        "radar_output_contract": dict(RADAR_OUTPUT_CONTRACT),
        "radar_output_contract_digest": RADAR_OUTPUT_CONTRACT_DIGEST,
        "radar_request_digest": _digest(radar_request_material),
        "output_contracts_are_independent": (
            FACTOR_OUTPUT_CONTRACT_DIGEST != RADAR_OUTPUT_CONTRACT_DIGEST
            and FACTOR_TARGET_DATASET != RADAR_TARGET_DATASET
            and FACTOR_TARGET_PACKET_KEY != RADAR_TARGET_PACKET_KEY
        ),
        "shared_map_reduce_reuses_verified_provider_reads": True,
        "factor_and_radar_are_separate_reduce_outputs": True,
        "execution_request_scope_ready": request_scope_ready,
        "execution_request_ready": False,
        "production_prerequisites_ready": False,
        "dispatch_allowed": False,
        "external_trusted_lineage_runner_available": False,
        "blockers": list(dict.fromkeys(blockers)),
        "production_complete": False,
        "factor_production_complete": False,
        "candidate_radar_production_replacement": False,
        "global_candidate_cache_overwritten": False,
        "provider_execution_triggered": False,
        "worker_execution_triggered": False,
        "redis_called": False,
        "celery_called": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _exact_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return actual is expected
    if isinstance(expected, int):
        return type(actual) is int and actual == expected
    return actual == expected


def _validate_independent_output_requests(
    factor_request: Mapping[str, Any],
    radar_request: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    provider = contract.get("provider") if isinstance(contract.get("provider"), Mapping) else {}
    shared = (
        contract.get("shared_scope_material")
        if isinstance(contract.get("shared_scope_material"), Mapping)
        else {}
    )
    expected_common = {
        "schema_version": CHILD_SCHEMA_VERSION,
        "status": (
            "execution_request_recorded_authoritative_inputs_pending"
            if contract.get("execution_request_scope_ready") is True
            else "execution_request_blocked_prerequisites_missing"
        ),
        "head_full": contract.get("head_full"),
        "shared_scope_hash": contract.get("shared_scope_hash"),
        "provider_scope_hash": provider.get("provider_scope_hash"),
        "provider_version_digest": provider.get("provider_version_digest"),
        "universe_digest": provider.get("universe_digest"),
        "artifact_manifest_digest": provider.get("artifact_manifest_digest"),
        "universe_count": provider.get("universe_count"),
        "required_sessions": REQUIRED_SESSIONS,
        "validated_trade_date": provider.get("validated_trade_date"),
        "requested_effective_dated_industry_membership_digest": shared.get(
            "requested_effective_dated_industry_membership_digest"
        ),
        "effective_dated_industry_membership_verified": False,
        "blockers": list(contract.get("blockers") or []),
        "dispatch_allowed": False,
        "external_trusted_lineage_runner_available": False,
        "production_complete": False,
        "writes_target_dataset": False,
        "writes_target_packet": False,
        "global_candidate_cache_overwritten": False,
        "provider_execution_triggered": False,
        "worker_execution_triggered": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    expected_factor = {
        **expected_common,
        "request_digest": contract.get("factor_request_digest"),
        "output_kind": FACTOR_OUTPUT_CONTRACT["output_kind"],
        "target_dataset": FACTOR_TARGET_DATASET,
        "target_packet_key": FACTOR_TARGET_PACKET_KEY,
        "output_contract_digest": FACTOR_OUTPUT_CONTRACT_DIGEST,
    }
    expected_radar = {
        **expected_common,
        "request_digest": contract.get("radar_request_digest"),
        "output_kind": RADAR_OUTPUT_CONTRACT["output_kind"],
        "target_dataset": RADAR_TARGET_DATASET,
        "target_packet_key": RADAR_TARGET_PACKET_KEY,
        "output_contract_digest": RADAR_OUTPUT_CONTRACT_DIGEST,
    }

    def packet_checks(
        prefix: str,
        packet: Mapping[str, Any],
        expected: Mapping[str, Any],
    ) -> dict[str, bool]:
        task_id = str(packet.get("task_id") or "")
        expected_keys = set(expected) | {"task_id", "packet_digest"}
        return {
            f"{prefix}_fields_exact": set(packet) == expected_keys,
            f"{prefix}_task_id_valid": bool(re.fullmatch(r"local-[0-9a-f]{12}", task_id)),
            f"{prefix}_authoritative_fields_exact": all(
                _exact_value(packet.get(key), value) for key, value in expected.items()
            ),
            f"{prefix}_packet_digest_exact": (
                _safe_digest(packet.get("packet_digest"))
                == _digest(
                    {key: value for key, value in packet.items() if key != "packet_digest"}
                )
            ),
        }

    checks = {
        "current_head_exact": bool(
            re.fullmatch(r"[0-9a-f]{40}", str(contract.get("head_full") or ""))
            and contract.get("head_full") == _current_head_full()
        ),
        "shared_scope_recomputed": (
            _safe_digest(contract.get("shared_scope_hash")) == _digest(shared)
        ),
        "provider_digests_complete": all(
            _safe_digest(provider.get(key))
            for key in (
                "provider_scope_hash",
                "provider_version_digest",
                "universe_digest",
                "artifact_manifest_digest",
            )
        ),
        **packet_checks("factor", factor_request, expected_factor),
        **packet_checks("radar", radar_request, expected_radar),
        "output_digests_are_distinct": (
            factor_request.get("output_contract_digest")
            != radar_request.get("output_contract_digest")
        ),
        "target_datasets_are_distinct": (
            factor_request.get("target_dataset") != radar_request.get("target_dataset")
        ),
        "target_packets_are_distinct": (
            factor_request.get("target_packet_key") != radar_request.get("target_packet_key")
        ),
        "shared_scope_exact": bool(
            factor_request.get("shared_scope_hash")
            and factor_request.get("shared_scope_hash") == radar_request.get("shared_scope_hash")
        ),
        "request_digests_are_distinct": bool(
            _safe_digest(factor_request.get("request_digest"))
            and _safe_digest(radar_request.get("request_digest"))
            and factor_request.get("request_digest") != radar_request.get("request_digest")
        ),
        "packet_digests_are_distinct": bool(
            _safe_digest(factor_request.get("packet_digest"))
            and _safe_digest(radar_request.get("packet_digest"))
            and factor_request.get("packet_digest") != radar_request.get("packet_digest")
        ),
        "task_ids_are_distinct": bool(
            factor_request.get("task_id")
            and factor_request.get("task_id") != radar_request.get("task_id")
        ),
    }
    blockers = [key for key, ready in checks.items() if ready is not True]
    return {
        "ready": not blockers,
        "checks": checks,
        "blockers": blockers,
        "factor_rows_accepted_as_radar": False,
        "radar_rows_accepted_as_factor": False,
        "production_complete": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
    }


def validate_independent_output_requests(
    factor_request: Mapping[str, Any],
    radar_request: Mapping[str, Any],
    *,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Rebuild authoritative local bindings before validating two request packets."""

    requested_digest = factor_request.get(
        "requested_effective_dated_industry_membership_digest"
    )
    contract = build_full_market_factor_radar_map_reduce_contract(
        {"effective_dated_industry_membership_digest": requested_digest},
        evidence_root=evidence_root,
    )
    return _validate_independent_output_requests(factor_request, radar_request, contract)


def _request_packet(
    contract: Mapping[str, Any],
    *,
    output_kind: str,
    target_dataset: str,
    target_packet_key: str,
    output_contract_digest: str,
    request_digest: str,
) -> dict[str, Any]:
    provider = contract.get("provider") if isinstance(contract.get("provider"), Mapping) else {}
    packet = {
        "schema_version": CHILD_SCHEMA_VERSION,
        "status": (
            "execution_request_recorded_authoritative_inputs_pending"
            if contract.get("execution_request_scope_ready") is True
            else "execution_request_blocked_prerequisites_missing"
        ),
        "head_full": contract.get("head_full"),
        "shared_scope_hash": contract.get("shared_scope_hash"),
        "request_digest": request_digest,
        "output_kind": output_kind,
        "target_dataset": target_dataset,
        "target_packet_key": target_packet_key,
        "output_contract_digest": output_contract_digest,
        "provider_scope_hash": provider.get("provider_scope_hash"),
        "provider_version_digest": provider.get("provider_version_digest"),
        "universe_digest": provider.get("universe_digest"),
        "artifact_manifest_digest": provider.get("artifact_manifest_digest"),
        "universe_count": provider.get("universe_count"),
        "required_sessions": REQUIRED_SESSIONS,
        "validated_trade_date": provider.get("validated_trade_date"),
        "requested_effective_dated_industry_membership_digest": contract.get(
            "shared_scope_material", {}
        ).get("requested_effective_dated_industry_membership_digest"),
        "effective_dated_industry_membership_verified": False,
        "blockers": list(contract.get("blockers") or []),
        "dispatch_allowed": False,
        "external_trusted_lineage_runner_available": False,
        "production_complete": False,
        "writes_target_dataset": False,
        "writes_target_packet": False,
        "global_candidate_cache_overwritten": False,
        "provider_execution_triggered": False,
        "worker_execution_triggered": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    packet["packet_digest"] = _digest(packet)
    return packet


def _local_request_ledger(api: str, packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "api": api,
            "request_params_safe": {
                "head_full": packet.get("head_full"),
                "shared_scope_hash": packet.get("shared_scope_hash"),
                "request_digest": packet.get("request_digest"),
                "target_dataset": packet.get("target_dataset"),
                "universe_count": packet.get("universe_count"),
                "required_sessions": packet.get("required_sessions"),
            },
            "row_count": 0,
            "call_status": str(packet.get("status") or "execution_request_blocked"),
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "redis_called": False,
            "celery_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    ]


def run_full_market_factor_radar_map_reduce_request(
    payload: Any = None,
    *,
    evidence_root: Path | None = None,
    meta_path: Path | None = None,
) -> dict[str, Any]:
    """Persist local execution requests; never dispatch provider or workers."""

    contract = build_full_market_factor_radar_map_reduce_contract(
        payload,
        evidence_root=evidence_root,
    )
    factor_task_id = f"local-{uuid.uuid4().hex[:12]}"
    radar_task_id = f"local-{uuid.uuid4().hex[:12]}"
    coordinator_task_id = f"local-{uuid.uuid4().hex[:12]}"
    factor_packet = _request_packet(
        contract,
        output_kind=str(FACTOR_OUTPUT_CONTRACT["output_kind"]),
        target_dataset=FACTOR_TARGET_DATASET,
        target_packet_key=FACTOR_TARGET_PACKET_KEY,
        output_contract_digest=FACTOR_OUTPUT_CONTRACT_DIGEST,
        request_digest=str(contract.get("factor_request_digest") or ""),
    )
    factor_packet["task_id"] = factor_task_id
    factor_packet["packet_digest"] = _digest(
        {key: value for key, value in factor_packet.items() if key != "packet_digest"}
    )
    radar_packet = _request_packet(
        contract,
        output_kind=str(RADAR_OUTPUT_CONTRACT["output_kind"]),
        target_dataset=RADAR_TARGET_DATASET,
        target_packet_key=RADAR_TARGET_PACKET_KEY,
        output_contract_digest=RADAR_OUTPUT_CONTRACT_DIGEST,
        request_digest=str(contract.get("radar_request_digest") or ""),
    )
    radar_packet["task_id"] = radar_task_id
    radar_packet["packet_digest"] = _digest(
        {key: value for key, value in radar_packet.items() if key != "packet_digest"}
    )
    independence = _validate_independent_output_requests(factor_packet, radar_packet, contract)
    if independence.get("ready") is not True:
        raise RuntimeError("independent_output_request_integrity_failed")
    factor_ledger = _local_request_ledger("local_factor_full_market_map_reduce_request", factor_packet)
    radar_ledger = _local_request_ledger("local_candidate_radar_map_reduce_request", radar_packet)
    factor_task = task_service.build_task_record(
        FACTOR_TASK_TYPE,
        task_id=factor_task_id,
        output_packet_key=FACTOR_REQUEST_PACKET_KEY,
        payload=factor_packet,
        status="success",
        progress=1.0,
        current_step=str(factor_packet["status"]),
        warnings=["execution_request_only_no_provider_worker_or_production_write"],
        call_ledger=factor_ledger,
    )
    radar_task = task_service.build_task_record(
        RADAR_TASK_TYPE,
        task_id=radar_task_id,
        output_packet_key=RADAR_REQUEST_PACKET_KEY,
        payload=radar_packet,
        status="success",
        progress=1.0,
        current_step=str(radar_packet["status"]),
        warnings=["execution_request_only_no_provider_worker_or_candidate_cache_write"],
        call_ledger=radar_ledger,
    )
    coordinator_payload = {
        **dict(contract),
        "task_id": coordinator_task_id,
        "factor_task_id": factor_task_id,
        "factor_request_packet_key": FACTOR_REQUEST_PACKET_KEY,
        "factor_request_packet_digest": factor_packet.get("packet_digest"),
        "radar_task_id": radar_task_id,
        "radar_request_packet_key": RADAR_REQUEST_PACKET_KEY,
        "radar_request_packet_digest": radar_packet.get("packet_digest"),
        "independent_output_request_validation": independence,
    }
    coordinator_payload["packet_digest"] = _digest(coordinator_payload)
    coordinator_ledger = _local_request_ledger(
        "local_full_market_factor_radar_map_reduce_request",
        {
            **coordinator_payload,
            "request_digest": coordinator_payload.get("packet_digest"),
            "target_dataset": "two_independent_outputs",
            "universe_count": contract.get("provider", {}).get("universe_count"),
            "required_sessions": REQUIRED_SESSIONS,
        },
    )
    coordinator = task_service.build_task_record(
        COORDINATOR_TASK_TYPE,
        task_id=coordinator_task_id,
        output_packet_key=COORDINATOR_PACKET_KEY,
        payload=coordinator_payload,
        status="success",
        progress=1.0,
        current_step=str(contract.get("status") or "execution_request_blocked"),
        warnings=[
            "shared_map_reduce_execution_request_only_no_provider_redis_celery_dispatch",
            "factor_and_candidate_radar_outputs_require_independent_trusted_lineage",
        ],
        call_ledger=coordinator_ledger,
    )
    store = SQLiteMetaStore(Path(meta_path or SQLITE_META_PATH))
    store.write_packet_task_bundle_atomic(
        packets={
            FACTOR_REQUEST_PACKET_KEY: factor_packet,
            RADAR_REQUEST_PACKET_KEY: radar_packet,
            COORDINATOR_PACKET_KEY: coordinator_payload,
        },
        tasks=[factor_task, radar_task, coordinator],
    )
    coordinator["payload_safe"] = coordinator_payload
    coordinator["external_calls_triggered"] = False
    coordinator["tushare_called"] = False
    coordinator["deepseek_called"] = False
    coordinator["github_called"] = False
    coordinator["does_not_execute_trades"] = True
    coordinator["does_not_modify_strategy_action"] = True
    return coordinator
