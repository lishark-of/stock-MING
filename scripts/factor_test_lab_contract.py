#!/usr/bin/env python3
"""Validate the local LTG-03 Factor Test Lab contract.

This push-gate guard runs only local research metric builders and service
contracts. It prevents light metrics, storage-query consumption, small-pool
readiness, and production QA checklists from being mistaken for provider-backed
or full-market Factor Test Lab production validation.
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

import command_center_factor_research as factor_research  # noqa: E402
from server.services import factor_service  # noqa: E402


REQUIRED_RESEARCH_STATES = {
    "research_pass",
    "watchlist",
    "disabled",
    "invalid",
    "not_enough_data",
}
REQUIRED_ACCEPTANCE_CRITERIA = {
    "core_ic_metrics_present",
    "group_return_present",
    "cost_model_present",
    "drawdown_present",
    "neutral_ic_present",
    "out_of_sample_decay_present",
    "bias_checks_passed",
}
PRODUCTION_PENDING_CRITERIA = {
    "provider_backed_small_pool_sample",
    "multi_horizon_forward_returns",
    "rolling_window_ic_icir",
    "out_of_sample_decay",
    "transaction_cost_assumptions",
    "neutralization_stability",
    "pit_lookahead_survivorship_controls",
}


def _row(criterion: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "evidence": evidence,
    }


def _flag_false(contract: dict[str, Any], *keys: str) -> bool:
    return all(contract.get(key) is False for key in keys)


def _sample_observations() -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for day_index, trade_date in enumerate(["20260601", "20260602", "20260603", "20260604"], start=1):
        for stock_index in range(1, 9):
            observations.append(
                {
                    "factor_key": "momentum_20d",
                    "ts_code": f"00000{stock_index}.SZ",
                    "trade_date": trade_date,
                    "factor_value": stock_index * 0.1 + day_index * 0.01,
                    "forward_return": stock_index * 0.006 + day_index * 0.0003,
                    "transaction_cost": 0.001,
                    "turnover": 0.18 + stock_index * 0.01,
                    "industry": "equipment" if stock_index % 2 else "semiconductor",
                    "market_cap": 100 + (stock_index % 4) * 30 + day_index * 5,
                    "pit_validated": True,
                    "lookahead_check": "passed",
                    "survivorship_check": "passed",
                    "forward_return_horizon": "1d",
                    "strategy_action": "buy",
                    "price": 99.0,
                }
            )
    return observations


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_contract() -> dict[str, Any]:
    now = "2026-06-09T11:09:00"
    research_packet = factor_research.compute_light_mode_factor_ic_metrics(
        observations=_sample_observations(),
        now=now,
    )
    rows_by_key = {
        str(row.get("factor_key") or ""): row
        for row in _list(research_packet.get("items"))
        if isinstance(row, dict)
    }
    primary_row = _dict(rows_by_key.get("momentum_20d"))
    small_pool = _dict(research_packet.get("small_pool_acceptance"))
    acceptance = _dict(research_packet.get("acceptance_contract"))
    acceptance_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(research_packet.get("small_pool_acceptance_rows"))
        if isinstance(row, dict)
    }
    state_rows = _list(research_packet.get("state_transition_rows"))
    state_names = {str(row.get("research_state") or "") for row in state_rows if isinstance(row, dict)}

    storage_query = factor_service._factor_test_storage_query_consumption(now)
    local_dataset_sample = factor_service._factor_test_local_dataset_sample_evidence(now)
    factor_tests = dict(research_packet)
    factor_tests["storage_query_consumption"] = storage_query
    factor_tests["local_dataset_sample_evidence"] = local_dataset_sample
    production_qa = factor_service._factor_test_production_validation_qa_contract(factor_tests, now)
    factor_tests["production_validation_qa_contract"] = production_qa
    provider_blocker_audit = factor_service._factor_test_provider_validation_blocker_audit(factor_tests, now)
    factor_tests["provider_validation_blocker_audit"] = provider_blocker_audit
    provider_sample_receipt = factor_service._factor_test_provider_sample_readiness_receipt(factor_tests, now)
    factor_tests["provider_sample_readiness_receipt"] = provider_sample_receipt
    provider_sample_activation = factor_service._factor_test_provider_sample_activation_receipt(factor_tests, now)
    production_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(production_qa.get("rows"))
        if isinstance(row, dict)
    }
    cache_packet = factor_service.read_factor_quant_cache()
    cache_factor_tests = _dict(cache_packet.get("factor_tests"))
    cache_local_dataset_sample = _dict(cache_factor_tests.get("local_dataset_sample_evidence"))
    cache_production_qa = _dict(cache_factor_tests.get("production_validation_qa_contract"))
    cache_provider_blocker_audit = _dict(cache_factor_tests.get("provider_validation_blocker_audit"))
    cache_provider_sample_receipt = _dict(cache_factor_tests.get("provider_sample_readiness_receipt"))
    cache_provider_sample_activation = _dict(cache_factor_tests.get("provider_sample_activation_receipt"))
    cache_call_ledger = _list(cache_packet.get("call_ledger"))
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/factor_test_lab_contract.py")

    rows = [
        _row(
            "local_light_metrics_readiness",
            research_packet.get("status") == "ready"
            and research_packet.get("computed_item_count") == 1
            and primary_row.get("result_status") == "research_pass"
            and primary_row.get("ic_mean") is not None
            and primary_row.get("rank_ic_mean") is not None
            and primary_row.get("icir") is not None
            and primary_row.get("top_bottom_group_return") is not None
            and primary_row.get("cost_adjusted_return") is not None
            and primary_row.get("max_drawdown") is not None
            and primary_row.get("industry_neutral_ic") is not None
            and primary_row.get("market_cap_neutral_ic") is not None,
            "Synthetic light observations must prove IC/Rank IC/ICIR, group return, cost, drawdown, neutral IC, split, and decay calculations locally.",
        ),
        _row(
            "small_pool_acceptance_is_local_only",
            small_pool.get("schema_version") == "factor_test_small_pool_acceptance.v1"
            and small_pool.get("status") == "local_small_pool_acceptance_ready"
            and small_pool.get("local_light_observation_acceptance_done") is True
            and small_pool.get("real_small_pool_validation_done") is False
            and small_pool.get("full_market_validation_done") is False
            and small_pool.get("storage_query_rows_used_as_metrics") is False
            and _flag_false(small_pool, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and all(_dict(acceptance_rows.get(key)).get("status") == "passed" for key in REQUIRED_ACCEPTANCE_CRITERIA),
            "Small-pool acceptance may pass for local light observations only; it must not become provider-backed or full-market proof.",
        ),
        _row(
            "research_states_stay_isolated",
            state_names == REQUIRED_RESEARCH_STATES
            and acceptance.get("all_result_states_are_research_only") is True
            and acceptance.get("research_pass_is_not_trade_signal") is True
            and acceptance.get("does_not_modify_strategy_action") is True
            and all(
                isinstance(row, dict)
                and row.get("governance_state") == "research_only"
                and row.get("allow_evidence_effects") is False
                and row.get("allow_strategy_trace") is False
                and row.get("allow_core_action") is False
                and row.get("allow_automatic_trade") is False
                and row.get("frontend_computes_trade_action") is False
                for row in state_rows
            ),
            "research_pass/watchlist/disabled/invalid/not_enough_data must remain research labels outside action, evidence, and frontend action computation.",
        ),
        _row(
            "input_action_fields_are_sanitized",
            "strategy_action" not in primary_row
            and "price" not in primary_row
            and primary_row.get("enters_strategy_action") is False
            and primary_row.get("enters_core_action") is False
            and primary_row.get("does_not_modify_strategy_action") is True,
            "Input action/price fields in observations must not leak into Factor Test Lab result rows.",
        ),
        _row(
            "storage_query_consumption_is_not_metric_source",
            storage_query.get("schema_version") == "factor_test_storage_query_consumption.v1"
            and storage_query.get("cache_only") is True
            and storage_query.get("query_result_contract_consumed") in {True, False}
            and storage_query.get("metrics_computed_from_storage_query") is False
            and storage_query.get("storage_query_enters_strategy_action") is False
            and storage_query.get("writes_parquet_on_get") is False
            and storage_query.get("auto_refresh_on_get") is False
            and _flag_false(storage_query, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and storage_query.get("does_not_execute_trades") is True
            and storage_query.get("does_not_modify_strategy_action") is True,
            "DuckDB/factor_values query consumption must remain local metadata and must not compute metrics, refresh providers, write files, or enter strategy action.",
        ),
        _row(
            "local_dataset_sample_evidence_is_not_validation",
            local_dataset_sample.get("schema_version") == "factor_test_local_dataset_sample_evidence.v1"
            and local_dataset_sample.get("scope") == "local_parquet_sample_sufficiency_audit_not_metric_validation"
            and local_dataset_sample.get("metrics_computed_from_local_dataset") is False
            and local_dataset_sample.get("storage_query_rows_used_as_metrics") is False
            and local_dataset_sample.get("real_small_pool_validation_done") is False
            and local_dataset_sample.get("provider_backed_small_pool_validation_done") is False
            and local_dataset_sample.get("full_market_validation_done") is False
            and local_dataset_sample.get("production_factor_test_validation_complete") is False
            and local_dataset_sample.get("writes_parquet_on_get") is False
            and local_dataset_sample.get("auto_refresh_on_get") is False
            and _flag_false(local_dataset_sample, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and local_dataset_sample.get("does_not_execute_trades") is True
            and local_dataset_sample.get("does_not_modify_strategy_action") is True,
            "Local Parquet sample evidence may count sufficiency only; it must not compute metrics or become provider-backed/full-market validation.",
        ),
        _row(
            "production_validation_qa_stays_pending",
            production_qa.get("schema_version") == "factor_test_production_validation_qa_contract.v1"
            and production_qa.get("status") == "production_validation_qa_contract_ready_provider_execution_pending"
            and production_qa.get("provider_backed_small_pool_validation_done") is False
            and production_qa.get("full_market_validation_done") is False
            and production_qa.get("production_factor_test_validation_complete") is False
            and int(production_qa.get("pending_criterion_count") or 0) >= len(PRODUCTION_PENDING_CRITERIA)
            and all(_dict(production_rows.get(key)).get("blocks_production_validation") is True for key in PRODUCTION_PENDING_CRITERIA)
            and _flag_false(production_qa, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and production_qa.get("does_not_execute_trades") is True
            and production_qa.get("does_not_modify_strategy_action") is True
            and production_qa.get("does_not_modify_core_action") is True
            and production_qa.get("does_not_enter_evidence_effects") is True
            and production_qa.get("does_not_enter_next_session_projection") is True,
            "Production QA is a local checklist; provider-backed small-pool, full-market, multi-horizon, rolling, cost, neutralization, and bias validation must remain pending.",
        ),
        _row(
            "provider_validation_blocker_audit_stays_pending",
            provider_blocker_audit.get("schema_version") == "factor_test_provider_validation_blocker_audit.v1"
            and provider_blocker_audit.get("scope") == "local_factor_test_provider_validation_blocker_audit_no_provider_execution"
            and provider_blocker_audit.get("status") == "provider_validation_blockers_visible"
            and provider_blocker_audit.get("provider_validation_ready") is False
            and provider_blocker_audit.get("provider_backed_small_pool_validation_done") is False
            and provider_blocker_audit.get("full_market_validation_done") is False
            and provider_blocker_audit.get("production_factor_test_validation_complete") is False
            and int(provider_blocker_audit.get("production_blocker_count") or 0) > 0
            and "provider_backed_small_pool_sample" in provider_blocker_audit.get("production_blockers", [])
            and "full_market_validation" in provider_blocker_audit.get("production_blockers", [])
            and provider_blocker_audit.get("metrics_computed_from_local_dataset") is False
            and provider_blocker_audit.get("storage_query_rows_used_as_metrics") is False
            and _flag_false(provider_blocker_audit, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and provider_blocker_audit.get("does_not_execute_trades") is True
            and provider_blocker_audit.get("does_not_modify_strategy_action") is True,
            "Provider validation blocker audit must centralize remaining real small-pool/full-market blockers without provider calls or metric promotion.",
        ),
        _row(
            "provider_sample_readiness_receipt_is_local",
            provider_sample_receipt.get("schema_version") == "factor_test_provider_sample_readiness_receipt.v1"
            and provider_sample_receipt.get("scope") == "local_factor_test_provider_sample_readiness_receipt_no_provider_execution"
            and provider_sample_receipt.get("local_receipt_ready") is True
            and provider_sample_receipt.get("provider_backed_small_pool_validation_done") is False
            and provider_sample_receipt.get("full_market_validation_done") is False
            and provider_sample_receipt.get("production_factor_test_validation_complete") is False
            and provider_sample_receipt.get("provider_refresh_called_by_receipt") is False
            and provider_sample_receipt.get("cache_get_external_calls") is False
            and provider_sample_receipt.get("receipt_external_calls_triggered") is False
            and provider_sample_receipt.get("tushare_called_by_receipt") is False
            and provider_sample_receipt.get("deepseek_called") is False
            and provider_sample_receipt.get("github_called") is False
            and provider_sample_receipt.get("does_not_execute_trades") is True
            and provider_sample_receipt.get("does_not_modify_strategy_action") is True
            and "GET /api/factor-quant/cache provider refresh" in provider_sample_receipt.get("not_allowed_next_steps", [])
            and "storage query rows as IC metrics" in provider_sample_receipt.get("not_allowed_next_steps", [])
            and "local light metrics as provider acceptance" in provider_sample_receipt.get("not_allowed_next_steps", [])
            and provider_sample_receipt.get("allowed_next_step")
            in {
                "complete_local_dataset_sample_and_forward_returns",
                "explicit_post_task_factor_test_provider_small_pool_acceptance",
                "review_prior_factor_test_provider_evidence",
            },
            "Provider sample readiness receipt may choose the next safe LTG-03 step, but it must stay local and cannot promote local metrics or QA rows.",
        ),
        _row(
            "provider_sample_activation_receipt_is_local_pending",
            provider_sample_activation.get("schema_version") == "factor_test_provider_sample_activation_receipt.v1"
            and provider_sample_activation.get("scope")
            == "local_factor_test_provider_sample_activation_receipt_no_provider_execution"
            and provider_sample_activation.get("local_activation_receipt_ready") is True
            and provider_sample_activation.get("provider_backed_small_pool_validation_done") is False
            and provider_sample_activation.get("production_factor_test_validation_complete") is False
            and provider_sample_activation.get("provider_task_created_by_receipt") is False
            and provider_sample_activation.get("provider_refresh_called_by_receipt") is False
            and provider_sample_activation.get("cache_get_external_calls") is False
            and provider_sample_activation.get("react_render_external_calls") is False
            and provider_sample_activation.get("receipt_external_calls_triggered") is False
            and provider_sample_activation.get("tushare_called_by_receipt") is False
            and provider_sample_activation.get("deepseek_called") is False
            and provider_sample_activation.get("github_called") is False
            and provider_sample_activation.get("does_not_execute_trades") is True
            and provider_sample_activation.get("does_not_modify_strategy_action") is True
            and "explicit provider-backed small-pool task execution" in provider_sample_activation.get("missing_evidence_items", [])
            and "safe provider call ledger rows for target pool" in provider_sample_activation.get("missing_evidence_items", [])
            and "activation receipt as production Factor Test completion"
            in provider_sample_activation.get("not_allowed_next_steps", [])
            and provider_sample_activation.get("allowed_next_step")
            in {
                "complete_local_dataset_sample_and_forward_returns",
                "explicit_post_task_factor_test_provider_small_pool_acceptance",
                "review_prior_factor_test_provider_evidence",
            },
            "Provider sample activation receipt must stay a local checklist before future provider-backed small-pool validation.",
        ),
        _row(
            "cache_get_factor_boundary",
            cache_packet.get("mode") == "light"
            and cache_production_qa.get("schema_version") == "factor_test_production_validation_qa_contract.v1"
            and cache_production_qa.get("production_factor_test_validation_complete") is False
            and cache_production_qa.get("provider_backed_small_pool_validation_done") is False
            and cache_production_qa.get("full_market_validation_done") is False
            and cache_provider_blocker_audit.get("schema_version") == "factor_test_provider_validation_blocker_audit.v1"
            and cache_provider_blocker_audit.get("provider_validation_ready") is False
            and cache_provider_blocker_audit.get("production_factor_test_validation_complete") is False
            and cache_provider_sample_receipt.get("schema_version") == "factor_test_provider_sample_readiness_receipt.v1"
            and cache_provider_sample_receipt.get("provider_backed_small_pool_validation_done") is False
            and cache_provider_sample_receipt.get("production_factor_test_validation_complete") is False
            and cache_provider_sample_activation.get("schema_version") == "factor_test_provider_sample_activation_receipt.v1"
            and cache_provider_sample_activation.get("production_factor_test_validation_complete") is False
            and cache_provider_sample_receipt.get("provider_refresh_called_by_receipt") is False
            and _flag_false(cache_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and cache_packet.get("does_not_execute_trades") is True
            and cache_packet.get("does_not_modify_strategy_action") is True
            and any(_dict(row).get("api") == "local_factor_test_production_validation_qa_contract" for row in cache_call_ledger),
            "GET factor cache must remain local/read-only and expose Factor Test Lab production QA as pending, not production complete.",
        ),
        _row(
            "cache_get_exposes_provider_sample_receipt_boundary",
            cache_provider_sample_receipt.get("schema_version") == "factor_test_provider_sample_readiness_receipt.v1"
            and cache_provider_sample_receipt.get("scope") == "local_factor_test_provider_sample_readiness_receipt_no_provider_execution"
            and cache_provider_sample_receipt.get("provider_backed_small_pool_validation_done") is False
            and cache_provider_sample_receipt.get("production_factor_test_validation_complete") is False
            and cache_provider_sample_receipt.get("receipt_external_calls_triggered") is False
            and cache_provider_sample_receipt.get("tushare_called_by_receipt") is False
            and cache_provider_sample_receipt.get("does_not_execute_trades") is True
            and any(_dict(row).get("api") == "local_factor_test_provider_sample_readiness_receipt" for row in cache_call_ledger),
            "GET factor cache must expose the provider small-pool readiness receipt as a local boundary with its own call ledger.",
        ),
        _row(
            "cache_get_exposes_provider_sample_activation_boundary",
            cache_provider_sample_activation.get("schema_version") == "factor_test_provider_sample_activation_receipt.v1"
            and cache_provider_sample_activation.get("scope")
            == "local_factor_test_provider_sample_activation_receipt_no_provider_execution"
            and cache_provider_sample_activation.get("provider_backed_small_pool_validation_done") is False
            and cache_provider_sample_activation.get("production_factor_test_validation_complete") is False
            and cache_provider_sample_activation.get("provider_task_created_by_receipt") is False
            and cache_provider_sample_activation.get("receipt_external_calls_triggered") is False
            and cache_provider_sample_activation.get("tushare_called_by_receipt") is False
            and cache_provider_sample_activation.get("does_not_execute_trades") is True
            and any(_dict(row).get("api") == "local_factor_test_provider_sample_activation_receipt" for row in cache_call_ledger),
            "GET factor cache must expose the provider small-pool activation receipt as a local boundary with its own call ledger.",
        ),
        _row(
            "cache_get_exposes_local_dataset_sample_boundary",
            cache_local_dataset_sample.get("schema_version") == "factor_test_local_dataset_sample_evidence.v1"
            and cache_local_dataset_sample.get("metrics_computed_from_local_dataset") is False
            and cache_local_dataset_sample.get("provider_backed_small_pool_validation_done") is False
            and cache_local_dataset_sample.get("production_factor_test_validation_complete") is False
            and _flag_false(cache_local_dataset_sample, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and any(_dict(row).get("api") == "local_factor_test_local_dataset_sample_evidence" for row in cache_call_ledger),
            "GET factor cache must expose local dataset sample sufficiency as a boundary audit with its own local call ledger.",
        ),
        _row(
            "push_gate_runs_contract_after_tushare",
            "scripts/factor_test_lab_contract.py" in push_gate_script
            and "Factor Test Lab contract" in push_gate_script
            and "factor_test_lab_contract: passed_local_contract_provider_execution_pending" in push_gate_script
            and push_gate_script.find('run_step "Tushare acceptance contract"') < push_gate_script.find('run_step "Factor Test Lab contract"')
            and push_gate_script.find('run_step "Factor Test Lab contract"') < push_gate_script.find('run_step "Motion viewport QA contract"'),
            "Push gate must run the LTG-03 local contract after Tushare acceptance and before motion/static QA.",
        ),
        _row(
            "script_is_local_no_provider_execution",
            "command_center_3_factor_test_lab_contract.v1" in this_script
            and "local_factor_test_lab_contract_no_provider_execution" in this_script
            and "provider_backed_small_pool_validation_done" in this_script
            and "provider_validation_blocker_audit_stays_pending" in this_script
            and "provider_sample_readiness_receipt_is_local" in this_script
            and "provider_sample_activation_receipt_is_local_pending" in this_script
            and "local_dataset_sample_evidence_is_not_validation" in this_script
            and "production_factor_test_validation_complete" in this_script
            and "does_not_execute_trades" in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script,
            "The push-gate contract script must stay local and must not import provider clients.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_factor_test_lab_contract.v1",
        "status": "factor_test_lab_contract_passed" if not blockers else "factor_test_lab_contract_blocked",
        "scope": "local_factor_test_lab_contract_no_provider_execution",
        "ltg": "LTG-03/LTG-11",
        "contract_ready": not blockers,
        "provider_backed_small_pool_validation_done": False,
        "full_market_validation_done": False,
        "production_factor_test_validation_complete": False,
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
        "observed": {
            "research_status": research_packet.get("status"),
            "computed_item_count": research_packet.get("computed_item_count"),
            "primary_factor_status": primary_row.get("result_status"),
            "small_pool_status": small_pool.get("status"),
            "production_qa_status": production_qa.get("status"),
            "production_qa_pending_count": production_qa.get("pending_criterion_count"),
            "provider_blocker_status": provider_blocker_audit.get("status"),
            "provider_blocker_count": provider_blocker_audit.get("production_blocker_count"),
            "provider_sample_receipt_status": provider_sample_receipt.get("status"),
            "provider_sample_receipt_allowed_next_step": provider_sample_receipt.get("allowed_next_step"),
            "provider_sample_activation_status": provider_sample_activation.get("status"),
            "provider_sample_activation_allowed_next_step": provider_sample_activation.get("allowed_next_step"),
            "cache_production_qa_status": cache_production_qa.get("status"),
            "cache_provider_blocker_status": cache_provider_blocker_audit.get("status"),
            "cache_provider_sample_receipt_status": cache_provider_sample_receipt.get("status"),
            "cache_provider_sample_activation_status": cache_provider_sample_activation.get("status"),
            "storage_query_status": storage_query.get("status"),
            "local_dataset_sample_status": local_dataset_sample.get("status"),
            "cache_local_dataset_sample_status": cache_local_dataset_sample.get("status"),
            "cache_call_ledger_count": len(cache_call_ledger),
        },
        "rows": rows,
        "note": "This is a local push-gate contract. Real provider-backed small-pool and full-market Factor Test Lab validation remain pending.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-03 Factor Test Lab contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"factor_test_lab_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "provider_backed_small_pool_validation_done: false; "
            "production_factor_test_validation_complete: false".format(**contract)
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
