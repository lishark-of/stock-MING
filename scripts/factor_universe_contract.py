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
WORKER_STAGE_SCOPE_LABELS = {
    "storage_read_plan": "Storage read plan",
    "worker_batch_scope": "Worker batch scope",
    "cross_sectional_rank": "Cross-sectional rank",
    "zscore": "Z-score",
    "neutralization": "Neutralization",
    "factor_combination": "Factor combination",
    "result_summary": "Result summary",
    "promotion_review": "Promotion review",
}
REQUIRED_WORKER_BATCH_EXECUTION_PHASES = (
    "scope_ticket_review",
    "explicit_worker_task_creation",
    "worker_runtime_binding",
    "storage_read_execution",
    "cross_sectional_rank_execution",
    "zscore_execution",
    "neutralization_execution",
    "factor_combination_execution",
    "result_summary_persistence",
    "production_promotion_review",
)
REQUIRED_FACTOR_UNIVERSE_DURABLE_EVIDENCE_KEYS = tuple(
    factor_service.FACTOR_UNIVERSE_DURABLE_EVIDENCE_KEYS
)
LOCAL_FACTOR_UNIVERSE_DURABLE_SURFACE_KEYS = {
    "mode_contract_visible",
    "storage_read_plan_visible",
    "readiness_audit_visible",
    "readiness_receipt_visible",
    "activation_receipt_visible",
    "local_rank_zscore_dry_run_visible",
    "worker_batch_scope_ticket_visible",
    "worker_batch_execution_recipe_visible",
    "worker_batch_execution_request_visible",
    "no_render_worker_provider_trade_secret_boundary",
}
PRODUCTION_FACTOR_UNIVERSE_DURABLE_BLOCKER_KEYS = {
    "explicit_worker_task_required",
    "worker_runtime_binding_required",
    "storage_read_execution_required",
    "cross_sectional_rank_required",
    "zscore_required",
    "neutralization_required",
    "factor_combination_required",
    "result_summary_persistence_required",
    "full_pool_validation_required",
    "promotion_review_required",
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


def _worker_stage_scope_rows(required_stages: list[str], selected_stages: list[str]) -> list[dict[str, Any]]:
    selected = set(selected_stages)
    return [
        {
            "stage_key": stage_key,
            "stage_label": WORKER_STAGE_SCOPE_LABELS.get(stage_key, stage_key),
            "scope": "factor_universe_worker_batch_stage_scope_manifest",
            "current_status": "local_worker_batch_scope_ticket_only",
            "target_status": "worker_backed_execution_required",
            "selected_by_worker_dry_run_scope": stage_key in selected,
            "required_before_production": True,
            "worker_execution_implemented": False,
            "worker_batch_executed": False,
            "large_universe_pipeline_done": False,
            "cross_sectional_rank_zscore_done": False,
            "neutralization_done": False,
            "factor_combination_research_done": False,
            "full_pool_validation_done": False,
            "production_factor_universe_complete": False,
            "page_render_starts_full_pool": False,
            "frontend_computes_rank_zscore": False,
            "external_calls_triggered": False,
            "tushare_called_by_contract": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "required_real_evidence": [
                "explicit worker-backed task execution",
                "durable task log rows",
                "large-universe result rows",
                "promotion review before production completion",
            ],
        }
        for stage_key in required_stages
    ]


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
    worker_batch_payload = factor_service._factor_universe_worker_batch_dry_run_payload(
        {"approved_by_user": True, "universe_mode": "full_pool", "requested_stages": list(factor_service.FACTOR_UNIVERSE_WORKER_BATCH_REQUIRED_STAGES)},
        now,
    )
    worker_batch_dry_run, worker_batch_rows = factor_service._factor_universe_worker_batch_dry_run_receipt(worker_batch_payload, now)
    required_worker_stage_scope = list(factor_service.FACTOR_UNIVERSE_WORKER_BATCH_REQUIRED_STAGES)
    selected_worker_stage_scope = [str(item) for item in _list(worker_batch_payload.get("requested_stages"))]
    worker_stage_scope_rows = _worker_stage_scope_rows(required_worker_stage_scope, selected_worker_stage_scope)

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
    receipt_packet = {
        "universe_research_contract": plan_contract,
        "universe_research_task_plan": read_plan,
        "universe_execution_readiness_audit": readiness,
        "universe_execution_readiness_rows": list(readiness.get("rows") or []),
        "universe_local_rank_zscore_dry_run": rank_zscore_dry_run,
    }
    execution_receipt = factor_service._factor_universe_execution_readiness_receipt(receipt_packet, now)
    activation_packet = dict(receipt_packet)
    activation_packet["universe_execution_readiness_receipt"] = execution_receipt
    execution_activation = factor_service._factor_universe_execution_activation_receipt(activation_packet, now)
    recipe_packet = dict(activation_packet)
    recipe_packet["universe_execution_activation_receipt"] = execution_activation
    recipe_packet["universe_worker_batch_dry_run_receipt"] = worker_batch_dry_run
    worker_batch_execution_recipe = factor_service._factor_universe_worker_batch_execution_recipe(recipe_packet, now)
    worker_batch_execution_rows = [
        row for row in _list(worker_batch_execution_recipe.get("rows")) if isinstance(row, dict)
    ]
    recipe_packet["universe_worker_batch_execution_recipe"] = worker_batch_execution_recipe
    recipe_packet["universe_worker_batch_execution_rows"] = worker_batch_execution_rows
    worker_batch_execution_request_payload = factor_service._factor_universe_worker_batch_execution_request_payload(
        {
            "approved_by_user": True,
            "worker_batch_scope_hash": worker_batch_dry_run.get("worker_batch_scope_hash"),
        },
        recipe_packet,
        now,
    )
    worker_batch_execution_request, worker_batch_execution_request_rows = (
        factor_service._factor_universe_worker_batch_execution_request_receipt(
            worker_batch_execution_request_payload,
            now,
        )
    )
    recipe_packet["universe_worker_batch_execution_request_receipt"] = worker_batch_execution_request
    recipe_packet["universe_worker_batch_execution_request_rows"] = worker_batch_execution_request_rows
    worker_batch_research_payload = factor_service._factor_universe_worker_batch_research_payload(
        {
            "approved_by_user": True,
            "worker_batch_scope_hash": worker_batch_execution_request.get("worker_batch_scope_hash"),
            "execution_request_task_id": "local-contract-execution-request",
        },
        recipe_packet,
        now,
    )
    worker_batch_research_receipt, worker_batch_research_rows = (
        factor_service._factor_universe_worker_batch_research_receipt(
            worker_batch_research_payload,
            now,
        )
    )
    recipe_packet["universe_worker_batch_research_receipt"] = worker_batch_research_receipt
    recipe_packet["universe_worker_batch_research_rows"] = worker_batch_research_rows
    durable_evidence_recipe, durable_evidence_rows, durable_evidence_ledger = (
        factor_service._factor_universe_durable_evidence_recipe(recipe_packet, now)
    )
    worker_batch_execution_phase_keys = [str(row.get("phase_key") or "") for row in worker_batch_execution_rows]
    durable_rows_by_key = {
        str(row.get("evidence_key") or ""): row
        for row in durable_evidence_rows
        if isinstance(row, dict)
    }
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
    worker_batch_task = _dict(task_catalog.get("run_factor_universe_worker_batch_dry_run"))
    worker_batch_request_task = _dict(task_catalog.get("run_factor_universe_worker_batch_execution_request"))
    worker_batch_research_task = _dict(task_catalog.get("run_factor_universe_worker_batch_research"))
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
            "execution_readiness_receipt_is_local",
            execution_receipt.get("schema_version") == "factor_universe_execution_readiness_receipt.v1"
            and execution_receipt.get("scope") == "local_factor_universe_execution_readiness_receipt_no_batch_or_provider_execution"
            and execution_receipt.get("local_receipt_ready") is True
            and execution_receipt.get("ready_for_explicit_worker_batch_task") is True
            and execution_receipt.get("allowed_next_step") == "explicit_post_task_factor_universe_worker_batch_research"
            and execution_receipt.get("large_universe_pipeline_done") is False
            and execution_receipt.get("cross_sectional_rank_zscore_done") is False
            and execution_receipt.get("neutralization_done") is False
            and execution_receipt.get("full_pool_validation_done") is False
            and execution_receipt.get("production_factor_universe_complete") is False
            and execution_receipt.get("provider_refresh_called_by_receipt") is False
            and execution_receipt.get("worker_batch_executed_by_receipt") is False
            and execution_receipt.get("receipt_external_calls_triggered") is False
            and execution_receipt.get("tushare_called_by_receipt") is False
            and execution_receipt.get("deepseek_called") is False
            and execution_receipt.get("github_called") is False
            and execution_receipt.get("does_not_execute_trades") is True
            and execution_receipt.get("does_not_modify_strategy_action") is True
            and "GET /api/factor-quant/cache full-pool execution" in execution_receipt.get("not_allowed_next_steps", [])
            and "frontend rank/zscore calculation" in execution_receipt.get("not_allowed_next_steps", [])
            and "read-plan as production completion" in execution_receipt.get("not_allowed_next_steps", []),
            "Universe execution readiness receipt may allow the next explicit worker-batch task, but it must stay local and cannot execute batch research or promote production flags.",
        ),
        _row(
            "execution_activation_receipt_is_local",
            execution_activation.get("schema_version") == "factor_universe_execution_activation_receipt.v1"
            and execution_activation.get("scope") == "local_factor_universe_execution_activation_receipt_no_worker_or_provider_execution"
            and execution_activation.get("local_activation_receipt_ready") is True
            and execution_activation.get("ready_for_explicit_worker_batch_task") is True
            and execution_activation.get("allowed_next_step") == "explicit_post_task_factor_universe_worker_batch_research"
            and execution_activation.get("worker_batch_created_by_receipt") is False
            and execution_activation.get("worker_batch_executed_by_receipt") is False
            and execution_activation.get("rank_zscore_computed_by_receipt") is False
            and execution_activation.get("neutralization_computed_by_receipt") is False
            and execution_activation.get("provider_refresh_called_by_receipt") is False
            and execution_activation.get("large_universe_pipeline_done") is False
            and execution_activation.get("cross_sectional_rank_zscore_done") is False
            and execution_activation.get("neutralization_done") is False
            and execution_activation.get("factor_combination_research_done") is False
            and execution_activation.get("full_pool_validation_done") is False
            and execution_activation.get("production_factor_universe_complete") is False
            and execution_activation.get("cache_get_external_calls") is False
            and execution_activation.get("activation_receipt_external_calls_triggered") is False
            and execution_activation.get("tushare_called_by_receipt") is False
            and execution_activation.get("deepseek_called") is False
            and execution_activation.get("github_called") is False
            and execution_activation.get("does_not_execute_trades") is True
            and execution_activation.get("does_not_modify_strategy_action") is True
            and int(execution_activation.get("production_blocker_count") or 0) >= 5
            and "GET /api/factor-quant/cache worker batch execution" in execution_activation.get("not_allowed_next_steps", [])
            and "activation receipt creates worker task" in execution_activation.get("not_allowed_next_steps", [])
            and "local rank/zscore dry-run as production research" in execution_activation.get("not_allowed_next_steps", []),
            "Universe execution activation receipt may fix the next explicit worker-batch gate, but it must not create tasks, execute workers, compute production metrics, call providers, or promote production flags.",
        ),
        _row(
            "worker_batch_dry_run_ticket_is_local",
            worker_batch_dry_run.get("schema_version") == "factor_universe_worker_batch_dry_run.v1"
            and worker_batch_dry_run.get("scope") == "local_factor_universe_worker_batch_dry_run_no_worker_or_provider_execution"
            and worker_batch_dry_run.get("local_dry_run_ready") is True
            and worker_batch_dry_run.get("preflight_ready_for_explicit_worker_batch_task") is True
            and worker_batch_dry_run.get("ready_to_execute_worker_task") is False
            and worker_batch_dry_run.get("worker_batch_scope_hash_short")
            and worker_batch_dry_run.get("worker_execution_implemented") is False
            and worker_batch_dry_run.get("worker_batch_executed") is False
            and worker_batch_dry_run.get("large_universe_pipeline_done") is False
            and worker_batch_dry_run.get("cross_sectional_rank_zscore_done") is False
            and worker_batch_dry_run.get("neutralization_done") is False
            and worker_batch_dry_run.get("factor_combination_research_done") is False
            and worker_batch_dry_run.get("full_pool_validation_done") is False
            and worker_batch_dry_run.get("production_factor_universe_complete") is False
            and worker_batch_dry_run.get("page_render_starts_full_pool") is False
            and worker_batch_dry_run.get("frontend_computes_rank_zscore") is False
            and worker_batch_dry_run.get("cache_get_external_calls") is False
            and _flag_false(worker_batch_dry_run, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and worker_batch_dry_run.get("does_not_execute_trades") is True
            and worker_batch_dry_run.get("does_not_modify_strategy_action") is True
            and any(_dict(row).get("criterion") == "worker_execution_implementation_boundary" and _dict(row).get("status") == "pending_worker_execution_not_implemented" for row in worker_batch_rows),
            "Worker-batch dry-run may create a local scope ticket only; it must not start workers, call providers/models, compute production metrics, or promote completion flags.",
        ),
        _row(
            "worker_stage_scope_manifest_is_complete_and_pending",
            [row.get("stage_key") for row in worker_stage_scope_rows] == required_worker_stage_scope
            and set(selected_worker_stage_scope) == set(required_worker_stage_scope)
            and worker_batch_payload.get("missing_required_stages") == []
            and worker_batch_dry_run.get("missing_required_stages") == []
            and all(
                isinstance(row, dict)
                and row.get("scope") == "factor_universe_worker_batch_stage_scope_manifest"
                and row.get("selected_by_worker_dry_run_scope") is True
                and row.get("required_before_production") is True
                and row.get("worker_execution_implemented") is False
                and row.get("worker_batch_executed") is False
                and row.get("large_universe_pipeline_done") is False
                and row.get("cross_sectional_rank_zscore_done") is False
                and row.get("neutralization_done") is False
                and row.get("factor_combination_research_done") is False
                and row.get("full_pool_validation_done") is False
                and row.get("production_factor_universe_complete") is False
                and row.get("page_render_starts_full_pool") is False
                and row.get("frontend_computes_rank_zscore") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called_by_contract") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                and row.get("contains_secret") is False
                for row in worker_stage_scope_rows
            ),
            "Required Factor universe worker stages must be visible as a pending local scope manifest without worker/provider/model execution.",
        ),
        _row(
            "worker_batch_execution_recipe_is_local_pending",
            worker_batch_execution_recipe.get("schema_version") == "factor_universe_worker_batch_execution_recipe.v1"
            and worker_batch_execution_recipe.get("scope") == "local_factor_universe_worker_batch_execution_recipe_no_worker_or_provider_execution"
            and worker_batch_execution_recipe.get("status") == "factor_universe_worker_batch_execution_recipe_ready_execution_pending"
            and worker_batch_execution_recipe.get("local_recipe_ready") is True
            and worker_batch_execution_recipe.get("execution_recipe_ready") is True
            and worker_batch_execution_recipe.get("scope_ticket_ready") is True
            and worker_batch_execution_recipe.get("activation_ready_for_worker_batch") is True
            and worker_batch_execution_recipe.get("worker_batch_scope_hash_short")
            and worker_batch_execution_recipe.get("phase_keys") == list(REQUIRED_WORKER_BATCH_EXECUTION_PHASES)
            and worker_batch_execution_recipe.get("pending_phases") == list(REQUIRED_WORKER_BATCH_EXECUTION_PHASES)
            and worker_batch_execution_recipe.get("allowed_execution_sequence") == list(REQUIRED_WORKER_BATCH_EXECUTION_PHASES)
            and "explicit worker task_id bound to scope hash" in worker_batch_execution_recipe.get("required_evidence", [])
            and "cross-sectional rank and zscore output" in worker_batch_execution_recipe.get("required_evidence", [])
            and "manual promotion review" in worker_batch_execution_recipe.get("required_evidence", [])
            and "treat_recipe_as_worker_execution_evidence" in worker_batch_execution_recipe.get("not_allowed_next_steps", [])
            and "create worker task from GET cache" in worker_batch_execution_recipe.get("not_allowed_next_steps", [])
            and "call Tushare or DeepSeek from this recipe" in worker_batch_execution_recipe.get("not_allowed_next_steps", [])
            and "compute rank/zscore in React" in worker_batch_execution_recipe.get("not_allowed_next_steps", [])
            and "mark production Factor universe complete from recipe" in worker_batch_execution_recipe.get("not_allowed_next_steps", [])
            and worker_batch_execution_recipe.get("worker_task_created") is False
            and worker_batch_execution_recipe.get("worker_task_executed") is False
            and worker_batch_execution_recipe.get("worker_started") is False
            and worker_batch_execution_recipe.get("storage_read_executed") is False
            and worker_batch_execution_recipe.get("large_universe_pipeline_done") is False
            and worker_batch_execution_recipe.get("cross_sectional_rank_zscore_done") is False
            and worker_batch_execution_recipe.get("neutralization_done") is False
            and worker_batch_execution_recipe.get("factor_combination_research_done") is False
            and worker_batch_execution_recipe.get("result_summary_persisted") is False
            and worker_batch_execution_recipe.get("full_pool_validation_done") is False
            and worker_batch_execution_recipe.get("production_factor_universe_complete") is False
            and worker_batch_execution_recipe.get("page_render_starts_full_pool") is False
            and worker_batch_execution_recipe.get("frontend_computes_rank_zscore") is False
            and _flag_false(worker_batch_execution_recipe, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and worker_batch_execution_recipe.get("does_not_execute_trades") is True
            and worker_batch_execution_recipe.get("does_not_modify_strategy_action") is True
            and worker_batch_execution_recipe.get("contains_secret") is False
            and worker_batch_execution_phase_keys == list(REQUIRED_WORKER_BATCH_EXECUTION_PHASES)
            and all(
                row.get("scope") == "factor_universe_worker_batch_execution_recipe"
                and row.get("selected_by_worker_dry_run_scope") is True
                and row.get("required_before_production") is True
                and row.get("worker_task_created") is False
                and row.get("worker_task_executed") is False
                and row.get("worker_started") is False
                and row.get("storage_read_executed") is False
                and row.get("large_universe_pipeline_done") is False
                and row.get("cross_sectional_rank_zscore_done") is False
                and row.get("neutralization_done") is False
                and row.get("factor_combination_research_done") is False
                and row.get("result_summary_persisted") is False
                and row.get("full_pool_validation_done") is False
                and row.get("production_factor_universe_complete") is False
                and row.get("page_render_starts_full_pool") is False
                and row.get("frontend_computes_rank_zscore") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                and row.get("contains_secret") is False
                for row in worker_batch_execution_rows
            )
            and _list(worker_batch_execution_recipe.get("call_ledger"))[0].get("api") == "local_factor_universe_worker_batch_execution_recipe",
            "Worker-batch execution recipe may define the future ordered runtime path only; it must not create worker tasks, start workers, compute rank/zscore, call providers/models, or promote production completion.",
        ),
        _row(
            "worker_batch_execution_request_is_scope_bound_local",
            worker_batch_execution_request.get("schema_version") == "factor_universe_worker_batch_execution_request.v1"
            and worker_batch_execution_request.get("scope") == "local_factor_universe_worker_batch_execution_request_no_worker_or_provider_execution"
            and worker_batch_execution_request.get("status") == "factor_universe_worker_batch_execution_request_ready_manual_worker_task_pending"
            and worker_batch_execution_request.get("local_execution_request_ready") is True
            and worker_batch_execution_request.get("ready_for_manual_worker_task_submission") is True
            and worker_batch_execution_request.get("requested_scope_hash_matches_latest") is True
            and worker_batch_execution_request.get("worker_batch_scope_hash_short") == worker_batch_dry_run.get("worker_batch_scope_hash_short")
            and worker_batch_execution_request.get("target_worker_task_route") == "POST /api/factor-quant/universe-worker-batch-research"
            and worker_batch_execution_request.get("target_worker_task_type") == "run_factor_universe_worker_batch_research"
            and worker_batch_execution_request.get("target_acceptance_mode") == "worker_backed_factor_universe_batch_research"
            and worker_batch_execution_request.get("worker_task_created") is False
            and worker_batch_execution_request.get("worker_task_executed") is False
            and worker_batch_execution_request.get("worker_execution_implemented") is False
            and worker_batch_execution_request.get("worker_started") is False
            and worker_batch_execution_request.get("storage_read_executed") is False
            and worker_batch_execution_request.get("large_universe_pipeline_done") is False
            and worker_batch_execution_request.get("cross_sectional_rank_zscore_done") is False
            and worker_batch_execution_request.get("neutralization_done") is False
            and worker_batch_execution_request.get("factor_combination_research_done") is False
            and worker_batch_execution_request.get("result_summary_persisted") is False
            and worker_batch_execution_request.get("full_pool_validation_done") is False
            and worker_batch_execution_request.get("production_factor_universe_complete") is False
            and worker_batch_execution_request.get("cache_get_external_calls") is False
            and worker_batch_execution_request.get("react_render_external_calls") is False
            and _flag_false(worker_batch_execution_request, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and worker_batch_execution_request.get("does_not_execute_trades") is True
            and worker_batch_execution_request.get("does_not_modify_strategy_action") is True
            and worker_batch_execution_request.get("contains_secret") is False
            and worker_batch_execution_request.get("blocking_criterion_count") == 0
            and "treat_execution_request_as_worker_batch_execution" in worker_batch_execution_request.get("not_allowed_next_steps", [])
            and "create worker task from GET cache" in worker_batch_execution_request.get("not_allowed_next_steps", [])
            and "start worker from execution request" in worker_batch_execution_request.get("not_allowed_next_steps", [])
            and "compute production rank/zscore from execution request" in worker_batch_execution_request.get("not_allowed_next_steps", [])
            and _list(worker_batch_execution_request.get("call_ledger"))[0].get("api") == "local_factor_universe_worker_batch_execution_request",
            "Worker-batch execution request may bind a future manual worker task scope only; it must not create or start workers, compute metrics, call providers/models, or promote production completion.",
        ),
        _row(
            "worker_batch_research_receipt_is_local_task_record_only",
            worker_batch_research_receipt.get("schema_version") == "factor_universe_worker_batch_research_receipt.v1"
            and worker_batch_research_receipt.get("scope") == "local_factor_universe_worker_batch_research_receipt_no_worker_or_provider_execution"
            and worker_batch_research_receipt.get("status") == "factor_universe_worker_batch_research_receipt_ready_worker_runtime_evidence_pending"
            and worker_batch_research_receipt.get("local_receipt_ready") is True
            and worker_batch_research_receipt.get("local_worker_research_receipt_ready") is True
            and worker_batch_research_receipt.get("requested_scope_hash_matches_latest") is True
            and worker_batch_research_receipt.get("worker_batch_scope_hash_short") == worker_batch_execution_request.get("worker_batch_scope_hash_short")
            and worker_batch_research_receipt.get("target_worker_task_route") == "POST /api/factor-quant/universe-worker-batch-research"
            and worker_batch_research_receipt.get("target_worker_task_type") == "run_factor_universe_worker_batch_research"
            and worker_batch_research_receipt.get("target_acceptance_mode") == "worker_backed_factor_universe_batch_research"
            and worker_batch_research_receipt.get("local_worker_task_record_created") is True
            and worker_batch_research_receipt.get("worker_task_created") is False
            and worker_batch_research_receipt.get("worker_task_executed") is False
            and worker_batch_research_receipt.get("worker_execution_implemented") is False
            and worker_batch_research_receipt.get("worker_process_started") is False
            and worker_batch_research_receipt.get("worker_started") is False
            and worker_batch_research_receipt.get("redis_pinged") is False
            and worker_batch_research_receipt.get("storage_read_executed") is False
            and worker_batch_research_receipt.get("large_universe_pipeline_done") is False
            and worker_batch_research_receipt.get("cross_sectional_rank_zscore_done") is False
            and worker_batch_research_receipt.get("zscore_done") is False
            and worker_batch_research_receipt.get("neutralization_done") is False
            and worker_batch_research_receipt.get("factor_combination_research_done") is False
            and worker_batch_research_receipt.get("result_summary_persisted") is False
            and worker_batch_research_receipt.get("full_pool_validation_done") is False
            and worker_batch_research_receipt.get("production_factor_universe_complete") is False
            and worker_batch_research_receipt.get("cache_get_external_calls") is False
            and worker_batch_research_receipt.get("react_render_external_calls") is False
            and _flag_false(worker_batch_research_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and worker_batch_research_receipt.get("does_not_execute_trades") is True
            and worker_batch_research_receipt.get("does_not_modify_strategy_action") is True
            and worker_batch_research_receipt.get("contains_secret") is False
            and worker_batch_research_receipt.get("blocking_criterion_count") == 0
            and "treat_local_receipt_as_worker_runtime_execution" in worker_batch_research_receipt.get("not_allowed_next_steps", [])
            and "start worker from GET cache" in worker_batch_research_receipt.get("not_allowed_next_steps", [])
            and "compute production rank/zscore from local receipt" in worker_batch_research_receipt.get("not_allowed_next_steps", [])
            and _list(worker_batch_research_receipt.get("call_ledger"))[0].get("api") == "local_factor_universe_worker_batch_research_receipt",
            "Worker-batch research receipt may record a local task receipt only; it must not start workers, compute metrics, call providers/models/GitHub, or promote production completion.",
        ),
        _row(
            "factor_universe_durable_evidence_recipe_is_local_production_pending",
            durable_evidence_recipe.get("schema_version") == "factor_universe_durable_evidence_recipe.v1"
            and durable_evidence_recipe.get("scope") == "local_factor_universe_durable_evidence_recipe_no_worker_or_provider_execution"
            and durable_evidence_recipe.get("status") == "factor_universe_durable_evidence_recipe_ready_production_pending"
            and durable_evidence_recipe.get("local_recipe_ready") is True
            and durable_evidence_recipe.get("durable_evidence_complete") is False
            and durable_evidence_recipe.get("durable_promotion_ready") is False
            and durable_evidence_recipe.get("production_factor_universe_complete") is False
            and durable_evidence_recipe.get("evidence_keys") == list(REQUIRED_FACTOR_UNIVERSE_DURABLE_EVIDENCE_KEYS)
            and durable_evidence_recipe.get("local_blockers") == []
            and set(durable_evidence_recipe.get("production_blockers") or []) == PRODUCTION_FACTOR_UNIVERSE_DURABLE_BLOCKER_KEYS
            and durable_evidence_recipe.get("production_blocker_count") == len(PRODUCTION_FACTOR_UNIVERSE_DURABLE_BLOCKER_KEYS)
            and "explicit worker task_id bound to scope hash" in durable_evidence_recipe.get("required_evidence", [])
            and "worker runtime binding and durable task logs" in durable_evidence_recipe.get("required_evidence", [])
            and "cross-sectional rank output" in durable_evidence_recipe.get("required_evidence", [])
            and "zscore output" in durable_evidence_recipe.get("required_evidence", [])
            and "full-pool validation report" in durable_evidence_recipe.get("required_evidence", [])
            and "manual promotion review" in durable_evidence_recipe.get("required_evidence", [])
            and "treat_durable_recipe_as_production_completion" in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and "treat_durable_recipe_as_worker_backed_batch_execution" in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and "create worker task from GET cache" in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and "start worker from GET cache" in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and "call Tushare or DeepSeek from this recipe" in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and "compute rank/zscore in React" in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and "partial pool as full-market proof" in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and durable_evidence_recipe.get("worker_task_created") is False
            and durable_evidence_recipe.get("worker_task_executed") is False
            and durable_evidence_recipe.get("worker_started") is False
            and durable_evidence_recipe.get("storage_read_executed") is False
            and durable_evidence_recipe.get("large_universe_pipeline_done") is False
            and durable_evidence_recipe.get("cross_sectional_rank_zscore_done") is False
            and durable_evidence_recipe.get("zscore_done") is False
            and durable_evidence_recipe.get("neutralization_done") is False
            and durable_evidence_recipe.get("factor_combination_research_done") is False
            and durable_evidence_recipe.get("result_summary_persisted") is False
            and durable_evidence_recipe.get("full_pool_validation_done") is False
            and durable_evidence_recipe.get("page_render_starts_full_pool") is False
            and durable_evidence_recipe.get("frontend_computes_rank_zscore") is False
            and _flag_false(durable_evidence_recipe, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and durable_evidence_recipe.get("does_not_execute_trades") is True
            and durable_evidence_recipe.get("does_not_modify_strategy_action") is True
            and durable_evidence_recipe.get("contains_secret") is False
            and set(durable_rows_by_key) == set(REQUIRED_FACTOR_UNIVERSE_DURABLE_EVIDENCE_KEYS)
            and all(
                durable_rows_by_key[key].get("passed") is True
                and durable_rows_by_key[key].get("local_surface_required") is True
                and durable_rows_by_key[key].get("production_blocker") is False
                for key in LOCAL_FACTOR_UNIVERSE_DURABLE_SURFACE_KEYS
            )
            and all(
                durable_rows_by_key[key].get("passed") is False
                and durable_rows_by_key[key].get("production_blocker") is True
                for key in PRODUCTION_FACTOR_UNIVERSE_DURABLE_BLOCKER_KEYS
            )
            and all(
                row.get("scope") == "factor_universe_durable_evidence_recipe"
                and row.get("worker_task_created") is False
                and row.get("worker_task_executed") is False
                and row.get("worker_started") is False
                and row.get("storage_read_executed") is False
                and row.get("large_universe_pipeline_done") is False
                and row.get("cross_sectional_rank_zscore_done") is False
                and row.get("zscore_done") is False
                and row.get("neutralization_done") is False
                and row.get("factor_combination_research_done") is False
                and row.get("result_summary_persisted") is False
                and row.get("full_pool_validation_done") is False
                and row.get("production_factor_universe_complete") is False
                and row.get("page_render_starts_full_pool") is False
                and row.get("frontend_computes_rank_zscore") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                and row.get("contains_secret") is False
                for row in durable_evidence_rows
            )
            and durable_evidence_ledger[0].get("api") == "local_factor_universe_durable_evidence_recipe",
            "Durable evidence recipe may list LTG-04 direct production evidence only; it must not be treated as worker execution, full-pool validation, provider/model evidence, or production completion.",
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
            "task_catalog_is_button_gated_read_plan_worker_dry_run_execution_request_and_research_receipt_only",
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
            and worker_batch_task.get("route") == "POST /api/factor-quant/universe-worker-batch-dry-run"
            and worker_batch_task.get("button_gated") is True
            and worker_batch_task.get("current_backend") == "local_factor_universe_worker_batch_dry_run_pipeline"
            and worker_batch_task.get("external_call_policy") == "local_worker_batch_dry_run_no_worker_provider_or_model_call"
            and worker_batch_task.get("possible_external_sources") == []
            and worker_batch_task.get("local_dry_run_only") is True
            and worker_batch_task.get("scope_hash_ticket") is True
            and worker_batch_task.get("worker_execution_implemented") is False
            and worker_batch_task.get("worker_batch_executed") is False
            and worker_batch_task.get("large_universe_pipeline_done") is False
            and worker_batch_task.get("cross_sectional_rank_zscore_done") is False
            and worker_batch_task.get("neutralization_done") is False
            and worker_batch_task.get("production_factor_universe_complete") is False
            and worker_batch_task.get("cache_get_external_calls") is False
            and worker_batch_task.get("react_render_direct_worker_calls") is False
            and worker_batch_task.get("does_not_execute_trades") is True
            and worker_batch_task.get("does_not_modify_strategy_action") is True
            and worker_batch_request_task.get("route") == "POST /api/factor-quant/universe-worker-batch-execution-request"
            and worker_batch_request_task.get("button_gated") is True
            and worker_batch_request_task.get("current_backend") == "local_factor_universe_worker_batch_execution_request_pipeline"
            and worker_batch_request_task.get("external_call_policy") == "local_execution_request_no_worker_provider_or_model_call"
            and worker_batch_request_task.get("possible_external_sources") == []
            and worker_batch_request_task.get("local_execution_request_only") is True
            and worker_batch_request_task.get("requires_bound_scope_hash") is True
            and worker_batch_request_task.get("target_worker_task_route") == "POST /api/factor-quant/universe-worker-batch-research"
            and worker_batch_request_task.get("creates_worker_task") is False
            and worker_batch_request_task.get("starts_worker") is False
            and worker_batch_request_task.get("starts_celery_worker") is False
            and worker_batch_request_task.get("pings_redis") is False
            and worker_batch_request_task.get("worker_execution_implemented") is False
            and worker_batch_request_task.get("worker_task_executed_by_request") is False
            and worker_batch_request_task.get("large_universe_pipeline_done") is False
            and worker_batch_research_task.get("route") == "POST /api/factor-quant/universe-worker-batch-research"
            and worker_batch_research_task.get("button_gated") is True
            and worker_batch_research_task.get("current_backend") == "local_factor_universe_worker_batch_research_receipt_or_execution_evidence_pipeline"
            and worker_batch_research_task.get("external_call_policy") == "local_worker_batch_evidence_no_celery_redis_provider_or_model_call"
            and worker_batch_research_task.get("possible_external_sources") == []
            and worker_batch_research_task.get("local_worker_research_receipt_only") is False
            and worker_batch_research_task.get("supports_local_worker_execution_evidence") is True
            and worker_batch_research_task.get("requires_bound_scope_hash") is True
            and worker_batch_research_task.get("creates_worker_task") is True
            and worker_batch_research_task.get("starts_worker") is False
            and worker_batch_research_task.get("starts_celery_worker") is False
            and worker_batch_research_task.get("pings_redis") is False
            and worker_batch_research_task.get("worker_execution_implemented") is True
            and worker_batch_research_task.get("worker_process_started") is False
            and worker_batch_research_task.get("storage_read_executed") is True
            and worker_batch_research_task.get("large_universe_pipeline_done") is False
            and worker_batch_research_task.get("cross_sectional_rank_zscore_done") is True
            and worker_batch_research_task.get("zscore_done") is True
            and worker_batch_research_task.get("neutralization_done") is False
            and worker_batch_research_task.get("factor_combination_research_done") is True
            and worker_batch_research_task.get("result_summary_persisted") is True
            and worker_batch_research_task.get("production_factor_universe_complete") is False
            and worker_batch_research_task.get("cache_get_external_calls") is False
            and worker_batch_research_task.get("react_render_direct_worker_calls") is False
            and worker_batch_research_task.get("does_not_execute_trades") is True
            and worker_batch_research_task.get("does_not_modify_strategy_action") is True
            and worker_batch_request_task.get("cross_sectional_rank_zscore_done") is False
            and worker_batch_request_task.get("neutralization_done") is False
            and worker_batch_request_task.get("production_factor_universe_complete") is False
            and worker_batch_request_task.get("cache_get_external_calls") is False
            and worker_batch_request_task.get("react_render_direct_worker_calls") is False
            and worker_batch_request_task.get("does_not_execute_trades") is True
            and worker_batch_request_task.get("does_not_modify_strategy_action") is True
            and light_task.get("universe_modes") == ["current_target", "watchlist", "custom_pool"]
            and light_task.get("future_universe_modes") == ["full_pool"]
            and light_task.get("local_rank_zscore_seed_supported") is True
            and light_task.get("local_rank_zscore_seed_is_provider_acceptance") is False
            and light_task.get("production_factor_universe_complete") is False,
            "Task catalog must keep factor universe work button-gated: run-light may write a local watchlist/custom_pool rank/zscore seed, and the worker-batch route may record explicit local execution evidence without Celery/Redis/provider/model calls while neutralization/full-pool production evidence remains pending.",
        ),
        _row(
            "frontend_displays_plan_and_does_not_compute_universe",
            "export function postTask" in api_client
            and "fetch(`${API_BASE}${path}`" in api_client
            and "import { getFactorQuantCache, postTask" in factor_page
            and "launchTask(\"/api/factor-quant/universe-research-plan\"" in factor_page
            and "launchTask(\"/api/factor-quant/universe-worker-batch-dry-run\"" in factor_page
            and "launchTask(\"/api/factor-quant/universe-worker-batch-execution-request\"" in factor_page
            and "universe_execution_readiness_audit" in factor_page
            and "universe_execution_readiness_receipt" in factor_page
            and "universe_execution_activation_receipt" in factor_page
            and "universe_local_rank_zscore_dry_run" in factor_page
            and "Factor Universe 执行准入回执" in factor_page
            and "Factor Universe execution activation receipt" in factor_page
            and "不创建任务、不启动 worker" in factor_page
            and "Factor Universe worker-batch dry-run ticket" in factor_page
            and "universe_worker_batch_dry_run_receipt" in factor_page
            and "不代表 worker-backed batch execution" in factor_page
            and "Factor Universe worker-batch execution request" in factor_page
            and "universe_worker_batch_execution_request_receipt" in factor_page
            and "不创建 worker task、不启动 worker" in factor_page
            and "Factor Universe worker-batch research receipt" in factor_page
            and "universe_worker_batch_research_receipt" in factor_page
            and "不启动 worker、不 ping Redis/Celery" in factor_page
            and "Factor Universe durable evidence recipe" in factor_page
            and "universe_durable_evidence_recipe" in factor_page
            and "universe_durable_evidence_rows" in factor_page
            and "LTG-04 worker-backed / full-pool" in factor_page
            and "不启动 worker、不调用 Tushare/DeepSeek/GitHub" in factor_page
            and "不在前端计算 rank/zscore" in factor_page
            and "production_factor_universe_complete" in factor_page
            and "批量研究预检" in factor_page
            and "Factor Universe 本地 Rank/Zscore Dry-run" in factor_page
            and "前端不计算 rank/zscore" in factor_page
            and "显式 worker batch" in factor_page
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
            and "worker_batch_dry_run_ticket_is_local" in this_script
            and "worker_stage_scope_manifest_is_complete_and_pending" in this_script
            and "worker_batch_execution_recipe_is_local_pending" in this_script
            and "worker_batch_execution_request_is_scope_bound_local" in this_script
            and "worker_batch_research_receipt_is_local_task_record_only" in this_script
            and "local_worker_batch_execution_evidence" in this_script
            and "task_catalog_is_button_gated_read_plan_worker_dry_run_execution_request_and_research_receipt_only" in this_script
            and "factor_universe_durable_evidence_recipe_is_local_production_pending" in this_script
            and "factor_universe_worker_batch_execution_recipe.v1" in this_script
            and "local_factor_universe_worker_batch_execution_recipe_no_worker_or_provider_execution" in this_script
            and "factor_universe_worker_batch_execution_request.v1" in this_script
            and "local_factor_universe_worker_batch_execution_request_no_worker_or_provider_execution" in this_script
            and "factor_universe_worker_batch_research_receipt.v1" in this_script
            and "local_factor_universe_worker_batch_research_receipt_no_worker_or_provider_execution" in this_script
            and "local_factor_universe_worker_batch_execution_evidence_no_celery_no_provider" in this_script
            and "factor_universe_durable_evidence_recipe.v1" in this_script
            and "local_factor_universe_durable_evidence_recipe_no_worker_or_provider_execution" in this_script
            and "run_factor_universe_worker_batch_dry_run" in this_script
            and "run_factor_universe_worker_batch_execution_request" in this_script
            and "run_factor_universe_worker_batch_research" in this_script
            and "execution_readiness_receipt_is_local" in this_script
            and "execution_activation_receipt_is_local" in this_script
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
        "ready_for_explicit_worker_batch_task": bool(execution_receipt.get("ready_for_explicit_worker_batch_task")),
        "execution_activation_receipt_ready": bool(execution_activation.get("local_activation_receipt_ready")),
        "worker_batch_dry_run_ready": bool(worker_batch_dry_run.get("local_dry_run_ready")),
        "worker_batch_scope_ticket_ready": bool(worker_batch_dry_run.get("worker_batch_scope_hash_short")),
        "worker_batch_execution_recipe_ready": bool(worker_batch_execution_recipe.get("local_recipe_ready")),
        "worker_batch_execution_request_ready": bool(worker_batch_execution_request.get("local_execution_request_ready")),
        "worker_batch_research_receipt_ready": bool(worker_batch_research_receipt.get("local_worker_research_receipt_ready")),
        "factor_universe_durable_evidence_recipe_ready": bool(durable_evidence_recipe.get("local_recipe_ready")),
        "factor_universe_durable_evidence_recipe_status": durable_evidence_recipe.get("status"),
        "worker_execution_implemented": False,
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
            "execution_receipt_status": execution_receipt.get("status"),
            "execution_receipt_allowed_next_step": execution_receipt.get("allowed_next_step"),
            "execution_activation_status": execution_activation.get("status"),
            "execution_activation_production_blocker_count": execution_activation.get("production_blocker_count"),
            "worker_batch_dry_run_status": worker_batch_dry_run.get("status"),
            "worker_batch_scope_hash_short": worker_batch_dry_run.get("worker_batch_scope_hash_short"),
            "worker_batch_execution_recipe_status": worker_batch_execution_recipe.get("status"),
            "worker_batch_execution_request_status": worker_batch_execution_request.get("status"),
            "worker_batch_execution_request_scope_hash_short": worker_batch_execution_request.get("worker_batch_scope_hash_short"),
            "worker_batch_research_receipt_status": worker_batch_research_receipt.get("status"),
            "worker_batch_research_receipt_scope_hash_short": worker_batch_research_receipt.get("worker_batch_scope_hash_short"),
            "worker_batch_execution_phase_count": len(worker_batch_execution_rows),
            "worker_batch_execution_phase_keys": worker_batch_execution_phase_keys,
            "worker_batch_execution_pending_phase_count": sum(
                1 for row in worker_batch_execution_rows if row.get("worker_task_executed") is False
            ),
            "factor_universe_durable_evidence_recipe_status": durable_evidence_recipe.get("status"),
            "factor_universe_durable_evidence_key_count": len(durable_evidence_rows),
            "factor_universe_durable_evidence_keys": [row.get("evidence_key") for row in durable_evidence_rows],
            "factor_universe_durable_evidence_production_blocker_count": durable_evidence_recipe.get("production_blocker_count"),
            "worker_stage_scope_count": len(worker_stage_scope_rows),
            "worker_stage_scope_keys": [row.get("stage_key") for row in worker_stage_scope_rows],
            "worker_stage_scope_pending_count": sum(
                1 for row in worker_stage_scope_rows if row.get("worker_execution_implemented") is False
            ),
            "task_backend": universe_task.get("current_backend"),
            "worker_batch_task_backend": worker_batch_task.get("current_backend"),
            "worker_batch_execution_request_task_backend": worker_batch_request_task.get("current_backend"),
            "worker_batch_research_task_backend": worker_batch_research_task.get("current_backend"),
        },
        "worker_stage_scope_rows": worker_stage_scope_rows,
        "worker_batch_execution_recipe": worker_batch_execution_recipe,
        "worker_batch_execution_rows": worker_batch_execution_rows,
        "worker_batch_execution_request": worker_batch_execution_request,
        "worker_batch_execution_request_rows": worker_batch_execution_request_rows,
        "worker_batch_research_receipt": worker_batch_research_receipt,
        "worker_batch_research_rows": worker_batch_research_rows,
        "factor_universe_durable_evidence_recipe": durable_evidence_recipe,
        "factor_universe_durable_evidence_rows": durable_evidence_rows,
        "rows": rows,
        "note": "This is a local push-gate contract. Worker batch dry-run is only a scope ticket; worker execution, rank/zscore, neutralization, provider-backed validation, and full-pool production research remain pending.",
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
