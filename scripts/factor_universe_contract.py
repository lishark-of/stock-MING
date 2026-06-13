#!/usr/bin/env python3
"""Validate the local LTG-04 Factor universe research contract.

This push-gate guard checks only local read-plan, task-catalog, and frontend
source contracts. It prevents watchlist/custom/full-pool readiness metadata
from being mistaken for worker-backed batch research, cross-sectional
rank/zscore, neutralization, provider-backed validation, or trade advice.
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
from server.services import factor_service, task_service  # noqa: E402


REQUIRED_UNIVERSE_MODES = {"current_target", "watchlist", "custom_pool", "full_pool"}
REQUIRED_PLAN_DATASETS = {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal"}
PRODUCTION_PENDING_CRITERIA = {
    "worker_batch_execution_pending",
    "cross_sectional_rank_zscore_pending",
    "neutralization_pending",
    "full_pool_validation_pending",
}


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


def _flag_false(contract: dict[str, Any], *keys: str) -> bool:
    return all(contract.get(key) is False for key in keys)


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def build_contract() -> dict[str, Any]:
    now = "2026-06-09T11:09:00"
    payload = {"universe_mode": "full_pool", "universe": ["002008.SZ", "300750.SZ", "600519.SH"]}
    hub = factor_research.build_factor_quant_hub_packet(
        mode="cache_only",
        universe={"type": "current_target", "items": ["002008.SZ"], "size": 1},
        now=now,
    )
    base_contract = _dict(hub.get("universe_research_contract"))
    mode_rows = _list(hub.get("universe_research_mode_rows"))
    read_plan = factor_service._build_factor_universe_research_read_plan(payload, now)
    read_rows = _list(read_plan.get("storage_query_rows"))
    rank_zscore_dry_run = factor_service._factor_universe_local_rank_zscore_dry_run(now)

    plan_contract = dict(base_contract)
    plan_contract.update(
        {
            "storage_query_contract_consumed": True,
            "worker_task_consumption_plan_ready": True,
            "requested_universe_mode": read_plan.get("requested_universe_mode"),
            "storage_query_contract_count": read_plan.get("storage_query_contract_count"),
            "large_universe_pipeline_done": False,
            "full_pool_validation_done": False,
            "watchlist_pipeline_done": False,
            "custom_pool_pipeline_done": False,
            "cross_sectional_rank_zscore_done": False,
            "full_sample_neutralization_done": False,
            "factor_combination_research_done": False,
            "page_render_starts_full_pool": False,
            "frontend_computes_rank_zscore": False,
            "partial_pool_is_full_market_proof": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    )
    readiness = factor_research.build_factor_universe_execution_readiness_audit(
        contract=plan_contract,
        mode_rows=mode_rows,
        task_plan=read_plan,
    )
    readiness_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(readiness.get("rows"))
        if isinstance(row, dict)
    }
    task_catalog = {
        str(row.get("task_type") or ""): row
        for row in _list(task_service.build_task_catalog().get("tasks"))
        if isinstance(row, dict)
    }
    universe_task = _dict(task_catalog.get("run_factor_universe_research_plan"))
    light_task = _dict(task_catalog.get("run_factor_light"))
    factor_page = _read_script("desktop/src/routes/FactorQuantHub.tsx")
    api_client = _read_script("desktop/src/api/client.ts")
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/factor_universe_contract.py")

    declared_modes = {str(row.get("universe_mode") or "") for row in mode_rows if isinstance(row, dict)}
    plan_datasets = {str(row.get("dataset") or "") for row in read_rows if isinstance(row, dict)}
    rows = [
        _row(
            "universe_modes_are_declared_not_executed",
            REQUIRED_UNIVERSE_MODES <= declared_modes
            and base_contract.get("scope") == "local_contract_not_full_market_pipeline"
            and base_contract.get("implemented_now") == ["current_target"]
            and set(base_contract.get("future_task_modes") or []) == {"watchlist", "custom_pool", "full_pool"}
            and base_contract.get("large_universe_pipeline_done") is False
            and base_contract.get("full_pool_validation_done") is False
            and base_contract.get("cross_sectional_rank_zscore_done") is False
            and base_contract.get("full_sample_neutralization_done") is False,
            "Factor universe modes must be visible, but only current_target light mode is implemented today.",
        ),
        _row(
            "read_plan_consumes_storage_contracts_only",
            read_plan.get("schema_version") == "factor_universe_research_read_plan.v1"
            and read_plan.get("status") == "read_plan_ready"
            and read_plan.get("requested_universe_mode") == "full_pool"
            and plan_datasets == REQUIRED_PLAN_DATASETS
            and read_plan.get("worker_task_consumption_plan_ready") is True
            and read_plan.get("metrics_computed") is False
            and read_plan.get("large_universe_pipeline_done") is False
            and read_plan.get("full_pool_validation_done") is False
            and read_plan.get("cross_sectional_rank_zscore_done") is False
            and read_plan.get("neutralization_done") is False
            and read_plan.get("cache_only_storage_contracts") is True
            and read_plan.get("post_task_required") is True
            and _flag_false(read_plan, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and read_plan.get("does_not_execute_trades") is True
            and read_plan.get("does_not_modify_strategy_action") is True,
            "The universe read plan may consume local storage query contracts only; it must not compute metrics or run full-pool research.",
        ),
        _row(
            "storage_read_rows_do_not_expose_metric_samples",
            plan_datasets == REQUIRED_PLAN_DATASETS
            and all(
                isinstance(row, dict)
                and row.get("query_result_contract_schema_version") == "duckdb_query_result_contract.v1"
                and row.get("row_payload_exposed_to_factor_research") is False
                and row.get("metrics_computed_from_storage_query") is False
                and row.get("full_pool_validation_done") is False
                and row.get("large_universe_pipeline_done") is False
                and row.get("cache_get_writes_files") is False
                and row.get("writes_parquet_on_get") is False
                and _flag_false(row, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                for row in read_rows
            ),
            "Storage query rows must remain metadata contracts and must not become metric samples, provider refreshes, writes, or action inputs.",
        ),
        _row(
            "execution_readiness_keeps_production_blockers_visible",
            readiness.get("schema_version") == "factor_universe_execution_readiness_audit.v1"
            and readiness.get("status") == "read_plan_ready_execution_pending"
            and readiness.get("read_plan_ready") is True
            and readiness.get("storage_query_contract_consumed") is True
            and readiness.get("worker_task_consumption_plan_ready") is True
            and readiness.get("large_universe_pipeline_done") is False
            and readiness.get("full_pool_validation_done") is False
            and readiness.get("watchlist_pipeline_done") is False
            and readiness.get("custom_pool_pipeline_done") is False
            and readiness.get("cross_sectional_rank_zscore_done") is False
            and readiness.get("neutralization_done") is False
            and readiness.get("factor_combination_research_done") is False
            and readiness.get("production_factor_universe_complete") is False
            and int(readiness.get("production_blocker_count") or 0) >= len(PRODUCTION_PENDING_CRITERIA)
            and all(_dict(readiness_rows.get(key)).get("status") == "blocked" for key in PRODUCTION_PENDING_CRITERIA),
            "Readiness may be local-ready, but worker batch, rank/zscore, neutralization, and full-pool validation must remain production blockers.",
        ),
        _row(
            "local_rank_zscore_dry_run_is_research_only",
            rank_zscore_dry_run.get("schema_version") == "factor_universe_local_rank_zscore_dry_run.v1"
            and rank_zscore_dry_run.get("scope") == "local_factor_values_rank_zscore_dry_run_not_full_pool_validation"
            and rank_zscore_dry_run.get("metrics_are_research_only") is True
            and rank_zscore_dry_run.get("cross_sectional_rank_zscore_done") is False
            and rank_zscore_dry_run.get("neutralization_done") is False
            and rank_zscore_dry_run.get("large_universe_pipeline_done") is False
            and rank_zscore_dry_run.get("full_pool_validation_done") is False
            and rank_zscore_dry_run.get("production_factor_universe_complete") is False
            and rank_zscore_dry_run.get("page_render_starts_full_pool") is False
            and rank_zscore_dry_run.get("frontend_computes_rank_zscore") is False
            and rank_zscore_dry_run.get("partial_pool_is_full_market_proof") is False
            and rank_zscore_dry_run.get("writes_parquet_on_get") is False
            and rank_zscore_dry_run.get("auto_refresh_on_get") is False
            and _flag_false(rank_zscore_dry_run, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and rank_zscore_dry_run.get("does_not_execute_trades") is True
            and rank_zscore_dry_run.get("does_not_modify_strategy_action") is True,
            "Local rank/zscore dry-run may only audit/preview local factor_values cross-sections and must not promote production universe flags.",
        ),
        _row(
            "task_catalog_is_button_gated_read_plan_only",
            universe_task.get("route") == "POST /api/factor-quant/universe-research-plan"
            and universe_task.get("button_gated") is True
            and universe_task.get("current_backend") == "local_storage_query_read_plan_pipeline"
            and universe_task.get("external_call_policy") == "local_storage_query_contract_only_no_external_call"
            and universe_task.get("possible_external_sources") == []
            and universe_task.get("storage_query_contract_consumed") is True
            and universe_task.get("worker_task_consumption_plan_ready") is True
            and universe_task.get("large_universe_pipeline_done") is False
            and universe_task.get("full_pool_validation_done") is False
            and universe_task.get("page_render_starts_full_pool") is False
            and universe_task.get("frontend_computes_rank_zscore") is False
            and universe_task.get("partial_pool_is_full_market_proof") is False
            and universe_task.get("does_not_execute_trades") is True
            and universe_task.get("does_not_modify_strategy_action") is True
            and light_task.get("universe_modes") == ["current_target"]
            and light_task.get("future_universe_modes") == ["watchlist", "custom_pool", "full_pool"],
            "Task catalog must keep factor universe work button-gated and read-plan-only while light mode remains current_target-only.",
        ),
        _row(
            "frontend_displays_plan_and_does_not_compute_universe",
            "export function postTask" in api_client
            and "fetch(`${API_BASE}${path}`" in api_client
            and "import { getFactorQuantCache, postTask" in factor_page
            and "launchTask(\"/api/factor-quant/universe-research-plan\"" in factor_page
            and "universe_execution_readiness_audit" in factor_page
            and "universe_local_rank_zscore_dry_run" in factor_page
            and "Factor Universe 本地 Rank/Zscore Dry-run" in factor_page
            and "前端不计算 rank/zscore" in factor_page
            and "universe_research_task_plan" in factor_page
            and "frontend_computes_rank_zscore" in factor_page
            and "page_render_starts_full_pool" in factor_page
            and "partial_pool_is_full_market_proof" in factor_page
            and "不代表全市场研究生产完成" in factor_page
            and "fetch(" not in factor_page
            and "axios" not in factor_page
            and ("tushare" + "_adapter") not in factor_page
            and ("deepseek" + "_adapter") not in factor_page
            and "pro_api" not in factor_page,
            "React must call the FastAPI client for the button task and only display readiness/read-plan boundaries.",
        ),
        _row(
            "research_outputs_do_not_enter_action_surfaces",
            readiness.get("does_not_execute_trades") is True
            and readiness.get("does_not_modify_strategy_action") is True
            and readiness.get("partial_pool_is_full_market_proof") is False
            and readiness.get("page_render_starts_full_pool") is False
            and readiness.get("frontend_computes_rank_zscore") is False
            and _flag_false(readiness, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Universe research readiness must stay outside trades, strategy action, page-render full-pool work, and frontend rank/zscore.",
        ),
        _row(
            "push_gate_runs_factor_universe_after_factor_test_lab",
            "scripts/factor_universe_contract.py" in push_gate_script
            and "Factor universe contract" in push_gate_script
            and "factor_universe_contract: passed_local_contract_read_plan_execution_pending" in push_gate_script
            and push_gate_script.find('run_step "Factor Test Lab contract"') < push_gate_script.find('run_step "Factor universe contract"')
            and push_gate_script.find('run_step "Factor universe contract"') < push_gate_script.find('run_step "DeepSeek governance contract"'),
            "Push gate must run the LTG-04 local contract after Factor Test Lab and before DeepSeek governance.",
        ),
        _row(
            "script_is_local_no_batch_or_provider_execution",
            "command_center_3_factor_universe_contract.v1" in this_script
            and "local_factor_universe_contract_no_batch_or_provider_execution" in this_script
            and "production_factor_universe_complete" in this_script
            and "full_pool_validation_done" in this_script
            and "cross_sectional_rank_zscore_done" in this_script
            and "local_rank_zscore_dry_run_is_research_only" in this_script
            and "does_not_execute_trades" in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script
            and ("deepseek" + "_adapter") not in this_script,
            "The push-gate contract script must stay local and must not import provider, model, GitHub, or browser execution clients.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_factor_universe_contract.v1",
        "status": "factor_universe_contract_passed" if not blockers else "factor_universe_contract_blocked",
        "scope": "local_factor_universe_contract_no_batch_or_provider_execution",
        "ltg": "LTG-04/LTG-11",
        "contract_ready": not blockers,
        "read_plan_ready": read_plan.get("status") == "read_plan_ready",
        "storage_query_contract_consumed": readiness.get("storage_query_contract_consumed") is True,
        "worker_task_consumption_plan_ready": readiness.get("worker_task_consumption_plan_ready") is True,
        "large_universe_pipeline_done": False,
        "watchlist_pipeline_done": False,
        "custom_pool_pipeline_done": False,
        "full_pool_validation_done": False,
        "cross_sectional_rank_zscore_done": False,
        "local_rank_zscore_dry_run_executed": bool(rank_zscore_dry_run.get("rank_zscore_dry_run_executed")),
        "neutralization_done": False,
        "factor_combination_research_done": False,
        "production_factor_universe_complete": False,
        "partial_pool_is_full_market_proof": False,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "frontend_computes_rank_zscore": False,
        "page_render_starts_full_pool": False,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "observed": {
            "declared_universe_modes": sorted(declared_modes),
            "read_plan_status": read_plan.get("status"),
            "requested_universe_mode": read_plan.get("requested_universe_mode"),
            "read_plan_dataset_count": read_plan.get("dataset_count"),
            "storage_query_contract_count": read_plan.get("storage_query_contract_count"),
            "rank_zscore_dry_run_status": rank_zscore_dry_run.get("status"),
            "rank_zscore_eligible_group_count": rank_zscore_dry_run.get("eligible_group_count"),
            "readiness_status": readiness.get("status"),
            "readiness_production_blocker_count": readiness.get("production_blocker_count"),
            "task_backend": universe_task.get("current_backend"),
        },
        "rows": rows,
        "note": "This is a local push-gate contract. Worker batch execution, rank/zscore, neutralization, provider-backed validation, and full-pool production research remain pending.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print full JSON contract")
    args = parser.parse_args()
    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"factor_universe_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "read_plan_ready: {read_plan_ready}; production_factor_universe_complete: false; "
            "full_pool_validation_done: false".format(**contract)
        )
        print(
            "external_calls_triggered: false; tushare_called: false; deepseek_called: false; "
            "github_called: false; does_not_execute_trades: true"
        )
    return 0 if contract["contract_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
