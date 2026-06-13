#!/usr/bin/env python3
"""Validate the local LTG-02 Tushare acceptance contract.

This script is a push-gate guard, not a provider acceptance run. It imports
only local task contract helpers and fails on unsafe regressions such as
matrix-only rows being promoted to verified, provider-backed acceptance being
claimed from local QA contracts, or lost no-trade/no-action boundaries.
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

from server.services import task_service, tushare_task_service  # noqa: E402


CONTRACT_KEYS = [
    "api_acceptance_audit",
    "failure_mode_qa_contract",
    "request_parameter_qa_contract",
    "provider_target_sample_plan_contract",
    "provider_acceptance_readiness_audit",
    "provider_acceptance_promotion_audit",
]


def _row(criterion: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "evidence": evidence,
    }


def _flag_false(contract: dict[str, Any], *keys: str) -> bool:
    return all(contract.get(key) is False for key in keys)


def _catalog_by_type(task_type: str) -> dict[str, Any]:
    for row in task_service.TASK_CATALOG:
        if row.get("task_type") == task_type:
            return dict(row)
    return {}


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def build_contract() -> dict[str, Any]:
    selected_apis: list[str] = []
    call_ledger: list[dict[str, Any]] = []
    validation_rows = tushare_task_service._api_validation_rows(selected_apis, call_ledger)
    validation_target_rows = tushare_task_service._validation_target_rows(validation_rows)
    acceptance_audit = tushare_task_service._api_acceptance_audit(validation_rows, call_ledger)
    failure_mode_qa = tushare_task_service._failure_mode_qa_contract(validation_rows, call_ledger)
    request_parameter_qa = tushare_task_service._request_parameter_qa_contract(selected_apis, {})
    target_sample_plan = tushare_task_service._provider_target_sample_plan_contract(
        selected_apis=selected_apis,
        payload={},
        api_validation_rows=validation_rows,
    )
    provider_readiness = tushare_task_service._provider_acceptance_readiness_audit(
        api_validation_rows=validation_rows,
        validation_target_rows=validation_target_rows,
        api_acceptance_audit=acceptance_audit,
    )
    provider_promotion = tushare_task_service._provider_acceptance_promotion_audit(
        api_validation_rows=validation_rows,
        validation_target_rows=validation_target_rows,
        api_acceptance_audit=acceptance_audit,
        provider_target_sample_plan_contract=target_sample_plan,
        provider_acceptance_readiness_audit=provider_readiness,
        call_ledger=call_ledger,
    )

    refresh_catalog = _catalog_by_type("refresh_tushare_facts")
    factor_refresh_catalog = _catalog_by_type("refresh_factor_data")
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/tushare_acceptance_contract.py")

    api_count = len(tushare_task_service.REFRESH_API_SPECS)
    core_apis = list(tushare_task_service.CORE_REFRESH_APIS)
    calendar_apis = list(tushare_task_service.CALENDAR_REFRESH_APIS)
    extended_apis = list(tushare_task_service.EXTENDED_REFRESH_APIS)
    parquet_apis = list(tushare_task_service.PARQUET_DATASETS.keys())
    matrix_only_rows = [row for row in validation_rows if row.get("validation_scope") == "capability_matrix_only"]
    target_matrix_only_rows = [row for row in validation_target_rows if row.get("readiness") == "matrix_only"]
    readiness_criteria = {row.get("criterion") for row in provider_readiness.get("rows", [])}

    default_selection = tushare_task_service._selected_apis({}, tushare_task_service.CORE_REFRESH_APIS)
    calendar_selection = tushare_task_service._selected_apis(
        {"include_calendar": True},
        tushare_task_service.CORE_REFRESH_APIS,
    )
    extended_selection = tushare_task_service._selected_apis(
        {"include_extended": True},
        tushare_task_service.CORE_REFRESH_APIS,
    )

    rows = [
        _row(
            "post_task_catalog_button_gate",
            refresh_catalog.get("route") == "POST /api/tasks/refresh-tushare-facts"
            and refresh_catalog.get("button_gated") is True
            and refresh_catalog.get("cache_get_external_calls") is False
            and refresh_catalog.get("default_core_apis") == core_apis
            and refresh_catalog.get("calendar_apis") == calendar_apis
            and refresh_catalog.get("optional_extended_apis") == extended_apis
            and refresh_catalog.get("parquet_enabled_apis") == parquet_apis
            and refresh_catalog.get("call_ledger_required") is True
            and refresh_catalog.get("full_interface_acceptance_done") is False,
            "Tushare refresh must remain a button-gated POST task with core defaults, optional calendar/extended APIs, and no GET cache external call.",
        ),
        _row(
            "factor_refresh_delegate_is_conservative",
            factor_refresh_catalog.get("route") == "POST /api/factor-quant/refresh-data"
            and factor_refresh_catalog.get("button_gated") is True
            and factor_refresh_catalog.get("cache_get_external_calls") is False
            and factor_refresh_catalog.get("api_acceptance_audit_contract")
            and factor_refresh_catalog.get("provider_target_sample_plan_is_provider_acceptance") is False
            and factor_refresh_catalog.get("request_parameter_qa_is_provider_acceptance") is False
            and factor_refresh_catalog.get("failure_mode_qa_is_provider_acceptance") is False,
            "Delegated factor refresh must inherit Tushare task contracts and cannot promote local QA to provider acceptance.",
        ),
        _row(
            "api_declarations_complete",
            api_count == len(core_apis) + len(calendar_apis) + len(extended_apis)
            and api_count >= 20
            and set(parquet_apis) == set(core_apis + calendar_apis)
            and "trade_cal" in calendar_apis
            and "fina_indicator" in extended_apis,
            "Declared Tushare APIs must keep core, trade_cal, and extended groups explicit while Parquet remains limited to approved datasets.",
        ),
        _row(
            "selection_policy_conservative",
            default_selection == core_apis
            and calendar_selection == core_apis + calendar_apis
            and set(extended_selection) == set(core_apis + calendar_apis + extended_apis),
            "Default selection is core only; trade_cal and extended APIs require explicit payload flags or API selection.",
        ),
        _row(
            "matrix_only_rows_not_verified",
            len(matrix_only_rows) == api_count
            and acceptance_audit.get("matrix_only_api_count") == api_count
            and acceptance_audit.get("matrix_only_not_verified_count") == api_count
            and acceptance_audit.get("does_not_claim_unselected_apis_verified") is True
            and all(row.get("validation_status") == "not_requested" for row in matrix_only_rows),
            "Unselected APIs must stay capability matrix rows and must not be marked verified.",
        ),
        _row(
            "api_acceptance_audit_is_semantic_only",
            acceptance_audit.get("schema_version") == "tushare_api_acceptance_audit.v1"
            and acceptance_audit.get("scope") == "local_call_ledger_semantic_audit_not_provider_call"
            and acceptance_audit.get("status") == "acceptance_audit_passed"
            and acceptance_audit.get("full_interface_acceptance_done") is False
            and acceptance_audit.get("provider_validation_done_in_this_task") is False
            and acceptance_audit.get("audit_calls_tushare") is False
            and _flag_false(acceptance_audit, "cache_get_external_calls", "audit_external_calls_triggered", "deepseek_called", "github_called")
            and acceptance_audit.get("does_not_execute_trades") is True
            and acceptance_audit.get("does_not_modify_strategy_action") is True,
            "Acceptance audit validates local call-ledger semantics only; it must not imply provider-backed coverage.",
        ),
        _row(
            "failure_mode_qa_is_local_pending",
            failure_mode_qa.get("schema_version") == "tushare_failure_mode_qa_contract.v1"
            and failure_mode_qa.get("status") == "failure_mode_qa_ready_provider_acceptance_pending"
            and failure_mode_qa.get("provider_backed_acceptance_done") is False
            and failure_mode_qa.get("production_tushare_pipeline_complete") is False
            and failure_mode_qa.get("matrix_only_not_requested_distinguishable") is True
            and _flag_false(failure_mode_qa, "cache_get_external_calls", "qa_external_calls_triggered", "tushare_called_by_qa", "deepseek_called", "github_called")
            and failure_mode_qa.get("does_not_execute_trades") is True
            and failure_mode_qa.get("does_not_modify_strategy_action") is True,
            "Failure-mode QA classifies visible ledger states only and keeps provider acceptance pending.",
        ),
        _row(
            "request_parameter_qa_is_local_pending",
            request_parameter_qa.get("schema_version") == "tushare_request_parameter_qa_contract.v1"
            and request_parameter_qa.get("status") == "request_parameter_qa_ready_provider_acceptance_pending"
            and request_parameter_qa.get("provider_backed_acceptance_done") is False
            and request_parameter_qa.get("production_tushare_pipeline_complete") is False
            and request_parameter_qa.get("matrix_only_api_count") == api_count
            and _flag_false(request_parameter_qa, "cache_get_external_calls", "qa_external_calls_triggered", "tushare_called_by_qa", "deepseek_called", "github_called")
            and request_parameter_qa.get("does_not_execute_trades") is True
            and request_parameter_qa.get("does_not_modify_strategy_action") is True,
            "Request-parameter QA checks safe local parameters and matrix boundaries without provider calls.",
        ),
        _row(
            "target_sample_plan_is_plan_only",
            target_sample_plan.get("schema_version") == "tushare_provider_target_sample_plan_contract.v1"
            and target_sample_plan.get("status") == "local_plan_ready_provider_execution_pending"
            and target_sample_plan.get("ready_to_execute_target_count") == 0
            and target_sample_plan.get("pending_or_blocked_target_count") == target_sample_plan.get("target_count")
            and target_sample_plan.get("provider_backed_acceptance_done") is False
            and target_sample_plan.get("production_tushare_pipeline_complete") is False
            and _flag_false(target_sample_plan, "cache_get_external_calls", "plan_external_calls_triggered", "tushare_called_by_plan", "deepseek_called", "github_called")
            and target_sample_plan.get("does_not_execute_trades") is True
            and target_sample_plan.get("does_not_modify_strategy_action") is True,
            "Target sample plan declares future real-provider samples only; it is not provider-backed acceptance.",
        ),
        _row(
            "provider_readiness_stays_pending",
            provider_readiness.get("schema_version") == "tushare_provider_acceptance_readiness_audit.v1"
            and provider_readiness.get("status") == "provider_acceptance_pending"
            and provider_readiness.get("provider_backed_acceptance_done") is False
            and provider_readiness.get("production_tushare_pipeline_complete") is False
            and provider_readiness.get("full_interface_acceptance_done") is False
            and int(provider_readiness.get("production_blocker_count") or 0) > 0
            and "provider_backed_acceptance_evidence" in readiness_criteria
            and _flag_false(provider_readiness, "cache_get_external_calls", "audit_external_calls_triggered", "deepseek_called", "github_called")
            and provider_readiness.get("does_not_execute_trades") is True
            and provider_readiness.get("does_not_modify_strategy_action") is True,
            "Provider readiness must remain pending until explicit real-provider full-interface samples are proven.",
        ),
        _row(
            "provider_promotion_audit_stays_local_pending",
            provider_promotion.get("schema_version") == "tushare_provider_acceptance_promotion_audit.v1"
            and provider_promotion.get("scope") == "local_call_ledger_promotion_audit_no_provider_execution"
            and provider_promotion.get("status") == "provider_acceptance_promotion_pending"
            and provider_promotion.get("promotion_ready") is False
            and provider_promotion.get("provider_backed_acceptance_done") is False
            and provider_promotion.get("production_tushare_pipeline_complete") is False
            and int(provider_promotion.get("blocking_criterion_count") or 0) > 0
            and _flag_false(
                provider_promotion,
                "cache_get_external_calls",
                "audit_external_calls_triggered",
                "tushare_called_by_audit",
                "deepseek_called",
                "github_called",
            )
            and provider_promotion.get("does_not_execute_trades") is True
            and provider_promotion.get("does_not_modify_strategy_action") is True,
            "Provider promotion audit must stay local/read-only and cannot promote matrix/local QA into provider-backed acceptance.",
        ),
        _row(
            "target_groups_matrix_only",
            len(target_matrix_only_rows) == len(tushare_task_service.VALIDATION_TARGET_GROUPS)
            and all(row.get("does_not_claim_unselected_apis_verified") is True for row in target_matrix_only_rows)
            and all(row.get("button_gated_external_calls_only") is True for row in target_matrix_only_rows),
            "Validation target groups must show matrix-only status until selected APIs produce ledger evidence.",
        ),
        _row(
            "push_gate_runs_contract_before_static_qa",
            "scripts/tushare_acceptance_contract.py" in push_gate_script
            and "Tushare acceptance contract" in push_gate_script
            and "tushare_acceptance_contract: passed_local_contract_provider_execution_pending" in push_gate_script
            and push_gate_script.find('run_step "Data Health freshness contract"') < push_gate_script.find('run_step "Tushare acceptance contract"')
            and push_gate_script.find('run_step "Tushare acceptance contract"') < push_gate_script.find('run_step "Motion viewport QA contract"'),
            "Push gate must run the LTG-02 local contract after Data Health and before motion/static QA.",
        ),
        _row(
            "script_is_local_no_provider_execution",
            "command_center_3_tushare_acceptance_contract.v1" in this_script
            and "local_matrix_and_readiness_contract_no_provider_execution" in this_script
            and "provider_backed_acceptance_done" in this_script
            and "production_tushare_pipeline_complete" in this_script
            and "does_not_execute_trades" in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script,
            "The push-gate contract script must stay local/static and must not import provider clients.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_tushare_acceptance_contract.v1",
        "status": "tushare_acceptance_contract_passed" if not blockers else "tushare_acceptance_contract_blocked",
        "scope": "local_matrix_and_readiness_contract_no_provider_execution",
        "ltg": "LTG-02/LTG-11",
        "contract_ready": not blockers,
        "provider_backed_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "full_interface_acceptance_done": False,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "api_count": api_count,
        "core_api_count": len(core_apis),
        "calendar_api_count": len(calendar_apis),
        "extended_api_count": len(extended_apis),
        "parquet_enabled_api_count": len(parquet_apis),
        "matrix_only_api_count": len(matrix_only_rows),
        "target_group_count": len(validation_target_rows),
        "matrix_only_target_count": len(target_matrix_only_rows),
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "contract_keys": CONTRACT_KEYS,
        "rows": rows,
        "observed": {
            "refresh_task_route": refresh_catalog.get("route"),
            "default_core_apis": core_apis,
            "calendar_apis": calendar_apis,
            "extended_api_count": len(extended_apis),
            "parquet_enabled_apis": parquet_apis,
            "provider_readiness_status": provider_readiness.get("status"),
            "provider_readiness_blocker_count": provider_readiness.get("production_blocker_count"),
            "provider_promotion_status": provider_promotion.get("status"),
            "provider_promotion_blocker_count": provider_promotion.get("blocking_criterion_count"),
            "target_sample_plan_ready_count": target_sample_plan.get("ready_to_execute_target_count"),
            "target_sample_plan_pending_count": target_sample_plan.get("pending_or_blocked_target_count"),
        },
        "note": "This is a local push-gate contract. Real Tushare samples remain pending until a future explicit POST task/provider acceptance run.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-02 Tushare acceptance contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"tushare_acceptance_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "provider_backed_acceptance_done: false; production_tushare_pipeline_complete: false".format(
                **contract
            )
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
