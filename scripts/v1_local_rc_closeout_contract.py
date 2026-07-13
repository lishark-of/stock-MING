#!/usr/bin/env python3
"""Validate the sanitized Command Center 3.0 v1 local-RC closeout contract.

The contract consumes the read-only evaluator result and independently derives
version, LTG, and production-closeout counts.  It deliberately keeps the local
RC claim separate from production strict closeout.  No source payload or local
path is copied into the contract result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import v1_closeout_service  # noqa: E402


SCHEMA_VERSION = "command_center_3_v1_local_rc_closeout_contract.v1"
EVIDENCE_FILENAME = "v1_local_rc_closeout_contract.json"

SEALED_VERSION_CHAIN = (
    ("v0.1", "38604dae31259d9004a58b77ab0129fc65947ff2"),
    ("v0.2", "c69eaf3b0284955717a3ff34b0cc577459f793cf"),
    ("v0.3", "8877748e89e3f57f07beead064edd6012ea3dbd8"),
    ("v0.4", "b9bc602ca1dd6ea21d49e5071d84def32b595b54"),
    ("v0.5", "864df775a54b6515a19d76dda826455f5b2be70b"),
    ("v0.6", "52de0b5ad9fe718255c49d6a535b859392cd845a"),
    ("v0.7", "65115c7a886f7358c6b02e955abf864848bf79c8"),
)
EXPECTED_VERSION_IDS = tuple(version for version, _sha in SEALED_VERSION_CHAIN)
EXPECTED_LTG_IDS = tuple(f"LTG-{index:02d}" for index in range(1, 15))

LOCAL_VERSION_REQUIREMENTS = {
    "LTG-01": ("v0.2",),
    "LTG-02": ("v0.2", "v0.3"),
    "LTG-03": ("v0.3",),
    "LTG-04": ("v0.3", "v0.4"),
    "LTG-05": ("v0.4",),
    "LTG-06": ("v0.4",),
    "LTG-07": ("v0.5",),
    "LTG-08": ("v0.5", "v0.6"),
    "LTG-09": ("v0.6",),
    "LTG-10": ("v0.5", "v0.6"),
    "LTG-11": ("v0.6",),
    "LTG-12": ("v0.7",),
    "LTG-13": ("v0.5", "v0.6"),
    "LTG-14": ("v0.6",),
}

PRODUCTION_REQUIREMENTS = {
    "LTG-01": ("trade_cal_provider_direct", "release_promotion_current_head"),
    "LTG-02": ("full_interface_provider_production", "release_promotion_current_head"),
    "LTG-03": (
        "factor_small_pool_provider_direct",
        "factor_production_promotion",
        "release_promotion_current_head",
    ),
    "LTG-04": (
        "full_market_worker_runtime",
        "production_storage",
        "release_promotion_current_head",
    ),
    "LTG-05": ("production_storage", "release_promotion_current_head"),
    "LTG-06": ("celery_redis_runtime", "release_promotion_current_head"),
    "LTG-07": ("governed_model_runtime", "release_promotion_current_head"),
    "LTG-08": ("next_session_production_replacement", "release_promotion_current_head"),
    "LTG-09": (
        "desktop_production_package",
        "developer_signing_notarization",
        "release_promotion_current_head",
    ),
    "LTG-10": ("streamlit_primary_retired", "release_promotion_current_head"),
    "LTG-11": ("remote_ci_current_head", "release_promotion_current_head"),
    "LTG-12": ("qmt_research_isolation",),
    "LTG-13": (
        "candidate_radar_production_replacement",
        "full_market_worker_runtime",
        "release_promotion_current_head",
    ),
    "LTG-14": ("motion_production_promoted", "release_promotion_current_head"),
}

EXPECTED_PRODUCTION_FACT_KEYS = tuple(
    sorted({item for values in PRODUCTION_REQUIREMENTS.values() for item in values})
)

_ALLOWED_AUDIT_KEYS = {
    "contains_secret",
    "raw_account_or_config_exposed",
    "raw_packet_payloads_exposed",
    "raw_payload_exposed",
    "total_tokens",
    "retry_tokens",
    "token_usage_complete",
    "token_budget_cost_evidence_complete",
}
_FORBIDDEN_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_key",
    "credential",
    "password",
    "private_key",
    "account_id",
    "raw_payload",
    "raw_account",
    "raw_config",
    "token",
)
_FORBIDDEN_VALUE_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "api_key=",
    "password=",
    "token=",
)


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_commit_sha(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_exact_nonnegative_int(value: Any, expected: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == expected


def _criterion(name: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": name,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "evidence": evidence,
    }


def _has_sensitive_material(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized not in _ALLOWED_AUDIT_KEYS and any(
                marker in normalized for marker in _FORBIDDEN_KEY_PARTS
            ):
                return True
            if _has_sensitive_material(item):
                return True
        return False
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_has_sensitive_material(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(marker.lower() in lowered for marker in _FORBIDDEN_VALUE_MARKERS)
    return False


def _version_evidence_integrity(rows: list[Mapping[str, Any]]) -> bool:
    if len(rows) != len(EXPECTED_VERSION_IDS):
        return False
    for row in rows:
        summaries = _rows(row.get("source_summaries"))
        if not _is_exact_nonnegative_int(row.get("required_source_count"), len(summaries)):
            return False
        if not _is_exact_nonnegative_int(
            row.get("observed_source_count"),
            sum(summary.get("observed") is True for summary in summaries),
        ):
            return False
        if row.get("local_direct_evidence_ready") is True and not all(
            summary.get("observed") is True for summary in summaries
        ):
            return False
        for summary in summaries:
            if summary.get("raw_payload_exposed") is not False:
                return False
            if summary.get("observed") is True:
                safe_fields = _mapping(summary.get("safe_fields"))
                if not _is_sha256(summary.get("safe_evidence_digest")):
                    return False
                if summary.get("safe_evidence_digest") != _canonical_digest(safe_fields):
                    return False
        if not _is_string_list(row.get("blockers")):
            return False
        blockers = _string_list(row.get("blockers"))
        expected_digest = _canonical_digest(
            {
                "version": str(row.get("version") or ""),
                "ready": row.get("local_direct_evidence_ready") is True,
                "source_digests": [
                    str(summary.get("safe_evidence_digest") or "") for summary in summaries
                ],
                "blockers": blockers,
            }
        )
        if row.get("safe_evidence_digest") != expected_digest:
            return False
    return True


def _qmt_research_isolation_ready(packet: Mapping[str, Any]) -> bool:
    summary = _mapping(packet.get("qmt_research_isolation_summary"))
    safe_fields = _mapping(summary.get("safe_fields"))
    false_fields = (
        "external_calls_triggered",
        "qmt_called",
        "qmt_external_connection_attempted",
        "qmt_process_discovered",
        "qmt_client_imported",
        "xtquant_imported",
        "broker_called",
        "broker_session_opened",
        "account_query_executed",
        "real_order_submitted",
        "real_order_cancelled",
        "real_trade_executed",
        "real_holdings_modified",
        "real_trading_enabled",
        "external_qmt_integration_verified",
        "paper_trading_sandbox_ready",
        "worker_dispatched",
        "tushare_called",
        "deepseek_called",
        "github_called",
        "contains_secret",
    )
    zero_fields = (
        "external_call_count",
        "qmt_connection_count",
        "broker_session_count",
        "real_order_count",
        "real_trade_count",
    )
    accepted_statuses = {
        "local_export_contract_and_replay_verified",
        "local_scope_replay_verified_export_pending",
    }
    return bool(
        summary.get("observed") is True
        and summary.get("schema_version") == "qmt_readonly_local_replay_result.v1"
        and summary.get("status") in accepted_statuses
        and safe_fields.get("schema_version") == "qmt_readonly_local_replay_result.v1"
        and safe_fields.get("status") in accepted_statuses
        and safe_fields.get("mode") == "local_research_replay"
        and all(safe_fields.get(field) is False for field in false_fields)
        and all(safe_fields.get(field) == 0 for field in zero_fields)
        and safe_fields.get("does_not_execute_trades") is True
        and safe_fields.get("does_not_modify_strategy_action") is True
        and safe_fields.get("does_not_modify_holdings") is True
        and summary.get("raw_payload_exposed") is False
        and _is_sha256(summary.get("safe_evidence_digest"))
        and summary.get("safe_evidence_digest") == _canonical_digest(safe_fields)
    )


def _boundary_is_read_only_and_offline(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("mode") == "read_only_local_evidence_closeout"
        and packet.get("cache_only") is True
        and packet.get("read_only") is True
        and packet.get("creates_task") is False
        and packet.get("writes_storage") is False
        and packet.get("external_calls_triggered") is False
        and packet.get("tushare_called") is False
        and packet.get("deepseek_called") is False
        and packet.get("github_called") is False
        and packet.get("qmt_called") is False
        and packet.get("broker_called") is False
        and packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("contains_secret") is False
        and packet.get("raw_packet_payloads_exposed") is False
        and packet.get("raw_account_or_config_exposed") is False
    )


def build_contract(
    *,
    evidence_root: Path | None = None,
    evaluation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    packet = (
        evaluation
        if evaluation is not None
        else v1_closeout_service.build_v1_closeout_evaluation(evidence_root=evidence_root)
    )
    packet = _mapping(packet)
    raw_version_rows = packet.get("version_evidence_rows")
    raw_ltg_rows = packet.get("ltg_closure_rows")
    raw_fact_rows = packet.get("production_fact_rows")
    version_rows = _rows(raw_version_rows)
    ltg_rows = _rows(raw_ltg_rows)
    fact_rows = _rows(raw_fact_rows)

    version_ids = [str(row.get("version") or "") for row in version_rows]
    ltg_ids = [str(row.get("id") or "") for row in ltg_rows]
    fact_keys = [str(row.get("evidence_key") or "") for row in fact_rows]
    facts = {
        str(row.get("evidence_key") or ""): row.get("observed") is True for row in fact_rows
    }

    version_inventory_valid = (
        isinstance(raw_version_rows, list)
        and len(raw_version_rows) == len(version_rows)
        and version_ids == list(EXPECTED_VERSION_IDS)
        and len(set(version_ids)) == len(EXPECTED_VERSION_IDS)
    )
    version_ready_count = sum(
        row.get("local_direct_evidence_ready") is True for row in version_rows
    )
    missing_local_versions = [
        str(row.get("version") or "")
        for row in version_rows
        if row.get("local_direct_evidence_ready") is not True
    ]
    version_counts_valid = bool(
        _is_exact_nonnegative_int(packet.get("local_version_ready_count"), version_ready_count)
        and _is_exact_nonnegative_int(packet.get("local_version_total_count"), len(version_rows))
        and _is_string_list(packet.get("missing_local_versions"))
        and _string_list(packet.get("missing_local_versions")) == missing_local_versions
        and packet.get("local_direct_evidence_ready")
        is (version_ready_count == len(EXPECTED_VERSION_IDS))
    )
    all_versions_locally_ready = bool(
        version_inventory_valid
        and len(version_rows) == len(EXPECTED_VERSION_IDS)
        and version_ready_count == len(EXPECTED_VERSION_IDS)
        and all(
            _is_string_list(row.get("blockers"))
            and _string_list(row.get("blockers")) == []
            for row in version_rows
        )
    )

    ltg_inventory_valid = (
        isinstance(raw_ltg_rows, list)
        and len(raw_ltg_rows) == len(ltg_rows)
        and ltg_ids == list(EXPECTED_LTG_IDS)
        and len(set(ltg_ids)) == len(EXPECTED_LTG_IDS)
    )
    facts_inventory_valid = bool(
        isinstance(raw_fact_rows, list)
        and len(raw_fact_rows) == len(fact_rows)
        and fact_keys == sorted(EXPECTED_PRODUCTION_FACT_KEYS)
        and len(set(fact_keys)) == len(EXPECTED_PRODUCTION_FACT_KEYS)
        and all(isinstance(row.get("observed"), bool) for row in fact_rows)
    )
    version_ready = {
        str(row.get("version") or ""): row.get("local_direct_evidence_ready") is True
        for row in version_rows
    }
    ltg_derivation_valid = ltg_inventory_valid and facts_inventory_valid
    locally_ready_ltg_count = 0
    non_ltg12_missing_external_is_blocked = True
    sanitized_ltg_rows: list[dict[str, Any]] = []
    for row in ltg_rows:
        goal_id = str(row.get("id") or "")
        local_requirements = list(LOCAL_VERSION_REQUIREMENTS.get(goal_id, ()))
        production_requirements = list(PRODUCTION_REQUIREMENTS.get(goal_id, ()))
        expected_missing_local = [
            version for version in local_requirements if version_ready.get(version) is not True
        ]
        expected_local_ready = not expected_missing_local
        expected_missing_production = [
            item for item in production_requirements if facts.get(item) is not True
        ]
        expected_production_complete = expected_local_ready and not expected_missing_production
        expected_blockers = [
            f"local_direct_evidence_missing:{version}" for version in expected_missing_local
        ]
        if goal_id != "LTG-12":
            expected_blockers.extend(
                f"external_or_environment_evidence_missing:{item}"
                for item in expected_missing_production
            )
        row_valid = bool(
            _is_string_list(row.get("required_local_versions"))
            and _string_list(row.get("required_local_versions")) == local_requirements
            and _is_string_list(row.get("missing_local_direct_evidence"))
            and _string_list(row.get("missing_local_direct_evidence")) == expected_missing_local
            and row.get("local_direct_evidence_ready") is expected_local_ready
            and _is_string_list(row.get("required_production_evidence"))
            and _string_list(row.get("required_production_evidence"))
            == production_requirements
            and _is_string_list(row.get("missing_production_evidence"))
            and _string_list(row.get("missing_production_evidence"))
            == expected_missing_production
            and _is_string_list(row.get("external_or_environment_blockers"))
            and _string_list(row.get("external_or_environment_blockers")) == expected_blockers
            and row.get("production_complete") is expected_production_complete
            and row.get("can_close") is expected_production_complete
            and row.get("closeout_decision")
            == (
                "strict_closeout_allowed"
                if expected_production_complete
                else "strict_closeout_blocked"
            )
        )
        ltg_derivation_valid = ltg_derivation_valid and row_valid
        if expected_local_ready:
            locally_ready_ltg_count += 1
        if goal_id != "LTG-12" and expected_missing_production:
            non_ltg12_missing_external_is_blocked = bool(
                non_ltg12_missing_external_is_blocked
                and row.get("can_close") is False
                and row.get("production_complete") is False
            )
        safe_goal_id = goal_id if goal_id in EXPECTED_LTG_IDS else "invalid_ltg_id"
        sanitized_ltg_rows.append(
            {
                "id": safe_goal_id,
                "local_direct_evidence_ready": row.get("local_direct_evidence_ready") is True,
                "production_complete": row.get("production_complete") is True,
                "can_close": row.get("can_close") is True,
                "missing_production_evidence_count": len(expected_missing_production),
            }
        )

    qmt_ready = _qmt_research_isolation_ready(packet)
    ltg12 = next((row for row in ltg_rows if row.get("id") == "LTG-12"), {})
    ltg12_scope_valid = bool(
        qmt_ready
        and facts.get("qmt_research_isolation") is True
        and ltg12.get("goal_scope") == "research_trade_isolation_only"
        and ltg12.get("future_real_trading_is_separate_unapproved_scope") is True
        and ltg12.get("local_direct_evidence_ready") is True
        and ltg12.get("production_complete") is True
        and ltg12.get("can_close") is True
        and _string_list(ltg12.get("missing_production_evidence")) == []
    )

    strict_done_count = sum(row.get("can_close") is True for row in ltg_rows)
    strict_total_count = len(ltg_rows)
    strict_remaining_count = strict_total_count - strict_done_count
    production_strict_complete = strict_total_count == len(EXPECTED_LTG_IDS) and all(
        row.get("can_close") is True for row in ltg_rows
    )
    strict_counts_valid = bool(
        _is_exact_nonnegative_int(packet.get("strict_closeout_done_count"), strict_done_count)
        and _is_exact_nonnegative_int(packet.get("strict_closeout_total_count"), strict_total_count)
        and _is_exact_nonnegative_int(
            packet.get("strict_closeout_remaining_count"), strict_remaining_count
        )
        and packet.get("strict_closeout") == f"{strict_done_count}/{strict_total_count}"
        and packet.get("production_strict_closeout_complete") is production_strict_complete
    )
    closed_ltg_ids = [
        (
            str(row.get("id") or "")
            if str(row.get("id") or "") in EXPECTED_LTG_IDS
            else "invalid_ltg_id"
        )
        for row in ltg_rows
        if row.get("can_close") is True
    ]
    local_and_production_are_separate = bool(
        packet.get("local_direct_evidence_ready") is all_versions_locally_ready
        and packet.get("production_strict_closeout_complete") is production_strict_complete
        and packet.get("evidence_boundary")
        == "v1_local_rc_is_local_direct_evidence_summary_production_strict_closeout_is_separate"
    )
    expected_packet_status = (
        "v1_local_evidence_ready_production_closeout_complete"
        if all_versions_locally_ready and production_strict_complete
        else "v1_local_evidence_ready_production_closeout_pending"
        if all_versions_locally_ready
        else "v1_local_evidence_incomplete_production_closeout_pending"
    )
    packet_status_valid = bool(
        packet.get("packet_key") == "command_center_3_v1_local_rc"
        and packet.get("schema_version") == "command_center_3_v1_local_rc.v1"
        and packet.get("status") == expected_packet_status
    )
    boundary_valid = _boundary_is_read_only_and_offline(packet)
    sanitized_input = not _has_sensitive_material(packet)
    evidence_integrity = _version_evidence_integrity(version_rows)
    local_rc_ready = bool(
        all_versions_locally_ready
        and version_counts_valid
        and evidence_integrity
        and ltg_derivation_valid
        and locally_ready_ltg_count == len(EXPECTED_LTG_IDS)
    )

    sealed_rows = [
        {"version": version, "sealed_sha": sealed_sha}
        for version, sealed_sha in SEALED_VERSION_CHAIN
    ]
    chain_material = {
        "schema_version": "command_center_3_sealed_version_chain.v1",
        "versions": sealed_rows,
    }
    sealed_chain_valid = bool(
        [row["version"] for row in sealed_rows] == list(EXPECTED_VERSION_IDS)
        and all(_is_commit_sha(row["sealed_sha"]) for row in sealed_rows)
        and len({row["sealed_sha"] for row in sealed_rows}) == len(sealed_rows)
    )
    chain_digest = _canonical_digest(chain_material)

    criteria = [
        _criterion("source_packet_schema_and_status", packet_status_valid, "v1 local RC packet"),
        _criterion(
            "sealed_version_chain_allowlist",
            sealed_chain_valid,
            f"{len(sealed_rows)}/{len(EXPECTED_VERSION_IDS)} sealed versions",
        ),
        _criterion(
            "version_rows_exact_order",
            version_inventory_valid,
            f"{len(version_rows)}/{len(EXPECTED_VERSION_IDS)} ordered version rows",
        ),
        _criterion(
            "version_evidence_digest_integrity",
            evidence_integrity,
            f"{len(version_rows)} sanitized version evidence rows",
        ),
        _criterion(
            "version_counts_derived_from_rows",
            version_counts_valid,
            f"{version_ready_count}/{len(version_rows)} ready",
        ),
        _criterion(
            "local_rc_all_versions_ready",
            all_versions_locally_ready,
            f"{version_ready_count}/{len(EXPECTED_VERSION_IDS)} local versions",
        ),
        _criterion(
            "ltg_inventory_exact_and_unique",
            ltg_inventory_valid,
            f"{len(ltg_rows)}/{len(EXPECTED_LTG_IDS)} LTGs",
        ),
        _criterion(
            "production_fact_inventory_exact_and_unique",
            facts_inventory_valid,
            f"{len(fact_rows)}/{len(EXPECTED_PRODUCTION_FACT_KEYS)} production facts",
        ),
        _criterion(
            "ltg_decisions_derived_from_rows",
            ltg_derivation_valid,
            f"{locally_ready_ltg_count}/{len(EXPECTED_LTG_IDS)} locally ready LTGs",
        ),
        _criterion(
            "strict_counts_derived_from_rows",
            strict_counts_valid,
            f"{strict_done_count}/{strict_total_count} strict closeout",
        ),
        _criterion(
            "local_rc_separate_from_production_strict",
            local_and_production_are_separate,
            "local RC and production strict are independently derived",
        ),
        _criterion(
            "ltg12_research_isolation_positive_closeout",
            ltg12_scope_valid,
            "research replay isolated; QMT/broker/order/trade remain disabled",
        ),
        _criterion(
            "missing_external_evidence_cannot_close_non_ltg12",
            non_ltg12_missing_external_is_blocked,
            "all externally blocked non-LTG-12 rows remain open",
        ),
        _criterion(
            "read_only_zero_external_boundary",
            boundary_valid,
            "cache-only evaluation; zero task/storage/provider/model/remote/trading calls",
        ),
        _criterion(
            "sanitized_no_secret_or_raw_material",
            sanitized_input,
            "no sensitive keys or values observed; output is allowlist-projected",
        ),
    ]
    passed = all(row["passed"] is True for row in criteria)

    sanitized_version_rows = [
        {
            "version": version,
            "sealed_sha": sealed_sha,
            "local_direct_evidence_ready": (
                index < len(version_rows)
                and version_rows[index].get("local_direct_evidence_ready") is True
            ),
        }
        for index, (version, sealed_sha) in enumerate(SEALED_VERSION_CHAIN)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "v1_local_rc_closeout_contract_passed"
            if passed
            else "v1_local_rc_closeout_contract_blocked"
        ),
        "passed": passed,
        "sealed_version_chain": sanitized_version_rows,
        "sealed_version_chain_digest": chain_digest,
        "local_rc": {
            "ready": local_rc_ready,
            "version_ready_count": version_ready_count,
            "version_total_count": len(EXPECTED_VERSION_IDS),
            "ltg_locally_ready_count": locally_ready_ltg_count,
            "ltg_total_count": len(EXPECTED_LTG_IDS),
            "production_strict_inferred_from_local_rc": False,
        },
        "production_strict": {
            "complete": production_strict_complete,
            "done_count": strict_done_count,
            "total_count": strict_total_count,
            "remaining_count": strict_remaining_count,
            "closed_ltg_ids": closed_ltg_ids,
        },
        "ltg12_research_isolation": {
            "ready": qmt_ready,
            "scope": "research_trade_isolation_only",
            "qmt_disabled": qmt_ready,
            "broker_disabled": qmt_ready,
            "real_order_path_disabled": qmt_ready,
            "real_trade_execution_disabled": qmt_ready,
            "future_real_trading_is_separate_unapproved_scope": True,
        },
        "ltg_rows": sanitized_ltg_rows,
        "boundary": {
            "validated": boundary_valid,
            "cache_only": True,
            "read_only": True,
            "creates_task": False,
            "writes_storage": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "qmt_called": False,
            "broker_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "raw_payloads_exposed": False,
        },
        "criteria": criteria,
    }


def _write_evidence(root: Path, contract: Mapping[str, Any]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / EVIDENCE_FILENAME
    path.write_text(
        json.dumps(dict(contract), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=v1_closeout_service.EVIDENCE_ROOT,
        help="Local evidence root to read; also receives the sanitized JSON when requested.",
    )
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help="Write the sanitized contract JSON below --evidence-root.",
    )
    args = parser.parse_args(argv)

    contract = build_contract(evidence_root=args.evidence_root)
    if args.write_evidence:
        _write_evidence(args.evidence_root, contract)
    print(json.dumps(contract, ensure_ascii=False, sort_keys=True))
    return 0 if contract["passed"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
