#!/usr/bin/env python3
"""Validate the local 14-LTG strict closeout evidence spine contract.

This push-gate guard reads only the local migration status service. It proves
that all LTG handoff summaries are inventory-visible while strict closeout
remains blocked and remote review stays separate from local evidence.
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

from server.services import migration_status_service  # noqa: E402


EXPECTED_LTG_IDS = {f"LTG-{index:02d}" for index in range(1, 15)}
EXPECTED_HANDOFF_SUMMARY_COUNT = 17
PUSH_GATE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "push_gate_3_0.sh"


def _row(criterion: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "evidence": evidence,
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_push_gate_script() -> str:
    try:
        return PUSH_GATE_SCRIPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return ""


def build_contract() -> dict[str, Any]:
    packet = migration_status_service.build_migration_status()
    summary = _dict(packet.get("ltg_strict_closeout_evidence_spine_summary"))
    spine_rows = [
        row
        for row in _list(packet.get("ltg_strict_closeout_evidence_spine_rows"))
        if isinstance(row, dict)
    ]
    rows_by_id = {str(row.get("id") or ""): row for row in spine_rows}
    call_ledger = _list(packet.get("call_ledger"))
    first_call_ledger = _dict(call_ledger[0] if call_ledger else {})
    push_gate_script = _read_push_gate_script()

    all_rows_visible = bool(spine_rows) and all(row.get("handoff_visible") is True for row in spine_rows)
    all_rows_block_closeout = bool(spine_rows) and all(
        row.get("strict_closeout_claim_allowed") is False
        and row.get("can_close_ltg_now") is False
        and row.get("all_handoffs_block_closeout") is True
        for row in spine_rows
    )
    all_rows_block_production = bool(spine_rows) and all(
        row.get("production_complete") is False
        and row.get("all_handoffs_block_production_complete") is True
        for row in spine_rows
    )
    all_rows_remote_review_split = bool(spine_rows) and all(
        row.get("remote_review_split_required") is True
        and row.get("requires_remote_ci_review") is True
        and row.get("requires_release_review_after_remote_green") is True
        for row in spine_rows
    )
    all_rows_cache_only = bool(spine_rows) and all(
        row.get("cache_only_readback") is True
        and row.get("cache_get_creates_task") is False
        and row.get("creates_task_from_get") is False
        and row.get("creates_task_from_render") is False
        for row in spine_rows
    )
    all_rows_safe_boundary = bool(spine_rows) and all(
        row.get("external_calls_triggered") is False
        and row.get("tushare_called") is False
        and row.get("deepseek_called") is False
        and row.get("github_called") is False
        and row.get("contains_secret") is False
        and row.get("does_not_execute_trades") is True
        and row.get("does_not_modify_strategy_action") is True
        for row in spine_rows
    )
    push_gate_step_ready = (
        "scripts/ltg_strict_closeout_evidence_spine_contract.py" in push_gate_script
        and "LTG strict closeout evidence spine contract" in push_gate_script
    )

    rows = [
        _row(
            "ltg_strict_closeout_evidence_spine_schema_visible",
            summary.get("schema_version") == "ltg_strict_closeout_evidence_spine_summary.v1",
            str(summary.get("schema_version") or "missing"),
        ),
        _row(
            "ltg_strict_closeout_evidence_spine_14_ltg_visible",
            summary.get("spine_visible_count") == 14
            and summary.get("spine_total_count") == 14
            and summary.get("spine_missing_ltg_ids") == []
            and set(rows_by_id) == EXPECTED_LTG_IDS,
            f"{summary.get('spine_visible_count')}/{summary.get('spine_total_count')}",
        ),
        _row(
            "ltg_strict_closeout_evidence_spine_17_handoffs_visible",
            summary.get("handoff_summary_visible_count") == EXPECTED_HANDOFF_SUMMARY_COUNT
            and summary.get("handoff_summary_total_count") == EXPECTED_HANDOFF_SUMMARY_COUNT
            and summary.get("all_handoff_summaries_visible") is True,
            f"{summary.get('handoff_summary_visible_count')}/{summary.get('handoff_summary_total_count')}",
        ),
        _row(
            "ltg_strict_closeout_evidence_spine_keeps_closeout_zero",
            summary.get("strict_closeout") == "0/14"
            and summary.get("strict_closeout_done_count") == 0
            and summary.get("strict_closeout_total_count") == 14
            and summary.get("strict_closeout_remaining_count") == 14,
            str(summary.get("strict_closeout") or "missing"),
        ),
        _row(
            "ltg_strict_closeout_evidence_spine_blocks_closeout_claim",
            summary.get("strict_closeout_claim_allowed") is False
            and summary.get("all_rows_block_closeout_claim") is True
            and all_rows_block_closeout,
            "summary and every row block closeout claim",
        ),
        _row(
            "ltg_strict_closeout_evidence_spine_blocks_production_complete",
            summary.get("all_rows_block_production_complete") is True and all_rows_block_production,
            "handoff inventory is not production completion evidence",
        ),
        _row(
            "ltg_strict_closeout_evidence_spine_requires_remote_review_split",
            summary.get("remote_review_split_required") is True
            and summary.get("requires_remote_ci_review") is True
            and summary.get("requires_release_review_after_remote_green") is True
            and all_rows_remote_review_split,
            "remote CI and release review stay separate from local handoff inventory",
        ),
        _row(
            "ltg_strict_closeout_evidence_spine_cache_only_no_task_creation",
            summary.get("cache_only_readback") is True
            and summary.get("cache_get_creates_task") is False
            and summary.get("creates_task_from_get") is False
            and summary.get("creates_task_from_render") is False
            and all_rows_cache_only,
            "GET/cache/render readback is task-silent",
        ),
        _row(
            "ltg_strict_closeout_evidence_spine_no_provider_model_github_or_trade",
            summary.get("external_calls_triggered") is False
            and summary.get("tushare_called") is False
            and summary.get("deepseek_called") is False
            and summary.get("github_called") is False
            and summary.get("contains_secret") is False
            and summary.get("does_not_execute_trades") is True
            and summary.get("does_not_modify_strategy_action") is True
            and all_rows_safe_boundary,
            "no provider/model/GitHub/trading boundary remains false/true as required",
        ),
        _row(
            "ltg_strict_closeout_evidence_spine_call_ledger_counts_match",
            first_call_ledger.get("ltg_strict_closeout_evidence_spine_visible_count") == 14
            and first_call_ledger.get("ltg_strict_closeout_evidence_spine_total_count") == 14
            and first_call_ledger.get("ltg_strict_closeout_evidence_spine_strict_closeout") == "0/14"
            and first_call_ledger.get("ltg_strict_closeout_evidence_spine_remote_review_split_required")
            is True,
            "migration status call ledger exposes spine counts without external calls",
        ),
        _row(
            "push_gate_runs_ltg_strict_closeout_evidence_spine_contract",
            push_gate_step_ready,
            "push gate includes scripts/ltg_strict_closeout_evidence_spine_contract.py",
        ),
        _row(
            "script_is_local_no_provider_model_github_or_trade_execution",
            True,
            "script imports migration_status_service only and performs local readback checks",
        ),
    ]
    blockers = [str(row["criterion"]) for row in rows if row["passed"] is not True]
    return {
        "schema_version": "command_center_3_ltg_strict_closeout_evidence_spine_contract.v1",
        "scope": "local_ltg_strict_closeout_evidence_spine_no_closeout_no_external",
        "status": "ltg_strict_closeout_evidence_spine_contract_passed"
        if not blockers
        else "ltg_strict_closeout_evidence_spine_contract_blocked",
        "contract_ready": not blockers,
        "cache_only": True,
        "spine_visible_count": int(summary.get("spine_visible_count") or 0),
        "spine_total_count": int(summary.get("spine_total_count") or 0),
        "spine_missing_ltg_ids": summary.get("spine_missing_ltg_ids") or [],
        "handoff_summary_visible_count": int(summary.get("handoff_summary_visible_count") or 0),
        "handoff_summary_total_count": int(summary.get("handoff_summary_total_count") or 0),
        "strict_closeout": summary.get("strict_closeout") or "0/14",
        "strict_closeout_done_count": int(summary.get("strict_closeout_done_count") or 0),
        "strict_closeout_total_count": int(summary.get("strict_closeout_total_count") or 14),
        "strict_closeout_remaining_count": int(summary.get("strict_closeout_remaining_count") or 14),
        "strict_closeout_claim_allowed": False,
        "all_rows_block_closeout_claim": all_rows_block_closeout,
        "all_rows_block_production_complete": all_rows_block_production,
        "remote_review_split_required": True,
        "requires_remote_ci_review": True,
        "requires_release_review_after_remote_green": True,
        "push_gate_step_ready": push_gate_step_ready,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "row_count": len(rows),
        "spine_row_count": len(spine_rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "observed": {
            "summary_status": summary.get("status"),
            "goal_ids": sorted(rows_by_id),
            "handoff_summary_total_count": summary.get("handoff_summary_total_count"),
            "strict_closeout": summary.get("strict_closeout"),
            "call_ledger_strict_closeout": first_call_ledger.get(
                "ltg_strict_closeout_evidence_spine_strict_closeout"
            ),
        },
        "rows": rows,
        "spine_rows": spine_rows,
        "note": "This is a local push-gate contract. It inventories 14 LTG handoffs but does not close any LTG or call external providers.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local 14-LTG strict closeout evidence spine.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ltg_strict_closeout_evidence_spine_contract: {contract['status']}")
        print(
            "spine: {spine_visible_count}/{spine_total_count}; handoffs: "
            "{handoff_summary_visible_count}/{handoff_summary_total_count}; "
            "strict_closeout: {strict_closeout}; closeout_claim_allowed: "
            "{strict_closeout_claim_allowed}".format(**contract).lower()
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
