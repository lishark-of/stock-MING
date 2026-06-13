#!/usr/bin/env python3
"""Validate the local LTG-01 Data Health freshness contract.

This script is a push-gate guard, not a provider acceptance run. It calls only
the local Data Health cache builder and fails on unsafe regressions such as
external-call flags, trade/action mutation flags, or false provider-backed
completion claims.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import data_health_service  # noqa: E402


CONTRACT_KEYS = [
    "freshness_acceptance_summary",
    "freshness_long_window_sample_validation",
    "trade_cal_physical_validation",
    "trade_cal_provider_acceptance_runbook",
    "trade_cal_provider_acceptance_promotion_audit",
    "freshness_production_blocker_audit",
    "current_evidence_freshness_qa_contract",
    "current_evidence_decision_surface_audit",
    "current_evidence_producer_coverage_audit",
]


def _get(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def _row(criterion: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "evidence": evidence,
    }


def _flag_false(contract: dict[str, Any], *keys: str) -> bool:
    return all(contract.get(key) is False for key in keys)


def build_contract() -> dict[str, Any]:
    packet = data_health_service.read_data_health_timeline_cache()
    summary = _get(packet, "freshness_acceptance_summary")
    sample = _get(packet, "freshness_long_window_sample_validation")
    physical = _get(packet, "trade_cal_physical_validation")
    runbook = _get(packet, "trade_cal_provider_acceptance_runbook")
    promotion = _get(packet, "trade_cal_provider_acceptance_promotion_audit")
    blockers_audit = _get(packet, "freshness_production_blocker_audit")
    current = _get(packet, "current_evidence_freshness_qa_contract")
    surfaces = _get(packet, "current_evidence_decision_surface_audit")
    producers = _get(packet, "current_evidence_producer_coverage_audit")
    policy = _get(packet, "policy")
    counts = _get(packet, "counts")

    rows = [
        _row(
            "packet_cache_only_boundary",
            packet.get("mode") == "cache_only"
            and packet.get("cache_only") is True
            and packet.get("read_only") is True
            and _flag_false(packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "GET data health cache must remain local/read-only and no-provider.",
        ),
        _row(
            "packet_no_trade_or_action_mutation",
            packet.get("does_not_execute_trades") is True and packet.get("does_not_modify_strategy_action") is True,
            "Data Health must not execute trades or mutate strategy action.",
        ),
        _row(
            "acceptance_matrix_is_not_provider_acceptance",
            summary.get("scope") == "local_contract_not_real_trade_cal_validation"
            and summary.get("trade_cal_long_window_validation_done") is False
            and summary.get("real_provider_validation_done") is False
            and summary.get("blocks_composite_score") is True
            and summary.get("blocks_support_factors") is True
            and summary.get("blocks_evidence_preview") is True
            and summary.get("blocks_next_session_bridge_preview") is True,
            "Freshness matrix must stay a local boundary contract, not a real trade_cal acceptance run.",
        ),
        _row(
            "synthetic_sample_is_fixture",
            sample.get("fixture_is_synthetic") is True
            and sample.get("uses_actual_freshness_gate") is True
            and sample.get("trade_cal_long_window_validation_done") is False
            and _flag_false(sample, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Long-window sample must remain a local fixture that exercises the gate without provider calls.",
        ),
        _row(
            "local_trade_cal_physical_not_provider_backed",
            physical.get("scope") == "local_physical_trade_cal_parquet_validation"
            and physical.get("provider_backed_long_window_acceptance_done") is False
            and physical.get("provider_refresh_called_by_validation") is False
            and _flag_false(physical, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Local trade_cal artifact validation cannot imply provider-backed acceptance.",
        ),
        _row(
            "provider_runbook_execution_pending",
            runbook.get("schema_version") == "data_health_trade_cal_provider_acceptance_runbook.v1"
            and runbook.get("local_runbook_ready") is True
            and runbook.get("provider_backed_long_window_acceptance_done") is False
            and runbook.get("provider_refresh_called_by_runbook") is False
            and runbook.get("production_freshness_gate_complete") is False
            and _flag_false(runbook, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Provider runbook may be ready, but execution and provider-backed acceptance must remain pending.",
        ),
        _row(
            "provider_promotion_audit_is_read_only_pending",
            promotion.get("schema_version") == "data_health_trade_cal_provider_acceptance_promotion_audit.v1"
            and promotion.get("scope") == "local_snapshot_evidence_promotion_audit_no_provider_execution"
            and promotion.get("status")
            in {
                "trade_cal_provider_acceptance_promotion_pending",
                "trade_cal_provider_acceptance_promotion_ready",
            }
            and promotion.get("provider_refresh_called_by_audit") is False
            and promotion.get("production_freshness_gate_complete") is False
            and _flag_false(promotion, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Provider acceptance promotion audit must read local prior evidence only and never run trade_cal refresh itself.",
        ),
        _row(
            "freshness_production_blocker_audit_is_local_pending",
            blockers_audit.get("schema_version") == "data_health_freshness_production_blocker_audit.v1"
            and blockers_audit.get("scope") == "local_read_only_freshness_production_blocker_audit_no_provider_execution"
            and blockers_audit.get("status") == "freshness_production_blockers_visible"
            and blockers_audit.get("production_ready") is False
            and blockers_audit.get("provider_backed_trade_cal_acceptance_done") is False
            and blockers_audit.get("production_freshness_gate_complete") is False
            and int(blockers_audit.get("production_blocker_count") or 0) > 0
            and "provider_backed_trade_cal_acceptance" in blockers_audit.get("production_blockers", [])
            and _flag_false(blockers_audit, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and blockers_audit.get("does_not_execute_trades") is True
            and blockers_audit.get("does_not_modify_strategy_action") is True,
            "Freshness production blocker audit must stay local and keep provider-backed production blockers visible.",
        ),
        _row(
            "current_evidence_boundary_contract",
            current.get("schema_version") == "data_health_current_evidence_freshness_qa.v1"
            and current.get("current_evidence_requires_expected_trade_date") is True
            and current.get("provider_backed_long_window_acceptance_done") is False
            and current.get("blocks_composite_score") is True
            and current.get("blocks_support_factors") is True
            and current.get("blocks_evidence_preview") is True
            and current.get("blocks_next_session_bridge_preview") is True,
            "Current evidence QA must keep expected-date and research-only boundaries visible.",
        ),
        _row(
            "decision_surface_audit_is_read_only",
            surfaces.get("schema_version") == "data_health_current_evidence_decision_surface_audit.v1"
            and surfaces.get("does_not_rescore") is True
            and surfaces.get("does_not_filter_packet") is True
            and surfaces.get("does_not_mutate_decision_surfaces") is True
            and surfaces.get("provider_backed_long_window_acceptance_done") is False,
            "Decision-surface audit must stay read-only and cannot prove provider-backed freshness.",
        ),
        _row(
            "producer_coverage_audit_is_read_only",
            producers.get("schema_version") == "data_health_current_evidence_producer_coverage.v1"
            and producers.get("does_not_build_missing_packets") is True
            and producers.get("not_observed_is_not_production_proof") is True
            and producers.get("provider_backed_long_window_acceptance_done") is False,
            "Producer coverage audit checks visible fields only; not_observed cannot be production proof.",
        ),
        _row(
            "policy_flags_remain_conservative",
            policy.get("freshness_acceptance_matrix_is_local_contract") is True
            and policy.get("freshness_acceptance_matrix_calls_trade_cal") is False
            and policy.get("freshness_long_window_sample_calls_trade_cal") is False
            and policy.get("trade_cal_physical_validation_calls_trade_cal_provider") is False
            and policy.get("real_trade_cal_long_window_validation_done") is False
            and policy.get("provider_backed_trade_cal_acceptance_still_pending") is True,
            "Policy flags must keep local contracts separate from provider-backed production acceptance.",
        ),
        _row(
            "contract_rows_are_present",
            all(key in packet for key in CONTRACT_KEYS)
            and int(counts.get("freshness_acceptance_scenario_count") or 0) >= 8
            and int(counts.get("trade_cal_provider_acceptance_promotion_row_count") or 0) >= 10
            and int(counts.get("freshness_production_blocker_row_count") or 0) >= 8
            and int(counts.get("current_evidence_freshness_qa_row_count") or 0) >= 8
            and int(counts.get("current_evidence_decision_surface_row_count") or 0) >= 5
            and int(counts.get("current_evidence_producer_coverage_row_count") or 0) >= 6,
            "Push gate expects all LTG-01 Data Health contracts and row groups to be present.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "data_health_freshness_push_gate_contract.v1",
        "status": "data_health_freshness_contract_passed" if not blockers else "data_health_freshness_contract_blocked",
        "scope": "local_cache_contract_no_provider_execution",
        "ltg": "LTG-01/LTG-11",
        "contract_ready": not blockers,
        "provider_backed_trade_cal_acceptance_done": False,
        "production_freshness_gate_complete": False,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "rows": rows,
        "observed_counts": {
            "freshness_acceptance_scenario_count": counts.get("freshness_acceptance_scenario_count"),
            "current_evidence_freshness_qa_row_count": counts.get("current_evidence_freshness_qa_row_count"),
            "current_evidence_decision_surface_row_count": counts.get("current_evidence_decision_surface_row_count"),
            "current_evidence_producer_coverage_row_count": counts.get("current_evidence_producer_coverage_row_count"),
            "trade_cal_provider_acceptance_pending_count": counts.get("trade_cal_provider_acceptance_pending_count"),
            "trade_cal_provider_acceptance_promotion_blocker_count": counts.get(
                "trade_cal_provider_acceptance_promotion_blocker_count"
            ),
            "trade_cal_provider_acceptance_evidence_row_count": counts.get(
                "trade_cal_provider_acceptance_evidence_row_count"
            ),
            "freshness_production_blocker_count": counts.get("freshness_production_blocker_count"),
        },
        "note": "This is a local push-gate contract. Pending/provider-backed blockers are expected until explicit provider acceptance is run later.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-01 Data Health freshness contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"data_health_freshness_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "provider_backed_trade_cal_acceptance_done: false".format(**contract)
        )
        print(
            "external_calls_triggered: false; tushare_called: false; "
            "deepseek_called: false; github_called: false; does_not_execute_trades: true"
        )
        if contract["blockers"]:
            print("blockers: " + ", ".join(contract["blockers"]))
    return 0 if contract["contract_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
